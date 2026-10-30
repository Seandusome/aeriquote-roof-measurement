"""Validate saved measurement snapshots independently of browser state (no GIS dependency)."""
import math

FT2 = 10.76391041671

def coordinates(points, minimum):
    if not isinstance(points, list) or len(points) < minimum:
        raise ValueError('Measurement outline is missing or incomplete. Remeasure before quoting.')
    result=[]
    for p in points:
        if isinstance(p,dict): p=[p.get('lat'),p.get('lng')]
        if not isinstance(p,(list,tuple)) or len(p)!=2 or any(isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) for v in p):
            raise ValueError('Measurement coordinates are invalid. Remeasure before quoting.')
        if abs(p[0])>90 or abs(p[1])>180:raise ValueError('Measurement coordinates are outside valid latitude/longitude ranges.')
        result.append(tuple(p))
    return result

def polygon_sqft(points):
    pts=coordinates(points,3)
    # Spherical trapezoids; independent of the client's projected shoelace calculation.
    area=0
    for (lat1,lon1),(lat2,lon2) in zip(pts,pts[1:]+pts[:1]):
        delta=math.radians((lon2-lon1+180)%360-180)
        area+=delta*(math.sin(math.radians(lat1))+math.sin(math.radians(lat2)))
    return abs(area)*6378137**2/2*FT2

def line_feet(points):
    pts=coordinates(points,2);total=0
    for (lat1,lon1),(lat2,lon2) in zip(pts,pts[1:]):
        a,b=math.radians(lat1),math.radians(lat2)
        h=math.sin((b-a)/2)**2+math.cos(a)*math.cos(b)*math.sin(math.radians(lon2-lon1)/2)**2
        total+=2*6371000*math.asin(min(1,math.sqrt(h)))/.3048
    return total

def linear_error(points):
    """Reject duplicated physical coverage, not ordinary intersections or closed loops."""
    pts=coordinates(points,2);lat,lon=pts[0];scale=6378137*math.pi/180
    xy=[(((b-lon+180)%360-180)*scale*math.cos(math.radians(lat)),(a-lat)*scale) for a,b in pts]
    segments=[]
    for a,b in zip(xy,xy[1:]):
        dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
        if length<.0003048:return 'The line has a zero-length edge. Move the repeated point or Undo.'
        for c,d in segments:
            if max(abs(dx*(p[1]-a[1])-dy*(p[0]-a[0]))/length for p in (c,d))>1e-6:continue
            lo,hi=sorted(((p[0]-a[0])*dx/length+(p[1]-a[1])*dy/length for p in (c,d)))
            if min(length,hi)-max(0,lo)>1e-6:return 'Linear segments overlap and count the same length twice. Correct the line before quoting.'
        segments.append((a,b))
    return ''

def planar(points):
    pts=coordinates(points,3);lat,lon=pts[0]
    scale=6378137*math.pi/180
    return [(((b-lon+180)%360-180)*scale*math.cos(math.radians(lat)),(a-lat)*scale) for a,b in pts]

def turn(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
def on(a,b,p):return abs(turn(a,b,p))<1e-6 and min(a[0],b[0])-1e-7<=p[0]<=max(a[0],b[0])+1e-7 and min(a[1],b[1])-1e-7<=p[1]<=max(a[1],b[1])+1e-7

def polygon_valid(points):
    xy=[]
    for point in planar(points):
        if not xy or point!=xy[-1]:xy.append(point)
    if xy[0]==xy[-1]:xy.pop()
    if len(xy)<3 or polygon_sqft(points)<.00001:return False
    for i,a in enumerate(xy):
        b=xy[(i+1)%len(xy)]
        for j in range(i+1,len(xy)):
            if j==i+1 or (i==0 and j==len(xy)-1):continue
            c,d=xy[j],xy[(j+1)%len(xy)]
            if (turn(a,b,c)*turn(a,b,d)<0 and turn(c,d,a)*turn(c,d,b)<0) or any((on(a,b,c),on(a,b,d),on(c,d,a),on(c,d,b))):return False
    return True

def polygons_overlap(first, second):
    # Translate both to the same local origin before testing; shared boundaries are allowed.
    origin=coordinates(first,3)[0];scale=6378137*math.pi/180
    def project(poly):return [(((lon-origin[1]+180)%360-180)*scale*math.cos(math.radians(origin[0])),(lat-origin[0])*scale) for lat,lon in coordinates(poly,3)]
    a,b=project(first),project(second)
    def inside(p,poly):
        if any(on(x,y,p) for x,y in zip(poly,poly[1:]+poly[:1])):return False
        hit=False
        for x,y in zip(poly,poly[1:]+poly[:1]):
            if (x[1]>p[1])!=(y[1]>p[1]) and p[0]<(y[0]-x[0])*(p[1]-x[1])/(y[1]-x[1])+x[0]:hit=not hit
        return hit
    for x,y in zip(a,a[1:]+a[:1]):
        for u,v in zip(b,b[1:]+b[:1]):
            if turn(x,y,u)*turn(x,y,v)<-1e-12 and turn(u,v,x)*turn(u,v,y)<-1e-12:return True
    for poly,other in ((a,b),(b,a)):
        candidates=poly+[((x[0]+y[0])/2,(x[1]+y[1])/2) for x,y in zip(poly,poly[1:]+poly[:1])]
        candidates.append((sum(x[0] for x in poly)/len(poly),sum(x[1] for x in poly)/len(poly)))
        for x,y in zip(poly,poly[1:]+poly[:1]):
            length=math.dist(x,y)
            if length:
                for side in (-1,1):
                    point=((x[0]+y[0])/2+side*(y[1]-x[1])/length*1e-5,(x[1]+y[1])/2-side*(y[0]-x[0])/length*1e-5)
                    if inside(point,poly):candidates.append(point)
        if any(inside(p,other) and (p in poly or inside(p,poly) or any(on(x,y,p) for x,y in zip(poly,poly[1:]+poly[:1]))) for p in candidates):return True
    return False

def snapshot_error(payload):
    quote=payload.get('quote')
    if not isinstance(quote,dict):return 'Save a complete measurement snapshot before creating an estimate.'
    try:
        areas=[a for a in quote.get('commercialAreas',[]) if a.get('sqft',0)>0]
        for area in areas:
            points=area.get('points')
            if not polygon_valid(points):return 'Saved service area outline is invalid. Remeasure before quoting.'
            measured=polygon_sqft(points)
            if abs(measured-float(area['sqft']))>max(1,measured*.001):return 'Saved service area quantity does not match its outline. Remeasure before quoting.'
        for i,area in enumerate(areas):
            if any(polygons_overlap(area['points'],other['points']) for other in areas[:i]):return 'Saved service areas overlap. Correct the outlines before quoting to avoid counting coverage twice.'
        if areas:
            expected=sum(float(a['sqft']) for a in areas)
            for value in (quote.get('areaSqFt'),payload.get('area_sqft'),payload.get('total_area')):
                if value is not None and abs(float(value)-expected)>.51:return 'Saved area totals do not match the included service areas.'
        elif quote.get('areaSqFt',0)>0:
            if not polygon_valid(quote.get('areaPoints')):return 'Saved area outline is invalid. Remeasure before quoting.'
            measured=polygon_sqft(quote['areaPoints'])
            if abs(measured-float(quote['areaSqFt']))>max(1,measured*.001):return 'Saved area quantity does not match its outline. Remeasure before quoting.'
        length=quote.get('linearFeet',0)
        if quote.get('linearPoints') and not length:return 'Saved linear quantity does not match its line. Remeasure before quoting.'
        if length>0:
            issue=linear_error(quote.get('linearPoints'))
            if issue:return issue
            measured=line_feet(quote.get('linearPoints'))
            if abs(measured-float(length))>max(.05,measured*.00001):return 'Saved linear quantity does not match its line. Remeasure before quoting.'
            if 'linear_feet' in payload and abs(float(payload['linear_feet'])-float(length))>.0001:return 'Saved linear totals do not match the included line.'
        planes=quote.get('manualPlanes',[])
        if not isinstance(planes,list):return 'Manual roof measurements must be a list.'
        for roof in planes+[r for r in quote.get('structures',[]) if r.get('manually_measured')]:
            if not isinstance(roof,dict):return 'Manual roof measurement is invalid.'
            is_structure='total_roof_sqft' in roof
            points=roof.get('outline') if is_structure else roof.get('points')
            pitch=(roof.get('segments') or [{}])[0].get('pitch_degrees') if is_structure else roof.get('pitch_degrees')
            quantity=roof.get('total_roof_sqft') if is_structure else roof.get('surface_sqft')
            if isinstance(pitch,bool) or not isinstance(pitch,(int,float)) or not math.isfinite(pitch) or not 0<=pitch<80:return 'Manual roof pitch is invalid. Remeasure before quoting.'
            if not polygon_valid(points):return 'Manual roof outline is incomplete or invalid.'
            actual=polygon_sqft(points)/math.cos(math.radians(pitch))
            if isinstance(quantity,bool) or not isinstance(quantity,(int,float)) or not math.isfinite(quantity) or abs(actual-quantity)>max(1,actual*.001):return 'Manual roof quantity does not match its outline and pitch.'
        if quote.get('businessType')=='roofing' and (quote.get('manualRoofWorkflow') or (quote.get('measurementMode')=='auto' and any(p.get('manual_roof_qa') for p in planes))):
            if quote.get('measurementMode')!='auto' or quote.get('structures') or quote.get('measureSource')!='manual':return 'Manual roofing sections must be priced as roof surface measurements.'
            if not planes or quote.get('roofScopeConfirmed') is not True:return 'Confirm all intended roof sections and buildings before quoting.'
            for i,roof in enumerate(planes):
                if roof.get('pitch_confirmed') is not True:return 'Confirm the pitch of every roof section.'
                if any(polygons_overlap(roof['points'],other['points']) for other in planes[:i]):return 'Manual roof sections overlap. Correct them before quoting.'
        if quote.get('businessType')=='roofing' and quote.get('measurementMode')=='auto':
            source=quote.get('measureSource','google')
            roofs=quote.get('structures',[])
            if any(not isinstance(r.get('total_roof_sqft'),(float,int)) or isinstance(r.get('total_roof_sqft'),bool) or not math.isfinite(r['total_roof_sqft']) or r['total_roof_sqft']<=0 for r in roofs):return 'Every included roof needs a valid measured area.'
            seen=set();seen_outlines=set();automatic_outlines=[]
            for roof in roofs:
                if roof.get('manually_measured'):continue
                if roof.get('building_id') and roof['building_id'] in seen:return 'The same automatic building is included more than once.'
                if roof.get('building_id'):seen.add(roof['building_id'])
                points=roof.get('outline')
                if not polygon_valid(points):return 'Automatic roof outline is missing or incomplete. Remeasure before quoting.'
                # Provider IDs may differ for the same roof. Vertex order, winding,
                # closing points and consecutive repeats do not make a new building.
                outline_key=frozenset(coordinates(points,3))
                if outline_key in seen_outlines:return 'The same automatic roof outline is included more than once. Remove the duplicate before quoting.'
                seen_outlines.add(outline_key)
                if any(polygons_overlap(points,other) for other in automatic_outlines):return 'Automatic roof outlines overlap. Correct the roof measurements before quoting to avoid counting coverage twice.'
                automatic_outlines.append(points)
                ground=float(roof.get('roof_ground_sqft') or 0);building=float(roof.get('building_ground_sqft') or 0);coverage=roof.get('roof_coverage_ratio')
                if not math.isfinite(ground) or ground<=0:return 'Automatic roof footprint is incomplete. Remeasure before quoting.'
                if coverage is not None and (not math.isfinite(float(coverage)) or float(coverage)<.95):return 'Automatic roof data covers only part of the building. Remeasure before quoting.'
                if not math.isfinite(building) or building<=0 or ground/building<.95:return 'Automatic roof data is missing building sections. Remeasure before quoting.'
                footprint=polygon_sqft(points)
                if not .75<=footprint/ground<=1.25 or roof['total_roof_sqft']<ground*.98:return 'Automatic roof area and outline cover different scopes. Remeasure before quoting.'
                segments=roof.get('segments')
                if not isinstance(segments,list) or not segments:return 'Automatic roof sections are missing. Remeasure before quoting.'
                for seg in segments:
                    pitch=seg.get('pitch_degrees');qty=seg.get('area_sqft')
                    if any(isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) for v in (pitch,qty)) or not 0<=pitch<80 or qty<=0:return 'Automatic roof section area or pitch is invalid.'
                section_area=sum(seg['area_sqft'] for seg in segments)
                section_ground=sum(seg['area_sqft']*math.cos(math.radians(seg['pitch_degrees'])) for seg in segments)
                if abs(section_area-roof['total_roof_sqft'])>max(1,roof['total_roof_sqft']*.01) or not .75<=section_ground/ground<=1.25:return 'Automatic roof sections do not match the complete roof area and pitch.'
            google=sum(r['total_roof_sqft'] for r in roofs);manual=sum(r['surface_sqft'] for r in planes)
            expected=google+manual if source=='hybrid' else (manual or google) if source=='manual' else google
            if source!='adjusted':
                for value in (payload.get('total_area'),payload.get('pricing',{}).get('area')):
                    if value is not None and abs(float(value)-expected)>.51:return 'Roof total does not match all included structures and manual roofs.'
        if not areas and not quote.get('areaSqFt',0) and not length and not quote.get('structures') and not quote.get('manualPlanes'):
            return 'Save a complete measurement before creating an estimate.'
    except (ValueError,TypeError,KeyError,OverflowError,AttributeError,IndexError):return 'Measurement snapshot is incomplete or invalid. Remeasure before quoting.'
    return ''
