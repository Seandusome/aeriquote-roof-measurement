// Trusted-touch correction + forced Chromium target close; disposable loopback only.
const fs=require('fs'),assert=require('assert/strict');
process.env.QA_BROWSER_WIDTHS='390';process.env.QA_BROWSER_INDUSTRIES='snow';process.env.QA_BROWSER_IMAGES='hide';process.env.QA_BROWSER_ALL_PDFS='1';
let script=fs.readFileSync('scripts/test_prelaunch_browser.cjs','utf8').replace('const page=await context.newPage()','let page=await context.newPage()').replace('viewport:{width,height:1000},acceptDownloads:true','viewport:{width,height:1000},hasTouch:true,isMobile:true,acceptDownloads:true');
const anchor="console.log('report opened');const list=";assert(script.includes(anchor));script=script.replace(anchor,`console.log('report opened');
 const oldRows=await(await context.request.get('http://127.0.0.1:8765/api/estimates')).json();const current=oldRows.find(r=>r.customer_name==='FICTIONAL QA '+industry+' '+width);assert(current);
 const storedBefore=await(await context.request.get('http://127.0.0.1:8765/api/estimates/'+current.id)).json();const usageBefore=(await(await context.request.get('http://127.0.0.1:8765/api/account/profile')).json()).allowance;
 await page.getByRole('button',{name:'RETRACE OUTLINE — AREA 1',exact:true}).tap();assert.equal(await page.evaluate(()=>reportMeasurementCorrection.points.length),0);await page.locator('#customerMap').scrollIntoViewIfNeeded();const bounds=await page.locator('#customerMap').boundingBox();for(const p of [[65,90],[160,90],[160,160],[65,160]])await page.touchscreen.tap(bounds.x+p[0],bounds.y+p[1]);assert.equal(await page.evaluate(()=>reportMeasurementCorrection.points.length),4);
 const cdp=await context.newCDPSession(page),target=(await cdp.send('Target.getTargetInfo')).targetInfo.targetId;await cdp.send('Target.closeTarget',{targetId:target});
 page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());await page.goto('http://127.0.0.1:8765/?industry='+industry);await page.waitForFunction(()=>typeof openHistoricalEstimate==='function');
 assert.deepEqual(await(await context.request.get('http://127.0.0.1:8765/api/estimates/'+current.id)).json(),storedBefore);assert.equal((await(await context.request.get('http://127.0.0.1:8765/api/estimates/'+current.id+'/versions')).json()).revisions.length,0);assert.deepEqual((await(await context.request.get('http://127.0.0.1:8765/api/account/profile')).json()).allowance,usageBefore);
 console.log('PASS forced close during touch retrace retains exact saved estimate, no revision or allowance deduction; unfinished draft is not autosaved');
 const list=`);
new Function('require',script)(require);
