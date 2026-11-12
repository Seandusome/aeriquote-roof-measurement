"""Strict Mapbox address validation. No credentials or provider URLs reach clients."""
import math
import re

_ALIASES = {'avenue':'ave','street':'st','road':'rd','crescent':'cres','place':'pl','square':'sq','trail':'trl','boulevard':'blvd','drive':'dr','court':'ct','north':'n','south':'s','east':'e','west':'w','northeast':'ne','northwest':'nw','southeast':'se','southwest':'sw'}

def street_key(value):
    words=re.findall(r'[a-z0-9]+', str(value).lower())
    return tuple(_ALIASES.get(word,word) for word in words)

def verified_address(feature, requested):
    p=feature.get('properties') or {}
    match=p.get('match_code') or {}
    label=str(p.get('full_address') or '').strip()
    name=p.get('name') or label.split(',')[0]
    issues=[]
    if p.get('feature_type')!='address':issues.append('The result is not a property address.')
    if match.get('street')!='matched' or street_key(requested.split(',')[0])!=street_key(name):
        issues.append('The returned street does not match the requested street.')
    if match.get('address_number')!='matched':issues.append('The building number was not matched.')
    if match.get('confidence') not in {'exact','high'}:issues.append('The address match is uncertain.')
    if (p.get('coordinates') or {}).get('accuracy')!='rooftop':issues.append('The pin is not a rooftop match.')
    coordinates=(feature.get('geometry') or {}).get('coordinates') or []
    try:
        lng,lat=map(float,coordinates)
        if not all(map(math.isfinite,[lat,lng])) or abs(lat)>85.05112878 or abs(lng)>180:raise ValueError()
    except (TypeError,ValueError):
        issues.append('The property pin is invalid.');lat=lng=None
    if not label:issues.append('The matched address is missing.')
    if issues:raise ValueError(' '.join(issues))
    return label,lat,lng
