"""Explicit unit notation without changing civic numbers or numbered streets."""
import re
CANADIAN_PROVINCES = {'AB','BC','MB','NB','NL','NS','NT','NU','ON','PE','QC','SK','YT'}

def unit_address(address, province=''):
    text = str(address or '').strip()
    first, comma, tail = text.partition(',')
    suffix = ','+tail if comma else ''
    # Unit-labelled prefixes are explicit in either country. Hyphen/slash prefixes
    # are treated as Canadian unit notation only when the property province is CA.
    match = re.match(r'^(?:unit|suite|apt\.?|#)\s*([\w-]+)\s+(\d+[A-Za-z]?)\s+(.+)$',first,re.I)
    if not match and str(province).upper() in CANADIAN_PROVINCES:
        match = re.match(r'^(\d+[A-Za-z]?)\s*[-/]\s*(\d+[A-Za-z]?)\s+(.+)$',first)
    if match:
        unit,number,street = match.groups()
        return f'{number} {street} #{unit}{suffix}', number
    match = re.match(r'^(\d+[A-Za-z]?)\s+',first)
    return text, match.group(1) if match else ''

def building_address(address):
    text = str(address or '').strip()
    province = next((p for p in CANADIAN_PROVINCES if re.search(r'\b'+p+r'\b',text)), '')
    text,_ = unit_address(text,province)
    first,comma,tail = text.partition(',')
    first = re.sub(r'\s+(?:#\s*|(?:unit|suite|apt\.?)\s+)[\w-]+\s*$','',first,flags=re.I)
    return first+(','+tail if comma else '')
