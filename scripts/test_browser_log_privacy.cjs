// Executes the real PDF failure handler with a secret-bearing synthetic exception.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('app.py','utf8');
const fn=source.slice(source.indexOf('async function downloadEstimatePDF(){'),source.indexOf('let reportCloseArmedAt='));
(async()=>{
 for(const industry of ['roofing','snow','pressure','paving','landscaping','commercial'])for(const layout of ['single','expanded']){
  const secret='QA_ONLY_BROWSER_API_KEY_42873',logs=[],messages=[];
  const button={disabled:false,textContent:'DOWNLOAD ESTIMATE PDF'};
  const fields={downloadPdfBtn:button,estimatePdfLayout:{value:layout},streetViewChoice:{value:'auto'},measureSource:{value:'google'}};
  const context={quoteSnapshot:{businessType:industry},reportMeasurementCorrection:null,
   savedEstimateMoneyIssue:()=>'',el:id=>fields[id],document:{querySelector:()=>({})},
   reportOutlineEditMode:false,estimateOpenInProgress:false,pdfInProgress:false,customerMap:null,
   html2canvas:async()=>{},window:{jspdf:{}},
   buildCustomerMap:async()=>{throw Error('https://qa.invalid/?api_key='+secret)},
   status:(...args)=>messages.push(args),console:{error:(...args)=>logs.push(args)}};
  vm.createContext(context);vm.runInContext(fn,context);await context.downloadEstimatePDF();
  assert.deepEqual(logs,[['AQ:pdf-generation-failed']]);
  assert(!JSON.stringify(logs).includes(secret));assert(messages.some(x=>x[0].includes('PDF could not be created')));
  assert.equal(context.pdfInProgress,false);assert.equal(button.disabled,false);assert.equal(button.textContent,'DOWNLOAD ESTIMATE PDF');
 }
 console.log('PASS: actual PDF failure handler logs fixed code without exception/URL secrets; UI recovery unchanged in all six industries and both layouts (VM simulation)');
})().catch(e=>{console.error(e);process.exit(1)});
