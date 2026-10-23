/* QA-only contingency exporter. No map, provider, fetch, canvas or measurement writes. */
(function(root){
'use strict';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
const R=6378137, rad=Math.PI/180, ft=3.280839895013123;
function points(raw,min){
 if(!Array.isArray(raw)||raw.length<min)throw Error('Saved measurement geometry is incomplete. Reopen and correct this estimate.');
 let p=raw.map(v=>Array.isArray(v)?v:[v?.lat,v?.lng]);
 if(p.some(v=>v.length!==2||v.some(x=>typeof x!=='number'||!Number.isFinite(x))||Math.abs(v[0])>=85||Math.abs(v[1])>180))throw Error('Saved coordinates are invalid or outside the supported diagram range.');
 // Collapse exact consecutive click duplicates in the export view only; never mutate saved vertices.
 p=p.filter((v,i)=>!i||v[0]!==p[i-1][0]||v[1]!==p[i-1][1]);
 if(min===3&&p.length>3&&p[0][0]===p.at(-1)[0]&&p[0][1]===p.at(-1)[1])p.pop();
 if(new Set(p.map(v=>v.join(','))).size!==p.length)throw Error('Saved outline repeats a non-adjacent vertex. Correct the estimate before export.');
 if(p.length<min)throw Error('Saved outline has too few distinct points.');
 return p;
}
function area(p){let a=0;p.forEach((v,i)=>{const w=p[(i+1)%p.length];a+=(w[1]-v[1])*rad*(Math.sin(v[0]*rad)+Math.sin(w[0]*rad));});return Math.abs(a)*R*R/2*ft*ft;}
function distance(a,b){const h=Math.sin((b[0]-a[0])*rad/2)**2+Math.cos(a[0]*rad)*Math.cos(b[0]*rad)*Math.sin((b[1]-a[1])*rad/2)**2;return 2*6371000*Math.asin(Math.min(1,Math.sqrt(h)))*ft;}
function dimension(n){return n>0&&n<.005?'<0.01':n.toFixed(2);}
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
  for(let i=0;i<count;i+=3){for(let j=i;j<Math.min(i+3,count);j++)notes.push(`<text x="${12+(j-i)*290}" y="${y}" font-size="12">V${j+1}-V${(j+1)%s.points.length+1}: ${esc(dimension(distance(s.points[j],s.points[(j+1)%s.points.length])))} ft</text>`);y+=17;}y+=12;
 }
 return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${m.width} ${y+15}" role="img" aria-label="Saved measurement diagram with horizontal dimensions"><rect width="100%" height="100%" fill="white"/><g font-family="DejaVu Sans,Arial,sans-serif" fill="#112d38">`+m.items.map(s=>`<${s.closed?'polygon':'polyline'} points="${s.xy.map(p=>p.join(',')).join(' ')}" fill="${s.closed?'#edf5f4':'none'}" stroke="#165b60" stroke-width="2"/>`+(m.items.length===1?s.xy:[s.xy[0]]).map((p,i)=>`<text x="${p[0]+3}" y="${p[1]+13}" font-size="11">${m.items.length===1?'V'+(i+1):s.id}</text>`).join('')).join('')+'<text x="12" y="20" font-size="12">N</text><path d="M18 44 V25 M14 30 L18 25 L22 30" fill="none" stroke="#165b60"/>'+notes.join('')+'</g></svg>';
}
function textBlocks(report,ids){
 return ids.flatMap(id=>{const n=report.querySelector('#'+id);if(!n||n.closest('.marketingHidden')||n.style.display==='none')return[];
 return (id==='rMarketingBenefits'?[...n.children]:[n]).map(node=>{
 const copy=node.cloneNode(true);copy.querySelectorAll('img,svg,canvas,script,style,button,input,select,.marketingHidden,.benefitIcon').forEach(x=>x.remove());
 copy.querySelectorAll('span,b,strong').forEach(x=>{x.prepend(copy.ownerDocument.createTextNode(' '));x.appendChild(copy.ownerDocument.createTextNode(' '));});
 copy.querySelectorAll('div,p,br,h1,h2,h3,h4,li,tr').forEach(x=>{x.prepend(copy.ownerDocument.createTextNode('\n'));x.appendChild(copy.ownerDocument.createTextNode('\n'));});
 return {title:id==='rProperty'?'MEASUREMENTS':id==='rPricing'?'ESTIMATE SUMMARY':'',text:copy.textContent.split('\n').map(x=>x.replace(/\s+/g,' ').trim()).filter(Boolean).join('\n')};});});
}
async function build(jsPDF,snapshot,report){
 const items=shapes(snapshot); // Validate before creating a document or reading branding.
 const pdf=new jsPDF({orientation:'portrait',unit:'mm',format:'letter',compress:true});
 if(typeof pdf.addFont==='function'&&!root.AQVectorPDFFont)throw Error('QA diagram font did not load. Retry the vector download.');
 if(root.AQVectorPDFFont){pdf.addFileToVFS('DejaVuSans.ttf',root.AQVectorPDFFont);pdf.addFont('DejaVuSans.ttf','AQVector','normal');pdf.setFont('AQVector','normal');}
 const text=id=>report.querySelector('#'+id)?.textContent?.trim()||'';
 const clean=s=>{if(/[^\x09\x0a\x0d\x20-\xff\u2022\u2010-\u2015\u2713\u25c6\u2605\u25cf]/.test(String(s)))throw Error('Vector QA export cannot safely render a character in the estimate. Use the existing aerial PDF.');return String(s).replace(/\u2022/g,' | ').replace(/[\u2010-\u2015]/g,'-').replace(/\u2713/g,'');};
 const navy=[24,48,76],blue=[39,99,151],muted=[89,105,119],pale=[235,243,250],border=[208,221,232];
 const left=15,right=200.9,width=right-left,bottom=261,overflow=[];let page=0,y=0;
 const wrap=(s,w,size)=>{pdf.setFontSize(size);return pdf.splitTextToSize(clean(s),w);};
 const ink=(s,x,top,size=9,color=navy)=>{pdf.setFontSize(size);pdf.setTextColor(...color);pdf.text(clean(s),x,top);};
 const box=(x,top,w,h,color)=>{pdf.setFillColor(...color);pdf.rect(x,top,w,h,'F');};
 const rule=top=>{pdf.setDrawColor(...border);pdf.setLineWidth(.3);pdf.line(left,top,right,top);};
 // Branding is already loaded/frozen by the download wrapper. No provider images are read.
 const assets={};for(const id of ['rDealerLogo','rWarrantyShield']){
  const img=report.querySelector('#'+id);if(!img||img.classList.contains('noDealerLogo')||img.style.display==='none'||!img.getAttribute('src'))continue;
  if(!img.complete&&img.decode)await img.decode();
  if(!img.complete||!img.naturalWidth||!img.naturalHeight)throw Error('Branding image is not ready. Wait and retry the vector download.');
  assets[id]={source:img.getAttribute('src').startsWith('data:image/')?img.getAttribute('src'):img,ratio:img.naturalWidth/img.naturalHeight};
 }
 const image=(id,x,top,w,h)=>{const a=assets[id];if(!a)return;const iw=Math.min(w,h*a.ratio),ih=iw/a.ratio;pdf.addImage(a.source,x+(w-iw)/2,top+(h-ih)/2,iw,ih);};
 const bounded=(value,x,top,w,size,max)=>{const lines=wrap(value,w,size);lines.slice(0,max).forEach((s,i)=>ink(s,x,top+i*size*.42,size));if(lines.length>max)overflow.push(value);};
 const company=text('rDealerCompany')||text('rEstimateSubtitle')||'AeriQuote';
 const newPage=()=>{if(page++)pdf.addPage();image('rDealerLogo',left,12,28,15);
  bounded(company,assets.rDealerLogo?48:left,19,assets.rDealerLogo?85:115,14,2);
  [text('rPhone'),text('rDealerEmail'),text('rDealerWebsite')].filter(Boolean).forEach((s,i)=>bounded(s,143,15+i*4,58,7.5,1));
  rule(33);y=43;
 };
 const heading=(s,size=12)=>{for(const line of wrap(s,width,size)){if(y+12>bottom)newPage();ink(line,left,y,size);y+=size*.48;}y+=2;};
 const write=(str,size=8.5)=>{if(!String(str).trim())return;for(const line of wrap(str,width,size)){if(y+size*.45>bottom)newPage();ink(line,left,y,size);y+=size*.45;}y+=3;};
 // Fit the projected geometry to the entire panel, using ONE uniform scale. Never move buildings.
 const draw=(subset,x,top,w,h,vertices=false)=>{
  const m=model(subset,1000,1000*h/w),k=w/1000;
  box(x,top,w,h,[247,250,253]);pdf.setDrawColor(...blue);pdf.setLineWidth(.65);
  for(const s of m.items){const xy=s.xy.map(p=>[x+p[0]*k,top+p[1]*k]);
   pdf.setDrawColor(...blue);pdf.setFillColor(...pale);
   pdf.lines(xy.slice(1).map((p,i)=>[p[0]-xy[i][0],p[1]-xy[i][1]]),xy[0][0],xy[0][1],[1,1],s.closed?'FD':'S',s.closed);
   if(vertices){xy.forEach((p,i)=>ink('V'+(i+1),p[0]+1,p[1]+3,6.5));}
   else {const cx=xy.reduce((n,p)=>n+p[0],0)/xy.length,cy=xy.reduce((n,p)=>n+p[1],0)/xy.length;const badge=h<35?2.5:6;box(cx-badge/2,cy-badge/2,badge,badge,navy);ink(String(s.id),cx-badge*.18,cy+badge*.18,h<35?4:8,[255,255,255]);}
  }
  if(!vertices&&subset.length>1){ink('N',x+5,top+8,8);pdf.setDrawColor(...navy);pdf.line(x+6,top+17,x+6,top+10);pdf.line(x+6,top+10,x+4,top+13);pdf.line(x+6,top+10,x+8,top+13);}
 };
 newPage();heading(text('rEstimateTitle')||'Property Measurement & Estimate',17);
 const meta=(label,values,x,w)=>{ink(label,x,y,7.5,muted);let yy=y+5;for(const value of values.filter(Boolean)){const ls=wrap(value,w,9);ls.slice(0,3).forEach(s=>{ink(s,x,yy,9);yy+=4;});if(ls.length>3)overflow.push(value);}return yy;};
 y=Math.max(meta('PREPARED FOR',[text('rCustomerName'),text('rCustomerPhone'),text('rCustomerEmail')],left,85),meta('PROPERTY / DATE',[text('rAddress'),text('rDate')],113,88))+7;
 const marketingHead=textBlocks(report,['rMarketingHeading']),benefits=textBlocks(report,['rMarketingBenefits']).map(b=>b.text.split('\n').filter(line=>!/^\s*[◆★●|]?\s*$/.test(line)).join('\n')),marketingTail=textBlocks(report,['rMarketingWarranty','rCtaHeading','rCtaText']);
 const benefitW=(width-8)/3,benefitRows=[];
 for(let i=0;i<benefits.length;i+=3){const row=benefits.slice(i,i+3).map(b=>wrap(b,benefitW-6,7));benefitRows.push({row,height:Math.max(...row.map(x=>x.length))*3.2+6});}
 const marketingHeight=[...marketingHead,...marketingTail].reduce((n,b)=>n+wrap(b.text,width,7.5).length*3.3+3,0)+benefitRows.reduce((n,r)=>n+r.height+3,0);
 if(y+110>bottom)newPage();heading('Property overview');const overviewTop=y,overviewHeight=Math.max(70,Math.min(123,bottom-y-marketingHeight-items.length*7-19));
 const overview=model(items),occupied=Math.max(...overview.items.map(s=>{const xs=s.xy.map(p=>p[0]),ys=s.xy.map(p=>p[1]);return (Math.max(...xs)-Math.min(...xs))*(Math.max(...ys)-Math.min(...ys));}))/(overview.width*overview.height);
 const enlarged=items.length>1&&items.length<=3&&occupied<.12;
 if(enlarged){
  // Widely spaced buildings remain on the location diagram; explicit insets are individually scaled.
  const mainW=117,otherX=left+125,otherW=width-125;
  bounded(items[0].id+'. '+items[0].label,left,y,mainW,8,1);draw([items[0]],left,y+4,mainW,overviewHeight-12);
  const otherH=(overviewHeight-46)/(items.length-1);
  items.slice(1).forEach((s,i)=>{const top=y+i*otherH;bounded(s.id+'. '+s.label,otherX,top,otherW,8,1);draw([s],otherX,top+4,otherW,otherH-7);});
  ink('LOCATION / SHARED SCALE',otherX,y+overviewHeight-39,6,muted);draw(items,otherX,y+overviewHeight-36,otherW,28);
  ink('North up. Enlarged views are individually scaled; location diagram preserves spacing.',left,y+overviewHeight-2,7,muted);
 }else draw(items,left,y,width,overviewHeight);
 y+=overviewHeight+7;
 ink('SAVED MEASUREMENT SCOPE',left,y,8,muted);y+=5;
 for(const s of items){const value=`${s.id}. ${s.label}   |   ${s.closed?s.quantity.toFixed(2):dimension(s.quantity)} ${s.closed?'ft²':'ft'}${s.pitch!=null?'   |   Pitch '+s.pitch.toFixed(2)+' degrees':''}`;write(value,8);}
 for(const b of marketingHead)write(b.text,7.5);
 for(const group of benefitRows){if(group.height>bottom-43){for(const lines of group.row)write(lines.join('\n'),7);continue;}if(y+group.height>bottom)newPage();group.row.forEach((lines,j)=>{const x=left+j*(benefitW+4);box(x,y-3,benefitW,group.height,pale);lines.forEach((line,i)=>ink(line,x+3,y+i*3.2,7));});y+=group.height+3;}
 for(const b of marketingTail)write(b.text,7.5);
 // Individual section views and all pricing share page two for ordinary two-section jobs.
 newPage();heading('Detailed measurements');
 const detailed=items.filter(s=>s.closed||s.points.length>2);
 for(let i=0;i<detailed.length;i+=2){const pair=detailed.slice(i,i+2),cardW=(width-8)/2;
  const heights=pair.map(s=>{const edges=s.closed?s.points.length:s.points.length-1;return 74+Math.ceil(Math.min(edges,12)/2)*4+Math.min(3,wrap(s.label,cardW-8,10).length)*4;});
  const h=Math.max(...heights);if(y+h>bottom){newPage();heading('Detailed measurements - continued');}
  const top=y;
  pair.forEach((s,j)=>{const x=left+j*(cardW+8);let yy=top;
   const labels=wrap(s.id+'. '+s.label,cardW-8,10);if(labels.length>3)overflow.push(s.id+'. '+s.label);labels.slice(0,3).forEach(line=>{ink(line,x,yy,10);yy+=4;});
   draw([s],x,yy+2,cardW,48,true);yy+=55;
   ink(`${s.closed?s.quantity.toFixed(2):dimension(s.quantity)} ${s.closed?'ft²':'ft'}${s.pitch!=null?' | Pitch '+s.pitch.toFixed(2)+' degrees':''}`,x,yy,8);yy+=5;
   ink('HORIZONTAL DIMENSIONS',x,yy,6.5,muted);yy+=4;
   const edges=s.closed?s.points.length:s.points.length-1;
   for(let e=0;e<Math.min(edges,12);e++){ink(`V${e+1}-V${(e+1)%s.points.length+1}: ${dimension(distance(s.points[e],s.points[(e+1)%s.points.length]))} ft`,x+(e%2)*(cardW/2),yy+Math.floor(e/2)*4,7);}
  });y+=h;
  for(const s of pair){const edges=s.closed?s.points.length:s.points.length-1;for(let e=12;e<edges;e++)write(`${s.label} - V${e+1}-V${(e+1)%s.points.length+1}: ${dimension(distance(s.points[e],s.points[(e+1)%s.points.length]))} ft`,8);}
  // Numerical historical roof segments are preserved as text, never fabricated as facets.
  for(const s of pair)for(const [i,seg] of (s.segments||[]).entries())write(`${s.label} - Saved roof segment ${i+1}: ${Number(seg.area_sqft).toFixed(2)} ft² | pitch ${Number(seg.pitch_degrees).toFixed(2)} degrees (no inferred facet outline)`,8);
 }
 for(const s of items.filter(s=>!s.closed&&s.points.length===2)){
  if(y+25>bottom){newPage();heading('Detailed measurements - continued');}
  bounded(s.id+'. '+s.label,left,y,width,9,1);draw([s],left,y+3,75,12,true);
  ink(`${dimension(s.quantity)} ft | V1-V2: ${dimension(distance(s.points[0],s.points[1]))} ft`,98,y+10,8);y+=25;
 }
 const pricing=report.querySelector('#rPricing');const rows=pricing?[...pricing.children]:[];
 if(y+22>bottom)newPage();heading('Estimate summary');if(!rows.length)for(const b of textBlocks(report,['rPricing']))write(b.text,9);
 // Copy labels and formatted values verbatim from the frozen customer report. No price arithmetic.
 for(const row of rows){const kids=[...row.children],amountNode=kids.length?kids.at(-1):null;
  const amount=amountNode?.textContent.trim()||'',copy=row.cloneNode(true);if(amountNode)copy.lastElementChild.remove();
  const label=copy.textContent.trim(),grand=row.classList.contains('grand')||/^total\b/i.test(label);
  const a=wrap(amount,57,9),b=wrap(label,116,9),count=Math.max(a.length,b.length);
  for(let start=0;start<count;){
   if(y+9.4>bottom){newPage();heading('Estimate summary - continued');}
   const length=Math.min(count-start,Math.floor((bottom-y-5)/4.4)),h=length*4.4+5;
   if(grand)box(left,y-4,width,h,navy);else rule(y+h-5);
   const color=grand?[255,255,255]:navy;
   b.slice(start,start+length).forEach((s,i)=>ink(s,left+3,y+i*4.4,9,color));a.slice(start,start+length).forEach((s,i)=>ink(s,141,y+i*4.4,9,color));y+=h;start+=length;
  }
 }
 y+=3;
 for(const b of textBlocks(report,['rProperty']))write(b.text,7.5);
 write('Dimensions show horizontal plan lengths. Roof surface areas retain saved pitch adjustments. Not a survey or roof pitch measurement.',7);
 for(const b of textBlocks(report,['rEstimateDealerSub','rDealerName','rDealerAddress']))write(b.text,7.5);
 if(assets.rWarrantyShield){if(y+18>bottom)newPage();image('rWarrantyShield',left,y,30,15);y+=18;}
 const foot=report.querySelector('.reportFoot')?.textContent.trim();if(foot)write(foot,7);
 for(const value of [...new Set(overflow)])write(value,8);
 for(let i=1;i<=pdf.getNumberOfPages();i++){pdf.setPage(i);rule(267);ink(company.slice(0,70),left,273,7,muted);ink(`QA preview | ${i} / ${pdf.getNumberOfPages()}`,155,273,7,muted);}
 return {pdf,svg:svg(model(items)),items,layout:{orientation:'portrait',overview:{top:overviewTop,width,height:overviewHeight,enlarged}}};
}

const api={points,area,distance,shapes,model,svg,build};if(typeof module!=='undefined')module.exports=api;else root.AQVectorPDF=api;
})(typeof window!=='undefined'?window:globalThis);
