const {chromium}=require(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES+'/playwright');
const assert=require('node:assert/strict');
const url='http://127.0.0.1:8884';
(async()=>{const browser=await chromium.launch({executablePath:'/tmp/aq-chrome/chrome-headless-shell-linux64/chrome-headless-shell',args:['--no-sandbox']});
try{for(const [key,width,old] of [['desktop',1440,false]]){
 const context=await browser.newContext({viewport:{width,height:900},acceptDownloads:true});
 await context.route('**/*',r=>{const u=new URL(r.request().url());if(u.origin===url){if(old&&u.pathname==='/static/workspace_drafts.js')return r.fulfill({path:'/tmp/aq-picker-qa/before.js',contentType:'application/javascript'});return r.continue()}const name=u.pathname.split('/').at(-1);return /^(leaflet\.(js|css)|html2canvas.min.js|jspdf.umd.min.js)$/.test(name)?r.fulfill({path:'/tmp/aq-picker-qa/vendor/'+name}):r.abort()});
 const login=await context.request.post(url+'/dealer-login',{form:{email:'desktop@example.invalid',password:process.env.AQ_FIXTURE_PASSWORD},maxRedirects:0});assert.equal(login.status(),302);
 const p=await context.newPage();await p.goto(url);await p.waitForFunction(()=>window.aqRecovery&&typeof map!=='undefined');
 const records=async()=>await (await context.request.get(url+'/qa-meter')).json();
 let cursor=0;
 const mark=async label=>{const all=await records(),counts={};for(const [,k] of all.slice(cursor))counts[k]=(counts[k]||0)+1;cursor=all.length;console.log(label,JSON.stringify(counts));};
 const lookup=async(street)=>{
  const response=await context.request.post(url+'/address-preview',{data:{key:'google-fixture-only',address:street+', Calgary, AB',expected_city:'Calgary',expected_province:'AB',expected_street_number:'18'}});
  await p.evaluate(street=>{setPropertyRegion('AB');el('streetAddress').value=street;el('cityTown').value='Calgary'},street);
  await p.evaluate(()=>loadProperty());return response.status();
 };
 assert.equal(await lookup('18 Missing Roof Lane'),404);await mark('failed preview and lookup');
 assert.equal(await lookup('18 Fictional Roof Lane'),200);
 assert.match(await p.locator('#status').innerText(),/Trace each roof section/);
 await p.waitForResponse(r=>r.url().includes('/street/')&&r.status()===200,{timeout:1200}).catch(()=>{});
 await mark('successful retry and map load');
 await p.evaluate(()=>{el('streetViewChoice').value='none';tracePoints=[[51,-114],[51,-113.9999],[51.0001,-113.9999],[51.0001,-114]].map(x=>L.latLng(x));el('pitchSel').value='22.62';el('pitchSel').dispatchEvent(new Event('change'));el('pitchDeg').value='22.62';finishTrace();el('manualRoofScopeConfirmed').checked=true;renderSummary();});
 await mark('manual trace');
 console.log('trace status',await p.locator('#status').innerText());await p.locator('#createEstimateBtn').click({timeout:5000});await p.waitForTimeout(800);console.log('save status',await p.locator('#status').innerText());await p.locator('#downloadPdfBtn').waitFor({state:'visible',timeout:5000});await mark('save and preview');
 await p.locator('#backToDealerBtn').click();await p.getByRole('button',{name:'PREVIOUS ESTIMATES',exact:true}).click();await p.getByRole('button',{name:'VIEW HISTORY',exact:true}).click();await p.getByRole('button',{name:'OPEN ESTIMATE',exact:true}).click();await p.locator('#downloadPdfBtn').waitFor({state:'visible'});await mark('reopen');
 for(const layout of ['single','expanded']){
  await p.locator('#estimatePdfLayout').selectOption(layout);const dl=p.waitForEvent('download');
  await p.locator('#downloadPdfBtn').click();await dl;await mark(layout+' PDF');
 }
 const minute={};for(const [m,k] of await records()){minute[m]??={};minute[m][k]=(minute[m][k]||0)+1;}console.log('UTC minute buckets',JSON.stringify(minute));
 await context.close();
}}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
