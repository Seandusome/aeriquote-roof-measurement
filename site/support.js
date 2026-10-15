(()=>{
'use strict';
const form=document.getElementById('support-form');if(!form)return;
const status=document.getElementById('support-status'),button=document.getElementById('support-send');
let csrf='',requestId='',lastPayload='';
const uuid=()=>crypto.randomUUID?crypto.randomUUID():'10000000-1000-4000-8000-100000000000'.replace(/[018]/g,c=>(Number(c)^crypto.getRandomValues(new Uint8Array(1))[0]&15>>Number(c)/4).toString(16));
async function configuration(){const response=await fetch('/api/public/support/config',{credentials:'same-origin',cache:'no-store'});if(!response.ok)throw Error('Support is temporarily unavailable. Please try again shortly.');const data=await response.json();csrf=data.csrf;if(!csrf)throw Error('Please refresh this page and try again.');}
form.addEventListener('submit',async event=>{
 event.preventDefault();if(!form.reportValidity())return;
 button.disabled=true;status.dataset.error='false';status.textContent='Sending your request…';
 const payload=Object.fromEntries(new FormData(form)),serialized=JSON.stringify(payload);
 if(serialized!==lastPayload){lastPayload=serialized;requestId=uuid();}
 payload.request_id=requestId;
 try{
  if(!csrf)await configuration();
  const response=await fetch('/api/public/support',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify(payload)});
  const data=await response.json().catch(()=>({}));
  if(!response.ok){if(response.status===400)csrf='';throw Error(data.error||'Your request could not be confirmed. Try again; your message is still here.');}
  if(!data.reference)throw Error('Your request could not be confirmed. Please try again.');
  status.textContent='Your request is saved. Reference: '+data.reference+'. We’ll reply by email.';
  form.reset();lastPayload='';requestId='';
 }catch(error){status.dataset.error='true';status.textContent=error.message||'Unable to connect. Please try again.';}
 finally{button.disabled=false;}
});
})();
