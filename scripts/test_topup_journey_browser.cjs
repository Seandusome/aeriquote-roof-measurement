// One paid-plan journey: owner buys; employee measures/saves; owner reopens/exports/revises.
const fs=require('fs'),assert=require('assert/strict');
process.env.QA_BROWSER_WIDTHS='1440';process.env.QA_BROWSER_INDUSTRIES='landscaping';process.env.QA_BROWSER_IMAGES='hide';process.env.QA_BROWSER_ALL_PDFS='1';
let script=fs.readFileSync('scripts/test_prelaunch_browser.cjs','utf8');
const start=" await page.goto('http://127.0.0.1:8765/login');";assert(script.includes(start));
script=script.replace(start,()=>String.raw`
 const base='http://127.0.0.1:8765',stages=[],saveRequests=[],acceptRequests=[];
 const state=async()=>{const r=await context.request.get(base+'/__qa_topup/state');assert.equal(r.status(),200);return r.json()};
 const mark=async label=>{const s=await state();stages.push({label,...s});fs.writeFileSync(output+'/topup-stages.json',JSON.stringify(stages,null,2));return s};
 page.on('request',r=>{if(r.method()==='POST'&&new URL(r.url()).pathname==='/api/estimates')saveRequests.push({data:r.postDataJSON(),headers:r.headers()});if(r.method()==='POST'&&new URL(r.url()).pathname==='/property/accept')acceptRequests.push(r.postDataJSON());});
 const login=async(email)=>{await page.goto(base+'/dealer-login');await page.fill('#loginEmail',email);await page.fill('#loginPassword','fictional-qa-password');await Promise.all([page.waitForURL(u=>!u.pathname.includes('login')),page.locator('button').first().click()])};
 await login('purchase-ca@example.invalid');assert.equal((await context.request.post(base+'/__qa_topup/exhaust',{data:{}})).status(),200);
 let s=await mark('monthly-and-bonus-exhausted');assert.equal(s.paid.lookups,28);assert.equal(s.paid.estimates,28);assert.deepEqual(s.ledger.bank,{lookups:0,estimates:0});
 await page.goto(base+'/qa/purchases');assert.equal(await page.locator('[data-balance=monthly]').textContent(),'0');assert.equal(await page.locator('[data-balance=bonus]').textContent(),'0');assert.equal(await page.locator('[data-balance=purchased]').textContent(),'0');assert(!(await page.locator('body').textContent()).includes('Configured applicable Canadian tax.'));
 await page.click('#startPurchase');await page.getByRole('button',{name:'Simulate success',exact:true}).waitFor();assert.deepEqual((await mark('pending-no-grant')).ledger.bank,{lookups:0,estimates:0});
 await page.getByRole('button',{name:'Simulate success',exact:true}).click();await page.locator('.status').filter({hasText:'Simulated success'}).waitFor();s=await mark('confirmed-pack');assert.deepEqual(s.ledger.bank,{lookups:25,estimates:25});assert.equal(s.counts.topup_fulfillments,1);await page.screenshot({path:output+'/topup-confirmed.png',fullPage:true});
 for(const prepare_only of [false,true]){const r=await context.request.post(base+'/property',{data:{address:'FICTIONAL FAIL',key:'qa-placeholder',prepare_only},headers:{'Idempotency-Key':'failed-'+prepare_only}});assert.equal(r.status(),503)}
 assert.deepEqual((await mark('failed-loads-free')).ledger.bank,{lookups:25,estimates:25});
 await page.goto(base+'/logout');
`+start);
script=script.replace("await page.fill('#loginEmail','qa-browser@example.invalid')","await page.fill('#loginEmail','purchase-employee@example.invalid')");
const loaded=" console.log('loaded',";assert(script.includes(loaded));script=script.replace(loaded,()=>String.raw`
 const employeeState=await mark('employee-property-accepted');assert.equal(employeeState.employee,true);assert.deepEqual(employeeState.ledger.bank,{lookups:24,estimates:25});
`+loaded);
const saved=" fs.writeFileSync(`${output}/${industry}-${width}-source.json`,JSON.stringify(payload,null,2));";assert(script.includes(saved));script=script.replace(saved,()=>saved+String.raw`
 let shared=await mark('employee-estimate-saved');assert.deepEqual(shared.ledger.bank,{lookups:24,estimates:24});assert.equal(shared.counts.estimates,1);
 const request=saveRequests.at(-1);assert(request.headers['idempotency-key']);for(let i=0;i<3;i++){const replay=await context.request.post(base+'/api/estimates',{data:request.data,headers:{'Idempotency-Key':request.headers['idempotency-key']}});assert.equal(replay.status(),200);assert.equal((await replay.json()).id,saved.id)}
 assert.deepEqual((await mark('save-retries-free')).ledger.bank,{lookups:24,estimates:24});
 await page.goto(base+'/logout');await login('purchase-ca@example.invalid');assert.equal((await state()).employee,false);
 for(let i=0;i<3;i++)assert.equal((await context.request.post(base+'/property/accept',{data:acceptRequests[0]})).status(),200);
 assert.deepEqual((await mark('owner-replays-employee-acceptance')).ledger.bank,{lookups:24,estimates:24});
`);
const finish=' await page.screenshot({path:';assert(script.includes(finish));script=script.replace(finish,()=>String.raw`
 assert.deepEqual((await mark('owner-reopened-and-both-pdfs-downloaded')).ledger.bank,{lookups:24,estimates:24});
 const changed=JSON.parse(JSON.stringify(payload));changed.customer_name='FICTIONAL TOPUP REVISED';
 const revision=await context.request.post(base+'/api/estimates',{data:changed,headers:{'Idempotency-Key':'topup-revision','If-Match':saved.version}});assert.equal(revision.status(),200);const revised=await revision.json();
 const retry=await context.request.post(base+'/api/estimates',{data:changed,headers:{'Idempotency-Key':'topup-revision','If-Match':saved.version}});assert.equal(retry.status(),200);assert.deepEqual(await retry.json(),revised);
 const old=await (await context.request.get(base+'/api/estimates/'+saved.id+'/versions')).json();assert.equal(old.revisions.length,1);assert.deepEqual(old.revisions[0].payload,payload);
 await page.evaluate(id=>openHistoricalEstimate(id,-1),saved.id);await page.waitForFunction(()=>document.body.classList.contains('report-open')&&!estimateOpenInProgress);assert.equal(await page.locator('#rCustomerName').textContent(),changed.customer_name);
 for(const layout of ['single','expanded']){await page.selectOption('#estimatePdfLayout',layout);const download=page.waitForEvent('download',{timeout:45000});await page.click('#downloadPdfBtn');await(await download).saveAs(output+'/topup-revised-'+layout+'.pdf')}
 fs.writeFileSync(output+'/topup-revised-source.json',JSON.stringify(changed,null,2));let end=await mark('revision-retry-reopen-and-both-pdfs-free');assert.deepEqual(end.ledger.bank,{lookups:24,estimates:24});assert.equal(end.counts.estimates,1);assert.equal(end.counts.estimate_revisions,1);assert.equal(end.purchased_debits.length,2);assert.deepEqual(end.purchased_debits.map(d=>[d.channel,d.delta]),[['estimates',-1],['lookups',-1]]);
 assert.equal((await context.request.post(base+'/__qa_topup/subscription',{data:{status:'canceled'}})).status(),200);const held=await mark('canceled-balance-retained');assert.deepEqual(held.ledger.bank,end.ledger.bank);
 assert.equal((await context.request.post(base+'/property',{data:{address:'2 FICTIONAL QA STREET',key:'qa-placeholder',prepare_only:true},headers:{'Idempotency-Key':'canceled-new'}})).status(),403);assert.deepEqual((await state()).ledger.bank,end.ledger.bank);
 assert.equal((await context.request.post(base+'/__qa_topup/subscription',{data:{status:'active'}})).status(),200);const available=await context.request.post(base+'/property',{data:{address:'2 FICTIONAL QA STREET',key:'qa-placeholder',prepare_only:true},headers:{'Idempotency-Key':'active-new'}});assert.equal(available.status(),200);assert.deepEqual((await mark('reactivation-allows-prepare-without-second-debit')).ledger.bank,end.ledger.bank);
 const other=await browser.newContext(),otherPage=await other.newPage();await other.route('**/*',r=>new URL(r.request().url()).origin===base?r.continue():r.abort());await otherPage.goto(base+'/dealer-login');await otherPage.fill('#loginEmail','purchase-us@example.invalid');await otherPage.fill('#loginPassword','fictional-qa-password');await Promise.all([otherPage.waitForURL(u=>!u.pathname.includes('login')),otherPage.locator('button').first().click()]);assert.equal((await other.request.get(base+'/api/estimates/'+saved.id)).status(),404);assert.equal((await other.request.post(base+'/property/accept',{data:acceptRequests[0]})).status(),404);const isolated=await(await other.request.get(base+'/__qa_topup/state')).json();assert.deepEqual(isolated.ledger.bank,{lookups:3,estimates:3});assert.deepEqual(isolated.ledger.sources.purchased,{lookups:0,estimates:0});await other.close();
 console.log('PASS full topup browser journey: exhausted monthly/bonus, confirmed pack25, employee measures/saves, owner retries/reopens/revises and four PDF downloads; exactly1 purchased measurement and included estimate, final24; failed loads free; cancellation holds/reactivation access; other business denied');
`+finish);
new Function('require',script)(require);
