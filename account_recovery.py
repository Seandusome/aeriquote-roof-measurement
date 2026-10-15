"""Single-use password recovery for business owners and employees."""
import hashlib, hmac, json, os, secrets, time
import urllib.request
from urllib.parse import urlsplit
from flask import request, session, redirect, render_template_string, Response

FORM = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{title}} | AeriQuote</title><meta name="referrer" content="no-referrer"><style>body{font-family:Arial;background:#f1f5f9;color:#17212b}.box{max-width:430px;margin:8vh auto;background:white;padding:30px;border-radius:18px}img{width:100%;max-width:360px}label{display:block;font-weight:bold;margin:16px 0 6px}input{width:100%;box-sizing:border-box;padding:12px;border:1px solid #cbd5ce;border-radius:9px}button{padding:13px;background:#1677c8;color:white;border:0;border-radius:9px;margin:20px 0;font-weight:bold;width:100%}.message{background:#eef7ff;padding:14px;border-radius:8px;line-height:1.5}a{color:#1264ad}</style><link rel="icon" type="image/svg+xml" href="/site/assets/favicon.svg"><link rel="stylesheet" href="/site/account-ui.css?v=20261015"></head><body class="aq-account-page"><main class="box"><a href="/site/"><img src="/static/aeriquote-logo.png" alt="AeriQuote"></a><h1>{{title}}</h1>{% if message %}<p class="message" role="status">{{message}}</p>{% endif %}{% if show_form %}<form method="post"><input type="hidden" name="csrf" value="{{csrf}}">{% if reset %}<label for="password">New password</label><input id="password" name="password" type="password" autocomplete="new-password" minlength="8" maxlength="256" required><label for="confirm">Confirm new password</label><input id="confirm" name="confirm" type="password" autocomplete="new-password" minlength="8" maxlength="256" required>{% else %}<p>Enter the email you use to sign in. Business owners and employees can reset their own password here.</p><label for="email">Login email</label><input id="email" name="email" type="email" autocomplete="email" maxlength="254" required>{% endif %}<button>{{'SAVE NEW PASSWORD' if reset else 'EMAIL RESET LINK'}}</button></form>{% endif %}<p><a href="/dealer-login">Back to login</a></p>{% if not reset %}<p>Forgot your login email? Contact AeriQuote support to verify ownership and recover access.</p>{% endif %}</main><footer class="aq-account-footer"><a href="/site/contact-support">Contact &amp; Support</a><a href="/site/privacy-policy">Privacy</a><a href="/site/terms-of-use">Terms</a></footer></body></html>"""

def init_recovery_db(con):
    con.execute('CREATE TABLE IF NOT EXISTS password_reset_tokens (token_hash TEXT PRIMARY KEY, account_type TEXT NOT NULL, account_id TEXT NOT NULL, password_stamp TEXT NOT NULL, expires_at REAL NOT NULL)')
    con.execute('CREATE TABLE IF NOT EXISTS account_auth_versions (account_type TEXT NOT NULL, account_id TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(account_type,account_id))')
    con.execute('CREATE TABLE IF NOT EXISTS auth_request_limits (bucket TEXT PRIMARY KEY, attempts INTEGER NOT NULL DEFAULT 0, expires_at REAL NOT NULL)')

def auth_version(con,kind,account_id):
    row=con.execute('SELECT version FROM account_auth_versions WHERE account_type=? AND account_id=?',(kind,account_id)).fetchone()
    return int(row['version']) if row else 0

def limited(con,key,maximum,seconds=900):
    # Persisted fixed-window counters work across workers and restart.
    bucket=hashlib.sha256(key.encode()).hexdigest()+':'+str(int(time.time()//seconds))
    con.execute('DELETE FROM auth_request_limits WHERE expires_at<?',(time.time(),))
    row=con.execute('INSERT INTO auth_request_limits(bucket,attempts,expires_at) VALUES(?,1,?) ON CONFLICT(bucket) DO UPDATE SET attempts=auth_request_limits.attempts+1 RETURNING attempts',(bucket,(int(time.time()//seconds)+1)*seconds)).fetchone()
    con.commit()
    return int(row['attempts'])>maximum

def mail_config():
    key=os.environ.get('RESEND_API_KEY','').strip();sender=os.environ.get('PASSWORD_RESET_FROM','').strip();base=os.environ.get('AERIQUOTE_PUBLIC_URL','').strip().rstrip('/')
    url=urlsplit(base)
    return (key,sender,base) if key and sender and url.scheme=='https' and url.netloc and not url.username and not url.password and not url.query and not url.fragment and url.path in ('','/') else None

def send_reset_email(config,email,token):
    key,sender,base=config
    text='Reset your AeriQuote password:\n\n'+base+'/reset-password?token='+token+'\n\nThis link expires in 30 minutes and can be used once. If you did not request it, ignore this email.'
    req=urllib.request.Request('https://api.resend.com/emails',data=json.dumps({'from':sender,'to':[email],'subject':'Reset your AeriQuote password','text':text}).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','User-Agent':'AeriQuote'},method='POST')
    with urllib.request.urlopen(req,timeout=15) as response:
        if not 200<=response.status<300:raise RuntimeError('Email provider rejected reset request')

def register_recovery(app,estimate_db,password_hash):
    def render(reset=False,message=None,show=True,status=200):
        session.setdefault('recovery_csrf',secrets.token_urlsafe(32))
        response=Response(render_template_string(FORM,title='Choose a new password' if reset else 'Forgot password?',reset=reset,message=message,show_form=show,csrf=session['recovery_csrf']),status=status,content_type='text/html')
        response.headers['Cache-Control']='no-store';response.headers['Referrer-Policy']='no-referrer'
        return response
    def csrf_ok():
        return hmac.compare_digest(str(request.form.get('csrf') or ''),str(session.get('recovery_csrf') or 'missing'))
    @app.route('/forgot-password',methods=['GET','POST'])
    def forgot_password():
        if request.method=='GET':return render()
        if not csrf_ok():return render(message='Please reload this page and try again.',status=400)
        config=mail_config()
        if not config:return render(message='Password recovery email is not available yet. Please contact AeriQuote support.',show=False,status=503)
        email=str(request.form.get('email') or '').strip().lower()
        if len(email)>254 or '@' not in email:return render(message='Enter a valid login email.',status=400)
        con=estimate_db()
        try:
            ip_limited=limited(con,'reset-ip:'+str(request.remote_addr),50)
            email_limited=limited(con,'reset-email:'+email,3)
            if ip_limited or email_limited:return render(message='Too many requests. Please try again in 15 minutes.',status=429)
            owner=con.execute('SELECT id,password_hash,email FROM dealers WHERE LOWER(email)=?',(email,)).fetchone()
            employee=con.execute('SELECT id,password_hash,email FROM dealer_employees WHERE LOWER(email)=?',(email,)).fetchone()
            # A conflicting identity requires support; never guess the account.
            account=owner if owner and not employee else employee if employee and not owner else None
            if account:
                kind='owner' if owner else 'employee';token=secrets.token_urlsafe(32);digest=hashlib.sha256(token.encode()).hexdigest()
                con.execute('DELETE FROM password_reset_tokens WHERE expires_at<?',(time.time(),))
                con.execute('INSERT INTO password_reset_tokens VALUES(?,?,?,?,?)',(digest,kind,account['id'],hashlib.sha256((account['password_hash']+'|'+account['email'].lower()).encode()).hexdigest(),time.time()+1800));con.commit()
                try:send_reset_email(config,email,token)
                except Exception:
                    con.execute('DELETE FROM password_reset_tokens WHERE token_hash=?',(digest,));con.commit()
                    app.logger.error('Password reset email delivery failed; inspect provider status and sender configuration.')
            return render(message='If this email belongs to an AeriQuote account, a reset link will be sent. Check your inbox and spam folder.',show=False)
        finally:con.close()
    @app.route('/reset-password',methods=['GET','POST'])
    def reset_password():
        token=str(request.args.get('token') or '')
        if not 20<=len(token)<=200:return render(reset=True,message='This reset link is invalid or expired. Request a new link.',show=False,status=400)
        digest=hashlib.sha256(token.encode()).hexdigest();con=estimate_db()
        try:
            row=con.execute('SELECT * FROM password_reset_tokens WHERE token_hash=? AND expires_at>?',(digest,time.time())).fetchone()
            if not row:return render(reset=True,message='This reset link is invalid or expired. Request a new link.',show=False,status=400)
            if request.method=='GET':return render(reset=True)
            if not csrf_ok():return render(reset=True,message='Please reload this page and try again.',status=400)
            if limited(con,'reset-submit:'+str(request.remote_addr),50):return render(reset=True,message='Too many attempts. Please try again in 15 minutes.',status=429)
            password=str(request.form.get('password') or '')
            if not 8<=len(password)<=256 or password!=request.form.get('confirm'):return render(reset=True,message='Use at least 8 characters and enter the same password twice.',status=400)
            # Delete RETURNING claims the token atomically across SQLite/PostgreSQL workers.
            row=con.execute('DELETE FROM password_reset_tokens WHERE token_hash=? AND expires_at>? RETURNING account_type,account_id,password_stamp',(digest,time.time())).fetchone()
            if not row:return render(reset=True,message='This reset link is invalid or expired. Request a new link.',show=False,status=400)
            table='dealers' if row['account_type']=='owner' else 'dealer_employees'
            account=con.execute('SELECT password_hash,email FROM '+table+' WHERE id=?',(row['account_id'],)).fetchone()
            if not account or not hmac.compare_digest(hashlib.sha256((account['password_hash']+'|'+account['email'].lower()).encode()).hexdigest(),row['password_stamp']):
                con.commit();return render(reset=True,message='This reset link is invalid or expired. Request a new link.',show=False,status=400)
            changed=con.execute('UPDATE '+table+' SET password_hash=? WHERE id=? AND password_hash=? RETURNING id',(password_hash(password),row['account_id'],account['password_hash'])).fetchone()
            if not changed:
                con.commit();return render(reset=True,message='This reset link is invalid or expired. Request a new link.',show=False,status=400)
            con.execute('DELETE FROM password_reset_tokens WHERE account_type=? AND account_id=?',(row['account_type'],row['account_id']))
            con.execute('INSERT INTO account_auth_versions(account_type,account_id,version) VALUES(?,?,1) ON CONFLICT(account_type,account_id) DO UPDATE SET version=account_auth_versions.version+1',(row['account_type'],row['account_id']));con.commit()
            session.clear()
            return render(reset=True,message='Your password has been changed. Sign in with your new password. Disabled accounts remain disabled.',show=False)
        finally:con.close()
