"""Fictional snapshot tests only. No application/database/provider imports."""
import copy
import json
import unittest
from datetime import timedelta
from standalone_policy import evaluate, instant, stamp, monthly_boundary


def fixture():
    return dict(schema=1, business_id='fictional-business-alpha', now='2026-01-20T12:00:00Z',
                security_eligible=True,
                saved_work=dict(customer='Fictional Test Customer',rate='0.85',pitch='5/12',
                                outline=[[1,1],[3,1],[3,3]],image_reference='fictional-image-sentinel'),
                period=dict(id='fictional-period-1', start='2026-01-01T00:00:00Z',
                            end='2026-02-01T00:00:00Z', renewal_anchor='2026-01-01T00:00:00Z',
                            plan='basic', payment_status='succeeded'),
                retention=dict(paid_access_end='2026-02-01T00:00:00Z',
                               legacy_full=dict(status='none'), legacy_lightweight=dict(status='none'),
                               full_present=True, lightweight_present=True),
                used=dict(lookups=23, estimates=20), extras=dict(lookups=7, estimates=11), upgrades=[])


def upgrade(consumed=(0, 0)):
    return dict(id='fictional-upgrade-1', business_id='fictional-business-alpha', attribution_source='fictional-unit-ledger-1', period_id='fictional-period-1',
                from_plan='basic', to_plan='pro', payment_status='succeeded',
                confirmed_at='2026-01-15T00:00:00Z',
                consumed=dict(zip(('lookups', 'estimates'), consumed)), reversals=[])


def reverse():
    return dict(id='fictional-reversal-1', status='succeeded', kind='full',
                confirmed_at='2026-01-19T00:00:00Z')


class PolicyTests(unittest.TestCase):
    def check(self, snapshot):
        before = json.dumps(snapshot, sort_keys=True)
        result = evaluate(snapshot)
        self.assertEqual(before, json.dumps(snapshot, sort_keys=True), 'Input mutated')
        self.assertEqual(result, evaluate(snapshot), 'Not deterministic')
        return result

    def test_initial_snapshot_and_output_independence(self):
        s = fixture(); r = self.check(s)
        self.assertFalse(r['review_required']); self.assertEqual(r['access']['state'], 'paid_active')
        self.assertEqual(r['entitlements']['remaining_monthly'], dict(lookups=2, estimates=5))
        r['entitlements']['extras']['lookups'] = 999
        self.assertEqual(s['extras']['lookups'], 7)

    def test_paid_end_and_exact_expiry(self):
        s = fixture(); end = instant(s['period']['end']); expiry = end + timedelta(days=120)
        for now, expected in [(end-timedelta(milliseconds=1), 'paid_active'), (end, 'retained_read_only'),
                              (end+timedelta(milliseconds=1), 'retained_read_only'),
                              (expiry-timedelta(milliseconds=1), 'retained_read_only'),
                              (expiry, 'expired'), (expiry+timedelta(milliseconds=1), 'expired')]:
            with self.subTest(now=now):
                s['now'] = stamp(now); r = self.check(s)
                self.assertEqual(r['access']['state'], expected)
                self.assertEqual(r['access']['base_expiry'], '2026-06-01T00:00:00.000000Z')
                self.assertEqual(r['access']['can_create_or_edit'], expected == 'paid_active')

    def test_month_end_original_day_and_leap_year(self):
        for anchor, expected in [('2026-01-31T18:30:00Z', ['2026-02-28T18:30:00.000000Z','2026-03-31T18:30:00.000000Z']),
                                 ('2028-01-31T18:30:00Z', ['2028-02-29T18:30:00.000000Z','2028-03-31T18:30:00.000000Z'])]:
            self.assertEqual([monthly_boundary(anchor, i) for i in (1,2)], expected)
        s=fixture();s['period'].update(start='2026-02-28T18:30:00Z',end='2026-03-31T18:30:00Z',renewal_anchor='2026-01-31T18:30:00Z');s['now']='2026-03-15T00:00:00Z'
        self.assertEqual(self.check(s)['schedule']['following_boundary'],'2026-04-30T18:30:00.000000Z')

    def test_offset_normalization_and_elapsed_days(self):
        s=fixture();s['retention']['paid_access_end']='2026-03-01T12:00:00-06:00'
        a=self.check(s)['access']['base_expiry'];s['retention']['paid_access_end']='2026-03-01T18:00:00Z'
        self.assertEqual(a,self.check(s)['access']['base_expiry'])
        self.assertEqual(instant(a)-instant(s['retention']['paid_access_end']),timedelta(seconds=10368000))

    def test_naive_invalid_and_missing_instants_flagged(self):
        for value in ['2026-01-20T12:00:00','invalid',None]:
            s=fixture();s['now']=value;r=self.check(s);self.assertTrue(r['review_required']);self.assertIsNone(r['access'])
        s=fixture();del s['retention']['paid_access_end'];self.assertTrue(self.check(s)['review_required'])

    def test_unknown_legacy_never_expires_by_inference(self):
        s=fixture();s['now']='2027-02-01T00:00:00Z';s['retention']['legacy_full']={'status':'unknown'}
        r=self.check(s);self.assertTrue(r['review_required']);self.assertEqual(r['access']['state'],'review_required')
        self.assertIsNone(r['access']['full_expiry']);self.assertIsNone(r['access']['lightweight_expiry'])
        self.assertFalse(r['access']['can_download_full'])

    def test_separate_longer_promises(self):
        s=fixture();s['retention'].update(legacy_full=dict(status='known',deadline='2026-08-01T00:00:00Z'),legacy_lightweight=dict(status='known',deadline='2027-02-01T00:00:00Z'))
        s['now']='2026-09-01T00:00:00Z';r=self.check(s)
        self.assertEqual(r['access']['state'],'retained_read_only');self.assertFalse(r['access']['readable_scopes']['full']);self.assertTrue(r['access']['readable_scopes']['lightweight'])
        self.assertFalse(r['access']['can_download_full'])

    def test_known_shorter_promise_cannot_shorten_base(self):
        s=fixture();s['retention']['legacy_full']=dict(status='known',deadline='2026-03-01T00:00:00Z')
        self.assertEqual(self.check(s)['access']['full_expiry'],'2026-06-01T00:00:00.000000Z')

    def test_pending_failed_upgrades_preserve_existing_plan(self):
        for state in ['pending','failed']:
            s=fixture();e=upgrade();e['payment_status']=state;del e['consumed'];del e['confirmed_at'];s['upgrades']=[e]
            r=self.check(s);self.assertFalse(r['review_required']);self.assertEqual(r['entitlements']['plan'],'basic');self.assertEqual(r['entitlements']['caps']['lookups'],25)

    def test_basic_to_pro_preserves_used_extras_and_renewal(self):
        s=fixture();s['upgrades']=[upgrade()];r=self.check(s)['entitlements']
        self.assertEqual(r['remaining_monthly'],dict(lookups=52,estimates=55));self.assertEqual(r['used'],s['used']);self.assertEqual(r['extras'],s['extras']);self.assertEqual(r['renewal_at'],'2026-02-01T00:00:00.000000Z')

    def test_duplicate_event_is_not_double_grant(self):
        s=fixture();s['upgrades']=[upgrade()];once=self.check(s);s['upgrades']*=3
        self.assertEqual(once,self.check(s))

    def test_conflicting_duplicate_is_review_not_guess(self):
        s=fixture();a=upgrade();b=copy.deepcopy(a);b['consumed']['lookups']=1;s['upgrades']=[a,b]
        r=self.check(s);self.assertTrue(r['review_required']);self.assertIsNone(r['entitlements']);self.assertFalse(r['access']['can_create_or_edit'])

    def test_partly_consumed_upgrade_reversal(self):
        s=fixture();s['used']=dict(lookups=33,estimates=26);e=upgrade((10,6));e['reversals']=[reverse()];s['upgrades']=[e]
        r=self.check(s)['entitlements'];self.assertEqual(r['caps'],dict(lookups=35,estimates=31));self.assertEqual(r['remaining_monthly'],dict(lookups=2,estimates=5))
        self.assertEqual(r['upgrades'][0]['removed_unused'],dict(lookups=40,estimates=44));self.assertEqual(r['extras'],dict(lookups=7,estimates=11));self.assertEqual(r['used'],s['used'])

    def test_zero_and_fully_consumed_upgrade_reversals(self):
        for n in (0,50):
            s=fixture();s['used']=dict(lookups=25+n,estimates=25+n);e=upgrade((n,n));e['reversals']=[reverse()];s['upgrades']=[e]
            r=self.check(s)['entitlements'];self.assertEqual(r['remaining_monthly'],dict(lookups=0,estimates=0));self.assertEqual(r['upgrades'][0]['removed_unused']['lookups'],50-n)
            self.assertTrue(all(x>=0 for x in r['caps'].values()));self.assertEqual(r['extras'],s['extras'])

    def test_repeated_reversal_removed_once(self):
        s=fixture();e=upgrade();e['reversals']=[reverse()]*3;s['upgrades']=[e]
        self.assertEqual(self.check(s)['entitlements']['caps']['lookups'],25)

    def test_pending_failed_reversal_no_entitlement_change(self):
        for status in ['pending','failed']:
            s=fixture();e=upgrade();rv=reverse();rv['status']=status;e['reversals']=[rv];s['upgrades']=[e]
            self.assertEqual(self.check(s)['entitlements']['caps']['lookups'],75)

    def test_missing_impossible_or_bool_attribution_flagged(self):
        for attr in [None,dict(lookups=51,estimates=0),dict(lookups=True,estimates=0),dict(lookups=24,estimates=0)]:
            s=fixture();e=upgrade()
            if attr is None:del e['consumed']
            else:e['consumed']=attr
            s['upgrades']=[e];self.assertTrue(self.check(s)['review_required'])

    def test_partial_and_cross_period_reversals_flagged(self):
        for update in [dict(kind='partial'),dict(confirmed_at='2026-02-02T00:00:00Z')]:
            s=fixture();s['now']='2026-02-03T00:00:00Z';e=upgrade();rv=reverse();rv.update(update);e['reversals']=[rv];s['upgrades']=[e];self.assertTrue(self.check(s)['review_required'])

    def test_multiple_paid_upgrades_attributed_and_reversed_chain_flagged(self):
        s=fixture();a=upgrade();b=upgrade();b.update(id='fictional-upgrade-2',from_plan='pro',to_plan='business',confirmed_at='2026-01-18T00:00:00Z');s['upgrades']=[a,b]
        self.assertEqual(self.check(s)['entitlements']['remaining_monthly']['lookups'],177)
        a['reversals']=[reverse()];self.assertTrue(self.check(s)['review_required'])

    def test_no_allowance_for_unconfirmed_new_period(self):
        for status in ['pending','failed']:
            s=fixture();s['period']['payment_status']=status;r=self.check(s)
            self.assertIsNone(r['entitlements']);self.assertTrue(r['review_required']);self.assertIsNone(r['access'])

    def test_cancel_retains_paid_access_and_stops_next_renewal(self):
        s=fixture();s['cancellation']=dict(requested_at='2026-01-10T00:00:00Z');r=self.check(s)
        self.assertEqual(r['access']['state'],'paid_active');self.assertFalse(r['schedule']['renewal_scheduled']);self.assertIsNone(r['schedule']['next_renewal_at']);self.assertEqual(r['schedule']['cancellation_effective_at'],'2026-02-01T00:00:00.000000Z')

    def test_downgrade_only_next_successful_renewal(self):
        s=fixture();s['upgrades']=[upgrade()];s['downgrade']='basic';r=self.check(s)
        self.assertEqual(r['entitlements']['caps']['lookups'],75);self.assertEqual(r['schedule']['next_plan_if_success'],'basic');self.assertTrue(r['schedule']['downgrade_requires_successful_renewal']);self.assertFalse(r['schedule']['reset_applied'])

    def reactivate(self, full_present=True, light_present=True):
        s=fixture();s['now']='2026-07-15T00:00:00Z';s['period'].update(id='fictional-resub-period',start='2026-07-01T00:00:00Z',end='2026-08-01T00:00:00Z',renewal_anchor='2026-07-01T00:00:00Z')
        s['reactivation']=dict(payment_status='succeeded',confirmed_at='2026-07-01T00:00:00Z',period_id='fictional-resub-period');s['retention'].update(full_present=full_present,lightweight_present=light_present)
        return s

    def test_after120_reactivation_restores_longer_retained_work(self):
        s=self.reactivate();s['retention']['legacy_full']=dict(status='known',deadline='2026-09-01T00:00:00Z');r=self.check(s)
        self.assertEqual(r['access']['state'],'paid_active');self.assertTrue(r['access']['restored_scopes']['full']);self.assertEqual(r['entitlements']['used'],s['used']);self.assertEqual(r['entitlements']['extras'],s['extras'])

    def test_within_window_reactivation_and_login_no_reset(self):
        s=self.reactivate();s['retention']['paid_access_end']='2026-06-01T00:00:00Z';r=self.check(s)
        self.assertTrue(r['access']['restored_scopes']['full']);self.assertEqual(r,self.check(s))
        s['now']='2026-07-16T00:00:00Z';later=self.check(s)
        self.assertEqual(r['access']['base_expiry'],later['access']['base_expiry']);self.assertEqual(r['entitlements'],later['entitlements'])

    def test_deleted_work_never_promised_recovered(self):
        s=self.reactivate(False,False);r=self.check(s)
        self.assertEqual(r['access']['state'],'paid_active');self.assertFalse(r['access']['restored_scopes']['full']);self.assertFalse(r['access']['can_download_full']);self.assertFalse(r['access']['recovery_of_deleted_work'])

    def test_confirmation_exact_deadline_not_within_window(self):
        s=self.reactivate();s['reactivation']['confirmed_at']='2026-06-01T00:00:00Z'
        self.assertFalse(self.check(s)['access']['reactivation_eligible']['full'])

    def test_unknown_legacy_reactivation_flagged(self):
        s=self.reactivate();s['retention']['legacy_full']=dict(status='unknown');r=self.check(s)
        self.assertTrue(r['review_required']);self.assertIsNone(r['access']['reactivation_eligible']['full'])

    def test_security_denial_does_not_become_reactivated_permission(self):
        s=self.reactivate();s['security_eligible']=False;r=self.check(s)
        self.assertEqual(r['access']['state'],'denied');self.assertFalse(r['access']['can_create_or_edit']);self.assertFalse(r['access']['can_download_full'])

    def test_business_snapshots_remain_independent(self):
        a=fixture();b=fixture();b.update(business_id='fictional-business-beta',extras=dict(lookups=0,estimates=0))
        self.assertNotEqual(self.check(a)['entitlements']['extras'],self.check(b)['entitlements']['extras']);self.assertEqual(a['extras']['lookups'],7)

    def test_bad_monthly_period_and_future_event_need_review(self):
        s=fixture();s['period']['end']='2026-02-02T00:00:00Z';self.assertTrue(self.check(s)['review_required'])
        s=fixture();e=upgrade();e['confirmed_at']='2026-01-25T00:00:00Z';s['upgrades']=[e];self.assertTrue(self.check(s)['review_required'])

    def test_independent_attribution_matrix(self):
        # Independently count the base units left and unused purchased units.
        # 26 base-consumption values x 51 upgrade-consumption values x 2 states.
        for base_used in range(26):
            for consumed in range(51):
                for reversed_ in (False, True):
                    s=fixture();s['used']=dict(lookups=base_used+consumed,estimates=base_used+consumed)
                    e=upgrade((consumed,consumed));e['reversals']=[reverse()] if reversed_ else [];s['upgrades']=[e]
                    r=self.check(s)
                    self.assertFalse(r['review_required'])
                    expected=(25-base_used)+(0 if reversed_ else 50-consumed)
                    self.assertEqual(r['entitlements']['remaining_monthly']['lookups'],expected)
                    self.assertEqual(r['entitlements']['remaining_with_extras']['estimates'],expected+11)

    def test_pending_failed_reactivation_does_not_restore_expired_work(self):
        for status in ('pending','failed'):
            s=self.reactivate();s['reactivation']={'payment_status':status}
            # Existing separately-confirmed current paid period can create NEW work,
            # but pending reactivation cannot resurrect expired OLD content.
            r=self.check(s);self.assertFalse(r['access']['restored_scopes']['full']);self.assertFalse(r['access']['can_download_full'])

    def test_longer_lightweight_only_reactivation(self):
        s=self.reactivate(False,True);s['retention']['legacy_lightweight']=dict(status='known',deadline='2027-02-01T00:00:00Z')
        r=self.check(s);self.assertFalse(r['access']['restored_scopes']['full']);self.assertTrue(r['access']['restored_scopes']['lightweight'])

    def test_invalid_event_containers_and_schema_flagged(self):
        for events in (None,[None],['not a record'],{}):
            s=fixture();s['upgrades']=events;self.assertTrue(self.check(s)['review_required'])
        for schema in (None,True,2):
            s=fixture();s['schema']=schema;self.assertTrue(self.check(s)['review_required'])
        self.assertTrue(evaluate(None)['review_required'])

    def test_reactivation_wrong_period_or_future_confirmation_flagged(self):
        for change in (dict(period_id='different-period'),dict(confirmed_at='2026-08-02T00:00:00Z')):
            s=self.reactivate();s['reactivation'].update(change);self.assertTrue(self.check(s)['review_required'])

    def test_new_period_success_does_not_itself_reset_input_usage(self):
        s=fixture();s['period'].update(id='fictional-period-2',start='2026-02-01T00:00:00Z',end='2026-03-01T00:00:00Z');s['now']='2026-02-10T00:00:00Z'
        r=self.check(s);self.assertFalse(r['review_required']);self.assertFalse(r['schedule']['reset_applied']);self.assertEqual(r['entitlements']['used'],s['used'])

    def test_future_cancellation_and_duplicate_reversal_conflict_flagged(self):
        s=fixture();s['cancellation']=dict(requested_at='2027-01-01T00:00:00Z');self.assertTrue(self.check(s)['review_required'])
        s=fixture();e=upgrade();rv=reverse();other=copy.deepcopy(rv);other['status']='failed';e['reversals']=[rv,other];s['upgrades']=[e];self.assertTrue(self.check(s)['review_required'])

    def test_second_plan_delta_and_invalid_chain(self):
        s=fixture();s['period']['plan']='pro';s['used']=dict(lookups=70,estimates=60);e=upgrade();e.update(from_plan='pro',to_plan='business');s['upgrades']=[e]
        self.assertEqual(self.check(s)['entitlements']['remaining_monthly']['lookups'],130)
        e['from_plan']='basic';self.assertTrue(self.check(s)['review_required'])

    def test_attribution_provenance_and_business_required(self):
        for field in ('business_id','attribution_source'):
            s=fixture();e=upgrade();del e[field];s['upgrades']=[e];self.assertTrue(self.check(s)['review_required'])
        s=fixture();e=upgrade();e['business_id']='fictional-business-beta';s['upgrades']=[e];self.assertTrue(self.check(s)['review_required'])

    def test_candidate_eligibility_without_payment_does_not_restore(self):
        s=fixture();s['now']='2026-04-01T00:00:00Z';r=self.check(s)
        self.assertTrue(r['access']['reactivation_candidate_scopes']['full'])
        self.assertFalse(r['access']['restored_scopes']['full'])
        self.assertFalse(r['access']['can_create_or_edit'])
        s['now']='2026-06-01T00:00:00Z'
        self.assertFalse(self.check(s)['access']['reactivation_candidate_scopes']['full'])


if __name__=='__main__':unittest.main(verbosity=2)
