"""End-of-day geometry, quote and account recovery attacks. Disposable SQLite only."""
import copy, math, os, sys, tempfile
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parent)]
from measurement_integrity import polygon_sqft, line_feet
from qa_estimate_fixture import price_fixture

# Independent GeographicLib 2.1 WGS84 references, generated outside AeriQuote.
concave=[[52,-106],[52,-105.9998],[52.00004,-105.9998],[52.00004,-105.9999],[52.00012,-105.9999],[52.00012,-106]]
triangle=[[52.00025,-106],[52.00025,-105.9998],[52.00037,-105.9999]]
thin=[[52.0005,-106],[52.0005,-105.9998],[52.0005001,-105.9998],[52.0005001,-106]]
line=[[52,-105.9996],[52.00005,-105.9996],[52.00005,-105.9995],[52.00015,-105.9995]]
for points,reference in [(concave,1316.0577917355927),(triangle,987.0389700971165),(thin,1.6450563388342956)]:
    assert abs(polygon_sqft(points)/reference-1)<.006
assert abs(line_feet(line)/77.28968886010122-1)<.006

with tempfile.TemporaryDirectory() as tmp:
    os.environ['DATABASE_URL']=''
    os.environ['ESTIMATE_DB_PATH']=tmp+'/final-qa.db'
    import app as a
    con=a.estimate_db()
    for did in ['final-a','final-b']:
        con.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,status,created_at) VALUES(?,?,?,'unused','active','2026-10-27')",(did,did,did+'@example.invalid'))
        con.execute('INSERT INTO account_allowances(dealer_id,complimentary) VALUES(?,1)',(did,))
    con.execute("INSERT INTO dealer_employees(id,dealer_id,employee_name,email,password_hash,status,created_at) VALUES('final-employee','final-a','QA employee','final-employee@example.invalid','unused','active','2026-10-27')")
    con.commit();con.close()
    def identify(client,did,employee=False):
        with client.session_transaction() as s:
            s.clear();s.update(dealer_id=did,account_type='employee' if employee else 'owner',auth_version=0)
            if employee:s['employee_id']='final-employee'
    c=a.app.test_client();identify(c,'final-a',True)
    other=a.app.test_client();identify(other,'final-b')
    def save(p,key,version=None):
        headers={'X-AeriQuote-Account':'final-a','Idempotency-Key':key}
        if version:headers['If-Match']=version
        return c.post('/api/estimates',json=p,headers=headers)
    for industry in ['snow','pressure','paving','landscaping','commercial','roofing']:
        for mode in ['regular','discount','included']:
            # Consecutive repeats and explicit closing vertex are retained, not silently rewritten.
            outline=[concave[0]]+concave+[concave[0]]
            p={'address':'FICTIONAL final '+industry+' '+mode,'customer_name':'QA DO NOT SEND',
               'extra_service_amount':17.35,'extra_service_description':'QA additional service',
               'pricing':{'mode':mode,'gst':5,'pst':6,'disc':7.25,'price':.83,'estimatePeriod':'season' if industry in ('snow','landscaping','commercial') else 'one_time'},
               'quote':{'businessType':industry,'measurementMode':'linear','linearFeet':line_feet(line),'linearPoints':copy.deepcopy(line),
                        'commercialAreas':[{'points':outline,'sqft':round(polygon_sqft(outline)),'rate':.17},
                                           {'points':triangle,'sqft':round(polygon_sqft(triangle)),'rate':.39},
                                           {'points':thin,'sqft':round(polygon_sqft(thin)),'rate':.11}]}}
            if industry=='roofing':
                # Two adjoining verified planes and a separate garage; no invented structural lines.
                left=[[52,-106],[52,-105.9999],[52.00012,-105.9999],[52.00012,-106]]
                right=[[lat,lng+.0001] for lat,lng in left]
                planes=[{'points':points,'pitch_degrees':math.degrees(math.atan(rise/12)),
                         'surface_sqft':polygon_sqft(points)*math.sqrt(1+(rise/12)**2),
                         'pitch_confirmed':True,'manual_roof_qa':True}
                        for points,rise in [(left,4),(right,8),(triangle,6)]]
                p['quote']={'businessType':'roofing','measurementMode':'auto','measureSource':'manual',
                            'manualRoofWorkflow':True,'roofScopeConfirmed':True,'structures':[],'manualPlanes':planes}
                for plane in planes:
                    assert abs(plane['surface_sqft']*math.cos(math.radians(plane['pitch_degrees']))/polygon_sqft(plane['points'])-1)<1e-12
            price_fixture(p)
            key=industry+'-'+mode;response=save(p,key);assert response.status_code==200,(key,response.json)
            eid=response.json['id'];receipt=response.json
            before=c.get('/api/estimates/'+eid).json
            assert before['payload']['quote']==p['quote'] and before['total_price']==p['total_price']
            assert save(p,key).json==receipt,'Repeated submission must replay the receipt'
            mutations=[lambda q:q['pricing'].update(total=q['pricing']['total']+.03),
                       lambda q:q.update(total_area=q['total_area']+3)]
            if industry=='roofing':
                mutations += [lambda q:q['quote']['manualPlanes'][0].update(pitch_confirmed=False),
                              lambda q:q['quote']['manualPlanes'].append(copy.deepcopy(q['quote']['manualPlanes'][0])),
                              lambda q:q['quote'].update(roofScopeConfirmed=False)]
            else:
                mutations += [lambda q:q['quote']['commercialAreas'][0].update(points=[]),
                              lambda q:q['quote']['commercialAreas'].append(copy.deepcopy(q['quote']['commercialAreas'][0])),
                              lambda q:q['quote'].update(linearFeet=1)]
            for i,mutate in enumerate(mutations):
                bad=copy.deepcopy(p);mutate(bad);r=save(bad,key+'-bad-'+str(i));assert r.status_code==400,(key,i,r.json)
                assert c.get('/api/estimates/'+eid).json==before,'Rejected input must retain the valid saved record'
            assert other.get('/api/estimates/'+eid).status_code==404
            assert other.get('/api/estimates/'+eid+'/versions').status_code==404
            assert other.post('/api/estimates/'+eid+'/editing-session',json={}).status_code==404
            # Old tab + different login, then expired session, must not create a foreign estimate.
            identify(c,'final-b');assert save(p,key).status_code==409
            with c.session_transaction() as s:s.clear()
            assert save(p,key).status_code==401
            identify(c,'final-a',True);assert save(p,key).json==receipt
            changed=copy.deepcopy(p);changed['customer_name']='QA corrected customer'
            r=save(changed,key+'-edit',receipt['version']);assert r.status_code==200,r.json
            assert save(p,key+'-stale',receipt['version']).status_code==409
            assert save(p,key).json==receipt,'Late lost-response replay must never overwrite the edit'
            assert c.get('/api/estimates/'+eid).json['payload']['customer_name']=='QA corrected customer'
            print('PASS',key,'independent quantity/Decimal pricing, save/reopen/edit, attacks, retry/expiry/account isolation')
    # A provider ID is not proof of a distinct building: identical geometry must not bill twice.
    from qa_estimate_fixture import automatic_roof
    original_roof=automatic_roof(triangle,building_id='qa-main')
    auto={'address':'FICTIONAL automatic duplicate protection','quote':{'businessType':'roofing','measurementMode':'auto','measureSource':'google','structures':[original_roof]}}
    price_fixture(auto);receipt=save(auto,'automatic-original');assert receipt.status_code==200,receipt.json
    before=c.get('/api/estimates/'+receipt.json['id']).json
    def usage():
        con=a.estimate_db()
        try:return [tuple(row) for row in con.execute('SELECT dealer_id,period,lookups,estimates FROM account_month_usage ORDER BY dealer_id,period').fetchall()]
        finally:con.close()
    used=usage()
    midpoint=[(triangle[0][0]+triangle[1][0])/2,(triangle[0][1]+triangle[1][1])/2]
    resampled=[triangle[0],midpoint]+triangle[1:]
    partial=[[lat,lng+.00004] for lat,lng in triangle]
    for index,points in enumerate([triangle,triangle[1:]+triangle[:1],list(reversed(triangle)),triangle+[triangle[0]],[triangle[0]]+triangle,resampled,partial]):
        duplicate=copy.deepcopy(auto);roof=copy.deepcopy(original_roof);roof.update(building_id='different-provider-id',outline=points)
        duplicate['quote']['structures'].append(roof);price_fixture(duplicate)
        rejected=save(duplicate,'automatic-duplicate-'+str(index))
        assert rejected.status_code==400,(rejected.status_code,rejected.json)
        assert any(word in rejected.json['error'].lower() for word in ['same','duplicate','overlap'])
        assert c.get('/api/estimates/'+receipt.json['id']).json==before
        assert usage()==used,'Rejected duplicate must not consume either business allowance'
    distinct=copy.deepcopy(auto)
    distinct['address']='FICTIONAL distinct automatic garage'
    distinct['quote']['structures'].append(automatic_roof([[lat+.001,lng] for lat,lng in triangle],building_id='qa-real-distinct-garage'))
    price_fixture(distinct);assert save(distinct,'automatic-distinct').status_code==200
    adjacent=copy.deepcopy(auto);adjacent['address']='FICTIONAL shared automatic boundary'
    adjacent['quote']['structures'].append(automatic_roof([[2*triangle[0][0]-lat,lng] for lat,lng in triangle],building_id='qa-adjacent-roof'))
    price_fixture(adjacent);assert save(adjacent,'automatic-adjacent').status_code==200
    print('PASS duplicate/resampled/partially overlapping automatic footprints rejected; shared boundaries and detached garages retained')
    assert other.get('/api/estimates').json==[]
    assert c.post('/api/account/profile',json={'company':'employee forbidden'}).status_code==403
    print('PASS 18 six-industry pricing/scope cases; zero foreign records; no provider calls or production database')
