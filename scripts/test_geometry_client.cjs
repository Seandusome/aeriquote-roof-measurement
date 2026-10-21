const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync('app.py','utf8');
const code=source.slice(source.indexOf('function measuredPolygonError('),source.indexOf('function setTraceControls('))+source.slice(source.indexOf('function savedAreaGeometryError('),source.indexOf('function quotePricingError('));
const c={commercialAreas:[]};vm.createContext(c);vm.runInContext(code,c);
const poly=[[52,-106],[52,-105.999],[52.001,-105.999],[52.001,-106]],move=(dx,dy=0)=>poly.map(([lat,lon])=>[lat+dy,lon+dx]);
const area=points=>({points,sqft:Math.round(c.localPolygonAreaM2(points.map(([lat,lng])=>({lat,lng})))*10.76391041671),rate:.1});
for(const industry of ['snow','pressure','paving','landscaping','commercial']){
 c.commercialAreas=[area(poly),area(move(.002))];assert.equal(c.savedAreaGeometryError(),'');
 c.commercialAreas=[area(poly),area(move(.001))];assert.equal(c.savedAreaGeometryError(),'','Shared edge allowed');
 for(const points of [poly,poly.slice().reverse(),move(.0005),move(.0005,.0005)]){c.commercialAreas=[area(poly),area(points)];assert(c.savedAreaGeometryError().includes('overlap'),industry)}
 c.commercialAreas=[area(poly)];c.commercialAreas[0].sqft=1;assert(c.savedAreaGeometryError().includes('quantity'));
 c.commercialAreas=[{points:[],sqft:100}];assert(c.savedAreaGeometryError().includes('outline'));
}
const u=[[52,-106],[52,-105.997],[52.003,-105.997],[52.003,-105.998],[52.001,-105.998],[52.001,-105.999],[52.003,-105.999],[52.003,-106]];c.commercialAreas=[area(u),area(u)];assert(c.savedAreaGeometryError().includes('overlap'));const hole=[[52.0015,-105.9988],[52.0015,-105.9982],[52.0025,-105.9982],[52.0025,-105.9988]];c.commercialAreas=[area(u),area(hole)];assert.equal(c.savedAreaGeometryError(),'');
console.log('PASS: actual client blocks missing/mismatched saved outlines and duplicate/partial overlap before report/save; adjacent and separated areas allowed');
