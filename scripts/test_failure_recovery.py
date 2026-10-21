"""Real Flask/DB failure and concurrent-request regressions; fixtures only.

Default uses disposable SQLite. --postgres REQUIRES an isolated local CI service,
never the app's existing DATABASE_URL or any Render/customer database.
"""
import copy,json,os,sys,tempfile,threading,time,uuid
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from urllib.parse import urlsplit
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parent)]
pg='--postgres' in sys.argv
scratch=tempfile.TemporaryDirectory()
if pg:
 url=os.environ.get('QA_POSTGRES_URL','');parts=urlsplit(url)
 assert parts.hostname in ('127.0.0.1','localhost') and parts.path=='/aeriquote_qa','Requires disposable localhost aeriquote_qa database'
 os.environ['DATABASE_URL']=url
else:os.environ['DATABASE_URL']=''
os.environ['ESTIMATE_DB_PATH']=scratch.name+'/batch4.db'
os.environ.pop('RENDER_SERVICE_ID',None);os.environ.pop('RENDER_EXTERNAL_HOSTNAME',None)
import app as a
from qa_estimate_fixture import price_fixture
from measurement_integrity import polygon_sqft
from account_credits import month_key
a.app.logger.disabled=True
points=[[52,-106],[52,-105.9999],[52.0001,-105.9999],[52.0001,-106]]
def client(did='qa4-owner',employee=None):
 c=a.app.test_client()
 with c.session_transaction() as s:
  s.update(dealer_id=did,auth_version=0,account_type='employee' if employee else 'owner')
  if employee:s['employee_id']=employee
 return c
def fixture(address='QA TEST Batch4 DO NOT SEND'):
 p={'address':address,'job_status':'Estimate','amount_paid':0,'quote':{'commercialAreas':[{'points':points,'sqft':round(polygon_sqft(points)),'rate':1}]}}
 price_fixture(p);return p
def sql(query,params=(),one=False):
 con=a.estimate_db()
 try:
  cur=con.execute(query,params)
  result=cur.fetchone() if one else None;con.commit();return result
 finally:con.close()
def owner(did):
 sql("INSERT INTO dealers(id,dealer_name,email,password_hash,status,created_at,lookup_limit,estimate_limit) VALUES(?,?,?,'unused','active','2026-10-21',1,1)",(did,'QA TEST '+did,did+'@example.invalid'))
 sql("INSERT INTO account_allowances(dealer_id,complimentary) VALUES(?,1)",(did,))
 sql("INSERT INTO account_month_usage(dealer_id,period,lookups,estimates) VALUES(?,?,199,199)",(did,month_key()))
def used(did,kind):return sql('SELECT '+kind+' AS n FROM account_month_usage WHERE dealer_id=? AND period=?',(did,month_key()),True)['n']
def together(fn,n=8):
 barrier=threading.Barrier(n)
 def run(i):barrier.wait(timeout=15);return fn(i)
 with ThreadPoolExecutor(max_workers=n) as pool:return list(pool.map(run,range(n)))
owner('qa4-owner');owner('qa4-other')
large=fixture('QA TEST precision');large['quote']['commercialAreas'][0]['rate']=12345.67;price_fixture(large)
large_response=client('qa4-other').post('/api/estimates',json=large);assert large_response.status_code==200
stored=client('qa4-other').get('/api/estimates/'+large_response.json['id']).json
assert abs(stored['total_price']-large['total_price'])<.000001,'Database total must retain cents for large quotes'

c=client();p=fixture();headers={'Idempotency-Key':'first'}
r=c.post('/api/estimates',json=p,headers=headers);assert r.status_code==200,r.data
eid=r.json['id'];v=r.json['version']
assert c.post('/api/estimates',json=p,headers=headers).json==r.json
assert c.post('/api/estimates',json=p).status_code==200
assert sql('SELECT COUNT(*) AS n FROM estimate_revisions',one=True)['n']==0
assert used('qa4-owner','estimates')==200
p2=copy.deepcopy(p);p2['customer_name']='QA TEST edited';h2={'Idempotency-Key':'second','If-Match':v}
r2=c.post('/api/estimates',json=p2,headers=h2);assert r2.status_code==200,r2.data
assert c.post('/api/estimates',json=p,headers=headers).json==r.json,'Lost response replay returns original receipt'
assert c.get('/api/estimates/'+eid).json['payload']['customer_name']=='QA TEST edited','Old replay must not overwrite a newer edit'
assert c.post('/api/estimates',json=p2,headers=headers).status_code==409
assert c.post('/api/estimates',json=p,headers={'Idempotency-Key':'stale','If-Match':v}).status_code==409
assert client('qa4-other').get('/api/estimates/'+eid).status_code==404
assert c.post('/api/estimates',json=fixture('QA TEST quota')).status_code==403
assert used('qa4-owner','estimates')==200
# Concurrent job-field changes must merge rather than read/overwrite one stale payload.
for cycle in range(3):
 values=[('status',{'job_status':'Booked'}),('amount-paid',{'amount_paid':123.45}),('scheduled-date',{'scheduled_date':'2026-11-01'}),('completion-date',{'completion_date':'2026-11-02'})]
 statuses=together(lambda i:client().post('/api/estimates/'+eid+'/'+values[i][0],json=values[i][1]).status_code,4)
 assert statuses==[200]*4,statuses
 saved=c.get('/api/estimates/'+eid).json['payload'];assert all(saved[k]==val for _,d in values for k,val in d.items()),saved
assert c.post('/api/estimates',json=p2).status_code==200
assert c.get('/api/estimates/'+eid).json['payload']['job_status']=='Booked','Pricing save cannot reset job metadata'
# Parallel identical estimate submissions consume exactly one credit, no duplicate revisions.
owner('qa4-race');race=fixture('QA TEST parallel');statuses=together(lambda i:client('qa4-race').post('/api/estimates',json=race,headers={'Idempotency-Key':'parallel'}).status_code)
assert statuses==[200]*8,statuses
assert sql("SELECT COUNT(*) AS n FROM estimates WHERE dealer_id='qa4-race'",one=True)['n']==1
assert used('qa4-race','estimates')==200
# Inject a transaction failure after credit reservation; retry must succeed once.
owner('qa4-rollback');original=a.DBCompat.execute
failure=[True]
def fail_insert(self,q,params=()):
 if failure[0] and q.startswith('INSERT INTO estimates('):failure[0]=False;raise RuntimeError('QA transaction interruption')
 return original(self,q,params)
with patch.object(a.DBCompat,'execute',fail_insert):assert client('qa4-rollback').post('/api/estimates',json=fixture('QA TEST interrupted'),headers={'Idempotency-Key':'retry'}).status_code==500
assert used('qa4-rollback','estimates')==199
assert client('qa4-rollback').post('/api/estimates',json=fixture('QA TEST interrupted'),headers={'Idempotency-Key':'retry'}).status_code==200
assert used('qa4-rollback','estimates')==200
# Failed provider requests and invalid coordinates must not spend the last credit.
owner('qa4-lookup');lookup=client('qa4-lookup')
with patch.object(a,'google_geocode_first',return_value=(200,{'status':'ZERO_RESULTS'},'')):
 assert lookup.post('/property',json={'key':'qa','address':'invalid'}).status_code==404
assert used('qa4-lookup','lookups')==199
for lat in (float('nan'),float('inf'),91):assert lookup.post('/property',json={'key':'qa','address':'QA coords','direct_coordinates':True,'latitude':lat,'longitude':0}).status_code==400
with patch.object(a,'building',side_effect=TimeoutError('QA upstream timeout')):
 assert lookup.post('/property',json={'key':'qa','address':'QA coords','direct_coordinates':True,'latitude':52,'longitude':-106}).status_code==400
assert used('qa4-lookup','lookups')==199
calls=[]
def provider(d):calls.append(1);time.sleep(.03);return a.jsonify(token='qa-fixture-token')
with patch.object(a,'perform_property_lookup',provider):
 statuses=together(lambda i:client('qa4-lookup').post('/property',json={'key':'qa','address':'QA TEST lookup'},headers={'Idempotency-Key':'lookup-retry'}).status_code)
 assert statuses==[200]*8,statuses
assert len(calls)==1 and used('qa4-lookup','lookups')==200
# Employee creation races return a clear duplicate result instead of a 500.
statuses=together(lambda i:client().post('/dealer-employees',data={'employee_name':'QA TEST employee','email':'qa4-employee@example.invalid','password':'QA-only-pass-2026'}).status_code)
assert statuses==[200]*8,statuses
assert sql("SELECT COUNT(*) AS n FROM dealer_employees WHERE email='qa4-employee@example.invalid'",one=True)['n']==1
employee=sql("SELECT id FROM dealer_employees WHERE email='qa4-employee@example.invalid'",one=True)['id']
old=client(employee=employee);assert old.get('/').status_code==200
for _ in range(2):assert c.post('/dealer-employees/'+employee+'/status',data={'action':'disable'}).status_code==302
assert c.post('/dealer-employees/'+employee+'/status',data={'action':'activate'}).status_code==302
assert old.get('/api/estimates').status_code==401,'Reactivation must not revive a pre-disable session'
assert c.get('/').status_code==200
# Expired sessions stop all JSON writes, preserving the existing saved quote.
expired=client();sql("INSERT INTO account_auth_versions(account_type,account_id,version) VALUES('owner','qa4-owner',1)")
before=sql('SELECT payload FROM estimates WHERE id=?',(eid,),True)['payload']
assert expired.post('/api/estimates',json=p2).status_code==401
assert expired.post('/property',json={'key':'qa','address':'QA TEST'}).status_code==401
assert sql('SELECT payload FROM estimates WHERE id=?',(eid,),True)['payload']==before
if pg:
 con=a.estimate_db();probe=con.execute('SELECT (1234567.89::real)::double precision AS old_total').fetchone()['old_total'];assert abs(probe-1234567.89)>.005;print('Confirmed old REAL precision error:',probe-1234567.89);print('Actual PostgreSQL server version:',con.execute('SHOW server_version').fetchone()['server_version']);con.close()
print('PASS '+('PostgreSQL' if pg else 'SQLite')+': retries, lost responses, stale editors, rollback/credits, 12 concurrent metadata edits, 8 concurrent estimates/lookups/employees, expired access and business isolation')
scratch.cleanup()
