"""Disposable order/event/refund-decision simulator. No HTTP, gateway or money movement."""
import hashlib,json,uuid
import extra_allowance_ledger as l
import allowance_writer_guard as fence

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'))
def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()
def init_db(con):
 con.execute("CREATE TABLE IF NOT EXISTS extra_subscription_state (dealer_id TEXT PRIMARY KEY,status TEXT NOT NULL CHECK(status IN ('active','canceled','inactive')))")
 con.execute("""CREATE TABLE IF NOT EXISTS topup_order_terms (
 dealer_id TEXT NOT NULL,order_id TEXT NOT NULL,owner_id TEXT NOT NULL,terms_hash TEXT NOT NULL,
 country TEXT NOT NULL,region TEXT NOT NULL,tax_policy TEXT NOT NULL,currency TEXT NOT NULL,quantity INTEGER NOT NULL DEFAULT 25 CHECK(quantity=25),estimates_included INTEGER NOT NULL DEFAULT 1 CHECK(estimates_included=1),
 subtotal_cents INTEGER NOT NULL,tax_cents INTEGER NOT NULL,total_cents INTEGER NOT NULL,
 created_at TEXT NOT NULL,PRIMARY KEY(dealer_id,order_id))""")
 con.execute("CREATE TABLE IF NOT EXISTS topup_order_state (dealer_id TEXT NOT NULL,order_id TEXT NOT NULL,state TEXT NOT NULL,PRIMARY KEY(dealer_id,order_id))")
 con.execute("CREATE TABLE IF NOT EXISTS topup_attempts (dealer_id TEXT NOT NULL,attempt_id TEXT NOT NULL,order_id TEXT NOT NULL,state TEXT NOT NULL,PRIMARY KEY(dealer_id,attempt_id))")
 con.execute("CREATE TABLE IF NOT EXISTS topup_events (dealer_id TEXT NOT NULL,event_id TEXT NOT NULL,payload_hash TEXT NOT NULL,payload_json TEXT NOT NULL,result_json TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(dealer_id,event_id))")
 con.execute("CREATE TABLE IF NOT EXISTS topup_fulfillments (dealer_id TEXT NOT NULL,order_id TEXT NOT NULL,attempt_id TEXT NOT NULL,lot_id TEXT NOT NULL,PRIMARY KEY(dealer_id,order_id),UNIQUE(dealer_id,lot_id))")
 con.execute("CREATE TABLE IF NOT EXISTS topup_review_flags (dealer_id TEXT NOT NULL,order_id TEXT NOT NULL,attempt_id TEXT NOT NULL,reason TEXT NOT NULL,PRIMARY KEY(dealer_id,order_id,attempt_id))")
 con.execute("""CREATE TABLE IF NOT EXISTS topup_refund_decisions (
 dealer_id TEXT NOT NULL,decision_id TEXT NOT NULL,order_id TEXT NOT NULL,reviewer_id TEXT NOT NULL,
 units INTEGER NOT NULL,approved INTEGER NOT NULL,reason TEXT NOT NULL,payload_hash TEXT NOT NULL,
 subtotal_cents INTEGER NOT NULL,tax_cents INTEGER NOT NULL,total_cents INTEGER NOT NULL,created_at TEXT NOT NULL,
 PRIMARY KEY(dealer_id,decision_id))""")
 con.execute("""CREATE TABLE IF NOT EXISTS topup_refund_revocations (
 dealer_id TEXT NOT NULL,decision_id TEXT NOT NULL,channel TEXT NOT NULL,lot_id TEXT NOT NULL,
 entry_id TEXT NOT NULL,units INTEGER NOT NULL CHECK(units>0),PRIMARY KEY(dealer_id,decision_id,channel),
 FOREIGN KEY(dealer_id,entry_id) REFERENCES extra_movements(dealer_id,entry_id))""")
 for table in ('topup_order_terms','topup_events','topup_fulfillments','topup_review_flags','topup_refund_decisions','topup_refund_revocations'):
  if con.postgres:con.execute(f'CREATE OR REPLACE TRIGGER immutable_{table} BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION reject_extra_history_edit()')
  else:
   for action in ('UPDATE','DELETE'):con.execute(f"CREATE TRIGGER IF NOT EXISTS immutable_{table}_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'Order history is append-only'); END")

def ready(con):l._disposable(con);fence.assert_writable(con)
def owner(con,did,actor):
 row=con.execute('SELECT status FROM dealers WHERE id=?',(did,)).fetchone()
 if actor!=did or not row or row['status']!='active':raise l.LedgerError('Active business owner required to purchase.')
def terms(con,did,order):
 row=con.execute('SELECT * FROM topup_order_terms WHERE dealer_id=? AND order_id=?',(did,order)).fetchone()
 if not row:raise l.LedgerError('Order does not belong to this business.')
 return dict(row)
def remaining(con,did,lot):
 return {c:int(con.execute('SELECT COALESCE(SUM(delta),0) AS n FROM extra_movements WHERE dealer_id=? AND lot_id=? AND channel=?',(did,lot,c)).fetchone()['n']) for c in l.CHANNELS}
def approved_units(con,did,order):return int(con.execute('SELECT COALESCE(SUM(units),0) AS n FROM topup_refund_decisions WHERE dealer_id=? AND order_id=? AND approved=1',(did,order)).fetchone()['n'])
def set_subscription(con,did,status):
 ready(con)
 if status not in ('active','canceled','inactive'):raise l.LedgerError('Invalid subscription status.')
 con.execute('INSERT INTO extra_subscription_state(dealer_id,status) VALUES(?,?) ON CONFLICT(dealer_id) DO UPDATE SET status=excluded.status',(did,status))
def create_order(con,did,actor,order,*,country,region='',tax_policy):
 ready(con);owner(con,did,actor);l.ref(order)
 # Same integer half-up and versioned tax snapshot as stage1; no grant yet.
 if not isinstance(tax_policy,dict) or not isinstance(tax_policy.get('rates_bps'),dict):raise l.LedgerError('Versioned tax configuration required.')
 rates=tax_policy.get('rates_bps',{});key='CA:'+region if country=='CA' else country
 if not tax_policy.get('version') or country not in ('CA','US') or key not in rates:raise l.LedgerError('Configured tax jurisdiction required.')
 rate=rates[key]
 if type(rate) is not int or not 0<=rate<=10000:raise l.LedgerError('Invalid tax rate.')
 body=dict(quantity=25,estimates_included=True,country=country,region=region,tax_policy=tax_policy,currency='USD',subtotal_cents=2500,tax_cents=(2500*rate+5000)//10000)
 body['total_cents']=2500+body['tax_cents'];hash=digest(body)
 old=con.execute('SELECT * FROM topup_order_terms WHERE dealer_id=? AND order_id=?',(did,order)).fetchone()
 if old:
  if old['terms_hash']!=hash:raise l.LedgerError('Order identifier reused with different terms.')
  return dict(old)
 con.execute('INSERT INTO topup_order_terms(dealer_id,order_id,owner_id,terms_hash,country,region,tax_policy,currency,subtotal_cents,tax_cents,total_cents,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(did,order,actor,hash,country,region,canonical(tax_policy),'USD',2500,body['tax_cents'],body['total_cents'],l.stamp()))
 con.execute("INSERT INTO topup_order_state(dealer_id,order_id,state) VALUES(?,?,'pending')",(did,order))
 return terms(con,did,order)
def start_attempt(con,did,actor,order,attempt):
 ready(con);owner(con,did,actor);terms(con,did,order);l.ref(attempt)
 old=con.execute('SELECT * FROM topup_attempts WHERE dealer_id=? AND attempt_id=?',(did,attempt)).fetchone()
 if old:
  if old['order_id']!=order:raise l.LedgerError('Attempt already belongs to another order.')
  return dict(old)
 if con.execute('SELECT order_id FROM topup_fulfillments WHERE dealer_id=? AND order_id=?',(did,order)).fetchone():raise l.LedgerError('Order already fulfilled; do not start another attempt.')
 con.execute("INSERT INTO topup_attempts(dealer_id,attempt_id,order_id,state) VALUES(?,?,?,'pending')",(did,attempt,order))
 con.execute("UPDATE topup_order_state SET state='pending' WHERE dealer_id=? AND order_id=?",(did,order))
 return dict(attempt_id=attempt,order_id=order,state='pending')
def _apply_refunds(con,did,order,lot):
 for d in con.execute('SELECT * FROM topup_refund_decisions WHERE dealer_id=? AND order_id=? AND approved=1 ORDER BY created_at,decision_id',(did,order)).fetchall():
  count=con.execute('SELECT COUNT(*) AS n FROM topup_refund_revocations WHERE dealer_id=? AND decision_id=?',(did,d['decision_id'])).fetchone()['n']
  if count==2:continue
  if count:raise l.LedgerError('Partial refund application requires reconciliation.')
  if min(remaining(con,did,lot).values())<d['units']:raise l.LedgerError('Refund exceeds attributable unused purchased units.')
  for channel in l.CHANNELS:
   # Legacy negative-movement bucket remains compatible; typed link identifies refund, not usage.
   entry=l._entry(con,did,lot,channel,-int(d['units']),'consume','manual-refund:'+d['decision_id'])
   con.execute('INSERT INTO topup_refund_revocations(dealer_id,decision_id,channel,lot_id,entry_id,units) VALUES(?,?,?,?,?,?)',(did,d['decision_id'],channel,lot,entry,d['units']))
  con.execute('UPDATE account_allowances SET lookup_bonus=lookup_bonus-?,estimate_bonus=estimate_bonus-? WHERE dealer_id=?',(d['units'],d['units'],did))
 l._assert_balanced(con,did)
def process_event(con,did,event,order,attempt,status,*,currency,total_cents):
 ready(con);l.ref(event);t=terms(con,did,order)
 if status not in ('pending','failed','succeeded') or currency!=t['currency'] or type(total_cents) is not int or total_cents!=t['total_cents']:raise l.LedgerError('Notification does not match immutable order terms.')
 a=con.execute('SELECT * FROM topup_attempts WHERE dealer_id=? AND attempt_id=?',(did,attempt)).fetchone()
 if not a or a['order_id']!=order:raise l.LedgerError('Unknown or cross-order attempt.')
 body=dict(order=order,attempt=attempt,status=status,currency=currency,total_cents=total_cents);hash=digest(body)
 old=con.execute('SELECT payload_hash,result_json FROM topup_events WHERE dealer_id=? AND event_id=?',(did,event)).fetchone()
 if old:
  if old['payload_hash']!=hash:raise l.LedgerError('Notification identifier reused with different data.')
  return json.loads(old['result_json'])
 rank={'pending':0,'failed':1,'succeeded':2}
 if rank[status]>rank[a['state']]:con.execute('UPDATE topup_attempts SET state=? WHERE dealer_id=? AND attempt_id=?',(status,did,attempt))
 f=con.execute('SELECT * FROM topup_fulfillments WHERE dealer_id=? AND order_id=?',(did,order)).fetchone()
 if status=='succeeded':
  if not f:
   granted,_=l.fulfill_simulated_pack(con,did,'events:'+order,country=t['country'],region=t['region'],tax_policy=json.loads(t['tax_policy']),purchased_at=t['created_at'])
   con.execute('INSERT INTO topup_fulfillments(dealer_id,order_id,attempt_id,lot_id) VALUES(?,?,?,?)',(did,order,attempt,granted['lot_id']))
   _apply_refunds(con,did,order,granted['lot_id'])
  elif f['attempt_id']!=attempt:
   con.execute("INSERT INTO topup_review_flags(dealer_id,order_id,attempt_id,reason) VALUES(?,?,?,'second_success_manual_review') ON CONFLICT(dealer_id,order_id,attempt_id) DO NOTHING",(did,order,attempt))
 fulfilled=bool(con.execute('SELECT order_id FROM topup_fulfillments WHERE dealer_id=? AND order_id=?',(did,order)).fetchone())
 waiting=con.execute("SELECT COUNT(*) AS n FROM topup_attempts WHERE dealer_id=? AND order_id=? AND state='pending'",(did,order)).fetchone()['n']
 current='refunded_simulation' if fulfilled and approved_units(con,did,order)==25 else 'fulfilled' if fulfilled else 'pending' if waiting else 'failed'
 con.execute('UPDATE topup_order_state SET state=? WHERE dealer_id=? AND order_id=?',(current,did,order))
 result=dict(order_id=order,state=current,fulfilled=fulfilled,review_required=bool(con.execute('SELECT order_id FROM topup_review_flags WHERE dealer_id=? AND order_id=?',(did,order)).fetchone()))
 con.execute('INSERT INTO topup_events(dealer_id,event_id,payload_hash,payload_json,result_json,created_at) VALUES(?,?,?,?,?,?)',(did,event,hash,canonical(body),canonical(result),l.stamp()))
 return result

def review_refund(con,did,reviewer,decision,order,units,*,approved,reason):
 ready(con);l.ref(decision);t=terms(con,did,order)
 admin=con.execute("SELECT r.dealer_id FROM account_admin_roles r JOIN dealers d ON d.id=r.dealer_id WHERE r.dealer_id=? AND d.status='active'",(reviewer,)).fetchone()
 if not admin:raise l.LedgerError('Active manual-review administrator required.')
 if type(units) is not int or not 1<=units<=25 or type(approved) is not bool or not isinstance(reason,str) or not reason.strip():raise l.LedgerError('Explicit manual decision, units and reason required.')
 body=dict(order=order,reviewer=reviewer,units=units,approved=approved,reason=reason);hash=digest(body)
 old=con.execute('SELECT * FROM topup_refund_decisions WHERE dealer_id=? AND decision_id=?',(did,decision)).fetchone()
 if old:
  if old['payload_hash']!=hash:raise l.LedgerError('Refund decision identifier reused with different data.')
  return dict(old)
 before=approved_units(con,did,order);f=con.execute('SELECT lot_id FROM topup_fulfillments WHERE dealer_id=? AND order_id=?',(did,order)).fetchone()
 if approved and (before+units>25 or (f and min(remaining(con,did,f['lot_id']).values())<units)):raise l.LedgerError('Manual refund exceeds attributable unused units.')
 subtotal=units*100 if approved else 0
 previous_tax=int(con.execute('SELECT COALESCE(SUM(tax_cents),0) AS n FROM topup_refund_decisions WHERE dealer_id=? AND order_id=? AND approved=1',(did,order)).fetchone()['n'])
 tax=((t['tax_cents']*(before+units)+12)//25-previous_tax) if approved else 0
 con.execute('INSERT INTO topup_refund_decisions(dealer_id,decision_id,order_id,reviewer_id,units,approved,reason,payload_hash,subtotal_cents,tax_cents,total_cents,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(did,decision,order,reviewer,units,int(approved),reason,hash,subtotal,tax,subtotal+tax,l.stamp()))
 if approved and f:
  _apply_refunds(con,did,order,f['lot_id'])
  if before+units==25:con.execute("UPDATE topup_order_state SET state='refunded_simulation' WHERE dealer_id=? AND order_id=?",(did,order))
 return dict(con.execute('SELECT * FROM topup_refund_decisions WHERE dealer_id=? AND decision_id=?',(did,decision)).fetchone())
