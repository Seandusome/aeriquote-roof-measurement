import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from qa_policy_fixtures import create
from qa_policy_view import FixtureReader, app_guard_probe, provisional_usage_probe, render, serve


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='aq-disposable-policy-qa-')
        self.root=create(Path(self.tmp.name)/'fixture')
        self.before=self.hashes()
        self.reader=FixtureReader(self.root)

    def hashes(self):
        return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.iterdir() if p.is_file()}

    def tearDown(self):
        self.assertEqual(self.before,self.hashes(),'Read-only QA changed a fixture file')
        self.tmp.cleanup()

    def test_required_access_states_and_exact_deadlines(self):
        expected={'active':('paid_active','2026-11-29T00:00:00.000000Z'),
                  'cancellation-pending':('paid_active','2026-11-29T00:00:00.000000Z'),
                  'read-only':('retained_read_only','2026-07-30T00:00:00.000000Z'),
                  'expired':('expired','2026-06-01T00:00:00.000000Z'),
                  'reactivated':('paid_active','2026-10-01T00:00:00.000000Z'),
                  'unknown-legacy':('review_required',None),'missing-payment':('unknown',None),
                  'missing-retention':('unknown',None),'disabled':('denied','2026-11-29T00:00:00.000000Z')}
        for case,(state,expiry) in expected.items():
            with self.subTest(case=case):
                result=self.reader.evaluate('qa-fictional-'+case)
                self.assertEqual((result['state'],result['expiry']),(state,expiry))
                self.assertFalse(result['deletion_authorized']);self.assertFalse(result['enforcement_enabled'])
        result=self.reader.evaluate('qa-fictional-cancellation-pending')['calculated']
        self.assertFalse(result['schedule']['renewal_scheduled'])
        self.assertEqual(result['schedule']['cancellation_effective_at'],'2026-08-01T00:00:00.000000Z')
        self.assertTrue(self.reader.evaluate('qa-fictional-reactivated')['calculated']['access']['restored_scopes']['full'])

    def test_mapping_uses_database_balances_not_sidecar_defaults(self):
        snapshot,gaps=self.reader.snapshot('qa-fictional-active')
        self.assertEqual(gaps,[]);self.assertEqual(snapshot['used'],{'lookups':3,'estimates':2})
        self.assertEqual(snapshot['extras'],{'lookups':7,'estimates':11})
        self.assertEqual(snapshot['period']['plan'],'basic')

    def test_missing_payment_and_retention_never_guessed(self):
        for name in ['missing-payment','missing-retention']:
            result=self.reader.evaluate('qa-fictional-'+name)
            self.assertIsNone(result['calculated']);self.assertTrue(result['missing_facts']);self.assertFalse(result['deletion_authorized'])

    def test_existing_guard_conflicts_are_component_execution_not_enforcement(self):
        for name in ['active','cancellation-pending','read-only','expired','reactivated','unknown-legacy','missing-payment','missing-retention']:
            probe=app_guard_probe(self.reader,'qa-fictional-'+name)
            self.assertEqual(probe['observations'],{'GET':'guard_allows','POST':'guard_allows'})
        self.assertEqual(app_guard_probe(self.reader,'qa-fictional-disabled')['observations'],{'GET':'guard_denies','POST':'guard_denies'})

    def test_provisional_app_usage_is_not_confirmed_payment(self):
        result=provisional_usage_probe(self.reader,'qa-fictional-missing-payment')
        self.assertEqual(result['basis'],'account_anniversary_provisional')
        self.assertEqual(result['lookups'],3);self.assertEqual(result['limit'],25)
        self.assertEqual(self.reader.evaluate('qa-fictional-missing-payment')['state'],'unknown')

    def test_sqlite_defenses_reject_every_write_class(self):
        con=self.reader.connect()
        try:
            for sql in ['UPDATE dealers SET status="disabled"','DELETE FROM estimates','CREATE TABLE bad(x)','ATTACH DATABASE ":memory:" AS other','PRAGMA query_only=OFF']:
                with self.assertRaises(sqlite3.DatabaseError):con.execute(sql)
        finally:con.close()

    def test_allowlist_unknown_account_and_target_protection(self):
        with self.assertRaises(KeyError):self.reader.evaluate('actual-business')
        with self.assertRaises(ValueError):create(self.root)
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(FileNotFoundError):FixtureReader(t)

    def test_http_is_get_only_and_has_no_app_routes(self):
        server=serve(self.reader);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_port)
        try:
            with urllib.request.urlopen(base+'/qa/policy') as response:
                text=response.read().decode();self.assertIn('READ ONLY',text);self.assertIn('UNKNOWN',text);self.assertEqual(response.headers['Cache-Control'],'no-store')
            with urllib.request.urlopen(base+'/qa/policy/qa-fictional-expired.json') as response:self.assertEqual(json.load(response)['state'],'expired')
            for method,path,expected in [('POST','/qa/policy',405),('DELETE','/qa/policy',405),('GET','/api/estimates',404),('GET','/qa/policy/other.json',404)]:
                with self.assertRaises(urllib.error.HTTPError) as err:urllib.request.urlopen(urllib.request.Request(base+path,method=method))
                self.assertEqual(err.exception.code,expected)
        finally:server.shutdown();server.server_close();thread.join()

    def test_html_escapes_qa_text(self):
        row=self.reader.evaluate('qa-fictional-active');row['case']='<script>alert(1)</script>'
        text=render([row]);self.assertNotIn('<script>',text);self.assertIn('&lt;script&gt;',text)


if __name__=='__main__':unittest.main(verbosity=2)
