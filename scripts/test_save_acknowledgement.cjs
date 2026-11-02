// Unreadable successful HTTP responses must not be treated as saved work.
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync(process.env.QA_SAVE_SOURCE||'app.py','utf8');
const save=source.slice(source.indexOf('async function saveEstimateHistory(){'),source.indexOf('function openEstimateHistory(){'));
(async()=>{
 for(const failure of ['truncated','empty','null','array','missing-version','missing-id']){
  const fields={streetViewChoice:{value:'none'},address:{value:'FICTIONAL QA PROPERTY'},customerName:{value:'FICTIONAL ACK '+failure}};
  const posts=[],notices=[];let cleared=0;
  const c={AbortController,setTimeout,clearTimeout,el:id=>fields[id],quotePricingError:()=>'',priceCalc:()=>({area:100,total:111}),captureQuoteSnapshot:()=>({}),quoteSnapshot:{areaPoints:[[1,1],[1,2],[2,2]],measurementMode:'area'},savedPropertyEditActive:true,savedStreetImageData:'',savedJobDetails:{},sessionToken:'fixture',lastHistorySaveKey:'',workspaceSaveFingerprint:()=> 'exact-unsaved-work',status:(...x)=>notices.push(x),console:{warn(){}},window:{aqRecovery:{confirmSave:async()=>null,prepareSave:async()=>true,headers:()=>({}),saved(){cleared++}}}};
  c.fetch=async(url,o)=>{posts.push(o);return{ok:true,json:async()=>{if(failure==='truncated')throw SyntaxError('Unexpected end of JSON');return {'empty':{},'null':null,'array':[],'missing-version':{id:'fixture-id'},'missing-id':{version:'fixture-version'}}[failure]}}};
  vm.createContext(c);vm.runInContext(save,c);
  assert.equal(await c.saveEstimateHistory(),false,'Unreadable/malformed 200 '+failure+' must not mark work saved');
  assert(c.saveEstimateHistory.pending?.payload);assert.equal(c.saveEstimateHistory.cleanWorkspace,undefined);assert.equal(c.lastHistorySaveKey,'');assert.equal(cleared,0);assert(notices.at(-1)[0].includes('retry'));
  const uncertain=posts[0];c.fetch=async(url,o)=>{posts.push(o);return{ok:true,json:async()=>({id:'fixture-id',version:'fixture-version'})}};
  assert.equal(await c.saveEstimateHistory(),true);assert.equal(posts[1].headers['Idempotency-Key'],uncertain.headers['Idempotency-Key']);assert.equal(posts[1].body,uncertain.body);assert.equal(cleared,1);assert.equal(c.saveEstimateHistory.pending,null);
 }
 console.log('PASS: malformed/truncated/empty save acknowledgements retain pending work and exact retry operation; valid acknowledgement alone clears it');
})().catch(e=>{console.error(e);process.exit(1)});
