/* Exercise the actual shared handler at both legacy and clean industry setup URLs. */
const fs=require('fs'),path=require('path'),assert=require('assert'),{JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..');
const source=fs.readFileSync(path.join(root,'site/onboarding.js'),'utf8').replace('window.location.assign(', 'window.__navigate(');
(async()=>{
for(const [page,industry] of [['roofer','roofing'],['snow','snow'],['pressure','pressure'],['paving','paving'],['landscaping','landscaping'],['commercial','commercial']]){
 for(const suffix of ['', '.html']){
  const dom=new JSDOM(fs.readFileSync(path.join(root,'site/'+page+'-setup.html'),'utf8'),{url:'https://test.invalid/site/'+page+'-setup'+suffix,runScripts:'outside-only'});
  const w=dom.window;let destination=null;const calls=[],alerts=[];
  w.scrollTo=()=>{};w.__navigate=url=>destination=url;w.alert=message=>alerts.push(message);
  w.fetch=async(url,options)=>{calls.push({url,options});return {ok:true,json:async()=>({})};};
  w.document.getElementById('companyName').value='Test Company';
  for(const [id,value] of [['warrantyStatement','Customer service terms'],['estimateMessage','Customer estimate message'],['ctaHeading','Arrange this service']]){
   assert(w.document.getElementById(id),page+' missing '+id);w.document.getElementById(id).value=value;
  }
  const format=w.document.querySelector('[data-step="5"]');assert.equal(format.querySelectorAll('select,input').length,0,page+' unsupported setup controls');
  assert(format.textContent.includes('square feet'));assert(format.textContent.includes('linear feet'));
  assert(!w.document.body.textContent.includes('enter the final job price'),page+' unsupported final-price promise');

  w.eval(source);const finish=w.document.getElementById('finishSetup');assert(finish,page+' finish');finish.click();
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(destination,'/?industry='+industry,page+suffix+' navigate');assert.equal(alerts.length,0,page+suffix+' alert');
  assert(calls.some(c=>c.url==='/api/account/profile'&&c.options.method==='POST'),page+' server save');
  assert.equal(w.localStorage.getItem('aeriQuoteIndustry'),industry,page+' stored industry');
  assert.equal(JSON.parse(calls.find(c=>c.url==='/api/account/profile').options.body).businessType,industry,page+' profile industry');
  const saved=JSON.parse(calls.find(c=>c.url==='/api/account/profile').options.body);
  assert.equal(saved.warrantyStatement,'Customer service terms',page+' service terms saved');
  assert.equal(saved.estimateMessage,'Customer estimate message',page+' customer message saved');
  assert.equal(saved.ctaHeading,'Arrange this service',page+' call to action saved');
  dom.window.close();
 }
}
console.log('PASS: all six industry finish buttons save profile and open the right measuring industry on clean and .html URLs (12 flows)');
})().catch(error=>{console.error(error);process.exit(1)});
