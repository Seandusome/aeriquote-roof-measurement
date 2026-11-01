"""Opt-in expiry QA using Flask's ordinary signed-cookie max-age validation."""
from datetime import timedelta
from urllib.parse import urlsplit


def configure_qa_session_expiry(app, environ):
    if environ.get('RENDER_SERVICE_ID') != 'srv-db5a2g5ckfvc739fui70':
        return False
    try:
        database = urlsplit(environ.get('DATABASE_URL', ''))
        seconds = int(environ.get('AERIQUOTE_QA_SESSION_LIFETIME_SECONDS', ''))
    except (ValueError, TypeError):
        return False
    if (database.hostname != 'dpg-dbj4f7lg1s2s73eob8t0-a'
            or database.path != '/aeriquote_recovery_qa' or not 1 <= seconds <= 3600):
        return False
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(seconds=seconds)
    return True
