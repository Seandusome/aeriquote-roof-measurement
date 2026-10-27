"""Disposable loopback QA server; fake provider, no customer data or external API calls."""
import os,sys,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
tmp=tempfile.TemporaryDirectory();os.environ['DATABASE_URL']='';os.environ['ESTIMATE_DB_PATH']=tmp.name+'/browser.db';os.environ['FLASK_SECRET_KEY']='isolated-qa-only';os.environ['AERIQUOTE_MANUAL_ROOF_QA']='1';os.environ['AERIQUOTE_MANUAL_ROOF_QA_IDS']='qa-browser'
import app as a
from flask import request
from account_credits import month_key
a.GOOGLE_MAPS_API_KEY='qa-placeholder';a.is_recovery_test_service=lambda:False
con=a.estimate_db();con.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,state,status,lookup_limit,estimate_limit,created_at,industry) VALUES(?,?,?,?,?,'active',1000,1000,'2026-10-27','snow')",('qa-browser','QA Browser','qa-browser@example.invalid',a.password_hash('fictional-qa-password'),'SK'))
profile=dict(name='QA Browser',company='FICTIONAL QA COMPANY',email='qa-browser@example.invalid',country='CA',province='SK',businessType='snow',price=.1,gst=5,pst=6,pricingMode='regular')
con.execute('INSERT INTO dealer_profiles(dealer_id,profile_json,updated_at) VALUES(?,?,?)',('qa-browser',json.dumps(profile),'2026-10-27'));con.execute('INSERT INTO account_allowances(dealer_id,complimentary) VALUES(?,1)',('qa-browser',));con.commit();con.close()
def fixture(d):
 roof=d.get('business_type')=='roofing';token=a.create_session('qa-placeholder',52,-106,mode='manual_roof_static' if roof else 'manual_static',formatted_address='1 Fictional QA Street, Saskatoon, SK, Canada')
 return a.jsonify(token=token,fallback=True,manual_roof_only=roof,center={'latitude':52,'longitude':-106},formatted_address='1 Fictional QA Street, Saskatoon, SK, Canada',parts={})
a.perform_property_lookup=fixture
# Unexpected provider calls fail rather than reaching commercial services.
a.req_json=lambda *args,**kwargs:(_ for _ in ()).throw(AssertionError('Unexpected provider call'))
a.req_bytes=a.req_json
a.urllib.request.urlopen=a.req_json
if __name__=='__main__':a.app.run(host='127.0.0.1',port=8765,threaded=True,use_reloader=False)
