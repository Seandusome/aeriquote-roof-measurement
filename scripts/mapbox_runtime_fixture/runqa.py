import app as m
from flask import jsonify
from datetime import datetime
for key in ('before','desktop','phone'):
 c=m.estimate_db()
 c.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,state,status,lookup_limit,estimate_limit,created_at,plan_code,industry) VALUES(?,?,?,?,?,'active',?,?,?,?,?)",(key,'Fictional QA Roofing',key+'@example.invalid',m.password_hash(__import__('os').environ['AQ_FIXTURE_PASSWORD']),'SK',25,25,datetime.now().isoformat(),'basic','roofing'))
 c.commit();c.close()
@m.app.get('/qa-state')
def state():
 c=m.estimate_db();id=m.session.get('dealer_id')
 try:
  tables={}
  for table in ('estimates','estimate_revisions','dealer_usage','account_subscription_usage','account_month_usage','account_allowances','workspace_drafts'):
   try:tables[table]=[dict(r) for r in c.execute('SELECT * FROM '+table+' WHERE dealer_id=?',(id,)).fetchall()]
   except Exception:pass
  tables['schema']=[r['name'] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
  return jsonify(tables)
 finally:c.close()
m.app.run(port=8880)
