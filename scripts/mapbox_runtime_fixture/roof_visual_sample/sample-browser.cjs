const {chromium}=require(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES+'/playwright');
const assert=require('node:assert/strict');
const url='http://127.0.0.1:8887';
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
 assert.equal(await lookup('18 Fictional Roof Lane'),200);
 assert.match(await p.locator('#status').innerText(),/Trace each roof section/);
 const inputs=[
  {label:'Main roof',pitch:'22.62',points:[[50.9999,-114.00023],[50.9999,-113.99998],[51.00004,-113.99998],[51.00004,-114.00023]]},
  {label:'Cross-gable',pitch:'33.69',points:[[51.00004,-114.00014],[51.00004,-114.00004],[51.00016,-114.00004],[51.00016,-114.00014]]},
  {label:'Detached garage',pitch:'18.43',points:[[50.99993,-113.99991],[50.99993,-113.99981],[51.00004,-113.99981],[51.00004,-113.99991]]}
 ];
 await p.evaluate(inputs=>{
  el('streetViewChoice').value='none';el('customerName').value='Fictional QA Customer';
  for(const {label,pitch,points} of inputs){
   if(!traceMode)toggleTrace();
   for(const pt of points)addTracePoint(L.latLng(pt));
   el('pitchSel').value=pitch;el('pitchSel').dispatchEvent(new Event('change'));finishTrace();
   if(manualPlanes.length===0||traceMode)throw Error(el('status').textContent);
   manualPlanes.at(-1).qa_sample_label=label;
  }
  el('manualRoofScopeConfirmed').checked=true;el('dealerCountry').value='CA';el('jobPrice').value='0.85';el('gst').value='5';el('pst').value='0';renderSummary();
 },inputs);
 const expected=await p.evaluate(()=>({planes:captureQuoteSnapshot().manualPlanes,pricing:priceCalc()}));
 assert.deepEqual(expected.planes.map(x=>x.qa_sample_label),inputs.map(x=>x.label));
 for(let i=0;i<inputs.length;i++){
  assert.deepEqual(expected.planes[i].points.map(x=>[x.lat,x.lng]),inputs[i].points);
  assert.equal(expected.planes[i].pitch_degrees,Number(inputs[i].pitch));
 }
 await p.locator('#createEstimateBtn').click({timeout:6000});
 await p.locator('#downloadPdfBtn').waitFor({state:'visible',timeout:6000});
 const state=await (await context.request.get(url+'/qa-state')).json();
 assert.equal(state.estimates.length,1);assert.equal(state.estimate_revisions.length,0);
 const id=state.estimates[0].id;
 await p.locator('#backToDealerBtn').click();
 await p.getByRole('button',{name:'PREVIOUS ESTIMATES',exact:true}).click();
 await p.getByRole('button',{name:'VIEW HISTORY',exact:true}).click();
 await p.getByRole('button',{name:'OPEN ESTIMATE',exact:true}).click();
 await p.locator('#downloadPdfBtn').waitFor({state:'visible'});
 const saved=await p.evaluate(()=>savedEstimateEditContext.payload);
 assert.deepEqual(saved.quote.manualPlanes,expected.planes);assert.deepEqual(saved.pricing,expected.pricing);
 assert.equal(saved.image_choice,'none');assert.equal(saved.street_image_data,'');
 assert.match(await p.locator('#rEstimateTitle').innerText(),/Sample — Fictional QA Estimate/);
 for(const input of inputs)assert.match(await p.locator('#rProperty').innerText(),new RegExp(input.label));
 for(const layout of ['single','expanded']){
  await p.locator('#estimatePdfLayout').selectOption(layout);const dl=p.waitForEvent('download');
  await p.locator('#downloadPdfBtn').click();await (await dl).saveAs('/tmp/aq-roof-sample/Sample_'+layout+'.pdf');
 }
 console.log(JSON.stringify({id,revision:'current; 0 prior revisions',planes:saved.quote.manualPlanes,pricing:saved.pricing}));
 await context.close();
}}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
