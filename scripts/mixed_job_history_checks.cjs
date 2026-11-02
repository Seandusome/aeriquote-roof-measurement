// Same property, mixed geometry history, real UI industry changes at paid cap.
const assert=require('assert/strict'),fs=require('fs');
module.exports=async({page,context,saved,draw,pts,output})=>{
 const versions=async()=>await(await context.request.get('http://127.0.0.1:8765/api/estimates/'+saved.id+'/versions')).json();
 const state=async()=>await(await context.request.get('http://127.0.0.1:8765/__qa_fresh/state')).json();
 const start=await state(),history=await versions();assert.equal(start.paid.lookups,25);const initialRows=history.revisions.map(r=>r.payload),initialCurrent=history.current.payload,record=[];
 for(const [n,industry] of ['commercial','landscaping','paving','pressure','snow'].entries()){
  const previous=await versions();await page.evaluate(id=>openHistoricalEstimate(id,-1),saved.id);await page.getByRole('button',{name:'EDIT MEASUREMENTS / PRICE',exact:true}).click();await page.waitForFunction(()=>sessionToken&&!savedEstimateEditContext&&!document.body.classList.contains('report-open'));
  await page.locator('details.dealer-settings > summary').click();await page.selectOption('#businessType',industry);await page.fill('#gst','7.25');await page.fill('#pst','2.5');await page.locator('details.dealer-settings > summary').click();
  await page.evaluate(()=>map.setView([52,-106],19,{animate:false}));
  if(n===0){await page.click('#toolAreaBtn');await draw(pts.map(([a,b])=>[a-.00016,b-.0001]));await page.click('#areaStartBtn');await page.click('#toolAreaBtn');await draw(pts.map(([a,b])=>[a+.00017,b-.0001]));await page.click('#areaStartBtn');await page.click('#toolLinearBtn');await draw([[51.9999,-105.9997],[52.0001,-105.9997]]);await page.click('#linearStartBtn');}
  for(let i=0;i<2;i++){const rate=page.getByRole('spinbutton',{name:'Rate per square foot'}).nth(i);await rate.fill((.21+n*.02+i*.04).toFixed(2));await rate.blur();}
  if(industry==='commercial')await page.fill('#commercialLinearRate','.33');else{await page.click('#toolLinearBtn');await page.fill('#jobPrice','.33')}
  await page.fill('#extraServiceAmount',(7.95+n).toFixed(2));await page.click('#customerName');await page.fill('#customerName','FICTIONAL MIXED '+industry);await page.click('#customerEmail');await page.fill('#customerEmail','mixed-'+industry+'@example.invalid');
  assert.equal(await page.evaluate(()=>manualPlanes.length),3,'Switching surface industry retains dormant roof history');assert.equal(await page.evaluate(()=>quotePricingError()),'');
  await page.click('#createEstimateBtn');await page.waitForFunction(()=>document.body.classList.contains('report-open')&&!estimateOpenInProgress);
  const current=await versions();assert.equal(current.revisions.length,previous.revisions.length+1);assert.deepEqual(current.revisions.map(r=>r.payload).slice(0,-1),previous.revisions.map(r=>r.payload));assert.deepEqual(current.revisions.at(-1).payload,previous.current.payload);
  const p=current.current.payload;assert.equal(p.quote.businessType,industry);assert.equal(p.quote.manualPlanes.length,3);assert.equal(p.quote.commercialAreas.length,2);assert.equal(p.quote.linearPoints.length,2);
  const requests=[];const onRequest=r=>{if(new URL(r.url()).pathname==='/saved-estimate-report-map')requests.push(r.postDataJSON())};page.on('request',onRequest);await page.evaluate(id=>openHistoricalEstimate(id,-1),saved.id);
  const body=requests.at(-1);assert.deepEqual(body.roofs.map(r=>r.kind),['area','area','linear'],'Dormant roofs must never be sent to the actual diagram endpoint');
  assert.deepEqual(body.roofs.map(r=>r.points),[...p.quote.commercialAreas.map(a=>a.points.map(([lat,lng])=>({lat,lng}))),p.quote.linearPoints.map(([lat,lng])=>({lat,lng}))]);
  fs.writeFileSync(output+'/mixed-'+industry+'-source.json',JSON.stringify(p,null,2));
  for(const layout of ['single','expanded']){await page.selectOption('#estimatePdfLayout',layout);const d=page.waitForEvent('download',{timeout:45000});await page.click('#downloadPdfBtn');await(await d).saveAs(output+'/mixed-'+industry+'-'+layout+'.pdf')}
  assert.equal(await page.locator('#rCustomerName').textContent(),p.customer_name);assert((await page.locator('#rPricing').textContent()).includes(p.total_price.toFixed(2)));page.off('request',onRequest);record.push({industry,payload:p,request:body});
 }
 const final=await versions();assert.deepEqual(final.revisions.slice(0,initialRows.length).map(r=>r.payload),initialRows);assert.deepEqual(final.revisions[initialRows.length].payload,initialCurrent);
 for(const index of [final.revisions.length-1,0,2,-1,1,3]){
  const p=(index<0?final.current:final.revisions[index]).payload;await page.evaluate(({id,index})=>openHistoricalEstimate(id,index),{id:saved.id,index});assert.equal(await page.evaluate(()=>quoteSnapshot.businessType),p.quote.businessType);assert.equal(await page.locator('#rCustomerName').textContent(),p.customer_name);assert((await page.locator('#rPricing').textContent()).includes(p.total_price.toFixed(2)));
 }
 assert.deepEqual(await versions(),final);const end=await state();assert.equal(end.paid.lookups,25);assert.equal(end.paid.estimates,start.paid.estimates);assert.equal(end.counts.estimates,start.counts.estimates);assert.equal(end.counts.estimate_revisions,start.counts.estimate_revisions+5);assert.equal(end.counts.estimate_save_receipts,start.counts.estimate_save_receipts+5);
 fs.writeFileSync(output+'/mixed-history-audit.json',JSON.stringify({start,end,record,priorRevisionsUnchanged:true,reverseReopenOrder:[final.revisions.length-1,0,2,-1,1,3]},null,2));console.log('PASS same-property mixed Roofing→five-surface-industry revisions, inactive roofs excluded from ten actual PDFs, out-of-order history immutable, no paid debit at cap');
};
