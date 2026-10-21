"""Independent server rejection of incomplete automatic results, even with browser flags cleared."""
import os,sys,tempfile,copy,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from qa_estimate_fixture import price_fixture,automatic_roof
points=[[52,-106],[52,-105.9999],[52.0001,-105.9999],[52.0001,-106]]
with tempfile.TemporaryDirectory() as tmp:
 os.environ['DATABASE_URL']='';os.environ['ESTIMATE_DB_PATH']=str(Path(tmp)/'roof.db')
 import app as a
 con=a.estimate_db();con.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,state,status,created_at) VALUES('qa','QA ROOF','qa-roof@example.invalid','unused','SK','active','2026-10-21')");con.commit();con.close()
 c=a.app.test_client()
 with c.session_transaction() as session:session.update(dealer_id='qa',account_type='owner',auth_version=0)
 q={'businessType':'roofing','measurementMode':'auto','measureSource':'google','structures':[automatic_roof(points,30,'main'),automatic_roof([[lat+.001,lon] for lat,lon in points],22.62,'garage')],'manualPlanes':[],'commercialAreas':[],'areaSqFt':0,'linearFeet':0}
 p=price_fixture({'address':'QA MULTI ROOF DO NOT SEND','quote':q,'pricing':{'price':.95,'mode':'discount','gst':5,'pst':6,'disc':10}})
 r=c.post('/api/estimates',json=p);assert r.status_code==200,r.get_json();eid=r.get_json()['id'];before=c.get('/api/estimates/'+eid).get_json()
 attacks=[lambda q:q['structures'][0].pop('outline'),lambda q:q['structures'][1].update(roof_coverage_ratio=.8),lambda q:q['structures'][1].update(building_ground_sqft=q['structures'][1]['roof_ground_sqft']*2),lambda q:q['structures'][1].update(roof_ground_sqft=q['structures'][1]['roof_ground_sqft']*3),lambda q:q['structures'][1].update(segments=[]),lambda q:q['structures'][1]['segments'][0].update(pitch_degrees=79),lambda q:q['structures'][1]['segments'][0].update(area_sqft=1),lambda q:q['structures'][1].update(building_id='main'),lambda q:q['structures'][1].update(total_roof_sqft=1)]
 for mutate in attacks:
  bad=copy.deepcopy(p);mutate(bad['quote']);price_fixture(bad)
  # No needs_remeasure or automatic_review_warning flag is supplied.
  response=c.post('/api/estimates',json=bad);assert response.status_code==400,response.get_json()
 assert c.get('/api/estimates/'+eid).get_json()==before
 # A legitimate manual replacement with confirmed pitch remains saveable.
 corrected=copy.deepcopy(p);roof=corrected['quote']['structures'][1];roof.update(manually_measured=True,pitch_confirmed=True);price_fixture(corrected)
 assert c.post('/api/estimates',json=corrected).status_code==200
print('PASS: multiple buildings/main+garage, missing outlines/sections, partial coverage, manipulated pitch, duplicate building and underreported area; flags cleared cannot bypass server; manual replacement retained')
