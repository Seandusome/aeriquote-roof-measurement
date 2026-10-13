"""Real pixel-mask conversion tests; provider calls mocked, no charges."""
import base64
import io
import json
import os
from pathlib import Path
import sys
import unittest
import urllib.error
from unittest.mock import patch
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ai_trace
import sam_trace


def encoded(mask):
    out = io.BytesIO(); Image.fromarray(mask.astype('uint8')*255).save(out, format='PNG')
    return 'data:image/png;base64,'+base64.b64encode(out.getvalue()).decode()


def pixel_area(points):
    return abs(sum(points[i][0]*points[(i+1)%len(points)][1]-points[(i+1)%len(points)][0]*points[i][1] for i in range(len(points))))/2


class Response:
    def __init__(self, data): self.data=json.dumps(data).encode()
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, *args): return self.data


class SamTests(unittest.TestCase):
    def test_three_separate_grass_sections_and_narrow_strip(self):
        mask=np.zeros((640,640), dtype='uint8')
        mask[100:108,80:280]=1
        mask[200:330,450:470]=1
        mask[420:440,90:410]=1;mask[370:440,390:410]=1
        drafts,rejected=sam_trace.masks_to_suggestions([mask],52,-106,18,'lawn')
        self.assertEqual(len(drafts),3);self.assertEqual(rejected,0)
        self.assertAlmostEqual(sum(pixel_area(a['image_points']) for a in drafts),int(mask.sum()), delta=mask.sum()*.02)
        # Corners must come from the mask's exact pixels, never language coordinates.
        strip=drafts[0]['image_points']
        self.assertEqual(min(p[0] for p in strip),80);self.assertEqual(max(p[0] for p in strip),280)
        self.assertEqual(min(p[1] for p in strip),100);self.assertEqual(max(p[1] for p in strip),108)

    def test_holes_cropped_masks_and_duplicates(self):
        mask=np.zeros((640,640), dtype='uint8');mask[100:200,100:200]=1;mask[120:140,120:140]=0
        drafts,rejected=sam_trace.masks_to_suggestions([mask],52,-106,18,'paved')
        self.assertEqual(drafts,[]);self.assertEqual(rejected,1)
        mask[:]=0;mask[0:30,100:200]=1
        self.assertEqual(sam_trace.masks_to_suggestions([mask],52,-106,18,'lawn')[0],[])
        mask[:]=0;mask[50:100,50:100]=1
        self.assertEqual(len(sam_trace.masks_to_suggestions([mask,mask],52,-106,18,'lawn')[0]),1)

    def test_mask_resolution_maps_back_to_640_aerial(self):
        mask=np.zeros((1024,1024), dtype='uint8');mask[256:512,256:512]=1
        drafts,_=sam_trace.masks_to_suggestions([mask],52,-106,18,'lawn')
        self.assertEqual(min(p[0] for p in drafts[0]['image_points']),160)
        self.assertEqual(max(p[0] for p in drafts[0]['image_points']),320)
        for pixel, geographic in zip(drafts[0]['image_points'],drafts[0]['points']):
            self.assertEqual(geographic,ai_trace.pixel_to_latlng(pixel[0]/640,pixel[1]/640,52,-106,18))

    def test_provider_payload_masks_and_no_openai_fallback(self):
        mask=np.zeros((640,640), dtype='uint8');mask[100:120,100:300]=1
        data={'masks':[{'url':encoded(mask)}],'scores':[.9]}
        with patch.dict(os.environ,{'FAL_KEY':'PRIVATE','OPENAI_API_KEY':'OTHER'},clear=True),patch('urllib.request.urlopen',return_value=Response(data)) as call:
            drafts,usage=ai_trace.suggest(b'png',52,-106,18,'lawn',scope=[.01,.01,.99,.99],seed=[200/640,110/640])
            self.assertEqual(len(drafts),1);self.assertEqual(usage['provider'],'fal-sam3')
            req=call.call_args.args[0];body=json.loads(req.data)
            self.assertEqual(req.full_url,sam_trace.ENDPOINT);self.assertEqual(call.call_count,1)
            self.assertEqual(body['point_prompts'],[{'x':200,'y':110,'label':1}]);self.assertNotIn('box_prompts',body);self.assertFalse(body['apply_mask']);self.assertTrue(body['sync_mode']);self.assertTrue(body['return_multiple_masks'])
            self.assertNotIn('PRIVATE',json.dumps(body));self.assertNotIn('OTHER',json.dumps(body))
        with patch.dict(os.environ,{'OPENAI_API_KEY':'OTHER'},clear=True),patch('urllib.request.urlopen') as call:
            self.assertFalse(ai_trace.configured())
            with self.assertRaisesRegex(ai_trace.ProviderError,'FAL_KEY'):ai_trace.suggest(b'png',52,-106,18,'lawn',scope=[.01,.01,.99,.99],seed=[200/640,110/640])
            call.assert_not_called()

    def test_safe_errors_and_low_confidence(self):
        for code in [401,402,403,422,429,500]:
            err=urllib.error.HTTPError(sam_trace.ENDPOINT,code,'SECRET',{},io.BytesIO(b'SECRET'))
            with patch.dict(os.environ,{'FAL_KEY':'SECRET'},clear=True),patch('urllib.request.urlopen',side_effect=err):
                with self.assertRaises(ai_trace.ProviderError) as raised:ai_trace.suggest(b'png',52,-106,18,'paved',scope=[.01,.01,.99,.99],seed=[200/640,110/640])
                self.assertNotIn('SECRET',str(raised.exception))
        with patch.dict(os.environ,{'FAL_KEY':'test'},clear=True),patch('urllib.request.urlopen',return_value=Response({'masks':[{'url':'bad'}],'scores':[.1]})):
            drafts,usage=ai_trace.suggest(b'png',52,-106,18,'paved',scope=[.01,.01,.99,.99],seed=[200/640,110/640]);self.assertEqual(drafts,[]);self.assertEqual(usage['rejected_regions'],1)

    def test_neighbouring_and_crossing_regions_are_not_offered(self):
        mask=np.zeros((640,640),dtype='uint8')
        mask[100:120,100:300]=1  # own south grass strip
        mask[200:320,400:420]=1  # own east grass strip
        mask[80:120,500:560]=1   # neighbouring property
        mask[500:530,100:300]=1  # property across the street
        mask[300:320,40:90]=1   # crosses selected job boundary
        drafts,rejected=sam_trace.masks_to_suggestions([mask],52,-106,18,'lawn',scope=[80/640,60/640,450/640,450/640])
        self.assertEqual(len(drafts),2);self.assertEqual(rejected,3)
        self.assertEqual(sum(pixel_area(a['image_points']) for a in drafts),6400)
        for a in drafts:
            self.assertTrue(all(80<=x<=450 and 60<=y<=450 for x,y in a['image_points']))

    def test_invalid_or_missing_scope_never_calls_provider(self):
        for scope in [None,[],[0,0,1],[0,0,2,1],[.5,0,.1,1],[False,0,1,1],[0,0,float('nan'),1]]:
            with patch.dict(os.environ,{'FAL_KEY':'test'},clear=True),patch('urllib.request.urlopen') as call:
                with self.assertRaises(ValueError):ai_trace.suggest(b'png',52,-106,18,'lawn',scope=scope,seed=[.5,.5])
                call.assert_not_called()

    def test_click_only_returns_that_section(self):
        mask=np.zeros((640,640),dtype='uint8')
        mask[100:120,100:300]=1
        mask[200:320,400:420]=1
        mask[80:120,500:560]=1
        drafts,rejected=sam_trace.masks_to_suggestions([mask],52,-106,18,'lawn',scope=[.02,.02,.98,.98],seed=[200/640,110/640])
        self.assertEqual(len(drafts),1);self.assertEqual(rejected,0)
        self.assertEqual(pixel_area(drafts[0]['image_points']),4000)
        self.assertEqual(sam_trace.masks_to_suggestions([mask],52,-106,18,'lawn',seed=[.5,.5])[0],[])
        # Selection scales correctly when the model returns 1024px masks.
        bigger=np.zeros((1024,1024),dtype='uint8');bigger[256:512,256:512]=1;bigger[600:700,600:700]=1
        self.assertEqual(len(sam_trace.masks_to_suggestions([bigger],52,-106,18,'lawn',seed=[.3,.3])[0]),1)

    def test_missing_click_never_calls_provider(self):
        for seed in [None,[],[.5],[0,.5],[float('nan'),.5],[True,.5]]:
            with patch.dict(os.environ,{'FAL_KEY':'test'},clear=True),patch('urllib.request.urlopen') as call:
                with self.assertRaises(ValueError):ai_trace.suggest(b'png',52,-106,18,'lawn',scope=[.02,.02,.98,.98],seed=seed)
                call.assert_not_called()

    def test_external_mask_urls_and_coloured_images_rejected(self):
        with patch('urllib.request.build_opener') as call:
            with self.assertRaises(ValueError):sam_trace.read_mask('https://internal.invalid/private')
            call.assert_not_called()
        out=io.BytesIO();Image.new('RGB',(640,640),(50,100,30)).save(out,format='PNG')
        with self.assertRaises(ValueError):sam_trace.decode_mask(out.getvalue())


if __name__=='__main__':unittest.main()
