"""Explicit units, mismatch guards and Street View fallback, without external requests."""
import os,sys,tempfile
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit,parse_qs
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from property_address import unit_address,building_address
assert unit_address('115-2301 Ave C North, Saskatoon, SK, Canada','SK')==('2301 Ave C North #115, Saskatoon, SK, Canada','2301')
assert unit_address('Unit 115 2301 Ave C North, Saskatoon, SK','SK')[1]=='2301'
assert unit_address('2301 100 Ave NW, Edmonton, AB','AB')[0]=='2301 100 Ave NW, Edmonton, AB'
assert unit_address('123-125 Main St, Boston, MA','MA')[0]=='123-125 Main St, Boston, MA'
assert building_address('2301 Ave C North #115, Saskatoon, SK')=='2301 Ave C North, Saskatoon, SK'
assert building_address('115-2301 Ave C North, Saskatoon, SK')=='2301 Ave C North, Saskatoon, SK'
with tempfile.TemporaryDirectory() as tmp:
 os.environ['DATABASE_URL']='';os.environ['ESTIMATE_DB_PATH']=str(Path(tmp)/'addresses.db')
 import app as a
 a.GOOGLE_MAPS_API_KEY='test-only'
 con=a.estimate_db();con.execute('INSERT INTO dealers(id,dealer_name,email,password_hash,state,status,created_at) VALUES(?,?,?,?,?,?,?)',('owner','QA','qa@example.invalid','unused','SK','active','2026-10-18'));con.commit();con.close()
 client=a.app.test_client()
 with client.session_transaction() as s:s['dealer_id']='owner';s['auth_version']=0
 parts=[{'types':['street_number'],'long_name':'2301'},{'types':['route'],'long_name':'Ave C North'},{'types':['locality'],'long_name':'Saskatoon'},{'types':['administrative_area_level_1'],'short_name':'SK'}]
 calls=[]
 def geocode(url):
  calls.append(parse_qs(urlsplit(url).query));return 200,{'status':'OK','results':[{'formatted_address':'2301 Ave C North #115, Saskatoon, SK','address_components':parts,'geometry':{'location':{'lat':52,'lng':-106}}}]}
 with patch.object(a,'req_json',geocode):
  result=client.post('/address-preview',json={'key':'test-only','address':'115-2301 Ave C North, Saskatoon, SK','expected_city':'Saskatoon','expected_province':'SK','expected_street_number':'115'})
  assert result.status_code==200,result.get_json()
  assert calls[-1]['address']==['2301 Ave C North #115, Saskatoon, SK']
  result=client.post('/address-preview',json={'key':'test-only','address':'115 2301 Ave C North, Saskatoon, SK','expected_city':'Saskatoon','expected_province':'SK','expected_street_number':'115'})
  assert result.status_code==409,'An unconfirmed ambiguous civic number must not bypass the scope guard'
  result=client.post('/address-preview',json={'key':'test-only','address':'999 Ave C North, Saskatoon, SK','expected_city':'Saskatoon','expected_province':'SK','expected_street_number':'999'})
  assert result.status_code==409
 calls=[]
 def metadata(url):
  q=parse_qs(urlsplit(url).query);calls.append(q)
  return (200,{'status':'ZERO_RESULTS'}) if len(calls)==1 else (200,{'status':'OK','pano_id':'qa-pano','date':'2015-07','location':{'lat':52,'lng':-106}})
 with patch.object(a,'req_json',metadata):
  url,date=a.street_view_info('test-only','2301 Ave C North #115, Saskatoon, SK',52,-106,52,-106)
  assert calls[0]['location']==['2301 Ave C North, Saskatoon, SK']
  assert calls[1]['location']==['52,-106'] and date=='2015-07'
  assert parse_qs(urlsplit(url).query)['pano']==['qa-pano']
 calls=[]
 def denied(url):calls.append(url);return 200,{'status':'REQUEST_DENIED'}
 with patch.object(a,'req_json',denied):
  assert a.street_view_info('test-only','Address',52,-106,52,-106)==(None,None)
  assert len(calls)==1,'Never retry an authentication/API denial as a location fallback'
print('PASS: Canadian explicit unit formats preserve civic number, numbered streets unchanged, wrong/ambiguous addresses blocked, Street View uses base building then verified coordinates only on ZERO_RESULTS')
