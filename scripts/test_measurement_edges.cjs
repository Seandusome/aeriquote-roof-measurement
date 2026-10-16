// Exercise the rendered app buttons and Leaflet click handler in a DOM environment.
const {JSDOM,VirtualConsole}=require('jsdom');const fs=require('fs'),assert=require('assert/strict'),path=require('path'),{execFileSync}=require('child_process');
(async()=>{const errors=[];const vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e.message));const raw=execFileSync('python',['-c',"import ast; from pathlib import Path; m=ast.parse(Path('app.py').read_text()); print(next(ast.literal_eval(n.value) for n in m.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='HTML' for t in n.targets)))"],{maxBuffer:4000000}).toString();const leafletRoot=path.dirname(require.resolve('leaflet/package.json'));const html=raw.replace(/<script[^>]+src=[^>]+>\s*<\/script>/g,'').replace(/<link[^>]+>/g,'').replace(/\{%.*?%\}/g,'').replace(/\{\{GOOGLE_MAPS_API_KEY\}\}/g,'test-key').replace(/\{\{.*?\}\}/g,'').replace('</head>','<style>'+fs.readFileSync(path.join(leafletRoot,'dist/leaflet.css'),'utf8')+'</style><script>'+fs.readFileSync(path.join(leafletRoot,'dist/leaflet.js'),'utf8')+'</script><script>L.Browser.svg=true;</script></head>');for(const industry of ['roofing','snow','pressure','paving','landscaping','commercial']){
const dom=new JSDOM(html,{url:'https://test.invalid/?industry='+industry,runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,beforeParse(w){w.fetch=async()=>({ok:true,json:async()=>({})});w.alert=()=>{};Object.defineProperty(w.HTMLElement.prototype,'clientWidth',{get(){return this.id==='map'?700:1440}});Object.defineProperty(w.HTMLElement.prototype,'clientHeight',{get(){return this.id==='map'?550:800}});w.HTMLElement.prototype.scrollIntoView=()=>{};}});const w=dom.window;await new Promise(r=>w.addEventListener('load',r,{once:true}));

const id=x=>w.document.getElementById(x);
function reset(){w.eval(`el('businessType').value='${industry}';resetMeasurementForNewProperty();sessionToken='measurement-edge-test';businessTypeChanged();map.setView([52,-106],19);el('jobPrice').value='.20';jobPriceChanged()`)}
function points(ps){for(const p of ps)w.eval(`map.fire('click',{latlng:L.latLng(${p[0]},${p[1]})})`)}
const rectangle=[[52,-106],[52,-105.9999],[52.0001,-105.9999],[52.0001,-106]];
const crossing=[[52,-106],[52.0003,-105.9998],[52,-105.9998],[52.0002,-106]];
reset();if(industry==='roofing')assert(w.document.querySelector('.measure-intro').textContent.includes('selected tool'));id('toolAreaBtn').click();points(crossing);const uses=w.eval('usage.area');id('areaStartBtn').click();
assert(!w.eval('areaMeasurementSaved'));assert(w.eval('areaMode'));assert.equal(w.eval('usage.area'),uses);assert(id('status').textContent.includes('crosses itself'));assert(id('createEstimateBtn')?.disabled!==false);
// Leaving an unfinished outline must not silently save its quantity.
const pending=w.eval('JSON.stringify(areaPoints)');id('toolLinearBtn').click();assert.equal(w.eval('measurementViewMode'),'area');assert.equal(w.eval('JSON.stringify(areaPoints)'),pending);
id('areaClearBtn').click();points([[52,-106],[52,-105.9999],[52,-105.9998]]);id('areaStartBtn').click();assert(!w.eval('areaMeasurementSaved'),'Collinear area must not save');
id('areaClearBtn').click();points(rectangle);id('areaStartBtn').click();assert(w.eval('areaMeasurementSaved'));const sqft=w.eval('areaSqFtTotal()');
const expected=6378137**2*(Math.PI/180)**2*.0001*.0001*Math.cos(52.00005*Math.PI/180)*10.76391041671;assert(Math.abs(sqft-expected)/expected<.0001,'Known rectangle area independent calculation: '+sqft+' vs '+expected);
assert.equal(w.eval('measuredPolygonError(areaPoints.slice().reverse())'),'');assert.equal(w.eval('measuredPolygonError([...areaPoints,areaPoints[0]])'),'');
assert.equal(w.eval(`measuredPolygonError([[52,-106],[52,-105.9997],[52.0001,-105.9997],[52.0001,-105.9999],[52.0003,-105.9999],[52.0003,-106]].map(p=>L.latLng(...p)))`),'','Concave L-shaped boundary remains valid');
id('toolLinearBtn').click();points([[52,-106],[52,-106]]);const lineUses=w.eval('usage.linear');id('linearStartBtn').click();assert(!w.eval('linearMeasurementSaved'));assert(w.eval('linearMode'));assert.equal(w.eval('usage.linear'),lineUses);
const lineDraft=w.eval('JSON.stringify(linearPoints)');id('toolAreaBtn').click();assert.equal(w.eval('measurementViewMode'),'linear');assert.equal(w.eval('JSON.stringify(linearPoints)'),lineDraft);
id('linearClearBtn').click();points([[52,-106],[52,-105.999]]);w.eval(`el('jobPrice').value='2';jobPriceChanged()`);id('linearStartBtn').click();const feet=w.eval('linearFeetTotal()');
// A collapsed correction cannot replace a good saved line; Cancel restores it.
id('linearEditBtn').click();w.eval('linearPoints[1]=L.latLng(linearPoints[0].lat,linearPoints[0].lng);redrawLinearMeasure()');id('linearSaveEditBtn').click();assert(w.eval('!!linearCorrectionOriginal'));id('linearCancelEditBtn').click();assert.equal(w.eval('linearFeetTotal()'),feet);
if(industry!=='roofing'){
 const rate=w.eval("currentBusinessType()==='commercial'?commercialLinearRate():surfaceLinearJobRate()");
 id('toolAreaBtn').click();id('commercialAreaList').querySelector('button:last-child').click();
 assert.equal(w.eval('commercialAreas.length'),0);assert.equal(w.eval('measurementViewMode'),'linear');assert.equal(w.eval('linearFeetTotal()'),feet);assert.equal(w.eval('priceCalc().unit'),'linear ft');assert(Math.abs(w.eval('priceCalc().subtotal')-feet*rate)<1e-8);
 assert.equal(w.eval('captureQuoteSnapshot().linearFeet'),feet);assert.equal(w.eval('captureQuoteSnapshot().areaSqFt'),0);
 // Clear the final saved area through the other visible control as well.
 id('toolAreaBtn').click();points(rectangle);id('areaStartBtn').click();id('areaClearBtn').click();assert.equal(w.eval('measurementViewMode'),'linear');assert(Math.abs(w.eval('priceCalc().subtotal')-feet*rate)<1e-8);
}
if(industry==='roofing'){
 reset();w.eval("measurementViewMode='auto';fallbackMode=true;manualOverrideMode=true;toggleTrace()");points(crossing);id('finishTrace').click();assert.equal(w.eval('manualPlanes.length'),0);assert(w.eval('traceMode'));assert(id('status').textContent.includes('crosses itself'));
 w.eval('clearManual()');points(rectangle);id('finishTrace').click();assert.equal(w.eval('manualPlanes.length'),1);assert(w.eval('manualPlanes[0].surface_sqft>areaSqFtTotal()'));
}
// A slow account fetch may hydrate company details, but must not undo an explicit industry choice.
 reset();w.eval("sessionToken='';areaMode=false;linearMode=false");let finishProfile;
 w.fetch=()=>new Promise(resolve=>finishProfile=resolve);w.eval('loadDealerDefaults()');
 const target=industry==='snow'?'pressure':'snow';dom.reconfigure({url:'https://test.invalid/?industry='+target});w.eval(`el('businessType').value='${target}';businessTypeChanged()`);
 const chosenMessage=id('marketingCtaText').value;
 finishProfile({ok:true,json:async()=>({profile:{businessType:industry,company:'Saved Company',marketingCtaText:'Old industry wording',price:.2,country:'CA'}})});
 await new Promise(resolve=>setImmediate(resolve));assert.equal(id('businessType').value,target);assert.equal(id('marketingCtaText').value,chosenMessage);assert.equal(id('dealerCompany').value,'Saved Company');
 console.log('PASS '+industry+': analytical area, concave/closed boundaries, crossed/zero-area rejection, unfinished-draft guards, zero-length line/correction protection'+(industry==='roofing'?', manual roof guard':', remove/clear last area retains priced saved line'));
await new Promise(resolve=>setTimeout(resolve,100));w.eval('_aeriTermObserver.disconnect();clearTimeout(_aeriTermTimer);clearTimeout(customerMapBuildTimer)');assert.deepEqual(errors,[]);dom.window.close();}
console.log('PASS: six-industry measurement edge cases');
})().catch(e=>{console.error(e);process.exit(1)});
