"""Disposable SQLite integration; forbids external providers and customer access."""
import os,sys,tempfile,json,time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory() as tmp:
 os.environ['DATABASE_URL']='';os.environ['ESTIMATE_DB_PATH']=str(Path(tmp)/'drafts.db')
 import app as a
 a.GOOGLE_MAPS_API_KEY='fictional-provider-key'
 c=a.estimate_db()
 for did in ('owner','other'):
  c.execute('INSERT INTO dealers(id,dealer_name,email,password_hash,status,created_at) VALUES(?,?,?,?,?,?)',(did,did,did+'@example.invalid','unused','active','2026-11-01'))
 for eid in ('one','two'):
  c.execute('INSERT INTO dealer_employees(id,dealer_id,employee_name,email,password_hash,status,created_at) VALUES(?,?,?,?,?,?,?)',(eid,'owner',eid,eid+'@example.invalid','unused','active','2026-11-01'))
 c.commit();c.close()
 def client(dealer='owner',employee=None):
  browser=a.app.test_client()
  with browser.session_transaction() as s:
   s['dealer_id']=dealer;s['auth_version']=0
   if employee:s['account_type']='employee';s['employee_id']=employee
  return browser
 owner=client();h={'X-AeriQuote-Account':'owner','X-AeriQuote-Principal':'owner:owner'}
 tab='fictional-qa-tab-0001'
 with a.app.test_request_context('/'):
  a.session['dealer_id']='owner'
  token=a.create_session('fictional-provider-key',52,-106,formatted_address='1 Fictional QA Street')
 w={'schema':1,'sessionToken':token,'values':{'customerName':'FICTIONAL ONLY'},'quote':{'areaPoints':[[52,-106],[52,-105.999],[52.001,-106]]},'pending':{'id':'qa-operation-0001'}}
 assert owner.put('/api/workspace-drafts/'+tab,headers=h,json={'version':0,'workspace':w}).status_code==200
 assert owner.get('/api/workspace-drafts',headers=h).get_json()['drafts'][0]['draft_id']==tab
 assert owner.get('/api/workspace-drafts/'+tab,headers=h).get_json()['workspace']==w
 for browser,principal,business in [(client('other'),'owner:other','other'),(client(employee='one'),'employee:one','owner'),(client(employee='two'),'employee:two','owner')]:
  hh={'X-AeriQuote-Account':business,'X-AeriQuote-Principal':principal}
  assert browser.get('/api/workspace-drafts',headers=hh).get_json()['drafts']==[]
  assert browser.get('/api/workspace-drafts/'+tab,headers=hh).status_code==404
 assert client(employee='one').put('/api/workspace-drafts/'+tab,headers=h,json={'version':1,'workspace':w}).status_code==409
 assert owner.put('/api/workspace-drafts/'+tab,headers={**h,'Origin':'https://foreign.invalid'},json={'version':1,'workspace':w}).status_code==403
 assert a.app.test_client().get('/api/workspace-drafts',headers=h).status_code==401
 # Expired property session is rehydrated only from acknowledged owned metadata.
 a.SESSIONS.clear()
 c=a.estimate_db();c.execute('DELETE FROM property_sessions');c.commit();c.close()
 with patch.object(a,'req_json',side_effect=AssertionError('No provider lookup')),patch.object(a,'req_bytes',side_effect=AssertionError('No provider lookup')):
  imagery=owner.post('/api/workspace-drafts/'+tab+'/imagery-session',headers=h,json={})
 assert imagery.status_code==200,imagery.data
 assert 'fictional-provider-key' not in imagery.get_data(as_text=True)
 c=a.estimate_db()
 for table in ('estimates','estimate_revisions','estimate_save_receipts','dealer_usage'):
  assert c.execute('SELECT COUNT(*) AS n FROM '+table).fetchone()['n']==0,table
 c.close()
 # Valid explicit save atomically removes the recovery payload; replay is exactly once.
 p={'address':'1 Fictional QA Street','customer_name':'FICTIONAL ONLY','quote':{'commercialAreas':[{'points':[[52,-106],[52,-105.999],[52.001,-106]],'rate':.1}]}}
 from measurement_integrity import polygon_sqft
 p['quote']['commercialAreas'][0]['sqft']=round(polygon_sqft(p['quote']['commercialAreas'][0]['points']))
 p['total_area']=p['quote']['commercialAreas'][0]['sqft']
 from qa_estimate_fixture import price_fixture
 price_fixture(p)
 sh={**h,'X-AeriQuote-Draft':tab,'Idempotency-Key':'qa-operation-0001'}
 r=owner.post('/api/estimates',headers=sh,json=p);assert r.status_code==200,r.data
 assert owner.get('/api/workspace-drafts',headers=h).get_json()['drafts']==[]
 assert owner.post('/api/estimates',headers=sh,json=p).get_json()==r.get_json()
 assert owner.put('/api/workspace-drafts/'+tab,headers=h,json={'version':1,'workspace':w}).status_code==409
 c=a.estimate_db();row=c.execute('SELECT payload,property_metadata FROM workspace_drafts').fetchone();assert row['payload'] is None and row['property_metadata'] is None
 assert c.execute('SELECT COUNT(*) AS n FROM estimates').fetchone()['n']==1
 assert c.execute('SELECT COUNT(*) AS n FROM estimate_revisions').fetchone()['n']==0
 assert c.execute('SELECT COUNT(*) AS n FROM estimate_save_receipts').fetchone()['n']==1
 c.close()
print('PASS API: owner/business/employee isolation, foreign-origin rejection, expired imagery without lookup/charge, side-effect-free restore, atomic save deletion, replay exactly once, late autosave rejection')
