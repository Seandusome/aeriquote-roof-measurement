"""Disposable-only purchase UI fixture; no public server or real accounts."""
import os,sys,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
tmp=tempfile.TemporaryDirectory();os.environ['DATABASE_URL']='';os.environ['ESTIMATE_DB_PATH']=tmp.name+'/purchase.db';os.environ['FLASK_SECRET_KEY']='fictional-purchase-qa-only';os.environ['AERIQUOTE_QA_PURCHASES']='1';os.environ['AERIQUOTE_QA_TOPUP_TAX_POLICY']=json.dumps({'version':'fictional-qa-v1','rates_bps':{'US':0,'CA:SK':1100}})
os.environ.pop('RENDER_SERVICE_ID',None);os.environ.pop('RENDER_EXTERNAL_HOSTNAME',None)
import app as a,account_credits as c,extra_allowance_ledger as l,payment_free_orders as p

def seed():
 db=a.estimate_db()
 for did,country,region in [('purchase-ca','CA','SK'),('purchase-us','US','TX')]:
  db.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,state,status,created_at,plan_code,lookup_limit,estimate_limit) VALUES(?,?,?,?,?,'active','2026-01-01','basic',25,25)",(did,'FICTIONAL PURCHASE QA',did+'@example.invalid',a.password_hash('fictional-qa-password'),region))
  db.execute('INSERT INTO dealer_profiles(dealer_id,profile_json,updated_at) VALUES(?,?,?)',(did,json.dumps({'country':country,'province':region,'company':'FICTIONAL QA'}),'2026-11-04'))
 db.execute("INSERT INTO dealer_employees(id,dealer_id,employee_name,email,password_hash,status,created_at) VALUES('purchase-employee','purchase-ca','FICTIONAL EMPLOYEE','purchase-employee@example.invalid',?,'active','2026-01-01')",(a.password_hash('fictional-qa-password'),));db.commit();db.close()
 for did in ['purchase-ca','purchase-us']:
  db=a.estimate_db();c.lock_account(db,did);l.grant_administrative(db,did,3,'fixture-grant');p.set_subscription(db,did,'active');db.commit();db.close()
seed()
a.is_recovery_test_service=lambda:False;a.is_head_office=lambda:False
# A forgotten provider call must fail, never reach imagery/payment services.
a.req_json=lambda *args,**kwargs:(_ for _ in ()).throw(AssertionError('External service disabled in disposable purchase QA'))
a.req_bytes=a.req_json;a.urllib.request.urlopen=a.req_json
if __name__=='__main__':a.app.run(host='127.0.0.1',port=8766,threaded=True,use_reloader=False)
