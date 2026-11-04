"""Business-scoped source lots and append-only extra-allowance movements.

No HTTP/payment integration. Call mutations under account_credits.lock_account;
commit/rollback with the lookup/save/grant receipt in the caller's transaction.
"""
import hashlib,json,uuid,tempfile
from pathlib import Path
from datetime import datetime,timezone

CHANNELS={'lookups':'lookup_bonus','estimates':'estimate_bonus'}
class LedgerError(ValueError):pass

def init_db(con):
 con.execute("""CREATE TABLE IF NOT EXISTS extra_bank_openings (
 dealer_id TEXT PRIMARY KEY, lookup_units INTEGER NOT NULL CHECK(lookup_units>=0),
 estimate_units INTEGER NOT NULL CHECK(estimate_units>=0), created_at TEXT NOT NULL)""")
 con.execute("""CREATE TABLE IF NOT EXISTS extra_source_lots (
 dealer_id TEXT NOT NULL, lot_id TEXT NOT NULL, origin TEXT NOT NULL CHECK(origin IN ('granted','purchased')),
 source_ref TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(dealer_id,lot_id), UNIQUE(dealer_id,source_ref))""")
 con.execute("""CREATE TABLE IF NOT EXISTS extra_movements (
 dealer_id TEXT NOT NULL, entry_id TEXT NOT NULL, lot_id TEXT NOT NULL,
 channel TEXT NOT NULL CHECK(channel IN ('lookups','estimates')), delta INTEGER NOT NULL CHECK(delta<>0),
 reason TEXT NOT NULL CHECK(reason IN ('opening','grant','simulated_purchase','consume')),
 operation_ref TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(dealer_id,entry_id),
 FOREIGN KEY(dealer_id,lot_id) REFERENCES extra_source_lots(dealer_id,lot_id))""")
 con.execute('CREATE INDEX IF NOT EXISTS extra_movements_lot ON extra_movements(dealer_id,lot_id,channel)')
 con.execute("""CREATE TABLE IF NOT EXISTS extra_policies (
 dealer_id TEXT PRIMARY KEY, spend_order TEXT, purchase_eligibility TEXT, refund_policy TEXT)""")
 con.execute("""CREATE TABLE IF NOT EXISTS extra_simulated_orders (
 dealer_id TEXT NOT NULL, order_id TEXT NOT NULL, lot_id TEXT NOT NULL,
 quantity INTEGER NOT NULL CHECK(quantity=25), currency TEXT NOT NULL CHECK(currency='USD'),
 subtotal_cents INTEGER NOT NULL CHECK(subtotal_cents=2500), tax_cents INTEGER NOT NULL CHECK(tax_cents>=0),
 total_cents INTEGER NOT NULL CHECK(total_cents=subtotal_cents+tax_cents),
 tax_snapshot TEXT NOT NULL, payload_hash TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(dealer_id,order_id), UNIQUE(dealer_id,lot_id),
 FOREIGN KEY(dealer_id,lot_id) REFERENCES extra_source_lots(dealer_id,lot_id))""")

 # History tables are append-only even if a later caller accidentally issues SQL edits.
 tables=('extra_bank_openings','extra_source_lots','extra_movements','extra_simulated_orders')
 if con.postgres:
  con.execute("CREATE OR REPLACE FUNCTION reject_extra_history_edit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Extra allowance history is append-only'; END; $$")
  for table in tables:
   con.execute(f'CREATE OR REPLACE TRIGGER immutable_{table} BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION reject_extra_history_edit()')
 else:
  for table in tables:
   for action in ('UPDATE','DELETE'):
    con.execute(f"CREATE TRIGGER IF NOT EXISTS immutable_{table}_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'Extra allowance history is append-only'); END")

def stamp():return datetime.now(timezone.utc).isoformat()
def ref(value):
 if not isinstance(value,str) or not value or len(value)>256:raise LedgerError('Invalid extra allowance reference.')
 return value

def _bank(con,did):
 row=con.execute('SELECT lookup_bonus,estimate_bonus FROM account_allowances WHERE dealer_id=?',(did,)).fetchone()
 return {c:int(row[col]) if row else 0 for c,col in CHANNELS.items()}

def _entry(con,did,lot,channel,delta,reason,operation):
 if not con.execute('SELECT lot_id FROM extra_source_lots WHERE dealer_id=? AND lot_id=?',(did,lot)).fetchone():raise LedgerError('Extra lot belongs to another business or does not exist.')
 entry_id=uuid.uuid4().hex
 con.execute('INSERT INTO extra_movements(dealer_id,entry_id,lot_id,channel,delta,reason,operation_ref,created_at) VALUES(?,?,?,?,?,?,?,?)',(did,entry_id,lot,channel,delta,reason,operation,stamp()))
 return entry_id

def ensure_opening(con,did):
 """Snapshot remaining extras once; never infer purchases or rewrite old grants."""
 if con.execute('SELECT dealer_id FROM extra_bank_openings WHERE dealer_id=?',(did,)).fetchone():return
 if not con.execute('SELECT id FROM dealers WHERE id=?',(did,)).fetchone():raise LedgerError('Unknown business.')
 bank=_bank(con,did)
 if any(v<0 for v in bank.values()):raise LedgerError('Negative existing extra balance requires reconciliation.')
 con.execute('INSERT INTO extra_bank_openings(dealer_id,lookup_units,estimate_units,created_at) VALUES(?,?,?,?)',(did,bank['lookups'],bank['estimates'],stamp()))
 if any(bank.values()):
  lot=uuid.uuid4().hex
  con.execute("INSERT INTO extra_source_lots(dealer_id,lot_id,origin,source_ref,created_at) VALUES(?,?,'granted','legacy-opening-v1',?)",(did,lot,stamp()))
  for channel,units in bank.items():
   if units:_entry(con,did,lot,channel,units,'opening','legacy-opening-v1')

def reconciliation(con,did):
 """Read-only and independent of the mutable bank projection."""
 bank=_bank(con,did);totals={c:0 for c in CHANNELS};origins={k:{c:0 for c in CHANNELS} for k in ['granted','purchased']}
 for row in con.execute('SELECT l.origin,m.channel,SUM(m.delta) AS units FROM extra_movements m JOIN extra_source_lots l ON l.dealer_id=m.dealer_id AND l.lot_id=m.lot_id WHERE m.dealer_id=? GROUP BY l.origin,m.channel',(did,)).fetchall():
  units=int(row['units']);totals[row['channel']]+=units;origins[row['origin']][row['channel']]=units
 negative=con.execute('SELECT lot_id,channel FROM extra_movements WHERE dealer_id=? GROUP BY lot_id,channel HAVING SUM(delta)<0',(did,)).fetchall()
 opened=bool(con.execute('SELECT dealer_id FROM extra_bank_openings WHERE dealer_id=?',(did,)).fetchone())
 unbacked=[r['lot_id'] for r in con.execute("SELECT l.lot_id FROM extra_source_lots l WHERE l.dealer_id=? AND l.origin='purchased' AND NOT EXISTS(SELECT 1 FROM extra_simulated_orders o WHERE o.dealer_id=l.dealer_id AND o.lot_id=l.lot_id)",(did,)).fetchall()]
 return dict(opened=opened,bank=bank,ledger=totals,sources=origins,unbacked_purchases=unbacked,balanced=opened and bank==totals and not negative and not unbacked)

def _assert_balanced(con,did):
 if not reconciliation(con,did)['balanced']:raise LedgerError('Extra allowance ledger does not match its bank. Reconciliation required.')

def _grant(con,did,units,source_ref,origin,reason,created_at=None):
 if type(units) is not int or not 1<=units<=10000:raise LedgerError('Invalid extra units.')
 ref(source_ref);ensure_opening(con,did);_assert_balanced(con,did)
 old=con.execute('SELECT lot_id,origin FROM extra_source_lots WHERE dealer_id=? AND source_ref=?',(did,source_ref)).fetchone()
 if old:
  rows=con.execute("SELECT channel,SUM(delta) AS units FROM extra_movements WHERE dealer_id=? AND lot_id=? AND delta>0 GROUP BY channel",(did,old['lot_id'])).fetchall()
  if old['origin']!=origin or {r['channel']:int(r['units']) for r in rows}!={c:units for c in CHANNELS}:raise LedgerError('Extra grant reference reused with different details.')
  return old['lot_id'],False
 lot=uuid.uuid4().hex
 con.execute('INSERT INTO extra_source_lots(dealer_id,lot_id,origin,source_ref,created_at) VALUES(?,?,?,?,?)',(did,lot,origin,source_ref,created_at or stamp()))
 for channel in CHANNELS:_entry(con,did,lot,channel,units,reason,source_ref)
 con.execute('INSERT INTO account_allowances(dealer_id) VALUES(?) ON CONFLICT(dealer_id) DO NOTHING',(did,))
 con.execute('UPDATE account_allowances SET lookup_bonus=lookup_bonus+?,estimate_bonus=estimate_bonus+? WHERE dealer_id=?',(units,units,did))
 return lot,True

def grant_administrative(con,did,units,operation):return _grant(con,did,units,'admin:'+ref(operation),'granted','grant')

def _disposable(con):
 if con.postgres:
  if con.con.info.host not in ('localhost','127.0.0.1') or con.con.info.dbname!='aeriquote_qa':raise LedgerError('Simulation requires disposable loopback aeriquote_qa.')
 else:
  filename=con.execute('PRAGMA database_list').fetchone()['file']
  if filename and not Path(filename).resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()):raise LedgerError('Simulation requires temporary SQLite.')

def configure_simulation(con,did,*,spend_order=None,refund_policy=None,eligibility=None):
 """Disposable fixture configuration only; no approved production purchase policy."""
 _disposable(con)
 if spend_order not in (None,'granted_first','purchased_first','fifo'):raise LedgerError('Unknown spending policy.')
 if eligibility not in (None,'simulation_only'):raise LedgerError('Unapproved purchase eligibility.')
 con.execute('INSERT INTO extra_policies(dealer_id,spend_order,purchase_eligibility,refund_policy) VALUES(?,?,?,?) ON CONFLICT(dealer_id) DO UPDATE SET spend_order=excluded.spend_order,purchase_eligibility=excluded.purchase_eligibility,refund_policy=excluded.refund_policy',(did,spend_order,eligibility,json.dumps(refund_policy) if refund_policy is not None else None))

def fulfill_simulated_pack(con,did,order_id,*,country,region='',tax_policy,purchased_at=None):
 """No payment claim: explicit simulated order, unavailable on hosted/real DBs."""
 _disposable(con);ref(order_id)
 if not isinstance(tax_policy,dict) or not isinstance(tax_policy.get('rates_bps'),dict) or not tax_policy.get('version'):raise LedgerError('Versioned tax configuration required.')
 rates=tax_policy.get('rates_bps',{});key='CA:'+region if country=='CA' else country
 if country not in ('CA','US') or key not in rates:raise LedgerError('Configured tax jurisdiction required.')
 rate=rates[key]
 if type(rate) is not int or not 0<=rate<=10000:raise LedgerError('Invalid tax rate.')
 # Current US policy is zero; caller-provided versioned rules remain configurable.
 tax=(2500*rate+5000)//10000
 snapshot=json.dumps(dict(country=country,region=region,rule=tax_policy),sort_keys=True,separators=(',',':'))
 digest=hashlib.sha256(snapshot.encode()).hexdigest()
 old=con.execute('SELECT * FROM extra_simulated_orders WHERE dealer_id=? AND order_id=?',(did,order_id)).fetchone()
 if old:
  if old['payload_hash']!=digest:raise LedgerError('Simulated order reference reused with different details.')
  _assert_balanced(con,did);return dict(old),False
 lot,created=_grant(con,did,25,'simulated-purchase:'+order_id,'purchased','simulated_purchase',created_at=purchased_at)
 if not created:raise LedgerError('Simulated purchase lot lacks its order record.')
 con.execute("INSERT INTO extra_simulated_orders(dealer_id,order_id,lot_id,quantity,currency,subtotal_cents,tax_cents,total_cents,tax_snapshot,payload_hash,created_at) VALUES(?,?,?,25,'USD',2500,?,?,?,?,?)",(did,order_id,lot,tax,2500+tax,snapshot,digest,stamp()))
 _assert_balanced(con,did)
 return dict(con.execute('SELECT * FROM extra_simulated_orders WHERE dealer_id=? AND order_id=?',(did,order_id)).fetchone()),True

def deduct_extra(con,did,channel,operation=None):
 """Monthly eligibility is checked by consume before reaching this function."""
 if channel not in CHANNELS:raise LedgerError('Unknown allowance channel.')
 ensure_opening(con,did);_assert_balanced(con,did)
 policy=con.execute('SELECT * FROM extra_policies WHERE dealer_id=?',(did,)).fetchone()
 candidates=[]
 for row in con.execute('SELECT l.lot_id,l.origin,l.created_at,SUM(m.delta) AS units FROM extra_source_lots l JOIN extra_movements m ON m.dealer_id=l.dealer_id AND m.lot_id=l.lot_id WHERE l.dealer_id=? AND m.channel=? GROUP BY l.lot_id,l.origin,l.created_at HAVING SUM(m.delta)>0 ORDER BY l.created_at,l.lot_id',(did,channel)).fetchall():
  if row['origin']=='purchased':
   if policy and policy['purchase_eligibility']=='simulation_only':_disposable(con)
   else:
    dealer=con.execute('SELECT status,plan_code FROM dealers WHERE id=?',(did,)).fetchone()
    cfg=con.execute('SELECT complimentary FROM account_allowances WHERE dealer_id=?',(did,)).fetchone()
    subscription=con.execute('SELECT status FROM extra_subscription_state WHERE dealer_id=?',(did,)).fetchone()
    from account_credits import SUBSCRIPTION_LIMITS
    if not dealer or dealer['status']!='active' or not ((cfg and cfg['complimentary']) or (dealer['plan_code'] in SUBSCRIPTION_LIMITS and subscription and subscription['status']=='active')):continue
  candidates.append(row)
 if not candidates:return False
 origins={r['origin'] for r in candidates}
 legacy_fixture=policy and policy['purchase_eligibility']=='simulation_only'
 order=policy['spend_order'] if legacy_fixture else 'granted_first'
 if len(origins)>1 and not order:return False # legacy counterfactual fixture only
 if order in ('granted_first','purchased_first'):
  first='granted' if order=='granted_first' else 'purchased';candidates.sort(key=lambda r:r['origin']!=first)
 chosen=candidates[0];operation=ref(operation) if operation else 'unkeyed:'+uuid.uuid4().hex
 _entry(con,did,chosen['lot_id'],channel,-1,'consume',operation)
 col=CHANNELS[channel]
 con.execute(f'UPDATE account_allowances SET {col}={col}-1 WHERE dealer_id=?',(did,))
 _assert_balanced(con,did);return True
