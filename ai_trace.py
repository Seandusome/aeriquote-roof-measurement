"""Optional shared AI boundary suggestions. Geometry and final pricing stay in AeriQuote."""
import base64
import json
import math
import os
import urllib.request
import urllib.error

SURFACES = {'lawn', 'paved'}

class ProviderError(RuntimeError):
    pass

def provider():
    return os.environ.get('AERIQUOTE_AI_TRACE_PROVIDER', 'fal').strip().lower()

def configured():
    name = provider()
    return name in {'fal', 'openai'} and bool(os.environ.get('FAL_KEY' if name == 'fal' else 'OPENAI_API_KEY', '').strip())

def pixel_to_latlng(x, y, lat, lng, zoom):
    scale = 256 * 2 ** zoom
    sin = math.sin(math.radians(lat))
    cx = (lng + 180) / 360 * scale
    cy = (.5 - math.log((1 + sin) / (1 - sin)) / (4 * math.pi)) * scale
    px, py = cx + (x - .5) * 640, cy + (y - .5) * 640
    return [math.degrees(math.atan(math.sinh(math.pi - 2 * math.pi * py / scale))), px / scale * 360 - 180]

def validate_polygons(payload, lat, lng, zoom):
    if not isinstance(payload, dict):
        raise ValueError('Invalid AI suggestions')
    polygons = payload.get('polygons')
    if not isinstance(polygons, list) or len(polygons) > 6:
        raise ValueError('Invalid AI suggestions')
    result = []
    for polygon in polygons:
        if not isinstance(polygon, dict):
            raise ValueError('Invalid AI outline')
        points = polygon.get('points')
        if not isinstance(points, list) or not 3 <= len(points) <= 40:
            raise ValueError('Invalid AI outline')
        xy = []
        for point in points:
            if not isinstance(point, dict):
                raise ValueError('Invalid AI corner')
            x, y = point.get('x'), point.get('y')
            if isinstance(x, bool) or isinstance(y, bool) or not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                raise ValueError('Invalid AI corner')
            if not math.isfinite(x) or not math.isfinite(y) or not 0 <= x <= 1 or not 0 <= y <= 1:
                raise ValueError('AI outline is outside the image')
            xy.append((x, y))
        if xy[0] == xy[-1]:
            xy.pop()
        if len(set(xy)) != len(xy) or len(xy) < 3:
            raise ValueError('Duplicate AI corners')
        def orient(a, b, c):
            return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
        for i in range(len(xy)):
            for j in range(i+1, len(xy)):
                if j == i+1 or (i == 0 and j == len(xy)-1):
                    continue
                a,b,c,d = xy[i],xy[(i+1)%len(xy)],xy[j],xy[(j+1)%len(xy)]
                if orient(a,b,c)*orient(a,b,d) <= 0 and orient(c,d,a)*orient(c,d,b) <= 0:
                    if max(min(a[0],b[0]),min(c[0],d[0])) <= min(max(a[0],b[0]),max(c[0],d[0])) and max(min(a[1],b[1]),min(c[1],d[1])) <= min(max(a[1],b[1]),max(c[1],d[1])):
                        raise ValueError('AI outline crosses itself')
        area = abs(sum(xy[i][0]*xy[(i+1)%len(xy)][1]-xy[(i+1)%len(xy)][0]*xy[i][1] for i in range(len(xy)))) / 2
        if area < .00001:
            raise ValueError('AI outline is too small')
        result.append({'name': str(polygon.get('name') or 'AI suggested area')[:80],
                       'image_points': [[x*640,y*640] for x,y in xy],
                       'points': [pixel_to_latlng(x,y,lat,lng,zoom) for x,y in xy]})
    return result

def validate_scope(scope):
    if not isinstance(scope,list) or len(scope)!=4 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in scope):
        raise ValueError('Set a valid job boundary before AI tracing.')
    x0,y0,x1,y1=scope
    if not (0<=x0<x1<=1 and 0<=y0<y1<=1 and x1-x0>=.005 and y1-y0>=.005):
        raise ValueError('Set a valid job boundary before AI tracing.')
    return scope

def suggest(image, lat, lng, zoom, surface, scope=None):
    if provider() == 'fal':
        import sam_trace
        return sam_trace.suggest(image, lat, lng, zoom, surface, scope=scope)
    if provider() == 'openai':
        drafts, usage = suggest_openai(image, lat, lng, zoom, surface)
        if scope is not None:
            validate_scope(scope)
            x0,y0,x1,y1=scope
            kept=[a for a in drafts if all(x0*640<=p[0]<=x1*640 and y0*640<=p[1]<=y1*640 for p in a['image_points'])]
            usage={**usage,'rejected_regions':len(drafts)-len(kept)}
            drafts=kept
        return drafts, usage
    raise ProviderError('Unknown AI tracing provider. Check AERIQUOTE_AI_TRACE_PROVIDER.')

def suggest_openai(image, lat, lng, zoom, surface):
    key = os.environ.get('OPENAI_API_KEY', '').strip()
    if not key:
        raise RuntimeError('AI tracing is not configured')
    if surface not in SURFACES:
        raise ValueError('Choose Lawn or Paved Surface')
    schema = {'type':'object','additionalProperties':False,'required':['polygons'],
              'properties':{'polygons':{'type':'array','items':{'type':'object','additionalProperties':False,
              'required':['name','points'],'properties':{'name':{'type':'string'},'points':{'type':'array',
              'items':{'type':'object','additionalProperties':False,'required':['x','y'],
              'properties':{'x':{'type':'number'},'y':{'type':'number'}}}}}}}}}
    prompt = ('Suggest visible '+('grass/turf' if surface=='lawn' else 'asphalt or concrete')+
              ' boundaries for the surface centered in this 640x640 satellite image. Return up to 6 simple polygons, '
              '3 to 40 corners each, excluding buildings, trees, roads, cars and unrelated neighboring properties. '
              'Do not infer legal property lines or hidden boundaries. If unsure, return an empty polygons list. '
              'For surfaces with holes, use separate simple sections; never include the hole in measured area. '
              'Coordinates must be normalized image positions: x=0 left, x=1 right, y=0 top, y=1 bottom. '
              'Do not repeat the first point. These are draft suggestions for human review, not certified measurements.')
    body = {'model':os.environ.get('AERIQUOTE_AI_TRACE_MODEL','gpt-4.1-2025-04-14'), 'store':False,
            'max_output_tokens':3000,'input':[{'role':'user','content':[{'type':'input_text','text':prompt},
            {'type':'input_image','detail':'high','image_url':'data:image/png;base64,'+base64.b64encode(image).decode()}]}],
            'text':{'format':{'type':'json_schema','name':'surface_outlines','strict':True,'schema':schema}}}
    req = urllib.request.Request('https://api.openai.com/v1/responses', data=json.dumps(body).encode(),
                                 headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            data = json.loads(response.read())
    except urllib.error.HTTPError as error:
        code = ''; error_type = ''
        try:
            detail = json.loads(error.read(65536)).get('error', {})
            code = detail.get('code', ''); error_type = detail.get('type', '')
        except Exception:
            pass
        if code == 'credit_balance_exhausted':
            message = 'OpenAI API credit balance is exhausted. Check API billing and available credits before tracing again.'
        elif code == 'project_spend_limit_exceeded':
            message = 'The OpenAI API project spending limit has been reached. Check the limits for the project that owns this key.'
        elif code == 'organization_spend_limit_exceeded':
            message = 'The OpenAI API organization spending limit has been reached. Check organization billing limits.'
        elif code == 'organization_usage_limit_exceeded':
            message = 'The OpenAI API organization usage limit has been reached. Check the approved usage limit in OpenAI settings.'
        elif code == 'insufficient_quota' or error_type == 'insufficient_quota':
            message = 'OpenAI API credits are unavailable. Check API billing and available credits for the project that owns this key.'
        elif error.code == 401:
            message = 'OpenAI rejected the API key. Check OPENAI_API_KEY in the test service environment.'
        elif error.code == 429:
            message = 'OpenAI rate limit reached. Check the tracing model request and token limits in the API project. Waiting will not help if one trace exceeds those limits.'
        elif error.code == 403:
            message = 'This OpenAI project does not have access to the tracing model. Check project permissions.'
        else:
            message = 'OpenAI could not process the tracing request (HTTP '+str(error.code)+').'
        raise ProviderError(message) from None
    except (TimeoutError, urllib.error.URLError):
        raise ProviderError('The OpenAI tracing request timed out or could not connect. Try again shortly.') from None
    if data.get('status') != 'completed':
        raise ValueError('AI tracing did not complete')
    text = ''.join(part.get('text','') for output in data.get('output',[]) if output.get('type')=='message'
                   for part in output.get('content',[]) if part.get('type')=='output_text')
    return validate_polygons(json.loads(text),lat,lng,zoom), data.get('usage',{})

def image_preview(image):
    return 'data:image/png;base64,' + base64.b64encode(image).decode()
