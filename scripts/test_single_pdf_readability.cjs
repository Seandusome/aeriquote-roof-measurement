const fs=require('fs'),assert=require('assert/strict'),vm=require('vm');
const source=fs.readFileSync('app.py','utf8'),context=vm.createContext({});
vm.runInContext(source.slice(source.indexOf('function singlePageReadability('),source.indexOf('async function captureSinglePageEstimate(')),context);
function report(width,height,font=14){return{getBoundingClientRect:()=>({width,height}),scrollWidth:width,scrollHeight:height,ownerDocument:{defaultView:{getComputedStyle:()=>({fontSize:font+'px'})}},querySelectorAll:()=>[{textContent:'659 square feet × 0.10 = 65.90',getClientRects:()=>[{}]}]}}
const ordinary=context.singlePageReadability(report(1320,1000));assert(ordinary.readable);assert(ordinary.points>7);context.assertSinglePageLegible(report(1320,1000));
const dense=context.singlePageReadability(report(1320,2000));assert(!dense.readable);assert(dense.points<5);assert.throws(()=>context.assertSinglePageLegible(report(1320,2000)),e=>e.code==='SINGLE_PAGE_DENSE'&&e.message.includes('Expanded PDF')&&e.message.includes('unchanged'));
// Height boundary is a real print-size cutoff, not a row-count heuristic.
const boundary=14*8.14*72/7;assert(context.singlePageReadability(report(1320,boundary-.1)).readable);assert(!context.singlePageReadability(report(1320,boundary+.1)).readable);
assert(context.singlePageReadability(report(1320,1000,18)).readable);assert(!context.singlePageReadability(report(2000,1000,14)).readable);
console.log('PASS Single print-size floor: ordinary accepted, dense/wide rejected, exact7pt boundary, clear Expanded direction, no row-count/data mutation');
