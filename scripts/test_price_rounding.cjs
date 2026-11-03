// Check displayed money independently of polygon geometry and map rendering.
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync(process.env.QA_PRICING_SOURCE||'app.py','utf8');
const priceCalc=source.split('\n').find(line=>line.startsWith('function priceCalc(){'));
const fields={pricingMode:{value:'added'},discountPct:{value:0},gst:{value:5},pst:{value:6}};
let area=1790.2248;
const c={el:id=>fields[id],commercialActive:()=>false,measurementViewMode:'auto',estimateArea:()=>area,currentJobPrice:()=>1,savedSurfaceHasAreas:()=>false,currentBusinessType:()=> 'roofing',landscapingCombined:()=>false,pressureCombined:()=>false,pavingCombined:()=>false,multiAreaSaved:()=>false,commercialHasAreas:()=>false};
vm.createContext(c);vm.runInContext(source.slice(source.indexOf('function estimatePeriodValue('),source.indexOf('function updateEstimatePeriodUi(')),c);const decimalHelper=source.split('\n').find(x=>x.startsWith('function decimalCurrency('));if(decimalHelper)vm.runInContext(decimalHelper,c);vm.runInContext(priceCalc,c);
const cents=n=>Math.round(n*100);
function check(expected){const r=c.priceCalc();assert.equal(cents(r.total),expected);assert.equal(cents(r.taxBase)+cents(r.gstAmt)+cents(r.pstAmt),expected);return r;}
check(198714);area=1746.30;check(193840);
fields.pricingMode.value='included';area=10;check(1000);
fields.pricingMode.value='discount';fields.discountPct.value=10;area=1790.2248;const r=check(178843);assert.equal(cents(r.discount),17902);
fields.gst.value=0;fields.pst.value=0;check(161120);
console.log('PASS: fractional roof area, half-cent tax, included taxes, discount and zero-tax totals equal displayed money lines');

// Regression for the actual rejected phone payload: decimal 367.30 * 5% = 18.365 -> 18.37.
fields.pricingMode.value='added';fields.discountPct.value=0;fields.gst.value=5;fields.pst.value=6;
for(const [base,gst,pst,total] of [[367.29,18.36,22.04,407.69],[367.30,18.37,22.04,407.71],[367.31,18.37,22.04,407.72]]){area=base;const p=check(cents(total));assert.equal(p.gstAmt,gst,'GST half-cent rule for '+base);assert.equal(p.pstAmt,pst);}
for(const [operation,values,expected] of [
 ['product',[.1,.35],.04],['product',[1,1.005],1.01],
 ['product',[1,.034999999999],.03],['product',[1,.035],.04],['product',[1,.035000000001],.04],
 ['sum',[.03,.005],.04],['sum',[.03,.00499999999],.03],
 ['percent',[367.3,5],18.37],['percent',[367.299999,5],18.36],['percent',[367.300001,5],18.37],
 ['product',[1e-7,350000],.04],['product',[0,1.005],0]
])assert.equal(c.decimalCurrency(operation,values),expected,operation+' '+values);
assert.equal(c.decimalCurrency('quantityProduct',[.1,.7],.04375),.04,'Sum exact roof quantities before rounding the priced roof line');
console.log('PASS exact rejected amount + adjacent tax/line/extra boundaries, scientific notation, zero and roof quantity sum; decimal ROUND_HALF_UP');
