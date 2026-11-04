"""Owner-only simulated purchase UI. Explicit opt-in AND disposable loopback DB only."""
import json,os,secrets,uuid
from urllib.parse import urlsplit
from flask import request,session,abort,redirect,render_template_string
from itsdangerous import URLSafeSerializer,BadSignature
import account_credits as credits
import extra_allowance_ledger as ledger
import payment_free_orders as orders

TEMPLATE='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Extra measurements · AeriQuote QA</title><style>
*{box-sizing:border-box}body{margin:0;background:#f4f7fa;color:#182a40;font:16px/1.5 system-ui,-apple-system,sans-serif}main{max-width:1000px;margin:auto;padding:32px 24px 60px}header{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:30px}.brand{font-weight:800;font-size:24px;color:#163853}.badge{font-size:13px;font-weight:750;padding:7px 12px;border-radius:8px;background:#fff0c5;color:#715100}h1{font-size:32px;line-height:1.2;margin:0 0 10px}h2{font-size:21px;margin:0 0 16px}p{margin:8px 0 18px}.muted,small{color:#526479}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:24px 0}.card,.purchase,.history{background:white;border:1px solid #dbe3eb;border-radius:14px;padding:22px}.card h2{font-size:16px;margin:0}.count{display:block;font-size:32px;font-weight:750;margin:4px 0}.card p{font-size:14px;margin:0}.purchase{display:grid;grid-template-columns:1fr 290px;gap:32px;margin-bottom:28px;border-top:4px solid #12766f}.pack{font-size:25px;line-height:1.3;font-weight:750;margin:0 0 6px}.price{font-size:30px;font-weight:750;margin:0 0 12px}.summary{border-top:1px solid #dbe3eb;padding:8px 0}.summary div{display:flex;justify-content:space-between;gap:15px;margin:5px 0}.total{font-weight:750;border-top:1px solid #dbe3eb;padding-top:10px}.money{white-space:nowrap;font-variant-numeric:tabular-nums}button{font:inherit;font-weight:700;cursor:pointer;border:0;border-radius:8px;background:#126c66;color:white;padding:13px 16px;width:100%;min-height:48px}button:hover{background:#0b514d}button:disabled{cursor:default;background:#667b80}button.secondary{background:#eef2f5;color:#34465b}.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}.actions form{flex:1;min-width:145px}.message{padding:14px 18px;border-radius:10px;background:#e4f4ee;margin-bottom:20px}.error{background:#fff0e8;color:#793b17}.status{font-weight:700;font-size:13px;border-radius:5px;padding:4px 8px;background:#edf1f5;white-space:nowrap}.status.success{background:#e1f2e9;color:#18583c}.status.failed{background:#fff0e8;color:#793b17}.order{border-top:1px solid #dbe3eb;padding:20px 0}.order:last-child{padding-bottom:0}.orderhead{display:flex;gap:14px;justify-content:space-between;align-items:center}.values{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-top:14px}.values dt{font-size:12px;color:#526479}.values dd{margin:2px 0 0;font-weight:650}.history>p:last-child{margin-bottom:0}a{color:#126c66}button:focus-visible,a:focus-visible{outline:3px solid #367fca;outline-offset:3px}@media(max-width:650px){main{padding:20px 16px 40px}header{margin-bottom:24px}.brand{font-size:21px}.badge{font-size:11px;padding:6px 8px}h1{font-size:28px}.cards{gap:8px}.card{padding:12px 9px}.card h2{font-size:13px}.card p{font-size:12px}.count{font-size:27px}.purchase{grid-template-columns:1fr;gap:16px;padding:20px}.pack{font-size:23px}.history{padding:20px}.values{grid-template-columns:repeat(3,1fr);row-gap:14px}.orderhead{align-items:flex-start;font-size:14px}.actions{flex-direction:column}.actions form{width:100%}}
</style></head><body><main><header><span class="brand">AeriQuote</span><span class="badge">SIMULATION MODE · QA ONLY</span></header><h1>Extra measurements</h1><p class="muted">Fictional purchases only. No payment details or real charges.</p>
{% if message %}<p role="status" class="message">{{message}}</p>{% endif %}{% if error %}<p role="alert" class="message error">{{error}}</p>{% endif %}
<section class="cards" aria-label="Measurement balances">{% for title,count,detail in balances %}<div class="card"><h2>{{title}}</h2><span class="count" data-balance="{{title|lower}}">{{count}}</span><p>{{detail}}</p></div>{% endfor %}</section>
<p class="muted">Used in this order: monthly, granted, then purchased. Employees share your business’s balance.</p>
<section class="purchase" aria-label="Buy extra measurements"><div><h2 class="pack">25 extra measurements</h2><p>Estimates included</p><p class="price">US$25 <small style="font-size:14px;font-weight:400">before applicable tax</small></p><p>Purchased extras never expire. An active paid or complimentary subscription is required to use them.</p><small>{{eligibility}} Cancellation keeps purchased extras; reactivating your subscription makes them usable again.</small></div><div>{% if quote %}<p><strong>{{jurisdiction}}</strong><br><small>{{tax_note}}</small></p><div class="summary"><div><span>Pack · USD</span><span class="money">US$25.00</span></div><div><span>Tax</span><span class="money" id="tax">{{money(quote.tax_cents)}}</span></div><div class="total"><span>Total · USD</span><span class="money" id="total">{{money(quote.total_cents)}}</span></div></div><form method="post" action="/qa/purchases"><input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="business" value="{{business}}"><input type="hidden" name="intent" value="{{intent}}"><input type="hidden" name="action" value="start"><button id="startPurchase" {% if pending %}disabled{% endif %}>{{"Complete pending purchase below" if pending else "Start simulated purchase"}}</button></form><small>Starting does not add measurements.</small>{% else %}<p class="message error">{{quote_error}}</p>{% endif %}</div></section>
<section class="history"><h2>Purchase history</h2><small>All amounts are USD. Only confirmed simulated fulfillment adds measurements.</small>{% if not history %}<p>No simulated purchases yet.</p>{% endif %}{% for order in history %}<article class="order" data-order="{{order.order_id}}"><div class="orderhead"><strong>{{order.created_at[:10]}} <small>{{order.created_at[11:16]}} UTC</small></strong><span class="status {{order.css}}">{{order.label}}</span></div><dl class="values"><div><dt>Quantity</dt><dd>{{order.quantity}}</dd></div><div><dt>Amount · USD</dt><dd class="money">{{money(order.subtotal_cents)}}</dd></div><div><dt>Tax · USD</dt><dd class="money">{{money(order.tax_cents)}}</dd></div><div><dt>Total · USD</dt><dd class="money">{{money(order.total_cents)}}</dd></div><div><dt>Estimates</dt><dd>Included</dd></div></dl>{% if order.state=='pending' %}<p class="muted">Awaiting simulated confirmation. Balance unchanged.</p><div class="actions">{% for action,label in [('succeeded','Simulate success'),('failed','Simulate failure')] %}<form method="post"><input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="business" value="{{business}}"><input type="hidden" name="order" value="{{order.order_id}}"><input type="hidden" name="attempt" value="{{order.attempt_id}}"><input type="hidden" name="action" value="{{action}}"><button {% if action=='failed' %}class="secondary"{% endif %}>{{label}}</button></form>{% endfor %}</div>{% elif order.state=='failed' %}<p class="muted">Simulated payment failed. No measurements added.</p><form method="post"><input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="business" value="{{business}}"><input type="hidden" name="order" value="{{order.order_id}}"><input type="hidden" name="attempt" value="{{order.retry_id}}"><input type="hidden" name="action" value="retry"><button class="secondary">Retry simulated payment</button></form>{% endif %}</article>{% endfor %}</section></main></body></html>'''

def money(cents):return 'US$'+format(int(cents)/100,',.2f')
def register(app,db,is_employee):
 signer=URLSafeSerializer(app.secret_key,salt='qa-purchase-intent-v1')
 def gated_db():
  # Check environment before opening a DB: never initialize a hosted database here.
  if os.environ.get('AERIQUOTE_QA_PURCHASES')!='1' or os.environ.get('RENDER_SERVICE_ID') or os.environ.get('RENDER_EXTERNAL_HOSTNAME') or request.host.split(':')[0] not in ('127.0.0.1','localhost'):abort(404)
  if is_employee():abort(403)
  con=db()
  try:ledger._disposable(con)
  except ledger.LedgerError:con.close();abort(404)
  return con
 def tax_terms(con,did):
  row=con.execute('SELECT profile_json FROM dealer_profiles WHERE dealer_id=?',(did,)).fetchone()
  profile=json.loads(row['profile_json']) if row else {}
  country=profile.get('country');region=profile.get('province','')
  policy=json.loads(os.environ.get('AERIQUOTE_QA_TOPUP_TAX_POLICY','{}'))
  if not isinstance(policy,dict) or not isinstance(policy.get('rates_bps'),dict):raise ledger.LedgerError('Tax configuration is unavailable. No purchase has been started.')
  key='CA:'+region if country=='CA' else country;rate=policy.get('rates_bps',{}).get(key)
  if not policy.get('version') or country not in ('US','CA') or type(rate) is not int or not 0<=rate<=10000:raise ledger.LedgerError('Tax is not configured for this business’s billing location. No purchase has been started.')
  return country,region,policy,dict(tax_cents=(2500*rate+5000)//10000,total_cents=2500+(2500*rate+5000)//10000)
 @app.route('/qa/purchases',methods=['GET','POST'])
 def qa_purchases():
  con=gated_db();did=str(session['dealer_id']);error='';message=''
  csrf=session.setdefault('qa_purchase_csrf',secrets.token_urlsafe(32))
  try:
   if request.method=='POST':
    origin=request.headers.get('Origin','')
    if request.headers.get('Sec-Fetch-Site')=='cross-site' or (origin and origin not in ('http://'+request.host,'https://'+request.host)) or not secrets.compare_digest(request.form.get('csrf',''),csrf):abort(403)
    if request.form.get('business')!=did:abort(409)
    action=request.form.get('action');credits.lock_account(con,did)
    if action=='start':
     try:payload=signer.loads(request.form.get('intent',''))
     except BadSignature:abort(400)
     if payload.get('business')!=did:abort(409)
     country,region,policy,_=tax_terms(con,did)
     if payload.get('tax_hash')!=orders.digest(dict(country=country,region=region,policy=policy)):raise ledger.LedgerError('Tax configuration changed. Review the updated total before starting.')
     oid=payload['order']
     pending=con.execute("SELECT order_id FROM topup_order_state WHERE dealer_id=? AND state='pending' AND order_id<>?",(did,oid)).fetchone()
     existing=con.execute('SELECT order_id FROM topup_order_terms WHERE dealer_id=? AND order_id=?',(did,oid)).fetchone()
     if pending and not existing:
      con.commit();return redirect('/qa/purchases',code=303)
     orders.create_order(con,did,did,oid,country=country,region=region,tax_policy=policy)
     # Stable first-attempt identity: duplicate form submissions reuse one order/attempt.
     orders.start_attempt(con,did,did,oid,oid+':1')
    elif action in ('retry','succeeded','failed'):
     oid=request.form.get('order','');t=orders.terms(con,did,oid);attempt=request.form.get('attempt','')
     if action=='retry':
      count=int(con.execute('SELECT COUNT(*) AS n FROM topup_attempts WHERE dealer_id=? AND order_id=?',(did,oid)).fetchone()['n'])
      existing=con.execute('SELECT attempt_id FROM topup_attempts WHERE dealer_id=? AND order_id=? AND attempt_id=?',(did,oid,attempt)).fetchone()
      state=con.execute('SELECT state FROM topup_order_state WHERE dealer_id=? AND order_id=?',(did,oid)).fetchone()['state']
      if not existing and (state!='failed' or attempt!=oid+':'+str(count+1)):abort(409)
      orders.start_attempt(con,did,did,oid,attempt)
     else:
      orders.process_event(con,did,'ui:'+attempt+':'+action,oid,attempt,action,currency=t['currency'],total_cents=t['total_cents'])
    else:abort(400)
    con.commit();return redirect('/qa/purchases',code=303)
   cfg=credits.settings(con,did);paid=None if cfg['complimentary'] else credits.paid_usage(con,did)
   if cfg['complimentary']:
    row=con.execute('SELECT lookups FROM account_month_usage WHERE dealer_id=? AND period=?',(did,credits.month_key())).fetchone();monthly=max(0,200-int(row['lookups'] if row else 0))
   elif paid:monthly=max(0,paid['limit']-paid['lookups'])
   else:
    d=con.execute('SELECT lookup_limit FROM dealers WHERE id=?',(did,)).fetchone();u=con.execute('SELECT property_lookups FROM dealer_usage WHERE dealer_id=?',(did,)).fetchone();monthly=max(0,int(d['lookup_limit'])-int(u['property_lookups'] if u else 0))
   rec=ledger.reconciliation(con,did);granted=rec['sources']['granted']['lookups'] if rec['opened'] else rec['bank']['lookups'];purchased=rec['sources']['purchased']['lookups']
   sub=con.execute('SELECT status FROM extra_subscription_state WHERE dealer_id=?',(did,)).fetchone();eligible=bool(cfg['complimentary'] or (paid and sub and sub['status']=='active'))
   quote=None;country='';region='';quote_error=''
   try:country,region,policy,quote=tax_terms(con,did)
   except (ledger.LedgerError,ValueError,TypeError):quote_error='Tax is not configured for this business’s billing location. No purchase can be started.'
   intent=signer.dumps(dict(business=did,order=uuid.uuid4().hex,tax_hash=orders.digest(dict(country=country,region=region,policy=policy)))) if quote else ''
   history=[]
   for row in con.execute('SELECT t.*,s.state FROM topup_order_terms t JOIN topup_order_state s ON s.dealer_id=t.dealer_id AND s.order_id=t.order_id WHERE t.dealer_id=? ORDER BY t.created_at DESC,t.order_id DESC',(did,)).fetchall():
    item=dict(row);attempts=con.execute('SELECT attempt_id FROM topup_attempts WHERE dealer_id=? AND order_id=? ORDER BY attempt_id',(did,item['order_id'])).fetchall();item['attempt_id']=item['order_id']+':'+str(len(attempts));item['retry_id']=item['order_id']+':'+str(len(attempts)+1)
    item['label']={'pending':'Pending','fulfilled':'Simulated success','failed':'Failed','refunded_simulation':'Refund simulated'}.get(item['state'],'Manual review');item['css']='success' if item['state']=='fulfilled' else 'failed' if item['state']=='failed' else '';history.append(item)
   return render_template_string(TEMPLATE,balances=[('Monthly',monthly,'Remaining this billing month'),('Granted',granted,'Extra measurements granted'),('Purchased',purchased,'Purchased extras · no expiry')],business=did,csrf=csrf,intent=intent,pending=any(o['state']=='pending' for o in history),quote=quote,quote_error=quote_error,money=money,history=history,message=message,error=error,jurisdiction=('Canada · '+region if country=='CA' else 'United States'),tax_note=('Configured applicable Canadian tax.' if country=='CA' else 'No tax under the current US billing policy.'),eligibility=('Your subscription is active.' if eligible else 'Purchased extras are held until your subscription is active.'))
  except (ledger.LedgerError,ValueError) as e:
   con.con.rollback();return render_template_string('<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><h1>Purchase not completed</h1><p role="alert">{{error}}</p><p>Your balance was not changed.</p><a href="/qa/purchases">Return to simulated purchases</a>',error=str(e)),409
  finally:con.close()
