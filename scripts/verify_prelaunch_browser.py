"""Independent WGS84 geometry and Decimal arithmetic for fictional browser snapshots."""
import json,math,sys
from pathlib import Path
from decimal import Decimal,ROUND_HALF_UP
from geographiclib.geodesic import Geodesic
D=lambda v:Decimal(str(v))
cent=lambda v:D(v).quantize(D('.01'),rounding=ROUND_HALF_UP)
def pair(p):return (p['lat'],p['lng']) if isinstance(p,dict) else p

def area(points):
 p=Geodesic.WGS84.Polygon()
 for point in points:p.AddPoint(*pair(point))
 return abs(p.Compute()[2])/(.3048**2)

folder=Path(sys.argv[1]);sources=sorted(folder.glob('*-source.json'));assert sources,'No browser sources'
for source in sources:
 p=json.loads(source.read_text());q=p['quote'];pr=p['pricing'];charges=[]
 for a in q.get('commercialAreas',[]):
  assert abs(a['sqft']-area(a['points']))<=max(1,area(a['points'])*.006),(source,a)
  charges.append(cent(D(a['sqft'])*D(a['rate'])))
 points=q.get('linearPoints',[])
 if points:
  independent=sum(Geodesic.WGS84.Inverse(*pair(a),*pair(b))['s12']/.3048 for a,b in zip(points,points[1:]))
  assert abs(q['linearFeet']-independent)<=max(.05,independent*.006)
  key={'commercial':'commercialLinearRate','pressure':'pressureLinearRate','paving':'pavingLinearRate'}.get(q['businessType'],'landscapingLinearRate')
  charges.append(cent(D(q['linearFeet'])*D(q[key])))
 planes=q.get('manualPlanes',[])
 if planes:
  for plane in planes:
   expected=area(plane['points'])/math.cos(math.radians(plane['pitch_degrees']))
   assert abs(plane['surface_sqft']-expected)<=max(1,expected*.006)
  charges.append(cent(sum(D(x['surface_sqft']) for x in planes)*D(pr['price'])))
 assert pr['mode']=='regular', 'This fixture independently verifies regular pricing; other modes covered by server pricing matrix'
 sub=sum(charges);assert cent(sub)==cent(pr['subtotal']),(source,sub,pr)
 base=cent(sub+D(pr['extraAmount']));gst=cent(base*D(pr['gst'])/100);pst=cent(base*D(pr['pst'])/100)
 assert (base,gst,pst,base+gst+pst)==tuple(D(pr[k]) for k in ['taxBase','gstAmt','pstAmt','total'])
 assert D(p['total_price'])==base+gst+pst
 print('PASS independent WGS84 + Decimal',source.name,pr['total'])
print('PASS',len(sources),'saved browser snapshots; WGS84 tolerance 0.6% reflects existing spherical measurements, not survey accuracy')
