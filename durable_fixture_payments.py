"""Disposable LOCAL PostgreSQL fictional inbox/reconciler. Not a webhook.
No app import, Stripe SDK/retrieval/signature verification or live enforcement.
"""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import psycopg2
from psycopg2.extras import Json
from stripe_fixture_boundary import normalize
from subscription_events_qa import encoded, digest, transition, instant

MARKER='AQ_FICTIONAL_PG_V1'
DDL='''
CREATE TABLE qa_business (
 business text PRIMARY KEY CHECK(business LIKE 'qa-fictional-%'),
 account text NOT NULL, customer text NOT NULL, subscription text NOT NULL,
 binding jsonb NOT NULL, state jsonb NOT NULL,
 UNIQUE(account,customer), UNIQUE(account,subscription));
CREATE TABLE qa_inbox (
 account text NOT NULL, event_id text NOT NULL, business text NOT NULL REFERENCES qa_business,
 raw_body bytea NOT NULL, raw_hash text NOT NULL, received_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(account,event_id), UNIQUE(business,event_id));
CREATE TABLE qa_task (
 business text NOT NULL, event_id text NOT NULL, status text NOT NULL,
 attempts integer NOT NULL DEFAULT 0, issue text,
 PRIMARY KEY(business,event_id), FOREIGN KEY(business,event_id) REFERENCES qa_inbox(business,event_id));
CREATE TABLE qa_facts (
 business text NOT NULL, event_id text NOT NULL, facts jsonb NOT NULL, facts_hash text NOT NULL,
 PRIMARY KEY(business,event_id), FOREIGN KEY(business,event_id) REFERENCES qa_inbox(business,event_id));
CREATE TABLE qa_deliveries (
 seq bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, business text NOT NULL REFERENCES qa_business,
 account text NOT NULL, event_id text NOT NULL, raw_body bytea NOT NULL, raw_hash text NOT NULL, outcome text NOT NULL);
CREATE TABLE qa_normalized (
 business text NOT NULL, event_id text NOT NULL, operation text NOT NULL, event jsonb NOT NULL,
 semantic_hash text NOT NULL, PRIMARY KEY(business,event_id),
 FOREIGN KEY(business,event_id) REFERENCES qa_inbox(business,event_id));
CREATE TABLE qa_applied (
 business text NOT NULL REFERENCES qa_business, operation text NOT NULL,
 event_id text NOT NULL, semantic_hash text NOT NULL, outcome text NOT NULL,
 PRIMARY KEY(business,operation), FOREIGN KEY(business,event_id) REFERENCES qa_normalized(business,event_id));
CREATE TABLE qa_history (
 seq bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 business text NOT NULL REFERENCES qa_business, event_id text NOT NULL,
 phase text NOT NULL, status text NOT NULL, issue text,
 before_state jsonb NOT NULL, after_state jsonb NOT NULL,
 previous_hash text NOT NULL, entry_hash text NOT NULL,
 recorded_at timestamptz NOT NULL DEFAULT clock_timestamp());
CREATE FUNCTION qa_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Fictional journal is append-only'; END $$;
'''


def fault(requested, location):
    if requested==location:
        os._exit(86)  # abrupt process death: no cleanup/rollback call
    if requested=='raise:'+location:
        raise RuntimeError('Injected transient failure at '+location)


class LocalJournal:
    def __init__(self, config):
        self.config=json.loads(Path(config).read_text()) if isinstance(config,(str,Path)) else deepcopy(config)
        k=self.config
        if k['host']!='127.0.0.1' or k['dbname']!='aq_durable_fiction' or type(k['port']) is not int:
            raise ValueError('Refuse nonlocal/nonfictional target')
        marker=json.loads(Path(k['marker']).read_text())
        if marker!={'marker':MARKER,'database':k['dbname'],'data_directory':k['data_directory']}:
            raise ValueError('Disposable cluster marker mismatch')

    @contextmanager
    def connection(self):
        k=self.config
        c=psycopg2.connect(host=k['host'],port=k['port'],dbname=k['dbname'],user=k['user'],connect_timeout=3)
        try:
            with c:
                with c.cursor() as q:
                    q.execute("SELECT current_database(), current_setting('data_directory'), host(inet_server_addr()), inet_server_port(), current_setting('fsync'), current_setting('synchronous_commit')")
                    row=q.fetchone()
                    if (row[:4]!=(k['dbname'],k['data_directory'],'127.0.0.1',k['port'])
                            or row[4:]!=('on','on')):
                        raise ValueError('Actual isolated target/durability settings mismatch before writes')
                yield c
        finally:c.close()

    def initialize(self):
        with self.connection() as c, c.cursor() as q:
            q.execute(DDL)
            for table in ('qa_inbox','qa_facts','qa_deliveries','qa_normalized','qa_applied','qa_history'):
                q.execute('CREATE TRIGGER immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON '+table+
                          ' FOR EACH STATEMENT EXECUTE FUNCTION qa_immutable()')

    def register(self, binding, state):
        if binding['business_id']!=state['business_id'] or not binding['business_id'].startswith('qa-fictional-'):
            raise ValueError('Fictional business/state binding mismatch')
        with self.connection() as c, c.cursor() as q:
            q.execute('INSERT INTO qa_business VALUES(%s,%s,%s,%s,%s,%s)',
                      (binding['business_id'],binding['account_id'],binding['customer_id'],binding['subscription_id'],Json(binding),Json(state)))
            self.history(q,binding['business_id'],'seed','register','registered',state,state)

    def lock(self,q,business,event_id=None):
        q.execute('SELECT binding,state FROM qa_business WHERE business=%s FOR UPDATE',(business,))
        row=q.fetchone()
        if not row:raise ValueError('Unknown fictional business')
        if event_id:
            q.execute('SELECT status FROM qa_task WHERE business=%s AND event_id=%s FOR UPDATE',(business,event_id))
            if not q.fetchone():raise ValueError('Event not in this business')
        return row

    def history(self,q,business,event_id,phase,status,before,after,issue=None):
        q.execute('SELECT entry_hash FROM qa_history WHERE business=%s ORDER BY seq DESC LIMIT 1',(business,))
        prior=q.fetchone();prior=prior[0] if prior else 'GENESIS'
        facts=dict(business=business,event_id=event_id,phase=phase,status=status,issue=issue,
                   before_state=before,after_state=after,previous_hash=prior)
        q.execute('INSERT INTO qa_history(business,event_id,phase,status,issue,before_state,after_state,previous_hash,entry_hash) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                  (business,event_id,phase,status,issue,Json(before),Json(after),prior,digest(facts)))

    def receive(self,business,raw_body,fail=None):
        # FUTURE REAL INGRESS: authenticate RAW bytes/signature/account BEFORE this
        # call. This fixture method does NOT authenticate its inputs.
        n=json.loads(raw_body)
        if not isinstance(n['id'],str) or not n['id'].startswith('evt_fixture_'):
            raise ValueError('Fictional event ID required')
        key=n['id']; hashed=hashlib.sha256(raw_body).hexdigest()
        with self.connection() as c,c.cursor() as q:
            b,s=self.lock(q,business)
            q.execute('SELECT business,raw_hash FROM qa_inbox WHERE account=%s AND event_id=%s',(b['account_id'],key))
            old=q.fetchone()
            if old:
                status='duplicate' if old==(business,hashed) else 'review'
                self.history(q,business,key,'receive',status,s,s,'Conflicting receipt' if status=='review' else None)
                if status=='review' and old[0]==business:
                    q.execute("UPDATE qa_task SET status='review',issue='Conflicting receipt' WHERE business=%s AND event_id=%s AND status NOT IN ('applied','duplicate','observed_no_grant')",(business,key))
            else:
                q.execute('INSERT INTO qa_inbox(account,event_id,business,raw_body,raw_hash) VALUES(%s,%s,%s,%s,%s)',
                          (b['account_id'],key,business,psycopg2.Binary(raw_body),hashed))
                q.execute('INSERT INTO qa_task(business,event_id,status) VALUES(%s,%s,%s)',(business,key,'received'))
                self.history(q,business,key,'receive','received',s,s)
                status='received'
            q.execute('INSERT INTO qa_deliveries(business,account,event_id,raw_body,raw_hash,outcome) VALUES(%s,%s,%s,%s,%s,%s)',
                      (business,b['account_id'],key,psycopg2.Binary(raw_body),hashed,status))
            fault(fail,'receive_before_commit')
        fault(fail,'receive_after_commit')
        return status

    def supply_simulated_facts(self,business,key,contract,canonical):
        # FUTURE RECONCILER: authenticated canonical retrieval + immutable locally
        # approved binding/quote/history belongs HERE, not in webhook metadata.
        value={'contract':contract,'canonical':canonical};hashed=digest(value)
        with self.connection() as c,c.cursor() as q:
            b,s=self.lock(q,business,key)
            q.execute('SELECT facts_hash FROM qa_facts WHERE business=%s AND event_id=%s',(business,key))
            old=q.fetchone()
            if old:
                status='duplicate' if old[0]==hashed else 'review'
                self.history(q,business,key,'supply',status,s,s,'Immutable simulated fact conflict' if status=='review' else None)
                if status=='review':
                    q.execute("UPDATE qa_task SET status='review',issue='Conflicting simulated facts' WHERE business=%s AND event_id=%s AND status NOT IN ('applied','duplicate','observed_no_grant')",(business,key))
                return status
            q.execute('INSERT INTO qa_facts VALUES(%s,%s,%s,%s)',(business,key,Json(value),hashed))
            self.history(q,business,key,'supply','supplied_simulation',s,s)
        return 'supplied_simulation'

    def reconcile(self,business,key,fail=None):
        with self.connection() as c,c.cursor() as q:
            b,s=self.lock(q,business,key)
            q.execute('SELECT status FROM qa_task WHERE business=%s AND event_id=%s',(business,key));status=q.fetchone()[0]
            if status not in ('received','retry'):return status
            q.execute('UPDATE qa_task SET attempts=attempts+1 WHERE business=%s AND event_id=%s',(business,key))
            q.execute('SELECT 1 FROM qa_normalized WHERE business=%s AND event_id=%s',(business,key))
            if q.fetchone():
                q.execute("UPDATE qa_task SET status='reconciled',issue=NULL WHERE business=%s AND event_id=%s",(business,key))
                self.history(q,business,key,'reconcile','resumed_reconciled',s,s)
                return 'reconciled'
            q.execute('SELECT facts FROM qa_facts WHERE business=%s AND event_id=%s',(business,key));f=q.fetchone()
            if not f:
                status='review';issue='Missing simulated canonical facts';event=None
            else:
                q.execute('SELECT raw_body FROM qa_inbox WHERE business=%s AND event_id=%s',(business,key))
                n=json.loads(bytes(q.fetchone()[0]));facts=f[0]
                result=normalize(n,b,facts['contract'],facts['canonical'])
                event=result['event'];status='reconciled' if event else 'review';issue='; '.join(result['issues']) or None
            if event:
                semantic=digest({k:v for k,v in event.items() if k!='id'})
                q.execute('INSERT INTO qa_normalized VALUES(%s,%s,%s,%s,%s)',(business,key,event['operation_id'],Json(event),semantic))
            q.execute('UPDATE qa_task SET status=%s,issue=%s WHERE business=%s AND event_id=%s',(status,issue,business,key))
            self.history(q,business,key,'reconcile',status,s,s,issue)
            fault(fail,'reconcile_before_commit')
        fault(fail,'reconcile_after_commit');return status

    def apply(self,business,key,now,fail=None):
        with self.connection() as c,c.cursor() as q:
            b,s=self.lock(q,business,key)
            q.execute('SELECT status FROM qa_task WHERE business=%s AND event_id=%s',(business,key));status=q.fetchone()[0]
            if status not in ('reconciled','pending','retry'):return status
            q.execute('SELECT event,semantic_hash FROM qa_normalized WHERE business=%s AND event_id=%s',(business,key));row=q.fetchone()
            if not row:raise ValueError('No reconciled event')
            e,hashed=row;op=e['operation_id'];new=s;issue=None
            q.execute('SELECT semantic_hash FROM qa_applied WHERE business=%s AND operation=%s',(business,op));old=q.fetchone()
            if old:
                status='duplicate' if old[0]==hashed else 'review'
                issue='Conflicting operation facts' if status=='review' else None
            elif instant(e['effective_at'])>instant(now):status='pending';issue='Future effective time'
            elif e['previous_operation']!=s['head']:
                q.execute('SELECT 1 FROM qa_applied WHERE business=%s AND operation=%s',(business,e['previous_operation']))
                status='review' if e['previous_operation'] is None or q.fetchone() else 'pending'
                issue='Stale or missing causal predecessor'
            else:
                # All candidates for the same entitlement head are reviewed, not
                # ordered by notification time or arbitrary worker acquisition.
                q.execute("SELECT n.event_id FROM qa_normalized n JOIN qa_task t USING(business,event_id) WHERE n.business=%s AND t.status IN ('reconciled','pending') AND n.event->>'previous_operation' IS NOT DISTINCT FROM %s AND n.operation<>%s AND n.event->>'kind'<>'payment.observed'",(business,s['head'],op))
                competitors=q.fetchall() if e['kind']!='payment.observed' else []
                if competitors:
                    status='review';issue='Competing causal branch'
                    for (other,) in competitors:
                        q.execute("UPDATE qa_task SET status='review',issue=%s WHERE business=%s AND event_id=%s",(issue,business,other))
                        self.history(q,business,other,'apply','review',s,s,issue)
                else:
                    try:new,status=transition(s,e,now)
                    except (ValueError,KeyError,TypeError,OverflowError) as exc:status='review';issue=str(exc)
                    if status in ('applied','observed_no_grant'):
                        q.execute('INSERT INTO qa_applied VALUES(%s,%s,%s,%s,%s)',(business,op,key,hashed,status))
            q.execute('UPDATE qa_business SET state=%s WHERE business=%s',(Json(new),business))
            fault(fail,'apply_after_state')
            q.execute('UPDATE qa_task SET status=%s,issue=%s WHERE business=%s AND event_id=%s',(status,issue,business,key))
            self.history(q,business,key,'apply',status,s,new,issue)
            fault(fail,'apply_before_commit')
        fault(fail,'apply_after_commit');return status

    def transient_failure(self,business,key,issue):
        with self.connection() as c,c.cursor() as q:
            b,s=self.lock(q,business,key)
            q.execute("UPDATE qa_task SET status='retry',issue=%s WHERE business=%s AND event_id=%s AND status IN ('received','reconciled','pending','retry')",(issue,business,key))
            self.history(q,business,key,'worker','retry',s,s,issue)

    def process(self,business,key,now,fail=None):
        try:
            status=self.reconcile(business,key,fail)
            if status in ('reconciled','pending','retry'):return self.apply(business,key,now,fail)
            return status
        except (RuntimeError,psycopg2.OperationalError) as exc:
            self.transient_failure(business,key,str(exc));raise

    def state(self,business):
        with self.connection() as c,c.cursor() as q:
            q.execute('SELECT state FROM qa_business WHERE business=%s',(business,));row=q.fetchone()
            if not row:raise ValueError('Unknown fictional business')
            return row[0]
