// Actual Chromium; disposable loopback fixture only, with controlled failed requests.
const fs=require('fs'),assert=require('assert/strict');
process.env.QA_BROWSER_WIDTHS='1440,390';process.env.QA_BROWSER_INDUSTRIES='snow';process.env.QA_BROWSER_IMAGES='hide';
let script=fs.readFileSync('scripts/test_prelaunch_browser.cjs','utf8');
const anchor=' const before=await page.evaluate(';assert(script.includes(anchor));
script=script.replace(anchor,`
 const oldDraft=await page.evaluate(()=>JSON.stringify(captureQuoteSnapshot()));
 const oldCustomer=await page.locator('#customerName').inputValue(),oldUsage=await page.evaluate(()=>usage.property);
 const unchanged=async()=>{assert.equal(await page.evaluate(()=>JSON.stringify(captureQuoteSnapshot())),oldDraft);assert.equal(await page.locator('#customerName').inputValue(),oldCustomer);assert.equal(await page.evaluate(()=>usage.property),oldUsage);assert(/retry|try again/i.test(await page.locator('#status').innerText()));};
 await page.route('**/property',r=>r.fulfill({status:503,json:{error:'Property provider temporarily unavailable. Please try again.'}}));
 await page.click('#propertyActionBtn');await page.waitForFunction(()=>!loadProperty.inFlight);await unchanged();await page.unroute('**/property');
 const imagePattern=/\\/(wide-aerial|fallback-map|exact-pin-map)\\//;
 await page.route(imagePattern,r=>r.abort());await page.click('#propertyActionBtn');await page.waitForFunction(()=>!loadProperty.inFlight);await unchanged();await page.unroute(imagePattern);
 await page.route('**/property/accept',r=>r.fulfill({status:401,json:{error:'Dealer login required'}}));
 await page.click('#propertyActionBtn');await page.waitForFunction(()=>!loadProperty.inFlight);await unchanged();await page.unroute('**/property/accept');
 console.log('PASS property API503, image decode/network failure and acceptance401 preserve old geometry/customer/usage and show retry; original quote remains usable');
`+anchor);
new Function('require',script)(require);
