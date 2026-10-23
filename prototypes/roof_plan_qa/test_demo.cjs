const {JSDOM}=require('jsdom'),assert=require('node:assert/strict'),fs=require('node:fs'),cp=require('node:child_process'),os=require('node:os'),path=require('node:path');
const out=fs.mkdtempSync(path.join(os.tmpdir(),'aq-roof-prototype-'));
try{
 cp.execFileSync('python',['prototypes/roof_plan_qa/build_demo.py',out]);
 const html=fs.readFileSync(path.join(out,'Contractor_Confirmation_Demo.html'),'utf8');
 const dom=new JSDOM(html,{runScripts:'dangerously',beforeParse(w){w.fetch=()=>{throw Error('No provider calls allowed')};}}),w=dom.window,el=id=>w.document.getElementById(id),change=id=>el(id).dispatchEvent(new w.Event('change'));
 assert(el('reviewButton').disabled);assert(el('review').hidden);assert.equal(w.document.querySelectorAll('polygon[data-plane]').length,4);assert.equal(w.document.querySelectorAll('line.ridge').length,2);
 for(const [id,value] of [['A1','6'],['A2','6'],['B1','4'],['B2','4']]){el('pitch-'+id).value=value;change('pitch-'+id);}
 for(const id of ['R1','R2','complete']){el(id).checked=true;change(id);}
 assert(!el('reviewButton').disabled);el('reviewButton').click();assert(!el('review').hidden);assert(el('price').textContent.includes('1743.21'));
 for(const id of ['R1','R2','complete']){el(id).checked=false;change(id);assert(el('reviewButton').disabled);assert(el('review').hidden);el(id).checked=true;change(id);}
 el('pitch-A1').value='8';change('pitch-A1');assert(el('reviewButton').disabled);assert(el('review').hidden);
 el('pitch-A1').value='6';change('pitch-A1');assert(!el('reviewButton').disabled);
 w.document.querySelector('[data-plane="B1"]').dispatchEvent(new w.MouseEvent('click'));assert.equal(w.document.activeElement.id,'pitch-B1');
 el('reset').click();assert(el('reviewButton').disabled);assert([...w.document.querySelectorAll('select')].every(n=>!n.value));assert([...w.document.querySelectorAll('input')].every(n=>!n.checked));
 assert(!/<script[^>]+src=|<iframe|<img[^>]+src="https?:|fetch\(/i.test(html));dom.window.close();
 console.log('PASS standalone emulated confirmation UI: four planes/two ridges, initial blocking, wrong/missing pitch rejection, missing ridge/scope rejection, stale review clearing, selection/focus and reset; no network resources');
}finally{fs.rmSync(out,{recursive:true,force:true});}
