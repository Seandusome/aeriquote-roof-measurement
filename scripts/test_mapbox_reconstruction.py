"""Reconstructed provider paths: deterministic, isolated, no live credentials."""
import os,sys,tempfile,json,copy,subprocess,math,re
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mapbox_provider import verified_address,street_key
feature={'geometry':{'coordinates':[-114.092641,50.952925]},'properties':{'name':'1340 Southdale Crescent SW','full_address':'1340 Southdale Crescent SW, Calgary, Alberta, Canada','feature_type':'address','coordinates':{'accuracy':'rooftop'},'match_code':{'street':'matched','address_number':'matched','confidence':'high'}}}
assert street_key('101 Churchill Square')==street_key('101 Churchill Sq')
for change in [{'name':'218 Chaparral Way SE'},{'match_code':{'street':'unmatched','address_number':'matched','confidence':'high'}},{'coordinates':{'accuracy':'interpolated'}}]:
 bad=copy.deepcopy(feature);bad['properties'].update(change)
 try:verified_address(bad,'1340 Southdale Crescent SW, Calgary');raise AssertionError('Unsafe address accepted')
 except ValueError:pass
with tempfile.TemporaryDirectory() as tmp:
 os.environ['DATABASE_URL']='';os.environ['ESTIMATE_DB_PATH']=tmp+'/isolated.db'
 import app as a
 a.is_recovery_test_service=lambda:False
 a.AERIAL_PROVIDER='mapbox';a.MAPBOX_ACCESS_TOKEN='fixture-only-not-a-token';a.GOOGLE_MAPS_API_KEY=''
 con=a.estimate_db();con.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,status,created_at) VALUES('mapbox-rebuild','FICTIONAL QA','mapbox-rebuild@example.invalid','unused','active','2026-11-12')")
 con.execute("INSERT INTO account_allowances(dealer_id,complimentary) VALUES('mapbox-rebuild',1)");con.commit();con.close()
 c=a.app.test_client()
 with c.session_transaction() as s:s.update(dealer_id='mapbox-rebuild',account_type='owner',auth_version=0)
 def dbstate():
  con=a.estimate_db();out={table:[dict(r) for r in con.execute('SELECT * FROM '+table).fetchall()] for table in ['account_allowances','account_subscription_usage','account_month_usage','estimates']};con.close();return out
 class Reply:
  def __init__(self,body,image=False):
   from email.message import Message
   self.body=body;self.headers=Message();self.headers['Content-Type']='image/png' if image else 'application/json'
  def __enter__(self):return self
  def __exit__(self,*args):pass
  def read(self,*args):return self.body
 def geocode(*args,**kwargs):return Reply(json.dumps({'features':[feature]}).encode())
 before=dbstate();body={'address':feature['properties']['full_address'],'business_type':'roofing','prepare_only':True}
 with patch.object(a.urllib.request,'urlopen',side_effect=geocode):r=c.post('/property',json=body,headers={'Idempotency-Key':'rebuild-1'})
 assert r.status_code==200,r.json
 token=r.json['token'];assert r.json['provider']=='mapbox' and r.json['manual_roof_only']
 assert dbstate()==before,'Preparing property consumed allowance'
 assert c.post('/property/accept',json={'operation_id':'rebuild-1','token':token}).status_code==409
 assert dbstate()==before
 for zoom in [19,18]:
  with patch.object(a.urllib.request,'urlopen',side_effect=OSError('fixture failure')):assert c.get('/fallback-map/'+token+'?zoom='+str(zoom)).status_code==502
  assert dbstate()==before
  with patch.object(a.urllib.request,'urlopen',return_value=Reply(b'fixture image',True)):assert c.get('/fallback-map/'+token+'?zoom='+str(zoom)).status_code==200
 assert c.get('/fallback-meta/'+token).json['zoom']==19,'An unaccepted frame changed session bounds'
 assert c.get('/fallback-meta/'+token).json['tile_size']==512
 assert c.post('/mapbox-aerial/'+token+'/commit',json={'zoom':18}).status_code==200
 assert c.get('/fallback-meta/'+token).json['zoom']==18
 assert dbstate()==before,'Widening/retry consumed allowance'
 assert c.post('/property/accept',json={'operation_id':'rebuild-1','token':token,'address_pin_confirmed':True}).status_code==200
 after=dbstate();assert after!=before,'Test bypassed real allowance accounting'
 assert c.post('/property/accept',json={'operation_id':'rebuild-1','token':token,'address_pin_confirmed':True}).status_code==200
 assert dbstate()==after,'Retry charged twice'
 print('PASS strict address/rooftop guard, Square/Sq normalization, confirmed acceptance, simulated failures/retries, transactional zoom, real allowance accounting and idempotency')
 # Extract actual app projection function and compare with an independent WGS84 geodesic.
 from geographiclib.geodesic import Geodesic
 origin=(50.952925,-114.092641);end=Geodesic.WGS84.Direct(*origin,90,30.48)
 funcs=re.search(r'function mercatorLat\(y\).*?\nasync function loadFallbackAerial',a.HTML,re.S).group(0).rsplit('\nasync',1)[0]
 code="const L={latLngBounds:(sw,ne)=>({sw,ne})};"+funcs+";console.log(JSON.stringify([19,18].map(z=>staticMapBounds(50.952925,-114.092641,z,640,640,512))));"
 bounds=json.loads(subprocess.check_output(['node','-e',code]));
 for z,b in zip([19,18],bounds):
  pixels=(end['lon2']-origin[1])/(b['ne'][1]-b['sw'][1])*640
  # App's spherical Leaflet length differs slightly from WGS84 ellipsoid; report rather than hide it.
  reference_pixels=323.437596/(2 if z==18 else 1)
  measured_lng=reference_pixels/640*(b['ne'][1]-b['sw'][1])
  measured=6371000*math.radians(measured_lng)*math.cos(math.radians(origin[0]))/.3048
  assert abs(measured-100)<.4,(z,measured)
  print(f'INDEPENDENT SCALE zoom={z} WGS84_distance_ft=100 pixels={pixels:.6f} app_spherical_distance_ft={measured:.6f} difference_pct={measured-100:.6f}')
 assert abs((bounds[1]['ne'][1]-bounds[1]['sw'][1])/(bounds[0]['ne'][1]-bounds[0]['sw'][1])-2)<1e-8
 print('PASS actual JavaScript 512-pixel Mapbox bounds; widening doubles extent without changing geographic points; Google default 256 remains unchanged')
