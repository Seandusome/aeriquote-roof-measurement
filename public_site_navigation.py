"""Presentation-only links for an already validated website session."""
import html
import re
from urllib.parse import parse_qs, urlsplit

INDUSTRIES = {
    'roofing': 'Roofing', 'snow': 'Snow Removal',
    'pressure': 'Pressure Washing', 'paving': 'Paving & Sealcoating',
    'landscaping': 'Landscaping', 'commercial': 'Commercial Properties',
}
PAGES = dict(zip(
    ['roofing', 'snow-removal', 'pressure-washing', 'paving-sealcoating',
     'landscaping', 'commercial-property'], INDUSTRIES))
TRIAL_PATHS = {'/site/start-free-trial', '/site/trial-signup'}


def industry_for(filename, fallback='roofing', query=''):
    value = parse_qs(query).get('industry', [''])[0]
    if value in INDUSTRIES:
        return value
    slug = filename.removesuffix('.html').removeprefix('industries/')
    return PAGES.get(slug, fallback if fallback in INDUSTRIES else 'roofing')


def measuring_url(industry):
    return '/?industry=' + (industry if industry in INDUSTRIES else 'roofing')


def signed_in_links(document, filename, fallback):
    """Rewrite only our own entry CTAs; never compile public HTML as a template."""
    current = industry_for(filename, fallback)

    def replace(match):
        anchor = match.group(0)
        href = re.search(r'\bhref\s*=\s*([\'"])(.*?)\1', anchor, re.I | re.S)
        if not href:
            return anchor
        url = urlsplit(html.unescape(href.group(2)))
        if url.scheme or url.netloc:
            return anchor
        path = url.path.removesuffix('.html')
        if path not in TRIAL_PATHS and path != '/dealer-login':
            return anchor
        industry = industry_for(filename, current, url.query)
        label = 'Start measuring' if path in TRIAL_PATHS else 'Open app'
        opening = anchor[:anchor.index('>') + 1]
        opening = opening[:href.start(2)] + measuring_url(industry) + opening[href.end(2):]
        opening = re.sub(r'\s+aria-label\s*=\s*([\'"]).*?\1', '', opening, flags=re.I | re.S)
        opening = opening[:-1] + ' aria-label="' + html.escape(
            label + ' — ' + INDUSTRIES[industry], quote=True) + '">'
        return opening + label + '</a>'

    return re.sub(r'<a\b[^>]*>.*?</a\s*>', replace, document, flags=re.I | re.S)
