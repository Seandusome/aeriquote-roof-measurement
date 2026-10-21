"""Signed Resend inbound events and capability-based support reply routing."""
import base64,hashlib,hmac,json,os,re,secrets,time,uuid
import urllib.request
from datetime import datetime
from email.utils import parseaddr
from html.parser import HTMLParser
from flask import request,jsonify

def init_inbound_db(con):
    con.execute('CREATE TABLE IF NOT EXISTS support_reply_routes (ticket_id TEXT PRIMARY KEY, token TEXT NOT NULL UNIQUE, domain TEXT NOT NULL)')
    con.execute('CREATE TABLE IF NOT EXISTS support_incoming (id TEXT PRIMARY KEY, ticket_id TEXT, received_at TEXT NOT NULL, sender TEXT NOT NULL, subject TEXT NOT NULL, message TEXT NOT NULL, attachment_count INTEGER NOT NULL, match_status TEXT NOT NULL, notification_status TEXT NOT NULL)')
    con.execute('CREATE INDEX IF NOT EXISTS idx_support_incoming_ticket ON support_incoming(ticket_id)')

def receiving_domain():
    value=os.environ.get('SUPPORT_REPLY_DOMAIN','').strip().lower()
    return value if len(value)<=200 and re.fullmatch(r'[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+',value) else ''

def inbound_ready():
    return bool(receiving_domain() and os.environ.get('RESEND_WEBHOOK_SECRET','').strip() and (os.environ.get('RESEND_RECEIVING_API_KEY') or os.environ.get('RESEND_API_KEY','')).strip())

def reply_address(con,ticket_id):
    if not inbound_ready():return ''
    con.execute('INSERT INTO support_reply_routes(ticket_id,token,domain) VALUES(?,?,?) ON CONFLICT(ticket_id) DO NOTHING',(ticket_id,secrets.token_hex(16),receiving_domain()));con.commit()
    row=con.execute('SELECT * FROM support_reply_routes WHERE ticket_id=?',(ticket_id,)).fetchone()
    return 'ticket+'+row['token']+'@'+row['domain']

def valid_signature(raw,headers,secret,now=None):
    try:
        stamp=headers.get('svix-timestamp','');event_id=headers.get('svix-id','');signature=headers.get('svix-signature','')
        if not event_id or len(event_id)>200 or abs((time.time() if now is None else now)-int(stamp))>300:return False
        key=base64.b64decode(secret.removeprefix('whsec_'),validate=True)
        if len(key)<16:return False
        signed=event_id.encode()+b'.'+stamp.encode()+b'.'+raw
        expected=base64.b64encode(hmac.new(key,signed,hashlib.sha256).digest()).decode()
        return any(hmac.compare_digest(expected,item[3:]) for item in signature.split() if item.startswith('v1,'))
    except (ValueError,TypeError,UnicodeError):return False

class PlainHTML(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.parts=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in {'script','style','head'}:self.skip+=1
        if not self.skip and tag in {'br','p','div','li','tr'}:self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in {'script','style','head'}:self.skip=max(0,self.skip-1)
        if not self.skip and tag in {'p','div','li','tr'}:self.parts.append('\n')
    def handle_data(self,data):
        if not self.skip:self.parts.append(data)

def plain_message(email):
    text=email.get('text')
    if not isinstance(text,str) or not text.strip():
        parser=PlainHTML();parser.feed(str(email.get('html') or '')[:1000000]);text=''.join(parser.parts)
    text=text.strip() or '(No text body. View the original email in Resend.)'
    return text[:100000]+('\n[Message shortened. View the full email in Resend.]' if len(text)>100000 else '')

def retrieve_email(email_id):
    key=(os.environ.get('RESEND_RECEIVING_API_KEY') or os.environ.get('RESEND_API_KEY','')).strip()
    if not key:raise RuntimeError('Receiving API key missing')
    req=urllib.request.Request('https://api.resend.com/emails/receiving/'+email_id+'?html_format=cid',headers={'Authorization':'Bearer '+key,'User-Agent':'AeriQuote'})
    with urllib.request.urlopen(req,timeout=12) as response:
        raw=response.read(4000001)
        if len(raw)>4000000:raise RuntimeError('Incoming email exceeds processing limit')
        data=json.loads(raw)
    if not isinstance(data,dict) or data.get('id')!=email_id:raise RuntimeError('Invalid receiving response')
    return data

def import_email(con,email_id,email):
    sender=parseaddr(str(email.get('from') or ''))[1].lower()[:254]
    ticket_ids=set()
    for value in email.get('to',[]) if isinstance(email.get('to'),list) else []:
        address=parseaddr(str(value))[1].lower()
        match=re.fullmatch(r'ticket\+([0-9a-f]{32})@([^@]+)',address)
        if match:
            row=con.execute('SELECT ticket_id FROM support_reply_routes WHERE token=? AND domain=?',(match[1],match[2])).fetchone()
            if row:ticket_ids.add(row['ticket_id'])
    ticket=None
    if len(ticket_ids)==1:ticket=con.execute('SELECT * FROM support_requests WHERE id=?',(next(iter(ticket_ids)),)).fetchone()
    authenticated=email.get('authentication') or {}
    auth_failed=isinstance(authenticated,dict) and authenticated.get('dmarc')=='fail'
    matched=bool(ticket and sender==str(ticket['email']).lower() and not auth_failed)
    headers=email.get('headers') or {};headers={str(k).lower():str(v).lower() for k,v in headers.items()} if isinstance(headers,dict) else {}
    automated=headers.get('auto-submitted','no')!='no' or headers.get('precedence') in {'bulk','junk','list'}
    state=('automated' if automated else 'matched') if matched else 'unmatched'
    ticket_id=ticket['id'] if matched else None
    attachments=email.get('attachments');count=len(attachments) if isinstance(attachments,list) else 0
    inserted=con.execute('INSERT INTO support_incoming(id,ticket_id,received_at,sender,subject,message,attachment_count,match_status,notification_status) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING RETURNING id',(email_id,ticket_id,datetime.utcnow().isoformat()+'Z',sender,str(email.get('subject') or '')[:500],plain_message(email),count,state,'pending' if state=='matched' else 'not_applicable')).fetchone()
    if inserted and state=='matched':con.execute("UPDATE support_requests SET status='open',archived=0 WHERE id=?",(ticket_id,))
    con.commit();return state

def deliver_notification(con,email_id,notify,app):
    row=con.execute('SELECT * FROM support_incoming WHERE id=?',(email_id,)).fetchone()
    if not row or row['match_status']!='matched' or row['notification_status']=='accepted':return
    ticket=con.execute('SELECT * FROM support_requests WHERE id=?',(row['ticket_id'],)).fetchone()
    if not ticket:return
    try:state=notify(dict(ticket),dict(row))
    except Exception:
        state='failed';app.logger.error('Incoming reply is saved but support notification failed.')
    con.execute('UPDATE support_incoming SET notification_status=? WHERE id=?',(state,email_id));con.commit()

def register_inbound(app,estimate_db,notify=None):
    @app.post('/api/public/support/inbound')
    def support_inbound():
        secret=os.environ.get('RESEND_WEBHOOK_SECRET','').strip()
        if not secret:return jsonify(error='Incoming email is not configured.'),503
        if (request.content_length or 0)>262144:return jsonify(error='Event too large.'),413
        raw=request.get_data(cache=False)
        if len(raw)>262144:return jsonify(error='Event too large.'),413
        if not valid_signature(raw,request.headers,secret):return jsonify(error='Invalid signature.'),400
        try:event=json.loads(raw)
        except (ValueError,UnicodeError):return jsonify(error='Invalid event.'),400
        if not isinstance(event,dict):return jsonify(error='Invalid event.'),400
        if event.get('type')!='email.received':return '',204
        try:email_id=str(uuid.UUID(str(event['data']['email_id'])))
        except (KeyError,TypeError,ValueError):return jsonify(error='Invalid email identifier.'),400
        con=estimate_db()
        try:
            if con.execute('SELECT id FROM support_incoming WHERE id=?',(email_id,)).fetchone():
                if notify:deliver_notification(con,email_id,notify,app)
                return jsonify(ok=True,duplicate=True)
            try:email=retrieve_email(email_id)
            except Exception:
                app.logger.error('Incoming support email retrieval failed; webhook delivery should retry.')
                return jsonify(error='Email retrieval temporarily unavailable.'),503
            state=import_email(con,email_id,email)
            if notify:deliver_notification(con,email_id,notify,app)
            return jsonify(ok=True,match=state)
        finally:con.close()
