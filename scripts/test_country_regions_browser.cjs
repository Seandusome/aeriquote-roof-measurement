// Actual isolated Chromium form controls at mobile widths; not physical hardware.
const fs=require('fs'),assert=require('assert/strict');let script=fs.readFileSync('scripts/test_linear_touch_browser.cjs','utf8');const anchor="  await page.tap('#linearEditBtn');const before=";const at=script.indexOf(anchor);assert(at>0);
script=script.slice(0,at)+String.raw`
  await page.waitForTimeout(1100);console.log('Country loaded',width,await page.evaluate(()=>({error:quotePricingError(),status:el('status').textContent,disabled:el('createEstimateBtn').disabled}))); 
  await page.selectOption('#streetViewChoice','none');await page.evaluate(()=>{el('customerName').value='FICTIONAL COUNTRY QA'});console.log('Country creating',width);
  const responsePromise=page.waitForResponse(r=>r.url().endsWith('/api/estimates')&&r.request().method()==='POST',{timeout:15000});await page.tap('#createEstimateBtn');const response=await responsePromise;assert.equal(response.status(),200,await response.text());const savedId=(await response.json()).id;
  const savedPayload=()=>page.evaluate(async id=>JSON.stringify((await (await fetch('/api/estimates/'+id)).json()).payload),savedId);const historical=await savedPayload();await page.evaluate(()=>resetReportForNewProperty());
  const beforeProperty=await page.evaluate(()=>JSON.stringify({address:el('address').value,city:el('cityTown').value,customer:el('customerName').value,areas:commercialAreas,line:linearPoints,taxes:[el('gst').value,el('pst').value],total:priceCalc().total}));
  await page.selectOption('#propertyCountry','CA');await page.selectOption('#propertyProvince','SK');
  const propertyCodes=()=>page.locator('#propertyProvince option').evaluateAll(nodes=>nodes.map(n=>n.value).filter(Boolean));assert.equal((await propertyCodes()).length,13);assert(!(await propertyCodes()).includes('TX'));
  await page.selectOption('#propertyCountry','US');assert.equal((await propertyCodes()).length,51);assert(!(await propertyCodes()).includes('SK'));assert.equal(await page.locator('#propertyProvince').inputValue(),'');await page.selectOption('#propertyProvince','DC');await page.selectOption('#propertyCountry','CA');assert.equal(await page.locator('#propertyProvince').inputValue(),'SK');
  assert.equal(await page.evaluate(()=>JSON.stringify({address:el('address').value,city:el('cityTown').value,customer:el('customerName').value,areas:commercialAreas,line:linearPoints,taxes:[el('gst').value,el('pst').value],total:priceCalc().total})),beforeProperty);assert.equal(await savedPayload(),historical);
  await page.locator('#propertyCountry').scrollIntoViewIfNeeded();await page.screenshot({path:output+'/country-property-'+width+'.png'});
  console.log('Country saved',width);await page.locator('.dealer-settings > summary').tap();
  await page.selectOption('#dealerCountry','CA');await page.selectOption('#province','SK');await page.fill('#gst','5');await page.fill('#pst','6');
  const taxes=await page.evaluate(()=>[el('gst').value,el('pst').value,priceCalc().total]);
  const codes=()=>page.locator('#province option').evaluateAll(nodes=>nodes.map(n=>n.value).filter(Boolean));assert.equal((await codes()).length,13);assert(!(await codes()).includes('TX'));
  await page.selectOption('#dealerCountry','US');assert.equal((await codes()).length,51);assert((await codes()).includes('DC'));assert(!(await codes()).includes('SK'));assert.equal(await page.locator('#province').inputValue(),'');await page.selectOption('#province','TX');await page.selectOption('#dealerCountry','CA');assert.equal(await page.locator('#province').inputValue(),'SK');
  assert.deepEqual(await page.evaluate(()=>[el('gst').value,el('pst').value,priceCalc().total]),taxes);assert.equal(await savedPayload(),historical,'Country filtering must not rewrite server-saved history');
  await page.locator('#dealerCountry').scrollIntoViewIfNeeded();await page.screenshot({path:output+'/country-profile-'+width+'.jpg'});
  for(const setup of ['roofer','snow','pressure','paving','landscaping','commercial']){await page.goto('http://127.0.0.1:8765/site/'+setup+'-setup.html');await page.waitForFunction(()=>typeof updateSetupRegions==='function');await page.waitForTimeout(200);
  await page.selectOption('#country','Canada');await page.selectOption('#region','SK');await page.selectOption('#country','United States');assert.equal(await page.locator('#region option').evaluateAll(n=>n.filter(o=>o.value).length),51);await page.selectOption('#region','DC');await page.selectOption('#country','Canada');assert.equal(await page.locator('#region').inputValue(),'SK');assert.equal(await page.locator('#region option').evaluateAll(n=>n.filter(o=>o.value).length),13);await page.selectOption('#country','United States');assert.equal(await page.locator('#region').inputValue(),'DC');
  }
  await page.goto('http://127.0.0.1:8765/site/trial-signup.html?industry=snow');assert.deepEqual(await page.locator('#trialCountry option').allTextContents(),['Canada','United States']);
  assert.deepEqual(errors,[]);results.push({width,profileCountryFirst:true,canada13:true,us51:true,regionRoundTrip:true,taxValuesUnchanged:true,savedHistoryUnchanged:true,onboarding:true,signup:true});console.log('PASS country forms',width);await context.close();
 }
 fs.writeFileSync(output+'/country-results.json',JSON.stringify(results,null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
`;
new Function('require',script)(require);
