"""Default-OFF subscription enforcement experiment. Disposable local QA ONLY.

No payment adapter, counter mutation, migrations, cleanup or global flag changes.
Existing authentication executes first; this guard cannot override its denials.
"""
import json
import re
from pathlib import Path
from flask import request, session, jsonify, g, Response
from standalone_policy import evaluate


MARKER = 'AERIQUOTE_SUBSCRIPTION_DISPOSABLE_QA_V1'


def lightweight(value):
    """Allowlist retained text/measurements/prices; never return stored imagery."""
    keys={'id','estimate_id','revision_id','dealer_id','created_at','revised_at','saved_at',
          'customer_name','customer_phone','customer_email','customer_notes','address','total_area','total_price',
          'extra_service_description','extra_service_amount','payload','current','revisions','quote','pricing',
          'measurement_mode','area_sqft','linear_feet','businessType','measurementMode','measureSource','areaSqFt','linearFeet',
          'commercialAreas','linearPoints','manualPlanes','structures','points','pts','outline','lat','lng','name','label',
          'sqft','rate','surface_sqft','total_roof_sqft','roof_ground_sqft','segments','pitch_degrees','pitch_confirmed',
          'price','gst','pst','disc','mode','subtotal','area','discount','extraAmount','extraDescription','taxBase','gstAmt','pstAmt','total','estimatePeriod'}
    if isinstance(value,list):return [lightweight(item) for item in value]
    if isinstance(value,dict):return {k:lightweight(v) for k,v in value.items() if k in keys}
    return value


def saved_roofs(payload):
    """Frozen active geometry projection matching the existing saved-map caller."""
    q=payload.get('quote') or {};surface=q.get('businessType')!='roofing';mode=q.get('measurementMode','auto')
    structures=[];manual=[];areas=[];line=[];area_points=[]
    if surface and q.get('commercialAreas'):
        areas=q['commercialAreas'];line=q.get('linearPoints',[]) if q.get('linearFeet',0)>0 else []
    elif mode=='area':area_points=q.get('areaPoints',[])
    elif mode=='linear':
        line=q.get('linearPoints',[])
        if surface and q.get(str(q.get('businessType'))+'Combined'):area_points=q.get('areaPoints',[])
    elif mode=='auto':
        source=q.get('measureSource','google')
        if source=='manual' and sum(p.get('surface_sqft',0) for p in q.get('manualPlanes',[]))>0:manual=q.get('manualPlanes',[])
        elif source in {'manual','google','adjusted'}:structures=q.get('structures',[])
        elif source=='hybrid':structures=q.get('structures',[]);manual=q.get('manualPlanes',[])
    roofs=[]
    def add(kind,points,minimum=3):
        if len(points)>=minimum:
            roofs.append({'kind':kind,'points':[{'lat':float(p['lat'] if isinstance(p,dict) else p[0]),'lng':float(p['lng'] if isinstance(p,dict) else p[1])} for p in points]})
    for i,roof in enumerate(structures):add('manual' if roof.get('manually_measured') else 'house' if i==0 else 'garage',roof.get('outline',[]))
    for roof in manual:add('manual',roof.get('points',[]))
    for area in areas or [{'points':area_points}]:add('area',area.get('points',[]))
    add('linear',line,2)
    return roofs


def register(app, estimate_db, db_path, is_head_office):
    app.config.setdefault('SUBSCRIPTION_ACCESS_QA', False)

    def enabled():
        if app.config['SUBSCRIPTION_ACCESS_QA'] is not True or not app.testing:
            return False
        target=db_path()
        if not target:return False
        path=Path(target).resolve()
        marker=path.with_suffix('.qa-marker')
        try:
            return (str(path)==app.config.get('SUBSCRIPTION_QA_DATABASE')
                    and marker.read_text().strip()==MARKER
                    and callable(app.config.get('SUBSCRIPTION_QA_POLICY_PROVIDER')))
        except OSError:
            return False

    def unknown(reason):
        g.subscription_qa={'state':'unknown','expiry':None,'issue':reason}

    def protected():
        path=request.path
        return (path=='/' or path.startswith(('/api/estimates','/api/estimate-storage-status','/api/workspace-drafts','/qa/subscription','/api/account/profile'))
                or path in {'/property','/property/accept','/address-preview','/locate-building','/structure','/saved-estimate-report-map'}
                or path.startswith(('/manual-report-map/','/exact-pin','/fallback-','/wide-aerial/','/rgb/','/mask/','/street/','/structure-mask/','/mapbox-aerial/')))

    def deny(state):
        return jsonify(error=('Paid access ended. Saved estimates are read-only.' if state=='retained_read_only' else 'Saved estimate access has expired.'),
                       code='subscription_'+state,expiry=g.subscription_qa.get('expiry')),403

    @app.before_request
    def qa_subscription_access():
        if not enabled() or not protected() or not session.get('dealer_id'):
            return None
        did=str(session['dealer_id'])
        if is_head_office() and (request.path.startswith(('/api/estimates','/qa/subscription/estimates')) or request.path in {'/saved-estimate-report-map','/api/account/profile'}):
            return jsonify(error='Business estimates are not available to Head Office.'),403
        # Complimentary/dealer entitlement is established from existing app data,
        # not an invented successful paid subscription in the explicit snapshot.
        con=estimate_db()
        try:
            account=con.execute('SELECT plan_code FROM dealers WHERE id=?',(did,)).fetchone()
            comp=con.execute('SELECT complimentary FROM account_allowances WHERE dealer_id=?',(did,)).fetchone()
        finally:con.close()
        if (comp and comp['complimentary']) or (account and account['plan_code'] not in {'basic','pro','business'}):
            g.subscription_qa={'state':'existing_dealer_access','expiry':None,'issue':None}
            return None
        try:
            snapshot=app.config['SUBSCRIPTION_QA_POLICY_PROVIDER'](did)
            if not isinstance(snapshot,dict) or snapshot.get('business_id')!=did:
                unknown('missing_or_wrong_business_policy');return None
            result=evaluate(snapshot)
        except Exception:
            unknown('policy_provider_unavailable');return None
        access=result.get('access')
        if result.get('review_required') or not access or access['state'] not in {'paid_active','retained_read_only','expired'}:
            unknown('missing_or_ambiguous_policy_facts');return None
        g.subscription_qa={'state':access['state'],'expiry':access['full_expiry'],'issue':None,'lightweight_only':access['state']=='retained_read_only' and not access['readable_scopes']['full']}
        if access['state']=='paid_active':return None
        if request.path=='/qa/subscription-policy':return None
        if access['state']=='expired':return deny('expired')
        path=request.path
        if g.subscription_qa.get('lightweight_only') and path=='/api/account/profile':
            return deny('retained_read_only') # Existing PDF/Print preflight must not authorize expired full content.
        readonly_get=(path in {'/','/api/account/profile','/api/estimates','/api/estimate-storage-status'}
                      or re.fullmatch(r'/api/estimates/[^/]+(?:/versions)?',path)
                      or re.fullmatch(r'/qa/subscription/estimates/[^/]+/download',path))
        if request.method in {'GET','HEAD'} and readonly_get:return None
        if path=='/saved-estimate-report-map' and request.method=='POST' and not g.subscription_qa.get('lightweight_only'):
            try:
                incoming=(request.get_json(silent=True) or {}).get('roofs')
                normalized=[{'kind':str(roof.get('kind') or 'house'),'points':[{'lat':float(p['lat']),'lng':float(p['lng'])} for p in roof.get('points',[])]} for roof in incoming or []]
                key=json.dumps(normalized,sort_keys=True,allow_nan=False)
                con=estimate_db()
                try:
                    rows=con.execute('SELECT payload FROM estimates WHERE dealer_id=? UNION ALL SELECT payload FROM estimate_revisions WHERE dealer_id=?',(did,did)).fetchall()
                finally:con.close()
                if incoming and any(json.dumps(saved_roofs(json.loads(row['payload'])),sort_keys=True,allow_nan=False)==key for row in rows):return None
            except (ValueError,TypeError,KeyError,AttributeError):pass
        return deny('retained_read_only')

    @app.after_request
    def subscription_qa_diagnostic(response):
        if getattr(g,'subscription_qa',None):
            if g.subscription_qa.get('lightweight_only') and response.status_code==200 and response.is_json and request.path!='/qa/subscription-policy':
                response.set_data(json.dumps(lightweight(response.get_json())))
            response.headers['X-AeriQuote-QA-Subscription']=g.subscription_qa['state']
            if g.subscription_qa.get('issue'):response.headers['X-AeriQuote-QA-Policy-Issue']=g.subscription_qa['issue']
            response.headers['Cache-Control']='no-store'
        return response

    @app.get('/qa/subscription-policy')
    def subscription_qa_policy():
        if not enabled():return jsonify(error='Not found'),404
        return jsonify(getattr(g,'subscription_qa',{'state':'unknown','expiry':None}))

    @app.get('/qa/subscription/estimates/<estimate_id>/download')
    def subscription_qa_saved_download(estimate_id):
        if not enabled():return jsonify(error='Not found'),404
        if is_head_office():return jsonify(error='Business estimates are private.'),403
        con=estimate_db()
        try:
            row=con.execute('SELECT payload FROM estimates WHERE id=? AND dealer_id=?',(estimate_id,str(session.get('dealer_id') or ''))).fetchone()
        finally:con.close()
        if not row:return jsonify(error='Estimate not found'),404
        return Response(row['payload'],content_type='application/json',headers={'Content-Disposition':'attachment; filename="saved-estimate.json"','Cache-Control':'no-store'})
