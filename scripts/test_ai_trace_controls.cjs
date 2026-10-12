// Test the actual browser functions without paid requests or external packages.
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync('app.py','utf8');
const code=source.slice(source.indexOf('function setAiTraceMessage('),source.indexOf('function reviewAiTrace('));
async function test(response,expected){
 const elements={aiTraceMessage:{textContent:''},aiTraceRunBtn:{disabled:false},aiTraceSurface:{value:'paved'}};
 let timer,cleared=false,request;
 const saved=[{name:'Existing lawn',sqft:1200}];
 const scope={sessionToken:'property',aiTraceBusy:false,aiTraceGeneration:0,areaMode:false,areaPoints:[],linearMode:false,linearPoints:[],aiTraceDrafts:[],commercialAreas:saved,
  map:{getCenter:()=>({lat:52,lng:-106}),getZoom:()=>19},el:id=>elements[id],status:(message)=>scope.message=message,renderAiTraceDrafts:()=>{},AbortController,
  setTimeout:fn=>{timer=fn;return 1},clearTimeout:()=>cleared=true,
  fetch:async(url,options)=>{request=options;if(response==='timeout'){return new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>{const e=new Error();e.name='AbortError';reject(e)}))}return response;}};
 vm.createContext(scope);vm.runInContext(code,scope);
 const pending=scope.runAiTrace();
 assert.equal(elements.aiTraceRunBtn.disabled,true);
 if(response==='timeout')timer();
 await pending;
 assert.equal(scope.aiTraceBusy,false);assert.equal(elements.aiTraceRunBtn.disabled,false);assert(cleared);
 assert(scope.message.includes(expected));assert.equal(elements.aiTraceMessage.textContent,scope.message);
 assert.equal(JSON.parse(request.body).surface,'paved');assert.deepEqual(saved,[{name:'Existing lawn',sqft:1200}]);
 return scope;
}
(async()=>{
 await test('timeout','timed out');
 await test({status:401},'login has expired');
 await test({status:404},'property session has expired');
 await test({status:502,json:async()=>{throw new SyntaxError()}},'unreadable response');
 await test({status:502,ok:false,json:async()=>({user_error:'Check API credits.'})},'Check API credits.');
 await test({status:200,ok:true,json:async()=>({suggestions:[]})},'No clear surface');
 const s=await test({status:200,ok:true,json:async()=>({suggestions:[{points:[[52,-106],[52,-105],[53,-106]]}]})},'Draft outlines');
 s.sessionToken=null;await s.runAiTrace();assert(s.message.includes('Load the property'));
 s.sessionToken='property';s.aiTraceBusy=true;await s.runAiTrace();assert(s.message.includes('already running'));
 s.aiTraceBusy=false;s.areaMode=true;s.areaPoints=[{}];await s.runAiTrace();assert(s.message.includes('Finish and save'));
 for(const file of ['Procfile','render.yaml'])assert(fs.readFileSync(file,'utf8').includes('--workers 1 --threads 4'));
 console.log('PASS: timeout recovery, expired sessions, invalid responses, provider errors, Paving request, draft-only results, visible blockers, single-worker deployment');
})().catch(e=>{console.error(e);process.exitCode=1});
