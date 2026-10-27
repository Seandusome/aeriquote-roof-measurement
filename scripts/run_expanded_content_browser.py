"""Run disposable server and export matrix together; loopback networking only."""
import os,subprocess,socket,time,sys
server=subprocess.Popen([sys.executable,'scripts/prelaunch_browser_server.py'],stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)
try:
 for i in range(100):
  try:
   with socket.create_connection(('127.0.0.1',8765),timeout=.2):break
  except OSError:time.sleep(.1)
 else:raise RuntimeError('Fixture server not ready')
 raise SystemExit(subprocess.call(['node','scripts/test_browser_expanded_content.cjs'],env=os.environ))
finally:server.terminate();server.wait()
