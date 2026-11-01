// Actual Chromium, synthetic fixture server only. Restore then reuse independent PDF checks.
const fs=require('fs'),assert=require('assert/strict');
process.env.QA_BROWSER_WIDTHS='1440,390';process.env.QA_BROWSER_INDUSTRIES='snow,roofing';
let script=fs.readFileSync('scripts/test_prelaunch_browser.cjs','utf8');
script=script.replace('const page=await context.newPage();','let page=await context.newPage();');
const anchor=" if(industry==='snow'&&width===1440){";assert(script.includes(anchor));
script=script.replace(anchor,`
 await page.waitForFunction(()=>!!window.aqRecovery);
 assert.equal(await page.evaluate(()=>aqRecovery.flush()),true,'Initial recovery copy acknowledged');
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
 await page.waitForFunction(()=>sessionToken&&el('workspaceRecoveryStatus').textContent.includes('saved for 24 hours'));
 const restored=await page.evaluate(()=>({quote:captureQuoteSnapshot(),pricing:priceCalc(),customer:el('customerName').value,email:el('customerEmail').value}));
 assert.deepEqual(restored,original,'Forced-close Restore must preserve exact geometry, pricing and customer');
 assert.equal(await page.locator('#customerNotes').inputValue(),'FICTIONAL interrupted autosave');
 assert.deepEqual(await(await context.request.get('http://127.0.0.1:8765/api/estimates')).json(),countsBefore,'Restore must create no estimate');
 // Refresh offers the same acknowledged workspace, without automatic save/PDF generation.
 await page.reload();await page.waitForTimeout(1400);await page.locator('#workspaceRecoveryChoices button').filter({hasText:/^Restore$/}).first().click();
 await page.waitForFunction(()=>sessionToken&&el('workspaceRecoveryStatus').textContent.includes('saved for 24 hours'));
 assert.deepEqual(await page.evaluate(()=>captureQuoteSnapshot()),original.quote);
 console.log('PASS actual tab closure/refresh, interrupted autosave warning/retry, exact restore without estimate creation',industry,width);
`+anchor);
new Function('require',script)(require);
