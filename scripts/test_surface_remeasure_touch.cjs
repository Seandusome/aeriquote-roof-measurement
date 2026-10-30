// Uses only the existing isolated loopback touch harness; no deployed accounts.
const fs=require('fs'),assert=require('assert/strict');
let script=fs.readFileSync('scripts/test_linear_touch_browser.cjs','utf8');
const anchor="  await page.tap('#linearEditBtn');const before=";const at=script.indexOf(anchor);assert(at>0);
script=script.slice(0,at)+String.raw`
  await page.waitForTimeout(1100);
  for(const industry of ['snow','pressure','paving','landscaping','commercial']){
   await page.evaluate(industry=>{
    resetReportForNewProperty();resetMeasurementForNewProperty();el('address').value='Fictional QA '+industry+' '+innerWidth;el('businessType').value=industry;applyBusinessTerminology();measurementViewMode='area';pendingMeasurementMode='area';
    map.setView([52,-106],19,{animate:false});const n=map.getSize();
    commercialAreas=[[[60,180],[n.x-65,180],[n.x-65,280],[60,280]],[[60,380],[n.x-65,380],[n.x-65,480],[60,480]]].map((ring,i)=>{const pts=ring.map(p=>map.containerPointToLatLng(p));return{name:'QA Area '+(i+1),rate:.12+i*.11,source:'manual',points:pts.map(p=>[p.lat,p.lng]),sqft:Math.round(localPolygonAreaM2(pts)*10.76391041671)}});
    areaPoints=[];areaMode=false;areaMeasurementSaved=false;commercialEditingIndex=-1;linearPoints=[[40,320],[n.x-40,320]].map(p=>map.containerPointToLatLng(p));linearMeasurementSaved=true;savedLinearJobRate=.3;el('jobPrice').value='.3';if(el('commercialLinearRate'))el('commercialLinearRate').value='.3';
    el('customerName').value='FICTIONAL REMEASURE QA';el('customerEmail').value='qa@example.invalid';el('gst').value='5';el('pst').value='6';
    redrawLinearMeasure();commercialAreaDrawSaved();updateAreaUi();renderSummary();
   },industry);
   const record=()=>page.evaluate(()=>JSON.stringify({areas:commercialAreas,line:linearPoints.map(p=>[p.lat,p.lng]),customer:el('customerName').value,total:priceCalc().total}));
   for(const which of [0,1,0,1]){
    const original=await record();await page.locator('#commercialAreaList .surface-saved-area').nth(which).getByRole('button',{name:'REMEASURE AREA',exact:true}).tap();
    assert(await page.evaluate(()=>areaRemeasureMode&&!map.dragging.enabled()));assert.equal(await record(),original);
    await page.locator('#map').scrollIntoViewIfNeeded();const rect=await page.locator('#map').boundingBox();
    // Real trusted touch events place a self-crossing replacement. Original stays saved.
    const y=which?390:190,ring=[[70,y],[rect.width-75,y+70],[rect.width-75,y],[70,y+70]];
    for(const [x,yy]of ring)await page.touchscreen.tap(rect.x+x,rect.y+yy);
    assert(await page.locator('#areaStartBtn').isDisabled());assert((await page.evaluate(()=>replacementAreaError())).includes('crosses'));assert.equal(await record(),original);
    await page.tap('#areaCancelCorrectionBtn');assert.equal(await record(),original);assert(await page.evaluate(()=>map.dragging.enabled()));
   }
   const before=JSON.parse(await record());await page.locator('#commercialAreaList .surface-saved-area').first().getByRole('button',{name:'REMEASURE AREA',exact:true}).tap();
   await page.locator('#map').scrollIntoViewIfNeeded();const rect=await page.locator('#map').boundingBox();const corners=[[70,190],[rect.width-75,190],[rect.width-75,260],[70,260]];
   for(const [x,y]of corners)await page.touchscreen.tap(rect.x+x,rect.y+y);
   assert.equal(await page.evaluate(()=>replacementAreaError()),'');assert.equal(JSON.parse(await record()).total,before.total);
   if(industry==='snow')await page.screenshot({path:output+'/remeasure-'+width+'.jpg',fullPage:false});
   await page.tap('#areaStartBtn');const after=JSON.parse(await record());assert.notDeepEqual(after.areas[0].points,before.areas[0].points);assert.deepEqual(after.areas[1],before.areas[1]);assert.deepEqual(after.line,before.line);assert.equal(after.customer,before.customer);assert.equal(after.areas[0].rate,before.areas[0].rate);assert.notEqual(after.total,before.total);
   const flags=await page.evaluate(()=>({mode:areaRemeasureMode,dragging:map.dragging.enabled(),events:touchQaEvents}));assert(!flags.mode&&flags.dragging&&flags.events.touch>0&&flags.events.pointer>0);
   // Secondary corner editing and repeated Linear editing retain prior locks and Cancel.
   await page.locator('#commercialAreaList .surface-saved-area').first().getByRole('button',{name:'EDIT OUTLINE',exact:true}).tap();const saved=await record();await page.tap('#areaCancelCorrectionBtn');assert.equal(await record(),saved);
   for(let repeat=0;repeat<2;repeat++){await page.tap('#linearEditBtn');assert(await page.evaluate(()=>!map.dragging.enabled()));const start=await marker('.linear-point');const original=await page.evaluate(()=>linearPoints.map(p=>[p.lat,p.lng]));const center=(await state()).center;await drag(start,{x:start.x+8,y:start.y+12});assert.deepEqual((await state()).center,center);await page.tap('#linearCancelEditBtn');assert.deepEqual(await page.evaluate(()=>linearPoints.map(p=>[p.lat,p.lng])),original);assert(await page.evaluate(()=>map.dragging.enabled()));}
   const expectedSaved=await page.evaluate(()=>({areas:JSON.parse(JSON.stringify(commercialAreas)),line:linearPoints.map(p=>[p.lat,p.lng]),total:priceCalc().total}));
   await page.selectOption('#streetViewChoice','none');
   const responsePromise=page.waitForResponse(r=>r.url().endsWith('/api/estimates')&&r.request().method()==='POST');await page.tap('#createEstimateBtn');const savedResponse=await responsePromise;assert.equal(savedResponse.status(),200,await savedResponse.text());const savedId=(await savedResponse.json()).id;
   const savedPayload=await page.evaluate(async id=>(await (await fetch('/api/estimates/'+id)).json()).payload,savedId);assert.deepEqual(savedPayload.quote.commercialAreas,expectedSaved.areas);assert.deepEqual(savedPayload.quote.linearPoints,expectedSaved.line);assert.equal(savedPayload.pricing.total,expectedSaved.total);
   await page.evaluate(async id=>{resetReportForNewProperty();await openHistoricalEstimate(id,-1)},savedId);assert.deepEqual(await page.evaluate(()=>quoteSnapshot.commercialAreas),expectedSaved.areas);assert.equal(await page.evaluate(()=>quoteSnapshot.savedPricing.total),expectedSaved.total);await page.evaluate(()=>resetReportForNewProperty());
   assert.deepEqual(errors,[]);results.push({width,industry,repeatedCancel:true,invalidBlocked:true,explicitSave:true,otherAreaAndLinePreserved:true,trustedTouch:true});console.log('PASS remeasure touch',width,industry);
  }
  await context.close();
 }
 fs.writeFileSync(output+'/remeasure-results.json',JSON.stringify(results,null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
`;
new Function('require',script)(require);
