"""Loopback-only disposable-fixture policy view. Not registered with AeriQuote.

Reads a sealed fictional SQLite database and explicit QA-only payment/retention
facts. No app import, migrations, event processing, writes or enforcement.
"""
import ast
import hashlib
import html
import json
from pathlib import Path
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import standalone_policy as policy

MARKER = 'AERIQUOTE_DISPOSABLE_POLICY_QA_V1'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FixtureReader:
    def __init__(self, root):
        self.root = Path(root).resolve(strict=True)
        self.manifest = json.loads((self.root / 'manifest.json').read_text())
        if self.manifest.get('kind') != MARKER:
            raise ValueError('Not an explicitly marked disposable policy fixture')
        self.db = self.root / 'accounts.sqlite'
        self.facts_path = self.root / 'facts.json'
        for name, path in [('database', self.db), ('facts', self.facts_path)]:
            if path.resolve().parent != self.root or path.is_symlink():
                raise ValueError('Fixture file escaped approved directory')
            if digest(path) != self.manifest[name + '_sha256']:
                raise ValueError('Fixture digest mismatch: ' + name)
        self.facts = json.loads(self.facts_path.read_text())
        if set(self.facts) != set(self.manifest['accounts']) or not all(k.startswith('qa-fictional-') for k in self.facts):
            raise ValueError('Fictional account allowlist mismatch')

    def connect(self):
        if digest(self.db) != self.manifest['database_sha256']:
            raise ValueError('Fixture changed; refusing to read unverified target')
        con = sqlite3.connect(self.db.as_uri() + '?mode=ro&immutable=1', uri=True)
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA query_only=ON')
        allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}
        con.set_authorizer(lambda action, *_: sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY)
        return con

    def snapshot(self, account_id):
        if account_id not in self.facts:
            raise KeyError('Unknown fictional account')
        f = self.facts[account_id]
        gaps = []
        con = self.connect()
        try:
            dealer = con.execute('SELECT id,status,plan_code,created_at FROM dealers WHERE id=?', (account_id,)).fetchone()
            if not dealer:
                return None, ['Account missing from fixture database']
            period = dict(f.get('period') or {})
            if not period.get('payment_status'):
                gaps.append('Payment confirmation unknown; active account/plan_code is not proof of payment')
            retention = dict(f.get('retention') or {})
            for field in ('paid_access_end', 'legacy_full', 'legacy_lightweight', 'full_present', 'lightweight_present'):
                if field not in retention:
                    gaps.append('Retention fact unknown: ' + field)
            if 'upgrades' not in f:
                gaps.append('Upgrade attribution inventory unknown')
            used = None
            if period.get('start'):
                key = policy.instant(period['start']).isoformat()
                row = con.execute('SELECT lookups,estimates FROM account_subscription_usage WHERE dealer_id=? AND period_start=?', (account_id, key)).fetchone()
                if row:
                    used = dict(row)
                else:
                    gaps.append('Verified-period usage missing; do not substitute provisional/lifetime counters')
            else:
                gaps.append('Verified period unknown')
            bank = con.execute('SELECT lookup_bonus,estimate_bonus FROM account_allowances WHERE dealer_id=?', (account_id,)).fetchone()
            if bank is None:
                gaps.append('Extra-bank balance unknown')
            estimate = con.execute('SELECT id,payload FROM estimates WHERE dealer_id=? ORDER BY created_at DESC LIMIT 1', (account_id,)).fetchone()
            if estimate is None and (retention.get('full_present') or retention.get('lightweight_present')):
                gaps.append('Retention inventory claims content but estimate row is absent')
            if gaps:
                return None, gaps
            period['plan'] = dealer['plan_code']
            result = dict(schema=1, business_id=account_id, now=f['now'], security_eligible=dealer['status']=='active',
                          period=period, retention=retention, used=used,
                          extras=dict(lookups=bank['lookup_bonus'], estimates=bank['estimate_bonus']), upgrades=f['upgrades'])
            for optional in ('cancellation', 'reactivation', 'downgrade'):
                if optional in f:
                    result[optional] = f[optional]
            return result, []
        finally:
            con.close()

    def evaluate(self, account_id):
        snapshot, gaps = self.snapshot(account_id)
        calculated = policy.evaluate(snapshot) if snapshot else None
        return dict(account_id=account_id, case=self.facts[account_id]['case'],
                    provenance='FICTIONAL QA payment/retention facts + read-only app-schema account rows',
                    missing_facts=gaps, calculated=calculated,
                    state=(calculated['access']['state'] if calculated and calculated['access'] else 'unknown'),
                    expiry=(calculated['access']['full_expiry'] if calculated and calculated['access'] else None),
                    deletion_authorized=False, enforcement_enabled=False)


def app_guard_probe(reader, account_id):
    """Execute exact existing auth guard function, NOT app startup or routes.

    Only read-only connections; fictional Flask request/session. Permission result
    is a guard-component observation, not proof that a real save/PDF succeeds.
    """
    from flask import Flask, request, session, Response, jsonify, redirect
    from account_recovery import auth_version
    source = Path(__file__).with_name('app.py').read_text()
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name=='require_dealer_login')
    node.decorator_list = []
    scope = dict(request=request, session=session, Response=Response, jsonify=jsonify, redirect=redirect,
                 estimate_db=reader.connect, auth_version=auth_version,
                 is_employee=lambda: session.get('account_type')=='employee')
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'exact-app-auth-guard', 'exec'), scope)
    app = Flask('fictional-policy-guard-probe')
    app.secret_key = 'disposable-fixture-only-not-an-account-credential'
    observed = {}
    for method, path in [('GET','/api/estimates'), ('POST','/api/estimates')]:
        with app.test_request_context(path, method=method):
            session['dealer_id'] = account_id
            session['account_type'] = 'owner'
            session['auth_version'] = 0
            response = scope['require_dealer_login']()
            observed[method] = 'guard_allows' if response is None else 'guard_denies'
    return dict(scope='exact auth guard component only; no endpoint execution', observations=observed,
                source_sha256=hashlib.sha256(ast.get_source_segment(source,node).encode()).hexdigest())


def provisional_usage_probe(reader, account_id):
    # Existing read-only application calculation, initialize=False explicitly.
    from account_credits import paid_usage
    con = reader.connect()
    try:
        return paid_usage(con, account_id, now=policy.instant(reader.facts[account_id]['now']), initialize=False)
    finally:
        con.close()


def render(rows):
    def esc(v): return html.escape(str(v))
    body = []
    for row in rows:
        calc = row['calculated'] or {}
        access = calc.get('access') or {}
        schedule = calc.get('schedule') or {}
        body.append('<tr>' + ''.join('<td>'+esc(v)+'</td>' for v in [
            row['case'], row['state'], row['expiry'] or 'UNKNOWN',
            schedule.get('cancellation_effective_at') or '—',
            'Review required' if row['missing_facts'] or calc.get('review_required') else 'Calculated',
            'NEVER — diagnostic view only']) + '</tr>')
    details = ''.join('<details><summary>'+esc(r['case'])+' — facts and diagnostic output</summary><pre>'+esc(json.dumps(r,indent=2))+'</pre></details>' for r in rows)
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AeriQuote disposable policy QA</title><style>body{font:16px system-ui;margin:0;padding:24px;background:#f5f7fa;color:#172d43}main{max-width:1200px;margin:auto}h1{font-size:28px}.notice{padding:18px;border:2px solid #aa6800;background:#fff3d7;line-height:1.5}.scroll{overflow:auto}table{width:100%;border-collapse:collapse;background:white;margin:24px 0}td,th{text-align:left;vertical-align:top;padding:12px;border:1px solid #d6dfe7}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}details{background:white;padding:16px;margin:12px 0}summary{cursor:pointer;font-weight:bold}@media(max-width:600px){body{padding:12px}h1{font-size:23px}}</style><main><h1>AeriQuote — disposable policy QA</h1><p class="notice"><strong>FICTIONAL DATA · READ ONLY · NO ENFORCEMENT</strong><br>Calculated states do not change application access, balances, payments or records. Missing facts remain unknown. No state authorizes deletion. This view is not part of the public app.</p><div class="scroll"><table><thead><tr><th>Fictional case</th><th>Calculated access</th><th>Full-content expiry (UTC)</th><th>Cancellation effective (UTC)</th><th>Evidence status</th><th>Delete permission</th></tr></thead><tbody>''' + ''.join(body) + '</tbody></table></div>'+details+'</main></html>'


def serve(reader, port=0):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urlsplit(self.path).path
            if path == '/qa/policy':
                payload = render([reader.evaluate(k) for k in reader.facts]).encode()
                content_type = 'text/html; charset=utf-8'
            elif path.startswith('/qa/policy/') and path.endswith('.json'):
                key = path[len('/qa/policy/'):-5]
                if key not in reader.facts:
                    self.send_error(404); return
                payload = json.dumps(reader.evaluate(key)).encode()
                content_type = 'application/json'
            else:
                self.send_error(404); return
            self.send_response(200)
            self.send_header('Content-Type',content_type)
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; form-action 'none'")
            self.send_header('Content-Length',str(len(payload)))
            self.end_headers(); self.wfile.write(payload)
        def do_POST(self): self.send_error(405)
        def do_PUT(self): self.send_error(405)
        def do_DELETE(self): self.send_error(405)
        def log_message(self,*_): pass
    return ThreadingHTTPServer(('127.0.0.1',port), Handler)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture-root',required=True)
    parser.add_argument('--port',type=int,default=0)
    args=parser.parse_args();server=serve(FixtureReader(args.fixture_root),args.port)
    print('QA-only loopback view: http://127.0.0.1:'+str(server.server_port)+'/qa/policy',flush=True)
    server.serve_forever()
