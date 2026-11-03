// Focused regression: real keyboard/blur events, actual save/reopen and both PDF exporters.
// Uses the existing loopback-only fictional provider/account fixture. No live credentials.
const fs=require('fs'),assert=require('assert/strict');
process.env.QA_BROWSER_WIDTHS='1440';process.env.QA_BROWSER_INDUSTRIES='snow';process.env.QA_BROWSER_IMAGES='hide';
let script=fs.readFileSync('scripts/test_prelaunch_browser.cjs','utf8');
const anchor=" console.log('drawn',";assert(script.includes(anchor));
script=script.replace(anchor,()=>String.raw`
 const rateEvidence=[];const posted=[];
 page.on('request',r=>{if(new URL(r.url()).pathname==='/api/estimates'&&r.method()==='POST')posted.push(r.postDataJSON())});
 await page.evaluate(()=>{window.qaRateEvents=[];for(const t of ['input','change','blur'])document.addEventListener(t,e=>{if(e.target.matches('[aria-label="Rate per square foot"]'))qaRateEvents.push({type:t,value:e.target.value,trusted:e.isTrusted})},true)});
 const rates=page.getByLabel('Rate per square foot',{exact:true});
 const checkRate=async(index,value,commit,mode)=>{
  const field=rates.nth(index);await field.click();await field.press('ControlOrMeta+A');await field.pressSequentially(value);
  if(commit==='tab')await field.press('Tab');else await page.locator('#customerName').click();
  const state=await page.evaluate(i=>({display:document.querySelectorAll('[aria-label="Rate per square foot"]')[i].value,rate:commercialAreas[i].rate,mode:measurementViewMode,jobPrice:el('jobPrice').value,price:priceCalc(),snapshot:captureQuoteSnapshot(),preview:el('summary').innerText}),index);
  assert.equal(state.mode,mode);assert.equal(Number(state.display),Number(value));assert.equal(state.rate,Number(value));assert.equal(state.snapshot.commercialAreas[index].rate,Number(value));
  assert(state.preview.includes('$'+Number(value).toFixed(2)+'/ft²'));
  rateEvidence.push({index,value,commit,...state});
 };
 // Base fixture has two saved areas plus a line, with Linear active.
 await checkRate(0,'0.27','tab','linear');await checkRate(0,'0.10','tab','linear');await checkRate(1,'0.12','click','linear');
 await page.locator('#jobPrice').click();await page.locator('#jobPrice').press('ControlOrMeta+A');await page.locator('#jobPrice').pressSequentially('0.25');await page.locator('#jobPrice').press('Tab');
 // Select an existing area through its real Edit/Cancel controls, preserving its geometry.
 await page.getByRole('button',{name:'EDIT OUTLINE',exact:true}).first().click();await page.getByRole('button',{name:'CANCEL',exact:true}).click();
 await checkRate(0,'0.14','click','area');await checkRate(0,'0.10','tab','area');
 // Playwright fill is separately distinguished from ordinary key events.
 await rates.nth(1).fill('0.13');await rates.nth(1).press('Tab');
 assert.equal(await page.evaluate(()=>commercialAreas[1].rate),.13);await checkRate(1,'0.12','click','area');
 const geometry=await page.evaluate(()=>JSON.stringify(commercialAreas.map(a=>({points:a.points,sqft:a.sqft}))));
 for(const invalid of ['', '-0.01']){
  await rates.first().click();await rates.first().press('ControlOrMeta+A');await rates.first().press('Backspace');
  if(invalid)await rates.first().pressSequentially(invalid);await rates.first().press('Tab');
  assert.equal(await page.locator('#createEstimateBtn').isDisabled(),true,'Invalid/blank rate must block creation');
  assert.equal(posted.length,0,'Invalid pricing must not submit an estimate');
  assert.equal(await page.evaluate(()=>JSON.stringify(commercialAreas.map(a=>({points:a.points,sqft:a.sqft})))),geometry);
 }
 await checkRate(0,'0.00','tab','area');assert.equal(await page.locator('#createEstimateBtn').isDisabled(),false,'Explicit zero remains valid');
 await checkRate(0,'0.10','click','area');
 fs.writeFileSync(output+'/rate-events.json',JSON.stringify(await page.evaluate(()=>qaRateEvents),null,2));
 fs.writeFileSync(output+'/rate-evidence.json',JSON.stringify(rateEvidence,null,2));
 await page.screenshot({path:output+'/snow-rate-workspace.png',fullPage:true});
`+anchor);
const savedAnchor=" assert.equal(payload.total_price,before.pricing.total);";assert(script.includes(savedAnchor));
script=script.replace(savedAnchor,()=>String.raw`
 assert(posted.length>=1);for(const p of posted){assert.deepEqual(p.quote.commercialAreas.map(a=>a.rate),[.1,.12]);assert.equal(p.total_price,before.pricing.total)}
 assert.deepEqual(payload.quote.commercialAreas.map(a=>a.rate),[.1,.12]);
 fs.writeFileSync(output+'/save-requests.json',JSON.stringify(posted,null,2));
`+savedAnchor);
const reopenAnchor=" assert.equal(await page.evaluate(()=>quoteSnapshot.savedPricing.total),before.pricing.total);";assert(script.includes(reopenAnchor));
script=script.replace(reopenAnchor,reopenAnchor+"\n assert.deepEqual(await page.evaluate(()=>quoteSnapshot.commercialAreas.map(a=>a.rate)),[.1,.12]);");
new Function('require',script)(require);
