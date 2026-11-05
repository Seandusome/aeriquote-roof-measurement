"""Run from scripts/ in a deployed-source checkout; disposable SQLite only.

All clients authenticate through /dealer-login. No injected sessions or cookies.
"""
import os,sys,tempfile,uuid,json,re,time,hashlib
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory() as tmp:
    os.environ['DATABASE_URL']=''
    os.environ['ESTIMATE_DB_PATH']=str(Path(tmp)/'employee-qa.db')
    import app as a
    a.is_recovery_test_service=lambda:False
    secret=uuid.uuid4().hex
    con=a.estimate_db()
    for did in ['office','owner']:
        con.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,status,lookup_limit,estimate_limit,created_at,plan_code) VALUES(?,?,?,?,'active',25,25,'2026-10-01','basic')",(did,'QA TEST '+did,did+'@example.invalid',a.password_hash(secret)))
    for eid in ['restricted','active']:
        con.execute("INSERT INTO dealer_employees(id,dealer_id,employee_name,email,password_hash,status,created_at) VALUES(?,'owner',?,?,?,'active','2026-10-01')",(eid,'QA TEST '+eid,eid+'@example.invalid',a.password_hash(secret)))
    con.execute("INSERT INTO account_admin_roles(dealer_id) VALUES('office')")
    con.execute("INSERT INTO account_allowances(dealer_id,lookup_bonus,estimate_bonus) VALUES('owner',7,9)")
    con.execute("INSERT INTO dealer_usage(dealer_id,property_lookups) VALUES('owner',2)")
    geometry={'commercialAreas':[{'points':[[52,-106],[52,-105.9999],[52.0001,-105.9999]],'sqft':400,'rate':0.1}],'linear':{'points':[[52,-106],[52,-105.9999]],'feet':20,'rate':1}}
    payload=json.dumps({'customer_name':'QA FICTIONAL','address':'QA FICTIONAL','quote':geometry,'total_area':400,'total_price':60},sort_keys=True)
    con.execute("INSERT INTO estimates(id,dealer_id,created_at,customer_name,address,total_area,total_price,payload) VALUES('private','owner','2026-10-01','QA FICTIONAL','QA FICTIONAL',400,60,?)",(payload,))
    con.execute("INSERT INTO estimate_revisions(revision_id,estimate_id,dealer_id,revised_at,customer_name,address,total_area,total_price,payload) VALUES('revision','private','owner','2026-10-01','QA FICTIONAL','QA FICTIONAL',400,60,?)",(payload,))
    token=uuid.uuid4().hex
    measurement={'dealer_id':'owner','created':time.time(),'lat':52,'lng':-106,'mode':'fallback','geometry':geometry}
    a.SESSIONS[token]=measurement
    con.execute("INSERT INTO property_sessions(token,dealer_id,expires_at,payload) VALUES(?,'owner',?,?)",(token,time.time()+3600,json.dumps(measurement,sort_keys=True)))
    con.commit();con.close()
    tables=['estimates','estimate_revisions','property_sessions','workspace_drafts','estimate_save_receipts','account_allowances','account_month_usage','account_subscription_usage','account_billing_periods','dealer_usage']
    def snapshot():
        con=a.estimate_db()
        try:
            data={t:sorted([tuple(r) for r in con.execute('SELECT * FROM '+t).fetchall()],key=repr) for t in tables}
            data['memory_measurements']=json.dumps(dict(a.SESSIONS),sort_keys=True)
            return json.dumps(data,sort_keys=True,default=str)
        finally:con.close()
    baseline=snapshot()
    def normal(identity,allowed=True):
        c=a.app.test_client()
        before=snapshot()
        response=c.post('/dealer-login',data={'email':identity+'@example.invalid','password':secret})
        assert snapshot()==before,'Login changed business data'
        if allowed:assert response.status_code==302 and response.location=='/'
        else:assert response.status_code==200 and b'Email or password is incorrect' in response.data
        return c
    office,owner,restricted,dormant,active=map(normal,['office','owner','restricted','restricted','active'])
    def rejected(c,label,stale_clients=None):
        before=snapshot()
        clients=stale_clients or [c]*4
        with patch('urllib.request.urlopen',side_effect=AssertionError('Rejected access reached network')) as network:
            assert clients[0].get('/api/estimates/private').status_code==401,label
            assert clients[1].post('/api/estimates',json={'id':'private','total_price':999,'quote':geometry}).status_code==401,label
            assert clients[2].post('/property',json={'address':'QA FICTIONAL'}).status_code==401,label
            assert clients[3].put('/api/workspace-drafts/qa-rejected',json={'payload':{'quote':geometry}}).status_code==401,label
            assert c.post('/dealer-employees/restricted/status',data={'action':'activate'}).status_code==302,label
            assert network.call_count==0
        assert snapshot()==before,label+' altered estimates/measurements/allowances'
    def toggle(action):
        assert owner.post('/dealer-employees/restricted/status',data={'action':action}).status_code==302
    page=office.get('/head-office/credits?q=owner%40example.invalid').data.decode()
    csrf=re.search(r'name="csrf" value="([^"]+)"',page).group(1)
    def business(action):
        assert office.post('/head-office/credits',data=dict(csrf=csrf,operation=str(uuid.uuid4()),dealer_id='owner',action=action,reason='QA FICTIONAL EMPLOYEE ACCESS')).status_code==302
    restricted_stale=[normal('restricted') for _ in range(4)]
    toggle('disable')
    normal('restricted',False)
    rejected(restricted,'individually disabled employee',restricted_stale)
    toggle('activate')
    restored=normal('restricted')
    assert restored.get('/api/estimates/private').status_code==200
    rejected(dormant,'old session after individual reactivation')
    toggle('disable')
    active_stale=[normal('active') for _ in range(4)]
    business('disable')
    normal('active',False)
    normal('restricted',False)
    rejected(active,'active employee under disabled owner',active_stale)
    rejected(restored,'restricted employee under disabled owner')
    business('reactivate')
    normal('restricted',False)
    revived=normal('active')
    assert revived.get('/api/estimates/private').status_code==200
    rejected(active,'old employee session after business reactivation')
    con=a.estimate_db()
    assert con.execute("SELECT status FROM dealer_employees WHERE id='restricted'").fetchone()['status']=='disabled'
    assert con.execute("SELECT status FROM dealer_employees WHERE id='active'").fetchone()['status']=='active'
    assert con.execute("SELECT dealer_id FROM account_admin_roles").fetchone()['dealer_id']=='office'
    assert con.execute("SELECT COUNT(*) AS n FROM account_credit_audit").fetchone()['n']==2
    con.close()
    owner=normal('owner')
    toggle('activate')
    assert normal('restricted').get('/api/estimates/private').status_code==200
    assert snapshot()==baseline,'Final business records differ from starting values'
    print('PASS: disabled employee normal login and existing session rejected; individual reactivation requires fresh login; disabled owner blocks active and restricted employees; owner reactivation preserves individual restriction; old sessions stay revoked; fresh permitted employee login succeeds.')
    print('PASS: rejected read/save/property/draft/access attempts make zero network calls and leave exact estimates, revisions, persisted/in-memory geometry, allowance/billing/usage counters and save receipts unchanged. Starting local settings restored; audit retained until disposable fixture teardown; Head Office role unchanged.')
    print('DOMAIN_SNAPSHOT_SHA256',hashlib.sha256(baseline.encode()).hexdigest())
