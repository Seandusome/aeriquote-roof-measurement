// Real recovery queue/actions with a controlled authenticated server boundary.
const fs=require('fs'),assert=require('assert/strict'),{JSDOM}=require('jsdom'),vm=require('vm');
const dom=new JSDOM('<meta id="aqAccountId" data-account-id="qa-owner" data-principal="owner:qa-owner">',{runScripts:'outside-only',url:'https://qa.example.invalid'}),w=dom.window;
let serial=0,mode='',badAck=false,closed=new Set(),rows=new Map(),writes=0;
Object.defineProperty(w.crypto,'randomUUID',{value:()=>`fictional-qa-tab-${String(++serial).padStart(5,'0')}`});
w.AbortController=AbortController;w.setInterval=()=>0;w.renderSummary=()=>{};
w.qaWorkspace={schema:1,values:{customerName:'FICTIONAL ORIGINAL'},pending:{id:'same-save-operation'},baseVersion:'same-stale-edit-guard'};
w.fetch=async(url,options={})=>{
 if(url==='/api/workspace-drafts')return{ok:true,json:async()=>({drafts:[]})};
 const id=url.split('/').at(-1);
 assert.equal(options.headers['X-AeriQuote-Principal'],'owner:qa-owner');
 if(mode)return{ok:false,status:409,json:async()=>({error:mode})};
 if(closed.has(id))return{ok:false,status:409,json:async()=>({error:'Draft closed',code:'draft_closed'})};
 const body=JSON.parse(options.body);rows.set(id,body.workspace);writes++;
 if(badAck)return{ok:true,json:async()=>({})};
 return{ok:true,json:async()=>({version:body.version+1,expires_at:9999999999})};
};
let source=fs.readFileSync(process.env.QA_DRAFT_CLIENT_SOURCE||'workspace_drafts.js','utf8');
source=source.slice(0,source.indexOf(' function capture(){'))+' function capture(){return window.qaWorkspace}\n'+source.slice(source.indexOf(' async function request('));
vm.runInContext(source,dom.getInternalVMContext());
(async()=>{
 await new Promise(resolve=>setImmediate(resolve));const recovery=w.aqRecovery;
 badAck=true;assert.equal(await recovery.flush(),false,'Malformed autosave acknowledgement must not claim recovery is saved');assert(w.document.getElementById('workspaceRecoveryStatus').textContent.includes('have not reached'));
 badAck=false;assert.equal(await recovery.flush(),true);const first=recovery.headers()['X-AeriQuote-Draft'];closed.add(first);
 w.qaWorkspace={...w.qaWorkspace,values:{customerName:'FICTIONAL LATER EDIT'}};
 const initialWrites=writes;
 assert.equal(await recovery.flush(),false);assert.equal(recovery.headers()['X-AeriQuote-Draft'],first);assert.equal(writes,initialWrites,'Background retry must not resurrect a consumed/discarded draft');
 const save=()=>recovery.prepareSave?recovery.prepareSave():recovery.flush();
 assert.equal(await save(),true,'Explicit Create must be able to preserve later edits after another tab consumed the original recovery ID');
 const second=recovery.headers()['X-AeriQuote-Draft'];assert.notEqual(second,first);assert.deepEqual(rows.get(second),w.qaWorkspace);
 assert.equal(rows.get(second).pending.id,'same-save-operation');assert.equal(rows.get(second).baseVersion,'same-stale-edit-guard');
 for(const error of ['Sign in to the original user account','Another tab changed this recovery version']){
  mode=error;w.qaWorkspace={...w.qaWorkspace,values:{customerName:'FICTIONAL UNSAVED '+error}};
  const before=writes,identifier=recovery.headers()['X-AeriQuote-Draft'];assert.equal(await save(),false);assert.equal(recovery.headers()['X-AeriQuote-Draft'],identifier);assert.equal(writes,before,'Account/stale-version conflicts must never be silently forked');
 }
 dom.window.close();console.log('PASS: explicit save recovers from a consumed draft ID, background autosave never resurrects it, exact operation/base version retained, account and stale-edit conflicts stay blocked');
})().catch(e=>{dom.window.close();console.error(e);process.exit(1)});
