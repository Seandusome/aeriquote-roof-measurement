"""Launch disposable browser review in one network namespace; no hosted settings."""
import os,subprocess,sys,time,urllib.request,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
os.chdir(root)
launch="import runpy,os; m=runpy.run_path('scripts/prelaunch_browser_server.py'); os.environ['AERIQUOTE_MANUAL_ROOF_QA']='0'; import json; c=m['a'].estimate_db(); profile=dict(m['profile'],businessType='roofing'); c.execute('UPDATE dealer_profiles SET profile_json=? WHERE dealer_id=?',(json.dumps(profile),'qa-browser')); c.execute('UPDATE dealers SET industry=? WHERE id=?',('roofing','qa-browser')); c.commit(); c.close(); m['a'].app.run(host='127.0.0.1',port=8765,threaded=True,use_reloader=False)"
with tempfile.TemporaryDirectory(prefix='aq-copy-runtime-') as scratch, open('/tmp/aq-copy-browser-server.log','w') as log:
 server=subprocess.Popen([sys.executable,'-c',launch],stdout=log,stderr=log,env={**os.environ,'TMPDIR':scratch})
 try:
  for _ in range(60):
   try:
    with urllib.request.urlopen('http://127.0.0.1:8765/dealer-login',timeout=.5):break
   except Exception:time.sleep(.2)
  else:raise RuntimeError('Disposable loopback server did not become ready')
  sys.exit(subprocess.run(['node','scripts/test_customer_copy_browser.cjs']).returncode)
 finally:
  server.terminate();server.wait(timeout=5)
