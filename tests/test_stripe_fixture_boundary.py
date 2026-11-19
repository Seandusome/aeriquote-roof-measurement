"""Recorded fiction only. Network disabled; SQL assertions do not use evaluator."""
import copy
import itertools
import json
import os
from pathlib import Path
import socket
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from subscription_events_qa import ReplayStore, seed
from stripe_fixture_boundary import FixtureReplay, normalize

ROOT=Path(os.environ.get('AQ_BOUNDARY_EVIDENCE',tempfile.mkdtemp(prefix='aq-boundary-')))
FIX=Path(__file__).parent/'fixtures'/'stripe_boundary_fictional.json'
F=json.loads(FIX.read_text())
NOW='2026-04-01T12:00:00Z'
RET={'paid_access_end':'2026-02-28T12:00:00Z','legacy_full':{'status':'none'},
     'legacy_lightweight':{'status':'none'},'full_present':True,'lightweight_present':True}


def raw(path):
    with sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True) as c:
        return json.loads(c.execute('SELECT data FROM projection').fetchone()[0]), list(c.execute('SELECT id,operation_id,status,issue FROM receipts ORDER BY id'))


def altered(data,path,value):
    root=copy.deepcopy(data); q=root; parts=path.split('.')
    for p in parts[:-1]:q=q[int(p)] if isinstance(q,list) else q[p]
    if isinstance(q,list):q[int(parts[-1])]=value
    else:q[parts[-1]]=value
    return root


class Boundary(unittest.TestCase):
    def setUp(self):
        self.root=ROOT/self._testMethodName;self.root.mkdir(parents=True,exist_ok=False)
        self.path=self.root/'fictional.sqlite'
        self.store=ReplayStore.create(self.path,seed(F['binding']['business_id'],{'lookups':7,'estimates':11},RET,True))
        self.runner=FixtureReplay(self.store);self.inputs=[]

    def tearDown(self):
        (self.root/'inputs.json').write_text(json.dumps(self.inputs,indent=2))
        (self.root/'boundary-audit.json').write_text(json.dumps(self.runner.audit,indent=2))

    def send(self,name='initial',data=None):
        q=copy.deepcopy(data or F['cases'][name]); self.inputs.append(q)
        return self.runner.deliver(q['notification'],q.get('binding',F['binding']),q['contract'],q['canonical'],NOW)

    def assert_base(self,used=0,upgrades=0):
        s,receipts=raw(self.path);p=s['snapshot']
        self.assertEqual(p['used'],{'lookups':used,'estimates':used})
        self.assertEqual(p['extras'],{'lookups':7,'estimates':11})
        self.assertEqual(len(p['upgrades']),upgrades)
        self.assertEqual(s['saved_work'],{'sentinel':'UNCHANGED'})
        return s,receipts

    def use23(self):
        self.store.ingest(dict(schema=1,id='qa-usage-23',operation_id='usage23',business_id=F['binding']['business_id'],
                previous_operation='invoice:in_fixture_initial:initial.paid',kind='usage.recorded',
                effective_at='2026-02-01T12:00:00Z',period_id='p1',units={'lookups':23,'estimates':23}),NOW)

    def test_initial_and_semantic_duplicate(self):
        self.assertEqual(self.send()['status'],'normalized');before=raw(self.path)[0]
        self.send();q=copy.deepcopy(F['cases']['initial']);q['notification']['id']='evt_fixture_second'
        q['notification']['type']='invoice.payment_succeeded';q['notification']['created']=1
        self.send(data=q);self.assertEqual(before,raw(self.path)[0]);self.assert_base()
        self.assertEqual(sum(r[2]=='applied' for r in raw(self.path)[1]),1)

    def test_upgrade_23_used_leaves52(self):
        self.send();self.use23();before=raw(self.path)[0]['snapshot']
        self.send('upgrade');s,_=self.assert_base(23,1)
        self.assertEqual(s['snapshot']['period'],before['period'])
        self.assertEqual(25+50-s['snapshot']['used']['lookups'],52)
        self.assertEqual(s['snapshot']['upgrades'][0]['to_plan'],'pro')
        after=raw(self.path)[0];self.send('upgrade');self.assertEqual(after,raw(self.path)[0])

    def test_pending_failed_incomplete_no_benefits_then_success(self):
        self.send();self.use23();before=raw(self.path)[0]
        for status in ('processing','requires_action','requires_payment_method','requires_confirmation','canceled'):
            q=copy.deepcopy(F['cases']['upgrade']);q['notification']['id']='evt_fixture_'+status
            q['notification']['type']='invoice.payment_failed' if status in ('requires_payment_method','canceled') else 'invoice.payment_action_required'
            inv=q['canonical']['invoice'];inv.update(status='open',amount_paid=0,amount_remaining=1500)
            inv['status_transitions']['paid_at']=None
            ip=inv['payments']['data'][0];ip.update(status='open',amount_paid=None);ip['status_transitions']['paid_at']=None
            pi=q['canonical']['payment_intent'];pi.update(status=status,amount_received=0,latest_charge=None)
            q['canonical']['charge']=None;q['canonical']['subscription']['status']='incomplete'
            self.assertEqual(self.send(data=q)['status'],'normalized');self.assertEqual(before,raw(self.path)[0])
        self.send('upgrade');self.assert_base(23,1)

    def test_out_of_order_paid_chain(self):
        self.send('renewal');self.send('upgrade');self.send();self.use23()
        # Usage arrives separately; adapter drains the already-normalized paid chain.
        s,r=self.assert_base(0,0)
        self.assertEqual(s['snapshot']['period']['id'],'p2')
        self.assertEqual(s['snapshot']['period']['plan'],'pro')
        self.assertEqual(s['periods']['p1']['used']['lookups'],23)
        self.assertEqual(sum(x[2]=='applied' for x in r),4)

    def test_renewal_duplicate_no_reset_after_usage(self):
        self.send();self.use23();self.send('upgrade');self.send('renewal')
        self.store.ingest(dict(schema=1,id='qa-use-new',operation_id='use-new',business_id=F['binding']['business_id'],
          previous_operation='invoice:in_fixture_renewal:renewal.paid',kind='usage.recorded',
          effective_at='2026-03-01T12:00:00Z',period_id='p2',units={'lookups':3,'estimates':3}),NOW)
        before=raw(self.path)[0];self.send('renewal');self.send('initial');self.send('upgrade')
        self.assertEqual(before,raw(self.path)[0]);self.assert_base(3)

    def test_conflicting_raw_receipt(self):
        self.send();before=raw(self.path)[0]
        q=altered(F['cases']['initial'],'notification.data.object.customer','cus_other')
        self.assertEqual(self.send(data=q)['status'],'review');self.assertEqual(before,raw(self.path)[0])

    def test_notification_claims_do_not_authorize(self):
        q=copy.deepcopy(F['cases']['initial']);q['notification']['data']['object'].update(customer='cus_attacker',amount_paid=1,status='paid',metadata={'business_id':'wrong'})
        q['canonical']['payment_intent']['status']='requires_action'
        before=raw(self.path)[0];self.assertEqual(self.send(data=q)['status'],'review')
        self.assertEqual(before,raw(self.path)[0])

    def test_stale_branch_and_conflicting_canonical_operation(self):
        self.send();self.use23();self.send('upgrade');before=raw(self.path)[0]
        q=copy.deepcopy(F['cases']['upgrade']);q['notification']['id']='evt_fixture_conflict'
        q['contract']['previous_operation']='invoice:in_fixture_initial:initial.paid'
        self.send(data=q);self.assertEqual(before,raw(self.path)[0])
        self.assertTrue(any(x[2]=='review' for x in raw(self.path)[1]))

    def test_refunds_disputes_unknown_and_redirect_review(self):
        self.send();self.use23();self.send('upgrade');before=raw(self.path)[0]
        for t in ('refund.created','refund.updated','charge.refunded','charge.dispute.created','customer.subscription.updated','checkout.session.completed','unknown.event'):
            q=copy.deepcopy(F['cases']['upgrade']);q['notification']['id']='evt_fixture_'+t;q['notification']['type']=t
            self.assertEqual(self.send(data=q)['status'],'review');self.assertEqual(before,raw(self.path)[0])

    def test_missing_canonical_fields_review(self):
        self.send();before=raw(self.path)[0]
        for field in ('customer','subscription','prices','invoice','payment_intent','charge','api_version','provenance'):
            q=copy.deepcopy(F['cases']['upgrade']);del q['canonical'][field]
            self.assertEqual(self.send(data=q)['status'],'review');self.assertEqual(before,raw(self.path)[0])

    def test_validation_matrix_no_grants(self):
        for i,(path,value) in enumerate(F['invalid_mutations']):
            with self.subTest(path=path,value=value):
                q=altered(F['cases']['initial'],path,value);q['notification']['id']='evt_fixture_bad'+str(i)
                before=raw(self.path)[0];result=self.send(data=q)
                self.assertEqual(result['status'],'review',path);self.assertEqual(before,raw(self.path)[0])
        self.assertIsNone(raw(self.path)[0]['snapshot'])
        self.assertEqual(raw(self.path)[1],[])

    def test_upgrade_mutations_no_benefits(self):
        self.send();self.use23();before=raw(self.path)[0]
        for i,(path,value) in enumerate(F['upgrade_mutations']):
            q=altered(F['cases']['upgrade'],path,value);q['notification']['id']='evt_fixture_upbad'+str(i)
            self.assertEqual(self.send(data=q)['status'],'review',path);self.assertEqual(before,raw(self.path)[0])
        self.assert_base(23)

    def test_missing_predecessor_stays_pending(self):
        self.send('upgrade');s,r=raw(self.path)
        self.assertIsNone(s['snapshot']);self.assertEqual(r[0][2],'pending')

    def test_changed_valid_quote_same_operation_requires_review(self):
        self.send();self.use23();self.send('upgrade');before=raw(self.path)[0]
        q=copy.deepcopy(F['cases']['upgrade']);q['notification']['id']='evt_fixture_changed_quote'
        q['contract']['quote_id']='qa-quote-different-record'
        self.assertEqual(self.send(data=q)['status'],'normalized')
        self.assertEqual(before,raw(self.path)[0])
        self.assertTrue(any(x[2]=='review' and 'Conflicting facts' in x[3] for x in raw(self.path)[1]))

    def test_late_old_invoice_against_new_subscription_snapshot_review(self):
        self.send();self.use23();self.send('upgrade');self.send('renewal');before=raw(self.path)[0]
        q=copy.deepcopy(F['cases']['initial']);q['notification']['id']='evt_fixture_delayed_old'
        q['canonical']['subscription']=copy.deepcopy(F['cases']['renewal']['canonical']['subscription'])
        self.assertEqual(self.send(data=q)['status'],'review');self.assertEqual(before,raw(self.path)[0])

    def test_malformed_nested_shapes_review(self):
        for i,path in enumerate(('canonical.invoice.lines.data','canonical.customer','canonical.subscription.items','contract.lines')):
            q=altered(F['cases']['initial'],path,None);q['notification']['id']='evt_fixture_shape'+str(i)
            before=raw(self.path)[0];self.assertEqual(self.send(data=q)['status'],'review')
            self.assertEqual(before,raw(self.path)[0])

    def test_all_paid_delivery_permutations(self):
        for i,order in enumerate(itertools.permutations(('initial','upgrade','renewal'))):
            path=self.root/('permutation'+str(i)+'.sqlite')
            store=ReplayStore.create(path,seed(F['binding']['business_id'],{'lookups':7,'estimates':11},RET,True))
            runner=FixtureReplay(store)
            store.ingest(dict(schema=1,id='qa-usage-23',operation_id='usage23',business_id=F['binding']['business_id'],
                previous_operation='invoice:in_fixture_initial:initial.paid',kind='usage.recorded',
                effective_at='2026-02-01T12:00:00Z',period_id='p1',units={'lookups':23,'estimates':23}),NOW)
            for name in order:
                q=F['cases'][name];runner.deliver(q['notification'],F['binding'],q['contract'],q['canonical'],NOW)
            s,r=raw(path)
            self.assertEqual(s['snapshot']['period']['id'],'p2');self.assertEqual(s['snapshot']['used']['estimates'],0)
            self.assertEqual(s['periods']['p1']['used']['estimates'],23)
            self.assertEqual(sum(x[2]=='applied' for x in r),4)
            (self.root/('permutation'+str(i)+'-audit.json')).write_text(json.dumps(runner.audit,indent=2))

if __name__=='__main__':
    with patch.object(socket,'socket',side_effect=RuntimeError('Network forbidden in fixture replay')):
        unittest.main(verbosity=2)
