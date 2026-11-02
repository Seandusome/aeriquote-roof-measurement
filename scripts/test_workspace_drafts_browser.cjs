// Actual Chromium, synthetic fixture server only. Restore then reuse independent PDF checks.
const fs=require('fs'),assert=require('assert/strict');
process.env.QA_BROWSER_WIDTHS='1440,390';process.env.QA_BROWSER_INDUSTRIES='snow,roofing';
let script=fs.readFileSync('scripts/test_prelaunch_browser.cjs','utf8');
script=script.replace('const page=await context.newPage();','let page=await context.newPage();');
const anchor=" if(industry==='snow'&&width===1440){const frozen";assert(script.includes(anchor));
const preProperty=" await page.fill('#streetAddress','1 Fictional QA Street');";assert(script.includes(preProperty));
script=script.replace(preProperty,`
 if(industry==='snow'&&width===1440){
  await page.click('#customerNotes');await page.fill('#customerNotes','FICTIONAL before property');await page.waitForFunction(()=>!!window.aqRecovery);assert.equal(await page.evaluate(()=>aqRecovery.flush()),true);
  await page.reload();await page.waitForTimeout(1400);
 const draftHttp=[];const classify=url=>{const p=new URL(url).pathname;return p==='/api/estimates'?'estimate-save':p.endsWith('/save-status')?'save-status':p.startsWith('/api/workspace-drafts/')?'draft':null};
 context.on('response',r=>{const family=classify(r.url());if(family)draftHttp.push({event:'response',family,method:r.request().method(),status:r.status()})});context.on('requestfailed',r=>{const family=classify(r.url());if(family)draftHttp.push({event:'failed',family,method:r.method(),reason:r.failure()?.errorText})});
 let cleanupReached,cleanupRelease;const atCleanup=new Promise(r=>cleanupReached=r),holdCleanup=new Promise(r=>cleanupRelease=r);
 if(industry==='snow'&&width===390)await page.route('**/api/workspace-drafts/*',async route=>{if(route.request().method()==='DELETE'){cleanupReached();await holdCleanup}return route.continue()});
 await page.locator('#workspaceRecoveryChoices button').filter({hasText:/^Restore$/}).first().click();
 if(industry==='snow'&&width===390){
  await Promise.race([atCleanup,new Promise((_,reject)=>setTimeout(()=>reject(Error('Restore cleanup not reached')),10000))]);
  assert((await page.locator('#workspaceRecoveryStatus').textContent()).includes('saved for 24 hours'));assert(await page.locator('#workspaceRecoveryChoices').isVisible());
  const earlySnapshot=await page.evaluate(()=>JSON.stringify(captureQuoteSnapshot())),httpStart=draftHttp.length;
  await page.click('#createEstimateBtn');await page.waitForFunction(()=>!estimateOpenInProgress);assert.equal(await page.evaluate(()=>document.body.classList.contains('report-open')),false);assert.equal(await page.evaluate(()=>JSON.stringify(captureQuoteSnapshot())),earlySnapshot);assert((await page.locator('#status').textContent()).includes('retry'));assert(await page.evaluate(()=>!!saveEstimateHistory.pending));assert.equal(draftHttp.slice(httpStart).filter(r=>r.family==='estimate-save'&&r.method==='POST').length,0,'Create before Restore finishes must not send an estimate save');
  console.log('PASS deterministic Restore-cleanup race: early Create retains pending work, emits retry, sends no estimate POST; badge acknowledgement is not completion');cleanupRelease();
 }
 await page.locator('#workspaceRecoveryChoices').waitFor({state:'hidden'});if(industry==='snow'&&width===390)await page.unroute('**/api/workspace-drafts/*');
  await page.waitForFunction(()=>el('workspaceRecoveryStatus').textContent.includes('saved for 24 hours'));
  assert.equal(await page.evaluate(()=>sessionToken),null,'Restoring customer details alone must not load or charge a property');assert.equal(await page.locator('#customerNotes').inputValue(),'FICTIONAL before property');
  console.log('PASS customer/pricing recovery before any property lookup');
 }
`+preProperty);

script=script.replace(anchor,`
 await page.waitForFunction(()=>!!window.aqRecovery);
 assert.equal(await page.evaluate(()=>aqRecovery.flush()),true,'Initial recovery copy acknowledged');
 const firstHeaders=await page.evaluate(()=>aqRecovery.headers());
 const second=await context.newPage();second.on('dialog',d=>d.accept());await second.goto('http://127.0.0.1:8765/?industry='+industry);await second.waitForTimeout(1400);
 await second.getByRole('button',{name:'Start a separate draft'}).click();
 await second.evaluate(token=>{sessionToken=token;areaPoints=[L.latLng(52,-106),L.latLng(52,-105.9999),L.latLng(52.0001,-106)];areaMeasurementSaved=true;measurementViewMode='area';el('customerName').value='FICTIONAL SECOND TAB';},await page.evaluate(()=>sessionToken));
 assert.equal(await second.evaluate(()=>aqRecovery.flush()),true);
 const secondHeaders=await second.evaluate(()=>aqRecovery.headers());assert.notEqual(firstHeaders['X-AeriQuote-Draft'],secondHeaders['X-AeriQuote-Draft']);
 const secondDraft=await(await context.request.get('http://127.0.0.1:8765/api/workspace-drafts/'+secondHeaders['X-AeriQuote-Draft'],{headers:secondHeaders})).json();assert.equal(secondDraft.workspace.values.customerName,'FICTIONAL SECOND TAB');
 const firstDraft=await(await context.request.get('http://127.0.0.1:8765/api/workspace-drafts/'+firstHeaders['X-AeriQuote-Draft'],{headers:firstHeaders})).json();assert.notEqual(firstDraft.workspace.values.customerName,'FICTIONAL SECOND TAB');
 assert.equal((await context.request.delete('http://127.0.0.1:8765/api/workspace-drafts/'+secondHeaders['X-AeriQuote-Draft'],{headers:secondHeaders})).status(),200);
 await second.close();assert.equal((await context.request.get('http://127.0.0.1:8765/api/workspace-drafts/'+firstHeaders['X-AeriQuote-Draft'],{headers:firstHeaders})).status(),200);
 console.log('PASS separate actual tabs, distinct drafts and discard isolation');
 const original=await page.evaluate(()=>({quote:captureQuoteSnapshot(),pricing:priceCalc(),customer:el('customerName').value,email:el('customerEmail').value}));
 const countsBefore=await(await context.request.get('http://127.0.0.1:8765/api/estimates')).json();
 // An interrupted autosave must warn, retain RAM and leave the acknowledged draft intact.
 await page.route('**/api/workspace-drafts/*',r=>r.request().method()==='PUT'?r.abort():r.continue());
 await page.click('#customerNotes');await page.fill('#customerNotes','FICTIONAL interrupted autosave');
 assert.equal(await page.evaluate(()=>aqRecovery.flush()),false);
 assert((await page.locator('#workspaceRecoveryStatus').textContent()).includes('not reached'));
 await page.unroute('**/api/workspace-drafts/*');assert.equal(await page.evaluate(()=>aqRecovery.flush()),true);
 const close=await context.newCDPSession(page);const target=(await close.send('Target.getTargetInfo')).targetInfo.targetId;await close.send('Target.closeTarget',{targetId:target});
 page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
 await page.goto('http://127.0.0.1:8765/?industry='+industry);await page.waitForTimeout(1400);
 await page.locator('#workspaceRecoveryChoices button').filter({hasText:/^Restore$/}).first().click();
 await page.waitForFunction(()=>sessionToken&&el('workspaceRecoveryStatus').textContent.includes('saved for 24 hours'));await page.locator('#workspaceRecoveryChoices').waitFor({state:'hidden'});
 const restored=await page.evaluate(()=>({quote:captureQuoteSnapshot(),pricing:priceCalc(),customer:el('customerName').value,email:el('customerEmail').value}));
 assert.deepEqual(restored,original,'Forced-close Restore must preserve exact geometry, pricing and customer');
 assert.equal(await page.locator('#customerNotes').inputValue(),'FICTIONAL interrupted autosave');
 assert.deepEqual(await(await context.request.get('http://127.0.0.1:8765/api/estimates')).json(),countsBefore,'Restore must create no estimate');
 // Refresh offers the same acknowledged workspace, without automatic save/PDF generation.
 await page.reload();await page.waitForTimeout(1400);
 const draftHttp=[];const classify=url=>{const p=new URL(url).pathname;return p==='/api/estimates'?'estimate-save':p.endsWith('/save-status')?'save-status':p.startsWith('/api/workspace-drafts/')?'draft':null};
 context.on('response',r=>{const family=classify(r.url());if(family)draftHttp.push({event:'response',family,method:r.request().method(),status:r.status()})});context.on('requestfailed',r=>{const family=classify(r.url());if(family)draftHttp.push({event:'failed',family,method:r.method(),reason:r.failure()?.errorText})});
 let cleanupReached,cleanupRelease;const atCleanup=new Promise(r=>cleanupReached=r),holdCleanup=new Promise(r=>cleanupRelease=r);
 if(industry==='snow'&&width===390)await page.route('**/api/workspace-drafts/*',async route=>{if(route.request().method()==='DELETE'){cleanupReached();await holdCleanup}return route.continue()});
 await page.locator('#workspaceRecoveryChoices button').filter({hasText:/^Restore$/}).first().click();
 if(industry==='snow'&&width===390){
  await Promise.race([atCleanup,new Promise((_,reject)=>setTimeout(()=>reject(Error('Restore cleanup not reached')),10000))]);
  assert((await page.locator('#workspaceRecoveryStatus').textContent()).includes('saved for 24 hours'));assert(await page.locator('#workspaceRecoveryChoices').isVisible());
  const earlySnapshot=await page.evaluate(()=>JSON.stringify(captureQuoteSnapshot())),httpStart=draftHttp.length;
  await page.click('#createEstimateBtn');await page.waitForFunction(()=>!estimateOpenInProgress);assert.equal(await page.evaluate(()=>document.body.classList.contains('report-open')),false);assert.equal(await page.evaluate(()=>JSON.stringify(captureQuoteSnapshot())),earlySnapshot);assert((await page.locator('#status').textContent()).includes('retry'));assert(await page.evaluate(()=>!!saveEstimateHistory.pending));assert.equal(draftHttp.slice(httpStart).filter(r=>r.family==='estimate-save'&&r.method==='POST').length,0,'Create before Restore finishes must not send an estimate save');
  console.log('PASS deterministic Restore-cleanup race: early Create retains pending work, emits retry, sends no estimate POST; badge acknowledgement is not completion');cleanupRelease();
 }
 await page.locator('#workspaceRecoveryChoices').waitFor({state:'hidden'});if(industry==='snow'&&width===390)await page.unroute('**/api/workspace-drafts/*');
 await page.waitForFunction(()=>sessionToken&&el('workspaceRecoveryStatus').textContent.includes('saved for 24 hours'));await page.locator('#workspaceRecoveryChoices').waitFor({state:'hidden'});
 assert.deepEqual(await page.evaluate(()=>captureQuoteSnapshot()),original.quote);
 console.log('PASS actual tab closure/refresh, interrupted autosave warning/retry, exact restore without estimate creation',industry,width);
 if(industry==='snow'&&width===1440){
  let committed;
  await page.route('**/api/estimates',async route=>{if(route.request().method()!=='POST')return route.continue();const response=await route.fetch();committed=await response.json();await route.abort();});
  await page.click('#createEstimateBtn');await page.waitForFunction(()=>!estimateOpenInProgress);
  assert(committed?.id,'The server committed before its response was lost');
  assert.equal(await page.evaluate(()=>document.body.classList.contains('report-open')),false);
  assert.equal(await page.evaluate(()=>!!saveEstimateHistory.pending?.id),true,'Retry retains original save operation');
  await page.unroute('**/api/estimates');
  const afterLost=await(await context.request.get('http://127.0.0.1:8765/api/estimates')).json();assert.equal(afterLost.length,countsBefore.length+1);
  console.log('PASS committed save with lost response retains operation for receipt confirmation');
 }

`+anchor);
script=script.replace("if(industry==='snow'&&width===1440){const frozen","if(false){const frozen");
const diagnostic="console.log('CREATE DIAGNOSTIC',await page.evaluate(";assert(script.includes(diagnostic));script=script.replace(diagnostic,"fs.writeFileSync(output+'/'+industry+'-'+width+'-draft-http.json',JSON.stringify(draftHttp,null,2));console.log('DRAFT_HTTP',JSON.stringify(draftHttp));"+diagnostic);
const finish=" await page.screenshot({path:";assert(script.includes(finish));script=script.replace(finish," fs.writeFileSync(output+'/'+industry+'-'+width+'-draft-http.json',JSON.stringify(draftHttp,null,2));\n"+finish);
new Function('require',script)(require);
