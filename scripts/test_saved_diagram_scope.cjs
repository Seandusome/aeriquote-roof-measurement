// Execute the actual historical renderer and label painter with isolated DOM/image
// stubs. Requests, labels and source immutability are checked, not source substrings.
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const {JSDOM}=require('jsdom');const dom=new JSDOM('<div/>');global.window=dom.window;global.document=dom.window.document;const L=require('leaflet');
const source=fs.readFileSync(process.argv[2]||'app.py','utf8');
const measured=source.slice(source.indexOf('function measuredPolygonError('),source.indexOf('\nfunction ',source.indexOf('function measuredPolygonError(')+10));
const geometry=source.split('\n').find(l=>l.startsWith('function localPolygonAreaM2('))+measured+source.slice(source.indexOf('function savedLinearGeometryError('),source.indexOf('function quotePricingError('));
let requests=[],labels=[],canvas=null;const host={style:{},innerHTML:'',appendChild(c){canvas=c},querySelector(){return canvas}};
const ctx={save(){},restore(){},drawImage(){},measureText:t=>({width:String(t).length*8}),beginPath(){},moveTo(){},lineTo(){},stroke(){},fillRect(){},strokeRect(){},fillText(t){labels.push(String(t))}};
const c={L,Number,Math,JSON,Error,fmt:n=>Math.round(n).toLocaleString('en-US'),el:id=>id==='customerMap'?host:{style:{}},customerMap:null,customerRgbLayer:null,customerOverlays:[],URL:{createObjectURL:()=> 'blob:fictional',revokeObjectURL(){}},document:{createElement:()=>({style:{},dataset:{},getContext:()=>ctx})},Image:class{constructor(){this.naturalWidth=1280;this.naturalHeight=840}set src(v){queueMicrotask(()=>this.onload())}},measurementLabelPosition:(x,y,w,h)=>({x:x-w/2,y:y-h/2}),fetch:async(url,options)=>{requests.push(JSON.parse(options.body));return{ok:true,headers:{get:()=>JSON.stringify({latitude:52,longitude:-106,zoom:19,width:640,height:420})},blob:async()=>({})}}};vm.createContext(c);
const start=source.includes('function activeSavedDiagramSnapshot(')?source.indexOf('function activeSavedDiagramSnapshot('):source.indexOf('function drawSavedMeasurementLabels(');
vm.runInContext(geometry+source.slice(start,source.indexOf('async function buildCustomerMap(')),c);
const ring=[[52,-106],[52,-105.9998],[52.0001,-105.9998],[52.0001,-106]],other=ring.map(([a,b])=>[a+.001,b]),line=[[52,-106],[52,-105.9999]];
const sqft=p=>Math.round(c.localPolygonAreaM2(p.map(p=>L.latLng(p)))*10.76391041671),feet=L.latLng(line[0]).distanceTo(L.latLng(line[1]))*3.28084;
const base={businessType:'commercial',measurementMode:'area',measureSource:'manual',commercialAreas:[{points:ring,sqft:sqft(ring),rate:.1},{points:other,sqft:sqft(other),rate:.1}],areaPoints:ring,areaSqFt:sqft(ring)+sqft(other),linearPoints:line,linearFeet:feet,manualPlanes:[{points:ring,surface_sqft:7348,pitch_degrees:22.6}],structures:[{outline:other,total_roof_sqft:1000}]};
async function render(snap){requests=[];labels=[];canvas=null;c.quoteSnapshot=snap;await c.buildSavedHistoricalSnapshot();return{requests:JSON.parse(JSON.stringify(requests)),labels:[...labels]}}
(async()=>{
 for(const industry of ['commercial','snow','pressure','paving','landscaping']){
  for(const mode of ['area','linear']){
   const snap={...base,businessType:industry,measurementMode:mode};const saved=JSON.stringify(snap);const out=await render(snap);
   assert.deepEqual(out.requests[0].roofs.map(x=>x.kind),['area','area','linear'],'Reopened '+industry+' must render exactly the priced surfaces, never inactive roofs');assert(!out.labels.includes('22.6°'));assert.equal(JSON.stringify(snap),saved,'Never rewrite a saved revision');
   assert.equal(c.savedDiagramGeometryError(snap),'');
  }
 }
 for(const [source,kinds]of [['google',['house']],['manual',['manual']],['hybrid',['house','manual']],['adjusted',['house']]]){
  const snap={...base,businessType:'roofing',measurementMode:'auto',measureSource:source};const saved=JSON.stringify(snap);const out=await render(snap);assert.deepEqual(out.requests[0].roofs.map(x=>x.kind),kinds);assert.equal(JSON.stringify(snap),saved);
 }
 for(const mode of ['area','linear']){const out=await render({...base,businessType:'roofing',measurementMode:mode,areaSqFt:sqft(ring)});assert.deepEqual(out.requests[0].roofs.map(x=>x.kind),[mode]);}
 const bad={...base,commercialAreas:[{...base.commercialAreas[0],sqft:99999}]};assert.match(c.savedDiagramGeometryError(bad),/quantity/);const before=requests.length;await assert.rejects(()=>render(bad),/quantity/);assert.equal(requests.length,0,'Invalid active geometry cannot request an aerial');
 const mismatch={...base,savedPricing:{area:1}};assert.match(c.savedDiagramGeometryError(mismatch),/quantity/);
 const download=source.slice(source.indexOf('async function downloadEstimatePDF(){'),source.indexOf('let reportCloseArmedAt=')),print=source.split('\n').find(l=>l.startsWith('function printEstimate(){'));
 let blocked=[];Object.assign(c,{quoteSnapshot:bad,status:m=>blocked.push(m),window:{print(){throw Error('Unsafe print')}},document:{querySelector(){throw Error('Unsafe capture')}}});vm.runInContext(download+print,c);for(const layout of ['single','expanded','vector']){c.el=()=>({value:layout});await c.downloadEstimatePDF();c.printEstimate();}assert.equal(blocked.length,6);assert(blocked.every(m=>m.includes('quantity')));
 console.log('PASS: historical request + label scope, five surface industries, roof sources/modes, repeated reopening, immutable revisions, invalid/mismatched geometry blocks every PDF mode and Print');dom.window.close();
})().catch(e=>{console.error(e);process.exit(1)});
