import copy
import json
import unittest
from datetime import datetime, timedelta, timezone

from retention_restore_planner import plan_retention, PlannerInputError


END = '2026-01-31T12:00:00Z'
EXPIRY = '2026-05-31T12:00:00Z'  # Independently counted: 28 + 31 + 30 + 31 days.


def fixture(now='2026-02-01T12:00:00Z', mode='restore'):
    return dict(schema=1, now=now, mode=mode, snapshot_at='2026-01-31T00:00:00Z',
                deletion_ledger=dict(authoritative=True, complete_through=now,
                                     independent_of_snapshot=True,
                                     covered_business_ids=['fictional-A', 'fictional-B'], entries=[]),
                records=[dict(business_id='fictional-A', id='estimate-1', kind='estimate', scope='full',
                              customer='FICTIONAL CUSTOMER', geometry=[[1, 2], [3, 4], [5, 6]], rate=1.23,
                              policy=dict(business_id='fictional-A', provenance='fictional-period-record',
                                          period=dict(id='period-1', start='2026-01-01T12:00:00Z',
                                                      end=END, payment_status='succeeded'),
                                          retention=dict(paid_access_end=END, full_present=True,
                                                         lightweight_present=True,
                                                         legacy_full=dict(status='none', provenance='fictional-promise-register'),
                                                         legacy_lightweight=dict(status='none', provenance='fictional-promise-register'))))])


def tombstone(record='estimate-1', scope='all', business='fictional-A', **extra):
    return dict(event_id='delete-1', business_id=business, record_id=record,
                kind='deleted', scope=scope, sequence=1,
                effective_at='2026-02-01T00:00:00Z', provenance='fictional-independent-ledger', **extra)


class Planner(unittest.TestCase):
    def run_plan(self, value):
        before = json.dumps(value, sort_keys=True)
        try:
            result = plan_retention(value)
        finally:
            self.assertEqual(json.dumps(value, sort_keys=True), before)
        self.assertEqual(result, plan_retention(copy.deepcopy(value)))
        self.assertFalse(result['writes_performed'])
        self.assertFalse(result['access_granted'])
        self.assertTrue(result['requires_independent_release_review'])
        return result

    def record(self, value):
        return self.run_plan(value)['records'][0]

    def test_paid_end_and_exact_120_day_boundaries(self):
        for now, expected in [('2026-01-31T11:59:59.999999Z', 'active'),
                              (END, 'read_only'), ('2026-05-31T11:59:59.999999Z', 'read_only'),
                              (EXPIRY, 'expired'), ('2026-05-31T12:00:00.000001Z', 'expired')]:
            with self.subTest(now=now):
                out = self.record(fixture(now)); self.assertEqual(out['state'], expected)
                self.assertEqual(out['expiry'], '2026-05-31T12:00:00.000000Z')

    def test_offset_equivalence(self):
        f = fixture('2026-05-31T06:00:00-06:00')
        self.assertEqual(self.record(f)['state'], 'expired')

    def test_leap_day_and_elapsed_days(self):
        f = fixture('2024-06-28T00:00:00Z'); f['snapshot_at'] = '2024-02-01T00:00:00Z'
        p = f['records'][0]['policy']; p['period'].update(start='2024-02-01T00:00:00Z', end='2024-02-29T00:00:00Z')
        p['retention']['paid_access_end'] = '2024-02-29T00:00:00Z'
        out = self.record(f); self.assertEqual(out['expiry'], '2024-06-28T00:00:00.000000Z'); self.assertEqual(out['state'], 'expired')

    def test_longer_full_protects_lightweight(self):
        for scope in ['full', 'lightweight']:
            f = fixture('2026-06-15T00:00:00Z'); r = f['records'][0]; r['scope'] = scope
            r['policy']['retention']['legacy_full'] = dict(status='known', deadline='2026-08-31T00:00:00Z', provenance='fictional-signed-promise')
            self.assertEqual(self.record(f)['expiry'], '2026-08-31T00:00:00.000000Z')
            self.assertEqual(self.record(f)['state'], 'read_only')

    def test_scopes_expire_separately(self):
        for scope, state in [('full', 'expired'), ('lightweight', 'read_only')]:
            f = fixture('2026-06-15T00:00:00Z'); f['records'][0]['scope'] = scope
            f['records'][0]['policy']['retention']['legacy_lightweight'] = dict(status='known', deadline='2027-01-01T00:00:00Z', provenance='fictional-prior-promise')
            self.assertEqual(self.record(f)['state'], state)

    def test_shorter_promise_does_not_shorten(self):
        f = fixture(); f['records'][0]['policy']['retention']['legacy_full'] = dict(status='known', deadline='2026-03-01T00:00:00Z', provenance='fictional')
        self.assertEqual(self.record(f)['expiry'], '2026-05-31T12:00:00.000000Z')

    def test_unknown_legacy_even_during_paid_period(self):
        for now in ['2026-01-31T11:59:59Z', '2026-09-01T00:00:00Z']:
            f = fixture(now); f['records'][0]['policy']['retention']['legacy_full'] = {'status': 'unknown'}
            out = self.record(f); self.assertEqual(out['state'], 'unknown'); self.assertEqual(out['restore_action'], 'HOLD'); self.assertIsNone(out['expiry'])

    def test_missing_conflicting_and_invalid_deadlines_hold(self):
        mutations = [lambda r:r.pop('policy'),
                     lambda r:r['policy']['retention'].pop('paid_access_end'),
                     lambda r:r['policy']['retention']['legacy_full'].pop('provenance'),
                     lambda r:r.update(recorded_expiry='2026-04-01T00:00:00Z'),
                     lambda r:r['policy']['period'].update(payment_status='unknown'),
                     lambda r:r['policy']['period'].update(end='2025-01-01T00:00:00Z'),
                     lambda r:r['policy'].update(business_id='fictional-B'),
                     lambda r:r.update(exceptions=[{'reason':'unresolved hold'}]),
                     lambda r:r['policy']['retention'].update(full_present=False)]
        for fn in mutations:
            with self.subTest(mutation=mutations.index(fn)):
                f = fixture(); fn(f['records'][0]); out=self.record(f)
                self.assertEqual(out['state'], 'unknown'); self.assertEqual(out['restore_action'], 'HOLD')

    def test_future_pending_period_grants_no_paid_access(self):
        for status in ['pending', 'failed']:
            f=fixture(); f['records'][0]['policy']['period'].update(start='2026-02-01T00:00:00Z', end='2026-03-01T00:00:00Z', payment_status=status)
            self.assertEqual(self.record(f)['state'], 'read_only')

    def test_missing_stale_or_untrusted_ledger_quarantines(self):
        edits=[lambda f:f.pop('deletion_ledger'),
               lambda f:f['deletion_ledger'].update(complete_through='2026-02-01T11:59:59Z'),
               lambda f:f['deletion_ledger'].update(complete_through='2026-02-01T12:00:01Z'),
               lambda f:f['deletion_ledger'].update(authoritative=False),
               lambda f:f['deletion_ledger'].update(independent_of_snapshot=False),
               lambda f:f['deletion_ledger'].update(covered_business_ids=[])]
        for i,fn in enumerate(edits):
            with self.subTest(case=i):
                f=fixture();fn(f);out=self.record(f);self.assertEqual(out['state'],'read_only');self.assertEqual(out['restore_action'],'HOLD');self.assertTrue(out['quarantine_required']);self.assertEqual(out['deletion_history'],'unresolved')

    def test_deletion_newer_than_snapshot_suppresses_and_is_scoped(self):
        for scope, action in [('all','SUPPRESS-ON-RESTORE'),('full','SUPPRESS-ON-RESTORE'),('lightweight','SUPPRESS-ON-RESTORE')]:
            f=fixture();f['deletion_ledger']['entries']=[tombstone(scope=scope)];self.assertEqual(self.record(f)['restore_action'],action)

    def test_full_deletion_on_lightweight_parent_reaches_nested_imagery(self):
        f=fixture();root=f['records'][0];root['scope']='lightweight'
        rev=copy.deepcopy(root);rev.update(kind='revision',id='rev-1',parent_id='estimate-1')
        image=copy.deepcopy(root);image.update(kind='imagery',id='image-1',scope='full',parent_id='rev-1')
        f['records'] += [rev,image];f['deletion_ledger']['entries']=[tombstone(scope='full')]
        result={r['id']:r for r in self.run_plan(f)['records']}
        self.assertEqual(result['estimate-1']['restore_action'],'READ-ONLY')
        self.assertEqual(result['rev-1']['restore_action'],'READ-ONLY')
        self.assertEqual(result['image-1']['restore_action'],'SUPPRESS-ON-RESTORE')

    def test_deletion_of_other_business_cannot_suppress(self):
        f=fixture();f['deletion_ledger']['entries']=[tombstone(business='fictional-B')];self.assertEqual(self.record(f)['restore_action'],'READ-ONLY')

    def test_duplicate_and_out_of_order_deletion_events(self):
        f=fixture();e=tombstone();e2=tombstone(record='unused');e2.update(event_id='delete-2',sequence=2)
        f['deletion_ledger']['entries']=[e,e2,e];a=self.run_plan(f)
        f['deletion_ledger']['entries']=[e2,e];self.assertEqual(a,self.run_plan(f))

    def test_conflicting_events_held_not_guessed(self):
        for field,val in [('scope','lightweight'),('kind','draft_closed')]:
            f=fixture();e=tombstone();e2=dict(e);e2[field]=val;f['deletion_ledger']['entries']=[e,e2]
            self.assertEqual(self.record(f)['restore_action'],'HOLD')

    def test_future_or_missing_sequence_events_held(self):
        for change in [{'effective_at':'2027-01-01T00:00:00Z'}, {'sequence':None}, {'provenance':''}, {'sequence':True}]:
            f=fixture();e=tombstone();e.update(change);f['deletion_ledger']['entries']=[e];self.assertEqual(self.record(f)['restore_action'],'HOLD')

    def test_different_event_ids_same_sequence_hold(self):
        f=fixture();a=tombstone();b=dict(a,event_id='delete-2');f['deletion_ledger']['entries']=[a,b]
        self.assertEqual(self.record(f)['restore_action'],'HOLD')

    def test_malformed_legacy_mapping_is_a_review_not_crash(self):
        for value in [None, [], 'missing']:
            f=fixture();f['records'][0]['policy']['retention']['legacy_full']=value
            self.assertEqual(self.record(f)['restore_action'],'HOLD')

    def test_parent_deletion_quarantines_every_linked_revision_and_media(self):
        f=fixture();parent=f['records'][0]
        for kind, rid, pid in [('revision','rev-1','estimate-1'),('imagery','image-1','rev-1'),('imagery','image-2','estimate-1')]:
            r=copy.deepcopy(parent);r.update(kind=kind,id=rid,parent_id=pid);f['records'].append(r)
        f['deletion_ledger']['entries']=[tombstone()];o=self.run_plan(f)
        self.assertTrue(all(r['quarantine_required'] for r in o['records']));self.assertFalse(o['restore_release_recommended'])
        f['records'].reverse();self.assertEqual(o,self.run_plan(f))

    def test_parent_missing_cross_business_and_cycles_hold(self):
        for variant in ['missing','foreign','cycle','wrong_kind']:
            f=fixture();r=copy.deepcopy(f['records'][0]);r.update(id='image-1',kind='imagery',parent_id='missing');f['records'].append(r)
            if variant=='foreign':f['records'][0].update(id='missing',business_id='fictional-B')
            if variant=='cycle':r['parent_id']='image-1'
            if variant=='wrong_kind':f['records'][0].update(id='missing',kind='imagery',parent_id='image-1')
            item=next(v for v in self.run_plan(f)['records'] if v['id']=='image-1');self.assertEqual(item['restore_action'],'HOLD')

    def test_duplicate_inventory_identity_held(self):
        f=fixture();f['records'].append(copy.deepcopy(f['records'][0]));self.assertEqual(self.record(f)['restore_action'],'HOLD')

    def test_draft_rolling_clock_and_boundary(self):
        for now, state in [('2026-02-01T23:59:59.999999Z','active'),('2026-02-02T00:00:00Z','expired')]:
            f=fixture(now);f['records']=[dict(business_id='fictional-A',id='draft-1',kind='draft',principal='owner:fictional-A',last_accepted_at='2026-02-01T00:00:00Z',expires_at='2026-02-02T00:00:00Z',clock_provenance='fictional-server-ack',closed=False,save_operation='save-1',last_retry_at=now)]
            self.assertEqual(self.record(f)['state'],state)

    def test_closed_draft_and_replayed_operation_never_restore(self):
        f=fixture();f['records']=[dict(business_id='fictional-A',id='draft-1',kind='draft',principal='owner:fictional-A',last_accepted_at='2026-02-01T00:00:00Z',clock_provenance='fictional-ack',closed=True,save_operation='save-1')]
        self.assertEqual(self.record(f)['restore_action'],'SUPPRESS-ON-RESTORE')
        f['records'][0]['closed']=False;e=tombstone(record='draft-1');e['kind']='draft_closed';f['deletion_ledger']['entries']=[e];self.assertEqual(self.record(f)['restore_action'],'SUPPRESS-ON-RESTORE')

    def test_draft_inconsistent_expiry_missing_clock_or_tombstone_state_hold(self):
        base=dict(business_id='fictional-A',id='draft-1',kind='draft',principal='owner:fictional-A',last_accepted_at='2026-02-01T00:00:00Z',clock_provenance='fictional',closed=False,save_operation=None)
        for field,value in [('expires_at','2026-02-03T00:00:00Z'),('last_accepted_at',None),('closed',None),('last_accepted_at','2026-03-01T00:00:00Z')]:
            f=fixture();r=dict(base);r[field]=value;f['records']=[r];self.assertEqual(self.record(f)['state'],'unknown')

    def test_inventory_still_flags_restore_risk(self):
        f=fixture(mode='inventory');f.pop('deletion_ledger');r=self.record(f);self.assertEqual(r['proposed_action'],'READ-ONLY');self.assertEqual(r['restore_action'],'HOLD');self.assertTrue(r['quarantine_required'])

    def test_invalid_top_level_contract_rejected(self):
        for change in [{'now':'2026-02-01'}, {'mode':'delete'}, {'snapshot_at':'2027-01-01T00:00:00Z'}, {'schema':True}]:
            f=fixture();f.update(change)
            with self.assertRaises((PlannerInputError,ValueError)):self.run_plan(f)

    def test_successful_reactivation_preserves_longer_retained_content(self):
        f=fixture('2026-07-01T00:00:00Z');p=f['records'][0]['policy'];p['period'].update(id='period-2',start='2026-06-30T00:00:00Z',end='2026-07-30T00:00:00Z');p['reactivation']=dict(payment_status='succeeded',confirmed_at='2026-06-30T00:00:00Z',period_id='period-2');p['retention']['legacy_full']=dict(status='known',deadline='2026-08-01T00:00:00Z',provenance='fictional-longer-promise')
        self.assertEqual(self.record(f)['state'],'active');f['deletion_ledger']['entries']=[tombstone()];self.assertEqual(self.record(f)['restore_action'],'SUPPRESS-ON-RESTORE')


if __name__ == '__main__':
    unittest.main()
