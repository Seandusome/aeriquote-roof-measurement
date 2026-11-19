"""Fresh offline replay evidence; independent raw SQLite/constant expectations."""
import copy
import itertools
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import socket
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from subscription_events_qa import ReplayStore, seed, projection, digest

B='qa-fictional-events'
NOW='2026-01-31T12:00:00Z'
ANCHOR=NOW
END='2026-02-28T12:00:00Z'
RET={'paid_access_end':END,'legacy_full':{'status':'none'},'legacy_lightweight':{'status':'none'},'full_present':True,'lightweight_present':True}
ROOT=Path(os.environ.get('AQ_EVENT_EVIDENCE',tempfile.mkdtemp(prefix='aq-offline-events-')))
ROOT.mkdir(parents=True,exist_ok=True)
OBS=[]


def period(i='p1',start=NOW,end=END,plan='basic',anchor=ANCHOR):
 return dict(id=i,start=start,end=end,plan=plan,renewal_anchor=anchor,payment_status='succeeded')
def payment(i,status='succeeded'):
 return dict(status=status,verified=True,subscription_status='active',invoice_id='invoice-'+i,subscription_id='subscription-fictional',source='fictional_verified_fixture')
def event(i,kind,previous=None,at=NOW,**data):
 return dict(schema=1,id='receipt-'+i,operation_id=i,business_id=B,kind=kind,previous_operation=previous,effective_at=at,**data)
def first(i='initial',p=None):
 return event(i,'initial.paid',period=p or period(),payment=payment(i))
def usage(i,prev,n,at='2026-02-01T12:00:00Z',**extra):
 return event(i,'usage.recorded',prev,at,period_id='p1',units={'lookups':n,'estimates':n},**extra)
def upgrade(i='upgrade',prev='usage',at='2026-02-02T12:00:00Z',target='pro',before='basic'):
 return event(i,'upgrade.paid',prev,at,payment=payment(i),period_id='p1',from_plan=before,to_plan=target,renewal_at=END)
def reverse(i='reversal',prev='upgrade',at='2026-02-04T12:00:00Z',up='upgrade',period_id='p1'):
 return event(i,'upgrade.reversed',prev,at,upgrade_id=up,period_id=period_id,status='succeeded',reversal_kind='full')

class Events(unittest.TestCase):
 def setUp(self):
  self.root=ROOT/self._testMethodName;self.root.mkdir(exist_ok=False)
  self.path=self.root/'fictional.sqlite'
  self.store=ReplayStore.create(self.path,seed(B,{'lookups':7,'estimates':11},RET,True))
  self.guard=patch.object(socket.socket,'connect',side_effect=AssertionError('Network forbidden in replay'));self.guard.start()
 def tearDown(self):
  self.guard.stop()
  with sqlite3.connect(self.path) as c:
   audit=c.execute('SELECT event_id,status,before_state,after_state,issue FROM audit ORDER BY seq').fetchall()
   for _,status,before,after,_ in audit:
    if status in ('review','duplicate','observed_no_grant'):self.assertEqual(before,after)
  OBS.append({'test':self._testMethodName,'projection_sha256':digest(self.raw()),'receipts':self.receipts(),'audit_rows':len(audit)})
 def raw(self):
  with sqlite3.connect(self.path) as c:return json.loads(c.execute('SELECT data FROM projection').fetchone()[0])
 def receipts(self):
  with sqlite3.connect(self.path) as c:return c.execute('SELECT id,status,issue FROM receipts ORDER BY id').fetchall()
 def add(self,e,now=None):
  original=copy.deepcopy(e);before=self.raw();self.store.ingest(e,now or e['effective_at']);self.assertEqual(e,original)
  after=self.raw();self.assertEqual(before['saved_work'],after['saved_work']);return after
 def init(self,p=None):return self.add(first(p=p))
 def calc(self,now='2026-02-05T12:00:00Z'):
  return projection(self.raw(),now)
 def unchanged(self,e,now=None):
  b=self.raw();self.add(e,now);self.assertEqual(b,self.raw())
 def assertBalance(self,monthly,extras=(7,11)):
  x=self.calc()['entitlements'];self.assertIsNotNone(x)
  self.assertEqual(x['remaining_monthly'],dict(zip(('lookups','estimates'),monthly)))
  self.assertEqual(x['extras'],dict(zip(('lookups','estimates'),extras)))

 def test_initial_and_successful_renewal_month_end(self):
  self.init();self.assertBalance((25,25));self.add(usage('usage','initial',23));self.assertBalance((2,2))
  e=event('renew','renewal.paid','usage',END,period=period('p2',END,'2026-03-31T12:00:00Z'),payment=payment('renew'))
  s=self.add(e);self.assertEqual(s['snapshot']['used'],{'lookups':0,'estimates':0});self.assertEqual(s['snapshot']['extras'],{'lookups':7,'estimates':11});self.assertEqual(s['periods']['p1']['used'],{'lookups':23,'estimates':23})
  self.assertEqual(projection(s,END)['schedule']['following_boundary'],'2026-04-30T12:00:00.000000Z')
 def test_pending_failed_initial_no_paid_benefits(self):
  for i,status in enumerate(['pending','failed']):
   self.unchanged(event('obs'+str(i),'payment.observed',payment=payment(str(i),status)))
  self.assertIsNone(self.raw()['snapshot'])
 def test_pending_failed_upgrade_and_renewal_keep_old_plan(self):
  self.init();self.add(usage('usage','initial',23));base=self.raw()
  for status in ['pending','failed']:
   for purpose in ['upgrade','renewal']:
    self.unchanged(event(status+purpose,'payment.observed','usage','2026-02-02T12:00:00Z',payment=payment(status+purpose,status),purpose=purpose))
  self.assertEqual(base,self.raw());self.assertBalance((2,2))
 def test_successful_upgrade_23_used_leaves_52(self):
  self.init();self.add(usage('usage','initial',23));before=self.raw();self.add(upgrade());self.assertBalance((52,52))
  s=self.raw()['snapshot'];self.assertEqual(s['used'],before['snapshot']['used']);self.assertEqual(s['extras'],before['snapshot']['extras']);self.assertEqual(s['period'],before['snapshot']['period']);self.assertEqual(self.calc()['entitlements']['plan'],'pro')
 def test_distinct_channel_usage_and_extra_bank(self):
  self.init();e=usage('usage','initial',0);e['units']={'lookups':29,'estimates':26};self.add(e);self.assertBalance((0,0),(3,10));self.unchanged(usage('too-many','usage',20))
 def test_downgrade_only_on_successful_next_renewal(self):
  self.init(period(plan='business'));self.add(usage('usage','initial',23))
  self.add(event('down','downgrade.scheduled','usage','2026-02-02T12:00:00Z',to_plan='pro'));self.assertBalance((177,177))
  self.unchanged(event('failed','payment.observed','down',END,payment=payment('renew','failed')))
  self.add(event('renew','renewal.paid','down',END,payment=payment('renew'),period=period('p2',END,'2026-03-31T12:00:00Z','pro')))
  self.assertEqual(projection(self.raw(),END)['entitlements']['remaining_monthly'],{'lookups':75,'estimates':75});self.assertEqual(self.raw()['periods']['p1']['used']['lookups'],23)
 def test_cancel_boundaries_120_days(self):
  self.init();self.add(usage('usage','initial',23));s=self.add(event('cancel','cancellation.scheduled','usage','2026-02-02T12:00:00Z',paid_access_end=END));before=copy.deepcopy(s)
  self.assertEqual(projection(s,'2026-02-28T11:59:59.999999Z')['access']['state'],'paid_active')
  x=projection(s,END);self.assertEqual(x['access']['state'],'retained_read_only');self.assertEqual(x['access']['full_expiry'],'2026-06-28T12:00:00.000000Z');self.assertFalse(x['schedule']['renewal_scheduled'])
  self.assertEqual(projection(s,'2026-06-28T11:59:59.999999Z')['access']['state'],'retained_read_only');self.assertEqual(projection(s,'2026-06-28T12:00:00Z')['access']['state'],'expired');self.assertEqual(before,self.raw())
 def test_reactivation_preserves_usage_extras(self):
  self.init();self.add(usage('usage','initial',23));self.add(event('cancel','cancellation.scheduled','usage','2026-02-02T12:00:00Z',paid_access_end=END));before=self.raw()
  s=self.add(event('reactivate','reactivation.paid','cancel','2026-03-31T12:00:00Z',payment=payment('reactivate'),period=period('p3','2026-03-31T12:00:00Z','2026-04-30T12:00:00Z')))
  for k in ['used','extras']:self.assertEqual(s['snapshot'][k],before['snapshot'][k])
  self.assertEqual(projection(s,'2026-04-01T12:00:00Z')['access']['restored_scopes'],{'full':True,'lightweight':True})
  self.assertEqual(projection(s,'2026-04-30T12:00:00Z')['access']['base_expiry'],'2026-08-28T12:00:00.000000Z')
 def test_reactivation_after120_longer_legacy_and_deleted_scope(self):
  state=self.raw();state['retention']['legacy_full']={'status':'known','deadline':'2027-01-01T00:00:00Z'}
  with sqlite3.connect(self.path) as c:c.execute('UPDATE projection SET data=?',(json.dumps(state),))
  self.init();s=self.add(event('reactivate','reactivation.paid','initial','2026-07-31T12:00:00Z',payment=payment('reactivate'),period=period('p7','2026-07-31T12:00:00Z','2026-08-31T12:00:00Z')))
  self.assertTrue(projection(s,'2026-08-01T00:00:00Z')['access']['restored_scopes']['full'])
  s['snapshot']['retention']['full_present']=False;s['snapshot']['retention']['lightweight_present']=False
  self.assertFalse(projection(s,'2026-08-01T00:00:00Z')['access']['restored_scopes']['full'])
 def test_unused_partial_and_full_upgrade_reversals(self):
  for n in [0,10,50]:
   path=self.root/('case'+str(n)+'.sqlite');st=ReplayStore.create(path,seed(B,{'lookups':7,'estimates':11},RET,True));st.ingest(first(),NOW)
   st.ingest(usage('usage','initial',25), '2026-02-01T12:00:00Z');st.ingest(upgrade(), '2026-02-02T12:00:00Z')
   st.ingest(usage('consume','upgrade',n,'2026-02-03T12:00:00Z'),'2026-02-03T12:00:00Z');before=st.state();st.ingest(reverse(prev='consume'),'2026-02-04T12:00:00Z');s=st.state();c=projection(s,'2026-02-05T12:00:00Z')['entitlements']
   self.assertEqual(c['caps'],{'lookups':25+n,'estimates':25+n});self.assertEqual(c['remaining_monthly'],{'lookups':0,'estimates':0});self.assertEqual(c['upgrades'][0]['removed_unused'],{'lookups':50-n,'estimates':50-n});self.assertEqual(before['snapshot']['used'],s['snapshot']['used']);self.assertEqual(before['snapshot']['extras'],s['snapshot']['extras']);self.assertEqual(before['usage_ledger'],s['usage_ledger'])
 def test_reverse_with_unused_base_preserves_two(self):
  self.init();self.add(usage('usage','initial',23));self.add(upgrade());self.add(reverse());self.assertBalance((2,2));self.assertEqual(self.calc()['entitlements']['plan'],'basic')
 def test_duplicate_receipts_and_semantic_operations(self):
  self.init();self.add(usage('usage','initial',23));e=upgrade();self.add(e);before=self.raw();self.unchanged(e);dup=copy.deepcopy(e);dup['id']='second-delivery';self.unchanged(dup);self.assertEqual(before,self.raw());self.assertBalance((52,52))
 def test_conflicting_receipt_and_operation(self):
  self.init();e=usage('usage','initial',23);self.add(e);bad=copy.deepcopy(e);bad['units']['lookups']=24;self.unchanged(bad);bad['id']='changed-semantic';self.unchanged(bad);self.assertBalance((2,2))
 def test_out_of_order_dependent_chain_converges(self):
  u=usage('usage','initial',23);g=upgrade();self.unchanged(g,'2026-02-05T12:00:00Z');self.unchanged(u,'2026-02-05T12:00:00Z');self.add(first(), '2026-02-05T12:00:00Z');self.assertBalance((52,52));self.assertEqual([s for _,s,_ in self.receipts()],['applied','applied','applied'])
 def test_delayed_old_period_cannot_reset_new_usage(self):
  self.init();self.add(event('renew','renewal.paid','initial',END,payment=payment('renew'),period=period('p2',END,'2026-03-31T12:00:00Z')))
  e=usage('new-usage','renew',9,'2026-03-01T12:00:00Z');e['period_id']='p2';self.add(e)
  self.unchanged(upgrade(prev='initial'),'2026-03-02T12:00:00Z');self.assertEqual(self.raw()['snapshot']['used']['lookups'],9)
 def test_duplicate_period_or_invoice_cannot_reset(self):
  self.init();self.add(usage('usage','initial',23));bad=first('different');bad['previous_operation']='usage';self.unchanged(bad)
  e=upgrade();e['payment']['invoice_id']='invoice-initial';self.unchanged(e);self.assertBalance((2,2))
 def test_missing_payment_evidence_redirect_unknown_kind(self):
  self.init()
  for key,change in [('pending',{'status':'pending'}),('failed',{'status':'failed'}),('unverified',{'verified':False}),('redirect',{'source':'browser_redirect'}),('past_due',{'subscription_status':'past_due'})]:
   e=upgrade(key,'initial');e['payment'].update(change);self.unchanged(e)
  self.unchanged(event('unknown','checkout.redirect','initial'));e=upgrade('missing','initial');del e['payment'];self.unchanged(e)
 def test_future_and_missing_predecessor_wait(self):
  e=first();self.unchanged(e,'2026-01-01T00:00:00Z');self.add(e,NOW);self.assertIsNotNone(self.raw()['snapshot'])
  self.unchanged(upgrade(prev='missing'));self.assertIn('pending',[x[1] for x in self.receipts()])
 def test_wrong_business_never_changes_state(self):
  self.init();e=upgrade('foreign','initial');e['business_id']='qa-fictional-other';self.unchanged(e)
 def test_unknown_legacy_not_guessed(self):
  s=self.raw();s['retention']['legacy_full']={'status':'unknown'}
  with sqlite3.connect(self.path) as c:c.execute('UPDATE projection SET data=?',(json.dumps(s),))
  self.unchanged(first());self.assertIn('review',[x[1] for x in self.receipts()])
 def test_atomic_failure_and_retry(self):
  self.init();e=usage('usage','initial',23)
  with sqlite3.connect(self.path) as c:before=list(c.iterdump())
  with self.assertRaises(RuntimeError):self.store.ingest(e,e['effective_at'],fail_before_commit=True)
  with sqlite3.connect(self.path) as c:self.assertEqual(before,list(c.iterdump()))
  self.add(e);self.unchanged(e);self.assertBalance((2,2))
 def test_competing_threads_same_receipt_once(self):
  self.init();e=usage('usage','initial',23)
  with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda _:self.store.ingest(e,e['effective_at']),range(2)))
  self.assertBalance((2,2));self.assertEqual(len(self.raw()['usage_ledger']),1)
 def test_partial_cross_period_and_multi_upgrade_reversals_flagged(self):
  self.init();self.add(usage('usage','initial',23));self.add(upgrade());e=reverse();e['reversal_kind']='partial';self.unchanged(e)
  self.unchanged(reverse('otherperiod',period_id='p0'));self.add(upgrade('business','upgrade','2026-02-03T12:00:00Z','business','pro'))
  self.unchanged(reverse('multi','business'));self.assertBalance((177,177))
 def test_disabled_security_never_grants_actionable_access(self):
  s=self.raw();s['security_eligible']=False
  with sqlite3.connect(self.path) as c:c.execute('UPDATE projection SET data=?',(json.dumps(s),))
  self.init();self.assertFalse(self.calc()['access']['can_create_or_edit']);self.unchanged(usage('usage','initial',1))
 def test_renewal_plan_and_anchor_conflicts_flagged(self):
  self.init()
  for i,p in [('wrong-plan',period('p2',END,'2026-03-31T12:00:00Z','pro')),('wrong-anchor',period('p2',END,'2026-03-31T12:00:00Z',anchor='2026-01-28T12:00:00Z'))]:
   self.unchanged(event(i,'renewal.paid','initial',END,payment=payment(i),period=p))

 def test_unknown_missing_and_stale_control_events(self):
  self.init();self.add(usage('usage','initial',23))
  e=event('missing','downgrade.scheduled',to_plan='basic');del e['previous_operation'];self.unchanged(e)
  self.unchanged(event('unknown','imaginary.event','never-seen'))
  self.unchanged(event('old-cancel','cancellation.scheduled','initial','2026-02-02T12:00:00Z',paid_access_end=END))
  self.assertTrue(all(s=='review' for i,s,_ in self.receipts() if i in ['receipt-missing','receipt-unknown','receipt-old-cancel']))

 def test_all_delivery_orders_use_causal_facts_not_timestamps(self):
  chain=[first(),usage('usage','initial',23),upgrade(),usage('consume','upgrade',12,'2026-02-03T12:00:00Z'),reverse(prev='consume')]
  # 120 complete event permutations, each with independent expected raw balances.
  for n,events in enumerate(itertools.permutations(chain)):
   st=ReplayStore.create(self.root/('order'+str(n)+'.sqlite'),seed(B,{'lookups':7,'estimates':11},RET,True))
   for e in events:st.ingest(e,'2026-02-05T12:00:00Z')
   with sqlite3.connect(st.path) as c:
    raw=json.loads(c.execute('SELECT data FROM projection').fetchone()[0]);statuses=c.execute('SELECT status FROM receipts').fetchall()
   self.assertEqual(raw['head'],'reversal');self.assertEqual(raw['snapshot']['used'],{'lookups':35,'estimates':35});self.assertEqual(raw['snapshot']['extras'],{'lookups':7,'estimates':11});self.assertEqual(raw['snapshot']['upgrades'][0]['consumed'],{'lookups':10,'estimates':10});self.assertTrue(all(s[0]=='applied' for s in statuses))
   self.assertEqual(projection(raw,'2026-02-05T12:00:00Z')['entitlements']['remaining_monthly'],{'lookups':0,'estimates':0})

 def test_repeated_reversal_does_not_remove_more(self):
  self.init();self.add(usage('usage','initial',23));self.add(upgrade());e=reverse();self.add(e);self.unchanged(e)
  self.unchanged(reverse('second-reversal','reversal','2026-02-05T12:00:00Z'));self.assertBalance((2,2))

 def test_conflicting_queued_branches_require_review(self):
  self.unchanged(usage('one','initial',1),'2026-02-03T12:00:00Z');self.unchanged(usage('two','initial',2),'2026-02-03T12:00:00Z');self.add(first(),'2026-02-03T12:00:00Z')
  self.assertBalance((25,25));self.assertEqual(len([s for _,s,_ in self.receipts() if s=='review']),2)

 def test_multiple_successful_upgrade_deltas(self):
  self.init();self.add(usage('usage','initial',23));self.add(upgrade());self.add(upgrade('business','upgrade','2026-02-03T12:00:00Z','business','pro'))
  self.assertBalance((177,177));self.assertEqual(self.calc()['entitlements']['plan'],'business');self.assertEqual(self.raw()['snapshot']['used']['lookups'],23)

 def test_unknown_or_naive_time_never_mutates_projection(self):
  self.init()
  for i,at in enumerate(['bad-time','2026-02-02T00:00:00',None]):
   self.unchanged(event('bad-time'+str(i),'usage.recorded','initial',at,period_id='p1',units={'lookups':1,'estimates':1}),NOW)

if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Events))
 (ROOT/'independent-observations.json').write_text(json.dumps(OBS,indent=2))
 raise SystemExit(not result.wasSuccessful())
