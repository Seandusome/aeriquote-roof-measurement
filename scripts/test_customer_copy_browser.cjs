// Disposable loopback visual review; use prelaunch_browser_server.py, never a hosted database.
const {chromium}=require('playwright'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const origin='http://127.0.0.1:8765',output=process.env.QA_COPY_OUTPUT||'/tmp/aq-customer-copy-review';fs.mkdirSync(output,{recursive:true});
const deps=path.dirname(path.dirname(require.resolve('leaflet/package.json')));
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.QA_CHROMIUM_EXECUTABLE||undefined,args:['--no-sandbox']});const results=[];
try{for(const width of [1440,390]){
 const browserVersion=browser.version();const context=await browser.newContext({viewport:{width,height:900},deviceScaleFactor:1});const page=await context.newPage(),errors=[],payments=[];
 page.on('pageerror',e=>errors.push(e.message));
 await context.route('**/*',async route=>{const u=new URL(route.request().url());let file;
  if(/stripe/i.test(u.hostname)){payments.push(u.hostname);return route.abort()}
  if(u.hostname==='unpkg.com'){if(u.pathname.endsWith('leaflet.js'))file=deps+'/leaflet/dist/leaflet.js';else if(u.pathname.endsWith('leaflet.css'))file=deps+'/leaflet/dist/leaflet.css';else return route.fulfill({body:''})}
  if(u.hostname==='cdnjs.cloudflare.com')file=u.pathname.includes('html2canvas')?deps+'/html2canvas/dist/html2canvas.min.js':deps+'/jspdf/dist/jspdf.umd.min.js';
  if(file)return route.fulfill({path:file,contentType:file.endsWith('.css')?'text/css':'text/javascript'});
  if(u.origin!==origin)return route.abort();return route.continue();
 });
 await page.goto(origin+'/dealer-login');await page.getByRole('textbox',{name:'Email',exact:true}).fill('qa-browser@example.invalid');await page.getByRole('textbox',{name:'Password',exact:true}).fill('fictional-qa-password');await Promise.all([page.waitForURL(u=>u.pathname==='/'),page.getByRole('button',{name:'LOG IN',exact:true}).click()]);
 await page.goto(origin+'/?industry=roofing');assert.equal(await page.evaluate(()=>innerWidth),width);await page.waitForFunction(()=>typeof map!=='undefined');
 const overflow=async()=>assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No horizontal overflow at '+width);
 const link=page.getByRole('link',{name:'PLANS / EXTRA MEASUREMENTS',exact:true});await link.waitFor({state:'visible'});assert.equal(await link.getAttribute('href'),'/site/pricing#extra-measurements');await overflow();
 await page.screenshot({path:`${output}/owner-${width}.png`});
 const intro=page.locator('.measure-intro');assert((await intro.innerText()).includes('Confirm pitch'));await intro.screenshot({path:`${output}/measurement-copy-${width}.png`});
 await link.click();await page.waitForURL('**/site/pricing#extra-measurements');
 const offer=page.locator('#extra-measurements');await offer.waitFor({state:'visible'});const text=await offer.innerText();
 for(const term of ['25 extra property measurements for US$25','Estimates included','carry forward without expiry','active paid or complimentary subscription','applicable tax','Purchasing is not available yet'])assert(text.includes(term),term);
 assert.equal(await offer.locator('button,input,form').count(),0,'No inactive-looking payment form or actionable purchase');await overflow();await offer.screenshot({path:`${output}/offer-${width}.png`});
 await page.goto(origin+'/site/');const ai=page.locator('.aq-auto-callout');assert(!/AI-assisted|automatic roof/i.test(await ai.innerText()));for(const term of ['Trace the roof','confirm its pitch','branded estimate'])assert((await ai.innerText()).includes(term),term);await overflow();await ai.screenshot({path:`${output}/roofing-ai-${width}.png`});
 await page.goto(origin+'/site/trial-signup?industry=roofing');assert((await page.locator('#measurementHelp').innerText()).includes('confirm its pitch'));await overflow();await page.screenshot({path:`${output}/signup-${width}.png`});
 await page.goto(origin+'/site/trial-signup?industry=landscaping');const otherCopy=await page.locator('#measurementHelp').innerText();assert(otherCopy.includes('Trace service areas and lengths'));assert(!/AI|automatic roof/i.test(otherCopy),'No AI/automatic-roof claim for manual surface tools');
 assert.equal((await page.request.get(origin+'/qa/purchases')).status(),404,'Hosted-disabled simulation stays off by default');assert.equal(payments.length,0);assert.deepEqual(errors,[]);
 results.push({width,actualWidth:await page.evaluate(()=>innerWidth),browserVersion,ownerLink:'pass',offer:'pass',aiScope:'pass',pitchAndManual:'pass',overflow:'pass',paymentsRequested:0});await context.close();
}}finally{await browser.close()}
fs.writeFileSync(`${output}/results.json`,JSON.stringify(results,null,2));console.log(JSON.stringify(results,null,2));
})().catch(e=>{console.error(e);process.exitCode=1});
