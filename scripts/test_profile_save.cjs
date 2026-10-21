// Actual profile-save handler: failed writes must not claim success or replace cached defaults.
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const app=fs.readFileSync('app.py','utf8');
const code=app.slice(app.indexOf('let dealerProfileSaveInProgress=false;'),app.indexOf('\nfunction applyOnboardingMarketing'));
const fields=new Map(),storage=new Map([['sxDealerDefaults','old authoritative cache']]);
function el(id){if(!fields.has(id))fields.set(id,{value:'',checked:false,textContent:'',innerHTML:'',disabled:false});return fields.get(id)}
el('price').value='0.80';el('jobPrice').value='1.25';el('dealerCompany').value='QA TEST Company';el('showWarrantyShield').checked=false;el('saveDealerProfileBtn').textContent='SAVE DEALER PROFILE & BRANDING';
let requests=0,posted,release,cacheBlocked=false,reply=()=>Promise.resolve({ok:false,json:async()=>({error:'Login required'})});
const ctx=vm.createContext({el,fetch:async(url,options)=>{requests++;posted=JSON.parse(options.body);return reply()},localStorage:{setItem(k,v){if(cacheBlocked)throw Error('quota');storage.set(k,v)}},dealerLogoSrc:()=>'/static/dealer-assets/shinglextra-logo.jpg',document:{querySelector:()=>({open:false})},applyBusinessTerminology(){},renderSummary(){},money:n=>'$'+Number(n).toFixed(2)});
vm.runInContext(code,ctx);
async function save(){return await vm.runInContext('saveDealerDefaults()',ctx)}
(async()=>{
 assert.equal(await save(),false);assert.match(el('savedMsg').textContent,/Profile not saved/);assert.equal(storage.get('sxDealerDefaults'),'old authoritative cache');assert.equal(el('jobPrice').value,'1.25');assert.equal(el('dealerCompany').value,'QA TEST Company');assert(!el('saveDealerProfileBtn').disabled);
 reply=()=>Promise.reject(Error('network down'));assert.equal(await save(),false);assert.equal(storage.get('sxDealerDefaults'),'old authoritative cache');
 reply=()=>Promise.resolve({ok:true,json:async()=>({})});assert.equal(await save(),false,'HTML/invalid success cannot claim a confirmed save');
 reply=()=>new Promise(resolve=>{release=resolve});const before=requests,pending=save();assert(el('saveDealerProfileBtn').disabled);assert.equal(await save(),false);assert.equal(requests,before+1,'Concurrent click must not create a second write');assert.equal(el('jobPrice').value,'1.25','Pending save cannot update job rate');
 release({ok:true,json:async()=>({ok:true})});assert.equal(await pending,true);assert.equal(JSON.parse(storage.get('sxDealerDefaults')).company,'QA TEST Company');assert.equal(posted.showWarrantyShield,false);assert.equal(posted.logoData,'/static/dealer-assets/shinglextra-logo.jpg');assert.equal(el('jobPrice').value,'0.80');assert.match(el('savedMsg').innerHTML,/profile & branding saved/);assert(!el('saveDealerProfileBtn').disabled);
 cacheBlocked=true;reply=()=>Promise.resolve({ok:true,json:async()=>({ok:true})});assert.equal(await save(),true,'Unavailable browser storage cannot turn a confirmed server save into failure');assert(!el('saveDealerProfileBtn').disabled);
 console.log('PASS: profile HTTP/network/unconfirmed failures preserve entries/cache/job price; retry and server-confirmed success; duplicate-click guard; shield/logo payload; browser-storage failure');
})().catch(e=>{console.error(e);process.exit(1)});
