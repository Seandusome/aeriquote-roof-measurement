"""Independent check of this mixed-history Paving QA snapshot; no app imports/DB."""
import hashlib,json,sys
from decimal import Decimal,ROUND_HALF_UP
from pathlib import Path
from geographiclib.geodesic import Geodesic
p=json.loads(Path(sys.argv[1]).read_text());q=p['quote'];pr=p['pricing']
assert q['businessType']=='paving' and q['measurementMode']=='area'
assert len(q['commercialAreas'])==2 and len(q['linearPoints'])>=2
D=lambda v:Decimal(str(v))
cent=lambda v:D(v).quantize(D('.01'),rounding=ROUND_HALF_UP)
pair=lambda p:(p['lat'],p['lng']) if isinstance(p,dict) else p
charges=[]
for index,a in enumerate(q['commercialAreas'],1):
 polygon=Geodesic.WGS84.Polygon()
 for pt in a['points']:polygon.AddPoint(*pair(pt))
 reference=abs(polygon.Compute()[2])/(.3048**2)
 assert abs(a['sqft']-reference)<=max(1,reference*.006),(index,reference,a['sqft'])
 charges.append(cent(D(a['sqft'])*D(a['rate'])))
 print('PASS WGS84 active Area',index,'stored',a['sqft'],'independent',round(reference,3),'rate',a['rate'])
feet=sum(Geodesic.WGS84.Inverse(*pair(a),*pair(b))['s12']/.3048 for a,b in zip(q['linearPoints'],q['linearPoints'][1:]))
assert abs(q['linearFeet']-feet)<=max(.05,feet*.006)
charges.append(cent(D(q['linearFeet'])*D(q['pavingLinearRate'])))
assert [a['sqft'] for a in q['commercialAreas']]==[6125,1733]
assert [a['rate'] for a in q['commercialAreas']]==[.1,.23]
assert sum(charges)==D(pr['subtotal'])==D('1029.92')
base=cent(sum(charges)+D(pr['extraAmount']));gst=cent(base*D(pr['gst'])/100);pst=cent(base*D(pr['pst'])/100)
assert (base,gst,pst,base+gst+pst)==tuple(D(pr[k]) for k in ('taxBase','gstAmt','pstAmt','total'))
assert D(p['total_price'])==base+gst+pst==D('1200.65')
hash_value=hashlib.sha256(json.dumps(q,sort_keys=True,separators=(',',':')).encode()).hexdigest()
assert hash_value=='a9abf3d553ed77bd6c0ef1b8d90c7f7b6e09332b5b67c21b7dbb1716b3999466'
print('PASS original acknowledged draft = restored quote = saved quote (canonical SHA256)')
print('PASS WGS84 active linear',round(feet,5),'stored',q['linearFeet'])
print('PASS Decimal subtotal',sum(charges),'extra',pr['extraAmount'],'tax base',base,'GST',gst,'PST',pst,'total',base+gst+pst)
print('Scope: retained Roofing history is inactive for Paving; it is neither charged nor drawn in either inspected PDF.')
print('Tolerance 0.6% checks existing spherical quantities against WGS84; not survey accuracy.')
