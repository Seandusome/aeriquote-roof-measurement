"""Secret-canary regressions: temporary storage and real loopback Gunicorn only."""
import io,json,logging,os,re,socket,subprocess,sys,tempfile,time,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from safe_logging import install_safe_logging
install_safe_logging()
CANARIES=['QA_ONLY_TOKEN_73816','QA_ONLY_PASSWORD_93817','QA_ONLY_KEY_53818',
          'QA_ONLY_COOKIE_13819','QA_ONLY_BEARER_23820','QA_ONLY_PRIVATE_CUSTOMER_43821']
stream=io.StringIO();handler=logging.StreamHandler(stream)
handler.setFormatter(logging.Formatter('%(levelname)s %(name)s %(module)s:%(lineno)s %(message)s'))
logger=logging.getLogger('qa.untrusted');logger.addHandler(handler);logger.setLevel(logging.DEBUG);logger.propagate=False
messages=[
 'https://qa.invalid/reset-password?ToKeN='+CANARIES[0]+'&password='+CANARIES[1],
 {'api_key':CANARIES[2],'Cookie':CANARIES[3],'Authorization':'Bearer '+CANARIES[4]},
 'password=%s token=%s Authorization=%s api_key=%s customer=%s',
]
logger.warning(messages[0]);logger.error(messages[1]);logger.info(messages[2],CANARIES[1],CANARIES[0],CANARIES[4],CANARIES[2],CANARIES[5])
try:
 try:raise ValueError(CANARIES[0])
 except ValueError as e:raise RuntimeError('postgresql://qa:'+CANARIES[1]+'@localhost/qa') from e
except RuntimeError:logger.exception('request body=%s',CANARIES[5],stack_info=True)
class SecretObject:
 def __str__(self):raise AssertionError('Do not stringify untrusted log objects')
logger.error(SecretObject())
raw=stream.getvalue();assert all(c not in raw for c in CANARIES)
assert 'exception=RuntimeError' in raw and '[details redacted]' in raw and 'ERROR' in raw
# Gunicorn access mapping: even a custom format cannot select raw headers/queries.
access=logging.getLogger('gunicorn.access');access.addHandler(handler);access.setLevel(logging.INFO)
atoms={'m':'POST','U':'/reset-password','s':'500','B':'123','L':'0.125','q':'?token='+CANARIES[0],
       'r':'POST /reset-password?token='+CANARIES[0]+' HTTP/1.1','{authorization}i':CANARIES[4]}
access.info('%(r)s %(q)s %({authorization}i)s',atoms)
assert 'route=password_recovery' in stream.getvalue() and 'status=500' in stream.getvalue()
assert all(c not in stream.getvalue() for c in CANARIES)
access.removeHandler(handler);logger.removeHandler(handler)

with tempfile.TemporaryDirectory() as td:
 env=dict(os.environ,DATABASE_URL='',ESTIMATE_DB_PATH=td+'/qa.db',FLASK_SECRET_KEY='fictional-logging-only',PYTHONPATH=td+os.pathsep+str(ROOT))
 env.pop('RENDER_SERVICE_ID',None);env.pop('RENDER_EXTERNAL_HOSTNAME',None)
 Path(td,'qa_logging_wsgi.py').write_text("from app import app\n@app.route('/health',methods=['GET','POST'])\ndef qa_log_failure():\n raise RuntimeError("+repr('api_key='+CANARIES[2]+' password='+CANARIES[1]+' customer='+CANARIES[5])+")\n")
 for preload in (False,True):
  sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
  with tempfile.TemporaryFile(mode='w+') as output:
   cmd=[sys.executable,'-m','gunicorn','qa_logging_wsgi:app','--bind',f'127.0.0.1:{port}','--workers','1','--threads','2','--access-logfile','-','--error-logfile','-']
   if preload:cmd.append('--preload')
   proc=subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT)
   def get(path,data=None):
    headers={'Authorization':'Bearer '+CANARIES[4],'Cookie':'qa='+CANARIES[3],
             'Referer':'https://qa.invalid/reset-password?token='+CANARIES[0], 'User-Agent':CANARIES[5],
             'Content-Type':'application/json'}
    req=urllib.request.Request(f'http://127.0.0.1:{port}'+path,data=data,headers=headers)
    try:
     with urllib.request.urlopen(req,timeout=3) as r:return r.status,r.read()
    except urllib.error.HTTPError as e:return e.code,e.read()
   try:
    for attempt in range(70):
     assert proc.poll() is None,'QA server stopped unexpectedly'
     try:get('/api/public/support/config');break
     except OSError:time.sleep(.1)
    else:raise AssertionError('QA readiness timeout')
    code,body=get('/reset-password?token='+CANARIES[0]+'&password='+CANARIES[1]+'&api_key='+CANARIES[2]);assert code==400
    code,body=get('/health?token='+CANARIES[0],json.dumps(dict(zip(('password','token','api_key'),CANARIES[:3]))).encode());assert code==500
    assert all(c.encode() not in body for c in CANARIES)
    get('/'+CANARIES[2]+'?access_token='+CANARIES[4])
   finally:proc.terminate();proc.wait(timeout=15)
   output.seek(0);logs=output.read()
   assert all(c not in logs for c in CANARIES),'Secret canary reached a Gunicorn/application log'
   assert 'route=password_recovery' in logs and 'status=500' in logs and 'exception=RuntimeError' in logs
   assert 'server_start' in logs and 'worker_start' in logs,'Startup retains safe lifecycle events'
 # Prove Gunicorn master/worker boot exceptions are filtered before Flask imports.
 Path(td,'qa_boot_failure.py').write_text('raise RuntimeError('+repr(CANARIES[2])+')\n')
 failed=subprocess.run([sys.executable,'-m','gunicorn','qa_boot_failure:app','--bind','127.0.0.1:0','--access-logfile','-','--error-logfile','-'],cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=15)
 assert failed.returncode!=0 and CANARIES[2] not in failed.stdout
 assert 'worker_exception' in failed.stdout

# Every application-owned browser diagnostic must use only fixed literal text.
source=(ROOT/'app.py').read_text()
calls=re.findall(r'console\.(?:error|warn|log|debug|info)\(([^\n]*?)\)',source)
assert calls and all(re.fullmatch(r"'[^']*'",arg) for arg in calls), 'Raw browser error/payload logging reintroduced'
assert "console.error('AQ:pdf-generation-failed')" in source
print(json.dumps({'result':'PASS','python_secret_canaries':len(CANARIES),'real_gunicorn_modes':['normal','preload','worker_boot_failure'], 'query_headers_body_exception_values_absent':True,'safe_status_duration_event_and_location_retained':True,'browser_fixed_message_calls':len(calls),'password_reset_and_session_semantics_changed':False,'production_data_accessed':False}))
