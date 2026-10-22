"""Disposable DB only: paid monthly rollover, limits, preservation, concurrency and isolation."""
import os,sys,tempfile
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory() as tmp:
 url=os.environ.get('QA_POSTGRES_URL','') if '--postgres' in sys.argv else ''
 if '--postgres' in sys.argv:
  parts=urlsplit(url);assert parts.hostname in ('localhost','127.0.0.1') and parts.path=='/aeriquote_qa'
 os.environ['DATABASE_URL']=url;os.environ['ESTIMATE_DB_PATH']=tmp+'/qa.db'
 import app as a
 from account_credits import subscription_period,consume,lock_account,paid_usage
 from unittest.mock import patch
 utc=timezone.utc;at=lambda text:datetime.fromisoformat(text).replace(tzinfo=utc)
 assert subscription_period('2024-01-31T12:30:00Z',at('2024-02-29T12:29:59'))[0].startswith('2024-01-31')
 assert subscription_period('2024-01-31T12:30:00Z',at('2024-02-29T12:30:00'))[0].startswith('2024-02-29')
 assert subscription_period('2024-01-31T12:30:00Z',at('2024-03-31T12:30:00'))[0].startswith('2024-03-31')
 con=a.estimate_db();con.execute("UPDATE account_billing_migration SET started_at='2026-10-22T00:00:00+00:00' WHERE id='monthly-v1'")
 for plan,limit in [('basic',25),('pro',75),('business',200)]:
  did='monthly-'+plan;con.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,status,created_at,plan_code,lookup_limit,estimate_limit) VALUES(?,?,?,'unused','active','2026-09-15T10:00:00Z',?,0,0)",(did,'QA ONLY',did+'@example.invalid',plan))
  con.execute('INSERT INTO dealer_usage(dealer_id,property_lookups) VALUES(?,?)',(did,limit))
 con.commit();con.close()
 def attempt(did,kind='lookups',when='2026-10-22T00:00:00',commit=True):
  con=a.estimate_db()
  try:
   lock_account(con,did);result=consume(con,did,kind,999,0,at(when))
   if commit:con.commit()
   return result
  finally:con.close()
 for plan,limit in [('basic',25),('pro',75),('business',200)]:
  did='monthly-'+plan
  # Denial may roll back entirely; fixed migration boundary must still renew next month.
  assert attempt(did,commit=False)==(False,limit,limit)
  assert attempt(did,when='2026-11-15T09:59:59',commit=False)[0] is False
  assert attempt(did,when='2026-11-15T10:00:00')==(True,1,limit)
  for _ in range(limit-1):assert attempt(did,when='2026-11-16T00:00:00')[0]
  assert not attempt(did,when='2026-11-16T00:00:00')[0]
  assert attempt(did,'estimates',when='2026-11-16T00:00:00')==(True,1,limit)
  con=a.estimate_db();assert con.execute('SELECT property_lookups FROM dealer_usage WHERE dealer_id=?',(did,)).fetchone()['property_lookups']==limit;con.close()
 # Concurrent final credit at new boundary: exactly one succeeds.
 for _ in range(24):assert attempt('monthly-basic',when='2026-12-16T00:00:00')[0]
 with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(lambda _:attempt('monthly-basic',when='2026-12-16T00:00:00')[0],range(8)))
 assert sum(results)==1,results
 # No reset by profile edits or client-provided billing fields; employee shares owner.
 c=a.app.test_client()
 with c.session_transaction() as s:s.update(dealer_id='monthly-basic',account_type='owner',auth_version=0)
 assert c.post('/api/account/profile',json={'billing_anchor':'2026-12-17','subscription_usage':0}).status_code==200
 assert not attempt('monthly-basic',when='2026-12-16T00:00:00')[0]
 assert a.app.test_client().post('/property/accept',json={}).status_code==401
 # Named recovery/testing service must not bypass an actual paid plan.
 import account_credits as credits
 class Frozen(datetime):
  @classmethod
  def now(cls,tz=None):return at('2026-12-16T00:00:00').astimezone(tz or utc)
 with patch.object(credits,'datetime',Frozen),patch.object(a,'is_recovery_test_service',return_value=True),a.app.test_request_context('/'):
  a.session.update(dealer_id='monthly-basic',account_type='owner',auth_version=0)
  assert not a.consume_property_lookup('monthly-basic')[0]
 # Real estimate retries by owner/employee share one paid-period deduction.
 from qa_estimate_fixture import price_fixture
 from measurement_integrity import polygon_sqft
 pts=[[52,-106],[52,-105.9999],[52.0001,-105.9999],[52.0001,-106]]
 payload={'address':'QA monthly retry DO NOT SEND','quote':{'commercialAreas':[{'points':pts,'sqft':round(polygon_sqft(pts)),'rate':1}]}}
 price_fixture(payload)
 con=a.estimate_db();con.execute("INSERT INTO dealer_employees(id,dealer_id,employee_name,email,password_hash,status,created_at) VALUES('monthly-employee','monthly-pro','QA ONLY','monthly-employee@example.invalid','unused','active','2026-10-22')");con.commit();con.close()
 def save(i):
  client=a.app.test_client()
  with client.session_transaction() as session:
   session.update(dealer_id='monthly-pro',account_type='employee' if i%2 else 'owner',auth_version=0)
   if i%2:session['employee_id']='monthly-employee'
  response=client.post('/api/estimates',json=payload,headers={'Idempotency-Key':'monthly-identical-save'})
  assert response.status_code==200,response.json
  return response.json['id']
 with patch.object(credits,'datetime',Frozen):
  with ThreadPoolExecutor(max_workers=8) as pool:ids=list(pool.map(save,range(8)))
  assert len(set(ids))==1
 con=a.estimate_db();assert paid_usage(con,'monthly-pro',now=at('2026-12-16T00:00:00'))['estimates']==1;con.close()
 # Existing complimentary rules are exercised separately by test_account_credits.py.
 print('PASS 25/75/200 exact anniversary rollover, leap/short month boundaries, preserved lifetime counters, denied-first-use rollback, separate estimates, zero-limit bypass blocked, eight concurrent final-credit requests, profile tampering and isolation')
