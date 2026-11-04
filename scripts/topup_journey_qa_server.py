"""Full journey fixture: real paid caps and receipt logic, temporary loopback DB only."""
import purchase_screen_qa_server as fixture
import json
from pathlib import Path
from flask import request,session,abort
from account_credits import consume,lock_account,paid_usage

a=fixture.a;c=fixture.c;l=fixture.l;p=fixture.p
assert not a.DATABASE_URL and Path(a.ESTIMATE_DB).is_relative_to(Path(fixture.tmp.name))
a.GOOGLE_MAPS_API_KEY='qa-placeholder'
db=a.estimate_db()
for did in ('purchase-ca','purchase-us'):
 profile=dict(name='FICTIONAL QA',company='FICTIONAL TOPUP COMPANY',email=did+'@example.invalid',country='CA' if did=='purchase-ca' else 'US',province='SK' if did=='purchase-ca' else 'TX',businessType='landscaping',price=.1,gst=5,pst=6,pricingMode='regular')
 db.execute('UPDATE dealer_profiles SET profile_json=? WHERE dealer_id=?',(json.dumps(profile),did))
db.commit();db.close()

def identity(owner=False):
 assert request.host.split(':')[0]=='127.0.0.1' and not a.DATABASE_URL and Path(a.ESTIMATE_DB).is_relative_to(Path(fixture.tmp.name))
 if owner and a.is_employee():abort(403)
 return session['dealer_id']

@a.app.get('/__qa_topup/state')
def state():
 did=identity();db=a.estimate_db()
 try:
  return a.jsonify(business=did,employee=a.is_employee(),ledger=l.reconciliation(db,did),paid=paid_usage(db,did),counts={t:db.execute('SELECT COUNT(*) AS n FROM '+t+' WHERE dealer_id=?',(did,)).fetchone()['n'] for t in ('estimates','estimate_revisions','topup_order_terms','topup_fulfillments')},purchased_debits=[dict(r) for r in db.execute("SELECT m.channel,m.delta,m.operation_ref FROM extra_movements m JOIN extra_source_lots lot USING(dealer_id,lot_id) WHERE m.dealer_id=? AND lot.origin='purchased' AND m.delta<0 ORDER BY m.channel,m.operation_ref",(did,)).fetchall()])
 finally:db.close()

@a.app.post('/__qa_topup/exhaust')
def exhaust():
 did=identity(True);db=a.estimate_db()
 try:
  lock_account(db,did)
  assert db.execute('SELECT plan_code FROM dealers WHERE id=?',(did,)).fetchone()['plan_code']=='basic'
  assert not db.execute('SELECT order_id FROM topup_order_terms WHERE dealer_id=?',(did,)).fetchone()
  assert l.reconciliation(db,did)['bank']=={'lookups':3,'estimates':3}
  for kind in ('lookups','estimates'):
   for n in range(28):assert consume(db,did,kind,0,25,operation_id='exhaust-'+kind+'-'+str(n))[0]
  assert l.reconciliation(db,did)['bank']=={'lookups':0,'estimates':0}
  db.commit();return a.jsonify(ok=True)
 finally:db.close()

@a.app.post('/__qa_topup/subscription')
def subscription():
 did=identity(True);db=a.estimate_db()
 try:lock_account(db,did);p.set_subscription(db,did,request.json['status']);db.commit();return a.jsonify(ok=True)
 finally:db.close()

def provider(data):
 if 'FAIL' in data.get('address',''):return a.jsonify(error='FICTIONAL imagery unavailable. Retry loading the property.'),503
 token=a.create_session('FICTIONAL-NO-PROVIDER',52,-106,mode='manual_static',formatted_address='1 Fictional QA Street, Saskatoon, SK, Canada')
 return a.jsonify(token=token,fallback=True,center={'latitude':52,'longitude':-106},formatted_address='1 Fictional QA Street, Saskatoon, SK, Canada',parts={})
a.perform_property_lookup=provider
if __name__=='__main__':a.app.run(host='127.0.0.1',port=8765,threaded=True,use_reloader=False)
