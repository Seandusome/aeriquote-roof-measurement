import app as m
from flask import jsonify
from urllib.parse import urlsplit, parse_qs
from pathlib import Path
from time import time
from io import BytesIO
records=[]
image=Path('qa-grid.png').read_bytes()
def event(service):records.append([int(time())//60,service])
def fixture_json(url):
 p=urlsplit(url)
 if p.path.endswith('/geocode/json'):
  event('Geocoding'); q=parse_qs(p.query).get('address',[''])[0]
  if 'Missing' in q:return 200,{'status':'ZERO_RESULTS'}
  components=[{'types':[k],'short_name':v,'long_name':v} for k,v in [('street_number','18'),('route','Fictional Roof Lane'),('locality','Calgary'),('administrative_area_level_1','AB')]]
  return 200,{'status':'OK','results':[{'address_components':components,'geometry':{'location':{'lat':51.,'lng':-114.}},'formatted_address':'18 Fictional Roof Lane, Calgary, AB'}]}
 if p.path.endswith('/streetview/metadata'):
  event('Street View metadata');return 200,{'status':'OK','pano_id':'fixture','location':{'lat':51.,'lng':-114.}}
 raise AssertionError(p.path)
def fixture_bytes(url,*a,**k):
 p=urlsplit(url).path
 assert p.endswith('/streetview'),p
 event('Street View image')
 return 'image/png',image
class Static(BytesIO):
 headers={'Content-Type':'image/png'}
def fixture_open(req,*a,**k):
 url=req if isinstance(req,str) else req.full_url
 p=urlsplit(url)
 assert p.path.endswith('/staticmap'),p.path
 event('Maps Static')
 return Static(image)
m.req_json=fixture_json;m.req_bytes=fixture_bytes;m.urllib.request.urlopen=fixture_open
m.app.view_functions['mapbox_test']=lambda:jsonify(status='safe')
m.manual_roof_qa_enabled=lambda:True
m.HTML=m.HTML.replace('<body>','<body><script>window.aqFictionalRoofSample=true</script>',1)
@m.app.get('/qa-meter')
def meter():return jsonify(records)
exec(open('runqa.py').read().replace('port=8880','port=8887'))
