"""Normal disposable trial cap: revisions/retries never spend another allowance."""
import copy,json
import fresh_user_browser_server as fixture
from qa_estimate_fixture import price_fixture
from measurement_integrity import polygon_sqft
from unittest.mock import patch

a=fixture.a;c=a.app.test_client();base='http://127.0.0.1:8765'
def req(method,path,**kw):return getattr(c,method)(path,base_url=base,**kw)
def state():return req('get','/__qa_fresh/state').get_json()
def save(payload,operation,version=None):
 headers={'Idempotency-Key':operation}
 if version:headers['If-Match']=version
 return req('post','/api/estimates',headers=headers,json=payload)
assert req('post','/api/public/signup',json={'name':'FICTIONAL OWNER','company':'FICTIONAL TRIAL','email':'trial-edit@example.invalid','password':'fictional-qa-password','country':'Canada','industry':'landscaping'}).status_code==200
assert state()['plan']['plan_code']=='trial' and not state()['complimentary']
ring=[[52,-106],[52,-105.9999],[52.0001,-105.9999],[52.0001,-106]]
payloads=[];saved=[]
for n in range(3):
 address=f'{n+1} Fictional Trial Street, Saskatoon, SK, Canada';operation=f'trial-lookup-{n}'
 if n==0:
  with patch.object(a,'perform_property_lookup',lambda d:(a.jsonify(error='Fictional provider unavailable'),503)):
   assert req('post','/property',headers={'Idempotency-Key':'trial-provider-failure'},json={'key':'qa-placeholder','address':address,'business_type':'landscaping','prepare_only':True}).status_code==503
  assert state()['lookups']==0
 prepared=req('post','/property',headers={'Idempotency-Key':operation},json={'key':'qa-placeholder','address':address,'business_type':'landscaping','prepare_only':True});assert prepared.status_code==200
 for _ in range(2):assert req('post','/property/accept',json={'operation_id':operation,'token':prepared.get_json()['token']}).status_code==200
 assert state()['lookups']==n+1
 p={'address':address,'customer_name':f'FICTIONAL ORIGINAL {n}','extra_service_amount':0,'quote':{'businessType':'landscaping','measurementMode':'area','commercialAreas':[{'name':'Fictional Yard','points':ring,'sqft':round(polygon_sqft(ring)),'rate':.23}]},'pricing':{'price':.23,'mode':'regular','gst':5,'pst':6}}
 price_fixture(p);r=save(p,f'trial-save-{n}');assert r.status_code==200,r.data;saved.append(r.get_json());payloads.append(p)
assert state()['counts']['estimates']==3 and state()['counts']['estimate_revisions']==0
assert req('post','/property',headers={'Idempotency-Key':'trial-over'},json={'key':'qa-placeholder','address':'4 Fictional Trial Street','business_type':'landscaping','prepare_only':True}).status_code==403
new=copy.deepcopy(payloads[0]);new['address']='4 Fictional Trial Street';assert save(new,'trial-new-over').status_code==403
changed=copy.deepcopy(payloads[0]);changed['customer_name']='FICTIONAL UPDATED';changed['quote']['commercialAreas'][0]['rate']=.37;changed['extra_service_amount']=12.95;price_fixture(changed)
r=save(changed,'trial-edit-retry',saved[0]['version']);assert r.status_code==200,r.data
assert save(changed,'trial-edit-retry',saved[0]['version']).get_json()==r.get_json()
versions=req('get','/api/estimates/'+saved[0]['id']+'/versions').get_json();assert len(versions['revisions'])==1 and versions['revisions'][0]['payload']==payloads[0]
stale=copy.deepcopy(changed);stale['customer_name']='FICTIONAL STALE';assert save(stale,'trial-stale',saved[0]['version']).status_code==409
# Invalid geometry must be rejected even when editing an existing quote at cap.
invalid=copy.deepcopy(changed);invalid['quote']['commercialAreas'][0]['points']=ring[:2];assert save(invalid,'trial-invalid',r.get_json()['version']).status_code==400
end=state();assert end['lookups']==3 and end['counts']['estimates']==3 and end['counts']['estimate_revisions']==1 and end['counts']['estimate_save_receipts']==4
assert req('get','/api/estimates/'+saved[0]['id']+'/versions').get_json()==versions
print('PASS normal trial: provider503 no debit; three lookups/estimates exhaust caps; repeated acceptance and save idempotent; existing edit at cap once; stale409 and invalid geometry400 preserve history/allowances')
print(json.dumps(end,sort_keys=True))
