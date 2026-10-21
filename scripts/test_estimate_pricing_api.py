"""Reject invalid money before history revisions or allowance consumption; isolated real Flask routes."""
import os,sys,tempfile,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory() as tmp:
 os.environ['DATABASE_URL']='';os.environ['ESTIMATE_DB_PATH']=str(Path(tmp)/'pricing.db')
 import app as a
 con=a.estimate_db();con.execute('INSERT INTO dealers(id,dealer_name,email,password_hash,state,status,created_at) VALUES(?,?,?,?,?,?,?)',('qa-owner','QA TEST Pricing','qa@example.invalid','unused','SK','active','2026-10-20'));con.commit();con.close()
 client=a.app.test_client()
 with client.session_transaction() as session:session['dealer_id']='qa-owner';session['auth_version']=0
 original={'address':'QA TEST Property','customer_name':'QA TEST DO NOT SEND','total_area':100,'total_price':111,'pricing':{'subtotal':100,'taxBase':100,'gst':5,'pst':6,'gstAmt':5,'pstAmt':6,'total':111}}
 eid=client.post('/api/estimates',json=original).get_json()['id']
 before=client.get('/api/estimates/'+eid).get_json()
 for key in ('total_price','total_area','extra_service_amount'):
  for value in (-1,None,'',float('inf'),float('nan'),'oops'):
   payload=copy.deepcopy(original);payload[key]=value;assert client.post('/api/estimates',json=payload).status_code==400,(key,value)
 for key,value in [('gst',-1),('pst',101),('total',-1),('subtotal',float('inf'))]:
  payload=copy.deepcopy(original);payload['pricing'][key]=value;assert client.post('/api/estimates',json=payload).status_code==400
 payload=copy.deepcopy(original);payload['pricing'].update(mode='discount',disc=101);assert client.post('/api/estimates',json=payload).status_code==400
 # Contradictory totals and malformed measurement quantities must not overwrite history.
 for mutation in [
  lambda p:p.update(total_price=1),
  lambda p:p['pricing'].update(gstAmt=6),
  lambda p:p['pricing'].update(taxBase=90),
  lambda p:p.update(linear_feet=-1),
  lambda p:p.update(area_sqft=float('nan')),
  lambda p:p.update(quote={'commercialAreas':[{'sqft':100,'rate':-1}]}),
  lambda p:p.update(quote={'commercialAreas':[{'sqft':-100,'rate':1}]}),
  lambda p:p.update(quote={'structures':[{'needs_remeasure':True}]}),
  lambda p:p.update(quote='broken snapshot'),
  lambda p:p.update(pricing=False),
 ]:
  payload=copy.deepcopy(original);mutation(payload);assert client.post('/api/estimates',json=payload).status_code==400,payload
 assert client.get('/api/estimates/'+eid).get_json()==before
 con=a.estimate_db();assert con.execute('SELECT COUNT(*) AS n FROM estimate_revisions').fetchone()['n']==0;con.close()
 payload=copy.deepcopy(original);payload.update(address='QA TEST Free Service',total_price=0);payload['pricing'].update(subtotal=0,taxBase=0,gstAmt=0,pstAmt=0,total=0);assert client.post('/api/estimates',json=payload).status_code==200
print('PASS: invalid amounts/taxes/discounts rejected without changing saved estimate/history; explicit free quote allowed')
