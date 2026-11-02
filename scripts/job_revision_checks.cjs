// Audit helpers deliberately use actual controls, native pointer drawing, real
// handlers and authenticated fixture APIs. No quote validation is stubbed.
const assert=require('assert/strict'),fs=require('fs');
module.exports=async function({page,context,industry,saved,payload,draw,pts,output,before,errors,seen}){
 const get=async path=>{const r=await context.request.get('http://127.0.0.1:8765'+path);assert.equal(r.status(),200);return r.json()};
 const versions=()=>get('/api/estimates/'+saved.id+'/versions'),state=()=>get('/__qa_fresh/state');
 const baseline=await versions();let paidStart=await state();
 const mapRequests=[];const onMapRequest=r=>{if(new URL(r.url()).pathname==='/saved-estimate-report-map')mapRequests.push(r.postDataJSON())};page.on('request',onMapRequest);assert.equal(paidStart.plan.plan_code,'basic');assert.equal(paidStart.complimentary,false);
 assert.equal(paidStart.paid.lookups,seen.length+1);assert.equal(paidStart.paid.estimates,seen.length+1);
 const edit=async()=>{await page.evaluate(id=>openHistoricalEstimate(id,-1),saved.id);await page.getByRole('button',{name:'EDIT MEASUREMENTS / PRICE',exact:true}).click();await page.waitForFunction(()=>sessionToken&&!savedEstimateEditContext&&!document.body.classList.contains('report-open'));await page.evaluate(()=>map.setView([52,-106],19,{animate:false}));};
 await edit();assert.deepEqual((await versions()).current.payload,payload);assert.equal((await state()).paid.lookups,paidStart.paid.lookups,'Saved edit imagery rehydration must not debit');
 const geometry=()=>page.evaluate(()=>stableWorkspaceJSON({areas:commercialAreas,line:linearPoints,planes:manualPlanes}));
 const frozen=await geometry();
 // A new failure context: loading replacement imagery during a saved-job edit.
 const imagePattern=/\/(wide-aerial|fallback-map|exact-pin-map)\//;
 await page.route(imagePattern,r=>r.abort());await page.click('#propertyActionBtn');await page.waitForFunction(()=>!loadProperty.inFlight);await page.unroute(imagePattern);
 assert.equal(await geometry(),frozen);assert.equal((await state()).paid.lookups,paidStart.paid.lookups);assert(/retry|again/i.test(await page.locator('#status').textContent()));
 if(industry==='roofing'){
  for(let n=paidStart.paid.lookups;n<25;n++){const operation='audit-exhaust-'+n;const prepared=await context.request.post('http://127.0.0.1:8765/property',{headers:{'Idempotency-Key':operation},data:{key:'qa-placeholder',address:'1 Fictional QA Street',business_type:'roofing',prepare_only:true}});assert.equal(prepared.status(),200);const accepted=await context.request.post('http://127.0.0.1:8765/property/accept',{data:{operation_id:operation,token:(await prepared.json()).token}});assert.equal(accepted.status(),200)}
  await page.click('#propertyActionBtn');await page.waitForFunction(()=>!loadProperty.inFlight);assert(/limit|allowance/i.test(await page.locator('#status').textContent()));assert.equal(await geometry(),frozen);paidStart=await state();assert.equal(paidStart.paid.lookups,25);
 }
 if(industry!=='roofing'){
  const second=page.locator('.surface-saved-area').nth(1);await second.getByRole('button',{name:'REMEASURE AREA',exact:true}).click();
  await draw(pts.slice(0,2).map(([a,b])=>[a+.0002,b+.00004]));assert(await page.locator('#createEstimateBtn').isDisabled());await page.click('#areaCancelCorrectionBtn');assert.equal(await geometry(),frozen,'Incomplete replacement Cancel must preserve saved areas and line');
  await page.locator('.surface-saved-area').nth(1).getByRole('button',{name:'REMEASURE AREA',exact:true}).click();await draw(pts.map(([a,b])=>[a+.0002,b+.00004]));await page.click('#areaStartBtn');
  await page.locator('.surface-saved-area').nth(0).getByRole('button',{name:'REMOVE AREA',exact:true}).click();
  await page.click('#toolAreaBtn');await draw(pts.map(([a,b])=>[a-.0002,b]));await page.click('#areaStartBtn');assert.equal(await page.locator('.surface-saved-area').count(),2);
  const lineBefore=await page.evaluate(()=>JSON.stringify(linearPoints));
  const dragEnd=async offset=>{const xy=await page.evaluate(off=>{const p=linearPoints.at(-1),a=map.latLngToContainerPoint(p),b=map.latLngToContainerPoint([p.lat+off,p.lng]),r=el('map').getBoundingClientRect();return [a.x+r.left,a.y+r.top,b.x+r.left,b.y+r.top]},offset);await page.mouse.move(xy[0],xy[1]);await page.mouse.down();await page.mouse.move(xy[2],xy[3],{steps:8});await page.mouse.up();};
  await page.click('#linearEditBtn');await page.locator('#map').scrollIntoViewIfNeeded();await dragEnd(.00004);await page.click('#linearCancelEditBtn');assert.equal(await page.evaluate(()=>JSON.stringify(linearPoints)),lineBefore);
  await page.click('#linearEditBtn');await page.locator('#map').scrollIntoViewIfNeeded();await dragEnd(.00006);await page.click('#linearSaveEditBtn');assert.notEqual(await page.evaluate(()=>JSON.stringify(linearPoints)),lineBefore,'Native endpoint drag must actually change the saved line');
  const changedLine=await page.evaluate(()=>JSON.stringify(linearPoints));await page.locator('#surfaceLineMore > summary').click();await page.click('#linearClearBtn');assert.equal(await page.evaluate(()=>linearMeasurementSaved),false);
  await page.click('#toolLinearBtn');await draw([[51.99995,-105.99985],[52.00014,-105.99985],[52.00014,-105.99981]]);await page.click('#linearStartBtn');assert.notEqual(await page.evaluate(()=>JSON.stringify(linearPoints)),changedLine);
  for(let i=0;i<2;i++){const rate=page.getByRole('spinbutton',{name:'Rate per square foot'}).nth(i);await rate.fill(i===0?'.17':'.29');await rate.blur();}
  if(industry==='commercial'){await page.fill('#commercialLinearRate','.31')}else await page.fill('#jobPrice','.31');
 }else{
  await page.locator('#manualRoofSections .structure').nth(0).getByRole('button',{name:'EDIT',exact:true}).click();await page.selectOption('#pitchSel','36.87');await page.click('#traceBtn');assert.equal(await geometry(),frozen,'Cancel roof pitch edit preserves every section');
  await page.locator('#manualRoofSections .structure').nth(0).getByRole('button',{name:'EDIT',exact:true}).click();await page.selectOption('#pitchSel','36.87');await page.click('#finishTrace');
  await page.locator('#manualRoofSections .structure').nth(1).getByRole('button',{name:'DELETE',exact:true}).click();assert(await page.locator('#createEstimateBtn').isDisabled(),'Deleting roof scope must require reconfirmation');
  await page.click('#traceBtn');await draw(pts.map(([a,b])=>[a-.00023,b]));assert(await page.locator('#createEstimateBtn').isDisabled());await page.selectOption('#pitchSel','26.57');await page.click('#finishTrace');await page.click('#manualRoofScopeConfirmed');await page.fill('#jobPrice','.43');
  assert.deepEqual(await page.evaluate(()=>manualPlanes.map(p=>p.pitch_degrees)),[36.87,45,26.57]);
 }
 await page.fill('#extraServiceDescription','FICTIONAL revised service '+industry);await page.fill('#extraServiceAmount','19.95');
 await page.locator('details.dealer-settings > summary').click();await page.fill('#gst','7.25');await page.fill('#pst','2.5');await page.locator('details.dealer-settings > summary').click();
 for(const [id,value] of [['customerName','FICTIONAL REVISED '+industry],['customerPhone','555-0199'],['customerEmail','revised-'+industry+'@example.invalid'],['customerNotes','FICTIONAL RESTORED EDIT '+industry]]){await page.click('#'+id);await page.fill('#'+id,value)}
 const invalidBefore=await geometry();await page.fill('#extraServiceAmount','-1');assert(await page.locator('#createEstimateBtn').isDisabled());assert(/amount|0 or more/.test(await page.locator('#quotePricingError').textContent()));assert.equal(await geometry(),invalidBefore);await page.fill('#extraServiceAmount','19.95');
 // Restore an edited existing job, retaining the original save version/identity.
 assert.equal(await page.evaluate(()=>aqRecovery.flush()),true);const edited=await page.evaluate(()=>({q:captureQuoteSnapshot(),p:priceCalc(),customer:el('customerName').value,notes:el('customerNotes').value}));
 await page.reload();await page.waitForTimeout(1400);await page.getByRole('button',{name:'Restore',exact:true}).click();await page.waitForFunction(()=>sessionToken&&el('workspaceRecoveryStatus').textContent.includes('saved for 24 hours'));
 assert.deepEqual(await page.evaluate(()=>({q:captureQuoteSnapshot(),p:priceCalc(),customer:el('customerName').value,notes:el('customerNotes').value})),edited);
 assert.deepEqual((await versions()).current.payload,payload,'Restore cannot rewrite current or historical estimates');assert.equal((await state()).paid.estimates,paidStart.paid.estimates);
 // Existing-job save commits but loses its response; retry must confirm one receipt.
 let committed;await page.route('**/api/estimates',async r=>{if(r.request().method()!=='POST')return r.continue();const response=await r.fetch();assert.equal(response.status(),200);committed=await response.json();await r.abort();});
 await page.click('#createEstimateBtn');await page.waitForFunction(()=>!estimateOpenInProgress);assert(committed?.id);assert.equal(committed.id,saved.id);assert.equal(await page.evaluate(()=>document.body.classList.contains('report-open')),false);assert(await page.evaluate(()=>!!saveEstimateHistory.pending));
 const lost=await versions();assert.equal(lost.revisions.length,baseline.revisions.length+1);await page.unroute('**/api/estimates');await page.click('#createEstimateBtn');await page.waitForFunction(()=>document.body.classList.contains('report-open')&&!estimateOpenInProgress);
 const final=await versions();assert.deepEqual(final,lost);assert.deepEqual(final.revisions[0].payload,payload,'Original revision is byte-for-byte unchanged');
 const paidEnd=await state();assert.equal(paidEnd.paid.lookups,paidStart.paid.lookups);assert.equal(paidEnd.paid.estimates,paidStart.paid.estimates);assert.equal(paidEnd.counts.estimates,paidStart.counts.estimates);assert.equal(paidEnd.counts.estimate_revisions,paidStart.counts.estimate_revisions+1);assert.equal(paidEnd.counts.estimate_save_receipts,paidStart.counts.estimate_save_receipts+1);
 fs.writeFileSync(output+'/'+industry+'-updated-source.json',JSON.stringify(final.current.payload,null,2));
 // Switch by reopening other industry's current/old snapshots in reverse order.
 for(const other of seen.slice(-2).reverse())for(const version of [-1,0]){await page.evaluate(({id,version})=>openHistoricalEstimate(id,version),{id:other.id,version});assert.equal(await page.evaluate(()=>quoteSnapshot.businessType),other.industry);}
 await page.evaluate(id=>openHistoricalEstimate(id,-1),saved.id);assert.equal(await page.locator('#rCustomerName').textContent(),final.current.payload.customer_name);
 const expectedRoofs=industry==='roofing'?final.current.payload.quote.manualPlanes.map(p=>({kind:'manual',points:p.points.map(v=>({lat:v.lat??v[0],lng:v.lng??v[1]}))})):[...final.current.payload.quote.commercialAreas.map(a=>({kind:'area',points:a.points.map(v=>({lat:v[0],lng:v[1]}))})),{kind:'linear',points:final.current.payload.quote.linearPoints.map(v=>({lat:v[0],lng:v[1]}))}];assert.deepEqual(mapRequests.at(-1).roofs,expectedRoofs,'Actual report-map request includes every priced outline exactly');
 const pdfState=await page.evaluate(()=>JSON.stringify(quoteSnapshot));const projection=await page.evaluate(()=>activeSavedDiagramSnapshot(quoteSnapshot));
 if(industry==='roofing'){assert.equal(projection.manualPlanes.length,3);assert.equal(projection.commercialAreas.length,0);assert.equal(projection.linearPoints.length,0)}else{assert.equal(projection.commercialAreas.length,2);assert.equal(projection.linearPoints.length,3);assert.equal(projection.manualPlanes.length,0);assert.equal(projection.structures.length,0)}
 for(const layout of ['single','expanded']){await page.selectOption('#estimatePdfLayout',layout);const d=page.waitForEvent('download',{timeout:45000});await page.click('#downloadPdfBtn');await(await d).saveAs(output+'/'+industry+'-updated-'+layout+'.pdf');assert.equal(await page.evaluate(()=>JSON.stringify(quoteSnapshot)),pdfState)}
 await page.screenshot({path:output+'/'+industry+'-updated.png',fullPage:true});
 assert.deepEqual((await versions()).revisions[0].payload,payload);assert.deepEqual((await versions()).current.payload,final.current.payload);
 // Editing the older revision is a distinct stale case from simultaneous current tabs.
 await page.evaluate(id=>openHistoricalEstimate(id,0),saved.id);await page.getByRole('button',{name:'EDIT MEASUREMENTS / PRICE',exact:true}).click();await page.waitForFunction(()=>sessionToken&&!savedEstimateEditContext&&!document.body.classList.contains('report-open'));await page.click('#customerNotes');await page.fill('#customerNotes','FICTIONAL STALE OLDER '+industry);assert.equal(await page.evaluate(()=>aqRecovery.flush()),true);await page.click('#createEstimateBtn');await page.waitForFunction(()=>!estimateOpenInProgress);assert.equal(await page.evaluate(()=>saveEstimateHistory.lastFailureStatus),409);assert.equal(await page.locator('#customerNotes').inputValue(),'FICTIONAL STALE OLDER '+industry);assert.deepEqual(await versions(),final);assert.equal((await state()).paid.estimates,paidEnd.paid.estimates);const staleHeaders=await page.evaluate(()=>aqRecovery.headers());assert.equal((await context.request.delete('http://127.0.0.1:8765/api/workspace-drafts/'+staleHeaders['X-AeriQuote-Draft'],{headers:staleHeaders})).status(),200);page.off('request',onMapRequest);
 fs.writeFileSync(output+'/'+industry+'-edit-audit.json',JSON.stringify({industry,initial:paidStart,final:paidEnd,original:payload,updated:final.current.payload,projection,mapRequests,staleOlderBlocked:true,olderUnchanged:true,lostResponseOneRevision:true,restoreExact:true},null,2));
 seen.push({id:saved.id,industry});console.log('PASS existing-job lifecycle',industry,'Cancel/add/replace/delete/restore/lost-response/immutable older revision/normal paid allowance/both updated PDFs');
};
