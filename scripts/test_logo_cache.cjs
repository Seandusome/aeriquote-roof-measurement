const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');const s=fs.readFileSync('app.py','utf8');
const helpers=s.slice(s.indexOf('let dealerLogoData='),s.indexOf('\n\nconst AERI_TERMS='));
const prepare=s.slice(s.indexOf('function prepareAccountBrandingCache('),s.indexOf('function loadDealerDefaults(){'));
for(const blocked of [false,true]){
 const storage=new Map([['sxDealerLogo','stale-other-business'],['sxDealerDefaults','stale'],['aqBrandingAccount','other']]);
 const preview={style:{},removeAttribute(name){delete this[name]}};
 const c={el:()=>preview,status(){},localStorage:{getItem(k){if(blocked)throw Error('blocked');return storage.get(k)||null},setItem(k,v){if(blocked)throw Error('blocked');storage.set(k,v)},removeItem(k){if(blocked)throw Error('blocked');storage.delete(k)}}};vm.createContext(c);vm.runInContext(helpers+prepare,c);
 c.prepareAccountBrandingCache('qa-owner');assert.equal(c.dealerLogoSrc(),'');
 c.applyDealerLogo('data:image/png;base64,SERVER',false);assert.equal(c.dealerLogoSrc(),'data:image/png;base64,SERVER');assert.equal(preview.src,c.dealerLogoSrc());
 c.applyDealerLogo('',false);assert.equal(c.dealerLogoSrc(),'','Server removal overrides stale cache');assert.equal(preview.style.display,'none');
 c.applyDealerLogo('data:image/png;base64,NEW');assert.equal(vm.runInContext('dealerLogoDirty',c),true);
 c.prepareAccountBrandingCache('qa-other');assert.equal(c.dealerLogoSrc(),'','Account switch clears in-memory logo even if storage blocked');
}
console.log('PASS actual logo helpers: blocked storage, server restoration/removal, visible preview, pending upload and account-isolated memory cache');
