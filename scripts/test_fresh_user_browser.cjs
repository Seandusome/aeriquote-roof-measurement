// Real first-user UI, no saved profile/localStorage fixtures or recovery bypass.
const fs=require('fs'),assert=require('assert/strict');
process.env.QA_BROWSER_WIDTHS='1440';process.env.QA_BROWSER_INDUSTRIES='paving';process.env.QA_BROWSER_IMAGES='hide';
let script=fs.readFileSync('scripts/test_prelaunch_browser.cjs','utf8');
const start=script.indexOf(" await page.goto('http://127.0.0.1:8765/login');"),end=script.indexOf(" await page.fill('#streetAddress'",start);assert(start>=0&&end>start);
script=script.slice(0,start)+String.raw`
 await page.goto('http://127.0.0.1:8765/site/trial-signup.html?industry=paving');
 await page.fill('#trialName','FICTIONAL FRESH OWNER');await page.fill('#trialBusiness','FICTIONAL FIRST JOB COMPANY');await page.fill('#trialEmail','fresh-desktop@example.invalid');await page.fill('#trialPassword','fictional-qa-password');
 await Promise.all([page.waitForURL(u=>u.pathname.replace(/\.html$/,'')==='/site/paving-setup'),page.click('#trialForm button')]);
 const state=async()=>await(await context.request.get('http://127.0.0.1:8765/__qa_fresh/state')).json();
 assert.equal((await state()).plan.plan_code,'trial');assert.equal((await state()).complimentary,false);assert.equal((await state()).lookups,0);
 await page.click('#nextBtn');assert.equal(await page.locator('.setup-step.active').getAttribute('data-step'),'1');assert(await page.locator('#setupError').isVisible());assert.equal(await page.inputValue('#companyName'),'FICTIONAL FIRST JOB COMPANY');
 await page.selectOption('#region','SK');await page.click('#nextBtn');
 await page.locator('input[name="pricing"][value="manual"]').check();await page.fill('#tax1','5');await page.fill('#tax2','6');await page.click('#nextBtn');
 await page.click('#nextBtn');await page.click('#finishSetup');await page.waitForURL(u=>u.pathname==='/'&&u.searchParams.get('industry')==='paving');
 await page.waitForFunction(()=>typeof map!=='undefined');await page.waitForTimeout(600);
 assert.equal((await(await context.request.get('http://127.0.0.1:8765/api/account/profile')).json()).profile.pricingMethod,'manual');
 console.log('PASS actual signup and four-step manual-rate business setup; missing region preserves contact entry; normal trial starts unused');
`+script.slice(end);
const point=" const before=await page.evaluate(";assert(script.includes(point));script=script.replace(point,String.raw`
 // Choosing per-job pricing must require a conscious rate, not a free quote.
 assert.equal(await page.locator('#createEstimateBtn').isDisabled(),true,'Manual per-job setup must not silently quote a newly measured job at zero');
 assert(/price|rate/i.test(await page.locator('#quotePricingError').textContent()));
 await page.fill('#jobPrice','.1');await page.locator('#jobPrice').blur();
 const rates=page.getByRole('spinbutton',{name:'Rate per square foot'});for(let n=0;n<await rates.count();n++){await rates.nth(n).fill('.1');await rates.nth(n).blur();}
`+point);
const after=" // A second page load simulates refresh; reopen the owned stored snapshot through the actual handler.";assert(script.includes(after));script=script.replace(after,String.raw`
 const firstState=await state();assert.equal(firstState.lookups,1);assert.equal(firstState.counts.estimates,1);assert.equal(firstState.counts.estimate_revisions,0);assert.equal(firstState.counts.estimate_save_receipts,1);
 // Distinct allowance case: three normal trial property acceptances, failed image
 // and exhausted fourth attempt retain the already-saved job and customer.
 await page.getByRole('button',{name:'Back to Dealer View',exact:true}).click();
 const snapshotBeforeLimits=await page.evaluate(()=>JSON.stringify(captureQuoteSnapshot()));
 for(let n=0;n<2;n++){const operation='fresh-trial-'+n;const prepared=await context.request.post('http://127.0.0.1:8765/property',{headers:{'Idempotency-Key':operation},data:{key:'qa-placeholder',address:'1 Fictional QA Street',business_type:'paving',prepare_only:true}});assert.equal(prepared.status(),200);const accepted=await context.request.post('http://127.0.0.1:8765/property/accept',{data:{operation_id:operation,token:(await prepared.json()).token}});assert.equal(accepted.status(),200);assert.equal((await state()).lookups,n+2);}
 await page.click('#propertyActionBtn');await page.waitForFunction(()=>!loadProperty.inFlight);assert.equal((await state()).lookups,3);assert((await page.locator('#status').textContent()).match(/allowance|trial|limit/i));assert.equal(await page.evaluate(()=>JSON.stringify(captureQuoteSnapshot())),snapshotBeforeLimits);if(await page.locator('#trialLimitOverlay.open').count())await page.locator('#trialLimitOverlay button').click();
 assert.equal((await state()).counts.estimates,1);
 // Paid state is test-fixture-only; no payment flow or live account is changed.
 assert.equal((await context.request.post('http://127.0.0.1:8765/__qa_fresh/basic-boundary')).status(),200);
 const imagePattern=/\/(wide-aerial|fallback-map|exact-pin-map)\//;await page.route(imagePattern,r=>r.abort());await page.click('#propertyActionBtn');await page.waitForFunction(()=>!loadProperty.inFlight);assert.equal((await state()).lookups,24);assert.equal(await page.evaluate(()=>JSON.stringify(captureQuoteSnapshot())),snapshotBeforeLimits);assert(/retry|again/i.test(await page.locator('#status').textContent()));await page.unroute(imagePattern);
 await page.click('#propertyActionBtn');await page.waitForFunction(()=>!loadProperty.inFlight);assert.equal((await state()).lookups,25);
 await page.click('#propertyActionBtn');await page.waitForFunction(()=>!loadProperty.inFlight);assert.equal((await state()).lookups,25);assert.equal((await state()).paid.lookups,25);
 console.log('PASS normal trial3 cap; paid24→25 once; failed imagery and exhausted retries do not debit or add estimates');
`+after);
new Function('require',script)(require);
