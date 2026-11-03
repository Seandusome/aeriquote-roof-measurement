"""Actual JS calculator versus independent Decimal contract at nearby cent boundaries."""
import copy,json,subprocess,sys
from pathlib import Path
from decimal import Decimal
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pricing_integrity import calculate,pricing_error
rows=[]
for industry in ('roofing','snow','pressure','paving','landscaping','commercial'):
 for mode in ('regular','discount','included'):
  for tax in (0,5,6,7.25,12.5):
   for cents in range(36720,36741):
    amount=float(Decimal(cents)/100)
    quote=dict(businessType=industry,measurementMode='auto' if industry=='roofing' else 'area',measureSource='manual',manualPlanes=[dict(surface_sqft=1)],structures=[],areaSqFt=1,linearFeet=0,commercialAreas=[] if industry=='roofing' else [dict(sqft=1,rate=amount)])
    rows.append(dict(quote=quote,pricing=dict(price=amount,mode=mode,gst=tax,pst=6,disc=12.5,extraAmount=.005,extraDescription='FICTIONAL half-cent extra',estimatePeriod='one_time')))
# Exact original submitted payload, not an altered price/geometry fixture.
original=json.loads(Path('docs/qa/roofing-next-action-2026-11-03/after-phone-and-failure/390-save-requests.json').read_text())[-1]
rows.append(copy.deepcopy(original));original_index=len(rows)-1
# Decimal accumulation of individual roof sections, not a binary intermediate sum.
for quantities,rate in [([.1,.7],.04375),([.1,.2],.15),([.01,.02],.5)]:
 row=copy.deepcopy(original);row['quote'].update(manualPlanes=[dict(surface_sqft=x) for x in quantities],structures=[])
 row['pricing'].update(price=rate,gst=5,pst=6,extraAmount=0,extraDescription='',mode='regular');rows.append(row)
actual=json.loads(subprocess.check_output(['node','scripts/price_fixtures.cjs'],input=json.dumps(rows),text=True))
for index,row in enumerate(actual):
 expected=calculate(row)
 for key,value in expected.items():
  got=Decimal(str(row['pricing'][key]));tolerance=Decimal('.00001') if key=='area' else Decimal(0)
  assert abs(got-value)<=tolerance,(index,key,got,value)
 assert pricing_error(row)=='',(index,pricing_error(row))
fixed=actual[original_index]
assert (fixed['pricing']['taxBase'],fixed['pricing']['gstAmt'],fixed['total_price'])==(367.30,18.37,407.71)
assert original['pricing']['gstAmt']==18.36 and pricing_error(original),'Original rejected payload remains rejected; server validation unchanged'
print(f'PASS {len(actual)} actual-JS versus independent-Decimal cases: six industries, regular/discount/included, nearby tax boundaries, fractional extras and roof sums; original367.30 ->GST18.37 ->total407.71')
