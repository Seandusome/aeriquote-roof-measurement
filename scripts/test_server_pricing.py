"""Actual browser calculator -> independent server Decimal calculation -> isolated real routes."""
import ast,copy,json,math,os,subprocess,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from measurement_integrity import polygon_sqft,line_feet
from pricing_integrity import calculate
points=[[52,-106],[52,-105.9999],[52.0001,-105.9999],[52.0001,-106]]
second=[[lat+.001,lon] for lat,lon in points];quantity=round(polygon_sqft(points));feet=line_feet(points[:2]);fixtures=[]
for industry in ['roofing','snow','pressure','paving','landscaping','commercial']:
 periods=['one_time','month','season','visit','snowfall','year'] if industry in ['snow','landscaping','commercial'] else ['one_time']
 for mode in ['regular','included','discount']:
  for period in periods:
   quote={'businessType':industry,'measurementMode':'linear','linearPoints':points[:2],'linearFeet':feet,'commercialAreas':[],'areaPoints':points,'areaSqFt':polygon_sqft(points),'structures':[],'manualPlanes':[],'landscapingLinearRate':.705,'pressureLinearRate':.705,'pavingLinearRate':.705,'commercialLinearRate':.705}
   if industry!='roofing':quote['commercialAreas']=[{'points':points,'sqft':quantity,'rate':.005},{'points':second,'sqft':round(polygon_sqft(second)),'rate':.015}];quote['areaSqFt']=sum(a['sqft'] for a in quote['commercialAreas'])
   else:quote['areaSqFt']=0;quote['areaPoints']=[]
   fixtures.append({'address':'QA PRICE '+str(len(fixtures)),'quote':quote,'pricing':{'price':.705,'mode':mode,'gst':5,'pst':6,'disc':12.5,'extraAmount':17.29,'extraDescription':'QA additional service','estimatePeriod':period}})
# Roof auto/manual pitch, single-area/linear, zero-priced intentional service.
for mode in ['auto','area','linear']:
 q={'businessType':'roofing','measurementMode':mode,'measureSource':'manual','areaPoints':points,'areaSqFt':polygon_sqft(points),'linearPoints':points[:2],'linearFeet':feet,'manualPlanes':[{'points':points,'pitch_degrees':30,'surface_sqft':polygon_sqft(points)/math.cos(math.pi/6)}],'structures':[],'commercialAreas':[]}
 fixtures.append({'address':'QA ROOF '+mode,'quote':q,'pricing':{'price':.95,'mode':'discount','gst':7.25,'pst':0,'disc':5,'extraAmount':0,'estimatePeriod':'one_time'}})
for industry in ['landscaping','pressure','paving']:
 q={'businessType':industry,'measurementMode':'linear','areaPoints':points,'areaSqFt':polygon_sqft(points),'linearPoints':points[:2],'linearFeet':feet,'commercialAreas':[],industry+'Combined':True,industry+'AreaRate':.125}
 fixtures.append({'address':'QA LEGACY '+industry,'quote':q,'pricing':{'price':.705,'mode':'included','gst':5,'pst':6,'disc':0,'extraAmount':5,'estimatePeriod':'one_time'}})
zero=copy.deepcopy(fixtures[0]);zero['address']='QA FREE';zero['pricing'].update(price=0,extraAmount=0,gst=0,pst=0);fixtures.append(zero)
fixtures=json.loads(subprocess.check_output(['node','scripts/price_fixtures.cjs'],input=json.dumps(fixtures).encode()))
for p in fixtures:
 result=calculate(p)
 for key in ['subtotal','discount','taxBase','gstAmt','pstAmt','total']:assert float(result[key])==p['pricing'][key],(p['address'],key,result,p['pricing'])
with tempfile.TemporaryDirectory() as tmp:
 os.environ['DATABASE_URL']='';os.environ['ESTIMATE_DB_PATH']=str(Path(tmp)/'pricing.db')
 import app as a
 con=a.estimate_db();con.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,state,status,estimate_limit,created_at) VALUES('qa','QA PRICE','qa-price@example.invalid','unused','SK','active',10000,'2026-10-21')");con.commit();con.close()
 c=a.app.test_client()
 with c.session_transaction() as session:session.update(dealer_id='qa',account_type='owner',auth_version=0)
 for p in fixtures:
  response=c.post('/api/estimates',json=p);assert response.status_code==200,(p,response.get_json())
 sample=fixtures[3];eid=c.post('/api/estimates',json=sample).get_json()['id'];before=c.get('/api/estimates/'+eid).get_json()
 con=a.estimate_db();revisions=con.execute('SELECT COUNT(*) AS n FROM estimate_revisions').fetchone()['n'];con.close()
 for mutation in [
  lambda p:(p.update(total_price=1),p['pricing'].update(subtotal=1,taxBase=1,gstAmt=0,pstAmt=0,total=1)),
  lambda p:p['pricing'].update(discount=999),lambda p:p['pricing'].update(gstAmt=0),lambda p:p['pricing'].update(pstAmt=0),
  lambda p:p['pricing'].update(subtotal=p['pricing']['subtotal']*12),lambda p:p['pricing'].update(extraAmount=0),
  lambda p:p.update(extra_service_amount=0),lambda p:p['pricing'].update(estimatePeriod='bad'),
  lambda p:p['pricing'].pop('price'),lambda p:p['pricing'].pop('subtotal'),lambda p:p.update(pricing={}),
 ]:
  bad=copy.deepcopy(sample);mutation(bad);r=c.post('/api/estimates',json=bad);assert r.status_code==400,r.get_json()
 assert c.get('/api/estimates/'+eid).get_json()==before
 con=a.estimate_db();assert con.execute('SELECT COUNT(*) AS n FROM estimate_revisions').fetchone()['n']==revisions;con.close()
 # Prior checkpoint validator really accepted a self-consistent forged one-dollar total.
 previous=Path(os.environ['PRIOR_PRICING_SOURCE']).read_text() if os.environ.get('PRIOR_PRICING_SOURCE') else None
 if previous:
  tree=ast.parse(previous);fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='estimate_pricing_error');fn.decorator_list=[]
  from measurement_integrity import snapshot_error
  ns={'math':math,'snapshot_error':snapshot_error};exec(compile(ast.Module(body=[fn],type_ignores=[]),'prior.py','exec'),ns)
  bad=copy.deepcopy(sample);bad['total_price']=1;bad['pricing'].update(subtotal=1,taxBase=1,gstAmt=0,pstAmt=0,total=1);assert ns['estimate_pricing_error'](bad)==''
print(f'PASS: {len(fixtures)} actual-client fixtures across six industries/tax modes/periods, rounded lines, decimals, manual pitch, zero price; independent real API rejects forged consistent totals and preserves history')
