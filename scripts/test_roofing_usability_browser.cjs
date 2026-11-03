// Roofing next-action UX with the real browser/save/PDF entry points, disposable QA only.
const fs=require('fs'),assert=require('assert/strict');
process.env.QA_BROWSER_WIDTHS=process.env.QA_ROOF_UX_WIDTHS||'1440';process.env.QA_BROWSER_INDUSTRIES='roofing';process.env.QA_BROWSER_IMAGES='hide';
const expectGuidance=process.env.QA_ROOF_UX_EXPECT!=='before';
let script=fs.readFileSync('scripts/test_prelaunch_browser.cjs','utf8');
script=script.replace(" await page.click('#propertyActionBtn');",()=>String.raw`
 const stages=[],saveRequests=[];
 page.on('request',r=>{if(new URL(r.url()).pathname==='/api/estimates'&&r.method()==='POST'){saveRequests.push(r.postDataJSON());fs.writeFileSync(output+'/'+width+'-save-requests.json',JSON.stringify(saveRequests,null,2));}});
 const stage=async name=>{
  if(await page.locator('#manualRoofDetails').isVisible())await page.locator('#manualRoofDetails').scrollIntoViewIfNeeded();else await page.locator('#propertyActionBtn').scrollIntoViewIfNeeded();
  const state=await page.evaluate(()=>({title:el('roofNextTitle')?.textContent,explanation:el('roofNextExplanation')?.textContent,confirmed:!!el('manualRoofScopeConfirmed')?.checked,trace:traceMode,pitch:el('pitchSel').value,planes:manualPlanes.map(p=>({area:p.surface_sqft,pitch:p.pitch_degrees})),confirmationVisible:!!el('confirmRoofPitches')&&!!el('confirmRoofPitches').getClientRects().length}));
  stages.push({name,...state});await page.screenshot({path:output+'/'+width+'-'+name+'.png'});
  fs.writeFileSync(output+'/'+width+'-stages.json',JSON.stringify(stages,null,2));return state;
 };
 const initial=await stage('01-before-property');if(expectGuidance){assert.equal(initial.confirmationVisible,false);assert.equal(initial.title,'Load the property to start');}
`+" await page.click('#propertyActionBtn');");
const drawing="  if(!await page.evaluate(()=>traceMode))await page.click('#toolAreaBtn');";assert(script.includes(drawing));
script=script.replace(drawing,()=>String.raw`
 await stage('02-drawing');if(expectGuidance){assert.equal(await page.locator('#confirmRoofPitches').isVisible(),false);assert.equal(await page.locator('#pitchSel').inputValue(),'');}
`+drawing);
const confirm="  await page.click('#confirmRoofPitches');";assert(script.includes(confirm));
script=script.replace(confirm,()=>String.raw`
 const roofDraw=async points=>{await page.evaluate(center=>map.setView(center,19,{animate:false}),[points.reduce((n,p)=>n+p[0],0)/points.length,points.reduce((n,p)=>n+p[1],0)/points.length]);await draw(points)};
 await page.locator('#jobPrice').fill('');await page.locator('#jobPrice').press('Tab');
 let s=await stage('03-saved-unconfirmed');
 if(expectGuidance){assert.equal(s.title,'Roof confirmation required');assert(s.confirmationVisible);assert.equal(await page.locator('#createEstimateBtn').isDisabled(),true);}
 await page.click('#confirmRoofPitches');s=await stage('04-price-next');
 if(expectGuidance){assert.equal(s.title,'Enter this job’s price');assert.equal(s.confirmationVisible,false);}
 await page.locator('#jobPrice').click();await page.locator('#jobPrice').pressSequentially('0.27');await page.locator('#jobPrice').press('Tab');s=await stage('05-customer-next');
 if(expectGuidance)assert.equal(s.title,'Add customer details');
 const savedRoof=await page.evaluate(()=>JSON.stringify(manualPlanes));
 await page.locator('#manualRoofSections .structure').first().getByRole('button',{name:'EDIT',exact:true}).click();
 s=await stage('06-editing');if(expectGuidance){assert(!s.confirmationVisible);assert(!s.confirmed);}
 await page.selectOption('#pitchSel','36.87');await page.click('#traceBtn');
 assert.equal(await page.evaluate(()=>JSON.stringify(manualPlanes)),savedRoof,'Cancel preserves exact saved geometry and pitch');
 assert.equal(await page.locator('#manualRoofSections .structure').first().getByRole('button',{name:'EDIT',exact:true}).isDisabled(),false);
 await stage('07-cancelled');
 // Save an edited pitch, then restore the original via the same actual Edit/Save controls.
 await page.locator('#manualRoofSections .structure').first().getByRole('button',{name:'EDIT',exact:true}).click();
 await page.selectOption('#pitchSel','36.87');await page.click('#finishTrace');assert.equal(await page.evaluate(()=>manualPlanes[0].pitch_degrees),36.87);
 await page.locator('#manualRoofSections .structure').first().getByRole('button',{name:'EDIT',exact:true}).click();await page.selectOption('#pitchSel','22.62');await page.click('#finishTrace');
 await page.click('#traceBtn');await roofDraw(pts.map(([lat,lng])=>[lat+.0003,lng]));
 assert.equal(await page.locator('#pitchSel').inputValue(),'','No default pitch silently verified');
 await page.click('#finishTrace');assert.equal(await page.evaluate(()=>manualPlanes.length),1,'Blank pitch cannot save');
 await page.selectOption('#pitchSel','0');await page.click('#finishTrace');
 await stage('08-two-sections');assert.deepEqual(await page.evaluate(()=>manualPlanes.map(p=>p.pitch_degrees)),[22.62,0]);
 await page.click('#confirmRoofPitches');await page.click('#traceBtn');await roofDraw(pts.map(([lat,lng])=>[lat+.0006,lng]));await page.selectOption('#pitchSel','45');await page.click('#finishTrace');
 await page.locator('#manualRoofSections .structure').last().getByRole('button',{name:'DELETE',exact:true}).click();
 assert.equal(await page.evaluate(()=>manualPlanes.length),2);assert.equal(await page.locator('#manualRoofScopeConfirmed').isChecked(),false);await page.click('#confirmRoofPitches');
`);
const before=" const before=await page.evaluate";assert(script.includes(before));script=script.replace(before,()=>String.raw`
 const ready=await stage('09-create-next');if(expectGuidance)assert.equal(ready.title,'Create the customer estimate');
`+before);
const reopen=" assert.equal(await page.evaluate(()=>quoteSnapshot.savedPricing.total),before.pricing.total);";assert(script.includes(reopen));
script=script.replace(reopen,()=>reopen+String.raw`
 const frozenReopen=await page.evaluate(()=>JSON.stringify(quoteSnapshot));
 await page.click('#backToDealerBtn');await page.waitForFunction(()=>!document.body.classList.contains('report-open'));
 await stage('10-reopened');assert.equal(await page.evaluate(()=>manualPlanes.length),2);assert.equal(await page.locator('#manualRoofScopeConfirmed').isChecked(),false);assert.equal(await page.locator('#createEstimateBtn').isDisabled(),true);await page.click('#confirmRoofPitches');
 await page.evaluate(id=>openHistoricalEstimate(id,-1),saved.id);await page.waitForFunction(()=>document.body.classList.contains('report-open'));
 assert.equal(await page.evaluate(()=>JSON.stringify(quoteSnapshot)),frozenReopen,'Workspace review must not mutate the stored estimate');
`);
script=script.replaceAll("await page.waitForFunction(()=>document.body.classList.contains('report-open'));","await page.waitForFunction(()=>document.body.classList.contains('report-open'));await page.waitForFunction(()=>!estimateOpenInProgress);");
// Pass only the mode flag to this generated browser program.
script='const expectGuidance='+JSON.stringify(expectGuidance)+';\n'+script;
new Function('require',script)(require);
