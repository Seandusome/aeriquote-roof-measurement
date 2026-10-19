/* Exercise shipped setup pages and handler with isolated account/network fixtures. */
const fs=require('fs'),path=require('path'),assert=require('assert'),{JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..');
const source=fs.readFileSync(path.join(root,'site/onboarding.js'),'utf8').replace('window.location.assign(', 'window.__navigate(');
const savedFixtures={};
const tick=()=>new Promise(r=>setTimeout(r,0));
(async()=>{
for(const [page,industry] of [['roofer','roofing'],['snow','snow'],['pressure','pressure'],['paving','paving'],['landscaping','landscaping'],['commercial','commercial']]){
 for(const suffix of ['', '.html']){
  const dom=new JSDOM(fs.readFileSync(path.join(root,'site/'+page+'-setup.html'),'utf8'),{url:'https://test.invalid/site/'+page+'-setup'+suffix,runScripts:'outside-only'});
  const w=dom.window,d=w.document;let destination=null,fail=false;const calls=[];
  w.scrollTo=()=>{};w.__navigate=url=>destination=url;w.fetch=async(url,options={})=>{calls.push({url,options});return {ok:!fail,json:async()=>({profile:{company:'QA Company',name:'QA Owner',email:'qa@example.invalid',country:'US'}})};};
  w.eval(source);await tick();const field=id=>d.getElementById(id),next=()=>field('nextBtn').click();
  assert.equal(d.querySelectorAll('.setup-step').length,4,page+' four steps');assert(d.querySelector('.setup-help').textContent.includes('of 4'));
  assert.equal(field('companyName').value,'QA Company');assert.equal(field('companyEmail').value,'qa@example.invalid');
  assert.equal(field('brandCompany').value,'QA Company',page+' no repeat contact entry');
  assert.equal(field('country').value,'United States');assert.equal(field('region').value,'');assert([...field('region').options].some(o=>o.value==='CA'&&o.textContent==='California'));
  assert(![...field('region').options].some(o=>o.value==='SK'),page+' no Canadian state');assert(field('tax1').closest('label').textContent.includes('Sales Tax'));assert(field('tax2').closest('label').textContent.includes('Additional Tax')); 
  next();assert(d.querySelector('[data-step="1"]').classList.contains('active'),page+' require region');assert(!field('setupError').hidden);
  field('country').value='Canada';field('country').dispatchEvent(new w.Event('change',{bubbles:true}));field('region').value='SK';next();assert(d.querySelector('[data-step="4"]').classList.contains('active'));
  next();assert(d.querySelector('[data-step="4"]').classList.contains('active'),page+' require explicit taxes');
  field('tax1').value='5';field('tax2').value='6';d.querySelector('input[name=taxmode][value=included]').checked=true;
  field('defaultPrice').value='-1';next();assert(d.querySelector('[data-step="4"]').classList.contains('active'),page+' invalid rate');field('defaultPrice').value='0.37';
  next();assert(d.querySelector('[data-step="7"]').classList.contains('active'));
  assert(!field('warrantyStatement').closest('details').open,page+' optional message collapsed');
  field('warrantyStatement').value='Customer service terms';field('estimateMessage').value='Customer message';field('ctaHeading').value='Arrange this service';
  next();assert(d.querySelector('[data-step="9"]').classList.contains('active'));assert(field('setupReview').textContent.includes('5% + 6%'));assert(field('setupReview').textContent.includes('included in price'));
  field('backBtn').click();assert.equal(field('estimateMessage').value,'Customer message',page+' back preserves input');next();
  const finish=field('finishSetup');fail=true;finish.click();await tick();assert.equal(destination,null);assert(!field('setupError').hidden);assert.equal(w.localStorage.getItem('sxDealerDefaults'),null,page+' failed account save not cached');assert(!finish.disabled);
  fail=false;finish.click();finish.click();await tick();
  assert.equal(destination,'/?industry='+industry,page+suffix+' navigate');
  const posts=calls.filter(c=>c.options.method==='POST');assert.equal(posts.length,2,page+' failed attempt plus one successful retry');
  const saved=JSON.parse(posts.at(-1).options.body);savedFixtures[industry]=saved;assert.equal(saved.businessType,industry);assert.equal(saved.province,'SK');assert.equal(saved.country,'CA');assert.equal(saved.gst,'5');assert.equal(saved.pst,'6');assert.equal(saved.pricingMode,'included');assert.equal(saved.price,'0.37');assert.equal(saved.name,'QA Owner');assert.equal(saved.warrantyStatement,'Customer service terms');assert.equal(saved.estimateMessage,'Customer message');assert.equal(saved.ctaHeading,'Arrange this service');
  assert.equal(JSON.parse(w.localStorage.getItem('sxDealerDefaults')).gst,'5');assert.equal(w.localStorage.getItem('aeriQuoteIndustry'),industry);
  // Changing country clears incompatible region, supports all Canadian provinces/territories.
  field('country').value='Canada';field('country').dispatchEvent(new w.Event('change',{bubbles:true}));assert.equal(field('region').value,'');assert.equal(field('tax1').value,'');assert.equal(field('tax2').value,'');assert(field('tax1').closest('label').textContent.includes('Federal / HST'));assert.equal(field('region').options.length,14);assert([...field('region').options].some(o=>o.value==='NU'));field('country').value='United States';field('country').dispatchEvent(new w.Event('change',{bubbles:true}));assert(field('tax2').closest('label').hidden);assert.equal(field('tax2').value,'0');field('tax2').value='6';assert.equal((await w.saveIndustrySetupLocal(industry)).pst,'0',page+' US has one sales tax matching the estimate engine');
  dom.window.close();
 }
}
// Alberta needs no provincial-tax entry, including stale saved PST and zero-GST businesses.
for(const page of ['roofer','snow','pressure','paving','landscaping','commercial']){
 const dom=new JSDOM(fs.readFileSync(path.join(root,'site/'+page+'-setup.html'),'utf8'),{url:'https://test.invalid/site/'+page+'-setup',runScripts:'outside-only'}),w=dom.window,d=w.document;
 w.scrollTo=()=>{};w.fetch=async()=>({ok:true,json:async()=>({profile:{company:'QA Alberta',name:'QA Owner',email:'qa@example.invalid',country:'CA',province:'AB',gst:'5',pst:'6'}})});
 w.eval(source);await tick();const f=id=>d.getElementById(id);
 assert.equal(f('region').value,'AB');assert.equal(f('tax1').value,'5');assert(f('tax1').closest('label').textContent.includes('GST %'));
 assert.equal(f('tax2').value,'0');assert(f('tax2').disabled);assert(!f('tax2').required);assert(f('tax2').closest('label').hidden);
 f('nextBtn').click();f('nextBtn').click();assert(d.querySelector('[data-step="7"]').classList.contains('active'),page+' Alberta advances without PST');
 for(const gst of ['5','0']){f('tax1').value=gst;assert(w.validateStep(2));const saved=await w.saveIndustrySetupLocal(page);assert.equal(saved.gst,gst);assert.equal(saved.pst,'0');}
 f('tax1').value='';assert(!w.validateStep(2),'GST still requires an explicit value including 0');f('tax1').value='5';
 f('region').value='SK';f('region').dispatchEvent(new w.Event('change'));assert(!f('tax2').disabled);assert(f('tax2').required);assert(!f('tax2').closest('label').hidden);assert.equal(f('tax2').value,'');assert.equal(f('tax1').value,'5');assert(!w.validateStep(2));
 f('tax2').value='6';f('region').value='AB';f('region').dispatchEvent(new w.Event('change'));assert.equal(f('tax2').value,'0');assert(w.validateStep(2));
 dom.window.close();
}
// Slow prefill cannot undo choices already made by the user.
{
 const dom=new JSDOM(fs.readFileSync(path.join(root,'site/roofer-setup.html'),'utf8'),{url:'https://test.invalid/site/roofer-setup',runScripts:'outside-only'}),w=dom.window,d=w.document;let respond;
 w.scrollTo=()=>{};w.fetch=()=>new Promise(r=>respond=r);w.eval(source);
 for(const [id,value] of [['companyName','Typed Company'],['country','United States'],['tax1','3']]){d.getElementById(id).value=value;d.getElementById(id).dispatchEvent(new w.Event('input',{bubbles:true}));}
 respond({ok:true,json:async()=>({profile:{company:'Old Company',country:'CA',province:'SK',gst:'5'}})});await tick();
 assert.equal(d.getElementById('companyName').value,'Typed Company');assert.equal(d.getElementById('country').value,'United States');assert.equal(d.getElementById('tax1').value,'3');dom.window.close();
}
if(process.env.ONBOARDING_FIXTURES_PATH)fs.writeFileSync(process.env.ONBOARDING_FIXTURES_PATH,JSON.stringify(savedFixtures));
console.log('PASS: 12 four-step setup flows, signup prefill, CA/US region codes, explicit taxes and pricing, saved services/messages, validation, failed-save retry and duplicate-click prevention; late account response preserves edits');
})().catch(error=>{console.error(error);process.exit(1)});
