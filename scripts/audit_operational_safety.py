"""Readiness evidence using disposable SQLite, mocked email and loopback Gunicorn.
Findings are observations, not passing production-readiness gates. No live requests.
"""
import os,sys,tempfile,uuid,json,re,logging,io,socket,subprocess,time,urllib.request,urllib.error
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
with tempfile.TemporaryDirectory() as scratch:
 os.environ.update(DATABASE_URL='',ESTIMATE_DB_PATH=scratch+'/audit.db',FLASK_SECRET_KEY='fictional-operational-audit-only')
 import app as a, support_center as support
 a.app.config['TESTING']=True
 c=a.app.test_client();findings={}
 findings['health_status']=c.get('/health').status_code
 findings['healthz_status']=c.get('/healthz').status_code
 findings['healthz_redirects_to_login']=c.get('/healthz').location=='/dealer-login'
 token=c.get('/api/public/support/config').json['csrf'];rid=str(uuid.uuid4())
 message='FICTIONAL QA issue. password=QA_FAKE_SUPPORT_PASSWORD api_key=QA_FAKE_SUPPORT_KEY customer=QA Fictional Customer'
 d=dict(request_id=rid,name='Fictional QA',company='Fictional Business',email='qa@example.invalid',topic='bug-report',message=message,device='Mobile phone',page_url='https://qa.example.invalid/reset-password?token=QA_FAKE_URL_TOKEN#private')
 log=io.StringIO();handler=logging.StreamHandler(log);a.app.logger.addHandler(handler)
 try:
  with patch.object(support,'notify_support',side_effect=RuntimeError('QA_FAKE_PROVIDER_EXCEPTION_KEY')) as mail:
   r=c.post('/api/public/support',json=d,headers={'X-CSRF-Token':token});assert r.status_code==201
   assert c.post('/api/public/support',json=d,headers={'X-CSRF-Token':token}).json['reference']==r.json['reference'];assert mail.call_count==1
 finally:a.app.logger.removeHandler(handler)
 con=a.estimate_db();row=dict(con.execute('SELECT * FROM support_requests WHERE id=?',(rid,)).fetchone());con.close()
 assert row['notification_status']=='failed' and row['page_url']=='https://qa.example.invalid/reset-password'
 assert 'QA_FAKE_PROVIDER_EXCEPTION_KEY' not in log.getvalue()
 findings.update(support_saved_before_mail_failure=True,support_retry_idempotent=True,support_page_query_fragment_removed=True,support_notification_exception_sanitized=True,support_free_text_preserved_verbatim=row['message']==message,support_free_text_secret_redaction=False)
 assert c.get('/head-office/support').status_code in (302,403)
 # Register the same isolated inbox with an explicit office gate; never log in to a real office.
 from flask import Flask
 office=Flask('qa-operational-office');office.secret_key='fictional-only';allowed=[False]
 support.register_support(office,a.estimate_db,lambda:allowed[0]);oc=office.test_client();assert oc.get('/head-office/support').status_code==403;allowed[0]=True
 inbox=oc.get('/head-office/support').get_data(as_text=True);assert row['reference'] in inbox
 with oc.session_transaction() as s:csrf=s['support_csrf']
 assert oc.post('/head-office/support/'+rid+'/manage',data={'csrf':csrf,'action':'update','status':'in-progress','note':'P1 - incorrect estimate reported; no customer estimate requested'}).status_code==302
 con=a.estimate_db();assert con.execute('SELECT status FROM support_requests WHERE id=?',(rid,)).fetchone()['status']=='in-progress';assert con.execute('SELECT COUNT(*) AS n FROM support_notes WHERE ticket_id=?',(rid,)).fetchone()['n']==1;con.close()
 findings.update(support_office_gate=True,support_status_and_manual_priority_note=True,automatic_priority_field=False,private_estimate_access_not_required=True)
 # Real default Gunicorn access format from the configured recovery command.
 wrapper=Path(scratch)/'qa_audit_wsgi.py';wrapper.write_text("from app import app\n@app.get('/health')\ndef qa_canary_error():\n raise RuntimeError('api_key=QA_FAKE_UNHANDLED_KEY')\n")
 sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
 env=dict(os.environ,PYTHONPATH=scratch+os.pathsep+str(ROOT),ESTIMATE_DB_PATH=scratch+'/wsgi.db')
 with tempfile.TemporaryFile(mode='w+') as output:
  proc=subprocess.Popen([sys.executable,'-m','gunicorn','qa_audit_wsgi:app','--bind',f'127.0.0.1:{port}','--workers','1','--threads','2','--access-logfile','-','--error-logfile','-'],cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT)
  try:
   def get(path):
    try:return urllib.request.urlopen(f'http://127.0.0.1:{port}'+path,timeout=3).read()
    except urllib.error.HTTPError as e:return e.read()
   for _ in range(60):
    if proc.poll() is not None:raise RuntimeError('Isolated Gunicorn failed to start')
    try:get('/api/public/support/config');break
    except OSError:time.sleep(.1)
   else:raise RuntimeError('Isolated Gunicorn readiness timeout')
   get('/reset-password?token=QA_FAKE_ACCESSLOG_RESET_TOKEN')
   body=get('/health');assert b'QA_FAKE_UNHANDLED_KEY' not in body
  finally:proc.terminate();proc.wait(timeout=15)
  output.seek(0);raw=output.read()
  findings.update(default_access_log_records_reset_query='QA_FAKE_ACCESSLOG_RESET_TOKEN' in raw,unhandled_exception_log_lacks_global_secret_scrub='QA_FAKE_UNHANDLED_KEY' in raw,generic_500_body_does_not_echo_exception=True)
 print(json.dumps({'isolated_functional_tests':'passed','readiness_findings':findings,'no_live_data_or_email':True},indent=2))
 if '--output' in sys.argv:Path(sys.argv[sys.argv.index('--output')+1]).write_text(json.dumps(findings,indent=2))
