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
  const marker=async (selector,index=0)=>{await page.locator('#map').scrollIntoViewIfNeeded();const b=await page.locator(selector).nth(index).boundingBox();assert(b);return{x:b.x+b.width/2,y:b.y+b.height/2};};
  await page.tap('#linearEditBtn');const before=await state();const start=await marker('.linear-point');const box=await page.locator('#map').boundingBox();const target={x:box.x+box.width-9,y:start.y+55};
  await drag(start,target,450);const moved=await state();
  console.log(JSON.stringify({width,editingMapDragging:before.dragging,centerBefore:before.center,centerAfter:moved.center,pointBefore:before.points[0],pointAfter:moved.points[0],events:moved.events}));
  assert.equal(before.dragging,false,'Map dragging must be disabled during line correction');assert.deepEqual(moved.center,before.center,'Touch endpoint drag near map edge must not pan aerial');assert.notDeepEqual(moved.points[0],before.points[0]);assert(moved.events.touch>0&&moved.events.pointer>0,'Must dispatch trusted touch and touch-pointer events, not mouse drags');assert.equal(moved.pinch,true);
  // Independent haversine distance from final saved endpoints, not Leaflet distance().
  const radians=x=>x*Math.PI/180,measure=pts=>pts.slice(1).reduce((n,p,i)=>{const a=pts[i],dlat=radians(p[0]-a[0]),dlng=radians(p[1]-a[1]);return n+2*6371000*Math.asin(Math.sqrt(Math.sin(dlat/2)**2+Math.cos(radians(a[0]))*Math.cos(radians(p[0]))*Math.sin(dlng/2)**2))*3.28084;},0);
  await page.tap('#linearSaveEditBtn');let saved=await state();assert(saved.dragging);assert(!saved.editing);assert(Math.abs(saved.feet-measure(saved.points))<.00001);
  // Use finger taps for Edit/Save too: repeat the actual same-line lifecycle.
  for(let cycle=0;cycle<4;cycle++){
   await page.tap('#linearEditBtn');const original=await state();assert(original.editing&&!original.dragging,'Repeated Edit tap must enter locked correction mode');
   const point=await marker('.linear-point',cycle%2);await drag(point,{x:point.x+(cycle%2?18:-18),y:point.y+32},100,1);const changed=await state();
   assert.deepEqual(changed.center,original.center,'Repeated touch correction must keep map stationary');assert.notDeepEqual(changed.points,original.points,'Repeated touch must move an endpoint');
   await page.tap('#linearSaveEditBtn');saved=await state();assert(!saved.editing&&saved.dragging);assert.deepEqual(saved.points,changed.points);assert(Math.abs(saved.feet-measure(saved.points))<.00001);
  }
  await page.tap('#linearEditBtn');assert.deepEqual((await state()).points,saved.points);const cancelStart=await marker('.linear-point');await drag(cancelStart,{x:cancelStart.x-22,y:cancelStart.y+25});assert.notDeepEqual((await state()).points,saved.points);await page.tap('#linearCancelEditBtn');assert.deepEqual((await state()).points,saved.points);assert((await state()).dragging);
  // Background single-finger pan stays locked while correcting. Background pinch still works.
  await page.tap('#linearEditBtn');await page.locator('#map').scrollIntoViewIfNeeded();const rect=await page.locator('#map').boundingBox(),middle={x:rect.x+rect.width/2,y:rect.y+440};const locked=await state();await drag(middle,{x:middle.x+35,y:middle.y-100},250,1);assert.deepEqual((await state()).center,locked.center);assert.deepEqual((await state()).points,locked.points,'A background gesture must not edit endpoint coordinates');
  await touch([{x:middle.x-35,y:middle.y},{x:middle.x+35,y:middle.y}],'touchStart');for(let i=1;i<=10;i++){await touch([{x:middle.x-35-i*2,y:middle.y},{x:middle.x+35+i*2,y:middle.y}],'touchMove');await page.waitForTimeout(20);}await touch([],'touchEnd');await page.waitForTimeout(350);assert((await state()).zoom>locked.zoom,'Two-finger background pinch remains available');assert.deepEqual((await state()).points,locked.points,'Pinch zoom must not alter saved coordinates');await page.tap('#linearCancelEditBtn');
  await page.locator('#map').scrollIntoViewIfNeeded();const normalBox=await page.locator('#map').boundingBox();const normalStart={x:normalBox.x+normalBox.width/2,y:normalBox.y+440};const normal=await state();await drag(normalStart,{x:normalStart.x+30,y:normalStart.y-20});assert.notDeepEqual((await state()).center,normal.center,'Normal map dragging must resume after cancel');
  // Respect a map that was already deliberately disabled, then cover new-property cleanup.
  await page.evaluate(()=>map.dragging.disable());await page.tap('#linearEditBtn');await page.tap('#linearSaveEditBtn');assert.equal((await state()).dragging,false);await page.evaluate(()=>map.dragging.enable());
  await page.tap('#customerName');await page.fill('#customerName','FICTIONAL TOUCH QA '+width);await page.selectOption('#streetViewChoice','none');await page.tap('#createEstimateBtn');await page.waitForFunction(()=>document.body.classList.contains('report-open'));await page.waitForFunction(()=>!estimateOpenInProgress);
  const rows=await(await context.request.get('http://127.0.0.1:8765/api/estimates')).json();const record=rows.find(r=>r.customer_name==='FICTIONAL TOUCH QA '+width);assert(record);const payload=(await(await context.request.get('http://127.0.0.1:8765/api/estimates/'+record.id)).json()).payload;assert.deepEqual(payload.quote.linearPoints.map(p=>Array.isArray(p)?p:[p.lat,p.lng]),saved.points);assert(Math.abs(payload.quote.linearFeet-saved.feet)<.00001);
  await page.goto('http://127.0.0.1:8765/?industry=snow');await page.waitForFunction(()=>typeof openHistoricalEstimate==='function');await page.evaluate(id=>openHistoricalEstimate(id,-1),record.id);await page.waitForFunction(()=>document.body.classList.contains('report-open'));assert.deepEqual(await page.evaluate(()=>quoteSnapshot.linearPoints.map(p=>Array.isArray(p)?p:[p.lat,p.lng])),saved.points);
  await page.tap('#backToDealerBtn');await page.waitForFunction(()=>savedPropertyEditActive&&!document.body.classList.contains('report-open'));
  assert.deepEqual((await state()).points,saved.points);await page.tap('#linearEditBtn');const restoredStart=await marker('.linear-point');await drag(restoredStart,{x:restoredStart.x-12,y:restoredStart.y+12});await page.tap('#linearCancelEditBtn');assert.deepEqual((await state()).points,saved.points);assert((await state()).dragging);
  // Repeat Save -> Edit after restoring an owned saved estimate as well.
  for(let cycle=0;cycle<2;cycle++){
   await page.tap('#linearEditBtn');const original=await state();assert(original.editing&&!original.dragging);assert.equal(await page.locator('#map').evaluate(n=>getComputedStyle(n).touchAction),'none');
   const point=await marker('.linear-point',cycle%2);await drag(point,{x:point.x+(cycle%2?12:-12),y:point.y+12},100,1);const changed=await state();assert.deepEqual(changed.center,original.center);assert.notDeepEqual(changed.points,original.points);
   await page.tap('#linearSaveEditBtn');const kept=await state();assert(!kept.editing&&kept.dragging);assert.deepEqual(kept.points,changed.points);assert(Math.abs(kept.feet-measure(kept.points))<.00001);
  }
  const reopenPolygonEstimate=async()=>{
   const expected=await page.evaluate(()=>JSON.stringify(captureQuoteSnapshot()));await page.tap('#createEstimateBtn');await page.waitForFunction(()=>document.body.classList.contains('report-open'));await page.waitForFunction(()=>!estimateOpenInProgress);
   const list=await(await context.request.get('http://127.0.0.1:8765/api/estimates')).json();const current=list.find(x=>x.id===record.id);assert(current,JSON.stringify(list));const stored=(await(await context.request.get('http://127.0.0.1:8765/api/estimates/'+current.id)).json()).payload;
   assert.deepEqual(stored.quote.commercialAreas,JSON.parse(expected).commercialAreas);assert.deepEqual(stored.quote.structures,JSON.parse(expected).structures);
   await page.goto('http://127.0.0.1:8765/?industry='+stored.quote.businessType);await page.waitForFunction(()=>typeof openHistoricalEstimate==='function');await page.evaluate(id=>openHistoricalEstimate(id,-1),current.id);await page.waitForFunction(()=>document.body.classList.contains('report-open'));await page.tap('#backToDealerBtn');await page.waitForFunction(()=>savedPropertyEditActive&&!document.body.classList.contains('report-open'));
  };
  // Area still receives touch drags after the Linear lock has been released.
  await page.evaluate(()=>{linearPoints=[];linearMeasurementSaved=false;clearLinearLayers();commercialAreas=[];commercialEditingIndex=-1;measurementViewMode='area';map.setView([52,-106],19,{animate:false});const n=map.getSize();areaPoints=[[65,210],[n.x-65,210],[n.x-65,340],[65,340]].map(p=>map.containerPointToLatLng(p));areaMeasurementSaved=true;areaMode=false;redrawAreaMeasure();updateLinearUi();correctAreaOutline();});
  if(process.env.QA_POLYGON_PROBE!=='roof')for(let cycle=0;cycle<3;cycle++){
   if(cycle)await page.evaluate(()=>correctAreaOutline());
   const original=await page.evaluate(()=>areaPoints.map(p=>[p.lat,p.lng]));const areaStart=await marker('.area-point');const originalCenter=(await state()).center;
   await drag(areaStart,{x:areaStart.x+10,y:areaStart.y+15});assert.notDeepEqual(await page.evaluate(()=>areaPoints.map(p=>[p.lat,p.lng])),original);assert.deepEqual((await state()).center,originalCenter);
   if(cycle===1){const r=await page.locator('#map').boundingBox();const before=(await state()).center;await drag({x:r.x+r.width/2,y:r.y+470},{x:r.x+r.width/2+35,y:r.y+445});console.log('SECOND AREA EDIT',width,{dragging:(await state()).dragging,before,after:(await state()).center});assert.deepEqual((await state()).center,before,'Second Area edit must keep aerial stationary even when touch misses a corner');}
   if(cycle===2){await page.evaluate(()=>cancelAreaCorrection());assert.deepEqual(await page.evaluate(()=>areaPoints.map(p=>[p.lat,p.lng])),original);}else{await page.evaluate(()=>toggleAreaMeasure());assert(await page.evaluate(()=>areaMeasurementSaved&&!areaMode));}
   assert((await state()).dragging);
  }
  if(process.env.QA_POLYGON_PROBE!=='roof'){
   await reopenPolygonEstimate();await page.evaluate(()=>commercialEditArea(0));const savedArea=await page.evaluate(()=>JSON.stringify(areaPoints));const p=await marker('.area-point');const center=(await state()).center;await drag(p,{x:p.x+10,y:p.y+12});assert.deepEqual((await state()).center,center);await page.evaluate(()=>cancelAreaCorrection());assert.equal(await page.evaluate(()=>JSON.stringify(areaPoints)),savedArea);assert((await state()).dragging);
  }
  // Fictional confirmed roof outline: touch a reviewed corner, then cancel safely.
  await page.evaluate(()=>{areaPoints=[];areaMode=false;areaCorrectionOriginal=null;areaMeasurementSaved=false;clearAreaLayers();commercialAreas=[];manualRoofQa=()=>false;el('businessType').value='roofing';applyBusinessTerminology();manualPlanes=[];const outline=[[51.99995,-106.00005],[51.99995,-105.99995],[52.00005,-105.99995],[52.00005,-106.00005]];structures=[{label:'FICTIONAL QA ROOF',latitude:52,longitude:-106,outline,manually_measured:true,total_roof_sqft:200,segment_count:1,segments:[{pitch_degrees:22.62}]}];startDetectedRoofReview(0);});
  for(let cycle=0;cycle<3;cycle++){
   if(cycle)await page.evaluate(()=>startDetectedRoofReview(0));await page.waitForTimeout(350);assert(await page.evaluate(()=>roofOutlineReviewMode&&traceMode));
   const roofBefore=await page.evaluate(()=>JSON.stringify(structures));const roofPoints=await page.evaluate(()=>tracePoints.map(p=>[p.lat,p.lng]));const roofStart=await marker('#map .point-label');const before=(await state()).center;const r=await page.locator('#map').boundingBox();
   await drag(roofStart,{x:cycle===1?r.x+10:roofStart.x+24,y:roofStart.y+30},cycle===1?450:0);assert.notDeepEqual(await page.evaluate(()=>tracePoints.map(p=>[p.lat,p.lng])),roofPoints);
   if(cycle===1){console.log('SECOND ROOF EDIT',width,{dragging:(await state()).dragging,before,after:(await state()).center});assert.deepEqual((await state()).center,before,'Second roof edit near edge must not pan aerial');}
   if(cycle===2){await page.evaluate(()=>cancelCurrentTrace());assert.equal(await page.evaluate(()=>JSON.stringify(structures)),roofBefore);}else{await page.selectOption('#roofReviewPitchSelect','custom');await page.fill('#roofReviewPitchDeg','22.62');await page.tap('#roofReviewBoundaryConfirmed');await page.tap('#finishTrace');assert(await page.evaluate(()=>!traceMode&&!roofOutlineReviewMode));}
   assert((await state()).dragging);
  }
  await reopenPolygonEstimate();await page.evaluate(()=>startDetectedRoofReview(0));await page.waitForTimeout(350);const savedRoof=await page.evaluate(()=>JSON.stringify(structures));const rp=await marker('#map .point-label');const rc=(await state()).center;await drag(rp,{x:rp.x+15,y:rp.y+18});assert.deepEqual((await state()).center,rc);await page.evaluate(()=>cancelCurrentTrace());assert.equal(await page.evaluate(()=>JSON.stringify(structures)),savedRoof);assert((await state()).dragging);
  // QA-only manual roof section editor has its own draggable polygon markers.
  await page.evaluate(()=>{manualRoofQa=()=>true;structures=[];manualPlanes=[];clearOverlays();clearManualDisplayLayers();map.setView([52,-106],19,{animate:false});const pts=[[51.99995,-106.00005],[51.99995,-105.99995],[52.00005,-105.99995],[52.00005,-106.00005]].map(p=>L.latLng(p));manualPlanes=[{points:pts,pitch_degrees:22.62,pitch_confirmed:true,surface_sqft:localPolygonAreaM2(pts)*10.76391041671/Math.cos(22.62*Math.PI/180)}];});
  for(let cycle=0;cycle<3;cycle++){
   await page.evaluate(()=>editManualRoofSection(0));const original=await page.evaluate(()=>JSON.stringify(manualPlanes));assert.equal((await state()).dragging,false);const before=(await state()).center;const point=await marker('#map .leaflet-marker-draggable');await drag(point,{x:point.x+12,y:point.y+15});assert.deepEqual((await state()).center,before);
   if(cycle===2){await page.evaluate(()=>cancelCurrentTrace());assert.equal(await page.evaluate(()=>JSON.stringify(manualPlanes)),original);}else{await page.selectOption('#pitchSel','22.62');await page.evaluate(()=>pitchChanged());await page.tap('#finishTrace');assert(await page.evaluate(()=>!traceMode&&manualPlanes.length===1));}
   assert((await state()).dragging);
  }
  assert.deepEqual(errors,[]);results.push({width,touchEvents:moved.events,savedFeet:saved.feet,mapStationary:true,pinch:true,saveCancel:true,reopened:true,savedEditing:true,areaTouch:true,roofTouchCancel:true,repeatedSaveCycles:5,reopenedSaveCycles:2,touchControls:true,nativeScrollLocked:true,areaSecondEdit:true,roofSecondEdit:true,manualRoofRepeatedEdit:true,polygonEstimateReopening:true});await page.screenshot({path:output+'/linear-touch-'+width+'.png',fullPage:false});await context.close();console.log('PASS touch linear / Area / roof',width);
 }
 fs.writeFileSync(output+'/results.json',JSON.stringify(results,null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
