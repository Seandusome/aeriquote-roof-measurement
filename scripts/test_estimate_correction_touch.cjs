// Real Chromium touch/pointer dispatch against the disposable loopback fixture ONLY.
// Not a physical-device test. Never target a deployed account or imagery provider.
const {chromium}=require('playwright'),assert=require('assert/strict'),fs=require('fs'),path=require('path');
const deps=path.dirname(path.dirname(require.resolve('leaflet/package.json')));
const output=process.env.QA_TOUCH_OUTPUT||'/tmp/aq-linear-touch';fs.mkdirSync(output,{recursive:true});
const grid='<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="1280"><defs><pattern id="g" width="80" height="80" patternUnits="userSpaceOnUse"><rect width="80" height="80" fill="#edf1ef" stroke="#b4c5c0"/></pattern></defs><rect width="1280" height="1280" fill="url(#g)"/><text x="40" y="40">FICTIONAL TOUCH QA</text></svg>';
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});const results=[];
 try{for(const width of [320,390,768]){
  const context=await browser.newContext({viewport:{width,height:1100},hasTouch:true,isMobile:true,deviceScaleFactor:1});
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
  await context.route('**/*',async r=>{
   const u=new URL(r.request().url());let f;
   if(u.hostname==='unpkg.com'){if(u.pathname.includes('leaflet.js'))f=deps+'/leaflet/dist/leaflet.js';else if(u.pathname.includes('leaflet.css'))f=deps+'/leaflet/dist/leaflet.css';else return r.fulfill({body:''});}
   if(u.hostname==='cdnjs.cloudflare.com')f=u.pathname.includes('html2canvas')?deps+'/html2canvas/dist/html2canvas.min.js':deps+'/jspdf/dist/jspdf.umd.min.js';
   if(f)return r.fulfill({path:f,contentType:f.endsWith('.css')?'text/css':'text/javascript'});
   if(u.hostname!=='127.0.0.1')return r.abort();
   if(/^\/(wide-aerial|fallback-map|exact-pin-map|manual-report-map)\//.test(u.pathname)||u.pathname==='/saved-estimate-report-map')return r.fulfill({body:grid,contentType:'image/svg+xml',headers:{'X-AeriQuote-Map-View':JSON.stringify({latitude:52,longitude:-106,zoom:19,width:640,height:420})}});
   if(u.pathname.startsWith('/street/'))return r.fulfill({status:404,body:''});
   if(u.pathname==='/address-preview')return r.fulfill({json:{formatted_address:'1 Fictional QA Street, Saskatoon, SK, Canada',parts:{},verified:true}});
   return r.continue();
  });
  await page.goto('http://127.0.0.1:8765/dealer-login');await page.fill('#loginEmail','qa-browser@example.invalid');await page.fill('#loginPassword','fictional-qa-password');await Promise.all([page.waitForURL('http://127.0.0.1:8765/'),page.click('button')]);
  await page.goto('http://127.0.0.1:8765/?industry=snow');await page.waitForFunction(()=>typeof map!=='undefined');
  await page.fill('#streetAddress','1 Fictional QA Street');await page.fill('#cityTown','Saskatoon');await page.selectOption('#propertyProvince','SK');await page.tap('#propertyActionBtn');await page.waitForFunction(()=>!!sessionToken);
  await page.evaluate(()=>{areaMode=false;areaPoints=[];areaMeasurementSaved=false;commercialAreas=[];clearAreaLayers();measurementViewMode='linear';pendingMeasurementMode='linear';linearMode=false;map.setView([52,-106],19,{animate:false});const size=map.getSize();linearPoints=[map.containerPointToLatLng([size.x-65,220]),map.containerPointToLatLng([60,340])];linearMeasurementSaved=true;redrawLinearMeasure();updateMeasurementInterface();renderSummary();window.touchQaEvents={touch:0,pointer:0};el('map').addEventListener('touchstart',e=>{if(e.isTrusted)touchQaEvents.touch++},{capture:true});el('map').addEventListener('pointerdown',e=>{if(e.isTrusted&&e.pointerType==='touch')touchQaEvents.pointer++},{capture:true});});
  const cdp=await context.newCDPSession(page);
  const touch=async(points,type)=>cdp.send('Input.dispatchTouchEvent',{type,touchPoints:points.map((p,i)=>({x:p.x,y:p.y,id:i+1,radiusX:5,radiusY:5,force:1}))});
  const drag=async(from,to,hold=0,steps=16)=>{await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));const scrollState=await page.evaluate(()=>({y:scrollY,top:el('map').getBoundingClientRect().top,editing:!!linearCorrectionOriginal||!!areaCorrectionOriginal||roofOutlineReviewMode||(traceMode&&manualRoofEditIndex!==null)}));await touch([from],'touchStart');for(let i=1;i<=steps;i++){await touch([{x:from.x+(to.x-from.x)*i/steps,y:from.y+(to.y-from.y)*i/steps}],'touchMove');await page.waitForTimeout(18);}if(hold)await page.waitForTimeout(hold);if(scrollState.editing){const endScroll=await page.evaluate(()=>({y:scrollY,top:el('map').getBoundingClientRect().top}));assert(Math.abs(endScroll.top-scrollState.top)<1,'A touch gesture during correction moved the aerial on screen: '+JSON.stringify({before:scrollState,after:endScroll}));}await touch([],'touchEnd');await page.waitForTimeout(160);};
  const state=()=>page.evaluate(()=>({center:[map.getCenter().lat,map.getCenter().lng],points:linearPoints.map(p=>[p.lat,p.lng]),feet:linearFeetTotal(),dragging:map.dragging.enabled(),zoom:map.getZoom(),pinch:map.touchZoom.enabled(),editing:!!linearCorrectionOriginal,events:window.touchQaEvents||{touch:0,pointer:0}}));
  const marker=async (selector,index=0)=>{await page.locator('#map').scrollIntoViewIfNeeded();await page.waitForTimeout(500);const b=await page.locator(selector).nth(index).boundingBox();assert(b);return{x:b.x+b.width/2,y:b.y+b.height/2};};

  await page.waitForTimeout(1000);
  for(const industry of ['snow','pressure','paving','landscaping','commercial']){
   await page.evaluate(industry=>{
    resetReportForNewProperty();resetMeasurementForNewProperty();el('businessType').value=industry;applyBusinessTerminology();el('address').value='Fictional QA Report '+industry+' '+innerWidth;measurementViewMode='linear';pendingMeasurementMode='linear';map.setView([52,-106],19,{animate:false});const n=map.getSize();
    commercialAreas=[[[60,180],[n.x-65,180],[n.x-65,280],[60,280]],[[60,380],[n.x-65,380],[n.x-65,480],[60,480]]].map((ring,i)=>{const pts=ring.map(p=>map.containerPointToLatLng(p));return{name:'QA Area '+(i+1),source:'manual',rate:.12+i*.11,points:pts.map(p=>[p.lat,p.lng]),sqft:Math.round(localPolygonAreaM2(pts)*10.76391041671)}});
    areaPoints=[];areaMode=false;areaMeasurementSaved=false;commercialEditingIndex=-1;linearPoints=[[40,320],[n.x-40,320]].map(p=>map.containerPointToLatLng(p));linearMeasurementSaved=true;savedLinearJobRate=.3;el('jobPrice').value='.3';if(el('commercialLinearRate'))el('commercialLinearRate').value='.3';el('customerName').value='FICTIONAL REPORT QA '+industry+' '+innerWidth;el('gst').value='5';el('pst').value='6';el('pricingMode').value='regular';el('streetViewChoice').value='assessment';redrawLinearMeasure();commercialAreaDrawSaved();renderSummary();if(el('commercialLinearRate'))el('commercialLinearRate').value='.3';renderSummary();
   },industry);
   const workspace=()=>page.evaluate(()=>JSON.stringify({areas:commercialAreas,line:linearPoints.map(p=>[p.lat,p.lng]),price:priceCalc().total,customer:el('customerName').value},(k,v)=>v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.entries(v).sort(([a],[b])=>a.localeCompare(b))):v));
   const create=async()=>{await page.tap('#createEstimateBtn');await page.waitForFunction(()=>document.body.classList.contains('report-open')&&!estimateOpenInProgress&&!!customerMap);};
   const checkReport=async()=>{
    const x=await page.evaluate(()=>({polys:customerOverlays.filter(p=>p instanceof L.Polygon).map(p=>p.getLatLngs()[0].map(v=>[v.lat,v.lng])),lines:customerOverlays.filter(p=>p instanceof L.Polyline&&!(p instanceof L.Polygon)).map(p=>p.getLatLngs().map(v=>[v.lat,v.lng])),snap:quoteSnapshot,svg:el('reportDrawLayer').innerHTML,handles:el('customerMap').querySelectorAll('.leaflet-marker-draggable').length,visual:visualCorrectionMode}));
    assert.deepEqual(x.polys,x.snap.commercialAreas.map(a=>a.points));assert.equal(x.lines.length,x.snap.linearPoints.length-1);x.lines.forEach((p,i)=>assert.deepEqual(p,[x.snap.linearPoints[i],x.snap.linearPoints[i+1]]));assert.equal(x.svg,'');assert.equal(x.handles,0);assert.equal(x.visual,null);assert.equal(await page.getByRole('button',{name:'REMEASURE AREA 1',exact:true}).count(),1);assert.equal(await page.getByRole('button',{name:'REMEASURE AREA 2',exact:true}).count(),1);assert.equal(await page.getByRole('button',{name:'EDIT LINEAR MEASUREMENT',exact:true}).count(),1);
   };
   await create();await checkReport();
   const original=await workspace();
   for(const index of [0,1]){
    await page.getByRole('button',{name:'REMEASURE AREA '+(index+1),exact:true}).tap();await page.waitForFunction(()=>areaRemeasureMode&&!document.body.classList.contains('report-open'));assert.equal(await workspace(),original);
    await page.locator('#map').scrollIntoViewIfNeeded();await page.waitForTimeout(500);const b=await page.locator('#map').boundingBox();await page.touchscreen.tap(b.x+80,b.y+200);assert(await page.locator('#areaStartBtn').isDisabled());await page.tap('#areaCancelCorrectionBtn');assert.equal(await workspace(),original);await create();await checkReport();
   }
   for(let cycle=0;cycle<2;cycle++){
    const before=JSON.parse(await workspace());await page.getByRole('button',{name:'REMEASURE AREA 1',exact:true}).tap();await page.waitForFunction(()=>areaRemeasureMode);await page.locator('#map').scrollIntoViewIfNeeded();await page.waitForTimeout(500);const b=await page.locator('#map').boundingBox();
    const center=await page.evaluate(()=>[map.getCenter().lat,map.getCenter().lng]);
    for(const [x,y]of [[75,195+cycle*5],[b.width-80,195+cycle*5],[b.width-80,260],[75,260]])await page.touchscreen.tap(b.x+x,b.y+y);
    assert.equal(await page.evaluate(()=>replacementAreaError()),'');assert.equal(await workspace(),JSON.stringify(before));assert.deepEqual(await page.evaluate(()=>[map.getCenter().lat,map.getCenter().lng]),center);await page.tap('#areaStartBtn');const after=JSON.parse(await workspace());assert.notDeepEqual(after.areas[0].points,before.areas[0].points);assert.deepEqual(after.areas[1],before.areas[1]);assert.deepEqual(after.line,before.line);assert.equal(after.customer,before.customer);await create();await checkReport();
   }
   const beforeLine=JSON.parse(await workspace());await page.getByRole('button',{name:'EDIT LINEAR MEASUREMENT',exact:true}).tap();await page.waitForFunction(()=>!!linearCorrectionOriginal);await page.locator('#map').scrollIntoViewIfNeeded();let point=await marker('#map .linear-point');const center=await page.evaluate(()=>[map.getCenter().lat,map.getCenter().lng]);await drag(point,{x:point.x+12,y:point.y+18});await page.tap('#linearCancelEditBtn');assert.equal(await workspace(),JSON.stringify(beforeLine));await create();await checkReport();
   await page.getByRole('button',{name:'EDIT LINEAR MEASUREMENT',exact:true}).tap();await page.waitForFunction(()=>!!linearCorrectionOriginal);point=await marker('#map .linear-point');const center2=await page.evaluate(()=>[map.getCenter().lat,map.getCenter().lng]);await drag(point,{x:point.x+12,y:point.y+18});assert.deepEqual(await page.evaluate(()=>[map.getCenter().lat,map.getCenter().lng]),center2);await page.tap('#linearSaveEditBtn');const intended=JSON.parse(await workspace());assert.deepEqual(intended.areas,beforeLine.areas);assert.notDeepEqual(intended.line,beforeLine.line);await create();await checkReport();
   // Independent haversine length and integer-cent item/tax arithmetic.
   const snap=await page.evaluate(()=>quoteSnapshot);const rad=x=>x*Math.PI/180;const feet=snap.linearPoints.slice(1).reduce((n,p,i)=>{const a=snap.linearPoints[i],dlat=rad(p[0]-a[0]),dlng=rad(p[1]-a[1]);return n+2*6371000*Math.asin(Math.sqrt(Math.sin(dlat/2)**2+Math.cos(rad(a[0]))*Math.cos(rad(p[0]))*Math.sin(dlng/2)**2))*3.28084;},0);assert(Math.abs(feet-snap.linearFeet)<1e-5);
   const rows=await(await context.request.get('http://127.0.0.1:8765/api/estimates')).json();const record=rows.find(r=>r.customer_name===intended.customer);assert(record);const payload=(await(await context.request.get('http://127.0.0.1:8765/api/estimates/'+record.id)).json()).payload;
   assert.deepEqual(payload.quote.commercialAreas,intended.areas);assert.deepEqual(payload.quote.linearPoints,intended.line);assert.equal(payload.pricing.total,intended.price);fs.writeFileSync(output+'/'+industry+'-'+width+'-payload.json',JSON.stringify(payload,null,2));
   const cents=Math.round(feet*100)/100*.3+intended.areas.reduce((n,a)=>n+Math.round(a.sqft*a.rate*100)/100,0);const base=Math.round(cents*100);const total=(base+Math.round(base*.05)+Math.round(base*.06))/100;assert(Math.abs(total-intended.price)<.011,JSON.stringify({total,price:intended.price,pricing:payload.pricing}));
   for(const layout of ['single','expanded']){await page.selectOption('#estimatePdfLayout',layout);const pending=page.waitForEvent('download');await page.tap('#downloadPdfBtn');const download=await pending;assert.equal(await download.failure(),null);await download.saveAs(output+'/'+industry+'-'+width+'-'+layout+'.pdf');await page.waitForFunction(()=>!pdfInProgress);}
   if(industry==='snow')await page.locator('#customerMap').screenshot({path:output+'/corrected-'+width+'.png'});
   await page.evaluate(async id=>{resetReportForNewProperty();await openHistoricalEstimate(id,-1)},record.id);assert.deepEqual(await page.evaluate(()=>quoteSnapshot.commercialAreas),intended.areas);assert.deepEqual(await page.evaluate(()=>quoteSnapshot.linearPoints),intended.line);assert.equal(await page.evaluate(()=>quoteSnapshot.savedPricing.total),intended.price);
   // Merely reopening/exporting must not rewrite the saved version.
   const afterPayload=(await(await context.request.get('http://127.0.0.1:8765/api/estimates/'+record.id)).json()).payload;assert.deepEqual(afterPayload,payload);
   await page.evaluate(()=>resetReportForNewProperty());assert.deepEqual(errors,[]);results.push({industry,width,repeatedAreaSave:true,areaCancel:true,lineSaveCancel:true,exactSavedOverlays:true,independentLengthPricing:true,reopened:true,pdfs:['single','expanded'],trustedTouch:true});console.log('PASS estimate correction',width,industry);
  }
  await context.close();
 }
 fs.writeFileSync(output+'/results.json',JSON.stringify(results,null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
