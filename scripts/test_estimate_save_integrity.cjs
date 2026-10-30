// Exercise the real save function with controlled network outcomes.
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const s=fs.readFileSync('app.py','utf8'),fn=s.slice(s.indexOf('async function saveEstimateHistory(){'),s.indexOf('function openEstimateHistory(){'));
const fields={streetViewChoice:{value:'none'},address:{value:'QA property'},customerName:{value:'QA DO NOT SEND'},extraServiceDescription:{value:'Original service'},extraServiceAmount:{value:10}};
const saved=[],messages=[];let fail=false;
const c={AbortController,setTimeout,clearTimeout,quotePricingError:()=>'',el:id=>fields[id],priceCalc:()=>({area:100,total:110,mode:'added'}),captureQuoteSnapshot:()=>({}),quoteSnapshot:{businessType:'landscaping',measurementMode:'area',areaPoints:[[1,1],[1,2],[2,2]],commercialAreas:[{name:'Front',sqft:100,rate:1}]},savedPropertyEditActive:true,savedStreetImageData:'',savedJobDetails:{job_status:'Booked',scheduled_date:'2026-10-20',amount_paid:50},sessionToken:'saved',lastHistorySaveKey:'',status:(...x)=>messages.push(x),console:{warn(){}},fetch:async(url,o)=>{if(fail)throw Error('offline');saved.push(JSON.parse(o.body));return{ok:true}}};vm.createContext(c);vm.runInContext(fn,c);
(async()=>{
 await c.saveEstimateHistory();await c.saveEstimateHistory();assert.equal(saved.length,1,'Identical submission is skipped');
 fields.extraServiceDescription.value='Revised service';await c.saveEstimateHistory();assert.equal(saved.length,2,'Description-only edit must save');
 c.quoteSnapshot.commercialAreas[0].name='Rear';await c.saveEstimateHistory();assert.equal(saved.length,3,'Area name edit must save with unchanged amount');
 c.quoteSnapshot.areaPoints[0]=[1.01,1];await c.saveEstimateHistory();assert.equal(saved.length,4,'Geometry edit must save with unchanged amount');
 c.quoteSnapshot.businessType='snow';await c.saveEstimateHistory();assert.equal(saved.length,5,'Industry change must save with unchanged amount');
 assert.equal(saved[4].job_status,'Booked');assert.equal(saved[4].amount_paid,50);
 fields.extraServiceDescription.value='Retry me';const previousKey=c.lastHistorySaveKey;fail=true;assert.equal(await c.saveEstimateHistory(),false);assert.equal(c.lastHistorySaveKey,previousKey);assert(messages.some(x=>x[0].includes('not saved')),'Save failure must be visible');
 fail=false;assert.equal(await c.saveEstimateHistory(),true);assert.equal(saved.length,6,'Failed save can retry');
 assert(s.includes('if(!historicalMode&&!correctionRefresh&&(await saveEstimateHistory())===false)'), 'Report opening must stop on failed save');
 // Delay image loading and edit the form while the save is in flight.
 fields.streetViewChoice.value='auto';c.savedPropertyEditActive=false;c.sessionToken='original-session';
 fields.extraServiceDescription.value='Frozen service';fields.extraServiceAmount.value=10;
 c.quoteSnapshot.commercialAreas[0].name='Frozen area';
 let releaseImage;const posted=[];
 c.fetch=async(url,options)=>{if(url.startsWith('/street/')){await new Promise(resolve=>releaseImage=resolve);return {ok:false}}posted.push(JSON.parse(options.body));return {ok:true}};
 const pending=c.saveEstimateHistory();
 fields.extraServiceDescription.value='Later service';fields.extraServiceAmount.value=99;
 c.quoteSnapshot.commercialAreas[0].name='Later area';fields.address.value='Later address';
 releaseImage();assert.equal(await pending,true);
 assert.equal(posted[0].extra_service_description,'Frozen service');
 assert.equal(posted[0].extra_service_amount,10);
 assert.equal(posted[0].quote.commercialAreas[0].name,'Frozen area');
 assert.equal(posted[0].address,'QA property');
 c.savedPropertyEditActive=true;fields.estimatePeriod={value:'one_time'};c.priceCalc=()=>({area:100,total:110,mode:'added',estimatePeriod:fields.estimatePeriod.value});
 const periodSaves=[];c.fetch=async(url,options)=>{periodSaves.push(JSON.parse(options.body));return{ok:true}};
 await c.saveEstimateHistory();fields.estimatePeriod.value='month';await c.saveEstimateHistory();assert.equal(periodSaves.length,2,'Period-only change must save despite unchanged money');assert.equal(periodSaves[1].pricing.estimatePeriod,'month');assert.equal(periodSaves[0].total_price,periodSaves[1].total_price);
 const originalSnapshot=JSON.stringify(c.quoteSnapshot),lastSaved=c.lastHistorySaveKey;
 fields.customerName.value='QA validation rejection';c.fetch=async()=>({ok:false,status:400,json:async()=>({error:'Finish saving or cancel the unfinished service area before creating an estimate.'})});
 assert.equal(await c.saveEstimateHistory(),false);assert(messages.at(-1)[0].includes('unfinished service area'));assert(!messages.at(-1)[0].includes('Check your connection'));assert.equal(JSON.stringify(c.quoteSnapshot),originalSnapshot);assert.equal(c.lastHistorySaveKey,lastSaved);
 const retryId=c.saveEstimateHistory.pending.id;c.fetch=async()=>({ok:true,json:async()=>({version:'retry-success'})});assert.equal(await c.saveEstimateHistory(),true);assert.equal(c.saveEstimateHistory.pending,null);
 console.log('PASS: unchanged-total edits persist, duplicate skips, job metadata preserved, failed save visible and retryable');
})().catch(e=>{console.error(e);process.exit(1)});
