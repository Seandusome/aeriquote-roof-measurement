// Real recovery client against an exactly-versioned disposable server boundary.
const fs=require('fs'),assert=require('assert/strict'),{JSDOM}=require('jsdom'),vm=require('vm');
const dom=new JSDOM('<meta id="aqAccountId" data-account-id="qa-owner" data-principal="owner:qa-owner">',{runScripts:'outside-only',url:'https://qa.example.invalid'}),w=dom.window;
w.AbortController=AbortController;w.setInterval=()=>0;w.renderSummary=()=>{};
w.qaWorkspace={schema:1,values:{customerName:'FICTIONAL FIRST ACK',customerNotes:'original'},pending:{id:'same-save-operation'},baseVersion:'original-base'};
let row=null,drop=true,requests=[];
w.fetch=async(url,o={})=>{
 if(url==='/api/workspace-drafts')return{ok:true,json:async()=>({drafts:[]})};
 const b=JSON.parse(o.body);requests.push(b);
 if(row&&b.version!==row.version){
  if(JSON.stringify(b.workspace)!==JSON.stringify(row.workspace)||b.version+1!==row.version)return{ok:false,status:409,json:async()=>({error:'Another tab changed this draft'})};
 }else row={version:b.version+1,workspace:b.workspace};
 if(drop){drop=false;throw Error('Response lost after server accepted autosave')}
 return{ok:true,json:async()=>({version:row.version,expires_at:9999999999})};
};
let source=fs.readFileSync(process.env.QA_DRAFT_CLIENT_SOURCE||'workspace_drafts.js','utf8');source=source.slice(0,source.indexOf(' function capture(){'))+' function capture(){return window.qaWorkspace}\n'+source.slice(source.indexOf(' async function request('));vm.runInContext(source,dom.getInternalVMContext());
(async()=>{
 await new Promise(r=>setImmediate(r));const r=w.aqRecovery;
 assert.equal(await r.flush(),false);assert.equal(row.workspace.values.customerNotes,'original');const first=requests[0];
 w.qaWorkspace={...w.qaWorkspace,values:{...w.qaWorkspace.values,customerNotes:'FICTIONAL LATER EDIT AFTER LOST ACK'}};
 assert.equal(await r.flush(),true,'Later edits must recover after an accepted autosave loses its acknowledgement');
 assert.deepEqual(requests[1],first,'Resolve uncertain autosave with its exact original version/payload before sending later edits');
 assert.equal(row.workspace.values.customerNotes,'FICTIONAL LATER EDIT AFTER LOST ACK');assert.equal(row.version,2);assert.equal(row.workspace.pending.id,'same-save-operation');assert.equal(row.workspace.baseVersion,'original-base');assert(w.document.getElementById('workspaceRecoveryStatus').textContent.includes('saved for 24 hours'));
 const acknowledged=JSON.parse(JSON.stringify(w.qaWorkspace));drop=true;w.qaWorkspace={...w.qaWorkspace,values:{...w.qaWorkspace.values,customerNotes:'FICTIONAL UNCERTAIN EDIT THEN REVERT'}};
 assert.equal(await r.flush(),false);assert.equal(row.version,3);
 w.qaWorkspace=acknowledged;assert.equal(await r.flush(),true);assert.deepEqual(row.workspace,acknowledged,'Reverting locally to the last acknowledged state must still reconcile the intervening uncertain server write');assert.equal(row.version,4);
 dom.window.close();console.log('PASS: lost autosave response followed by later edits confirms exact uncertain write first, then acknowledges newest work without stale overwrite');
})().catch(e=>{dom.window.close();console.error(e);process.exit(1)});
