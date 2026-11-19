"""Independent PostgreSQL auditor. No app/adapter/evaluator/normalizer imports."""
import hashlib
import json
from pathlib import Path
import sys
import psycopg2

k=json.loads(Path(sys.argv[1]).read_text());output=Path(sys.argv[2]);rows={}
def hashed(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
assert k['host']=='127.0.0.1' and k['dbname']=='aq_durable_fiction'
with psycopg2.connect(**{x:k[x] for x in ('host','port','dbname','user')}) as c,c.cursor() as q:
 c.set_session(readonly=True)
 q.execute("SELECT current_database(),current_setting('data_directory'),host(inet_server_addr()),inet_server_port(),current_setting('server_version')")
 target=q.fetchone();assert target[:4]==(k['dbname'],k['data_directory'],'127.0.0.1',k['port'])
 for table in ('qa_business','qa_inbox','qa_deliveries','qa_facts','qa_normalized','qa_applied','qa_task','qa_history'):
  q.execute('SELECT * FROM '+table);names=[d[0] for d in q.description]
  rows[table]=[dict(zip(names,row)) for row in q.fetchall()]
 # SQL invariants independent of stored projection calculations.
 q.execute('SELECT business,operation,count(*) FROM qa_applied GROUP BY business,operation HAVING count(*)<>1');assert not q.fetchall()
 q.execute('SELECT t.business,t.event_id FROM qa_task t LEFT JOIN qa_applied a USING(business,event_id) WHERE t.status IN (\'applied\',\'observed_no_grant\') AND a.operation IS NULL');assert not q.fetchall()
 q.execute('SELECT a.business,a.operation FROM qa_applied a JOIN qa_normalized n USING(business,event_id) WHERE a.operation<>n.operation OR a.semantic_hash<>n.semantic_hash');assert not q.fetchall()
limits={'basic':25,'pro':75,'business':200};business_report=[]
for b in rows['qa_business']:
 biz=b['business'];s=b['state'];assert s['business_id']==biz and biz.startswith('qa-fictional-')
 assert s['saved_work']=={'sentinel':'UNCHANGED'}
 hist=sorted([x for x in rows['qa_history'] if x['business']==biz],key=lambda x:x['seq'])
 prev='GENESIS';state=None
 for h in hist:
  if state is not None:assert state==h['before_state']
  assert h['previous_hash']==prev
  facts={key:h[key] for key in ('business','event_id','phase','status','issue','before_state','after_state','previous_hash')}
  assert hashed(facts)==h['entry_hash'];prev=h['entry_hash'];state=h['after_state']
  if not(h['phase']=='apply' and h['status']=='applied'):assert h['before_state']==h['after_state']
 assert state==s
 first=hist[0]['before_state'];assert first['saved_work']==s['saved_work']
 assert len(s['invoices'])==len(set(s['invoices']))
 for p in [s['snapshot']] if s['snapshot'] else []:
  assert p['extras']=={'lookups':7,'estimates':11}
  if first['snapshot']:assert p['used']==first['snapshot']['used'] and p['period']==first['snapshot']['period']
  cap=limits[p['period']['plan']]+sum(limits[x['to_plan']]-limits[x['from_plan']] for x in p['upgrades'])
  remaining={x:cap-p['used'][x] for x in ('lookups','estimates')};assert min(remaining.values())>=0
  if p['upgrades']:
   assert len(p['upgrades'])==1 and p['upgrades'][0]['from_plan']=='basic' and p['upgrades'][0]['to_plan']=='pro'
   assert remaining=={'lookups':52,'estimates':52}
  business_report.append({'business':biz,'remaining_monthly':remaining,'extras':p['extras'],'history_rows':len(hist)})
for r in rows['qa_inbox']+rows['qa_deliveries']:
 assert hashlib.sha256(bytes(r['raw_body'])).hexdigest()==r['raw_hash']
for r in rows['qa_facts']:assert hashed(r['facts'])==r['facts_hash']
for r in rows['qa_normalized']:
 assert r['event']['business_id']==r['business']
 assert hashed({x:v for x,v in r['event'].items() if x!='id'})==r['semantic_hash']
# Export exact rows privately as fictional evidence, keeping original byte bodies.
def serial(v):
 if isinstance(v,memoryview):return {'hex':bytes(v).hex()}
 if hasattr(v,'isoformat'):return v.isoformat()
 raise TypeError(type(v).__name__)
output.mkdir(parents=True,exist_ok=True)
(output/'independent-sql-rows.json').write_text(json.dumps(rows,default=serial,indent=2))
summary={'passed':True,'fictional_only':True,'target':list(target),'row_counts':{t:len(v) for t,v in rows.items()},'businesses':business_report,
         'assertions':['SQL unique operations','applied status backed by committed operation','normalized operation hashes match',
                       'history continuity and hash chain','no-change denials/observations/duplicates','raw bytes immutable hashes',
                       'preserved original usage, extras, paid period, work','52 remaining for every Basic23->Pro case']}
(output/'independent-audit.json').write_text(json.dumps(summary,indent=2));print(json.dumps({'passed':True,'row_counts':summary['row_counts']}))
