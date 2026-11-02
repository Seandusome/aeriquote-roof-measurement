"""Loopback-only fresh-user fixture: real signup and normal trial/paid policy.

SQLite is isolated. The established policy adapter prevents SQLite's local-demo
bypass without creating or accessing any external PostgreSQL connection.
"""
import sqlite3
import prelaunch_browser_server as fixture
from flask import request,session
from account_credits import paid_usage

a=fixture.a
path=a.ESTIMATE_DB

def disposable_db():
 raw=sqlite3.connect(path,timeout=30);raw.row_factory=sqlite3.Row
 return a.DBCompat(raw,False)
a.estimate_db=disposable_db
a.DATABASE_URL='postgresql://disposable-policy-only'
a.is_recovery_test_service=lambda:False

def identity():
 assert request.host.split(':')[0]=='127.0.0.1'
 assert a.DATABASE_URL=='postgresql://disposable-policy-only'
 did=session.get('dealer_id');assert did
 return did

@a.app.get('/__qa_fresh/state')
def state():
 did=identity();c=disposable_db()
 try:
  dealer=c.execute('SELECT plan_code,lookup_limit,estimate_limit FROM dealers WHERE id=?',(did,)).fetchone()
  usage=c.execute('SELECT property_lookups FROM dealer_usage WHERE dealer_id=?',(did,)).fetchone()
  counts={t:c.execute('SELECT COUNT(*) AS n FROM '+t+' WHERE dealer_id=?',(did,)).fetchone()['n'] for t in ['estimates','estimate_revisions']}
  counts['estimate_save_receipts']=c.execute("SELECT COUNT(*) AS n FROM estimate_save_receipts WHERE dealer_id=? AND operation_id NOT LIKE 'prepared:%' AND operation_id NOT LIKE 'lookup:%'",(did,)).fetchone()['n']
  return a.jsonify(plan=dict(dealer),lookups=usage['property_lookups'] if usage else 0,counts=counts,paid=paid_usage(c,did),complimentary=bool(a.credit_settings(c,did)['complimentary']))
 finally:c.close()

@a.app.post('/__qa_fresh/basic-boundary')
def basic_boundary():
 did=identity();c=disposable_db()
 try:
  c.execute("UPDATE dealers SET plan_code='basic',lookup_limit=25,estimate_limit=25 WHERE id=?",(did,))
  c.execute('INSERT INTO dealer_usage(dealer_id,property_lookups) VALUES(?,24) ON CONFLICT(dealer_id) DO UPDATE SET property_lookups=24',(did,));c.commit()
  return a.jsonify(ok=True)
 finally:c.close()

if __name__=='__main__':a.app.run(host='127.0.0.1',port=8765,threaded=True,use_reloader=False)
