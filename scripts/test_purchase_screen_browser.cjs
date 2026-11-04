// Real Chromium, real login/forms; fixture server on loopback8766 only.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert/strict');
const output=process.env.QA_BROWSER_OUTPUT||'/tmp/aq-purchase-screen';fs.mkdirSync(output,{recursive:true});
const base='http://127.0.0.1:8766';
(async()=>{const browser=await chromium.launch({headless:true,channel:'chromium',args:['--no-sandbox']});const results=[];
try{for(const width of [1440,390,320]){
 const context=await browser.newContext({viewport:{width,height:1000}});const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(10000);
 await context.route('**/*',r=>new URL(r.request().url()).origin===base?r.continue():r.abort());
 await page.goto(base+'/dealer-login');await page.fill('#loginEmail','purchase-ca@example.invalid');await page.fill('#loginPassword','fictional-qa-password');
 await Promise.all([page.waitForURL(u=>!u.pathname.includes('login')),page.locator('button').first().click()]);await page.goto(base+'/qa/purchases');
 const purchased=async()=>Number(await page.locator('[data-balance=purchased]').textContent());const initial=await purchased();assert.equal(await page.locator('[data-balance=granted]').textContent(),'3');
 assert.equal(await page.locator('#tax').textContent(),'US$2.75');assert.equal(await page.locator('#total').textContent(),'US$27.75');
 const capture=async name=>{assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'No horizontal overflow at '+width+' '+name);await page.screenshot({path:`${output}/${width}-${name}.png`,fullPage:true});};
 await capture('01-start');
 // Two submissions of the exact visible form exercise real browser cancellation/double click.
 await page.locator('#startPurchase').evaluate(button=>{button.form.requestSubmit();button.form.requestSubmit()});
 await page.locator('.order .status').first().filter({hasText:'Pending'}).waitFor();const order=page.locator('.order').first();const oid=await order.getAttribute('data-order');
 assert.equal(await purchased(),initial);await page.reload();assert.equal(await page.locator(`.order[data-order="${oid}"]`).count(),1);await capture('02-pending');
 await page.locator(`.order[data-order="${oid}"]`).getByRole('button',{name:'Simulate failure',exact:true}).click();await page.locator(`.order[data-order="${oid}"] .status`).filter({hasText:'Failed'}).waitFor();assert.equal(await purchased(),initial);await capture('03-failed');
 await page.locator(`.order[data-order="${oid}"]`).getByRole('button',{name:'Retry simulated payment',exact:true}).click();await page.locator(`.order[data-order="${oid}"] .status`).filter({hasText:'Pending'}).waitFor();assert.equal(await purchased(),initial);
 const success=page.locator(`.order[data-order="${oid}"]`).getByRole('button',{name:'Simulate success',exact:true});
 const data=await success.evaluate(b=>Object.fromEntries(new FormData(b.form)));
 if(width===390){
  // Server commits success, browser loses the response. Reload/replay must show one grant.
  await page.route('**/qa/purchases',async r=>{if(r.request().method()==='POST'){const response=await r.fetch({maxRedirects:0});assert.equal(response.status(),303);return r.abort('failed')}return r.continue()});
  const failedNavigationLoaded=page.waitForEvent('load');
  await success.click({noWaitAfter:true});await failedNavigationLoaded;await page.unroute('**/qa/purchases');await page.goto(base+'/qa/purchases');
 }else await success.click();
 await page.locator(`.order[data-order="${oid}"] .status`).filter({hasText:'Simulated success'}).waitFor();assert.equal(await purchased(),initial+25);
 for(let i=0;i<3;i++){const r=await context.request.post(base+'/qa/purchases',{form:data,maxRedirects:0});assert.equal(r.status(),303);}
 await page.reload();assert.equal(await purchased(),initial+25);assert.equal(await page.locator(`.order[data-order="${oid}"]`).count(),1);await capture('04-success');
 assert.equal(errors.length,0,errors.join('\n'));results.push({width,pending_no_grant:true,failed_no_grant:true,retry_same_order:true,duplicate_refresh_success_once:true,lost_response:width===390,initial,purchased:initial+25,uncaught_errors:errors.length});await context.close();
}
 const us=await browser.newContext({viewport:{width:1440,height:1000}});const p=await us.newPage();await us.route('**/*',r=>new URL(r.request().url()).origin===base?r.continue():r.abort());await p.goto(base+'/dealer-login');await p.fill('#loginEmail','purchase-us@example.invalid');await p.fill('#loginPassword','fictional-qa-password');await Promise.all([p.waitForURL(u=>!u.pathname.includes('login')),p.locator('button').first().click()]);await p.goto(base+'/qa/purchases');assert.equal(await p.locator('#tax').textContent(),'US$0.00');assert.equal(await p.locator('#total').textContent(),'US$25.00');assert.equal(await p.locator('.order').count(),0);await p.screenshot({path:output+'/1440-us-zero-tax.png',fullPage:true});await us.close();
 fs.writeFileSync(output+'/browser-results.json',JSON.stringify(results,null,2));console.log('PASS owner purchase screen desktop1440 and phone390/320; pending, failed, retry, double-submit, refresh, replay and lost-success-response once; USzero and CA tax; zero uncaught errors');console.log(JSON.stringify(results));
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
