"""Run real onboarding JS payloads through isolated signup/profile Flask endpoints."""
import os,sys,json,tempfile,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory() as tmp:
 os.environ['ESTIMATE_DB_PATH']=str(Path(tmp)/'new-users.db');os.environ['DATABASE_URL']=''
 fixtures=Path(tmp)/'profiles.json'
 subprocess.run(['node','scripts/test_onboarding_finish.cjs'],check=True,env={**os.environ,'ONBOARDING_FIXTURES_PATH':str(fixtures)})
 import app as a
 for industry,profile in json.loads(fixtures.read_text()).items():
  client=a.app.test_client()
  result=client.post('/api/public/signup',json={'name':'QA Owner','company':'QA Company','email':industry+'@example.invalid','password':'isolated-test-only','country':'United States','industry':industry})
  assert result.status_code==200,(industry,result.status_code)
  assert result.json['industry']==industry
  setup=client.get(result.json['redirect'],follow_redirects=True)
  assert setup.status_code==200 and b'of 4' in setup.data
  before=client.get('/api/account/profile').json['profile']
  assert before['businessType']==industry and before['country']=='US'
  response=client.post('/api/account/profile',json=profile);assert response.status_code==200
  actual=client.get('/api/account/profile').json['profile']
  for key in ['name','company','country','province','businessType','price','gst','pst','pricingMode','services','propertyTypes','warrantyStatement','estimateMessage','ctaHeading']:
   assert actual[key]==profile[key],(industry,key,actual.get(key),profile.get(key))
  assert client.get('/?industry='+industry).status_code==200
  assert client.get('/api/estimates').status_code==200
 print('PASS: all six new trial accounts, clean setup routes, actual shared-JS profile payloads persisted and reloaded, protected measurement workspace and saved-estimate API access')
