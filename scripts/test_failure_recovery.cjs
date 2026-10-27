// Deterministic network failures, not physical-device/browser network testing.
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync('app.py','utf8');
const save=source.slice(source.indexOf('async function saveEstimateHistory(){'),source.indexOf('function openEstimateHistory(){'));
const fields={streetViewChoice:{value:'none'},address:{value:'QA TEST saved property'},customerName:{value:'QA TEST DO NOT SEND'}};
const messages=[],posts=[];
const c={AbortController,setTimeout,clearTimeout,el:id=>fields[id],quotePricingError:()=>'',priceCalc:()=>({area:100,total:100}),captureQuoteSnapshot:()=>({}),quoteSnapshot:{measurementMode:'area'},savedPropertyEditActive:true,savedStreetImageData:'',savedJobDetails:{},sessionToken:'qa',lastHistorySaveKey:'',status:(...x)=>messages.push(x),console:{warn(){}}};
vm.createContext(c);vm.runInContext(save,c);
(async()=>{
 let release;
 c.fetch=async(url,o)=>{posts.push(o);await new Promise(r=>release=r);return{ok:true,json:async()=>({version:'saved-version'})}};
 const first=c.saveEstimateHistory(),second=c.saveEstimateHistory();release();assert.deepEqual(await Promise.all([first,second]),[true,true]);assert.equal(posts.length,1,'Rapid double click sends one POST');
 fields.customerName.value='QA TEST uncertain response';
 c.fetch=async(url,o)=>{posts.push(o);throw Error('Response lost after commit')};
 assert.equal(await c.saveEstimateHistory(),false);const uncertain=posts.at(-1);
 c.fetch=async(url,o)=>{posts.push(o);return{ok:true,json:async()=>({version:'new-version'})}};
 assert.equal(await c.saveEstimateHistory(),true);assert.equal(posts.at(-1).headers['Idempotency-Key'],uncertain.headers['Idempotency-Key']);assert.equal(posts.at(-1).body,uncertain.body);assert.equal(posts.at(-1).headers['If-Match'],'saved-version');
 fields.customerName.value='QA TEST expired';const before=c.lastHistorySaveKey;
 c.fetch=async()=>({ok:false,status:401,json:async()=>({error:'Login required'})});
 assert.equal(await c.saveEstimateHistory(),false);assert.equal(c.lastHistorySaveKey,before);assert(messages.at(-1)[0].includes('login expired'));assert.equal(fields.address.value,'QA TEST saved property');
 c.fetch=async()=>({ok:false,status:409,json:async()=>({error:'Changed in another session; reopen latest'})});
 assert.equal(await c.saveEstimateHistory(),false);assert(messages.at(-1)[0].includes('another session'));
 // Abort an unresponsive save and retain the exact operation for retry.
 c.setTimeout=(fn,ms)=>setTimeout(fn,ms===30000?5:ms);
 c.fetch=async(url,o)=>new Promise((resolve,reject)=>o.signal.addEventListener('abort',()=>reject(Error('timeout'))));
 assert.equal(await c.saveEstimateHistory(),false);assert(c.saveEstimateHistory.pending.payload);
 // Failed new-property lookup must not reset the old workspace/address.
 const load=source.slice(source.indexOf('async function loadProperty(){'),source.indexOf('function startGarageMode(){'));
 const notices=[];let resets=0,requests=0,finish;
 const old={sessionToken:'old-session',points:[[52,-106],[52,-105.99],[52.01,-105.99]]};
 const dom={streetAddress:{value:'invalid new address'},cityTown:{value:'Saskatoon'},address:{value:'old saved address'}};
 const l={el:id=>dom[id],clearTimeout,addressPreviewTimer:null,addressPreviewSeq:0,unitAddressSuggestion:()=>null,coordinatesEntered:()=>null,currentBusinessType:()=> 'roofing',workspaceSaveFingerprint:()=> 'unchanged',propertyInputAddressKey:()=> 'qa-input',propertyLookupProvince:()=> 'SK',enteredStreetNumber:()=> '1',propertyCountryFromProvince:()=> 'Canada',pendingMeasurementMode:'area',measurementViewMode:'area',status:(...x)=>notices.push(x),showLoad(){},resetReportForNewProperty(){resets++},resetMeasurementForNewProperty(){resets++},...old,fetch:async()=>{requests++;await new Promise(r=>finish=r);return{ok:false,status:401,json:async()=>({error:'Login required'})}}};
 vm.createContext(l);vm.runInContext(load,l);
 const a=l.loadProperty(),b=l.loadProperty();finish();await Promise.all([a,b]);assert.equal(requests,1);assert.equal(resets,0);assert.equal(l.sessionToken,old.sessionToken);assert.equal(dom.address.value,'old saved address');assert(notices.some(n=>n[0].includes('login expired')));
 // Browser refresh guard: unsaved geometry/price changes warn; saved work can reload.
 const listeners={},f={...c,window:{addEventListener:(name,fn)=>listeners[name]=fn},areaPoints:[[52,-106]],linearPoints:[],structures:[],manualPlanes:[]};
 vm.createContext(f);vm.runInContext(save,f);
 vm.runInContext(source.slice(source.indexOf('function workspaceSaveFingerprint(){'),source.indexOf('async function saveEstimateHistory(){')),f);
 let prevented=false;listeners.beforeunload({preventDefault(){prevented=true}});assert(prevented);
 f.saveEstimateHistory.cleanWorkspace=f.workspaceSaveFingerprint();prevented=false;listeners.beforeunload({preventDefault(){prevented=true}});assert.equal(prevented,false);
 fields.customerName.value='QA TEST unsaved after successful save';listeners.beforeunload({preventDefault(){prevented=true}});assert(prevented);
 f.sessionToken=null;prevented=false;listeners.beforeunload({preventDefault(){prevented=true}});assert.equal(prevented,false,'No loaded property needs no warning');
 f.sessionToken='qa';f.areaPoints=[];prevented=false;listeners.beforeunload({preventDefault(){prevented=true}});assert.equal(prevented,false,'An empty workspace needs no warning');
 // Real address input handlers retain old geometry/customer/address and block mismatched quotes.
 const addressSource=source.slice(source.indexOf('function propertyInputAddressKey(){'),source.indexOf('function propertyProvinceChanged(){'));
 const addressFields={streetAddress:{value:'Old street'},cityTown:{value:'Saskatoon'},propertyProvince:{value:'SK'},address:{value:'Old stored property'},customerName:{value:'QA TEST existing customer'}};
 const addressContext={el:id=>addressFields[id],coordinatesEntered:()=>null,sessionToken:'saved-token',structures:[],manualPlanes:[],fallbackMode:false,loadProperty(){},clearAddressVerificationState(){},clearTimeout(){},setTimeout(){},previewAddress(){},renderSummary(){},areaPoints:[[52,-106]],addressPreviewTimer:null};
 vm.createContext(addressContext);vm.runInContext(addressSource,addressContext);
 addressContext.loadProperty.loadedAddressKey=addressContext.propertyInputAddressKey();
 addressFields.streetAddress.value='Invalid new street';addressContext.addressTyped();assert(addressContext.propertyAddressNeedsReload());
 assert.equal(addressContext.sessionToken,'saved-token');assert.equal(addressContext.areaPoints.length,1);assert.equal(addressFields.address.value,'Old stored property');assert.equal(addressFields.customerName.value,'QA TEST existing customer');
 addressFields.streetAddress.value='Old street';addressFields.cityTown.value='Saskatoon';addressFields.propertyProvince.value='SK';assert.equal(addressContext.propertyAddressNeedsReload(),false);
 addressFields.streetAddress.value='Invalid new street';vm.runInContext(source.slice(source.indexOf('function quotePricingError(calc=null){'),source.indexOf('function updateQuotePricingValidation(calc){')),addressContext);assert(addressContext.quotePricingError().includes('address has changed'),'Actual validation must block mismatched quotes');
 console.log('PASS: single-flight create/lookup, stable retry identity, lost response, timeout, expired login, conflict message and existing workspace preservation');
})().catch(e=>{console.error(e);process.exit(1)});
