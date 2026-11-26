import json,os,sqlite3,sys,tempfile,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
folder=Path(tempfile.mkdtemp(prefix='aq-expired-save-fictional-'))
os.environ.update(DATABASE_URL='',ESTIMATE_DB_PATH=str(folder/'qa.sqlite'),GOOGLE_API_KEY='',GOOGLE_MAPS_API_KEY='',RESEND_API_KEY='')
import app as a,workspace_drafts as d
assert a.DATABASE_URL=='' and Path(a.ESTIMATE_DB)==folder/'qa.sqlite'
c=a.estimate_db()
for who in ['fictional-A','fictional-B']:
 c.execute('INSERT INTO dealers(id,dealer_name,email,password_hash,status,created_at) VALUES(?,?,?,?,?,?)',(who,'FICTIONAL',who+'@example.invalid','unused','active','2026-11-25'))
c.commit();c.close()
def client(who):
 x=a.app.test_client()
 with x.session_transaction() as s:s.update(dealer_id=who,account_type='owner',auth_version=0)
 return x
o=client('fictional-A');other=client('fictional-B')
h={'X-AeriQuote-Account':'fictional-A','X-AeriQuote-Principal':'owner:fictional-A'}
w={'schema':1,'values':{'customerName':'FICTIONAL','jobPrice':'2'},'quote':{'pitch':26.565,'points':[[1,2],[1,3],[2,3]]},'pending':{'id':'same-pending-id'}}
old='fictional-expired-0001';fresh='fictional-fresh-0001';path='/api/workspace-drafts/'
c=a.estimate_db();d.put(c,'fictional-A','owner:fictional-A',old,0,w,now=time.time()-d.TTL-10);c.commit();c.close()
r=o.put(path+old,headers=h,json={'version':1,'workspace':w});assert r.status_code==409 and r.json['code']=='draft_closed'
def snapshot():
 c=sqlite3.connect(folder/'qa.sqlite');r=c.execute('SELECT * FROM workspace_drafts ORDER BY 1,2,3').fetchall();c.close();return r
before=snapshot()
for browser,headers,expected in [(other,h,409),(o,{**h,'X-AeriQuote-Principal':'employee:fictional'},409),(o,{**h,'Origin':'https://foreign.invalid'},403),(a.app.test_client(),h,401)]:
 r=browser.put(path+old,headers=headers,json={'version':1,'workspace':w});assert r.status_code==expected,(r.status_code,r.json);assert snapshot()==before
assert o.put(path+fresh,headers=h,json={'version':0,'workspace':w}).status_code==200
newer={**w,'values':{'customerName':'FICTIONAL NEWER'}}
assert o.put(path+fresh,headers=h,json={'version':1,'workspace':newer}).status_code==200
before=snapshot();r=o.put(path+fresh,headers=h,json={'version':1,'workspace':w});assert r.status_code==409 and r.json['code'] is None and snapshot()==before
assert o.get(path+fresh,headers=h).json['workspace']==newer
c=a.estimate_db();c.execute("UPDATE dealers SET status='disabled' WHERE id='fictional-A'");c.commit();c.close()
r=o.put(path+fresh,headers=h,json={'version':2,'workspace':w});assert r.status_code==401 and snapshot()==before
print(json.dumps({'status':'PASS','checks':['expired PUT fresh-ID code','new payload and pending ID exact','business switch denied','principal mismatch denied','foreign origin denied','signed out denied','newer version not reclassified','disabled account denied'],'fixture_database_preserved':str(folder/'qa.sqlite')}))
