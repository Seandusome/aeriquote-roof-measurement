"""Exercise authenticated image routes after a simulated process restart; no Google calls."""
import os, sys, tempfile, json, time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory() as tmp:
    os.environ['DATABASE_URL']=''
    os.environ['ESTIMATE_DB_PATH']=str(Path(tmp)/'recovery.db')
    import app as a
    a.GOOGLE_MAPS_API_KEY='current-test-key'
    con=a.estimate_db()
    for did in ('owner','other'):
        con.execute('INSERT INTO dealers(id,dealer_name,email,password_hash,state,status,created_at) VALUES(?,?,?,?,?,?,?)',(did,did,did+'@example.invalid','unused','SK','active','2026-10-18'))
    con.commit();con.close()
    with a.app.test_request_context('/property'):
        a.session['dealer_id']='owner'
        token=a.create_session('old-test-key',52,-106,street_url='https://maps.googleapis.com/maps/api/streetview?pano=qa&key=old-test-key',layers={'rgbUrl':'https://example.invalid/rgb?key=old-test-key','maskUrl':'https://example.invalid/mask'})
        a.SESSIONS[token].update(exact_pin=True,display_lat=52.1,display_lng=-106.1,display_zoom=19)
        a.SESSIONS[token]['structure_masks']={'extra':{'roof':{'latitude':52.2,'longitude':-106.2},'mask_cache':('image/tiff',b'not-persisted')}}
        a.SESSIONS.persist(token)
    con=a.estimate_db();stored=con.execute('SELECT payload FROM property_sessions WHERE token=?',(token,)).fetchone()['payload'];con.close()
    assert 'old-test-key' not in stored and 'current-test-key' not in stored and 'not-persisted' not in stored
    a.SESSIONS.clear() # New worker/deploy has no in-memory property session or images.
    client=a.app.test_client()
    with client.session_transaction() as s:s['dealer_id']='owner';s['auth_version']=0
    calls=[]
    def fetch(url,*args,**kwargs):calls.append(url);return 'image/jpeg',b'image-fixture'
    with patch.object(a,'req_bytes',fetch):
        response=client.get('/street/'+token)
        assert response.status_code==200 and response.data==b'image-fixture'
        assert 'key=current-test-key' in calls[0] and 'old-test-key' not in calls[0]
        assert client.get('/street/'+token).status_code==200 and len(calls)==1
        assert client.get('/mask/'+token).status_code==200
        assert client.get('/rgb/'+token).status_code==200
    meta=client.get('/exact-pin-meta/'+token).get_json()
    assert meta['latitude']==52.1 and meta['longitude']==-106.1 and meta['zoom']==19
    assert a.SESSIONS[token]['structure_masks']['extra']['roof']['latitude']==52.2
    assert a.SESSIONS[token]['structure_masks']['extra']['mask_cache'] is None
    other=a.app.test_client()
    with other.session_transaction() as s:s['dealer_id']='other';s['auth_version']=0
    assert other.get('/street/'+token).status_code==404 # Cached route remains owner-scoped.
    a.SESSIONS.clear()
    assert other.get('/street/'+token).status_code==404 # Database recovery remains owner-scoped.
    assert a.app.test_client().get('/street/'+token).status_code==302
    a.SESSIONS.clock=lambda:time.time()+3601
    assert client.get('/street/'+token).status_code==404
    con=a.estimate_db();assert con.execute('SELECT COUNT(*) AS n FROM dealer_usage').fetchone()['n']==0;con.close()
print('PASS: restart recovers Street View/aerial/mask/exact pin and extra-roof metadata, rotates runtime key, caches bytes, enforces ownership/expiry without consuming measurements')
