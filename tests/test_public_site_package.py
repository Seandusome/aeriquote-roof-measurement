"""Website routes/packaging only. No app startup, DB, credentials or payments."""
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from flask import Flask,Response,send_from_directory,redirect,request
from scripts.check_public_site_package import inspect

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=Path(os.environ.get('AQ_SITE_PACKAGE_EVIDENCE',tempfile.mkdtemp(prefix='aq-site-evidence-')))
EVIDENCE.mkdir(parents=True,exist_ok=True)
SOURCE=(ROOT/'app.py').read_text();TREE=ast.parse(SOURCE)
PAGES=ast.literal_eval(next(n for n in TREE.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='PUBLIC_SITE_PAGES' for x in n.targets)).value.args[0])
FALLBACK=ast.literal_eval(next(n for n in TREE.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='PUBLIC_SITE_UNAVAILABLE' for x in n.targets)).value)

def harness(site):
    names={'_public_site_package_ready','_serve_site_resource','public_site_home','public_page_redirect','public_site_file','require_dealer_login'}
    nodes=[n for n in ast.parse(SOURCE).body if isinstance(n,ast.FunctionDef) and n.name in names]
    for n in nodes:n.decorator_list=[]
    env=dict(os=os,json=json,hashlib=hashlib,SITE_DIR=str(site),PUBLIC_SITE_UNAVAILABLE=FALLBACK,PUBLIC_SITE_PAGES=set(PAGES),Response=Response,send_from_directory=send_from_directory,redirect=redirect,request=request)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'actual_public_route_functions','exec'),env)
    app=Flask('isolated_public_routes');app.before_request(env['require_dealer_login'])
    app.add_url_rule('/site/',view_func=env['public_site_home'])
    app.add_url_rule('/site/<path:filename>',view_func=env['public_site_file'])
    return app

class Package(unittest.TestCase):
    def setUp(self):
        self.path=EVIDENCE/self._testMethodName;self.path.mkdir(exist_ok=False)
    def copy_without(self,missing):
        dest=self.path/'site';dest.mkdir()
        for f in (ROOT/'site').rglob('*'):
            name=str(f.relative_to(ROOT/'site'))
            if f.is_file() and name not in missing:
                target=dest/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,target)
        return dest
    def assert_safe(self,response):
        self.assertEqual(response.status_code,503);self.assertEqual(response.headers['Cache-Control'],'no-store')
        for text in ['USD $29/month','USD $59/month','USD $99/month','25 property lookups','75 property lookups','200 property lookups','payments unavailable','Stripe work is paused','Policy draft']:
            self.assertIn(text,response.text)
        for text in ['<input','SUBSCRIBE &','Secure Checkout','50 property measurements','150 property measurements','300 property measurements']:
            self.assertNotIn(text,response.text)
    def test_complete_package_hashes_and_all_public_routes(self):
        result=inspect(ROOT/'site');self.assertTrue(result['passed']);self.assertEqual(result['checked'],71)
        rows=[]
        with harness(ROOT/'site').test_client() as c:
            for name in PAGES:
                r=c.get('/site/'+name)
                if name=='login':self.assertEqual(r.status_code,308);continue
                self.assertEqual(r.status_code,200,name)
                self.assertEqual(r.data,(ROOT/'site'/(name+'.html')).read_bytes())
                rows.append({'page':name,'status':r.status_code,'disk_bytes_match':True});r.close()
            for name in json.loads((ROOT/'site/public-package.json').read_text())['files']:
                r=c.get('/site/'+name,follow_redirects=False)
                if name=='index.html' or (name.endswith('.html') and name[:-5] in PAGES):self.assertEqual(r.status_code,308)
                else:self.assertEqual(r.status_code,200,name)
                r.close()
        (self.path/'normal-routes.json').write_text(json.dumps({'manifest':result,'pages':rows},indent=2))
    def test_missing_pricing_and_checkout_fail_closed(self):
        site=self.copy_without({'pricing.html','checkout.html'})
        self.assertEqual(set(inspect(site)['missing']),{'pricing.html','checkout.html'})
        with harness(site).test_client() as c:
            self.assert_safe(c.get('/site/pricing'));self.assert_safe(c.get('/site/checkout'))
            self.assert_safe(c.get('/site/'))
    def test_missing_styles_or_logo_fail_closed(self):
        site=self.copy_without({'styles.css','assets/aeriquote-logo.png'})
        with harness(site).test_client() as c:
            self.assert_safe(c.get('/site/pricing'));self.assert_safe(c.get('/site/privacy-policy'))
            for name in ['styles.css','assets/aeriquote-logo.png']:
                r=c.get('/site/'+name);self.assertEqual(r.status_code,404);self.assertNotIn('data:image',r.text)
    def test_missing_policy_or_onboarding_fails_closed(self):
        site=self.copy_without({'terms-of-use.html','trial-signup.html','roofer-setup.html'})
        with harness(site).test_client() as c:
            for name in ['terms-of-use','trial-signup','roofer-setup','refund-cancellation']:
                self.assert_safe(c.get('/site/'+name))
    def test_missing_manifest_or_entire_site(self):
        site=self.copy_without({'public-package.json'})
        with harness(site).test_client() as c:self.assert_safe(c.get('/site/'))
        empty=self.path/'empty';empty.mkdir()
        with harness(empty).test_client() as c:
            self.assert_safe(c.get('/site/pricing'));self.assertEqual(c.get('/site/styles.css').status_code,404)
    def test_preflight_rejects_changed_content(self):
        site=self.copy_without(set());(site/'pricing.html').write_text('Obsolete pricing fixture, never deployed')
        self.assertEqual(inspect(site)['changed'],['pricing.html'])
        with harness(site).test_client() as c:self.assert_safe(c.get('/site/pricing'))
        # Every requested HTML page is checked against its manifest hash; the
        # preflight also checks all non-HTML assets without per-request rehashing.
    def test_no_obsolete_embedded_payload_remains(self):
        names=[x.id for n in TREE.body if isinstance(n,ast.Assign) for x in n.targets if isinstance(x,ast.Name)]
        self.assertNotIn('EMBEDDED_SITE',names);self.assertNotIn('_aq_b64',SOURCE)

if __name__=='__main__':unittest.main(verbosity=2)
