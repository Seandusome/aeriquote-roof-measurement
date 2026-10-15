"""Customer email replies stay separate from collapsed internal notes."""
import os,sys,tempfile,uuid,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory() as tmp:
 os.environ['DATABASE_URL']='';os.environ['ESTIMATE_DB_PATH']=str(Path(tmp)/'reply.db')
 import app as a
 import support_center as s
 from flask import Flask
 app=Flask(__name__);app.secret_key='testing';allowed=[True]
 s.register_support(app,a.estimate_db,lambda:allowed[0]);c=app.test_client()
 token=c.get('/api/public/support/config').json['csrf'];ticket_id=str(uuid.uuid4());reply_id=str(uuid.uuid4())
 d=dict(request_id=ticket_id,name='Tester',email='customer@example.com',company='',topic='billing',device='Tablet',page_url='',message='Please help with my account.')
 with patch.object(s,'notify_support',return_value='accepted'):assert c.post('/api/public/support',json=d,headers={'X-CSRF-Token':token}).status_code==201
 manage='/head-office/support/'+ticket_id+'/manage';url='/head-office/support/'+ticket_id+'/reply'
 assert c.post(manage,data=dict(csrf=token,action='note',note='PRIVATE: do not email')).status_code==302
 html=c.get('/head-office/support').get_data(as_text=True)
 assert html.index('Reply to customer')<html.index('Internal notes (')
 assert '<details style="margin:22px 0"><summary' in html and '<details open' not in html
 assert 'To: ' not in html and 'Email to <b>customer@example.com</b>' in html
 fields=dict(csrf=token,reply_id=reply_id,message='Hello, your setup is ready. <script>literal text</script>')
 assert c.post(url,data=dict(fields,csrf='bad')).status_code==400
 allowed[0]=False;assert c.post(url,data=fields).status_code==403;allowed[0]=True
 with patch.object(s,'send_support_reply',side_effect=RuntimeError('timeout')) as send:
  response=c.post(url,data=fields);assert response.status_code==302 and 'reply_result=failed' in response.location
  assert send.call_count==1
 con=a.estimate_db();row=con.execute('SELECT * FROM support_replies').fetchone();con.close()
 assert row['message']==fields['message'] and row['recipient']=='customer@example.com' and row['delivery_status']=='failed'
 html=c.get('/head-office/support?reply_result=failed').get_data(as_text=True)
 assert 'Retry this email' in html and '&lt;script&gt;literal text&lt;/script&gt;' in html
 with patch.object(s,'send_support_reply',return_value='accepted') as send:
  assert c.post(url,data=dict(csrf=token,reply_id=reply_id,mode='retry')).status_code==302
  assert c.post(url,data=fields).status_code==302
  assert send.call_count==1,'Accepted reply must not be sent again'
  assert c.post(url,data=dict(fields,message='different message')).status_code==409
 con=a.estimate_db();ticket=dict(con.execute('SELECT * FROM support_requests').fetchone());row=dict(con.execute('SELECT * FROM support_replies').fetchone());con.close()
 with patch.object(s,'mail_config',return_value=('fake-key','AeriQuote <accounts@aeriquote.com>','https://example.com')):
  with patch.object(s.urllib.request,'urlopen') as transport:
   transport.return_value.__enter__.return_value.status=200
   assert s.send_support_reply(ticket,row)=='accepted'
   req=transport.call_args.args[0];payload=json.loads(req.data)
   assert payload['to']==['customer@example.com'] and payload['reply_to']=='sean@aeriquote.com'
   assert 'PRIVATE' not in payload['text'] and ticket['reference'] in payload['subject']
   assert req.get_header('Idempotency-key')=='support-reply-'+reply_id
 with patch.object(s,'mail_config',return_value=None):assert s.send_support_reply(ticket,row)=='not_configured'
 assert c.post('/head-office/support/'+ticket_id+'/delete',data=dict(csrf=token,reference=ticket['reference'])).status_code==302
 con=a.estimate_db();assert con.execute('SELECT COUNT(*) AS total FROM support_replies').fetchone()['total']==0;con.close()
 print('PASS collapsed private notes, customer reply recipient, CSRF/access, saved failures/retry, duplicate suppression, escaped history, mocked email isolation and deletion cleanup; no live email sent')
