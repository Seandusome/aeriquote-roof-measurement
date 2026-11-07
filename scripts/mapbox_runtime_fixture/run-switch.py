import os
from collections import Counter
from flask import jsonify, request, Response
import app as m
from mapbox_cutover_qa import AddressCandidate, ProviderSettings

original_html=m.HTML
original_lookup=m.perform_property_lookup
provider=ProviderSettings()
calls=Counter()
candidate=AddressCandidate.from_mapbox({
 'geometry':{'coordinates':[-114.029064,50.88856]},
 'properties':{'full_address':'218 Chaparral Way SE, Calgary, AB','feature_type':'address',
 'coordinates':{'accuracy':'rooftop'},'match_code':{'street':'unmatched','address_number':'matched','confidence':'high'}}})

def fixture_lookup(d):
 if provider.address=='google':
  return original_lookup(d)
 calls['Mapbox geocoding fixture']+=1
 token=m.create_session('',candidate.latitude,candidate.longitude,mode='manual_roof_static',formatted_address=candidate.label)
 return jsonify(provider='mapbox',token=token,manual_roof_only=True,fallback=True,
   center=dict(latitude=candidate.latitude,longitude=candidate.longitude),
   formatted_address=candidate.label,warnings=candidate.warnings,parts={})

def fallback(token):
 if provider.aerial!='mapbox':return m.fallback_map(token)
 if not m.SESSIONS.get(token):return Response('Session expired',status=404)
 calls['Mapbox imagery fixture']+=1
 return m.send_from_directory('/tmp/aq-mapbox-runtime','qa-grid.png')

m.perform_property_lookup=fixture_lookup
m.app.view_functions['fallback_map']=fallback
m.app.view_functions['fallback_meta']=lambda token: (jsonify(latitude=candidate.latitude,longitude=candidate.longitude,zoom=19,width=640,height=640) if provider.aerial=='mapbox' and m.SESSIONS.get(token) else m.fallback_meta(token))
@m.app.post('/qa-provider')
def switch():
 global provider
 mode=request.json['mode']
 provider=ProviderSettings('mapbox','mapbox','none') if mode=='mapbox' else ProviderSettings()
 m.GOOGLE_MAPS_API_KEY='' if mode=='mapbox' else 'google-fixture-only'
 m.HTML=original_html.replace('<body>','<body><script>window.aqLocalMapbox=true</script>',1) if mode=='mapbox' else original_html
 return jsonify(settings=provider.__dict__,google_key_available=bool(m.GOOGLE_MAPS_API_KEY))
@m.app.get('/qa-provider-counts')
def provider_counts():return jsonify(calls)
exec(open('runqa.py').read().replace('port=8880','port=8881'))
