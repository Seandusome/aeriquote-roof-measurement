"""Disposable loopback existing-job fixture using normal paid allowance rules."""
import fresh_user_browser_server as fixture
import io,math
from urllib.parse import urlparse,parse_qs

a=fixture.a
con=fixture.disposable_db()
con.execute("UPDATE dealers SET plan_code='basic',lookup_limit=25,estimate_limit=25 WHERE id='qa-browser'")
con.execute("UPDATE account_allowances SET complimentary=0 WHERE dealer_id='qa-browser'")
con.commit();con.close()
def fictional_property(d):
 response=fixture.fixture.fixture(d);body=response.get_json();body['formatted_address']=d.get('address') or '1 Fictional QA Street, Saskatoon, SK, Canada'
 a.SESSIONS[body['token']]['formatted_address']=body['formatted_address']
 return a.jsonify(body)
a.perform_property_lookup=fictional_property

# Exercise the real report-map endpoints and their Static Maps path generation.
# Only the external provider bytes are replaced; unexpected requests still fail.
def synthetic_static_map(req,timeout=None):
 parsed=urlparse(req.full_url);assert parsed.netloc=='maps.googleapis.com' and parsed.path=='/maps/api/staticmap'
 args=parse_qs(parsed.query);assert args['key']==['qa-placeholder']
 width,height=map(int,args['size'][0].split('x'));scale=int(args['scale'][0]);zoom=int(args['zoom'][0]);lat,lng=map(float,args['center'][0].split(','))
 def xy(lat,lng):return ((lng+180)/360,.5-math.log((1+math.sin(math.radians(lat)))/(1-math.sin(math.radians(lat))))/(4*math.pi))
 cx,cy=xy(lat,lng);shapes=[]
 for path in args.get('path',[]):
  parts=path.split('|');points=[tuple(map(float,p.split(','))) for p in parts if ',' in p];assert len(points)>=2
  color=next(p.split(':',1)[1] for p in parts if p.startswith('color:'));fill=next((p.split(':',1)[1] for p in parts if p.startswith('fillcolor:')),'0x00000000')
  pixel=[((x-cx)*256*2**zoom*scale+width*scale/2,(y-cy)*256*2**zoom*scale+height*scale/2) for x,y in [xy(*p) for p in points]]
  coords=' '.join(f'{x:.3f},{y:.3f}' for x,y in pixel)
  shapes.append(f'<polyline points="{coords}" stroke="#{color[2:8]}" stroke-width="{4*scale}" fill="#{fill[2:8]}" fill-opacity="{int(fill[8:10],16)/255}"/>')
 assert shapes
 svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="{width*scale}" height="{height*scale}"><defs><pattern id="g" width="80" height="80" patternUnits="userSpaceOnUse"><rect width="80" height="80" fill="#edf1ef" stroke="#bacbc6"/></pattern></defs><rect width="100%" height="100%" fill="url(#g)"/><text x="25" y="30">FICTIONAL QA PROVIDER - NOT REAL IMAGERY</text>'+''.join(shapes)+'</svg>'
 response=io.BytesIO(svg.encode());response.headers={'Content-Type':'image/svg+xml'};return response

a.urllib.request.urlopen=synthetic_static_map
if __name__=='__main__':a.app.run(host='127.0.0.1',port=8765,threaded=True,use_reloader=False)
