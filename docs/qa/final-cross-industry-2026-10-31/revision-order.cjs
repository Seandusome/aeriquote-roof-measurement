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
 const revisions=[],expected=[];
 for(let n=0;n<30;n++)for(const businessType of ['roofing','snow','pressure','paving','landscaping','commercial']){
  const dx=n*.00001,move=points=>points.map(([lat,lng])=>[lat,lng+dx]);
  const a=move(ring),b=move(other),l=move(line),roof=ring.map(([lat,lng])=>[lat+.003,lng+dx]);
  const ground=c.localPolygonAreaM2(roof.map(p=>L.latLng(p)))*10.76391041671,pitch=[0,18.43494882292201,26.56505117707799,45][n%4];
  const snap={...JSON.parse(JSON.stringify(base)),businessType,measurementMode:businessType==='roofing'?'auto':n%2?'linear':'area',measureSource:'manual',commercialAreas:[{name:'QA A '+n,points:a,sqft:sqft(a),rate:.13},{name:'QA B '+n,points:b,sqft:sqft(b),rate:.07}],areaPoints:a,areaSqFt:sqft(a)+sqft(b),linearPoints:l,linearFeet:L.latLng(l[0]).distanceTo(L.latLng(l[1]))*3.28084,manualPlanes:[{points:roof,surface_sqft:ground/Math.cos(pitch*Math.PI/180),pitch_degrees:pitch}],commercialLinearRate:.29,landscapingLinearRate:.29,pressureLinearRate:.29,pavingLinearRate:.29};
  snap.savedPricing={area:businessType==='roofing'?snap.manualPlanes[0].surface_sqft:snap.areaSqFt};
  revisions.push(snap);expected.push(businessType==='roofing'?['manual']:['area','area','linear']);
 }
 const originals=revisions.map(q=>JSON.stringify(q));let seed=20261031;const rnd=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed};
 // Alternating old/new and randomized revisions exercise reused renderer state.
 const order=[...revisions.keys()].reverse().concat([...revisions.keys()]);for(let i=0;i<720;i++)order.push(rnd()%revisions.length);
 for(const index of order){const q=revisions[index],out=await render(q);assert.deepEqual(out.requests[0].roofs.map(x=>x.kind),expected[index]);assert.equal(JSON.stringify(q),originals[index]);assert.equal(c.savedDiagramGeometryError(q),'');if(q.businessType!=='roofing')assert(!out.labels.some(t=>t.endsWith('°')));else assert.equal(out.labels.filter(t=>t.endsWith(' ft²')).length,0,'Roof revision must not inherit service Area labels');}
 for(let i=0;i<revisions.length;i++)assert.equal(JSON.stringify(revisions[i]),originals[i]);
 fs.writeFileSync('/tmp/aq-final-revision-fixtures.json',JSON.stringify(revisions));
 console.log(JSON.stringify({passed:true,fictional_revisions:revisions.length,rendered_reopens:order.length,industries:6,scope_and_source_immutability:true,physical_device:false}));dom.window.close();
})().catch(e=>{console.error(e);process.exit(1)});
