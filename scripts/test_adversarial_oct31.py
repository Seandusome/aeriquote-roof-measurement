"""Seeded independent geometry/pricing and real API adversarial checks; fictional data.
Shapely and GeographicLib are test-only dependencies, never application providers.
"""
import copy,json,math,os,random,sys,tempfile,uuid
from pathlib import Path
from decimal import Decimal,ROUND_HALF_UP
from shapely.geometry import Polygon
from geographiclib.geodesic import Geodesic
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from measurement_integrity import polygon_sqft,line_feet,polygons_overlap,polygon_valid
# A real cancellation counterexample discovered by the seeded reference run:
# the former server formula returned 2.015244ft² instead of about 2.52ft².
tiny=[[50.31238235823389,-93.39372167910379],[50.3123836813516,-93.39372528805664],[50.31238557741114,-93.39372757407205],[50.31238413090775,-93.39373166393945],[50.31238235823389,-93.39373066804731],[50.312380816043834,-93.39372999716021],[50.312380256295214,-93.39372757407205],[50.312380855375636,-93.39372445439975]]
rng=random.Random(10312026);max_area_error=0;max_line_error=0

def outline(lat,lon,xy):return [[lat+y/111320,lon+x/(111320*math.cos(math.radians(lat)))] for x,y in xy]
def area_ref(points):
 p=Geodesic.WGS84.Polygon()
 for lat,lon in points:p.AddPoint(lat,lon)
 return abs(p.Compute()[2])*10.76391041671
assert abs(polygon_sqft(tiny)/area_ref(tiny)-1)<.007
for offset in range(len(tiny)):
 rotated=tiny[offset:]+tiny[:offset]
 assert abs(polygon_sqft(rotated)-polygon_sqft(tiny))<.00001
 assert abs(polygon_sqft(rotated[::-1])-polygon_sqft(tiny))<.00001
for i in range(1200):
 lat=rng.uniform(25,65);lon=rng.uniform(-150,-65);size=rng.uniform(.05,80)
 xy=[(math.cos(j*math.pi/4)*size*rng.uniform(.45,1),math.sin(j*math.pi/4)*size*rng.uniform(.45,1)) for j in range(8)]
 first=Polygon(xy);assert first.is_valid and first.area>0
 dx,dy=rng.uniform(-2,2)*size,rng.uniform(-2,2)*size
 otherxy=[(x+dx,y+dy) for x,y in xy];second=Polygon(otherxy)
 a=outline(lat,lon,xy);b=outline(lat,lon,otherxy)
 assert polygon_valid(a)
 expected=first.intersection(second).area>1e-7
 assert polygons_overlap(a,b)==expected,(i,expected)
 max_area_error=max(max_area_error,abs(polygon_sqft(a)/area_ref(a)-1))
 expected_length=sum(Geodesic.WGS84.Inverse(*x,*y)['s12'] for x,y in zip(a,a[1:]))/.3048
 max_line_error=max(max_line_error,abs(line_feet(a)/expected_length-1))
assert max_area_error<.007 and max_line_error<.007,'Reference differences exceed known sphere/WGS84 model tolerance'
D=lambda n:Decimal(str(n));cent=lambda n:n.quantize(D('.01'),rounding=ROUND_HALF_UP)
def independent_price(p):
 q=p['quote'];r=p['pricing'];parts=[]
 if q['businessType']=='roofing':
  qty=sum((D(r['surface_sqft']) for r in q['manualPlanes']),D(0));parts=[cent(qty*D(r['price']))]
 else:
  qty=sum((D(a['sqft']) for a in q['commercialAreas']),D(0));parts=[cent(D(a['sqft'])*D(a['rate'])) for a in q['commercialAreas']]
  key={'pressure':'pressureLinearRate','paving':'pavingLinearRate','commercial':'commercialLinearRate'}.get(q['businessType'],'landscapingLinearRate');parts.append(cent(D(q['linearFeet'])*D(q[key])))
 sub=sum(parts);discount=cent(sub*D(r['disc'])/100) if r['mode']=='discount' else D(0)
 if r['mode']=='included':
  total=cent(sub+D(r['extraAmount']));base=cent(total/(1+(D(r['gst'])+D(r['pst']))/100));ga=cent(base*D(r['gst'])/100);pa=cent(base*D(r['pst'])/100);base=total-ga-pa
 else:
  base=cent(sub-discount+D(r['extraAmount']));ga=cent(base*D(r['gst'])/100);pa=cent(base*D(r['pst'])/100);total=base+ga+pa
 r.update({k:float(v) for k,v in dict(area=qty,subtotal=sub,discount=discount,taxBase=base,gstAmt=ga,pstAmt=pa,total=total).items()});p.update(total_area=float(qty),total_price=float(total),extra_service_amount=r['extraAmount'],extra_service_description=r['extraDescription'])
 return p
with tempfile.TemporaryDirectory() as td:
 os.environ.update(DATABASE_URL='',ESTIMATE_DB_PATH=td+'/adversarial.db',FLASK_SECRET_KEY='fictional-seeded-only')
 import app as appmod
 c=appmod.app.test_client();other=appmod.app.test_client();did='qa-fuzz-'+uuid.uuid4().hex
 con=appmod.estimate_db()
 for owner in (did,did+'-other'):
  con.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,status,created_at) VALUES(?,?,?,'unused','active','2026-10-31')",(owner,'FICTIONAL QA',owner+'@example.invalid'));con.execute('INSERT INTO account_allowances(dealer_id,complimentary) VALUES(?,1)',(owner,))
 con.commit();con.close()
 for client,owner in ((c,did),(other,did+'-other')):
  with client.session_transaction() as s:s.update(dealer_id=owner,account_type='owner',auth_version=0)
 cases=attacks=corrections=0
 for industry in ('roofing','snow','pressure','paving','landscaping','commercial'):
  for case in range(12):
   lat=rng.uniform(27,61);lon=rng.uniform(-125,-70);w=rng.uniform(2,45);h=rng.uniform(3,60)
   xy=[(0,0),(w,0),(w,h*.4),(w*.45,h*.4),(w*.45,h),(0,h)]
   a=outline(lat,lon,xy);b=outline(lat,lon,[(x+w*3,y+h*2) for x,y in xy]);line=outline(lat,lon,[(w*6,0),(w*6,h),(w*7,h)])
   q=dict(businessType=industry,measurementMode='area',commercialAreas=[dict(points=pts,sqft=round(polygon_sqft(pts)),rate=rate) for pts,rate in ((a,rng.choice([.005,.015,.1,1.2345])),(b,rng.choice([.005,.015,.1,1.2345])))],linearPoints=line,linearFeet=line_feet(line))
   for key in ('landscapingLinearRate','pressureLinearRate','pavingLinearRate','commercialLinearRate'):q[key]=rng.choice([0,.005,.25,2.5])
   if industry=='roofing':
    planes=[]
    for pts in (a,b):
     pitch=rng.choice([0,4,5,8,12]);deg=math.degrees(math.atan(pitch/12))
     planes.append(dict(points=pts,pitch_degrees=deg,surface_sqft=polygon_sqft(pts)*math.sqrt(1+(pitch/12)**2),pitch_confirmed=True,manual_roof_qa=True))
    q=dict(businessType=industry,measurementMode='auto',measureSource='manual',manualRoofWorkflow=True,roofScopeConfirmed=True,manualPlanes=planes,structures=[])
   p=independent_price(dict(address='FICTIONAL QA '+industry+' '+str(case),customer_name='Fictional QA customer',quote=q,pricing=dict(mode=rng.choice(['regular','discount','included']),price=rng.choice([.1,.955,2.01]),gst=rng.choice([0,5,7.25,13]),pst=rng.choice([0,6]),disc=rng.choice([0,7.25,50,100]),extraAmount=rng.choice([0,17.29,100.01]),extraDescription='Fictional service',estimatePeriod=rng.choice(['one_time','visit','month','season','year']) if industry in ('snow','landscaping','commercial') else 'one_time')))
   r=c.post('/api/estimates',json=p,headers={'Idempotency-Key':uuid.uuid4().hex});assert r.status_code==200,(industry,case,r.json);cases+=1
   eid=r.json['id'];before=c.get('/api/estimates/'+eid).json
   assert before['payload']['quote']==q and before['total_price']==p['total_price']
   assert other.get('/api/estimates/'+eid).status_code==404
   mutations=[lambda b:b['pricing'].update(total=b['pricing']['total']+.01),lambda b:b.update(total_area=b['total_area']+2)]
   if industry=='roofing':
    def duplicate(b):b['quote']['manualPlanes'].append(copy.deepcopy(b['quote']['manualPlanes'][0]));b['quote']['manualRoofWorkflow']=False;[x.pop('manual_roof_qa',None) for x in b['quote']['manualPlanes']];independent_price(b)
    mutations.append(duplicate)
   else:
    mutations.extend([lambda b:b['quote'].update(linearFeet=0),lambda b:b['quote']['commercialAreas'].append(copy.deepcopy(b['quote']['commercialAreas'][0]))])
   for change in mutations:
    bad=copy.deepcopy(p);change(bad);assert c.post('/api/estimates',json=bad).status_code==400,(industry,case)
    assert c.get('/api/estimates/'+eid).json==before;attacks+=1
   if industry!='roofing':
    changed=copy.deepcopy(p);pts=outline(lat,lon,[(x-w*4,y) for x,y in xy]);changed['quote']['commercialAreas'][0]['points']=pts;changed['quote']['commercialAreas'][0]['sqft']=round(polygon_sqft(pts));independent_price(changed)
    rr=c.post('/api/estimates',json=changed,headers={'If-Match':r.json['version'],'Idempotency-Key':uuid.uuid4().hex});assert rr.status_code==200,rr.json
    stored=c.get('/api/estimates/'+eid).json;assert stored['payload']['quote']['commercialAreas'][1]==q['commercialAreas'][1] and stored['payload']['quote']['linearPoints']==line
    assert c.post('/api/estimates',json=p,headers={'If-Match':r.json['version']}).status_code==409
    assert c.get('/api/estimates/'+eid).json==stored;corrections+=1
 print(json.dumps(dict(result='PASS',seed=10312026,independent_geometry_pairs=1200,max_wgs84_area_difference=max_area_error,max_wgs84_distance_difference=max_line_error,model_tolerance_not_survey_certification=True,real_api_valid_cases=cases,adversarial_mutations_rejected=attacks,selected_area_revision_cases=corrections,all_six_industries=True)))
