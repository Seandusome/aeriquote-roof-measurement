"""Privacy boundary for application-owned Python and Gunicorn logs.

No free-text messages, query strings, headers, bodies, exception values or source
lines are emitted. Unknown diagnostics keep level, event ID and code location.
This does not rewrite requests, responses, credentials, database data or sessions.
"""
import logging
import uuid
from collections.abc import Mapping
from urllib.parse import urlsplit

_MODULES = frozenset(('app','account_recovery','account_credits','activation_metrics',
    'support_center','support_inbound','storage_checks','measurement_integrity',
    'pricing_integrity','property_sessions','property_address','saved_estimate_edit',
    'safe_logging'))
_SAFE_MESSAGES = frozenset((
    'Password reset email delivery failed; inspect provider status and sender configuration.',
    'Support notification failed; the request remains saved in Head Office.',
    'Support reply could not be confirmed; its text remains saved for retry.',
    'Incoming reply is saved but support notification failed.',
    'Incoming support email retrieval failed; webhook delivery should retry.',
    'Property imagery recovery metadata could not be retained',
))
_EVENTS = {
    'Starting gunicorn %s':'server_start', 'Listening at: %s (%s)':'server_listening',
    'Using worker: %s':'worker_type', 'Booting worker with pid: %s':'worker_start',
    'Worker exiting (pid: %s)':'worker_exit', 'Handling signal: %s':'server_signal',
    'Shutting down: %s':'server_stop', 'Exception in worker process':'worker_exception',
}
_EXCEPTION_TYPES = frozenset(('Exception','RuntimeError','ValueError','TypeError',
    'KeyError','IndexError','AttributeError','OSError','PermissionError','TimeoutError',
    'ConnectionError','OperationalError','IntegrityError','HTTPError','URLError'))


def _number(value, limit=999999999):
    # Never call repr/str on objects supplied in a log event.
    if isinstance(value,(int,float)) and not isinstance(value,bool):
        return value if 0 <= value <= limit else '-'
    if isinstance(value,str) and len(value)<20:
        try:
            parsed=float(value)
            return parsed if 0 <= parsed <= limit else '-'
        except ValueError:
            pass
    return '-'


def _route(path):
    if not isinstance(path,str):return 'other'
    try:path=urlsplit(path).path
    except ValueError:return 'other'
    if path in ('/reset-password','/forgot-password'):return 'password_recovery'
    if path in ('/dealer-login','/dealer-logout','/login','/logout'):return 'authentication'
    for prefix,category in (('/api/estimates','estimates'),('/api/public/support','support'),
                            ('/head-office/support','support'),('/static/','static')):
        if path.startswith(prefix):return category
    return 'other'


def _sanitize(record):
    if getattr(record,'_aq_safe',False):return record
    name=record.name if record.name in ('gunicorn.access','gunicorn.error','werkzeug') else 'application'
    raw=record.msg
    if name=='gunicorn.access' and isinstance(record.args,Mapping):
        atoms=record.args
        method=atoms.get('m')
        method=method if method in ('GET','POST','PUT','PATCH','DELETE','HEAD','OPTIONS') else 'OTHER'
        record.msg='http method=%s route=%s status=%s bytes=%s seconds=%s' % (
            method,_route(atoms.get('U')),_number(atoms.get('s'),599),
            _number(atoms.get('B')),_number(atoms.get('L'),86400))
    elif isinstance(raw,str) and raw in _SAFE_MESSAGES and not record.args:
        record.msg=raw
    else:
        event=_EVENTS.get(raw,'runtime_event') if isinstance(raw,str) else 'runtime_event'
        exc='none';frames=[]
        if record.exc_info:
            kind=record.exc_info[0].__name__ if record.exc_info[0] else 'Exception'
            exc=kind if kind in _EXCEPTION_TYPES else 'Exception'
            tb=record.exc_info[2]
            while tb and len(frames)<8:
                module=tb.tb_frame.f_globals.get('__name__')
                frames.append('%s:%s' % (module if module in _MODULES else 'runtime',tb.tb_lineno))
                tb=tb.tb_next
        record.msg='event=%s id=%s exception=%s frames=%s [details redacted]' % (
            event,uuid.uuid4().hex,exc,','.join(frames) or 'none')
    record.args=()
    record.exc_info=None
    record.exc_text=None
    record.stack_info=None
    record.name=name
    module=record.module if record.module in _MODULES else 'runtime'
    record.module=module;record.filename=module+'.py';record.pathname=record.filename
    record.funcName='redacted'
    record._aq_safe=True
    return record


def install_safe_logging():
    """Idempotent process-wide record boundary, including future handlers/loggers."""
    current=logging.getLogRecordFactory()
    if getattr(current,'_aq_safe_factory',False):return
    def factory(*args,**kwargs):
        return _sanitize(current(*args,**kwargs))
    factory._aq_safe_factory=True
    logging.setLogRecordFactory(factory)
