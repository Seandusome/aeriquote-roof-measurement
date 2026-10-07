let current=1;
const total=9;
const steps=[...document.querySelectorAll('.setup-step')];
const next=document.getElementById('nextBtn'), back=document.getElementById('backBtn');
function showStep(n){
 current=Math.max(1,Math.min(total,n));
 steps.forEach(s=>s.classList.toggle('active',Number(s.dataset.step)===current));
 document.getElementById('stepNum').textContent=current;
 document.getElementById('progressBar').style.width=(current/total*100)+'%';
 back.style.visibility=current===1?'hidden':'visible';
 next.style.display=current===total?'none':'inline-block';
 window.scrollTo({top:0,behavior:'smooth'});
}
next.addEventListener('click',()=>showStep(current+1));
back.addEventListener('click',()=>showStep(current-1));
document.getElementById('country').addEventListener('change',e=>{
 document.getElementById('regionLabel').childNodes[0].nodeValue=e.target.value==='Canada'?'Province':'State';
});
function syncBusiness(){
 const c=document.getElementById('companyName').value;
 const p=document.getElementById('companyPhone').value;
 const e=document.getElementById('companyEmail').value;
 if(c){ document.getElementById('brandCompany').value=c; document.getElementById('previewCompany').textContent=c.toUpperCase(); }
 if(p) document.getElementById('brandPhone').value=p;
 if(e) document.getElementById('brandEmail').value=e;
}
['companyName','companyPhone','companyEmail'].forEach(id=>document.getElementById(id).addEventListener('input',syncBusiness));
document.querySelectorAll('input[name="pricing"]').forEach(r=>r.addEventListener('change',()=>{
 document.getElementById('defaultPriceField').style.display=document.querySelector('input[name="pricing"]:checked').value==='manual'?'none':'block';
}));
document.getElementById('brandCompany').addEventListener('input',e=>document.getElementById('previewCompany').textContent=(e.target.value||'ABC ROOFING').toUpperCase());
document.getElementById('logoUpload').addEventListener('change',e=>{
 const file=e.target.files&&e.target.files[0]; if(!file)return;
 const reader=new FileReader(); reader.onload=()=>{document.getElementById('previewLogo').innerHTML='<img src="'+reader.result+'" alt="Company logo" style="max-width:150px;max-height:70px;object-fit:contain">';}; reader.readAsDataURL(file);
});
showStep(1);

// V6.63 / V11.6.91 — save Snow Removal onboarding to the authenticated AeriQuote account.
async function saveSnowSetup(){
 const country=document.getElementById('country')?.value||'Canada';
 const pricing=document.querySelector('input[name="pricing"]:checked')?.value||'sqft';
 const checkedTexts=(step)=>[...document.querySelectorAll('.setup-step[data-step="'+step+'"] .check-card input:checked')].map(i=>i.closest('.check-card')?.querySelector('b')?.textContent.trim()).filter(Boolean);
 const profile={
  name:document.getElementById('contactName')?.value.trim()||'', company:document.getElementById('brandCompany')?.value.trim()||document.getElementById('companyName')?.value.trim()||'',
  phone:document.getElementById('brandPhone')?.value.trim()||document.getElementById('companyPhone')?.value.trim()||'', email:document.getElementById('brandEmail')?.value.trim()||document.getElementById('companyEmail')?.value.trim()||'',
  website:document.getElementById('companyWebsite')?.value.trim()||'', address:'', country:country==='Canada'?'CA':'US', province:document.getElementById('region')?.value||'', businessType:'snow',
  pricingMethod:pricing, price:pricing==='manual'?'0':(document.getElementById('defaultPrice')?.value||'0'), coverage:'0', services:checkedTexts(2), propertyTypes:checkedTexts(3),
  gst:document.getElementById('tax1')?.value||'0', pst:document.getElementById('tax2')?.value||'0', pricingMode:(document.querySelector('input[name="taxmode"]:checked')?.parentElement?.textContent.toLowerCase().includes('included')?'included':'regular'),
  warrantyStatement:document.getElementById('warrantyStatement')?.value||'Example: We stand behind our snow removal service. Add your company service guarantee or satisfaction policy here.', estimateMessage:document.getElementById('estimateMessage')?.value||'Contact us to schedule snow removal service for your property.', ctaHeading:document.getElementById('ctaHeading')?.value||'Schedule Your Snow Removal Service',
  marketingEnabled:true, marketingHeading:'WHY CHOOSE US', marketingWarranty:document.getElementById('warrantyStatement')?.value||'Example: We stand behind our snow removal service. Add your company service guarantee or satisfaction policy here.', marketingCtaHeading:document.getElementById('ctaHeading')?.value||'Schedule Your Snow Removal Service', marketingCtaText:document.getElementById('estimateMessage')?.value||'Contact us to schedule snow removal service for your property.',
  benefits:[
   {icon:'✓',title:'Reliable Service',text:'Dependable snow removal service tailored to your property.'},
   {icon:'✓',title:'Help Keep Properties Safe',text:'Help keep parking lots, driveways and walkways clear and accessible.'},
   {icon:'$',title:'Clear Upfront Pricing',text:'Your estimate clearly shows the service areas and pricing before work begins.'},
   {icon:'◆',title:'Property-Specific Service',text:'Service areas and pricing are prepared for your individual property.'},
   {icon:'✓',title:'Service Guarantee',text:'Add your company warranty, service guarantee or satisfaction promise here.'}
  ]
 };
 const file=document.getElementById('logoUpload')?.files?.[0];
 if(file){profile.logoData=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=reject;r.readAsDataURL(file)})}
 const r=await fetch('/api/account/profile',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(profile)}); const d=await r.json(); if(!r.ok)throw new Error(d.error||'Could not save snow setup');
 if(profile.logoData)localStorage.setItem('sxDealerLogo',profile.logoData);localStorage.setItem('sxDealerDefaults',JSON.stringify(profile));window.location.href='/';
}
if(document.body.classList.contains('setup-page') && /snow-setup\.html/i.test(location.pathname)){
 document.getElementById('finishSetup')?.addEventListener('click',async function(){const old=this.textContent;this.disabled=true;this.textContent='SAVING SETUP…';try{await saveSnowSetup()}catch(e){alert(e.message);this.disabled=false;this.textContent=old}});
}
