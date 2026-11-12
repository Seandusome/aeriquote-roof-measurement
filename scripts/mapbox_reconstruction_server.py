"""Disposable loopback-only live QA. Never run with a hosted database."""
import os,sys,json,secrets
from pathlib import Path
from flask import request
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
work=Path(os.environ['AERIQUOTE_SCRATCH_DIR']).resolve()
assert str(work).startswith('/tmp/aq-mapbox-rebuild-')
assert os.environ.get('DATABASE_URL','')==''
assert not os.environ.get('GOOGLE_API_KEY') and not os.environ.get('GOOGLE_MAPS_API_KEY')
os.environ['ESTIMATE_DB_PATH']=str(work/'fictional.sqlite')
os.environ['FLASK_SECRET_KEY']=secrets.token_hex(32)
import app as a
a.is_recovery_test_service=lambda:False
password_file=work/'password';password=secrets.token_urlsafe(24);password_file.write_text(password);password_file.chmod(0o600)
con=a.estimate_db()
con.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,state,status,lookup_limit,estimate_limit,created_at,industry) VALUES(?,?,?,?,?,'active',100,100,'2026-11-12','roofing')",('mapbox-rebuild','FICTIONAL MAPBOX RECONSTRUCTION','mapbox-rebuild@example.invalid',a.password_hash(password),'AB'))
con.execute("INSERT INTO account_allowances(dealer_id,complimentary) VALUES('mapbox-rebuild',1)")
profile={'company':'FICTIONAL MAPBOX QA','email':'mapbox-rebuild@example.invalid','country':'CA','province':'AB','businessType':'roofing','price':.1,'gst':5,'pst':6,'pricingMode':'regular'}
con.execute('INSERT INTO dealer_profiles(dealer_id,profile_json,updated_at) VALUES(?,?,?)',('mapbox-rebuild',json.dumps(profile),'2026-11-12'));con.commit();con.close()
@a.app.get('/qa-evidence')
def evidence():
 assert request.remote_addr=='127.0.0.1'
 con=a.estimate_db()
 result={table:[dict(r) for r in con.execute('SELECT * FROM '+table).fetchall()] for table in ['account_month_usage','account_subscription_usage','account_allowances','estimates']}
 con.close();return a.jsonify(result)
a.app.run(host='127.0.0.1',port=8765,threaded=True,use_reloader=False)
