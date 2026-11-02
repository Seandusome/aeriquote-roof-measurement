// Distinct desktop race cases on the disposable loopback fixture only.
const fs=require('fs'),assert=require('assert/strict');
process.env.QA_BROWSER_WIDTHS='1440';process.env.QA_BROWSER_INDUSTRIES='snow';process.env.QA_BROWSER_IMAGES='none';
let script=fs.readFileSync('scripts/test_prelaunch_browser.cjs','utf8');
const anchor=" if(industry==='snow'&&width===1440){const frozen";assert(script.includes(anchor));
script=script.replace(anchor,String.raw`
 assert.equal(await page.evaluate(()=>aqRecovery.flush()),true);
 const raceHeaders=await page.evaluate(()=>aqRecovery.headers()),raceSource=raceHeaders['X-AeriQuote-Draft'];
 const raceOld=(await(await context.request.get('http://127.0.0.1:8765/api/workspace-drafts/'+raceSource,{headers:raceHeaders})).json()).workspace;
 const raceOther=await context.newPage();raceOther.on('dialog',d=>d.accept());await raceOther.goto('http://127.0.0.1:8765/');await raceOther.waitForTimeout(1200);
 let raceReached,raceRelease;const raceAtCleanup=new Promise(r=>raceReached=r),raceHold=new Promise(r=>raceRelease=r);
 await raceOther.route('**/api/workspace-drafts/'+raceSource,async route=>{if(route.request().method()==='DELETE'){raceReached();await raceHold}return route.continue()});
 await raceOther.getByRole('button',{name:'Restore',exact:true}).click();
 await Promise.race([raceAtCleanup,new Promise((_,reject)=>setTimeout(()=>reject(Error('Restore cleanup was never reached')),15000))]);
 await page.click('#customerNotes');await page.fill('#customerNotes','FICTIONAL NEWER ACK WHILE OTHER TAB RESTORES');assert.equal(await page.evaluate(()=>aqRecovery.flush()),true);
 raceRelease();await raceOther.waitForFunction(()=>el('workspaceRecoveryStatus').textContent.includes('Newer work from another tab was kept separately.'));
 const raceKept=await(await context.request.get('http://127.0.0.1:8765/api/workspace-drafts/'+raceSource,{headers:raceHeaders})).json();assert.equal(raceKept.workspace.values.customerNotes,'FICTIONAL NEWER ACK WHILE OTHER TAB RESTORES');
 const raceCopyHeaders=await raceOther.evaluate(()=>aqRecovery.headers());const raceCopy=await(await context.request.get('http://127.0.0.1:8765/api/workspace-drafts/'+raceCopyHeaders['X-AeriQuote-Draft'],{headers:raceCopyHeaders})).json();assert.deepEqual(raceCopy.workspace.values,raceOld.values);
 console.log('PASS actual delayed Restore cleanup retains both original newer acknowledgement and the copied older snapshot');
 // Another tab discards/consumes the source. Later edits must stay in RAM; only
 // an explicit Create may acknowledge a new tab-specific copy and save them.
 await context.request.delete('http://127.0.0.1:8765/api/workspace-drafts/'+raceSource,{headers:raceHeaders});
 await page.fill('#customerNotes','FICTIONAL LATER EDIT AFTER REMOTE DISCARD');assert.equal(await page.evaluate(()=>aqRecovery.flush()),false);
 assert.equal(await page.evaluate(()=>aqRecovery.headers()['X-AeriQuote-Draft']),raceSource);
 assert.equal((await context.request.get('http://127.0.0.1:8765/api/workspace-drafts/'+raceSource,{headers:raceHeaders})).status(),404);
`+anchor);
script=script.replace("if(industry==='snow'&&width===1440){const frozen","if(false){const frozen");
const after=" // A second page load simulates refresh; reopen the owned stored snapshot through the actual handler.";assert(script.includes(after));
script=script.replace(after,String.raw`
 assert.equal(payload.customer_notes,'FICTIONAL LATER EDIT AFTER REMOTE DISCARD');assert.notEqual(await page.evaluate(()=>aqRecovery.headers()['X-AeriQuote-Draft']),raceSource);
 await context.request.delete('http://127.0.0.1:8765/api/workspace-drafts/'+raceCopyHeaders['X-AeriQuote-Draft'],{headers:raceCopyHeaders});await raceOther.close();
 console.log('PASS explicit Create after a remotely closed recovery ID retains the exact later edit and saves successfully');
 const raceEditors=[];
 for(let n=0;n<2;n++){
  const editor=await context.newPage();editor.on('dialog',d=>d.accept());editor.on('pageerror',e=>errors.push(e.message));await editor.goto('http://127.0.0.1:8765/');await editor.waitForFunction(()=>typeof openHistoricalEstimate==='function');await editor.waitForTimeout(1000);await editor.waitForFunction(()=>el('workspaceRecoveryStatus')?.textContent);if(await editor.getByRole('button',{name:'Start a separate draft'}).count())await editor.getByRole('button',{name:'Start a separate draft'}).click();
  await editor.evaluate(id=>openHistoricalEstimate(id,-1),saved.id);await editor.getByRole('button',{name:'EDIT MEASUREMENTS / PRICE',exact:true}).click();
  await editor.waitForFunction(()=>sessionToken&&!savedEstimateEditContext&&!document.body.classList.contains('report-open'));
  await editor.click('#customerNotes');await editor.fill('#customerNotes','FICTIONAL CONCURRENT EDITOR '+n);raceEditors.push(editor);
 }
 const raceVersions=async()=>await(await context.request.get('http://127.0.0.1:8765/api/estimates/'+saved.id+'/versions')).json();
 const raceBefore=(await raceVersions()).revisions.length;
 await raceEditors[0].click('#createEstimateBtn');await raceEditors[0].waitForFunction(()=>document.body.classList.contains('report-open'));
 assert.equal((await raceVersions()).revisions.length,raceBefore+1);
 await raceEditors[1].click('#createEstimateBtn');await raceEditors[1].waitForFunction(()=>!estimateOpenInProgress);
 assert.equal(await raceEditors[1].evaluate(()=>saveEstimateHistory.lastFailureStatus),409);
 assert.equal(await raceEditors[1].locator('#customerNotes').inputValue(),'FICTIONAL CONCURRENT EDITOR 1');
 assert.equal((await raceVersions()).revisions.length,raceBefore+1,'Stale second editor must not add another revision');
 assert.equal((await raceVersions()).current.payload.customer_notes,'FICTIONAL CONCURRENT EDITOR 0');
 const staleHeaders=await raceEditors[1].evaluate(()=>aqRecovery.headers());const staleDraft=await(await context.request.get('http://127.0.0.1:8765/api/workspace-drafts/'+staleHeaders['X-AeriQuote-Draft'],{headers:staleHeaders})).json();assert.equal(staleDraft.workspace.values.customerNotes,'FICTIONAL CONCURRENT EDITOR 1');assert(staleDraft.workspace.baseVersion);
 await context.request.delete('http://127.0.0.1:8765/api/workspace-drafts/'+staleHeaders['X-AeriQuote-Draft'],{headers:staleHeaders});for(const e of raceEditors)await e.close();
 console.log('PASS actual concurrent saved editors: first save succeeds once, stale second save409 retains its acknowledged workspace and original base version');
`+after);

// Different interruption: server accepts the PUT, but its successful response is
// replaced with unreadable acknowledgement data. Never announce durability early.
const firstFlush=" assert.equal(await page.evaluate(()=>aqRecovery.flush()),true);";assert(script.includes(firstFlush));
script=script.replace(firstFlush,String.raw`
 await page.route('**/api/workspace-drafts/*',async route=>{if(route.request().method()!=='PUT')return route.continue();const accepted=await route.fetch();assert.equal(accepted.status(),200);return route.fulfill({status:200,contentType:'application/json',body:'{}'})});
 assert.equal(await page.evaluate(()=>aqRecovery.flush()),false);
 assert((await page.locator('#workspaceRecoveryStatus').textContent()).includes('have not reached'));
 const interruptedHeaders=await page.evaluate(()=>aqRecovery.headers());const acceptedDraft=await(await context.request.get('http://127.0.0.1:8765/api/workspace-drafts/'+interruptedHeaders['X-AeriQuote-Draft'],{headers:interruptedHeaders})).json();
 assert.equal(acceptedDraft.workspace.values.customerName,await page.locator('#customerName').inputValue());
 await page.click('#customerNotes');await page.fill('#customerNotes','FICTIONAL EDIT AFTER ACCEPTED AUTOSAVE LOST ACK');
 await page.unroute('**/api/workspace-drafts/*');
 console.log('PASS accepted autosave with malformed acknowledgement retains server copy and visible unsaved warning; identical retry recovers');
`+firstFlush);
const firstCreate=" await page.click('#createEstimateBtn');await page.waitForFunction(()=>document.body.classList.contains('report-open'),{timeout:10000})";assert(script.includes(firstCreate));
script=script.replace(firstCreate,String.raw`
 let acceptedSave,savePosts=0;
 await page.route('**/api/estimates',async route=>{if(route.request().method()!=='POST')return route.continue();savePosts++;const response=await route.fetch();assert.equal(response.status(),200);acceptedSave=await response.json();return route.fulfill({status:200,contentType:'application/json',body:'{"id":'})});
 const uncertainSnapshot=await page.evaluate(()=>JSON.stringify(captureQuoteSnapshot()));
 await page.click('#createEstimateBtn');await page.waitForFunction(()=>!estimateOpenInProgress);
 assert.equal(await page.evaluate(()=>document.body.classList.contains('report-open')),false);
 assert.equal(await page.evaluate(()=>JSON.stringify(captureQuoteSnapshot())),uncertainSnapshot);
 assert(await page.evaluate(()=>!!saveEstimateHistory.pending?.payload));assert((await page.locator('#status').textContent()).includes('retry'));
 const acceptedVersions=await(await context.request.get('http://127.0.0.1:8765/api/estimates/'+acceptedSave.id+'/versions')).json();
 assert.equal(acceptedVersions.revisions.length,0);
 await page.unroute('**/api/estimates');
`+firstCreate);
const reportOpened=" console.log('report opened');";assert(script.includes(reportOpened));
script=script.replace(reportOpened,String.raw`
 assert.equal(savePosts,1);const confirmedVersions=await(await context.request.get('http://127.0.0.1:8765/api/estimates/'+acceptedSave.id+'/versions')).json();assert.equal(confirmedVersions.revisions.length,0);assert.equal(confirmedVersions.current.id,acceptedSave.id);
 assert.equal(await page.evaluate(()=>saveEstimateHistory.pending),null);
 console.log('PASS committed save with truncated HTTP200 blocks report, keeps exact work, confirms original receipt on retry without another revision');
`+reportOpened);
new Function('require',script)(require);

