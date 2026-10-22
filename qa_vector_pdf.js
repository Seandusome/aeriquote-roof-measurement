/* QA-only contingency exporter. No map, provider, fetch, canvas or measurement writes. */
(function(root){
'use strict';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
const R=6378137, rad=Math.PI/180, ft=3.280839895013123;
function points(raw,min){
 if(!Array.isArray(raw)||raw.length<min)throw Error('Saved measurement geometry is incomplete. Reopen and correct this estimate.');
 const p=raw.map(v=>Array.isArray(v)?v:[v?.lat,v?.lng]);
 if(p.some(v=>v.length!==2||v.some(x=>typeof x!=='number'||!Number.isFinite(x))||Math.abs(v[0])>=85||Math.abs(v[1])>180))throw Error('Saved coordinates are invalid or outside the supported diagram range.');
 if(min===3&&p.length>3&&p[0][0]===p.at(-1)[0]&&p[0][1]===p.at(-1)[1])p.pop();
 if(new Set(p.map(v=>v.join(','))).size<min)throw Error('Saved outline has too few distinct points.');
 return p;
}
function area(p){let a=0;p.forEach((v,i)=>{const w=p[(i+1)%p.length];a+=(w[1]-v[1])*rad*(Math.sin(v[0]*rad)+Math.sin(w[0]*rad));});return Math.abs(a)*R*R/2*ft*ft;}
function distance(a,b){const h=Math.sin((b[0]-a[0])*rad/2)**2+Math.cos(a[0]*rad)*Math.cos(b[0]*rad)*Math.sin((b[1]-a[1])*rad/2)**2;return 2*6371000*Math.asin(Math.min(1,Math.sqrt(h)))*ft;}
function agree(actual,saved,label){if(typeof saved!=='number'||!Number.isFinite(saved)||saved<=0||Math.abs(actual-saved)>Math.max(.05,saved*.001))throw Error(label+' does not match the saved geometry. Correct the estimate before export.');}
function shapes(s){
 if(!s||!['roofing','commercial','snow','pressure','paving','landscaping'].includes(s.businessType))throw Error('Saved estimate industry is missing.');
 const mode=s.measurementMode,roof=s.businessType==='roofing',hasAreas=(s.commercialAreas||[]).length>0;
 if(!['auto','area','linear'].includes(mode))throw Error('Saved measurement mode is missing.');
 const includeArea=mode==='area'||(!roof&&(hasAreas||s[s.businessType+'Combined']));
 const includeLine=mode==='linear'||(!roof&&hasAreas);
 const includeRoofs=roof&&mode==='auto';
 if(includeRoofs&&s.measureSource==='adjusted')throw Error('This historical adjusted quote needs independent scope review before vector export. Use the existing aerial PDF.');
 const planes=includeRoofs&&['manual','hybrid'].includes(s.measureSource)?s.manualPlanes||[]:[];
 const buildings=includeRoofs&&(s.measureSource!=='manual'||!planes.length)?s.structures||[]:[];
 s={...s,commercialAreas:includeArea?s.commercialAreas:[],areaPoints:includeArea?s.areaPoints:[],areaSqFt:includeArea?s.areaSqFt:0,linearPoints:includeLine?s.linearPoints:[],linearFeet:includeLine?s.linearFeet:0,manualPlanes:planes,structures:buildings};
 if(s.linearFeet>0&&!(s.linearPoints||[]).length||s.areaSqFt>0&&!(s.commercialAreas||[]).length&&!(s.areaPoints||[]).length)throw Error('Saved measurement geometry is missing.');
 const result=[];const add=(raw,min,label,quantity,pitch)=>{const p=points(raw,min);result.push({id:result.length+1,points:p,closed:min===3,label:String(label),quantity,pitch});return p;};
 if((s.commercialAreas||[]).length){for(const a of s.commercialAreas){const p=add(a.points,3,a.name||'Service area',a.sqft);agree(area(p),a.sqft,'Area');}}
 else if((s.areaPoints||[]).length){const p=add(s.areaPoints,3,'Service area',s.areaSqFt);agree(area(p),s.areaSqFt,'Area');}
 if((s.structures||[]).length){for(const a of s.structures){if(a.needs_remeasure||a.automatic_review_warning)throw Error('Roof coverage is unverified.');if(!(a.total_roof_sqft>0))throw Error('Saved roof surface area is missing.');add(a.outline,3,a.label||'Roof outline',a.total_roof_sqft,null);result.at(-1).segments=a.segments||[];}}
 for(const [i,a] of (s.manualPlanes||[]).entries()){
  if(typeof a.pitch_degrees!=='number'||!Number.isFinite(a.pitch_degrees)||a.pitch_degrees<0||a.pitch_degrees>=80)throw Error('Saved roof pitch is missing or invalid.');
  if(s.manualRoofWorkflow&&(!a.pitch_confirmed||!s.roofScopeConfirmed))throw Error('Roof pitch or scope is unconfirmed.');
  const p=add(a.points,3,a.label||'Roof section '+(i+1),a.surface_sqft,a.pitch_degrees);agree(area(p)/Math.cos(a.pitch_degrees*rad),a.surface_sqft,'Roof surface area');
 }
 if((s.linearPoints||[]).length){const p=add(s.linearPoints,2,'Linear measurement',s.linearFeet);agree(p.slice(1).reduce((n,v,i)=>n+distance(p[i],v),0),s.linearFeet,'Linear distance');}
 if(!result.length)throw Error('No saved geometry is available for a vector diagram.');
 const all=result.flatMap(x=>x.points);if(Math.max(...all.map(x=>x[1]))-Math.min(...all.map(x=>x[1]))>1||Math.max(...all.map(x=>x[0]))-Math.min(...all.map(x=>x[0]))>1)throw Error('Saved measurements span too large an extent for a property diagram.');
 // Reject degenerate and crossing polygon edges independently of the measurement engine.
 for(const a of result.filter(x=>x.closed)){
  if(area(a.points)<.01)throw Error('Saved polygon is degenerate.');
  const cross=(p,q,r)=>(q[1]-p[1])*(r[0]-p[0])-(q[0]-p[0])*(r[1]-p[1]);
  for(let i=0;i<a.points.length;i++)for(let j=i+2;j<a.points.length;j++){
   if(i===0&&j===a.points.length-1)continue;const p=a.points[i],q=a.points[(i+1)%a.points.length],r=a.points[j],t=a.points[(j+1)%a.points.length];
   if(cross(p,q,r)*cross(p,q,t)<0&&cross(r,t,p)*cross(r,t,q)<0)throw Error('Saved polygon crosses itself.');
  }
 }
 return result;
}
function model(items,width=900,height=480){
 const all=items.flatMap(s=>s.points),lat=all.reduce((n,p)=>n+p[0],0)/all.length,origin=all[0];
 const project=p=>[(p[1]-origin[1])*rad*R*Math.cos(lat*rad),-(p[0]-origin[0])*rad*R];
 const xy=all.map(project),xs=xy.map(p=>p[0]),ys=xy.map(p=>p[1]),x0=Math.min(...xs),y0=Math.min(...ys),dx=Math.max(...xs)-x0,dy=Math.max(...ys)-y0;
 const scale=Math.min((width-70)/(dx||1),(height-70)/(dy||1)),ox=(width-dx*scale)/2,oy=(height-dy*scale)/2;
 return {width,height,scale,items:items.map(s=>({...s,xy:s.points.map(p=>{const q=project(p);return[ox+(q[0]-x0)*scale,oy+(q[1]-y0)*scale];})}))};
}
function svg(m){
 let y=m.height+22;const notes=[];
 for(const s of m.items){notes.push(`<text x="12" y="${y}" font-size="13">${esc(s.id+'. '+s.label+' | '+s.quantity.toFixed(2)+(s.closed?' ft²':' ft')+(s.pitch!=null?' | pitch '+s.pitch.toFixed(2)+' degrees':''))}</text>`);y+=19;
  const count=s.closed?s.points.length:s.points.length-1;
  for(let i=0;i<count;i+=3){for(let j=i;j<Math.min(i+3,count);j++)notes.push(`<text x="${12+(j-i)*290}" y="${y}" font-size="12">V${j+1}-V${(j+1)%s.points.length+1}: ${distance(s.points[j],s.points[(j+1)%s.points.length]).toFixed(2)} ft</text>`);y+=17;}y+=12;
 }
 return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${m.width} ${y+15}" role="img" aria-label="Saved measurement diagram with horizontal dimensions"><rect width="100%" height="100%" fill="white"/><g font-family="DejaVu Sans,Arial,sans-serif" fill="#112d38">`+m.items.map(s=>`<${s.closed?'polygon':'polyline'} points="${s.xy.map(p=>p.join(',')).join(' ')}" fill="${s.closed?'#edf5f4':'none'}" stroke="#165b60" stroke-width="2"/>`+(m.items.length===1?s.xy:[s.xy[0]]).map((p,i)=>`<text x="${p[0]+3}" y="${p[1]+13}" font-size="11">${m.items.length===1?'V'+(i+1):s.id}</text>`).join('')).join('')+'<text x="12" y="20" font-size="12">N</text><path d="M18 44 V25 M14 30 L18 25 L22 30" fill="none" stroke="#165b60"/>'+notes.join('')+'</g></svg>';
}
function textBlocks(report,ids){
 return ids.flatMap(id=>{const n=report.querySelector('#'+id);if(!n||n.classList.contains('marketingHidden')||n.style.display==='none')return[];
 const copy=n.cloneNode(true);copy.querySelectorAll('img,svg,canvas,script,style,button,input,select,.marketingHidden').forEach(x=>x.remove());
 copy.querySelectorAll('span,b,strong').forEach(x=>{x.prepend(copy.ownerDocument.createTextNode(' '));x.appendChild(copy.ownerDocument.createTextNode(' '));});
 copy.querySelectorAll('div,p,br,h1,h2,h3,h4,li,tr').forEach(x=>{x.prepend(copy.ownerDocument.createTextNode('\n'));x.appendChild(copy.ownerDocument.createTextNode('\n'));});
 return [{title:id==='rProperty'?'MEASUREMENTS':id==='rPricing'?'ESTIMATE SUMMARY':'',text:copy.textContent.split('\n').map(x=>x.replace(/\s+/g,' ').trim()).filter(Boolean).join('\n')}];});
}
async function build(jsPDF,snapshot,report){
 const items=shapes(snapshot); // Fail before making any document or reading branding images.
 const pdf=new jsPDF({orientation:'landscape',unit:'mm',format:'letter',compress:true});let y=0,page=0;
 if(typeof pdf.addFont==='function'&&!root.AQVectorPDFFont)throw Error('QA diagram font did not load. Retry the vector download.');
 if(root.AQVectorPDFFont){pdf.addFileToVFS('DejaVuSans.ttf',root.AQVectorPDFFont);pdf.addFont('DejaVuSans.ttf','AQVector','normal');pdf.setFont('AQVector','normal');}
 const text=id=>report.querySelector('#'+id)?.textContent?.trim()||'';
 const clean=s=>{if(/[^\x09\x0a\x0d\x20-\xff\u2022\u2010-\u2015\u2713\u25c6\u2605\u25cf]/.test(String(s)))throw Error('Vector QA export cannot safely render a character in the estimate. Use the existing aerial PDF.');return String(s).replace(/\u2022/g,' | ').replace(/[\u2010-\u2015]/g,'-').replace(/\u2713/g,'');};
 const write=(str,size=10)=>{pdf.setFontSize(size);for(const line of pdf.splitTextToSize(clean(str),245)){if(y>190)newPage('ESTIMATE DETAILS - CONTINUED');pdf.text(line,15,y);y+=size*.48;}y+=2;};
 const newPage=title=>{if(page++)pdf.addPage();pdf.setTextColor(17,45,56);y=15;
  const head=(value,size)=>{pdf.setFontSize(size);const lines=pdf.splitTextToSize(clean(value),245);lines.slice(0,2).forEach((line,i)=>{pdf.text(line+(i===1&&lines.length>2?'...':''),15,y);y+=size*.48;});y+=2;};
  head(text('rEstimateTitle')||'AeriQuote Estimate',16);head(text('rEstimateSubtitle'),10);head([text('rAddress'),text('rCustomerName'),text('rDate')].filter(Boolean).join(' | '),9);head(title,12);
 };
 newPage('VECTOR DIAGRAM - QA ONLY');
 write('Saved geometry. North up. Dimensions are horizontal plan lengths; roof surface areas retain saved pitch adjustments. Not a survey or roof pitch measurement.',9);
 const draw=(m,top,h,labels)=>{
  const k=Math.min(245/m.width,h/m.height),left=15+(245-m.width*k)/2;
  pdf.setDrawColor(22,91,96);pdf.setLineWidth(.45);
  for(const s of m.items){const xy=s.xy.map(p=>[left+p[0]*k,top+p[1]*k]);
   for(let i=1;i<xy.length;i++)pdf.line(...xy[i-1],...xy[i]);if(s.closed)pdf.line(...xy.at(-1),...xy[0]);
   pdf.setFontSize(8);pdf.text(String(s.id),xy[0][0],xy[0][1]-2);
   if(labels){xy.forEach((p,i)=>pdf.text('V'+(i+1),p[0]+1,p[1]+3));}
  }
  pdf.setFontSize(9);pdf.text('N',17,top+5);pdf.line(18,top+12,18,top+7);
 };
 draw(model(items),y,105,false);y+=110;write('SECTION KEY',10);
 for(const s of items)write(`${s.id}. ${s.label} - ${s.quantity.toFixed(2)} ${s.closed?'ft²':'ft'}${s.pitch!=null?' | pitch '+s.pitch.toFixed(2)+' degrees':''}${s.closed&&s.pitch==null&&snapshot.businessType==='roofing'?' | saved outer outline; no inferred roof facets':''}`,9);
 for(const s of items){newPage(`${s.id}. ${s.label}`);draw(model([s]),y,100,true);y+=105;
  write(`Saved ${s.closed?'area':'length'}: ${s.quantity.toFixed(2)} ${s.closed?'ft²':'ft'}${s.pitch!=null?' | pitch '+s.pitch.toFixed(2)+' degrees':''}`,10);
  for(const [i,seg] of (s.segments||[]).entries())write(`Saved roof segment ${i+1}: ${Number(seg.area_sqft).toFixed(2)} ft² | pitch ${Number(seg.pitch_degrees).toFixed(2)} degrees (no inferred facet outline)`,9);
  write('HORIZONTAL DIMENSIONS (feet)',10);
  const edges=s.closed?s.points.length:s.points.length-1;
  for(let i=0;i<edges;i+=3){if(y>188)newPage('HORIZONTAL DIMENSIONS - CONTINUED');pdf.setFontSize(9);for(let j=i;j<Math.min(i+3,edges);j++)pdf.text(`V${j+1} to V${(j+1)%s.points.length+1}: ${distance(s.points[j],s.points[(j+1)%s.points.length]).toFixed(2)} ft`,15+(j-i)*82,y);y+=7;}
 }
 newPage('MEASUREMENTS & ESTIMATE DETAILS');
 for(const b of textBlocks(report,['rEstimateTitle','rEstimateSubtitle','rAddress','rCustomerName','rDate','rCustomerPhone','rCustomerEmail','rEstimateDealerSub','rProperty','rPricing','rMarketingHeading','rMarketingBenefits','rMarketingWarranty','rCtaHeading','rCtaText','rDealerCompany','rDealerName','rPhone','rDealerEmail','rDealerWebsite','rDealerAddress'])){if(b.title)write(b.title,12);write(b.text,10);}
 // Preserve only already-loaded dealer branding assets. Never fetch or embed property imagery.
 for(const id of ['rDealerLogo','rWarrantyShield']){
 const logo=report.querySelector('#'+id);
 if(logo&&!logo.classList.contains('noDealerLogo')&&logo.style.display!=='none'&&logo.getAttribute('src')){
  if(!logo.complete&&logo.decode)await logo.decode();
  if(!logo.complete||!logo.naturalWidth||!logo.naturalHeight)throw Error('Branding image is not ready. Wait and retry the vector download.');
  if(y>165)newPage('BRANDING');const h=Math.min(20,45/(logo.naturalWidth/logo.naturalHeight));pdf.addImage(logo.getAttribute('src')?.startsWith('data:image/')?logo.getAttribute('src'):logo,15,y,h*logo.naturalWidth/logo.naturalHeight,h);y+=h+3;
 }}
 const foot=report.querySelector('.reportFoot')?.textContent?.trim();if(foot)write(foot,8);
 for(let i=1;i<=pdf.getNumberOfPages();i++){pdf.setPage(i);pdf.setFontSize(8);pdf.text(`Vector Diagram QA | ${i} / ${pdf.getNumberOfPages()} | No property imagery`,15,207);}
 return {pdf,svg:svg(model(items)),items};
}
const api={points,area,distance,shapes,model,svg,build};if(typeof module!=='undefined')module.exports=api;else root.AQVectorPDF=api;
})(typeof window!=='undefined'?window:globalThis);
