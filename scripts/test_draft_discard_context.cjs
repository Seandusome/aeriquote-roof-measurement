// Deterministic DOM simulation, not Chromium or physical-device verification.
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict'),{JSDOM}=require('jsdom');
const source=fs.readFileSync(process.env.QA_DRAFT_CLIENT_SOURCE||'workspace_drafts.js','utf8');
const tick=async()=>{for(let i=0;i<5;i++)await new Promise(r=>setImmediate(r))};
async function setup({expired=false}={}){
 const dom=new JSDOM('<meta id="aqAccountId" data-account-id="fictional-A" data-principal="owner:fictional-A">',{runScripts:'outside-only',url:'https://qa.example.invalid'}),w=dom.window;
 let clock=Date.now(),serial=0,current='fictional-A',principal='owner:fictional-A',failure=0,lost=false;
 const row={draft_id:'fictional-source-draft-0001',version:1,expires_at:clock/1000+(expired?-10:60)};
 const state={version:1,closed:false,workspace:{values:{address:'1 Fictional QA Street',customerName:'FICTIONAL SOURCE'}}};
 const intervals=[];w.Date.now=()=>clock;w.setInterval=f=>{intervals.push(f);return intervals.length};w.AbortController=AbortController;
 Object.defineProperty(w.crypto,'randomUUID',{value:()=>`fictional-tab-id-${++serial}-000000`});
 w.structures=[];w.manualPlanes=[];w.tracePoints=[];w.renderSummary=()=>{};
 w.qaWorkspace={schema:1,values:{customerName:'FICTIONAL CURRENT',customerNotes:'Preserve exact current notes'},quote:{points:[[0,0],[0,1],[1,1]],rate:1.23,pitch:26.565}};
 w.fetch=async(url,options={})=>{
  const response=(status,data)=>({ok:status<400,status,headers:{get:()=> 'application/json'},json:async()=>data});
  if(failure)return response(failure,{error:failure===401?'Your login expired.':'Temporary server failure.'});
  if(options.headers['X-AeriQuote-Account']!==current)return response(409,{code:'draft_account_context',error:"This tab's saved account context does not match the current login. No draft was changed."});
  if(options.headers['X-AeriQuote-Principal']!==principal)return response(409,{code:'draft_user_context',error:"This tab's user context does not match the current login."});
  if(url==='/api/workspace-drafts')return response(200,{drafts:[{...row}],server_time:clock/1000});
  if(options.method==='PUT'){const body=JSON.parse(options.body);return response(200,{version:body.version+1,expires_at:clock/1000+86400})}
  if(options.method==='DELETE'){
   const body=JSON.parse(options.body||'{}');
   if(body.version!==undefined&&body.version!==state.version)return response(409,{code:'draft_changed',error:'Newer saved work was kept.'});
   state.closed=true;if(lost){lost=false;throw new Error('Fictional lost response')}
   return response(200,{deleted:true});
  }
  return response(200,{...row,version:state.version,workspace:state.workspace});
 };
 const script=source.slice(0,source.indexOf(' function capture(){'))+' function capture(){return window.qaWorkspace}\n'+source.slice(source.indexOf(' async function request('));
 vm.runInContext(script,dom.getInternalVMContext());await tick();
 return {dom,w,row,state,intervals,advance:ms=>clock+=ms,account:x=>current=x,user:x=>principal=x,fail:x=>failure=x,lose:()=>lost=true,
  discard:()=>[...w.document.querySelectorAll('button')].find(e=>e.textContent==='Discard'),message:()=>w.document.body.textContent};
}
(async()=>{
 if(process.env.QA_EXPECT_BASELINE==='1'){
  const a=await setup({expired:true});assert(a.discard(),'baseline shows already-expired choice');a.dom.window.close();
  const b=await setup();b.state.version=2;await b.discard().onclick();assert(b.state.closed,'baseline unversioned discard erases newer fictional draft');b.dom.window.close();
  const c=await setup();await c.w.aqRecovery.flush();const id=c.w.aqRecovery.headers()['X-AeriQuote-Draft'];await c.discard().onclick();assert.notEqual(c.w.aqRecovery.headers()['X-AeriQuote-Draft'],id,'baseline discarding old choice rotates current draft ID');c.dom.window.close();
  console.log('REPRODUCED baseline: already-expired choices visible, unversioned discard consumes newer saved draft, and current draft ID rotates. Same source hash on deployed 80dc173 and e5bebda.');return;
 }
 let count=0;
 const initial=await setup({expired:true});assert(!initial.discard());initial.dom.window.close();count++;
 const timed=await setup();const work=JSON.stringify(timed.w.qaWorkspace);timed.advance(61000);timed.w.dispatchEvent(new timed.w.Event('pageshow'));assert(!timed.discard());assert.equal(JSON.stringify(timed.w.qaWorkspace),work);assert(!timed.state.closed);timed.dom.window.close();count++;
 const normal=await setup();await normal.w.aqRecovery.flush();const originalId=normal.w.aqRecovery.headers()['X-AeriQuote-Draft'];const originalWork=JSON.stringify(normal.w.qaWorkspace);await normal.discard().onclick();assert(normal.state.closed);assert.equal(normal.w.aqRecovery.headers()['X-AeriQuote-Draft'],originalId);assert.equal(JSON.stringify(normal.w.qaWorkspace),originalWork);normal.dom.window.close();count++;
 const race=await setup();race.state.version=2;race.state.workspace.values.customerName='FICTIONAL NEWER';await race.discard().onclick();assert(!race.state.closed);assert(race.message().includes('Draft was not discarded.'));assert(race.message().includes('refreshed'));await race.discard().onclick();assert(race.state.closed);race.dom.window.close();count++;
 for(const status of [401,503]){const f=await setup();f.fail(status);await f.discard().onclick();assert(!f.state.closed);assert(!f.discard().disabled);assert(f.message().includes('Draft was not discarded.'));assert(!f.message().includes('Changes have not reached the server.'));f.fail(0);await f.discard().onclick();assert(f.state.closed);f.dom.window.close();count++}
 for(const kind of ['account','user']){const f=await setup();const before=JSON.stringify(f.w.qaWorkspace);if(kind==='account')f.account('fictional-B');else f.user('employee:fictional-employee');await f.discard().onclick();assert(!f.state.closed);assert(f.message().includes('context does not match'));assert.equal(JSON.stringify(f.w.qaWorkspace),before);f.account('fictional-A');f.user('owner:fictional-A');await f.discard().onclick();assert(f.state.closed);f.dom.window.close();count++}
 const lost=await setup();lost.lose();await lost.discard().onclick();assert(lost.state.closed);assert(lost.discard());await lost.discard().onclick();assert(!lost.discard());lost.dom.window.close();count++;
 console.log('PASS '+count+' DOM scenarios: expired on entry, expiry/pageshow, current work/ID preservation, stale version, 401/503 retry, account/principal changes and lost discard acknowledgement. Fictional controlled boundary, not browser/device verification.');
})().catch(e=>{console.error(e);process.exitCode=1});
