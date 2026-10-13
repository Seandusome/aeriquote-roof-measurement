"""Provider and route tests use mock responses; no paid AI or map requests."""
import ast
import io
import json
import math
import os
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import urllib.request
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ai_trace

SQUARE = dict(name='Lawn', points=[dict(x=.25,y=.25),dict(x=.75,y=.25),dict(x=.75,y=.75),dict(x=.25,y=.75)])
class Response:
    headers={'Content-Type':'image/png'}
    def __init__(self,data): self.data=data
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def read(self,*args): return self.data

class TraceTests(unittest.TestCase):
    def test_projection(self):
        lat,lng=ai_trace.pixel_to_latlng(.5,.5,52,-106,18)
        self.assertAlmostEqual(lat,52);self.assertAlmostEqual(lng,-106)
        nw=ai_trace.pixel_to_latlng(0,0,52,-106,18)
        se=ai_trace.pixel_to_latlng(1,1,52,-106,18)
        self.assertGreater(nw[0],se[0]);self.assertLess(nw[1],se[1])
    def test_validation(self):
        outline=ai_trace.validate_polygons({'polygons':[SQUARE]},52,-106,18)[0]
        self.assertEqual(len(outline['points']),4)
        self.assertEqual(outline['image_points'],[[160,160],[480,160],[480,480],[160,480]])
        for points in [[dict(x=2,y=0),dict(x=0,y=1),dict(x=1,y=1)],
                       [dict(x=0,y=0),dict(x=1,y=1),dict(x=0,y=1),dict(x=1,y=0)],
                       [dict(x=0,y=0)]*4, [dict(x=False,y=0),dict(x=1,y=0),dict(x=0,y=1)]]:
            with self.assertRaises(ValueError): ai_trace.validate_polygons({'polygons':[dict(name='Bad',points=points)]},52,-106,18)
    def test_provider_payload_and_response(self):
        data={'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'polygons':[SQUARE]})}]}],'usage':{'input_tokens':1000,'output_tokens':200}}
        with patch.dict(os.environ,{'AERIQUOTE_AI_TRACE_PROVIDER':'openai','OPENAI_API_KEY':'test-key'},clear=True),patch('urllib.request.urlopen',return_value=Response(json.dumps(data).encode())) as call:
            result,usage=ai_trace.suggest(b'png',52,-106,18,'lawn')
            self.assertEqual(len(result),1);self.assertEqual(usage['input_tokens'],1000)
            payload=json.loads(call.call_args.args[0].data)
            self.assertFalse(payload['store']);self.assertTrue(payload['text']['format']['strict'])
            self.assertTrue(payload['input'][0]['content'][1]['image_url'].startswith('data:image/png;base64,'))
    def test_provider_errors_are_safe_and_specific(self):
        for status, code, phrase in [(429,'insufficient_quota','credits'),(401,'invalid_api_key','API key'),(429,'rate_limit_exceeded','rate limit'),(403,'','permissions')]:
            error=urllib.error.HTTPError('https://api.openai.com/v1/responses',status,'private provider detail',{},io.BytesIO(json.dumps({'error':{'code':code,'message':'SECRET'}}).encode()))
            with patch.dict(os.environ,{'AERIQUOTE_AI_TRACE_PROVIDER':'openai','OPENAI_API_KEY':'SECRET'},clear=True),patch('urllib.request.urlopen',side_effect=error):
                with self.assertRaises(ai_trace.ProviderError) as raised: ai_trace.suggest(b'png',52,-106,18,'paved')
                self.assertIn(phrase,str(raised.exception));self.assertNotIn('SECRET',str(raised.exception))
    def test_billing_errors_are_not_reported_as_retryable_rate_limits(self):
        for code, kind, phrase in [('credit_balance_exhausted','','credit balance'),('project_spend_limit_exceeded','','project spending'),('organization_spend_limit_exceeded','','organization spending'),('organization_usage_limit_exceeded','','usage limit'),(None,'insufficient_quota','credits')]:
            error=urllib.error.HTTPError('https://api.openai.com/v1/responses',429,'private',{},io.BytesIO(json.dumps({'error':{'code':code,'type':kind,'message':'SECRET'}}).encode()))
            with patch.dict(os.environ,{'AERIQUOTE_AI_TRACE_PROVIDER':'openai','OPENAI_API_KEY':'SECRET'},clear=True),patch('urllib.request.urlopen',side_effect=error):
                with self.assertRaises(ai_trace.ProviderError) as raised: ai_trace.suggest(b'png',52,-106,18,'paved')
                self.assertIn(phrase,str(raised.exception));self.assertNotIn('rate limit',str(raised.exception));self.assertNotIn('SECRET',str(raised.exception))
    def test_provider_error_reaches_user_and_unlocks(self):
        scope,sess=self.route()
        with patch('ai_trace.configured',return_value=True),patch('urllib.request.urlopen',return_value=Response(b'png')),patch('ai_trace.suggest',side_effect=ai_trace.ProviderError('Check API credits.')):
            result,status=scope['ai_trace_suggestions']()
            self.assertEqual(status,502);self.assertEqual(result['user_error'],'Check API credits.');self.assertFalse(sess['ai_trace_busy'])
    def test_missing_key_no_network(self):
        with patch.dict(os.environ,{'AERIQUOTE_AI_TRACE_PROVIDER':'openai'},clear=True),patch('urllib.request.urlopen') as call:
            with self.assertRaises(RuntimeError): ai_trace.suggest(b'png',52,-106,18,'lawn')
            call.assert_not_called()
    def route(self,owner='dealer',enabled=True):
        tree=ast.parse(Path('app.py').read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='ai_trace_suggestions');fn.decorator_list=[]
        sess=dict(created=time.time(),dealer_id=owner,lat=52,lng=-106,key='test-map-key')
        scope=dict(request=SimpleNamespace(get_json=lambda **kw:dict(token='token',surface='paved',latitude=52,longitude=-106,zoom=18,scope=[.05,.05,.95,.95],seed=[.5,.5]),host_url='https://test.invalid/'),
                   SESSIONS={'token':sess},session={'dealer_id':'dealer'},time=time,math=math,urllib=urllib,AI_TRACE_LOCK=threading.Lock(),ai_trace=ai_trace,
                   app=SimpleNamespace(logger=SimpleNamespace(info=lambda *a:None)),json=json,jsonify=lambda **kw:kw)
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'app.py','exec'),scope)
        return scope,sess
    def test_account_isolation(self):
        scope,_=self.route(owner='another-dealer')
        with patch('urllib.request.urlopen') as call:
            self.assertEqual(scope['ai_trace_suggestions']()[1],403);call.assert_not_called()
    def test_unconfigured_route_no_network(self):
        scope,_=self.route()
        with patch('ai_trace.configured',return_value=False),patch('urllib.request.urlopen') as call:
            self.assertEqual(scope['ai_trace_suggestions']()[1],503);call.assert_not_called()
    def test_route_burst_limit_reports_seconds_without_network(self):
        scope,sess=self.route();sess['ai_trace_recent_starts']=[time.time()]*20
        with patch('ai_trace.configured',return_value=True),patch('urllib.request.urlopen') as call:
            data,status=scope['ai_trace_suggestions']()
            self.assertEqual(status,429);self.assertTrue(1<=data['retry_after_seconds']<=60);call.assert_not_called()
    def test_next_section_does_not_require_a_15_second_wait(self):
        scope,sess=self.route()
        with patch('ai_trace.configured',return_value=True),patch('ai_trace.suggest',return_value=([],{})),patch('urllib.request.urlopen',return_value=Response(b'png')) as call:
            scope['ai_trace_suggestions']()
            scope['request'].get_json=lambda **kw:dict(token='token',surface='paved',latitude=52.0001,longitude=-106,zoom=18,scope=[0,0,1,1],seed=[.5,.5])
            self.assertTrue(scope['ai_trace_suggestions']()['review_required']);self.assertEqual(call.call_count,2)
    def test_route_cache_and_busy_cleanup(self):
        scope,sess=self.route()
        with patch('ai_trace.configured',return_value=True),patch('ai_trace.suggest',return_value=([{'name':'Paved','points':[[52,-106],[52,-105.99],[52.01,-106]]}],{})),patch('urllib.request.urlopen',return_value=Response(b'png')) as call:
            result=scope['ai_trace_suggestions']();self.assertTrue(result['review_required']);self.assertEqual(len(result['suggestions']),1)
            self.assertFalse(sess['ai_trace_busy']);self.assertEqual(result['image_preview'],ai_trace.image_preview(b'png'));self.assertEqual(scope['ai_trace_suggestions'](),result);self.assertEqual(call.call_count,1)
        scope,sess=self.route()
        with patch('ai_trace.configured',return_value=True),patch('urllib.request.urlopen',side_effect=TimeoutError()):
            self.assertEqual(scope['ai_trace_suggestions']()[1],502);self.assertFalse(sess['ai_trace_busy'])

if __name__=='__main__': unittest.main()
