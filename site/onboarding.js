let current=1;
const total=9;
const steps=[...document.querySelectorAll('.setup-step')];
const next=document.getElementById('nextBtn'), back=document.getElementById('backBtn');
function showStep(n){
 current=Math.max(1,Math.min(total,n));
 steps.forEach(s=>s.classList.toggle('active',Number(s.dataset.step)===current));
 const sn=document.getElementById('stepNum'), pb=document.getElementById('progressBar');
 if(sn)sn.textContent=current;if(pb)pb.style.width=(current/total*100)+'%';
 if(back)back.style.visibility=current===1?'hidden':'visible';
 if(next)next.style.display=current===total?'none':'inline-block';
 window.scrollTo({top:0,behavior:'smooth'});
}
if(next)next.addEventListener('click',()=>showStep(current+1));
if(back)back.addEventListener('click',()=>showStep(current-1));

const country=document.getElementById('country');
if(country)country.addEventListener('change',e=>{
 const r=document.getElementById('regionLabel');
 if(r && r.childNodes[0])r.childNodes[0].nodeValue=e.target.value==='Canada'?'Province':'State';
});
function syncBusiness(){
 const c=document.getElementById('companyName')?.value||'';
 const p=document.getElementById('companyPhone')?.value||'';
 const e=document.getElementById('companyEmail')?.value||'';
 if(c){document.getElementById('brandCompany').value=c;document.getElementById('previewCompany').textContent=c.toUpperCase();}
 if(p)document.getElementById('brandPhone').value=p;
 if(e)document.getElementById('brandEmail').value=e;
}
['companyName','companyPhone','companyEmail'].forEach(id=>document.getElementById(id)?.addEventListener('input',syncBusiness));
document.querySelectorAll('input[name="pricing"]').forEach(r=>r.addEventListener('change',()=>{
 const f=document.getElementById('defaultPriceField');
 if(f)f.style.display=document.querySelector('input[name="pricing"]:checked')?.value==='manual'?'none':'block';
}));
document.getElementById('brandCompany')?.addEventListener('input',e=>document.getElementById('previewCompany').textContent=(e.target.value||'ABC SNOW SERVICES').toUpperCase());
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
  gst:document.getElementById('tax1')?.value||'0',pst:document.getElementById('tax2')?.value||'0',
  pricingMode:document.querySelector('input[name="taxmode"]:checked')?.value||'regular',
  warrantyStatement:document.getElementById('warrantyStatement')?.value||'',
  estimateMessage:document.getElementById('estimateMessage')?.value||'',
  ctaHeading:document.getElementById('ctaHeading')?.value||(industry==='snow'?'Schedule Your Snow Removal Service':'Schedule Your Pressure Washing Service'),
  marketingEnabled:true,marketingHeading:'WHY CHOOSE US',
  benefits:[
   {icon:'✓',title:'Reliable Service',text:'Dependable snow removal service tailored to your property.'},
   {icon:'✓',title:'Help Keep Properties Safe',text:'Help keep parking lots, driveways and walkways clear and accessible.'},
   {icon:'$',title:'Clear Upfront Pricing',text:'Your estimate clearly shows the service areas and pricing before work begins.'},
   {icon:'◆',title:'Property-Specific Service',text:'Service areas and pricing are prepared for your individual property.'}
  ]
 };
 const file=document.getElementById('logoUpload')?.files?.[0];
 if(file){profile.logoData=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=reject;r.readAsDataURL(file)})}
 if(profile.logoData)localStorage.setItem('sxDealerLogo',profile.logoData);
 localStorage.setItem('sxDealerDefaults',JSON.stringify(profile));
 localStorage.setItem('aeriQuoteIndustry',industry);
 return profile;
}
const setupIndustry=/snow-setup\.html/i.test(location.pathname)?'snow':(/pressure-setup\.html/i.test(location.pathname)?'pressure':null);
if(document.body.classList.contains('setup-page') && setupIndustry){
 const finish=document.getElementById('finishSetup');
 finish?.addEventListener('click',async function(event){
   event.preventDefault();
   if(this.dataset.opening==='true')return;
   const originalText=this.textContent;
   this.dataset.opening='true';this.disabled=true;this.textContent='OPENING MEASURING SYSTEM…';
   try{
     const profile=await saveIndustrySetupLocal(setupIndustry);
     const response=await fetch('/api/account/profile',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify(profile)});
     if(!response.ok)throw new Error('Your setup could not be saved to your account. Please sign in and try again.');
     // Carry the snow industry into the measuring URL as well as localStorage.
     window.location.assign('/?industry='+encodeURIComponent(setupIndustry));
   }catch(e){
     alert('Could not save setup in this browser. '+(e?.message||''));
     this.dataset.opening='false';this.disabled=false;this.textContent=originalText;
   }
 });
}
showStep(1);