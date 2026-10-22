"""QA vector access, actual saved/reopened geometry, no provider/credit writes."""
import os,sys,tempfile,json,subprocess,math
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from measurement_integrity import polygon_sqft,line_feet
with tempfile.TemporaryDirectory() as tmp:
 os.environ['DATABASE_URL']='';os.environ['ESTIMATE_DB_PATH']=tmp+'/vector.db'
 import app as a
 con=a.estimate_db()
 for owner in ['vector-qa','not-qa']:
  con.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,status,created_at) VALUES(?,? ,?,'unused','active','2026-10-22')",(owner,'QA ONLY',owner+'@example.invalid'))
  con.execute('INSERT INTO account_allowances(dealer_id,complimentary) VALUES(?,1)',(owner,))
 con.commit();con.close();c=a.app.test_client()
 def login(owner):
  with c.session_transaction() as s:s.update(dealer_id=owner,account_type='owner',auth_version=0)
 login('vector-qa')
 assert c.get('/qa-vector-diagram.js').status_code==404
 with patch.dict(os.environ,{'AERIQUOTE_VECTOR_PDF_QA':'1','AERIQUOTE_VECTOR_PDF_QA_IDS':'vector-qa'}),patch.object(a,'req_json',side_effect=AssertionError('Vector must not call providers')):
  assert 'value="vector"' in c.get('/').text
  script=c.get('/qa-vector-diagram.js');assert script.status_code==200 and 'no-store' in script.headers['Cache-Control']
  login('not-qa');assert 'value="vector"' not in c.get('/').text;assert c.get('/qa-vector-diagram.js').status_code==404;assert c.post('/qa-vector-diagram/validate',json={}).status_code==404
  login('vector-qa');assert c.post('/qa-vector-diagram/validate',json={}).status_code==400
  base=[[52,-106],[52,-105.9999],[52.0001,-105.9999],[52.0001,-106]]
  line=[[52,-106],[52.0002,-106]]
  for industry in ['roofing','commercial','snow','pressure','paving','landscaping']:
   q={'businessType':industry,'measurementMode':'area','structures':[],'manualPlanes':[],'commercialAreas':[{'name':'QA area','sqft':polygon_sqft(base),'points':base,'rate':.2}], 'areaSqFt':polygon_sqft(base),'areaPoints':[],'linearPoints':line,'linearFeet':line_feet(line),'commercialLinearSaved':True,'commercialLinearRate':.7,'landscapingLinearRate':.7,'pressureLinearRate':.7,'pavingLinearRate':.7}
   if industry=='roofing':q.update(measurementMode='auto',measureSource='manual',commercialAreas=[],areaSqFt=0,areaPoints=[],linearPoints=[],linearFeet=0,manualPlanes=[{'points':base,'pitch_degrees':30,'surface_sqft':polygon_sqft(base)/math.cos(math.pi/6)}])
   payload={'quote':q,'address':'QA VECTOR DO NOT SEND','business_type':industry,'total_area':polygon_sqft(base),'total_price':0,'pricing':{'mode':'regular','price':.2,'gst':5,'pst':6,'disc':0,'extraAmount':25.5,'estimatePeriod':'one_time'}}
   payload=json.loads(subprocess.check_output(['node','scripts/price_fixtures.cjs'],input=json.dumps([payload]).encode()))[0]
   saved=c.post('/api/estimates',json=payload);assert saved.status_code==200,saved.json
   eid=saved.json['id'];data=c.get('/api/estimates/'+str(eid)).json['payload'];before=json.dumps(data,sort_keys=True)
   assert c.post('/qa-vector-diagram/validate',json={'quote':data['quote']}).status_code==200
   again=c.get('/api/estimates/'+str(eid)).json['payload'];assert json.dumps(again,sort_keys=True)==before,'Export validation never edits an estimate'
   bad=json.loads(before);bad['quote']['manualPlanes'][0].update(surface_sqft=1) if industry=='roofing' else bad['quote']['commercialAreas'][0].update(sqft=1);assert c.post('/qa-vector-diagram/validate',json={'quote':bad['quote']}).status_code==400
  login('not-qa');assert c.post('/qa-vector-diagram/validate',json={'quote':q}).status_code==404
 print('PASS vector default off/double opt-in/account isolation; actual six-industry save/reopen, independent server geometry validation, mismatch rejection, immutable saved estimates and zero provider calls')
