"""Exercise real Flask permissions with isolated QA businesses; never uses live accounts."""
import os, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory() as tmp:
    os.environ['DATABASE_URL'] = ''
    os.environ['ESTIMATE_DB_PATH'] = str(Path(tmp) / 'isolation.db')
    import app as a
    a.GOOGLE_MAPS_API_KEY = 'qa-unused-key'
    con = a.estimate_db()
    for did in ('qa-owner-a', 'qa-owner-b'):
        con.execute('INSERT INTO dealers(id,dealer_name,email,password_hash,state,status,created_at) VALUES(?,?,?,?,?,?,?)',
                    (did, did, did + '@example.invalid', 'unused', 'SK', 'active', '2026-10-18'))
    for eid, did in (('qa-employee-a', 'qa-owner-a'), ('qa-employee-b', 'qa-owner-b')):
        con.execute('INSERT INTO dealer_employees(id,dealer_id,employee_name,email,password_hash,status,created_at) VALUES(?,?,?,?,?,?,?)',
                    (eid, did, eid, eid + '@example.invalid', 'unused', 'active', '2026-10-18'))
    con.commit(); con.close()
    def client(did=None, eid=None):
        c = a.app.test_client()
        if did:
            with c.session_transaction() as s:
                s.update(dealer_id=did, account_type='employee' if eid else 'owner', auth_version=0)
                if eid: s['employee_id'] = eid
        return c
    owner = client('qa-owner-a'); employee = client('qa-owner-a', 'qa-employee-a')
    other = client('qa-owner-b'); other_employee = client('qa-owner-b', 'qa-employee-b')
    anon = client()
    payload = {'customer_name':'QA TEST ONLY', 'address':'QA TEST PROPERTY', 'total_area':100, 'total_price':10,
               'dealer_id':'qa-owner-b', 'quote':{'commercialAreas':[{'sqft':100, 'rate':.1, 'points':[[52,-106],[52,-105.999],[52.001,-106]]}]}}
    from measurement_integrity import polygon_sqft
    payload['quote']['commercialAreas'][0]['sqft']=round(polygon_sqft(payload['quote']['commercialAreas'][0]['points']))
    payload['total_area']=payload['quote']['commercialAreas'][0]['sqft']
    eid = employee.post('/api/estimates', json=payload).get_json()['id']
    assert owner.get('/api/estimates/' + eid).get_json()['dealer_id'] == 'qa-owner-a'
    assert len(owner.get('/api/estimates').get_json()) == 1
    assert other.get('/api/estimates').get_json() == []
    # Foreign IDs must not expose estimates, revisions, edit tokens, or allow metadata writes.
    writes = {'status':{'job_status':'Booked'}, 'amount-paid':{'amount_paid':25},
              'scheduled-date':{'scheduled_date':'2026-10-25'}, 'completion-date':{'completion_date':'2026-10-26'},
              'editing-session':{'version_index':-1}}
    for c in (other, other_employee):
        for suffix in ('', '/versions'):
            assert c.get('/api/estimates/' + eid + suffix).status_code == 404
        for suffix, body in writes.items():
            assert c.post('/api/estimates/' + eid + '/' + suffix, json=body).status_code == 404
    before = owner.get('/api/estimates/' + eid).get_json()['payload']
    assert before['total_price'] == 10 and 'amount_paid' not in before
    # Nonfinite paid amounts must not poison customer balances or saved JSON.
    for value in ('Infinity','NaN',-1,True):
        response=employee.post('/api/estimates/'+eid+'/amount-paid',json={'amount_paid':value})
        assert response.status_code==400,(value,response.get_json())
    assert owner.get('/api/estimates/'+eid).get_json()['payload']==before
    # Same address in another business creates a different record, never a shared revision.
    foreign_id = other.post('/api/estimates', json={**payload,'total_price':999}).get_json()['id']
    assert foreign_id != eid
    assert owner.get('/api/estimates/' + eid + '/versions').get_json()['revisions'] == []
    # Employees may share job history, but cannot change the business profile or manage logins/admin.
    for c in (employee, other_employee):
        assert c.post('/api/account/profile', json={'company':'QA forbidden'}).status_code == 403
        for route in ('/dealer-employees','/head-office/dealers','/head-office/legacy-dealers'):
            assert c.get(route).status_code == 403
        assert c.post('/dealer-employees/qa-employee-b/status', data={'action':'disable'}).status_code == 403
        assert c.post('/head-office/dealers/qa-owner-b/status', data={'action':'disable'}).status_code == 403
    assert owner.post('/api/account/profile', json={'company':'QA A'}).status_code == 200
    assert employee.get('/api/account/profile').get_json()['profile']['company'] == 'QA A'
    assert other.get('/api/account/profile').get_json()['profile'].get('company') != 'QA A'
    token = employee.post('/api/estimates/' + eid + '/editing-session', json={}).get_json()['token']
    for cold in (False, True):
        if cold: a.SESSIONS.clear()
        assert owner.get('/fallback-meta/' + token).status_code == 200
        for c in (other, other_employee):
            for prefix in ('fallback-meta','fallback-map','wide-aerial','exact-pin-meta','exact-pin-map','rgb','mask','street'):
                assert c.get('/' + prefix + '/' + token).status_code == 404, prefix
    # An employee email must remain a single login identity across owner signup paths.
    signup=anon.post('/api/public/signup',json={'name':'QA Duplicate','company':'QA Only','email':'QA-EMPLOYEE-B@EXAMPLE.INVALID','password':'qa-duplicate-only'})
    assert signup.status_code==409,signup.get_json()
    os.environ['ADMIN_SETUP_KEY']='qa-identity-test-only'
    headers={'X-Admin-Setup-Key':'qa-identity-test-only'}
    for route in ['/api/admin/create-dealer','/api/admin/create-signup-account']:
        response=owner.post(route,headers=headers,json={'name':'QA Duplicate','dealer_name':'QA Duplicate','company':'QA Only','email':'qa-employee-b@example.invalid','password':'qa-test-only'})
        assert response.status_code==409,(route,response.get_json())
    assert anon.post('/setup-dealer',data={'setup_key':'qa-identity-test-only','dealer_name':'QA Duplicate','email':'qa-employee-b@example.invalid','password':'qa-test-only'}).status_code==400
    os.environ.pop('ADMIN_SETUP_KEY')
    for route in ('/api/estimates','/api/account/profile','/api/estimates/'+eid+'/versions'):
        assert anon.get(route).status_code == 401
    # Cross-business employee update does nothing. Disabling the real employee revokes their live session.
    owner.post('/dealer-employees/qa-employee-b/status', data={'action':'disable'})
    assert other_employee.get('/api/estimates').status_code == 200
    owner.post('/dealer-employees/qa-employee-a/status', data={'action':'disable'})
    assert employee.get('/api/estimates').status_code == 401
    assert employee.post('/api/estimates', json=payload).status_code == 401
print('PASS: real Flask business isolation, same-address separation, foreign revisions/metadata/edit/image rejection, employee permissions, profile isolation and immediate disable')
