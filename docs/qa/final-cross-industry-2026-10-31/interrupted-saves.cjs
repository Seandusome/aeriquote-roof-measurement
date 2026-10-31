// Exercise the real save function with controlled network outcomes.
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const s=fs.readFileSync('app.py','utf8'),fn=s.slice(s.indexOf('async function saveEstimateHistory(){'),s.indexOf('function openEstimateHistory(){'));
const fields={streetViewChoice:{value:'none'},address:{value:'QA property'},customerName:{value:'QA DO NOT SEND'},extraServiceDescription:{value:'Original service'},extraServiceAmount:{value:10}};
const saved=[],messages=[];let fail=false;
const c={AbortController,setTimeout,clearTimeout,quotePricingError:()=>'',el:id=>fields[id],priceCalc:()=>({area:100,total:110,mode:'added'}),captureQuoteSnapshot:()=>({}),quoteSnapshot:{businessType:'landscaping',measurementMode:'area',areaPoints:[[1,1],[1,2],[2,2]],commercialAreas:[{name:'Front',sqft:100,rate:1}]},savedPropertyEditActive:true,savedStreetImageData:'',savedJobDetails:{job_status:'Booked',scheduled_date:'2026-10-20',amount_paid:50},sessionToken:'saved',lastHistorySaveKey:'',status:(...x)=>messages.push(x),console:{warn(){}},fetch:async(url,o)=>{if(fail)throw Error('offline');saved.push(JSON.parse(o.body));return{ok:true}}};vm.createContext(c);vm.runInContext(fn,c);

(async()=>{
 let operations=0;
 for(const industry of ['roofing','snow','pressure','paving','landscaping','commercial'])for(const failure of ['offline','timeout','409','400']){
  const original=JSON.parse(JSON.stringify(c.quoteSnapshot));original.businessType=industry;original.commercialAreas[0].name='Original '+industry;const previous=JSON.stringify(original);
  c.quoteSnapshot=JSON.parse(previous);c.lastHistorySaveKey='verified-'+industry;c.saveEstimateHistory.pending=null;c.saveEstimateHistory.baseVersion='original-revision';c.savedPropertyEditActive=true;fields.customerName.value='Fictional '+industry;fields.extraServiceDescription.value=failure;
  let posted=null;c.fetch=async(url,o)=>{posted=JSON.parse(o.body);if(failure==='offline')throw Error('offline');if(failure==='timeout')throw new DOMException('timeout','AbortError');return{ok:false,status:Number(failure),json:async()=>({error:'Controlled rejection'})}};
  assert.equal(await c.saveEstimateHistory(),false);assert.equal(c.lastHistorySaveKey,'verified-'+industry);assert.equal(c.saveEstimateHistory.baseVersion,'original-revision');assert.equal(JSON.stringify(original),previous);assert.equal(JSON.stringify(c.quoteSnapshot),previous);
  const id=c.saveEstimateHistory.pending.id;c.fetch=async(url,o)=>{assert.equal(o.headers['Idempotency-Key'],id);return{ok:true,json:async()=>({version:'new-revision'})}};
  assert.equal(await c.saveEstimateHistory(),true);assert.equal(c.saveEstimateHistory.baseVersion,'new-revision');assert.equal(JSON.stringify(original),previous);operations++;
 }
 console.log(JSON.stringify({passed:true,industry_failure_retry_cases:operations,failures:['offline','timeout','409','400'],original_revisions_unchanged:true,same_idempotency_key_on_retry:true,environment:'VM controlled responses only',physical_device:false}));
})().catch(e=>{console.error(e);process.exit(1)});
