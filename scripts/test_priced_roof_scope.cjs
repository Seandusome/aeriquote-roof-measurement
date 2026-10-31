const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('app.py','utf8');
const lines=source.split('\n');
const c={};vm.createContext(c);
// Use the existing shared geometry functions, not a replacement measuring engine.
const measuredStart=source.indexOf('function measuredPolygonError('),measuredEnd=source.indexOf('\nfunction ',measuredStart+10);
vm.runInContext(lines.find(x=>x.startsWith('function localPolygonAreaM2('))+source.slice(measuredStart,measuredEnd)+source.slice(source.indexOf('function savedAreaGeometryError('),source.indexOf('function quotePricingError('))+source.slice(source.indexOf('function manualRoofGeometryError('),source.indexOf('function beginManualRoofSection(')),c);
const points=[[52,-106],[52,-105.9999],[52.0001,-105.9999],[52.0001,-106]],shift=dx=>points.map(([a,b])=>[a,b+dx]);
function quote(src,other){return {businessType:'roofing',measurementMode:'auto',measureSource:src,structures:src==='manual'?[]:[{outline:points},...(src==='google'?[{outline:other,manually_measured:true}]:[])],manualPlanes:src==='google'?[]:[{points:src==='hybrid'?other:points},...(src==='manual'?[{points:other}]:[])]};}
for(const src of ['manual','hybrid','google']){
 for(const other of [points,points.slice().reverse(),shift(.00005)])assert.match(c.pricedRoofGeometryError(quote(src,other)),/overlap/);
 for(const other of [shift(.0001),shift(.001)])assert.equal(c.pricedRoofGeometryError(quote(src,other)),'');
}
assert.equal(c.pricedRoofGeometryError({businessType:'snow',measurementMode:'area'}),'');
(async()=>{
 const download=source.slice(source.indexOf('async function downloadEstimatePDF(){'),source.indexOf('let reportCloseArmedAt='));
 const print=lines.find(x=>x.startsWith('function printEstimate(){'));
 for(const layout of ['single','expanded','vector']){
  const messages=[];c.quoteSnapshot=quote('hybrid',points);const saved=JSON.stringify(c.quoteSnapshot);
  Object.assign(c,{status:m=>messages.push(m),el:()=>({value:layout}),window:{print(){throw Error('Unsafe print')}},document:{querySelector(){throw Error('Unsafe capture')}}});
  vm.runInContext(download+print,c);await c.downloadEstimatePDF();c.printEstimate();
  assert.equal(messages.length,2);assert(messages.every(m=>m.includes('overlap')));assert.equal(JSON.stringify(c.quoteSnapshot),saved);
 }
 console.log('PASS: mixed/manual roof overlap guard, adjoining valid sections, surface isolation, all PDF modes/Print blocked before capture without altering saved geometry (VM simulation)');
})().catch(e=>{console.error(e);process.exit(1)});
