const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {JSDOM}=require('jsdom');
const source=fs.readFileSync('app.py','utf8');
const context=vm.createContext({});
vm.runInContext(source.slice(source.indexOf('function fitExpandedStreetBlock('),source.indexOf('async function buildExpandedEstimatePDF(')),context);
function scenario(remaining,photo=true){
 const doc=new JSDOM('<div id="col"><div id="block"><img style="height:170px" data-expanded-street-image><p>Street View imagery: 2015-07</p></div></div>').window.document;
 const col=doc.querySelector('#col'),block=doc.querySelector('#block'),image=block.querySelector('img');
 if(!photo)delete image.dataset.expandedStreetImage;
 Object.defineProperty(col,'scrollHeight',{get:()=>500-remaining+parseFloat(image.style.height)+20});
 context.fitExpandedStreetBlock(block,col,500);
 return {col,block,image};
}
const fitting=scenario(200);assert.equal(fitting.image.style.height,'170px');
const orphan=scenario(180);assert(orphan.col.scrollHeight<=500,'photo and caption must both fit');assert.equal(orphan.block.children.length,2);assert(parseFloat(orphan.image.style.height)>=100);
const continuation=scenario(80);assert.equal(continuation.image.style.height,'170px','keep the whole readable photo with its caption for continuation');assert(continuation.col.scrollHeight>500);
const ordinary=scenario(180,false);assert.equal(ordinary.image.style.height,'170px','unrelated content must not shrink');
assert(source.includes('block.appendChild(image);block.appendChild(clone(el(\'rStreetMeta\')))'),'caption must travel in the same pagination block');
console.log('PASS: Expanded PDF keeps photo and date together, fits small overflows, preserves readable continuation and unrelated blocks');
