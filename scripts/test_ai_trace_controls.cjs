// Test the actual browser functions without paid requests or external packages.
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync('app.py','utf8');
const code=source.slice(source.indexOf('function setAiTraceMessage('),source.indexOf('function reviewAiTrace('));
async function test(response,expected){
 const elements={aiTraceMessage:{textContent:''},aiTraceRunBtn:{disabled:false},aiTraceSurface:{value:'paved'}};
 let timer,cleared=false,request;
 const saved=[{name:'Existing lawn',sqft:1200}];
 const scope={sessionToken:'property',aiTraceSeed:{lat:52,lng:-106},aiTracePickMode:false,aiTraceRequestView:()=>({centre:{lat:52,lng:-106},zoom:18,scope:[.1,.1,.9,.9],seed:[.5,.5]}),aiTraceBusy:false,aiTraceGeneration:0,aiTraceDraftSequence:0,areaMode:false,areaPoints:[],linearMode:false,linearPoints:[],aiTraceDrafts:[],commercialAreas:saved,
  map:{getCenter:()=>({lat:52,lng:-106}),getZoom:()=>19},el:id=>elements[id],status:(message)=>scope.message=message,startAiTracePick:()=>scope.message="Click inside the surface",renderAiTraceDrafts:()=>{},renderAiTracePreview:()=>{},AbortController,
  setTimeout:fn=>{timer=fn;return 1},clearTimeout:()=>cleared=true,
  fetch:async(url,options)=>{request=options;if(response==='timeout'){return new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>{const e=new Error();e.name='AbortError';reject(e)}))}return response;}};
 vm.createContext(scope);vm.runInContext(code,scope);
 const pending=scope.runAiTrace();
 assert.equal(elements.aiTraceRunBtn.disabled,true);
 if(response==='timeout')timer();
 await pending;
 assert.equal(scope.aiTraceBusy,false);assert.equal(elements.aiTraceRunBtn.disabled,false);assert(cleared);
 assert(scope.message.includes(expected));assert.equal(elements.aiTraceMessage.textContent,scope.message);
 assert.equal(JSON.parse(request.body).surface,'paved');assert.equal(JSON.parse(request.body).zoom,18);assert.deepEqual(JSON.parse(request.body).scope,[.1,.1,.9,.9]);assert.deepEqual(JSON.parse(request.body).seed,[.5,.5]);assert.deepEqual(saved,[{name:'Existing lawn',sqft:1200}]);
 return scope;
}
function testExactImagePreview(){
 const make=()=>({style:{},attrs:{},children:[],setAttribute(k,v){this.attrs[k]=v},appendChild(n){this.children.push(n)}});
 const elements={aiTracePreview:make(),aiTraceComparison:make()};
 const scope={el:id=>elements[id],document:{createElementNS:()=>make()}};vm.createContext(scope);
 vm.runInContext(source.slice(source.indexOf('function renderAiTracePreview('),source.indexOf('function setAiTraceMessage(')),scope);
 const drafts=[{name:'Grass',image_points:[[160,160],[480,160],[480,480],[160,480]],points:[[52,-106],[52,-105],[53,-106]]}];
 const before=JSON.stringify(drafts);scope.renderAiTracePreview('data:image/png;base64,cG5n',drafts);
 const svg=elements.aiTracePreview.children[0];assert.equal(svg.attrs.viewBox,'0 0 640 640');assert.equal(svg.children[0].attrs.href,'data:image/png;base64,cG5n');assert.equal(svg.children[1].attrs.points,'160,160 480,160 480,480 160,480');assert.equal(JSON.stringify(drafts),before);assert.equal(elements.aiTraceComparison.style.display,'block');
 scope.renderAiTracePreview('https://external.invalid/image',drafts);assert.equal(elements.aiTraceComparison.style.display,'none');
 console.log('PASS: exact cached image and original AI pixel corners are displayed without map reprojection, new requests or draft changes');
}
(async()=>{
 testExactImagePreview();
 await test('timeout','timed out');
 await test({status:401},'login has expired');
 await test({status:404},'property session has expired');
 await test({status:502,json:async()=>{throw new SyntaxError()}},'unreadable response');
 await test({status:502,ok:false,json:async()=>({user_error:'Check API credits.'})},'Check API credits.');
 await test({status:200,ok:true,json:async()=>({suggestions:[]})},'No clear surface');
 const s=await test({status:200,ok:true,json:async()=>({suggestions:[{points:[[52,-106],[52,-105],[53,-106]]}]})},'draft outline');
 s.sessionToken=null;await s.runAiTrace();assert(s.message.includes('Load the property'));
 s.sessionToken='property';s.aiTraceBusy=true;await s.runAiTrace();assert(s.message.includes('already running'));
 s.aiTraceBusy=false;s.aiTraceSeed=null;await s.runAiTrace();assert(s.message.includes('Click inside'));s.aiTraceSeed={};s.areaMode=true;s.areaPoints=[{}];await s.runAiTrace();assert(s.message.includes('Finish and save'));
 for(const file of ['Procfile','render.yaml'])assert(fs.readFileSync(file,'utf8').includes('--workers 1 --threads 4'));
 console.log('PASS: timeout recovery, expired sessions, invalid responses, provider errors, Paving request, draft-only results, visible blockers, single-worker deployment');
})().catch(e=>{console.error(e);process.exitCode=1});
