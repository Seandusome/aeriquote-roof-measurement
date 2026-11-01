"""Disposable SQLite: real elapsed cookie expiry, first save, one remaining allowance."""
import json, os, sys, tempfile, time
from datetime import timedelta
from pathlib import Path
root=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(root),str(root/'scripts')]
with tempfile.TemporaryDirectory() as tmp:
 os.environ['DATABASE_URL']='';os.environ['ESTIMATE_DB_PATH']=str(Path(tmp)/'expiry.db')
 import app as a
 from account_credits import month_key
 from measurement_integrity import polygon_sqft
 from qa_estimate_fixture import price_fixture
 a.is_recovery_test_service=lambda:False
 password='SYNTHETIC_DISPOSABLE_LOGIN_ONLY'
 con=a.estimate_db()
 for did in ('expiry-original','expiry-other'):
  con.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,status,created_at) VALUES(?,?,?,?,'active','2026-10-27')",(did,'FICTIONAL QA',did+'@example.invalid',a.password_hash(password)))
  con.execute('INSERT INTO account_allowances(dealer_id,complimentary) VALUES(?,1)',(did,))
  con.execute('INSERT INTO account_month_usage(dealer_id,period,lookups,estimates) VALUES(?,?,199,199)',(did,month_key()))
 con.commit();con.close()
 def state(did):
  con=a.estimate_db()
  try:
   return tuple(con.execute(q,(did,)).fetchone()[key] for q,key in [("SELECT COUNT(*) AS n FROM estimates WHERE dealer_id=?",'n'),("SELECT COUNT(*) AS n FROM estimate_revisions WHERE dealer_id=?",'n'),("SELECT COUNT(*) AS n FROM estimate_save_receipts WHERE dealer_id=?",'n'),("SELECT estimates FROM account_month_usage WHERE dealer_id=?",'estimates')])
  finally:con.close()
 def login(did):
  c.get('/dealer-logout')
  r=c.post('/dealer-login',data={'email':did+'@example.invalid','password':password})
  assert r.status_code==302
 c=a.app.test_client()
 pts=[[52,-106],[52,-105.9999],[52.0001,-105.9999],[52.0001,-106]]
 p={'address':'FICTIONAL EXPIRY QA ONLY','customer_name':'UNSAVED CUSTOMER','customer_phone':'306-555-0148','customer_email':'fixture@example.invalid','customer_notes':'Preserve unsaved customer details','quote':{'commercialAreas':[{'points':pts,'sqft':round(polygon_sqft(pts)),'rate':.17}]}}
 price_fixture(p)
 headers={'X-AeriQuote-Account':'expiry-original','Idempotency-Key':'pending-before-first-save'}
 baseline=state('expiry-original');other=state('expiry-other');assert baseline==(0,0,0,199)
 a.app.config['PERMANENT_SESSION_LIFETIME']=timedelta(seconds=2)
 login('expiry-original')
 assert c.get('/api/account/profile').status_code==200
 time.sleep(3.1)
 assert c.post('/api/estimates',json=p,headers=headers).status_code==401
 assert state('expiry-original')==baseline
 login('expiry-original');r=c.post('/api/estimates',json=p,headers=headers)
 assert r.status_code==200,r.json
 assert state('expiry-original')==(1,0,1,200)
 assert c.post('/api/estimates',json=p,headers=headers).json==r.json
 assert state('expiry-original')==(1,0,1,200)
 stored=c.get('/api/estimates/'+r.json['id']).json['payload']
 assert all(stored[k]==p[k] for k in ('customer_name','customer_phone','customer_email','customer_notes','quote','total_price'))
 login('expiry-other')
 assert c.post('/api/estimates',json=p,headers=headers).status_code==409
 assert state('expiry-other')==other and state('expiry-original')==(1,0,1,200)
 login('expiry-original')
 assert c.post('/api/estimates',json=p,headers=headers).json==r.json
 assert state('expiry-original')==(1,0,1,200)
 print(json.dumps({'result':'PASS','before':baseline,'after':state('expiry-original'),'other_unchanged':state('expiry-other')==other,'coverage':['real password login','real elapsed max-age expiry before first save','same operation after reauthentication','one allowance deduction','repeat retry','wrong-account 409','second reauthentication retry','exact stored fictional customer/quote/total']}))
