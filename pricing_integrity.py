"""Independent decimal line-item pricing. No client subtotal or tax amount is trusted."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENT=Decimal('0.01')

def number(value, maximum=None):
    if value is None or isinstance(value,bool) or str(value).strip()=='':raise ValueError('Missing or invalid price input.')
    n=Decimal(str(value))
    if not n.is_finite() or n<0 or (maximum is not None and n>maximum):raise ValueError('Invalid price input.')
    return n

def money(value):return value.quantize(CENT,rounding=ROUND_HALF_UP)
def whole(value):return value.quantize(Decimal(1),rounding=ROUND_HALF_UP)

def calculate(payload):
    q=payload['quote'];p=payload['pricing']
    industry=q.get('businessType')
    if industry not in ('roofing','snow','pressure','paving','landscaping','commercial'):raise ValueError('Choose a valid estimate industry.')
    mode=q.get('measurementMode')
    if mode not in ('auto','area','linear'):raise ValueError('Choose a valid measurement mode.')
    price=number(p['price']);gst=number(p['gst'],100);pst=number(p['pst'],100);disc=number(p['disc'],100)
    tax_mode=p['mode']
    if tax_mode not in ('regular','added','included','discount'):raise ValueError('Choose a valid pricing mode.')
    period=p.get('estimatePeriod','one_time')
    if period not in ('one_time','visit','snowfall','month','season','year') or (industry not in ('snow','landscaping','commercial') and period!='one_time'):raise ValueError('Choose a valid estimate period.')
    areas=q.get('commercialAreas',[]);length=number(q.get('linearFeet',0));surface=industry!='roofing'
    items=[]
    if surface and areas:
        for a in areas:
            qty=number(a['sqft'])
            if qty<=0:raise ValueError('Save every service area before quoting.')
            items.append(money(qty*number(a['rate'])))
        area=sum(number(a['sqft']) for a in areas)
        if length:
            key={'commercial':'commercialLinearRate','snow':'landscapingLinearRate','landscaping':'landscapingLinearRate','pressure':'pressureLinearRate','paving':'pavingLinearRate'}[industry]
            items.append(money(length*number(q[key])))
    else:
        if mode=='linear':area=length
        elif mode=='area':area=whole(number(q['areaSqFt']))
        else:
            src=q.get('measureSource','google');auto=sum((number(r['total_roof_sqft']) for r in q.get('structures',[])),Decimal(0));manual=sum((number(r['surface_sqft']) for r in q.get('manualPlanes',[])),Decimal(0))
            if src=='hybrid':area=auto+manual
            elif src=='manual':area=manual or auto
            elif src=='google':area=auto
            elif src=='adjusted':area=number(q['adjustedArea'])
            else:raise ValueError('Choose a valid roof measurement source.')
        items.append(money(area*price))
        # Legacy combined surface snapshots still represent two distinct services.
        if surface and mode=='linear' and q.get(industry+'Combined'):
            area_qty=whole(number(q['areaSqFt']))
            items.insert(0,money(area_qty*number(q[industry+'AreaRate'])))
    if area<=0:raise ValueError('Save a positive measurement before quoting.')
    subtotal=sum(items,Decimal(0));extra=number(p['extraAmount'])
    if number(payload.get('extra_service_amount',0))!=extra:raise ValueError('Additional services do not match their pricing details.')
    if str(payload.get('extra_service_description','')).strip()!=str(p.get('extraDescription','')).strip():raise ValueError('Additional service descriptions do not match.')
    discount=money(subtotal*disc/100) if tax_mode=='discount' else Decimal(0)
    if tax_mode=='included':
        total=money(subtotal+extra);base=money(total/(1+(gst+pst)/100));ga=money(base*gst/100);pa=money(base*pst/100);base=total-ga-pa
    else:
        base=money(subtotal-discount+extra);ga=money(base*gst/100);pa=money(base*pst/100);total=base+ga+pa
    return dict(area=area,subtotal=subtotal,discount=discount,extraAmount=extra,taxBase=base,gstAmt=ga,pstAmt=pa,total=total)

def pricing_error(payload):
    try:
        expected=calculate(payload);p=payload['pricing']
        for key,value in expected.items():
            actual=number(p[key])
            tolerance=Decimal('0.00001') if key=='area' else Decimal('0.000001')
            if abs(actual-value)>tolerance:return 'Estimate '+key+' does not match independently calculated measurements, rates and taxes. Recreate the estimate.'
        if number(payload['total_price'])!=expected['total']:return 'Estimate total does not match the independently calculated price.'
        if abs(number(payload['total_area'])-expected['area'])>Decimal('0.00001'):return 'Estimate quantity does not match its independently calculated measurement.'
    except (KeyError,ValueError,TypeError,AttributeError,InvalidOperation,OverflowError,ZeroDivisionError):return 'Complete valid measurements, rates, taxes and pricing details before saving the estimate.'
    return ''
