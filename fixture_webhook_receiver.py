"""Default-OFF LOCAL TEST-only WSGI receiver. No app import or Stripe connection.
A valid locally signed notification proves only possession of the fictional
signing secret. It does not prove payment, ownership or retrieved facts.
"""
import json
import logging
import time
import stripe
from stripe_fixture_boundary import API_VERSION, SUCCESS_HINTS, OBSERVATION_HINTS

MAX_BODY=65536
TOLERANCE=300
LOG=logging.getLogger('aeriquote.fixture_webhook')


def unique_object(pairs):
    out={}
    for key,value in pairs:
        if key in out:raise ValueError('Duplicate JSON key')
        out[key]=value
    return out


def create_receiver(journal, endpoint_account, invoice_routes, signing_secret, enabled=False):
    if enabled is not True:raise ValueError('Local fictional receiver is OFF by default')
    if not isinstance(signing_secret,str) or not signing_secret.startswith('whsec_fixture_'):
        raise ValueError('Locally generated fictional signing secret required')
    if not endpoint_account.startswith('acct_fixture'):
        raise ValueError('Fictional endpoint account required')
    routes=dict(invoice_routes)
    if not routes or any(not b.startswith('qa-fictional-') for b in routes.values()):
        raise ValueError('Explicit server-owned fictional invoice routes required')

    def app(environ,start_response):
        # Never log raw payload, signature, secret, event/customer IDs or SDK/DB
        # exception strings. SDK signature errors can contain sensitive material.
        def respond(status,code):
            LOG.info('fixture_webhook status=%s code=%s',status,code)
            body=json.dumps({'code':code,'fixture_only':True}).encode()
            reason={200:'OK',400:'Bad Request',403:'Forbidden',404:'Not Found',405:'Method Not Allowed',413:'Content Too Large',415:'Unsupported Media Type',503:'Service Unavailable'}[status]
            start_response(str(status)+' '+reason,[('Content-Type','application/json'),('Content-Length',str(len(body))),('Cache-Control','no-store')])
            return [body]
        if environ.get('REMOTE_ADDR') not in ('127.0.0.1','::1'):
            return respond(403,'local_test_only')
        if environ.get('PATH_INFO')!='/qa/stripe-fixture':return respond(404,'not_found')
        if environ.get('REQUEST_METHOD')!='POST':return respond(405,'post_required')
        if environ.get('CONTENT_TYPE','').split(';')[0].strip()!='application/json':return respond(415,'json_required')
        try:
            size=int(environ.get('CONTENT_LENGTH',''))
            if size<=0:return respond(400,'invalid_length')
            if size>MAX_BODY:return respond(413,'body_too_large')
            raw=environ['wsgi.input'].read(size)
            if len(raw)!=size:return respond(400,'incomplete_body')
            signature=environ.get('HTTP_STRIPE_SIGNATURE')
            stripe.Webhook.construct_event(raw,signature,signing_secret,tolerance=TOLERANCE)
            # SDK17.1 rejects stale signatures; explicitly reject future-dated or
            # ambiguous timestamps too. Multiple v1 signatures remain supported.
            timestamps=[v.split('=',1)[1] for v in signature.split(',') if v.startswith('t=')]
            if len(timestamps)!=1 or abs(time.time()-int(timestamps[0]))>TOLERANCE:
                return respond(400,'invalid_timestamp')
            event=json.loads(raw,object_pairs_hook=unique_object)
        except (ValueError,TypeError,KeyError,AttributeError,UnicodeError,stripe.SignatureVerificationError):
            return respond(400,'invalid_signed_message')
        try:
            if event['object']!='event' or event['api_version']!=API_VERSION or event['livemode'] is not False:
                return respond(400,'unsupported_event_context')
            if not isinstance(event['id'],str) or not event['id'].startswith('evt_fixture_'):
                return respond(400,'fictional_event_required')
            if event['type'] not in SUCCESS_HINTS | OBSERVATION_HINTS:
                return respond(400,'unsupported_event_type')
            if event.get('account',endpoint_account)!=endpoint_account or environ.get('HTTP_STRIPE_ACCOUNT',endpoint_account)!=endpoint_account:
                return respond(403,'account_mismatch')
            obj=event['data']['object']
            if obj['object']!='invoice' or obj['id'] not in routes:
                return respond(403,'unmapped_invoice')
            business=routes[obj['id']]
        except (KeyError,TypeError,AttributeError):return respond(400,'incomplete_event')
        try:
            # Routes are locally supplied for this offline experiment. A real
            # receiver needs authoritative server-owned mapping/retrieval; never
            # trust a body-provided business/customer/metadata for authorization.
            with journal.connection() as c,c.cursor() as q:
                q.execute('SELECT account FROM qa_business WHERE business=%s',(business,))
                row=q.fetchone()
                if not row or row[0]!=endpoint_account:return respond(403,'binding_mismatch')
            result=journal.receive(business,raw)
            # receive returns only after its transaction context commits. This is
            # receipt acceptance, never a payment/entitlement success response.
            if result not in ('received','duplicate','review'):
                return respond(503,'receipt_not_committed')
        except Exception:
            return respond(503,'receipt_unavailable')
        return respond(200,'receipt_stored' if result!='review' else 'receipt_stored_for_review')
    return app
