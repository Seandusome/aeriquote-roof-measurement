from pathlib import Path
from decimal import Decimal,ROUND_HALF_UP
from geographiclib.geodesic import Geodesic
import json,math,sys
D=lambda v:Decimal(str(v));money=lambda v:v.quantize(D('.01'),rounding=ROUND_HALF_UP)
root=Path(sys.argv[1]);rows=[]
for p in sorted(root.glob('*-source.json')):
 data=json.loads(p.read_text());q=data['quote'];price=data['pricing'];areas=q.get('commercialAreas',[]);items=[];shapes=[]
 if q['businessType']!='roofing':
  items=[money(D(a['sqft'])*D(a['rate'])) for a in areas];shapes=[(a['points'],a['sqft'],0) for a in areas]
  length=D(q.get('linearFeet',0));key={'snow':'landscapingLinearRate','pressure':'pressureLinearRate','paving':'pavingLinearRate','landscaping':'landscapingLinearRate','commercial':'commercialLinearRate'}[q['businessType']]
  if length:items.append(money(length*D(q[key])))
 else:
  qty=sum((D(a['surface_sqft']) for a in q.get('manualPlanes',[])),D(0));items=[money(qty*D(price['price']))];shapes=[(a['points'],a['surface_sqft'],a['pitch_degrees']) for a in q.get('manualPlanes',[])]
 subtotal=sum(items,D(0));discount=money(subtotal*D('0.125'));base=money(subtotal-discount+D('23.47'));gst=money(base*D('.05'));pst=money(base*D('.06'));total=base+gst+pst
 for key,value in [('subtotal',subtotal),('discount',discount),('taxBase',base),('gstAmt',gst),('pstAmt',pst),('total',total)]:assert abs(D(price[key])-value)<D('.000001'),(p.name,key,price[key],value)
 assert D(data['total_price'])==total
 geometry=[]
 for points,qty,pitch in shapes:
  poly=Geodesic.WGS84.Polygon()
  for v in points:
   lat,lng=(v['lat'],v['lng']) if isinstance(v,dict) else v;poly.AddPoint(lat,lng)
  _,_,area=poly.Compute(False,True);surface=abs(area)*10.76391041671/math.cos(math.radians(pitch));delta=abs(surface-qty)/surface;assert delta<.005,(p.name,delta);geometry.append({'saved_quantity':qty,'wgs84_pitch_adjusted':surface,'relative_difference':delta,'pitch':pitch})
 if q.get('linearFeet',0):
  pts=q['linearPoints'];r=math.radians;feet=0
  for a,b in zip(pts,pts[1:]):h=math.sin(r(b[0]-a[0])/2)**2+math.cos(r(a[0]))*math.cos(r(b[0]))*math.sin(r(b[1]-a[1])/2)**2;feet+=2*6371000*math.asin(math.sqrt(h))/.3048
  assert abs(feet-q['linearFeet'])<.011
 rows.append({'case':p.stem,'independent_total':str(total),'geometry':geometry,'independent_price_tax':True})
(root/'independent-checks.json').write_text(json.dumps(rows,indent=2));print('PASS independent Decimal price/discount/extra/GST/PST',len(rows),'cases;',sum(len(r['geometry']) for r in rows),'WGS84/pitch polygons; max deviation',max(g['relative_difference'] for r in rows for g in r['geometry']))
