"""Offline fictional event adapter. No app import, network, Stripe or enforcement.

Input events are trusted NORMALIZED facts, not Stripe webhook payloads. A future
Stripe adapter must authenticate/reconcile them first. Nothing here proves payment.
Only the separately marked disposable replay database is ever written.
"""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import sqlite3
from standalone_policy import evaluate, instant, stamp, integer, plan, LIMITS, CHANNELS

MARKER = 'AERIQUOTE_FICTIONAL_EVENT_REPLAY_V1'
KINDS = {'initial.paid','renewal.paid','reactivation.paid','upgrade.paid',
         'payment.observed','usage.recorded','downgrade.scheduled',
         'cancellation.scheduled','upgrade.reversed'}


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def seed(business_id, extras, retention, security_eligible):
    if not isinstance(business_id, str) or not business_id.startswith('qa-fictional-'):
        raise ValueError('Fictional business required')
    for c in CHANNELS:
        integer(extras[c])
    if type(security_eligible) is not bool:
        raise ValueError('Explicit independent security eligibility required')
    return dict(business_id=business_id, head=None, snapshot=None,
                seed_extras=deepcopy(extras), retention=deepcopy(retention), security_eligible=security_eligible,
                periods={}, invoices=[], usage_ledger=[], saved_work={'sentinel':'UNCHANGED'})


def projection(state, now):
    """Explicit clock only. Ending a reactivated period starts ITS retention clock."""
    if state['snapshot'] is None:
        return {'review_required':True, 'issues':['No confirmed paid period'],
                'access':None, 'entitlements':None}
    s = deepcopy(state['snapshot'])
    s['now'] = stamp(instant(now))
    if s.get('reactivation') and instant(now) >= instant(s['period']['end']):
        s['retention']['paid_access_end'] = s['period']['end']
        s.pop('reactivation')
    return evaluate(s)


def confirmed(event):
    p = event['payment']
    if (p['status'] != 'succeeded' or p['verified'] is not True
            or p['subscription_status'] != 'active'
            or not isinstance(p['invoice_id'], str) or not p['invoice_id']
            or not isinstance(p['subscription_id'], str) or not p['subscription_id']):
        raise ValueError('Explicit verified successful invoice AND active subscription required')
    if p['source'] != 'fictional_verified_fixture':
        raise ValueError('Only fictional verified inputs supported, never redirects/live payloads')


def transition(state, event, now):
    """Pure candidate transition; caller commits state/receipt together or neither."""
    q = deepcopy(state)
    kind = event['kind']
    at = instant(event['effective_at'])
    if at > instant(now):
        raise ValueError('Future event requires later explicit clock/reconciliation')
    s = q['snapshot']
    if s and at < instant(s['now']):
        raise ValueError('Causal facts have conflicting effective instants; reconcile')
    if kind == 'payment.observed':
        if event['payment']['status'] not in ('pending', 'failed'):
            raise ValueError('Unknown unconfirmed payment status')
        return q, 'observed_no_grant'
    if kind in ('initial.paid', 'renewal.paid', 'reactivation.paid', 'upgrade.paid'):
        confirmed(event)
        if event['payment']['invoice_id'] in q['invoices']:
            raise ValueError('Invoice already granted under another operation')
    if kind in ('initial.paid', 'renewal.paid', 'reactivation.paid'):
        p = deepcopy(event['period'])
        plan(p['plan'])
        if p['payment_status'] != 'succeeded' or not p['id']:
            raise ValueError('Explicit paid period required')
        if at < instant(p['start']) or at >= instant(p['end']):
            raise ValueError('Payment effective instant outside purchased period; reconcile delayed payment')
        if p['id'] in q['periods'] or (s and p['id'] == s['period']['id']):
            raise ValueError('Purchased period already granted')
        if kind == 'initial.paid':
            if s is not None:
                raise ValueError('Initial grant cannot replace an existing period')
            s = dict(schema=1, business_id=q['business_id'], security_eligible=q['security_eligible'],
                     period=p, now=stamp(at), retention=deepcopy(q['retention']),
                     used=dict.fromkeys(CHANNELS,0), extras=deepcopy(q['seed_extras']), upgrades=[])
            s['retention']['paid_access_end'] = p['end']
        else:
            if s is None:
                raise ValueError('Prior paid period missing')
            previous = evaluate({**deepcopy(s), 'now':stamp(at)})
            if previous['entitlements'] is None:
                raise ValueError('Prior entitlement facts require reconciliation')
            if p['renewal_anchor'] != s['period']['renewal_anchor']:
                raise ValueError('Billing anchor changed without explicit reconciliation')
            if event['payment']['subscription_id'] != s['subscription_id'] and kind != 'reactivation.paid':
                raise ValueError('Subscription mapping conflict')
            if kind == 'renewal.paid':
                if s.get('cancellation') or instant(p['start']) != instant(s['period']['end']):
                    raise ValueError('Canceled or noncontiguous renewal requires reconciliation')
                expected = s.get('downgrade') or previous['entitlements']['plan']
                if p['plan'] != expected:
                    raise ValueError('Renewed plan conflicts with schedule')
            else:
                if instant(p['start']) < instant(s['period']['end']):
                    raise ValueError('Reactivation cannot overlap paid access')
                if s['upgrades'] or p['plan'] != previous['entitlements']['plan']:
                    raise ValueError('Reactivation usage/plan attribution requires reconciliation')
            q['periods'][s['period']['id']] = deepcopy(s)
            old_end = s['period']['end']
            s['period'] = p
            s.pop('cancellation',None)
            s.pop('downgrade',None)
            s.pop('reactivation',None)
            if kind == 'renewal.paid':
                s['used'] = dict.fromkeys(CHANNELS,0)
                s['upgrades'] = []
                s['retention']['paid_access_end'] = p['end']
            else:
                s['retention']['paid_access_end'] = old_end
                s['reactivation'] = dict(payment_status='succeeded', confirmed_at=stamp(at), period_id=p['id'])
        s['subscription_id'] = event['payment']['subscription_id']
        q['snapshot'] = s
    elif s is None:
        raise ValueError('Paid predecessor missing')
    elif kind == 'upgrade.paid':
        if event['payment']['subscription_id'] != s['subscription_id']:
            raise ValueError('Subscription mapping conflict')
        if event['period_id'] != s['period']['id']:
            raise ValueError('Upgrade belongs to another period')
        if event['renewal_at'] != s['period']['end']:
            raise ValueError('Upgrade cannot change renewal date')
        before = evaluate({**deepcopy(s),'now':stamp(at)})['entitlements']
        if not before or event['from_plan'] != before['plan']:
            raise ValueError('Upgrade from-plan conflict')
        if s.get('downgrade'):
            raise ValueError('Upgrade with scheduled downgrade needs explicit reconciliation')
        s['upgrades'].append(dict(id=event['operation_id'], business_id=q['business_id'],
            period_id=s['period']['id'], from_plan=event['from_plan'],to_plan=event['to_plan'],
            payment_status='succeeded',confirmed_at=stamp(at),attribution_source='qa_immutable_usage_ledger',
            consumed=dict.fromkeys(CHANNELS,0),reversals=[]))
    elif kind == 'downgrade.scheduled':
        plan(event['to_plan'])
        s['downgrade'] = event['to_plan']
    elif kind == 'cancellation.scheduled':
        if event['paid_access_end'] != s['period']['end']:
            raise ValueError('Cancellation cannot invent paid-access end')
        s['cancellation'] = {'requested_at':stamp(at)}
    elif kind == 'upgrade.reversed':
        if event['status'] != 'succeeded' or event['reversal_kind'] != 'full':
            raise ValueError('Only confirmed full attributable reversal supported')
        u = next((u for u in s['upgrades'] if u['id']==event['upgrade_id']),None)
        if not u or u['period_id'] != event['period_id']:
            raise ValueError('Missing attributable upgrade/period')
        u['reversals'].append(dict(id=event['operation_id'],status='succeeded',kind='full',confirmed_at=stamp(at)))
    elif kind == 'usage.recorded':
        if event['period_id'] != s['period']['id']:
            raise ValueError('Usage period mismatch')
        current = evaluate({**deepcopy(s),'now':stamp(at)})
        if current['review_required'] or not current['access']['can_create_or_edit']:
            raise ValueError('Usage cannot consume unavailable access')
        allocation = {}
        for c in CHANNELS:
            units = integer(event['units'][c])
            remaining = current['entitlements']['remaining_monthly'][c]
            monthly, extra = min(units,remaining), max(0,units-remaining)
            if extra > s['extras'][c]:
                raise ValueError('Insufficient balance')
            attributed = sum(u['consumed'][c] for u in s['upgrades'])
            base_left = max(0,LIMITS[s['period']['plan']]-(s['used'][c]-attributed))
            left = max(0, monthly-base_left)
            for u in s['upgrades']:
                if u['reversals']:
                    continue
                delta = LIMITS[u['to_plan']]-LIMITS[u['from_plan']]
                n = min(left,delta-u['consumed'][c]);u['consumed'][c]+=n;left-=n
            if left:
                raise ValueError('Consumption attribution incomplete')
            s['used'][c]+=monthly;s['extras'][c]-=extra
            allocation[c]={'monthly':monthly,'extras':extra}
        q['usage_ledger'].append({'operation_id':event['operation_id'],'period_id':s['period']['id'],'allocation':allocation})
    else:
        raise ValueError('Unknown normalized event kind')
    if kind.endswith('.paid'):
        q['invoices'].append(event['payment']['invoice_id'])
    s['now'] = stamp(at)
    result = evaluate(s)
    if result['review_required']:
        raise ValueError('; '.join(result['issues']) or 'Unknown protected retention facts')
    q['head'] = event['operation_id']
    return q, 'applied'


class ReplayStore:
    """Disposable local SQLite journal with atomic receipt/projection commits.

    No webhook endpoint or production account mutation. Causal predecessor IDs are
    explicit domain inputs; NOT Stripe event.created or invented provider versions.
    Missing predecessors remain pending; divergent/stale branches require review.
    """
    @classmethod
    def create(cls, path, initial):
        path=Path(path).resolve()
        if path.exists() or path.with_suffix('.qa-marker').exists():
            raise ValueError('Refuse replacement of existing replay data')
        if not initial['business_id'].startswith('qa-fictional-'):
            raise ValueError('Fictional target required')
        path.parent.mkdir(parents=True,exist_ok=True)
        path.with_suffix('.qa-marker').write_text(MARKER)
        with sqlite3.connect(path) as c:
            c.executescript('CREATE TABLE projection(id INTEGER PRIMARY KEY CHECK(id=1),data TEXT NOT NULL);'
                'CREATE TABLE receipts(id TEXT PRIMARY KEY,operation_id TEXT NOT NULL,facts TEXT NOT NULL,status TEXT NOT NULL,issue TEXT);'
                'CREATE TABLE audit(seq INTEGER PRIMARY KEY,event_id TEXT,status TEXT,before_state TEXT,after_state TEXT,issue TEXT);')
            c.execute('INSERT INTO projection VALUES(1,?)',(encoded(initial),))
        return cls(path)

    def __init__(self,path):
        if Path(path).is_symlink():
            raise ValueError('Symlink is not a disposable replay target')
        self.path=Path(path).resolve(strict=True)
        if self.path.with_suffix('.qa-marker').read_text()!=MARKER or self.path.is_symlink():
            raise ValueError('Disposable replay marker required')

    def state(self):
        with sqlite3.connect(self.path) as c:
            return json.loads(c.execute('SELECT data FROM projection').fetchone()[0])

    def ingest(self,event,now,fail_before_commit=False):
        instant(now)
        facts=encoded(event);key=event.get('id')
        if not isinstance(key,str) or not key:
            raise ValueError('Receipt ID required')
        semantic=deepcopy(event);semantic.pop('id',None)
        with sqlite3.connect(self.path,timeout=15) as c:
            c.execute('BEGIN IMMEDIATE')
            state=json.loads(c.execute('SELECT data FROM projection').fetchone()[0]);before=encoded(state)
            existing=c.execute('SELECT facts,status FROM receipts WHERE id=?',(key,)).fetchone()
            status,issue='pending','Awaiting explicit causal predecessor or effective time'
            if existing:
                status='duplicate' if existing[0]==facts else 'review'
                issue=None if status=='duplicate' else 'Conflicting payload for receipt ID'
            elif event.get('schema')!=1 or type(event.get('schema')) is not int or event.get('business_id')!=state['business_id']:
                status,issue='review','Schema or business mapping mismatch'
            elif event.get('kind') not in KINDS or 'previous_operation' not in event or (event['previous_operation'] is not None and not isinstance(event['previous_operation'],str)):
                status,issue='review','Unknown kind or missing/invalid explicit causal reference'
            else:
                matches=c.execute('SELECT facts FROM receipts WHERE operation_id=?',(event.get('operation_id'),)).fetchall()
                for (raw,) in matches:
                    old=json.loads(raw);old.pop('id',None)
                    if old==semantic:status,issue='duplicate',None;break
                    status,issue='review','Conflicting facts for operation';break
            if not existing:
                if not isinstance(event.get('operation_id'),str) or not event.get('operation_id'):
                    status,issue='review','Operation ID required'
                c.execute('INSERT INTO receipts VALUES(?,?,?,?,?)',(key,event.get('operation_id') or '',facts,status,issue))
            c.execute('INSERT INTO audit(event_id,status,before_state,after_state,issue) VALUES(?,?,?,?,?)',(key,status,before,before,issue))
            def mark_review(i,reason):
                c.execute('UPDATE receipts SET status=?,issue=? WHERE id=?',('review',reason,i))
                raw=encoded(state)
                c.execute('INSERT INTO audit(event_id,status,before_state,after_state,issue) VALUES(?,?,?,?,?)',(i,'review',raw,raw,reason))
            # Resolve a pending causal chain atomically. Same-head competing facts
            # already in inbox are held, never ordered by receipt/event timestamp.
            while True:
                pending=[(i,json.loads(raw)) for i,raw in c.execute('SELECT id,facts FROM receipts WHERE status=? ORDER BY id',('pending',))]
                eligible=[]
                for i,e in pending:
                    try:
                        if instant(e['effective_at'])>instant(now):continue
                        if e.get('previous_operation')==state['head']:eligible.append((i,e))
                        elif e.get('previous_operation') is None or c.execute("SELECT 1 FROM receipts WHERE operation_id=? AND status='applied'",(e.get('previous_operation'),)).fetchone():
                            mark_review(i,'Stale causal predecessor; reconciliation required')
                    except (KeyError,TypeError,ValueError):
                        mark_review(i,'Missing/invalid event timestamp')
                if not eligible:break
                if len(eligible)>1:
                    for i,e in eligible:mark_review(i,'Competing causal branch')
                    break
                i,e=eligible[0];old=encoded(state)
                try:
                    new,outcome=transition(state,e,now);problem=None
                except (ValueError,KeyError,TypeError,OverflowError) as exc:
                    new,outcome,problem=state,'review',str(exc)
                state=new
                c.execute('UPDATE receipts SET status=?,issue=? WHERE id=?',(outcome,problem,i))
                c.execute('INSERT INTO audit(event_id,status,before_state,after_state,issue) VALUES(?,?,?,?,?)',(i,outcome,old,encoded(state),problem))
            c.execute('UPDATE projection SET data=? WHERE id=1',(encoded(state),))
            if fail_before_commit:raise RuntimeError('Fictional transaction interruption')
        return self.state()
