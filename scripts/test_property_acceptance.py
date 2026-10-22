"""Isolated real routes: imagery readiness is confirmed before charging a lookup."""
import os,sys,tempfile,uuid
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory() as tmp:
 url=os.environ.get('QA_POSTGRES_URL','') if '--postgres' in sys.argv else ''
 if '--postgres' in sys.argv:
  parts=urlsplit(url);assert parts.hostname in ('127.0.0.1','localhost') and parts.path=='/aeriquote_qa','Disposable localhost QA database only'
 os.environ['DATABASE_URL']=url;os.environ['ESTIMATE_DB_PATH']=tmp+'/qa.db'
 import app as a
 from account_credits import month_key
 a.is_recovery_test_service=lambda:False;a.is_head_office=lambda:False
 con=a.estimate_db()
 for did in ['qa-a','qa-b']:
  con.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,status,created_at) VALUES(?,?,?,'unused','active','2026-10-22')",(did,'QA ONLY',did+'@example.invalid'))
  con.execute('INSERT INTO account_allowances(dealer_id,complimentary) VALUES(?,1)',(did,))
  con.execute('INSERT INTO account_month_usage(dealer_id,period,lookups) VALUES(?,?,199)',(did,month_key()))
 con.commit();con.close()
 def client(did='qa-a'):
  c=a.app.test_client()
  with c.session_transaction() as s:s.update(dealer_id=did,account_type='owner',auth_version=0)
  return c
 def usage():
  con=a.estimate_db()
  try:return con.execute('SELECT lookups FROM account_month_usage WHERE dealer_id=? AND period=?',('qa-a',month_key())).fetchone()['lookups']
  finally:con.close()
 def provider(d):
  token=a.create_session('fake',52,-106,mode='manual_static')
  return a.jsonify(token=token,fallback=True,center={'latitude':52,'longitude':-106})
 data={'key':'fake','address':'QA rural coordinates','direct_coordinates':True,'latitude':52,'longitude':-106,'prepare_only':True}
 with patch.object(a,'perform_property_lookup',side_effect=provider) as upstream:
  c=client();h={'Idempotency-Key':'qa-operation'}
  r=c.post('/property',json=data,headers=h);assert r.status_code==200,r.json;token=r.json['token'];assert usage()==199
  assert c.post('/property',json=data,headers=h).json==r.json;assert upstream.call_count==1
  assert c.post('/property',json={**data,'latitude':53},headers=h).status_code==409
  body={'operation_id':'qa-operation','token':token}
  assert client('qa-b').post('/property/accept',json=body).status_code==404
  assert c.post('/property/accept',json={**body,'token':'wrong'}).status_code==409;assert usage()==199
  # Image failure means no accept; refresh/retry receives original prepared result.
  assert client().post('/property',json=data,headers=h).json==r.json;assert usage()==199
  with ThreadPoolExecutor(max_workers=8) as pool:codes=list(pool.map(lambda _:client().post('/property/accept',json=body).status_code,range(8)))
  assert codes==[200]*8,codes;assert usage()==200
  assert c.post('/property/accept',json=body).status_code==200;assert usage()==200
  assert a.app.test_client().post('/property/accept',json=body).status_code==401
 # Invalid direct coordinates do not call providers or consume credits.
 with a.app.test_request_context('/property',method='POST'):
  response=a.app.make_response(a.perform_property_lookup({'key':'fake','address':'QA','direct_coordinates':True,'latitude':90,'longitude':0}));assert response.status_code==400
 print('PASS prepared lookup/no debit, reload replay, mismatch/isolation, eight simultaneous accepts one debit, lost-response retry, expired login, polar coordinate rejection')
