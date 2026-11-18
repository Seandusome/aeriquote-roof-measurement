"""Real Flask application routes, disposable local SQLite, fictional sessions.
No browser, provider calls, Stripe or actual credentials. Flag OFF by default.
"""
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.request


class EnforcementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='aq-subscription-enforcement-')
        cls.root=Path(cls.tmp.name)
        assert list(cls.root.iterdir())==[]  # Verify isolated target before ANY write.
        cls.seed=cls.root/'seed.sqlite'
        os.environ.update(DATABASE_URL='',ESTIMATE_DB_PATH=str(cls.seed),FLASK_SECRET_KEY='fictional-local-test-only',GOOGLE_API_KEY='',GOOGLE_MAPS_API_KEY='',MAPBOX_ACCESS_TOKEN='',RESEND_API_KEY='')
        cls.network=patch.object(urllib.request,'urlopen',side_effect=AssertionError('External network prohibited in subscription QA'))
        cls.network.start()
        cls.a=importlib.import_module('app')  # Full real startup, only on NEW QA DB.
        assert cls.a.DATABASE_URL=='' and Path(cls.a.ESTIMATE_DB)==cls.seed
        assert cls.a.app.config['SUBSCRIPTION_ACCESS_QA'] is False
        con=sqlite3.connect(cls.seed)
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
        from qa_estimate_fixture import price_fixture
        from measurement_integrity import polygon_sqft
        points=[[0,0],[0,.0001],[.0001,.0001],[.0001,0]];qty=polygon_sqft(points)
        cls.payload=price_fixture(dict(address='Fictional Lot A',customer_name='Fictional QA Customer',quote=dict(businessType='paving',measurementMode='area',areaSqFt=qty,commercialAreas=[dict(points=points,sqft=qty,rate=.85)])))
        cls.payload['street_image_data']='data:image/png;base64,FICTIONAL-IMAGE-SENTINEL'
        for did,plan,comp in [('qa-a','basic',0),('qa-b','basic',0),('qa-comp','basic',1),('qa-dealer','legacy',0),('qa-office','legacy',0)]:
            con.execute('INSERT INTO dealers(id,dealer_name,email,password_hash,state,status,lookup_limit,estimate_limit,created_at,plan_code,industry) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(did,'Fictional '+did,did+'@example.invalid','fictional-not-a-login','','active',25,25,'2026-01-01T00:00:00Z',plan,'paving'))
            con.execute('INSERT INTO account_allowances(dealer_id,complimentary,lookup_bonus,estimate_bonus) VALUES(?,?,?,?)',(did,comp,7,11))
            con.execute('INSERT INTO dealer_usage VALUES(?,?)',(did,3))
            con.execute('INSERT INTO estimates(id,created_at,customer_name,customer_phone,customer_email,address,total_area,total_price,payload,dealer_id) VALUES(?,?,?,?,?,?,?,?,?,?)',('estimate-'+did,'2026-01-02T00:00:00Z','Fictional QA','','','Fictional Lot A',cls.payload['total_area'],cls.payload['total_price'],json.dumps(cls.payload),did))
        con.execute("INSERT INTO account_admin_roles VALUES('qa-office')")
        for eid,did,status in [('qa-employee','qa-a','active'),('qa-disabled','qa-a','disabled'),('qa-foreign-employee','qa-b','active')]:
            con.execute('INSERT INTO dealer_employees VALUES(?,?,?,?,?,?,?)',(eid,did,'Fictional Employee',eid+'@example.invalid','fictional-not-a-login',status,'2026-01-01T00:00:00Z'))
        con.commit();con.close()
        cls.observations=[]
        if os.environ.get('SUBSCRIPTION_QA_EVIDENCE_DIR'):
            root=Path(os.environ['SUBSCRIPTION_QA_EVIDENCE_DIR']);root.mkdir(parents=True,exist_ok=True)
            with sqlite3.connect(cls.seed) as source,sqlite3.connect(root/'fictional-seed.sqlite') as target:source.backup(target)

    @classmethod
    def tearDownClass(cls):
        if os.environ.get('SUBSCRIPTION_QA_EVIDENCE_DIR'):
            Path(os.environ['SUBSCRIPTION_QA_EVIDENCE_DIR'],'request-results.json').write_text(json.dumps(cls.observations,indent=2))
        cls.network.stop();cls.tmp.cleanup()

    def setUp(self):
        self.db=self.root/(self.id().split('.')[-1]+'.sqlite')
        with sqlite3.connect(self.seed) as src,sqlite3.connect(self.db) as dst:src.backup(dst)
        self.a.ESTIMATE_DB=str(self.db)
        con=self.a.estimate_db();con.close()  # Complete schema before state baseline.
        from subscription_access_qa import MARKER
        self.db.with_suffix('.qa-marker').write_text(MARKER)
        self.facts={}
        for did in ('qa-a','qa-b','qa-comp','qa-dealer','qa-office'):
            self.facts[did]=dict(schema=1,business_id=did,now='2026-01-15T00:00:00Z',security_eligible=True,
                period=dict(id='fictional-period',start='2026-01-01T00:00:00Z',end='2026-02-01T00:00:00Z',renewal_anchor='2026-01-01T00:00:00Z',plan='basic',payment_status='succeeded'),
                used=dict(lookups=3,estimates=1),extras=dict(lookups=7,estimates=11),upgrades=[],
                retention=dict(paid_access_end='2026-02-01T00:00:00Z',legacy_full={'status':'none'},legacy_lightweight={'status':'none'},full_present=True,lightweight_present=True))
        self.a.app.config.update(TESTING=True,SUBSCRIPTION_ACCESS_QA=True,SUBSCRIPTION_QA_DATABASE=str(self.db),SUBSCRIPTION_QA_POLICY_PROVIDER=lambda did:copy.deepcopy(self.facts.get(did)))
        self.client=self.a.app.test_client();self.login()

    def login(self,did='qa-a',employee=None):
        with self.client.session_transaction() as s:
            s.clear();s.update(dealer_id=did,account_type='employee' if employee else 'owner',auth_version=0)
            if employee:s['employee_id']=employee

    def state(self):
        con=sqlite3.connect(self.db)
        tables=[x[0] for x in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        result={t:con.execute('SELECT * FROM '+t+' ORDER BY rowid').fetchall() for t in tables};con.close()
        return result

    def unchanged(self,method,path,expected,**kwargs):
        before=self.state();response=getattr(self.client,method)(path,**kwargs)
        after=self.state()
        self.observations.append(dict(test=self.id(),method=method,path=path,expected=expected,actual=response.status_code,policy=response.headers.get('X-AeriQuote-QA-Subscription'),before_sha256=hashlib.sha256(json.dumps(before,sort_keys=True).encode()).hexdigest(),after_sha256=hashlib.sha256(json.dumps(after,sort_keys=True).encode()).hexdigest()))
        self.assertEqual(response.status_code,expected,(path,response.get_data(as_text=True)[:500]));self.assertEqual(before,after,path+' changed rows')
        return response

    def test_default_off_and_missing_qa_marker_are_inert(self):
        self.facts['qa-a']['now']='2026-06-01T00:00:00Z'
        self.a.app.config['SUBSCRIPTION_ACCESS_QA']=False
        self.a.app.config['SUBSCRIPTION_QA_POLICY_PROVIDER']=lambda _:(_ for _ in ()).throw(AssertionError('Must not run when OFF'))
        r=self.unchanged('get','/api/estimates/estimate-qa-a',200);self.assertNotIn('X-AeriQuote-QA-Subscription',r.headers)
        self.unchanged('get','/qa/subscription-policy',404)
        self.a.app.config['SUBSCRIPTION_ACCESS_QA']=True;self.a.app.config['SUBSCRIPTION_QA_DATABASE']='not-this-database'
        self.unchanged('get','/api/estimates/estimate-qa-a',200)

    def test_active_and_cancel_pending_access(self):
        for now in ['2026-01-15T00:00:00Z','2026-01-31T23:59:59.999999Z']:
            self.facts['qa-a']['now']=now;self.facts['qa-a']['cancellation']={'requested_at':'2026-01-10T00:00:00Z'}
            self.unchanged('get','/api/estimates/estimate-qa-a',200)
            self.unchanged('post','/api/estimates',200,json=self.payload) # Unchanged save, no debit/revision.
            self.unchanged('get','/api/account/profile',200)

    def test_read_only_saved_views_export_and_denied_direct_writes(self):
        self.facts['qa-a']['now']='2026-02-01T00:00:00Z'
        for path in ['/api/estimates','/api/estimates/estimate-qa-a','/api/estimates/estimate-qa-a/versions','/api/account/profile']:
            self.unchanged('get',path,200)
        r=self.unchanged('get','/qa/subscription/estimates/estimate-qa-a/download',200)
        self.assertIn('attachment',r.headers['Content-Disposition']);self.assertEqual(r.get_json(),self.payload)
        for path in ['/api/estimates','/api/estimates/estimate-qa-a/editing-session','/api/estimates/estimate-qa-a/status','/api/estimates/estimate-qa-a/scheduled-date','/api/estimates/estimate-qa-a/completion-date','/api/estimates/estimate-qa-a/amount-paid','/property','/property/accept','/address-preview','/api/account/profile','/manual-report-map/token','/saved-estimate-report-map']:
            self.unchanged('post',path,403,json=self.payload)
        for method,path in [('put','/api/workspace-drafts/fictional-draft-0001'),('delete','/api/workspace-drafts/fictional-draft-0001'),('get','/api/workspace-drafts'),('get','/rgb/fictional-token')]:
            self.unchanged(method,path,403,json={})

    def test_exact_expiry_and_just_before(self):
        self.facts['qa-a']['now']='2026-05-31T23:59:59.999999Z'
        self.unchanged('get','/qa/subscription/estimates/estimate-qa-a/download',200)
        self.facts['qa-a']['now']='2026-06-01T00:00:00Z'
        for path in ['/api/estimates','/api/estimates/estimate-qa-a','/api/estimates/estimate-qa-a/versions','/api/account/profile','/qa/subscription/estimates/estimate-qa-a/download']:
            self.unchanged('get',path,403)
        self.unchanged('post','/api/estimates',403,json=self.payload)
        self.assertEqual(self.unchanged('get','/qa/subscription-policy',200).get_json()['state'],'expired')

    def test_reactivation_preserves_usage_and_extras_and_saved_work(self):
        f=self.facts['qa-a'];f['now']='2026-06-15T00:00:00Z';f['period'].update(id='resubscribed',start='2026-06-01T00:00:00Z',end='2026-07-01T00:00:00Z')
        f['retention']['legacy_full']={'status':'known','deadline':'2026-08-01T00:00:00Z'}
        f['reactivation']={'payment_status':'succeeded','confirmed_at':'2026-06-01T00:00:00Z','period_id':'resubscribed'}
        for _ in range(3):
            self.unchanged('get','/api/estimates/estimate-qa-a',200)
            self.unchanged('post','/api/estimates',200,json=self.payload)
            self.unchanged('get','/qa/subscription/estimates/estimate-qa-a/download',200)

    def test_unknown_data_flags_without_changing_existing_access(self):
        for kind in ['legacy','payment','missing','provider-error']:
            f=self.facts['qa-a'];f['now']='2026-06-15T00:00:00Z'
            if kind=='legacy':f['retention']['legacy_full']={'status':'unknown'}
            if kind=='payment':del f['period']['payment_status']
            if kind=='missing':self.a.app.config['SUBSCRIPTION_QA_POLICY_PROVIDER']=lambda _:None
            if kind=='provider-error':self.a.app.config['SUBSCRIPTION_QA_POLICY_PROVIDER']=lambda _:1/0
            r=self.unchanged('get','/api/estimates/estimate-qa-a',200)
            self.assertEqual(r.headers['X-AeriQuote-QA-Subscription'],'unknown')
            self.unchanged('post','/api/estimates',200,json=self.payload)

    def test_business_isolation_and_disabled_employee_still_apply(self):
        self.facts['qa-a']['now']='2026-02-10T00:00:00Z'
        self.unchanged('get','/api/estimates/estimate-qa-b',404)
        self.unchanged('get','/api/estimates/estimate-qa-b/versions',404)
        self.unchanged('get','/qa/subscription/estimates/estimate-qa-b/download',404)
        self.unchanged('get','/api/account/profile',409,headers={'X-AeriQuote-Account':'qa-b'})
        self.login(employee='qa-employee');self.unchanged('get','/qa/subscription/estimates/estimate-qa-a/download',200)
        con=sqlite3.connect(self.db);con.execute("UPDATE dealer_employees SET status='disabled' WHERE id='qa-employee'");con.commit();con.close()
        self.unchanged('get','/qa/subscription/estimates/estimate-qa-a/download',302)
        self.login(employee='qa-disabled');self.unchanged('post','/api/estimates',401,json=self.payload)
        self.login(employee='qa-foreign-employee');self.unchanged('get','/api/estimates/estimate-qa-a',401)

    def test_complimentary_and_legacy_dealers_preserve_existing_access(self):
        for did in ['qa-comp','qa-dealer']:
            self.login(did);self.facts[did]['now']='2027-01-01T00:00:00Z'
            self.unchanged('get','/api/estimates/estimate-'+did,200)
            self.unchanged('post','/api/estimates',200,json=self.payload)
            r=self.unchanged('get','/qa/subscription/estimates/estimate-'+did+'/download',200)
            self.assertEqual(r.headers['X-AeriQuote-QA-Subscription'],'existing_dealer_access')

    def test_head_office_and_mismatched_policy(self):
        self.login('qa-office');self.unchanged('get','/api/estimates/estimate-qa-a',403);self.unchanged('get','/qa/subscription/estimates/estimate-qa-a/download',403)
        self.login();self.a.app.config['SUBSCRIPTION_QA_POLICY_PROVIDER']=lambda _:self.facts['qa-b']
        r=self.unchanged('get','/api/estimates/estimate-qa-a',200);self.assertEqual(r.headers['X-AeriQuote-QA-Subscription'],'unknown')

    def test_active_changed_edit_saves_one_revision_with_no_allowance_change(self):
        before=self.state();payload=copy.deepcopy(self.payload);payload['customer_name']='Fictional Updated Customer'
        response=self.client.post('/api/estimates',json=payload);self.assertEqual(response.status_code,200)
        after=self.state();self.assertEqual(len(after['estimate_revisions']),len(before['estimate_revisions'])+1)
        for table in before:
            if table not in {'estimates','estimate_revisions'}:self.assertEqual(before[table],after[table],table)
        self.assertEqual(self.client.get('/api/estimates/estimate-qa-a').get_json()['payload']['customer_name'],'Fictional Updated Customer')

    def test_longer_promise_and_lightweight_only_are_not_silently_shortened(self):
        f=self.facts['qa-a'];f['now']='2026-07-01T00:00:00Z'
        f['retention']['legacy_full']={'status':'known','deadline':'2026-08-01T00:00:00Z'}
        self.unchanged('get','/api/estimates/estimate-qa-a',200)
        self.unchanged('post','/api/estimates',403,json=self.payload)
        f['now']='2026-08-01T00:00:00Z';self.unchanged('get','/api/estimates/estimate-qa-a',403)
        f['retention']['legacy_lightweight']={'status':'known','deadline':'2027-01-01T00:00:00Z'}
        r=self.unchanged('get','/api/estimates/estimate-qa-a',200)
        self.assertEqual(r.headers['X-AeriQuote-QA-Subscription'],'retained_read_only')
        self.assertEqual(r.get_json()['payload']['customer_name'],'Fictional QA Customer')
        self.assertNotIn('street_image_data',r.get_json()['payload'])
        download=self.unchanged('get','/qa/subscription/estimates/estimate-qa-a/download',200)
        self.assertNotIn('street_image_data',download.get_json())
        self.unchanged('get','/api/account/profile',403)
        self.unchanged('post','/api/estimates',403,json=self.payload)

    def test_client_headers_cannot_override_expiry_or_enable_gate(self):
        self.facts['qa-a']['now']='2026-06-01T00:00:00Z'
        self.unchanged('get','/api/estimates/estimate-qa-a',403,headers={'X-AeriQuote-QA-Subscription':'paid_active'})
        self.unchanged('post','/api/estimates',403,json={**self.payload,'subscription_state':'paid_active'})
        self.a.app.config['SUBSCRIPTION_ACCESS_QA']=False
        self.unchanged('get','/api/estimates/estimate-qa-a',200,headers={'X-AeriQuote-QA-Subscription':'expired'})

    def test_saved_map_export_authorization_uses_owned_frozen_geometry(self):
        from flask import Response
        from subscription_access_qa import saved_roofs
        self.facts['qa-a']['now']='2026-02-01T00:00:00Z'
        roofs=saved_roofs(self.payload)
        # Renderer stub isolates access control; no actual imagery/PDF claim.
        with patch.dict(self.a.app.view_functions,{'saved_estimate_report_map':lambda:Response(b'fictional-renderer-output',content_type='image/png')}):
            self.unchanged('post','/saved-estimate-report-map',200,json={'roofs':roofs})
            integers=copy.deepcopy(roofs)
            for point in integers[0]['points']:
                for coordinate in point:
                    if point[coordinate]==0:point[coordinate]=0
            self.unchanged('post','/saved-estimate-report-map',200,json={'roofs':integers})
            altered=copy.deepcopy(roofs);altered[0]['points'][0]['lat']=.00005
            self.unchanged('post','/saved-estimate-report-map',403,json={'roofs':altered})
            self.facts['qa-a']['now']='2026-06-01T00:00:00Z'
            self.unchanged('post','/saved-estimate-report-map',403,json={'roofs':roofs})


if __name__=='__main__':unittest.main(verbosity=2)
