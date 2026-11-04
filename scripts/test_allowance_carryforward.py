"""Disposable paid/complimentary bonus-bank audit; no payments or hosted databases.

Administrative extras exercise the existing nonexpiring bank. They are not
payment-backed purchases. SQLite and optional loopback PostgreSQL only.
"""
import os,sys,tempfile,uuid,copy,json
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
utc=timezone.utc
at=lambda value:datetime.fromisoformat(value).replace(tzinfo=utc)
class Clock(datetime):
 value=at('2030-01-20T12:00:00')
 @classmethod
 def now(cls,tz=None):return cls.value.astimezone(tz or utc)

with tempfile.TemporaryDirectory() as tmp:
 pg='--postgres' in sys.argv
 url=os.environ.get('QA_POSTGRES_URL','') if pg else ''
 if pg:
  parsed=urlsplit(url);assert parsed.hostname in ('localhost','127.0.0.1') and parsed.path=='/aeriquote_qa','Disposable loopback aeriquote_qa only'
 os.environ['DATABASE_URL']=url;os.environ['ESTIMATE_DB_PATH']=tmp+'/carryforward.db'
 os.environ.pop('RENDER_SERVICE_ID',None);os.environ.pop('RENDER_EXTERNAL_HOSTNAME',None)
 import app as a
 import account_credits as credit
 from qa_estimate_fixture import price_fixture
 from measurement_integrity import polygon_sqft
 original_db=a.estimate_db
 original_db().close()
 # Apply normal production allowance policy to isolated SQLite, as in the
 # established fresh-user fixture. This marker can never open a real database.
 if not pg:
  def db():
   import sqlite3
   raw=sqlite3.connect(tmp+'/carryforward.db',timeout=30);raw.row_factory=sqlite3.Row
   return a.DBCompat(raw,False)
  a.estimate_db=db;a.DATABASE_URL='postgresql://disposable-policy-only'
 a.is_recovery_test_service=lambda:False;a.is_head_office=lambda:False
 prefix='carry-'+uuid.uuid4().hex[:10]+'-'
 def identity(name,plan='basic',bonus=25,comp=False):
  did=prefix+name;c=a.estimate_db()
  try:
   c.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,status,created_at,plan_code,lookup_limit,estimate_limit) VALUES(?,?,?,'unused','active','2029-12-15T12:00:00Z',?,0,0)",(did,'FICTIONAL AUDIT',did+'@example.invalid',plan))
   c.execute('INSERT INTO account_allowances(dealer_id,complimentary,lookup_bonus,estimate_bonus) VALUES(?,?,?,?)',(did,int(comp),bonus,bonus));c.commit()
  finally:c.close()
  return did
 def consume(did,kind='lookups',now=None,commit=True):
  c=a.estimate_db()
  try:
   credit.lock_account(c,did);result=credit.consume(c,did,kind,0,0,now or Clock.value)
   if commit:c.commit()
   return result
  finally:c.close()
 def bank(did):
  c=a.estimate_db()
  try:return credit.settings(c,did)
  finally:c.close()
 def state(did):
  c=a.estimate_db()
  try:
   p=credit.paid_usage(c,did,now=Clock.value)
   return {'lookup_bonus':credit.settings(c,did)['lookup_bonus'],'estimate_bonus':credit.settings(c,did)['estimate_bonus'],'lookups':p['lookups'],'estimates':p['estimates'],'saved':c.execute('SELECT COUNT(*) AS n FROM estimates WHERE dealer_id=?',(did,)).fetchone()['n'],'revisions':c.execute('SELECT COUNT(*) AS n FROM estimate_revisions WHERE dealer_id=?',(did,)).fetchone()['n']}
  finally:c.close()
 def client(did,employee=None):
  c=a.app.test_client()
  with c.session_transaction() as s:
   s.update(dealer_id=did,account_type='employee' if employee else 'owner',auth_version=0)
   if employee:s['employee_id']=employee
  return c
 def employee(did,name):
  eid=prefix+name;c=a.estimate_db()
  c.execute("INSERT INTO dealer_employees(id,dealer_id,employee_name,email,password_hash,status,created_at) VALUES(?,?,?,?,'unused','active','2030-01-01')",(eid,did,'FICTIONAL EMPLOYEE',eid+'@example.invalid'));c.commit();c.close();return eid
 with patch.object(credit,'datetime',Clock):
  for plan,limit in [('basic',25),('pro',75),('business',200),('complimentary',200)]:
   did=identity(plan,plan='trial' if plan=='complimentary' else plan,comp=plan=='complimentary')
   for kind,col in [('lookups','lookup_bonus'),('estimates','estimate_bonus')]:
    for _ in range(limit):assert consume(did,kind)[0]
    assert bank(did)[col]==25,(plan,kind,'monthly must be spent first')
    assert consume(did,kind)[0];assert bank(did)[col]==24
    # A rolled-back request cannot consume bank or monthly use.
    before=bank(did);assert consume(did,kind,commit=False)[0];assert bank(did)==before
    assert consume(did,kind,at('2030-02-20T12:00:00'))==(True,1,limit)
    assert bank(did)[col]==24,'Renewal cannot erase unused extras'
    assert consume(did,kind,at('2040-02-20T12:00:00'))==(True,1,limit)
    assert bank(did)[col]==24,'No expiry across ten years'
   print('PASS monthly-first, rollback, renewal and ten-year carry-forward:',plan)
  # Racing distinct uses across the last monthly unit and one bank unit.
  race=identity('race',bonus=1)
  for _ in range(24):assert consume(race)[0]
  with ThreadPoolExecutor(max_workers=8) as pool:allowed=list(pool.map(lambda _:consume(race)[0],range(8)))
  assert sum(allowed)==2 and bank(race)['lookup_bonus']==0
  assert state(race)['lookups']==26
  print('PASS eight concurrent distinct uses: final monthly + final extra exactly once each')
  owner=identity('owner',bonus=2);other=identity('other',bonus=2);eid=employee(owner,'employee')
  for did in [owner,other]:
   c=a.estimate_db();credit.lock_account(c,did);period=credit.paid_usage(c,did,now=Clock.value,initialize=True)
   c.execute('UPDATE account_subscription_usage SET lookups=25,estimates=25 WHERE dealer_id=? AND period_start=?',(did,period['start']));c.commit();c.close()
  def provider(data):
   token=a.create_session('FICTIONAL-NO-PROVIDER',52,-106,mode='manual_static')
   return a.jsonify(token=token,fallback=True,center={'latitude':52,'longitude':-106})
  def prepare(did,op,emp=None):
   return client(did,emp).post('/property',json={'address':'FICTIONAL AUDIT PROPERTY','key':'FICTIONAL','prepare_only':True},headers={'Idempotency-Key':op})
  before=state(owner)
  def failed(data):return a.jsonify(error='FICTIONAL imagery unavailable'),503
  with patch.object(a,'perform_property_lookup',side_effect=failed):
   assert prepare(owner,'failed').status_code==503
   assert client(owner).post('/property',json={'address':'FICTIONAL','key':'FICTIONAL'},headers={'Idempotency-Key':'failed-direct'}).status_code==503
  assert state(owner)==before,'Provider failures must not consume bonus or monthly allowance'
  with patch.object(a,'perform_property_lookup',side_effect=provider):
   prepared=prepare(owner,'accepted');assert prepared.status_code==200
   body={'operation_id':'accepted','token':prepared.json['token']}
   assert state(owner)==before,'Prepared but never accepted imagery must be free'
   # Other business cannot confirm or inspect this prepared operation.
   assert client(other).post('/property/accept',json=body).status_code==404
   def accept(i):return client(owner,eid if i%2 else None).post('/property/accept',json=body).status_code
   with ThreadPoolExecutor(max_workers=8) as pool:assert list(pool.map(accept,range(8)))==[200]*8
   after=state(owner);assert after['lookup_bonus']==1 and after['lookups']==26
   assert client(owner).post('/property/accept',json=body).status_code==200
   assert prepare(owner,'accepted').json==prepared.json
   assert state(owner)==after,'Lost response / replay must not debit twice'
   abandoned=prepare(owner,'never-accepted');assert abandoned.status_code==200;assert state(owner)==after
   pending=[]
   for i in range(8):
    r=prepare(owner,'distinct-'+str(i));assert r.status_code==200;pending.append({'operation_id':'distinct-'+str(i),'token':r.json['token']})
   def last(i):return client(owner,eid if i%2 else None).post('/property/accept',json=pending[i]).status_code
   with ThreadPoolExecutor(max_workers=8) as pool:codes=list(pool.map(last,range(8)))
   assert codes.count(200)==1 and codes.count(403)==7,codes
   assert state(owner)['lookup_bonus']==0 and state(owner)['lookups']==27
   # Same operation name is scoped to another business's own token and balance.
   r=prepare(other,'accepted');assert r.status_code==200
   assert client(other).post('/property/accept',json={'operation_id':'accepted','token':r.json['token']}).status_code==200
   assert state(other)['lookup_bonus']==1 and state(other)['lookups']==26
  print('PASS real property routes: failures/abandoned imagery free; owner/employee replay once; last-bank concurrency; business isolation')
  points=[[52,-106],[52,-105.9999],[52.0001,-105.9999],[52.0001,-106]]
  payload={'address':'FICTIONAL AUDIT SAVED JOB','customer_name':'FICTIONAL OWNER','quote':{'commercialAreas':[{'points':points,'sqft':round(polygon_sqft(points)),'rate':.1}]}}
  price_fixture(payload)
  def save(i,payload=payload,operation='same-save',version=None):
   headers={'Idempotency-Key':operation}
   if version:headers['If-Match']=version
   return client(owner,eid if i%2 else None).post('/api/estimates',json=payload,headers=headers)
  before=state(owner)
  with ThreadPoolExecutor(max_workers=8) as pool:responses=list(pool.map(save,range(8)))
  assert all(r.status_code==200 for r in responses),[r.status_code for r in responses]
  assert len({r.json['id'] for r in responses})==1
  saved=responses[0].json;after=state(owner)
  assert after['estimate_bonus']==before['estimate_bonus']-1 and after['estimates']==26 and after['saved']==1 and after['revisions']==0
  assert save(1).json==saved and state(owner)==after
  assert save(1,operation='new-key-same-payload').status_code==200 and state(owner)==after
  changed=copy.deepcopy(payload);changed['customer_name']='FICTIONAL REVISED';changed['quote']['commercialAreas'][0]['rate']=.2;price_fixture(changed)
  result=save(1,changed,'edit',saved['version']);assert result.status_code==200
  revised=state(owner);assert revised['revisions']==1 and revised['estimate_bonus']==after['estimate_bonus'] and revised['lookups']==after['lookups']
  assert save(0,changed,'edit',saved['version']).json==result.json and state(owner)==revised
  stale=copy.deepcopy(changed);stale['customer_name']='FICTIONAL STALE'
  assert save(0,stale,'stale',saved['version']).status_code==409 and state(owner)==revised
  invalid=copy.deepcopy(changed);invalid['quote']['commercialAreas'][0]['points']=points[:2]
  assert save(0,invalid,'invalid',result.json['version']).status_code==400 and state(owner)==revised
  for actor in [client(owner),client(owner,eid)]:
   assert actor.get('/api/estimates/'+saved['id']).status_code==200
   assert actor.get('/api/estimates/'+saved['id']+'/versions').status_code==200
  assert client(other).get('/api/estimates/'+saved['id']).status_code==404
  assert state(owner)==revised,'Reopening does not debit either allowance channel'
  assert client(owner).post('/api/account/profile',json={'lookup_bonus':999,'estimate_bonus':999,'subscription_usage':0}).status_code==200
  assert state(owner)==revised,'Profile fields cannot mint extras or reset monthly usage'
  c=a.estimate_db();c.execute("UPDATE dealer_employees SET status='disabled' WHERE id=?",(eid,));c.commit();c.close()
  assert client(owner,eid).post('/property/accept',json=body).status_code==401 and state(owner)==revised
  print('PASS saves: eight owner/employee retries once, free unchanged saves/revisions/reopens, stale/invalid blocked, cross-business and disabled-employee isolation, tamper rejection')
  print(json.dumps({'backend':'postgres' if pg else 'sqlite','owner':state(owner),'other':state(other),'payments':'not implemented or exercised'},sort_keys=True))
