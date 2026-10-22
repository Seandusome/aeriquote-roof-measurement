// Reuse the real DOM/Leaflet manual measurement regression as the customer-report fixture.
const fs=require('node:fs');let test=fs.readFileSync('scripts/test_manual_roofing.cjs','utf8');
test=test.replace('const html=raw.replace(',"const html=raw.replaceAll('{{ VECTOR_PDF_QA_FLAG }}','1').replace(");
const injection=`
w.eval(require('node:fs').readFileSync('qa_vector_pdf.js','utf8'));
let vectorSaved=0,vectorText=[];
class VectorSink{constructor(){this.pages=1}setFontSize(){}setTextColor(){}setDrawColor(){}setLineWidth(){}splitTextToSize(s){return String(s).split('\\n')}text(t){vectorText.push(t)}line(){}addPage(){this.pages++}getNumberOfPages(){return this.pages}setPage(){}save(){vectorSaved++}}
w.jspdf={jsPDF:VectorSink};
const providerPaths=[];w.fetch=async(url,options)=>{providerPaths.push(url);assert.equal(url,'/qa-vector-diagram/validate');return{ok:true,json:async()=>({ok:true})}};
btn('estimatePdfLayout').value='vector';await w.eval('downloadEstimatePDF()');
assert.equal(vectorSaved,1,w.document.getElementById('status').textContent);assert(vectorText.join(' ').includes(w.eval('money(priceCalc().total)')),'Actual generated customer total preserved');assert.equal(w.eval('JSON.stringify(quoteSnapshot)'),frozen);assert.deepEqual(providerPaths,['/qa-vector-diagram/validate']);
if(process.env.VECTOR_QA_JSPDF&&process.env.VECTOR_QA_OUTPUT){
 w.eval(require('node:fs').readFileSync(process.env.VECTOR_QA_JSPDF,'utf8'));w.AQVectorPDFFont=require('node:fs').readFileSync('qa_assets/DejaVuSans.ttf').toString('base64');
 w.eval("el('dealerCountry').value='CA';countryChanged();el('province').value='AB';el('gst').value='5';el('pst').value='0';el('address').value='QA Alberta tax check, Edmonton, AB, Canada';el('customerName').value='QA Alberta Customer';renderSummary()");
 await w.eval('showCustomerEstimate()');w.eval('clearTimeout(customerMapBuildTimer);customerMapBuildTimer=null;estimateOpenInProgress=false');
 assert.equal(w.eval('priceCalc().pstAmt'),0);assert.equal(w.eval('priceCalc().gst'),5);
 const doc=await w.AQVectorPDF.build(w.jspdf.jsPDF,w.eval('JSON.parse(JSON.stringify(quoteSnapshot))'),w.document.querySelector('#reportOverlay .report'));
 require('node:fs').writeFileSync(process.env.VECTOR_QA_OUTPUT+'/simple-roof.pdf',Buffer.from(doc.pdf.output('arraybuffer')));
 const price=w.eval('priceCalc()'),quote=w.eval('JSON.parse(JSON.stringify(quoteSnapshot))');require('node:fs').writeFileSync(process.env.VECTOR_QA_OUTPUT+'/simple-roof-source.json',JSON.stringify({quote,pricing:price,total_area:price.area,total_price:price.total,extra_service_amount:price.extraAmount||0,extra_service_description:price.extraDescription||''},null,2));require('node:fs').writeFileSync(process.env.VECTOR_QA_OUTPUT+'/simple-roof.svg',doc.svg);
}
console.log('PASS real customer report from DOM/Leaflet manual sections reaches QA vector download with matching price, unchanged snapshot, and no provider paths');
`;
const anchor='w.eval("el(\'businessType\').value=\'snow\';businessTypeChanged();renderSummary()")';
if(!test.includes(anchor))throw Error('Manual report fixture changed; update explicit vector insertion point');
test=test.replace(anchor,injection+'\n'+anchor);new Function('require',test)(require);
