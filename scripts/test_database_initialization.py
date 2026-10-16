"""Schema setup must not run during concurrent authenticated image requests."""
import os,sys,tempfile,threading,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory() as tmp:
 os.environ['DATABASE_URL']='';os.environ['ESTIMATE_DB_PATH']=str(Path(tmp)/'concurrent.db')
 import app as a
 con=a.estimate_db()
 con.execute("INSERT INTO dealers (id,dealer_name,email,password_hash,state,status,created_at) VALUES (?,?,?,?,?,?,?)",('concurrent-owner','Concurrent test','owner@example.invalid','not-used','SK','active','2026-10-16'))
 con.commit();con.close()
 a.SESSIONS['concurrent-images']={'key':'test-only','rgb':'https://example.invalid/rgb','rgb_cache':None,'mask':'https://example.invalid/mask','mask_cache':None,'street':'https://example.invalid/street','street_cache':None}
 original=a.DBCompat.execute;ddl=[]
 def track(self,sql,params=()):
  if sql.lstrip().upper().startswith(('ALTER ','CREATE ','DROP ')):ddl.append(sql)
  return original(self,sql,params)
 def image_request(index):
  client=a.app.test_client()
  with client.session_transaction() as session:session['dealer_id']='concurrent-owner';session['auth_version']=0
  return client.get(['/rgb/','/mask/','/street/'][index%3]+'concurrent-images').status_code
 with patch.object(a.DBCompat,'execute',track),patch.object(a,'req_bytes',lambda *args,**kwargs:('image/tiff',b'image-fixture')):
  with ThreadPoolExecutor(max_workers=8) as pool:statuses=list(pool.map(image_request,range(24)))
 assert statuses==[200]*24,statuses
 assert not ddl,'Repeated image authentication must not execute schema DDL'
 # Initialization is serialized and successful work is cached, including PostgreSQL
 # advisory locking across processes. Use fakes here; no live database credentials.
 class Raw:
  def __init__(self):self.closed=False;self.queries=[]
  def execute(self,sql,params=()):self.queries.append((sql,params));return self
  def close(self):self.closed=True
 connections=[];counter=[0];lock=threading.Lock()
 def connect(*args,**kwargs):
  assert kwargs['connect_timeout']==10
  raw=Raw();connections.append(raw);return raw
 def init(con):
  with lock:counter[0]+=1
  time.sleep(.02)
  con.execute('ALTER TABLE test ADD COLUMN IF NOT EXISTS test TEXT')
 a._ESTIMATE_SCHEMA_READY.clear()
 with patch.object(a,'DATABASE_URL','postgresql://test-only'),patch.object(a,'psycopg',type('FakePsycopg',(),{'connect':staticmethod(connect)})),patch.object(a,'_initialize_estimate_schema',init):
  with ThreadPoolExecutor(max_workers=8) as pool:
   list(pool.map(lambda _:a.estimate_db().close(),range(16)))
  assert counter[0]==1,counter
  assert sum(any('pg_advisory_xact_lock' in sql for sql,_ in raw.queries) for raw in connections)==1
  assert sum(any(sql.startswith('ALTER ') for sql,_ in raw.queries) for raw in connections)==1
  # A failed initialization closes its connection and is not marked ready.
  a._ESTIMATE_SCHEMA_READY.clear();fail_count=[0]
  def retry_init(con):
   fail_count[0]+=1
   if fail_count[0]==1:raise RuntimeError('simulated initialization failure')
  with patch.object(a,'_initialize_estimate_schema',retry_init):
   try:a.estimate_db()
   except RuntimeError:pass
   else:raise AssertionError('Expected first initialization failure')
   assert connections[-1].closed
   assert not a._ESTIMATE_SCHEMA_READY
   a.estimate_db().close();assert fail_count[0]==2
print('PASS: 24 concurrent authenticated imagery requests, no repeated DDL, serialized PostgreSQL initialization/advisory lock, failure cleanup and retry')
