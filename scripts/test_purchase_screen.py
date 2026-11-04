"""Real purchase HTML/POST regression, temp SQLite or isolated PostgreSQL16/18 schema."""
import os,sys,tempfile,json,uuid
from pathlib import Path
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from urllib.parse import urlsplit,urlunsplit,urlencode,parse_qsl
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
class Forms(HTMLParser):
 def __init__(self,text):super().__init__();self.forms=[];self.current=None;self.feed(text)
 def handle_starttag(self,tag,attrs):
  d=dict(attrs)
  if tag=='form':self.current={};self.forms.append(self.current)
  if tag=='input' and self.current is not None and d.get('name'):self.current[d['name']]=d.get('value','')
 def handle_endtag(self,tag):
  if tag=='form':self.current=None
with tempfile.TemporaryDirectory() as td:
 pg='--postgres' in sys.argv;schema=None
 if pg:
  import psycopg
  from psycopg import sql
  raw=os.environ['QA_POSTGRES_URL'];u=urlsplit(raw);assert u.hostname in ('localhost','127.0.0.1') and u.path=='/aeriquote_qa';schema='screen_'+uuid.uuid4().hex
  with psycopg.connect(raw,autocommit=True) as db:db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
  args=dict(parse_qsl(u.query));args['options']='-csearch_path='+schema;os.environ['DATABASE_URL']=urlunsplit(u._replace(query=urlencode(args)))
 else:os.environ['DATABASE_URL']=''
 os.environ['ESTIMATE_DB_PATH']=td+'/screen.db';os.environ['FLASK_SECRET_KEY']='fictional-screen-test';os.environ['AERIQUOTE_QA_PURCHASES']='1';os.environ['AERIQUOTE_QA_TOPUP_TAX_POLICY']=json.dumps({'version':'fictional-v1','rates_bps':{'US':0,'CA:SK':1100}})
 os.environ.pop('RENDER_SERVICE_ID',None);os.environ.pop('RENDER_EXTERNAL_HOSTNAME',None)
 import app as a,account_credits as c,extra_allowance_ledger as l,payment_free_orders as p
 try:
  def query(sql,params=()):
   db=a.estimate_db()
   try:return [dict(x) for x in db.execute(sql,params).fetchall()]
   finally:db.close()
  def tx(did,fn):
   db=a.estimate_db()
   try:c.lock_account(db,did);v=fn(db);db.commit();return v
   finally:db.close()
  for did,country,region in [('screen-ca','CA','SK'),('screen-us','US','TX')]:
   db=a.estimate_db();db.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,status,created_at,plan_code,lookup_limit,estimate_limit) VALUES(?,?,?,'unused','active','2026-01-01','basic',25,25)",(did,'FICTIONAL SCREEN',did+'@example.invalid'));db.execute('INSERT INTO dealer_profiles(dealer_id,profile_json,updated_at) VALUES(?,?,?)',(did,json.dumps({'country':country,'province':region}),'2026-11-04'));db.commit();db.close();tx(did,lambda db:l.grant_administrative(db,did,3,'fixture-grant'))
  tx('screen-ca',lambda db:db.execute("INSERT INTO dealer_employees(id,dealer_id,employee_name,email,password_hash,status,created_at) VALUES('screen-emp','screen-ca','EMP','screen-emp@example.invalid','unused','active','2026-01-01')"))
  def client(did='screen-ca',employee=False):
   cl=a.app.test_client()
   with cl.session_transaction() as s:s.update(dealer_id=did,account_type='employee' if employee else 'owner',employee_id='screen-emp' if employee else '',auth_version=0)
   return cl
  def page(cl):
   r=cl.get('/qa/purchases');assert r.status_code==200,r.status_code;assert r.headers['Cache-Control']=='private, no-store';return r.get_data(as_text=True)
  def form(cl,action):return next(x for x in Forms(page(cl)).forms if x.get('action')==action)
  def bank(did='screen-ca'):return query('SELECT lookup_bonus,estimate_bonus FROM account_allowances WHERE dealer_id=?',(did,))[0]
  cl=client();before=bank();html=page(cl);assert 'SIMULATION MODE' in html and 'US$27.75' in html and 'US$2.75' in html
  assert bank()==before and not query('SELECT * FROM topup_order_terms');us=page(client('screen-us'));assert 'US$25.00' in us and 'No tax under the current US billing policy' in us
  assert client(employee=True).get('/qa/purchases').status_code==403
  assert a.app.test_client().get('/qa/purchases').status_code==302
  start=form(cl,'start');other_tab=form(cl,'start');assert cl.post('/qa/purchases',data={**start,'csrf':'wrong'}).status_code==403
  assert cl.post('/qa/purchases',data=start,headers={'Origin':'https://foreign.invalid'}).status_code==403
  cl.set_cookie('session',cl.get_cookie('session').value,domain='hosted.invalid')
  assert cl.post('/qa/purchases',data=start,headers={'Host':'hosted.invalid'}).status_code==404
  with patch.dict(os.environ,{'AERIQUOTE_QA_PURCHASES':'0'}):assert cl.get('/qa/purchases').status_code==404
  with patch.dict(os.environ,{'RENDER_SERVICE_ID':'fictional-hosted-id'}):assert cl.get('/qa/purchases').status_code==404
  # Same signed form concurrently, then refresh: one pending order and zero grants.
  with cl.session_transaction() as s:session_state=dict(s)
  def replay(data):
   other=client()
   with other.session_transaction() as s:s.clear();s.update(session_state)
   return other.post('/qa/purchases',data=data).status_code
  with ThreadPoolExecutor(max_workers=8) as pool:assert list(pool.map(lambda _:replay(start),range(8)))==[303]*8
  assert len(query('SELECT * FROM topup_order_terms'))==1 and bank()==before
  assert cl.post('/qa/purchases',data=other_tab).status_code==303
  assert len(query('SELECT * FROM topup_order_terms'))==1 and bank()==before
  for _ in range(3):page(cl)
  assert len(query('SELECT * FROM topup_order_terms'))==1 and bank()==before
  failed=form(cl,'failed');assert cl.post('/qa/purchases',data=failed).status_code==303;assert bank()==before
  retry=form(cl,'retry')
  with ThreadPoolExecutor(max_workers=8) as pool:assert list(pool.map(lambda _:replay(retry),range(8)))==[303]*8
  assert len(query('SELECT * FROM topup_attempts'))==2 and bank()==before
  success=form(cl,'succeeded')
  # Server failure after grant but before acknowledgment rolls the entire HTTP transaction back.
  original=a.DBCompat.execute
  def interrupted(db,sql,params=()):
   if sql.startswith('INSERT INTO topup_events'):raise RuntimeError('fictional interrupted acknowledgment')
   return original(db,sql,params)
  with patch.object(a.DBCompat,'execute',interrupted):assert cl.post('/qa/purchases',data=success).status_code==500
  assert bank()==before and not query('SELECT * FROM topup_fulfillments')
  with ThreadPoolExecutor(max_workers=8) as pool:assert list(pool.map(lambda _:replay(success),range(8)))==[303]*8
  assert bank()=={'lookup_bonus':28,'estimate_bonus':28} and len(query('SELECT * FROM topup_fulfillments'))==1
  for data in [start,retry,success,failed]:assert cl.post('/qa/purchases',data=data).status_code==303
  assert bank()=={'lookup_bonus':28,'estimate_bonus':28}
  assert 'Simulated success' in page(cl) and 'Purchased extras are held' in page(cl)
  assert client(employee=True).post('/qa/purchases',data=success).status_code==403
  foreign=client('screen-us');foreign_csrf=form(foreign,'start')['csrf'];assert foreign.post('/qa/purchases',data={**success,'csrf':foreign_csrf}).status_code==409
  assert foreign.post('/qa/purchases',data={**success,'csrf':foreign_csrf,'business':'screen-us'}).status_code==409
  assert 'Simulated success' not in page(foreign) and bank('screen-us')=={'lookup_bonus':3,'estimate_bonus':3}
  # Explicit current tax config required; changing tax between quote and POST fails closed.
  fresh=form(cl,'start')
  with patch.dict(os.environ,{'AERIQUOTE_QA_TOPUP_TAX_POLICY':json.dumps({'version':'changed','rates_bps':{'CA:SK':1200}})}):assert cl.post('/qa/purchases',data=fresh).status_code==409
  with patch.dict(os.environ,{'AERIQUOTE_QA_TOPUP_TAX_POLICY':'{}'}):assert 'No purchase can be started' in page(cl)
  with patch.dict(os.environ,{'AERIQUOTE_QA_TOPUP_TAX_POLICY':json.dumps({'version':'future-config-test','rates_bps':{'US':500}})}):
   text=page(foreign);assert 'Configured US tax.' in text and 'US$26.25' in text and 'No tax under the current US billing policy' not in text
  assert tx('screen-ca',lambda db:l.reconciliation(db,'screen-ca'))['balanced']
  # Active / held wording follows the same eligibility evidence used by actual spending.
  tx('screen-ca',lambda db:p.set_subscription(db,'screen-ca','active'));assert 'Your subscription is active.' in page(cl)
  tx('screen-ca',lambda db:p.set_subscription(db,'screen-ca','canceled'));assert 'Purchased extras are held' in page(cl) and bank()['lookup_bonus']==28
  print('PASS purchase GET is read-only; Canadian configurable tax/USzero; owner, employee, business, CSRF, origin and hosted/disposable guards')
  print('PASS HTTP pending/failure/retry/success; 8-way repeated starts/retries/confirmation; refresh and old form replay; exactly one pack and atomic interrupted-response rollback')
  print('PASS history and three source balances; subscription hold/active/canceled; no real money or hosted balance changes')
  print(json.dumps(dict(backend='postgres' if pg else 'sqlite',orders=len(query('SELECT * FROM topup_order_terms')),fulfillments=len(query('SELECT * FROM topup_fulfillments')),bank=bank(),real_money_moved=False)))
 finally:
  if schema:
   with psycopg.connect(raw,autocommit=True) as db:db.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
