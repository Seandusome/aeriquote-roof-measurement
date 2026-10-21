"""Real Flask QA-only account grants, isolation, monthly rollover and quota enforcement."""
import os,sys,tempfile,uuid
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory() as tmp:
 os.environ['DATABASE_URL']='';os.environ['ESTIMATE_DB_PATH']=str(Path(tmp)/'credits.db')
 import app as a
 from account_credits import consume,month_key,settings,lock_account
 a.is_recovery_test_service=lambda:False
 con=a.estimate_db()
 for did,name in [('office','Head Office'),('dealer','QA TEST Credits'),('other','QA TEST Other')]:
  con.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,status,lookup_limit,estimate_limit,created_at,plan_code) VALUES(?,?,?,'unused','active',1,1,'2026-10-19','basic')",(did,name,did+'@example.invalid'))
 con.execute("INSERT INTO dealer_employees(id,dealer_id,employee_name,email,password_hash,status,created_at) VALUES('employee','dealer','QA TEST employee','employee@example.invalid','unused','active','2026-10-19')")
 con.execute("INSERT INTO account_admin_roles(dealer_id) VALUES('office')")
 con.commit();con.close()
 def client(did,eid=None):
  c=a.app.test_client()
  with c.session_transaction() as s:
   s.update(dealer_id=did,account_type='employee' if eid else 'owner',auth_version=a.login_auth_version('employee' if eid else 'owner',eid or did))
   if eid:s['employee_id']=eid
  return c
 office=client('office');owner=client('dealer');employee=client('dealer','employee');other=client('other')
 for c in [owner,employee,other]:
  assert c.get('/head-office/credits').status_code==403
  assert c.post('/head-office/credits',data={}).status_code==403
 # Account display names must never grant Head Office privileges.
 assert other.post('/api/account/profile',json={'name':'Head Office'}).status_code==200
 assert other.get('/head-office/dealers').status_code==403
 assert other.get('/head-office/credits').status_code==403
 assert other.post('/api/account/profile',json={'name':'QA TEST Other'}).status_code==200
 first=office.get('/head-office/credits')
 assert first.status_code==200 and b'<section class="account">' not in first.data
 result=office.get('/head-office/credits?q=dealer%40example.invalid')
 assert b'<section class="account">' in result.data and b'QA TEST Other</h2>' not in result.data
 assert b'<section class="account">' not in office.get('/head-office/credits?q=does-not-exist').data
 with office.session_transaction() as s:token=s['credit_csrf']
 def data(action='grant',**kw):
  return dict(csrf=token,operation=str(uuid.uuid4()),dealer_id='dealer',action=action,amount='25',reason='QA TEST ONLY',**kw)
 assert office.post('/head-office/credits',data={**data(),'csrf':'bad'}).status_code==403
 for amount in ['-1','0','1.5','10001']:
  r=office.post('/head-office/credits',data={**data(),'amount':amount});assert r.status_code==200 and b'role="alert"' in r.data
 grant=data();assert office.post('/head-office/credits',data=grant).status_code==302
 assert office.post('/head-office/credits',data=grant).status_code==302
 assert owner.get('/api/account/profile').json['allowance']['lookup_bonus']==25
 assert other.get('/api/account/profile').json['allowance']['lookup_bonus']==0
 assert owner.post('/api/account/profile',json={'brand':'shinglextra','complimentary':1,'lookup_bonus':999}).status_code==200
 assert not owner.get('/api/account/profile').json['allowance']['brand']
 # Normal-plan saved estimates exhaust base first, then bonuses; revisions are free.
 payload={'address':'QA TEST first','customer_name':'QA TEST ONLY','total_price':1}
 from measurement_integrity import polygon_sqft
 points=[[52,-106],[52,-105.9999],[52.0001,-105.9999],[52.0001,-106]]
 quantity=round(polygon_sqft(points))
 payload['quote']={'commercialAreas':[{'points':points,'sqft':quantity,'rate':.1}]}
 payload['total_area']=quantity
 assert owner.post('/api/estimates',json=payload).status_code==200
 for i in range(25):
  assert employee.post('/api/estimates',json={**payload,'address':f'QA TEST extra {i}'}).status_code==200
 assert owner.post('/api/estimates',json={**payload,'address':'QA TEST over limit'}).status_code==403
 assert employee.post('/api/estimates',json=payload).status_code==200
 cfg=data('configure',complimentary='1',brand='shingle_guard')
 assert office.post('/head-office/credits',data=cfg).status_code==302
 assert owner.get('/api/account/profile').json['allowance']['brand']=='shingle_guard'
 assert owner.post('/api/account/profile',json={'showWarrantyShield':False}).status_code==200
 assert employee.post('/api/account/profile',json={'showWarrantyShield':True}).status_code==403
 assert owner.get('/api/account/profile').json['profile']['showWarrantyShield'] is False
 # Monthly lookups stop at 200+25 unspent measurement bonuses, including employee usage.
 for i in range(225):
  with a.app.test_request_context('/'):
   a.session.update(dealer_id='dealer',account_type='owner')
   assert a.consume_property_lookup('dealer')[0],i
 with a.app.test_request_context('/'):
  a.session.update(dealer_id='dealer',account_type='owner')
  assert not a.consume_property_lookup('dealer')[0]
 # Boundary uses Edmonton, not UTC; bonus stays exhausted into a fresh month.
 assert month_key(datetime(2026,11,1,5,59,tzinfo=timezone.utc))=='2026-10'
 assert month_key(datetime(2026,11,1,6,0,tzinfo=timezone.utc))=='2026-11'
 con=a.estimate_db();lock_account(con,'dealer')
 assert consume(con,'dealer','lookups',999,1,datetime(2026,11,2,tzinfo=timezone.utc))[0]
 assert settings(con,'dealer')['lookup_bonus']==0
 con.commit();con.close()
 # Changing brand or re-saving membership cannot reset usage.
 assert office.post('/head-office/credits',data=data('configure',complimentary='1',brand='shinglextra')).status_code==302
 with a.app.test_request_context('/'):
  a.session.update(dealer_id='dealer',account_type='owner');assert not a.consume_property_lookup('dealer')[0]
 # Complimentary estimate channel is also capped at 200; saved revisions stay available.
 for i in range(200):
  assert owner.post('/api/estimates',json={**payload,'address':f'QA TEST monthly {i}'}).status_code==200
 assert owner.post('/api/estimates',json={**payload,'address':'QA TEST monthly blocked'}).status_code==403
 assert employee.post('/api/estimates',json=payload).status_code==200
 html=office.get('/head-office/dealers').data.decode()
 assert 'Complimentary dealers' in html and 'Complimentary dealer — 200 monthly' in html
 con=a.estimate_db()
 assert con.execute("SELECT COUNT(*) AS n FROM account_credit_audit WHERE action='grant'").fetchone()['n']==1
 assert con.execute("SELECT COUNT(*) AS n FROM account_credit_audit WHERE dealer_id='other'").fetchone()['n']==0
 con.close()
 # Disable in the credit console blocks existing owner/employee sessions, preserves data,
 # stops monthly access and does not award new credits on reactivation.
 owner=client('dealer');employee=client('dealer','employee');dormant=client('dealer')
 con=a.estimate_db()
 before_count=con.execute("SELECT COUNT(*) AS n FROM estimates WHERE dealer_id='dealer'").fetchone()['n']
 before_cfg=settings(con,'dealer');con.close()
 disable=data('disable')
 assert office.post('/head-office/credits',data=disable).status_code==302
 assert office.post('/head-office/credits',data=disable).status_code==302
 assert owner.get('/api/account/profile').status_code==401
 assert employee.get('/api/estimates').status_code==401
 con=a.estimate_db()
 assert settings(con,'dealer')['complimentary']==0
 assert settings(con,'dealer')['lookup_bonus']==before_cfg['lookup_bonus']
 assert con.execute("SELECT COUNT(*) AS n FROM estimates WHERE dealer_id='dealer'").fetchone()['n']==before_count
 assert con.execute("SELECT COUNT(*) AS n FROM account_credit_audit WHERE action='disable'").fetchone()['n']==1
 con.close()
 assert office.post('/head-office/credits',data=data('reactivate')).status_code==302
 assert dormant.get('/api/account/profile').status_code==401,'Reactivation never revives an old login session'
 revived=client('dealer').get('/api/account/profile')
 assert revived.status_code==200 and not revived.json['allowance']['complimentary']
 assert office.post('/head-office/credits',data={**data('disable'),'dealer_id':'office'}).status_code==200
 assert office.get('/head-office/credits').status_code==200,'Head Office cannot disable itself'
 print('PASS: Head Office-only grants, CSRF, duplicate retry, invalid inputs, profile escalation rejection, employee-shared limits, ordinary extra credits, 200 monthly quotas in both channels, Edmonton rollover, no reset on brand/resave, free revisions and separate reporting')
