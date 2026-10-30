// Isolated loopback QA only: saved-image interruption and export retry.
const fs=require('fs'),assert=require('assert/strict');
process.env.QA_BROWSER_WIDTHS='390';process.env.QA_BROWSER_INDUSTRIES='snow';process.env.QA_BROWSER_IMAGES='hide';process.env.QA_BROWSER_ALL_PDFS='1';
let script=fs.readFileSync('scripts/test_prelaunch_browser.cjs','utf8');
const anchor="await page.evaluate(id=>openHistoricalEstimate(id,-1),saved.id);await page.waitForFunction(()=>document.body.classList.contains('report-open'));";
assert(script.includes(anchor));script=script.replace(anchor,`
 await page.route('**/saved-estimate-report-map',r=>r.fulfill({status:503,body:'FICTIONAL QA imagery failure'}));
 ${anchor}
 await page.waitForFunction(()=>!estimateOpenInProgress);const frozen=await page.evaluate(()=>JSON.stringify(quoteSnapshot));
 await page.evaluate(()=>downloadEstimatePDF());assert.equal(await page.evaluate(()=>pdfInProgress),false);assert((await page.locator('#status').textContent()).includes('could not be created'));assert.equal(await page.evaluate(()=>JSON.stringify(quoteSnapshot)),frozen);
 await page.unroute('**/saved-estimate-report-map');const retry=page.waitForEvent('download');await page.click('#downloadPdfBtn');await (await retry).saveAs(output+'/recovered-image.pdf');await page.waitForFunction(()=>!pdfInProgress);
 assert(await page.locator('#customerMapPlaceholder').isHidden(),'Successful aerial retry must remove stale image-error placeholder');
 assert.equal(await page.evaluate(()=>JSON.stringify(quoteSnapshot)),frozen);
 await page.evaluate(async()=>{const capture=html2canvas;try{window.html2canvas=async()=>{throw Error('FICTIONAL QA renderer interruption')};await downloadEstimatePDF()}finally{window.html2canvas=capture}});
 assert.equal(await page.evaluate(()=>pdfInProgress),false);assert(!await page.locator('#downloadPdfBtn').isDisabled());assert.equal(await page.evaluate(()=>JSON.stringify(quoteSnapshot)),frozen);
 await page.evaluate(async()=>{const length=quoteSnapshot.linearFeet;try{quoteSnapshot.linearFeet=0;await downloadEstimatePDF()}finally{quoteSnapshot.linearFeet=length}});assert((await page.locator('#status').textContent()).includes('quantity does not match'));assert.equal(await page.evaluate(()=>JSON.stringify(quoteSnapshot)),frozen);
 let repeated=0;const count=()=>repeated++;page.on('download',count);await page.evaluate(()=>Promise.all([downloadEstimatePDF(),downloadEstimatePDF()]));await page.waitForTimeout(200);assert.equal(repeated,1,'Rapid duplicate download calls produce one PDF');page.off('download',count);
 console.log('PASS saved-image failure, stale placeholder cleanup, interrupted capture, duplicate download single-flight and safe retry');
`);
new Function('require',script)(require);
