"""Small web support inbox. Requests are saved before optional email notification."""
import hashlib,hmac,json,os,re,secrets,time,uuid
import urllib.request
from datetime import datetime
from urllib.parse import urlsplit,urlunsplit
from flask import request,session,jsonify,Response,render_template_string
from account_recovery import limited,mail_config
from support_inbound import init_inbound_db,register_inbound,reply_address,inbound_ready,deliver_notification

TOPICS={'getting-started':'Getting Started','account-login':'Account & Login','measurement-pdf':'Measurement & PDF Help','bug-report':'Report a Bug','billing':'Billing & Subscription','feature-request':'Feature Request','other':'Other / Privacy'}
STATUSES={'open':'Open','in-progress':'In Progress','resolved':'Resolved'}
DEFAULT_SUPPORT_INBOX='sean@aeriquote.com'  # Explicitly selected by Sean on October15.

def init_support_db(con):
    init_inbound_db(con)
    con.execute('CREATE TABLE IF NOT EXISTS support_requests (id TEXT PRIMARY KEY, reference TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, name TEXT NOT NULL, company TEXT NOT NULL, email TEXT NOT NULL, topic TEXT NOT NULL, message TEXT NOT NULL, device TEXT NOT NULL, page_url TEXT NOT NULL, dealer_id TEXT, fingerprint TEXT NOT NULL, notification_status TEXT NOT NULL)')

    columns={'status':"TEXT NOT NULL DEFAULT 'open'",'archived':"INTEGER NOT NULL DEFAULT 0"}
    if con.postgres:
        for name,definition in columns.items():con.execute('ALTER TABLE support_requests ADD COLUMN IF NOT EXISTS '+name+' '+definition)
    else:
        existing={r['name'] for r in con.execute('PRAGMA table_info(support_requests)').fetchall()}
        for name,definition in columns.items():
            if name not in existing:con.execute('ALTER TABLE support_requests ADD COLUMN '+name+' '+definition)
    con.execute('CREATE TABLE IF NOT EXISTS support_replies (id TEXT PRIMARY KEY, ticket_id TEXT NOT NULL, created_at TEXT NOT NULL, author TEXT NOT NULL, recipient TEXT NOT NULL, message TEXT NOT NULL, delivery_status TEXT NOT NULL)')
    con.execute('CREATE INDEX IF NOT EXISTS idx_support_replies_ticket ON support_replies(ticket_id)')
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

INBOX_HTML='''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AeriQuote Support Inbox</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f4f8fc;font:16px system-ui,Arial;color:#173b61;line-height:1.5}.wrap{max-width:1000px;margin:28px auto;padding:0 18px}a{color:#0757a6}h1{margin-bottom:8px}h2{font-size:20px;margin:0 0 8px}h3{font-size:17px;margin:0 0 10px}.muted,.meta{font-size:14px;color:#465d75}.ticket,.notice{background:white;border:1px solid #dce5ef;border-radius:14px;margin:20px 0;padding:24px}.notice{background:#edf5ff;padding:16px}.ticket-head{display:flex;justify-content:space-between;align-items:start;gap:20px;flex-wrap:wrap;border-bottom:1px solid #e1e8f1;padding-bottom:18px}.status-form{display:flex;align-items:end;gap:8px;flex-wrap:wrap}.status-form label{display:block;font-size:13px;font-weight:700}.message{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.6}.conversation{padding:22px 0}.entry{background:#f2f6fc;border:1px solid #e0e9f2;border-radius:10px;padding:16px;margin:12px 0}.entry.outgoing{background:#edf7ff;border-left:4px solid #1264ac}.entry header{font-size:14px;margin-bottom:10px;display:flex;gap:8px;flex-wrap:wrap;justify-content:space-between}.entry time{font-size:12px;color:#465d75}.delivery{font-size:13px;margin-top:10px;color:#465d75}.delivery summary{font-size:13px}.compose{border-top:1px solid #e1e8f1;padding-top:20px}textarea,select,input{font:inherit;padding:10px;max-width:100%;border:1px solid #bccddb;border-radius:8px}textarea{width:100%;min-height:110px;margin:8px 0}button{font:inherit;padding:10px 15px;border:1px solid #b8c9da;border-radius:8px;background:#f6f9fc;color:#173b61;cursor:pointer;min-height:44px}.primary{background:#125da8;color:white;border-color:#125da8;font-weight:700}.secondary-details{border-top:1px solid #e1e8f1;margin-top:20px;padding-top:14px}.secondary-details>summary{font-size:14px;color:#465d75;cursor:pointer}.secondary-details form{margin-top:12px}.actions,.views{display:flex;flex-wrap:wrap;gap:14px;align-items:center;margin:15px 0}.danger{color:#a12929}.private{background:#f6f7f9;padding:14px;margin:10px 0;border-radius:8px}.view-current{font-weight:700}textarea:focus-visible,select:focus-visible,a:focus-visible,button:focus-visible,summary:focus-visible{outline:3px solid #1264ac;outline-offset:3px}@media(max-width:600px){.ticket{padding:16px}.wrap{padding:0 12px}.status-form{width:100%}.entry{padding:12px}}
</style></head><body><main class="wrap">
<a href="/head-office/dealers">← Admin Dashboard</a><h1>Support requests</h1>
{% if result %}<p role="status" class="notice">{{result}}</p>{% endif %}
<div class="notice"><b>Support email: {{inbox}}</b><br>{% if not configured %}Outgoing email is not configured. Requests are still saved here.{% elif not inbound %}You can send replies below. Incoming replies are not connected yet; check {{inbox}} for customer responses.{% else %}Incoming replies are configured. Complete a live reply test to verify that they appear here.{% endif %}</div>
<nav class="views" aria-label="Support views"><a href="/head-office/support" {{'aria-current=page class=view-current' if not archived else ''}}>Active requests</a><a href="/head-office/support?view=archived" {{'aria-current=page class=view-current' if archived else ''}}>Archived requests</a></nav>
{% for t in tickets %}
<article class="ticket" id="{{t.id}}"><div class="ticket-head"><div><h2>{{t.reference}} · {{topics[t.topic]}}</h2><div>{{t.name}}{% if t.company %} · {{t.company}}{% endif %}</div><a href="mailto:{{t.email}}">{{t.email}}</a></div>
<form class="status-form" method="post" action="/head-office/support/{{t.id}}/manage"><input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="action" value="update"><div><label for="status-{{t.id}}">Status</label><select name="status" id="status-{{t.id}}">{% for key,label in statuses.items() %}<option value="{{key}}" {{'selected' if t.status==key else ''}}>{{label}}</option>{% endfor %}</select></div><button>Save status</button></form></div>
<section class="conversation" aria-label="Conversation"><h3>Conversation</h3>
{% for m in conversations[t.id] %}<div class="entry {{'outgoing' if m.kind=='outgoing' else 'customer'}}"><header><b>{{m.label}}</b><time>{{m.created_at}}</time></header><div class="message">{{m.message}}</div>
{% if m.kind=='outgoing' %}
{% if m.delivery_status=='accepted' %}<details class="delivery"><summary>Email details</summary><p>{{reply_states[m.delivery_status]}}<br>To: {{m.recipient}}</p></details>{% else %}<p class="delivery">{{reply_states.get(m.delivery_status,m.delivery_status)}}</p><form method="post" action="/head-office/support/{{t.id}}/reply"><input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="reply_id" value="{{m.id}}"><input type="hidden" name="mode" value="retry"><button>Retry this email</button></form>{% endif %}
{% elif m.kind=='incoming' %}{% if m.attachment_count %}<p class="meta">{{m.attachment_count}} attachment(s) — view in Resend; files are not imported.</p>{% endif %}{% if m.match_status=='matched' and m.notification_status!='accepted' %}<details class="delivery"><summary>Team notification needs attention</summary><p>{{m.notification_status}}</p><form method="post" action="/head-office/support/incoming/{{m.id}}/notify"><input type="hidden" name="csrf" value="{{csrf}}"><button>Retry team notification</button></form></details>{% endif %}{% endif %}</div>{% endfor %}</section>
<section class="compose" aria-labelledby="reply-title-{{t.id}}"><h3 id="reply-title-{{t.id}}">Reply to customer</h3><p class="meta">Email to <b>{{t.email}}</b></p><form method="post" action="/head-office/support/{{t.id}}/reply"><input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="reply_id" value="{{reply_ids[t.id]}}"><label for="reply-{{t.id}}">Your reply</label><textarea id="reply-{{t.id}}" name="message" required maxlength="6000" placeholder="Write your reply to the customer…"></textarea><button class="primary">Send reply</button></form></section>
<details class="secondary-details internal-notes"><summary>Internal notes ({{notes.get(t.id,[])|length}}) — private</summary>{% for n in notes.get(t.id,[]) %}<div class="private"><small>{{n.created_at}} · {{n.author}}</small><div class="message">{{n.message}}</div></div>{% endfor %}<form method="post" action="/head-office/support/{{t.id}}/manage"><input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="action" value="note"><label for="note-{{t.id}}">Add internal note</label><textarea name="note" id="note-{{t.id}}" maxlength="4000" required placeholder="Internal only. Never emailed to the customer."></textarea><button>Save private note</button></form></details>
<details class="secondary-details more-actions"><summary>More actions</summary><div class="actions"><form method="post" action="/head-office/support/{{t.id}}/manage"><input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="action" value="{{'restore' if t.archived else 'archive'}}"><button>{{'Restore to active requests' if t.archived else 'Archive resolved request'}}</button></form><a class="danger" href="/head-office/support/{{t.id}}/delete">Delete test / spam request</a></div><p class="meta">{{t.device}}{% if t.page_url %} · {{t.page_url}}{% endif %}<br>Email notification: {{"Accepted by email provider" if t.notification_status=="accepted" else t.notification_status}}. This does not indicate ticket resolution or confirmed inbox delivery.</p>{% if t.notification_status!='accepted' %}<form method="post" action="/head-office/support/{{t.id}}/notify"><input type="hidden" name="csrf" value="{{csrf}}"><button>Retry notification</button></form>{% endif %}</details>
</article>{% else %}<div class="notice">No {{'archived' if archived else 'active'}} support requests.</div>{% endfor %}
{% if unmatched %}<details class="secondary-details"><summary>Unmatched incoming emails ({{unmatched|length}})</summary><p>These could not be safely matched to a customer ticket. Review them in Resend; they have not reopened a ticket.</p>{% for m in unmatched %}<div class="ticket"><small>{{m.received_at}} · {{m.sender}}</small><h3>{{m.subject}}</h3><div class="message">{{m.message}}</div></div>{% endfor %}</details>{% endif %}
</main></body></html>'''

def register_support(app,estimate_db,is_head_office):
    notify_incoming=lambda ticket,incoming:notify_support(dict(ticket,id="incoming-"+incoming["id"],message="Customer reply:\n"+incoming["message"]))
    register_inbound(app,estimate_db,notify_incoming)
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
        archived=request.args.get('view')=='archived';notes={};replies={};incoming={};conversations={}
        try:
            tickets=[dict(row) for row in con.execute('SELECT * FROM support_requests WHERE archived=? ORDER BY created_at DESC LIMIT 100',(int(archived),)).fetchall()]
            unmatched=[dict(row) for row in con.execute("SELECT * FROM support_incoming WHERE ticket_id IS NULL ORDER BY received_at DESC LIMIT 25").fetchall()]
            for ticket in tickets:
                incoming[ticket['id']]=[dict(row) for row in con.execute('SELECT * FROM support_incoming WHERE ticket_id=? ORDER BY received_at,id',(ticket['id'],)).fetchall()]
                replies[ticket['id']]=[dict(row) for row in con.execute('SELECT * FROM support_replies WHERE ticket_id=? ORDER BY created_at,id',(ticket['id'],)).fetchall()]
                notes[ticket['id']]=[dict(row) for row in con.execute('SELECT * FROM support_notes WHERE ticket_id=? ORDER BY created_at,id',(ticket['id'],)).fetchall()]
            for ticket in tickets:
                messages=[dict(kind='original',label='Customer · original request',created_at=ticket['created_at'],message=ticket['message'])]
                messages += [dict(row,kind='incoming',label='Automatic email' if row['match_status']=='automated' else 'Customer reply',created_at=row['received_at']) for row in incoming[ticket['id']]]
                messages += [dict(row,kind='outgoing',label='AeriQuote support · '+row['author']) for row in replies[ticket['id']]]
                conversations[ticket['id']]=sorted(messages,key=lambda m:(m['created_at'],m.get('id','')))
        finally:con.close()
        response=Response(render_template_string(INBOX_HTML,tickets=tickets,topics=TOPICS,conversations=conversations,incoming=incoming,unmatched=unmatched,inbound=inbound_ready(),notes=notes,replies=replies,reply_ids={t["id"]:str(uuid.uuid4()) for t in tickets},reply_states=REPLY_STATES,result=REPLY_RESULTS.get(request.args.get("reply_result")),archived=archived,statuses=STATUSES,csrf=csrf(),inbox=support_inbox(),configured=bool(mail_config()) and email_valid(support_inbox())),content_type='text/html');response.headers['Cache-Control']='no-store';return response
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
        if action not in {'update','note','archive','restore'} or len(note)>4000 or (action=='update' and status not in STATUSES):return Response('Invalid ticket update.',status=400)
        con=estimate_db()
        try:
            row=con.execute('SELECT * FROM support_requests WHERE id=?',(ticket_id,)).fetchone()
            if not row:return Response('Request not found.',status=404)
            if action=='archive' and row['status']!='resolved':return Response('Mark the request Resolved before archiving it. Use Delete for test tickets or spam.',status=400)
            if action=='note' and not note:return Response('Enter an internal note.',status=400)
            if action in {'update','note'}:
                if action=='update':con.execute('UPDATE support_requests SET status=? WHERE id=?',(status,ticket_id))
                if note:con.execute('INSERT INTO support_notes(id,ticket_id,created_at,author,message) VALUES(?,?,?,?,?)',(uuid.uuid4().hex,ticket_id,datetime.utcnow().isoformat()+'Z',str(session.get('dealer_email') or session.get('dealer_name') or 'Head Office'),note))
            else:con.execute('UPDATE support_requests SET archived=? WHERE id=?',(int(action=='archive'),ticket_id))
            con.commit()
        finally:con.close()
        return redirect('/head-office/support'+('?view=archived' if action=='archive' or (action in {'update','note'} and row['archived']) else ''))
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
                con.execute('DELETE FROM support_incoming WHERE ticket_id=?',(ticket_id,));con.execute('DELETE FROM support_reply_routes WHERE ticket_id=?',(ticket_id,));con.execute('DELETE FROM support_replies WHERE ticket_id=?',(ticket_id,));con.execute('DELETE FROM support_notes WHERE ticket_id=?',(ticket_id,));con.execute('DELETE FROM support_requests WHERE id=?',(ticket_id,));con.commit()
                return redirect('/head-office/support')
            page=render_template_string(DELETE_HTML,ticket=dict(row),csrf=csrf())
            response=Response(page,content_type='text/html');response.headers['Cache-Control']='no-store';return response
        finally:con.close()

    @app.post('/head-office/support/incoming/<email_id>/notify')
    def retry_incoming_notification(email_id):
        from flask import redirect
        if not is_head_office():return Response('Head Office permission required.',status=403)
        if not hmac.compare_digest(str(request.form.get('csrf') or ''),str(session.get('support_csrf') or 'missing')):return Response('Refresh and try again.',status=400)
        con=estimate_db()
        try:deliver_notification(con,email_id,notify_incoming,app)
        finally:con.close()
        return redirect('/head-office/support')

    @app.post('/head-office/support/<ticket_id>/reply')
    def support_reply(ticket_id):
        from flask import redirect
        if not is_head_office():return Response('Head Office permission required.',status=403)
        if not hmac.compare_digest(str(request.form.get('csrf') or ''),str(session.get('support_csrf') or 'missing')):return Response('Refresh and try again.',status=400)
        try:reply_id=str(uuid.UUID(str(request.form.get('reply_id') or '')))
        except ValueError:return Response('Refresh and try again.',status=400)
        message=str(request.form.get('message') or '').strip();retry=request.form.get('mode')=='retry'
        if not retry and not 1<=len(message)<=6000:return Response('Enter a reply of 1 to 6000 characters.',status=400)
        con=estimate_db()
        try:
            ticket=con.execute('SELECT * FROM support_requests WHERE id=?',(ticket_id,)).fetchone()
            if not ticket:return Response('Request not found.',status=404)
            prior=con.execute('SELECT * FROM support_replies WHERE id=?',(reply_id,)).fetchone()
            if prior and (prior['ticket_id']!=ticket_id or (not retry and prior['message']!=message)):return Response('Refresh before composing a different reply.',status=409)
            if retry and not prior:return Response('Reply not found.',status=404)
            if prior and prior['delivery_status']=='accepted':return redirect('/head-office/support?reply_result=accepted')
            if not prior:
                if limited(con,'support-reply:'+str(session.get('dealer_id') or request.remote_addr),30,3600):return Response('Too many replies. Please try again later.',status=429)
                con.execute('INSERT INTO support_replies(id,ticket_id,created_at,author,recipient,message,delivery_status) VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING',(reply_id,ticket_id,datetime.utcnow().isoformat()+'Z',str(session.get('dealer_email') or session.get('dealer_name') or 'Head Office'),ticket['email'],message,'pending'))
                con.commit()
            reply=con.execute('SELECT * FROM support_replies WHERE id=?',(reply_id,)).fetchone()
            if reply['ticket_id']!=ticket_id or (not retry and reply['message']!=message):return Response('Refresh before composing a different reply.',status=409)
            try:
                outgoing=dict(ticket);outgoing['reply_to_address']=reply_address(con,ticket_id)
                state=send_support_reply(outgoing,dict(reply))
            except Exception:
                state='failed';app.logger.error('Support reply could not be confirmed; its text remains saved for retry.')
            con.execute('UPDATE support_replies SET delivery_status=? WHERE id=?',(state,reply_id));con.commit()
        finally:con.close()
        return redirect('/head-office/support?reply_result='+state+('#'+ticket_id))

DELETE_HTML='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Delete support request</title><style>body{font:16px Arial;max-width:650px;margin:40px auto;padding:20px;line-height:1.6;color:#173b61}input,button{font:inherit;padding:12px;margin:12px 0}button{background:#a12929;color:white;border:0;border-radius:8px}label{display:block}</style></head><body><main><h1>Delete test / spam request</h1><p>This permanently deletes <b>{{ticket.reference}}</b> and its saved replies and private notes. It does not remove emails already sent. Archive resolved customer requests to keep their history.</p><form method="post"><input type="hidden" name="csrf" value="{{csrf}}"><label for="reference">Type {{ticket.reference}} to confirm deletion</label><input id="reference" name="reference" required autocomplete="off"><br><button>Permanently delete request</button></form><a href="/head-office/support">Cancel — keep request</a></main></body></html>'''

REPLY_STATES={'accepted':'Accepted by email provider — inbox delivery not confirmed','pending':'Saved — sending not yet confirmed','failed':'Sending not confirmed — use Retry this email','not_configured':'Saved — email configuration is missing'}
REPLY_RESULTS={'accepted':'Reply accepted by the email provider. A copy is saved below; inbox delivery is not confirmed.','failed':'Sending could not be confirmed. Your reply is saved below; use Retry this email.','not_configured':'Reply saved, but email is not configured. Configure email and retry.'}

def send_support_reply(ticket,reply):
    config=mail_config();inbox=support_inbox()
    if not config or not email_valid(inbox):return 'not_configured'
    if not email_valid(reply['recipient']):raise ValueError('Invalid reply recipient')
    key,sender,_=config
    payload={'from':sender,'to':[reply['recipient']],'reply_to':ticket.get('reply_to_address') or inbox,'subject':'Re: AeriQuote support '+ticket['reference'],'text':reply['message']+'\n\nAeriQuote Support\nReference: '+ticket['reference']+'\nReply to this email if you need more help.'}
    req=urllib.request.Request('https://api.resend.com/emails',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','Idempotency-Key':'support-reply-'+reply['id'],'User-Agent':'AeriQuote'},method='POST')
    with urllib.request.urlopen(req,timeout=12) as response:
        if not 200<=response.status<300:raise RuntimeError('Reply rejected')
    return 'accepted'
