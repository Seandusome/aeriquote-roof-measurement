"""Real Flask handlers, disposable local SQLite; independent SQL assertions."""
import json, os, sqlite3, sys, tempfile, time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.dont_write_bytecode=True
with tempfile.TemporaryDirectory(prefix='aq-discard-fictional-') as folder:
 target=Path(folder)/'fictional.sqlite'
 os.environ['DATABASE_URL']='';os.environ['ESTIMATE_DB_PATH']=str(target)
 os.environ['GOOGLE_API_KEY']='';os.environ['GOOGLE_MAPS_API_KEY']=''
 assert target.parent==Path(folder) and not target.exists()
 import app as a, workspace_drafts as drafts
 from account_credits import month_key
 assert a.DATABASE_URL=='' and Path(a.ESTIMATE_DB)==target
 a.app.config['TESTING']=True
 c=a.estimate_db()
 for business in ['fictional-A','fictional-B']:
  c.execute('INSERT INTO dealers(id,dealer_name,email,password_hash,status,created_at) VALUES(?,?,?,?,?,?)',(business,'FICTIONAL',business+'@example.invalid','unused','active','2026-11-22'))
  c.execute('INSERT INTO account_allowances(dealer_id,complimentary,lookup_bonus,estimate_bonus) VALUES(?,1,7,11)',(business,))
  c.execute('INSERT INTO account_month_usage(dealer_id,period,lookups,estimates) VALUES(?,?,9,13)',(business,month_key()))
 c.execute('INSERT INTO dealer_employees(id,dealer_id,employee_name,email,password_hash,status,created_at) VALUES(?,?,?,?,?,?,?)',('fictional-employee','fictional-A','FICTIONAL','employee@example.invalid','unused','active','2026-11-22'))
 c.commit();c.close()
 def client(business='fictional-A',employee=False):
  x=a.app.test_client()
  with x.session_transaction() as s:
   s.update(dealer_id=business,auth_version=0,account_type='employee' if employee else 'owner')
   if employee:s['employee_id']='fictional-employee'
  return x
 owner=client();other=client('fictional-B');employee=client(employee=True)
 h={'X-AeriQuote-Account':'fictional-A','X-AeriQuote-Principal':'owner:fictional-A'}
 hb={'X-AeriQuote-Account':'fictional-B','X-AeriQuote-Principal':'owner:fictional-B'}
 he={'X-AeriQuote-Account':'fictional-A','X-AeriQuote-Principal':'employee:fictional-employee'}
 now=time.time()
 workspace={'schema':1,'values':{'customerName':'FICTIONAL','customerNotes':'EXACT RETAINED TEXT'},'quote':{'rate':.85,'pitch':26.565,'points':[[1,2],[1,3],[2,3]]}}
 c=a.estimate_db()
 for ident,when in [('fictional-valid-0001',now),('fictional-other-tab-0001',now-1),('fictional-boundary-0001',now-drafts.TTL),('fictional-expired-0001',now-drafts.TTL-1)]:
  drafts.put(c,'fictional-A','owner:fictional-A',ident,0,workspace,now=when)
 c.commit();c.close()
 def snapshot():
  # Independent connection, not application serializer or cached response.
  con=sqlite3.connect(target)
  result={}
  for table in ['workspace_drafts','estimates','estimate_revisions','estimate_save_receipts','dealer_usage','account_month_usage','account_allowances','account_subscription_usage','account_credit_audit']:
   result[table]=con.execute('SELECT * FROM '+table+' ORDER BY 1,2').fetchall()
  con.close();return result
 log=[]
 with patch.object(drafts.time,'time',return_value=now):
  listed=owner.get('/api/workspace-drafts',headers=h)
  assert [x['draft_id'] for x in listed.json['drafts']]==['fictional-valid-0001','fictional-other-tab-0001']
  assert listed.json['server_time']==now
  assert listed.headers['Cache-Control']=='private, no-store'
 log.append('Expired and exact-24h-boundary drafts not listed; existing server purge unchanged; current draft remains exact.')
 path='/api/workspace-drafts/fictional-valid-0001'
 before=snapshot()
 for browser,headers,status in [(owner,hb,409),(other,h,409),(other,hb,404),(employee,he,404),(employee,h,409),(a.app.test_client(),h,401)]:
  result=browser.delete(path,headers=headers,json={'version':1,'intent':'discard'})
  assert result.status_code==status,(result.status_code,result.json)
  assert snapshot()==before
 assert owner.delete(path,headers=h).status_code==428 and snapshot()==before
 assert owner.delete(path,headers={**h,'Origin':'https://foreign.invalid'},json={'version':1,'intent':'discard'}).status_code==403
 assert snapshot()==before
 log.append('Stale page account/user bindings, actual switched session, foreign business, foreign employee, signed-out and foreign-origin requests denied with no SQL changes. No silent rebinding.')
 # Same original login and freshly rendered page has no mismatch; this does not identify Sean's actual old-tab state.
 html=owner.get('/?industry=paving')
 assert html.status_code==200 and 'data-account-id="fictional-A"' in html.text and 'data-principal="owner:fictional-A"' in html.text
 assert html.headers['Cache-Control']=='private, no-store'
 assert owner.get('/static/workspace_drafts.js').headers['Cache-Control']=='private, no-store'
 log.append('Unchanged original login renders matching binding; authenticated workspace and draft script not cacheable. Actual Sean-tab mismatch cause remains unknown.')
 # Another tab acknowledged a new version while the chooser was idle.
 newer={**workspace,'values':{'customerName':'FICTIONAL NEWER','customerNotes':'KEEP NEWER'}}
 assert owner.put(path,headers=h,json={'version':1,'workspace':newer}).status_code==200
 before=snapshot();conflict=owner.delete(path,headers=h,json={'version':1,'intent':'discard'})
 assert conflict.status_code==409 and conflict.json['code']=='draft_changed' and snapshot()==before
 assert owner.get(path,headers=h).json['workspace']==newer
 # Restore cleanup retains its non-destructive deleted:false protocol.
 assert owner.delete(path,headers=h,json={'version':1}).json=={'deleted':False} and snapshot()==before
 log.append('Stale explicit Discard rejects newer version unchanged; delayed Restore cleanup still returns deleted:false and preserves newer work.')
 def failed_close(*args,**kwargs):
  original_close(*args,**kwargs)
  raise sqlite3.OperationalError('FICTIONAL failure before commit')
 original_close=drafts.close
 with patch.object(drafts,'close',side_effect=failed_close):
  try:owner.delete(path,headers=h,json={'version':2,'intent':'discard'})
  except sqlite3.OperationalError:pass
  else:raise AssertionError('Expected fictional storage failure')
 assert snapshot()==before
 log.append('Injected post-write/pre-commit database failure rolls back; original exact workspace and all allowance/estimate rows unchanged.')
 result=owner.delete(path,headers=h,json={'version':2,'intent':'discard'})
 assert result.status_code==200 and result.json['deleted']
 closed=snapshot();assert owner.delete(path,headers=h,json={'version':2,'intent':'discard'}).json['deleted'] and snapshot()==closed
 for table in before:
  if table!='workspace_drafts':assert before[table]==closed[table]
 con=sqlite3.connect(target);saved=con.execute('SELECT closed,payload,property_metadata FROM workspace_drafts WHERE draft_id=?',('fictional-valid-0001',)).fetchone();con.close()
 assert saved==(1,None,None)
 assert owner.get('/api/workspace-drafts/fictional-other-tab-0001',headers=h).json['workspace']==workspace
 log.append('Authorized versioned Discard closes only its fictional target; lost-ack retry idempotent; no estimates, revisions, receipts or allowance changes.')
 print(json.dumps({'status':'PASS','database':'disposable local SQLite only','checks':log,'unrelated_draft_exact':'preserved','before_allowances':before['account_allowances'],'after_allowances':closed['account_allowances'],'before_usage':before['account_month_usage'],'after_usage':closed['account_month_usage'],'limits':'No hosted records or Sean tab inspected; not PostgreSQL/browser/phone verification.'},indent=2))
