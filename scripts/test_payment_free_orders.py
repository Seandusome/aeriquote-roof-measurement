"""Orders/events/manual decisions and controlled writer cutover; disposable only."""
import os,sys,tempfile,uuid,json,copy,subprocess
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit,urlencode,parse_qsl
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as td:
 pg='--postgres' in sys.argv;url=os.environ.get('QA_POSTGRES_URL','') if pg else '';schema=None
 if pg:
  import psycopg
  from psycopg import sql
  u=urlsplit(url);assert u.hostname in ('localhost','127.0.0.1') and u.path=='/aeriquote_qa'
  schema='events_'+uuid.uuid4().hex
  with psycopg.connect(url,autocommit=True) as db:db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
  args=dict(parse_qsl(u.query));args['options']='-csearch_path='+schema
  url=urlunsplit(u._replace(query=urlencode(args)))
 os.environ['DATABASE_URL']=url;os.environ['ESTIMATE_DB_PATH']=td+'/events.db';os.environ.pop('RENDER_SERVICE_ID',None);os.environ.pop('RENDER_EXTERNAL_HOSTNAME',None)
 import app as a,account_credits as c,extra_allowance_ledger as l,payment_free_orders as p,allowance_writer_guard as g
 from qa_estimate_fixture import price_fixture
 from measurement_integrity import polygon_sqft
 a.is_head_office=lambda:False;a.is_recovery_test_service=lambda:False
 try:
  def owner(name,plan='basic',comp=False):
   did=name;db=a.estimate_db();db.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,status,created_at,plan_code,lookup_limit,estimate_limit) VALUES(?,?,?,'unused','active','2026-01-01',?,0,0)",(did,'FICTIONAL EVENT QA',did+'@example.invalid',plan));db.execute('INSERT INTO account_allowances(dealer_id,complimentary) VALUES(?,?)',(did,int(comp)));db.commit();db.close();return did
  def tx(did,fn,commit=True):
   db=a.estimate_db()
   try:
    c.lock_account(db,did);value=fn(db)
    if commit:db.commit()
    return value
   finally:db.close()
  def op(fn):
   db=a.estimate_db()
   try:
    if not pg:db.execute('BEGIN IMMEDIATE')
    value=fn(db);db.commit();return value
   finally:db.close()
  def query(sql,params=()):
   db=a.estimate_db()
   try:return [dict(r) for r in db.execute(sql,params).fetchall()]
   finally:db.close()
  def balance(did):
   db=a.estimate_db()
   try:return l.reconciliation(db,did)
   finally:db.close()
  def rejected(fn):
   try:fn()
   except Exception as e:
    if isinstance(e,AssertionError):raise
    return
   raise AssertionError('Expected guarded rejection')
  tax={'version':'fictional-us-ca','rates_bps':{'US':0,'CA:SK':1100,'CA:ROUND':2}}
  did=owner('events-owner');other=owner('events-other');office=owner('events-reviewer');comp=owner('events-comp',plan='trial',comp=True)
  tx(office,lambda db:db.execute('INSERT INTO account_admin_roles(dealer_id) VALUES(?)',(office,)))
  eid='events-employee';tx(did,lambda db:db.execute("INSERT INTO dealer_employees(id,dealer_id,employee_name,email,password_hash,status,created_at) VALUES(?,?,?,?,'unused','active','2026-01-01')",(eid,did,'FICTIONAL EMPLOYEE',eid+'@example.invalid')))
  def create(who,key,**kw):return tx(who,lambda db:p.create_order(db,who,who,key,country=kw.get('country','US'),region=kw.get('region',''),tax_policy=tax))
  def attempt(who,key,ref):return tx(who,lambda db:p.start_attempt(db,who,who,key,ref))
  def event(who,ev,key,ref,status,**kw):
   t=query('SELECT * FROM topup_order_terms WHERE dealer_id=? AND order_id=?',(who,key))[0]
   return tx(who,lambda db:p.process_event(db,who,ev,key,ref,status,currency=kw.get('currency','USD'),total_cents=kw.get('total_cents',t['total_cents'])))
  def refund(who,decision,key,units,approved=True,reviewer=office):return tx(who,lambda db:p.review_refund(db,who,reviewer,decision,key,units,approved=approved,reason='FICTIONAL manual review only'))
  def exhaust(who,kind='lookups'):
   # Seed an exhausted real current billing period without changing extra balances.
   def seed(db):
    period=c.paid_usage(db,who,initialize=True)
    if period:db.execute('UPDATE account_subscription_usage SET '+kind+'=25 WHERE dealer_id=? AND period_start=?',(who,period['start']))
    else:
     db.execute('INSERT INTO account_month_usage(dealer_id,period,lookups,estimates) VALUES(?,?,200,200) ON CONFLICT(dealer_id,period) DO UPDATE SET lookups=200,estimates=200',(who,c.month_key()))
   tx(who,seed)
  def use(who,kind='lookups'):return tx(who,lambda db:c.consume(db,who,kind,0,0))
  # Order ownership, immutable terms, failures, retry and notification idempotency.
  t=create(did,'one');assert (t['currency'],t['subtotal_cents'],t['tax_cents'],t['total_cents'])==('USD',2500,0,2500)
  rejected(lambda:tx(did,lambda db:p.create_order(db,did,eid,'employee-buy',country='US',tax_policy=tax)))
  attempt(did,'one','failed-attempt');event(did,'failed-1','one','failed-attempt','failed');assert query('SELECT state FROM topup_order_state WHERE dealer_id=? AND order_id=?',(did,'one'))[0]['state']=='failed'
  event(did,'late-pending','one','failed-attempt','pending');assert query('SELECT state FROM topup_attempts WHERE dealer_id=? AND attempt_id=?',(did,'failed-attempt'))[0]['state']=='failed'
  attempt(did,'one','retry-attempt')
  with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(lambda _:event(did,'same-success','one','retry-attempt','succeeded'),range(8)))
  assert all(r==results[0] for r in results);assert balance(did)['bank']=={'lookups':25,'estimates':25}
  for i in range(4):event(did,'same-payment-new-event-'+str(i),'one','retry-attempt','succeeded')
  event(did,'late-failure','one','retry-attempt','failed');event(did,'late-pending-after-success','one','retry-attempt','pending')
  assert query('SELECT state FROM topup_order_state WHERE dealer_id=? AND order_id=?',(did,'one'))[0]['state']=='fulfilled'
  assert len(query('SELECT * FROM topup_fulfillments WHERE dealer_id=?',(did,)))==1
  rejected(lambda:event(did,'same-success','one','retry-attempt','failed'))
  rejected(lambda:event(did,'wrong-money','one','retry-attempt','succeeded',total_cents=2501))
  rejected(lambda:event(did,'wrong-currency','one','retry-attempt','succeeded',currency='CAD'))
  rejected(lambda:tx(other,lambda db:p.process_event(db,other,'cross','one','retry-attempt','succeeded',currency='USD',total_cents=2500)))
  print('PASS owner-only orders, immutable USD/tax terms, failed/retried attempts, duplicate/concurrent notifications, out-of-order pending/failure, cross-business isolation')
  # Two separately successful attempts require review, never a second fulfillment.
  create(did,'double');attempt(did,'double','a');attempt(did,'double','b');event(did,'double-a','double','a','succeeded');r=event(did,'double-b','double','b','succeeded');assert r['review_required']
  assert len(query('SELECT * FROM topup_fulfillments WHERE dealer_id=? AND order_id=?',(did,'double')))==1
  assert len(query('SELECT * FROM topup_review_flags WHERE dealer_id=? AND order_id=?',(did,'double')))==1
  before=balance(did);create(did,'rollback');attempt(did,'rollback','rollback-attempt')
  original=a.DBCompat.execute
  def fail(db,sql,params=()):
   if sql.startswith('INSERT INTO topup_events'):raise RuntimeError('FICTIONAL event acknowledgement interrupted')
   return original(db,sql,params)
  with patch.object(a.DBCompat,'execute',fail):rejected(lambda:event(did,'rollback-event','rollback','rollback-attempt','succeeded'))
  assert balance(did)==before and not query('SELECT * FROM topup_fulfillments WHERE dealer_id=? AND order_id=?',(did,'rollback'))
  event(did,'rollback-event','rollback','rollback-attempt','succeeded');event(did,'rollback-event','rollback','rollback-attempt','succeeded')
  assert balance(did)['bank']['lookups']==before['bank']['lookups']+25
  create(did,'early-notification')
  rejected(lambda:event(did,'early-notice','early-notification','not-yet-registered','succeeded'))
  assert not query('SELECT * FROM topup_events WHERE dealer_id=? AND event_id=?',(did,'early-notice'))
  attempt(did,'early-notification','not-yet-registered')
  event(did,'early-notice','early-notification','not-yet-registered','succeeded')
  event(did,'early-notice','early-notification','not-yet-registered','succeeded')
  print('PASS second successful attempt flagged for manual review, rollback after fulfillment leaves no partial event/lot/bank, retry fulfills once')
  # Approved spending order and explicit active subscription requirement.
  tx(did,lambda db:l.grant_administrative(db,did,2,'admin-two'));exhaust(did)
  assert use(did)[0] and use(did)[0] # granted units remain usable without purchased eligibility
  assert not use(did)[0];held=balance(did)
  tx(did,lambda db:p.set_subscription(db,did,'active'));assert use(did)[0]
  tx(did,lambda db:p.set_subscription(db,did,'canceled'));before=balance(did);assert not use(did)[0] and balance(did)==before
  tx(did,lambda db:p.set_subscription(db,did,'active'));assert use(did)[0]
  assert balance(did)['sources']['purchased']['lookups']==held['sources']['purchased']['lookups']-2
  # Purchase chronology must not be replaced by notification arrival order.
  fifo=owner('fifo-owner');old=create(fifo,'older');new=create(fifo,'newer');attempt(fifo,'older','old-a');attempt(fifo,'newer','new-a');event(fifo,'new-paid','newer','new-a','succeeded');event(fifo,'old-paid','older','old-a','succeeded')
  tx(fifo,lambda db:p.set_subscription(db,fifo,'active'));exhaust(fifo);assert use(fifo)[0]
  old_lot=query('SELECT lot_id FROM topup_fulfillments WHERE dealer_id=? AND order_id=?',(fifo,'older'))[0]['lot_id']
  assert tx(fifo,lambda db:p.remaining(db,fifo,old_lot))['lookups']==24
  create(comp,'comp');attempt(comp,'comp','comp-a');event(comp,'comp-paid','comp','comp-a','succeeded');exhaust(comp);assert use(comp)[0]
  print('PASS monthly then granted then purchased FIFO, reversed notification arrival, active paid/complimentary eligibility, cancellation holds units and reactivation restores use')
  # Manual-only unused attributable refunds, including notification before funding.
  create(other,'full-before');attempt(other,'full-before','f');refund(other,'pending-refund','full-before',25)
  event(other,'after-refund','full-before','f','succeeded');assert balance(other)['bank']=={'lookups':0,'estimates':0}
  event(other,'replayed-payment','full-before','f','succeeded');assert balance(other)['bank']['lookups']==0
  rr=create(other,'rounding',country='CA',region='ROUND');assert rr['tax_cents']==1
  attempt(other,'rounding','r');event(other,'round-paid','rounding','r','succeeded')
  rejected(lambda:refund(other,'self-review','rounding',1,reviewer=other))
  refund(other,'denied','rounding',25,False);assert balance(other)['bank']['lookups']==25
  x=refund(other,'partial-12','rounding',12);assert x['tax_cents']==0
  assert refund(other,'partial-12','rounding',12)==x
  y=refund(other,'partial-13','rounding',13);assert y['tax_cents']==1 and x['total_cents']+y['total_cents']==rr['total_cents']
  rejected(lambda:refund(other,'too-much','rounding',1))
  # Consumed purchased units cannot be refunded from other lots or admin grants.
  lot=query('SELECT lot_id FROM topup_fulfillments WHERE dealer_id=? AND order_id=?',(fifo,'older'))[0]['lot_id']
  rejected(lambda:refund(fifo,'spent','older',25));refund(fifo,'unused','older',24)
  assert tx(fifo,lambda db:p.remaining(db,fifo,lot))['lookups']==0
  assert all(balance(w)['balanced'] for w in [did,other,fifo,comp])
  print('PASS manual reviewer authorization, decline, attributable unused-unit bounds, duplicate decisions, refund-before-fulfillment, partial tax rounding, no resurrection or money movement')
  # Cutover pauses all financial writers; database fence rejects old projection-only SQL.
  op(lambda db:g.set_mode(db,'legacy','paused'))
  before=balance(did);rejected(lambda:event(did,'paused','one','retry-attempt','succeeded'));assert balance(did)==before
  cl=a.app.test_client()
  with cl.session_transaction() as s:s.update(dealer_id=did,account_type='owner',auth_version=0)
  assert cl.post('/api/estimates',json={}).status_code==503
  assert a.app.test_client().post('/api/estimates',json={}).status_code==401
  assert cl.get('/api/estimates').status_code==200
  op(lambda db:g.set_mode(db,'paused','ledger'))
  # Run the actual pre-ledger application in a separate process, not just mock SQL.
  old_dir=Path(td)/'actual-older-app';old_dir.mkdir()
  baseline=os.environ.get('QA_OLD_WRITER_REF','194c435b377dbcb23ad24a422c63763fcd931ed4')
  assert subprocess.check_output(['git','rev-parse',baseline+':app.py'],cwd=root,text=True).strip()=='661a1f0b514e04c0a7b3b67945b7ec588ea449fe','Pinned deployed baseline app must match verified194c435b'
  for name in subprocess.check_output(['git','ls-tree','--name-only',baseline],cwd=root,text=True).splitlines():
   if name.endswith('.py'):(old_dir/name).write_bytes(subprocess.check_output(['git','show',baseline+':'+name],cwd=root))
  probe='''import app,json,sys,uuid
c=app.app.test_client()
with c.session_transaction() as s:s.update(dealer_id=sys.argv[1],account_type='owner',auth_version=0)
r=c.get('/head-office/credits?q='+sys.argv[2]+'@example.invalid');assert r.status_code==200,r.status_code
with c.session_transaction() as s:csrf=s['credit_csrf']
r=c.post('/head-office/credits',data=dict(csrf=csrf,operation=str(uuid.uuid4()),dealer_id=sys.argv[2],action='grant',amount='25',reason='FICTIONAL old writer probe'))
assert r.status_code==500,r.status_code
assert c.get('/api/estimates').status_code==200
print(json.dumps(dict(actual_old_read=200,actual_old_write=r.status_code,guarded=True)))
'''
  env=dict(os.environ,PYTHONPATH=str(old_dir))
  old_result=subprocess.check_output([sys.executable,'-c',probe,office,did],cwd=old_dir,env=env,text=True)
  assert any(json.loads(line).get('guarded') for line in old_result.splitlines() if line.startswith('{'))
  assert balance(did)==before,'Actual old application must not change the fenced bank or ledger'
  rejected(lambda:tx(did,lambda db:db.execute('UPDATE account_allowances SET lookup_bonus=lookup_bonus+1 WHERE dealer_id=?',(did,))))
  assert balance(did)==before
  tx(did,lambda db:l.grant_administrative(db,did,1,'fenced-new-grant'));assert balance(did)['balanced']
  rejected(lambda:op(lambda db:g.set_mode(db,'ledger','legacy')))
  op(lambda db:g.set_mode(db,'ledger','paused'));assert cl.get('/api/estimates').status_code==200
  subprocess.check_output([sys.executable,'-c',probe,office,did],cwd=old_dir,env=env,text=True)
  assert balance(did)['balanced']
  op(lambda db:g.set_mode(db,'paused','ledger'))
  print('PASS controlled pause/drain/cutover, authenticated maintenance503 with reads available, actual old194c435b reader works/writer rejected in ledger and paused modes, compatible writer succeeds, paused rollback/resume and no unfenced downgrade')
  print(json.dumps({'backend':'postgres' if pg else 'sqlite','balances_reconcile':all(balance(w)['balanced'] for w in [did,other,fifo,comp]),'real_money_moved':False,'writer_mode':query('SELECT mode FROM allowance_writer_control')[0]['mode']},sort_keys=True))
 finally:
  if schema:
   with psycopg.connect(os.environ['QA_POSTGRES_URL'],autocommit=True) as db:db.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
