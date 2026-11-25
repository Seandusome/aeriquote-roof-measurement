/* Server-acknowledged recovery only: no customer data in browser storage. */
(() => {
 'use strict';
 const meta=document.getElementById('aqAccountId');
 if(!meta?.dataset.principal)return;
 const identity=meta.dataset.principal,account=meta.dataset.accountId;
 const headers={'Content-Type':'application/json','X-AeriQuote-Account':account,'X-AeriQuote-Principal':identity};
 const uuid=()=>crypto.randomUUID();
 let id=uuid(),version=0,ack='',busy=false,paused=true,ended=false,writing=null,lastError=null,touched=false,uncertainWrite=null;
 let pruneRecoveryChoices=()=>{};
 const badge=document.createElement('div');badge.id='workspaceRecoveryStatus';badge.setAttribute('role','status');badge.style.cssText='padding:7px 12px;font-size:12px;background:#f0f5f3;color:#24483a';
 document.body.prepend(badge);
 const say=(message,warn=false)=>{badge.textContent=message;badge.hidden=!message;badge.style.background=warn?'#fff0d5':'#f0f5f3'};

 // A native modal keeps forms, maps and job navigation inert for the entire
 // asynchronous restore, not just until the first geometry has been applied.
 const loading=document.createElement('dialog');loading.id='workspaceRecoveryLoading';
 loading.setAttribute('aria-labelledby','workspaceRecoveryLoadingTitle');loading.setAttribute('aria-describedby','workspaceRecoveryLoadingHelp');
 loading.style.cssText='box-sizing:border-box;width:calc(100% - 32px);max-width:30rem;padding:24px;border:2px solid #16457b;border-radius:12px;color:#132a46;background:white;overflow-wrap:anywhere';
 loading.innerHTML='<h2 id="workspaceRecoveryLoadingTitle" tabindex="-1" style="margin:0 0 12px">Restoring draft…</h2><p id="workspaceRecoveryLoadingHelp" style="margin:0">Please wait before editing or switching jobs. Your measurements, prices and customer details are being restored. Keep this tab open.</p>';
 loading.addEventListener('cancel',e=>e.preventDefault());document.body.append(loading);

 // Recovery imagery is staged off-screen. Only this awaited attempt can
 // install it; a timeout/cancelled attempt never writes into a later job.
 const cancelImagery=document.createElement('button');cancelImagery.id='workspaceRecoveryKeepCurrent';cancelImagery.type='button';cancelImagery.textContent='Keep current work';cancelImagery.style.cssText='margin-top:16px;padding:10px 14px';cancelImagery.hidden=true;loading.append(cancelImagery);
 function releaseRecoveryImagery(ready){
  if(!ready?.layer)return;
  const layers=ready.layer.getLayers?ready.layer.getLayers():[ready.layer];
  ready.layer.remove();layers.forEach(layer=>{if(String(layer._url||'').startsWith('blob:'))URL.revokeObjectURL(layer._url)});
 }
 async function prepareRecoveryImagery(imagery){
  let accept=true,timer,rejectWait;
  const fail=(message,code)=>Object.assign(new Error(message),{code});
  const stopped=new Promise((resolve,reject)=>{rejectWait=reject;timer=setTimeout(()=>reject(fail('Imagery did not finish within 25 seconds. Current work is unchanged.','recovery_imagery_timeout')),25000)});
  // manual_roof_only keeps Google's recovery on its existing wide-aerial
  // path regardless of the industry of the workspace currently on screen.
  const pending=preparePropertyImagery({...imagery,manual_roof_only:true});
  pending.then(ready=>{if(!accept)releaseRecoveryImagery(ready)},()=>{});
  const help=el('workspaceRecoveryLoadingHelp'),originalHelp=help.textContent;help.textContent='Waiting for saved imagery (up to 25 seconds). Keep current work stops recovery without discarding the saved draft.';
  cancelImagery.hidden=false;
  cancelImagery.onclick=()=>rejectWait(fail('Recovery stopped. Current work is unchanged.','recovery_cancelled'));
  try{return await Promise.race([pending,stopped])}
  finally{accept=false;clearTimeout(timer);cancelImagery.onclick=null;cancelImagery.hidden=true;help.textContent=originalHelp}
 }
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
  const failure=(message,status=0,code)=>Object.assign(new Error(message),{status,code});
  try{
   let r;
   try{r=await fetch('/api/workspace-drafts'+path,{...options,headers,cache:'no-store',signal:controller.signal})}
   catch(e){throw failure(e.name==='AbortError'?'Recovery connection timed out.':'Recovery connection is unavailable.');}
   // Preserve the HTTP/authentication result even if a private preview gateway
   // returns HTML rather than the application's JSON error response.
   if(r.status===401)throw failure('Your login expired. Sign in to the original account in another tab, then retry here.',401);
   const type=r.headers?.get('content-type')||'';
   if(r.redirected||(r.headers&&!/\bapplication\/(?:[\w.+-]+\+)?json\b/i.test(type)))
    throw failure('Recovery connection returned an unexpected page. Check the private preview sign-in in another tab, then retry here.',r.ok?0:r.status,'unexpected_response');
   let data;
   try{data=await r.json()}catch(e){throw failure('Recovery returned an unreadable response. Retry here when the server is available.',r.ok?0:r.status,'invalid_response');}
   if(!r.ok)throw failure(typeof data?.error==='string'?data.error:'Recovery request failed.',r.status,data?.code);
   return data;
  }finally{clearTimeout(timer)}
 }
 async function flush(duringRestore=false){
  // An unresolved older draft choice must not prevent preserving NEW work
  // under this tab's independent ID. Explicit estimate save still requires a choice.
  if(ended)return false;
  // Visibility/online events and external callers must not acknowledge a
  // partially applied workspace. Only restore's own checkpoints may write.
  if(busy&&duringRestore!==true)return false;
  if(writing){const ok=await writing;if(!ok)return false;return flush(duringRestore)}
  let workspace;try{workspace=capture()}catch(e){say('Changes have not reached recovery storage. Keep this tab open.',true);return false}
  if(!workspace)return true;
  const serialized=JSON.stringify(workspace);if(serialized===ack&&!uncertainWrite)return true;
  if(!lastError)say('Changes have not reached the server yet. Keep this tab open.',true);
  // Resolve an uncertain accepted write before attempting a newer payload.
  // Reusing its exact version/body lets the server recognize a lost-ack retry.
  const attempt=uncertainWrite?.id===id?uncertainWrite:{id,version,workspace:clone(workspace),serialized};
  const draftId=attempt.id,draftVersion=attempt.version;
  writing=(async()=>{
   try{const r=await request('/'+draftId,{method:'PUT',body:JSON.stringify({version:draftVersion,workspace:attempt.workspace})});if(id!==draftId)return true;if(!Number.isInteger(r?.version)||r.version!==draftVersion+1||!Number.isFinite(r.expires_at))throw new Error('Recovery acknowledgement unavailable');version=r.version;ack=attempt.serialized;uncertainWrite=null;lastError=null;if(JSON.stringify(capture())===ack)say('Recovery copy saved for 24 hours.');else if(!lastError)say('Changes have not reached the server yet. Keep this tab open.',true);return true}
   catch(e){if(id===draftId&&!(e.status>=400&&e.status<500))uncertainWrite=attempt;lastError=e;say('Changes have not reached the server. '+e.message+' Keep this tab open.',true);return false}
  })();
  let ok;try{ok=await writing}finally{writing=null}
  if(ok&&id===draftId&&JSON.stringify(capture())!==ack)return flush(duringRestore);
  return ok;
 }
 function newDraft(){id=uuid();version=0;ack='';ended=false;uncertainWrite=null}
 async function restore(row){
  if(busy)return false;
  busy=true;let restoredValues=null,stagedImagery=null,cancelled=false;
  const applyValues=()=>{if(restoredValues)fields.forEach(k=>{const n=el(k);if(n&&k in restoredValues){if(n.type==='checkbox')n.checked=restoredValues[k];else n.value=restoredValues[k]}})};
  try{
   loading.showModal();el('workspaceRecoveryLoadingTitle').focus();
   if(capture()&&!await flush(true))throw new Error('Current work has not reached recovery storage. Keep this tab open before restoring another draft.');
   const d=await request('/'+row.draft_id),w=d.workspace;
   const imagery=w.sessionToken?await request('/'+row.draft_id+'/imagery-session',{method:'POST',body:'{}'}):null;
   if(imagery)stagedImagery=await prepareRecoveryImagery(imagery);
   // Read the retained workspace only after ownership and imagery metadata checks.
   resetMeasurementForNewProperty();
   restoreSavedQuoteFields({address:w.values.address||''},w.quote,{});
   restoredValues=w.values;applyValues();
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
   if(stagedImagery){installPropertyImagery(stagedImagery);stagedImagery=null}
   // Aerial loading initializes its own source defaults; recovery owns the retained source and rates.
   applyValues();
   renderSummary();
   const sourceId=row.draft_id;newDraft();paused=false;
   say('Draft restored. Review your measurements, then create the estimate when ready.');
   if(!await flush(true))return false;
   const cleanup=await request('/'+sourceId,{method:'DELETE',body:JSON.stringify({version:d.version})});
   if(!cleanup.deleted)say('Recovery copy saved for 24 hours. Newer work from another tab was kept separately.');
   return true;
  }catch(e){
   // An imagery failure must not leave loader defaults in the retained fields.
   applyValues();if(restoredValues)renderSummary();
   if(e.code==='recovery_cancelled'){cancelled=true;paused=false;document.getElementById('workspaceRecoveryChoices')?.remove();say('Recovery stopped. Current work is unchanged. The server draft is kept; reload to restore it later.');return false}
   say('Draft could not be restored. '+e.message+' Retry Restore; the server copy is retained.',true);return false;
  }finally{if(stagedImagery)releaseRecoveryImagery(stagedImagery);busy=false;if(loading.open)loading.close();if(cancelled)focusWorkspace()}
 }
 const focusWorkspace=()=>{const target=el('streetAddress')||el('address');if(target)target.focus()};
 const separateLabel=()=>structures.some(roof=>roof.manually_measured)||manualPlanes.length||tracePoints.length
  ?'Keep working on this estimate':'Start a separate draft';
 async function choose(){
  try{
   const data=await request('');
   const clockOffset=Number.isFinite(data.server_time)?data.server_time*1000-Date.now():0;
   const expired=row=>Number.isFinite(row.expires_at)&&row.expires_at*1000<=Date.now()+clockOffset;
   data.drafts=data.drafts.filter(row=>!expired(row));
   if(!data.drafts.length){paused=false;say('Recovery autosave is ready.');return}
   const panel=document.createElement('section');panel.id='workspaceRecoveryChoices';panel.setAttribute('aria-labelledby','workspaceRecoveryHeading');
   panel.style.cssText='margin:0 16px 12px;padding:12px;border:1px solid #bdcbd8;border-radius:10px;background:#f8fafc;scroll-margin-top:16px';
   const title=document.createElement('h2');title.id='workspaceRecoveryHeading';title.tabIndex=-1;title.textContent='Unsaved draft found';title.style.cssText='margin:0 0 8px;font-size:1rem';panel.append(title);
   const choices=[];
   const finishChoices=message=>{if(panel.children.length===2){panel.remove();pruneRecoveryChoices=()=>{};paused=false;say(message)}};
   pruneRecoveryChoices=()=>{if(busy)return;for(const choice of choices){if(expired(choice.row))choice.line.remove()}finishChoices('The listed recovery windows ended. Current work is unchanged.');};
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
    label.id='workspaceRecoveryLabel-'+choices.length;
    const yes=document.createElement('button');yes.textContent='Restore';yes.setAttribute('aria-describedby',label.id);
    const no=document.createElement('button');no.textContent='Discard';no.setAttribute('aria-describedby',label.id);no.style.cssText='background:white;color:#9b2226;border:1px solid #9b2226';
    yes.style.cssText='background:white;color:#16457b;border:1px solid #16457b';
    const actionStatus=document.createElement('span');actionStatus.setAttribute('role','status');actionStatus.style.cssText='flex-basis:100%;color:#9b2226';
    yes.onclick=async()=>{if(busy)return;pruneRecoveryChoices();if(expired(row))return;yes.disabled=true;const ok=await restore(row);yes.disabled=false;if(ok){panel.remove();pruneRecoveryChoices=()=>{};focusWorkspace()}};
    no.onclick=async()=>{
     if(busy)return;pruneRecoveryChoices();if(expired(row))return;
     no.disabled=true;yes.disabled=true;actionStatus.textContent='Discarding this recovery draft…';
     try{
      const result=await request('/'+row.draft_id,{method:'DELETE',body:JSON.stringify({version:row.version,intent:'discard'})});
      if(result.deleted!==true)throw new Error('The server did not confirm discard. The draft is kept.');
      line.remove();finishChoices('Recovery draft discarded. Current work is unchanged.');
      if(panel.isConnected)panel.querySelector('button:not([disabled])')?.focus();else focusWorkspace();
     }catch(e){
      actionStatus.textContent='Draft was not discarded. '+e.message+' Current work is unchanged.';
      if(e.code==='draft_changed'){
       try{const latest=await request('/'+row.draft_id);row.version=latest.version;row.expires_at=latest.expires_at;const address=latest.workspace?.values?.address||latest.workspace?.values?.streetAddress||'Recovery draft';label.textContent=address+' · Expires '+new Date(row.expires_at*1000).toLocaleString();actionStatus.textContent+=' Its saved version was refreshed. Review it before retrying Discard.'}catch(_){}
      }
     }finally{no.disabled=false;yes.disabled=false}
    };
    line.append(label,yes,no,actionStatus);panel.append(line);choices.push({row,line});
   }
   const fresh=document.createElement('button');fresh.id='workspaceRecoveryContinue';fresh.textContent=separateLabel();
   fresh.onclick=()=>{if(busy)return;panel.remove();pruneRecoveryChoices=()=>{};paused=false;say('Separate recovery draft ready.');flush();};panel.append(fresh);
   const steps=document.getElementById('progress1')?.closest('.stepbar');
   if(steps)steps.before(panel);else badge.after(panel);
   say('');
  }catch(e){paused=false;say('Recovery storage is unavailable. Changes have not reached the server. Keep this tab open.',true)}
 }
 async function prepareSave(){
  lastError=null;
  if(busy){lastError=Object.assign(new Error('Draft recovery is still loading. Wait for it to finish before saving.'),{status:428});return false}
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
  if(busy)return;
  try{const w=capture();if(!w||JSON.stringify(w)===ack)return}catch(e){}
  if(!lastError)say('Changes have not reached the server yet. Keep this tab open.',true);clearTimeout(debounce);debounce=setTimeout(flush,700);
 }
 document.addEventListener('input',()=>{touched=true;changed()});
 const priorSummary=renderSummary;renderSummary=function(){const result=priorSummary.apply(this,arguments);changed();return result};
 setInterval(()=>{pruneRecoveryChoices();if(!busy)flush()},1800);
 document.addEventListener('visibilitychange',()=>{pruneRecoveryChoices();if(document.visibilityState==='hidden')flush()});
 window.addEventListener('pageshow',()=>pruneRecoveryChoices());
 window.addEventListener('online',flush);
 choose();
})();
