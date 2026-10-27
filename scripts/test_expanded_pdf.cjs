const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {JSDOM}=require('jsdom');
const source=fs.readFileSync('app.py','utf8');
const context=vm.createContext({});
vm.runInContext(source.slice(source.indexOf('function fitExpandedStreetBlock('),source.indexOf('async function buildExpandedEstimatePDF(')),context);
// A portrait phone aerial and landscape tablet/desktop aerial must retain their pixel ratio.
for(const [w,h,maxW,maxH] of [[670,930,1152,650],[1280,840,1152,650],[2000,500,1152,650],[640,640,1152,650]]){
 const size=context.expandedAerialSize(w,h,maxW,maxH);
 assert(Math.abs(size.width/size.height-w/h)<1e-10);
 assert(size.width<=maxW&&size.height<=maxH);
 assert(Math.abs(size.width-maxW)<1e-8||Math.abs(size.height-maxH)<1e-8,'Use the largest proportional fit');
}
assert.throws(()=>context.expandedAerialSize(0,5,10,10),/dimensions/);
// Leader lines must not cross existing area/edge label rectangles; labels themselves stay intact.
const boxes=[{x:40,y:40,w:20,h:20}];
const parts=context.expandedLeaderSegments({x:0,y:50},{x:100,y:50},boxes);
assert.equal(parts.length,2);assert(parts[0][1].x<40&&parts[1][0].x>60);
assert.equal(context.expandedLeaderSegments({x:45,y:45},{x:55,y:55},boxes).length,0);
assert.equal(context.expandedLeaderSegments({x:0,y:0},{x:100,y:0},boxes).length,1);
assert.equal(context.expandedLeaderSegments({x:0,y:0},{x:0,y:0},boxes).length,0);

function scenario(remaining,photo=true){
 const doc=new JSDOM('<div id="col"><div id="block"><img style="width:302.2222222222px;height:170px" data-expanded-street-image><p>Street View imagery: 2015-07</p></div></div>').window.document;
 const col=doc.querySelector('#col'),block=doc.querySelector('#block'),image=block.querySelector('img');
 if(!photo)delete image.dataset.expandedStreetImage;
 Object.defineProperty(col,'scrollHeight',{get:()=>500-remaining+parseFloat(image.style.height)+20});
 context.fitExpandedStreetBlock(block,col,500);
 return {col,block,image};
}
const fitting=scenario(200);assert.equal(fitting.image.style.height,'170px');
const orphan=scenario(180);assert(orphan.col.scrollHeight<=500,'photo and caption must both fit');assert.equal(orphan.block.children.length,2);assert(parseFloat(orphan.image.style.height)>=100);assert(Math.abs(parseFloat(orphan.image.style.width)/parseFloat(orphan.image.style.height)-640/360)<1e-8,'Street photo must resize proportionally, not stretch');
const continuation=scenario(80);assert.equal(continuation.image.style.height,'170px','keep the whole readable photo with its caption for continuation');assert(continuation.col.scrollHeight>500);
const ordinary=scenario(180,false);assert.equal(ordinary.image.style.height,'170px','unrelated content must not shrink');
assert(source.includes('block.appendChild(image);block.appendChild(clone(el(\'rStreetMeta\')))'),'caption must travel in the same pagination block');
console.log('PASS: Expanded PDF keeps photo and date together, fits small overflows, preserves readable continuation and unrelated blocks');
