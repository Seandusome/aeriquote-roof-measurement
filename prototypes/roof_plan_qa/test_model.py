"""Independent analytic geometry, 3D triangle areas, pricing and rejection tests."""
import unittest,math,copy,sys
from pathlib import Path
from decimal import Decimal,ROUND_HALF_UP
from model import load,validate,quantities,price
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from pricing_integrity import calculate

def triangle(a,b,c):
    u=[b[i]-a[i] for i in range(3)];v=[c[i]-a[i] for i in range(3)]
    cross=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
    return math.sqrt(sum(x*x for x in cross))/2

class ModelTests(unittest.TestCase):
    def test_3d_geometry_and_shared_ridges(self):
        d=load();before=copy.deepcopy(d);q=quantities(d)
        for b in d['buildings']:
            ridge=set(map(tuple,b['ridge']['points']));shared=set(map(tuple,b['planes'][0]['vertices']))&set(map(tuple,b['planes'][1]['vertices']));self.assertEqual(ridge,shared)
            self.assertAlmostEqual(math.dist(*b['ridge']['points']),b['length'])
            self.assertAlmostEqual(sum(p['plan_area'] for p in q if p['building_id']==b['id']),b['length']*b['width'])
            for p in b['planes']:
                a,z,c,e=p['vertices'];actual=triangle(a,z,c)+triangle(a,c,e);record=next(x for x in q if x['id']==p['id']);self.assertAlmostEqual(actual,record['surface_area'],places=8)
                # Direct Pythagorean slope length, independent of polygon area and pitch-angle code.
                expected=b['length']*math.sqrt((b['width']/2)**2+b['ridge']['points'][0][2]**2);self.assertAlmostEqual(actual,expected,places=8)
        self.assertEqual(d,before)
        self.assertAlmostEqual(sum(p['surface_area'] for p in q),1847.6052121268147)
    def test_independent_decimal_and_existing_server_prices(self):
        d=load();p=price(d);money=lambda v:v.quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
        main=Decimal(1200)*(Decimal(1)+Decimal('0.5')**2).sqrt();garage=Decimal(480)*(Decimal(1)+(Decimal(1)/3)**2).sqrt();subtotal=money((main+garage)*Decimal('.85'))
        gst=money(subtotal*Decimal('.05'));pst=money(subtotal*Decimal('.06'))
        self.assertEqual((p['subtotal'],p['gst'],p['pst'],p['total']),(subtotal,gst,pst,Decimal('1743.21')))
        payload={'quote':{'businessType':'roofing','measurementMode':'auto','measureSource':'manual','manualPlanes':[{'surface_sqft':v['surface_area']} for v in quantities(d)]},'pricing':{'price':.85,'gst':5,'pst':6,'disc':0,'mode':'regular','extraAmount':0,'estimatePeriod':'one_time'}}
        actual=calculate(payload);self.assertEqual(actual['total'],p['total']);self.assertEqual(actual['subtotal'],p['subtotal'])
    def test_reject_incomplete_inconsistent_and_unconfirmed(self):
        mutations=[lambda d:d.update(fictional=False),lambda d:d.update(units='meters'),lambda d:d['buildings'][0]['planes'][0].update(confirmed=False),lambda d:d['buildings'][0]['ridge'].update(confirmed=False),lambda d:d['buildings'][0]['ridge'].update(type='valley'),lambda d:d['buildings'][0]['planes'][0]['vertices'][2].__setitem__(2,8),lambda d:d['buildings'][0]['planes'][0].update(pitch_rise=8),lambda d:d['buildings'][0]['ridge']['points'][0].__setitem__(1,14),lambda d:d['buildings'][0]['planes'].pop(),lambda d:d['buildings'][1].update(origin=[0,0]),lambda d:d['buildings'][0]['planes'][0]['vertices'][0].__setitem__(0,False),lambda d:d['buildings'][0].update(origin=[float('nan'),0]),lambda d:d['buildings'][0]['planes'][1].update(id='A1')]
        for fn in mutations:
            d=load();fn(d)
            with self.subTest(fn=fn),self.assertRaises(ValueError):validate(d)

if __name__=='__main__':unittest.main()
