// Exercise the rendered app buttons and Leaflet click handler in a DOM environment.
const {JSDOM,VirtualConsole}=require('jsdom');const fs=require('fs'),assert=require('assert/strict'),path=require('path'),{execFileSync}=require('child_process');
(async()=>{const errors=[];const vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e.message));const raw=execFileSync('python',['-c',"import ast; from pathlib import Path; m=ast.parse(Path('app.py').read_text()); print(next(ast.literal_eval(n.value) for n in m.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='HTML' for t in n.targets)))"],{maxBuffer:4000000}).toString();const leafletRoot=path.dirname(require.resolve('leaflet/package.json'));const html=raw.replace(/<script[^>]+src=[^>]+>\s*<\/script>/g,'').replace(/<link[^>]+>/g,'').replace(/\{%.*?%\}/g,'').replace(/\{\{GOOGLE_MAPS_API_KEY\}\}/g,'test-key').replace(/\{\{.*?\}\}/g,'').replace("const MANUAL_ROOF_QA=''==='1'","const MANUAL_ROOF_QA=true").replace('</head>','<style>'+fs.readFileSync(path.join(leafletRoot,'dist/leaflet.css'),'utf8')+'</style><script>'+fs.readFileSync(path.join(leafletRoot,'dist/leaflet.js'),'utf8')+'</script><script>L.Browser.svg=true;</script></head>');const dom=new JSDOM(html,{url:'https://test.invalid/?industry=landscaping',runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,beforeParse(w){w.fetch=async()=>({ok:true,json:async()=>({})});w.alert=()=>{};Object.defineProperty(w.HTMLElement.prototype,'clientWidth',{get(){return this.id==='map'?700:1440}});Object.defineProperty(w.HTMLElement.prototype,'clientHeight',{get(){return this.id==='map'?550:800}});w.HTMLElement.prototype.scrollIntoView=()=>{};}});const w=dom.window;await new Promise(r=>w.addEventListener('load',r,{once:true}));w.eval("el('businessType').value='landscaping';sessionToken='test';businessTypeChanged();map.setView([52,-106],19)");const btn=id=>w.document.getElementById(id);btn('toolAreaBtn').click();function draw(offset){for(const p of [[52+offset,-106],[52+offset,-105.9999],[52.0001+offset,-105.9999],[52.0001+offset,-106]])w.eval(`map.fire('click',{latlng:L.latLng(${p[0]},${p[1]})})`);btn('areaStartBtn').click();}



w.eval("resetMeasurementForNewProperty();el('businessType').value='roofing';businessTypeChanged();sessionToken='manual-qa';fallbackMode=true;manualOverrideMode=true;structures=[];measurementViewMode='auto';el('jobPrice').value='.2';el('gst').value='5';el('pst').value='6';renderSummary()");
w.eval('applyBusinessTerminology()');assert(w.document.querySelector('.measure-intro span').textContent.includes('Confirm pitch'));assert.equal(btn('toolAreaBtn').querySelector('b').textContent,'TRACE ROOF');assert(w.eval('manualRoofQa()'));assert.equal(btn('toolAutoBtn').style.display,'none');
function trace(points,pitch='22.62'){
 w.eval('beginManualRoofSection()');for(const [lat,lng] of points)w.eval(`addTracePoint(L.latLng(${lat},${lng}))`);
 w.eval('finishTrace()'); // Blank pitch must block saving.
 assert(w.eval('traceMode'));
 btn('pitchSel').value=pitch;w.eval('pitchChanged();finishTrace()');
}
const roof=[[52,-106],[52,-105.9999],[52.0001,-105.9999],[52.0001,-106]];
trace(roof);assert.equal(w.eval('manualPlanes.length'),1);assert(w.eval('manualPlanes[0].pitch_confirmed'));
const first=w.eval('JSON.stringify(manualPlanes[0])');
trace(roof.map(([lat,lng])=>[lat,lng+.0001]),'0');assert.equal(w.eval('manualPlanes.length'),2,'Adjacent facets allowed: '+w.document.body.textContent.slice(-700));
trace(roof.map(([lat,lng])=>[lat+.001,lng]),'45');assert.equal(w.eval('manualPlanes.length'),3,'Detached garage');
w.eval('beginManualRoofSection()');for(const [lat,lng] of roof)w.eval(`addTracePoint(L.latLng(${lat},${lng}))`);btn('pitchSel').value='22.62';w.eval('pitchChanged();finishTrace()');assert.equal(w.eval('manualPlanes.length'),3,'Overlap rejected');w.eval('cancelCurrentTrace();renderSummary()');
w.eval('editManualRoofSection(0)');assert.equal(w.eval('manualRoofEditIndex'),0);assert.equal(btn('pitchSel').value,'');w.eval('cancelCurrentTrace();redrawManualDisplayLayers();renderSummary()');assert.equal(w.eval('JSON.stringify(manualPlanes[0])'),first,'Cancel preserves geometry/pitch');
w.eval('editManualRoofSection(0)');btn('pitchSel').value='0';w.eval('pitchChanged();finishTrace()');assert.equal(w.eval('manualPlanes.length'),3,'Edit replaces one section');assert.equal(w.eval('manualPlanes[0].pitch_degrees'),0);
w.eval('deleteManualRoofSection(1)');assert.equal(w.eval('manualPlanes.length'),2);assert.equal(w.eval('manualPlanes[1].pitch_degrees'),45,'Delete preserves garage');
assert(w.eval('quotePricingError()').includes('Confirm'));btn('manualRoofScopeConfirmed').checked=true;btn('manualRoofScopeConfirmed').dispatchEvent(new w.Event('change'));assert.equal(w.eval('quotePricingError()'),'');
const snap=w.eval('captureQuoteSnapshot()');assert(snap.manualRoofWorkflow&&snap.roofScopeConfirmed);assert.equal(snap.manualPlanes.length,2);
const area=w.eval('priceCalc().area');w.eval('map.setZoom(21);map.panTo([52.00005,-106])');assert.equal(w.eval('priceCalc().area'),area);
w.eval('beginManualRoofSection()');assert(w.eval('quotePricingError()').includes('Save or cancel'));w.eval('cancelCurrentTrace();renderSummary()');
btn('manualRoofScopeConfirmed').checked=true;btn('manualRoofScopeConfirmed').dispatchEvent(new w.Event('change'));
w.HTMLCanvasElement.prototype.toDataURL=()=> 'data:image/jpeg;base64,QA';
await w.eval('showCustomerEstimate()');
w.eval('clearTimeout(customerMapBuildTimer);customerMapBuildTimer=null;estimateOpenInProgress=false');
assert(btn('rProperty').textContent.includes('Dealer Manual Measurement'));
assert(btn('rPricing').textContent.includes(w.eval('money(priceCalc().total)')),'Customer total matches pitch-adjusted price');
assert.equal(w.eval('quoteSnapshot.manualPlanes.length'),2);
const frozen=w.eval('JSON.stringify(quoteSnapshot)');
// Real Single/Expanded exporter entry points, controlled canvas/PDF sinks (not live downloaded PDFs).
w.eval("document.body.classList.remove('report-open');el('streetViewChoice').value='none';customerMap=null;reportOutlineEditMode=false");
w.HTMLCanvasElement.prototype.getContext=()=>new Proxy({},{get:(_,k)=>k==='measureText'?()=>({width:20}):()=>{}});
w.HTMLImageElement.prototype.decode=async()=>{};
const exports=[];let captures=0;
w.html2canvas=async node=>{captures++;assert(node.textContent.includes(w.eval('money(priceCalc().total)'))||!node.classList.contains('report'),'Price remains in captured report');return{width:1320,height:1800,toDataURL:()=> 'data:image/jpeg;base64,QA'}};
w.jspdf={jsPDF:class{constructor(){this.internal={pageSize:{getWidth:()=>297,getHeight:()=>210}}}addImage(){}addPage(){}save(name){exports.push(name)}}};
for(const layout of ['single','expanded']){btn('estimatePdfLayout').value=layout;await w.eval('downloadEstimatePDF()');assert.equal(w.eval('JSON.stringify(quoteSnapshot)'),frozen,'PDF never mutates roof sections/pitch/pricing')}
assert.equal(exports.length,2,'Both real exporter entry points reach PDF save');assert(captures>=2);
w.eval("el('businessType').value='snow';businessTypeChanged();renderSummary()");assert.equal(btn('manualRoofSections'),null,'QA section controls disappear outside Roofing');assert.equal(btn('toolAreaBtn').disabled,false);
assert.equal(errors.length,0,JSON.stringify(errors));
console.log('PASS actual DOM/Leaflet manual sections: explicit pitch, shared edges, garage, overlap rejection, individual edit/cancel/delete, scope confirmation, draft blocking, snapshot and zoom invariance; emulated browser only');
dom.window.close();
})().catch(e=>{console.error(e);process.exit(1)});
