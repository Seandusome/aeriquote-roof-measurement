"""Read-only preflight: verify complete current public-site package hashes."""
import hashlib
import json
from pathlib import Path
import sys

def inspect(site):
    site=Path(site);report={'schema':1,'missing':[],'changed':[],'invalid':[],'checked':0}
    try:
        manifest=json.loads((site/'public-package.json').read_text())
        assert manifest['schema']==1 and isinstance(manifest['files'],dict) and manifest['files']
        for name,expected in manifest['files'].items():
            if Path(name).is_absolute() or '..' in Path(name).parts:
                report['invalid'].append(name);continue
            file=site/name;report['checked']+=1
            if not file.is_file():report['missing'].append(name)
            elif hashlib.sha256(file.read_bytes()).hexdigest()!=expected:report['changed'].append(name)
    except (OSError,ValueError,KeyError,TypeError,AssertionError):report['invalid'].append('manifest missing or invalid')
    report['passed']=not any(report[k] for k in ('missing','changed','invalid'));return report

if __name__=='__main__':
    result=inspect(sys.argv[1] if len(sys.argv)>1 else Path(__file__).resolve().parents[1]/'site')
    print(json.dumps(result,indent=2));sys.exit(0 if result['passed'] else 1)
