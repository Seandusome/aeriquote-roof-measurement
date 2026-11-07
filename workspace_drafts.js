/* Server-acknowledged recovery only: no customer data in browser storage. */
(() => {
 'use strict';
 const meta=document.getElementById('aqAccountId');
 if(!meta?.dataset.principal)return;
 const identity=meta.dataset.principal,account=meta.dataset.accountId;
 const headers={'Content-Type':'application/json','X-AeriQuote-Account':account,'X-AeriQuote-Principal':identity};
 const uuid=()=>crypto.randomUUID();
 let id=uuid(),version=0,ack='',busy=false,paused=true,ended=false,writing=null,lastError=null,touched=false,uncertainWrite=null;
 const badge=document.createElement('div');badge.id='workspaceRecoveryStatus';badge.setAttribute('role','status');badge.style.cssText='padding:7px 12px;font-size:12px;background:#f0f5f3;color:#24483a';
 document.body.prepend(badge);
 const say=(message,warn=false)=>{badge.textContent=message;badge.hidden=!message;badge.style.background=warn?'#fff0d5':'#f0f5f3'};
 const fields=['address','streetAddress','cityTown','postalCode','propertyProvince','businessType','dealerCountry','customerName','customerPhone','customerEmail','customerNotes','extraServiceDescription','extraServiceAmount','streetViewChoice','jobPrice','pricingMode','discountPct','gst','pst','estimatePeriod','commercialLinearRate','landscapingAreaRate','pressureAreaRate','pavingAreaRate','measureSource','adjustedArea','manualRoofScopeConfirmed','pitchSel','pitchDeg','roofRemeasurePitch'];
 const clone=x=>JSON.parse(JSON.stringify(x));
 const points=x=>(x||[]).map(p=>[p.lat??p[0],p.lng??p[1]]);
 const latlng=x=>(x||[]).map(p=>L.latLng(p));
 function capture(){
  if(savedEstimateEditContext)return null;
  if(!sessionToken&&!touched)return null;
  if(!reportMeasurementCorrection&&saveEstimateHistory.cleanWorkspace&&saveEstimateHistory.cleanWorkspace===workspaceSaveFingerprint())return null;
  const previous=quoteSnapshot;let quote;
  try{quote=clone(captureQuoteSnapshot())}finally{quoteSnapshot=previous}
  const values={};fields.forEach(k=>{const n=el(k);if(n)values[k]=n.type==='checkbox'?n.checked:n.value});
  const pending=saveEstimateHistory.pending?clone(saveEstimateHistory.pending):null;
  // The exact operation identifier survives; image bytes never enter draft storage.
  if(pending){if(pending.requestKey){const k=JSON.parse(pending.requestKey);k.street_image_data='';pending.requestKey=stableWorkspaceJSON(k)}if(pending.payload?.street_image_data){pending.imageOmitted=true;pending.payload.street_image_data=''}}
  return {schema:1,sessionToken,quote,values,streetMeta:el('streetMeta')?.textContent||'',state:{areaPoints:points(areaPoints),linearPoints:points(linearPoints),areaMode,linearMode,areaMeasurementSaved,linearMeasurementSaved,commercialEditingIndex,traceMode,tracePoints:points(tracePoints),garageMode,roofFixMode,outlineEditMode,outlinePoints:points(outlinePoints),adjustedOutline,areaRemeasureMode,areaCorrectionOriginal,linearCorrectionOriginal,surfaceLineDraftOriginal,savedLinearJobRate,savedPropertyEditActive,savedJobDetails,measurementViewMode,pendingMeasurementMode,lastLoadedStreet,roofRemeasureTarget,roofOutlineReviewMode,roofReviewBoundarySource,roofReviewManualIndices,loadedAddressKey:loadProperty.loadedAddressKey,manualRoofEditIndex},reportCorrection:reportMeasurementCorrection?{mode:reportMeasurementCorrection.mode,index:reportMeasurementCorrection.index,points:points(reportMeasurementCorrection.points),uncertain:!!reportMeasurementCorrection.uncertain}:null,pending,baseVersion:saveEstimateHistory.baseVersion||null,lastHistorySaveKey:null};
 }
 async function request(path,options={}){
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),12000);
  try{const r=await fetch('/api/workspace-drafts'+path,{...options,headers,signal:controller.signal});const data=await r.json();if(!r.ok){const e=new Error(data.error||'Recovery request failed');e.status=r.status;e.code=data.code;throw e}return data}finally{clearTimeout(timer)}
 }
 async function flush(){
  if(paused||ended)return false;
  if(writing){const ok=await writing;if(!ok)return false;return flush()}
  let workspace;try{workspace=capture()}catch(e){say('Changes have not reached recovery storage. Keep this tab open.',true);return false}
  if(!workspace)return true;
  const serialized=JSON.stringify(workspace);if(serialized===ack&&!uncertainWrite)return true;
  say('Changes have not reached the server yet. Keep this tab open.',true);
  // Resolve an uncertain accepted write before attempting a newer payload.
  // Reusing its exact version/body lets the server recognize a lost-ack retry.
  const attempt=uncertainWrite?.id===id?uncertainWrite:{id,version,workspace:clone(workspace),serialized};
  const draftId=attempt.id,draftVersion=attempt.version;
  writing=(async()=>{
   try{const r=await request('/'+draftId,{method:'PUT',body:JSON.stringify({version:draftVersion,workspace:attempt.workspace})});if(id!==draftId)return true;if(!Number.isInteger(r?.version)||r.version!==draftVersion+1||!Number.isFinite(r.expires_at))throw new Error('Recovery acknowledgement unavailable');version=r.version;ack=attempt.serialized;uncertainWrite=null;if(JSON.stringify(capture())===ack)say('Recovery copy saved for 24 hours.');else say('Changes have not reached the server yet. Keep this tab open.',true);return true}
   catch(e){if(id===draftId&&!(e.status>=400&&e.status<500))uncertainWrite=attempt;lastError=e;say('Changes have not reached the server. '+e.message+' Keep this tab open.',true);return false}
  })();
  let ok;try{ok=await writing}finally{writing=null}
  if(ok&&id===draftId&&JSON.stringify(capture())!==ack)return flush();
  return ok;
 }
 function newDraft(){id=uuid();version=0;ack='';ended=false;uncertainWrite=null}
 async function restore(row){
  busy=true;
  try{
   const d=await request('/'+row.draft_id),w=d.workspace;
   const imagery=w.sessionToken?await request('/'+row.draft_id+'/imagery-session',{method:'POST',body:'{}'}):null;
   // Read the retained workspace only after ownership and imagery metadata checks.
   resetMeasurementForNewProperty();
   restoreSavedQuoteFields({address:w.values.address||''},w.quote,{});
   fields.forEach(k=>{const n=el(k);if(n&&k in w.values){if(n.type==='checkbox')n.checked=w.values[k];else n.value=w.values[k]}});
   const v=w.state;
   areaPoints=latlng(v.areaPoints);linearPoints=latlng(v.linearPoints);
   ({areaMode,linearMode,areaMeasurementSaved,linearMeasurementSaved,commercialEditingIndex,traceMode,garageMode,roofFixMode,outlineEditMode,adjustedOutline,areaRemeasureMode,areaCorrectionOriginal,linearCorrectionOriginal,surfaceLineDraftOriginal,savedLinearJobRate,savedPropertyEditActive,savedJobDetails,measurementViewMode,pendingMeasurementMode,lastLoadedStreet,roofRemeasureTarget,roofOutlineReviewMode,roofReviewBoundarySource,roofReviewManualIndices,manualRoofEditIndex}=v);
   tracePoints=latlng(v.tracePoints);outlinePoints=latlng(v.outlinePoints);
   if(w.reportCorrection){
    const c=w.reportCorrection;
    if(c.mode==='area'){commercialEditingIndex=c.index;areaCorrectionOriginal=latlng(commercialAreas[c.index]?.points||[]);areaPoints=latlng(c.points);areaMode=true;areaRemeasureMode=true;areaMeasurementSaved=false;measurementViewMode='area'}
    else{linearCorrectionOriginal=latlng(w.quote.linearPoints);linearPoints=latlng(c.points);linearMode=true;linearMeasurementSaved=false;measurementViewMode='linear'}
   }
   sessionToken=imagery?.token||null;touched=true;fallbackMode=!!imagery;removeStaleAerialLayers();
   loadProperty.loadedAddressKey=v.loadedAddressKey;
   saveEstimateHistory.pending=w.pending;if(w.pending?.payload&&!w.pending.requestKey)saveEstimateHistory.pending.requestKey=stableWorkspaceJSON(w.pending.payload);if(el('streetMeta'))el('streetMeta').textContent=w.streetMeta||'';saveEstimateHistory.baseVersion=w.baseVersion;saveEstimateHistory.cleanWorkspace=null;lastHistorySaveKey='';quoteSnapshot=null;
   if(imagery){map.setView([imagery.center.latitude,imagery.center.longitude],18);setPropertyMarker(imagery.center.latitude,imagery.center.longitude)}
   redrawRoofData();redrawManualDisplayLayers();if(traceMode){redrawTraceLine();setTraceControls(true)};redrawAreaMeasure();redrawLinearMeasure();updateAreaUi();updateLinearUi();updatePropertyActionButton();renderSummary();
   // Keep every measurement exactly as stored. Imagery refresh never invokes lookup.
   if(imagery)await loadStandardWideAerial();
   // Aerial loading initializes its own source defaults; recovery owns the retained source and rates.
   fields.forEach(k=>{const n=el(k);if(n&&k in w.values){if(n.type==='checkbox')n.checked=w.values[k];else n.value=w.values[k]}});
   renderSummary();
   const sourceId=row.draft_id;newDraft();paused=false;
   say('Draft restored. Review your measurements, then create the estimate when ready.');
   if(!await flush())return false;
   const cleanup=await request('/'+sourceId,{method:'DELETE',body:JSON.stringify({version:d.version})});
   if(!cleanup.deleted)say('Recovery copy saved for 24 hours. Newer work from another tab was kept separately.');
   return true;
  }catch(e){say('Draft could not be restored. '+e.message+' Retry Restore; the server copy is retained.',true);return false}
  finally{busy=false}
 }
 const separateLabel=()=>structures.some(roof=>roof.manually_measured)||manualPlanes.length||tracePoints.length
  ?'Keep working on this estimate':'Start a separate draft';
 async function choose(){
  try{
   const data=await request('');
   if(!data.drafts.length){paused=false;say('Recovery autosave is ready.');return}
   const panel=document.createElement('section');panel.id='workspaceRecoveryChoices';panel.setAttribute('aria-labelledby','workspaceRecoveryHeading');
   panel.style.cssText='margin:0 16px 12px;padding:12px;border:1px solid #bdcbd8;border-radius:10px;background:#f8fafc;scroll-margin-top:16px';
   const title=document.createElement('h2');title.id='workspaceRecoveryHeading';title.tabIndex=-1;title.textContent='Unsaved draft found';title.style.cssText='margin:0 0 8px;font-size:1rem';panel.append(title);
   for(const row of data.drafts){
    const line=document.createElement('div'),label=document.createElement('span');
    line.style.cssText='display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-bottom:8px';
    label.style.cssText='flex:1 1 14rem;overflow-wrap:anywhere';
    const expiry=new Date(row.expires_at*1000).toLocaleString(undefined,{month:'short',day:'numeric',year:'numeric',hour:'numeric',minute:'2-digit'});
    label.textContent='Expires '+expiry;
    request('/'+row.draft_id).then(d=>{
     const address=d.workspace?.values?.address||d.workspace?.values?.streetAddress;
     if(address)label.textContent=address+' · Expires '+expiry;
    }).catch(()=>{});
    const yes=document.createElement('button');yes.textContent='Restore';
    const no=document.createElement('button');no.textContent='Discard';no.style.cssText='background:white;color:#9b2226;border:1px solid #9b2226';
    yes.style.cssText='background:white;color:#16457b;border:1px solid #16457b';
    yes.onclick=async()=>{if(busy)return;yes.disabled=true;const ok=await restore(row);yes.disabled=false;if(ok)panel.remove()};
    no.onclick=async()=>{if(busy)return;no.disabled=true;try{await request('/'+row.draft_id,{method:'DELETE'});line.remove();if(panel.children.length===2){panel.remove();paused=false;newDraft();say('Recovery draft discarded.')}}catch(e){say(e.message,true);no.disabled=false}};
    line.append(label,yes,no);panel.append(line);
   }
   const fresh=document.createElement('button');fresh.id='workspaceRecoveryContinue';fresh.textContent=separateLabel();
   fresh.onclick=()=>{if(busy)return;panel.remove();paused=false;newDraft();say('Separate recovery draft ready.');};panel.append(fresh);
   const steps=document.getElementById('progress1')?.closest('.stepbar');
   if(steps)steps.before(panel);else badge.after(panel);
   say('');
  }catch(e){paused=false;say('Recovery storage is unavailable. Changes have not reached the server. Keep this tab open.',true)}
 }
 async function prepareSave(){
  lastError=null;
  if(busy)return false;
  if(paused){
   const panel=document.getElementById('workspaceRecoveryChoices');
   if(panel){
    const label=separateLabel();
    document.getElementById('workspaceRecoveryContinue').textContent=label;
    const message='A recovery draft choice is pending. Choose '+label+', Restore, or Discard.';
    lastError=Object.assign(new Error(message),{status:428});
    panel.scrollIntoView({block:'center'});
    document.getElementById('workspaceRecoveryHeading')?.focus({preventScroll:true});
   }
   return false;
  }
  if(await flush())return true;
  // A source consumed in another tab must not strand this tab's later edits.
  // Only an explicit Create retries under a fresh ID. Background autosave and
  // account/version conflicts never resurrect or overwrite a closed draft.
  if(lastError?.code!=='draft_closed')return false;
  newDraft();return flush();
 }
 window.aqRecovery={flush,prepareSave,lastError:()=>lastError,async confirmSave(operation_id){const d=await request('/'+id+'/save-status',{method:'POST',body:JSON.stringify({operation_id})});return d.saved?d.result:null},headers:()=>({...headers,'X-AeriQuote-Draft':id}),saved(){ended=true;ack='';newDraft();say('Estimate saved. Recovery copy deleted.');},capture};
 let debounce;
 function changed(){
  const continueButton=document.getElementById('workspaceRecoveryContinue');
  if(continueButton)continueButton.textContent=separateLabel();
  if(paused||busy)return;
  try{const w=capture();if(!w||JSON.stringify(w)===ack)return}catch(e){}
  say('Changes have not reached the server yet. Keep this tab open.',true);clearTimeout(debounce);debounce=setTimeout(flush,700);
 }
 document.addEventListener('input',()=>{touched=true;changed()});
 const priorSummary=renderSummary;renderSummary=function(){const result=priorSummary.apply(this,arguments);changed();return result};
 setInterval(()=>{if(!paused&&!busy)flush()},1800);
 document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden')flush()});
 window.addEventListener('online',flush);
 choose();
})();
