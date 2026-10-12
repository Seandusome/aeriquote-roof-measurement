// Execute the application's actual functions with deterministic map/DOM adapters.
const fs=require('fs'), vm=require('vm'), assert=require('assert/strict');
const source=fs.readFileSync('app.py','utf8');
const names=['commercialActive','multiAreaTotal','multiAreaSaved','landscapingHasAreas','landscapingAreaSubtotal','landscapingSavedPriceLines','landscapingCombined','landscapingAreaRate','commercialSyncCurrent','commercialAddArea','commercialSelectArea','commercialRemoveArea','commercialAreaField','priceCalc','captureQuoteSnapshot','jobPriceChanged','currentJobPrice','localPolygonAreaM2','areaSqFtTotal'];
const funcs=names.map(n=>(()=>{const lines=source.split('\n'),i=lines.findIndex(l=>l.startsWith('function '+n+'('));if(lines[i].endsWith('}'))return lines[i];const j=lines.findIndex((l,k)=>k>i&&l==='}');return lines.slice(i,j+1).join('\n')})()).join('\n');
const fields={jobPrice:{value:'0.10'},pricingMode:{value:'added'},discountPct:{value:'0'},gst:{value:'5'},pst:{value:'6'},landscapingAreaRate:{value:'0.10'}};
const c={console, commercialAreas:[],commercialAreaLayers:[],commercialEditingIndex:-1,areaPoints:[],areaMode:false,areaMeasurementSaved:false,linearPoints:[],linearMeasurementSaved:false,measurementViewMode:'area',structures:[],manualPlanes:[],quoteSnapshot:null,
 el:id=>fields[id],currentBusinessType:()=> 'landscaping',linearFeetTotal:()=>40, commercialHasAreas:()=>false,commercialHasLinear:()=>false,pressureCombined:()=>false,pavingCombined:()=>false,estimateArea:()=>999,
 fmt:String,money:n=>Number(n).toFixed(2),escapeHistory:String,clearAreaLayers(){},commercialAreaDrawSaved(){},updateAreaUi(){},renderSummary(){},status(){},redrawAreaMeasure(){},toggleAreaMeasure(){c.areaMode=true},L:{latLng:(lat,lng)=>({lat,lng})}};
vm.createContext(c);vm.runInContext(funcs,c);
const poly=[[52,-106],[52,-105.9999],[52.0001,-105.9999],[52.0001,-106]];
function save(points=poly){c.areaPoints=points.map(p=>c.L.latLng(...p));c.areaMode=false;c.areaMeasurementSaved=true;c.commercialSyncCurrent();}
save();const first=c.multiAreaTotal();assert(first>0);
c.commercialAddArea();assert.equal(c.commercialAreas.length,2);assert.equal(c.multiAreaTotal(),first);
save(poly.map(p=>[p[0]+.001,p[1]]));assert(c.multiAreaTotal()>first);
c.commercialAreaField(0,'rate',.10);c.commercialAreaField(1,'rate',.25);
const subtotal=c.commercialAreas[0].sqft*.1+c.commercialAreas[1].sqft*.25;
assert.equal(c.priceCalc().subtotal,subtotal);
c.areaMode=true;c.areaMeasurementSaved=false;c.areaPoints=[];assert.equal(c.priceCalc().subtotal,subtotal);
c.areaMode=false;c.linearMeasurementSaved=true;c.linearPoints=[{},{}];c.measurementViewMode='linear';fields.jobPrice.value='2';
assert.equal(c.priceCalc().subtotal,subtotal+80);assert.equal(c.priceCalc().unit,'ft²');
assert(Math.abs(c.priceCalc().total-(subtotal+80)*1.11)<1e-8);
const snap=c.captureQuoteSnapshot();assert.equal(snap.commercialAreas.length,2);assert.equal(snap.areaSqFt,c.multiAreaTotal());
assert(c.landscapingSavedPriceLines(snap).includes('Service Area 2'));
c.measurementViewMode='area';c.commercialSelectArea(0);fields.jobPrice.value='.3';c.jobPriceChanged();assert.equal(c.commercialAreas[0].rate,.3);
c.commercialRemoveArea(0);assert.equal(c.commercialAreas.length,1);const remaining=c.commercialAreas[0].sqft;
c.commercialEditingIndex=-1;save();assert.equal(c.commercialAreas.length,2);assert.equal(c.commercialAreas[0].sqft,remaining);
c.commercialRemoveArea(1);c.commercialRemoveArea(0);assert.equal(c.multiAreaTotal(),0);assert.equal(c.priceCalc().subtotal,0);
console.log('PASS: independent areas, draft preservation, per-area rates, mixed units, tax, snapshots, editing, removal, append after removal');
