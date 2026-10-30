"""Independent geodesic references and real isolated save-route mismatch attacks."""
import copy,json,math,os,subprocess,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from measurement_integrity import polygon_sqft,line_feet,polygons_overlap,FT2
source=Path('app.py').read_text();function=next(x for x in source.splitlines() if x.startswith('function localPolygonAreaM2('))
# WGS84 references generated with GeographicLib 2.1, not AeriQuote's formulas.
refs=[(52,-106,.001,7641.536594033241),(25,-80,.001,11182.488350570202),(60,-149,.001,6216.7124799489975),(49,-123,.000001,.008137415861710906),(52,179.999,.002,30565.808434724808)]
polys=[]
for lat,lon,size,expected in refs:
 east=(lon+size+180)%360-180
 polys.append([[lat,lon],[lat,east],[lat+size,east],[lat+size,lon]])
js=function+';console.log(JSON.stringify('+json.dumps(polys)+'.map(pts=>localPolygonAreaM2(pts.map(p=>({lat:p[0],lng:p[1]}))))));'
actual=json.loads(subprocess.check_output(['node','-e',js]))
for pts,value,reference in zip(polys,actual,refs):
 assert abs(value/reference[3]-1)<.005,(value,reference)
 assert abs(value-polygon_sqft(pts)/FT2)<max(.000001,value*.00001)
# Independent known equator distance: one degree on mean-radius sphere.
assert abs(line_feet([[0,0],[0,1]])-math.pi*6371000/180/.3048)<1e-7
base=polys[0]
def moved(dx,dy=0):return [[lat+dy,lon+dx] for lat,lon in base]
assert polygons_overlap(base,base)
assert polygons_overlap(base,moved(.0005))
assert polygons_overlap(base,moved(.0005,.0005))
assert not polygons_overlap(base,moved(.001)),'Shared boundary is not overlapping coverage'
assert not polygons_overlap(base,moved(.002))
# Concave U-shaped duplicate: the mean vertex lies outside, so centroid-only checks fail.
u=[[52,-106],[52,-105.997],[52.003,-105.997],[52.003,-105.998],[52.001,-105.998],[52.001,-105.999],[52.003,-105.999],[52.003,-106]]
assert polygons_overlap(u,u)
hole=[[52.0015,-105.9988],[52.0015,-105.9982],[52.0025,-105.9982],[52.0025,-105.9988]]
assert not polygons_overlap(u,hole)
with tempfile.TemporaryDirectory() as tmp:
 os.environ['DATABASE_URL']='';os.environ['ESTIMATE_DB_PATH']=str(Path(tmp)/'geometry.db')
 import app as a
 con=a.estimate_db();con.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,state,status,created_at) VALUES('qa-geometry','QA TEST','qa-geometry@example.invalid','unused','SK','active','2026-10-21')");con.commit();con.close()
 client=a.app.test_client()
 with client.session_transaction() as session:session.update(dealer_id='qa-geometry',account_type='owner',auth_version=0)
 sqft=round(polygon_sqft(base));length=line_feet(base[:2])
 original={'address':'QA GEOMETRY DO NOT SEND','total_area':sqft,'total_price':100,'area_sqft':sqft,'linear_feet':length,'pricing':{'total':100},'quote':{'businessType':'landscaping','measurementMode':'linear','commercialAreas':[{'points':base,'sqft':sqft,'rate':.10}],'areaSqFt':sqft,'linearFeet':length,'linearPoints':base[:2]}}
 from qa_estimate_fixture import price_fixture,automatic_roof
 price_fixture(original)
 result=client.post('/api/estimates',json=original);assert result.status_code==200,result.get_json();eid=result.get_json()['id']
 before=client.get('/api/estimates/'+eid).get_json()
 for mutation in [
  lambda p:p.pop('quote'),
  lambda p:p.update(quote={}),
  lambda p:p['quote']['commercialAreas'][0].update(sqft=1),
  lambda p:p['quote']['commercialAreas'][0].update(points=[]),
  lambda p:p['quote']['commercialAreas'].append(copy.deepcopy(p['quote']['commercialAreas'][0])),
  lambda p:p['quote']['commercialAreas'].append({'points':moved(.0005),'sqft':sqft,'rate':.1}),
  lambda p:p['quote'].update(linearFeet=1),
  lambda p:p['quote'].update(linearPoints=[]),
  lambda p:p.update(linear_feet=1),
  lambda p:p.update(total_area=1),
  lambda p:p.update(area_sqft=1),
  lambda p:p['quote'].update(areaSqFt=1),
  lambda p:p.update(quote={'businessType':'roofing','measurementMode':'auto'}),
 ]:
  p=copy.deepcopy(original);mutation(p);response=client.post('/api/estimates',json=p)
  assert response.status_code==400,response.get_json()
 assert client.get('/api/estimates/'+eid).get_json()==before
 con=a.estimate_db();assert con.execute('SELECT COUNT(*) AS n FROM estimate_revisions').fetchone()['n']==0;con.close()
 # A retraced linear segment cannot be billed twice, even with internally matching prices.
 from measurement_integrity import linear_error
 A=[52,-106];B=[52,-105.999];C=[52.001,-105.999];D=[52.001,-106]
 invalid_lines=[[A,B,A],[A,B,[52,-105.9995]],[A,B,C,D,A,B],[A,A,B]]
 valid_lines=[[A,B],[A,B,C,D,A],[A,C,B,D],[A,[52,-105.9995],B],[A,[52,-105.99999999]]]
 for pts in invalid_lines:assert linear_error(pts)
 for pts in valid_lines:assert not linear_error(pts)
 for industry in ['snow','pressure','paving','landscaping','commercial','roofing']:
  for pts in invalid_lines:
   p={'address':'QA INVALID LINE '+industry,'quote':{'businessType':industry,'measurementMode':'linear','linearPoints':pts,'linearFeet':line_feet(pts)}}
   price_fixture(p);assert client.post('/api/estimates',json=p).status_code==400
  assert client.get('/api/estimates/'+eid).get_json()==before
 # Zeroing the claimed length while retaining a real line must not remove it from pricing.
 for industry in ['snow','pressure','paving','landscaping','commercial','roofing']:
  p=copy.deepcopy(original);p['address']='QA ZERO LINE '+industry;p['quote']['businessType']=industry;p['quote']['linearFeet']=0;p['linear_feet']=0
  price_fixture(p);assert client.post('/api/estimates',json=p).status_code==400
 assert client.get('/api/estimates/'+eid).get_json()==before
 # Normal matching snapshots and shared-border multi-area work across the five surface industries.
 for industry in ['snow','pressure','paving','landscaping','commercial']:
  p=copy.deepcopy(original);p['address']='QA '+industry;p['quote']['businessType']=industry
  p['quote']['commercialAreas'].append({'points':moved(.001),'sqft':sqft,'rate':.2})
  p['quote']['areaSqFt']=p['area_sqft']=p['total_area']=sqft*2
  price_fixture(p);response=client.post('/api/estimates',json=p);assert response.status_code==200,(industry,response.get_json())
 # Manually traced pitched roofs and included garages must agree with the saved total.
 pitch=22.62;surface=polygon_sqft(base)/math.cos(math.radians(pitch))
 roof={'address':'QA ROOF DO NOT SEND','total_area':surface+500,'total_price':100,'pricing':{'area':surface+500,'total':100},'quote':{'businessType':'roofing','measurementMode':'auto','measureSource':'hybrid','manualPlanes':[{'points':[{'lat':lat,'lng':lon} for lat,lon in base],'pitch_degrees':pitch,'surface_sqft':surface}],'structures':[automatic_roof([[lat+.002,lon] for lat,lon in base])]}}
 price_fixture(roof)
 response=client.post('/api/estimates',json=roof);assert response.status_code==200,response.get_json()
 for mutation in [lambda p:p['quote']['manualPlanes'][0].update(surface_sqft=1),lambda p:p['quote']['manualPlanes'][0].update(points=[]),lambda p:p.update(total_area=surface),lambda p:p['pricing'].update(area=surface),lambda p:p['quote']['structures'].append({'total_roof_sqft':250})]:
  bad=copy.deepcopy(roof);mutation(bad);response=client.post('/api/estimates',json=bad);assert response.status_code==400,response.get_json()
print('PASS: independent WGS84 area references, tiny/dateline outlines, spherical length, duplicate/partial overlaps, shared boundaries, real Flask mismatches preserve saved records/revisions, five industry combined snapshots')
