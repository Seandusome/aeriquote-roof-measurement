"""Support lifecycle, private notes, confirmations and legacy schema migration."""
import os,sys,tempfile,sqlite3,re,uuid
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory() as tmp:
 os.environ['DATABASE_URL']='';os.environ['ESTIMATE_DB_PATH']=str(Path(tmp)/'support.db')
 import app as a
 import support_center as s
 from flask import Flask
 app=Flask(__name__);app.secret_key='testing';allowed=[True]
 s.register_support(app,a.estimate_db,lambda:allowed[0]);client=app.test_client()
 token=client.get('/api/public/support/config').json['csrf'];tid=str(uuid.uuid4())
 data=dict(request_id=tid,name='Tester',email='tester@example.com',company='',topic='account-login',device='Mobile phone',page_url='',message='Test support workflow message')
 with patch.object(s,'notify_support',return_value='accepted') as notify:
  result=client.post('/api/public/support',json=data,headers={'X-CSRF-Token':token});assert result.status_code==201
  ref=result.json['reference']
  def manage(**fields):return client.post('/head-office/support/'+tid+'/manage',data=dict(csrf=token,**fields))
  assert manage(action='archive').status_code==400
  assert manage(action='update',status='invalid').status_code==400
  assert client.post('/head-office/support/'+tid+'/manage',data={'action':'update','status':'resolved'}).status_code==400
  assert manage(action='update',status='in-progress',note='<script>private</script>').status_code==302
  html=client.get('/head-office/support').get_data(as_text=True)
  assert 'In Progress' in html and '&lt;script&gt;private&lt;/script&gt;' in html and '<script>private</script>' not in html
  assert 'Accepted by email provider' in html
  assert manage(action='update',status='resolved',note='Replied by email; fixed setup.').status_code==302
  assert manage(action='archive').status_code==302
  assert ref not in client.get('/head-office/support').get_data(as_text=True)
  assert ref in client.get('/head-office/support?view=archived').get_data(as_text=True)
  assert manage(action='restore').status_code==302
  url='/head-office/support/'+tid+'/delete'
  assert client.get(url).status_code==200
  con=a.estimate_db();assert con.execute('SELECT COUNT(*) AS total FROM support_requests').fetchone()['total']==1;con.close()
  assert client.post(url,data={'csrf':token,'reference':'wrong'}).status_code==400
  allowed[0]=False
  for route in [url,'/head-office/support/'+tid+'/manage']:
   assert client.post(route,data={'csrf':token,'reference':ref,'action':'update','status':'resolved'}).status_code==403
  allowed[0]=True
  assert client.post(url,data={'csrf':token,'reference':ref}).status_code==302
  con=a.estimate_db()
  assert con.execute('SELECT COUNT(*) AS total FROM support_requests').fetchone()['total']==0
  assert con.execute('SELECT COUNT(*) AS total FROM support_notes').fetchone()['total']==0;con.close()
  assert notify.call_count==1,'Private notes/status must never trigger customer email'
 # Migrate an existing schema and preserve its ticket.
 raw=sqlite3.connect(':memory:');raw.row_factory=sqlite3.Row;con=a.DBCompat(raw)
 original='CREATE TABLE support_requests (id TEXT PRIMARY KEY, reference TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, name TEXT NOT NULL, company TEXT NOT NULL, email TEXT NOT NULL, topic TEXT NOT NULL, message TEXT NOT NULL, device TEXT NOT NULL, page_url TEXT NOT NULL, dealer_id TEXT, fingerprint TEXT NOT NULL, notification_status TEXT NOT NULL)'
 con.execute(original);con.execute("INSERT INTO support_requests VALUES ('old','AQ-OLD','today','Test','','test@example.com','billing','Original message','Tablet','','','hash','accepted')")
 s.init_support_db(con);s.init_support_db(con)
 old=con.execute("SELECT * FROM support_requests WHERE id='old'").fetchone()
 assert old['status']=='open' and old['archived']==0 and old['message']=='Original message'
 con.close()
 print('PASS legacy migration, statuses, escaped private notes, archive/restore, admin/CSRF validation and confirmed deletion with notes; no customer emails')
