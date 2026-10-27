const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {JSDOM}=require('jsdom');
const app=fs.readFileSync('app.py','utf8');
const helper=app.slice(app.indexOf('async function captureSinglePageEstimate('),app.indexOf('async function downloadEstimatePDF('));
async function run(width,fail=false,saved=false){
 const dom=new JSDOM('<body><div class="report"><div id="customerMap"><span>approved aerial</span></div><div class="reportActions">buttons</div><div id="reportOutlineControls">edit</div><div id="rPricing">unchanged total</div></div></body>');
 const doc=dom.window.document,report=doc.querySelector('.report');report.getBoundingClientRect=()=>({width});
 const sourceCanvas=saved?doc.createElement('canvas'):null;if(sourceCanvas){sourceCanvas.dataset.mapView='{}';sourceCanvas.width=1280;sourceCanvas.height=840;doc.querySelector('#customerMap').replaceChildren(sourceCanvas);dom.window.HTMLCanvasElement.prototype.getContext=()=>({drawImage(){}});}
 const before=report.outerHTML,calls=[];
 const html2canvas=async(node,options)=>{calls.push({node,options});if(node.id==='customerMap'){const c=doc.createElement('canvas');c.width=670;c.height=930;return c;}
  if(width<900){assert.equal(node.style.width,'1320px');assert(node.classList.contains('pdf-export'));assert.equal(node.querySelector('.reportActions'),null);assert.equal(node.querySelector('[id]'),null);assert.equal(node.querySelectorAll('canvas').length,1);const pixels=node.querySelector('canvas');assert(Math.abs(parseFloat(pixels.style.width)/parseFloat(pixels.style.height)-pixels.width/pixels.height)<1e-8,'Aerial aspect ratio must be preserved');assert.equal(options.windowWidth,1440);}
  if(fail)throw Error('capture failed');return 'captured';};
 const context=vm.createContext({document:doc,html2canvas});vm.runInContext(helper,context);
 if(fail)await assert.rejects(context.captureSinglePageEstimate(report),/capture failed/);else assert.equal(await context.captureSinglePageEstimate(report),'captured');
 assert.equal(report.outerHTML,before,'live report and geometry must remain untouched');assert.equal(doc.querySelectorAll('.report').length,1,'export clone must be removed');assert.equal(calls.length,width<900&&!saved?2:1);if(width>=900)assert.equal(calls[0].node,report);
}
async function streetRatio(w,h,fail=false){
 const dom=new JSDOM('<div class="report"><img id="rStreet" class="reportStreet" style="display:block;width:400px;height:225px"><div id="rPricing">123.45</div></div>');
 const doc=dom.window.document,report=doc.querySelector('.report'),source=doc.querySelector('img');report.getBoundingClientRect=()=>({width:1320});
 for(const [k,v] of Object.entries({naturalWidth:w,naturalHeight:h,complete:true}))Object.defineProperty(source,k,{value:v});
 const original=report.outerHTML;let draw;
 const context=vm.createContext({document:doc,html2canvas:async(node,options)=>{
  assert.equal(typeof options.onclone,'function','Single capture must preserve Street View source proportions');
  const clone=node.cloneNode(true),image=clone.querySelector('img');Object.defineProperty(image,'clientWidth',{value:398});Object.defineProperty(image,'clientHeight',{value:223});
  dom.window.HTMLCanvasElement.prototype.getContext=()=>({fillRect(){},drawImage(...args){draw=args}});
  options.onclone(doc,clone);const canvas=clone.querySelector('canvas');assert(canvas,'Only the cloned Street View becomes a fitted pixel frame');
  assert.equal(canvas.width,796);assert.equal(canvas.height,446);assert.equal(canvas.className,source.className);assert.equal(canvas.style.cssText,source.style.cssText);
  assert(Math.abs(draw[3]/draw[4]-w/h)<1e-10,'Source image ratio survives both directions');assert(draw[1]>=0&&draw[2]>=0&&draw[1]+draw[3]<=canvas.width+.001&&draw[2]+draw[4]<=canvas.height+.001,'Entire source frame stays within the existing photo box');
  assert.equal(clone.querySelector('#rPricing').textContent,'123.45');if(fail)throw Error('capture failed');return 'captured';}});
 vm.runInContext(helper,context);if(fail)await assert.rejects(context.captureSinglePageEstimate(report),/capture failed/);else await context.captureSinglePageEstimate(report);
 assert.equal(report.outerHTML,original,'Single capture must never modify the live source image, layout or data');
}
(async()=>{await streetRatio(640,360);await streetRatio(360,640);await streetRatio(360,640,true);await run(335);await run(272);await run(1320);await run(335,true);await run(335,false,true);console.log('PASS: phone PDF uses full paper width, frozen map canvas, clean clone, cleanup on failure; proportional Street View and desktop layout preserved');})().catch(e=>{console.error(e);process.exit(1)});
