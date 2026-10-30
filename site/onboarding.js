let current=1;
const steps=[...document.querySelectorAll('.setup-step')];
const total=steps.length;
const next=document.getElementById('nextBtn'), back=document.getElementById('backBtn');
function setupError(message='',field){const box=document.getElementById('setupError');if(box){box.textContent=message;box.hidden=!message}if(field){field.closest('details')?.setAttribute('open','');field.focus();field.reportValidity?.()}}
function validateStep(index){
 const section=steps[index-1];
 for(const field of section.querySelectorAll('input,select,textarea')){
  if(field.required&&!field.value.trim()){setupError('Please complete '+(field.closest('label')?.childNodes[0]?.textContent.trim()||'this field')+'.',field);return false}
  if(!field.checkValidity()){setupError('Please check '+(field.closest('label')?.childNodes[0]?.textContent.trim()||'this field')+'.',field);return false}
 }
 if(section.dataset.step==='4'&&document.querySelector('input[name="pricing"]:checked')?.value!=='manual'&&!(Number(document.getElementById('defaultPrice').value)>0)){setupError('Enter a starting rate greater than 0, or choose “I set each job’s rate”.',document.getElementById('defaultPrice'));return false}
 setupError();return true;
}
function updateSetupReview(){const review=document.getElementById('setupReview');if(!review)return;review.replaceChildren();
 const region=document.getElementById('region');const rate=document.querySelector('input[name="pricing"]:checked')?.value==='manual'?'Set the rate on each job':'$'+document.getElementById('defaultPrice').value+' / sq. ft.';
 for(const [title,value] of [['Business',document.getElementById('companyName').value],['Location',region.selectedOptions[0]?.textContent+', '+document.getElementById('country').value],['Starting price',rate],['Taxes',document.getElementById('tax1').value+'%'+(document.getElementById('country').value==='Canada'?' + '+document.getElementById('tax2').value+'%':'')+' · '+(document.querySelector('input[name="taxmode"]:checked')?.value==='included'?'included in price':'added to price')]]){const row=document.createElement('p'),b=document.createElement('b');b.textContent=title+': ';row.append(b,document.createTextNode(value));review.append(row)}
}
function showStep(n){
 current=Math.max(1,Math.min(total,n));
 steps.forEach((s,i)=>s.classList.toggle('active',i+1===current));
 const sn=document.getElementById('stepNum'), pb=document.getElementById('progressBar');
 if(sn)sn.textContent=current;if(pb)pb.style.width=(current/total*100)+'%';
 if(back)back.style.visibility=current===1?'hidden':'visible';
 if(next)next.style.display=current===total?'none':'inline-block';
 if(current===total)updateSetupReview();
 const heading=steps[current-1]?.querySelector('h1');if(heading){heading.tabIndex=-1;heading.focus({preventScroll:true})}
 window.scrollTo({top:0,behavior:'instant'});
}
if(next)next.addEventListener('click',()=>{if(validateStep(current))showStep(current+1)});
if(back)back.addEventListener('click',()=>{setupError();showStep(current-1)});

const country=document.getElementById('country');
const setupRegions={Canada:'AB:Alberta|BC:British Columbia|MB:Manitoba|NB:New Brunswick|NL:Newfoundland and Labrador|NS:Nova Scotia|NT:Northwest Territories|NU:Nunavut|ON:Ontario|PE:Prince Edward Island|QC:Quebec|SK:Saskatchewan|YT:Yukon','United States':'AL:Alabama|AK:Alaska|AZ:Arizona|AR:Arkansas|CA:California|CO:Colorado|CT:Connecticut|DE:Delaware|FL:Florida|GA:Georgia|HI:Hawaii|ID:Idaho|IL:Illinois|IN:Indiana|IA:Iowa|KS:Kansas|KY:Kentucky|LA:Louisiana|ME:Maine|MD:Maryland|MA:Massachusetts|MI:Michigan|MN:Minnesota|MS:Mississippi|MO:Missouri|MT:Montana|NE:Nebraska|NV:Nevada|NH:New Hampshire|NJ:New Jersey|NM:New Mexico|NY:New York|NC:North Carolina|ND:North Dakota|OH:Ohio|OK:Oklahoma|OR:Oregon|PA:Pennsylvania|RI:Rhode Island|SC:South Carolina|SD:South Dakota|TN:Tennessee|TX:Texas|UT:Utah|VT:Vermont|VA:Virginia|WA:Washington|WV:West Virginia|WI:Wisconsin|WY:Wyoming|DC:District of Columbia'};
let setupAlbertaTax=false;
function syncSetupTaxes(){
 const primary=document.getElementById('tax1'),secondary=document.getElementById('tax2');if(!primary||!secondary)return;
 for(const field of [primary,secondary]){field.step='any';field.placeholder='Example: 5 for 5%'}
 const canadian=country.value==='Canada',alberta=canadian&&document.getElementById('region')?.value==='AB';
 const primaryLabel=primary.closest('label'),secondaryLabel=secondary.closest('label');
 if(primaryLabel?.firstChild)primaryLabel.firstChild.nodeValue=alberta?'GST %':canadian?'Federal / HST Tax %':'Sales Tax %';
 if(secondaryLabel?.firstChild)secondaryLabel.firstChild.nodeValue=canadian?'Provincial Tax %':'Additional Tax %';
 if(secondaryLabel)secondaryLabel.hidden=!canadian||alberta;
 secondary.disabled=!canadian||alberta;secondary.required=canadian&&!alberta;
 if(secondary.disabled)secondary.value='0';else if(setupAlbertaTax)secondary.value='';
 const help=primary.closest('.setup-section')?.querySelector('.lead');
 if(help){if(!help.dataset.taxHelp)help.dataset.taxHelp=help.textContent;help.textContent=alberta?'Alberta has no provincial sales tax. Provincial tax is set to 0%. Enter the GST percentage your business charges, or 0 if you do not charge GST.':help.dataset.taxHelp;help.textContent+=' Enter 5 for 5% (not 0.05). Decimal rates such as 7.25 are supported.'}
 setupAlbertaTax=alberta;
}
function updateSetupRegions(value){
 const r=document.getElementById('regionLabel'),field=document.getElementById('region');if(!country||!field)return;
 const previous=field.dataset.country,memory=field._countryRegions||(field._countryRegions={});if(previous)memory[previous]=field.value;
 if(value===undefined)value=memory[country.value]||'';field.dataset.country=country.value;
 const label=country.value==='Canada'?'Province / territory':'State';if(r?.childNodes[0])r.childNodes[0].nodeValue=label;
 field.replaceChildren(new Option('Choose your '+label.toLowerCase(),''));field.required=true;
 for(const pair of setupRegions[country.value].split('|')){const [code,name]=pair.split(':');field.add(new Option(name,code));if(value===code||value===name)field.value=code}
 syncSetupTaxes();
}
if(country)country.addEventListener('change',()=>{updateSetupRegions();for(const id of ['tax1','tax2']){const f=document.getElementById(id);if(f){f.value=id==='tax2'&&country.value!=='Canada'?'0':'';f.dispatchEvent(new Event('input',{bubbles:true}))}}});
updateSetupRegions();
document.getElementById('region')?.addEventListener('change',syncSetupTaxes);
function syncBusiness(){
 const c=document.getElementById('companyName')?.value||'';
 const p=document.getElementById('companyPhone')?.value||'';
 const e=document.getElementById('companyEmail')?.value||'';
 for(const [id,value] of [['brandCompany',c],['brandPhone',p],['brandEmail',e]]){const field=document.getElementById(id);if(field&&!field.dataset.edited)field.value=value}
 if(c)document.getElementById('previewCompany').textContent=document.getElementById('brandCompany').value.toUpperCase();
}
['brandCompany','brandPhone','brandEmail'].forEach(id=>document.getElementById(id)?.addEventListener('input',e=>e.target.dataset.edited='true'));
['companyName','companyPhone','companyEmail'].forEach(id=>document.getElementById(id)?.addEventListener('input',syncBusiness));
document.querySelectorAll('input[name="pricing"]').forEach(r=>r.addEventListener('change',()=>{
 const f=document.getElementById('defaultPriceField');
 if(f)f.style.display=document.querySelector('input[name="pricing"]:checked')?.value==='manual'?'none':'block';
}));
document.getElementById('brandCompany')?.addEventListener('input',e=>document.getElementById('previewCompany').textContent=(e.target.value||(setupIndustry==='paving'?'ABC PAVING & SEALCOATING':setupIndustry==='pressure'?'ABC EXTERIOR CLEANING':setupIndustry==='landscaping'?'ABC LANDSCAPING':setupIndustry==='commercial'?'ABC PROPERTY SERVICES':setupIndustry==='roofing'?'ABC ROOFING':'ABC SNOW SERVICES')).toUpperCase());
document.getElementById('logoUpload')?.addEventListener('change',e=>{
 const file=e.target.files&&e.target.files[0];if(!file)return;
 const reader=new FileReader();reader.onload=()=>{document.getElementById('previewLogo').innerHTML='<img src="'+reader.result+'" alt="Company logo" style="max-width:150px;max-height:70px;object-fit:contain">';};reader.readAsDataURL(file);
});
function checkedTexts(step){return [...document.querySelectorAll('.setup-step[data-step="'+step+'"] .check-card input:checked')].map(i=>i.closest('.check-card')?.querySelector('b')?.textContent.trim()).filter(Boolean)}
async function saveIndustrySetupLocal(industry){
 const pricing=document.querySelector('input[name="pricing"]:checked')?.value||'sqft';
 const profile={
  name:document.getElementById('contactName')?.value.trim()||'',
  company:document.getElementById('brandCompany')?.value.trim()||document.getElementById('companyName')?.value.trim()||'',
  phone:document.getElementById('brandPhone')?.value.trim()||document.getElementById('companyPhone')?.value.trim()||'',
  email:document.getElementById('brandEmail')?.value.trim()||document.getElementById('companyEmail')?.value.trim()||'',
  website:document.getElementById('companyWebsite')?.value.trim()||'',
  country:document.getElementById('country')?.value==='Canada'?'CA':'US',
  province:document.getElementById('region')?.value||'',
  businessType:industry,pricingMethod:pricing,price:pricing==='manual'?'0':(document.getElementById('defaultPrice')?.value||'0'),
  coverage:'0',services:checkedTexts(2),propertyTypes:checkedTexts(3),
  gst:document.getElementById('tax1')?.value||'0',pst:country.value==='Canada'&&document.getElementById('region')?.value!=='AB'?(document.getElementById('tax2')?.value||'0'):'0',
  pricingMode:document.querySelector('input[name="taxmode"]:checked')?.value||'regular',
  warrantyStatement:document.getElementById('warrantyStatement')?.value||'',
  estimateMessage:document.getElementById('estimateMessage')?.value||'',
  ctaHeading:document.getElementById('ctaHeading')?.value||(industry==='roofing'?'Schedule Your Roofing Service':industry==='snow'?'Schedule Your Snow Removal Service':industry==='paving'?'Schedule Your Paving & Sealcoating Service':industry==='landscaping'?'Schedule Your Landscaping Service':industry==='commercial'?'Request Your Commercial Property Service':'Schedule Your Pressure Washing Service'),
  marketingEnabled:true,marketingHeading:'WHY CHOOSE US',
  benefits:industry==='roofing'?[{icon:'✓',title:'Professional Roofing',text:'Roofing services tailored to your property.'},{icon:'$',title:'Clear Upfront Pricing',text:'Measured roof areas and pricing shown before work begins.'},{icon:'◆',title:'Property-Specific Service',text:'Roofing work prepared for your property.'}]:industry==='commercial'?[{icon:'✓',title:'Commercial Property Services',text:'Commercial exterior and grounds services tailored to your property.'},{icon:'$',title:'Clear Upfront Pricing',text:'Clear estimates based on measured areas and your selected services.'},{icon:'◆',title:'Multiple Service Areas',text:'Parking lots, walkways, grounds and other service areas.'},{icon:'★',title:'Professional Service',text:'Professional estimates with a clearly defined scope of work.'},{icon:'●',title:'Property-Specific Planning',text:'Service recommendations tailored to the property layout.'},{icon:'✓',title:'Convenient Scheduling',text:'Scheduling options that consider property access and operations.'}]:industry==='landscaping'?[{icon:'✓',title:'Landscape Care',text:'Landscaping tailored to your property.'}]:industry==='paving'?[
   {icon:'✓',title:'Surface Preparation',text:'Paving and sealcoating tailored to the surface.'},
   {icon:'✓',title:'Protect Asphalt Surfaces',text:'Sealcoating can help protect suitable asphalt surfaces.'},
   {icon:'$',title:'Clear Upfront Pricing',text:'Measured paved areas and pricing shown before work begins.'},
   {icon:'◆',title:'Property-Specific Service',text:'Driveways and parking areas measured for your property.'},
   {icon:'✓',title:'Professional Service',text:'Paving and sealcoating tailored to your property.'}
  ]:industry==='pressure'?[
   {icon:'✓',title:'Professional Cleaning',text:'Pressure washing tailored to exterior surfaces.'},
   {icon:'✓',title:'Improve Curb Appeal',text:'Help remove dirt and grime.'},
   {icon:'$',title:'Clear Upfront Pricing',text:'Measured cleaning areas and pricing shown.'},
   {icon:'◆',title:'Property-Specific Service',text:'Cleaning areas tailored to your property.'},
   {icon:'✓',title:'Reliable Service',text:'Professional pressure washing.'}
  ]:[
   {icon:'✓',title:'Reliable Service',text:'Dependable snow removal tailored to your property.'},
   {icon:'✓',title:'Help Keep Properties Safe',text:'Keep lots, driveways and walkways clear.'},
   {icon:'$',title:'Clear Upfront Pricing',text:'Service areas and pricing shown upfront.'},
   {icon:'◆',title:'Property-Specific Service',text:'Service areas prepared for your property.'}
  ]
 };
 const file=document.getElementById('logoUpload')?.files?.[0];
 if(file){profile.logoData=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=reject;r.readAsDataURL(file)})}
 // Resize uploaded logos before storing them: raw phone images can exceed
 // the browser's small localStorage quota and block the entire setup.
 if(profile.logoData){
   try{
     const resized=await new Promise((resolve,reject)=>{
       const img=new Image();img.onload=()=>{
         const scale=Math.min(1,600/img.width,240/img.height);
         const canvas=document.createElement('canvas');
         canvas.width=Math.max(1,Math.round(img.width*scale));
         canvas.height=Math.max(1,Math.round(img.height*scale));
         const ctx=canvas.getContext('2d');ctx.clearRect(0,0,canvas.width,canvas.height);
         ctx.drawImage(img,0,0,canvas.width,canvas.height);
         resolve(canvas.toDataURL('image/png'));
       };img.onerror=reject;img.src=profile.logoData;
     });
     profile.logoData=resized;
   }catch(err){profile.logoData='';}
 }
 return profile;
}
function cacheSavedSetup(profile,industry){
 // Account save is authoritative; unavailable browser storage must not block navigation.
 const cachedProfile={...profile};delete cachedProfile.logoData;
 try{localStorage.setItem('sxDealerDefaults',JSON.stringify(cachedProfile))}catch(err){
   try{localStorage.removeItem('sxDealerDefaults');localStorage.setItem('sxDealerDefaults',JSON.stringify(cachedProfile))}catch(ignore){}
 }
 if(profile.logoData){
   try{localStorage.setItem('sxDealerLogo',profile.logoData)}
   catch(err){try{localStorage.removeItem('sxDealerLogo')}catch(ignore){}}
 }
 try{localStorage.setItem('aeriQuoteIndustry',industry)}catch(ignore){}
}
const setupPage=location.pathname.replace(/\/$/,'').split('/').pop().replace(/\.html$/i,'');
const setupIndustry=({'roofer-setup':'roofing','snow-setup':'snow','pressure-setup':'pressure','paving-setup':'paving','landscaping-setup':'landscaping','commercial-setup':'commercial'})[setupPage]||null;
if(document.body.classList.contains('setup-page') && setupIndustry){
 const edited=new Set();document.getElementById('setupForm')?.addEventListener('input',e=>edited.add(e.target.id));document.getElementById('setupForm')?.addEventListener('change',e=>edited.add(e.target.id));
 // Reuse the details just supplied at signup without overwriting an active edit.
 fetch('/api/account/profile',{credentials:'same-origin'}).then(r=>r.ok?r.json():null).then(account=>{
  if(!account)return;const p=account.profile||{};
  for(const [id,value] of [['companyName',p.company],['contactName',p.name],['companyPhone',p.phone],['companyEmail',p.email],['companyWebsite',p.website]]){const field=document.getElementById(id);if(field&&!edited.has(id)&&value)field.value=value}
  if(!edited.has('country')&&!edited.has('region')){country.value=['US','USA','UNITED STATES'].includes(String(p.country||'').toUpperCase())?'United States':'Canada';updateSetupRegions(p.province||'')}
  for(const [id,key] of [['tax1','gst'],['tax2','pst']]){if(!edited.has(id)&&p[key]!==undefined)document.getElementById(id).value=id==='tax2'&&country.value!=='Canada'?'0':p[key]}
  syncSetupTaxes();syncBusiness();
 }).catch(()=>{});
 const finish=document.getElementById('finishSetup');
 finish?.addEventListener('click',async function(event){
   event.preventDefault();
   if(this.dataset.opening==='true')return;
   for(let i=1;i<=total;i++){if(!validateStep(i)){showStep(i);return}}
   const originalText=this.textContent;
   this.dataset.opening='true';this.disabled=true;this.textContent='OPENING MEASURING SYSTEM…';
   try{
     const profile=await saveIndustrySetupLocal(setupIndustry);
     const response=await fetch('/api/account/profile',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify(profile)});
     if(!response.ok)throw new Error('Your setup could not be saved to your account. Please sign in and try again.');
     cacheSavedSetup(profile,setupIndustry);
     // Carry the selected industry into the measuring URL as well as localStorage.
     window.location.assign('/?industry='+encodeURIComponent(setupIndustry));
   }catch(e){
     setupError('Setup was not saved. '+(e?.message||'Please check your connection and try again.'));
     this.dataset.opening='false';this.disabled=false;this.textContent=originalText;
   }
 });
}
showStep(1);
