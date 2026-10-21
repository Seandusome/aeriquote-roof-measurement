"""Canonical QA payloads for permission/history tests, independent of production pricing code."""
from decimal import Decimal,ROUND_HALF_UP
D=lambda v:Decimal(str(v))
cent=lambda v:D(v).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
def price_fixture(payload):
 q=payload['quote'];q.setdefault('businessType','landscaping');q.setdefault('measurementMode','area')
 p=payload.setdefault('pricing',{});p.setdefault('mode','regular');p.setdefault('price',1);p.setdefault('gst',0);p.setdefault('pst',0);p.setdefault('disc',0);p.setdefault('estimatePeriod','one_time')
 areas=q.get('commercialAreas',[]);length=D(q.get('linearFeet',0));parts=[]
 if areas:
  area=sum(D(a['sqft']) for a in areas);parts=[cent(D(a['sqft'])*D(a['rate'])) for a in areas]
  if length:
   key={'commercial':'commercialLinearRate','pressure':'pressureLinearRate','paving':'pavingLinearRate'}.get(q['businessType'],'landscapingLinearRate');q.setdefault(key,.7);parts.append(cent(length*D(q[key])))
 elif q['measurementMode']=='linear':area=length;parts=[cent(area*D(p['price']))]
 elif q['measurementMode']=='auto':
  auto=sum(D(r['total_roof_sqft']) for r in q.get('structures',[]));manual=sum(D(r['surface_sqft']) for r in q.get('manualPlanes',[]));src=q.get('measureSource','google');area=auto+manual if src=='hybrid' else (manual or auto) if src=='manual' else auto;parts=[cent(area*D(p['price']))]
 else:area=D(q['areaSqFt']).quantize(D(1),rounding=ROUND_HALF_UP);parts=[cent(area*D(p['price']))]
 sub=sum(parts);extra=D(payload.get('extra_service_amount',0));discount=cent(sub*D(p['disc'])/100) if p['mode']=='discount' else D(0)
 if p['mode']=='included':
  total=cent(sub+extra);base=cent(total/(1+(D(p['gst'])+D(p['pst']))/100));ga=cent(base*D(p['gst'])/100);pa=cent(base*D(p['pst'])/100);base=total-ga-pa
 else:base=cent(sub-discount+extra);ga=cent(base*D(p['gst'])/100);pa=cent(base*D(p['pst'])/100);total=base+ga+pa
 for k,v in dict(area=area,subtotal=sub,discount=discount,extraAmount=extra,taxBase=base,gstAmt=ga,pstAmt=pa,total=total).items():p[k]=float(v)
 p['extraDescription']=payload.get('extra_service_description','');payload.update(total_area=float(area),total_price=float(total))
 return payload


def automatic_roof(points,pitch=22.62,building_id='qa-building'):
 import math
 from measurement_integrity import polygon_sqft
 ground=polygon_sqft(points);surface=ground/math.cos(math.radians(pitch))
 return {'building_id':building_id,'outline':points,'total_roof_sqft':surface,'roof_ground_sqft':ground,'building_ground_sqft':ground,'roof_coverage_ratio':1,'segments':[{'pitch_degrees':pitch,'area_sqft':surface}],'segment_count':1}
