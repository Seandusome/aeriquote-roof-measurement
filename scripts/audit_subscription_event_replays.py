"""Independent read-only SQL evidence audit. No adapter/evaluator imports."""
import hashlib,json,sqlite3,sys
from pathlib import Path
root=Path(sys.argv[1]).resolve();rows=[];limits={'basic':25,'pro':75,'business':200}
for path in sorted(root.rglob('*.sqlite')):
 assert path.with_suffix('.qa-marker').read_text()=='AERIQUOTE_FICTIONAL_EVENT_REPLAY_V1'
 con=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True);con.execute('PRAGMA query_only=ON')
 raw=con.execute('SELECT data FROM projection').fetchone()[0];state=json.loads(raw);assert state['business_id'].startswith('qa-fictional-')
 receipts=con.execute('SELECT id,operation_id,facts,status,issue FROM receipts ORDER BY id').fetchall()
 audits=con.execute('SELECT event_id,status,before_state,after_state,issue FROM audit ORDER BY seq').fetchall()
 applied=[op for _,op,_,status,_ in receipts if status=='applied'];assert len(applied)==len(set(applied))
 changed=[eid for eid,status,before,after,_ in audits if before!=after];assert len(changed)==len(set(changed))
 for _,status,before,after,_ in audits:
  if status in ('duplicate','review','observed_no_grant'):assert before==after
  assert json.loads(before)['saved_work']==json.loads(after)['saved_work']
 balances={};s=state['snapshot']
 if s:
  for channel in ['lookups','estimates']:
   cap=limits[s['period']['plan']]
   for u in s['upgrades']:
    delta=limits[u['to_plan']]-limits[u['from_plan']]
    cap+=u['consumed'][channel] if any(r['status']=='succeeded' for r in u['reversals']) else delta
   monthly=max(0,cap-s['used'][channel]);extra=s['extras'][channel]
   assert monthly>=0 and extra>=0
   balances[channel]={'cap':cap,'used':s['used'][channel],'monthly':monthly,'extras':extra,'available':monthly+extra}
  assert len(state['invoices'])==len(set(state['invoices']))
 for _,_,fact,status,_ in receipts:
  e=json.loads(fact)
  if status=='applied' and e['kind'].endswith('.paid'):
   assert e['payment']['status']=='succeeded' and e['payment']['verified'] is True and e['payment']['source']=='fictional_verified_fixture'
 rows.append({'database':str(path.relative_to(root)),'projection_sha256':hashlib.sha256(raw.encode()).hexdigest(),'balances_from_raw_sql':balances,'receipt_count':len(receipts),'audit_count':len(audits),'statuses':{status:sum(r[3]==status for r in receipts) for status in sorted({r[3] for r in receipts})}})
 con.close()
# Constants independently approved, not computed by the adapter/evaluator.
by={r['database']:r for r in rows}
for ch in ['lookups','estimates']:
 assert by['test_successful_upgrade_23_used_leaves_52/fictional.sqlite']['balances_from_raw_sql'][ch]['monthly']==52
 assert by['test_reverse_with_unused_base_preserves_two/fictional.sqlite']['balances_from_raw_sql'][ch]['monthly']==2
 assert by['test_pending_failed_upgrade_and_renewal_keep_old_plan/fictional.sqlite']['balances_from_raw_sql'][ch]['monthly']==2
 assert by['test_multiple_successful_upgrade_deltas/fictional.sqlite']['balances_from_raw_sql'][ch]['monthly']==177
(root/'independent-sql-audit.json').write_text(json.dumps({'database_count':len(rows),'checks':'raw SQL balance, immutable-work, exactly-once receipt/change and no-mutation denial assertions PASS','results':rows},indent=2))
print('INDEPENDENT_SQL_AUDIT_PASS',len(rows),'fictional databases')
