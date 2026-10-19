"""Named test-service bypass must not weaken production or complimentary quotas."""
import os,sys,sqlite3,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory() as tmp:
 os.environ['DATABASE_URL']='';os.environ['ESTIMATE_DB_PATH']=str(Path(tmp)/'allowance.db')
 import app as a
 con=a.estimate_db()
 con.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,status,lookup_limit,created_at) VALUES('dealer','QA TEST Allowance','qa-allowance@example.invalid','unused','active',3,'2026-10-19')")
 con.execute("INSERT INTO dealer_usage(dealer_id,property_lookups) VALUES('dealer',3)")
 con.commit();con.close()
 # Run production policy against an isolated real SQLite database, never live DB.
 def db():
  raw=sqlite3.connect(a.ESTIMATE_DB);raw.row_factory=sqlite3.Row
  return a.DBCompat(raw,False)
 a.estimate_db=db;a.DATABASE_URL='postgresql://qa-policy-only'
 for env,allowed in [({},False),({'RENDER_SERVICE_ID':'srv-db5a2g5ckfvc739fui70'},True),
                     ({'RENDER_EXTERNAL_HOSTNAME':'aeriquote-commercial-test.onrender.com'},True),
                     ({'RENDER_EXTERNAL_HOSTNAME':'aeriquote-roof-measurement.onrender.com'},False)]:
  with patch.dict(os.environ,env,clear=True),a.app.test_request_context('/'):
   a.session.update(dealer_id='dealer',account_type='owner')
   result=a.consume_property_lookup('dealer')
   assert result[0]==allowed,(env,result)
 con=db()
 assert con.execute("SELECT property_lookups FROM dealer_usage WHERE dealer_id='dealer'").fetchone()['property_lookups']==3
 con.execute("INSERT INTO account_allowances(dealer_id,complimentary) VALUES('dealer',1)")
 from account_credits import month_key
 con.execute("INSERT INTO account_month_usage(dealer_id,period,lookups) VALUES('dealer',?,200)",(month_key(),))
 con.commit();con.close()
 with patch.dict(os.environ,{'RENDER_SERVICE_ID':'srv-db5a2g5ckfvc739fui70'},clear=True),a.app.test_request_context('/'):
  a.session.update(dealer_id='dealer',account_type='owner')
  assert not a.consume_property_lookup('dealer')[0],'Complimentary quotas remain enforced on recovery service'
 print('PASS: real quota logic keeps named recovery bypass, production exhausted trial rejection, unchanged usage and complimentary cap')
