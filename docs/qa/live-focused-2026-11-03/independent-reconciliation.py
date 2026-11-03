from geographiclib.geodesic import Geodesic
from decimal import Decimal, ROUND_HALF_UP
import math,json
areas=[[[52.16175125435327,-106.67605238186192],[52.16175125435327,-106.67582488120978],[52.16165817868,-106.67582488120978],[52.16165817868,-106.67605238186192]],[[52.16214189085673,-106.67603119832991],[52.16214189085673,-106.6758301142626],[52.16206785027778,-106.6758301142626],[52.16206785027778,-106.67603119832991]]]
line=[[52.16159069869516,-106.67604661234887],[52.16159069869516,-106.67530018782598],[52.16164887110198,-106.67530018782598]]
roof=[[52.16196245542267,-106.67613435688385],[52.16196245542267,-106.67580448093824],[52.16171115185071,-106.67580448093824],[52.16171115185071,-106.67613435688385]]
def area(pts):
 p=Geodesic.WGS84.Polygon()
 for lat,lng in pts:p.AddPoint(lat,lng)
 return abs(p.Compute()[2])*10.76391041671
vals=[area(a) for a in areas]; length=sum(Geodesic.WGS84.Inverse(*a,*b)['s12'] for a,b in zip(line,line[1:]))*3.280839895
roof_area=area(roof)/math.cos(math.radians(22.62))
for independent,saved in zip(vals,[1733,1218]):assert abs(independent-saved)/saved<.006
assert abs(length-188.2640110545814)/length<.006
assert abs(roof_area-7348.380392728047)/roof_area<.006
D=Decimal
round2=lambda v:v.quantize(D('.01'),rounding=ROUND_HALF_UP)
base=round2(D(1733)*D('.27'))+round2(D(1218)*D('.27'))+round2(D('188.2640110545814')*D('.1'))+D('54.25')
assert base==D('869.85')
total=base+round2(base*D('.05'))+round2(base*D('.06'));assert total==D('965.53')
rb=round2(D('7348.380392728047')*D('.27'))+D('54.25');rt=rb+round2(rb*D('.05'))+round2(rb*D('.06'));assert rt==D('2262.53')
print(json.dumps({'independent_WGS84_areas_ft2':vals,'independent_line_ft':length,'independent_roof_surface_ft2':roof_area,'area_base':str(base),'area_total':str(total),'roof_base':str(rb),'roof_total':str(rt),'tolerance':'0.6% geodesic vs spherical; cents exact'},indent=2))
