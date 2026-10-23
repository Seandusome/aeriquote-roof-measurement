from pathlib import Path
import sys,json
from model import load,validate,quantities,price,ROOT
output=Path(sys.argv[1]);output.mkdir(parents=True,exist_ok=True);data=validate(load());p=price(data)
summary={'planes':quantities(data),'total':str(p['total'])}
html=(ROOT/'demo.template.html').read_text().replace('__FIXTURE__',json.dumps(data)).replace('__SUMMARY__',json.dumps(summary))
(output/'Contractor_Confirmation_Demo.html').write_text(html)
