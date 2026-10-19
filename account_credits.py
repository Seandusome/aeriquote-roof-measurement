"""Head Office allowances, audited grants and complimentary monthly dealer usage."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import uuid, secrets, hmac
from flask import request, session, Response, redirect, render_template_string

BRANDS = {'': 'No dealer brand', 'shingle_guard': 'Shingle Guard', 'shinglextra': 'ShingleXtra'}

def month_key(now=None):
    return (now or datetime.now(timezone.utc)).astimezone(ZoneInfo('America/Edmonton')).strftime('%Y-%m')

def init_credit_db(con):
    con.execute("CREATE TABLE IF NOT EXISTS account_admin_roles (dealer_id TEXT PRIMARY KEY)")
    con.execute("CREATE TABLE IF NOT EXISTS account_credit_migrations (id TEXT PRIMARY KEY)")
    if not con.execute("SELECT id FROM account_credit_migrations WHERE id='head-office-role-v1'").fetchone():
        # Preserve existing roles once; never derive new roles from editable names.
        con.execute("""INSERT INTO account_admin_roles(dealer_id) SELECT id FROM dealers
            WHERE lower(trim(dealer_name))='head office' OR lower(trim(email))='sdusome@diitalk.com'
            ON CONFLICT(dealer_id) DO NOTHING""")
        con.execute("INSERT INTO account_credit_migrations(id) VALUES('head-office-role-v1')")
    con.execute("""CREATE TABLE IF NOT EXISTS account_allowances (
      dealer_id TEXT PRIMARY KEY, complimentary INTEGER NOT NULL DEFAULT 0,
      brand TEXT NOT NULL DEFAULT '', lookup_bonus INTEGER NOT NULL DEFAULT 0,
      estimate_bonus INTEGER NOT NULL DEFAULT 0)""")
    con.execute("""CREATE TABLE IF NOT EXISTS account_month_usage (
      dealer_id TEXT NOT NULL, period TEXT NOT NULL, lookups INTEGER NOT NULL DEFAULT 0,
      estimates INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(dealer_id,period))""")
    con.execute("""CREATE TABLE IF NOT EXISTS account_credit_audit (
      id TEXT PRIMARY KEY, dealer_id TEXT NOT NULL, actor TEXT NOT NULL,
      created_at TEXT NOT NULL, action TEXT NOT NULL, amount INTEGER NOT NULL,
      reason TEXT NOT NULL, details TEXT NOT NULL)""")

def settings(con, did):
    row = con.execute('SELECT * FROM account_allowances WHERE dealer_id=?', (did,)).fetchone()
    return dict(row) if row else dict(dealer_id=did, complimentary=0, brand='', lookup_bonus=0, estimate_bonus=0)

def lock_account(con, did):
    # Serialize grants and both usage channels against this owner, including employees.
    if con.postgres:
        return con.execute('SELECT * FROM dealers WHERE id=? FOR UPDATE', (did,)).fetchone()
    con.execute('BEGIN IMMEDIATE')
    return con.execute('SELECT * FROM dealers WHERE id=?', (did,)).fetchone()

def consume(con, did, kind, normal_used, normal_limit, now=None):
    """Caller holds owner lock. Returns allowed, used, limit; commits with caller."""
    cfg = settings(con, did)
    bonus_col = 'lookup_bonus' if kind == 'lookups' else 'estimate_bonus'
    used, limit = normal_used, normal_limit
    if cfg['complimentary']:
        period = month_key(now)
        con.execute('INSERT INTO account_month_usage(dealer_id,period) VALUES(?,?) ON CONFLICT(dealer_id,period) DO NOTHING', (did, period))
        row = con.execute('SELECT lookups,estimates FROM account_month_usage WHERE dealer_id=? AND period=?', (did, period)).fetchone()
        used, limit = int(row[kind]), 200
    if limit > 0 and used >= limit:
        if int(cfg[bonus_col]) <= 0:
            return False, used, limit
        con.execute(f'UPDATE account_allowances SET {bonus_col}={bonus_col}-1 WHERE dealer_id=?', (did,))
    if cfg['complimentary']:
        con.execute(f'UPDATE account_month_usage SET {kind}={kind}+1 WHERE dealer_id=? AND period=?', (did, month_key(now)))
    return True, used + 1, limit

def register_credits(app, db, is_head_office):
    @app.route('/head-office/credits', methods=['GET', 'POST'])
    def credit_console():
        if not is_head_office():
            return Response('Head Office permission required.', status=403)
        token = session.setdefault('credit_csrf', secrets.token_urlsafe(32))
        error = ''
        if request.method == 'POST':
            if not hmac.compare_digest(str(request.form.get('csrf') or ''), token):
                return Response('Please reload this page and try again.', status=403)
            did = str(request.form.get('dealer_id') or '')
            reason = str(request.form.get('reason') or '').strip()
            action = request.form.get('action')
            operation = str(request.form.get('operation') or '')
            try:
                uuid.UUID(operation)
                amount = int(request.form.get('amount') or 0)
                if not reason or len(reason)>500: raise ValueError('Enter a reason of 1 to 500 characters.')
                if action not in {'grant','configure','disable','reactivate'}: raise ValueError('Unknown action.')
                if action=='grant' and not 1<=amount<=10000: raise ValueError('Choose 1 to 10,000 credits.')
                brand = str(request.form.get('brand') or '')
                if brand not in BRANDS: raise ValueError('Unknown brand.')
                complimentary = int(request.form.get('complimentary')=='1')
                con = db()
                try:
                    account = lock_account(con, did)
                    if not account: raise ValueError('Account not found.')
                    if con.execute('SELECT dealer_id FROM account_admin_roles WHERE dealer_id=?',(did,)).fetchone() or str(account['email']).lower()=='sdusome@diitalk.com':
                        raise ValueError('Head Office accounts are protected.')
                    # A repeated browser submission never awards credits twice.
                    if not con.execute('SELECT id FROM account_credit_audit WHERE id=?', (operation,)).fetchone():
                        con.execute('INSERT INTO account_allowances(dealer_id) VALUES(?) ON CONFLICT(dealer_id) DO NOTHING', (did,))
                        before = settings(con, did)
                        if action=='grant':
                            con.execute('UPDATE account_allowances SET lookup_bonus=lookup_bonus+?,estimate_bonus=estimate_bonus+? WHERE dealer_id=?', (amount, amount, did))
                            details = f'Added {amount} measurements and {amount} estimates. Extra credits carry forward.'
                        elif action in {'disable','reactivate'}:
                            status='disabled' if action=='disable' else 'active'
                            con.execute('UPDATE dealers SET status=? WHERE id=?',(status,did))
                            if action=='disable':
                                con.execute('UPDATE account_allowances SET complimentary=0 WHERE dealer_id=?',(did,))
                                identities=[('owner',did)]+[('employee',r['id']) for r in con.execute('SELECT id FROM dealer_employees WHERE dealer_id=?',(did,)).fetchall()]
                                for kind,identity in identities:
                                    con.execute('INSERT INTO account_auth_versions(account_type,account_id,version) VALUES(?,?,1) ON CONFLICT(account_type,account_id) DO UPDATE SET version=account_auth_versions.version+1',(kind,identity))
                            details=f"Account {account['status']} → {status}. "+('Complimentary monthly access stopped; owner and employee access blocked. ' if action=='disable' else 'Monthly access remains off until explicitly enabled. ')+'Saved estimates and unused extra credits retained.'
                        else:
                            con.execute('UPDATE account_allowances SET complimentary=?,brand=? WHERE dealer_id=?', (complimentary, brand, did))
                            details = f"Complimentary {before['complimentary']} → {complimentary}; brand {before['brand']} → {brand}. Existing usage preserved."
                        con.execute('INSERT INTO account_credit_audit(id,dealer_id,actor,created_at,action,amount,reason,details) VALUES(?,?,?,?,?,?,?,?)',
                                    (operation,did,str(session['dealer_id']),datetime.now(timezone.utc).isoformat(),action,amount if action=='grant' else 0,reason,details))
                    con.commit()
                finally: con.close()
                from urllib.parse import urlencode
                return redirect('/head-office/credits?'+urlencode({'saved':'1','q':account['email']}))
            except (ValueError, TypeError) as exc:
                error = str(exc) or 'Check the entered values.'
        query=str(request.args.get('q') or '').strip()[:200]
        con = db()
        try:
            accounts = [dict(r) for r in con.execute("""SELECT d.id,d.dealer_name,d.email,d.plan_code,d.status,
                COALESCE(a.complimentary,0) AS complimentary,COALESCE(a.brand,'') AS brand,
                COALESCE(a.lookup_bonus,0) AS lookup_bonus,COALESCE(a.estimate_bonus,0) AS estimate_bonus,p.profile_json
                FROM dealers d LEFT JOIN dealer_profiles p ON p.dealer_id=d.id LEFT JOIN account_allowances a ON a.dealer_id=d.id
                WHERE lower(d.dealer_name)<>'head office' AND lower(d.email)<>'sdusome@diitalk.com'
                ORDER BY lower(d.dealer_name)""").fetchall()]
            import json
            for account in accounts:
                try: account['company']=str(json.loads(account.pop('profile_json') or '{}').get('company') or '')
                except (ValueError,TypeError,AttributeError): account['company']=''
            accounts=[a for a in accounts if len(query)>=2 and query.casefold() in ' '.join([a['dealer_name'],a['email'],a['company']]).casefold()][:20]
            for account in accounts:
                usage=con.execute('SELECT lookups,estimates FROM account_month_usage WHERE dealer_id=? AND period=?',(account['id'],month_key())).fetchone()
                account['month_lookups']=int(usage['lookups']) if usage else 0
                account['month_estimates']=int(usage['estimates']) if usage else 0
            audit = [dict(r) for r in con.execute("""SELECT a.*,d.email,actor.email AS actor_email
                FROM account_credit_audit a JOIN dealers d ON d.id=a.dealer_id LEFT JOIN dealers actor ON actor.id=a.actor
                ORDER BY a.created_at DESC LIMIT 100""").fetchall()]
        finally: con.close()
        return render_template_string(PAGE, accounts=accounts,audit=audit,csrf=token,error=error,
                                      saved=request.args.get('saved')=='1', query=query, brands=BRANDS, new_id=lambda:str(uuid.uuid4()))

PAGE = """<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>AeriQuote Account Credits</title>
<style>body{font:16px system-ui;background:#f3f6fa;color:#172b45;margin:0}main{max-width:1100px;margin:28px auto;padding:16px}section{background:white;border:1px solid #dce5ef;border-radius:12px;padding:20px;margin:18px 0}label{display:block;margin:12px 0}input,select,button{font:inherit;padding:9px;max-width:100%;box-sizing:border-box}input[name=reason]{width:100%}button{background:#1469b0;color:white;border:0;border-radius:7px;cursor:pointer}form{margin:18px 0;border-top:1px solid #ddd;padding-top:12px}.scroll{overflow:auto}table{border-collapse:collapse;width:100%}td,th{padding:10px;border-bottom:1px solid #ddd;text-align:left}small{display:block;color:#52647a}.error{color:#a11}</style></head><body><main>
<a href="/head-office/dealers">← Admin Dashboard</a><h1>Measurement Credits and Dealer Access</h1>
<p>Extra credits add both property measurements and saved estimates. They carry forward until used. Complimentary dealers receive 200 of each per calendar month, renewing on the first in America/Edmonton. Unused monthly credits do not roll over. Employees share their business allowance.</p>
<p>Complimentary access does not change the underlying plan or create a paid subscription. Turning it off restores the existing plan and its usage. Warranty branding is independent of complimentary access.</p>
{% if saved %}<p role="status">Account updated and audit entry saved.</p>{% endif %}{% if error %}<p class="error" role="alert">{{error}}</p>{% endif %}
<form method="get"><label>Find account <input type="search" style="display:block;width:100%;max-width:640px;margin-top:6px" name="q" value="{{query}}" minlength="2" required placeholder="Business name or signup email"></label><button>SEARCH ACCOUNTS</button></form>
{% if not query %}<p>Search for an account to manage its credits or dealer access.</p>{% elif not accounts %}<p role="status">No matching accounts. Enter at least two characters of the business name, owner name or signup email.</p>{% else %}<p>{{accounts|length}} matching account(s), showing up to 20. Check the signup email before making changes.</p>{% endif %}
{% for a in accounts %}<section class="account"><h2>{{a.company or a.dealer_name}}</h2><p>{{a.email}} · {{a.status}} · Underlying plan: {{a.plan_code}}</p>
<p>{% if a.complimentary %}This month: {{a.month_lookups}} measurements · {{a.month_estimates}} estimates used.{% endif %}</p><p><b>{{'Complimentary dealer — 200 monthly' if a.complimentary else 'Standard account allowance'}}</b><small>Extra credits remaining: {{a.lookup_bonus}} measurements · {{a.estimate_bonus}} estimates. Brand: {{brands[a.brand]}}</small></p>
<form method="post"><input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="operation" value="{{new_id()}}"><input type="hidden" name="dealer_id" value="{{a.id}}"><input type="hidden" name="action" value="grant">
<h3>One-time extra credits</h3><p>Adds credits once. This does not enable the 200 monthly allowance.</p><label>Extra credits <select name="amount"><option>25</option><option>75</option><option>150</option></select></label>
<label>Reason <input name="reason" maxlength="500" required placeholder="Service adjustment or dealer support"></label><button>ADD SELECTED ONE-TIME CREDITS</button></form>
<form method="post"><input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="operation" value="{{new_id()}}"><input type="hidden" name="dealer_id" value="{{a.id}}"><input type="hidden" name="action" value="configure">
<h3>Monthly dealer access and warranty brand</h3><label><input type="checkbox" name="complimentary" value="1" {% if a.complimentary %}checked{% endif %}> Complimentary dealer — 200 measurements and estimates per month</label>
<label>Approved warranty brand <select name="brand">{% for key,label in brands.items() %}<option value="{{key}}" {% if key==a.brand %}selected{% endif %}>{{label}}</option>{% endfor %}</select></label>
<label>Reason <input name="reason" maxlength="500" required></label><button>SAVE MONTHLY ACCESS AND BRAND</button></form>
<form method="post"><h3>Account access</h3><input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="operation" value="{{new_id()}}"><input type="hidden" name="dealer_id" value="{{a.id}}">
{% if a.status|lower=='active' %}<input type="hidden" name="action" value="disable"><p>Disabling blocks the owner and all employees and stops complimentary monthly access. Estimates and unused extra credits remain saved.</p><label>Reason <input name="reason" required maxlength="500" placeholder="Dealer left the program"></label><button style="background:#9a2435">DISABLE ACCOUNT AND MONTHLY ACCESS</button>
{% else %}<input type="hidden" name="action" value="reactivate"><p>Reactivate login access. Complimentary monthly access must be enabled separately.</p><label>Reason <input name="reason" required maxlength="500"></label><button>REACTIVATE ACCOUNT</button>{% endif %}</form></section>{% endfor %}
<section><h2>Recent adjustments</h2><div class="scroll"><table><tr><th>Date</th><th>Account</th><th>Issued by</th><th>Change</th><th>Reason</th></tr>{% for e in audit %}<tr><td>{{e.created_at}}</td><td>{{e.email}}</td><td>{{e.actor_email or e.actor}}</td><td>{{e.details}}</td><td>{{e.reason}}</td></tr>{% else %}<tr><td colspan="5">No adjustments yet.</td></tr>{% endfor %}</table></div></section></main></body></html>"""
