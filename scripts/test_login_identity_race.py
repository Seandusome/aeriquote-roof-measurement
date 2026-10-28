"""Deterministic signup/employee identity race in a disposable database only."""
import os,sys,tempfile,threading
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory() as tmp:
    url=os.environ.get('QA_POSTGRES_URL','') if '--postgres' in sys.argv else ''
    if '--postgres' in sys.argv:
        parsed=urlsplit(url);assert parsed.hostname in ('localhost','127.0.0.1') and parsed.path=='/aeriquote_qa'
    os.environ.update(DATABASE_URL=url,ESTIMATE_DB_PATH=tmp+'/identity.db')
    import app as a
    a.app.config['TESTING']=True
    con=a.estimate_db();con.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,status,created_at) VALUES('identity-race-owner','QA ONLY','identity-race-owner@example.invalid',?,'active','2026-10-28')",(a.password_hash('fictional-password'),));con.commit();con.close()
    owner=a.app.test_client();signup=a.app.test_client()
    assert owner.post('/dealer-login',data={'email':'identity-race-owner@example.invalid','password':'fictional-password'}).status_code==302
    target='identity-race-target@example.invalid'
    employee_inserting=threading.Event();signup_checked=threading.Event();employee_committed=threading.Event()
    original_execute=a.DBCompat.execute;original_check=a.login_email_in_use
    def intercept_insert(con,query,params=()):
        if query.startswith('INSERT INTO dealer_employees(') and target in params:
            employee_inserting.set()
            # Correct locking prevents signup's check until this transaction ends.
            signup_checked.wait(2)
        return original_execute(con,query,params)
    def checked(con,email):
        result=original_check(con,email)
        if email==target:
            signup_checked.set();assert employee_committed.wait(10)
        return result
    def employee_request():
        try:return owner.post('/dealer-employees',data={'employee_name':'QA ONLY','email':target,'password':'fictional-password'}).status_code
        finally:employee_committed.set()
    with patch.object(a.DBCompat,'execute',intercept_insert),patch.object(a,'login_email_in_use',checked),ThreadPoolExecutor(max_workers=2) as pool:
        employee_future=pool.submit(employee_request);assert employee_inserting.wait(10)
        signup_future=pool.submit(lambda:signup.post('/api/public/signup',json={'name':'QA ONLY','company':'QA ONLY','email':target.upper(),'password':'fictional-password','industry':'snow'}).status_code)
        employee_status=employee_future.result(15);signup_status=signup_future.result(15)
    con=a.estimate_db()
    identities=con.execute('SELECT id FROM dealers WHERE LOWER(email)=? UNION ALL SELECT id FROM dealer_employees WHERE LOWER(email)=?',(target,target)).fetchall();con.close()
    assert employee_status==200 and signup_status==409 and len(identities)==1,(employee_status,signup_status,len(identities))
    assert signup.get('/api/account/profile').status_code==401,'Rejected signup must not authenticate as the employee or owner'
    assert owner.get('/api/account/profile').json['id']=='identity-race-owner'
    print('PASS concurrent case-insensitive signup/employee email collision has one identity, clear duplicate response and no foreign session; '+('PostgreSQL' if url else 'SQLite'))
