"""Actual loopback HTTP + official SDK + disposable PostgreSQL; no Stripe calls."""
import copy
from contextlib import contextmanager
import hashlib
import hmac
import http.client
import io
import json
import logging
import os
from pathlib import Path
import secrets
import threading
import time
import unittest
import uuid
from unittest.mock import patch
from wsgiref.simple_server import make_server,WSGIRequestHandler
import psycopg2
import requests
from durable_fixture_payments import LocalJournal
from subscription_events_qa import seed
from fixture_webhook_receiver import create_receiver

CONFIG=Path(os.environ['AQ_LOCAL_PG_CONFIG']);K=json.loads(CONFIG.read_text());ROOT=Path(os.environ['AQ_WEBHOOK_EVIDENCE']);ROOT.mkdir(parents=True,exist_ok=True)
F=json.loads((Path(__file__).parent/'fixtures/stripe_boundary_fictional.json').read_text())
RET={'paid_access_end':'2026-02-28T12:00:00Z','legacy_full':{'status':'none'},'legacy_lightweight':{'status':'none'},'full_present':True,'lightweight_present':True}


def sql(business):
    with psycopg2.connect(**{x:K[x] for x in ('host','port','dbname','user')}) as c,c.cursor() as q:
        q.execute('SELECT state FROM qa_business WHERE business=%s',(business,));state=q.fetchone()[0]
        result={'state':state}
        for table in ('qa_inbox','qa_deliveries','qa_task','qa_applied','qa_facts','qa_normalized','qa_history'):
            q.execute('SELECT count(*) FROM '+table+' WHERE business=%s',(business,));result[table]=q.fetchone()[0]
        q.execute('SELECT raw_hash,encode(raw_body,\'hex\') FROM qa_inbox WHERE business=%s',(business,));result['raw']=q.fetchall()
        return result

class Quiet(WSGIRequestHandler):
    def log_message(self,*args):pass

class Receiver(unittest.TestCase):
    def setUp(self):
        self.root=ROOT/self._testMethodName;self.root.mkdir(exist_ok=False)
        suffix=uuid.uuid4().hex[:10];self.f=json.loads(json.dumps(F).replace('fixture','fixture_http'+suffix).replace('qa-fictional-boundary','qa-fictional-http'+suffix))
        self.b=self.f['binding'];self.biz=self.b['business_id'];self.j=LocalJournal(CONFIG)
        s=seed(self.biz,{'lookups':7,'estimates':11},RET,True);s['head']='usage23';s['invoices']=[self.f['cases']['initial']['contract']['invoice_id']]
        s['snapshot']=dict(schema=1,business_id=self.biz,security_eligible=True,now='2026-02-01T12:00:00Z',
          period=dict(id='p1',start='2026-01-31T12:00:00Z',end='2026-02-28T12:00:00Z',renewal_anchor='2026-01-31T12:00:00Z',plan='basic',payment_status='succeeded'),
          subscription_id=self.b['subscription_id'],used={'lookups':23,'estimates':23},extras={'lookups':7,'estimates':11},upgrades=[],retention=RET)
        self.j.register(self.b,s)
        self.q=self.f['cases']['upgrade'];self.n=copy.deepcopy(self.q['notification'])
        self.sensitive='FICTIONAL_PRIVATE_TEXT_'+secrets.token_hex(8)
        self.n['data']['object']['description']=self.sensitive
        self.secret='whsec_fixture_'+secrets.token_hex(32)  # never persisted/logged
        self.logs=io.StringIO();self.handler=logging.StreamHandler(self.logs);self.logger=logging.getLogger('aeriquote.fixture_webhook');self.logger.addHandler(self.handler);self.logger.setLevel(logging.INFO)
        self.receipts=[];self.responses=[];self.signatures=[];self.servers=[]
        self.before=sql(self.biz)
        self.port=self.server(self.j)

    def tearDown(self):
        for server,thread in self.servers:server.shutdown();server.server_close();thread.join(timeout=3)
        self.logger.removeHandler(self.handler)
        logs=self.logs.getvalue()
        self.assertNotIn(self.secret,logs);self.assertNotIn(self.sensitive,logs)
        for sig in self.signatures:self.assertNotIn(sig,logs)
        self.assertNotIn('Traceback',logs)
        (self.root/'safe-receiver.log').write_text(logs)
        (self.root/'sql-evidence.json').write_text(json.dumps({'before':self.before,'after':sql(self.biz),'response_commit_checks':self.responses,'log_redaction_passed':True},indent=2))
        # Full private fictional raw bytes are retained in the DB evidence, not
        # operational logs. Signing secret and signature headers are never saved.

    def server(self,journal,endpoint=None,routes=None):
        app=create_receiver(journal,endpoint or self.b['account_id'],routes or {self.q['contract']['invoice_id']:self.biz},self.secret,enabled=True)
        def observed(environ,start_response):
            def commit_checked(status,headers,exc_info=None):
                snapshot=sql(self.biz);self.responses.append({'status':status,'inbox_count':snapshot['qa_inbox'],'benefits_unchanged':snapshot['state']==self.before['state']})
                if status.startswith('200'):self.assertGreater(snapshot['qa_inbox'],0)
                return start_response(status,headers,exc_info)
            return app(environ,commit_checked)
        server=make_server('127.0.0.1',0,observed,handler_class=Quiet);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();self.servers.append((server,thread));return server.server_port

    def raw(self,n=None):return json.dumps(n or self.n,indent=1,ensure_ascii=False).encode()
    def sign(self,body,at=None,secret=None):
        at=int(time.time()) if at is None else at
        mac=hmac.new((secret or self.secret).encode(),str(at).encode()+b'.'+body,hashlib.sha256).hexdigest()
        value=f't={at},v1={mac}';self.signatures.append(value);return value
    def post(self,body=None,signature='auto',headers=None,port=None):
        body=self.raw() if body is None else body
        h={'Content-Type':'application/json'}
        if signature=='auto':h['Stripe-Signature']=self.sign(body)
        elif signature is not None:h['Stripe-Signature']=signature
        if headers:h.update(headers)
        c=http.client.HTTPConnection('127.0.0.1',port or self.port,timeout=5)
        c.request('POST','/qa/stripe-fixture',body,h);r=c.getresponse();data=r.read();status=r.status;c.close()
        self.assertNotIn(self.sensitive,data.decode());self.assertNotIn(self.secret,data.decode())
        return status
    def unchanged(self):self.assertEqual(sql(self.biz),self.before)

    def test_valid_raw_bytes_receipt_only_and_duplicate(self):
        self.assertEqual(self.post(),200);one=sql(self.biz)
        self.assertEqual(one['qa_inbox'],1);self.assertEqual(one['qa_applied'],0);self.assertEqual(one['qa_facts'],0)
        self.assertEqual(one['state'],self.before['state']);self.assertEqual(bytes.fromhex(one['raw'][0][1]),self.raw())
        self.assertEqual(self.post(),200);after=sql(self.biz);self.assertEqual(after['qa_inbox'],1);self.assertEqual(after['qa_deliveries'],2);self.assertEqual(after['state'],self.before['state'])

    def test_modified_signed_body_rejected(self):
        body=self.raw();signature=self.sign(body)
        self.assertEqual(self.post(body+b' ',signature),400);self.unchanged()

    def test_missing_invalid_and_wrong_secret_rejected(self):
        body=self.raw()
        for sig in (None,'garbage','t=1,v1=no',self.sign(body,secret='whsec_fixture_wrong')):
            self.assertEqual(self.post(body,sig),400);self.unchanged()

    def test_old_and_future_timestamp_rejected(self):
        body=self.raw()
        for at in (int(time.time())-600,int(time.time())+600):
            self.assertEqual(self.post(body,self.sign(body,at)),400);self.unchanged()

    def test_live_version_account_and_unmapped_rejected(self):
        for field,value in (('livemode',True),('api_version','2025-01-27.acacia'),('account','acct_foreign')):
            n=copy.deepcopy(self.n);n[field]=value
            self.assertIn(self.post(self.raw(n)),(400,403));self.unchanged()
        self.assertEqual(self.post(headers={'Stripe-Account':'acct_foreign'}),403);self.unchanged()
        n=copy.deepcopy(self.n);n['data']['object']['id']='in_unmapped'
        self.assertEqual(self.post(self.raw(n)),403);self.unchanged()

    def test_db_failure_before_commit_redelivers_safely(self):
        original=self.j.receive
        with patch.object(self.j,'receive',side_effect=lambda b,r:original(b,r,fail='raise:receive_before_commit')):
            self.assertEqual(self.post(),503)
        self.unchanged();self.assertEqual(self.post(),200)
        self.assertEqual(sql(self.biz)['qa_inbox'],1);self.assertEqual(sql(self.biz)['state'],self.before['state'])

    def test_actual_postgresql_statement_failure_rolls_back_receipt(self):
        class FailingCursor(psycopg2.extensions.cursor):
            def execute(self,query,params=None):
                if isinstance(query,str) and query.startswith('INSERT INTO qa_task'):
                    return super().execute('SELECT 1/0')
                return super().execute(query,params)
        original=self.j.connection
        @contextmanager
        def failing():
            with original() as c:
                c.cursor_factory=FailingCursor
                yield c
        with patch.object(self.j,'connection',side_effect=failing):self.assertEqual(self.post(),503)
        self.unchanged();self.assertEqual(self.post(),200);self.assertEqual(sql(self.biz)['qa_inbox'],1)

    def test_committed_receipt_lost_response_safe_duplicate(self):
        original=self.j.receive
        def lost(b,raw):
            original(b,raw);raise psycopg2.OperationalError(self.sensitive+' '+self.secret)
        with patch.object(self.j,'receive',side_effect=lost):self.assertEqual(self.post(),503)
        self.assertEqual(sql(self.biz)['qa_inbox'],1);self.assertEqual(self.post(),200)
        self.assertEqual(sql(self.biz)['qa_inbox'],1);self.assertEqual(sql(self.biz)['qa_applied'],0)

    def test_unavailable_database_no_success_then_redelivery(self):
        with patch.object(self.j,'connection',side_effect=psycopg2.OperationalError(self.secret)):
            self.assertEqual(self.post(),503)
        self.unchanged();self.assertEqual(self.post(),200)

    def test_signature_does_not_validate_payment_simulation_separate(self):
        self.assertEqual(self.post(),200);key=self.n['id'];self.assertEqual(sql(self.biz)['state'],self.before['state'])
        # Explicit offline worker step, NOT called by receiver. Deliberately bad
        # simulated payment facts are held despite a valid signature.
        facts=copy.deepcopy(self.q['canonical']);facts['payment_intent']['status']='requires_capture'
        self.j.supply_simulated_facts(self.biz,key,self.q['contract'],facts)
        self.assertEqual(self.j.process(self.biz,key,'2026-04-01T12:00:00Z'),'review')
        self.assertEqual(sql(self.biz)['state'],self.before['state'])

    def test_valid_then_explicit_simulated_upgrade_once(self):
        self.post();key=self.n['id'];self.assertEqual(sql(self.biz)['qa_applied'],0)
        self.j.supply_simulated_facts(self.biz,key,self.q['contract'],self.q['canonical'])
        self.assertEqual(self.j.process(self.biz,key,'2026-04-01T12:00:00Z'),'applied')
        before=sql(self.biz)['state'];self.post();self.j.process(self.biz,key,'2026-04-01T12:00:00Z')
        after=sql(self.biz);self.assertEqual(after['state'],before);self.assertEqual(after['qa_applied'],1)
        p=after['state']['snapshot'];self.assertEqual(p['used']['lookups'],23);self.assertEqual(25+50-p['used']['lookups'],52);self.assertEqual(p['extras'],{'lookups':7,'estimates':11})

    def test_malformed_json_and_duplicate_keys_rejected(self):
        for body in (b'{',self.raw().replace(b'"livemode": false',b'"livemode": false,"livemode": true')):
            self.assertEqual(self.post(body),400);self.unchanged()

    def test_disabled_by_default_and_wrong_binding(self):
        with self.assertRaises(ValueError):create_receiver(self.j,self.b['account_id'],{self.q['contract']['invoice_id']:self.biz},self.secret)
        port=self.server(self.j,endpoint=self.b['account_id']+'_wrong')
        self.assertEqual(self.post(port=port),403);self.unchanged()

if __name__=='__main__':
    # Any accidental SDK external HTTP call fails the test. Only local httplib
    # requests and PostgreSQL connections are used.
    with patch.object(requests.Session,'request',side_effect=RuntimeError('External HTTP forbidden')):
        unittest.main(verbosity=2)
