// Actual Chromium exports for adjacent facets plus a detached garage, with
// explicit different pitches. Disposable loopback providers/accounts only.
const fs=require('fs'),assert=require('assert/strict');
process.env.QA_BROWSER_WIDTHS='1440';process.env.QA_BROWSER_INDUSTRIES='roofing';process.env.QA_BROWSER_IMAGES='hide';
let script=fs.readFileSync('scripts/test_prelaunch_browser.cjs','utf8');
const anchor="  await page.click('#confirmRoofPitches');";assert(script.includes(anchor));
script=script.replace(anchor,String.raw`
  await page.evaluate(()=>beginManualRoofSection());await draw(pts.map(([lat,lng])=>[lat,lng+.0001]));await page.selectOption('#pitchSel','0');await page.evaluate(()=>{pitchChanged();finishTrace()});
  await page.evaluate(()=>beginManualRoofSection());await draw(pts.map(([lat,lng])=>[lat+.0003,lng]));await page.selectOption('#pitchSel','45');await page.evaluate(()=>{pitchChanged();finishTrace()});
  assert.equal(await page.evaluate(()=>manualPlanes.length),3,'Two adjacent facets and detached garage must survive export setup');
  assert.deepEqual(await page.evaluate(()=>manualPlanes.map(p=>p.pitch_degrees)),[22.62,0,45]);
  assert((await page.locator('#manualRoofSections').innerText()).includes('5/12 pitch'));
  assert((await page.locator('#manualRoofSections').innerText()).includes('0/12 (flat)'));
  assert((await page.locator('#summary').innerText()).includes('Roof confirmation required'));
  assert(!(await page.locator('#summary').innerText()).includes('pitch confirmed'));
  assert.equal(await page.locator('#manualRoofScopeConfirmed').isVisible(),false);
  assert.equal(await page.locator('#garageControls').isVisible(),false);
  await page.click('#confirmRoofPitches');
  assert.equal(await page.locator('#confirmRoofPitches').getAttribute('aria-pressed'),'true');
  const confirmedGeometry=await page.evaluate(()=>JSON.stringify(manualPlanes));
  await page.locator('#manualRoofSections .structure').first().getByRole('button',{name:'EDIT',exact:true}).click();
  await page.selectOption('#pitchSel','36.87');await page.click('#traceBtn');
  assert.equal(await page.evaluate(()=>JSON.stringify(manualPlanes)),confirmedGeometry,'Cancel preserves geometry and pitch');
  assert.equal(await page.locator('#confirmRoofPitches').getAttribute('aria-pressed'),'false');
  assert(await page.locator('#createEstimateBtn').isDisabled());

`+anchor);
const end=" await page.screenshot({path:";assert(script.includes(end));script=script.replace(end," console.log('PASS actual Chromium Single and Expanded roofing downloads: three sections, explicit22.62/0/45pitch, unchanged saved geometry/pricing/customer');\n"+end);
new Function('require',script)(require);
