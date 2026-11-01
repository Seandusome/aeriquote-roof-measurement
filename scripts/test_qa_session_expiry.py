"""Real elapsed signed-cookie expiry; never connects to a database."""
import sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from flask import Flask,session
from qa_session_expiry import configure_qa_session_expiry

app=Flask(__name__);app.secret_key='DISPOSABLE_TEST_SECRET_ONLY'
default=app.permanent_session_lifetime
env={'RENDER_SERVICE_ID':'srv-db5a2g5ckfvc739fui70',
     'DATABASE_URL':'postgresql://fictional@dpg-dbj4f7lg1s2s73eob8t0-a/aeriquote_recovery_qa',
     'AERIQUOTE_QA_SESSION_LIFETIME_SECONDS':'1'}
invalid=[{'RENDER_SERVICE_ID':'production'},
         {'DATABASE_URL':'postgresql://fictional@other/aeriquote_recovery_qa'},
         {'DATABASE_URL':'postgresql://fictional@dpg-dbj4f7lg1s2s73eob8t0-a/other'}]
invalid += [{'AERIQUOTE_QA_SESSION_LIFETIME_SECONDS':v} for v in ('','invalid','0','-1','3601')]
assert not configure_qa_session_expiry(app,{})
for changes in invalid:
    assert not configure_qa_session_expiry(app,{**env,**changes})
    assert app.permanent_session_lifetime==default
assert configure_qa_session_expiry(app,env)
@app.get('/login')
def login():
    session['dealer_id']='FICTIONAL_QA';return 'signed in'
@app.get('/protected')
def protected():
    return ('authenticated',200) if session.get('dealer_id') else ('login required',401)
client=app.test_client();client.get('/login')
assert client.get('/protected').status_code==200
time.sleep(2.1)
assert client.get('/protected').status_code==401,'Actual elapsed Flask signed-cookie max_age must reject the session'
client.get('/login');assert client.get('/protected').status_code==200
print('PASS real elapsed signed-cookie expiry, fresh login recovery, default-off, production/foreign-database exclusion and bounded QA timeout')
