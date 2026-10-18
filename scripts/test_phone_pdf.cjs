const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {JSDOM}=require('jsdom');
const app=fs.readFileSync('app.py','utf8');
const helper=app.slice(app.indexOf('async function captureSinglePageEstimate('),app.indexOf('async function downloadEstimatePDF('));
async function run(width,fail=false){
 const dom=new JSDOM('<body><div class="report"><div id="customerMap"><span>approved aerial</span></div><div class="reportActions">buttons</div><div id="reportOutlineControls">edit</div><div id="rPricing">unchanged total</div></div></body>');
 const doc=dom.window.document,report=doc.querySelector('.report');report.getBoundingClientRect=()=>({width});
 const before=report.outerHTML,calls=[];
 const html2canvas=async(node,options)=>{calls.push({node,options});if(node.id==='customerMap'){const c=doc.createElement('canvas');c.width=670;c.height=930;return c;}
  if(width<900){assert.equal(node.style.width,'1320px');assert(node.classList.contains('pdf-export'));assert.equal(node.querySelector('.reportActions'),null);assert.equal(node.querySelector('[id]'),null);assert.equal(node.querySelectorAll('canvas').length,1);assert.equal(options.windowWidth,1440);}
  if(fail)throw Error('capture failed');return 'captured';};
 const context=vm.createContext({document:doc,html2canvas});vm.runInContext(helper,context);
 if(fail)await assert.rejects(context.captureSinglePageEstimate(report),/capture failed/);else assert.equal(await context.captureSinglePageEstimate(report),'captured');
 assert.equal(report.outerHTML,before,'live report and geometry must remain untouched');assert.equal(doc.querySelectorAll('.report').length,1,'export clone must be removed');assert.equal(calls.length,width<900?2:1);if(width>=900)assert.equal(calls[0].node,report);
}
(async()=>{await run(335);await run(272);await run(1320);await run(335,true);console.log('PASS: phone PDF uses full paper width, frozen map canvas, clean clone, cleanup on failure; desktop unchanged');})().catch(e=>{console.error(e);process.exit(1)});
