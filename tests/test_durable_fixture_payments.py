"""Focused PostgreSQL crash/restart/worker tests. Fictional inputs only."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
import uuid
import psycopg2
from psycopg2.extras import Json
from durable_fixture_payments import LocalJournal
from subscription_events_qa import seed

CONFIG=Path(os.environ['AQ_LOCAL_PG_CONFIG']);K=json.loads(CONFIG.read_text())
ROOT=Path(os.environ['AQ_DURABLE_EVIDENCE']);ROOT.mkdir(parents=True,exist_ok=True)
SOURCE=Path(__file__).resolve().parents[1]
F=json.loads((SOURCE/'tests/fixtures/stripe_boundary_fictional.json').read_text())
NOW='2026-04-01T12:00:00Z'
RET={'paid_access_end':'2026-02-28T12:00:00Z','legacy_full':{'status':'none'},'legacy_lightweight':{'status':'none'},'full_present':True,'lightweight_present':True}


def independent(business):
    """Independent raw SQL before/after; no evaluator/normalizer calculation."""
    with psycopg2.connect(host=K['host'],port=K['port'],dbname=K['dbname'],user=K['user']) as c,c.cursor() as q:
        q.execute('SELECT state FROM qa_business WHERE business=%s',(business,));s=q.fetchone()[0]
        q.execute('SELECT event_id,status,attempts,issue FROM qa_task WHERE business=%s ORDER BY event_id',(business,));tasks=q.fetchall()
        q.execute('SELECT operation,event_id,semantic_hash,outcome FROM qa_applied WHERE business=%s ORDER BY operation',(business,));ops=q.fetchall()
        q.execute('SELECT event_id,phase,status,before_state,after_state,previous_hash,entry_hash FROM qa_history WHERE business=%s ORDER BY seq',(business,));history=q.fetchall()
        q.execute('SELECT event_id,raw_hash,encode(raw_body,\'hex\') FROM qa_inbox WHERE business=%s ORDER BY event_id',(business,));inbox=q.fetchall()
        return dict(state=s,tasks=tasks,operations=ops,history=history,inbox=inbox)


class Durable(unittest.TestCase):
    def setUp(self):
        self.root=ROOT/self._testMethodName;self.root.mkdir(exist_ok=False)
        suffix=uuid.uuid4().hex[:10]
        text=json.dumps(F).replace('fixture','fixture_'+suffix).replace('qa-fictional-boundary','qa-fictional-'+suffix)
        # Restore version/provenance strings unchanged (replacement only affects
        # fixture IDs; provenance uses 'fictional', so it is already unchanged).
        self.f=json.loads(text);self.b=self.f['binding'];self.biz=self.b['business_id'];self.j=LocalJournal(CONFIG)
        self.snapshots=[];self.workers=[]
        self.register(self.b)

    def register(self,b,paid=True):
        s=seed(b['business_id'],{'lookups':7,'estimates':11},RET,True)
        if paid:
            s['head']='usage23';s['invoices']=[self.f['cases']['initial']['contract']['invoice_id']]
            s['snapshot']=dict(schema=1,business_id=b['business_id'],security_eligible=True,now='2026-02-01T12:00:00Z',
               period=dict(id='p1',start='2026-01-31T12:00:00Z',end='2026-02-28T12:00:00Z',renewal_anchor='2026-01-31T12:00:00Z',plan='basic',payment_status='succeeded'),
               subscription_id=b['subscription_id'],used={'lookups':23,'estimates':23},extras={'lookups':7,'estimates':11},upgrades=[],retention=RET)
        self.j.register(b,s)

    def tearDown(self):
        for p in self.workers:
            if p.poll() is None:p.kill();p.wait()
        self.snap('final')
        (self.root/'sql-snapshots.json').write_text(json.dumps(self.snapshots,indent=2))

    def snap(self,label):
        s=independent(self.biz);self.snapshots.append({'label':label,**s});return s

    def input(self,name='upgrade',q=None):
        q=copy.deepcopy(q or self.f['cases'][name]);q['binding']=self.b
        path=self.root/(str(len(list(self.root.glob('*-input.json'))))+ '-input.json')
        path.write_text(json.dumps(q,indent=2));return path,q

    def worker(self,path,action,fail=None,async_=False):
        cmd=[sys.executable,str(SOURCE/'scripts/fixture_payment_worker.py'),str(CONFIG),str(path),action]
        if fail:cmd+=['--fail',fail]
        p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);self.workers.append(p)
        if async_:return p
        out,err=p.communicate(timeout=15)
        with (self.root/'worker-log.jsonl').open('a') as log:log.write(json.dumps({'action':action,'fail':fail,'exit':p.returncode,'stdout':out,'stderr':err})+'\n')
        return p.returncode,out,err

    def prepare(self,name='upgrade',q=None):
        path,q=self.input(name,q);self.assertEqual(self.worker(path,'receive')[0],0);self.assertEqual(self.worker(path,'supply')[0],0)
        return path,q

    def assert52(self):
        s=self.snap('assert52')['state'];p=s['snapshot'];self.assertEqual(p['used'],{'lookups':23,'estimates':23})
        self.assertEqual(p['extras'],{'lookups':7,'estimates':11});self.assertEqual(len(p['upgrades']),1)
        self.assertEqual(25+50-p['used']['lookups'],52);self.assertEqual(p['period']['end'],'2026-02-28T12:00:00Z')
        self.assertEqual(s['saved_work'],{'sentinel':'UNCHANGED'})
        self.assertEqual(len(independent(self.biz)['operations']),1)

    def test_received_event_survives_process_shutdown(self):
        path,q=self.input();self.worker(path,'receive');self.snap('after_receive_process_exit')
        self.worker(path,'supply');self.worker(path,'process');self.assert52()

    def test_crash_after_receipt_commit_lost_ack(self):
        path,q=self.input();code,_,_=self.worker(path,'receive','receive_after_commit');self.assertEqual(code,86)
        s=self.snap('durably_received_no_ack');self.assertEqual(s['tasks'][0][1],'received')
        self.worker(path,'receive');self.worker(path,'supply');self.worker(path,'process');self.assert52()

    def test_crash_before_receipt_commit_redelivery(self):
        path,q=self.input();before=self.snap('before')
        self.assertEqual(self.worker(path,'receive','receive_before_commit')[0],86)
        after=self.snap('not_acknowledged_not_committed');self.assertEqual(after['inbox'],before['inbox']);self.assertEqual(after['state'],before['state'])
        self.worker(path,'receive');self.worker(path,'supply');self.worker(path,'process');self.assert52()

    def test_crash_during_reconcile(self):
        path,q=self.prepare();before=self.snap('before')
        self.assertEqual(self.worker(path,'reconcile','reconcile_before_commit')[0],86)
        after=self.snap('rollback');self.assertEqual(after['state'],before['state']);self.assertEqual(after['tasks'][0][1],'received')
        self.worker(path,'process');self.assert52()

    def test_crash_between_reconcile_and_apply(self):
        path,q=self.prepare();self.assertEqual(self.worker(path,'reconcile','reconcile_after_commit')[0],86)
        self.assertEqual(self.snap('reconciled_not_applied')['tasks'][0][1],'reconciled')
        self.worker(path,'process');self.assert52()

    def test_crash_after_state_write_atomic_rollback(self):
        path,q=self.prepare();self.worker(path,'reconcile');before=self.snap('before')
        self.assertEqual(self.worker(path,'apply','apply_after_state')[0],86)
        after=self.snap('rolled_back');self.assertEqual(after,before)
        self.worker(path,'process');self.assert52()

    def test_crash_after_history_before_commit(self):
        path,q=self.prepare();self.worker(path,'reconcile');before=self.snap('before')
        self.assertEqual(self.worker(path,'apply','apply_before_commit')[0],86)
        self.assertEqual(self.snap('rolled_back'),before);self.worker(path,'process');self.assert52()

    def test_crash_after_apply_commit_lost_response(self):
        path,q=self.prepare();self.assertEqual(self.worker(path,'process','apply_after_commit')[0],86)
        self.assert52();before=independent(self.biz)['state']
        self.worker(path,'receive');self.worker(path,'process');self.assert52();self.assertEqual(independent(self.biz)['state'],before)

    def test_failed_processing_retries(self):
        path,q=self.prepare();self.assertNotEqual(self.worker(path,'process','raise:apply_after_state')[0],0)
        s=self.snap('retry');self.assertEqual(s['tasks'][0][1],'retry');self.assertEqual(s['operations'],[])
        self.assertEqual(s['state']['snapshot']['used']['lookups'],23)
        self.worker(path,'process');self.assert52()

    def test_failed_reconciliation_retries(self):
        path,q=self.prepare();before=self.snap('before')['state']
        self.assertNotEqual(self.worker(path,'process','raise:reconcile_before_commit')[0],0)
        s=self.snap('retry');self.assertEqual(s['tasks'][0][1],'retry');self.assertEqual(s['state'],before)
        self.worker(path,'process');self.assert52()

    def test_conflicting_receipt_before_application_is_held(self):
        path,q=self.prepare();before=self.snap('before')['state']
        bad=copy.deepcopy(q['notification']);bad['data']['object']['id']='in_conflicting'
        self.assertEqual(self.j.receive(self.biz,json.dumps(bad).encode()),'review')
        self.worker(path,'process');s=self.snap('held')
        self.assertEqual(s['tasks'][0][1],'review');self.assertEqual(s['state'],before);self.assertEqual(s['operations'],[])

    def test_competing_causal_branches_both_held(self):
        path,q=self.prepare();self.worker(path,'reconcile');before=self.snap('before')['state']
        other=copy.deepcopy(q)
        old=other['contract']['invoice_id'];other=json.loads(json.dumps(other).replace(old,old+'_competing'))
        other['notification']['id']+='_branch'
        path2,_=self.prepare(q=other);self.worker(path2,'reconcile')
        self.worker(path,'process');self.worker(path2,'process');s=self.snap('both_held')
        self.assertEqual({x[1] for x in s['tasks']},{'review'});self.assertEqual(s['operations'],[]);self.assertEqual(s['state'],before)

    def test_conflicting_financial_operation_cannot_regrant(self):
        path,q=self.prepare();self.worker(path,'process');self.assert52();before=self.snap('before')['state']
        other=copy.deepcopy(q);other['notification']['id']+='_other';other['contract']['quote_id']='qa-quote-different'
        path2,_=self.prepare(q=other);self.worker(path2,'process')
        self.assertEqual(independent(self.biz)['state'],before)
        self.assertIn('review',[x[1] for x in independent(self.biz)['tasks']]);self.assert52()

    def test_duplicate_deliveries_competing_process_workers(self):
        path,q=self.prepare()
        self.worker(path,'receive');self.worker(path,'receive')
        cfg={x:K[x] for x in ('host','port','dbname','user')}
        c=psycopg2.connect(**cfg);cur=c.cursor();cur.execute('SELECT 1 FROM qa_business WHERE business=%s FOR UPDATE',(self.biz,))
        try:
            ps=[self.worker(path,'process',async_=True) for _ in range(6)]
            waiting=0;deadline=time.time()+8
            while time.time()<deadline:
                with psycopg2.connect(**cfg) as watch,watch.cursor() as q:
                    q.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock'");waiting=q.fetchone()[0]
                if waiting>=2:break
                time.sleep(.05)
            self.assertGreaterEqual(waiting,2)
            (self.root/'concurrent-lock-observation.json').write_text(json.dumps({'blocked_workers_observed':waiting}))
        finally:c.commit();cur.close();c.close()
        for p in ps:
            out,err=p.communicate(timeout=15);self.assertEqual(p.returncode,0,err)
            with (self.root/'worker-log.jsonl').open('a') as log:log.write(json.dumps({'action':'competing-process','exit':p.returncode,'stdout':out,'stderr':err})+'\n')
        self.assert52()
        # A different event ID for the identical canonical operation also dedups.
        other=copy.deepcopy(self.f['cases']['upgrade']);other['notification']['id']+='_other'
        path,_=self.prepare(q=other);self.worker(path,'process');self.assert52()
        self.assertIn('duplicate',[x[1] for x in independent(self.biz)['tasks']])

    def test_missing_and_conflicting_facts_held(self):
        before=self.snap('before')['state']
        path,q=self.input();self.worker(path,'receive');self.worker(path,'process')
        self.assertEqual(self.snap('missing_facts')['tasks'][0][1],'review')
        path,q=self.prepare();self.worker(path,'process');self.assertEqual(independent(self.biz)['state'],before)
        bad=copy.deepcopy(q['notification']);bad['data']['object']['id']='in_wrong'
        self.assertEqual(self.j.receive(self.biz,json.dumps(bad).encode()),'review')
        self.assertEqual(independent(self.biz)['state'],before)
        q2=copy.deepcopy(q);q2['contract']['expected_total']=1
        self.assertEqual(self.j.supply_simulated_facts(self.biz,q['notification']['id'],q2['contract'],q2['canonical']),'review')
        self.assertEqual(independent(self.biz)['state'],before)

    def test_wrong_business_cannot_process_or_change_other_work(self):
        path,q=self.prepare();before=self.snap('before')
        b=copy.deepcopy(self.b);b.update(business_id=self.biz+'-other',account_id=self.b['account_id']+'other',customer_id=self.b['customer_id']+'other',subscription_id=self.b['subscription_id']+'other')
        self.register(b);other=independent(b['business_id'])
        with self.assertRaises(ValueError):self.j.process(b['business_id'],q['notification']['id'],NOW)
        self.assertEqual(independent(self.biz),before);self.assertEqual(independent(b['business_id']),other)
        # Even receipt + supplied foreign canonical facts in another business grant nothing.
        self.j.receive(b['business_id'],json.dumps(q['notification']).encode())
        self.j.supply_simulated_facts(b['business_id'],q['notification']['id'],q['contract'],q['canonical'])
        self.assertEqual(self.j.process(b['business_id'],q['notification']['id'],NOW),'review')
        self.assertEqual(independent(b['business_id'])['state'],other['state']);self.assertEqual(independent(self.biz),before)
        self.worker(path,'process');self.assert52()

    def test_duplicate_business_binding_rejected(self):
        before=self.snap('before')
        b=copy.deepcopy(self.b);b['business_id']+='-duplicate'
        with self.assertRaises(psycopg2.IntegrityError):self.register(b)
        self.assertEqual(independent(self.biz),before)

    def test_immutable_history_and_original_raw_body(self):
        path,q=self.prepare();self.worker(path,'process');before=self.snap('before')
        with self.j.connection() as c,c.cursor() as cur:
            for statement in ("UPDATE qa_history SET status='changed' WHERE business=%s",'DELETE FROM qa_inbox WHERE business=%s',"UPDATE qa_facts SET facts='{}' WHERE business=%s",'DELETE FROM qa_applied WHERE business=%s'):
                with self.assertRaises(psycopg2.Error):
                    try:cur.execute(statement,(self.biz,))
                    finally:c.rollback()
        after=self.snap('tamper_rejected');self.assertEqual(after,before)
        self.assertEqual(bytes.fromhex(after['inbox'][0][2]),json.dumps(q['notification'],sort_keys=True).encode())

    def test_incomplete_payment_and_refund_stay_review(self):
        before=self.snap('before')['state']
        for i,kind in enumerate(('incomplete','refund','wrong-currency')):
            q=copy.deepcopy(self.f['cases']['upgrade']);q['notification']['id']+=str(i)
            if kind=='incomplete':q['canonical']['subscription']['status']='incomplete'
            elif kind=='refund':q['canonical']['charge']['amount_refunded']=100
            else:q['canonical']['invoice']['currency']='cad'
            path,_=self.prepare(q=q);self.worker(path,'process')
            self.assertEqual(independent(self.biz)['state'],before)
        self.assertEqual({x[1] for x in independent(self.biz)['tasks']},{'review'})

    def test_initial_paid_delivery_once(self):
        # Independent empty fictional account; same registered binding scheme.
        b=copy.deepcopy(self.b);b.update(business_id=self.biz+'-new',account_id=self.b['account_id']+'new',customer_id=self.b['customer_id']+'new',subscription_id=self.b['subscription_id']+'new')
        self.register(b,False)
        q=copy.deepcopy(self.f['cases']['initial']);text=json.dumps(q).replace(self.b['customer_id'],b['customer_id']).replace(self.b['subscription_id'],b['subscription_id']).replace(self.biz,b['business_id']).replace(self.b['account_id'],b['account_id']);q=json.loads(text)
        raw=json.dumps(q['notification']).encode();key=q['notification']['id']
        self.j.receive(b['business_id'],raw);self.j.supply_simulated_facts(b['business_id'],key,q['contract'],q['canonical'])
        self.assertEqual(self.j.process(b['business_id'],key,NOW),'applied');before=independent(b['business_id'])['state']
        self.j.receive(b['business_id'],raw);self.j.process(b['business_id'],key,NOW)
        self.assertEqual(independent(b['business_id'])['state'],before);self.assertEqual(before['snapshot']['used']['lookups'],0)
        (self.root/'additional-business.json').write_text(json.dumps(independent(b['business_id']),indent=2))

if __name__=='__main__':unittest.main(verbosity=2)
