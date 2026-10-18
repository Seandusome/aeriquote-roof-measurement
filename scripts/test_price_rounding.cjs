// Check displayed money independently of polygon geometry and map rendering.
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync('app.py','utf8');
const priceCalc=source.split('\n').find(line=>line.startsWith('function priceCalc(){'));
const fields={pricingMode:{value:'added'},discountPct:{value:0},gst:{value:5},pst:{value:6}};
let area=1790.2248;
const c={el:id=>fields[id],commercialActive:()=>false,measurementViewMode:'auto',estimateArea:()=>area,currentJobPrice:()=>1,savedSurfaceHasAreas:()=>false,currentBusinessType:()=> 'roofing',landscapingCombined:()=>false,pressureCombined:()=>false,pavingCombined:()=>false,multiAreaSaved:()=>false,commercialHasAreas:()=>false};
vm.createContext(c);vm.runInContext(priceCalc,c);
const cents=n=>Math.round(n*100);
function check(expected){const r=c.priceCalc();assert.equal(cents(r.total),expected);assert.equal(cents(r.taxBase)+cents(r.gstAmt)+cents(r.pstAmt),expected);return r;}
check(198714);area=1746.30;check(193840);
fields.pricingMode.value='included';area=10;check(1000);
fields.pricingMode.value='discount';fields.discountPct.value=10;area=1790.2248;const r=check(178843);assert.equal(cents(r.discount),17902);
fields.gst.value=0;fields.pst.value=0;check(161120);
console.log('PASS: fractional roof area, half-cent tax, included taxes, discount and zero-tax totals equal displayed money lines');
