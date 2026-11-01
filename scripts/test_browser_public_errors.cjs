// Disposable loopback server only; fresh Chromium contexts and synthetic credentials.
const {chromium}=require('playwright'),fs=require('fs'),path=require('path'),assert=require('assert/strict');
const deps=path.dirname(path.dirname(require.resolve('leaflet/package.json'))),out=process.env.QA_BROWSER_OUTPUT||'/tmp/aq-public-errors';fs.mkdirSync(out,{recursive:true});
const results=[];
async function prepare(browser,width){
 const context=await browser.newContext({viewport:{width,height:1000}}),page=await context.newPage(),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await context.route('**/*',async route=>{const u=new URL(route.request().url());let f;
  if(u.hostname==='unpkg.com'){if(u.pathname.includes('leaflet.js'))f=deps+'/leaflet/dist/leaflet.js';else if(u.pathname.includes('leaflet.css'))f=deps+'/leaflet/dist/leaflet.css';else return route.fulfill({body:''});}
  if(u.hostname==='cdnjs.cloudflare.com')f=u.pathname.includes('html2canvas')?deps+'/html2canvas/dist/html2canvas.min.js':deps+'/jspdf/dist/jspdf.umd.min.js';
  if(f)return route.fulfill({path:f,contentType:f.endsWith('.css')?'text/css':'text/javascript'});
  if(u.hostname!=='127.0.0.1')return route.abort();return route.continue();
 });return{context,page,errors};
}
(async()=>{const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
for(const width of [1440,390]){
 let {context,page,errors}=await prepare(browser,width);
 await page.goto('http://127.0.0.1:8765/dealer-login');
 await page.fill('#loginEmail','qa-browser@example.invalid');await page.fill('#loginPassword','WRONG_SYNTHETIC_ONLY');await page.click('button');
 await page.getByText('Email or password is incorrect.',{exact:true}).waitFor();
 await page.fill('#loginEmail','qa-browser@example.invalid');await page.fill('#loginPassword','fictional-qa-password');
 await Promise.all([page.waitForURL(u=>u.pathname==='/'),page.click('button')]);await page.waitForFunction(()=>typeof map!=='undefined');
 assert.equal(await page.locator('#aqAccountId').getAttribute('data-account-id'),'qa-browser');
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 assert.deepEqual(errors,[]);results.push({stage:'login rejection and successful retry',width,uncaught:errors});await context.close();
 ({context,page,errors}=await prepare(browser,width));
 await page.goto('http://127.0.0.1:8765/site/trial-signup.html?industry=pressure');
 const email=`public-crash-${width}-${Date.now()}@example.invalid`;
 await page.fill('#trialName','FICTIONAL QA PUBLIC');await page.fill('#trialBusiness','FICTIONAL QA ONLY');await page.fill('#trialEmail',email);await page.fill('#trialPassword','fictional-qa-password');
 let mode='network';await page.route('**/api/public/signup',route=>mode==='network'?route.abort():mode==='invalid-json'?route.fulfill({status:503,body:'<html>unavailable</html>',contentType:'text/html'}):route.fulfill({status:429,json:{error:'Temporarily unavailable. Please try again.'}}));
 for(mode of ['network','invalid-json','server']){
  await page.click('#trialForm button');await page.waitForFunction(()=>!document.querySelector('#trialForm button').disabled&&!document.querySelector('#signupError').hidden);
  assert(/try again|retry/i.test(await page.locator('#signupError').innerText()));
  assert.equal(await page.inputValue('#trialBusiness'),'FICTIONAL QA ONLY');assert.equal(await page.inputValue('#trialEmail'),email);
 }
 await page.screenshot({path:`${out}/signup-recovery-${width}.png`,fullPage:true});
 await page.unroute('**/api/public/signup');await Promise.all([page.waitForURL(u=>u.pathname.replace(/\.html$/,'')==='/site/pressure-setup'),page.click('#trialForm button')]);
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 assert.deepEqual(errors,[]);results.push({stage:'signup network/invalid JSON/server failure then successful retry',width,uncaught:errors,preserved:true});await context.close();
}
await browser.close();fs.writeFileSync(out+'/public-results.json',JSON.stringify(results,null,2));console.log(JSON.stringify(results));
})().catch(e=>{console.error(e);process.exit(1)});
