"""Real isolated profiles: invalid writes preserve branding; owner/employee/device isolation."""
import os,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory() as tmp:
 os.environ['DATABASE_URL']='';os.environ['ESTIMATE_DB_PATH']=tmp+'/qa.db'
 import app as a
 con=a.estimate_db()
 for did in ['profile-a','profile-b']:
  con.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,status,created_at) VALUES(?,?,?,'unused','active','2026-10-22')",(did,'QA ONLY',did+'@example.invalid'))
 con.execute("INSERT INTO dealer_employees(id,dealer_id,employee_name,email,password_hash,status,created_at) VALUES('profile-employee','profile-a','QA ONLY','profile-employee@example.invalid','unused','active','2026-10-22')");con.commit();con.close()
 def client(did='profile-a',employee=False):
  c=a.app.test_client()
  with c.session_transaction() as s:
   s.update(dealer_id=did,account_type='employee' if employee else 'owner',auth_version=0)
   if employee:s['employee_id']='profile-employee'
  return c
 c=client();profile={'company':'QA Persistent Brand','email':'owner+quotes@example.com','logoData':'data:image/png;base64,QAONLY','gst':'5','pst':'6','marketingHeading':'QA marketing'}
 assert c.post('/api/account/profile',json=profile).status_code==200
 before=c.get('/api/account/profile').json['profile']
 for email in ['',None,[],{},42,'bad','a@b','a b@example.com','a..b@example.com','.a@example.com','a.@example.com','a@-bad.com','a@bad-.com','a@example..com','Name <a@example.com>','a@example.com\nBcc:x@example.com','a'*65+'@example.com']:
  response=c.post('/api/account/profile',json={'email':email,'company':'SHOULD NOT SAVE','logoData':''});assert response.status_code==400,(email,response.json)
  assert c.get('/api/account/profile').json['profile']==before
 assert client().get('/api/account/profile').json['profile']==before,'Independent authorized browser session'
 employee=client(employee=True);assert employee.get('/api/account/profile').json['profile']==before
 assert employee.post('/api/account/profile',json={'email':'valid@example.com','logoData':''}).status_code==403
 assert client('profile-b').get('/api/account/profile').json['profile']=={}
 assert c.post('/api/account/profile',json={'email':'  Billing+Quotes@Example.COM  '}).status_code==200
 assert c.get('/api/account/profile').json['profile']['email']=='Billing+Quotes@Example.COM'
 assert c.post('/api/account/profile',json={'logoData':''}).status_code==200
 assert client().get('/api/account/profile').json['profile']['logoData']==''
 assert a.app.test_client().get('/api/account/profile').status_code==401
 print('PASS invalid/blank/header-injected dealer emails rejected before all writes, valid plus address trimmed, profile/logo/taxes/marketing survive independent sessions and employees, employee write denied, business isolation, explicit logo removal')
