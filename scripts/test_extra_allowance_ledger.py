"""Source-lot migration/reconciliation and simulated top-ups; disposable DB only."""
import os,sys,tempfile,uuid,copy,json
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
class Clock(datetime):
 value=datetime(2030,1,20,12,tzinfo=timezone.utc)
 @classmethod
 def now(cls,tz=None):return cls.value.astimezone(tz or timezone.utc)
with tempfile.TemporaryDirectory() as td:
 pg='--postgres' in sys.argv;url=os.environ.get('QA_POSTGRES_URL','') if pg else ''
 if pg:
  u=urlsplit(url);assert u.hostname in ('127.0.0.1','localhost') and u.path=='/aeriquote_qa'
 os.environ['DATABASE_URL']=url;os.environ['ESTIMATE_DB_PATH']=td+'/ledger.db'
 os.environ.pop('RENDER_SERVICE_ID',None);os.environ.pop('RENDER_EXTERNAL_HOSTNAME',None)
 import app as a,account_credits as c,extra_allowance_ledger as l
 from qa_estimate_fixture import price_fixture
 from measurement_integrity import polygon_sqft
 a.is_recovery_test_service=lambda:False;a.is_head_office=lambda:False
 prefix='ledger-'+uuid.uuid4().hex[:9]+'-'
 tax={'version':'fictional-policy-1','rates_bps':{'US':0,'CA:SK':1100}}
 def owner(name,lookup=0,estimate=0):
  did=prefix+name;db=a.estimate_db()
  db.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,status,created_at,plan_code,lookup_limit,estimate_limit) VALUES(?,?,?,'unused','active','2029-12-15T12:00:00Z','basic',0,0)",(did,'FICTIONAL LEDGER',did+'@example.invalid'))
  db.execute('INSERT INTO account_allowances(dealer_id,lookup_bonus,estimate_bonus) VALUES(?,?,?)',(did,lookup,estimate));db.commit();db.close();return did
 def mutate(did,fn,commit=True):
  db=a.estimate_db()
  try:
   c.lock_account(db,did);result=fn(db)
   if commit:db.commit()
   return result
  finally:db.close()
 def read(did):
  db=a.estimate_db()
  try:return l.reconciliation(db,did)
  finally:db.close()
 def count(did,table):
  db=a.estimate_db()
  try:return db.execute('SELECT COUNT(*) AS n FROM '+table+' WHERE dealer_id=?',(did,)).fetchone()['n']
  finally:db.close()
 def use(did,kind='lookups',commit=True,operation=None):return mutate(did,lambda db:c.consume(db,did,kind,0,0,now=Clock.value,operation_id=operation),commit)
 def pack(did,key,**kw):return mutate(did,lambda db:l.fulfill_simulated_pack(db,did,key,country=kw.pop('country','US'),region=kw.pop('region',''),tax_policy=kw.pop('tax_policy',tax)))
 def config(did,order=None,eligibility='simulation_only',refund=None):return mutate(did,lambda db:l.configure_simulation(db,did,spend_order=order,eligibility=eligibility,refund_policy=refund))
 def rejects(fn):
  try:fn()
  except (l.LedgerError,ValueError):return
  raise AssertionError('Expected fail-closed rejection')
 with patch.object(c,'datetime',Clock):
  legacy=owner('legacy',17,9)
  before=read(legacy);assert not before['opened'] and before['bank']=={'lookups':17,'estimates':9}
  # Eight first users initialize one opening; no bank update and no purchase reclassification.
  with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(lambda _:mutate(legacy,lambda db:l.ensure_opening(db,legacy)),range(8)))
  assert read(legacy)['balanced'] and count(legacy,'extra_bank_openings')==1
  assert read(legacy)['sources']=={'granted':{'lookups':17,'estimates':9},'purchased':{'lookups':0,'estimates':0}}
  with ThreadPoolExecutor(max_workers=8) as pool:grants=list(pool.map(lambda _:mutate(legacy,lambda db:l.grant_administrative(db,legacy,25,'admin-retry')),range(8)))
  assert sum(created for _,created in grants)==1
  assert read(legacy)['bank']=={'lookups':42,'estimates':34} and count(legacy,'extra_source_lots')==2
  rejects(lambda:mutate(legacy,lambda db:l.grant_administrative(db,legacy,24,'admin-retry')))
  before=read(legacy);lots=count(legacy,'extra_source_lots')
  mutate(legacy,lambda db:l.grant_administrative(db,legacy,3,'rolled-back'),False)
  assert read(legacy)==before and count(legacy,'extra_source_lots')==lots
  print('PASS legacy opening exactly once, existing balances unchanged/granted, concurrent duplicate administrative grants once, mismatched reference rejected, rollback')
  purchase=owner('purchase')
  with ThreadPoolExecutor(max_workers=8) as pool:orders=list(pool.map(lambda _:pack(purchase,'order-1'),range(8)))
  assert sum(created for _,created in orders)==1
  assert count(purchase,'extra_simulated_orders')==1 and count(purchase,'extra_source_lots')==1
  order=orders[0][0];assert (order['quantity'],order['currency'],order['subtotal_cents'],order['tax_cents'],order['total_cents'])==(25,'USD',2500,0,2500)
  assert read(purchase)['sources']['purchased']=={'lookups':25,'estimates':25}
  rejects(lambda:pack(purchase,'order-1',country='CA',region='SK'))
  other=owner('other');ca,_=pack(other,'order-1',country='CA',region='SK')
  assert (ca['subtotal_cents'],ca['tax_cents'],ca['total_cents'])==(2500,275,2775)
  rejects(lambda:pack(other,'unknown-province',country='CA',region='UNKNOWN'))
  assert count(other,'extra_simulated_orders')==1
  assert read(other)['bank']=={'lookups':25,'estimates':25}
  before=read(other);mutate(other,lambda db:l.fulfill_simulated_pack(db,other,'rollback',country='US',tax_policy=tax),False)
  assert read(other)==before and count(other,'extra_simulated_orders')==1
  print('PASS simulated pack25 with estimates, USD25 subtotal, configurable Canada tax/US zero, per-business order idempotency, mismatch/unknown-tax rejection, fulfillment rollback')
  # Purchased use is not activated by fulfilling a simulated record alone.
  for _ in range(25):assert use(purchase)[0]
  assert not use(purchase)[0] and read(purchase)['bank']['lookups']==25
  config(purchase,refund={'mode':'unapproved'})
  db=a.estimate_db();policy=db.execute('SELECT * FROM extra_policies WHERE dealer_id=?',(purchase,)).fetchone();db.close()
  assert json.loads(policy['refund_policy'])=={'mode':'unapproved'} and policy['purchase_eligibility']=='simulation_only'
  assert use(purchase,operation='lookup:one')[0]
  assert read(purchase)['bank']=={'lookups':24,'estimates':25},'Saving an estimate must not spend another measurement'
  for _ in range(25):assert use(purchase,'estimates')[0]
  assert use(purchase,'estimates',operation='save:one')[0]
  assert read(purchase)['bank']=={'lookups':24,'estimates':24}
  before=read(purchase);assert use(purchase,commit=False)[0];assert read(purchase)==before
  Clock.value=datetime(2040,2,20,12,tzinfo=timezone.utc)
  assert use(purchase)[0];assert read(purchase)==before,'Renewal/ten-year advance cannot expire or debit purchased extras'
  Clock.value=datetime(2030,1,20,12,tzinfo=timezone.utc)
  print('PASS monthly first, purchased eligibility unapproved by default, included-estimate channel, rollback, renewal and nonexpiry')
  pack(legacy,'mixed');config(legacy)
  for _ in range(25):assert use(legacy)[0]
  before=read(legacy);assert not use(legacy)[0] and read(legacy)==before,'Mixed pool priority requires explicit fixture policy'
  config(legacy,'granted_first');assert use(legacy)[0]
  assert read(legacy)['sources']['granted']['lookups']==41 and read(legacy)['sources']['purchased']['lookups']==25
  config(legacy,'purchased_first');assert use(legacy)[0]
  assert read(legacy)['sources']['purchased']['lookups']==24
  assert read(legacy)['balanced']
  race=owner('race');pack(race,'one');config(race)
  for _ in range(49):assert use(race)[0]
  with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(lambda _:use(race)[0],range(8)))
  assert sum(results)==1 and read(race)['bank']['lookups']==0 and read(race)['balanced']
  print('PASS configurable mixed-source priority (no assumed approval), last purchased unit race exactly once, nonnegative source-lot reconciliation')
  # Actual authenticated save path, shared business bank and receipt atomicity.
  eid=prefix+'employee';db=a.estimate_db();db.execute("INSERT INTO dealer_employees(id,dealer_id,employee_name,email,password_hash,status,created_at) VALUES(?,?,?,?,'unused','active','2030-01-01')",(eid,purchase,'FICTIONAL EMPLOYEE',eid+'@example.invalid'));db.commit();db.close()
  def client(did=purchase,employee=False):
   cl=a.app.test_client()
   with cl.session_transaction() as s:
    s.update(dealer_id=did,account_type='employee' if employee else 'owner',auth_version=0)
    if employee:s['employee_id']=eid
   return cl
  points=[[52,-106],[52,-105.9999],[52.0001,-105.9999],[52.0001,-106]]
  payload={'address':'FICTIONAL LEDGER SAVED JOB','quote':{'commercialAreas':[{'points':points,'sqft':round(polygon_sqft(points)),'rate':.1}]}}
  price_fixture(payload)
  def save(i):return client(employee=bool(i%2)).post('/api/estimates',json=payload,headers={'Idempotency-Key':'ledger-save'})
  before=read(purchase)
  with ThreadPoolExecutor(max_workers=8) as pool:responses=list(pool.map(save,range(8)))
  assert all(r.status_code==200 for r in responses),[r.json for r in responses]
  assert len({r.json['id'] for r in responses})==1 and read(purchase)['bank']['estimates']==before['bank']['estimates']-1
  db=a.estimate_db();moves=db.execute("SELECT channel,delta FROM extra_movements WHERE dealer_id=? AND operation_ref='save:ledger-save'",(purchase,)).fetchall();db.close()
  assert [(r['channel'],r['delta']) for r in moves]==[('estimates',-1)]
  after=read(purchase);assert save(0).status_code==200 and read(purchase)==after
  assert client(other).get('/api/estimates/'+responses[0].json['id']).status_code==404
  assert client(employee=True).get('/api/estimates/'+responses[0].json['id']).status_code==200 and read(purchase)==after
  assert read(other)['bank']=={'lookups':25,'estimates':25}
  print('PASS owner/employee save retries one ledger debit/one estimate, free reopening, other-business isolation')
  # Exact lookup operation is recorded in the same acceptance transaction.
  def provider(data):
   token=a.create_session('FICTIONAL-NO-PROVIDER',52,-106,mode='manual_static')
   return a.jsonify(token=token,fallback=True,center={'latitude':52,'longitude':-106})
  with patch.object(a,'perform_property_lookup',side_effect=provider):
   prepared=client().post('/property',json={'key':'FICTIONAL','address':'FICTIONAL LEDGER PROPERTY','prepare_only':True},headers={'Idempotency-Key':'ledger-property'})
   assert prepared.status_code==200;body={'operation_id':'ledger-property','token':prepared.json['token']};before=read(purchase)
   def accept(i):return client(employee=bool(i%2)).post('/property/accept',json=body).status_code
   with ThreadPoolExecutor(max_workers=8) as pool:assert list(pool.map(accept,range(8)))==[200]*8
   assert read(purchase)['bank']['lookups']==before['bank']['lookups']-1
   db=a.estimate_db();rows=db.execute("SELECT delta FROM extra_movements WHERE dealer_id=? AND operation_ref='lookup:ledger-property'",(purchase,)).fetchall();db.close();assert len(rows)==1 and rows[0]['delta']==-1
  before=read(purchase);movement_count=count(purchase,'extra_movements')
  failed=copy.deepcopy(payload);failed['address']='FICTIONAL INTERRUPTED LEDGER SAVE'
  original_execute=a.DBCompat.execute
  def fail_write(db,sql,params=()):
   if sql.startswith('INSERT INTO estimates('):raise RuntimeError('Fictional interrupted save')
   return original_execute(db,sql,params)
  with patch.object(a.DBCompat,'execute',fail_write):assert client().post('/api/estimates',json=failed,headers={'Idempotency-Key':'rollback-save'}).status_code==500
  assert read(purchase)==before and count(purchase,'extra_movements')==movement_count
  for _ in range(2):assert client().post('/api/estimates',json=failed,headers={'Idempotency-Key':'rollback-save'}).status_code==200
  assert read(purchase)['bank']['estimates']==before['bank']['estimates']-1 and count(purchase,'extra_movements')==movement_count+1
  rejects(lambda:mutate(other,lambda db:l._entry(db,other,order['lot_id'],'lookups',-1,'consume','cross-business')))
  print('PASS lookup operation trace once across owner/employee retries; interrupted save rolls back movement/bank/receipt, retry once; cross-business lot write denied')
  # Out-of-band/old-version bank writes cannot silently invent source attribution.
  drift=owner('drift',1,1);mutate(drift,lambda db:l.ensure_opening(db,drift))
  mutate(drift,lambda db:db.execute('UPDATE account_allowances SET lookup_bonus=2 WHERE dealer_id=?',(drift,)))
  assert not read(drift)['balanced'];rejects(lambda:mutate(drift,lambda db:l.deduct_extra(db,drift,'lookups')))
  for table in ['extra_movements','extra_source_lots','extra_bank_openings','extra_simulated_orders']:
   db=a.estimate_db()
   try:
    try:db.execute('DELETE FROM '+table+' WHERE dealer_id=?',(purchase,));raise AssertionError('History must be append-only')
    except Exception as exc:
     if isinstance(exc,AssertionError):raise
   finally:db.close()
  class Info:host='hosted-not-qa';dbname='aeriquote_qa'
  class Raw:info=Info()
  class Hosted:postgres=True;con=Raw()
  rejects(lambda:l.fulfill_simulated_pack(Hosted(),'not-real','blocked',country='US',tax_policy=tax))
  print('PASS immutable history, independent bank drift detection/fail-closed, hosted simulation guard; no refund or production eligibility activated')
  print(json.dumps({'backend':'postgres' if pg else 'sqlite','purchase':read(purchase),'other':read(other),'actual_payments':False},sort_keys=True))
