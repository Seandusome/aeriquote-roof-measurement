/* Image preparation never acknowledges, saves or replaces a workspace until accepted. */
let estimateImageryAttempt=null,reportImageryHistorical=false;
function disposeEstimateImagery(ready){
 if(!ready?.layer)return;
 const layers=ready.layer.getLayers?ready.layer.getLayers():[ready.layer];
 ready.layer.remove();layers.forEach(layer=>{if(String(layer._url||'').startsWith('blob:'))URL.revokeObjectURL(layer._url)});
}
function estimateImageryControls(){
 let box=el('estimateImageryStatus');if(box)return box;
 box=document.createElement('div');box.id='estimateImageryStatus';box.className='warning estimateImageryActions';box.hidden=true;box.setAttribute('data-html2canvas-ignore','true');
 box.innerHTML='<p id="estimateImageryMessage" role="status" aria-live="polite" tabindex="-1" style="margin:0 0 10px"></p><button type="button" id="retryEstimateImage">RETRY IMAGE</button> <button type="button" id="leaveSavedEstimate">BACK TO PREVIOUS ESTIMATES</button>';
 el('backToDealerBtn').closest('.reportActions').before(box);
 el('retryEstimateImage').onclick=()=>retryEstimateImage();el('leaveSavedEstimate').onclick=()=>{
  estimateImageryAttempt?.cancel();document.body.classList.remove('report-open');el('reportOverlay').style.display='none';openEstimateHistory();
 };
 return box;
}
function estimateImageryMessage(text,retry=false){
 const box=estimateImageryControls();box.hidden=!text;el('estimateImageryMessage').textContent=text;
 el('retryEstimateImage').hidden=!retry;el('leaveSavedEstimate').hidden=!savedEstimateEditContext;
}
function startEstimateImagery(title,opener){
 estimateImageryAttempt?.cancel();
 const controller=new AbortController(),dialog=document.createElement('dialog');dialog.id='estimateImageryLoading';
 dialog.setAttribute('aria-labelledby','estimateImageryLoadingTitle');dialog.setAttribute('aria-describedby','estimateImageryLoadingHelp');
 dialog.style.cssText='max-width:520px;width:90%;box-sizing:border-box;border:2px solid #175bba;border-radius:12px;padding:20px;color:#173b24;background:#fff';
 dialog.innerHTML='<h2 id="estimateImageryLoadingTitle"></h2><p id="estimateImageryLoadingHelp">Waiting up to 25 seconds. Your measurements, pitch, prices and customer details are retained.</p><button type="button" id="keepEstimateWork">Keep current work</button>';
 dialog.querySelector('h2').textContent=title;document.body.append(dialog);
 let rejectStop,timer,active=true;
 const stopped=new Promise((resolve,reject)=>{rejectStop=reject});
 const attempt={signal:controller.signal,check(){if(!active||estimateImageryAttempt!==attempt)throw new Error('Image loading stopped. Your work is retained.');},cancel(){
  if(!active)return;active=false;controller.abort();rejectStop(new Error('Image loading stopped. Your work is retained. Retry when ready.'));
 },async wait(pending){return Promise.race([pending,stopped])},finish(){
  active=false;controller.abort();clearTimeout(timer);dialog.close();dialog.remove();if(estimateImageryAttempt===attempt)estimateImageryAttempt=null;
  if(opener?.isConnected&&!opener.closest('[hidden]'))opener.focus();else if(document.body.classList.contains('report-open'))el('backToDealerBtn')?.focus();
 }};
 estimateImageryAttempt=attempt;
 timer=setTimeout(()=>{if(active){active=false;controller.abort();rejectStop(new Error('Image loading timed out. Your work is retained. Retry when ready.'));}},25000);
 dialog.addEventListener('cancel',event=>{event.preventDefault();attempt.cancel()});dialog.querySelector('button').onclick=()=>attempt.cancel();dialog.showModal();dialog.querySelector('button').focus();
 return attempt;
}
async function renderEstimateAerial(url,body,original,attempt){
 const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:attempt?.signal});
 // A long-lived browser may outlive its short-lived imagery session. Use the
 // frozen geometry route, with the same account checks, rather than remeasuring.
 if(r.status===404&&url.startsWith('/manual-report-map/'))return buildSavedHistoricalSnapshot(attempt,original);
 if(!r.ok)throw new Error('Property imagery is unavailable. Your saved measurement and estimate are retained.');
 const view=JSON.parse(r.headers.get('X-AeriQuote-Map-View')||'null');
 if(!view||![view.latitude,view.longitude,view.zoom,view.width,view.height].every(Number.isFinite)||view.width<=0||view.height<=0)throw new Error('Property image coordinates are unavailable. Your work is retained.');
 const blob=await r.blob(),obj=URL.createObjectURL(blob);
 try{
  const img=await new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(new Error('Property image could not be decoded. Your work is retained.'));im.src=obj});
  attempt?.check();
  const canvas=document.createElement('canvas');canvas.width=img.naturalWidth||1280;canvas.height=img.naturalHeight||840;
  Object.assign(canvas.style,{width:'auto',height:'auto',maxWidth:'100%',maxHeight:'100%',flex:'none',display:'block'});
  canvas.dataset.diagramScope=savedDiagramFingerprint(original);canvas.dataset.mapView=JSON.stringify(view);
  const ctx=canvas.getContext('2d');ctx.drawImage(img,0,0,canvas.width,canvas.height);canvas.dataset.labelBoxes=JSON.stringify(drawSavedMeasurementLabels(ctx,original,view,canvas.width,canvas.height));
  attempt?.check();const host=el('customerMap');
  if(customerMap){customerMap.remove();customerMap=null}customerRgbLayer=null;customerOverlays=[];
  host.replaceChildren(canvas);Object.assign(host.style,{position:'relative',overflow:'hidden',display:'flex',alignItems:'center',justifyContent:'center'});fitReportCanvas(host,canvas);el('customerMapPlaceholder').style.display='none';
 }finally{URL.revokeObjectURL(obj)}
}
async function retryEstimateImage(){
 if(estimateImageryAttempt)return;
 const opener=el('retryEstimateImage'),attempt=startEstimateImagery('Loading estimate image',opener);
 estimateImageryMessage('Loading the image. The estimate is already saved.');
 try{
  const useAerial=(el('streetViewChoice')?.value||'auto')!=='none';
  await attempt.wait(!useAerial?Promise.resolve(buildSavedRoofOutlineSnapshot()):reportImageryHistorical?buildSavedHistoricalSnapshot(attempt):buildCustomerMap(attempt));
  attempt.check();estimateImageryMessage('');
 }catch(e){
  // Never display a stale image as if it belonged to the current report.
  el('customerMap').style.display='none';el('customerMapPlaceholder').style.display='flex';el('customerMapPlaceholder').textContent='Property image unavailable. Saved measurements and pricing are retained.';
  estimateImageryMessage((e.name==='AbortError'?'Image loading stopped. Your work is retained.':e.message)+' Retry the image or return without saving again.',true);
 }finally{attempt.finish()}
}
async function stageSavedEditorImagery(d,attempt){
 const host=document.createElement('div');host.style.cssText='position:fixed;left:-20000px;top:0;width:900px;height:650px';document.body.append(host);
 const staging=L.map(host,{zoomControl:false,attributionControl:false,zoomAnimation:false});staging.setView([d.center.latitude,d.center.longitude],18);
 try{
  const ready=d.provider==='mapbox'?await preparePropertyImagery(d):await loadStandardWideAerial(d.token,staging,true,L.latLng(d.center.latitude,d.center.longitude),attempt.signal);
  if(d.provider!=='mapbox'){
   const layers=ready.layer.getLayers?ready.layer.getLayers():[ready.layer];layers.forEach(layer=>layer.off('remove'));staging.removeLayer(ready.layer);layers.forEach(layer=>layer.once('remove',()=>URL.revokeObjectURL(layer._url)));
  }
  try{attempt.check()}catch(e){disposeEstimateImagery(ready);throw e}return ready;
 }finally{staging.remove();host.remove()}
}
