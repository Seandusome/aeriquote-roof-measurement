const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const s=fs.readFileSync('app.py','utf8');const helper=s.slice(s.indexOf('function quotePricingError('),s.indexOf('function updateQuotePricingValidation('));
let industry='roofing',areas=false,line=false,linearRate=.25;const fields={gst:{value:'5'},pst:{value:'6'},jobPrice:{value:'1'},discountPct:{value:'0'},pricingMode:{value:'regular'},extraServiceAmount:{value:'0'},commercialLinearRate:{value:'.25'}};
const ctx=vm.createContext({el:id=>fields[id],commercialAreas:[],measurementViewMode:'auto',linearMeasurementSaved:false,currentBusinessType:()=>industry,savedSurfaceHasAreas:()=>areas&&industry!=='commercial',commercialHasAreas:()=>areas,commercialHasLinear:()=>line,surfaceLinearJobRate:()=>linearRate,landscapingCombined:()=>false,pressureCombined:()=>false,pavingCombined:()=>false,priceCalc:()=>({subtotal:100,extraAmount:0,taxBase:100,gstAmt:5,pstAmt:6,total:111})});vm.runInContext(helper,ctx);
const error=()=>ctx.quotePricingError();
for(industry of ['roofing','snow','pressure','paving','landscaping','commercial']){
 assert.equal(error(),'');
 for(const value of ['', '-1','Infinity','abc']){fields.jobPrice.value=value;assert(error(),industry+' rejects job rate '+value)}fields.jobPrice.value='0';assert.equal(error(),'','Explicit free service allowed');fields.jobPrice.value='1';
 for(const id of ['gst','pst']){for(const value of ['', '-1','101','Infinity']){fields[id].value=value;assert(error())}fields[id].value=id==='gst'?'5':'6'}
 fields.pricingMode.value='discount';for(const value of ['', '-1','100.1']){fields.discountPct.value=value;assert(error())}fields.discountPct.value='100';assert.equal(error(),'');fields.pricingMode.value='regular';fields.discountPct.value='0';
 fields.extraServiceAmount.value='-2';assert(error());fields.extraServiceAmount.value='';assert.equal(error(),'');fields.extraServiceAmount.value='0';
 if(industry!=='roofing'){areas=true;ctx.commercialAreas=[{sqft:100,rate:.1},{sqft:200,rate:.2}];assert.equal(error(),'');for(const value of [null,-1,NaN,Infinity]){ctx.commercialAreas[1].rate=value;assert(error())}ctx.commercialAreas[1].rate=0;assert.equal(error(),'');areas=false;ctx.commercialAreas=[];}
 console.log('PASS '+industry+': blank/negative/non-finite rates, taxes, discount limits, extras and intentional zero');
}
industry='commercial';line=true;fields.commercialLinearRate.value='';assert(error());fields.commercialLinearRate.value='0';assert.equal(error(),'');line=false;
assert(ctx.quotePricingError({subtotal:100,extraAmount:0,taxBase:100,gstAmt:0,pstAmt:0,total:Infinity}));
// Synchronising a saved area must never turn a cleared rate into an intentional zero.
Object.assign(ctx,{commercialActive:()=>true,areaMeasurementSaved:true,areaPoints:[{lat:52,lng:-106},{lat:52,lng:-105.999},{lat:52.001,lng:-106}],commercialEditingIndex:0,areaSqFtTotal:()=>100,currentJobPrice:()=>1});
ctx.commercialAreas=[{name:'QA',rate:null,sqft:100}];
vm.runInContext(s.split('\n').find(line=>line.startsWith('function commercialSyncCurrent(){')),ctx);ctx.commercialSyncCurrent();assert.equal(ctx.commercialAreas[0].rate,null);
ctx.commercialAreas=[];
// Run the real entry points with invalid input: neither may reach report construction or a write.
fields.jobPrice.value='';let writes=0,messages=[];Object.assign(ctx,{status:m=>messages.push(m),fetch:()=>{writes++;throw Error('Unexpected write')}});
const save=s.slice(s.indexOf('async function saveEstimateHistory(){'),s.indexOf('\nasync function searchEstimateHistory'));
const showStart=s.indexOf('async function showCustomerEstimate('),showEnd=s.indexOf('\nfunction ',showStart);vm.runInContext(save,ctx);vm.runInContext(s.slice(showStart,showEnd),ctx);
(async()=>{assert.equal(await ctx.saveEstimateHistory(),false);await ctx.showCustomerEstimate();assert.equal(writes,0);assert.equal(messages.length,2);console.log('PASS: invalid prices blocked at actual save/report entry points before writes')})().catch(e=>{console.error(e);process.exit(1)});
