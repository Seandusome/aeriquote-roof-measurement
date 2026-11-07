const {chromium}=require(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES+'/playwright');
const assert=require('node:assert/strict');
const url='http://127.0.0.1:8881';
(async()=>{const browser=await chromium.launch({executablePath:'/tmp/aq-chrome/chrome-headless-shell-linux64/chrome-headless-shell',args:['--no-sandbox']});
try{for(const [key,width,old] of [['desktop',1440,false]]){
 const context=await browser.newContext({viewport:{width,height:900},acceptDownloads:true});
 await context.route('**/*',r=>{const u=new URL(r.request().url());if(u.origin===url){if(old&&u.pathname==='/static/workspace_drafts.js')return r.fulfill({path:'/tmp/aq-picker-qa/before.js',contentType:'application/javascript'});return r.continue()}const name=u.pathname.split('/').at(-1);return /^(leaflet\.(js|css)|html2canvas.min.js|jspdf.umd.min.js)$/.test(name)?r.fulfill({path:'/tmp/aq-picker-qa/vendor/'+name}):r.abort()});
 await context.request.post(url+'/qa-provider',{data:{mode:'google'}});
 const login=await context.request.post(url+'/dealer-login',{form:{email:(key==='before-phone'?'before':key)+'@example.invalid',password:process.env.AQ_FIXTURE_PASSWORD},maxRedirects:0});assert.equal(login.status(),302);
 const p=await context.newPage();p.setDefaultTimeout(6500);p.on('console',m=>{if(m.text().startsWith('AQ:'))console.log(m.text())});p.on('pageerror',e=>console.log('PAGE',e.message));await p.goto(url);await p.waitForFunction(()=>window.aqRecovery&&typeof map!=='undefined');
 if(!await p.locator('#workspaceRecoveryChoices').count()){
  await p.locator('#workspaceRecoveryStatus').getByText('Recovery autosave is ready.').waitFor();
  await p.evaluate(()=>{el('address').value='99 Fictional Older Draft Lane';el('streetAddress').value='99 Fictional Older Draft Lane';el('customerNotes').value='older draft';el('customerNotes').dispatchEvent(new Event('input',{bubbles:true}));});
  assert.equal(await p.evaluate(()=>aqRecovery.flush()),true);await p.reload();
 }
 await p.locator('#workspaceRecoveryChoices').waitFor();
 await p.evaluate(()=>{sessionToken='fictional-test-token';el('address').value='18 Fictional New Roof Lane';el('streetAddress').value='18 Fictional New Roof Lane';el('customerName').value='QA Fictional Customer';el('streetViewChoice').value='none';map.setView([52,-106],19);tracePoints=[[52,-106],[52,-105.9999],[52.0001,-105.9999],[52.0001,-106]].map(x=>L.latLng(x));el('pitchDeg').value='22.62';finishTrace();});
 console.log('trace prepared',key,await p.locator('#createEstimateBtn').isEnabled());
 const before=await (await context.request.get(url+'/qa-state')).json();
 const beforeCounts=[before.estimates.length,before.estimate_revisions.length];
 const baseQuote=await p.evaluate(()=>({planes:captureQuoteSnapshot().manualPlanes,total:priceCalc().total,area:priceCalc().area}));
 assert(baseQuote.planes.length&&baseQuote.total>0);
 await p.locator('#createEstimateBtn').click();
 console.log('clicked',key,await p.locator('#status').textContent());
 await p.waitForFunction(()=>el('status').textContent.includes('Estimate not saved'),null,{timeout:6500});
 const message=await p.locator('#status').innerText();
 const blocked=await (await context.request.get(url+'/qa-state')).json();
 assert.deepEqual(blocked,before);
 if(!old){assert.match(message,/Keep working on this estimate, Restore, or Discard/);assert.equal(await p.evaluate(()=>document.activeElement.id),'workspaceRecoveryHeading');assert(await p.locator('#workspaceRecoveryChoices').innerText().then(x=>x.includes('99 Fictional Older Draft Lane')));}
 if(!old){const layout=await p.evaluate(()=>{const card=el('workspaceRecoveryChoices'),r=card.getBoundingClientRect();return card.previousElementSibling.classList.contains('header')&&card.nextElementSibling.classList.contains('stepbar')&&r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight;});assert(layout,'Card between header and steps, in viewport');}
 await p.evaluate(()=>scrollTo(0,0));
 await p.screenshot({path:'/mnt/data/Draft_picker_'+key+'.png'});
 if(old){console.log(key,message);await context.close();continue;}
 await p.getByRole('button',{name:'Keep working on this estimate',exact:true}).click();
 assert.deepEqual(await p.evaluate(()=>({planes:captureQuoteSnapshot().manualPlanes,total:priceCalc().total,area:priceCalc().area})),baseQuote);
 const sent=p.waitForResponse(r=>r.url()===url+'/api/estimates'&&r.request().method()==='POST');
 await p.locator('#createEstimateBtn').click();const response=await sent;assert.equal(response.status(),200,await response.text());
 await p.locator('#backToDealerBtn').click();await p.getByRole('button',{name:'PREVIOUS ESTIMATES',exact:true}).click();
 await p.getByRole('button',{name:'VIEW HISTORY',exact:true}).click();
 await p.getByRole('button',{name:'OPEN ESTIMATE',exact:true}).click();
 await p.locator('#downloadPdfBtn').waitFor();assert.match(await p.locator('#rPricing').innerText(),/756.20/);
 const dl=p.waitForEvent('download');await p.locator('#downloadPdfBtn').click();await (await dl).saveAs('/tmp/aq-picker-qa/'+key+'.pdf');
 await p.locator('#estimatePdfLayout').selectOption('expanded');const expanded=p.waitForEvent('download');await p.locator('#downloadPdfBtn').click();await (await expanded).saveAs('/tmp/aq-picker-qa/'+key+'-expanded.pdf');
 const after=await (await context.request.get(url+'/qa-state')).json();assert.deepEqual([after.estimates.length,after.estimate_revisions.length],[beforeCounts[0]+1,beforeCounts[1]]);
 const saved=JSON.parse(after.estimates[0].payload);assert.deepEqual(saved.quote.manualPlanes,baseQuote.planes);assert.equal(saved.total_price,baseQuote.total);assert.equal(saved.total_area,baseQuote.area);
 assert(after.workspace_drafts.some(x=>x.draft_id===before.workspace_drafts[0].draft_id&&x.payload===before.workspace_drafts[0].payload));
 const id=after.estimates[0].id;
 const getVersions=async id=>(await (await context.request.get(url+'/api/estimates/'+id+'/versions')).json());
 const revised={...saved,customer_notes:'Fictional revision marker'};
 const revision=await context.request.post(url+'/api/estimates',{data:revised});
 assert.equal(revision.status(),200,await revision.text());
 const baseline=await getVersions(id);assert.equal(baseline.revisions.length,1);
 const verify=async(id,versions)=>{
  for(const index of [-1,...versions.revisions.map((_,i)=>i)]){
   const expected=index<0?versions.current.payload:versions.revisions[index].payload;
   await p.evaluate(([id,index])=>openHistoricalEstimate(id,index),[id,index]);
   await p.locator('#downloadPdfBtn').waitFor({state:'visible'});
   const reopened=await p.evaluate(()=>savedEstimateEditContext.payload);
   assert.deepEqual(reopened,expected);
   assert.match(await p.locator('#rPricing').innerText(),new RegExp(expected.total_price.toFixed(2).replace('.','[.]')));
  }
 };
 const switched=await (await context.request.post(url+'/qa-provider',{data:{mode:'mapbox'}})).json();
 assert.equal(switched.google_key_available,false);
 await p.reload();await p.waitForFunction(()=>window.aqRecovery&&window.aqLocalMapbox);
 await verify(id,baseline);assert.deepEqual(await getVersions(id),baseline);
 await p.locator('#backToDealerBtn').click();
 await p.evaluate(()=>{setPropertyRegion('AB');el('streetAddress').value='218 Chaparral Place SE';el('cityTown').value='Calgary'});
 let dialogText='';
 p.once('dialog',async d=>{dialogText=d.message();await d.dismiss()});
 await p.evaluate(()=>loadProperty());assert.match(dialogText,/Chaparral Way SE/);assert.match(dialogText,/Confirm the property and map pin/);
 assert.match(await p.locator('#status').innerText(),/not confirmed/);
 let counts=await (await context.request.get(url+'/qa-provider-counts')).json();
 assert.equal(counts['Mapbox imagery fixture'],undefined);
 p.once('dialog',d=>d.accept());
 await p.evaluate(()=>loadProperty());
 assert.match(await p.locator('#status').innerText(),/Trace each roof section/);
 await p.evaluate(()=>{el('customerName').value='Fictional Mapbox QA';tracePoints=[[50.8885,-114.0291],[50.8885,-114.029],[50.8886,-114.029],[50.8886,-114.0291]].map(x=>L.latLng(x));el('pitchDeg').value='22.62';finishTrace();});
 const openPicker=p.locator('#workspaceRecoveryContinue');if(await openPicker.count())await openPicker.click();
 await p.locator('#createEstimateBtn').click();
 await p.locator('#downloadPdfBtn').waitFor({state:'visible'});
 const final=await (await context.request.get(url+'/qa-state')).json();
 assert.equal(final.estimates.length,2);assert.equal(final.estimate_revisions.length,1);
 const fresh=final.estimates.find(x=>x.id!==id), freshVersions=await getVersions(fresh.id);
 await verify(fresh.id,freshVersions);
 for(const layout of ['single','expanded']){
  await p.locator('#estimatePdfLayout').selectOption(layout);
  const dl=p.waitForEvent('download');await p.locator('#downloadPdfBtn').click();
  await (await dl).saveAs('/tmp/aq-mapbox-runtime/Mapbox_QA_'+layout+'.pdf');
 }
 await context.request.post(url+'/qa-provider',{data:{mode:'google'}});
 await p.reload();await p.waitForFunction(()=>window.aqRecovery&&!window.aqLocalMapbox);
 await verify(id,baseline);await verify(fresh.id,freshVersions);
 assert.deepEqual(await getVersions(id),baseline);assert.deepEqual(await getVersions(fresh.id),freshVersions);
 console.log('PASS Google fixture → Mapbox fixture with no Google key → rollback. Exact current/revision payloads, new Mapbox record, Chaparral cancel/confirm, both PDFs, no migration.',fresh.total_area,fresh.total_price);
 await context.close();
}}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
