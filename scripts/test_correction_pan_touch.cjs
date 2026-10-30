// Real Chromium touch/pointer dispatch against the disposable loopback fixture ONLY.
// Not a physical-device test. Never target a deployed account or imagery provider.
const {chromium}=require('playwright'),assert=require('assert/strict'),fs=require('fs'),path=require('path');
const deps=path.dirname(path.dirname(require.resolve('leaflet/package.json')));
const output=process.env.QA_TOUCH_OUTPUT||'/tmp/aq-linear-touch';fs.mkdirSync(output,{recursive:true});
const grid='<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="1280"><defs><pattern id="g" width="80" height="80" patternUnits="userSpaceOnUse"><rect width="80" height="80" fill="#edf1ef" stroke="#b4c5c0"/></pattern></defs><rect width="1280" height="1280" fill="url(#g)"/><text x="40" y="40">FICTIONAL TOUCH QA</text></svg>';
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});const results=[];
 try{for(const width of [320,390,768]){
  const context=await browser.newContext({viewport:{width,height:process.env.QA_EMBEDDED?844:1100},hasTouch:true,isMobile:true,deviceScaleFactor:1,...(process.env.QA_EMBEDDED?{userAgent:'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 [FBAN/MessengerForiOS;FBAV/500.0]'}:{})});
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
    assert.deepEqual(x.polys,x.snap.commercialAreas.map(a=>a.points));assert.equal(x.lines.length,x.snap.linearPoints.length-1);x.lines.forEach((p,i)=>assert.deepEqual(p,[x.snap.linearPoints[i],x.snap.linearPoints[i+1]]));assert.equal(x.svg,'');assert.equal(x.handles,0);assert.equal(x.visual,null);assert.equal(await page.getByRole('button',{name:'RETRACE OUTLINE — AREA 1',exact:true}).count(),1);assert.equal(await page.getByRole('button',{name:'RETRACE OUTLINE — AREA 2',exact:true}).count(),1);assert.equal(await page.getByRole('button',{name:'CORRECT LINEAR MEASUREMENT',exact:true}).count(),1);
   };
   await page.locator('#map').scrollIntoViewIfNeeded();const r=await page.locator('#map').boundingBox();await drag({x:r.x+r.width/2,y:r.y+450},{x:r.x+r.width/2+30,y:r.y+420});
   assert(await page.evaluate(()=>map.dragging.moved()));await create();await checkReport();
   await page.getByRole('button',{name:'RETRACE OUTLINE — AREA 1',exact:true}).tap();await page.locator('#customerMap').scrollIntoViewIfNeeded();await page.waitForTimeout(500);const b=await page.locator('#customerMap').boundingBox();if(industry==='snow')await page.screenshot({path:output+'/retrace-empty-'+width+'.png'});
   const protectedOriginal=await page.evaluate(()=>JSON.stringify({areas:commercialAreas,line:linearPoints,total:priceCalc().total,quote:quoteSnapshot}));
   for(let i=0;i<3;i++){await page.touchscreen.tap(b.x+80+i*40,b.y+100);assert.equal(await page.evaluate(()=>reportMeasurementCorrection.points.length),i+1,'Each tap must reach the draft');}
   for(let i=0;i<3;i++)await page.tap('#reportUndoOutlineBtnTop');assert.equal(await page.evaluate(()=>reportMeasurementCorrection.points.length),0,'Undo must return to empty, never the original polygon');
   const ring=await page.evaluate(()=>{const p=commercialAreas[0].points.map(v=>customerMap.latLngToContainerPoint(v)),l=Math.min(...p.map(v=>v.x)),r=Math.max(...p.map(v=>v.x)),t=Math.min(...p.map(v=>v.y)),b=Math.max(...p.map(v=>v.y)),x=l+(r-l)*.15,y=t+(b-t)*.15,w=(r-l)*.7,h=(b-t)*.7;return [[x,y],[x+w,y],[x+w,y+h*.5],[x+w*.5,y+h*.5],[x+w*.5,y+h],[x,y+h]]});
   for(const p of ring)await page.touchscreen.tap(b.x+p[0],b.y+p[1]);assert.equal(await page.evaluate(()=>reportCorrectionProblem()),'');assert.equal(await page.evaluate(()=>JSON.stringify({areas:commercialAreas,line:linearPoints,total:priceCalc().total,quote:quoteSnapshot})),protectedOriginal);
   await page.evaluate(()=>{window.termCalls=0;window.qaOriginalTerm=window.qaOriginalTerm||applyBusinessTerminology;applyBusinessTerminology=function(...a){termCalls++;return qaOriginalTerm(...a)};renderSummary()});await page.waitForTimeout(1200);assert(await page.evaluate(()=>termCalls<=3),'Wording observer must settle, not loop');assert.deepEqual(errors,[]);await page.tap('#reportCancelOutlineBtnTop');assert(await page.evaluate(()=>customerMap.dragging.enabled()&&!reportMeasurementCorrection));assert.equal(await page.evaluate(()=>JSON.stringify({areas:commercialAreas,line:linearPoints,total:priceCalc().total,quote:quoteSnapshot})),protectedOriginal);await checkReport();results.push({width,industry,firstThreeTouches:true,previousPan:true,terminologyPasses:await page.evaluate(()=>termCalls),embeddedUserAgent:!!process.env.QA_EMBEDDED});console.log('PASS first taps after report and prior pan',width,industry);
  }
  await context.close();
 }
 fs.writeFileSync(output+'/first-tap-results.json',JSON.stringify(results,null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
