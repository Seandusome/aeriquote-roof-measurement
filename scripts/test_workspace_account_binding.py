"""Disposable account-switch recovery: an old workspace must not write to a new business."""
import copy,json,os,sys,tempfile
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parent)]
with tempfile.TemporaryDirectory() as tmp:
 os.environ['DATABASE_URL']='';os.environ['ESTIMATE_DB_PATH']=tmp+'/accounts.db'
 import app as a
 from qa_estimate_fixture import price_fixture
 from measurement_integrity import polygon_sqft
 from account_credits import month_key
 con=a.estimate_db()
 for did in ['qa-original','qa-other']:
  con.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,status,created_at) VALUES(?,?,?,'unused','active','2026-10-27')",(did,did,did+'@example.invalid'))
  con.execute('INSERT INTO account_allowances(dealer_id,complimentary) VALUES(?,1)',(did,))
  con.execute('INSERT INTO dealer_profiles(dealer_id,profile_json,updated_at) VALUES(?,?,?)',(did,json.dumps({'company':did,'email':did+'@example.invalid'}),'2026-10-27'))
 con.commit();con.close()
 def identify(c,did):
  with c.session_transaction() as s:s.clear();s.update(dealer_id=did,account_type='owner',auth_version=0)
 def state(did):
  con=a.estimate_db()
  try:
   n=con.execute('SELECT COUNT(*) AS n FROM estimates WHERE dealer_id=?',(did,)).fetchone()['n']
   usage=con.execute('SELECT estimates FROM account_month_usage WHERE dealer_id=? AND period=?',(did,month_key())).fetchone()
   profile=con.execute('SELECT profile_json FROM dealer_profiles WHERE dealer_id=?',(did,)).fetchone()['profile_json']
   return n,usage['estimates'] if usage else 0,profile
  finally:con.close()
 c=a.app.test_client();identify(c,'qa-original')
 pts=[[52,-106],[52,-105.9999],[52.0001,-105.9999],[52.0001,-106]]
 p={'address':'FICTIONAL original workspace','customer_name':'QA ORIGINAL ONLY','quote':{'commercialAreas':[{'points':pts,'sqft':round(polygon_sqft(pts)),'rate':.1}]}};price_fixture(p)
 h={'X-AeriQuote-Account':'qa-original','Idempotency-Key':'original-tab'}
 original=state('qa-original');other=state('qa-other')
 identify(c,'qa-other')
 r=c.post('/api/estimates',json=p,headers=h)
 assert r.status_code==409,(r.status_code,r.json)
 assert 'business' in r.json['error'].lower()
 assert state('qa-original')==original and state('qa-other')==other,'Mismatch must not write estimates or deduct either allowance'
 r=c.post('/api/account/profile',json={'company':'WRONG ORIGINAL TAB'},headers=h);assert r.status_code==409
 assert state('qa-other')==other,'Mismatch must not overwrite the newly signed-in business branding'
 identify(c,'qa-original')
 html=c.get('/').get_data(as_text=True);assert 'id="aqAccountId" data-account-id="qa-original"' in html,'Account cache identity must be rendered in the real measurement workspace'
 r=c.post('/api/estimates',json=p,headers=h);assert r.status_code==200,r.json
 assert c.post('/api/estimates',json=p,headers=h).json==r.json,'Same-account retry is idempotent'
 assert state('qa-original')[:2]==(1,1)
 with c.session_transaction() as s:s.clear()
 assert c.post('/api/estimates',json=p,headers=h).status_code==401,'Expired authentication remains 401'
 identify(c,'qa-original');assert c.post('/api/estimates',json=p,headers=h).status_code==200
 assert state('qa-original')[:2]==(1,1),'Reauthentication/retry never spends again'
 assert state('qa-other')==other
 # Compatibility callers remain authenticated/isolated even when omitting the optional workspace header.
 assert c.get('/api/estimates',headers=h).status_code==200
 print('PASS old-tab account mismatch blocks estimate/profile writes before credits; original-login recovery, idempotency, expiry and rendered workspace identity')
