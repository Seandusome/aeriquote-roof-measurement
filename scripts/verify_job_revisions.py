"""Independent active-scope WGS84/Decimal check for fictional revision snapshots.

Does not import the app or its pricing/projection helpers. Dormant roof history
in a surface quote is deliberately excluded from active quantities/charges.
"""
import json,math,sys
from pathlib import Path
from decimal import Decimal,ROUND_HALF_UP
from geographiclib.geodesic import Geodesic
D=lambda v:Decimal(str(v))
cent=lambda v:D(v).quantize(D('.01'),rounding=ROUND_HALF_UP)
def pair(p):return (p['lat'],p['lng']) if isinstance(p,dict) else p
def area(points):
 polygon=Geodesic.WGS84.Polygon()
 for p in points:polygon.AddPoint(*pair(p))
 return abs(polygon.Compute()[2])/(.3048**2)
def length(points):return sum(Geodesic.WGS84.Inverse(*pair(a),*pair(b))['s12']/.3048 for a,b in zip(points,points[1:]))
folder=Path(sys.argv[1]);sources=sorted(folder.glob('*-source.json'));assert sources
out=[]
for source in sources:
 p=json.loads(source.read_text());q=p['quote'];pr=p['pricing'];charges=[];active=[];industry=q['businessType']
 if industry=='roofing':
  assert q['measurementMode']=='auto' and q['measureSource']=='manual';planes=q['manualPlanes'];assert planes
  for plane in planes:
   expected=area(plane['points'])/math.cos(math.radians(plane['pitch_degrees']))
   assert abs(expected-plane['surface_sqft'])<=max(1,.006*expected)
   active.append({'kind':'roof','sqft':plane['surface_sqft'],'pitch':plane['pitch_degrees']})
  qty=sum(D(x['surface_sqft']) for x in planes);charges=[cent(qty*D(pr['price']))]
 else:
  for a in q['commercialAreas']:
   expected=area(a['points']);assert abs(expected-a['sqft'])<=max(1,.006*expected)
   amount=cent(D(a['sqft'])*D(a['rate']));charges.append(amount);active.append({'kind':'area','name':a['name'],'sqft':a['sqft'],'rate':a['rate'],'amount':str(amount)})
  qty=sum(D(a['sqft']) for a in q['commercialAreas']);points=q.get('linearPoints',[])
  if points:
   expected=length(points);assert abs(expected-q['linearFeet'])<=max(.05,.006*expected)
   key={'commercial':'commercialLinearRate','paving':'pavingLinearRate','pressure':'pressureLinearRate'}.get(industry,'landscapingLinearRate');amount=cent(D(q['linearFeet'])*D(q[key]));charges.append(amount);active.append({'kind':'linear','feet':q['linearFeet'],'rate':q[key],'amount':str(amount)})
 assert abs(float(qty)-p['total_area'])<1e-6,(source,'active area mismatch')
 assert pr['mode']=='regular';sub=sum(charges);extra=D(p.get('extra_service_amount',0));base=cent(sub+extra);gst=cent(base*D(pr['gst'])/100);pst=cent(base*D(pr['pst'])/100);total=base+gst+pst
 assert [sub,base,gst,pst,total]==[D(pr[k]) for k in ['subtotal','taxBase','gstAmt','pstAmt','total']],(source,sub,base,gst,pst,total,pr)
 assert total==D(p['total_price']);out.append({'source':source.name,'industry':industry,'customer':p['customer_name'],'active':active,'subtotal':str(sub),'extra':str(extra),'tax_base':str(base),'gst':str(gst),'pst':str(pst),'total':str(total),'inactive_roof_sections':len(q.get('manualPlanes',[])) if industry!='roofing' else 0})
 print('PASS independent active quantities/WGS84/Decimal',source.name,total)
(folder/'independent-reconciliation.json').write_text(json.dumps(out,indent=2)+'\n')
print('PASS',len(out),'snapshots; 0.6% geometry tolerance reflects spherical app measurements, not survey accuracy')
