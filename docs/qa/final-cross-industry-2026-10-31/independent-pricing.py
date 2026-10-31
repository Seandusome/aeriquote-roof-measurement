import json,sys
from pathlib import Path
from decimal import Decimal as D, ROUND_HALF_UP
sys.path.insert(0,str(Path.cwd()))
from pricing_integrity import calculate
from geographiclib.geodesic import Geodesic
rows=json.loads(Path('/tmp/aq-final-revision-fixtures.json').read_text());checks=0;area_errors=[];line_errors=[];roof_errors=[]
def money(n):return n.quantize(D('.01'),rounding=ROUND_HALF_UP)
def geodesic_area(points):
 p=Geodesic.WGS84.Polygon()
 for lat,lng in points:p.AddPoint(lat,lng)
 return abs(p.Compute(False,True)[2])*10.76391041671
for q in rows:
 for a in q['commercialAreas']:
  true=geodesic_area(a['points']);area_errors.append(abs(a['sqft']/true-1));assert abs(a['sqft']/true-1)<.01
 line=q['linearPoints'];true=sum(Geodesic.WGS84.Inverse(*a,*b)['s12']*3.28084 for a,b in zip(line,line[1:]));line_errors.append(abs(q['linearFeet']/true-1));assert abs(q['linearFeet']/true-1)<.01
 import math
 for plane in q['manualPlanes']:
  true=geodesic_area(plane['points'])/math.cos(math.radians(plane['pitch_degrees']));roof_errors.append(abs(plane['surface_sqft']/true-1));assert abs(plane['surface_sqft']/true-1)<.01
 for mode in ['regular','discount','included']:
  p={'price':.37,'gst':5,'pst':6,'disc':7,'mode':mode,'extraAmount':12.34,'extraDescription':'Fictional QA add-on','estimatePeriod':'one_time'}
  if q['businessType']=='roofing':subtotal=money(D(str(q['manualPlanes'][0]['surface_sqft']))*D('.37'))
  else:subtotal=sum(money(D(str(a['sqft']))*D(str(a['rate']))) for a in q['commercialAreas'])+money(D(str(q['linearFeet']))*D('.29'))
  discount=money(subtotal*D('.07')) if mode=='discount' else D(0)
  if mode=='included':total=money(subtotal+D('12.34'));base=money(total/D('1.11'));gst=money(base*D('.05'));pst=money(base*D('.06'));base=total-gst-pst
  else:base=money(subtotal-discount+D('12.34'));gst=money(base*D('.05'));pst=money(base*D('.06'));total=base+gst+pst
  expected={'subtotal':subtotal,'discount':discount,'taxBase':base,'gstAmt':gst,'pstAmt':pst,'total':total}
  actual=calculate({'quote':q,'pricing':p,'extra_service_amount':12.34,'extra_service_description':'Fictional QA add-on'})
  for k,v in expected.items():assert actual[k]==v,(q['businessType'],mode,k,actual[k],v)
  checks+=1
result={'passed':True,'pricing_scenarios':checks,'independent_reference':'Decimal line-item/tax arithmetic compared with server pricing; GeographicLib WGS84 versus existing spherical quantities','maximum_area_relative_difference':max(area_errors),'maximum_line_relative_difference':max(line_errors),'maximum_pitch_adjusted_roof_relative_difference':max(roof_errors),'area_rounding_and_spherical_model_tolerance':'.01 maximum; not survey accuracy','physical_device':False}
Path('docs/qa/final-cross-industry-2026-10-31/independent-results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
