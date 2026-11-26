"""Expired draft IDs signal a fresh-ID retry without overwriting newer work."""
import json,sqlite3,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import workspace_drafts as d
c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row;d.initialize(c)
w={'schema':1,'values':{'customerName':'FICTIONAL RETAINED'},'pending':{'id':'same-save-operation'},'quote':{'points':[[1,2],[1,3],[2,3]],'rate':2,'pitch':26.565}}
def fails(call,code):
 before=c.execute('SELECT * FROM workspace_drafts ORDER BY 1,2,3').fetchall()
 try:call()
 except d.DraftError as e:assert e.status==409 and e.code==code,(str(e),e.code)
 else:raise AssertionError('Expected failure')
 assert c.execute('SELECT * FROM workspace_drafts ORDER BY 1,2,3').fetchall()==before
old='fictional-expired-0001';fresh='fictional-new-id-0001'
d.put(c,'A','owner:A',old,0,w,now=0)
fails(lambda:d.put(c,'A','owner:A',old,1,w,now=d.TTL),'draft_closed')
d.purge(c,now=d.TTL)
fails(lambda:d.put(c,'A','owner:A',old,1,w,now=d.TTL),'draft_closed')
assert d.put(c,'A','owner:A',fresh,0,w,now=d.TTL)['version']==1
assert json.loads(d.load(c,'A','owner:A',fresh,now=d.TTL)['payload'])==w
newer={**w,'values':{'customerName':'FICTIONAL NEWER'}}
d.put(c,'A','owner:A',fresh,1,newer,now=d.TTL+1)
fails(lambda:d.put(c,'A','owner:A',fresh,1,w,now=d.TTL+2),None)
fails(lambda:d.put(c,'B','owner:B',fresh,2,w,now=d.TTL+2),'draft_closed')
assert json.loads(d.load(c,'A','owner:A',fresh,now=d.TTL+2)['payload'])==newer
print('PASS expiry retained/purged classification, explicit fresh ID, exact payload/operation preservation, newer-version isolation')
