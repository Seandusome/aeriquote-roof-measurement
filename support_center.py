"""Small web support inbox. Requests are saved before optional email notification."""
import hashlib,hmac,json,os,re,secrets,time,uuid
import urllib.request
from datetime import datetime
from urllib.parse import urlsplit,urlunsplit
from flask import request,session,jsonify,Response,render_template_string
from account_recovery import limited,mail_config

TOPICS={'getting-started':'Getting Started','account-login':'Account & Login','measurement-pdf':'Measurement & PDF Help','bug-report':'Report a Bug','billing':'Billing & Subscription','feature-request':'Feature Request','other':'Other / Privacy'}
STATUSES={'open':'Open','in-progress':'In Progress','resolved':'Resolved'}
DEFAULT_SUPPORT_INBOX='sean@aeriquote.com'  # Explicitly selected by Sean on October15.

def init_support_db(con):
    con.execute('CREATE TABLE IF NOT EXISTS support_requests (id TEXT PRIMARY KEY, reference TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, name TEXT NOT NULL, company TEXT NOT NULL, email TEXT NOT NULL, topic TEXT NOT NULL, message TEXT NOT NULL, device TEXT NOT NULL, page_url TEXT NOT NULL, dealer_id TEXT, fingerprint TEXT NOT NULL, notification_status TEXT NOT NULL)')

    columns={'status':"TEXT NOT NULL DEFAULT 'open'",'archived':"INTEGER NOT NULL DEFAULT 0"}
    if con.postgres:
        for name,definition in columns.items():con.execute('ALTER TABLE support_requests ADD COLUMN IF NOT EXISTS '+name+' '+definition)
    else:
        existing={r['name'] for r in con.execute('PRAGMA table_info(support_requests)').fetchall()}
        for name,definition in columns.items():
            if name not in existing:con.execute('ALTER TABLE support_requests ADD COLUMN '+name+' '+definition)
    con.execute('CREATE TABLE IF NOT EXISTS support_notes (id TEXT PRIMARY KEY, ticket_id TEXT NOT NULL, created_at TEXT NOT NULL, author TEXT NOT NULL, message TEXT NOT NULL)')

def support_inbox():
    return os.environ.get('SUPPORT_INBOX',DEFAULT_SUPPORT_INBOX).strip()

def email_valid(value):
    return len(value)<=254 and bool(re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+',value))

def notify_support(ticket):
    config=mail_config();inbox=support_inbox()
    if not config or not email_valid(inbox):return 'not_configured'
    key,sender,_=config
    text='Support reference: '+ticket['reference']+'\nTopic: '+TOPICS[ticket['topic']]+'\nName: '+ticket['name']+'\nBusiness: '+ticket['company']+'\nReply email: '+ticket['email']+'\nDevice: '+ticket['device']+'\nPage: '+ticket['page_url']+'\n\n'+ticket['message']
    payload={'from':sender,'to':[inbox],'reply_to':ticket['email'],'subject':'AeriQuote support '+ticket['reference']+' | '+TOPICS[ticket['topic']],'text':text}
    req=urllib.request.Request('https://api.resend.com/emails',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','Idempotency-Key':'support-'+ticket['id'],'User-Agent':'AeriQuote'},method='POST')
    with urllib.request.urlopen(req,timeout=12) as response:
        if not 200<=response.status<300:raise RuntimeError('Support notification rejected')
    return 'accepted'

INBOX_HTML='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AeriQuote Support Inbox</title><link rel="stylesheet" href="/site/account-ui.css"><style>body{margin:0;background:#f4f8fc;font:16px Arial;color:#173b61}.wrap{max-width:1000px;margin:30px auto;padding:0 18px}.ticket,.note{padding:22px;background:#fff;border:1px solid #dce5ef;border-radius:12px;margin:18px 0}.message{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.6}a{color:#0757a6}.meta{font-size:14px;line-height:1.7;color:#465d75}label{display:block;margin:12px 0 6px;font-weight:bold}textarea,select{font:inherit;padding:10px;max-width:100%;box-sizing:border-box}textarea{width:100%;min-height:90px}.actions{display:flex;flex-wrap:wrap;gap:10px;margin:15px 0}.private{background:#f2f6fc;padding:14px;margin:10px 0;border-radius:8px}.danger{color:#a12929}button{padding:12px 16px;border:0;border-radius:8px;background:#125da8;color:#fff;cursor:pointer}</style></head><body><main class="wrap"><a href="/head-office/dealers">← Admin Dashboard</a><h1>Support requests</h1><p>Manage requests here and reply from your email inbox. Private notes stay in Head Office and are never emailed to the customer.</p><div class="note">Notification inbox: <b>{{inbox}}</b><br>Email configuration: {{'Ready for live delivery test' if configured else 'Not configured; requests are still saved here'}}. “Accepted” means the provider accepted the notification, not verified inbox delivery or resolution.</div><nav class="actions" aria-label="Support views"><a href="/head-office/support">Active requests</a><a href="/head-office/support?view=archived">Archived requests</a></nav><h2>{{"Archived requests" if archived else "Active requests"}}</h2>{% for t in tickets %}<article class="ticket"><h2>{{t.reference}} · {{topics[t.topic]}}</h2><p class="meta">{{t.created_at}}<br>{{t.name}} · {{t.company or 'No business supplied'}}<br><a href="mailto:{{t.email}}">{{t.email}}</a><br>{{t.device}}{% if t.page_url %} · {{t.page_url}}{% endif %}<br>Email notification: {{"Accepted by email provider" if t.notification_status=="accepted" else t.notification_status}}</p><p><b>Ticket status: {{statuses.get(t.status,t.status)}}</b></p><div class="message">{{t.message}}</div><h3>Private support notes</h3>{% for n in notes.get(t.id,[]) %}<div class="private"><small>{{n.created_at}} · {{n.author}}</small><div class="message">{{n.message}}</div></div>{% else %}<p>No private notes yet.</p>{% endfor %}<form method="post" action="/head-office/support/{{t.id}}/manage"><input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="action" value="update"><label for="status-{{t.id}}">Ticket status</label><select name="status" id="status-{{t.id}}">{% for key,label in statuses.items() %}<option value="{{key}}" {{'selected' if t.status==key else ''}}>{{label}}</option>{% endfor %}</select><label for="note-{{t.id}}">Add private note (optional)</label><textarea name="note" id="note-{{t.id}}" maxlength="4000" placeholder="Record your reply or actions taken. This is not sent to the customer."></textarea><button>Save status / note</button></form><div class="actions"><form method="post" action="/head-office/support/{{t.id}}/manage"><input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="action" value="{{'restore' if t.archived else 'archive'}}"><button>{{'Restore to active requests' if t.archived else 'Archive request'}}</button></form><a class="danger" href="/head-office/support/{{t.id}}/delete">Delete test / spam request</a></div>{% if t.notification_status!='accepted' %}<form method="post" action="/head-office/support/{{t.id}}/notify"><input type="hidden" name="csrf" value="{{csrf}}"><button>Retry notification</button></form>{% endif %}</article>{% else %}<div class="note">No support requests yet.</div>{% endfor %}</main></body></html>'''

def register_support(app,estimate_db,is_head_office):
    def csrf():
        session.setdefault('support_csrf',secrets.token_urlsafe(32));return session['support_csrf']
    @app.get('/api/public/support/config')
    def support_config():
        response=jsonify(csrf=csrf());response.headers['Cache-Control']='no-store';return response
    @app.post('/api/public/support')
    def submit_support():
        if not request.is_json:return jsonify(error='Please send the support form again.'),415
        if (request.content_length or 0)>18000:return jsonify(error='Your message is too long.'),413
        if not hmac.compare_digest(str(request.headers.get('X-CSRF-Token') or ''),str(session.get('support_csrf') or 'missing')):return jsonify(error='Please refresh the support page and try again.'),400
        d=request.get_json(silent=True) or {}
        if not isinstance(d,dict):return jsonify(error='Invalid form.'),400
        limits={'name':120,'company':160,'email':254,'message':6000,'device':20,'page_url':1000,'topic':40}
        values={k:str(d.get(k) or '').strip() for k in limits};values['email']=values['email'].lower()
        if any(len(values[k])>limit for k,limit in limits.items()):return jsonify(error='One or more fields are too long.'),400
        if not values['name'] or len(values['message'])<10 or not email_valid(values['email']) or values['topic'] not in TOPICS or values['device'] not in {'Desktop / laptop','Mobile phone','Tablet','Not sure'}:
            return jsonify(error='Enter your name, a valid email, a support topic, device, and a message of at least 10 characters.'),400
        try:request_id=str(uuid.UUID(str(d.get('request_id') or '')))
        except (ValueError,TypeError):return jsonify(error='Please refresh the support page and try again.'),400
        if values['page_url']:
            try:parsed=urlsplit(values['page_url'])
            except ValueError:return jsonify(error='Use a valid website address.'),400
            if parsed.scheme not in {'http','https'} or not parsed.netloc or parsed.username or parsed.password:return jsonify(error='Use a website address for the optional page link.'),400
            values['page_url']=urlunsplit((parsed.scheme,parsed.netloc,parsed.path,'',''))
        fingerprint=hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest();con=estimate_db()
        try:
            prior=con.execute('SELECT reference,fingerprint FROM support_requests WHERE id=?',(request_id,)).fetchone()
            if prior:
                if prior['fingerprint']!=fingerprint:return jsonify(error='Refresh the support page before sending a different request.'),409
                return jsonify(ok=True,reference=prior['reference'])
            blocked_ip=limited(con,'support-ip:'+str(request.remote_addr),10,3600)
            blocked_email=limited(con,'support-email:'+values['email'],5,3600)
            if blocked_ip or blocked_email:return jsonify(error='Too many support requests. Please try again later.'),429
            reference='AQ-'+uuid.uuid4().hex[:12].upper();created=datetime.utcnow().isoformat()+'Z'
            row=con.execute('INSERT INTO support_requests(id,reference,created_at,name,company,email,topic,message,device,page_url,dealer_id,fingerprint,notification_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING RETURNING reference',(request_id,reference,created,values['name'],values['company'],values['email'],values['topic'],values['message'],values['device'],values['page_url'],str(session.get('dealer_id') or ''),fingerprint,'pending')).fetchone()
            con.commit()
            if not row:
                prior=con.execute('SELECT reference,fingerprint FROM support_requests WHERE id=?',(request_id,)).fetchone()
                if prior['fingerprint']!=fingerprint:return jsonify(error='Refresh the support page before sending a different request.'),409
                return jsonify(ok=True,reference=prior['reference'])
            ticket=dict(values,id=request_id,reference=reference,created_at=created)
            try:state=notify_support(ticket)
            except Exception:
                state='failed';app.logger.error('Support notification failed; the request remains saved in Head Office.')
            con.execute('UPDATE support_requests SET notification_status=? WHERE id=?',(state,request_id));con.commit()
            return jsonify(ok=True,reference=reference),201
        finally:con.close()
    @app.get('/head-office/support')
    def support_admin():
        if not is_head_office():return Response('Head Office permission required.',status=403)
        con=estimate_db()
        archived=request.args.get('view')=='archived';notes={}
        try:
            tickets=[dict(row) for row in con.execute('SELECT * FROM support_requests WHERE archived=? ORDER BY created_at DESC LIMIT 100',(int(archived),)).fetchall()]
            for ticket in tickets:
                notes[ticket['id']]=[dict(row) for row in con.execute('SELECT * FROM support_notes WHERE ticket_id=? ORDER BY created_at,id',(ticket['id'],)).fetchall()]
        finally:con.close()
        response=Response(render_template_string(INBOX_HTML,tickets=tickets,topics=TOPICS,notes=notes,archived=archived,statuses=STATUSES,csrf=csrf(),inbox=support_inbox(),configured=bool(mail_config()) and email_valid(support_inbox())),content_type='text/html');response.headers['Cache-Control']='no-store';return response
    @app.post('/head-office/support/<ticket_id>/notify')
    def support_retry(ticket_id):
        if not is_head_office():return Response('Head Office permission required.',status=403)
        if not hmac.compare_digest(str(request.form.get('csrf') or ''),str(session.get('support_csrf') or 'missing')):return Response('Refresh and try again.',status=400)
        con=estimate_db()
        try:
            row=con.execute('SELECT * FROM support_requests WHERE id=?',(ticket_id,)).fetchone()
            if not row:return Response('Request not found.',status=404)
            if row['notification_status']!='accepted':
                try:state=notify_support(dict(row))
                except Exception:state='failed'
                con.execute('UPDATE support_requests SET notification_status=? WHERE id=?',(state,ticket_id));con.commit()
        finally:con.close()
        from flask import redirect
        return redirect('/head-office/support')

    @app.post('/head-office/support/<ticket_id>/manage')
    def support_manage(ticket_id):
        from flask import redirect
        if not is_head_office():return Response('Head Office permission required.',status=403)
        if not hmac.compare_digest(str(request.form.get('csrf') or ''),str(session.get('support_csrf') or 'missing')):return Response('Refresh and try again.',status=400)
        action=request.form.get('action');status=request.form.get('status');note=str(request.form.get('note') or '').strip()
        if action not in {'update','archive','restore'} or len(note)>4000 or (action=='update' and status not in STATUSES):return Response('Invalid ticket update.',status=400)
        con=estimate_db()
        try:
            row=con.execute('SELECT * FROM support_requests WHERE id=?',(ticket_id,)).fetchone()
            if not row:return Response('Request not found.',status=404)
            if action=='archive' and row['status']!='resolved':return Response('Mark the request Resolved before archiving it. Use Delete for test tickets or spam.',status=400)
            if action=='update':
                con.execute('UPDATE support_requests SET status=? WHERE id=?',(status,ticket_id))
                if note:con.execute('INSERT INTO support_notes(id,ticket_id,created_at,author,message) VALUES(?,?,?,?,?)',(uuid.uuid4().hex,ticket_id,datetime.utcnow().isoformat()+'Z',str(session.get('dealer_email') or session.get('dealer_name') or 'Head Office'),note))
            else:con.execute('UPDATE support_requests SET archived=? WHERE id=?',(int(action=='archive'),ticket_id))
            con.commit()
        finally:con.close()
        return redirect('/head-office/support'+('?view=archived' if action=='archive' or (action=='update' and row['archived']) else ''))
    @app.route('/head-office/support/<ticket_id>/delete',methods=['GET','POST'])
    def support_delete(ticket_id):
        from flask import redirect
        if not is_head_office():return Response('Head Office permission required.',status=403)
        con=estimate_db()
        try:
            row=con.execute('SELECT * FROM support_requests WHERE id=?',(ticket_id,)).fetchone()
            if not row:return Response('Request not found.',status=404)
            if request.method=='POST':
                if not hmac.compare_digest(str(request.form.get('csrf') or ''),str(session.get('support_csrf') or 'missing')):return Response('Refresh and try again.',status=400)
                if request.form.get('reference')!=row['reference']:return Response('Enter the exact ticket reference to confirm deletion.',status=400)
                con.execute('DELETE FROM support_notes WHERE ticket_id=?',(ticket_id,));con.execute('DELETE FROM support_requests WHERE id=?',(ticket_id,));con.commit()
                return redirect('/head-office/support')
            page=render_template_string(DELETE_HTML,ticket=dict(row),csrf=csrf())
            response=Response(page,content_type='text/html');response.headers['Cache-Control']='no-store';return response
        finally:con.close()

DELETE_HTML='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Delete support request</title><style>body{font:16px Arial;max-width:650px;margin:40px auto;padding:20px;line-height:1.6;color:#173b61}input,button{font:inherit;padding:12px;margin:12px 0}button{background:#a12929;color:white;border:0;border-radius:8px}label{display:block}</style></head><body><main><h1>Delete test / spam request</h1><p>This permanently deletes <b>{{ticket.reference}}</b> and its private notes. It does not remove emails already sent. Archive resolved customer requests to keep their history.</p><form method="post"><input type="hidden" name="csrf" value="{{csrf}}"><label for="reference">Type {{ticket.reference}} to confirm deletion</label><input id="reference" name="reference" required autocomplete="off"><br><button>Permanently delete request</button></form><a href="/head-office/support">Cancel — keep request</a></main></body></html>'''
