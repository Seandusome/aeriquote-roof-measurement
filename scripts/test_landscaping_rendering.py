"""Check shipped JavaScript syntax and saved-aerial request geometry without API charges."""
import ast
import math
from pathlib import Path
import re
import subprocess
import tempfile
from types import SimpleNamespace
import urllib.request
import urllib.parse
from unittest.mock import patch

source = Path('app.py').read_text()
module = ast.parse(source)
html = next(ast.literal_eval(n.value) for n in module.body if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == 'HTML' for t in n.targets))
with tempfile.TemporaryDirectory() as d:
    for i, js in enumerate(re.findall(r'<script[^>]*>(.*?)</script>', html, re.S)):
        p = Path(d) / f'script-{i}.js'
        p.write_text(js)
        subprocess.run(['node', '--check', str(p)], check=True)
print('PASS: all shipped inline JavaScript parses')

fn = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == 'saved_estimate_report_map')
fn.decorator_list = []
areas = [{'kind': 'area', 'points': [{'lat': 52, 'lng': -106}, {'lat': 52, 'lng': -105.99}, {'lat': 52.01, 'lng': -105.99}]},
         {'kind': 'area', 'points': [{'lat': 52.02, 'lng': -106}, {'lat': 52.02, 'lng': -105.99}, {'lat': 52.03, 'lng': -105.99}]},
         {'kind': 'linear', 'points': [{'lat': 52, 'lng': -106}, {'lat': 52.03, 'lng': -106}]}]
request = SimpleNamespace(get_json=lambda **kw: {'roofs': areas}, host_url='https://test.invalid/')
scope = dict(GOOGLE_MAPS_API_KEY='test-key', request=request, math=math, urllib=urllib,
             Response=lambda body, **kw: (body, kw))
exec(compile(ast.Module(body=[fn], type_ignores=[]), 'app.py', 'exec'), scope)
class ImageResponse:
    headers = {'Content-Type': 'image/png'}
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self): return b'test-image'
with patch('urllib.request.urlopen', return_value=ImageResponse()) as get:
    body, meta = scope['saved_estimate_report_map']()
    assert body == b'test-image', (body, meta)
    params = urllib.parse.parse_qs(urllib.parse.urlparse(get.call_args.args[0].full_url).query)
    assert len(params['path']) == 3
    assert int(params['zoom'][0]) < 18, 'Large landscaping properties must fit the image'
    assert params['path'][2].endswith('52.0300000,-106.0000000'), 'Linear trace must stay open'
    assert '52.0000000,-106.0000000' in params['path'][0]
print('PASS: saved aerial includes both areas and open linear trace; large-property framing')
