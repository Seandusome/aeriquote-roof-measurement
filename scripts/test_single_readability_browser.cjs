// Real saved multi-area jobs, ordinary/dense, desktop/phone; no PDF/data mocks.
const fs=require('fs'),assert=require('assert/strict');
const scenario=process.env.QA_DENSITY_CASE||'ordinary';assert(['ordinary','dense'].includes(scenario));
process.env.QA_BROWSER_WIDTHS='1440,390';process.env.QA_BROWSER_INDUSTRIES='landscaping';process.env.QA_BROWSER_IMAGES='hide';process.env.QA_BROWSER_ALL_PDFS='1';
let script=fs.readFileSync('scripts/test_prelaunch_browser.cjs','utf8');
script=script.replaceAll('FICTIONAL QA ${industry} ${width}','FICTIONAL '+scenario+' ${industry} ${width}');
const before=' const before=await page.evaluate(()=>({snapshot:captureQuoteSnapshot(),pricing:priceCalc(),overflow:document.documentElement.scrollWidth>innerWidth}));';assert(script.includes(before));
script=script.replace(before,()=>String.raw`
 if(denseCase){for(let n=2;n<8;n++){const shifted=pts.map(([lat,lng])=>[lat+n*.00014,lng]);await page.evaluate(points=>map.setView([points.reduce((a,p)=>a+p[0],0)/points.length,points.reduce((a,p)=>a+p[1],0)/points.length],19,{animate:false}),shifted);await page.click('#toolAreaBtn');await draw(shifted);await page.click('#areaStartBtn');}}
 await page.evaluate(dense=>{if(dense)commercialAreas.forEach((a,i)=>a.name='FICTIONAL AREA '+(i+1)+' - complete mowing, edging and planting requirements preserved for this measured service area');el('extraServiceDescription').value=dense?'FICTIONAL ADDITIONAL SERVICE - '+('Complete customer instructions for cleanup, planting, edging and careful removal of debris. '.repeat(6)):'FICTIONAL ordinary cleanup';el('extraServiceAmount').value='12.95';renderSummary()},denseCase);
`+before);
const capture=' const captureChecks=[];';assert(script.includes(capture));script=script.replace(capture,()=>String.raw`
 const frozen={snapshot:await page.evaluate(()=>JSON.stringify(quoteSnapshot)),payload:JSON.stringify(payload)};
 await page.evaluate(()=>{window.qaSingleFits=[];window.qaOriginalSingleGuard=assertSinglePageLegible;window.assertSinglePageLegible=report=>{qaSingleFits.push(singlePageReadability(report));if(!window.qaReproduceOldShrink)qaOriginalSingleGuard(report)}});
 if(denseCase){
  // Red control: disable only the new readability check in this disposable browser,
  // leaving the old real one-page exporter unchanged to reproduce its tiny text.
  await page.evaluate(()=>window.qaReproduceOldShrink=true);await page.selectOption('#estimatePdfLayout','single');const oldDownload=page.waitForEvent('download',{timeout:45000});await page.click('#downloadPdfBtn');await(await oldDownload).saveAs(output+'/'+width+'-dense-before-single.pdf');await page.evaluate(()=>window.qaReproduceOldShrink=false);
  const oldFit=await page.evaluate(()=>qaSingleFits.at(-1));assert(oldFit.measured&&oldFit.points<7,'Reproduced unreadable Single print size');
 }
`+capture);
const loop="for(const layout of ['single','expanded']){await page.selectOption('#estimatePdfLayout',layout);";assert(script.includes(loop));script=script.replace(loop,()=>String.raw`for(const layout of ['single','expanded']){if(denseCase&&layout==='single'){
 let downloads=0;const count=()=>downloads++;page.on('download',count);const first=await page.evaluate(()=>document.querySelector('#customerMap').innerHTML);await page.selectOption('#estimatePdfLayout','single');await page.evaluate(()=>downloadEstimatePDF());page.off('download',count);
 assert.equal(downloads,0);assert.equal(await page.locator('#estimatePdfLayout').inputValue(),'expanded');assert(await page.locator('#pdfLayoutHelp').isVisible());assert((await page.locator('#pdfLayoutHelp').textContent()).includes('Your saved estimate is unchanged'));assert.equal(await page.evaluate(()=>pdfInProgress),false);assert.equal(await page.locator('#downloadPdfBtn').isDisabled(),false);assert.equal(await page.evaluate(()=>JSON.stringify(quoteSnapshot)),frozen.snapshot);assert.equal(await page.evaluate(()=>document.querySelector('#customerMap').innerHTML),first,'Block restores exact saved imagery/labels/overlays');await page.locator('#reportOverlay').screenshot({path:output+'/'+width+'-dense-guidance.png'});continue;
 }await page.selectOption('#estimatePdfLayout',layout);`);
const expandedCapture="  const image=node.querySelector?.('[data-expanded-aerial]');";assert(script.includes(expandedCapture));script=script.replace(expandedCapture,()=>`  if(node.classList.contains('aq-expanded-page'))for(const head of node.querySelectorAll('.structure-head')){const amount=head.lastElementChild;if(!amount)continue;const range=document.createRange();range.selectNodeContents(amount);const lines=new Set([...range.getClientRects()].filter(r=>r.width&&r.height).map(r=>Math.round(r.top)));if(lines.size>1)throw Error('Expanded measurement quantity wrapped: '+amount.textContent);if(head.firstElementChild.getBoundingClientRect().right>amount.getBoundingClientRect().left+1)throw Error('Expanded measurement description overlaps quantity');}
`+expandedCapture);
const end=' await page.screenshot({path:';assert(script.includes(end));script=script.replace(end,()=>String.raw`
 const fits=await page.evaluate(()=>qaSingleFits);assert(fits.length);if(!denseCase)assert(fits.every(f=>f.measured&&f.points>=7),'Ordinary Single stays readable');
 const stored=(await(await context.request.get('http://127.0.0.1:8765/api/estimates/'+saved.id)).json()).payload;assert.equal(JSON.stringify(stored),frozen.payload,'Readability check/export must never rewrite saved text, geometry, pricing or totals');
 fs.writeFileSync(output+'/'+width+'-readability.json',JSON.stringify({scenario:denseCase?'dense':'ordinary',fits,payload:stored},null,2));console.log('PASS READABILITY',JSON.stringify({width,dense:denseCase,fits}));
`+end);
script='const denseCase='+JSON.stringify(scenario==='dense')+';\n'+script;
new Function('require',script)(require);
