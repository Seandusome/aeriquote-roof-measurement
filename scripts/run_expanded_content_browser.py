"""Run disposable server and export matrix together; loopback networking only."""
import os,subprocess,socket,time,sys
target=sys.argv[1] if len(sys.argv)>1 else 'scripts/test_browser_expanded_content.cjs'
if target not in {'scripts/test_browser_expanded_content.cjs','scripts/test_pdf_failure_browser.cjs','scripts/test_browser_recovery.cjs','scripts/test_employee_csrf_browser.cjs','scripts/test_interrupted_correction_browser.cjs'}:raise SystemExit('Isolated browser QA scripts only')
try:
 with socket.create_connection(('127.0.0.1',8765),timeout=.2):raise RuntimeError('Port8765 is already in use; refusing to test an unknown server')
except OSError:pass
server=subprocess.Popen([sys.executable,'scripts/prelaunch_browser_server.py'],stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)
try:
 for i in range(100):
  try:
   with socket.create_connection(('127.0.0.1',8765),timeout=.2):break
  except OSError:time.sleep(.1)
 else:raise RuntimeError('Fixture server not ready')
 raise SystemExit(subprocess.call(['node',target],env=os.environ))
finally:server.terminate();server.wait()
