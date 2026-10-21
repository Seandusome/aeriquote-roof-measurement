"""Signed inbound mail, correct routing, reopens and safe retries."""
import os,sys,tempfile,json,time,uuid,hmac,hashlib,base64
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory() as tmp:
 os.environ['DATABASE_URL']='';os.environ['ESTIMATE_DB_PATH']=str(Path(tmp)/'incoming.db')
 import app as a
 import support_center as s
 import support_inbound as incoming
 # Published Svix test vector verifies our implementation independently.
 assert incoming.valid_signature(b'{"event_type":"ping","data":{"success":true}}',{'svix-id':'msg_loFOjxBNrRLzqYUf','svix-timestamp':'1731705121','svix-signature':'v1,rAvfW3dJ/X/qxhsaXPOyyCGmRKsaKWcsNccKXlIktD0='},'whsec_plJ3nmyCDGBKInavdOK15jsl',now=1731705121)
 client=a.app.test_client();url='/api/public/support/inbound'
 assert client.post(url).status_code==503,'Public webhook must bypass login and fail closed if unconfigured'
 key=b'0123456789abcdef0123456789abcdef'
 os.environ['RESEND_WEBHOOK_SECRET']='whsec_'+base64.b64encode(key).decode()
 os.environ['SUPPORT_REPLY_DOMAIN']='test.resend.app';os.environ['RESEND_API_KEY']='fake-test-key'
 tid=str(uuid.uuid4());csrf=client.get('/api/public/support/config').json['csrf']
 fields=dict(request_id=tid,name='Customer',email='customer@example.com',company='',topic='bug-report',device='Tablet',page_url='',message='Please help with this test.')
 with patch.object(s,'notify_support',return_value='accepted'):assert client.post('/api/public/support',json=fields,headers={'X-CSRF-Token':csrf}).status_code==201
 con=a.estimate_db();address=incoming.reply_address(con,tid)
 assert address.endswith('@test.resend.app') and address==incoming.reply_address(con,tid)
 con.execute("UPDATE support_requests SET status='resolved',archived=1 WHERE id=?",(tid,));con.commit();con.close()
 eid=str(uuid.uuid4());email={'id':eid,'from':'Customer <customer@example.com>','to':[address],'subject':'Re: support','html':'<p>Customer <b>response</b></p><script>BAD</script>','text':None,'headers':{},'authentication':{'dmarc':'pass'},'attachments':[{'filename':'photo.jpg'}]}
 def signed(eid,stamp=None,kind='email.received'):
  raw=json.dumps({'type':kind,'data':{'email_id':eid}}).encode();stamp=str(stamp or int(time.time()));event_id='msg_test'
  sig=base64.b64encode(hmac.new(key,event_id.encode()+b'.'+stamp.encode()+b'.'+raw,hashlib.sha256).digest()).decode()
  return raw,{'svix-id':event_id,'svix-timestamp':stamp,'svix-signature':'v1,'+sig}
 raw,headers=signed(eid)
 with patch.object(incoming,'retrieve_email',return_value=email) as fetch, patch.object(s,'notify_support',return_value='accepted') as notify:
  assert client.post(url,data=raw+b' ',headers=headers).status_code==400
  old,oldheaders=signed(eid,int(time.time())-600);assert client.post(url,data=old,headers=oldheaders).status_code==400
  assert fetch.call_count==0
  assert client.post(url,data=raw,headers=headers).json['match']=='matched'
  assert client.post(url,data=raw,headers=headers).json['duplicate']
  assert fetch.call_count==1 and notify.call_count==1
  assert notify.call_args.args[0]['message'].startswith('Customer reply:')
 con=a.estimate_db();ticket=con.execute('SELECT * FROM support_requests').fetchone();row=con.execute('SELECT * FROM support_incoming').fetchone()
 assert ticket['status']=='open' and ticket['archived']==0 and row['attachment_count']==1 and row['notification_status']=='accepted'
 assert 'response' in row['message'] and 'BAD' not in row['message'] and '<b>' not in row['message']
 # Wrong sender is retained separately and cannot reopen a ticket.
 for overrides in [{'from':'attacker@example.com'},{'to':['unknown@test.resend.app']},{'authentication':{'dmarc':'fail'}}]:
  other=str(uuid.uuid4());content=dict(email,**overrides,id=other);raw,headers=signed(other)
  con.execute("UPDATE support_requests SET status='resolved',archived=1 WHERE id=?",(tid,));con.commit()
  with patch.object(incoming,'retrieve_email',return_value=content):assert client.post(url,data=raw,headers=headers).json['match']=='unmatched'
  assert con.execute('SELECT status FROM support_requests').fetchone()['status']=='resolved'
 auto=str(uuid.uuid4());raw,headers=signed(auto)
 with patch.object(incoming,'retrieve_email',return_value=dict(email,id=auto,headers={'auto-submitted':'auto-replied'})):assert client.post(url,data=raw,headers=headers).json['match']=='automated'
 assert con.execute('SELECT status FROM support_requests').fetchone()['status']=='resolved'
 failed=str(uuid.uuid4());raw,headers=signed(failed)
 with patch.object(incoming,'retrieve_email',side_effect=RuntimeError('timeout')):assert client.post(url,data=raw,headers=headers).status_code==503
 assert not con.execute('SELECT id FROM support_incoming WHERE id=?',(failed,)).fetchone()
 con.close()
 # Admin UI shows incoming messages/unmatched mail with escaped text.
 from flask import Flask
 admin=Flask(__name__);admin.secret_key='test';s.register_support(admin,a.estimate_db,lambda:True)
 body=admin.test_client().get('/head-office/support?view=archived').get_data(as_text=True)
 assert 'Conversation' in body and 'Unmatched incoming emails' in body and 'response' in body
 # Outgoing replies use a ticket-specific address only when enabled.
 with patch.object(s,'mail_config',return_value=('fake','AeriQuote <accounts@aeriquote.com>','https://example.com')):
  with patch.object(s.urllib.request,'urlopen') as transport:
   transport.return_value.__enter__.return_value.status=200
   s.send_support_reply({'reference':'AQ-TEST','reply_to_address':address},{'recipient':'customer@example.com','message':'Hello','id':str(uuid.uuid4())})
   assert json.loads(transport.call_args.args[0].data)['reply_to']==address
 # Production recipient override does not change the default test inbox.
 with patch.dict(os.environ,{'SUPPORT_INBOX':'Nancy@aeriquote.com'}):
  with patch.object(s,'mail_config',return_value=('fake','AeriQuote <accounts@aeriquote.com>','https://example.com')):
   with patch.object(s.urllib.request,'urlopen') as transport:
    transport.return_value.__enter__.return_value.status=200
    s.notify_support(dict(fields,id='incoming-test',reference='AQ-TEST',message='Customer reply: example'))
    assert json.loads(transport.call_args.args[0].data)['to']==['Nancy@aeriquote.com']
 print('PASS official signature vector, raw/timestamp verification, public fail-closed webhook, stable reply routes, matching/reopening, duplicates, HTML-to-text, attachments notice, sender/auth quarantine, autoreply handling, retrieval retry and outbound Reply-To; no live mail')
