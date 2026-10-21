"""Exercise actual account routes against an isolated SQLite database."""
import ast, sqlite3, json, sys
from pathlib import Path
from types import SimpleNamespace
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from account_credits import lock_account
source=(root/'app.py').read_text()
tree=ast.parse(source)
con=sqlite3.connect(':memory:');con.row_factory=sqlite3.Row
con.executescript('''CREATE TABLE dealers(id TEXT,status TEXT,estimate_limit INTEGER);
CREATE TABLE dealer_employees(id TEXT,dealer_id TEXT,status TEXT);
CREATE TABLE estimates(id TEXT,dealer_id TEXT,created_at TEXT,customer_name TEXT,customer_phone TEXT,customer_email TEXT,address TEXT,total_area REAL,total_price REAL,payload TEXT);
CREATE TABLE estimate_revisions(revision_id TEXT,estimate_id TEXT,dealer_id TEXT,revised_at TEXT,customer_name TEXT,customer_phone TEXT,customer_email TEXT,address TEXT,total_area REAL,total_price REAL,payload TEXT);
INSERT INTO dealers VALUES('a','active',25),('b','active',25);
INSERT INTO dealer_employees VALUES('ea','a','active'),('eb','b','active');
INSERT INTO estimates VALUES('qa','a','2026-10-14','Alice','','','A',100,10,'{}'),('qb','b','2026-10-14','Bob','','','B',200,20,'{}');''')
class DB:
 postgres=False
 def execute(self,*args):return con.execute(*args)
 def close(self):pass
 def commit(self):con.commit()
session={'dealer_id':'a','account_type':'employee','employee_id':'ea'}
req=SimpleNamespace(is_json=False,path='/api/estimates',method='GET',get_json=lambda **kw:{},args={})
scope=dict(lock_account=lock_account,session=session,request=req,estimate_db=DB,jsonify=lambda *a,**kw:a[0] if a else kw,redirect=lambda url:('redirect',url),is_head_office=lambda:False,auth_version=lambda *args:0,json=json,Response=lambda body,**kw:(body,kw))
for name in ['is_employee','is_dealer_owner','require_dealer_login','account_profile_api','estimate_history_one','estimate_history_versions','dealer_employee_status']:
 n=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name);n.decorator_list=[]
 exec(compile(ast.Module(body=[n],type_ignores=[]),'app.py','exec'),scope)
limits=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PLAN_LIMITS' for t in n.targets))
assert [limits[k] for k in ['trial','basic','pro','business']]==[3,25,75,200]
assert scope['require_dealer_login']() is None
assert scope['estimate_history_one']('qa')['id']=='qa'
assert scope['estimate_history_one']('qb')[1]==404
assert scope['estimate_history_versions']('qb')[1]==404
req.method='POST';assert scope['account_profile_api']()[1]==403
req.method='GET';scope['_account_profile']=lambda did:{'id':did}
assert scope['account_profile_api']()=={'id':'a'}
con.execute("UPDATE dealer_employees SET status='disabled' WHERE id='ea'")
assert scope['require_dealer_login']()[1]==401 and not session
con.execute("UPDATE dealer_employees SET status='active' WHERE id='ea'")
session.update(dealer_id='a',account_type='employee',employee_id='ea');assert scope['require_dealer_login']() is None
session['employee_id']='eb';assert scope['require_dealer_login']()[1]==401 and not session
session.update(dealer_id='a',account_type='owner');assert scope['require_dealer_login']() is None
con.commit();req.form={'action':'disable'};scope['dealer_employee_status']('eb')
assert con.execute("SELECT status FROM dealer_employees WHERE id='eb'").fetchone()[0]=='active'
con.execute("UPDATE dealers SET status='disabled' WHERE id='a'");assert scope['require_dealer_login']()[1]==401 and not session
session.update(dealer_id='a',account_type='employee',employee_id='ea');assert scope['require_dealer_login']()[1]==401
req.path='/site/pricing.html';assert scope['require_dealer_login']() is None
assert 'Basic includes 25 property measurements' in (root/'site/pricing.html').read_text()
print('PASS: plan values, business isolation, employee read-only settings, immediate disable, reactivation, owner disable, cross-business employee rejection and public-site access')
