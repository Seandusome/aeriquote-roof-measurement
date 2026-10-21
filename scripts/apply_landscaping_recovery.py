from pathlib import Path
p=Path('app.py')
s=p.read_text()
old="area=linearActive?linearFeetTotal():(areaActive?(savedServiceAreas.length?savedAreaTotal():Math.round(areaSqFtTotal())):estimateArea()),price=currentJobPrice()"
new="area=(savedServiceAreas.length?savedAreaTotal():0)+(linearMeasurementSaved?linearFeetTotal():0)|| (linearActive?linearFeetTotal():(areaActive?Math.round(areaSqFtTotal()):estimateArea())),price=currentJobPrice()"
assert s.count(old)==1
s=s.replace(old,new,1)
old="subtotal=area*price,extraDescription="
new="subtotal=(savedServiceAreas.length&&['landscaping','paving','pressure'].includes(currentBusinessType())?savedAreaTotal()*price:0)+(linearMeasurementSaved&&['landscaping','paving','pressure'].includes(currentBusinessType())?linearFeetTotal()*price:0)+(!['landscaping','paving','pressure'].includes(currentBusinessType())||(!savedServiceAreas.length&&!linearMeasurementSaved)?area*price:0),extraDescription="
assert s.count(old)==1
s=s.replace(old,new,1)
old="if(snap.measurementMode==='area'&&Array.isArray(snap.areaPoints)"
new="if(['landscaping','paving','pressure'].includes(currentBusinessType())&&Array.isArray(snap.serviceAreas)&&snap.serviceAreas.length){const bounds=[];snap.serviceAreas.forEach((a,i)=>{if(!Array.isArray(a.points)||a.points.length<3)return;const poly=L.polygon(a.points,{color:'#7357b8',weight:4,fillOpacity:.12,interactive:false}).addTo(customerMap);customerOverlays.push(poly);bounds.push(...a.points);const lab=L.marker(poly.getBounds().getCenter(),{interactive:false,icon:L.divIcon({className:'',html:`<div class=\"area-label\">${fmt(a.sqft)} ft²</div>`,iconAnchor:[35,10]})}).addTo(customerMap);customerOverlays.push(lab)});if(snap.linearPoints?.length>1){const pts=snap.linearPoints.map(p=>L.latLng(p[0],p[1]));const line=L.polyline(pts,{color:'#0f8f83',weight:5,interactive:false}).addTo(customerMap);customerOverlays.push(line);bounds.push(...snap.linearPoints)}if(bounds.length)customerMap.fitBounds(L.latLngBounds(bounds).pad(.12),{padding:[24,24],animate:false,maxZoom:21.5});return}\n if(snap.measurementMode==='area'&&Array.isArray(snap.areaPoints)"
assert s.count(old)==1
s=s.replace(old,new,1)
old="if(areaReport){prop="
new="if(['landscaping','paving','pressure'].includes(currentBusinessType())&&snap.serviceAreas?.length){prop='<div class=\"metric-grid\"><div class=\"metric\">Total Service Area<b>'+fmt(snap.areaSqFt)+' ft²</b></div></div>'+snap.serviceAreas.map((a,i)=>'<div class=\"structure\"><div class=\"structure-head\"><b>'+escapeHistory(a.name||'Service Area '+(i+1))+'</b><b>'+fmt(a.sqft)+' ft²</b></div></div>').join('')+(snap.linearFeet>0?'<div class=\"structure\"><div class=\"structure-head\"><b>Linear Service</b><b>'+snap.linearFeet.toFixed(1)+' ft</b></div></div>':'')}\n else if(areaReport){prop="
assert s.count(old)==1
s=s.replace(old,new,1)
p.write_text(s)
import py_compile
py_compile.compile(str(p),doraise=True)
print('Patched multi-area quote total and customer map/estimate rendering')
