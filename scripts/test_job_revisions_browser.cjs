// Real Chromium existing-job audit, fictional providers and normal paid policy.
const fs=require('fs'),assert=require('assert/strict');
process.env.QA_BROWSER_WIDTHS='1440';process.env.QA_BROWSER_IMAGES='hide';
let script=fs.readFileSync('scripts/test_prelaunch_browser.cjs','utf8');
script=script.replace('const results=[];','const results=[],auditSeen=[];');
const mapRoute=script.split('\n').find(line=>line.includes("u.pathname.startsWith('/manual-report-map/')"));assert(mapRoute);
script=script.replace(mapRoute," if(u.pathname.startsWith('/manual-report-map/')||u.pathname==='/saved-estimate-report-map')return r.continue();");
script=script.replace("await page.fill('#streetAddress','1 Fictional QA Street')","await page.fill('#streetAddress','1 Fictional '+industry+' QA Street')");
const roof="  await page.click('#confirmRoofPitches');";assert(script.includes(roof));
script=script.replace(roof,String.raw`
  await page.click('#traceBtn');await draw(pts.map(([lat,lng])=>[lat,lng+.00015]));await page.selectOption('#pitchSel','0');await page.click('#finishTrace');
  await page.click('#traceBtn');await draw(pts.map(([lat,lng])=>[lat+.00028,lng]));await page.selectOption('#pitchSel','45');await page.click('#finishTrace');
  assert.deepEqual(await page.evaluate(()=>manualPlanes.map(p=>p.pitch_degrees)),[22.62,0,45]);
`+roof);
const anchor=' // A second page load simulates refresh; reopen the owned stored snapshot through the actual handler.';assert(script.includes(anchor));
script=script.replace(anchor,String.raw`
 await require('./job_revision_checks.cjs')({page,context,industry,saved,payload,draw,pts,output,before,errors,seen:auditSeen});
`+anchor);
script=script.replace('openHistoricalEstimate(id,-1),saved.id)','openHistoricalEstimate(id,0),saved.id)');
new Function('require',script)(require);
