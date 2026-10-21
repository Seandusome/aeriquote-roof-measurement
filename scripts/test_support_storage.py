import os,sys,tempfile,uuid,re,importlib
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory() as tmp:
 os.environ['DATABASE_URL']='';os.environ['ESTIMATE_DB_PATH']=str(Path(tmp)/'test.db')
 import app as a
 import support_center as support
 import storage_checks as storage
 a.app.config['TESTING']=True
 client=a.app.test_client();csrf=client.get('/api/public/support/config').json['csrf']
 data=dict(request_id=str(uuid.uuid4()),name='<script>alert(1)</script>',email='tester@example.com',company='Test',topic='bug-report',message='The test request is saved before email.',device='Mobile phone',page_url='https://example.com/reset-password?token=SECRET#fragment')
 assert client.post('/api/public/support',json=data).status_code==400
 headers={'X-CSRF-Token':csrf}
 with patch.object(support,'notify_support',side_effect=RuntimeError('mail unavailable')) as notify:
  r=client.post('/api/public/support',json=data,headers=headers);assert r.status_code==201,r.data
  ref=r.json['reference'];assert notify.call_count==1
  assert client.post('/api/public/support',json=data,headers=headers).json['reference']==ref
  assert notify.call_count==1
 con=a.estimate_db();row=con.execute('SELECT * FROM support_requests').fetchone()
 assert row['notification_status']=='failed' and row['page_url']=='https://example.com/reset-password'
 assert 'SECRET' not in str(dict(row));con.close()
 assert client.post('/api/public/support',json=dict(data,request_id=str(uuid.uuid4()),page_url='http://['),headers=headers).status_code==400
 assert client.post('/api/public/support',json=dict(data,message='Changed message'),headers=headers).status_code==409
 from flask import Flask
 admin=Flask(__name__);admin.secret_key='test-only';allowed=[False]
 support.register_support(admin,a.estimate_db,lambda:allowed[0]);storage.register_storage(admin,a.estimate_db,lambda:allowed[0])
 ac=admin.test_client();assert ac.get('/head-office/support').status_code==403
 assert ac.post('/head-office/storage').status_code==403
 allowed[0]=True
 body=ac.get('/head-office/support').get_data(as_text=True)
 assert '<script>alert(1)</script>' not in body and '&lt;script&gt;' in body
 assert ac.post('/head-office/storage').status_code==400
 page=ac.get('/head-office/storage').get_data(as_text=True);token=re.search('name="csrf" value="([^"]+)"',page)[1]
 assert ac.post('/head-office/storage',data={'csrf':token}).status_code==302
 con=a.estimate_db();cp=con.execute('SELECT * FROM storage_checkpoints').fetchone();before=storage.snapshot(con);con.close()
 assert all(v['missing']==0 for v in storage.compare(before,before).values())
 importlib.reload(storage);assert storage.BOOT_ID!=cp['boot_id']
 page=ac.get('/head-office/storage').get_data(as_text=True)
 assert cp['id'] in page and 'different application process' in page
 con=a.estimate_db();con.execute('DELETE FROM support_requests');con.commit();after=storage.snapshot(con);con.close()
 assert storage.compare(before,after)['support_requests']['missing']==1
 print('PASS support validation, CSRF, idempotency, saved email failures, URL redaction, escaped admin inbox, protected checkpoint/restart/missing detection')
 # Verify recipient, reply-to and provider idempotency without sending mail.
 with patch.object(support,'mail_config',return_value=('fake-secret','AeriQuote <accounts@aeriquote.com>','https://example.com')):
  with patch.object(support.urllib.request,'urlopen') as send:
   send.return_value.__enter__.return_value.status=200
   ticket=dict(data,id=data['request_id'],reference=ref)
   assert support.notify_support(ticket)=='accepted'
   req=send.call_args.args[0]
   import json
   payload=json.loads(req.data)
   assert payload['to']==['sean@aeriquote.com'] and payload['reply_to']=='tester@example.com'
   assert req.get_header('Idempotency-key')=='support-'+data['request_id']
 print('PASS mocked Resend recipient, Reply-To and idempotency header; no external email sent')
