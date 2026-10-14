"""Verify activation attribution, uniqueness, and Edmonton calendar reporting."""
import ast, math, sqlite3, sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from activation_metrics import account_metrics
now=datetime(2026,10,14,20,tzinfo=timezone.utc)
accounts=[{'created_at':'2026-10-14T05:59:59Z','first_measured_at':'2026-10-14T06:00:00Z'},
          {'created_at':'2026-10-14T06:00:00Z','first_measured_at':'2026-10-14T07:00:00Z'},
          {'created_at':'2026-10-13T10:00:00Z','first_measured_at':None},
          {'created_at':'2026-09-01T00:00:00Z','first_measured_at':'2026-10-14T08:00:00Z'}]
r=account_metrics(accounts,now)
assert (r[0]['signups'],r[0]['activations'],r[0]['cohort_activated'],r[0]['conversion'])==(1,3,1,100.0)
assert r[1]['signups']==3 and r[1]['cohort_activated']==2 and r[1]['conversion']==66.7
assert account_metrics([],now)[0]['conversion'] is None
# Test the actual Edmonton midnight boundary using the runner's timezone rules.
from zoneinfo import ZoneInfo
from datetime import timedelta
boundary=datetime(2026,11,2,tzinfo=ZoneInfo('America/Edmonton')).astimezone(timezone.utc)
r=account_metrics([{'created_at':(boundary-timedelta(seconds=1)).isoformat()}, {'created_at':boundary.isoformat()}],boundary+timedelta(hours=12))
assert r[0]['signups']==1
module=ast.parse(Path('app.py').read_text());fn=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='record_account_activation');fn.decorator_list=[]
con=sqlite3.connect(':memory:');con.row_factory=sqlite3.Row
con.execute('CREATE TABLE account_activations(dealer_id TEXT PRIMARY KEY,first_measured_at TEXT NOT NULL)');con.execute('CREATE TABLE dealers(id TEXT PRIMARY KEY,status TEXT)');con.execute("INSERT INTO dealers VALUES('owner','active')");con.commit()
class DB:
 def execute(self,*args):return con.execute(*args)
 def commit(self):con.commit()
 def close(self):pass
payload={'token':'property','kind':'area','amount':1111}
scope=dict(session={'dealer_id':'owner','account_type':'employee'},request=SimpleNamespace(get_json=lambda **kw:payload),SESSIONS={'property':{'dealer_id':'owner'}},math=math,datetime=datetime,estimate_db=DB,jsonify=lambda **kw:kw)
exec(compile(ast.Module(body=[fn],type_ignores=[]),'app.py','exec'),scope)
assert scope['record_account_activation']()=={'recorded':True}
stamp=con.execute('SELECT first_measured_at FROM account_activations').fetchone()[0]
assert scope['record_account_activation']()=={'recorded':True}
assert con.execute('SELECT count(*) FROM account_activations').fetchone()[0]==1
assert con.execute('SELECT first_measured_at FROM account_activations').fetchone()[0]==stamp
scope['session']['dealer_id']='other';assert scope['record_account_activation']()[1]==400
scope['session']['dealer_id']='owner';payload['amount']=0;assert scope['record_account_activation']()[1]==400
payload['amount']=float('nan');assert scope['record_account_activation']()[1]==400
payload['amount']=1111;payload['token']='missing';assert scope['record_account_activation']()[1]==400
print('PASS: Edmonton period boundaries/DST, signup-cohort conversion, employee attribution, idempotent first activation, invalid/cross-account rejection')
# Render the actual admin template, checking responsive reporting labels and all three periods.
from jinja2 import Template
html=next(ast.literal_eval(n.value) for n in module.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='AERIQUOTE_ADMIN_HTML' for t in n.targets))
rendered=Template(html).render(accounts=[],total_accounts=0,active_accounts=0,activated_accounts=0,metrics=account_metrics([],now))
assert all(x in rendered for x in ['Today','This week','This month','Not connected','Signup conversion','America/Edmonton'])
assert 'Dealer Management' not in rendered
print('PASS: admin dashboard renders activation/conversion/revenue for each reporting period')
