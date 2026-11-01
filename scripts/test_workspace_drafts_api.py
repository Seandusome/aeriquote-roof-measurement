"""Disposable SQLite integration; forbids external providers and customer access."""
import os,sys,tempfile,json,time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory() as tmp:
 from urllib.parse import urlsplit
 url=os.environ.get('QA_POSTGRES_URL','') if '--postgres' in sys.argv else ''
 if '--postgres' in sys.argv:
  parts=urlsplit(url);assert parts.hostname in ('127.0.0.1','localhost') and parts.path=='/aeriquote_qa','Disposable local QA PostgreSQL only'
 os.environ['DATABASE_URL']=url;os.environ['ESTIMATE_DB_PATH']=str(Path(tmp)/'drafts.db')
 import app as a
 a.GOOGLE_MAPS_API_KEY='fictional-provider-key'
 c=a.estimate_db()
 for did in ('draft-owner','draft-other'):
  c.execute('INSERT INTO dealers(id,dealer_name,email,password_hash,status,created_at) VALUES(?,?,?,?,?,?)',(did,did,did+'@example.invalid','unused','active','2026-11-01'))
 for eid in ('draft-one','draft-two'):
  c.execute('INSERT INTO dealer_employees(id,dealer_id,employee_name,email,password_hash,status,created_at) VALUES(?,?,?,?,?,?,?)',(eid,'draft-owner',eid,eid+'@example.invalid','unused','active','2026-11-01'))
 from account_credits import month_key
 c.execute('INSERT INTO account_allowances(dealer_id,complimentary) VALUES(?,1)',('draft-owner',))
 c.execute('INSERT INTO account_month_usage(dealer_id,period,lookups,estimates) VALUES(?,?,199,199)',('draft-owner',month_key()))
 c.commit();c.close()
 def client(dealer='draft-owner',employee=None):
  browser=a.app.test_client()
  with browser.session_transaction() as s:
   s['dealer_id']=dealer;s['auth_version']=0
   if employee:s['account_type']='employee';s['employee_id']=employee
  return browser
 owner=client();h={'X-AeriQuote-Account':'draft-owner','X-AeriQuote-Principal':'owner:draft-owner'}
 tab='fictional-qa-tab-0001'
 with a.app.test_request_context('/'):
  a.session['dealer_id']='draft-owner'
  token=a.create_session('fictional-provider-key',52,-106,formatted_address='1 Fictional QA Street')
 w={'schema':1,'sessionToken':token,'values':{'customerName':'FICTIONAL ONLY'},'quote':{'areaPoints':[[52,-106],[52,-105.999],[52.001,-106]]},'pending':{'id':'qa-operation-0001'}}
 assert owner.put('/api/workspace-drafts/'+tab,headers=h,json={'version':0,'workspace':w}).status_code==200
 assert owner.get('/api/workspace-drafts',headers=h).get_json()['drafts'][0]['draft_id']==tab
 assert owner.get('/api/workspace-drafts/'+tab,headers=h).get_json()['workspace']==w
 for browser,principal,business in [(client('draft-other'),'owner:draft-other','draft-other'),(client(employee='draft-one'),'employee:draft-one','draft-owner'),(client(employee='draft-two'),'employee:draft-two','draft-owner')]:
  hh={'X-AeriQuote-Account':business,'X-AeriQuote-Principal':principal}
  assert browser.get('/api/workspace-drafts',headers=hh).get_json()['drafts']==[]
  assert browser.get('/api/workspace-drafts/'+tab,headers=hh).status_code==404
 assert client(employee='draft-one').put('/api/workspace-drafts/'+tab,headers=h,json={'version':1,'workspace':w}).status_code==409
 assert owner.put('/api/workspace-drafts/'+tab,headers={**h,'Origin':'https://foreign.invalid'},json={'version':1,'workspace':w}).status_code==403
 assert a.app.test_client().get('/api/workspace-drafts',headers=h).status_code==401
 # Expired property session is rehydrated only from acknowledged owned metadata.
 a.SESSIONS.clear()
 c=a.estimate_db();c.execute('DELETE FROM property_sessions WHERE dealer_id=?',('draft-owner',));c.commit();c.close()
 with patch.object(a,'req_json',side_effect=AssertionError('No provider lookup')),patch.object(a,'req_bytes',side_effect=AssertionError('No provider lookup')):
  imagery=owner.post('/api/workspace-drafts/'+tab+'/imagery-session',headers=h,json={})
 assert imagery.status_code==200,imagery.data
 assert 'fictional-provider-key' not in imagery.get_data(as_text=True)
 c=a.estimate_db()
 for table in ('estimates','estimate_revisions','estimate_save_receipts','dealer_usage'):
  assert c.execute('SELECT COUNT(*) AS n FROM '+table+' WHERE dealer_id=?',('draft-owner',)).fetchone()['n']==0,table
 assert c.execute('SELECT estimates,lookups FROM account_month_usage WHERE dealer_id=? AND period=?',('draft-owner',month_key())).fetchone()['estimates']==199
 c.close()
 # Different failure case: Restore reads v1, original tab acknowledges v2,
 # then Restore's source cleanup arrives late. v2 must remain recoverable.
 race='fictional-race-source-0001';fork='fictional-race-copy-00001'
 assert owner.put('/api/workspace-drafts/'+race,headers=h,json={'version':0,'workspace':w}).status_code==200
 observed=owner.get('/api/workspace-drafts/'+race,headers=h).get_json()
 newer={**w,'values':{'customerName':'NEWER ACKNOWLEDGED ORIGINAL TAB'}}
 assert owner.put('/api/workspace-drafts/'+race,headers=h,json={'version':1,'workspace':newer}).status_code==200
 assert owner.put('/api/workspace-drafts/'+fork,headers=h,json={'version':0,'workspace':observed['workspace']}).status_code==200
 cleanup=owner.delete('/api/workspace-drafts/'+race,headers=h,json={'version':observed['version']})
 assert cleanup.status_code==200 and cleanup.get_json()['deleted'] is False,'Late Restore cleanup must not erase newer acknowledged work'
 assert owner.get('/api/workspace-drafts/'+race,headers=h).get_json()['workspace']==newer
 assert owner.get('/api/workspace-drafts/'+fork,headers=h).get_json()['workspace']==w
 assert owner.delete('/api/workspace-drafts/'+race,headers=h,json={'version':2}).get_json()['deleted'] is True
 assert owner.delete('/api/workspace-drafts/'+fork,headers=h).get_json()['deleted'] is True
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
 state=owner.post('/api/workspace-drafts/'+tab+'/save-status',headers=h,json={'operation_id':'qa-operation-0001'}).get_json();assert state['saved'] and state['result']==r.get_json()
 assert owner.post('/api/workspace-drafts/'+tab+'/save-status',headers=h,json={'operation_id':'wrong-operation'}).get_json()['saved'] is False
 assert owner.delete('/api/workspace-drafts/'+tab,headers=h,json={'version':1}).get_json()['deleted'] is False
 assert owner.post('/api/workspace-drafts/'+tab+'/save-status',headers=h,json={'operation_id':'qa-operation-0001'}).get_json()['saved'] is True,'Late Restore cleanup must retain lost-response receipt confirmation'
 assert owner.post('/api/estimates',headers=sh,json=p).get_json()==r.get_json()
 assert owner.put('/api/workspace-drafts/'+tab,headers=h,json={'version':1,'workspace':w}).status_code==409
 c=a.estimate_db();row=c.execute('SELECT payload,property_metadata FROM workspace_drafts WHERE dealer_id=?',('draft-owner',)).fetchone();assert row['payload'] is None and row['property_metadata'] is None
 assert c.execute('SELECT COUNT(*) AS n FROM estimates WHERE dealer_id=?',('draft-owner',)).fetchone()['n']==1
 assert c.execute('SELECT COUNT(*) AS n FROM estimate_revisions WHERE dealer_id=?',('draft-owner',)).fetchone()['n']==0
 assert c.execute('SELECT COUNT(*) AS n FROM estimate_save_receipts WHERE dealer_id=?',('draft-owner',)).fetchone()['n']==1
 usage=c.execute('SELECT estimates,lookups FROM account_month_usage WHERE dealer_id=? AND period=?',('draft-owner',month_key())).fetchone();assert usage['estimates']==200 and usage['lookups']==199
 c.close()
print('PASS API: owner/business/employee isolation, foreign-origin rejection, expired imagery without lookup/charge, side-effect-free restore, atomic save deletion, replay exactly once, late autosave rejection')
