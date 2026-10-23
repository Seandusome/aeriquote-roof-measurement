"""Standalone, deliberately limited QA gable fixture. Not an application measurement engine."""
import math
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parent

def load(): return json.loads((ROOT/'fixture.json').read_text())
def area_xy(v): return abs(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(v,v[1:]+v[:1])))/2

def validate(data):
    if data.get('fictional') is not True or data.get('units')!='feet': raise ValueError('Fictional QA feet fixture required')
    if len(data.get('buildings',[]))!=2: raise ValueError('This prototype supports the two defined test buildings only')
    ids=set()
    for b in data['buildings']:
        L,W=b['length'],b['width']
        if len(b.get('origin',[]))!=2 or any(isinstance(n,bool) or not isinstance(n,(int,float)) or not math.isfinite(n) for n in b['origin']): raise ValueError('Invalid building placement')
        if not all(isinstance(n,(int,float)) and not isinstance(n,bool) and math.isfinite(n) and n>0 for n in [L,W]): raise ValueError('Invalid dimensions')
        if b['outline']!=[[0,0,0],[L,0,0],[L,W,0],[0,W,0]]: raise ValueError('Unsupported test footprint')
        if len(b['planes'])!=2 or b['ridge'].get('confirmed') is not True or b['ridge'].get('type')!='ridge': raise ValueError('Two planes and confirmed ridge required')
        heights=[]
        for i,p in enumerate(b['planes']):
            if p['id'] in ids: raise ValueError('Duplicate plane ID')
            ids.add(p['id'])
            if p.get('confirmed') is not True: raise ValueError('Pitch confirmation missing')
            rise,run=p['pitch_rise'],p['pitch_run']
            if not all(isinstance(n,(int,float)) and not isinstance(n,bool) and math.isfinite(n) and n>0 for n in [rise,run]): raise ValueError('Invalid pitch')
            if math.degrees(math.atan(rise/run))>=80: raise ValueError('Unsupported pitch')
            h=W/2*rise/run;heights.append(h)
            expected=([[0,0,0],[L,0,0],[L,W/2,h],[0,W/2,h]] if i==0 else [[0,W/2,h],[L,W/2,h],[L,W,0],[0,W,0]])
            if len(p['vertices'])!=4 or any(len(a)!=3 or any(not isinstance(x,(int,float)) or isinstance(x,bool) or not math.isfinite(x) or abs(x-y)>1e-8 for x,y in zip(a,c)) for a,c in zip(p['vertices'],expected)): raise ValueError('Plane coordinates do not match explicit gable dimensions/pitch')
        if not math.isclose(*heights,abs_tol=1e-8): raise ValueError('Planes do not share a consistent ridge height')
        expected_ridge=[[0,W/2,heights[0]],[L,W/2,heights[0]]]
        if len(b['ridge']['points'])!=2 or any(len(a)!=3 or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or abs(x-y)>1e-8 for x,y in zip(a,c)) for a,c in zip(b['ridge']['points'],expected_ridge)): raise ValueError('Ridge does not match shared plane boundary')
    a,b=data['buildings'];ax,ay=a['origin'];bx,by=b['origin']
    if min(ax+a['length'],bx+b['length'])>max(ax,bx) and min(ay+a['width'],by+b['width'])>max(ay,by): raise ValueError('Test buildings overlap')
    return data

def quantities(data):
    validate(data)
    return [{**p,'building_id':b['id'],'building':b['name'],'plan_area':area_xy(p['vertices']),'surface_area':area_xy(p['vertices'])*math.hypot(1,p['pitch_rise']/p['pitch_run']),'pitch_degrees':math.degrees(math.atan(p['pitch_rise']/p['pitch_run']))} for b in data['buildings'] for p in b['planes']]

def price(data):
    q=quantities(data);money=lambda v:Decimal(str(v)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
    lines=[(b['name'],sum(p['surface_area'] for p in q if p['building_id']==b['id'])) for b in data['buildings']]
    # One fictional test job, one saved total area/rate; display building rows must reconcile.
    subtotal=money(sum(v for _,v in lines)*float(data['rate_cad']))
    amounts=[money(v*float(data['rate_cad'])) for _,v in lines]
    if sum(amounts)!=subtotal: raise ValueError('Building line items do not reconcile')
    gst=money(subtotal*Decimal(data['gst_percent'])/100);pst=money(subtotal*Decimal(data['pst_percent'])/100)
    return {'lines':[(name,qty,amount) for (name,qty),amount in zip(lines,amounts)],'subtotal':subtotal,'gst':gst,'pst':pst,'total':subtotal+gst+pst}
