"""Create NEW fictional disposable QA files only; never opens an existing DB."""
import copy
import json
from pathlib import Path
import sqlite3
from qa_policy_view import MARKER, digest


def create(root):
    root=Path(root).resolve()
    root.mkdir(parents=True,exist_ok=True)
    if list(root.iterdir()):
        raise ValueError('Fixture target must be new and empty; existing files preserved')
    (root/'ISOLATED_FIXTURE.txt').write_text(MARKER+'\nFictional accounts only. Verified empty target before database creation.\n')
    base=dict(now='2026-07-15T12:00:00Z',
              period=dict(id='qa-confirmed-period',start='2026-07-01T00:00:00Z',end='2026-08-01T00:00:00Z',renewal_anchor='2026-01-01T00:00:00Z',payment_status='succeeded'),
              retention=dict(paid_access_end='2026-08-01T00:00:00Z',legacy_full={'status':'none'},legacy_lightweight={'status':'none'},full_present=True,lightweight_present=True),upgrades=[])
    facts={}
    for name in ['active','cancellation-pending','read-only','expired','reactivated','unknown-legacy','missing-payment','missing-retention','disabled']:
        f=copy.deepcopy(base);f['case']=name
        if name=='cancellation-pending':f['cancellation']=dict(requested_at='2026-07-10T00:00:00Z')
        if name=='read-only':
            f['period'].update(start='2026-03-01T00:00:00Z',end='2026-04-01T00:00:00Z')
            f['retention']['paid_access_end']='2026-04-01T00:00:00Z'
        if name in ('expired','unknown-legacy'):
            f['period'].update(start='2026-01-01T00:00:00Z',end='2026-02-01T00:00:00Z')
            f['retention']['paid_access_end']='2026-02-01T00:00:00Z'
        if name=='reactivated':
            f['retention'].update(paid_access_end='2026-02-01T00:00:00Z',legacy_full=dict(status='known',deadline='2026-10-01T00:00:00Z'),legacy_lightweight=dict(status='known',deadline='2027-02-01T00:00:00Z'))
            f['reactivation']=dict(payment_status='succeeded',confirmed_at='2026-07-01T00:00:00Z',period_id='qa-confirmed-period')
        if name=='unknown-legacy':
            f['retention'].update(legacy_full=dict(status='unknown'),legacy_lightweight=dict(status='unknown'))
        if name=='missing-payment':del f['period']['payment_status']
        if name=='missing-retention':del f['retention']['paid_access_end']
        facts['qa-fictional-'+name]=f
    con=sqlite3.connect(root/'accounts.sqlite')
    try:
        con.executescript('''CREATE TABLE dealers(id TEXT PRIMARY KEY,status TEXT,plan_code TEXT,created_at TEXT);
CREATE TABLE dealer_employees(id TEXT PRIMARY KEY,dealer_id TEXT,status TEXT);
CREATE TABLE account_auth_versions(account_type TEXT,account_id TEXT,version INTEGER);
CREATE TABLE account_billing_periods(dealer_id TEXT PRIMARY KEY,anchor_at TEXT,seed_period TEXT,basis TEXT);
CREATE TABLE account_billing_migration(id TEXT PRIMARY KEY,started_at TEXT);
CREATE TABLE account_subscription_usage(dealer_id TEXT,period_start TEXT,lookups INTEGER,estimates INTEGER,PRIMARY KEY(dealer_id,period_start));
CREATE TABLE account_allowances(dealer_id TEXT PRIMARY KEY,complimentary INTEGER,lookup_bonus INTEGER,estimate_bonus INTEGER);
CREATE TABLE dealer_usage(dealer_id TEXT PRIMARY KEY,property_lookups INTEGER);
CREATE TABLE estimates(id TEXT PRIMARY KEY,created_at TEXT,customer_name TEXT,address TEXT,total_area REAL,total_price REAL,payload TEXT,dealer_id TEXT);
CREATE TABLE estimate_revisions(revision_id TEXT PRIMARY KEY,estimate_id TEXT,payload TEXT,dealer_id TEXT);
CREATE TABLE workspace_drafts(dealer_id TEXT,principal TEXT,draft_id TEXT,payload TEXT);
''')
        con.execute('INSERT INTO account_billing_migration VALUES(?,?)',('monthly-v1','2026-01-01T00:00:00+00:00'))
        for key,f in facts.items():
            con.execute('INSERT INTO dealers VALUES(?,?,?,?)',(key,'disabled' if f['case']=='disabled' else 'active','basic','2026-01-01T00:00:00+00:00'))
            con.execute('INSERT INTO account_auth_versions VALUES(?,?,0)',('owner',key))
            con.execute('INSERT INTO account_billing_periods VALUES(?,?,?,?)',(key,'2026-01-01T00:00:00+00:00','2026-01-01T00:00:00+00:00','account_anniversary_provisional'))
            starts={f['period']['start'].replace('Z','+00:00'),'2026-07-01T00:00:00+00:00'}
            for start in starts:con.execute('INSERT INTO account_subscription_usage VALUES(?,?,?,?)',(key,start,3,2))
            con.execute('INSERT INTO account_allowances VALUES(?,?,?,?)',(key,0,7,11))
            con.execute('INSERT INTO dealer_usage VALUES(?,?)',(key,3))
            payload=json.dumps(dict(customer_name='Fictional QA Customer',address='Fictional property, no real address',quote={'areaVertices':[[1,1],[2,1],[2,2]],'pitch':'5/12'},pricing={'rate':0.85,'tax':5},qa_media_inventory='fictional-present-sentinel'))
            con.execute('INSERT INTO estimates VALUES(?,?,?,?,?,?,?,?)',('estimate-'+key,'2026-01-02T00:00:00Z','Fictional QA Customer','Fictional property',100,89.25,payload,key))
            con.execute('INSERT INTO estimate_revisions VALUES(?,?,?,?)',('revision-'+key,'estimate-'+key,payload,key))
            con.execute('INSERT INTO workspace_drafts VALUES(?,?,?,?)',(key,'owner:'+key,'draft-'+key,payload))
        con.commit()
    finally:con.close()
    (root/'facts.json').write_text(json.dumps(facts,indent=2))
    manifest=dict(kind=MARKER,accounts=list(facts),database_sha256=digest(root/'accounts.sqlite'),facts_sha256=digest(root/'facts.json'),target_verified_empty_before_writes=True)
    (root/'manifest.json').write_text(json.dumps(manifest,indent=2))
    return root
