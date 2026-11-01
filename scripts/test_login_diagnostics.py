"""Disposable SQLite only; fixed login decisions, no secret-bearing diagnostics."""
import io, logging, os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory() as tmp:
    os.environ['DATABASE_URL']=''
    os.environ['ESTIMATE_DB_PATH']=str(Path(tmp)/'login.db')
    import app as a
    email='fictional-login-diagnostic@example.invalid'
    password='SYNTHETIC_PASSWORD_CANARY_NOT_REAL'
    os.environ['AERIQUOTE_LOGIN_DIAGNOSTIC_EMAIL']=email
    con=a.estimate_db()
    con.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,status,created_at) VALUES(?,?,?,?,?,?)",('diag-owner','FICTIONAL QA',email,a.password_hash(password),'active','2026-11-01'))
    con.commit();con.close()
    stream=io.StringIO();handler=logging.StreamHandler(stream);a.app.logger.addHandler(handler)
    def attempt(secret=password,address=email):
        stream.seek(0);stream.truncate(0)
        c=a.app.test_client()
        response=c.post('/dealer-login',data={'email':address,'password':secret})
        return c,response,stream.getvalue()
    with patch.object(a,'is_recovery_test_service',return_value=True):
        c,r,logs=attempt('WRONG_SYNTHETIC_CANARY')
        assert r.status_code==200 and b'Email or password is incorrect.' in r.data
        assert 'stage=owner_found' in logs and 'stage=owner_verifier_fail' in logs and 'stage=rejected' in logs
        assert 'stage=session_created' not in logs and 'Set-Cookie' not in r.headers
        assert len(r.headers['X-AeriQuote-Login-Diagnostic'])==32
        assert all('id='+r.headers['X-AeriQuote-Login-Diagnostic'] in line for line in logs.splitlines())
        assert c.get('/api/account/profile').status_code==401
        c,r,logs=attempt()
        assert r.status_code==302 and r.headers['Location']=='/' and 'Set-Cookie' in r.headers
        assert 'stage=owner_verifier_pass' in logs and 'stage=session_created' in logs
        assert c.get('/api/account/profile').status_code==200
        for forbidden in (email,password,'WRONG_SYNTHETIC_CANARY','password_hash'):
            assert forbidden not in logs
        con=a.estimate_db();con.execute("UPDATE dealers SET status='disabled' WHERE id='diag-owner'");con.commit();con.close()
        _,r,logs=attempt()
        assert r.status_code==200 and 'stage=owner_inactive' in logs
        assert 'stage=owner_verifier_' not in logs and 'Set-Cookie' not in r.headers
        con=a.estimate_db();con.execute("UPDATE dealers SET status='active' WHERE id='diag-owner'");con.commit();con.close()
        with patch.object(a,'limited',return_value=True):
            _,r,logs=attempt()
            assert r.status_code==429 and 'stage=rate_limited' in logs and 'stage=owner_found' not in logs
        _,r,logs=attempt(address='unmatched@example.invalid')
        assert not logs and 'X-AeriQuote-Login-Diagnostic' not in r.headers
    with patch.object(a,'is_recovery_test_service',return_value=False):
        _,r,logs=attempt()
        assert r.status_code==302 and not logs and 'X-AeriQuote-Login-Diagnostic' not in r.headers
    del os.environ['AERIQUOTE_LOGIN_DIAGNOSTIC_EMAIL']
    with patch.object(a,'is_recovery_test_service',return_value=True):
        _,r,logs=attempt()
        assert r.status_code==302 and not logs and 'X-AeriQuote-Login-Diagnostic' not in r.headers
    stream.seek(0);stream.truncate(0)
    a.app.logger.warning('AQ login diagnostic stage=%s id=%s',password,'f'*32)
    assert password not in stream.getvalue() and 'event=qa_login' not in stream.getvalue()
    stream.seek(0);stream.truncate(0)
    a.app.logger.warning('AQ login diagnostic stage=%s id=%s','received',email)
    assert email not in stream.getvalue() and 'event=qa_login' not in stream.getvalue()
    a.app.logger.removeHandler(handler)
print('PASS: scoped diagnostics distinguish verifier rejection from session creation; successful cookies/profile, default-off, production exclusion and secret-canary redaction preserved')
