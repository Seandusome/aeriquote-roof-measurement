"""Disposable account lifecycle and reset/login race. Never sends actual mail."""
import os,sys,tempfile,re,threading,uuid
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
scratch=tempfile.TemporaryDirectory()
url=os.environ.get('QA_POSTGRES_URL','') if '--postgres' in sys.argv else ''
if '--postgres' in sys.argv:
    parts=urlsplit(url);assert parts.hostname in ('localhost','127.0.0.1') and parts.path=='/aeriquote_qa'
os.environ.update(DATABASE_URL=url,ESTIMATE_DB_PATH=scratch.name+'/security.db',RESEND_API_KEY='mock-only',PASSWORD_RESET_FROM='QA <qa@example.invalid>',AERIQUOTE_PUBLIC_URL='https://qa.example.invalid')
import app as a
a.app.config['TESTING']=True
def sql(query,params=(),fetch=False):
    con=a.estimate_db()
    try:
        cur=con.execute(query,params);row=cur.fetchone() if fetch else None;con.commit();return row
    finally:con.close()
did='security-lifecycle';email='security-owner@example.invalid'
sql("INSERT INTO dealers(id,dealer_name,email,password_hash,status,created_at) VALUES(?,?,?,?,'active','2026-10-28')",(did,'QA ONLY',email,a.password_hash('fictional-old-password')))
sql("INSERT INTO dealer_employees(id,dealer_id,employee_name,email,password_hash,status,created_at) VALUES('security-employee',?,'QA ONLY','security-employee@example.invalid',?,'disabled','2026-10-28')",(did,a.password_hash('fictional-employee-password')))
owner=a.app.test_client()
assert owner.post('/dealer-login',data={'email':email,'password':'fictional-old-password'}).status_code==302
failures=[]
for body in [{},{'action':''},{'action':'enable'},{'action':'delete'}]:
    sql("UPDATE dealer_employees SET status='disabled' WHERE id='security-employee'")
    r=owner.post('/dealer-employees/security-employee/status',data=body)
    if r.status_code!=400 or sql("SELECT status FROM dealer_employees WHERE id='security-employee'",fetch=True)['status']!='disabled':failures.append('Malformed action reactivated employee: '+repr(body))
bad_email='not-an-email'
response=owner.post('/dealer-employees',data={'employee_name':'QA invalid','email':bad_email,'password':'fictional-password'})
if sql('SELECT COUNT(*) AS n FROM dealer_employees WHERE email=?',(bad_email,),True)['n']!=0:failures.append('Malformed login email created an employee')
assert owner.post('/dealer-employees/security-employee/status',data={'action':'activate'}).status_code==302
employee=a.app.test_client();assert employee.post('/dealer-login',data={'email':'security-employee@example.invalid','password':'fictional-employee-password'}).status_code==302
assert employee.post('/dealer-employees/security-employee/status',data={'action':'disable'}).status_code==403
assert owner.post('/dealer-employees/security-employee/status',data={'action':'disable'}).status_code==302
assert employee.get('/api/account/profile').status_code==401
assert owner.post('/dealer-employees/security-employee/status',data={'action':'activate'}).status_code==302
assert employee.get('/api/account/profile').status_code==401,'Reactivation must not revive an old session'
if '--employee-only' in sys.argv:
    assert not failures,'\n'.join(failures)
    print('PASS explicit employee actions, malformed-email rejection, disable/reactivation and permissions')
    sys.exit(0)

def csrf(client,path):return re.search(r'name="csrf" value="([^"]+)"',client.get(path).text).group(1)
for kind,account_email,old_password in [('owner',email,'fictional-old-password'),('employee','security-employee@example.invalid','fictional-employee-password')]:
    login=a.app.test_client();recovery=a.app.test_client();sent=[]
    with patch('account_recovery.send_reset_email',side_effect=lambda cfg,to,token:sent.append(token)):
        recovery.post('/forgot-password',data={'email':account_email,'csrf':csrf(recovery,'/forgot-password')})
    reset='/reset-password?token='+sent[0];token_csrf=csrf(recovery,reset)
    verified=threading.Event();release=threading.Event();original=a.password_ok
    def paused(password,stored):
        result=original(password,stored)
        if password==old_password and result:
            verified.set();assert release.wait(15),'Reset test did not release login'
        return result
    with patch.object(a,'password_ok',paused),ThreadPoolExecutor(max_workers=1) as pool:
        pending=pool.submit(lambda:login.post('/dealer-login',data={'email':account_email,'password':old_password}))
        assert verified.wait(15),'Login did not reach credential check'
        new_password='fictional-reset-'+kind
        try:
            assert recovery.post(reset,data={'csrf':token_csrf,'password':new_password,'confirm':new_password}).status_code==200
        finally:release.set()
        pending.result(timeout=15)
    if login.get('/api/account/profile').status_code!=401:failures.append(kind+' old-password login adopted a post-reset session version')
    assert recovery.post('/dealer-login',data={'email':account_email,'password':new_password}).status_code==302
    assert recovery.get('/api/account/profile').status_code==200
    assert recovery.get(reset).status_code==400,'Reset token remains single-use'
    print('PASS reset/new-password/single-use checks',kind)
assert not failures,'\n'.join(failures)
print('PASS explicit employee actions, login-email validation, disable/reactivation, employee permissions and owner/employee concurrent reset/login revocation; '+('PostgreSQL' if url else 'SQLite'))
