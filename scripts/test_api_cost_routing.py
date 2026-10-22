"""Record actual route provider URLs, no paid requests or customer database."""
import os,sys,tempfile,copy
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory() as tmp:
 os.environ['DATABASE_URL']='';os.environ['ESTIMATE_DB_PATH']=tmp+'/qa.db'
 import app as a
 a.GOOGLE_MAPS_API_KEY='qa-unused'
 con=a.estimate_db();con.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,status,created_at) VALUES('cost-qa','QA ONLY','cost-qa@example.invalid','unused','active','2026-10-22')");con.execute("INSERT INTO account_allowances(dealer_id,complimentary) VALUES('cost-qa',1)");con.commit();con.close()
 c=a.app.test_client()
 with c.session_transaction() as s:s.update(dealer_id='cost-qa',account_type='owner',auth_version=0)
 calls=[]
 def provider(url):
  calls.append(url)
  if 'geocode/json' in url:return 200,{'status':'OK','results':[{'formatted_address':'2301 Ave C North, Saskatoon, SK','address_components':[{'types':['street_number'],'long_name':'2301'},{'types':['route'],'long_name':'Ave C North'},{'types':['locality'],'long_name':'Saskatoon'},{'types':['administrative_area_level_1'],'short_name':'SK'}],'geometry':{'location':{'lat':52,'lng':-106}}}]}
  if 'buildingInsights' in url:return 200,{'name':'buildings/qa','center':{'latitude':52,'longitude':-106},'solarPotential':{'wholeRoofStats':{'areaMeters2':100,'groundAreaMeters2':80},'buildingStats':{'groundAreaMeters2':80},'roofSegmentStats':[{'stats':{'areaMeters2':100},'pitchDegrees':30,'azimuthDegrees':180}]}}
  if 'dataLayers' in url:return 200,{'rgbUrl':'https://example.invalid/rgb','maskUrl':'https://example.invalid/mask'}
  if 'streetview/metadata' in url:return 200,{'status':'ZERO_RESULTS'}
  raise AssertionError(url)
 def count(part):return sum(part in u for u in calls)
 with patch.object(a,'req_json',side_effect=provider):
  for industry in ['snow','pressure','paving','landscaping','commercial','roofing']:
   for mode in (['area','linear','auto'] if industry=='roofing' else ['area','linear']):
    for direct in [False,True]:
     calls.clear();body={'key':'qa-unused','address':'QA rural coordinates' if direct else '2301 Ave C North, Saskatoon, SK','business_type':industry,'measurement_mode':mode,'prepare_only':True}
     body.update({'direct_coordinates':True,'latitude':52,'longitude':-106} if direct else {'expected_city':'Saskatoon','expected_province':'SK','expected_street_number':'2301'})
     operation=f'cost-{industry}-{mode}-{direct}';r=c.post('/property',json=body,headers={'Idempotency-Key':operation});assert r.status_code==200,r.json
     if industry=='snow' and mode=='area' and not direct:first={'operation_id':operation,'token':r.json['token']}
     expected=1 if industry=='roofing' or '--baseline' in sys.argv else 0
     assert count('buildingInsights')==expected,(industry,mode,direct,'Insights',calls)
     assert count('dataLayers')==expected,(industry,mode,direct,'Layers',calls)
     assert count('geocode/json')==(0 if direct else 1)
     if industry=='roofing':assert r.json['main']['segments'][0]['pitch_degrees']==30 and r.json['main']['total_roof_sqft']>1000
     elif '--baseline' not in sys.argv:
      assert r.json['fallback'] and r.json['fallback_aerial']=='static' and 'main' not in r.json
      with a.app.test_request_context('/'):
       a.session['dealer_id']='cost-qa';sess=a.SESSIONS.get(r.json['token']);assert sess['rgb'] is None and sess['mask'] is None
     print(industry,mode,'pin' if direct else 'address','Solar:',count('buildingInsights'),count('dataLayers'))
  if '--baseline' not in sys.argv:
   from account_credits import month_key
   def used():
    con=a.estimate_db()
    try:
     row=con.execute("SELECT lookups FROM account_month_usage WHERE dealer_id='cost-qa' AND period=?",(month_key(),)).fetchone();return row['lookups'] if row else 0
    finally:con.close()
   assert used()==0,'All imagery preparations remain uncharged'
   assert c.post('/property/accept',json=first).status_code==200;assert used()==1
   assert c.post('/property/accept',json=first).status_code==200;assert used()==1
   # Existing report renderer falls back to /rgb if its Static Maps request fails.
   calls.clear()
   with patch.object(a,'req_bytes',return_value=('image/tiff',b'qa-original-raster')):
    fallback=c.get('/rgb/'+first['token']);assert fallback.status_code==200,fallback.data
    assert fallback.data==b'qa-original-raster' and count('buildingInsights')==1 and count('dataLayers')==1
    assert c.get('/rgb/'+first['token']).data==fallback.data
    assert count('buildingInsights')==1 and count('dataLayers')==1
    a.SESSIONS.pop(first['token'],None)
    assert c.get('/rgb/'+first['token']).data==fallback.data,'Fallback metadata survives a new worker/session cache'
    assert count('buildingInsights')==1 and count('dataLayers')==1
   assert used()==1,'Image recovery never changes subscription credit accounting'
   for invalid in ['unknown',[],42]:
    calls.clear();r=c.post('/property',json={'key':'qa','address':'QA','business_type':invalid});assert r.status_code==400 and not calls
   calls.clear();r=c.post('/property',json={'key':'qa','address':'999 Ave C North, Saskatoon, SK','business_type':'landscaping','expected_city':'Saskatoon','expected_province':'SK','expected_street_number':'999'});assert r.status_code==409 and count('buildingInsights')==0 and count('dataLayers')==0
 print('PASS actual URL-level Solar call inventory, all six industries, Area/Linear, rural coordinates and validated addresses'+(' BASELINE' if '--baseline' in sys.argv else ', malformed industry and address mismatch rejection'))
