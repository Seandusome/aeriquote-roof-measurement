"""Check actual clean-page redirects and public access without a live account/database."""
import os,sys,tempfile,re,ast,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory() as tmp:
 os.environ['ESTIMATE_DB_PATH']=str(Path(tmp)/'public.db');os.environ['DATABASE_URL']=''
 import app as a
 client=a.app.test_client()
 assert client.get('/site/').status_code==200
 assert client.get('/').status_code==302,'Measurement workspace stays protected'
 for page in a.PUBLIC_SITE_PAGES:
  old='/site/'+page+'.html?industry=snow&source=test'
  res=client.get(old)
  assert res.status_code==308,(page,res.status_code)
  expected='/dealer-login' if page=='login' else '/site/'+page
  assert res.headers['Location']==expected+'?industry=snow&source=test'
  response=client.get(expected+'?industry=snow&source=test')
  assert response.status_code==200,(page,response.status_code)
 assert client.get('/site/index.html').headers['Location']=='/site/'
 for alias,dest in [('/pricing','/site/pricing'),('/pricing.html','/site/pricing'),('/trial-signup.html','/site/trial-signup'),('/roofer-setup.html','/site/roofer-setup')]:
  assert client.get(alias).headers['Location']==dest
 for asset in ['site-ui.css','site-ui.js','account-ui.css','help-center.css','help-center.js','assets/favicon.svg']:
  assert client.get('/site/'+asset).status_code==200
 icon=client.get('/favicon.ico');assert icon.status_code==200 and 'image/' in icon.content_type
 assert client.get('/site/nonexistent-page').status_code==404
 assert client.get('/api/estimates').status_code==401
 login=client.get('/dealer-login').get_data(as_text=True)
 assert 'name="viewport"' in login and 'for="loginEmail"' in login and '/site/account-ui.css' in login
 assert '/site/account-ui.css' in client.get('/forgot-password').get_data(as_text=True)
 # Every static inline script still parses after HTML accessibility/URL edits.
 for page in Path('site').rglob('*.html'):
  for i,script in enumerate(re.findall(r'<script[^>]*>(.*?)</script>',page.read_text(),re.S)):
   p=Path(tmp)/'inline.js';p.write_text(script);subprocess.run(['node','--check',str(p)],check=True,capture_output=True)
 print('PASS: all clean public pages, legacy/query redirects, public homepage/favicon/assets, protected workspace/API, login/recovery markup and every static inline script')
