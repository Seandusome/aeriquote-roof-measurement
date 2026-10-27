// Real local Chromium dialog/session tests only. The fixture server is mandatory; never production.
const fs=require('fs'),assert=require('assert/strict');
process.env.QA_BROWSER_WIDTHS='390';process.env.QA_BROWSER_INDUSTRIES='snow';process.env.QA_BROWSER_IMAGES='none';
let script=fs.readFileSync('scripts/test_prelaunch_browser.cjs','utf8');
const anchor=" if(industry==='snow'&&width===1440){";
assert(script.includes(anchor));
const injection=`
 const originalDraft=await page.evaluate(()=>JSON.stringify(captureQuoteSnapshot()));
 const originalCustomer=await page.locator('#customerName').inputValue();
 page.removeAllListeners('dialog');let warnings=0;
 page.on('dialog',async dialog=>{if(dialog.type()==='beforeunload'){warnings++;await dialog.dismiss()}else await dialog.accept()});
 await page.reload({timeout:2000}).catch(()=>{});
 assert.equal(warnings,1,'Unsaved refresh must ask before discarding');
 assert.equal(await page.evaluate(()=>JSON.stringify(captureQuoteSnapshot())),originalDraft);
 await page.evaluate(()=>window.location.assign('/site/'));await page.waitForTimeout(150);
 assert.equal(warnings,2,'Accidental navigation must ask');assert.equal(await page.locator('#customerName').inputValue(),originalCustomer);

 assert.equal(await page.evaluate(()=>JSON.stringify(captureQuoteSnapshot())),originalDraft);
 console.log('PASS real Chromium refresh/navigation warnings; dismiss preserves exact draft/customer');
 console.log('BEFORE EXPIRY',await page.evaluate(()=>({image:el('streetViewChoice').value,status:el('status').textContent})));
 // Expire the shared cookie while leaving the original page untouched.
 await context.request.get('http://127.0.0.1:8765/logout');
 await page.click('#createEstimateBtn');await page.waitForFunction(()=>!estimateOpenInProgress,{},{timeout:35000}).catch(async e=>{console.log('RECOVERY DEBUG',await page.evaluate(()=>({image:el('streetViewChoice').value,inProgress:estimateOpenInProgress,saving:!!saveEstimateHistory.inFlight,pending:!!saveEstimateHistory.pending,status:el('status').textContent})));throw e});
 assert((await page.locator('#status').textContent()).includes('login expired'),await page.locator('#status').textContent());
 assert.equal(await page.evaluate(()=>document.body.classList.contains('report-open')),false);
 assert.equal(await page.evaluate(()=>JSON.stringify(captureQuoteSnapshot())),originalDraft);
 await context.request.post('http://127.0.0.1:8765/dealer-login',{form:{email:'qa-other@example.invalid',password:'fictional-qa-password'}});
 const otherPage=await context.newPage();await otherPage.route('**/api/account/profile',route=>route.abort());await otherPage.goto('http://127.0.0.1:8765/?industry=snow');await otherPage.waitForFunction(()=>typeof prepareAccountBrandingCache==='function');
 assert.equal(await otherPage.locator('#aqAccountId').getAttribute('data-account-id'),'qa-browser-other');
 assert.notEqual(await otherPage.locator('#dealerCompany').inputValue(),'FICTIONAL QA COMPANY','Failed profile load cannot show the previous business cache');await otherPage.close();
 console.log('PASS real workspace clears previous-business branding before profile hydration');

 await page.click('#createEstimateBtn');await page.waitForFunction(()=>!estimateOpenInProgress,{},{timeout:35000}).catch(async e=>{console.log('RECOVERY DEBUG',await page.evaluate(()=>({image:el('streetViewChoice').value,inProgress:estimateOpenInProgress,saving:!!saveEstimateHistory.inFlight,pending:!!saveEstimateHistory.pending,status:el('status').textContent})));throw e});
 assert((await page.locator('#status').textContent()).includes('another business'));
 assert.equal(await page.evaluate(()=>document.body.classList.contains('report-open')),false);
 const otherEstimates=await(await context.request.get('http://127.0.0.1:8765/api/estimates')).json();assert.equal(otherEstimates.length,0);
 assert.equal(await page.evaluate(()=>JSON.stringify(captureQuoteSnapshot())),originalDraft);
 await context.request.post('http://127.0.0.1:8765/dealer-login',{form:{email:'qa-browser@example.invalid',password:'fictional-qa-password'}});
 console.log('PASS real Chromium expired session + wrong-business re-login retain draft, block report and write no foreign estimate; original account restored');
`;
script=script.replace(anchor,injection+" if(false){");
// After the ordinary successful save/reopen, simulate a forced discard of a separate unsaved tab.
const finish=" await page.screenshot({path:";
assert(script.includes(finish));
script=script.replace(finish,`
 const discarded=await context.newPage();await discarded.goto('http://127.0.0.1:8765/?industry=snow');await discarded.waitForFunction(()=>typeof captureQuoteSnapshot==='function');
 await discarded.waitForTimeout(1100); // Let initial anti-autofill/reset timers finish before creating this draft.
 // This fixture deliberately supplies browser memory that has never been saved.
 await discarded.evaluate(()=>{sessionToken='FICTIONAL-UNSAVED';areaPoints=[L.latLng(52,-106),L.latLng(52,-105.9999),L.latLng(52.0001,-106)];el('customerName').value='UNSAVED DISCARD QA';});
 let closeWarnings=0;discarded.on('dialog',async d=>{closeWarnings++;await d.dismiss()});await discarded.locator('#streetAddress').click();await discarded.close({runBeforeUnload:true});await discarded.waitForTimeout(150);assert.equal(closeWarnings,1);assert.equal(discarded.isClosed(),false);assert.equal(await discarded.locator('#customerName').inputValue(),'UNSAVED DISCARD QA');const forceSession=await context.newCDPSession(discarded);const forcedTarget=(await forceSession.send('Target.getTargetInfo')).targetInfo.targetId;await forceSession.send('Target.closeTarget',{targetId:forcedTarget});
 const replacement=await context.newPage();await replacement.goto('http://127.0.0.1:8765/?industry=snow');await replacement.waitForFunction(()=>typeof captureQuoteSnapshot==='function');
 assert.equal(await replacement.evaluate(()=>areaPoints.length+linearPoints.length+manualPlanes.length),0,'There is no crash/forced-discard draft autosave');
 const history=await(await context.request.get('http://127.0.0.1:8765/api/estimates')).json();assert.equal(history.length,1,'Only explicit successful estimate exists; discarded draft creates no revision');
 await replacement.close();console.log('CONFIRMED LIMITATION: forced tab close bypasses warning and unsaved geometry is not restored; explicit saved estimate survives');
`+finish);
new Function('require',script)(require);
