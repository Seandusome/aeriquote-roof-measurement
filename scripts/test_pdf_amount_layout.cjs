// Real exporters on disposable loopback QA; currency stays whole while descriptions wrap.
const fs=require('fs'),assert=require('assert/strict');
process.env.QA_BROWSER_WIDTHS=process.env.QA_AMOUNT_WIDTHS||'1440';process.env.QA_BROWSER_INDUSTRIES='roofing';process.env.QA_BROWSER_IMAGES='hide';process.env.QA_BROWSER_ALL_PDFS='1';
let script=fs.readFileSync('scripts/test_prelaunch_browser.cjs','utf8');
const scenario=process.env.QA_AMOUNT_SCENARIO||'original';assert(['original','large','pages'].includes(scenario));
script=script.replaceAll('FICTIONAL QA ${industry} ${width}','FICTIONAL QA ${industry} ${width} '+scenario);
const anchor=' const before=await page.evaluate(()=>({snapshot:captureQuoteSnapshot(),pricing:priceCalc(),overflow:document.documentElement.scrollWidth>innerWidth}));';assert(script.includes(anchor));
script=script.replace(anchor,` await page.evaluate(s=>{el('extraServiceDescription').value='FICTIONAL QA additional service for exact tax-boundary verification'+(s!=='large'?'':' - complete long service description with quantities 12345 ft and customer requirements preserved. '.repeat(3));el('extraServiceAmount').value=s==='original'?'293.82':'999999999.99';renderSummary()},${JSON.stringify(scenario)});`+anchor);
script=script.replace('const dl=await wait;',"const dl=await wait.catch(async e=>{console.error('EXPORT STATUS',await page.locator('#status').textContent());throw e});");
script=script.replace("page.on('pageerror',e=>errors.push(e.message));","page.on('console',m=>{if(m.text().startsWith('AMOUNT_LAYOUT'))console.log(m.text())});page.on('pageerror',e=>errors.push(e.message));");
const capture="  const image=node.querySelector?.('[data-expanded-aerial]');";assert(script.includes(capture));
script=script.replace(capture,`  if(node.classList.contains('aq-expanded-page')||node.classList.contains('report')){
   await window.qaRecordPdfImage({layout:node.classList.contains('report')?'single':'expanded',pricingRows:[...node.querySelectorAll('.line,.pdf-qa-pagination-note')].map(n=>n.textContent)});
   for(const row of node.querySelectorAll('.line')){const amount=row.lastElementChild;if(!amount||row.children.length!==2)continue;const r=document.createRange();r.selectNodeContents(amount);const boxes=[...r.getClientRects()].filter(b=>b.width>0&&b.height>0);const ys=new Set(boxes.map(b=>Math.round(b.top)));if(ys.size>1){console.error('AMOUNT_LAYOUT wrapped '+amount.textContent);throw Error('Currency amount wrapped: '+amount.textContent);}const a=amount.getBoundingClientRect(),p=row.getBoundingClientRect(),d=row.firstElementChild.getBoundingClientRect();if(a.right>p.right+1||d.right>a.left+1)throw Error('Price columns overlap/overflow');}
  }
`+capture);
if(process.env.QA_AMOUNT_REMOVE_FIX==='1')script=script.replace(' const captureChecks=[];',` await page.evaluate(()=>{for(const sheet of document.styleSheets){let rules;try{rules=sheet.cssRules}catch{continue}for(let i=rules.length-1;i>=0;i--)if(rules[i].selectorText?.startsWith('.reportPrice .line >'))sheet.deleteRule(i)}}); const captureChecks=[];`);
const pdfAnchor=' const captureChecks=[];';assert(script.includes(pdfAnchor));
script=script.replace(pdfAnchor,` if(${JSON.stringify(scenario)}==='pages')await page.evaluate(()=>{const pricing=el('rPricing'),extra=[...pricing.children].find(n=>n.textContent.includes('FICTIONAL QA additional service'));for(let i=0;i<15;i++){const row=document.createElement('div');row.className='pdf-qa-pagination-note';row.style.padding='12px 0';row.textContent='PAGE BREAK FIXTURE '+(i+1)+' - Nonbillable document note for pagination only. Complete customer instructions are preserved; no additional charges.';pricing.insertBefore(row,extra)}});
`+` const expectedPricingRows=await page.evaluate(()=>[...el('rPricing').children].map(n=>n.textContent));`+pdfAnchor);
const finish=' await page.screenshot({path:';assert(script.includes(finish));script=script.replace(finish,` for(const layout of ['single','expanded'])assert.deepEqual(captureChecks.filter(c=>c.layout===layout).flatMap(c=>c.pricingRows),expectedPricingRows,layout+' capture preserves every complete pricing description, note and amount in order');`+finish);
new Function('require',script)(require);
