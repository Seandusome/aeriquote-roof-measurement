// Opt-in real Chromium QA against prelaunch_browser_server.py only; fixture imagery, no physical devices.
const grid='<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="1280"><defs><pattern id="g" width="80" height="80" patternUnits="userSpaceOnUse"><rect width="80" height="80" fill="#edf1ef" stroke="#b4c5c0"/></pattern></defs><rect width="1280" height="1280" fill="url(#g)"/><text x="40" y="40">FICTIONAL QA IMAGERY - NOT A REAL PROPERTY</text></svg>';
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert/strict');
const path=require('path'),deps=path.dirname(path.dirname(require.resolve('leaflet/package.json'))),output=process.env.QA_BROWSER_OUTPUT||'/tmp/aq-prelaunch';fs.mkdirSync(output,{recursive:true});
const widths=(process.env.QA_BROWSER_WIDTHS||'1440,390,768').split(',').map(Number),industries=(process.env.QA_BROWSER_INDUSTRIES||'snow,pressure,paving,landscaping,commercial,roofing').split(',');
assert(widths.every(w=>[320,390,768,1440].includes(w)));assert(industries.every(i=>['snow','pressure','paving','landscaping','commercial','roofing'].includes(i)));const imageChoice=process.env.QA_BROWSER_IMAGES||'none';assert(['none','hide'].includes(imageChoice));
(async()=>{const browser=await chromium.launch({headless:true,args:['--no-sandbox']});const results=[];
for(const width of widths)for(const industry of industries){
 const context=await browser.newContext({viewport:{width,height:1000},acceptDownloads:true});const page=await context.newPage();const errors=[];console.log('START',industry,width);page.setDefaultTimeout(10000);page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
 await context.route('**/*',async r=>{const u=new URL(r.request().url());let f;
 if(u.hostname==='unpkg.com'){if(u.pathname.includes('leaflet.js'))f=deps+'/leaflet/dist/leaflet.js';else if(u.pathname.includes('leaflet.css'))f=deps+'/leaflet/dist/leaflet.css';else return r.fulfill({body:''});}
 if(u.hostname==='cdnjs.cloudflare.com')f=u.pathname.includes('html2canvas')?deps+'/html2canvas/dist/html2canvas.min.js':deps+'/jspdf/dist/jspdf.umd.min.js';
 if(f)return r.fulfill({path:f,contentType:f.endsWith('.css')?'text/css':'text/javascript'});
 if(u.hostname!=='127.0.0.1')return r.abort();
 if(/^\/(wide-aerial|fallback-map|exact-pin-map)\//.test(u.pathname))return r.fulfill({body:grid,contentType:'image/svg+xml'});
 if(u.pathname.startsWith('/street/'))return r.fulfill({status:404,body:'QA street image intentionally unavailable'});
 if(u.pathname==='/address-preview')return r.fulfill({json:{formatted_address:'1 Fictional QA Street, Saskatoon, SK, Canada',parts:{},verified:true}});
 if(u.pathname==='/mapbox-test')return r.fulfill({json:{}});
 if(u.pathname.startsWith('/manual-report-map/')||u.pathname==='/saved-estimate-report-map')return r.fulfill({body:grid,contentType:'image/svg+xml',headers:{'X-AeriQuote-Map-View':JSON.stringify({latitude:52,longitude:-106,zoom:19,width:640,height:420})}});
 return r.continue();});
 await page.goto('http://127.0.0.1:8765/login');await page.fill('#loginEmail','qa-browser@example.invalid');await page.fill('#loginPassword','fictional-qa-password');await Promise.all([page.waitForURL(u=>u.pathname!='/login'),page.click('button')]);
 await page.goto('http://127.0.0.1:8765/?industry='+industry);await page.waitForFunction(()=>typeof map!=='undefined'&&typeof renderSummary==='function');await page.waitForTimeout(400);
 // Selecting the current QA industry's profile is fixture setup, not a UI usability assertion.
 await page.evaluate(i=>{el('businessType').value=i;businessTypeChanged();el('jobPrice').value='.1';el('dealerCompany').value='FICTIONAL QA COMPANY';el('gst').value='5';el('pst').value='6';},industry);
 await page.fill('#streetAddress','1 Fictional QA Street');await page.fill('#cityTown','Saskatoon');await page.selectOption('#propertyProvince','SK');
 await page.click('#propertyActionBtn');console.log('clicked property');
 await page.waitForFunction(()=>!!sessionToken,{timeout:30000});await page.waitForTimeout(400);
 const draw=async pts=>{await page.locator('#map').scrollIntoViewIfNeeded();for(const p of pts){const xy=await page.evaluate(([lat,lng])=>{const p=map.latLngToContainerPoint([lat,lng]);const r=el('map').getBoundingClientRect();return{x:r.left+p.x,y:r.top+p.y};},p);const previous=await page.evaluate(()=>areaMode?areaPoints.length:traceMode?tracePoints.length:linearPoints.length);await page.mouse.click(xy.x,xy.y);assert.equal(await page.evaluate(()=>areaMode?areaPoints.length:traceMode?tracePoints.length:linearPoints.length),previous+1,'Every intended corner must be recorded, including clicks beneath the property pin');}};
 await page.evaluate(()=>map.setView([52,-106],19,{animate:false}));await page.waitForTimeout(100);
 console.log('loaded',await page.locator('#status').textContent());const pts=[[51.99995,-106.00012],[51.99995,-106.00002],[52.00003,-106.00002],[52.00003,-106.00012]];
 if(industry==='roofing'){
  if(!await page.evaluate(()=>traceMode))await page.click('#toolAreaBtn');await draw(pts);await page.selectOption('#pitchSel','22.62');await page.evaluate(()=>pitchChanged());await page.evaluate(()=>finishTrace());
  await page.click('#manualRoofScopeConfirmed');
 }else{
  await draw(pts);await page.click('#areaStartBtn');await page.click('#toolAreaBtn');await draw(pts.map(([lat,lng])=>[lat+.00014,lng]));await page.click('#areaStartBtn');
  await page.click('#toolAreaBtn');await page.click('#toolLinearBtn');await draw([[51.99995,-105.9999],[52.00012,-105.9999]]);await page.click('#linearStartBtn');
 }
 console.log('drawn',await page.evaluate(()=>({areas:commercialAreas.length,points:areaPoints.length,line:linearPoints.length,manual:manualPlanes.length,status:el('status').textContent})));await page.click('#customerName');await page.fill('#customerName',`FICTIONAL QA ${industry} ${width}`);await page.click('#customerEmail');await page.fill('#customerEmail','fictional-customer@example.invalid');await page.click('#customerPhone');await page.fill('#customerPhone','555-0100');await page.selectOption('#streetViewChoice',imageChoice);
 const before=await page.evaluate(()=>({snapshot:captureQuoteSnapshot(),pricing:priceCalc(),overflow:document.documentElement.scrollWidth>innerWidth}));
 assert.equal(await page.locator('#createEstimateBtn').isDisabled(),false,industry+' '+width+' '+await page.locator('#status').textContent());
 if(industry==='snow'&&width===1440){const frozen=JSON.stringify(before.snapshot);await page.route('**/api/estimates',r=>r.request().method()==='POST'?r.abort():r.continue());await page.click('#createEstimateBtn');await page.waitForFunction(()=>!estimateOpenInProgress);assert.equal(await page.evaluate(()=>document.body.classList.contains('report-open')),false);assert.equal(await page.evaluate(()=>JSON.stringify(captureQuoteSnapshot())),frozen);await page.unroute('**/api/estimates');console.log('PASS browser aborted save preserves measurements and blocks report');}
 await page.click('#createEstimateBtn');await page.waitForFunction(()=>document.body.classList.contains('report-open'),{timeout:10000});
 await page.waitForFunction(()=>!estimateOpenInProgress);
 assert((await page.locator('#rPricing').textContent()).includes(await page.evaluate(()=>money(priceCalc().total))));
 console.log('report opened');const list=await (await context.request.get('http://127.0.0.1:8765/api/estimates')).json();const saved=list.find(x=>x.customer_name===`FICTIONAL QA ${industry} ${width}`);assert(saved,'save missing');
 const payload=(await(await context.request.get('http://127.0.0.1:8765/api/estimates/'+saved.id)).json()).payload;
 assert.equal(payload.total_price,before.pricing.total);assert.equal(payload.customer_name,`FICTIONAL QA ${industry} ${width}`);
 fs.writeFileSync(`${output}/${industry}-${width}-source.json`,JSON.stringify(payload,null,2));
 // A second page load simulates refresh; reopen the owned stored snapshot through the actual handler.
 await page.goto('http://127.0.0.1:8765/?industry='+industry);await page.waitForFunction(()=>typeof openHistoricalEstimate==='function');await page.waitForTimeout(300);
 await page.evaluate(id=>openHistoricalEstimate(id,-1),saved.id);await page.waitForFunction(()=>document.body.classList.contains('report-open'));
 assert.equal(await page.evaluate(()=>quoteSnapshot.savedPricing.total),before.pricing.total);
 assert.equal(await page.locator('#rCustomerName').textContent(),payload.customer_name);
 const savedFrame=await page.locator('#customerMap canvas[data-map-view]').evaluate(n=>{const r=n.getBoundingClientRect();return{source:n.width/n.height,display:r.width/r.height}});assert(Math.abs(savedFrame.display/savedFrame.source-1)<.001,'Reopened saved aerial must retain intrinsic proportions');
 const captureChecks=[];const pdfState=await page.evaluate(()=>({quote:JSON.stringify(quoteSnapshot),price:el('rPricing').textContent,customer:el('rCustomerName').textContent,company:el('rEstimateSubtitle').textContent}));
 await page.exposeFunction('qaRecordPdfImage',check=>captureChecks.push(check));
 await page.evaluate(()=>{const capture=window.html2canvas;window.html2canvas=async(node,options)=>{
  const image=node.querySelector?.('[data-expanded-aerial]');
  if(image){const box=image.getBoundingClientRect(),ratio=image.naturalWidth/image.naturalHeight;if(Math.abs(box.width/box.height/ratio-1)>.001)throw Error('Expanded aerial CSS dimensions distort source pixels');await window.qaRecordPdfImage({sourceWidth:image.naturalWidth,sourceHeight:image.naturalHeight,drawWidth:box.width,drawHeight:box.height});}
  return capture(node,options);
 };});
 const pdfs=[];
 if(process.env.QA_BROWSER_ALL_PDFS==='1'||width===1440||industry==='snow'){for(const layout of ['single','expanded']){await page.selectOption('#estimatePdfLayout',layout);const wait=page.waitForEvent('download',{timeout:45000});await page.click('#downloadPdfBtn');const dl=await wait;const destination=`${output}/${industry}-${width}-${layout}.pdf`;await dl.saveAs(destination);pdfs.push(destination);assert.deepEqual(await page.evaluate(()=>({quote:JSON.stringify(quoteSnapshot),price:el('rPricing').textContent,customer:el('rCustomerName').textContent,company:el('rEstimateSubtitle').textContent})),pdfState,'PDF export preserves stored geometry, pricing, customer and branding');}}
 await page.screenshot({path:`${output}/${industry}-${width}.png`,fullPage:true});
 assert.deepEqual(errors,[],'No browser script errors');assert.equal(before.overflow,false,'Workspace must not overflow');results.push({industry,width,total:before.pricing.total,overflow:before.overflow,errors,pdfs,captureChecks,saved:true,reopened:true});fs.writeFileSync(output+'/results.json',JSON.stringify(results,null,2));console.log(JSON.stringify(results.at(-1)));await context.close();
}
await browser.close();})().catch(e=>{console.error(e);process.exit(1)});
