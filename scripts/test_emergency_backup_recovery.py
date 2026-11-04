"""Non-destructive recovery drill: disposable SQLite or localhost CI PostgreSQL only.
Never restores over the source. No live database, Render restore or production rollback.
"""
import os,sys,tempfile,subprocess,json,uuid,sqlite3,hashlib
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
pg='--postgres' in sys.argv
with tempfile.TemporaryDirectory() as td:
 os.environ.update(FLASK_SECRET_KEY='fictional-backup-drill-only',ESTIMATE_DB_PATH=td+'/source.db')
 os.environ.pop('RENDER_SERVICE_ID',None);os.environ.pop('RENDER_EXTERNAL_HOSTNAME',None)
 if pg:
  url=os.environ.get('QA_POSTGRES_URL','');parts=urlsplit(url)
  assert parts.hostname in ('localhost','127.0.0.1') and parts.path=='/aeriquote_qa' and parts.username=='qa'
  container=os.environ.get('QA_POSTGRES_CONTAINER','');assert container and container.replace('-','').isalnum()
  os.environ['DATABASE_URL']=url
 else:os.environ['DATABASE_URL']=''
 import app as a
 from qa_estimate_fixture import price_fixture
 from measurement_integrity import polygon_sqft
 con=a.estimate_db();did='qa-recovery-'+uuid.uuid4().hex
 con.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,status,created_at,lookup_limit,estimate_limit) VALUES(?,?,?,'unused','active','2026-10-30',200,200)",(did,'Fictional Recovery QA',did+'@example.invalid'))
 con.execute('INSERT INTO account_allowances(dealer_id,complimentary) VALUES(?,1)',(did,));con.commit();con.close()
 c=a.app.test_client()
 with c.session_transaction() as s:s.update(dealer_id=did,auth_version=0,account_type='owner')
 points=[[52,-106],[52,-105.9999],[52.0001,-105.9999],[52.0001,-106]]
 def save(label):
  p=price_fixture({'address':'FICTIONAL QA '+label,'customer_name':'Fictional Customer','quote':{'commercialAreas':[{'points':points,'sqft':round(polygon_sqft(points)),'rate':1}]}})
  r=c.post('/api/estimates',json=p);assert r.status_code==200,r.status_code
  return r.json['id']
 # Extra source history must restore at the same point in time as its bank.
 import extra_allowance_ledger as ledger
 from account_credits import lock_account
 con=a.estimate_db();lock_account(con,did);ledger.grant_administrative(con,did,7,'backup-before');con.commit();con.close()
 first=save('before backup')
 backup=Path(td)/('backup.dump' if pg else 'backup.db')
 if pg:
  with backup.open('wb') as f:subprocess.run(['docker','exec',container,'pg_dump','-U','qa','-d','aeriquote_qa','-Fc','--no-owner'],stdout=f,check=True)
 else:
  with sqlite3.connect(td+'/source.db') as source,sqlite3.connect(backup) as dest:source.backup(dest)
 con=a.estimate_db();lock_account(con,did);ledger.grant_administrative(con,did,2,'backup-after');con.commit();con.close()
 second=save('after backup')
 before=c.get('/api/estimates/'+first).json;newer=c.get('/api/estimates/'+second).json
 # Import the previous recovery revision in a separate process against THIS disposable DB.
 old=Path(td)/'previous';old.mkdir()
 paths=subprocess.check_output(['git','ls-tree','--name-only','HEAD^'],cwd=ROOT,text=True).splitlines()
 for path in paths:
  if path.endswith('.py'):(old/path).write_bytes(subprocess.check_output(['git','show','HEAD^:'+path],cwd=ROOT))
 probe="""import app,json,sys
c=app.app.test_client()
with c.session_transaction() as s:s.update(dealer_id=sys.argv[1],auth_version=0,account_type='owner')
for i in sys.argv[2:]:
 r=c.get('/api/estimates/'+i);assert r.status_code==200;print(json.dumps(r.json,sort_keys=True))
"""
 env=dict(os.environ,PYTHONPATH=str(old));out=subprocess.check_output([sys.executable,'-c',probe,did,first,second],cwd=old,env=env,text=True)
 assert [json.loads(line) for line in out.splitlines() if line.startswith('{')]==[before,newer]
 assert c.get('/api/estimates/'+second).json==newer
 if pg:
  import psycopg
  from psycopg import sql
  target='aeriquote_qa_restore_'+uuid.uuid4().hex
  with psycopg.connect(url,autocommit=True) as admin:
   assert not admin.execute('SELECT 1 FROM pg_database WHERE datname=%s',(target,)).fetchone()
   admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(target)))
  with backup.open('rb') as f:subprocess.run(['docker','exec','-i',container,'pg_restore','-U','qa','-d',target,'--no-owner','--exit-on-error'],stdin=f,check=True)
  restored_url=urlunsplit(parts._replace(path='/'+target))
  with psycopg.connect(restored_url) as dest:
   rows=dest.execute('SELECT id,payload FROM estimates WHERE dealer_id=%s',(did,)).fetchall();ids={row[0] for row in rows};payloads={row[0]:json.loads(row[1]) for row in rows}
   restored_ledger=dict(dest.execute('SELECT channel,SUM(delta) FROM extra_movements WHERE dealer_id=%s GROUP BY channel',(did,)).fetchall());restored_bank=dest.execute('SELECT lookup_bonus,estimate_bonus FROM account_allowances WHERE dealer_id=%s',(did,)).fetchone()
 else:
  target=Path(td)/'new-empty-restored.db';assert not target.exists()
  with sqlite3.connect(backup) as source,sqlite3.connect(target) as dest:source.backup(dest)
  with sqlite3.connect(target) as dest:
   rows=dest.execute('SELECT id,payload FROM estimates WHERE dealer_id=?',(did,)).fetchall();ids={row[0] for row in rows};payloads={row[0]:json.loads(row[1]) for row in rows}
   restored_ledger=dict(dest.execute('SELECT channel,SUM(delta) FROM extra_movements WHERE dealer_id=? GROUP BY channel',(did,)).fetchall());restored_bank=dest.execute('SELECT lookup_bonus,estimate_bonus FROM account_allowances WHERE dealer_id=?',(did,)).fetchone()
 assert restored_ledger=={'lookups':7,'estimates':7} and tuple(restored_bank)==(7,7),'Restored extra history and bank must agree at backup time'
 con=a.estimate_db();source_ledger=ledger.reconciliation(con,did);con.close()
 assert source_ledger['balanced'] and source_ledger['bank']=={'lookups':9,'estimates':9},'Source extra history must retain post-backup grant'
 assert payloads[first]==before['payload'],'Restored geometry, customer fields and pricing must match'
 assert first in ids and second not in ids,'Restore reflects backup time, not later writes'
 assert c.get('/api/estimates/'+first).json==before and c.get('/api/estimates/'+second).json==newer,'Source preserved'
 print(json.dumps(dict(result='PASS',backend='PostgreSQL' if pg else 'SQLite',prior_recovery_revision_reads_newer_estimates=True,restore_target_new_and_empty=True,source_newer_estimates_preserved=True,backup_does_not_contain_post_backup_writes=True,extra_ledger_and_bank_restore_together=True,live_pitr_or_render_rollback_tested=False)))
