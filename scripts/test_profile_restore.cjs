// Account settings must hydrate even when browser storage is unavailable/full.
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync('app.py','utf8');
const code=source.slice(source.indexOf('function loadDealerDefaults(){'),source.indexOf('\n\nfunction toggleMarketingEditor'));
async function run(blocked,activeJob=false){
 const fields=new Map();const el=id=>{if(!fields.has(id))fields.set(id,{value:'',dataset:{accountId:'qa'},style:{},setAttribute(){},removeAttribute(){}});return fields.get(id)};
 el('businessType').value='roofing';el('dealerCompany').value=activeJob?'Current job company':'Unsaved default';el('jobPrice').value=activeJob?'1.25':'0.10';
 const profile={company:'QA TEST Restored',name:'QA TEST Owner',email:'qa@example.invalid',country:'CA',province:'SK',businessType:'roofing',price:'0.83',gst:'5',pst:'6',showWarrantyShield:false};
 const noop=()=>{};const ctx=vm.createContext({el,fetch:async()=>({ok:true,json:async()=>({profile,industry:'roofing'})}),prepareAccountBrandingCache:noop,localStorage:{getItem(){if(blocked)throw Error('storage unavailable');return null},setItem(){if(blocked)throw Error('quota')},removeItem:noop},sessionToken:activeJob?'existing-job':'',linearMode:false,areaMode:false,industryChosenByUser:false,measurementViewMode:'auto',pendingMeasurementMode:'auto',window:{location:{search:''}},URLSearchParams,currentBusinessType:()=>el('businessType').value,applyWarrantyAccount:noop,applyBusinessTerminology:noop,countryChanged:noop,applyOnboardingMarketing:noop,applySnowMarketingDefaultsIfNeeded:noop,fillLandscapingBenefits:noop,fillCommercialBenefits:noop,toggleMarketingEditor:noop,pricingChanged:noop,renderSummary:noop,updatePropertyActionButton:noop,clearNewJobCustomer:noop,setTimeout:noop,dealerLogoSrc:()=>''});
 vm.runInContext(code,ctx);vm.runInContext('loadDealerDefaults()',ctx);await new Promise(resolve=>setImmediate(resolve));
 assert.equal(el('dealerCompany').value,activeJob?'Current job company':profile.company);
 assert.equal(el('jobPrice').value,activeJob?'1.25':profile.price);
 if(!activeJob){assert.equal(el('province').value,'SK');assert.equal(el('gst').value,'5');assert.equal(el('pst').value,'6')}
}
(async()=>{await run(false);await run(true);await run(true,true);console.log('PASS: server company/rate/taxes hydrate with blocked browser storage; active job settings/rate remain unchanged')})().catch(e=>{console.error(e);process.exit(1)});
