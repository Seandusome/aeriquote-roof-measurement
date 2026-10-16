"""Isolated route tests: each added building owns a cached mask; no paid API calls."""
import ast,uuid,time
from pathlib import Path
from flask import Flask,request,session,jsonify,Response
import urllib.parse
source=ast.parse(Path('app.py').read_text())
names={'building','structure','structure_mask'}
functions=[n for n in source.body if isinstance(n,ast.FunctionDef) and n.name in names]
for n in functions:n.decorator_list=[]
app=Flask(__name__);app.secret_key='test-only';sessions={};calls=[]
def req_json(url):
 return 200,{'name':'buildings/stable-id','center':{'latitude':52,'longitude':-106},'boundingBox':{'sw':{'latitude':51.9999,'longitude':-106.0001},'ne':{'latitude':52.0001,'longitude':-105.9999}},'solarPotential':{'wholeRoofStats':{'areaMeters2':100},'roofSegmentStats':[]}}
def layers(key,lat,lng,radius):
 calls.append((lat,lng,radius));return {'maskUrl':'https://example.invalid/own-mask'}
ns=dict(request=request,session=session,jsonify=jsonify,Response=Response,uuid=uuid,urllib=urllib,SESSIONS=sessions,req_json=req_json,SolarBuildingNotFound=type('SolarBuildingNotFound',(Exception,),{}),date_text=lambda x:'2023-10-16',roof_imagery_request=lambda roof:(roof['latitude'],roof['longitude'],100),solar_layers=layers,req_bytes=lambda url:('image/tiff',b'own-roof-mask'))
exec(compile(ast.Module(body=functions,type_ignores=[]),'app.py','exec'),ns)
sessions['property']={'key':'test-key','dealer_id':'owner','lat':50,'lng':-105,'mask':'original-main-mask'}
with app.test_request_context('/structure',method='POST',json={'token':'property','latitude':52,'longitude':-106}):
 session['dealer_id']='owner';roof=ns['structure']().get_json()
 assert roof['building_id']=='buildings/stable-id' and roof['bounding_box']['sw']['latitude']==51.9999
 assert abs(roof['total_roof_sqft']-1076.391041671)<1e-8
 assert not calls,'Rejected duplicate must not incur a Data Layers call'
 mask_id=roof['mask_url'].split('/')[-1]
with app.test_request_context(roof['mask_url']):
 session['dealer_id']='owner'
 for _ in range(2):assert ns['structure_mask']('property',mask_id).data==b'own-roof-mask'
 assert calls==[(52.,-106.,100)],'Own roof coordinates, with cached repeat'
 assert sessions['property']['mask']=='original-main-mask','Main imagery must remain unchanged'
with app.test_request_context(roof['mask_url']):
 session['dealer_id']='another-owner';assert app.make_response(ns['structure_mask']('property',mask_id)).status_code==404
ns['solar_layers']=lambda *args:(_ for _ in ()).throw(RuntimeError('API down'))
sessions['property']['structure_masks'][mask_id]['mask_cache']=None
with app.test_request_context(roof['mask_url']):
 session['dealer_id']='owner';response=app.make_response(ns['structure_mask']('property',mask_id));assert response.status_code==503;assert response.get_json()['code']=='AQ-MASK-LAYERS'
print('PASS: stable building ID/area, lazy per-building mask, caching, ownership, main imagery preservation and recoverable API failure')
