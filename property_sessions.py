"""Short-lived property metadata recovery; image bytes and API keys stay in memory."""
import json
import time
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

FIELDS = ('rgb','mask','street','lat','lng','created','mode','fallback_zoom','anchor_lat','anchor_lng','formatted_address','dealer_id','exact_pin','display_lat','display_lng','display_zoom')
CACHES = ('rgb_cache','mask_cache','street_cache','fallback_cache','exact_pin_cache')

def image_url(url, key=None):
    if not url:
        return url
    parts = urlsplit(url)
    query = [(k,v) for k,v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() != 'key']
    if key:
        query.append(('key',key))
    return urlunsplit((parts.scheme,parts.netloc,parts.path,urlencode(query),parts.fragment))

class PropertySessions(dict):
    def __init__(self, database, owner, api_key, ttl=3600, clock=time.time):
        super().__init__()
        self.database, self.owner, self.api_key = database, owner, api_key
        self.ttl, self.clock = ttl, clock

    def persist(self, token):
        value = super().get(token)
        if not value or not value.get('dealer_id'):
            return
        clean = {k:value[k] for k in FIELDS if k in value}
        for field in ('rgb','mask','street'):
            if field in clean:
                clean[field] = image_url(clean[field])
        clean['structure_masks'] = {k:{'roof':v.get('roof')} for k,v in value.get('structure_masks',{}).items()}
        con = self.database()
        try:
            con.execute('DELETE FROM property_sessions WHERE expires_at < ?', (self.clock(),))
            con.execute('INSERT INTO property_sessions(token,dealer_id,expires_at,payload) VALUES(?,?,?,?) ON CONFLICT(token) DO UPDATE SET payload=excluded.payload,expires_at=excluded.expires_at',
                        (token,clean['dealer_id'],float(clean['created'])+self.ttl,json.dumps(clean)))
            con.commit()
        finally:
            con.close()

    def get(self, token, default=None):
        value = super().get(token)
        owner = str(self.owner() or '')
        if value is not None:
            # Older unowned development fixtures stay memory-only. Production sessions
            # are always created with the signed-in business identifier.
            if value.get('dealer_id') and value['dealer_id'] != owner:
                return default
            if value.get('created') and self.clock()-float(value['created']) >= self.ttl:
                super().pop(token,None)
                return default
            return value
        if not owner or not isinstance(token,str) or len(token) != 32:
            return default
        con = self.database()
        try:
            row = con.execute('SELECT payload FROM property_sessions WHERE token=? AND dealer_id=? AND expires_at>?', (token,owner,self.clock())).fetchone()
        finally:
            con.close()
        if not row:
            return default
        value = json.loads(row['payload'])
        if value.get('dealer_id') != owner or self.clock()-float(value['created']) >= self.ttl:
            return default
        key = self.api_key()
        if not key:
            return default
        value['key'] = key
        value.update({field:None for field in CACHES})
        if value.get('street'):
            value['street'] = image_url(value['street'], key)
        for mask in value.get('structure_masks',{}).values():
            mask['mask_cache'] = None
        super().__setitem__(token,value)
        return value
