"""Owned frozen quote -> imagery token, without property lookup or measurement usage."""
import os,sys,tempfile,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory() as tmp:
 os.environ['DATABASE_URL']='';os.environ['ESTIMATE_DB_PATH']=str(Path(tmp)/'edit.db')
 import app as a
 a.GOOGLE_MAPS_API_KEY='test-key'
 con=a.estimate_db()
 for did in ('owner','other'):con.execute('INSERT INTO dealers(id,dealer_name,email,password_hash,state,status,created_at) VALUES(?,?,?,?,?,?,?)',(did,did,did+'@example.invalid','unused','SK','active','2026-10-18'))
 con.commit();con.close()
 client=a.app.test_client()
 with client.session_transaction() as s:s['dealer_id']='owner';s['auth_version']=0
 p={'customer_name':'QA only','address':'2301 Ave C North #115, Saskatoon, SK, Canada','job_status':'Booked','scheduled_date':'2026-10-25','amount_paid':25,'total_area':100,'total_price':11.1,'quote':{'commercialAreas':[{'sqft':100,'rate':.1,'points':[[52,-106],[52,-105.999],[52.001,-106]]}],'linearPoints':[[52,-106],[52.002,-105.998]]}}
 from measurement_integrity import polygon_sqft,line_feet
 p['quote']['commercialAreas'][0]['sqft']=round(polygon_sqft(p['quote']['commercialAreas'][0]['points']))
 p['total_area']=p['quote']['commercialAreas'][0]['sqft']
 p['quote']['linearFeet']=line_feet(p['quote']['linearPoints'])
 from qa_estimate_fixture import price_fixture
 price_fixture(p)
 eid=client.post('/api/estimates',json=p).get_json()['id']
 before=client.get('/api/estimates/'+eid).get_json()['payload']
 # No Google request is permitted for restoring a saved job's coordinates.
 with patch.object(a,'req_json',side_effect=AssertionError('No lookup')),patch.object(a,'req_bytes',side_effect=AssertionError('No lookup')):
  r=client.post('/api/estimates/'+eid+'/editing-session',json={'version_index':-1})
 assert r.status_code==200,r.data
 d=r.get_json();assert d['bounds']==[[52.0,-106.0],[52.002,-105.998]] and len(d['token'])==32
 assert 'test-key' not in r.get_data(as_text=True)
 assert d['job_details']['job_status']=='Booked' and d['job_details']['amount_paid']==25
 assert client.get('/api/estimates/'+eid).get_json()['payload']==before
 a.SESSIONS.clear();assert client.get('/fallback-meta/'+d['token']).status_code==200
 other=a.app.test_client()
 with other.session_transaction() as s:s['dealer_id']='other';s['auth_version']=0
 assert other.post('/api/estimates/'+eid+'/editing-session',json={}).status_code==404
 assert other.get('/fallback-meta/'+d['token']).status_code==404
 assert a.app.test_client().post('/api/estimates/'+eid+'/editing-session',json={}).status_code==401
 assert client.post('/api/estimates/'+eid+'/editing-session',json={'version_index':99}).status_code==400
 p['quote']['commercialAreas'][0]['rate']=.2;price_fixture(p);client.post('/api/estimates',json=p)
 assert client.post('/api/estimates/'+eid+'/editing-session',json={'version_index':0}).status_code==200
 con=a.estimate_db();assert con.execute('SELECT COUNT(*) AS n FROM dealer_usage').fetchone()['n']==0;con.close()
print('PASS: saved editing preserves payload/revisions, recovers owned imagery token, rejects other owners/versions, and consumes no property lookup')
