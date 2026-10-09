from pathlib import Path
import ast
p=Path('app.py');s=p.read_text(encoding='utf-8')
def replace(a,b):
 global s
 if s.count(a)!=1:raise RuntimeError('Expected exactly one match: '+a[:90]+' found '+str(s.count(a)))
 s=s.replace(a,b,1)
replace('        if limit>0 and used>=limit:return False,used,limit','        if limit>0 and used>=limit and not is_head_office():return False,used,limit')
replace(" if(el('reportOutlineControls'))el('reportOutlineControls').style.display=useAerial?'flex':'none';if(useAerial)renderReportOutlineTargetButtons();"," if(el('reportOutlineControls'))el('reportOutlineControls').style.display=useAerial?'flex':'none';if(useAerial)renderReportOutlineTargetButtons();")
replace("if(snap.measurementMode==='area'&&Array.isArray(snap.areaPoints)&&snap.areaPoints.length>=3){if(el('reportOutlineControls'))el('reportOutlineControls').style.display='none';","if(snap.measurementMode==='area'&&Array.isArray(snap.areaPoints)&&snap.areaPoints.length>=3){if(el('reportOutlineControls'))el('reportOutlineControls').style.display='flex';renderReportOutlineTargetButtons();")
replace(" box.innerHTML=html||'<span class=\"small\">No roof outline available to edit.</span>';"," if(snap.measurementMode==='area'&&snap.areaPoints&&snap.areaPoints.length>=3){html='<button class=\"orange\" onclick=\"returnToAreaCorrection()\">CORRECT MEASUREMENT OUTLINE</button>';if(el('reportOutlineHelpTop'))el('reportOutlineHelpTop').textContent='Return to the measurement screen to adjust the saved area and update the price.';}\n box.innerHTML=html||'<span class=\"small\">No roof outline available to edit.</span>';")
replace('function renderReportOutlineTargetButtons(){','function returnToAreaCorrection(){document.body.classList.remove("report-open");if(el("reportOverlay"))el("reportOverlay").style.display="none";if(customerMap){try{customerMap.remove()}catch(e){}customerMap=null}customerRgbLayer=null;customerOverlays=[];if(typeof correctAreaOutline==="function")correctAreaOutline();if(el("areaTool"))el("areaTool").scrollIntoView({behavior:"smooth",block:"center"});}\nfunction renderReportOutlineTargetButtons(){')
ast.parse(s)
p.write_text(s,encoding='utf-8')
print('Validated app patch')
