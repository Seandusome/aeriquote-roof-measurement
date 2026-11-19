"""OFFLINE ONLY: fictional canonical records -> unchanged replay adapter.

No network, SDK, credential, app import, webhook or enforcement. The separately
supplied local contract is NOT a Stripe notification field and is not generated
here. It represents a future authenticated, serialized reconciliation decision.
"""
from copy import deepcopy
from datetime import datetime, timezone
from subscription_events_qa import digest

API_VERSION = '2026-10-28.endive'
PROVENANCE = 'recorded_fictional_canonical_objects_v1'
CENTS = {'basic':2900, 'pro':5900, 'business':9900}
SUCCESS_HINTS = {'invoice.paid','invoice.payment_succeeded'}
OBSERVATION_HINTS = {'invoice.payment_failed','invoice.payment_action_required'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(n):
    require(type(n) is int, 'Integer cents/timestamp required')
    return n


def utc(n):
    require(number(n) > 0, 'Positive timestamp required')
    return datetime.fromtimestamp(n, timezone.utc).isoformat().replace('+00:00','Z')


def listed(value):
    require(value['object'] == 'list' and value['has_more'] is False,
            'Complete canonical pagination required')
    rows = value['data']
    require(type(rows) is list and len({x['id'] for x in rows}) == len(rows),
            'Unique canonical list objects required')
    return rows


def normalize(notification, binding, contract, canonical):
    """Return event or explicit review. All inputs must be recorded fiction.

    Only object ID/type/version/mode are read from the notification. Amounts,
    status, metadata, customer and dates in it are deliberately NOT authorities.
    Contract/catalog/binding must come from local trusted reconciliation state.
    """
    try:
        return {'status':'normalized','event':_normalize(notification,binding,contract,canonical),
                'issues':[], 'fixture_only':True}
    except (ValueError, KeyError, TypeError, AttributeError, IndexError, OverflowError, OSError) as exc:
        return {'status':'review','event':None,'issues':[str(exc)],'fixture_only':True}


def _normalize(n, b, c, r):
    require(r['provenance'] == PROVENANCE and r['api_version'] == API_VERSION,
            'Pinned recorded-fiction retrieval required')
    require(n['object'] == 'event' and n['api_version'] == API_VERSION and n['livemode'] is False,
            'Only pinned test-shaped snapshot notifications supported')
    require(isinstance(n['id'],str) and n['id'].startswith('evt_fixture_'), 'Fictional receipt required')
    require(b['business_id'].startswith('qa-fictional-') and r['account_id'] == b['account_id'],
            'Exact fictional business/account binding required')
    # Local authenticated account context is separate from Event.account (absent
    # for ordinary own-account events); reject a supplied foreign Connect account.
    require(n.get('account', b['account_id']) == b['account_id'], 'Notification account mismatch')
    require(c['business_id'] == b['business_id'] and c['subscription_id'] == b['subscription_id']
            and c['customer_id'] == b['customer_id'], 'Local reconciliation mapping mismatch')
    require(n['type'] in SUCCESS_HINTS | OBSERVATION_HINTS,
            'Unsupported/refund/reversal/schedule notification requires reconciliation review')
    hint = n['data']['object']
    inv = r['invoice']; sub = r['subscription']; cust = r['customer']
    require(hint['object'] == 'invoice' and hint['id'] == c['invoice_id'] == inv['id'],
            'Exact invoice hint/contract/retrieval mapping required')
    require(inv['object'] == 'invoice' and sub['object'] == 'subscription'
            and cust['object'] == 'customer', 'Canonical object types required')
    require(all(x['livemode'] is False for x in (inv,sub,cust)), 'Live objects forbidden')
    require(cust['id'] == inv['customer'] == sub['customer'] == b['customer_id']
            and cust.get('deleted',False) is False, 'Customer mismatch/deleted')
    require(inv['parent']['type'] == 'subscription_details'
            and inv['parent']['subscription_details']['subscription'] == sub['id'] == b['subscription_id'],
            'Invoice subscription mismatch')
    require(inv['currency'] == 'usd' and inv['collection_method'] == 'charge_automatically',
            'Only USD automatic collection supported; other settlement requires review')
    require(c['kind'] in {'initial.paid','renewal.paid','reactivation.paid','upgrade.paid'},
            'Explicit reconciled grant purpose required')
    reason = {'initial.paid':'subscription_create','renewal.paid':'subscription_cycle',
              'reactivation.paid':'subscription_create','upgrade.paid':'subscription_update'}[c['kind']]
    require(inv['billing_reason'] == reason, 'Billing reason/purpose mismatch')
    p = c['period']; start=number(p['start']); end=number(p['end']); anchor=number(p['anchor'])
    require(start < end and anchor <= start, 'Invalid purchased period/anchor')
    items=listed(sub['items']); require(len(items)==1, 'Single licensed subscription item required')
    item=items[0]
    require(item['id'] == b['subscription_item_id'] and type(item['quantity']) is int and item['quantity'] == 1,
            'Subscription item/quantity mismatch')
    require(item['current_period_start'] == start and item['current_period_end'] == end
            and sub['billing_cycle_anchor'] == anchor, 'Subscription period/anchor mismatch; reconcile history')
    target=c['to_plan']; require(target in CENTS, 'Unknown plan')
    catalog=b['prices']; require(set(catalog)==set(CENTS), 'Explicit three-plan catalog required')
    require(len({v['id'] for v in catalog.values()})==3, 'Ambiguous price mapping')
    prices=r['prices']
    for plan, known in catalog.items():
        price=prices[known['id']]
        require(price['id']==known['id'] and price['object']=='price' and price['livemode'] is False
                and price['product']==known['product'] and price['currency']=='usd'
                and type(price['unit_amount']) is int and price['unit_amount']==CENTS[plan]
                and price['type']=='recurring' and price['billing_scheme']=='per_unit'
                and price['recurring']=={'interval':'month','interval_count':1,'usage_type':'licensed'},
                'Price/product/currency/monthly amount mismatch')
    require(item['price']['id'] == catalog[target]['id'], 'Subscription selected price mismatch')
    lines=listed(inv['lines']); expected=c['lines']
    require(len(lines)==len(expected) and len({x['id'] for x in expected})==len(expected),
            'Missing/extra/duplicate invoice lines')
    expected={x['id']:x for x in expected}
    amounts=[]; plans=[]
    for line in lines:
        e=expected[line['id']]; plan=e['plan']; number(e['amount'])
        require(plan in catalog, 'Unknown line plan')
        parent=line['parent']; details=parent['subscription_item_details']
        require(line['object']=='line_item' and line['livemode'] is False
                and line['invoice']==inv['id'] and line['currency']=='usd'
                and type(line['quantity']) is int and line['quantity']==1,
                'Line identity/currency/quantity mismatch')
        require(parent['type']=='subscription_item_details' and details['subscription']==sub['id']
                and details['subscription_item']==item['id'], 'Line subscription/item mismatch')
        require(line['pricing']['type']=='price_details'
                and line['pricing']['price_details']=={'price':catalog[plan]['id'],'product':catalog[plan]['product']},
                'Line exact price/product mismatch')
        require(type(line['amount']) is int and line['amount']==e['amount']
                and line['period']==e['period'] and type(details['proration']) is bool
                and details['proration']==e['proration'], 'Line amount/period/proration mismatch')
        require(not line['discount_amounts'] and not line['taxes']
                and not line['pretax_credit_amounts'], 'Line credits/discounts/tax require review')
        amounts.append(line['amount']);plans.append(plan)
    if c['kind']=='upgrade.paid':
        before=c['from_plan']; require(before in CENTS and CENTS[target]>CENTS[before], 'Not an upgrade')
        at=number(c['effective_at'])
        require(start <= at < end and len(lines)==2 and sorted(plans)==sorted([before,target]),
                'Exact two-line upgrade required')
        for e in expected.values():
            require(e['proration'] is True and e['period']=={'start':at,'end':end}, 'Proration window mismatch')
            require((e['amount']<0 if e['plan']==before else e['amount']>0), 'Proration credit/debit sign mismatch')
        require(c['quote_id'].startswith('qa-quote-'), 'Recorded approved proration quote required')
    else:
        require(len(lines)==1 and plans==[target] and amounts==[CENTS[target]], 'Full monthly price mismatch')
        require(next(iter(expected.values()))['proration'] is False
                and next(iter(expected.values()))['period']=={'start':start,'end':end}, 'Service period mismatch')
    total=sum(amounts); require(total>0 and number(c['expected_total'])==total, 'Expected quote total mismatch')
    require(all(number(inv[k])==total for k in ('subtotal','total','amount_due')), 'Invoice monetary totals mismatch')
    require(all(number(inv[k])==0 for k in ('starting_balance','pre_payment_credit_notes_amount',
            'post_payment_credit_notes_amount','amount_overpaid','amount_shipping'))
            and not inv['discounts'] and not inv['total_taxes'] and inv['on_behalf_of'] is None,
            'Credits/tax/discounts/alternate settlement require review')
    payments=listed(inv['payments']); require(len(payments)==1, 'One complete invoice payment allocation required')
    ip=payments[0]; pi=r['payment_intent']; charge=r['charge']
    require(ip['object']=='invoice_payment' and ip['livemode'] is False and ip['invoice']==inv['id']
            and ip['currency']=='usd' and number(ip['amount_requested'])==total
            and ip['payment']=={'type':'payment_intent','payment_intent':pi['id']}, 'Invoice payment allocation mismatch')
    require(pi['object']=='payment_intent' and pi['livemode'] is False and pi['customer']==cust['id']
            and pi['currency']=='usd' and number(pi['amount'])==total, 'PaymentIntent mapping/amount mismatch')
    require('previous_operation' in c, 'Explicit causal predecessor required')
    base=dict(schema=1,id=n['id'],business_id=b['business_id'],previous_operation=c['previous_operation'])
    if pi['status'] in {'processing','requires_action','requires_payment_method','requires_confirmation','canceled'}:
        require(inv['status']=='open' and ip['status']=='open' and number(inv['amount_paid'])==0
                and number(inv['amount_remaining'])==total and number(pi['amount_received'])==0
                and ip['amount_paid'] in (None,0) and charge is None, 'Conflicting unpaid settlement facts')
        status='failed' if pi['status'] in {'requires_payment_method','canceled'} else 'pending'
        return dict(base,operation_id='observe:'+inv['id']+':'+pi['id']+':'+pi['status'],
                    kind='payment.observed',effective_at=utc(c['effective_at']),payment={'status':status})
    require(pi['status']=='succeeded' and sub['status']=='active' and sub['pending_update'] is None,
            'Confirmed successful payment and active reconciled subscription required')
    require(inv['status']=='paid' and ip['status']=='paid' and number(inv['amount_paid'])==total
            and number(inv['amount_remaining'])==0 and number(ip['amount_paid'])==total
            and number(pi['amount_received'])==total, 'Invoice not fully settled by this payment')
    paid=number(inv['status_transitions']['paid_at'])
    require(paid==number(ip['status_transitions']['paid_at'])==number(c['effective_at']), 'Paid/effective time mismatch')
    require(charge['object']=='charge' and charge['livemode'] is False
            and charge['id']==pi['latest_charge'] and charge['payment_intent']==pi['id']
            and charge['customer']==cust['id'] and charge['currency']=='usd'
            and number(charge['amount'])==total and number(charge['amount_captured'])==total
            and charge['paid'] is True and charge['captured'] is True
            and charge['refunded'] is False and number(charge['amount_refunded'])==0
            and charge['disputed'] is False, 'Charge/refund/dispute requires review')
    op='invoice:'+inv['id']+':'+c['kind']
    event=dict(base,operation_id=op,kind=c['kind'],effective_at=utc(paid),
               payment=dict(status='succeeded',verified=True,subscription_status='active',
                            invoice_id=inv['id'],subscription_id=sub['id'],source='fictional_verified_fixture'))
    # Preserve validated financial/reconciliation facts in the adapter's semantic
    # dedup comparison. A new receipt with a changed quote must not silently look
    # like the same entitlement operation merely because its unit delta matches.
    event['reconciliation_digest']=digest({'binding':b,'contract':c,'canonical':r})
    if c['kind']=='upgrade.paid':
        event.update(period_id=p['id'],from_plan=c['from_plan'],to_plan=target,renewal_at=utc(end))
    else:
        event['period']=dict(id=p['id'],start=utc(start),end=utc(end),renewal_anchor=utc(anchor),
                             plan=target,payment_status='succeeded')
    return event


class FixtureReplay:
    """In-memory fixture receipt audit; adapter owns durable fictional journal.

    Not a production inbox or crash-safe cross-store reconciliation service.
    """
    def __init__(self, store):
        self.store=store;self.seen={};self.audit=[]

    def deliver(self, notification, binding, contract, canonical, now):
        before=self.store.state(); key=notification.get('id'); raw=digest(notification)
        if key in self.seen and self.seen[key]!=raw:
            result={'status':'review','event':None,'issues':['Conflicting immutable notification receipt'],'fixture_only':True}
        else:
            self.seen[key]=raw
            result=normalize(notification,binding,contract,canonical)
            if result['event'] is not None:
                self.store.ingest(result['event'],now)
        self.audit.append(dict(notification=deepcopy(notification),contract=deepcopy(contract),
                               result=deepcopy(result),before=before,after=self.store.state()))
        return result
