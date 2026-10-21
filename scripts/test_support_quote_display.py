"""Quoted history is secondary, while new text and original storage remain intact."""
import os,sys,tempfile,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['DATABASE_URL']=''
with tempfile.TemporaryDirectory() as tmp:
 os.environ['ESTIMATE_DB_PATH']=str(Path(tmp)/'quote.db')
 import app as a
 import support_center as s
 cases=[
  ('thanks for the second test\n\nOn 2026-10-15 2:54 p.m., AeriQuote wrote:\n> AeriQuote Support\n> second test','thanks for the second test'),
  ('Thanks. On 2026-10-15 2:54 p.m., AeriQuote wrote: > AeriQuote Support > second test','Thanks.'),
  ('That works.\n\n-----Original Message-----\nFrom: AeriQuote\nOld body','That works.'),
  ('Confirmed.\nFrom: AeriQuote\nSent: Thursday\nTo: Customer\nSubject: Re: test\nOld body','Confirmed.'),
  ('All good.\n\n> Prior line\n> Prior footer','All good.'),
 ]
 for original,expected in cases:
  preview,quote=s.split_quoted_email(original)
  assert preview==expected and quote and original.endswith(quote),(preview,expected)
 for original in ['On Monday I wrote: please help.','Please keep AeriQuote Support in the heading.','> Earlier question\nMy answer follows here.','> Only quoted content','An ordinary reply with no quote.']:
  assert s.split_quoted_email(original)==(original,'')
 con=a.estimate_db();tid=str(uuid.uuid4());eid=str(uuid.uuid4());original=cases[0][0]+'\n> <script>unsafe</script>'
 con.execute('INSERT INTO support_requests(id,reference,created_at,name,company,email,topic,message,device,page_url,dealer_id,fingerprint,notification_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(tid,'AQ-QUOTETEST','2026-10-15T10:00:00Z','Customer','','customer@example.com','billing','Original question','Tablet','','','hash','accepted'))
 con.execute('INSERT INTO support_incoming(id,ticket_id,received_at,sender,subject,message,attachment_count,match_status,notification_status) VALUES(?,?,?,?,?,?,?,?,?)',(eid,tid,'2026-10-15T11:00:00Z','customer@example.com','Re: test',original,0,'matched','accepted'));con.commit();con.close()
 from flask import Flask
 app=Flask(__name__);app.secret_key='test';s.register_support(app,a.estimate_db,lambda:True)
 html=app.test_client().get('/head-office/support').get_data(as_text=True)
 assert '<div class="message">thanks for the second test</div>' in html
 assert '<details class="delivery quoted-email"><summary>Show quoted email</summary>' in html
 assert '&lt;script&gt;unsafe&lt;/script&gt;' in html and '<script>unsafe</script>' not in html
 con=a.estimate_db();assert con.execute('SELECT message FROM support_incoming WHERE id=?',(eid,)).fetchone()['message']==original;con.close()
 print('PASS familiar email quote headers, flat replies, Outlook, quoted tails, conservative fallback, escaped collapsed history and unchanged stored content')
