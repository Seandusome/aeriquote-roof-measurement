"""Actual isolated save routes: priced roof scope, flag stripping and mixed sources."""
import copy,json,math,os,sys,tempfile,uuid
from pathlib import Path
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
pg='--postgres' in sys.argv
scratch=tempfile.TemporaryDirectory()
if pg:
 url=os.environ.get('QA_POSTGRES_URL','');u=urlsplit(url)
 assert u.hostname in ('localhost','127.0.0.1') and u.path=='/aeriquote_qa' and u.username=='qa'
 os.environ['DATABASE_URL']=url
else:os.environ['DATABASE_URL']=''
os.environ.update(ESTIMATE_DB_PATH=scratch.name+'/scope.db',FLASK_SECRET_KEY='fictional-roof-scope-only')
import app as a
from measurement_integrity import polygon_sqft
from qa_estimate_fixture import automatic_roof,price_fixture
points=[[52,-106],[52,-105.9999],[52.0001,-105.9999],[52.0001,-106]]
def moved(dx,dy=0):return [[lat+dy,lon+dx] for lat,lon in points]
def plane(pts):return dict(points=pts,pitch_degrees=30,surface_sqft=polygon_sqft(pts)/math.cos(math.pi/6))
owner='qa-scope-'+uuid.uuid4().hex
con=a.estimate_db();con.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,status,created_at) VALUES(?,?,?,'unused','active','2026-10-31')",(owner,'FICTIONAL QA',owner+'@example.invalid'));con.execute('INSERT INTO account_allowances(dealer_id,complimentary) VALUES(?,1)',(owner,));con.commit();con.close()
c=a.app.test_client()
with c.session_transaction() as s:s.update(dealer_id=owner,account_type='owner',auth_version=0)
def payload(source,second):
 q=dict(businessType='roofing',measurementMode='auto',measureSource=source,structures=[],manualPlanes=[])
 if source=='manual':q['manualPlanes']=[plane(points),plane(second)]
 elif source=='hybrid':q.update(structures=[automatic_roof(points,30,'main')],manualPlanes=[plane(second)])
 else:q['structures']=[automatic_roof(points,30,'main'),dict(automatic_roof(second,30,'manual'),manually_measured=True,pitch_confirmed=True)]
 return price_fixture(dict(address='FICTIONAL QA scope '+source,quote=q,pricing=dict(price=1,gst=5,pst=6)))
rejected=0;valid=0
for source in ('manual','hybrid','google'):
 original=payload(source,moved(.001));r=c.post('/api/estimates',json=original);assert r.status_code==200,r.json
 eid=r.json['id'];before=c.get('/api/estimates/'+eid).json
 con=a.estimate_db();versions=con.execute('SELECT COUNT(*) AS n FROM estimate_revisions WHERE estimate_id=?',(eid,)).fetchone()['n'];usage=[dict(r) for r in con.execute('SELECT * FROM account_month_usage WHERE dealer_id=?',(owner,)).fetchall()];con.close()
 for second in (points,list(reversed(points)),[points[0]]+points+[points[0]],moved(.00005)):
  bad=payload(source,second)
  # Neither browser-only QA flag nor provider identity can be trusted as a bypass.
  bad['quote'].update(manualRoofWorkflow=False,roofScopeConfirmed=False)
  r=c.post('/api/estimates',json=bad,headers={'Idempotency-Key':uuid.uuid4().hex});assert r.status_code==400 and 'overlap' in r.json['error'],r.json;rejected+=1
  assert c.get('/api/estimates/'+eid).json==before
 con=a.estimate_db();assert con.execute('SELECT COUNT(*) AS n FROM estimate_revisions WHERE estimate_id=?',(eid,)).fetchone()['n']==versions
 assert [dict(r) for r in con.execute('SELECT * FROM account_month_usage WHERE dealer_id=?',(owner,)).fetchall()]==usage;con.close()
 # Adjoining planes, detached garages and sub-metre gaps are legitimate.
 for second in (moved(.0001),moved(.001),moved(.00010001)):
  assert c.post('/api/estimates',json=payload(source,second)).status_code==200;valid+=1
# Cached geometry excluded by the selected pricing source cannot trigger a false overlap.
for source in ('manual','google'):
 p=payload(source,moved(.001));p['quote']['structures' if source=='manual' else 'manualPlanes']=[automatic_roof(points,30,'ignored')] if source=='manual' else [plane(points)]
 price_fixture(p);assert c.post('/api/estimates',json=p).status_code==200;valid+=1
print(json.dumps(dict(result='PASS',backend='PostgreSQL' if pg else 'SQLite',overlap_attacks_rejected=rejected,valid_scope_cases=valid,original_geometry_pricing_revisions_usage_preserved=True)))
