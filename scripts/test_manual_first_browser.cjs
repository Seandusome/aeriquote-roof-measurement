// Extend the existing native-export workflow, keeping its name, pricing and reopen assertions.
const fs=require('fs'),assert=require('assert/strict');
process.env.QA_BROWSER_WIDTHS='1440,390';process.env.QA_BROWSER_INDUSTRIES='roofing';process.env.QA_BROWSER_IMAGES='hide';process.env.QA_BROWSER_ALL_PDFS='1';process.env.QA_BROWSER_OUTPUT=process.env.QA_MANUAL_OUTPUT||'/tmp/aq-manual-first';
let script=fs.readFileSync('scripts/test_prelaunch_browser.cjs','utf8');
function change(a,b){assert(script.includes(a),a.slice(0,80));script=script.replace(a,b)}
change("chromium.launch({headless:true,args:","chromium.launch({headless:true,executablePath:process.env.QA_CHROMIUM_EXECUTABLE||undefined,args:");
// Faithful simulated Static Maps response: bake the submitted saved outline into fixture pixels.
change("if(u.pathname.startsWith('/manual-report-map/')||u.pathname==='/saved-estimate-report-map')return r.fulfill({body:grid,contentType:'image/svg+xml',headers:{'X-AeriQuote-Map-View':JSON.stringify({latitude:52,longitude:-106,zoom:19,width:640,height:420})}});",`if(u.pathname.startsWith('/manual-report-map/')||u.pathname==='/saved-estimate-report-map'){
 const body=r.request().postDataJSON(),rings=body.planes||body.roofs.map(x=>x.points),view={latitude:52,longitude:-106,zoom:19,width:640,height:420};
 const world=p=>{const v=Math.sin(p.lat*Math.PI/180);return[(p.lng+180)/360*256*2**19,(.5-Math.log((1+v)/(1-v))/(4*Math.PI))*256*2**19]},center=world({lat:52,lng:-106});
 const polygons=rings.map(ring=>'<polygon fill="#f59e0b22" stroke="#d97706" stroke-width="5" points="'+ring.map(p=>{const q=world(p);return[(q[0]-center[0])*2+640,(q[1]-center[1])*2+420].join(',')}).join(' ')+'"/>').join('');
 const svg='<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="840"><rect width="1280" height="840" fill="#edf1ef"/><text x="20" y="35">FICTIONAL QA IMAGERY — NOT A REAL PROPERTY</text>'+polygons+'</svg>';
 return r.fulfill({body:svg,contentType:'image/svg+xml',headers:{'X-AeriQuote-Map-View':JSON.stringify(view)}});
}`);
change(" console.log('loaded',", " assert.equal(await page.locator('#toolAutoBtn').isVisible(),false);assert.equal(await page.getByRole('button',{name:/KEEP OUTLINE|REVIEW OUTLINE/i}).count(),0);await page.screenshot({path:output+'/manual-ready-'+width+'.png',fullPage:true});\n console.log('loaded',");
change("  await page.click('#confirmRoofPitches');",`  assert.equal(await page.evaluate(()=>manualPlanes.length),1);
  await page.click('#traceBtn');await draw(pts.map(([lat,lng])=>[lat,lng+.00018]));await page.selectOption('#pitchSel','26.57');await page.evaluate(()=>pitchChanged());await page.click('#finishTrace');
  assert.equal(await page.evaluate(()=>manualPlanes.length),2);await page.click('#confirmRoofPitches');`);
// Independently verify editing and a server recovery draft before returning to the saved report for PDF export.
change(" const captureChecks=[];",` const beforeEdit=await(await context.request.get('http://127.0.0.1:8765/api/estimates/'+saved.id)).json();
 await page.click('#backToDealerBtn');await page.waitForFunction(()=>!document.body.classList.contains('report-open')&&!!sessionToken);
 assert.equal(await page.evaluate(()=>manualPlanes.length),2);const geometry=await page.evaluate(()=>JSON.stringify(manualPlanes));
 const afterEdit=await(await context.request.get('http://127.0.0.1:8765/api/estimates/'+saved.id)).json();assert.deepEqual(afterEdit,beforeEdit,'Opening edit does not change saved record');
 const keepWorking=page.locator('#workspaceRecoveryContinue');if(await keepWorking.isVisible())await keepWorking.click();
 await page.click('#customerNotes');await page.fill('#customerNotes','MANUAL FIRST DRAFT '+width);const flushed=await page.evaluate(()=>window.aqRecovery.flush());if(!flushed)console.log('DRAFT DIAGNOSTIC',await page.evaluate(()=>({message:el('workspaceRecoveryStatus')?.textContent,status:el('status')?.textContent,choices:el('workspaceRecoveryChoices')?.innerText})));assert(flushed);
 const recovery=await context.newPage();await recovery.goto('http://127.0.0.1:8765/?industry=roofing');await recovery.getByRole('button',{name:'Restore',exact:true}).first().waitFor();await recovery.getByRole('button',{name:'Restore',exact:true}).first().click();
 await recovery.waitForFunction(()=>el('customerNotes')?.value.startsWith('MANUAL FIRST DRAFT')&&manualPlanes.length===2);
 assert.equal(await recovery.evaluate(()=>JSON.stringify(manualPlanes)),geometry);await recovery.waitForFunction(()=>el('workspaceRecoveryStatus')?.textContent.includes('24 hours')||el('workspaceRecoveryStatus')?.textContent.includes('Draft restored'));
 await recovery.screenshot({path:output+'/restored-'+width+'.png',fullPage:true});await recovery.close();
 await page.goto('http://127.0.0.1:8765/?industry=roofing');await page.waitForFunction(()=>typeof openHistoricalEstimate==='function');await page.evaluate(id=>openHistoricalEstimate(id,-1),saved.id);await page.waitForFunction(()=>document.body.classList.contains('report-open')&&!estimateOpenInProgress);
 console.log('PASS normal manual UI: main + garage, pitch, edit read-only, exact server draft restore',width);
 const captureChecks=[];`);
// Discard the test-only retained recovery copy through normal choice before later width runs if needed.
const Module=require('module');const runner=new Module(__filename,module);runner.filename=__filename;runner.paths=module.paths;runner._compile(script,__filename);
