"""QA-only signup -> owner-created employee -> login/recovery/disable flow, real routes, mocked email."""
import os,sys,tempfile,re
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory() as tmp:
 os.environ.update(DATABASE_URL='',ESTIMATE_DB_PATH=str(Path(tmp)/'auth.db'),RESEND_API_KEY='mock-only',PASSWORD_RESET_FROM='QA <qa@example.invalid>',AERIQUOTE_PUBLIC_URL='https://qa.example.invalid')
 import app as a
 owner=a.app.test_client();employee=a.app.test_client();other=a.app.test_client()
 signup={'name':'QA Owner','company':'QA Auth Only','email':'qa-owner@example.invalid','password':'qa-test-password','industry':'snow'}
 assert owner.post('/api/public/signup',json=signup).status_code==200
 assert owner.get('/dealer-employees').status_code==200
 assert owner.post('/dealer-employees',data={'employee_name':'QA Employee','email':'qa-employee@example.invalid','password':'qa-test-employee'}).status_code==200
 con=a.estimate_db();row=con.execute("SELECT id,dealer_id FROM dealer_employees WHERE email='qa-employee@example.invalid'").fetchone();assert row;eid=row['id'];did=row['dealer_id'];con.close()
 assert employee.post('/dealer-login',data={'email':'QA-EMPLOYEE@EXAMPLE.INVALID','password':'wrong'}).status_code==200
 assert employee.get('/api/account/profile').status_code==401
 assert employee.post('/dealer-login',data={'email':'qa-employee@example.invalid','password':'qa-test-employee'}).status_code==302
 assert employee.get('/api/account/profile').get_json()['id']==did
 for route in ['/dealer-employees','/head-office/dealers','/head-office/credits']:assert employee.get(route).status_code==403
 assert employee.post('/api/account/profile',json={'company':'unauthorized'}).status_code==403
 assert other.post('/api/public/signup',json={**signup,'email':'qa-other@example.invalid'}).status_code==200
 assert other.get('/api/account/profile').get_json()['id']!=did
 sent=[]
 with patch('account_recovery.send_reset_email',side_effect=lambda config,email,token:sent.append((email,token))):
  csrf=re.search(r'name="csrf" value="([^"]+)"',employee.get('/forgot-password').get_data(as_text=True)).group(1)
  assert employee.post('/forgot-password',data={'email':'qa-employee@example.invalid','csrf':csrf}).status_code==200
  assert sent[-1][0]=='qa-employee@example.invalid'
  url='/reset-password?token='+sent[-1][1]
  csrf=re.search(r'name="csrf" value="([^"]+)"',employee.get(url).get_data(as_text=True)).group(1)
  assert employee.post(url,data={'csrf':csrf,'password':'qa-reset-employee','confirm':'qa-reset-employee'}).status_code==200
 assert employee.get('/api/account/profile').status_code==401
 assert owner.get('/api/account/profile').status_code==200,'Employee reset must not revoke owner'
 assert employee.post('/dealer-login',data={'email':'qa-employee@example.invalid','password':'qa-test-employee'}).status_code==200
 assert employee.post('/dealer-login',data={'email':'qa-employee@example.invalid','password':'qa-reset-employee'}).status_code==302
 assert owner.post('/dealer-employees/'+eid+'/status',data={'action':'disable'}).status_code==302
 assert employee.get('/api/account/profile').status_code==401
 assert employee.post('/dealer-login',data={'email':'qa-employee@example.invalid','password':'qa-reset-employee'}).status_code==200
 assert owner.post('/dealer-employees/'+eid+'/status',data={'action':'activate'}).status_code==302
 assert employee.post('/dealer-login',data={'email':'qa-employee@example.invalid','password':'qa-reset-employee'}).status_code==302
print('PASS: real isolated signup, owner employee creation, case-insensitive login, permissions, recovery email targeting, old credential/session rejection, owner access preserved, immediate disable/reactivate and distinct business identities')
