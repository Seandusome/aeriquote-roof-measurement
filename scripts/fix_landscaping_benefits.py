from pathlib import Path
import ast
p=Path('app.py')
s=p.read_text(encoding='utf-8')
def replace_once(old,new):
    global s
    count=s.count(old)
    if count!=1: raise RuntimeError(f'Expected 1 match, got {count}: {old[:70]}')
    s=s.replace(old,new,1)
row='<div class="benefit-editor"><select id="benefitIcon6"><option value="✓">✓ Check</option><option value="★">★ Star</option><option value="$">$ Savings</option><option value="◆">◆ Diamond</option><option value="●">● Dot</option><option value="W">W Warranty</option></select><input id="benefitTitle6" placeholder="Benefit 6 headline"><input id="benefitText6" placeholder="Short description"></div>'
replace_once('<input id="benefitText5" placeholder="Short description"></div><div class="grid2"', '<input id="benefitText5" placeholder="Short description"></div>'+row+'<div class="grid2"')
s=s.replace('[1,2,3,4,5]','[1,2,3,4,5,6]')
replace_once("text:'Careful lawn and landscape work.'}]}}","text:'Careful lawn and landscape work.'},{icon:'★',title:'Reliable & Dependable Service',text:'Professional service from estimate through completion.'}]}}")
replace_once(":'Roof AutoMeasure is not included in this service-area quote.'",":currentBusinessType()==='landscaping'?'Only the measured landscaping area is included in this quote.':'Roof AutoMeasure is not included in this service-area quote.'")
helper="""function fillLandscapingBenefits(){if(currentBusinessType()!=='landscaping')return;const d=landscapingMarketingDefaults();const titles=[1,2,3,4,5,6].map(n=>(el('benefitTitle'+n)?.value||'').trim());const starter=titles[0]==='Landscape Care'&&titles.slice(1).every(v=>!v);const empty=titles.every(v=>!v);if(starter||empty){d.benefits.forEach((b,j)=>{const n=j+1;for(const [prefix,value] of [['benefitIcon',b.icon],['benefitTitle',b.title],['benefitText',b.text]]){const e=el(prefix+n);if(e)e.value=value}});if(starter&&el('marketingHeading')?.value==='WHY CHOOSE US')el('marketingHeading').value=d.heading;}else{d.benefits.forEach((b,j)=>{const n=j+1,t=el('benefitTitle'+n),x=el('benefitText'+n);if(t&&!t.value.trim()&&x&&!x.value.trim()){t.value=b.title;x.value=b.text;if(el('benefitIcon'+n))el('benefitIcon'+n).value=b.icon}})}}\n"""
replace_once('function businessTypeChanged()',helper+'function businessTypeChanged()')
replace_once('applySnowMarketingDefaultsIfNeeded(false);toggleMarketingEditor();pricingChanged();','applySnowMarketingDefaultsIfNeeded(false);fillLandscapingBenefits();toggleMarketingEditor();pricingChanged();')
replace_once('applySnowMarketingDefaultsIfNeeded(false);const enabled=','applySnowMarketingDefaultsIfNeeded(false);fillLandscapingBenefits();const enabled=')
replace_once('applySnowMarketingDefaultsIfNeeded(true);renderSummary()','applySnowMarketingDefaultsIfNeeded(true);fillLandscapingBenefits();renderSummary()')
replace_once('});applySnowMarketingDefaultsIfNeeded(false)}else if(el(\'price\')','});applySnowMarketingDefaultsIfNeeded(false);fillLandscapingBenefits()}else if(el(\'price\')')
ast.parse(s)
p.write_text(s,encoding='utf-8')
print('Six landscaping benefits patched; Python syntax valid')
