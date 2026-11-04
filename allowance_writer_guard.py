"""Database-enforced allowance writer fence; no deployment or hosted activation."""

def init_db(con):
 con.execute("CREATE TABLE IF NOT EXISTS allowance_writer_control (id INTEGER PRIMARY KEY CHECK(id=1), mode TEXT NOT NULL CHECK(mode IN ('legacy','paused','ledger')), epoch INTEGER NOT NULL DEFAULT 0)")
 con.execute("INSERT INTO allowance_writer_control(id,mode,epoch) VALUES(1,'legacy',0) ON CONFLICT(id) DO NOTHING")
 tables=('account_allowances','account_subscription_usage','account_month_usage','dealer_usage','estimates','estimate_revisions','estimate_save_receipts')
 if con.postgres:
  con.execute("""CREATE OR REPLACE FUNCTION allowance_pause_guard() RETURNS trigger LANGUAGE plpgsql AS $$
  BEGIN IF (SELECT mode FROM allowance_writer_control WHERE id=1)='paused' THEN RAISE EXCEPTION 'Allowance writers are paused'; END IF; IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF; END; $$""")
  for table in tables:con.execute(f'CREATE OR REPLACE TRIGGER paused_{table} BEFORE INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION allowance_pause_guard()')
  con.execute("""CREATE OR REPLACE FUNCTION allowance_bank_guard() RETURNS trigger LANGUAGE plpgsql AS $$
  BEGIN
   IF (SELECT mode FROM allowance_writer_control WHERE id=1)='ledger' THEN
    IF NEW.lookup_bonus <> COALESCE((SELECT SUM(delta) FROM extra_movements WHERE dealer_id=NEW.dealer_id AND channel='lookups'),0)
       OR NEW.estimate_bonus <> COALESCE((SELECT SUM(delta) FROM extra_movements WHERE dealer_id=NEW.dealer_id AND channel='estimates'),0)
    THEN RAISE EXCEPTION 'Untracked allowance writer rejected'; END IF;
   END IF; RETURN NEW;
  END; $$""")
  # Zero-row creation is allowed: a new writer inserts history before updating it.
  con.execute("CREATE OR REPLACE TRIGGER fenced_allowance_update BEFORE UPDATE OF lookup_bonus,estimate_bonus ON account_allowances FOR EACH ROW WHEN (OLD.lookup_bonus IS DISTINCT FROM NEW.lookup_bonus OR OLD.estimate_bonus IS DISTINCT FROM NEW.estimate_bonus) EXECUTE FUNCTION allowance_bank_guard()")
  con.execute("CREATE OR REPLACE TRIGGER fenced_allowance_insert BEFORE INSERT ON account_allowances FOR EACH ROW WHEN (NEW.lookup_bonus<>0 OR NEW.estimate_bonus<>0) EXECUTE FUNCTION allowance_bank_guard()")
 else:
  for table in tables:
   for action in ('INSERT','UPDATE','DELETE'):
    con.execute(f"CREATE TRIGGER IF NOT EXISTS paused_{table}_{action.lower()} BEFORE {action} ON {table} WHEN (SELECT mode FROM allowance_writer_control WHERE id=1)='paused' BEGIN SELECT RAISE(ABORT,'Allowance writers are paused'); END")
  mismatch="NEW.lookup_bonus<>COALESCE((SELECT SUM(delta) FROM extra_movements WHERE dealer_id=NEW.dealer_id AND channel='lookups'),0) OR NEW.estimate_bonus<>COALESCE((SELECT SUM(delta) FROM extra_movements WHERE dealer_id=NEW.dealer_id AND channel='estimates'),0)"
  con.execute(f"CREATE TRIGGER IF NOT EXISTS fenced_allowance_update BEFORE UPDATE OF lookup_bonus,estimate_bonus ON account_allowances WHEN (SELECT mode FROM allowance_writer_control WHERE id=1)='ledger' AND (OLD.lookup_bonus<>NEW.lookup_bonus OR OLD.estimate_bonus<>NEW.estimate_bonus) AND ({mismatch}) BEGIN SELECT RAISE(ABORT,'Untracked allowance writer rejected'); END")
  con.execute(f"CREATE TRIGGER IF NOT EXISTS fenced_allowance_insert BEFORE INSERT ON account_allowances WHEN (SELECT mode FROM allowance_writer_control WHERE id=1)='ledger' AND (NEW.lookup_bonus<>0 OR NEW.estimate_bonus<>0) AND ({mismatch}) BEGIN SELECT RAISE(ABORT,'Untracked allowance writer rejected'); END")

def assert_writable(con):
 if con.execute('SELECT mode FROM allowance_writer_control WHERE id=1').fetchone()['mode']=='paused':raise ValueError('Allowance writers are paused. Retry after controlled maintenance.')

def set_mode(con,expected,target):
 """Operator transaction, never called by HTTP. Caller must drain writers first.

Ledger mode is one-way: rollback uses paused/read-only or another ledger-aware
build, never a return to unfenced legacy writes.
"""
 from extra_allowance_ledger import reconciliation,ensure_opening
 if expected not in ('legacy','paused','ledger') or target not in ('paused','ledger'):raise ValueError('Unsafe writer-mode transition.')
 if con.postgres:
  con.execute('LOCK TABLE account_allowances,account_subscription_usage,account_month_usage,dealer_usage,estimates,estimate_revisions,estimate_save_receipts IN ACCESS EXCLUSIVE MODE')
  con.execute('SELECT id FROM allowance_writer_control WHERE id=1 FOR UPDATE')
 row=con.execute('SELECT mode,epoch FROM allowance_writer_control WHERE id=1').fetchone()
 if row['mode']!=expected:raise ValueError('Writer mode changed; inspect before retrying.')
 if target=='ledger':
  if expected!='paused':raise ValueError('Pause and drain writers before ledger cutover.')
  for dealer in con.execute('SELECT id FROM dealers ORDER BY id').fetchall():
   ensure_opening(con,dealer['id'])
   if not reconciliation(con,dealer['id'])['balanced']:raise ValueError('Cutover reconciliation failed; remain paused.')
 con.execute('UPDATE allowance_writer_control SET mode=?,epoch=epoch+1 WHERE id=1 AND epoch=?',(target,row['epoch']))
 return dict(mode=target,epoch=int(row['epoch'])+1)
