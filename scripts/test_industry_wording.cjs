// Exercise the rendered app buttons and Leaflet click handler in a DOM environment.
const {JSDOM,VirtualConsole}=require('jsdom');const fs=require('fs'),assert=require('assert/strict'),path=require('path'),{execFileSync}=require('child_process');
(async()=>{const errors=[];const vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e.message));const raw=execFileSync('python',['-c',"import ast; from pathlib import Path; m=ast.parse(Path('app.py').read_text()); print(next(ast.literal_eval(n.value) for n in m.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='HTML' for t in n.targets)))"],{maxBuffer:4000000}).toString();const leafletRoot=path.dirname(require.resolve('leaflet/package.json'));const html=raw.replace(/<script[^>]+src=[^>]+>\s*<\/script>/g,'').replace(/<link[^>]+>/g,'').replace(/\{%.*?%\}/g,'').replace(/\{\{GOOGLE_MAPS_API_KEY\}\}/g,'test-key').replace(/\{\{.*?\}\}/g,'').replace('</head>','<style>'+fs.readFileSync(path.join(leafletRoot,'dist/leaflet.css'),'utf8')+'</style><script>'+fs.readFileSync(path.join(leafletRoot,'dist/leaflet.js'),'utf8')+'</script><script>L.Browser.svg=true;</script></head>');for(const industry of ['roofing','snow','pressure','paving','landscaping','commercial']){
const dom=new JSDOM(html,{url:'https://test.invalid/?industry='+industry,runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,beforeParse(w){w.fetch=async()=>({ok:true,json:async()=>({})});w.alert=()=>{};Object.defineProperty(w.HTMLElement.prototype,'clientWidth',{get(){return this.id==='map'?700:1440}});Object.defineProperty(w.HTMLElement.prototype,'clientHeight',{get(){return this.id==='map'?550:800}});w.HTMLElement.prototype.scrollIntoView=()=>{};}});const w=dom.window;await new Promise(r=>w.addEventListener('load',r,{once:true}));
const id=x=>w.document.getElementById(x);
function visible(n){for(let p=n;p&&p.tagName;p=p.parentElement){const s=w.getComputedStyle(p);if(s.display==='none'||s.visibility==='hidden'||p.hidden)return false;}return true}
{
 dom.reconfigure({url:'https://test.invalid/?industry='+industry});
 w.eval(`el('businessType').value='${industry}';sessionToken='audit';resetMeasurementForNewProperty();sessionToken='audit';businessTypeChanged();map.setView([52,-106],19)`);
 id('toolAreaBtn').click();
 for(const p of [[52,-106],[52,-105.9999],[52.0001,-105.9999],[52.0001,-106]])w.eval(`map.fire('click',{latlng:L.latLng(${p[0]},${p[1]})})`);
 id('areaStartBtn').click();w.eval('applyBusinessTerminology()');
 const leaf=[...w.document.querySelectorAll('body *')].filter(n=>!n.children.length&&!['SCRIPT','STYLE','OPTION'].includes(n.tagName)&&visible(n));
 const lines=leaf.map(n=>(n.textContent||'').trim()).filter(Boolean);
 const attributes=[...w.document.querySelectorAll('[data-tip],[title],[aria-label],input[placeholder],textarea[placeholder]')].filter(visible).map(n=>[n.id,...['data-tip','title','aria-label','placeholder'].map(k=>n.getAttribute(k)||'')].filter(Boolean).join(' | '));
assert.equal(id('toolAreaBtn').querySelector('small').textContent,w.eval('AERI_TOOL_COPY[currentBusinessType()].area'));
 assert.equal(id('toolLinearBtn').querySelector('small').textContent,w.eval('AERI_TOOL_COPY[currentBusinessType()].linear'));
 if(industry!=='roofing'){
  assert(!/roof|shingle|pitch|gallon|extra structures/i.test(lines.join(' ')),industry+' area workspace: '+lines.filter(t=>/roof|shingle|pitch|gallon|extra structures/i.test(t)));
  assert(!visible(id('areaAutoBtn')),industry+' must not expose roof AutoMeasure');
 }
 id('toolLinearBtn').click();w.eval('applyBusinessTerminology()');
 if(industry!=='roofing'){
  assert(!/roof|shingle|pitch/i.test(id('status').textContent),industry+' linear status');
  assert(!visible(id('linearAutoBtn')),industry+' linear must not expose roof AutoMeasure');
 }
 for(const p of [[52,-106],[52,-105.9999]])w.eval(`map.fire('click',{latlng:L.latLng(${p[0]},${p[1]})})`);
 id('linearStartBtn').click();

 w.eval(`el('streetViewChoice').value='none';el('customerName').value='AUDIT TEST';document.body.classList.remove('report-open');estimateOpenInProgress=false`);
 await w.eval('showCustomerEstimate()');w.eval('applyBusinessTerminology()');
if(industry!=='roofing'){
  const report=[...id('reportOverlay').querySelectorAll('*')].filter(n=>!n.children.length&&visible(n)).map(n=>n.textContent).join(' ');
  assert(!/roof|shingle|pitch|gallon/i.test(report),industry+' customer estimate: '+report);
  assert(!/roof|shingle|pitch/i.test(id('reportOutlineHelpTop').textContent),industry+' outline help');
 }
 assert(id('rProperty').textContent.includes('ft'),industry+' customer quantities');
 assert(id('rPricing').textContent.includes('$'),industry+' customer pricing');
 // A length-only quote must describe a length, rather than a surface area.
 w.eval(`el('reportOverlay').style.display='none';document.body.classList.remove('report-open');estimateOpenInProgress=false;commercialAreas=[];areaPoints=[];areaMeasurementSaved=false;measurementViewMode='linear'`);
 await w.eval('showCustomerEstimate()');
 assert(id('rProperty').textContent.includes('Measured Service Length'),industry+' linear-only quantity');
 assert(!id('rProperty').textContent.includes('Only the measured service area'),industry+' linear-only scope');
 // Industry switches must replace tool examples even after Snow replaces text nodes.
 for(const target of ['snow','pressure','paving','landscaping','commercial','roofing']){
  dom.reconfigure({url:'https://test.invalid/?industry='+target});
  w.eval(`el('businessType').value='${target}';businessTypeChanged();applyBusinessTerminology()`);
  const expected={roofing:['Lawns','Gutters'],snow:['Driveways','Sidewalks'],pressure:['Driveways','Gutters'],paving:['Driveways','Curbing'],landscaping:['Lawns','Edging'],commercial:['Parking lots','Curbs']}[target];
  assert(id('toolAreaBtn').querySelector('small').textContent.startsWith(expected[0]),target+' area examples after switch');
  assert(id('toolLinearBtn').querySelector('small').textContent.startsWith(expected[1]),target+' linear examples after switch');
  if(target!=='snow')assert.equal(id('toolAreaBtn').querySelector('b').textContent,'+ ADD AREA');
 }

 dom.reconfigure({url:'https://test.invalid/?industry='+industry});
 w.eval(`el('businessType').value='${industry}';businessTypeChanged();el('marketingHeading').value='Custom company heading';el('marketingCtaText').value='Custom customer message';el('marketingEnabled').checked=false`);
 const custom=w.eval('JSON.stringify(captureIndustryMarketing())');
 const other=industry==='snow'?'pressure':'snow';dom.reconfigure({url:'https://test.invalid/?industry='+other});w.eval(`el('businessType').value='${other}';businessTypeChanged()`);
 dom.reconfigure({url:'https://test.invalid/?industry='+industry});w.eval(`el('businessType').value='${industry}';businessTypeChanged()`);
 assert.equal(w.eval('JSON.stringify(captureIndustryMarketing())'),custom,industry+' custom text and marketing off retained');
 console.log('PASS '+industry+': area + linear controls, instructions, estimates, switching and custom marketing preservation');

 w.eval(`clearTimeout(customerMapBuildTimer);customerMapBuildTimer=null;estimateOpenInProgress=false;el('reportOverlay').style.display='none';document.body.classList.remove('report-open')`);
}
await new Promise(resolve=>setTimeout(resolve,100));w.eval('_aeriTermObserver.disconnect();clearTimeout(_aeriTermTimer);clearTimeout(customerMapBuildTimer)');assert.deepEqual(errors,[]);dom.window.close();}
console.log('PASS: all six industry wording and estimate flows');
})().catch(e=>{console.error(e);process.exit(1)});
