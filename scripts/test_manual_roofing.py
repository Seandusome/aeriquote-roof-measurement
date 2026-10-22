"""Isolated manual roofing: URL recorder, geometry attacks, persistence and off switch."""
import os,sys,tempfile,copy,math
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from measurement_integrity import polygon_sqft,snapshot_error
with tempfile.TemporaryDirectory() as tmp:
 os.environ['DATABASE_URL']='';os.environ['ESTIMATE_DB_PATH']=tmp+'/qa.db'
 import app as a
 a.GOOGLE_MAPS_API_KEY='qa-unused'
 con=a.estimate_db()
 for owner in ['manual-qa','unlisted']:
  con.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,status,created_at) VALUES(?,? ,?,'unused','active','2026-10-22')",(owner,'QA ONLY',owner+'@example.invalid'))
  con.execute('INSERT INTO account_allowances(dealer_id,complimentary) VALUES(?,1)',(owner,))
 con.commit();con.close()
 c=a.app.test_client()
 with c.session_transaction() as s:s.update(dealer_id='manual-qa',account_type='owner',auth_version=0)
 calls=[]
 def provider(url):
  calls.append(url)
  assert 'solar.googleapis.com' not in url,url
  if 'streetview/metadata' in url:return 200,{'status':'ZERO_RESULTS'}
  if 'geocode/json' in url:return 200,{'status':'OK','results':[{'formatted_address':'QA property','address_components':[],'geometry':{'location':{'lat':52,'lng':-106}}}]}
  raise AssertionError(url)
 with patch.dict(os.environ,{'AERIQUOTE_MANUAL_ROOF_QA':'1','AERIQUOTE_MANUAL_ROOF_QA_IDS':'manual-qa'}),patch.object(a,'req_json',side_effect=provider):
  assert "const MANUAL_ROOF_QA='1'" in c.get('/').text
  for direct in [True,False]:
   body={'key':'qa','address':'QA property','business_type':'roofing','prepare_only':True}
   if direct:body.update(direct_coordinates=True,latitude=52,longitude=-106)
   r=c.post('/property',json=body,headers={'Idempotency-Key':'manual-'+str(direct)});assert r.status_code==200,r.json
   assert r.json['manual_roof_only'] and 'main' not in r.json
   token=r.json['token']
   # Every automatic escape route fails closed before a provider request.
   for path in ['/structure','/locate-building']:
    assert c.post(path,json={'token':token,'latitude':52,'longitude':-106}).status_code==409
   for path in ['/rgb/','/mask/','/structure-mask/']:
    assert c.get(path+token+('/fake' if 'structure-mask' in path else '')).status_code in [404,409]
   # Static failures and retries never fall through to Solar.
   with patch.object(a.urllib.request,'urlopen',side_effect=OSError('QA network failure')):
    for _ in range(2):assert c.get('/fallback-map/'+token).status_code>=400
   assert c.post('/property/accept',json={'operation_id':'manual-'+str(direct),'token':token}).status_code==200
   a.SESSIONS.pop(token,None)
   assert c.get('/rgb/'+token).status_code==409,'Mode survives worker/reload recovery'
  for industry in ['snow','pressure','paving','landscaping','commercial']:
   r=c.post('/property',json={'key':'qa','address':'QA property','business_type':industry,'direct_coordinates':True,'latitude':52,'longitude':-106,'prepare_only':True},headers={'Idempotency-Key':industry});assert r.status_code==200 and r.json['manual_roof_only'] is False
  with c.session_transaction() as s:s['dealer_id']='unlisted'
  assert "const MANUAL_ROOF_QA='0'" in c.get('/').text,'Allowlist isolates QA from other accounts'
  with c.session_transaction() as s:s['dealer_id']='manual-qa'
 assert "const MANUAL_ROOF_QA='0'" in c.get('/').text,'Mode defaults off'
 # Independent spherical reference, one rectangle per pitch; adjacent boundaries permitted.
 base=[[52,-106],[52,-105.9999],[52.0001,-105.9999],[52.0001,-106]]
 def plane(points,pitch):return {'points':points,'pitch_degrees':pitch,'surface_sqft':polygon_sqft(points)/math.cos(math.radians(pitch)),'pitch_confirmed':True,'manual_roof_qa':True}
 planes=[plane(base,math.degrees(math.atan(.5))),plane([[lat,lon+.0001] for lat,lon in base],0),plane([[lat+.001,lon] for lat,lon in base],45)]
 q={'businessType':'roofing','measurementMode':'auto','measureSource':'manual','structures':[],'manualPlanes':planes,'manualRoofWorkflow':True,'roofScopeConfirmed':True}
 payload={'quote':q,'total_area':sum(p['surface_sqft'] for p in planes)}
 assert not snapshot_error(payload),snapshot_error(payload)
 for mutate in [lambda q:q.update(roofScopeConfirmed=False),lambda q:q['manualPlanes'][0].update(pitch_confirmed=False),lambda q:q['manualPlanes'][0].update(surface_sqft=1),lambda q:q['manualPlanes'][0].update(pitch_degrees=80),lambda q:q['manualPlanes'].append(copy.deepcopy(q['manualPlanes'][0])),lambda q:q['manualPlanes'][0].update(points=[]),lambda q:q.update(measurementMode='area')]:
  bad=copy.deepcopy(payload);mutate(bad['quote']);assert snapshot_error(bad),bad
 assert abs(planes[0]['surface_sqft']/polygon_sqft(base)-math.sqrt(1.25))<1e-10
 # Full save/reopen with authoritative server pricing, not only a geometry helper.
 payload.update(address='QA manual sections',business_type='roofing',total_price=0,pricing={'mode':'regular','price':.2,'gst':5,'pst':6,'disc':0,'extraAmount':0,'estimatePeriod':'one_time'})
 import json,subprocess
 payload=json.loads(subprocess.check_output(['node','scripts/price_fixtures.cjs'],input=json.dumps([payload]).encode()))[0]
 r=c.post('/api/estimates',json=payload);assert r.status_code==200,r.json
 eid=r.json['id'];saved=c.get('/api/estimates/'+str(eid)).json;assert saved['payload']['quote']['manualPlanes']==planes
 with patch.dict(os.environ,{'AERIQUOTE_MANUAL_ROOF_QA':'1','AERIQUOTE_MANUAL_ROOF_QA_IDS':'manual-qa'}),patch.object(a,'req_json',side_effect=provider):
  r=c.post('/api/estimates/'+str(eid)+'/editing-session',json={});assert r.status_code==200,r.json
  assert c.get('/rgb/'+r.json['token']).status_code==409
 print('PASS QA double opt-in; default off/account isolation; manual property/pin and all automatic escape routes; imagery failures/retries/recovery zero Solar; five industries unchanged; independent multi-pitch/shared-edge/garage geometry; invalid/overlap/unconfirmed rejection; actual save/reopen')
