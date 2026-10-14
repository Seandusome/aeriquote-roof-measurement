"""Exercise live Flask routes with temporary storage and mocked email delivery."""
import os, sys, tempfile, re, time, hashlib
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory() as tmp:
 os.environ['ESTIMATE_DB_PATH']=str(Path(tmp)/'accounts.db');os.environ['DATABASE_URL']=''
 os.environ['FLASK_SECRET_KEY']='isolated-test-key';os.environ['RESEND_API_KEY']='mock-key'
 os.environ['PASSWORD_RESET_FROM']='AeriQuote <test@example.test>';os.environ['AERIQUOTE_PUBLIC_URL']='https://example.test'
 import app as application
 application.app.config['TESTING']=True
 con=application.estimate_db()
 for did,email in [('a','owner@example.test'),('b','other@example.test')]:
  con.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,status,created_at) VALUES(?,?,?,?,'active','2026-10-14')",(did,did,email,application.password_hash('old-password')))
 con.execute("INSERT INTO dealer_employees VALUES('ea','a','Employee','employee@example.test',?,'active','2026-10-14')",(application.password_hash('old-password'),));con.commit();con.close()
 client=application.app.test_client();owner_session=application.app.test_client();employee_session=application.app.test_client()
 assert owner_session.post('/dealer-login',data={'email':'owner@example.test','password':'old-password'}).status_code==302
 assert employee_session.post('/dealer-login',data={'email':'employee@example.test','password':'old-password'}).status_code==302
 def csrf(url):
  body=client.get(url).get_data(as_text=True);return re.search(r'name="csrf" value="([^"]+)"',body).group(1)
 sent=[]
 with patch('account_recovery.send_reset_email',side_effect=lambda config,email,token:sent.append((email,token))):
  assert client.post('/forgot-password',data={'email':'owner@example.test'}).status_code==400
  c=csrf('/forgot-password');known=client.post('/forgot-password',data={'email':'owner@example.test','csrf':c})
  unknown=client.post('/forgot-password',data={'email':'missing@example.test','csrf':c})
  assert known.status_code==unknown.status_code==200 and known.data==unknown.data
  token=sent[-1][1];url='/reset-password?token='+token;c=csrf(url)
  assert client.post(url,data={'csrf':c,'password':'new-password','confirm':'wrong'}).status_code==400
  assert client.post(url,data={'csrf':c,'password':'new-password','confirm':'new-password'}).status_code==200
  assert client.post(url,data={'csrf':c,'password':'new-password','confirm':'new-password'}).status_code==400
  assert owner_session.get('/api/account/profile').status_code==401
  assert client.post('/dealer-login',data={'email':'owner@example.test','password':'old-password'}).status_code==200
  assert client.post('/dealer-login',data={'email':'owner@example.test','password':'new-password'}).status_code==302
  # Employees reset their own password; shared owner account password is unchanged.
  c=csrf('/forgot-password');client.post('/forgot-password',data={'email':'employee@example.test','csrf':c})
  url='/reset-password?token='+sent[-1][1];c=csrf(url)
  assert client.post(url,data={'csrf':c,'password':'employee-new','confirm':'employee-new'}).status_code==200
  assert employee_session.get('/api/account/profile').status_code==401
  assert client.post('/dealer-login',data={'email':'employee@example.test','password':'employee-new'}).status_code==302
  con=application.estimate_db();con.execute("UPDATE dealer_employees SET status='disabled' WHERE id='ea'");con.commit();con.close()
  c=csrf('/forgot-password');client.post('/forgot-password',data={'email':'employee@example.test','csrf':c})
  url='/reset-password?token='+sent[-1][1];c=csrf(url)
  assert client.post(url,data={'csrf':c,'password':'disabled-new','confirm':'disabled-new'}).status_code==200
  assert client.post('/dealer-login',data={'email':'employee@example.test','password':'disabled-new'}).status_code==200
  # Expiration and per-address request limiting.
  c=csrf('/forgot-password');client.post('/forgot-password',data={'email':'other@example.test','csrf':c})
  token=sent[-1][1];con=application.estimate_db();con.execute('UPDATE password_reset_tokens SET expires_at=? WHERE token_hash=?',(time.time()-1,hashlib.sha256(token.encode()).hexdigest()));con.commit();con.close()
  assert client.get('/reset-password?token='+token).status_code==400
  client.post('/forgot-password',data={'email':'other@example.test','csrf':c});client.post('/forgot-password',data={'email':'other@example.test','csrf':c})
  assert client.post('/forgot-password',data={'email':'other@example.test','csrf':c}).status_code==429
  assert client.get('/reset-password?token=bad').status_code==400
  assert 'Public Login Coming' not in client.get('/site/login.html').get_data(as_text=True)
  assert '/dealer-login' in client.get('/site/login.html').get_data(as_text=True)
  # Invalid origin cannot be used to generate password-reset links.
  os.environ['AERIQUOTE_PUBLIC_URL']='http://example.test';assert client.post('/forgot-password',data={'email':'owner@example.test','csrf':c}).status_code==503
  os.environ['AERIQUOTE_PUBLIC_URL']='https://example.test'
  # Login request limiting applies to nonexistent logins as well as real ones.
  for _ in range(20):assert client.post('/dealer-login',data={'email':'limited@example.test','password':'wrong'}).status_code==200
  assert client.post('/dealer-login',data={'email':'limited@example.test','password':'wrong'}).status_code==429
  os.environ.pop('RESEND_API_KEY');assert client.post('/forgot-password',data={'email':'owner@example.test','csrf':c}).status_code==503
 print('PASS: real login/website routes, owner/employee resets, no account disclosure, CSRF, expiration, single use, password validation, old-session rejection, disabled-account enforcement, request limits and unconfigured-mail response')
