const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
(async()=>{
 const source=fs.readFileSync('app.py','utf8'),start=source.indexOf('function recordFirstMeasurement(){'),end=source.indexOf('\n}\n',start)+3,fn=source.slice(start,end);
 const calls=[];let responseOk=true,report=false;
 const c={activationRecorded:false,activationRecording:false,sessionToken:'own-property',quoteSnapshot:null,document:{body:{classList:{contains:()=>report}}},linearMeasurementSaved:false,linearPoints:[],areaMeasurementSaved:false,areaPoints:[],structures:[],manualPlanes:[],multiAreaSaved:()=>false,multiAreaTotal:()=>0,areaSqFtTotal:()=>100,linearFeetTotal:()=>70,googleTotal:()=>1200,manualTotal:()=>0,fetch:async(url,options)=>{calls.push({url,body:JSON.parse(options.body)});return{ok:responseOk}}};
 vm.createContext(c);vm.runInContext(fn,c);
 const flush=()=>new Promise(r=>setImmediate(r));
 c.recordFirstMeasurement();await flush();assert.equal(calls.length,0,'Loading aerial alone does not activate');
 c.areaPoints=[1,2,3];c.recordFirstMeasurement();await flush();assert.equal(calls.length,0,'Unsaved area does not activate');
 c.areaMeasurementSaved=true;c.recordFirstMeasurement();c.recordFirstMeasurement();await flush();assert.equal(calls.length,1);assert.equal(calls[0].body.kind,'area');assert.equal(calls[0].body.amount,100);
 c.recordFirstMeasurement();await flush();assert.equal(calls.length,1,'Successful first activation only sends once per workspace');
 c.activationRecorded=false;c.areaMeasurementSaved=false;c.linearMeasurementSaved=true;c.linearPoints=[1,2];responseOk=false;c.recordFirstMeasurement();await flush();assert.equal(c.activationRecorded,false);responseOk=true;c.recordFirstMeasurement();await flush();assert.equal(c.activationRecorded,true);assert.equal(calls.at(-1).body.kind,'linear');
 c.activationRecorded=false;report=true;c.recordFirstMeasurement();await flush();assert.equal(c.activationRecorded,false,'Historical report does not activate');report=false;c.quoteSnapshot={savedPricing:{}};c.recordFirstMeasurement();await flush();assert.equal(c.activationRecorded,false);
 c.quoteSnapshot=null;c.linearMeasurementSaved=false;c.structures=[{}];c.recordFirstMeasurement();await flush();assert.equal(calls.at(-1).body.kind,'roof');assert.equal(calls.at(-1).body.amount,1200);
 console.log('PASS: only successful saved/manual/automatic measurements activate, repeat suppression, retry and historical-report exclusion');
})().catch(e=>{console.error(e);process.exit(1)});
