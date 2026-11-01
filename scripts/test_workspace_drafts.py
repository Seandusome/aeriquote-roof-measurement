"""Isolated recovery storage: no application database or provider connections."""
import json,sqlite3,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import workspace_drafts as d
c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row;d.initialize(c)
a='fictional-tab-00001';b='fictional-tab-00002';w={'schema':1,'values':{'customerName':'FICTIONAL QA'},'quote':{'areaPoints':[[52,-106],[52.01,-106],[52,-106.01]]},'pending':{'id':'retained-save-operation'},'baseVersion':'retained-stale-guard'}
def rejected(call,status):
 try:call();raise AssertionError('Expected rejection')
 except d.DraftError as e:assert e.status==status,(e,e.status,status)
r=d.put(c,'business-a','owner:a',a,0,w,{'lat':52,'lng':-106},now=100)
assert r['version']==1 and r['expires_at']==100+d.TTL
assert json.loads(d.load(c,'business-a','owner:a',a,now=101)['payload'])==w
for dealer,user in [('business-b','owner:a'),('business-a','employee:a'),('business-a','employee:b')]:
 rejected(lambda:d.load(c,dealer,user,a,now=101),404)
# Interrupted/lost autosave acknowledgement can be retried without incrementing.
assert d.put(c,'business-a','owner:a',a,0,w,now=101)['version']==1
w2={**w,'values':{'customerName':'SECOND FICTIONAL EDIT'}}
rejected(lambda:d.put(c,'business-a','owner:a',a,0,w2,now=101),409)
d.put(c,'business-a','owner:a',a,1,w2,now=102)
d.put(c,'business-a','owner:a',b,0,w,now=102)
assert json.loads(d.load(c,'business-a','owner:a',a,now=103)['payload'])==w2
assert json.loads(d.load(c,'business-a','owner:a',b,now=103)['payload'])==w
for bad in [{'schema':1,'password':'secret'},{'schema':1,'api_key':'secret'},{'schema':1,'image':'data:image/png;base64,xxx'},{'schema':1,'pending':{'payload':{'street_image_data':'data:image/png;base64,xxx'}}}]:
 rejected(lambda:d.put(c,'business-a','owner:a','forbidden-tab-0001',0,bad,now=103),400)
# Discard is idempotent and erases payload immediately; delayed autosaves fail.
d.close(c,'business-a','owner:a',a,now=104);d.close(c,'business-a','owner:a',a,now=104)
row=c.execute('SELECT * FROM workspace_drafts WHERE draft_id=?',(a,)).fetchone();assert row['payload'] is None and row['property_metadata'] is None
rejected(lambda:d.put(c,'business-a','owner:a',a,2,w2,now=105),409)
rejected(lambda:d.load(c,'business-a','owner:a',a,now=105),404)
rejected(lambda:d.load(c,'business-a','owner:a',b,now=102+d.TTL),404)
d.purge(c,now=104+d.TTL);assert c.execute('SELECT COUNT(*) FROM workspace_drafts').fetchone()[0]==0
print('PASS: individual/business isolation, separate tabs, exact workspace/save IDs/base version, lost acknowledgement retry, stale edits, private-data rejection, discard/tombstones, expiry/deletion')
