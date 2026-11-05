"""Targeted normal-auth checks; temporary SQLite and fictional identities only."""
import os, sys, tempfile, uuid, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory() as tmp:
    os.environ['DATABASE_URL']=''
    os.environ['ESTIMATE_DB_PATH']=str(Path(tmp)/'qa.db')
    import app as a
    a.is_recovery_test_service=lambda:False
    secret=uuid.uuid4().hex
    con=a.estimate_db()
    for did in ['office','owner','other']:
        con.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,status,lookup_limit,estimate_limit,created_at,plan_code) VALUES(?,?,?,?, 'active',25,25,'2026-10-01','basic')",(did,'QA TEST '+did,did+'@example.invalid',a.password_hash(secret)))
    con.execute("INSERT INTO dealer_employees(id,dealer_id,employee_name,email,password_hash,status,created_at) VALUES('employee','owner','QA TEST Employee','employee@example.invalid',?,'active','2026-10-01')",(a.password_hash(secret),))
    con.execute("INSERT INTO account_admin_roles(dealer_id) VALUES('office')")
    con.execute("INSERT INTO estimates(id,dealer_id,created_at,customer_name,address,total_area,total_price,payload) VALUES('private','owner','2026-10-01','QA FICTIONAL','QA FICTIONAL',1,1,'{}')")
    con.commit();con.close()
    def login(identity):
        c=a.app.test_client()
        response=c.post('/dealer-login',data={'email':identity+'@example.invalid','password':secret})
        assert response.status_code==302 and response.location=='/'
        return c
    office,owner,employee=map(login,['office','owner','employee'])
    assert office.get('/head-office/dealers').status_code==200
    for suffix in ['', '/versions']:
        assert office.get('/api/estimates/private'+suffix).status_code==404
    assert owner.get('/api/estimates/private').status_code==200
    assert employee.get('/api/estimates/private').status_code==200
    page=office.get('/head-office/credits?q=owner%40example.invalid').data.decode()
    csrf=re.search(r'name="csrf" value="([^"]+)"',page).group(1)
    def access(action):
        return office.post('/head-office/credits',data=dict(csrf=csrf,operation=str(uuid.uuid4()),dealer_id='owner',action=action,reason='QA FICTIONAL CONTROL TEST'))
    assert access('disable').status_code==302
    assert owner.get('/api/account/profile').status_code==401
    assert employee.get('/api/estimates').status_code==401
    for identity in ['owner','employee']:
        c=a.app.test_client()
        assert b'Email or password is incorrect' in c.post('/dealer-login',data={'email':identity+'@example.invalid','password':secret}).data
    assert access('reactivate').status_code==302
    owner,employee=map(login,['owner','employee'])
    assert owner.get('/api/estimates/private').status_code==200
    assert employee.get('/api/estimates/private').status_code==200
    assert owner.post('/dealer-employees/employee/status',data={'action':'disable'}).status_code==302
    assert employee.get('/api/estimates').status_code==401
    assert owner.post('/dealer-employees/employee/status',data={'action':'activate'}).status_code==302
    employee=login('employee')
    assert employee.get('/api/estimates/private').status_code==200
    assert office.get('/logout').status_code==302
    for path in ['/head-office/dealers','/head-office/credits']:
        result=office.get(path)
        assert result.status_code==302 and result.location=='/dealer-login'
    print('PASS: normal password authentication; private estimate/history denied to Head Office; owner and employee disabled sessions rejected; disabled normal logins rejected; normal re-login after reactivation; individual employee disable/reactivate; logout blocks both dashboards. Temporary fictional SQLite discarded.')
