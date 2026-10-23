// Local QA artifact only. Uses the existing saved complex-roof snapshot unchanged.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {JSDOM}=require('jsdom'),v=require('../qa_vector_pdf.js');
(async()=>{
 const out=process.env.VECTOR_QA_OUTPUT,umd=process.env.VECTOR_QA_JSPDF;if(!out||!umd)throw Error('Set VECTOR_QA_OUTPUT and VECTOR_QA_JSPDF for local PDF generation.');
 const source=JSON.parse(fs.readFileSync('scripts/fixtures/vector-complex-roof.json','utf8')),before=JSON.stringify(source),p=source.pricing;
 const dom=new JSDOM('<div id="report"></div>',{runScripts:'dangerously'}),w=dom.window;w.HTMLCanvasElement.prototype.getContext=()=>({});w.eval(fs.readFileSync(umd,'utf8'));
 globalThis.AQVectorPDFFont=fs.readFileSync('qa_assets/DejaVuSans.ttf').toString('base64');globalThis.AQVectorPDFBoldFont=require('node:fs').readFileSync('qa_assets/DejaVuSans-Bold.ttf').toString('base64');const r=w.document.getElementById('report');
 const add=(id,value,tag='div')=>{const n=w.document.createElement(tag);n.id=id;n.textContent=value;r.appendChild(n);return n;};
 add('rEstimateTitle','Property Measurement & Estimate');add('rEstimateSubtitle','AeriQuote Demo');add('rDealerCompany','AeriQuote Demo');add('rPhone','(306) 555-0100');add('rDealerEmail','demo@example.invalid');add('rDealerWebsite','aeriquote.com');
 add('rCustomerName','Sample Customer - QA Preview');add('rCustomerEmail','customer@example.invalid');add('rAddress','Saskatchewan QA property\n52.000000, -106.000000');add('rDate','October 23, 2026');
 const logo=add('rDealerLogo','','img'),bytes=fs.readFileSync('site/assets/aeriquote-logo.png');logo.src='data:image/png;base64,'+bytes.toString('base64');Object.defineProperties(logo,{complete:{value:true},naturalWidth:{value:bytes.readUInt32BE(16)},naturalHeight:{value:bytes.readUInt32BE(20)}});
 add('rMarketingHeading','WHY CHOOSE US');const benefits=add('rMarketingBenefits','');
 for(const [title,body] of [['Professional Roofing','Roofing services tailored to your property.'],['Clear Upfront Pricing','Review measured quantities and pricing before work begins.'],['Property-Specific Planning','Review the included work and service scope for your property.']]){const row=w.document.createElement('div'),a=w.document.createElement('b'),b=w.document.createElement('div');a.textContent=title;b.textContent=body;row.append(a,b);benefits.appendChild(row);}
 const pricing=add('rPricing',''),money=n=>'CAD '+Number(n).toLocaleString('en-CA',{minimumFractionDigits:2,maximumFractionDigits:2});
 const row=(label,value,grand=false)=>{const n=w.document.createElement('div');n.className=grand?'line grand':'line';const a=w.document.createElement('span'),b=w.document.createElement('b');a.textContent=label;b.textContent=value;n.append(a,b);pricing.appendChild(n);};
 const sectionAmounts=source.quote.manualPlanes.map(s=>Math.round(s.surface_sqft*p.price*100)/100);assert.equal(Math.round(sectionAmounts.reduce((a,b)=>a+b,0)*100)/100,p.subtotal,'Section line items must reconcile to saved subtotal');
 source.quote.manualPlanes.forEach((s,i)=>row(s.label+' | '+s.surface_sqft.toFixed(2)+' ft² x '+money(p.price)+'/ft²',money(sectionAmounts[i])));
 row('Roofing subtotal',money(p.subtotal));row('Additional services',money(p.extraAmount));row('Promotion discount ('+p.disc+'%)','-'+money(p.discount));row('Taxable subtotal',money(p.taxBase));row('GST ('+p.gst+'%)',money(p.gstAmt));row('PST ('+p.pst+'%)',money(p.pstAmt));row('TOTAL (CAD)',money(p.total),true);
 add('rProperty','Roof surface area: '+p.area.toFixed(2)+' ft² | 2 measured sections | Confirmed pitches');
 add('rEstimateDealerSub','Prepared by AeriQuote Demo | (306) 555-0100 | demo@example.invalid');
 const footer=w.document.createElement('div');footer.className='reportFoot';footer.textContent='Final site conditions and measurements should be confirmed before work begins.';r.appendChild(footer);
 const result=await v.build(w.jspdf.jsPDF,source.quote,r);assert.equal(result.pdf.getNumberOfPages(),2,'Professional QA estimate must remain two pages');assert.equal(JSON.stringify(source),before,'Saved geometry and pricing must not change');
 fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,'AeriQuote_Professional_Vector_Estimate.pdf'),Buffer.from(result.pdf.output('arraybuffer')));fs.writeFileSync(path.join(out,'source.json'),JSON.stringify(source,null,2));
 console.log('PASS professional two-page actual AeriQuote exporter; unchanged saved geometry/pricing; section amounts reconcile; QA fixture only');w.close();
})().catch(e=>{console.error(e);process.exit(1)});
