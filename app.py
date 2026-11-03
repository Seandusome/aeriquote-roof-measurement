# V11.6.85 â€” SELF-CONTAINED WEBSITE ROUTING
# V11.6.82 â€” ACCOUNT / WEBSITE SIGNUP READINESS
# V11.6.76 â€” FOCUSED MEASUREMENT INTERFACE
import re
# AERIQUOTE V11.6.74 â€” MULTI-MEASUREMENT INTERFACE
# AeriQuote V11.6.91 â€” SNOW REMOVAL WORKFLOW. Roofing V11.6.90 behavior preserved.
# Measurement calculations, API calls, pricing, estimates and PDF mechanics are unchanged.
from flask import Flask, request, jsonify, Response, render_template_string, session, redirect, send_from_directory
import urllib.request, urllib.parse, urllib.error
import json, webbrowser, threading, uuid, math, time, os, sqlite3, hmac, hashlib, secrets
from datetime import datetime
from activation_metrics import account_metrics, account_plan_report
from account_credits import init_credit_db, settings as credit_settings, lock_account, consume as consume_credit, register_credits, paid_usage, SUBSCRIPTION_LIMITS
from property_sessions import PropertySessions
from property_address import unit_address, building_address
from account_recovery import init_recovery_db, auth_version, register_recovery, limited
from support_center import init_support_db, register_support
from storage_checks import init_storage_db, register_storage
try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg=None
    dict_row=None

from safe_logging import install_safe_logging
install_safe_logging()

app = Flask(__name__, static_folder=".", static_url_path="/static")
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
from qa_session_expiry import configure_qa_session_expiry
configure_qa_session_expiry(app, os.environ)

def password_hash(password, salt=None):
    salt=salt or secrets.token_hex(16)
    digest=hashlib.pbkdf2_hmac("sha256",str(password).encode(),salt.encode(),200000)
    return salt+"$"+digest.hex()

def password_ok(password, stored):
    try:
        salt,expected=stored.split("$",1)
        actual=password_hash(password,salt).split("$",1)[1]
        return hmac.compare_digest(actual,expected)
    except Exception:return False
SESSIONS = PropertySessions(lambda: estimate_db(), lambda: session.get("dealer_id"), lambda: GOOGLE_MAPS_API_KEY)
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_API_KEY", "") or os.environ.get("GOOGLE_MAPS_API_KEY", "")
MAPBOX_ACCESS_TOKEN = os.environ.get("MAPBOX_ACCESS_TOKEN", "")
# Persistent estimate storage:
# - Render production uses PostgreSQL whenever DATABASE_URL is present.
# - Local development falls back to SQLite.
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
ESTIMATE_DB = os.environ.get("ESTIMATE_DB_PATH", os.path.join(os.path.dirname(__file__), "aeriquote_estimates.db"))

class DBCompat:
    """Small compatibility wrapper so the existing estimate-history routes work with SQLite or PostgreSQL."""
    def __init__(self, con, postgres=False):
        self.con=con
        self.postgres=postgres
    def execute(self, sql, params=()):
        if self.postgres:
            sql=sql.replace("?", "%s")
            return self.con.execute(sql, params)
        return self.con.execute(sql, params)
    def commit(self): return self.con.commit()
    def close(self): return self.con.close()

_ESTIMATE_SCHEMA_LOCK = threading.Lock()
_ESTIMATE_SCHEMA_READY = set()

def estimate_db():
    if DATABASE_URL:
        if psycopg is None:
            raise RuntimeError("DATABASE_URL is configured but psycopg is not installed. Add psycopg[binary] to requirements.txt.")
        raw=psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=10)
        con=DBCompat(raw, True)
        schema_key=("postgres",DATABASE_URL)
    else:
        raw=sqlite3.connect(ESTIMATE_DB)
        raw.row_factory=sqlite3.Row
        con=DBCompat(raw, False)
        st=os.stat(ESTIMATE_DB)
        schema_key=("sqlite",os.path.abspath(ESTIMATE_DB),st.st_dev,st.st_ino)
    try:
        # Authenticated imagery requests arrive concurrently. Never run ALTER TABLE
        # on every connection: PostgreSQL lock upgrades can deadlock those requests.
        with _ESTIMATE_SCHEMA_LOCK:
            if schema_key not in _ESTIMATE_SCHEMA_READY:
                if DATABASE_URL:
                    # Serialize initialization between workers/deploy instances too.
                    # Transaction-scoped: commit or connection close releases it.
                    con.execute("SELECT pg_advisory_xact_lock(?)",(614728193,))
                _initialize_estimate_schema(con)
                _ESTIMATE_SCHEMA_READY.add(schema_key)
        return con
    except Exception:
        con.close()
        raise

def _initialize_estimate_schema(con):
    import workspace_drafts
    workspace_drafts.initialize(con)
    con.execute("CREATE TABLE IF NOT EXISTS property_sessions (token TEXT PRIMARY KEY, dealer_id TEXT NOT NULL, expires_at DOUBLE PRECISION NOT NULL, payload TEXT NOT NULL)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_property_sessions_expiry ON property_sessions(expires_at)")
    con.execute("""CREATE TABLE IF NOT EXISTS estimates (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, customer_name TEXT, customer_phone TEXT, customer_email TEXT, address TEXT NOT NULL, total_area REAL, total_price REAL, payload TEXT NOT NULL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS estimate_revisions (revision_id TEXT PRIMARY KEY, estimate_id TEXT NOT NULL, revised_at TEXT NOT NULL, customer_name TEXT, customer_phone TEXT, customer_email TEXT, address TEXT NOT NULL, total_area REAL, total_price REAL, payload TEXT NOT NULL)""")
    con.execute("CREATE TABLE IF NOT EXISTS estimate_save_receipts (dealer_id TEXT NOT NULL, operation_id TEXT NOT NULL, payload_hash TEXT NOT NULL, response_json TEXT NOT NULL, PRIMARY KEY(dealer_id,operation_id))")
    con.execute("CREATE INDEX IF NOT EXISTS idx_estimates_address ON estimates(address)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_estimates_customer ON estimates(customer_name)")
    con.execute("""CREATE TABLE IF NOT EXISTS dealers (id TEXT PRIMARY KEY, dealer_name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, state TEXT, status TEXT NOT NULL DEFAULT 'active', lookup_limit INTEGER NOT NULL DEFAULT 250, estimate_limit INTEGER NOT NULL DEFAULT 150, created_at TEXT NOT NULL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS dealer_employees (id TEXT PRIMARY KEY, dealer_id TEXT NOT NULL, employee_name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL)""")
    con.execute("CREATE INDEX IF NOT EXISTS idx_dealer_employees_dealer ON dealer_employees(dealer_id)")
    con.execute("CREATE TABLE IF NOT EXISTS account_activations (dealer_id TEXT PRIMARY KEY, first_measured_at TEXT NOT NULL)")
    con.execute("""CREATE TABLE IF NOT EXISTS dealer_usage (dealer_id TEXT PRIMARY KEY, property_lookups INTEGER NOT NULL DEFAULT 0)""")
    con.execute("""CREATE TABLE IF NOT EXISTS head_office_settings (setting_key TEXT PRIMARY KEY, setting_value TEXT NOT NULL)""")
    # V11.6.82 â€” website/signup-ready account data. Keep flexible onboarding fields in
    # a compact JSON profile instead of continuously widening the main dealer table.
    con.execute("""CREATE TABLE IF NOT EXISTS dealer_profiles (dealer_id TEXT PRIMARY KEY, profile_json TEXT NOT NULL DEFAULT '{}', updated_at TEXT NOT NULL)""")
    if DATABASE_URL:
        con.execute("ALTER TABLE dealers ADD COLUMN IF NOT EXISTS plan_code TEXT NOT NULL DEFAULT 'legacy'")
        con.execute("ALTER TABLE dealers ADD COLUMN IF NOT EXISTS industry TEXT NOT NULL DEFAULT 'roofing'")
    else:
        dealer_cols=[r["name"] for r in con.execute("PRAGMA table_info(dealers)").fetchall()]
        if "plan_code" not in dealer_cols: con.execute("ALTER TABLE dealers ADD COLUMN plan_code TEXT NOT NULL DEFAULT 'legacy'")
        if "industry" not in dealer_cols: con.execute("ALTER TABLE dealers ADD COLUMN industry TEXT NOT NULL DEFAULT 'roofing'")
    # Dealer ownership migration. Existing installations pre-date dealer separation.
    # PostgreSQL must use IF NOT EXISTS: catching a duplicate-column error without a
    # rollback leaves the whole transaction aborted and breaks Previous Estimates.
    if DATABASE_URL:
        # PostgreSQL REAL is float32: large quote totals can lose customer-visible cents.
        for table in ("estimates","estimate_revisions"):
            con.execute(f"ALTER TABLE {table} ALTER COLUMN total_area TYPE DOUBLE PRECISION, ALTER COLUMN total_price TYPE DOUBLE PRECISION")
        con.execute("ALTER TABLE estimates ADD COLUMN IF NOT EXISTS dealer_id TEXT")
        con.execute("ALTER TABLE estimate_revisions ADD COLUMN IF NOT EXISTS dealer_id TEXT")
    else:
        estimate_cols=[r["name"] for r in con.execute("PRAGMA table_info(estimates)").fetchall()]
        revision_cols=[r["name"] for r in con.execute("PRAGMA table_info(estimate_revisions)").fetchall()]
        if "dealer_id" not in estimate_cols:
            con.execute("ALTER TABLE estimates ADD COLUMN dealer_id TEXT")
        if "dealer_id" not in revision_cols:
            con.execute("ALTER TABLE estimate_revisions ADD COLUMN dealer_id TEXT")
    # Preserve legacy Head Office estimates. Only the explicit Head Office account
    # may claim records created before dealer ownership existed.
    try:
        head=con.execute("SELECT id FROM dealers WHERE LOWER(dealer_name) LIKE '%head office%' ORDER BY created_at ASC LIMIT 1").fetchone()
        if head:
            hid=head["id"] if hasattr(head,"keys") else head[0]
            con.execute("UPDATE estimates SET dealer_id=? WHERE dealer_id IS NULL OR dealer_id=''",(hid,))
            con.execute("UPDATE estimate_revisions SET dealer_id=? WHERE dealer_id IS NULL OR dealer_id=''",(hid,))
    except Exception:
        pass
    con.execute("CREATE INDEX IF NOT EXISTS idx_estimates_dealer ON estimates(dealer_id)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_estimate_revisions_dealer ON estimate_revisions(dealer_id)")
    init_support_db(con)
    init_storage_db(con)
    init_recovery_db(con)
    init_credit_db(con)
    con.commit()

def login_auth_version(kind,account_id):
    con=estimate_db()
    try:return auth_version(con,kind,account_id)
    finally:con.close()

register_recovery(app,estimate_db,password_hash)
register_support(app,estimate_db,lambda: is_head_office())
register_storage(app,estimate_db,lambda: is_head_office())
HTML = r"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta id="aqAccountId" data-account-id="{{ACCOUNT_ID}}" data-principal="{{DRAFT_PRINCIPAL}}">
<title>AeriQuote Roof Measurement & Estimate</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
:root{--green:#1456c0;--green2:#0b1739;--orange:#e35b21;--dark:#111827;--gold:#e35b21;--bg:#f3f6fa;--line:#d8e0eb;--muted:#5f6b7a;--house:#1456c0;--garage:#1596d2;--manual:#e35b21;--warn:#fff4e8}
*{box-sizing:border-box} body{font-family:Arial,sans-serif;background:var(--bg);margin:0;color:var(--dark)}
.wrap{max-width:none;margin:14px auto;padding:0 12px}.card{background:#fff;border-radius:16px;box-shadow:0 8px 28px rgba(0,0,0,.08);overflow:hidden}
.header{padding:14px 20px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;gap:14px;align-items:center}.brand{display:flex;align-items:center;gap:13px}.brand img.aeriquote-main-logo{width:520px;max-width:52vw;height:auto;max-height:110px;object-fit:contain;object-position:left center;display:block}.brandLogoWrap{display:flex;flex-direction:column;align-items:flex-start}.brandLogoWrap .aeriquote-main-logo{clip-path:inset(0 0 19% 0);margin-bottom:-18px}.industryBrandTag{font-size:10px;font-weight:900;letter-spacing:2.4px;color:#111827;margin-left:8px;white-space:nowrap}.aeri-wordmark{font-size:34px;font-weight:900;letter-spacing:-1.5px;line-height:1}.aeri-wordmark .aeri{color:#090d18}.aeri-wordmark .quote{color:#1456c0}.aeri-wordmark .pointer{color:#e35b21;font-size:22px;vertical-align:5px;margin-left:-7px}.aeri-tag{font-size:10px;font-weight:900;letter-spacing:3.2px;color:#111827;margin-top:6px}.brand h1{margin:0;color:var(--green2);font-size:27px}.sub{color:var(--muted);margin-top:3px}.badge{background:#edf7f0;color:var(--green2);border:1px solid #cfe5d5;padding:8px 11px;border-radius:999px;font-weight:800;font-size:12px}
.setup{padding:13px 20px;background:#fbfcfb;border-bottom:1px solid var(--line)}.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}.grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px} label{font-weight:800;display:block;margin:4px 0 5px} input,select,textarea{width:100%;padding:10px 11px;border:1px solid #cbd5ce;border-radius:8px;font-size:14px;font-family:inherit}textarea{min-height:70px;resize:vertical}.small{font-size:12px;color:var(--muted)}
.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}button{background:var(--green);color:#fff;border:0;border-radius:9px;padding:10px 14px;font-weight:800;cursor:pointer}button.secondary{background:#fff;color:var(--green);border:1px solid var(--green)}button.orange{background:var(--manual)}button.ghost{background:#f3f6f4;color:var(--dark);border:1px solid var(--line)}button.danger{background:#fff;color:#a12622;border:1px solid #d8a7a4}button:disabled{opacity:.45;cursor:not-allowed}
.status{padding:9px 20px;font-weight:800}.ok{color:var(--green)}.error{color:#a12622}.warn{color:#8a5a08}
.workflow{padding:9px 20px;border-bottom:1px solid var(--line);background:#edf7f0;font-size:13px}.workflow b{color:var(--green2)}
.job-summary-bar{display:grid;grid-template-columns:2fr .55fr .8fr .8fr;gap:0;margin:0 20px 12px;border:1px solid #cfe0d3;border-radius:11px;background:#f7fbf8;overflow:hidden}.job-summary-bar>div{padding:9px 12px;border-right:1px solid #dbe7de;min-width:0}.job-summary-bar>div:last-child{border-right:0}.job-summary-bar b{display:block;margin-top:2px;color:var(--green2);font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.js-label{font-size:10px;font-weight:900;letter-spacing:.55px;color:var(--muted)}
.main{display:grid;grid-template-columns:2.55fr .68fr;gap:13px;padding:0 20px 20px}.panel{border:1px solid var(--line);border-radius:12px;overflow:hidden;background:#fff}.ptitle{padding:11px 13px;background:#f8faf9;border-bottom:1px solid var(--line);font-weight:800}
#map{height:840px;background:#e9efeb}.mapwrap{position:relative;overflow:hidden}.loading{position:absolute;z-index:1200;left:14px;top:14px;background:rgba(255,255,255,.95);border:1px solid var(--line);padding:9px 12px;border-radius:8px;font-weight:800;box-shadow:0 2px 8px #0002}.tracebanner{display:none;position:absolute;z-index:1200;left:50%;top:14px;transform:translateX(-50%);background:#fff7ed;border:2px solid var(--manual);color:#8a5208;padding:8px 13px;border-radius:8px;font-weight:800}.leaflet-zoom-animated{transition-duration:.22s!important}.leaflet-fade-anim .leaflet-tile{transition:opacity .12s linear!important}
.manualbox{background:#fff7ed;border-bottom:1px solid #efd4aa}.manualbox summary{cursor:pointer;padding:10px 12px;font-weight:800;color:#8a5208}.manualrow{padding:0 12px 10px;display:flex;gap:8px;align-items:end;flex-wrap:wrap}.pitch{width:120px}.point-label{background:#fff;border:2px solid var(--manual);border-radius:50%;width:25px;height:25px;text-align:center;padding-top:3px;color:#8a5208;font-size:12px;font-weight:800}.manual-label{background:#fff;border:2px solid var(--manual);border-radius:6px;padding:3px 6px;color:#8a5208;font-size:12px;font-weight:800;white-space:nowrap}.seg-label{display:inline-block;width:max-content;background:rgba(255,255,255,.92);border:1px solid #e27b2d;border-radius:6px;padding:2px 5px;font-weight:800;color:#7a3f08;box-shadow:0 1px 3px #0002;white-space:nowrap;font-size:11px}.edge-label{display:inline-block;width:max-content;background:rgba(255,255,255,.98);border:1px solid #8fa9ca;border-radius:5px;padding:2px 5px;color:#0b1739;font-size:11px;font-weight:900;white-space:nowrap;box-shadow:0 1px 4px #0002}.roof-corner{width:10px;height:10px;border-radius:50%;background:#fff;border:3px solid currentColor;box-shadow:0 1px 4px #0004}
.side{padding:12px}.street{width:100%;height:190px;object-fit:cover;background:#e8ece9;border-radius:9px;border:1px solid var(--line)}.section{margin-top:12px}.section h3{margin:0 0 7px;font-size:15px}.metric-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.metric{padding:9px;border:1px solid var(--line);border-radius:9px;background:#f8faf9}.metric b{display:block;font-size:18px;color:var(--green2);margin-top:2px}.structure{border:1px solid var(--line);border-radius:9px;padding:9px;margin:7px 0}.structure-head{display:flex;justify-content:space-between;gap:8px}.dot{width:9px;height:9px;border-radius:50%;display:inline-block;margin-right:6px}.house-dot{background:var(--house)}.garage-dot{background:var(--garage)}.manual-dot{background:var(--manual)}.calc{display:grid;grid-template-columns:1fr auto;gap:6px;font-size:13px}.calc div:nth-child(even){font-weight:800}.estimate{background:#f7faf8;border:1px solid var(--line);border-radius:9px;padding:10px;margin-top:9px}.line{display:flex;justify-content:space-between;gap:8px;padding:6px 0;border-bottom:1px solid #e5ece7}.line:last-child{border-bottom:0}.grand{font-size:17px;color:var(--green2);font-weight:900}.total{padding:11px;background:#edf7f0;border:1px solid #cde5d4;border-radius:9px;font-weight:800;margin-top:9px}.warning{padding:9px;background:var(--warn);border:1px solid #e5ca7e;border-radius:8px;color:#79520c;margin-top:8px;font-size:12px}.good{padding:9px;background:#edf7f0;border:1px solid #cde5d4;border-radius:8px;color:var(--green2);margin-top:8px;font-size:12px}.fallbackbox{display:none;background:#fff8e8;border:1px solid #e7c56f;border-radius:10px;padding:11px 12px;margin:10px 0;color:#6f4b08}.fallbackbox b{color:#5e3e05}
.dealer-settings{margin-top:10px;border:1px solid var(--line);border-radius:10px;background:#fff}.dealer-settings summary{cursor:pointer;padding:10px 12px;font-weight:800;color:var(--green2)}.settingsbody{padding:0 12px 12px}.savedmsg{padding:8px;border-radius:8px;background:#edf7f0;border:1px solid #cde5d4;color:var(--green2);font-size:12px;margin-top:8px}.usage{font-size:12px;color:var(--muted);margin-top:6px}
.dealer-branding-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:7px;margin-top:7px}.dealer-logo-tools{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:8px}.dealer-logo-preview{width:180px;height:64px;object-fit:contain;border:1px solid var(--line);border-radius:8px;background:#fff;padding:6px}.dealer-logo-note{font-size:11px;color:var(--muted);max-width:440px}.dealer-logo-clear{padding:7px 10px}.reportHead .dealerLogo{width:auto!important;height:auto!important;max-width:100%;max-height:120px;object-fit:contain;justify-self:center;transform:none;transform-origin:center center}.reportHead .dealerLogo.defaultDealerLogo{transform:none}.reportDealerSub{font-size:12px;color:#5b675f;text-align:center;margin-top:4px}.dealerContactCompact{margin-top:7px;font-size:13px;line-height:1.55}.dealerContactCompact .contactSep{opacity:.65;padding:0 7px}.dealerContactCompact #rDealerEmailWrap,.dealerContactCompact #rDealerAddressWrap,.dealerContactCompact #rPhoneWrap{display:inline-block}
.marketing-settings{margin-top:12px;border:1px solid var(--line);border-radius:10px;background:#f8fafc;padding:0}.marketing-settings>summary{cursor:pointer;padding:12px;font-weight:900;color:var(--green2);list-style-position:inside}.marketing-settings-body{padding:0 12px 12px}.marketing-toggle{display:flex;align-items:center;gap:8px;font-weight:800;margin-bottom:10px}.marketing-toggle input{width:auto}.benefit-editor{display:grid;grid-template-columns:90px 1fr 2fr;gap:7px;margin-top:7px}.marketing-cta-fields label{display:block;margin-top:8px}.marketing-cta-fields input{display:block;width:100%;margin-top:4px}.save-profile-btn.saved{background:#28612f!important;color:#fff!important}.reportHead .dealerLogo.noDealerLogo{visibility:hidden}.marketingWarranty{margin-top:8px;padding:9px 10px;border:1px solid var(--line);border-radius:8px;background:#f8faf9;font-size:13px}.marketingHidden{display:none!important}@media(max-width:800px){.benefit-editor{grid-template-columns:1fr}}
.historyModal{display:none;position:fixed;inset:0;background:#0008;z-index:6500;padding:30px;overflow:auto}.historyModal.open{display:block}.historyBox{max-width:1000px;margin:auto;background:#fff;border-radius:14px;padding:18px;box-shadow:0 16px 50px #0005}.historyHead{display:flex;justify-content:space-between;align-items:center;gap:12px}.historyResults{margin-top:14px}.historyRow{display:grid;grid-template-columns:1.15fr 2fr .75fr .75fr auto;gap:16px;align-items:center;padding:16px 10px;border-bottom:1px solid var(--line);font-size:13px}.historyRow:hover{background:#f8faf9}.historyCustomer b,.historyAddress b{font-size:14px}.historyDate,.historyAmount{white-space:nowrap}.historyActions{display:flex;gap:12px;align-items:center;justify-content:flex-end;flex-wrap:nowrap}.historyActions button{white-space:nowrap;margin:0;min-width:max-content}.historyColumns{display:grid;grid-template-columns:1.15fr 2fr .75fr .75fr auto;gap:16px;padding:10px 10px 6px;color:#66736b;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.04em;border-bottom:1px solid var(--line)}@media(max-width:800px){.historyColumns{display:none}.historyRow{grid-template-columns:1fr;gap:8px;padding:16px 6px}.historyActions{justify-content:flex-start}.historyModal{padding:10px}}
/* V11.5 dealer-simple UI only â€” measurement logic unchanged */
.stepbar{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;padding:12px 20px;background:#f7faf8;border-bottom:1px solid var(--line)}
.stepchip{padding:10px 12px;border:1px solid var(--line);border-radius:10px;background:#fff;font-weight:800;color:var(--muted);transition:.15s ease}
.stepchip strong{display:block;color:#5b675f;font-size:15px;margin-bottom:2px}.stepnum{display:inline-flex;width:24px;height:24px;border-radius:50%;align-items:center;justify-content:center;background:#dfe6e1;color:#526158;margin-right:6px}
.stepchip.done{background:#edf7f0;border-color:#9cc8a7;color:#28612f}.stepchip.done strong{color:#174f2b}.stepchip.done .stepnum{background:#28612f;color:#fff}
.stepchip.current{background:#fff8e8;border:2px solid #f59d0a;color:#704b08;box-shadow:0 2px 7px #0001}.stepchip.current strong{color:#704b08}.stepchip.current .stepnum{background:#f59d0a;color:#fff}
.roof-advanced{margin-top:10px;border:1px solid #d9e3dc;border-radius:9px;background:#fafcfb}.roof-advanced>summary{cursor:pointer;padding:10px 12px;font-weight:900;color:#5b675f}.roof-advanced-body{padding:0 12px 12px}.customer-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.customer-grid .full{grid-column:1/-1}
.stepcard{border:1px solid var(--line);border-radius:12px;padding:12px;background:#fff;margin-top:10px}.stepcard h2{font-size:17px;color:var(--green2);margin:0 0 8px}.primarybig{font-size:16px;padding:12px 18px}.nexthelp{font-size:14px;line-height:1.45;color:var(--dark)}
.simple-actions{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.advanced{margin-top:9px}.advanced summary{cursor:pointer;font-weight:800;color:var(--muted)}
@media(max-width:980px){.stepbar{grid-template-columns:1fr 1fr}.job-summary-bar{grid-template-columns:1fr 1fr}.job-summary-bar>div:nth-child(2){border-right:0}.job-summary-bar>div:nth-child(-n+2){border-bottom:1px solid #dbe7de}}

/* dealer help bubbles */
.info-tip{display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;margin-left:5px;border-radius:50%;background:#e9f3ec;color:#174f2b;font-size:12px;font-weight:900;cursor:help;position:relative;vertical-align:middle}
.info-tip:hover:after,.info-tip:focus:after{content:attr(data-tip);position:absolute;z-index:4000;left:24px;top:-8px;width:270px;padding:9px 11px;background:#173c29;color:#fff;border-radius:8px;box-shadow:0 4px 16px #0004;font-size:12px;font-weight:600;line-height:1.35;white-space:normal}
.info-tip:hover:before,.info-tip:focus:before{content:"";position:absolute;z-index:4001;left:18px;top:2px;border:6px solid transparent;border-right-color:#173c29}
.pitch-reminder{display:none;margin:7px 0 0;padding:8px 10px;border-radius:8px;background:#fff7e6;border:1px solid #e8b44d;color:#664500;font-size:12px;line-height:1.35}
/* customer report */
#reportOverlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:5000;overflow:auto;padding:22px}.report{max-width:1320px;margin:auto;background:#fff;border-radius:14px;padding:20px;box-shadow:0 16px 50px #0005}.reportHead{display:grid;grid-template-columns:280px 1fr 240px;align-items:center;gap:18px;border-bottom:2px solid var(--green);padding-bottom:12px}.reportHead .logo{width:255px}.reportHead h1{text-align:center;color:var(--green2);font-size:31px;margin:0}.reportHead .shield{width:210px;margin:auto}.reportMeta{display:grid;grid-template-columns:1.3fr .7fr .7fr;gap:12px;margin:14px 0}.reportMeta div{padding:8px 10px;border-bottom:1px solid var(--line)}.reportGrid{display:grid;grid-template-columns:1.5fr .72fr;gap:16px}.reportPanel{border:1px solid var(--line);border-radius:10px;overflow:hidden}.reportTitle{padding:9px 12px;background:var(--green2);color:#fff;font-weight:800}.reportBody{padding:12px}.customerMap{height:465px;background:#e9efeb}.reportMapWrap{position:relative}.reportDrawLayer{position:absolute;inset:0;width:100%;height:465px;z-index:900;display:none;cursor:crosshair;pointer-events:none}.reportDrawLayer.active{display:block;pointer-events:auto}.reportDrawLayer polyline{fill:none;stroke:#f59d0a;stroke-width:4;stroke-dasharray:8 5}.reportDrawLayer circle{fill:#fff;stroke:#f59d0a;stroke-width:3}.reportStreet{width:100%;height:225px;object-fit:cover;border-radius:8px;border:1px solid var(--line)}.benefit{display:flex;gap:9px;padding:9px 0;border-bottom:1px solid #e8ece9}.benefit:last-child{border-bottom:0}.benefitIcon{width:32px;height:32px;border-radius:50%;background:#edf7f0;color:var(--green2);display:flex;align-items:center;justify-content:center;font-weight:900}.cta{padding:14px;background:var(--green2);color:white;border-radius:10px;margin-top:12px}.cta strong{font-size:20px}.reportPrice{margin-top:12px;border:1px solid #cde5d4;border-radius:10px;overflow:hidden}.reportPrice .rphead{background:#edf7f0;color:var(--green2);padding:9px 12px;font-weight:800}.reportPrice .rpbody{padding:10px 12px}.reportFoot{font-size:11px;color:var(--muted);margin-top:10px}.reportActions{display:flex;gap:8px;margin-top:14px}body.report-open #reportOverlay{display:block!important}.estimateOutlineBar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:9px 10px;background:#fff8e8;border-top:1px solid #f1d08b;border-bottom:1px solid #f1d08b;position:relative;z-index:950}.estimateOutlineBar .orange{font-weight:900}
/* PDF CUSTOMER EXPORT â€” dealer editing controls are hidden and customer text is enlarged. */
.report.pdf-export{padding:14px;max-width:1320px}
.report.pdf-export .reportHead{grid-template-columns:240px 1fr 190px;gap:12px;padding-bottom:8px}
.report.pdf-export .reportHead .logo{width:220px}.report.pdf-export .reportHead .shield{width:170px}.report.pdf-export .reportHead h1{font-size:29px}
.report.pdf-export .reportMeta{margin:8px 0;gap:8px}.report.pdf-export .reportMeta div{padding:6px 8px;font-size:15px}
.report.pdf-export .reportGrid{gap:12px}.report.pdf-export .customerMap{height:430px}.report.pdf-export .reportDrawLayer{height:430px}
.report.pdf-export .reportStreet{height:205px}.report.pdf-export .reportTitle{padding:8px 10px;font-size:15px}
.report.pdf-export .reportBody{padding:10px;font-size:15px;line-height:1.25}.report.pdf-export .small{font-size:13.5px!important;line-height:1.3}
.report.pdf-export .structure,.report.pdf-export .metric{font-size:14.5px;line-height:1.25}
.report.pdf-export .benefit{padding:7px 0;font-size:14px;line-height:1.25}.report.pdf-export .benefitIcon{width:30px;height:30px}
.report.pdf-export .cta{padding:11px;margin-top:9px;font-size:13.5px;line-height:1.28}.report.pdf-export .cta strong{font-size:19px}
.report.pdf-export .reportPrice{margin-top:9px}.report.pdf-export .reportPrice .rphead,.report.pdf-export .reportPrice .rpbody{padding:8px 10px;font-size:14.5px;line-height:1.25}
.report.pdf-export .reportFoot{font-size:11.5px;line-height:1.3;margin-top:7px}
.report.pdf-export #reportOutlineControls,.report.pdf-export .reportActions{display:none!important}
@media(max-width:980px){.main,.grid2,.grid3,.reportGrid,.reportHead,.reportMeta{grid-template-columns:1fr}#map{height:600px}.reportHead h1{text-align:left}}
@page{size:letter landscape;margin:.22in}
@media print{
 html,body{width:11in;height:8.5in;margin:0;padding:0;background:#fff;overflow:hidden}
 .wrap{display:none}
 #reportOverlay{display:block!important;position:static;background:#fff;padding:0;margin:0}
 .report{box-shadow:none;width:10.56in;height:8.02in;max-width:none;border-radius:0;padding:.12in;overflow:hidden;transform:none}
 .reportHead{grid-template-columns:1.85in 1fr 1.55in;gap:.08in;padding-bottom:.05in}
 .reportHead .logo{width:1.65in}.reportHead .dealerLogo{width:auto!important;height:auto!important;max-width:1.65in;max-height:1.08in;transform:scale(1.55);transform-origin:center center}.reportHead .dealerLogo.defaultDealerLogo{transform:scale(1.75);transform-origin:center center}.reportHead .shield{width:1.28in}.reportHead h1{font-size:18pt}
 .reportMeta{margin:.05in 0;gap:.06in}.reportMeta div{padding:.035in .05in;font-size:8.5pt}
 .reportGrid{grid-template-columns:1.55fr .72fr;gap:.08in}
 .customerMap{height:3.25in!important}
 .reportStreet{height:1.38in}
 .reportTitle{padding:.04in .07in;font-size:9pt}
 .reportBody{padding:.06in}
 .structure,.metric{padding:.04in;font-size:8pt}
 .small{font-size:7pt!important}
 .benefit{padding:.035in 0;font-size:7.5pt}.benefitIcon{width:.22in;height:.22in;font-size:7pt}
 .cta{padding:.06in;margin-top:.05in;font-size:8pt}.cta strong{font-size:11pt}
 .reportPrice{margin-top:.05in}.reportPrice .rphead,.reportPrice .rpbody{padding:.05in .07in;font-size:8pt}
 .reportFoot{font-size:6.5pt;margin-top:.03in}
 .reportActions{display:none}.estimateOutlineBar{display:none!important}
 .reportPanel,.reportPrice,.cta{break-inside:avoid;page-break-inside:avoid}
}

.pitch-select{min-width:110px;padding:8px 10px}
.pitch-select option{padding:4px 8px}

/* Roofing added-roof controls: presentation only */
@media (min-width:700px){
  .manual-tools .pitch-wrap,
  .add-roof-tools .pitch-wrap,
  .pitch-control,
  .pitch-field{min-width:190px}
  .manual-tools .pitch-wrap label,
  .add-roof-tools .pitch-wrap label,
  .pitch-control label,
  .pitch-field label{white-space:nowrap;display:block;margin-bottom:6px}
  .manual-tools .pitch-wrap select,
  .add-roof-tools .pitch-wrap select,
  .pitch-control select,
  .pitch-field select,
  .pitch-select{min-width:160px;width:auto}
}

.aeri-added-pitch-label{white-space:nowrap!important;display:block;margin-bottom:6px}
.aeri-added-pitch-label + select{min-width:160px}

/* Manual main-roof tracing controls â€” layout only */
.aeri-manual-main-row{
  display:flex!important;
  align-items:flex-end!important;
  gap:14px!important;
  flex-wrap:wrap!important;
}
.aeri-manual-main-row label{
  white-space:nowrap!important;
}
.aeri-manual-main-row select{
  min-width:150px!important;
}
@media (max-width:900px){
  .aeri-manual-main-row{gap:10px!important}
}

/* Dynamic manual main-roof pitch controls â€” layout only */
.aeri-dynamic-manual-actions{
  display:flex!important;
  align-items:flex-end!important;
  flex-wrap:wrap!important;
  column-gap:18px!important;
  row-gap:10px!important;
}
.aeri-dynamic-main-pitch{
  min-width:210px!important;
  flex:0 0 210px!important;
  margin-right:18px!important;
}
.aeri-dynamic-main-pitch{
  white-space:nowrap!important;
}
.aeri-dynamic-main-pitch-select{
  display:block!important;
  min-width:170px!important;
  width:170px!important;
  margin-top:6px!important;
}
.aeri-dynamic-finish-measurement{
  margin-left:12px!important;
  flex:0 0 auto!important;
}

/* V11.6.79 â€” clean manual MAIN HOUSE control panel.
   Interface only: two compact left-aligned rows; measurement logic unchanged. */
.manualrow.main-house-trace-row{
  display:grid!important;
  grid-template-columns:210px 260px 250px!important;
  grid-template-areas:
    "cancel pitch finish"
    "undo clear clear"!important;
  align-items:end!important;
  justify-content:start!important;
  column-gap:18px!important;
  row-gap:12px!important;
  width:100%!important;
  padding:4px 12px 2px!important;
}
.manualrow.main-house-trace-row #traceBtn{grid-area:cancel;justify-self:stretch!important;width:100%!important;margin:0!important}
.manualrow.main-house-trace-row .main-house-pitch-control{
  grid-area:pitch;width:260px!important;min-width:260px!important;margin:0!important;position:static!important;transform:none!important
}
.manualrow.main-house-trace-row .main-house-pitch-control label{display:block!important;white-space:nowrap!important;margin:0 0 6px!important}
.manualrow.main-house-trace-row .main-house-pitch-control select{display:block!important;width:260px!important;min-width:260px!important;margin:0!important}
.manualrow.main-house-trace-row #finishTrace{grid-area:finish;justify-self:stretch!important;width:100%!important;margin:0!important;position:static!important;transform:none!important}
.manualrow.main-house-trace-row #undoTraceBtn{grid-area:undo;justify-self:stretch!important;width:100%!important;margin:0!important}
.manualrow.main-house-trace-row #clearManualBtn{grid-area:clear;justify-self:start!important;width:300px!important;margin:0!important}
.manualrow.main-house-trace-row .aeri-dynamic-main-pitch{min-width:260px!important;flex:initial!important;margin:0!important}
.manualrow.main-house-trace-row .aeri-dynamic-finish-measurement{margin:0!important;flex:initial!important}
@media(max-width:850px){
 .manualrow.main-house-trace-row{grid-template-columns:1fr!important;grid-template-areas:"cancel" "pitch" "finish" "undo" "clear"!important;align-items:start!important;padding:4px 12px!important}
 .manualrow.main-house-trace-row .main-house-pitch-control,.manualrow.main-house-trace-row .main-house-pitch-control select,.manualrow.main-house-trace-row #clearManualBtn{width:100%!important;min-width:0!important}
}


/* Keep replacement pitch, confirmation and action controls together. */
.manualrow.roof-replacement-row{display:grid!important;grid-template-columns:repeat(3,minmax(0,1fr))!important;grid-template-areas:"pitch pitch cancel" "confirm confirm confirm" "feedback feedback feedback" "save undo clear"!important;gap:12px!important;align-items:end!important;padding:12px!important;width:100%!important;box-sizing:border-box}
.roof-replacement-row #tracePitchControl{grid-area:pitch;width:100%!important;min-width:0!important}
.roof-replacement-row #manualPitchLabel{white-space:normal!important;font-weight:700}
.roof-replacement-row #pitchSel{width:100%!important;min-width:0!important;max-width:320px}
.roof-replacement-row #traceBtn{grid-area:cancel}.roof-replacement-row #finishTrace{grid-area:save}.roof-replacement-row #undoTraceBtn{grid-area:undo}.roof-replacement-row #clearManualBtn{grid-area:clear}
.roof-replacement-row #roofRemeasurePitch{grid-area:confirm;padding:12px!important;background:#fff;border:1px solid #d7c19e;border-radius:8px}
.roof-replacement-row #roofRemeasurePitch label{font-size:15px;line-height:1.45;font-weight:700}
.roof-replacement-row #roofRemeasurePitch input[type=checkbox]{width:20px!important;height:20px;flex:0 0 20px}
.roof-replacement-row #manualRoofSaveFeedback{grid-area:feedback;padding:9px 12px;border-radius:6px;background:#fff3cd;color:#684d00}
.roof-replacement-row>button{width:100%!important;min-width:0!important;min-height:44px;margin:0!important;white-space:normal}
@media(max-width:700px){.manualrow.roof-replacement-row{grid-template-columns:1fr!important;grid-template-areas:"pitch" "confirm" "feedback" "save" "undo" "clear" "cancel"!important}}

/* Roofing exposes only the current task; existing tools remain available. */
.roofing-simplified .measure-toolbar{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}
.roof-secondary-tools{border:1px solid #cbd8e5;border-radius:10px;background:#f8fafc;padding:12px;min-width:0}
.roof-secondary-tools>summary{cursor:pointer;font-weight:700;color:#334155}
.roof-secondary-tools .roof-secondary-buttons{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px}
.roof-secondary-tools .measure-mode{width:100%;min-width:0}
.roofing-simplified #roofCheckCard{border:0;background:none;padding:0;box-shadow:none}
.roofing-simplified #roofCheckCard>h2,.roofing-simplified #roofCheckCard>.small,.roofing-simplified #roofCheckCard>.simple-actions,.roofing-simplified #roofFixHelp{display:none!important}
.roofing-simplified #manualRoofDetails:not(.roof-editor-active){margin:8px 0}
.roofing-simplified #manualRoofDetails.roof-editor-active{border:1px solid #d8c09d;border-radius:10px;margin:10px 0;background:#fffaf2}
.roofing-simplified .roof-editor-active>summary{cursor:default;color:#1e293b}
.roofing-simplified .roof-editor-active #manualRoofWarning,.roofing-simplified .roof-editor-active #pitchReminder{display:none!important}
.roof-row-action{margin:8px 0;min-height:38px}
.roof-editing-indicator{display:block;margin:8px 0;color:#815700;font-weight:700}
.roofing-simplified .roof-editor-active #traceBtn{background:#fff;color:#475569;border:1px solid #cbd5e1}
@media(max-width:700px){.roofing-simplified .measure-toolbar{grid-template-columns:1fr}.roof-secondary-tools .roof-secondary-buttons{grid-template-columns:1fr}}
.reportPanel.correction-panel{overflow:visible}.correcting-measurement{touch-action:none!important}.report-correction-point{touch-action:none!important}.report-correction-point span{display:block;width:18px;height:18px;margin:5px;background:white;border:3px solid #f97316;border-radius:50%;box-sizing:border-box}.measurement-correction-controls{position:sticky;bottom:0;z-index:1100;background:#fff8e8;box-shadow:0 -2px 8px #0002;max-height:45dvh;overflow:auto}.measurement-correction-controls button{min-height:44px}.measurement-correction-controls .reportEditHelp{flex-basis:100%} </style>
<style>
.estimate-hide-street #reportStreet img,.estimate-hide-street .report-street img{visibility:hidden}
.estimate-hide-street #reportStreet,.estimate-hide-street .report-street{background:linear-gradient(135deg,#f3f7f4,#e6efe9);position:relative}
.estimate-hide-street #reportStreet:after,.estimate-hide-street .report-street:after{content:"PROPERTY ASSESSMENT COMPLETED\A Roof measured using available aerial imagery.";white-space:pre;text-align:center;font-weight:700;color:#174f2b;position:absolute;inset:0;display:flex;align-items:center;justify-content:center}

.trial-limit-overlay{display:none;position:fixed;inset:0;background:rgba(10,25,40,.62);z-index:9000;padding:22px;align-items:center;justify-content:center}.trial-limit-overlay.open{display:flex}.trial-limit-card{width:min(560px,100%);background:#fff;border-radius:16px;padding:28px;box-shadow:0 18px 60px #0006;text-align:center}.trial-limit-card h2{margin:0 0 10px;color:#102a43;font-size:28px}.trial-limit-card p{color:#5b6770;line-height:1.55;margin:8px 0}.trial-limit-card .trial-note{font-size:12px;margin-top:12px}.trial-limit-actions{display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-top:20px}.trial-limit-actions a,.trial-limit-actions button{min-height:44px;padding:11px 18px;border-radius:8px;font-weight:900;text-decoration:none}.trial-limit-actions a{background:#f28c28;color:#fff}.trial-limit-actions button{background:#fff;color:#17324d;border:1px solid #cbd5df;cursor:pointer}
</style><style>
.estimate-hide-street #rStreet{visibility:hidden}
.estimate-hide-street .reportPanel:has(#rStreet) .reportBody{min-height:150px;background:linear-gradient(135deg,#f3f7f4,#e6efe9);position:relative}
.estimate-hide-street .reportPanel:has(#rStreet) .reportBody:before{content:"PROPERTY ASSESSMENT COMPLETED\A Roof measured using available aerial imagery.";white-space:pre;text-align:center;font-weight:800;color:#174f2b;position:absolute;inset:0;display:flex;align-items:center;justify-content:center}
</style><style>
.reportImagePlaceholder{display:none;min-height:465px;background:linear-gradient(135deg,#f3f7f4,#e6efe9);align-items:center;justify-content:center;text-align:center;padding:32px;color:#174f2b;border-bottom:1px solid var(--line)}
.reportImagePlaceholder .big{font-size:24px;font-weight:900;letter-spacing:.3px}.reportImagePlaceholder .miniShield{width:95px;margin:0 auto 14px;display:block}
.reportEditHelp{font-size:12px;color:#5b675f;margin-left:6px;align-self:center}.estimate-editing #customerMap{outline:4px solid #f59d0a;outline-offset:-4px;cursor:crosshair}
@media print{ #streetPlaceholder{height:1.38in!important}.reportStreet[style*="display: none"]{display:none!important}.reportImagePlaceholder{min-height:3.2in!important}}
</style><style>
/* AeriQuote V11.6.70 â€” isolated Linear Measure workspace + saved total. Measurement engine unchanged. */
.linear-tool{margin:10px 0;border:1px solid #d9e3dc;border-radius:10px;background:#fbfdfc;overflow:hidden}
.linear-tool .linear-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:11px 12px;background:#f4f8f6;border-bottom:1px solid #e3ebe6}
.linear-tool .linear-title{font-weight:900;color:#102a43;letter-spacing:.2px}
.linear-tool .linear-body{padding:10px 12px}
.linear-total{display:inline-flex;align-items:center;gap:7px;margin-left:4px;padding:8px 11px;border-radius:8px;background:#e9f7f4;color:#0f5f55;font-weight:900;border:1px solid #bfe4dc}
.linear-seg-label{background:#fff;border:2px solid #0f8f83;border-radius:6px;padding:2px 5px;font-size:12px;font-weight:900;color:#0d4f49;white-space:nowrap;box-shadow:0 1px 4px #0003}
.linear-point{width:12px;height:12px;border-radius:50%;background:#fff;border:3px solid #0f8f83;box-shadow:0 1px 4px #0004}
.linear-active #map{cursor:crosshair}
/* Leaflet removes its touch-drag CSS when panning is disabled. Keep native page
   gestures from taking over a line correction; Leaflet still handles pinch zoom. */
#map.linear-correcting,#map.polygon-correcting{touch-action:none}
.surface-simple #jobMeasurements{display:none}.surface-simple .measure-toolbar{grid-template-columns:repeat(2,minmax(0,1fr))}.surface-simple #commercialAreaPanel{padding:12px!important;background:#fff;border-radius:10px!important}.surface-saved-area{display:grid;grid-template-columns:minmax(220px,1fr) minmax(235px,1fr) auto;gap:12px;align-items:center;padding:10px 0;border-top:1px solid #e4e9ed;margin-top:8px}.surface-saved-area .simple-actions{flex-wrap:wrap}.surface-saved-area button{font-size:12px;padding:8px}.surface-simple #areaStartBtn,.surface-simple #linearStartBtn,.surface-simple #linearSaveEditBtn{order:0}.surface-simple #areaCancelCorrectionBtn,.surface-simple #surfaceLineCancel,.surface-simple #linearCancelEditBtn{order:1}.surface-simple #areaUndoBtn,.surface-simple #linearUndoBtn{order:2}.surface-simple #areaClearBtn,.surface-simple #linearClearBtn{order:3}@media(max-width:1150px){.surface-saved-area{grid-template-columns:1fr}.surface-area-heading label{max-width:none}}.surface-area-heading,.surface-area-price{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:8px}.surface-area-heading label{flex:1;margin:0;max-width:420px}.surface-area-heading strong{white-space:nowrap}.surface-saved-area label{font-size:12px;color:#536579;font-weight:700}.surface-saved-area label input{display:block;margin-top:4px}.surface-area-price label{max-width:135px;margin:0}.surface-area-price .small{color:#39765a}.surface-simple #surfaceLineMore{margin-top:8px}.surface-simple #surfaceLineMore summary{font-size:13px;font-weight:700;color:#52677a;cursor:pointer}.surface-simple #surfaceLineMore .simple-actions{margin-top:8px}@media(max-width:600px){.surface-area-heading,.surface-area-price{flex-wrap:wrap}.surface-area-price .small{width:100%}}

.area-tool{margin:10px 0;border:1px solid #d9e3dc;border-radius:10px;background:#fbfdfc;overflow:hidden}.area-tool .area-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:11px 12px;background:#f7f5ff;border-bottom:1px solid #e6e0f5}.area-tool .area-title{font-weight:900;color:#102a43;letter-spacing:.2px}.area-tool .area-body{padding:10px 12px}.area-total{display:inline-flex;align-items:center;gap:7px;padding:8px 11px;border-radius:8px;background:#f1edff;color:#5630a5;font-weight:900;border:1px solid #d7ccf7}.area-point{width:12px;height:12px;border-radius:50%;background:#fff;border:3px solid #7357b8;box-shadow:0 1px 4px #0004}.area-label{background:#fff;border:2px solid #7357b8;border-radius:6px;padding:3px 6px;font-size:12px;font-weight:900;color:#49348a;white-space:nowrap;box-shadow:0 1px 4px #0003}.area-active #map{cursor:crosshair}

.measure-intro{display:flex;flex-direction:column;gap:3px;margin:4px 0 10px}.measure-intro b{font-size:20px;color:#102a43}.measure-intro span{color:#607080;font-size:13px}.measure-toolbar{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin:8px 0 12px}.measure-mode{min-height:70px;border:2px solid #d8e1e8;border-radius:11px;background:#fff;color:#17324d;text-align:left;padding:10px 12px;cursor:pointer}.measure-mode b{display:block;font-size:14px}.measure-mode small{display:block;margin-top:4px;color:#667788;font-weight:600}.measure-mode.active{border-color:#1677c8;background:#eef7ff;box-shadow:inset 0 0 0 1px #1677c8}.job-measurements{border:1px solid #d9e3dc;border-radius:10px;background:#fff;margin:0 0 12px;overflow:hidden}.jm-head{display:flex;justify-content:space-between;gap:10px;align-items:center;padding:9px 12px;background:#f6f8fa;border-bottom:1px solid #e4e9ed}.jm-list{display:grid;gap:0}.jm-row{display:grid;grid-template-columns:minmax(120px,1fr) auto auto;gap:10px;align-items:center;padding:9px 12px;border-top:1px solid #eef1f3}.jm-row:first-child{border-top:0}.jm-kind{font-weight:900;color:#17324d}.jm-value{font-weight:900;color:#102a43}.jm-status{font-size:11px;font-weight:800;color:#39765a;background:#edf8f1;border-radius:999px;padding:3px 7px}.jm-empty{padding:10px 12px;color:#6d7882;font-size:13px}.area-tool,.linear-tool{display:none}.measure-area .area-tool,.measure-linear .linear-tool{display:block}.measure-area .auto-only,.measure-linear .auto-only{display:none!important}.measure-auto .area-tool,.measure-auto .linear-tool{display:none}.measure-area #linearTool,.measure-linear #areaTool{display:none}.measure-area #areaTool,.measure-linear #linearTool{display:block}
/* V11.6.75 interface cleanup only â€” measurement engines unchanged */
.measure-area #advancedOptions,.measure-linear #advancedOptions{display:none!important}
#areaAutoBtn,#linearAutoBtn{display:none!important}
.measure-area .roof-legend,.measure-linear .roof-legend{display:none!important}
.measure-result-card{border:1px solid #cfe0d3;border-radius:11px;background:#f7fbf8;padding:12px;margin-top:10px}
.measure-result-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;padding-bottom:9px;border-bottom:1px solid #dbe7de}
.measure-result-title{font-size:12px;font-weight:900;letter-spacing:.45px;color:#607080;text-transform:uppercase}
.measure-result-value{font-size:23px;font-weight:900;color:#174f2b;margin-top:2px}
.measure-result-saved{font-size:11px;font-weight:900;color:#28612f;background:#e7f5eb;border-radius:999px;padding:4px 8px;white-space:nowrap}
.price-summary{margin-top:10px;border:1px solid var(--line);border-radius:10px;background:#fff;padding:11px}
.price-summary h3{margin:0 0 8px;font-size:15px;color:#174f2b}
.price-summary .grand{padding-top:8px;margin-top:3px;border-top:2px solid #dbe7de}
.workflow-next{margin-top:28px!important;border-top:4px solid #dbe7de!important;padding-top:18px!important}.measure-area .workflow-next,.measure-linear .workflow-next{margin-top:34px!important}.measure-area #summary,.measure-linear #summary{margin-top:-1px}.measure-area #jobPriceCard,.measure-linear #jobPriceCard{margin-bottom:0!important;border-bottom-left-radius:0;border-bottom-right-radius:0}.measure-area #summary .measure-result-card,.measure-linear #summary .measure-result-card{margin-top:0!important;border-top-left-radius:0;border-top-right-radius:0;border-top:0!important}
@media(max-width:760px){.measure-toolbar{grid-template-columns:1fr}.jm-head{align-items:flex-start;flex-direction:column}.jm-row{grid-template-columns:1fr auto}.jm-status{grid-column:1/-1;width:max-content}}
@media(max-width:760px){.linear-tool .linear-head{align-items:flex-start;flex-direction:column}.linear-total{margin-left:0}}
</style><style>
body.pressure-industry #toolAutoBtn{display:none!important}
body.pressure-industry .measure-auto .roof-only{display:none!important}
body.landscaping-industry #toolAutoBtn,body.landscaping-industry #garageControls,body.landscaping-industry #solarFallback,body.landscaping-industry .roof-only,body.landscaping-industry .auto-only{display:none!important}
</style><link rel="stylesheet" href="/site/help-center.css"><link rel="stylesheet" href="/site/mobile-workspace.css?v=20261018"><script defer src="/site/help-center.js?v=20261016"></script><style>.aeri-edge-label-icon{background:transparent;border:0;pointer-events:none}.aeri-edge-label{display:inline-block;white-space:nowrap;background:#fff;color:#283653;border:1px solid #7357b8;border-radius:5px;padding:3px 6px;font-size:12px;font-weight:800;box-shadow:0 1px 4px #0003;transform:translateY(-3px)}</style></head>
<body>
<div class="wrap"><div class="card">
 <div class="header"><div class="brand"><div class="brandLogoWrap"><a href="/site/" title="Back to AeriQuote website" aria-label="AeriQuote website"><img class="aeriquote-main-logo" src="/static/aeriquote-logo.png" alt="AeriQuote"></a><div id="industryBrandTag" class="industryBrandTag">ROOF MEASUREMENT &amp; ESTIMATE SOFTWARE</div></div></div><div class="header-actions" style="display:flex;gap:8px;align-items:center">{% if IS_HEAD_OFFICE %}<button type="button" class="secondary" onclick="window.location.href='/head-office/dealers'">ADMIN DASHBOARD</button>{% endif %}{% if IS_DEALER_OWNER %}<button type="button" class="secondary" onclick="window.location.href='/dealer-employees'">EMPLOYEES</button>{% endif %}<a href="/site/pricing.html" style="display:inline-flex;align-items:center;justify-content:center;text-decoration:none;padding:11px 16px;border-radius:8px;font-weight:900;background:#f47b20;color:#fff;border:2px solid #e46d10;box-shadow:0 2px 6px #0002;white-space:nowrap">VIEW PLANS / UPGRADE</a><button type="button" class="secondary" data-aq-help-topic="first-estimate">HELP / FIRST ESTIMATE</button><button type="button" class="secondary" onclick="openEstimateHistory()">PREVIOUS ESTIMATES</button><button type="button" class="ghost" onclick="window.location.href='/logout'">LOG OUT</button></div></div>
 <div class="stepbar"><div id="progress1" class="stepchip current"><strong><span class="stepnum">1</span>Property</strong>Enter address & load</div><div id="progress2" class="stepchip"><strong><span class="stepnum">2</span>Measure</strong>Choose measurement tools</div><div id="progress3" class="stepchip"><strong><span class="stepnum">3</span>Price</strong>Set this job's price</div><div id="progress4" class="stepchip"><strong><span class="stepnum">4</span>Customer</strong>Add customer details</div><div id="progress5" class="stepchip"><strong><span class="stepnum">5</span>Estimate</strong>Create customer estimate</div></div>
 <div class="setup">
  <div class="stepcard"><h2>STEP 1 â€” Enter the property</h2><button type="button" class="aq-context-help" data-aq-help-topic="property">Help with this step</button><div class="grid2"><div><label for="propertyCountry">Property Country</label><select id="propertyCountry" onchange="propertyCountryChanged()"><option value="CA">Canada</option><option value="US">United States</option></select><label>Property Address</label><input id="streetAddress" placeholder="Start typing the address â€” U.S. or Canada" value=""><div id="addressAutoStatus" class="small" style="margin-top:5px;color:#176b43;font-weight:700">City, state/province and ZIP/postal code will fill automatically when Google finds the address.</div><div id="addressParts" style="display:grid;grid-template-columns:1.2fr .55fr .8fr;gap:7px;margin-top:7px"><input id="cityTown" placeholder="City" value=""><select id="propertyProvince" aria-label="Property province or state" onchange="propertyProvinceChanged()"><option value="">Choose province / territory</option></select><input id="postalCode" placeholder="ZIP / Postal Code â€” filled by Google" readonly></div><input id="address" type="hidden"><div id="googleMatch" class="small" style="margin-top:5px;color:#176b43;font-weight:700"></div><div id="propertyVerify" class="small" style="display:none;margin-top:7px;font-weight:700"></div>
<details id="coordinateFallback" style="margin-top:10px;border:1px solid #d9e3dc;border-radius:9px;background:#fafcfb">
<summary style="cursor:pointer;padding:10px 12px;font-weight:900;color:#5b675f">CAN'T LOCATE THE PROPERTY? USE DROPPED PIN / COORDINATES</summary>
<div style="padding:0 12px 12px">
<label>Latitude, Longitude <span class="info-tip" tabindex="0" data-tip="Enter latitude first, then longitude. Example: 27.950575, -82.457178. You can also paste 27.950575Â° N, 82.457178Â° W. West longitude becomes negative automatically.">â“˜</span></label>
<input id="coordinateInput" placeholder="Example: 27.950575, -82.457178">
<div class="small" style="margin-top:5px"><b>Example:</b> 27.950575, -82.457178 &nbsp;â€¢&nbsp; Latitude first, Longitude second.</div>
<div class="simple-actions" style="margin-top:8px"><button type="button" class="secondary" onclick="loadExactCoordinates()">LOAD EXACT PIN LOCATION</button></div>
<div id="coordinateStatus" class="small" style="margin-top:6px;font-weight:700"></div>
</div></details>
</div></div><div class="simple-actions"><button id="propertyActionBtn" class="primarybig" onclick="loadProperty()">LOAD & MEASURE ROOF</button></div></div>
  <details class="dealer-settings" {% if IS_EMPLOYEE %}style="display:none"{% endif %}><summary>âš™ DEALER PROFILE / BRANDING â€” set once, then leave closed</summary><div class="settingsbody"><div class="savedmsg"><b>Set this up once.</b> Your company branding and optional marketing message will appear on customer estimates.</div><div class="grid3"><div><label for="dealerCountry">Country</label><select id="dealerCountry" onchange="countryChanged()"><option value="US">United States</option><option value="CA">Canada</option></select></div><div><label id="regionLabel" for="province">State</label><select id="province" onchange="provinceChanged()"><option value="AL">AL</option></select></div></div><div class="grid3"><div><label>Dealer / Contact Name</label><input id="dealerName" value=""></div><div><label>Company Name</label><input id="dealerCompany" placeholder="Your company name"></div><div><label>Dealer Phone</label><input id="dealerPhone" value=""></div></div><div class="dealer-branding-grid"><div><label>Dealer Email</label><input id="dealerEmail" type="email" placeholder="name@company.com"></div><div><label>Website</label><input id="dealerWebsite" placeholder="www.yourcompany.com"></div><div><label>Business Address</label><input id="dealerAddress" placeholder="City, State / Province"></div></div><div class="dealer-logo-tools"><div><label style="display:block;margin-bottom:4px">Dealer Logo</label><input id="dealerLogoFile" type="file" accept="image/png,image/jpeg,image/webp" onchange="dealerLogoChanged(event)"></div><img id="dealerLogoPreview" class="dealer-logo-preview" style="display:none" alt="Dealer logo preview"><button type="button" class="ghost dealer-logo-clear" onclick="clearDealerLogo()">REMOVE DEALER LOGO</button><div class="dealer-logo-note">Your logo is saved in this browser and used on the customer estimate. If no logo is uploaded, the estimate uses your company name without a fallback brand logo.</div></div><div class="grid3" style="margin-top:10px"><div><label>Default Price / sq. ft.</label><input id="price" type="number" step="0.01" value="0.85"></div><div id="coverageWrap"><label>Coverage / gallon (dealer only)</label><input id="coverage" type="number" value="330"></div><div><label>Business Type</label><select id="businessType" onchange="businessTypeChanged()"><option value="roofing">Roofing</option><option value="commercial">Commercial Properties</option><option value="snow">Snow Removal</option><option value="pressure">Pressure Washing</option><option value="paving">Paving &amp; Sealcoating</option><option value="landscaping">Landscaping</option></select><div class="small">Selected for your account. Change only if your business offers a different service.</div></div></div><div class="grid3" style="margin-top:7px"><div><label>Pricing Mode</label><select id="pricingMode" onchange="pricingChanged()"><option value="regular">Regular Price + Tax</option><option value="included">Taxes Included Promotion</option><option value="discount">Discount Promotion</option></select></div><div><label>Promotion Discount %</label><input id="discountPct" type="number" step="0.1" value="0" oninput="renderSummary()"></div></div><div class="grid3" style="margin-top:7px"><div><label id="primaryTaxLabel">Sales Tax %</label><input id="gst" type="number" step="any" aria-describedby="taxPercentHelp" value="0" oninput="renderSummary()"></div><div id="secondaryTaxWrap" style="display:none"><label>Provincial Tax %</label><input id="pst" type="number" step="any" aria-describedby="taxPercentHelp" value="0" oninput="renderSummary()"></div></div><div id="taxPercentHelp" class="small">Enter 5 for 5% (not 0.05). Enter 0 for a tax you do not charge. Decimal rates such as 7.25 are supported.</div>
<div id="warrantyShieldSettings" style="display:none;margin-top:12px"><label><input type="checkbox" id="showWarrantyShield" checked> Show warranty shield on Roofing estimates</label><div class="small">Optional. Turn this off when using your own company branding. Save your profile to keep this choice.</div><button type="button" class="ghost" onclick="useApprovedDealerLogo()">USE APPROVED BRAND LOGO</button></div>
<details id="marketingSettings" class="marketing-settings"><summary>Estimate Marketing Section</summary><div class="marketing-settings-body"><div class="small" style="margin-bottom:8px">Optional. Turn this on to add your own benefits, warranty/message and call-to-action to customer estimates.</div><label class="marketing-toggle"><input id="marketingEnabled" type="checkbox" onchange="toggleMarketingEditor()"> Show marketing section on estimates</label><div id="marketingEditor" style="display:none"><label>Section Heading</label><input id="marketingHeading" placeholder="Example: WHY CHOOSE US"><div class="small" style="margin-top:8px"><button type="button" class="secondary" id="commercialMarketingPresetButton" style="display:none;margin:10px 0" onclick="loadCommercialMarketingPreset()">LOAD 6 COMMERCIAL BENEFITS</button><b>Benefit boxes</b> â€” leave unused rows blank.</div><div class="benefit-editor"><select id="benefitIcon1"><option value="âœ“">âœ“ Check</option><option value="â˜…">â˜… Star</option><option value="$">$ Savings</option><option value="â—†">â—† Diamond</option><option value="â—">â— Dot</option><option value="W">W Warranty</option></select><input id="benefitTitle1" placeholder="Benefit 1 headline"><input id="benefitText1" placeholder="Short description"></div><div class="benefit-editor"><select id="benefitIcon2"><option value="âœ“">âœ“ Check</option><option value="â˜…">â˜… Star</option><option value="$">$ Savings</option><option value="â—†">â—† Diamond</option><option value="â—">â— Dot</option><option value="W">W Warranty</option></select><input id="benefitTitle2" placeholder="Benefit 2 headline"><input id="benefitText2" placeholder="Short description"></div><div class="benefit-editor"><select id="benefitIcon3"><option value="âœ“">âœ“ Check</option><option value="â˜…">â˜… Star</option><option value="$">$ Savings</option><option value="â—†">â—† Diamond</option><option value="â—">â— Dot</option><option value="W">W Warranty</option></select><input id="benefitTitle3" placeholder="Benefit 3 headline"><input id="benefitText3" placeholder="Short description"></div><div class="benefit-editor"><select id="benefitIcon4"><option value="âœ“">âœ“ Check</option><option value="â˜…">â˜… Star</option><option value="$">$ Savings</option><option value="â—†">â—† Diamond</option><option value="â—">â— Dot</option><option value="W">W Warranty</option></select><input id="benefitTitle4" placeholder="Benefit 4 headline"><input id="benefitText4" placeholder="Short description"></div><div class="benefit-editor"><select id="benefitIcon5"><option value="âœ“">âœ“ Check</option><option value="â˜…">â˜… Star</option><option value="$">$ Savings</option><option value="â—†">â—† Diamond</option><option value="â—">â— Dot</option><option value="W">W Warranty</option></select><input id="benefitTitle5" placeholder="Benefit 5 headline"><input id="benefitText5" placeholder="Short description"></div><div class="benefit-editor"><select id="benefitIcon6"><option value="âœ“">âœ“ Check</option><option value="â˜…">â˜… Star</option><option value="$">$ Savings</option><option value="â—†">â—† Diamond</option><option value="â—">â— Dot</option><option value="W">W Warranty</option></select><input id="benefitTitle6" placeholder="Benefit 6 headline"><input id="benefitText6" placeholder="Short description"></div><div class="grid2" style="margin-top:10px"><div><label>Optional Warranty / Guarantee Statement</label><textarea id="marketingWarranty" placeholder="Example: Backed by our 5-year workmanship warranty."></textarea></div><div><label>Bottom Call-to-Action</label><input id="marketingCtaHeading" placeholder="Example: READY TO GET STARTED?"><label style="margin-top:7px">Call-to-Action Message</label><input id="marketingCtaText" placeholder="Example: Contact us today to schedule your service."></div></div></div></div></details>
<div class="actions"><button id="saveDealerProfileBtn" class="save-profile-btn" type="button" onclick="saveDealerDefaults()">SAVE DEALER PROFILE & BRANDING</button></div><div id="savedMsg"></div></div></details>
  <button id="measureClicked" onclick="startGarageMode()" style="display:none" disabled></button><div class="usage" id="usageLine"></div>
 </div>
 <div id="status" class="status"></div>
 <div id="jobSummaryBar" class="job-summary-bar"><div><span class="js-label">PROPERTY</span><b id="jsProperty">No property loaded</b></div><div><span class="js-label">ROOFS</span><b id="jsRoofs">â€”</b></div><div><span class="js-label">TOTAL AREA</span><b id="jsArea">â€”</b></div><div><span class="js-label">ESTIMATE</span><b id="jsTotal">â€”</b></div></div>
 <div id="solarFallback" class="fallbackbox"><b>Manual Measurement Required</b><div id="solarFallbackText" class="small" style="margin-top:4px">Google does not have an automatic roof measurement for this property. Trace the shingled roof area below and confirm the roof pitch.</div><div class="small" style="margin-top:6px"><b>Important:</b> If the aerial appears older, verify the current roof layout with the homeowner or on site before sending the estimate.</div></div>
 <div class="main">
  <div class="panel"><div class="ptitle">STEP 2 â€” Measure the property</div><button type="button" class="aq-context-help" data-aq-help-topic="measure">Help with this step</button><div class="measure-intro"><b>What do you need to measure?</b><span>Use one tool or combine multiple measurements on the same property.</span></div><div class="measure-toolbar"><button id="toolAutoBtn" type="button" class="measure-mode active" onclick="selectMeasurementTool('auto')"><b>AUTOMEASURE</b><small>Roof â€¢ automatic</small></button><button id="toolAreaBtn" type="button" class="measure-mode" onclick="startServiceAreaTool()"><b>+ ADD AREA</b><small>Lawns â€¢ driveways â€¢ parking</small></button><button id="toolLinearBtn" type="button" class="measure-mode" onclick="selectMeasurementTool('linear')"><b>+ LINEAR</b><small>Gutters â€¢ fencing â€¢ curbing</small></button></div><div id="jobMeasurements" class="job-measurements"><div class="jm-head"><b>Measurements for This Job</b><span class="small">Saved measurements stay with the property.</span></div><div id="jobMeasurementsList" class="jm-list"></div></div>
   <div id="garageControls" class="good auto-only" style="margin:8px"><div id="garageSavedConfirm" class="good" style="display:none;margin-bottom:8px;padding:10px;border:2px solid #2f7d44;font-size:15px"></div><div class="nexthelp"><b id="garageGuide">Load the property first. The main house will measure automatically.</b></div><div class="simple-actions" style="margin-top:10px"><button id="measureClickedTop" class="secondary primarybig" onclick="startGarageMode()" disabled>+ ADD GARAGE / OTHER ROOF</button><button class="ghost" onclick="removeLastExtra()">UNDO LAST ADDED ROOF</button></div><div class="small" style="margin-top:7px">Only use Add Garage / Other Roof when another shingled structure should be included.</div></div>
   <div id="roofCheckCard" class="stepcard auto-only" style="margin:10px 0"><h2 style="margin-bottom:5px">Is AutoMeasure showing the correct MAIN HOUSE?</h2><div class="small">If the blue outline is on the correct main house, continue. Garage and other-roof corrections are handled separately below.</div><div class="simple-actions" style="margin-top:9px"><button class="primary" onclick="roofCheckGood()">YES â€” MAIN HOUSE IS CORRECT</button></div><div id="roofFixHelp" class="small" style="margin-top:7px"></div><details class="roof-advanced"><summary>ROOF CORRECTIONS / ADVANCED OPTIONS</summary><div class="roof-advanced-body"><details style="margin-top:8px"><summary>Wrong garage / extra roof included? <span class="info-tip" tabindex="0" data-tip="Use this when Google correctly measured the main house but included a garage or other roof you do not want in the quote.">â“˜</span></summary><div class="small" style="padding:8px 0"><b>Remove only the wrong extra roof.</b> The main house stays in the quote. If you need the correct garage afterward, use <b>ADD / REMEASURE GARAGE OR OTHER ROOF</b> directly below.</div><div class="simple-actions" style="margin-top:8px"><button id="fixRoofBtn" class="ghost" onclick="toggleRoofFix()">REMOVE WRONG GARAGE / EXTRA ROOF</button></div></details><details style="margin-top:8px"><summary>Customer picture outline needs cleanup? <span class="info-tip" tabindex="0" data-tip="Picture only. Adjusting this outline does NOT change Google's square footage, pitch, or estimate price.">â“˜</span></summary><div class="small" style="padding:8px 0">This changes the customer picture only â€” not square footage, pitch or price.</div><div class="simple-actions"><button id="adjustOutlineBtn" class="secondary" onclick="toggleOutlineAdjust()">ADJUST CUSTOMER OUTLINE</button><button id="finishOutlineBtn" class="primary" onclick="finishOutlineAdjust()" disabled style="display:none">FINISH OUTLINE</button><button id="undoOutlineBtn" class="ghost" onclick="undoOutlinePoint()" style="display:none">UNDO POINT</button><button id="clearOutlineBtn" class="ghost" onclick="clearAdjustedOutline()" style="display:none">USE GOOGLE OUTLINE</button></div><div id="outlineHelp" class="small" style="margin-top:7px"></div></details><details style="margin-top:12px;border-top:1px solid #d9e3dc;padding-top:9px"><summary><b>Main house measurement is wrong?</b></summary><div class="warning" style="margin-top:8px"><b>Only use this to replace the MAIN HOUSE measurement.</b> Do not use this button for a garage or other added roof.</div><div class="simple-actions" style="margin-top:8px"><button id="manualOverrideBtn" class="danger" onclick="startManualOverride()">REPLACE MAIN HOUSE MEASUREMENT</button></div></details></div></details></div><div id="commercialAreaPanel" style="display:none;padding:10px;border:1px solid #ccd7e4;border-radius:8px;margin-bottom:8px"><b>Commercial service areas</b><div id="commercialAreaList"></div><button type="button" class="secondary" id="commercialAddAreaBtn" onclick="startServiceAreaTool()">+ ADD ANOTHER SERVICE AREA</button></div><div id="areaTool" class="area-tool"><div class="area-head"><div><div class="area-title">AREA MEASURE</div><div class="small">Measure the selected service area in square feet.</div></div><div id="areaTotal" class="area-total">Area: 0 ftÂ²</div></div><div class="area-body"><div class="simple-actions"><button id="areaCorrectBtn" type="button" class="secondary" onclick="correctAreaOutline()" style="display:none">CORRECT MEASUREMENT OUTLINE</button><button id="areaCancelCorrectionBtn" type="button" class="ghost" onclick="cancelAreaCorrection()" style="display:none">CANCEL CORRECTION</button><button id="areaStartBtn" type="button" class="secondary" onclick="toggleAreaMeasure()">START AREA MEASURE</button><button id="areaUndoBtn" type="button" class="ghost" onclick="undoAreaPoint()" style="display:none">UNDO LAST POINT</button><button id="areaClearBtn" type="button" class="ghost" onclick="clearAreaMeasure()" style="display:none">CLEAR AREA MEASUREMENT</button><button id="areaAutoBtn" type="button" class="ghost" onclick="returnAreaToAutoMeasure()" style="display:none">RETURN TO AUTOMEASURE</button></div><div id="areaHelp" class="small" style="margin-top:7px">Click Start Area Measure for a clean aerial workspace. Click around the outside edge of the service area, then save it.</div></div></div><div id="linearTool" class="linear-tool"><div class="linear-head"><div><div class="linear-title">LINEAR MEASURE</div><div class="small">Measure gutters, fencing, curbing, edging, crack sealing or any point-to-point distance.</div></div><div id="linearTotal" class="linear-total">Total: 0.0 ft</div></div><div class="linear-body"><div class="simple-actions"><button id="linearEditBtn" type="button" class="secondary" onclick="editLinearMeasure()" style="display:none">EDIT LINE</button><button id="linearSaveEditBtn" type="button" class="primary" onclick="saveLinearCorrection()" style="display:none">SAVE LINE CHANGES</button><button id="linearCancelEditBtn" type="button" class="ghost" onclick="cancelLinearCorrection()" style="display:none">CANCEL LINE EDIT</button><button id="linearStartBtn" type="button" class="secondary" onclick="toggleLinearMeasure()">START LINEAR MEASURE</button><button id="linearUndoBtn" type="button" class="ghost" onclick="undoLinearPoint()" style="display:none">UNDO LAST POINT</button><button id="linearClearBtn" type="button" class="ghost" onclick="clearLinearMeasure()" style="display:none">CLEAR LINEAR MEASUREMENT</button><button id="linearAutoBtn" type="button" class="ghost" onclick="returnToAutoMeasure()" style="display:none">RETURN TO AUTOMEASURE</button></div><div id="linearHelp" class="small" style="margin-top:7px">Click Start Linear Measure for a clean aerial workspace. Roof overlays hide while you draw. AeriQuote shows every segment and the running total. Use the measurement tools above to switch modes.</div></div></div><details id="manualRoofDetails" class="manualbox auto-only" open><summary id="manualRoofSummary">Add / Remeasure Garage or Other Roof</summary><div id="manualRoofWarning" class="warning" style="margin:8px 12px"><b>Google's confirmed MAIN HOUSE stays in the quote.</b> Use this to add or remeasure a garage, shed, addition, or other shingled roof.</div><div class="manualrow"><button id="traceBtn" class="orange" onclick="toggleTrace()">ADD / REMEASURE GARAGE OR OTHER ROOF</button><div id="tracePitchControl" class="pitch" style="display:none"><label id="manualPitchLabel" style="margin:0 0 3px" class="aeri-added-pitch-label">Pitch of Added Roof <span class="info-tip" tabindex="0" data-tip="Google supplies pitch for automatically measured roofs. For a manually traced roof, the dealer must confirm the pitch. 5/12 is only the starting default.">â“˜</span></label><select id="pitchSel" onchange="pitchChanged()" class="pitch-select"><option value="">Select roof pitch</option><option value="18.43">4/12</option><option value="22.62" selected>5/12</option><option value="26.57">6/12</option><option value="30.26">7/12</option><option value="33.69">8/12</option><option value="36.87">9/12</option><option value="39.81">10/12</option><option value="42.51">11/12</option><option value="45">12/12</option><option value="custom">CustomÂ°</option></select></div><input id="pitchDeg" type="hidden" value="22.62"><button id="finishTrace" class="secondary" onclick="finishTrace()" disabled style="display:none">SAVE & ADD ROOF</button><button id="undoTraceBtn" class="ghost" onclick="undoPoint()" style="display:none">UNDO LAST POINT</button><button id="clearManualBtn" class="danger" onclick="clearManual()" style="display:none">CLEAR CURRENT DRAWING</button></div><div id="pitchReminder" class="pitch-reminder"><b>Confirm the roof pitch.</b> Manual roofs start at 5/12. Change it if needed before saving.</div><div id="manualRoofHelp" class="small" style="padding:0 12px 10px">Click around only the garage or other roof you want to add, confirm its pitch, then press SAVE & ADD ROOF. The Google main house stays unchanged.</div></details>
   <details id="advancedOptions" class="advanced"><summary>Show advanced roof display options</summary><div style="padding:8px 10px"><b>Roof Outlines:</b> <select id="outlineMode" onchange="redrawRoofData()" style="width:auto"><option value="smart">Actual Roof Outline (Recommended)</option><option value="all">Show Google segment boxes</option><option value="clean">Pitch labels only</option></select></div></details>
   <div class="mapwrap"><div id="loading" class="loading" style="display:none">Loading aerial imageryâ€¦</div><div id="traceBanner" class="tracebanner">MANUAL MEASURE ON â€” click roof corners, then SAVE & ADD ROOF</div><div id="map"></div></div>
  </div>
  <div class="panel"><div class="ptitle">STEP 3 â€” Review & price</div><button type="button" class="aq-context-help" data-aq-help-topic="price">Help with this step</button><div class="side"><img id="street" class="street" alt="Actual Street View"><div id="streetMeta" class="small" style="margin-top:4px"></div><div id="jobPriceCard" class="stepcard measurement-price-card" style="margin-top:10px"><h2 id="jobPriceTitle">Price for this job</h2><label id="jobPriceLabel">Price for This Job / sq. ft. <span class="info-tip" tabindex="0" data-tip="Your dealer default loads here automatically. Change this number for any individual job and the quote recalculates immediately.">â“˜</span></label><input id="jobPrice" type="number" step=".01" value=".95" oninput="jobPriceChanged()" onchange="jobPriceChanged()"><div id="jobPriceHelp" class="small">This is the price used for the quote. Change it anytime before creating the estimate.</div><div id="appliedJobPrice" class="good" style="margin-top:7px;padding:7px">Quote is using <b>$0.95 / sq. ft.</b></div></div><div id="estimatePeriodWrap" style="display:none;margin-top:10px"><label for="estimatePeriod">Price covers</label><select id="estimatePeriod" onchange="renderSummary()"><option value="one_time">One-time service</option><option value="visit">Per visit</option><option value="snowfall">Per snowfall</option><option value="month">Per month</option><option value="season">Per season</option><option value="year">Per year</option></select><div class="small">The calculated amount applies to this period. It is not multiplied by visits or months. Any additional services use the same period.</div></div><div id="summary"></div><div class="stepcard workflow-next"><h2>STEP 4 â€” Customer</h2><button type="button" class="aq-context-help" data-aq-help-topic="customer">Help with this step</button><div class="customer-grid"><div class="full"><label>Customer Name</label><input id="customerName" name="aq_job_customer_name" autocomplete="new-password" readonly onfocus="this.removeAttribute('readonly')" placeholder="Customer name" oninput="updateProgressSteps()"></div><div><label>Customer Phone</label><input id="customerPhone" name="aq_job_customer_phone" autocomplete="new-password" readonly onfocus="this.removeAttribute('readonly')" placeholder="Phone" oninput="updateProgressSteps()"></div><div><label>Customer Email</label><input id="customerEmail" name="aq_job_customer_email" autocomplete="new-password" readonly onfocus="this.removeAttribute('readonly')" type="email" placeholder="Email" oninput="updateProgressSteps()"></div><div class="full"><label>Customer / Job Notes <span class="small">(optional)</span></label><textarea id="customerNotes" name="aq_job_customer_notes" autocomplete="new-password" readonly onfocus="this.removeAttribute('readonly')" placeholder="Optional notes for this customer or job"></textarea></div></div></div><div class="stepcard workflow-next"><h2>STEP 5 â€” Create estimate</h2><button type="button" class="aq-context-help" data-aq-help-topic="estimate">Help with this step</button><label>Additional Services / Repairs <span class="small">(optional)</span></label><input id="extraServiceDescription" placeholder="Example: Replace damaged shingles, seal vent, minor roof repair" oninput="renderSummary()"><label style="margin-top:8px">Additional Services / Repairs Amount</label><input id="extraServiceAmount" type="number" min="0" step="0.01" value="0" oninput="renderSummary()"><div class="small" style="margin-top:5px">Added to the estimate and uses the same sales-tax setting as this job.</div><label style="margin-top:10px">Estimate images</label><select id="streetViewChoice"><option value="auto" selected>Use Aerial + Google Street View</option><option value="hide">Use Aerial + Property Assessment Placeholder</option><option value="none">Create Estimate Without Images</option></select><div class="simple-actions" style="margin-top:10px"><button id="createEstimateBtn" class="primarybig" onclick="showCustomerEstimate()" disabled>CREATE CUSTOMER ESTIMATE</button></div></div></div></div>
 </div>
</div></div>

<div id="historyModal" class="historyModal"><div class="historyBox"><div class="historyHead"><div><h2 style="margin:0;color:var(--green2)">Previous Estimates</h2><div class="small">Find and reopen a saved estimate or review its earlier versions.</div></div><button class="ghost" onclick="closeEstimateHistory()">CLOSE</button></div><div style="display:flex;gap:8px;margin-top:14px"><input id="historySearch" placeholder="Search customer, address, phone or email" onkeydown="if(event.key==='Enter')searchEstimateHistory()"><button onclick="searchEstimateHistory()">SEARCH</button></div><div class="historyColumns"><div>Customer</div><div>Property</div><div>Date</div><div>Estimate</div><div>Actions</div></div><div id="historyResults" class="historyResults"><div class="small" style="padding:14px 0">Your saved estimates will appear here.</div></div></div></div>

<div id="trialLimitOverlay" class="trial-limit-overlay" role="dialog" aria-modal="true" aria-labelledby="trialLimitTitle"><div class="trial-limit-card"><h2 id="trialLimitTitle">Youâ€™ve Used Your 3 Free Property Measurements</h2><p>Your AeriQuote free trial included 3 property measurements and estimates.</p><p>Choose a plan to continue measuring properties and creating professional estimates.</p><div class="trial-limit-actions"><a href="/site/pricing.html">VIEW PLANS â†’</a><button type="button" onclick="closeTrialLimit();openEstimateHistory()">BACK TO MY ACCOUNT</button></div><p class="trial-note">No automatic billing. Choose a plan only when you're ready.</p></div></div>
<div id="reportOverlay"><div class="report" style="width:min(1320px,calc(100vw - 44px));">
 <div class="reportHead"><img id="rDealerLogo" class="logo dealerLogo noDealerLogo" alt="Dealer logo"><div><h1 id="rEstimateTitle">Property Measurement &amp; Estimate</h1><div id="rEstimateSubtitle" style="text-align:center;color:#28612f;font-weight:800;margin-top:6px"></div><div id="rEstimateDealerSub" class="reportDealerSub"></div></div><div><img id="rWarrantyShield" alt="6-Year Transferable Warranty" style="display:none;width:125px;max-width:100%;height:125px;object-fit:contain"></div></div>
 <div class="reportMeta"><div><b>Property Address</b><div id="rAddress"></div></div><div><b>Date Prepared</b><div id="rDate"></div></div><div><b>Prepared For</b><div id="rCustomerName">Homeowner</div><div id="rCustomerPhone" class="small"></div><div id="rCustomerEmail" class="small"></div></div></div>
 <div class="reportGrid"><div>
  <div class="reportPanel"><div class="reportTitle">PROPERTY ASSESSMENT</div><div class="reportMapWrap"><div id="customerMap" class="customerMap"></div><svg id="reportDrawLayer" class="reportDrawLayer" aria-label="Draw customer measurement outline"></svg></div><div id="reportOutlineControls" class="estimateOutlineBar"><div id="reportOutlineTargetButtons" style="display:flex;gap:7px;flex-wrap:wrap"></div><button id="reportCancelOutlineBtnTop" class="danger" onclick="cancelReportOutlineEdit()" style="display:none">CANCEL OUTLINE EDIT</button><button id="reportUndoOutlineBtnTop" class="ghost" onclick="undoReportOutlinePoint()" style="display:none">UNDO POINT</button><button id="reportSaveOutlineBtnTop" class="primary" onclick="saveReportOutline()" style="display:none" disabled>SAVE OUTLINE</button><button id="reportRedrawBtn" class="ghost" onclick="redrawSelectedReportMeasurement()" style="display:none">REDRAW</button><span id="reportOutlineHelpTop" class="reportEditHelp">Choose an outline to edit. Picture only â€” quote numbers do not change.</span></div><div id="customerMapPlaceholder" class="reportImagePlaceholder"><div><div class="big">PROPERTY ASSESSMENT</div><div style="margin-top:10px;font-weight:700">Professional property estimate prepared for this address.</div><div class="small" style="margin-top:8px">Property imagery omitted from this estimate.</div></div></div><div class="reportBody"><div id="rProperty"></div></div></div>
  <div class="reportPrice"><div class="rphead">ESTIMATE SUMMARY</div><div class="rpbody" id="rPricing"></div></div>
 </div><div>
  <div class="reportPanel"><div class="reportTitle">PROPERTY IMAGE</div><div class="reportBody">
<div id="streetPlaceholder" style="display:none;height:225px;border-radius:8px;border:1px solid #cde5d4;background:linear-gradient(135deg,#f3f7f4,#e6efe9);align-items:center;justify-content:center;text-align:center;padding:20px;color:#174f2b"><div><b style="font-size:18px">PROPERTY ASSESSMENT COMPLETED</b><br><span id="reportPropertyImageNote" class="small">Roof measured using available aerial imagery.</span></div></div>
<img id="rStreet" class="reportStreet"><div id="rStreetMeta" class="small" style="margin-top:4px"></div></div></div>
   <div id="rMarketingPanel" class="reportPanel marketingHidden" style="margin-top:12px"><div id="rMarketingHeading" class="reportTitle"></div><div id="rMarketingBenefits" class="reportBody"></div><div id="rMarketingWarranty" class="marketingWarranty marketingHidden"></div></div>
   <div class="cta"><strong id="rCtaHeading">YOUR ESTIMATE</strong><div id="rCtaText" style="margin-top:5px;color:#f59d0a;font-weight:800"></div><div style="margin-top:9px"><b id="rDealerCompany"></b></div><div id="rDealerName" style="margin-top:2px"></div><div class="dealerContactCompact"><span id="rPhoneWrap">Call or Text: <b id="rPhone"></b></span><span id="rDealerEmailWrap"><span class="contactSep">â€¢</span><span id="rDealerEmail"></span></span><br><span id="rDealerWebsite"></span><span id="rDealerAddressWrap"><span class="contactSep">â€¢</span><span id="rDealerAddress"></span></span></div></div>
 </div></div>
 <div class="reportFoot">Remote aerial measurements are used for estimating. Final property conditions and measurements should be confirmed before work begins.</div>
 <div class="reportActions"><span id="reportOutlineHelp" class="reportEditHelp" style="display:none"></span><label style="font-weight:700">PDF layout <select id="estimatePdfLayout" aria-label="PDF layout"><option value="single">Single page</option><option value="expanded">Expanded - aerial, then details</option>{% if VECTOR_PDF_QA_FLAG == "1" %}<option value="vector">Vector Diagram - QA only</option>{% endif %}</select></label><button id="downloadPdfBtn" class="primary" onclick="downloadEstimatePDF()">DOWNLOAD ESTIMATE PDF</button><button class="secondary" onclick="printEstimate()">PRINT ESTIMATE</button><button class="primary" onclick="startNewProperty()">NEW PROPERTY / NEXT ESTIMATE</button><button id="backToDealerBtn" class="secondary" onpointerdown="armReportClose(event)" onclick="closeReport(event)">Back to Dealer View</button></div>
</div></div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/georaster"></script>
<script src="https://unpkg.com/georaster-layer-for-leaflet"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
<!-- AERIQUOTE V11.6.70 LINEAR MODE ISOLATION + V1 CANADA + USA: dealer polish built directly from VERIFIED V11.6.56. Only dealer-facing version cleanup and the read-only job summary strip were added. Measurement, address, map, outline, dealer branding and PDF capture mechanics are unchanged. -->
<script>
const MANUAL_ROOF_QA='{{ MANUAL_ROOF_QA_FLAG }}'==='1';
let manualRoofEditIndex=null;
function manualRoofQa(){return typeof MANUAL_ROOF_QA!=='undefined'&&MANUAL_ROOF_QA&&currentBusinessType()==='roofing'}
let map=L.map('map',{maxZoom:22,zoomControl:true,zoomSnap:.25,zoomDelta:.5}).setView([52.1522,-106.6595],19);
let skipAddressConflictOnce=false;
L.control.scale({imperial:true,metric:true}).addTo(map);
let rgbLayer=null,roofMask=null,sessionToken=null,clicked=null,clickMarker=null,structures=[],overlays=[],mainBounds=null;
let roofRemeasureTarget=null;
let roofOutlineReviewMode=false;
let roofReviewBoundarySource="detected",roofReviewManualIndices=[];
let traceMode=false,tracePoints=[],tempTraceLayers=[],manualPlanes=[],manualLayers=[],garageMode=false,roofFixMode=false,locateRoofMode=false,fallbackMode=false,fallbackLayer=null,fallbackBounds=null,traceSavePopup=null;
let linearCorrectionOriginal=null;
let measurementMapDraggingWasEnabled=null;
let surfaceLineDraftOriginal=null,areaCorrectionOriginal=null,areaRemeasureMode=false;
let linearMode=false,linearPoints=[],linearLayers=[],linearMeasurementSaved=false,areaMode=false,areaPoints=[],areaLayers=[],areaMeasurementSaved=false,measurementViewMode='auto',pendingMeasurementMode='auto';
let outlineEditMode=false,outlinePoints=[],outlineTempLayers=[],adjustedOutline=null,adjustedOutlineLayer=null,addressPreviewTimer=null,addressPreviewSeq=0,lastLoadedStreet='',propertyMarker=null,manualOverrideMode=false,manualAerialSwitching=false;
let customerMap=null,customerRgbLayer=null,customerOverlays=[],reportOutlines={},reportOutlineTarget=null,reportOutlineEditMode=false,reportOutlinePoints=[],reportOutlineTemp=[];
let quoteSnapshot=null;
let commercialAreas=[],commercialAreaLayers=[],commercialEditingIndex=-1;
let savedLinearJobRate=null;
let savedStreetImageData='';
let savedEstimateEditContext=null,savedPropertyEditActive=false,savedJobDetails=null;
let exactPinDisplay=false;
let estimateOpenInProgress=false,customerMapBuildTimer=null,pdfInProgress=false;
let usage={property:0,structures:0,reports:0,saved:0,area:0,linear:0};
let lastHistorySaveKey='';

const legend=L.control({position:'bottomright'});legend.onAdd=()=>{const d=L.DomUtil.create('div');d.style.cssText='background:white;padding:7px 9px;border-radius:7px;box-shadow:0 1px 5px #0003;font-size:11px;line-height:1.5';d.innerHTML='<b>Roof Segments</b><br>Blue = Main House<br>Teal = Extra Structure<br>Gold = Pitch';return d};legend.addTo(map);if(legend.getContainer())legend.getContainer().classList.add('roof-legend');
map.on('click',e=>{if(areaMode){addAreaPoint(e.latlng);return}if(linearMode){addLinearPoint(e.latlng);return}if(outlineEditMode){addOutlinePoint(e.latlng);return}if(traceMode){if(manualRoofEditIndex!==null){status('Drag an existing roof corner to adjust this section. Save the changes or Cancel to restore it.','warn');return}addTracePoint(e.latlng);return}if(roofFixMode){removeClickedExtraRoof(e.latlng);return}if(locateRoofMode){retryRoofAt(e.latlng);return}if(!garageMode)return;clicked=e.latlng;if(clickMarker)clickMarker.remove();clickMarker=L.marker(e.latlng).addTo(map).bindPopup('Measuring selected roofâ€¦').openPopup();garageMode=false;measureClicked();});

function el(id){return document.getElementById(id)}function fmt(n){return Math.round(Number(n||0)).toLocaleString()}function currencyCode(){return (el('dealerCountry')?.value||'US')==='CA'?'CAD':'USD'}function money(n){const c=currencyCode();return new Intl.NumberFormat(c==='CAD'?'en-CA':'en-US',{style:'currency',currency:c}).format(Number(n||0))}function status(t,k=''){if(currentBusinessType()==='snow')t=translateSnowText(String(t));const surface=['commercial','paving','pressure','landscaping','snow'].includes(currentBusinessType());if(surface)t=String(t).replace(/AutoMeasure remains hidden until you return to it\.?/gi,'Your service measurement has been saved.').replace(/Roof AutoMeasure is not included in this service-area quote\.?/gi,'Only the selected service measurements are included in this quote.');el('status').textContent=t;el('status').className='status '+k}function showLoad(v){el('loading').style.display=v?'block':'none'}
const AERIQUOTE_US_STATES=`<option value="AL">AL</option><option value="AK">AK</option><option value="AZ">AZ</option><option value="AR">AR</option><option value="CA">CA</option><option value="CO">CO</option><option value="CT">CT</option><option value="DE">DE</option><option value="FL">FL</option><option value="GA">GA</option><option value="HI">HI</option><option value="ID">ID</option><option value="IL">IL</option><option value="IN">IN</option><option value="IA">IA</option><option value="KS">KS</option><option value="KY">KY</option><option value="LA">LA</option><option value="ME">ME</option><option value="MD">MD</option><option value="MA">MA</option><option value="MI">MI</option><option value="MN">MN</option><option value="MS">MS</option><option value="MO">MO</option><option value="MT">MT</option><option value="NE">NE</option><option value="NV">NV</option><option value="NH">NH</option><option value="NJ">NJ</option><option value="NM">NM</option><option value="NY">NY</option><option value="NC">NC</option><option value="ND">ND</option><option value="OH">OH</option><option value="OK">OK</option><option value="OR">OR</option><option value="PA">PA</option><option value="RI">RI</option><option value="SC">SC</option><option value="SD">SD</option><option value="TN">TN</option><option value="TX">TX</option><option value="UT">UT</option><option value="VT">VT</option><option value="VA">VA</option><option value="WA">WA</option><option value="WV">WV</option><option value="WI">WI</option><option value="WY">WY</option><option value="DC">DC</option>`;
const AERIQUOTE_CA_PROVINCES=`<option value="AB">AB â€” Alberta</option><option value="BC">BC â€” British Columbia</option><option value="MB">MB â€” Manitoba</option><option value="NB">NB â€” New Brunswick</option><option value="NL">NL â€” Newfoundland and Labrador</option><option value="NS">NS â€” Nova Scotia</option><option value="NT">NT â€” Northwest Territories</option><option value="NU">NU â€” Nunavut</option><option value="ON">ON â€” Ontario</option><option value="PE">PE â€” Prince Edward Island</option><option value="QC">QC â€” Quebec</option><option value="SK">SK â€” Saskatchewan</option><option value="YT">YT â€” Yukon</option>`;
function provinceRules(code){return [Number(el('gst')?.value||0),Number(el('pst')?.value||0)]}
function countryChanged(preserveRegion=false){
 if(typeof initializePropertyRegions==='function')initializePropertyRegions();
 const country=el('dealerCountry')?.value||'US',region=el('province'),old=region?.value||'';
 if(el('regionLabel'))el('regionLabel').textContent=country==='CA'?'Province / territory':'State';
 if(el('primaryTaxLabel'))el('primaryTaxLabel').textContent=country==='CA'?'Federal Tax %':'Sales Tax %';
 // Filtering location options must never reset a job's tax rates.
 const tax=el('secondaryTaxWrap');if(tax){tax.style.display=country==='CA'||Number(el('pst')?.value||0)!==0?'block':'none';const label=tax.querySelector('label');if(label)label.textContent=country==='CA'?'Provincial Tax %':'Additional Tax %'}
 if(region){
  const previous=region.dataset.country,remembered=region._countryRegions||(region._countryRegions={});
  if(previous)remembered[previous]=old;
  const selected=previous===country?old:(remembered[country]??((preserveRegion||!previous)?old:''));
  region.innerHTML='<option value="">Choose your '+(country==='CA'?'province / territory':'state')+'</option>'+(country==='CA'?AERIQUOTE_CA_PROVINCES:AERIQUOTE_US_STATES);
  region.value=[...region.options].some(o=>o.value===selected)?selected:'';region.dataset.country=country;
 }
 renderSummary();
}
function provinceChanged(){renderSummary()}function pricingChanged(){el('discountPct').disabled=el('pricingMode').value!=='discount';renderSummary()}
function dealerLogoChanged(event){
 const file=event&&event.target&&event.target.files?event.target.files[0]:null;if(!file)return;
 if(!/^image\/(png|jpeg|webp)$/i.test(file.type)){status('Please choose a PNG, JPG or WEBP logo.','error');if(el('dealerLogoFile'))el('dealerLogoFile').value='';return}
 if(file.size>4000000){status('That logo file is too large. Please use an image under 4 MB.','error');if(el('dealerLogoFile'))el('dealerLogoFile').value='';return}
 const reader=new FileReader();reader.onload=()=>{const img=new Image();img.onload=()=>{try{const maxW=700,maxH=240,scale=Math.min(1,maxW/img.width,maxH/img.height),w=Math.max(1,Math.round(img.width*scale)),h=Math.max(1,Math.round(img.height*scale)),c=document.createElement('canvas');c.width=w;c.height=h;const ctx=c.getContext('2d');ctx.clearRect(0,0,w,h);ctx.drawImage(img,0,0,w,h);const data=c.toDataURL('image/png');applyDealerLogo(data);status('Dealer logo ready. Click SAVE DEALER PROFILE & BRANDING to save the rest of the profile.','ok')}catch(e){status('Could not prepare that logo. Try a different image.','error')}};img.onerror=()=>status('Could not read that logo image.','error');img.src=reader.result};reader.onerror=()=>status('Could not read that logo file.','error');reader.readAsDataURL(file)
}
let dealerLogoData=null,dealerLogoDirty=false,dealerBrandingAccount='',dealerLogoRevision=0;
function applyDealerLogo(src,dirty=true){
 dealerLogoData=typeof src==='string'?src:'';if(dirty){dealerLogoDirty=true;dealerLogoRevision++;}
 try{if(dealerLogoData)localStorage.setItem('sxDealerLogo',dealerLogoData);else localStorage.removeItem('sxDealerLogo')}catch(e){}
 const preview=el('dealerLogoPreview');if(preview){if(dealerLogoData){preview.src=dealerLogoData;preview.style.display='block'}else{preview.removeAttribute('src');preview.style.display='none'}}
}
function clearDealerLogo(){applyDealerLogo('');if(el('dealerLogoFile'))el('dealerLogoFile').value='';status('Dealer logo removed. Your company name will be used on estimates.','ok')}
function dealerLogoSrc(){if(dealerLogoData!==null)return dealerLogoData;try{return localStorage.getItem('sxDealerLogo')||''}catch(e){return''}}


const AERI_TERMS={
 roofing:{label:'Roofing'},
 commercial:{label:'Commercial Properties'},
 snow:{label:'Snow Removal'},
 pressure:{label:'Pressure Washing'},
 paving:{label:'Paving & Sealcoating'},
 landscaping:{label:'Landscaping'}
};
const AERI_TOOL_COPY={
 roofing:{area:'Roof footprints â€¢ flat areas',linear:'Gutters â€¢ eaves â€¢ ridges',distance:'Measure gutters, eaves, ridges or other roof work priced by length.'},
 snow:{area:'Driveways â€¢ parking lots â€¢ service areas',linear:'Sidewalks â€¢ curbs â€¢ access runs',distance:'Measure sidewalks, curbs and access routes priced by length.'},
 pressure:{area:'Driveways â€¢ patios â€¢ sidewalks â€¢ parking',linear:'Gutters â€¢ fencing â€¢ cleaning runs',distance:'Measure gutters, fencing or other cleaning work priced by length.'},
 paving:{area:'Driveways â€¢ parking lots â€¢ paved areas',linear:'Curbing â€¢ edging â€¢ crack sealing',distance:'Measure curbing, edging and crack sealing priced by length.'},
 landscaping:{area:'Lawns â€¢ sod â€¢ garden beds â€¢ patios',linear:'Edging â€¢ borders â€¢ retaining walls',distance:'Measure edging, borders and retaining walls priced by length.'},
 commercial:{area:'Parking lots â€¢ walkways â€¢ grounds',linear:'Curbs â€¢ fencing â€¢ access routes',distance:'Measure curbs, fencing and other commercial services priced by length.'}
};
const _aeriOriginalText=new WeakMap();
const _aeriOriginalAttributes=new WeakMap();
function currentBusinessType(){const selected=(el('businessType')&&el('businessType').value)||'';const requested=new URLSearchParams(window.location.search).get('industry');return requested==='commercial'&&!quoteSnapshot?.savedPricing?'commercial':(selected||requested||'roofing')}
function translateSnowText(t){
 const rules=[
  [/Additional Services \/ Repairs/gi,'Additional Snow Services'],
  [/Main house measured\./gi,'Primary service area measured.'],
  [/Main house measurement is wrong\?/gi,'Primary service area measurement is wrong?'],
  [/MAIN HOUSE/g,'PRIMARY SERVICE AREA'],[/Main House/g,'Primary Service Area'],[/main house/g,'primary service area'],
  [/Choose which area outline to edit\.[\s\S]*?Picture only â€” measurements and price stay unchanged\./gi,'Choose which service area outline to edit. Primary and additional service areas can be edited separately. Picture only â€” measurements and price stay unchanged.'],
  [/Google(?:'|â€™|&#x27;)s confirmed PRIMARY SERVICE AREA stays in the quote\./gi,'The confirmed PRIMARY SERVICE AREA stays in the quote.'],
  [/Google(?:'|â€™|&#x27;)s confirmed primary service area stays in the quote\./gi,'The confirmed primary service area stays in the quote.'],
  [/Use this to add or remeasure (?:a|an) additional area, shed, addition, or other service area\./gi,'Use this to add or remeasure another service area.'],
  [/Use this to add or remeasure a garage, shed, addition, or other (?:shingled structure|service area)\./gi,'Use this to add or remeasure another service area.'],
  [/Wrong additional area \/ extra area included\?/gi,'Wrong area included?'],
  [/Wrong garage \/ extra area included\?/gi,'Wrong area included?'],
  [/not square footage, pitch or price/gi,'not square footage or price'],
  [/garage and other-area corrections/gi,'additional-area corrections'],
  [/garage afterward/gi,'additional area afterward'],
  [/garage, shed, addition, or other service area/gi,'another service area'],
  [/garage, shed, addition, or other shingled structure/gi,'another service area'],
  [/GARAGE \/ OTHER ROOF/g,'ADDITIONAL AREA'],[/Garage \/ Other Roof/g,'Additional Area'],[/garage \/ other roof/g,'additional area'],
  [/GARAGE OR OTHER ROOF/g,'ADDITIONAL AREA'],[/Garage or Other Roof/g,'Additional Area'],[/garage or other roof/g,'additional area'],
  [/GARAGE/g,'ADDITIONAL AREA'],[/Garage/g,'Additional Area'],[/garage/g,'additional area'],
  [/\bSHED\b/g,'ADDITIONAL AREA'],[/\bShed\b/g,'Additional Area'],[/\bshed\b/g,'additional area'],
  [/ADDED ROOF/g,'ADDED AREA'],[/Added Roof/g,'Added Area'],[/added roof/g,'added area'],
  [/EXTRA ROOF/g,'EXTRA AREA'],[/Extra Roof/g,'Extra Area'],[/extra roof/g,'extra area'],
  [/OTHER ROOF/g,'ADDITIONAL AREA'],[/Other Roof/g,'Additional Area'],[/other roof/g,'additional area'],
  [/ROOFS IN QUOTE/g,'AREAS IN QUOTE'],[/Roofs in Quote/g,'Areas in Quote'],[/roofs in quote/g,'areas in quote'],
  [/ROOF ASSESSMENT/g,'PROPERTY ASSESSMENT'],[/Roof Assessment/g,'Property Assessment'],[/roof assessment/g,'property assessment'],
  [/ROOF MEASUREMENT/g,'AREA MEASUREMENT'],[/Roof Measurement/g,'Area Measurement'],[/roof measurement/g,'area measurement'],
  [/ROOF OUTLINE/g,'AREA OUTLINE'],[/Roof Outline/g,'Area Outline'],[/roof outline/g,'area outline'],
  [/ROOF CORRECTIONS/g,'AREA CORRECTIONS'],[/Roof Corrections/g,'Area Corrections'],[/roof corrections/g,'area corrections'],
  [/ROOF AREA/g,'SERVICE AREA'],[/Roof Area/g,'Service Area'],[/roof area/g,'service area'],
  [/TREATMENT AREA/g,'SERVICE AREA'],[/Treatment Area/g,'Service Area'],[/treatment area/g,'service area'],
  [/SHINGLED STRUCTURE/g,'SERVICE AREA'],[/Shingled Structure/g,'Service Area'],[/shingled structure/g,'service area'],
  [/SHINGLED ROOF/g,'SERVICE AREA'],[/Shingled Roof/g,'Service Area'],[/shingled roof/g,'service area'],
  [/ROOFS/g,'AREAS'],[/Roofs/g,'Areas'],[/roofs/g,'areas'],
  [/Actual Roof Outline/gi,'Measured Area Outline'],
  [/Show Google segment boxes/gi,'Show Measured Sections'],
  [/pitch labels only/gi,'measurement labels only'],
  [/roof segments/gi,'measured sections'],
  [/area segments/gi,'measured sections'],
  [/pitch included/gi,'automatic area measurement'],
  [/confirm its pitch/gi,'confirm the area'],
  [/confirm the pitch/gi,'confirm the area'],
  [/Google Service Area/gi,'Service Area'],
  [/Google Automatic Measurement â€” automatic area measurement/gi,'Automatic Area Measurement'],
  [/ROOF/g,'AREA'],[/Roof/g,'Area'],[/roof/g,'area']
 ];
 let out=t;for(const [a,b] of rules)out=out.replace(a,b);return out
}

function polishRoofingManualTraceControls(){
 if(currentBusinessType()!=='roofing')return;
 const leaves=Array.from(document.querySelectorAll('body *')).filter(x=>!x.children.length && !['SCRIPT','STYLE','OPTION'].includes(x.tagName));
 const pitchLabel=leaves.find(x=>(x.textContent||'').trim()==='Pitch of Added Roof â“˜') ||
                  leaves.find(x=>/^Pitch of Added Roof/i.test((x.textContent||'').trim()));
 if(!pitchLabel)return;
 pitchLabel.textContent='Pitch of Main Roof â“˜';
 const wrap=pitchLabel.parentElement;
 if(wrap){
   wrap.classList.add('aeri-dynamic-main-pitch');
   const sel=wrap.querySelector('select') || wrap.parentElement?.querySelector('select');
   if(sel)sel.classList.add('aeri-dynamic-main-pitch-select');
 }
 const finish=leaves.find(x=>(x.textContent||'').trim()==='FINISH MEASUREMENT');
 if(finish){
   finish.classList.add('aeri-dynamic-finish-measurement');
   const parent=finish.parentElement;
   if(parent)parent.classList.add('aeri-dynamic-manual-actions');
 }
}

function translatePressureText(t){
 const rules=[
 [/LOAD & MEASURE ROOF/gi,'LOAD PROPERTY & MEASURE SURFACE'],
 [/Roof â€¢ automatic/gi,'Roof â€¢ automatic (Roofing only)'],
 [/Lawns â€¢ driveways â€¢ parking/gi,'Driveways â€¢ patios â€¢ sidewalks â€¢ parking'],
 [/ROOFS IN QUOTE/gi,'SURFACES IN QUOTE'],
 [/Roofs in Quote/gi,'Surfaces in Quote'],
 [/Google Roof Area/gi,'Measured Surface Area'],
 [/Main house will measure automatically/gi,'Select Area Measurement to outline the surface'],
 [/main house will measure automatically/gi,'select Area Measurement to outline the surface'],
 [/Finish the manual roof trace first/gi,'Finish and save a surface-area measurement first'],
 [/Trace the shingled roof around the customer property pin to unlock pricing and the customer estimate/gi,'Outline and save the cleaning surface to unlock pricing and the customer estimate'],
 [/Additional Services \/ Repairs/gi,'Additional Cleaning Services'],
 [/Example: Replace damaged shingles, seal vent, minor roof repair/gi,'Example: Additional patio, sidewalk or driveway cleaning']
 ];let v=t;for(const [re,to] of rules)v=v.replace(re,to);return v;
}
function translatePavingText(t){return translatePressureText(t).replace(/Gutters â€¢ fencing â€¢ curbing/g,'Curbing â€¢ edging â€¢ crack sealing').replace(/Additional Cleaning Services/g,'Additional Paving & Sealcoating Services').replace(/cleaning surface/gi,'paved surface').replace(/cleaning surfaces/gi,'paved surfaces').replace(/cleaning/gi,'paving & sealcoating');}
function translateLandscapingText(t){return translatePressureText(t).replace(/Driveways â€¢ patios â€¢ sidewalks â€¢ parking/g,'Lawns â€¢ sod â€¢ garden beds â€¢ patios').replace(/Gutters â€¢ fencing â€¢ curbing/g,'Edging â€¢ borders â€¢ retaining walls').replace(/Additional Cleaning Services/g,'Additional Landscaping Services').replace(/cleaning surface/gi,'landscaping area').replace(/cleaning surfaces/gi,'landscaping areas').replace(/cleaning/gi,'landscaping');}
function applyBusinessTerminology(root=document.body){
 const mode=currentBusinessType();
 // Translate interface copy only. These fields render immutable user/provider data.
 const protectedContent='.expandedPdfExport,.pdf-export,#jsProperty,#rAddress,#rCustomerName,#rCustomerPhone,#rCustomerEmail,#rEstimateSubtitle,#rEstimateDealerSub,#rDealerCompany,#rDealerName,#rPhone,#rDealerEmail,#rDealerWebsite,#rDealerAddress,#rMarketingHeading,#rMarketingBenefits,#rMarketingWarranty,#rCtaHeading,#rCtaText,#historyResults,#rPricing,#rProperty,#summary,#googleMatch,#addressAutoStatus,#propertyVerify';
 const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
 const nodes=[];while(walker.nextNode())nodes.push(walker.currentNode);
 nodes.forEach(n=>{
   const p=n.parentElement;if(!p||['SCRIPT','STYLE','OPTION'].includes(p.tagName)||p.closest(protectedContent))return;
   if(!_aeriOriginalText.has(n))_aeriOriginalText.set(n,n.nodeValue);
   const base=_aeriOriginalText.get(n);
   n.nodeValue=mode==='snow'?translateSnowText(base):mode==='paving'?translatePavingText(base):mode==='landscaping'?translateLandscapingText(base):mode==='pressure'?translatePressureText(base):base;
 });
 document.querySelectorAll('[data-tip],[title],[aria-label]').forEach(node=>{
  if(node.closest(protectedContent))return;
  let original=_aeriOriginalAttributes.get(node);if(!original){original={};for(const attr of ['data-tip','title','aria-label'])if(node.hasAttribute(attr))original[attr]=node.getAttribute(attr);_aeriOriginalAttributes.set(node,original)}
  for(const [attr,base] of Object.entries(original))node.setAttribute(attr,mode==='snow'?(attr==='data-tip'&&/pitch/i.test(base)?'Measure the snow-clearing service area or linear route, then save the measurement.':translateSnowText(base)):base);
 });
 if(mode==='roofing'&&roofRemeasureTarget){if(el('manualPitchLabel'))el('manualPitchLabel').childNodes[0].nodeValue='Roof pitch â€” defaults to 5/12; change if needed ';if(el('manualRoofSummary'))el('manualRoofSummary').textContent='Replace measurement â€” '+roofRemeasureTarget.label;if(el('manualRoofWarning'))el('manualRoofWarning').textContent='Editing '+roofRemeasureTarget.label+' only. Its saved measurement stays unchanged until the replacement is saved.';if(el('clearManualBtn'))el('clearManualBtn').textContent='CLEAR THIS ROOF DRAWING'}
 const intro=document.querySelector('.measure-intro span');if(intro)intro.textContent=mode==='roofing'?(manualRoofQa()?"Load property â†’ Trace roof â†’ Confirm pitch â†’ Review estimate. Trace different pitches as separate sections.":"Use AutoMeasure for pitched roofs, Area for roof footprints, or Linear for roof lengths. The selected tool sets this estimate's measurement."):'Use one tool or combine multiple measurements on the same property.';
 const copy=AERI_TOOL_COPY[mode]||AERI_TOOL_COPY.roofing;
 const areaToolButton=el('toolAreaBtn'),linearToolButton=el('toolLinearBtn');
 if(areaToolButton){areaToolButton.querySelector('b').textContent=manualRoofQa()?'TRACE ROOF':'+ ADD AREA';areaToolButton.querySelector('small').textContent=manualRoofQa()?'Roof sections â€¢ confirmed pitch':copy.area;}
 if(linearToolButton){linearToolButton.querySelector('b').textContent=mode==='snow'?'LINEAR':'+ LINEAR';linearToolButton.querySelector('small').textContent=copy.linear;}
 const linearDescription=document.querySelector('#linearTool .linear-head .small');if(linearDescription)linearDescription.textContent=copy.distance;
 const snow=mode==='snow';
 const pressure=mode==='pressure',paving=mode==='paving',landscaping=mode==='landscaping',commercial=mode==='commercial';
 const areaDescription=document.querySelector('#areaTool .area-head .small');if(areaDescription)areaDescription.textContent=commercial?'Measure parking lots, walkways, grounds or other commercial service areas in square feet.':landscaping?'Measure lawns, sod, garden beds, patios or other landscaping areas in square feet.':paving?'Measure paved surfaces, driveways and parking areas in square feet.':pressure?'Measure driveways, sidewalks, patios and other cleaning areas in square feet.':snow?'Measure driveways, sidewalks and other snow clearing areas in square feet.':'Measure a roof footprint in square feet. Area Measure does not adjust for pitch; use AutoMeasure and roof correction for pitched roof area.';
 const extra=el('extraServiceDescription');if(extra)extra.placeholder=commercial?'Example: Additional parking lot, walkway or grounds services':landscaping?'Example: Sod installation, mulch, planting, edging or additional garden work':paving?'Example: Crack filling, asphalt patching or additional sealcoating':pressure?'Example: Additional patio, sidewalk or driveway cleaning':snow?'Example: Additional sidewalk clearing, de-icing or snow hauling':'Example: Replace damaged shingles, seal vent, minor roof repair';
 document.body.classList.toggle('pressure-industry',pressure||paving||landscaping||commercial);
 document.body.classList.toggle('landscaping-industry',landscaping);
 if((landscaping||commercial)&&measurementViewMode==='auto'){measurementViewMode='area';pendingMeasurementMode='area';updatePropertyActionButton();}
 const coverageWrap=el('coverageWrap');if(coverageWrap)coverageWrap.style.display=(snow||pressure||paving||landscaping||commercial)?'none':'';
 const industryTag=el('industryBrandTag');if(industryTag)industryTag.textContent=snow?'SNOW REMOVAL MEASUREMENT & ESTIMATE SOFTWARE':pressure?'PRESSURE WASHING MEASUREMENT & ESTIMATE SOFTWARE':paving?'PAVING & SEALCOATING MEASUREMENT & ESTIMATE SOFTWARE':landscaping?'LANDSCAPING MEASUREMENT & ESTIMATE SOFTWARE':mode==='commercial'?'PROPERTY MEASUREMENT & ESTIMATE SOFTWARE':'ROOF MEASUREMENT & ESTIMATE SOFTWARE';
 if(el('marketingWarranty')){if(landscaping)el('marketingWarranty').placeholder='Optional: Add your landscaping workmanship guarantee or service terms.';else if(paving)el('marketingWarranty').placeholder='Example: Add your workmanship guarantee or service terms.';else if(snow){el('marketingWarranty').placeholder='Optional: Add your company service guarantee or satisfaction policy.';if(/^Example: We stand behind our snow removal service/i.test((el('marketingWarranty').value||'').trim()))el('marketingWarranty').value='';}else el('marketingWarranty').placeholder=mode==='roofing'?'Example: Backed by our 5-year workmanship warranty.':'Optional: Add your company service guarantee or satisfaction policy.';}
 document.querySelectorAll('body *').forEach(x=>{
   if(x.children.length||['SCRIPT','STYLE'].includes(x.tagName))return;
   const tx=(x.textContent||'').trim();
   if(!snow && tx==='Service â€” Main House')x.textContent='Roofing Service â€” Main House';
 });
 const businessSelect=el('businessType');
 if(businessSelect){
   Array.from(businessSelect.options||[]).forEach(o=>{
     if(o.value==='roofing')o.textContent='Roofing';
     if(o.value==='snow')o.textContent='Snow Removal';
     if(o.value==='pressure')o.textContent='Pressure Washing';if(o.value==='paving')o.textContent='Paving & Sealcoating';if(o.value==='landscaping')o.textContent='Landscaping';
   });
 }
 // Central Snow Removal display cleanup for dynamically rendered screens/previews.
 const snowExact=(selector,pattern,replacement)=>{
   document.querySelectorAll(selector).forEach(x=>{
     if(!x.dataset.aeriOriginalHtml)x.dataset.aeriOriginalHtml=x.innerHTML;
     if(snow && pattern.test(x.textContent||''))x.textContent=replacement;
     else if(!snow && x.dataset.aeriOriginalHtml)x.innerHTML=x.dataset.aeriOriginalHtml;
   });
 };
 if(snow){
   document.querySelectorAll('body *').forEach(x=>{
     if(['SCRIPT','STYLE'].includes(x.tagName)||x.children.length||x.closest(protectedContent))return;
     const tx=(x.textContent||'').trim();
     if(/^Main House$/i.test(tx))x.textContent='Primary Service Area';
     else if(/Main house and added areas can be edited separately/i.test(tx))x.textContent='Choose which service area outline to edit. Primary and additional service areas can be edited separately. Picture only â€” measurements and price stay unchanged.';
     else if(/^Service â€” Primary Service Area$/i.test(tx))x.textContent='Snow Removal Service â€” Primary Service Area';
   });
 }
 const areaMode=el('outlineMode');
 if(areaMode){
   const opts=Array.from(areaMode.options||[]);
   opts.forEach((o,i)=>{
     if(!o.dataset.aeriOriginalLabel)o.dataset.aeriOriginalLabel=o.textContent;
     if(snow){
       if(i===0)o.textContent='Measured Area Outline (Recommended)';
       else if(i===1)o.textContent='Show Measured Sections';
       else if(i===2)o.textContent='Pitch Labels Only';
       o.hidden=(i===2);
       o.disabled=(i===2);
     }else{
       o.textContent=o.dataset.aeriOriginalLabel;
       o.hidden=false;o.disabled=false;
     }
   });
   if(snow && areaMode.selectedIndex===2){areaMode.selectedIndex=0;areaMode.dispatchEvent(new Event('change'))}
 }
 // Hide only roof/product-specific display elements for Snow Removal.
 document.querySelectorAll('.pitch,.pitch-reminder').forEach(x=>{x.style.display=snow?'none':''});
 document.querySelectorAll('label,.small,.structure,.metric,.advanced-row,.map-legend div').forEach(x=>{
   const tx=(x.textContent||'').trim();
   if(snow && (/^Pitch labels only$/i.test(tx)||/^Gold\s*=\s*Pitch$/i.test(tx)||/Multiple pitches|Avg pitch|pitch used|pitch confirmed/i.test(tx))){
     if(!x.dataset.aeriDisplay)x.dataset.aeriDisplay=x.style.display||'';
     x.style.display='none';
   }
 });
 if(snow){
   // Snow Removal uses service-area / linear tools, never roof AutoMeasure.
   const autoBtn=el('toolAutoBtn'); if(autoBtn)autoBtn.style.display='none';
   const areaBtn=el('toolAreaBtn'); if(areaBtn){areaBtn.querySelector('b').textContent='+ ADD AREA';areaBtn.querySelector('small').textContent='Driveways â€¢ parking lots â€¢ service areas'}
   const linearBtn=el('toolLinearBtn'); if(linearBtn){linearBtn.querySelector('b').textContent='LINEAR';linearBtn.querySelector('small').textContent='Sidewalks â€¢ curbs â€¢ access runs'}
   if(!sessionToken && measurementViewMode==='auto'){pendingMeasurementMode='area';measurementViewMode='area';updatePropertyActionButton();updateMeasurementInterface()}
   // Hide visible blocks whose original labels are strictly roof/product specific.
   document.querySelectorAll('.metric,.structure,.calc>div,.section,.warning,.small,label').forEach(x=>{
     const txt=(_aeriOriginalText.get(x.firstChild)||x.textContent||'').trim();
     if(/Roof Pitch|Main Roof Pitch|Multiple Roof Pitches|Coverage per gallon|Estimated product required|pitch included/i.test(txt)){
       if(!x.dataset.aeriDisplay)x.dataset.aeriDisplay=x.style.display||'';
       if(/Coverage per gallon|Estimated product required/i.test(txt) && x.parentElement && x.parentElement.classList.contains('calc')){
         x.style.display='none';
         const next=x.nextElementSibling;if(next){if(!next.dataset.aeriDisplay)next.dataset.aeriDisplay=next.style.display||'';next.style.display='none'}
       } else x.style.display='none';
     }
   });
   const fb=el('solarFallbackText');if(fb)fb.textContent='Trace the customer service area on the aerial image, then save the area measurement.';
 }else{
   const autoBtn=el('toolAutoBtn');if(autoBtn)autoBtn.style.display='';
   document.querySelectorAll('[data-aeri-display]').forEach(x=>{x.style.display=x.dataset.aeriDisplay;delete x.dataset.aeriDisplay});
 }
 syncRoofWorkspace();if(manualRoofQa())syncManualRoofQa();
}

function pressureMarketingDefaults(){return {heading:'WHY CHOOSE US',warranty:'',cta:'Schedule Your Pressure Washing Service',message:'Contact us to schedule professional pressure washing for your property.',benefits:[{icon:'âœ“',title:'Professional Cleaning',text:'Pressure washing tailored to your exterior surfaces.'},{icon:'âœ“',title:'Improve Curb Appeal',text:'Help remove built-up dirt and grime from driveways, patios and walkways.'},{icon:'$',title:'Clear Upfront Pricing',text:'Your estimate shows the measured cleaning area and pricing before work begins.'},{icon:'â—†',title:'Property-Specific Service',text:'Cleaning areas and pricing are prepared for your individual property.'},{icon:'âœ“',title:'Reliable Service',text:'Professional pressure washing for your property.'}]}}
function pavingMarketingDefaults(){return {heading:'WHY CHOOSE US',warranty:'',cta:'Schedule Your Paving & Sealcoating Service',message:'Contact us to discuss paving, asphalt repair or sealcoating for your property.',benefits:[{icon:'âœ“',title:'Surface Preparation',text:'Every paving and sealcoating estimate is tailored to the condition of your surface.'},{icon:'âœ“',title:'Protect Asphalt Surfaces',text:'Sealcoating can help protect suitable asphalt surfaces from weathering and wear.'},{icon:'$',title:'Clear Upfront Pricing',text:'Your estimate clearly shows measured work areas and pricing.'},{icon:'â—†',title:'Property-Specific Service',text:'Driveways and parking areas are measured for your individual property.'},{icon:'âœ“',title:'Professional Service',text:'Paving and sealcoating work planned around your property needs.'}]}}
function snowMarketingDefaults(){return {heading:'WHY CHOOSE US',warranty:'',cta:'Schedule Your Snow Removal Service',message:'Contact us to schedule snow removal service for your property.',benefits:[{icon:'âœ“',title:'Reliable Service',text:'Dependable snow removal service tailored to your property.'},{icon:'âœ“',title:'Help Keep Properties Safe',text:'Help keep parking lots, driveways and walkways clear and accessible.'},{icon:'$',title:'Clear Upfront Pricing',text:'Your estimate clearly shows the service areas and pricing before work begins.'},{icon:'â—†',title:'Property-Specific Service',text:'Service areas and pricing are prepared for your individual property.'},{icon:'âœ“',title:'Detailed Written Estimate',text:'Review the included work, measured quantities and pricing.'}]}}
function landscapingMarketingDefaults(){return {heading:'WHY CHOOSE OUR LANDSCAPING SERVICE',warranty:'',cta:'READY TO IMPROVE YOUR OUTDOOR SPACE?',message:'Contact us to schedule your landscaping project.',benefits:[{icon:'âœ“',title:'Accurate Property Measurements',text:'Measured service areas for a clear estimate.'},{icon:'â˜…',title:'Tailored Landscaping',text:'Lawns, sod, garden beds, patios and walkways.'},{icon:'$',title:'Clear Upfront Pricing',text:'Square-foot and linear-foot pricing.'},{icon:'â—†',title:'Property-Specific Service',text:'Project scope tailored to your outdoor space.'},{icon:'âœ“',title:'Professional Service',text:'Careful lawn and landscape work.'},{icon:'â˜…',title:'Reliable & Dependable Service',text:'Professional service from estimate through completion.'}]}}
function applySnowMarketingDefaultsIfNeeded(force=false){if(!['snow','pressure','paving','landscaping'].includes(currentBusinessType())||(!force&&el('marketingEnabled')?.checked===false))return;const d=currentBusinessType()==='landscaping'?landscapingMarketingDefaults():(currentBusinessType()==='paving'?pavingMarketingDefaults():(currentBusinessType()==='pressure'?pressureMarketingDefaults():snowMarketingDefaults())),roofWords=/roof|shingle|transferable warranty|protect your investment|property-specific assessment/i;const fields=[el('marketingWarranty')?.value,el('marketingCtaHeading')?.value,el('marketingCtaText')?.value,...[1,2,3,4,5,6].flatMap(n=>[el('benefitTitle'+n)?.value,el('benefitText'+n)?.value])].filter(Boolean).join(' ');const empty=!fields.trim();const wrongIndustry=['pressure','paving'].includes(currentBusinessType())&&/snow removal|snow service|keep parking lots|walkways clear/i.test(fields)||currentBusinessType()==='paving'&&/pressure washing|professional cleaning|curb appeal/i.test(fields);if(!(force||empty||roofWords.test(fields)||wrongIndustry))return;if(el('marketingEnabled'))el('marketingEnabled').checked=true;if(el('marketingHeading'))el('marketingHeading').value=d.heading;if(el('marketingWarranty')){el('marketingWarranty').value=d.warranty;el('marketingWarranty').placeholder='Optional: Add your company service guarantee or satisfaction policy.';}if(el('marketingCtaHeading'))el('marketingCtaHeading').value=d.cta;if(el('marketingCtaText'))el('marketingCtaText').value=d.message;d.benefits.forEach((b,j)=>{const n=j+1;if(el('benefitIcon'+n))el('benefitIcon'+n).value=b.icon;if(el('benefitTitle'+n))el('benefitTitle'+n).value=b.title;if(el('benefitText'+n))el('benefitText'+n).value=b.text});toggleMarketingEditor()}
function loadCommercialMarketingPreset(){
 if(currentBusinessType()!=='commercial'){alert('Select Commercial Properties under Business Type first.');return;}
 const defaults=[
  ['âœ“','Clear Upfront Pricing','Review measured areas and pricing before work begins.'],
  ['â—†','Property-Specific Planning','Service areas and scope tailored to your property.'],
  ['âœ“','Professional Service','A clear plan for your commercial property project.'],
  ['â˜…','Flexible Scheduling','Coordinate work around your property operations.'],
  ['âœ“','Detailed Estimate','Review project scope, quantities and pricing in one estimate.'],
  ['â—','Clear Communication','Know what work is included before approving the project.']
 ];
 const existing=[1,2,3,4,5,6].some(n=>(el('benefitTitle'+n)?.value||'').trim()||(el('benefitText'+n)?.value||'').trim());
 if(existing&&!confirm('Replace the current six marketing benefits with the Commercial Properties preset?'))return;
 if(el('marketingEnabled'))el('marketingEnabled').checked=true;
 if(el('marketingHeading'))el('marketingHeading').value='WHY CHOOSE US';
 defaults.forEach((b,j)=>{const n=j+1;if(el('benefitIcon'+n))el('benefitIcon'+n).value=b[0];if(el('benefitTitle'+n))el('benefitTitle'+n).value=b[1];if(el('benefitText'+n))el('benefitText'+n).value=b[2]});
 if(el('marketingCtaHeading'))el('marketingCtaHeading').value='Ready to Get Started?';
 if(el('marketingCtaText'))el('marketingCtaText').value='Contact us to discuss your commercial property and request scheduling.';
 toggleMarketingEditor();
}
function fillMissingMarketingBenefits(){
 // Fill missing rows without changing a dealer's existing wording or branding.
 const commercial=currentBusinessType()==='commercial';
 const defaults=commercial?[
  ['âœ“','Clear Upfront Pricing','Review measured areas and pricing before work begins.'],
  ['â—†','Property-Specific Planning','Service areas and scope tailored to your property.'],
  ['âœ“','Professional Service','A clear plan for your commercial property project.'],
  ['â˜…','Flexible Scheduling','Coordinate work around your property operations.'],
  ['âœ“','Detailed Estimate','Review project scope, quantities and pricing in one estimate.'],
  ['â—','Clear Communication','Know what work is included before approving the project.']
 ]:[
  ['âœ“','Clear Upfront Pricing','Review the project scope and price before work begins.'],
  ['â—†','Property-Specific Assessment','We assess each property and tailor the estimate to the work required.'],
  ['âœ“','Professional Service','A clear service plan from assessment through completion.'],
  ['â˜…','Convenient Scheduling','Coordinate service at a time that works for your property.'],
  ['âœ“','Detailed Written Estimate','Review the included work, measured quantities and pricing.'],
  ['â—','Clear Communication','Know what work is included before approving the project.']
 ];
 for(let i=1;i<=6;i++){
  const title=el('benefitTitle'+i),body=el('benefitText'+i),icon=el('benefitIcon'+i);
  if(!title||!body)continue;
  if(!title.value.trim()){title.value=defaults[i-1][1];if(icon)icon.value=defaults[i-1][0]}
  if(!body.value.trim())body.value=defaults[i-1][2];
 }
}
function fillCommercialBenefits(){
 if(currentBusinessType()!=='commercial')return;
 const defaults=[
  {icon:'âœ“',title:'Clear Upfront Pricing',text:'Review measured areas and pricing before work begins.'},
  {icon:'â—†',title:'Property-Specific Planning',text:'Service areas and scope tailored to your property.'},
  {icon:'âœ“',title:'Professional Service',text:'A clear plan for your commercial property project.'},
  {icon:'â˜…',title:'Flexible Scheduling',text:'Coordinate work around your property operations.'},
  {icon:'âœ“',title:'Detailed Estimate',text:'Review project scope, quantities and pricing in one estimate.'},
  {icon:'â—',title:'Clear Communication',text:'Know what work is included before approving the project.'}
 ];
 if(el('marketingHeading')&&!el('marketingHeading').value.trim())el('marketingHeading').value='WHY CHOOSE US';
 for(let i=1;i<=6;i++){
  const title=el('benefitTitle'+i),body=el('benefitText'+i),icon=el('benefitIcon'+i);
  if(title&&body&&!title.value.trim()&&!body.value.trim()){
   title.value=defaults[i-1].title;body.value=defaults[i-1].text;
   if(icon)icon.value=defaults[i-1].icon;
  }
 }
 toggleMarketingEditor();
}
function fillLandscapingBenefits(){if(currentBusinessType()!=='landscaping')return;const d=landscapingMarketingDefaults();const titles=[1,2,3,4,5,6].map(n=>(el('benefitTitle'+n)?.value||'').trim());const starter=titles[0]==='Landscape Care'&&titles.slice(1).every(v=>!v);const empty=titles.every(v=>!v);if(starter||empty){d.benefits.forEach((b,j)=>{const n=j+1;for(const [prefix,value] of [['benefitIcon',b.icon],['benefitTitle',b.title],['benefitText',b.text]]){const e=el(prefix+n);if(e)e.value=value}});if(starter&&el('marketingHeading')?.value==='WHY CHOOSE US')el('marketingHeading').value=d.heading;}else{d.benefits.forEach((b,j)=>{const n=j+1,t=el('benefitTitle'+n),x=el('benefitText'+n);if(t&&!t.value.trim()&&x&&!x.value.trim()){t.value=b.title;x.value=b.text;if(el('benefitIcon'+n))el('benefitIcon'+n).value=b.icon}})}}
let marketingIndustry='',industryMarketingDrafts=new Map(),industryChosenByUser=false;
function captureIndustryMarketing(){return {marketingEnabled:!!el('marketingEnabled')?.checked,marketingHeading:el('marketingHeading')?.value||'',marketingWarranty:el('marketingWarranty')?.value||'',marketingCtaHeading:el('marketingCtaHeading')?.value||'',marketingCtaText:el('marketingCtaText')?.value||'',benefits:[1,2,3,4,5,6].map(n=>({icon:el('benefitIcon'+n)?.value||'âœ“',title:el('benefitTitle'+n)?.value||'',text:el('benefitText'+n)?.value||''}))}}
function switchIndustryMarketing(){
 const industry=currentBusinessType();
 if(marketingIndustry===industry)return;
 if(marketingIndustry)industryMarketingDrafts.set(marketingIndustry,captureIndustryMarketing());
 let draft=industryMarketingDrafts.get(industry);
 if(!draft){
  const d=industry==='snow'?snowMarketingDefaults():industry==='pressure'?pressureMarketingDefaults():industry==='paving'?pavingMarketingDefaults():industry==='landscaping'?landscapingMarketingDefaults():{
   heading:'WHY CHOOSE US',warranty:'',cta:industry==='roofing'?'Schedule Your Roofing Service':'Ready to Get Started?',message:industry==='roofing'?'Contact us to discuss roofing services for your property.':'Contact us to discuss your commercial property and request scheduling.',benefits:[{icon:'âœ“',title:industry==='roofing'?'Professional Roofing':'Commercial Property Services',text:industry==='roofing'?'Roofing services tailored to your property.':'Services tailored to your commercial property.'},{icon:'$',title:'Clear Upfront Pricing',text:'Review measured quantities and pricing before work begins.'},{icon:'â—†',title:'Property-Specific Planning',text:'Review the included work and service scope for your property.'}]
  };
  draft={marketingEnabled:true,marketingHeading:d.heading,marketingWarranty:d.warranty,marketingCtaHeading:d.cta,marketingCtaText:d.message,benefits:Array.from({length:6},(_,i)=>d.benefits[i]||{icon:'âœ“',title:'',text:''})};
 }
 applyOnboardingMarketing({...draft,businessType:industry});
 // Preserve an explicit off choice along with the industry's unsaved custom text.
 if(el('marketingEnabled'))el('marketingEnabled').checked=draft.marketingEnabled;
}
function businessTypeChanged(){industryChosenByUser=true;if(['pressure','paving','landscaping','commercial','snow'].includes(currentBusinessType())){measurementViewMode='area';pendingMeasurementMode='area';updatePropertyActionButton();}switchIndustryMarketing();applyBusinessTerminology();fillLandscapingBenefits();fillCommercialBenefits();toggleMarketingEditor();renderSummary()}
let _aeriTermTimer=null;
const _aeriTermObserver=new MutationObserver(()=>{if(currentBusinessType()!=='snow')return;clearTimeout(_aeriTermTimer);_aeriTermTimer=setTimeout(()=>{
 // Wording updates must not observe and continuously reschedule themselves.
 _aeriTermObserver.disconnect();try{applyBusinessTerminology()}finally{_aeriTermObserver.observe(document.body,{childList:true,subtree:true})}
},30)});
document.addEventListener('DOMContentLoaded',()=>{_aeriTermObserver.observe(document.body,{childList:true,subtree:true})});


let accountWarrantyBrand="";
function applyWarrantyAccount(a){accountWarrantyBrand=a.allowance?.brand||"";if(el("warrantyShieldSettings"))el("warrantyShieldSettings").style.display=accountWarrantyBrand?"block":"none";if(el("showWarrantyShield"))el("showWarrantyShield").checked=a.profile?.showWarrantyShield!==false}
function applyReportWarranty(snap={},historicalMode=false){const shield=el('rWarrantyShield'),shieldBrand=historicalMode?(snap.warrantyBrand||''):accountWarrantyBrand,showShield=historicalMode?snap.showWarrantyShield:!!el('showWarrantyShield')?.checked;
 if(shield){const visible=currentBusinessType()==='roofing'&&showShield&&['shingle_guard','shinglextra'].includes(shieldBrand);shield.style.display=visible?'block':'none';if(visible)shield.src='/static/dealer-assets/'+shieldBrand+'-warranty.png';else shield.removeAttribute('src')}}
function useApprovedDealerLogo(){if(!['shingle_guard','shinglextra'].includes(accountWarrantyBrand))return;const src='/static/dealer-assets/'+accountWarrantyBrand+'-logo.'+(accountWarrantyBrand==='shinglextra'?'jpg':'png');applyDealerLogo(src);status('Brand logo selected. Save your profile to keep this choice.','ok')}
let dealerProfileSaveInProgress=false;
function validDealerProfileEmail(value){
 if(typeof value!=='string')return false;const email=value.trim();if(!email||email.length>254)return false;
 const parts=email.split('@');if(parts.length!==2)return false;const [local,domain]=parts;
 if(!local||local.length>64||local.startsWith('.')||local.endsWith('.')||local.includes('..')||!/^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+$/.test(local))return false;
 const labels=domain.split('.');return labels.length>=2&&labels.every(label=>/^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$/.test(label))&&/^[A-Za-z]{2,63}$/.test(labels[labels.length-1]);
}
async function saveDealerDefaults(){
 if(dealerProfileSaveInProgress)return false;
 const d={logoData:dealerLogoSrc(),showWarrantyShield:!!el("showWarrantyShield")?.checked,name:el('dealerName').value,company:el('dealerCompany')?el('dealerCompany').value:'',email:el('dealerEmail')?el('dealerEmail').value:'',website:el('dealerWebsite')?el('dealerWebsite').value:'',address:el('dealerAddress')?el('dealerAddress').value:'',price:el('price').value,coverage:el('coverage').value,country:el('dealerCountry')?el('dealerCountry').value:'US',businessType:el('businessType')?el('businessType').value:'roofing',province:el('province').value,pricingMode:el('pricingMode').value,discountPct:el('discountPct').value,gst:el('gst').value,pst:el('pst').value,phone:el('dealerPhone').value,marketingEnabled:!!el('marketingEnabled')?.checked,marketingHeading:el('marketingHeading')?.value||'',marketingWarranty:el('marketingWarranty')?.value||'',marketingCtaHeading:el('marketingCtaHeading')?.value||'',marketingCtaText:el('marketingCtaText')?.value||'',benefits:[1,2,3,4,5,6].map(n=>({icon:el('benefitIcon'+n)?.value||'âœ“',title:el('benefitTitle'+n)?.value||'',text:el('benefitText'+n)?.value||''}))};
 d.email=d.email.trim();if(!validDealerProfileEmail(d.email)){el('savedMsg').textContent='Enter a valid dealer email address, such as name@company.com. Your saved profile is unchanged.';el('dealerEmail')?.focus?.();return false;}
 dealerProfileSaveInProgress=true;
 const sb=el('saveDealerProfileBtn'),buttonText=sb?.textContent||'SAVE DEALER PROFILE & BRANDING';
 if(sb){sb.disabled=true;sb.textContent='SAVINGâ€¦'}
 try{
  const response=await fetch('/api/account/profile',{method:'POST',headers:{'Content-Type':'application/json','X-AeriQuote-Account':el('aqAccountId')?.dataset?.accountId||''},body:JSON.stringify(d)});
  const result=await response.json().catch(()=>null);
  if(!response.ok||result?.ok!==true){const error=new Error(result?.error||'Profile save was not confirmed.');error.status=response.status;throw error}
  dealerLogoDirty=false;
  try{localStorage.setItem('sxDealerDefaults',JSON.stringify(d))}catch(e){}
  const savedPrice=parseFloat(d.price);if(Number.isFinite(savedPrice)&&savedPrice>=0&&el('jobPrice'))el('jobPrice').value=savedPrice.toFixed(2);const ds=document.querySelector('details.dealer-settings');if(ds)ds.open=true;const ms=el('marketingSettings');if(ms)ms.open=false;applyBusinessTerminology();renderSummary();el('savedMsg').innerHTML=`<div class="savedmsg"><b>âœ“ Dealer profile & branding saved.</b> Current quote updated to <b>${money(savedPrice)} / sq. ft.</b>. Your company information and marketing choices will appear on customer estimates.</div>`;
  return true;
 }catch(e){
  el('savedMsg').textContent=e.status===409?'Profile not saved. '+e.message:'Profile not saved. Your entries are still here. Check your connection or sign-in, then click SAVE DEALER PROFILE & BRANDING to retry.';
  return false;
 }finally{
  dealerProfileSaveInProgress=false;
  if(sb){sb.disabled=false;sb.textContent=buttonText}
 }
}
function applyOnboardingMarketing(d){if(!d)return;marketingIndustry=d.businessType||currentBusinessType();const warranty=(d.marketingWarranty||d.warrantyStatement||'').trim(),msg=(d.marketingCtaText||d.estimateMessage||'').trim(),cta=(d.marketingCtaHeading||d.ctaHeading||'').trim();const enabled=d.marketingEnabled===false?false:((d.marketingEnabled===true)||!!warranty||!!msg);if(el('marketingEnabled'))el('marketingEnabled').checked=enabled;if(el('marketingHeading'))el('marketingHeading').value=d.marketingHeading||'WHY CHOOSE US';if(el('marketingWarranty'))el('marketingWarranty').value=warranty;if(el('marketingCtaHeading'))el('marketingCtaHeading').value=cta||'Ready to Get Started?';if(el('marketingCtaText'))el('marketingCtaText').value=msg;(d.benefits||[]).slice(0,6).forEach((b,j)=>{const n=j+1;if(el('benefitIcon'+n))el('benefitIcon'+n).value=b.icon||'âœ“';if(el('benefitTitle'+n))el('benefitTitle'+n).value=b.title||'';if(el('benefitText'+n))el('benefitText'+n).value=b.text||''});}function clearNewJobCustomer(){['customerName','customerPhone','customerEmail','customerNotes'].forEach(id=>{const n=el(id);if(n){n.value='';n.setAttribute('readonly','readonly')}});updateProgressSteps();}
function prepareAccountBrandingCache(accountId){
 if(!accountId||dealerBrandingAccount===accountId)return;
 dealerBrandingAccount=accountId;dealerLogoData=null;dealerLogoDirty=false;
 try{if(localStorage.getItem('aqBrandingAccount')!==accountId){localStorage.removeItem('sxDealerDefaults');applyDealerLogo('',false);localStorage.setItem('aqBrandingAccount',accountId)}}catch(e){dealerLogoData=''}
}
function loadDealerDefaults(){prepareAccountBrandingCache(el('aqAccountId')?.dataset.accountId||'');const logoRevision=dealerLogoRevision;fetch('/api/account/profile').then(r=>r.ok?r.json():null).then(a=>{if(!a)return;applyWarrantyAccount(a);if(sessionToken||linearMode||areaMode)return;const d=a.profile||{};if(!Object.keys(d).length)return;try{localStorage.setItem('sxDealerDefaults',JSON.stringify(d))}catch(e){};if(!dealerLogoDirty&&logoRevision===dealerLogoRevision)applyDealerLogo(d.logoData||'',false);if(d.name!==undefined&&el('dealerName'))el('dealerName').value=d.name;if(d.company!==undefined&&el('dealerCompany'))el('dealerCompany').value=d.company;if(d.email!==undefined&&el('dealerEmail'))el('dealerEmail').value=d.email;if(d.phone!==undefined&&el('dealerPhone'))el('dealerPhone').value=d.phone;if(d.website!==undefined&&el('dealerWebsite'))el('dealerWebsite').value=d.website;if(d.address!==undefined&&el('dealerAddress'))el('dealerAddress').value=d.address;if(el('dealerCountry'))el('dealerCountry').value=(['CA','CANADA'].includes(String(d.country||'').toUpperCase())?'CA':'US');if(el('businessType')&&!industryChosenByUser)el('businessType').value=new URLSearchParams(window.location.search).get('industry')==='commercial'?'commercial':(d.businessType||a.industry||'roofing');if(['pressure','paving','landscaping','commercial'].includes(currentBusinessType())&&measurementViewMode==='auto'&&pendingMeasurementMode==='auto'){measurementViewMode='area';pendingMeasurementMode='area';updatePropertyActionButton();}applyBusinessTerminology();countryChanged(false);['price','coverage','province','pricingMode','discountPct','gst','pst'].forEach(id=>{if(d[id]!==undefined&&el(id))el(id).value=id==='price'?(d.pricingMethod==='manual'?'':currentBusinessType()==='pressure'&&!(parseFloat(d[id])>0)?'0.70':d[id]):d[id]});if(d.pricingMethod==='manual'&&el('commercialLinearRate'))el('commercialLinearRate').value='';if(d.price!==undefined&&el('jobPrice'))el('jobPrice').value=d.pricingMethod==='manual'?'':currentBusinessType()==='pressure'&&!(parseFloat(d.price)>0)?'0.70':d.price;if(!industryChosenByUser||currentBusinessType()===(d.businessType||a.industry||'roofing'))applyOnboardingMarketing(d);applySnowMarketingDefaultsIfNeeded(false);fillLandscapingBenefits();toggleMarketingEditor();pricingChanged();renderSummary()}).catch(()=>{});try{const d=JSON.parse(localStorage.getItem('sxDealerDefaults')||'null');if(d){if(d.name!==undefined&&el('dealerName'))el('dealerName').value=d.name;if(d.company!==undefined&&el('dealerCompany'))el('dealerCompany').value=d.company;if(d.email!==undefined&&el('dealerEmail'))el('dealerEmail').value=d.email;if(d.website!==undefined&&el('dealerWebsite'))el('dealerWebsite').value=d.website;if(d.address!==undefined&&el('dealerAddress'))el('dealerAddress').value=d.address;if(d.phone!==undefined&&el('dealerPhone'))el('dealerPhone').value=d.phone;if(el('dealerCountry'))el('dealerCountry').value=(['CA','CANADA'].includes(String(d.country||'').toUpperCase())?'CA':'US');if(el('businessType'))el('businessType').value=new URLSearchParams(window.location.search).get('industry')==='commercial'?'commercial':(d.businessType||'roofing');countryChanged(false);['price','coverage','province','pricingMode','discountPct','gst','pst'].forEach(id=>{if(d[id]!==undefined&&el(id))el(id).value=id==='price'?(d.pricingMethod==='manual'?'':currentBusinessType()==='pressure'&&!(parseFloat(d[id])>0)?'0.70':d[id]):d[id]});if(d.pricingMethod==='manual'&&el('commercialLinearRate'))el('commercialLinearRate').value='';if(d.price!==undefined&&el('jobPrice'))el('jobPrice').value=d.pricingMethod==='manual'?'':currentBusinessType()==='pressure'&&!(parseFloat(d.price)>0)?'0.70':d.price;applyOnboardingMarketing(d);applySnowMarketingDefaultsIfNeeded(false);(d.benefits||[]).slice(0,6).forEach((b,j)=>{const n=j+1;if(el('benefitIcon'+n))el('benefitIcon'+n).value=b.icon||'âœ“';if(el('benefitTitle'+n))el('benefitTitle'+n).value=b.title||'';if(el('benefitText'+n))el('benefitText'+n).value=b.text||''});applySnowMarketingDefaultsIfNeeded(false);fillLandscapingBenefits();fillCommercialBenefits()}else if(el('price')&&el('jobPrice'))el('jobPrice').value=el('price').value}catch(e){}const logo=dealerLogoSrc();if(el('dealerLogoPreview')){if(logo){el('dealerLogoPreview').src=logo;el('dealerLogoPreview').style.display='block'}else{el('dealerLogoPreview').removeAttribute('src');el('dealerLogoPreview').style.display='none'}}toggleMarketingEditor();pricingChanged();clearNewJobCustomer();setTimeout(clearNewJobCustomer,250);setTimeout(clearNewJobCustomer,1000)};applyBusinessTerminology()

function toggleMarketingEditor(){if(el('marketingEnabled')?.checked)fillMissingMarketingBenefits();if(el('marketingEditor'))el('marketingEditor').style.display=el('marketingEnabled')?.checked?'block':'none';if(el('commercialMarketingPresetButton'))el('commercialMarketingPresetButton').style.display=currentBusinessType()==='commercial'?'inline-block':'none'}
function applyDealerMarketing(){applySnowMarketingDefaultsIfNeeded(false);fillLandscapingBenefits();fillCommercialBenefits();fillMissingMarketingBenefits();const enabled=!!el('marketingEnabled')?.checked,panel=el('rMarketingPanel'),benefitsBox=el('rMarketingBenefits'),warranty=el('rMarketingWarranty');if(panel)panel.classList.toggle('marketingHidden',!enabled);if(!enabled){if(el('rCtaHeading'))el('rCtaHeading').textContent='YOUR ESTIMATE';if(el('rCtaText'))el('rCtaText').textContent='';return}if(el('rMarketingHeading'))el('rMarketingHeading').textContent=(el('marketingHeading')?.value||'WHY CHOOSE US').trim();if(benefitsBox){benefitsBox.innerHTML='';[1,2,3,4,5,6].forEach(n=>{const title=(el('benefitTitle'+n)?.value||'').trim(),txt=(el('benefitText'+n)?.value||'').trim();if(!title&&!txt)return;const row=document.createElement('div');row.className='benefit';const icon=document.createElement('span');icon.className='benefitIcon';icon.textContent=el('benefitIcon'+n)?.value||'âœ“';const body=document.createElement('div'),b=document.createElement('b');b.textContent=title||'Benefit';body.appendChild(b);if(txt){body.appendChild(document.createElement('br'));const sm=document.createElement('span');sm.className='small';sm.textContent=txt;body.appendChild(sm)}row.appendChild(icon);row.appendChild(body);benefitsBox.appendChild(row)})}let wt=(el('marketingWarranty')?.value||'').trim();if(/^Example: We stand behind our snow removal service/i.test(wt)||/add your company(?:'s)? (?:service guarantee|warranty)/i.test(wt))wt='';if(/^6\s*[-â€“â€”]?\s*year\s+transferable\s+warranty$/i.test(wt))wt='6-Year Transferable Warranty';if(warranty){warranty.textContent=wt;warranty.classList.toggle('marketingHidden',!wt)}if(el('rCtaHeading'))el('rCtaHeading').textContent=(el('marketingCtaHeading')?.value||'YOUR ESTIMATE').trim();if(el('rCtaText'))el('rCtaText').textContent=(el('marketingCtaText')?.value||'').trim()}
function detectProvince(addr){const a=(' '+String(addr||'').toUpperCase().replace(/[.,]/g,' ')+' ');const states={AL:'ALABAMA',AK:'ALASKA',AZ:'ARIZONA',AR:'ARKANSAS',CA:'CALIFORNIA',CO:'COLORADO',CT:'CONNECTICUT',DE:'DELAWARE',FL:'FLORIDA',GA:'GEORGIA',HI:'HAWAII',ID:'IDAHO',IL:'ILLINOIS',IN:'INDIANA',IA:'IOWA',KS:'KANSAS',KY:'KENTUCKY',LA:'LOUISIANA',ME:'MAINE',MD:'MARYLAND',MA:'MASSACHUSETTS',MI:'MICHIGAN',MN:'MINNESOTA',MS:'MISSISSIPPI',MO:'MISSOURI',MT:'MONTANA',NE:'NEBRASKA',NV:'NEVADA',NH:'NEW HAMPSHIRE',NJ:'NEW JERSEY',NM:'NEW MEXICO',NY:'NEW YORK',NC:'NORTH CAROLINA',ND:'NORTH DAKOTA',OH:'OHIO',OK:'OKLAHOMA',OR:'OREGON',PA:'PENNSYLVANIA',RI:'RHODE ISLAND',SC:'SOUTH CAROLINA',SD:'SOUTH DAKOTA',TN:'TENNESSEE',TX:'TEXAS',UT:'UTAH',VT:'VERMONT',VA:'VIRGINIA',WA:'WASHINGTON',WV:'WEST VIRGINIA',WI:'WISCONSIN',WY:'WYOMING',DC:'DISTRICT OF COLUMBIA'};for(const [code,name] of Object.entries(states)){if(new RegExp('\\b'+code+'\\b').test(a)||a.includes(' '+name+' '))return code}return null}
function updateUsage(){if(currentBusinessType()!=='roofing')el('usageLine').textContent=`This session â€” property lookups: ${usage.property} â€¢ area measurements: ${usage.area} â€¢ linear measurements: ${usage.linear} â€¢ estimates created: ${usage.reports}`;else el('usageLine').textContent=`This session â€” property lookups: ${usage.property} â€¢ extra structures: ${usage.structures} â€¢ reports: ${usage.reports} â€¢ saved assessments: ${usage.saved}`}

async function loadRaster(url,targetMap=map){const res=await fetch(url);if(!res.ok)throw new Error('Could not load Google aerial imagery.');const arr=await res.arrayBuffer();const gr=await parseGeoraster(arr);const layer=new GeoRasterLayer({georaster:gr,opacity:1,resolution:64,updateWhenIdle:true,updateWhenZooming:false,keepBuffer:8,resampleMethod:'nearest',pixelValuesToColorFn:vals=>{if(!vals||vals.length<3||vals.every(v=>v===null||v===undefined||Number.isNaN(v)))return null;const r=Number(vals[0]),g=Number(vals[1]),b=Number(vals[2]);if(!Number.isFinite(r)||!Number.isFinite(g)||!Number.isFinite(b))return null;return `rgb(${Math.max(0,Math.min(255,r))},${Math.max(0,Math.min(255,g))},${Math.max(0,Math.min(255,b))})`}});layer._sgAerial=true;layer._sgAerialType='solar-rgb';layer.addTo(targetMap);return{layer,bounds:layer.getBounds()}}
function removeStaleAerialLayers(keep=null){
 map.eachLayer(layer=>{if(layer&&layer._sgAerial&&layer!==keep){try{map.removeLayer(layer)}catch(e){}}});
 if(rgbLayer&&rgbLayer!==keep){try{map.removeLayer(rgbLayer)}catch(e){}rgbLayer=null}
 if(fallbackLayer&&fallbackLayer!==keep){try{map.removeLayer(fallbackLayer)}catch(e){}fallbackLayer=null}
}
let aerialDetailSequence=0,aerialDetailTimer=null,aerialDetailLayer=null,aerialDetailKey='';
async function refreshAerialDetail(){
 const token=sessionToken,base=fallbackLayer,z=Math.min(20,Math.floor(map.getZoom()));
 if(!token||base?._sgAerialType!=='wide-3x3-mosaic'||z<=18)return;
 const c=map.getCenter(),key=token+':'+z+':'+c.lat.toFixed(6)+':'+c.lng.toFixed(6);if(key===aerialDetailKey)return;
 const seq=++aerialDetailSequence,q=new URLSearchParams({lat:String(c.lat),lng:String(c.lng),zoom:String(z)});
 try{const r=await fetch('/wide-aerial/'+token+'?'+q);if(!r.ok)return;const blob=await r.blob();if(seq!==aerialDetailSequence||token!==sessionToken||base!==fallbackLayer)return;
 const url=URL.createObjectURL(blob),layer=L.imageOverlay(url,staticMapBounds(c.lat,c.lng,z,640,640),{opacity:1,interactive:false});layer.once('remove',()=>URL.revokeObjectURL(url));
 await new Promise((resolve,reject)=>{layer.once('load',resolve);layer.once('error',reject);layer.addTo(base)});
 if(seq!==aerialDetailSequence||token!==sessionToken||base!==fallbackLayer){base.removeLayer(layer);return}if(aerialDetailLayer&&base.hasLayer(aerialDetailLayer))base.removeLayer(aerialDetailLayer);aerialDetailLayer=layer;aerialDetailKey=key;
 }catch(e){console.warn('AQ:detail-aerial-failed')}
}
function scheduleAerialDetail(){clearTimeout(aerialDetailTimer);aerialDetailTimer=setTimeout(refreshAerialDetail,300)}
async function loadStandardWideAerial(token=sessionToken,targetMap=map,staging=false,center=null){
 if(!token)throw new Error('Load the property first.');
 // A 3x3 continuous satellite mosaic restores panning beyond the old 640px square.
 // The measurement geometry and pricing code are untouched.
 const c=center||((propertyMarker&&propertyMarker.getLatLng)?propertyMarker.getLatLng():map.getCenter());
 const z=18,scale=256*Math.pow(2,z),tileSize=640;
 const latToY=lat=>{const sin=Math.sin(lat*Math.PI/180);return (.5-Math.log((1+sin)/(1-sin))/(4*Math.PI))*scale};
 const x=(c.lng+180)/360*scale,y=latToY(c.lat);
 const toLatLng=(px,py)=>L.latLng(mercatorLat(py/scale),px/scale*360-180);
 const group=L.layerGroup().addTo(targetMap),bounds=L.latLngBounds([]);
 const jobs=[];
 for(let row=-1;row<=1;row++)for(let col=-1;col<=1;col++){
   const cx=x+col*tileSize,cy=y+row*tileSize;
   const centre=toLatLng(cx,cy);
   const b=L.latLngBounds(toLatLng(cx-tileSize/2,cy+tileSize/2),toLatLng(cx+tileSize/2,cy-tileSize/2));
   bounds.extend(b);
   const q=new URLSearchParams({lat:String(centre.lat),lng:String(centre.lng),zoom:String(z)});
   jobs.push((async()=>{
     const r=await fetch('/wide-aerial/'+token+'?'+q.toString());
     if(!r.ok)throw new Error('Wide satellite image request failed: '+r.status);
     const blob=await r.blob(),url=URL.createObjectURL(blob);
     const layer=L.imageOverlay(url,b,{opacity:1,interactive:false});
     layer.once('remove',()=>URL.revokeObjectURL(url));
     await new Promise((resolve,reject)=>{
       const timeout=setTimeout(()=>reject(new Error('Satellite tile timed out')),20000);
       layer.once('load',()=>{clearTimeout(timeout);resolve()});
       layer.once('error',()=>{clearTimeout(timeout);reject(new Error('Satellite tile failed to decode'))});
       layer.addTo(group);
     });
   })());
 }
 try{await Promise.all(jobs)}catch(e){await Promise.allSettled(jobs);group.eachLayer(l=>{if(l._url&&l._url.startsWith('blob:'))URL.revokeObjectURL(l._url)});targetMap.removeLayer(group);throw e}
 group._sgAerial=true;group._sgAerialType='wide-3x3-mosaic';
 if(staging)return{layer:group,bounds};
 removeStaleAerialLayers(group);
 fallbackLayer=group;fallbackBounds=bounds;rgbLayer=null;mainBounds=bounds;
 map.setMinZoom(14);map.setMaxBounds(null);map.options.maxBoundsViscosity=0;
 // Start at the same useful property scale, but retain imagery in all directions.
 map.off('moveend',scheduleAerialDetail);map.on('moveend',scheduleAerialDetail);aerialDetailSequence++;aerialDetailKey='';aerialDetailLayer=null;
 map.setView(c,z,{animate:false});
 return{layer:group,bounds};
}
async function loadSingleWideAerial(){
 if(!sessionToken)throw new Error('Load the property first.');
 const c=(propertyMarker&&propertyMarker.getLatLng)?propertyMarker.getLatLng():map.getCenter();
 const z=18,q=new URLSearchParams({lat:String(c.lat),lng:String(c.lng),zoom:String(z)});
 const r=await fetch('/wide-aerial/'+sessionToken+'?'+q.toString());
 if(!r.ok)throw new Error((await r.text())||'Could not load wider aerial view.');
 const blob=await r.blob(),obj=URL.createObjectURL(blob),b=staticMapBounds(c.lat,c.lng,z,640,640);
 const layer=L.imageOverlay(obj,b,{opacity:1,interactive:false});layer._sgAerial=true;layer._sgAerialType='standard-wide-static';
 layer.once('remove',()=>{try{URL.revokeObjectURL(obj)}catch(e){}});layer.addTo(map);
 removeStaleAerialLayers(layer);fallbackLayer=layer;fallbackBounds=b;rgbLayer=null;mainBounds=b;
 map.setMinZoom(14);map.setMaxBounds(null);map.options.maxBoundsViscosity=0;
 map.fitBounds(b.pad(0.01),{padding:[8,8],animate:false,maxZoom:z});
 return{layer,bounds:b};
}
async function useStableManualAerial(){
 // The dealer must see the same aerial before and after Manual Measure.
 // Manual Measure changes drawing mode only; it does not swap, zoom or recenter imagery.
 return !!(rgbLayer||fallbackLayer);
}
function showSolarFallback(show,text=''){fallbackMode=!!show;if(el('solarFallback'))el('solarFallback').style.display=show?'block':'none';if(text&&el('solarFallbackText'))el('solarFallbackText').textContent=text;if(!show)locateRoofMode=false}
function setPropertyMarker(lat,lng){if(propertyMarker){try{map.removeLayer(propertyMarker)}catch(e){}}propertyMarker=L.marker([lat,lng],{interactive:false,keyboard:false}).addTo(map).bindTooltip('Customer Property',{permanent:false,direction:'top',offset:[0,-18]});}
function setManualCorrectionLayout(on){manualOverrideMode=!!on;if(el('garageControls'))el('garageControls').style.display=on||manualRoofQa()?'none':'';if(el('roofCheckCard'))el('roofCheckCard').style.display=on?'none':'';if(el('advancedOptions'))el('advancedOptions').style.display=on?'none':'';}
async function startManualOverride(){if(!sessionToken){status('Load the property first.','error');return}cancelCurrentTrace();garageMode=false;roofFixMode=false;locateRoofMode=false;outlineEditMode=false;outlinePoints=[];clearOutlineTemp();clearOverlays();structures=[];manualPlanes=[];manualLayers.forEach(x=>{try{map.removeLayer(x)}catch(e){}});manualLayers=[];adjustedOutline=null;setManualCorrectionLayout(true);setManualUi(true);if(el('measureSource'))el('measureSource').value='manual';if(el('solarFallback'))el('solarFallback').style.display='block';if(el('solarFallbackText'))el('solarFallbackText').textContent='Manual measurement selected for this property. Trace the shingled roof around the customer property pin and confirm the pitch.';if(el('garageGuide'))el('garageGuide').innerHTML='<b>Manual measurement mode.</b> Google lines are hidden. Trace the customer roof shown at the property pin.';const details=el('manualRoofDetails');if(details)details.open=true;renderSummary();status('Preparing stable satellite image for manual measurementâ€¦','warn');await useStableManualAerial();setTimeout(()=>{if(!traceMode)toggleTrace()},60);status('Manual measurement mode is ready. Trace the roof corners, zoom as needed, then save.','warn')}
function mercatorLat(y){const n=Math.PI-2*Math.PI*y;return 180/Math.PI*Math.atan(.5*(Math.exp(n)-Math.exp(-n)))}
function staticMapBounds(lat,lng,zoom,w=640,h=640){const scale=256*Math.pow(2,zoom),x=(lng+180)/360*scale,s=Math.sin(lat*Math.PI/180),y=(.5-Math.log((1+s)/(1-s))/(4*Math.PI))*scale;const x1=x-w/2,x2=x+w/2,y1=y-h/2,y2=y+h/2;return L.latLngBounds([mercatorLat(y2/scale),(x1/scale)*360-180],[mercatorLat(y1/scale),(x2/scale)*360-180])}
async function loadFallbackAerial(token,targetMap=map){
 const r=await fetch('/fallback-meta/'+token),d=await r.json();
 if(!r.ok)throw new Error(d.error||'Could not load fallback aerial.');
 const b=staticMapBounds(d.latitude,d.longitude,d.zoom,d.width,d.height);
 let proxyError='';
 try{
   const ir=await fetch('/fallback-map/'+token+'?v='+Date.now());
   if(!ir.ok){proxyError=(await ir.text())||'Could not load Google satellite fallback.';throw new Error(proxyError)}
   const blob=await ir.blob(),obj=URL.createObjectURL(blob),layer=L.imageOverlay(obj,b,{opacity:1,interactive:false});layer._sgAerial=true;layer._sgAerialType='static-satellite';layer.addTo(targetMap);
   layer.once('remove',()=>{try{URL.revokeObjectURL(obj)}catch(e){}});
   return{layer,bounds:b,method:'proxy'}
 }catch(e){proxyError=e.message||String(e)}
 // If a Google key uses browser/referrer restrictions, the local Python proxy can be
 // rejected even though the same Static Maps request is allowed from this page.
 // Try the browser context once before declaring the aerial unavailable.
 const key="{{GOOGLE_MAPS_API_KEY}}".trim();
 if(key){
   const qs=new URLSearchParams({center:d.latitude+','+d.longitude,zoom:String(d.zoom),size:d.width+'x'+d.height,maptype:'satellite',format:'png',key:key});
   const direct='https://maps.googleapis.com/maps/api/staticmap?'+qs.toString();
   try{
     return await new Promise((resolve,reject)=>{
       let done=false;const layer=L.imageOverlay(direct,b,{opacity:1,interactive:false});layer._sgAerial=true;layer._sgAerialType='static-satellite';
       const timer=setTimeout(()=>{if(done)return;done=true;try{targetMap.removeLayer(layer)}catch(x){}reject(new Error('browser fallback timed out'));},12000);
       layer.once('load',()=>{if(done)return;done=true;clearTimeout(timer);resolve({layer,bounds:b,method:'browser'})});
       layer.once('error',()=>{if(done)return;done=true;clearTimeout(timer);try{targetMap.removeLayer(layer)}catch(x){}reject(new Error('browser fallback was rejected'))});
       layer.addTo(targetMap);
     })
   }catch(e){throw new Error(proxyError+' | '+(e.message||String(e)))}
 }
 throw new Error(proxyError||'Could not load Google satellite fallback.')
}
function startLocateRoof(){if(!sessionToken||!fallbackMode){status('Load the property first.','error');return}locateRoofMode=true;garageMode=false;roofFixMode=false;status('Click once near the centre of the house roof. Weâ€™ll retry Google at that exact location.','warn');if(el('solarFallbackText'))el('solarFallbackText').textContent='Click once near the centre of the HOUSE roof on the aerial.'}
function setManualUi(pure=false){const manualRow=el('traceBtn')?el('traceBtn').closest('.manualrow'):null;if(manualRow)manualRow.classList.toggle('main-house-trace-row',!!pure);if(el('tracePitchControl'))el('tracePitchControl').classList.toggle('main-house-pitch-control',!!pure);if(el('manualRoofSummary'))el('manualRoofSummary').textContent=pure?'Manual Measurement â€” Trace Customer Roof':'Add / Remeasure Garage or Other Roof';if(el('manualRoofWarning'))el('manualRoofWarning').innerHTML=pure?'<b>Manual measurement for this property.</b> Trace the shingled MAIN HOUSE around the customer property pin, then confirm the pitch. 5/12 is only the starting default.':(structures.length?"<b>Google's confirmed MAIN HOUSE stays in the quote.</b> Use this to add or remeasure a garage, shed, addition, or other shingled roof.":'<b>Your manually measured MAIN HOUSE stays in the quote.</b> Use this to add the garage, shed, shop, or another shingled building.');if(el('manualRoofHelp'))el('manualRoofHelp').textContent=pure?'Click each outside corner of the MAIN HOUSE, confirm the pitch, then press FINISH MEASUREMENT.':'Click around only the garage or other roof you want to add, confirm its pitch, then press SAVE & ADD ROOF.';if(el('manualPitchLabel'))el('manualPitchLabel').childNodes[0].nodeValue=pure?'Pitch of Main Roof ':'Pitch of Added Roof ';if(el('traceBtn')&&!traceMode)el('traceBtn').textContent=pure?'START MANUAL MEASUREMENT':'ADD MISSING ROOF';if(el('finishTrace'))el('finishTrace').textContent=pure?'FINISH MEASUREMENT':'SAVE & ADD ROOF';if(el('traceBanner'))el('traceBanner').textContent=pure?'MANUAL MEASURE ON â€” click roof corners, then FINISH MEASUREMENT':'MANUAL MEASURE ON â€” click roof corners, then SAVE & ADD ROOF';if(el('clearManualBtn'))el('clearManualBtn').textContent=pure?'CLEAR MAIN HOUSE OUTLINE':'CLEAR ADDED ROOF DRAWING';}
function startManualFallback(){if(!sessionToken||!fallbackMode){status('Load the property first.','error');return}locateRoofMode=false;setManualUi(true);if(el('solarFallbackText'))el('solarFallbackText').textContent='Manual mode: trace the shingled roof and confirm the pitch. Google automatic measurement is unavailable for this property.';status('Manual measurement ready â€” open the manual roof section, trace the roof, and confirm pitch.','warn');const details=el('manualRoofDetails');if(details)details.open=true;}
async function retryRoofAt(ll){if(!sessionToken)return;locateRoofMode=false;if(clickMarker){try{map.removeLayer(clickMarker)}catch(e){}}clickMarker=L.marker(ll).addTo(map).bindPopup('Checking this roof with Googleâ€¦').openPopup();try{showLoad(true);status('Checking the selected roof with Googleâ€¦');const r=await fetch('/locate-building',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:sessionToken,latitude:ll.lat,longitude:ll.lng})}),d=await r.json();if(!r.ok){showSolarFallback(true,'Google still cannot automatically measure this roof. You can click a slightly different spot and retry, or choose MEASURE MANUALLY.');status(d.user_error||'Google automatic measurement is unavailable for this roof.','warn');return}structures=[{...d.main,label:'Main House'}];setManualCorrectionLayout(false);setManualUi(false);if(el('measureSource'))el('measureSource').value='google';if(fallbackLayer){try{map.removeLayer(fallbackLayer)}catch(e){}fallbackLayer=null}if(rgbLayer){try{map.removeLayer(rgbLayer)}catch(e){}rgbLayer=null}let rgb=await loadRaster('/rgb/'+sessionToken);rgbLayer=rgb.layer;mainBounds=rgb.bounds;frameAerial(map,rgb.bounds,0);roofMask=await loadRoofMask('/mask/'+sessionToken);structures[0].outline=outlineFromMask(roofMask,d.main.latitude,d.main.longitude);reviewAutomaticRoof(structures[0]);await loadStandardWideAerial();redrawRoofData();showSolarFallback(false);renderSummary();if(el('garageGuide'))el('garageGuide').innerHTML=roofQuoteNeedsReview()?'<b>Main roof requires review.</b> Use FIX ROOF in the Property Summary.': '<b>Main house measured.</b> If there is another roof to include, click <b>+ ADD GARAGE / OTHER ROOF</b>, then click once on that roof.';if(el('measureClicked'))el('measureClicked').disabled=false;if(el('measureClickedTop'))el('measureClickedTop').disabled=false;status((structures[0]?.needs_remeasure||structures[0]?.automatic_review_warning)?'Main roof coverage needs review. Use FIX ROOF in the Property Summary.':'Main house measured from the roof you selected.',(structures[0]?.needs_remeasure||structures[0]?.automatic_review_warning)?'warn':'ok')}catch(e){showSolarFallback(true,'Google still cannot automatically measure this roof. Try a slightly different point or choose MEASURE MANUALLY.');status('Google automatic measurement is unavailable for this roof.','warn')}finally{showLoad(false);if(clickMarker){try{map.removeLayer(clickMarker)}catch(e){}clickMarker=null}}}

function frameAerial(targetMap,bounds,extraZoom=0){
 // Display framing only: never lock dealer navigation to the Solar raster bounds.
 // Earlier builds used setMinZoom/setMaxBounds here; that made some properties impossible to zoom back out.
 targetMap.setMinZoom(15);
 targetMap.setMaxBounds(null);
 targetMap.options.maxBoundsViscosity=0;
 targetMap.fitBounds(bounds.pad(0.02),{padding:[10,10],animate:false,maxZoom:20.5});
 if(extraZoom){const z=Math.min(20,targetMap.getZoom()+extraZoom);targetMap.setView(bounds.getCenter(),z,{animate:false});}
}
function quoteRoofBounds(){
 const pts=[];
 structures.forEach(st=>{(st.segments||[]).forEach(seg=>{const b=seg.bounding_box||{},sw=b.sw,ne=b.ne;if(sw&&ne){pts.push([sw.latitude,sw.longitude],[ne.latitude,ne.longitude],[sw.latitude,ne.longitude],[ne.latitude,sw.longitude])}});(st.outline||[]).forEach(p=>pts.push(p));});
 manualPlanes.forEach(p=>(p.points||[]).forEach(x=>pts.push([x.lat!==undefined?x.lat:x[0],x.lng!==undefined?x.lng:x[1]])));
 return pts.length>=2?L.latLngBounds(pts):null;
}
function fitEntireQuote(targetMap){const b=quoteRoofBounds();if(b&&b.isValid())targetMap.fitBounds(b.pad(0.16),{padding:[28,28],animate:false,maxZoom:20});}
function clearOverlays(){overlays.forEach(x=>{try{map.removeLayer(x)}catch(e){}});overlays=[]}
function rdp(points,eps){if(points.length<3)return points;const d2=(p,a,b)=>{const x=p[0],y=p[1],x1=a[0],y1=a[1],x2=b[0],y2=b[1],dx=x2-x1,dy=y2-y1;if(!dx&&!dy)return(x-x1)**2+(y-y1)**2;let t=((x-x1)*dx+(y-y1)*dy)/(dx*dx+dy*dy);t=Math.max(0,Math.min(1,t));const qx=x1+t*dx,qy=y1+t*dy;return(x-qx)**2+(y-qy)**2};let best=0,idx=-1;for(let i=1;i<points.length-1;i++){const d=d2(points[i],points[0],points[points.length-1]);if(d>best){best=d;idx=i}}if(best>eps*eps){const a=rdp(points.slice(0,idx+1),eps),b=rdp(points.slice(idx),eps);return a.slice(0,-1).concat(b)}return[points[0],points[points.length-1]]}
// Simplify a CLOSED raster contour without turning pixel stair-steps into a squiggly roof line.
// The previous code ran RDP on a ring whose first and last points were identical; that makes
// simplification unstable. Split the ring across an approximate diameter, simplify each open arc,
// then remove tiny/near-collinear leftovers. Roof corners remain, one-pixel zig-zags do not.
function simplifyClosedContour(loop,eps=3.2){
 if(!Array.isArray(loop)||loop.length<4)return loop||[];
 let pts=loop.slice();const same=(a,b)=>a&&b&&a[0]===b[0]&&a[1]===b[1];if(same(pts[0],pts[pts.length-1]))pts.pop();
 if(pts.length<4)return pts;
 const dist2=(a,b)=>(a[0]-b[0])**2+(a[1]-b[1])**2;
 let a=0;for(let i=1;i<pts.length;i++)if(dist2(pts[i],pts[a])>dist2(pts[0],pts[a]))a=i;
 let b=a;for(let i=0;i<pts.length;i++)if(dist2(pts[i],pts[a])>dist2(pts[b],pts[a]))b=i;
 if(a>b){const t=a;a=b;b=t}
 const arc1=pts.slice(a,b+1),arc2=pts.slice(b).concat(pts.slice(0,a+1));
 let out=rdp(arc1,eps).slice(0,-1).concat(rdp(arc2,eps).slice(0,-1));
 // Remove tiny notches and nearly straight intermediate points.
 let changed=true,guard=0;while(changed&&out.length>4&&guard++<8){changed=false;const next=[];for(let i=0;i<out.length;i++){
   const prev=out[(i-1+out.length)%out.length],cur=out[i],nxt=out[(i+1)%out.length];
   const v1=[cur[0]-prev[0],cur[1]-prev[1]],v2=[nxt[0]-cur[0],nxt[1]-cur[1]];
   const l1=Math.hypot(v1[0],v1[1]),l2=Math.hypot(v2[0],v2[1]);
   const cross=Math.abs(v1[0]*v2[1]-v1[1]*v2[0]),dot=v1[0]*v2[0]+v1[1]*v2[1];
   const nearStraight=l1>0&&l2>0&&cross/(l1*l2)<0.10&&dot>0;
   const tiny=(l1<1.8||l2<1.8)&&cross<2.0;
   if(nearStraight||tiny){changed=true;continue}next.push(cur)
 }if(next.length>=4)out=next;else break}
 return out;
}
async function loadRoofMask(url,strict=false){
 let stage='DOWNLOAD';
 try{
  const res=await fetch(url,{signal:AbortSignal.timeout(60000)});
  if(!res.ok){const error=new Error('Roof mask download failed');error.roofCode='AQ-MASK-HTTP-'+res.status;try{const body=await res.json();if(/^AQ-MASK-[A-Z0-9-]+$/.test(body.code||''))error.roofCode=body.code}catch(e){}throw error}
  stage='PARSE';const gr=await parseGeoraster(await res.arrayBuffer());let values=gr.values;
  if(!values&&gr.getValues)values=await gr.getValues({top:0,left:0,bottom:0,right:0,width:gr.width,height:gr.height});
  stage='PIXELS';if(!values||!values[0])throw new Error('Roof mask has no pixels');
  stage='PROJECTION';const helper=new GeoRasterLayer({georaster:gr,resolution:16});
  const toRaster=helper.getProjector(4326,gr.projection).forward,toWgs=helper.getProjector(gr.projection,4326).forward;
  if(typeof toRaster!=='function'||typeof toWgs!=='function')throw new Error('Roof projection unavailable');
  return{gr,band:values[0],toRaster,toWgs};
 }catch(e){if(strict){const error=new Error('Roof outline could not load');error.roofCode=e.roofCode||('AQ-MASK-'+(e.name==='TimeoutError'||e.name==='AbortError'?'TIMEOUT':stage));throw error}console.warn('Roof mask unavailable');return null}
}

function maskValue(mask,r,c){if(r<0||c<0||r>=mask.gr.height||c>=mask.gr.width)return 0;const row=mask.band[r];return row&&Number(row[c])>0?1:0}
function nearestMaskPixel(mask,lat,lng,accept=()=>true){
 const hasPixel=(r,c)=>maskValue(mask,r,c)&&accept(r,c);
 let xy;try{xy=mask.toRaster([lng,lat])}catch(e){return null}const gr=mask.gr,c0=Math.floor((xy[0]-gr.xmin)/Math.abs(gr.pixelWidth)),r0=Math.floor((gr.ymax-xy[1])/Math.abs(gr.pixelHeight));if(hasPixel(r0,c0))return[r0,c0];
 const maxR=Math.min(60,Math.max(12,Math.round(12/Math.max(.1,Math.abs(gr.pixelWidth||.25)))));for(let d=1;d<=maxR;d++){for(let dc=-d;dc<=d;dc++){for(const rr of [r0-d,r0+d])if(hasPixel(rr,c0+dc))return[rr,c0+dc]}for(let dr=-d+1;dr<=d-1;dr++){for(const cc of [c0-d,c0+d])if(hasPixel(r0+dr,cc))return[r0+dr,cc]}}return null
}
function outlineFromMask(mask,lat,lng,buildingBox=null){
 if(!mask)return null;
 // The raster identifies rooftop pixels across the whole neighbourhood, not a building ID.
 // Restrict component tracing to the selected Building Insights bounds. Retain real
 // mask edges inside those bounds rather than substituting a rectangular outline.
 const box=buildingBox?.sw&&buildingBox?.ne?buildingBox:null,gr0=mask.gr;
 const accept=(r,c)=>{if(!box)return true;const ll=mask.toWgs([gr0.xmin+(c+.5)*Math.abs(gr0.pixelWidth),gr0.ymax-(r+.5)*Math.abs(gr0.pixelHeight)]);return ll[1]>=box.sw.latitude&&ll[1]<=box.ne.latitude&&ll[0]>=box.sw.longitude&&ll[0]<=box.ne.longitude};
 const seed=nearestMaskPixel(mask,lat,lng,accept);if(!seed)return null;const H=mask.gr.height,W=mask.gr.width,seen=new Uint8Array(H*W),q=[seed],cells=[],key=(r,c)=>r*W+c;seen[key(seed[0],seed[1])]=1;
 for(let qi=0;qi<q.length;qi++){const [r,c]=q[qi];cells.push([r,c]);for(const [dr,dc] of [[-1,0],[1,0],[0,-1],[0,1]]){const nr=r+dr,nc=c+dc;if(nr<0||nc<0||nr>=H||nc>=W)continue;const k=key(nr,nc);if(!seen[k]&&maskValue(mask,nr,nc)&&accept(nr,nc)){seen[k]=1;q.push([nr,nc])}}}
 if(cells.length<8)return null;const inside=(r,c)=>r>=0&&c>=0&&r<H&&c<W&&seen[key(r,c)]===1,edges=[],vkey=(r,c)=>r+','+c;
 for(const [r,c] of cells){if(!inside(r-1,c))edges.push([[r,c],[r,c+1]]);if(!inside(r,c+1))edges.push([[r,c+1],[r+1,c+1]]);if(!inside(r+1,c))edges.push([[r+1,c+1],[r+1,c]]);if(!inside(r,c-1))edges.push([[r+1,c],[r,c]])}
 const byStart=new Map();edges.forEach((e,i)=>{const k=vkey(e[0][0],e[0][1]);if(!byStart.has(k))byStart.set(k,[]);byStart.get(k).push(i)});const used=new Uint8Array(edges.length),loops=[];
 for(let i=0;i<edges.length;i++){if(used[i])continue;let loop=[],cur=i,startKey=vkey(edges[i][0][0],edges[i][0][1]),guard=0;while(cur!==undefined&&!used[cur]&&guard++<edges.length+5){used[cur]=1;const e=edges[cur];loop.push(e[0]);const nk=vkey(e[1][0],e[1][1]);if(nk===startKey){loop.push(e[1]);break}const nexts=(byStart.get(nk)||[]).filter(j=>!used[j]);cur=nexts.length?nexts[0]:undefined}if(loop.length>=4)loops.push(loop)}
 if(!loops.length)return null;let loop=loops.sort((a,b)=>b.length-a.length)[0];loop=simplifyClosedContour(loop,3.2);if(loop.length<3)return null;const gr=mask.gr,pts=[];for(const [r,c] of loop){const x=gr.xmin+c*Math.abs(gr.pixelWidth),y=gr.ymax-r*Math.abs(gr.pixelHeight);let ll;try{ll=mask.toWgs([x,y])}catch(e){return null}pts.push([ll[1],ll[0]])}return pts
}
function outlineMatchesBuilding(points,roof){
 const box=roof.bounding_box;if(!box?.sw||!box?.ne)return true;
 // A mask component extending onto a neighbouring building is unsafe to save.
 const dy=2/111320,dx=dy/Math.max(.1,Math.cos(Number(roof.latitude)*Math.PI/180));
 return points.every(p=>p[0]>=box.sw.latitude-dy&&p[0]<=box.ne.latitude+dy&&p[1]>=box.sw.longitude-dx&&p[1]<=box.ne.longitude+dx);
}
function automaticRoofReviewDetails(roof,outline){
 const issues=[],ground=Number(roof.roof_ground_sqft||0),area=Number(roof.automatic_roof_sqft||roof.total_roof_sqft||0),validOutline=Array.isArray(outline)&&outline.length>=3&&outline.every(p=>Array.isArray(p)&&p.length===2&&Number.isFinite(p[0])&&Number.isFinite(p[1])&&Math.abs(p[0])<=90&&Math.abs(p[1])<=180),footprint=validOutline?localPolygonAreaM2(outline.map(p=>L.latLng(p)))*10.76391041671:0;
 if(!validOutline||footprint<=0)issues.push('The complete automatic roof outline is unavailable. Remeasure this roof.');
 if(!Number.isFinite(area)||area<=0||!Number.isFinite(ground)||ground<=0)issues.push('Automatic roof area or footprint data is incomplete.');
 const buildingGround=Number(roof.building_ground_sqft||0);if(!Number.isFinite(buildingGround)||buildingGround<=0)issues.push('The complete building footprint is unavailable. Remeasure this roof.');else if(ground/buildingGround<.95)issues.push('Automatic roof data is missing building sections.');
 if(validOutline&&!outlineMatchesBuilding(outline,roof))issues.push('The extracted outline extends beyond Googleâ€™s matched building boundary.');
 if(Number.isFinite(roof.roof_coverage_ratio)&&roof.roof_coverage_ratio<.95)issues.push('Googleâ€™s roof data covers '+(roof.roof_coverage_ratio*100).toFixed(1)+'% of its reported building footprint.');
 if(ground>0&&(footprint/ground<.75||footprint/ground>1.25))issues.push('The extracted outline footprint differs from Googleâ€™s reported roof footprint by more than 25%.');
 if(ground>0&&area<ground*.98)issues.push('Automatic roof surface area is smaller than its ground footprint.');
 const segments=roof.segments;if(!Array.isArray(segments)||!segments.length||segments.some(seg=>!Number.isFinite(seg.pitch_degrees)||seg.pitch_degrees<0||seg.pitch_degrees>=80||!Number.isFinite(seg.area_sqft)||seg.area_sqft<=0))issues.push('Automatic roof sections or pitches are incomplete.');
 if(Array.isArray(segments)&&segments.length&&segments.every(seg=>Number.isFinite(seg.pitch_degrees)&&Number.isFinite(seg.area_sqft))){const segmentArea=segments.reduce((n,seg)=>n+seg.area_sqft,0),segmentGround=segments.reduce((n,seg)=>n+seg.area_sqft*Math.cos(seg.pitch_degrees*Math.PI/180),0);if(Math.abs(segmentArea-area)>Math.max(1,area*.01)||ground>0&&(segmentGround/ground<.75||segmentGround/ground>1.25))issues.push('Automatic roof sections do not match the complete roof area and pitch.')}
 return {issues,outline_ground_sqft:footprint,google_roof_ground_sqft:ground,google_roof_sqft:area};
}
function automaticRoofNeedsReview(roof,outline){return automaticRoofReviewDetails(roof,outline).issues.length>0}
function automaticRoofReviewHtml(roof){
 const review=roof.automatic_review;if(!review?.issues?.length)return '';
 return '<details class="small" style="margin-top:7px"><summary>Why this roof needs review</summary><div style="padding:7px 0">'+review.issues.map(t=>'<div>'+escapeHistory(t)+'</div>').join('')+'<div>Google returned roof area: '+fmt(review.google_roof_sqft)+' ftÂ².</div><div>Google roof footprint: '+fmt(review.google_roof_ground_sqft)+' ftÂ². Extracted outline footprint: '+fmt(review.outline_ground_sqft)+' ftÂ².</div></div></details>';
}
function reviewAutomaticRoof(roof,requireRemeasure=false){
 {
  const review=automaticRoofReviewDetails(roof,roof.outline);
  if(review.issues.length){
   roof.automatic_review=review;
   roof.detected_outline=Array.isArray(roof.outline)?roof.outline.map(p=>[p[0],p[1]]):null;
   if(requireRemeasure||!Array.isArray(roof.outline)||roof.outline.length<3){roof.automatic_roof_sqft=roof.automatic_roof_sqft??roof.total_roof_sqft;roof.total_roof_sqft=0;roof.needs_remeasure=true;roof.outline=null}
   else roof.automatic_review_warning=true;
  }
 }
 return roof;
}
function drawEdgeMeasurements(points,color,targetMap=map,targetList=overlays,showCorners=true){
 if(!Array.isArray(points)||points.length<2)return;
 const pts=points.map(p=>L.latLng(p.lat!==undefined?p.lat:p[0],p.lng!==undefined?p.lng:p[1]));
 let edges=[];for(let i=0;i<pts.length;i++){const a=pts[i],b=pts[(i+1)%pts.length],feet=targetMap.distance(a,b)*3.28084;if(feet>=4)edges.push({a,b,feet,i})}
 const chosen=[...edges].sort((a,b)=>b.feet-a.feet).slice(0,14);
 // Smart label placement: prioritize longer edges, move labels farther outside the roof,
 // and suppress labels that would land on top of another edge label on complex roofs.
 let center=null;try{const cps=pts.map(p=>targetMap.latLngToContainerPoint(p));center=cps.reduce((a,p)=>L.point(a.x+p.x,a.y+p.y),L.point(0,0));center=L.point(center.x/cps.length,center.y/cps.length)}catch(e){}
 const placed=[];
 chosen.forEach(e=>{let mid=L.latLng((e.a.lat+e.b.lat)/2,(e.a.lng+e.b.lng)/2),labelPoint=null;try{const mp=targetMap.latLngToContainerPoint(mid);labelPoint=mp;}catch(err){}if(labelPoint)placed.push(labelPoint);const lab=L.marker(mid,{interactive:false,icon:L.divIcon({className:'',html:`<div class="edge-label">${e.feet.toFixed(1)} ft</div>`,iconAnchor:[22,8]})}).addTo(targetMap);targetList.push(lab)});
 if(showCorners&&pts.length<=24)pts.forEach(pt=>{const dot=L.circleMarker(pt,{radius:4,color,weight:2,fillColor:'#fff',fillOpacity:1,interactive:false}).addTo(targetMap);targetList.push(dot)});
}
function drawSegments(s,kind,targetMap=map,targetList=overlays,skipOutline=false){if(targetMap===map&&traceMode&&roofRemeasureTarget===s)return;const roofList=targetMap===map?structures:(quoteSnapshot?.structures||structures),compact=roofList.length>3,index=roofList.indexOf(s);if(s.needs_remeasure){const n=document.createElement('div');n.className='manual-label';n.textContent=s.label+' â€” needs remeasurement';targetList.push(L.marker([s.latitude,s.longitude],{interactive:false,icon:L.divIcon({className:'',html:n.outerHTML,iconAnchor:[70,10]})}).addTo(targetMap));return}const color=s.manually_measured?'#d97706':kind==='house'?'#2d6cdf':'#18a7a0',segs=(s.segments||[]),mode=(el('outlineMode')?el('outlineMode').value:'smart'),showBoxes=(mode==='all');if(s.manually_measured&&!compact){targetList.push(L.marker([s.latitude,s.longitude],{interactive:false,icon:L.divIcon({className:'',html:`<div class="manual-label">${Number(segs[0]?.pitch_degrees||0).toFixed(1)}Â° Â· ${fmt(s.total_roof_sqft)} ftÂ²</div>`,iconAnchor:[65,10]})}).addTo(targetMap))}segs.forEach((seg)=>{const b=seg.bounding_box;if(!b||!b.sw||!b.ne)return;if(showBoxes){const rect=L.rectangle([[b.sw.latitude,b.sw.longitude],[b.ne.latitude,b.ne.longitude]],{color,weight:2,fillColor:color,fillOpacity:.08}).addTo(targetMap);targetList.push(rect)}if(compact)return;const c=seg.center||{latitude:(b.sw.latitude+b.ne.latitude)/2,longitude:(b.sw.longitude+b.ne.longitude)/2};const lab=L.marker([c.latitude,c.longitude],{interactive:false,icon:L.divIcon({className:'',html:`<div class="seg-label">${seg.pitch_degrees.toFixed(1)}Â°</div>`,iconAnchor:[24,10]})}).addTo(targetMap);targetList.push(lab)});if(compact){targetList.push(L.marker([s.latitude,s.longitude],{interactive:false,icon:L.divIcon({className:'',html:`<div class="seg-label" data-roof-summary="true">#${index+1} Â· ${fmt(s.total_roof_sqft)} ftÂ²</div>`,iconAnchor:[45,10]})}).addTo(targetMap))}const visualOutline=(kind==='house'&&outlineEditMode)?null:((kind==='house'&&Array.isArray(adjustedOutline)&&adjustedOutline.length>=3)?adjustedOutline:s.outline);if(!skipOutline&&mode==='smart'&&Array.isArray(visualOutline)&&visualOutline.length>=3){const poly=L.polygon(visualOutline,{color,weight:5,fillColor:color,fillOpacity:.045,interactive:false,lineJoin:'round',smoothFactor:1.35}).addTo(targetMap);targetList.unshift(poly);if(targetMap===map&&!compact)drawEdgeMeasurements(visualOutline,color,targetMap,targetList,true)}}
function redrawRoofData(){clearOverlays();(structures||[]).forEach((st,i)=>drawSegments(st,i===0?'house':'garage'));}

function roofCheckGood(){if(structures[0]?.needs_remeasure||structures[0]?.automatic_review_warning){status('The main roof needs remeasurement in the Property Summary before it can be confirmed.','warn');return}if(structures[0])structures[0].automatic_review_confirmed=true;roofFixMode=false;if(el('fixRoofBtn')){el('fixRoofBtn').textContent='NO â€” REMOVE WRONG ROOF';el('fixRoofBtn').className='orange'}if(el('roofFixHelp'))el('roofFixHelp').innerHTML='<b>âœ“ Roofs confirmed.</b> Continue to price and estimate.';status('Roofs confirmed. Continue to price and estimate.','ok')}
function toggleRoofFix(){if(!structures.length){status('Load and measure the property first.','error');return}roofFixMode=!roofFixMode;if(el('fixRoofBtn')){el('fixRoofBtn').textContent=roofFixMode?'CANCEL FIX':'NO â€” REMOVE WRONG ROOF';el('fixRoofBtn').className=roofFixMode?'danger':'orange'}if(el('roofFixHelp'))el('roofFixHelp').innerHTML=roofFixMode?'<b>Click a wrong extra roof on the map to remove it.</b> If a roof is missing, use <b>+ ADD GARAGE / OTHER ROOF</b> above. Square footage and price recalculate automatically.':'Roof fix cancelled.';status(roofFixMode?'FIX ROOF ON â€” click the wrong extra roof to remove it.':'Roof fix cancelled.',roofFixMode?'warn':'ok')}
function removeClickedExtraRoof(ll){if(!roofFixMode||structures.length<2){roofFixMode=false;if(el('roofFixHelp'))el('roofFixHelp').textContent='No extra roof is available to remove. Use + Add Garage / Other Roof if a roof is missing.';status('No extra roof to remove.','warn');return}let best=-1,bestD=Infinity;for(let i=1;i<structures.length;i++){const st=structures[i],lat=Number(st.latitude),lng=Number(st.longitude);if(!Number.isFinite(lat)||!Number.isFinite(lng))continue;const dy=(ll.lat-lat)*111320,dx=(ll.lng-lng)*111320*Math.cos(ll.lat*Math.PI/180),d=Math.hypot(dx,dy);if(d<bestD){bestD=d;best=i}}if(best<1){status('Could not identify that extra roof. Click nearer its centre.','error');return}const removed=structures.splice(best,1)[0];roofFixMode=false;if(el('fixRoofBtn')){el('fixRoofBtn').textContent='NO â€” REMOVE WRONG ROOF';el('fixRoofBtn').className='orange'}redrawRoofData();renderSummary();if(el('roofFixHelp'))el('roofFixHelp').innerHTML='<b>âœ“ '+(removed.label||'Extra roof')+' removed.</b> Measurement and estimate recalculated. If the correct roof is missing, click <b>+ ADD GARAGE / OTHER ROOF</b>.';status((removed.label||'Extra roof')+' removed. Total and estimate recalculated.','ok')}
function outlineLooksGood(){status('Customer roof outline confirmed. Google measurement and price are unchanged.','ok');if(el('outlineHelp'))el('outlineHelp').innerHTML='<b>âœ“ Outline confirmed.</b> Google measurement remains '+fmt(googleTotal())+' ftÂ².'}
function setOutlineButtons(editing){if(el('adjustOutlineBtn')){el('adjustOutlineBtn').textContent=editing?'CANCEL OUTLINE EDIT':'ADJUST CUSTOMER OUTLINE';el('adjustOutlineBtn').className=editing?'danger':'orange'};['finishOutlineBtn','undoOutlineBtn','clearOutlineBtn'].forEach(id=>{if(el(id))el(id).style.display=editing||adjustedOutline?'inline-block':'none'});if(el('finishOutlineBtn'))el('finishOutlineBtn').disabled=!editing||outlinePoints.length<3}
function clearOutlineTemp(){outlineTempLayers.forEach(x=>{try{map.removeLayer(x)}catch(e){}});outlineTempLayers=[]}
function toggleOutlineAdjust(){if(!structures.length){status('Load and measure the property first.','error');return}if(outlineEditMode){outlineEditMode=false;outlinePoints=[];clearOutlineTemp();redrawRoofData();setOutlineButtons(false);if(el('outlineHelp'))el('outlineHelp').textContent='Outline edit cancelled. Google measurement and price were not changed.';return}outlineEditMode=true;outlinePoints=[];clearOutlineTemp();redrawRoofData();setOutlineButtons(true);if(el('outlineHelp'))el('outlineHelp').innerHTML='<b>Click around the outside edge of the shingled roof.</b> Click each corner once, then Finish Outline. This changes the customer picture only.';status('Adjust Customer Outline ON â€” click the outside roof corners.','warn')}
function addOutlinePoint(ll){outlinePoints.push(ll);const n=outlinePoints.length,pt=L.marker(ll,{interactive:false,icon:L.divIcon({className:'',html:`<div class="point-label">${n}</div>`,iconAnchor:[12,12]})}).addTo(map);outlineTempLayers.push(pt);redrawOutlineTrace();setOutlineButtons(true)}
function redrawOutlineTrace(){outlineTempLayers.filter(x=>x._outlineLine).forEach(x=>{try{map.removeLayer(x)}catch(e){}});outlineTempLayers=outlineTempLayers.filter(x=>!x._outlineLine);if(outlinePoints.length>=2){let c=[...outlinePoints];if(outlinePoints.length>=3)c.push(outlinePoints[0]);let l=L.polyline(c,{color:'#2d6cdf',weight:5,dashArray:'8,5'}).addTo(map);l._outlineLine=true;outlineTempLayers.push(l)}}
function undoOutlinePoint(){if(!outlineEditMode||!outlinePoints.length)return;const keep=outlinePoints.slice(0,-1);outlinePoints=[];clearOutlineTemp();keep.forEach(addOutlinePoint);setOutlineButtons(true)}
function finishOutlineAdjust(){if(!outlineEditMode||outlinePoints.length<3)return;adjustedOutline=outlinePoints.map(p=>[p.lat,p.lng]);outlineEditMode=false;outlinePoints=[];clearOutlineTemp();redrawRoofData();setOutlineButtons(false);if(el('outlineHelp'))el('outlineHelp').innerHTML='<b>âœ“ Customer outline adjusted.</b> Google roof measurement stays at '+fmt(googleTotal())+' ftÂ² and the estimate price is unchanged.';renderSummary();status('Customer outline updated. Google measurement and estimate price are unchanged.','ok')}
function clearAdjustedOutline(){adjustedOutline=null;outlineEditMode=false;outlinePoints=[];clearOutlineTemp();redrawRoofData();setOutlineButtons(false);if(el('outlineHelp'))el('outlineHelp').textContent='Using Google customer outline. Measurement and price are unchanged.';renderSummary();status('Google outline restored.','ok')}
function pitchChanged(){if(el('pitchSel').value!=='custom')el('pitchDeg').value=el('pitchSel').value;const custom=el('pitchSel').value==='custom';if(custom&&el('pitchDeg').type==='hidden')el('pitchDeg').value='';el('pitchDeg').type=custom?'number':'hidden';el('pitchDeg').placeholder='Pitch in degrees';el('pitchDeg').min='0';el('pitchDeg').max='79.9';el('pitchDeg').step='0.1';el('pitchDeg').setAttribute('aria-label','Roof pitch in degrees');el('tracePitchControl').append(el('pitchDeg'));el('pitchDeg').oninput=()=>updateManualReplacementUi();if(roofRemeasureTarget&&!roofOutlineReviewMode)updateManualReplacementUi()}
function commercialActive(){return ['commercial','paving','pressure','landscaping','snow'].includes(currentBusinessType())&&measurementViewMode==='area'}
function surfaceLinearJobRate(){return measurementViewMode==='linear'?currentJobPrice():(savedLinearJobRate===null?currentJobPrice():savedLinearJobRate)}
function savedSurfaceHasAreas(){return ['landscaping','paving','pressure','snow'].includes(currentBusinessType())&&multiAreaSaved()}
function surfaceServiceLabel(){return ({landscaping:'Landscaping',paving:'Paving & Sealcoating',pressure:'Pressure Washing',snow:'Snow Removal'})[currentBusinessType()]||'Service'}
function savedSurfacePriceLines(snap){return landscapingSavedPriceLines(snap).replace(/Landscaping Linear/g,surfaceServiceLabel()+' Linear')}
function landscapingHasAreas(){return currentBusinessType()==='landscaping'&&multiAreaSaved()}
function landscapingAreaSubtotal(){return commercialAreas.reduce((sum,a)=>sum+Number(a.sqft||0)*Number(a.rate||0),0)}
function landscapingSavedPriceLines(snap){return (snap.commercialAreas||[]).filter(a=>a.sqft>0).map(a=>`<div class="line"><span>${escapeHistory(a.name||'Service Area')} â€” ${fmt(a.sqft)} ftÂ² Ã— ${money(a.rate)}/ftÂ²</span><b>${money(a.sqft*a.rate)}</b></div>`).join('')+(snap.linearFeet>0?`<div class="line"><span>${surfaceServiceLabel()} Linear â€” ${Number(snap.linearFeet).toFixed(1)} ft Ã— ${money(snap.landscapingLinearRate)}/ft</span><b>${money(snap.linearFeet*snap.landscapingLinearRate)}</b></div>`:'')}
function multiAreaTotal(){return commercialAreas.reduce((n,a)=>n+(Number(a.sqft)||0),0)}
function multiAreaSaved(){return ['commercial','paving','pressure','landscaping','snow'].includes(currentBusinessType())&&commercialAreas.some(a=>a.sqft>0)}
function pavingCombined(){return currentBusinessType()==='paving'&&areaMeasurementSaved&&areaPoints.length>=3&&linearMeasurementSaved&&linearPoints.length>1}
function pavingAreaRate(){return Math.max(0,Number(el('pavingAreaRate')?.value||0))}
function pavingPriceLines(){return '<div class="line"><span>Paving Area â€” '+fmt(Math.round(multiAreaSaved()?multiAreaTotal():areaSqFtTotal()))+' ftÂ² Ã— '+money(pavingAreaRate())+'/ftÂ²</span><b>'+money(Math.round(multiAreaSaved()?multiAreaTotal():areaSqFtTotal())*pavingAreaRate())+'</b></div><div class="line"><span>Paving Linear â€” '+linearFeetTotal().toFixed(1)+' ft Ã— '+money(currentJobPrice())+'/ft</span><b>'+money(linearFeetTotal()*currentJobPrice())+'</b></div>'}
function pressureCombined(){return currentBusinessType()==='pressure'&&areaMeasurementSaved&&areaPoints.length>=3&&linearMeasurementSaved&&linearPoints.length>1}
function pressureAreaRate(){return Math.max(0,Number(el('pressureAreaRate')?.value||0))}
function pressurePriceLines(){return `<div class="line"><span>Pressure Washing Area â€” ${fmt(Math.round(multiAreaSaved()?multiAreaTotal():areaSqFtTotal()))} ftÂ² Ã— ${money(pressureAreaRate())}/ftÂ²</span><b>${money(Math.round(multiAreaSaved()?multiAreaTotal():areaSqFtTotal())*pressureAreaRate())}</b></div><div class="line"><span>Pressure Washing Linear â€” ${linearFeetTotal().toFixed(1)} ft Ã— ${money(currentJobPrice())}/ft</span><b>${money(linearFeetTotal()*currentJobPrice())}</b></div>`}
function landscapingCombined(){return currentBusinessType()==='landscaping'&&(multiAreaSaved()||(areaMeasurementSaved&&areaPoints.length>=3))&&linearMeasurementSaved&&linearPoints.length>1}
function landscapingAreaRate(){return Math.max(0,Number(el('landscapingAreaRate')?.value||0))}
function landscapingPriceLines(){if(landscapingHasAreas())return landscapingSavedPriceLines({commercialAreas,linearFeet:linearMeasurementSaved?linearFeetTotal():0,landscapingLinearRate:surfaceLinearJobRate()});return `<div class="line"><span>Landscaping Area â€” ${fmt(Math.round(multiAreaSaved()?multiAreaTotal():areaSqFtTotal()))} ftÂ² Ã— ${money(landscapingAreaRate())}/ftÂ²</span><b>${money(Math.round(multiAreaSaved()?multiAreaTotal():areaSqFtTotal())*landscapingAreaRate())}</b></div><div class="line"><span>Landscaping Linear â€” ${linearFeetTotal().toFixed(1)} ft Ã— ${money(currentJobPrice())}/ft</span><b>${money(linearFeetTotal()*currentJobPrice())}</b></div>`}
function commercialHasAreas(){return currentBusinessType()==='commercial'&&commercialAreas.some(a=>a.sqft>0)}
function commercialHasLinear(){return currentBusinessType()==='commercial'&&linearMeasurementSaved&&linearPoints.length>1}
function commercialLinearRate(){return Math.max(0,Number(el('commercialLinearRate')?.value||0))}
function commercialPriceLines(){return commercialAreas.filter(a=>a.sqft>0).map(a=>`<div class="line"><span>${escapeHistory(a.name||'Service Area')} â€” ${fmt(a.sqft)} ftÂ² Ã— ${money(a.rate)}/ftÂ²</span><b>${money(a.sqft*a.rate)}</b></div>`).join('')+(commercialHasLinear()?`<div class="line"><span>Linear Service â€” ${linearFeetTotal().toFixed(1)} ft Ã— ${money(commercialLinearRate())}/ft</span><b>${money(linearFeetTotal()*commercialLinearRate())}</b></div>`:'')}
function commercialSyncCurrent(){if(!commercialActive()||!areaMeasurementSaved||areaPoints.length<3)return;if(commercialEditingIndex<0)commercialEditingIndex=commercialAreas.length;const old=commercialAreas[commercialEditingIndex]||{};commercialAreas[commercialEditingIndex]={name:old.name||'Service Area '+(commercialEditingIndex+1),rate:old.rate===undefined?(String(el('jobPrice')?.value??'').trim()===''?'':currentJobPrice()):old.rate,source:old.source||'manual',points:areaPoints.map(p=>[p.lat,p.lng]),sqft:Math.round(areaSqFtTotal())}}
function commercialAreaField(i,key,value){if(areaRemeasureMode)return;if(!commercialAreas[i])return;if(key==='rate'){commercialAreas[i].rate=String(value).trim()===''?null:Number(value);if(currentBusinessType()!=='commercial'&&el('jobPrice')&&measurementViewMode==='area'&&commercialAreas.length===1){el('jobPrice').value=String(commercialAreas[i].rate);const rateId={landscaping:'landscapingAreaRate',paving:'pavingAreaRate',pressure:'pressureAreaRate'}[currentBusinessType()];if(rateId&&el(rateId))el(rateId).value=String(commercialAreas[i].rate)}}else commercialAreas[i].name=value;commercialAreaUi();renderSummary()}
function commercialAreaDrawSaved(){commercialAreaLayers.forEach(l=>{try{map.removeLayer(l)}catch(e){}});commercialAreaLayers=[];if(!['commercial','paving','pressure','landscaping','snow'].includes(currentBusinessType()))return;commercialAreas.forEach((a,i)=>{if((measurementViewMode==='area'&&i===commercialEditingIndex)||!a.points||a.points.length<3)return;const poly=L.polygon(a.points,{color:'#198b87',weight:3,fillOpacity:.1,interactive:false}).addTo(map);commercialAreaLayers.push(poly);drawCustomerAreaEdgeLabels(a.points,map,commercialAreaLayers);commercialAreaLayers.push(L.marker(poly.getBounds().getCenter(),{interactive:false,keyboard:false,icon:L.divIcon({className:'',html:`<div class="area-label">${fmt(a.sqft)} ftÂ²</div>`,iconAnchor:[35,10]})}).addTo(map))})}
function commercialAreaUi(){
 const panel=el('commercialAreaPanel');if(!panel)return;
 const surface=['commercial','paving','pressure','landscaping','snow'].includes(currentBusinessType()),saved=commercialAreas.map((a,i)=>({a,i})).filter(x=>x.a.sqft>0);
 panel.style.display=surface&&saved.length?'block':'none';if(!surface)return;
 panel.querySelector('b').textContent='Saved areas â€” '+fmt(multiAreaTotal())+' ftÂ²';
 const box=el('commercialAreaList');if(box)box.innerHTML=saved.map(({a,i})=>`<div class="surface-saved-area"><div class="surface-area-heading"><label>Area name<input aria-label="Service area name" value="${escapeHistory(a.name||'').replace(/"/g,'&quot;')}" onchange="commercialAreaField(${i},'name',this.value)"${areaRemeasureMode?' disabled':''}></label><strong>${fmt(a.sqft)} ftÂ²</strong></div><div class="surface-area-price"><label>Rate / sq. ft.<input aria-label="Rate per square foot" type="number" min="0" step="0.01" value="${a.rate}" onchange="commercialAreaField(${i},'rate',this.value)"${areaRemeasureMode?' disabled':''}></label><b>${a.rate!==null&&a.rate!==undefined&&String(a.rate).trim()!==''&&Number.isFinite(Number(a.rate))&&Number(a.rate)>=0?money(a.sqft*a.rate):'Rate required'}</b><span class="small">âœ“ Saved in this job</span></div><div class="simple-actions"><button type="button" class="primary" onclick="remeasureSurfaceArea(${i})"${areaMode||linearMode||linearCorrectionOriginal?' disabled':''}>REMEASURE AREA</button><button type="button" class="ghost" onclick="commercialEditArea(${i})"${areaMode||linearMode||linearCorrectionOriginal?' disabled':''}>EDIT OUTLINE</button><button type="button" class="ghost" onclick="commercialRemoveArea(${i})"${areaCorrectionOriginal||linearMode||linearCorrectionOriginal?' disabled':''}>REMOVE AREA</button></div></div>`).join('');
 if(el('commercialAddAreaBtn')){el('commercialAddAreaBtn').style.display='none';el('commercialAddAreaBtn').disabled=areaMode||!saved.length}
}
// A replacement is a draft; the saved record remains authoritative until Save.
function remeasureSurfaceArea(i){
 if(!surfaceIndustry()||!sessionToken||areaMode||linearMode||linearCorrectionOriginal)return;
 const saved=commercialAreas[i];if(!saved||!saved.points||saved.points.length<3)return;
 if(measurementViewMode==='linear')savedLinearJobRate=String(el('jobPrice')?.value??'').trim()===''?'':currentJobPrice();
 commercialSelectArea(i);
 if(commercialEditingIndex!==i)return;
 // Enter the requested workflow directly; no transient corner-edit/tool toggle.
 areaCorrectionOriginal=saved.points.map(p=>L.latLng(p[0],p[1]));
 measurementViewMode='area';pendingMeasurementMode='area';
 areaRemeasureMode=true;areaMode=true;areaPoints=[];areaMeasurementSaved=false;
 hideRoofDisplayForLinear();if(linearMeasurementSaved)redrawLinearMeasure();
 updatePropertyActionButton();redrawAreaMeasure();commercialAreaDrawSaved();renderSummary();
 status('Trace a new outline, then SAVE REPLACEMENT AREA. The original area and price stay unchanged until you save. Cancel keeps the original.','warn');
}
function replacementAreaError(){
 const problem=measuredPolygonError(areaPoints);if(problem)return problem;
 const candidate=commercialAreas.map((a,i)=>i===commercialEditingIndex?{...a,points:areaPoints.map(p=>[p.lat,p.lng]),sqft:Math.round(areaSqFtTotal())}:a);
 return savedAreaGeometryError(candidate);
}
function commercialEditArea(i){if(linearCorrectionOriginal)cancelLinearCorrection();if(linearMode){status('Finish and save your current line before editing an area.','warn');return}if(measurementViewMode==='linear'){savedLinearJobRate=String(el('jobPrice')?.value??'').trim()===''?'':currentJobPrice();measurementViewMode='area';pendingMeasurementMode='area';updatePropertyActionButton();updateMeasurementInterface()}commercialSelectArea(i);if(!areaMode&&commercialEditingIndex===i)correctAreaOutline()}
function restoreSavedLineAfterLastArea(){
 if(currentBusinessType()==='roofing'||commercialAreas.some(a=>a.sqft>0)||areaPoints.length||areaMode||!linearMeasurementSaved||linearPoints.length<2)return;
 const rate=currentBusinessType()==='commercial'?commercialLinearRate():surfaceLinearJobRate();
 measurementViewMode='linear';pendingMeasurementMode='linear';
 if(el('jobPrice'))el('jobPrice').value=String(rate);
 updatePropertyActionButton();redrawLinearMeasure();updateMeasurementInterface();
}
function commercialRemoveArea(i){if(areaRemeasureMode){status('Save or cancel the replacement area first.','warn');return}if(areaMode&&areaPoints.length){status('Finish and save your current outline before removing another area.','warn');return}if(areaMode){const draft=commercialEditingIndex;areaMode=false;areaMeasurementSaved=false;commercialEditingIndex=-1;if(draft>=0&&commercialAreas[draft]&&!commercialAreas[draft].sqft){commercialAreas.splice(draft,1);if(i===draft)i=-1;else if(i>draft)i--}if(el('areaStartBtn')){el('areaStartBtn').textContent='START ANOTHER SERVICE AREA';el('areaStartBtn').className='secondary'}}if(i<0){if(commercialAreas.length)commercialSelectArea(commercialAreas.length-1);else{updateAreaUi();renderSummary()}return}if(!commercialAreas[i])return;commercialAreas.splice(i,1);commercialEditingIndex=-1;areaPoints=[];areaMeasurementSaved=false;clearAreaLayers();if(commercialAreas.length&&measurementViewMode!=='linear'){commercialSelectArea(Math.min(i,commercialAreas.length-1))}commercialAreaDrawSaved();restoreSavedLineAfterLastArea();updateAreaUi();renderSummary()}
function commercialSelectArea(i){if(areaMode){status('Save the current outline first.','warn');return}commercialSyncCurrent();const a=commercialAreas[i];if(!a||!a.points.length)return;commercialEditingIndex=i;if(['landscaping','paving','pressure','snow'].includes(currentBusinessType())&&el('jobPrice'))el('jobPrice').value=String(a.rate);areaPoints=a.points.map(p=>L.latLng(p[0],p[1]));areaMeasurementSaved=true;redrawAreaMeasure();commercialAreaDrawSaved();updateAreaUi();renderSummary()}
function commercialAddArea(){if(!commercialActive()||areaMode||(!multiAreaSaved()&&(!areaMeasurementSaved||areaPoints.length<3))){status('Save the current service area first.','warn');return}commercialSyncCurrent();let number=commercialAreas.length+1;while(commercialAreas.some(a=>a.name==='Service Area '+number))number++;commercialEditingIndex=commercialAreas.length;commercialAreas.push({name:'Service Area '+number,rate:String(el('jobPrice')?.value??'').trim()===''?'':currentJobPrice(),points:[],sqft:0});areaPoints=[];areaMeasurementSaved=false;clearAreaLayers();commercialAreaDrawSaved();updateAreaUi();renderSummary();toggleAreaMeasure()}
function areaSqFtTotal(){if(areaPoints.length<3)return 0;return localPolygonAreaM2(areaPoints)*10.76391041671}
function clearAreaLayers(){areaLayers.forEach(x=>{try{map.removeLayer(x)}catch(e){}});areaLayers=[]}
function surfaceIndustry(){return ['commercial','paving','pressure','landscaping','snow'].includes(currentBusinessType())}
function cancelSurfaceAreaDrawing(){
 if(!surfaceIndustry()||!areaMode)return;
 if(areaCorrectionOriginal){cancelAreaCorrection();commercialAreaDrawSaved();return}
 const draft=commercialEditingIndex;areaMode=false;areaPoints=[];areaMeasurementSaved=false;commercialEditingIndex=-1;
 if(draft>=0&&commercialAreas[draft]&&!commercialAreas[draft].sqft)commercialAreas.splice(draft,1);
 clearAreaLayers();const saved=commercialAreas.map((a,i)=>({a,i})).filter(x=>x.a.sqft>0);
 if(saved.length)commercialSelectArea(saved[saved.length-1].i);else restoreSavedLineAfterLastArea();
 commercialAreaDrawSaved();updateAreaUi();updateLinearUi();renderSummary();status('Area drawing cancelled. Saved measurements are unchanged.','ok');
}
function restartSurfaceAreaDrawing(){
 if(!surfaceIndustry()||!areaMode)return;
 areaPoints=[];areaMeasurementSaved=false;redrawAreaMeasure();renderSummary();status('Drawing cleared. Click the corners again, or Cancel to keep the saved measurements.','ok');
}
function restartSurfaceLineDrawing(){
 if(!surfaceIndustry()||!linearMode)return;linearPoints=[];linearMeasurementSaved=false;redrawLinearMeasure();renderSummary();status('Line drawing cleared. Place the points again, or Cancel to restore the saved line.','ok');
}
function cancelSurfaceLineDrawing(){
 if(!surfaceIndustry()||!linearMode)return;
 const original=surfaceLineDraftOriginal;linearMode=false;
 linearPoints=(original?.points||[]).map(p=>L.latLng(p.lat,p.lng));linearMeasurementSaved=!!original?.saved;
 if(original){savedLinearJobRate=original.savedRate;if(el('jobPrice'))el('jobPrice').value=original.jobRate}
 surfaceLineDraftOriginal=null;redrawLinearMeasure();
 if(!linearMeasurementSaved&&multiAreaSaved())selectMeasurementTool('area');
 updateLinearUi();renderSummary();status('Line drawing cancelled. Saved measurements are unchanged.','ok');
}
function syncSurfaceMeasurementControls(){
 const surface=surfaceIndustry();document.body.classList.toggle('surface-simple',surface);
 const area=el('areaTool'),line=el('linearTool'),start=el('linearStartBtn'),clear=el('linearClearBtn');if(!area||!line||!start||!clear)return;
 for(const node of [start,clear])if(!node._surfaceAnchor){const anchor=document.createComment('Original line control');node.before(anchor);node._surfaceAnchor=anchor}
 let more=el('surfaceLineMore'),cancel=el('surfaceLineCancel');
 if(!surface){
  for(const node of [start,clear])if(node._surfaceAnchor&&node.parentNode!==node._surfaceAnchor.parentNode)node._surfaceAnchor.parentNode.insertBefore(node,node._surfaceAnchor.nextSibling);
  if(more)more.remove();if(cancel)cancel.hidden=true;
  area.style.display='';line.style.display='';
  el('areaStartBtn').disabled=false;el('areaStartBtn').textContent=areaMode?'FINISH & SAVE AREA':areaMeasurementSaved?'CONTINUE AREA MEASURE':'START AREA MEASURE';start.disabled=false;start.textContent=linearMode?'FINISH & SAVE LINEAR':linearMeasurementSaved?'CONTINUE LINEAR MEASURE':'START LINEAR MEASURE';clear.textContent='CLEAR LINEAR MEASUREMENT';clear.setAttribute('onclick','clearLinearMeasure()');el('linearSaveEditBtn').disabled=false;el('linearEditBtn').disabled=false;
  el('areaCancelCorrectionBtn').setAttribute('onclick','cancelAreaCorrection()');el('areaCancelCorrectionBtn').textContent='CANCEL CORRECTION';
  el('areaClearBtn').setAttribute('onclick','clearAreaMeasure()');el('areaClearBtn').textContent='CLEAR AREA MEASUREMENT';
  for(const id of ['toolAreaBtn','toolLinearBtn'])if(el(id))el(id).disabled=false;
  const guide=el('surfaceSaveGuidance');if(guide){guide.hidden=true;guide.textContent=''}return;
 }
 // One Add Area action lives in the toolbar. Drawing controls appear only during a draft/edit.
 if(el('commercialAddAreaBtn'))el('commercialAddAreaBtn').style.display='none';
 area.style.display=areaMode?'block':'none';if(areaMode)el('areaTotal').textContent='Drawing: '+fmt(areaSqFtTotal())+' ftÂ²';
 el('areaStartBtn').style.display=areaMode?'inline-block':'none';el('areaStartBtn').textContent=areaRemeasureMode?'SAVE REPLACEMENT AREA':areaCorrectionOriginal?'SAVE AREA CHANGES':'SAVE AREA';el('areaStartBtn').disabled=areaMode&&!!(areaRemeasureMode?replacementAreaError():measuredPolygonError(areaPoints));
 el('areaCorrectBtn').style.display='none';el('areaCancelCorrectionBtn').style.display=areaMode?'inline-block':'none';el('areaCancelCorrectionBtn').textContent='CANCEL';el('areaCancelCorrectionBtn').setAttribute('onclick','cancelSurfaceAreaDrawing()');
 el('areaClearBtn').style.display=areaMode&&areaPoints.length?'inline-block':'none';el('areaClearBtn').textContent='START OVER';el('areaClearBtn').setAttribute('onclick','restartSurfaceAreaDrawing()');
 if(areaMode&&areaRemeasureMode)el('areaHelp').textContent=areaPoints.length>=3&&replacementAreaError()?replacementAreaError():'Trace the replacement boundary in order. SAVE REPLACEMENT AREA confirms the new outline and price; Cancel keeps the original.';
 else if(areaMode)el('areaHelp').textContent=areaPoints.length>=3&&measuredPolygonError(areaPoints)?measuredPolygonError(areaPoints):areaCorrectionOriginal?'Drag the corner points or start over. Save Area Changes when finished; Cancel keeps the original outline.':areaPoints.length>=3?'Check the outline, then click SAVE AREA.':'Click around the outside edge. Place at least three corners, then SAVE AREA.';
 const savedLine=linearMeasurementSaved&&linearPoints.length>=2&&!linearMode&&!linearCorrectionOriginal;
 line.style.display=linearMode||linearCorrectionOriginal||savedLine?'block':'none';
 if(!more){more=document.createElement('details');more.id='surfaceLineMore';more.innerHTML='<summary>More line options</summary><div class="simple-actions"></div>';el('linearHelp').before(more)}
 if(savedLine){more.hidden=false;if(!more._wasSaved)more.open=false;more.querySelector('div').append(start,clear);start.style.display='inline-block';start.textContent='EXTEND LINE';clear.style.display='inline-block';clear.textContent='REMOVE LINE';clear.setAttribute('onclick','clearLinearMeasure()');el('linearHelp').textContent='âœ“ Saved in this job. Edit Line moves the points. More line options lets you extend or remove the line.'}
 else{more.hidden=true;for(const node of [start,clear])if(node.parentNode!==node._surfaceAnchor.parentNode)node._surfaceAnchor.parentNode.insertBefore(node,node._surfaceAnchor.nextSibling);clear.style.display=linearMode&&linearPoints.length?'inline-block':'none';clear.textContent='START OVER';clear.setAttribute('onclick','restartSurfaceLineDrawing()');start.textContent='SAVE LINE'}
 more._wasSaved=savedLine;start.disabled=areaMode||(linearMode&&(linearPoints.length<2||linearFeetTotal()<.001));clear.disabled=areaMode||!!linearCorrectionOriginal;
 el('linearSaveEditBtn').disabled=!!linearCorrectionOriginal&&linearFeetTotal()<.001;el('linearEditBtn').disabled=areaMode;
 if(!cancel){cancel=document.createElement('button');cancel.id='surfaceLineCancel';cancel.type='button';cancel.className='ghost';cancel.textContent='CANCEL';cancel.onclick=cancelSurfaceLineDrawing;start._surfaceAnchor.parentNode.append(cancel)}cancel.hidden=!linearMode;
 if(linearMode)el('linearHelp').textContent=linearPoints.length>=2&&linearFeetTotal()<.001?'The line needs two different points. Start over or Cancel.':linearPoints.length>=2?'Check the line, then click SAVE LINE.':'Click the starting point, then each turn or endpoint. Place at least two points, then SAVE LINE.';
 el('toolAreaBtn').disabled=false;el('toolLinearBtn').disabled=false;
 const button=el('createEstimateBtn');let guide=el('surfaceSaveGuidance');if(!guide){guide=document.createElement('div');guide.id='surfaceSaveGuidance';guide.setAttribute('role','status');guide.setAttribute('aria-live','polite');guide.style.marginTop='10px';button.closest('.simple-actions').after(guide)}
 guide.hidden=!sessionToken;const active=areaMode||linearMode||linearCorrectionOriginal,hasSaved=multiAreaSaved()||savedLine;
 guide.className=(active?'warning':'good')+' small';guide.textContent=active?'Finish the active drawing above the aerial: '+(areaMode?(areaRemeasureMode?'SAVE REPLACEMENT AREA':areaCorrectionOriginal?'SAVE AREA CHANGES':'SAVE AREA'):linearCorrectionOriginal?'SAVE LINE CHANGES':'SAVE LINE')+' or CANCEL. Saved measurements are kept.':hasSaved?'âœ“ Measurements saved in this job. Add customer details, then CREATE CUSTOMER ESTIMATE to save the completed estimate. Create it before leaving or refreshing.':'Choose ADD AREA or LINEAR above the aerial to start measuring.';
}
function updateAreaUi(){syncMeasurementEditMapDragging();const total=areaSqFtTotal(),surfaceOnly=['commercial','paving','pressure','landscaping','snow'].includes(currentBusinessType());commercialAreaUi();if(el("areaCorrectBtn"))el("areaCorrectBtn").style.display=areaMeasurementSaved&&!areaMode&&areaPoints.length>=3?"inline-block":"none";if(el("areaCancelCorrectionBtn"))el("areaCancelCorrectionBtn").style.display=areaCorrectionOriginal?"inline-block":"none";if(el('areaTotal'))el('areaTotal').textContent=`Area: ${fmt(multiAreaSaved()?multiAreaTotal():total)} ftÂ²`;if(el('areaUndoBtn'))el('areaUndoBtn').style.display=areaMode&&areaPoints.length?'inline-block':'none';if(el('areaClearBtn'))el('areaClearBtn').style.display=(areaMode||measurementViewMode==='area')&&areaPoints.length?'inline-block':'none';if(el('areaAutoBtn'))el('areaAutoBtn').style.display=!surfaceOnly&&measurementViewMode==='area'?'inline-block':'none';if(el('areaHelp'))el('areaHelp').innerHTML=areaMode?(areaPoints.length>=3?`<b>Area Measure ON.</b> ${areaPoints.length} points placed â€¢ <b>${fmt(total)} ftÂ²</b>. Keep clicking to adjust the outline, then Save Area Measurement.`:`<b>Area Measure ON.</b> Click at least three corners around the service area.`):(measurementViewMode==='area'&&areaMeasurementSaved?`<b>âœ“ Area measurement saved: ${fmt(total)} ftÂ².</b> ${multiAreaSaved()?'All saved service areas are included in this quote.':currentBusinessType()==='paving'?'Only the saved paved surface is included in this quote.':currentBusinessType()==='pressure'?'Only the saved cleaning surface is included in this quote.':currentBusinessType()==='landscaping'?'Only the measured landscaping area is included in this quote.':'Only the selected service area is included in this quote.'}`:'Click Start Area Measure for a clean aerial workspace.');document.body.classList.toggle('area-active',areaMode);syncSurfaceMeasurementControls();}
function correctAreaOutline(){if(!sessionToken||!areaMeasurementSaved||areaPoints.length<3)return;areaCorrectionOriginal=areaPoints.map(p=>L.latLng(p.lat,p.lng));toggleAreaMeasure();status("Drag the purple corner handles to correct the outline, then select FINISH & SAVE AREA.","warn")}
function cancelAreaCorrection(){if(!areaCorrectionOriginal)return;areaRemeasureMode=false;areaPoints=areaCorrectionOriginal.map(p=>L.latLng(p.lat,p.lng));areaCorrectionOriginal=null;areaMode=false;areaMeasurementSaved=true;measurementViewMode="area";if(el("areaStartBtn")){el("areaStartBtn").textContent=commercialActive()?"START ANOTHER SERVICE AREA":"CONTINUE AREA MEASURE";el("areaStartBtn").className="secondary"}redrawAreaMeasure();renderSummary();commercialAreaDrawSaved();status("Outline correction cancelled; previous measurement restored.","ok")}
function redrawAreaMeasure(){clearAreaLayers();if(!areaPoints.length){updateAreaUi();return}areaPoints.forEach(pt=>{const dot=L.marker(pt,{draggable:areaMode,interactive:areaMode,icon:L.divIcon({className:'',html:'<div class="area-point"></div>',iconAnchor:[6,6]})}).addTo(map);if(areaMode){const index=areaPoints.indexOf(pt);dot.on('dragend',()=>{areaPoints[index]=dot.getLatLng();redrawAreaMeasure();renderSummary()})}areaLayers.push(dot)});if(areaPoints.length>=2){let pts=[...areaPoints];if(areaPoints.length>=3)pts.push(areaPoints[0]);const poly=L.polyline(pts,{color:'#7357b8',weight:5,opacity:.95,lineJoin:'round'}).addTo(map);areaLayers.push(poly)}if(areaPoints.length>=2){
 const closed=areaPoints.length>=3;
 const count=closed?areaPoints.length:areaPoints.length-1;
 for(let i=0;i<count;i++){
  const a=areaPoints[i],b=areaPoints[(i+1)%areaPoints.length];
  const feet=map.distance(a,b)*3.28084;
  const mid=L.latLng((a.lat+b.lat)/2,(a.lng+b.lng)/2);
  const label=L.marker(mid,{interactive:false,keyboard:false,icon:L.divIcon({className:'aeri-edge-label-icon',html:'<span class="aeri-edge-label">'+(feet<100?feet.toFixed(1):Math.round(feet).toLocaleString())+' ft</span>',iconSize:[90,24],iconAnchor:[45,12]})}).addTo(map);
  areaLayers.push(label);
 }
}if(areaPoints.length>=3){const fill=L.polygon(areaPoints,{color:'#7357b8',weight:0,fillColor:'#7357b8',fillOpacity:.14,interactive:false}).addTo(map);areaLayers.push(fill);const c=fill.getBounds().getCenter(),lab=L.marker(c,{interactive:false,icon:L.divIcon({className:'',html:`<div class="area-label">${fmt(areaSqFtTotal())} ftÂ²</div>`,iconAnchor:[35,10]})}).addTo(map);areaLayers.push(lab)}updateAreaUi()}
function addAreaPoint(ll){if(!areaMode)return;if(areaCorrectionOriginal&&!areaRemeasureMode){status('Drag an existing corner to adjust this outline. Save the changes or Cancel to restore the saved area.','warn');return}areaPoints.push(ll);areaMeasurementSaved=false;redrawAreaMeasure();renderSummary()}
function undoAreaPoint(){if(!areaMode||!areaPoints.length)return;areaPoints.pop();areaMeasurementSaved=false;redrawAreaMeasure();renderSummary()}
function clearAreaMeasure(){if(areaRemeasureMode){cancelSurfaceAreaDrawing();return}areaCorrectionOriginal=null;areaPoints=[];areaMeasurementSaved=false;if(commercialActive()&&commercialEditingIndex>=0){commercialAreas.splice(commercialEditingIndex,1);commercialEditingIndex=-1;commercialAreaDrawSaved()}clearAreaLayers();restoreSavedLineAfterLastArea();updateAreaUi();renderSummary();status('Area measurement cleared.','ok')}
function toggleAreaMeasure(){if(linearCorrectionOriginal)cancelLinearCorrection();if(!sessionToken){status('Load the property first.','error');return}if(commercialActive()&&!areaMode&&areaMeasurementSaved&&areaPoints.length>=3&&!areaCorrectionOriginal){commercialAddArea();return}if(areaMode){const problem=areaRemeasureMode?replacementAreaError():measuredPolygonError(areaPoints);if(problem){status(problem,'error');return}areaMode=false;if(!areaMeasurementSaved)usage.area++;areaMeasurementSaved=true;areaCorrectionOriginal=null;areaRemeasureMode=false;measurementViewMode='area';if(commercialActive()){commercialSyncCurrent();commercialAreaDrawSaved();}if(el('areaStartBtn')){el('areaStartBtn').textContent=commercialActive()?'START ANOTHER SERVICE AREA':'CONTINUE AREA MEASURE';el('areaStartBtn').className='secondary'}updateAreaUi();renderSummary();status(`âœ“ AREA MEASUREMENT SAVED â€” ${fmt(areaSqFtTotal())} ftÂ².`,'ok');return}if(linearMode)stopLinearMode(false);linearMode=false;if(linearMeasurementSaved&&linearPoints.length>=2)redrawLinearMeasure();else clearLinearLayers();areaMode=true;areaMeasurementSaved=false;measurementViewMode='area';hideRoofDisplayForLinear();if(el('areaStartBtn')){el('areaStartBtn').textContent='FINISH & SAVE AREA';el('areaStartBtn').className='primary'}redrawAreaMeasure();updateAreaUi();renderSummary();status('AREA MEASURE ON â€” click around the outside edge of the service area.','warn')}
function returnAreaToAutoMeasure(){if(areaMode&&areaPoints.length){status('Finish and save or clear the current area before returning to AutoMeasure.','warn');return}areaMode=false;measurementViewMode='auto';areaMeasurementSaved=areaPoints.length>=3;if(el('areaStartBtn')){el('areaStartBtn').textContent='START AREA MEASURE';el('areaStartBtn').className='secondary'}clearAreaLayers();restoreAutoMeasureDisplay();updateAreaUi();renderSummary();status('AutoMeasure restored. Your saved area measurement is still available.','ok')}
function roofRowActionHtml(roof,index){
 if(roofRemeasureTarget===roof)return '<span class="roof-editing-indicator">Editing this roof â€” use the controls beside the aerial.</span>';
 const flagged=roof.needs_remeasure||roof.automatic_review_warning;
 const saved=roof.manually_measured&&!flagged?'<div class="good small" style="margin:6px 0">âœ“ Saved in this job â€” no additional roof Save needed.</div>':'';
 return saved+'<button class="'+(flagged?'secondary':'ghost')+' roof-row-action" type="button"'+(traceMode?' disabled':'')+' onclick="correctSelectedRoof('+index+')">'+(flagged?'FIX ROOF':'EDIT ROOF')+'</button>';
}
function correctSelectedRoof(index){
 if(traceMode){status('Save or cancel the roof you are editing before selecting another roof.','warn');return}
 const roof=structures[index];if(!roof)return;
 // An unverified provider boundary is not the dealer's saved correction.
 // Fix starts clean; Edit still reviews a saved boundary. Preserve the explicit
 // overlapping-manual-trace review rather than silently double-counting it.
 if((roof.needs_remeasure||roof.automatic_review_warning)&&!roof.manually_measured&&!manualTracesForRoof(roof).length){startRoofRemeasure(index);return}
 if(detectedRoofReviewOutline(roof))startDetectedRoofReview(index);else startRoofRemeasure(index);
}
function updateRoofSaveGuidance(){
 const button=el('createEstimateBtn');if(!button)return;
 let help=el('roofSaveGuidance');
 if(!help){help=document.createElement('div');help.id='roofSaveGuidance';help.setAttribute('role','status');help.setAttribute('aria-live','polite');help.style.marginTop='10px';button.closest('.simple-actions').after(help)}
 const visible=currentBusinessType()==='roofing'&&measurementViewMode==='auto'&&(structures.length||manualPlanes.length);
 help.hidden=!visible;if(!visible){help.textContent='';return}
 const pending=structures.filter(s=>s.needs_remeasure||s.automatic_review_warning),saved=structures.filter(s=>s.manually_measured&&!s.needs_remeasure&&!s.automatic_review_warning);
 const savedText=saved.length?saved.map(s=>s.label).join(', ')+(saved.length===1?' is':' are')+' saved in this job. ':'';
 const confirmationRequired=manualRoofQa()&&manualPlanes.length&&!el('manualRoofScopeConfirmed')?.checked;
 help.className=(roofRemeasureTarget||pending.length||confirmationRequired?'warning':'good')+' small';
 help.textContent=roofRemeasureTarget?'Editing '+roofRemeasureTarget.label+'. Save or cancel this roof using the controls above the aerial before creating the estimate.':pending.length?savedText+'Estimate locked: '+pending.map(s=>s.label).join(', ')+(pending.length===1?' still needs':' still need')+' correction. Click FIX ROOF beside '+pending[0].label+' in Property Summary.':confirmationRequired?'Review each saved sectionâ€™s pitch, then select â€œConfirm pitches and included roofsâ€ beside the saved sections to continue.':savedText+'Roof measurements are ready. Add customer details, then click CREATE CUSTOMER ESTIMATE to save the completed estimate.';
 help.textContent+=' Measurements stay in this job until you leave or refresh; create the completed estimate before then.';
}
function syncRoofWorkspace(){
 syncMeasurementEditMapDragging();
 const roofing=currentBusinessType()==='roofing',toolbar=document.querySelector('.measure-toolbar'),manual=el('manualRoofDetails'),advanced=el('roofCheckCard')?.querySelector('.roof-advanced'),advancedBody=advanced?.querySelector('.roof-advanced-body'),display=el('advancedOptions');
 document.body.classList.toggle('roofing-simplified',roofing);
 if(!toolbar||!manual||!advancedBody)return;
 for(const node of [manual,display])if(node&&!node._roofWorkspaceAnchor){const anchor=document.createComment('Roof workspace tool position');node.before(anchor);node._roofWorkspaceAnchor=anchor}
 let other=el('roofSecondaryTools');
 if(roofing){
  if(!other){other=document.createElement('details');other.id='roofSecondaryTools';other.className='roof-secondary-tools';const title=document.createElement('summary');title.textContent='Area / linear tools';other.append(title);const buttons=document.createElement('div');buttons.className='roof-secondary-buttons';other.append(buttons);toolbar.append(other);buttons.append(el('toolAreaBtn'),el('toolLinearBtn'))}
  if(other._roofLastMode!==measurementViewMode){other.open=measurementViewMode!=='auto';other._roofLastMode=measurementViewMode;}
  const title=advanced.querySelector('summary');if(title&&title.textContent!=='Advanced roof tools')title.textContent='Advanced roof tools';
  const oldOverride=el('manualOverrideBtn')?.closest('details');if(oldOverride)oldOverride.hidden=structures.length>0;
  if(display&&display.parentNode!==advancedBody)advancedBody.append(display);
  const active=traceMode||(!structures.length&&!manualPlanes.length&&fallbackMode);
  manual.classList.toggle('roof-editor-active',active);
  if(active){const anchor=manual._roofWorkspaceAnchor;if(manual.parentNode!==anchor.parentNode)anchor.parentNode.insertBefore(manual,anchor.nextSibling);manual.open=true;if(traceMode&&el('manualRoofSummary')){const name=roofRemeasureTarget?.label||(!structures.length?'Main roof':'Additional roof');const title='Edit '+name;if(el('manualRoofSummary').textContent!==title)el('manualRoofSummary').textContent=title}}
  else{if(manual.parentNode!==advancedBody){advancedBody.append(manual);manual.open=false}if(el('manualRoofSummary')&&el('manualRoofSummary').textContent!=='Trace a missing roof manually')el('manualRoofSummary').textContent='Trace a missing roof manually'}
 }else{
  if(other){toolbar.append(el('toolAreaBtn'),el('toolLinearBtn'));other.remove()}
  manual.classList.remove('roof-editor-active');for(const node of [manual,display]){const anchor=node?._roofWorkspaceAnchor;if(anchor&&node.parentNode!==anchor.parentNode)anchor.parentNode.insertBefore(node,anchor.nextSibling)}
  const oldOverride=el('manualOverrideBtn')?.closest('details');if(oldOverride)oldOverride.hidden=false;
 }
 if(roofing&&traceMode){
  if(el('traceBtn')&&el('traceBtn').textContent!=='CANCEL')el('traceBtn').textContent='CANCEL';
  if(el('clearManualBtn')&&el('clearManualBtn').textContent!=='START OVER')el('clearManualBtn').textContent='START OVER';
 }
}
function updateMeasurementInterface(){
 if(!manualRoofQa()&&el('manualRoofSections')){el('manualRoofSections').remove();for(const id of ['toolAreaBtn','toolLinearBtn'])if(el(id))el(id).disabled=false;}
 const industry=currentBusinessType(),surfaceOnly=['commercial','paving','pressure','landscaping','snow'].includes(industry);
 const roofLegend=document.querySelector('.roof-legend');if(roofLegend)roofLegend.style.display=surfaceOnly?'none':'';
 const autoButton=el('toolAutoBtn');if(autoButton)autoButton.style.display=surfaceOnly?'none':'';
 const areaAuto=el('areaAutoBtn');if(areaAuto)areaAuto.style.display=surfaceOnly?'none':areaAuto.style.display;
 const linearAuto=el('linearAutoBtn');if(linearAuto)linearAuto.style.display=surfaceOnly?'none':linearAuto.style.display;
 const mode=measurementViewMode||'auto';document.body.classList.remove('measure-auto','measure-area','measure-linear');document.body.classList.add('measure-'+mode);
 const priceTitle=el('jobPriceTitle');if(priceTitle)priceTitle.textContent=mode==='linear'?'LINEAR MEASUREMENT & PRICE':mode==='area'?'AREA MEASUREMENT & PRICE':'Price for this job';
 ['auto','area','linear'].forEach(m=>{const b=el('tool'+m.charAt(0).toUpperCase()+m.slice(1)+'Btn');if(b)b.classList.toggle('active',mode===m)});
 const rows=[];const roofSq=Math.round((structures||[]).reduce((a,x)=>a+Number(x.total_roof_sqft||0),0)+(manualPlanes||[]).reduce((a,x)=>a+Number(x.surface_sqft||0),0));
 if(roofSq>0&&currentBusinessType()==='roofing')rows.push(`<div class="jm-row"><span class="jm-kind">Roof â€” ${manualRoofQa()&&manualPlanes.length&&!structures.length?'Manual roof sections':structures.some(st=>st.manually_measured)?'Measured with corrections':'AutoMeasure'}</span><span class="jm-value">${fmt(roofSq)} ftÂ²</span><span class="jm-status">${structures.some(st=>st.needs_remeasure||st.automatic_review_warning)?'REVIEW REQUIRED':'SAVED'}</span></div>`);
 if(multiAreaSaved())commercialAreas.forEach((a,i)=>{if(a.sqft>0)rows.push(`<div class="jm-row"><span class="jm-kind">${escapeHistory(a.name||'Service Area '+(i+1))}</span><span class="jm-value">${fmt(a.sqft)} ftÂ²</span><span class="jm-status">SAVED</span></div>`)});
 else if(areaMeasurementSaved&&areaPoints.length>=3)rows.push(`<div class="jm-row"><span class="jm-kind">Service Area â€” Area</span><span class="jm-value">${fmt(areaSqFtTotal())} ftÂ²</span><span class="jm-status">SAVED</span></div>`);
 if(linearMeasurementSaved&&linearPoints.length>=2)rows.push(`<div class="jm-row"><span class="jm-kind">Service Length â€” Linear</span><span class="jm-value">${linearFeetTotal().toFixed(1)} ft</span><span class="jm-status">SAVED</span></div>`);
 if(el('jobMeasurementsList'))el('jobMeasurementsList').innerHTML=rows.length?rows.join(''):'<div class="jm-empty">Load a property, then choose a measurement tool.</div>';
 syncRoofWorkspace();updateRoofSaveGuidance();syncSurfaceMeasurementControls();if(manualRoofQa())syncManualRoofQa();
}
function updatePropertyActionButton(){
 const b=el('propertyActionBtn');if(!b)return;
 const mode=pendingMeasurementMode||measurementViewMode||'auto';
 b.textContent=mode==='area'?'LOAD PROPERTY & START AREA MEASURE':mode==='linear'?'LOAD PROPERTY & START LINEAR MEASURE':'LOAD & MEASURE ROOF';
}
function startServiceAreaTool(){
 if(linearMode&&linearPoints.length&&!linearCorrectionOriginal){status('Finish and save or clear the current line before adding an area.','warn');return}
 if(linearCorrectionOriginal)cancelLinearCorrection();
 if(sessionToken&&!areaMode&&multiAreaSaved()){
  if(measurementViewMode==='linear')savedLinearJobRate=String(el('jobPrice')?.value??'').trim()===''?'':currentJobPrice();
  measurementViewMode='area';pendingMeasurementMode='area';updateMeasurementInterface();commercialAddArea();return;
 }
 selectMeasurementTool('area');
}
function selectMeasurementTool(mode){
 if(manualRoofQa()){
  if(traceMode){status('Save or cancel the roof section before switching tools.','warn');return}
  if(mode==='area'){beginManualRoofSection();return}
 }
 if(areaMode&&areaPoints.length&&mode!=='area'){status('Finish and save or clear the current area before switching measurement tools.','warn');return}
 if(surfaceIndustry()&&areaMode&&!areaPoints.length&&mode!=='area')cancelSurfaceAreaDrawing();
 if(linearMode&&linearPoints.length&&mode!=='linear'&&!linearCorrectionOriginal){status('Finish and save or clear the current line before switching measurement tools.','warn');return}
 if(linearCorrectionOriginal&&mode!=='linear')cancelLinearCorrection();
 if(measurementViewMode==='linear'&&mode!=='linear')savedLinearJobRate=String(el('jobPrice')?.value??'').trim()===''?'':currentJobPrice();
 // Preserve the area price entered in the main job-rate field before switching to linear.
 // Combined Pressure Washing estimates use a separate area-rate field.
 if(currentBusinessType()==='pressure'&&measurementViewMode==='area'&&mode==='linear'&&areaMeasurementSaved&&el('pressureAreaRate')&&Number(el('pressureAreaRate').value||0)===0){el('pressureAreaRate').value=String(el('jobPrice')?.value??'').trim()===''?'':String(currentJobPrice());}
 // The visible Area price is authoritative when switching to Linear.
 // Never retain a stale default area rate from an earlier quote.
 if(currentBusinessType()==='paving'&&measurementViewMode==='area'&&mode==='linear'&&el('pavingAreaRate')){el('pavingAreaRate').value=String(el('jobPrice')?.value??'').trim()===''?'':String(currentJobPrice());}
 if(currentBusinessType()==='landscaping'&&measurementViewMode==='area'&&mode==='linear'&&el('landscapingAreaRate')){el('landscapingAreaRate').value=String(el('jobPrice')?.value??'').trim()===''?'':String(currentJobPrice());}
 if(currentBusinessType()==='paving'&&measurementViewMode==='linear'&&mode==='area'&&el('pavingAreaRate')&&el('jobPrice')){el('jobPrice').value=el('pavingAreaRate').value;}
 if(currentBusinessType()==='landscaping'&&measurementViewMode==='linear'&&mode==='area'&&el('landscapingAreaRate')&&el('jobPrice')){el('jobPrice').value=el('landscapingAreaRate').value;}
 if(surfaceIndustry()&&mode==='linear'&&measurementViewMode!=='linear'&&linearMeasurementSaved&&savedLinearJobRate!==null&&currentBusinessType()!=='commercial'&&el('jobPrice'))el('jobPrice').value=String(savedLinearJobRate);
 pendingMeasurementMode=mode;measurementViewMode=mode;updatePropertyActionButton();updateMeasurementInterface();
 // Before a property is loaded, choosing a tool only sets the intended workflow.
 if(!sessionToken){status(mode==='area'?'Area Measure selected. Enter the property and load it to start measuring.':mode==='linear'?'Linear Measure selected. Enter the property and load it to start measuring.':'AutoMeasure selected. Enter the property and load it to measure the roof.','ok');return}
 if(mode==='auto'){if(areaMode)areaMode=false;if(linearMode)linearMode=false;clearAreaLayers();clearLinearLayers();restoreAutoMeasureDisplay();updateAreaUi();updateLinearUi();updateMeasurementInterface();renderSummary();status('AutoMeasure view selected. Saved Area and Linear measurements are still available.','ok');return}
 if(mode==='area'){if(linearMode)linearMode=false;hideRoofDisplayForLinear();if(linearMeasurementSaved&&linearPoints.length>=2)redrawLinearMeasure();else clearLinearLayers();if(areaMeasurementSaved&&areaPoints.length>=3){redrawAreaMeasure();updateMeasurementInterface();updateAreaUi();renderSummary();status(surfaceIndustry()?'Saved areas are in this job. Use ADD AREA for another section or EDIT OUTLINE on a saved area.':'Saved area selected. Click CONTINUE AREA MEASURE only if you need to edit it.','ok');return}updateMeasurementInterface();updateAreaUi();renderSummary();if(!areaMode)toggleAreaMeasure();return}
 if(mode==='linear'){if(areaMode){areaMode=false;areaMeasurementSaved=areaPoints.length>=3||areaMeasurementSaved;}hideRoofDisplayForLinear();if(multiAreaSaved()){commercialSyncCurrent();clearAreaLayers();commercialAreaDrawSaved()}else clearAreaLayers();if(linearMeasurementSaved&&linearPoints.length>=2){redrawLinearMeasure();updateMeasurementInterface();updateLinearUi();renderSummary();status(surfaceIndustry()?'Saved line is in this job. Use EDIT LINE to move its points.':'Saved linear measurement selected. Click CONTINUE LINEAR MEASURE only to edit it.','ok');return}updateMeasurementInterface();updateLinearUi();renderSummary();if(!linearMode)toggleLinearMeasure();return}
}
function linearFeetTotal(){let total=0;for(let i=1;i<linearPoints.length;i++)total+=map.distance(linearPoints[i-1],linearPoints[i])*3.28084;return total}
// Keep the aerial fixed for saved line/polygon corrections, preserving prior dragging.
// Touch zoom remains independent; do not disable Leaflet's two-finger zoom handler.
function syncMeasurementEditMapDragging(){
 // Rapid replacement taps must place corners, not trigger Leaflet double-tap zoom.
 if(map.doubleClickZoom){
  if(typeof areaRemeasureMode!=='undefined'&&areaRemeasureMode){
   if(map._aqRemeasureDoubleClick===undefined)map._aqRemeasureDoubleClick=map.doubleClickZoom.enabled();
   map.doubleClickZoom.disable();
  }else if(map._aqRemeasureDoubleClick!==undefined){
   if(map._aqRemeasureDoubleClick)map.doubleClickZoom.enable();
   delete map._aqRemeasureDoubleClick;
  }
 }
 const polygonEditing=!!areaCorrectionOriginal||roofOutlineReviewMode||(traceMode&&manualRoofEditIndex!==null);
 map.getContainer().classList.toggle('polygon-correcting',polygonEditing);
 map.getContainer().classList.toggle('linear-correcting',!!linearCorrectionOriginal);
 if(linearCorrectionOriginal||polygonEditing){
  if(measurementMapDraggingWasEnabled===null)measurementMapDraggingWasEnabled=map.dragging.enabled();
  map.dragging.disable();
 }else if(measurementMapDraggingWasEnabled!==null){
  if(measurementMapDraggingWasEnabled)map.dragging.enable();
  measurementMapDraggingWasEnabled=null;
 }
}
function updateLinearUi(){syncMeasurementEditMapDragging();const editing=!!linearCorrectionOriginal;if(el('linearEditBtn'))el('linearEditBtn').style.display=linearMeasurementSaved&&linearPoints.length>=2&&!linearMode&&!editing?'inline-block':'none';['linearSaveEditBtn','linearCancelEditBtn'].forEach(id=>{if(el(id))el(id).style.display=editing?'inline-block':'none'});if(el('linearStartBtn'))el('linearStartBtn').style.display=editing?'none':'inline-block';if(el('linearClearBtn'))el('linearClearBtn').disabled=editing;if(el('linearAutoBtn'))el('linearAutoBtn').disabled=editing;const total=linearFeetTotal(),surfaceOnly=['commercial','paving','pressure','landscaping','snow'].includes(currentBusinessType());if(el('linearTotal'))el('linearTotal').textContent=`Total: ${total.toFixed(1)} ft`;if(el('linearUndoBtn'))el('linearUndoBtn').style.display=linearMode&&linearPoints.length?'inline-block':'none';if(el('linearClearBtn'))el('linearClearBtn').style.display=(linearMode||measurementViewMode==='linear')&&linearPoints.length?'inline-block':'none';if(el('linearAutoBtn'))el('linearAutoBtn').style.display=!surfaceOnly&&measurementViewMode==='linear'?'inline-block':'none';if(el('linearHelp'))el('linearHelp').innerHTML=editing?'<b>Edit Line ON.</b> Drag the teal corner points, then Save Line Changes or Cancel Line Edit.':linearMode?(linearPoints.length?`<b>Linear Measure ON.</b> ${linearPoints.length} point${linearPoints.length===1?'':'s'} placed â€¢ Total <b>${total.toFixed(1)} ft</b>. Keep clicking to continue the run.`:'<b>Linear Measure ON.</b> Click the first point, then each turn or endpoint.'):(measurementViewMode==='linear'&&linearPoints.length?`<b>âœ“ Linear measurement saved: ${total.toFixed(1)} ft.</b> Continue measuring or select another measurement tool above.`:(linearPoints.length?`Saved linear measurement â€¢ <b>${total.toFixed(1)} ft</b>.`:'Click Start Linear Measure for a clean aerial workspace.'));document.body.classList.toggle('linear-active',linearMode);syncSurfaceMeasurementControls()}
function clearLinearLayers(){linearLayers.forEach(x=>{try{map.removeLayer(x)}catch(e){}});linearLayers=[]}
function redrawLinearMeasure(){clearLinearLayers();linearPoints.forEach((pt,i)=>{const dot=L.marker(pt,{draggable:!!linearCorrectionOriginal,interactive:!!linearCorrectionOriginal,autoPan:false,icon:L.divIcon({className:'',html:'<div class="linear-point"></div>',iconAnchor:[6,6]})}).addTo(map);if(linearCorrectionOriginal)dot.on('dragend',()=>{linearPoints[i]=dot.getLatLng();redrawLinearMeasure();renderSummary()});linearLayers.push(dot);if(i>0){const a=linearPoints[i-1],b=pt,feet=map.distance(a,b)*3.28084;const line=L.polyline([a,b],{color:'#0f8f83',weight:5,opacity:.95,lineCap:'round'}).addTo(map);linearLayers.push(line);const mid=L.latLng((a.lat+b.lat)/2,(a.lng+b.lng)/2);const lab=L.marker(mid,{interactive:false,icon:L.divIcon({className:'',html:`<div class="linear-seg-label">${feet.toFixed(1)} ft</div>`,iconAnchor:[24,9]})}).addTo(map);linearLayers.push(lab)}});updateLinearUi()}
function editLinearMeasure(){
 if(!sessionToken||!linearMeasurementSaved||linearPoints.length<2||linearMode)return;
 if(areaMode){status('Finish and save the area outline before editing the line.','warn');return}
 if(measurementViewMode!=='linear')selectMeasurementTool('linear');
 linearCorrectionOriginal=linearPoints.map(p=>L.latLng(p.lat,p.lng));
 redrawLinearMeasure();renderSummary();status('EDIT LINE ON â€” drag the teal points, then SAVE LINE CHANGES or CANCEL LINE EDIT.','warn');
}
function saveLinearCorrection(){
 if(!linearCorrectionOriginal)return;
 const issue=savedLinearGeometryError();if(issue){status(issue,'error');return}
 linearCorrectionOriginal=null;linearMeasurementSaved=true;redrawLinearMeasure();renderSummary();status(`LINE CHANGES SAVED â€” ${linearFeetTotal().toFixed(1)} ft.`,'ok');
}
function cancelLinearCorrection(){
 if(!linearCorrectionOriginal)return;
 linearPoints=linearCorrectionOriginal.map(p=>L.latLng(p.lat,p.lng));linearCorrectionOriginal=null;linearMeasurementSaved=true;redrawLinearMeasure();renderSummary();status('Line edit cancelled; original line restored.','ok');
}
function clearManualDisplayLayers(){manualLayers.forEach(x=>{try{map.removeLayer(x)}catch(e){}});manualLayers=[]}
function redrawManualDisplayLayers(){clearManualDisplayLayers();manualPlanes.forEach((plane,i)=>{const poly=L.polygon(plane.points,{color:'#d97706',weight:5,fillColor:'#f59e0b',fillOpacity:.12,lineJoin:'round'}).addTo(map),c=poly.getBounds().getCenter(),lab=L.marker(c,{interactive:false,icon:L.divIcon({className:'',html:`<div class="manual-label">M${i+1} â€¢ ${Number(plane.pitch_degrees||0).toFixed(1)}Â° â€¢ ${fmt(plane.surface_sqft)} ftÂ²</div>`,iconAnchor:[65,10]})}).addTo(map);manualLayers.push(poly,lab);drawEdgeMeasurements(plane.points,'#d97706',map,manualLayers,true)})}
function hideRoofDisplayForLinear(){clearOverlays();clearManualDisplayLayers();if(clickMarker){try{map.removeLayer(clickMarker)}catch(e){}clickMarker=null}}
function restoreAutoMeasureDisplay(){redrawRoofData();redrawManualDisplayLayers()}
function stopLinearMode(restoreRoof=false){linearMode=false;if(el('linearStartBtn')){el('linearStartBtn').textContent='START LINEAR MEASURE';el('linearStartBtn').className='secondary'}if(restoreRoof){measurementViewMode='auto';restoreAutoMeasureDisplay()}updateLinearUi()}
function returnToAutoMeasure(){if(linearMode&&linearPoints.length&&!linearCorrectionOriginal){status('Finish and save or clear the current line before returning to AutoMeasure.','warn');return}linearMode=false;measurementViewMode='auto';linearMeasurementSaved=linearPoints.length>1;if(el('linearStartBtn')){el('linearStartBtn').textContent='START LINEAR MEASURE';el('linearStartBtn').className='secondary'}restoreAutoMeasureDisplay();updateLinearUi();renderSummary();status('AutoMeasure restored. Your saved linear measurement is still available.','ok')}
function toggleLinearMeasure(){if(surfaceIndustry()&&!linearMode&&!linearCorrectionOriginal&&measurementViewMode!=='linear'){selectMeasurementTool('linear');if(measurementViewMode!=='linear')return}if(surfaceIndustry()&&!linearMode&&!linearCorrectionOriginal&&sessionToken)surfaceLineDraftOriginal={points:linearPoints.map(p=>({lat:p.lat,lng:p.lng})),saved:linearMeasurementSaved,savedRate:savedLinearJobRate,jobRate:el('jobPrice')?.value};if(linearCorrectionOriginal){saveLinearCorrection();return}if(!sessionToken){status('Load the property first.','error');return}if(areaMode){areaMode=false;if(multiAreaSaved())commercialSyncCurrent();clearAreaLayers();commercialAreaDrawSaved();updateAreaUi()}if(linearMode){const issue=savedLinearGeometryError();if(issue){status(issue,'error');return}linearMode=false;if(!linearMeasurementSaved)usage.linear++;linearMeasurementSaved=true;surfaceLineDraftOriginal=null;measurementViewMode='linear';if(el('linearStartBtn')){el('linearStartBtn').textContent='CONTINUE LINEAR MEASURE';el('linearStartBtn').className='secondary'}hideRoofDisplayForLinear();redrawLinearMeasure();updateLinearUi();renderSummary();status(`LINEAR MEASUREMENT SAVED â€” ${linearFeetTotal().toFixed(1)} ft. ${currentBusinessType()==='roofing'?'AutoMeasure remains hidden until you return to it.':'You can continue measuring or create the estimate.'}`,'ok');return}if(traceMode)cancelCurrentTrace();if(outlineEditMode){outlineEditMode=false;outlinePoints=[];clearOutlineTemp();setOutlineButtons(false)}roofFixMode=false;locateRoofMode=false;garageMode=false;measurementViewMode='linear';linearMeasurementSaved=false;hideRoofDisplayForLinear();linearMode=true;if(el('linearStartBtn')){el('linearStartBtn').textContent='FINISH & SAVE LINEAR';el('linearStartBtn').className='primary'}updateLinearUi();renderSummary();status(currentBusinessType()==='roofing'?'LINEAR MEASURE ON â€” roof overlays are hidden. Click the first point, then each turn or endpoint.':'LINEAR MEASURE ON â€” click the first point, then each turn or endpoint.','warn')}
function addLinearPoint(ll){linearPoints.push(L.latLng(ll.lat,ll.lng));redrawLinearMeasure();if(linearPoints.length===1)status('Start point set. Click the next point.','warn');else status(`Linear total: ${linearFeetTotal().toFixed(1)} ft.`,'ok')}
function undoLinearPoint(){if(!linearPoints.length)return;linearPoints.pop();redrawLinearMeasure();status(linearPoints.length?`Last point removed. Linear total: ${linearFeetTotal().toFixed(1)} ft.`:'Linear measurement cleared.','ok')}
function clearLinearMeasure(){linearCorrectionOriginal=null;linearPoints=[];linearMeasurementSaved=false;clearLinearLayers();updateLinearUi();renderSummary();status('Linear measurement cleared.','ok')}
function measuredPolygonError(points){
 const bad='Place at least three distinct corners around an area before saving.';
 if(!Array.isArray(points)||points.length<3||points.some(p=>!Number.isFinite(p.lat)||!Number.isFinite(p.lng)||Math.abs(p.lat)>90||Math.abs(p.lng)>180))return bad;
 const origin=points[0],scale=6378137*Math.PI/180,cos=Math.cos(origin.lat*Math.PI/180),eps=1e-7;
 const xy=[];for(const p of points){const q={x:((p.lng-origin.lng+540)%360-180)*scale*cos,y:(p.lat-origin.lat)*scale};const last=xy[xy.length-1];if(!last||Math.hypot(q.x-last.x,q.y-last.y)>eps)xy.push(q);}
 if(xy.length>1&&Math.hypot(xy[0].x-xy[xy.length-1].x,xy[0].y-xy[xy.length-1].y)<=eps)xy.pop();
 if(xy.length<3)return bad;
 const turn=(a,b,c)=>(b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x);
 const on=(a,b,c)=>Math.abs(turn(a,b,c))<=eps&&c.x>=Math.min(a.x,b.x)-eps&&c.x<=Math.max(a.x,b.x)+eps&&c.y>=Math.min(a.y,b.y)-eps&&c.y<=Math.max(a.y,b.y)+eps;
 for(let i=0;i<xy.length;i++)for(let j=i+1;j<xy.length;j++){
  if(j===i+1||(i===0&&j===xy.length-1))continue;
  const a=xy[i],b=xy[(i+1)%xy.length],c=xy[j],d=xy[(j+1)%xy.length],abC=turn(a,b,c),abD=turn(a,b,d),cdA=turn(c,d,a),cdB=turn(c,d,b);
  if((abC*abD<0&&cdA*cdB<0)||on(a,b,c)||on(a,b,d)||on(c,d,a)||on(c,d,b))return 'This outline crosses itself. Follow the outside boundary in order, then save again.';
 }
 let area=0;for(let i=0;i<xy.length;i++){const b=xy[(i+1)%xy.length];area+=xy[i].x*b.y-b.x*xy[i].y;}
 return Math.abs(area)<1e-6?bad:'';
}
function localPolygonAreaM2(points){if(points.length<3)return 0;const R=6378137,origin=points[0],lat0=points.reduce((a,p)=>a+p.lat,0)/points.length*Math.PI/180,xy=points.map(p=>({x:R*((p.lng-origin.lng+540)%360-180)*Math.PI/180*Math.cos(lat0),y:R*((p.lat-origin.lat)*Math.PI/180)}));let a=0;for(let i=0;i<xy.length;i++){const j=(i+1)%xy.length;a+=xy[i].x*xy[j].y-xy[j].x*xy[i].y}return Math.abs(a)/2}
function setTraceControls(active){['tracePitchControl','finishTrace','undoTraceBtn','clearManualBtn'].forEach(id=>{if(el(id))el(id).style.display=active?'':'none'})}
function tracedRoofContains(roof,latitude,longitude){
 if(!roof.manually_measured||!Array.isArray(roof.outline))return false;
 let inside=false;const pts=roof.outline;
 for(let i=0,j=pts.length-1;i<pts.length;j=i++){const a=pts[i],b=pts[j];if((a[0]>latitude)!==(b[0]>latitude)&&longitude<(b[1]-a[1])*(latitude-a[0])/(b[0]-a[0])+a[1])inside=!inside}
 return inside;
}
function manualTracesForRoof(roof){
 const boundary=roof?.detected_outline||roof?.outline;
 if(!roof||!Array.isArray(boundary)||boundary.length<3)return [];
 const contains=(points,lat,lng)=>{let inside=false;for(let i=0,j=points.length-1;i<points.length;j=i++){const a=points[i],b=points[j],ay=a.lat??a[0],ax=a.lng??a[1],by=b.lat??b[0],bx=b.lng??b[1];if((ay>lat)!==(by>lat)&&lng<(bx-ax)*(lat-ay)/(by-ay)+ax)inside=!inside}return inside};
 const centre=points=>({lat:points.reduce((n,p)=>n+(p.lat??p[0]),0)/points.length,lng:points.reduce((n,p)=>n+(p.lng??p[1]),0)/points.length});
 const bc=centre(boundary);
 return manualPlanes.map((plane,index)=>({plane,index})).filter(({plane})=>{if(!Array.isArray(plane.points)||plane.points.length<3)return false;const pc=centre(plane.points);return contains(boundary,pc.lat,pc.lng)&&(contains(plane.points,roof.latitude,roof.longitude)||contains(plane.points,bc.lat,bc.lng))}).map(x=>x.index);
}
function roofReviewActionLabel(roof){return roof.manually_measured?'REVIEW SAVED OUTLINE & PITCH':manualTracesForRoof(roof).length?'REVIEW LATEST MANUAL TRACE & PITCH':'REVIEW DETECTED OUTLINE & PITCH'}
function detectedRoofReviewOutline(roof){
 if(!roof)return null;
 const matches=manualTracesForRoof(roof);
 const outline=roof.manually_measured?roof.outline:matches.length?manualPlanes[matches[matches.length-1]].points.map(p=>[p.lat,p.lng]):roof.detected_outline||roof.outline;
 if(!Array.isArray(outline)||outline.length<3||outline.some(p=>!Array.isArray(p)||p.length<2||!Number.isFinite(p[0])||!Number.isFinite(p[1])))return null;
 const points=outline.map(p=>L.latLng(p[0],p[1]));
 return measuredPolygonError(points)?null:points;
}
function roofMeasurementSourceLabel(roof){return roof.measurement_source==='dealer_reviewed_detected_outline'?'Dealer-reviewed detected outline â€¢ verified uniform pitch':roof.measurement_source==='dealer_reviewed_trace'?'Dealer-reviewed manual trace â€¢ verified uniform pitch':'Dealer traced â€¢ confirmed pitch'}
function reviewedRoofPitch(){
 const choice=el('roofReviewPitchSelect')?.value;
 if(!choice)return NaN;
 const raw=choice==='custom'?el('roofReviewPitchDeg')?.value:choice;
 return raw===undefined||String(raw).trim()===''?NaN:Number(raw);
}
function reviewedRoofPitchChanged(){
 if(!roofOutlineReviewMode)return;
 if(el('roofReviewPitchDeg'))el('roofReviewPitchDeg').style.display=el('roofReviewPitchSelect').value==='custom'?'':'none';
 updateReviewedRoofUi();
}
function invalidateReviewedRoofConfirmations(){
 if(el('roofReviewBoundaryConfirmed'))el('roofReviewBoundaryConfirmed').checked=false;
}
function updateReviewedRoofUi(){
 syncMeasurementEditMapDragging();
 if(!roofOutlineReviewMode)return;
 const problem=measuredPolygonError(tracePoints),pitch=reviewedRoofPitch(),validPitch=Number.isFinite(pitch)&&pitch>=0&&pitch<80;
 const ground=problem?0:localPolygonAreaM2(tracePoints)*10.76391041671;
 if(el('roofReviewDraft'))el('roofReviewDraft').textContent=problem?problem:'Draft footprint: '+fmt(ground)+' ftÂ².'+(validPitch?' Draft roof area at selected pitch: '+fmt(ground/Math.cos(pitch*Math.PI/180))+' ftÂ².':' Select a verified pitch to calculate roof area.')+' Not saved or included in the estimate.';
 if(el('finishTrace'))el('finishTrace').disabled=!!problem||!validPitch||!el('roofReviewBoundaryConfirmed')?.checked||(roofReviewManualIndices.length>0&&!el('roofReviewReplaceManualConfirmed')?.checked);
}
function redrawReviewedRoofPoints(){
 clearTempTrace();
 tracePoints.forEach((point,index)=>{
  const marker=L.marker(point,{draggable:true,autoPan:false,icon:L.divIcon({className:'',html:'<div class="point-label">'+(index+1)+'</div>',iconAnchor:[12,12]})}).addTo(map);
  marker._roofReviewVertex=index;
  marker.on('dragend',()=>{tracePoints[index]=marker.getLatLng();invalidateReviewedRoofConfirmations();redrawTraceLine();updateReviewedRoofUi();status('Outline changed. Check its complete boundary and pitch again before saving.','warn')});
  tempTraceLayers.push(marker);
 });
 redrawTraceLine();updateReviewedRoofUi();
}
function startDetectedRoofReview(index){
 const roof=structures[index],reuseDraft=traceMode&&roofRemeasureTarget===roof&&!roofOutlineReviewMode;
 const points=reuseDraft?tracePoints.map(p=>L.latLng(p.lat,p.lng)):detectedRoofReviewOutline(roof);
 if(!points||measuredPolygonError(points)){status('No usable boundary is available. Finish the trace or use Remeasure This Roof.','warn');return}
 if(measureClicked.pending||(traceMode&&!reuseDraft)||areaMode||linearMode||outlineEditMode){status('Finish or cancel the current measurement before reviewing a roof.','warn');return}
 const matches=manualTracesForRoof(roof),source=reuseDraft||roof.manually_measured||matches.length?'trace':'detected';
 if(reuseDraft)cancelCurrentTrace();
 startRoofRemeasure(index);if(roofRemeasureTarget!==roof)return;
 if(el('manualRoofSaveFeedback'))el('manualRoofSaveFeedback').remove();
 roofOutlineReviewMode=true;roofReviewBoundarySource=source;roofReviewManualIndices=matches;tracePoints=points.map(p=>L.latLng(p.lat,p.lng));
 el('roofRemeasurePitch').innerHTML='<div class="warning"><b>Detected outline â€” requires your review.</b><br>This outline is not a verified whole-building measurement. Check every edge against the aerial. This method uses ONE uniform pitch across the entire selected outline. If slopes differ, cancel this review; this shortcut cannot measure mixed pitches.</div><label for="roofReviewPitchSelect">Verified uniform roof pitch</label><select id="roofReviewPitchSelect" onchange="reviewedRoofPitchChanged()"><option value="">Select verified pitch</option>'+[0,1,2,3,4,5,6,7,8,9,10,11,12].map(r=>'<option value="'+(Math.atan(r/12)*180/Math.PI)+'">'+r+'/12'+(r===0?' (flat)':'')+'</option>').join('')+'<option value="custom">Custom degrees</option></select><input id="roofReviewPitchDeg" type="number" min="0" max="79.9" step="0.1" placeholder="Verified pitch in degrees" aria-label="Verified pitch in degrees" style="display:none" oninput="reviewedRoofPitchChanged()"><label style="display:flex;gap:8px;align-items:center"><input id="roofReviewBoundaryConfirmed" type="checkbox" style="width:auto" onchange="updateReviewedRoofUi()">I checked every edge. This outline covers exactly the intended building roof, with no ground or neighbouring roofs included.</label><div id="roofReviewDraft" class="small"></div>';
 if(source==='trace'){
  const warning=el('roofRemeasurePitch').querySelector('.warning');warning.innerHTML='<b>Review your latest roof boundary.</b><br>Your latest manual trace is used, not the original detected outline. Check every edge. This method uses ONE verified uniform pitch. If slopes differ, cancel; this shortcut cannot measure mixed pitches.';
 }
 if(matches.length){const notice=document.createElement('label');notice.style.display='block';notice.innerHTML='<input id="roofReviewReplaceManualConfirmed" type="checkbox" style="width:auto" onchange="updateReviewedRoofUi()"> Replace these overlapping saved manual traces with this ONE reviewed roof when I save: '+matches.map(i=>'M'+(i+1)+' ('+fmt(manualPlanes[i].surface_sqft)+' ftÂ²)').join(', ')+'. Cancel keeps them unchanged.';el('roofRemeasurePitch').append(notice)}
 el('manualRoofHelp').textContent='Drag the numbered corners to correct this roof boundary. Use START OVER to draw a new boundary. The original roof stays unchanged until you save.';
 el('tracePitchControl').style.display='none';el('undoTraceBtn').style.display='none';el('clearManualBtn').style.display='';
 el('traceBtn').textContent='CANCEL OUTLINE REVIEW';el('finishTrace').textContent='SAVE REVIEWED ROOF & PITCH';el('traceBanner').textContent='REVIEW '+roof.label+' â€” check outline and verified uniform pitch';
 clearManualDisplayLayers();redrawRoofData();redrawReviewedRoofPoints();map.fitBounds(L.latLngBounds(tracePoints),{padding:[45,45],maxZoom:20});
 status('Review the detected outline and verify one uniform pitch. The estimate remains blocked until both are confirmed and saved.','warn');renderSummary();
}
function replacementPitchIsChosen(){const pitch=Number(el('pitchDeg').value);return !!el('pitchSel').value&&String(el('pitchDeg').value).trim()!==''&&Number.isFinite(pitch)&&pitch>=0&&pitch<80}
function updateManualReplacementUi(message=''){
 if(!roofRemeasureTarget||roofOutlineReviewMode)return;
 const row=el('traceBtn').closest('.manualrow');row.classList.add('roof-replacement-row');
 let feedback=el('manualRoofSaveFeedback');if(!feedback){feedback=document.createElement('div');feedback.id='manualRoofSaveFeedback';feedback.setAttribute('role','status');feedback.setAttribute('aria-live','polite');row.insertBefore(feedback,el('finishTrace'))}
 const issue=measuredPolygonError(tracePoints),confirmed=replacementPitchIsChosen();
 el('finishTrace').disabled=!!issue||!confirmed;
 feedback.style.display='block';feedback.textContent=message||(issue?'Step 1: trace at least three roof corners in boundary order.':!confirmed?'Step 2: select the roof pitch above, then save. No separate confirmation checkbox is required.':'Ready: click SAVE REPLACEMENT ROOF. This replaces only '+roofRemeasureTarget.label+'.');
}
function startRoofRemeasure(index){
 const roof=structures[index];if(!sessionToken||!roof)return;
 if(traceMode&&roofRemeasureTarget===roof)cancelCurrentTrace();
 if(measureClicked.pending||traceMode||areaMode||linearMode||outlineEditMode){status('Finish or cancel the current measurement before remeasuring a roof.','warn');return}
 garageMode=false;roofFixMode=false;locateRoofMode=false;measurementViewMode='auto';
 toggleTrace(true);roofRemeasureTarget=roof;clearManualDisplayLayers();redrawRoofData();
 const correctionBoundary=detectedRoofReviewOutline(roof);
 if(correctionBoundary)map.fitBounds(L.latLngBounds(correctionBoundary),{padding:[45,45],maxZoom:20,animate:false});
 else if(Number.isFinite(roof.latitude)&&Number.isFinite(roof.longitude))map.setView([roof.latitude,roof.longitude],19,{animate:false});
 const details=el('manualRoofDetails');if(details)details.open=true;
 let confirm=el('roofRemeasurePitch');if(!confirm){confirm=document.createElement('div');confirm.id='roofRemeasurePitch';confirm.className='small';confirm.style.padding='10px 12px';el('manualRoofHelp').after(confirm)}
 el('traceBtn').closest('.manualrow').insertBefore(confirm,el('finishTrace'));
 confirm.style.display='block';confirm.textContent='Area is calculated using the selected pitch. The starting pitch is 5/12; change it if needed. Different slopes require separate roof sections.';el('pitchSel').value='22.62';el('pitchDeg').value='22.62';el('pitchDeg').type='hidden';
 el('manualRoofHelp').textContent='Remeasuring '+roof.label+'. Trace the intended roof boundary. The existing area stays unchanged until you save.';
 if(el('manualPitchLabel'))el('manualPitchLabel').childNodes[0].nodeValue='Roof pitch â€” defaults to 5/12; change if needed ';el('finishTrace').textContent='SAVE REPLACEMENT ROOF';el('traceBanner').textContent='REMEASURE '+roof.label+' â€” trace roof, confirm pitch, then save';
 updateManualReplacementUi();
 status('Remeasure '+roof.label+': trace its boundary, change the default 5/12 pitch if needed, then save. This replaces only this roof.','warn');
 renderSummary();
 el('manualRoofDetails')?.scrollIntoView?.({block:'start',behavior:'smooth'});
}
function finishRoofRemeasure(points,pitch,surface){
 const original=roofRemeasureTarget,index=structures.indexOf(original);
 if(index<0){status('The selected roof changed. Cancel and select it again.','error');return}
 if(roofOutlineReviewMode&&!el('roofReviewBoundaryConfirmed')?.checked){status('Check the complete roof boundary, then tick its confirmation before saving.','warn');return}
 if(!roofOutlineReviewMode&&!replacementPitchIsChosen()){updateManualReplacementUi('Save blocked: select the roof pitch above, then click SAVE REPLACEMENT ROOF.');status('Select the roof pitch before saving the replacement.','warn');return}
 if(roofOutlineReviewMode&&roofReviewManualIndices.length&&!el('roofReviewReplaceManualConfirmed')?.checked){status('Confirm which overlapping manual traces this reviewed roof replaces before saving.','warn');return}
 if(!Number.isFinite(surface)||surface<=0){status('Trace a roof with a positive area before saving.','error');return}
 const outline=points.map(p=>[p.lat,p.lng]),bounds=L.latLngBounds(outline),c=bounds.getCenter();
 structures[index]={label:original.label,building_id:original.building_id,latitude:c.lat,longitude:c.lng,total_roof_sqft:surface,segment_count:1,segments:[{pitch_degrees:pitch,area_sqft:surface,center:{latitude:c.lat,longitude:c.lng}}],outline,manually_measured:true,measurement_source:roofOutlineReviewMode?(roofReviewBoundarySource==='trace'?'dealer_reviewed_trace':'dealer_reviewed_detected_outline'):'dealer_trace',pitch_confirmed:true,...(roofOutlineReviewMode?{boundary_confirmed:true,uniform_pitch_confirmed:true,reviewed_ground_sqft:localPolygonAreaM2(points)*10.76391041671,previous_automatic_review:original.automatic_review}:{}),previous_automatic_area_sqft:original.automatic_roof_sqft??original.previous_automatic_area_sqft??original.total_roof_sqft};
 if(index===0)adjustedOutline=null;
 if(roofOutlineReviewMode&&roofReviewManualIndices.length)manualPlanes=manualPlanes.filter((_,i)=>!roofReviewManualIndices.includes(i));
 if(el('measureSource'))el('measureSource').value=manualPlanes.length?'hybrid':'google';
 delete reportOutlines['structure-'+index];cancelCurrentTrace();setManualUi(false);redrawRoofData();renderSummary();
 const remaining=structures.filter(s=>s.needs_remeasure||s.automatic_review_warning).length;
 if(el('garageGuide'))el('garageGuide').textContent=original.label+' remeasured â€” '+fmt(surface)+' ftÂ² included. '+(remaining?'Other roofs still need remeasurement; check the Property Summary.':'To include another roof, click + ADD GARAGE / OTHER ROOF.');
 if(el('garageSavedConfirm'))el('garageSavedConfirm').style.display='none';
 if(clickMarker){try{map.removeLayer(clickMarker)}catch(e){}clickMarker=null}clicked=null;
 status(original.label+' remeasured â€” '+fmt(surface)+' ftÂ² replaces the previous area. Roof count is unchanged.','ok');
}
function manualRoofPitchLabel(deg){return Number(deg)===0?'0/12 (flat)':pitchRiseLabel(deg)}
function manualRoofInvalidateScope(){if(el('manualRoofScopeConfirmed'))el('manualRoofScopeConfirmed').checked=false}
function manualRoofGeometryError(planes){
 const areas=planes.map(p=>{const points=(p.points||[]).map(v=>[Number(v.lat??v[0]),Number(v.lng??v[1])]);return{points,sqft:localPolygonAreaM2(points.map(v=>({lat:v[0],lng:v[1]})))*10.76391041671}});
 // Check incomplete candidates as well, before the shared validator filters zero areas.
 if(areas.some(a=>measuredPolygonError(a.points.map(v=>({lat:v[0],lng:v[1]})))))return 'Roof section outline is incomplete or invalid.';
 return savedAreaGeometryError(areas).replaceAll('service area','roof section');
}
function pricedRoofGeometryError(snapshot){
 if(!snapshot||snapshot.businessType!=='roofing'||snapshot.measurementMode!=='auto')return '';
 const source=snapshot.measureSource||'google';if(!['google','manual','hybrid'].includes(source))return '';
 // Existing incomplete-roof safeguards retain their specific repair instructions.
 if((snapshot.structures||[]).some(r=>r.needs_remeasure||r.automatic_review_warning))return '';
 try{
  const roofs=(snapshot.structures||[]).map(r=>({points:r.outline||[]})),planes=(snapshot.manualPlanes||[]).map(p=>({points:p.points||[]}));
  const included=source==='manual'?(planes.length?planes:roofs):source==='hybrid'?roofs.concat(planes):roofs;
  return manualRoofGeometryError(included);
 }catch(e){return 'Roof measurement snapshot is incomplete or invalid. Review the saved measurements before quoting.'}
}
function beginManualRoofSection(){
 if(!sessionToken){status('Load the property first.','warn');return}
 if(traceMode){status('Save or cancel the current roof section first.','warn');return}
 if(linearMode||linearCorrectionOriginal){status('Save or cancel the line first.','warn');return}
 measurementViewMode='auto';pendingMeasurementMode='auto';clearLinearLayers();redrawManualDisplayLayers();
 manualRoofEditIndex=null;toggleTrace();renderSummary();
}
function editManualRoofSection(index){
 if(!manualRoofQa()||traceMode||!manualPlanes[index])return;
 beginManualRoofSection();manualRoofEditIndex=index;syncMeasurementEditMapDragging();
 const points=manualPlanes[index].points.map(p=>L.latLng(p.lat??p[0],p.lng??p[1]));
 points.forEach(addTracePoint);clearTempTrace();
 tracePoints.forEach((p,i)=>{const marker=L.marker(p,{draggable:true}).addTo(map);marker.on('dragend',()=>{tracePoints[i]=marker.getLatLng();redrawTraceLine();manualRoofInvalidateScope()});tempTraceLayers.push(marker)});
 redrawTraceLine();el('finishTrace').textContent='SAVE SECTION CHANGES';
 status('Drag corners or start over to correct this section. Confirm its pitch before saving. Cancel preserves the saved section.','ok');
}
function deleteManualRoofSection(index){
 if(!manualRoofQa()||traceMode||!manualPlanes[index])return;
 manualPlanes.splice(index,1);manualRoofInvalidateScope();redrawManualDisplayLayers();renderSummary();
}
function syncManualRoofQa(){
 if(el('pitchSel')&&!el('pitchSel').querySelector('option[value="0"]')){const o=document.createElement('option');o.value='0';o.textContent='0/12 â€” Flat';el('pitchSel').append(o)}
 if(el('pitchReminder'))el('pitchReminder').textContent='Confirm the actual pitch of this section before saving. Different pitches require separate sections.';
 for(const id of ['toolAutoBtn','areaAutoBtn','linearAutoBtn','roofCheckCard','advancedOptions'])if(el(id))el(id).style.display='none';
 if(el('toolAreaBtn')){if(el('toolAreaBtn').querySelector('b'))el('toolAreaBtn').querySelector('b').textContent='TRACE ROOF';el('toolAreaBtn').disabled=traceMode}
 if(el('toolLinearBtn'))el('toolLinearBtn').disabled=traceMode;
 if(el('propertyActionBtn'))el('propertyActionBtn').textContent='LOAD PROPERTY';
 const details=el('manualRoofDetails');if(details){const anchor=details._roofWorkspaceAnchor;if(anchor&&details.parentNode!==anchor.parentNode)anchor.parentNode.insertBefore(details,anchor.nextSibling);details.open=true}
 if(el('manualRoofSummary'))el('manualRoofSummary').textContent='Trace roof sections â†’ Confirm pitches â†’ Review estimate';
 if(el('garageControls'))el('garageControls').style.display='none';
 if(el('garageGuide'))el('garageGuide').textContent='Load the property, then trace the main house and any other included roofs.';
 if(el('manualRoofWarning'))el('manualRoofWarning').textContent='Trace each roof section with its actual pitch. Include the main house and any garages or other roofs you are quoting.';
 if(el('manualRoofHelp')&&traceMode)el('manualRoofHelp').textContent='Trace one roof section with a single pitch. Confirm its pitch before saving. Add other slopes and garages separately.';
 if(el('traceBtn'))el('traceBtn').textContent=traceMode?'CANCEL SECTION':'ADD ROOF SECTION / GARAGE';
 let panel=el('manualRoofSections');if(!panel){panel=document.createElement('div');panel.id='manualRoofSections';details.after(panel)}
 const confirmed=!!el('manualRoofScopeConfirmed')?.checked;
 panel.replaceChildren();
 manualPlanes.forEach((p,i)=>{const row=document.createElement('div');row.className='structure';const text=document.createElement('span');text.textContent='Roof section '+(i+1)+' Â· '+fmt(p.surface_sqft)+' ftÂ² Â· '+manualRoofPitchLabel(p.pitch_degrees)+' pitch ';row.append(text);for(const [label,fn] of [['EDIT',editManualRoofSection],['DELETE',deleteManualRoofSection]]){const b=document.createElement('button');b.type='button';b.textContent=label;b.disabled=traceMode;b.onclick=()=>fn(i);row.append(b)}panel.append(row)});
 // Retain the persisted confirmation field for saved drafts; the visible action is a button.
 const check=document.createElement('input');check.type='checkbox';check.id='manualRoofScopeConfirmed';check.checked=confirmed;check.hidden=true;check.style.display='none';panel.append(check);
 const confirmation=document.createElement('div');confirmation.className=confirmed?'good':'warning';confirmation.style.cssText='margin:10px 0;padding:14px;border:2px solid '+(confirmed?'#2f7d44':'#b86b00');
 const title=document.createElement('strong');title.textContent=confirmed?'âœ“ Pitches and included roofs confirmed':'Roof confirmation required';confirmation.append(title);
 const help=document.createElement('p');help.style.margin='8px 0';help.textContent=confirmed?'Saved section pitches and included roofs are confirmed. Editing, adding or deleting a section requires confirmation again.':'Review the pitch shown beside every saved section. Edit any incorrect pitch, include every roof you are quoting, then select â€œConfirm pitches and included roofsâ€ to continue.';confirmation.append(help);
 const action=document.createElement('button');action.id='confirmRoofPitches';action.type='button';action.className='primarybig';action.textContent=confirmed?'âœ“ Pitches and included roofs confirmed':'Confirm pitches and included roofs';action.setAttribute('aria-pressed',String(confirmed));action.disabled=confirmed||traceMode||!manualPlanes.length||manualPlanes.some(p=>!p.pitch_confirmed||!Number.isFinite(Number(p.pitch_degrees))||Number(p.pitch_degrees)<0||Number(p.pitch_degrees)>=80)||!!manualRoofGeometryError(manualPlanes);action.onclick=()=>{check.checked=true;renderSummary()};confirmation.append(action);panel.append(confirmation);
}
function toggleTrace(forReplacement=false){if(manualRoofQa()&&!traceMode){el('pitchSel').value='';el('pitchDeg').value='';manualRoofInvalidateScope()}if(!traceMode&&!forReplacement&&structures.some(st=>st.needs_remeasure||st.automatic_review_warning)){status('To correct a flagged roof, use FIX ROOF in its Property Summary row. This keeps the replacement linked to that roof instead of adding another measurement.','warn');return}if(traceMode){cancelCurrentTrace();renderSummary();status('Manual trace cancelled.','ok');return}if(linearMode)stopLinearMode(false);const mainManual=(manualOverrideMode||fallbackMode)&&structures.length===0&&manualPlanes.length===0;setManualUi(mainManual);traceMode=true;tracePoints=[];clearTempTrace();setTraceControls(true);if(el('manualRoofHelp'))el('manualRoofHelp').innerHTML=mainManual?'Trace the MAIN HOUSE only.':'Trace only the garage or other roof you want to add. The main house stays unchanged.';if(!window.sgPitchReminderShown&&el('pitchReminder')){el('pitchReminder').style.display='block';window.sgPitchReminderShown=true;setTimeout(()=>{if(el('pitchReminder'))el('pitchReminder').style.display='none'},7000)}el('traceBtn').textContent='CANCEL TRACE';el('traceBtn').className='danger';el('traceBanner').style.display='block';el('finishTrace').disabled=true;status(mainManual?'Manual measurement ON â€” click the outside corners of the MAIN HOUSE.':'Added-roof trace ON â€” click the outside corners of the garage or other roof.','warn');syncRoofWorkspace()}
function addTracePoint(ll){if(roofOutlineReviewMode){status('Drag the numbered corners to correct this outline. Cancel and use Remeasure This Roof to draw a different boundary.','warn');return}tracePoints.push(ll);let n=tracePoints.length,pt=L.marker(ll,{interactive:false,icon:L.divIcon({className:'',html:`<div class="point-label">${n}</div>`,iconAnchor:[12,12]})}).addTo(map);tempTraceLayers.push(pt);redrawTraceLine();const ready=tracePoints.length>=3;el('finishTrace').disabled=!ready;if(ready){const action=roofRemeasureTarget?'SAVE REPLACEMENT ROOF':((manualOverrideMode||fallbackMode)&&structures.length===0&&manualPlanes.length===0)?'FINISH MEASUREMENT':'SAVE & ADD ROOF';if(el('manualRoofHelp'))el('manualRoofHelp').innerHTML=`<b>âœ“ Roof traced.</b> Confirm the pitch, then click <b>${action}</b>.`;status('Roof traced â€” confirm pitch, then save.','ok')}updateManualReplacementUi()}
function redrawTraceLine(){tempTraceLayers.filter(x=>x._traceLine).forEach(x=>map.removeLayer(x));tempTraceLayers=tempTraceLayers.filter(x=>!x._traceLine);if(tracePoints.length>=2){let c=[...tracePoints];if(tracePoints.length>=3)c.push(tracePoints[0]);let l=L.polyline(c,{color:'#d97706',weight:4,dashArray:'6,5'}).addTo(map);l._traceLine=true;tempTraceLayers.push(l)}}
function clearTempTrace(){tempTraceLayers.forEach(x=>{try{map.removeLayer(x)}catch(e){}});tempTraceLayers=[];if(traceSavePopup){try{map.closePopup(traceSavePopup)}catch(e){}traceSavePopup=null}}
function cancelCurrentTrace(){if(manualRoofQa())manualRoofEditIndex=null;el('traceBtn')?.closest('.manualrow')?.classList.remove('roof-replacement-row');if(el('manualRoofSaveFeedback'))el('manualRoofSaveFeedback').remove();const restoreRoofDisplay=!!roofRemeasureTarget;if(restoreRoofDisplay){el('pitchSel').value='22.62';el('pitchDeg').value='22.62';el('pitchDeg').type='hidden'}roofOutlineReviewMode=false;roofReviewBoundarySource='detected';roofReviewManualIndices=[];roofRemeasureTarget=null;if(el('roofRemeasurePitch'))el('roofRemeasurePitch').style.display='none';traceMode=false;tracePoints=[];clearTempTrace();setTraceControls(false);const mainManual=(manualOverrideMode||fallbackMode)&&structures.length===0&&manualPlanes.length===0;el('traceBtn').textContent=mainManual?'START MAIN HOUSE MEASUREMENT':'ADD / REMEASURE GARAGE OR OTHER ROOF';el('traceBtn').className='orange';el('traceBanner').style.display='none';el('finishTrace').textContent=mainManual?'FINISH MEASUREMENT':'SAVE & ADD ROOF';el('finishTrace').disabled=true;if(restoreRoofDisplay){redrawRoofData();redrawManualDisplayLayers();renderSummary()}syncRoofWorkspace()}
function undoPoint(){if(!traceMode||!tracePoints.length)return;let keep=tracePoints.slice(0,-1);tracePoints=[];clearTempTrace();keep.forEach(addTracePoint)}
function finishTrace(){
 if(manualRoofQa()){
  if(!replacementPitchIsChosen()){status('Select and confirm the pitch for this section before saving.','warn');return}
  const candidates=manualPlanes.filter((_,i)=>i!==manualRoofEditIndex).concat([{points:tracePoints}]);
  const issue=manualRoofGeometryError(candidates);if(issue){status(issue,'error');return}
 }
 const problem=measuredPolygonError(tracePoints);if(problem){updateManualReplacementUi(problem);status(problem,'error');return}
 let pitch=roofOutlineReviewMode?reviewedRoofPitch():roofRemeasureTarget&&!replacementPitchIsChosen()?NaN:Number(el('pitchDeg').value||0);
 if(!Number.isFinite(pitch)||pitch<0||pitch>=80){updateManualReplacementUi('Select the roof pitch above before saving.');status('Select a roof pitch from 0 to less than 80 degrees before saving.','warn');return}
 let flat=localPolygonAreaM2(tracePoints),surface=flat/Math.cos(pitch*Math.PI/180)*10.76391041671;
 if(roofRemeasureTarget){finishRoofRemeasure(tracePoints,pitch,surface);return}
 let plane={points:tracePoints.map(p=>({lat:p.lat,lng:p.lng})),pitch_degrees:pitch,surface_sqft:surface};
 if(manualRoofQa()){
  plane.pitch_confirmed=true;plane.manual_roof_qa=true;
  if(manualRoofEditIndex!==null){manualPlanes[manualRoofEditIndex]=plane;manualRoofEditIndex=null;cancelCurrentTrace();redrawManualDisplayLayers();renderSummary();status('Roof section changes saved.','ok');return}
 }
 manualPlanes.push(plane);
 let poly=L.polygon(plane.points,{color:'#d97706',weight:5,fillColor:'#f59e0b',fillOpacity:.12,lineJoin:'round'}).addTo(map),
     c=poly.getBounds().getCenter(),
     lab=L.marker(c,{interactive:false,icon:L.divIcon({className:'',html:`<div class="manual-label">M${manualPlanes.length} â€¢ ${pitch.toFixed(1)}Â° â€¢ ${fmt(surface)} ftÂ²</div>`,iconAnchor:[65,10]})}).addTo(map);
 manualLayers.push(poly,lab);drawEdgeMeasurements(plane.points,'#d97706',map,manualLayers,true);
 cancelCurrentTrace();
 const pureManual=structures.length===0;
 if(el('measureSource'))el('measureSource').value=pureManual?'manual':'hybrid';
 renderSummary();
 if(pureManual&&manualPlanes.length===1){setManualCorrectionLayout(false);setManualUi(false);if(el('garageGuide'))el('garageGuide').innerHTML='<b>Main house measured manually.</b> If there is another building to include, click <b>+ ADD GARAGE / OTHER ROOF</b>.';if(el('measureClickedTop'))el('measureClickedTop').disabled=false;if(el('measureClicked'))el('measureClicked').disabled=false;}
 status(pureManual?`âœ“ MANUAL ROOF SAVED â€” ${fmt(manualTotal())} ftÂ² total. Add another roof if needed.`:`âœ“ MISSING ROOF ADDED â€” ${fmt(surface)} ftÂ² added. New estimate area: ${fmt(googleTotal()+manualTotal())} ftÂ².`,'ok');
}
function deleteLastPlane(){
 if(!manualPlanes.length)return;
 manualPlanes.pop();
 redrawManualDisplayLayers();
 if(el('measureSource'))el('measureSource').value=manualPlanes.length?(structures.length?'hybrid':'manual'):(structures.length?'google':'manual');
 renderSummary();
}
function clearManual(){
 if(roofOutlineReviewMode&&roofRemeasureTarget){startRoofRemeasure(structures.indexOf(roofRemeasureTarget));return}
 const mainStage=(manualOverrideMode||fallbackMode)&&structures.length===0&&manualPlanes.length===0;
 if(traceMode){tracePoints=[];clearTempTrace();if(el('finishTrace'))el('finishTrace').disabled=true;updateManualReplacementUi();status(mainStage?'Main-house drawing cleared. Click the roof corners again.':'Added-roof drawing cleared. The saved main house and other roofs were not changed.','ok');return}
 if(mainStage){status('Start the main-house trace first, then CLEAR MAIN HOUSE OUTLINE will clear the points you are drawing.','warn');return}
 status('No added-roof drawing is active. Your saved roof measurements were not changed.','ok');
}
function manualTotal(){return manualPlanes.reduce((a,p)=>a+Number(p.surface_sqft||0),0)}
function googleTotal(){return structures.reduce((a,s)=>a+Number(s.total_roof_sqft||0),0)}
function estimateArea(){
 let src=el('measureSource')?el('measureSource').value:'google';
 if(src==='hybrid')return googleTotal()+manualTotal();
 if(src==='manual')return manualTotal()||googleTotal();
 if(src==='adjusted')return Number(el('adjustedArea').value||0)||googleTotal();
 return googleTotal();
}
function estimatePeriodValue(value=el('estimatePeriod')?.value,industry=currentBusinessType()){
 if(!['snow','landscaping','commercial'].includes(industry))return 'one_time';
 return ['one_time','visit','snowfall','month','season','year'].includes(value)?value:'one_time';
}
function estimatePeriodSuffix(value){return ({visit:' per visit',snowfall:' per snowfall',month:' per month',season:' per season',year:' per year'})[value]||''}
function updateEstimatePeriodUi(){
 const enabled=['snow','landscaping','commercial'].includes(currentBusinessType());
 if(el('estimatePeriodWrap'))el('estimatePeriodWrap').style.display=enabled?'block':'none';
 const period=estimatePeriodValue(),suffix=estimatePeriodSuffix(period);
 if(!quotePricingError()){
  el('summary')?.querySelectorAll('.line.grand span:last-child').forEach(n=>{n.textContent=n.textContent.replace(/ per (visit|snowfall|month|season|year)$/,'')+suffix});
  const total=el('jsTotal');if(total&&total.textContent.startsWith('$'))total.textContent=total.textContent.replace(/ per (visit|snowfall|month|season|year)$/,'')+suffix;
 }
}
function savedLinearGeometryError(points=linearPoints,expectedFeet=null){
 if(!Array.isArray(points)||points.length<2)return 'Add at least two different points.';
 const pts=points.map(p=>Array.isArray(p)?p:[p?.lat,p?.lng]);
 if(pts.some(p=>p.length!==2||p.some(v=>typeof v!=='number'||!Number.isFinite(v))||Math.abs(p[0])>90||Math.abs(p[1])>180))return 'Invalid measurement coordinates.';
 const [lat,lon]=pts[0],scale=6378137*Math.PI/180,xy=pts.map(([a,b])=>[(((b-lon+180)%360+360)%360-180)*scale*Math.cos(lat*Math.PI/180),(a-lat)*scale]),segments=[];
 for(let i=1;i<xy.length;i++){
  const a=xy[i-1],b=xy[i],dx=b[0]-a[0],dy=b[1]-a[1],length=Math.hypot(dx,dy);
  if(length<.0003048)return 'The line has a zero-length edge. Move the repeated point or Undo.';
  for(const [c,d] of segments){
   if(Math.max(...[c,d].map(p=>Math.abs(dx*(p[1]-a[1])-dy*(p[0]-a[0]))/length))>1e-6)continue;
   const [lo,hi]=[c,d].map(p=>((p[0]-a[0])*dx+(p[1]-a[1])*dy)/length).sort((x,y)=>x-y);
   if(Math.min(length,hi)-Math.max(0,lo)>1e-6)return 'Linear segments overlap and count the same length twice. Correct the line before quoting.';
  }segments.push([a,b]);
 }
 if(expectedFeet!==null){
  let measured=0;for(let i=1;i<pts.length;i++){const a=pts[i-1],b=pts[i],rad=Math.PI/180,h=Math.sin((b[0]-a[0])*rad/2)**2+Math.cos(a[0]*rad)*Math.cos(b[0]*rad)*Math.sin((b[1]-a[1])*rad/2)**2;measured+=2*6371000*Math.asin(Math.min(1,Math.sqrt(h)))*3.28084;}
  if(!Number.isFinite(expectedFeet)||expectedFeet<=0||Math.abs(measured-expectedFeet)>Math.max(.05,measured*.00001))return 'Saved linear quantity does not match its line. Remeasure before quoting.';
 }return '';
}
function savedAreaGeometryError(inputAreas=commercialAreas){
 const areas=inputAreas.filter(a=>Number(a.sqft)>0);
 const inside=(p,poly)=>{let hit=false;for(let i=0,j=poly.length-1;i<poly.length;j=i++){const a=poly[j],b=poly[i],cross=(b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]);if(Math.abs(cross)<1e-16&&p[0]>=Math.min(a[0],b[0])-1e-12&&p[0]<=Math.max(a[0],b[0])+1e-12&&p[1]>=Math.min(a[1],b[1])-1e-12&&p[1]<=Math.max(a[1],b[1])+1e-12)return false;if((a[1]>p[1])!==(b[1]>p[1])&&p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0])hit=!hit}return hit};
 const cross=(a,b,c)=>(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
 for(let i=0;i<areas.length;i++){
  const a=areas[i],points=(a.points||[]).map(p=>({lat:p[0],lng:p[1]}));
  if(measuredPolygonError(points))return 'Saved service area outline is invalid. Remeasure before quoting.';
  const actual=localPolygonAreaM2(points)*10.76391041671;
  if(Math.abs(actual-Number(a.sqft))>Math.max(1,actual*.001))return 'Saved service area quantity does not match its outline. Remeasure before quoting.';
  for(const b of areas.slice(0,i)){
   let overlap=false;const origin=a.points[0][1],project=points=>points.map(p=>[p[0],(p[1]-origin+540)%360-180]),aa=project(a.points),bb=project(b.points);
   for(let j=0;j<aa.length;j++)for(let k=0;k<bb.length;k++){const p=aa[j],q=aa[(j+1)%aa.length],r=bb[k],t=bb[(k+1)%bb.length];if(cross(p,q,r)*cross(p,q,t)<-1e-28&&cross(r,t,p)*cross(r,t,q)<-1e-28)overlap=true}
   for(const [poly,other] of [[aa,bb],[bb,aa]]){const samples=poly.concat(poly.map((p,j)=>[(p[0]+poly[(j+1)%poly.length][0])/2,(p[1]+poly[(j+1)%poly.length][1])/2]));const center=[poly.reduce((n,p)=>n+p[0],0)/poly.length,poly.reduce((n,p)=>n+p[1],0)/poly.length];if(inside(center,poly))samples.push(center);for(let k=0;k<poly.length;k++){const p=poly[k],q=poly[(k+1)%poly.length],length=Math.hypot(q[0]-p[0],q[1]-p[1]);if(length)for(const side of [-1,1]){const near=[(p[0]+q[0])/2+side*(q[1]-p[1])/length*1e-9,(p[1]+q[1])/2-side*(q[0]-p[0])/length*1e-9];if(inside(near,poly))samples.push(near)}}if(samples.some(p=>inside(p,other)))overlap=true}
   if(overlap)return 'Saved service areas overlap. Correct the outlines before quoting to avoid counting coverage twice.';
  }
 }
 return '';
}
function quotePricingError(calc=null){
 if(typeof pricedRoofGeometryError==='function'){const issue=pricedRoofGeometryError({businessType:currentBusinessType(),measurementMode:measurementViewMode,measureSource:el('measureSource')?.value||'google',structures,manualPlanes});if(issue)return issue;}
 if(typeof manualRoofQa==='function'&&manualRoofQa()&&measurementViewMode==='auto'){
  if(traceMode)return 'Save or cancel the roof section before creating the estimate.';
  if(manualPlanes.length&&manualPlanes.some(p=>p.manual_roof_qa)&&!el('manualRoofScopeConfirmed')?.checked)return 'Review each saved roof sectionâ€™s pitch, then select â€œConfirm pitches and included roofsâ€ beside the saved sections to continue.';
 }
 if(typeof propertyAddressNeedsReload==='function'&&propertyAddressNeedsReload())return 'The address has changed. Your previous measurements are retained. Load the new property before creating an estimate.';
 if(linearMeasurementSaved){const issue=savedLinearGeometryError();if(issue)return issue;}
 const valid=(value,max=Infinity)=>value!==null&&value!==undefined&&String(value).trim()!==''&&Number.isFinite(Number(value))&&Number(value)>=0&&Number(value)<=max;
 for(const id of ['gst','pst'])if(!valid(el(id)?.value,100))return 'Enter a tax percentage from 0 to 100. Enter 0 when no tax is charged.';
 if(el('pricingMode')?.value==='discount'&&!valid(el('discountPct')?.value,100))return 'Enter a promotion discount from 0 to 100%.';
 const extra=el('extraServiceAmount')?.value;if(String(extra??'').trim()!==''&&!valid(extra))return 'Enter an additional-services amount of 0 or more.';
 if(['commercial','paving','pressure','landscaping','snow'].includes(currentBusinessType())&&commercialAreas.some(a=>!Number.isFinite(Number(a.sqft))||Number(a.sqft)<=0))return 'Finish saving or cancel the unfinished service area before creating an estimate.';
 const savedAreas=savedSurfaceHasAreas()||(currentBusinessType()==='commercial'&&commercialHasAreas());
 if(savedAreas&&commercialAreas.some(a=>a.sqft>0&&!valid(a.rate)))return 'Enter a rate of 0 or more for every saved service area.';
 if(currentBusinessType()==='commercial'){
  if(commercialHasLinear()&&!valid(el('commercialLinearRate')?.value))return 'Enter a linear service rate of 0 or more.';
  if(!savedAreas&&!commercialHasLinear()&&!valid(el('jobPrice')?.value))return 'Enter this jobâ€™s rate. Use 0 only for an intentionally free service.';
 }else{
  if((!savedAreas||measurementViewMode==='linear')&&!valid(el('jobPrice')?.value))return 'Enter this jobâ€™s rate. Use 0 only for an intentionally free service.';
  if(savedAreas&&linearMeasurementSaved&&!valid(surfaceLinearJobRate()))return 'Enter a linear service rate of 0 or more.';
  for(const [combined,id] of [[landscapingCombined(),'landscapingAreaRate'],[pressureCombined(),'pressureAreaRate'],[pavingCombined(),'pavingAreaRate']])if(combined&&!savedAreas&&!valid(el(id)?.value))return 'Enter an area service rate of 0 or more.';
 }
 const geometryIssue=savedAreaGeometryError();if(geometryIssue)return geometryIssue;
 const totals=calc||priceCalc();
 if(['subtotal','extraAmount','taxBase','gstAmt','pstAmt','total'].some(key=>!Number.isFinite(totals[key])||totals[key]<0))return 'Review the prices and taxes. The estimate must have valid, non-negative amounts.';
 return '';
}
function updateQuotePricingValidation(calc){
 const issue=quotePricingError(calc),label=/Confirm pitches and included roofs/.test(issue)?'Roof confirmation required':/outline|overlap|quantity/.test(issue)?'Measurement review required':'Price required';let box=el('quotePricingError');
 if(!box){box=document.createElement('div');box.id='quotePricingError';box.className='warning';box.setAttribute('role','alert');el('createEstimateBtn')?.before(box)}
 box.textContent=issue;box.style.display=issue?'block':'none';
 if(issue){
  if(el('createEstimateBtn'))el('createEstimateBtn').disabled=true;
  if(el('jsTotal'))el('jsTotal').textContent=label;
  el('summary')?.querySelectorAll('.price-summary,.estimate').forEach(preview=>{preview.innerHTML='<h3>'+label+'</h3><div class="warning">'+escapeHistory(issue)+'</div>'});
 }
}
function currentJobPrice(){const jp=el('jobPrice');const raw=jp?jp.value:'';const v=parseFloat(raw);if(Number.isFinite(v)&&v>=0)return v;const fallback=parseFloat((el('price')&&el('price').value)||0);return Number.isFinite(fallback)&&fallback>=0?fallback:0}
function priceCalc(){const currencyAmount=value=>Math.round((Number(value)+Number.EPSILON)*100)/100;if(commercialActive()&&areaMeasurementSaved)commercialSyncCurrent();let linearActive=measurementViewMode==='linear',areaActive=measurementViewMode==='area',area=linearActive?linearFeetTotal():(areaActive?(multiAreaSaved()?multiAreaTotal():Math.round(areaSqFtTotal())):estimateArea()),price=currentJobPrice(),mode=el('pricingMode').value,disc=Number(el('discountPct').value||0),gst=Number(el('gst').value||0),pst=Number(el('pst').value||0),subtotal=(savedSurfaceHasAreas()?landscapingAreaSubtotal()+(linearMeasurementSaved&&linearPoints.length>1?linearFeetTotal()*surfaceLinearJobRate():0):currentBusinessType()==='commercial'&&(commercialHasAreas()||commercialHasLinear())?commercialAreas.reduce((sum,a)=>sum+(a.sqft||0)*(a.rate||0),0)+(commercialHasLinear()?linearFeetTotal()*commercialLinearRate():0):landscapingCombined()?Math.round(multiAreaSaved()?multiAreaTotal():areaSqFtTotal())*landscapingAreaRate()+linearFeetTotal()*price:pressureCombined()?Math.round(multiAreaSaved()?multiAreaTotal():areaSqFtTotal())*pressureAreaRate()+linearFeetTotal()*price:pavingCombined()?Math.round(multiAreaSaved()?multiAreaTotal():areaSqFtTotal())*pavingAreaRate()+linearFeetTotal()*price:area*price),extraDescription=(el('extraServiceDescription')?.value||'').trim(),extraAmount=Math.max(0,Number(el('extraServiceAmount')?.value||0)),discount=0,taxBase=subtotal+extraAmount,gstAmt=0,pstAmt=0,total=0;let charges=[];if(savedSurfaceHasAreas()||(currentBusinessType()==='commercial'&&(commercialHasAreas()||commercialHasLinear()))){charges=commercialAreas.filter(a=>a.sqft>0).map(a=>currencyAmount(Number(a.sqft)*Number(a.rate)));if(linearMeasurementSaved&&linearPoints.length>1)charges.push(currencyAmount(linearFeetTotal()*(currentBusinessType()==='commercial'?commercialLinearRate():surfaceLinearJobRate())))}else if(landscapingCombined()||pressureCombined()||pavingCombined()){const areaRate=landscapingCombined()?landscapingAreaRate():pressureCombined()?pressureAreaRate():pavingAreaRate();charges=[currencyAmount(Math.round(multiAreaSaved()?multiAreaTotal():areaSqFtTotal())*areaRate),currencyAmount(linearFeetTotal()*price)]}else charges=[currencyAmount(area*price)];subtotal=currencyAmount(charges.reduce((n,v)=>n+v,0));taxBase=currencyAmount(subtotal+extraAmount);if(mode==='discount'){discount=currencyAmount(subtotal*(disc/100));taxBase=currencyAmount(subtotal-discount+extraAmount);gstAmt=currencyAmount(taxBase*gst/100);pstAmt=currencyAmount(taxBase*pst/100);total=currencyAmount(taxBase+gstAmt+pstAmt)}else if(mode==='included'){total=currencyAmount(subtotal+extraAmount);taxBase=currencyAmount(total/(1+(gst+pst)/100));gstAmt=currencyAmount(taxBase*gst/100);pstAmt=currencyAmount(taxBase*pst/100);taxBase=currencyAmount(total-gstAmt-pstAmt)}else{taxBase=currencyAmount(subtotal+extraAmount);gstAmt=currencyAmount(taxBase*gst/100);pstAmt=currencyAmount(taxBase*pst/100);total=currencyAmount(taxBase+gstAmt+pstAmt)}if(multiAreaSaved())area=multiAreaTotal();return{estimatePeriod:estimatePeriodValue(),area,price,mode,disc,subtotal,extraDescription,extraAmount,discount,taxBase,gst,pst,gstAmt,pstAmt,total,measurementMode:linearActive?'linear':(areaActive?'area':'auto'),unit:(commercialHasAreas()||savedSurfaceHasAreas())?'ftÂ²':(linearActive?'linear ft':'ftÂ²')}}
function roofQuoteNeedsReview(){return currentBusinessType()==='roofing'&&measurementViewMode==='auto'&&structures.some(st=>st.needs_remeasure||st.automatic_review_warning)}
function confidence(){if(structures.some(st=>st.needs_remeasure))return ['An automatic roof is incomplete. Remeasure it before creating the estimate.'];return structures.some(st=>st.automatic_review_warning)?['Roof area and outline may cover different scopes. Remeasure the flagged roof before creating an estimate; confirming its location or editing its picture does not verify its area.']:[]}
function pitchLabel(deg){const d=Number(deg||0);if(!d)return 'â€”';const rise=12*Math.tan(d*Math.PI/180);const rounded=Math.round(rise*2)/2;return `${d.toFixed(1)}Â° (approx. ${Number.isInteger(rounded)?rounded.toFixed(0):rounded.toFixed(1)}/12)`}
function pitchRiseLabel(deg){const d=Number(deg||0);if(!d)return 'â€”';const rise=12*Math.tan(d*Math.PI/180);const rounded=Math.round(rise*2)/2;return `${Number.isInteger(rounded)?rounded.toFixed(0):rounded.toFixed(1)}/12`}
function structurePitchSummary(st){if(!st||!st.segments||!st.segments.length)return {complex:false,label:'â€”',detail:''};const vals=st.segments.map(x=>Number(x.pitch_degrees||0)).filter(x=>x>0);if(!vals.length)return {complex:false,label:'â€”',detail:''};const avg=vals.reduce((a,b)=>a+b,0)/vals.length,min=Math.min(...vals),max=Math.max(...vals);const rises=[...new Set(vals.map(pitchRiseLabel))];const complex=vals.length>=6&&(max-min>=8||rises.length>=3);if(complex)return {complex:true,label:'Multiple Roof Pitches',detail:`${pitchRiseLabel(min)}â€“${pitchRiseLabel(max)} (${min.toFixed(1)}Â°â€“${max.toFixed(1)}Â°)`};return {complex:false,label:pitchLabel(avg),detail:`${st.manually_measured?'Confirmed pitch from':'Average of'} ${vals.length} ${st.manually_measured?'traced':'Google'} roof segment${vals.length===1?'':'s'}`}}
function updateJobSummaryBar(calc,roofCount){
 const p=el('jsProperty'),r=el('jsRoofs'),a=el('jsArea'),t=el('jsTotal');if(!p||!r||!a||!t)return;
 const full=(el('address')&&el('address').value?el('address').value:'').trim();
 const typed=[el('streetAddress')?.value,el('cityTown')?.value,el('propertyProvince')?.value].filter(Boolean).join(', ');
 p.textContent=full||typed||'No property loaded';
 const has=calc&&Number(calc.area)>0;
 const summaryLabel=r.previousElementSibling;if(summaryLabel&&['pressure','paving','landscaping','commercial','snow'].includes(currentBusinessType()))summaryLabel.textContent=currentBusinessType()==='landscaping'?'SERVICE AREAS':'SURFACES';else if(summaryLabel)summaryLabel.textContent='ROOFS';
 r.textContent=['pressure','paving','landscaping','commercial','snow'].includes(currentBusinessType())?(multiAreaSaved()?String(commercialAreas.filter(a=>a.sqft>0).length):(areaMeasurementSaved&&areaPoints.length>=3?'1':'â€”')):(has?String(roofCount||1):'â€”');
 const savedSurfaceArea=multiAreaSaved()?multiAreaTotal():(areaMeasurementSaved&&areaPoints.length>=3?Math.round(areaSqFtTotal()):0);
 const savedLinearLength=linearMeasurementSaved&&linearPoints.length>=2?linearFeetTotal():0;
 a.textContent=savedSurfaceArea>0?fmt(savedSurfaceArea)+' ftÂ²'+(savedLinearLength>0?' â€¢ '+savedLinearLength.toFixed(1)+' linear ft':''):(measurementViewMode==='linear'&&savedLinearLength>0?savedLinearLength.toFixed(1)+' linear ft':has?fmt(calc.area)+' ftÂ²':'â€”');
 if(surfaceIndustry()&&(areaMode||linearMode||linearCorrectionOriginal)){a.textContent=savedSurfaceArea>0?fmt(savedSurfaceArea)+' ftÂ² saved':'Unsaved drawing';t.textContent='Save measurement';return}
 if(roofQuoteNeedsReview()){a.textContent='Unverified roof area';t.textContent='Review required';return}
 t.textContent=has?money(calc.total):'â€”';
}
function updateProgressSteps(){
 const measured=priceCalc().area>0&&!roofQuoteNeedsReview()&&(!surfaceIndustry()||(!areaMode&&!linearMode&&!linearCorrectionOriginal&&(areaMeasurementSaved||multiAreaSaved()||linearMeasurementSaved)));
 const verified=!!(el('propertyVerify')&&el('propertyVerify').style.display!=='none'&&(el('propertyVerify').textContent||'').includes('verified'));
 const customerReady=!!((el('customerName')?.value||'').trim());
 const estimateOpen=document.body.classList.contains('report-open');
 let current=1;if(verified)current=2;if(measured)current=3;if(measured&&customerReady)current=5;if(estimateOpen)current=5;
 for(let i=1;i<=5;i++){const c=el('progress'+i);if(!c)continue;c.classList.remove('done','current');const n=c.querySelector('.stepnum');if(i<current){c.classList.add('done');if(n)n.textContent='âœ“'}else if(i===current){c.classList.add('current');if(n)n.textContent=String(i)}else{if(n)n.textContent=String(i)}}
 // Price is complete once a valid measured quote exists; Customer becomes current before Estimate.
 if(measured&&!customerReady){const p3=el('progress3'),p4=el('progress4');if(p3){p3.classList.add('done');p3.classList.remove('current');const n=p3.querySelector('.stepnum');if(n)n.textContent='âœ“'}if(p4){p4.classList.add('current');const n=p4.querySelector('.stepnum');if(n)n.textContent='4'}}
}
function updatePriceUnitUi(){const linear=measurementViewMode==='linear';if(el('jobPriceCard'))el('jobPriceCard').style.display=surfaceIndustry()&&((measurementViewMode==='area'&&!areaMode&&multiAreaSaved())||(currentBusinessType()==='commercial'&&linear))?'none':'';if(el('jobPriceLabel'))el('jobPriceLabel').innerHTML=linear?'Price for This Job / linear ft. <span class="info-tip" tabindex="0" data-tip="Set the price charged for each linear foot measured.">â“˜</span>':'Price for This Job / sq. ft. <span class="info-tip" tabindex="0" data-tip="Your dealer default loads here automatically. Change this number for any individual job and the quote recalculates immediately.">â“˜</span>';if(el('jobPriceHelp'))el('jobPriceHelp').textContent=linear?'This price is multiplied by the saved linear footage for this job.':'This is the price used for the quote. Change it anytime before creating the estimate.';}
let activationRecorded=false,activationRecording=false;
function recordFirstMeasurement(){
 if(activationRecorded||activationRecording||!sessionToken||document.body.classList.contains('report-open')||quoteSnapshot?.savedPricing)return;
 let kind='',amount=0;
 if(linearMeasurementSaved&&linearPoints.length>=2){kind='linear';amount=linearFeetTotal()}
 else if(multiAreaSaved()||areaMeasurementSaved&&areaPoints.length>=3){kind='area';amount=multiAreaSaved()?multiAreaTotal():areaSqFtTotal()}
 else if(structures.length||manualPlanes.length){kind='roof';amount=googleTotal()+manualTotal()}
 if(!(amount>0))return;
 activationRecording=true;
 fetch('/api/account/activation',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:sessionToken,kind,amount})}).then(r=>{if(r.ok)activationRecorded=true}).catch(()=>{}).finally(()=>{activationRecording=false});
}
function renderSummary(){try{recordFirstMeasurement();updateMeasurementInterface();if(currentBusinessType()==='paving'&&!el('pavingAreaRate')){const anchor=el('summary');if(anchor){const d=document.createElement('div');d.id='pavingAreaPriceBox';d.innerHTML='<label for="pavingAreaRate">Paving area rate ($ / sq. ft.)</label> <input id="pavingAreaRate" type="number" min="0" step="0.01" value="0" oninput="if(measurementViewMode===\'area\'&&el(\'jobPrice\'))el(\'jobPrice\').value=this.value;renderSummary()">';anchor.parentNode.insertBefore(d,anchor)}}if(el('pavingAreaPriceBox'))el('pavingAreaPriceBox').style.display=currentBusinessType()==='paving'&&measurementViewMode==='linear'&&!savedSurfaceHasAreas()?'block':'none';if(currentBusinessType()==='pressure'&&!el('pressureAreaRate')){const anchor=el('summary');if(anchor){const d=document.createElement('div');d.id='pressureAreaPriceBox';d.innerHTML='<label for="pressureAreaRate"><b>Pressure Washing area service rate ($ / sq. ft.)</b></label> <input id="pressureAreaRate" type="number" min="0" step="0.01" value="0" placeholder="Enter rate" style="width:105px;padding:7px" oninput="renderSummary()"><div class="small">Set your area rate. When area and linear measurements are both saved, both services are included in the estimate.</div>';anchor.parentNode.insertBefore(d,anchor)}}if(el('pressureAreaPriceBox'))el('pressureAreaPriceBox').style.display=currentBusinessType()==='pressure'&&measurementViewMode==='linear'&&!savedSurfaceHasAreas()?'block':'none';if(currentBusinessType()==='landscaping'&&!el('landscapingAreaRate')){const anchor=el('summary');if(anchor){const d=document.createElement('div');d.id='landscapingAreaPriceBox';d.innerHTML='<label for="landscapingAreaRate"><b>Landscaping area service rate ($ / sq. ft.)</b></label> <input id="landscapingAreaRate" type="number" min="0" step="0.01" value="0.15" style="width:105px;padding:7px" oninput="if(measurementViewMode===\'area\'&&el(\'jobPrice\'))el(\'jobPrice\').value=this.value;renderSummary()"><div class="small">When area and linear measurements are both saved, the area rate and linear job rate are added together.</div>';anchor.parentNode.insertBefore(d,anchor)}}if(el('landscapingAreaPriceBox'))el('landscapingAreaPriceBox').style.display=currentBusinessType()==='landscaping'&&measurementViewMode==='linear'&&!savedSurfaceHasAreas()?'block':'none';if(currentBusinessType()==='commercial'&&!el('commercialLinearRate')){const anchor=el('summary');if(anchor){const d=document.createElement('div');d.id='commercialLinearPriceBox';d.innerHTML='<label for="commercialLinearRate"><b>Commercial linear service rate ($ / linear ft)</b></label> <input id="commercialLinearRate" type="number" min="0" step="0.01" value="0.25" style="width:105px;padding:7px" oninput="renderSummary()"><div class="small">Saved linear and area measurements are combined on one commercial estimate.</div>';anchor.parentNode.insertBefore(d,anchor)}}if(el('commercialLinearPriceBox'))el('commercialLinearPriceBox').style.display=currentBusinessType()==='commercial'?'block':'none';if(commercialActive())commercialAreaUi();if(!el('summary'))return;updatePriceUnitUi();let g=googleTotal(),m=manualTotal(),coverage=Number(el('coverage').value||330),src=el('measureSource')?el('measureSource').value:'google',calc=priceCalc(),gallons=coverage?calc.area/coverage:0;let pureManual=src==='manual'&&m>0,hasMeasurement=calc.area>0,roofCount=pureManual?manualPlanes.length:structures.length+(src==='hybrid'?manualPlanes.length:0);if(measurementViewMode==='area'){const ready=areaMeasurementSaved&&areaPoints.length>=3&&calc.area>0&&(!commercialActive()||commercialAreas.every(a=>a.sqft>0));if(el('createEstimateBtn'))el('createEstimateBtn').disabled=!ready;updateJobSummaryBar(calc,1);let html=`<div class="measure-result-card"><div class="measure-result-head"><div><div class="measure-result-title">Area Measurement</div><div class="measure-result-value">${fmt(calc.area)} ftÂ²</div></div>${ready?'<span class="measure-result-saved">âœ“ SAVED</span>':''}</div><div class="small" style="margin-top:8px">${ready?'This saved area is being used for the quote.':'Finish and save the area to use it for the quote.'} ${currentBusinessType()==='pressure'?'Only the saved cleaning surface is included in this price.':currentBusinessType()==='paving'?'Only the saved paved surface is included in this price.':currentBusinessType()==='landscaping'?'Only the saved landscaping area is included in this price.':'Area and linear measurements are saved with this quote.'}</div></div><div class="price-summary"><h3>Price</h3><div class="line"><span>${savedSurfaceHasAreas()?savedSurfacePriceLines({commercialAreas,linearFeet:linearMeasurementSaved?linearFeetTotal():0,landscapingLinearRate:surfaceLinearJobRate()}):pavingCombined()?pavingPriceLines():pressureCombined()?pressurePriceLines():landscapingCombined()?landscapingPriceLines():commercialHasAreas()?commercialPriceLines():`${fmt(calc.area)} ftÂ² Ã— ${money(calc.price)} / sq. ft.</span><b>${money(calc.subtotal)}</b></div>`}${calc.extraAmount>0?`<div class="line"><span>${escapeHistory(calc.extraDescription||'Additional Services / Repairs')}</span><b>${money(calc.extraAmount)}</b></div>`:''}${calc.discount?`<div class="line"><span>Promotion discount</span><b>-${money(calc.discount)}</b></div>`:''}${calc.mode==='included'?`<div class="line"><span>Pricing</span><b>Taxes Included</b></div>`:`<div class="line"><span>Sales Tax (${calc.gst}%)</span><b>${money(calc.gstAmt)}</b></div>${calc.pst?`<div class="line"><span>Additional Tax (${calc.pst}%)</span><b>${money(calc.pstAmt)}</b></div>`:''}`}<div class="line grand"><span>Total</span><span>${money(calc.total)}</span></div></div>${!ready?`<div class="warning"><b>Finish & save the area to continue.</b></div>`:''}`;el('summary').innerHTML=html;if(el('appliedJobPrice'))el('appliedJobPrice').innerHTML=savedSurfaceHasAreas()?`Quote uses <b>each saved area's rate</b>${linearMeasurementSaved?' + <b>'+money(surfaceLinearJobRate())+' / linear ft.</b>':''}`:(pressureCombined()||pavingCombined()||landscapingCombined())?`Quote is using <b>${money(pressureCombined()?pressureAreaRate():pavingCombined()?pavingAreaRate():landscapingAreaRate())} / sq. ft. (area)</b> + <b>${money(currentJobPrice())} / linear ft. (linear)</b>`:`Quote is using <b>${money(calc.price)} / sq. ft.</b>`;updateUsage();updateProgressSteps();return}if(measurementViewMode==='linear'){const ready=linearMeasurementSaved&&linearPoints.length>1&&linearFeetTotal()>0&&!linearCorrectionOriginal;if(el('createEstimateBtn'))el('createEstimateBtn').disabled=!ready;updateJobSummaryBar(calc,0);let html=`<div class="measure-result-card"><div class="measure-result-head"><div><div class="measure-result-title">Linear Measurement</div><div class="measure-result-value">${linearFeetTotal().toFixed(1)} linear ft</div></div>${ready?'<span class="measure-result-saved">âœ“ SAVED</span>':''}</div><div class="small" style="margin-top:8px">${ready?'This saved length is being used for the quote.':'Finish and save the line to use it for the quote.'} ${currentBusinessType()==='landscaping'?'Only the saved landscaping length is included in this price.':'Only the saved service measurements are included in this quote.'}</div></div><div class="price-summary"><h3>Price</h3><div class="line"><span>${savedSurfaceHasAreas()?savedSurfacePriceLines({commercialAreas,linearFeet:linearMeasurementSaved?linearFeetTotal():0,landscapingLinearRate:surfaceLinearJobRate()}):pavingCombined()?pavingPriceLines():pressureCombined()?pressurePriceLines():landscapingCombined()?landscapingPriceLines():commercialHasAreas()?commercialPriceLines():`${linearFeetTotal().toFixed(1)} ft Ã— ${money(commercialHasLinear()?commercialLinearRate():calc.price)} / linear ft.</span><b>${money(calc.subtotal)}</b></div>`}${calc.extraAmount>0?`<div class="line"><span>${escapeHistory(calc.extraDescription||'Additional Services / Repairs')}</span><b>${money(calc.extraAmount)}</b></div>`:''}${calc.discount?`<div class="line"><span>Promotion discount</span><b>-${money(calc.discount)}</b></div>`:''}${calc.mode==='included'?`<div class="line"><span>Pricing</span><b>Taxes Included</b></div>`:`<div class="line"><span>Sales Tax (${calc.gst}%)</span><b>${money(calc.gstAmt)}</b></div>${calc.pst?`<div class="line"><span>Additional Tax (${calc.pst}%)</span><b>${money(calc.pstAmt)}</b></div>`:''}`}<div class="line grand"><span>Total</span><span>${money(calc.total)}</span></div></div>${!ready?`<div class="warning"><b>Finish & save the linear measurement to continue.</b></div>`:''}`;el('summary').innerHTML=html;if(el('appliedJobPrice'))el('appliedJobPrice').innerHTML=savedSurfaceHasAreas()?`Quote uses <b>each saved area's rate</b>${linearMeasurementSaved?' + <b>'+money(surfaceLinearJobRate())+' / linear ft.</b>':''}`:(pressureCombined()||pavingCombined()||landscapingCombined())?`Quote is using <b>${money(pressureCombined()?pressureAreaRate():pavingCombined()?pavingAreaRate():landscapingAreaRate())} / sq. ft. (area)</b> + <b>${money(currentJobPrice())} / linear ft. (linear)</b>`:`Quote is using <b>${money(commercialHasLinear()?commercialLinearRate():calc.price)} / linear ft.</b>`;updateUsage();updateProgressSteps();return}const roofReview=roofQuoteNeedsReview();if(el('createEstimateBtn'))el('createEstimateBtn').disabled=!hasMeasurement||roofReview||!!roofRemeasureTarget;updateJobSummaryBar(calc,roofCount);let mainPitch=structures.length?structurePitchSummary(structures[0]):null;let html=`<div class="section"><h3>Property Summary</h3><div class="metric-grid"><div class="metric">${roofReview?'Unverified Provider Area':pureManual?'Manual Roof Area':structures.some(st=>st.manually_measured)?'Measured Roof Area':'Google Roof Area'}<b>${fmt(pureManual?m:g)} ftÂ²</b></div><div class="metric">Roofs in Quote<b>${roofCount}</b></div>${!pureManual&&mainPitch&&mainPitch.label!=='â€”'?`<div class="metric">${mainPitch.complex?'Roof Pitch':'Main Roof Pitch'}<b>${mainPitch.label}</b>${mainPitch.detail?`<span class="small" style="display:block;margin-top:3px">${mainPitch.detail}</span>`:''}</div>`:''}</div>${m&&!pureManual?`<div class="metric" style="margin-top:7px">Added Roof<b>+ ${fmt(m)} ftÂ²</b></div>`:''}</div>`;structures.forEach((s,i)=>{let ps=structurePitchSummary(s);html+=`<div class="structure"><div class="structure-head"><div><span class="dot ${i===0?'house-dot':'garage-dot'}"></span><b>${structures.length>3?`#${i+1} Â· `:''}${s.label}</b></div><b>${s.needs_remeasure?'Needs remeasurement':s.automatic_review_warning?'Review required Â· '+fmt(s.total_roof_sqft)+' ftÂ² unverified':fmt(s.total_roof_sqft)+' ftÂ²'}</b></div>${currentBusinessType()==='roofing'?roofRowActionHtml(s,i):''}<div class="small">${s.manually_measured?roofMeasurementSourceLabel(s)+' â€¢ ':s.needs_remeasure?'Automatic coverage needs correction â€¢ area excluded â€¢ ':s.automatic_review_warning?'Automatic area and outline have mismatched scopes â€¢ ':''}${s.segment_count} ${s.manually_measured?(s.measurement_source?.startsWith('dealer_reviewed_')?'reviewed roof outline':'traced roof section'):'roof segments'} â€¢ ${ps.complex?`Multiple pitches ${ps.detail}`:`${s.manually_measured?'Confirmed':'Avg'} pitch ${ps.label}`}${s.manually_measured?'':` â€¢ ${s.imagery_quality||'â€”'} quality â€¢ Imagery ${s.imagery_date||'â€”'}`}</div>${s.manually_measured?'':automaticRoofReviewHtml(s)}</div>`});let suspiciousGoogleRoof=!pureManual&&structures.length===1&&g>0&&g<1000;if(suspiciousGoogleRoof){html+=`<div class="warning" style="margin-top:10px"><b>âš  POSSIBLE INCOMPLETE ROOF MEASUREMENT</b><br>Google returned a small roof measurement. Trees, shadows or limited aerial imagery can sometimes prevent the entire roof from being identified. Review the aerial carefully before creating the estimate. If the full roof cannot be clearly identified, an on-site assessment may be required.</div>`}if(pureManual){manualPlanes.forEach((p,i)=>{html+=`<div class="structure"><div class="structure-head"><div><span class="dot manual-dot"></span><b>${manualPlanes.length===1?'Manual Roof':'Manual Roof '+(i+1)}</b></div><b>${fmt(p.surface_sqft)} ftÂ²</b></div><div class="small">Dealer traced â€¢ ${manualRoofPitchLabel(p.pitch_degrees)} pitch${el('manualRoofScopeConfirmed')?.checked?' confirmed':' â€” confirmation required'}</div></div>`})}html+=`<div class="section"><h3>Quote Measurement</h3><input id="measureSource" type="hidden" value="${src}"><input id="adjustedArea" type="hidden" value="${src==='adjusted'?calc.area:''}"><div class="${hasMeasurement?'good':'warning'}"><b>${hasMeasurement?(structures.some(st=>st.manually_measured)?'âœ“ Roof measurement with dealer corrections â€” pitch included':src==='hybrid'?'âœ“ Google Measurement + Added Roof':src==='manual'?'âœ“ Dealer Manual Measurement':'âœ“ Google Automatic Measurement â€” pitch included'):'Manual measurement required'}</b><br>${hasMeasurement?(src==='hybrid'?`${fmt(g)} ftÂ² measured + ${fmt(m)} ftÂ² added = <b>${fmt(calc.area)} ftÂ² total</b>`:`${fmt(calc.area)} ftÂ² is being used for this estimate.`):'Trace the shingled roof around the customer property pin to unlock pricing and the customer estimate.'}${hasMeasurement&&src!=='manual'&&adjustedOutline?'<br><b>Customer outline adjusted â€” measurement and price unchanged.</b>':''}</div></div>`;html+=`<div class="section"><h3>Dealer-Only Calculation</h3><div class="calc"><div>Estimate measurement</div><div>${fmt(calc.area)} ftÂ²</div><div>Coverage per gallon</div><div>${fmt(coverage)} ftÂ²</div><div>Estimated product required</div><div>${gallons.toFixed(1)} gal</div><div>Price per sq. ft.</div><div>${money(calc.price)}</div></div></div><div class="estimate"><b>Dealer Estimate Preview</b><div class="line"><span>Subtotal before tax</span><b>${money(calc.taxBase)}</b></div>${calc.discount?`<div class="line"><span>Promotion discount</span><b>-${money(calc.discount)}</b></div>`:''}${calc.mode==='included'?`<div class="line"><span>Pricing</span><b>Taxes Included</b></div>`:`<div class="line"><span>Sales Tax (${calc.gst}%)</span><b>${money(calc.gstAmt)}</b></div>${calc.pst?`<div class="line"><span>Additional Tax (${calc.pst}%)</span><b>${money(calc.pstAmt)}</b></div>`:''}`}<div class="line grand"><span>Total Estimate</span><span>${money(calc.total)}</span></div></div>`;let w=confidence();html+=!hasMeasurement?`<div class="warning"><b>Finish the manual roof trace first.</b><br>Pricing and estimate creation stay locked until a roof area has been measured.</div>`:(w.length?`<div class="warning"><b>Review before sending:</b><br>${w.map(x=>'â€¢ '+x).join('<br>')}</div>`:`<div class="${manualRoofQa()&&!el('manualRoofScopeConfirmed')?.checked?'warning':'good'}"><b>${manualRoofQa()&&!el('manualRoofScopeConfirmed')?.checked?'Confirm pitches and included roofs to continue.':'Measurement looks ready.'}</b></div>`);if(roofReview){const reviewStart=html.indexOf('<div class="section"><h3>Quote Measurement</h3>');html=html.slice(0,reviewStart)+`<div class="section"><h3>Quote Measurement</h3><input id="measureSource" type="hidden" value="${src}"><input id="adjustedArea" type="hidden" value="${src==='adjusted'?calc.area:''}"><div class="warning"><b>REVIEW REQUIRED â€” estimate blocked</b><br>The provider area is unverified because it does not cover the same scope as the outline. No quote total or product quantity is ready. ${roofRemeasureTarget?'Finish editing '+escapeHistory(roofRemeasureTarget.label)+' using the controls beside the aerial. The price updates after you save.':'Select FIX ROOF beside the roof that needs correction.'}</div></div>`}el('summary').innerHTML=html;if(el('appliedJobPrice'))el('appliedJobPrice').innerHTML=savedSurfaceHasAreas()?`Quote uses <b>each saved area's rate</b>${linearMeasurementSaved?' + <b>'+money(surfaceLinearJobRate())+' / linear ft.</b>':''}`:(pressureCombined()||pavingCombined()||landscapingCombined())?`Quote is using <b>${money(pressureCombined()?pressureAreaRate():pavingCombined()?pavingAreaRate():landscapingAreaRate())} / sq. ft. (area)</b> + <b>${money(currentJobPrice())} / linear ft. (linear)</b>`:`Quote is using <b>${money(calc.price)} / sq. ft.</b>`;updateUsage();updateProgressSteps()}finally{updateQuotePricingValidation();updateEstimatePeriodUi()}}

function resetReportForNewProperty(){
 document.body.classList.remove('report-open');
 const overlay=el('reportOverlay');if(overlay)overlay.style.display='none';
 if(customerMap){try{customerMap.remove()}catch(e){}customerMap=null}
 customerRgbLayer=null;customerOverlays=[];quoteSnapshot=null;reportOutlines={};reportOutlineTarget=null;reportOutlineEditMode=false;reportOutlinePoints=[];reportOutlineTemp=[];reportCloseArmedAt=0;estimateOpenInProgress=false;pdfInProgress=false;if(customerMapBuildTimer){clearTimeout(customerMapBuildTimer);customerMapBuildTimer=null}if(el('createEstimateBtn'))el('createEstimateBtn').disabled=false;if(el('downloadPdfBtn'))el('downloadPdfBtn').disabled=false;
 const report=document.querySelector('#reportOverlay .report');if(report)report.classList.remove('estimate-editing');
}
function resetMeasurementForNewProperty(){areaRemeasureMode=false;manualRoofEditIndex=null;manualRoofInvalidateScope();
 saveEstimateHistory.baseVersion=null;saveEstimateHistory.pending=null;saveEstimateHistory.cleanWorkspace=null;loadProperty.loadedAddressKey=null;
 savedEstimateEditContext=null;savedPropertyEditActive=false;savedStreetImageData='';savedJobDetails=null;if(el('estimatePeriod'))el('estimatePeriod').value='one_time';
 surfaceLineDraftOriginal=null;areaCorrectionOriginal=null;
 linearCorrectionOriginal=null;linearMode=false;linearPoints=[];linearMeasurementSaved=false;areaMode=false;commercialAreas=[];commercialEditingIndex=-1;savedLinearJobRate=null;commercialAreaLayers.forEach(l=>{try{map.removeLayer(l)}catch(e){}});commercialAreaLayers=[];areaPoints=[];areaMeasurementSaved=false;measurementViewMode=pendingMeasurementMode||'auto';clearLinearLayers();clearAreaLayers();updateLinearUi();updateAreaUi();updatePropertyActionButton();updateMeasurementInterface();
 cancelCurrentTrace();
 structures=[];
 clearOverlays();
 manualPlanes=[];
 manualLayers.forEach(x=>{try{map.removeLayer(x)}catch(e){}});manualLayers=[];
 tracePoints=[];clearTempTrace();
 garageMode=false;clicked=null;
 if(clickMarker){try{map.removeLayer(clickMarker)}catch(e){}clickMarker=null}
 adjustedOutline=null;reportOutline=null;reportOutlineEditMode=false;reportOutlinePoints=[];
 roofFixMode=false;outlineEditMode=false;outlinePoints=[];clearOutlineTemp();setOutlineButtons(false);
 roofMask=null;mainBounds=null;
 if(el('measureSource'))el('measureSource').value='google';
 if(el('garageSavedConfirm')){el('garageSavedConfirm').style.display='none';el('garageSavedConfirm').innerHTML=''}
}

function parseDealerCoordinates(raw){
 const s=String(raw||'').trim().toUpperCase();
 // Accept exactly two decimal degrees, optionally with explicit hemisphere labels.
 // Never extract the first two numbers from DMS, URLs, exponents or arbitrary text.
 const m=s.match(/^([+-]?\d+(?:\.\d+)?)\s*(?:Â°\s*)?([NS])?\s*(?:,\s*|\s+)([+-]?\d+(?:\.\d+)?)\s*(?:Â°\s*)?([EW])?$/);
 if(!m||!!m[2]!==!!m[4])return null;
 let lat=Number(m[1]),lng=Number(m[3]);
 if(m[2]){
  if(/^[+-]/.test(m[1])||/^[+-]/.test(m[3]))return null;
  lat*=m[2]==='S'?-1:1;lng*=m[4]==='W'?-1:1;
 }
 // The aerial's Web Mercator projection cannot display the poles.
 if(!Number.isFinite(lat)||!Number.isFinite(lng)||Math.abs(lat)>85.05112878||Math.abs(lng)>180)return null;
 return {lat,lng};
}
async function loadExactCoordinates(){
 const box=el('coordinateInput'),msg=el('coordinateStatus');
 const p=parseDealerCoordinates(box?box.value:'');
 if(!p){
   if(msg){msg.textContent='Check the format â€” latitude first, longitude second. Example: 27.950575, -82.457178';msg.style.color='#a12622'}
   status('Could not read those coordinates. Check the example beside the field.','error');return;
 }
 const normalized=p.lat.toFixed(6)+', '+p.lng.toFixed(6);
 if(box)box.value=normalized;
 if(msg){msg.textContent='âœ“ Exact pin accepted: '+normalized;msg.style.color='#176b43'}
 if(el('streetAddress'))el('streetAddress').value=normalized;
 if(el('cityTown'))el('cityTown').value='';
 if(el('propertyProvince'))el('propertyProvince').value='';
 if(el('postalCode'))el('postalCode').value='';
 status('Loading the exact dropped-pin locationâ€¦','warn');
 await loadProperty();
}

async function loadExactPinAerial(token,targetMap=map){
 const r=await fetch('/exact-pin-meta/'+token),d=await r.json();
 if(!r.ok)throw new Error(d.error||'Could not load exact-pin aerial.');
 const b=staticMapBounds(d.latitude,d.longitude,d.zoom,d.width,d.height);
 let proxyError='';
 try{
   const ir=await fetch('/exact-pin-map/'+token+'?v='+Date.now());
   if(!ir.ok){proxyError=(await ir.text())||'Could not load exact-pin satellite image.';throw new Error(proxyError)}
   const blob=await ir.blob(),obj=URL.createObjectURL(blob),layer=L.imageOverlay(obj,b,{opacity:1,interactive:false});
   layer._sgAerial=true;layer._sgAerialType='exact-pin-static';layer.once('remove',()=>{try{URL.revokeObjectURL(obj)}catch(e){}});
   layer.addTo(targetMap);return{layer,bounds:b,method:'proxy'};
 }catch(e){proxyError=e.message||String(e)}
 const key="{{GOOGLE_MAPS_API_KEY}}".trim();
 if(key){
   const qs=new URLSearchParams({center:d.latitude+','+d.longitude,zoom:String(d.zoom),size:d.width+'x'+d.height,maptype:'satellite',format:'png',key:key});
   const direct='https://maps.googleapis.com/maps/api/staticmap?'+qs.toString();
   return await new Promise((resolve,reject)=>{
     let done=false;const layer=L.imageOverlay(direct,b,{opacity:1,interactive:false});layer._sgAerial=true;layer._sgAerialType='exact-pin-static';
     const timer=setTimeout(()=>{if(done)return;done=true;try{targetMap.removeLayer(layer)}catch(x){}reject(new Error('exact-pin browser fallback timed out'));},12000);
     layer.once('load',()=>{if(done)return;done=true;clearTimeout(timer);resolve({layer,bounds:b,method:'browser'})});
     layer.once('error',()=>{if(done)return;done=true;clearTimeout(timer);try{targetMap.removeLayer(layer)}catch(x){}reject(new Error(proxyError||'exact-pin browser fallback was rejected'))});
     layer.addTo(targetMap);
   });
 }
 throw new Error(proxyError||'Could not load exact-pin satellite image.');
}

function showTrialLimit(){const x=el('trialLimitOverlay');if(x)x.classList.add('open')}function closeTrialLimit(){const x=el('trialLimitOverlay');if(x)x.classList.remove('open')}
async function preparePropertyImagery(d){
 const host=document.createElement('div');host.style.cssText='position:fixed;left:-20000px;top:0;width:900px;height:650px;';document.body.appendChild(host);
 const staging=L.map(host,{zoomControl:false,attributionControl:false,zoomAnimation:false});
 const center=d.center||d.anchor||d.main;
 staging.setView([center.latitude,center.longitude],18);
 let ready;
 try{
  const surface=['paving','pressure','landscaping','commercial','snow'].includes(currentBusinessType());
  if(surface||d.manual_roof_only){try{ready=await loadStandardWideAerial(d.token,staging,true,L.latLng(center.latitude,center.longitude))}catch(e){ready=d.exact_pin_display?await loadExactPinAerial(d.token,staging):await loadFallbackAerial(d.token,staging)}}
  else if(d.fallback)ready=await loadFallbackAerial(d.token,staging);
  else{
   ready=d.exact_pin_display?await loadExactPinAerial(d.token,staging):await loadRaster('/rgb/'+d.token,staging);
   ready.mask=await loadRoofMask('/mask/'+d.token,true);
   if(!d.exact_pin_display){const wide=await loadStandardWideAerial(d.token,staging,true,L.latLng(center.latitude,center.longitude));staging.removeLayer(ready.layer);ready={...wide,mask:ready.mask}}
  }
  // ImageOverlay fallbacks return before their image has decoded. Wait here too.
  const layers=ready.layer.getLayers?ready.layer.getLayers():[ready.layer];
  await Promise.all((ready.layer.getLayers?[]:layers).map(layer=>new Promise((resolve,reject)=>{
   const img=layer.getElement?.();if(!img||img.tagName!=='IMG')return resolve();
   if(img.complete)return img.naturalWidth?resolve():reject(new Error('Satellite image could not decode.'));
   const timer=setTimeout(()=>reject(new Error('Satellite image timed out.')),20000);
   const done=fn=>{clearTimeout(timer);fn()};layer.once('load',()=>done(resolve));layer.once('error',()=>done(()=>reject(new Error('Satellite image could not decode.'))));
  })));
  const objectLayers=layers.filter(layer=>String(layer._url||'').startsWith('blob:'));
  objectLayers.forEach(layer=>layer.off('remove'));
  staging.removeLayer(ready.layer);
  objectLayers.forEach(layer=>layer.once('remove',()=>URL.revokeObjectURL(layer._url)));
  return ready;
 }finally{staging.remove();host.remove()}
}
function installPropertyImagery(ready){
 ready.layer.addTo(map);removeStaleAerialLayers(ready.layer);fallbackLayer=ready.layer;fallbackBounds=ready.bounds;rgbLayer=null;mainBounds=ready.bounds;
 map.setMinZoom(14);map.setMaxBounds(null);map.options.maxBoundsViscosity=0;
 if(ready.layer._sgAerialType==='wide-3x3-mosaic')map.setView(ready.bounds.getCenter(),18,{animate:false});else frameAerial(map,ready.bounds,0);
 map.off('moveend',scheduleAerialDetail);if(ready.layer._sgAerialType==='wide-3x3-mosaic')map.on('moveend',scheduleAerialDetail);
 aerialDetailSequence++;aerialDetailKey='';aerialDetailLayer=null;
}
async function loadProperty(){
 if(loadProperty.inFlight)return loadProperty.inFlight;
 loadProperty.inFlight=performLoadProperty();
 try{return await loadProperty.inFlight}finally{loadProperty.inFlight=null}
}
async function performLoadProperty(){
 const unitGuess=unitAddressSuggestion(el('streetAddress')?.value,propertyLookupProvince());
 if(!coordinatesEntered()&&unitGuess){
  if(!window.confirm('Is '+unitGuess.unit+' the unit and '+unitGuess.number+' the building number?\n\nUse: '+unitGuess.address+'\n\nChoose Cancel to edit the address.')){status('Enter the building address, then # and the unit number if needed.','warn');return}
  el('streetAddress').value=unitGuess.address;
 }
 const requestedMeasurementMode=pendingMeasurementMode||measurementViewMode||'auto';
 const enteredStreet=(el('streetAddress')?.value||'').trim(),enteredCity=(el('cityTown')?.value||'').trim(),enteredProvince=propertyLookupProvince(),enteredNumber=enteredStreetNumber();
 const cc=coordinatesEntered(),enteredKey=propertyInputAddressKey(),workspaceKey=workspaceSaveFingerprint();
 if(cc&&!window.confirm('Use latitude '+cc.lat.toFixed(6)+' and longitude '+cc.lng.toFixed(6)+'?\n\nLatitude must be first. Confirm these are the intended property coordinates.'))return;
 if(!cc&&(!enteredStreet||!enteredCity||!enteredProvince)){status('Enter the street address, City and State/Province. ZIP/postal code is not required.','error');return}
 // Freeze exactly what the dealer entered BEFORE any report/measurement reset can change UI state.
 const authoritativeAddress=cc?(cc.lat.toFixed(6)+','+cc.lng.toFixed(6)):[enteredStreet,enteredCity,enteredProvince,propertyCountryFromProvince(enteredProvince)].join(', ');

 if(cc&&el('googleMatch'))el('googleMatch').textContent='Loading exact coordinates: '+authoritativeAddress;
const key="{{GOOGLE_MAPS_API_KEY}}",address=authoritativeAddress;if(!key||!address){status('Enter API key and address.','error');return}
 try{
  status('Loading propertyâ€¦');showLoad(true);
  const payload=cc?{key,address,latitude:cc.lat,longitude:cc.lng,direct_coordinates:true}:{key,address,expected_city:enteredCity,expected_province:enteredProvince,expected_street_number:enteredNumber};
  clearTimeout(addressPreviewTimer);addressPreviewSeq++;
  payload.business_type=currentBusinessType();
  const requestKey=JSON.stringify(payload);if(loadProperty.pending?.key!==requestKey)loadProperty.pending={key:requestKey,id:typeof crypto!=='undefined'&&crypto.randomUUID?crypto.randomUUID():Date.now().toString(36)+'-'+Math.random().toString(36).slice(2)};
  let r=await fetch('/property',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':loadProperty.pending.id},body:JSON.stringify({...payload,prepare_only:true})}),d=await r.json();if(r.status===401)throw new Error('Your login expired. Keep this page open and sign in in another tab. Your previous measurements are unchanged.');if(!r.ok){if(r.status===410)loadProperty.pending=null;if(r.status===403&&d.code==='trial_limit_reached'){showLoad(false);showTrialLimit();status('Free trial complete â€” choose a plan to continue measuring properties.','warn');return}throw new Error(d.user_error||d.error||'Property request failed')}
  const verifyEl=el('propertyVerify');if(verifyEl){verifyEl.style.display='none';verifyEl.textContent=''}
  try{
    if(cc){if(verifyEl){verifyEl.style.display='block';verifyEl.style.color='#176b43';verifyEl.textContent='âœ“ Using exact dropped-pin coordinates â€” address matching bypassed.'}}
    else{
    const vr=await fetch('/mapbox-test?address='+encodeURIComponent(d.formatted_address||address)),vd=await vr.json();
    if(verifyEl&&vr.ok&&vd.status==='warning'&&vd.nearby_same_number_alternatives?.length&&!skipAddressConflictOnce){
      const alt=vd.nearby_same_number_alternatives[0],matched=d.formatted_address||address;
      verifyEl.style.display='block';verifyEl.style.color='#9a6700';verifyEl.textContent='âš  ADDRESS CONFLICT â€” measurement is paused until you confirm the correct property.';
      showLoad(false);
      const useMatched=window.confirm('ADDRESS CONFLICT â€” DO NOT MEASURE YET.\n\nGoogle matched:\n'+matched+'\n\nNearby same-number property:\n'+alt.address+'\n\nPress OK to CONFIRM THE GOOGLE MATCHED PROPERTY.\nPress Cancel to USE THE NEARBY ALTERNATIVE.');
      skipAddressConflictOnce=true;
      if(!useMatched){
        if(el('streetAddress'))el('streetAddress').value=alt.address;
        if(el('cityTown'))el('cityTown').value='';if(el('propertyProvince'))el('propertyProvince').value='';if(el('postalCode'))el('postalCode').value='';
        status('Review the alternative address, enter its City and State/Province, then load it. Your existing work is unchanged.','warn');return;
      }
      verifyEl.style.color='#176b43';verifyEl.textContent='âœ“ Dealer confirmed Google matched property: '+matched;
    }
    else if(verifyEl&&vr.ok){verifyEl.style.display='block';verifyEl.style.color='#176b43';verifyEl.textContent='âœ“ Property address verified'}
    }
  }catch(e){if(verifyEl&&!cc)verifyEl.style.display='none'}
  skipAddressConflictOnce=false;
  const prepared=await preparePropertyImagery(d);
  if(workspaceSaveFingerprint()!==workspaceKey)throw new Error('Your measurements or pricing changed while loading. Save your work before replacing the property.');
  if(propertyInputAddressKey()!==enteredKey)throw new Error('The address changed while imagery was loading. Review it and retry.');
  const accepted=await fetch('/property/accept',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({operation_id:loadProperty.pending.id,token:d.token})});
  const acceptance=await accepted.json();
  if(!accepted.ok){if(accepted.status===410)loadProperty.pending=null;throw new Error(acceptance.error||'Property could not be accepted. Keep this page open and retry.');}
  loadProperty.pending=null;
 if((el('address')?.value||'')!==authoritativeAddress)['customerName','customerPhone','customerEmail','customerNotes'].forEach(id=>{if(el(id))el(id).value=''});
 resetReportForNewProperty();exactPinDisplay=false;if(el('address'))el('address').value=authoritativeAddress;syncPropertyProvince();
  resetMeasurementForNewProperty();locateRoofMode=false;fallbackMode=false;setManualCorrectionLayout(false);showSolarFallback(false);if(propertyMarker){try{map.removeLayer(propertyMarker)}catch(e){}propertyMarker=null};removeStaleAerialLayers();
  sessionToken=d.token;exactPinDisplay=!!d.exact_pin_display;lastLoadedStreet=el('streetAddress')?.value.trim()||'';applyAddressParts(d.parts);loadProperty.loadedAddressKey=propertyInputAddressKey();if(d.center)setPropertyMarker(d.center.latitude,d.center.longitude);else if(d.anchor)setPropertyMarker(d.anchor.latitude,d.anchor.longitude);if(el('addressAutoStatus'))el('addressAutoStatus').textContent='âœ“ '+(d.formatted_address||buildPropertyAddress());if(el('googleMatch'))el('googleMatch').textContent='Google matched: '+(d.formatted_address||buildPropertyAddress());
  let prov=detectProvince(d.formatted_address||address);if(prov){if(el('propertyProvince'))setPropertyRegion(prov);syncPropertyProvince()}
  el('street').style.visibility='visible';el('street').src='/street/'+sessionToken+'?v='+Date.now();el('streetMeta').textContent=d.street_date?('Street View imagery: '+d.street_date):'Actual Street View';usage.property++;
  installPropertyImagery(prepared);
  // Commercial surface measurements must never run the roof AutoMeasure path.
  // Use the property satellite image, then activate the selected surface tool.
  if(['paving','pressure','landscaping','commercial','snow'].includes(currentBusinessType())){
    structures=[];manualPlanes=[];roofMask=null;
    setManualCorrectionLayout(false);setManualUi(false);
    if(el('measureSource'))el('measureSource').value='manual';
    // Prefer the existing wider commercial satellite framing used before the
    // roof-routing correction. Fall back to the previous image only if needed.
    pendingMeasurementMode=((pendingMeasurementMode||requestedMeasurementMode)==='linear'?'linear':'area');
    measurementViewMode=pendingMeasurementMode;
    selectMeasurementTool(pendingMeasurementMode);
    renderSummary();
    if(el('garageGuide'))el('garageGuide').textContent='Satellite imagery loaded. Measure the paved or service area using Area or Linear tools.';
    status('Property aerial loaded â€” ready for '+(pendingMeasurementMode==='linear'?'Linear':'Area')+' measurement.','ok');
    return;
  }
  if(d.manual_roof_only){
    structures=[];manualPlanes=[];roofMask=null;measurementViewMode='auto';pendingMeasurementMode='auto';
    fallbackMode=true;manualOverrideMode=true;el('measureSource')&&(el('measureSource').value='manual');
    setManualCorrectionLayout(true);setManualUi(true);showSolarFallback(false);fallbackMode=true;
    toggleTrace();renderSummary();status('Trace each roof section, confirm its pitch, then review the estimate.','ok');return;
  }
  if(d.fallback){
    structures=[];setManualCorrectionLayout(true);setManualUi(true);if(el('measureSource'))el('measureSource').value='manual';
    const aerialLoaded=true;
    showSolarFallback(true,'Google does not have an automatic roof measurement for this property. Manual measurement is required. Trace the shingled roof below and confirm its pitch.');
    renderSummary();
    if(el('garageGuide'))el('garageGuide').innerHTML='<b>Manual measurement required.</b> Trace the shingled roof area shown below and confirm the pitch. If imagery appears older, verify the current roof layout before sending the estimate.';
    if(el('measureClicked'))el('measureClicked').disabled=true;if(el('measureClickedTop'))el('measureClickedTop').disabled=true;
    const details=el('manualRoofDetails');if(details)details.open=true;
    if(aerialLoaded){setTimeout(()=>{if(!traceMode)toggleTrace()},80)}
    status('Automatic measurement unavailable â€” manual roof tracing is ready. Confirm the pitch before saving.','warn');return;
  }
  structures=[{...d.main,label:'Main House'}];setManualCorrectionLayout(false);setManualUi(false);if(el('measureSource'))el('measureSource').value='google';roofMask=prepared.mask;d.main.outline=outlineFromMask(roofMask,d.main.latitude,d.main.longitude);structures[0].outline=d.main.outline;reviewAutomaticRoof(structures[0]);let rgb=prepared;redrawRoofData();if(exactPinDisplay)frameAerial(map,rgb.bounds,0);renderSummary();if(el('garageGuide'))el('garageGuide').innerHTML=roofQuoteNeedsReview()?'<b>Main roof requires review.</b> Use FIX ROOF in the Property Summary.': '<b>Main house measured.</b> If there is another roof to include, click <b>+ ADD GARAGE / OTHER ROOF</b>, then click once on that roof. It will measure automatically.';if(el('measureClicked'))el('measureClicked').disabled=false;if(el('measureClickedTop'))el('measureClickedTop').disabled=false;status((structures[0]?.needs_remeasure||structures[0]?.automatic_review_warning)?'Main roof coverage needs review. Use FIX ROOF in the Property Summary.':'Main house measured. Use + Add Garage / Other Roof if needed.',(structures[0]?.needs_remeasure||structures[0]?.automatic_review_warning)?'warn':'ok');pendingMeasurementMode=requestedMeasurementMode;if(requestedMeasurementMode==='area'||requestedMeasurementMode==='linear'){selectMeasurementTool(requestedMeasurementMode)}else{measurementViewMode='auto';updatePropertyActionButton();updateMeasurementInterface()}
 }catch(e){status(e.message+' Your existing saved or unsaved work is unchanged. Retry Load Property when ready.','error')}finally{showLoad(false)}
}
function startGarageMode(){if(manualRoofQa()){beginManualRoofSection();return}if(measureClicked.pending){extraRoofStatus('The selected roof is still being measured. Please wait for its result.','warn');return}if(!sessionToken){status('Load the property first.','error');return}if(!structures.length){if(manualPlanes.length){garageMode=false;setManualCorrectionLayout(false);setManualUi(false);const details=el('manualRoofDetails');if(details)details.open=true;if(!traceMode)toggleTrace();status('Add Garage / Other Roof â€” trace the next shingled building, confirm its pitch, then save it.','warn');return}status('Finish the main-house manual measurement first.','warn');return}garageMode=true;clicked=null;if(el('garageSavedConfirm'))el('garageSavedConfirm').style.display='none';if(clickMarker){try{map.removeLayer(clickMarker)}catch(e){}clickMarker=null}if(el('garageGuide'))el('garageGuide').innerHTML='<b>Add Garage / Other Roof is ON.</b> Click once near the centre of the garage, shed or shop roof. It will measure automatically.';status('Click once near the centre of the extra roof to measure it automatically.','warn')}
function extraRoofStatus(message,kind=''){
 status(message,kind);
 const guide=el('garageGuide');if(guide)guide.textContent=message;
 if(clickMarker){const text=document.createElement('div');text.textContent=message;clickMarker.setPopupContent(text).openPopup()}
}
async function measureClicked(){if(measureClicked.pending)return;if(!sessionToken||!clicked){extraRoofStatus('Click the centre of the extra structure first.','error');return}measureClicked.pending=true;try{extraRoofStatus('Measuring selected structureâ€¦');let r=await fetch('/structure',{signal:AbortSignal.timeout(45000),method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:sessionToken,latitude:clicked.lat,longitude:clicked.lng})}),d=await r.json();if(!r.ok)throw new Error(d.error||'Structure request failed');let dup=structures.find(s=>(s.building_id&&d.building_id&&s.building_id===d.building_id)||(Math.abs(s.latitude-d.latitude)<.00003&&Math.abs(s.longitude-d.longitude)<.00003)||tracedRoofContains(s,d.latitude,d.longitude));if(dup){extraRoofStatus(dup.needs_remeasure?'That roof is already listed for correction. Use FIX ROOF in the Property Summary.':'That building is already included. Click nearer the centre of a different structure.','error');return}d.label=structures.length===1?'Detached Garage':`Extra Structure ${structures.length}`;extraRoofStatus('Roof measurement received. Loading its outlineâ€¦');const ownMask=d.mask_url?await loadRoofMask(d.mask_url,true):null;d.outline=outlineFromMask(ownMask,d.latitude,d.longitude);delete d.mask_url;if(!d.outline){extraRoofStatus('Google measured this roof, but no usable outline was found in its imagery (AQ-MASK-CONTOUR). It has not been added.','warn');return}reviewAutomaticRoof(d,true);structures.push(d);redrawRoofData();fitEntireQuote(map);usage.structures++;renderSummary();if(d.needs_remeasure){extraRoofStatus('This automatic result may cover only part of the roof. No area has been included for it. Use FIX ROOF in the Property Summary.','warn');return}if(clickMarker){try{map.removeLayer(clickMarker)}catch(e){}clickMarker=null}clicked=null;if(el('garageGuide'))el('garageGuide').innerHTML=`<b>${d.label} is already saved in this quote.</b> To add another roof, click <b>+ ADD GARAGE / OTHER ROOF</b> again.`;if(el('garageSavedConfirm')){el('garageSavedConfirm').style.display='block';el('garageSavedConfirm').innerHTML=`<b>âœ“ ${d.label} SAVED TO QUOTE â€” ${fmt(d.total_roof_sqft)} ftÂ² INCLUDED</b><br><span class="small">No other Save button is required. It is already included in Roofs in Quote and the estimate total.</span>`}extraRoofStatus(`${d.label} saved to quote â€” ${fmt(d.total_roof_sqft)} ftÂ² included.`,'ok')}catch(e){extraRoofStatus(e.roofCode?'Google measured this roof, but its outline could not load ('+e.roofCode+'). It has not been added.':e.name==='TimeoutError'||e.name==='AbortError'?'This roof request timed out. It has not been added. Click + Add Garage / Other Roof to retry.':'This roof could not finish measuring. It has not been added. Try again or use Add Missing Roof.','warn')}finally{measureClicked.pending=false}}
function removeLastExtra(){
 // Never touch the main house. Undo only something the dealer added after it.
 if(manualPlanes.length){
   manualPlanes.pop();
   for(let i=0;i<2;i++){const lyr=manualLayers.pop();if(lyr){try{map.removeLayer(lyr)}catch(e){}}}
   if(el('measureSource'))el('measureSource').value=manualPlanes.length?(structures.length?'hybrid':'manual'):(structures.length?'google':'manual');
   renderSummary();status('Last dealer-added manual roof removed. Main house measurement was not changed.','ok');return;
 }
 if(structures.length>1){
   const removed=structures.pop();redrawRoofData();renderSummary();status((removed.label||'Last added roof')+' removed. Main house measurement was not changed.','ok');return;
 }
 status('No added roof to undo. The main house is protected and was not changed.','warn');
}


function captureQuoteSnapshot(){
 const clone=x=>JSON.parse(JSON.stringify(x||[]));
 quoteSnapshot={manualRoofWorkflow:typeof manualRoofQa==='function'&&manualRoofQa()&&measurementViewMode==='auto'&&manualPlanes.some(p=>p.manual_roof_qa),roofScopeConfirmed:!!el('manualRoofScopeConfirmed')?.checked,warrantyBrand:accountWarrantyBrand,showWarrantyShield:!!el("showWarrantyShield")?.checked,structures:clone(structures),manualPlanes:clone(manualPlanes),measureSource:(el('measureSource')&&el('measureSource').value)||'google',adjustedArea:Number(el('adjustedArea')?.value||0),measurementMode:measurementViewMode,linearPoints:linearPoints.map(p=>[p.lat,p.lng]),linearFeet:linearFeetTotal(),areaPoints:areaPoints.map(p=>[p.lat,p.lng]),areaSqFt:multiAreaSaved()?multiAreaTotal():areaSqFtTotal(),commercialAreas:clone(commercialAreas),businessType:currentBusinessType(),dealerCountry:el('dealerCountry')?.value||'US',commercialLinearRate:commercialHasLinear()?commercialLinearRate():0,commercialLinearSaved:commercialHasLinear(),landscapingCombined:landscapingCombined(),landscapingAreaRate:landscapingCombined()?landscapingAreaRate():0,landscapingLinearRate:surfaceLinearJobRate(),pressureCombined:pressureCombined(),pressureAreaRate:pressureCombined()?pressureAreaRate():0,pressureLinearRate:surfaceLinearJobRate(),pavingCombined:pavingCombined(),pavingAreaRate:pavingCombined()?pavingAreaRate():0,pavingLinearRate:surfaceLinearJobRate()};
 return quoteSnapshot;
}
function clearReportOutlineTemp(){reportOutlineTemp.forEach(x=>{try{customerMap&&customerMap.removeLayer(x)}catch(e){}});reportOutlineTemp=[];const svg=el('reportDrawLayer');if(svg)svg.innerHTML=''}
function syncReportDrawLayer(){const svg=el('reportDrawLayer');if(!svg||!customerMap)return;const c=el('customerMap'),w=c.clientWidth||1,h=c.clientHeight||465;svg.setAttribute('viewBox',`0 0 ${w} ${h}`);svg.setAttribute('width',w);svg.setAttribute('height',h)}
function drawReportOutlineTemp(){const svg=el('reportDrawLayer');if(!svg||!customerMap)return;syncReportDrawLayer();svg.innerHTML='';const pts=reportOutlinePoints.map(p=>customerMap.latLngToContainerPoint(p));if(pts.length>1){const pl=document.createElementNS('http://www.w3.org/2000/svg','polyline');pl.setAttribute('points',pts.map(p=>`${p.x},${p.y}`).join(' '));svg.appendChild(pl)}pts.forEach(p=>{const c=document.createElementNS('http://www.w3.org/2000/svg','circle');c.setAttribute('cx',p.x);c.setAttribute('cy',p.y);c.setAttribute('r','6');svg.appendChild(c)})}
function reportTargetLabel(key){
 if(key==='structure-0')return'MAIN HOUSE';
 const snap=quoteSnapshot||captureQuoteSnapshot();
 const extraCount=Math.max(0,(snap.structures||[]).length-1)+(snap.manualPlanes||[]).length;
 if(key&&key.startsWith('structure-'))return extraCount===1?'ADDED GARAGE / OTHER ROOF':`ADDED GARAGE / OTHER ROOF ${key.split('-')[1]}`;
 if(key&&key.startsWith('manual-')){const i=Number(key.split('-')[1]);if((snap.measureSource||'')==='manual'&&!(snap.structures||[]).length&&i===0)return'MAIN HOUSE';return extraCount===1?'ADDED GARAGE / OTHER ROOF':`ADDED GARAGE / OTHER ROOF ${Math.max(0,(snap.structures||[]).length-1)+i+1}`;}
 return'ROOF';
}
function returnToAreaCorrection(){document.body.classList.remove("report-open");if(el("reportOverlay"))el("reportOverlay").style.display="none";if(customerMap){try{customerMap.remove()}catch(e){}customerMap=null}customerRgbLayer=null;customerOverlays=[];if(typeof correctAreaOutline==="function")correctAreaOutline();if(el("areaTool"))el("areaTool").scrollIntoView({behavior:"smooth",block:"center"});}
function returnToLinearCorrection(){document.body.classList.remove('report-open');if(el('reportOverlay'))el('reportOverlay').style.display='none';if(customerMap){try{customerMap.remove()}catch(e){}customerMap=null}customerRgbLayer=null;customerOverlays=[];if(el('linearTool'))el('linearTool').scrollIntoView({behavior:'smooth',block:'center'});if(el('linearStartBtn'))el('linearStartBtn').focus();}
let visualCorrectionMarkers=[],visualCorrectionLayer=null,visualCorrectionMode=null;
function clearVisualCorrection(){if(visualCorrectionClickHandler&&customerMap){customerMap.off('click',visualCorrectionClickHandler);visualCorrectionClickHandler=null;}if(el('reportUndoOutlineBtnTop'))el('reportUndoOutlineBtnTop').style.display='none';visualCorrectionMarkers.forEach(m=>{try{customerMap&&customerMap.removeLayer(m)}catch(e){}});visualCorrectionMarkers=[];if(visualCorrectionLayer){try{customerMap&&customerMap.removeLayer(visualCorrectionLayer)}catch(e){}}visualCorrectionLayer=null;visualCorrectionMode=null;}
let visualCorrectionClickHandler=null;
function refreshVisualCorrectionLine(){
 if(!visualCorrectionLayer)return;
 const pts=visualCorrectionMarkers.map(m=>m.getLatLng());
 visualCorrectionLayer.setLatLngs(pts);
 if(el('reportSaveOutlineBtnTop'))el('reportSaveOutlineBtnTop').disabled=pts.length<(visualCorrectionMode==='area'?3:2);
 if(el('reportUndoOutlineBtnTop'))el('reportUndoOutlineBtnTop').style.display=pts.length?'inline-block':'none';
}
function addVisualCorrectionPoint(latlng){
 if(!visualCorrectionMode)return;
 const m=L.marker(latlng,{draggable:true,autoPan:true,title:'Drag this point to correct the estimate image'}).addTo(customerMap);
 m.on('drag',refreshVisualCorrectionLine);
 visualCorrectionMarkers.push(m);
 refreshVisualCorrectionLine();
}
function startVisualMeasurementCorrection(mode){
 if(surfaceIndustry()){correctSavedMeasurementFromReport(mode);return}
 if(!customerMap){if(el('reportOutlineHelpTop'))el('reportOutlineHelpTop').textContent='The aerial image is not ready. Please reopen the estimate.';return;}
 clearVisualCorrection();
 visualCorrectionMode=mode;
 customerOverlays.forEach(layer=>{try{customerMap.removeLayer(layer)}catch(e){}});customerOverlays=[];
 // Start EMPTY: the dealer traces the estimate image, not an automatic four-corner shape.
 visualCorrectionLayer=(mode==='area'?L.polygon([],{color:'#f97316',weight:4,fillOpacity:.10}):L.polyline([],{color:'#f97316',weight:5})).addTo(customerMap);
 visualCorrectionClickHandler=e=>addVisualCorrectionPoint(e.latlng);
 customerMap.on('click',visualCorrectionClickHandler);
 if(el('reportOutlineTargetButtons'))el('reportOutlineTargetButtons').style.display='none';
 if(el('reportSaveOutlineBtnTop')){el('reportSaveOutlineBtnTop').style.display='inline-block';el('reportSaveOutlineBtnTop').disabled=true;el('reportSaveOutlineBtnTop').textContent='SAVE TRACED IMAGE';}
 if(el('reportCancelOutlineBtnTop'))el('reportCancelOutlineBtnTop').style.display='inline-block';
 if(el('reportUndoOutlineBtnTop'))el('reportUndoOutlineBtnTop').style.display='none';
 if(el('reportOutlineHelpTop'))el('reportOutlineHelpTop').textContent='Click each point along the actual service line on the aerial. Drag points to adjust, Undo Point to remove the last point, then Save Traced Image. Measurement and price will not change.';
 if(el('downloadPdfBtn'))el('downloadPdfBtn').disabled=true;
}
async function saveVisualCorrection(){
 if(!visualCorrectionMode)return;
 const mode=visualCorrectionMode;
 reportOutlines[mode+'-visual']=visualCorrectionMarkers.map(m=>[m.getLatLng().lat,m.getLatLng().lng]);
 clearVisualCorrection();await buildCustomerMap();setReportOutlineButtons(false);
 if(el('reportSaveOutlineBtnTop'))el('reportSaveOutlineBtnTop').textContent='SAVE OUTLINE';
 if(el('reportOutlineHelpTop'))el('reportOutlineHelpTop').textContent='âœ“ Estimate image corrected. Original measurement and price are unchanged.';
}
// Estimate corrections use a separate draft; the saved workspace stays authoritative.
let reportMeasurementCorrection=null;
function reportCorrectionWorkspace(){return {areas:JSON.parse(JSON.stringify(commercialAreas)),area:areaPoints.map(p=>[p.lat,p.lng]),line:linearPoints.map(p=>[p.lat,p.lng]),snapshot:quoteSnapshot,index:commercialEditingIndex}}
function restoreReportCorrectionWorkspace(w){commercialAreas=JSON.parse(JSON.stringify(w.areas));areaPoints=w.area.map(p=>L.latLng(p));linearPoints=w.line.map(p=>L.latLng(p));quoteSnapshot=w.snapshot;commercialEditingIndex=w.index}
function applyReportCorrectionCandidate(){
 const c=reportMeasurementCorrection,pts=c.points.map(p=>[p.lat,p.lng]);
 if(c.mode==='area'){
  commercialAreas[c.index]={...commercialAreas[c.index],points:pts,sqft:Math.round(localPolygonAreaM2(c.points)*10.76391041671)};
  if(commercialEditingIndex===c.index)areaPoints=c.points.map(p=>L.latLng(p));
 }else linearPoints=c.points.map(p=>L.latLng(p));
}
function reportCorrectionProblem(){
 const c=reportMeasurementCorrection;if(!c)return '';
 if(c.points.some(p=>!Number.isFinite(p.lat)||!Number.isFinite(p.lng)||Math.abs(p.lat)>90||Math.abs(p.lng)>180))return 'Invalid measurement coordinates.';
 if(c.mode==='area')return measuredPolygonError(c.points)||savedAreaGeometryError(commercialAreas.map((a,i)=>i===c.index?{...a,points:c.points.map(p=>[p.lat,p.lng]),sqft:Math.round(localPolygonAreaM2(c.points)*10.76391041671)}:a));
 return savedLinearGeometryError(c.points);
}
function redrawReportCorrection(){
 const c=reportMeasurementCorrection;if(!c)return;
 c.layers.forEach(l=>customerMap.removeLayer(l));c.layers=[];
 const poly=(c.mode==='area'?L.polygon:L.polyline)(c.points,{color:'#f97316',weight:4,fillOpacity:.12,interactive:false}).addTo(customerMap);c.layers.push(poly);
 c.points.forEach((p,i)=>{
  const marker=L.marker(p,{draggable:!c.saving&&!c.uncertain,autoPan:false,icon:L.divIcon({className:'report-correction-point',html:'<span></span>',iconSize:[28,28],iconAnchor:[14,14]})}).addTo(customerMap);
  marker.on('dragstart',()=>{c.history.push(c.points.map(p=>[p.lat,p.lng]))});
  marker.on('drag',()=>{c.points[i]=marker.getLatLng();poly.setLatLngs(c.points)});
  marker.on('dragend',()=>{c.error='';redrawReportCorrection()});c.layers.push(marker);
 });
 const issue=reportCorrectionProblem();let message=issue;
 if(!issue){const before=reportCorrectionWorkspace();try{applyReportCorrectionCandidate();const calc=priceCalc();message=quotePricingError(calc);if(!message){const quantity=c.mode==='area'?commercialAreas[c.index].sqft:linearFeetTotal();message=`${c.mode==='area'?'Area '+(c.index+1):'Linear'}: ${c.originalQuantity.toLocaleString()} â†’ ${c.mode==='area'?fmt(quantity):quantity.toFixed(1)} ${c.mode==='area'?'ftÂ²':'ft'}. Estimate total: ${money(c.originalTotal)} â†’ ${money(calc.total)}. Save confirms this measurement and price change.`;}}finally{restoreReportCorrectionWorkspace(before)}}
 el('reportOutlineHelpTop').textContent=(c.mode==='area'?'RETRACE OUTLINE â€” tap the new boundary in order. Cancel keeps the original. ':'')+(c.error||message||'Adjust the points or select Redraw. Cancel keeps the original.');
 el('reportSaveOutlineBtnTop').disabled=!!issue||c.saving;
 el('reportSaveOutlineBtnTop').textContent=c.saving?'SAVINGâ€¦':'SAVE MEASUREMENT & UPDATE ESTIMATE';
 el('reportCancelOutlineBtnTop').disabled=c.saving||!!c.uncertain;el('reportUndoOutlineBtnTop').disabled=c.saving||!!c.uncertain||!c.history.length;
 el('reportRedrawBtn').disabled=c.saving||!!c.uncertain;
}
function correctSavedMeasurementFromReport(mode,index=0){
 if(!surfaceIndustry()||!sessionToken||!customerMap||!['area','linear'].includes(mode)||reportMeasurementCorrection||pdfInProgress||estimateOpenInProgress)return;
 if(savedEstimateEditContext||quoteSnapshot?.savedPricing){status('Select EDIT MEASUREMENTS / PRICE to restore this saved job before correcting it.','warn');return}
 if(areaMode||linearMode||areaCorrectionOriginal||linearCorrectionOriginal)return;
 const pts=mode==='area'?commercialAreas[index]?.points:linearMeasurementSaved?linearPoints.map(p=>[p.lat,p.lng]):null;
 if(!pts||pts.length<(mode==='area'?3:2))return;
 clearVisualCorrection();clearReportOutlineTemp();reportOutlines={};
 const c=reportMeasurementCorrection={mode,index,points:mode==='area'?[]:pts.map(p=>L.latLng(p)),layers:[],originalQuantity:mode==='area'?commercialAreas[index].sqft:Number(linearFeetTotal().toFixed(1)),originalTotal:priceCalc().total,saving:false,drawing:mode==='area',history:[],drag:customerMap.dragging.enabled(),double:customerMap.doubleClickZoom.enabled()};
 customerMap.dragging.disable();customerMap.doubleClickZoom.disable();
 // Hide only the selected saved measurement; unrelated Areas and Linear stay visible.
 customerOverlays.filter(l=>l._reportMeasurement?.mode===mode&&(mode!=='area'||l._reportMeasurement.index===index)).forEach(l=>customerMap.removeLayer(l));
 c.click=e=>{if(c.saving||c.uncertain||!c.drawing)return;c.history.push(c.points.map(p=>[p.lat,p.lng]));c.points.push(e.latlng);c.error='';redrawReportCorrection()};customerMap.on('click',c.click);
 el('reportOutlineTargetButtons').style.display='none';
 ['reportSaveOutlineBtnTop','reportCancelOutlineBtnTop','reportUndoOutlineBtnTop','reportRedrawBtn'].forEach(id=>el(id).style.display='inline-block');
 el('reportRedrawBtn').style.display=mode==='area'?'none':'inline-block';el('reportRedrawBtn').textContent='REDRAW';el('reportUndoOutlineBtnTop').textContent='UNDO';el('reportCancelOutlineBtnTop').textContent='CANCEL';el('downloadPdfBtn').disabled=true;el('backToDealerBtn').disabled=true;
 el('reportOutlineControls').classList.add('measurement-correction-controls');el('reportOutlineControls').closest('.reportPanel').classList.add('correction-panel');el('customerMap').classList.add('correcting-measurement');
 c.touchGuard=e=>{if(e.touches?.length===1&&e.cancelable)e.preventDefault()};el('customerMap').addEventListener('touchmove',c.touchGuard,{passive:false});
 redrawReportCorrection();
}
function redrawSelectedReportMeasurement(){const c=reportMeasurementCorrection;if(!c||c.saving||c.uncertain)return;c.history.push(c.points.map(p=>[p.lat,p.lng]));c.points=[];c.drawing=true;c.error='';redrawReportCorrection()}
function finishReportMeasurementCorrection(){
 const c=reportMeasurementCorrection;if(!c)return;
 c.layers.forEach(l=>customerMap.removeLayer(l));customerMap.off('click',c.click);
 if(c.drag)customerMap.dragging.enable();if(c.double)customerMap.doubleClickZoom.enable();
 el('customerMap').removeEventListener('touchmove',c.touchGuard);el('customerMap').classList.remove('correcting-measurement');el('reportOutlineControls').closest('.reportPanel').classList.remove('correction-panel');
 reportMeasurementCorrection=null;el('backToDealerBtn').disabled=false;el('reportOutlineControls').classList.remove('measurement-correction-controls');el('reportRedrawBtn').style.display='none';
 setReportOutlineButtons(false);renderReportOutlineTargetButtons();
}
function cancelReportMeasurementCorrection(){
 if(!reportMeasurementCorrection||reportMeasurementCorrection.saving||reportMeasurementCorrection.uncertain)return;
 finishReportMeasurementCorrection();customerOverlays.forEach(l=>l.addTo(customerMap));layoutCustomerMeasurementLabels();
}
async function saveReportMeasurementCorrection(){
 const c=reportMeasurementCorrection;if(!c||c.saving||reportCorrectionProblem())return;
 const before=reportCorrectionWorkspace();c.saving=true;c.error='';redrawReportCorrection();
 let saved=false;
 try{
  applyReportCorrectionCandidate();const issue=quotePricingError();if(issue)throw new Error(issue);
  quoteSnapshot=captureQuoteSnapshot();saved=await saveEstimateHistory();
  if(!saved){c.uncertain=!saveEstimateHistory.lastFailureStatus||saveEstimateHistory.lastFailureStatus>=500;throw new Error(c.uncertain?'The save result could not be confirmed. Retry SAVE to safely confirm the same request before editing or cancelling. Your original and draft are retained.':el('status')?.textContent||'Estimate not saved. Retry Save or Cancel; the original is protected.')}
 }catch(e){restoreReportCorrectionWorkspace(before);c.saving=false;c.error=e.message;redrawReportCorrection();return}
 finishReportMeasurementCorrection();renderSummary();redrawAreaMeasure();commercialAreaDrawSaved();redrawLinearMeasure();
 await showCustomerEstimate(false,'',true);
}
function renderReportOutlineTargetButtons(){
 const box=el('reportOutlineTargetButtons');if(!box)return;
 const snap=quoteSnapshot||captureQuoteSnapshot();let html='';
 if(surfaceIndustry()){
  (snap.commercialAreas||[]).forEach((area,i)=>{if(area.points?.length>=3)html+=`<button class="orange" onclick="correctSavedMeasurementFromReport('area',${i})">RETRACE OUTLINE â€” AREA ${i+1}</button>`});
  if(snap.linearPoints?.length>=2)html+=`<button class="orange" onclick="correctSavedMeasurementFromReport('linear')">CORRECT LINEAR MEASUREMENT</button>`;
  box.innerHTML=html||'<span class="small">No saved measurement available to correct.</span>';
  if(el('reportOutlineHelpTop'))el('reportOutlineHelpTop').textContent='Choose a measurement to correct here. Save confirms the displayed quantity and price change. Cancel keeps the original.';
  return;
 }
 (snap.structures||[]).forEach((st,i)=>{
   const key=`structure-${i}`;
   const label=i===0?'EDIT MAIN HOUSE OUTLINE':`EDIT ${reportTargetLabel(key)} OUTLINE`;
   html+=`<button class="orange" onclick="startReportOutlineEdit('${key}')">${label}</button>`;
 });
 (snap.manualPlanes||[]).forEach((p,i)=>{
   const key=`manual-${i}`;
   html+=`<button class="orange" onclick="startReportOutlineEdit('${key}')">EDIT ${reportTargetLabel(key)} OUTLINE</button>`;
 });
 if(snap.measurementMode==='linear'&&snap.linearPoints&&snap.linearPoints.length>=2){html='<button class="orange" onclick="startVisualMeasurementCorrection(\'linear\')">CORRECT MEASUREMENT LINE</button>';if(el('reportOutlineHelpTop'))el('reportOutlineHelpTop').textContent='Adjust the line directly on this image. Measured length and price stay unchanged.';}
 if(snap.measurementMode==='area'&&snap.areaPoints&&snap.areaPoints.length>=3){html='<button class="orange" onclick="startVisualMeasurementCorrection(\'area\')">CORRECT MEASUREMENT OUTLINE</button>';if(el('reportOutlineHelpTop'))el('reportOutlineHelpTop').textContent='Adjust the outline directly on this image. Measured area and price stay unchanged.';}
 box.innerHTML=html||'<span class="small">No roof outline available to edit.</span>';
}
function setReportOutlineButtons(editing){if(el('reportOutlineTargetButtons'))el('reportOutlineTargetButtons').style.display=editing?'none':'flex';if(el('reportCancelOutlineBtnTop'))el('reportCancelOutlineBtnTop').style.display=editing?'inline-block':'none';if(el('reportUndoOutlineBtnTop'))el('reportUndoOutlineBtnTop').style.display=editing?'inline-block':'none';if(el('reportSaveOutlineBtnTop')){el('reportSaveOutlineBtnTop').style.display=editing?'inline-block':'none';el('reportSaveOutlineBtnTop').disabled=reportOutlinePoints.length<3}if(el('downloadPdfBtn'))el('downloadPdfBtn').disabled=!!editing;const msg=editing?`Editing ${reportTargetLabel(reportOutlineTarget)}. Click each corner on the final estimate image, then SAVE OUTLINE. The PDF button unlocks after the outline is saved.`:'Choose which roof outline to edit. Main house and added roofs can be edited separately. Picture only â€” measurements and price stay unchanged.';['reportOutlineHelp','reportOutlineHelpTop'].forEach(id=>{if(el(id))el(id).textContent=msg});const svg=el('reportDrawLayer');if(svg){svg.classList.toggle('active',!!editing);if(editing)syncReportDrawLayer()}}
function reportOutlinePointer(e){if(!reportOutlineEditMode||!customerMap)return;e.preventDefault();e.stopPropagation();const svg=el('reportDrawLayer'),r=svg.getBoundingClientRect(),pt=L.point(e.clientX-r.left,e.clientY-r.top);reportOutlinePoints.push(customerMap.containerPointToLatLng(pt));drawReportOutlineTemp();setReportOutlineButtons(true)}
function reportOutlineClick(e){if(!reportOutlineEditMode)return}
async function startReportOutlineEdit(target){
 if(el('streetViewChoice')?.value==='none'){
   if(el('reportOutlineHelpTop'))el('reportOutlineHelpTop').textContent='Turn estimate images on to edit roof outlines.';return
 }
 // A pure manual estimate is normally a pixel-locked baked image. If the
 // dealer chooses to edit that outline, temporarily open the interactive map
 // for drawing; SAVE OUTLINE rebuilds the pixel-locked customer image again.
 if(!customerMap){
   const snap=quoteSnapshot||captureQuoteSnapshot();
   const pureManual=(snap.measureSource==='manual'&&(snap.manualPlanes||[]).length>0&&!(snap.structures||[]).length);
   if(pureManual){
     try{await buildInteractiveCustomerMap()}catch(e){console.error('AQ:outline-editor-failed');if(el('reportOutlineHelpTop'))el('reportOutlineHelpTop').textContent='Could not open outline editor. Close and reopen the estimate, then try again.';return}
   }
 }
 if(!customerMap){if(el('reportOutlineHelpTop'))el('reportOutlineHelpTop').textContent='Turn estimate images on to edit roof outlines.';return}
 reportOutlineTarget=target;reportOutlineEditMode=true;reportOutlinePoints=[];clearReportOutlineTemp();
 // Hide ONLY the roof being edited. Every other roof stays visible as a reference.
 customerOverlays.forEach(layer=>{
   try{
     if(layer&&layer._reportRoofKey===target&&layer.setStyle)layer.setStyle({opacity:0,fillOpacity:0});
     if(layer&&layer._reportRoofKey===target&&layer.setOpacity)layer.setOpacity(0);
   }catch(e){}
 });
 document.querySelector('#reportOverlay .report')?.classList.add('estimate-editing');setReportOutlineButtons(true);
 const svg=el('reportDrawLayer');if(svg&&!svg.dataset.bound){svg.addEventListener('pointerdown',reportOutlinePointer);svg.dataset.bound='1'}
}
function cancelReportOutlineEdit(){if(reportMeasurementCorrection){cancelReportMeasurementCorrection();return}if(visualCorrectionMode){clearVisualCorrection();buildCustomerMap().catch(e=>console.error('AQ:outline-render-failed'));setReportOutlineButtons(false);if(el('reportSaveOutlineBtnTop'))el('reportSaveOutlineBtnTop').textContent='SAVE OUTLINE';return}reportOutlineEditMode=false;reportOutlinePoints=[];clearReportOutlineTemp();document.querySelector('#reportOverlay .report')?.classList.remove('estimate-editing');setReportOutlineButtons(false);buildCustomerMap().catch(e=>console.error('AQ:outline-render-failed'))}
function undoReportOutlinePoint(){if(reportMeasurementCorrection){const c=reportMeasurementCorrection;if(!c.saving&&!c.uncertain&&c.history.length){c.points=c.history.pop().map(p=>L.latLng(p));c.error="";redrawReportCorrection()}return}if(visualCorrectionMode){const m=visualCorrectionMarkers.pop();if(m)customerMap.removeLayer(m);refreshVisualCorrectionLine();return;}if(!reportOutlineEditMode||!reportOutlinePoints.length)return;reportOutlinePoints.pop();drawReportOutlineTemp();setReportOutlineButtons(true)}
async function saveReportOutline(){if(reportMeasurementCorrection){await saveReportMeasurementCorrection();return}if(visualCorrectionMode){saveVisualCorrection().catch(e=>console.error('AQ:outline-render-failed'));return}if(!reportOutlineEditMode||reportOutlinePoints.length<3||!reportOutlineTarget)return;const target=reportOutlineTarget,label=reportTargetLabel(target);reportOutlines[target]=reportOutlinePoints.map(p=>[p.lat,p.lng]);reportOutlineEditMode=false;reportOutlinePoints=[];clearReportOutlineTemp();document.querySelector('#reportOverlay .report')?.classList.remove('estimate-editing');await buildCustomerMap();setReportOutlineButtons(false);if(el('reportOutlineHelpTop'))el('reportOutlineHelpTop').textContent=`âœ“ ${label} outline saved. You can now edit another roof. Measurements and price are unchanged.`}

async function buildExactPinCustomerSnapshot(){
 const host=el('customerMap');if(!host||!sessionToken)return;
 if(customerMap){try{customerMap.remove()}catch(e){}customerMap=null;customerRgbLayer=null;customerOverlays=[]}
 host.innerHTML='';host.style.position='relative';host.style.overflow='hidden';

 const snap=quoteSnapshot||captureQuoteSnapshot();
 const roofs=[];

 (snap.structures||[]).forEach((st,i)=>{
   const key=`structure-${i}`;
   let pts=(Array.isArray(reportOutlines[key])&&reportOutlines[key].length>=3)?reportOutlines[key]:st.outline;
   if(Array.isArray(pts)&&pts.length>=3){
     roofs.push({
       kind:i===0?'house':'garage',
       points:pts.map(v=>({lat:Number(v.lat!==undefined?v.lat:v[0]),lng:Number(v.lng!==undefined?v.lng:v[1])}))
     });
   }
 });

 (snap.manualPlanes||[]).forEach((p,i)=>{
   const key=`manual-${i}`;
   let pts=(Array.isArray(reportOutlines[key])&&reportOutlines[key].length>=3)?reportOutlines[key]:p.points;
   if(Array.isArray(pts)&&pts.length>=3){
     roofs.push({
       kind:'manual',
       points:pts.map(v=>({lat:Number(v.lat!==undefined?v.lat:v[0]),lng:Number(v.lng!==undefined?v.lng:v[1])}))
     });
   }
 });

 if(!roofs.length)throw new Error('No roof outline is available for the exact-pin estimate.');

 const r=await fetch('/exact-pin-report-map/'+sessionToken,{
   method:'POST',
   headers:{'Content-Type':'application/json'},
   body:JSON.stringify({roofs})
 });
 if(!r.ok)throw new Error((await r.text())||'Could not create exact-pin estimate aerial.');

 const blob=await r.blob(),obj=URL.createObjectURL(blob);
 try{
   const img=await new Promise((resolve,reject)=>{
     const im=new Image();
     im.onload=()=>resolve(im);
     im.onerror=()=>reject(new Error('Exact-pin estimate aerial could not be decoded.'));
     im.src=obj;
   });
   const canvas=document.createElement('canvas');
   canvas.width=img.naturalWidth||1280;
   canvas.height=img.naturalHeight||840;
   canvas.style.width='100%';
   canvas.style.height='100%';
   canvas.style.display='block';
   canvas.getContext('2d').drawImage(img,0,0,canvas.width,canvas.height);
   host.appendChild(canvas);
 }finally{try{URL.revokeObjectURL(obj)}catch(e){}}
}

async function buildManualCustomerSnapshot(){
 const host=el('customerMap');if(!host||!sessionToken)return;
 if(customerMap){try{customerMap.remove()}catch(e){}customerMap=null;customerRgbLayer=null;customerOverlays=[]}
 host.innerHTML='';host.style.position='relative';host.style.overflow='hidden';
 // Manual reports are rendered by Google as ONE satellite image with the dealer trace
 // baked into the image. This is the proven manual-PDF path from the earlier working build.
 const snap=quoteSnapshot||captureQuoteSnapshot();
 const planes=(snap.manualPlanes||[]).map((p,i)=>{
   const key=`manual-${i}`;
   const pts=(Array.isArray(reportOutlines[key])&&reportOutlines[key].length>=3)?reportOutlines[key]:p.points;
   return Array.isArray(pts)?pts.map(v=>({lat:Number(v.lat!==undefined?v.lat:v[0]),lng:Number(v.lng!==undefined?v.lng:v[1])})):[];
 }).filter(pts=>pts.length>=3);
 if(!planes.length)throw new Error('No saved manual roof outline is available for the report.');
 const r=await fetch('/manual-report-map/'+sessionToken,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({planes})});
 if(!r.ok)throw new Error((await r.text())||'Could not create manual report aerial.');
 const view=JSON.parse(r.headers.get('X-AeriQuote-Map-View')||'null');if(!view)throw new Error('Manual report aerial is missing its map view.');
 const blob=await r.blob(),obj=URL.createObjectURL(blob);
 try{
   const img=await new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(new Error('Manual report aerial could not be decoded.'));im.src=obj});
   const canvas=document.createElement('canvas');canvas.width=img.naturalWidth||1280;canvas.height=img.naturalHeight||840;canvas.style.width='100%';canvas.style.height='100%';canvas.style.display='block';
   const ctx=canvas.getContext('2d');ctx.drawImage(img,0,0,canvas.width,canvas.height);
   const labeledSnap={...snap,manualPlanes:(snap.manualPlanes||[]).map((p,i)=>({...p,points:reportOutlines['manual-'+i]||p.points}))};
   drawSavedMeasurementLabels(ctx,labeledSnap,view,canvas.width,canvas.height);host.appendChild(canvas);
 }finally{try{URL.revokeObjectURL(obj)}catch(e){}}
}
async function loadCustomerWideAerial(token,targetMap){
 // Use one continuous satellite image for estimates instead of a raster tile mosaic.
 const snap=activeSavedDiagramSnapshot(quoteSnapshot||captureQuoteSnapshot()),pts=[];
 (snap.commercialAreas||[]).forEach(a=>(a.points||[]).forEach(p=>pts.push(L.latLng(p[0],p[1]))));
 (snap.areaPoints||[]).forEach(p=>pts.push(L.latLng(p[0],p[1])));
 (snap.linearPoints||[]).forEach(p=>pts.push(L.latLng(p[0],p[1])));
 (snap.structures||[]).forEach(st=>(st.outline||[]).forEach(p=>pts.push(L.latLng(p.lat!==undefined?p.lat:p[0],p.lng!==undefined?p.lng:p[1]))));
 (snap.manualPlanes||[]).forEach(st=>(st.points||[]).forEach(p=>pts.push(L.latLng(p.lat!==undefined?p.lat:p[0],p.lng!==undefined?p.lng:p[1]))));
 const center=pts.length?L.latLngBounds(pts).getCenter():(propertyMarker?.getLatLng?.()||map.getCenter());
 const extent=pts.length?L.latLngBounds(pts):null;
 let zoom=18;if(extent)for(zoom=20;zoom>15;zoom--){const nw=map.project(extent.getNorthWest(),zoom),se=map.project(extent.getSouthEast(),zoom);if(Math.abs(se.x-nw.x)<=500&&Math.abs(se.y-nw.y)<=340)break}
 const qs=new URLSearchParams({lat:String(center.lat),lng:String(center.lng),zoom:String(zoom)});
 const response=await fetch('/wide-aerial/'+token+'?'+qs.toString());
 if(!response.ok)throw new Error('Wide estimate aerial unavailable');
 const blob=await response.blob();
 const dataUrl=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(new Error('Could not decode estimate aerial'));reader.readAsDataURL(blob)});
 const bounds=staticMapBounds(center.lat,center.lng,zoom,640,640);
 const layer=L.imageOverlay(dataUrl,bounds,{opacity:1,interactive:false});
 await new Promise((resolve,reject)=>{layer.once('load',resolve);layer.once('error',()=>reject(new Error('Wide estimate image failed to load')));layer.addTo(targetMap)});
 return{layer,bounds};
}
function measurementLabelPosition(x,y,w,h,occupied,width,height,gap=4){
 const clamp=(v,lo,hi)=>Math.max(lo,Math.min(hi,v));let best=null;
 for(let radius=0;radius<=260;radius+=26){
  const offsets=radius?[[0,-radius],[0,radius],[-radius,0],[radius,0],[-radius,-radius],[radius,-radius],[-radius,radius],[radius,radius]]:[[0,0]];
  for(const [dx,dy] of offsets){const cx=clamp(x+dx,w/2+gap,width-w/2-gap),cy=clamp(y+dy,h/2+gap,height-h/2-gap),box={x:cx-w/2,y:cy-h/2,w,h};
   const overlap=occupied.reduce((n,b)=>n+Math.max(0,Math.min(box.x+w+gap,b.x+b.w)-Math.max(box.x-gap,b.x))*Math.max(0,Math.min(box.y+h+gap,b.y+b.h)-Math.max(box.y-gap,b.y)),0);
   if(!best||overlap<best.overlap)best={...box,overlap};if(!overlap){occupied.push(box);return box}
  }
 }occupied.push(best);return best;
}
function layoutCustomerMeasurementLabels(){
 if(!customerMap)return;const occupied=[],size=customerMap.getSize();
 const labels=customerOverlays.map(layer=>({layer,node:layer.getElement?.()?.querySelector('.aeri-edge-label,.linear-seg-label,.area-label,.edge-label,.seg-label,.manual-label')})).filter(a=>a.node);
 labels.sort((a,b)=>Number(b.node.classList.contains('area-label'))-Number(a.node.classList.contains('area-label')));
 labels.forEach(({layer,node})=>{if(node.dataset.roofSummary){layer.getElement().querySelector('.measurement-label-leader')?.remove();return}const marker=layer.getElement(),pt=customerMap.latLngToContainerPoint(layer.getLatLng()),w=node.offsetWidth||node.textContent.length*7+14,h=node.offsetHeight||26,box=measurementLabelPosition(pt.x,pt.y,w,h,occupied,size.x,size.y);
  marker.style.marginLeft='0';marker.style.marginTop='0';Object.assign(node.style,{position:'absolute',left:(box.x-pt.x)+'px',top:(box.y-pt.y)+'px',transform:'none',width:'max-content'});
  marker.querySelector('.measurement-label-leader')?.remove();const dx=box.x+w/2-pt.x,dy=box.y+h/2-pt.y;
  if(Math.hypot(dx,dy)>4){const leader=document.createElement('div');leader.className='measurement-label-leader';Object.assign(leader.style,{position:'absolute',left:'0',top:'0',width:Math.hypot(dx,dy)+'px',height:'1px',background:'#46576b',transformOrigin:'0 0',transform:'rotate('+Math.atan2(dy,dx)+'rad)',pointerEvents:'none',zIndex:'-1'});marker.prepend(leader)}
 });
}
function drawCustomerAreaEdgeLabels(points,targetMap=customerMap,targetList=customerOverlays){
 if(!targetMap||!Array.isArray(points)||points.length<3)return;
 const pts=points.map(p=>L.latLng(p[0]!==undefined?p[0]:p.lat,p[1]!==undefined?p[1]:p.lng));
 for(let i=0;i<pts.length;i++){
  const a=pts[i],b=pts[(i+1)%pts.length],feet=targetMap.distance(a,b)*3.28084;
  const mid=L.latLng((a.lat+b.lat)/2,(a.lng+b.lng)/2);
  const label=feet<100?feet.toFixed(1):Math.round(feet).toLocaleString();
  targetList.push(L.marker(mid,{interactive:false,keyboard:false,icon:L.divIcon({className:'aeri-edge-label-icon',html:'<span class="aeri-edge-label">'+label+' ft</span>',iconSize:[90,24],iconAnchor:[45,12]})}).addTo(targetMap));
 }
}
async function buildInteractiveCustomerMap(){
 if(!sessionToken)return;
 const imageChoice=el('streetViewChoice')?.value||'auto';
 const useAerial=imageChoice!=='none';
 if(el('customerMap'))el('customerMap').style.display=useAerial?'block':'none';
 if(el('customerMapPlaceholder'))el('customerMapPlaceholder').style.display=useAerial?'none':'flex';
 if(el('reportOutlineControls'))el('reportOutlineControls').style.display=useAerial?'flex':'none';if(useAerial)renderReportOutlineTargetButtons();
 if(!useAerial){if(customerMap){customerMap.remove();customerMap=null;customerRgbLayer=null;customerOverlays=[]}return}
 if(customerMap){customerMap.remove();customerMap=null;customerRgbLayer=null;customerOverlays=[]}
 customerMap=L.map('customerMap',{zoomControl:false,attributionControl:false,zoomSnap:.25}).setView([52.1522,-106.6595],19);
 customerMap.on('click',reportOutlineClick);customerMap.on('moveend zoomend',layoutCustomerMeasurementLabels);
 await new Promise(r=>setTimeout(r,180));
 customerMap.invalidateSize(true);
 let rgb;if(exactPinDisplay)rgb=await loadExactPinAerial(sessionToken,customerMap);else if(fallbackMode)rgb=await loadCustomerWideAerial(sessionToken,customerMap);else{try{rgb=await loadCustomerWideAerial(sessionToken,customerMap)}catch(e){console.warn('AQ:wide-image-fallback');rgb=await loadRaster('/rgb/'+sessionToken,customerMap)}}
 customerRgbLayer=rgb.layer;
 customerMap.invalidateSize(true);
 frameAerial(customerMap,rgb.bounds,0);
 await new Promise(r=>setTimeout(r,220));
 customerMap.invalidateSize(true);
 frameAerial(customerMap,rgb.bounds,0);
 const snap=activeSavedDiagramSnapshot(quoteSnapshot||captureQuoteSnapshot());
 // Draw saved area and linear outlines together on the customer estimate and PDF.
 const hasArea=(snap.commercialAreas||[]).some(a=>a.points?.length>=3)||(Array.isArray(snap.areaPoints)&&snap.areaPoints.length>=3);
 const hasLinear=Array.isArray(snap.linearPoints)&&snap.linearPoints.length>=2;
 if(hasArea||hasLinear){
  if(el('reportOutlineControls'))el('reportOutlineControls').style.display='flex';
  renderReportOutlineTargetButtons();
  const allBounds=[];
  if(hasArea){
   // Commercial estimates can contain multiple independent saved service polygons.
   const areas=(Array.isArray(snap.commercialAreas)&&snap.commercialAreas.some(a=>Array.isArray(a.points)&&a.points.length>=3))
    ?snap.commercialAreas.filter(a=>Array.isArray(a.points)&&a.points.length>=3):[];
   if(areas.length){
    areas.forEach((area,i)=>{
     const overlayStart=customerOverlays.length;
     const pts=area.points.map(p=>L.latLng(p[0],p[1]));
     const poly=L.polygon(pts,{color:'#7357b8',weight:5,fillColor:'#7357b8',fillOpacity:.14,interactive:false,lineJoin:'round'}).addTo(customerMap);
     customerOverlays.push(poly);allBounds.push(...pts);drawCustomerAreaEdgeLabels(area.points);
     customerOverlays.push(L.marker(poly.getBounds().getCenter(),{interactive:false,icon:L.divIcon({className:'',html:`<div class="area-label">${fmt(Number(area.sqft||0))} ftÂ²</div>`,iconAnchor:[35,10]})}).addTo(customerMap));
     customerOverlays.slice(overlayStart).forEach(l=>l._reportMeasurement={mode:'area',index:snap.commercialAreas.indexOf(area)});
    });
   }else{
   const overlayStart=customerOverlays.length;
   const pts=(reportOutlines['area-visual']||snap.areaPoints).map(p=>L.latLng(p[0],p[1]));
   const poly=L.polygon(pts,{color:'#7357b8',weight:5,fillColor:'#7357b8',fillOpacity:.14,interactive:false,lineJoin:'round'}).addTo(customerMap);
   customerOverlays.push(poly);allBounds.push(...pts);drawCustomerAreaEdgeLabels(reportOutlines['area-visual']||snap.areaPoints);
   const lab=L.marker(poly.getBounds().getCenter(),{interactive:false,icon:L.divIcon({className:'',html:`<div class="area-label">${fmt(Number(snap.areaSqFt||0))} ftÂ²</div>`,iconAnchor:[35,10]})}).addTo(customerMap);
   customerOverlays.push(lab);
   customerOverlays.slice(overlayStart).forEach(l=>l._reportMeasurement={mode:'area',index:0});
   }
  }
  if(hasLinear){
   const overlayStart=customerOverlays.length;
   const pts=(reportOutlines['linear-visual']||snap.linearPoints).map(p=>L.latLng(p[0],p[1]));
   allBounds.push(...pts);
   for(let i=1;i<pts.length;i++){
    const a=pts[i-1],b=pts[i],feet=customerMap.distance(a,b)*3.28084;
    customerOverlays.push(L.polyline([a,b],{color:'#0f8f83',weight:5,opacity:.95,lineCap:'round'}).addTo(customerMap));
    const mid=L.latLng((a.lat+b.lat)/2,(a.lng+b.lng)/2);
    customerOverlays.push(L.marker(mid,{interactive:false,icon:L.divIcon({className:'',html:`<div class="linear-seg-label">${feet.toFixed(1)} ft</div>`,iconAnchor:[24,9]})}).addTo(customerMap));
   }
   pts.forEach(pt=>customerOverlays.push(L.marker(pt,{interactive:false,icon:L.divIcon({className:'',html:'<div class="linear-point"></div>',iconAnchor:[6,6]})}).addTo(customerMap)));
   customerOverlays.slice(overlayStart).forEach(l=>l._reportMeasurement={mode:'linear'});
  }
  try{customerMap.fitBounds(L.latLngBounds(allBounds).pad(0.12),{padding:[24,24],animate:false,maxZoom:21.5})}catch(e){}
  layoutCustomerMeasurementLabels();return;
 }
 const reportStructures=snap.structures||[], reportManual=snap.manualPlanes||[];
 reportStructures.forEach((st,i)=>{
   const key=`structure-${i}`,custom=Array.isArray(reportOutlines[key])&&reportOutlines[key].length>=3;
   const before=customerOverlays.length;
   drawSegments(st,i===0?'house':'garage',customerMap,customerOverlays,custom);
   customerOverlays.slice(before).forEach(layer=>{try{layer._reportRoofKey=key}catch(e){}});
   if(custom){
     const color=i===0?'#2d6cdf':'#169a8f';
     let poly=L.polygon(reportOutlines[key],{color,weight:4,fillColor:color,fillOpacity:.08,interactive:false,lineJoin:'round',smoothFactor:1.5}).addTo(customerMap);
     poly._reportRoofKey=key;customerOverlays.push(poly)
   }
   // V11.6.67 â€” CUSTOMER ESTIMATE EDGE DIMENSIONS
   // Carry the approved perimeter dimensions into the customer estimate aerial.
   // Keep corners off here so the report stays cleaner than the dealer workspace.
   const estimateOutline=custom?reportOutlines[key]:((i===0&&Array.isArray(adjustedOutline)&&adjustedOutline.length>=3)?adjustedOutline:st.outline);
   if(reportStructures.length<=3&&Array.isArray(estimateOutline)&&estimateOutline.length>=3)drawEdgeMeasurements(estimateOutline,i===0?'#2d6cdf':'#18a7a0',customerMap,customerOverlays,false);
 });
 reportManual.forEach((p,i)=>{
   const key=`manual-${i}`,pts=(Array.isArray(reportOutlines[key])&&reportOutlines[key].length>=3)?reportOutlines[key]:p.points;
   let poly=L.polygon(pts,{color:'#d97706',weight:3,fillColor:'#f59e0b',fillOpacity:.12,interactive:false,lineJoin:'round'}).addTo(customerMap);
   poly._reportRoofKey=key;customerOverlays.push(poly)
 });
 // CUSTOMER ESTIMATE DYNAMIC AERIAL FRAMING
 // Frame every roof that is actually in the frozen quote. A single home gets a
 // closer useful view; garages and large multi-building/HOA quotes automatically
 // zoom out because fitBounds uses the combined outside bounds of all quoted roofs.
 // This changes presentation only â€” measurement geometry and pricing are untouched.
 let fitLayers=[];customerOverlays.forEach(x=>{try{if(x.getBounds)fitLayers.push(x)}catch(e){}});
 if(fitLayers.length){
   try{
     const quotedBounds=L.featureGroup(fitLayers).getBounds();
     if(quotedBounds&&quotedBounds.isValid()){
       customerMap.fitBounds(quotedBounds.pad(0.06),{padding:[20,20],animate:false,maxZoom:21.5});
     }else{fitEntireQuote(customerMap)}
   }catch(e){fitEntireQuote(customerMap)}
 }else{fitEntireQuote(customerMap)};
 layoutCustomerMeasurementLabels();
 setReportOutlineButtons(false);
}
// Project only the geometry selected by the existing pricing rules. Never mutate
// the saved snapshot: inactive families remain available in earlier revisions.
function activeSavedDiagramSnapshot(snap){
 const out={...snap,structures:[],manualPlanes:[],commercialAreas:[],areaPoints:[],linearPoints:[]};
 const surface=snap.businessType!=='roofing',mode=snap.measurementMode||'auto';
 if(surface&&(snap.commercialAreas||[]).length){
  out.commercialAreas=snap.commercialAreas;
  if(Number(snap.linearFeet)>0)out.linearPoints=snap.linearPoints||[];
 }else if(mode==='area')out.areaPoints=snap.areaPoints||[];
 else if(mode==='linear'){
  out.linearPoints=snap.linearPoints||[];
  if(surface&&snap[snap.businessType+'Combined'])out.areaPoints=snap.areaPoints||[];
 }else if(mode==='auto'){
  const source=snap.measureSource||'google',planes=snap.manualPlanes||[],roofs=snap.structures||[];
  if(source==='manual'){if(planes.reduce((n,p)=>n+Number(p.surface_sqft||0),0)>0)out.manualPlanes=planes;else out.structures=roofs}
  else if(source==='hybrid'){out.structures=roofs;out.manualPlanes=planes}
  else if(source==='google'||source==='adjusted')out.structures=roofs;
  else throw new Error('Saved estimate measurement source is unavailable. Review its measurements before export.');
 }else throw new Error('Saved estimate measurement mode is unavailable. Review its measurements before export.');
 return out;
}
function savedDiagramGeometryError(snapshot){
 if(!snapshot)return '';
 try{
  const snap=activeSavedDiagramSnapshot(snapshot),areas=snap.commercialAreas.length?snap.commercialAreas:(snap.areaPoints.length||Number(snap.areaSqFt)>0&&snap.measurementMode==='area'?[{points:snap.areaPoints,sqft:snap.areaSqFt}]:[]);
  if(areas.length){if(areas.some(a=>!Number.isFinite(Number(a.sqft))||Number(a.sqft)<=0))return 'Saved area quantity is invalid. Review the saved estimate before export.';const issue=savedAreaGeometryError(areas);if(issue)return issue;}
  if(snap.linearPoints.length||Number(snap.linearFeet)>0&&(snap.measurementMode==='linear'||snap.commercialAreas.length)){const issue=savedLinearGeometryError(snap.linearPoints,Number(snap.linearFeet));if(issue)return issue;}
  if(!areas.length&&!snap.linearPoints.length&&!snap.structures.length&&!snap.manualPlanes.length)return 'Saved estimate has no active measurement geometry. Review its measurements before export.';
  if(snapshot.savedPricing&&areas.length&&snap.measurementMode!=='linear'){
   const quantity=areas.reduce((n,a)=>n+Number(a.sqft),0);
   if(!Number.isFinite(Number(snapshot.savedPricing.area))||Math.abs(quantity-Number(snapshot.savedPricing.area))>1)return 'Saved estimate quantity does not match its active diagram. Review the saved estimate before export.';
  }
  return '';
 }catch(e){return 'Saved estimate diagram cannot be reconciled with its measurements. Review the saved estimate before export.'}
}
function savedDiagramFingerprint(snap){const active=activeSavedDiagramSnapshot(snap);return JSON.stringify([active.businessType,active.measurementMode,active.measureSource,active.structures,active.manualPlanes,active.commercialAreas,active.areaPoints,active.linearPoints,active.areaSqFt,active.linearFeet])}
function drawSavedMeasurementLabels(ctx,snap,view,width,height){
 snap=activeSavedDiagramSnapshot(snap);
 const occupied=[];const world=256*Math.pow(2,view.zoom),xy=p=>{const lat=Number(p[0]??p.lat),lng=Number(p[1]??p.lng),v=Math.sin(lat*Math.PI/180);return[(lng+180)/360*world,(.5-Math.log((1+v)/(1-v))/(4*Math.PI))*world]},center=xy([view.latitude,view.longitude]);
 const pixel=p=>{const q=xy(p);return[width/2+(q[0]-center[0])*width/view.width,height/2+(q[1]-center[1])*height/view.height]};
 const label=(point,text,color,anchored=false)=>{const [px,py]=pixel(point);ctx.save();ctx.font='bold 20px Arial';ctx.textAlign='center';ctx.textBaseline='middle';const w=ctx.measureText(text).width+14,box=anchored?{x:px-w/2,y:py-14}:measurementLabelPosition(px,py,w,28,occupied,width,height,8),x=box.x+w/2,y=box.y+14;ctx.strokeStyle=color;ctx.lineWidth=1;if(!anchored&&Math.hypot(x-px,y-py)>4){ctx.beginPath();ctx.moveTo(px,py);ctx.lineTo(x,y);ctx.stroke()}ctx.fillStyle='#fff';ctx.fillRect(box.x,box.y,w,28);ctx.strokeRect(box.x,box.y,w,28);ctx.fillStyle=color;ctx.fillText(text,x,y);ctx.restore()};
 const edges=(points,closed,color)=>{for(let i=1;i<points.length+(closed?1:0);i++){const a=points[i-1],b=points[i%points.length],feet=L.latLng(a).distanceTo(L.latLng(b))*3.28084;label([(a[0]+b[0])/2,(a[1]+b[1])/2],(feet<100?feet.toFixed(1):Math.round(feet).toLocaleString())+' ft',color)}};
 const areas=(snap.commercialAreas||[]).filter(a=>a.points?.length>=3);
 (areas.length?areas:[{points:snap.areaPoints||[],sqft:snap.areaSqFt}]).forEach(a=>{if(a.points.length<3)return;edges(a.points,true,'#7357b8');const lats=a.points.map(p=>p[0]),lngs=a.points.map(p=>p[1]);if(Number(a.sqft)>0)label([(Math.min(...lats)+Math.max(...lats))/2,(Math.min(...lngs)+Math.max(...lngs))/2],fmt(a.sqft)+' ftÂ²','#7357b8')});
 if(snap.linearPoints?.length>=2)edges(snap.linearPoints,false,'#0f8f83');
 (snap.structures||[]).forEach((st,i)=>{
  if((snap.structures||[]).length>3){label([st.latitude,st.longitude],'#'+(i+1)+' Â· '+fmt(st.total_roof_sqft)+' ftÂ²',st.manually_measured?'#d97706':i===0?'#2d6cdf':'#18a7a0',true);return}
  const color=st.manually_measured?'#d97706':i===0?'#2d6cdf':'#18a7a0',points=(st.outline||[]).map(p=>[Number(p.lat??p[0]),Number(p.lng??p[1])]);if(points.length>=3)edges(points,true,color);
  (st.segments||[]).forEach(seg=>{const c=seg.center,b=seg.bounding_box;const point=c?[c.latitude,c.longitude]:b?.sw&&b?.ne?[(b.sw.latitude+b.ne.latitude)/2,(b.sw.longitude+b.ne.longitude)/2]:null;if(point&&Number.isFinite(Number(seg.pitch_degrees)))label(point,Number(seg.pitch_degrees).toFixed(1)+'Â°','#7a3f08')});
 });
 (snap.manualPlanes||[]).forEach(st=>{const points=(st.points||[]).map(p=>[Number(p.lat??p[0]),Number(p.lng??p[1])]);if(points.length<3)return;edges(points,true,'#d97706');const bounds=L.latLngBounds(points).getCenter();label([bounds.lat,bounds.lng],Number(st.pitch_degrees||0).toFixed(1)+'Â°','#7a3f08')});
 return occupied;
}
async function buildSavedHistoricalSnapshot(){
 const host=el('customerMap');if(!host)return;
 if(customerMap){try{customerMap.remove()}catch(e){}customerMap=null;customerRgbLayer=null;customerOverlays=[]}
 host.innerHTML='';host.style.position='relative';host.style.overflow='hidden';host.style.display='flex';host.style.alignItems='center';host.style.justifyContent='center';
 const original=quoteSnapshot||captureQuoteSnapshot(),issue=savedDiagramGeometryError(original);if(issue)throw new Error(issue);
 const snap=activeSavedDiagramSnapshot(original),roofs=[];
 (snap.structures||[]).forEach((st,i)=>{
   const pts=st.outline;
   if(Array.isArray(pts)&&pts.length>=3)roofs.push({kind:st.manually_measured?'manual':i===0?'house':'garage',points:pts.map(v=>({lat:Number(v.lat!==undefined?v.lat:v[0]),lng:Number(v.lng!==undefined?v.lng:v[1])}))});
 });
 (snap.manualPlanes||[]).forEach(p=>{
   const pts=p.points;
   if(Array.isArray(pts)&&pts.length>=3)roofs.push({kind:'manual',points:pts.map(v=>({lat:Number(v.lat!==undefined?v.lat:v[0]),lng:Number(v.lng!==undefined?v.lng:v[1])}))});
 });
 const areas=(snap.commercialAreas||[]).filter(a=>a.points?.length>=3);
 (areas.length?areas:[{points:snap.areaPoints||[]}]).forEach(a=>{if(a.points.length>=3)roofs.push({kind:'area',points:a.points.map(p=>({lat:p[0],lng:p[1]}))})});
 if(snap.linearPoints?.length>=2)roofs.push({kind:'linear',points:snap.linearPoints.map(p=>({lat:p[0],lng:p[1]}))});
 if(!roofs.length)throw new Error('Saved estimate has no measurement outline for the aerial image.');
 const r=await fetch('/saved-estimate-report-map',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({roofs})});
 if(!r.ok)throw new Error((await r.text())||'Could not rebuild saved estimate aerial.');
 const view=JSON.parse(r.headers.get('X-AeriQuote-Map-View')||'null');
 if(!view||![view.latitude,view.longitude,view.zoom,view.width,view.height].every(Number.isFinite))throw new Error('Saved aerial measurement coordinates are unavailable.');
 const blob=await r.blob(),obj=URL.createObjectURL(blob);
 try{
   const img=await new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(new Error('Saved estimate aerial could not be decoded.'));im.src=obj});
   const canvas=document.createElement('canvas');canvas.width=img.naturalWidth||1280;canvas.height=img.naturalHeight||840;canvas.style.width='auto';canvas.style.height='auto';canvas.style.maxWidth='100%';canvas.style.maxHeight='100%';canvas.style.flex='none';canvas.style.display='block';
   canvas.dataset.diagramScope=savedDiagramFingerprint(original);canvas.dataset.mapView=JSON.stringify(view);const ctx=canvas.getContext('2d');ctx.drawImage(img,0,0,canvas.width,canvas.height);canvas.dataset.labelBoxes=JSON.stringify(drawSavedMeasurementLabels(ctx,snap,view,canvas.width,canvas.height));host.appendChild(canvas);if(el('customerMapPlaceholder'))el('customerMapPlaceholder').style.display='none';
 }finally{try{URL.revokeObjectURL(obj)}catch(e){}}
}

async function buildCustomerMap(){
 if(!sessionToken)return;
 const imageChoice=el('streetViewChoice')?.value||'auto';
 const useAerial=imageChoice!=='none';
 const snap=activeSavedDiagramSnapshot(quoteSnapshot||captureQuoteSnapshot());
 const pureManual=(snap.measureSource==='manual'&&(snap.manualPlanes||[]).length>0&&!(snap.structures||[]).length);
 // V11.6.63 â€” MANUAL ESTIMATE PIXEL LOCK
 // For a pure dealer-manual quote, do not re-project the saved trace onto a
 // second Leaflet map. Ask Google Static Maps to render the satellite image
 // AND the dealer's saved outline in the same image. Because the imagery and
 // orange path are baked together by Google, the outline cannot drift between
 // manual measurement, customer estimate, and PDF capture.
 if(exactPinDisplay&&useAerial&&!snap.commercialAreas?.length&&!snap.areaPoints?.length&&!snap.linearPoints?.length){
   if(el('customerMap'))el('customerMap').style.display='block';
   if(el('customerMapPlaceholder'))el('customerMapPlaceholder').style.display='none';
   if(el('reportOutlineControls')){el('reportOutlineControls').style.display='none'}
   await buildExactPinCustomerSnapshot();
   setReportOutlineButtons(false);
   return;
 }
 if(pureManual&&useAerial){
   if(el('customerMap'))el('customerMap').style.display='block';
   if(el('customerMapPlaceholder'))el('customerMapPlaceholder').style.display='none';
   if(el('reportOutlineControls')){el('reportOutlineControls').style.display='flex';renderReportOutlineTargetButtons()}
   await buildManualCustomerSnapshot();
   setReportOutlineButtons(false);
   return;
 }
 return buildInteractiveCustomerMap();
}
function stableWorkspaceJSON(value){return JSON.stringify(value,function(key,v){return v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.keys(v).sort().map(k=>[k,v[k]])):v})}
function workspaceSaveFingerprint(){
 const previous=quoteSnapshot;
 try{return stableWorkspaceJSON({quote:captureQuoteSnapshot(),pricing:priceCalc(),fields:['address','customerName','customerPhone','customerEmail','customerNotes','extraServiceDescription','extraServiceAmount','streetViewChoice'].map(id=>el(id)?.value||'')})}catch(e){return null}finally{quoteSnapshot=previous}
}
window.addEventListener('beforeunload',event=>{
 if(typeof reportMeasurementCorrection!=='undefined'&&reportMeasurementCorrection){event.preventDefault();event.returnValue='';return}
 if(!sessionToken||(!areaPoints.length&&!linearPoints.length&&!structures.length&&!manualPlanes.length))return;
 if(saveEstimateHistory.cleanWorkspace&&saveEstimateHistory.cleanWorkspace===workspaceSaveFingerprint())return;
 event.preventDefault();event.returnValue='';
});
async function saveEstimateHistory(){
 if(saveEstimateHistory.inFlight)return saveEstimateHistory.inFlight;
 saveEstimateHistory.inFlight=performEstimateHistorySave();
 try{return await saveEstimateHistory.inFlight}finally{saveEstimateHistory.inFlight=null}
}
async function performEstimateHistorySave(){
 const pricingIssue=quotePricingError();if(pricingIssue){status(pricingIssue,'error');return false}
 try{
  const workspaceStamp=typeof workspaceSaveFingerprint==='function'?workspaceSaveFingerprint():null;
  if(typeof window!=='undefined'&&window.aqRecovery&&saveEstimateHistory.pending){
   const pending=saveEstimateHistory.pending,confirmed=await window.aqRecovery.confirmSave(pending.id);
   if(confirmed){saveEstimateHistory.baseVersion=confirmed.version||saveEstimateHistory.baseVersion;saveEstimateHistory.pending=null;window.aqRecovery.saved();if(pending.workspaceStamp===workspaceStamp){saveEstimateHistory.cleanWorkspace=workspaceStamp;return true}}
  }
  const calc=priceCalc(),snap=quoteSnapshot||captureQuoteSnapshot();
  let streetImageData=savedPropertyEditActive?savedStreetImageData:'';
  const imageChoice=(el('streetViewChoice')?.value||'auto');
  const payload=JSON.parse(JSON.stringify({customer_name:(el('customerName')?.value||'').trim(),customer_phone:(el('customerPhone')?.value||'').trim(),customer_email:(el('customerEmail')?.value||'').trim(),customer_notes:(el('customerNotes')?.value||'').trim(),extra_service_description:(el('extraServiceDescription')?.value||'').trim(),extra_service_amount:Math.max(0,Number(el('extraServiceAmount')?.value||0)),job_status:savedJobDetails?.job_status||'Estimate',scheduled_date:savedJobDetails?.scheduled_date||'',completion_date:savedJobDetails?.completion_date||'',amount_paid:Number(savedJobDetails?.amount_paid||0),address:(el('address')?.value||'').trim(),total_area:Number(calc.area||0),total_price:Number(calc.total||0),quote:snap,pricing:calc,measurement_mode:(snap.measurementMode||'auto'),linear_feet:Number(snap.linearFeet||0),area_sqft:Number(snap.areaSqFt||0),street_meta:(el('streetMeta')?.textContent||''),image_choice:imageChoice,street_image_data:streetImageData}));
  const requestKey=typeof stableWorkspaceJSON==='function'?stableWorkspaceJSON(payload):JSON.stringify(payload);
  if(saveEstimateHistory.pending?.requestKey!==requestKey)saveEstimateHistory.pending={requestKey,id:typeof crypto!=='undefined'&&crypto.randomUUID?crypto.randomUUID():Date.now().toString(36)+'-'+Math.random().toString(36).slice(2),payload:null};
  const operation=saveEstimateHistory.pending;if(!operation.workspaceStamp)operation.workspaceStamp=workspaceStamp;
  const imageSessionToken=sessionToken;
  if(imageChoice==='auto'&&sessionToken&&!savedPropertyEditActive){
   try{
    const sr=await fetch('/street/'+imageSessionToken+'?save=1');
    if(sr.ok){
     const blob=await sr.blob();
     streetImageData=await new Promise((resolve,reject)=>{const fr=new FileReader();fr.onload=()=>resolve(String(fr.result||''));fr.onerror=()=>reject(new Error('Street View capture failed'));fr.readAsDataURL(blob)});
    }
   }catch(e){console.warn('AQ:street-snapshot-failed')}
  }
  payload.street_image_data=streetImageData;
  if(!operation.payload)operation.payload=payload;
  const frozen=operation.payload,saveKey=JSON.stringify(frozen);
  if(saveKey===lastHistorySaveKey)return true;
  if(typeof window!=='undefined'&&window.aqRecovery&&!await window.aqRecovery.prepareSave())throw window.aqRecovery.lastError()||new Error('Recovery acknowledgement failed');
  const headers={...(typeof window!=='undefined'&&window.aqRecovery?window.aqRecovery.headers():{}),'Content-Type':'application/json','Idempotency-Key':operation.id,'X-AeriQuote-Account':el('aqAccountId')?.dataset?.accountId||''};if(saveEstimateHistory.baseVersion)headers['If-Match']=saveEstimateHistory.baseVersion;
  const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),30000);let r;
  try{r=await fetch('/api/estimates',{method:'POST',headers,body:JSON.stringify(frozen),signal:controller.signal})}finally{clearTimeout(timeout)}
  if(!r.ok){let message='';try{message=(await r.json()).error||''}catch(e){}const error=new Error(message||'save failed');error.status=r.status;throw error}
  const result=await r.json();if(!result||Array.isArray(result)||typeof result.id!=='string'||!result.id.trim()||typeof result.version!=='string'||!result.version.trim())throw new Error('Save acknowledgement unavailable');saveEstimateHistory.baseVersion=result.version;
  lastHistorySaveKey=saveKey;saveEstimateHistory.pending=null;saveEstimateHistory.cleanWorkspace=workspaceStamp;if(typeof window!=='undefined'&&window.aqRecovery)window.aqRecovery.saved();return true;
 }catch(e){saveEstimateHistory.lastFailureStatus=e.status||0;console.warn('AQ:estimate-save-failed');status(e.status===401?'Your login expired. This estimate was not saved. Keep this page open and sign in in another tab, then retry.':e.status===409?e.message:e.status>=400&&e.status<500&&e.message!=='save failed'?'Estimate not saved. '+e.message+' Your measurements are still here.':'Estimate not saved. Your measurements are still here. Check your connection, then select CREATE CUSTOMER ESTIMATE to retry.','error');return false}
}
function openEstimateHistory(){el('historyModal').classList.add('open');searchEstimateHistory()}
function closeEstimateHistory(){el('historyModal').classList.remove('open')}
async function searchEstimateHistory(){
 const q=(el('historySearch')?.value||'').trim(),box=el('historyResults');box.innerHTML='<div class="small" style="padding:14px 0">Searchingâ€¦</div>';
 try{const r=await fetch('/api/estimates?q='+encodeURIComponent(q)),d=await r.json();if(!r.ok)throw new Error(d.error||'Search failed');if(!d.length){box.innerHTML='<div class="small" style="padding:14px 0">No saved estimates found.</div>';return}
 const shown=d;
 box.innerHTML=shown.map(x=>`<div class="historyRow"><div class="historyCustomer"><b>${escapeHistory(x.customer_name||'Homeowner')}</b><div class="small">${escapeHistory(x.customer_phone||'')}${x.customer_email?' â€¢ '+escapeHistory(x.customer_email):''}</div></div><div class="historyAddress"><b>${escapeHistory(x.address||'')}</b></div><div class="historyDate">${escapeHistory((x.created_at||'').slice(0,10))}</div><div class="historyAmount"><b>${money(x.total_price||0)}</b></div><div class="historyActions"><button class="secondary" onclick="viewSavedEstimate('${x.id}')">OPEN</button><button class="ghost" onclick="viewEstimateVersions('${x.id}')">VIEW HISTORY</button></div></div>`).join('');
 }catch(e){box.innerHTML='<div class="error" style="padding:14px 0">Could not load previous estimates.</div>'}
}
async function updateJobStatus(id,value){
 const allowed=['Estimate','Booked','Completed'];if(!allowed.includes(value))return;
 try{
  const r=await fetch('/api/estimates/'+encodeURIComponent(id)+'/status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_status:value})});
  const d=await r.json();if(!r.ok)throw new Error(d.error||'Status update failed');
  status('Job status updated to '+value+'.','ok');
 }catch(e){status('Could not update job status.','error');searchEstimateHistory()}
}

function setHistoryStatusFilter(value,btn){
 historyStatusFilter=value||'All';
 document.querySelectorAll('[data-status-filter]').forEach(b=>b.classList.toggle('active',b===btn));
 searchEstimateHistory();
}
async function updateCompletionDate(id,value){
 try{const r=await fetch('/api/estimates/'+encodeURIComponent(id)+'/completion-date',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({completion_date:value||''})});const d=await r.json();if(!r.ok||!d.ok)alert(d.error||'Could not save completion date.')}catch(e){alert('Could not save completion date.')}
}
async function updateAmountPaid(id,value){
 try{const amount=Math.max(0,Number(value||0));const r=await fetch('/api/estimates/'+encodeURIComponent(id)+'/amount-paid',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({amount_paid:amount})});const d=await r.json();if(!r.ok||!d.ok){alert(d.error||'Could not save amount paid.');return}searchEstimateHistory()}catch(e){alert('Could not save amount paid.')}
}
async function updateScheduledDate(id,value){
 try{
  const r=await fetch('/api/estimates/'+encodeURIComponent(id)+'/scheduled-date',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scheduled_date:value||''})});
  const d=await r.json();
  if(!r.ok||!d.ok){alert(d.error||'Could not save scheduled date.');return}
 }catch(e){alert('Could not save scheduled date.')}
}
function escapeHistory(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function savedMeasurementSummary(p,v={}){
 const snap=p.quote||{},industry=snap.businessType||p.business_type||'',hasAreas=(snap.commercialAreas||[]).som×M»ë›Ê×¬¢h­µç\”Õ–‘–šÚÜÖL‘UÌÕÖ–Ü›SÜ™•ÖRÜ˜^ŒœÜ˜P–]V^ÔYSŒL\Î]V™QØS\ÕPÔPZÔTZÐ‘RÝÖŽY‹ÓÔËÔNÞZM‘ÒÒÛ•ÙS–VXŒXÙÌQ\QMJÛÐÛ“VR™RTST
ÙÚšPSÝLÒJÙL–ŒÔ‹Ù“šZŒNLPXÕS‘’MÑËÒ˜L–
ÕÚÖŒL™Î[ÕÕQÚšN]N[’R’KÕ•ÜÎÖ›\QZÔÑ”SST’šÕÒVQZ‘QZTÐZ”™ÙŒ–˜^•ÍUÍU\NSš–[ŒÑœ–›MÞQ\SRÎ[ÊÒ]RžU‘ŒŒP[QXXŒ”ÍQSÝZÑ’”Þ’”ZÛ]ÒR^\LRŽ”ÒÛ’Ú^ž^”L\\ÚØXØ“–Œ‘JÖPÒPÊÞÍNL‹Ò]MÝL‹ÍXÕYÛ˜Ö’ÚÙŽÝ•Ñ˜ÒÒ˜ÝLÔ‹ÎTÝÙJÍLY””ŠØ
ÙL™^•ÍŽKÍ™^’Œ‘ŠÖZ™LÛÚÍ’ÔP™Ö”PT‘˜Ü•R›[”SÒ”ÊÑÎ•NUÕ[[[›T•›XPÑLÞ\•LŒ]Ö’–ÓKÛÙ•›XTÜ\›ZÚž]S\M\QÞ’RZ”ÖVŒÌ]]MPÐ“ŽM–Ú™“S]’]”NT’\JÑSËÍÒÚÐÍšÞX™UÍV
ÊÝŒZÌÐ”’QœÍ][›
Î\T^YZMÝ˜YÝ‘YV“Í”Ö”ÜÛÓ–\“QÞ\ÑÕÜY™ÜP“ÕËÜ™STS\R^˜Ý^RPÚZÛRÚ[œQÜ›‘–^]“ÛUÖÙRšM‘Ô”ÐÍ’ÒYN“ÓÑ]ÛÜ]ÒÙ\››ÞØÛœNYÌ”˜ÝSÛÜTYÑ’XŒ”ÍYLÔ‘ÙÐÛŠÑ‹ÑÓŒL’ž™Ø›JÖTLÛÌ™’™PÙKÑ^ÚV’Ò”Ý’ÎÝ•”›Ô™™Q“›T™
ÐÖš“–QÑÒPTXÔÚ^T“MÚSUÓ™”œÕŒž’•–UŒPMžM‘ÞMÔÕ[RMÛJÕŒÞÊÍÐšNSÔ‘”ÜXÒÍÚ–˜ÝZ’Ù’šTQÒSXÐ\’TÚYJÌ^VMÞ˜ÞM‘TRÖRÎYQžPÎŠÌŠØÔÚÛÛRQZžš–QŒÔ™–R]“ÞQÑZNÔ^•Î^ÝŒ’ÔÔ™SÌ
ÞÞNÔTQTŒÙž’ÍMÛŒ“‘PÔ“^“™ÚÕ[ØU›PÕ[ÍQ‘ÝZQ”UMŠÛŒRÜRœSšÐÔÒš›MKÐÚÞJÕV›ZžRR›Ù›PPÝÔÍÕZÔÕÒËÝØÒTÌšLLšUŒŒÑ˜TYÞ’MËÐÍÓ‹ÔPÖ”MÍQ’šØÍž™ÚXÙšVŽMÕÓÙMŒÑ“MYJÕÞT^šNVÖRNŒÎ•
ÎS”ZÑŽPN“TÌ^šUÕM’ÑÙ^RÌYŠÚÙ•PÛLÞŒMRÞ\PÜMÒ’ÎLÕÓÑNÍÑ’[LT‹Ô]Uœžš–œÝ
Ö]JÌ˜ÑV^˜ŽÚÞÌ[ž›UÓU]Ú›”ÐX^MËÒÝÞÌÙŒ›“L[™›
ÐÐ”Ô‘S]N]™Y‹Òš›Ì˜T›’ÖXV]KÊÕ›–X‘ÙM‘MÕÕš[YÚœž]‘™YQ˜ÙÕSŠÙÝÍ‹ÝN]‘^SLŠÛÚÜ\’’ÒÚ”’U^”ÎJÍU\Ú\”ÛM›–ÝÙÕÜÛ‘ZPÜTUžZÞ]‹Û”šÌTÒ™]ŒYMUŒ‘Ì^[ÛU”šÌZœ›ÐÕLÔÌPÑÜÒÙÕ˜–[PTÕ˜S”œÎšÙUÍÌÝ‹ÞËÞSØÚŒŽR[˜Ù˜STYLÑŽ’ÕŒKÞLJÎMÙšSSZ^“R]ÑLZÚ\XÚ‘ŠØÔ^MR“›‘™UÑ›\”™TÛ•šŒ
ÞÚYÚÒPVT–X–ŒÛLÌËÌ[‹Ì‘‹ËÍÞ[^MËÎT’T]ZS›Ý“ÕÌÙ\˜œUÑT‘ÚŠÒÍÜZÎZQ‘’Í™™\UÙKÍ™–ÝÙ›ÙKÔYQšQÜÐNÔÐZUšÑÒZœÔÖ]]œ^Ù™œœLŠÎ\ÊÊÍ››™ÝŒÛ•ŽÜ^ŒÝŒP•[šL™•V–YTŽL“ÙLÖÌ˜Ü“NZQVZYÚ^L•ZÒNT^RQ\RØÚÖ‘Í–ÝS•ZÊÒÓTPÒÓœÑ[ÙŒÒŒÜVŒRŽ”Ù\Û•\“NS[PÑZÜJÞš[Þ]ŽSÎZÚMZÕRJÓ‘’Ù”ÍSNœÔ[”YÌ‘ÍMžZÙ•S’•Ý›PV[YZQLL›ÞÝ]ÞU‘ÕÖQS’LÛLÞ“Ñ”ÌRÖ›šÑÜ\ÞYSÍÕšS˜“™’ÎÛZ’Ñ˜SUQÛR”STSÙÝÔ’žYŠÔËÍÑž‘\‘›”ŒÜRUUY–MÐš[™ÍÕÒÓš•“ØÎœXXžœZM‘STÕžÑÙ\ÐÌ™Ó^RÓ’ÔTž‘’RÞ\Q–‘ÞÌU™R[T’ÛZÖ^œ\ØTRÜ\ÑÒV–R^œKÚ‘UÍÒR[’Ü›RSQZZÑRÎVNQ’\MÒ[PÌXYœÍ\™ÒÙÛ•ŒXX[S•œÛ›ÜÙ‘M“L™X”^PŒ“”XVVÌM‘\ÚÑÑœÍž•Ú›ÔSL˜^X™Ì•ÕRÓ‘“ÊÕ™ÑØÑšÖ^NÓLÝ”•‘™Û[žŠÛTÕVXÒ“ž–]KÞNKÍÐKÜ
ÖV‘SžQÞP”Í“ØÎ›–•YTÍžJØ‹ÎVŒ‹Ó™–ÍÜRUËÚ]MY™™]”ÍLT^‘LœÒPVÌ‘’žY•ÜV[Õ•ÚLŽÔÙŒ”˜‘•P™Ó–•ÑŽZ–ÑšÌÕÝ]
ÝšÝ[‘U–›”M\\\MÚÐÜZ’ÖŠÝÚSMÔÒ\TÑUÚÍÚN^‹Ì’Y›^^JÖœœÒžTSŽŒÜ™•’ÒÑŒ^[TS˜UšÞ\›Ü\Z›”ÞT”MÌÛÕKÝUŠÎËÚM”Q
Ü›LQšœYš
ÝÎÑTÓLÕÛŽ˜MØRÓ•Õ“”ÌØÚÜÐÌÔÚŒžÜÍÔÝ]\Q•Ü’ÙÒÜ›ÙÜ]PT^XKÛ[]™“ZÞÎMÕTÕX‘Î]U••R˜Ò’S[Y‘–ÛZÛQÍ–ŒÌ[
Ü•Û›ŽQ›ÔÝÙÙÒ][“ZšÚVNÍÔM
ËÖMNŒNLÚQŒXPÚÑPRUËÝQÞQÛSÝZ[ÔÍVÊÓVœÚ”[V[›ÞQÒ^ÎÝ“Ú”RXÊÍšÐNTšÓSL]šÝÝÜPS^PÍ•˜^ÑÝÑŒU™Ü›LM“œŒžM\ÙÐÌ[Þ•ÕÕV\œÝÛJÙÔ››Y\˜ÑŒY•ÕMÕÒYÞVQ^ž›LLSQ‘UÒšLÓÚVS’XTØš][ÌÖM™TØœÎP[RT^‘ÊÎT]ÊØÚŠËÎÒÑÕÔ]˜Û•Ó•NS]Y’ÙPÑ›N•Ó™ØØTT\ÐTÑÐ[ÛMP™ÙØœTšÚÛ’ŒÌ‘ŒLÍÓœœ•‘ÒTØS[ÚSÔMÎKÙÜM‹Ð˜M›žU\JÕ\‘™ÔËÕÔ–™S–œÕÍRTZ›ÜL‘R‘‘ÔJÔ^LÔÊÞYXš[™ØNPÌLRRÔQTT”M]˜‘Q”SÍÒRÒL]Ú–ŠÑ]]ËÓPž™YŒÞ\‘ŽXÛÙœŽ\‘ÌÝÊÔQØÔÔ™ÞQ“ŽÝÑØ‘ÓRÖž“XŒ˜Ò”YÑÕ\›Ú]ŒÔÔÐŒSÔÝÜTšÜZ[ŒÔÞMÔŒÊÑœ–“ÞÍ™\[“LÐÜŒTÚY“UVXÐP•ZÞLNÚ’\R[ÍÖ‘R]U•M^œ
ÛQÖ›Ü›[™–VZ˜PžQJÞ›V”œRV’“TÛÚÞÛ˜–ŠÍMÞSYŠÛT˜ÑŽX^’‘XÕV]•ZÌ[\ÌY
ÚšN\TMÝœÝœÜXÞRZÜNMÕ]ÐÚÞUÎQLŠÖ’ÍTÓÙœÐÌ”ÍÞ’SÛQM‘ÙÔÖÙÔ^V\PÍT•ÐœÚÜLUŒÖÑž[\RRÖœL\ÖQÝ”^XÓÌSÙÓZT]ÕÕ•]SÐÖYÛPØÍ–LSÖRÛž”ÕŒQ•Ð™‘ÒU‘ØÞSœÝUPšQÖYLÔ‹ÊÍ“LŠÔ“ŒMM
ÝØÐÑMÝ[VZMšYÚÐXÖYÚšMÍÛÞYŒ˜šžžÓØ‘Ì›RœPL˜ÑYŒÓÚTÌÕÜš‘“Ì\ÌY™ž–‘QZ“RšÐ”’ÒÑX›ØL™Ž™ŠÍŽ‹ØÙËÞN]S˜Þ˜YQV^[žÖPÛœ[RSŠÝUQžÊÜÒZÚP[ÔÛ›šžž‘KËÛ]ŽMËÌ˜Î]ÞSP”Ò[œÜÚQR]ÝZMšÝZ›PÔSÝ•TœÔ›˜ÕÚžNšÒŽ^LÜ’ÛÙŒZ™–^™SÒ^KÓÚžÔÜÎÚÕÓÌÚ‘šXÓÛ•ÊÙ”M“\‘ÛÓSSXØM[ÐTQZQÚ\ÖUÙ“ÝØ˜œ›•”]ÐÒšÕ™•VYM[“’šÍRœTÕ”›M‹ÑŒ[”ÍUÎZ™Ð•ÒÝL[\N”–ŽÌÖUVž–ÚÜžÓX“ZØ›ÒŽLUØXÞ•ž”UPUQÙ’ØPXš”ÜXR‘ÛÚY“]ÖJÑZÍŽQŽRÑÌPÎVœÝØÞš”ZÍØžYšÕÑ\•\QMŒ“™ÒÌ‘”ÌZÍ•ÍÌÌZZžXÊÛÚ‘QÖRSÊÚTÍž›ÙÖMTÊÊÙ™’ÙRÌŽNVšÝM’™RPPYPT\ÖPÛÝRRØÒÌÛœMØÕ[•ÑUÖ^ŽXN\ÖÓ]PÚÑ–N^ÙJÞQZQ’Y•Ý’ÓÓXR^PÕ\Ü›ÎÒVYUÜšÓÝKÛÍZYÜœÚJÔÓT–S\ŒVTœ^\š‘MTRZT[ÙUTRZ[ÓÓZÛÕPÙÙPUSÐÐSÒ›Q^\[•Ì’“ÒPZÜš”›[ŠÖQ^ŽRšÝÒž•˜•žÛVÜ]ÖZÔZ˜Y“Ò”]’S]ÎZLÕ’ZRXÒÝÔÌP]ŒÍÔØž›–Q‘ÔÙÙÖ‘š]Û™Ú›VLžŠÞ™›Ý]žžZÚÖÔÒ›™Ñ‘RÑœÞ™‹ËÓÖKÙŠÙŒŽMÞKØÝ]›TQTÞS•’™–]”ÒÐLÜQš˜ÊÔ”ÞXXÕ]•ŠÛÓœ‘–PÛRÔYÛYšŒN^QÛÒY˜PÍX“T]šÕSYYX™[šÝžUPÙÌUÓŽVMU’Ûž‹ÓÔÌÝšÛÐÕ™LœZZÌYŒT‹ÎÕž]ŠÔ™MÚÕP“QÙÛTŒÜ^Z‹ÎXÎMQŒ]Ö”“ÔÜÍÑ
ËËÍÔŒÙY›MŒÓÒ[P‘QžšYPQ’“Xš]ÜÜ’ÜU’›ÔUÖÍLN“”ÕÒYÑ•[XÛ’ÊÛÛŒ’S”ÒÖ–•ÓšŽZÍ“’Œ˜ÐÖTSÚ]Ñ™™•LM[Ó–™ZÞVS•Í”ÙÝÛ‹Û’Ø”\’Ü][Ü\ÒÑU–“ÜÒÑÖÎS•^šÒMSÚQQÌ‹Ûš‹ÍPŠÓÌM
ÙLÜÓQNZNXØZM”ÞRÒÙQ™Û’XËÞL–œ•‘ÐZÚU‹Í›Ô“Y”‘šÑÔ™ÑšYÑÜYŽT[ŒZRT‹Î^Ž›]R[\ÕÍ•”ÐQœV“–UÚÕÔ”ÐÐZÛÔ›ÓÐÞ^KÑ[ÐTÒX˜ÍVQ’ÔSZ^T™ÜÔÔQ]\•L^Û”LÍÐšžTR™\›Î[ZÑMØ‘TÖ]ÓÚ™•ž^ÜÞ’ÓÍÍRØšÚÒT“ÝÍVXÙÎL’Ü”šÖ™YVP˜šKÔ•Í–]ÓÕYSÑ’Ö˜UR[›ŽRÌ“U‘™ÞP™ÐÙÕXÒZœÚUÝT•–[Ù–™ÓšPUŒÚžSØ‘ÒU]›Í›]ŒÞ‘L\ØÕ[Ø•]Z”QÑZZPTÒÙPT’YËËÍ™žSKÚÍÜÍšÖœšVÙÔÚÖS\ÊÚZRSŽMYRÞML’šÕMP”‘RPÚUR\ÔÚËÎUJØÑÚJÞRTÐYÌÔÔ’ULXÓMÎ‘Ô’VŽL“UÔ[ØÚV“ÓÎNRTŒP^MÍÚÌÍMSÒÜš›ÚR‹ØÜÕÚÜY”ŽVÛÒÛP’]\ÜÑÓÑP•ÛÑ^V“Î”UÛ]˜Ð–XÚÛS\]›X^\–[NNÛM
ËÕV™Y”[PÚÜLŽZÖ[Rž›RžLÐŒ\ÒÎX”‘œR
ÝÓÝZ‘Þ\ÝŒ\ÊÐ‹Ô›ÞUM[ØX›V›ÎËÕY\’[ÍZQ]Ú[ÔR™T˜ÔÚŠÞVYT“ÙMÐJÔŽÝÜR•ŠÍ‘ÚØÛœØ–”šXŒR’šÝRÌ›[™™L“žPL
Þ]•š’ŽUšT›ØÐ›ÕÕX]”UPKÜVY[Q“NP\T”T–ZSž^™Ò››ÛÍÚ–PQ[ÌŒÖ‘–•Ü”˜šXSÛÜ™ÝZYÐU[^ŒM[ŽQÜÞœM™ÒÌ›ÖœPVŠÝŒœÝšœ‘[^›•X^NKÌSYÍÔÐ^\Õ•›ÝU”š™•U’ÓÞ–ŒKÔŒËÍ–Ù•œž
ËÑÐ’ÌØVš“^SÍ˜ŒÛYQ•–ÔÐÒÍŽ
ÎYTÓ˜ÑÜœMØXÛÎUš’ÝÜTžZÜ\Ù›[YU[Ö\Ûš[R“[œšKÔÜ\žPTTQž]MÕØ™“Ø˜Ü‹Þ’ËÌÚ•žLKÍ•‹ÌÞY“Ö
ÚÔSÕÕ™‘ZÚ^LÐ›P”Ð•P“šÚR[™–‹ÖRŒ]ÓÓŒÓŽÔP]TS]ÖLKÍ™ŽÙ‹Ö“[ŒLÒÍS[TÓ]Þ™
ÌUÓQTÌUÓØ\PÑÓ[Pšž““ÖžÚÙYM\ÌŒÙÞœ›XžŽX–[ŒÍÍÍÜÊÒÒŒMLŽT–ÞŽSÕ[šJÊÎ’‘ÍÜÌÜ“Þ–”š›ÜÍS]Þ’ÒÞÓ›ØQL’\˜™^XSÍÚÞQÔÌ\™]]Z•ÍšZÙL•œ”“TUÙËÝZÖ“–žYÙ–“šVÓŒÚ•™››Õ›ËÑMÜÝ’Z™LÌÙ[ZœÝ[ÝLU“ÖÒ––ŒÛNP›Ú^ÙZM‘ÌÌ•’XÚÑÖ–^RØ[RÔÎÓ[ÚNÊÕ™’ÙNVMÓÞ›ŽS“ÙÎ[]ÙPÜÙÓ“RTŒR–šMKÜNÒÓØYUÞQTÝÝÍËÍ[ÓÌÌÛ‹ÊÊÚÑœÝ’•ÝJÒYÚœJÛÌÙQYMÔ“”’ÔÕZUÔ’Þ“SUTØŒÐPPÚL”œ–QÛšŠÔ[Z]ÑÐÐÕÑL•ÎUYÑTœLÛÜÝ^Í’ZÕÙ›ZL›RLÞ\[›MšU]XVSÕ]MPÕL^P”ÌYÔÑ[žQÜÛQÐMXUVXTž]›UJÕ”•QVÓØÔPÔ^–LVKÐŠÒ”Ó“˜Z‘X’Œ™“˜Ù^UÚ][ÚØ[•ÖÕÕR•ÕRœÓU›ÐÛNSÝ[][ÕÕÐžM’ÌÐQ˜Ð\›ÛÕNUPœ‘ÕT”ÓJÒTšžÒ•Z“X˜Ñ–VŒËÒ–Œ
ÍX‹Ú”šT^UZPÑ[]ÔÛÖ–žKÍÙTÚÝTÊÔNRMÔ[•QÒŒR‘’ÜR[TJÙÑÖUÑ
ÒQ‘[ÚÔNY‘Ð^Ð][š™ÖU\Ô–P\ÒÎ’™UÖÖšž”ÚUŠØØQÐ’ÎTÑXÙ‹Ý\™Ú[’\Ì™Œ“PYÞPÞM‹ÑžŽ™™MŽœÜœÍMSUØLZ’ž\Í‘U“ZØV”ŠÔÙYÐÓÜÙÞXÜLÒÊÊÔÝ‹Ù]Y™P“QŠÓP“ÖÐÞ”Z]ÊÑ\S’XÝLYØTZÜ[•SV›ÎY–LNSÌ•˜SÜYU‹ÑÚSŒM\YYT™œ^PŽNÑMNÌÒQÍ‘ÖÍ’Z[
ÓÒœÓPÔÙÑÜUZ^MÖQ‹Ö\•›Ý^”ÝÓœ\TQ“]MYÓ’L”’‘ZÑ^Pš[›ÌÛ“ÕÔŒMTÎNÌÎNÞUÓYÎPÜÍ\PœÕZžÐ›TÓ˜ÝÑ‘LŒœÐQTX’ËÊÚ–JÑÞM˜ÜÚØÌ[Ú‘œÓXYVŒÍÝŒ\Þ˜–•ÖPž’MÒM”[–‘MXÙMSV’[T•UQÐËÝLY“JÔSÓPÔQLV˜ZL”RKÝØ]ÔŒœŒ˜R[’UT™[›ÙÓSÝÜRÍSUÓ•N[RUP’Ó–›XÜÝJÓŒØU™”ÚÚÍZTM–LL›™S
Ý’ØLZÜŠÖÔZZ’Ð‘XLÊËÍVÌUV”ž•šÕŽNS]Ñ–’˜[›ØXU–™šÖXXU•™[‘UQ\V’YÜ–ÑPPZ^SKËÚšJÔY–˜“V\Þ[L˜RÌÜÌ™Z]ÒRŒ™Ü\T“P›Q•ÞYÒ•ÌTQœÐ”RTÖ•ÓØS\ÛJÓ‹Ø”YKÙ^QÑØœÌÛšÓQP‘LQÛ•“[VTÓUÔÕZÚÕžÖ\‘TÕ\Ð˜ÜÐ‘ž]PÎÔÑRYV’ÑÎUŒÍÙSÞËÒÌÛšŒ^Ñ™LUÙUÛÙšŠÌÑÌÝ•ÐTSSVÐ‘RQSŽUŽZ“[ž\ÌPÜÖ™UžÞS™ŒØÐÍ˜ÛTÛÑ]KÛœÚœMMÖUZØLUšZUÕ–Ò’ÞŒMÑœM[Ž\X™[•[^šZ•ØÛÓÖLTÒLZÕPÚÛ›\PŒ•LJÍ’œÔPVMžÝ™Ú•ËÌÐ^˜ÊÙKØ˜ÍÓÐP”Ô“ÜšžMÍ’”L‘[[Xœ\L›˜LÕ–•RPVÌÕU˜^˜ÙYÔÒYT^š‘–ŽQÕÐÕ™RNÓÊÔ]^‹ÙX˜Ô[Þ“ZU’š™––P“ÌšUÕLVRÕÖÍØÙQ–š™ÒÌ–•SÛMXŒ\S‘PVL[ÍVœMÞ•T˜VJÒQÓUÐÍVVT’›œUžžÑ’”ØÑZ™ŽšØNY^Y–Ù\X‘ÓT\ÕŠÎÛXSR”NKÌ]›ËÙY“]‹ÜÒÝÌYÒ–[SÖX›Ö™ŽLKÍÛ\ËÊÖ[˜‘›ÜÛÍÒÓSNZ[KÕ’UÍ›ŒJÛØ•]YŒ™ÊÚŒX’Z–’šXÑ”[Ð‘YÑÞœÌËÔžžŒÍÍÜQŽT›N]^QŒ˜]ÖÒÖŠÒP™LšÐYTT’ÑŒ›ÑLMR•MÌËÌÒÎQÖZÔž˜SœŒš]SÎMXÌ™ÛÜSP]ÚPÞTMXÛ–ZRZÙšÓNSÙ›”ÌÜÝÙLËÔUÒÝËÜ˜JÝMŽ]MÔŒÒÎÔÌS[Z’T–šÕ“[šMZŒÛ›Ì]Q™ÐSSTMÓVYÔšQŒÛÌ’Û‘ÞœS•Ô’VNŠÍÚÕN“–”œÓY‘ÒÐ]”L›‘NU™\TÝ‘•]SÛ›V’ØËÒÞRÑÓÍÎ“Ý“ÖQT‘ŠÜ^Ú[UNÖP•Zœ”[ÐÑÎ[[ŽST˜œŽ^JØRÛ–JÛ•Õ“Ž[ÞY“ÜÑÛPÚY“ŒÙXQ•šœJÝ]SÙœ“ÙMÍ]‘ÕJÖ•ÍJÒVRYÖRYÚ‘PYœÌÝÛ‹ÊÌÛS™ŽNP‘YÑ^]˜˜ÝX”ÍÐÒL™”LLÕY“‘šÙŒÜÖ”XUÜ\ÜX˜ÜÝÙÌVM•MXNTÜÍ‘ÒÞÒ•š“Î–’Ø•]˜[ÍTÜŒ›žYÕ˜N“›˜ÌÍÓÛœXÓÝVVYÖ‘S]ØÐ‘•ÝœLÜ•–RQNPX›ØLVZPVUZ’ÌÖžM”ÊÙØš™ÞÔÍÐÜ˜Z•Ü““Ù\ÛM“Ö‘Ý’MJÜ”X[QLÌÛÚUÑLJÜÍ™XÖ\R]š\[Õ[”ÓÑÒÍT“ÓÜÔKËÚÌÓÍNLÖÞSÙÛ™ÚÓZ›ÓÕU›ŠÙÑNÌÐ]•UÒ\Ú”ÚŽMR™X’ÌÍÔÔM–PPš‘ÛZÐÐVXÐÎURÎZ’RÑÓ›RT“šÛÛÜS“LV]˜QÒŽ^‘Z™™\“UÐV“’\š•‘–UÑPRÝ\Û•›Ð^“Ù›JÓ™MŠÔNMÚÎ]XÝÖšÑÝÌÝ’\VSUMÎNV›P’ÓÖ[QTÍ–T[Ý]Z^‹ÍŠÌÓ™™N’ÍÚPÐ”“ÒÌÚLRÐØÔ›ÍÌXšÕ˜™ÕÞV™œ–YÙ˜••YQšRÌX•TQÞÔÖ”UŒKÒ“ŠÌÒ–N–˜Ý™T”UP\“œV]ŽXMÌXÌ
ØJÛVJÚš]Þ˜Õ[™ÌÔ•ZÔÜZU•ØœNÎžŒ˜MÊÓÖXÑKÝQJØÑšŽL‹ÜŽM’”ÖVÖZž]Ì]RL™ÕTÓÕXMUZÜÙZŒ\ÑÌ]Í]Z˜\ÑšSžŠÌ‹Ò‘Y“ÐLÓÒž]ÐŒÔÍRØÚ’›R™ØÖ™œššÝÖÜÑV“Õ˜–ŒLRÕ‘Þ›XNÙÐRÑRT]Þ”Þ–š•ÊÖJÌ––\ÓØÔÒZY‹ÜZLœM“™Ø[ÚL›ÑÊÛ^’ÌNTT‘XŒKÍšÐÛÜÚL”\šÔÐ˜Zœ–XXš\VS’SÌKÍPXU••T“L™SËÝÙ“\žŽÚSMMÖ^Þ’Ý
ÜMÑÊÒÙ–ÕŠÜ“LÑL‘LQ‘šÚV‹ÛÑÖYÛÔœR^ÜÒÍ[›ŽœÒ’•P›Z›Í‘MÞ\ÔØMÜ”[ÚÛÙ”ÍXM’Lœ‘•Ô[‘XŒÑ”VZ‹ÌSœžZÒŒXUÍÙ™ÚSYÐÔž]ÜÜÜ–RÓTÕœU›ÓŒÊÖ–ŒM‘SÝ“]’Ø^[ÑPUSN[ÐÎ\ËÑžËËÍ[ËÑÞ›Ù›RÖÒ‘ËÙ›ÜXÚÞTUVPÐYÚ“ÑY˜›\’[X‘ÎZ˜™”\ÍÜœ™ÓPÐ]šÌÍ]^”ÍÜÛQÞ™˜ÒÝ’ŒÓKÙž›ZŒÖYRœœžÒT\Ò^ZRVQJÛÐNUUÜ“ÍÑ\MÓÍ“ÞTØYÓÖL“U]’ÐY™’ÛŽR
ÓM[TÝ™TÒÍR\•’Ú•˜Ö“MÚTQ•ÒLV
ÛÎTÛÌœ›–ÝœVÙLØRN]\ž
ÔÜTš™“‘P”ÕÓ“ÕQLUœÕ•“––QÍSÓZU–RTÒRMQY“Ì•ÕMÛœ“QYœÛÌÕV“ÍšYX^šÜ•X[šØÑU‹ÛQ‘›ÜÚÛ˜ŒÍÙQ˜•MÔ•ŒÐ^ZÚYÜLMØLžÒP›SÛ[TÙÓRÐ“Ù‹ÛËØÒ•ÔËÖ›P‘Ñ‘T’Û’Ú•JÓLPYMÍÛ“˜ÕXÔRÍSÝžLX’PÝ˜œMÑÍÍÑÓÜÓÝÓS^ŒÛQKÙÞ^ž]•\Þž[[›ØQØÙ›™ŠÞ^ž[TÑÜZMYÒMœÛ‘S™•[Ü\ÞQ™ÝUKÒ]ÊËËÌÌ™˜Ô–ÑœŒN•Ì\šLÓ^[žTÖÍÐÊÝ˜’ÓÜS‹Þ–X•ÍÓ™L]Ú‘\\Ù’Î]”•Ö•ÜÑ^Ø”ÌŒLQZÌ™ÕLQ•ÒUÑÚSŒØLÝÙ™U•ÍÒTÛ–‹ËÚÞ›\ÜÌØ–œ“NžQU”Ñ^Z[’žYÖST™RÛ’N\–ŒXÛ’™NMÌÎŠÞŒËÌLJÙŽžMV“PŽM\Õ•SM]^˜™YS”ÐšÔL˜QSÒT™ÝÑÖPÍ”ÓZÚS[LÑÍÒY”””žÖVT“ÓR‹ÓŒ]›YKØš›Í•–‹ÞNÝ]]SÓQ”ÙSÖžY–•
ÓÐœÌ\QŒLÒšPPV^š[“ÙLZÙÍ[ÞÑšŠÔÚÚØÒÑÊÊÍSKÓšÔTMQ’Òœ[ÖZLUYÍRL˜Ü”Ö]ZÍÝÒTšVUVPYR”–SXTÒ‘MËÜ]ÎX\SÜÔÓØÞ“Û‘œ^ÜÙ•ÚSŽ[ÓÜ“”Ñ–•XÓ“RØÙ˜”’ŒÞŒL
ÒP\TRÌšÎÜÌ•’ŒZÚ’
Üœ’ÜÙ›ZÝ[Ó˜˜›N•Ù‹ÒÍ‘Ú^‘ž™VRYÔÐ•T•]Ñ•œÔYÛR]ÑRÝÙÌÓ’ÙÍTÜžKÖ‘›Ú[ÐPÐ]˜Ò”ÜÛ^Ýž\Œ”Ò”–›]š”œ\‘›Ñ•RÎJÞ‹ÕÎNPÔX›Ö˜LYVLŠÓ^™ÛÓÒÛœÜRœÓ^ÌT]Ñš•““ØQPšZ˜Ì”MÜ\ÔÝTÕ]ŒKÙ‘QÕÕV]ÐM”ÓŽZÖ’ÓÒQœ–NVT‘•šV’ÙTØUQYÞ“PQTÝÔÞXÓÓ›\Ò]M›ŽRVQXÜ”Ø\“ŒÛÞ™ÒÐÕÝUÎ]ÕŒÛTÝ‘•Ó“MÙÐL•Uœ›”Ø‹Ö^ZŒ‹ËÕ”‘ŒÊØÌÔž[T•ÝØÌ˜ÑMTZÝ’•ÒØYžS‘œ–Mž‹ÕXÔ•S”•’ÕÛ””ÜŠÚ›–œÎ‹ÖRËÝ›XÛMX–›UÌSÛRNL\ÑØ’Ö\™Ì’Mš^ŠÝ’”VZÕ’Þ’ÕÜÕÊÛ•^TÒP‘ÐÓPÌÙ”žžœÙËÝ–ÜSšMZÌX[ÚL“^YT”ÍQ•Ù“\’Ý\‘RÓSYÚÐÝ^ŒÚUÎQY›]ÎQÚ^œ’ØZ‘U]Ò›MœSÔ•JÛ“
ÜZYÍÐ^Zž•Z[ÔV•žœ‘ŠÕÍœšÍJÍÒÊÝ’ŒUš”VX[L
ÊÙYšÌÚØÔÐÒ[Ü[^[SV^ÒÕ‘œ[\•ÜMÚÚT•ÛœV
Ñ”ÓÔŠÌž‘ÊÑMRÜPÓ’LÖNžŒÓÔÕÝØ]TPÓM”Ò™U]•\˜LZÌÍULX”ÕMÒ›LS›MUŒ’“SÎ]Ù‹ÍÙUËÊÓÚ”]‘›ÚT™ÑZ“’’˜“UKÝŒÖ^˜]œ’
Í•ÜL™Ò•ÐZSVSÞÖÞZÜœLÐÐYÓQÍÞŒœÜÜÞÐÍYÑTLš\U“VS“œÓYœ^“Q›“ÚÓ–PÔÝÑÜŒ[Ùž[ÚMSÙXÛ•V^^UQœ‘”‘UžÛTUTVL‘ÝLMÒžœËÚŽNÙ›™SL]L•œÌÌ’Õ[QZ›‘–ÞšUŒQœËÓÖ’[[YT‘[ÙVY›’ØMXKÙLÙQ]ÜŒÑ[L\ÒÒ‹ØXÐŽÓšÑ\‘Q’Ì–U‹Í[’ŠÕSMÕSQÑÒÑS’˜”Í•‹ÜYÔ˜ÙMÖTÞÚÌÍ\ÐÒ“ÜZžZÑŒYØÝPŒÙV™QÜËÚÑ]ÝÑ\\ZÛZÝTŒŠÕÒÍ”šÒYÜÔ™^TËÜØTQQœ™œMØœŒÌÞÓÙÔX‘PTšPXÕ\ÞY“U•’ž™šŒ\KÐÚ˜ÑÍTÞŽÞ˜ÝžR]RXœ›ÎKÓÜ›šÓŒÝQYŒÚ–YÎ[LYÌ^LÓÌØÔ^\ÔYNÕN]UÕÝ•Ý‘ÜÞSÍ^‘•Þ\ŒÜŒ]^Œ”‘˜’ÚYV^XRÞJÕÒZÍ”S––ØÝÔÍÔÐ^\YÝœ’•ÛŒ\”Ó“QQUM•ØQÚ•\ÞÔTPXœ\‘QÝÌÍœÙYSÚš™›ÑÙÝÐ‘ž•”ŒT“›YÛQÛ]Íœž›YM˜V–ÔÙÜœ›R“Ùšž’›ÛÙY•RQÓVž”ËÊÎ[KÍ–[‘ÒÙTYLPšQŠÓL]•ÔÖRVZ[Ì\VÔÕVQÐ™ÛÐÍÕ”ÚŒ•œ]ÚÓ˜ÒÝÍYØ•˜ÌRÍ‘Lœ•QÑÛPÝLÙŒQšÓÍSUUžLÑVR’Ì‹ÑÚQÒ”LÝŠÓNSŽN^PÜLÖšT[Ñ›^ZŒœÔQ\SN[ÒYÝKÜN˜ÞRÚSÒX‹Ù•QÝQNVKÐš\ÜÑVÌNQŒÍËÌÐ^ËÔÎLÍØŽNLÙ”Ð^”’ŒRTU]‘ŽN]˜Ý\šÜØ™šQÌšZYÓšÝZ^ÚM–\Í–[Ñ]Í’•ÓMÚZ[S•RŒÎSÖÎÙÚ^QS˜™‹ÎN
ÎQSÞŠØ‹ËÕ‹ËÒXY•Í]ž‹Ü“Ý–^œÓØÕžQXÎ^žUž]”Û›[•TÕQU]Í‹ÝT“Þ‹ÓÒ‹ÜP^ÙÌÞUÖœœÐSÒR”Ü™”\ž–Ñ‘œÙÊÜ\ÔXÒ“™ÔŒØ^Z•RRÞS‘Z‘SXÓ]ÖMØÌÛžœÍ]ÍÒšM[MÝÔY‘ÓŽLM‘ššY™›žœš›^”•[‹Þ“ÒUÌÚÚœÜSÑÛœÌ”ÝM™SÛ’˜\ÜÝÝ’ŽMÕL[QÜ™•SŒ–”šÙ’ž
Ù
ÒÚ’Z[TÓX›Ø“ÖUÜTYÝN–™ØÙZ•KÌRØ^ØŒV
Õ^Ó]]•RÙU“MUÎÛÞÎ[˜ÊÕ[”˜ÕÌKÛ[TUYKÞŽ]•ÝËÌ[ÒZ˜ÒÌ““™UÑ^œR›]ÕœMÝÑ˜QL\Y]Y]ÔÌ›Ñ]”ÐYJËÖ‹ÒLÙ™^\ZQÞU[ØÓÝ‘Ý’ÐZ•Ø‘
Õ\Ú“L^\ÖPÒÜRÜM˜•NQÒ˜Ü‘]Qž™JÜÚÝT’”ÎX^S“ÚÝR]Þ›V\“Ì”TÕŽVÒSÛÝ“ÍÞ‹ÚÛÍ“šÐ\ÎPÓÑLTÔÔ]RYŒ–\ÐÒRÕ”ÔÕ’™TUPÍÊÍQÌ›ÝžŒ^“”ÎMM‹Ò’]]ÜØKÐKÝ›PÝž›JØSØPœÖ–Óšž^™’JÕÖ‘Œ”ž
ÍZXLZÛ‘Ý’ÓJÕØÒ›ÊÌQÚU›
Ò\Ö\Ò[ZV\X˜•[TÍV“QÑSÔ‹ÍÔËÙ“”]ÐVZÕTPVRRŒ”žYPÎUPŒÓ’Ô“ÕÔUZ›\ÌÚ‘ÛœZŒ‘QÍÕÕL’’ÒPTPLžNPÖ›VÌ[Ü•[ØMÛV[Ð’™ÓQÍØ[SR^Z\QMÒ\R™LÓJÌÚZ’’XŒQXÑPÐÙ”RÌÛœÓŽ\ÓP–‹ÞœRÚUTZÕZ\•[QÍ›ÝÖLY“Ùš^KÐÌQP‘‘]ÍÎZÙSNNNŠËÕÌŽ•ÙRSÜÛZX”Ò^TPØZœ“ŽX™ÖÎËÔÔ™™^ŒžžœR]R•˜›ZSR“\‘Õ[YR‹ÓZ‘ÜÖ™–ÕM‹ÝÛ–˜›SŒ•]ÖL”™’ÒP“[ÞLÔ˜ÊÞÒJÎ”ÍÐT’ÝÛMÑšST–œ™›‘Ö‹ËÔÛ›RÒ’ŽV’ÞTÒ‘JÓP“VšËØÑÊÚÌ‹Û]M›NXœ“ÜX‘ÛÕÕŒ]\Ý’›ÛLÙÜUÙTÕ
Ò”NžM]›ÎÙKËÒŽN™ZX“Ø–X
ÖRYÚQÚMÎR™‘˜NXKÑÍSÌÜÙ•UVœÞ“˜“ÝÝQS™QÛTÓ™JÙÝU^’–™KÔ”›S“ËÊÜÖU[UÒRÑÛ–˜ZYØ’LÑXUÙžS™ŒÛÙUÒLÞYÝJÒQÑ˜ÐU’ZÕÑZÓVØÙMØœÐTŠÕKÙ‘]ŒÓÑX–MZ’TYÎR˜˜ÙØÖÑÛÚÜ[ÛÛÐPP“XÝÙÔL\™ÔÌŒ”MTÕ
ËÚŒS
Û™Y‘][“UÎÚQRZMÙSÍÛ™^]“ÕÊÖ^]šT˜ÓÛ™ØÓÝÝÛQUž›“™T^’ŒY^˜ÔÑY™SÎMKÐÞVL]ÓPÓ^‘•ÒÛ˜“Û‘YÍŒÑÎ˜Ö”U]–“[ÚŠÞŒÕÓÜŒŽZ‘RÑÍTÐKÊÛÍÚØ˜ÔÜÌ•ŠÕÚÓ•Œ™XÖTU“
ÚLÑZPTŠÙÛMÚ\SÎNSÕšÔZR•ÑX‘ÍÔMØ“ÒPšžŠÙ–Ú’žÜÚ–˜š™ÙŒÖ]˜ØNQÍÚŒ’QŠÍM]ÑÒÊÎZØÌÓÐ^žTUÜ]žKÚÝS™ÑÔŒÕÝÍÜ™‘]ŠÝØÛLVÛÕQÙ™\SZ™‹ØÓÒŽZ[˜T’ŒSSÜŠÎS˜JÍœÕÜMZœ–‘”MÖ[KÖMÑNU’–ÚZÞUU•œY’ÍŒQ›ÊÌÚ[ÛLRØÞŒ™ÌËÌÝÔžŽMŽÒ^Ó›ÌÛ‘Õ–˜ŽNTÍÓ˜šVM‘Þ“ÌMV“ÛÜJËÒÖM’[–šVTœQ™Õ’‘Ñ[Ø”S™›˜Ú–ŽVÓ™ËËÐÝSÕVÙ[™ÙÒÓ˜JØÍN›šžÕÚ\‘–•Ô]‘VŒÕ‹Ü]XZ•š‘ZÑKÖ›ÝÕÜYÜXRÚÝRÎ[ŒÜØÌÖ–L–ŒŒ‘ËÑ•]Ù’“Ùž[QPX›ÖSR–‹Ì›[˜ŒYY]
ÔYÚÖÝØ[’RÕQÚšSœÓ–’“Í\Ù•‘\ZÓÕžY™‹ÊÕÞ›\œ]™œÑžÎ“œœÌÒX[^Q™Ñ‹ÞMœÝ™]˜ÙNÚÒ•Œ‘T›ŠÝ\XÙXœØÚÖM
Í‘][ÙYXQÜ‘UŒ‘ŽÍV™ÔÜžUŽMÐ]Þ™MXSKËÛ[‹Ì™ŒNLÞ˜šÓ‹Ý]TÌÜ”RVŒÌÞZÑ^ÖNÓX[™›‹ÎPÑ”‘ÖžŠØÌÌÛš’ÍÝÝÌÚ›ËÓQ
ÝÚM’UÝ”Pœž–Œ’^\ž]šž”Ù•˜QÚÐÙš[[Ý\]”ZQQLœÞ›ÔÑ[SÓ\ÚÝQš‹ÍÔÛž›LÙJØ›Ý‹Ð•ÔY›Ò‹ÍUÝ™RRVTššQQÓ’ÕÊÙÑS””ÖZJÛÔÑÛ]™ÙÓÑ“
Ý•Ú’ŽMÑP•YÒŽS\QÚ
Ö“ÝNÚ™ÝÝ•ÓÜŒ]‘^T“ŠÖŽ[Ì™Ü^TÖ\”Ú“ÓÝUÌœÙ“Õ\R’•ÒÛ’Ü™^LŒPZ™œ^˜PÍUÍXÝNQT›QUÊÚž™œV˜QUV™ÜØÔYÚMÓPXZÎ^VJÜ[^[ÝžŒ›ÊÝÍÔ•V™]•–›ÑQÒZYŠÝ”œœŒËÑLØŒÓ“ÔœT^–’ÊÔ˜™Y\P›QVT”Õ\UKÕ”œ[ÑÙSÒžœ›JÚØ•ÌQÞPU’^[YYŒ[Ì“ÒÜ[ÞšJÔžÞ’ÓšR’ÑÌš”Ý^\Í]Û”RÌšÍS••XR‹ÞÛXŠÓÛÒÌZMœŒ›Ö•žŒÛ^›Ô“SÎ[PSÛÎ]MÕUŠÔ–•ÚVMRÔNPÍž\ÔÖSœÔŒÕÕÐ›ØZ]ØÐ™YŒ[Ð”ÕÌÍÍ”‘ÒX“ZYÕÐ•
Ì‘Ú’RÖLXšØ˜’“ÙQÑRÜ–’Ü˜[KÙT–LÚUÔÓV\™™Ô”PÛÜÕ^Ûš^^NNLÌËØš•ÑÞNXÛUTÝÚM
ØÓÚZ›Ü‘Ú\ÌÞ•Ð’LMÌÌS›LR–]Ò••ŒRÍRL‹ÝÌÍÙJÍUP\Õ–P•ÛÕ‘’Í’ÙMœTÒÛÙÝ[TÑØ’MÚXÐVÜ^’SV‘˜ÙÎ\PSÒRÒ]ÔÐÔÔPNNZÊÍJÔŽNMÙŠÚŒYSÔÐMÖRšÍ‘ÒM[P“•ÓÓÒÑPPÑËÑ[Ü”ÔÛœÚ•ÙTËËËÚTSÞ
ÔYMMPQŒLÝÍP”ÝÒ“ž–•QÙØÙ^‘•ÙSMRØšMÚÌ“ÝÖ˜KÐ™ÜÓÓXUÌ”SXÜZ[Z\ŒÝ™ØMUžQ›\ÝZÙœMÍØ“RÙ›ÔœÑÌÖY™‹Ô™ËÎUÑÖšÕšU˜ÓSRPQZ“ÖÙÑ•[ŠÌÍ“–LR“ž“ØMPS\’ZT–”ž
ÕPQZQZÙÎ]YZMÛJÍYŠÓÌØÙNNKÑSÒMU^LV–LY–Vž^Q^QÐQ\ŒÛUV›ÕšXÜQPšTŠÝÔTQ
ÓY‹ÌQŽÝÌÖVÔSÓPSZLL\™ÝRÍØÓÍšØÔQÕ[\–”[šÔUÛÜÖZ[ØÓ’YÎÐ”‘ÓÒ™ÜÓŒMÙËÚT™Î™Ý˜X˜›•Î\™ÛŠÌÔ˜•ÝÔÚÐÒVSZUÛœŽ\™ŒÛÑØ˜–MÝÒÔÛØQU[ÙÛMœZž™PÌ™PÌ•\ÒTTM™ÞŽÝKÓLNMÚ™LœØŒPTŠÛÜÙÓY••œÐÝJÚÚÔÔËÓ–šžÚTÓM‹ÜÓÍžÐXÐYÕÐMQÛ[”ZÞTÍÒMŒMÔ[žÖ’ÛYÍ]Ø•U–\MÑÞJØ‘XÔŒ”•T–UQÜ“KÎ\š‘T•ÌU™ÎUÔSÒUÐšÛR^TŒXžŽVÙÎ‹Õ›ÙTÓUŒÕÐÓ]\’˜[Z˜[R––LœLÍ\’M’Ü[ÔÒRÛÜÙÞ\ÚSVKÍÚJÔÌÔÐMXÙ’‘RÕÒÒÔÓ\ÛžRUŽ‘ÒYÍÛÛJÒRÕ“ÕÙÌÝÒÖZ‘š•Ø›“]ÝœYQÙÝÐÝÖMÐ˜Ì’–ž‘ÛžšTŒRÑYš”‹Ð‘Œ\ŠÞ[\ÙÝÑÚÓX]X›ÝÞ›LSÔÙNTÍ•ØY™LVQÕœ^œ™^T]ŒŒ‘“ÎPÖZØJÍžÊÊÚÔV’“ÕÛÍ
ÓV\Ó•ÝL]Î]ÞZÜÖLXLÝØ^[™š‘UÎÝŒ‹ØÍLÚŠÖYRÒÍNÝÎŒœZ–VL™Œ‘ŒÖPZÔ•^JÌŒLÖ^–SÒÝÜSR”]ÌÖ™\UÚ–Lš•ËÚŠÎ[\œ”“ÐÔVN\TT’”ÐÍTÐ™”Ù›“ÍØÝZ“™‘ÊÝ^”SÛÐQ\ËÌ‘Q\ÓXœŒ][Õ[Y•’Ý•M‘[LÜžšT^ŠØØ”‘YU’Yœ–Ô‘RYPØQ”Í•T™ŽÝJÍÎ˜ÓÔÓUÕŠÔZÞ˜ZÕÓYŒ›ZÌRLÜÙQX]TYÜMØ™ÚšœÛP”™\ÐšYŒZ–T“NL^‹Ó–ÜYYŒÎ[˜LMPÐP‘ÔV
ÒSRšÕž]\ŽÙŽX–“ÓÝÍÌ]ÎRœÞžš”‘ZÑÚUUÔM[SÖ–’LM’ÓQÊÝ]˜ÛN[\ÝœM[Ô[ÞœÍÙNKÖTšŒÌÑ^‹ÊÓŽKÍ˜›M‘ÕÓÒT”ULœÓÌRTÍÔŒR]QŒÍRPÎVTYMXVÝ”TŒ‹ÎLž‹ÎÞÌ\ÖP‹ØZÞ‘SÒ–]TÒXÓXPÝÐT]XRSÙ][Ò[ÞŠÛP“’ÞLÌÙ\šÚ›TÔ]YÝÕÊÝS\TÝV\Ó‹Ø›–LKÔYŒR]ÕRÐÔŒŽVTÍÔÚÌTÛ\Ñ•ÓŒÖQšXÒÓ“•ÍŽžTËËÍL•ÐMŽLUÌU\Þš[QLLšÔÛ›‘Ñ’ÞRÒÛÖQÝ\ÍVŒÜÓYÞ\‘ØÜZ•Ú[XœžQÎLURXžRYV^“ÐÚRÌRŽPœRÍœLŠÒÔV™šœ^LQœœ˜žS\Õ›RÌÞULÙÑRœJÎ\UTšÓYQTš‘ÍËÚUÊÓžÞžÑLÒ‘QUÐÚÒT›Z›PÞ’–MÙY\XZPZSÙLUÞYÚžŽ\ÐÓYÖžKÒMÔKÙÞ‘Q˜ÙZœ›•ÞÒšUÓ˜Ú˜”ÐÛšÕ”œUØU”›Ð–T[˜^˜‘JÞX\Ó‘ÛZÜ’RœÕŒ[”V]Ø“˜–Þ”˜VQž]“NS–Už™šÐS’
ÒÞ™Ù\’Ú”ššÒÒÕŽQ˜SÒVËÔYËÕTL˜ÐÑT–’S^TSÐšZ[UQ]VLÐ’ÔÛVÚ^ÌUÓšÑLSÛÚÛQ›ÔšÊÑÙ™P]XÚRž’ÕQÐ™ØM‹Øž˜ŠÞT™‹ÝTÎ]Þ“ŽLÛŒ[”ŒTZ\RœÌ‘U™•ÝSU•ÝYŽU‘Ò˜U[ŒÙQ]ÕŒYX\ÚNMÜÛ][Ž“LRYYP–˜RšÎSšLÒÒ“\“ÊÒR\‘TÓYÕRZUÒ’ÚœÝœY]ËÛTËÚKÙžNMÑ‹ÝœQ•›SÌP”’ÕMPØQ›SÕÕšŒÒSVŒ[UNVšËÙÙšÕLÙ’ÍZÓÙZÑVRÔž‘Ý[Í]]\Qš^œQÌÙÕ–‘LÜTRÜÔVŒ“™ÊÒÚUX•ÑÑY”›P›“SÚËÍ™˜Í‘ØTÜËÑÛSYÛÍž™U[LÕR›ÖQ›Ó™[–ÙŠÜ”‘Òž•Ú˜ÓÝ˜\”˜ÝÓÐUÓPÑZ›Œ•U^\Ò’’]ËÓÜÓ›ŠÒKÊÐÓ“ÍRLœ]ÝTZ]™ŽVLŒœÌ›UšÍ’QÔRÙ˜UØÖPšÛÓÜÞ˜MÍšY‹ÚšŠÒšÒ]Ù\Ü–ÒRYÞ‘QTMZœV˜ÕÍÒ˜RÕXÍ••LÒÕ”SNQÜÌ™\L\Ò’ŒTÕœ‘X–‘žKÑQ^›’Y“ÜØÚÔ‘”–žZ›YZŒÖŒÑ™ŒžT’ÛÍSŽ“VNML–RÛÒžÌ™ÌQÖMÚ^]ÜVV˜Ö[”[Ò
Ù››œËÎSÖÜž^ÒMØÕÝPšPÐYVPÝPÌ^ÌTÖZMÌUÖ˜Œ]S•RP’›\ÒÕXÖÎšÓNUŒ’LÌÜÔ”Ü”ÍY\]’Ì’›ŒSœŒPÐ\ŒLZ™’›ÖMÔÚšÞU\]›YÑSÊÒPÑÐÛÍÙÜ›Þ™XXÌÖZ›ÒYÓÍÐ“šÖ[›˜UÒ‹Í™ÍŽT[N‘ÕZYÝÚŒZœÊØÕMJÍÓÍ–YZÖÒÒÌ^UTS››ÒPZ™˜“’Ñ™
Ù–‘Ú^˜”ÝÚÑXÎÒÐÝ•šPPÓ[R”TŒÖ˜ÕLÙÞR]SÔ™MÙZ–L“Ö’™ÜÜšYÝ•Mš‘ÜT“MÒš–[JÕÍQÚXÙX^\TÕšŠÔ
ÕYPÚÌZž™PÑ›U]X’NM•žŠÜMSœTÛY›Ò•›œ’”LÔUÚ’R”UÍ‘–ÚÍ•’•ZP^Ö–Ô
ÝÛÖŠÞ‹ÎTÙY™‘ØL™MØÛYŽ–›ÕZSXŒ“V›SËÌÛ\
ØÝKÍšžÜÛPÌ]ÚX[TÜÒQNRÙÑRT”ZSÜ[ÞžÊÒ]ÐP’š’’Ú^›ÔÍž•ÙLUÛLÌ›NV™ÊÕÞžZÛS•ž]Ù–^ZTž›UÔ˜[\RØÖQ^ÚÜ’’Ó“š”ÜSÌÛÌÛLTÎKÎ™‹Ö^”Ñ””M’•›]MXŽŒUÌÙQ\ÖÌÞœ‹ÑŠÎZÝV›USÌ˜Z‘TÔŒšÜÕž
ÕÙ–]KÍ]ÐÙ]”ŠÌMÌÛR•Œ\ÛœMZYÔÓÝMÊÜZ™JÊÎœ™ž•Ø
ÑTS˜V‘ŽUZKÞ“™™˜XÜQŒJÌÖU“[Í”N\^YÚÐšR
ÖÒÙžÍS‹ÍÕÕÍÎRÜPËÌ™XŒV˜ÖÔÔÓÐÒSœNXÎ[ÐÕžTÕ[TÒ™Î›–Œ]‹ÝÍËËÒÊÒVŒÕ™“QNQŒÒZRØÒ–œUÚ›Ø‘ŽQÌUV–T”\PV–•ÙT–ØÖœS’ÒŠÕŒ˜Z‘‘ÒÕ™ZÑNÕÝ™˜ÌY•ÎQÙÎXU™’ŒVM‘ÜœØ‘ŽRœLÝ’ÓœÑXšXÞ^UPËÍ™ÛÓ
ÖMÌPØÓ“šØ”ÙÑKØMUšÝSÍ\[ŒÓÛÔÚYÐÕ”MÐÙÙØŠÌRÚš”Ò’šÓUÐÊØÌ””šÚÛÔ˜–›]Q\Z[™ËÑÞYÚ’Ü^žQKÒTÒŽ^TØ’UšÜZNZÑVŒœÜ”œÑVXNÖQL”’Ý‹ÌM™JËÎKÙ]Í‹ÜRNPÛÒP^XÖ›[•‘ØÖPÞ”ÔÔŠÔ™ÓÕ›Ó˜ZÚMÑ\‘–MÒ]Ñ›‘“Ò^Q’V‘Yž–Œ›ÛÔÔT”Ó™ZRSLÍ[ÙžÐ˜]Ø]ÎM‘šQœž“XY”Q›Ð“ÓSŒÞ]ÝÓLSSÖY’[ÌÌÜ\šJÖXPÚ\JØLœ”ÙÌ‘Ö›XS–]˜ÕY\™ÐšÚ[PNŽÒQR\ÛZS–šÌ”ÛœQž\ÓPÎMVZÍLÛRR^XYž’Xžž]ÎVÕÙZÔÒ\Ú–NVž]‘‹ÎNTÖY™TÎN]ZKÚÍÍJÒÍ’ÐTÙ[œÎÔš™Ð^[ÝÑ•Ó]”L’ÒÛÑÑRŒRšÔXžXTÚÍQ•ÚYSU’^“R‘ž›•œT\]UKÛ[‘ÛÛŒÔQŒ–‘’]ÑZUXÚQSÛÛ’UÒP™NMSÔŽ‹ÑÝQÊÔœ–ÌÎšž^KÛ™“XSÌ[ÚÐ’RPÔZSÒT[\Ü•ÑU™[Í]šV]ž\Î]ŒÛUÒÜ”™[Ó^•ÑQU]ÔPTTÌQ[ÕÔœL\^MPÌYŒ”ÕRKÛSËÑ’[VV•Õ–”“‘–ÑÐ[RŽÒœ™Õ“œÜÒP˜TSÒ[ÖN]Ô”KÛXÔ^šÓœÌ\–ÊÛTÑ^ZÐÍVTRÜ[™TXœZ^ZÌÒžPšY•ŽÞTÔÑÒPØ[ÙZÝŽ]›ÊÚJÎKÙÌÞŒÞMÐ‘Ž]–^‘YÚÚ[ÙÕ›SRÖ”••ŒÛÖ[ÕTÒVÎÍÍU]^Ý^TœÕRÍ”–ÜUÑœ\ÜUUÖ‘“\‘Q›ÍZQÞPœRÙM•ÊÞ]YœSUšXÒÍœTSPÔÛÖQUQ™ÚPš•ÍKÕÖÔÔšR“šSÓQ••Ü“˜Í›ÜÔMÛP[“–ZU^LšØÞ˜UÑœÍX›NZÌ[ËÔÔ
Í“Uš‘ÎU\ÔP’Z‘ÙÐÍYÒTÝ›ZŽ˜ÊÙÕÎMØÚ”–ŠÕVT]ZR^P›^Ø™ÕYLœPZ”[PÛÎ^]XÐ“‘›œÐÎZŽ›RÍÒYQËÓY˜ÛÙ™ÜœQY^V‘[Ý]•SYŠÌRTÕÕØž›ÒÎQY™Ò]›š“NU’ØÜ›ÑÞL™™[Ù\[’Z–ŒÍSÌÎÛÝžTLKÑÌÌÜÑ›PMÕR”PŽ[Ü‘X”ÓÜ“Ù^XÜÞUL]ÞPÊÕ\‘UPZÔš]ÚNMŒÚŽ\ÙUÔÛÓÙXÝŒTT–TÍ\V™ZVLœÙZ˜žUMÞNRÌ–ŒÓYÙÔÛÛS’ÐÕV”QÔSQRÔÑÓÕ[‹ÑœR]LžP“ÑÐZÌÑ›ÖÐ›ÍSÐ“œÔXÛÙQÜ]•Ñš˜ÖËÑNL”–KÌYÜU–\Q[Í™Õ”ÝZÓÐÙÝÐÑU”“V•RÍ™U•›ÚZÙÌÚ“ž•Ð“\ÔÓÑÜžNSÓQØÞRÙÛ™ÜØÜVRÜÚž™ÌÕÙKÓÝÛ”\š“TX˜RÞUŽT”\Œ]ÕJÎRÜTN]Í’TÍÑ
ÞU“Ú••Ü•TÖ[UœŒÚËÌÊÚËÖYÙÙÚŠÜ\ÍMÍÌ’[ŒÒYÔP’“RPQPLÝÙÑÐ[T–\‘‘V›TÒØÛTÖ›YšÚØÔVXØœœØØÙZŽMÎUÔœšØŒ“ÒNØRÌP•RZ[RÓÖ\‘ÐPR\ØÝ”TŒYŒÔ–‘Û™œPÎžKÙXÔÕŒV•Í\›ØS’MÕÜ›U
ÊÎU]“Ú]ÎÔL’•Ñ‘™™˜ÍNZÒ^ÖLZÕÑŒ\Pž˜ÕU][ŽœT˜\ÎTŽLZ\ÓL“
ÓÙÑKÕÑ›LŒÚNKÍ]MÊÙœÛR\Œœ]]“ÚQSTšZLÑTL‘š›”LÛJÚÑ˜S^–Ž˜[šV›U›S–•P\T[ÑPÐ“™Y™‘^TÎNÚ]ÎRQ”ŽUÒUÙ›•ž‘’ÝÔL
ËÎœVÒÜž‹ÍŒ˜ÊÒ–‘œÖŠÔ›–^X•[NT”VZ”œM“MÝ“ÚSÚ]ÐÐ”V™›\ŒLÔÓÞVÐÕ›YM•˜Ó‘Û”ËÌÖÛÜ‹ÊÚU‹ÛšY‹ÌÌÖ–™]LJÝ“’šÞÒV™•ÚZ•UUÒRZœŽJÖ–T\[’ÒPÍØÝUL–ÊÒ‹ÊÍŒKÍËÜZšŠÎYJËÐÛÞÞX[‘SÝÙ\MÔÒÝPŒ’ÕLUÙ’ÑUÖPÎVQŒUÛœZ]ML’]XÍ^P]‹ÌÍQŒ^ÑÚÛPŒœRÝQ”^ÕÞ]Z˜šÕ–LœV˜ž”ÕŠÕ^SX˜YØLØÑÌ•M•Û˜ZPL’˜M’ÕMŠÙÜQÜÖ\Ì˜MKÝÜÝ
ÕÜÔÌÞ’ÖRÍÕ›ÔP•šÙ˜Üš‘•M‘ÌV“’Ú“UŒTÍQS\PÓYYÐØ]ŒRLVÜÒÊÖUÒÜYX\]‘VŒ[ZYZÝ›YÌS“ÒšR”ÚXš\]Z^L^LN‹ÕŒžQÙ”•ÒQ•‘ÛZÌ\ÕÞZ’Í“–›ŽN˜]ŠÝ]KÙÎ‘“ÖY\TÔ‘TÞÎUUŒLN
ÝKÖQÔT•ÑžVLŒ‹ÒÜÔ••RVPP^S[”ÝÎYÎ]Þ˜UÍ
ÚRXÖX]Ñ›UÜ“Ôš‹ÐÕ\Ú]Ð]˜ÌššRšLV™]ÞV•”ÝYQÍÛÐP”‘Y•ŒŒÚYœÙ][^TP’QšÖ™^]TYÙÖž™VœSQPÍŽ[ÖV^QÙS]PšÒÚRÚØ[Ñ]\\ŽœœQ^›ÞZQžRØÝÐTQ\UÓ‘ÝZšUØZÝZÑœ
Ì•Ž^ÚÑÞÚÜYÍ•ÔRÔÐ“TÕ’ŠËÙ›TLœŽØÕœ[ÞÜ[˜NZÒ’›™™ÚÖ“KËÍØVÕÒJÓÞSØÔM]^RQ˜™–•ÕLÚXMšÊÚÑÌÙÚÍNLS™^šÕ›S‘V[[PZšJÒÒ]ÑÔZÚŒV\^UÍØ^›œÜÍ‘š™ÓŠØYÖœ›œÛÒÞMÖžTZ˜œRRÙ“Ó–[XÞ^TVYÎ›MÍP]ŒÍ‹ËÚÙŽ’“ÑÑÜÒž\QÜÝÜUÖÓœV”ÖšTÓš“™Œ^ÑÝ”ËÚ^ŠÑÎSÒ”ÑÛÒ•R’YTSMXZ˜ÌZ”ZZÓÖ“Tž–TNUÕŒÑÐ˜VUœ™ÌP”T^Ø]œRÐÝUÛ
ÔÕÜ˜S˜MÛÖ›Ô”ØVQŒÍYØ\ÚYÑSSÝ–“JÝVÑKÍ‘Lœ›‘ÒÑÕ‘QR[MNSÛ›Ù™Õ‘ÔÖ’L^ŠÍ•Ì‘RÕžYÍ›˜[Õœ[‘ÞUTÝÙÓULÍ™ÌÍKÚž˜™’Ù““›ÐÙÓMÖšQT‘X‘ÓÑÒR]Ó™œVÍ\•^ZÕUœQÛÑž[˜ÔÓSMžLŒKÐÝ‹ÝV]“ÙSÓšRMÙ^”RšLÍ•ÑÒÝVŒÐž•Q“’ÝÎÍž“šRZLÒU[[ÖJÜ“–XÐÐ•˜ZSÕÚ“‘NMÐÜŒÚZÒ”ÚY“Þ’’ÝÞ“ÌÛ[ÒŒÐ’ÞPPXÓURÓXÔRZ“Øœ‘œÖ]RVYRX^ÜY’ÖTšQZ”œ™S™ŒÔNVÖžZYPÕššP››ÌÔ^ÒËÛÕ[›’ÎTÝœKÒÔÓQ[[’ÚÖV
Í•ŽÒ“ËÚÝØ”]ÑÎÚJÔœSÕS“SÖÎQŽVœËÛ˜Ú[MÑÔÛÝÕP•™\Ò˜RÛŒÛÍT
ÓR–ÙšËÑQMYT[ÔÝÐÓ˜^ÖU‘‘[“\PÓRKÙ\ÝÔMÛÍÍœÚUÌÑ^T–“”\–Qœ^TÓ[S‘ŠÓTÖ™‹ÑNQËÍÕÞLÒLTØ”Ô›Q[Ô‘YÍŒœÔÕ’\\RMÚ“XP’™‘ÙUÖ“X\ÐÒ––JÕÝ‹ÍNNSœÓLÒÌ•Û”ÓRPQÜÌ]ÍÞ”Úž›ÔŒÙQPLžŒYœžZ•JÖŽTÕYÜÎÕÜRUÞTL–’PžÚSÛ›ÒÒZÒÜÎ[‘™™SŽSÕU“šUÌXÕÓLÙ”’ÌLVPSÌÍQ”[ÒÕÜQ”QœÎ“\ÎLÓXRLRØ”ÔÕ‹ÜÖÑ”‘ÜÍYÞ“Ì”ÐÜ“U•PÑžÛÚKÔ˜”œUM]ÛLœ‘Õ”X•Ô[ÔLP˜Õ‘Q”XÙÙ‹ÌÛœÊÎÕ]ŒÚ’ÍÙÚ˜œ]ž•YœÒV›QZPœÙ\ËÑÛ“Ú”žØÊÜSÔ–•ÛLž^[š^LUØ‘PÑY›Ò•ÛžRÌŽKÒ”ÑV\ÐÔšQÒÜ’RžŒ“LN[Y\\šÑ‘QÜÝØMŒ’P›KÕS[ŽNÙ]X“›’”U\SRšTT“šVZZÙÕÚØÌ[KÔL™“ÑLUŒLÌ›
ÎYšÍ]UÐÖ–TÙšX–X‘Ó][TNÍÛ“UQÔ›ÔÐ‹ÑœÖKÒÔXÞPPØ]N]–T]ÊÎM^JÍÕÌ™’ÒÔÌÞSÖ[šÐÕVÕ›ÞÍL™JÛ]‹ÌKÝ]SÜ–^YRÑšM–YÜ•ÍœÍYL^QRÞP‘ZS^˜NNVPÙQ’Ö“™^œ–LÛ]Í‘ÜMRRZŽR”™˜Ù‹ÜœÞ‹ËÐÝ‹ÌÚ•ÌÜŒÍÙÜ•ÎJÎSÒÍTž[›ÕÚÑÚÌUZX›Y•’ËÔšQÐ[ŒÑ]žM’”ÞTÐX”œØS’S‹Ö‹ÍËÚÌËÞ›X‹ÍÊÖKÝÙ^YÐÐ“žQ™ÝÌM‘^TÜÜŠÑYZ[Q‘ÌQZL[ÝžUÎž•ÓVT‘ÓÕ˜ŒÕ^LÎ[Øœ–˜^M]Ì˜SœVPØ››LÒSU[ÚÐ^T›šÑÒØŽTÌ”ÊÜÒÜ[“ÝS“Ù›ZÍ’QÕZÑÜS]ÌÒSQÝ”\YÔ]’Tž^ŒTÕÖ‹ØYÙP˜^ŠÓ™]’ÜÍ]žYÝš^™L˜Q‘P“]Ì›ØÛNÝRÖšXœÔœ––”VŒÕÓRÐR˜Ø’›Ýž[“ÐØÌUKÍÌÌ]œMœ]LT]LXTQSLSZÍ‘ØÙ[Ý•‘L˜]RR‘ÝR™T‘ŒXÛTËÍ–ÞŒÔY‹ÍÑ˜Ù”ØÓ]Õ\Í”Ü]Õ˜M”[ÝVŒØÒÛÛÞ\Ô˜˜œÕÙÍQ’R]MœRLZÖYRTNXžR‹Ù™ÌS˜Ù]ÛÖÔÒS\ŒQÕ–QZÙœU›PšœÖV•P”U•Ð[ÜÌR™ÔÑÔR›NM‘LÚ‘XŒ™VYÓÍØ›SZÚNP\RTS‘YÊÝØÒÕÚ^P›ÞÖS\S‹ÒMRYÝÜÍÖ˜S™ÛÞ‘Ì]ÌT\PTÕÚ“•ÙÎRQQÕ[\Ø[VšÐ™žÕ’M[ÐÓÚ›Ù”›[™M[YÖ‘•žLÙÝÜÚ’R]ÚÑÛ–^]”Y‹Þ™R›™JÜ“^MÛQÞ\Þ^MRZ’ÍÞ]UÝM‘JÛŽXÐÖV•ÔÍ•ŒžÍRÕRÙYSÍÎUÍŠÐÙËÙ‘V•ÙLÜRZÌš˜[[ÔÙÝÚÙ’Ö›ÑSUVT•ÎRÖQÕÚ–P\ÜÓUÎ]–]ML][ÌSØQYU\ÛÚKÙšZKÙš™”ŠÖ‹ÍQLÒ]šÜY][ÍS]MÝTVZUUœÙZÌÝLXÙ[ÎÒP‹ÍšÛžšžÒžÌZ–Œ\‘\ZÔÍMMÓQŒQœQ‘ÜXQÊÒÜ™’\V’]šP’›˜Ñ‘“žNXØ•›ÌÛÔÚ]š\Ñ–\˜ÝT“˜Ò•\’ZØ”]M“ŠÝQÕPžUTT›LšÞ]ÔÍÙ[”Ž^žVœÓ^YÑZY’ÚR›šÌL”Y˜MÌPÚÌTÓ“T›\“ÐUÎZ“Q’X˜ÚÝ]˜\›•ÍØLYÛ–Ð[LÎ™‘’JÊÑVžœLÑÑÌšÖŒ]ÊÒŒR˜žœÕÒS›Ž\SÙÖPÍ–˜ÜÌ“ÖS]‹ÍŠÖLT“™œN
ÐÐS“ÞÑÕY”PšÎLL‘•UP–ŽZžTV‘ÌÜSMQNÝ•‘\Ò›ÛXÌÚÍ•LØŒ›PÑÑU\žT‘RœÒŒÔSÝT–›VUKËÔPÔÜØØLÚœPPKÑÍÓT’ŒMš™ÔÙÙÞZÐRÛÛPÒÚSÙÌNU”NUÒÖÑÕZ›Ô]Ù\›ŽPLLÝœÎ[\Õ–‘œÜVŽ’P”[ÞRÚÔÍžž™š“›–žPžYÓ\ÝÝVU’SÙÓÚ“”Ú›‘šÐŽÚYØ”‘SÍÊÔÐTŒSUÐÙ–›ÐÝ^ÎYTTXÜÔ•Ù^RÍØÛYÕ\›]\YšŒSÌÌÍ‹Î^›–™UMŠÔÚMÛÓRœ\\TX––SÚÞR”šX”]”Ì“™“›ŒÌUŒ“TRšÐP•QSQÒÐ\Þš™Þ^M’“]ÛŠÕÕ‹ÐLÑPYU”“Û”ÒQÜÌŒ^Ö”ÑŒÕÔS™T•U›SÔ‘ÓRšVZœL]ÌL\ž™KÊÛÝÑXLMÓÕÔÚœžRUÝ–‘^Q[ÐSSÑÛÙ‘]]\[Ú™UR™Õ\Ö]šUÍ[ÑTYÜËÕÖÚÙ\U^™ÙRÞ\ØœZØÒžœXÓÕN–”]“UÔÛ”ÎMÎÖ•Í‘RS˜^”SØZžR^T•“Öž™T–‘X]“›ÞP’™XÒÖÒÔ]Zž•ÕÒÜÛÝ“•^ÙÌV’Ó^ÙMÝRVYX›™ÖY”SŒQYQÑVŠÍRËÝ™Q]ÍKÙ“ÚV“ZMVV›TÝ’ÜXVŒYT“’ÓÛš‘ÑÙœTQÛLœ˜UÍÕ”SËÔLSU]ÐšYÐ“S“ØU\ÜUJÎJÔ›Ú[”›PZS‘ÍËÓÕØLZ”ÜS–ÌMÝ]V•‘UÒËÓ]˜ÜÜ™ÕÑœÕTÔ•’ÚMÌÔM“’Ž]XžS]L›œÛž[ÖYÞ\šš
ÜÝNRÒ˜œ[•Z“Ì”Ð‘L[›”\Ì˜ÝÑV‘ÒUUÒLÌL[XÛ›]ZSÖYYÔŽXT˜ÚÝ‘“ÓÞ›Ù^‹ÝÜUNN
ÜÝ‘’•MVUV[˜Xž”ÝXÝ”Û[ËÎTÖX^™œPœ‘XU™]Ý’QQ›]ÙVŒÞXÞVŒTž’›PÒ‘’Y™S”•X\Í›Ô]ÔÛÒM™T
ÓÔSŒÌÌËÜ‹Þœ‹Î™^ÙJÍÝ˜˜›ÝÛÕÙÎ‘UÕ›‘ÖÒ”’ÕTÍ]M\Õ•ÚXRRZRÕJØž–”^“^ÜÚÙTZŒÌÎËËÌ”ÍÝ]‹ÎÙ‹Ý›‹ÎÍÍLšLÒT\ÚÒ“^ZM˜R”Y^Y–šLŒØQVZKÑÊÙ”YÙÞ•Ñ]Ü•””T’RœÒ]‘šÙSMÍÝNPÔYÕY\œšÝ‘‘VMX\ÖžRQQÙš’˜“JÕU[ÒÌŽLÜ‹Ú•YÖMQRÍÝŒ•Ý’Ü][YÐÍ[ZÔÙU•›ÌÜTÚ”˜’–U˜ÐÔM‹ÖœÞTÒšÑ‘žšNTJÕÕ“ÌÖ–›NYSÚ•ÛÎQÜ’XÜ]XY•PŒ™YLÒ“QžUŽM–JÓÜ[Û™VR”NÓ[ÝšžœÐ‹ÍžœÝKÊÔÌNN^’ÓTLUØËÒŒVNUŒÓØJÌ’QÞSVšŽY]ZÕUÛ™˜š•\˜”STÚYÕÚÑRS’P“ØÝQ
Ò^XMŠÑRQ’N]˜š’ÑÞÞPØšTÔTLT““Ð\Œ•›Yš’[ŒÒSPØ–›Ö
Õ›–žQ•ÖXÎS™^PÔÊÛ^”˜ÙÛY›V™T[•™•‘Q[ÝÔ’’ÛŠÞTQÖœQ[\“›[ÝÝÑ›œÒÜ’››RL\VÑT‘ZUL[šÖPQÛÔÓ^’TÙÞZLÚSØÕŒ‘UŽUS^MÙPÐÍZÙÛZÓUÔÒÒSÍ]ÚÛÜÞQ””“ÚVTRÌX”Ú“
ÒÚYQS”Õ’’ÑÞ\RÓÝNÜURÍÎQVš“PÕÚXZKÖT’Þ\]M”Œš™ÞUSTR‘Ž•ž
ÕÚŽÝ‘ÑUÙÑÍZUØRÛVPUT›ØŒX™TœLÌN
ÍÔÙZœMÙÒXMœPT˜•YSÚ˜STZTZMN[SÍÎZÔ”ŠÛZMÕZžRÛKÔÜMŽURMŽ[ÚÛÕÕÚÛžVN’MŒÎÐšÎ
ÐYÙL˜Ù’TÐÖšžMÒL’ÛTÖV”šQØÒšXØZX^˜‘Y\ØÝR™Ìž‘ÌÛÙÖLÖ’Ø‘Õ™ZŽÖPXYÊÜYš
Ý“ž™\Ò‘–\ÒPÒÝ˜ÎSÝ™PJÎÎœÐÐÕPÛ˜ÒYÔ›[XÒ™‘ÍMÔÚ‘šXJÑÙÌÎRÔ˜ÛRTÝPÌÜÔ[ÖœU[YœÍÌV\›ÚÝÔXŠÚTÎMËÔKÌÝ™ŒN^\RNS]›ÞYSYÝÚ‘Ö\•ÛUÐÛØÝ]ÕÔ–KÙU‹ÊÌRÞM˜KÚÌÊÔËÊÔTÖYÍTÍPZÓ˜•ÑN]]NVKÐÑMPÚ“‘–[ÍÌÚS˜œÝÚÕšQÜ“’’”QšÚÒY]Ö[Ò•ŒJÒÝ
ÑYÚV”PU^’ÛMÜÖÖÕÎž•Ø›šRÜËÒÔÒMÒMÐSÜÍZQSÖJÌÝšÜ•ÌÚ›Ü–’SMM]U“š“ÌRŒQ™ÓÞXX’TŒÒQ[Œ‘
Û˜ÒYMMQ‹ÎX[‘ÛŒÕVM‘œ^•šÝÑ–[Q‘QSQÔ–SM–˜SS^’‘ÝÛSÚÞUÌZ•ÞRQÙÖŽÛØ”ŽYZÓM™^SœÞ›\žLØ–LYØYÖ“‘”™P›Õ”’™LØÒRœÒ’[XÍ]TžŠÛPÔZÍŒ”QZŒÔMÝœJÍZÛLLQÐ‹ÒLQSÔKØÓ’SÞPU˜œÍZMš[^[Ð]“\L™VœÛU^šÑ›ššÜ”“ŠÕ™™šŽ
ÎUM\Ì
ÌžXXNZÒÝ]Ñ˜UšÌÌ[Öœ™ÜNKÜV”NM•ZÍVNT\ØRÔ‘T\Ô“Z^ÜØœ›\SœÍQ™›ÛLM‘ZÙ›QUYÕÝYÚMœÛÎLMJÌY‘š[]Û›™ÚÔ–›™UZXRœSÜKÕRžQÓP”Ø‘Õ’ÖRŒ˜–Z•\™ÍJØŠÑØYLÕÛ™ÓÜ’[\\ž’ÒÌSÔ˜ÚP[‘Ò[ž”ÊÍÞSÙ‹ÝšÑ›VLRÔÛRL”“Ý’š™’–[PÛ›“LÚUØ•ZS™”^^Þ[Ô•ŒYÔÖÎVŒR“ŒÎPMRÐÓÙ™•ZYžQÍPÌÙ™QS›”^MÍŽÐ]ÌX–Œ•T›QÌÕ]Ö]–ÝMŠÎœSR™’“ÍÓ\ÒÞT˜œZ[R™V˜ÜÒÛZ\ÜÝ‘Ù\SžZUÎMKÕ]ÎU
ÎS^”šUÜÛ[•’XœÝR›XÝÚÚ•PX[MœÚR’R™ÕZ’–\\L™ÞØ˜Ú•ZÝ\ÌšJÍÒNZ”JÊÎ
ÞŒÝ‹ÙZÕšÔÓMÕL[Ö]ÜÝY^ÞÐÕUZœV“Î\ŒÍÜ‹ÌÑÙ^–›Œ‘ÔZV›M‘RÚÑ[LŒ’VÍÌMQÕ“ÕÑÛ™Lž–YYXNÌQÒ”MRžŒ‹ØÌ™›œYÝËÎNKÊÝËÝ™™™‹Ý’˜ŠÛŒ]ÌÝÚÊÊÍÜQ^•›XU\QŒYÎVZSÐULU‘œÜ]UUZÍT]ÚLMÓM“ÛÍÍÖ‹Ù™ŠÍÍ”Ù]‹Ý–‹ÓÎ[‹ÝŽÎØYY–S™ÑÓ“”PPPP’”‘Q•QUÝV•ÙÚU›ÌÔ“™ŽSÓ–RÒ‘’Þ“‘œ]Q–ØÌLÒÐP\‘Mž’Ý]V’˜VPÒÝ›NÙÑ’ŒMËÛ]SÍÓÌÚÛ‘U^]ÐM”YLRSPQ^‘LVUYL™QYŽLšÚÙZÓ››QNŽQÕÚ[[Yž’Lš–™ÔQšÙÖ›–PSÙØ˜ŽSQœ–šÕØSÕÙYœXÍÛ\•š™UXV‘Ü‘šÚÕœ›\ÜV˜ÔØYÌ‘œLÍØRÒ[š™ÎÍ›™–VMÚQ›˜–žPNPÕ”›^TÍLT”Y\Ì›ÓQŠÞNY›TRQSM“^]ZÒ“T••P”Í[˜RRXÓ”•Y’‹Ð‘ŒËÝÕ™‹Í‘QZP“[’TÕÔ“›ÕSÒÙ]T^ÒQVZR^Y›ÜÌY[ÚSŒÒÌœÔ‘’MVžPÝÜšÞ˜ÜØÐ’S•JÚ^MÒ’Ñ“MÖV[ÚJÖSØ‘SÕÒœœÝXÝ\˜ØžXšÚØPÑ˜•ÕÜÕTÙÍ
ÖUÕ•ZRZ”Õ•Q‘“ÞMKÓÞšÒÊÕUÚVL[ÎÙÒÚVXTÓœPP›’–T™LXÜÙ˜]Øš]–›^R]RYÓÐŒÓž–^LRÝ\ÎQRMÌœ™Ì›ÒQ•Ú›]Ù\›ÕÕÔÛ]ÖQPÓÌ[ÙÎÞÚ’YPŒLÓžRÐ‘ÚÍZ’\ÙPÕUÕQ
ÝSP’ÓÚULRŒ‘ÚÔPžMS’V–KÎÚÌÖŒŠÙ•KÔÖÊÊÛÓÍ™ÝV[ØÜ›ÝÜÙÜ”R‘œ’Y’]ÙÑÐÓÎN“QP]]MÖ”•Uš›L•YÑÔ’ÒŒŽMUQÑžšNZ”MÕ˜QRLÞPPÛÕPÞZÛÖM“–SY
ÜÕVÍ˜œ\\\‘“‘ÐÐMœÒKÑRÞQYÒ‘^UŽÚ\ËØÓM“UÓÕXUÜ
ÑÒ’Y›œÐÓ““ÝÐÌ’TÑUSYÛÙXL]ÚžÜÓ\Ò”ŒPÛZYS”ŒÝ”[ZRT”TÖSTY•Œ\ZÖSÚÑœšŒRÖTU•ÎQR™ÜÌPSÑ›ÔÕÙŒZÕ›ŽL“’ÖŠÌÑÚÛR™\Ö”UUUPVTÒÖŒUNS^LÍX˜‘Ô‘Ü’R–ZZÍž”SÓ’ÛZT–žÐR”[››šÝÔXÛMS›ÞUšÖ›Œ‘”ÍÔœ™’NU™Ó^’ÕMÐR˜ÙÍššT“Ü›ššŒÙÒÖ“\YM[ŒšÎPRUÍÒQÝŒÒ]ÒRÔUØÑÔZSÚÓPÚ™ÞÐTÛÓMMÍÖÜÛ“\’™šÍ––•]ÕLÕÕZÕÓUYUÐTÙŒ‘SÒÙÕŒQÝÝXŒÚÝ[›™Ò’™ÞPTÒXÍRQÜÐ]–\ÚÖZÒRÛ]Ü[ÞMÕŒÙÖ‘“]ÑÖÔÖ’ÔJØZRÛST˜TTÌÙÛÒÐQ–”VYUÒš[JÒÝÑœÔœZQÑÙŒŽ›Ò“T’TUÑMÐ“XÚšÖPLU[ÍQÕ[TZZÐØ[’Ù˜P‘Q’œV™Ò’\ÙÕU\XÑYÒRVLQ’ÛSZ’RXYNSÊÍÎ\Ü˜Ü™T“Ì
ÔÌ]M”‘ÍÓÔQ’ÚÕÜTØÖX[SÑŒQPTØ”›[Ö‘Œ\ŽT‘LZœQ‘YÞURS]S^XŒÍUM‘ŒËÊØÝ”ÕÍ–MÝ’^‘ŒÑÍTØTVX’ÌN]USš’ÜÜTÖ^•\M\”‘UÐT˜Y›žŽN
ÙÐNKÖÌÑL”“ÚZž][šZšÒ›’ÔTÓUU•ÝÛRŒUÒTÙM’“[ÒžšU\ÞLÕÒÛÓÒÚÝZÐYÚQ’“YÞY–›ÕQÔVTQPUÐÎ[š˜Ñ\\ž”ÖXVMÍÚ›š‹ÑÌÖ™[ÑXÔ”[NÓŒS“MŒÔ\ž]UÝ”›]Ò‘RZTÛÙPÒÓL[Þ^U\ÍØ˜›“SÎÓŒ’ÍÒZMLŒMÐÜ”[•™Ìš^]˜Y’ÓÌTUUÑXÚÍQMQZÍR]™™™RÝ”ÝYNNRL”UUMZZÓ’“]Q
Ì’ØœÐ™˜QÜ•ÛØMQÙZœ^TRÌR˜’’ÜRQÔ’ŠÍ›RÌÝÝT•^TÎVÌ“ŒZÒSÌÞ›ÙT™]’”UŒSÜÖS[ÍÌ’[Ý
Ò‘YÞYÚÌÕ™ZÕ[\Ü”XLKÍØËÍ–V”ŠÖ“Ô’\NÓ•QÐÚ˜XÐQœÌ’š’QTMR\ZRÒÐÑÌÜÛ’ÛÜ•ØS•ÚÚXXSžPžR™KØQMÝŠÔUÛžœÞ›ÓÔZPZÐQÓSÙŽ]KÍS‹ÎZ
ÙŠÜËÍJÓYS]Î˜ÖØœNÐÙÓÑYŽXÖ^šžSÜ\˜\š“Ü•Ô’™ÝÕÞÔÒYÑœQ\VR^TÚ˜YÍMÝ‘ÊÛÌÞŒÌMÊÍP™NMšÝ”V•ËØQXÎ[MÙÕÔÜUZÑÔRÕQ›ZÝÕÙÜ[VZœRR[ÜÞ–™™‹ÍXÊËÝKÎÍLÝ‹ØÚ–ÍÞUŽYœ˜Y˜”VÛ›PÕÛY]LR”ÜÒZV[Ì“”MLMÚTV›Õ“™™ÝÊÝÒRš’ÍÙKÓÝÚŽŽÜÓ›Ü“™“YÑ˜KÛ“ÝN^SL”ZÝž^]TÑ\LÌ]\
Õ]ÞÔšT˜JÍÜÐÛ“L[\”ÕŒR‘QœšÊÜ‘šRÌ^Ó™’NLÔ‹ÝM•ÚM‘ÌÒÍÌL\•VUžÖT^ŠÖ”“^œ\ÕŒSZ˜PXÓÔ]˜M™‹ÖMÒÝÞžRÒTXYTÑ]MÛMÝVLËØœ‘ÚNÎXZ‹ÓZ•˜œÕ‹Ìš˜˜ÌØ˜ÜV]ŽSU[ÒZQÛ\Íœ[ÝËÝT‘Ý‹ÊÛ–ÍÜV›•šÚÔT”Þ’Òž\Ó•ÑÔÎPÑÝÒÚRÐÚ˜ÌÞšZŽMšÙÌ[ËØPÑSšžœÙÍÚÐY]›ÐÝ]YÛ™U›œ’ÖRÚPÚÝ\ÕLÞ‘”“YUP‘Ý”Ý’Ü]›ÒÓ˜™ÎÛ\\YÜÜ\RN]X”NRÔÔž•ÊÐÛÑÎ]Ô””Ú’RœL“ÓÍ›Ô\ÌœÊÔYÝÚT‹ÌP‘“\ÜYÎ’ÒZÕÙRšQÐÍÐÍŒÕÑÒÛÜŠÔšÌ“žÓÍXÖ‘ÎR‘šRÙÜ[PÜØPœ’MZÎQÙ””TT–VÔMS^Yœ–ÝÕ“‹ÌžœÚÕÛÞ–‘ÝS™™ÒPÒ–ŠËÔ[›ÚZÍ‹ØÞPTJØ‘ÓÚ‹ÍSÍP[[ÚUÚQS]YÚÌÖÕž^YVR]ÌMØ[]ÙÔP’–QNYZ’‘”œ›LTUš
Ø[Ö”–^–›’]T‘œÕZ’ÑšÑ›ÐQÑØØXSÛQXÎMQZÒQ’–™Û]šÛ”\ÚR–‘\M–[TÊÔRÝMÐÍ’MŒÝÒPSZÑXÚY”\[ÜTÑÓSÓŒMRÌVÐÍ›Ñ•ÌMŒÞœÝÚÍÓÐ›ÚV”PÖPÛUÑ]XÑ™S˜ÛŽžÒÖÝ‘M”MÝŽœ˜Q™ØMR”ÜM™ÕÓÛ[XÎJÎÌšÊÐSžL•ÜÞRÜ[ØQL\ZPÒÚÜÖ\PMSPR\QTÒMÜž™ÓÍNQÍ›Ô\“Ø–Z”ŒXÌØQZ“ÎZYR]ÓÙÓXÍ“‘žŠÙ”PŽZYœÒRØPÐZÛÔ‘”ÙS”S›™\\Ñ•ØÚ[˜Þ]Î[ÖM˜‘Œ˜ŒÖ[ÚÞU’ŒÚÍÔ‘Í“Ñ\ÍZ\R”\™š]MMÑXVRšPŽVX–ZVÖ‘Í]ÔTÎTŽØ“’SÑZTšÎÑZNS™ÍŽ˜˜Ì[ZÒPÚÔÑ›ÍUÛS“ÝVU\TÔÒXS“ÌÍ’M‘QVQÔV•“Ñ›YQZšQ\\ÔR\\šÚVÌU\“’UU–’•VUÝœ•›šÞ^U‘ŽŒÑ‹ÚÞÔ\\JÐÒRZÝP‘œ“›Ö[ÌÙÜ–[ÊÌÞQ
ÌUØ’PžMÛÙÕÌŽVZÝMPœR\ÐÛÔ^Ñ’“ÊÓÓ]ÔÞQÎJÕÍÐÕÎN[MÑÚÙ^M[‘Ô\\Q‘Ì^™•ÕLJÙÜS‹Ý‘RQSÕ]“LØQÕÝ^U
Ù™‹ÓÎLËÒËÔNÒÜÙÐ[ÕR•›”žXÑPN˜PÖQŒÐTQJÓÙÞQ\š[ÐÞž[•’ŒÍQ”XMVRÛ”PÑžžMS]
Þ›Ö‘ÝÔÝQÓVLÑÎS•TžŽRLØÍ[VS‘–LÊÍ•–]R™ÐšQ›JÒŽUŒÌ•ÙÓÍV˜Ö”YÑÓÐ[ž’JÔÑÌPØšUÞV^›‘Ñ›Þ›ŒœÝVP˜]]NNTS•šÔUŒœJÕ‘Õ™•ÍZRÍZ[TÞTÐÍÌœÚ]œŽËÍ‹Ý™
ØSœZÝ”“ÚÜYM‘\N\Ð[ÎV^ÚÒTÍÙØœTÜ]žU•ÑX›^^“[šS˜“Ó‘’ŒÝÛYUQRU“Ì›ŒØÛLŠÊÍ–XUSZ‘S™Ð\]L[˜QS[•[ÒÐŒÖÓÜÜSP]YUÞ’ÕYQ\^SZÑZÞ’™PU’^–SÞP‘žL–UÝ™N‹ÌÕQŽ\’\ÚÜÕL]ÓPRÎ‘•˜™VžžZ”–ZPQžMÌYYÛ\USÍÝÞVUYËÒÖL–]Ó^UœJÓÒÚ‹ÍœØÎMU[–ÐÐ\“T[UÔ‘U”MÜ›ÝÛS™“ÜŒÝYQŒMŠÜÞÍÒÚšÜYšŠÙ’‘ÔÙ’JÜÊÐUSSÔS“[ZVÝÑXÕÌÚQ››Û”ÖŒ“PRÐZ’PQQZÔÔXRJÌYQ]ÓÜ‹ÙNNP–‹ØJÙËÌÝÌYÙœÛŒSŒ^Ž[“ØÎÕ”]UœšœÚÜÝTÚZÞY’]”ËÑ\•™YNNL^Œ™‹Ô–ÖÛ‹ÐžÍ]XÎJËÝMÔÕZÌÙÞY^’ÕSœ\–XZÖ˜PØSTÜÞžRŒV”PTÒ”T˜ŽÛÍ\ØŒÌ’SÖ‘TØSÔÚNJÐMš–Tž›ZSŠÓ”ÊÍKÓ”Ò›’\PÎJØÐ–SLMÌY[ÌŽTÎM^N”UN˜]ŠØ\Í’^XYÔRÒM›MV[šRžœÍŠÖ‹Ö[˜ŽZTZYÑÔT™Z’šM\™Y™œ’Ö]›MÙRSÝ›Ô•Ñ•LÌŽXXÌ’›^›˜ØÎJÓ^ÕÍ‘•Ü“ŒMŒ]Ò’Ö\Þ”RÔLÞX]P”]Œ[Ù]›ËÛ”Ò›ÚœÍXVÕÕÙSQ“ZMšÚŽM”
Ì˜RKËÞRMKÕ
ÍQÚJÝNVZV’”]ÚÕT”•P›ÊÑ]SÔÞÑÐTRÝM–Í’™ÙÑÝÑS]œ™“ÌJÔÑÜMšÒÞM•[Þ]PÖœÞLXTœÓ”Ñ
ÐÞ•ZÒ’™ÚÔY”Ü‹Ì•L\NŽQQÒ]•Tšš]SUÓ›TšÚÌSÖ’ÓÒÒPPÛ–™ÝÕV\ÚKÕÒJÙ“YÍ•SL”ÍSÐ^–ÔÜZ[•LÞLÔM•Ò’Õ]ZšUÐL[ÞMÔ›ÚQÙRÑÊÖZJÖŒÐ–\Ý•ÌLMÔ•ÎTY’Î\VPS›“ÜQQQLV“ÐÜŽ’Ü•”^L’•ÒÎ
ÒSÍ’Ú‘PÓ›’“ËÖTÍLØ•PPÛÍYœŒ\‹ÚœYÌÖÍ“œÐØYÝÚ’™\ZžNÌNX^“ÍQÛ˜ÚQÞ[ÞJÒ˜ÜÑÑŠÙ”JÑÝM\QTÛžÛÙ–™ÒX]U‘ÝÓ–Ù”‘Z•T›RÓÛÔ™ÕØ^\ÞÎ–^‘šÛÕ’R•ÛZ]ÌZ\TNPXMÖYÎYÍÑ“ÚÓÚ˜ÚUžTYZYÍÞ˜ÑÞÛVœ˜’“ÕËÙU˜Z‘\ËÜ”L[ZÕ•QØXÌ•YÍ˜ÜM‘˜˜ÚÖUÍ[Ù˜N^“˜ŒÞV›ÌÖ’LÑÑ•ÙÞSÌÊØUYÔŒ™N^YÓÌRÔÕ“ÚÛØ‘Ô•ÑNMÞ™šSÔSÐ“ÑÔYÝÔÖ\ÜZÑUQVÍÛÙ[XQRQ’^YÜ]ÑÌ•ÙNUMÕ“™UM\TÑN[Ñ˜M’–Zž›YZLØ‘Q–X›•SÐ˜Ûž–MËÌ˜‘RÚZQÒ™ÕQÖZ[VÓÝÞ‹ÝÝS˜[ÝPSÌPÍXZNT™\SÒ‘TŠÑ™Ñ›Û–ZšTØÕ•Ð]Í‘ÛÛØÕ\^œ™]“TMT›”ÍQ\Þ\]RØSÔžXÔÛÚšTŠÌPŒœYÝSÐÑRØ›ÑYÕÜ‘ÞRŒ‹Ý›’ÌÒ–VÎ™]˜›UžŠÐRNÌ›ÚÒ‘•ÊÌYŒšQÞ›M
Ú[ÜÒSÍ›ÕÔÚÕÑ‘”\Ô““U›‘ÕÕÚ]N‹ÝÒJÙœŽ]ÝÞ“Ýž]žžM”›^MÑšUÓÕ“MRSQÍ‘“ž^™ZÙØZPš›Ú]ZÚKÙÍ›\žœžKÚVŠÕSN–ŒXÚžÔ‘ÕÚ’ÍUÐš›Û[Þ•MÕMZØ“[ØÒ‘ÒVÝ™›PÚÔ–Ž^ÚÙMÓZŒ‘œ\TŠÝÛÔYÚÐYÍÔÒÐÊÎZÕM™U\Õ]ÖT‘Ðš’Ý[ŽœØTœ–™LM‘PMÚŒ“Œ›LÙMÒÔ“ÔLLU‘SUÍP]ŠÚ˜\MŽÑÒX˜ÒŽØ›‘UŒÒ”Y˜œ‹ØžÓÜ“ÖÝØ‘VSMÌÔÐ˜Q›ØÌœQÙŒÔN[“PŒÐÌÚ•“ŒZÖ›ÙÐÌ]šÚMÝÌÎÙKÎÝŽMÐPJÕ“Ü˜SUMÛ’Þ›‘YUÒXZÕYQÒÑ\ÔUÖY“ÛÕÞUÛ]R\ÝT\ÜZL–MN\ŒÛXÑ]žRÛšÍÝYYœÓšVœ™Ø–\ÝUZUPP™”LÛ›Þ›PRYVPP˜ÊÒŒŠØÕLÒÌÒ™NŠØZÌ–Ö^™MLQSSÊÐS[‘R•ZVTÐšVPÍÊÕ]ŒÚKÊÝ‹Ó\M]Þ”ÓSÒØ–’RÒQÔUÛžšMÞVNSY^ÒÓÞ[MY‘™ËÖ˜œKÙš‹Õ[ÍÖ–LMÓÝ’ÎNQËÊÒÞ™Ó˜JÎXRÓÔÝÐV’ÕYÌ›Q\Y’ØUÌÝ™Q›‹ÖœËÜ•‹ËÐ“ÌÝÔ“•\•TÍÖ•ÐLÙ]YÜ’Û”œ’Û
Ù–›\PÙœ[ÙYTÍÍÒÖ˜–›Ý’ÔšÑÐ^YU”ÞUÝ‘NM^YSÝ™ËÌÝÞÙT–ž™YÛLL^LÔ“Ý]JÜœRÌ˜ÓÒÚÞSÝMÝMÓØZœÑÕLQ™–MžÔÓTÜ•“ÊÍÍÐ™JÓœ–Ü›˜LØËÎYÚŒ
ÑPžQÌ]“ÙL“ZÖ•LœPÐZQNZÔŠÌ”›ÞLXÐžR
ÖRÞ™˜]R”ÙÒ
ÛMÓQX“[Q[™ZPPÌÑÝQTŒ\ÝÌLLLÌÌNQSÒÕLœZÝUÓ]›™ÛšÙÍšÕ’œTÜYÐS””ÙÝVXœÕŽ[ØZŒÕUÓÛSÑZ•KÚÍÕÑQÝVYVL^“]ØÌÍÓ[ÖÑÞ›U–Q‘ž“M“[NY˜Rž–˜“MÙ’ZÝUšÞ\•
ÛÝZXV”ÓXLÙÔÙ’‹Ù]ÝRLÒÒÚNLÌ˜MÜÓMV˜T’ÍŽÔ”Î\UŽXÜÖP”Þ]ÓS–•QÕ‹ÍœŒÚÎ–ÌÜÔYR™œÑÑZÑÔ‘\ÓÍŒ]Î]Í’]Þ\žžV\ÕÚ]Ó^ÌÝ[U[Ú‘^TÎMXÍÚž•PTM˜Ý]ÐÕ[˜ÑÔÕRÕÓZ“™\L˜“NÛU’˜S›YÜ‘M[[MÜÌ–SUØ–Þ‘]ÞŒ]\Œ›’ŒÒ\žZ™ÓM]XÝT[ÐœNUV”œÎÛ]‘Ý–Z•“Õš”‘VÑYUš›ÔÙÐÚ“P“M™’M•ÕX”V\ÛÓV“˜QÕÕÙTPMS•MTL•šYÐ˜TÜÛÜœXTÕ“šXÖÐT\M›VY›Õ“ÎXŒ\SÒR‹Ù”‹ËÓJÌQ–‘
ÑÔUULSYž”œžÔ^PXL[ÐNNPÑÞ–Ø’Ú^L’ÙS›SÕ’ÓŽT[™‘YZÝ]RNÔœ\ÚšÛÚMX›ŒÔ[V[ÒM–˜‘T”ÐÝ\ÒÖMÛÛÜÙ’]•VRÕÓŽS•RM–‘ÌLØ\Œ›Q›ÛMMšNSÝÚJÚÕ™Ü^UÔPJÎT\œLÖMS‘ÎR’œÖœÐÌJÐÐ˜ŽUšÙNPSTŒRÜÝÍQšQVŒ›ÍÐÑÐÍžLÙÖœUÕR‘ÕZÔÖ’ËÛLÍLŠÝSÝ–TÍÙÜœÐŒZYŠÙÕŠÙ^™ÓL™UÜÑÚÝ–”œÕŒÜÔ’PSÔRZ^‹ÓMÙÖ’Ö˜Í™ÝÒ[YÑ]“ÖÔÓU”’œ™RPŽVLÕ”ZU\]ÚR]Ü]ÓÐN\RT›ÍVœÕšš›ÖZœR•‘[‘LÌ›YÙU˜Õ”ŒÓ]X–Y–›ØÌNYÛT›Ó“^ŠÖ›ÝÔPUœÒšÜÕÌÔ[ÐRØ‘–NLMZQ“MXÜØ]ÛÛÝSÒ™Ú“[L••UÜÛÚJÊÜRZÐÛÝKÓ˜ÑV[’ÔÑL’Ñ˜Í›ÛV•L
ÌTZ–ž^›‘SÐ’ÝŒ•ÝÛL“ËÑ^\\VÑUZÛPLœÞZ‘M–“[š”ËÍÊÓÝY›“–œ”•ÚÞŒšÝÕYÝS”\˜ÎÛÓ‘ÒR™˜ÒL™ÌS]”ÊÕTÔÊÚËÑÝšÛPš’R“R]ÙÌ’Y]Ý^RËÝ[ÌÒT››ÍTÒ™SÜ[Ñ™URY[ÖSš‘ÕR\ŽZNNÜN
ÚKÙ™ÎÙ’–˜Û™NLÑRLÖŒÔS“ZTÔŒÌ‘•ÖŽRZ^^PUÒšMPX^–TZÝØQUZÌ‹ÕÝQLR™]ŽÙÐÒXÒ•ÝÔØŒÙÑÒÑ™YÓÌÚ\[ÝÙ^Ú\SÞŒÖÚÝÝ”ŒÒ]X[›Û‘ÓÛÌJÓ[ÝŒMMLÍ””SÚLÛÛ›ÍZ™œ“[ÍZÕžÍ˜ÕÎœ”•Ú\Ü^LÕTÍ˜ÊÐÝN\’PLUÌZM‘ÙÍÍÌž›ŒŒX‘MÕÞ’QÜžLÓPÒšUPØPœ“X•–M
ØËÙLÙŠÐÔšÜÖPÚÚÛV]]ÎPPœ
ËÑÕ‘ÝZ™“ÙÍÒØÍ[QØÕ‘MSVX\‘”MŒÞZVUVÐÒÐ[Q[^MTžžŒV”ÎJÑÐšS“T•V“œ”šS“™ÙÝ”ÙTÓž[]™“M’Œ]šN]Û˜MŒÔM™˜\ÑXÒÎÒÝT\ÕÚ›]šR[R˜ÜØž›‹ÙU[MMÞJÎM“ŽÐÚŒJÚÐLÕSV“ÒØšÓ[ŠÜXPÔS\‘Ì^N•ÖËÖM˜MÔ“ÝSÐÝQYÞUUVQÔV‹ÒSKËÓYÖ•‘LUP”Z‘[ÛMRLÐÖZ\V“›žËÎZ™ŽMXÙY]šŒT[šX–UŠÕYœÙŒQ]ÙÚQÞ˜™Ø‘‘ŒP’LQÖUZVÖœUÞ‘™œ•šJÝÖ^QÕÔŒšMÕÚÖ›•›”’M™™JÙÞ“Ö\“’ZXŽ^–“ÍÒÍÖ[]’ÖTšV”YP\Ó\UœÌRLM]œŒÌY]ØÒ[XÝÚ^Í’ÕSXUL’Œš›MÐM‘ÑÌZÝ–QœÌ\ŽÚ‘RÚÝ
ÝÎ[ÕZœÍ‹Ü•ÝŽUÒ\M^[˜YŒ“œÛŽM•UÌR\ÕØœÓÙ™Tž–YšÞY“‘“L–›\ÓÓZX\˜žŽ›\Ý•Õ\KÚÕR’Öœ–ÚÒÎZL”LQYTŽ]–ÙÚ”LÙN[ÒZÑLX”UÞXXQ\SÖšœÔžËÔ“Ý’\ÞZ–ZÌ]šÌR]SNXZÓÛ••Yœž‘V”ÜVŒ‹ËÕ‘RØœY\Ó•PÚP\žX^NÍ›“TRÌ‘MQÒU\PÓ™ËÕÊËØYJÖ^œMËÎR
ÊÙžMTÎM”PÐS’™Î^RÍÛ[Ì\ÐVMVšœšœÐ›š›Ñž˜ŽY[]Ô•T[Ö\PÖ’]Ý[’ÑÍ‘Œ’ÔÌÔÞÙ\LL“Õ\TÌš›QY\XÒ[ÑÞÜ“ÒMLÒÒÓ^UÜšÌÕ‹Ý^˜QžšÔPÕT–™LL’R™LSØÚ›TÞÐŒ•’X’•YÛœ\’•”]YV\S’T“Œ“V›šL[ZÒÑ“šÒ“ËÒVÍœ–ZÕTÌ•QQ\”•Ô]“]JÙÙÒ•›ÍM™ÖÜU–V”•TÚUÒ‘ÊÔTšÑQ‘ÌRU”™MÞSYPZV’T‹ÙšÍÔÍ›ËÊØ\•XV“™RU’š[”^YT‹ÖS^•TUÐ™XYÓSŽ]ÍQ›››\Þ–š[™QS˜ÙÝÞ[MLUYÐÚÚÖUL–[•ZRš\–RÌœ•LÌ‹ÐUÝ“Õ•’LY[ZÊÐ\LÛRÒS’ÕÒ”XÚ™\N^Ð^Í™R•\””’ÞKÌ“VŽMÝÖÊÝÞLQ[•˜•Ý[”ØS•ÓÐšÐ™^˜™ÍQR•SÑÜ”œ\QZ“•ÑÜÑ^ÍØ™Sž˜LÕLM^ÖÑšN]ÓZSÑM\Ú
ÐSL’ÙšžPÓÕž\ÚÙÐšRÛÍ™X•QQMX™Ñ‘YÙ“ZUÚV™Ô™YRÎ]Í[ÔÐÒQR”ÑP––XÕŠÛV”ÎÑ˜\[ÚNM”ÔÕØÛ”^]]MÔÛPÒÕÜŽVšÍ”ÒÒÙÜÝ”ÓÚÑ‘ÙŒžQUÌLÜ‘U’\šÑÔ–‘ËÒPÓTS^QPŒNYžž›ÕÍL”RŒ“^]SÕ™ÝœQMUPMUUÐ’RM–”›\ŒÚÛÓÝ–VÙÔ[ž‘Ø^L’›U]Û“ÚšSÍ^“ž›”VX“QVQ]ÛÒÛœ\œ^™RÖUÓ™YÔQÓ]ÖZÒRÑ]•”UNR[ŒMÌPŽ“•R\ÚÒÚNYœÜT^\ÛÎ›U˜[Û–˜Ó•œ’ÞÝ•š““Ó
Ú]PÓQUÖTRYÚÓÜœËÙ“Ü\Ù“Ü“ËÒÛ‘KÝYÝÎU’S[Ó”Û\[Ž^ÍÖQÕSÒÓÜÞRÙZÕÑÎ]ÝSÑÞŒÓ•ÙœÐKÕŒÒÝÌÚšÒŒ[’ÙYÝÍÓÖSÖÓ“Ú’SÝ’Ò•N\Ó–“ÔÑ™ŒSPÛÜPL–œÞËÑTÕP™\[Q–JÍŽTÔPÙYÜÜR–‘MšŒ\VTMYÛÐšØÌ“\MÙYP\‘œ^PNSPÒS]™NLÑÌÛTÖYÝ‹Ù‘QYÝÕ–ZŒÔÌLZP‘]ŒRÞ“Z‘Œ™ZVSÒSZÙÔYT^UMUŒŽ]ZŒÞM›Í˜TÓ[SÜÑXJÌTŽR““[\•˜‘^ÞL”KËÌXÞ“YKÜÍ\ÒQ^NÙÍ›šÜØ›]™Z”ÍÔœœT’NØ”ÙÚ\ŒœVšÓŒÍ’›ÞPÌšMX”XL‘ÙÝKÝ\›ÌÛ]T’Û”]ØÓÕÌ[YPÛ“ÜT^TÚQ••”ÎÍŒÖ[[ŒÒŠÓÒ^•šÚV™U–MÒžØÚšÌžV›Ò\’ž”‘‘Y™ÌËÞQÕŒÞÔ‹ÒSÕÜ–S\ÕÒ–Í[Ô“U[ÜMØ\P•QØÕÝ“šÔŒTP]ÙÚ˜››[ÜQ›]ÔÝ[Ø^‘œÙŒ”‹ÍSÞÎØÎ
ÍÞ›ÍŒ‘ÛÔÑ[\ÛÓKÛ]ÌÛ^™KÒLŠØÊËÙKËÚ™KÓT[Ó”ÒR’RUÔ[ÜY]ZÞL•–TJÎÎ]žRœ[Î’‘M˜•’ØÌžZ˜ØU“›JÝÎ]ÚÒPLœQ]ÜNS“ÍœÕ›Ú\”ÕLYÒ^RÑ^ÝÕQ•œ^UÌÙQÌÔÔ[˜ÌÔÌRœ]Ñ“L\ÛLÓÖ[ÝÜRX”™V\Õ–\ÚÛ“P•RÎSÌX™œZ™PÛŠÚPÖ˜VÝÕ]QÌÛžQ›ÑžYRšU]™Ž]–žžL’žšÕUšš˜]Ò^KÙÛÍ^XQšŒÔZÒKÒS‘’YYNÒLLÌÍ\ÑÌ[PÑ[]VÕ”•“œÕQ‘]–Û‘œLR–’˜“ÌÖ]RÛKÍÕ•“ÓžQMÜÜQÛ]™Ù”ÕU]ÎL‘Œ”ZS–“ZÊØ]ÙÐšÛžUœ›PÐZ]••šÕQ]PÞXL]ŒMP›UMLLÕÍÔL•[‘Ì›Õ”Ý‘YÝŒÓÖPÝÎ]ÛÒÛž”™RÚ\M[Õ‘”™ÜÍžN]XØÞ^ŽJÌY™‹ËÑ˜ÔŽQ•]M“ZQUÕŒ™™›XLY‘ÓžRÒNRŒMYÔ”Ó›LTÖQRÚÚŒž]\ÊÑÌÝPÍQZšP›™]”S^MÓÌ™Î[XÔRÜ^USYÜ‘ÜÝU›ÌRÛšŒÎ›ÜÍQÕ‘S‘™™ÒMŠÔ]Ó]ÜXÕÞ”–TŒPY•ÒXXM•˜Ü’”žY”ZQSÍÍ™ØÓÚÌ[œœ[žPQØUÕ[ÔÚÕÑÙžÜ]ÎXÑ•œZ•Ò“ŒS‹ÛTÕÙRœœ]ÜÑ•ZšÍÔÞ™ÛœV[R˜ÌRZZÐœÕMÚ‘ÕZZÐ•‘MŒ˜˜ÌŒ“šZZTÕZYÛ]ÓÍ“™ÔÒŠÖ‹Ý™KÔLŽNÑXÚÒ™Ú^•Ô›Ý–TÛQÛÝPÛ]ÌNUØ‘Ú’šÎSšXœR]LÔ^’•ÜÝMØÎUÖÛÌZÓÝÑÕÑ[SQ’™
ÌZ’ÚÙ[ÜÐžÔÑœÛÛÕÜ›ÔÓ•ÝŽÞ]ÙÍSQÕÖ\™‘M”Ô]Î\QUÝÒ•ÙÌQÖYSTYŒYŠÜTÎ]‘ÝQTMØ”“
Õ›Ì˜ÍÕQÌÝ˜RLÐš\Õ\Ô’œL”–•X]ÑÜPMÚÌL–ž^˜™ÕU”Q˜M]]TN˜žšžS™ž–‹ÊÒN\^T”XZÐ[“ŒŒRÒÝÚ•œ”ÐÙÛÚÑšžSÐÔ\ŒUÜ]NL›‘PÕS“Y›\ÛÙœ]][•RŒQšœ\œÞ”QÚ˜ÑÒ•MPÜ“R‹ÙÙZÑÞ^ŒÔMPŠÙŠÙS“[ÍÌŠÜÖXXÌ
Û^’›”YR›™ŒÌP”ÌÖZŒ”QÐÒÙÚÕR[ÝYžœÑÛÜš‘“ŒUš™Ì[’
Ò’QUÍ’ÕÔ’UZÖÒ˜ÒRž•ÕÍ‘ÓÙ]LNLÔÓš]šPÚXÒ’•Þ]Qž”œ]‘ØÍšÒ[ŽSŽ]ÑÝ”›QS”ÎQ”ÍÕZ\ÕRÝÙ\VP–S\ÒSÝYRÞXZZÕÚÖQ’]XLÚÌÛÌÐÐÛšŒÎ“ÌÎšÊÛžZ–ÛRSS\S–›ÒYÊÓ’RRNYØ”ØXZQ\UÍ•MXÖ[[ÓšÌQŒUÌ™ÓSÌÔ”ÑSÑUÚÛQ–^\ÕÓÝ^TÔU]ÖN\ÐPÑZÛXÔNM]ÕÐÒSÒ”žœL›ÚÛVXÑQ•XÚÖTØ’ÛLQPPØÔ‘ÌQÚÚŒÔUÝX”ÙÖMš•Ø\Û
ÙËÖ‘™\˜Œ\“‘”U‘RžVœÝÛS’Õ”ÒÖ’PQUVMTœŽV›Œ‘U˜ÙÖUÜÛYÕŒšÞY›Z•Ò‹Þ•TQÌY[šL]^ž˜NQÑ’^“’™œV^ÒM›MŽ›˜XÙ[ÍÕÐÜœÐQÍÒ›Ð[ØQT”™T”ŠÍ›]ÙÒ’‘ÝLJÙÜ“ÑP\‘ÙÝÕÝÌÔURŒVZ[S•NL™Œš[•ÑÚQÒšVZUZPÌËÜŽTÜš•ËÑÔ‹ØÞR‘ÙšØÜ˜\L™“ŒQŒQ˜JÞX[LSYÌ[ÜÛÛÛXŒš^Œ˜Ü’XUT›ZQÍ[RRQ›MPQ”\’TSYŒSÌ›Z]Ž]R˜žžž™ÜVžœ›VÛÑXPV•šUVQNRÎS]UÞ™Û^ÙMUÑNLÞV›TNU•ÐšÌ[RÎ“[UÊÍØÌŠÞXRÌ•ØQÑšÚÔT’ZÚTÔ^Û”
ÓSYÞ[ŒVLT˜’›QÌŽ\Õ^•ÖRÊÚZ•ÕÓœQ›ÐœÌÙÞÑP’•›UÛ•ÙLÜØMÌŒËÝJÚžŒÍÓÜŒUÓTMSÖ™Ö\ÙÍM^Ñ\Y\œ›ÝÚŽUÌ]™“RUXÓÞŒ“PMÓÖ]ÐÌÕ[L\M••]Zœ\X^UÑ[SÍÓ\ÜÛÒÌŠÝÝUÛÖLœKÑÔÐ˜ÙÚ]YNTšSS–QÕÞ›XXŒRœYPMR™ÒMŒVÍ
ÒÛ^–[“•Õ[“ŒLKÒ’“›L‘S]ÙSÞ’ÝU™ÔÕÓ’™XÜÌœTŽXÙ[’›˜]ËÒPQÚJÙ^TÕ™MPœÛœ‘XLYÌVŒÒ^‘ÞPÜ]œÜÔ
ÒšSZÓÙÔRQUT–›ÎMÞŒP’ØÝÚP›VšX›^ZÔŒQÍÖžLÒÒÛÖœ”ÔSÛ’œÔÝL^ŽŒXŽÛŒØ•ÍœÔ][•[ÚUPŽNÒÞ[JÒØÐ–•ÒÕÒÒ’LM“•ÌÞZž˜RŒXÐ™Œ’ŒÞLÐ›]Í[‘ÒÔ•“M‘ÙÚRŒÝÚR’[ÊÜÎXÌRVY™Í•ŠÚQ›Ò•Q’’ÓÎ]”Œ]Qš[œÓœJÞ^‘Z˜’VÑÖ\RÐšTYœÚœ”ÙN˜ÎKÊÙËÊËÓ–šžRØÌ˜Ö™ÓVKÓÌÝX”SÚPœÙ–‘“™›UÎ[ÎŒÚÎL‘]”NLœUÌXTPÒPYSÒQšÑŒ^ÍL
ÍNQšZ‘Q]•TQRYN\\ŒZÛ\›”ÒÍžR™ÍŒÖ[’TÍVV˜ÙZXÝžNM›“œÕœ–”ŒLŽÙÕYÍ[S[“UÕÖYM
Û˜›”ŒØœSMœÙPÙœœÛÔ]œNU[™TÐØL‘ÒÍY›ÛŽÑZÒŒÕYÑÞPVQM’M^ÌS‘ŽXYÕX–’šÞ›‘“ÝšÝPšÝ’ÜÜJÛPMÜ“ÔœŽZMÊÙÑœNP“XJÔ“ZÜÜ[T™Õ˜]MRV‘UžSÛ–MÝÝKÙVUÛXPXÐ[‘TÚ’Ó^ŽÙ”MTÙ™ØÓÜÚŒÚœžR™LŒÑ›TMÐ›ÝUÜTÜŒÛ˜Q•Þ˜^ÌL“]ÍÓ›UQÒ\Ì‘™Ò[M•˜^ÔšËÍ‘–ŽXM’\^SÌX›Û]Ö
ÓœÙ™ÛœM[•TYLÌMÖšœÍPŒS]œ
ÛÙRÞU›ÐL•ZŒž“L‘ÙÕ’ÕÒ^šÙÞUSÜÖYXÌÑR‘ÝÜ•ŽM[ÔœZ•\YÛ“šÔ\YÚZ˜ZœÐS]TÛž[UV–ZÓÔŽUÔ•UÙ”Õ‘\•LšRÊÒÍÚ“[S˜\]’NTPPÍ›TZÒVR”ÒTŒšÎQ˜Úœš\ÜÍÐÛ\”NU™Õ™VœÖY^MšTÕ•SÞšÌØžÚVšÕ›žRQ“ÚÐ–XÔ™]Ò•RZÓ›X•VQÛÞ\˜SUÐÑTM™ÜXÐØœ›QÓ›ÑœM™ÐÛÍÍŒÛXTšPN\RÞYŽšž›ÐSQŒ\˜››^žXÚ™JÝR‘Ü[\ÑJÖ™˜XÝØ›QœÚ]ÑÍÛÓUÌ\‹ÕT“VLQMÝÙÒQ•P’[MÜØT’’ÝÐ]]ËÍ\•ÌÕSSÕTÔÞ’ÒUœÔÐÑŒÒ]ÒÕœ”ŠÔ‹ÔÓÌQ^ÜTUMœPZ^QÙ[T\ST“’\ÚÚ“ÓZÛÑQœžšZÒ“V^Ò‘TÛ“‹Þ™Ù\ž™‹Þ˜[Y‘ÝLÙÌLÛX]›™QÞ‹Ò‘‹ÕÚÍšÚ^XZÍM]MT’ÔÓ[’ÕŽ[RÛœZQÜš›ŽP–™]˜LŽRÍžšQÒTŒRŒÝ›ÞŒJÑÜÜœXUÑ^\Ò[›ÒšÚÖ™XÔLÔÓ™XÕÌR“]ŒÎT‘MÕØÑ˜“Ó™ÔÔÓ]YN\[YŽ[ŒX”šN^šÐUŒšY[ËÛTÖ[ÒÖKÍYŠÚÕ]RÌÑ™ÍPÑZSQV•™Ô•ËÜXQÓZRYÝ“ÌJÕÙ]VT^“ÙÕQÕ[ÊÔÌ”SU
ÒÐÑÛØÕÝØ”ÛÌ™”‘QRÞ‘ÍÍÍÌÌÙŠÞŒ–YU•ÝÑÛÝYZM™RÞ^ÒTŠÐU“œÝUUNM’”™U•N™‘Û^^ZT™••TÐÙ›[ÔÕÍMÌKÑ^ZšÛTÛ[‘ÖžRQTŠÓœÕžY’]œ]ÞUKÙ[œÍØYQS]Ú^LXSžRŒS•NPÍÖSN”•ÎT‘TÝ]‹ÍÔÛËÜÐ–Ñ”QL›–ŒÜŽÕ™\UÜ™œž[ÑZ›œ•‘ÒŽÜÝ˜ØRÓš›[”“’QQ]Ö“’ÔNRLÍÝ”‹ÍNQÙJÔ“T[U^•ÒUÖÕÛÕ›“T–ŒRÍMÌÊÝKÑ‘›QšœÓZÑÍ[]Ü\š˜QX]]ÞžZ’•›”ÒÕŒÐ”žRÛ[Rœ“QÜTÔÐ˜’ÜËÜ•ÎÖUQUÑÑP“ÚÜV\”MÖÙœ™ÍÔ‹Ø”‹Õ‹ÙXÞŒÓ›Œ]Ø›œž˜RÖLXÔV•ŠÛ‘\’“›ÙÚÝœQ›ÑŽSUÔ”‘ÔRÐ\”Þ‘^•–™–ÛVÛÝ\ÐÓÔ‘ž–QQTPšRPšVÒÝ]’ÞMËÝ]MMÕ‘Ð‘ŒÓ’Û’ËÖ‘UÝYÝÔÐÐ[ÑÔMÊÕ•Ó[TÌQ•ÜÜ•š’ÝÌ[ÔÍÕX”T]”M“šØQUZVM[–‹Ð˜S–VÚØ™ÜÒSÌ]Z“•–MžŠÜÝSÍ‘œ]RUÒLÞš›[^“U™^SÑŠÌÕT™ÚÌTÐ•Z•LSÝŒQÍ\KÑXÍ’ÐV™Í“ŒM^’Þ[R^RZSU˜LØØ˜QÚP“]“MSÓÒV˜Ù[”ŒÕYÔÔPÓQÓXÓPMQÓ]ÞQRÌŠÖ–Ô‹ÑQLRËÌ˜RV’NPL•L“Ý“UÜ”ÜR
ÙÚÕ““ÙRÛÛSÍXšYÐÔÜ™ÝSÐ‹ÖÑTÞ”TXZQYXQZ‹Í’ÔÜÙšžTš•X^ÔÒM\]SÍZÑMÒÐ‘PŒÕÚ\œ•NYÌ›ÒËÙ›ÞUZSMÕYÜ”ÖUV™QÒÔÔšÖ’ÔÙ›UZ™››Ð˜ÓÜÞ’\RTŽUV•›˜ÌMMÜ“ÓRÒ™Ý–MY\ÜÔœŒÍPZ[š™ÌŒ’ÖUÍÔRQ’\›‘ÒÐÖ”žQ–™‘KÌU•QÕXZÍ]^”P”MÑN\•ÔœÌÒ]QœÍPÒ[”ÓYSÌT‹ÍÌÎÙŠÚSPLÙÑ‘TÛ“ÒŽSÙ™ÒÌÙÕÚËÊÞ••ÞZšZ‘Ô]”Q‘–PTQ–Ð“[’TS[ÌZÕ–›
ÒÍ[ÜÌTÚVTšŒ[ÝÓYÌØZœPV™Ì“N]Z˜ÝYKÜÝÛXLÕÕ”V‘˜\’ÛÓÝ–˜šLÙÍšP”ŽPXÝÞMÔQU•š^S›’LÚLXUSVÐÒXžŒØ‘\RÒÓ“ÜÚÚZ^[“ÜÍÚ™ÒØ]”œL^VžRLØ‘Ù\”ÙÓPÝ”ÔRÖZLØš[U‘S\ZÖV”P˜‘–˜ž™”ÞVŽRÌÕ‘]ÜRÓS[ŽÑ™’ÐY\\ÓÌPÚTÎŒÝ‘Ü^\™\ÔÙÓ[XÒ]NœØÑŽœÔÝÌU‘‘ÜR•Þœ˜Ý™ÒXÕ•’\ÑP\ÍÕÞU“ZÒVšÒÙÒÕÔXÝSXV˜Î•ÊÌKÝZ™Ý‹ÜRÝY™Ö‘T\ŒV’“QM˜QRÖ™–ŒÓ’˜ÔœÜ–PMŽPÓ˜”N^ÝQZÕÍX\šŽRÒÒÒÍ›ÖU\˜ÙÙ“ËÍÍLU›ÐRÑžS™YV\Ô“ÌœžSÍŒ™ÚR’ÚÌ^L”ÒL“S›MXLPL[]ÌÐ[˜œ
ÒNMØÒXÕSVœ‹Ô\SÕÜŠÌÜZ]–•ŽÝÝœNR›MÓ–\˜ÜZ‘‘SÞ‘”žŒ\ÖšÐÕSššÒ[QÝ\Y”ÞRÖžžŒLÒÒ™QÜR\U‘ÕÍÞU•Z^TÔSZÊÒ“žU”“žQ›VNÚTØØÞ\••œ]ÍSÌÝ“ÍNœÛš’ÛÊÜ”MMQÒT’ÜQÚÛœ[TÜÞLÒÙÕ–šÌÛU”“ÝSÙSTÓ›MÌLSÌV[[T•Z[Û]S–“Y”^T\P\–œÚÜÚV‘ÞšTÖQ’ÒÊÚ˜œRUÍ]Z™˜Ò˜ŠÞ›ÌÓSUÌÔÛR˜Í“UÞ’œJÙžZ[ŽLXœž\Z]MRSZ›YÐÙ\YÙØÜžSÍŒ˜X–Ý\’‘LÞQPÔœÜËÞ[™ÛŒQM™Mš‘ÎVŒÖY“XœQ–X]œØÕ•ØÌ“ÛœKÒ“UÝŽ^ÛM]\Þ[T–ÞQS‘ÔÚ’žŒÌÛTÞÔÝÍLL“ÕÍZÕŒ•’ž^UÝÚžRP]UÔÕU˜›XRZ]MZ[ÚÜ’“XÖ‘Öž“^]ÍÒL”Ð›ÑÑ”ÛÌ‘šÖ\ÎLYSÒ›ÌÌNÜÝSÑž˜ÜLT’ÖØ“\ÜRTÛÍœÓÕÑQœØÔQÑ›šÙ]\YŠÜ]T›X™–\ŽUœRž™S™ÜÕŽSÌÝžŽLÍRÜÙÜ[’ÕLUÚ›MžUÞRšÛSUZQ\XÞRZØÌÙUTXXMÒÝÛ\RSÙXÚVT›ÕZØÜž’ŒÔ’Ð•ÑŒ]SÎNTœM•ÕVT‘Û’ÓÎSÌÖÒNMN]ØÓÎ]ÊÖU“ÞšPRQTÙÙØØT•™“Î™˜›œ›SKØ”›YÍ\‘Ø˜TUYZS]“ÖSÜZ™[ŒžTÚ‘Œ›ÛÊÑÚÚšTš•UŒÓÚÖ–[›NUÙÌÔÓÜ\]‘ZÕ‘SÐVš
Ý’R”šTÔ“YÚÝY›ÞU˜SJÑÝT\ÐÍSQÙÜZŒXšÙ˜›Ù]
ÍZVNPZZÍÔP‘›UQÖYŒÔMV[ÑÑÐXÓ’S’ÔÕLÝ“ØÞÎšÑ‘\Ü•ÌLSÑœÝœšZÕKÓ˜ÒÒRKÙÜŒžNPÙ\™ZT[LÐRÑœZMÞN˜Q›ÜMœ\SYSÛÕ–ÜZÝ›MØR‘][ÌÜ•ZMR]ÎQš›™Ñ“ÖSMÕLØŽTRUUÕÝ^NÑ›TYØž–]ÕÓN^™ÞM•ÔÓ’”LRS‘œMÝ˜ÚÚÐ’œÌJÛÌ›Œ^Õ•ÙS‘™S’”
ÚU›ÒRÖTTÌTÔ”ÚQÝÞXT\ÍNXYLNMMÎÔÝÒ[X™ÌšØÎØYÐ\œÔ–R•[JÓ[ÞÍTÍÔÙ™Ù™V^Y•ÕLÓÑÎP^ÚQÔ’ÝÑÑšV’˜LÜŒXœœ’žŒXž‘PŒœÓV•T’“]Z‘Õ™Q“‘Ó•P“\˜Ø]ÙÛ”Þ•Œ”‘LÝÓUž•˜œ’ÛJÒÔYÔPRÞU™ÐV“ÞYžTÒQÐ’ØœUÕšMÓÕTZLLžMÐÛÔTN[R™Ø’ÍØÖ˜Þ˜XÖYÒ–V”Ì˜ÔÝÜV\
ÚœÑQÖ]ÑÍV’šY’ÑÌÚJÑ\–\YÝPXÕXÌPœšÞÙÐ”ÜÒ‘ÌÔL]UM\’^QÒÐ˜Ö
ØXÕÕT]Þ’Ö›QÛÕV\ÒÎLÔÜPŒÝV‘R”ÑTÔ™ŠÝ‹Î›–\Œ’Ì]ÜÜZ\V“UU^[Z˜^‘Œ^NU™ÐTœÛ“Ô•ŒÎ[ÝPž›ÖœSLR^›XÓL–ØÓRLQŽPž›šÐ^RœQZÐÛMÜÌ”[R“ZÔŒ™ÕY”’Ñ”Õœ”Ó›MŒÕÊÓ]‹Ñ–“ØQM“Û–œZÑX]Ú•]ÍÝRRÝÜÕ˜R‘•]Ö˜]œ“™ŠÑÐÓLÙRYÛØÕ–[ŠÚÜLÝÍŒÜØRÛÜN–––JÙQPšœÊÑÖ˜]”Ò•’ÌžØÜY›X””LÐ”\Ñ]œ››\^^YU˜M•QÛ“\‹ÓZSÓS\Ô‹ÚÙÔ““Ö˜ÜTØÒ–ÒÌL˜Z’•KÕÓ–ŠØÖ–Q[šœU’ÜY]Ü˜ÜRÝ’Ú\ÚL™Í“S]Ü•‘ŠÝQŒ]PÚÕÙ›^Z[Ô\LÛ[TÛÛY’]UÖÕ\ÐŠÚžM’œQ‘QÑœU˜RXUZTTU“S’V›ÙSš‘Ý˜Ó[MLÛÑ––ÌÓ^QØØÝ^JÎ[ÎÓTÎÜŒ\Y\œ[’[ÑQŽ\YSRÕXØÚÒ‘RÍ\LÛUTVXS[ÕÒ[ÌÓ‘MS™ÕÚÜœPÑZ[Ý[ŽMÒÓÌ\LLQPTÌ\ÛÖœ]ÚšÓÙQØYÑÙœ”^ŠÛÚ’YVVÕL^]\™ÝUÐ˜ÜU\ÑMPÜÚœšŒZÝÍÙZL›UU”Ô™ÌÓX™ÓÚTšØÒPUZYS\“\YÚ\–•›ÌÙ“žL’“ÍM\PšPÛQœ\™Q–ZšÚÓ[YN[JØYVŒXZÐÖ“QM™RœÒ’›Ö“ÚU”[ZÒ›žJÒX^V”ÚTØUÚZN›QSU›ÐXU“•X’PNZVÍ›ÔØQPÝÚRÐ”TÛÛ[ÓQMXTÑ’P•TÌYÚ^TÊØXÛSœÔPÝÔÔ•™U“RžÝ”R]RÜÞž“šSŒÛ–]ÙÍ•ÊÙ‘ŒžÒ‹ÜžÚ”Õ™ÑYž]Ó“ÔYÓX]PXÚŒMÚ[QØÐ^’›’Œ[‘ÕÑÕÖLR‘Q‘RP^ÌÛÒ]ÍÕ˜\\R•Þ‘RŽ\ÍÒÓŒÍVž\š^šÛ–Ø›Û”ŽMMQ’Œ’–‘ÔSÜQ\Õ••MšÛ‘˜JÓYZYÞQUQP]\\›YžšÜÙ™RŒš^žÌ™ZTÑ–œÔQMÊÚÕÌÌÑ]ÜÒ–•ÝZPœKÔTXTŒÒ]•SXTÞQÖšÚY•]šLÜØ˜’›ÎU]ÐŠÔœTÊÍÍPØÎUÓ‘L•]ŒŒÍÔÚ•NRÚÜÚÝÜÚQ^LÛÌÕØ™ÑÜÒ›™ÌVNX–TYÑN•ÌÜÚÖÛS\’•ŒŠÐ•‘ž•SÓ‘MËÞ™ÞŒ\›œÓMÝQYÑ]ÓPN]ÍÍ“”UÌÔÌØŒÝ’^œÍÍŽLQ“ÐS”ÚÎUM‘TØV–\ÖQTÜž’š™’JÒÞ›“^RT’›•RÍÔ”^R›]^•VMÐžYVJÙÐÖU’œÔ”YÝ]•KÌTÕšTÞ“ÌÑÛYR”ÌŽXMÌÒÞ›XÜÕÕÒ]ÖÍMØ[ÌZ‘™Ù”QÑØLËÝÝMËÛR[ZŒ˜’Ò•KÍÐØ‘NMØÞ‘^’ÝVš‘ÒQZTRÌÍ›‘ÙUËÔ[Œ\LZÕšL^‘ÛÔ]ST™]žLRÕ“”˜ÜÝ”˜š\N]”XØš››Þ›–“žÕ’PVX“S’RÍ“ÒÒ\Ö”]Ø””LÙÞPÌJÞ
ÜXÍšTÍš”–LšËËÛÊÊÕÖ™ÜšV\LT›ÙŽR›ÒÍœž˜ŒÛ\\šËÕœZ™š‹ÚÜÝ“”ÓÐ™ÓÌYÝ‹Í™Y››™ÜÓ’ÔÓ[‘ÛÙ›ÜÜœž]XŒÔÚÚÎSLÔÑÐÑ™UXÐÛ]šPÜZ[X”PÜVÜXÚšÕÝššŽQYRNRÝÕÚ\ÑÐV’”SžRÖRPÌ”R\QÚXÖšÔÚ˜MXÍÚÜ•XÒVž™ÔLÒŒ™ž[M•ÙÔÚMÙœÒYÑÚš[Q[ŒP“ÒÍ™YY\Û’ÞL‘Vž˜ÙÞLÐÍÕÐÜ”RÜÒ•ZÚœPŽÔR›žœØ]‘ÜT™RÐÒÒ•Í”P•˜ŒšRÚÕ’ØŒQ•žÚ[Í‘UUNRŠÙØÔU“ÚPMÛÐÕ\T‘ÞYÖVPÕœ“ÛŒÌÎLËÜUËÒT‹ËÓ–]Ú›R‘[œTÌVœÛ’ÑÛ™U‘RUÎ^MÒS“ÐRTSšÝÎÚ[R•U“MœžÑYš]XÌP“VÕZœØ\SÍÔUÜU•ÐÊÑ“
ÜTÚØŽËÜL^“VÜ‹Ø‘Ô™œÕÔž‘Ð–\“š[ÙÙVL“Í™Ó›ÒÜ˜ØMXÑ[RÞTÑ–]‹Ü™ØÝÑ•Í[‘ÚÔŒUÞ]•ÍUÙÑLZXQJÞNRP[[QÒXÜ”ÜQÊÚ˜™Ñ^’Ó‘^Œž‘ÐYMLÐÜS“ÒP‘ÍÔœÜÖ[QSÚRÜPÜLÙÐ“ÌÕ‘•YÒ]
Þ•ZÐÐÕL™ÙÕ“Y™ÊÙÒØÌœ‘ÚÑLÔÚÔÐÓÑÝ‹Û[ÞžUŒÖRQÔ‘MPSX•U˜ÐÓVNLžŒPP\ÍYÝÕšPN[ŽÑ“
Ô–YZS^RÜ^RYÎMR]\L‘ÕÐVŒS›JÞ]’ÖÒRRšÙÓÛ[RÊÛ’YÐÛQUÌ›^\^L^ž›VN\™–[]‘˜Ô‘Þ›šYÙ––MÑYŠÙÒ[”Z\ÐÛ•›LŽKÔÛÑ\‘ŽÒP›KÙÎšÐÍ“TÕšÍQ˜QÔŽœŽ™KÓRŽS\”UÒÍÛXL™M[ÊÞ^YÑÍ˜\œ’Ü[Z•YSŒ•Ü˜™ÕP]œPÓ›“]MMÓ••Y”ÚNTÞ˜Ìœ‘[‘NÕÕ“Ý’””YÛQ‘\ÓQœÓ”SÑ[XŒPœ•PLMUZL‘L\ÎRÒÞ›Ý”LZN•U›ÔŒÒŽ]Í\ÒM–U\VZÚYœŽU‘ŒYÒ‹ÒÍŠÔ››Y\KÙ^MœM[VUŒÒ^›ÕšL“ËÌœÖ–›ÒZKÐÛÙM•P“Ì–UØ–ÙQ]NUTSÌÒT’TØ^“™[ÝÌ’’™SÔÍš›”‘ÞÞQ–‘ÝR]Q^ŒYÛœQ››œÙÍV•ØÓÙŠÓPY™”ÓÍZÛ”ÚÐŒÒSZ]Z[ÙÌ’ULÛ›Ì”™ŠÐÝÕ’Í\›ÜÚ™[Õ]ÒÙQ[ØÊÓQÒVPÑ“[KÕÒÊÙÌÔÔŒMÜ[ÔLšXÙÒšžÐÞS\›ŒÞ]–‘“‘˜ÙZÐÛÖVXšÑ›Í™ÕÌZ••Þ“TÑÓL›Ì›\ZšMÒP™ZÙÒÚ^”
ÓÚTÍŽN[U]’VŒTØœ™‘ÛY˜ZY™ÜU”Ñ–S]’Ý’T•ŒRLQ”“Ù“•LT™LX•ÔÍURYÎUÜTU™ÜÌ^ÍXÊÊÖUT™]Þ”‘Ð›\V’‘Þ^Q–X[TZVž”YÌÚ”ÎJÌ]XŒTÓÚMVUZÞ”[^X’NYNPÓ”Ñ]ŒÖ]X\[ÌŒ“˜’ZÔV[ÍØRVŒš]\ÕÓÔÐ•X’]ZZœ’Ì\”Ð“ÚÙ’M[NÍÒž–”UQÐÙUÑY˜Ò’ÓÎV‘Ø[]\Û’Ó^^R”ÌÙVQžYÍœÞPÔ^VZRšZÙÍ‹Í]™™SÜÝÔ’ØU\TÛ•™”QÌ
ÑS\’˜ÕTÒ•]ÔÝT“\]Õ™“”ÙÑ››•
ÙÖÚ”•[ÑÝŒÓTJÒœ[]˜ÕØPÛÍÛP™ÌRÛ’ÚRŒÛÖ“ÝÛZRÌŽÝ\\Ì›[U›ÎÕÍMÝ”[ÕUŽ
ÔÙ““Þ›ÜÍÍL™^Q^œÚPžSžYÌ•\ÖVXÔM“]\S‘™Î“UM“ÙY’Û›LÜÌS•[ÚS›ÔÔPÌ[
ÊÓVÎØÒÕÓM
Ò’TNÔØ™ÝTPÒ–‹ÜÓÛÕ]™ØÝ›–ZYÜØ’Ì’ÝšUÐKÌMVYšZ“ZJÛÛØÕŒV›ÒÛšXTPTÑT›’NNJÓÝKÐÌYJÚšŒ›Ó‘Ó‘Ô’T]’^L‘U•[˜ÓÝÖ”[šUÐUŒœPMšÜ›Þ™SÝÐTÚÙËÌNN[RŒÔÞ–ZVŒ›[™ÚŒ›Ò‘œSMÕ\ŽVÍ][ÖÛÑÑŒ™–[–PÔZ˜^PÚQ›LÑÝ^SÓSÛUX\RM‘ŽV”Ù‹ÚœLVÕY”Y›YPÕÛXŒœUÜLTSQLÐ›NÙœ˜M–S[”^T›Ò–TT”ÔS“Q^”™–’”ÝŽ™ÎT\›Öš”Ì›Õš˜S“R•ÛLŒQÔ›TZÝÞS•\ÙTØTV••LP™ÌÕÖ™•ÒžSÓSÕSM•[LKÌY›‘ØÔ’NVœRPÌÍ]ŠÛSÜUYŽÝV“”˜ÑSMÙÒZZJÐ]‘Ø™ÝMœZÙÒM”N\œNÕ˜ÒZÐšSVL›Q’ÎT\šŒ”Ñ]›”“ÛÛPSÙTÌÒŠËÜØSŒœM”‘ŠÞ[ŒÚžÓY\ÒÔÙ•STR[Y\Ù]QÍV˜ŒTTSLÐV\YTPRUÝ]SP•ËÑPYÞYÔYNM–ŒÖ[ÛÖPZZÌ\ÐÝRÚžžÕR›MŒÖÞœVLÚY]‹ÒÛ’“”ÖNÍ•Z‹Ô“Œ\•ŒTÚYŒÔÍZZT]˜Y••ÕÍXÜ[[\•˜Ž]YÍ–YZP–UÙLÝšÜMY–\Þ™ÜÌÕÖ]Þ\R”ØÐ”ŒÑ•”UœÍ‘ÕR^˜ÞY”Õ•UM\ZP‘UJÝÍ™œMœ‘ÜR’’X“Õ[ŒÍœQ]ÓLV’Zž\Y‘QVÓQ›‘Û\M\žZÖœÖXRÍœÖLœ“ÖÛS[–‘ÚÕJÞÊÒÙQÚšÒ“LPŒÚÝÜÞ[ÔU’ž–ŽMXÚØ’ÚÍTÌÕY–”QUR•ÐœÔ›ÙÝÔNJÜ[Ö\]Ö™ÝÕŠÜY–“Õ\Í\ÚËÌÙ’’˜›‘Ó‘’ÐØMMRTR[^T–™•TÜž•“Z’Ó”M^”˜Ù“–\[Ñžœ˜œ˜^LTÐÐXRŒÕ•PPÙ
ÙJÒÑŒP\QŒMÌZÚÞžTNLÐÚÔ”•ÑŒLP\[ÍZ[ØÖ™œM]ÛÜRÍR“L^•ÌŒ^TÐÝÙ”–KÛÍÛU–ÐZšÌÕTÜ]šÕšLŒ“RKÖ’ÑJÜ“XYQR˜˜M[Í]‘Ü’ÞœÚMÚ™ÜYÜÛ”•Ô“S›Þš]ÌLÚXMÓÕÚX’[\P”œ–\‘ÙÞ›ÎRÌYX]‘TQ–ŽVJËÝœ™Ø˜Û‘”ÜšÛÒÑžTÖPž]˜‘Î–”Ó^‘šÒ™™ÞšQÍÐÓÍœØYÝÞZ–‘Õ”ÜPŒ[˜RSRÚZÜ’•TÍP˜šJØVLPZ”\›ÊÛ‘S[“ÐZ™ÖZ\Zš[ËÎR•Þš\Î
Ù’LÕÒZ•””S’ÝÚZM•
ÕÍÕ“Ú•Y\•[TÓ›^™ÓQÙZÌšÍ]]M\Z•TLÓ™œÎKÒØšÞÐ‘“–™ÐPS’ÕLÝ“Û
ÍM“RL•ÑMZÛZ]SÑÍS[Z˜[Ð[[ÌŒ“ÙÌ\ZÖLRÓ“ÕSž›Yš“UÊØQQÛQ•Ô™JÞ^ÚŽQÌŒ‘šÚ\[Þ–[ÙLÚR”’TÖœ[™•ÛËÝ™ÛRUØŒ™RVSœÑÑœÞ]•^[›ÞÌÒžœÙÚ\ÒÐØ™ÑXUUÜY
ÕRÙÜXÖ•LQQÖNÕØÙX™Ð•YÍUÝÖZÔÙÛR•ÛÜQÍÞ•Ú[•Ð”[ÖLÒ\‘Î^‘•“Ñ”ÝÒš]Õ‘Z›^L]QPœÝTÝš”ÙRÙÚ^\›ÛœÍžUJÙ[ÝÎ[KÎ]Þ›ŒÛžŽLÍÖËØSÜšÔ^XÔÙŒ˜JËÓZSžY›QRÖS‘ÑØÙ\V”•ÍÐšÙÒ˜LQÖ”ÓPÜUŒ”UÜUTRR”U–œQVœRSØÜLÔÞ’ÜÝÜÖ›•ÜŒ\˜ÙÚRÛXÜÜUVšÑ\ÝŒš[ÞœZÑ™V™ÜVÒž“ÝÝÓÕ[QQÓ’UÓÜ[RÝœ\’ÝMž”žRÖZSPÜTÌžQ˜›ZÕLQP•TÞ‘ÑQ]VLœZšXÝÛÕÓØŠÌÑ\œ›]ÎXZRP›ÓRØÕÒYŒÝÞÝÓU[Þ‘šÒU‘SšÛ™Nœ–Í”ZÜÞSRÌÕÙ›TSÒ›LÌÍÐMÚÝÐ•ËÝœ“”ÓÝÑÕ–šMÌ[Ú”Ñ
ÞZ”ÌZœ™ÚÕÌÔQÚÕž”’VšÛÕQÑÕT™ÍÒ\ÒÎÜÝ™•LYP‘žœRPœÖT’S[\”ÚžX”V\ÑÍÌUSÓÛQÕ‘’TšžÝ\TÛ‘]–‘\•Íœ–JÑMUZØÎVÜÞŠÓV“œšŠÓ›R˜•ZÝÞV“
Ñ›[ÜŒž’Q“U™PŒRÓPÕNRÍTKÓŒTÓT\ÓY–
ÕSÓÍÜ’ÝÕ™ÜÝÓÜŒUÔNX[Ó[Ú›œËÜÚQŒÕV
ÍÌKÎ™›•SÍÒ]ØPÚžÛÓQÕœVšÕÌœÌ”TTÓ‘žÓRVZŒURL[•ÚÚÖLÑLÝÕ›]SÓQ]™ž\’Öœ’’’ÓÐQÌP›X‘’\ÙÞZXÑ]PÒÜU‘\UÍÚ‘’L‘ÎŒŒ”NUœXÜÕ‹ÜMSTØÜSMMÛ^šL’QÎUQRŒÒ“M‘LÎÔ”ŒŒÒÎZLÕŒ™
ÝÙVQZX\]ÜQUÝ•˜–RQPQ\Õ••YRœÌ‘ÐÒšQÑÌ‹ÖTÍYš‘L›ÞV–œ\ÔL•UU^S”Œ–’[ÔÒ‘ŽSMÖÛ“šUÔÐ“MÙÖN[ÎVY‘\YÕT™œÛ•NRÜÛ]žXQT[RQ–›LUÓLÒÜŠÍ‘™Ü™UÍULÚ’MÜ[YVT[Ó’›•ÚMTZÍ”ZÖŒ[ÓLÜÝRZ]Ý]’Í\ÙÕÛŒ’‘M’’”Ržš•šJÍT’™Þ’P^’ž’œ^MÒÖÌÙY[ÑNL[Ô‹Ü‘PšÖ•Ì^Ð˜QZ’ÛÝ[˜“[ØÒ^ÚÙY^™YQ[
ÜMÒTZÜÜS™V“XœÐ–™Þ^MÐQÌœŽÕ‘[S˜ÐÕ]MÚLZS•YÝÚNY–™ØZ‘T™^XRÖ“‘ÓÕÕ’ÙQ]R‘’ÒUÍÒXTRRÙÌÝÓNNÖÎZÜ
Ø]L”™XÜÓÝQXS™UÜ[•ÛRÓÒÚ™”œU•ŒÓ•ŒÑ’“]JÛ›Z\ÑÎM“^X›’ZZ–˜^‘QËÑœÓV]ÓÓÙQŽZX™“ŒJÓÖ\U[™Ò[“Z\™›ŒÞ™šœ\ŒP›QTÍÌŒ[Ñ–ÕÑ”ÒÕRÛÕÔ™ÍXRYRÎ\™S›šÒŽZ^˜QÍPÓŒMÜÔ“VYVMÕ˜ZÙYŒÓÛÐšÝ•Øœ›P™V]“›ÝÜÐÕÝNL“ÕXŒZÒZ–ÎRÑŒÑ™‹ÓX•Ö’[YÌ’ÙMY‘Ö˜^‘‹Þ“[MQŒÑ™[™ÝŒœØÖžQÔ\VÌM›VÖÖ“ÕÖPNVVRÛÎSËÎÝž›^˜Ì”ÒTR”ÍŒ“ÛÌRLYXËÕ“ÒÚY›S’VL”UUÝšMœUÎPUÐØÚJÜSÕRÕXÝšÖžžšœX™NJÓÚT]\MØYžœ“ÔÝ˜]Õ^[YZ“ØŒ^Ö˜ZÝÜZŠÚœšÞËÑÝÔ•\XSMÜTNPœY›Þ“ž]PÜPNKÒÐÍ^ŒÛXÊÎÕXš‘QÝÞ\YÒUËÝžQSÒUM[YPØQ“ÕZZ”ÑT‘[’“ZÝS^YZ™›Î^RœUQUT‘UšÙŒŒÝ•ÙZŒÞ›PÌN•”Ö’Ú]•N”ÛØUÑÎXŒËÑØŒÚÍ˜^L”˜Q]Ò”Ñ“™PÕÜ^“SÝÚŒTŽØÚ“^QYÍœL›˜ÚMÞ˜ÚÌ[™[ÕXSTÛSÑYSÙÑŒ‘TÒÔ[‘•T˜]]\‘”Ý[‘Ù“’ÞÚÍÙUX“”ÔÒš”šÚ\Z]TLÖL›TÌÜÌ“LÙÒ‘YÕ“ËÍØÎ^žŒ\YUÎ^V›RYZ
ÝSMÚÙPU‘ØŠÜ\U“Ú”\ÍÕZTÎRY
ÚTQÛÍÒÚÎÑÝÞ˜ÌÊÚÓŒÕš•Û]Ý›ÊÚÎ[Q^VšMXžM”T˜[‘ÌRšÌ\TLRÛL›LLŒLÖM™V\ÑMUÒÝÜ\Y”ÕœJÙ[]™‘Í[SÝMÐZZ–[LUÒŽ–[ÛÓ˜L™SÑZÜ•žKÚ][ÍŽÍÝœ[žÔÍœ™“QÔXØ™XÙ\“™ÛÍÚŒ‘[˜T–•ÜMÙÝšR™[XÙœ˜R\™•ÑPÙÔÓ^’QÝM^“Q[RUXÐÜÔ’Ø[Î“Í“›Õ’ÔXZÚTN[SÍÑŒÙÑ™™TÍ“ÝTQÚÑž“ÚP’ÙØÊÌž•ÎU•Þ”ËÒTÐ\YŒ›ŒØÙS]ØÔPYSN]ÖSS“•Î’ÐÓZÜš•˜•”Þ\QŒÕÔ’V^QÞV’LXÕÓÜ“Œ›Õ•VLMš’“‘ÝÓPÍÒRPžXNNSÒ^ZÒÕœQ“šÐ–V–\Û•M‘^˜ÖVN^UÑ^–•š•QZ\”ÕZžYPÓNV‹ÎR]V–[•™[’ÙšÓ’˜ÝššÓ^ÕÌ[žR”T”ÍYMœ’L‘P‘•XÑÕ›ÑÝ”ÔÒ‹Ò“ŒLQQQRZÓ”RU•Ì
Ô™ÌÛÌŒRÛTR•“”ÍÖS••[’•’œÖ™Ó”Ñ‘VVÚ
ÛÛÎXT˜\SNV‘ÑU’TÜ]Òœš˜Û”’šMYÙ^RRRÛÕÖ•˜ÑÌ’“ÝÍÙÞQÌÌžL[UËÝž[UÍV•Ñ”ŒPTKÎ™Œ”Î\]˜™ÔÜÍÑÒUÖXPÙ]Q]MSXŒÍÜ”“’Õ™Ù\Î“ÖQÒXÍÜ[
Ø›ŒÚŒÕ”˜LPØ›S›‘ÙØ‘]\P–ÚSXVT™\Ð˜QY’Þ˜™VN[]MÙÚÝ]Ó’ÜÝÑÕÚ›Ö˜–YÝRTÜ–”ÓÓUUŽÒÓ›MÝ˜“ŽYÑ‘X›PÚÞ“ZSÕÞ“Œ•ÐMUÜÍØ“ÌTÌ[MÚÒÜ]•ÜÕËÛÌ]^ÚZÔÛ‘ÜV˜ÛÕœJÊÛÜ[V\ÕP[S“ÝTZÖÎTÐ’š[Û’^ÛUØÍž‘‘›œ\’UÑ•šÙVL”ÖS”Ò[ÚMÌ””RšMXT]›•Ð\Ì]S‘’[ÞÔÔ›œ‘
Ñ”R^P’RØÛQS\ÔMTÎ[š‘ŒÑÑÌYÙSÍÓ˜Û‘ÕœSSZÒQžŠÙÑ›Ø‘™’›\[Lž“Ü™S”VžPØ“U[’ZÞV›“ÚÕÒKÜœÎ\Z˜›Ì‘ÑšÚ•R]QÐÛÚXÔQž•”Q^ÔZTÎPÛ’’Y\\\]P™XÖU‘Û‘L]ÍSÌžÐM
Ö\\ŠÐYM™ÚPÛ‘Ö‘’ÜXÓžÙ›RÖŽ^ž]Þ[ÎXVLÜ“ÝJÜN–\ÞŒ–›”QŒ’V”™•Ì™ÓÞUUÑŠÐP•S“\PÌ\šÞUšKÔ›]ÜJÛÒZž\ÙTZ”Ì]X[˜ÛÌ‘V\ÓØ\‘SQÜ]›UTÝ™’ÍšÙÑNÛXÕÎKÌ™‹ÔÔÓP’šÚÜXQÌ™™•S^NPŽ]U™ÕÑÑ[LÔËÜÍRRÕLZ‘P”–’LÑXVÕÍÞÙX“ŠÛŒÝPÕÍN^ž–Ö”ÓÍ\›ÙÕÖ‘LŒ\•M]Nš˜•ÙŽÒ›ÌÛ˜ÐÒ‘SÝMÓÚ˜YÍMLÌÚÓ–›\ZM]Y˜•]]LMÚ”ŒY™Ž\•”ÐÚÞ“R\ÓØÐ“P^QÝ‘^PšSÔÜÞ™R™•ÛÍžQœQQšÍÔ‘ÒÑVPÔJØ›ÍR’“\ÑXVÚÝÜ‹ÎÝJÎR^[XTžQÜ“Ž^Y››’ÙU\ÛÍX˜“””˜ÙJÍšÙŠÊÍ›”YÎ
Ó’RQL‘TÛV\QØŒVSšZÕ”“^“V]™œÎ]Û™–P’œ[‘ÑÑÛÓQ™ÛYÕY™ÕTQÜÒVNT‘]Ó‘SÜXÞŠÖÙ˜ÝZÒR™ÚZ”TTÚ™S]Už›QÛÔÍ“‘ÕÖÜ^Ì‘”RœXŒÔ\šTŒœ“ÐÙY›Œ’QŽ›˜ŒÞ™NKÌ•ÎZšUÔ’ÌXSVŒÎ]S\X˜ÐÓØ•V›R[YÙNÜØž™’Þ’Ì“RÝ[ÊØ––[RSšLMU\ÝÐ›ÚZÜÌL“–V]’ŒLÌLYÓÜ]Û‘Ö^–š™Z”•V•LÓT]ÓSMÎUÑÌ˜NPX•P˜Ù˜œ‘’›LÛ‘™SÛ‹ÑÙÝTÜ‹Û\\ÝšZ[ZÕT‘’YŒ˜ÖX™MÍÕMVŒ[ÕYÚÎN››T^UÌ“ÞLNRž\Tœ]ÎÌNMÍ”VÍÍJÍ]\•‹ÜÔUÔ[‘JÙQ[ÒÎLÙ]MÑ›SR[’YÝQœÞ“Ó^’QÝÞŒÎSÑÔÝLÓX”Z›TSVRÑTÜPRÞ“]ËÙÝ›ÞŽLÞ]ÔÞM“SžXÑMTÐZSM‘\ÚÙJÛœÓŒËÝY”ÓœØR™U“˜TVQÓRSÒÚÔÝSÎ[SšQÜ’ÝQÕÌSL”ÝÔÓYžUZÔØšØÚV’ÓTÔZX•ZÍ›QJÛ•RÙÙÕSÝ\Ü•ÝÖÒÐÔÒÍ–X^‹Ð“MLYÔRÕQ™ÛÜÕÌNœŒ“Ò’›[XÚQÛ–œXÔšLQÓ––RMœŒTÔ•JÜU[]•ÊÑ™ÝÚ’\ZÒRÑÓYZVVMËÞUÝÜËÚPÊÊÛ]UšžYÑTLžÊÔœÒÞRÜÐÎZ’›\ŒLÍÌXÚ[]RQ‘Í^œÕÍLÞTÓžYœÌS“ž\ÍSR\Ù“Õ\UZÜÛX”]ÝÌRÐ–Q‘ÛÑ–ÌM–]TšUÓ]YJÚSÝL–\L‘™žLÛžžÙMNZ›ZÛŽQš[ÕYRÐ‘[ZÕMXRLÐS“˜Z“ZÓPMÜ[LÙÝÚÌÑÖÝS›YRÐ›ZXËÝQ[œÍÕœMZÕÖTÓN“ÑÜÝØN–T[R“”QšÐÔS]ÑšRÙ›ÕŽR^œ˜ÖÔšÕÞ‘Ô•ÞVšÔ–L›ÓZMœŒ[PR™Ô“ÛÝÔÌŠÚÛRÞR™ÕÙTŒZ’YŽZÝ[Ô™ÌÖÞ›Øš”Î]’•˜œ]Z••VÕŒÔÑ˜^œÓYÓ–L^^š’]–UP’P˜R]•TÜ]”Vœ˜Ñ“QÑL‘ÖTÛÓXœ›ÚTÍ–Ö‘ÖT‘ZÒ•^M”›ÍÙžŒQLÚYUž[JËÔ‘ŒT^•’ÎRL\Ýž™’PŽRšžQT™ÙÚÒ]YRQYØ[]ÖY‘šVž\[•S^›ØÜZÞRÕÑ\Ñ›\Ô“ÔLSÌÑ™žQ•\“YYÔÚ˜ØZ•[•S•ÕÕ”ÐÙÕ
Õ™™š›ÍÒ^NZSÓšY[œÌœZQÖQÍŒ™ÕÍÕ’ÓØÔØ’šÔÔ›•LÑUNÜKÔKÙ“ÔR‹ÒÍš‘ZÔY’Ó•\TÐÖYUÛ›•^UQYÚMÚ\™[TÔYÔÌ’ÛVŒ•UUŒ›\LÌ•ÐØRœÞRÒR[ÑÑÔÝ›ÚšUÛYœ‘[Ò]Þ•[›šLÙ™ÖQQŒ›ÝÔ\ÝXM^‘SÌÍØJÐœQÜ“ÌÕ–TÕŽžYÒÍ
Ø”žšÞÑÝYPÙ––T\ÜŒÎP’™‘ÐšÚšLVŽŠÌÌ”’ZžTPšV”œMØžLXÔÕ™ÐÝR˜ÓÞVËÎ•\^JÞš‘LÑÔJÖPÍY\ÑZSÝ\‘˜ŽSV[JÔ•”ž‘ÙY•–ŒÐ˜™ŒQ”˜–›Û•Ý•ULRÍÎPÌÒ›TØZUUÕ‘\PÑÚÙ•\[QÛ\KÍ™ÝËÙÊÎMNSÛŒ]ÌÕÙ\œœU[ÍÜ\šLQœQ˜ÙÛÌ“ÙM™UZœ–šœQÕ\LËÒš[YÍUÑŽLJØU]™œÑÞžQž[S‘\[TMÚÞ]L”LY–^–“Œ˜QŒR™V’’™ÝYYZZLÌ[˜ÔMÌÖ“œ‘TUžLšVÐ]ÕÚ’YœŽPZU“Ø‹Ý[UŒN^T•ÞTØPP’ÞšS›Þ”X™ÌÜÍPØ›•–’ÛÕ\’ZÝR]ÕšQ]\ÔÓ›ŒQRšÓÛVXPšÔÕ‹ÍŽTÌÜ’X•ÞVÔ‘ÐšÍZÌ’ÒžÓM˜ÓÖ”œ•KÍÜŒÍÚJÞMŠÓRÑŒž[\”Q“SÜ\ÓL\Ò–œU›ÓÌUÜÔž“ÙÕ’KÌŽÛ]Œ•QÍSQ^žŒLÛS›N”Ì–SÝZUY\LÑÚŒRÞœ”RÔ™œÔ“˜”™ÖÕV’
ÜZ[Û‘‘“[PÛV‘PLÚÙ›”Þ”Œ’]JÙ™\˜^LËÜTÍÚšÚÝÔR›ŽTÍSÐÙ”NZÖ
ØÙÔÎ‘Xš›ÔÌQÒ›]]›˜ZRÛÊÞžRYÐž›M”ÑÖTÍ•›NZœÌZ–SV–TšœÞ“”ÙSŒØÕ˜ÔÕMŒ’Ò’‹ÍÝZZš•]œV˜XQØžRZV]QZSÊØŽ‘U^•˜\’ÊÚXÞQÙÐÜŒÍ[›Û’PU”ŒP\“TXÌ‘[ÒÛPÌ‘“‘XÓšM‘[Ì•VÙÓ^‹ÌSÓÙÌMZ™PÒÝ•ÌØ^NYž”M›”QÓ]Ø[ZÕÛœŒÕœÒ›žLNKÍËÌS]MÓXžQ]Ñ™ÑÍRR”P“YLMUÍLUYVÑÊÍ–MÚÚÒ”S•ŽÚœÜP”UPŒ›ÓÌÙÒPšÖPÙÜÓŠÔV\‘U’“RP–‘^MSÐPZžžSPŠÍÒÙ™šÔYšÚÕYšÍÐ›\Ñ]Û[ÙR›XS˜YÞ\ÝÍ^•‘œU]LžSÍ\Q‹ÐÒVT”YSVšTVR™L“ÜŽVTTV”QÓ™ÒšLP\UÐÒ“’Ó™“˜ZRÚ“XÛQ[SÜÓœXÌœ˜RÔÖÑYV”Í\”QÓŽ]Z˜”’L’’‘ÑËÔ›˜ÐM“Ù™[ÛŽLYÒ‘RÛQ\•Ý[’ž”›
Í^YV•ÍÝœÙX•”YÙ\QQÚTÓš“Î›ŒKÎÝ™ÝÑSYÌTŠÙÛÝ‘”Ù”“™PÝSÕÞLÛÚMÝZ”•XM\ÙÎTš˜XÓ
ÙYÚØ”LÌÜÔ”‘“ÐSP\]ÞÚÞUŒY‹Ð\ÚPÚ˜Œ[[^STMŽšYP•š”Ž]ž]ZPšÙZ^Œ‘•ÐÝŽÎV
Ú[NÞ–RT’šJÕVRÔÚ•’ÔÍ[Y™œ–YÌYØŽP–QN\Ì•Ì[ŠÔLNÑ–SÝÐXY™Û
ÕÕ•ÞUÛ^ŽLQ^JÎ]ULLJÎPÔ“\’Œ“QÓÛR›ÜLÑ[Í[ÓSRžÚSYžU™QžÛ]S[ÝÝÍQZQÞÜÓÍ•–SX‘ØÑ“ZÍSP–Ý›ÌTÛÍ™žÔÛÙ”TÓL‘ÔÌ”–YZÌTÌ]ÛÓÖ\Y–ÓÜÔVY‹Ð[Ô‘SX”ÛZÔ\Q•\–[VQZÒÞ\\•Ò‘Ú”LšM–œKÞšÔÞ[‘Ó™ÔÚ”SÓÔL’ËÊÌŠÊÛÖ›ÙV•\X]ÛÐSÍÚ“ÌS””“^NSÙ“‹ÜV[LÛšÚ”NZ”Í‹Ú’Üœ“Õ^MS\ž\ËÔœ“P“NVYÌ]U˜Ú’Þ™ÕQ‘ÊÞZÝÛ˜[ÒU™œÒ˜QVLZÓœXÔ™S˜ÖÓÌÍÌÚÓÑÛLÛÜ\MQ•–Ù]QÜÐÚMÞ›ZY”ÖÎÔœ‘QYÌÐUYU[ÑP’œŒ’ÓÒ”P]\•\Ú›ÞMŒÑ–‹ÛÑ•\ÚYRÕV[Û•–”TSŠÒQÐ’ÍVP\žP‘QY‘žQV[XÐÖ›ÎR’ÑÓØ›^
Íš›\ÝžÓN^šÑP”ÔL™ÙLUUÞÒRT[^^’ØÚÜžœÖÐ•ËÛPÑUÐÕSTÕSS›QJÜXRÒTÔœÞR™RÌLÑ””Ñ”TÌÞœ]“ÍÖ’Îš[MÞ“ŒZ˜ZY•–œ“Ô›TMÌ‹ÔRœ™YÕŒJÝXÌNPŒÐ[ÜRÔMÖ]Ý–žPZœMÛÌ[–V[P›ŒÌ‘œ™’ÕLPQœœ–‘P]ÐN]–ŒŒÓŽNÎÌÍŽÍ]^–’UÞš•^^”ÛYVÒ›[šQŒ[V”Û›ŠÙšÎÞT\•Ñ’Î“•U•^YÓ––S›ÎÖ›Y^›žVZ]ÌPžXŽ‘YRXVŒÕPR™ÓžŽMR‘ØLÙžYSÍÓPØœŽMÑ”QœNLÌ^ÊÛ[Ü›™ÚYÚ“[“Nœ–ÌŒÚT”Ó‘L\S•P””žŒ‘Œ\NUÒÚÌÍLÓšŒZ›Ú]ÚZSÝÓSV”’ËËÑRÍÝÐŒ•TT^UÒÙÑP’•ŽŒSYMÜM]™YLLÙ˜ÎÍ^UTZÙ‘U‘Ú”Ð”ÜšZŒ–LYÞUŒÙTVÛÛÑ‘ÍÕ\ÚÛPŽŽÛ“MLMœž™Ú]ÔZÖÔSÖœ”Õ›Ò\ÍVY‘JÕSÕ”‘LQÌÔÓ“Ì[
ÔÓÔÓÝœÐ›RQ›ÍŒJÒÛ“^“[V‘ÐÑ””ÚŒËÙŒ•ÌŽNTÜÍ\ÔœÍÙ“ÛÞ’ÌŽŽZQŒÖ^ÛUUÜZRQLÝÍÌÐÒZØ]‘ÌÑ^YMTTÒ\•Ö˜L›œÌYÛS\ÛÔ‘M“Q•XÒKÚU]]Z^›ØYYÜXUžÍPÔÓÍ[LYÙ”ÚÒ•SL™ÕÝÓMMÔ“ÔÞQÙYÎZ˜ÚTÍXœ”S”ÜÙMÝÚœVœQUšŒÓŽØZ‹ÒÓ[T™ÖPœ]ÑÑÒ™‘ÑV
ØÌÌÖŒËÞLNM“USPžSÍÔÒÝY›Ô“ZÛ•Ú™SÚÙXLR–”ÍU]V˜\YÜŽJÔž[ÞUÐPÑPUšP›ÑZ[’ÑJÔ
ÊÌÑÙ™“PKÓ]Þš]žLžZÚVQQTÖTÛØMÌØRSš›Ü’Y‘NQÑÔQU›ŒRÑ\NœUÖMÌœYšSÖÙ^\ÓP–Ð^JÛÍÍY˜’Ø’]ÞM[Ú›P™Ø\QÍQYÞ\ZLP‘]]ššÕÙÕÙÝØšÑÖ“ÐRÕÝR\Y]]ŽM^‘ÚÑÛÓZÐZ^]\L–œTœÕšÕLY™ÕKÙSRŒ™žZ•‘ÝÑ‹ÙÍÕÜ]œ^]•‘ŒUMY“Ô\ÎJÔ”L›Ó[Ð\”œÛÖ˜ž™Ø[žžž–Ñ[‘]™‘RSLYSœ]MÐÍPÔÑÙPÔUJÐ”ÑÜSÞŒÞŽLUÜÓVN]ÌŒQŒSÛ\VŠÑÛRÓ˜œQÕÝ\ÐÙRÞRÖP•ÚÔÞŒÙÜLŽÕÓV[Q[Ì’ÌšÑVÔ’ÞTØÞšÎ]ÐÒÙÔ’ÍV\ÍšU˜ÚZ™ÙÔZÔÕR’ÝÞ“›Œ’ŒÞ›ž–˜šMÐTžU“[Qœ“[XUœ™\Ú”YUYž^˜ÞQRMUXÍÐ˜žYPX[ÛÛ™“–S”Ù•””ÕÛÒZÖÚÍ–ÓÖ‘]Ú”š•šL˜UÑÒSËÒUÐÒXM•ÚÛZZQ–ÚZ“œÒÌL\V‘ÛPÔŽP]ÚÙÞXšÖÞ[ž[Mœ’Ü[ÙÓ]Œ”ÚÝŠÑ[M“SËÕMÓ]ÑÖLÓÚP‘SÒžÍQ]RNNRUYÒžRZT’›ŽQØÜœ™UÝLTLÞ^ŠÙR^’ÛÛÔÎÛ”TÒ]X”Û“TÕØ^V‹Ñ]VÙÚ”[ØÕ•VÍ“ÕÝÌM\ÞËÒÖš
ÊÍ”VPšØ[VMVMÜYÜ\™YLÕšÑÝ™[\ÍŒÕÑÑ‘ŒSÎ\›œœ›”ÍÖ]ØLÕ\Y•Œ[‘LL™ÔÌÒÑ•ØZÐ[P™X[’˜“ÕPÌVŽÕLP˜LPTÖYÝ]M”X–PÜURTÞÚÝPÝ•ÒØLLÒÝÓš’ÖSÙS\U˜Ò[XœYÔVRU•ÝSU™ØŒ”ÙŒÝŽ“Ö˜ÖÎ[ÜÍ›’•\ŒÚ[LÚXØ\ZÑÌYPÛV]˜ÙŠÕ[[Ò”™ÜžT–PŒÛ™VTÙ[ÒÐLZZ–”ÓŒÜXUPÖ“’Î›Ò^SRÌÚÒ”UÜR[ÓÑVY[RÖZ™Ó™ŠÓžVÐ›Ñ›•ÛZQSSšÕÌ’–TLX˜œÝ”N”Sš˜\KÜ’’œN\”ÓÛÖÔ™YØÛØ’Ú™ÍÓJÖÌSÒÛ˜ÊÍÍÔSNØÓÚ]Ú”X–YUXÓLÌÔ\™QLÌÙ\]Ø’ž“ÝXÕXLÜÍS^YÕÕYÜ[]’V\^UVR’ZRÓ˜ÝÚ•UÛÔÚÒœÜMØÝ[“[•ÎMËÙUL›’Û‘YR]“ÚÑ”]ÚÜÑÓš›ÌšÜ”ZÓUÛÊÓYUZSÍÑ“ÕL“•Í^“‘ØÔÛ’MÖÛUŽXÍ
ØËÜLLÝ™T”Œ
Ýž’SšMÜZÔÙÙUÒÓ“ÕZšÙ‹ØNKÎŠÙ\˜œ”RšÜ’[–RUQÞ‹Þ‘QšYÑ›ÚSÝVPV–L’U–\–[Ú^’SQ–‘ÝÕ‘˜ÝTÌØÑœ™MTØYŠÑÕÐPÜLÝÔ›ÕZÐVÚ“ÌÔÜJÞÕ™ÛQÜÖ›ŠÝÓšUžÓÚVLÕ[ÕM•X“˜T›ÍÔXš‘UÊÒÌžœ–ZÝ‘^S\ÛV[VXUÐJÔU˜JÎÖYKËÍ]™œ]X˜X“’’•ÔÌSQÌÜÌUÒQ^JÎ‘’‘ÞYšÔ“]\S‘Þ[Û“ÒÓÚÐ^š‘“NÚPÛÔžT\˜LÖšTÕ[ÌÚ^L^ž”œ^’‹ÝQÔ–NÜXÛKÛRR^“ÔVLÒTÓŽ[Ñ^JÛÜÙœÌJÚšÎ•Ó]ÎV\Þ˜RMÔËÓY›YV˜œÚšLYÔP^UÔÙÛ›]PÕXÞ’ŠÞ–^“MÜ›ÝŽSÍÜŽ\’•]ÚLÚ’]ZUTMšNVšÐ‘–œÜœ’ÕRŠÎYœ”ÎZŒLÌËÜLSÊÌšÞ“XÖ”š‹ÓœXQLXÑØ™šœ˜žŒRÑÙÔ•LÕÐŒ]SXÞ‘ÖLTÓÊÓQÐ•ŠÑ“‘ÎJÔÞ™[Í’ÙÕÐPÒ›ÌQØUŒ‘QLŽ‹Ù™™ÝÙ]ÎÍÑÒÙ–SL]UL\Q]PSY•“RÚœKÚÓRSQNMÐZÙ\Q]ÝXTÚL’™ÑÔXÐŽJÓšRœÜZš\™S’ÓMSÖVŒÙ“ÕTÑÖ”Ü’”Ù“Q“LÛÕ˜’ØT™ÙV›\Q^š™ÑÞ^^U“ÛXZžÑÌ›S›”›’ÓžRV˜\’ÛÙM\ÙÕÕ™”‘’Ó™•[•”Ò”U™žVR]Ö’ÞÝ“[›Õ’ÓÜ‘Î\Ú[ZV]ÌU\“Ì™[‘MÎT•ŠÔKËÜÑ[ÍQÍÝY˜–^ÙÒ\Uš“L›ÜÒUZÕUš]PŠÞ\ÍZ•ÌÜœZRP’™Þ\^XšÓ\‹ÜÖ›Ž“]ZÎRÜ“NQÍ’œ‘\L”šÒØš›ØU•›Ü“R™U–]R]›YÝÞUšÛ–ÖUÒÛÑ]Üœ“ÝPRZÛš[M‘Z\‘RÛ‘ÑQÙÐRVŒœÌŒÓ–LM”Ì[ÝÜN[“Ì˜L”’ÜÙYÎ^ÚØ‘ÐRRšÑUÞœÜ”žVŠÓÙËÝM\Ó“\\ZÔÞÍ•Q”–’Y•ÑÓ˜ÓJÑÎY’œ™™PKÌÚÖšÛ[ÔÞXÔÕÕ’ÔÒÝ^ÌRUUQŠÖÛÔ”ÓL’Ó–U““LÔS•”™ÜœÍPÌUS•ËÌ’]SL›ØÍÞÍLÑÝLX›ÚØÛRRÊÛZÌœ›PœLKÕÑMš‘]ÙÑ˜UQŠÑ’]šRÑLÕÓœÐÚQLP˜šÙX‘TV’TMM[ÒÌZÌUÊÑ‘ÞQZÛÜ™”V“ÜSÐÕ]Ì
ÑÒ˜ZÓ›‘ZV˜S–^Þ•ŒR[“SÜÜKÓÞ[ÖPZ^RQÕ“[V“YÐLŽJÐÚMR›šÔÜÞ’Ú“T[ZMU
Ô“ÝV[UÔ\[ØÖR•ÌÖZ[ÔšÌJÝ’SVœžQ•Z›ÜÒÕ’[ÑÖ‘ÔMÐÚQŒP˜\›NZMZ]QœŒQZR“œÊÔSZVš^šËÊÚÓ™SXLXÝV^ÓžRÜšJÍ“›ÔœYSQR•UÐÔTÚYÎšPU]’X›ÓÖMÑÍ]ÐŒ‹ØŒÔÚÝ›]Õ‘\Œš–ØÑ[‘Zš•L‹ÛÐ^QPÕZÌ’QÌKÒÔÖM˜Ø]UQ™SÔPÜ]NLZRT˜Ð‘ÙRYÝ^UÞ•Q˜U™TQ–™QQMYÞ“ËÝSÛ–LVŒPÔØÞØM]Ö’–^‘•œ‘]“NUUÛÕÒÞZZÛSKÐ’R–Œ›Ü“œLÓLÓœZÐÎY“ÑÒ˜Þ•›MÒŒU”œ‘˜ÒÖYY\JÖžLÛYÓžUÐX’]ÞŒ‘ØšÐ•R’‘‘Ž\[MYÛ™MÞ™ËÍ\‘XUTØP’‘ÌRVRÒ\“Vš–JÎNL™]šZ™‘ÙÞÒÜŒ›“ÙUÍÐ•Ü^žÎÐ•P[YœÔJÚ“ÍPÍÞ[ÌNQÜ‘ÎRœÖ‘Ð‘QMÓVQYÊÔÑNM–]Y”Ú[›Ü^S‘•ÐÕR”˜^Ú]\”ÝÙÕM•ŒŽ‘UJÚ[MžÞ’‘ØÐ–R‹ÔUYš”UÚÛ›Õ›ÝSLÞÍ”ÕKÍPV“\•›Ø‘•Z’“œM^›šS”R•X‘[Þ]“•
ÜXÔ•XTÐV\ÑÔÛÍ•ØMNSÓRšV‘’–RÕØ›š‘LÒÍ‹ÕMÍËËÒ^ŠÝÒ]ÛY\U™›”^]^‘ŠÙ
ÎZN˜VXŒ[Î
ÜÜ“Þ“]Þ“T‘TœRšÒZÚ–TJÔMM™QY“XRÚ›••VœP\Ý^ÞÚÙST‘[ÚšZZ’XÔÓÖ›ÔØ˜ÚÊÓŠÌŒ™ÜMÌÜØž\ÓÙLSœÜXR”KÞÛÛÓTÙNUTQŒUšZVQ]Õ^L›Ô\Ñ^[˜ËÚ–“^”ÌÑL^ZÔÒÐLÐÜžTÚ•ZNNR›ÝÚ^RÎYZUKÐYÛ^VX˜VMNLœÑRYMÍKØNLÖP›M”˜’[•R^›ÌÙTQÛÐ•VRÔZÞSQ›ÐŽ•[^”Ìš‘”]]]•MV“ÛŒNQÕÎZÖM›TËÖ•]‘™ÕÌ•š\ÌLUÜœ]•™UUÔRNL“‹ÎYXÌÊÌÛ˜Û[ØÑŽXUž’ŒÛÕÖMœÚÓÒKÞšÞLÙŠÜ
ÊÍœÙ™™QŒÒÖQ‘’šÕØÊÒÔÖ’ÑLU›ÒVÍÌ^•ÕUUÓÒUPKÛ“Ù][\žY”Nšž]QÕÌÍUZÚSÐÕŠÐU‘ÓÒRÐÕMŒÓYV”‹ÒÙËÕËÙ•Y™•Y–›ÐUŒPMÐ‘ØÙ]ÍÛ“Óž[˜VL•MŒ[ÌQZ™RUžÚÝÍÑÒ›šÕÒÑŠÔ™ÝÑÓS•ÝÚÞYL™ÜÕYRÒÚ››•Ó’YÜÑÕUVJÜSYV“ÑÚM[ÕœSQZÍÐ™R\’”\Ðœš\]š\œ”’V[[YÍR›–œ›ÛMÍÔ\Ö\ZZUÊÔŽžXšYMUPÌ^QŒšÜU™QÕÐLÚÌÓMÌQÖÝÖ‘’[Û”MÍÛÐÛžœÝ™ZÖÌ]MNLÓVTŠÔÓS“ÚÛ˜™NPÌÝ›œÜT\Ó˜“Ì‘ÜÑ™’Û\Y\Ø”’™XÐÌN^N–\ÛQÚ]YÜÝKÛ™Ðž‘VZP’Ú‘KÎËÙ›ÛØœ]ÊÒÕRLÒR]\Ù]œÓQšÒ]]Þ›“NQœÝ–šØV›LÙÍRÚÙZKØXŽT–”™ZL––™ÚŒÚ“•’ÖMLšSÑ˜^Ú˜›”Œ]V›Þ˜–œUÕÐÛ˜œ’ÚŒZ’Qž›ÐÑÖM’YŒÓ˜ž]]œTÍÙÕ˜Ü›RX^Ñ’ÓÛÑÌ’”L›ÙKÐ’YÛÝ•ÖYÞ’Q™ÜÚÖ]ÐÎ\VRÞLÌÍ‘M••\R–‹ÓM\Ž“ÖQXÞŒ™Ý•]^œÞØÝVRÑUÎMÎRÝÒÎV^V˜RÝÎ\Ý‘\˜ÓUÜÒ]X“P[\ÙYXTœÓT’MYÔ
Ö™™ž™’\ÜÝÞ”P››ÜV˜–MÚÍÑUPÐQØVÚ^ž“UÝÛY‘QËÒ^]L“ÑÞž”“RÊÚ›Zš\[UÚVžMÜžŽXQŠÌSÐÓ\M”V™ÓYÝRLÕ]”˜KÕ[ÞÌ–JÚÔÓY™ÕÑ™RšS˜–MMTVSÔÛÜ]YØTÑUÛRZÙÕÕ[œ‹ÍÛVÖŽZÑØÚÓ’YÛLVMU”ÒMÕÓÔÕ]ÝXØ’ÌN•Ö]‘˜šYÑËÌ]ÐLUZ\šÒÝÛÝšPM\ÔÌÖššÙ[RÍÕŽPÕ•ÍÐ•ÍÍUÍLÌSPÕV]Ú•˜MÝPœÌUÜÕÌ•UZŒœ‘ØÔÒÜUÐŠÜÌ–\ÌžN^RšÛ‘ÕVULM‹ÎX”•ÊÚ›ÙÐÛ›ÜÜMÔš“M““ØQÐ•ÞM]’V™V•]PÑÓÙMŒU›Œ•ŒSN^[™ÌQT›”‘SÌÌÞNTLQLž”–URÔKÜÐÎ–][XNŽR]QÙÞØ[Þ\Í•žœRLš‘\’LÕ•’š’Þ™ÝMKÌZLŽKÎ\Í‹Ð•ØÝM›ZÐÖÍÙYÞœŽQÌšZNÕXÐÌZÚ–ž™’Ý‘[Ø\X‘ZÚ•L[S˜Þ]YTSYÐMS“X^XMV–›ŒÖ•Í™Ü[›’’ÍZÒ‘]šÑÍÓŒZ™ÖMÌÝZ›ÝLU“žRÍÓVŒÔN\ÎËÒ˜YÞT’Þ‘UZ™šZ“Úžš[››”LÔÌÍQÝÎSXÐ’LV™Ô“Ž•[ÍP–ÜÛQÐÛLŒQUÜMRSÒÕ\ÖZ’ÒÛVQœ“LÜŒVZÓÝ›’ÒNM^•ÍÒ–˜•Z‘ŠØœÍ•–ZÖ^RËÝÜŒÚ–˜ËËÞVÜT”ÞMNÌ™SÊÜÙÕ”XÔ›ÌÝ“ÌžYžLUL”›˜TÔÌÌÑÜ
ÜM‘ÒŒ‘UVÕÚ[ØT
ÎR‘\LÙÓÌ‘V^[™–[M‹ÛUTŒÝÜS•ž”–’Ü’ÐZ‹ÌPŠÓ[^ÙRÜ”ÛÙ–ÒZ›QY›ÖšÓÚÙŠÍÍ–Ý˜\ÝÜ[ÎS^šŒÌÕM››URÞŠÐX›œÔ\[˜^ËÓÞ“R˜ZÝT’U•RÊÝMR’ÒLÛÍYÚT
ÞXÙœÜÙQ\ÜP]ÜØ]•ÒŽXžÑš•^˜XÑÞZRU˜“ÕLÐÐÔŒP›Q–V]PÞM^›X’ÝžŒÚZ\ŒÌÚÛÜÒTP““U\SL^“[L™ØÓÞÑÙ‘–•JÜZLTÌ]\ÚÛÓÛT™QÌ’UTU’‘Ü^”[š”SÖ’Œ”Œ\–[•‹ËÐŽU‹ËÜÝM[ŽœZÚØVZÖZÛÛÖÌ™X›Ó’Ô^™PÊÍÜZ\˜™V–Œ”ÎL˜ÐÌL‘’RÕ\T™M–ÝÙÑ˜™ÒœSRTÐ[RÓ‘MÚZØÙ[ÛØÙ’ÐŽPPYYTZ[’Ö“^šÑYŒ˜ØÔÝÓÜÑÑM^“‘‘“Û\ÕÍÊÚÞT•Ú•\PÑ˜”RT]^ŽPÒÐÐP^MØY˜ÒUZVY[ÓÝ›]”RÖ”ÙØ™ÝM^XQÌT›]ÝXÎ]“‘LÒÕP™œÍ[’ÑÛÚÑÐÒÕÌMQ[ŠÞ“Y“ÛÑ•ÐÒMLKÓUZÔÛXÑRÙÞÜLÔŒY’TÌÞV–Y™’YÐL”KÛ•ÚÌÙžPÔÐ’’‘ÍÍÍÝ›”MÊÕ™‹Ð›˜ÊÞ›\ÙÜ[VPSÔ•Ìœ˜XJÛXÌšÝÑÑÞS“”ÜÛSœQÙÚÓØ‘ÓŠÖ›•’ÔQRž”XKÜ[L•MLŒZVšZÕVRTPØTÛÛÛV“•]^ÝL’ÍÎ‘žœÜZÐM]“P’Ø\Ñ’NœÑÌÔ”ÔÍTM
Ú˜šL™ZŽS\Ø“UÔ]ÝNžXVSÕÑÕÙÙLœ’LTÕUÒ”ÝÝMŒÐ˜ž˜‘T™Í‘MPX‘ÐPÑ™ÖS›™”ÝØMS›ÊØž–ZP’UÑÕšÛLQ•Z•ÒM]SQ\ÎÍÑ\JÕ”“˜TÙÖR˜]ÑÌX›ÒÑžU™Ò‘Õ”Û•ÕX•–TÓ˜•ŒUÔØ•Ø“XYÍœ
ÚSÒ^]ZØPTRN‘ÒÎ]’ÚÙÜ˜˜’TŒÌXN\’XœPZPQYÌSÖJÎÖ^ÜÒ›MÜVUP\ÍÒQËÒÛNLœÞXÌXÛ›ÙMÓXÓZ›“VÙJÖQVšÞUUÞSÒ›Ù[Î[ÛÞ˜ÌMU^Ñž“ÖQ‘ÔSœKÜ[‘ÞÛ“MÕŒXÙÑÐSÚ’V\[ÔŒ˜ÜXÌÞUÜY•‘ÌT•ØÔšÖ”TÛšŽUžVÍ•ÛÖZÞ““YÌPLÓÚÌÖžURUÍÝØ•™“ÑNXœÎ‹ÔÝTQ˜˜ÙY˜šÞ[ËÜÚÓ’˜‘\Ö‘ÒÙUQLÔ“\ZJÒ•Ú•R]ÚÖRLÜÜLNXVÚ”SÐ’[]œÜ]›[‘JÕN[TÔV“Ô\šžYžÓSžQÔÜX\VSRRYÞ[šÚÛJÌÚÝÌ‹ÝÓ™]ŒÚ[ž›UËÍÌYÓ˜ŒMÐÑXÓØÝŽ\ÊÚŒRN–Ü[Ú’V^ŒŒÝÑÕR’Q’ŒM]S[ÝŒÓÌÚ^]ÛÌÜMÒØYYšŒÝÌ›\[ÙÚÜÝÚMÝNTœÍPÒØ‹ÍÊÐÍÎUÛÕŒYV’‘›ÒSŽRYžœ˜XÖV›‘Ì”XUVšÛÞLÛ]Pž›•ÝÝQÔJØšÓPZQRQ
ÔÓÑ[ŒKÎ\ÎÍ’ÓœÍÝ
ÙÛ‘QÌZYPY‘•ÑYŠÓM]ŒÔ™ÝTž’ÚL\M›Œ[Y[ÐØ’Ž“’ZKÖSØÛÙPœZL™œ
ÕÌÓ’Ì›’›”œÍœ›QLÛNXŒËÔÜVÚ[‹Þ”V]Ù‘ÛÚTÛ“YÌ–ÜQœÐÛÑRÓžMMÜŒžZÑ“›ØÖQ˜QœžZÜYSœÚÓPV”œÑPžUZÖY[TYÌÝJÍÍÞŒŽMMSÝžV‘UÐÒMPœŒÒ]U\Õ’‘XLÜÓ‘[ÑÑ’ÌÙMŠÝKÎYŒËÓKÊÓ
Ý˜šÜÌÔTPÞ^“›œZ]\TÜÚ]^ÖUTÓÔYÐUžM^XR‘[ŽSŠÜÚ\Ó\Ð–SL‘Õ[ZŒ’ÍšÒÕRšÍSžR–YœV“ÙÓ‘•ÌXXNP•ÛÓÍÕ’ÚÜÖ”RÓÖUV[\LM]–XÞœÔÞTÓYÚž’SÑÙKÊÌÝ™‹ÛÔŽžSÕ^Ð[ÖUTRTÒØY]ÐŒ’ÝÚÕXÞSÐÝTÊÖšœ›JÓU‘ÊÓ[ÝÌ]žZMÖR›˜‘[ØR]V•ÑÌÖØ™œNÕS\ÜÓLÐÝÕÌ‘PÎT•ZNNUŽÐÍUŽ”Ø’‘ÔY]X›\ŽUMÑ›[Ì\šÌ’ÓÌ^ž›UPT™TPŒ‘ÑØRÒÍVœL™–Í^SŒX’Û™ÚÕ[T’SŒÞNSÛÞ[ØÚVSÑÑ’”L^ÚÒÔZÝVZ’]ÝYZŽŠÓM•MËÜKÙJËÜÍ”‘T–•Ù\ÍÔ“ÚÒS–›Ó[TÒŒÐ]Ù•”ÌÚ[˜NMž^›Ì\œTšÔUÐÜXT’[’Ú\ÌšÓLRMÙXZQYš›\YMŒ\Ô˜ÛTR\Û”Ð’ÞQ”[•Õ•V”TTÚÚÛ”\™ÛPPÐ‘ŒØŠÙ’Ö’ÑSYÔTÓSÐYÛÓÕÌ›•Í›ÜÌÖJÑœÓZ”•]Ñ•’YLÓQž‘˜‘”\Ú‘“UM›Y[ÜT•QÕ˜]ŽQÙSÑ[ÑL\Ì’SR•‹Õ’QR\œÔT••ŽÛNÐÐ“Ò]TÛ’\’Ó‹Ù”P’Ò•‘ÖŽZÒRQÔVQ˜ŽV›]RÐYÔÊÜZÒ”L›œœËÌÐÖJÎSËÔœTÙ’ÝØXZœPÜZ‘ÚX]•ZÚÐ”ÓœØUZ\Ü\TS]TÞ“ÙSLKÑŒÌÒ\KÎÝ–\Ñ•ZLÐ[™œ]ÔRQ™™Ø\YUR›[‘•SQÒŒ[LY™YYÙÔ]QTUZÙÛÑ^PU›‘MZ]Ñ›ŒQPN[›QÍŠÞZYRÞYœ\P\TSÙŒTœž”L˜ÕRÛSR•][ÔÜ›“ËÜØŠÚ™•Ó^”––”Ø•š™ØÝR“š“LžZ^L\QÒQRÑÜ]ZžYXQLÑ[SÞŽTMŽ
ÛŠÖÛ\“TÒ›˜ÜMØ“]ÕÛÜÝÙ•“NMQŒ\
ÞMMSÊÑ•››ÓËÚSS\›ÍTÝÓUSSÌœÍÛÖŒœVYÙž^RUÑ”Ñ˜™ÌœÌRT‘Ìš”ÚÒ“ÍPMXÍYš[ÙÖQÜÚ‘œÍ“ZZPÒÔÚ\ÑÞž“XRÐžPÕÔV“ÑT›Û”Ø[KÑÕÑÍQžšžÙYÒŽÛÐ–Y–U]œZZÐJÜM]Rš^–ÐÓZ––”‹Ù™ÝÙŠÓÛÝÚœÑ“]Þ’››NUJÚT[ÒÓ\TÓUUPVN\’MÝ˜P•TYÓÚÌS\T’P”M™L›LÑÕZž^’RTY’ÑšU[•V^Q^YÐTSš’Ñ˜MPœQÔÐš›ÒQšÜÚ‘Y‘ŒÖQ”“’›QÒY^ŠÊÓ‹ËÞŒÍRÚ’žU”œP^TÜPÑÍ›Ô˜ÞÜšØZÐNR“UPÑÜœØÝZ–\˜PÔ‘T˜QQÓœš’ÐÑYÛÙÔVŽŒZ˜žSÙ[]YÐ[”ZÚÐÛ“œ˜›–QYTŒUNU•ÞÜMÝZT˜ÍZ’Z]ÕÜœXP‘šZPÐÕÙÖ\Ò›SÖLÍÝÒÜŒÛÐÜ^˜“ÓÑPŠÖ–š›ÍTËÓÛŠÓ’UÛØÍÌš–KÛ\]ZØ”ÍŠÒ]–JÙ™[ÚXTÚšLSÌÙÛV[XZM‘”‘Í]ÚÖÚ]ŠÞÍÕžÌPTœ]ŒÒ]XÍ’ÚÎRœÔžYžMP–“–™M›ÍÚMJÓÝÙ‹ÓQY›•Ù™›ž›žØ•LÌš‘YÝÜ\”ÙÜËÐÜSŒ\–\ÝšÝXÔNUQÍ˜˜ÌÚÒPQ’TZTR‘Ì›\^ŒSNRÝÓRX“\QJÓMËÒÞP”“]‘RVœÛYÚ›œ™XS]œŒ\U‘•ÜV›Œ]‘‘–™T”ØÛŒœZ]SÜXQŽPÔPÚÞœYÔÐÛÓÞ”››UÍM“˜TŽT••’\VœŽ^P‘ÛÓŠÑ]PJÛ“L\œ^ÒMQŽYÜ[ŽLÛLÕœYQ‘•RÞY”ŠÐÒ“ÔØÜJÙ“Ü•Pž‹Í˜TPZZÜ“ÒMYÖ‘”Ö”V”ŽLÝ•˜šÓ‘LÝ[ÛŒÝ‘YËÍÍÔJÙYÜ
ÔÜV\ÞUÓ“Ô]ÌQÞ–X]YUÑÒ›ÍÙ›ÚÒ[œœÎŒ\’V‘]^’Ò”ÑÌKÖ•ÖLU[ÌžšJÙÞNVš]Q^MÔV\XÑUÙ˜’ÞZÊÓS“›]ÑS‘’JÌÑÎZÜ˜ÊÜ
ÎÒŽTÕ]ÍÛTYXT›Ø’™X•^“›UQU\YÌVL”]ŽRÒÒššÝœ•Ñ›^–œ–™’ÊÛÛ[ÜP‘Q•Û–ZUÞ’VJÍ[ÍÍ•ÞœŽ^YM“LÞÜÐØZ
Ü‘\”Þ•’ÍŒŒÞ’Ü]Ô“X˜ŒUÑPŽPœÞTVœMUUUŠÜRLÛXNÙ“’YŒÍœšÕ”ŒËÙš”MÝ[•ÌÕÔÐUÖL]šSÐU^QV’›žVÍÕ‹ÛÔŠÊÍœ•‹ÚÓ\SSSÔ“[XÚÞNJÖ•UœZ’ÚÖUTQÞ‘Ý‘ØX’[Vœ™QVTNMž™Ñ[Œ•ÔÛÕTMM“T•[Ü\ÊÛTÐÙÕQ[ÑÒPXKÜRÖMÑ™œ˜ÛÜLžX™VLÌÐÙ\ÐËÍÊÊÕ]Ö‹ÑÚÑšÛÍÔMNXSØ˜ÝÙ––KÓTZTMÒÍ[•ÒZL–žYŒÒÑÜÜšZœ]\Ö^Œ•”U˜[RZÔ”LŽÐ\S™ÚP•RœSœ–R•™ÌMœÙÜ™ŒÑV•Ü”‘[›ÞXUU””YQÜ\Ô’ÝŠÜ[œTÕ[–Œ‹ÛÙÜÕŒ’Î”ÝÙUÒ”PLSZMS\‹ËÝRËÊÓËÝÍ‘ŒÝPÒ\QTÖÌYÊÜJÙLÚSMÛšØ‘Mš““ZÛMŒX]Ù•TYYÕM^–“•‘žÚÌ›žYšÙ]•NYÞš•ÙÒVšÛÜ“[”˜œÛN•[’Ü”’ZÜLÙÔ•™•ZMŒ^UPÑRÔŒÎP™KÑ–S”UÐÓÌÑ”TMÚ\•“UØP]Þ›ÍÕÑLÐNLXV’Þ\P™ÒÞ’ÝSVPÓSZMÖÜÌV•ŒU›^PYUœPÌ™ÎUM]ÚSÚJËÞVÑV–ZRVQ”Ð™ÒÝY”™ÍVSR[ÒXSPUÐÕY\Ú[ššU“Í‹ÓXÕ”Ý”ÕL•Q[•Ñ™ËÐSPÒ^P[[ÓXÒŒšU›™‘XŒÓT“ÑÓMÛYÔL]Ø™LLÚ]ÜÔ”Ð“Õ‘˜MÜÌ[VPÑÐ“^Y\TšÍLÒ™’ZX™QP‘“RS[^ÍšUËÐZžŠÖSTÓVZÌØÖ\ØÕ•VÛÓÌÚLML\ÔŽLÕMU\ÐZÑ’Ô‘“‘ÙËÛ–‘Û’ÔYT”X\]œŒ•XÜŒÑÖœÞœ’Þ“ËÛ[ÑRž˜™QM›ZÒÙUØSXÓ”˜’\LX–Q–•[ÚÎÜ›Œœ›ÞÞYÌ”“ØØSœÍÒÐÒLÖRÔ™”ÐÎKÑÔRŒ“››UŽZPÚÚVVŠÚ^X[^YZ™ÕÛÔRÚÍRÝÖÕ›VLTRÛÕÍÛP\–RÔšRÍÜ^•Þ]QÛ\ÌVÊÛÖ›ÒVZM••]’›ÚÖQJÑR’Ó™Q\ÔTTžŒRÖ“S[YÍÓÓÙN^‹ÞXÛž’–ÞœU[L^SžX”Ó[\›œÍSQ•ÊÜÝM›ŒÕ›ÌPT‘SR›PÜ–QœKÐT“YNY”ËÕÌ–RÍ[\ÞšS^[ÝÜÓUMÌÞœÔÛR”žžØ›’ÍÌ\\[]ÕÛY™ÕÛÛ^LM’ÒÛT–VSŽ[ÛÍ\]ZÑZÍL]ÞœVšQÍÊËÖ›TÜ“TMUÓM•ÛÍš”ÜØUŒÑZš™Õ‘–R›N“ØVMÌ‘MÒÚQÝYÛ”TSÞX›–Œ™NN
ÍŒT]S’ÔÕ›MZZJÓÝQRÓ“YšL”L”Õ^–[X™ÕšÛÎ˜YTQÙN–]˜Ó]’QÓÚž•Ô›‘UÞž]Û‘Ñš˜Þ‘ÜÍ‘Ì]™XÌ”›Ó”^P“•ÚÍžÝY•ÚÒM‘™MU[XÜÜš”˜–ÚZ\ÓÌ“”]UQÑQ\ŽRšTÖŒ\^MTÊÔL–Œ™˜ÛÍLŽŽ–ŒŒUPÎ[M[‘VU\ÜVÞžMLÍÛPËÚX™”ÖRTÙR™ÐÔZQØMLUÌQÒÞÔ”KÛÔÔÓT™Zœ^“ÖTÑ˜ÚÝ”Ù]]ÜZÓ”UÞ–]ÙÜ›Ñ›š”ÕMÐÙÝÜØYPÌ”Õ
ÐMVU•Ò\ÖM™™]ÝYÒ•ÕQ•Ô”ÛLÕÚœŽVÐšÛQÕYÜÑNQÑÐÔYžŽMÌRÙŽ–‹Î\ÔØÎM™\Ž]ËÕœÌ[]“ŒS’ÕØÔT”ÔÚ–šSÛ\Ð’š˜Ú^]U›
Õ••ž›ÒYÙYZXÞ[Ú]›Œ”Òž›’’URØÖ\MÝÒUYRÔÖÍÙÛÒÜ•\œRÑ”MÕÞQ^YÔQÍXš›Ò“ŒÞY•Y›UÑ”™›•˜LQ“Ú[M›Ø\ÖS˜Ì’Ôš–œYÖŠÛÙššÌ
Ì˜ÒL•Ú]Œ\]ÙÓÐÝÖ‘ÑÍ]œÝÖX^›LØ–œLTZUÒÔØØ[SXP™ÖYPŽ\PŒZ‘ÍÌØÒ™™“ÓšLSÕ^š‘^žÕS[[˜Üœ”LRŒŒQÊÛLÌ˜S”]N–ZÒÚÝÐÝ”TÛÍÕ™ÐœZJÜ›Ö]’RÔ’’Û“UL[UÌ™ÚÌZ‘ÔY’ÙNPÜÛ’MÙÖ[ÛšTšÑÍP•ÝR[‘šÑTPZMR’“Z–[TTÎV\MYØ^[T‹ÑÐSRÒUNSRÞ•UPSœØS–ZÞ‘ÜÌUÊÌ]Þ•LÚÌÑZKÕZSËÜLœQÖZYÓÑQ””“Ô‘Û•[Z“^TÒÕJÕ\ÒÛMÝX‘LÜÛÑUXÜZÙ–[™ÑÞVŒ“UšÔÔØÜY”LÑLQQR’•L\ž›‹Í\ŠÞ‹ÑÌNU[•
Õ\ÍPŒÒž\ZLYÕÐLØ’
Ú›œ•ÝÖXLœ[•MV›–Ø™˜Ø]\ÙÕUÑÐ’›‘“\š•Ò\QÓÍLR–XŒ™Ý’SUÖXÔU›ŠÑZ“ÛJÒZÙMÐÑÌÚY[ÞTÛUSUU^UÌ^YÍ^“KÔPVŒÚZÐÍÓ]Í]Ý‘–RœÑž”ÖšÕ™‘Ò]RšYVT“ÔšZÊÖšVÜQÓJÚ–ÑV›L˜Ò‘ÐŽÔMžœTšÐÒÐ’šœZŒËÓŽU‘ÚÐZ“ÖÑR^MVŒŽMÓ‹Ü
Ø•‘ZÍÛVÔÔœ–“ÝZS]ÙØŒÒÌŒ•Q“žUÔ”ËÚ˜ŒÔÜ’ŒÞŒYZ\Ú•YÓ‘^U˜ÛXÒÐÕÔ]–R]ZÖ\JËÚÎ[[ÑV“ÊÑ–™ÎÜL’Ö‘T
ÛÓÕT™Ù\^M^Yš’[T›Y“’SÙLšÒÌ‹ÜÜQTÕšTÑŽS”Ð^”UÒMTÕÑÐZÐJÙU]ÌÐ‘ÎM–\ÚPP[ÙZRTZÚJÐ˜˜ŽLQŒ’Ø[RZÊÚÌ˜NÛÝQŽSRÔ\šÖ˜ŒÑÒÝÝÜSMR[[Y\PÞ‘^‘RJÐ[LÝ˜ÐÓÚ[RÒ[ÔÕLÌÌ™›ØY”Ù[Í˜SS”ÑX›ÒšÊÔÜ”ÔÞ™L•Û]“ÒN›TÖKÓ˜ž
ÙŽÔÙÎÕYTÚ’“›™ÛTšR\œÐY–[[MÍ“ÛÐØÙœÓšÐ•^UÕ›ž\˜JÛRÙÔT[”ÛžLRTÔL[^RQ•’“–YV\ÝŒX™ÖTÑ”ÓÚ‘ÜØŒÖXXP”ZÓÓÚMV’Í”ÚÜY•ŒÔÝÑÖ
Ô[UÜ]ÒT\Ó]V™ÑÎŒ\Õ‘[ÚÍPœ[L™”YLØ™Ü\˜ššMžQŒ‘L•ž^›]\Ù˜ÒÎÒÜM”[Ø”ÌY•“Ž
ÞœŽÚNJÌY›\STP’SÔÎ\”ÖZ›ÕS^Õ[ÛÒÓÜžJÍMÒœLÞ^•ØÊÚÞYÝÚMØØÛ›RSØ]Õ“]ÚPP\•ÓÕKÍÓŒÌÌÙŒÙ˜ÊÓÐÖœL[TÔSÚšYÛU›Qš’Ò™›˜UœÛÚÓ’S’šÖÊÌœ˜Ì‘˜RYTØÕJÍÕÑØP\]ÎY\V›PŒÙUÜœÕRJÍ˜ÞQÓZ]ÕMšÙÝÐ•œÓŒÌÝQÛÚžÍ–“‘Ð\ÑÝTUŽ\–’ÛUŒZœÕÚ\T“^ÐÐZšXÒM]ÒÜ‘ÔÓUP“LUŠÛØV›“™Õ\ÙÝÖ–]Ö›˜ÒÌ“Z\YÒÙžž”YÙÝ\Ô™ÔÙYÌÚÓTSQJÔZ\^’ž™\ÐÒ”›YR™ÛU‘ÚLY‘NLÌÚÎJÎÞQÛZKÛUÑÓT^TÛ›U[ÚXÛš
ÓÔ[–ËÛÌKÖÖMMÍRÑÙVLŽUÌ™ÐÕÑZÓ›QÌœŒRŒ’NLSZŒÜÚ“œQÓÝ“YXÙRÐÜÔÛÖZUVœZXUYš]PU›V]œZÚ[USÌL•Ú•Ü›ÔŒ[ÕXÌ™Í˜]Xœ”žPPRŽYNX\ÔÒ›SZVQÓÚQÙÝÚYÒšÕ’šÌÜÍÛšZZ]
ÍÚKÎ^]N^U\S›][•ÛZ”ŠÔÛÞ”Ð’‹ÝÞLŒU˜]‘ÛLÒ”“Ò^ZLVYPÓÍÊÐÕ[ÝÎQÐØTZÚÞS˜”›ØVž]šÛÕ›ŒžJÒ™UØLR“ØÌÐž•MÝ”Ù“š]Ú“Î\NÞR•Z“LÍTNLž›‘ÝÙQ™MÍÜ•œÜšŽ›ÚYÔÎšS\Ì[UÝR”\“”ÐØÕ–ŒLÌØZÔ–”•Q˜“˜Ö\“^]Ö“›ÙÜ•Ô–™ØÚMÜÑRÐ‘˜]Ú‘™ÚÞÔ’JØÕNNLœ‘‹ÊÚ]ŠÍ‘LÖšÚ–ŽRUÓÛPYTÕ›ÛÞŒÐÝ[˜MÞÙ•™NPLÕQ›XZQØ–Ó•ÛÒÚÑÐÚÝ•šÎYÌ]P\œ”œXQÖ\Œš\LÑPšMÜXVZÓÓ\S”ŒLŒÕ•Q”ËÛØ˜]SšSÜ[^]–ŽNš›\•›ÓV\XÙTØ˜ÌS™™Ò‘š^˜Õ™ÛÔÒ\•‘™Ô‘\RÑQ^”•UÛ•ÍÜYRÜŒ[^PXUZX“™ÌÌÕÑÔS•’TÒÙ
ÔÑTQÔÞ\ÔÝ›ÌV•ÛLXZÙ^Œ•“–Œ“YÌØÒÌZYQX–™Û–•ÍÐUÍÕÍQÛZÙÕÙÛ’[ÌÕÖNKÍÛ”Ý™›ÍSÌÌ\’‘•L[Ð•Í\ÐÚ‘S–“Ö”QQRÕQQÒÐ–^SÓšUÑÑ“[VV”ÞZž’LŒŠÛ[M–\ÓSZÜÑ’”LTÑVœÐÎŒ”ŠÔÖ˜Î“XTÐ›RÚšÒÚÞ’ST“ÓÖYÑYÕÝ™Q\Þ•Õ’ÊÍÐÕP]ÖYZ
Ö’Ò‹Ô]YÌ™žœØÕ‘˜]Ž]Ö\[›Z‘ÝœÓÞ“RÝÒÔP•ML\SÔUÌ[YŒšÑÌÚÔSÐ”Q^M•ÕMÖžRLšQS™NXž™•ÍU‘‘Ø”^Ü
ÒÚ‘Ò›“ŒÒZÖŒÎYYÕÛ–^ULÑ]Ý”ÛZ•˜Z™RœÙÌRŽÓTžšU–UX^^S”ÛQYÔÑÕQ’›R”Ž]MM˜LÖ”^ZÌÐÒÕ[Ý\\L[ÓMÌN\žV˜ÜÝœÙ›ÚJÜ[ÒÑÌŒ•][SÍšSØÌŒRš˜•›Ð’UP˜Ö•Ü[ZRÒÓ[ÑÐL“Ò]‘R
ÜœžÌÌL‘ÕS\’PQSQÔÍÔŠÑQÖYÕ˜Y™^“”ÌÛQÓTRÞšÛ\V“QSQSQÝJÑ“ŽÓÔ’’ÖTRÜ‘Ô‘QR\ÕÜÕ]ÚT‘ÊÐŒœL‘Ó’[L–YÞšËÝ‘ÍTÍ”•QŒ“PL[\ŒR\–YS‘Ô’ŒÞVNžÖ[”Z[Ó–“ÚÛZÓLPN›^‹ËÚŽ]Ø–•TQ™YPœÛQ˜XP˜ÚTZM[‘QS\šZ^ÚS™›Nœ›ÕšUSÔÜÜS‘Ü]LÞÍÚÜJÔÝšÜ]SÒVÛžTÝÜžQQUžžŽT“\”ÌÙØÒÐÞ‘ÍÌœ^[\•’ÓÛÐVÌQ\ŠÞ”S‘Ì[\ÓZÛÍ•RNX”\Í’Üž›QÝÞU•Q–KÞ[ÎUÜÒÒX”\ZÔÛ””L˜Í]]LÔž›Y’ÎNZ–‹ÙMØM\™SŠÌNšMÜÑÜÔØŒŽ”ÎLTLU]U”‘ÒÍRÞXœ˜’ÌØ[ÐÑ‘RŒ•Ü–š’ž›Ú›ÛÙ•M[ÌYÍÖQ”NZÎŽÙZ\“LP[˜QšÙÞÝØÓ›YXÎ\‘‹ÎKÊÒÍZÙÙV‘
ÒTÜLÎ\TQ^’P”Ì“’ÎR–™QØÙTZŒ”“’ÒÙØVœÐÚÑU•S“ÐÖ’ÙŽÞŠÐÕÛLSZÒÕ[ÝÜ\ÙÚQQ–‘“T”ÖžR’ÛÕÔžÜ•ÜTŒZ]Œ™Ý[MR›LLÒ]PSV”ÍÕÍVV[ÌÑSÓRÝ]]T›N•“TÜZ]ÕÜPZTšœPœÞUÒ]RP‘žLœNQŒLœ“^ŒžSÚ–RR“šÔšÖ™\ŒXÊÓ”ŠÕZ’ÎXÕ’]ÐžZÐ[‘”ÕÒ[Û›”ÖœV”ÙÍ”SÒKÊÓœËÙ™“•žžŒÓZ™ÔÚ’œÜ˜ÜTÊÐØ\YÓ•–N‘‘ÍMšÑÌŒÙYÌUU”ŒÖQÌSUQÓRP]ÜLÎL™ÞLÓÞLžUÑÚYÚ˜R‘ØÐÓ[YŒÔÎX•Ó•ŽÓž–[ÕÒQ^\”ž™QÍ^Ôž‹ÌÜ‹Ð“˜ŒÛÚQÞŽ\“S“ÑÜØ’LÝÓYÙÎJÑ–R‹ÓÖ’MÕšLÒØœÙ[Z[ÛV–ŠÍQ›œ\ÐQÞšÙØ˜Ð•ŽXÒŒZUÝÌ\M˜œ–JÓÎÙMÒ‘’XÐÕÛÍ–TQ˜ZZM[\ÛR’SL˜ÌTÝ“™ÖÜÖ›Ñ^˜\V^LŠÞ›’ÓŒZZXX”V•SP[\ÑPÍ•œSTÑÎ’Ô‘]•LQZRM\ÚÓÛŽNTÌ‹ÎÙ]JÐŽKÎÜ\œŽ]ÍTÜÜžÓ^™Í]ÑÝUØÎ˜ÍRZÜMZÝÙ“”‘’–ÔÛÑÙÞ]š””VS’QÞS[ÝÙœ‘‘Õ‘“M•–MMÞ[Ý–šÓ“›\”–[LRVÝU\TÑœ”R›Y””TØÛÚÜ•ÔPÚ[ÎÛÒ˜T\ÔÕ›Z›ZžPUÛÚSÎËÛÜMV^VV\•ÍÜ“V^ÛLÌ]›Þ‘U[’[–ZQ]ÙÌN\[’ÌÒÞPRÙT”Ô’‘X‘ÍÕ]ÑÜMšÕ[YÙÕX“–MZÖÑSØ“–ÛÌZÎÓœXÚÞÍÚÒXÔšNV›PL”JÙX[ŽœŽSËÜÝÑ‘ÐÓRÛÛ‘ÔMYX˜™\MœTŒ™U\Ü[–›ÒU]’ÕœÜ“ÐQ[ŠÛÔ™”š™RÒÒ”N^R‘S^RX’œZZÝTŒ™ÔZÔS˜˜™YTSÐÔœœÖZ[ÍÍœÑÜŒTQœÔ•T›\˜˜LRšNÌSÔ™UYVZ’ÞQœ‘œŠÎÓ•›[–’”Ü“ŒQ‘ZQ•šÌ•ÒÌTÓXZZXÞ^V˜P‘ÒÛÜÚÌRU›ÖÚMVÐÛPÜÜÜQSQ]Ì›YZÕKØŒ]›ÛY™ZÐMÌŽM””™ÞT]ÔL[ZQPÝÕRÑÕÓÑÓÑÓ–\š›XÑ^SšMKÝÑQÔLŒ–ÓÚÝS”ŒœØÒ“•QÕSUÞ‘–Œ]ÝšMŒSÑ›\XÜ’œ‘œ\“ŠÌ•
ÛV’PÕU“MÑR“™^STTÙÓ–ž^ÒÔšYÒšÛRŠÕÚP™ÚÛ”SœËÓSÝÒžMXU^QQZZ•ÝXÜ™ÚÖÛÊÖ–’[QÒÚSœÒUÊÚØÑš]ØÙ“YœÞÍœR[ÌšTÌQÌŽ]Q“NŒØ™YÝTÕLÌÝžYÛ]T–U“QÌÓÕÚžVMšØÌZÜMŠÒÓ™ÚÝP˜‹ÍÙš›Y[ž•S^‘šÒÛS]PKÕZŒ]ÜÒÝšÚ’ÜÙÙMQÚZ‘XÔ’Q\Í[\YNÓRTÌÞTÔŽ\PÞÐZÔÌÍÚÛÑÔSLž]Í‘ÒN˜Þ“’LRÖ‘SÍ˜ÔPÑ]ÒÑ˜P–ZÚÑUTÒTÓX‘™š\ÖÍKÎX–š”™”[^–PÔSSÑRž^ŒTMX›“ÎZY™XÖ‘ŠËÐÛ]ÎX–“SMYžŒU›œYžÜ^Y”ÓÖ“Œ–•ÜÐRNÒV]ÚÕ˜•JÛœMRNXUÓM’M“U‘ÍJÛLXÓZ[Z˜–S“™ÖÚÞ^–šÔÐVTš
Í‹ØÊÊÐÙYŠÎ]ÑÚU\Ð™[MÐ\ÑÜÍ™Î^Q”“˜’ÝÖTLÔ‘ÎR[ÒØ’\•ÔÝ–]Ø\ÌSÍ\ÖRÒÍŒÚZÌRÙ˜ž^QÎšZLMÞž^™™Ó–“[Ì•UUÚÌØ^š^Ì[V–š’ÎŒZÕžLŽš“œÕÌTÞ]–’ž™[Ø[ÚÝTÐ‘‘ÝÝžÓÔÐ›–RÓVZ’L˜M[ÛRURœÐLÔXÍÍMÙÌœŒZ™L›ØÙÙÓ’ÙTLÓ”Ú˜Ñœ˜ÑšÙ’˜Ü]ÕØšÞÖ˜Ð]]XÞSSØ“ÞPLÝÌÕUNMÙZTÙR‹Ñ
ÐžN’LQYÒMØULÞšLŠÑÙÖYYŒV”Ñž‹Ü‹ËÍÖŠÜ\\MØÐœPÜURXšÕ[Z”UÜÛÍSœÑ[ÚÐL”PÕÜÓ\]TÕ›˜ÜYT[’ZRÓ˜’ÛÝœTSRÖÊÒÍÖŽšUØÒÑÞNUÜTž”]ÝÔVMÒÝ•[Ì’œ[ÙœÍÍ[Ñ”LXÑÞRŽ‹Ñ–ÛÌÞ’Ð’MÓRÜÙœÐšËÜ[ËÓÐTŽX”Ñ’^ÜÒPœœU™ØÐÐÓQ“Ú“ÜØ^]JÚÝŽQÝ”Vš“‘TŒQÚ“T•TžRLÔ‘MNL˜ZX”‘ÐÎ‘YÍšS’KÒ›Ô‘NÛ•‘T^ž˜TŒšÔÙ[šÕÑ”RLÐÛÍQØL˜Í•ÛTœŒM˜UÚLÖŽLÚRLÌNVŒ’˜’RÛÍLR‘Þž–^L›’S‘Ð”]RR’UÝÌÜÌMÛ[ÒL˜ž”’YŒYKÓÒRš\Ì•ŒUÛÐ˜ÒÌR˜M–‘ÓQ•ÐMŒÑÙØÍÓÒNÜÔÛM•^‹ËÑŠÍØ›’[Ì˜JÞSS’YRÔNÓÝŒP”ØÕX\ÕÛ‘ÒUÜ–‘ÞžXžP^Ö›ÜÌÙ“\•ÜPÒ’Û™ÊÖÛ•^œQÕ[ŒÑSXMÍÑÙÔ\ÍÝZZV™žT›Ý’\^[™ÑTMRLU™Ž[œULTÑØ“MšÜLÍÞÚ–˜Ö™“™^LM’ÙÕQUUMÓœ“Ú›ÜM’”RÜÌ‘Ö’ÛÍQÖ”Þ“U•™S›S\LYÐ˜V’Õ^]šØÑ™Þ\Ü^žœ•TÒžšUJÐÍÖM˜œ’ZÒ’TÚÔœUÐTUPTMUÛÐÜ”M^NP˜TÒ\QœÍ’’Ì]ŽÚVM™‘MÊØËÝŒÙžÑÚŒ“šÝYÚÛÝ^ŒTÌÙŒRÚÚYÌYÛMÓÚUÎÕ]ÕÌ\ÞR™Q\ÝMMÕLÌ˜™ZÒ‘”ZXL˜Ø[ŽÐœ•MÊÞLUR”ÎÑXœÙV”œÙR’œŽU•S™œ[“RQÛUX\ÑÖZRT–š›PÕRY[”ÒÊÍ•TÎ]Œ•\š]”Û“™šÍžYÛÖ›ÓXÑ[™ÔÜÝžYÙœZÙ–^ÚÚQÑ”””Û^’ÍZŠÝ›ÍZ‘]ÌÓÚÑYÕ\ÝÛ[‘Ò•™™Ò–œœÚ‘Ó[QYÐJÙ•ÑŒUÞ–NN’ØÑY‘“•ŽUÌ[œš”ÍUN]Ì›ÚPSJÞ™ÛM™TTLQ˜LÞ‘YœÕËØ[MÐœPR\XÖÓ[ŠÞQÊÒÔ[‘ÍNUTÓ“
Ô^SŒœ’ÚÔRÛÓ“ŽPØTP›ÝÍ‘ÛŒ‘–Ž
ÌŽSšÒV^šÞ˜ÓMžRÍŠÕYSœ“MLÔÛSšÕY“Z™
Ð˜ZÑQ”ÊËÙÕÌ’^S[“QLQÌš^\T\”ŒÖÌ’QÜPYSž˜KÛ[ÍØÔÕ’ÚÒœÛššÎ[ÕSÚÜÑQMQÙSÑØÓÝÞ‘š™NŒÛ\ÑÙÊÕŒ[ÙZ˜X\^LÓ[TVšš’Ô’Û™Ø’”ÜÝ]œËÒ“L]ÊÑÍ[˜ÞØN[X–’•^Ö[Ž’šÕU–‘^P\MRÌ™Ù[Ú›ÕÕÜ–PŒÜZÚ“Ù•ÊÞ›•R›Vž‹ÔšÜT
Î›ÚÑÝÖ\[Ù\ÌÚSœØMÌÙN[[^QL‘V]ŒYSŽQPÛT‘ÔQ’–˜ÙSNT[ËËÒ›œ‘ŒV”TÞ’›^Z•\ZZ]Ý“N]ŽQÞ•ŒŒ’Ö”ÛXÙM^”]’ÌÞž“–ZPÛÑ
ÑŠÛÓRÝÖSÞYÒ•’ÛÝ˜›Ú“ÌÕÚ“’[–VYÚÞQ[Ì‘ØØLÖŽRÛ‹ÚÛ›\ÝKÜYÍÒŠÓ\ÜM‘XMšQËÌ˜•Ò]Î™ÓÞ“^œËÔRKÝ‹ÒŒÌÔž–M–“‹ÑŒšŠÓŒUÎT\ÌÜVX”‘Þž\ÝšX\RØ‘ÕX•”ÐšÚYœØ‘LSÐÍN•X’ÑT™ÖœT\Ú
ÝX˜›œ’ÞLMLÌÙQÞ’™VMÎRV‘‘Û•–\”]MÚS’TQQŒÍ[ØŒRÙLÜPUS\]ÑXÞÛ˜ÓÛÞ^T“QÙ‘ÛUÔ™ŒNSVÜX^“ÐR^LÔKÑV•R^“^[YÚ™•ÑŽÌ^”PÒÔ–•Ö”RXTÎ\RÍÕÝS]›š“RQYÝÙÕšÝÐÓV\ÙÍÑÑL™‹ÕXÙŠÙ•ššSQÜSURTR]Ì˜ÞYÝÎœÓLÝ™‘[ŠÝ]‹Ô[LNÚ”TØ[QST’š\ž”ÐÒÔžZÝ]ÙY’LÑÛ›˜M‘™•Ì^›[ÎQÌÕ›ÔX™NÔQ”ØÓ™”ÒÒÞS’MÕ[›˜L’’[ŒœÖXœÑÑ•‹Ó‘ÙXU›ÒÔ]^Ü[™]Ö–ÖLÞV^M•Ô]‘T’ÜÚÍQÒ‹ÚÔŒËÙÝ‹ÍÒÎZÖ˜ÌœRP™LT”\Ø‘ÌX–•VL™™KÌP”ØVQÓšUœšÐ‘œž‘˜TLÔ^[ÛX•\PR’Û‹ÕÑÓÚMŠÓ‘ÔØŒ[ØUÌÛ“YÙXŒP™ØÙœÒÖ›SÚÙÑ]PSÙLÞÔ•UÕV•ŠÍ[‘PLVŽ
Ò]ÊÛST]‘“ÛÌKÛ™šœ’Ó‹ÑUT‘‘ÓÑ“ØÙ^™^\’ÓU[MŒÕŽQÙÐÞÖR›ØR•\\ÝÑV[U›VT[YY‹ÒÕY‹ØRÌÑÚÝ›žUÚ•\ÑYÌPÔL–œR’URT•”ÙRÚØÛMœ˜ÒVUÛ™ÞZ“ÝZÑÖ]ÜÜ•KÝÕÔÞYÌÙÔY^\ÕÔY[ÓÑÜ“]Ñ”šœÕÕÛšUÝÌSÒÔÙVYÍP]ÞNMÔ”ÝšÌNÙ”ÕÌÍPÝ[Ü’ÍU–\\XÝÚ\•ÜPÚ]ÔRÊÛ˜NÑ™ÐM]Ø•Ñ]Ó›ÙLÓ‘[X^QYMÞÒšÙÚRšÕÜÙÝœY‘’Ñ›ÑMTœ\XÒÐÝXUÕRÍœ™ÕÛØÍM^UÚ˜ž‘Õ]ÙNTÞ\™ÍžÚÒ“ÚÒÝZVM™žX‹ÍÓPÝÕÍ^LÞ›[Q‘P”Z“Ú“M’ÙRÞ‹ÙKÚž™\ÜSÍ‘ËØNUJÎKØ˜Õ[]PØ•˜N›PØÌPT’Þ‘X“^Ð]ÍSUŠÕÕJÐN‘ÞËÔXY™Ì“šŠÞXÖMÞ“]ÎÚ“RZÐPÐRÐšÔZÙ™N]LœNTœÌX\˜JÍ^ZÙ™MØNMÞ›ÌMX]XLX[ÜØYJÝÔ\ÑÖœÓ\[™ÒMMÐ]ÐMÞ’ÝŽL•Œ]ÓVÒÌÓ–˜’L[M]Õ[SÕœMZ›™ÜÝUZ“›‘”ÑÕ‹ÊÒžMTMÙ’PœÜšÙ›“ÐPQžÕØÐUU’[ÊÖUVœUÙÕRP™‹ÔÞTœKÌZ[^”Ö[“ÓÞœÒ^ÔÓÚP^NÔÞQL™ØZ–\Q”šP]\UM™ÛØ•ÕS[ÍœMÛZZLLœÚ”Ú’ÌYÝ[
Ö’ÛÕXœÝÞLUS\X–R]Ì\‘YœÑ‹Ù™ÑÙQÝÍQV“ÐP•ÒZQ“ÒQQYQ]ÊÞ]UÑQ\Î˜L’^‘”Ñ•ÝÜ””šÞ\“TÍ–“]Ü[ÓœÍÊÔŽRÛÛ\UZPMÎ˜Ó\ÕŒÐRÞQQSÜÐÌÜÕÝ™MÎ\QÔÎQÜÌÛ“ÔUŽL–ÚÑZËÜÜÙœÖQPËÑ]ÙYž
ÜŒ™ž›LÝÐT”LÞÖž’˜žMÐV’Ý•‘Œ\SUŒœÐžÛœ˜[Ò™ÞÒPÐQJÕPØNJÚV–ÚÛšÊÛÑÕXÖ›ÙÒ’QœØÚXT‘\RÑVœÙÜ\LÌ‘RS]œQÒV‘ÚŽÎRÐSVLÍ^Z˜šÜÍ\•N
Þ“]”ÑSÎÝ’ž“ÌS•“\X\”ÕYÍUZÔ‘˜ÙL\ÑÝ\““Üš–JÙQZRQSÛÙTPÒ”ž”ZUØZ’ÓÖ‘ÝP”ÜÓSY[ŒÖšÙšMÛ\˜ÑÒ\™ÛÚLÚ‘™ÜÝUÒ”QÞTž\œ^ÕVœ–\T•ÐÍÒ]ŠÚPLQÞ\™Þ›ZÒŒÑ˜Ö\ÞØÑ]”“”ÍQ[ÓRÌRÛT–YÝÔNN[žZ’ÔÒ•ÑÍÕÊÌÔšÚ“^ZÙQYQ\“Ù•Ý‘’MZÎX’L–Z’œQÞL––L’ÑÎ’[ž”ŒœÚLMÒÒ[\ÛÚÕU›KÍÔžZN’N“RÒ™[ÒžœÞL”P“ÐN\UÐ“TÓÝN–UÖÌÙ’]LÍœYR[RžUP’ÌÐ•[NZZ•V[UU”ÑÙ]QLÓ˜ÕÐ‘œÒÑ˜ÕÜÐÓÛ˜UÝÐMœÍÖ^Lž[ŽZZœÜŒ’ÕÞ–˜UÍËÒ\SMÔ\TN
Üœœ^TÛUÜMŒ”ššœ‘’ÝQ]žPÒÐ]PÐT›YÙXQ•UŒYSÓ™ÞZ[ÕžYÍSÔÛ“Þ\Þ[Ò™S›ÑÍØÎ–RŒNX]ÚÔ^ÍZŽÜ’ÔÑL’‘TÙ^Ò[š\MTQ•›Y–RQVTZÍ›ÐLÍ’ÍÔœLJÍÎ^QY›˜ËÍÞXÜQR“Þ^™ÙLQÛMÙšŽ™PÑQÙŽTÎMÎN\ËØÙ”ÞŽ™œ™Ú˜ÔÐ“Ó[]NXMÚÌ–[Ò•ÙVœ••’\ÔSU’NUÝ”–M\RR“]XNÜÕX–ÔØØJÜØVÌ˜ÞX]Ô[‹Ó‘Œ’Ô]–’ÐJÜ]•ÜÑRÜÕ^’XMR\UXÍÒŽ\VYPËÓYÔ™”S”ÜÚ•ÍÙ’\Ò“RSššœ‘SMPL–UYÝVZPÛÊÕšY‘PÜÙXZÛÑY’‘[š’JÍš[ÝÛYžS‘ZÜYLžKÝ\JÑ‘RØŒ]”ÐÕÞRÍÑ\ÙR›Q\Ì–›ÝÔÛZQÍV[ÕÓ]ÜLÞ]‘™PRÒ’M”]˜MÛÝ
ÑUÌ•ØšÑUÔÐ”–’›ž^ZVœYR•JÚÜÙœV˜]ÓZÚÓÛ^Ñ‘Ž]šU“Ö‘M‘ÔÝ›ÌÍKÓÖ˜ÖŽTÓÐR^•Û\ÌÐTÝSÌZ˜Ž˜Ù]KÓÍ™ËÞN^ŒÍKÚ’ÐQ]•ÔQÐÜ\“ÓÕÜš›™ÝØ›šÜÔQL˜ÎTR™\žSÕÓMSX\Þ‘ŽÕ‹ÚPVMÔ’œKØœÓ™ÖÜ˜Õ]ÞÌ^Û“R˜ÍQŠÓ™ÜÔ˜Û“TÞ••Û™’PY^‹ÒÍšL™ÕRMÚÛÛŒÖXÕQÓÐ‘UÓZ™T”ÒÎ[ÖRšT•ÙœÓÝ“PSÑZÓ›ÝS]ÓÒ\”]ÛX‘ØQMU˜TU’ÛÜ[ÐS]R[ÖSL\ŒŒSNQ›Õ”\\ÛLTTÝÕ\Q”VZœÑÐ•Ý“ÓÍZTÌËÎZ
ÓžÜØRÝ’ÜÑSš›ÑÙU\ÞUÑÜšÙ‘”•[ÛYÖŒŽTš\ÓÝ–˜Ü•ÒKØÞŒ]ŒÍŠÔÛ•YYNQLU[”V[ÍJÞRM’ÌÔÐTYÓ\MSÎ’ÚY”Ð‘•’•’ÛÖUVÝ›ÜY”Ð\Už•šL”‘ÌšÝ\[S›ÐÔÙÌXÕL[•Ù]ÛU‹Ô•ÙÌ‘›YØ™šØUÑØ’PšÐ”Ø˜Œ˜ÒÚ™^\UÖ[ÞM›MMÑÕ•‘\ÕÕ‘^“UŒØ™ËÔœZV\Í’^–ŠÖžR›SÐY›™Ü‘“ÔÞ›˜‹ØÍÞ™Y˜ÝL˜™ÚšZÝRÞVÔ”S[Ò\R“X””•Y–ÔYÞ[ÐSÐÞ•Þ•ÓX“YU”“\ÔÝ’ÓZ˜XœÓS–•YÔPÑ™VUÌ\˜RÒÍ’ØØÕÊÖY˜Ì‘ÕÕÑ›–‘Û”T][Ûž’TÔYØœžY™YTŒ™Ü”ÔLŒœÚ’ÐÕÜÙÌZÜ”XZULœ–[ØÖ‘••™ÜÒ›ÒœÓÜØÓœRž“UÕ•žYÓÚ’ÒQUšRQÎYQÓ]”ÕÌšZŒ^QÕ]Þ\ŒQÝØ’Ìœœ
ÒÚ–•MYžÙT‹ÍÓžÖÒPÓSÒÔZ•ÑÑ
ÛÛ”“œÛÕ™KÐZ”YSZ[›TNR‹ÌŽY“Í’ÕN[^YSÙÞTÍŽ\Q’Q•Þ™UžÒÓŠÓÐ’–ZÔÓ”]UY“S•ÞŒYÎ^Q\ÒÒ]ž]Ò™ÌÔÚœRÒ˜ÖU[˜VZšÙžÑKÒÎZËÜœÜ\MœPNQ“SUÔÜKÛÔšTN“YÒ“TQUÜžZTÙšLMJÑÞŽÓ‘QÒ
ÓZ[[™–“”ÎTÒŒ]RÝ›^L•‘šÚŒÓSš™ŒžZ’š™XSQ•““Í•L›Ó•’SZX]šÛ•Ö\–]\™ÑÕŒ›ÔÌÛZ
ÝÌ–ÌY“‘QÞž‘[šÒÌQ”L“Ú“ÝÖ^TšÔÑ^˜”ÔÖZ]”žŠÞ‹Þ–ÙLœ•UÒQ‘ŒXÕPTÊÛÚ›˜šÑYÖLÑØTÚZ•ÍœQžPYšÌ’ÒÑžPÚ”YUÔYÔÓŠËÞ˜ÖV˜ÔL™“LNNJØV“šÌZËÑŒÓÍ•ÒÔœ^Ý›ÝÒPÕžœ\P]UÞ‘YÚÜ^RÎVÑTØMÕT[ÙLÝÌJÝØ™ÔYÔÊÌœ™RU˜•U’Ù\”ÝÑØMÍM\‘U“ÌÚÒ\ÎML™ÌØšš›ÚZÐÔÎY”TÔUR[PY”ÌÞJÝ\šÝYÞPYÜUØVŒVžšÖ\“SUœÜYÒŒÕZQšZžQPLÔ[ÕÝŒ•MÞœ”YLÐÔ‘^ÍÙÑ^TÌÝ™‹ÑÞŠÖ›VŽN™™NÝY™˜Þ^žœÓÎÝP^•ÚšPRZÔ‘‘MÔ]U™Mœ\‘ÕL˜Þ]”\ŒÒÒ]•]ÖKÑÑLÌ^SÛUUÐšÕ“[ÑØ^Y[\‘\S\šPÔÒTŒSÔU^“^•M]ŒSTÕÖY\Ó’ØÑž\ÓšR
ÓÍUÍ^[VžÑQÒÍ˜œ˜Î›Ô‹ÍNKÍËÌ“M“ÍœšÜØ–^‘ÚÙÖZSÍ’š›‘]Ô[^MœÔÛ\ÖŒPSÝÚ˜MÒØ›œœÖS\ž–SX›”\ZÖYLLÌŠÓÔØ™Ì–™VÑ^TŽ[Ü’QÛ–œV•šYÔÒ™Ì›Q[›œ‘ÌP[’[ÞRÛÝYŒTÛÕPTÑXÞ›SRZSQR]^YÕ›MV^]U••Ö]’›ÜLUÚPÑ[ÚÍ\U›ÜVŽRÔÔš[ÍÞYMÊÜ^RÚ[ÍTž™N‘Þ’›
Ø˜”“XÞYUÕÑPU•˜PÍNÚQ”Ö™ÔUÔ›ÔL–šÐL^žLJËËÊÔ”[”U
Ý˜˜’ž•–LœÛ“UUNTœÖXY[ÙÖ™]X–™Û‘ÎQNL\SÙQÕU•U˜™X\Ž˜ŽZ“žVÒÓÞYÖ“Ñ’•šM”šÚTT[[ÛŒÒÑ]VULÓN“YÎÚ–LÐYÑXÚXÔ”•ÓÌXÞœT”ÜRŒVPLÕV›ÒÌÞTŒUÒVÕQUÝ[™ÒÛQØ’PÕMÖZ›L^ÜÝœQÖ’RP’PYœM’ÍÌÞRSÍSÞU˜Ó›PÒÚÔ”\MQRœÎQœÔQTÙUœ^[Ó“Û[™ÛÑ”ÕYRNMÝ•L–•ÝÔ’šSŒ›ÌÑÓÌXÌ]ž]ÎTYš\–”MZ\ÝÜLT]ÝTËÍ™ZœÙZTTØÑTœ’ÖLMšžžM’Ò‘SÔÑÑPÚÞ™ÎQÜÙÓ›“Ô™NQ•ÓŒÒššZŒÙÛ‘›–\Õ[PÓÛT“^˜ÕÜP‘Ó]•S”Î[ZUZ“U’LMQKÕYUL•›LÒZž\]YSRXÕÚÖ•ÙVŽL”Q•T”ÑLT[Û˜^KÙœÚ–RPR›KÕ›’”˜RU[Î[ÍÕQ”QV˜“ž›ÍœŒÔÔX[SÛÞYRÞ’˜ŒŒÕL]YY–ÕUŒP\T^][ÒÎXR™Ó›V‘ÕV˜‘šPVRÑÛÛÚÚ[ŒÛ]KÑRžÜŒ]Í’ÛÞ‘˜ÓU^YPT]“ÔÒÍÝ”LÒÊÕ‘RŒœSÌÑÍÍ‘Ô’U[ÝYÊÒÔ‘\TÓ“QÌJÓÐ“^]]ÜPÜZËÙ“™ÒU™•PŽÞÜœZÜQYžKÙ\Ì\LÞZUÕœšÜLÒÒPÎÑNUÖ–TËÜN™Ù[ÛÌTZPTœUM›Ò”UÙÞÐÝÝ]“Ñ–ÍÑ›QœTPœ››ØÐÎ\ÍSS]“MUÔ[XÍ^’ÖžXTVŽRM˜STNRÎ]Ý\’ÑÌÐL‘”ÒÊÜPR“ÛT“SÓš\\MU‘R›MPTÑœ”U–X–“žTÞ]–ÚÔÍÑš˜ÌÑ–•L›ÙÑÒšÖM˜^MÝÐSYMPZØ’ÎMÌ\œÕZV^XÔŒÒÕÚÛÌÑŽJÜÝÛÎ’LQžU]ÔÐR]š‘LŒ’Þ˜šZÐÌY‹Ó\•›Ô‹ÔÒÒÜŽPÌšV”˜ÞPPU[ÌÜÛ[^VRÐ“ÞT[•X”ÝZ•Ñ”ÍÖ›LØÙÚPÌÓ›ÛžSÓŒ™\ÔØÒžZÍ‹Ô[”SMÓšÖÖ›žš\ÓÓUÑŒœJÔ[›“RRš™V[ÑR\ÑRRTÞYÌÑÛZ‘™“UÑÍX›ÙŒÔ]Ö•šÒ›ÓšÕ–™ÙÒZ•™›ÌÑ–˜XQÝR“ÚÐ’Zœ’ÌšRÒU™ÜUØUV˜“ZžLJÑÖ“\ÙÌÌ™ÓÒSLL^PZTRŒ‘ZJÍŽ]ÌÝ›’Ú‹ÍœVLÍY‘–ŒVQLÐÍMUNÚ”Ì›ÌÛTLÖLÞÖŒÞžVÒ]›ZÜ\NMžXš•ZÕQMYŽMÍML^]Õ›™P‹ÒTKÑ–‹ÐS[\ÑR\ÛØŒÕÍ•ÒÝÝV\•ZJÕQØLZ\ÍšQÜØÞ“Ò[ÔœÌÌN]Ø\Þ\˜“[ÖÌž^PÐ[ÔYÌÙÙ”JËÑ™XÙœ––Œ’LŒXÕÔÝ[V]•šQÕR]PÛÔŽ™Ñ‘YÛXRZ•V•Ð“UZÝ‘’TÑÑÒÒU\ÞVKÓMQÓZÞS[”’œRZTT”ÌËÖZÐÞY™œÝ‹ÍÐÖŒ‹ËÚ\ZÝ[ØUPÑUNVZÝZ”ÞUTM^™ÑM˜ÔËÙÌ•ÎNØÎÙ™ËÝRŒÓÝ[ÑQSSTšRšØÜUÍ˜”ØÔ[ÞÞ^YÝžU›XTÛÍYÜ^“‘ÖQLœÒ]ÓÓ’Þ’‘˜MŒNÊÌÓP\R‘ÖÍ^‘–SÝ’›LQÛUÜÖ^^PM–L^ZÌSÕÔŒÞš\–LX”ÒTÝŽRXYŠËÑ]žX™JËÚÌšXŽRU›ZLXÕP^[\”•]‘ÝR”PÚ‹ÕS™”Q™•žšš‘]ÙŒÕÑ[Ì›žU™Ð••ÒZÛ‘ÌÓÌU’ÛÓ[ÒR˜\ÍÒY\ž™Ì[”šÍØMÓÓVZSÝ–V‘ÌœÚÑÞRÊÝÓÖJÐ•Q›Î[ÔUQÖYTÙ••ÒÛÍÊØ\•PžRLÑ•’Ü\ZÓÒQYšÜÍÜÜSÞPÒÝ˜NT‘[œ’ÜœÙL^S‘T^Uš]ÛMŠÖ^LYŒPQÒXÛT™”ÜÙÓÑUÛœÎZ™‹Þ[]™VTž•ÝÙ”NNXÓ\“ZÔNÞV[\PÍœÐžPÜÖUÒÓTÌÜMÌ^’ÊÛ–•ÛÒØVšPÒ”Íš”–’ÜÜ˜UŒšÛÍT^KÕ™šÞ™ÒÍÐ[–Œ^]]MÍÝËÓLÝÊÒ[ØUØœM••\SØ\ÝÝ™˜SVÛ”Ò‘QÎ^PÜ\Ö^’ÍŒÐL”–ZYÐÛÚZ’ÛUÙÍPŽÓ‘•P‘UÙÔ™žZQ–PÛÔÖVSPÛ•^YY–QRM›R•™ÒÐ›ŽMÑLÑ“–QœÕJÒ”ÕÞY^ÙžTÓ‘Ø–[ÓŒ–•UÎÐVUŒÒ™V•˜ÝSÚÜ‹ÍÛËÐÌÝŒ•™PÕZšÑÓQY[]TÔR^\UŒ^KÕŽP’ÚœQXZÔ“ŽNÜšÞ‘KÚS•R›SÓNUÚ“\MÐ]]Z[R”ÛœÚÔÌ\L’Ü‘ÔœÖ’•YÜ^œ›“”•˜\ÑSÜZL”›ÚM‘ZŒZ™’YQÚ[Ì
ÔÓV\P•PÙÕQQ›žNT•
ÌUÛ•QQZšNPÙÒ™ÝZMÍVZJÔÙ’Ðœ\•ZœÑQ\Ñ˜[ÝÜURÙ‘ŒXØÓÕ‘Ð–ÒP’PÑÎTÚ”ÛÚÛZÌÛMQŒUÕ›PTPUSUÒ’ÜÎÛÌÜÞ–XÔÙÝœ™ÝÜÕÔMœM–[™ÖP\SMMŒQ\\”’™ÙŒYTUV\“Í‘Õ]‘˜ÛÌV’\ÔRZÍLŒ‘[^Q]^•ÖSQØ\ÔØØÑT’T“T[˜ÐÖP\SXšLØÌÔLÖÖ‹ÎÒŒÍÚ’ÔN[ÕSÍ›LSZ•Õ”ÖTØR‘ZÌSMœÚÊÖ•Ö‘ÖL›Ó‘“•ž“ŠÐYÖ[QZÚŒQL›–Yž‘›ÍÖ˜›Ø\LØ\˜Ò‘”’“ŒÛ”ZÊÒLRÑÍ[ZÖ’”TÖ‘RRPœØÙÕRVœLZÞSXÖœ–““JÑ”]“ÜVÚŒšLÞÐÚ•S›ÛÚQÍNL”ÓZ˜ÚÛÒÝÕYÙUÛR[NVËÙ“–’Õ™Q\ÖP–[[™XY•ØPÌŒÞ’Þ‘ÑÛÛ‹ÜMž^SÚ’™\TXž–\LÝš‘MÓØÚ“•QYÙœ–Ö”šÞ‘žUÞÑÒR˜Z[]LÜ\YÔÎL–ž“‘”Ü\XËÑÖSNR›ÚØÒ•Ùš]KÐSžRÔÐTM™Íž›UR“[ÌÒØM”URUŒš^]ÑÒ›ÑÍÑÊÎ^XQTL“œMŽZLQž”Ø›˜žTXZ•ÝÝÒ•˜Í^ÓYØVŒÒÙKÑ™‘YÔÚTPUNRÖÚÌT”ÝÒ™š’ÚJÒ™•ÌÒRÒÕ›PÖ’^MÒY”ÑQÍÜÌZKÙYšQJÜ^‘^ÒÜÜ\Q›Ô“•™”ÞÙÞŒM\Õ[ÛžMØ™ÌÕ•QP“MÓØ•™˜]ÍŠÍ‹ÓÓ•YÌ[NQ‘RØ^Ò”“U“ŒÌ\ÚØPZL•œÙXŠÙR–\ÕÕ[ÐÌÑZœ[ÑÜ^œÍS]Œ”Ð“[’šTJÍËÝJÎKÓMÞVŒSÝÞÎQÖ’ÑÞ\[Ö–˜\[\˜ÜÛUSÔ•UÞ–S™ÍXŽLQ•[ŒUÕYÙÔPÎ˜YÓØVÜMÖ’ž™ËÙJÍÖ––ŠØRN[šš\MU[UÙ[Y“šÍV›–“ÐTÖš\–˜\ËËÐœœŒÌÓXXY””PŒØU•Ò’T’SÒÑ]P^P^[’ÍÌÚ”›–”ÒÕ‘‘ÜRR•JÙ\’T›ž’›]U\ÑXZ™RØUÓÔSÒÕ]•ŽÖ”ØÔÚÐÙËÕ˜X’UØŽÜ”YÌTÒÍSÖšLVZÙÑ[Vž“YÞœÌØ™œ^ËÍ\‹ÍÚUž˜Œ›JÚž^›œTÌ–™ÛZÕR\”UV–•“R––›]”TÖ’MÖ–ØŒÔÖžZ™Û[TŒÌT™R]Þ]TÙÖ^ØLÕRÑÎQ™ÕZÊÕYÝÙU˜ÚMYœY–]˜Ì–”JÝZ™ÖMÑ–[ÒÌT•^™XÜ”Ô]\ŠÚ‘\RÑÝÕZ”QÕ•ÝQ›ŒÐËÑ[LŒQ›’”Ô‹ÓTÍ•NŒÐZ–NSÝÊÝÚŒÛ^ŠÝÊÞ™Í’Ô\žÞŒ]MÒŽRXÓUÍRŒXœX‘‘™[]Óœ™ÜžPØÛšÓRÜLM\MÜ““’“ÙÞ•œÕÜUUÚYÖUÙ›UÓ‘\SJÔ™Ì”ÛÑÚRYÜÜÊØ]ÙJØÞ]Í‘YÐ‘ÖSÜÊÞV’]QYÙÍT’˜’–‹ÐžS‘ÐÕUULY]ÌS\ÑÌÛYVÚ]\‘Û^V“Tž‘™[’™ÒLÑUJÌ™ÙŠÕÓÐŒÚSRZTÓMÛÞ[ÍÛ[Œ”SÖÔŠÓVT“^Ú‘]M’˜›ÑÒÜÜÍ’ÜÚÕÞ]™•žZÓÖžŠÌU•T‘™‘PÎ]Û^RÕTZš™ÜÎMšŠÐ–’’Ø˜ŽÔœ™[XÝ‘›””ÌPœÕQMœYÍUšÐ“Y]ÜYÎV›XÙžKÍÛ™ÕY“
ÙÑÜÓ[‘MZÝ•Q’\Z™SœÛÌ[ÓÚÔÛ\œMÒRœ”“ÙY”XÐÚRŒ]ÔÙ–šÙSSÖ–‘’ÔMUPÛÕZÝÑÌS›ÓØ™\ÐTœËÝRšRXÙNUÝŒËÓÍœU[LÓP[ÝÌŒËÕÕÑ™ZÛÜUQQÛTÑÌ^›Ü™ØU•’›RÒ™ÔÕÐÙÛ•ÌLœYÒX^ÕÍ™Y\]“•ŠÕVÑ›XÐPM”ŒœÞ”\ÎLÝ˜ÞYš][
ÓŠÎVTÑRŒ•–ÑX^JÜÜ\Þ”ÛÖTÓžV“›œ›ÚŒØÐNÚ‘’ž•QŽRÎZZZ•Í’š\YžQ]šÌÜÔÎQÜ\^ØÖ’Ö˜[ÌÞLÑ‘Ý–‘ÑZØÜX’UŒÑÌ[Ò“MTŽ^ŠÓ›–YKÛšžÓ^PŒ“ÚÖ’šœÒÒÓ’^™ÍÒÞœ[ÕÙ^’YPÎRÞŠÕ]ÔVLÐZ\Ó–]ËÝUÜŠÔRÔRÖZÕ^ŽUMÚ]ÖKÒÑ–’ŽPÑS[[ÚZ’›[Ù’N^L–Ô•Ý‘’Í’MV”œ\ÓÝÑ[”VS•™ÚÝÌ˜‘LZÚÙÒ•MÙ”œÙÔ–YÛÐŽRÕœÎ•ÚŒQÝÑÚPÖU\
ÍÒÞQV˜ØÛN]Ù™ÊÍËÒžVNXMÚ“ÊÌVÎVÚÔ^^Y^MÑÑÑÝÞÌ\”ÝSÌÔ™ÔÙØ––MRœZÐ“KÌMVŒ™ÑM‘ÑÜÖU›^“MSÕXŒÖ•‘ÑÜÔVUÐ“ŽLÕUžNRPÐÒMÎPÒ–ZKÎLÞŠÛœÞ™PÐ’SZRÐ’X”ØÌÌ^ÊÞ•ZÕÓMY˜‹Þ–•RÜšÖY]ZLš\QÒZRS›ÝZ•ZYÌ]]ZÕŽ™•STN˜LSÓÙRS[Þ[L–
ØÙÜ’L‘ÙØ’ÜÚ™ÑŒ’ÖÕŒTŒÛ’ÚÜÕPNRÌ’ÓÞ›\ÔÙZUÌÛÛŒ]‘QÒÛTÜUÑÜTšÛÝÑUš•Ø™VU•ÌœRÖMÑVŒ^T•““\Ü›ÛRLÒÞÐ“MTÓ™”
ÌT›’‘žYÚÞÙ”\ÖZ˜ÒQŽJÔMÜ’š^šQÔXÝ™ÜÖÍP“Sœ[RÌœSUR–XÚTÜ–™ÞÍYZV™[]ÚQR“™–ž‹Í“”›–QMÍM”Ó\Ñ–”V[‘X]XÙÔR[ÛÚUÛÐNœUÑ–RÓŽQ^XMPÍ˜Œ^”ÙÝ^TRÞ^œÑNY–^QVYÚÛÑÍžNÍÌÌÔLÊÕÞXT[œÓVRU•JÑPTÚÕP“[ÔNœÍV“ŽUŠÌÖËÞT™ŒJÎXÌÒ‹Ù•V]RÕZPUNVÛÔU–œÛ‘ÖXÙÓKÔT”\U[•LÑU\•Y\[RšZËÚÍ’\ÍÊÕÛT•‘QÚ“Ì–V^ZÍŠÓTMœ”Ô\]ÐZÚÛÓ‘ÛÝVšŒÞ[‘PPŠÑÑ
Í™Ûž–ŒÍÍžÍÎYN
ÎÙÝQÍÕ‘XØ]’Ø‘RZÍXMTZRž’ZÑÌU]\^’ÒLÛRÒÑÚRU˜›ÛLXÕÎÔL“\NTšÚTÍÙQÓ•ÔÓÌSUZÔM
Ì””T]^Œ–“”Õ˜“’SXÞ^Õ–\ÒQ™\]TÙ][•”‹Ø”™[UPU•VÓ\ÜT]Û\Ò][ÝM˜ÍSÜÎQNSÜž“›ÌPÒÎ\YÜÓ]ÌQÛÞPšUP^Z]ŒYÍZÝVPžMÑ›š•žœLÚR“šÑÒQÍÕY‘ÑŽRLUZS\Ó[RLÚ˜Õ›T”Þ^œÕËØÝ›œ–‹ÍÕMÛÊÎššŠÒŠÍVÞYÍÙÞ”›’ÚÛÑÙ]ÒÊÛÞ™XœTVÒ”ÛQÎÛSÙÒYJÒ”ÌšM\Ø]™ÐÍÖ’ÝÞÛUÝ“›QÑ\ŠÕU‹ÞM’^\œÕÚËÛ‘[ÍMš–QÌŒ[ZÒ“]]”Ô\ÖLšŒŒŒ•Ü›Ô›ÍM’›VÙÙR•ZØQÙÖQ“›SŒMMUÐ^ÐVKØL–]ÒÒÍÓ^MÐ•]ÚSNUŒÊÜÍÌMNKÍÙžZÕJÙžQ[•TÑÍSQTPP””Õ\ÑÔÑÓ‘LÑ™ËÕN“XŒ–XMÐÕPRÕT–žÒÊÍV[ÖÑÞÐMÞNNVÛÒP]”ÚXž“œÓRKÜKËÛLËÚ‹ÎÍ[]ÑMJÑ•NŒP^”LÚRÓÖÍ‘U”ØM‘ŒRJÓQZÔM[ŒÑÜ]Q‘ÚÝÌLÚ‘ÓÙšŒÓ‹ÔœMÒŠÙÐšÕÍÜÙÕT›ÞÚ“\UŽTÐÐŒ”[MÕ••Y“Û•V’^X”L“SS’ÍÕS™T]\LÕš–]‘•\YÚŒ^ž’
Õ\ÙÜŽÙ™ÑØÞœ“™ZÓÔÔÔMÖRØ‹ÞY’ÚM•Ì[ÜPÛ
ÜÖ“ÒÜ›S˜˜SR^›Í\S‘[ÛNØ[ž^S\]•ÜÚXXSRÌÖšÝSŒ‘ÓYÛMÙ•ÛVÙ™‘QÐŒZŽÕ˜Ì^Ü]Z’
ÝÙYžÑ‘ÖUMSM“‘›ÖÔÞZœŽ[ST˜P“V”Í“•ÑY‘\LV›ÑZÍÖ–KÍQÛ[V‘›V]V‘ÝÝRZVUœÝ“L]ÒVZV^–JÕQ“TÌ\•TS\“”ØÕÐŒ^–R[‘‘ÓšÐ›ÙÜÕŒKÐR“UÚÓœZL”–ÛØY•ŒÑJÚ
Öœ™URÐ]]‘Ø›XUÓV›VPP’PRUÐËÔ•ÍTÑÖ[Ý•ÕMŒ“ÙÐRÚPÕÖNKÙ]Ó™ÍZÔLZZÒNNRÚZÞØÖ•‘ŒÕU•”ÚÜÒ”ÜKÐ˜šÚY]P˜SŒRÙÝV’Ý˜X[ÖžZ‹Í‘UÛ’ÓØÌR[Ø’QšLÖZMMÕÍ“ŽÝLZÑ“œ˜PÛTœ[\‘JÜJÛ]••UUTYÎPQX“^žŒ””“
Ó^LMÒJÒ‘]ÙPØšÓÖšSSU–•šÛZZMÑVUÚLTR”‹Ô™Ù[XÔZØ\šŒN]ÜÓTÔØS[‘šXÔÕÕLLÙ^ÛVM^ŽœÔ“ÑÕQÙÊÔÌžÖRÚŽQÕ›ÚØYNÕTQ“ÐQLØÖ“ŠÝ™M‹ÚÔÜTKÍÑ›PÖV]”TYU’•œÑRVP“ÔÜ–LM‘ZRÜS›ËÓÜŒ‘SšÔÛÔKÓœÕUŠÔØÔ›ÙZÕ™QÛÊÕšQZ[ÑQZÕ[Y™›ÚÔÎ]ÖUØÚÑÕ’›]œ“Ü^›ŒV’ÓÚ”Y^ŽU[ÝÒZ”M\Œ“]Ñ’ZÙLÙ™\›LXÊÙ
ÝYÞšXÌÔ“ŒV]’XÒV”Ñ“‘ÛÔ™
Í™RU”˜–žP›Ú’T˜•–ŽÕQNR^SŒÑS“ÙVÐYÐ\ÍT\ÒŠÑÓÍÜÊÔ™XÑÚT]ÜÕZQœÛÒ\VŒYÞRS”“ÚŠÍU[
ÑÑ]ÓN™KÔÕYÚ›ÝXLRTSVSÜÌTÝÙ˜ÒM[SJÛMP–LÜÕ“ÕMÕÚLÛÕZLËÖ–Ô™‹ÜŒ‘SRØÚÑÑžT]ŽL˜ÑÕ]šÑŒ]\XÛ””ÓŒTÕØÛÙÍUËËÔ[PNQÎÓ‘ØP›PšÙY”ÌŠÍÍÔYZ^M[–YMKÕÎ“”UÓ[ÛRÙT‘MÍL–LÎZœ]“ÊÒSÞ[ËÛ’KÍKÜZÔMÙVQÖÌPÎ“ÔÖPÚ•S•˜^ÕÓ\TXÐ‘“ÞUÙÞL’ÖZ›RÚLžUŽÔÝÔ›•ZUÜU”“žV”œÞ^’›ÓÔ”ÎMŒ“Õ•ÛÊÖ™’QSSÞVœRÓÐ\ÒP[R™ÔÖœœL™T^Î”ÒÝYŠÓÑØ’™™ÔZRšÐ\Ú”XTYÝ“QšÒÞTQšÓ›ÜPÝTY˜œÞTÍ’˜\šM\]”ÕœP›ØÓYÞR–JÖšÜÌÔ[™]ÑQ\LÔÖšMÝÑ•–X]’ÐšVZØ[ÛR•XLT˜œR\“œ”X”•P\•\TR™ØÛXÙÚRÌMYXÓ‘ÎKÜZJÕÕM]ÊÔÚZ‘•XŽÎQÎ\œPÙÒXSÝY]“”ÜTZ™YMŒÞV‘Ì^Ò›M˜]˜”XVŒ‘NÙRŽ\ØM•–MT\”\ÐÐ[MÑ‹ÌÖžMÊÝYYYž™–ÎKÍR™”š^NUÌ’ÍSYÚR]JÝšž‘’œÚMLLÔ]MŽ’ÙV™šL\Þ]˜ÝVU^ÝÍ\MÛØŒU[URZÓYÛÚZ›Ìš\ÜNÖZZÐSÐÔÝPŠÙšRž›LQÕZÑšÝšÞQ’Ô]šÑÜÐUZKÕ[ÜSŒ•––ÑœÐ˜Œ•TÕÑ”S™žUS˜™Už˜SÚUÒš[ÛÞ’YSœœÍÐRÍN^™V‘ŒZKÜMÔÍÛ‹Ü”‘MÑ’›ÖŒV•“˜Y›Ü[ŽXJØŽ[Ü”ÐŒž•ZLQX\žžÝURØY]Q\PÐRQÐTŒÕœÙNJÚMÛÕ™]\\“YQJÔ•ÒÖ\[[UÝÖ[Ì“ÚÒŠÐÒÖÕ•T‘Vš”RTY™UMÒPŠÎ[N[Ø•\U˜Þ™ÓÍš”[ÜTU[šRRÖ›œ•”TSR‘RÓÑÌ“š“›‘Ó•[ÛMP–Z›ÚT™XœÌšÒ“[ÝžR›PPÜÙ“ÙÐPR”QQ[Þ™ÜÕÓÜ‹Ò‹ÔPŽŒÒ“’“[L’SRÔŽRŽMÛÚ
ØZP›QžÞZš”M›[Ù]›’žY]QÌMœÔ^ÖœÓÌUZ]”L[U‘XÜYVÖ’ÞRQX‘UÚœ]Rš]ÒšÓÔš•‹ÓÕKÍLZSœUÕÔPYÞšÛ‘P›‹Ñ’[VTQS•˜Ó‹ÐÔLZÐQÌRQNX–\ÙLX›^ÙÙQ\’ÐR›R”–JÛ\“›SœÛ^ÌÞSŽ˜LY”Õ–X•–
ÙÞRRYÑT^UÍ–žÔ\
ÍPÛŽ\ÒPY“P^
Ö“šÕ\Z‘ÜØÛÎÜLRQÙÔ\S–‘ÎZVYÒ•“œ\ÌÖTÕSÐQžPXÔVYšžÌÌœYšÙÙšÞKÙ”[LÙÛÔ™ÚŽÚÕYY˜ÔUÔM^‘ÑÑŒ’ÕœUXšØ^Q“‘RS”•ÑVÌÔX›Z›™”PM˜TÜŒ\Yš\U“ÑÛÜØ[XZPQšÖQÍÍQZ^SX›ÍÔÊÕ›žœËÝXŽL’T]^ÒSÛXÌšÚR[\]›N]™\œÓ”ÎQUQÝ‘]QSXÑN\LRYÞÝÐÝÙM‘[QUÜ•ÕÒŽMÌÕ“™ÚÌØQÔÜÊÝ\Y^˜ZZÌ“MUšœÜÕU•VŽTZžœÛUØÒXÜÛ]]›žSÔSÎ•ÖŽRŒM’ÔÓÍœUQ›Ò[š“\Ø˜ÒÞÝ\žVYšR“ÕÚÛ›šÎ[\’˜–“ÔÞM–UÜ‹ÜR•š
ÜÍÍ‘šSL’ÌÒZRÜLØÚŽZžÔTM”Õ˜Ú”ÕL›ÕŒÞ™™ÔNÙUÚ˜NXX^QUZÊÜ”\^YŒÝ[Q[ŒËÎR[MÝ›ÌÓÌM‘Í^Œ”ÎVQZ’‘–ššUÕÒÛÝ•ZÑ•‘T›‘ÙUU–PÌšZÕLÚUPž•SÒ›MU–“SYÝSÛSÎL‘š˜UŽMPÎ•‘^Ö]VVZ”ËÖœ›NÔZ”KÔŒQÍ’ÑX]ÑSšÒ]ÝÜYÍÝœÜSœ˜L\‘NQœÕš’ÚÔ”ÞSÚYTœM›RRMšÌÔ–›ÍRQM˜ÙR›M[Ü–“ÐÜ’ÍR
ÔÜ’VTšKÖ’T˜‘SÙŠÌX™ÍNS”X]ÞN\’Ü[^”P\ÔÌ^’Ì•
ÊËÕY‹ÙLÛS[Ûž˜šÔÕ“Í™žÜN\‘RšYÍÜ–™M[ÛÌ
ÜœYÓŒŒUÛ‹ØÒ‹ÝÔÜ]“ÌÓ›ÌLÌÑ\˜Û™ÌSMÚÛ›ÖÕV•ÑÞ•Q[YœÌÜ•ÍQÍ’“’ÎRÌ‘YJÔ‘ZÑQÍ•ULÞ’ÕÝ][\‘[L›ÐŒÛÔÙÌXœÚËÐU’šMÒ™LLšTLZÌX’ÝÓ››’Ü‹Ô•Û‘‹Ùž•ÙMÍÍÌ’SÑYLÕÙÝÓÕ“ÝÖŒ^–Ú›ÜÒÞ“ŒÒ™ÜR\\“ŒU\Õ]ÜÑÕÙ’Þ™Ø\]™Ü›Þ^•ÜÒ\šÑÝ•RTU•UŠÌSŒÛÖ™ÛÕÕÕÓUÝ]M››ÜÖ\]ÖŒQYTYÍ–•›TY›ÐN\ž™™ÙQ•ŽS’ÑšÔ™–NÜŒ’MÌ^^žÎÖ‘›Z–\•‹ÓÕ™ÜÑ›Ù\ÍÔšœÛZŒ•”VšÞYÚšÌÜXšZ^ÚÛÍŒœ”ŠÒ•ÎRZ‹ËÞ•’‹Î“^^œ”\Ž[˜’š›šÞZØÌMNÖ”Ü]’\LŽ“ŒZÑ•]ÞP˜[ÖS]Ú[Õ‘”\[••ÓZZXÔ”ØÖVQ™žTœØU\VS›SÜÞžŒ”Ñ\‘Ú”U’•ÜÜ™›Ž\ÊÐR]ÌVŒ]Ö”Ù“ÔUQÍXSÑÌÍÒTÜ™SP•NÝžÖ”œPÜšP‘[XRLÑÖ‘[ØÌÚ\ÍV›ÙVžÍ’Ù
Ý™LKÙ™–TM™ŽQ‘ËÙ–
Þ–““›ØŒÚMŽ[TÒZRÜLš]Ô]Ý–˜ÌRL\ÌÍœTÔSKÍ˜’Ìž’]‘ÛÞÔÛÎšØÍ”^\Ñš^ŽÜZœÖ‘ÓRZUPŒ•ŒÞÝŠÓÍUT”LÜV˜‘\\™ÔRÙÔÔÔZ‘R›‘Ú•œ™Q˜]Ì‘Ú[’ÕÙP’[‘TšZÒYÙ]KÓÚ\ÚÌÛÙ’ž‘]•NUTž“ÜZÕ™N’SÑÝÖ’Ò’[ÖNŽVPÐœÜÍS^”™›˜ÝU\œ˜ÚœœÙ\ÕV‘ÒLš•[œÐ^›TÖR\ŒRX’›SÍÔŽVš“JÌLZÌÙ•RÑS”•ÕR‘ÎXNÙÑ™›QØ•ÛÜZŽN’VZ˜]‘JÍ]™žÐ•^U‘\Sœ™[œ\ÝSU‘Q•”TŒP™“P–MØÓÛ˜œÙËÕMž˜“žÐM˜X–^™ÑžUM–[RÓÝ^M›ÜU™œX]š•SL–šœÌTËÕZUÌÑŒ’MQÕÊÝÜ\RÊÑÜLZQZQš•ÌÓÚ\“Ü•Ð™Ø\X•ÕÕÊÎTÝ™TÑÊÝV‹ÍUYTÑ]ÔÓSÝœÐ”^JÚÛÊÓÍÞ›“Ò•ŠÍMSÒ™MÕPRÚT[ÜÚP\œÜY•“›[RQÜVYØYÍKÍU‘•ÍRÛÒN’Úž”ÛJÜUÛŒ˜˜UÓÚLÝTÞPP’“Ú]^TØQY^šÎ[Y\œL‘]^•X•ÙU‘ÒU\XSŽ\“QPLVMžR•ÒQž•RÒÓ’UYXÚÚÒ‘Œ’ÖXÕ’‘S›M”[NM˜™XV‹ÑÙRÝ•Óž“^Ö”‘LZÓ–\RÍ[™ÐMÞ\YPŒPVŒ•V^]L–MVP‘›^ÜÌLM™™žŠÛ›ÍÓ[ÓÝS’ÛÑÑÜ[ÔŽLUž’]ŽX“XMYÒÒJÔ“Ó•ž•š’TÑ[›ÓœÖŠÑSRŠÑ–šÌÞžX‹ÜÝ˜SÎUÒ™ÐYÓÐšœžÊÚ˜SÜ•VYŽ–ËËØ]•Ü™[LM]YX•ÍÒŒÐÙÚÎ[’™ÝÌÜš
ÜMœZÖÕ
ÐÚÒŒÑPžXÐZÍ[]ÖQVLVŽUŽÜMP‘ÌLVY^™NYLÌÛÌÌÝ™™‘ŽVL˜™ÓPÔÍ›”ÐXØ‘\ŽU–ÝÖ’Z^•Í“ÚÜÐ™Û™XÔUÙ˜ÛžÞUZ›P\ÍšTV[ÖQJÓšÖ–ŠÍŽM“TÑšUžYÎ^™ÒÕÛUÚ”‹ÔVSMÞÛPÕ•SšSZVÝXTZV[U™ž’ÙLÝœ”‘ÚÜQ‘Ž‘œØŒÙYSÌ^LœLŒÌÝQ[[LM•Z›”Ö˜QÐ“ZR™™ÚNÍ\˜ÚRÙÔQŒ”ÛÞÕ™ÖXÙÕPL•Œ[L”ÌX’™–X
Ö•UÊËÜÛ˜”Ü^ÌÎTÔšQ‘Ñ]ÑÚ™ÛØÔSXÛUXÖJÙÎSTÔNÕMœÜœQÌ‹ÊÙNKÍž•ÌTËÛ“–Ü’Ô“ÍÚœ™ÎPØÙYÞTÑÞ’ÔÝ‘UYÙ]•ÌÎZV]ÙYÍ‘‘ÐžYXY›VUQŒ\XLV[”ÚÌQ’TÚ^U‹Ò]–‘ÔšŒÓ
ÛÖ’ÔÊÕU•™ÔUÖ•’–ÒYÎÞ™ÞÑÝ]]ž›–ÔÛšT–ÙšM•M[ŠÕ
ÑL”PÙÝ]ÌÌ•Ì‘Œ\TÛRÕÑQÒœUÜ’’šÛLÜ\Tž‘˜˜“ÎR[Í“•“Q^•^Œš˜ÖQÝST“XÜZXÖMYVQÔZ‘ÔÌÑZUÕÖUV^˜ÌZ]ŒÕÜ^R[•žQ“\\Þ“–‘“ÓœUSžÒ™ÓÖPÞ˜JÔQÕ›[UŒÍÒ”ÖQÍ[Y\’ÞQ‘Þ™šUšMÕSÚTÛPÝ›ØÐÜ\XšØÜ”Z“S”ÌœQÒS”™NRPPÖSÑÐLž™•ÎMÚ–ž™‹Í›šMÌšUYJÍÔZÖUZÜÑÝ\ÌZÊÓÌœÜÖŒ][œÝUQ^UœŠÓœ˜‘•ŒPÌ•ÙKÖV“[V–SUÜSœš
Ð”›TÑS‹ÞP˜UZNZSØ“\ÚXÍPSÚÜÒÕÓÙÍŽR•šPžX‘ž˜’•”TÚVŒÐÚJÜ]U‘Ù“^“Þ[ÜÖÙ[V\Þ›S]”ÔZÕJÚ’ÜÔLÝÓT”›Ô’ÒÞ]\“ÚÎMÕL[ÑSÛÓYÒLÒ“˜”ÑZ•Ø”ØÓÖ“ÛÞ\[Ö\’ÞPNRÝNPÒœššÕšQ\ÒTTÔ‘ÓZšÞ^‘ÎÎ]ÌÝ\T]ŒÔ]RLÛÜž‘•ÍÜ[NœMR–YÐÒ‘UÐTPŽÑÔŽÙžJÝŠÔÌQÒ^ZXY”QT™RÑÌT‘™ÖQÜœM˜ÔÜÍšÚÎØ–SYUYŒJÓ’V]™ÔÐPÕšT•ÒÌ›Þ[•ÔÓV\Z]Í”P–LMLNTÛœ‘Ð‘SÜØ›ÚSÜÔËÊÓLÐRP\ÑÒVZ’[XLS’P]ÑSÜŽJÔÛ™\M™ÚŠÌLÌŒVYLXÌÒÒ••ÕÙÐšMÐÖ˜ÌUVšPLSÙ‘SÜ
ÑÛÞUÌQš””Ðž\ÙÙÍ“JÞ™Q–›ÛÓŠØÌÝ›JÙ^™PØLST“T‘QXÚV–Íœ\Ú‘Þ[\Ì”••ÜÙM
ÓSLUØÜÌ˜™’ÓÓÓ™š^XÕ“VTÔÚ’ÍÞ’LÑŒ•V‹ÌRÕX“˜‘U“ØVMœ‘•ÚÑ•RÙž\šRÐTYÒ™Ì™˜ÔM”]
ÎÛŒ–^šÔVUÛ–ž‘RLVTUÌÓS][Œœ[[ËÐšÓÖ‘Ñ]Û›™Ö–^UÙÖ]ZZQ[RÖJÖÑ™™Œ™KÝÍ˜NJÐÓÑPÚS›NÑÓÕœÌÞ\ŠÍ[Œœ\ÌMÒ•Î]ÎMTRÛQÜÝØ[MŒV›^ÑSš]ÑSÖR”VXÖÚTJÐ•ÚÛÌTM™[ŒÓS’”ÍÔ”‘TR•ž
ÑYÒŽMÑ\KÕš”
Ð•ÜÞV”ÕÞ[X[Y\LM\]’•ÌLR
ØS‘ÙT–Í”ÚÕSRÐÑPšÛÑ^\\\›ÔŒTÑS^•œ”]ÒZÜ\[^•“[”TÊÝ“‘Ü
ØÛÓQXÚ•”VZRVMÍÒÍÓ”Ö‘U”M˜YÙ‘Í–œLÑššYJÛ^šŒR“ŒYØSÝQV“S›YXÞKÜZ’ÌZÐÖTÒŒ[–L^LÙ”›ÝS––šÒ›’Ú^]ÜÎP’Lš‘ÑžRJÜÓÝÓQ‘Ö›ÜœPšSÒšSÕPÔÔÒX‘›YYMÔÒ•^Ñ\ÝÔS\Ô›\ÍU”•Þ[–”˜SMŒ”••^•ÞQÚÕSRÝMÙšÞš“ØœŽUZÜ“ÎL“JÛ^›š^^MMËÕÝ[‘ÕV’ŽMZÛÜÜ•Í“[ÜÍÝYØÖJÑZÖ™NVVSÍÌ“ÜŒS˜SMYÍÔ•ZÓÍŒœXÓZM‘Ì\ZXJÖ›•NMÓžQLÔQØ^ŒËÍŽL“V“QTØY˜ÛØ\Ö–L–URŒY‘ŽP]UŽYZ•ÛØÕ‘VVLV›ÝLQ[ÓØÛ“MÒÜÎM\›
ËÛœM]’Ü‹ÌÌÙKÎM‘ÙYLÓÛ™QNL’ÞV\ÚZŽ’ÌÒÐÞQ™Í]ÓœÚ’ÖNMŠÛS™N^]KÎM‘ÔÛÜ\Ü’œÞÑ‘P’LÍNSÓ™SZR›Ñ”’^”Ò’Ñ]Ú™Ö™]ÙYUÛSÙÜ]’ÍÝ•‘•Ó”’•“’“^S\–ÕMÔÝVMMV^UZMLŒÐÕ•“ÙÎÛÙMÛ™ËÙ•YLœ˜ÊÎ
ØÖ™ŠÑ]“ÝYœÌÖÙ‘^‘Þ˜›–^šÐØÜ–œ’ÒÝL™™˜ÙÖ˜ÖYÖ“RRQÔY’Þ\ÓQØUÎVXVYÖ\“ÛÔ’Ô›ÖV”Ü™ÑÖ”ZÝZ”ÔL“™VKÚZÑ“ŽÑSÛ\JÔš”ÙQœP‘ÓÞ™Yš˜’œMšMÎRÚ“šÙRRÔ›ÛXZ\TTÝ›]QŠÒ[[ZX˜•žTÝÐÑ[T“M™Ò›Ö•™\U“M›ÜÐ›\Û’–šŽ‘
ÓM\JÒY›M]QÑš›Q••”Õ•[›XJÜYÑ›ÕRLÒ–œÑÔ\LÓ]XSSÛ”PŒÌÝÚÕÛœœžœËÎLÝZÙÌÌÌ•Ì\ŒQLQT‘Z”ÛZ“’UT[’Ü[œ’Vœ[“ÔÚØÕÚ’NYNÕ”MÑÛÐÌ”›ÞÒÖ]SZ“ÕÍœMšØÊÍZTÓËÐÒP˜ÒRPN\ŒRUZZžÞRœQÔYJÑM“ÐXXŒX\ÒÔÜššÑÕ^[ÚŽÑ\[Ó\’ÜŽZÒY“QØÌQÔ™[S]ÓÞ”^\ÚXÞœ“Ô]™”Î^–Œ]Ó’•T‘ZÜ”‘ÚYžSMËÓ‹ÎZ]XÞQÔÒÚQÚ˜SUMŽ^”][ÐY][Qœ–Ñ\”›Ì\ÜQ˜QžMÚ^V”ÒUØ‘”“ÕÜ’Ù”]Ó›S“Ò“ÜÞŒÚœ‘^YŠÚ‹ÎS”ÓQÌMÓRRJËÚ]UÍÕÛ^“KÕ•ÜMMÞ•NTžRT”Ù^P‹ÔP”UÌY›ÌÞŒÓ‘›NMQœÞšÛRËÐJÙÛQÔ”\›ØU™ÙÒÐ–šÓ“Q’ÌÙÔQMŒPLÞT^š[šÔ’ÍUL–YÕ•˜\ÒÑÍÐÜ–™Ý”•ZP“ÕKÎ›šXXŽÎËÙÐÜÙ[šÐ‘MÓÐ’M’ÒTÓÝÕ\‘˜ÛšULÜM‘Ü[›˜Ñ^PÜ\“\“^ŒZMŒÐ\ÔÔ–ŒšÕ›ÒÙL‘“šš“ÜššÙ“˜Û\SZ]Y–V‘R˜N–šQ›XÍÞÒZÚ•Ô›ÎUÞ‘ÖÚÚ”TÍ›ŽYÚÓ[[\’Ì\ŒÊÌKÚV^V•ZUÔ^ZÕÞÜÔŒ““[Ž
Ö^ZUÞYVKÔÍMŒÜ”•]Û“ÓŒ]LØ™ÑÞLQÌ[^LU˜ÐÖTÌS’ÕZÚÌÝQV›œ›ŒÚŽŽ›PÒŠÌYMSÜŒÕÌœ“M]–ÙÖ^JÚÛÙÝ‹Õ]–KÐŒœRZÛ\ÕYJÑQ^XÝÔÑ]Ö“Øž^™šMÙÑ’MÚ”XÔPÚÒYÖS–••–RQ’LÕ’Ðž‘RÜÎLZØJÌLÛÐ’–Z\œšQU”L–Tœ˜NTšNžVšÊÛ’\XÝPNU’›ÍÚ‘Û“UØ^’™•ÐPÛ]ÎQÙÝœ[ZØYÙT’S]ÚØÍÝVPY™LÞŽ‹ËÝÍJÜÍ•U›TQ]”ÖÜZQ–UTÕ˜“‘ÜTœU–ÝLÙÔŒ”ÐÔ”•Ì‘’’ÛÞÓSÙV™ÖPRÔ›ÚœZKÛÝ[–““ÞY™ÌÞYÚÑËÑUP˜[ÝÚšÚLÑMÛXS˜Òš™šM\RSœSV]ÍœÓÑÔN–\ÑÕÜZÎÞ‘^šS[˜ÛŽJÓ˜•S–^•Y“žR“˜]VQ•Ò›ÌŠÜTÒÒÌ^™ÔÓQÝÎ˜‘[RÜ]\ÜÓ”Íœ’ÞŒUYÕ”RÛÞ]ŽŽLÜ]Õ–YVRÑÑ]ÓŒÑJËÐÓÎLÞšÌÛ˜Í\”YUZZ[^PÙŒÓÝ\Ø™^”œLÖLÝÚ•Ü“šÓÑÔ]ÌžMX”š”–•PÚ›N\ÍÑÍ›QÝ]]Rœ]‘ÙUQšÜMÔÛXPžÚ•Ü[[T]ŒÚœÚÓTŒŽÍœSU\ÔÞÔÓœPÚ^““ÍÔÍ™‘QÐ]ÑP’Ú’Œ›YÚÊÓÐÙ™KÓÓ™‹Ó‹ËÜ”Œ˜™™ÔÕUUÕžTŒ‘Û”’R˜Z[Õ–U\Ñ^VSœÕ–KÕLÎ\Ú–ÖØÛ[YÛ•TTYÑ›ÚÞ’ÔÌVKÎÑ”™–ž–ÍÎ˜ÝÜÌÓ]UÔÐœ˜[”ÙÖ’P[QQ’LMÑTQ^KÞU[MÌËÐÍ–Ý•ÎKÌÙÔÒMŽMÚÚRÑžZYS•ÓÜ”ÚÌ[XÑ“‘ÕJÚ“]’^™ŒÚ[ÞSÊÙÜÜY™ÒYÑÙM[–[Uœ’NSÕLTR[PSœÓ›ÔLSÑMŒØÖ’™
ÑšÍÙXÎKÙ\ÕSÌQ\^X˜’ÊÝŒSÍžU\“Ú[\PÎRÕŒNVÖ•“œ˜YRMŒ•ÐÐTVPN’’‘ÝNœZRŠÑ“LŒNSX‘ÒY•]šŒ‘Ý“ÍÝ“MÜS“ž–R]Ñ\Ð\UÝMÖY\]™ÍÞ[ÖL›Ü‘Íœ›\•ÒÕSÔÒÙÛPRÕ”œÛÌ”PSÙÌ“U[›Y”œÙÜTÒTÓÕZÎS\YTÍœTQZÚ\UÙQÐ–VRSØZÌ
ÕÓÖJÓÍ“Û][’ÖUZÕ”LŽÖ‹Û]ÚÊÎ[Õ‘‘”ÍšUœ“KÒÕÚÜ]LŒÌÚ[JÞŽÍÓÔ”X‘ËÓ\SR^PPZšÔS™ŒÛ^™Í\JÔœLÚš’]ŒÙSœÜÌQ™ÖÕÜZÞYÛV‘ÛÌÛšÙ™Uš’ÍÓ’›ØL•›Œ”Ú’ÐNLQÖ^Œ–•žP•[LœZÚMØÐ”Q^ÌÓ•L]Œ’S›\›Ñ\PÍœPÚ›Ì‘[PQRœÖ“Ú›QÍNNJÒœSÜÝ][‘œ™MØÑÊÐM•PÝXŒSÙ›Ú›NÍMÍšÍÓ˜ŒÚNY‹ÐÞÚVTÐÒS\[Ø“–TÔ™L]•TS‘VPÐÒ™Ð[Ô™T”ÕÚYX”šÒSÌ‘\UÖ–SVZXRžRÜÝÌYÓ\Ü˜”RPSYS“ÕÌÙš[ŒÍËÖÔ•QZÒ\˜ÓTÙÐR]‘™Ö•S\ÕÖX›ž”ÔÍ–NT›šÓ™MLZ\T‹ÐÐÒ^YŒ^™]MÍËÑžžZTYRQRSÔTÚS’\˜Ù›^•”S”\^ÐÝ˜^UÕŒJÑV˜\SZÑR\Ý‘]VT^[MÒZUÕP^^ŽŒ’ÍX”ÍÙM^‹Ô‹ÙŒØ\ËÞXÒU”ÑÞP›Q\QJÒRÛÌQQ›ZYÚ”^“Ô]ÕZNS•VXTÖ\[•™ÓÍØRRÎR••“ÛM‘Ü\RÜ]ÛÜRN\ÕÕÌLÕÖV’ÖLÛ™›ÙÔÜRÌËÝ”UŽPšÚ‹ÍR^”Ñ’šTTTØQLU›ÒSMUMÎQœ›ÒÙ™’•ÙÍØ˜UKÛV”œšÒÛRŽPš”ÝÐ™“YÔ•Ü™LÛLÔ–S›Þ]Ü]œU›ŒÚ˜ÒTZÚTNM\Ñ’‹Ð\œœYY›ÖMÚPJÖYYÞX”ØÌ™ÙÖ›ÙL›ÜÝÝÙËÔ”›Û\S\M\ÒZ[Ý\UMÔN]Ô[Y‘›žY[™™šÓ^XÔZÔÐQSPÔÝÖRÚŒS]‘Œ’PT[šÝUÖ•LÑÖZÛÌšÛTQšÌUŒM‘NN\ÕŽÝ‘N”–YMVTÞXÕ’L”•Ö˜QËÝLN’YØ™YL\‘‘V‘QQ^‘PŽ]Íœ’M‹ÚLMÌ”Q
ÓœÍT•Õ›ÓQPÔQÐÔ\ÖœL’T”LRÌÌ\PØX‘Ó^›‹ÜÑRMPœPŽÚÑž–ŠÒ\ŽŒZœSQÔ^œšT™Ð•ÚÎYÝM“ÖZËÔMS’U\Ô[ÞNŒRÒš“ØYœÓÙS[“”ÛÝSÜS•XÑ^T”ÙžRš–ŠÙÚ“ÙÖLÙÌX“Þ^ÔS[SYTÍ]”’Ô^UQŒš“ÔZ‘ÛÑ[ÙÜ˜ÌÐ“ŒÚÕ^ŒPÎ[’LÕÒÜÚŽYT“Ö\”ÕÒÕŽLš‘P[YÙV˜“ÜJÎRÕ™“Õ›[ÜÒÛ‘X“ŒYŒ]ÚZ^L[ÜQ–‹ÎœYÌUUÒšÑ“ÊÜ™PYLÚ•–QœZž‘VYÔT’™ÒŒÜTÖžžŒž“\Ý“Õ˜ÙÞÐÙ‘ž›‘LS›ÍŽÎPÚ]QYÖ]“ËÔ–VJÜNU^PÔXÕ‘
ØZÝSKÚXZ›^Œ–‘ÝL™^’QYž˜ÖÜšÔ™YTÌËÕTœ’ÍÛÕ‘•ÓÌQSUÜ[\N[NSKØÕ’ÖPÔŽ[ÌT•YŒUØSQÝSØ•ÌšQœÒ‘Ž^MÔPÐÊÛŽ[\•KÎÕÝ™PÑÞžYÝYÞPÞÔÌž’ÌPÌLV”TÞÒRPRÔV^™YœÍÙš‹Î[]‹ÔÎŒ›KËÖ›–Ûž˜^’ž^\Ü•œŒØ–^ž[ÙÓÓ•Œ‘Ø]™M[‘Ø™ØÙÒš™S‹ÌÕ˜[\ÝL––‘^UURRÕ“ÒŒYÐ[TÝÌQ”RÒÓZšÚØÕŽ\ÕÕ–ŠÝœœNLÜS•JÍš•KÎ\”VÊÖÊÛN’“ØœÞ“^V–˜LŒUÖ’‘ž–SÛ›PÛQVŽT–•ÔÛ‹ÌÙÔÕÜ[ZQÙLUŒÐUÙLU“ZZÖ•ÛÜPÑ[•œMÔR]ØX”YÙÍ›ØR^XZ[“RÒ\ÑÝÎL“Ô˜’–M]’ÍÐQÕ›V•
ÌÑNÑTZÊÒ•’Ø•ÜS‘ÕžVUÐÝÚUÛÒÛÔP™ŒœÛUŒ]STÌSÙÜQLÙ\LNVRØÌXMÝ]›Z˜–“ÕÔÑÌÔ•TTÍ‹Ú^–SÒJÒMJÊÑœPŒœÍŽ[ŒÓ^›[ÐÛÙ\XÌÝÛŠÔLÒÕÚ^MØŽMÛœÙ™\Ù’NKÍ\˜ZÔÚ]”ÓØÔÞ™ÓŒÍQŒ]Ö[ÝÛÛÞ”UÙÖœÔUÝÒX™T•VšÙÍœŽÓZL›’S[RÝ•U™[Þ˜[ÝÒ‘ZŒX[ÙÐÙÝ‹Ô‘Ù•Þ\œZU“MÖYTSŒÕÛÝ[“QTš]LŒYÞÒÜÒž\Þ]MÔžØU›JÜÔÖR‘žŽR‘[ž˜ÓÔÞÚ]]YLLLÝÒ”RÙÜQMP›PÐQÒQÔZ“UÓŒÙY™\\‹ÊÛÞ›TÝÐTTÕQÖUUÍÌ\]ŒŽP^QQÔž™šÞ™ÔÕ
Ú–™M›SÛÔ–URM\SœÎTœ“XS›ÙÜ[›Ì‘““R‹Ù’ÒÐÕN\”ŒÎÒ‘SÙLU][YÕÞ™TÊÝÚQÜ\MŽVPžšÓÊÞ›œ˜^Y˜ÖÌ]Ý™ÌXV•ÚX]PZYÒYÍ\UUXÌÒRÓœ“Œ”VYÕŒÐL
Ì™UPXŠÌQT›Ì[ÓÍ”ÜÝÝÖŒYRÊÞQÜQØL”ÓQ[Ì›ÚRYÖ“ÚÔRÓ^]ØÞ
ÎÛ]•šQX‘ÙÛÓRØ“Ö\RÍSØšÐÒ›’™œšœÖÎUŽÎZ^Ò˜Þ]ÚPÛÛYVÖ›ÑM›ÜX‘”ÚÑÍÜRUR]R”^ÔŒ\ØÔÓP]ZVÖ]RRÒ›\NKÒšŒÝQ”TÝÙÙšžÕÜV\\ÎTZ•]™S]ŽPQÓÕÔUQ”Ž]‘Ñ\TÜUÓÛŒØÎ[ÎRÊÖœ–L“]^Ž[Ì‘Vš”™ÜZžY
ÛÊÌLŽQ™ÐÓX–\ÛÜžœÕ]”VŒÊÛÐ˜Ô]Õ\Í”ÙÖS[]X[ÍQÐœ‘‘]“Z[ÖšÎY™”RÜÒÑR”TŒ•”ÓÓÚPÒQTÓM”ž’S™™MœÐÙÚPÒ–JÖTS–•ÚLUš“ÓŒ••›\\Ô˜TÒ•”ÝÕ^œKÝšZLœÚÚ‘ÒÚÑP[Ñ›ÕÍ]TÑ•Ö‘ÕN•‘LP”ÌTZ]‘XV‘YÔ’TJÚPZNMÚXJÍÐ•NJÊÕÞŒÍR’”ž‘VQ\ÜRSœ˜–’ÌRœU˜^]ÜØ˜^[ÞMŒÜÜ“MÕÓ\X•ÔÒÑØ’NURLÙVTÌ\˜XÕŒ‘XÖ\^•ÑÕŒ›šSXÜ“‘XZTT™[ÔLÜÞ™ÑKÑÓÌYÖ^MÜÌR\ØšÚ‹ÑRÑUTœ“”^ÎLÕÍ[Û˜Ž^ZÛÝ”ÔS]]T›Ó•X’SÜ”ÍŒSÓÚ’RÍÔSQÓÙU]URÓ
ÚœRÒ“ÒÑÙŒ\Û[ÒËØÖ‘‘™›ÝS˜\RRÛZÛ’•ÖŽQÔž’JÍLV•ÍšÜÎQšÕ–•šÓÖRØQÐR›X•”’Q™UUÌšV–š^X\LšY‘ZZÑ]ÓÑTØÚMKÝQÜ•ÍMÜSM^YYÙ[[SŽLUU–[^SLJÞ›XÑšV”QšT‘PZ”Ý^TÝZ’Ø\XÓÛ•ÊÔÒRÑÑZÛÌÔP[–SÚÌÔËÝÐÓÒØÍŒ]‘V™‘Vš”Ûš‹ÍXÞÐL™XÛÒÑÚÚLÜX›Ð^˜™ŽRL››Ñ]ÜTQ“Z“Ü˜žÑ“ÐÔÒš”\ÓÝÝž™ËÍÔPÍMMÍ[ÝNMÔÞS”[Õ˜‘Í›ÛTRÝÒP[QMÞMÝÍÙÌœÝ”ÔJËÎKÙŽM“ÒLL^URPÙÝÔUÛÛÑX]TÍ\™ÐÝZ–›”ÛSœÚXØÔÖœÜJÛ˜’Ò\QÔÓÍM]Í”ÐLž\\NPÕ’ŽÔ™Ô–Ò]\“•Ó–Ø]Ö“LÚSMÚPÒÕÐÙZPSÛÌÙZÞ›”ž‹ÊÌKÜ‹Ý•T’˜\Ùš’[MÜšS•™RS”ÍšÞR’Ô•NUÐÍÓÞNT’ÌLÒXÛP›Z”\TTÔŠØT\\MUÐ[ÒØ’‘ÕÌŒ‘™Ø“]”ÜÛY[QÌ”ËÍÑM’ÔÍÒÜÝ^NN“VZÜXÞ•LœÙ–^NÙP\ÕUÛÓ˜’ØŠÑ˜[“YÛÚœJÒPÓÐQš˜SœYÒ\YžŒÐšÕZ”“Ñ“ØÜ™‘˜[Sž^U–\Y^LÜŒ“ÐÚÚ”˜›ÛYÙY‹Í™RL[Qž[ZÐ™ÚÑÝÛÞ‘ÐÚQSÛËÙUÙ“XÒØURV“MMÒ\”\MRXZšÓŒÜÕÕ\Õž’T–“ÓÙZÌY‹ÎSKÙÓÔÚ”JËÎNRQÝŒÛŽ]ÍÜÕŒ^]ÚÐÐZ˜YÝVQ”MR”TÔ\TÍÒÒØVKÖ‘žž[š™ŒÔ”Õ’ÚÓÑ“YËÛÜØ\˜P•ÑZUÑ‘™Ü[ÖÜ™ÝYÍ^QY]ÑVYÍQÐÜXYŒÚU•ÔÌÓ•™Ý›RYZÐ’ÞR“œÓRÓžœ“”žS˜]’ZVœYŒÐT]”ŠÍšXÞJØ”›Ü‘LÙÖQTMŒÚÒ[[žŒÕZRÌ‘ÚSÙž˜›’”LËÛŽLÛLVQšRÌ“YÍÒš•NNÔŒYÌ]›XQ•Û”˜M˜ÕÖŒÕV“NU‘ÌVœËÕ]]XÚ[Ø]ÌÎš\ÜÝÐ[ÕÔœTšÙL”Ð’YY“TËÊÖLÛÕÌSžPÑ•M’Í’ÍØ]ÚÜQ‘XÕœÛS‘ÕXZÍ•ÚX’Ó‘ÖYYPÐYÜÐRÛÒS’ŒÐš™ÝÌ‹ÎÍJÎMÕÑ–[T\Í’SØ]Ý›ÐÊÕÝUŒÜÜÝ–‘^“ÞÖ‘X˜ŒÙÖ[ÓÝTÖŒÛ‘•S•R“Î]RÝ]ÝZÙÕLÖ‘ÍÐÔÑÒQL“PÚÎRZYY’ÎJÓÝŒÍNUSÔ‘ÌPR^VÔ“ÐQ“\ÕÍÍ[\RÖLËÐ™ÌP[Ö˜“L”ZQÐQ’ÚÕJÓVSÛ–“•ÌXÖš›Õ^PÎT˜\”RÙÌQœ[“QRÜ“T”TŒž•’\Ð]ÐÒPÐ‘Z›ŒXN[š‘ÖJÛTÔ•‹ÍYŽ˜ÙšËÛÙ‘ÛÝÙœÍœÐš]ÚšKÐØÛ™›ÕÐ›ÓÒžØÔžQÞM–‹Ú›–ŠÌ]P›ÑXXŒVLÍMZËÜÜÌœR[ÎXÍ•ŒKÙ•\Ú–›Ö˜ÝÛÚZRËÖ‘™ÔÝÍ^YÎœÙ•ŽVŽMQTYÐÕÒTS”ÞžXQÓÞY]TÛÌÐœ‘œ™ÎKÎQ˜ž›MØÒØTÞ[R–U’ÞRÚšSÙ–^ŠÎÒš›ÍÞŽRÒRØR”ÑÒÑÑY^”œÛTZ\ÔÖÔ•ÝØÑÓÞZÍÌR•[–YÔ–Ž]XUÝÍÞ“ÚQÛÔ‘Œ‹Ü–[‘]šÚœÐŒYZ‹ÒUXÖUÝRÖSÐÜ••žœ“š‘XP”‘Y’“UU•ÔQÙ]XV™ŒYN^ŽËÞVœÓ]UÒ[SÞTÕZSœÚœYUYÝÖ˜™šØ–Ñ“ÝÑÕÍÛYžLÒÕZÚØŒÔÜ^XÝ]Í]•ÐXœ]T‘]JÛQY’QÓY”ÌÜÝÛÒ–Ú[PXÓÎŒ]Œ•SÐKÙ”TXÚSÖ›PÎ^”ÌŒÜÖ’ÚÓÝžV““\ÕÜJÕ]Œœ˜ÕÕ˜’ZÜ›ÒZTš™MXŒNœœŽšMPŽZÙ’ÙMÝœŒ“žÜ˜ÞÑÒÒÚ–”›TQš•‘ÕKÝÑ‘ÑŒVYÝÔš\Õ‹Ì“Ô•“›“’Œ”PÐ\ÚT‘Ž
ÓÍKÔ
ÔKÍÊÓTÑ”˜›˜SUŽ“Ô”[Œ]œ›RV”[UÓXÕÞ›Ð•œ
ÑÎžSÑ•›Ô’TÐšÑÝQÙ”Ú\Ý”
ÞYÝ•Ó›œÚÔ”ØSÕÎPUœ[“V”UÐ\Ð››SSÎX”VŒ‘ÑTÌŽMÕ[M”M[’PÝUÞÓÚL\”SÝUMÌ’“ÖYÚ’ÙKÙ”ÌÒœ’šÔŽUØ‘˜Ñ[–V]ÜSPÚØ][ÓÜP“œÌšŠÒÓ–Ž]••V’ÔÙÕÝÚZMž“–P\RT’‘TZŠÙ–]ËÛÞ
ÍÍV›››‘žTRÔ“Ð”^SÖXÍT[Z]RTÍÞÐQVXÔ]ÝŠÛ–™™KÌÚ[‹ÌÛËÍÝÞ–MÍŒŒŒÞŽVTœMÐÐÑZQQMÞŒ˜ÜØTÜLUMQM“TÍ”ŒÖXÛšŠÕPLS”ÐÞ[^›™\^“]Î›S”[ÛPÖRRÜÒ›ZÐÒ[\ÑR•^\XÌZÖPÔVYÐÕY‘ŒËÓRJØÙ™™RRÜ”Í^ŠÒU]ÍÑÖÛ\ÑYZÍšÔ•NÚŽYÍKÚÛ›\“X›ÓX”ŒŽYÔTÙÜ^M˜ÙÝY•LÝÚ“ÙTÞ^ÑœQ˜ÞLËÌ\–ÐÓTQÓPšÜØÓ˜ŽM•P‘Ù]ÝTÓÕÓÙU›[M”ÍÍÜ›\ŽÕQšVTÑÕœšS“ÔYÒPTR‘ÍÛÓÜNÕZžQQœÚÒÖŒS”Ì”ÑÍÝUÌQœœX’ÓZMšRÕ•–LÝSÛ]Þ–Ùž[ÌÓ™UÞ˜ÙÖPÜRÒ’N’’“š^SV•X•R]™Í›–L[^Q˜XÝÚYŽ[ÜÞÔ’ŒšT˜ÒŽš•ž]ÌŠÎSÌÍÙÛÖÊÌS]”^’ÙœÕ‘QØÙÓÑV™X‘œÐÒ]”RQÝŽÍÔŽR“R]ÕÓM\ÔÜØÑ™RÕ”˜TÝÒ]ÐÛY•”Ì›RŽÚÚP•TYØ’L“ZÖ“ÙJÕM^RZ]ÔU]\T\™™™Ö\M•T›ÚÛÎ\KÔRSÓÚÜš‘U‘UØÞÐÙ]YY™MLLNLÛÕ™YÖ•ÝÒÌ]“TÝV‘ž[ÚP[™Ù•ÔÓPUÌLÎ[‹ÍY™“Ü““šÜÍÕ^[UQŒ][Z’–[ØÛS‘QÐX]VÝ””ÚVž^[ÓQR^ŒÌ‹ÙÐ]TÙTÕR”‘Íœ[››ÓÖ‘–•“ÌÒÞ›ÙUSÊÎPKÞ“YNLRYR\Sš’œPÖ[™ÔÛÑÛÑÝUÛZ]ŽLÚRÑ–‘RJÐSPÔ
Ó“ÓÖ\KÖ™šÌØÍÕØ‘RZ’ZQ\‘Ò]
ÜÖŽ[ÓR\ÎXœÛÜÔ^ŒÖ‘Z––XÖLœ’ÒÒ\Ñ˜[L]“ÞQÌVTTÚQPŠÜP\›–ŠÎ›\TÙ”Ó˜Ò–RÌÒ^ZÖœ‘[XT•ÛQÔSœ“’ÝÜÛV”ÓÕÜÛÚZ[ÒYÝÚŒV”[’˜ÚQ]ŒX’QTÙžT‘NRÝ”YÖ–TTÑÝÌœœÑÞÑÙ^ZÜ™ZÎSÒŠÕ[šV•ØÔ]ÙÞ“ÕÑX™”Øž•œžœÊÑMÍ‹ÐŒÝM^V\TPÑP]”QXÔ\•ÌŒÑ’ÞLÜ‘[RÔ˜ŒZ•ŒUÞ“”ŠÓÒ™ØU•‘œÔÚÞÑœ”QZ”ZÖ•œ\˜ÍÓšNXLÒUÒ’N^–UÓÌÑR–šÜËÙšLÍÞYNMZ“ÍÖPÍSÓÝÜQXVÍÔ™ÓKÖT‘ŒÛÊØ–šÌRŽR˜ÒÓÕ›[ÔÙžZ”šÑZ˜ÔQÔTQQ–“˜•Õ›ÑMÑKÌ–ZY‹Ô“R•’RR[ž•Q–]Z[ÊÜT]UÎUÞ’–Œ^LRÚVQÔ]‘ÔœZU–[Ö[”\VVÛ\”ÐÝœQÚNV\”ÒØœ[LZÛV^“SR•^••ÜYXPŒ”ÚLTÜQÓÒM]™NTÓ[MZKÌ•Ü”ÑŽN”‘–V
ËÛŒPÒ^ÑRSMT]ÎÙÐÎÑœXMUZZQÐ’Y’Ø\QŒLÕMT›^•ÌTÝš˜KÒÖ–]Zž\Ð•X”™^\Ô\]ÎXPœÜ–’S[ÕÑQ•”ÛÒ””Ò]‘PÛXÒ“Ì\[žPNYžZŒ^QÒLVØÒ˜ZÛMZ”Ô[T^]SZYQÝR˜‘ZS‘TÞ“’R›–]ÌY‘œRLSÑ˜ŠÙ“ÚY™ÌÓ“]ÑUÛž‹ÔÐŒ–LQ[Ì•ŽÜNÚVYS]ÐÔV“Ü–‘S™ŽL\KÚ^Z˜SMÓÕ\ÍÞ›[ÜXÍUÓÖXYŠÑ]”Ü‘ÐÙÜÑÜÑÖŒÔÜËÍ•MØÒÛ’UœÜÓÑœÛU\MžJÚÓÜœ‘Ø]ÛL^–T›ÍÜJÕ’Ý”Ú^ÐRQRZËÝÍRžÕSÌ]“Ý”PÓKÛÊÚPÖR”UÜ[ÐœœSR“ÞKÓ•ÍÔ›•ÕLMž]“YØR[’M“Ô^]M›ÕœZÐÙÛLÍRYÒYÑYÍYŽM–SØœZNMÞTN”žPÓÑX””ÛXžÑÍÑËÓ’N[œÜÝŽPÔÓ[ÐÌY•LXX›ÛÝÙZÑ
ÛNQÙœ•ÍÙ“˜ËÝ”ŽNL[ÝŒÖÚ››TTÓ]QR“ÚVšÝ–‘LÜÒTTPÚQ›]–LT–
Ì˜ÎJÝÛ™Ò‹ÜLÙ‹ÙUÙ‹Ü”
ØÜÕV™ÔMYÍÝQÍžœ•MÓ[LX”ZÝÜÚ–XTÎÙžœ[N[^XÛ™˜Z›R™Í™Ì•Ò\Ö‘–MRQ^MžSS“•\ŒQÓÔ™ÍÐŠÛL[•ÍNT–ŒËÔ‹ÞšNLÞ›TÓž–YÌR]UZT•“[•Õ‘TÜ‹ÕXŒÓÐÔÚÐX™–˜ÐÞ\ÙÙZŒ•ŽPÒPžÔ\Q–MÒ‘SœTU‘“ÍÜ–š““›ÚÌÌ˜ØØÜ[Ð\ŒœÊØÚU\VÕRÔÑ\ÝMYÕÌÛRÍÕ]Ü“X\RÜV[]ÕØ[NV•“ÊÔ[\YÝÚRœKÚÔP\ÔÑYÜM\‘™ÔMYU‘ÚÓÐ^TTVKÜQ›Ð“N\]^œ“^VPšÕšU\Í\ÙŒ™Ò”ÕØQMœÎ[ŽÓÚ›YÎLÓ•Œ\ÐTšœÐ˜YÛRSÕŒÐRÓ•–TÓšÚÍVœN]SÓ^•™XÝšÎUŒËÜžM“SÙ“Ùš]–X˜ÞŽZPZÚ•ÔP™TRÝXÝ’ÕUSÕœMZ–œŠÒ^Ô•ÖPÓÔ•UÖ\ÕÌÛšZ›KÑ•ZZœUÖÕŒZÙ”ÓÎTÒÖUT’RÌÙ‘SVŒTN^]‘•ÓRTÓY[ÍÖ^“˜PÙ’ÜT›]VÚ^Ì•V–žžMRœÛ›Ó
ÑÌ•JÔÞ[ÛÞ˜ÓZQ’ÑYÙÚØš‘MÑU›Zž˜Ø]™ŠÌT‹ËÒXMÝYžÔ]Þ’Õ[šÖ‘Ôœ“žš^ZÔÜÐÌš›ž•Ó™]QÖL^LÕY–JÞP‘ÙN^‹ÊÒ”›•^M‘žMRÔ\‹ÑÛX˜š›ÛYZ›”QËÌÐŒ•’MZÞŽNUÖ[ÒTÒÍÔÒT“ÐÕS\TžšXŽKÍÝ™V‹Ú™ÌœÌ[[šX™UTÐQYÑU˜ÌÓÑ[žŒÙ\‹ØÜÑÓŒ’ÞœTØ[ÐÓŒX”Z•œÌ[ÛÒ‘šÔM^M‘ŽZ›•ÓP˜“Ö–VRÐZQÝÐÞPRØZŒ–Ž[VÌÛÌÖš]Í”“‘LM’ÝÍÐQQYÔZRšPYÖ™ÔN
Ñ•”ÑœÝ“ÜÍÒÙÛÓÎZYT–KÛQÛÕ\SØŠÑ]ÑÎR“\RZPŒ\ÒØ™V[L”LR“œ›œ›šÎ\Ñž\V[‘ÔPQNPÓ™JÚ‹ÊØQ]ËÔ–ÜÎÕTTY’œSÛTLÔÒÑÕR]JÐVÓMÒ]ÍÕQ\RV^SMÙÔ–ÔžœQ“™S˜\TÒÚ”’TUÜRTŒ’ÑZÚ’’N›MRŽP“œQYNLšœšQYÒ˜‘ÍM“LRTŒ]ÊÙÛ]ZÕUØÙRÜRÌœÖTYÖMžR™Ø›šÜÛ˜”KÎLMœÜ™”RšQÐÎMPT]”QšÝ›^”‘™ÔÒRRMÓX”M•ŒÔÔXTÝÜÒ
ÓžRžLŽÔ˜Z[ÛÜÔ›ÝÚÕLPRU[QV”ÓÞ–ÚÒUSMšÑ\Ø•XÖ[ÔÔŒÕ”‹ÌÑU•ÔÐš–‘ÌRÛTËÚY“ÒÝJËÛŒ‹ÍÒ–“žLÐP[Ù^YX••ÓÚLÖPV•R›œU“”XÒR•MX”Ý^XXšYÝÑÔÌ”Ú“Ó™Í]œ^ŒU‘Ö]”’UÒÝZ^ÞYY‘ÒÓL
Ú\L™Í^RÐS\^MžS]‘\˜›‘ÛÓ“Ü››‹Ô˜’KÑP‘ØÎPÓ“PÔÒÓÛ”œRPÑ\–œÜÓ\ÐYÙÍX[SÞÒÓMLÜÖ\žž^ŽÒ‘U•PN^ÍY˜‘Q]ML\œSœQžZMVZÒTÓž•RÒ[‘”U]^ÌUÎJËÕ•SÔPZÓŒ[V›žZÝÎKÒžš\M•^““LÌR\Ì”L\ÝÕÛÊÙZQ]›Ö’TLÞŽM–]Í‹ÓÓžÎ[LŽÛYZØÕÞL“œ˜žSLU›[•œÑQÐ^˜L[[Ñœ‘PŒÒZÕÊÎS’ÌZ]ÑÑÍÓÚ]ÒÜU’LÑPÐÑRÍ]NMN™ŠÛÍÞ›”\ÚM•ÚQÞ]QX^”UœŒÝÎÝÙÕTÛÚX‘š\•ÖÒ›[TÚ›ÓT‘žšVS”VZMÔV“ÕQÛ“MMËÍÝ]]šÐÌZVUØTÙXÕ“Í“’[ÛPÐ‘ÖYUšËÌØ]ÖS››ŒÝž\‹ËÔÕžžœÝÍÌÊËÜÔ‹ËÚŒÞRšYU––ž’˜œ’ÐÐšÖšRÞT’ÚSUÕÛNŒÍØP\MÌ’ÐÜÝ›Q\ž]N[^RP]S‹ÒœŽRÌ˜”[Ø[‘MRV’LX[ÔP”ÖZÙÕV“ÝÌÛKÙ\ÝT\ÝZMÌ™ÛXËÍÙU••^[œÌ–“™˜š˜›[ÔÝ”XZ“”ÝÕ•YUY^US‘\ŽÝR’MRÜYØÌÖ“R“ZQÔUUŒSZTVLÕQ•Lž–“UÕœTÚÑÝŽUÝPUQSYÝÞQ›LÚSPÞ^^VšœÌ˜œÍÑ^[•Û‘]’›ŒÒÌšÑØYTÝÒPÑ’PÒ\ž›SÑš]“Q^KÚMXÚRÒÙÚÛ^NQUZŒÜ‹ÔÚÛUÔÔ™\ŒXU›MQ”Ž[ÐÚ˜Ü›[ÔÌ]PMY[QœÓÌVÞ™Ú›QYXYÌœ–VNV‘“\[˜[QÔØÒÍžšÕU‘U’”ÕLÚSÌQL–™ÑÑQÍ‹ÝL\ŽMÞŒŒÜ˜Í[ÖSÙŒ–™‹Ù]^”‘’žQP]ÚÐÔ’TLUÙ••ÚÝU’M™ÝžS]Z[Ð–ÌÙÒÍÔLÌÑ“ŽU]Ñ]QUU•ÔZ^[˜QÖKÎÌSQÛZXÚÔ”‘U[ÔRÝVRØÝÐ’ÍÒ™ÙSTSZ[ÓÕSUÎ[œMRÌRR\–žÔM[ZT›ZRÔžNÔYKÕ^U^‹Ö”ÙY^™JÜÓœÙLš›˜ÕÑÊÔY\ÒÐŒ˜Ð^ÞLŒR]ÖÞYÙ›YÑ’ZÝKÞ‹Ì•“ÜÝÛSÒÍÚÙTLœZYX•ŒQÚÒ™ÔTYÚ\VRÐÊÓYN“•™^V]šÛYÔ[Q‘U]ŒÕÝœÍ[ZQÐXPÍÚ–Q’]ÓPŽÚÙZÛKÙÙ‹ÜZ˜žKÊÙPYÐQ]ÑQQÍ[PÛ’ØÍŒZ•Ú^LÚÚQQ’RQZSPRP“Y‘ÑJÖ‘Œ[’ØËØÛ“
ÙTLŽJÖËÙÙÔÐURšY’ÑP[ÌÜUÜU\–^ŒžMSÕÓ•ÔUœ•™YÌÑPUYÒžŽXÚ]ÕÜÙÛÌUÚ‘Ö™ŒÑ˜ÕÖ‘ÙÔŽRÑ’L–Û‹ÍÛÍ™Ú‘S[’U‘]LÚ’ZPTYLPXÒ’YÒ]ÔÓÔQPSZØÓXP“M•TÒL’ÒÌŽQËØN]’™U‘NSÖV[Ô’RQTšSÝSŒXÒŽZÐX\›Z]“œLTŒÑÐZÑžUVXœÌÎÛQ™ž”Õ•ØÊÔKÝœ‹Í•“ÍŒNŠÚ›ÚÞ–V›‘Z\ŒRÌÐZŽ–VRLNM•LÝÝ’[‘[\Õ[XP\YLRÐ›M]T“ŠÒ]V‘ÚQÌ]ÚÐŒ˜SÌ“PÎÝÚVMŒ[XÍššÍLÎËØ]“šS›RÖœ\™ÝŒ\ŽQYP”Z›ÙœR]œšÙ˜›‘[KÕXÖ\L\V’TTYYœVN]ZÛLÕžL‹Ò^ÜXQSÙÚÐ[ÚÔÛÒLÒUU”[TÐÓM›R‘]Ü[˜Lœ[‘•˜•^Ù•’Ü‘ÌMPÔÞZP[ÝÕMÚž‘•LÜXÒ™žY‘‘QXÌ‘PQXÓÙÔ‘\Ö‘ÑS™ÕÝ˜ÑN]ËÊÚÚŽÎÝÙM›ŒŒÕÛËÖT[QPMÐÒ[\Ü]˜]^”UPÞX\Ý“žR\žRLQÔ”\ÜL]’Û\[ÌÐÌ’[œ˜”M‘ÒÌY™‘ÝœUÔŽ’œZR™Þ™ÑMÊÑÑMÙËÓ”\”TÞMÚÒLX]ÓT“[Už^”™Ü›Ý˜MQMÔYL˜SÜ“[Ý›”š^\“’›ŽTÚ”ÜN\ZžXšUÐ•Ùœ•TÝ\ŠÒÐÜ’VÝÌUœX˜˜˜L›–“™MRÍœÌÍTÓ\ÑÜ]LÛQÍP[UÍÖM]ŠÜÝUœ[–œL”[šP‘YNÐÐ‘Þ›ÝÙ•Ñ^Ìž[™TLÑžTÚ›SÚŒÍ•™ËÚŒÒœUÍÓÌÞ“XÍX\N]•L]ž•ÝÒRÕÙÔÐÚÎR”ÝMœ^NY[XÚÚZ‘JÚÝ“Ž›”ÝZ]ÍRÒØTNœRÙQS”Z[”š[ÌÔÚÓMÛXRMÖÌ›‘Y’ÊÔ]ÑÍÍNLØUÔÙ•ÕSÞUÍLØ•ÌÑœØÔ›]ŒÚ‘QŽSÜQ\TžLZŽ]Ì\•™šÝ‘XNUÖT”S“ŠØŒÍTPÑVSÍ”Ù˜žœMYJÝœÛZ]”ŒÖZ”ZLRÌÓŒTÔTS^”ž\PÓÓÙRXRZÜÑ^›ŒÖ™NSÎNM‹ËÓLÌËÒÒžŠÝËÝSX\œNLÜRÜ‘ÑÝ“QÓVSÝ’žYÓÕU”š’Ò›Ó‘ÙX\^^ŒÔÝŽ]•ÛQ“ÔÑÙšM[ÌŠÜÊÍ•UÞ“’QÐÝÐ‹Ö•ÜŽÜŒÖ›–œ˜ÍËÛžNJÒ›Ò“œ–^œJÜÔÌšÕ^ž˜X˜›Þ]–]˜Ñ™[“ÜŒ‘ÕŽŒ›ØZÙU\–LÚŒ“Í›]ŽR‘Ð™ÜX•ZPÛPÚÔÒSQÍQYQÚ”YÚÒL“NRQRÍÍÔ˜VTÞ’Lœ[ÙÑY™Q›SZQÊÝÜÙ’RSM™S”•\ÚYZ–ÚXTÓÑ]RÎ[UZ\›KÝÕÎÓÕšÚÛ˜ŒT›ËÓ’•^KÐÕžU’L›SR\RžM–YÖPR™^S“ÚÎSZÔÝŒÒÛžÊÍ’ÙÝ˜\”Qœ\ÕÝXXšÙMYÓÐZR›NQR‘[^MÙXÝTUÞÌÌËËÕÔÌÝ™–‹Ö™™LÐœÓÔ˜ÌÑÝÖRPXÍVÌÑŽLSŒZÌ’“Ð”LXYMÌ–Ü™^VLX^Sš•ÚÑYÞZ[ÞL[ÔXÕÓSÍQÙVÌPÍNZMÙYQSNR“ÖNMœTÓT•ÌÜÚÓÍXÒP]“ŒZUÖ˜V•ÞŒÓÕXš›SÝÌÖR’ÖR™Ñ™ÔPPÊÖXŽÖ\˜ÜÍ‘‹ÒTVTÝ”ÑYYÒÑžÙÍÜÔÝÚÒ[MUž™TQÓÙÙPÐžÞžŒ˜Q™YšÌL\ËÔ™ËÙTŽLPQRž\”SL•™”P”šQ•L›YÐËÚÚ’‘LœTKÜ‘X˜ZÌ˜[ÖÕÓÜ[Ô“‘TØ–[ÞTÒSŒ‘žPVRÝSÎŠËÓKÞŒÓŒJÍ™ÞŠÕZTTÔYÐÐÜœ›TÌÒZQQÞÑ•‘›UL”ÔNVœÍŒÜ’ÌYÛ‹ÊÌ™”•–LNM’•ÍËÔÜ™™™ÑÞP””ZÒQ’^\ÒÞ\R›ÓŽYÐÔÕ›UÒ]QÌUŽKÎR[RœÌTŽ[V•ÞÒÕœÑ’VZÒTTÔžRÒ’ÑÕÓÛÌÜžU^™””ÎšL”žQR™œMRœÜ“ÔÑšÔRP”TYÑÜ[S™VZÚÓÙXL’Ð“^›•LZÚ^\YÍKÞRÑÕÕ^Q“ZXÙZÝÊÒšLÐÖ‘•KÖÞŒU]Û‘PšÚÛPØUÌ“
Ð˜ÞQ‹ÞÙ]N›ËÙ™Ø•\“ÐV^MÌTPZÌÑTÒS™ÒÚŽ\œ\•‘‘Ù]Z›ÜUšQLR•LZQLLTVšM]™”U›ÍSÞ’ÛSŒPZ’Q[™VŽXÎP›ÌLÖ˜ÙŠÍP›ÎžPYÍÓÝÐÔ“ZÓÚ^–“”Œ“•’[Î\Mž™V›Û“ÔÚÝTËÝ\šTÑÑ^]ÑÛUÙPÑÔ’“YÕNS“”Ü“ÔKÍÐŽ^\Ù[Ûš]\ÍQRTNVÌ‘[–U–”LÖœž^NÒÍÜ[™TÍ[TTÚÛÙÌŽšÚ[ÙÝŽTžZÌTœ\
ÔÙÌ•ËÓž]\›œQPÐPÑŠÝÓœÖ[ËÐÙ›Œ”ŽÔJÞÑJÌ›››Ô˜Þ’ŒQ][‘Ì“™ZÕÐÔX˜M\]“RSžR\”M™Íš›ØÚ]Þ•Ø]œÖ˜PLÚÍ
ÞšŠÑÝ““˜Û”NÒZVTTÓÑÍÓ
ÜÐ^ŒÌŒ^YR™S˜[
ÓRMÝTVN]S[VM“ÛÍ\\ÕÜÚÔUÓ”ÍU–œU”ÓÞÖ•”›Ì˜›Z”ÍÝ™ÓÕÕ]RÛY›žÜØ^X–˜SSY›LR“ÌZ\MM[ÝTÙÒ’ÜœÐÕØÌVZXÑRL”œXQS“ØTMPRÚÒQR]\TÌ”SÔ^™]žUÌÚ\ÎžÒ™šÍ]Ð•ÚNYM[ÚYÛ[ÍYËÑÚÕÍ]ŽXZÜ]žZ“Œ\Ñ–ÜÚ]ÞNMÞšZÊÛÒ\ÒÔÛÜÝœ]ŒVSXVœšVNQŒ•\ŒœœV”ZÖ^“[ÔÍ^š•ÌÓÊÔS“ŒUÕÛÞž\ŒQQÒ›ÒÓÓÌÝ›KÍ^ŠÔ[•ÐP’TUS–XÖŠÔÝÍÝÜTSÞMÍ˜^QRŒÜÒÓÍÓSÕÚ’“™™šZXXNRU^UZRQZ›ÓŒŒÖ”Ò^ÊÍÌ™œÑÓLØÙ™ŽV^ž••ÓU’ÔXŒ’ÙJÝÍÞÍÍLRPÊÝMÎZ^
ÚÔÍ›”“œLY‹ÌÌËÌ–ŒÛ’LÎ]Ý˜SÜL]XÜ•’šÍÑT‹ÕQ‘“ØPØ’”S˜Q™ØTÕÖŽ‘”[Ø’šÕTQÕV^PŒ“›ÛÛÔYV›ÚœÙNT[ÝÍÌ™R˜^ŒXÍ™\ž‹ÎTÙÍÛœÝ“Ú•L–JÝš‘›MÝžUÙš“›š–“˜‘‘Ú–”TœLQZ‘JÌ^”š[ZUYšR[XÑš]ÝPÌŒÛÕ
Ð\Q‘Y›Ó”“Õ‘˜•S’NPÙÜÞSÔ•ÊÜ’ŒV\ÕJÓËÚ]RÕÖÐZZÚLÜUM›ÌYÒ•VUÑ’ØX\•YÖ›U›LUŽMÞL”Ù›™ŒQ˜ÔØØ‘\”Ô]•ÛŒÌÓM››•œÜÕÎÙ“•ž’XÊÕ‘LTÑËÞÌœÒRÚU˜ÒLÕÓÜÖ]Í^KÚÜLTÒÚ˜NR•[ž\ÑLPšÑÔÍ\ÌÕž”[U•[›ÙÐ‘RSVYÔP]L[Ú]YY^œ]XØÎ[]’’
ÍËÚËÖ™]Ù•ÙYÎ^ÊÐ[Û•ZÕœ]ÊÔÐ•ÛQÕœÕÜYÚ[PÕÌÚ[
Ú”ÞL‘ÑÛÑœ]“ZVP˜˜šPP\XÕQ\QQ™–NM‘ÞœÐÔ^UQYÐYPÑT‘RYZ”ÕQ“S“Z]TÑQTLV˜[ÚÑÓ[Öš\XÜZT›]˜PÙš™Ù]ÍNÎX“Í˜LMPÒ^RÊÙ\ÚÍSP\ÍRT’šP\ÕÝÑÑMÜ˜STQTžL‘ÒÛM
ÔQS“^Ò^–
Í’LUSŒÍÓ•ÒUÔÝ–ŽZÚ”Û•ZZÖÛ“ÞUÕ›LXUTÚ]–UŒV^UÚÝU^ÍY–›]•ÜTQVš]Ü[ÓÓÚXÕŒTÔ[MÞœR‘‹ÛËËÙÖÐL‹ÚÚÞJÕÑ™PNÐ‘Ó™Ì•š“ÑÔUŽX‘ÝÑ]ÑÐZ’Ö‘LXÔZŒ[ÕÙYRØÖ›NM‹Ý[Ú‹ÓÑ
ÑPØ˜ÝTQËÓ™MÕVž\SQ˜ÒLÞQÌ]RšÐ\ØÕ”˜ÓYÒ“››ÕÞXZ˜Ô’ÔÜ[^–VU˜Þ‘Þ”TZœÌTYœYÞNQJÎVÚZœŽPÒÝž“[M”™Ö›Õ[YÚÛPLZMQÌÚY[\Ñ’Q\]Ì’•[ZŒØU‘LSŒPÒÛT[™Ì™Õ’œØ•žM^YÞÞYšÞM\Ò•ÚÜœÙYÙÚP™ŽÌ•ZÔT”Ý]QN“ÚÚÌšÕžSXPUÓÞQ“RZÔÒšÒÚUÒÝ’\^ŽN[ÚÑÞ]’VœUØÓP•\“Û›ÒÑÜ^ZT[“›
ÔQXZ]Ñ[’JÌÚZÐ“ÌØZ›Ý“Ü™ÎÐŒÜ•TÞÝ^Q“VKÞQ–˜ÜÎQXÛVL”žJÙÜÓÞ™ŒX“›M›ØÒ’
ÝKÕJÚ“VZ™LLMLŒXÊÛÛX‘ÖZÎÕRJÎVUÌœŽËÚ›UÍT]\SÛÌÓY‘XÐÔ–ÖM˜NXXV™NLQRÌ\“LÑÔÚ˜ÒŽ]‹ÌÐS\RÝQ››ÜÚ–SÒ’ØXÑšRLLX[
ÌS˜Ó‘QUQÔ‘“PÌ”U–NLTQŒÝœÙZŒ“ÜYYÝL‘YÌYœ›ÍKÒÝ[™Ñ[[™ÖXÖZÝ™ÍÚÒžÓ”Û–‘šŒÚ”ÐLšZ‘Ú]ÍÒ’ØSœMLÔ“]PSVš
ÕLÑZÎRZQÝÓ˜’ÕÓÒžZžŽ[
ÒÜQ]ÛTM•žVM’ÕÚÍÕQXœÕ[ÞÕÖPÙÖY›ÜÓY]ÎšLV“œšÓËØQÚTUÜS“ÐTÕP’™•ÞRÔ–U”›Ó˜[•S“Õ•ÌPÛ’ÍÝ[ÙØÙ›™ÔËÖÖ”’ÛTœÝ•šœ•^Q”^œ^X]M””™^TØžÝ“ÙŽ[ÚŒÝULÌžÑžÞUœ“]T‘•^M^JÜ
ÛMšÛY]•–›L›ÑÖ‘XŒS™R˜^]R’ÔŠÛÜœŠÛ[ÝÍÙ•ÎMM–Ø\œRžY\\UšÚZÝ]Þ
ÞÖ•T–’”N\Q‘Ýš™^\SŒšŒTØœ˜’•ÛœŒšQ™ÍN
Ö›–‹ØŒÐŒ–NSÞ›Í[ÕN‘’^“QY^“YÙUÛž’]\“Ô[^R‘”œÕÕÚ\™SSŠÚPTŒ^Z–›™Ð[TŒRLSÌÖKÚJÙŠÎRÞŽJÍšœÚÑS”ÝSRÍÜR^RšV›”TÓV’–ŽÑŒÌ‹ÛÛ›”Ù–•ÞS‹Û‹ÊÓYŒÝ–^ŒÍ\•Ì“•›MŒ^‘^M’Ò\Ú^™TÐ‘ÒÕÖ‘KØYÞP’ÕÝ“ÔÙV[L\YVXÍ•œÞYÓŠÖ‘ÜÌS’ÕMZ™X‹ÞRÜ™ÍTYTÞR˜Òœ™ÞŒÝœÙÝŒ•ŒLMŒÜ‘M‹ÎÝY™Òœ”\ŠÝ™ÍR›YšÝ\›ÒÖ\’ÖSÝL™RTTÙ[PQÝÒMÐZš”Ö”˜QÐ’LQZ“ÒŒ›•Z[LØU\TÎ˜ÕÜMÐT]RX”“ÞØÙœÒT^L˜Þœ‘ÞTŽTÔZ›ÊÜÕYœÝ”ŒžLÞÍÚÙ^’UËØ˜šU\Õž’›ÒÑ”Ó[
Þ]ÑYÛš]TÌÛ•PN
Ú]ÚTKÐ•–QÕžÌŠÛLYL’šMÙQMX“’KÙ]ÕÕ\L‘ÖV˜šÖ‘Qž][‘Y”]ËÚ’’Œ^U•˜]š•ÞM›ØÐRTXž’]ÖLÛÓ™Î™TÛŒÌÍÞ]ÔÍTÔ–ÖY’ÑYU”VTÎÒŠÍÔ[”˜P[TÞ’^‘Ò\šÐ‘ÖXX–^–”MÚØÌTZTØVšÒ™S^SØÚØ˜ÌÓMYPN“ÎÞ^VŒÕZLÓP“MÔŽ˜ÔŽ‹ÕÒÜ[[NSÜ‘“œMRÕÞP‘YÒŽRÝžM‘™^NP“™™MÐÍ‹ÝUZ”ÌÑØÜS‘Ô]PPTPPTÕT•‘[YZÑÌZ[ÖÝÒÜXÌšÝSŒ\ÌÚÊÙJÑSÞ•ÊÚ™“Ó“›QS[ÑUXZÌZ\•œYÜ•œÜV]ÌØ\œÍÙÚÚSTÑTÕMMQ˜LPTÖ™–MKÕÛ]ÔœURÙ\]ÙQMYÐÑXÎRÓÜÌÔŽÖ™›Ò™KÚÙ–˜ÒÝYÕPÐ‘ÔQ‘LUV–˜’Î›ÑÑÞU’’UYQ˜PRQTSQ^™šÓÓÌÙ]ÑNÝKËÕ™R”ÝUÛLÛÒ‘VTPÚÓžTÚÙÜÙÓQÓÞ“–\Õ›Ø’[ÌÑÜÎQÝœØÞUÙ[žJÒÛ’•ÚÎSÚÕ•œKÌ•ÞLZ‘›ÐÑPT\›Ð˜\ÜÙLÑÚžŒ™TZRœQÍÚØÑÕÛ›“T”ÜXÐYÚœÑ[‘TVYUP[ÑR’XÎUU]ÜY•TU‘Xž]ÌPÕ•Ú’˜[S]Ù››”ÌŠÒ“šX’QŒ]ÖY•Ø›ÑÑPM˜YNS”ŽRÛUÑŒZNLÓMQXÜ^“SÝ^\Q‹ØÍÝØV‹ÓY‹ÜÒŒÔ“’ÞQ“Ö“ÚQSTPÜÒZS–Q^UÓÔP•‘ÍUÎ˜RØPÕU•[]ŽURR]ÌJÍ]ØØPÑ[VR˜\Õ–˜ÜØ\Ù••Õ›S\Q•ZQQQÑPŽZQ’Î
Ô›JÒÜLP“ÌYÙ–MŒ\UÒ
ÔÓQŒ•–]ÜS›ÔUšTÞPXXÓÐÍV™TL\SYL››ÓËÓ‘Û^œÝMÑZÐZØ›]Y^^™ÎRÔUMRËÌ‘]ŒÝ”™LÒ]žš™ÑVUVY˜QŒ›Ü\Ý”“•ÚÖœS“šŒÓÜ’ÓUÛ”ÙÎUTžQ–šœ\šUX˜’MÌÍQ•“‘ÍPÊÍ˜]›Ñ–œXNM™Þ^˜ÙÕJÊÐQNQŒ‹ÍU”UÔ•šÙSÚÙÎPÒŒÙÕšPPQM›ÛÔÛUSS•ÖVZ[V™QÓ™œ^ŒÐ’–”Ý\^\]ŒVš’ÝÙ–ZÕÓ“ŒžUTP\ÌYÕÕXšžÖ–”–˜™ÒÝÔT[ÛŒÝŒY‘ÚSZSšN‹ÝMVQ]ÔSÚŒÕËÎŒR“ÓÒÕÍØQ\[QÍÍ›ÚÖ–žØ’ŠÔSÝ[ËØÝU‘P]]ÒMÊÒYÌ[ÐŒMÛ“Õ’ÝYXŽJÒÕœSQ[•Ø›ØKÙMRÓÙ›\Íž[ŒUÑ]‘ÑÚÕQMÕ›[\™\ÜQSÖ”Ù‘\ŽTXÍ‘ŒÞ–ŽTS›Ò]ÙœZÑŽÝÞUÌž‘‘ÓÛPTÖ^ŽÊËÕ›LÐR‘TXÔYÕRXÎRÛÐ\Þ\[Ó]QÒ[RÌSÎÛQ™Ú‘–šMÝÎ[œQÓSZTMÒYLÌÕÌÞ–M”Ò’ÐÍÚÓZØ\Ý”ÊÌKÖŽ“ŒØÓÐÔPÔP“ÖÔŽRQUZÍ\SŽR[X‘’Î\L]]ŒÛÍÕ•]™”\ÖQÞP™”LÒV–L’›ÖSÌ›“œYŠËÜŽRÜÜ•NNÐÕÕUÔJÍÍ\™ÙÞZS\”ÒPR•ÕœÍÖšQšXÚQUšžYNMž’Î\YŽRž–‹Û™‹ÔÝÍÜ™•ŠÎØÜÒ
ÞY•^QRšÝMYUžQÒM•ÞÕÌÙŽM‘Ú˜V›Ú’TNÒ“\TÑ™˜UÖ™ÑÑ“ÙÍTžÚÔÖŽ”S™M[“ŒÊÌÍÎZÖ”Ý‘ÍMÞ“ÔÎÙ^‘ÔT\’Þ•ÚL”ZQ]TZRP‘›YQ\L]Ô“”™Ó‘œžJÙRSÊÓNPš”RšMž[SZSÎ™ÕQ‘‘–”œÌŽZRUÜQÚœ”ÙY˜‘’Ð™Ô“MPRV™‘•›ÛÞ^YÛÚÜÖ]KÓN[\U’]’šÛÕÚÐ”ŠÛ‘˜JÕÕØQ‘‘Z’SUš[VQÑÓÞU“QÝÌX‘‘•[TXÒ•ÕÒ›SÞŽ–]œ[ÖZ“˜Ú“•Y\ZÝY”ÑšTYÐÐ[S•[Õ]Ñ˜Ø›ÊÑÖMÚX‘ÎYT–VœXZRMÚÒ[RÔ’Ö™PV•]Ú[U‘MÔœ[UÜÐVP‘PÖ]ÝÕÔÑZØ”ÜÜPYŒÒ’ÍÙØ‘ž–žÊÌÙ–ŒÝ˜ØSM[ÍÒ•XÙZÔÔ›žVR‘XÜU’›XTÌÔT˜Q™ÙÒ]Q”–TÛÍÝ›˜•QÛÞ’šQM[Ý›”ØŽ”Ý•LÍÜUÓQŠØ^XÝÝÖÔ”^’]Í™[Î›’PXQ˜TÒÝ“œS˜˜KÝØ˜ÕZÛÐÐQÓLšÞ“™ZÛSÓÓŽ]\YS“ÎRZNU’Rœ•]T‘ÔÓPRÙLÓP^’ZŒTPÐUUž›]YJÖÑ›ÝS™UÍR\‹ÖUÞR\˜T[ÛŒÍV\–•“L•ZÙT–‘Ô–‘]ÙR›Lœ˜RËÒÖŽ™ŒŒM”Õ”ÒRZÜ\ÒžZQÞRTØ^™[[ÛÊÕÓÌ‹Ì˜™‘ÌXKÔTÔ˜Ûš”˜ÐN›ÝJÙ›\’ÔVRÕ
Ø\–M“T–ŠÚTÕœZTYÚ^TPSÑÑRPQ•Õ]›Qž]]ž•ÙJÖ‹ËÚ‘ÍŠÝÑœÐ“Õ™ÕZÔUÖS›MØPŒÓ™šÛQÑÓØT–\ÑÛ˜]]X]”R•ÚÖ›S]Û˜TÙÕÒÑÕÚYÌ“ÎŒ˜XØÒÕÙPÛŽLSÔÕYÚ\R™‘ÔMÒÚÛÛZR[’Ñ[’\™VTTÑÕMYÕZYÔÔ•L™QœÒÜ•]YVÔÍZT‘\\]LTY‘›L“ÐÍÛYšÐÐŒMLMÚžœ[ZLÒÒÕÐP›UÖQVYUÎR”Ñ•‘ÍÛŒM’RÙ‘TÓURÔZ•SÌŒ]™ŒœŒÔLYQ”ÍRJÓMMØSŠÕVššÛÍÛTZÑYÝM‘ZÎRZ–“›Ð•ÜÕ˜YÝœRÝÖ\UÞ–’œ˜“RRQ[YYZÙÛSÕUÞ•UNSŒØ™ÝÚ•YR‘TTÒQ^’U\žŽ“SÛ›˜ÜÕM
Ð\ÓÑX˜ÝÓKÛÚŠÒÜS‘•TÝÔÓTžŒ›[PVRœ[ÞUÜÎQÕ˜L]ÒÖ’Ø“LV‘šÍÛÜÔœÖØ\ÓÎØÌMÒN]‹Õ™’ÓÒ^PÓÙPÓÒ’P[ÐÛŽQ™”–•TÑLR•Ñ˜L•“ÜQŒÒÎUÔP\’ØZNÝRUÚTLR\Ôž\ÒÐÒÍQÔLPŒŠÕÖÚLØŠÖXR‘MšššVRYÛÔ[N•ÍÒ]™•ÕËÌY™”Ü
Ð]ŠËÚÙ™ÙN\\Ö]SZœÍ–YÚÚ\ÔZŽœ”‘ŠÕ[ÔSšÜQ”ÛÖ˜Í–YÞ›PZÔ\ÜÝÎÞ–’JÕÙÙÚÔÌPÒ[ŒP]›ÚY”YXÙTP‘›YÔ‘MšÕ•Ì^‘›•^[ÛÐÍLPŠÔš”ËÒJÜZ™UÜR•Mž˜R‘™SÜM\–JÌž’]ÍÒÔY›JÐ[[^XÝ–™Z]SÍLT’ZSÕ\“U[TÕŒ\VQX‘›‘T”ÚSÓMÛÔV˜˜TÜ[”’Õœ‘RLšXÑÓ’SšX™žŽJÌY’ÐÞØQV“ÒžU•ZÚKÑ‘XÜ]ÌQœT]UŽUP]ÞšJÐÒL’”ÛQN[ÜU\L’ØÜœ\›‘Û™‹Ú[Ú”ÓÒšÐR\S\•XYÛ’SÓÒ\ÕÚÖXQ^QYNXR’ËÝS“PÊÖ\ÖšZ“Z[Þ–ÒÜÍQY[[
ÛÒQQ‘ÙSœÚRVT]Þ™™™TMÍTQ›ÝSÛÑ[
Ý”T–›MÕÛS“ØÌÖUŽœÞÐÌP^XÝÓKÑRMÑZÖÓUL“ÕÛÒÌÒÙSZZÑÖ“SÌËÒÒžŒÍÎM‹Ù“ÙUÍRU•[RTœŽV‹ÔÑÓRÚšQ•RÝÞSÚT“ŒÙØËÔ
Ì“VLÍÚŒKÌœÚËÎXLÝŠÓPKËØN™›ÞNKÍÍÌÕÛX™“U˜Ú–“Y›Þ›VTÛLTQQ›L”XŠÞÎ\RMRKÖ[ÓZMYŠÔÚ]Þ™ÔÔÙÐÕZZÔŽPÐÓR™ÙÖMœÚSžš’ÕJÍ^[–˜QÔØÑN”šÑÛPŒÖUÒ[ØU”Ó•[ŒS–LSUÑTÛ]šÌ™ÒÑSœQZÌ‘^‘[œ›’ÓÖØœÓ]šQ]Z\ŒMSžTÜPX™ZUÚS›
ÓMXÛ–QÑYQPTYœÜ\ÖXÔ’ŒV“šÍ[ÚÑÝ\ÛZÍŒ^’•[ØÞ˜ÌQ’›”›ÊÎT™ÎMØ’ÍÕ”]TÞSšUÞJÑ–Œ^›”PÚÊÍœJÔZ•ÕRTÎQÑSÒ”•]ÍUÕ•[ÜLUSMTÚÛÙÔšT”žP[S–žQÔRÔ’›TÖ]ÚTÐÚSÒ^•”^QšTVUÕÍMUÍ“Ó\”Ú˜ÜØÝÕU›^LÝÝÛÚSYÝ[ØŽ’ÛÓœX˜RQÔ“ÝÎXRÑSZÙÍÞVÜ•Ó”PÞUÕŒKÖ‹ÝMÜ‹ÍÎSÌÌÓJÊÌL‘ØÜ‹ÙÕRM”ÜØÕP\UÙMU‘‘•ÔLÔTKÞš’Þ™ZØ›‘V”ÕY[L”Ý[ÕU›ÕÎ™LÑÛMÓPÜ–Tž[ÔšŒR˜]ÝŽÚÌUÕZ™‘’–ÐSYšÑYÌL“’›YR–QÎ›UQÍ“™šÒÙYT™ÎÌÒZœ“ÐQQRŒLYYL›ÝM[^’ÕÌ‘X\–Õ”ÐPRÔRšÔSQÙÞTÌËÔMÌXÒžÑÌSÞXÞYUÙ”ÜLÍSL›ÐÔZTX”˜ÕÕ[Xž˜ŒZÔÚ\Ô’•Ó“Ì[SVÝÜ\Z‹ÕÔ‘ÐŒÖ^ÙÜÞSÔQÑTX™”ŽŠÚŽNYËÝP–RšQPKÞYÖMš“ŽPŒ‘RØNšÍ[Ò^[Û˜Þ˜P”Z˜ÜÐÖ›”Ì‘TÝ™N’ÒÍ‹ÜYŠÓÎNËÍ“‹ÌÐPMÓÍÖœ››\ÔÎ’UVš^QœÝÝÛ“ÙSÍÜÊÔÖVœMÑ›ŽRÝÔ’ž•ÐRÔ›S˜ÑTXÐÎV‹ÔÌ•ÙÍJÎÎÞœYÑQRÝÍR]Û[ÊÑ’ÞŽÖ‘YÍžR^QT–YÐÐ”ÒSÛÒÜ‘žPPØ‘ŒÌ›[YT•Õ\ZÕLÐÚRÓUP[ÔM•[›LÛÚ]›VÞÙNTQÝUL’ÚP”“ZÝÚ“‹ÌPQ“ÙÑY“‘ÒUÍŽNSMLÚYœ]ÙPÔ’–ÚTSÛÒQ[TVXÝLYJÎUVN˜ÌŒKÍ”“™Û˜Ù]ÔXR›Ì“ZP[U
Óš[ZÐ[Y“ÜUUPSÙÞšRÕ›Í\[MÌQ’Ú’L™”ÓØT™ÕÍ\^ZTTÔ“•˜ZQQYM’\ÓÔJÛœXÊÛU›
ÒÍžP›TN[”Í“ÓYQÚÓ›Ì’Ð‘Z]Ý]”’PN]”Rž]N[ŠÒÑÞ˜ÛPRÜ•Ý\Sœ”ØÜZL”ÒP\•T[ÜPÔÐÞSœUÜŽMÚKÙžV
ËÝ”MÍÝÌÙ”ÓÙ]TYÍZLUÛØYÔ]U]
ÔÖÜ™ZÝMÖXQÚLQ”ÌNUZT”ŒLžœRZŒ“ÝM[ÍÜ‘ËÛÞQÒ]ÔM“ÙUÛ˜UÞ’–N[^TUS™Œ[Y”Ò•ÙÒ‘S’ÎPL›VNÓÙ“]YÎS]‹ÞÞÔKÙ‘˜ÓØ[ZÖÎ˜ÞRZŒÙ–œ“‘‘ØZÐUÑ”VÚÖÑÜÑÒQY\Y\[ÒUÜ”ÙÚ’SUŠÕÓ•VT‘ÝœÚÍÐLšXZNQÌÐLÚÓN›ÛLÍÙTÞ•ØÓ–ŽS“ÎPS›VZPQÛÔÐ•YšÖUÐŒU™˜YÚØVœÊÕÍRÓØ”ÛŽÖTÔJÛV’VUÜZŽÎ\QTžÑ›ZÍLUM[Ó[ÕZ]”Ì]Ò’T^œR’[•ÖTÜTš‘ÙÕŒR’ÊÍÛQLŒ›R••ŒŽTž•^ZÌ›ËÌÓÖXÒR\ÍÞ“ÍÙŽÍÌÌÝ‹ÔR^]“ÌŒQTÑYÍPÐ]ÍPRÙÜ™Ö›ÌÖ‹ÚÝ‘‘ÓÝÛÜ“™ÖMŽMÙÐÙÝÒTÖVÌLRRQUS’˜ÖZØœžØÓÔÖ[ÞKÞUÜ’ÍLÌÛRšœÐLÍ’Õ^“”ŒÚJÌÚÌVMLR™Y›XÛÑ›Ó™^Q‹ÛÚÐÐÍœÕÕÞ\ZLÒN\ÕUžZJÚ\SŒ[›œ•˜‹ÌÌËÍÜ[ÔTšÝÛTZÛÚÛÐÐØÜ‘‘PÕÞ“ÓÜ’ÜZP]M‘Û’Y
Ñš[“TÑY™QVRÒ\[Œ[X•ÛÌJÍŽY“ŒÛ˜ž›Q[››Q‘‹ÓÙÙÓ”SÔŒV]R™ÍÒ”ÑšTŽYšÊÒ““Ô\‹ËÑ™P[‹Ü”TžÎL[ŽNÝØÊØÓ]ÜžšœÚš•œšX“RÙMÑXž’TÙœÜÜMP”˜›“ŒTT›PYÜSPQœ”Ð’ÚÚ\Í•ÍÜ“ÚTÔRŒÐŽL\ÌYTÓÓÕØ^^M
Ù[–™MÍMZJÛŒ[•^SRœV]\KÖËÐ[[]ÌNZR™]Ò[Z˜ÕÒV“”V[L’œRKÙÙÕQZÐP‘TZÒÐŒQUM”ÑRÓTŽ\\ÞMÑŒR“LØUXÝšÑÛÞœ“œT]^Ú]Ó˜ŠÔžÒSLŒÓ[Õ”Z”PLÍÚ^RØÛ•’•]JÙLÓÔÜ“‘›[\ÜÌM’ÓÜÒÛÒÕœÍÛÎÕPP]šÊÛ›]PTÍ’]ZJÓ“RÔ‘UÝšžŒÐÕVŽÖ•–›Ú“œÒZÔÑ\PÑÒ[PÐPÑRÞRRTNÑžŒÝËÍŒRRXXÕ‘ÌZMU”‹Í‘ÝÙUÌ‹ÕÚÙ™U••\žRM’’[Ì]Q]™˜’œZÊÜÑÖ\Í\ÙÓ^–Q™Û^“TSPÚ™ÔV•ÔÒ››œšKÜZ‹ÜËÝØY–X•MJÙ•ÍÍÍ[
ÐPÑR”TZŽZšPÔSÔUJÔœÝØÑQÑÑœÒ]œU›JÚTÝŒUØZ™ÕÞ]R\ÚTLTZÚÔ”ÒQL•šŽLŒYÑÙ“ÛÍÓÔÔÜš™ÕÛ“XÔÕŒÊØ’ÑS“PÔÛ\’ÎÓRÚQVžQ“RQNSÑJÍÕ
Õ›œÓ–›ÒÓÔÚÔYPÎZS^ÙÜœ–[’Ì\ËØØ\Øž•S[ZYÜÒPÐUŒ“ÚYN•ÞŽÍÝ›Ü\ŒÛ’L›ÜÑXŒ˜–Q˜ÖRMÊÜSÎ˜U^•”Ñ]Ò˜ÒZÎMÜÎÐžJÍ’ÞŽ”SŒ‘]SšMŒ”RÜZVTžUS›T“’RÞŽSÛÍØR˜™U]ÝÖŠÚÕŒMÞÙÑÌÖœU]Þ’ÍZR[UÙÐ[U]œÔœÒ“]ÚVYLÜ“\MÛŽ]ŽLPLÚËÍTYS[ŽÐÌØÒÐVSÐMZžœTÔXÙTZ’ŒÌ›ÛÝÑY”Øš˜^SVŒLÚÐ[ÝÝÝÚSLXQÍ]^^JÝÛŽ]ŒÛÔ^žœÒÖZÝ“ÍSÌSY”œÑRœLÖPØ\‘ÍÐ•ÓÒÚP’ÒPR“•Û•ZQY’˜ÒÑŽLÒÌÜÝ›ØU[–“UZSÜS••MZPP›ÌÔT\ÐÒZY”SšÛSŒ˜“ZÌQÛNXœMžPÍKÕ]VŒ”]Îž^›MXRÞT•ÍXÍÊÙŠÐ™ÎZÌÍYPNPU•R“”QSŒT“ÍÔQMJÝÍ’™Õ˜Ó^N][^Ü•Ð•ž˜QÍMŒŽVLÓ“œœSšÐTšÔPRÌ“œ
ÌÑŒœÛŒÝ“ÒŒÛÙÒÙ™ZÑÕV\•”MÕž•“š›
Ò^X›œŽÜ™–”˜˜Í™Ž]]PÞšÔS”™Ð”˜X•š
Ò
Õ”ËÎÝ››ŒŒÚ‹Û”KÒÜP“–›T™^SÒPÐ]QÞZÔU\’\ÓULÜNÑM’“TL“ÓYÛÒV“MŒZ˜žR[ØSÐ™TRŒ^LYšXQ”Ú[ÓÞT]ÚØMÑ\ÔPÕšQMœÑÌ[‘S™Ì‘žX”Ö’Õ™MÍQZV›“Q[ÔÝŒÝ[]NNÝÌ˜ËÍÝ”KÞ[ÙY›ÓÐ[P]ÝÌ’™ÑËÒŒ”ÕLLMSYL[S›“ÕšœYQTTU”œ™–••Ð•™ÓØ“P‘ÐQPŽÐY‘ÑSYÒÙPÚÌØ••Ù•™Y”Ó”Ù^Û]˜^ŒÒQSXQÚYY’ÒZ–œ][VŒYUZÒÓÎQœÞÛM’ÚØÌ]ÐÑV–KÛ•ššÜÖÑXP“ÕÔÑžLÔÝÞM“]ÌJÍÔÒšÓÌ”›U–“ÕÐÞÝ\JÛœÚ’›ÛZÑ\SÒÜÛÓ\UœŒU–™]‘
ÌQÔÊÍP”‘Ó•”ÎUÓVL’ZÝÝŠÖMÌÜÙ“šXL\TV’ŽT•QQ\YÎS’œRX”œY‘‘ZR“^š“ÔÌ“™ZRÝ’QQ•Ûš]˜[ÒSÐÛÜÛÓP“VMÔÜÙ”ÞMŠÍÙÔÓÒœÎQ˜ÔÚÓÓQSZœMÒ‘TŒÛVš‘RÜ‘^’Õ’›š›Öž”]ÑŒ\™’ÑUXÔ˜šQ]Q[[SY“RšžŒÝŽQ”›”Tžš›ÙÐÚÖNT’PZ[UÛ]‘ÑM’–Z”ÙÒŒÙØÚÚšÔÔÍ“ÛÒÍYÞUU’“šÔ”TU^MQÐSYSÌ•’ÛUPÚVŽZÑ[[NLJÔNVËÖ^LËÕVL“Ù\ÜXÚ^ZQSQM‘UÐZSNPTÍRNRÙ›UÕ››“MŒTKÓ[ÎMÌÛ™žKÊÌÙÎNÙŠÙ–NNMŒŒ‘\›Zž^’Õ˜VU“ÌT–UÍP–ÜÍ]SÕš“Ø^œž]ÌVX›™ŒX˜Ü•\UYÙÒÛÔQ‹Ó\]”KÔÞÚV\Ü”LL’››––”™™
ÒT\“šÍÊØ“ž™ØËÛNP–SÙVTÑ•–šRŒ]PVL’ÜÙQÛÚS[ÛXŒ˜[’•œÔ”ÍœZNTÝÝÛ›TKÑœ”]Ü–UŠØšÍ\TUÕRÙ‘Ñ‘’[]•ÔU“žšÝØ•œ˜•ØÙžÞRSÞR]Úœ\ÍÔ™‘SZ™ÐSXšT]XÜ]XTšÔÓ\ÓÐÞ”“V^ÒÍYœŠÍ˜œVœRÙ“TÞZŒÓÜÍ›YÐÞVSLÛÖZKØ[ÖžšYÖ•^šZÓÛÌ˜Ú››ÑšÛXš’–’’Û\ÓZZŒÜ•œRÒPÒUPYÓ‘^LÝÛMžž™XÞV^L]ÚLÒÙVYœ–UUÌ[ÛTPÜ]ZRÍY’™ØPUÜP•ÎÝÓÑ•›ÍŒÙTœØ\SŒPLŒÛÎ”šMÛRU›R\Ú–[ÝÌ‹Ü˜\Ô[™ÓÌYJÕÓËÝMMËÐÓR
Ú•R’ÑYÜ’–[”Ô•QPÑÕØÒPUÕÕÑ›PÌZLV[M“žŒÒžUÌÌÚ˜X\LTÛUž^YRJÔÖÒÎZVZÙ[’Ñ’PQÕQ›ŽÚœÍÝÖœN\Ô]šÛœš•’[TÙZØžQ›Ð]\LR[SSSœÑÛÒTÐ[ÍÛ’žÑŒÙRÛ”–ZÙÑ”Þ”ÛTZ‘›ÚRJÖM“šÒÙÓšTXÕQZZ”\ŒšÑÌÜ›ŠÚ‹Ü™
ÛœÜ]Z“XÒLÞ][VŒÜUÔÕ‘“Í•ÜŽ[’Ò\ŠÚYY•˜Ø›ÕÚÌŽSÔÝ“JÙÛÍVœURØÐ˜ÌYÕSÒ‘Y˜ÓÔÔ–”ŠÊÛœËÎYRÌ›PVRÌÚUÜV›SZž‘ÌZ\SUŽRÖ“ÚšTœ›Z\UšŽž™TRRRÕŠÑ™Ø‹ÝÚÎ^‹ØËÎTJÔYS]]SÕ’VLž“[M]Ú˜\TÝ’‘\ZRÒÙQÕX^ZÊÖS’ÙUÓZSYÔÑÓ™SœÕÓÝ]Ù“ÎZ•˜–˜]ÓUNÒSR›”RŒ›Ù]ÐŒ”ÌŒS]ŽMPÌÌ–RR\ÒPÑšÌÝTžU“ØYULÙQœØ›–T“˜žXŒÙ\ÑÚÙ‘“•ZQ^ÝTœ’ÜLQLUš–RZŽšZÐRYUÐ‘VYš\ÔÒ™ÌžÞ‘XTÌÔšÖœZÜÐœ^œ’ZÞÓÒÝ™›šÜŒÔ“
Í–‹ÎZJÍ•ÊÊÚÚšÐ^V^S•šÌ•ØÖ]Íž‘MZÝÌÞLLÌœ^œTÙÒÕÑÜÌ›ž™ÓÒPÞœY[S”ÌÖ\›’ÐÐ˜”QY•ÙLÖŽSÔÎYÑÒ™T‘ÍÔÓÝRËÕZËÚ\žUÜÚU\Û\Ô›ÓÙZLR–VJÍÌ˜’XÌÕÚLMÑÖR–œXZÌÖY\[ÑÙNLUÔÓÌ^ÕÙQQ››ÕÚ’QÙYšY–ÍÌ’ÝTQœ“RÔ›UÛžUXUÕQ[Û[Z™”“XSŽSÚUÍV˜\ØÑ’Y\ÚS•ZPYÍÒ^˜ÒZZYSÒ’NKØÝž[ÙN\MØQQYŒÜÒš^YÍ’ÓZ“ÒÓ[Þ]ÚÙÑLUSY”–ÊÛ\ŒÛÌYMÞŽ]ÕŒÛœÙSÙVRÝœ
ÊÜÞTÝÔUÖQ\ÑR’T\˜^ZšL‘“–›•˜ÝZ\ŠÕT]Z™ÕŠÚ•ËÍRÒÞ“\TÜ“[ØUÒY›QR’ÑY\Uš“œ›TÛÜ”Ú“ÕÙžœLÔUØYSœÔVXRÑ–ŒÞS“Õ’ÔÝ™ÖŒ’ÕšÎ•SYVQœ’]S“ŒXKÝSšØÝXVœÖÑÛÞÞšž‘–™™ÐŒ[’ÚÊÜ]ÜšÓ\ÓM›ÔÜ–VSÒYÓÕÔ•™RÝJÔRÕÒQŠÝŽ™ÖU[ÓžZ“”•Ó•TÓPÑN\ŒÙXŽ^L˜ÕVX\Ü›]ÒÍST\ÚZÕ›UMÕ^XÑM[‘LJÜ‘X›”ŒÝ^SÕPÌZ\šÖŒ›Ó]ŽZ‘QÝÑ^žSØPÑT™˜ÚžKÚ›]P•ØTž‹ÊÎ“ÓÜ›ÖœZ\VÜRœÛ˜LQØÌÔÑUÚS–ZXLÌ‹ÕØNUÖKÒ[Þ”SšÝU•^Ö“•˜R’’Ì™RTÑXÔPÑQRL”QËËÓVM
Ø]LU[–ÖS”“ZU]P]SÓÕØÌLÛŒUQM‘–šT’žž›T]ÖTÔÝÖLUL‘–•’ÒÓÎLÔTJÔÒ“ÕÕÜÚ”˜LÕ[œ”Q]Ý‘šžZÍÎZÖ]ŒŒØ[ÚKÑQS™R˜[^UY”’Y•SLZ•’™ÙŽM’‘UU[‘^ÍSœ“T“ÖœØNšÝŠÝ›ŒÌÜœ’‹ÊÍ‘ØÊÊÛÛ”“Ø^–ÞŒÍ‹ÙLNX›ž“˜ZÙ\ØÕÜSÚÙTÔ\ÛUÌ^VLÚÑÛ•Ù‘RSX“™˜Ö›“ÕØÞÓÒØU’•ÒRÑL\NŒÙULØÙYVV•ŒLJÌ•–ÕœÙÓÒÔÓ‹ÌÎÚÒ‘–“ÕÛ\ÑÒØLVTMRÞPSM˜]UÒÎ›•ÑÍÚ]Ü›•RŠÒØÊÕNMÞ’ŽM’Ô[N[LLR[R›SÌYN–MZPLSZSUÍ‘Ö\T^•ÕÝ•UšUÚMÊÓÝYÒQ\ZÍQZS™ØÚÞÊØÍMÚ–šS“ÚØÔÝ’‹ÔÜŽÓšMNZSSU^UÔT“Þ”‘ÜTZUÒUž]˜ÓÚ˜Ùš’RXÜ”ZÎÚÝ”
Ø‹Þ’RMÙŒY”ÝÎLMÜRÍ™ÔÔL•]Ö[ÙÜ^X]ÞX[ÝY–“Tž]™QU•TŒÛQÛÚÎPÔ]Rœ^‘ÙRQÚXÚÔ”™Ô”Œž™]œ–šQš•ÔLŒQ“Q›Ô™U›”ØZØÙ^ZZLÞÜÜ‘›ÖÒÒØX•
ÌX^
ÍÛ˜]ÚŒØRVR›UŽ\ŽÐ\]ŒÚS•UÓØL’‘ÒY‘PRL–œÒ\ÜM˜œœÌŠÝÙÔ˜‘š˜™XÙœ”
ËÙÊÐ™”YQÌÌPPÐÓTQQRXÔU‘]NœÔ˜YYšÒÜ]QŠÝYÌ˜ÔLÝLTÕVšÞ]ÚYÎR[ÊÓ™ÕÒÙ\Ú‘U[”““ÕTÛ]ÝÌ”PÑU”žSÐØUQÚÕ[ÞZÙÒ™ÙÑP[V•UÓÔ’–Ý
ÖJÍÛÔÙÙN
ÐÔÖÒT™–ÛTŽÓÓMT[ÓœÛŒ’ÕŒÊÔÚž[‹ÌÍÌÊÍXÔŠÔSNUÜšNÌÌ•PR‘•YÑRZ•Pœ^USž›ÐÒŽULYÚ–\“Þ”ÒÜUŒ•\^\›
Øž‘š“š\[‘™U[ZÒÕ’ØY”Ì“]”“‘YÓÙ”YM™ŽÝ–Y”MSŒ^š]NVž‘ÔÍSÒL–[ÔRÞ‘ÜÒTQÞÕ˜Ó•Ý‘SÔTL^R•™ÕJÎšÓÌÌ]›]žX‹ÑÓÞËÝVL
ÎÕTJÒQ[ÔT[Z’Ì[šZUÑÚ]M–•œMRÐ\ÓN’“ÚŽYR–”QZÔRRÒÚœÓÚœœQÓÜT“Ð™•UL›ŒÚ\ÞœÓ‘ÓLVSÐÝœÒP”ŽÙ›ÐMSÙžšžÔV•VR]Y›R‘“MTÌYÞSØSRÌÝRVZ›Õ“Õ]š“ÔQžÛV’ÓJÕ^LŒœÐ’ÒPÞ‘U[Ò›[Y“SP]›ÔÕRUÔMZœÝÒ]ÕšÖ[ÌÒ“™šÐR
ÐR™ŽVLR\L[RÙZU\ZZXšÓœNXÚÜ[MØRÙÙ”VP›ÚÌUÖÒœS™“Õž\ÒÞÌ›TPMVšNMœÜU•™š[™Ù™
ÍÐLÍÑJÐŠÍÎŒ™VPÌ”‘šUZQUžYPÕÚÞ›UŽQU’˜Z’‘JÓÓUUÑœØ[Z”PÛÕÜÚšÍ™ØÜÕÐ^–Y“ÙMM]R•T˜Ý[[ÝÞRSSÊÞVTR\šZÖMÌT‹ØÌZ˜ÊÛÐ•™žP”\T“ZÕÓŽLŒ“KÚ’’Ûžœ[ÑLZNQZL›ÚQ[ÌYÛRÔ’\Õ‘^TQœ™ÒRSMÚÐLËÔ›JÚ”ÞÊÒÞLÛ–XŒÖ[ÖVLYÐŒPYÖÒUU[Ñ”][^P[‹ÌV›ÑÔJÔÚKÎ\ÓÌJÓÔÑLÖœÛÚ››RZÒYÑQQXÒÜÕÜ’U–M’\ÍÑ‘YYÐ[
Ì›•™MÜ\Ì[Ñ[\YQÐMÞRQšV^Ó›’––VTXÓRÖŠÐšPÍÍÖŒÍÍ’›ž›ÐÊÑÝ˜ŽÒVÒ”ÑZÐÐMÜÚPÜžÓYÍÌÓÛVÓÖ\ÑSÑ]Rœ\žT^ZŒKÕXÒÖYÕ˜S[R’LÌQÛÍ\šÐÔT™Þ^™]ÝŒ››Ñ•Ù•œÔU’ŽQQM’[ÐZœÔT“ÔÍÍMÑ[ŒÚÔVVZSZÛÛTMÞ”’ØS›UÕÒŒœžT
Ý‘œV‘Ü[^RŒŽ\MŒ\R››’ÐUZœSšÒÍU’ÑÔMSÝš’V‘ÒÔÍÐž“^YÛÔR’ÔÞ•œ\[ÌÚ™Ì”\šSÌÙQLÓ[‘S[Ì\’ÓÕ’”•PÍUÕ––•ÛÐÑV[ÛÑY\Ñ’\]•Y[PYÚUšÖÔÖZZÝÓ’ZÜ^“–ÚÔ›‘QYÔU––\Ì•X“›VœÛ\ÊÔÓQÒ]Ø“[›ÚšUžQÐNËÛU•QÕÔžœTš–˜ÝMÝQž›™ÞŒ›˜ÓQÌLZ
Ü\KÛŽPž™R\SÝÝY“MS”ÓÎLž^Tž‘“Ñ^UÜÐ]ÍÍZÒÛ™ÌÞS[
ÓUS”œR“QU™ÑKÓÕ”ÎVŒ\œ^]“S‘–žÙRÛ^L\ÍMš’•œQPŽÙPJÐRÒ‹ÔÛŒËÌÎJËÐ“ÌÙ“ËÝLKØ“ÓLÍÌ\ÑÒÊÛÜ[RÎRU‘œ›URXVœÓÑLKÜQP˜Œ™Ö™[’‘XUXÛ‘•”ÐÒZP˜Ò‹ÕQTPX][Û˜[ŒÖ”M’ÔÍMÞY™“QÖžÐ“R
ÞRMXSÞš\ŽTPŒœMÎ’Ù\Ú\R‹Ò“šÌÒ]ÕÍÝ“ÖŽS‘šÔR‘ÍØÌÕ–šÖVYËÜ“QÔÌTÜÚX”ÖSÜ\ž\™žUÑÊÙ•ÐÞ™JØšÐÔžSš™Þ›LUØŒÚžVUœÝÌœ\T•\ÓÜYP][^ÐÛÖ‘]œSÚZ”RÑ\ÜØÐÌ”žšÎU[QÞŒžÊÛQV]P”ÎTPÒUÖ“Þ\^ZÎ]ÐÖT›T]”ÜšUÝÓPÌUÔŠÎVVšÒÙÔ’Î[ÛLÕTZ^’M’ÎQLÜ˜T™S\ØŒ’ÒÍÐ‘ÐÜZ^[UÌœÞS›Ú’•›ÔšL]RÒÜÜÝ˜M\QZÌ›ÕSVUÛ\ÝÒÒÛÒÐÓ‘ÎS^™Ñ]NKÍRMÜËÜÊÛÙJÝ’“ÌTŒ˜^•ÔYÒXÒR™ÐUSž‘Ò\•Z]ØÐ’ÙÕTR–Ò”ÞSšÜŒÔÛ\Ø\ÞMÕ›\QÔPQÑ›ÔÛÙÑÔ’ÓÌØ™Ú˜NšY]Lœ–‘›VT’QZÛØ•ÚÛ[KÑV”ŠÚÌÌKÞLÙ“ØPX›YÍšUSž‘ZVžYÒPÑÞÔÖ–XÓRMUTLÑMM”^’LUÍÙÛ“–VZM^UTÙ\Ô“Õ˜ž’ZØQTÎ[T˜ÌÞYÔ[ZÛ[™‹ÍÞXÔ•XÛ[M[ÖŒšÍÕ\’™”™“ÛÙRÞQ•ÛÔ–LØÚV[‘ÜÚ[ÚÑ™^]ÝÔM™SœØRšQUXÛYÍUQ[XSÍ]ÛšžJÔÔ’ÌXLÞÍQZ™YZ˜™UÞŠÔZŒ”ž[ÑÑQ[Ø’ÒÕÑ“ÔÖZUZ•“•Mš’ØLRÖRQVYÚšP•TÌ™ÒMMÎËÝ^‹ØJÔ\ËÓÝLÙ’Ù™ÛÛYÑ^STšÍÚZXUVXÚÝÐLXÝÐ˜UÙ’ÛTÍ“V–YÚØ[TšŠÚÑÚÕššÙLMJÑ‘Œ^LMM‘STJÔPUXØÑ™[™T\‘U“V‘ÛœÜÍÝÛÑYRÓZJÐRÒ™ÚTÑÌ–MMY^ÛTRRœÙ•›ÝšÕ\S\Ö\ÙMTÚY”˜‘PÓ›QMÐ›YZšŽY\XÓÞ“ÒœÑÛ”‘QÓœZÕšLÞUÌÙŒÑ[Ý™Öž
ÝÚMÓLÑØQQZU”ÐPŽPTS’PXÔ
ÊÙšYS™›KÙZÎN[]ÍÝ]ÎU’Q“ÔÒUÌšÛLÑLYšÜÎX”PÞ˜QÝ•Û™Ü’’Ò”
Ö™T‘ŒS’[‘Þ“ÐÐ“’Ö“ÍVYÝL]TÒÙSÍUVÔÛÐÕ–QÒ]ÐÜÙ]ÑTŒÑTœ”šÕÌ[Í]ÎZ•XY™Œ]TVT•VMÓTÝ““ÜUÖXULÐ’QP“ÛÖRT˜œŒ‹ÌœÙŽ›–MØUÓ]PT“YÑZÙÍœŒÛšZ^VTÐ‘\ÕVQÚUÛSÔQŒYÝY
ÒÔÝV“MžVÜÔYÕQŒœRXPÓYX^TØ“›Ú]LØš”Ù™ÌŒÌ“ÓÝÛXZ]PÔ‘’SÑÙ•Z–]˜ÛÒQUKÕÑTÛ\ŠØRÒ”ÑÝ]˜Žš››’PÔÒTœœZ™™QŽ]šÖŽÎT™Ô\˜ÎÑÙÐ“šQ”ÍQ[XËØ’Ô””LÝÑP]SÒÖžÑL]ÝÓËÒ’Ó\ÍÙ[Þ’^QUž’\ÌšMXÎMÍ™PÊÙÝÙRÛPUP’’Ö\ÕÜÑÞ•L]ÌRÎ
ÙKÍ‹Ý[ØœQ‘ÛÞšÐŒ’ËÙ“RÔRÞ\˜\žL™YŒTRQ’ÒUZMØ“ÕÛÎZR–NRÌVš^QYšYRÌÚ–TLÐ”›ØÍYNVÐÞœÔQ
ÚLÕ”
ÞYØ•UŒ’’Q”ÍÔSœSžQÖZÎZ’ÚÞ™ÕÓÖZÎ‘Û]Ö“–“Ò˜Lž“ÙÐZKÕÑ˜SÜMQ•
ÛÛŒ‹Ö[Õ‘Ñ\[QžVZ™šÚQ
ÔÖ•QÎXÚšXŒ‘œ˜ŽT™Úšž]š[MÛ\”Í™U^Œ•”ŒÛ\ÜÖ‘ÖXÖ™‘ž‘YV”ÍÓPRÕÕÝÛ[Ò’RYÒVTTYN\ÌÓÓÛ–ÍÝVMÊÜÕNNMÜ“ÌÌÙ’ŒÞŒ]ÙJÔÙØÔ’[ÕœÒ’[SVÒÒÍJÐ[Ò‘VÓQ[LÍVÜU”Þ]ÒRVÝŒÙZŽPÍÍÙYLž–™žL^œ[››ŒÙ›V”™YËÚÛMML™Û‘M“ÌÝ–KÝ“^“MÍZÞ›ÙØ“M[ÌYÚÚÝ›\ÔœÞ]Ì‘[[Î^[PØ\ÌÜTÛÞžÊÌ^•UœÜLXKÚQÍÓ™U^’Q•‘Þ•PZQXTŒÜ‘X™ÎZÒÜL“–NX\ZLš’TÕ”ÒÒM˜•ÙÐÕÖYÝMœUžš
Ü™’’ÓY]\ÛYYTÌKÒœÕZÚ^X^QÐÖœ\“‘
ÑJÓÑYÍÞÑ˜”U]”Õ\ÞYœÚQÒ˜ÜŠÓ‘ÝœÞMRÛUYÌÔ^•ÙJÖ
ÛÒUQ\\ÝZ”S]Z‹ÍÜNRSŒÜ’ÚÒÝØËËØ–Ù™^“˜[Y–TÌZL]–ÔÔTÖVZ”\ÝXÙŒ”MÕÝYÚ›Û\ÕÛÐÐÍRXXÜÕÊÛ˜ÝŒ™•ÓM^P›Í’›Í’“L‘ŠÍÛÝÓŒÌÎ]ŠÙQ“Ò“\Ú^˜ÚÛ›[RYÐÔZŠÛÐŠÒœ“V–œP]ÐÚÌÒ•ÊÚÕNPŽZNPÓÓRÚÑY]Ô’˜•ÔÑÙ[•MYÜžU[ÚUÎÓ‘›ŒY‹ÕÌJÊÜUVšÍQž[YÔ•UYÑÚÚ”ÒÝÕ™Ó›˜“”P^MP[ÍUÍÊØÙNUSÛUX]ÜÜÎL]T“ÐÝÝÒ]ŒY’Z\RÒTÎVÊÔÛÒQ”ÑY‘ÞÚÍ˜SÒ›Ó“šÒ]™^žœ›XÞ™ÓÎM”Õš‘SÒ“ÍÛ’ž‘š[ÞZR‘ÓÍÑž’™ÓÞÕŠÊÔZ™ÜLÌÞJÙZŒÔ]^’ŒUÐ‘ÐMUYL’^M\U“–U”]œR“P^“QTZÚž˜ÖUQQ“YÜšœTØÓÕV™Ó–™SR™Lœ“Ù‘YÙ”T“ZÜ’RšÛ\ÕRœ‘XVS™Õ”–YÑÌšÕSRS’XVž‘ËÜLÕšÚR^V’™Ö]RÍÛXÒÕPÚ]ÎQUVXÌŒÕ‹ÒØU]TÕØ˜RVÞTÐÜœÖ]ÕÚØ™ÔSÑÒ™M–œUÓP“T™ÞXKÒ’ŠËÐžÊÐœŽM˜RÖNMÙŒU“”ÞLÑÝ™\ÙÍMÌ”Í‘œ‹ÍžR”ÛTÚV›S™‘TSQ’ZQNÚÙÎ]SÍÚZKÙ”LV›ÎØÙ”Ì\ÐRPQŽYÐKÔ’U^R‘‘›TœÔ’ÜJÑ”RÖL‘ZÐŒ\‘M‘Øž\ÓÔšUŒSP\ÙŽQÌMÛÕTZ˜]YÚ›™ØÒÔXÛÛœUŽYØTš[NYšÔKÙJÚSTZMVš•RÕ^S‘JÓÍÍÜÙÛTŒ^LNR‘ØUTÔL˜šÒ›ÐÐ]QRÖ^RPSÝQSÑŒLš˜‘V›TÖ–JÔžJÚÍÒÑ’ÙÌ‘UšËÖšÎU˜ÜŽS‘ZR^™RZÒZU\ÑÛMUœ•TØÓÐR]‘ZžMžš\S•ÎQ
Ó^™T•NPÍKÕMMQV^ŽQR”›NRNÑ‘ÐTÑV“•ÒÐ”›žPÐS“ÜVLššÌ]KÎ””’ÝUTÞ]Ü[™\˜RÑPRPUQÜØ™]Ú]”š˜Ù’SÍ]][ÞÖ”•ÑÕ[ÜÛ›ÛÜšYŒSšÕÖ•SÙTŒTÌQØÍ’LTÒULšKÓ“›[“Ò[œÕTÐØ•‹ÍËÙÌØŒNQÍšŒž][ÛšÒÒ[ÙÙ”XÕQ“ÖÐËÓ]M”š‘ÒÑR\’[Ò˜QUÌYQVž\’
ÙËÚ••Ó“ÙØVÌÔKÔÍZÍÙ]ŒSÜÔÕ™Õ]]ÝÌž‘Ð^NV“ÝX”TœX’ÕœŠÕ›™ÕTÒMÔUÞšËÛ^]Î^PTM–™ÐÙÛ]’ZÓÞPÒ‘ÖLÙ™TS“Y˜ÞRœZ™MÚ[ÑT]™šJÜV‘ÕNÌQÒž“–ÒNVU˜Ý•‘šš\QRšR”[[‘[S‘”ÔžXÎPÙ™JÔÍÌZMÙ™™–ÝÑÒŠÍN™QÙKÍ\ŒÖžR[N^Þ“ÕYXÒZ›ÙÚÚžSÙØYÜÙÒ”]^YŒSX\›ÌÍM]ÕPZÒSÛ“L››’ÑØYY™]X\LŒŽM”ÞžÊÚTÕÓÚŽÞ˜ÙSÕÖ[R^ÍNÑSÓVVKÛÖ•ÛXŽÕÔL•›ÛÕ\˜•”Ì]UQ”V˜ÜÞ’•ŒMS‹Ó‘ÝÞT•Q•Nœ’]•ÐÒRSV•Ž]M–›–Y‘X^Û‘Öž‘•š“›ÒÕV™–]Õ\›MYZÒÌRZ\\XLUÜ™ÍMX‘JÍR\›\ÓÌÍ™
ÛQÕØÓT™^QŽ]Œ–\MšMŒXMÛ\T˜[LQÙÓÞ˜ZÓ•^žQÛŠÌ“Ñ]N‘MLQÍ’XÜÕLÚÑÖKÑ™•Q‘ÍMœS[ÔÞ”›ž\Ò›ZÖMÐR]ÔSžTUUMŽÝKÜÔÓÓŽ
Ñ˜ÌÝ›Œ›^™ž’]LšÐÍœVR‘MZ‘M[‘Ú“Q”ÎUÛ^\–T™Ô•–S”U™ÚPÐ[U’ÒÒPÑRØÌ\™‘ÎMS‹ÎXZÍÌL™”ÜÙVMRÒÌV’ÐXSÓÚ–‹ÎÔÚŒŽ^‘LŒ^TÓ›SÑ˜ÕÎRžŠÕ
Ô^
ÓŒÒšX–™”ÜYYPÜYÚ™QY^LšÐ\Ü™Ó”š“Vž˜ÓÚYÍ’XZÙPÕÔYÒZÞ›ŒQ[ÔRŒ’ÙŠÝ]MÜÍT•ÙYÔÎÖ”‘Ú‘•RNP”RÒ]T‘Yœ•VTPÕÓPÐœQÝÑÒšÝU˜•œRP[ÒœZÒÓ’\ÌÍ[T˜ÝXÛŽ\[Ó\SŒ”ÖS‘“ZÒ–›™–›Y[ÌY^’ËÍ–žÚÞ›˜Ò^TÞM^ÛŽÊÛ‘ŒÐÑ›•VVS’ÑVTÞžZÛYÝËÍ™›LÙšV
Í›ŽL]]N’ÖRŽ^œÞšÑ\ÒQ–[ÓÚ”ÛQ\”ÙÒQZÒZÙÙÜPYÙ“Í‘SÚÙULJØËÐœXÚ“YYT’™“ÓÒQœVL\ÛSØ\Ô\R[””›ÙÖ”œZXL•MŽQLNÒÒÌ˜™^ÚX˜žÐ’ÍTš’ÙÌQ›“ÌÚÒÝQQLV\ÕS”Ý™[œYZ›\“Ø^Œ[ŠÜÒ’ÝÕYR]Ü“MŽÓžSÒZUNTØVY]ÍY”\™ž
ÙKÚUœÖLRQQSTMP]XÓ[ÔZÙÚÒZ[P’RQ˜“Ö•M™šÜÚ]ÐMM’LP[ÓÐMÐÕ^™ÛPÒÝML™\ÙY\“ÓÞSŒŒ›TYÐÑÑYÑÔÕÖ™“XÒ•ÎMTÕÞ^\ÖŒš^ÑÎPS–š‘ÑÚÕ^™•ÑÙQš]–ž\Þœ••SœÓL’”U\Õ˜\™ZXSÝMÕÜÓQ\Q’ÔYÛÕ•“ÓÓÙJÖØY‹ÔØJÎTYMÊÙ‹ÎØšÒRQÐPÕPÒÕ™ÔÚP›œØÌÓÔ]ÐÒPÒYSÞUÛTLÎPÔ˜–TÑÓÍžÕTL˜”LMÚœQ\Ž]–ž
ÑÖKÚNKÛ“[ÎRTœTÒÔPPJÒ’ÚMÔPÛUÎNRœÜRÒšÓ•ŽPÌ”ÓUUSšT’ÓKÓ•Ñ“Z”Ý]ÚšÓ^^Z›ÐÜ”ÓžSŽJÍÌÍÑœKÙ’‹ÛÓLTÍÐUÒTŒVÍ’ÝZŽ^Vš”\X‘•]XŒ”ŠÑŠÞ‹Ñ”XÖŒNŒÚRœP“TSÌÐUÛ˜œÝÓ›’ÒUØÖžÓÓVTMÛQ“]RÙ[Už]ž’\’Ò’LSÙRÝQM™ÚžÛÜ’Ü\U\ÌVšSMX˜[YY‘ÍÞJÔšUSXÐTÌ•ÒÌQÝY\ÐŒTSÕÕÕÚ›LÑT•ÑÙÊÚT^LZœÌÙ
ÛTÑ”^U’’•X[Ó›ZJÞZÜÓš‘Ì™ÑQÌØÛÌ›VMÝÌž‘Y[UÖS
ÓÎTS’ÓQÌUš›ÝÞœSÛÌØ[QÒ“ž•ÓœRÔZRÞŽ]ŒSXÜØ]LÖÐÑŒLÜ]ÔÎ\NÒÎQÜÍœÓUÓ’–JÑÝ›Ý[ÓRURÜÑX\NNš•T’“ÐZÎVËÌÐÌKÍŒœKÊÛÌ]™™]JÙMÍÞ˜KÎÌ]™]˜˜]Ù•ÖšÞR^R’MÛÎÕÝLXÌŠÓÌZ^š“TYÌ^›–›ÝÌ]L˜‘ŠÍ’ÔÍÑ]Û’ÓLNNUKÞÚš‹ÊÞQÍPÑ\ÔÒQ^R‹ÕÚ˜ZYR’Ñ^•V›Ü[ÙØ‘Ô^LÔQž]^\Ý‘ÑVZÚŽ™Î\’ÐÜLŒTÑUÌZÍ“šP’–™šÖRØPœVSšÊÜÛÐSÛÞTš•UÕ•ÎZœZÛÑUÜ›USLÌ˜ZÑ^JÓ˜VŒ\–Õ]LÒÕ›ÜQ]TZÜU\žŒØÚÒ–”UÝ™ÓËÜUSPN[]LT›Ý]ÑœœÙÔœÍÑXPÎQËÖ›QšÒZÕLœÓV”XUR–ŽÕLÛÑ–RUMÑØšQTSM^PÙÚØ“Ž^^\ÊÌÍÙ˜Ô]ŒÎLŒÌÞŽUR˜ÒRY›‘’˜ÐÑÜ‘ÐPŒžšÜRÑ[Ú›Ø\ÕÌMŒNXVUÜœÕVžÑÛ›•ŽT]TÙÎT“ÚL“ÚÔ”\[
Ô™Ì‘ÊÎYQ”ÝšÌ“ÓÛQNÚØ”‹Í”P”^LžLÑ[Œ[[žJÍ™YKÛ”ÎÜ•STÐTJÖPQÔÌYTÕ•–•’[ÌÕŠÒÜ™ÕRNœSÑ][ÛKØ
Ò‹Þ–ŠÎP]Ü\ÔÎ›M‘VÖ–”TÞ›ÞUÓ[X™ÌM˜˜ØÓÑPMØÜž\ÜÖ•ÔQÜžVQ•[›‹Ò›ÒXÍÛR^‘ÔÔRÒRÙUÓ\•Ù•Ì”ËÛŒMPÐ‘TSXÙT[T‘MJÑ]YPœKÎÒÛ›ÖÖ]UZZL^ÝQXUÓÒSV]Z•ŠÞMŽJÛÐM›–[Õ]•Î›SR“Zœ‘LÌ™KÑÕÍËÖš›YœœŒ[ÖœŠÔ
Ù•QNÚÙRZMÝšžRQ“ÕÚ“Ö“TZÜŠÕ‘MQUNQÓÐSÞ“ÞQØØÙ–N[XÍÍ[ÍZÍÚ›–“RÑÝYÕœœšYÛLÒ’‘‘–•ÐŒ–]Ô[UœÜM”LÛŽVØ^Œ•ËÌRSLÎT‘Ì]LÚU”R‘ÙÑQLÑŽKÑÌ”YQXÚ›P‘”PUœR‹ÐÓÛÛTÌ\ÌÓMœŒÛŒÝÒSÝÚ™Ñ™JÕÜŒÎ™MÝ”Ð™ŠÍY•ÍŒÎQÐÚ‘PYšÔ•Ú™[ÚžTÚ›ÒÔKÞÒMZšRš[VPXUÐY–VSÑ[–NÍLÙ”žUYšX›ÛŒLQ\TÜTÐÐRZT–ÑY^[’Ó›œM›–UÔŒÜÙÜSÓ‘[š^RUÊØSž‘›UQÙÚR•Ò‘•YYVT’žT[ššÙÌ–ÛÎÛšÍ“ÜÔV
Ù”]œ”ÑŒZ–MZØÑR˜V™Ô‘RšÚÍÞTžÌÑ–‘”PÝÐMSTTÍ\]’Ý–““ÖTLœÑ–ŠÞÚUÝÐTÑÙRPÒYÚÙÙÖYÓRÓ•ŠÙPÞSTšÓZZ‘‘ÒšÑÎQLZÕÒÒ^ÜYÔÔ
ÚÙØRÊÎØØTPQ
Í˜[ŒÚÝËÒQžYÖ]›’ÙŒÔÝÒVKÐÝÓÐØÐSØÙž›ÜšÔ^œZ’”Î[ÛÒTÌ™“’›”ÐV\Ü–žQÒZš˜ÐÛLÙZÓÍŒÒÛ’‘ÍØSNSÛ“ÑP\ÚÔÖNYÕM‹ÑÙÞœÝ“ÙŠÓÜšØÌN–]•ÍÜ’ÓÌž‘ÛÒ˜^–]žUQ\Ù”–›•PÕÝÍ”ÛŒZ]M[ÊÖKÔ[UÝ[–•šPYž\Ó“šØ˜^RÐÔ[YÒ•ÚÙ•MRÜP™œSžUU[SÛ˜”ÝTŒ’ZÛUœ•SL“Ù^V™›“MVL[”’[]Í\Û™ÕL–žŠÌšÔÒÑ“
ÎMŽQÛ”’™Ù^ZM
Í’ÛPLN]’ÜL‹ÐSÕ]ŒUÜTTS^\–^\’ÞUŒRXRÓÜSXT‘[Rœ›ÙÜÛ\ÒRÙÞ\^Y‘ÙÓÜ‘ŒÙšÕRÕÚ’ŠÑ˜ÙœÑÐ\œŠÜšÍ•T˜œT^R˜ž™Í‹ÐÙ“™žÓÝŽVš‘ÖQÙPT]ÝŽSŒÙŠÙPŠÞØNKÑ
ÊÞM“ÍÒÞ‹ÓÝËÝŒŒÎYÍØÑÝÙ•Óš™–ŒœÑÑ
ÞÖÎ]•X”ZÊÚÚNÚÛLž–‘Û“LØ^™]‘ÖŒ]LØššœžZSÓÓÌÖÜ›ÚMMÓ‘’ÚÚSÓÓÓÌÜ›LÎÍÓÌÝ‘ÔÒÙ
ÒÛ
ÚÍ•V˜V”žžš›ZZZÜÚÙÛÜ‘^UÝš‘ÝÕÙ‹ÜÌÖÎ]RœÐN‘ÍP]ÚZXPPZÛSÖMšÌ]ÚQYÜZžYQÎMÝœŽXÙ•ÔÕ™Ø˜ŽMÜ“žœ™‘šŒÖœLRÛ\ZÍÝÎYÔÐP^‹ÝËÖ‹Ù]PžV˜ŠÎM›Ñ]M“œS[]YœØÙÛÒÙR’ØY•LSÍÔŒSÚÝÝÍœÔÐ˜›PÔÜÕÚÍ™”QSÐÐžT™VQŒ˜šSÎPÜ’MÕQ“NSÌ‘NX^^RÑXËÕJÛÌP[SÑ^šœ^™TMTÌÑPÕXÐ‘‘ÒRÙÔ\ÒœÊÛÐÖSSTLÜQKÚJÑŒNZÕRMT‘X’Ž\‘ÐÍ™[Ì“YSXLÛS‘Z[Ý\Ô•ÔÙÛÝŒR\Ö˜Õ˜[”[š]ZÑ•Ú[UÛžMÑÑÍÕÙQPSÜY•Ì™ÒX‹Ø\’^L’–RZËÎR”™ŠØÕRNSX”MÌŠÑÛP]ÑÑÐVŒ‘ZP“L™ÍŒ‹Ý[Œ’žÚ•ŒÒÍÊÑQÜ]œXÛ™[ÔŒÜžMÛ™\Ý™‹Ó•^TÚËØŽS™ŠÝÕ]ÒÑÒ•KÜ–ÛÌÊÎY‹Ì‘M[Rœ\T\TÙ›P™ÜÌÓ[œÖKÙ‹ØÑY^ÔLŠÙYÌÚÑÛT”ŒLÑØœRÝÝÝÊÒÎYŒ]ØšL[œœÔÓÛMØUÌVÔ’ÓJÐÙXXÜÒU–Ûœ]ÞÊÕ’ÎYÓRÌ]‹ÌÍ[ÛœZV]ŽMÐÙ
Ý’ÛŒVZ›Ð•
ÍÕž™Qž]ŠÛÌXÌM]NMZÒÙ\LURMV]Y[Üœ”SœÒÚTRÐLÛŒVSNP”X˜QXËØV’^RÍÒ–ŒP\ŠØÒ
ÑÖœ^ž–
ÌJÎ]™
ÔQ]ÝV[ÖT‘™ÔMŽPÜ––ŽUXÛ’’‘PÎ““ZURJÝ•
ÑÒ›œÎ[PžZŽY‘\XÑÕÌ•ŒÞUS”Ž\Í]ÍÔØKÙš“œÌ]Øœ]Ì’›ŠØÚÚÊÑØYÔš›NSÍ’QÞ”Y›NR–]˜ÛœÝ˜ÌÜÝŽÜ–˜ÌÚÝ™ÚÝŒLMšNLÊÞN^ÌÜÝÙ“ÜÎXÒVÒNU”NÙÓQSÔœÔÙžž]”^ÚUKÙ‘SÔŒ›ÎT[™QÑ••ÕØÎÕÜ™ZÛ™STXÔÜ“’LÒMÌZÌ^YULÓÎ\”T˜›[“ËÔÕ‘]š]Ñ“Ü‹Õ‹ÛÍ\RQÝœÜ’š[ŒLÓPSSÕšÕÖ“ÌÙÍLÊÍ–LÊÜY•ÑŒØÔSÛ›LŽ^ÙM–“]Ì˜JÍš˜ÍMÎMÍKÝ–’’ÚRNÍMMMÞX^V[[Ñ™ŽTÖ™ÌÛžLØPÜÝU•Ù[ÓÌÙÌÌ•ÙXŒÌ™Ö•Ù\Œ•ÊÜŒŒÔ[ŒŒŽ]˜ÑÎÐÒšÛ™ÌNN\RÕSTNZRM•]Ì‘ŠÍY[ÔY–]ŒÌZ”’šÌ“XYTLÞ˜ÐœÒ”ÜKÒšZLÑXÚÖÍÞÞ“RšÔMYœ“–Œ‹Ð™ÔÑ\ÐTY]SÑSÛÓÙÍÐžPRœÛ–XÌQËÎX]ÖNÊÒÙLÓ˜–T[UÓÓŒ[JÑ‘˜ÍZLQž™–šŒ‘ZMÓP•ÍÌÓ\ÛSÎL–SÍÊÓŒœÚÝ•ÝÐÓNÔÔ˜œÚÙQY^^”˜ÞYL’SÒUÓ‘ÙMÞ‘XÍ’ÌÔ”ŽVœœLšÛžKÐPžQMÑÛ’™[RVQV™™’˜’S[ŒÝŒ˜Ô]œÐQžRËÛNUžŒSÍÜPœÛKÔS”
ÙY’žJÑžLÚŠÍ^šŠÞØPQÜÌÜ“ØŒÙX“™›[ÔÐ›‘TNYT\šŽ\Y“Ú™”ŽÔ]ÎN’ž•ŽSÞNL™^M^ŠÞJÒ–˜ÓÛKÚÙœN[ÛQ›QÑ™ÛÑšÌYRÝY\]ZTÞš
ÜQÛÙ˜L›“ÛÕœ\]“ËÑQØÚUQXVYÛ‘Í›ØÓÙUÒ\Ý\L[YÐÖ›•Í[ZS[]\Ž’TÛÕÙÛÙÑ”QÍœ
ÞYÑÐœÓPœ”’Õž^V”ÙÕKÒVŒÖ’˜ZŒ–ÚULLžœXÓÑRLUR’SJÛžØš
Ý^PÎš˜Ø”\œÞNZŠÒUP’˜šŒÔØšÝ–VÓ^Ž]LÓXPœÊÖœSÊÌ˜[U
Ü”ÝVPÒÐ›ZRÙÍZ›Ò““‘URN‘žÑY]ŒÜLÒ]Ô’ÔÞSÚÒ˜ÐQÒœÐÞÞR“’’–•[]ŒL™MRUSš\ÝS\]”ØRÛTØ•›QÔ›ÙUR–‘œMÎMÝRœÔ[™™ËËÑÑØ™QžPMÛRŒÚÕPQV[]“\YŒœYŒœ–“Øž˜œÒÌ˜SÙYKÍÙ•‹ÎYTNL]]ÖSš^\ÕÓœMSÑÐÚ\ÕÓœLÓQÐÙT]›UPÑYQœRQ›[Ô˜“–TÍÍL\RMP“QZUNÍ”›ZL›[ÌÛ^ULÌ’ŒÌ›
Ò’ÌÌVS]““ÑP’ÔTÒÒ•ÌRÑSÕP˜ÞYÚÌQZÜLZÝÕÛÔŒ\žÒÙØÚ˜NÖ’R“T›ÙLÓÒØ‘ÝÎNM™”ÕœÌŒXÞ\ÓTÊØÙMÝÖÙ‘MÝ’Q’‘\[ÚØØ˜Ó\”\ÌÒ›šQÕP”YÙšQ›ÝÝRY”–^Ì’ÚÔÙŒÒ^QŠÓTÛSÔÌSUUÛ”ÚZÛ‘–ŒœQ•YÔRÐPŠØÒQT“•ÎYQŒ^™™•Öœ\VYY›‘žŒMS˜••ŒNMÛ\YœÌJÌžT“U›
ÊÒUÝÖ•šÐ“ÎVT–˜]NNNTž[™Ù™‘ÒZÓœÑZÕž••]ÌPQšÍÌ’ŠØŒÌÝŒÒLÍÌ[]ÜQž”JÎSÐ˜QÑŽKÞ•[NKÙS™‹ØØŽ˜ÙÒ•^]UÎY–KÜS™ØŒÑ”Í˜“ŠÙÔ
ÚÓPRÍV™’‹Ýš[ÝU\”Y
ÌVŒV‘ÖŒZ˜ÐZ]˜ÜÍ™ËÙQ“–žÓY\Œ‹ÒÒÜ–ÌËÔÓT]Ø[šYÊÑÑXÒ˜U™“ÑUXMÛÔY•YSÓÙÌÚÌÌKÓÜžŽ”[ÑÖS•UØš™˜“SÍ]ÐNYQÝKÜ^‹Ü““Ý–XÜÞQÔÞÓ[ÙÝÑÔJÙNM“•JÜZÙYÍØÝÓPLYÑLÜÔ–ŠÑÕ‹Ù
Î]‹Ð[™ÙÖTËØ™Y\›š‘TÚÜ[ÝÕ“ÔÝY[›Ý•^œ[ÎNYÙÖŠÓQÞ]•”T”T]\ÌÛM™Ì˜KÙT[Û\‘‘‘ÝØÒ–\TŠÓPšJÝQXÕ™ÛÝY›NL‘™“ÐTÞÒ]›QŽÐÔMÎÒÐÒÙ™ÙYÒÝÕX‹ÝŒZ‘š[ÛÖTÚ•˜[”“‘›ST›‘ÒÍUNÝØŒÚ[Õ“\ÖÝVTÒKÒÕ]TZÔ]“ÒÔM›ZÜU[Ò]Þ^ZSPÌÞNLŒœÚMš””ØZQÒM\–[ÌÒRÙ–]ÙÔš]ÒÐÕ•ÎNÔLØ›ÝÑÚÜ˜’žžQÍ™ÞM”Ù›’R]–YÌ•Í–]]Ý›\KÍÚÜÙšULP˜“ÙÍU›\ËÞšJØMV”]˜ÓŒÐœQ”XÚZ™ÎKÚ”™PTR™Ó”ÚÛ“\“ÛÙ’ÕŽÙQÙ•ŠÒSRQ^\PÞ^T‹Í›”[ÑRŒRJÔÑÊÔÝÓ•ÝSÓÙÎŽMÞ›Z]›ÕQÓQ“ÕYØ–š[ÔÛÙ“ÛÓPXJÓÚ•PYZŒ–MNŒÙËÐX\PÜ™ŒÜJÕ]URQŽ–ÙŒÝ“ÖšÜÑÐPÑ›KÎÍÐ••ŠÒV–]ZÑÙ[ÍÌÙš]•ÔŽ^S˜šÔLÛÖØ™”TØÐœYÝ”SÛÒY‘šÞL™ŠÝÞËÐÊÎLT•ØÒLÎUPÌM]•ZP“Œ\LÙÝÌ“ÖLÕÛ\–ÕÎÖNVX]™œÜÌT–KÔÍœ›R›œVYÐUUÑÐJÓÝ™ÛÙ›ÛL‘Û”™M’”]ÎLÎÒ–]\ÑÊÞL[ÑÒY[Ò›RÜ\›YšÎÕÜ•V^ŠÙÍ›UœY‘ÑÔÌÞLQÔÛšÙZY›YTžžYÔMÚMTÔS“ŒT“ZR”Ü\RS•]ÕžŠÔÔTÛMžZŽ
Ö‘VKÝZ[Ó•NÌJÔÊÕ’”“ÓÛ˜\ÔŽÜ]ÊÚ›ÛUPÊÓ’Ñ“JØ™šÌŽZRÓ“ÖÍÒPLÍ^™YLZÍ“Ý^UÙÍÑL›•ÛŽYVÝ”ÜØYPÑ‘QPSÌÖ’œÞÒÚ[‘ŒÙ[ÐSÙÒRTÙ”MÔÜÑLØ˜QØRÌ\žŒÐÞPU[”U\SÍÌ“\Rœ]]œÝJØLÛ™\”Ú–ÔŽNSœÍ
ÒRÝ™›Ö’‘’[•š‘ÞŽZQÓÓUÍÝÚÚL‘Ü\ÝÛÞ–[VÙžSVQXÌ’ÒUÛÕQÚÝØQ“ZS˜Ô“›–RÜJÓÝÙÛØœ›žS™œVYÚÕ–KÒYU›ÛÚÑ‘YÙ•ÞT™NÖQ‘œŽ•Ü’šVš–ŒšÐ›™Z™•ÓXÖRØž‘XœUÓ\ÌÚÝ[•œR›NJÝ\›\QVU™VŠÚVÞM”YJÌ‘ËÖÛÔÚS›^ž•ÎNYZX\VYYRÎS”Z•
Î[^‹ÒŠÜÛLLŒÜŽMÜ]ÐS˜Œ\ÌŠÝŒŒÙÊÌÍÙÝ–™QÞSŒNÐËÑ“RRÝ]^TNN‘‘Ùž’SYQX“ÕÞÌNÍÙ“ÕSÌŠÙT[[]••TSÎ’ÚÒÜ›ÛÒYÓ“ÚŒ•ÓÑÞ“\Q”›ÙÙ‘UÍ^šØRÎ[TÕRU“ŒZ”’ÚQÐ]•S”Ùž™–U™›L˜ÍÊÍŒ\ÊÖNY™ÐÎN]Ù•ØÍÎ‘X[ÒÔÙËÓ“”L^™ÎŒ™–˜ŒÜÕT™TÌ\NUÖTY“‘•LJÑÍÌÍ
Ô”Lœ\˜\˜‘Í\M]œÐ‘Ü\ÌÑUKÐYXØÌQ
ÔÌ˜•[JØVš
Ö^ŒÑ™Ö™MM•“QÙÕ™ÌKÝ‘PRÑÓÑÝ[™MÎ–›“ÚËÍXÑKÌÝÕžŒ^ÕËÑÜÛ™ÌL’Ù
ÛÍN–‘PÚ˜MŠÝU“SÐVQÍ\YMXQYœœ‹ÍYÒUTZ[UP–LœKÞ”ÚÞœšÓšYR‹ÞQ‹ÓžUU]SœœÌ’Tšš˜ÕÑSTÐPÙ•ÓÕ^ÌÍÚœÒPÓ‘‹ÑYSKÑ™KÞŒÔ[L•Ö\]ÓÞT™ŽQÓTÍÛÛLÍ™ÒRœYŒšZÙUÑÒÚLVÍ\›Ö‘ÎTÊÓ•[ÒššJÎR‘›ÛRÖ‘ÜÒØUŒÞ›ULŒQMVÞ˜YÔQÔZU\ZLUV\QÞRZ”SÐQÜÝUÍÔMÓ™œZ™Ž\ÔKÖ›NXZÍTPRZŽ‘ÌÙÖQØš’ÙÙ–]ÌPÕŠÚÓT]ŽZT–›]ÎZUÜœžN’ÕQ^˜ÑMPXÝL[RžUÒYN^R•Ø™LML[RŽTÞš“˜ÌØŒ\ÍÓÝÑPÜœÍ’ŠÊÝÓ[šÙŽÑÝÍÓPÐÎX–›ŽYRœNÎÌÒ[UZSÍÛUÜÝÌÍLÒ”‘’\UY’“œ•Z’ÛžPÛŒÑMS™ÑÓÛÓÝÚÊÐÛœ[•]˜ÜSš’ÎZÌJÙLÓœÙ\š]UÚZ[^œQÓšLÒ]XŒÍ\™ÕÞÙÓÔTUM[˜RŽL’ÛÑ”]RÕQ•TJÜXM“‘’››UÝŽRžUÛR”œÖZYRÝÌšT\LÚYZM^˜Ò^•šÔØ[ØÜÝQ˜‘[VMÛÝRSÒÔ]™Ô^P]™T™ØYÍÒ›œÙ[YÛÚ\œØ•Ø˜ÌR˜Ø™SŽU–Ñ•ØØ™”[Z“ŽŽ‘ÎÑÖ”JÍU•ÒÙÐM
Ì‘\‹ÔÐLÛZÛ™Ý–ZŠÚÛV“TÌUUZÍTÍÕÜ™›ÔÑ“UUXUZžM“ZÑ]T•ÍÌR’URZ•Î\ÙZVUÞ\’ÒUÒÕŒŒŽÔLÐÌUN[”ÕÝÙÝT•”ÖP‘œ›Ž[P–
ÎRŒœÑ]U‘ÓPÑPL“ÑLžRZœËÐ^ÑKÔ•Ý›ÜQ›–[ØTV
ÜÔÔ–KÑŠÖ˜LNXY”ÓÌLMX“ÌÑ
ÜÌÝÍÒØ\Ì‘ŽM™[šS“X‹ÓX]Ù•ØŠÌ\ÛŒ]LŠØÌ•Ò“LÖ\˜“ÛY”ŽÝYR–RžŒÝœÙ]RZÙ^’ŽJØŒÛ^XUÓ^–‹ØR\žš]NM“
ÙÓœ[ÎMÓž›[–Í•Q[
ÝUU‘^M•žTÛÝ\•LX–Ð™QÕVœSÛÛÝRÔÜZ–Ó›LŽTŒŒÙÒ”KÌUŽLÚVNMZšÒP›ÔŒŒYYÙ˜ÖSÌÐU›]“ž^ŒRŒ˜PÊÛURÚÍÕ“ÊÛœŒÍÎPT•SÚ–žM]šÑUŽÝ‘“˜Ì^[œ’ÌÕÝØMM™MžMVPQÝÔ™[MÐÝYšÝÛRTÛNPKÑ^™Zœ•Œ”š˜UR‘YœTJËÜÖYUÑÙ”UŒÓš“L”VV™’Þž™N^[ÜÓSËÑŒÒURX“’“NUœÚ’‘\ÚTÍÙÑ‘ž[ÌMšZÛÌ›PÖ’žÖR“XLRRRRU’ÚØÒÛÜ–SM’VÌSÙ™ÑÔŒSZ’ÐœÛšÙYÝÖ\]–“šÜ[šØ–‘Œ\Z›šÌ]šLŒ™TVNYÌPTØ”S™Ž]‘ÒœLÑÚZ[ŽVRZÖÌØÛÊÓÛVÑÌLUÝÙŠÛÜ”™ÕÜ”UV˜Õ“TžXÚÙÕÙÍ›–YÝÛVMŒXÛ[QÑ™XØÍU›ÒLLXTÚÙ”Ð•ÚZMØÐN•ÔT]ÌÙÜÚPŒÑYZœÞŒÒQÑ‘ÙV‘›ÒUÜYÔLšÚœVÙÜLR–TZ™MÞÖ]R™ÕÔX•PÊÙÝLœœQ˜˜ÚÎ]UZ”ÍšÛQÚÞ–šÛ’L•Ô‘ÒšRØT›˜“Ú•SÚ‘[V™ÒVTÑUÕT“[NXSÓÝ“™ÐYSÜÖŽ]™ÔRŒU‘Ž˜•Y’NRÌVÚ“ÌPÑÙY”™ÛžœSÝ•MÕÓš“•ÑžZYÍTR“ÜžX•UÒ›PÖ““Õ^œÑ[JÛŒ‘ÝÒ””ÕÓÙÍŒPMÌXÒTœÔPÕÑRZÌ’Þ’ÜÌSœPÐžMØÒVX”ÜQÑÙÝ‘Lž˜SLÔÝLÔ]Òš^ÒPÑT^ZÑÓ™Ó\KÑPÕY‘]™Ý–Y”\‘[ÍÍL[T’˜ÓÎY•R[œÞ’œÝÞÚÑ\ÞUÕØÖ
Ü›”ÙÕ˜•ÛYM
Þ\š[ÕU›Zž’\^ŒS“XÚP–Y[ZNŽUUœÔÐÕÞ\šŠÔÌL\šQ^YŒTŒÝÛLÓSÜÎLÛÊÎXÑÒXUÛÚX[™S[Ø\Q
ÐÎY›ÍRYÌTZ–‘KÙÝQœ–‘œYÒÝRZ˜ÐÔLÒÑXPÚ•RÝJÍXšYQÖ‘[NVÌTÚÌÙ]MÎLZÒÖ“ŠÚLUQÌYÓÙ]ÙÖ“YÒÙ]Ø˜ÔœÑÑQÔÎLPÖS[QYÌ‘–ÙT’ÜR–•ÖQ“TÕ]ZP•ÕÖÌÚÎURRÕYTÐÓÙL›”S]]KÝÐ]Œ“›ZQ“YššMÙšÒœØ^™Õ–”›œÍØP^•SœZËÝ]Þ™šMQ^S’ÝÙÔÓ™ŒŒÑÜÜÙŒÓÑÓ™ÎL“ËÙÑØ[^š[“[Ð™SÖ[ÎYÛÞSÛ]š–Ñ”\QÕ]’Ò‘ÜÒÐNR\ÖXXÌQ^ÝØÝUÑZÛMXZÚ’’“–MÙÕSRÑ^™Ì““Ñ’PMÒ\L•œRZËÜÙÔÕ™TÔRÜZÙNQ‘^Ž[T•QNPXQÖQYÙ›Ú˜Ó’[“LU›šœ™ÍÞ‘ÓÝXÙXX\X›ÙÑLÒÞÒPPÐUÜ›Ø›ÌÒT˜Œ’T\ÍÜŒLMÍÖŽM••ÔZXYÜÞYRØ^›Í]“Ó‘ÛØZœ‘ØÛÒÙØØÔž™^”ÞTÌÕššÝ‘QZUQLRÌU›ÓÊÙÌÑYœ›Ü]›Ö™Û’^SN[ØÙÍÝ^XÕTJÒ]
Ýœ›V™ÓÔÕŽL›Ø[Õ’ÚÚšTÔ’š›–]›\\ŒšŽULXŽU]”QZRœ‘Y[ŒœSšÔÔ’LœLÕž
Í^’œÔÐT“
Ò–]VÕL”UU›ÐKÌÞM\Õ›[ÞVŒ’\ÔœÒKÓ›”™ÑØÐMXZ•Ñ”]Pœ]˜’RT”ÌÔÕÌÐÕÚ]ÑU‹ÝÒÛÞYÚÐ[ÔÑÛÞSÓZŒÍSYLÙÜÚÖT’ŒTPšØÕS™TLQ–Œ”œ’V“Õž•ZÚÛÞÜVÛÞÑVVMÓÔœ“V]ÕNS]ÖT˜U™žZÜRœÙÝSZÝ‘ÙYTŠÕÜÚT’œ“•”ŽÕÑP“’LÚžšÙ][XÎZT’ÍSÜ’[Ö™ÛÙÛ’\X\N‘ÕžRÕÒT›ÔÑ”ŒÚUŒ˜SËÕ[ÌÌ‘ÚÐU[]”ÛÌ•’™ØNVNRÙMÜM‘›ŽÒØÜÎMVÎÔ‹ÙRM›ŽÙUœT]‘QÕ“ÝÑ›‘SÙ’•ÝY[ÛÑÒÚS–˜LÕQNU™ÞŽSÞÜN›R]ÚV›]ÞÙÐÓš[LT[QLMÑRX]ÍÕT•ÒÑS“ÌTÞPÊÑÖÜÔ–SZT]Xž•ØÐ“Ò›][URÕ›S’Ž“œ[ÙžÔÚMM”›QÕX˜˜œXPV›Û“š]YÖ›]YœÓ•VXTÖ–\ÌŒY]QV^‘ŒUÙ’•‘\^MR”˜Ô–YMMUŠÛÒŒP\Ñ\™S[˜Ø˜T‘ÞÜ]šQÖX”ÌÛQÌŽ[žSÔÜYÒÛU˜MLÕšÖŽ–PÖ›ššM]ÎZÒ•Ò\ÛSÛ“ÍŒV”YNSR’ÖQN\žZ[•ÍR”\SÐÑÜŒÚYÐNR”XZÖ•L•™Q•ÔV›Ñ]XÙÖXXRÌMÕ‘”[PTÛÓÒTÖTXŒYRÚÎšPÜ‘Ì\RÒZÙY•ØØÜ•Úš““U™•UÓ”ÕÕÚÒ”Õ‘LLZU”\™™TÒ›ÕMÞ\M
ÊÕÛZTÔ\ÓRÜQÑÚMTÑ’Ø–VšÚž’Î[\ÖUšÎJÝR‹ÚžXÓLPÜ[ž^UL•S]Ý”ÚS\LÞ[ÍšŽ•Ô”ÖšT’Ì•ÝÔÒÝX•ÌZP^SÚ”ÌMÔX[ÎVR›ÝÝØVžŠÕ›’ÒÙRLYØRžÝU\SØÙÛÌÌžZÓÖQ‘XÜÙØ‘”ÓÓÍ™M”–‘Y“ÚÕÞ\ÝR]”S‘]–^R›ÚÖ“Î“’ŒÚ’›Ó›Ž]™S˜\QÔ•™XÐJÜY]ÐV\Ì[ÍÕMÍQÙYÒËÚ^‘Y]S‘UÓ[[Œ“M’“–RXQ\T“Q™Ñ•Û›PU™ÔÝ]ž“žÕ•Î^QMžZŒUZURVLUR–MžKÙÚŽÕU\Û[›”œÎ]œÜÌ^Z’“\ÙLYšÓR“ÙÝØÍ]ÕÙÍVœÖ–RÍZPÞÚVYÑÍØ“SZ\SžÙSX[NØØÖ]šUŽ\L›TŒ[ÒÌÙÕÑS[Xœ\ÌœÛZžM\ŽŒQœÐ‘˜œŒPR•‹ÎX‘ÚÒUŒÊÖÜÖ•ÝØÎN”œ”Ð\R™T•Y’SËÓÐ]’ÐÑ[•œ]T’ÑÍMÑÛÊÕËÕœÞ‘Ò“‘ÞÌ™SXÍMQTQÎMNPST“ŽMž“œZÍÍNR”˜Ú˜Ù”]“X‘Û\Ô”ÒÚZ””^Z‘Ø[ŠÌTVTÔÓ^ZRÜÍ]ÐRžMÑ”RÒÜ[V›ÓLKÌS‘Ý’‹ÔŒŒÕ\ÒX]Ü”S]S‘Ö˜šÑÚZS“ÙÔ˜Ô•Y]ZSÓNSÑÒ\ÛZYÐ“LÎVšÎ›ÎSQ’ÓÕÙ•LšžXV•‹ÞÊÛž‘”ÚLœÓSÕœ–\šX“Ì–^MÒ[\™ÔRSY”TYL™LRNT‹ÌYYM\ZSÎÎ‘žÔÒØS‘•ÕÒ–Y‘YÒSR–Y[ÑURÍ•–VZŒŒTÔ‹Ô•‘[\–[™ÜÕÜÕTQÔNPQQY˜Í’œÎS”[™U[^T
ÐÛTR”’ÙPN•ØÛT•VJÝTÔœNTÖ[XŒ›RS“Œ[Ø˜ZU
Û”šÜÑXÓÒQÍYÔR^ÛMT[–LÌ˜U–šMŒšŽÍÑ’–™^›[ÌLQ”ZUP”Ð–š’–”][ÌS“Ý\˜Ø‘‘ž›ÑZÑKÑ\‘ÝN
ÝKÍ•L\QKÒ\ÒžLPÒP’˜ÜL“YÑ\[ÓRÚ[žšV”ÒœœÒžRŒ˜V“\[ÓÊÚ“][™Û™ž’MÔUÐÐÒÚ\ZUš˜R›ÖÒÖQQ[›[Q\ÐÎRœ›PÍÕTTØ•U˜T’Ý\ÒÍÐ[MRÔÝMÞ’ZÙÑZ‘TX–M˜Ô^\ÚÐL\]]Ó“UÜŒÚTÐYÕŒÑSQš”ÖR™\Q›SÑÒÍ]^MŒÔUU[Z”ÚT“U[Ì”–•’Õ–[ÔšQÞ[NXL“]Öš]’›Ì•œS’QÑÐšMÞVX™ÚKÑÍ\ØZÝÝ‘šÙÐÜÑŒ‘Ž–Œ›ÓUÞ
ÑNÔÑÖQLV[‘\RPÜS
ÑMÐNJÐSRÑÍ›šVÚ^\˜“šTQV‘–T˜Ö•Q•Ò[ÜJÒ˜žLM™••S^ÎP”ÛÝQœž™ŽQPNžšÖ˜Y›ÓSÒ“ÑR™YÐÒ˜ZËÚMZ[Ñ“”P]U‘ÚMÕÌ“Ý›\^]LØÍÌ“ÑÑÓZQ’ÙR\ÖÑÍ’Ö]’]Ù›œ
ÌÓØÒTÛÓ”ÜTÕZ[M“QXÌQZPŽ‘ÙMJÝÙžÔY˜”ÎSSÝ\–SÙVÚÜÑ˜ÕÌšÌ“L“ØV‘ÜSSÌŒÝS“Õ“˜ÛÙMÌSÌZU]›ÕÞ™šÎYZ”ÌÜÒÝUÐÌPÒ’ÔM‘UœÒÔ^\\’ZšU–PÐÒ™[›ÖÕÙ›’V]]Ô‘L•PÐÓÒN’šÝÑ™•TX\›Q[Ì[N“ÚV™ST–›‘]U–™ÌÔÐZT–[ZÑœ[ØYZ”N•ÖZšLÝ]U˜œÛŠÜ‘”M“QŠÌRY[L[^ŽY\VSMPŽQ˜Ì\SØÐÞ]Ó’Ö˜Ü\–’“R[Ô”ÛU[P›XMŒ”UÛÒÕŒ–Í‘^‘MÌRQÕQÓÖœ‘Ö
ÝXVL‹ÚQMÍ•ËÌLÚQÎLœN[ÐÙÙÐÍÞLšÕÚÞ”Û’V“Ò–^ÑŒ“
ÎUœN”[Òž\’”™ÌÖTPÛ”ÍÌZ›JÙ]Q–VYTS•V–•Ú‘œ˜ÕT‘ÌT[ØÔŽÔ‘Ì“ÔQQ•Ô•›Ó–šRÌYÜÒ”™ZÝÜ’ÝÞ[ÊÛ\LZ\™ŒXÕØ]›Ù[]SÒËØ™T[S‘“VMYÔÕ[ŽX’œÍ[ÝŒ[ZN[ÛUÛ^‘ŽRÍÒÍŠÚTÔ•QØÒÌ•ÐÚÔ\ÜZžšQQQ•ÑUšNÚÝ[‘[\QŒQL^ŽTÜ˜œNXTÛ[
Ü‘V[P[ÔSÔ^˜ÒÐœ˜Œš˜‘^Ü\˜ÑÖUSNXZžSQÎŠÐTÐÞÎ^]ÓLÚŒÓÕ›’œÐÙ™]LUYšÔÐÞ™ÐT^ZY
ÑÙÎQ’XTÖž‘™Vž’Œ•–U”ÝÞÌ\Ú•[UYÌ’PPÔÕ[Ð‘ÒœÝTÓÌÕ‘ÙRRœÚÒ’R™Ý–ž[‘MÝÛÍÝPUUÓÑ“[\ÍÚËÛÙÙ•ÐÕšQUÑÌQœÌ‘Q[’šÚQMX”Q›ÒVŒ]ÌZ]LÚ–œÝQXSZ™ØÍSXXœ‘\M•\ØÑÌŒ•Û˜XŽZ“X›’œŽUŒ”œ–›U[ZJÝÊÒÙYY]ÝUZÛ’‹ÙTM˜Í‘ÜSLV›VP]ž•›™ŽœÚ™KÔXUSÔ]Q™TPÒËÐ\ÚRÞ“TÜÌØÕÍÜÌœV[–›MTÕŒY’Û•Ž[‘ØS]T˜•ÍXPÙÒ–\Ý™ÑSXÒZ‘[””Ò˜ÙVUÜÎPÔ‘LÝQ•ÑÕÔÛTœSTÕLÍ^RXSŠÒ˜ZTšš›Û\•ÞQ“Þ”ÓÒÔÓXÓ’SXTžžSÕ–Ü’“XÙÌØÚ“]\ŠÖ•ÒžPœ“PŒš‘T“”[Ø\LžÞTYÍ^S–‘Þ’RØÜœ[[M’ÛKÛ“S“š›ÙœT^ÙNž]ØÚ“]Ò‘›–[TšÎ^œLQTÊØ\™]\’ŽT›–
ÝÝ[YÛÒš”QŒœP^‘QY•›”YUV•ÐÝSËÚÐÕÞÒ\‹ÜÑ–˜LQŒÞ[NQœ“Už\™NÔ“•YØTQ”‘[ÝÞ[L
ÑT‘”ÖšÎP‹Õ]S”X‘”Þ™ÌQ•^”ŒØ•‘š[
ÒRÚR]•ÚŽÝÐX^QLÞQT“›‘RÞJÛŒ•Œ’”[Òš[RZ^ZPRŽSL•XQÝ˜ÜØ\œPS›•ÛU••U™TV[RR›ÖS”ÜšYÍ’Ö”\šÓØžÙTS–[ÌšÚÜÓÓÛUÜ‘JÙžXÝU“SÌ˜QP“ÞŠÚÕ™UÚ]ØÓ›L˜Ò“‘’•™ÕÌ“’’TÓžL
Ñœ“œÞœÎY›Ñœ“•–XÖ›Ý“Ö^VÍQÍ]ÖSÒÔŒÓ”QžÐÝØÚRÚ“›ÙÜ“TÚÓÌÒS™S™ÞšÕKÚM–[ÚÝÝ™‘ÌYTÝLMÖÒÓÓYÌÐRœÙÎLXÞ˜Yš›šNÔR”“]Þ–•ØV“ÛVYÕTØÎÛÞS’Ñ‘ŒÓžŒÛ“ÝUÛTŒR™‘ÚR’ÊÕšUR’ÛÍ^™ÔYMÐÕÝ•›TÛ\ÜÌRXÑSV˜\–Y\RRXQLÓ•ZRÍ›TÎXœ™Ý›ÖœÕÎQ•–Ü‘–\RÜŒž”ÑVŒPÒÛRÍœPÕX‘žÑÌÍ˜šÝÓœXT•Í”ÌÐ™ÙÖ\Ì\ZPZ’ÓTÝ”˜ÕJÕ”QÞŒMÛÒ››žÌÜLQPÌŽ–’ÜRRQ•MU•ÜËÓÔÎÛUÔ[[\•™ÙÝUÕÖ]Þ›QŒPPÓÌÛNÙ^”‘^ZÜUSNÎ›Û“ZÛÑZSÜÕÐž\šQ›ÍÚ–’\‘ÒŽ•Ö›[›“TPKÓÞVU“ÓÚÚZžSÛU[ÎUV’YZ›ŒÑÚX˜L“ÖŠÓP™ŽT]ÐÜMÒÐTÙPÚŽNS˜˜]ÐJÕ^’›Û›ÛRÝŽMšZ›’•PŒ\ÝL›œZV–’ÓÙRÚØ^PšZžR‘[TQÓ\ULÒÐZžVMTÎÖ’T”ÔÒUYÍžZÕÛ˜œŒ”‘ÌQ“SÔÕÕ‘SML“XXÊÕŒÒNTÌÚÑU]›TÛÒÍÌ™Ô“YÙÍÚŒ‘M]^ÒÚ\^žS’“[Ž–R‘”žÝšÕRÓš“ÍTSURÛ“Õ^Q’Ý]ÚÍ^TQZQL•ÙLšÌ•ZPØ‘‘ÍÞÕÕÒÐÝÙLM›ÜÑ’TQŠÞ“]‘Í˜ÝÍ™š’‘œÝ”’YRÌ\\U“PœXUÙÚž[Ð]”Ì’ÙŽšÍ’LŒØ˜Ó‘TÜÎ“ÛÑU^S˜\ÖRÍœT“RX‘Ý™^Œ“šTÜRTÛÜYÚ\QNÕÑÑÓ™Œ]ÙÓPÓÝNLÕÌšPZÚÝÙÎ•V^ŒQ’–JÚÓUY•ž™ÜÒ]ÌÕQÖ\ÙÕœQÐÓÚž‘ÖŒÛÔ”“ÙÌS”ÔÝ”Œ“ÖT•“^N\œ–[TÔÌRJÓPÙÐX“ÒSÐž™Ù–LØ™™ÛÔÓÔÚ”^QÔÐMÍ’’ÍšÚXXÑ”“Ý›ÚUPLÍVZÚÜ[\œQÒ^ÙÛYÔÛRÒÛÖÜNÕšZÊÙÒÍÕ]ÐÑž]SÖUÜÌšPÜÝSÜÒTÔšP’L”ÒM\ZÍÑÎ\ÚÝÚ^T[\Œ‘“ÐÔ›ZYM›ÔZÕ‘MØ^RMÒ›”šÚÕ\’™Í”ÔÌ‘œÌX›ÞY•ÒÖÓÝÍÕž™PÙSœ›ÞYVšÓ˜ÞœZLQÑÛÞNÕPÜTYš‹ÚØÚØÐÝÓZØLMJÍRU•Q[JÕP›’ÙžÍšR™QŒÔš˜LÎ”™ž•\‘ŒRšÖR“ÝÌ•›[RÐÓ’“”ŠÌVQÔÕUÚQ™›R]ÚÜUÐÖTÒMŒSÚÙT‘žŒÍ›ZÚÜ[”Ù^‘ÜTÐÝ›ØÔœZØÓÜT[ÙÔÞžT‘“ÎÓXS™ÓP[
Üœ˜ÌœÛ•ØžSÑ“ÒÛT[TÔÔNÓÝÞ™ÌÌQ‹ÍPQžKÐÝ™ÝÝZÚ‘U[Œ“PÙÜž‘XŒRMÔSUÕÜTÙŒÌÜÎLMM]’ŠÒ‘\[–’œ–šYQY’›Ý]UÚSØUTšRŽY›™ÒS’ÙœÒÕ›R^–XœÍXP‘Õ›•[”ZRÔž•U‘ÒÞ’YNÒÔØÝPÜ‘ÖMŠÝšTÌ’ÖUØÕÔÛUQ[Ú‹ÎY’ÜRMJÖ^˜ÚÍTŽUÞ˜ššNS˜‘Ô›™LÊØMQÛSÛ]ÜÑ™ÕÌšZ[R›’RXÔQ”ÝTPXÔÓÍVNZ›’ÚJÚœÎRÒÑÎUÒÌ[M–“š™ŒXšLQÚÍÑÝœZ˜š“ÓÌÜÙÒVMž‘ÍÒÌ™Ø–”TÒ›Í‘SUÓÍSLVLÚÖ›œ‘ØÛšVR]œ\MZ›[\•“ÚUÜÜÍSžŒL\ÚÛÕÓŽ]ŽZQ^ŒÕÓ”ÑŽZ•Q™KÒÞTÕÎÕTZšT[Ý•UÜSZØZšYR™ÑÚ˜ÍPÞZÌœ]œSÖYÙÝÖS[MÔ™U’™ÍÕ˜YRLQLT–UšØž›LŠÚ››Ô[•ZÌMÌÑÛÍ›‹ÕPÙ›š\QÙØ–LMžQLÜ]•V›RÞYÛž^ž›ÍÜ›Z–RL˜XÎP•QZ’LÜÌÕÚMSÍØœM\[‘ÓU’^Y^U^SSÑØÚLUUSXZš]ÙÐ•ÒžU[RÚÐÝTÛŽVPRÕÛÖÌZÞVTšUU’ÑŒT]™^QÚœÕMšÛÚYÛœÛS’ÝÚ˜\›QŒÐZšPRUUÝUÔÞÛ›ÖTQN
ÑÓPY™ZP’ÞŒ•ÊÚ[\Ñ“MÕ•ÓÒU\–Õ™U“œÜSÝ“[UV”Rœ‘ÓÙQÍR“ÓZÌ˜Q[XÕQS™Öš˜YØ\žÊÛTÝ–’RÝ’ÛÙ]S^ŒÕ]SR˜T”^T–˜Ñ^“”ÌNQÙÜ][Œ]NÐœ™R\M˜Q™ZLU[NÛ•ŒT™]ÝS^M•]ÚYÞZ’œQ\’˜žZÔÔ‘[Q”Ô‘ÚØYÝÕ‘šLÕX’˜ZÌÑ\•^V›Ó[ØÜÓÚ‹ÌS’ÜY–UV’M[”’Ô“ÑVR–U‘š‘‘ÑMJÌ”V‘‘‘‘Z›Ñ\ÒQU’]–S•\ÚÙžœ‘’“Ù–SØ“Ù›[Ì™U”Ì
ÞT›Ž”ÕÞ™ÙÙŒM[ÜJÖžÓÚ’›”Ñ›ÑRTÚPœšÕ“•ÕÖYYÓ”™ÑÛ‘Zš˜œ‘ÑÚÛÌ›ÍM•ËÒž‘R•SŠÛÞJÎÌST’ÒÒÒLÖ‘ØQÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓP›Ô–QPR^“Q–QVQXQÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓRÕ™ÚŒŒ]ÑÐ]ÑÙÎ™ÓP™ÓP›Ô–QVQÓS˜L”X‘XQÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓP›Óš‘ÑÓ˜’T–QVQXQÕÐ]ÑÐ]ÑÙÎ™ÓR]Ì\’‘P™ÓP›Ô–QVQXQÕÐ]ÑÐ^QÜÖVL\ÙÌÙÎ™ÓP™ÓP›Ô–QVQXQÕÜÑXLÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓP›Ô–QV^•ÞQVQXQÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓPœÓ–]Þ–›Ô–QVQXQÕÐ]ÑÐ]ÑÙÎ™ÑÑÝRN]ÓP™ÓP›Ô–QVQXQÕÐ]ÑÐ^‘ÝÑÝÝÑÙÎ™ÓP™ÓP›Ô–QVQXQX^•ÞQÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓP›Ô–QÓS˜^T˜•VQXQÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓZ‘ÑÓ˜’S›Ô–QVQXQÕÐ]ÑÐ]ÑÙÎ]Ì\‘ÝÑ™ÓP™ÓP›Ô–QVQXQÕÐ]ÑÓVXL\ÙÌ‘Ð]ÑÙÎ™ÓP™ÓP›Ô–QVQX‘ÓSXL”XQÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓP›Ô–Pš•ÐÔ–QVQXQÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓV]Ì\–œÓP›Ô–QVQXQÕÐ]ÑÐ]ÑÙÌ‘ÜÖVL\ÙÎ™ÓP™ÓP›Ô–QVQXQÕÐ]Ú‘ÜÚÕÌÑÐ]ÑÙÎ™ÓP™ÓP›Ô–QVQX^•ÞQXQÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓP›Ô“S˜]Ôœ˜–QVQXQÕÐ]ÑÐ]ÑÙÎ™ÓPš‘ÑÝ’SšÓP›Ô–QVQXQÕÐ]ÑÐ]ÑÝÌZŒÛ]ÓR“ÖYVZÍÔÎZ›^–ŠÌŽRÛÊÌLÍÒšÖXXØÙŽ^LÙ™ÜPÝÒ“šMY]‘ÕÖMÎ\Ú‘š›^SST‘œÛÌXÊÊÔSŽKÊÞRN–ÓŒŒÖœŒLŒ˜›‘žJÞMÓ^MØ–MÙ›ÞÛ’ÝÍRœUÝ“N^žP”‹Ü™KËÍ•Íš™Ý‹Ý›™˜Ý”˜™^]˜˜™N
ËÊÓŒÙ•NÐZ‹ËÙ‹Û‘]ÑÐQJÕÙYÙÜËÎ
Ö”œœ\ŠÍ]ÊÜÌÜŽMœN˜–RÝÔSLÜœ˜LËÜU”ÎMM”Ö™‹ÊÍÚTY•›Œ™YÝRÝXÙÎ•ÑV[\ÕÎQžŠÙÍËÎMJÜŒMÕÓÝ[›KÊËÓÌœNMYLMž–]UÜPžÍNœS‘Þ™LÓ™ÝÙž[ÊÌŒ
ËÒ™ž›ž\Ð“ÓÔRÛÝÝÍ˜Ö\TV“ÍÝœUÙÐMVTš‹ÎÊÍÛ“Ù‘ÍNM‹ÊÜTœNÎ\ÑKÍÙ•’ÌÍYœ”]ÎÛÌ]LL]‘QRÔËÊÒÕžZÒÙJØÓULLLX–ÍPSÙQÌYÌ”œÛ›Ôž›Ý]•X™\ŒÙ\œÝUÒ’ÝÙYYY’’žNÒÒ[RR›ŽMÞœQ]ÖY‹Û^‹ÍÔ•Ý’Öž–UÙÜJÖLÒÒ[•Ó•L‘PÕÛÛQ[Z^•Ö\ÔžQ‹ËÍÒQ’Ö‘›VKÙŠÌ”ÝLÓÐ^\ÕËÙ]Y‹ÍNUÜÙËÍ‹ÍÎ˜“žKÙ›˜‹Ú]R–ÍÜ“LYžP[’ÕX‹ÎKÝ™LÚ]JÍ–ÞLZÌUÐVR’S›ÝÜ›Ô]•XŒ\LÙŽÚš•^ÌŒ™V^ŠÛÜÝLÒTØ™œ’œÌ˜ŽMŒY“UN^Ô™LTÍSÑÔÔÚÍXZ[Œ‘MJØ––›‘“™ËÎ
ÞXÝ]RœMJÍ[[U–™ŒSŽ
Ù”ÊÌ‘MMÌ\œÎXÙLšÐ\“ÌM^“ÓQÕšMÖUÙÑ”™XËÍÓ™ÎUŒLKÍÛ›“’–ÓLXžŒÌJÝVJÎMJÍŠÙÛUšÓÔÍ‹ÊÜœ™ÐÍN^›Ü’]ÌÖLšSÖÑ•Œ–ÖÎMÍÔÕŒ•ÔžKÍÝ™‹Ó^™RÞÎX[“‹ÕL˜žžS“ŒÌØ™žZNKÍšQRÔ˜[ËÍ‘““Û’PžžŒ^ŠÒSPÝ\œÓÜZÍÊÝ™JËÊÜUV“YØÝÞLÌØ–TMKÎÒœLM‹ÑžKØÊÝšULLKÖL››–ÓÎMÍ\ŒÌŒ‘ÌŒžœÒP˜Ýžž•UL‘›QVÑÝX”ÍÚZÓÓÜ‘\ÌÜ“ÖXÙSÙRÔYÎ’š›ÚŒVÝÑ]”ŠÝÌÜÓÌY˜ÖÌšœYVÝÕ]œÖS[\]ÙPŒ\ÙÌžÖ–•ÌÍŽNM’ÝQÕ–ËÚZ•ÊÎMÎ]™™TœŽÓ\PÌÍ›ÒÊÒÙ”“QMÌÝKØÝÑ^Úž•œšž‹ÍÝV[Z^›SÕY™™SMÌYKÍÚVYMÖ“ÓRÒRZY[SMLN•˜žUÓ™šU“Ý”˜–ŽRÛSÑ”ÌÑ”ÝYÎMÝÞPÙŠÙ[ÌÌ^žMÝÝ•ÊÍÙSR
ÔŒ–Z’YÛ››œž›”
ÒÒL™šÌLMÓÒ‘ÐÑÌV•šœ]
ËÍÝX˜Ž•Ü˜Úœ”ØŒMÌ™ÎYNLÒœXZÜÍY\™ÔžJÌÚ[]]ŒJÌÓÒZ’›RÌSPÝ“–UÓš]ŽÕ™YŒÍÙ˜ŠÎSÌÓ›ÚšÒ‘S“ÓÌÍMÌÊÎTUœÑVœÝžXÛ“
ÙÌÕ›ž™™Ù™ÊÍÍÜ•ŽMLÑ’ÑÚU]ÚÎ[ÌSLMLŽP[Ñ™”“YÝJÖRÒÜÜ™]R]ž\]Ö^‘ÖYUM^ÙÌÜ˜œ“ÎYš‹ÎPSÍXØÖ
Ü”›–›ÔMÖ’MŽÎÑÙ›ÛÛRšÕRZžX\ŒRÞQ“RÜÍT
Í’ÚNLÍÚœÌT™]KÔŒÜ›XX›L˜Œ’ŒÍ^XÛ“JØÎÙ–UÚÌžL™^VKÙŒ\˜Œ^^ÛŒN\œŒMž™”[”‹ÚÜÚY™ŠÍKÎœU–•ÝUžMJÓÚÛ’™ŒÒ\Ý^P”]›\Œ[MÍÜŒNMŒV]UÓNV™ŽYNYŽ˜œÚ›™ËÎÖ˜L
ÝÐ–MÚ›Œ–“ÙS‹ÒUŒÖ•ÚÊËÜÕ“›–U”PËÑ‘’“ÐÖÌ]’SÖQQÊØKÍMŒ]‹Ó“‹ÊÐPT[\ÎYL™Y™ÌX–›\ÕÓ™LXÓŽSš›žŒÓTÌLØœšœÜ]]ÓJÐžËÞLSUL‘ÑÌV–ZLÜš]ÐXØØÚš‹ÞTÌXMMŽMÌÜ“ŒžÝ]““Ì–œÍÎ˜NKÍÎÍMÒÛÌN]Þ›ÍÒLÛœÝ›ULØŒÙŽQžÞÙ”Tž\X\LÎLT”‹ÞJÍÙ™TZÍ[˜’UÐL™Ü“X”ÞUÙRÞXÛ\ÌÚXËËÍÓŒÍ^Ú\ÕÜÐ’ZST“•ÊÞÜV\ŒNÞ•^YQP\‘Œ‹Í\œÍŽMÜÎKÝUÌS‹ÊÍ‘ÔÙV‹ÙXLPÙ•Ú•šž›Û“™ÓÌ˜Ô˜“ÙÓÞXRÓÝœRÌÖšÌ’SY–[Ì››šŒÕ•ZŠÍŽMÌÌTÎRÚ›˜ÔÝÙLNNTSŽÖ–]ËÙ™RSÓQÕ]”RÞÕšÌUÐ›ÚMÛš–Q›™\XÍÓŽS™ŠÛÒž‹ÕÌÍÜš\]‹ÕY”ZÍÞŒX–ŒXššÕSŠÍÌMMÍÍÜ–Î
Î[ÙŒÙ’ÜÊÎYZTÊÛKÎLÝ›”ÌKÕÚ™LYÓTÜÍÝËÕÝÕ”L]NNRVMÛR”\ØÊÙY]ÑYUÙXÊÝMÐ‘ÍÍ˜–]ÊÞSKÙÔËØY”Ð\Î]
ÕZ“ÊÒŒ™ž‘ØÖŒ“ÝRVËÑ’ÒÜÎ
ÎØSÑŒÍËÛ[‘“ØV]ZÌS•Û•MMŒžÍÓÝKØÖÒUÍX˜Ì\MÙœÓ]TÌØÙZÛÊØŽŒYXž‹ÊÖÓÒ[žÞ•ÝŒÙÕ•KÝ”ÙœŽKÍÕLŒÝ”QLÎ]]šMÕZÖ›ÎM]YRÊÌ˜ÎY]
ÍRÑRÎTÓŒËÛÍÐÖ•Ü™
Ð]ÑÊÎY‹Ý‘VŒËÜNM
ÓÒÓRŠØM™ŠÐ]ÒÍ]V[P™ÓPÍÊÌVNJÓÌœŒÍÍP™Y”ÔžR‹ÍŽ\ËÓÕÌÌœŠÍYKÔÑŒ•ÍÝž›UËÎÓÔÓ“ËËÎP™ÓSšN˜ÜÖ‹ÑÙËÌQ“[ÐÞ]‘ÙÒ“ŒÐŒLPÒL˜’Ý“Õ‘ÜÞ•‘ØÙSÞ›MMS”QÝŠÜZ™ÛQž]ÛÊÚX›Õ“
ËÍUQ‹ÌÜžšššœÎ[NYÙ™ÒÜÍÙ’LÔ]QÐZÞ’Ñš“‘Zœ\ÑÙÞUŽ“S]Ð“œMÌŠÍ›™‹Ø–ÕšŒ[ÙÝ‹ÎXÖP™XÎMTKËËËÊÞÍÌ]ŽJÙ––žST’ÝŽŒšYPÊÙKËÒ‹ËÜŒYÞšVZÌÔÙ–ÓÕ]™ŠÊÌÖ•UÙÕ’MMŠÛÎÊÒÊØ“›KÝRšÐ˜ž“˜Y^žÛNZ‘Z‹ÎZ\Û]ÜR”ÔÒžÙ•ÓÔ–›––LØŒJÌL]]Œ•ÝLVZÓžLœT’ÍËÙ]‹ÓÑS›ÍÑ\ÒŒŽ[ÌÜKÑ‘’SÜÍ›^˜™]XÎPSÐØÓÊÔÍ
ÖUJÛLÌÑÝÓ™”VœŒÍž™\ŒÍÎËÊÒÊÌ]XØR™Ðœ›ŒÐV›”‹ÙQSTÞž\˜™^MÛRÔ
ÛÖR–•ØÑZ\Ý“ÓÙ“M•›“›ÎUÙÛT]Ò”ŒÛŒÝœÙœQËÍÓUÝžŒÜÙÑÓÔÓÞ[–žŽ•ÌSŽLÕÛÔ
ÎN’ÝQ™–SÝ›ÖÞ’ÒŽ^˜›X”MÚPÓSÛMZVPRQœXZÕ‘ÜRÜ[ÙL˜ÑÐRXÙ‘PRJÔMÙÍÝ‘Î^XVN[ššUY›Ó[•ÑÓ˜“SØÝÖ‘ÒžSÓÍ™\Œ^NUSÌÌÖÝ‘^M–”ÚLËÚYV™•\XÛ\œšÓÌYR™™]ØËÜ‘™P‹ÝÑÔVžLÓQÌÝ˜‘ÎLœÜMVŽÌQÕ‘Ö›Œ˜ÖLÓSMÛ^‹ÌÒ•ÌJÎT[›œœ–UQÛžYMœNU›[›’”ØÙŠÛžN‹ÍÝÞœ]VÓNYY˜’ËÞ™ÝZ\^Y\ÊØÙRKÍ[NMZ™Ìšœ™–“ÓÜ]ÙÍYœÝ^UM
ÜÚÞ]YœZYšÊÎUÕ–RØ“‹ÌÑÊÌÍŒRY˜[^NS]ŠÝ[ÖÔ’ÝÕÖRÍZSÜQÐÕÕ›MS•UÌMMÌ’ÙÒÐX™ÛTÞ’ž
ÞQÎŒÒÙž]\‘‹ÔžžšYÖUÓMNUKÛœ‘œ
ÖY˜Ù[”]Ú’]LÛž™ÍÊÐ›ÒÓUŒ“–SP””\Ö›ÎZVŒÛÎÐÔ[ÝÍÍR™Ú‘LÙ“•‘Œž˜]’Õ™˜ÓŒÑÌNZšX›Xœ›Ó[•ÑÓ˜“S˜ÝÙÖ›‘›[ÜÐXœžœV™KÙ‹ÚËÒÜÌUX“›ÛÑMJÜ–JÎ^
ÍËÍY™ŒKØ’•LŽMŒXÝ‹ÜÓœ]–ÓÚUÒMMMšL’•Î[žQÓYRTžÜ“ÔQSJÜÔ[ž›XËÎTÌÎ^ÍP™\^ŽÝÕÎKÌL›ÛÍJÝ‹ËÐÜÎ
ÜÛQS”ÒÔ–ŒVšŽNY\ÒœËÎšYÖZÜÖ›–ÔÐPÞÜÓÑÊÝ™–œÜš›•–SXM‹ÍY˜œ^›››˜’YÙœÖšœËÌÌÙŽ\S]Ü’ÞYY”ÖžŒÛ[ÛŽ\Þ’Ñ\X[\–˜ÜÙYœšT]]JÛ™˜ËÌÜÚZ•UÓŒ™™–]ÔÌ”ÙÛL’RÍÔ“Y^
ÍVšÑÝÎQŒ™XRÓ\™]ÙZQ›^Û\“LšNQ]šÌMT’ÍÛÝÔYœÕ‹Ì”ÍJÓ”–[YT‘Ž[ËÌÌLÛVM[›
Þ›ZZžX\Œ›•ÞQ“R™”˜““Ò‹ÖÖMÕÙQUØÊÝUËËÒZN[Ó™˜œŒÍÌ^MÙ›ÓS‘ŽVÚŽJÞYQ‘Öž›NX•KÑ•›]™›“[RQM•ÌÜÊÝÞ›QØÓÌÞžœYŒÝ\ŒÊÞÍP™^RØÝLÜÞY\R]ËËÙœ]Ì]ÌUÙÙYJÍTÔ’›–‘š]Üœ[ÙZÊÒØÓÊËÓLÜŽ]YRLÚš^XY–ÌPQ›žœ^YPš
ÑÜZØŠÍQÌ^NQ’Œ^NT›ž˜ÓÍVŒTYSÐÕÓÊÍUV’ÍZ››Ò’Ð]œQÙ™ŠËÓ“Ô
ÍÒ]ÍœÜ›‹Þ”Ì]Ý“ØÛRšXQÌURÜQS•Ý–š^ŠÍØ›JÜÕT™UšZMÔŒNUÖSXMŽ[“PRŽU“ÜUž‹ÞL’V“›MÓÍÖUÌ[U‘ÒœŽVMÓÑUšZÙšYZ‹ÎÜÞU]“T™U–SÚMžT˜–š“ÓÜ]ÔM›Ö‹ÞÒ^NL––TTY“[MZ[Ö™šÌËÓ[LÚS]™ŠÑTžM˜ÑÐ\ÊÙŽKÔ™Q”JÜ[Œ]Þ^Ù
Ò“ÞQÔ‘XÎYŒ“’‘ØÓÖZMŽM[ÑN””œÒ–™ÜÊÛÚÔV™Ù™
ÓPšÕQTÎØ˜ÌÜŒÙ›ÓÙ‘RNY””ŠÞJÙ“™MJÑ›™ÝÐš›SSÔÕSÝ\LM™YÓžÐ”\ÐM[[›ÛŒÙÙÚŽL˜˜”
ÎVTÞ‘[ÛÕSšœŽÓÜŒXÊÛÞZLËÖS–‘ØØ•UŽLÝŒÕÓŽY“Î]^™
Ü”ŒÑÌšœšYTØ‘UËÝÕNRÚPM\ÊÙ
Ù^UY“ž“]ŒšžÚÊÐœ’ÓTÜÌ“™SÕX^S”ÍÍ’PÙ]ÑÐSËÎLÙ™]^““˜ËÎUÎÒÚ™”R[ÎVÕSÕ\MYŒÞ›ž‘ÛÖ’JËÛZSX\Œ›•ÞQ“SVTÔÙ–RÝÌŽ‹Û•ÝXØÎœ[Œ[Œ^X‹Ý“QÍœRÌÌ\NM›ZžRÔXÙYNšY]–ŽUUšL^^œÊÔ^ZŽMNššš
Þž–ÜÌØ–
Ì™JÕ”Y^[ÒQŽKÞŒZ™“ÚÒÍ”P–’NÑUVR‘]ÌËÚœÌÚ
Í˜Ý”ÙPS™ÐŒÛUÍ]\Í”Þž›š›žÖS\LM”M™’Ý^Þ[ÙSÜ“ÓSÓÕÚ”Ö˜YžQT““Ø[Ùž\Íš–œÝY“ÛŒÍÛ•KÛ[Ú’U”^Œœž›ÝU•œÌ˜‹ÛËÙ“S\NM’‘ÞPM’YTŠØRÒZœÕÊÙÞX™žš]KÌTØÍ™Ý‘œSÔÝØÚ]P‘”Ý–KÕ[žŽ]ŒÝÒ\VÜž^ž“‘šÌQÓ‘ÝQÓÖ^’ÖžR˜Í\LM›ÛMÓNL^ÛŽS•žNUÔšÑL
ÔÒÌØ›™ÝQ’ÝœLÞ›œ™N\Ù›ÜMYžÞ\TÊÒS‘™™˜ÔŒ›Ö‹ÜÎŠÙUØÍÖLÐ–Q‹ËÜžžžžœ]
Ý“ÒØL[ÕÍT™YŒ“šÍS•SšÚU››’ÎTŒÑÍšZ\•‹ËÚÜUØÐVRÓÝÎP\ŒÑ˜XYSÊØ˜‘PžTÞ•Óž•RMšØÙX^ŽJÍÑÎKËÝÓ‹ÊËÜÙ™SËØ–ŠÎZÓ›Ò’^\ÍÒÐN”ÐÕÌÌÝ‘ÍKÍÝ™MÌ“ÖRÌKÍ™Œ˜žÞRÎKÜÙ‹ÓZÜ•›MÑÐØØÍŽMÞU^“SÝØžÐMS\PÜÛÞÞ–LMV’LÝ‘”Úœ”šÚŽXÙÜÍSÜLÞ“ŽÍžËÔÕÖM\L™SÖ“VŽÍS‘[˜Þ•ÑÔLœÚÕÌ–VLZ›L•ÌP˜UV™Ô
ÌÙ›ÓŒY]žVËÖ\Û–›ÙRÕ™ÒXÜTÌP“ÓÜVÛPYÑ]ŠÐŒšÕÖ[Œ™’X”ÖZ’VœÙœØ–Û^M•YN^’ÍÖYÛZŒËÞÝ\ŒVTXÙŽSœŠÔ”•T™^SŒÝNYYžM]ÍŒQžSVLUÔÍYÜšYÖ”M‹ÜÚ˜ÔÌPØÙTÔÞ\ÐVSÓÛ^˜SNÖ•]‘^Q‹ØÓŒ“˜ËÕÔÙ[Ùž“[ÐÙÜ\”MZÌY–L›ž[ŠÌÐÛÙSŒ–RÔœ˜ËÊÍJÙJÙÛN]œžSÍÍLÌÔÒVŠÐY™™YP”‘›ÙV‘“Ì‘Y™SP‘ŽQUØ™]›˜VV[LSÍTššËÌÛTÐž–“žžŽ”ŒÍÒJÝŽNZKÜžMŒ˜ÙÚÎNZ
ÍÍRÒ™ÕRÓÒœ\ÑÔ^™RN\ÝÞÐšMX\œ^ÓŠÞØËÎÑÌÕËÙ™™\LÑ]”Ýž‹ÌÓžXT]Þ‘‹Ù“VQÍÌÜÊÝÊÚžÓÐÚLMLÜQRÎKÝTÖšÖŠÔYU•Ü‘ÊÙÌUÐšV]RÎXÝM^ÓN’ÙœÝLÙ[MQÑRÛŒVTÖšÞ••M˜ÌÌ‘žX[\ŒŠÜ–LÜ[šÜžNÎ
ÕžTÝ‘ÝLÌÖ“M›Ô^ŒÌÖ’ÙÌšY’T›UP•ÓÝÚ‘šÛÙ’ŽŠÝQÓ”ÕQÓÓ‹Ù™–“ÌÞ“ÊÜ\œ˜ÜXÙ™Y^ËÊÕKÚÍÌ’ØØÙŽØ–ÙÚQÓPËØQTÚL–\ÊÐ›ÒÓXÔÓUXLÓPÙJÍŒ™“ÎYŽY\ŠÕY™YNRÌKÜØÊÝM“™œÎœSÜÛRœÙœ•ÔÙ“ÒZ™MMUX\›ÓLÕUÒL‘ÔÑÔÐNJÊÚÍ˜\ÖÙS“ÝÌŒŒŽÛžŒž[ÝÓšÌÌÌ–MŒÚÓ”ÓÞUŒ]ÚN[˜NÝSYQKÔ™™NKÙRÒšTZÐUÓ™KÎÌ]ØNÕ™QM\ÒÎJÞTURØ‹ÝÒZ[ÍžYLÒ’ÝYVœÍÝž›Ì‘’™šÛLÜš]Ð\ÖÚ’“ÓÍ]ÕŒ[ËÚÐÍUœV™ÝÙ\›ÍÌœUÙŠÙ[ÌÜJÎ\‘ÞÖLÍž“[ÖLÝ”Ü[JÛSÙ‹ÎM‘•MÞÝ™ZÑKÔKÔÝ›
ÌVNJÓŒ–ËËÛÙ’Î^JÐÝ\NLÒÊÊÊÞÍ˜Ö™ÖÖ]ÞQU^‘›Óšš
Î[Þ\•MZ“ÔÙTÝUVŒŠÑŒQYšÕXÔÍÞÝ™ØÔÍÌ˜™
ÝÑÍ\ÍMLQÜŒÌÛZ\VMŽ\]ÙRÌ\ÙÌžÕ˜Ù–Mš–^\]‘ÓLJÙUÌLY]SžPÎUŽL
ÍŽN^ÞVÝ][š[STÝÔÔÙ“U™ÍŒËÙ“ÛYœ’ÒMÖ]UœPSÚŒÊËËÊÍ”ÎU›Y
ÙJËÍL›NP–[RRÔÙLÎQX‘V–ÔÑÚÚQØ“›JÊÍÜXšžSÕ•–VKÖ^UœNJÐRŒÙÝRÓSÜŒÍL™\™‘M–QJÍÞLÎMÞZÜ’™™V“ÙRËËÍ‹ÒžLÎPTÚÓ™Ð‹ÒS–‘ØÑÐÊÙ”ŽKÖLÕ•YMYœÔÚŽÔš•[RšVJÓÝ’ÔMÑ^ŒJÌËÎÖÎZŽJÜYœPÍ‘VËÖËÛ^›ÓžŒ›–QŒN”QŽVNUV[ØNÛÌ]VT]ÝYZÌÊÑÞTÌXÓ’ÐÜØØÝQ
ÓÞNVYÐØ“›NYKÙÚŒMÍÜ›“ÔVRLŠØQ[YÐšÛÑÔ•ÜÚÕÌ–SMÚŒÙÙÙŠÓ“ÕX‹ÒÎXÙšØXY‘›^˜]”‹Ý•KÜ\ÎÓMŽYQÍÍL”ZÞ[N•™Õ•ËÌÊÙKÝž•R•N[Œ‘ÓXÜÔššNMÒŽNN[ÕSŒÒÌÓQ‹ÝŽKÝKÙ
ÕÚšžŽSMNMÍÎM\^ÝSÑÊÙ”]™PVŒTÝœ‹ÚšV“Í
ÛØXœNJÚ–Øž•QVYVL›^˜Ù]YÝÙQÎN›‘Û–žY‘VKÖ[›•
ÙÍKÔ›[Y–RÓÝ›ËÛZ‹Ú[šŒÞ›ŠÎY–XžšÐšŠÝØ^SMYÚ‘ŒÒŽ
ÜMÌŒÝ]•ÓÌ–•›”œÝ™‹ÎŒÕ™•ÊÓS[ÛÕSŠÕ™ÌÕŒÚ•˜ÍÛÓšKØQTZL–M
Ð›ÒÓV”SUXLÓSMYTÔ]ÍÖŒ[ÙšRÛ››ž‘ÔPÖ[R™Í[Ú‘ÌÛŒÒ’ŠÖ›–MžRŒÕMÓÙQ[ÞÌUÐ›ÚØ^ÓP‘L˜ŒÚSÍMÍ”•–TXÑR™ËÙŽMÌÝšXQÖšŒÍšÙÓZÝ™•ÎSÑX“œRŠÑ\ÚÌšNS˜˜ÜTZY•X“šLY]ÚM“Ð““MÍMËÝÙÙ
ÝŽÛÌÌÚ™“ÌÍ˜š“ÚÍV™ÞÓYRÎY“ŠÊÎXËÍžÍMÍÔŒÍÎXÊËÎUY–™\ÛžŽËÑ’ÑÓÓ^‹Ý‘ÍYLÌÝ‹ÎRœ˜Ì\žZÛ’[QNYQMVŒVKÔž˜N[RKÙQÓØÙ”P–]•ÕØÊÍ^•Û•ÍU˜ÐÓ’ÞM•ÙŒŒÒŒØ•œMØYŽKËÊÝÛÖY›Z]
ËÍÙMMØÝÖÑXËÙ™œŒœR“ÓÔœ‘VMN›Ú\ÜÓ
ÛÙ–™Sš–•Õš‘ZJÝSœ›ž›œ\KÝZŒÞœÚÖYœS[T\›^–]‘Ú”œÌÑÌ[^œËÍÍ“
Þ^^ž’ÌUPÓM–™ZÕÍÖX^ÝÒÎ[‘›T™Q\ÞVY–L]ÙšÒÍËÙNM™ÚšÚÜÕÓ‹ÍÔÔYÐYÝÙÙ’]^R‘Ò”›ÒXÌÕš›^SÜZÙ™YKÊÜ–ÛÐ’ÍÕSLYYQÜœÙR”Ø^PKÓÑZ’˜\ÑÔ^›\ÚÕÌUKÔRÍ“žŒÞS“ŒÌËÙ]ŠÎ
Ý˜SÞ›ŒÝŠÞ˜žŒÚÙÔŒŒÞX“›NMYÍ™^VKÖT™›N[’ÞNM•ÙšŒš‘Ü–YQLÚ™LÛM›YTÙ‹ÜÛ^
Ô^‘ÛÎMÒYÙTÖŒËÌÐ‘ÑYÙ“\ÎJÕÍÝULQŽœV›œÝ˜ÙRžMSÌÌÌÐ\Ð[LNVœ\Ý–ÌTNV›Q›–•N–’^Ì“NÖ˜ÌÖ•SÓ˜ÍÑ]ÍÞŒLœÓœLŠÍÙÕUÞ™œÝŽÙRÚ›NMLLÎ–Û“•™™šŽJÕŒÞœ[]KÙUÌPÊØ”Ò[ÍMKÌ[[[›–˜ÛTM”‘Ú[Ùž“[ÍšMVNŒÖÞ[‹ËÐZËÌØY\ËËÜÕ“ÝÍÌÚž˜”[Ì›Ô‘ËÞØNN
Þ“’ÌMž˜Î\ÔÕ^’[šÛVQŠÌ\Ù’‘œÞŽUÖQÙXXÎQÐUž›^X›U‹ËÒSXÑL›“‘’ÛÕŽJÍØÝ–ÌP•Ý›[ŠÊÊÞNY“™œŒ”ÑZœ\ÑÙÞ›ÑXL–U”ŽZÌ‹ÜŽS‹ÙNV•šŽ[RšY^ŒØÛLKÖÑŽTÖ\Û•œŒÑXN•QšJÙZV–MÌYZŽÙÍÕÎÝÙšš\˜JÎM“ÖMÍÛMž˜”\™NœÞ“ÛšÔ‘TLU›ÔÌLÌÝ”[YÖÍœ”››LY\ÚNN]Ý[ŒÙVVVŽKÓ[[•œMJÜR]’ÛPžžšš›NKÍ’Ð˜ÙÓ“ŒR[ÙšÍØÙYšM‘YTQÌŠËÎŽL‹ÖZLØÌÕMYYSMMLÓKÌYJÍRžžÐ’V]ÕËÍZ•ÒÖLÞ\Ø“˜LÒ]PÍÝÍKÌ›•”‹ÍKÓQŒSMNLœÚÛ’ÙŒQNÑš–‹ËÓÚ[’ÛÕP™ÒTŒÌÙTÖ˜™™ÝËÜÎTÎ‹ÖR’ÜÞ^ŒLÔZM’SY‘‘œÞÖÝ“ØŒÝ^žS™ZÒžÑ‘™‹ÓÖŒÐYQJÌYŒPÔÒ˜™LÌÕœÑYÙJÊÞ
ÍMÓÞ[U’šY–Ö\ÕXÙT™Ú\‘Ñ™ŠÒÞÌÍÙ^N^L•ÕVPÛQÓ˜“TÝÒSNN]Î][]™™›QžLÙ“›SÕœÍÍÝÞ•Ý‘™YÊÝÑÔM™ÙQÑÌÕ•“šÐSV–œÙ[SVNKÍ˜ËÊØŒ\Ó\™S‘ÓR^QœMŒ]™YŒY‹ØÝ^‹ÔSÕQY
Ñ[P›XÙ]RžLÙXÝKÎQ•
ÎLÎU’Ô˜”ÕÓ
Î–˜œNVV˜ŽT^]Ý[Ø[™LžŒ^’”[]š˜ÓLÝU‹Ó^YØÙ”ž™ÐM™šUMÍËÔÐÜÎMÙŽTŽJÌXËÙ™NLJÞÌ’JÐÕLYKØÚ[›‘•™ŠÞ\™œÖŒÙTÎKÛRLÓÑUÓ]™Ù’ŒMËÞL\Õ‘ËÊËÙ[‹Ú‹ÓXŒŠÊÖ–Q•ŽMN\ËËÎÓÔ‘šÎYXÓžÞNMÎÙËÊÑÍÌ›ŒXËËÓÚ›SŠÍ[ËÎÎJÍY’Í“›TÍÝ“ZMVš•”“ÐU‘ØÖ–JÙUÌ’Ì“˜˜‘ŒÎ\ÝÓÓËÚ^\ÕØ™žV™“ÕÓN
ÔÔš“MÞÎ“Ô“›]ÑYÐÕÓž›QÓÖRžJÕNÙÊÍš•Þ‹ÖŒÌÜšTÚ™žÚÕš–]Ö“•™ÒÒTL\ÙÌžšXÔØ™šU^ÕÜÓÓÕÑÖMÒ•šÛ\˜X‘QŽU–YÝËÎUNYÌ“ÓšY˜Ì\[Ý’Ú“ž–˜Î[‘ÑŒžÓÒ•MÖÎY]™œNÛ^“M’›œNQLMÕ•Pš”Ý
ÙST–ÑÚ
Ð–œLŠÍ™L”ÔP–]\Ý\MÐžŒÖœÍÚ]\ŒJÕÙYV˜ŠÎQ›ÝŽUÔVPUŒLKÌÔ›žT“ULÙ™Z”šMŽ]]˜™
ÚŠÝ’ÒMÎÑÒMÝ\’Ì‹ËÛËËÌŠÎN^Œ“QÖ˜’˜ÎžŒQV’ÌŒÒÑÌÛ˜‘ËËÚ[žÐQJÝ™Y–•ÍÑÝNKÍšÕØZ˜^Œ‘ÔÜ™ÝÍKØRÝ–NØ–ÌÔÑÞÓ\KËËÝÍÙŠÎ‹ÛMÝ
ÙÌËÜÛUËÞY›‹Í“›ŒÎ‹ËÑ’ÌÝÖ
ÍYžPKÓœÙŒ˜]P’ÑšM’XÙ‘ŽUÖYœØ^Œ’‘\ŒÙ˜ÕVY™SR™™U›–šÚÕZSÑMQÎ[ŒÌÛŽ^™™]š^Y]ÝÐPNV[JÒYLUÌ‘Œ˜Ôž“›ÌQÐ\•Þ‘‘Ò•ÌÝ”“Ü›‹Ú˜ÎM‹ÎQTPNš‘Þ™U]ÓŽ[Y–LÙÌÒØTMÞ\Ý^XSÙ”ÍŽ”ŒžVT›ÍÛ”Þ]ÕÐÝÍ]LSŽN^‹ÚX’V™“KÞ”œYNXSÎ‘š™]››œÍLRÑ˜ÎÜTÜÌÜ[™NÒ‹ØSšQŒ•ÓÞXÎMÎ”ÍÑžNTÙKÎSÜUSž]ØY™‹Î]ËÓ‘‹ÊÜYš›Y]‘˜ÎYËÔÝ“TššŒÜš•ÙYYLRŒYY™’žLJÑÝÓ•ÝËËÔ“ÚKÎ\ÙŠØL^Û•ÌÖÎY•ÍÞÎM›
ËÍ–MÍÝÚSËÓMØÙÙØMÓ[“MÍÒÚY]ZNMJÐœ’ÓTÌ“™›\ÍÔM\ZKÝYJÌKÌÎYÜÑÖÙœÝ\SSÙÎMÍÐžNS]•Ü™™Òš\Ì”LŽÚKÙTZ^ÔÕÙ^N\]ÕPØL”X‘’XÓ‘“œ›š\[
ÝžŽY“ÍÜ›ÍÒÝLÍ“MZ‘‹ÌÝNXÐTPTØÌ˜›^TÌX]\[ÙÚÌÓØ›RXZŽYÝÚ™LLSÔQÖRÜJÎMÓÜ™U›ÝÒSÔ’V]ÑM‹Õ™YM–œÞQYÑRPKÔ™‹ËÓ•ÖNYŒ’˜–Ý”ÝTLSŽT
ÎLÎKËÌÎNKÚ]™‹ØÑÌPSŒŒÙœ”ËÚ•ŒVMŠÓ›KÛš™^ØÓžŒÎ“™S•N^MÍ]LPTÚÍÊÞŒÍÛ“Œ\ÙÓØÛØœžœ™‹ÙŒÖMÌ•ÓÔÙËÌQ‹ÌšXÎÒ™KÎXŒ‘NKÌÑÞJËÎUNÍÌÙXXÚÌQÍÑØ”šJÍ[R™“ÙPÜ‘T[ÎZV•Ý^™Ý‘Í‹ÝÔšŠÔÐÐ™“Ü”ÝŽKÚŒLQšPÓÌ]ÌÝ[™ÐKÖ˜‹ÙÚ‹ØÒÍÝœÙ]ÓVVTŽM‘’”ÚšÓÒR’“”šÖQÎQÝÝÔŽ]YšYÝ›ŒÌ]ÍL–›–VVYMÎÍÊÎNMR–˜ÓŽžLŒRVŒÚ‘Z[™PZ›X–™ŠÎT^˜N™JÛÔLL‘Ú‹ÝÜSÑÐžX]\M›LŽšT––[MÌ˜ÝYLšÕM\LŠÝU›RP™“Ò˜Ü›SÔ[S’ÛJÙÙUM\ÊØL
Ó‘
Í››\U–\ÛšT™JÜžZžMS””\ŒÍ\UÖS‹Ý˜]œÖžMÌTÙ™ÜNÞžŒÚ‘šNSËÎ]‹Þ–žNKÒ[Í[›œMJÍUÞZLN]œžŒŒÞÔÓŒŒÊÚS[Ó””Ú\ÌÌVœÕ\Œ‘Ù”˜˜Ø•ÐUÎNTŽYÐÍ‹ÖVNMMÜ˜œ“[Y‘‘Ú‘ÑØ“ÌÝÑQÊÒJÊÒ[”ÑÕÖNN^M™œ›ÓUÕ™ÚŒŒÙÙSLÓ^Q“]ËÎ[[^”Þ]“ÝšPKØ\–NMLŠÚPÌÖŒÝ–œÌ‘ÊÌMÛ”’Òš]R^–“S\ÚœRŒÜNNVÝÒÌ˜“ŒMÖLŒÕ’Î”MS^KØŽ\Ñ™]ÙZL^]‹Ö
ÚšÛ•ÖœŒÝMÌžÔÝŽNMŒÖ^NRÝÑÝN^–Û–V–SÜMÙŒÍ•UÔ–]LVX™Î\ÑÔÚ
ÙX[–›ÓÔÔKÐ‹ÔŒÜÛŒÙÙÞ’ÜÍÖS]•Ø–KÎ
ÔNX]YZÑÐÎL™L–YX›ÝÍÙŽMØŽNS^™ÓÌRPYQŽPXSŒÊÚS[Ó””Ú[LÌVœÕ˜Ð‹ÒÑL[‹ÔQVœÍ”šÍÝXM\ÙYœ•YÊÊÎR‘Ñ”ÌÌœÌ“[\]ÖÑ”œ‘VRÑV™[“ÜŒÚ”ŠÕŠÍNQP]SÌÝYJÊÍ˜ŠÕžŒÖŽØMV^Ý•YÖLŒÝ“ÌŒQÖY”›MU
ÛÖ]ÒÜšÓ˜U^š‘T[QXÍQLÍÝ“NNVœÐN\™‹ÔÑÛŒÜS˜ÑŠÎÜŽN\Q‹ÚQSŒTžÌÑÊÎMV”‘›LÝ‹ÍLÛ’žXÛ\XÝ]•ÌŒNM[–œJÍÊØ˜œM”žR•LÛœÌÛ™ÐKØ™NšT–œÌ˜ÑÐRËÚÞY’Ð‘Õ•Ì^ÚŒÕŒÌLZ’Ý^ŒŒšL››]ÌYÜ™SÓÜ˜ËÛœ–Œ[”Þ\Þ’ŒÍNLÜÔQPQ‘ÒÚ™œT]\“Z›Ýœ‹ØÜMÙœËÎV”ÒÌÊÙKËÜÙ[™“VÙÕP[LNX•UÞ“ÑÒ›–žÞUUŒÔ^ZS\MÜÛÞÞ–[œœÍUšŠÖQÔJÎUÝ]œÍM›TÝžTJÙ”UMS”•ÚŒšQÔÜXÝž””^MÙ’œSQÔšŽÌ‘ÐTÎÒVXÍÙ›XQ\ž˜ÓMVŒTNTUÛMMNTÙÚTš’VLÙ•RM“RV“SÐS“ŒÞXœ]”Ø”RÌVJÍÕÓÊÎŒM‹ÍLÕš]Ý”Ý’
ÓÕØÎTœÌŒÛœ–]\Œ]UØÕKÖV“]ÓÒ‘šLYš˜ÔÒ]ž]ÊËÜÕÝ‹ØÓ’ÚÔÌÚÝ™L›\‘ÙÔÌÌ˜œÕÒœ’””žJÔÔÚT˜Ù]NLØVYQXLÌÞŒÙKÔŒ˜œ”ÚUÓ›˜’šÚV™]”œ]T•ŒÍÍÎ\Œ^Tž’[™]’˜‘Ò–KÞÚÕœ•Ó”Î^‘™]ŒÍÓ™JÙ™YNN^‹ÞS”–Lž‘ÐVœÝSÜÖQ•ŽÎRZœÔÎŒ[VQ›ÙŽÒSTSÐUP‹ÓSŒUÛÐXÓMU™ÓÝÒÐÊØ”ŒÒ“ËÌ’Û]\šM™ÔQÝYRÛZ^ÌUÑVLÛ”‘ÜSSšÜÕÓÕÔÐÍœ–ÌXËÙÓØ›ÊÚMMU™ÍŽMÍÙŠÔ[ÕKÌJÎYÐSŽLLÓÔ•ÚØ›ÓPYŒ^Xœ’Ùœž›“ÜŒM‘ÕY™UžËÔP^’VYTÞžœÌMVUŒNMLMËÙš^YÓ[˜\ÜÞšŒÚ›Ü‘”™]™[œ“œÍÚ™]Y“œ•ÌÕ•™ZYœšÍÜ˜ŽÔÌÜ•KÝLU™S•S“ŒŒÖS’Þ
ÕËÔUÎL˜”ÝÌÓÞQššP”ÔLÚÍ•–ÌÜÜÔÙYP’P™XŒ’•Ú›ÚÎŽPYQMYM–˜JÎY[›ŒÛŒR\ÍØÝŠÍ“™œœM™ÐÙLÔ^UÑŽLTÝJØQ˜PÜ‘T\Ì’™•œ^“Û–™\ÝUYËÖRÒÛ
ÙŠÕÑÔYÝÎÕ›ŒN]˜ÍV‘R‘ÛÑÛ™LŒÞN[žZœÛ[ÝÜÑÓ˜’SžÝ™QÍÝ“ÛPšÓÜ[ÞÍ˜ÍÐUPËÌËÊÛ‹ËÞ•]L•šÜ“LN]ÌÝ”›^XR™L“ÍšÝÝ”ZKÖ“›™™\ÖŽRÍŽ™››–ZXÝŒÛ[•Ò’ÚN\’žPÙ”ÍÓLN’ÓšÎÒPNYŽ“˜ÚØÙVœŒMÔ™–Õ˜V[’œ‹ÐÙ˜NLÕÎMÝLMÙYYŽXÑM\ŒÜ–ÚKÌÍÓÛLØšSÌX]ŽNM^Ž^STYÝØ–\ÙŒÑÎÝ]QÙŒÜS•ÙRÓ‘RšŒÌÒZMYJÞJÙ“QÐÍSÝŒÕ’Õ‘›ŠÛQKÊÚŽY’RÑÕÒÞŒŒÓJÊÓšVÙÛÞËÖ›\ÒRJÜ•‘Ð]\\ŠÍÍÑœÝ˜‘žŒYTŒÍÌÌŒÒÍ\œSRS›ÙNM™›ÓPÕ™ÚŒŒÔ\ÕÑ‹Ó™KÍÓNXSÔR\ÕØ˜Œ•ÎMÖKÖœÔÙYKÔ‹ÊÝÛ^™LJÊÙQ\›MÌŽYNYØŒ
ÍTUžŽ\šÌÑÍÙÞ[ÍÖSS[ÚLŠÑÎYÙQLŠÍYÝ–L›Ò[™]ÐÙ”ŽÐVQž›^ŒÜÕRÎ
Ù““ËÔÍY–ž\ŠÍ™SV’žXÝŒ\MX–Z[ÝÜš›œLØ“ŒX]•Ý\R”’ÎÖ–MÙ›Y]ÊÎ’ÌÎY’ÞÝÊÜÎT–[]\”ÍÛ[Ý˜“ÝÔÍÖ‹ÙPÍVUÕØÜÌÖ[™ÍÜJÎMÍÜœ˜[ÌÍÞ›”šŒYÝÙ‹ÍÒžY™Þ\™U™ÙØQÎLÝSÓÝ^TNÙ–œLNÓ‘ÖœXÞZQŽLXÓÊØSPÜ‘T\Ì•™•œ^“ÜÒ]“ÜMž•ÙÐØÕP–‘Q›ËÊÜŽMœÙ™›•[LÚY–’VLMZTŒÕÕVQ\‘ÝÑÙÍÖ›œ–ÜœËÝÎYJÑXL^ZÛ’ŠÊÜÍÖšMY[ËËÜÙ™RÜÛKÓX–XËÓš›‹ÜM\ŒLXKØ›˜œœN
ÌŒ]ØQXÔŒ‘š[’
ØÊÜ–ž‹ÌšÙž–œÐ’PQ]MÙ^Ž™XÖTNLÝÓ\ÒVLNT[•ÙZÜšRÓÔÓ‹Ø‹ÙTÖŽQÜUL˜™“ÛNYœTPKØ˜–ŽUÜÙÒÓRÙ]’ŽMM\œœÌÜ“ËÊÔKÙ]\šÍ˜]‹ÍÝLÞŽ^
ÌLÕ–Y‹ÔT]›ÌžÍÝ‹ÖML\Ñ‘”ÔQM•[‹ÔÌ^•LžœMMV‘ÍœÖ‘‹ËÝÕVŒÓÛÌ™žY^VRXÝ‘‘ŠÔ“™ÜÙ]Y•L–\ŠÐ›ÒÓV]Œ–˜Ö^“ÓÛÔ]ÎY]QÐPSžLØ[•ËÌÍÎLÍUÛÐ[QÞØÝÔšUSYU•›ÎVY]\ŽM‘Z”ÐÞ››R’“”™ÌÐÔ–Q^UM˜Y–•˜•ŒV‹Ù–ŽYKÕÓT‘ÞLYŠÊÑÎ
ÙNLÑ]›VŽKÍ‘ÕÌËÛŒËÌJÑ\ÛœÝžÙ–Ö[RÌÓ“ÓÌœR
ÞRJÙŠÔ––‘“•YKÎLY•[’œÍMUÝŒ”ŒLÑ‘Ò™˜VÌšVNMQ^™YLQŒY\Û›ŒÍÛ\‹ËÌT››SSš›KÞÎÕ‘]˜[•ÝÓ“Ô
ÛLKÍ\Ý\Œ\ÊÝ•ËÎQRËÖÛ‘ÊÙÌ“–‹Ù•ÌÌÔÙ‹ÍÐŽÚTÙ™™˜NY™‹ÖMÕLÙ‘L™]Ü‘ÞÎMX–ÑŒÌÖXS•ŽV”ÎLÚÙTšŠÝ™œMÜ™˜\ÙKÓ‹ÊÒ^^Œ™ÞÍJÑØÝšVYÍœMMÕŒÍÜ^LKÙ›ÒÛX–JÍ”[Q™“’]ŒLPÒL˜•]’ÎV›QÐ“UNÙYT™ÐX“›MÙ[Ø˜œMJÐŠÖ]ÝÍÑÛ’Ò[ž
ÝMÍÕœLžPUžVŒPXÖT™N^M™›ÓQÜ^T˜•ÚØÓ–œÍËÑÜÎ^M•ÕÑ”•’ËÌÐÞ‹ÍÛÎÍ^œ^Ž\XNJÊËÓËÍŽÊÒÝÊÙZŒNLÌMÌ’Ýš^TÙY•ÖÍ›Ù]]ŠÖ‹ËÚœÛÍÍYËÍÞÍJÒ”UŠÛŒÌŒÝ”ËÌŒ™ÙŒÝÙ[RÍ“šÝÚ›^Y“M\TÝœ^ÎØ™ËÛ››š˜X“ZÌ•œ^Ò^Ý’–KÚÍÚ‘ÎSÑÝŒ^L‘žŽMÎKÔ•ÚN›MM‹ÍÜÝËÙYKÒÐ’KÓSžLšŠÍ^ËÞ•ÌLÌÞšØÓV\žLÙV–ÝžQËÍœ˜ÓSÙ™ÖÝ[‹ÊÙ‹ÍÜÙÞÍJÑÕ–ÙMœÙ‹ÎŒž–ŽMMŒL‹ÊÒ[‹ÛR‹ÛÒÛTPYKÙKÎRÝÊÊÝÞ™ÞÖT
Þ–Uš–M™MŽ
Î•ŒŒ•–ÚÙžœ
ÊÊÒQMŽYLÌÌËÐMËÞœËÝ‘LKÎšÓÔÚ™ÔNPYQ”ÝØÙ‹Ô˜™‹ÚL›R]ÍM“™™NÜ[UÙ]ž\\LŠÍYV[ž’\š™š›Z™ÍŠÚS›ÖX\Þ•Üž’ŠÎYVÞ\ÛÑJÞ]]œQÛMMYZššŒUSŒØUÖMšTŒÕVS“ŠÙ\ŒÐŽžPØÊÍSœŒÜLÌÍÛÖ]ÐÝØœÔØŒ^Œ™Þ™ÎR“Ü’Ý^˜NÎ[Ú‘‘ÛŒUÔœœNLŠÍNMXÜÛ“UÜZLLÝ–™YNMRÖŒSN™ŠÙÚÍ]˜YJÞ”‹Ý]•˜ÍXXžPLÕR˜ÎÊÞÚLXÓÍœVKÛ‘Q“ÜQÚYÝKÙYMQÕUXÙKÜ\ÍÜŽÙÐ–]LÎRÝT›™ÌUÝUŽJÌN]‹ËÐŽÕZŒSN[[›•‹ÊÌÔ]ÍÖMÍžœœ\ÑTŒ›SÌÛ––\ÎZ˜Œ“”ÍËÜ]ØÝ]YRœNÌKÜY™ŽX”RSJÍM’ZœLÕÞM˜“SŒLÖX˜œšÎJËÓÔMLMM›™JÜØžQ
ÛQ˜””ZÍ]ÝÞ‘”žÚ[–™šœ•™Ù™S^•ÓÕÓÍŽNÌÝŠÊÕÓÙœœœËØÒÛMY‹ÍVÌ‘ÙÕÍÓŒ˜–L–žVJÝÛ–‘ÒÙNNJÎS\ÎKÌØÝ‹ÓU™šÐTž\ŠÊÌÞŒM’X™[QQÝÝ•Ý™ZSÚ[ž˜“X™“XÐ˜ÎÞœMNT™S›ŠÓÒÛQ
Í˜’ÌÛœÝY^MNNœÌÕMMÖMÌÓÝÍMšUŒÑÕ–Pš•ÞQVTœŠÎST’Ì™ŠËÍS›‹ÓÒÓ
ÚKÜž•œ›Ó]JÙ–U•ŒMMÝÍ\LMžÕN
Ù““ËÛNMÌ\”^œRXÕŒUKÒØÜŠÚÎV\ÓÌÑšŒÔVžÎYYT‘™ÝMœœSÕNU™•œŒ
ÝSžQÐXÙP™JÊÍYKÕT]]šÝÔÌMÙ‹Í[N[‹ÍÒÓÍÎKÕÝ\ZTžÓÒÝŒJÝRÓ–Þ\[˜‘ÔÒÌÍ™šKÔ’ÝÔÍŠÍ
Û•Ì\ÞMYš–™RÐÍRÐT’ŠÌ“M™’TJÙÑÖŽ’Þ\““œœ•ÊÍMËÖZ’˜VQšMŽ‹ÎV]žXMžKÍN]VÌ›MØœÜJÓY˜’T]ÎJÍŒÍZ‘›ŠÙ“Œ“žžŒÝ‘ÎSÕŒKÞÌÕÎÕŠÙ
ÕÐM“N[ÌMŒMLŽSJÒÒžÓžšœ›šYL™™œ˜ž\ÖSNN[JÍžM\Ö’ÙÔQN\Ú“ÚÊËÑÒLÝÙMÙÑšÌQÑT–RN]ÞSÔœŒÍÑ›‹ÍÑÐ™ÞNX]ÌÌ–™NMÍ–ÝÖRÓÕÞSÍÞ\™]]ÑÕÊÍMSY‘›MØœÌØ]ÛRYœÛ^SÝŒ•ÓÎ“ÓÓÙ•ÑVLXœÚ˜XŒÚPLÕÙÝ”Ý‘‹ÛÐÐPžžŽÛJÍÖQØÜ™Ü”ËÞÓ“’–’PÞ•ŒÔÓÎQ˜ÙÙMÝMXžXZN
ÙŽ^“UÝ“Ù]•ZÍÍÊÌÔÝ]“YN›ÙÛÛMÍÔUŒÝ“žLML‘QRÍ]ÚÕÓËÊÛÜNU]–žLYLLÌÌÙ‹Í›Ù•Ü›
ËØŒÑÜX[\–™XY“ÓÊÌÌMM’ÑPØØØÝXÙ^M™ŒÍÖYÙŒÑ[›^^ÞŽUÎ‹Î^ÐÞ“ÓMŽJÓ›–ÛX™™]RÓÑ™™™ŠÎVŽY]ÍÐšÞNÖ™”ÌÍXYXÔÔœLMÒMÍÍVNNMËÞ˜˜‹Þ–‹Î]˜“•ŽMN]NÎ‘TÓ\Ò››ÍÍ[SSVŽL“ÛQLÜ[ÕRÝ›ÔÞ˜›UÜ“LUž›^SÎYŠÍ”NY‘’\‘Õ“ÓÓÎV’ÕRšœ–RRS™Í–ÝÑÙÎ™ÓPš–QNQÌÌÖÝš\Ü’œŒL˜“›LÖ][PŒŒ›[’•]ÕÛ“YÙœÙ™Z’žLÎT™[TLÙÌ‘“VUÕVSš
ÓTÞQÐ]ÑÐML\ÙÌÙÎ™ÓP™ÓP›Ô–QVQXQÕÌ‘ËÍÛXÝÑÐ]ÑÙÎ™ÓP™ÓP›Ô–QVQVY’SšÓP›Ô–QVQXQÕÐ]ÑÐ]ÑÝÌZ‘ÝÑÙÎ™ÓP™ÓP›Ô–QVQXQÕÐVXLYÚŒŒ]ÑÐ]ÑÙÎ™ÓP™ÓP›Ô–QVQÓS˜L”X‘XQÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓP›Óš‘ÑÓ˜’T–QVQXQÕÐ]ÑÐ]ÑÙÎ™ÓR]Ì\’‘P™ÓP›Ô–QVQXQÕÐ]ÑÐ^QÜÖVL\ÙÌÙÎ™ÓP™ÓP›Ô–QVQXQÕÜÑXLÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓP›Ô–QV^•ÞQVQXQÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓPœÓ–]Þ–›Ô–QVQXQÕÐ]ÑÐ]ÑÙÎ™ÑÑÝRN]ÓP™ÓP›Ô–QVQXQÕÐ]ÑÐ^‘ÝÑÝÝÑÙÎ™ÓP™ÓP›Ô–QVQXQX^•ÞQÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓP›Ô–QÓS˜^T˜•VQXQÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓZ‘ÑÓ˜’S›Ô–QVQXQÕÐ]ÑÐ]ÑÙÎ]Ì\‘ÝÑ™ÓP™ÓP›Ô–QVQXQÕÐ]ÑÓVXL\ÙÌ‘Ð]ÑÙÎ™ÓP™ÓP›Ô–QVQX‘ÓSXL”XQÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓP›Ô–Pš•ÐÔ–QVQXQÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓV]Ì\–œÓP›Ô–QVQXQÕÐ]ÑÐ]ÑÙÌ‘ÜÖVL\ÙÎ™ÓP™ÓP›Ô–QVQXQÕÐ]Ú‘ÜÚÕÌÑÐ]ÑÙÎ™ÓP™ÓP›Ô–QVQX^•ÞQXQÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓP›Ô“S˜]Ôœ˜–QVQXQÕÐ]ÑÐ]ÑÙÎ™ÓPš‘ÑÝ’SšÓP›Ô–QVQXQÕÐ]ÑÐ]ÑÝÌZ‘ÝÑÙÎ™ÓP™ÓP›Ô–QVQXQÕÐVXLYÚŒŒ]ÑÐ]ÑÙÎ™ÓP™ÓP›Ô–QVQÓS˜L”X‘XQÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓP›Óš‘ÑÓ˜’T–QVQXQÕÐ]ÑÐ]ÑÙÎ™ÓR]Ì\’‘P™ÓP›Ô–QVQXQÕÐ]ÑÐ^QÜÖVL\ÙÌÙÎ™ÓP™ÓP›Ô–QVQXQÕÜÑXLÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓP›Ô–QV^•ÞQVQXQÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓPœÓ–]Þ–›Ô–QVQXQÕÐ]ÑÐ]ÑÙÎ™ÑÑÝRN]ÓP™ÓP›Ô–QVQXQÕÐ]ÑÐ^‘ÝÑÝÝÑÙÎ™ÓP™ÓP›Ô–QVQXQX^•ÞQÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓP›Ô–QÓS˜^T˜•VQXQÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓZ‘ÑÓ˜’S›Ô–QVQXQÕÐ]ÑÐ]ÑÙÎ]Ì\‘ÝÑ™ÓP™ÓP›Ô–QVQXQÕÐ]ÑÓVXL\ÙÌ‘Ð]ÑÙÎ™ÓP™ÓP›Ô–QVQX‘ÓSXL”XQÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓP›Ô–Pš•ÐÔ–QVQXQÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓV]Ì\–œÓP›Ô–QVQXQÕÐ]ÑÐ]ÑÙÌ‘ÜÖVL\ÙÎ™ÓP™ÓP›Ô–QVQXQÕÐ]Ú‘ÜÚÕÌÑÐ]ÑÙÎ™ÓP™ÓP›Ô–QVQX^•ÞQXQÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓP›Ô“S˜]Ôœ˜–QVQXQÕÐ]ÑÐ]ÑÙÎ™ÓPš‘ÑÝ’SšÓP›Ô–QVQXQÕÐ]ÑÐ]ÑÝÌZ‘ÝÑÙÎ™ÓP™ÓP›Ô–QVQXQÕÐVXLYÚŒŒ]ÑÐ]ÑÙÎ™ÓP™ÓP›Ô–QVQÓS˜L”X‘XQÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓP›Óš‘ÑÓ˜’T–QVQXQÕÐ]ÑÐ]ÑÙÎ™ÓR]Ì\’‘P™ÓP›Ô–QVQXQÕÐ]ÑÐ^QÜÖVL\ÙÌÙÎ™ÓP™ÓP›Ô–QVQXQÕÜÑXLÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓP›Ô–QV^•ÞQVQXQÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓPœÓ–]Þ–›Ô–QVQXQÕÐ]ÑÐ]ÑÙÎ™ÑÑÝRN]ÓP™ÓP›Ô–QVQXQÕÐ]ÑÐ^‘ÝÑÝÝÑÙÎ™ÓP™ÓP›Ô–QVQXQX^•ÞQÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓP›Ô–QÓS˜^T˜•VQXQÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓZ‘ÑÓ˜’S›Ô–QVQXQÕÐ]ÑÐ]ÑÙÎ]Ì\‘ÝÑ™ÓP™ÓP›Ô–QVQXQÕÐ]ÑÓVXL\ÙÌ‘Ð]ÑÙÎ™ÓP™ÓP›Ô–QVQX‘ÓSXL”XQÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓP›Ô–Pš•ÐÔ–QVQXQÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓV]Ì\–œÓP›Ô–QVQXQÕÐ]ÑÐ]ÑÙÌ‘ÜÖVL\ÙÎ™ÓP™ÓP›Ô–QVQXQÕÐ]Ú‘ÜÚÕÌÑÐ]ÑÙÎ™ÓP™ÓP›Ô–QVQX^•ÞQXQÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓP›Ô“S˜]Ôœ˜–QVQXQÕÐ]ÑÐ]ÑÙÎ™ÓPš‘ÑÝ’SšÓP›Ô–QVQXQÕÐ]ÑÐ]ÑÝÌZ‘ÝÑÙÎ™ÓP™ÓP›Ô–QVQXQÕÐVXLYÚŒŒ]ÑÐ]ÑÙÎ™ÓP™ÓP›Ô–QVQÓS˜L”X‘XQÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓP›Óš‘ÑÓ˜’T–QVQXQÕÐ]ÑÐ]ÑÙÎ™ÓR]Ì\’‘P™ÓP›Ô–QVQXQÕÐ]ÑÐ^QÜÖVL\ÙÌÙÎ™ÓP™ÓP›Ô–QVQXQÕÜÑXLÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓP›Ô–QV^•ÞQVQXQÕÐ]ÑÐ]ÑÙÎ™ÓP™ÓPœÓ–VMMÌÛ›œœšš›UžMUÛÑ[ŒÛ\ÖÖVŒÝÌZœ^]š›SžT]ÚÌ™KÔØÍUR”PÙZS‘]ÙØ[[[^NšRÊÛ–”TYŽZÒ^“KØ]Õ‘ÜŒÌ[S›’ÔXZÛÒ‘UÙ‘VLS›ÑR‘ØN\YÖ’žÌœMÖ‘œŒÚÒÑÔMÖ–[XLÜM\M’˜ÙÎRLÝL–ÒTŽÌXÖSØÕÑš˜“UÐ›Ú–S•ÜÜRÓR’UÝX\ÛÍžZUMØÜVYN\ÚUØQ‘›ÐÎ’Z‘’”V™ÜU››S˜‘Q™Ü‘Õ^ŽËØÐL[SZØV‘MXÚ[\“[Q•ÍÔ’™QÒY›ÞPÜXÑÙÐTÝNX\ÚÞS–L”ÍØQÙT•žPÓÙ™R]LLž\TJÞš’’˜š˜L
ÜM’•XŒÒTX“’‘’TYÞÝž[ŒUPÐÜ]“ÓÙL‘ž’ZÑ‘ÕÑ‘ÚÖNQÕÕ[™QÜÞZ˜ÝÚÖšØ[ÝÖ›UP•X“ÔM–‘‘UVÌÒ™ÔTS•˜–ZÎ[ÓÜÔ‘ÎY’SZÐÑœ’SÔ›Ô™LQÕÒ\RS•Y‘’V]ÐJÑÛ‘‹Þ\“ŒÊÓ][S•‘•šÍšš\^UVM•S[\PZ
ÚXÔ^ÔMÑX•ÑYQÌXÐZÌY
Ò›ÝTÐÑÝNÚÌ^MTMXÓŒÐ^˜^šMZÖÙÚ]ÌÝV”˜œ]ÙÔÎQ’ÕÒ[ÜM’šÕNÒSQNŽ\›ÎQYZÙUÌYÐÛÎØ^›˜SšØ”Ù˜U\][YR”ÙRÔÑSÛÐ”ÚØM“]ØÓ\›U\ÜRÍÜ”•š’”]ÓÚS\[ÝÜÖ™›“ÚX•U›VV™ÕØÚ›U™ÜšØZÕÍQ”ÍÑšQ]ÛÓ[Ò]ZÙœJÑPY’š•[Õ˜˜UPÖ”ÚØÝŒJÔØYXÛ]SÞ^ÑLRÓÕKÒÙ™”ÜÝÕÔ“ÐÕÒÖÜšYÓ]X‘›P™ÛÝ”\Þ›^^˜ÑNTÜŒ˜QÓžV\ÙZ’›ÑLšÕPVSU]ÚÎœ^TPÛ‘Ü”]YÑÙÌœÒ–”MÙÚž™•Ò^™ÛÜšÚ]ØJÝÖ˜]‘YPÎUÚŽÌÛÖ™ÚÑÔP’Q”ÕÕÕ‘ÖÙ•XÒœS“‘UL˜Õ‘˜’JÒÍ•›ÍU\[™[X”L•Ì‘[Zš‘ÙÝÔX’‘Ì•”ÙV’šYžÑÚÓLÐYÛÞR™œ•Ú•ÓUÝU‘–ÑÓžR^QÕÓÜXÎ“PÜS“ÕP“ÖÎ^]ÒœÔÕÝUNQÛUYÞ˜Xž‘’Ì“Õ”ÎQ–[ÎÓÍÛžÓÓ[LVËÐ‘M“ÙÙÖ˜ØMœ”ÜÝ
ÛÞ“Q”SËÑÓ]›L•NÒÕPLž^]V›M]QMÜ•Ôœ‘RSÔMØRŽJÝ”QRUÐ‹ÓSÜÚZÝXPÒMÙUPP’˜‘ÚšÌ^P“Ú
Ø]LÌ]ÓZUUØUžÕÕL‘ÚŒ“ŒXUJÜMU”ÒUÑÒÓ“ŽÝÜÑ^•^˜[ZÒ]œP›ÝÜQÒPLŽUÐÓœQR™Z]\YRÑNX˜”Ô™TÍ“UZÐÙÛÐÕPœÚ“TÜÍÕRÔXÛ“TLÔ•ÓV^Ì‘Tœž•YÔ‹Ô\XUÖL’œ[ÔÓÛŒ^[TÍÌÓ[Ý\\UØ›SÚØÙ•–•šVŠÔRZÑ•ÕÚVUZÜYÙX\“”Ù’Ó[–\ÝL’žNR‘ÍYËÓYÑÝ•V[ÔžŒRJÝVŽŠÊÓU•ÎXRQ]ÓR”XR^\UÕ”ÒŒT“–NSŒY’Ñ^SÝ’Ð[˜Ý^ZœRSPNSÝÒÑ““LTX–T™›Q›T’V[[ÑÙV^ŠÒÒÝÑXYÔÝÑÕÝÛ]V[]’Z\”ÔXÖžJÛ^˜[\RÛ™‘ÌZÝÚ›Y–[P›ØÑ“ÑŒQ^œYÑL™•“YÞNÝUTQÛRŒ›RÙŒÖT™‘UÝÒŒÒŠÑ–LÑœœ•Z–Ø›ÛV]ÎQ‘SÚšZ‘PØRNYNŒ•”“”ÑZÛÙÓÓœÑNÌM^“YYÛ[Û‘]‘™ÖZÚTT^Sž“SZ\Q™žQŒÙ“Ú”NÌÚÌÖNZ]V”Ì–žS[”™ÍUÖ•™ÓÙÝ›TUZÜ˜Ú›ÌÙÛT\ZÝÚÎ”ZÝPž•›ØUÒÍMÛšÝœ^•TXUTÌÚNNZÌRÑ\M]ÖS[ÐÐžXÝYSØÐZÒ“‘ÜœTšUÒ›šÕZ‘
Ð•–]ØS›ÞP•KÚML•U“Íœ•[LÒYÛ›ÍŽ\[MUŽÞ’ÍŒJÖ^QYR]–˜‘LY‘ZÖÚP’™ÞXÝÚÌ™RÌQ’ÜRR›’\UÞ–NXPÕÔÛÑÌÜÓPš•–ZÜ”Q“œMÚØLÕÚSV˜X“LÖŽÛPœTÚMSšRÚ”Ù“MU–›ÒÜÌÔÍ^\Ô”’R˜•Q”
ÕUŽSž‘ZŒ\ÒÒL‘Ò–”ÚRÖMJÝLQ”PYUÐ“ÓÔSÜSÍÓQÖYÕV›Ø^ŒT˜ÔÍN[›’Ü•
Õ•Ý^V\PÔšÞ[ÛšT˜MÜ–YšP‘ÒLVÜÑL”ZÌU‘’ÝÙÊÓÕY\UÍ›žRÒÖ”Ü[š˜^QÑ‘[ÝšS^–LQR\”Q›XÞM™YÜÚ›\MLT‘ÚT””––’“ZZPUÓÚÓÚZYR‘TULÛ›Ó”’”ÌQÍ™[ÎZÔÙ•ÝÝØÔNY™˜ÔÔN“”ÐZÛTËÚUSÌŒÕŠÓ[[ÐÙ”–\ÒSQVÐÙ^–PÚT•Ñ]LÍ•ÚU‘RÚJËÒÓœ’U›ÞžR[Þ’QR[ÙœTMZÔMÖ’NÌYÚZ^‘œLÑŒUŒÓÙ’›ŠÖYSÝÙRÛ\ŒMZSØÍZ•šÚY^NVÚÙLœQÑœš”‘Í–LZLÔ”Õ›”Ú\Õ‘^UÚÕ\˜ÛÎÔÐœÑ’PV‘YÞP”Z‘ÑÙPØYÞ”ÒÝž\–UT[RÍŒ–’YÕÒÖT“œTÚØËÕPY›TLÐV‘ØÝÔZØÝUÚVY“ž•TÜÛ™^ŒRÝ]ØUÝ“Œ”›PÒÕ^ZÝ’TPYZV]^”ÜÍ•Ð›’˜ÝØÞ’Ñ’PžMÒÒVŒ™–‘
Õ‘QœRÝÜÌ’”ÐÍÒSØÜÜ˜“ÑŽÓ\”^•™\ÕZ›™ÒVÐ”P’ÐVVÕÒÝY“ŒÚ–VT›ÒRZÒÚ[Ñ›Þ]\ÜYÛP‘Í[[‘œX‘^ÓÑšÐUššU”“NQÚÌÊÍœQQ[ÍÒÌÓÒ›Ó˜Ú’•Ñ^[ÜÓÔÞ™]ÖžZÙZÚMÔMU›RYV]›\QØNR[Ò”›ÚÙÕÓÖšÔÝ\[T’PŠÕÌ[ÌÛÌ™‹ÜSXšÕ–‘TÙÞ›Û›V]TÓ›RÌ›Ó’ÛÌÜÞLTU^’ÚUYUUS’[Œ›ŒŒÛÜ‘XTUZVZÑ
Ô’–ZÔR^QÛ•ÌS‘ŠÒÒ–ÍYÞNS^\”NVN]YÍšÐ\ÑÞ””ÓÜKÑÑÕšÒ^YÛ•YR™LœØÞÝ™Œ”ÔÍÖ’Ö’ÌÑR”^œ˜ÜKÓÖ‘UP\MŒÜÒQZÓÕÑQ”ÑÑ\U[ŽÌÙ‘Û›™’Ì’›ÐÕQÛÜ™L’TZL›X‘––RLLÚ›Ü]Ù›œÕR”–’ÒÍLU^RJÙQTÕÌ]ÍÝTžXÛœ‘KÛ’ÌÕRTÞ[’U•\ÜR[šT\Ù‘VM™Ø‘žQÔLžŽ]ÓÛ]ÙY”˜ÝÌ˜Ø–’L‘UÍJÌ
ØQ“ÒÚU]šÔœÝÝMËÐ‘ÖTRšRÔUŒÌÛ]ÕMÓZœTUÓÍ™T’ÍPÌÍUÜÒÒžTÚSPLÌTU•T’YXšZ[’[UQNUÝZÝÓÓ^ÔšÚÜÛÙÖ”ÚÛšÕÊÝ\‘
ÐœSÛÌœ
ÖRžM›U›U’ÝÙQ“ŒÑÙLMŒTZJÑ”ÐÓP”Í
Ô‘TØÒ™™Ð“Ú’ÚÚÓ˜U’SLŽMZÎNT›ÚÜšÍÛT‘Õ‘‘ÒÔŒLŒÚÓZÜ^[UR]ÔÖ‘LU’ÌPÞœÍV‘˜™NÛœÒ
ÙÐ“Œ›ZS‘ÝÔ”›ÚZ]Ž‘^”ÚQV^ÛNUMÕ–‘PYÌÞMS›”XÊÓÕL˜ÔÓžUT“šÜ]œ”ÐšY^Y”ÎXÍœÎÜÛSž\RXÝSÞ\ZÐ–’[UÔÒ’[^Þ’žSQ‘›Ø–ÝYQYÕÙR’Œ•“ŽZÚØÔ^PTÒQšÜÎ]Þ’”LÚÔLŠÕ“’’Tœ[[ZÒPÌÒXS“LŽLŒÝS‘ÚÙ•Y’ÜNZ[’˜Ù‘‘Í•TPÓÕU”T[˜P›]ÛÍN^MÚÞUžR^NÖÍÎÍYUËÍ™[ÒÞ™šPÕSÑÛÓ’^M›ÒšÙUÓÔÚU]ZÝM”ÛÎZ^T•ÐR”UÒŒZ•œSÔ’žœ’ÓS•“QNMVYÚ^šPšZ[’ZSMR]Ô”ÔTÖQMÑÞ^Œ›ÕMURÙÑÒQŽ›Ù“ÕšÔZÞ’œÒÚT˜ÍÖZQÑ“••ÑÞXÚQ[ËÖ”Ú˜ÕÔÔRŒ‘USÖ””[ŒÔÜÚÝšÛNž
ÔYÓNJÍœMÞ‘ÝÒÕÐŒšLZU[XÙ–šLPXMÎÍT’\RQYÒšËÌÌÑUYXZ[ËÕ”NLÜÚžUS™ÚVœÕQQQ•UU”^
Ó\•ZQYÞXÔZÞŒÖJÜ˜ÊÌZ\™’›Ó›ZÎU“•ÍVØTœ[œÛÚX]KÞPZÑÐÓÙ
ÒÑÑ\ÑQ’^‹ÒÌŒÕÔžJÛÌŽRœY^]ÍÙ”ÌÍÔMT™ÞTÌ›^™ZÌPÒMKÙÕ–ÞŒ
ÝÓÖ’™Ì’LRÑ’œÞZÜÌRR”“ÓÓ”Ì™ÝTÑJÍL]X–•ÌÔÖYÑ’\›‘\YVLÕžV‘YÞTšÌTŒÛÓÞT“›SRS›YÛÖ\M]•Õ˜ÓSÎZ”’Û•ÜÔ[YUÚMLŒPÌPœ‘“QU•›^RQSŒ™JÑN[Þ•ULÍÚÚQÕŒÛÕ‘YÍQÌšXÕÚÐ–’ÝŒš\ÔØ˜ÕÚÓQQ\ÜÙZX[ÍÙ˜‘]ÕTR\Õ•T’ÞÌœ›YØÙZQ™ÛYÜ™Y™žM’ÐYPÒ˜ÑSÕ[L^L™\ÚÙZŒŒÙÝY™’UMÒØÚ[N[‘VLœÜØ\ÙYÍÑÌšÍQZÙ’™M™RÜ]Sž“MŒÜQ›Ð••ZUÚ’™ÚÑUÜV^”PQZÍQÑ™TÙ™ÔÌÛJÒ”PÍÍÜ”MTMT–LÕ“›œQ^SRUTÔSš[[LYS’ZQQ‘Ø”]Ú•^˜ÙV˜]XR•\XT•“Ý]Û•X^Ž\XÙÚÓÕÔØ–™ÑRÚžŒT˜”Õ’QZ–[ÔŽÚ’›”T”ÒšV™U™V‹ÝQLTÍ‘Ò“ÑTRY\œÓÛVÕQÐ›ÑÝÌ™“ÜMZYØ^YXTTØËÙM™ÓXUÚRRÚUÎT\•Ö“’ÕZ˜“ÚRÕÝÙÔN[[ÝV“™•“Ü’^^™V”˜Ô“^QÚ•ÛÖ˜œRÛNSQÙ^ŒÕZ”›Û”Ü]ÕÊÌ’ÛÕšTÙž]›STUÒšÛž[]^UÔÍ[ŠÐŠÛQVÜSÔÑšÑÒY[ÛÚÓÚ
ÑZœ™LÛœÐ\RÛ\›QÖŽÌÓ˜MQ™Ñ“ŒVÜU›MR˜Ý˜–ÍR‘“’“”MžÒV’ž\[ZØ•[ÛLÔÍN^Ö”œÔ˜ÙÑ‘[ÌŒ”ÚÜQZ˜Þ‘ÜÝTT\™ÐÎPÔ˜]’ÑÓÔÖYTUX’–^XÕV™›Ø\Q›’ÐÌÙžS™ÙUÒÝYœÓMÞZ•‹ÓšÜØÓÍTÕ“UÍœ[Õ“Ì•XÜQ”MÕÚJÞÌ•”‘NL•M\RUMÜØ\ÎPÔSÖLXÓÚÔšÕJÕ˜ÕÑœNY[ÕÕ›[MLR[˜Ý–Z’œ›’ÒZÛÕÌÔ”žÒÍ”PÕ[Ú^[’šÓPÙ[ÔVÝXÔMÞ\•SQUÚÔNZRÓœŒ˜‘“T•ÊÙ’Õ’ÔÕUšŒ‘]šPÓLUQ•SR™\ÓØMY^TSV\ÍU‘”^PÑM’TMÞPZ’VÕÛN]V\
ÖSÒÖRÚÚÞÑÓSUÍžQ’ÌÍSÑ[[“ÕU•š›TKØÍ’TÑ\•MRÍ‘‘ÕÙ‘Ò˜ÛÙÕ™œ›žÌ^ŒLXYMÔR]]ÑV]ÜÔQ˜R–”Úž“RœYžV’[ÕÓÞZYU‘TŽš™ÙY]›X›VRËÐ›VÑPÚJÑÎXÛÝÖMS^ZÓÛÓUÔÕÔ™ÒZUNU™Û^RŠÓ[”šM“Ó˜ÔÐTš™’^XNTÜ–QÝ”‘ÜÒÖ”šÚ\–œ™ÛËÕTQTÓL–QÚÔÎ[UŒÔ•ÐY‘œÚ‘TRQœ’ÕÔ’•ÝÝ”ÜšœÚœÚRÔ–”ÒPÔNSUV[ÚÒœÕ[ÒÚ”‘R[X˜SŠÒœL’’ÊÙQ’QLQÎ›[S‘Ü’‘œPN–šÒ”ÌUÌÚ•Ô‘NÍL“LQÕ”KÛ‘UšÞTÝÚUÙU˜ÝZÛØÛ[Ú™•ÑTÍ“\Í’QÔ^PZ^YÔPÙÙÐ™[ÕUZÐXÛ‘Q\Ò–SÜZT]Œ“ÛÔÒÛ“”ÍL‘›XZÞSŒž”˜U˜\S“LT^QMTY›PZT“LUÜL–\\UÛØÜ[ÞÝS[Y“ZÎÛÝ[ÛT›[X’T•Ì[ÙÚÚÍÛÕQÒZY]UÕÌÕRQÕZNÑ•ZÝ’RUÖZ›•Þž“\SÖ’ZU’ËÛRÍÕKÓVU“ZÛÐ“S“XŒÍ\T‘TÓšMÒÜÑNXŽ]UQÐÛÓ
ÒÕ’STÕ”ÎUUœÔ^LÑTJÚÚUÜœLÜÑU™ÚÌNUÔVYY–“\ÙÔÎÖœÕ–œ•RV’’‘]ÙQ]ÚÐ‘JÝÐSÖQÚ]’ÓÒ”Ò˜QËÜRÒŒZVRMN”ŽZL[”ž›SŒ•ÎLU[RLÔ–TÔ‘Ý•Z”ÒLM•[X›Ô‘ÙÓ“‘]ZÓ‘•Õ™Û“™KÜS•˜ÚQÜSMÒÔœ”•–V‘ØÎÍZMÕTL–Z–L”Ü’Í•–žJÕ\Ø‘LS™›UMŽM›^‘Ñ–TœÞXÓL“Ñ‘šÑÛXRÌ\˜›ÞŠÞŽVÕÜ’›Ú–U[NSÞXT””TÐËÛØÊÖYÍ˜Ò•Qš’Ð’ÙR™Î[™ÍÜŒœ‘‘QÛ–š’QÒXšMSÒ[ÔÌ”QÕLULšSQÍN]Ö[RØÜ•–UÔÑJÝMT\Ø““QÒ›Ô\ÓÒ’–^SQZ˜Lš‘ÝÊÖÍ”˜ZÓQ™[ÓÖ”Ð™SÝÒ’Ø[U]Í“Ù•“Ð‘Ž]•ŠÓÞ™‘™ÚZTTÔ‘–XMÜÙ^ž\VšRSM]ZL›]’\ØUœš‘Œœ”ÛŒN––]]Ö[œ’[Ì‘ÝÛTÝY^U›RXÓÜJÒZT™ÚXUÑ]TÓRËÓÖ‹Ý]‘ZM•›ÚÔQ’ÓŒ\ÞXÑÍžžÚRKÛPR[PZLšÑTYTžÐ\UT[”›]]U[œ[ÎRØ›ŠÑØÛP™ÑZÛÛÖXTÜÍRMÊÓØXšÓÜ“Ô[ÝÎ•ÜÑžQÔ’Z\™ÙŒž˜M“ÖU›]Z]UÒÜUM[Ö‘Õ\ÒTÑ“^QÖTM’ÚœM“UÝ‘Œ™U”ÑÛËÓÝ›™ÙZL]ÌžMÛÞU’RžMSLž[Òœ[ÚÒÒQ’ŒUPÚ‘ÑYÞX›ÛQ“ÓŒÙšVŒSNSØV\P‘šÝÑÞ\‘ÒÚSÞQŒŽ›TÎÓÚÚZSÒËÙËÓ’ÍMÛXÙÍŒÔ™ÜÞVŽR™ØžY]ÌSÜTÙ˜›Ú]ž[›ÒXM–š•›Z•ÝÒ™Ý[]ÛÚ•’”ÜQÌTž‘Ý˜L‘MY›šYZœÖRÐSŒŒ–TÙÛ“ÒTÌÑ[ŽM‘“VQžLÚS™ŒÚÖŒÖ‘Q’ÔÝYXÓÔUÝU”ÒLØ’TTÎÝ[ÜœLTÙÚ•TUØ”Þ]™›”•V“Ì˜™RZ“”“šXÍšØ[U–S’žžM]ÞPRÕ›ÑÚÞ[Ü[ÞŽÎSÙ–MÛÝššÓ^ÓZ•XÚV\[V[]RUÔ“UM•URÛ–•UT’œYRÞ˜ÒÛœPÑÓœMšÖ••R‘›“›[L–ÒÚRÛ‘QRÍÞ^œQ’’ÓÐ^]’’ÌÖ[T’U›˜žUVSNT›œQUœV›LŠÕYÍœÑÙÙ–ŽUSR™TR”RÍ”žŒ›Ð’Z‘TÑ•PÝšÐŽ™ÓÍÛÞ”[]YLØÝ˜YQŽ]ÒRQ‘]ÛÊÝšÍPÒÙœÔÙÔÚÔ“ÛSV\ØÌTŒ›S^•JÑÚÛÍVØ[ÓÒÚLžVM‹Ý•XÍ–PRÒ]RžV‘˜T”ÍÎU•‘NMQÚ‘T[ÍÍTÓ’“ž˜šœXÞR[ÝÜQÎ›Ø[Z]RÌ˜ÓQJÎÞ–\ÍÑÕUÍœÙ\ZÜZUÌØÍÕ›ÍUÖÕšL\ÕP^Ô‘ÎMÓÛ”›Y[šÌ[ÕKÒQXËÓVL^ÑŽUš]Ø^MÔ•ÕŒÓU™’ÎUÕ•TÖRSYYÞ–SÌ›ZÑZY–ÒšœÝZØÌL”•ÛÜYU˜ÝVLXYŒN–›QÙÒœÛ’”•Ü^ŒÍPTMYÙÌZMÑSUœœXÞ“UŽT‘›ŠÖNÞ[Ò\ÑMÓYÜËÐ’‘JÑÎ‘NQMŽPÛÜžPXÖ]Ó‘˜Õ™ÖÛšVÛUÑ™‘UÒŠÌ\‘šÐLœU[RVšÔR™ÚRÛØ\Ó]]SÛÐÕZ’œÓœ“ÌÛÕ‘ÌÛLŒÜž˜“Ø’Ô’ÖÛSY\TÌÛRÑÛÐÛÚÝØœÜ^X^\R›œÝ\›™“^œŒ•œRXœ‘MŒUR˜“šÚLÑÞ”PNV˜R‘YÕ›ÛMÒ^PQ[Ó•Ì\ÓÔRTSL\ŽV”’R
ÍÛPÒÍ”Ü^MZÑ˜Í^XKÌ’ÑT™TSÜS‘Ž’ÓÒ[‘ÚÔÍ˜PÓS™L‘ÞVÚMUTÝZÖ˜ŒÚY›‘PÕ›Ò\ÝU˜™ÛRRÞÞX^ÓÛ‘–U˜YÜ’Õ’ZÑV™Øž\SL”UR›\ÕVÞZÎV••ÝTTRÒ–]ÛÍžXÚT›ÐÜ›^Y‘\ÖRÒœ’X›R]™”QÓÞ’•˜˜˜ZÑ˜TÑÛÞZ]ÚXÑÜ–^•ÜÒN›ÜÕ“Ö\ÓRÍLØÙLLVTÛÖ\ÜV\[’[YÝ[‘™Û^“]TØ›˜ŒÑ›^QÓŒU™Q“TÝÞ“•MSTV•Úœ•ÙŒZ•›––•SU›Y™]ÒZÝT‘””””‘šUž’˜ÐÓZSÕÖ’QšÜMÔUÙ•”ÞZLLÓP“Ö™ÐŒÎÚØ]Ò”[YTÒ\UVQšÝÌPž\ÚRZRœÓ^ÑÜ•Ñ[žŒ“Z›ÓÛYÌ]VTÐÒ”‘™YÕÞRL–““ÑXQÍ•Qœ]QÓ’˜[\‘›[’œ˜Y‘\UÙ\‘ÙÜ–’\ÕÜ”˜PÜ\’R’“MÔŠÙ•LMR“Õ\]‘˜XŒÐÚKÖRSLXUŒÙ›‘NYØšŒ^ŽXÕÜ’šS”Ð’ÜšQSÓÐÓšÒUXRÔ™Í’œÖRÕL“ž“M•ÎLUšÕSÓÖLšÕR‘]žM’RÛ™Ý–KÍMSUÕ˜YS[œ˜ÙÍ\
Í–MUÔšÒÕUÓÐÙÕ™ÙTØ[ÚÕÙVœ]›ÝY[ŽR•‘ÝÝÛÑÒT›X[QÜÚL›ÒPØR–›œVTQ‘œÓQÊÐM]X\ÙYÙL‘UŽV“Ó•“Ü[PÝPYÎ]’QÒÐ\S[Q•^™YZÑÑÝ“ÊÖ™•Q›‘Q’ÌšÜY’™LT’”šÕPÖPUÞTØÕMœÐœ˜Õ”ÞRRŽÜÓÒ
ÛL[Ì˜ÝÍ‘Î\^Ó˜Òœœ•TœÌØ–œR™Õ–›Ü’QÛØÑÍQUÒ•VUUÙ[œÌ‘QNJØÒœ\žÑ™QQØÝVœZšÞ]YÙÑ’ÍLS‘šVMÐ“‘L™LR”\YÐÑSÛ^JÞÓ[[Û’Mœ“LÛ“œMZ^ZMÜ’YÓš›žMP\œÌSŠÐœTQÖ’ÞSÓTÓQZÒ[MœÞ›RšV›R“’Þ
Ø’ÓÌX’ÎSÛZ•ÞÙMR’ÝRÚ”ÒÙYÌMÙÓMÖMXL›žÕœšÕ•Ô[ÚÝV˜Ü–TÎ[PÛ•ÞSSÚÕÕTTÖž›žZLÔ‘Ý‘ÎÒ–^”ÙÐRÚÕŒÚÕÖRQUQÌ–NRÍÒ\Œ”‘^Z”šQÕ›ŒÌÞ•^ZM
Ú˜•ÔXQÒœSšÚÑœ\˜U‘ÎVËÕÐÛNZ“™XÓÍ˜•X˜˜ÞÛÌ›žQN^Y\ÕÒÐYMUÙYØP•šÞ‘U^”Ü]“˜U•[Mœ‘™\ÒÝÔ“ÌÓÕUÎž’R˜ÐQ“NÔÌRTÓ˜[ÖœUÜŒÖSM]PÕÍ]TšÑÑSÔU^ŒYRÞÛ‘”Ô”ÞVÔMÜÛMž–X]Z›ÙÛžÚÑÓM[šÛš–YPÌÔÐÝÑœRLPÞ][Ñ˜“ÖØŽL“TÖ]›Û•›T“T˜ÒÛM‘ÎMZÌMQ[Î^‘\’œ–QS”N[^P˜ÑRÌ•ÜÕPÎLUÔ”ÜÞQÚ\TR^]Í“ÎÛÔV\ž˜V•R^’šÎ^T›Û[Í˜ÐÝ’Õ‘’“’”ÝRÙUž“–[“SL^–^R^YÜÐ’
ÝØX•Û”ÑÛÒ›ÔÛÔšÖR˜LØ[ÓLÛÔ›ŒVTÙUœÞ^‘žÌ“XR›Ó’^”UTVŒŽÚQœ“Û”ØŒ[QÚ’’TÖTÕYÖ]“Ü›V^Œ›”UØ‘ÊÎPTTŽLUQ•‹ÑÒœLT\ÝQ]SSÞMÑšÒ™ÍÍ•TS’Õ””Ð–’NÞ’ÛÌÔ[MÐÒVTM•
ÔZ›NÝÒœÌ]ÞÔšQUžÙÑ™“]\ÛÚ•”’ÜÐRT[NU\Y’UšS[JÙÚØZÔ•[Ú\‘M^ÓQ‘ÒÑ›–ÖÛ›šÑLÎ“U]\TZÐL[ÑÌÙÑM\Ú\]ÝXÕÐÖ[’LY^Y•UY›ÍÞP”šÑÓÍQXŒœÒ•Ó™•ÝR™ž^^”ÝÊÚœÜÌ‘TN‘“’’Œ‘V›ÒSÖVTT]TÞPÌÛÍØ\QZ˜QZ‘[SÒPÛœYÒUMØÔÓ[TÍ[™ÍV˜RšÖÚ•šÜTL”Ú\M]šžT“œšÛÍYSV\MR”ÚR“›PRQMÖ“ÑŒ\ÔMÍÑV]ÍMV^]SÒ‘‘ZÖLRQØÙÍÜSÌÞŒZ^Í\ÔÙ“M“\ZRÜQ–ÓÌÌTžXT–\]ÝšÛ”Þ]U•’Ì“QM]œ\Ù[]™‘\]]”•™™™ÓÞ•\ÑÓ[žRXÖÓÕRNÞžÞÛZÝ•Ü˜S–YÛš”NQX[–ËÓÞØ\[ÔÍŒ›Ùž™ÓÓ’™ÒÎ]^]ÝV›S\ÚYœNZRÑL[ZMÓÛÜUœÙÐ–’‘TÖ’ÒV‘ZÕÌNžÙYš]Z›ÔT‘Û“ŒÙQ\ÙŒ[\ÕÐ“™”Q”[Í’ÖžVTÖ•ÔT^[ËÒšÕ˜Z’‘Y“’\ÌÜYØ›LÙT’œšUØœ\”žœMU˜]VPÓœ’ËÕ™ZVVšÍUÎYRÍÕU˜Õ‘žŽSÝT•X\ÜU\šÌØŒ”Í’ÛÕÛØ“ÒMQ\ÓP‹ÚÒš][˜ZVNY“[]šÑÌ›M^LÜ˜ÑV‘\[ØØPQN’[™•Õ
Ñ–•ÒÍÔÐ–”QTL™ÞLŒ•›–Ý[ÖÓ›ÙRÓZØÎœ–[•]Ý[ÌVÚZ‘ÛXTÐ‹ÑÜšÚØÛ•ÜŽKÕ“’XÕÓ]ÛRÍSZÒ\ÚŒÍ\ÝZÐZUžŽPšÑU”Qž]MÖPSÚÜLXMQš”]ÜÙ“’Øšžž]ÛÒÛR’–XY^•šTÐSÒž™LZ[ÖLU”RÚÞ•–RÖÕU‘Q‘œÕY’SÒ[UÛZÛ•Nœ[Q^\Ø\X›Ø^™UQ“Ú˜PŽZVTÛ\RÛX[’ÙÖ\˜Ò˜™ÛÔ”˜’”ÚÝZÛÞLTÛ›ÜV]šRMœÝVšÎU•UN–RZ•ÑÜÐÙÑÐŽÕ›NL‘RVNQ[œÛ[“ÝØÔ’^QQÛZÐYÛ”Ñ•M™”œZÍ\™Ù™ØÙËÔTXÜÖ^TÑP•Z”žÝYÖÚÌ‘T‘ŒTŽÓMTL“Ô^ŒY’LMS’S
ÓM[™V”ÒMZUPšZŒÑZ\ÖÞL[ÑJÔYYšœ]œ”ØUVZR’LœU‘“T’SÖ˜[Øœ]“ÑÜVœÍÓ˜™RSŒ˜ÔQÕZ\’Ð‘S\[Ó’Ì‘Þ•ÎUZM\›ÒÝÕÍQÌ’YL™ÍÛšVÞ\U™XÑÛY•ÔžZQÍYÒŽL™š•]Ô•Z’[ŽQPÕSYXÙœÚÎU[Z™ÔLŽXU˜V“ÙÐÚPYÎšJÝLZQ[“\™NZÔžLÝÞ”U–ZT™ÐXÙX™Q^ÚÝ–\ŒQ›Œ]Ñ’Þ‘‘\œÖXXTVŒUTš›ÒV’ÓÑÔÜQZÓ^^[ÊÓTÐž”]NRÑÕRØ‘ž‘œRŒ•RÚ”’‘ÕM•Q™‘MÑ™MŠÜ]™ØÛSšž–R‘›Ö›‘ž™‘Ø’S
ÓUNžV“ÑQÕÐLSÓN›ÓÚSÒ–SŒYÚÞVRSÍžÜ›ÝÕ˜VQSZ’ÍÞZXÎXÝ›Û’]MZœ^P’ÕR’Í\[ÕÓRÒLØ™“’ÙÞÛ”Í\TÙÓž•\ÍÒž•ž]”YQ^”š[Ì‹ÚÌÒULQžUXUžSÜS]›ÌRZV\œÍ™–•”ŒÒ•RÑU™ÖËÞÑYVMÑLT™ÛS•Ò^’™’“šÐ’‘[ÙÖ›ÙUÌR[ÊÒÓYžÍÍÝšÚ\ZÐ•[M’ÐÚ]ZRš^ŠÐ‘•M›’ÓQSÕ\ÑÒM’U’ÍJÞZÔX–›œLžZ[Ò[Ý™Ñ’ÜžT”KÝ\KÐTÝ]\–]XNXÔ•“‘•ØLS]PV”M\PÖ˜“ÔÕÑÝÛÔQRÝ”ÔR–^\Uš•ŒÛ™MÙÝÔžŒÓÚÛM\Ö[L’TM]Þ–JÛY^URšŽTMQÌP”RZÎMœœ”]’”Í“›ÛÙ™R•™ÝÔS•ÚÚÌST[”šØ[›[•œ››ÒÔÐÖÑ^PÞSšÔÖÍQ˜Z]Þ“‘ŠÊÕ›Û’•Ì[ÜTQLU“ÐÛYZœ“LÒÜ’“ÒŒ\QÞQ’’›•ÞL\NSQ‘PÚ•’ÔN^•X”\•‘’Ü–›ÌÕ’SÒÔ”ÒÚ’S–”ÖØÚ›\ZœXÝÜVQ\U“\ÝÍ^T]L”Ü[SÔ\N›ZØ–NQ]UP”Q•š™•KÜÌ•ÕÚššUžYÌ‘Õ’Ú[[ÌØ•œ[œÑ™SÐ’š]TSÑMQP[ÚUM]ÑÌÜÍÕ]ÍYMÓXUQLžœS‘[T”U]ÍÐ[Vž]ÌÐP^Íœ[–Y“ÔSÙÔLÒÛŒ’KÛZ“Ü‹ÎLRŒUZÐžÚÓ›”ÒÑÝÛ]\[UÌUÖ”ØÝÙX•ÖžLTÒP™Û–˜ÒMQ›Ü]ÜÍR‘ÖÛÑ–YULXÌÍÞ’SÚÝXÞUL“Û^^™MQ“Ôš›[ÑÛUPÐœŒŒTVÝÛTRM[LVÝ‘‹ÜÑSÛŽSšÚØš”Þœ’SÍQ™TVÒ]ÕÚÌšÚL^XÝTÖ“PœLÑ\Ý]]QRP^’\œLT\’]VÙÍXÛRš“ÞÜ›ÛRMÙÛšÞ[Œ]ŽQLœœ\ÚÌšSÖœ‘Ð‘–˜]PÎT’œU“’ÐÕ‘šÌšŒY•\ŒÔÒ^šUR“TœØÌ]šSÔÙ•žš””ÔUš^˜Ð›ÛÔYžÕTYRMžÛVQ]R”Ñ’USÚ•Û•ÙS›MÑTØ\R™Ôœ˜ÜMÕÙ“]XÙSÕÎ–œÜQÓØJÙPÙÓÙ“\ÜÔZ‘ÓVÚÔ’LŒÝÙNØÙÛÐÍ–ÝšÛœ\Î–‘ŒTÎLÎÒLMÒ‘Y\XV[RØÔÛÙ“ÌZÛSÛ›ÔÌš“Ø‘ÜŒšÝÙJÐ\SÒQ•Ú™’ŽQŠÎU”‘T\RÑÙSÚLÙLMÝ\YÝÒU[QÔÔ’™RÌ^R]]šYÚZÜKÞ’ÞL]˜’’ÒSÑÚLÛ\^PÔ[”^Y]]SUÔM“˜VPS[S]šZQ”’–\ÌÕ\ÙÒQ›ZÝšÔÞPZÒ™Û\ØÖÚÔÌT”ÚT˜Û‘”
Ì\LT\STÜÍœŒÓÔÙV“ÛQœ•RšÛNžSUš•ÝZYÚÌUJÚUØÕÑS’ÍÚÛ“ZØY’‘ÍÝ‹ÑYY“\ÕRžÕQ’šÒŽJÛ›ÞVU•ÜÓ[QŽYZ’RÜ\\KÙ]™’]Œ•Ú”ÛÑÍÑÑZQ\MJÒÓLÒ›ÚŒÑÑÎYŽ\ÞÑØÐž[ÛUYLœMUÔR’ÑP’–Û[V˜ÕVÒÒšX›QÞŒ™L›ÐÛSÔ”ÜMÖYÛšš
ËÕXSÒLœÑ–š›ÌMQ[ŒPØ\UÎNÑZÍ’L˜”œ’[ËÛœÔÞ›“ž\Ô\ÜU’YÍ•UÚÑY^L[šP‘ÑœØÕ[ÊÝ^™Ò“\ÞSÜÚÕÚTZZ[ËÍ]QQÜ\NYÞ’PŠËÒ›™QÐ›ÝURÖ“ÒÓ‘•˜˜^XÌÐ‘MÐ˜X›’–•Ý‘L–U•ÑÕÔÌ’’PQŒœ\QPUÙÖYÎYš–TØT[ÞT™^^]ÛZKÞSØÔÙ”ÐX‘“ÚÝÚÑ›‘R™ÚÜ–œÔ”R’˜›T›PÙØ›L™•ŒVTÔ˜Û‘SÓQ’Ý’‘RZÍZ’^UÙL“ÛÍQ›PY”QÜÑÔÜÕ–’]ÑSLUÜœÍÛ‘UšÝÜ^–MÌVšž[Ø’\‘ÒŒ‘Ù›YÑÖÝTQœXÞ–™ZR™Y›™ÙU““UQÕV˜SZÌ’\ÕÑ]L]ÚØP•UØ\š’“ÛÓ•œØÚŽÒœ[ÎÐUÌÐŽLYÕ”P“ÐSR‘ÕYQ[ØÕŽYš”ÎXÎÛÞ\›ÍRTŒ˜ÐØšL^[””ÞQ–VLšZ›XXRžYUSŒÓ“[œŒÑPœ›ÓZ“ÒÓÛ\[‘]•Ü”NYÛ^V”]R™[Ü“]\œ™›V\U˜QXÔ”ŒR’ZR’ÒUÕ“ÖL“Ü’NZØV\“NŒ™ŒTÑ“•œR[LY[Ñ˜Ú–œÓVTÝŽ[ØÛYV›”ŽRØÙV^šÐÞPÙS’ÜMÙSPT[Í’\ÕØÌXZR’’Ì
Ü•–“ÞRM[ÝÒ‘œXŒ˜UUÍ˜ÛÖžŽSŽ^’”ÛTÙÒÜÒ˜•UÚZ•ÚR‘‘Ž^”›ÔÐ™QQ‘YLÜMÎR”Y\”ÐÚÌŒž™[VVVXÍVœÕÜT–‹Ð”›ØP]’ÙÛ[”ZšŒ–Œ™•ÍPV]›T[ÝXMÚ\MŒ’ÛX^•Þ–^šÚÐÞ™Y^UÓÑ\^MÕÒž–JÞU‘ZÎZQ™SØJÔLÛÌPYšÓ\ØžÑ^“YP•ÙRÔPUÚÚ]ÝÑUÙQœÑšžRÔ]UÓQRžÔ›RTL^QÔÍQÕ•Ù‘Ì’^Óš›[™ÐLRÞ•MP•‘VÜ]LSVTœÚØÛŒ›JÔSPÌÒ‘ÓÙÌ–ZÑZÞ•”ÑœR™ÕQM]ÒM[L^–JËÓMÌËÐPLÒÜÕ‘ØšQ[VLÒPØSš”œÍÝ^]]•’PRUÍ\ŠÔPÓ[ÑÚZÜYLZ]PÐØšMQÛV’ZÜÙÐT™‘\ÜN]UÌÑÍÓ]ŒMÒSËÒ“ŒSÎQšÑP”TTŽLXØÒÒR›ŽMÜÖšÒRÕÜÎR’ÙZÜKÝRÒÚUNXËÐJÕÚÜ‘V›ÚVLšÍR^”YQ]•›T›RšUYÝ^Ú^UYMŒTœNQÌÜÎŒÙUXÕžMÑØÜ’šXÌÒš”˜R”Ú‘Õ“˜ÛŠÍ’Þ’œRV’]TÓ‘YšQÓR•“Q[›–]Õ’RÚVÌ‘Ú”YÍ“’M’RÚÓX”\LTÞSS\ŽUÙÑRŽRUÜZUTU”•PÐ“ÐXÌVQœÑÌUÙÌÙ‘ÐÞ“ÐUQÜŒ\Ü™[S–š™™L•]“ZTÙJÙØÕÙÍ‘“^XUÊÕÓÛÚ™™ÚZž”Œ\›SV[Ú\ÒP˜]˜RÜZN[ÛÎ[ŒœRÕMÞ‘Ø“^UÊÒÑÌœÜÝŠØÑ•ÍTÜ•›šÔÌUT•YNXÝ˜ÜÓÔÍØVŒR\MÎÒÕ™“ÙLŒ[ÒÚZÞMÝLž›LÖLMT–[Ó]ÚÙšÚ™ÒV–ÐžV‘Í–ZÓÎQ“šÌ˜ÚÖŒ’””“KÐš•XÞ–•ÔSŽRL‘PÔ•›QÐ’‹Ý‘SZÔžŽ]ZŒœYT•\UÚQ”ÛÙÙ›ZÍMZ\™œUXÑ\ÜQRÌÓ›šœÜPUÙPÚR“SRT^TN[Ñ^•ÕZËÜL˜Uš^TLœTJÑ˜XÓ’œQÕÛšÑ’ÎÌXÞŽZ\ÚŠÐÊÊÑQ[ÚR•œMQ›š“œNXÍQ•Q\ÝRØÑœÍ•VšT›ZÓ\ÙUÓÒ’ÚSSLÒMÐ•PÒÑTÙÕ‘
ÝÜQÜÍTÍ”^UÚM’NR’ÛRR[Ñ[[ÚšY[šÔLÖ•ÜÍ]‘ÞUŒÖ
ÔU‘”NR”‘ÒÙY”’S›˜RXœXÞ•TL^[YÝÛœÊÜÔØR”“ZÜÖUÊÜRÔP–RZÝÙ“QÓ[Ô‘ÛX\œÒMQ“ÊÝ“Ü“ÌRÎÔŒ\’VÜ\P“NÔ˜™TÐP”ÐLÑÓ[N“ÜV˜ÛRšÕJÒŒ•ÚXÌMÔÞ[ÙÌÕÌ\P˜\Ð›Ó•^S›ÐÑ“UÓRKÛÜÞÔSÓ‹Ó”“ÍYœŠÔYUÒ[[\˜Ó[T•ÕYÌš›\–“”LPÕ^QYJÍÔÖ’SÜ]]Ž[Œ\M”Û’ÖÝ^]ÑLPœ^“ZÌ\œ]˜TÚPUÒTØ’Û^U’KÜZÑZ›–ZÌX–SÛŒ“Z]SUÕÔÛ“ZØÔÛÍ\ÐÛÓÔÜÛœZUœ\V”‘œVÐ˜][^TÐØ”M“T‘[ÒPV™ÙÐR’JÚ’ÑNPØZV–[ÙÑÔLQÛ˜™š•‘““YÔNRš™•Î^R”ÚŒÞœTSÕŠÒÙ–UÝÛ™ÚÕÝ–T^SÒ]“ZQÎ]Ö
ÕÚÜÞQ‘’•T–“MUU‘Y]Q›YY\RÙ•^–V›MØZQÌžZœÙZÒ^L”QÝ
ÚP–‘Ž\U“]SY[•”ÒÒ”]Ñ“ÌÐØVUÝT””TLXÎ•›VR’’]ÚLŒÑÛ]‹ÓÕÍ’Í˜ÖXYÑÞ”Ü”œÙÓÜœÕ^‘™RZÓ˜ÙÙÚÍÒÍ^•YÙÝšœØ’Ì”ÌV[NJÞžÒRTÍNÍR•˜]ÕZÛ•KÛRÒÕQŒÍXYÝPQX›•ššžT˜S•ZPT”Ý]’T”RÌšR’^MÎ\“ÑSÓYTÚ›ÚVÔ[ÜÒÒØX\Ó–•œR”ÑÍ“
ÊÑ˜”Ù‘’ŒÓUšÐ˜Ñ^‘RÚ˜^ZLžS
ÔÛ[ÑÎÞVTS›•˜ÝS›‘‘›Í›ÐÙ•”MÛXÍÎT™ÛLÕ\
ÒR‘Ý]ZRž[^]˜U•RNÓÑRÕ^™ÞŽN”ÊÖYÕÜVUMR“Ñ”ŽS•Þ’LœÕ\ÛL›^V^“Ð™Ñ˜ZSLœKÑ][ZZÜŒ”Xž]R”›KÛÔÙÑZLMÍØÌ™™[ÔÕ›
ÓT™˜ÑTLŒÝUÒÌXÕœTUXŠÜÚZ\PŽTUœ™žZLT•LÛT›”ÍLÚL\ÒZ[MLLYS“Œ˜ZPž]›ÐÚÚ™“V^ZZ’Ù’Ø˜ÜVQØRÖÕUÜŒQL‘Ú›ZÞÖ]‹Ì‘ÌPÓYÒ›ÓÜ’ŒŠÍš\Õ[›R“˜]ÚÜÒÛŒÙÑÚ••‘ÌÊÖ‘“œZšÔÑ˜ÓRÓ˜\ÖTœÞÚ\ØTV‘–Ž›œTYQZMTÓSTÚÍ”[S’]]ÚMRVšSZœš“XXÝ‘Ò‘M˜œ\ÐÙ”Ú[šÐL›ZXÒÝžÝUÍŒ‘›ÖL“R“ÖXÜž[Q’ÚÎL”ZÛ”ÕÖ\UÍÕQÖœ\’YÔ“Ý–Q”Ø‘\Ì]XXXÔÚÙÚÎ“›ÛžQ™Ö“LSM‘ÑTÛLÛ‘JÝPÕ›Y˜‘Ø”\’ÓZËØÖXÝ[ÖÚš•Ü™™Ñ–YØ[VLÛ[LTÒÕÌTTRRÊÜ›ÕNÕYŒ”R’ZTÑÖ^‘“UÞ‘žTÞYÜSÒšUŠÖ”ÒTÕ[›\’ÚØÕP“™Õ”N
Û›‘Õ™PÎ–žZ\’QV›ŒXLÜÙÙÞ\ÍTÓÐ[Û\UZÚ’ÎÊÖRJÌRš^•šQ”RLÐÛÕÛÝURÙ[‘šPÌYÒÌÕXÎLPÚžQKÌLYTÔLÙÊÌÑ–“ÔÙ“]“ÒÜSÛMÛÙÓ“ÐXÜ•Ó™œYØ›YTœÖÜY–XËÎ\ZšXžšØÒ™ÝRÒÒÛÚÙRÒÑ–™UÝšÑ‘›ÞÚœP‘“P•Í˜]ÓÓMÛÒšLÍPÔSU]\XVSÞ›Ù[”ÔÐÙ˜ÝÛšTÍ’TÛZ™TÔ˜ÜÛYÕÚÙPËÕ’”ÚVRž”•ËÛÕM’šÖ[“ÛU\VÌ˜M\ÚRSLš[™ÜÜUØS“\Ö˜Z™ÕVŠÔ“ÙYÚ[Õ\ÓTž–˜\Y“‘ÓÛÞZ
Õ’ZÔŠÛSš™ÔŽRÔ]\ÔÐšÔÞUÖÓœ–[P’›œX[ÙT’”›]RVœTÔÙÙÚÑÞ˜››Ù˜NR‘‘UšÝ›Ø^UTXÜ›^“[ZÚÕÚ^“ÙÙÜY”ÐŽ[TÐ”Ó‘•]Y‘YÜTÔ˜UÙXTŒ”S˜LÖY•Œ–QšL–]›ÓÕMXÙQÛš•ÌÞ˜[YLÌ–’Õ›UÝZ\SYX\Z[”^›RP[™N[“YÚŠÚ˜‘SQ]VPÜÞ‘Ûž›SSV™RX\Y’ÝÝÚÞR^S˜QÞZLÒZÒSURÓ™]TÕÒTUŽ\‘ÖZ˜\P[U››–‘œÎÙ“ŠÑÒPZŠÑÌ\•ÞÜSRØÒVÑŠÞVŒ\›VœY–™’V•Úœ[›^Q’RØšNTÒÓÔ‘ÛZ‘P‘›ÜU’‹Õ[TÝšÐšÛ•MT’Þ^SÌÕÖŽQÑ“UR“š]›Ô]ÛQÙ\™’Ð”’U˜Œ™ÛÔRTÖÞ–•šÚŒÕ[ÖÝTšÚÕS™Ü‘’ÌMÔ^\ÚÔP“ÝŒY˜œ˜’›ŒŒš›L˜YÑT’ZÙSÕLZR–ŽXÔ[‘•T‘RÔ•›\
Õ–“’œÐÊÌ›Ì\\”›Xž‘›YÌÒŒžÐÌSU[JÞš
Ü’ÑÞXTÜÕ”Ð^Ú^UÜšKÓÒ˜Œ[^VŒ–•YRYÚÕZÞYUÜQ]ÖSŒU”žUMÐÐQRÍU–UÚÓ]ŒT–[NÐ’]Ì“YZÜÕU˜™’U\V™
Ú‘QLZMY‘’’Y˜PPQÕŒœX–ž”ÕPÖU’’›USÍØQÛÛ“][QYÍÑTÝ–ZÓ’ÛZ^QUÑ^“žTÚXNZZÜZ•SÑYœVRÞZœ]Ú™ÎZVšN–ŒÕÕ^Î‘›ÛXŒZ[ÍUÒ\•Ü\Û˜“N\ÖVQÜM’XNÜ“]NMVUÝ›ššÒš™VÕœYÙÕTÒÛZQQSÐØÛ’UšP˜]ÚŽPÛÚYÌ”ž^ZÞ™ÚQžS\TÛÚÕ™Ú\˜TŒQÑ[Þ˜ÖœÜS‘›S^‘ÙÑ›\ÓX’UœÑS–Y›ÒQ[TšZŒÙÚY[‘Í˜”ØP’LŒž^[œRÞQRTÜLZUPÎÛ›žM˜“LÜÕÖVQZZQ•ÍÛ™RŒÜUXŒÎZœÝ“ÒÔÝ•Ðœ•Ú]\S•YÖ’R‘ÒNSQ[NZV‘’ËÝNš–[ŠÞQRÓÜØPÖÚ•ž]YUÞYÙ\–˜ÒU›Y]ÑMUÚÛŽS”VXL‘\S\[YÑÐÜ
Õ•SÓQPŠÓ\Ù””š‘‘MÖTÐ”ÝÞ˜YPN^‘ÌžÓËÕœŒ”QÛÝ™’ÙÔ–Q”S–ŽÑÑŽÛ]ÒÝÒYÜ[RPÌÜPÜZŒ‘Ñœ˜JÖ›Û^S™Ñ•™YTÔ”RÌTÙÒRZQZ“ÝÜ^RÌ’UÕÛŠÔÐ‘‘ÑVSÝ‘•Q›MLYLš•šU]›ÓžYRZQÜÍš–Œ™ÕZ›N\”]Û[UYNTÐ”ÑÕPÞ\›Z™ÔJÝÒØÌÚÕÚÝP”ØR˜žÝ›“Ð™Ö”Þ]˜V\ÛÒM›ÙÓ˜PÜÝ”ÕÑ\•œÛTÑRSV›Ù“S“ÓÐšÐÔÑÜ‹ÑT’›ÕÔØÒ™ÝžÙÍSV™^LÚšžÑ[‘^ŒTÔ^]Œ”Ó[‘]ÕÑMLÞœ”’[ÒØÒÞž‘UÜ‘TŒ–Ø–‘ÝÛŽÍR[“RœZLNÐ^‘[UYÛXÚ’‘SÌÙÒQ\–•ÛÝ™ËÓTÍP‘SÌ”P[ÝÚ•ØšÓÜYÕÕØ’SÜÍQÕZÑQZ›ZKÞÞž›T[TUÍ›N”ZZÛ–^RRÝZLTR’T\˜žÜXÕØSÚÛŠÑXÌM\Ü˜ÐUÔS™ÍÙRRœÑRÍÙ“\ÚÒXÙÒ”ÒÚ“œ”’ZÝ^MÚËÖŒZQ‘ÚLÕÕ”•ÙTZ‘ÜV^V[TUÙPÑ•Ò\˜šÛÛ“ØÕ’RšU[ÌœÕÞ]P™ÐÌÛØ•YQ]JÕ“RÌÕ[UšU[YZP]YÔ\ULUÜš]ÝÔLV]]ÖZÕY\Z‘ÜÐYÝTœÍZV˜ÑS“ØMÒ“MQÙRÙÝL‹Ò˜œÚ
Ò–•ÛÒLÚTÓÓÛÔÕŒPÛXR‘ÌRÞ“šÕ‹ÊÔŒÜÐYÌ\[ÍÙŒÑKÝTÚX˜ÛY”^ØÛV˜TÖVRÌžZR\MŒœR›œUšÚUÒ™•[”U“Ý›žT›L\ÞÙVØ–ÝVÖQšÛÙÝÖÝŒÙÓ˜YÔÊÚœÞš“YÚšÒš[Ô›Ü[œSJÑM]ÚTœœÚL‘Z›Ý–œÛR™UÚQ•˜˜Ž––œÜÓLÞYLÝÜLUMUÑ’™LM]ÌÒZÕÖQ–TÎYÊÖLJÞMVRUÜ“XÜÙžœVÙ˜’ÚÕÕ^PY”SÙ]’ŠÎœKÑÒ”ÒÕÛÑ–›ÓXÚ[ÙÕ^‘ULÔMÔP‘]YžKÜPÜ[‘’’ÍJÓZ’MÑ‘•‹ØUMŠÔUÜÍ“™[ÊÛÜZZœÐMQÜž”Ì˜ÛZ™ÔÐÐZÊÓÔL“œÞR•RYÑT[Yš›[Í›•]ŒÔLÑ“ÕJÕRXÚ\^
Í›VP]›‘Í”‘[ÛššÊÝÜMÒUÝ”ÍÍT[š•Q^•U˜ÛØ˜ÙÖ[ÑLLŒÞXV™ÜUSÙ–L™ÌŒÒÔ”’ØLX’^’ŒZÔT‘Ü•Ø‘Ð™ÞQœ›RS\’›][•ÑZKÎXT“ÑÍÕU“ÌÛÌÕYÚ[ØÓÚ”LÛT™˜Ü\ÚÑ˜YÓL™LÕ‘[œÞR•šÖ›ÚÐÖ
ÙÔ›UÔ›ÚÛÝRÕ“œZXZÚ–ZZÑŒSÖ™ÒØXTÙ–TÌ”ÎS’žV\ÛšRZŽSžÛ•ÞY‘ÌŠÑ™VZRšLZÕ›Í]Z˜LÕ‘[U\’–Ó“L[Í’ÓÓTž‘Û™š”ŒUŒØÕœÚY˜ÝÜRž]TŽ[ÍŒ–ÝZÕQ’QÕS”’ÝÌ[Y[•T•’UœT’“šRUÕ\[’›JÔMšPÔÔ””ÝLÒLTTÓL“SÍRšÒZ[ÚÛÝQÙÕP\ØTJÛ•RÚÍZ•Üš•ÔœT’LTÞ•RØZT”žXŒÔ[™U[’™ÔŒKÞÝ™œŽ]ÙÕÒQ]ž^UMXÒSLØÑœÖ›‹ÞLÌT“]›š]V‘‘Î[ÝÚ“œŽ]ÑÝØÜPÒVÐXŒRÕ”•TRS[TÝVÞ’Û›Ð”•RÜLZÑ\TÙTÖ’ÑJÕ]ÔL›ÐÌÛ]ZÝ•V›’XZ‘\œØRMœM›\“ÚT‘•ÚTÓØYšÒX^ZPQ›[Ð’œÛ”KÔ‹Ì”œUÚSUÐ–[M\“ÖŽULV]SØÒPSÚ\PSQ”ÚŠÐÞÎXZQZÌÛ–›Ü]PÝÎÕ[ÛV˜˜S˜R™YQZ•Lœ›ŒÍT“Ò–QVÒSXÔ‘Yž^‘•™Q•LL\XÖJÕYÍœNSÝšÓZ“ÞQØ”KÓ”Ú•Ö’›QÙPÕ•SUÕÒ•ÙŒ[ÌÙ•Ð’–‘XÞVŠÞžUÛ‘UÝÛÑÛ‘˜”Ò™Q”U]QÒP‘ž’‘LÜÛYÝY‹ÛÐ˜žšYÔËÒÔÖT]‘SÔRQRÒ˜ÜœÞÍÝÐ““Ü\Œ“‘R“]˜ÚYÖ˜Œ‹ÛS’Y]’“RÙ”“ÞÔœ˜Ì™]ŽTVšÕ’TÖš]Œ›žL\‘L™YÞV^“KÖX‘œXšÜ˜ÓSÕLLš”ÝT[LZLÓ[Ö’LÓ›–šMšÝ[Ý”‘Ûœ˜ÒU™–SY•œÜÔ˜UÜ›ÝÌØSÕRRNŽUT\VYL‘LKÐÚ]ÔUš”šÖÖš”Y‘œU–ÊÛY˜ÞM[ÓÒN\šMU““Ù•SÍNQM•U‘ÌŒÓ’U™]Ó]MÜQMŽšKÛ–[XÍSÞŒØÕ‘\Ü“ŒZ”PÚÕØÍ“Ü’•ÝRÞYNZT]ž˜Ð]ÒRŽKÝ“ÚÎÊÞX–ŒÑU˜TØÜRŠÔZÍXMÝÑØ•Ð›TU”TRÙ\N\žÜZÙÌZVÌ”ÑR]šÔ•ÑZŒÔŠÑ‘PL\›ÔœMV–S˜‘ÐU‘T•›YÜÝ“–’ÖUJÔ\L™UZÕØÞ–ÜŒX“ÛQÔÑY”˜ØžQÔœÓÌVŠÓUÒ^ØUœ”Ò[‘ŒÚ›[“Ì“ÒÑÒÛ”ŒÐÌ•U›Û”M•NMÌYœÙÑÑ˜ÕÞ–œÑÛÚZÛÛÚœÕÛ–”ÜÝÓž•LœS”Ô[UÕ]ÜÓ–[QTZ››^œTÞ“Ò”ÜU•Û[ÙR\Ö’UYVZÍ›ŽÍÐ]Úš\‘Ð’œPÕ‘MÓYœVUÌ›LÌÛ™’PXQKÑžÒ–ŒÑ^[•T•ZYÒÝÌSž\N\•ÒšSÐQÝÞ›Øœ’\ÒÌÒQÞšZ‘žŒSŽQ›T™ÌSTSÔÙÑÝËÓ‘šZXÑ^”ŽšÛËÛY•ÓÖ[QÍ[[•\ÐQPÓT]‘]›\Œ^UÕ’Y[Ü˜ŒÒÔ‘ÛX–™›SØQÞž’“ÚÒšÕÔÒÞÜPPž[]Ò[ZÎÛÍÒ]•LSVTÓÜÐÛTÞ^–’™U˜S’ÜÛÍÛ–PQPÌŒ“™SUÚžš›šŽ]ÌQÕSØ•RÝÕ\ÎQÝÚœÐURŒ’ÞÚÑ–V”ÚšÝLÐÙÌœÔÑ”ÙÛ’Þ˜šÝY[›ÞTU•ÛZU‘SÐÙÚSÎQ–YœQ^]Õœ•šÙVTTÞ’ZÞÍ˜Ú’–[Ð–œT]š™“SÙ^‘Ø‘Ù‘•ZÔÕ[Y•R][XÔÜÍXZÒ’ÔÚ–’UÚ’SZÙQR”’™PÖVMUÙ^YXLU]”XšNÚÞ‘ÙÌSŽS˜’Û‘˜TP^TÊÌœNR™SR]ÓMSÔÒÔQÒŒXXÕ›ÎÕTXVÛÜ]V”ŽQS–ŒR‘XÐž•VŒY›^YTN’R\”‘MÝ[ÝÚÒKÜÓÍ\–žXžSPNV•]šPÍÕÞYž]Z”ÛÜ˜ÔÌØ•ÓLÒ•[RU“M”[“\ÛÍœÜ‘Œ’–\ÒÚTRU”Ú”šL•ÓL]’˜T’Ñ“ËÕ•ÍÓYÛ‘ÙY•šžÑU•^Œ”œ\ŒYÍÔ‘X“UX“Z“ÑØMYÍŠÑÍ™ÓÞSÙ[Ó‘Ò˜ÎÌ““œ[^‘ÐP[ÓÐÝÒÔQžÕY’ÙÝQT˜ÓÝ”RZ™ÜNYÐÚQ–“[ZÖNM›NUÔ”VY›’UÌ˜V–Uœ‘Z^LÚž“^V’ØLÝœ›TÍ›ZŒ˜LÒ‘VÑÚ’ŒÔ‘Þ•T[ÙQÙŒVžQÙÒž]žŒ’YT•‹ÙXšÑ™]Z›Ñ[ZÜ•Ö[”ÒÞ”MÓ•ZÜQTÜŒ[^•T[š’šP›\YX™YÚLÔRZÚÝÙžŽUššÍÜ˜MÌLR•Õ]ÔÛÛ^QÒœ[QØXÌÜTÞÕUÒRQ“ÚœÚ’“UÕ›–ÙLÎÖ^^TÍ[•ËÝšÌSŒÞœ˜ÝZ•Ì˜˜SœÕÒŽQÚ“M”MŒÔÓKÝŽ‘œÌ‘ÛPRMÙ“[Ž[ÚŠÚÞž[
ÍVY˜PÝÕÕÛ“œ”’VÓÕQ™\“šZÝQ‹ÜTŽMÚPU”U™Ü™˜\œPÑÍš]šSMÌ”SN[ÞM”Ý“••LPšÔÍÓÙZž\SžÓZTœ–ÜÒQÕ’ÞXSV›ÙMÍÞÑ˜U–Ô•‹ÜZYXSÌ\VU•YM^š”™XTŒ›LÍÛÞURRPž’N]‘ÒT“ÚUSÓÍSÍ^‘ÍLUŽLJÓÐÜÚÛ”’\ÙZÔÍÊÑÍžÍÌŽZÔÚSÔœÞœÖ˜\ÔœRUœ–‘P]^ÞÒÞœÌSžYÒ\“Ü[ÒÓÖQÒ’Q\˜[‘U˜Ö]VžÌ’‘PŠÜ’ÌÑ^ž[[^Ô^X[ÑSÓQQ˜YQšÝY›˜ÕØÜÙœ•™Ó’˜•^UÍØMM˜[šMUŽUYœRŒQ™YÞ“Xœ]ÚšÛNYQ›
Í^XRN[M˜Øž™P’SÑML™TÙÚL\•šV\ÑRT’ZLÙPÍÓP[Ö\˜‘SJÔÙQXVUSY›X”›Ðœ˜QÛT“ÑÕØ’ÞšLQÍÒ’‹ÓTŒZQ”ZÝ\ÙÛXTÝ‘–ZšSL•S”]”ÌZÌ”QÝ›PYžTPÖ[•”ÛMšR‘PžYžTSXXMÝUÜ]ÙÐÚÑ“YÊÝTSLÜ˜ÛŒ•YÒRQØÌÖMTÍÎ^Œ[Ù]UÔYZÜ•ZRÍšVT’TšÑÙÜÑÓ•ZÌYÒš‘ZQÒšRVTÑÕ]ÒTÕŒÒÕTÜÚ\XVZÚŠÍÑÕ^žŒÝ“MQÔ”‘›’ÝÜŒ•ÑšÙ“ÐÛ”Ì^]’ÚÖY“\šX\ZÐ’ÐØÒœØX•MPÕ™TRÕŒ›Z–T•”–›’]ÚÕPÚÌÒ[ÚX›QZÖ[œ^TÕPËÐÔUŒQ‘‘ÓÙ^žRXS•‘Ì›^P\‘Ô]Ô[Tž]YZžKÔMXÜØ’MÓ˜L\‘šQÎ”UÜ–LØZŠÓMS‘ÔLÕÜØÐÌ\•SÜTLT\Ú‘Y–˜[”]Q
Ñ•LÑÔUÚQÑLVX‘Õ•Ü“ÛÜÓLNTÔÔÔÑL”YÔ“Y[ÕXXZ\ÐP•Œ›\V’S™’ÑŽTœ™‘ÑÔÌŒœÙÕ[Î“ÑQ™RZ’Ü•JÙšÒšZ––’ØXÝÐÌœ\’ÛUÙV]NVšS’P™‘SÐZœ”’M]›RÐÐX•ÛYÖ˜ÒÞ‘’ÒØXZ]ZÑš[™T[’ÑQŽÖPÛZURJØÙ‹ÝÜÔÍÔTÌ[•‘LUP“ØPÒÙVYšÚ\SVU’V[œ”^VL\Í”’’žPÔ˜MÑRž\VŒ‘ÒÓ^
ÕÔœRÎQÒÓ”Ò]œQÜÐÐÚTÔQ[ÚÓÒUŒ›Ø›”˜XÌÚTV˜Õ\ÝÌÚ“ÎZ™’LšÓ™TÑÒšÔÔ[œØZUMÔ”‘UÍXŒšTMÓÌLŽSÕ”ŽVQ”ÛJÜ›”Ó™ÚYÛŒÜÕ“T’ÕÎLËÒ[L’ØVTŒÒ‘’Í•Ì^L˜SšÒY’••Œ’^UÑXÛ–QTÕÛÖ™’“ž•YÞ”QLÓUÛSYÔÝZQZXT]ÎNVÞY“Ò˜ÜÑÐÎÒš–^Y][[šXÓ“™UÔYUV‘ÚSÝÌÚMžL•šÐŽRUš”–œÛRT“œMV“SYššR”ž”ÛYNÖ^XYÓÒ˜ÓÓÕ‘Þ\ŒPŒÒŠÔÍV˜‘žMžSŒÛ“‘\”SVYšÜÌÜŠÓÐZQLÑ]LXÖ–ÛÌÛÕSPžLX›S’ÜUÕYÝÛØÓ˜‘\ÍÔÒ˜™VLÍÐZTÓ™RÒŠÙ’”ÒÙœÌÓž’[ÚYØ“ZØRÝ[ZÌ™M”SÓÙŒÍ“ÜŠÚ––”‘™\ÙRÙ’’Ó˜’šÕ‘ÚSS”ÒŒY\U]œN’XÕÑTUŒLÖžSLÚ]ÕTPRœSÒ“šU˜Ž‘Ú“TÓL˜Z›RVTT–‘ÔX˜[–”šYÜÖœS[Ú‘TÍÜYVZQÑ’]V‘UšQ’Ô’^ÞÛXZ‘U›ÛÌÕÌÕ]ššÒS‹Þ›QÒUMSÎSœÜÙÛSÒŒ‘šPÚÖžQÑÌMMÜÙØŠÜÐ[–N\ž•]ÖÔœ”œÒš‘ÑÚšš]ÛÙÒQVÕÞœV™ÌUŒM]UP™]PØÜÒ]Ú“Z‘^ÝRœNQ™Ô^RÌ‘ÑœœÙ”T[
ÚÔ‘ÙœØÞMÕ”\Ô™•’ZÛÜSÕ›ÓÙÛZXÝØZÐTXÜSØUžLY]\R™LÓTXÞÔSŽÔ”ÌVY]
ÙX˜ÓÌ”Ú”ÛÑØR’ÕL™ÍšÒL‹Ö\Žœ˜RÖ‘‘›ÎÔÐÎÕÛœ‘ÎV›ÓM’Ð’QLœ˜ÚÍÍ›š–ŒÌ•^SØœÕZÓšY\›ÚMÕÜœ–œ“ÚSšÝ\ÕQž–\šÓÔM\ŒœZP‘UUU^LÔ’V[\–ÝRÑ^œMRÛÌÔ“Z›ÛœÍÝÛ“Ý]–^ÔUXJÜ›’•˜ÚÕ’–Vœ˜X”\–ÒÕ^KÙÍY“U[Ì]ÕÑYMÚLÐ–•Q˜Ñ˜”Ú›ÚšÞ[RÝUU“UÛÍ”ÐSžRM\ÒÝ’ž^“[’˜PÞ“š•U]M‘‘XRšQÍÕÌš’ÔŒZŠÝ”“ÕÜÕÖšÍU]“ÓÛÎX]’VY]ÐÔJÕž›]™Z”žÑM^ŒÐ^PYPÌ’žœ[ÔRZ‘šÖX’
ÝÚJÊÔÌÔÍÚ˜™ÒÒŒ^ÚQ™ZŽ\[ŒœÒ]ÐÑ’NSÖX™ØJÝšXÌSØXÐØÙZYÚ“ÒÍ™ÓL™U’“[ÝTÞ›ÛÚ\Q]ŽUKÛ’ŽLUÔR’Ì•\RœRŒTÚÕ™YËÚUÒ•ØœŒž•ÔL’–\ÌÜ^œÔÓ[ÓŽÑYQšÛ[[ÛZQÜœZÙPKÜ–’œšÐžš“\ÚV˜‘ÑMZ[‘ÝÔÑÓ\UU”Ü^TÑXÞYÍNRŽY’YÝM”ÕYÚS\ÙÜR”ÑÊÒSM‘”ÌS“ÛŒžÑ˜RÕœLSÕ\TŒ–œÕY’NVY•ÝÛPXœÛ“Ò‘ÛØLÕŒ”Õ™ÍØÒ]œ’ÚYÖ“œÔ‘\ÙÙÕÙ•Xš‘ÛVYÝ^]Þ’œÍS‹Ü’ÛœXQRRÊÝÎY‘]ÓŒžÙŒ\Ì•ÙÝÕZ–ZTYÒÖ^NÑÒR”ÒYUšÞ]Ò“ÜÐ\ŒPU^ÌÕ–Y\X”ÓØSÓÓšTÓÔULÌœQ]Ü–Y^MÍL’ÖXÕVÜÔXÚ–šMXÛVZ‹Ò•ÞV“ZØZÝÝUMŠÕ[›ÑÊÍRSÕÒžRÝ“™Û”ÓØQÛ^™’ÕVR•›L›ÝÝÐ”ŽVU“žÚÑÖX\œ^ZÒØUšÌR[V‘‘Z˜’Ö“TPUT’ŠÐš‘NÍ]ÕNXÙÔ’Z“ÑTÚ“TXÒQžZ›ÎRÚÌ‘TZPÖÌÝLÕÓšP”ŒMÕÔ”‘[ÒÞYRÌ”ÞÑVÌYÛšYœ‘’ZTšT˜Ú˜“ÒÓ[S]Z•ÔYÔL˜Ì“•ÜÕ^œ”P˜•V^™XÎY\Òœ’JÎŒ\\’XÜÐŒSÚVUU˜PÕ]Í’ÚÙÜ\YŒžYNRÌÒ^›TÓ˜LšÞŽJÑ‘ØÔ’VœR•ÓšÜS[šÐ›ÌÓYÛ•ÝÓÎM™M’•ÒÝ’ÙQÍKÛSÔÓ–ÒÕ”RTÒŽZYšÑM•TÌ^]š›LÜœÍÚSL\\›\TÕšTY\‘ÐÞVV“TYÛÙÞ\Q™Î\Ó]š’ÓœÑ“]”“^XÌÔZ”ŒÕÚÚÚYZÑ‘”‘›XS‘SN]Ú‹ÓÐXÑYšÑÕÓÔŒRXLYLÔœLŽ\œÍÞ\Þ\š\›QÔ–RS’’ÚÔÔØ‘ØÚÜÖ–UPU›Ó‘Sž”Ò]]›UÌRØÍR‘ÒÚÛÑ–‘’›ÎQ“ZÚÌM–[Ò]ÌÚSQU•S\\ÔÒØ•ÑPØÝ“[U]PÑ™Ý[YKÛRÌJÞ‹ÚTÙÌÞMXZÑÓÔ–”ÝZSžžZTÖZPTÜÛÝRXÔÔÑÙRŒÕRÔØ””QÚ“YMŒØPU^PÞYØÚ^”\QU\’‘”Ó^ÑÒQLÙ™]XSÖŠØ]Z\”ÌNÓP]œËÑŒ”ÐRššP™\^–V™QÕRT™ÌM–[ÜÓÖŠÙ“Ô\Ü‘ZÍPXL”Mœ\ÐÒYUÒ™“”’MVÕÑPžRÓšSÙ•YÒÓ\]VX\QSUÞU˜^šT•›Ñ˜Õ“\ÐÑ™YÍ“’Q[Û‘X’Zœ’’Ö]\Õ[’Î™ØS]•Û›ÚÖÚLžŒRXØÜTÓ™ÒÔØÜ[•[ÙUUÌŠÚZ“R‘[YT˜˜’ÝÑÍÚJÖ“MQVMÜLÔ[UÑÍŒÕ”ÚXŒ•Ì[ÓÚ‘ÚÛ–XTÔ^’šÑQJÑÔØVY›Ú[R‘•L–PÙL”VRÓšZ›[^[ÒÒ\V^RÛšŽÍÛV›ÎÕÎLÓZ•[ÝUM’•\RL\ŒVYÐ˜YPV˜Õ˜Qš•ÔÌ™Ù[”ŽÍžŒ\Ö‹ÛÎÓÒ•ZÞ”ÌŽÒ–L›LÕSQM[ÕÛœ˜ÕÍÙÝÊÝYX[UVÚÕžÚ\RÕTÙ‘ÌšU‘ÜUÌ\UÔÜZŒ”’“PÖ™PÛRÚÝZÕÔÕ•ÒNL”ÕÔRØVÓMVÍÓ‘”MŒ–UÔ˜ÊÖŽ]–TZŽ]ÜYS’MYÒÐL”Z•ÊÌ]ÙÚÚšÌ˜RØYXNÚÛ[šŽ[ÔÛÓžPÑ˜ÑZ“‘\ÚÔÙ”Ò˜TÖŒXÐÐZŽLÓÑZVžLM˜[œÛÚ]ÍPÑ[YÍÕÌ–]Ò˜[MVZÜP[ÊÌ–\U•Öž”ØSÒ›Þ–YTRÜ•ÐZÓP\‘ÕXŒÐÖZMSÖ]TÑ\MR‹ÓÓ–ž\‘‘ÜY’QÖ•SRYŒØM\LLUÚ™Ú\˜M]ÝS“U™SÑ]R“RZUPUX”Ò–™QÐSœ›’œ”MÜ‘ÑÛ“^\PT’Ú“JÛ–ÎVZÑ[˜ÑÖ]ŒZRÒš^ŽR™UM–ÕUÛUYÖÞ]QR‹ÔÞSLšÚQMTÔŒŒœ‘•Õ[ZÖ“ÔÝ\›RÜÚÑNÜŒTÕ\UÔ\Í’ÛÚUÒYZÚMLÚV•ŽLZÎLŠÝÜZÕVÎÙRLÛUš[ÝÓÝÔQžÓPLšMœ•Ý’ÕNZ™SYÌ•Þ˜Ý[LU‘ÚVÚÜÑÚQÝPÑÞ“œÚœÚÙUšÙš^›“ÝT›ÐÓZÕÞ˜LZ•RZÔ[ÓUP–˜’ÕÓÜZT^UZ[JÐÚM‘œZÕXžRQÞ“ÐÝ”[MŒLLœR‘Ñ•””‘ÎVRÖRŒ]ØU]ÚSÕÝM˜YÑXÙX™œZœÕÕTÜžT[•VY[ÝÖØØÒÐKÝXœÕ‘ž‘PÑÓÒžÌšSSÍSÝœNKÝX”Q“LZ•™ÔžQÖQ–Ñ›‘œLRNZÛÔ“Y“Ü”˜RÒÝU•œ]ZSÒZÛžX–œ’ÕØ\V’TÚMRÚÝSXÚÑÒ\MYÝžYÑÒ‘’ÎZLT“ÙÜÒ–LRÊÜÑÌ”Ö’‘YÛT“‹ÚÐLRTÛ[“LÞ\ÌM‘ØÌŒÞ‘NLÜÞ]”œLTÌÒMŒÒ–P[RÜÌŽL•QÖ^SPTRÍŽZÚ“^“’ÕL’ÞT[›“YÒžž^QLQ•ÑLž[•š‘ZVZT^šZÞSž‘ÒR[LQÙV
Ñ››ÝJÜZÕÒZYTPLV“U’TQTUŽUY••T””\ÓŽXT“ÍÝZØÝTÜÚZRÍVP‘ÑØMZž›’]UUÔ‘\žœÒ•TQÒ˜NT–L”ÜœÖSÛŒÛÌÛ˜›ÚÛL”ÝPÕ››™R›’ÚT›‘Y”UTÌÑÔÕYÐ˜S[ØÍÕÍÚÜÛÓS‘L’›žQÓÜ›R]šÑL^ŽQQžQYØ••UÐÓ\]ZÞLŒXJÝLÙR]\R[^’Q“•]ŒÚŽL˜–Ú‘L–L’ÝVRŒÚTÓTÐ–•šÒŽ”ÝZÒS›ÜL[LÑ™•ŽS’^RÕ]œUS]Þ˜Þ“XS”\ÙÜ›––š˜T™žÒÌ[UUÖ•T“ÝŒXœXUUZS\‘“RÞ•UP˜[ÛQ•“’Ú›ÌV]‘ÒQ]šÝ”[Ì™ÎQÍ’•ÌTÑL]ÎÖV[š^
ÛÝR›ÖTÜUš\Ì\Ñ”Ž[ÛU’˜ŒT“•”ŒœYZRÒÍ\UÊÜ›RÚÕUÜšÚÔØ•Ú]PT”ÊÔV•YÕJÙÔ’ÛÜÍ\
ÒÑ‘”Ùœ‹Ù™Ù‘Ž‘ÕŒ‘^LÍ
ÑZQš‹Û[^–^RM‘ÍÔ“œÜRÜ™[YŠÛU”ÙYÑÞ\Ð‘T”Ò\ÌL”ÖšNZ“Õ›ÔZÚ^ÜYMRÜYMÑTŽUœÒÔ˜”œ”•Z^UŽ]S\ÒSÚLQQU˜ÚMÛ›ÚÖ’VX˜S›\R›ÞZJÓÙÛÍÍœÜVUœÚX˜›V^œ“MÚÐŒPÑÛ•™œ\Ž]ÒMÓÌV[ÎMQÌ”\’ÚÒ™Y]VŒ‘QÐTÚRÝÚR‹ÞNÑŒS^RRYZÕUQÛØÎžRJÞSVZ^
ÍUžRÕœ^š’VšNÚÞ’SÛÕPUÚÓÛVž”Ü›XNYÌÒ˜LRTÞ’Ý[ŒV‘ŒÛŒR•P“šVUÔS“œV•UQœ”Þ^M”™Ñœ•Ó’ÒQÓ”PÚXÕ^ÌžQZÕÜP\QZÍT\UÍQMÝœ^›XÜUR\ÚZYØRÝ‘œ’œ
ÜØÚÛ]Ü•ÚÐÞVLZSÚ“Œ”MÛ’™ÍÛÎMØQžÒÚ’”Þ›ÚžV›[–Y]XÚÎM“šXÓœÞ^šP”ÖY‘UUŽR”X]V•Ù^YÔÙZ]ÑMU[SX’ØÔLÖ›]’ÑŒÝÓ–Œ––™Ü[[LÔL˜–ÛÐÔÝ]Ð’Í˜QØœU”ÛÜ[Zœ[“ÚŒMTÎÓ›ØšÔÊÕÜÜ–ŒLS“ŒÍ[ÍKÜS™RQÐUÑÓÑ’MÕ˜ÚPTP”M^P™MP‘ššTUÌTœVNSÒÑÜRÕ•ÓQSÛÙÌÒ“TŒÝÝšYR™S‘ÜSÒLšX^•ž˜ÚSÊÌQÜÔU’‘“Ý\”]ÒÐ–[[’œÛ›ÖŒPÒMØ™ÞM]U]^Ö’ÚZ‘LÕU™šØ›ØÓ›\ÌÞŒ’Ñ\‘ÒÒLÕœ˜’[ÕYÓÍ]ÎQ˜ÌU”ÙÒZR•˜N^\ÕQšÑœUÔÚTQÌÔÜœ›‘Ý
ÔÓÝÔšQŒUXÚL“QÕXžTÕÑÑÚšÓÑRÞ\”™‹Õ\Û›“UÎœŒ‘Ð›ÐYQQÜÛ‘”S›^YV–TNT•[ÓÑUT”ÐLÐÕØÝV”–ÝÐÐV[XÑÛÚ^œ›œ“ÛÖšÚÒN[™ÛR™™R•RZSÔ’’šÕÙST™•[LVMÕÍY[š‹ËÐÝUZU‘SLQÙÙÛZÚÎŒœ“Q[Ü’Z‘ŽLVÝMÌ[ZP•]•œ“˜ÎU[[V“ÑTZØ›Q\’SœÚÌŒÜSP]ŠÌJÞÞ‘Ú^\’]ÌR•ÔÖ’˜ÛU–[MÑŽÚ‘XÝUšSÔÞœ–
ÊÒÓ”]URXŒ^ØZ]ÌÜUÕÑÝP™ÜÜ˜ÔVYZ’ZÞÛÒÚšÌÙ’YÍ›RÝ‹Ú“ÞMÛÝTVÜÞ‘]ÐVYÓÚ[[ÚÓŽ\S“ZÕX[ÕÚTZÍ[\L[LPÚR’–\ÛV\ÕRÒULV‹ÌYÛ–“”˜]ÒXÞLÊÜÚÖœ
ÒPUZ‘ÚSÒ]NÍQÔÙžÍšÞNÙÛYÑ\ÍÍZÚÖŒÑRÑZÚš‘Ð™SÞ’ÖRÕÊÍÒU^\TŒRÔXÛœLPQVPÞX”TÝÜ‘ÜR’šÖšœZSÕYJÕUÓ^“^[•[ÙÚÜ•U“ÙÕ][TÎ›Q[ÒÜÛÒÌL^RÞ\\Ü^ÎN”Í]™’\[SPœX”LÛN[Ó•šÌÒÕÛX›šÖÚÚXœR‘RÕÞ‘RÕÚÖ’Ž^TŠÛÚÙ[TLÖ]Y’ÖŒ‘QÝÑÊÔSLXPšÑ”M]’’MÑR”ŠÚÍœœÍÙÐLKÚÍŒ[Õ‘[ÎÒL›ÕšJÌžœ’œÔ•LXšÎ‘ÝÖ[ÌÔÜÑ\–XžUØ“SÌÚÕ‘RØÝŒ”ÙQQ‘ÚTÜ[U‘˜ÖQNQ›Z›TZÒT‘Ú˜ÎTÌØŒœ‘\PZ[Q“ÌSÌ”ŠÝRÛÕ”“ŒM’›ÍTSY[M‘]Ú•\Õ\˜•QKÛZU•ÑUP˜‘“XU‘”ZY™\’”Ø\\KÙÑÎNS‘ÓU“RÕœUØŒ[T‘ÑXTSMRN[‹ÚÝ]”ÑZØŒÑ•ÚVÛœP[ÕXš’˜\Ô›ÐÜ“\’ÓÛPÑÛ–“QÞTX^šÒÊÞ[ÞTÞ”ÕXžÛÛÑÚÙZÐ’ÑÍÐ]UÌZÚ•›Û‘”ÓœÍPž›ÛžTQ’ÞœšMÙ”ÕÚÓÎÑVšL’[”™‘ÛUÚÒULÛ
ÌRš\RLšZÝ›[Ö•‘PÌPÛ‘‘^œÕY•]“Y’ÔÞ”ÚMÓÌV”š^RÐUÓTYÓQ]Ùš›YÙÙžUÚÌJÚÑSZQÞÔ”ÌÝØÍUV‘˜Ó™MÜÚ’SœPÚ^
Õ^Œž‘Õ™ØÑÑšMÌR•Ñ]YÕÌ\›•ŽÑÌJÑUÚ–’^œÔXÌÙ™ÊÕÛUÜL•YÖÔš™ÒÕÜ^“––™M™™“šUVQMžSX‘[ÝZÚÚTšX˜Œ™‹Û”LÚTÛÙÌÚÌ’QÕ”RÖY\Ø•“XV^Tš‘”•“ÚÎVLÛS˜Í[žŒ“PŒSÐUÐ‘ÓR™R‘U\“[Û˜YÕ“ÔVUÖ[˜‘˜ÍVš™ÜÞŒR^R›UUÒŽ‘S[Û•”U^YÌžX“ž–S“ÜÌÔRÌÑQÙ[ÑÖ”ÝÒÛšÐÚÔTÕYLÞRÓMŽTšXØÜÝÎ]Õ™ÒÛ“ÛMZœPÖNSØ˜”PÚ–”\‘VXP”š\XÍÙØÙMÔÓÖ[]ÑXV’šÐÕÔ’ÚUMÕUÓLŽTÒSÓ“ZN^”˜ÒÍ“ZÍÝÕ\ÚÍUÜ˜’QRÒUÑSžSZÚ”šL–SÑ”›’LMŒÕ[[N™ØÍ•“ÜÓÌSÚ›ÚŒ[ÍÚKÎSR\ÌYÝY–Û’•ÌÌŽ“RÊÜ•ÜÌš^›P‘˜UÒ‘ÛQ\Ú^ÞRJÑZ™ÒÐ‘ž^PQÚÊÐ^˜ÎU]‘Ù’™ÑLÌTUÕXU”•ÞžU“‘[ŒÊØÚÚÔQ˜ž‘S›ÙYÕNLÙÞ–M“˜ÔÒÒŽRLœQÍ”™ÛZLS\\šž•ÎYÒ”›RM›”ËÐœÛ]ÊÞP[QÑZÑVYVÜLØÕ”ÛLUžÔ–^RN\‘ÓUŒžÒ“˜Ý˜ÙšÞQÍšKÝØØ•ÌQÚ™Ý“ÊÚ’^^™RRN\ÛUT^SU™\’QŒÒÍœ^QÍÙYZ˜ÜÐ–^TÒT™ÐUÛ“PÕÙX›Ø•Í^Ú^ZQ”œ
ÖXQ™•^Ú‘X’Œš›Q”SÝÖ˜ZÓœ^›^”Q˜TÕžZÝÑÔÓÌS\ÚÚXXRÖ
Ó’L‘
ØÛUšRÌœ]ÞQRÚMRÕYPPPÎ[TU•MÒTÙšš’•“–’S›ÕÜ]•UšKØÙM””›–•ÑR–ÐPL”Ž^ZUX™Z“•V›œ•X™š–Z‘T‘Ù”ÓTÖUÌVœÝÔÑ‹ÖLÖ[•ÛÍžØ]–“ÕT“‹ÖTR“›VÞS“ÑXQ‘”Û[ŽQ˜[šÔMÞÝÑSJÐÑ]Q‘Òš•\ÔÑN[šœ^^›•[ÖœÐ™LV[ÓTšÙL”œÕRT[U[\ÍÑXÖRÑR›“šÙ•ÚYÛ’ÞQZÖPÓ‘Z‹ÑVÍ”ÔVZÛ›šÍÕQÕœÛÚœLÖ›ÍPÕQ^TŽ[’[XUÒUÛ
Ú]Ý”ÑÕÜL–ÛÌY•ZSš‘USJÙR–^R’œš[ÒÝVÒ[Ìœ•ÕÒÛ–Z]NXZŒ“P™Ô•ÌS™ÜÕÕUÍSÛXÛLVYÕ]Z‘•[ÒLŽÊÛSM[ÚQQ“X‘‹ÑÜYšTÕÝXÕ[R[‘œÍLV’[VRÒ™šÒÔQSPÜ[’[Õ™ÔÞÔÞQYŒTÛÚÝÞšØZ–šLÚÑÔTÒKØ‘Ø–Q’Q™ÑZQœÒUÑ^‹ÔÝ“‘ÕÜNZÍLS”ZØ’ÙÓÕÌ–ž]^Uš’YÑ“MU[QšUœ•ÚÔZ’Ì–TÐ“PÞMTZÓ]ÛŽÒ™•‘ØTM’Zœ•šÌRTÙ™›M™“UZ[UÚ’PœÍS^LZTÑœÕÒÐYÓQžL[MÔŒž^]ÌKÊÓž’U\ÙÝÎ‘œ“Ù”RR‹ËÜRMRQÜTÙŒXÖ[V^œÛ\ÚLÜR‘UL’LLÙÝ[–X™ÌMRÌPÛÔTLS˜•UKÝ–‹ÝØVœSPTÑ•šS˜LÜœXÙÌÒ˜S””ÊÜRRV“QÑ›Œ^YÚ‘P‘•ËÍÔÜLSÐÞLÐQLX™LÔÕÐ^[Ñ^LØŒÎTÚÒUÞLÛÚÚMZ–“›ÎÎLT”ÞÊÔT™ÜÒ‘••Ô’œÝÒM^ŒÝšR™[›MNMÙ’ÑYZZ›JÞQŽMÖVšÓÛV˜•ŒœXYRšÚÛM’\ŒVPÙNVKÜ•LZ›šÊÍ[\VKÛÖ[’’ZSZŒX’\PZ[‘]’ŽRRŒX]ÌÕÛÖQËÜTÔÕŽUZÌŽQÙÒ•ÚÔÜ\QXšÛÚÑÔÓÒÍÍMÔYÔÑ™ØŽÊÓžQMLœUX\VRÚ‘Œ‘šT˜“ÛÕšÖ“NœØÕ“Ú““KÑÕ›šPÒ[ÔKÓÕÚQ‘SXÕÔTPÌ‘Q‘SZSÌÒÑÓš™‘]UTÖ’Òš^[[Ð”KÔÞÞ\MŽQ[RÑQ’PY’ÙÔØ–ÎQÞ•ÑRÙÛžM]–YLÕÌœšÜ›Ñ‘ŽU’ÒZÓPÖ]T›ZÑÐ”Pœ”Ì‘˜TÎSÎQ[Ñ˜“ÔÜQ^•YÔMYÓÍZS‹ÒÜ]\“š\RMÒÑ”‘XœÜ•ŒVQL•“™Ó]žTÜÌ“\Ú™]–˜ÑÕ›žZÞ[ÝP“ÔÌ
Ó•^TÓTYØ“ÖŒR\^žT’ØUS‹ÚLšÓUÑ”\”ššÜ˜Ì’™•ÝššJÛRXÓ]˜ÙÖÊÒÛŒÍ’“Z’™šÕÔT•\ÜÜÖ›Õ–]Ú\ÌU˜ÜRYLÙØ]ÛÓTŠÑÍÕÜÜUœTÝÖ™ÍÍUÔÍR\Ô’›žTÑÒL›ZÔPZU›ÒœYSÛT‘TÝÚÒV]ÝžZÞLÒ^NÑUÖœÕÓ]Ý
ÕÍŒÕTÙ‘Ü“’ZÔÞ^^šMZÚ–›YZÚY^QÝ‘MÕZÓZÐÍNP[TZNS‘NRZÍ“L[\ÞP“T[ŠÜ“Ú]Ö••SUÜÎL^“Ž‘šQMÙÌ“•PJÛÚŽQÚPÞVU“UžTUPÕÕUR‘’™Ò[ØN\ÙZQ]ŒTÔÒ™Ü’YUSYÒUMœÔÜPPÊÕÞ[š”Ñœ›˜”]ÍSÒœQ[U›ÙQU™]ÐR™ÖPXÓÖÜRU“ÚZ’ÍœšÝ›’š›ŒVJÌ•žÔÛ\ÒÑÚNR›ZÑÛXXS˜ÕYÒÓ›JØUJÚ\T“[ŽYÜL“•œSÛQÒMM‘Ž\œR[›Þ›ÒZKÎQ[ÒžœYNR•PÓœ‘SXž•PÓPÊØVÝŒœÜÓMÔ™•Œ’ŒU’RJÔÌP]P›ÊÑ›QRÔÖžÜ\XUZ›’U’^SPÝ•›Í“^U[ØŒM“ÕÞØRJÝÛMVQ™
ÛØSÚT™LYN\T‘[Ö]\VS^‹ÕÍX[YÛÍÜV“TMNÕÌš[RZSUÌÑS”’”Ñ–Ñ‘Ò’›”“ÖXÝ[‘S‘\PÑX[™“Ì\^›[^]š”T•˜“Ò‘•TÊÛ
ÕRSR‘]ÔRX’X•ÓÚÕRÍØXU“žŽ”U›MRÒÙÛQÕÎPÜZÓÑ“ÞÌ›[“TÞ^‘ŒZÓÌ›P•ÙÔ–LœL^U‘Î’ËÕ‘ÍÑœÔž]Ö•ŽQÓÌRÛ”T›ÑÔÕ•ÐÒœœžQ’˜[[šYÓ[LŒœQÕØ”UŽZM]šXRMÕMžŒÍ\L››ÓS›ÍÌÍPV^\L[ÛTVšÛÚ•Ú•’–’ÓÕÙY–RUœSÚU’^JÒ‘ž›ŠÚÌ”[˜VR
ÙÝÒœMÖV’ÜÞœTRÜÝÍÐ’^ZZÔÖ•S\]Ü^^œN[YS\“\œL‘\™ÑRSš
ÙÖÔM”ÚÛš›’]Ìšœ\œSÕÞ–[M”Ò–RXN”’Ý“ÛÞ
ÝSÒÔŒËÝRÛœNšÕÕÚÍšÝ’[ÛÙÔÞšS”Ì™R™T‘“SQ^YÝŠÖ’ZUUR“”Ò“•TY”“\T•“ËÔÌUÝÍÌÕšNÞZZ’LÌÚMžPœ”š“œŒ“œÒ\žX[˜MÍ]›Õ‘ÌÕŽXÕÛLÔœž”Ü[ÙÚ]ÞQÌTÜ™ØØ[\Ö”•V]ÓP]ÐœÔ^NUÑžVQ™SžPT^™ÝÜÎ^ÛÌQÐÑ“Ö^VQÍ^˜SšÒ›•ÍX‹ÛÜÐÌRP‘ZÓÜTÍÔ•\ÕÕœR‘Vœ›RÚŒT”YÚ[Ñ•Ì“–‘Yž[š[Y]•ÚÍ’’Õ]Ó•““]MQÒPÊÞY“UQMÞ‘YÚ“šÎXU–\ÖžPSÝÌÚØšÙZ“Œ›‘ÜÕÑV›R•X˜’ŽÛZÝXÔ”ÐUÛPT\ÌÍÝÌÚÍ”ÞQÕ\ššMZÕŒ›XUSZÛQSœ™UTU’P^RŒÜTÔ’SÜÐÍÑ‹ÓÓ›ÛÍKÑœÛS
ØÒ“Y“ŽYÙÌÙLœÙÒÓ’V”MÑNUÌÒ›Üž[ÜÕÓÚÚ]Ö[Õ–•“ŠÛÔÓž•ÙŒÜ’PV^[Ò’VTšÑ“žš›–[XSÜÚ[SÙÔ’’˜ÔPÌ
ÎÑ“›^YÔ˜ÑšÑÍÜÌQÜœÒ”ÑVNPÓ]“ZÓ‘M›”ÒÑTÍÒM–^T“Ò‹ÑTÖŒÙÒÍU’Ú™ZÎL‘›’ÔšÒÕ\›XÖSLÍ\™S’Y”Ò]ÚÕQY•YT”ÜÞ‘Õ•\šÍ–”œÒ“Õ™Û›S]›MÝ•ÙÝ–T–TLMJÞ“ÙU]ÌÐUL’ÓÛ‘ZÌLÔÛLÞUÙÞQ’^VR•Ú•M“”Ì›ÜZTÑMÛZÖN^šÖ‘L[Ø˜”ÕUÜJÝTKÔšXVž]UŽ“ËØÞV“ÌQ›
Í[ØØÙYXÚ^”šÓœPSM]‘ÛUÞÔÒL›JÌžÝRRÞÌU]”•‘ÌšUQ\LL›ÓSÓÙÜÕÕRR•Þ”XÙÍMØÞÛMŒ[‘Ó›TÖÐ–™RM›ÚŽP^[^[žY\žÔURÝÜ’USRRÚ]Ù\S^”ŒÛž•Ü”QKÌÔ]U›ZÔÑS”™ZÝTÕ]ÍRÛUYQ[ÖQ\[R–š[ÍÐ“Ñ]Û•S–ÝÊÔÝ“Ô“‘V^ŠÕ•Í‘[PÝ‘\Ý’ÓŒÒ–Ú•ŠÝ’YÕNÖ–SÔÝR–ÜÒžPYÎÌ”œLLÔ\“›YÜÙÒ]ÙRÚTZUž‘”™ÎRULLÑ]”ÜŠÒœSÖP[\[ÌÙÐYÍ]V’TZÙÝÖURÞ“LÌVZXÚ’“š˜šU\LÛÞS›LÝ’“ÞÛ”Û^]ÎRSUÐ]Û“˜ÐÞŽŒÝÜ’MYQÚ›U’R˜•UÑR‘ŒšZœÌ’ŽYÙ”‘SVœLÒZÐÛUÜšÞXÕÞSN–]“ÛÐÒ”]”Õ‹ÓÜÖVQ”ZÚQ”šËØ’ÛÔÕXÜÓÜ–R\XSÔ”Ô‘›R[ÍL•Ò[œÚÔ–Lš]Ø›ZØ›•ÚœÌYÎQ]V›•ÐQÞT™MUÌ•ÔV^“\›UZÜ‘Ú[Ñ•TÔÚQÛVZÌQ’ÝÕ’]ÒM˜–XÚRRSÑMLXÑØÜZMÌVÚÝÕRQ”›””ÑLÐÙÌÐRÚJÑ•US“ÐL›ÑZÜ’ÑžTUÚÒY‘L™‘’ÞTUÞŽUŒSÒMMšQÜšNžÖœM‘“NMÝ’ÑÙÚM\Û\QYÚŽMV‘]›ZÒMUÍžTÕÛQ’Ì˜™Õ’\œ–˜ÝÐY[’SPšÖšRQ”ZÑ]T\ÞÕÍPŠÌÔÖUÙYTÓÑZ‘šSÌKÕ‘^˜”““ZÔÞ^”ZMMP[ÞQ•ÙÚTØÕMQŒR“V™“ØÎÛRšQ–ÓÙVU^œ‘ÌSKÞ’ÚÚ’“ÛL››R›JÚÕ›Ñ‹ØÚØRUŽ›”XS^RNQžRÌP“œœ[“œX’šÞ”PZSÔ“S•Þ“[”]Ù‹ÛÛU•žTÜÛ›L™[S”TØÜTÞT™XŒLQN\ÍYŒR’ÚÍ\ÎRÌLMLÒL[T“ÖXSÚ•\UÓ’œŒÚ“–\‘Ú]US˜ÚZXÍ[NV”‘™VMÒ‘\‘’’ÍPÔPØÕŽTLÕ“ÖÛVŒQÍÛ\•ÜUÔÐÜÒ•Ð]ŒÓXUÖÑÑ™VÝž“^’SÌÓ‘–\šS™
ÊÞX’Ž^[XÎÌÎRPÜÔP™LRÛYœšÕKÜËÜÞž–Ù‘”Õ]JÒÖQ‘ÚLÖ[[U‘ÔÝÓØÚžœUÙÖV]”Ù]Ò[Ü˜”ÔÚÑV\YUÜXTR^]ZÊÕUQÖPSÔ\SÙ”QÒ]ŠÝÕL’TUÍÛ[šN[ÕXÕTT’PÜÔ[•M^TY™Q–“RZ˜Ý›”ÛU•ËÓÚS“–\™ÝÙ•Ö””VœXÓU“ÍQU[•ÓÑ•Ö‘Ö’QÑUŒÐÚÛŒÝÕ‹Ð\–‘RÓÙÚNÞ›š›R›™]ÝÓLÔX]’ÕQ•Y]ÞNUÑ]Þ‹Ô•™’ÌŒÔÝ•TÜ^šN\LVYžÓ›”–[‘ULÌÔÐŒPÜ›œ“Sœš“\
ËÔÓÞXRUžJÌYšPËÐ’’“SRÓÔV^‘‹ÑœV–[Û^XZ”šNMÔY’ÜÝš™Ù‘ÛÖR”Íœ˜RÜÛÌÞQT]UÒ™‘PUÓ•ËÓÛÍÒÜ^“˜ÔYÞÙ‘ÔMUÛ–RM–™“RRÑRÚÕŽYXž‘’LÎQÑÓ\ÍÜÖZØ˜™ÔÛŒ‘[ÙXœšXT’SMŒÐÒ–U\Y•ÖÚUU]Q›]Ü^ŒMšÙ•JÙYNY]U•[UU–‘^“Ú]™ÙÐ^ZÜ–˜””Ü[”XQœ^SZJÔÔÛSÜÛP”ÓœÒ\’ÜÛRÙS’]ØZ’T\ÐZÌ]LÛÑUŒÞ\›‘”Í^QËÑœ‘U’’[P‹Ü\ÑPQÕ‘ÛÑÜY”ØM[[\›XXU”TÛZ[ÜÌ“š•ÜÖNM\MÑM‘Ò”U–RÜSØPTPNZÍZÖ‘Z•ÔÍÓÕUYÞ^™ZÕšLÙÜÎœÝÛLÚœÍÒÔÎ‘ÌØQœœ–KÓKÐÑÕYÍÔ”ÔÍÚÚ’™Û™ÒÒËÌ•[Ó›‘ŠÕNÖ
ØŽY˜ËÜÝšU›TUžšÔÑÙšÊÖU–Q[Õ‘Ö\TÐš\Í›Û˜YÝRÚYQÝ’ÓLÑ^MMÑœVšÛX™ÕÙ]ÍV\ÍMÛ
ÛÞÛ”]ÌX]ÊÔÝ˜”SQRÚ”•Ò”›X–Y”š[’‘\ÝžL”ÛÜRÕPžŒLYÒÞšZRT–MRÕÒÔŒRQ™\ÛPP’’–V‘ŒXQ›MÝUÑÔRÙ›\Í›ÌÕQÑš\PØÐžŠÒÎ‘LšÖ]ÜNV–Ú‘œ“™Û‘ÚXR”œÐÒÞ[ÔLV\ÍYÛ“UÔÕZÜÓÍ–]ÛÝ
ÕTÑ“ZžžM™Y“^›”“ÕMÊÖ]UTT[ÚLÚZQÝ‘ÌSP˜ÜXŒXPØQŒV’UÖ[ÒXÓŒÍ––•ÝÜÓ]L™^PÌÝX”Ý“ÍXT\ŠÕ™[ZTYÚÔ™Ñ\”MššÞVKÜšMÝ››Í˜ÖšP™]ÚÎ’SÒÔZ]ÕSÎ[SQ›XÕŠÒÛÍLÜ]LÝÓŒSØÊÔÚ^QRÔÑUYÞ[ÔYÛ]Ñ[S–SÌMœÔZÌUŒTÍœ]šÚM^M•UœœÖ’RU–P‘Û[Ñ–UÚU”ŽJÐ‘–œÖžPTVTŒLUÞ‘•œÊÜZÝM–“’\ÝÊÑNLXØœ™Ršž^
ØR\RP”›ž\”›ÜT[ÜØ“ML‹ÑUÒTÖLœ”ÝXÌ[ÖRYÔVQ’›œ”ÌY–L^LŒÔÍ–Ó^ÙÔÖ\ÌÐ\SÛ“Ñ›˜ÎSÍ”•œšZÝTMXŒž›ÒÌ’ÑUÒÛÚž[Í”“ÙXÊÓNÊÕ[‘VLZUŒØœ–ZÑÒ]ÚMÝÑÙ‘ÓÔ”š\ÍÍRUÍÒÔÝÕÛÌ”Œ‘ØS\Õ\˜–\“‘™™ÛS]™Ò[–Û‘Ž\˜YÛ\ÕP\ÎUX\š^ZZÞ›ÜÒÓ]Ö“ÌMÖžZ]ÝT•Ö]ZÖUÒ•ÎV”[L^ŒÕÓZŠÑXÞZ]LTQ]Ý–Þ“NU^’–˜PXTYÓÓ™•ZL•[ÚTÔ˜TRUŽŠÕZÑÙQZÕ^ÜQ^‘ÓÍ[]XÑÌ””ÛÎRÑ”’TÎ]•Õ”]Sš‘ZÕÍÙœÑÙÕ™“UÑ™SSU”ÝœÛÑ\ž”ÌšU™UV™M]ÝÝ
Ñ”YžRX”[ÚÛQXLÜÞUQYØV•’RZÜ“Ó\MÝÍÞUM•ÓQ[]’Øœ’MØÒ^ŠÐÝ›’LŒYUÌÞÔÕÌ™Ô›š[RÐØÚLÑUÖZ˜Ø™ŠÜZšÛ™‘˜YPØ’ÒŽXV‘ÓšÍZš
ÒÞÐØ•š’ŒUœ‘R^œ›“Õ–šÞšUÚÞ\LÔPÓU\RÜ˜ÚÞUUÝÓšÐ[ÍÛÛÑÑU[ÓŒM’ÐÐTŽÑœTZZ^ÛM‹Ð’œP\ÒT”RœUÑÞ‹ÚMÑÕÚ”‘[”V•YVÑ’ÊÕÜ’UÖU[ÎLZ]šÒÛÌÚR[ÍÛTÙN‘˜VœÌÌÓSP›Sœ™[UÔš’”ÕQÖV“›Ú]Óž]”MR’ŠÖ”œ˜MÚ“
Ö–ÍÜU–‘V’œØTÎQYÙÚÓÎLÓÓRMËÚ^QRœJÔZÌÔÕLÓZ–™\ÝÕÒ”ÍU™][XŒ™Ñ•šÒ•U–“Ú™™SÚšZMQËÜRœÕ•ÓÓÒÍ™Ô–ÝV˜S’UÍÛŽQÜY””šØ•\‘Ú›X›‘ÙÌÓKÓÐØÑÒÜÔÊÒUX“š“Ì[ÑœL›ŠÖÝÐŒÖ˜L–™ÌSTÐÜÚ‘›ÛÔÚQÛ•Ó›™YœÞZ]UœÔŒ[ŽLœRÓZœ\ÐÓŒX\UÖ›Þ˜S••ÍŒT›RÝÚ–SMÙÒ˜ÑZRšÌÜZž™›L“UÍÔ“’”ÌÔÚ]\ÜÑZ‘’Q‘S•QÛ›ÜÖ“Y“ÚÔ”Í˜Ô˜L™]‘•RÛ‘ÙÚ“L›ŒÕžZÛ]ÞœNŒSšÒÒžÙ•ØÜNKÝ‘MÙ–[ÖTÔ˜ÙÒšXÜ”ÜMPÌÛÑš•”VUÓÛRŽLQÕ˜ÜM
ÛRœÚÛ‘›X”ULXÑ‘˜˜ÙÐ–ž‘[\^•MÌœÔž–[Õ[ÍÎLVZš“ÔÒÐ‘ÌKÛ]MXXV“\ž^–S[œTZÚ[˜TØ”ZV[XÒ\ÌR\Ð”Y[]QÓ‘TM™QÚÑÜÝÊÝ›YšÔ\œ”^QY^Ò”R‹ÒÙLRÍ’ŒJÝÞ™ÐÒÑ‘š’ÜÙT•ÙRÝUÛX^TY]Þ]MJÑ–QTRÚÙ‘ŒÓ]M’ÖTÛÐ\ÖL[ÜØYÚQZÑÔSZQR”]Ù“MÝ˜ËÌ”S‘šY’PZÙšU’”“œÜÜÒX’ÒQØU\\ÔQ^˜S‘‘SÍXXÓÑÎ•[^‘XLZÑMÔ‘ÓšÖUØQÞLVS[ÛÔMMŒ•]Í–VR‘ÓšKÜ™™Ôž
ÖQÛŒ˜ÞMŒ’“šÔ[‘ÓMÚÑ[ÞÕQRÍUÔÖL[ÝÍÝ”Í˜ÐPT˜•Þ“’“–\ÍY’SÖž[YVŽ[Ñ–[KÐØ’Y“ÒÛÔZUÎ\Ý[Z›ŠÚ^ž^’Ù›PXKÑŒÚTÙÜLÞÖRL›SQMÒœ–
Ô]TžœÒ™Ú[VSÛÕ‘›\•ÜPZÚÕZ]ØÛR\YÕÒ\ÌUUÔšŽ‘XÍ]PSšœÓÝž‘Ô\NYÖ^QÛÞ›ZÐÞØœØMXÑšÚØŒ\’’VšÑÓSZÑÝZ–“^L^ÑššZœÓUUšœ•M“RÖ˜ÓŽRËÔž
Ó™ÒZLÜLÒ”ÖŽ\LVTÛVTTVX”Ì[”UÌTÚÞŒTÓSLZÖYLP•ÌM”ÝJÓžVL•YMÝ““RKÌžZÕšU”Ñ’TÝÕ
ÝZÛÕØYÑÝšY•š•Rš”šÌM^Ò“ÌØ’^’ÜTÙÕ”LÔÎ\YŒJÌTÙÔTTS”™ž\TSJÍÖQŒ“ÍY^^š˜™[YÓTX[–˜œYÜŒ’“P™ÛÔ’[ÛŒÑR–•Z™UÐPÙÝÒÌ™ÐÜËÍV™˜YŒŒLÞQV˜œ–^šÌSÒÚ]ÒLÖœœNNYÓ“YL’ŒÔŒŒÛØLY’‹ÓUÔÚZRÑŠÌ›ÛÍT˜Ì“ÕÝ[š’^œÐšÔXVTZP‘Z›ØPU’S[Ô›ÕÜ‹ÌXYÜYÌ[RPZ™Ñ[U•’ZLTSZT“”]Ü’NXÔZÍ’PZ™‘[T^ž“ÔQ•”]ZÚ^VÍÚÝŒ]TTZVÍMØÍžQYÚV’ÑRLÓÕÕM™[S’SXŽŒ’SÝU’ÒP”Ð–QÞU\šØVTYQ‘ÕTÑRU’›“š]MNZQL™ÛQÒQRÒž^šÞšÕ‘]››ÌPZÛÑÔÕÒÞ“SÜY]ËÜ[Í˜SÚ[ÍSËÕžVŒÚ[œR•TÖ‘ÌTÑšR™U‘XÙUYP]ÖÐŽUSX^‘‘ZÚQ”ÓØÛ[‘[ÑÐÕVZÐVPœšJÚ•Ý“œÍNYNTÕY]ZÜVY]Q
Ú[›Þ”ÒU’žÞÐœ–Y“LSRÕÑJÓ’žœUTPÐ”^[ŽJÚQX‘Ò™ØÌØ]žÑV[ZLPÕMŒœÞ[ÛŒ™œP”\ÛUÑš”MšÑ^Ó‘UÙ–ÒÍYM•UZÝLÝÕQÓ–L–R›’™“˜ÓŒ[PÔ”UÑVR–U›Ñ–‘LV‘ÚÒÑ–UÓ‘[ÞUÝQ“P›‘šØ‘”LŠÎ’”Œ‘[SÌÑ\RÕTÜ]\”SŒ•ËÌØLV’žQÓÓ”œZÔ”ÌT™’R™Ó’‘ÜTYZ“ËÒÔV›ÒVÝ“XÑÑÔ\PR”’UÓ™•Õ’MœÓ‘•ÕŒPÌ•’^˜ÒÒMÔÝQ]ÚÐšÙŒ–žTÚZU””Z•–\šÜ]ÕÒÕÛUŒÊÝZÖ]••’ÖSMÒLU“˜Z“QL’Ù–RRYœÒ‘T’ÐQÍ–TœÒ‘LVP’Ü\\V“ZYÜMMÐÞÌLJÚSÔYLZT”Þ–›PœÝÍšÔ[ZNŽUÝZRÙ•ŒT‘ZTžQLÕQÐÐÚØ•“ÕÓ’LTQ”RMUVPÞœRÜš“•Y™œUÒŒ[ÛÍÝœ™–‘ÔZ•UØRTQÞ•S–UÝÞ™ÍœULT››ZÐL’\ÑÝZÍ’^TÓÞS™ÎMJÜT\Ì\Õ™’T^T™›Ó’Û•Q^V\ÓÚ•ÛÝÕ
ÕÙ”LÛQ[QVÙÔ’XLTÓRØÖX•Ì”]SÍV–™ÓËÞUYÖS
Ý˜‘”Z^•MÛÕÌ™ŽVœUÖ^[NSY^‹ÖQÚÜÒVœUÕQ[’ZœÌÞ“‘QØ’[ÒRž[RžÒ[TX^ÓRÜ[ÖœÍKÍšÑ\™UPR]VZ˜Õ^V^M[ÞžMPœPÝ”œ“Œ^•PÓXÑÕ”ÓQÙ‘^“žUÕ™œ]XÕ™ÞÙX›R”Ü]MR˜”Õ”ZÚ[Ö\–XY\QYšZÕUŒ[[Ðž‘N[ÜžÓNXUTÑÙPÌZŒ˜’QÝ“–šÍ™”ÝšÙ‹ÑÕQR^’ÞžT[ÒT]SZÕPØ›ž[Ö”ÙÝUŒ™ÜZØKÚY]›ÔÛ”•ÊÚ›Ó”[\VÖŽÒ‘œR\^ÌS™”ÊÍ”Í‹ÙÒ•V˜ÓÐ’SSÞU™’SÚ[’TÕ]ZT–[QYÒ’ÝšS]Z•L^Z’[ÌSSR”™ÍÔÝÐÌÙšÕSZNQÛKÍž•ÔQŠÙX\ZV™ÔS“šRÛRQÌÌZP››KÎKØÝMSœ]“[ÛÍMKÞ™\”XÜ–ÞJÓÒ[XMžZØPQR™MX\›NR–^XXÝÝ•ÕTTSÙÖ’›N’ÒÌÒN˜XÔÑ˜SMÛš^“’ÍNZŒÝÎRRZØMž]Ø]Z›™LÙœ–SRTÓ”RØÌšÌÓÍ”žØËÖÝšÔ“]’š\œ˜YÒLLUÜŽ“’LT[ŒÓŠØÓÚÕŽÚØÚÕÍUX[XËÚ›ÝYÕ˜QÞÌÝÔY‘UÍX–]ØËÝZ’SŒ\V•”]“ÜP’QNXÓÎRÖÙ\•’ÒV]U˜ZLŒØ•ÌQÙXŒ–[ÌÌ˜ÛœÔ™UVNQÔRTX™TT”X’NSÕ]Ù‹ÐÚ’‘\ØZY–‘“žQ]TÍŒÙŽQ‘PÐÍZS“ž\^›ÜŒžÜ™Õ]ÖZ^œ›œ˜œ[Í^•\ÑÎ]“ÍÚUVM
Ò
Ó”Ý\]•ÝÌYXÝ–VÛRP‹ÙÚ[ŠÝÐÚÍR•[™ÔÖ™ÛšžÓ]žYŒ›\^ŠÒÒNL\š]TÒÑQ]œÒ‘^^–PUÕÔVÊÜ›YÒÞž”SÙ”ÒÎÑÝÖ–ŒŒŠÜŒ’žœ›Z˜ÔLL˜SŒ
ÑØ\ÐÙ’MS\T\Û\ÙVQšPŒœÑ“ÚÌÙžZ‘QÌ^˜XÛÐÝ]ÓÖÒÑ•UY\SMN›ÛÕ”Ñ’ZÚÙT”S‘ÌÚÝÞLÝXœTÒ\Ñš]Ò^™U˜›T[ÛÍRLÛUÖYUÛU”ŒÖšÓ’Ü›Ì–RY™ŒZLÌQMSÕÑSÒš•ØÓ
Ú]Þ\V’ÕQÛUVž]SÐÖœYÑRšÑÔ˜UÑÝS[ÙÖ[ÎSL‹Ñ]’”œQÝÒ‹Ù˜Ò^•–žœÛMRœšÜŽSÛÜÛYZ]Þ™ÐT”Ó“ŠÚÊÒKÍ–LšÖ[›
Ñ^[”ÍØMÞ‘SSžŒœÓÔ™ÕVQ“]Ù”U[ÐÜ–šÜÚÌžYSTUS™ØRLLËÒÔ”‘ÍPÝšËÑÝZYYÐ–P^“V™LÑ•Uš[Ò›ŽÚÝŽÎR
Ì’KØÝ•“Û[P]‘Œ]\œ•–T”ŽÚÕY™Õ‘™œTUØMVPÛÛÕSÞ™ÌZØÔšÔMLÐÚT˜PÚÔÙ[‘“[V›]Ñ\N‘\™Z\ŒÒ]XÛ^Û\”N\]USTžÍÔ’•ŒPŒŒ›Ýžš^ÚPÜÐØšMØÑ]ÙMNRLÙS\ØQ]œÜ–”X”RLÜÜM]•ŒKÑØž[UÖ[[RÞ]–ÓU”œV‘ŽLžÝŒÕRÚÍ›Ú”S’NNS“NU]”Ðž]ÎV˜ÙÙ’™”[ž\JÔÙšRÞžÛ–š˜Þš[MRQÚYQÕÓÙÕœPQÎY[›Ý[Ú™’S™VT™YÕLMÔÞÑ›]ŒÌÝÍÝ™‘U™‘Ø–ÌÐŠÝŒÒÕÒÐYRÒMSÖPŽRZ”™ÙUÓÎ”˜Œ“‘›ÌRVZÙ[Ñ[[Í’›Í™™LTQØËÚÜYÑRÓTÙØ]ÑN^\[ÚÌNÍ“^ŒX˜ÌÜÛ]ÛZT^T^\Ö’^]V˜˜œRM›\ž]ÔÜØMÐT]NQ“YÕT”œÝÌŽRž–STÒ“NÔYZ›ÒLÝ“NÌTV[Õ›[“’QŽTXž‘XTSÙXÍQ“ÑÑŽ^KÓÙÚÞSÖ•ÞMXœÍÍÞXÚ]žT•“Ò”ÑVÙÓÍSÖQQÕ›TÛ”ÍMÝ”žžYÑ[ÖKÔÓÜ’LRÚÔQP”˜“Ü”ÙœÛ™NœQšL“MšTÑœŒZX\™ÒPSÐÖÝ”ØSÓVœ•ÛžUÓ›ÚÙZNS‘ÓÍ•Ó–]ËÔ’ÜXMÜ]Q]ÚZRÌ“]Þ™UÔRYÎ[Ü\TRÞVSœSŒT™Ü[N\Õ‘“MÌJØÚÜÔšMšZÛQØšRMZ^“ÖLœRZÒËÕÕZUÎLÍ›ÙØÕœTÍÑÝšÍ[ÌœVœÐ^šÛZ]˜ÓT–™Y•RQP˜LœÝœÑ‘^ŒÚ•^›ZÒÑ^SžMÞ•Ûœ–R’]ÖÔÑšL›^šÐÖTUPÝžY\ÙRMV›ÞU]ž[ÞÍSÑ\ÖTÍÛMM‘šUÕÖÌ˜Q›Yš–T\LšŒÝ•V\UU’Œ“ÝM‘Ý\›YPÑÌÙÚ[Ô“SQVVÒŒ
ÓÙÓ’ÛÖQT‘œ›ÞÞPÞ‘ŠÙS[ÚŽ\Ý]œÙMU”ŽQÍœÙØžÑÛRÐPÚÙP“’ÜØMžUÒ“ÓÒŠÐ^]•\“˜[Ó[ŒžÓUÙÕUÙRÚÓU››šŒËÒÞÌÜÙPSL^Œ™TÜÑ”TZÙLXU’šLÚÍ^QÓ^VžTYMœÛšQ’‘ZSŠÜ“‘KÝÕ‘NV–’˜œVÒœÚNMÔ“ÒY›Ì]šÐL]Y–Q‘]™ÑXUÍÝUÕÍ‘ÒVY™\Ü\Ì]Þ›”Ð”RYP‘XÑÍPYQYÍÒ•”Ì’žŒÚÐÙLÌZZ’žYŒÞÑR“LÍ\ÍM™SÞTÕÓœZTTNÌ™Ñ–˜Ô]˜žQR“QžS]Ý™P’ŠÜMœÕ˜MÎ“ÊÓØ\YœTŽKÓÙLÌKÚU™ÜYÖYU\[ÞTÝŒÞRPÓ“VšU\[•^ZÖ’œÕœŒœ˜ÑZÙÎVYZ™Ó\”ÕÖYÔX\Ö•[ÝÌžš˜Ó^SØœÓJÒLœ’Ôž”“”ÕXNXÜLÝ\R\Ü˜ŒÚØ]–UZ‘›NT‘TÜ˜KÒÐÐ^ŽÖUX”•ËÑSÔœÎL^P[ØYÓLYÓÑ•ÛÚVQ]\LÞRÊÚŽMÒÕ\RÔ‘™ž”˜Ö“‹ÕÐVMÒÑ•M•Ý]”X^‹Ð^ZYÐ^”Tž“^ËÎ^TÑÓÛSQÚYÐÐÑÔ][žLŽR“ÎJÌž\Ó[R•Ö\œÌ›ÝÍ\LT’ÜÝÒÚ[T˜ÞÍÚ“žQ–“ÓÙŒ˜ÕÝžN“[‘œR•UZ˜ÌÑØÑ‘^^^ŽRQ™“ÛQžL[Ð]ÚÐMÖÕž˜•š•ÌRÜš”•”™\•‘ZY‘Z“TPLØÌ”T“N\\ÛRŽÒZËÙ’UVY•L^œÞV‘ÑY]ÓÌÓ–Ù““ÚÛ–ÛÑT”šMÚŒSP™Ûœ^ZÙÐÚÖÜ“ZÕÞY’‘NXÍ™\ZÚYT›”^^X‘NM•Z\›’Ò[]KËÒ›ÚQQ’•’‘\šY“’ÕÚXÔ“ÒŠØÞT[QÓÙÎUŽRÞX‘Œ‘ÎQÙ›•–SÐšRØœSÍšÛÒÝÍšQœÒÔ“ŒÐJÖQZKÍÍÎVJØžÝÞ[ÜÌSÛ’ØÍÕÓ”‘ÒSšÎØUÔMR\‘•Í\ÝRÜ[™ŒRÌÓÒ“ÔÚÚÕÐ‹Ô˜•ÚN–ŠÓLTŒÜMÎ^•N[USRV‘›ž•ÑÕÚžU’ÒšÝ›ÚÐÛœ\YSÎ]••Ö–”•š]˜LÕ“XTŒ›Õ–Žš\ÜÛ‘Ü”MÒšÚ˜ÓÎYÝËÎMÕ
Ü™ÓÐ›˜ËÓÒšZÍX‘Z‘‹ÛÌŠÔZÞNZ”MØ‹ÒTÌÛŠÕœ•UÑÕULŽX•’]Óœ’™S’Q‘Ž]Ô
Õ\›MY˜”ÝžÍYYÝ[ZÓUY••ž•M™Z“ŒÍÑ‹ÍÓšZÛ™QÝÜ‘”\[”“œšRÜUSS‘U™›SÍÊÚ\Y[ZŠÙÒ™VÖ›S]ŒZ”Ô˜šÕSXU‘]ÚÙKÕ›U‘ÍVLžZÑÜŽSMUœÞž“–•^˜ž–‘NÛ“ÌÑ“””ŠÍ]YZ™RŽ›•ÊÖ[Y[œž\NUšœÑ^šœÓÙÎXV“ÛØÔMÖžŒS–LÚ“”ÊÖŒ”ŒÓNÚÓNSÌSÚ^’SÚNÓ˜ÞšÛ‹ÞY[ÒÙ•QYÜSÜ]ŒPY
ÐÞLÚ›ZSÚÚ‹ÓØËÙÒÔœ“QYMZ›š’ÚÍÝZÚXÕž‹Ô[LÛ^•˜Ñ˜Ú
Ý’”ÒÐœM’RÜ^ŠÓÑÕ^^\ÓŒ’MÔ‘Y^QÌ–U™TX•ZžLÚ“Ü”JÍLZ]ÚX\œÔM›ÛTÛÞšÔ^‹ÑÔÒLÍ”TY•“ŒÌ”“ÌÝÛRÞÕØVŒÐÙŒÊÍN^›ÔÍ–]ŒŽØ\R•SÜÝÓØžŽ’™‘ÚYÔÐ[ÛNSÕ
ÕL•Ô–ÔMJÚÚÙ’RÕœLÝÝÖÖžQ’Ž’›ÖXQ‘šÞKÙŒÎU”Œ[Z•Û˜™–T”X–ÌTZZÊÜÛ[PœšÕËÛVYUYSÐ^•™R›‘Y””ÙX“YÍÌ”›\UL\’ÑMPYÎ\ÞVQ’ŒÌŠÙ›]Ø[[ŽR˜Î]ÞNÔÛÚ]ÌœÝVY\ŽKØž\]ÌSš›XZMÔÚœ–YÌŒP^”ŒÚ“ŽÓÜS^^TPÛÞž[Ì“’M™PÚRYšÒŽÎÒ\P•˜SÝPÕÊÛ’œX˜ÞZÑY]XUÔÍQ˜Î”ÜX[ÍRŒ™˜Ò–””Õ™XØSYQÜÍÜMÓ”V–\Ž]ÜÌPÔÒL
ÓQÐT]ÎLÌVÍŒ]UÌÞÑ˜MUÑ]TQÓXSÜÜ”ŒKÜÔÕZU˜STMÝYÚ]V•PP™NVZXÔœ•’U[‘Ó]’LYÝ›Ö[Òž\QYZ^’Ü‹ÒÑØŒRÞ•V]YÌÙM›ŒÛZÌÓYZZZUÚ™œž”‘ØØÐÕY[S‘˜˜UYS[Ì‹ÊÎ’TšQÌÍŒ˜\T]\X˜“SÍÝœUMZ^UTŒÙØRžŒÙP•ÊÛÚšÐÔÙSØÚTÞKÖ^•ZTÓÕLL™ÝÎL’ÑšÐMÔ•™šÎZœYÖRœQZÌ“œUÓŠÌŒŒTÛ›˜ÙŒ™ÙÐPQ“Ü”]–’“•VŠÓLÒ•œØR›T“ÜÐŠÖ’•QÒ–KÞU–Ž]YUPQÛ[ÛÑX–\[KØÑ˜SSÑQÌ˜ZÍ]ÒšÐœÜÙÝÌQT”Œ›YŽÕYÕMUÞÕ™YT]Ú’›ÞÛÚZ]\“ÙL[\””ÕNYÔ[S‘TØ•Y]ÝÌÛ”Qš‘ž˜RTŠÙ‘ÑL“’Û˜UUÞM›‘PÛ•S™Qš\KÙKÌ™š™ÚÜJÕÙž][ÛÛLVÐ[UÜÕÖŽÙÖ[‘“ÐÕ‘ÜÐ›\Þ›LŒV][ÙLÐ›Ò˜PJÐÙX›RTŒMQÔ]‘ÔÔVLÎ\ÚÍÓ’ÕQÊÝÓ’Œ‘ŒÖ‹ØMJÎUSÐØ^ÙšXYN^šÖÕÌž”•ÑËÛSÛÌ˜ŒÔSY‘ÒÒ›NMŒ™[Ž^[”™SÕÒ–ÍÛÑÚÕTŒ“Ö^›žž[L’ÖSTÜÖNÒRÌY”P•ÓTSÕ–^][‘R\ÚÍ˜ÕÓØUŽTÞ›šÍÛ]JÓPÐšN][œYUÙV\RZRÞ\ÛÒÚS^^\ŠÐ’ÒÕQR‹Õ‘UÎMNÐ‘Þ
ÝšÑ]ÕÝÌÐL]Nž”V•YÐZÎ\ZS™ÕXMLÔ•Øœ’ÚNVQ^œÓ[žVR•ÕÚ[™Y‹ÕšÌ]YVP’Z–LÖ‘MÖÊÓU\›LMÚU–ØÚšTÒÔ\PÙ^[\[•Q]MÐÙZMÛÑ]‘˜Í•ÔŒNKÌÊÜÐZÌÖŒY\[^š”^ÕÜZ›•™ÊÒX\“•œÕÐUÝ’’Y]SØ›–‘’ÑZÙVŒT–šš–YÍ[›ØÓLŒ’Ø]ÑZÕQYÌÝ^šžŒÌÞŒPÕY]ÌÜ›ÔSÙ•ÐÚÌÌØ˜U^Œ“YÙMÑÚÐÜ“QZ‘]ÊÜŒVÊÍ›•Ì‹ÕTX’ÕËØZØšÔšÓ]Ô’U™ÍSMŠÓÍ˜˜M•Pž[œVYšT››LØšSTŽSR›“QS]UžVLÜT[˜TQ\XÒÑ•Ò˜ÞKÐUÚQR’•\˜V“UÍS’TL™ŒÚÒÓÛØžSÛQLÛŒMÕÛLQQÜJÓžUÖ™Ù”ÙXZŠÜ˜[ÑSœUÔŽÞ‹ÝÚT]ŒÕMNVRÚML’ŠÛØÓÍÒRY•U™ÙRŒÐËÖš^™[”•šZÍÌ‘ÙN[ÍÒœMŒ–•\–UKÕUNTÝ•ÓÐÙRÒL[›PÑÛS\MÜÓ–MS“œÞ›Y•“’V]ZX^TÑÜU™•›Ñ^[ÕšRÎ[ÌÔ›ÓšÝœÌÓLÝÞ•PÚÙRQÝÚ›’]–U”TVÕÊÝÖXLRÞÓZUÒËÛMÚÜVËÐÖÞSÜ™Y–R•”™[ZRMS‘•Ó”MPÌš‘LQ^RÎ˜[ÙÝR^^ÙZÖ‘UÝ‘ÙÍSÙ•ÓÌRQÌMÑ•LMÔSXÕšØÜÌTØÜ›–
Ôœ’˜‹ÛÕÓÚURÎÍŒÌÞTRÒNÍÍÍ›TÔÚ›RŒP]‘ÓÞÔRŠÓÛÝÌLÊÛšœPY’’ÖZ[–Ü”ÎŽVQÔ”Ð›VZÐÚ“ZŒPYSXX‘Ù”Î[^LÔZR›YZZØÙLUP]Q’œÖ›YYÛVQÍÙTšÔM•ŽS›ÑÕŒUÙ“Ý“•˜ÒÎ]ÖLT–Y›ËÝÚÒ–›]ÚQL\‘ž“Z“ÔVL[ÕÌ•š•–ZŒYÐÓ^R˜ÚÓLVÒ”–™VÞ^•ÚÛ‹Û‘ÓSœ”YÐÓÜÜšZÌŒÐÝ˜Ü–ÖQV•^V”MÞ”ÕÔÔœÑÙY“Üœ›U–ÛÍÌŒž›ÙRMMYÚÑÙÍJÖZ\ÌœL“^‘UÚ™T“žM\ÛŽ
ÌÛ™V‘œ]Ò”QTPÞŒÛLÞ‘]\›ÖY•–˜ÌÞQMQMÚYVUÒÕÒ–MRÞL]ÞNP[ÎRÎXÎÒÌZÞRVLÞ˜ÞZÕ‘RÓ\QØZP›”ÊÕPžYÝÒ“”[Ý•ŠÙÔØÌSŽZÍYœ–M–Û›LŽŒ”ØÌ“NØÌÔRMÕÖŽÛU^V
ÌZ[\ØRPÍ•ÕT˜SÚ•PRTUÌŒRÔØ“YÖÜRÚÙÝ^YÎšÍ“Ô‹Í‘’Ø•ÜVšÔÔ^N\UØUÚNUSÞžR˜‘UÕ]ÑÞ[U[SÎœ]\šÎZÜMÓXÒÖÔŽXÔQV‘’Z“Öžž“SLS]›Þ“\•]RÐ›ÍÙØÚšYŒÍ]•ÙÝÙÝÊÍÙŽM›ÔU•PÔšÊÝ[[’˜UST›RŒÜTš˜‘ÔÓ–R^”Ù[QÙÓÕÖ^TšRTÍÜRÙVÔTØÙ–R›ZVžZ™LLÚLØZV•Ü™X™ÚœÖ[YTT‘QÓÓ˜S’ÖRØÚ”ÝUÞLÖÛŒ’ÔÙ›ÓžZU–œ
ÍUÕLYNVQTŒQQ‘]
ÕÙÕÓØYRÙÙ–’ÑL‘MUMZÐ[SQÐ[LM”ÓÍTP\LQS’ÖJÝRÝœ\”SÚÛÌÎÖLUÝ\TÝÑŒ”T–[MZÛÎSÚ‘ÜRRTÕXKÍÑUŽYŽžKÑVQQYž›YPÖSÓŒÓZV˜ÊÚÚ–]ÛÜ”R[\M”“ÚV‘SZ]’Ù\ÛM\ËÒ“PN‘ÚLQÓÙMTTÚÕÙÝZ•ÙZÓŠÐšÌPZÓŒÝ“ÓÙY›•‹ÝL•ÜÐÔÌÞÑML\QÑÍRšÚÎÜ˜ÖRYZÓÔ’˜•LÛR[ÚÍšT\\TœÌT\žŒ’]\ŠÔMTÖŒ™Y‘VVZÖSÕšÔM“NY‘
ÛXÍÞSV•\ž›Û™ØØ™ÜÜUž’ÑÙœØ™R›ÕVTÝ”™Ó˜JÍ\–›“›YÑœ–LN^UMU\–™VMÚZKÍYULLPÜLÝÔŒÕ]TÔÖPLž–ž›ÓPYZ™ÙÔÍÛQ™M’PXS–’ÊÌÛ›TÍRVÔÚY”“ÌS‘[ÛŒ[ÍÑ[S•œRX™ÙL’ÖY›ÛTÕÔÊÞXÞ™RÑž‘ÖVÌSÛLÚ‘’YÕT•TX‘‘“ÜRZ]]N•ÔØ^LšÑX›ÓŽ^’ÒY\\P‘ÜÎ‘–TZÒËÎSœÐR”Õ‹ÛÚLŒž•–QLÝ‘šÌ[URSÓš[ÚÒQV™PÌ]]ŒœÔR‘’œÍÙ‘Þ“Í\ÛÍØÔ”R“•\ØÜŒN[Þ›ÙÛÝ›\ØSÜ\Ø‘ØœÕ
Ð™’ÐQœœÖÜÛ[ÚM”š›ÔÎPÒL’[ÐÙR˜šœ]P™\]šN•“Ñ•XYN•Ö”ÍUÓÝPŒÛSœœ[RPÚØYYS––\žVNP“^ZŒTLÒ˜U“ÖQÙ›ÑÛ•MRÍ”QV[‹ÕZŒœX^V›˜Ý˜ÓÌ››”M[[ËØXÓÚ–‘’ÚŠÙÝÜPÙŽÛ[TÌŽ’L™R]•KÞŽ^YœÕMÕUQV›””P”LŽœM]ÒÛPÞ”ÙœSQÕÚ“ØÕÙÑ]Ú•V”ØÍMš–šPNXRMN™ÔY^Ô‘”]ÞVŠÙÙÕÙ\–]Ž
ÙÚVŒœÕÛ^Û]Ð^UÚÊÝÍ’ØÔ˜Ò\QLœ–”ØŒZØ^^ÔÛU‘•LÛMZRÎLRšš•R™“Ì™USL›‘’’ÍÚL‘XYžRÛZYSY™ÝÓZÚRÚ˜ÔPœST’T[“Ö“›’[ÕžŒV’ÛÑØ‘X™œJÕ[•Z•Í‘ZÑS^RÔ“ÚY\\QÝÐQ’RYM”ÝP[Z›ØLÍØUÙ›SUÓÑÞ”ÑRÊÌÐŽP‘TMÑ‘ÍÌ–PÙTLÓŽZ–P“TœÞŽœÙÒÝÒ˜Þ“Ó]TžÙ”ÒÌÑÞš›‘Ü™•Ú›•š\LŒQšY”UÔNZ[ÑÌÌ™N[ÔÑ\Ž]R\ÞS–™Û]œ]JÎTËÞ]”ŒNS’Ò–ŒŽÖ]›TÕ˜ÍŽTR”
ÌŒÒ‘YÜ^ÌÑMM˜Œ]œSÔMÚLÜÓÙ‘Õ‘
Ò]•ÒKÐŠÑZÛU›VœÖ›™ZÙ“™\Ð”Õ\ÔÍÚÞÌÙPÛX”ËÑ]Ý›LXSU]Y˜YQÒUÖŒMÖUØYZš•ÛÑÔ‘•›ÓÙ•””ÑÓM[ÐÞ‘[–Y™Ó•MÌÎUšÜL“œÚ^œÛÓÎMMZ™ÓÔœRÔTLÞV•Í^MZZÍ\‘œÐÝœœÓØžPUÞ]QZŠÝQ]ÜMÛÑLV™”[JÌÒÖYQ“‘žMÓÍŽžÒXšQRÜ–LSÒMÕVSÍLMÚP™ÚQÜ›Ó›QšUÚÛYÒ™›MXPÛÙMÍ“Ù•[“ÔŠÞÐÍÐÝ‘\RÝLœÚNR‘ÖYÌ’ŽJÖPZUSÌžP\œ‘Þ”Ü‘YQRQL[ÛÌÜSÕ[Ô“”SUÌTŒ•[ÑYœXÑ•žUš“žPNQÛÝ\œYØZÕRžLÑ\M“™ÞŒŠËËÜËÓÛ^PL›Î\Z”P”ÛžŽLŽPŒ›ÙÌÒ›’L›ÙÕ›”\ŒX™ÌœŽUÕ‹ÔT•ÝSÞRÊÓŠÌÖ‘RZ›™Þ”S’ÚÑLUšŒQÍ^™V”UÕž’Í]TŒÍËÕZ”’ŒRNZ™›
Û“MÒÕ–Ù’L™”Í[S^TÖM]”‘•ÓX“JÕMS[’•L[Œ“UØžTÍÔÛŒËÖXXŒ\Î“TÑÖ^[™œMÊÛ”Ô”Pœ’ÌVUËÍ”ÔRYVY™ÎYLLÛLÜÔTPØ[
Ú’žY‘LQÜšMÕ[˜Ô–[ÍÕ“ÐËÕRØ[ÙNTÙžNž’MUÑÔ–’šSZU›ÙšN“XR–RÌ˜‘Z›•›RRYÒ]QšÛÙ™ÝÜœŠÔNPÒUU]œQ]ÔYÌ”’M˜Ó’ÔMÕÖ™Ô]JÌœ–“ÑÓÑLÞÒTLÌN›R’›ÛÚŒÖÕQÌL˜ÝQLYÚSÚœ–ÒÓQTYN–˜RUÙPU”ÝZPÚÌÜR’›^’Í–“Ø‘ÓXXS^UÙœÒÙXMÕÔ]Mœ”TÒÊÜUÞR^ž^M”ÍÍMžUØŠÎT]ŽÒ]–[NLZ–Ò”TÑÓÚSÑ›–QÍÝL–RPØÑUŒ™“™M[ÒÎ’–LPKÒYPTÛY‘ZØ‘”ZZžTÙÛÒÌYœYXM“ÑL]ÌœNR]Y^œJØ˜ÐŽUÐŒ‹ÒÜ™ÓZL[LÜÕ”œÔÑÐ^[U‘š™ÙÕRš›Ú‘Ó™œÙÌØVX[VLÝVŒ›ÍËÎœL‘ŽJÌÔ“PÐŒšœÑSÔ”ÐSRZ–ÖTÛ–›ÓMŒ
ÚÒÚÞYY[ÜÛØRÜÕ]‘TÕ\U“ÛÚLSQÛœÔÔY”‘ÒLP‘S•ŽLœÙÓ
ÌÔM”’RÔ‘ÙU“]Ú‘SÐÔÖÒÚ™•”[›ÌZ‘PÔL”˜Ö]R’ÙKÍ˜SSYÊËÔÝMžÚXÜ›Ì’’ÞMŒÕŠÌØS[š
Ù]Ü^P™Ì“ÔÒÞ‘›ÜSÔTÙÐSÌšÐœŒ‘^PSÝÑ[ÑZSÑ]’ÝÜÖŒÜËÚÕÍMÚ–‘Lž“]ŠÓ’JØ\ÍœZNÛZÍQÊÒ‘”œ”SM“]ÊÔ™™]L™“ÊÐTY–U™šØZ™•ÛÝZÑ[žQÕ^˜Ì^’™›ZL–ZÙ“‘”›Ú•ÒÔÙÑYÑÒ–MÕÓ˜˜TÜžŒVPTÙÝL“Žš™NÕž•Mž’MÌÓY^˜TQ^–››MUÑÐÚKÓ‘”Œ[ÔMÊÓ]MÛÕÌQ˜ÕM\VP›T’ÞQ”RÓÒ“’ÝMŒšŠÖ˜VV˜–’™NÚ^•ÙRÐ–]ÍŽ^MÌžœ–Ž]UVRŽ›SÎ[ÙÖYŠÚÍMÚMSÒV]ØŽ
Ý•›ØÐŒ]MšLÓPÎœVY“ZÌÒÎ””JÎS›ÜžMT’ZÙZÌÙŽ]]TMžYžŒÕ]]šSÝP^›UZ\ÍL™›‘™•]œM‘˜KÑ]ÍNŽÌPØØŠÚTZXZž’ÝÝ‘ÜÜPÒÛŽS‘R”ÙP”Œ’ÙÙZ]žMXÕ]M–žQÖœ[ÔØŒÞTÛR\ÞRÑ•MR]Ø]–YQÛÍUMÓ[L]’LL™TÌZš”Ô‘]•ÜLRÛšPÙ[ØVX™›YM•Z’Í”™ÐR•V™ÌÝŽUSUÖR”JØÒšœŒžQ˜ÛX’Ð›RQU–Lœ™šYÝZŒPÙ’“ZÛKÕÓÌÚÓÖMžR™ÚÐŒœÕÐTL’ÛMšVš˜S™ËÝ‘Y•ÞPÜÕÙPÓQ[›ÌRÖ“\ÙØŒVŽPÜÍP™YÍÞÍM“LUÌ’SÚ˜˜›YÙ“Z™žU”Ñ”SÜMÛTYÔØšÌZ’QRÛÚÝ™Í•ÐÝXQ˜›^NT[ÒVÓÌ•Ù”ÑÔUXTN”“NšÕÍš]”]YÌQ’ÓN‘JÕÑ^Sš^ÍÜ]]QSMQÜÖ‘TM^Õ˜[ØšÜ[’TÐ•ÖÓœÑÊÓ[ÙÓœÒØS”YZLS˜]XRšŒÑÌœTÖÐÚ
Ô”LRÝ]™UØÛšÚÕLL[ÒQ•ÍÛÞKÖ™\Ð’Ñ‘LÐY^”‘‘M]UYÜÓ™ÛÒÐËÝ[”M\XZÔQ™ÜÌÖ^”ž›Í]\š–]œ\ÔÖLM‹ÐÝVÐ\L”•MTÜX›ŽP]žZ]U[[”ÙØQÛÊÑT’QÖ]Ñ”L•ÛÛ“ŽÚÕ\TžLQXPÜ‹Þ““ÝX]ÍÛ•ÎP‘YÜÜÛ›žŒÌžÙYØÔSØÖ’ŒÓ’^SU˜’ØÒ“–˜’R’™™QKÔÙRQÞœYÝMM˜U˜šœŠÐ]M’™ÚT™œZØ“ÞT‘ÜËØÜ[ZÝU^Ì^žžÛZÙÌØÞM”\Zš“[•Í“”L‘‘š–’XÔTŒ‘•RUÍØXUÑÜÚUÑŽ^LSœžÔ[ÊÖÜËÌÑÌžPÐV˜YQ‹Þ\›ÍÖÝÓÛÐSËÍŠÚS\ÌVÜŽÑ[QZ\Þ”Ü’ÙÙÌÌPVRœVTQUŽ˜Õ•Ü^œØ“ÙÚÍ[R]LZØRÎQÍÕVÖ]ÔU[ž[ÔÊÚYÝRRÓT•ZMÖ‘Þ™Œ›Þœš“]ÑÍN““ÕM“N]N\YÝÜNUPÔÙÍ–’[ÓÍÙQÐSÐÙ–R›PRÝ™™ÝNÔÕ•YÐVÔž”Þ”ÜÊÔÜ’ÚTŒ\™MÓXP›TÐÞš’ZÌÖRÜ’™ÛSÒZSÔÝÍÛULÙ™ŽÖZPÖ™ÑVš]Í˜Î[šÓŠÚVRÙUŒœNPU^ÎRSœÎ^ZURYSKÑY›žž‘œÝYMRÜ™š•YšÖÚXTU–Û”ÛÝž‘™Ü\ÛŒÛX\Ù™Þ’Ž
ÛU–ÌÍN\ŽQYš]›ÍÜS–R^œSÞXØUMÝYÐÝL\œŽX•Ö”–LUPÌLÝ
ÒŽÙR›™žŽLØ’Q]L\[ÌËÑPœ^U™ÔÜŒXÛXž”TYšMMÝž•Ü”[ZÞ˜ŒUÛZ”Ñ^Y›ÒÓ^Q’š“SŠÞ‹Ù‘Z›‘XÍNXÙ–]VMY’ÑPÓ^™ÝÙSÙÔM›ÌÚœŽTR[R•Ì›Ô^‹Ý”]^”^˜“˜ÐÌÖŽ\YÓœÎ™’ÍÓ^œÛÕœÝQ[ÕM”X™RS‘’ÛT^“ÕZYM›[Ý‘“ÔØTS[ZSÎQÐÑ•™ÎÎŠÒšJÐ˜ÝžM•Ñ
Ôš[™ZUÕ•ÓÞ[Ø”[NÚ[ÜÚšÓTØ’LÔ‹Þ›R›ÑŽÒÙ’›PÛÍŽ’Í”ÕLÒÙ”ÎP[L”Ù[‘ÕÍNLQ”Ü›ÔQQUÌ’ÝËÕUž’XÍÌÕÐXYÐ“ÚV“Ü[Ú–š›]Ú[YZÛ™Ôš”ÝÌ•ÞVÕ]ŠÚÌ\JÐ‘ÐÞR[VV˜ÑÌ•ÍÙSS[N”š[ÙÛ‘™T‘”Lš›MQÜZÜ]Ø]›TÝLL˜““Ñ‹ÕÌÓTXÙšÖNVÑÒŒMžÌQN[š“œ–›Õ”‘ÖQÕ[ŒÌQ“SL]LÌMT˜\‘•ÑR–QQÎÚSœ˜TÎ”]žMSœÛ’ÍÛ]MSS“ÔÑ‘ÛŠÛÖ”RÒVœÙU\ŠÚÕÞRÍÍVMšU™]^Rž[Ø•ŽœÛ›ZÔÖLšÛ\LÚU’]ÒY’ŽžÝÔ™XU“Z’žS\NVUPÌ“Pœ
ÑÍÚÚ˜ŠÍ[ÜSÐÙ“šÔÖ–šŒQ\Ø›TÔÚUVŒØ“[Öš’œÍ‘VUÝVÌZØRTÛ’\ÍZÓÞšU]ÍÝYžVNUQ™NÖ•ÓPÝÌÚZÍ™Œ[LZLYMYÑLÍÖšÝ•–˜LTŒ\QÜQ–TÕ–ÍÓ˜ÛÍ‹ÒŒXÜ•VJÚÕØ”ØSÖ˜“Û‘ÖŒœ’]R“ÖMÜ”^Ô”\™U”ÑÌ^X]UQÙQU\ÒZŒLÒZ’œÛžÌ‹ÚÖ\ŠÜ[TXÚ’YÞS™ž’MLÝLŒ“ÐÐ›ÒÎV[•TÐV\KÒÛNYVYÒUÚ“ÝÜÒÌQÝÜÊÓSÑ™•Ð•]˜Ûž]U^]›ŠÒÔÚ^Uœ^ZÝXÜÒÒ‹Ø“ÛUŠÕÛ’ÛR”˜ÝÌ”ÊÛÞÔ”[ÒÜZ™ŒTœMTLÎ–LÐ›[Û\SœÛ]XÝÜ“]Ô–RÙT]“•Õ›JÑÒœT”RÍÐ‘Y[MžJÔÐ•Üœ™Ü‘žšXšÝœSYQ™˜[ÚS˜Q˜Ü™Óž™X™SÜš–RËÒÓT^˜Û‘]V^•Ó›Õ–›ÕÒÍÔ\ÎKÑÒYY“”Ú‹ÙVY]JÑR’žŒ–˜œÖ\[ÜLœ\ÛÞ”Œ\\ŽX“ZÐÛËÓœÎ^RV›“Û”SÒ›ÞMZQÓYÓ–RÙÝTTÓžMÚTRž^^ÙÛLQÛ’”U”ÊÚÑœÜÖŒPÕÍLRNNžÎÛÖ\JÔž™’UÜ›Û]ÕMÕžRRZTœŽÝQ–‘RœžÑ“˜‘[™TÒ‘\ÝÚÌ–Lœ˜ÌÓ’UJÖŽ–XLLZ‹ØØÕ›Ô[M‘‘ÜšS“\T\““^^‘\SÝ‘Ó[˜QÕ˜M’ÐUÖ’ÐšYQU“UPÌ˜ZšœÛ“šÒXÖœQ›ZŠÛÔÛÒœÚ™U”RØ‘ÎQ‘ÔÕÙÙY‘ÚžŒP–’œUÔÍ’™ÛÞ’žœ˜VPŒÚÓ’Üœ–Õ›MÌ\S[^™RMŒMTVQPŽ[”ÌÑ•U”ÛMŒ’’ÛÜ™œXž]MÛÔÛÒMY›™UXRÌÚÌŒÎZœÜYVPÜÚž”“QM”Ð‘ÙÑÛYL]ÕÌ•Ñ[ÖRÝ“[VYP–TUÝÍžÙ™ÌËÐ]‘TÞ[ÔRÞ^\ÞËÕXRÓÙ”[˜Öž”•[\•Q›ÖÛLQžURÙ•™Q•LËÓÐ›TÜLÒÕMÒ”ÌÌ™ÛLÑÚÙ\R‘RRž’[‘NUTZM™ŒSSÒÞZNRÎÑÛ•Í”“‹ØšÚU“ÔYPœ^KÍQLŒ“ÕJÙQZ^™ÙQÕÞ˜ŠÕØZRÕÚØ‘^œÓÎ•QSÞN\ÙRMÖL[’ŽY
ÒÑÖ•]ÜÜRÑšLÓ›UÝM\šŒÒQ›ZÚXšÕ[ž‘ÕT‘NÍž”œ”SÑÍ˜œSM–˜S
ÔÝ\ÚØÑÐŒÌšZJÐ˜L‘JÖSQMŽRMšž˜˜PÑš–›™PÒ\YV˜‘Ž]SÑSÛØ–RJÜ\Z–š][šX[ÙNPÔÜÍKÚ‘ŽSÕÛ”™LQ^•^Ðœ˜MÖ‘V“™’‹ÜVSMÕÕÐVZLTÚÍ\\]ÜÛÍÍÜJÖšKÌT‘ÌÕ’ÎPYÓšÒÕ^\LËÚRPÚÒ‹ÔZYŒ“]JÖQÛÌÔÑÌœÛ]RÜÐNR˜Z‘“œ˜T‘ÚŒ’Ù]RÒT]LÍÐTÔÙÔ–ÙKÞUÚL[ÎÓ”ÒTÙ]˜YÛPÛ’QQÛ
Ý“ÑNQËÜ–^œÍÔ•™ÌšQÚ–•RNZ’žS\•Î’QŒ˜Ü^MÎž”ÎT]”KÓÔÝQNLÔRÓÑR˜œÍÚ[ÝÝNZÓ]ŒÒR•ÑœM\ST’^ŒÔš‘Ý]ŒÜL™Û‘ÑÓ“’Xš^PÐMVPL\ÚY]Ü‘™“T™Q[™Ýœ›ÜL]U\ŽÎMŒS‘PœŽØÒÞ]X\ÒÐYLÖ–Í˜Û]“ŒZ“–\ÑÝ]ÍÔÚÜŽ\Þ–TVšÜSÎMÑÝÓÕ[Ý’ÝT‘žNž‹ÒØÝÕTÒžU–LS^•UÍ™œÌ‘”QV^ššÕ˜ÜSVVTYØR[“ÚÓŒÙÜ\™Ó‘Q–XUÖVLU‘Õ\˜•LP[LÒSÔQ[ØÔ^MÚLÊÕ™Û’Ý”ÕÜURYž™›TL”šTM“ž[žŒNPL\L›ÚÜVKÔVÙœ”^’Ñ“ÐÙÌÙ”ŒžšÛLÍKÎSTLUQY“’ÞX‹ÖŒÚÊÌ–ŒP›œ™ÓÚN–œÌÞP™YÌÐÓQN]YÞØYÚKÒËÍ]ÛÚLÑžÒÕÛTÍ–^˜œ[R–ÑÓQÙSZ’ÖR^NÎÌY]ÓUÔ[Ì‘YY›Ù“ÝÐ]Ò›P^’S›Ø›™“YÓšœÍZÌÛŽVŒT\LNYÒ›ÓTžŒQLœÝ•ŒÜPRXÓÑYYÚ˜™[™QY’LVXÖÛÔžLÙT“ÒÜÜ]ÕÍUÙRLÒUÝQÖ]ÐÑŽ’Ø˜UŒÓŒÞ˜QÑÚX‘ÞQ›Q‘YÝYŒ˜JÎTXÝÒÐ˜VŒZ”RÐ–™œTÒQŒQQÒ•ØÙ“ÚSÎÍQŒÚŒ›QÜ”]ØØÛÝ\[™“œšÜSÚÐÑÚSÓšÞžž\“ÝÕÔN•ŽUÑJÙZMVÛÎP˜ÒÛQÔÝL“žUÐLÍÖ”Œ^‹ÐS’VŠÌQÐ^˜ŽRVŒŒ^”š™ZŒUÙ“žœžLÔËÔ“•œRÝY”Ù‹ÎJÕ‘P™ÕÚ•XÝ”ÕSM[\ÎMØ‘ÞSš’Þ[\Z[ÚY\\Ú•–]ÝÙ’ÐSX“]œÑŽ\SSÕÔ
ÝÛÎJÙšÚÜš[šNZN
Ò’–•ŽX™Y[Òœ›]T™YÙŒËÑšÜ™Ð‘ÒœÙ–SÚÍØ[XLS[™ÑÓÞYÎZÍÛMUÒÜQ‘ÍÍXšÞ[šÓÑS‘”[KÛXÒŽVSSŽL™šZUÚT™ZÜÎRØUQÖ‘ÑLYÍ’^RŽÜS^MÕ\‘ÍÓÕÑLÔQM[’œ^RÓÔLÖJÓ‘ÒYÌPÌÒ
ÕÑV’RÑŒ‘XMÍRÔÌÍšYTÛ”ØPKÐPÑ^KÜØÜTÞÍœZ‘NØRÌÚ›ÝUÖVTÖœÑLLÖU–œØ‹ÚÜ]›\ÖZS˜]ZÌÐ“ËÌU[“ÐœÑYÙœMUSÐ’[SS”ÚÙÒ]UTJÍQ•UV]“Û›UŒËÚ›RLœX™^šÖRÙYÐMÑØ•]ÛXÒÒÔÓ]ŠÕÐQM”PRÜRÞ]“\ÜX™ÛÓÚÝÔÒL™YÓJÒ‘ÑÔ[•YZŒSÑVÙ^™ÖUMÕÚÒ\ÕÎKÒÝ‘•’ÜMMÓÍÐ^S“Ñ‘ÛÑÑ•ÕžM]RVPÞ™[ŒÕQYÑÔ]™NXØÚP’Ô^™ÐÖQÚV“USZÚ]ÞÝS]UœØÎLVYMY•ÍžRÍÍœžMZÊØÑ“^˜ÙÍL›’\ÔRÓÖKÝN^LŽMÑÚ›LÍ’Ì‘QÒZS“šÑÚPÞVJÓM˜^R™YN]–V“ÓÜ”Ù”ÜÙÑ”ÛÛQÚYÐ’”
Ó
Ù‘ÖLÎQ’Ô\ÝÎX•RÊÌ•ÖÒ‹ÕPÛÒÛPMžÝ”Ñ”Q’ÔœŒ››\ËØŠÕ•Z”YÝÙ]ŽZLÙTÖ˜R”ZQVNÐœÐÓ]••UœÖ•\™TžšÐ›ÕÖ‘\“Y–[^R
ÑR‹Þ˜ÍÖ˜RšŒÞ‘Œ›Ô“•ÎQÐM[\Ü[“ÛL•œY•™ž]LR™QÍ‘QÑSšR•ËÌÍV›ÑÒ’Ð‘ØY”•UÜØ™]Ú
ÌÖ^ÔŒPËÞZÐÖLÛÙLÙQ\U˜‘ŽYSZÒ“\Î•XY•PÔ\[ÛLKÛÖŽÝÍ•QS\]ZÐÌ˜VÝ]›ÜVPÍT–KÌÑT›™ÖU[UÐÑV]^‹ÔL‘Z›’”Ý–ÙÌ]ÓYÓ[LMÞŠÓQVœÚØÔœÝÕŽÐÞZÖÎ[“TÕšÑSÛšZÔNNUŒ–Ö”Ú”]ÚÖ“ÑT›Õ]•ÌJÎ[™LQ™ÓL‘ÍØÝÙÖ^[NKÝM]ž”UM›”™Ô\•V“
Ú\NÖ“YÒ›•ÙÑPSP›UØ”YÕÛ‘œ“UR–ZÎÙÒ[ÑTÔQ’ŒÛÜ‘SÒL–TŽÚÚRQ›]“ÍÔšU]•”\TÐ™RZ•YZZ•
ÝTÑžKÑLÒÓ‘MÍÎ
ÍÔ™PM^YÑQÝÚÌ]ÞKÍ[MŒZÐÚ]ÝÚXZÜV[™ž˜Ð–‘Ö˜Î˜”[ÍÓšÓœœMZ–›QÒÛÜS–“ÔXÒZZPÌ\ÔšLŒÜ’Ò]–•ÔÕŠÜMŠÚUMšUÜ\RTUQÞTSZÓYÕÝÛÞ^›[ÍÍœœNZ•Í’Q•NŽQÐ–YÙŽŽMž\’ÝMÚ]Ø’UÚÛY‘ÚÞUšZX]TP]ÔQN˜ÚÛÑS™”ÓZÒ”Í›YU[[[Õ˜œLZÓ••]“ÚËÐS˜M\ÕÜ]ÒÍŒ›SÑV™ØÞšÎMÝNPšLšœÍŒÝ[ÜUÌQ“ÜœP\M•YZKÜÛ^KÚÊÌ“ÝP›QÖšÎ\UÒš‘[œœÜLÓ]•XÎ–S™™L‘ÔÍÚSÐ\‘”P”šP–Î^”ÕYËÐÍUÝ’“U–˜ÍÞ\YPŒS–ÝÍL^››N’ÙÌÛ‘’ŠÍUVU–Õ\Ñ‹ÕŒ˜‹Þ]ÔÖYÐTMMÛ•ÑÔœUQXÔRXQÔŒÊÓ‘•ÜÔÛZ’L›]˜Ô^šYÞ‘•ÝÊÕQÓ]–ÔœÊÞYÝÑÙÔ\SVUÒ™\^T–˜Ü\™ØÛšKÕUÓXÖSXÓ’TÓœ–ŽÎÍÞS›ÝPNVÚœÒ”ÎQœÔÙØUYÍ]VM™PQŒ•“JÓ‘Ì’’Ñ]“P˜MÛžVQÖšœ]•Úš^™”˜“Ü]•žRžž”ËÜÎÒYØÓ^Ž\š\ÚÎ]P]KÕÍLZRY[]\LP’[Ó”–ŒÜYXU™ÐŒ“ÕØš™M–U^•ÔVTVSQ•Ù™^]PMÊÌ™ÒPÖMLØ’“ØØSJÜU“Ð^\–’”RNÝNU˜‘Rœ–’\ÔKÒTž‘S^ÝÙÕžYXÔÔšÒ^ZŒ•™ÙŽ[M]LÔQžÚVU\STÖLœÚÌØ\[ÐŒÓLØØQÛÖT^ÕQÎ\™ÕS•MÛ›NSÕLšZ^Nš™ST”Ó‘Û’Ñ™–Z˜Ž‘ÖžŒÍÚPUÜ“Ý›VRY•^žUžÒÐYÝÔÎYÝšÑŒ[“Ô•Q]PT]‘œ\[RX\[ZÛ‘VžJÑÔÔž‘–ŒLPÓTÐ›]›–UÜÖXUÒ’[QXÌXV]ÌØ™‹ÑÞœZYÍÌÍÒšYÛŒÑ[Y^RP›ZÌÓÜÞZšŒÍØ^žÑŽQ›\ÕS\Pš“^•ØÑØÌÌXÛSL”YYÝNÌ”QœRÕÙM[VÐÐR[žŒ•]Ô˜ŒL“šS•™ØÍ˜ÜV™RÔ•‘™ÝžZ‘M™›TÒV“Ì•›–\Ì^šÚ’ÍÝ‘ÌÓZNM‘\]TÒÝZœ\[ÍP^œžÜÙžžšMXÚQÑRš’ÎÍ”œ^^R‘QÜš”Ü”‘ËÞŒÖLV›NMPÙP’ÐŠÖX^JÍŒÞ”Q]KÓ’[Œ‘^X›”YÙÔÓ
ÊÕQÎN]•ÛKÚ[ÎQžT‘LŒÙ˜Ù\ÙÞÌ˜[Œ›ŠÝœ]ÔZV˜ÝØR•Ô™RÒÑÒ•ÔL]ÊÝ[–š“^SÙÔÑš\Ø’•ÞNV™ÝÓZÌQSLÚÜÔÔ™‹ÍÌ\ÍÒŒSŽPÑÝ^œÝÚšR™JÍ–LÚ^U”U”’ËÞQ’–žT‘’˜ÚÔYŒTžS‘ŠØžSQÜšÞ]TÙÍ››Y’’\Y˜T
Ô›Ò•ÍÞ^›ÙžMUÚ’™ZXÓQ›šÝ‘–]VZŠÓÙ›žÐÞQLLÎ‘UÚRÛšRÓV˜Z\š”S’QÖ”XXÎ^“Q–ZŠØÍÝÖV”ÑÑ™’‘–˜UZŽNLÓœœ››ŒšÛ[Í\LÖÔ\Ñ\ÖŠÜÎMÜÔÓ\ž‘
ÖœÑ•Õ”
ÜÓÎ”Œ–šÝÕZPÓÖM›ÑÌ™PUZÛØZÍ˜YS•Q”ÔÚT˜”ÜŒÒ[™“Ø‘˜ÜPÞ’‘œŒ]›žSP“ž™M“TSÑTUšLŒTÓÛYŒÔ–œ]›ÜÞ”ŠÐÌX”ž›ÌÔ\ÍžŽ[˜ÌZ”Œ™ÝKÒZV[žÙÊÕ˜^ŽRSÔ[UÙMœQŠÚ”–XÜÚ’’ÕŒMQœ•^–TÙÚRÛœ˜ÚÞV’›ÖLØÓËÒœÌÌUÎRÜ\–›™KÚÙUÖMÊÕ–“›YÚŽš“•VÑMÒQ–ŠÙ“ÌÜ“ÕÍØ]“ÐÓ›[Mž‘ÑŒÙ^S–’]Ý›VÌÛÓÎL“ÐÓU‘›šËÊÞVUUÓ™›‘QÓ]•ÙÎV[ÛÔŽZÒYÔÐ\™’]YÒ•šÚØ”PRÑÍYSVŽ\™Þš’‘œÐØÒÕÌÔÌPÕÔRÛœÝœ™RÖSÖLžLM••‘ÎÔTRÐÙ˜TÑ“ÍœMÞØÒÒŠÌÕÖRÎ^•JÐKÒ‘ÓÔRžRZÙž^‘S–MÐ–žTMQÚœÛZX‘Ð–M[šVJÌR˜JÝ“XÝÜKÐ’–šÙLPÙ™Ð]ž
Ò^JÖšÎÝLžžÑÝ][ÍÐRÐÝÙ™ÔQT‘ÎMœÛÛŠÕMVR•ÙœŽSXPÌÍÒŒØÍÓœÐŒÚž^^Z›Q™’Í”“MËËÙžœÌ‘ØŒTÞ‘ÎUœT–Í“RYTÞKÛUŠÓÌ“YT\ÛÛYÔËÚœ]Ô‘ÍÍL›ŒQXÝTÍÚ’œÍ”žÞÔÍ™PÝ–žšÔ]–Ø–›”˜ÖSÒ]›ÎSTÙS\[•Ùš
ÚYŠÚÔ[JÙ’T‘Œ˜N\ØÒ‘MVY˜ÑXRYSÌÎÌKÊÙÊÓÙ[Ù’M[ÞSÌ^šXÔS]R\X–›››™TÖMÌÖZ•›žš^žTR™[–›‹ÛÞ’•YYÌMSU˜“ÝMÞŠÜRX™Œ\ËÝR\Û]Þ\”XUXŒLÛ”PØœ]ÞQ”ZÑÚ›”LÛÔVZœ“™ZŽ\RP•Î[MZY‹ÚÙ‘’QÑ“ÊÚTÔ–]ÝŒNYSÙÎLÚÛTœUYÝÜ
ØÝËÕXŒUšVZUÚØØÍQž‘T[ÞÍQYÔ‘™LÌURÐY\XUN’ÚXMT•]ÝÞMÔÑ•ÐQSLÒTTZÛÙÒ^NMUSRØÍÖN\›QTÍ^X\Ø”ÌVXÛNÞ‘TÛ[ÌSÕ‹Ð“X›šÓÜY\ÕPÛÚŒ’Ùš•ÚÒVZ\™ÌPQÑ[’VYÚNXÜJÎZ]ÞÙÛ™Ú•ÒÎN\ÍJÜ˜R‘X™•Ù^ŒŒQT’TœÝšÑRZ’Ý]“UZžœ[Þ’Ô‹ÎVœUZÞX”›ZRÖ^ÐØR[\ÞXÛÎMÑÛLX\‘ÕžŒÙŽUL“ŒSUXÒÙZŠÐœÜLMLÙ˜TÔTÜÝÎ^RÎž•’ÕTÖ[’NTTVZLLÕYÔ’ÓMÝÓÒÓÓš‘Ó’šÑN\ÜZ–^ZMŒ’ÑÒžTNLUŒÜÔ’Y–SŒŒZŒ›ÚZÔ\–ZR‘Ú[NN\š•ZÛÔT™UŠØ”ÓÕ•ŒÛÌ›ÎQPUÙ[ÖMŒN]Ñ\“S™‹ÐÓÙQ‘YÐÞRÑZÔT“Í]Ü•”U–XŽ]š”ZLš“ÝUÔRÜTÜ™Z^[\›X™ÍTÚ’SMÞNU›QÙU\•ÐÖÝ^MÜ™ÍÝÓXÛŒÜX˜ULMÙ‘ÓÕ”KÚÑUÒ’YM™ÒNUÛœ[Ú“YT[œS˜Ò•Œ‘[œZÌÕÌšÚÜÒÞ™ÝÜÒU’™RSRSœ^”ÒÐžÒ‘ÌÔØÑ–[QLLTÛJÞZT‘•ÎTÑÔžR•YR\ÙÎÖŒšœŽ‘SÚJÌ–›ËÝUÝ‘ØŒ]’RYœØ”JÌ^\ÒZRÌÍ•MÙ™R’ÛÌÕÌÍ‘ÕÒNRÕ‹ÛZ›QMÛ”•Ü[Ó‘‘]”[’VKÕÜKÒXÍ“ÌŒÝYTÛYšŽ›X”ZLŒÐÎX“ÑÖ’‹Ò•]ÛZÐÕ–œŒÐSÑUÖ”Z•’™V’‘XT[]ÞÔÍ[[‘ŒXU‘ŠÝN–™Sš›S˜S‹ÙT˜[•ÚS\M\[Ð‘MÌÝÛ]ÕUÒSÞ[˜’›Y‘ÝÜÐÊÐØÔM”ÛY™ÔŽÒ–›S›ZÖR•Ü–ÔœÊÒY‘•ÚYÕžV[ÔÞUU’Ù[Ñ\LÓ\Ñ˜ZÑ™YL›U™Ñž’‹ÕÒÕÚNLQÔÕXËÑQ™ŒÞÑœRÙÔÛX[P›žNSÜKÔMÜËÔRÛ‘ÍÝ[œXÐÍZÝ[Í“KÕœÕÜÝ•SÑÓ–XÑÓÔ’\TU™^•RÖQÌ‹Ô”ÐJÍUÛSŒLÓVÞPžLÜœ•Ü›˜‹ÚÕLÓRÓŒœÞTŽ“SZ‘ŒËØQ‘^‘[ÊËÔÖP˜ÎTÌ^VÛ”žÕŒÓÞQžXŽÌÓÖN•ŠÍV‹ÊÜV”’ÚQÛÔ[ŠÝÑ–“Ú“ÙÔ‘ŽMÚŒžŒž™U\MYZÖT^ÐÜÖ‹ØVYLÎ’ÜKØXÛ‘ÔÑU\Ó‘›RŒÛ“Œ˜SÙÓÜMÛ›ÎLÌ•ÙÕÚPJÔRœVSŒÒÓRU•[[QÞÞžÛ‹Ò\’MšPÎŽÝÍ›[ÒÓ›ÎYPRUTÞÚ™ž˜XYÌZÌ•Ñ\š›ÍSÑLŒÜœ[TUÜÍÖMZUÙœÝÖ[ÓQÙ]˜Y›ÓNS\›RØ‘Õ‘QNR›Þ™ZšSZ\[™SÌÎSŠÙÒL”]˜›ÜÍÝ’TL•VRMMXËÎÛÓÌ›ÚZPU•ÎZ[T™QÜÐM
ÒŠÌÌ]šÔ™Ó›MÞ‹Ö[VP’ËÕÍŒUM“‘Ô^MŽÌMÍP•ÓÍÌ–‘ZÕXÑ]TÒŽKÕËØÔTÓ]Q–“[RYKÞRZ”KËÛ•ZÔ\[™RÑU”QÛ‘Lš‘Ò˜ŒÚ“Y][™QP‹ÒŠÕÒÛÝœÛ›ÚSÎž^SZÓ‘ØŽL[TRÕÛ•˜PŒQÔÌŒYTÒŒLÍŒSž”Þ‹ÝŒÌ^\Y^TÒY’šÊÚÚSÒÕØXÍœ’R\ÓTÙM[“PÖŽÒÔ‘RÒUÖŒÙJÜ]]Þ’œXÒ‘ÚKÛÝ\U[YT’Ý›UÛ’ÚÖYYÝÌœž‘ÛÑŒÛ[ÛÒ“KÛœ”›\“Þ›“ZØŒÛS›œÌÊÎPÝŒ–”šRÔÒÑ]ÝÓ‘˜ÍXQ^Ì’ÛÔV]ÚÛžY•‘ŠÖ˜^RØØšœ^R”\QÓUÑSZ–YÝUÛÑÛÞRPÕÖYLž”™ŠÕÑØœPŒS\–•SÙ’›S•PÕZRV’ÙR^ÒJÙTÒYŒÛVLUQ•M”VLUØ^]XÙÒT‘YÞŠÑÐ™ÔPTÛÑ’™ÔÌ”[ÖSPX‘ÔØ‘’PQ›]ÞZ•ZŠËÔÜL“^žUZ“\Þ]\ØSÎ[U[ÐZ”ÑLRÔÛLTSM–TSŽ\SÓÒ•’ÕÙÙÖ\‘JÕV‘Û–ÝÕÑ]T›”ÛSL^•RÖ\ÍÓRÛÞT–XMÞ\ž]‘LÍÑžMÎYÕÛÐM“^QX“SL™ŠÍTVQÙÕÍ•M–S\^Z“MÛTNR›ÛZ”P”•Ž\[ØRYLÝSžPÐ“\SÝÍX]Ó^]”[QLÕQÚUÓ]X’šM›Û[ØÕNŽ›‘^JÕšÜU\ÓÚÝUÜÒšÖYJÓSR”Þ^™ÍžÓÎKÝ]
ÞØR[^[ÚÌÒTX]’ÕU”ŽN^‹ÔÕYŒ^YMXÞNŠÎ‘ÑUÕ”ÚL[]ÓŽ”ÒQQ•ÐÌØNSPÌV”MÐšKÕ\“‘”PZVSUÜ”ž“LÎS™[Ö[ÒÙÌUM‘Þœ
ÚLZXÔÕ˜[M[ÙÔ•ŒLV˜X•ÔÌSÒŽ™š›•“ÚŒÛÝ^Y]SÚžŒSMQÝÌËÛÞÞLœÛÕ^Yž™’R“Ž•XXUU‹ÌÚ™ÚÔJÔT[ÜTÜX[QØÛÕž”•˜XœŽLšÒÝÛL–LÙÊÕÚÑTÜÐXšÝ^•Ð]LNTTÔÌ‹ÜXRÒŒSšÌ™ÚÍ•’[RžŒ–M‘MÕPTœZÜÕU’Ò‘“”“’JÖNÛÝ“ÎZØ™[Y™ÑÚXŒÓRZÕÕ]‹ÍÒÎY“‘”–™QÒ‘V“œœ“›USVRÝ‘Ý“QNÔSÖÓQLÐÖ’Þœœ
ÛÕÒÜ^\ÐÓÕÙŽYV]ž”]ÖTÖ“N]œXÚYÓšÛNRšÐ[ZUNULÜÑ[RRT˜›˜Ò”š‘ËÜÑÜTLNZÒ\^PØSÖ™ÕÛS‘•››ÝØ–ŒÞ\’Íž”‘PT‘ÑXÙUÚXTÒ\™‘ÖQPÝ\\›RT\•PÕZZQ”Ú™[™]“ÒÚQÒÔL›ÑR“ÚÛLT’š›ÒÝ^’žRÐ”’KÐYXÐÎ]]–MŽRX˜RœNL‘V[’“‘MZÑY\U“Œ›˜ÚÌØUUMÐMV^S’šÍÝÝËÝž”’MØÐÝX™Ü
ÌŠÝZšÐPŒÔTYLMŠÐUVZ]ŒL››–SP”ÔžŒÓÐžZÛÜÌ‘LÒËÕ›ØÍLÌÐ^UXžVXQRšÕ”QS™Ûž˜’ŽPÔÓÖMÍMœ‘R““•ÚÓÒM“ÓØ]ÜYTÐ’Û‘šŽ™ÚËÐÚ“ÙLÒ˜“ÌšÛ–™‘]˜šPŒÛMÎYÍÕŒ‘ÍÚ™ÐÚRŠÑMœLJÜÖ‹Ñ˜Œž’Û–ŒŒÍ]
Ò^MVŽN\RÞ–œ^ž]KÔ”MÌÛ˜RÞ’ÞÔÌÑÛ™P’Úš˜TØ[™Ø“ÍQ“™Ö\[ÌÞ–ØÜUÑÔ[“‘ÌZPÒY“ÑÚÐ”–TšTZ“–UÞVRÛ”ÌÍ™YÑ™LÌÍØ–[–]LSÛ’]N[MØÜYÕœ“]‘RŽ[PUÜ^Z˜SUÛšœšÙØÍŒÚžŒËÙÍNP”ÑÓ”•Í\XNYÌ•ÚRÔTÚËÑR^ŠÙÙÜÔÎZ’ÕJÙ™ÍXÛÝÍÍ™ŠÑ”Ú^œ›‹ÜNSQÚÜÕŠÒNXXQÌÑž•ÒS”š˜MÜ˜UÝ–MTÙÕŒÙÌž\’•]ÌÒX›Þ’ÔÓÝÚÕÚ•L]˜ŒÍÚSšV•Î[ÍÕÞZLZYÝœU‘ÚÛ[’ÓVÐÍXM\QÞ”™TSÚÍP™Œ“ÜÙL’]™ÑMÐSM[’ÛÔÛÖSÍJÔ\ÞœÎœ]Û˜‘\Úœ™ËÙÛžŽ^QÚQŒÕÑŒÑØ”Ò›˜NÑRÜ]Ñ^VXVNLNÑœMÓSRÝ”\
ÍM\SÖ]Þ‘Q^œ›Ù•^”NRÌ‘MÝÝž\\ZUœ“ÜÙUÛÌYÊÛ•›SS™ZÛÓ[R
ÓÛÑUÓÑšÓL”TÒÌ”QNMÙY’Ô”‘ÝQNYÖ‘ÙÔÔÔÍ^RTNR“NLÛÞ“ÔKÚØ‘•QÑ’TÒÝ™ÕÒX˜QŽ˜‘ÒT–]QZÕÑÚT]‘ÝT“Ø˜MŒÍÓ]˜“ÝÖ’M˜YÚUŒÍ™ÕÚ^›SUØR›ÛYšÛUPœ‹ÓPÛNÝPØN
Ý›ÝÛ˜N]LZ[Û›š–˜MŒ•UYS“SÑ’œPŒØ˜œLËËÑQ[”^Ð^R•ŒUR’ÐKÙNÙÐ[VLÚV’šU“ŒÌL™ÒŒ[ÖJÌRÚÍÚœTÕžSÚœÍU\Ì•’Ö’X–’ÖÔ]ÍÝTŒSÔšÓÝ
ØL‹ÝÕÒ›NYÝžYÞQ›•š^ÌÍÛRš”YZÑÐ˜SšZÌ˜œÜÔ”“PRULÍÓ•LÌ[“Ö’ÖVY]ŒLŽÌ•’ÛY–’RÜØ^™ØØÙÌS“’Ž]]Ô‘UÒÜÒÕÒ”^ÒÛ[\Ô’[^ŽNL“ÖŒšSÊÑUÌ˜Òž™ZÐ•ÞSTÝQXÍ]Ø]ŽNN”ZŒÑVL˜ÜËÚÖS”žUQÜ•ÒÓT\S˜Õ‘ÍPS[Y[MšÑ”šYœŒKÜR•YŒ
Ì]’–ÍVU‘ÑLÖŽP]›ÔRØNSÚJÙVŒZ‘ÌÒÔÖTRÖTÎRXÚÙÞRYMQÜÚM•T]œÖT–ËÐŽ^UL\ÍÊÙÞŒŽVY‘Ü^UXMRžŒ[Q^ÝžœÌ’QŽSMUÕ›ZÔ•ÍMQZS™ÖÙLÑÌš[ž[MÌ˜ÕQŽY’Ñ™ÞÝ‹ÚUKÜM\ŽÞL’ZÌÙ\ÔUÊÑ[ÖMLXÍÓT’ÒÞ^ÑÒPÍTÎTÖTS™ÕÞ[™Ó–šÑËÚLÝÑÊÙ›ÞY’\ÚÎ‘Î]Õ]ŽNÎV]ÎRËÞZÔ]Þ”ÎYZ]ÊÓÜÔÚœŒ›ÙZ‘ž“ZÍS˜TÒRÍQV”Ô‹ÌÛXKÌš^˜ÌSÚ^šRÎSÌ‘–ŒÍ”]TÓ’Ó^MÜÐš•“ZÖŽTÐPÚ–JÕMž”]ÜÓ
Óš“RœNX’ÚYÑ”œÛ’”LÐÞ–’R˜ŒÙ“MŠÛÞ[TÚSÚY‘›š‹Ð’ÙÕžYËÑLŒ–Ò•›šÜÝ•Ž–KÞ–ŽU˜ÜYM”šYÓÚ”–X–TJÌX[šNU’Ž•\RÌ–P“ÖRšÌ“ŒÒÛ›Üš[\ZÌžRÚ\ÙÒŒSTÝR˜œMÛ‘ÝœÕSSX“ÔÐTPTžÍš™Ô^SYQÌÑœ\™Z’ËÖ\˜JÐÙ”ËÔSŠÝ”‘[LTLXÑÕ[Q––TžLV[Q”ŒP\ØS›œŠÕUUÙ]ž’ŒM™ÐÑUÓÛ‘Í]‘šXV[šÚSY
ÒÞ™QœÌ’Z‘˜XÍ‘”‘ÙÍ’^“ØVMÙ^Ù‘]•ÔQNMN^ØÑÚž”ÕQT]’L“ŽXÚŒ’KÌÙ“Ò›šL\žšÛZ’T^UŒÞŒÞÛQÝÙ›JÜÙÚÑ]S›L\•XV–XÜXQÞ[ž”S’žRVZY•“
Ú[YÍXZ“PÎM™SÍÞ”–LšLNT”˜›ÛÌÒ”ÙXVÒÑRš\™ÚŽÌ‘Ì•˜’XÊÙ[RRÙ–’š^^Z•ÙÓZXÍŒ[šZÍQ“ÑQÔÑ”Ñ’ŒŽ]ÒÔÌœ˜LUÍQÜ’S–Úœ[ZÔSTLÝÖÒSÚž””JÛ]”“Û\[Ü“ØÞTNRPRŠÛÍËÛ›
Î[U[^]ž\]•›UTÑLÓL•“XÚZ›Ù’ÛÌÛ[RŽÓÓU\‘Ö\ÍÞØYÔY\
Ò‘ÕMÛÕ‘M‘[Ò‹Ö˜Ì•ÜÍÙÑM]”“Ò”›MÓLžZš•™Ó™ÒÌÎ^\›“NRÕšR^QÑËÊÛ[œR’ÔÜŒÒTÚ]’Õ–L•Ó^YŒ“’NÌQS“•ÒÍ“’NÍ”šÌNUÕØLšÝ›RVÍÑÌÒ’šPMÓÝ‘ÚT“YZËÙÞœšÞSXY”X“œVV”ÙÔ\Ð’LØÐ[ÒÍÛÌ”ÞVŽœÝ]]Î”Ì™LØŽÍ‘NÕÛJÒ\’ÑMRÖËÑÑ‘ÌYÒRÌP\ÍØTQÌÌ]LÞMXSPÜ‘•LŠÒQÍŽUÊÕ™ÖYUNÔUÎQYSÛÒÕÞML”S“ŽSŒ\”ÑYÍ[MžZÔÎXRÞVU”ÕSØÚ’‘YZYÝ™ÙTÙ˜ŽQQYØ[LÌX]QMM^–VT”ÌML[\ÊÍYYÙÌ›–KÑKÔUÑ›ÚÑ’SÍÚ[ÌUšÌX’\[ÝÝ’ËÛÒÜ]ÔÒ’ŒZ˜ÔÛURÖœÝZÚQÛUQSž–Ù\[ÓÕœQU˜Í“Ñ™QS“[^–XMPLQÚU^TÚÔQ^‘S™P™S–]S“›Û\Lš”ÓR›š\ÔÝY[[Õ’™T\ž]Ý™]ÍY–]ÚUZ]^Ü
Ú‘œž\’ÙÚ’”KÕØTY”ÌÞšYÔLÌØ”XM‘Ø[Ý”Ì‹Ý™œÑQÙÙÚÐPÐØÞRQM““”ÓYÑžUÓ’ŒÖ˜Þ]ÑžVÎÚÎÛ\‘ÓšÝ‹ÓÞL•Û˜•[LÝŠÝ˜ÙÜ™TÛXÖMÜžÌ‘•ÛšUœLšœ•ÌšMÝYÍUSÖU›UžUÌÜUYÐLÌQœÌ›LÍUTÝÝ’ÒÌÑ˜™M”MŠÞUSQM”ÙT˜ÛQÙ”‘
Ñ•”ÚŒÐ”ÔUÒÜÛU^”MÞ”šÓŽTšÍTVœÎX•MÓÙÔLUY\Ö“•ž[^UÐÚÚL›Ó˜T”šžT\žZŒÍÔ]Y›Y\ÝNœÔUÙšYœ]Ù˜’Ú”Øš[ÑØ”Õ›\V•LRœžS‘”š”ÊÕ”ÕLR’ŒN\Ù™Ñ“ÒÓM–’]ŽRZšÐÙÐ˜–žVXØSžžŒQ\Ý““YYM•Ì–Ó^L‹ÐÑ˜Œ[[ÖÌ•œÌÊÚMQŒšžš›[ÑŒÌÖÓ\”–YÑÞ”ÝÍ›“SR’[RRš›YÎ›™LUU’ZÒU‘Ž“•^Œ‘YR[^‹ÜZÞØ•“š™YT‹ÓÑLLNL”Ù”X’QS‘[\^]šÝ˜[ŒÍÐÜNÛ‘Ó\UZ›ÊÎZÝžÒ™R‘Ô•[™NÎ‘ÑÚ›‘ÍSžÔÕÙ]’–MRYÐœ™PÐÜ‹ØPR’˜”ÓL‘MšM]˜ÍYÝœÑNTÜžTZÞQMÍØÜ‘ÑQTÔÌÐÞLT’›S“ÍšÍ“YPÔYÚžYSRÓ[Í’NZL‘
ÑRR\MÒVZÕœÍUÍÒLŒšŒÚÙX\Ô^[œ[Õ[‘ÓÖ[Û–LÊÚÍSÎQÎXÖ•\Û\ÚœRØXÓŒZÐÓŒ[ØSXÍÞšŠÒšZ‘^˜ÍÍLÝZ™“ÔÙÓ”›’’ZVQŠÓžÚÊÍÑRÒ–MLZËÌQ˜‘ÑXÝZš“œÕL‹Õ“\ž‘Œ•^MÝÍS“ØV™[ŒšQVÝÑÝ”ZR˜ÝÌZSZ
ÚQÞ[ÖVJÔÖÜL™ZÜQPÞ’“RÒPŒ‘”TÐVœ“ŒÔÔKÒYÛX[ÛJÖ[ÜS‹ÓÛRNž“ÚKÔÞQ‹ÍQÛŽT˜ÍRULÕ•ZšÓÔœMQ™•Ñ”ÜÍT“MÚ’ÕVÖZÓRSŒ\•TÔÞ^›’R\ÖMÜÕM˜Î^”Q\PÛ•ÖUÒM]ØQ[ÊÖYL”LLQÌŒœTR[QÒœ“LT’ÙLMÚŒ’S•ÊÒÔš“RÕÜÒšÓÑÓ”ÛNLLÜÜZÝ“ÙšÍ^•LTŠØÔÚÛÍ”œÎ”RZ\ZÚÐ‹ÖRÞNPœ”’’”ÖZNR••ÑTšZÕLZ–ÝUÓØLžQR^“‘šÒMMœM˜ÜÔ•QÒ\˜Ù›JÛS–LÐŽLKÝUUÐÑÜÚÓ‹Ö“M˜™ÒVŒ[UÌÌYV][ÖŠËÚZØÍ‹ÌŠÛ\ÔQÍžL\Z’™T‘ž]UXTÍ‹Î\VÌššZ’Ô”Ü”^YZR›‘ŠÎT˜\^Ü]SÑY‘ÖY\N‘ÙQœÔZ^]ŒØÙ”Vš[“ÓRÞ˜YœYSÒ›ÜÜÞXPÜ’‘’ÙXŽN[Í\Ó˜XZšUÍ‘ËÙÜT[ÕNYš[Û•V˜Ó”\[Œ˜˜ÙRŽVU•ššPÙUMÜÔV˜ÍTTZŒ‹Ø\ÚŽ\‘U’œS‘MÓ^‘šU’
ÕŠÛÑL]\N“’ZUNX]˜VžÎšÕPÑM’Ž›SÕÚÞÙ“ÊÓ™›^YÐŒMÖ˜ž™žQ–œÛš–VUØÝÔÍZ^˜–Z]UL•Ûž\Õ\–ÛÛÝ›ÞLÛU˜[ÓÞ‹ÕQ’˜Î™Û“ÔÙÖ–^^ÊÛžYŠÙÐ]SŒYÜ›šÛ•˜MœXUÞUYÐÜÌ™XYU˜^ZÓÖžÌNYÖ”ÔZ•ÌÓ[X™™ÖÐžQ\‘ÖMÚ[˜ÍÜPÔN^ÞÙŽZÝ\YLTX‹Ó–MÜX‹ÔMQL•NœžKÚÞ‘‘ÓÔL™]ULž”šÔ]ž[RŒ^’[RÝ[ZVZ^[^œV‘‘˜ŠÜÖYÍ›UœÊÝÙT‘NKÓÛœÚ›ÙØZ^[‘–“^ÍÔR’ŽÜY™‘Õ™‹Ü‹Î\T•˜ÎLŠÓš[ÞTYÖYÙN\[‘TšLQZž’ÔŠÖ‘QÞ”YÍ›”ŒXÛ[RŠÚM’ØTÚV•Ûž˜]•ÚL›ÝÕMZL“ÔZœ”“Ø“‘”]PÙ™ÐÍX™XTÒMÛNQÓX’ššXNLœÝYU[˜žUT‘]KÙSÙLÕž]ÌÕ‘[ÎTY˜VÌ[’‘Y”\ÛJÌ^PÕÝ˜ž™•›Ø”\P˜R‘ØU‹ÖNXžZÎ\’”[™RÙPT˜S˜Qž–VŒQ‘›Y[]“ÖÎSXØ•MP•“\ÍžžS[ÛØÔÚÒUN]VMTLÚÞŽQ“•Ù›LÒ•“SLSÖ”^XÍÞ][ŽÕ”•VSœ[LÙÔ••[LŒZÎLÎZÔÜRœÔ’”L[›ÛÑÎ’›™UÛQÕTÞTN]Õ‘”ÙRØŒYMÚ“Q”VUÛ›ÑÔ‘Î[TÍKÊÒU^LUÙÖXU‘ÚØR‘•]PÑšŽÐ•LUÚÑŒSÓ‘Ž
ÑÍ•ŽÌÊÒLÒÕÒÑL–XÞVŽZTL^KÞŒR™Ú]^ÖXÝ”ŒÔU”T\““ÓTÓÜMŒ“KÍÔ”™\XYœY˜‹ØÎUÌ”[ÙšÕ^ŒTÕ’›Ú‘œ“]‘–“ÝPÒL˜TMŒÜXÔœ•ÍV’žQR’YMŽÍŒQœÛ[SÑ^œTÚMÔQKÝÖÝ
ËÙÒ‘––ÚŽRËÕÙLLÞœ›TÚ›–ÒTÕÙ›ÔÍÑŒÑÚÑP’‘^LÐÞÓÖŠÓžUÕ•“Q”Ôž“Ü]˜U‘Ý\RÕš™“’œTÛÛÌÒMS
ÊÜYšU”TMÕQU›“ÙØ˜ÌR\•VU–SÛÍÕŽZQTÔÔ›ZÖžQ‘›[‘[‘ÓžÌYÚ–”Ò‘Ú””ÔUÕ™“Ó”ÊÕRÞ™žVÜÒLSšÍÐKÝÐÌNÑ^\‘‹Ý•Ý‹ÓšÚœNR‘UÔŒRÒÙ““‘ÑØÑšØTÜT^Q[•LUÕ\šZÛšÔšÚ˜\LšV[ž]ÒÓXVRRTÑ[‘ÞX˜™VXÌÚÜYÕRÑM^ŽNŠÔ
Ú’^•šLÚ˜ÙŒŽ^\ÔŽ”œÓNUÐÍMPÌU˜ÌQ’Œ\KÌÓÝÛ“^œ’ž\[ZŒKÌ–žY]X“L’›ÜÙ[Y‘œ•Ò]R™Ø‹Ø“ÌÔÔLZÔŒLYœZ‘ÓÐ‘Ð›ÒŒTV”“]ÝÝÙN[Z›ÎRœÑÎØ^Ø•Ò\]šZ]ÖTÍPÍ’QŒRYR•›\–YÑ›QÍLÙJËÐLÒQœ˜[^M]•
ÚV“ÒÓUR’šššRLš”Sš]M”ÍœÚY™YÚ\›]™ÌÛš™[MZÝX[ÌP”ÛKÜ’ÒšÓNLØ”ÌÜV’œQ[Ý‹ÔT”™Ú^L–ŒÞÍÐÑ•N\ÍÝÊÒ”ÔU[ÙÌœ•›R˜YÞÛ”VVZœQT\ÍRŒÚ–’Ô’M™M˜Ù–L™ÐÜŽMYÒ••‘R–•’ÔYZ™QÌ\ž^ŒÐÒÚÓ^R‹ÍÓ‘\›^]MÐUTSÍMÛÖMšÒMSÓY›šVÕÎÔœ]MœQÍÞMM[Ý˜ž›NPšÞ˜Û“›UYVQTX[ŒÖšÎT™Ò‘–š‘ÐS˜RJÛÒ›Ô™ZÑZM••[RÜUÙLKÎUÙÚœR][TÓY‘ÜÌT
Ö˜V›““ÜÚ•ÌžSž”–žœTÓÚÜŒ’KÖ“ZÖŽXšÑÖ›ZÑU“UJÕ˜ÙÒÚ‘UZÕÓÖ›ÔŒÍVMJÌ[Ó“˜˜R\\š‘X[žŽœØ–YËÚ]KÕ”^LÝY›™Ú”L˜™MÌ’ÓQÍ\Ö[U]ÙÞN^Z[šŒ”Œ‹ÑR”ÎÝ‘‘YT˜ÚZÚŒÎ‹ÌÓØÎšZØœQÝPÌÝÞ\•ØYÓ˜™™]–žPRÐ‘“[Í”Í^ZÑ•L
ÍšÌ”SÔZÍQ–“›Û’^›œÔšPÑPÚVZÚÛØÍœ‹Þ‘L•ÙÜ”Ý’ŽU‹ÖL]œÜ’ÖTÎQÙÞSL–›ÖSÓÜ›LÍÓÍ‘LTœ^•\ØÜÔšÕÌÍÐš\\ÛZLYZŽMT^ššPX‘ËÌSÚ‹Û‹ÕLTÒTÛØÔ”›ÊÔÛ‘šÝXÍT•žÑQÚKÍÔTQš“ÖÐ•MÒX\TÖ”ÍÊÛNSÙYžœ™ÐÔÐ’Q˜ÕNNÔ˜žULUY‘™“ŒUTY•ÝQZVÚŒÍ‘TV\›LÞ›™ZSŠÙ‘››Qš”[JÕÓÔÐ’ÖZÛQ’\š[œÑ›Óž™˜Ýš‘–VÝ[ÝÓÑžRŒ\UZÙ”™ÙSÚ“Y™Ž]Z^ŽTJÐŒÚNÛ”MØPP[ÍM˜UÖZYLU›\Ø™“RS‘‘Z•ÔÍYT–žÑ“\ZœL“ZžZR™ÓNLÜ›ÒÔÕœŠÝÌÌÒ]S^L\U][‹Ú[›YRÍR]VZÖT˜ZZÓX›[ÐUš•L]QRŒSLØœÑ‘ÖœÙœÔ““›[ŽNJØÝØÔŒUZŒÎT’Ü[Ó›Y”˜š–[ÍZ–“U“•QRJÖZÌSÛŒÙšØÌY–\T’\Û“™ÕNÚ›ZšM
Ð™ÚÞ“[Y‘Ý’VQžÛŒ™Ñ]˜]Ì•\Ò‘U–žYSŒÛQÜUØÜÖLZÕQ™JÕÚšÓÝ]TØÌ’Œ•ÕUÔM˜Î]ÝšØZŒËÚœTÐMPžP”PžŒYSM’Ö‹Õ›’Ò›ÒU[ÍØ‘’™XÕ›Ó–SÔQSÐÞÚœÚÝXÔ‘’MšÜU˜U™[ÕÞVV‹ÝPÌRØSÓLŒÝ‘SÔÐœ’\NTV[ÞÍÑZTÐMÔÐ››TŠÜ’œ˜ÚÌÒ‹Õ™[ÜÍ[TÎ\
ÚQ›\“LÎVRÍ[ÙMÒœÞÕL•Û”ÜšJØQšŒÔÙÑÌTÒ^ž“SXPÙ\˜ÔUÙLÙšÑÕÔ”R™œTVX‘ÝÔQ^ÍÓÔ‘Y\˜]\YŽQÕÖ•Ûš]ZžSÜÓX˜ŽÜÜL[ÖÝŽUSQÒLÍ•‘ÙMÜœ”ÖZžššÎSÎZ]šMž‘™XS™ÒÞ–T
ÒšRÎZPØÔŒ“KÐ’ÒJÚÒÕÌœÍZšÌšM™TŽÛQX›’LZYMŒÜŽ”ÚZ‹ÝÓÚV™N˜œZÝÖQ–QÐQÓÜL“SØ[NÝXRÛ‘šRŠÝXÌÍÌŒŒÊÚNR]ÖM’•ÜUÕÔKÌ•SÓQÓšœXX”’Ì“Ò›ÚLZÝ”PÓÕVY•ÍÌÛ’Ù›ÛÝÒ^Y[Tœ]V‘Z˜XTÒTL™›Õ™Q›S^ZŽRØ›^^XYœY“Z‘\
ÝY^œ”šXœUÛ•]ÚÝ›ZZÐÕ›Ô“š•ÑœÍ““R[ZYURÒYRž[ÑU[ÑZÛœ™^NUÛ‘™YØ’Ü’•V^›ÍÔ™U\ÌÍÛ˜ÑØŠÔPSÕMMÙ›M’Œ’”^Uš˜Õ‘VËÞMš›Œ\^[[Z‹Ò“ÍÎLZUX“ÚÙ^ž\RVTÑÎLMÍQÛŽ\Ø˜]ÚÎLZ–[MœØQÛÌJËÎTÎÐÚ‘YžRZÍÙÚRÚ›T™“›ÐPKÒÛ™M›Ú™ÒÛX–•SÖœœŒZ‘Ô’›ÛÑVV’’T–ž
ØMÖ•YUœÛU•ÓŒÕÍŽžž–š›ÕQÐÔÞšÔXSÙQ˜ÕNÛÙS˜MÔ]–U›’ÔÊÔ\^NY^ÔM•ÖÐM“™ØV”ÙV˜Ú\YÔ^KÛÌÝ‘\L™Œ•”R––”Ò‘ÖÛP•ÌRRP›VÔÕR’ËÝ“U”ÓY“Ü‘šÒQÑÞY”\QUØÛ[Ú˜ŽVŒQT\žZÓXTXUÍMÚŽLM‘ÐÛÙLZÞ™ÒT]ž^™ÍT–ZœØYY”[^L\œPYÌÙ›Z\ÛÝ[ŒÖMÊÍ–ŽZYœRN”ÝR‘ÜV•ÔÐÙ‹ÛÕÕUZ]Ü^’X™Œ“Õœ“[Ô”ÐÕ“ÝT•ŒÛ˜ÚÊÛRL]ŒÌJÖ’]YÙ™Ô“]RÓ’˜–˜Œ[U™‹Ú–V–R“ZšÛÝž•ÞÝÑÛÓžËÜLØ•ÌV[šÐ’ÖŒÐ”^–T’RŒ‘žSÔŒ˜ÕÙÞVL\ž›Ì•œ[S]ÚÌÌœÕÓÓPY\ÕÌÔÎXZÓÞJÜÌ^TÙ›ŠÞKÒQÎ™U›šÍŒZžTÓÔÕTU–TR\’RŒØÎPÕÚÐÚžV“–ÖNŒÝLŠÜØMÛ•ÚÊÕ“ËÖPXž]
ÎžÙ–œZ‹ÝR
ÌSYÌÔ]Ì™ž“NÓSÌÚ•Pœ›ÒÙUÞŽNRÌÑNMXÛÑT’QVSU]XÛžQU“ÞY]“›Rž™ÜS”ÑMNY[ÞŒZÙ\MYSÑÔT˜[šYYŒYZÜÖ›œžQLŠÒ\\˜ÕL›Û”ŽÔÐS[ÛU›ÕZÒŒ›“XÕV–˜•›ÙTTÌMœÔÑÜÞ[ÞU’XÝPYYÑÕZ•ŽUYÚ[L]ŠÒÓÚRÓ[]“”–ŒÓLÝÛXÍœYSØY™ÔœÍÌZ’‹ÚPžŒ]ÓZQ•\ÙÙ“ÓSJÖ•–PP[LU‘–XšŒÚN‘š[LÕ“ÖU‘JÛZJÙLQËÑšŽ•›Ô^Ž“T’ÍÙœVSUÔ‘QXÙYœÑÕ’ÍËÑÝN›\ÕYQŠÚœŒT”Ø•LÛÒ™™ÜÔQŒQÓÕÔXÐœPÙÕ˜XœÐLÙ]SÕUœQ“YÚ›Vš›^UKÖÞŒØLRÌNÚRÍÖ‘ÔQQ›[Ú–RšNÚQ›U’
ÑLU’ÓTÚŒÒÖÕLRÔP˜“\ŽP\SËÛNLÜÍXŽUŒÖ‘M^Í[UÝ”TX˜Óœ’”UMœYÍÒÖU[ÐZ^Í[ÕLÜP’ÐRÙÑ‘ÓšLÓR™L“ÓU•[Œ–MÎYÛÛLœ›žXÖ“Þ–™LÎUŽ\[ÛJËÙ]™]’SMÕš‘Í•ŒÑ]ŽKÚÜÛØ’Q“VU”Ò^Ñ“Ò˜ŒššÚÚ”ÜŽQ•ÔZ›œU’LÜ˜žŽ\MTNYž™][QRLYÜÝYÙQ•YR’ÎSTUXŠÌÍ–ZKÕZQLXÔXS”ÜÛXÍ[SZMT–œLŽTÔ“MØÛSš“PRÖS[–‘ÓÚÓTØ‘ÚØMÐŽPUØ[UQR˜’œÒšÌÕRÒžžÖ•^NTM›œXM›Z”ÎÑÔTN
Ö”›ÙQÜ\\Ü^–ZžN™[^RÒÔLÐ]ÐXÖž‘Õ^KÐØÑÐMSŒ›\^R–[Î•›ŒTÙ[ÛRš“™T›š[]^Õ“ZÓ“ÔÒËÌÓ\MÚ[ÍÑÛÐÚÐÓ”Q™™YÝX]ŠÝÍTÖ™ÐžSž–MÎ“SSÍ–KÚVŒËÕP™LÜÖŒ[Õ‘ÙYQ[ÙœZÛŒžšÕÕQÙ‘ÔÑØÔØÞ“ŒLž“™’ËÍUÖNÎ“‘šÎRQLYœ^]’Ü^š]ÖUÍMÜSLØZŽ]XÕQÙÑ•QU™Þ˜MMÛTU“–LÜRÓÞ\]RZQžÌÞLÐQÛÚžPÙÞÑPÖXRKÍ’•Ú“QSYÕ˜MÖ˜Íš‘Ø“’–Y]Û”‘VQ•Ì”XLÚÐÓSÜšÐœ’›Ì“ÖNN^ÔÕËÜÝ™Z•\Ùš[ÝYž^QÜÑXÛ[ÊÍLMKÒÊÝÝL–
ÌÖ“Õ‘LÕ‘Ó•ÎZLUÌÊÜL^•RŒU]ž\ZNXÖN™Þ“ÙRS]˜ÎQ]\ÚSÝUQ”˜ZÕÖ[“Ú’Þ’R‘Û\T‘Û’’ÔšZÐYœUU]“U”ŠÒØXŽžYRMÛS‘ÕÍS^RXMÞV’KÔÓ˜ØNQÛÌZ‘Û“ÌÎÞPR]™˜YŒÍ™’ÙRÞQXTÓž^YÝ]VŒÚ˜RÞ”ÒZLÊÜ[˜ÌØZÌÒLÝÜ[”Í‘’•ÞUÎSS^ŒžLÕ•‘œ\Ž\ÓX“ÚMRÛÛVžN˜––Z’ÔÞ–YSN]VÓÎRÙS[S[ÒÑÕÍTTT”PÌYÜŽU˜Õ‘ÓÒ•XÜÒššTÜ›šPÐŠÍ’’ÞUZÚÞ•Þ’Ø\ÕYÒ–ŒÕ’œ[ÍÕÒ™ÔÛÑSUÒ˜LSŽ–šLR\]LŒ[”Ö›QU“TPÒ˜ÓÛ•“ËÛT–[Ô•ÓÔSÚM“ÙØÍR•’ZQ^ZÜ[Ù“U’M›Ú˜œÕÕÔ•MPž\œVÓSÝÞšÎ]›YÖž”PšÐLÖSšÔNXÌT[[œ^™XÑ^\\SØÜZžž’YVŒÚ]ŠÕÖ^šš[Z’ÔZTÚšÛ™ÙÍÑLÔ‘KÕÐÕÙTS]Þ‘ÍX’’ÖUSXÍØY]™^[“V•ÔÙ“˜JÍŒÑÐÑ^Ô–™ZMNžVLŒÌÛ‘\ÕÞ]ÕMÓZSÓŽZPQœ]ÔÜÖŒÔœ]‘\Ü\ÜŒ–›ÚÐTM]ÚÊÚÕRÎÙP]ÙÍÎ“QUM””Ó[JÖZš^JÑ˜ÝŒÙPœšÕÙÕZ”YÙ[ÔÓÞUœÓžYÓ[ŽLÕ•[]–‘M“‘T]VMÙÎÛÓ›ÌŒÌÙ
ÜÔ•Z˜Ô’JÚÝ–‹ÙÕLÐÒ’ÖLœ\TŽ[[Ú[ÎY•’ž‘™™ZLXZÞXÜÖÌ™TUÍ•ÙMM“ØÙÕÛ
Ü”Ñ“ÎÚTÚÌŒÑLŠÝ]LØU‹Ô’RÛQ›Ô\Ó™XŒTÖ™YMPÐÓ’Ò›[ØÙM]\Y›Ñ”[X^™–Þ^™’Ì’˜Í™^•PÕž›ÓØKÚÐšÒÎ[ÕÌRŒÜšÑÞLÛPÎRšÍNJÕ]ÔSÖLÐ“ÓRÌ•ÛÚÚÙQÔÖ“ž›QÜ‘ÖÎZLQ“[–LÒÖÎR”VÔÖ“ÛÍÓØÑ\˜“ÞŒMÔLËØX‹ÜYÒ›ØZU[ÑÙÜÙY[X[\PÛ›ššÒÙ“’ÌÓÜÚÝ\Ò•Û‹Ú]”–QÌYZÜ›L^”^˜XÙÚÍÌšÑZ^UÝZ”ÙRQ›ÕU[VŒŠÎUÎXÚÌ]Ù‘Ó•M˜œÌ‘M–“ØP“œÊÒÑ\™œN’ÙQ•ÐVž›MSQÙšÖÑŒÚZ•™ŒR‹ÚÒZY]
ÚžŒLQÍRŒ–YJÜLÒÓÜÜTVÓŽØÖ[SÚS[ÐL™”ÓœÎU\›ÕÕÙÐÝÕšM™ØÛMÚTÜZ‘TS^U‘\‘Z\’ÞRÔÚÛ]˜TT˜ÌXÛŒ]Ô‘ÙS˜‘•TÖ]ÔÌØÕÝYÞÒPT\UTÙÌU”ØØ–R™V]V˜œLQÜÙMUÑ“œÑZ”œZÓQÚY•Ò’ŒÞ›NY\˜Y^™ÐLU“Í‘]Ø›R“ZSÚÒÍ™Íž‘œ”ÓUQÚËÓœ•]ŠÛQœÌÙQ™XRR‘QŒØZÐR\JÙUÞžQÚÙ”VNÓU™QÔQœMÐ™ÜÛŒÙX”MPÐ\Y‹ÒÕXÕÒZÛÕRPÝÎMÙ™•Öœ’Ú’“ÙÛÑJÔ›RZÔSR›’YÛšœÓœÜÜÞ\“š’\ÕUÕ•Ñ\KÐÙ•ÒšÛÔÐÑÖ•VMÜLÚÝ[œ‘ZR›ÞžT\U\Y™Û™NQ–Y[žSÑQŒžS•Z™LYÑYÚ^QÝQRÕYœÜKÝžQLUÒKÑMœ[M™’NžZÞLXÎR\˜ÝZ^’\TÖ˜‘\JÐ•[“VÜŠÒÌÚÌ^ZR”œÙ•’Óœ”VÐÙQÞ
ÒÍ“ØTÚQL”ØUYŽ[\ÍÔÐ]“’œ”‘SŠÔÐKÝ–X•”ÓØÔ–’LŒS““Ù‘ÎÚ•Õ”šÕ”SXÊÔRÓM–LN]PRÑLVY’YT\”ÜÕ\ÓNR]Ô˜Þ’“ÜÜMYSÚÍÝœ]NLÝÛR“œœY‘MÖ•Þ\S–Z[YÍœX›ÖšŒSÑÛÞšUžÒNQU[JÔ™ÛÒÑŽRRšÕ\U–ZØVUPÚ–UZÚ•ÕÔÍR”ØØ\–L’›Ö‹ÓÌÎ\UØ[QÔš™NMÑM‹ÓVZTÜ[ØÕ”NV™ÜÚ]Z™ÍRLÕÖœNLUÐ••V–Rš–\Õ”ZXÓÕËËÍMš•VÓ“˜–ŒÛÖXšÙ˜^]”\ÕTÕSÎU]‘ZTÒÙULÞ]ÔP”Üœ™ÓÙÑJÝ“^QÙV””“ÌÝXUÍÍÑUÒZÚ[Ö‘ÜšNžØUU]RœÍ[ÍTÕQ•Ž[[ÒUNU\VU[˜–UMTÕ^\•‹ÎZÕLLJÙZÛŽLURÐMQ”KÎNËÜÖÐÖ’ÍL•ZÛÑžšSŒššžœÊÒÛ\ÍTQÜÒLÍT‘ÚÔV“VZR“Ù[^‹Þ–ŽÔ™”ÊÝÔÊØ[ZÒÚLÛ‘‘›]š”QÜ“Œ›ËËÑ[ÜšÜËÌÕUÍÍTZœ“Ì[Ñ”[ÒR\•\’•ÜÐ^Üž’Þ•ŒÙœLÔJÖ–’Mš›œRœ\˜–TÒÜÜRØœ•ŒÔXYU‘KÔ”Ò”Q•Ò™ÕX››MÎQÝRŒPVNJÖT[PRXXŽM“•šÙÚÍž“TÚØZÔ]ÎLÒ“”™XZÌÒÌÚ•›‘LÛÔTÕ˜ŽÒ‘Ø”ÛÒRŒÓÜTR›ÓÝVXRÔ›ÔÍYŒRœ‘Î\[š•RÚœÊØLÒSÑ™ÒÍTÚURQUMÍÎRLN“ÙMŠÛN”“”\XÝR”’“ZKÛ›Øš•›ÕÜ\ÊÜ›SÔÔ”ÜÑœQ]^ÜÜÜP[ÒTQ’œ\[Üž›ÝN\Û™Ð“‹Ò›–\ÕÛ\QžSSŒVÖØR–PSQ[[LÕœšUÙÒT‘™ÙÜV“QÙÙRLŒS’YTV–ÔÛ–]ÛÑJÑ[JÔX”Ó™UÍš‘Q\[ÍÚŒ[•œMžÜœÊÛ\LÑ›T“”Õ”]™ÝÍ›–RŒMÌRÌ•SÙ”UÛŒ[ÚÛP™LžÛYÝYY]SœÌÍTLŒ•ÝÛ›‘Ù›ÒZT•Þ“RÍÛÎ
ÒÝÕKÒY‘ÊÑ][Ýž•[““’Ø^šÚŠÓ]Rœ˜[ÛŒX™ÛÍÌžŒTL[•ÛVZ[ÊÜÒÍZZÍUš[^˜ÔœSÔ’Z’NÍRÙLR•™ÍØPUUS•ÍPŒÑUžÝ’L^›ÞPR˜Û\ÔšYŽÓ”Ý”PœÓM“ÔX^ž›–[–ŒÝÜØÍ\ž™ÓÔšŽÎRÐÑÚ™™œÙÛUT‘]Z[KÝŽS\™ÕR‘‹Þš]’’™ÔŽX˜›ÛÛLž˜S˜“Ý’Ñ‘[ÙÓ–•ŒÌÝ˜œœ”œ‹ÕÞN[’TœÜS’™ÞL–QÚ™’]SŽÛžÜV–œ“S•šÍSLÐÓÜ–RUÝÕÐZV“‘Ð^SÛÙÞ\Þ[ÕV™ÛÕL›JÝ™’XØÜÚ\XÖ\ŽMÒÙ•Ô^ŠÍ\YÖ’U‘šLÑ‘]ÔÕTÍ
Ò•V’ÔšØÒ–ŽNVV“^›•Õ›Ü\ÐÞQUÌœ“Ý^[^”ÜMX\Ò”N›Î[Y[Ô”ÝÑ˜›ÍPÌØRUÚ[ŽN“žPZÔÎUKÊÒZR]Ò”ÓÌVÝ“ÙÓÖ[^™ÛT“ÑÜ–šØR––VXÕ“ÊÍ•’[š“YLÝYL“ÌZÖÞV•ÛŠÌÝ•œQY^ZÝ‘QÝ˜V‹ÔÑ”Ú^SKÕ›NZQYÙ]šLÛ]Û’RÒÜMÌšTÜØÞÛÙÌ”žÜ‹ÝÛš˜UMÒØÚ–˜ÍÕÝÜÙLLVXŒQ’[ÚÜL]SUœÙÓÑZÜÝÚR]ÚšÑQRž™Ìž–ÝËÑÖ›RÙÑ’šR[š“Q“Ñ•’ÕÚ”ÓTYTÎYZÑÒZVØ[Œ›ÜÜÔY\ÜÛQÞÌÝŒÔ˜Ì’ÚÊØÙ›“ÝŒVP•›LZÓZÙÝÙXÓ›]™MÜ‹ÓÊÌšÊÕÑ–”SÎ˜ÊÌŒU›ÝÙÓŒM–^RœÔÍÌN^KÙ•’LÚZÐÑ]ZÖSŒœR‹Î’›šÓQ[”žKÙ™Qœ–T‹Ø–ZŒZÛÕœÚËØV›TžZP›–
ÝTÐÐÔZLÍÜQ–ÒËÒÓ•ÊÌÍKÍÔÒÙP–ZÙÔÔ˜šÓÖÕPÔÌšÜXœN[Y‹ÒÔ\ÓYØ›ŽXZXYÔÓÓ\YTÙQŒSÛÒRM
ÝÌœ‹ÔÚRT™Í’Qœ[››œÝ]Ü^M]˜œ’Ò[“Ñ›UÛ™TÍPÕ•Ì‘•ÑŒÓÒÌURQÕLÚ’
ÔÕYÍÓPZ\USÙ]”TMÒ\ÌØMÜ”Ô“ŽŒ[ZMÞ]RZÜÛ”žYŽM–N›ÛÚJÔM\R’šQSÜPŒRÓÝXQ]•M›UÍ\ËÐ™YKÙž\ÙMÝÜQ”ŒØÔ–]™
ÞZ™–QŒ’ÑQ\]Ú’Ð••ÛN]QÓ•VJÚUZËÍÛL™‘\VšÚ–’”YUŒUœSÓÕÞM“›RÖXš[ÝXÕJÝQ˜RMÔÔÒÍÔÌXPMT’^ŽVT–U”ÙÑÖ“Õ™‘Î
Û›œLÙšVÖ•ž[XÖÑÐÔÓžŽØQ^ŽÑÍQRX^›•^RZÞSÓÚ
ÜÖÖ]ÔZMœYQÕ]Û^TÓMX™M\LÛŽ‹ÛÑ•‹ÛQÑZœÛ›PÝSÍÔËÓ^–Ü‘”’Õ]‘œLšZZÌ–^\’ÌÓ
Ö^œÍÚ™ØXšœMš\“”ÝTÚŒÙÙšÔÔœÌÔ‘UœÒÚ‘œÝÒÚRÛËÖ“Ü›ÐÔ^™ÚLUÐÛÝ\Ñ›‘ž‹ÞŽYŒžÙŽUZLÌŒ“™ÌÒRRÓ
ÑXSœÕSÛR‹ÚÚÕÝš^–X–SM]UÜ“–JØÕ[^ÚÓØÓ–QØS]ZÒœ–ÙÔÛP“VŒÔÜUÌÐQÍ–TTÒÊÚÕœ[MYÚL”^]Ì“ŒP]SLX”Ú‘š‘ÞœÜ^]KÞ‘Û[˜ÑJÕRP™JÎPœQN^šÖ[Þ›”ÌV[UUŒœÔÙÖŒØLØ\RÛV‘’ÙÙZÙÚÒS^S–žžT”•VŒŽ[UÒÍÝ›’TLÞXXÜš[ÚÔ”™–ÐÑUÝ•QÔÓJÍÜÔR[“™ÍØÚ^•
ÓUÝÝÎZÕSKÌÌ˜VY\LÍ“ÔÑ““Þ’ÒÓTÌ“PÚMÎZÍ™›‘ž\TÝKÛÛ]žšT’ÓÓXPR‘ÙM˜^\ÝZËÚÔRÐÌŽ^žY‘^]˜’
ÔUPÒMŠÖTÍÒÞšU™œØT›ÙÔØ“ŒS
ÌX”N’RÚVXZV››[Ô˜Q™›ŒÜZYU[RÙÐÙÐ”™Ù’RT“RMÙÚ–UØ‘˜\PRÚÊÍYœMV™Þš’›žJÖ^ZTŒÍ••”ÔÖ[YV›‘ÙTÎQZ\[•ËÝ’˜ÑÚÐXÖX\RÑ•LÑÕ^‘šÝÙÔÚY^Œ]TRÐ˜]Ö”Ú™ØÕ‹ÕLMŠÚ[ÐŒžœ“[\Ì’RÕSZÙÚLÎQV”˜LÑ’Ö””\MÖ‘\VœXšœÓP]U›[ÑÞÑR]^’R
ØZLÔÎTUžTŽPXU’ÒÚT˜‘\”
ÌÛ“ÞLÒŒMKÜTÍQÍPYSššÝ’œÌ™Ž–TY‘YNÝÔ’”–•YÒTSÔÜ’šžŒÖ’V‘˜Ú\\›˜LŠÑŽ]Þ“–ZRÊÑÓL\]Ð^XÝÍ^Ú”Œ›]Œ–ZŒLRšÎRÝUZM]XÑ^[Ø[ØPžKÎL˜NYÝËÎ]ÛÛMTÒ›šÍÔÞQ‘Ü™\”Þ]XÖ›Íž‘JÚ‘UÕÛ^›T™‹ÔÍ\ÐŽRÖMÚM–QTœšÝZÞ™›•ÑT]R•“RNQ™•^S‘Z[ÖLÙRÖS‘ÜMÌ›TÌÞ‘TÛÔV›U““RQØÙÍÑÕ”M[RR“’P“Ý‘Q–YSÓÍ›ÑTÒÔ[JÍLÜM\JÍP\–MX‘XÔØ]ŒšLÒÝÓÌL”ÚÚÞTÙTÖ›PÔÕQÝQÞŠÓ[Ð^RÒÕ›ÝQŒÕLÚTY[œ]ÚPQÊÊÓPÔUÐÒž[\[Þ”ÕZœ“•™ÎUšQ‘^LLQÑZž‘Î\•ÑR”›ÜØ“KÓ˜žŽS^\ÐÝ\”ØTL”]ÞÚXÍÝ
Ó‘“ØÎL^MÐPLÚ•Û”Õ‘Ô™ÝJÝÙQ]ŽT“ŒËÙR››ÑžŽSÌ›ŒÓÙ›^XŽÕX•^MÛ›SÑÛLMœÐšTSÜÌ[RšYM[T“Ñ˜Ý[ŒTM]Û\‘ÚTZ”ŽMÛÛžQYYÕ‹Ù[›ŒM›Z˜\ÍœÚ˜“ÐR\ÔÛZœÌÚÑžKÓÎ\MÌZ
ÕN^œ[T’\UÐMÓYÙRXSU™™›žRÑÔš]ÙUÝ“ÊÛ\•’LRŒ“^šVŒšŽÒŒXÍTL›Z[ÝÜ[”
ÚSÑYÝYLJÚVSQ‹Ý^“˜XV’ÕžTÌÕÍLÕÊÚJÓX›“ÐYÚU[UÛŽÐÌÔËÌÍÕžUÝŒž›XÑ•LÔ˜M”ÓÒŒÞM
Î›XÖQ\Ú\Xœ™ÓTž””œLP˜–M›ËÚÕVX[R
ÔÓ\”ÙYËØŒ[ÊÍ‘]œÚUXØÛMXÍTÑ“–›Ý’ÊÐ–›šÛ]œSZÑÝÜ\Ì•–’]‹ÍÚÜL“’’PËÍŒ“’ž˜R]›Ì\LÒ^›[ŽÖKØÞ›ØÍ•]•RÙQ^‘VŽ]›VZÙ•ÝUÙ[•T•MTÕ™ÕRQ^TKÕ‘UÎ[VMLÕÚ“ØYÕÛ’•ÙTZ[ÕX–[[ZZÛT[ÛÍKÓÊÔ
Ý˜SZÌ‘Ö”UÚZØM’[UÖS•YÙ˜Q›Ó˜QX•Ò›šYÜ[Ô˜ŒTÝÜ˜YÊÚÙQÔšÝUQÕXSXØZZÑÝÓš•Õ™ÑÑ]ÍšÌ˜ØœL–\•Ó^TÐT[ÓÜÚ[ÙŒš”[Ö‘ÙÐT•ÌÛYŽSÑ’ÒÓMÒÑÓŒŒR
Ô’Ž˜VŽPÝ˜Ì’™“Ì™ÝXÔÜËÕL›[[›X•ÛÍÑM
Ö[ŽÚYÛ
Þ•–[œTÍ‘ŽÑ™MUÝ™ÚŽ–ž‹ÍÙ”ÜŽTÌ’ÕÚKÝÐU‘›ÑLÝÖšMÍQÓÚÚŽ]Ó[ÌÚÎ]ML“Y\Z“ÊÓ˜XÛUÖPTÜÞ˜ÍÕ“]ÐÍN]QÞŽ’”ÝÖÞŽJÞ™ŒT˜QUÞÒŒÔ”˜Í‘ÌQÎ\‘UQMU’ŒÌ™[N[P–‘]‘ÒT^][•ÕÕÚU]›[L™ÕVUÞÐ[PÌPÍVRR[“\TQ\YÑÐÎRÕ•ÒÙ\R™ÖËÞšÕ[˜Ð˜MÌ˜^•Q‘Y™QÔÍÝÔ’Þ›ÓÍ”Ðš›‘ŒÚ^šÚÛÕUMÜÝ\Y\Í›œØSXR‘XžšÝÕ–UPØL‘LSœQÕÝYÝP“ÑÓš”–™TØÒÒRU‘ZMYUÚRÖ‹ÜÑR[ÍMXRŽZV[ÓÕ˜PÜÜ˜ØÌžœ›™TÜPML]ž›‘U•XÙZÛÍœœÒÊÚÞ”™”S•‘ÞM”S\ÝTLÕRÓQ[˜ÝPÕÒ]ÚÛÒ\L^SŠÍ^šYÚS“Œ›ÌÞÛÑPÕJÌÔVYÓÍš‹ÒÒšÖU™Rž˜ŽKÚ[ÌLØËÌÞÕØRÑLÍÓ”Þ\LÒTÜMTœ•\ÜJÞSÜU˜ÔÑ”‘œ^‘ÙÍžRT•Í”UÌÍÝÛÎR‘ŽP‘ŒQ•ÓÕ–‘ËÛ›Lš\ÙÚ•ÜØÙYÖU‘ÒU”ÐMÖM•›ÜÍÚSU›ÐØÎT]Þ•ÚMNSÙ›‘”ÌÖÞQTLÌÓ‘ÖLœ“Ó\Ž–œ
Ö›’ÎLž]ÜÙÍ›™YXÝÑ‘ÝšÝQXÓÔÞYSÜÓÌÓÚÔZM‘“KÙÍ‹ØÓ\–“UT“Ñ™ÒÓÌÒ’“XUÚ–’ÑÌVPSÙÍÖPXÜ]LÔ^^’ÙTRÚPÖRQžMSÚ–•Q™TXŽZÐ“œ‘••Y”ÑÒ]™Ž‹Ú’‘PM’Ô•Ò]™Ø’[œžœ•ZŒØÙÐ’Ý\TTœŽ\‹ÛÖST“RQ›Sœ”™ØVMRÖ]]ÔÓÕÍ•TÞŒš•ÙNQŽYØÓÔ[SKÛœUYÚ]LYVXZœ•ÙMÑÓ[ZÙÛTÑÔLM™ÔXÝ
Ó›ÌMÍÌYRTR’L\ÙÒ™R]ÌËÒ]ÙÐÐY“ÕRÝÛš•ÒTX˜XZKÓSŒÙÎ•ØÛ‹Ø›•˜UÝÖLÞU[Í“ÝÞUÒZÔ^\›USÕ›Ú’ÙÑÜM”UPÛT’‘ÖNÞZšžP’ÕTŽÛ’‘YTØ–œŠÔÕž[‘ŒÒÛMKÝÎRZ‘Í‘Ô^UÝÙÖQš’ØÎJÊÜZÖÕ•[ÛL˜ŒÓ’ŠÖ‘\œTÌÍ™ÔÎ]“Ó•šU“ÚÍÛ]ÛZ[šZÑQZ–
Íš‘–”ÝÝY’–Q‘›ÎTÚ™˜•ÛŒÍ^Pœ‘\MÙ˜Õ^[Û’LÝŠØÓÑÎUUMŒZ‹ÖX“\V™‘ÛÍ˜‘XÍXQ‘UÜŽ˜RÓ•]ZÜ™Ú]L“MÌ“‘Û‘‘VTØÑÞ[žÍÍ›^]ÕXÙYÑŒŒœÛØ]ØQ“ÞNÐ”[ÝMÌ
ÓÐ[™Ô‘’[\N]MZ›SŒMM“PSQ[“ÚÝSÞXÜÖTNR‹ÌYš‘ÞQŽÌRÙ•”Ò‘˜\R˜QPPØ”Ð^VLM“›Ó‘TØÓž™ØÖYZTSSŒ›X‹Ü›P^ZT
ÖQÓ’NÐÖŒ›QUZÜÑ”MÖŒÛÛžŒÜžVÞY[KÙ[]“ÑÒ”‘
Õ˜ÒLÞMRÌ›VÖ“ÎPÍÊÌSYÛÓÙY•LÑÛLÌ”T]QÝœÔÙ’ÐÜÑÙZXÞ
Õ
ÕÜRÔ[Ò™^[QŒ›[›T‹ÓÌ›œRQÚ–•M\KÓÕSÍTTÕ”ÔÜ’ÒPTR˜–]RÚÜÒÔ’U‘›T’˜Ý‘™ŠØPX\Ý•JÕ\\Ý›Ò™ŽY^]–š™ÎMKÜ”ÖœN\ÛVÔœØ™ÜÖØV˜›Ý›”ÖP\ØXÖXŽÓÎZSÝ™ÌÙRT]œž^•ÑÍœ“””Q^LÙÚRYŒÔÜ]ÎMVÚ›ŒXÖV‘Û“”Ý›\–”SÝ^ØÒ”ÜØÝLËÓSÞÙ•[PÝMÖ–[•Ö‘™ÌRÍŽÚŒS”Ó‹ÚÚYÑÞTV›^\MRÑÓQT•ÍÐ\[USÔTÊÚœžœLÒVQÕÊÛZVKÕ^KÒÙ”SZž•ÎULRÖ”ÜÑVÌZžÍÜ]”Ù“Y[[ÑLŒØÌ‘“Ì•ÚÑU‹Ú•ÊÚÑMY•ÌÎV”’^P\R^V‘ÑÑÊÐJÜŠØØ’ËÝœÞÜMÝÝ›’’˜ÙŒÒNX–™NÝÒMÜš\LÓÕV–’RÚQ–Q“\’Q–•ÍŒÒ“ÎY‘LŒQLÚ˜Z“Û”Ñ•PÚN˜ÑÑœVž”‘™]ØSÕœ
ÔÐ™RÓ›Y’›ZËÍŠÙV‘–ZØP’ZÌUULÐšËÕÑÑPZšÛŒ–^ÛNRÞV‘ÞRØš[QŒVžT‘PNÖMšŒ›šVQÑ]•]]PM\RMÖRU[ZŽRTÑYÛ[ÒšËÞUÔÕŠÌ\ÎQRJÚÝ•[ÑÍÞÍÜ[Y[Ú[Û\XÌÙÔN^SÌÑV•KÖZÙ˜Ö]ÕNZPVYÓÑÞR‘T^YKÙŒTÖÜ˜›ÎV[ØÎMMØ–ŒÞUX\ÍXP[‘ZTÓÜ[T“Õ›\V]R‘[›MÙÙšYS]ÑY•ÍÒÌÐ[ÓS•N]^™•ÛL–UŽXŽËÑS››QÓÕ\YÚ™ÜV]TÍNV‘SÞ›ÙQÛÜZËÖYZ”SÙÓ˜JÞLÐÝÌÑÙžUVØÐÞ›R˜“ÛÛ[SÛ\ÑÞ
Þ]“ÊÑÓLQØ–”]\^SNZMQËÚÌÖ“ÑÍÕÓžM™•QL^ÑÑ\KÕÜ•L”›ÖœÚ“TÌT›‘žÝÑUÕÐRÐ]ÎV˜[Œ’ÒLÐÓ•U˜•Y•MØÜP]ÌÑ“Ü’ÓL˜T\Ú’ÍŒS–RÙ\YZÝ^ÖM•˜›UšZÍ˜Ñ™”ÓÚÖ]ÞšÛ‘ŠÖž–Ü’Z›ÝÍÓËÎ\LTÜÍ’ÌRQÖÜÚN›]ÝÝ˜UÕ–›ÓRÚÙ™UÛ˜•š\›Þ\[[Ì’ÑLÔœPNZQÛÝT‘
Ü
ÑÙ–SL’’ÍØRQXÕUÑUYÒŒÌMÙÛ’ŽKÞš[ŒQQÌÛÝÜ^œÍÑZ‘›ÛÍÔÚšYÍÐ^PYU–PÌN]^ÓMžQÕ”Ù]ÑÖ™ÔÑŒÙ‘Uš™
ØÛ[‘””Õ›–\ÚZÎÝŽTÎ”’Ì™YØ[Y”Ž[˜’žžœÑÚS[”Ù^”Ô’YÝÚÛ\[ÙžØZÔTÝ\”šÕS]ÒÚZÜÌ™ZÝÝ•˜LÖT\MÕÜ‘U]ÎX•ÑœYSP\XMÍÑÙ\œÌÓ–M•Ü™•ÑÞšQ–\QšXÔRLÒVŽL
ÜÌÕÐÖ™V‘S“T^œZ”KÑ•ŒRÔŽ”•Ž^RMÒ–QÚ‘”MØ™U•”ÜT›‘ÙRÙPž˜LV•Þ•UÍ•™Ý]\ÔÖ‘’ÒÑÐSÛS”QÛLÜRÔÞ\^UÙYÝTSÛÍQ•Í
ÜÙÐŽ\L›Þ‘XÖ›ÝV^žž•Ùž™SUR^YÌQ•Ì^šÒ“VQRÙ]
ÜÑŠÓ–˜ÕRÖ”šÞžXÒSÌMMQL’”ÍMÛMR\Ò™“Ø”œY“ËÙ’ÜÒÍÔÍÑÕ”Þ]Y]ÓX˜[ÕØUS“™Õ[ÙÓš’”ÙÌ‘VVVXN“ÑQ’Û˜Q“ÊÛSMJÕÛŠÍ•ÑŒÐÌSÊÑ]ZÚ[ÌÓØ›ÕÒÕÔ\ÛÜØ™•ŠÙÞÞÔš™Ü[œZ’YÔTœÊÐ‘–Þ•Ù[ÐS]›JÕ]RVVÒŽÜÝ‹Í’MÌÞU›‘ÔR^TTÚžŠÑKÚZP’]œÚ˜ÙÙÙžUÛÓÔÓØØÛÌJÌTY“ÌšÔÚV[YÕ[XÎ’]Ó•RÓÕQ–‘ÜVYÑœÍZÜ“Ü‘ÊÑY‘[]ÛÔÜŠÔÍX™]ÐÙ™]Û›L‘]T–ž‹ÒVZžP‘USžÞSZŽXÓÍœM’œ™ÓŽKÍLÜX[“NÓ\–ŽUÞÑÑPÌJÛ“ÑÝ‹ÑšMÔÌL’ÛZ–XT›^˜ÛÝÒ•Ó›˜šÐÝÚ›Z˜P]TÑ“PYÒÖ“ÊÌUÔÎÚM•ÍRŽTÙšÚÖ˜™ŒZŽ›ZTÕžS•RœV™ÓšÞMŒš›”ÖLÝ“šMÛÞ]˜SM‘ÝÍÔžQJÙ›ÜÓÙÑÒžšL’UÌËÖM–RRRÖ”””˜ÍTNÎ›QLZŽÍ™M’’ÚZUÎYÕ™R\S[ÝÚÔTSÑÒRŽPYÜMž]]™X˜Õ˜[ÕÞÌÑÜ–“Ñ•Ö™ZMUš‘”ZÓXQNRÊÌ’ÌÝ“™Ñ\Ý˜ZTÚMLVSÍ\^“’š™ÙÎQS’]ÔMÌ•‘ÌÛÑ\XÔ’ÕPÌSœ“ØVS™\V][ËÔYÒMŒÕQMRÎYÙ^TšRš˜ÍX”ÓŒšYX›Ý[ÞYËÑ›UŒ[ÛÚ\ŒP˜š“YVZ˜”šÙÌ™–PÎPÒPÍÔMÛQ[\SØRÑŽQSÜÔ˜YÝ“™›[VT“Z–ÒŒRNÕ•UP•›Ý‘ÙZ–TU’•ÚØÒ’ÍŽÝÚ“”“ÜÚŒ•ÓÚÜMML[•“Þ˜’KÌLÕT–ŒÙ’^MÖUŽ]^^ZQ‘˜ZYœÔ\“ÝS›YZ‘˜‘QÍVŽU^QRÒÎVQœVSYÚZR^QÕ”žÚYYœœÒX\VLÐXZ˜QYž’SÍÑ‹Ø•˜LUÙ[UP–ZÎ[ÚÊÌNTÛRMP’]ÎNPÖXRM•Öš
Ò™S™ÜZÚÐÎTÎM]VŒ˜Y]ÙÑJÛÕN’œšV‘’ÛN[YÒÐLÕ‘]V“ÒÊÒ››˜ŒÓÝÛÖ–MÚÓÖSYZÓX˜ÒTÖT[ØŽ•ÐL˜“SšÕ]MUž™œPJÓÚÍÔ‘ÍØ“ÛXÔÔ[”Ì^RQPU[ÑU•SMYÍYRQŽ•YKÍ\’ZÍ“UÕÚP”]Ù”[ÙÍÜ[^šÝÞXÓÍUœÌÕXSÛÝÑ•™›žQž•ZÛÓTÑQÌÙ’VV–šÑQÝÌ\ÐZTšYØŒPU‘–”MÎSÕ\”RÞS‘Ð’^˜”VTS\ŒŽ^”]’[Ý–‘Õ˜PÖNQÒÙÑÑUÝQÑÎQ[^NUÚÖ•Lš
ÚÓZÞX‘ÙUÜÙS^
ÌQMÑšNÙšQKËÖŽSKËÌNLÕ\‘™“ÒÔYÍž‘šSÙS”[žMÔ”˜UŽPQÒUÙÔJÛ“YšžXQØZžŽPœ•ÔØM”‘VœVMÜKÌUL]ŠÒ\ÛLÐÕÔÜŒPMÙÙ›[ŒÖYMœYÐTÝÚÜÛÚ‘ÒNJÝÊÑÐÛÜÍ‘ØÚÞÙY•M™MT–ÛP“‘ÙÍ™RMXÝÜ›TÍŽÔÓœ™”‘šœPœÌœÚ‘ž^VPÚ™š•LÜ‘KÙYÛšVYTJÜÕÔ”TZ›ÐÙQ”\”Ýž™ËÝ^–ÓÕØ^R›ÑU‘L™S™“Öš\ÛÚ•ÕÚšLSSÒTÕTÝÑY˜Z“ÍSÖXY‘YÓ^]ÌÝ]SÛ™“ÌSÒÝVÜ^˜Ì[šŒ‘‹Ù“–•QUÕ•ÐÎ\MLÒÓ‘ŠÞ\ÑQ”YM–™NÎ\XØQÙŽ‘YÖÍYZZQL“Ú›
Ûš]NNš]KÓÞR“SÖYÓ’ŽM™[”^•ÔÛÌÔ^™•žŒMÌÕÚTÝÝÕ›“SÐ™ÑN^TÐ”ŒJÌÛÛPTœ“Ú™™ÒšLÐ™Ú›\Ù˜QÎLZSU[ÞšYZÌ˜[œØTÌ›‘ÍÔÕMLšR‘•™’‘›™Z[•TSœ]Yœ•ÛMÊÕ”ZUS]XÑ^‹Ô]Ú’Ô‘•QœR›ÞJÕÚ’VXÓÞ\VNÜÛÌš›•š[–RÝœ]ÞMÒ”ÑTØ[•Þ›ÔÍ™V‘ÝÙ”ÐÑ]\[RÕVÒ˜Ù”[Y›”ÑœÌ›Ž™Mšž\ÖÙÌVZÎ›ÙMÝ–ÎÜŠÌÜÛœS]YÒ’S]Z[˜ÔVÜ››RQÍMÕQ•ÒÓ^NV’–•SÐÔVLÌŽœš˜NTÛ“ÐÞÜ’]ÞUÝ“ÌQLÝÙÓ•ÒÚ’ŠÙ’ÕÑ“ØšŒ]ÒÖRØØÐÛÍ•\VT”ÙÝÎ›‘ÕŒTÕP“JÞÚM‘ØÜ”–SÕ[ÕÕ“RÒÝÙ˜ØQÌR‘M’Öž[™][ÔÓZŒÚÛ]ÒÍ^RL\][™ÑÙTY‘’ÛÌ^ÓÒUœÝQ^šÝÜØJÒ[ŽSY
ÛUÙ˜ZÌ’UØKÒ]‘Î[ÝN]]]‘[ÛÍÓÞL’T›ÌÔ[ÓÓ“UYÙŒXÛ\•ÐÍXZMÑX‘ÍY‘]œÜ–UQÔRÙÍRÖ•’Ú‘ÔTÞÕR\ÞUZŽV˜›šÒ–›˜ŒŠÌ–QÌ“XLXÚž˜TQÚ–›ÊÑ›]’MV‘Ö˜š]‘UÜ”ØÝZœÜ’Y“PÝÞ‘“RžMÝLÒL‘ÔÌÒJÌØ›UYšž\Í^›Ì•Ø^›ÎSSÌL’”šŒLS[Q[PšSQÙ‘LU™U›L“Ì–\ÒÜL”ØÎLÓÙÓ“ÐUXNSÚL]™ÜQ˜ÜÌËÎŽY›˜U˜–ÐS–XYÌÎÔUNXØ[“ÛTRR’œ‘ÊÝXÕ[•–LÐY]VœÑ\’ÕLÎÕÔ˜ÚZÑÒ‘™ZÑŒQËÙÊÙÝR^X™SMÍ]•ÍÜ^“Q^^™Ð‹ÕÚ\ÍU’ÐLZÍ’YŒÌÛR™››šÍŒÓMTÕÔÒ\œÛUÐœ\N\˜ÜÖŽœPÍU›VÝÞ‘ÎPÔ\Ú
ÜÜ’SÔ“Ø›Ž\ÓÎY’ÛÖTŒÑØŒÍŒQTÐ’Þ–YÓ•šQ\“TÝ•‘Ûž‘NR˜ÜŽRRQÜÚÚœ–SKÙLœž›MTÔKÝ^”“ÎSVŒ–‘Uš’Ðž–’QžQÚ˜œÚ]X”P’\SÌžUŽÛ˜[XÍŽ‘ÖLÚšÝYÛÑZPÜM’SZœœ\
ÝYRTÕ\ÜZÞ››QZÝ˜–RÖ]™ÖR]RXÑ”Í^\”P]››]T‹Ú™ÑUŒP^‹ÞÓŒRÑœ”ÒÍÙÝY]YËÚN]‘JÒX’žÌÞš”V”ÐÚžŽUž]ÛUÚÍœ^’Ì[•˜Ü–œ]^Z]Ú[MÛÑÌÜØ‹Ú]Ù’\‘Ú^››KÜXœÎÒQÌ\MRŽ\•MŒ[ZÍZQSZŠÔÞ”Û’ŒžMÕŽTÚ›•ÕÐVP™Ô™˜S™^\ÜÒŒ–œ’MÑSSÛšÙ‘Y™ØØL^“–^[Ü’T]šÜZZ™–[”ØLT˜™\š™“‘ŒŒŽ^R“XSÐ”Ô™™ŒPžX’ÍTSÛ›YPNPZ\ÖÝ“ÞUÕV’Ü[ÌU‘T”ÕÑ•“š“Ý\•Ì•Ð^Œ’VMŒ^˜žÔÌØV^[Ò[Ìœ]TÞÚËÍÓ\“QÛY˜VRžŽJÍLÐ^™Ò“T•UJØNUÝY^‘Þ•ÌÍÌÌLÒœ›ÝSÕÔÙS]”ÒÝÐÌ˜V^SMÑ“Q\Ø[[TR˜ÔUTÎSZU˜™V[[TÜ”TÖL˜ÐÜX•SœÙÕŒYØ˜ÜÒ•Ó”ÚÙVLVž˜ÕÓÛÑNÝÕÙÓ“Ì]ž›œØœÍ”ÝRÍÕÖQ’ÌÞMZ•ÌQÛÝÓSVTÜÌÚÚÚ‘L–S•Y–MØš›˜ÌÞLÍ[ZÜ]›ÜQÜ”UÜÍÙP“[[š–]‘ÓÖœX”ÝMRZÝXÒÞLž’Y]RÕZÚÌ’\\™TÖ’“VRœZÌ”›[JÒ•NYRœ[MÕX˜ÍÝX^KÓŒ”ØÔJÌ]U›YÖÞ›MÔÊÐ“QÜZŽZMR™Ò\Ó\VQØYÛÝ’ŠÎ–\JÊÕYV\X”Ò^PVÔNRMN’ÙÍ’V”ÜÓÓ’P’ÐÝUÔÞX™SÕÍ’’TÓŒ\ÜÒÌX›NUÍYÕšÛÌŒÙŽQ‘Ý]\˜ÓÝœÖJËËÛNœ•UQ•R’–TSLÜ^LTŒÓR”[‹ÓÑ“Õ–œÙÍÛ›ÌT\\•ššŒÔXÚP“ÖUUM‘YÓ›’››ÍÍÌPØTÌTš–STÚ^ž•šMœZTN›^ÛÔœ\ÕMœ’^“Ž^œÝ˜[UÌMŒ’R
ÚNRÌŒžÑU˜•Q›ÓÐÚØ‘–””ÜÛ•RÜ›LZÕÒULÝSURQÖÛLÜ˜]ÌY–ØTLLÌÔ]L]ÍÚ“ZU–^T’Ò]LŠÓ–Q‘MV™[ÌØÝÞ^•ØM’ÕMLUUÕQÌMœSÝKÕØ[Õ’Ý[Ø[œ•ŒQ’œ\QR”[šSYSž[“ËÓZZÎPZMÝ\ÑšÝ]ÌÜQ•‘šŒÙ‘]™YÌÐV’[ÝPÐUØØŒ™ÌËÑSžœMÍÐÒMÒQPÒ[•‘Ø[]Ú[
ÔNŒÙZÌÛ\XÕž\“Ô]Ð•‘’[ÍZMQÒ’šMŒÑ\MÎLÛXÍTÓÑS•ZURUÌÔ”\SÙ˜Ö^“ÙËØ[ÒÝ]^“œÌÞžŒÔÌÑšTŒÒÒPšÚœ–[•šÝÕ[Q‘Œ
ÛMSÛ[RÔRÌ“RQØ‘›Q[^”SXšÕÜ’[\Þ˜ÊÞš\•™UUZ“ÝŒUØUSØÛM[KÕ›UØS‘V›TÖ›QY“VÓJÛÌ‘[ÑKÍ”šÜZR“ÝÞ[ÍXZJÕ\œMKÚÍV•’ÔTÛžœÒ\ŒÝ\Õ•ÎÕÐÐŒ‘Ž]›PØÌ[Õ˜\]U\•ÙÌMÊÜJÛÜÓÑ›œM[Û›ÕRRMØÞ‘ÓÐØÐ]ÎÞ”•Q”˜V]ÊÓU\“R‹ËÊÙYØÑRÌ’MP“\M^VXZŒŠÛTÊØ\ÝÔÜËÝ•“ÚLÌ“ÓœVXÑšŒMÔØ•ÍÝ[Y]‘SŒÞXL••[\‘RMÕÚÒÕŒÜVNUPYÒÌ‘Õ
ÙžQ–UL›RžT•ÎTÜ–Y˜šÝ”ÙØÌÚS™‘š”‹Í“XžU“ÙÕ”XRTÜ””ÔXÐ™Þ’ÒÙÖŽ]”ÑVZÝÞŽL“ÐLÚÒ™VSÚ’JÕ”Ü
ËÍžNÜMMÞXÛSŠÖ^TÍMZ’›Ö[›ÜØV•ÌÌÙU™Õ“YœÓÖZÌÍ™‘N
ÔUUŽ\ÞØQ]Ó[Ô[Ô˜[‘TžUM”Œ[ËÎYÕ‘ÔÎÜÖYÔÝÑMÝÌÌ”]Ž^ZÝÞ“JÜTNRÓšÍØZVVPŽ˜Û]XÞ˜TÔÓZSQYÜØ•XÐœMÑÕQÞQšÓžSSžQ]^RÔšP–R]SÌL‹Ò^•U[”œ™UMœÛÙžV^^ŠÜœØÌØ‘ST››Ò
ÓÛ]ŽLÑ“]’Mš[Ú\Ý™[M–Œ’ÖM™›–QÞZØÑXN]Ü[RTSQÒ›•^œÝœ–QQÖLTT[][TÜ–VÝÔÕ’Ü™•“\]MÛYÔÒQÜÛÜ\ÌÔMœQLŒÙžŒÙÔÝRM™R”“X™™”ÒP–˜ÛÜÑÔž™Ô[T›^YÕÑÛPRÌÞŠÖŠÖ‘œÐÕœÌÕUÔ]\]ÐÌMXYPÑŒÔÜTS˜™›KÔÕÍSÌ–‘ž]”^–NÚœœÛØÜØœV˜ÓMÐ[‘ÙÊÌÒUZÔTÓÜÛÚËÓ]L–“”R“ÒMÝËÒ”ÌÒÍÙÑÕ›Œ”ÞžŒžZXÜZÚÛÑ]ÝRX\šÕŒXMØRMœÔÝÍÌ”šRSRJÔU]LN]šSSÖYŒZÌ“PÍÚÌÝÛÝ]‹ÕÍSN–^MÖ‘[ÒRÓÓÙÙÚRQÝPÓRØSY™TÛŽŒÞ^[RRÕ››Ó”ZZØŒMT’žU‘“VšRSÜÚ”Ô“L•›YŒU™‘ÕÙÍNÔV™ÐQUZZ“
ÊÞ]M]•™ÛXÚ’›RÒ^VY
Û[™ÌÕR’ÕRY‘‘ÌÍ[ÒÑÓ”VQ‘]TÒ“™ÜPØ“ÔÛSÝÐŒÝÒ‘TJÚÍŒÖ]XVÓ™‘ÝÍ–’Ø\ÑSQRÖ“]ËÙÛÙžUÚY’LÞPNX™PYQLZ“ÖŒÙŒSÝÙÛÚšÓÞ˜ŒÎ•UÍÑœÕ]˜Õ]Y[]”MRØQ™V[PÞ[MÛÛÚÙÑVTQÞÞžŒÓÚÞ[U‘”VV‘šM›ÚVSŽ[NžJÞR’Yš
ÚÞSZÖ–•ÌšØÜ•R^•LšÔ‘’ÕRJÚYÚÍP™ÝP]Ü“ŽM•š›ÖÞ•ÓÛ›\’Œ–›SÜZÍÓšZ•‘ÙÐTŠÜ\œÒœ‹ÑTÐNS\›’ÑÜ^‹Û•VœÐPÖXVP“LÜY’Ø]œUžZ–ÊÜ‘ÛÓM”••UÔžRXÜ•‘”P™”ÐŒTÍšÓ‘ÑËÑ™Ú\[ŽM^U]RÚ[Í˜‘ÚÎÌXJÔÜÙTœUÐ^T•“ÔTšœšUÖVUš^XV”ÙÞPM•Óž‘ÛÛËÒV‘QZÑLËÐSYÓœ“ÌÓÔÕP™UL”ÜM›‘’Ô•ÜÚ\‹Ú]MVPÍž•ŒœLÑÔÖUX[\N]ÙÔÛÙS“ž^ÜšSÜ’šŒ“SÜÕÓÝž]ÛÍQZŽYTœLÓšP‘–\™ÞN]›SMJÖŒÞX\NVš–™]™ŒTPM›^“ÑLŒR]LÌÔœ[]RS”UÓÓÛUŒ]šUÖž\RQZ‘ÖÔSÝQSÚÞ^žÖŽÔŒ’š\“ÐT\XRSÖžQŽÙÛÝ[ÔMYÓŒÙÒVMP”•ÒËÓÜÐžŽPÙ‘’ÜšÙØ™šV˜]ÔÔÓSVMžÍR“ÌÊÔZRYPÙRÜÜ[Q™šS–X“ÑžM’V–\QŠÛ“™œÒÚ’S•ŒÕÝZÝÒ’ÝÞÝKÛÐšœ‘ÔÑÚÜ“Ü”›–]ÔÖ›Y‹ËÊÝT›QSŽRY‘]ZÑœLÑ™Q\ÓU’œŠÜÜVXÜRÓÚÍ–œ[ÛÓUU[RÞœŒN\ÑÒÍL^U]ÌÌURÖUQS™Õ˜ÛÍUÕ‘[ÝZVÒ‘ÜY‹ÖšØ\ÓÓžÓ‘Rœ[™›Ò]X•Û›Ú•STU
ÙÝ^
Ûžž
Ñ•–ÕÕ›ÔVØ’RVÕš–ŽR’–U”›R•[Q™ÖžÒ^YÚ•›‘U\ËËÕ[RŠÍÜ˜TQÛV˜œMX›[ÓKÚPÕ\S–]Mœ\ØR“Û’P™LZSQÝYMËÙ^žKÜÑXTÔNTÙœ]ZÑÓÕUœ]žKÌŒŒÑÜ˜ŠÛÑUŒUš•™Ò“–[ÜŒ”Ó•QÖ–R•T[UÐV‹ÕSÍ\’Ù›œTÑ‘[Z’Ø]Î^šVœ’XVQÔÙÒÖVÐ]›ÝÔÎ”ÌXÑžMPÛ’R”žš[”ÙJÓ\˜ÌVZS’šZ•UÎT[ÚÙZÒ™ÌÑ\˜UÍšÍÝ˜U^ZÔ–M’Ô][^˜XÙQXÍX‘QS\ŽYÕMT’žKÞZÐ’Ò›ÜÌ˜RÛV•–ÛÓÛYTQËÐMQ™V\P–ÜS”\ÕÛR›ŠÍ”“ÒŒÛŽ^Ú•TUÚYÌØÌPœÝXRÌ”ÍÚVœÑX›•Ó’“ËËÍÕYÜ[ÙÍUUÜ‘“ÔÌZÙ•UØ“LXÚÒ›Ñ^XQ“ÊÖÛYÞ”ÓZŒU˜Ì[ÓÛÔÑQ˜šXQTRŠÚ’”•ÚÌ^\Ñ]QT[R“ÕÚZ”^P[ž™XÚ\™ÕXØÝÙ•“]ÛT”LZŠÐÎ]ÊÚËÚÙUR‘ËÚQÐžTÌÎP^š˜™T›RÐL’›ÓSRPÓ™QÞZZÓÕ–XÒT–Mœ[TÔ‘ÜžYVSÍYÕ›ÖSZÜ]MÌ
ÞŒ[Ú\ÔŽYMXÒÖÑYR–ÜÔTÝžŒÒL“ŽTÜÍÍŒËÙ•”Ô“TN]œ\ŽMÞœŽVŒËÑØÚQÌZÓšLMÚÎN“UÜ\VPšÌ™’’“^\]•QQ–U›ÜžP’Ôœ•
ÑÔ[ÒÔQÝÙP^]’ÕÙ^•]Û––\[ššU]œÑÑ^Ø™™ÍŠÓLÜÌRŽ^ÙYXÌÓ˜\\™URVQš\š[LN’‘•œ”PM–™Ú–QÑØ›Óž”ŠÞ“‘’”Ò–YÒšÜS[Ó•Ú]NSÚËÊÐÞÛRŠÍ^Ž]SÜŽÒ•UURÌÚ™ŠÒÞœ’NUœ–•ZÞÙUÊÓ\˜YUÓÌ
ÔØNTÒ\ÒÊÒYÓQÔ”›TÛËÚÚÝRÖœS™Û•ŠÜÕL’”ÑÌ•ÕSËÎUQš“PÕ\™žVXŒS•Ú•“ÌN˜\ÑÓÌQÔšL^™Ö“P\Ð“SMŒÓÎ\›ÛÒYÖœÚ\ÌR‹ÐVQÔKÝM–œËÛÝÚÒÛŒÖ”X˜T“‘ÒÙSÙ]LÔÎQÖXLYM›ÞNÜNMÊÝZÙÍTÖRZMSŽZÙS•œËÔ–“ØÞ’SÞžM‘RYÌÚÞRÙÕØÖX[YÝœÕÑÊÎŽLUTžLTJÛYžZ››ŠÊÞ–RMØRŽLÑÙ–UÝØ˜ÕSRKÙSPÜÛÜSš“ØØÚÎZQÓUÒÎY˜›X‹Ü’žTÚÓÒMZ•ÑÚZšMNTMÔNUŒZ^œŒQÑÝPMRŽUUŒ’–PYLËÎ[QM]ÒÎÞQ™ÙV’[XŒSÕ˜[ØZ–\™\Y\VÌSœMÞÌËÍÔNSØQQ‘Vš”›Ü””[•Ó’˜ŒQY\T™œZÑT[]”Y™™\ÚSŒÒPŽ‘RÙ[ÕÓRÕ\™ÍØÑÓÕž–ÓÎ[P˜ÝÑ›P™KÝKÙ™”–VR“Ôš‘R™šRœYUL^˜™œÚš“Q]Ž^ÕMLÒL›UÑQ•Y”P‹Ü‘P•ÍX[Ü\^S’U“’ÓÐ\NRSKÝØP”UÖÛPZš[ŽSÞKÕÑ]RJÜËÙQQ˜ÍšYœM™Z”S’•ÜJÞLQY
ÖMÚÍž‹ÑNÝ[N›ÓX[”\ÌÝËËÍÛÑL‘QLMP–YšJÝž]
ÔRSÜŒ•N[ÝVRÎZÎRÜÌÔY^\Û\Ò•SY“MœÒV›V\^‘Ìž•S‹ÚMŽžžUV[SËÕR^\”ÓÍÝÑÎRÞ•ÞQ›R’š™ÝÌ‘™ÙÓÒŒÔÛ\””U\˜ÔÜ‘ÐJÒš˜šÛ]š“™\RÖZš››U›•RX–\UšÜ˜ÜÝÔ\ÌÝV]š–U›U›TLÔÎœ\YÖ’š[•VT’ŒY[‘MžRÜLÕÑ›ÚÙÐ™JØX–‹ÔMÌSž[\“˜“ÑØQš™XM\ÜÐÑÛÓÙÛ
ÑÑÒš[ÓœPšÍÍÐÕÕ•UÙÜÍ]ÍÐ˜JÐÙTÙ”Ý˜Y]Q^^“Zž‹ÔÙ˜LœšU™Ô‘Õ–Y’[Ú\[Ó]’Q’X^L]ŒÖULXŒÕÑT“ÑTÝœœÓ]Ú”–Œ–UMÎM’\ÐUœÕÝ\RSœÔ
ÌÔ”™ØÚÑUŽXÐœ[›ÑšÌTPÞÖÒT\VŒšÍ‹ÔÞ\ÍQQQÌX˜ÝÑœ˜PÖQÛVMÓYÙÐ[Ú•ÛØŒ‘œTÓŒMÞ”ÕMÕSUVRÛ“ÒÌMÓ™STNTPÐËÑRMÑÓLÔÐY•ÒKÞÌU’ŠÜR^™Ý•ÜYVR”RÛ]”MÚÒ™^QSV\YXÌÑ•žœTŒ“–ZTTÜ™’ÝÍŠÍ™‘ÓÖ[“UÙŠÙZ•“PZÞ’–R–MP]ÝXžTZ[ÚŒS–›^–™ÖT‘ÙšÕÎÛÓLUV[]]ØÔ’ŒÒ’““]]TP[˜ÖJØ“TÒÛÐ\Ö›LØÙÌ[Ø[ÚQØÒÚ™XÊÚ”ÑRÍ\ÕØ\“US\Ý[TžžZ’ÑÌÕTÑPPÑÖ’œ\Ð–\›\ÒÐÜÖLÑÐÓ•ÞPŽYÝR–˜P”Ý[”Î“ÚÕLžXZMšÌÙ[ËÚQT^ÖœTNUZQ’ÐLœÌžMÍ˜ÚÓÛZÜœ–Ù–PN[ÓÊÓŽ
ØP˜Už“L’ÚM\]šŒœÒMÖRR‘ÕŠÒŒŒ”ÌÖJÛÞQÓ]Xœ“ÕœLTÝÑJÖPÔYMQÍ›ÙÔÓYNU˜™ZÔV[ÍLT”R™‘”TR[\Zš‘ÑRÔNUSÙÔœKÚÚ›–˜”UÍÒ“Y‘–ŽMXXœÒÜÜ[XS˜V\‘Ô›ÚŒ”Ðš”ÌÛSŒÐ[”ÍKÔŒŒÕY^
ÔÜØN^“ÙÑ‹ÕÒÙÝ™‘Uœ•žŒÑZÍZÊÛLÚÕZ’RRSÎ^LÛÝ\–ÓÑÕ\PYÒšÌÍ””VUMÒ\^”œÝÒÚÛTÖÞ^ZœÑ›‘Ø™PÍY›ŒŒÒÊÒÔÌ’ŒP•ÎŒŒ^LÕÊÊËÍVPšMÖU\Ò\ÙÜ’\ÖZSS”ÙÞ•ŒØMÑR™TLŒR˜L^“ÝÚ˜ŠÔÔ‘ÌLšZYÓÕÖNQUÕ“RMÕÜ–MZZŒžZMÝÌØÔ”[KÛŒSNXÚÓØÍTÍMMÌUÍšNÖUÜœ›•–UZYÜÙQ•ÛÙRJÙ]ÒÝÑL’ÍTÑ–PUØØ^Û˜JÕÕ‘ÜÎSRŠÎLÕÊÍÔNS[“ÎXKÌÔœ‹ÔZÒÞÜ[M”œZØ›™QT–“˜™MÌ“QŠÜÒX•U•ÙŒYÑ–šÍ‘›Ù[M›RU•LÑKÓžÔš›ËÜÕžLN]ÓY]’Ý“\šÑÌ[œ“Õ˜žL“M^Z“Q–[Ö™ŠÛSTP^VSšLŠÒ‘ÕÖL“šVLPÙÐTÐÓŠÑ]ÖŠÓÒL^’X›™ÙSÛÛš‘ÛÛL˜Ý›TŒ“\Ô]ÜNTZžSÛ\ÑMR‘”MËÖŽ’Q™]L’SRM–Õ›’ÚÙžMVVM“ŽL“UPÑÐLTÞ˜•SØš•ŒœÛ•’™˜Ô‹ÙY›[ÑŒYL’SÛUZ•“ËÐšTÌžÛ––RÖXš•\X]]]LPÓŒRŽYZÍ^›˜ÜÚ
ÍÚÓT›Óš˜ÝÛÌ˜Ò]Ý•ÐÕ–RZÞ““Ó”žÔ‘ÒŠÕœY‘ÞQ“ÑÛÝÐ™ÜTÖ”KÚÙŒØ‘‹ÒL^ž›“Ò”Ô[Q‘“Z›Z›‘Z’ÚVÔÓ‹Í˜\œL“ÜV“][ÓNUY–PÑML]ÎL“^]ÚœœN^šSÜ]ÑÎšÕÒPÍÚŒÚÚTMÒU™ÚMÝÜP[ÌÙZÞSS[ÛQÞ™YÒZRÝÚØURQŒ^QÚMMYšÜÓ•RZžšÑÙ]š\UÍLÓ‹ÕÓ”ËÍ
ÜÞžSQÜÛšÌØÙ˜ÛRQœ]ž\‘V
ÔÙ›ÍT™žRY\ÛÊÒ^œ[Ù‹ÖœÜR•ÔTYKÝMYXÐX’‘NJÓX\ÒRÜX•ÓÖY›QÌT“ÜNPL–VÛŒ•ÓLŒÌ™’ÝœÐÓRØÕVYÌÙ\U\–›MZR’RÓœÛM•šŒÜR“•TÑÛ\ØÝ’ÖÒÖ”JÝÌšØÊÌÙRØ’ÞXÙM“XÜ’ÒVTÍÐ‘Ù]ÒÓ“YÍÊÔŽM›•YÜRÚV™ÝœÙ^\œV‹Ø˜ÌÌPMœKÕM^“œTJÝžš[ÊÚM•ŒÞSTV”\›Ý›žÝ™ŒYÌQÚšÕ”–™ËÒÕLÐ”NYÑŠÌÙžÔ’ÖÝL^L]ÌØS“^]ÜSÕVÛŒÞÙÜ]’ž“L“ÐTÑ›ŠÊØ‘L›TœMÑÓLØ]ÕÔÔN•ÍŽT•Nš‘Û“T”XÓ[ÊÝ^žM–^^ÜÙ›””Ó™ÌÌÝÒ•ÒšÌÞPÔUÍL”ÊÐZÙÌÑŽM™”™ŠÚ\š™SÑU–šÔÔËÙ–L˜™N˜’^MV›‹Ý‘’M™Îž\XPRÞØÚY\Ú›P’•’œ]žšÑÝ‘JÓÑÒÛQÎZŒ\YS“’RZÑ^XUÖ’“YYŒ”œÍ“™œUÔ’ÔÞYÑ“Ó
ÒÒ\ÛÎSÖÜL”‹ÕTšœ[UMÍÛR]T\ÚœLœ›S[UYRÔÔÓ™ÍÜPXL›\ÊÑMRSÛÓYÛÚžœR”\V’\Ù’˜œ’ÔŒÝ–ž‹Í
ÜZ[›•Ù”ÚTÔV’Ž\Ó•ÕY‘Íž•ÓÔÛUÚÓš^TÒÞÚ›’ÕQÕÜTYŽ•“Ô[RÓQšÜ˜’LÑRUNÜ
Ó\Ô™ÜUKÙ[”ÒU[ÛÔÚ™š•[›‘Q˜ÌM]N^\Í‘ÛVžÝ–™“–JÚÖPÛÍMÔV\ÛÎXÍÕž\ÑšY›V\STÊÞ\ÑÝÖžœÐKÖŒÝ“’™ÎÔÞ^S\Ž]Ò‹Þ]\œŒR‘SÕ›ÝÔ›V”ÑTQšTRÞšÛ‘ZÑÌR™ÑÐŒœÐ™’ŠÙÜTSŒØJÎ‹ËÖÔ”’SœÑÓ‹ÓÕ–Œ˜\ZUŒU]››“ÒPU•ŒÌUÓÕÛÜT–ÌÍÍ’\Ú”ÍÝ]Û^YPRZÕQ“Õ•ÙKÓÖ“Ñ“LM’SŠÎ]ÛØÜÝ™ŒŠÙ›ÝÜLTŒœÖ–P‘œ–U›ÙžQŽZÖÒšÎÒÜÞšÝ\ÞR•][žŽ–’TÝÑ[ÓM’•QÝV‹ÔÝ’•Ð™V–’SžÍÜZÓ•’RÒŠÝœÔÞÔ
ÍZÜ‹ÑÙžZ]˜™ÎÛJÑKÚP““‘MRTL\ZUÎRPÚQÖ–™žSQšÕœ•˜ÒXTÔÐÙXÝÍSÜÙ•›ØMÍÚMÍ–žR[ÓLÜš]JÚL”Ù]Ð–Ñ\–ZÞŒ[ÝS”ÕSÍÓÎZÖÓ[žŽMÜ™UÔZ•\˜ZÍÔ”ž\ÑŠÖÓžœXØÛÓÌËÌÎYVRœ’XšÞ“’YL^M‘™S]ÒSS›Ù–V™šMLLPÐPÌÑZVÒÕS––L]žYÔV‘UÍËÝŠÙØÖÔ‘ž˜V–”LŒËÕž]Ò““RP”PYÐšSÓ[™šS˜žRÑTV’™LV˜ÊÍÌœ”^RL–]ØZ\ÒÞ›UÒLZ’ŒŒÎJÔSS“”’ÌÕ’Ò‹ÎPÒ–U™]žSÍÓÒMMNMÒÍQÙÓÙÑÛSÕÝÔ\›™’ÕUZŒUÜÌÍLÖ“‘ÚÔœQ\Í\–”NSš˜’ž’Ð[œRž]Ø[ZMMÍÔÚ
Û’MÛÐ\NœÖœ˜\™ZšS–œ]Ñ™ØŽ[Í”ÒL›žM””[\ZM]YZÒ“”ÝœQÓšMLÙž•“Ñ•TXTŒÑL•ÕŒMÔ\™ÝÔ[ÕVÝZœ‘MÝÑ“ÒÝÚÜÌÕ‘QÓM›XÜ™ÌQŒÙZÒ“ÐLLÙZœYÒÓÔœU–šÓUKÛ“Ì›žM›ZY‹ÒQ^ŒS‹Ú[›ÚŽMRRÙZÖ“ÔÎ]ÞNU]ÔXMMÍYÓŠÖTÓŒ–Ñ^TXŽTÒÓÕÙÞ›“JÒÚY•ÕXNÚÝŽ\ÒÍV’™ÜÕ“ÕU’™ÓÎM’’œVžÝMQMTPT–ŠÙž]Þ^XUÚ‘[˜UÍÝRÒÊÚ“–“›’žT”UžŒRRÙÙœÑ]‹ØÔÚÎTZÍÙÍ•ÒšZÖžÖ\ÌÑÓT‘ÑZRÕÔÝSUÌTÍ“œ[T›Ó•“ÑZÌŠÒ•ÒUJÔ\˜ŒXP–•RÔ\X˜ZÍÕT\YLÑŒÓÜÌÕÔLKÎYZRXÙY”PPPPPTÕU“Ô’ÍPÖRROIÊKŸB‚™YˆÜÙ\™WÜÚ]WÜ™\ÛÝ\˜ÙJš[[˜[YJN‚ˆ\Ú×Ü][ÜËœ]š›Ú[ŠÒUWÑT‹š[[˜[YJBˆYˆÜËœ]š\Ùš[J\Ú×Ü]
N‚ˆ™]\›ˆÙ[™Ùœ›ÛWÙ\™XÝÜžJÒUWÑT‹š[[˜[YJBˆ][OQSP‘QQÔÒUK™Ù]
š[[˜[YJBˆYˆ][N‚ˆÝ\KZ][Bˆ™]\›ˆ™\ÜÛœÙJØ\WØ˜XÛÙJ
KÛÛ[Ý\OXÝ\JBˆ™]\›ˆ™\ÜÛœÙJ“›Ý›Ý[™‹Ý]\ÏMÛÛ[Ý\OH^ÜZ[ŽÈÚ\œÙ]]]‹NŠB‚ˆÈŒLK‹Ž8 %[YÜ˜]YX›XÈÙXœÚ]H
ÈšX[ÚYÛ\œšYÙK‚ˆÈ\ÙH[ˆXœÛÛ]H›Û\ˆ˜\ÙYÛˆ\œHÛÈ™[™\ˆØ[ˆÙ\™HHÙXœÚ]H]™[ˆY‚ˆÈHÙ\šXÙHÛÜšÚ[™È\™XÝÜžHY™™\œÈœ›ÛHH›Ú™XÝ\™XÝÜžK‚”ÒUWÑTˆHÜËœ]š›Ú[ŠÜËœ]™\›˜[YJÜËœ]˜XœÜ]
×Ùš[W×ÊJKœÚ]HŠB‚\™Ù]
‹ÜÚ]HŠB\™Ù]
‹ÜÚ]KÈŠB™YˆX›X×ÜÚ]WÚÛYJ
N‚ˆ™]\›ˆÜÙ\™WÜÚ]WÜ™\ÛÝ\˜ÙJš[™^š[ŠB‚”P“P×ÔÒUWÔQÑTÏYœ›Þ™[œÙ]
ÉÚ[	Ë	Üš]˜XÞK\ÛXÞIË	ØX›Ý]	Ë	Ü›ÛÙ™\‹\Ù]\	Ë	Ü™\ÜÝ\™K\Ù]\	Ë	Ü™Y[™XØ[˜Ù[][Û‰Ë	ØÛÛ[Y\˜ÚX[\Ù]\	Ë	Ý\›\Ë[Ù‹]\ÙIË	ØÛÛXÝ\Ý\Ü	Ë	Ý\Ü˜YIË	Û[™ØØ\[™Ë\Ù]\	Ë	ÜšXÚ[™ÉË	Ù™X]\™\ÉË	ÛÙÚ[‰Ë	Ù˜\IË	ÜÝ\Yœ™YK]šX[	Ë	ÝšX[\ÚYÛ\	Ë	Ü]š[™Ë\Ù]\	Ë	ÜÛ›ÝË\Ù]\	Ë	ØÚÛÜÙK\[‰Ë	ØÚXÚÛÝ]	Ë	ÚÝËZ]]ÛÜšÜÉË	Ú[™\ÝšY\ËÜ]š[™Ë\ÙX[ÛØ][™ÉË	Ú[™\ÝšY\ËÜ™\ÜÝ\™K]Ø\Ú[™ÉË	Ú[™\ÝšY\ËÜ›ÛÙš[™ÉË	Ú[™\ÝšY\ËØÛÛ[Y\˜ÚX[\›Ü\IË	Ú[™\ÝšY\ËÛ[™ØØ\[™ÉË	Ú[™\ÝšY\ËÜÛ›ÝË\™[[Ý˜[	×JB‚™YˆX›X×ÜYÙWÜ™Y\™XÝ
\Ý[˜][ÛŠN‚ˆ]Y\žO\™\]Y\Ýœ]Y\žWÜÝš[™Ë™XÛÙJ›][‹LHŠBˆ™]\›ˆ™Y\™XÝ
\Ý[˜][ÛŠÊÈŠÜ]Y\žHYˆ]Y\žH[ÙHˆŠKÛÙOLÌ
B‚\™Ù]
‹ÜÚ]KÏ]™š[[˜[YOˆŠB™YˆX›X×ÜÚ]WÙš[Jš[[˜[YJN‚ˆYˆš[[˜[YH[ˆÈ›ÙÚ[ˆ‹›ÙÚ[‹š[ŸNœ™]\›ˆX›X×ÜYÙWÜ™Y\™XÝ
‹ÙX[\‹[ÙÚ[ˆŠBˆYˆš[[˜[YOOHš[™^š[Žœ™]\›ˆX›X×ÜYÙWÜ™Y\™XÝ
‹ÜÚ]KÈŠBˆYˆš[[˜[YK™[™ÝÚ]
‹š[ŠH[™š[[˜[YVÎ‹MWH[ˆP“P×ÔÒUWÔQÑTÎ‚ˆ™]\›ˆX›X×ÜYÙWÜ™Y\™XÝ
‹ÜÚ]KÈŠÙš[[˜[YVÎ‹MWJBˆYˆš[[˜[YH[ˆP“P×ÔÒUWÔQÑTÎ™š[[˜[YJÏH‹š[‚ˆ™]\›ˆÜÙ\™WÜÚ]WÜ™\ÛÝ\˜ÙJš[[˜[YJB‚\™Ù]
‹Ù˜]šXÛÛ‹šXÛÈŠB™YˆX›X×Ù˜]šXÛÛŠ
N‚ˆ™]\›ˆÜÙ\™WÜÚ]WÜ™\ÛÝ\˜ÙJ˜\ÜÙ]ËÙ˜]šXÛÛ‹œÝ™ÈŠB‚\™Ù]
‹ÜšXÚ[™ÈŠB\™Ù]
‹ÜšXÚ[™Ëš[ŠB™YˆX›X×ÜšXÚ[™×Ù\™XÝ

N‚ˆ™]\›ˆX›X×ÜYÙWÜ™Y\™XÝ
‹ÜÚ]KÜšXÚ[™ÈŠB‚ˆÈœšY[™H\™XÝ›Ý]\È\ÙY\š[™ÈÚYÛ\\Ý[™Ë‚\™Ù]
‹ÝšX[\ÚYÛ\š[ŠB™YˆX›X×ÝšX[ÜÚYÛ\Ù\™XÝ

N‚ˆ™]\›ˆX›X×ÜYÙWÜ™Y\™XÝ
‹ÜÚ]KÝšX[\ÚYÛ\ŠB‚\™Ù]
‹Ü›ÛÙ™\‹\Ù]\š[ŠB™YˆX›X×Ü›ÛÙ™\—ÜÙ]\Ù\™XÝ

N‚ˆ™]\›ˆX›X×ÜYÙWÜ™Y\™XÝ
‹ÜÚ]KÜ›ÛÙ™\‹\Ù]\ŠB‚\œÜÝ
‹Ø\KÜX›XËÜÚYÛ\ŠB™YˆX›X×ÜÚYÛ\

N‚ˆ\™\]Y\Ý™Ù]ÚœÛÛŠÚ[[UYJHÜˆßBˆ˜[YO\ÝŠ™Ù]
›˜[YHŠHÜˆˆŠKœÝš\

NÈÛÛ\[žO\ÝŠ™Ù]
˜ÛÛ\[žHŠHÜˆˆŠKœÝš\

Bˆ[XZ[\ÝŠ™Ù]
™[XZ[ŠHÜˆˆŠKœÝš\

K›ÝÙ\Š
NÈ\ÜÝÛÜ™\ÝŠ™Ù]
œ\ÜÝÛÜ™ŠHÜˆˆŠBˆÛÝ[žO\ÝŠ™Ù]
˜ÛÝ[žHŠHÜˆØ[˜YHŠKœÝš\

Bˆ[™\ÝžO\ÝŠ™Ù]
š[™\ÝžHŠHÜˆœ›ÛÙš[™ÈŠKœÝš\

K›ÝÙ\Š
BˆYˆ[™\ÝžH›Ý[ˆÈœ›ÛÙš[™È‹œÛ›ÝÈ‹œ™\ÜÝ\™H‹œ]š[™È‹›[™ØØ\[™È‹˜ÛÛ[Y\˜ÚX[ŸNˆ[™\ÝžOHœ›ÛÙš[™È‚ˆYˆ›Ý˜[YHÜˆ›ÝÛÛ\[žHÜˆ›Ý[XZ[Üˆ[Š\ÜÝÛÜ™
O‚ˆ™]\›ˆœÛÛšYžJ\œ›ÜH“˜[YK\Ú[™\ÜÈ˜[YK[XZ[[™H\ÜÝÛÜ™Ùˆ]X\ÝÚ\˜XÝ\œÈ\™H™\]Z\™YˆŠKˆY\ÝŠ]ZY]ZY

JNÈÜ™X]Y][YKœÝ™[YJ‰VKI[KIY	R‰SN‰TÖˆ‹[YK™Û][YJ
JNÈ[Z]TS—ÓSRUÖÈšX[—Bˆ›Ùš[O^È›˜[YHŽ›˜[YK˜ÛÛ\[žHŽ˜ÛÛ\[žK™[XZ[Ž™[XZ[˜ÛÝ[žHŽˆÐHˆYˆÛÝ[žK›ÝÙ\Š
KœÝ\ÝÚ]
˜Ø[ˆŠH[ÙH•TÈ‹˜\Ú[™\ÜÕ\HŽš[™\Ýž_BˆÛÛY\Ý[X]WÙŠ
BˆžN‚ˆYˆÙÚ[—Ù[XZ[Ú[—Ý\ÙJÛÛ‹[XZ[
N‚ˆ™]\›ˆœÛÛšYžJ\œ›ÜH[ˆY\šT][ÝHXØÛÝ[[™XYH^\ÝÈÚ]][XZ[ˆŠKBˆÛÛ‹™^XÝ]J’S”ÑT•S•ÈX[\œÊYX[\—Û˜[YK[XZ[\ÜÝÛÜ™Ú\ÚÝ]KÝ]\ËÛÚÝ\Û[Z]\Ý[X]WÛ[Z]Ü™X]YØ][—ØÛÙK[™\ÝžJHSQTÊËËËËË	ØXÝ]™IËËËËËÊH‹
Y˜[YK[XZ[\ÜÝÛÜ™Ú\Ú
\ÜÝÛÜ™
Kˆ‹[Z][Z]Ü™X]YšX[‹[™\ÝžJJBˆÛÛ‹™^XÝ]J’S”ÑT•S•ÈX[\—Ü›Ùš[\ÊX[\—ÚY›Ùš[WÚœÛÛ‹\]YØ]
HSQTÊËËÊH‹
YœÛÛ‹™[\Ê›Ùš[JKÜ™X]Y
JNØÛÛ‹˜ÛÛ[Z]

Bˆš[˜[NˆÛÛ‹˜ÛÜÙJ
BˆÙ\ÜÚ[Û‹˜ÛX\Š
NÜÙ\ÜÚ[Û–È™X[\—ÚY—OYYÜÙ\ÜÚ[Û–È™X[\—Û˜[YH—O[˜[YNÜÙ\ÜÚ[Û–È˜XØÛÝ[Ý\H—OH›ÝÛ™\ˆ‚ˆ™]\›ˆœÛÛšYžJÚÏUYK™Y\™XÝJ‹ÜÚ]KÜÛ›ÝË\Ù]\š[ˆYˆ[™\ÝžOOHœÛ›ÝÈˆ[ÙH‹ÜÚ]KÜ™\ÜÝ\™K\Ù]\š[ˆYˆ[™\ÝžOOHœ™\ÜÝ\™Hˆ[ÙH‹ÜÚ]KÜ]š[™Ë\Ù]\š[ˆYˆ[™\ÝžOOHœ]š[™Èˆ[ÙH‹ÜÚ]KÛ[™ØØ\[™Ë\Ù]\š[ˆYˆ[™\ÝžOOH›[™ØØ\[™Èˆ[ÙH‹ÜÚ]KØÛÛ[Y\˜ÚX[\Ù]\š[ˆYˆ[™\ÝžOOH˜ÛÛ[Y\˜ÚX[ˆ[ÙH‹ÜÚ]KÜ›ÛÙ™\‹\Ù]\š[ŠK[HšX[‹[™\ÝžOZ[™\ÝžKYX\Ý\™[Y[Û[Z][[Z]
B‚‚’PQÓÑ‘’PÑWÑPST”×ÒS\ˆˆˆYØÝ\H[[XYY]HÚ\œÙ]H]‹N]OY\šT][ÝHX[\ˆX[˜YÙ[Y[Ý]O‚Ý[O˜›Ù^Ù›ÛY˜[Z[N\šX[Ø˜XÚÙÜ›Ý[™ˆÙŒYYŽNØÛÛÜŽˆÌMÌŒL˜ŽÛX\™Ú[ŽŒKÜ˜\ÛX^]ÚYŒLLÛX\™Ú[ŽŒŽ]]ÎÜY[™ÎŒMœK˜Ø\™Ø˜XÚÙÜ›Ý[™ˆÙ™™ŽØ›Ü™\‹\˜Y]\ÎŒMœØ›Þ\ÚYÝÎŒŽÌŽÜY[™ÎŒŒœÛX\™Ú[‹X›ÝÛNŒNZKžØÛÛÜŽˆÌL˜MÎÛX\™Ú[‹]ÜŒKÜÙ\Ü^N™›^Ú\ÝYžKXÛÛ[œÜXÙKX™]ÙY[ŽØ[YÛ‹Z][\Î˜Ù[\ŽÙØ\ŒLœK™ÜšYÙ\Ü^N™ÜšYÙÜšY][\]KXÛÛ[[œÎŒYœˆYœŽÙØ\ŒLœK™[ÙÜšYXÛÛ[[ŽŒKËL_[X™[Ù›Û]ÙZYÚŽÙ\Ü^N˜›ØÚÎÛX\™Ú[Ž\Z[œ]Ù[XÝÝÚYŒL	NØ›Þ\Ú^š[™Î˜›Ü™\‹X›ÞÜY[™ÎŒL\Ø›Ü™\ŽŒ\ÛÛYØØ™XÙNØ›Ü™\‹\˜Y]\ÎŽÙ›Û\Ú^™NŒM\X]Û‹˜žÙ\Ü^Nš[›[™KX›ØÚÎØ›Ü™\ŽŒØ›Ü™\‹\˜Y]\ÎŽ\ÜY[™ÎŒL\M\Ø˜XÚÙÜ›Ý[™ˆÌMÍØÎØÛÛÜŽˆÙ™™ŽÙ›Û]ÙZYÚŽLÝ^YXÛÜ˜][ÛŽ››Û™NØÝ\œÛÜŽœÚ[\ŸKœÙXÛÛ™\ž^Ø˜XÚÙÜ›Ý[™ˆÙ™™ŽØÛÛÜŽˆÌMÍØÎØ›Ü™\ŽŒ\ÛÛYÌMÍØÎK›\ÙÞÜY[™ÎŒLØ›Ü™\‹\˜Y]\ÎŽØ˜XÚÙÜ›Ý[™ˆÙYÙŒØÛÛÜŽˆÌMÍŒ˜ŽÛX\™Ú[‹X›ÝÛNŒLœK™\œžÜY[™ÎŒLØ›Ü™\‹\˜Y]\ÎŽØ˜XÚÙÜ›Ý[™ˆÙ™™ŒŒØÛÛÜŽˆØLLNÛX\™Ú[‹X›ÝÛNŒLœ]X›^ÝÚYŒL	NØ›Ü™\‹XÛÛ\ÙN˜ÛÛ\Ù_]Ý^X[YÛŽ›YÜY[™ÎŒLØ›Ü™\‹X›ÝÛNŒ\ÛÛYÙYLÙXNÙ›Û\Ú^™NŒM]ØÛÛÜŽˆÌL˜MÎØ˜XÚÙÜ›Ý[™ˆÙŽ˜YŽ_Kœ[Ù\Ü^Nš[›[™KX›ØÚÎÜY[™ÎØ›Ü™\‹\˜Y]\ÎŽNN\Ø˜XÚÙÜ›Ý[™ˆÙYÙŒÙ›Û]ÙZYÚŽÙ›Û\Ú^™NŒLœK›™]ÛÜšÑ\Ú›Ø\™ÛX\™Ú[‹]ÜŒNK›™]ÛÜšÕÝ[ÞÙ\Ü^N™ÜšYÙÜšY][\]KXÛÛ[[œÎœ™\X]
YœŠNÙØ\Ž\ÛX\™Ú[ŽŒLœMK›™]ÛÜšÓY]šXÞØ˜XÚÙÜ›Ý[™ˆÙŽ˜Y˜ÎØ›Ü™\ŽŒ\ÛÛYÙYLÙXNØ›Ü™\‹\˜Y]\ÎŽ\ÜY[™ÎŒLK›™]ÛÜšÓY]šXÈÜ[žÙ\Ü^N˜›ØÚÎÙ›Û\Ú^™NŒL\Ù›Û]ÙZYÚŽLØÛÛÜŽˆÍXÍÌÝ^]˜[œÙ›Ü›N\\˜Ø\Ù_K›™]ÛÜšÓY]šXÈžÙ\Ü^N˜›ØÚÎÛX\™Ú[‹]ÜŒÜÙ›Û\Ú^™NŒNØÛÛÜŽˆÌL˜MßK›™]ÛÜšÕX›UÜ˜\ÛÝ™\™›ÝÎ˜]]ßK›™]ÛÜšÕX›^ÝÚYŒL	NØ›Ü™\‹XÛÛ\ÙN˜ÛÛ\ÙNÙ›Û\Ú^™NŒLœK›™]ÛÜšÕX›H›™]ÛÜšÕX›HÜY[™ÎŽ\Ø›Ü™\‹X›ÝÛNŒ\ÛÛYÙLÙNYYNÝ^X[YÛŽœšYÚÝÚ]K\ÜXÙN››ÝÜ˜\K›™]ÛÜšÕX›H™š\œÝXÚ[›™]ÛÜšÕX›H™š\œÝXÚ[Ý^X[YÛŽ›YKš[™[ÜžQÜšYÙ\Ü^N™ÜšYÙÜšY][\]KXÛÛ[[œÎœ™\X]
YœŠNÙØ\Ž\ÛX\™Ú[ŽŒLœKš[™[ÜžQ›Ü›^Ù\Ü^N™›^ÙØ\ŒLØ[YÛ‹Z][\Î™[™Ù›^]Ü˜\Ü˜\Kš[™[ÜžQ›Ü›O™]žÛZ[‹]ÚYŒNÙ›^Œ_Kš[™[ÜžP˜\žÚZYÚŒLœØ˜XÚÙÜ›Ý[™ˆÙM™X™YŽØ›Ü™\‹\˜Y]\ÎŽNN\ÛÝ™\™›ÝÎšY[ŽÛX\™Ú[‹]ÜŒLKš[™[ÜžP˜\‘š[ÚZYÚŒL	NØ˜XÚÙÜ›Ý[™ˆÌÌÍMŽØ›Ü™\‹\˜Y]\ÎŽNN\Kœ™[Ü™\[\ÛX\™Ú[‹]ÜŒLœÜY[™ÎŒLœØ›Ü™\‹\˜Y]\ÎŽ\Ù›Û]ÙZYÚŽLØ˜XÚÙÜ›Ý[™ˆÙ™™ŒØÙØ›Ü™\ŽŒ\ÛÛYÙLŽŽØÛÛÜŽˆÍ˜LKš[™[ÜžSÒÞÛX\™Ú[‹]ÜŒLœÜY[™ÎŒLØ›Ü™\‹\˜Y]\ÎŽ\Ù›Û]ÙZYÚŽØ˜XÚÙÜ›Ý[™ˆÙYÙŒØ›Ü™\ŽŒ\ÛÛYØŽYXÌŽØÛÛÜŽˆÌXÌÌŸBYYXJX^]ÚYÌ
^Ë™ÜšYÙÜšY][\]KXÛÛ[[œÎŒYœŸK™[ÙÜšYXÛÛ[[Ž˜]]ßKÜØ[YÛ‹Z][\Î™›^\Ý\Ù›^Y\™XÝ[ÛŽ˜ÛÛ[[Ÿ]X›^Ù\Ü^N˜›ØÚÎÛÝ™\™›ÝÎ˜]]ßK›™]ÛÜšÕÝ[ÞÙÜšY][\]KXÛÛ[[œÎŒYœˆYœŸKš[™[ÜžQÜšYÙÜšY][\]KXÛÛ[[œÎŒYœˆYœŸ_OÜÝ[OÚXY‚›ÙO]ˆÛ\ÜÏHÜ˜\]ˆÛ\ÜÏHÜ]OY\šT][ÝH8 %X[\ˆX[˜YÙ[Y[ÚO]’XYÙ™šXÙOÙ]Ù]]HÛ\ÜÏH˜ˆÙXÛÛ™\žHˆ™YH‹ÈPÒÈÈ“ÓÑˆTÔÑTÔÓQS•ØOˆHÛ\ÜÏH˜ˆÙXÛÛ™\žHˆ™YH‹ÛÙÛÝ]“ÑÈÕUØOÙ]Ù]‚]ˆÛ\ÜÏH˜Ø\™™]ÛÜšÑ\Ú›Ø\™’XYÙ™šXÙH™]ÛÜšÈ\Ú›Ø\™Ú‚]ˆÛ\ÜÏH›™]ÛÜšÕÝ[È‚]ˆÛ\ÜÏH›™]ÛÜšÓY]šXÈÜ[•Ý[X[\œÏÜÜ[žÞÛ™]ÛÜš×ÝÝ[ÖÈÝ[ÙX[\œÈ—__OØÙ]‚]ˆÛ\ÜÏH›™]ÛÜšÓY]šXÈÜ[XÝ]™HX[\œÏÜÜ[žÞÛ™]ÛÜš×ÝÝ[ÖÈ˜XÝ]™WÙX[\œÈ—__OØÙ]‚]ˆÛ\ÜÏH›™]ÛÜšÓY]šXÈÜ[‘\Ý[X]\ÏÜÜ[žÞÛ™]ÛÜš×ÝÝ[ÖÈ™\Ý[X]\È—__OØÙ]‚]ˆÛ\ÜÏH›™]ÛÜšÓY]šXÈÜ[›ÛÚÙYÜÜ[žÞÛ™]ÛÜš×ÝÝ[ÖÈ˜›ÛÚÙY—__OØÙ]‚]ˆÛ\ÜÏH›™]ÛÜšÓY]šXÈÜ[ÛÛ\]YÜÜ[žÞÛ™]ÛÜš×ÝÝ[ÖÈ˜ÛÛ\]Y—__OØÙ]‚]ˆÛ\ÜÏH›™]ÛÜšÓY]šXÈÜ[”›Ü\HÛÚÝ\ÏÜÜ[žÞÛ™]ÛÜš×ÝÝ[ÖÈ›ÛÚÝ\È—__OØÙ]‚]ˆÛ\ÜÏH›™]ÛÜšÓY]šXÈÜ[‘\Ý[X]H˜[YOÜÜ[‰ÞÈžÎ‹Œ™ŸH‹™›Ü›X]
™]ÛÜš×ÝÝ[ÖÈ™\Ý[X]WÝ˜[YH—J__OØÙ]‚]ˆÛ\ÜÏH›™]ÛÜšÓY]šXÈÜ[›ÛÚÙY˜[YOÜÜ[‰ÞÈžÎ‹Œ™ŸH‹™›Ü›X]
™]ÛÜš×ÝÝ[ÖÈ˜›ÛÚÙYÝ˜[YH—J__OØÙ]‚]ˆÛ\ÜÏH›™]ÛÜšÓY]šXÈÜ[ÛÛ\]Y˜[YOÜÜ[‰ÞÈžÎ‹Œ™ŸH‹™›Ü›X]
™]ÛÜš×ÝÝ[ÖÈ˜ÛÛ\]YÝ˜[YH—J__OØÙ]‚]ˆÛ\ÜÏH›™]ÛÜšÓY]šXÈÜ[[[Ý[ZYÜÜ[‰ÞÈžÎ‹Œ™ŸH‹™›Ü›X]
™]ÛÜš×ÝÝ[ÖÈ˜[[Ý[ÜZY—J__OØÙ]‚]ˆÛ\ÜÏH›™]ÛÜšÓY]šXÈÜ[“Ý]Ý[™[™ÏÜÜ[‰ÞÈžÎ‹Œ™ŸH‹™›Ü›X]
™]ÛÜš×ÝÝ[ÖÈ˜˜[[˜ÙH—J__OØÙ]‚Ù]‚]ˆÛ\ÜÏH›™]ÛÜšÕX›UÜ˜\X›HÛ\ÜÏH›™]ÛÜšÕX›HXY‘X[\Ý‘\Ý[X]\ÏÝ›ÛÚÙYÝÛÛ\]YÝ‘\Ý[X]H˜[YOÝ”ZYÝ˜[[˜ÙOÝ“ÛÚÝ\ÏÝ‘\Ý[X]H\ØYÙOÝ“\ÝXÝ]š]OÝÝÝXY›ÙO‚žÉH›Üˆˆ[ˆ™]ÛÜš×ÙX[\œÈ	_OžÞÛ‹™X[\—Û˜[Y__OØœÜ[ˆÝ[OH˜ÛÛÜŽˆÍXÍÌžÞÛ‹œÝ]HÜˆ	Éß_^ÉHYˆ‹œÝ]\ÈOIØXÝ]™IÈ	_H8 (ˆ\ØX›YÉH[™Yˆ	_OÜÜ[ÝžÞÛ–È™\Ý[X]WÝ\ÙY—__OÝžÞÛ–È˜›ÛÚÙY—__OÝžÞÛ–È˜ÛÛ\]Y—__OÝ‰ÞÈžÎ‹Œ™ŸH‹™›Ü›X]
–È™\Ý[X]WÝ˜[YH—J__OÝ‰ÞÈžÎ‹Œ™ŸH‹™›Ü›X]
–È˜[[Ý[ÜZY—J__OÝ‰ÞÈžÎ‹Œ™ŸH‹™›Ü›X]
–È˜˜[[˜ÙH—J__OÝžÞÛ–È›ÛÚÝ\Ý\ÙY—__HÈÞÛ–È›ÛÚÝ\Û[Z]—__OÝžÞÛ–È™\Ý[X]WÝ\ÙY—__HÈÞÛ–È™\Ý[X]WÛ[Z]—__OÝžÞÛ–È›\ÝØXÝ]š]H—HÜˆ¸ %Ÿ_OÝÝžÉH[™›Üˆ	_BÝ›ÙOÝX›OÙ]Ù]‚]ˆÛ\ÜÏH˜Ø\™”ÙX\ÛÛˆ›ÙXÝ[™[ÜžOÚ‚]ˆÝ[OH˜ÛÛÜŽˆÍXÍÌÙ›Û\Ú^™NŒLÜ“™]ÛÜšË]ÚYH[›š[™È\Ý[X]H˜\ÙYÛ›HÛˆ›ØœÈX\šÙYÛÛ\]YÙ]‚]ˆÛ\ÜÏHš[™[ÜžQÜšY‚]ˆÛ\ÜÏH›™]ÛÜšÓY]šXÈÜ[”Ý\[™È[™[ÜžOÜÜ[žÞÈžÎ‹ŒYŸH‹™›Ü›X]
[™[ÜžKœÝ\[™×ÙØ[ÛœÊ__HØ[ØÙ]‚]ˆÛ\ÜÏH›™]ÛÜšÓY]šXÈÜ[”›ÙXÝYYÜÜ[žÞÈžÎ‹ŒYŸH‹™›Ü›X]
[™[ÜžKœ›ÙXÝØYY
__HØ[ØÙ]‚]ˆÛ\ÜÏH›™]ÛÜšÓY]šXÈÜ[•Ý[›ÙXÝ]˜Z[X›OÜÜ[žÞÈžÎ‹ŒYŸH‹™›Ü›X]
[™[ÜžKÝ[Ø]˜Z[X›J__HØ[ØÙ]‚]ˆÛ\ÜÏH›™]ÛÜšÓY]šXÈÜ[ÛÛ\]Y›ÛÙˆ\™XOÜÜ[žÞÈžÎ‹ŒŸH‹™›Ü›X]
[™[ÜžK˜ÛÛ\]YØ\™XJ__HÜKˆØÙ]‚]ˆÛ\ÜÏH›™]ÛÜšÓY]šXÈÜ[‘\Ý[X]Y\ÙYÜÜ[žÞÈžÎ‹ŒYŸH‹™›Ü›X]
[™[ÜžK\ÙYÙØ[ÛœÊ__HØ[ØÙ]‚]ˆÛ\ÜÏH›™]ÛÜšÓY]šXÈÜ[‘\Ý[X]Y™[XZ[š[™ÏÜÜ[žÞÈžÎ‹ŒYŸH‹™›Ü›X]
[™[ÜžKœ™[XZ[š[™×ÙØ[ÛœÊ__HØ[ØÙ]‚]ˆÛ\ÜÏH›™]ÛÜšÓY]šXÈÜ[’[™[ÜžH\ÙYÜÜ[žÞÈžÎ‹ŒYŸH‹™›Ü›X]
[™[ÜžK\ÙYÜ\˜Ù[
__IOØÙ]‚]ˆÛ\ÜÏH›™]ÛÜšÓY]šXÈÜ[‘Ø[ÛœÈX›Ý™H™[Ü™\ˆ]™[ÜÜ[žÞÈžÎ‹ŒYŸH‹™›Ü›X]
[™[ÜžK™Ø[Ûœ×ØX›Ý™WÜ™[Ü™\Š__HØ[ØÙ]‚Ù]‚]ˆÛ\ÜÏHš[™[ÜžP˜\ˆ]ˆÛ\ÜÏHš[™[ÜžP˜\‘š[ˆÝ[OHÚYžÞÚ[™[ÜžK˜˜\—Ü\˜Ù[_IHÙ]Ù]‚žÉHYˆ[™[ÜžKœÝ\[™×ÙØ[ÛœÏŒ[™[™[ÜžKœ™[XZ[š[™×ÙØ[ÛœÏZ[™[ÜžKœ™[Ü™\—Û]™[	_B]ˆÛ\ÜÏHœ™[Ü™\[\”“ÑPÕSÓˆ‘SÔ‘TˆU‘S‘PPÒQ8 %\Ý[X]Y™[XZ[š[™È[™[ÜžH\ÈÞÈžÎ‹ŒYŸH‹™›Ü›X]
[™[ÜžKœ™[XZ[š[™×ÙØ[ÛœÊH_HØ[ÛœËÙ]‚žÉH[Yˆ[™[ÜžKœÝ\[™×ÙØ[ÛœÏŒ	_B]ˆÛ\ÜÏHš[™[ÜžSÒÈ’[™[ÜžH\ÈX›Ý™HH›ÙXÝ[Ûˆ™[Ü™\ˆ]™[ÙˆÞÈžÎ‹ŒYŸH‹™›Ü›X]
[™[ÜžKœ™[Ü™\—Û]™[
H_HØ[ÛœËÙ]‚žÉH[™Yˆ	_B›Ü›HÛ\ÜÏHš[™[ÜžQ›Ü›HˆY]ÙHœÜÝˆXÝ[ÛH‹ÚXY[Ù™šXÙKÚ[™[ÜžK\Ù][™ÜÈˆÝ[OH›X\™Ú[‹]ÜŒM‚]X™[”ÙX\ÛÛˆÝ\]OÛX™[[œ]˜[YOHœÙX\ÛÛ—ÜÝ\Ù]Hˆ\OH™]Hˆ˜[YOHžÞÚ[™[ÜžKœÙX\ÛÛ—ÜÝ\Ù]__Hˆ™\]Z\™YÙ]‚]X™[”ÙX\ÛÛˆÝ\[™ÈØ[ÛœÏÛX™[[œ]˜[YOHœÝ\[™×ÙØ[ÛœÈˆ\OH›[X™\ˆˆZ[HŒˆÝ\HŒŒHˆ˜[YOHžÞÚ[™[ÜžKœÝ\[™×ÙØ[Ûœß_Hˆ™\]Z\™YÙ]‚]X™[”›ÙXÝYY\ÈÙX\ÛÛˆ
Ø[
OÛX™[[œ]˜[YOHœ›ÙXÝØYYˆ\OH›[X™\ˆˆZ[HŒˆÝ\HŒŒHˆ˜[YOHžÞÚ[™[ÜžKœ›ÙXÝØYY_Hˆ™\]Z\™YÙ]‚]X™[ÛÝ™\˜YÙH\ˆØ[Ûˆ
ÜKˆŠOÛX™[[œ]˜[YOH˜ÛÝ™\˜YÙWÜ\—ÙØ[Ûˆˆ\OH›[X™\ˆˆZ[HŒHˆÝ\HŒŒHˆ˜[YOHžÞÚ[™[ÜžK˜ÛÝ™\˜YÙWÜ\—ÙØ[ÛŸ_Hˆ™\]Z\™YÙ]‚]X™[”›ÙXÝ[Ûˆ™[Ü™\ˆ]™[
Ø[
OÛX™[[œ]˜[YOHœ™[Ü™\—Û]™[ˆ\OH›[X™\ˆˆZ[HŒˆÝ\HŒŒHˆ˜[YOHžÞÚ[™[ÜžKœ™[Ü™\—Û]™[_Hˆ™\]Z\™YÙ]‚]]Ûˆ\OHœÝX›Z]”ÐU‘HS•‘S•Ô–HÑUS‘ÔÏØ]ÛÙ]‚Ù›Ü›OÙ]‚]ˆÛ\ÜÏH˜Ø\™H™YH‹ÚXY[Ù™šXÙKÜÝ\Ü”Ý\Ü™\]Y\ÝÏØOˆ0­ÈH™YH‹ÚXY[Ù™šXÙKÜÝÜ˜YÙH‘\Þ[Y[ÝÜ˜YÙHÚXÚÏØOÙ]]ˆÛ\ÜÏH˜Ø\™Ü™X]HX[\ˆXØÛÝ[ÚžÉHYˆY\ÜØYÙH	_O]ˆÛ\ÜÏH›\ÙÈžÞÛY\ÜØYÙ__OÙ]žÉH[™Yˆ	_^ÉHYˆ\œ›Üˆ	_O]ˆÛ\ÜÏH™\œˆˆ›ÛOH˜[\žÞÙ\œ›ÜŸ_OÙ]žÉH[™Yˆ	_B›Ü›HY]ÙHœÜÝ]ˆÛ\ÜÏH™ÜšY]X™[‘X[\ˆÈÝÛ™\ˆ˜[YOÛX™[[œ]˜[YOH™X[\—Û˜[YHˆ™\]Z\™YÙ]]X™[ÛÛ\[žH˜[YOÛX™[[œ]˜[YOH˜ÛÛ\[žHÙ]]X™[‘[XZ[ÈÙÚ[ÛX™[[œ]˜[YOH™[XZ[ˆ\OH™[XZ[ˆ™\]Z\™YÙ]]X™[›ÜH˜YZ[ÛÝ[žHÛÝ[žOÛX™[Ù[XÝYH˜YZ[ÛÝ[žHˆÛ˜Ú[™ÙOH™š[\YZ[”™YÚ[ÛœÊ
HÜ[Ûˆ˜[YOHÐHØ[˜YOÛÜ[ÛÜ[Ûˆ˜[YOH•TÈ•[š]YÝ]\ÏÛÜ[ÛÜÙ[XÝÙ]]X™[›ÜH˜YZ[”™YÚ[Ûˆ”›Ýš[˜ÙHÈÝ]OÛX™[Ù[XÝYH˜YZ[”™YÚ[Ûˆˆ˜[YOHœÝ]HÜ[Ûˆ˜[YOHˆÚÛÜÙH™YÚ[ÛÛÜ[ÛÜÜ›Ý\X™[HÐHÜ[ÛPÛÜ[ÛÜ[ÛÏÛÜ[ÛÜ[Û“PÛÜ[ÛÜ[Û“ÛÜ[ÛÜ[Û““ÛÜ[ÛÜ[Û“”ÏÛÜ[ÛÜ[Û“•ÛÜ[ÛÜ[Û“•OÛÜ[ÛÜ[Û“ÓÛÜ[ÛÜ[Û”OÛÜ[ÛÜ[Û”PÏÛÜ[ÛÜ[Û”ÒÏÛÜ[ÛÜ[Û–UÛÜ[ÛÛÜÜ›Ý\ÜÜ›Ý\X™[H•TÈžÉH›ÜˆÈ[ˆÝ]\È	_OÜ[Ûˆ˜[YOHžÞÜß_HžÞÜß_OÛÜ[ÛžÉH[™›Üˆ	_OÛÜÜ›Ý\ÜÙ[XÝÙ]]X™[•[\Ü˜\žH\ÜÝÛÜ™ÛX™[[œ]˜[YOHœ\ÜÝÛÜ™ˆ\OHœ\ÜÝÛÜ™ˆZ[›[™ÝHŽˆ™\]Z\™YÙ]]X™[XØÛÝ[Ý]\ÏÛX™[Ù[XÝ˜[YOHœÝ]\ÈÜ[Ûˆ˜[YOH˜XÝ]™HXÝ]™OÛÜ[ÛÜ[Ûˆ˜[YOH™\ØX›Y‘\ØX›YÛÜ[ÛÜÙ[XÝÙ]]ˆÛ\ÜÏH™[X™[”\›Z\ÜÚ[Ûˆ]™[ÛX™[[œ]˜[YOH‘X[\ˆÝÛ™\ˆˆ™XYÛ›OÙ]]ˆÛ\ÜÏH™[]Ûˆ\OHœÝX›Z]Ô‘PUHPSTˆPÐÓÕS•Ø]ÛÙ]Ù]Ù›Ü›OÙ]‚]ˆÛ\ÜÏH˜Ø\™‘X[\ˆXØÛÝ[ÏÚ‚žÉH›Üˆ[ˆX[\œÈ	_B]ˆÝ[OH˜›Ü™\ŽŒ\ÛÛYÙYLÙXNØ›Ü™\‹\˜Y]\ÎŒLœÜY[™ÎŒMÛX\™Ú[ŽŒLœ‚]ˆÝ[OH™\Ü^N™›^Ú\ÝYžKXÛÛ[œÜXÙKX™]ÙY[ŽÙØ\ŒLœØ[YÛ‹Z][\Î˜Ù[\ŽÙ›^]Ü˜\Ü˜\]Ý›Û™ÏžÞÙ™X[\—Û˜[Y__OÜÝ›Û™Ïˆ	›˜œÜÈÞÙ™[XZ[_H	›˜œÜÈÞÙœÝ]HÜˆ	Éß_O]ˆÝ[OH›X\™Ú[‹]ÜœÙ›Û\Ú^™NŒLÜ”›Ü\HÛÚÝ\ÎØˆÞÙ›ÛÚÝ\Ý\ÙY_HÈÞÙ›ÛÚÝ\Û[Z]_H	›˜œÜÈ8 (ˆ	›˜œÜÈ‘\Ý[X]\ÎØˆÞÙ™\Ý[X]WÝ\ÙY_HÈÞÙ™\Ý[X]WÛ[Z]_OÙ]Ù]Ü[ˆÛ\ÜÏHœ[žÞÙœÝ]\ß]__OÜÜ[Ù]‚žÉHYˆ	ÚXYÙ™šXÙIÈ›Ý[ˆ™X[\—Û˜[Y_ÝÙ\ˆ	_B]Z[ÈÝ[OH›X\™Ú[‹]ÜŒLœÝ[[X\žHÝ[OH™›Û]ÙZYÚŽØÝ\œÛÜŽœÚ[\ˆ‘QUPSTÜÝ[[X\žO‚›Ü›HY]ÙHœÜÝˆXÝ[ÛH‹ÚXY[Ù™šXÙKÙX[\œËÞÞÙšY_KÙY]]ˆÛ\ÜÏH™ÜšYˆÝ[OH›X\™Ú[‹]ÜŒLœ‚]X™[‘X[\ˆÈÝÛ™\ˆ˜[YOÛX™[[œ]˜[YOH™X[\—Û˜[YHˆ˜[YOHžÞÙ™X[\—Û˜[Y__Hˆ™\]Z\™YÙ]‚]X™[‘[XZ[ÈÙÚ[ÛX™[[œ]˜[YOH™[XZ[ˆ\OH™[XZ[ˆ˜[YOHžÞÙ™[XZ[_Hˆ™\]Z\™YÙ]‚]X™[”Ý]OÛX™[[œ]˜[YOHœÝ]Hˆ˜[YOHžÞÙœÝ]HÜˆ	Éß_HˆX^[™ÝHŒˆÙ]‚]X™[”›Ü\HÛÚÝ\[Z]ÛX™[[œ]˜[YOH›ÛÚÝ\Û[Z]ˆ\OH›[X™\ˆˆZ[HŒˆ˜[YOHžÞÙ›ÛÚÝ\Û[Z]_HÙ]‚]X™[‘\Ý[X]H[Z]ÛX™[[œ]˜[YOH™\Ý[X]WÛ[Z]ˆ\OH›[X™\ˆˆZ[HŒˆ˜[YOHžÞÙ™\Ý[X]WÛ[Z]_HÙ]‚]ˆÝ[OH˜[YÛ‹\Ù[Ž™[™]Ûˆ\OHœÝX›Z]”ÐU‘HPSTˆÒS‘ÑTÏØ]ÛÙ]Ù]Ù›Ü›OÙ]Z[Ï‚]Z[ÈÝ[OH›X\™Ú[‹]ÜŒLÝ[[X\žHÝ[OH™›Û]ÙZYÚŽØÝ\œÛÜŽœÚ[\ˆ”‘TÑUTÔÕÓÔ‘ÜÝ[[X\žO‚›Ü›HY]ÙHœÜÝˆXÝ[ÛH‹ÚXY[Ù™šXÙKÙX[\œËÞÞÙšY_KÜ\ÜÝÛÜ™ˆÝ[OH›X\™Ú[‹]ÜŒLÙ\Ü^N™›^ÙØ\ŽÙ›^]Ü˜\Ü˜\[œ]Ý[OH›X^]ÚYŒÌŒˆ˜[YOHœ\ÜÝÛÜ™ˆ\OHœ\ÜÝÛÜ™ˆZ[›[™ÝHŽˆXÙZÛ\H“™]È[\Ü˜\žH\ÜÝÛÜ™ˆ™\]Z\™Y]Ûˆ\OHœÝX›Z]”ÐU‘H‘UÈTÔÕÓÔ‘Ø]ÛÙ›Ü›OÙ]Z[Ï‚›Ü›HY]ÙHœÜÝˆXÝ[ÛH‹ÚXY[Ù™šXÙKÙX[\œËÞÞÙšY_KÜÝ]\ÈˆÝ[OH›X\™Ú[‹]ÜŒLœ[œ]\OHšY[ˆˆ˜[YOH˜XÝ[Ûˆˆ˜[YOHžÞÉØXÝ]˜]IÈYˆœÝ]\ÏOIÙ\ØX›Y	È[ÙH	Ù\ØX›Iß_H]Ûˆ\OHœÝX›Z]ˆÝ[OH˜˜XÚÙÜ›Ý[™žÞÉÈÌMÍØÎ	ÈYˆœÝ]\ÏOIÙ\ØX›Y	È[ÙH	ÈÍØLŒØIß_HžÞÉÐPÕUUHPST‰ÈYˆœÝ]\ÏOIÙ\ØX›Y	È[ÙH	ÑTÐP“HPST‰ß_OØ]ÛÙ›Ü›O‚žÉH[ÙH	_O]ˆÝ[OH›X\™Ú[‹]ÜŒLÙ›Û\Ú^™NŒLÜÝ›Û™Ï’XYÙ™šXÙOÜÝ›Û™Ïˆ8 %›ÝXÝYXØÛÝ[Ù]žÉH[™Yˆ	_BÙ]žÉH[™›Üˆ	_OÙ]Ù]ØÜš\‚˜ÛÛœÝYZ[”™YÚ[Û‘Ü›Ý\ÏP\œ˜^K™œ›ÛJØÝ[Y[œ]Y\žTÙ[XÝÜ[
	ÈØYZ[”™YÚ[ÛˆÜÜ›Ý\	ÊJK›X\
ÏOŠØÛÝ[žN™Ë›X™[Ü[ÛœÎ\œ˜^K™œ›ÛJËœ]Y\žTÙ[XÝÜ[
	ÛÜ[Û‰ÊJK›X\
ÏOŠÝ˜[YN›Ë˜[YK^›Ë^ÛÛ[JJ_JJNÂ˜ÛÛœÝYZ[”™YÚ[Û“Y[[ÜžO^ßNÛ]YZ[”™]š[Ý\ÐÛÝ[žOIÉÎÂ™[˜Ý[Ûˆš[\YZ[”™YÚ[ÛœÊ
^ØÛÛœÝÛÝ[žOYØÝ[Y[™Ù][[Y[žRY
	ØYZ[ÛÝ[žIÊK˜[YK™YÚ[ÛYØÝ[Y[™Ù][[Y[žRY
	ØYZ[”™YÚ[Û‰ÊNÚYŠYZ[”™]š[Ý\ÐÛÝ[žJXYZ[”™YÚ[Û“Y[[ÜžVØYZ[”™]š[Ý\ÐÛÝ[žWO\™YÚ[Û‹˜[YNÜ™YÚ[Û‹œ™\XÙPÚ[™[Š™]ÈÜ[ÛŠ	ÐÚÛÜÙH	ÊÊÛÝ[žOOOIÐÐIÏÉÜ›Ýš[˜ÙHÈ\œš]ÜžIÎ‰ÜÝ]IÊK	ÉÊJNÙ›ÜŠÛÛœÝÈÙˆYZ[”™YÚ[Û‘Ü›Ý\Ë™š[™
ÏO™Ë˜ÛÝ[žOOOXÛÝ[žJK›Ü[ÛœÊ\™YÚ[Û‹˜Y
™]ÈÜ[ÛŠË^Ë˜[YJJNÜ™YÚ[Û‹˜[YOXYZ[”™YÚ[Û“Y[[ÜžVØÛÝ[žW_	ÉÎØYZ[”™]š[Ý\ÐÛÝ[žOXÛÝ[ž_B™š[\YZ[”™YÚ[ÛœÊ
NÂÜØÜš\Ø›ÙOÚ[ˆˆˆ‚‚•T×ÔÕUTÏVÉÐS	Ë	ÐRÉË	ÐV‰Ë	ÐT‰Ë	ÐÐIË	ÐÓÉË	ÐÕ	Ë	ÑIË	Ñ“	Ë	ÑÐIË	ÒIË	ÒQ	Ë	ÒS	Ë	ÒS‰Ë	ÒPIË	ÒÔÉË	ÒÖIË	ÓIË	ÓQIË	ÓQ	Ë	ÓPIË	ÓRIË	ÓS‰Ë	ÓTÉË	ÓSÉË	ÓU	Ë	Ó‘IË	Ó•‰Ë	Ó’	Ë	Ó’‰Ë	Ó“IË	Ó–IË	ÓÉË	Ó‘	Ë	ÓÒ	Ë	ÓÒÉË	ÓÔ‰Ë	ÔIË	Ô’IË	ÔÐÉË	ÔÑ	Ë	Õ‰Ë	Õ	Ë	ÕU	Ë	Õ•	Ë	ÕIË	ÕÐIË	ÕÕ‰Ë	ÕÒIË	ÕÖIË	ÑÉ×B‚™Yˆ\×ÚXYÛÙ™šXÙJ
N‚ˆYˆÙ\ÜÚ[Û‹™Ù]
˜XØÛÝ[Ý\HŠHOH›ÝÛ™\ˆˆÜˆ›ÝÙ\ÜÚ[Û‹™Ù]
™X[\—ÚYŠN‚ˆ™]\›ˆ˜[ÙBˆÛÛY\Ý[X]WÙŠ
BˆžN‚ˆ›ÝÏXÛÛ‹™^XÝ]J”ÑSPÕX[\—Û˜[YK[XZ[Ý]\È”“ÓHX[\œÈÒT‘HYOÈ‹
Ù\ÜÚ[Û–È™X[\—ÚY—K
JK™™]ÚÛ™J
Bˆ™]\›ˆ›ÛÛ
›ÝÈ[™ÝŠ›ÝÖÈœÝ]\È—JK›ÝÙ\Š
OOH˜XÝ]™Hˆ[™
ÝŠ›ÝÖÈ™[XZ[—JKœÝš\

K›ÝÙ\Š
OOHœÙ\ÛÛYPZ][Ë˜ÛÛHˆÜˆÛÛ‹™^XÝ]J”ÑSPÕX[\—ÚY”“ÓHXØÛÝ[ØYZ[—Ü›Û\ÈÒT‘HX[\—ÚYOÈ‹
Ù\ÜÚ[Û–È™X[\—ÚY—K
JK™™]ÚÛ™J
JJBˆš[˜[N‚ˆÛÛ‹˜ÛÜÙJ
B‚‚QT’TUSÕWÐQRS—ÒS\ˆˆˆYØÝ\H[[[™ÏH™[ˆXYY]HÚ\œÙ]H]‹NY]H˜[YOHšY]ÜÜˆÛÛ[HÚYY]šXÙK]ÚY[š]X[\ØØ[OLH]OY\šT][ÝHYZ[ˆ\Ú›Ø\™Ý]O‚Ý[O‚ŠžØ›Þ\Ú^š[™Î˜›Ü™\‹X›ÞX›Ù^ÛX\™Ú[ŽŒØ˜XÚÙÜ›Ý[™ˆÙŒÙ™˜NØÛÛÜŽˆÌMÌ˜NÙ›ÛŒM\Þ\Ý[K]ZKX\K\Þ\Ý[KÙYÛÙHRK\šX[Ø[œË\Ù\šYŸZXY\žØ˜XÚÙÜ›Ý[™ˆÌL˜NØÛÛÜŽÚ]NÜY[™ÎŒX^
ŒœØ[Ê
LÈHLM
KÌŠJNÙ\Ü^N™›^Ú\ÝYžKXÛÛ[œÜXÙKX™]ÙY[ŽØ[YÛ‹Z][\Î˜Ù[\ŽÙØ\ŒNÙ›^]Ü˜\Ü˜\ZXY\ˆ^ÛX\™Ú[ŽŒÙ›Û\Ú^™NŒ\ZXY\ˆÛX\™Ú[ŽØÛÛÜŽˆØ˜Ù™NX^ØÛÛÜŽˆÌMŽXŒZXY\ˆ^ØÛÛÜŽÚ]NÝ^YXÛÜ˜][ÛŽ››Û™NØ›Ü™\ŽŒ\ÛÛYÍŒÙYØ›Ü™\‹\˜Y]\ÎŽ\ÜY[™ÎŽ\LÜ[XZ[žÛX^]ÚYŒLMÛX\™Ú[ŽŒÌ]]ÎÜY[™ÎŒNKš[›ÞÙ\Ü^N™›^Ú\ÝYžKXÛÛ[œÜXÙKX™]ÙY[ŽØ[YÛ‹Z][\Î˜Ù[\ŽÙØ\ŒM\Ù›^]Ü˜\Ü˜\Kš[›ÈžÛX\™Ú[ŽŒK›]]YØÛÛÜŽˆÍÍŸK›Y]šXÜÞÙ\Ü^N™ÜšYÙÜšY][\]KXÛÛ[[œÎœ™\X]
ËZ[›X^
YœŠJNÙØ\ŒM\ÛX\™Ú[ŽŒŒÜK›Y]šXËœ[™[Ø˜XÚÙÜ›Ý[™Ú]NØ›Ü™\ŽŒ\ÛÛYÙLYNŒNØ›Ü™\‹\˜Y]\ÎŒMØ›Þ\ÚYÝÎŒMÌLŒØŒK›Y]šXÞÜY[™ÎŒŒK›Y]šXÈÜ[žØÛÛÜŽˆÍŒÌŽÙ›Û\Ú^™NŒLÜÙ\Ü^N˜›ØÚßK›Y]šXÈÝ›Û™ÞÙ\Ü^N˜›ØÚÎÙ›Û\Ú^™NŒÜÛX\™Ú[‹]ÜŽ\Kœ[™[ÜY[™ÎŒŒÜÛX\™Ú[ŽŒNKœ[™[ÞÛX\™Ú[ŽŒÙ›Û\Ú^™NŒN\Kœ[Ù\Ü^Nš[›[™KX›ØÚÎØ›Ü™\‹\˜Y]\ÎLÜY[™Î\L\Ø˜XÚÙÜ›Ý[™ˆÙYŒ™ŽØÛÛÜŽˆÍM™Ù›Û\Ú^™NŒLœÙ›Û]ÙZYÚÌK››Ý^ÜY[™ÎŒMMœØ˜XÚÙÜ›Ý[™ˆÙÙ˜ŽØ›Ü™\‹\˜Y]\ÎŒLØ›Ü™\ŽŒ\ÛÛYÙÙMYŒÛX\™Ú[‹]ÜŒM\]X›^ÝÚYŒL	NØ›Ü™\‹XÛÛ\ÙN˜ÛÛ\ÙNÛZ[‹]ÚYŽ]Ý^X[YÛŽ›YØ›Ü™\‹X›ÝÛNŒ\ÛÛYÙMÙYÜY[™ÎŒLÜLÙ›Û\Ú^™NŒM]ØÛÛÜŽˆÍŒÌŽÙ›Û\Ú^™NŒLœÝ^]˜[œÙ›Ü›N\\˜Ø\ÙNÛ]\‹\ÜXÚ[™Î‹Œ[_]Ý›Û™ÞÙ\Ü^N˜›ØÚß]ÛX[ØÛÛÜŽˆÍÍŸKœØÜ›ÛÛÝ™\™›ÝÎ˜]]ßZ[œ]ÜY[™ÎŒL\LœØ›Ü™\ŽŒ\ÛÛYØÙYMŽØ›Ü™\‹\˜Y]\ÎŽ\Ù›Ûš[š\š]ÝÚYŒL	NÛX^]ÚYŒÍLKYÞØ˜XÚÙÜ›Ý[™ˆÙXYYYŽØÛÛÜŽˆÌNØNØ›Ü™\‹\˜Y]\ÎœÜY[™ÎÙ›Û\Ú^™NŒLœKYË›Ù™žØ˜XÚÙÜ›Ý[™ˆÙŒÙŽØÛÛÜŽˆÍÍŸK™ÜšYÙ\Ü^N™ÜšYÙÜšY][\]KXÛÛ[[œÎŒYœˆYœŽÙØ\ŒMœK™\ØX›YÛÜXÚ]N‹MNØÝ\œÛÜŽ››ÝX[ÝÙYØ›Ü™\ŽŒØ˜XÚÙÜ›Ý[™ˆØØ™YLNØÛÛÜŽˆÌÌÍMMNÜY[™ÎŒLM\Ø›Ü™\‹\˜Y]\ÎŽÙ›Û]ÙZYÚÌX]ÛŽ››Ý
™\ØX›Y
^ØÝ\œÛÜŽœÚ[\ŸPYYXJX^]ÚYÌŒ
^Ë›Y]šXÜË™ÜšYÙÜšY][\]KXÛÛ[[œÎŒYœŸKœ[™[ÜY[™ÎŒMœZXY\žÜY[™ÎŒŒ_BÜÝ[OÚXY›ÙO‚XY\]OY\šT][ÝHÜ[ˆÝ[OH™›Û]ÙZYÚ‹ÈYZ[ÜÜ[ÚOXÝ]˜][ÛœËÛÛ™\œÚ[Ûˆ	ˆ™]™[YOÜÙ]˜]ˆ\šXK[X™[HYZ[ˆ˜]šYØ][ÛˆˆÝ[OH™\Ü^N™›^Ù›^]Ü˜\Ü˜\ÙØ\ŒLH™YH‹ÚXY[Ù™šXÙKÜÝ\Ü”Ý\Ü™\]Y\ÝÏØOH™YH‹ÚXY[Ù™šXÙKÜÝÜ˜YÙH‘\Þ[Y[ÝÜ˜YÙHÚXÚÏØOH™YH‹ÜÚ]KÚ[™^š[Y\šT][ÝHÙXœÚ]OØOH™YH‹ÛÙÛÝ]“ÙÈÝ]ØOÛ˜]ÚXY\‚XZ[]ˆÛ\ÜÏHš[›È]“Ý™\šY]ÏÚÛ\ÜÏH›]]Y“X[˜YÙHY\šT][ÝHÛÙØ\™HXØÛÝ[Ëˆ\Ú[™\ÜÈ\Ý[X]\È™[XZ[ˆš]˜]HÈXXÚ\Ú[™\ÜËÜÙ]Ü[ˆÛ\ÜÏHœ[’XYÙ™šXÙOÜÜ[Ù]‚]ˆÛ\ÜÏH›Y]šXÜÈ]ˆÛ\ÜÏH›Y]šXÈÜ[”™YÚ\Ý\™YÝ\ÝÛY\ˆXØÛÝ[ÏÜÜ[Ý›Û™ÏžÞÝÝ[ØXØÛÝ[ß_OÜÝ›Û™ÏÙ]]ˆÛ\ÜÏH›Y]šXÈÜ[‘[˜X›YÝ\ÝÛY\ˆXØÛÝ[ÏÜÜ[Ý›Û™ÏžÞØXÝ]™WØXØÛÝ[ß_OÜÝ›Û™ÏÙ]]ˆÛ\ÜÏH›Y]šXÈÜ[”ÝXœØÜš\[Ûˆ™]™[YOÜÜ[Ý›Û™Ï¸ %ÜÝ›Û™ÏÛX[Û\ÜÏH›]]Y]ØZ][™ÈÝš\HÛÛ›™XÝ[ÛÜÛX[Ù]Ù]‚ÙXÝ[ÛˆÛ\ÜÏHœ[™[Ï”ÝXœØÜš\[ÛœÈ	˜[\ÈšX[ÏÚÏÛ\ÜÏH›]]Y”ZYÝXœØÜš\[ÛœË\Ü˜Y\ËØ[˜Ù[][ÛœÈ[™ÝXœØÜš\[Ûˆ™]™[YNˆÝ›Û™Ï“›ÝÛÛ›™XÝYÜÝ›Û™Ï‹ˆ\ÙHšYÝ\™\È™\]Z\™H™\šYšYYš[[™È™XÛÜ™Ëˆ[˜X›YXØÛÝ[È[™\ÜÚYÛ™Y[œÈÈ›ÝÛÛ™š\›H^[Y[Ü]ˆÛ\ÜÏHœØÜ›ÛX›H\šXK[X™[H”™YÚ\Ý˜][ÛœÈžH™\Ü[™È\š[ÙXY”\š[ÙÝÝ\ÝÛY\ˆÚYÛ\ÏÝÝ\œ™[HšX[ÝÝ\œ™[H˜\ÚXÈÈ›ÈÈ\Ú[™\ÜÏÝÛÛ\[Y[\žHX[\œÏÝ“YØXÞHÈÝ\Ý”PHÚYÛ\È^ÛYYÝÝÝXY›ÙOžÉH›ÜˆH[ˆ[—Ü™\Üœ\š[ÙÈ	_OÝ›Û™ÏžÞÛK›˜[Y__OÜÝ›Û™ÏÛX[”Ú[˜ÙHÞÛKœÝ\_OÜÛX[ÝžÞÛKœÚYÛ\ß_OÝžÞÛKšX[ß_OÝžÞÛK˜\ÜÚYÛ™YÜ[œß_OÝžÞÛK˜ÛÛ\[Y[\ž__OÝžÞÛK›YØXÞ__OÝžÞÛKœX__OÝÝžÉH[™›Üˆ	_OÝ›ÙOÝX›OÙ]Û\ÜÏH›]]Y”™YÚ\Ý˜][Ûˆ]\ÈÜ›Ý\YžHXXÚXØÛÝ[	ÜÈÝ\œ™[[‹ˆ\È\È›ÝHÛÝ[Ùˆ™]ÈZYÝXœØÜš\[ÛœÈÜˆ\ÝÜšXØ[[ˆÚ[™Ù\Ëˆ[Y\šXØKÑY[ÛÛˆØ[[™\ˆ\š[ÙÎÈÙYZÜÈ™YÚ[ˆ[Û™^KÜ]ˆÛ\ÜÏHœØÜ›ÛX›H\šXK[X™[HÝ\œ™[XØÛÝ[[œÈXYÝ\œ™[[ÝXØÛÝ[ÏÝ‘[˜X›YXØÛÝ[ÏÝÝÝXY›ÙOžÉH›Üˆ[ˆ[—Ü™\Üœ[œÈ	_OžÞÜ›X™[_OÝžÞÜÝ[_OÝžÞÜ™[˜X›Y_OÝÝžÉH[™›Üˆ	_OÝ›ÙOÝX›OÙ]]ˆÛ\ÜÏH››ÝHžÞÜ[—Ü™\ÜœXWØÛÝ[_H^XÚ]HX™[YPHXØÛÝ[È^ÛYYœ›ÛHÝ\ÝÛY\ˆÝ[È[™XÝ]˜][Ûˆ™\Ü[™ËˆH\Ú[™\ÜÈÝÛ™\ˆÜˆÛÛ\[žH˜[YH™YÚ[›š[™ÈÚ]8 'PHTÕ8 'HX\šÜÈHPHXØÛÝ[ˆÝ\ˆ[\›˜[XØÛÝ[È]\Ý™HX™[YÈ^ÛYH[Kˆ[\ÞYY\ÈÈ›ÝÛÝ[\ÈÝXœØÜš\[ÛœËÙ]ÜÙXÝ[Û‚ÙXÝ[ÛˆÛ\ÜÏHœ[™[ÏXØÛÝ[XÝ]˜][ÛœÈ	ˆ™]™[YOÚÏÛ\ÜÏH›]]Y[ˆXØÛÝ[XÝ]˜]\ÈY\ˆ]Èš\œÝÝXØÙ\ÜÙ[›Ü\HYX\Ý\™[Y[ˆXXÚ\Ú[™\ÜÈÛÝ[ÈÛ˜ÙK[˜ÛY[™ÈYX\Ý\™[Y[ÈžH]È[\ÞYY\ËÜ]ˆÛ\ÜÏHœØÜ›ÛX›OXY”\š[ÙÝ”ÚYÛ\ÏÝ‘š\œÝYX\Ý\™[Y[ÏÝ”ÚYÛ\ÛÛ™\œÚ[ÛÝ”™]™[YOÝÝÝXY›ÙOžÉH›ÜˆH[ˆY]šXÜÈ	_OÝ›Û™ÏžÞÛK›˜[Y__OÜÝ›Û™ÏÛX[”Ú[˜ÙHÞÛKœÝ\_OÜÛX[ÝžÞÛKœÚYÛ\ß_OÝžÞÛK˜XÝ]˜][Ûœß_OÝžÉHYˆK˜ÛÛ™\œÚ[Ûˆ\È›Ý›Û™H	_^ÞÛK˜ÛÛ™\œÚ[ÛŸ_IOÛX[Ý[OH™\Ü^N˜›ØÚÈžÞÛK˜ÛÚÜØXÝ]˜]Y_HÙˆÞÛKœÚYÛ\ß_HÚYÛ\ÈXÝ]˜]YÜÛX[žÉH[ÙH	_x %ÉH[™Yˆ	_OÝÝ›Û™Ï“›ÝÛÛ›™XÝYÜÝ›Û™ÏÝÝžÉH[™›Üˆ	_OÝ›ÙOÝX›OÙ]Û\ÜÏH›]]Y”™\Ü[™È[Y^›Û™Nˆ[Y\šXØKÑY[ÛÛ‹ˆÙYZÜÈ™YÚ[ˆ[Û™^KˆÛÛ™\œÚ[Ûˆ›ÛÝÜÈXØÛÝ[È™YÚ\Ý\™Y[ˆXXÚ\š[ÙÈš\œÝYX\Ý\™[Y[È[ÛÈ[˜ÛYHÛ\ˆXØÛÝ[ÈXÝ]˜][™È\š[™È]\š[ÙÜ]ˆÛ\ÜÏH››ÝHžÞØXÝ]˜]YØXØÛÝ[ß_H™XÛÜ™YXØÛÝ[XÝ]˜][ÛœËØˆš\œÝ[YX\Ý\™[Y[˜XÚÚ[™È™YÚ[œÈÚ]\È\]KˆX\›Y\ˆYX\Ý\™[Y[È]™H›È™\šYšYYXÝ]˜][Ûˆ[Y\Ý[\[™\™H›Ý˜XÚÙ]Yˆœ”™]™[YH\È›ÝÛÛ›™XÝYØˆÛÛ™š\›YYÝXœØÜš\[Ûˆ^[Y[™XÛÜ™ÈÚ[Ý\H™]™[YHY\ˆ^[Y[È\™HÛÛ›™XÝYÙ]ÜÙXÝ[Û‚ÙXÝ[ÛˆÛ\ÜÏHœ[™[]ˆÛ\ÜÏHš[›È]ÏÝ\ÝÛY\ˆXØÛÝ[ÏÚÏÛ\ÜÏH›]]Y‘š[™[ˆXØÛÝ[žH\Ú[™\ÜÈ˜[YHÜˆ[XZ[ˆ\ØYÙH[™\Ý[X]\È\™H]˜Z[X›HÈ\Ú[™\ÜÈÝÛ™\œÈ[ˆZ\ˆÝÛˆÛÜšÜÜXÙKÜÙ][œ]YHœÙX\˜Úˆ\OHœÙX\˜ÚˆXÙZÛ\H”ÙX\˜Ú\Ú[™\ÜÈÜˆ[XZ[‹‹ˆˆ\šXK[X™[H”ÙX\˜ÚÝ\ÝÛY\ˆXØÛÝ[ÈˆÛš[œ]H™š[\XØÛÝ[Ê
HÙ]]ˆÛ\ÜÏHœØÜ›ÛX›HYH˜XØÛÝ[ÈXY\Ú[™\ÜÈÈÝÛ™\Ý“ÙÚ[ˆ[XZ[Ý”[ÝXØÛÝ[ÝXÝ]˜][ÛÝÝÝXY›ÙOžÉH›ÜˆH[ˆXØÛÝ[È	_OÝ›Û™ÏžÞØK™X[\—Û˜[Y__OÜÝ›Û™ÏÝžÞØK™[XZ[_OÝžÞÉÐÛÛ\[Y[\žHX[\ˆ8 %Œ[ÛIÈYˆK˜ÛÛ\[Y[\žH[ÙH
Kœ[—ØÛÙHÜˆ	ÓYØXÞIÊ_]__OÝžÉHYˆKœÝ]\ßÝÙ\ˆOH	ØXÝ]™IÈ	_OÜ[ˆÛ\ÜÏHYÈXÝ]™OÜÜ[žÉH[ÙH	_OÜ[ˆÛ\ÜÏHYÈÙ™ˆžÞØKœÝ]\ß]__OÜÜ[žÉH[™Yˆ	_OÝžÉHYˆK™š\œÝÛYX\Ý\™YØ]	_OÜ[ˆÛ\ÜÏHYÈ“YX\Ý\™YÜÜ[žÉH[ÙH	_OÜ[ˆÛ\ÜÏH›]]Y“›Ý™XÛÜ™YÜÜ[žÉH[™Yˆ	_OÝÝžÉH[™›Üˆ	_OÝ›ÙOÝX›OÙ]ÜÙXÝ[Û‚ÙXÝ[ÛˆÛ\ÜÏHœ[™[]Z[ÏÝ[[X\žHÝ[OH˜Ý\œÛÜŽœÚ[\ŽÙ›Û]ÙZYÚÌÙ›Û\Ú^™NŒN\‘[\ÞYYHÙÚ[ˆÛÚÝ\ÜÝ[[X\žOÛ\ÜÏH›]]Y‘š[™ÚXÚ\Ú[™\ÜÈÝÛœÈ[ˆ[\ÞYYHÙÚ[‹ˆXØÙ\ÜÈ\È™XY[Û›NÈ\Ú[™\ÜÈÝÛ™\œÈX[˜YÙHZ\ˆ[\ÞYY\ËÜ[œ]\OHœÙX\˜ÚˆXÙZÛ\H”ÙX\˜Ú[\ÞYYH˜[YHÜˆÙÚ[‹‹‹ˆˆ\šXK[X™[H”ÙX\˜Ú[\ÞYYHÙÚ[œÈˆÛš[œ]H™ØÝ[Y[œ]Y\žTÙ[XÝÜ[
	ÈÙ[\ÞYYSÛÚÝ\›ÙH‰ÊK™›Ü‘XXÚ
›ÝÏOœ›ÝËšY[H\›ÝË^ÛÛ[ÓÝÙ\Ø\ÙJ
Kš[˜ÛY\Ê\Ë˜[YKÓÝÙ\Ø\ÙJ
JJH]ˆÛ\ÜÏHœØÜ›ÛX›HYH™[\ÞYYSÛÚÝ\XY‘[\ÞYYOÝ‘[\ÞYYHÙÚ[Ý”Ý]\ÏÝ\Ú[™\ÜÏÝ“ÝÛ™\ˆÙÚ[ˆ[XZ[ÝÝÝXY›ÙOžÉH›ÜˆH[ˆ[\ÞYYWØXØÛÝ[È	_OžÞÙK™[\ÞYYWÛ˜[Y__OÝžÞÙK™[\ÞYYWÙ[XZ[_OÝžÞÙK™[\ÞYYWÜÝ]\ß]__OÝžÞÙK˜\Ú[™\Ü×Û˜[Y__OÝžÞÙK›ÝÛ™\—Ù[XZ[_OÝÝžÉH[ÙH	_OÛÛÜ[HH“›È[\ÞYYHÙÚ[œÈ™XÛÜ™YÝÝžÉH[™›Üˆ	_OÝ›ÙOÝX›OÙ]Ù]Z[ÏÜÙXÝ[Û‚]ˆÛ\ÜÏH™ÜšYÙXÝ[ÛˆÛ\ÜÏHœ[™[Ï“YX\Ý\™[Y[Ü™Y]È[™X[\ˆXØÙ\ÜÏÚÏYKÍHÜˆMLYX\Ý\™[Y[[™\Ý[X]HÜ™Y]ËX[˜YÙHÛÛ\[Y[\žHX[\ˆ[ÝØ[˜Ù\Ë[™\ÜÚYÛˆØ\œ˜[Hœ˜[™[™ËÜH™YH‹ÚXY[Ù™šXÙKØÜ™Y]È“PSQÑHÔ‘QUÈS‘PSTˆPÐÑTÔÏØOÜÛX[Û\ÜÏH›]]Y•\ØYÙHÜ™Y]ÈÛ›Kˆ›È[Û™^H\È™Y[™YÜˆÚ\™ÙYÜÛX[ÜÙXÝ[ÛÙXÝ[ÛˆÛ\ÜÏHœ[™[Ï”™Y[™H\˜Ú\ÙOÚÏÛ\ÜÏH›]]Y”™]šY]È[ˆÜšYÚ[˜[^[Y[[™\ÜÝYHH[Üˆ\X[™Y[™Ü]ÛˆÛ\ÜÏH™\ØX›Yˆ\ØX›Y]OH]˜Z[X›HY\ˆÝš\H[YÜ˜][Ûˆ’\ÜÝYH™Y[™8 %ÛÛZ[™È]\Ø]ÛÜÛX[Û\ÜÏH›]]Y“›È[Û™^HØ[ˆ[Ý™Hœ›ÛH\È\Ú›Ø\™Y]ÜÛX[ÜÙXÝ[ÛÙ]‚Û\ÜÏH›]]YˆÝ[OH›X\™Ú[ŽŒÎ‘]™[ÜY[\Ú›Ø\™0­Èš[[™È[YÜ˜][ÛˆY™\œ™Y[[Y\šT][ÝH[™\ÝžHÛÜšÙ›ÝÜÈ\™HÛÛ\]KÜÛXZ[‚ØÜš\™[˜Ý[Ûˆš[\XØÛÝ[Ê
^ØÛÛœÝOYØÝ[Y[™Ù][[Y[žRY
	ÜÙX\˜Ú	ÊK˜[YKÓÝÙ\Ø\ÙJ
Kš[J
NÙØÝ[Y[œ]Y\žTÙ[XÝÜ[
	ÈØXØÛÝ[È›ÙH‰ÊK™›Ü‘XXÚ
OžÜ‹šY[H\‹^ÛÛ[ÓÝÙ\Ø\ÙJ
Kš[˜ÛY\ÊJ_J_OÜØÜš\Ø›ÙOÚ[ˆˆˆ‚‚\œÜÝ
‹Ø\KØXØÛÝ[ØXÝ]˜][ÛˆŠB™Yˆ™XÛÜ™ØXØÛÝ[ØXÝ]˜][ÛŠ
N‚ˆY\ÝŠÙ\ÜÚ[Û‹™Ù]
™X[\—ÚYŠHÜˆˆŠBˆ]O\™\]Y\Ý™Ù]ÚœÛÛŠÚ[[UYJHÜˆßBˆÚÙ[\ÝŠ]K™Ù]
ÚÙ[ˆŠHÜˆˆŠBˆYX\Ý\™[Y[TÑTÔÒSÓ”Ë™Ù]
ÚÙ[ŠBˆžNˆ[[Ý[Y›Ø]
]K™Ù]
˜[[Ý[ŠHÜˆ
Bˆ^Ù\
\Q\œ›Ü‹˜[YQ\œ›ÜŠNˆ[[Ý[LˆYˆ›ÝYX\Ý\™[Y[ÜˆYX\Ý\™[Y[™Ù]
™X[\—ÚYŠHOYYÜˆ›ÝX]š\Ùš[š]J[[Ý[
HÜˆ[[Ý[LÜˆ]K™Ù]
šÚ[™ŠH›Ý[ˆÈœ›ÛÙˆ‹˜\™XH‹›[™X\ˆŸN‚ˆ™]\›ˆœÛÛšYžJ\œ›ÜHHÝXØÙ\ÜÙ[YX\Ý\™[Y[Ûˆ[Ý\ˆ›Ü\HÙ\ÜÚ[Ûˆ\È™\]Z\™YˆŠKˆÛÛY\Ý[X]WÙŠ
BˆžN‚ˆXØÛÝ[XÛÛ‹™^XÝ]J”ÑSPÕÝ]\È”“ÓHX[\œÈÒT‘HYOÈ‹
Y
JK™™]ÚÛ™J
BˆYˆ›ÝXØÛÝ[ÜˆÝŠXØÛÝ[ÈœÝ]\È—JK›ÝÙ\Š
HOH˜XÝ]™HŽœ™]\›ˆœÛÛšYžJ\œ›ÜHXÝ]™HXØÛÝ[™\]Z\™YˆŠKÂˆÛÛ‹™^XÝ]J’S”ÑT•S•ÈXØÛÝ[ØXÝ]˜][ÛœÊX[\—ÚYš\œÝÛYX\Ý\™YØ]
HSQTÊËÊHÓˆÓÓ‘“PÕ
X[\—ÚY
HÈ“ÕS‘È‹
Y]][YK]Û›ÝÊ
Kš\ÛÙ›Ü›X]

JÈ–ˆŠJBˆÛÛ‹˜ÛÛ[Z]

Bˆš[˜[N˜ÛÛ‹˜ÛÜÙJ
Bˆ™]\›ˆœÛÛšYžJ™XÛÜ™YUYJB‚œ™YÚ\Ý\—ØÜ™Y]Ê\\Ý[X]WÙ‹\×ÚXYÛÙ™šXÙJB‚\™Ù]
‹ÚXY[Ù™šXÙKÙX[\œÈŠB™YˆY\š\][ÝWØYZ[—Ù\Ú›Ø\™

N‚ˆYˆ›Ý\×ÚXYÛÙ™šXÙJ
Nœ™]\›ˆ™\ÜÛœÙJ’XYÙ™šXÙH\›Z\ÜÚ[Ûˆ™\]Z\™Yˆ‹Ý]\ÏMÊBˆÛÛY\Ý[X]WÙŠ
BˆžN‚ˆ›ÝÜÏXÛÛ‹™^XÝ]J”ÑSPÕ™X[\—Û˜[YK™[XZ[œÝ]\Ëœ[—ØÛÙK˜Ü™X]YØ]K™š\œÝÛYX\Ý\™YØ]œ›Ùš[WÚœÛÛ‹ÓÐSTÐÑJØK˜ÛÛ\[Y[\žK
HTÈÛÛ\[Y[\žH”“ÓHX[\œÈQ•“ÒSˆXØÛÝ[Ø[ÝØ[˜Ù\ÈØHÓˆØK™X[\—ÚYYšYQ•“ÒSˆXØÛÝ[ØXÝ]˜][ÛœÈHÓˆK™X[\—ÚYYšYQ•“ÒSˆX[\—Ü›Ùš[\ÈÓˆ™X[\—ÚYYšYÒT‘HÝÙ\Š™[XZ[
OÈS‘ÝÙ\Š™X[\—Û˜[YJOÈÔ‘Tˆ–H˜Ü™X]YØ]TÐÈ‹
œÙ\ÛÛYPZ][Ë˜ÛÛH‹šXYÙ™šXÙHŠJK™™]Ú[

BˆXØÛÝ[ÏVÙXÝ
›ÝÊH›Üˆ›ÝÈ[ˆ›ÝÜ×Bˆ›ÜˆXØÛÝ[[ˆXØÛÝ[Î‚ˆžNˆXØÛÝ[È˜ÛÛ\[žH—OZœÛÛ‹›ØYÊXØÛÝ[œÜ
œ›Ùš[WÚœÛÛˆŠHÜˆžßHŠK™Ù]
˜ÛÛ\[žH‹ˆŠBˆ^Ù\
˜[YQ\œ›Ü‹\Q\œ›Ü‹]šX]Q\œ›ÜŠNˆXØÛÝ[È˜ÛÛ\[žH—OHˆ‚ˆ[—Ü™\ÜXXØÛÝ[Ü[—Ü™\Ü
XØÛÝ[ÊBˆÝ\ÝÛY\—ØXØÛÝ[Ï\[—Ü™\ÜÈ˜Ý\ÝÛY\œÈ—Bˆ[\ÞYYWØXØÛÝ[ÏVÙXÝ
›ÝÊH›Üˆ›ÝÈ[ˆÛÛ‹™^XÝ]J”ÑSPÕK™[\ÞYYWÛ˜[YKK™[XZ[TÈ[\ÞYYWÙ[XZ[KœÝ]\ÈTÈ[\ÞYYWÜÝ]\Ë™X[\—Û˜[YHTÈ\Ú[™\Ü×Û˜[YK™[XZ[TÈÝÛ™\—Ù[XZ[”“ÓHX[\—Ù[\ÞYY\ÈH“ÒSˆX[\œÈÓˆšYYK™X[\—ÚYÔ‘Tˆ–HÝÙ\ŠK™[XZ[
HŠK™™]Ú[

WBˆš[˜[N‚ˆÛÛ‹˜ÛÜÙJ
Bˆ™]\›ˆ™[™\—Ý[\]WÜÝš[™ÊQT’TUSÕWÐQRS—ÒSXØÛÝ[ÏXXØÛÝ[Ë[\ÞYYWØXØÛÝ[ÏY[\ÞYYWØXØÛÝ[Ë[—Ü™\Ü\[—Ü™\ÜÝ[ØXØÛÝ[Ï[[ŠÝ\ÝÛY\—ØXØÛÝ[ÊKXÝ]™WØXØÛÝ[Ï\Ý[JÝŠVÈœÝ]\È—JK›ÝÙ\Š
OOH˜XÝ]™Hˆ›ÜˆH[ˆÝ\ÝÛY\—ØXØÛÝ[ÊKY]šXÜÏXXØÛÝ[ÛY]šXÜÊÝ\ÝÛY\—ØXØÛÝ[ÊKXÝ]˜]YØXØÛÝ[Ï\Ý[J›ÛÛ
VÈ™š\œÝÛYX\Ý\™YØ]—JH›ÜˆH[ˆÝ\ÝÛY\—ØXØÛÝ[ÊJB‚\œ›Ý]J‹ÚXY[Ù™šXÙKÛYØXÞKYX[\œÈ‹Y]ÙÏVÈ‘ÑU‹”ÔÕ—JB™YˆXYÛÙ™šXÙWÙX[\œÊ
N‚ˆYˆ›Ý\×ÚXYÛÙ™šXÙJ
Nˆ™]\›ˆ™\ÜÛœÙJ’XYÙ™šXÙH\›Z\ÜÚ[Ûˆ™\]Z\™Yˆ‹Ý]\ÏMÊBˆY\ÜØYÙOS›Û™NÈ\œ›ÜS›Û™BˆYˆ™\]Y\Ý›Y]ÙOH”ÔÕŽ‚ˆ˜[YO\ÝŠ™\]Y\Ý™›Ü›K™Ù]
™X[\—Û˜[YHŠHÜˆˆŠKœÝš\

Bˆ[XZ[\ÝŠ™\]Y\Ý™›Ü›K™Ù]
™[XZ[ŠHÜˆˆŠKœÝš\

K›ÝÙ\Š
BˆÝ]O\ÝŠ™\]Y\Ý™›Ü›K™Ù]
œÝ]HŠHÜˆˆŠKœÝš\

K\\Š
Bˆ\ÜÝÛÜ™\ÝŠ™\]Y\Ý™›Ü›K™Ù]
œ\ÜÝÛÜ™ŠHÜˆˆŠBˆÝ]\×Ý˜[YO\ÝŠ™\]Y\Ý™›Ü›K™Ù]
œÝ]\ÈŠHÜˆ˜XÝ]™HŠKœÝš\

K›ÝÙ\Š
BˆYˆÝ]\×Ý˜[YH›Ý[ˆÈ˜XÝ]™H‹™\ØX›YŸNˆÝ]\×Ý˜[YOH˜XÝ]™H‚ˆYˆ›Ý˜[YHÜˆ›Ý[XZ[Üˆ[Š\ÜÝÛÜ™
O‚ˆ\œ›ÜH‘X[\ˆ˜[YK[XZ[[™H[\Ü˜\žH\ÜÝÛÜ™Ùˆ]X\ÝÚ\˜XÝ\œÈ\™H™\]Z\™Yˆ‚ˆ[ÙN‚ˆÛÛY\Ý[X]WÙŠ
BˆžN‚ˆ^\Ý[™Ï[ÙÚ[—Ù[XZ[Ú[—Ý\ÙJÛÛ‹[XZ[
BˆYˆ^\Ý[™Îˆ\œ›ÜHHX[\ˆXØÛÝ[Ú]][XZ[[™XYH^\ÝËˆ‚ˆ[ÙN‚ˆY\ÝŠ]ZY]ZY

JNÈÜ™X]Y][YKœÝ™[YJ‰VKI[KIY	R‰SN‰TÖˆ‹[YK™Û][YJ
JBˆÛÛ‹™^XÝ]J’S”ÑT•S•ÈX[\œÊYX[\—Û˜[YK[XZ[\ÜÝÛÜ™Ú\ÚÝ]KÝ]\ËÛÚÝ\Û[Z]\Ý[X]WÛ[Z]Ü™X]YØ]
HSQTÊËËËËËËËËÊH‹ˆ
Y˜[YK[XZ[\ÜÝÛÜ™Ú\Ú
\ÜÝÛÜ™
KÝ]KÝ]\×Ý˜[YKLMLÜ™X]Y
JBˆÛÛ‹˜ÛÛ[Z]

NÈY\ÜØYÙOH‘X[\ˆXØÛÝ[Ü™X]Yˆ[ÝHØ[ˆ›ÝÈÙÈÝ][™\Ý]X[\‰ÜÈXØÙ\ÜËˆ‚ˆš[˜[NˆÛÛ‹˜ÛÜÙJ
BˆÛÛY\Ý[X]WÙŠ
BˆžN‚ˆ˜]×ÙX[\œÏXÛÛ‹™^XÝ]J”ÑSPÕYX[\—Û˜[YK[XZ[Ý]KÝ]\ËÛÚÝ\Û[Z]\Ý[X]WÛ[Z]Ü™X]YØ]”“ÓHX[\œÈÔ‘Tˆ–HÜ™X]YØ]TÐÈŠK™™]Ú[

BˆX[\œÏV×Bˆ›Üˆˆ[ˆ˜]×ÙX[\œÎ‚ˆYXÝ
ŠBˆOXÛÛ‹™^XÝ]J”ÑSPÕ›Ü\WÛÛÚÝ\È”“ÓHX[\—Ý\ØYÙHÒT‘HX[\—ÚYOÈ‹
ÈšY—K
JK™™]ÚÛ™J
BˆÈ›ÛÚÝ\Ý\ÙY—OZ[
VÈœ›Ü\WÛÛÚÝ\È—HYˆH[ÙH
Bˆ\Ý[X]WÜ›ÝÜÏXÛÛ‹™^XÝ]J”ÑSPÕÝ[ÜšXÙK^[ØYÜ™X]YØ]”“ÓH\Ý[X]\ÈÒT‘HX[\—ÚYOÈÔ‘Tˆ–HÜ™X]YØ]TÐÈ‹
ÈšY—K
JK™™]Ú[

BˆÈ™\Ý[X]WÝ\ÙY—O[[Š\Ý[X]WÜ›ÝÜÊBˆÈ˜›ÛÚÙY—OLÈÈ˜ÛÛ\]Y—OLÈÈ™\Ý[X]WÝ˜[YH—OLŒÈÈ˜›ÛÚÙYÝ˜[YH—OLŒÈÈ˜ÛÛ\]YÝ˜[YH—OLŒÈÈ˜[[Ý[ÜZY—OLŒÈÈ›\ÝØXÝ]š]H—OHˆŽÈÈ˜ÛÛ\]YØ\™XH—OLŒˆ›Üˆ\ˆ[ˆ\Ý[X]WÜ›ÝÜÎ‚ˆÈ™\Ý[X]WÝ˜[YH—JÏY›Ø]
\–ÈÝ[ÜšXÙH—HÜˆ
BˆžNˆ\ZœÛÛ‹›ØYÊ\–Èœ^[ØY—HÜˆžßHŠBˆ^Ù\^Ù\[ÛŽˆ\^ßBˆ\Ï\ÝŠ\™Ù]
š›Ø—ÜÝ]\ÈŠHÜˆ‘\Ý[X]HŠBˆYˆ\ÏOH›ÛÚÙYŽ‚ˆÈ˜›ÛÚÙY—JÏLNÈÈ˜›ÛÚÙYÝ˜[YH—JÏY›Ø]
\–ÈÝ[ÜšXÙH—HÜˆ
Bˆ[Yˆ\ÏOHÛÛ\]YŽ‚ˆÈ˜ÛÛ\]Y—JÏLNÈÈ˜ÛÛ\]YÝ˜[YH—JÏY›Ø]
\–ÈÝ[ÜšXÙH—HÜˆ
BˆžNˆÈ˜ÛÛ\]YØ\™XH—JÏ[X^
Œ›Ø]
\™Ù]
Ý[Ø\™XHŠHÜˆ
JBˆ^Ù\^Ù\[ÛŽˆ\ÜÂˆžNˆÈ˜[[Ý[ÜZY—JÏ[X^
Œ›Ø]
\™Ù]
˜[[Ý[ÜZYŠHÜˆ
JBˆ^Ù\^Ù\[ÛŽˆ\ÜÂˆÈ˜˜[[˜ÙH—O[X^
ŒÈ™\Ý[X]WÝ˜[YH—KYÈ˜[[Ý[ÜZY—JBˆYˆ\Ý[X]WÜ›ÝÜÎ‚ˆ˜]×ØXÝ]š]OY\Ý[X]WÜ›ÝÜÖÌVÈ˜Ü™X]YØ]—BˆYˆ˜]×ØXÝ]š]N‚ˆžN‚ˆÈ›\ÝØXÝ]š]H—O\˜]×ØXÝ]š]KœÝ™[YJ‰VKI[KIYŠBˆ^Ù\^Ù\[ÛŽ‚ˆXÝ]š]WÝ^\ÝŠ˜]×ØXÝ]š]JBˆO\™KœÙX\˜Ú
ˆ—ÍKWÌŸKWÌŸH‹XÝ]š]WÝ^
BˆÈ›\ÝØXÝ]š]H—O[K™Ü›Ý\

HYˆH[ÙHXÝ]š]WÝ^ˆ[ÙN‚ˆÈ›\ÝØXÝ]š]H—OHˆ‚ˆX[\œË˜\[™

Bˆš[˜[NˆÛÛ‹˜ÛÜÙJ
Bˆ™]ÛÜš×ÙX[\œÏYX[\œÂˆ™]ÛÜš×ÝÝ[Ï^ÈÝ[ÙX[\œÈŽ›[ŠX[\œÊKˆ˜XÝ]™WÙX[\œÈŽœÝ[JH›Üˆ[ˆX[\œÈYˆÝŠÈœÝ]\È—HÜˆˆŠK›ÝÙ\Š
OOH˜XÝ]™HŠKˆ™\Ý[X]\ÈŽœÝ[JÈ™\Ý[X]WÝ\ÙY—H›Üˆ[ˆX[\œÊKˆ˜›ÛÚÙYŽœÝ[JÈ˜›ÛÚÙY—H›Üˆ[ˆX[\œÊKˆ˜ÛÛ\]YŽœÝ[JÈ˜ÛÛ\]Y—H›Üˆ[ˆX[\œÊKˆ™\Ý[X]WÝ˜[YHŽœÝ[JÈ™\Ý[X]WÝ˜[YH—H›Üˆ[ˆX[\œÊKˆ˜›ÛÚÙYÝ˜[YHŽœÝ[JÈ˜›ÛÚÙYÝ˜[YH—H›Üˆ[ˆX[\œÊKˆ˜ÛÛ\]YÝ˜[YHŽœÝ[JÈ˜ÛÛ\]YÝ˜[YH—H›Üˆ[ˆX[\œÊKˆ˜[[Ý[ÜZYŽœÝ[JÈ˜[[Ý[ÜZY—H›Üˆ[ˆX[\œÊKˆ˜˜[[˜ÙHŽœÝ[JÈ˜˜[[˜ÙH—H›Üˆ[ˆX[\œÊKˆ›ÛÚÝ\ÈŽœÝ[JÈ›ÛÚÝ\Ý\ÙY—H›Üˆ[ˆX[\œÊ_BˆÛÛY\Ý[X]WÙŠ
BˆžN‚ˆÙ][™×Ü›ÝÜÏXÛÛ‹™^XÝ]J”ÑSPÕÙ][™×ÚÙ^KÙ][™×Ý˜[YH”“ÓHXYÛÙ™šXÙWÜÙ][™ÜÈÒT‘HÙ][™×ÚÙ^HSˆ
ËËËËÊH‹
œÝ\[™×ÙØ[ÛœÈ‹˜ÛÝ™\˜YÙWÜ\—ÙØ[Ûˆ‹œ™[Ü™\—Û]™[‹œÙX\ÛÛ—ÜÝ\Ù]H‹œ›ÙXÝØYYŠJK™™]Ú[

BˆÙ][™ÜÏ^Ü–ÈœÙ][™×ÚÙ^H—Nœ–ÈœÙ][™×Ý˜[YH—H›Üˆˆ[ˆÙ][™×Ü›ÝÜßBˆš[˜[NˆÛÛ‹˜ÛÜÙJ
BˆžNˆÝ\[™×ÙØ[ÛœÏ[X^
Œ›Ø]
Ù][™ÜË™Ù]
œÝ\[™×ÙØ[ÛœÈ‹ŒŠJJBˆ^Ù\^Ù\[ÛŽˆÝ\[™×ÙØ[ÛœÏLŒˆÙX\ÛÛ—ÜÝ\Ù]O\ÝŠÙ][™ÜË™Ù]
œÙX\ÛÛ—ÜÝ\Ù]HŠHÜˆŒŒ‹LKLHŠBˆžNˆ›ÙXÝØYY[X^
Œ›Ø]
Ù][™ÜË™Ù]
œ›ÙXÝØYY‹ŒŠJJBˆ^Ù\^Ù\[ÛŽˆ›ÙXÝØYYLŒˆžNˆÛÝ™\˜YÙWÜ\—ÙØ[Û[X^
KŒ›Ø]
Ù][™ÜË™Ù]
˜ÛÝ™\˜YÙWÜ\—ÙØ[Ûˆ‹ŒÌHŠJJBˆ^Ù\^Ù\[ÛŽˆÛÝ™\˜YÙWÜ\—ÙØ[ÛLÌKŒˆžNˆ™[Ü™\—Û]™[[X^
Œ›Ø]
Ù][™ÜË™Ù]
œ™[Ü™\—Û]™[‹ŒŠJJBˆ^Ù\^Ù\[ÛŽˆ™[Ü™\—Û]™[MŒŒˆÛÛ\]YØ\™XOLŒˆÛÛY\Ý[X]WÙŠ
BˆžN‚ˆÙX\ÛÛ—Ü›ÝÜÏXÛÛ‹™^XÝ]J”ÑSPÕ^[ØY”“ÓH\Ý[X]\ÈŠK™™]Ú[

Bˆ›ÜˆÜˆ[ˆÙX\ÛÛ—Ü›ÝÜÎ‚ˆžNˆÜZœÛÛ‹›ØYÊÜ–Èœ^[ØY—HÜˆžßHŠBˆ^Ù\^Ù\[ÛŽˆÜ^ßBˆYˆÝŠÜ™Ù]
š›Ø—ÜÝ]\ÈŠHÜˆ‘\Ý[X]HŠHOHÛÛ\]YŽˆÛÛ[YBˆÛÛ\][Û—Ù]O\ÝŠÜ™Ù]
˜ÛÛ\][Û—Ù]HŠHÜˆˆŠVÎŒLBˆYˆÛÛ\][Û—Ù]H[™ÛÛ\][Û—Ù]HÙX\ÛÛ—ÜÝ\Ù]NˆÛÛ[YBˆžNˆÛÛ\]YØ\™XJÏ[X^
Œ›Ø]
Ü™Ù]
Ý[Ø\™XHŠHÜˆ
JBˆ^Ù\^Ù\[ÛŽˆ\ÜÂˆš[˜[NˆÛÛ‹˜ÛÜÙJ
BˆÝ[Ø]˜Z[X›O\Ý\[™×ÙØ[ÛœÊÜ›ÙXÝØYYˆ\ÙYÙØ[ÛœÏXÛÛ\]YØ\™XKØÛÝ™\˜YÙWÜ\—ÙØ[Û‚ˆ™[XZ[š[™×ÙØ[ÛœÏ[X^
ŒÝ[Ø]˜Z[X›K]\ÙYÙØ[ÛœÊBˆ\ÙYÜ\˜Ù[J\ÙYÙØ[ÛœËÝÝ[Ø]˜Z[X›JŒLŒ
HYˆÝ[Ø]˜Z[X›OŒ[ÙHŒˆ[™[ÜžO^ÈœÝ\[™×ÙØ[ÛœÈŽœÝ\[™×ÙØ[ÛœËœ›ÙXÝØYYŽœ›ÙXÝØYYÝ[Ø]˜Z[X›HŽÝ[Ø]˜Z[X›KˆœÙX\ÛÛ—ÜÝ\Ù]HŽœÙX\ÛÛ—ÜÝ\Ù]K˜ÛÝ™\˜YÙWÜ\—ÙØ[ÛˆŽ˜ÛÝ™\˜YÙWÜ\—ÙØ[Û‹ˆ˜ÛÛ\]YØ\™XHŽ˜ÛÛ\]YØ\™XK\ÙYÙØ[ÛœÈŽ\ÙYÙØ[ÛœËœ™[XZ[š[™×ÙØ[ÛœÈŽœ™[XZ[š[™×ÙØ[ÛœËˆ\ÙYÜ\˜Ù[Ž\ÙYÜ\˜Ù[˜˜\—Ü\˜Ù[Ž›Z[ŠLŒX^
Œ\ÙYÜ\˜Ù[
JKœ™[Ü™\—Û]™[Žœ™[Ü™\—Û]™[ˆ™Ø[Ûœ×ØX›Ý™WÜ™[Ü™\ˆŽ›X^
Œ™[XZ[š[™×ÙØ[ÛœË\™[Ü™\—Û]™[
_Bˆ™]\›ˆ™[™\—Ý[\]WÜÝš[™ÊPQÓÑ‘’PÑWÑPST”×ÒSX[\œÏYX[\œËÝ]\ÏUT×ÔÕUTËY\ÜØYÙO[Y\ÜØYÙK\œ›ÜY\œ›Ü‹™]ÛÜš×ÙX[\œÏ[™]ÛÜš×ÙX[\œË™]ÛÜš×ÝÝ[Ï[™]ÛÜš×ÝÝ[Ë[™[ÜžOZ[™[ÜžJB‚‚\œÜÝ
‹ÚXY[Ù™šXÙKÚ[™[ÜžK\Ù][™ÜÈŠB™YˆXYÛÙ™šXÙWÚ[™[ÜžWÜÙ][™ÜÊ
N‚ˆYˆ›Ý\×ÚXYÛÙ™šXÙJ
Nˆ™]\›ˆ™\ÜÛœÙJ’XYÙ™šXÙH\›Z\ÜÚ[Ûˆ™\]Z\™Yˆ‹Ý]\ÏMÊBˆžN‚ˆÝ\[™Ï[X^
Œ›Ø]
™\]Y\Ý™›Ü›K™Ù]
œÝ\[™×ÙØ[ÛœÈŠHÜˆ
JBˆ›ÙXÝØYY[X^
Œ›Ø]
™\]Y\Ý™›Ü›K™Ù]
œ›ÙXÝØYYŠHÜˆ
JBˆÛÝ™\˜YÙO[X^
KŒ›Ø]
™\]Y\Ý™›Ü›K™Ù]
˜ÛÝ™\˜YÙWÜ\—ÙØ[ÛˆŠHÜˆÌJJBˆ™[Ü™\—Û]™[[X^
Œ›Ø]
™\]Y\Ý™›Ü›K™Ù]
œ™[Ü™\—Û]™[ŠHÜˆŒ
JBˆÙX\ÛÛ—ÜÝ\Ù]O\ÝŠ™\]Y\Ý™›Ü›K™Ù]
œÙX\ÛÛ—ÜÝ\Ù]HŠHÜˆˆŠKœÝš\

BˆYˆ›ÝÙX\ÛÛ—ÜÝ\Ù]Nˆ™]\›ˆ™\ÜÛœÙJ”ÙX\ÛÛˆÝ\]H\È™\]Z\™Yˆ‹Ý]\ÏM
Bˆ^Ù\^Ù\[ÛŽ‚ˆ™]\›ˆ™\ÜÛœÙJ’[™[ÜžHÙ][™ÜÈ]\Ý™H˜[Y[X™\œËˆ‹Ý]\ÏM
BˆÛÛY\Ý[X]WÙŠ
BˆžN‚ˆ›ÜˆÙ^K˜[YH[ˆ

œÝ\[™×ÙØ[ÛœÈ‹Ý\[™ÊK
œ›ÙXÝØYY‹›ÙXÝØYY
K
˜ÛÝ™\˜YÙWÜ\—ÙØ[Ûˆ‹ÛÝ™\˜YÙJK
œ™[Ü™\—Û]™[‹™[Ü™\—Û]™[
K
œÙX\ÛÛ—ÜÝ\Ù]H‹ÙX\ÛÛ—ÜÝ\Ù]JJN‚ˆYˆUPTÑWÕT“‚ˆÛÛ‹™^XÝ]Jˆˆ’S”ÑT•S•ÈXYÛÙ™šXÙWÜÙ][™ÜÊÙ][™×ÚÙ^KÙ][™×Ý˜[YJHSQTÊËÊBˆÓˆÓÓ‘“PÕ
Ù][™×ÚÙ^JHÈTUHÑUÙ][™×Ý˜[YOQVÓQQœÙ][™×Ý˜[YHˆˆ‹
Ù^KÝŠ˜[YJJJBˆ[ÙN‚ˆÛÛ‹™^XÝ]Jˆˆ’S”ÑT•S•ÈXYÛÙ™šXÙWÜÙ][™ÜÊÙ][™×ÚÙ^KÙ][™×Ý˜[YJHSQTÊËÊBˆÓˆÓÓ‘“PÕ
Ù][™×ÚÙ^JHÈTUHÑUÙ][™×Ý˜[YOY^ÛYYœÙ][™×Ý˜[YHˆˆ‹
Ù^KÝŠ˜[YJJJBˆÛÛ‹˜ÛÛ[Z]

Bˆš[˜[NˆÛÛ‹˜ÛÜÙJ
Bˆ™]\›ˆ™Y\™XÝ
‹ÚXY[Ù™šXÙKÙX[\œÈŠB‚\œÜÝ
‹ÚXY[Ù™šXÙKÙX[\œËÏX[\—ÚY‹ÜÝ]\ÈŠB™YˆXYÛÙ™šXÙWÙX[\—ÜÝ]\ÊX[\—ÚY
N‚ˆYˆ›Ý\×ÚXYÛÙ™šXÙJ
Nˆ™]\›ˆ™\ÜÛœÙJ’XYÙ™šXÙH\›Z\ÜÚ[Ûˆ™\]Z\™Yˆ‹Ý]\ÏMÊBˆXÝ[Û\ÝŠ™\]Y\Ý™›Ü›K™Ù]
˜XÝ[ÛˆŠHÜˆˆŠKœÝš\

K›ÝÙ\Š
Bˆ™]×ÜÝ]\ÏH™\ØX›YˆYˆXÝ[ÛOH™\ØX›Hˆ[ÙH˜XÝ]™H‚ˆÛÛY\Ý[X]WÙŠ
BˆžN‚ˆ›ÝÏXÛÛ‹™^XÝ]J”ÑSPÕX[\—Û˜[YH”“ÓHX[\œÈÒT‘HYOÈ‹
X[\—ÚY
JK™™]ÚÛ™J
BˆYˆ›Ý›ÝÎœ™]\›ˆ™\ÜÛœÙJ‘X[\ˆ›Ý›Ý[™ˆ‹Ý]\ÏM
BˆYˆšXYÙ™šXÙHˆ[ˆÝŠ›ÝÖÈ™X[\—Û˜[YH—HÜˆˆŠK›ÝÙ\Š
N‚ˆ™]\›ˆ™\ÜÛœÙJ•HXYÙ™šXÙHXØÛÝ[Ø[››Ý™H\ØX›Y\™Kˆ‹Ý]\ÏM
BˆÛÛ‹™^XÝ]J•TUHX[\œÈÑUÝ]\ÏOÈÒT‘HYOÈ‹
™]×ÜÝ]\ËX[\—ÚY
JNØÛÛ‹˜ÛÛ[Z]

Bˆš[˜[NˆÛÛ‹˜ÛÜÙJ
Bˆ™]\›ˆ™Y\™XÝ
‹ÚXY[Ù™šXÙKÙX[\œÈŠB‚\œÜÝ
‹ÚXY[Ù™šXÙKÙX[\œËÏX[\—ÚY‹Ü\ÜÝÛÜ™ŠB™YˆXYÛÙ™šXÙWÙX[\—Ü\ÜÝÛÜ™
X[\—ÚY
N‚ˆYˆ›Ý\×ÚXYÛÙ™šXÙJ
Nˆ™]\›ˆ™\ÜÛœÙJ’XYÙ™šXÙH\›Z\ÜÚ[Ûˆ™\]Z\™Yˆ‹Ý]\ÏMÊBˆ\ÜÝÛÜ™\ÝŠ™\]Y\Ý™›Ü›K™Ù]
œ\ÜÝÛÜ™ŠHÜˆˆŠBˆYˆ[Š\ÜÝÛÜ™
Oœ™]\›ˆ™\ÜÛœÙJ•[\Ü˜\žH\ÜÝÛÜ™]\Ý™H]X\ÝÚ\˜XÝ\œËˆ‹Ý]\ÏM
BˆÛÛY\Ý[X]WÙŠ
BˆžN‚ˆ›ÝÏXÛÛ‹™^XÝ]J”ÑSPÕY”“ÓHX[\œÈÒT‘HYOÈ‹
X[\—ÚY
JK™™]ÚÛ™J
BˆYˆ›Ý›ÝÎœ™]\›ˆ™\ÜÛœÙJ‘X[\ˆ›Ý›Ý[™ˆ‹Ý]\ÏM
BˆÛÛ‹™^XÝ]J•TUHX[\œÈÑU\ÜÝÛÜ™Ú\ÚOÈÒT‘HYOÈ‹
\ÜÝÛÜ™Ú\Ú
\ÜÝÛÜ™
KX[\—ÚY
JBˆÛÛ‹™^XÝ]J’S”ÑT•S•ÈXØÛÝ[Ø]]Ý™\œÚ[ÛœÊXØÛÝ[Ý\KXØÛÝ[ÚY™\œÚ[ÛŠHSQTÊ	ÛÝÛ™\‰ËËJHÓˆÓÓ‘“PÕ
XØÛÝ[Ý\KXØÛÝ[ÚY
HÈTUHÑU™\œÚ[ÛXXØÛÝ[Ø]]Ý™\œÚ[ÛœË™\œÚ[ÛŠÌH‹
X[\—ÚY
JNØÛÛ‹˜ÛÛ[Z]

Bˆš[˜[NˆÛÛ‹˜ÛÜÙJ
Bˆ™]\›ˆ™Y\™XÝ
‹ÚXY[Ù™šXÙKÙX[\œÈŠB‚\œÜÝ
‹ÚXY[Ù™šXÙKÙX[\œËÏX[\—ÚY‹ÙY]ŠB™YˆXYÛÙ™šXÙWÙX[\—ÙY]
X[\—ÚY
N‚ˆYˆ›Ý\×ÚXYÛÙ™šXÙJ
Nˆ™]\›ˆ™\ÜÛœÙJ’XYÙ™šXÙH\›Z\ÜÚ[Ûˆ™\]Z\™Yˆ‹Ý]\ÏMÊBˆ˜[YO\ÝŠ™\]Y\Ý™›Ü›K™Ù]
™X[\—Û˜[YHŠHÜˆˆŠKœÝš\

Bˆ[XZ[\ÝŠ™\]Y\Ý™›Ü›K™Ù]
™[XZ[ŠHÜˆˆŠKœÝš\

K›ÝÙ\Š
BˆÝ]O\ÝŠ™\]Y\Ý™›Ü›K™Ù]
œÝ]HŠHÜˆˆŠKœÝš\

K\\Š
BˆÛÚÝ\Û[Z]Ü˜]Ï\ÝŠ™\]Y\Ý™›Ü›K™Ù]
›ÛÚÝ\Û[Z]ŠHÜˆŒLŠKœÝš\

Bˆ\Ý[X]WÛ[Z]Ü˜]Ï\ÝŠ™\]Y\Ý™›Ü›K™Ù]
™\Ý[X]WÛ[Z]ŠHÜˆŒMLŠKœÝš\

BˆYˆ›Ý˜[YHÜˆ›Ý[XZ[œ™]\›ˆ™\ÜÛœÙJ‘X[\ˆ˜[YH[™[XZ[\™H™\]Z\™Yˆ‹Ý]\ÏM
BˆžN‚ˆÛÚÝ\Û[Z][X^
[
ÛÚÝ\Û[Z]Ü˜]ÊJNÙ\Ý[X]WÛ[Z][X^
[
\Ý[X]WÛ[Z]Ü˜]ÊJBˆ^Ù\^Ù\[ÛŽœ™]\›ˆ™\ÜÛœÙJ“ÛÚÝ\[™\Ý[X]H[Z]È]\Ý™HÚÛH[X™\œËˆ‹Ý]\ÏM
BˆÛÛY\Ý[X]WÙŠ
BˆžN‚ˆ\XØ]OXÛÛ‹™^XÝ]J”ÑSPÕY”“ÓHX[\œÈÒT‘HÕÑTŠ[XZ[
OOÈS‘YÈS’SÓˆSÑSPÕY”“ÓHX[\—Ù[\ÞYY\ÈÒT‘HÕÑTŠ[XZ[
OOÈ‹
[XZ[X[\—ÚY[XZ[
JK™™]ÚÛ™J
BˆYˆ\XØ]Nœ™]\›ˆ™\ÜÛœÙJ[›Ý\ˆX[\ˆ[™XYH\Ù\È][XZ[ˆ‹Ý]\ÏM
BˆÛÛ‹™^XÝ]J•TUHX[\œÈÑUX[\—Û˜[YOOË[XZ[OËÝ]OOËÛÚÝ\Û[Z]OË\Ý[X]WÛ[Z]OÈÒT‘HYOÈ‹ˆ
˜[YK[XZ[Ý]KÛÚÝ\Û[Z]\Ý[X]WÛ[Z]X[\—ÚY
JNØÛÛ‹˜ÛÛ[Z]

Bˆš[˜[NˆÛÛ‹˜ÛÜÙJ
Bˆ™]\›ˆ™Y\™XÝ
‹ÚXY[Ù™šXÙKÙX[\œÈŠB‚‚™Yˆ\×Ù[\ÞYYJ
N‚ˆ™]\›ˆÝŠÙ\ÜÚ[Û‹™Ù]
˜XØÛÝ[Ý\HŠHÜˆˆŠOOH™[\ÞYYH‚‚™Yˆ\×ÙX[\—ÛÝÛ™\Š
N‚ˆ™]\›ˆ›ÛÛ
Ù\ÜÚ[Û‹™Ù]
™X[\—ÚYŠJH[™›Ý\×ÚXYÛÙ™šXÙJ
H[™›Ý\×Ù[\ÞYYJ
B‚‘PST—ÑSTÖQQT×ÒS\ˆˆˆYØÝ\H[[XYY]HÚ\œÙ]H]‹N]OY\šT][ÝH[\ÞYY\ÏÝ]O‚Ý[O˜›Ù^Ù›ÛY˜[Z[N\šX[Ø˜XÚÙÜ›Ý[™ˆÙŒYYŽNØÛÛÜŽˆÌMÌŒL˜ŽÛX\™Ú[ŽŒKÜ˜\ÛX^]ÚYŽLÛX\™Ú[ŽŒŽ]]ÎÜY[™ÎŒMœK˜Ø\™Ø˜XÚÙÜ›Ý[™ˆÙ™™ŽØ›Ü™\‹\˜Y]\ÎŒMœØ›Þ\ÚYÝÎŒŽÌŽÜY[™ÎŒŒœÛX\™Ú[‹X›ÝÛNŒNZKžØÛÛÜŽˆÌL˜MßK™ÜšYÙ\Ü^N™ÜšYÙÜšY][\]KXÛÛ[[œÎŒYœˆYœŽÙØ\ŒLœ[X™[Ù›Û]ÙZYÚŽÙ\Ü^N˜›ØÚÎÛX\™Ú[Ž\Z[œ]ÝÚYŒL	NØ›Þ\Ú^š[™Î˜›Ü™\‹X›ÞÜY[™ÎŒL\Ø›Ü™\ŽŒ\ÛÛYØØ™XÙNØ›Ü™\‹\˜Y]\ÎŽX]Û‹˜žÙ\Ü^Nš[›[™KX›ØÚÎØ›Ü™\ŽŒØ›Ü™\‹\˜Y]\ÎŽ\ÜY[™ÎŒL\M\Ø˜XÚÙÜ›Ý[™ˆÌMÍØÎØÛÛÜŽˆÙ™™ŽÙ›Û]ÙZYÚŽLÝ^YXÛÜ˜][ÛŽ››Û™NØÝ\œÛÜŽœÚ[\ŸK™[™Ù\žØ˜XÚÙÜ›Ý[™ˆÍØLŒØ_Kœ›ÝÞØ›Ü™\ŽŒ\ÛÛYÙYLÙXNØ›Ü™\‹\˜Y]\ÎŒLœÜY[™ÎŒMÛX\™Ú[ŽŒLK™\œžØ˜XÚÙÜ›Ý[™ˆÙ™™ŒŒØÛÛÜŽˆØLLNÜY[™ÎŒLØ›Ü™\‹\˜Y]\ÎŽK›\ÙÞØ˜XÚÙÜ›Ý[™ˆÙYÙŒØÛÛÜŽˆÌMÍŒ˜ŽÜY[™ÎŒLØ›Ü™\‹\˜Y]\ÎŽPYYXJX^]ÚYL
^Ë™ÜšYÙÜšY][\]KXÛÛ[[œÎŒYœŸ_OÜÝ[OÚXY‚›ÙO]ˆÛ\ÜÏHÜ˜\HÛ\ÜÏH˜ˆˆ™YH‹ÈPÒÈÈ“ÓÑˆTÔÑTÔÓQS•ØOÜ]ˆÛ\ÜÏH˜Ø\™O“X[˜YÙH[\ÞYY\ÏÚO‘[\ÞYY\ÈÚ\™H[Ý\ˆX[\œÚ\	ÜÈ\Ý[X]\È[™\ØYÙH[ÝØ[˜ÙKˆ^HØ[››ÝX[˜YÙHX[\œÚ\Ù][™ÜÈÜˆÝ\ˆ[\ÞYY\ËÜ‚žÉHYˆY\ÜØYÙH	_O]ˆÛ\ÜÏH›\ÙÈžÞÛY\ÜØYÙ__OÙ]žÉH[™Yˆ	_^ÉHYˆ\œ›Üˆ	_O]ˆÛ\ÜÏH™\œˆˆ›ÛOH˜[\žÞÙ\œ›ÜŸ_OÙ]žÉH[™Yˆ	_BÜ™X]H[\ÞYYHÙÚ[Ú›Ü›HY]ÙHœÜÝ]ˆÛ\ÜÏH™ÜšY]X™[‘[\ÞYYH˜[YOÛX™[[œ]˜[YOH™[\ÞYYWÛ˜[YHˆ™\]Z\™YÙ]]X™[‘[XZ[ÈÙÚ[ÛX™[[œ]˜[YOH™[XZ[ˆ\OH™[XZ[ˆ™\]Z\™YÙ]]X™[•[\Ü˜\žH\ÜÝÛÜ™ÛX™[[œ]˜[YOHœ\ÜÝÛÜ™ˆ\OHœ\ÜÝÛÜ™ˆZ[›[™ÝHŽˆ™\]Z\™YÙ]]ˆÝ[OH˜[YÛ‹\Ù[Ž™[™]ÛÔ‘PUHSTÖQQOØ]ÛÙ]Ù]Ù›Ü›OÙ]‚]ˆÛ\ÜÏH˜Ø\™‘[\ÞYY\ÏÚžÉHYˆ›Ý[\ÞYY\È	_O“›È[\ÞYY\ÈY]ÜžÉH[™Yˆ	_^ÉH›ÜˆH[ˆ[\ÞYY\È	_O]ˆÛ\ÜÏHœ›ÝÈžÞÙK™[\ÞYYWÛ˜[Y__OØˆ8 %ÞÙK™[XZ[_H8 %žÞÙKœÝ]\ß]__OØ›Ü›HY]ÙHœÜÝˆXÝ[ÛH‹ÙX[\‹Y[\ÞYY\ËÞÞÙKšY_KÜÝ]\ÈˆÝ[OH›X\™Ú[‹]ÜŒL[œ]\OHšY[ˆˆ˜[YOH˜XÝ[Ûˆˆ˜[YOHžÞÉØXÝ]˜]IÈYˆKœÝ]\ÏOIÙ\ØX›Y	È[ÙH	Ù\ØX›Iß_H]ÛˆÛ\ÜÏHžÞÉÉÈYˆKœÝ]\ÏOIÙ\ØX›Y	È[ÙH	Ù[™Ù\‰ß_HžÞÉÐPÕUUIÈYˆKœÝ]\ÏOIÙ\ØX›Y	È[ÙH	ÑTÐP“Iß_OØ]ÛÙ›Ü›OÙ]žÉH[™›Üˆ	_OÙ]Ù]Ø›ÙOÚ[ˆˆˆ‚‚\œ›Ý]J‹ÙX[\‹Y[\ÞYY\È‹Y]ÙÏVÈ‘ÑU‹”ÔÕ—JB™YˆX[\—Ù[\ÞYY\Ê
N‚ˆYˆ›Ý\×ÙX[\—ÛÝÛ™\Š
Nˆ™]\›ˆ™\ÜÛœÙJ‘X[\ˆÝÛ™\ˆ\›Z\ÜÚ[Ûˆ™\]Z\™Yˆ‹Ý]\ÏMÊBˆY\ÝŠÙ\ÜÚ[Û–È™X[\—ÚY—JNÛY\ÜØYÙOS›Û™NÙ\œ›ÜS›Û™BˆYˆ™\]Y\Ý›Y]ÙOH”ÔÕŽ‚ˆ˜[YO\ÝŠ™\]Y\Ý™›Ü›K™Ù]
™[\ÞYYWÛ˜[YHŠHÜˆˆŠKœÝš\

NÙ[XZ[\ÝŠ™\]Y\Ý™›Ü›K™Ù]
™[XZ[ŠHÜˆˆŠKœÝš\

K›ÝÙ\Š
NÜ\ÜÝÛÜ™\ÝŠ™\]Y\Ý™›Ü›K™Ù]
œ\ÜÝÛÜ™ŠHÜˆˆŠBˆYˆ›Ý˜[YHÜˆ›Ý[XZ[Üˆ[Š\ÜÝÛÜ™
O™\œ›ÜH‘[\ÞYYH˜[YK[XZ[[™H[\Ü˜\žH\ÜÝÛÜ™Ùˆ]X\ÝÚ\˜XÝ\œÈ\™H™\]Z\™Yˆ‚ˆ[Yˆ›Ý˜[YÙX[\—Ü›Ùš[WÙ[XZ[
[XZ[
N™\œ›ÜH‘[\ˆH˜[Y[\ÞYYHÙÚ[ˆ[XZ[Y™\ÜËÝXÚ\È˜[YPÛÛ\[žK˜ÛÛKˆ‚ˆ[ÙN‚ˆÛÛY\Ý[X]WÙŠ
BˆžN‚ˆÈ[[\ÞYYHÜ™X]ÜœÈÚ\™HÛ™HY[]HØÚË[˜ÛY[™ÈY™™\™[ÝÛ™\œË‚ˆYˆÛÛ‹œÜÝÜ™\Î˜ÛÛ‹™^XÝ]J”ÑSPÕ×ØYš\ÛÜžWÞXÝÛØÚÊÊH‹
ŒMÌŽNM
JBˆØÚ×ØXØÛÝ[
ÛÛ‹Y
Bˆ\OXÛÛ‹™^XÝ]J”ÑSPÕY”“ÓHX[\œÈÒT‘HÕÑTŠ[XZ[
OOÈ‹
[XZ[
JK™™]ÚÛ™J
Bˆ\XÛÛ‹™^XÝ]J”ÑSPÕY”“ÓHX[\—Ù[\ÞYY\ÈÒT‘HÕÑTŠ[XZ[
OOÈ‹
[XZ[
JK™™]ÚÛ™J
BˆYˆ\HÜˆ\Ž™\œ›ÜH•][XZ[\È[™XYH\ÙYžH[›Ý\ˆÙÚ[‹ˆ‚ˆ[ÙN‚ˆÛÛ‹™^XÝ]J’S”ÑT•S•ÈX[\—Ù[\ÞYY\ÊYX[\—ÚY[\ÞYYWÛ˜[YK[XZ[\ÜÝÛÜ™Ú\ÚÝ]\ËÜ™X]YØ]
HSQTÊËËËËË	ØXÝ]™IËÊH‹
ÝŠ]ZY]ZY

JKY˜[YK[XZ[\ÜÝÛÜ™Ú\Ú
\ÜÝÛÜ™
K[YKœÝ™[YJ‰VKI[KIY	R‰SN‰TÖˆ‹[YK™Û][YJ
JJJNØÛÛ‹˜ÛÛ[Z]

NÛY\ÜØYÙOH‘[\ÞYYHÙÚ[ˆÜ™X]Yˆ‚ˆš[˜[N˜ÛÛ‹˜ÛÜÙJ
BˆÛÛY\Ý[X]WÙŠ
BˆžN™[\ÞYY\ÏXÛÛ‹™^XÝ]J”ÑSPÕY[\ÞYYWÛ˜[YK[XZ[Ý]\ËÜ™X]YØ]”“ÓHX[\—Ù[\ÞYY\ÈÒT‘HX[\—ÚYOÈÔ‘Tˆ–HÜ™X]YØ]TÐÈ‹
Y
JK™™]Ú[

Bˆš[˜[N˜ÛÛ‹˜ÛÜÙJ
Bˆ™]\›ˆ™[™\—Ý[\]WÜÝš[™ÊPST—ÑSTÖQQT×ÒS[\ÞYY\ÏY[\ÞYY\ËY\ÜØYÙO[Y\ÜØYÙK\œ›ÜY\œ›ÜŠB‚\œÜÝ
‹ÙX[\‹Y[\ÞYY\ËÏ[\ÞYYWÚY‹ÜÝ]\ÈŠB™YˆX[\—Ù[\ÞYYWÜÝ]\Ê[\ÞYYWÚY
N‚ˆYˆ›Ý\×ÙX[\—ÛÝÛ™\Š
Nˆ™]\›ˆ™\ÜÛœÙJ‘X[\ˆÝÛ™\ˆ\›Z\ÜÚ[Ûˆ™\]Z\™Yˆ‹Ý]\ÏMÊBˆXÝ[Û\ÝŠ™\]Y\Ý™›Ü›K™Ù]
˜XÝ[ÛˆŠHÜˆˆŠK›ÝÙ\Š
BˆYˆXÝ[Ûˆ›Ý[ˆÈ˜XÝ]˜]H‹™\ØX›HŸNœ™]\›ˆ™\ÜÛœÙJÚÛÜÙHXÝ]˜]HÜˆ\ØX›H›Üˆ\È[\ÞYYKˆ‹Ý]\ÏM
BˆY\ÝŠÙ\ÜÚ[Û–È™X[\—ÚY—JNÛ™]×ÜÝ]\ÏH™\ØX›YˆYˆXÝ[ÛOH™\ØX›Hˆ[ÙH˜XÝ]™H‚ˆÛÛY\Ý[X]WÙŠ
BˆžN‚ˆØÚ×ØXØÛÝ[
ÛÛ‹Y
BˆÝ\œ™[XÛÛ‹™^XÝ]J”ÑSPÕÝ]\È”“ÓHX[\—Ù[\ÞYY\ÈÒT‘HYOÈS‘X[\—ÚYOÈ‹
[\ÞYYWÚYY
JK™™]ÚÛ™J
BˆYˆÝ\œ™[[™ÝŠÝ\œ™[ÈœÝ]\È—JK›ÝÙ\Š
HO[™]×ÜÝ]\Î‚ˆÛÛ‹™^XÝ]J•TUHX[\—Ù[\ÞYY\ÈÑUÝ]\ÏOÈÒT‘HYOÈS‘X[\—ÚYOÈ‹
™]×ÜÝ]\Ë[\ÞYYWÚYY
JBˆYˆ™]×ÜÝ]\ÏOH™\ØX›YŽ˜ÛÛ‹™^XÝ]J’S”ÑT•S•ÈXØÛÝ[Ø]]Ý™\œÚ[ÛœÊXØÛÝ[Ý\KXØÛÝ[ÚY™\œÚ[ÛŠHSQTÊ	Ù[\ÞYYIËËJHÓˆÓÓ‘“PÕ
XØÛÝ[Ý\KXØÛÝ[ÚY
HÈTUHÑU™\œÚ[ÛXXØÛÝ[Ø]]Ý™\œÚ[ÛœË™\œÚ[ÛŠÌH‹
[\ÞYYWÚY
JBˆÛÛ‹˜ÛÛ[Z]

Bˆš[˜[N˜ÛÛ‹˜ÛÜÙJ
Bˆ™]\›ˆ™Y\™XÝ
‹ÙX[\‹Y[\ÞYY\ÈŠB‚™Yˆ\×Ü™XÛÝ™\žWÝ\ÝÜÙ\šXÙJ
N‚ˆˆˆ•[œ™\ÝšXÝY™XÛÝ™\žH\Ý[™ÈÛ›HÛˆH^XÚ]HY[YšYY™[™\ˆ\ÝÙ\šXÙKˆˆˆ‚ˆ™]\›ˆ
ÜË™[š\›Û‹™Ù]
”‘S‘T—ÔÑT•’PÑWÒQ‹ˆŠHOHœÜ‹YXL™ÍXÚÙ˜ÍÌÎYZMÌ‚ˆÜˆÜË™[š\›Û‹™Ù]
”‘S‘T—ÑVT“SÒÔÕSQH‹ˆŠHOH˜Y\š\][ÝKXÛÛ[Y\˜ÚX[]\Ý›Ûœ™[™\‹˜ÛÛHŠB‚™YˆÛÛœÝ[YWÜ›Ü\WÛÛÚÝ\
X[\—ÚYÛÛ›™XÝ[ÛS›Û™JN‚ˆÛÛXÛÛ›™XÝ[ÛˆÜˆ\Ý[X]WÙŠ
BˆžN‚ˆ[ØÚ×ØXØÛÝ[
ÛÛ‹X[\—ÚY
HYˆÛÛ›™XÝ[Ûˆ\È›Û™H[ÙHÛÛ‹™^XÝ]J”ÑSPÕ
ˆ”“ÓHX[\œÈÒT‘HYOÈ‹
X[\—ÚY
JK™™]ÚÛ™J
BˆYˆ›ÝÜˆÝŠÈœÝ]\È—JK›ÝÙ\Š
HOH˜XÝ]™HŽœ™]\›ˆ˜[ÙKˆÙ™ÏXÜ™Y]ÜÙ][™ÜÊÛÛ‹X[\—ÚY
BˆOXÛÛ‹™^XÝ]J”ÑSPÕ›Ü\WÛÛÚÝ\È”“ÓHX[\—Ý\ØYÙHÒT‘HX[\—ÚYOÈ‹
X[\—ÚY
JK™™]ÚÛ™J
Bˆ\ÙYZ[
VÈœ›Ü\WÛÛÚÝ\È—HYˆH[ÙH
NÛ[Z]Z[
È›ÛÚÝ\Û[Z]—HÜˆ
BˆYˆ\×ÚXYÛÙ™šXÙJ
HÜˆ

\×Ü™XÛÝ™\žWÝ\ÝÜÙ\šXÙJ
HÜˆ›ÝUPTÑWÕT“
H[™›ÝÙ™ÖÈ˜ÛÛ\[Y[\žH—H[™Èœ[—ØÛÙH—H›Ý[ˆÕP”ÐÔ’TSÓ—ÓSRUÊN‚ˆ™]\›ˆYK\ÙY[Z]ˆ[ÝÙY\ÙY[Z]XÛÛœÝ[YWØÜ™Y]
ÛÛ‹X[\—ÚY›ÛÚÝ\È‹\ÙY[Z]
BˆYˆ[ÝÙY‚ˆÛÛ‹™^XÝ]J’S”ÑT•S•ÈX[\—Ý\ØYÙJX[\—ÚY›Ü\WÛÛÚÝ\ÊHSQTÊËJHÓˆÓÓ‘“PÕ
X[\—ÚY
HÈTUHÑU›Ü\WÛÛÚÝ\ÏYX[\—Ý\ØYÙKœ›Ü\WÛÛÚÝ\ÊÌH‹
X[\—ÚY
JBˆYˆÛÛ›™XÝ[Ûˆ\È›Û™N˜ÛÛ‹˜ÛÛ[Z]

Bˆ™]\›ˆ[ÝÙY\ÙY[Z]ˆš[˜[N‚ˆYˆÛÛ›™XÝ[Ûˆ\È›Û™N˜ÛÛ‹˜ÛÜÙJ
B‚‚™Yˆ™\Ù]ÝšX[Ý\ØYÙWÙ›Ü—ÝŒLNM—Ý\Ý[™×ÛÛ˜ÙJ
N‚ˆÛÛY\Ý[X]WÙŠ
BˆžN‚ˆÛÛ‹™^XÝ]JÔ‘PUHP“HQˆ“ÕVTÕÈ\ÛZYÜ˜][ÛœÈ
ZYÜ˜][Û—ÚÙ^HV’SPT–HÑVK\YYØ]V“Õ•S
HŠBˆÙ^OHŒLWÍ—ÎM—ÝšX[Ý\ÝÜ™\Ù]‚ˆYˆÛÛ‹™^XÝ]J”ÑSPÕH”“ÓH\ÛZYÜ˜][ÛœÈÒT‘HZYÜ˜][Û—ÚÙ^OOÈ‹
Ù^K
JK™™]ÚÛ™J
Nœ™]\›‚ˆÛÛ‹™^XÝ]J•TUHX[\—Ý\ØYÙHÑU›Ü\WÛÛÚÝ\ÏLÒT‘HX[\—ÚYSˆ
ÑSPÕY”“ÓHX[\œÈÒT‘HÝÙ\ŠÓÐSTÐÑJ[—ØÛÙK	ÉÊJOIÝšX[	ÊHŠBˆÛÛ‹™^XÝ]J’S”ÑT•S•È\ÛZYÜ˜][ÛœÊZYÜ˜][Û—ÚÙ^K\YYØ]
HSQTÊËÊH‹
Ù^K]][YK]Û›ÝÊ
Kš\ÛÙ›Ü›X]

JJBˆÛÛ‹˜ÛÛ[Z]

Bˆš[˜[N˜ÛÛ‹˜ÛÜÙJ
B‚œ™\Ù]ÝšX[Ý\ØYÙWÙ›Ü—ÝŒLNM—Ý\Ý[™×ÛÛ˜ÙJ
B‚\˜™Y›Ü™WÜ™\]Y\Ý™Yˆ™\]Z\™WÙX[\—ÛÙÚ[Š
N‚ˆ]J™\]Y\Ýœ]ÜˆˆŠKœœÝš\
‹ÈŠHÜˆ‹È‚ˆYˆ][ˆÈ‹ÜÚ]H‹‹Ù˜]šXÛÛ‹šXÛÈ‹‹ÜšXÚ[™È‹‹ÜšXÚ[™Ëš[‹‹ÝšX[\ÚYÛ\š[‹‹Ü›ÛÙ™\‹\Ù]\š[‹‹ÙX[\‹[ÙÚ[ˆ‹‹Ù›Ü™ÛÝ\\ÜÝÛÜ™‹‹Ü™\Ù]\\ÜÝÛÜ™‹‹ÜÙ]\YX[\ˆ‹‹ÚX[‹‹Ø\KØYZ[‹ØÜ™X]KYX[\ˆ‹‹Ø\KÜX›XËÜÚYÛ\‹‹Ø\KÜX›XËÜÝ\Ü‹‹Ø\KÜX›XËÜÝ\ÜØÛÛ™šYÈ‹‹Ø\KÜX›XËÜÝ\ÜÚ[˜›Ý[™ŸHÜˆ]œÝ\ÝÚ]
‹ÜÝ]XËÈŠHÜˆ]œÝ\ÝÚ]
‹ÜÚ]KÈŠNœ™]\›ˆ›Û™BˆYˆ›ÝÙ\ÜÚ[Û‹™Ù]
™X[\—ÚYŠN‚ˆYˆ™\]Y\Ýœ]œÝ\ÝÚ]
‹Ø\KÈŠHÜˆ™\]Y\Ýš\×ÚœÛÛŽœ™]\›ˆœÛÛšYžJ\œ›ÜH‘X[\ˆÙÚ[ˆ™\]Z\™YŠKBˆ™]\›ˆ™Y\™XÝ
‹ÙX[\‹[ÙÚ[ˆŠBˆÛÛY\Ý[X]WÙŠ
BˆžN‚ˆXØÛÝ[XÛÛ‹™^XÝ]J”ÑSPÕÝ]\È”“ÓHX[\œÈÒT‘HYOÈ‹
Ù\ÜÚ[Û–È™X[\—ÚY—K
JK™™]ÚÛ™J
BˆXÝ]™OX›ÛÛ
XØÛÝ[[™ÝŠXØÛÝ[ÈœÝ]\È—JK›ÝÙ\Š
OOH˜XÝ]™HŠBˆYˆXÝ]™H[™\×Ù[\ÞYYJ
N‚ˆ[\ÞYYOXÛÛ‹™^XÝ]J”ÑSPÕÝ]\È”“ÓHX[\—Ù[\ÞYY\ÈÒT‘HYOÈS‘X[\—ÚYOÈ‹
ÝŠÙ\ÜÚ[Û‹™Ù]
™[\ÞYYWÚYŠHÜˆˆŠKÙ\ÜÚ[Û–È™X[\—ÚY—JJK™™]ÚÛ™J
BˆXÝ]™OX›ÛÛ
[\ÞYYH[™ÝŠ[\ÞYYVÈœÝ]\È—JK›ÝÙ\Š
OOH˜XÝ]™HŠBˆYˆXÝ]™N‚ˆÚ[™H™[\ÞYYHˆYˆ\×Ù[\ÞYYJ
H[ÙH›ÝÛ™\ˆ‚ˆXØÛÝ[ÚY\ÝŠÙ\ÜÚ[Û‹™Ù]
™[\ÞYYWÚYŠHÜˆˆŠHYˆ\×Ù[\ÞYYJ
H[ÙHÙ\ÜÚ[Û–È™X[\—ÚY—BˆXÝ]™OZ[
Ù\ÜÚ[Û‹™Ù]
˜]]Ý™\œÚ[ÛˆŠHÜˆ
OOX]]Ý™\œÚ[ÛŠÛÛ‹Ú[™XØÛÝ[ÚY
Bˆš[˜[N˜ÛÛ‹˜ÛÜÙJ
BˆYˆ›ÝXÝ]™N‚ˆÙ\ÜÚ[Û‹˜ÛX\Š
BˆYˆ™\]Y\Ýœ]œÝ\ÝÚ]
‹Ø\KÈŠHÜˆ™\]Y\Ýš\×ÚœÛÛŽœ™]\›ˆœÛÛšYžJ\œ›ÜHXØÛÝ[XØÙ\ÜÈ\ØX›YˆX\ÙHÙÈ[ˆYØZ[‹ˆŠKBˆ™]\›ˆ™Y\™XÝ
‹ÙX[\‹[ÙÚ[ˆŠB‚‚ˆÈœ›ÝÜÙ\œÈ]\Ý›ÝÜ˜[ÜˆÚ[™ÙH[\ÞYYHXØÙ\ÜÈœ›ÛHH›Ü™ZYÛˆYÙK‚ˆYˆ™\]Y\Ý›Y]ÙOH”ÔÕˆ[™
]OH‹ÙX[\‹Y[\ÞYY\ÈˆÜˆ
]œÝ\ÝÚ]
‹ÙX[\‹Y[\ÞYY\ËÈŠH[™]™[™ÝÚ]
‹ÜÝ]\ÈŠJJN‚ˆÜšYÚ[\™\]Y\ÝšXY\œË™Ù]
“ÜšYÚ[ˆ‹ˆŠKœÝš\

K›ÝÙ\Š
BˆÜÝ\™\]Y\ÝšÜÝ›ÝÙ\Š
BˆYˆ™\]Y\ÝšXY\œË™Ù]
”ÙXËQ™]ÚTÚ]H‹ˆŠK›ÝÙ\Š
OOH˜Ü›ÜÜË\Ú]HˆÜˆ
ÜšYÚ[ˆ[™ÜšYÚ[ˆ›Ý[ˆÈšÎ‹ËÈŠÚÜÝš‹ËÈŠÚÜÝJN‚ˆ™]\›ˆ™\ÜÛœÙJ‘[\ÞYYHXØÙ\ÜÈÚ[™Ù\È]\ÝÛÛYHœ›ÛH\ÈY\šT][ÝHÚ]Kˆ™[ØYX[˜YÙH[\ÞYY\È[™žHYØZ[‹ˆ‹Ý]\ÏMÊB‚ˆÈ[ˆÛœ›ÝÜÙ\ˆXˆ]\Ý›ÝØ]™H]È˜Y[ÈHY™™\™[\Ú[™\ÜÈY\ˆ™K[ÙÚ[‹‚ˆ^XÝYØXØÛÝ[\™\]Y\ÝšXY\œË™Ù]
–PY\šT][ÝKPXØÛÝ[‹ˆŠBˆYˆ^XÝYØXØÛÝ[[™^XÝYØXØÛÝ[O\ÝŠÙ\ÜÚ[Û‹™Ù]
™X[\—ÚYŠHÜˆˆŠN‚ˆ™]\›ˆœÛÛšYžJ\œ›ÜH•\ÈYÙH™[Û™ÜÈÈ[›Ý\ˆ\Ú[™\ÜËˆÙY\]Ü[‹ÚYÛˆ[ˆÈHÜšYÚ[˜[\Ú[™\ÜÈ[ˆ[›Ý\ˆX‹[ˆ™]žKˆ[Ý\ˆ[œØ]™Y[šY\È\™HÝ[\™KˆŠKB‚‚\™Ù]
‹ÛÙÛÝ]ŠB™YˆÙÛÝ]

N‚ˆÙ\ÜÚ[Û‹˜ÛX\Š
Bˆ™]\›ˆ™Y\™XÝ
‹ÈŠB‚™Yˆ™XÝÜ—Ü—ÜXWÙ[˜X›Y

N‚ˆ[ÝÙY^Ý‹œÝš\

H›Üˆˆ[ˆÜË™[š\›Û‹™Ù]
QT’TUSÕWÕ‘PÕÔ—Ô—ÔPWÒQÈ‹ˆŠKœÜ]
‹ŠHYˆ‹œÝš\

_Bˆ™]\›ˆÜË™[š\›Û‹™Ù]
QT’TUSÕWÕ‘PÕÔ—Ô—ÔPH‹ˆŠOOHŒHˆ[™ÝŠÙ\ÜÚ[Û‹™Ù]
™X[\—ÚYŠHÜˆˆŠH[ˆ[ÝÙY‚\œÜÝ
‹ÜXK]™XÝÜ‹YXYÜ˜[KÝ˜[Y]HŠB™Yˆ™XÝÜ—Ü—ÜXWÝ˜[Y]J
N‚ˆYˆ›Ý™XÝÜ—Ü—ÜXWÙ[˜X›Y

Nœ™]\›ˆœÛÛšYžJ\œ›ÜH“›Ý›Ý[™ŠKˆœ›ÛHYX\Ý\™[Y[Ú[YÜš]H[\ÜÛ˜\ÚÝÙ\œ›Ü‚ˆ]O\™\]Y\Ý™Ù]ÚœÛÛŠÚ[[UYJBˆYˆ›Ý\Ú[œÝ[˜ÙJ]KXÝ
Nœ™]\›ˆœÛÛšYžJ\œ›ÜHHØ]™YYX\Ý\™[Y[Û˜\ÚÝ\È™\]Z\™YˆŠKˆ\œ›Ü\Û˜\ÚÝÙ\œ›ÜŠÈœ][ÝHŽ™]K™Ù]
œ][ÝHŠ_JBˆYˆ\œ›ÜŽœ™]\›ˆœÛÛšYžJ\œ›ÜY\œ›ÜŠKˆ™]\›ˆœÛÛšYžJÚÏUYJB‚\™Ù]
‹ÜXK]™XÝÜ‹YXYÜ˜[KšœÈŠB™Yˆ™XÝÜ—Ü—ÜXWÜØÜš\

N‚ˆYˆ›Ý™XÝÜ—Ü—ÜXWÙ[˜X›Y

Nœ™]\›ˆ“›Ý›Ý[™‹ˆœ›ÛH]Xˆ[\Ü]ˆ[\Ü˜\ÙMˆ›ÛX˜\ÙM˜[˜ÛÙJ
]
×Ùš[W×ÊKœ\™[ÈœXWØ\ÜÙ]È‹È‘Z˜UTØ[œËˆŠKœ™XYØž]\Ê
JK™XÛÙJ˜\ØÚZHŠBˆ›ÛÙ›ÛX˜\ÙM˜[˜ÛÙJ
]
×Ùš[W×ÊKœ\™[ÈœXWØ\ÜÙ]È‹È‘Z˜UTØ[œËP›ÛˆŠKœ™XYØž]\Ê
JK™XÛÙJ˜\ØÚZHŠBˆ›ÝXÙOJ]
×Ùš[W×ÊKœ\™[ÈœXWØ\ÜÙ]È‹È‘Z˜UKSPÑS”ÑKŠKœ™XYÝ^

Kœ™\XÙJŠ‹È‹ŠˆÈŠBˆ™\ÜÛœÙOX\œ™\ÜÛœÙWØÛ\ÜÊ‹ÊˆŠÛ›ÝXÙJÈˆ
‹×Ú[™ÝËTU™XÝÜ”‘›ÛHŠÚœÛÛ‹™[\Ê›Û
JÈŽ×Ú[™ÝËTU™XÝÜ”›Û›ÛHŠÚœÛÛ‹™[\Ê›ÛÙ›Û
JÈŽ×ˆŠÔ]
×Ùš[W×ÊKÚ]Û˜[YJœXWÝ™XÝÜ—Ü‹šœÈŠKœ™XYÝ^

KZ[Y]\OH˜\XØ][Û‹Ú˜]˜\ØÜš\ŠBˆ™\ÜÛœÙKšXY\œÖÈØXÚKPÛÛ›Û—OHœš]˜]K›Ë\ÝÜ™H‚ˆ™]\›ˆ™\ÜÛœÙB‚™YˆX[X[Ü›ÛÙ—ÜXWÙ[˜X›Y

N‚ˆÈ[X™\˜]HÝX›HÜZ[‹ˆ™]™\ˆ[˜X›Y›Üˆ[ˆ[\™H[ˆÜˆ\Ú[™\ÜÈ\K‚ˆ[ÝÙY^Ý‹œÝš\

H›Üˆˆ[ˆÜË™[š\›Û‹™Ù]
QT’TUSÕWÓPS•PSÔ“ÓÑ—ÔPWÒQÈ‹ˆŠKœÜ]
‹ŠHYˆ‹œÝš\

_Bˆ™]\›ˆÜË™[š\›Û‹™Ù]
QT’TUSÕWÓPS•PSÔ“ÓÑ—ÔPH‹ˆŠOOHŒHˆ[™ÝŠÙ\ÜÚ[Û‹™Ù]
™X[\—ÚYŠHÜˆˆŠH[ˆ[ÝÙY‚™YˆX[X[Ü›ÛÙ—ÜÙ\ÜÚ[ÛŠÙ\ÜÊN‚ˆ™]\›ˆ›ÛÛ
Ù\ÜÈ[™Ù\ÜË™Ù]
›[ÙHŠOOH›X[X[Ü›ÛÙ—ÜÝ]XÈŠB‚\œ›Ý]J‹ÈŠB™YˆÛYJ
Nœ™]\›ˆ™[™\—Ý[\]WÜÝš[™ÊS‘PÕÔ—Ô—ÔPWÑ“QÏHŒHˆYˆ™XÝÜ—Ü—ÜXWÙ[˜X›Y

H[ÙHŒ‹PS•PSÔ“ÓÑ—ÔPWÑ“QÏHŒHˆYˆX[X[Ü›ÛÙ—ÜXWÙ[˜X›Y

H[ÙHŒ‹PÐÓÕS•ÒQ\ÝŠÙ\ÜÚ[Û‹™Ù]
™X[\—ÚYŠHÜˆˆŠKQ•Ô’SÒTSW×Ú[\Ü×ÊÛÜšÜÜXÙWÙ˜YÈŠKœš[˜Ú\[
Ù\ÜÚ[ÛŠKÓÓÑÓWÓPT×ÐTWÒÑVOQÓÓÑÓWÓPT×ÐTWÒÑVKT×ÒPQÓÑ‘’PÑOZ\×ÚXYÛÙ™šXÙJ
KT×ÑSTÖQQOZ\×Ù[\ÞYYJ
KT×ÑPST—ÓÕÓ‘TZ\×ÙX[\—ÛÝÛ™\Š
JB\™Ù]
‹ÛX\›Þ]\ÝŠB™YˆX\›ÞÝ\Ý

N‚ˆY™\ÜÈH™\]Y\Ý˜\™ÜË™Ù]
˜Y™\ÜÈ‹ˆŠKœÝš\

BˆYˆ›ÝY™\ÜÎ‚ˆ™]\›ˆœÛÛšYžJÈ™\œ›ÜˆŽˆ‘[\ˆ[ˆY™\ÜÈŸJKˆžN‚ˆHH\›X‹œ\œÙKœ][ÝJY™\ÜÊBˆ\›HˆšÎ‹ËØ\K›X\›Þ˜ÛÛKÜÙX\˜ÚÙÙ[ØÛÙKÝ‹Ù›ÜØ\™ÜO^Ü_I˜XØÙ\Ü×ÝÚÙ[^Ý\›X‹œ\œÙKœ][ÝJPT“ÖÐPÐÑTÔ×ÕÒÑSŠ_I˜ÛÝ[žOXØI›[Z]MH‚ˆÚ]\›X‹œ™\]Y\Ý\›Ü[Š\›[Y[Ý]LL
H\ÈŽ‚ˆ]HHœÛÛ‹›ØYÊ‹œ™XY

K™XÛÙJ]‹NŠJBˆ™X]\™\ÈH]K™Ù]
™™X]\™\È‹×JBˆš[X\žHH™X]\™\ÖÌHYˆ™X]\™\È[ÙH›Û™BˆØ\›š[™ÜÈH×BˆYˆš[X\žN‚ˆHš[X\žK™Ù]
œ›Ü\Y\È‹ßJBˆÝH™Ù]
˜ÛÛ^‹ßJBˆš[X\žWØYˆH
Ý™Ù]
˜Y™\ÜÈŠHÜˆßJK™Ù]
˜Y™\Ü×Û[X™\ˆ‹ˆŠBˆš[X\žWÜÝ™Y]H
Ý™Ù]
˜Y™\ÜÈŠHÜˆßJK™Ù]
œÝ™Y]Û˜[YH‹ˆŠBˆÛÛÜ™ÈH
š[X\žK™Ù]
™Ù[ÛY]žHŠHÜˆßJK™Ù]
˜ÛÛÜ™[˜]\È‹×JB‚ˆYˆš[X\žWØYˆ[™[ŠÛÛÜ™ÊHOHŽ‚ˆ›Üˆ[[ˆ™X]\™\ÖÌN—N‚ˆ\H[™Ù]
œ›Ü\Y\È‹ßJBˆXÝH\™Ù]
˜ÛÛ^‹ßJBˆ[ØYˆH
XÝ™Ù]
˜Y™\ÜÈŠHÜˆßJK™Ù]
˜Y™\Ü×Û[X™\ˆ‹ˆŠBˆ[ÜÝ™Y]H
XÝ™Ù]
˜Y™\ÜÈŠHÜˆßJK™Ù]
œÝ™Y]Û˜[YH‹ˆŠBˆXÛÛÜ™ÈH
[™Ù]
™Ù[ÛY]žHŠHÜˆßJK™Ù]
˜ÛÛÜ™[˜]\È‹×JB‚ˆYˆ[ØYˆOHš[X\žWØYˆ[™[ÜÝ™Y][™[ÜÝ™Y]OHš[X\žWÜÝ™Y][™[ŠXÛÛÜ™ÊHOHŽ‚ˆ]KÛŒHHÛÛÜ™ÖÌWKÛÛÜ™ÖÌBˆ]‹ÛŒˆHXÛÛÜ™ÖÌWKXÛÛÜ™ÖÌBˆH
ÛŒ‹[ÛŒJH
ˆLLLÌŒ
ˆX]˜ÛÜÊX]œ˜YX[œÊ
]JÛ]ŠKÌŠJBˆHH
]‹[]JH
ˆLLMˆ\Ý[˜ÙHHX]œÜ\

™
ÈJ™JB‚ˆYˆ\Ý[˜ÙHHL‚ˆØ\›š[™ÜË˜\[™
Âˆ˜Y™\ÜÈŽˆ\™Ù]
™[ØY™\ÜÈ‹ˆŠKˆ™\Ý[˜ÙWÛHŽˆ›Ý[™
\Ý[˜ÙJBˆJB‚ˆ™]\›ˆœÛÛšYžJÂˆœÝ]\ÈŽˆØ\›š[™ÈˆYˆØ\›š[™ÜÈ[ÙHœØY™H‹ˆœš[X\žHŽˆš[X\žKˆ›™X\˜žWÜØ[YWÛ[X™\—Ø[\›˜]]™\ÈŽˆØ\›š[™ÜÂˆJBˆ^Ù\^Ù\[Ûˆ\ÈN‚ˆ™]\›ˆœÛÛšYžJÈ™\œ›ÜˆŽˆÝŠJ_JK™YˆÙ[ØÛÙWÜ\ÊÊN‚ˆ\Ï^ÈœÝ™Y]Žˆˆ‹˜Ú]HŽˆˆ‹œ›Ýš[˜ÙHŽˆˆ‹œÜÝ[ŽˆˆŸBˆÛÛ\ÏYË™Ù]
˜Y™\Ü×ØÛÛ\Û™[ÈŠHÜˆ×Bˆ[O\›Ý]OHˆ‚ˆ›ÜˆÈ[ˆÛÛ\Î‚ˆ\\Ï\Ù]
Ë™Ù]
\\ÈŠHÜˆ×JBˆYˆœÝ™Y]Û[X™\ˆˆ[ˆ\\Î›[OXË™Ù]
›Û™×Û˜[YHŠHÜˆˆ‚ˆYˆœ›Ý]Hˆ[ˆ\\Îœ›Ý]OXË™Ù]
›Û™×Û˜[YHŠHÜˆˆ‚ˆYˆ›Ý\ÖÈ˜Ú]H—H[™\\Ëš[\œÙXÝ[ÛŠÈ›ØØ[]H‹œÜÝ[ÝÝÛˆ‹œÝX›ØØ[]H‹˜YZ[š\Ý˜]]™WØ\™XWÛ]™[ÌÈŸJNœ\ÖÈ˜Ú]H—OXË™Ù]
›Û™×Û˜[YHŠHÜˆˆ‚ˆYˆ˜YZ[š\Ý˜]]™WØ\™XWÛ]™[ÌHˆ[ˆ\\Îœ\ÖÈœ›Ýš[˜ÙH—OXË™Ù]
œÚÜÛ˜[YHŠHÜˆˆ‚ˆYˆœÜÝ[ØÛÙHˆ[ˆ\\Îœ\ÖÈœÜÝ[—OXË™Ù]
›Û™×Û˜[YHŠHÜˆˆ‚ˆ\ÖÈœÝ™Y]—OJ[JÈˆŠÜ›Ý]JKœÝš\

Bˆ™]\›ˆ\Â‚™Yˆ\ØWØY™\Ü×Ý˜\šX[ÊY™\ÜÊN‚ˆY™\ÜÏ\ÝŠY™\ÜÈÜˆˆŠKœÝš\

BˆÝ]VØY™\Ü×HYˆY™\ÜÈ[ÙH×BˆYˆ›ÝY™\ÜÎœ™]\›ˆÝ]ˆš\œÝÙ\Z[XY™\ÜËœ\][ÛŠ‹ŠBˆ[\Ü™BˆO\™K›X]Ú
ˆ——ÊŠ
ÖÐKV˜K^—OÊWÊ–ËK×WÊŠ
ÖÐKV˜K^—OÊWÊÊŠÏÊWÊ‰‹š\œÝ
BˆYˆN‚ˆ[š]Ý™Y]Û›ËÝ™Y]Ü™\Ý[K™Ü›Ý\Ê
NÜÝY™š^J‹ŠÝZ[
HYˆÙ\[ÙHˆ‚ˆ›ÜˆH[ˆ
ˆžÜÝ™Y]Û›ßHÜÝ™Y]Ü™\ÝHÞÝ[š]^ÜÝY™š^H‹ˆžÜÝ™Y]Û›ßHÜÝ™Y]Ü™\ÝH[š]Ý[š]^ÜÝY™š^H‹ˆžÜÝ™Y]Û›ßHÜÝ™Y]Ü™\ÝHÝ[š]^ÜÝY™š^HŠN‚ˆYˆH›Ý[ˆÝ]›Ý]˜\[™
JBˆ™]\›ˆÝ]‚™YˆÛÛÙÛWÙÙ[ØÛÙWÙš\œÝ
Ù^KY™\ÜËÛÛ\Û™[×ØÛÝ[žOQ˜[ÙK^XÝYÜ›Ýš[˜ÙOHˆŠN‚ˆ\ÝS›Û™BˆØ[˜YX[^ÈPˆ‹È‹“Pˆ‹“ˆ‹““‹“”È‹“•‹“•H‹“Óˆ‹”H‹”PÈ‹”ÒÈ‹–UŸBˆ\×ØØ[˜YO\ÝŠ^XÝYÜ›Ýš[˜ÙHÜˆˆŠKœÝš\

K\\Š
H[ˆØ[˜YX[‚ˆ›Ü›X[^™YÏ][š]ØY™\ÜÊY™\ÜË^XÝYÜ›Ýš[˜ÙJBˆ]Y\šY\Ï[\Ý
XÝ™œ›ÛZÙ^\ÊÛ›Ü›X[^™YJÝ\ØWØY™\Ü×Ý˜\šX[ÊY™\ÜÊJJBˆ›ÜˆH[ˆ]Y\šY\Î‚ˆ\˜[\Ï^È˜Y™\ÜÈŽœKšÙ^HŽšÙ^_BˆYˆÛÛ\Û™[×ØÛÝ[žN‚ˆ\˜[\ÖÈ˜ÛÛ\Û™[È—OH˜ÛÝ[žNÐHˆYˆ\×ØØ[˜YH[ÙH˜ÛÝ[žN•TÈ‚ˆ\˜[\ÖÈœ™YÚ[Ûˆ—OH˜ØHˆYˆ\×ØØ[˜YH[ÙH\È‚ˆÜO]\›X‹œ\œÙK\›[˜ÛÙJ\˜[\ÊNÙÜËÙ[Ï\™\WÚœÛÛŠšÎ‹ËÛX\Ë™ÛÛÙÛX\\Ë˜ÛÛKÛX\ËØ\KÙÙ[ØÛÙKÚœÛÛÈŠÙÜJNÛ\ÝJÜËÙ[ËJBˆYˆÜÏOLŒ[™Ù[Ë™Ù]
œÝ]\ÈŠOOH“ÒÈˆ[™Ù[Ë™Ù]
œ™\Ý[ÈŠNœ™]\›ˆÜËÙ[ËBˆ™]\›ˆ\ÝYˆ\Ý[ÙH
ÈœÝ]\ÈŽˆ–‘T“×Ô‘TÕSÈŸKY™\ÜÊB‚™YˆÛ›Ü›WÜXÙJŠN‚ˆ[\Ü™Bˆ™]\›ˆ™KœÝXŠˆ–×˜K^ŒNWH‹ˆ‹ÝŠˆÜˆˆŠK›ÝÙ\Š
JB‚™YˆY™\Ü×ÛZ\ÛX]Ú
^XÝYØÚ]K^XÝYÜ›Ýš[˜ÙK\Ë^XÝYÜÝ™Y]Û[X™\HˆŠN‚ˆXÏWÛ›Ü›WÜXÙJ^XÝYØÚ]JNÈ\WÛ›Ü›WÜXÙJ^XÝYÜ›Ýš[˜ÙJBˆXÏWÛ›Ü›WÜXÙJ
\ÈÜˆßJK™Ù]
˜Ú]HŠJNÈ\WÛ›Ü›WÜXÙJ
\ÈÜˆßJK™Ù]
œ›Ýš[˜ÙHŠJBˆÚ]WØ˜YX›ÛÛ
XÈ[™
›ÝXÈÜˆXÈOXXÊJBˆ›Ý—Ø˜YX›ÛÛ
\[™
›Ý\Üˆ\OX\
JBˆ[\Ü™Bˆ[\™KœÝXŠˆ–×ŒNXK^—H‹ˆ‹ÝŠ^XÝYÜÝ™Y]Û[X™\ˆÜˆˆŠK›ÝÙ\Š
JBˆ›Ý[™ÜÝ™Y]\ÝŠ
\ÈÜˆßJK™Ù]
œÝ™Y]ŠHÜˆˆŠKœÝš\

BˆO\™K›X]Ú
ˆ——ÊŠ
ÖÐKV˜K^—OÊWˆ‹›Ý[™ÜÝ™Y]
Bˆ[\™KœÝXŠˆ–×ŒNXK^—H‹ˆ‹
K™Ü›Ý\
JHYˆH[ÙHˆŠK›ÝÙ\Š
JBˆ[X™\—Ø˜YX›ÛÛ
[ˆ[™[ˆOX[ŠHÈ[ÛÈ™Z™XÝÈHÝ™Y][Û›HÛÛÙÛH™\Ý[Ú]›ÈÚ]šXÈ[X™\‚ˆ™]\›ˆÚ]WØ˜YÜˆ›Ý—Ø˜YÜˆ[X™\—Ø˜Y‚™YˆZ\ÛX]ÚÛY\ÜØYÙJ^XÝYØÚ]K^XÝYÜ›Ýš[˜ÙK\ÊN‚ˆØ[YH‹‹š›Ú[Š›Üˆ[ˆÜÝŠ^XÝYØÚ]HÜˆˆŠKœÝš\

KÝŠ^XÝYÜ›Ýš[˜ÙHÜˆˆŠKœÝš\

WHYˆ
HÜˆHØØ][Ûˆ[\™Y‚ˆ›Ý[™H‹‹š›Ú[Š›Üˆ[ˆÊ\ÈÜˆßJK™Ù]
˜Ú]H‹ˆŠK
\ÈÜˆßJK™Ù]
œ›Ýš[˜ÙH‹ˆŠWHYˆ
HÜˆ˜HY™™\™[ØØ][Ûˆ‚ˆ™]\›ˆˆ–[ÝH[\™YÝØ[YH]ÛÛÙÛH›Ý[™Ù›Ý[™KˆÛÜœ™XÝHY™\ÜÈÜˆ\ÙH^XÝ›ÜY\[ˆÛÛÜ™[˜]\Ëˆ‚‚\œÜÝ
‹ØY™\ÜË\™]šY]ÈŠB™YˆY™\Ü×Ü™]šY]Ê
N‚ˆ\™\]Y\Ý™Ù]ÚœÛÛŠÚ[[UYJHÜˆßNÚÙ^O\ÝŠ™Ù]
šÙ^HŠHÜˆˆŠKœÝš\

NØY™\ÜÏ\ÝŠ™Ù]
˜Y™\ÜÈŠHÜˆˆŠKœÝš\

HÈ]]Üš]]]™H]Y\žH\ÈÝ™Y]
ÈÚ]H
È›Ü\H›Ýš[˜ÙNÈ’TÛÙH\È™]™\ˆÙ[ˆYˆ›ÝÙ^HÜˆ[ŠY™\ÜÊOœ™]\›ˆœÛÛšYžJ\œ›ÜHY™\ÜÈ[™THÙ^H\™H™\]Z\™YˆŠKˆžN‚ˆ^XÝYØÚ]O\ÝŠ™Ù]
™^XÝYØÚ]HŠHÜˆˆŠKœÝš\

NÙ^XÝYÜ›Ýš[˜ÙO\ÝŠ™Ù]
™^XÝYÜ›Ýš[˜ÙHŠHÜˆˆŠKœÝš\

NÙ^XÝYÜÝ™Y]Û[X™\\ÝŠ™Ù]
™^XÝYÜÝ™Y]Û[X™\ˆŠHÜˆˆŠKœÝš\

Bˆ›Ü›X[^™YØY™\ÜË[š]Û[X™\][š]ØY™\ÜÊY™\ÜË^XÝYÜ›Ýš[˜ÙJBˆ^XÝYÜÝ™Y]Û[X™\][š]Û[X™\ˆÜˆ^XÝYÜÝ™Y]Û[X™\‚ˆÜËÙ[ËÛX]ÚYÜ]Y\žOYÛÛÙÛWÙÙ[ØÛÙWÙš\œÝ
Ù^KY™\ÜËÛÛ\Û™[×ØÛÝ[žOUYK^XÝYÜ›Ýš[˜ÙOY^XÝYÜ›Ýš[˜ÙJBˆYˆÜÈOLŒÜˆÙ[Ë™Ù]
œÝ]\ÈŠHOH“ÒÈˆÜˆ›ÝÙ[Ë™Ù]
œ™\Ý[ÈŠNœ™]\›ˆœÛÛšYžJ\œ›ÜHY™\ÜÈ›Ý›Ý[™ŠKˆÏYÙ[ÖÈœ™\Ý[È—VÌNÜ\ÏYÙ[ØÛÙWÜ\ÊÊBˆYˆY™\Ü×ÛZ\ÛX]Ú
^XÝYØÚ]K^XÝYÜ›Ýš[˜ÙK\Ë^XÝYÜÝ™Y]Û[X™\ŠN‚ˆ™]\›ˆœÛÛšYžJ\œ›ÜHQ‘TÔÈÑTÓ‰ÕPUÒ‹\Ù\—Ù\œ›Ü[Z\ÛX]ÚÛY\ÜØYÙJ^XÝYØÚ]K^XÝYÜ›Ýš[˜ÙK\ÊK›Ü›X]YØY™\ÜÏYË™Ù]
™›Ü›X]YØY™\ÜÈŠK\Ï\\ÊKBˆ™]\›ˆœÛÛšYžJ›Ü›X]YØY™\ÜÏYË™Ù]
™›Ü›X]YØY™\ÜÈŠK\Ï\\ÊBˆ^Ù\^Ù\[Ûˆ\ÈNœ™]\›ˆœÛÛšYžJ\œ›Ü\ÝŠJJK‚™YˆÝ™Y]ÝšY]×Ú[™›ÊÙ^KY™\ÜË]™Ë\™Ù]Û]\™Ù]Û™ÊN‚ˆ\O]\›X‹œ\œÙK\›[˜ÛÙJÈ›ØØ][ÛˆŽ˜Z[[™×ØY™\ÜÊY™\ÜÊKšÙ^HŽšÙ^KœÛÝ\˜ÙHŽˆ›Ý]ÛÜˆŸJBˆ\ËY]O\™\WÚœÛÛŠšÎ‹ËÛX\Ë™ÛÛÙÛX\\Ë˜ÛÛKÛX\ËØ\KÜÝ™Y]šY]ËÛY]Y]OÈŠÛ\JBˆYˆ\ÏOLŒ[™Y]K™Ù]
œÝ]\ÈŠOOH–‘T“×Ô‘TÕSÈˆ[™]\È›Ý›Û™H[™™È\È›Ý›Û™N‚ˆ\O]\›X‹œ\œÙK\›[˜ÛÙJÈ›ØØ][ÛˆŽ™ˆžÛ]KÛ™ßH‹šÙ^HŽšÙ^KœÛÝ\˜ÙHŽˆ›Ý]ÛÜˆŸJBˆ\ËY]O\™\WÚœÛÛŠšÎ‹ËÛX\Ë™ÛÛÙÛX\\Ë˜ÛÛKÛX\ËØ\KÜÝ™Y]šY]ËÛY]Y]OÈŠÛ\JBˆÝ™Y]Ý\›S›Û™NÜÝ™Y]Ù]OS›Û™BˆYˆ\ÏOLŒ[™Y]K™Ù]
œÝ]\ÈŠOOH“ÒÈŽ‚ˆØÏ[Y]K™Ù]
›ØØ][ÛˆŠHÜˆßNÚXYX™X\š[™Ê›Ø]
ØË™Ù]
›]‹]
JK›Ø]
ØË™Ù]
›™È‹™ÊJK\™Ù]Û]\™Ù]Û™ÊBˆÜO]\›X‹œ\œÙK\›[˜ÛÙJÈœÚ^™HŽˆÍŒ‹œ[›ÈŽ›Y]K™Ù]
œ[›×ÚYŠKšXY[™ÈŽœ›Ý[™
XYŠKœ]ÚŽK™›ÝˆŽŽKœ™]\›—Ù\œ›Ü—ØÛÙHŽˆYH‹šÙ^HŽšÙ^_JBˆÝ™Y]Ý\›HšÎ‹ËÛX\Ë™ÛÛÙÛX\\Ë˜ÛÛKÛX\ËØ\KÜÝ™Y]šY]ÏÈŠÜÜNÜÝ™Y]Ù]O[Y]K™Ù]
™]HŠBˆ™]\›ˆÝ™Y]Ý\›Ý™Y]Ù]B‚™Yˆ›ÛÙ—Ú[XYÙ\žWÜ™\]Y\Ý
XZ[‹Z[š[][OLLX^[][OLL
N‚ˆÈ™\]Y\ÝÛÛÙÛHÛÛ\‰ÜÈ[Ý\ÜYLHY\šX[˜Y]\È›Üˆ]™\žH›Ü\K‚ˆÈ\ÈÚ]™\ÈHX[\ˆÝXœÝ[X[H[Ü™HÝ\œ›Ý[™[™È[XYÙ\žH›ÜˆØ\˜YÙ\ËˆÈ™ZYÚ›Üš[™ÈZ[[™ÜÈ[™\™Ù\ˆÛÛ\^\ÈÚ]Ý]Ú[™Ú[™È›ÛÙˆYX\Ý\™[Y[Ë‚ˆÈ\™ÙKØÛÛ\^›ÛÙœÈ\ÙHHÙ[™HÙˆH[ÛÛÙÛHÙYÛY[^[ÛÈ[‚ˆÈ\Þ[[Y]šXÈÛÛ™ËÖ\Ú\YZ[[™È\È›ÝÛ\YÛˆÛ™HÚYHÙˆH˜\Ý\‹‚ˆ˜\ÙWÛ]Y›Ø]
XZ[‹™Ù]
›]]YHŠHÜˆ
NØ˜\ÙWÛ™ÏY›Ø]
XZ[‹™Ù]
›Û™Ú]YHŠHÜˆ
BˆÛÜ›™\œÏV×Bˆ›ÜˆÙYÈ[ˆXZ[‹™Ù]
œÙYÛY[ÈŠHÜˆ×N‚ˆ›Þ\ÙYË™Ù]
˜›Ý[™[™×Ø›ÞŠHÜˆßBˆÝË™OX›Þ™Ù]
œÝÈŠK›Þ™Ù]
›™HŠBˆYˆÝÈ[™™N‚ˆÛÜ›™\œË™^[™
Âˆ
›Ø]
ÝË™Ù]
›]]YH‹˜\ÙWÛ]
JK›Ø]
ÝË™Ù]
›Û™Ú]YH‹˜\ÙWÛ™ÊJJKˆ
›Ø]
™K™Ù]
›]]YH‹˜\ÙWÛ]
JK›Ø]
™K™Ù]
›Û™Ú]YH‹˜\ÙWÛ™ÊJJKˆ
›Ø]
ÝË™Ù]
›]]YH‹˜\ÙWÛ]
JK›Ø]
™K™Ù]
›Û™Ú]YH‹˜\ÙWÛ™ÊJJKˆ
›Ø]
™K™Ù]
›]]YH‹˜\ÙWÛ]
JK›Ø]
ÝË™Ù]
›Û™Ú]YH‹˜\ÙWÛ™ÊJJKˆJBˆYˆ›ÝÛÜ›™\œÎœ™]\›ˆ˜\ÙWÛ]˜\ÙWÛ™ËZ[š[][BˆZ[›][Z[ŠÌH›Üˆ[ˆÛÜ›™\œÊNÛX^][X^
ÌH›Üˆ[ˆÛÜ›™\œÊBˆZ[›™Ï[Z[ŠÌWH›Üˆ[ˆÛÜ›™\œÊNÛX^™Ï[X^
ÌWH›Üˆ[ˆÛÜ›™\œÊBˆÙ[\—Û]JZ[›]
ÛX^]
KÌ‹ŒØÙ[\—Û™ÏJZ[›™ÊÛX^™ÊKÌ‹ŒˆYˆ\ÝÛJ]™ÊN‚ˆOJ]XÙ[\—Û]
JŒLLLÌŒŒˆJ™ËXÙ[\—Û™ÊJŒLLLÌŒŒ
›X]˜ÛÜÊX]œ˜YX[œÊÙ[\—Û]
JBˆ™]\›ˆX]š\Ý
JBˆ™YYY[X^
\ÝÛJ]™ÊH›Üˆ]™È[ˆÛÜ›™\œÊJÌMŒˆYˆ™YYY[Z[š[][Nœ™]\›ˆ˜\ÙWÛ]˜\ÙWÛ™ËZ[š[][Bˆ™]\›ˆÙ[\—Û]Ù[\—Û™ËX^
Z[š[][KZ[ŠX^[][K[
X]˜ÙZ[
™YYY
JJJB‚‚™Yˆ^XÝÜ[—Ù\Ü^WÜ™\]Y\Ý
XZ[ŠN‚ˆ˜\ÙWÛ]Y›Ø]
XZ[‹™Ù]
›]]YHŠHÜˆ
NØ˜\ÙWÛ™ÏY›Ø]
XZ[‹™Ù]
›Û™Ú]YHŠHÜˆ
BˆÛÜ›™\œÏV×Bˆ›ÜˆÙYÈ[ˆXZ[‹™Ù]
œÙYÛY[ÈŠHÜˆ×N‚ˆ›Þ\ÙYË™Ù]
˜›Ý[™[™×Ø›ÞŠHÜˆßNÜÝË™OX›Þ™Ù]
œÝÈŠK›Þ™Ù]
›™HŠBˆYˆÝÈ[™™N‚ˆÛÜ›™\œË™^[™
Âˆ
›Ø]
ÝË™Ù]
›]]YH‹˜\ÙWÛ]
JK›Ø]
ÝË™Ù]
›Û™Ú]YH‹˜\ÙWÛ™ÊJJKˆ
›Ø]
™K™Ù]
›]]YH‹˜\ÙWÛ]
JK›Ø]
™K™Ù]
›Û™Ú]YH‹˜\ÙWÛ™ÊJJKˆ
›Ø]
ÝË™Ù]
›]]YH‹˜\ÙWÛ]
JK›Ø]
™K™Ù]
›Û™Ú]YH‹˜\ÙWÛ™ÊJJKˆ
›Ø]
™K™Ù]
›]]YH‹˜\ÙWÛ]
JK›Ø]
ÝË™Ù]
›Û™Ú]YH‹˜\ÙWÛ™ÊJJKˆJBˆYˆ›ÝÛÜ›™\œÎœ™]\›ˆ˜\ÙWÛ]˜\ÙWÛ™ËNBˆZ[›][Z[ŠÌH›Üˆ[ˆÛÜ›™\œÊNÛX^][X^
ÌH›Üˆ[ˆÛÜ›™\œÊBˆZ[›™Ï[Z[ŠÌWH›Üˆ[ˆÛÜ›™\œÊNÛX^™Ï[X^
ÌWH›Üˆ[ˆÛÜ›™\œÊBˆÛ]JZ[›]
ÛX^]
KÌ‹ŒØÛ™ÏJZ[›™ÊÛX^™ÊKÌ‹ŒˆZYÚ[X^
KŒ
X^][Z[›]
JŒLLLÌŒŒ
BˆÚY[X^
KŒ
X^™Ë[Z[›™ÊJŒLLLÌŒŒ
›X]˜ÛÜÊX]œ˜YX[œÊÛ]
JJBˆÈX]™HÙ[™\›Ý\È›ÛÛH\›Ý[™H›ÛÙˆÛÈHX[\ˆØ[ˆÙYHHÚÛHZ[[™ËˆÈ]™]™\ˆ[\ˆHYX\Ý\™[Y[]Ù[‹‚ˆ\Ú\™Y[X^
LŒÚY
ŒKŒÎZYÚ
ŒKŒÎ
Bˆ[X]™›ÛÜŠX]›ÙÌŠ
MMMËŒÌÎLŠ›X^
Œ‹X]˜ÛÜÊX]œ˜YX[œÊÛ]
JJJŒ
KÙ\Ú\™Y
JBˆ›ÛÛO[X^
M‹Z[ŠŒ[
ŠJJBˆ™]\›ˆÛ]Û™Ë›ÛÛB‚™YˆÛÛ\—Û^Y\œÊÙ^K]™Ë˜Y]\ÏLÍ
N‚ˆ˜Y]\Ï[X^
ŒZ[ŠL[
˜Y]\ÊJJBˆO]\›X‹œ\œÙK\›[˜ÛÙJÈ›ØØ][Û‹›]]YHŽ›]›ØØ][Û‹›Û™Ú]YHŽ›™Ëœ˜Y]\ÓY]\œÈŽœ˜Y]\ËšY]ÈŽˆ’SPQÑT–WÓVQT”È‹œ™\]Z\™Y]X[]HŽˆTÑH‹œ^[Ú^™SY]\œÈŽŒŒKšÙ^HŽšÙ^_JBˆË^Y\œÏ\™\WÚœÛÛŠšÎ‹ËÜÛÛ\‹™ÛÛÙÛX\\Ë˜ÛÛKÝŒKÙ]S^Y\œÎ™Ù]ÈŠÙJBˆYˆÈOLŒœ˜Z\ÙH˜[YQ\œ›ÜŠ”ÛÛ\ˆY\šX[[XYÙ\žH[˜]˜Z[X›H›Üˆ\È›ÛÙ‹ˆŠBˆ™Ø[^Y\œË™Ù]
œ™Ø•\›ŠBˆYˆ›Ý™ØŽœ˜Z\ÙH˜[YQ\œ›ÜŠ‘ÛÛÙÛH™]\›™Y›ÛÙˆ]H]›Ý‘ÐˆY\šX[[XYÙ\žKˆŠBˆ™]\›ˆ^Y\œÂ‚™YˆÜ™X]WÜÙ\ÜÚ[ÛŠÙ^K]™ËÝ™Y]Ý\›S›Û™K[ÙOHœÛÛ\ˆ‹^Y\œÏS›Û™K[˜ÚÜ—Û]S›Û™K[˜ÚÜ—Û™ÏS›Û™K›Ü›X]YØY™\ÜÏS›Û™JN‚ˆÚÙ[]]ZY]ZY

Kš^ˆÑTÔÒSÓ”ÖÝÚÙ[—O^ÈšÙ^HŽšÙ^Kœ™ØˆŽ›^Y\œË™Ù]
œ™Ø•\›ŠHYˆ^Y\œÈ[ÙH›Û™Kœ™Ø—ØØXÚHŽ“›Û™K›X\ÚÈŽ›^Y\œË™Ù]
›X\ÚÕ\›ŠHYˆ^Y\œÈ[ÙH›Û™K›X\Ú×ØØXÚHŽ“›Û™KœÝ™Y]ŽœÝ™Y]Ý\›œÝ™Y]ØØXÚHŽ“›Û™K›]Ž›]›™ÈŽ›™Ë˜Ü™X]YŽ[YK[YJ
K›[ÙHŽ›[ÙK™˜[˜XÚ×ØØXÚHŽ“›Û™K™˜[˜XÚ×Þ›ÛÛHŽŒNK˜[˜ÚÜ—Û]Ž˜[˜ÚÜ—Û]Yˆ[˜ÚÜ—Û]\È›Ý›Û™H[ÙH]˜[˜ÚÜ—Û™ÈŽ˜[˜ÚÜ—Û™ÈYˆ[˜ÚÜ—Û™È\È›Ý›Û™H[ÙH™Ë™›Ü›X]YØY™\ÜÈŽ™›Ü›X]YØY™\ÜË™X[\—ÚYŽœÝŠÙ\ÜÚ[Û‹™Ù]
™X[\—ÚYŠHÜˆˆŠ_Bˆ›Üˆ[ˆ\Ý
ÑTÔÒSÓ”ÊN‚ˆYˆ[YK[YJ
KTÑTÔÒSÓ”ÖÝVÈ˜Ü™X]Y—OŒÍŒ”ÑTÔÒSÓ”ËœÜ
›Û™JBˆ™]\›ˆÚÙ[‚‚\˜Y\—Ü™\]Y\Ý™Yˆ™]Z[—Ü›Ü\WÜÙ\ÜÚ[ÛŠ™\ÜÛœÙJN‚ˆYˆ™\]Y\Ý›Y]ÙOH”ÔÕˆ[™™\ÜÛœÙKœÝ]\×ØÛÙHOHŒ[™™\]Y\Ýœ][ˆÈ‹Ü›Ü\H‹‹ÜÝXÝ\™H‹‹ÛØØ]KXZ[[™ÈŸN‚ˆ™\Ý[H™\ÜÛœÙK™Ù]ÚœÛÛŠÚ[[UYJHÜˆßBˆ]HH™\]Y\Ý™Ù]ÚœÛÛŠÚ[[UYJHÜˆßBˆÚÙ[ˆH™\Ý[™Ù]
ÚÙ[ˆŠHÜˆ]K™Ù]
ÚÙ[ˆŠBˆYˆÚÙ[Ž‚ˆžN‚ˆÑTÔÒSÓ”Ëœ\œÚ\Ý
ÚÙ[ŠBˆ^Ù\^Ù\[ÛŽ‚ˆ\›ÙÙÙ\‹Ø\›š[™Ê”›Ü\H[XYÙ\žH™XÛÝ™\žHY]Y]HÛÝ[›Ý™H™]Z[™YŠBˆ™]\›ˆ™\ÜÛœÙB‚\œÜÝ
‹Ü›Ü\HŠB™Yˆ›Ü\WÙ]J
N‚ˆX[\—ÚY\ÝŠÙ\ÜÚ[Û‹™Ù]
™X[\—ÚYŠHÜˆˆŠBˆ\™\]Y\Ý™Ù]ÚœÛÛŠÚ[[UYJHÜˆßBˆYˆ›Ý\Ú[œÝ[˜ÙJXÝ
Nœ™]\›ˆœÛÛšYžJ\œ›ÜH”›Ü\H]Z[È]\Ý™H[ˆØš™XÝˆŠKˆÜ\˜][Û\ÝŠ™\]Y\ÝšXY\œË™Ù]
’Y[\Ý[˜ÞKRÙ^HŠHÜˆˆŠBˆYˆÜ\˜][Ûˆ[™›Ý™K™[X]Ú
ˆ–ÐKV˜K^ŒNWËW^ÌKLŽH‹Ü\˜][ÛŠNœ™]\›ˆœÛÛšYžJ\œ›ÜH’[˜[YÛÚÝ\Y[YšY\‹ˆŠKˆžN™YÙ\ÝY\Ý[X]WÝ™\œÚ[ÛŠ
Bˆ^Ù\
˜[YQ\œ›Ü‹\Q\œ›ÜŠNœ™]\›ˆœÛÛšYžJ\œ›ÜH’[˜[Y›Ü\H]Z[ËˆŠKˆÛÛY\Ý[X]WÙŠ
BˆžN‚ˆØÚ×ØXØÛÝ[
ÛÛ‹X[\—ÚY
BˆYˆ™Ù]
	Ü™\\™WÛÛ›IÊN‚ˆYˆ›ÝÜ\˜][ÛŽœ™]\›ˆœÛÛšYžJ\œ›ÜH“ÛÚÝ\Y[YšY\ˆ™\]Z\™YˆŠKˆÛXÛÛ‹™^XÝ]J”ÑSPÕ^[ØYÚ\Ú™\ÜÛœÙWÚœÛÛˆ”“ÓH\Ý[X]WÜØ]™WÜ™XÙZ\ÈÒT‘HX[\—ÚYOÈS‘Ü\˜][Û—ÚYOÈ‹
X[\—ÚYœ™\\™YˆŠÛÜ\˜][ÛŠJK™™]ÚÛ™J
BˆYˆÛ‚ˆYˆÛÈœ^[ØYÚ\Ú—HOYYÙ\Ýœ™]\›ˆœÛÛšYžJ\œ›ÜH•\ÈÛÚÝ\Y[YšY\ˆØ\È\ÙY›ÜˆHY™™\™[›Ü\KˆŠKBˆ™\\™YZœÛÛ‹›ØYÊÛÈœ™\ÜÛœÙWÚœÛÛˆ—JBˆYˆ›ÝÑTÔÒSÓ”Ë™Ù]
™\\™Y™Ù]
ÚÙ[ˆŠJNœ™]\›ˆœÛÛšYžJ\œ›ÜH”›Ü\H™\\˜][Ûˆ^\™Yˆ™]žHØY›Ü\KˆŠKLˆ™]\›ˆœÛÛšYžJ™\\™Y
BˆÈÚXÚÈÝ\œ™[[ÝØ[˜ÙHÚ]Ý]Ü[™[™È]Ú[H[XYÙ\È\™H[™[™Ë‚ˆÛÛ‹™^XÝ]J”ÐU‘TÒS•[XYÙWØ[ÝØ[˜ÙHŠBˆ[ÝÙY\ÙY[Z]XÛÛœÝ[YWÜ›Ü\WÛÛÚÝ\
X[\—ÚYÛÛŠBˆÛÛ‹™^XÝ]J”“ÓPÒÈÈÐU‘TÒS•[XYÙWØ[ÝØ[˜ÙHŠNØÛÛ‹™^XÝ]J”‘SPTÑHÐU‘TÒS•[XYÙWØ[ÝØ[˜ÙHŠBˆYˆ›Ý[ÝÙY‚ˆ›ÝÏXÛÛ‹™^XÝ]J”ÑSPÕ[—ØÛÙH”“ÓHX[\œÈÒT‘HYOÈ‹
X[\—ÚY
JK™™]ÚÛ™J
BˆYˆ›ÝÈ[™ÝŠ›ÝÖÈœ[—ØÛÙH—HÜˆˆŠK›ÝÙ\Š
OOHšX[Žœ™]\›ˆœÛÛšYžJ\œ›ÜH‘œ™YHšX[ÛÛ\]Kˆ‹ÛÙOHšX[Û[Z]Ü™XXÚYŠKÂˆ™]\›ˆœÛÛšYžJ\œ›ÜH”›Ü\HÛÚÝ\[ÝØ[˜ÙH™XXÚYˆŠKÂˆ™\ÜÛœÙOX\›XZÙWÜ™\ÜÛœÙJ\™›Ü›WÜ›Ü\WÛÛÚÝ\

JBˆYˆ™\ÜÛœÙKœÝ]\×ØÛÙOOLŒ‚ˆÛÛ‹™^XÝ]J’S”ÑT•S•È\Ý[X]WÜØ]™WÜ™XÙZ\ÊX[\—ÚYÜ\˜][Û—ÚY^[ØYÚ\Ú™\ÜÛœÙWÚœÛÛŠHSQTÊËËËÊH‹
X[\—ÚYœ™\\™YˆŠÛÜ\˜][Û‹YÙ\ÝœÛÛ‹™[\Ê™\ÜÛœÙK™Ù]ÚœÛÛŠ
JJJBˆÛÛ‹˜ÛÛ[Z]

Bˆ™]\›ˆ™\ÜÛœÙBˆYˆÜ\˜][ÛŽ‚ˆÛXÛÛ‹™^XÝ]J”ÑSPÕ^[ØYÚ\Ú™\ÜÛœÙWÚœÛÛˆ”“ÓH\Ý[X]WÜØ]™WÜ™XÙZ\ÈÒT‘HX[\—ÚYOÈS‘Ü\˜][Û—ÚYOÈ‹
X[\—ÚY›ÛÚÝ\ˆŠÛÜ\˜][ÛŠJK™™]ÚÛ™J
BˆYˆÛ‚ˆYˆÛÈœ^[ØYÚ\Ú—HOYYÙ\Ýœ™]\›ˆœÛÛšYžJ\œ›ÜH•\ÈÛÚÝ\Y[YšY\ˆØ\È\ÙY›ÜˆHY™™\™[›Ü\KˆŠKBˆ™]\›ˆœÛÛšYžJœÛÛ‹›ØYÊÛÈœ™\ÜÛœÙWÚœÛÛˆ—JJBˆ[ÝÙY\ÙY[Z]XÛÛœÝ[YWÜ›Ü\WÛÛÚÝ\
X[\—ÚYÛÛŠBˆYˆ›Ý[ÝÙY‚ˆ›ÝÏXÛÛ‹™^XÝ]J”ÑSPÕ[—ØÛÙH”“ÓHX[\œÈÒT‘HYOÈ‹
X[\—ÚY
JK™™]ÚÛ™J
BˆYˆ›ÝÈ[™ÝŠ›ÝÖÈœ[—ØÛÙH—HÜˆˆŠK›ÝÙ\Š
OOHšX[Žœ™]\›ˆœÛÛšYžJ\œ›ÜH‘œ™YHšX[ÛÛ\]Kˆ‹ÛÙOHšX[Û[Z]Ü™XXÚY‹\Ù\—Ù\œ›ÜH–[Ýx &]™H\ÙY[Èœ™YH›Ü\HYX\Ý\™[Y[È[˜ÛYYÚ][Ý\ˆY\šT][ÝHšX[ˆŠKÂˆ™]\›ˆœÛÛšYžJ\œ›ÜH”›Ü\HÛÚÝ\[ÝØ[˜ÙH™XXÚYˆ‹\Ù\—Ù\œ›ÜYˆ–[Ý\ˆXØÛÝ[\È\ÙY[Û[Z]H›Ü\HYX\Ý\™[Y[È[˜ÛYYÚ]HÝ\œ™[[‹ˆŠKÂˆ™\ÜÛœÙOX\›XZÙWÜ™\ÜÛœÙJ\™›Ü›WÜ›Ü\WÛÛÚÝ\

JBˆYˆ™\ÜÛœÙKœÝ]\×ØÛÙOOLŒ‚ˆYˆÜ\˜][ÛŽ˜ÛÛ‹™^XÝ]J’S”ÑT•S•È\Ý[X]WÜØ]™WÜ™XÙZ\ÊX[\—ÚYÜ\˜][Û—ÚY^[ØYÚ\Ú™\ÜÛœÙWÚœÛÛŠHSQTÊËËËÊH‹
X[\—ÚY›ÛÚÝ\ˆŠÛÜ\˜][Û‹YÙ\ÝœÛÛ‹™[\Ê™\ÜÛœÙK™Ù]ÚœÛÛŠ
JJJBˆÛÛ‹˜ÛÛ[Z]

Bˆ™]\›ˆ™\ÜÛœÙBˆš[˜[N˜ÛÛ‹˜ÛÜÙJ
B‚\œÜÝ
‹Ü›Ü\KØXØÙ\ŠB™YˆXØÙ\Ü›Ü\J
N‚ˆX[\—ÚY\ÝŠÙ\ÜÚ[Û‹™Ù]
™X[\—ÚYŠHÜˆˆŠNÙ\™\]Y\Ý™Ù]ÚœÛÛŠÚ[[UYJHÜˆßBˆYˆ›Ý\Ú[œÝ[˜ÙJXÝ
Nœ™]\›ˆœÛÛšYžJ\œ›ÜH’[˜[Y›Ü\HÛÛ™š\›X][Û‹ˆŠKˆÜ\˜][Û\ÝŠ™Ù]
›Ü\˜][Û—ÚYŠHÜˆˆŠNÝÚÙ[\ÝŠ™Ù]
ÚÙ[ˆŠHÜˆˆŠBˆÛÛY\Ý[X]WÙŠ
BˆžN‚ˆØÚ×ØXØÛÝ[
ÛÛ‹X[\—ÚY
Bˆ[™[™ÏXÛÛ‹™^XÝ]J”ÑSPÕ^[ØYÚ\Ú™\ÜÛœÙWÚœÛÛˆ”“ÓH\Ý[X]WÜØ]™WÜ™XÙZ\ÈÒT‘HX[\—ÚYOÈS‘Ü\˜][Û—ÚYOÈ‹
X[\—ÚYœ™\\™YˆŠÛÜ\˜][ÛŠJK™™]ÚÛ™J
BˆYˆ›Ý[™[™Îœ™]\›ˆœÛÛšYžJ\œ›ÜH”›Ü\H™\\˜][Ûˆ›Ý›Ý[™ˆ™]žHØY›Ü\KˆŠKˆ™\Ý[ZœÛÛ‹›ØYÊ[™[™ÖÈœ™\ÜÛœÙWÚœÛÛˆ—JBˆYˆ™\Ý[™Ù]
ÚÙ[ˆŠHO]ÚÙ[Žœ™]\›ˆœÛÛšYžJ\œ›ÜH”›Ü\HÛÛ™š\›X][ÛˆÙ\È›ÝX]ÚˆŠKBˆ™XÙZ\XÛÛ‹™^XÝ]J”ÑSPÕ™\ÜÛœÙWÚœÛÛˆ”“ÓH\Ý[X]WÜØ]™WÜ™XÙZ\ÈÒT‘HX[\—ÚYOÈS‘Ü\˜][Û—ÚYOÈ‹
X[\—ÚY›ÛÚÝ\ˆŠÛÜ\˜][ÛŠJK™™]ÚÛ™J
BˆYˆ™XÙZ\œ™]\›ˆœÛÛšYžJÚÏUYJBˆYˆ›ÝÑTÔÒSÓ”Ë™Ù]
ÚÙ[ŠNœ™]\›ˆœÛÛšYžJ\œ›ÜH”›Ü\H™\\˜][Ûˆ^\™Yˆ™]žHØY›Ü\KˆŠKLˆ[ÝÙY\ÙY[Z]XÛÛœÝ[YWÜ›Ü\WÛÛÚÝ\
X[\—ÚYÛÛŠBˆYˆ›Ý[ÝÙYœ™]\›ˆœÛÛšYžJ\œ›ÜH”›Ü\HÛÚÝ\[ÝØ[˜ÙH™XXÚYˆ^\Ý[™ÈÛÜšÈ\È[˜Ú[™ÙYˆŠKÂˆÛÛ‹™^XÝ]J’S”ÑT•S•È\Ý[X]WÜØ]™WÜ™XÙZ\ÊX[\—ÚYÜ\˜][Û—ÚY^[ØYÚ\Ú™\ÜÛœÙWÚœÛÛŠHSQTÊËËËÊH‹
X[\—ÚY›ÛÚÝ\ˆŠÛÜ\˜][Û‹[™[™ÖÈœ^[ØYÚ\Ú—K[™[™ÖÈœ™\ÜÛœÙWÚœÛÛˆ—JJBˆÛÛ‹˜ÛÛ[Z]

NÜ™]\›ˆœÛÛšYžJÚÏUYJBˆš[˜[N˜ÛÛ‹˜ÛÜÙJ
B‚™Yˆ\™›Ü›WÜ›Ü\WÛÛÚÝ\

N‚ˆÙ^O\ÝŠ™Ù]
šÙ^HŠHÜˆˆŠKœÝš\

NØY™\ÜÏ\ÝŠ™Ù]
˜Y™\ÜÈŠHÜˆˆŠKœÝš\

BˆYˆ›ÝÙ^HÜˆ›ÝY™\ÜÎœ™]\›ˆœÛÛšYžJ\œ›ÜHTHÙ^H[™Y™\ÜÈ\™H™\]Z\™YˆŠKˆ[™\ÝžOY™Ù]
˜\Ú[™\Ü×Ý\H‹œ›ÛÙš[™ÈŠBˆYˆ›Ý\Ú[œÝ[˜ÙJ[™\ÝžKÝŠHÜˆ[™\ÝžH›Ý[ˆÈœ›ÛÙš[™È‹œÛ›ÝÈ‹œ™\ÜÝ\™H‹œ]š[™È‹›[™ØØ\[™È‹˜ÛÛ[Y\˜ÚX[ŸN‚ˆ™]\›ˆœÛÛšYžJ\œ›ÜH•[šÛ›ÝÛˆYX\Ý\™[Y[[™\ÝžKˆŠKˆžN‚ˆ\™XÝX›ÛÛ
™Ù]
™\™XÝØÛÛÜ™[˜]\ÈŠJNÙÏ^ßBˆYˆ\™XÝ‚ˆ]Y›Ø]
™Ù]
›]]YHŠJNÛ™ÏY›Ø]
™Ù]
›Û™Ú]YHŠJBˆYˆ›ÝX]š\Ùš[š]J]
HÜˆ›ÝX]š\Ùš[š]J™ÊHÜˆXœÊ]
OŽKŒLLLŽÎÜˆXœÊ™ÊOŒNˆ™]\›ˆœÛÛšYžJ\œ›ÜH’[˜[YÛÛÜ™[˜]\Ëˆ‹\Ù\—Ù\œ›ÜH‘[\ˆ˜[Y]]YH[™Û™Ú]YHÛÛÜ™[˜]\ËˆŠKˆ›Ü›X]YYˆžÛ]‹™ŸKÛ™Î‹™ŸH‚ˆ[ÙN‚ˆ^XÝYØÚ]O\ÝŠ™Ù]
™^XÝYØÚ]HŠHÜˆˆŠKœÝš\

NÙ^XÝYÜ›Ýš[˜ÙO\ÝŠ™Ù]
™^XÝYÜ›Ýš[˜ÙHŠHÜˆˆŠKœÝš\

NÙ^XÝYÜÝ™Y]Û[X™\\ÝŠ™Ù]
™^XÝYÜÝ™Y]Û[X™\ˆŠHÜˆˆŠKœÝš\

Bˆ›Ü›X[^™YØY™\ÜË[š]Û[X™\][š]ØY™\ÜÊY™\ÜË^XÝYÜ›Ýš[˜ÙJBˆ^XÝYÜÝ™Y]Û[X™\][š]Û[X™\ˆÜˆ^XÝYÜÝ™Y]Û[X™\‚ˆÜËÙ[ËÛX]ÚYÜ]Y\žOYÛÛÙÛWÙÙ[ØÛÙWÙš\œÝ
Ù^KY™\ÜËÛÛ\Û™[×ØÛÝ[žOUYK^XÝYÜ›Ýš[˜ÙOY^XÝYÜ›Ýš[˜ÙJBˆYˆÜÈOLŒÜˆÙ[Ë™Ù]
œÝ]\ÈŠHOH“ÒÈˆÜˆ›ÝÙ[Ë™Ù]
œ™\Ý[ÈŠNœ™]\›ˆœÛÛšYžJ\œ›ÜH‘ÛÛÙÛHÛÝ[›Ýš[™]Y™\ÜËˆÚXÚÈHY™\ÜÈ[™žHYØZ[‹ˆ‹\Ù\—Ù\œ›ÜH‘ÛÛÙÛHÛÝ[›Ýš[™]Y™\ÜËˆÚXÚÈHY™\ÜÈ[™žHYØZ[‹ˆŠKˆÏYÙ[ÖÈœ™\Ý[È—VÌNÜ\ÏYÙ[ØÛÙWÜ\ÊÊBˆYˆY™\Ü×ÛZ\ÛX]Ú
^XÝYØÚ]K^XÝYÜ›Ýš[˜ÙK\Ë^XÝYÜÝ™Y]Û[X™\ŠN‚ˆ™]\›ˆœÛÛšYžJ\œ›ÜHQ‘TÔÈÑTÓ‰ÕPUÒ‹\Ù\—Ù\œ›Ü[Z\ÛX]ÚÛY\ÜØYÙJ^XÝYØÚ]K^XÝYÜ›Ýš[˜ÙK\ÊK›Ü›X]YØY™\ÜÏYË™Ù]
™›Ü›X]YØY™\ÜÈŠK\Ï\\ÊKBˆØÏYÖÈ™Ù[ÛY]žH—VÈ›ØØ][Ûˆ—NÛ]Y›Ø]
ØÖÈ›]—JNÛ™ÏY›Ø]
ØÖÈ›™È—JNÙ›Ü›X]YYË™Ù]
™›Ü›X]YØY™\ÜÈŠHÜˆY™\ÜÂˆYˆ[™\ÝžHOHœ›ÛÙš[™ÈˆÜˆX[X[Ü›ÛÙ—ÜXWÙ[˜X›Y

N‚ˆÈÙ\šXÙKX\™XKÛ[™X\ˆÙ[ÛY]žH\ÈYX\Ý\™YØØ[HÝ™\ˆHØ[YHÝ]XÂˆÈX\È[XYÙ\žKˆÛÛ\ˆ›ÛÙˆ]H\È[\ÙY[ˆ\ÙHš]™HÛÜšÙ›ÝÜË‚ˆÝ™Y]Ý\›Ý™Y]Ù]O\Ý™Y]ÝšY]×Ú[™›ÊÙ^K›Ü›X]Y]™Ë]™ÊBˆÚÙ[XÜ™X]WÜÙ\ÜÚ[ÛŠÙ^K]™ËÝ™Y]Ý\›\Ý™Y]Ý\›[ÙOH›X[X[Ü›ÛÙ—ÜÝ]XÈˆYˆ[™\ÝžOOHœ›ÛÙš[™Èˆ[ÙHœÝ\™˜XÙWÜÝ]XÈ‹[˜ÚÜ—Û][][˜ÚÜ—Û™Ï[™Ë›Ü›X]YØY™\ÜÏY›Ü›X]Y
BˆYˆ\™XÝ”ÑTÔÒSÓ”ÖÝÚÙ[—K\]JÈ™^XÝÜ[ˆŽ•YK™\Ü^WÛ]Ž›]™\Ü^WÛ™ÈŽ›™Ë™\Ü^WÞ›ÛÛHŽŒN_JBˆ™]\›ˆœÛÛšYžJÚÙ[]ÚÙ[‹X[X[Ü›ÛÙ—ÛÛ›OZ[™\ÝžOOHœ›ÛÙš[™È‹˜[˜XÚÏUYK˜[˜XÚ×ØY\šX[HœÝ]XÈ‹Ù[\^È›]]YHŽ›]›Û™Ú]YHŽ›™ßK›Ü›X]YØY™\ÜÏY›Ü›X]Y\ÏYÙ[ØÛÙWÜ\ÊÊKÝ™Y]Ù]O\Ý™Y]Ù]K^XÝÜ[—Ù\Ü^OX›ÛÛ
\™XÝ
JBˆžN‚ˆXZ[XZ[[™ÊÙ^K]™ÊBˆ^Ù\ÛÛ\Z[[™Ó›Ý›Ý[™‚ˆÈZ[[™È[œÚYÚÈØ[ˆ™H[˜]˜Z[X›H]™[ˆÚ[ˆÛÛÙÛHÝ[\È\ØX›BˆÈÛÛ\ˆY\šX[]H›ÜˆH\™XKˆžH]^\Ý[™ÈÛÛ\ˆ]H^Y\œÈTBˆÈš\œÝÛÈHX[\ˆØ[ˆ˜XÙHX[X[HÚ]Ý][›Ý\ˆÛÛÙÛH›ÙXÝ‚ˆÝ™Y]Ý\›Ý™Y]Ù]O\Ý™Y]ÝšY]×Ú[™›ÊÙ^K›Ü›X]Y]™Ë]™ÊBˆžN‚ˆ˜[˜XÚ×Û^Y\œÏ\ÛÛ\—Û^Y\œÊÙ^K]™ÊBˆÚÙ[XÜ™X]WÜÙ\ÜÚ[ÛŠÙ^K]™ËÝ™Y]Ý\›\Ý™Y]Ý\›[ÙOH›X[X[ÜÛÛ\ˆ‹^Y\œÏY˜[˜XÚ×Û^Y\œË[˜ÚÜ—Û][][˜ÚÜ—Û™Ï[™Ë›Ü›X]YØY™\ÜÏY›Ü›X]Y
Bˆ™]\›ˆœÛÛšYžJÚÙ[]ÚÙ[‹˜[˜XÚÏUYK˜[˜XÚ×ØY\šX[HœÛÛ\ˆ‹Ù[\^È›]]YHŽ›]›Û™Ú]YHŽ›™ßK›Ü›X]YØY™\ÜÏY›Ü›X]Y\ÏYÙ[ØÛÙWÜ\ÊÊKÝ™Y]Ù]O\Ý™Y]Ù]JBˆ^Ù\^Ù\[ÛŽ‚ˆÈ\Ý\Ü^H˜[˜XÚÈÛ›KˆYˆX\ÈÝ]XÈ\È›Ý[˜X›YHRBˆÈÚ]™\ÈHÛX\ˆÙ]\Y\ÜØYÙH[œÝXYÙˆ^ÜÚ[™ÈH˜]ÈÛÛÙÛH\œ›Ü‹‚ˆÚÙ[XÜ™X]WÜÙ\ÜÚ[ÛŠÙ^K]™ËÝ™Y]Ý\›\Ý™Y]Ý\›[ÙOH›X[X[ÜÝ]XÈ‹^Y\œÏS›Û™K[˜ÚÜ—Û][][˜ÚÜ—Û™Ï[™Ë›Ü›X]YØY™\ÜÏY›Ü›X]Y
Bˆ™]\›ˆœÛÛšYžJÚÙ[]ÚÙ[‹˜[˜XÚÏUYK˜[˜XÚ×ØY\šX[HœÝ]XÈ‹Ù[\^È›]]YHŽ›]›Û™Ú]YHŽ›™ßK›Ü›X]YØY™\ÜÏY›Ü›X]Y\ÏYÙ[ØÛÙWÜ\ÊÊKÝ™Y]Ù]O\Ý™Y]Ù]JBˆ[Y×Û][Y×Û™Ë[Y×Ü˜Y]\Ï\›ÛÙ—Ú[XYÙ\žWÜ™\]Y\Ý
XZ[ŠNÛ^Y\œÏ\ÛÛ\—Û^Y\œÊÙ^K[Y×Û][Y×Û™Ë[Y×Ü˜Y]\ÊBˆÝ™Y]Ý\›Ý™Y]Ù]O\Ý™Y]ÝšY]×Ú[™›ÊÙ^K›Ü›X]Y]™Ë]™ÊBˆÚÙ[XÜ™X]WÜÙ\ÜÚ[ÛŠÙ^KXZ[–È›]]YH—KXZ[–È›Û™Ú]YH—KÝ™Y]Ý\›\Ý™Y]Ý\›[ÙOHœÛÛ\ˆ‹^Y\œÏ[^Y\œË[˜ÚÜ—Û][][˜ÚÜ—Û™Ï[™Ë›Ü›X]YØY™\ÜÏY›Ü›X]Y
BˆYˆ\™XÝ‚ˆËY^XÝÜ[—Ù\Ü^WÜ™\]Y\Ý
XZ[ŠBˆÑTÔÒSÓ”ÖÝÚÙ[—K\]JÈ™^XÝÜ[ˆŽ•YK™\Ü^WÛ]Ž™™\Ü^WÛ™ÈŽ™Ë™\Ü^WÞ›ÛÛHŽ™‹™˜[˜XÚ×Þ›ÛÛHŽ™ŸJBˆ™]\›ˆœÛÛšYžJÚÙ[]ÚÙ[‹XZ[[XZ[‹›Ü›X]YØY™\ÜÏY›Ü›X]Y\ÏYÙ[ØÛÙWÜ\ÊÊKÝ™Y]Ù]O\Ý™Y]Ù]K[˜ÚÜ^È›]]YHŽ›]›Û™Ú]YHŽ›™ßK^XÝÜ[—Ù\Ü^OX›ÛÛ
\™XÝ
JBˆ^Ù\^Ù\[Ûˆ\ÈN‚ˆ™]\›ˆœÛÛšYžJ\œ›Ü\ÝŠJK\Ù\—Ù\œ›ÜH‘ÛÛÙÛHÛÝ[›ÝÛÛ\]HH]]ÛX]XÈ›ÛÙˆYX\Ý\™[Y[›Üˆ\È›Ü\KˆžHYØZ[‹Üˆ\ÙHHX[X[˜[˜XÚÈYˆÙ™™\™YˆŠK‚\œÜÝ
‹ÜÝXÝ\™HŠB™YˆÝXÝ\™J
N‚ˆ\™\]Y\Ý™Ù]ÚœÛÛŠÚ[[UYJHÜˆßNÜÙ\ÜÏTÑTÔÒSÓ”Ë™Ù]
ÝŠ™Ù]
ÚÙ[ˆŠHÜˆˆŠJBˆYˆ›ÝÙ\ÜÈÜˆÙ\ÜË™Ù]
™X[\—ÚYŠHO\ÝŠÙ\ÜÚ[Û‹™Ù]
™X[\—ÚYŠHÜˆˆŠNœ™]\›ˆœÛÛšYžJ\œ›ÜH”›Ü\HÙ\ÜÚ[Ûˆ^\™Yˆ™[ØYH›Ü\Kˆ‹\Ù\—Ù\œ›ÜH”›Ü\HÙ\ÜÚ[Ûˆ^\™Yˆ™[ØYH›Ü\KˆŠKˆYˆX[X[Ü›ÛÙ—ÜÙ\ÜÚ[ÛŠÙ\ÜÊHÜˆX[X[Ü›ÛÙ—ÜXWÙ[˜X›Y

Nœ™]\›ˆœÛÛšYžJ\œ›ÜH]]ÛX]XÈ›ÛÙš[™È\È[˜]˜Z[X›H[ˆX[X[[Û›HPH[ÙKˆŠKBˆžN‚ˆ›ÛÙXZ[[™ÊÙ\ÜÖÈšÙ^H—K›Ø]
È›]]YH—JK›Ø]
È›Û™Ú]YH—JJBˆÈ™]Ú[XYÙ\žHÛ›HÚ[ˆHÛY[\ÈXØÙ\Y\È\Ý[˜ÝZ[[™Ë‚ˆX\Ú×ÚY]]ZY]ZY

Kš^ˆÙ\ÜËœÙ]Y˜][
œÝXÝ\™WÛX\ÚÜÈ‹ßJVÛX\Ú×ÚYO^Èœ›ÛÙˆŽœ›ÛÙ‹›X\Ú×ØØXÚHŽ“›Û™_Bˆ›ÛÙ–È›X\Ú×Ý\›—OH‹ÜÝXÝ\™K[X\ÚËÈŠÜÝŠÈÚÙ[ˆ—JJÈ‹ÈŠÛX\Ú×ÚYˆ™]\›ˆœÛÛšYžJ›ÛÙŠBˆ^Ù\ÛÛ\Z[[™Ó›Ý›Ý[™œ™]\›ˆœÛÛšYžJ\œ›ÜHZ[[™È›Ý›Ý[™‹\Ù\—Ù\œ›ÜH‘ÛÛÙÛHÛÝ[›Ý]]ÛX]XØ[HX]Ú]›ÛÙ‹ˆÛXÚÈÛÜÙ\ˆÈHÙ[™HÜˆY]X[X[KˆŠKˆ^Ù\^Ù\[Ûˆ\ÈNœ™]\›ˆœÛÛšYžJ\œ›Ü\ÝŠJK\Ù\—Ù\œ›ÜH‘ÛÛÙÛHÛÝ[›ÝYX\Ý\™H]›ÛÙˆšYÚ›ÝËˆŠK‚\™Ù]
‹ÜÝXÝ\™K[X\ÚËÏÚÙ[‹ÏX\Ú×ÚYˆŠB™YˆÝXÝ\™WÛX\ÚÊÚÙ[‹X\Ú×ÚY
N‚ˆÙ\ÜÏTÑTÔÒSÓ”Ë™Ù]
ÚÙ[ŠBˆYˆ›ÝÙ\ÜÈÜˆÙ\ÜË™Ù]
™X[\—ÚYŠHO\ÝŠÙ\ÜÚ[Û‹™Ù]
™X[\—ÚYŠHÜˆˆŠN‚ˆ™]\›ˆœÛÛšYžJÛÙOHTKSPTÒËTÑTÔÒSÓˆŠKˆYˆX[X[Ü›ÛÙ—ÜÙ\ÜÚ[ÛŠÙ\ÜÊHÜˆX[X[Ü›ÛÙ—ÜXWÙ[˜X›Y

Nœ™]\›ˆœÛÛšYžJÛÙOHTKSPS•PSSÓ“HŠKBˆ][OJÙ\ÜË™Ù]
œÝXÝ\™WÛX\ÚÜÈŠHÜˆßJK™Ù]
X\Ú×ÚY
BˆYˆ›Ý][Nœ™]\›ˆœÛÛšYžJÛÙOHTKSPTÒËT‘Q‘T‘SÑHŠKˆÝYÙOH“VQT”È‚ˆžN‚ˆYˆ][VÈ›X\Ú×ØØXÚH—H\È›Û™N‚ˆ]™Ë˜Y]\Ï\›ÛÙ—Ú[XYÙ\žWÜ™\]Y\Ý
][VÈœ›ÛÙˆ—JBˆ^Y\œÏ\ÛÛ\—Û^Y\œÊÙ\ÜÖÈšÙ^H—K]™Ë˜Y]\ÊBˆ\›[^Y\œË™Ù]
›X\ÚÕ\›ŠBˆYˆ›Ý\›œ™]\›ˆœÛÛšYžJÛÙOHTKSPTÒËS“ÕT“Õ’QQŠKˆÙ\H‰ˆˆYˆÈˆ[ˆ\›[ÙHÈ‚ˆÝYÙOH‘ÕÓ“ÐQ‚ˆ][VÈ›X\Ú×ØØXÚH—O\™\WØž]\Ê\›
ÜÙ\
ÈšÙ^OHŠÝ\›X‹œ\œÙKœ][ÝJÙ\ÜÖÈšÙ^H—JJBˆÝ›ÙOZ][VÈ›X\Ú×ØØXÚH—Bˆ™]\›ˆ™\ÜÛœÙJ›ÙKÛÛ[Ý\OXÝ
Bˆ^Ù\^Ù\[Ûˆ\ÈN‚ˆ\Ý™X[OYÙ]]ŠK˜ÛÙH‹›Û™JBˆÝY™š^H‹HŠÜÝŠ\Ý™X[JHYˆ\Ú[œÝ[˜ÙJ\Ý™X[K[
H[ÙHˆ‚ˆ™]\›ˆœÛÛšYžJÛÙOHTKSPTÒËHŠÜÝYÙJÜÝY™š^
KLÂ‚\œÜÝ
‹ÛØØ]KXZ[[™ÈŠB™YˆØØ]WØZ[[™Ê
N‚ˆ\™\]Y\Ý™Ù]ÚœÛÛŠÚ[[UYJHÜˆßNÜÙ\ÜÏTÑTÔÒSÓ”Ë™Ù]
ÝŠ™Ù]
ÚÙ[ˆŠHÜˆˆŠJBˆYˆ›ÝÙ\ÜÎœ™]\›ˆœÛÛšYžJ\œ›ÜH”›Ü\HÙ\ÜÚ[Ûˆ^\™Yˆ‹\Ù\—Ù\œ›ÜH”›Ü\HÙ\ÜÚ[Ûˆ^\™Yˆ™[ØYH›Ü\KˆŠKˆYˆX[X[Ü›ÛÙ—ÜÙ\ÜÚ[ÛŠÙ\ÜÊHÜˆX[X[Ü›ÛÙ—ÜXWÙ[˜X›Y

Nœ™]\›ˆœÛÛšYžJ\œ›ÜH]]ÛX]XÈ›ÛÙš[™È\È[˜]˜Z[X›H[ˆX[X[[Û›HPH[ÙKˆŠKBˆžN‚ˆ]Y›Ø]
È›]]YH—JNÛ™ÏY›Ø]
È›Û™Ú]YH—JNÛXZ[XZ[[™ÊÙ\ÜÖÈšÙ^H—K]™ÊNÚ[Y×Û][Y×Û™Ë[Y×Ü˜Y]\Ï\›ÛÙ—Ú[XYÙ\žWÜ™\]Y\Ý
XZ[ŠNÛ^Y\œÏ\ÛÛ\—Û^Y\œÊÙ\ÜÖÈšÙ^H—K[Y×Û][Y×Û™Ë[Y×Ü˜Y]\ÊBˆÝ™Y]Ý\›Ý™Y]Ù]O\Ý™Y]ÝšY]×Ú[™›ÊÙ\ÜÖÈšÙ^H—KÙ\ÜË™Ù]
™›Ü›X]YØY™\ÜÈŠHÜˆˆ‹Ù\ÜË™Ù]
˜[˜ÚÜ—Û]ŠKÙ\ÜË™Ù]
˜[˜ÚÜ—Û™ÈŠKÙ\ÜË™Ù]
˜[˜ÚÜ—Û]ŠKÙ\ÜË™Ù]
˜[˜ÚÜ—Û™ÈŠJBˆÙ\ÜË\]JÈœ™ØˆŽ›^Y\œË™Ù]
œ™Ø•\›ŠKœ™Ø—ØØXÚHŽ“›Û™K›X\ÚÈŽ›^Y\œË™Ù]
›X\ÚÕ\›ŠK›X\Ú×ØØXÚHŽ“›Û™K›]Ž›XZ[–È›]]YH—K›™ÈŽ›XZ[–È›Û™Ú]YH—K›[ÙHŽˆœÛÛ\ˆ‹œÝ™Y]ŽœÝ™Y]Ý\›œÝ™Y]ØØXÚHŽ“›Û™_JBˆ™]\›ˆœÛÛšYžJXZ[[XZ[‹Ý™Y]Ù]O\Ý™Y]Ù]JBˆ^Ù\ÛÛ\Z[[™Ó›Ý›Ý[™œ™]\›ˆœÛÛšYžJ\œ›ÜHZ[[™È›Ý›Ý[™‹\Ù\—Ù\œ›ÜH‘ÛÛÙÛHÝ[Ø[››Ý]]ÛX]XØ[HYX\Ý\™H\È›ÛÙ‹ˆžHH™X\˜žHÚ[ÜˆÚÛÜÙHX[X[YX\Ý\™[Y[ˆŠKˆ^Ù\^Ù\[Ûˆ\ÈNœ™]\›ˆœÛÛšYžJ\œ›Ü\ÝŠJK\Ù\—Ù\œ›ÜH‘ÛÛÙÛHÛÝ[›ÝÛÛ\]H]]ÛX]XÈYX\Ý\™[Y[]]Ú[ˆ[ÝHØ[ˆ\ÙHX[X[YX\Ý\™[Y[ˆŠK‚\œÜÝ
‹ÛX[X[\™\Ü[X\ÏÚÙ[ˆŠB™YˆX[X[Ü™\ÜÛX\
ÚÙ[ŠN‚ˆˆˆ”™\Ü[Û›H[XYÙNˆÛÛÙÛHØ][]H
ÈX[\ˆX[X[Ý][™H˜ZÙYÙÙ]\‹ˆˆˆ‚ˆÙ\ÜÏTÑTÔÒSÓ”Ë™Ù]
ÚÙ[ŠBˆYˆ›ÝÙ\ÜÎœ™]\›ˆ™\ÜÛœÙJ”Ù\ÜÚ[Ûˆ^\™Y‹Ý]\ÏM
BˆžN‚ˆ]O\™\]Y\Ý™Ù]ÚœÛÛŠÚ[[UYJHÜˆßNÜ[™\ÏY]K™Ù]
œ[™\ÈŠHÜˆ×BˆÛX[V×Bˆ›Üˆ[™H[ˆ[™\Î‚ˆÏV×Bˆ›Üˆˆ[ˆ
[™HÜˆ×JN‚ˆžN‚ˆ]Y›Ø]
‹™Ù]
›]ŠJNÛ™ÏY›Ø]
‹™Ù]
›™ÈŠJBˆYˆNL[]NL[™LN[™ÏLNœË˜\[™

]™ÊJBˆ^Ù\^Ù\[ÛŽœ\ÜÂˆYˆ[ŠÊOLÎ˜ÛX[‹˜\[™
ÊBˆYˆ›ÝÛX[Žœ™]\›ˆ™\ÜÛœÙJ“›È˜[YX[X[›ÛÙˆÝ][™H‹Ý]\ÏM
Bˆ[ÏVÜ›Üˆ[™H[ˆÛX[ˆ›Üˆ[ˆ[™WBˆYˆY\˜×ÞJ]™ÊN‚ˆ][X^
NKŒLLLŽÎZ[ŠKŒLLLŽÎ]
JBˆJ™ÊÌNŒ
KÌÍŒŒˆÚ[žO[X]œÚ[ŠX]œ˜YX[œÊ]
JBˆOLK[X]›ÙÊ
JÜÚ[žJKÊK\Ú[žJJKÊ
›X]œJBˆ™]\›ˆBˆOVÛY\˜×ÞJ]™ÊH›Üˆ]™È[ˆ[×BˆÏVÜVÌH›ÜˆH[ˆWNÞ\ÏVÜVÌWH›ÜˆH[ˆWBˆZ[‹X^[Z[ŠÊKX^
ÊNÞ[Z[‹[X^[Z[Š\ÊKX^
\ÊBˆ[X^
X^^Z[‹YKNJNÙO[X^
[X^^[Z[‹YKNJBˆš]ÝÏM
ŒMNÙš]ÚMŒ
ŒMBˆž[X]›ÙÊš]ÝËÊM‹Œ
™
KŠNÞžO[X]›ÙÊš]ÚÊM‹Œ
™JKŠBˆ›ÛÛO[X^
NKZ[ŠŒK[
X]™›ÛÜŠZ[ŠžžJJJJJBˆÞJZ[ŠÞX^
KÌ‹ŒØÞOJ[Z[ŠÞ[X^
KÌ‹ŒˆÙ[\—Û™ÏXÞ
ŒÍŒŒLNŒˆ[X]œKL‹Œ
›X]œJ˜ÞBˆÙ[\—Û][X]™YÜ™Y\ÊX]˜][ŠX]œÚ[š
ŠJJBˆ\˜[\ÏVÊœÚ^™H‹ŒŠK
œØØ[H‹ŒˆŠK
˜Ù[\ˆ‹ˆžØÙ[\—Û]‹ÙŸKØÙ[\—Û™Î‹ÙŸHŠK
ž›ÛÛH‹ÝŠ›ÛÛJJK
›X\\H‹œØ][]HŠK
™›Ü›X]‹œ™ÈŠWBˆ›ÜˆÈ[ˆÛX[Ž‚ˆ]H˜ÛÛÜŽŒMÍÌ™™ŸÙZYÚš[ÛÛÜŽŒNYLŒŒŸŠÈŸ‹š›Ú[ŠˆžÛ]‹ÙŸKÛ™Î‹ÙŸHˆ›Üˆ]™È[ˆÊÖÜÖÌWJBˆ\˜[\Ë˜\[™

œ]‹]
JBˆ\˜[\Ë˜\[™

šÙ^H‹Ù\ÜÖÈšÙ^H—JJBˆ\›HšÎ‹ËÛX\Ë™ÛÛÙÛX\\Ë˜ÛÛKÛX\ËØ\KÜÝ]XÛX\ÈŠÝ\›X‹œ\œÙK\›[˜ÛÙJ\˜[\ÊBˆXY\œÏ^È•\Ù\‹PYÙ[Žˆ”Ú[™ÛQÝX\™›ÛÙ\ÜÙ\ÜÛY[Ì‹Œ‹”™Y™\™\ˆŽœ™\]Y\ÝšÜÝÝ\›“ÜšYÚ[ˆŽœ™\]Y\ÝšÜÝÝ\›œœÝš\
‹ÈŠ_Bˆ™\O]\›X‹œ™\]Y\Ý”™\]Y\Ý
\›XY\œÏZXY\œÊBˆžN‚ˆÚ]\›X‹œ™\]Y\Ý\›Ü[Š™\K[Y[Ý]LMJH\ÈœŽ˜Ý\œ‹šXY\œË™Ù]
ÛÛ[U\H‹š[XYÙKÜ™ÈŠNØ›ÙO\œ‹œ™XY

Bˆ^Ù\\›X‹™\œ›Ü‹’\œ›Üˆ\ÈN‚ˆ˜]ÏZKœ™XY

K™XÛÙJ]‹N‹œ™\XÙHŠVÎŒLŒKœ™\XÙJÙ\ÜË™Ù]
šÙ^HŠHÜˆˆ‹–ÐTHÑVH‘QPÕQHŠBˆ˜Z\ÙH˜[YQ\œ›ÜŠˆ‘ÛÛÙÛHX\ÈÝ]XÈÚK˜ÛÙ_NˆÜ˜]ßHŠBˆ™]\›ˆ™\ÜÛœÙJ›ÙKÛÛ[Ý\OXÝXY\œÏ^È–PY\šT][ÝKSX\UšY]ÈŽšœÛÛ‹™[\ÊÈ›]]YHŽœ›Ý[™
Ù[\—Û]ÊK›Û™Ú]YHŽœ›Ý[™
Ù[\—Û™ËÊKž›ÛÛHŽž›ÛÛKÚYŽšZYÚŽŒJ_JBˆ^Ù\^Ù\[Ûˆ\ÈN‚ˆ™]\›ˆ™\ÜÛœÙJÝŠJKœ™\XÙJÙ\ÜË™Ù]
šÙ^HŠHÜˆˆ‹–ÐTHÑVH‘QPÕQHŠKÝ]\ÏMÛÛ[Ý\OH^ÜZ[ŽÈÚ\œÙ]]]‹NŠB‚‚‚\œÜÝ
‹ÜØ]™YY\Ý[X]K\™\Ü[X\ŠB™YˆØ]™YÙ\Ý[X]WÜ™\ÜÛX\

N‚ˆˆˆ”™XZ[HØ]™Y\Ý[X]HY\šX[œ›ÛH]Èœ›Þ™[ˆ›ÛÙˆÙ[ÛY]žHÚ]Ý]H]™HYX\Ý\™[Y[Ù\ÜÚ[Û‹ˆˆˆ‚ˆÙ^OQÓÓÑÓWÓPT×ÐTWÒÑVBˆYˆ›ÝÙ^Nœ™]\›ˆ™\ÜÛœÙJ‘ÛÛÙÛHX\ÈTHÙ^H\È›ÝÛÛ™šYÝ\™Y‹Ý]\ÏML
BˆžN‚ˆ]O\™\]Y\Ý™Ù]ÚœÛÛŠÚ[[UYJHÜˆßNÚ[˜ÛÛZ[™ÏY]K™Ù]
œ›ÛÙœÈŠHÜˆ×NÜ›ÛÙœÏV×Bˆ›Üˆ›ÛÙˆ[ˆ[˜ÛÛZ[™Î‚ˆÚ[™\ÝŠ
›ÛÙˆÜˆßJK™Ù]
šÚ[™ŠHÜˆšÝ\ÙHŠNÜÏV×Bˆ›Üˆˆ[ˆ

›ÛÙˆÜˆßJK™Ù]
œÚ[ÈŠHÜˆ×JN‚ˆžN‚ˆ]Y›Ø]
‹™Ù]
›]ŠJNÛ™ÏY›Ø]
‹™Ù]
›™ÈŠJBˆYˆNL[]NL[™LN[™ÏLNœË˜\[™

]™ÊJBˆ^Ù\^Ù\[ÛŽœ\ÜÂˆYˆ[ŠÊOJˆYˆÚ[™OH›[™X\ˆˆ[ÙHÊNœ›ÛÙœË˜\[™

Ú[™ÊJBˆYˆ›Ý›ÛÙœÎœ™]\›ˆ™\ÜÛœÙJ“›È˜[YØ]™Y›ÛÙˆÝ][™H‹Ý]\ÏM
Bˆ[ÏVÜ›ÜˆËÈ[ˆ›ÛÙœÈ›Üˆ[ˆ×BˆYˆY\˜×ÞJ]™ÊN‚ˆ][X^
NKŒLLLŽÎZ[ŠKŒLLLŽÎ]
JNÞJ™ÊÌNŒ
KÌÍŒŒÜÚ[žO[X]œÚ[ŠX]œ˜YX[œÊ]
JNÞOLK[X]›ÙÊ
JÜÚ[žJKÊK\Ú[žJJKÊ
›X]œJNÜ™]\›ˆBˆOVÛY\˜×ÞJ]™ÊH›Üˆ]™È[ˆ[×NÞÏVÜVÌH›ÜˆH[ˆWNÞ\ÏVÜVÌWH›ÜˆH[ˆWBˆZ[‹X^[Z[ŠÊKX^
ÊNÞ[Z[‹[X^[Z[Š\ÊKX^
\ÊNÙ[X^
X^^Z[‹YKNJNÙO[X^
[X^^[Z[‹YKNJBˆž[X]›ÙÊ

‹N
KÊM‹Œ
™
KŠNÞžO[X]›ÙÊ
Œ
‹N
KÊM‹Œ
™JKŠNÞ›ÛÛO[X^
HYˆ[žJÚ[™[ˆ
˜\™XH‹›[™X\ˆŠH›ÜˆÚ[™È[ˆ›ÛÙœÊH[ÙHNZ[ŠŒK[
X]™›ÛÜŠZ[ŠžžJJJJJBˆÞJZ[ŠÞX^
KÌ‹ŒØÞOJ[Z[ŠÞ[X^
KÌ‹ŒØÙ[\—Û™ÏXÞ
ŒÍŒŒLNŒÛ[X]œKL‹Œ
›X]œJ˜ÞNØÙ[\—Û][X]™YÜ™Y\ÊX]˜][ŠX]œÚ[š
ŠJJBˆ\˜[\ÏVÊœÚ^™H‹ŒŠK
œØØ[H‹ŒˆŠK
˜Ù[\ˆ‹ˆžØÙ[\—Û]‹ÙŸKØÙ[\—Û™Î‹ÙŸHŠK
ž›ÛÛH‹ÝŠ›ÛÛJJK
›X\\H‹œØ][]HŠK
™›Ü›X]‹œ™ÈŠWBˆ›ÜˆÚ[™È[ˆ›ÛÙœÎ‚ˆYˆÚ[™OH™Ø\˜YÙHŽ˜ÛÛÜ‹š[HŒNMØL™ˆ‹ŒNMØLN‚ˆ[YˆÚ[™OH›X[X[Ž˜ÛÛÜ‹š[HŒMÍÌ™™ˆ‹ŒNYLŒŒ‚ˆ[YˆÚ[™OH˜\™XHŽ˜ÛÛÜ‹š[HŒÌÍMØŽ™ˆ‹ŒÌÍMØŽŒ‚ˆ[YˆÚ[™OH›[™X\ˆŽ˜ÛÛÜ‹š[HŒŽŽÙ™ˆ‹Œ‚ˆ[ÙN˜ÛÛÜ‹š[HŒ™˜Ù™™ˆ‹Œ™˜ÙŒMˆ‚ˆÛÜÙY\ÈYˆÚ[™OH›[™X\ˆˆ[ÙHÊÖÜÖÌWNÜ\˜[\Ë˜\[™

œ]‹ˆ˜ÛÛÜŽžØÛÛÜŸ_ÙZYÚš[ÛÛÜŽžÙš[_ŠÈŸ‹š›Ú[ŠˆžØN‹ÙŸKØŽ‹ÙŸHˆ›ÜˆKˆ[ˆÛÜÙY
JJBˆ\˜[\Ë˜\[™

šÙ^H‹Ù^JJNÝ\›HšÎ‹ËÛX\Ë™ÛÛÙÛX\\Ë˜ÛÛKÛX\ËØ\KÜÝ]XÛX\ÈŠÝ\›X‹œ\œÙK\›[˜ÛÙJ\˜[\ÊBˆXY\œÏ^È•\Ù\‹PYÙ[Žˆ”Ú[™ÛQÝX\™›ÛÙ\ÜÙ\ÜÛY[Ì‹Œ‹”™Y™\™\ˆŽœ™\]Y\ÝšÜÝÝ\›“ÜšYÚ[ˆŽœ™\]Y\ÝšÜÝÝ\›œœÝš\
‹ÈŠ_NÜ™\O]\›X‹œ™\]Y\Ý”™\]Y\Ý
\›XY\œÏZXY\œÊBˆžN‚ˆÚ]\›X‹œ™\]Y\Ý\›Ü[Š™\K[Y[Ý]LMJH\ÈœŽ˜Ý\œ‹šXY\œË™Ù]
ÛÛ[U\H‹š[XYÙKÜ™ÈŠNØ›ÙO\œ‹œ™XY

Bˆ^Ù\\›X‹™\œ›Ü‹’\œ›Üˆ\ÈN‚ˆ˜]ÏZKœ™XY

K™XÛÙJ]‹N‹œ™\XÙHŠVÎŒLŒKœ™\XÙJÙ^K–ÐTHÑVH‘QPÕQHŠNÜ˜Z\ÙH˜[YQ\œ›ÜŠˆ‘ÛÛÙÛHX\ÈÝ]XÈÚK˜ÛÙ_NˆÜ˜]ßHŠBˆ™]\›ˆ™\ÜÛœÙJ›ÙKÛÛ[Ý\OXÝXY\œÏ^È–PY\šT][ÝKSX\UšY]ÈŽšœÛÛ‹™[\ÊÈ›]]YHŽœ›Ý[™
Ù[\—Û]ÊK›Û™Ú]YHŽœ›Ý[™
Ù[\—Û™ËÊKž›ÛÛHŽž›ÛÛKÚYŽšZYÚŽŒJ_JBˆ^Ù\^Ù\[Ûˆ\ÈNœ™]\›ˆ™\ÜÛœÙJÝŠJKœ™\XÙJÙ^K–ÐTHÑVH‘QPÕQHŠKÝ]\ÏMÛÛ[Ý\OH^ÜZ[ŽÈÚ\œÙ]]]‹NŠB‚‚\œÜÝ
‹Ù^XÝ\[‹\™\Ü[X\ÏÚÙ[ˆŠB™Yˆ^XÝÜ[—Ü™\ÜÛX\
ÚÙ[ŠN‚ˆˆˆ‘^XÝ\[ˆÝ\ÝÛY\ˆ\Ý[X]NˆÝX›HÛÛÙÛHØ][]H[XYÙH
ÈØ]™Y›ÛÙˆÝ][™\È˜ZÙYÙÙ]\‹ˆˆˆ‚ˆÙ\ÜÏTÑTÔÒSÓ”Ë™Ù]
ÚÙ[ŠBˆYˆ›ÝÙ\ÜÎœ™]\›ˆ™\ÜÛœÙJ”Ù\ÜÚ[Ûˆ^\™Y‹Ý]\ÏM
BˆžN‚ˆ]O\™\]Y\Ý™Ù]ÚœÛÛŠÚ[[UYJHÜˆßBˆ[˜ÛÛZ[™ÏY]K™Ù]
œ›ÛÙœÈŠHÜˆ×Bˆ›ÛÙœÏV×Bˆ›Üˆ›ÛÙˆ[ˆ[˜ÛÛZ[™Î‚ˆÚ[™\ÝŠ
›ÛÙˆÜˆßJK™Ù]
šÚ[™ŠHÜˆšÝ\ÙHŠBˆÏV×Bˆ›Üˆˆ[ˆ

›ÛÙˆÜˆßJK™Ù]
œÚ[ÈŠHÜˆ×JN‚ˆžN‚ˆ]Y›Ø]
‹™Ù]
›]ŠJNÛ™ÏY›Ø]
‹™Ù]
›™ÈŠJBˆYˆNL[]NL[™LN[™ÏLNœË˜\[™

]™ÊJBˆ^Ù\^Ù\[ÛŽ‚ˆ\ÜÂˆYˆ[ŠÊOLÎœ›ÛÙœË˜\[™

Ú[™ÊJBˆYˆ›Ý›ÛÙœÎœ™]\›ˆ™\ÜÛœÙJ“›È˜[Y^XÝ\[ˆ›ÛÙˆÝ][™H‹Ý]\ÏM
B‚ˆÈ\ÙHH^XÝØ[YHÙ[\‹Þ›ÛÛH]\ÜÙYÛˆHX[\ˆØÜ™Y[‹‚ˆ]Y›Ø]
Ù\ÜË™Ù]
™\Ü^WÛ]‹Ù\ÜË™Ù]
›]ŠJJBˆ™ÏY›Ø]
Ù\ÜË™Ù]
™\Ü^WÛ™È‹Ù\ÜË™Ù]
›™ÈŠJJBˆ›ÛÛOZ[
Ù\ÜË™Ù]
™\Ü^WÞ›ÛÛH‹NJJB‚ˆ\˜[\ÏVÂˆ
œÚ^™H‹ŒŠKˆ
œØØ[H‹ŒˆŠKˆ
˜Ù[\ˆ‹ˆžÛ]‹ÙŸKÛ™Î‹ÙŸHŠKˆ
ž›ÛÛH‹ÝŠ›ÛÛJJKˆ
›X\\H‹œØ][]HŠKˆ
™›Ü›X]‹œ™ÈŠKˆB‚ˆ›ÜˆÚ[™È[ˆ›ÛÙœÎ‚ˆYˆÚ[™OH™Ø\˜YÙHŽ‚ˆÛÛÜHŒNMØL™ˆŽÙš[HŒNMØLN‚ˆ[YˆÚ[™OH›X[X[Ž‚ˆÛÛÜHŒMÍÌ™™ˆŽÙš[HŒNYLŒŒ‚ˆ[ÙN‚ˆÛÛÜHŒ™˜Ù™™ˆŽÙš[HŒ™˜ÙŒMˆ‚ˆÛÜÙY\ÊÖÜÖÌWBˆ]Yˆ˜ÛÛÜŽžØÛÛÜŸ_ÙZYÚš[ÛÛÜŽžÙš[_ŠÈŸ‹š›Ú[ŠˆžØN‹ÙŸKØŽ‹ÙŸHˆ›ÜˆKˆ[ˆÛÜÙY
Bˆ\˜[\Ë˜\[™

œ]‹]
JB‚ˆ\˜[\Ë˜\[™

šÙ^H‹Ù\ÜÖÈšÙ^H—JJBˆ\›HšÎ‹ËÛX\Ë™ÛÛÙÛX\\Ë˜ÛÛKÛX\ËØ\KÜÝ]XÛX\ÈŠÝ\›X‹œ\œÙK\›[˜ÛÙJ\˜[\ÊBˆXY\œÏ^È•\Ù\‹PYÙ[Žˆ”Ú[™ÛQÝX\™›ÛÙ\ÜÙ\ÜÛY[Ì‹Œ‹”™Y™\™\ˆŽœ™\]Y\ÝšÜÝÝ\›“ÜšYÚ[ˆŽœ™\]Y\ÝšÜÝÝ\›œœÝš\
‹ÈŠ_Bˆ™\O]\›X‹œ™\]Y\Ý”™\]Y\Ý
\›XY\œÏZXY\œÊBˆžN‚ˆÚ]\›X‹œ™\]Y\Ý\›Ü[Š™\K[Y[Ý]LMJH\ÈœŽ‚ˆÝ\œ‹šXY\œË™Ù]
ÛÛ[U\H‹š[XYÙKÜ™ÈŠBˆ›ÙO\œ‹œ™XY

Bˆ^Ù\\›X‹™\œ›Ü‹’\œ›Üˆ\ÈN‚ˆ˜]ÏZKœ™XY

K™XÛÙJ]‹N‹œ™\XÙHŠVÎŒLŒKœ™\XÙJÙ\ÜË™Ù]
šÙ^HŠHÜˆˆ‹–ÐTHÑVH‘QPÕQHŠBˆ˜Z\ÙH˜[YQ\œ›ÜŠˆ‘ÛÛÙÛHX\ÈÝ]XÈÚK˜ÛÙ_NˆÜ˜]ßHŠBˆ™]\›ˆ™\ÜÛœÙJ›ÙKÛÛ[Ý\OXÝ
Bˆ^Ù\^Ù\[Ûˆ\ÈN‚ˆ™]\›ˆ™\ÜÛœÙJÝŠJKœ™\XÙJÙ\ÜË™Ù]
šÙ^HŠHÜˆˆ‹–ÐTHÑVH‘QPÕQHŠKÝ]\ÏMÛÛ[Ý\OH^ÜZ[ŽÈÚ\œÙ]]]‹NŠB‚‚\™Ù]
‹Ø\KÙ\Ý[X]K\ÝÜ˜YÙK\Ý]\ÈŠB™Yˆ\Ý[X]WÜÝÜ˜YÙWÜÝ]\Ê
N‚ˆX[\—ÚY\ÝŠÙ\ÜÚ[Û‹™Ù]
™X[\—ÚYŠHÜˆˆŠBˆÛÛY\Ý[X]WÙŠ
BˆžN‚ˆ\Ý[X]WØÛÝ[XÛÛ‹™^XÝ]J”ÑSPÕÓÕS•

ŠHTÈÝ[”“ÓH\Ý[X]\ÈÒT‘HX[\—ÚYOÈ‹
X[\—ÚY
JK™™]ÚÛ™J
VÈÝ[—Bˆ™]š\Ú[Û—ØÛÝ[XÛÛ‹™^XÝ]J”ÑSPÕÓÕS•

ŠHTÈÝ[”“ÓH\Ý[X]WÜ™]š\Ú[ÛœÈÒT‘HX[\—ÚYOÈ‹
X[\—ÚY
JK™™]ÚÛ™J
VÈÝ[—Bˆš[˜[N‚ˆÛÛ‹˜ÛÜÙJ
Bˆ™]\›ˆœÛÛšYžJˆ\œÚ\Ý[X›ÛÛ
UPTÑWÕT“
Kˆ\Ý[X]WØÛÝ[Y\Ý[X]WØÛÝ[ˆ™]š\Ú[Û—ØÛÝ[\™]š\Ú[Û—ØÛÝ[ˆ
B‚™œ›ÛHYX\Ý\™[Y[Ú[YÜš]H[\ÜÛ˜\ÚÝÙ\œ›Ü‚™œ›ÛHšXÚ[™×Ú[YÜš]H[\ÜšXÚ[™×Ù\œ›Ü‚‚™Yˆ\Ý[X]WÜšXÚ[™×Ù\œ›ÜŠ^[ØY
N‚ˆYˆ›Ý\Ú[œÝ[˜ÙJ^[ØYXÝ
Nœ™]\›ˆ‘\Ý[X]H]Z[È]\Ý™H[ˆØš™XÝˆ‚ˆYˆ˜[Y
˜[YKX^[][OY›Ø]
š[™ˆŠJN‚ˆžNœ™]\›ˆ˜[YH\È›Ý›Û™H[™›Ý\Ú[œÝ[˜ÙJ˜[YK›ÛÛ
H[™ÝŠ˜[YJKœÝš\

HOHˆˆ[™X]š\Ùš[š]J›Ø]
˜[YJJH[™Y›Ø]
˜[YJO[X^[][Bˆ^Ù\
\Q\œ›Ü‹˜[YQ\œ›Ü‹Ý™\™›ÝÑ\œ›ÜŠNœ™]\›ˆ˜[ÙBˆ›ÜˆÙ^H[ˆ
Ý[ÜšXÙH‹Ý[Ø\™XH‹™^˜WÜÙ\šXÙWØ[[Ý[‹›[™X\—Ù™Y]‹˜\™XWÜÜY‹˜[[Ý[ÜZYŠN‚ˆYˆÙ^H[ˆ^[ØY[™›Ý˜[Y
^[ØYÚÙ^WJNœ™]\›ˆ‘[\ˆ˜[Y›Û‹[™YØ]]™H\Ý[X]H[[Ý[È[™]X[]Y\Ëˆ‚ˆšXÚ[™Ï\^[ØY™Ù]
œšXÚ[™È‹ßJBˆYˆ›Ý\Ú[œÝ[˜ÙJšXÚ[™ËXÝ
Nœ™]\›ˆ”šXÚ[™È]Z[È]\Ý™H[ˆØš™XÝˆ‚ˆ›ÜˆÙ^H[ˆ
œÝXÝ[‹œšXÙH‹™^˜P[[Ý[‹^˜\ÙH‹™ÜÝ[]‹œÝ[]‹Ý[ŠN‚ˆYˆÙ^H[ˆšXÚ[™È[™›Ý˜[Y
šXÚ[™ÖÚÙ^WJNœ™]\›ˆ‘[\ˆ˜[Y›Û‹[™YØ]]™HšXÙ\È[™^\Ëˆ‚ˆ›ÜˆÙ^H[ˆ
™ÜÝ‹œÝŠN‚ˆYˆÙ^H[ˆšXÚ[™È[™›Ý˜[Y
šXÚ[™ÖÚÙ^WKL
Nœ™]\›ˆ•^\˜Ù[YÙ\È]\Ý™Hœ›ÛHÈLˆ‚ˆYˆšXÚ[™Ë™Ù]
›[ÙHŠOOH™\ØÛÝ[ˆ[™›Ý˜[Y
šXÚ[™Ë™Ù]
™\ØÈŠKL
Nœ™]\›ˆ‘\ØÛÝ[]\Ý™Hœ›ÛHÈL	Kˆ‚ˆÈ™Z™XÝ[˜ÛÛœÚ\Ý[ÛY[Û˜\ÚÝÈ™Y›Ü™HÜ™X][™È™]š\Ú[ÛœÈÜˆÛÛœÝ[Z[™ÈÜ™Y]‚ˆYˆÝ[ÜšXÙHˆ[ˆ^[ØY[™Ý[ˆ[ˆšXÚ[™È[™XœÊ›Ø]
^[ØYÈÝ[ÜšXÙH—JKY›Ø]
šXÚ[™ÖÈÝ[—JJOŒŒN‚ˆ™]\›ˆ‘\Ý[X]HÝ[Ù\È›ÝX]Ú]ÈšXÚ[™È]Z[Ëˆ™XÜ™X]HH\Ý[X]Kˆ‚ˆYˆ[
Ù^H[ˆšXÚ[™È›ÜˆÙ^H[ˆ
^˜\ÙH‹™ÜÝ[]‹œÝ[]‹Ý[ŠJN‚ˆYˆXœÊÝ[J›Ø]
šXÚ[™ÖÚÙ^WJH›ÜˆÙ^H[ˆ
^˜\ÙH‹™ÜÝ[]‹œÝ[]ŠJKY›Ø]
šXÚ[™ÖÈÝ[—JJOŒŒN‚ˆ™]\›ˆ‘\Ý[X]HÝ[Ù\È›ÝX]Ú]È^œ™XZÙÝÛ‹ˆ™XÜ™X]HH\Ý[X]Kˆ‚ˆYˆœ][ÝHˆ[ˆ^[ØY‚ˆ][ÝO\^[ØYÈœ][ÝH—BˆYˆ›Ý\Ú[œÝ[˜ÙJ][ÝKXÝ
Nœ™]\›ˆ“YX\Ý\™[Y[Û˜\ÚÝ]\Ý™H[ˆØš™XÝˆ‚ˆ›ÜˆÙ^H[ˆ
›[™X\‘™Y]‹˜\™XTÜQŠN‚ˆYˆÙ^H[ˆ][ÝH[™›Ý˜[Y
][ÝVÚÙ^WJNœ™]\›ˆ‘[\ˆ˜[YYX\Ý\™[Y[]X[]Y\Ëˆ‚ˆ\™X\Ï\][ÝK™Ù]
˜ÛÛ[Y\˜ÚX[\™X\È‹×JBˆYˆ›Ý\Ú[œÝ[˜ÙJ\™X\Ë\Ý
Nœ™]\›ˆ”Ø]™YÙ\šXÙH\™X\È]\Ý™HH\Ýˆ‚ˆ›Üˆ\™XH[ˆ\™X\Î‚ˆYˆ›Ý\Ú[œÝ[˜ÙJ\™XKXÝ
HÜˆ›Ý˜[Y
\™XK™Ù]
œÜYŠJHÜˆ›Ý˜[Y
\™XK™Ù]
œ˜]HŠJN‚ˆ™]\›ˆ‘]™\žHØ]™YÙ\šXÙH\™XH™YYÈH˜[Y]X[]H[™˜]Kˆ‚ˆYˆ›Ø]
\™XVÈœÜY—JOLœ™]\›ˆ‘š[š\ÚØ]š[™ÈÜˆØ[˜Ù[H[™š[š\ÚYÙ\šXÙH\™XH™Y›Ü™HÜ™X][™È[ˆ\Ý[X]Kˆ‚ˆ›ÛÙœÏ\][ÝK™Ù]
œÝXÝ\™\È‹×JBˆYˆ›Ý\Ú[œÝ[˜ÙJ›ÛÙœË\Ý
HÜˆ[žJ›Ý\Ú[œÝ[˜ÙJ›ÛÙ‹XÝ
H›Üˆ›ÛÙˆ[ˆ›ÛÙœÊNœ™]\›ˆ”Ø]™Y›ÛÙœÈ]\Ý™HH\Ýˆ‚ˆYˆ[žJ›ÛÙ‹™Ù]
›™YY×Ü™[YX\Ý\™HŠHÜˆ›ÛÙ‹™Ù]
˜]]ÛX]X×Ü™]šY]×ÝØ\›š[™ÈŠH›Üˆ›ÛÙˆ[ˆ›ÛÙœÊN‚ˆ™]\›ˆ”™[YX\Ý\™HH›YÙÙY›ÛÙˆ™Y›Ü™HØ]š[™È[ˆ\Ý[X]Kˆ‚ˆ™]\›ˆÛ˜\ÚÝÙ\œ›ÜŠ^[ØY
HÜˆšXÚ[™×Ù\œ›ÜŠ^[ØY
B‚™Yˆ\Ý[X]WÝ™\œÚ[ÛŠ^[ØY
N‚ˆYˆ\Ú[œÝ[˜ÙJ^[ØYÝŠNœ^[ØYZœÛÛ‹›ØYÊ^[ØY
Bˆ™]\›ˆ\ÚX‹œÚLMŠœÛÛ‹™[\Ê^[ØYÛÜÚÙ^\ÏUYKÙ\\˜]ÜœÏJ‹‹ŽˆŠK[Ý×Û˜[Q˜[ÙJK™[˜ÛÙJ
JKš^YÙ\Ý

B‚™Yˆ˜YÚY[]J
N‚ˆ[\ÜÛÜšÜÜXÙWÙ˜YÈ\È˜YÂˆX[\\ÝŠÙ\ÜÚ[Û‹™Ù]
™X[\—ÚYŠHÜˆˆŠBˆ\Ù\Y˜YËœš[˜Ú\[
Ù\ÜÚ[ÛŠBˆYˆ™\]Y\ÝšXY\œË™Ù]
–PY\šT][ÝKTš[˜Ú\[ŠHOH\Ù\Ž‚ˆ˜Z\ÙH˜YË‘˜Y\œ›ÜŠ”ÚYÛˆ[ˆÈHÜšYÚ[˜[\Ù\ˆXØÛÝ[™Y›Ü™H™XÛÝ™\š[™È\ÈÛÜšÜÜXÙKˆ‹JBˆÜšYÚ[\™\]Y\ÝšXY\œË™Ù]
“ÜšYÚ[ˆ‹ˆŠK›ÝÙ\Š
BˆYˆ™\]Y\ÝšXY\œË™Ù]
”ÙXËQ™]ÚTÚ]H‹ˆŠOOH˜Ü›ÜÜË\Ú]HˆÜˆ
ÜšYÚ[ˆ[™ÜšYÚ[ˆ›Ý[ˆÈšÎ‹ËÈŠÜ™\]Y\ÝšÜÝ›ÝÙ\Š
Kš‹ËÈŠÜ™\]Y\ÝšÜÝ›ÝÙ\Š
_JN‚ˆ˜Z\ÙH˜YË‘˜Y\œ›ÜŠ”™XÛÝ™\žH™\]Y\ÝÈ]\ÝÛÛYHœ›ÛH\ÈY\šT][ÝHYÙKˆ‹ÊBˆ™]\›ˆX[\‹\Ù\‚‚\œ›Ý]J‹Ø\KÝÛÜšÜÜXÙKY˜YÈ‹Y]ÙÏVÈ‘ÑU—JB\œ›Ý]J‹Ø\KÝÛÜšÜÜXÙKY˜YËÏ˜YÚYˆ‹Y]ÙÏVÈ‘ÑU‹”U‹‘SUH—JB™YˆÛÜšÜÜXÙWÙ˜YØ\J˜YÚYS›Û™JN‚ˆ[\ÜÛÜšÜÜXÙWÙ˜YÈ\È˜YÂˆÛÛY\Ý[X]WÙŠ
BˆžN‚ˆX[\‹\Ù\Y˜YÚY[]J
BˆØÚ×ØXØÛÝ[
ÛÛ‹X[\ŠBˆ˜YËœ\™ÙJÛÛŠBˆYˆ˜YÚY\È›Û™N‚ˆ›ÝÜÏXÛÛ‹™^XÝ]J”ÑSPÕ˜YÚY™\œÚ[Û‹^\™\×Ø]”“ÓHÛÜšÜÜXÙWÙ˜YÈÒT‘HX[\—ÚYOÈS‘š[˜Ú\[OÈS‘ÛÜÙYLÔ‘Tˆ–H^\™\×Ø]TÐÈ‹
X[\‹\Ù\ŠJK™™]Ú[

BˆÛÛ‹˜ÛÛ[Z]

Bˆ™]\›ˆœÛÛšYžJ˜YÏVÙXÝ
ŠH›Üˆˆ[ˆ›ÝÜ×JBˆYˆ™\]Y\Ý›Y]ÙOH‘SUHŽ‚ˆÛX[\\™\]Y\Ý™Ù]ÚœÛÛŠÚ[[UYJHÜˆßBˆYˆ›Ý\Ú[œÝ[˜ÙJÛX[\XÝ
Nœ™]\›ˆœÛÛšYžJ\œ›ÜH”™XÛÝ™\žHÛX[\]\Ý™H[ˆØš™XÝˆŠKˆ[]YY˜YË˜ÛÜÙJÛÛ‹X[\‹\Ù\‹˜YÚY^XÝYÝ™\œÚ[ÛXÛX[\™Ù]
™\œÚ[ÛˆŠJBˆÛÛ‹˜ÛÛ[Z]

NÜ™]\›ˆœÛÛšYžJ[]YY[]Y
BˆYˆ™\]Y\Ý›Y]ÙOH‘ÑUŽ‚ˆ›ÝÏY˜YË›ØY
ÛÛ‹X[\‹\Ù\‹˜YÚY
BˆÛÛ‹˜ÛÛ[Z]

Bˆ™]\›ˆœÛÛšYžJ˜YÚYY˜YÚY™\œÚ[Û\›ÝÖÈ™\œÚ[Ûˆ—K^\™\×Ø]\›ÝÖÈ™^\™\×Ø]—KÛÜšÜÜXÙOZœÛÛ‹›ØYÊ›ÝÖÈœ^[ØY—JJBˆ›ÙO\™\]Y\Ý™Ù]ÚœÛÛŠÚ[[UYJBˆYˆ›Ý\Ú[œÝ[˜ÙJ›ÙKXÝ
Nœ™]\›ˆœÛÛšYžJ\œ›ÜH”™XÛÝ™\žHÛÜšÜÜXÙH]\Ý™H[ˆØš™XÝˆŠKˆÈÛ›HY]Y]Hœ›ÛHH™]š[Ý\ÛHXØÙ\YÝÛ™Y[XYÙ\žHÙ\ÜÚ[Ûˆ\È™]Z[™Y‚ˆÚÙ[X›ÙK™Ù]
ÛÜšÜÜXÙH‹ßJK™Ù]
œÙ\ÜÚ[Û•ÚÙ[ˆŠHYˆ\Ú[œÝ[˜ÙJ›ÙK™Ù]
ÛÜšÜÜXÙHŠKXÝ
H[ÙH›Û™BˆÛÝ\˜ÙOTÑTÔÒSÓ”Ë™Ù]
ÚÙ[ŠHYˆ\Ú[œÝ[˜ÙJÚÙ[‹ÝŠH[ÙH›Û™BˆY]Y]OS›Û™BˆYˆÛÝ\˜ÙN‚ˆœ›ÛH›Ü\WÜÙ\ÜÚ[ÛœÈ[\Ü’QSË[XYÙWÝ\›ˆY]Y]O^ÚÎœÛÝ\˜ÙVÚ×H›ÜˆÈ[ˆ’QSÈYˆÈ[ˆÛÝ\˜Ù_Bˆ›ÜˆÈ[ˆ
œ™Øˆ‹›X\ÚÈ‹œÝ™Y]ŠN‚ˆYˆÈ[ˆY]Y]N›Y]Y]VÚ×OZ[XYÙWÝ\›
Y]Y]VÚ×JBˆ™\Ý[Y˜YËœ]
ÛÛ‹X[\‹\Ù\‹˜YÚY›ÙK™Ù]
™\œÚ[ÛˆŠK›ÙK™Ù]
ÛÜšÜÜXÙHŠKY]Y]JBˆÛÛ‹˜ÛÛ[Z]

NÜ™]\›ˆœÛÛšYžJ™\Ý[
Bˆ^Ù\˜YË‘˜Y\œ›Üˆ\ÈN‚ˆ™]\›ˆœÛÛšYžJ\œ›Ü\ÝŠJKÛÙOYK˜ÛÙJKKœÝ]\Âˆš[˜[N˜ÛÛ‹˜ÛÜÙJ
B‚\œÜÝ
‹Ø\KÝÛÜšÜÜXÙKY˜YËÏ˜YÚY‹ÜØ]™K\Ý]\ÈŠB™YˆÛÜšÜÜXÙWÙ˜YÜØ]™WÜÝ]\Ê˜YÚY
N‚ˆ[\ÜÛÜšÜÜXÙWÙ˜YÈ\È˜YÂˆÛÛY\Ý[X]WÙŠ
BˆžN‚ˆX[\‹\Ù\Y˜YÚY[]J
NÙ˜YË˜[Y]WÚY
˜YÚY
BˆÜ\˜][ÛJ™\]Y\Ý™Ù]ÚœÛÛŠÚ[[UYJHÜˆßJK™Ù]
›Ü\˜][Û—ÚYŠBˆ›ÝÏXÛÛ‹™^XÝ]J”ÑSPÕØ]™WÛÜ\˜][Ûˆ”“ÓHÛÜšÜÜXÙWÙ˜YÈÒT‘HX[\—ÚYOÈS‘š[˜Ú\[OÈS‘˜YÚYOÈS‘^\™\×Ø]ÈS‘ÛÜÙYLH‹
X[\‹\Ù\‹˜YÚY[YK[YJ
JJK™™]ÚÛ™J
BˆYˆ›Ý›ÝÈÜˆ›ÝÜ\˜][ÛˆÜˆ›ÝÖÈœØ]™WÛÜ\˜][Ûˆ—HO[Ü\˜][ÛŽœ™]\›ˆœÛÛšYžJØ]™YQ˜[ÙJBˆ™XÙZ\XÛÛ‹™^XÝ]J”ÑSPÕ™\ÜÛœÙWÚœÛÛˆ”“ÓH\Ý[X]WÜØ]™WÜ™XÙZ\ÈÒT‘HX[\—ÚYOÈS‘Ü\˜][Û—ÚYOÈ‹
X[\‹Ü\˜][ÛŠJK™™]ÚÛ™J
Bˆ™]\›ˆœÛÛšYžJØ]™YX›ÛÛ
™XÙZ\
K™\Ý[ZœÛÛ‹›ØYÊ™XÙZ\Èœ™\ÜÛœÙWÚœÛÛˆ—JHYˆ™XÙZ\[ÙH›Û™JBˆ^Ù\˜YË‘˜Y\œ›Üˆ\ÈNœ™]\›ˆœÛÛšYžJ\œ›Ü\ÝŠJJKKœÝ]\Âˆš[˜[N˜ÛÛ‹˜ÛÜÙJ
B‚\œÜÝ
‹Ø\KÝÛÜšÜÜXÙKY˜YËÏ˜YÚY‹Ú[XYÙ\žK\Ù\ÜÚ[ÛˆŠB™YˆÛÜšÜÜXÙWÙ˜YÚ[XYÙ\žJ˜YÚY
N‚ˆ[\ÜÛÜšÜÜXÙWÙ˜YÈ\È˜YÂˆÛÛY\Ý[X]WÙŠ
BˆžN‚ˆX[\‹\Ù\Y˜YÚY[]J
Bˆ›ÝÏY˜YË›ØY
ÛÛ‹X[\‹\Ù\‹˜YÚY
BˆY]Y]OZœÛÛ‹›ØYÊ›ÝÖÈœ›Ü\WÛY]Y]H—HÜˆ›[ŠBˆYˆ›ÝY]Y]Nœ™]\›ˆœÛÛšYžJ\œ›ÜH”›Ü\H[XYÙ\žHØ\È›ÝXÚÛ›ÝÛYÙY™Y›Ü™H[\œ\[Û‹ˆ[Ý\ˆYX\Ý\™[Y[È\™H™]Z[™YÈ™]žHHÜšYÚ[˜[›Ü\HØY[™ÈÝ\ˆŠKBˆYˆ›ÝÓÓÑÓWÓPT×ÐTWÒÑVNœ™]\›ˆœÛÛšYžJ\œ›ÜH’[XYÙ\žH\È[˜]˜Z[X›Kˆ[Ý\ˆ˜Y™[XZ[œÈ]˜Z[X›NÈ™]žH]\‹ˆŠKLÂˆÚÙ[]]ZY]ZY

Kš^ˆY]Y]K\]JÙ^OQÓÓÑÓWÓPT×ÐTWÒÑVKÜ™X]Y][YK[YJ
KX[\—ÚYYX[\ŠBˆœ›ÛH›Ü\WÜÙ\ÜÚ[ÛœÈ[\ÜÐPÒTË[XYÙWÝ\›ˆY]Y]K\]JÚÎ“›Û™H›ÜˆÈ[ˆÐPÒTßJBˆYˆY]Y]K™Ù]
œÝ™Y]ŠN›Y]Y]VÈœÝ™Y]—OZ[XYÙWÝ\›
Y]Y]VÈœÝ™Y]—KÓÓÑÓWÓPT×ÐTWÒÑVJBˆY]Y]VÈœÝXÝ\™WÛX\ÚÜÈ—O^ßBˆÑTÔÒSÓ”ÖÝÚÙ[—O[Y]Y]NÔÑTÔÒSÓ”Ëœ\œÚ\Ý
ÚÙ[ŠBˆ™]\›ˆœÛÛšYžJÚÙ[]ÚÙ[‹Ù[\^È›]]YHŽ›Y]Y]VÈ›]—K›Û™Ú]YHŽ›Y]Y]VÈ›™È—_JBˆ^Ù\˜YË‘˜Y\œ›Üˆ\ÈNœ™]\›ˆœÛÛšYžJ\œ›Ü\ÝŠJJKKœÝ]\Âˆš[˜[N˜ÛÛ‹˜ÛÜÙJ
B‚\œ›Ý]J‹Ø\KÙ\Ý[X]\È‹Y]ÙÏVÈ‘ÑU‹”ÔÕ—JB™Yˆ\Ý[X]WÚ\ÝÜžWØ\J
N‚ˆX[\—ÚY\ÝŠÙ\ÜÚ[Û‹™Ù]
™X[\—ÚYŠHÜˆˆŠBˆÛÛY\Ý[X]WÙŠ
BˆžN‚ˆYˆ™\]Y\Ý›Y]ÙOH”ÔÕŽ‚ˆØÚ×ØXØÛÝ[
ÛÛ‹X[\—ÚY
Bˆ™XÛÝ™\žWÚY\™\]Y\ÝšXY\œË™Ù]
–PY\šT][ÝKQ˜YŠBˆYˆ™XÛÝ™\žWÚY‚ˆ[\ÜÛÜšÜÜXÙWÙ˜YÈ\È˜YÂˆžN‚ˆË™XÛÝ™\žWÝ\Ù\Y˜YÚY[]J
NÙ˜YË˜[Y]WÚY
™XÛÝ™\žWÚY
Bˆ^Ù\˜YË‘˜Y\œ›Üˆ\ÈNœ™]\›ˆœÛÛšYžJ\œ›Ü\ÝŠJJKKœÝ]\Âˆ\™\]Y\Ý™Ù]ÚœÛÛŠÚ[[UYJHÜˆßBˆšXÚ[™×Ù\œ›ÜY\Ý[X]WÜšXÚ[™×Ù\œ›ÜŠ
BˆYˆšXÚ[™×Ù\œ›ÜŽœ™]\›ˆœÛÛšYžJ\œ›Ü\šXÚ[™×Ù\œ›ÜŠKˆY™\ÜÏ\ÝŠ™Ù]
˜Y™\ÜÈŠHÜˆˆŠKœÝš\

BˆYˆ›ÝY™\ÜÎœ™]\›ˆœÛÛšYžJ\œ›ÜH”›Ü\HY™\ÜÈ\È™\]Z\™YŠKˆÜ\˜][Û\ÝŠ™\]Y\ÝšXY\œË™Ù]
’Y[\Ý[˜ÞKRÙ^HŠHÜˆˆŠBˆYˆÜ\˜][Ûˆ[™›Ý™K™[X]Ú
ˆ–ÐKV˜K^ŒNWËW^ÌKLŽH‹Ü\˜][ÛŠNœ™]\›ˆœÛÛšYžJ\œ›ÜH’[˜[YØ]™H™\]Y\ÝY[YšY\‹ˆŠKˆžNœ™\]Y\ÝÚ\ÚY\Ý[X]WÝ™\œÚ[ÛŠ
Bˆ^Ù\
˜[YQ\œ›Ü‹\Q\œ›ÜŠNœ™]\›ˆœÛÛšYžJ\œ›ÜH‘\Ý[X]HÛÛZ[œÈ[˜[Y˜[Y\ËˆŠKˆYˆÜ\˜][ÛŽ‚ˆ™XÙZ\XÛÛ‹™^XÝ]J”ÑSPÕ^[ØYÚ\Ú™\ÜÛœÙWÚœÛÛˆ”“ÓH\Ý[X]WÜØ]™WÜ™XÙZ\ÈÒT‘HX[\—ÚYOÈS‘Ü\˜][Û—ÚYOÈ‹
X[\—ÚYÜ\˜][ÛŠJK™™]ÚÛ™J
BˆYˆ™XÙZ\‚ˆYˆ™XÙZ\Èœ^[ØYÚ\Ú—HO\™\]Y\ÝÚ\Úœ™]\›ˆœÛÛšYžJ\œ›ÜH•\ÈØ]™HY[YšY\ˆØ\È[™XYH\ÙY›ÜˆY™™\™[\Ý[X]H]Z[ËˆŠKBˆYˆ™XÛÝ™\žWÚY‚ˆ˜YË˜ÛÜÙJÛÛ‹X[\—ÚY™XÛÝ™\žWÝ\Ù\‹™XÛÝ™\žWÚYÜ\˜][Û[Ü\˜][ÛŠNØÛÛ‹˜ÛÛ[Z]

Bˆ™]\›ˆœÛÛšYžJœÛÛ‹›ØYÊ™XÙZ\Èœ™\ÜÛœÙWÚœÛÛˆ—JJBˆYˆš[š\ÚÜØ]™J™\Ý[
N‚ˆYˆ™XÛÝ™\žWÚY™˜YË˜ÛÜÙJÛÛ‹X[\—ÚY™XÛÝ™\žWÝ\Ù\‹™XÛÝ™\žWÚYÜ\˜][Û[Ü\˜][ÛŠBˆ™\Ý[È™\œÚ[Ûˆ—OY\Ý[X]WÝ™\œÚ[ÛŠ
BˆYˆÜ\˜][ÛŽ˜ÛÛ‹™^XÝ]J’S”ÑT•S•È\Ý[X]WÜØ]™WÜ™XÙZ\ÊX[\—ÚYÜ\˜][Û—ÚY^[ØYÚ\Ú™\ÜÛœÙWÚœÛÛŠHSQTÊËËËÊH‹
X[\—ÚYÜ\˜][Û‹™\]Y\ÝÚ\ÚœÛÛ‹™[\Ê™\Ý[
JJBˆÛÛ‹˜ÛÛ[Z]

Bˆ™]\›ˆœÛÛšYžJ™\Ý[
BˆÈÛ™HXÝ]™H\Ý[X]H\ˆ›Ü\HTˆPST‹ˆ[›Ý\ˆX[\ˆØ[ˆ][ÝBˆÈHØ[YHY™\ÜÈÚ]Ý]ÙYZ[™ÈÜˆÝ™\Üš][™È\ÈX[\‰ÜÈ™XÛÜ™‚ˆ›Ü›O[[X™HŽˆˆ‹š›Ú[ŠÝŠˆÜˆˆŠK›ÝÙ\Š
Kœ™\XÙJ‹‹ˆŠKœ™\XÙJ‹ˆ‹ˆŠKœÜ]

JBˆY™\Ü×ÚÙ^O[›Ü›JY™\ÜÊBˆ^\Ý[™ÏS›Û™Bˆ›Üˆ›ÝÈ[ˆÛÛ‹™^XÝ]J”ÑSPÕ
ˆ”“ÓH\Ý[X]\ÈÒT‘HX[\—ÚYOÈÔ‘Tˆ–HÜ™X]YØ]TÐÈ‹
X[\—ÚY
JK™™]Ú[

N‚ˆYˆ›Ü›J›ÝÖÈ˜Y™\ÜÈ—JOOXY™\Ü×ÚÙ^N‚ˆ^\Ý[™Ï\›ÝÎØœ™XZÂˆYˆ^\Ý[™Î‚ˆ˜\ÙO\™\]Y\ÝšXY\œË™Ù]
’Y‹SX]ÚŠBˆYˆ˜\ÙH[™˜\ÙHOY\Ý[X]WÝ™\œÚ[ÛŠ^\Ý[™ÖÈœ^[ØY—JNœ™]\›ˆœÛÛšYžJ\œ›ÜH•\È\Ý[X]HÚ[™ÙY[ˆ[›Ý\ˆÙ\ÜÚ[Û‹ˆ[Ý\ˆYX\Ý\™[Y[È\™HÝ[\™Kˆ™[Ü[ˆH]\ÝØ]™Y™\œÚ[Ûˆ™Y›Ü™HØ]š[™ÈÚ[™Ù\ËˆŠKBˆÈšXÚ[™ÈY]ÈÈ›ÝÝÛˆ›ÛÚÚ[™ËÜ^[Y[šY[ÎÈYXØ]Y[™Ú[ÈË‚ˆØ]™YZœÛÛ‹›ØYÊ^\Ý[™ÖÈœ^[ØY—JBˆ›ÜˆÙ^H[ˆ
š›Ø—ÜÝ]\È‹œØÚY[YÙ]H‹˜ÛÛ\][Û—Ù]H‹˜[[Ý[ÜZYŠN‚ˆYˆÙ^H[ˆØ]™Y™ÚÙ^WO\Ø]™YÚÙ^WBˆYˆ\Ý[X]WÝ™\œÚ[ÛŠ
OOY\Ý[X]WÝ™\œÚ[ÛŠØ]™Y
N‚ˆ™]\›ˆš[š\ÚÜØ]™JXÝ
YY^\Ý[™ÖÈšY—KÜ™X]YØ]Y^\Ý[™ÖÈ˜Ü™X]YØ]—K\]YQ˜[ÙJJBˆYˆ›Ý^\Ý[™Î‚ˆÙ™ÏXÜ™Y]ÜÙ][™ÜÊÛÛ‹X[\—ÚY
BˆX[\—Ü›ÝÏXÛÛ‹™^XÝ]J”ÑSPÕ\Ý[X]WÛ[Z][—ØÛÙH”“ÓHX[\œÈÒT‘HYOÈ‹
X[\—ÚY
JK™™]ÚÛ™J
BˆZYÜ[X›ÛÛ
X[\—Ü›ÝÈ[™X[\—Ü›ÝÖÈœ[—ØÛÙH—H[ˆÕP”ÐÔ’TSÓ—ÓSRUÊBˆYˆ›Ý\×ÚXYÛÙ™šXÙJ
H[™
ZYÜ[ˆÜˆÙ™ÖÈ˜ÛÛ\[Y[\žH—HÜˆ›Ý\×Ü™XÛÝ™\žWÝ\ÝÜÙ\šXÙJ
JN‚ˆ\Ý[X]WÛ[Z]Z[
X[\—Ü›ÝÖÈ™\Ý[X]WÛ[Z]—HÜˆ
HYˆX[\—Ü›ÝÈ[ÙHˆ\Ý[X]WÝ\ÙYZ[
ÛÛ‹™^XÝ]J”ÑSPÕÓÕS•

ŠHTÈ\Ý[X]WØÛÝ[”“ÓH\Ý[X]\ÈÒT‘HX[\—ÚYOÈ‹
X[\—ÚY
JK™™]ÚÛ™J
VÈ™\Ý[X]WØÛÝ[—JBˆ[ÝÙYËÏXÛÛœÝ[YWØÜ™Y]
ÛÛ‹X[\—ÚY™\Ý[X]\È‹\Ý[X]WÝ\ÙY\Ý[X]WÛ[Z]
BˆYˆ›Ý[ÝÙY‚ˆ™]\›ˆœÛÛšYžJ\œ›ÜH‘\Ý[X]H[ÝØ[˜ÙH™XXÚYˆ‹\Ù\—Ù\œ›ÜH–[Ý\ˆ\Ý[X]H[ÝØ[˜ÙH\È\ÙYˆÛÛXÝY\šT][ÝHÝ\Ü›Üˆ^˜HÜ™Y]ËˆŠKÂ‚ˆÜ™X]Y][YKœÝ™[YJ‰VKI[KIY	R‰SN‰TÖˆ‹[YK™Û][YJ
JBˆ^[ØYÚœÛÛZœÛÛ‹™[\ÊÙ\\˜]ÜœÏJ‹‹ŽˆŠJBˆ˜[ÏJÝŠ™Ù]
˜Ý\ÝÛY\—Û˜[YHŠHÜˆˆŠKÝŠ™Ù]
˜Ý\ÝÛY\—ÜÛ™HŠHÜˆˆŠKÝŠ™Ù]
˜Ý\ÝÛY\—Ù[XZ[ŠHÜˆˆŠKY™\ÜË›Ø]
™Ù]
Ý[Ø\™XHŠHÜˆ
K›Ø]
™Ù]
Ý[ÜšXÙHŠHÜˆ
K^[ØYÚœÛÛŠBˆYˆ^\Ý[™Î‚ˆÛÛ‹™^XÝ]J’S”ÑT•S•È\Ý[X]WÜ™]š\Ú[ÛœÊ™]š\Ú[Û—ÚY\Ý[X]WÚY™]š\ÙYØ]Ý\ÝÛY\—Û˜[YKÝ\ÝÛY\—ÜÛ™KÝ\ÝÛY\—Ù[XZ[Y™\ÜËÝ[Ø\™XKÝ[ÜšXÙK^[ØYX[\—ÚY
HSQTÊËËËËËËËËËËÊH‹
ÝŠ]ZY]ZY

JK^\Ý[™ÖÈšY—KÜ™X]Y^\Ý[™ÖÈ˜Ý\ÝÛY\—Û˜[YH—K^\Ý[™ÖÈ˜Ý\ÝÛY\—ÜÛ™H—K^\Ý[™ÖÈ˜Ý\ÝÛY\—Ù[XZ[—K^\Ý[™ÖÈ˜Y™\ÜÈ—K^\Ý[™ÖÈÝ[Ø\™XH—K^\Ý[™ÖÈÝ[ÜšXÙH—K^\Ý[™ÖÈœ^[ØY—KX[\—ÚY
JBˆÛÛ‹™^XÝ]J•TUH\Ý[X]\ÈÑUÜ™X]YØ]OËÝ\ÝÛY\—Û˜[YOOËÝ\ÝÛY\—ÜÛ™OOËÝ\ÝÛY\—Ù[XZ[OËY™\ÜÏOËÝ[Ø\™XOOËÝ[ÜšXÙOOË^[ØYOÈÒT‘HYOÈS‘X[\—ÚYOÈ‹
Ü™X]Y
˜[Ë^\Ý[™ÖÈšY—KX[\—ÚY
JBˆ™]\›ˆš[š\ÚÜØ]™JXÝ
YY^\Ý[™ÖÈšY—KÜ™X]YØ]XÜ™X]Y\]YUYJJBˆZY\ÝŠ]ZY]ZY

JBˆÛÛ‹™^XÝ]J’S”ÑT•S•È\Ý[X]\ÊYÜ™X]YØ]Ý\ÝÛY\—Û˜[YKÝ\ÝÛY\—ÜÛ™KÝ\ÝÛY\—Ù[XZ[Y™\ÜËÝ[Ø\™XKÝ[ÜšXÙK^[ØYX[\—ÚY
HSQTÊËËËËËËËËËÊH‹
ZYÜ™X]Y
˜[ËX[\—ÚY
JBˆ™]\›ˆš[š\ÚÜØ]™JXÝ
YYZYÜ™X]YØ]XÜ™X]Y\]YQ˜[ÙJJBˆO\ÝŠ™\]Y\Ý˜\™ÜË™Ù]
œHŠHÜˆˆŠKœÝš\

BˆYˆN‚ˆZÙOH‰HŠÜJÈ‰HŽÈ›ÝÜÏXÛÛ‹™^XÝ]J”ÑSPÕYÜ™X]YØ]Ý\ÝÛY\—Û˜[YKÝ\ÝÛY\—ÜÛ™KÝ\ÝÛY\—Ù[XZ[Y™\ÜËÝ[Ø\™XKÝ[ÜšXÙH”“ÓH\Ý[X]\ÈÒT‘HX[\—ÚYOÈS‘
Ý\ÝÛY\—Û˜[YHRÑHÈÔˆÝ\ÝÛY\—ÜÛ™HRÑHÈÔˆÝ\ÝÛY\—Ù[XZ[RÑHÈÔˆY™\ÜÈRÑHÊHÔ‘Tˆ–HÜ™X]YØ]TÐÈSRUL‹
X[\—ÚYZÙKZÙKZÙKZÙJJK™™]Ú[

Bˆ[ÙNˆ›ÝÜÏXÛÛ‹™^XÝ]J”ÑSPÕYÜ™X]YØ]Ý\ÝÛY\—Û˜[YKÝ\ÝÛY\—ÜÛ™KÝ\ÝÛY\—Ù[XZ[Y™\ÜËÝ[Ø\™XKÝ[ÜšXÙH”“ÓH\Ý[X]\ÈÒT‘HX[\—ÚYOÈÔ‘Tˆ–HÜ™X]YØ]TÐÈSRUL‹
X[\—ÚY
JK™™]Ú[

Bˆ™\Ý[V×Bˆ›Üˆˆ[ˆ›ÝÜÎ‚ˆ][OYXÝ
ŠBˆžN‚ˆ[XÛÛ‹™^XÝ]J”ÑSPÕ^[ØY”“ÓH\Ý[X]\ÈÒT‘HYOÈS‘X[\—ÚYOÈ‹
][VÈšY—KX[\—ÚY
JK™™]ÚÛ™J
Bˆ^[ØYZœÛÛ‹›ØYÊ[Èœ^[ØY—HÜˆžßHŠHYˆ[[ÙHßBˆ^Ù\^Ù\[ÛŽ‚ˆ^[ØY^ßBˆ][VÈš›Ø—ÜÝ]\È—O\ÝŠ^[ØY™Ù]
š›Ø—ÜÝ]\ÈŠHÜˆ‘\Ý[X]HŠBˆ][VÈœØÚY[YÙ]H—O\ÝŠ^[ØY™Ù]
œØÚY[YÙ]HŠHÜˆˆŠBˆ][VÈ˜ÛÛ\][Û—Ù]H—O\ÝŠ^[ØY™Ù]
˜ÛÛ\][Û—Ù]HŠHÜˆˆŠBˆžNˆ][VÈ˜[[Ý[ÜZY—OY›Ø]
^[ØY™Ù]
˜[[Ý[ÜZYŠHÜˆ
Bˆ^Ù\^Ù\[ÛŽˆ][VÈ˜[[Ý[ÜZY—OLŒˆ™\Ý[˜\[™
][JBˆ™]\›ˆœÛÛšYžJ™\Ý[
Bˆš[˜[NˆÛÛ‹˜ÛÜÙJ
B‚\œÜÝ
‹Ø\KÙ\Ý[X]\ËÏ\Ý[X]WÚY‹ØÛÛ\][Û‹Y]HŠB™Yˆ\Ý[X]WØÛÛ\][Û—Ù]J\Ý[X]WÚY
N‚ˆX[\—ÚY\Ù\ÜÚ[Û‹™Ù]
™X[\—ÚYŠBˆYˆ›ÝX[\—ÚYœ™]\›ˆœÛÛšYžJÚÏQ˜[ÙK\œ›ÜH“ÙÚ[ˆ™\]Z\™YˆŠKBˆ\™\]Y\Ý™Ù]ÚœÛÛŠÚ[[UYJHÜˆßNØÛÛ\][Û—Ù]O\ÝŠ™Ù]
˜ÛÛ\][Û—Ù]HŠHÜˆˆŠKœÝš\

BˆYˆÛÛ\][Û—Ù]N‚ˆžNˆ[YKœÝœ[YJÛÛ\][Û—Ù]K‰VKI[KIYŠBˆ^Ù\˜[YQ\œ›ÜŽœ™]\›ˆœÛÛšYžJÚÏQ˜[ÙK\œ›ÜH’[˜[YÛÛ\][Ûˆ]KˆŠKˆÛÛY\Ý[X]WÙŠ
BˆžN‚ˆØÚ×ØXØÛÝ[
ÛÛ‹ÝŠX[\—ÚY
JBˆ›ÝÏXÛÛ‹™^XÝ]J”ÑSPÕ^[ØY”“ÓH\Ý[X]\ÈÒT‘HYOÈS‘X[\—ÚYOÈ‹
\Ý[X]WÚYX[\—ÚY
JK™™]ÚÛ™J
BˆYˆ›Ý›ÝÎœ™]\›ˆœÛÛšYžJÚÏQ˜[ÙK\œ›ÜH‘\Ý[X]H›Ý›Ý[™ˆŠKˆ˜]Ï\›ÝÖÈœ^[ØY—HYˆ\Ø]Š›ÝËšÙ^\ÈŠH[ÙH›ÝÖÌNÜ^[ØYZœÛÛ‹›ØYÊ˜]ÈÜˆžßHŠNÜ^[ØYÈ˜ÛÛ\][Û—Ù]H—OXÛÛ\][Û—Ù]BˆÛÛ‹™^XÝ]J•TUH\Ý[X]\ÈÑU^[ØYOÈÒT‘HYOÈS‘X[\—ÚYOÈ‹
œÛÛ‹™[\Ê^[ØY
K\Ý[X]WÚYX[\—ÚY
JNØÛÛ‹˜ÛÛ[Z]

Bˆ™]\›ˆœÛÛšYžJÚÏUYKÛÛ\][Û—Ù]OXÛÛ\][Û—Ù]JBˆš[˜[NˆÛÛ‹˜ÛÜÙJ
B‚\œÜÝ
‹Ø\KÙ\Ý[X]\ËÏ\Ý[X]WÚY‹Ø[[Ý[\ZYŠB™Yˆ\Ý[X]WØ[[Ý[ÜZY
\Ý[X]WÚY
N‚ˆX[\—ÚY\Ù\ÜÚ[Û‹™Ù]
™X[\—ÚYŠBˆYˆ›ÝX[\—ÚYœ™]\›ˆœÛÛšYžJÚÏQ˜[ÙK\œ›ÜH“ÙÚ[ˆ™\]Z\™YˆŠKBˆ\™\]Y\Ý™Ù]ÚœÛÛŠÚ[[UYJHÜˆßBˆžN‚ˆ˜]×Ø[[Ý[Y™Ù]
˜[[Ý[ÜZY‹
Bˆ[[Ý[ÜZYY›Ø]
˜]×Ø[[Ý[
BˆYˆ\Ú[œÝ[˜ÙJ˜]×Ø[[Ý[›ÛÛ
HÜˆ›ÝX]š\Ùš[š]J[[Ý[ÜZY
HÜˆ[[Ý[ÜZYœ˜Z\ÙH˜[YQ\œ›ÜŠ
Bˆ^Ù\
\Q\œ›Ü‹˜[YQ\œ›Ü‹Ý™\™›ÝÑ\œ›ÜŠNœ™]\›ˆœÛÛšYžJÚÏQ˜[ÙK\œ›ÜH’[˜[Y[[Ý[ˆŠKˆÛÛY\Ý[X]WÙŠ
BˆžN‚ˆØÚ×ØXØÛÝ[
ÛÛ‹ÝŠX[\—ÚY
JBˆ›ÝÏXÛÛ‹™^XÝ]J”ÑSPÕ^[ØY”“ÓH\Ý[X]\ÈÒT‘HYOÈS‘X[\—ÚYOÈ‹
\Ý[X]WÚYX[\—ÚY
JK™™]ÚÛ™J
BˆYˆ›Ý›ÝÎœ™]\›ˆœÛÛšYžJÚÏQ˜[ÙK\œ›ÜH‘\Ý[X]H›Ý›Ý[™ˆŠKˆ˜]Ï\›ÝÖÈœ^[ØY—HYˆ\Ø]Š›ÝËšÙ^\ÈŠH[ÙH›ÝÖÌNÜ^[ØYZœÛÛ‹›ØYÊ˜]ÈÜˆžßHŠNÜ^[ØYÈ˜[[Ý[ÜZY—OX[[Ý[ÜZYˆÛÛ‹™^XÝ]J•TUH\Ý[X]\ÈÑU^[ØYOÈÒT‘HYOÈS‘X[\—ÚYOÈ‹
œÛÛ‹™[\Ê^[ØY
K\Ý[X]WÚYX[\—ÚY
JNØÛÛ‹˜ÛÛ[Z]

Bˆ™]\›ˆœÛÛšYžJÚÏUYK[[Ý[ÜZYX[[Ý[ÜZY
Bˆš[˜[NˆÛÛ‹˜ÛÜÙJ
B‚\œÜÝ
‹Ø\KÙ\Ý[X]\ËÏ\Ý[X]WÚY‹ÜØÚY[YY]HŠB™Yˆ\Ý[X]WÜØÚY[YÙ]J\Ý[X]WÚY
N‚ˆX[\—ÚY\Ù\ÜÚ[Û‹™Ù]
™X[\—ÚYŠBˆYˆ›ÝX[\—ÚYœ™]\›ˆœÛÛšYžJÚÏQ˜[ÙK\œ›ÜH“ÙÚ[ˆ™\]Z\™YˆŠKBˆ\™\]Y\Ý™Ù]ÚœÛÛŠÚ[[UYJHÜˆßBˆØÚY[YÙ]O\ÝŠ™Ù]
œØÚY[YÙ]HŠHÜˆˆŠKœÝš\

BˆYˆØÚY[YÙ]N‚ˆžNˆ[YKœÝœ[YJØÚY[YÙ]K‰VKI[KIYŠBˆ^Ù\˜[YQ\œ›ÜŽœ™]\›ˆœÛÛšYžJÚÏQ˜[ÙK\œ›ÜH’[˜[YØÚY[Y]KˆŠKˆÛÛY\Ý[X]WÙŠ
BˆžN‚ˆØÚ×ØXØÛÝ[
ÛÛ‹ÝŠX[\—ÚY
JBˆ›ÝÏXÛÛ‹™^XÝ]J”ÑSPÕ^[ØY”“ÓH\Ý[X]\ÈÒT‘HYOÈS‘X[\—ÚYOÈ‹
\Ý[X]WÚYX[\—ÚY
JK™™]ÚÛ™J
BˆYˆ›Ý›ÝÎœ™]\›ˆœÛÛšYžJÚÏQ˜[ÙK\œ›ÜH‘\Ý[X]H›Ý›Ý[™ˆŠKˆ˜]Ï\›ÝÖÈœ^[ØY—HYˆ\Ø]Š›ÝËšÙ^\ÈŠH[ÙH›ÝÖÌBˆ^[ØYZœÛÛ‹›ØYÊ˜]ÈÜˆžßHŠBˆ^[ØYÈœØÚY[YÙ]H—O\ØÚY[YÙ]BˆÛÛ‹™^XÝ]J•TUH\Ý[X]\ÈÑU^[ØYOÈÒT‘HYOÈS‘X[\—ÚYOÈ‹
œÛÛ‹™[\Ê^[ØY
K\Ý[X]WÚYX[\—ÚY
JBˆÛÛ‹˜ÛÛ[Z]

Bˆ™]\›ˆœÛÛšYžJÚÏUYKØÚY[YÙ]O\ØÚY[YÙ]JBˆš[˜[N‚ˆÛÛ‹˜ÛÜÙJ
B‚\œÜÝ
‹Ø\KÙ\Ý[X]\ËÏ\Ý[X]WÚY‹ÜÝ]\ÈŠB™Yˆ\Ý[X]WÚ›Ø—ÜÝ]\Ê\Ý[X]WÚY
N‚ˆX[\—ÚY\ÝŠÙ\ÜÚ[Û‹™Ù]
™X[\—ÚYŠHÜˆˆŠBˆ\™\]Y\Ý™Ù]ÚœÛÛŠÚ[[UYJHÜˆßBˆ›Ø—ÜÝ]\Ï\ÝŠ™Ù]
š›Ø—ÜÝ]\ÈŠHÜˆˆŠKœÝš\

BˆYˆ›Ø—ÜÝ]\È›Ý[ˆ
‘\Ý[X]H‹›ÛÚÙY‹ÛÛ\]YŠN‚ˆ™]\›ˆœÛÛšYžJ\œ›ÜH’[˜[Y›ØˆÝ]\ÈŠKˆÛÛY\Ý[X]WÙŠ
BˆžN‚ˆØÚ×ØXØÛÝ[
ÛÛ‹ÝŠX[\—ÚY
JBˆ›ÝÏXÛÛ‹™^XÝ]J”ÑSPÕ^[ØY”“ÓH\Ý[X]\ÈÒT‘HYOÈS‘X[\—ÚYOÈ‹
\Ý[X]WÚYX[\—ÚY
JK™™]ÚÛ™J
BˆYˆ›Ý›ÝÎœ™]\›ˆœÛÛšYžJ\œ›ÜH‘\Ý[X]H›Ý›Ý[™ŠKˆžNˆ^[ØYZœÛÛ‹›ØYÊ›ÝÖÈœ^[ØY—HÜˆžßHŠBˆ^Ù\^Ù\[ÛŽˆ^[ØY^ßBˆ^[ØYÈš›Ø—ÜÝ]\È—OZ›Ø—ÜÝ]\ÂˆÛÛ‹™^XÝ]J•TUH\Ý[X]\ÈÑU^[ØYOÈÒT‘HYOÈS‘X[\—ÚYOÈ‹
œÛÛ‹™[\Ê^[ØYÙ\\˜]ÜœÏJ‹‹ŽˆŠJK\Ý[X]WÚYX[\—ÚY
JBˆÛÛ‹˜ÛÛ[Z]

Bˆ™]\›ˆœÛÛšYžJÚÏUYK›Ø—ÜÝ]\ÏZ›Ø—ÜÝ]\ÊBˆš[˜[N‚ˆÛÛ‹˜ÛÜÙJ
B‚\™Ù]
‹Ø\KÙ\Ý[X]\ËÏ\Ý[X]WÚYˆŠB™Yˆ\Ý[X]WÚ\ÝÜžWÛÛ™J\Ý[X]WÚY
N‚ˆX[\—ÚY\ÝŠÙ\ÜÚ[Û‹™Ù]
™X[\—ÚYŠHÜˆˆŠBˆÛÛY\Ý[X]WÙŠ
BˆžNˆ›ÝÏXÛÛ‹™^XÝ]J”ÑSPÕ
ˆ”“ÓH\Ý[X]\ÈÒT‘HYOÈS‘X[\—ÚYOÈ‹
\Ý[X]WÚYX[\—ÚY
JK™™]ÚÛ™J
Bˆš[˜[NˆÛÛ‹˜ÛÜÙJ
BˆYˆ›Ý›ÝÎœ™]\›ˆœÛÛšYžJ\œ›ÜH‘\Ý[X]H›Ý›Ý[™ŠKˆYXÝ
›ÝÊNÙÈœ^[ØY—OZœÛÛ‹›ØYÊ™Ù]
œ^[ØYŠHÜˆžßHŠNÜ™]\›ˆœÛÛšYžJ
B‚\™Ù]
‹Ø\KÙ\Ý[X]\ËÏ\Ý[X]WÚY‹Ý™\œÚ[ÛœÈŠB™Yˆ\Ý[X]WÚ\ÝÜžWÝ™\œÚ[ÛœÊ\Ý[X]WÚY
N‚ˆX[\—ÚY\ÝŠÙ\ÜÚ[Û‹™Ù]
™X[\—ÚYŠHÜˆˆŠBˆÛÛY\Ý[X]WÙŠ
BˆžN‚ˆÝ\œ™[XÛÛ‹™^XÝ]J”ÑSPÕ
ˆ”“ÓH\Ý[X]\ÈÒT‘HYOÈS‘X[\—ÚYOÈ‹
\Ý[X]WÚYX[\—ÚY
JK™™]ÚÛ™J
BˆYˆ›ÝÝ\œ™[œ™]\›ˆœÛÛšYžJ\œ›ÜH‘\Ý[X]H›Ý›Ý[™ŠKˆ™]š\Ú[ÛœÏXÛÛ‹™^XÝ]J”ÑSPÕ
ˆ”“ÓH\Ý[X]WÜ™]š\Ú[ÛœÈÒT‘H\Ý[X]WÚYOÈS‘X[\—ÚYOÈÔ‘Tˆ–H™]š\ÙYØ]TÐÈ‹
\Ý[X]WÚYX[\—ÚY
JK™™]Ú[

BˆYˆ[œXÚÊ›ÝË]WÙšY[
N‚ˆYXÝ
›ÝÊBˆÈœ^[ØY—OZœÛÛ‹›ØYÊ™Ù]
œ^[ØYŠHÜˆžßHŠBˆÈœØ]™YØ]—OY™Ù]
]WÙšY[
HÜˆˆ‚ˆ™]\›ˆˆ™]\›ˆœÛÛšYžJÝ\œ™[][œXÚÊÝ\œ™[˜Ü™X]YØ]ŠK™]š\Ú[ÛœÏVÝ[œXÚÊ‹œ™]š\ÙYØ]ŠH›Üˆˆ[ˆ™]š\Ú[Ûœ×JBˆš[˜[N‚ˆÛÛ‹˜ÛÜÙJ
B‚\œÜÝ
‹Ø\KÙ\Ý[X]\ËÏ\Ý[X]WÚY‹ÙY][™Ë\Ù\ÜÚ[ÛˆŠB™YˆØ]™YÙ\Ý[X]WÙY][™×ÜÙ\ÜÚ[ÛŠ\Ý[X]WÚY
N‚ˆœ›ÛHØ]™YÙ\Ý[X]WÙY][\ÜYX\Ý\™[Y[Ø›Ý[™Âˆ™\œÚ[ÛœÏY\Ý[X]WÚ\ÝÜžWÝ™\œÚ[ÛœÊ\Ý[X]WÚY
BˆYˆ\Ú[œÝ[˜ÙJ™\œÚ[ÛœË\JNœ™]\›ˆ™\œÚ[ÛœÂˆ]O]™\œÚ[ÛœË™Ù]ÚœÛÛŠ
BˆžN‚ˆ[™^J™\]Y\Ý™Ù]ÚœÛÛŠÚ[[UYJHÜˆßJK™Ù]
™\œÚ[Û—Ú[™^‹LJBˆYˆ\Ú[œÝ[˜ÙJ[™^›ÛÛ
HÜˆ›Ý\Ú[œÝ[˜ÙJ[™^[
HÜˆ[™^LNœ˜Z\ÙH˜[YQ\œ›ÜŠ’[˜[YØ]™Y™\œÚ[ÛˆŠBˆ™\œÚ[ÛY]VÈ˜Ý\œ™[—HYˆ[™^OKLH[ÙH]VÈœ™]š\Ú[ÛœÈ—VÚ[™^Bˆ^[ØY]™\œÚ[Û‹™Ù]
œ^[ØYŠHÜˆßNØ›Ý[™Ï[YX\Ý\™[Y[Ø›Ý[™Ê^[ØY
Bˆ^Ù\
˜[YQ\œ›Ü‹[™^\œ›Ü‹Ù^Q\œ›ÜŠH\ÈNœ™]\›ˆœÛÛšYžJ\œ›Ü\ÝŠJHÜˆ”Ø]™Y™\œÚ[Ûˆ[˜]˜Z[X›HŠKˆYˆ›ÝÓÓÑÓWÓPT×ÐTWÒÑVNœ™]\›ˆœÛÛšYžJ\œ›ÜH‘ÛÛÙÛHX\ÈTHÙ^H\È›ÝÛÛ™šYÝ\™YŠKLÂˆ]J›Ý[™ÖÌVÌJØ›Ý[™ÖÌWVÌJKÌŽÛ™ÏJ›Ý[™ÖÌVÌWJØ›Ý[™ÖÌWVÌWJKÌ‚ˆÚÙ[]]ZY]ZY

Kš^ˆÑTÔÒSÓ”ÖÝÚÙ[—O^ÈšÙ^HŽ‘ÓÓÑÓWÓPT×ÐTWÒÑVK™X[\—ÚYŽœÝŠÙ\ÜÚ[Û‹™Ù]
™X[\—ÚYŠHÜˆˆŠK˜Ü™X]YŽ[YK[YJ
K›[ÙHŽˆ›X[X[Ü›ÛÙ—ÜÝ]XÈˆYˆX[X[Ü›ÛÙ—ÜXWÙ[˜X›Y

HÜˆ
^[ØY™Ù]
œ][ÝHŠHÜˆßJK™Ù]
›X[X[›ÛÙ•ÛÜšÙ›ÝÈŠH[ÙH™˜[˜XÚÈ‹›]Ž›]›™ÈŽ›™Ë˜[˜ÚÜ—Û]Ž›]˜[˜ÚÜ—Û™ÈŽ›™Ë™›Ü›X]YØY™\ÜÈŽœ^[ØY™Ù]
˜Y™\ÜÈŠHÜˆˆ‹œ™ØˆŽ“›Û™K›X\ÚÈŽ“›Û™KœÝ™Y]Ž“›Û™Kœ™Ø—ØØXÚHŽ“›Û™K›X\Ú×ØØXÚHŽ“›Û™KœÝ™Y]ØØXÚHŽ“›Û™K™˜[˜XÚ×ØØXÚHŽ“›Û™K™^XÝÜ[—ØØXÚHŽ“›Û™KœÝXÝ\™WÛX\ÚÜÈŽžß_BˆÑTÔÒSÓ”Ëœ\œÚ\Ý
ÚÙ[ŠBˆ™]\›ˆœÛÛšYžJÚÙ[]ÚÙ[‹™\œÚ[ÛY\Ý[X]WÝ™\œÚ[ÛŠ]VÈ˜Ý\œ™[—VÈœ^[ØY—JKÙ[\^È›]]YHŽ›]›Û™Ú]YHŽ›™ßK›Ý[™ÏX›Ý[™Ë›Ø—Ù]Z[Ï^ÚÎŠ]VÈ˜Ý\œ™[—K™Ù]
œ^[ØYŠHÜˆßJK™Ù]
ÊH›ÜˆÈ[ˆ
š›Ø—ÜÝ]\È‹œØÚY[YÙ]H‹˜ÛÛ\][Û—Ù]H‹˜[[Ý[ÜZYŠ_JB‚\™Ù]
‹Ù^XÝ\[‹[Y]KÏÚÙ[ˆŠB™Yˆ^XÝÜ[—ÛY]JÚÙ[ŠN‚ˆÙ\ÜÏTÑTÔÒSÓ”Ë™Ù]
ÚÙ[ŠBˆYˆ›ÝÙ\ÜÎœ™]\›ˆœÛÛšYžJ\œ›ÜH”Ù\ÜÚ[Ûˆ^\™YŠKˆ™]\›ˆœÛÛšYžJ]]YO\Ù\ÜË™Ù]
™\Ü^WÛ]‹Ù\ÜË™Ù]
›]ŠJKÛ™Ú]YO\Ù\ÜË™Ù]
™\Ü^WÛ™È‹Ù\ÜË™Ù]
›™ÈŠJK›ÛÛO\Ù\ÜË™Ù]
™\Ü^WÞ›ÛÛH‹NJKÚYMZYÚM
B‚\™Ù]
‹Ù^XÝ\[‹[X\ÏÚÙ[ˆŠB™Yˆ^XÝÜ[—ÛX\
ÚÙ[ŠN‚ˆÙ\ÜÏTÑTÔÒSÓ”Ë™Ù]
ÚÙ[ŠBˆYˆ›ÝÙ\ÜÎœ™]\›ˆ™\ÜÛœÙJ”Ù\ÜÚ[Ûˆ^\™Y‹Ý]\ÏM
BˆžN‚ˆYˆÙ\ÜË™Ù]
™^XÝÜ[—ØØXÚHŠH\È›Û™N‚ˆ]\Ù\ÜË™Ù]
™\Ü^WÛ]‹Ù\ÜË™Ù]
›]ŠJNÛ™Ï\Ù\ÜË™Ù]
™\Ü^WÛ™È‹Ù\ÜË™Ù]
›™ÈŠJNÞ›ÛÛO\Ù\ÜË™Ù]
™\Ü^WÞ›ÛÛH‹NJBˆO]\›X‹œ\œÙK\›[˜ÛÙJÈ˜Ù[\ˆŽ™ˆžÛ]KÛ™ßH‹ž›ÛÛHŽž›ÛÛKœÚ^™HŽˆ‹›X\\HŽˆœØ][]H‹™›Ü›X]Žˆœ™È‹šÙ^HŽœÙ\ÜÖÈšÙ^H—_JBˆ\›HšÎ‹ËÛX\Ë™ÛÛÙÛX\\Ë˜ÛÛKÛX\ËØ\KÜÝ]XÛX\ÈŠÜBˆXY\œÏ^È•\Ù\‹PYÙ[Žˆ”Ú[™ÛQÝX\™›ÛÙ\ÜÙ\ÜÛY[Ì‹Œ‹”™Y™\™\ˆŽœ™\]Y\ÝšÜÝÝ\›“ÜšYÚ[ˆŽœ™\]Y\ÝšÜÝÝ\›œœÝš\
‹ÈŠ_Bˆ™\O]\›X‹œ™\]Y\Ý”™\]Y\Ý
\›XY\œÏZXY\œÊBˆžN‚ˆÚ]\›X‹œ™\]Y\Ý\›Ü[Š™\K[Y[Ý]LLŠH\ÈŽ˜Ý\‹šXY\œË™Ù]
ÛÛ[U\H‹š[XYÙKÜ™ÈŠNØ›ÙO\‹œ™XY

Bˆ^Ù\\›X‹™\œ›Ü‹’\œ›Üˆ\ÈN‚ˆ˜]ÏZKœ™XY

K™XÛÙJ]‹N‹œ™\XÙHŠVÎŒLŒKœ™\XÙJÙ\ÜË™Ù]
šÙ^HŠHÜˆˆ‹–ÐTHÑVH‘QPÕQHŠBˆ˜Z\ÙH˜[YQ\œ›ÜŠˆ‘ÛÛÙÛHX\ÈÝ]XÈÚK˜ÛÙ_NˆÜ˜]ßHŠBˆÙ\ÜÖÈ™^XÝÜ[—ØØXÚH—OJÝ›ÙJBˆÝ›ÙO\Ù\ÜÖÈ™^XÝÜ[—ØØXÚH—NÜ™]\›ˆ™\ÜÛœÙJ›ÙKÛÛ[Ý\OXÝ
Bˆ^Ù\^Ù\[Ûˆ\ÈN‚ˆ™]\›ˆ™\ÜÛœÙJÝŠJKœ™\XÙJÙ\ÜË™Ù]
šÙ^HŠHÜˆˆ‹–ÐTHÑVH‘QPÕQHŠKÝ]\ÏMÛÛ[Ý\OH^ÜZ[ŽÈÚ\œÙ]]]‹NŠB‚\™Ù]
‹ÝÚYKXY\šX[ÏÚÙ[ˆŠB™YˆÚYWØY\šX[
ÚÙ[ŠN‚ˆÙ\ÜÏTÑTÔÒSÓ”Ë™Ù]
ÚÙ[ŠBˆYˆ›ÝÙ\ÜÎœ™]\›ˆ™\ÜÛœÙJ”Ù\ÜÚ[Ûˆ^\™Y‹Ý]\ÏM
BˆžN‚ˆ]Y›Ø]
™\]Y\Ý˜\™ÜË™Ù]
›]‹Ù\ÜË™Ù]
›]ŠJJNÛ™ÏY›Ø]
™\]Y\Ý˜\™ÜË™Ù]
›™È‹Ù\ÜË™Ù]
›™ÈŠJJBˆ›ÛÛOZ[
›Ø]
™\]Y\Ý˜\™ÜË™Ù]
ž›ÛÛH‹MÊJJBˆYˆ›Ý
NL[]NL[™LN[™ÏLN
Nœ˜Z\ÙH˜[YQ\œ›ÜŠ’[˜[YX\Ù[™HŠBˆ›ÛÛO[X^
MKZ[ŠŒ›ÛÛJJBˆO]\›X‹œ\œÙK\›[˜ÛÙJÈ˜Ù[\ˆŽ™ˆžÛ]KÛ™ßH‹ž›ÛÛHŽž›ÛÛKœÚ^™HŽˆ‹œØØ[HŽˆŒˆ‹›X\\HŽˆœØ][]H‹™›Ü›X]Žˆœ™È‹šÙ^HŽœÙ\ÜÖÈšÙ^H—_JBˆ\›HšÎ‹ËÛX\Ë™ÛÛÙÛX\\Ë˜ÛÛKÛX\ËØ\KÜÝ]XÛX\ÈŠÜBˆXY\œÏ^È•\Ù\‹PYÙ[Žˆ”Ú[™ÛQÝX\™›ÛÙ\ÜÙ\ÜÛY[Ì‹Œ‹”™Y™\™\ˆŽœ™\]Y\ÝšÜÝÝ\›“ÜšYÚ[ˆŽœ™\]Y\ÝšÜÝÝ\›œœÝš\
‹ÈŠ_Bˆ™\O]\›X‹œ™\]Y\Ý”™\]Y\Ý
\›XY\œÏZXY\œÊBˆÚ]\›X‹œ™\]Y\Ý\›Ü[Š™\K[Y[Ý]LLŠH\ÈŽ‚ˆÝ\‹šXY\œË™Ù]
ÛÛ[U\H‹š[XYÙKÜ™ÈŠNØ›ÙO\‹œ™XY

Bˆ™]\›ˆ™\ÜÛœÙJ›ÙKÛÛ[Ý\OXÝ
Bˆ^Ù\^Ù\[Ûˆ\ÈN‚ˆ™]\›ˆ™\ÜÛœÙJÝŠJKœ™\XÙJÙ\ÜË™Ù]
šÙ^HŠHÜˆˆ‹–ÐTHÑVH‘QPÕQHŠKÝ]\ÏMÛÛ[Ý\OH^ÜZ[ŽÈÚ\œÙ]]]‹NŠB‚\™Ù]
‹Ù˜[˜XÚË[Y]KÏÚÙ[ˆŠB™Yˆ˜[˜XÚ×ÛY]JÚÙ[ŠN‚ˆÙ\ÜÏTÑTÔÒSÓ”Ë™Ù]
ÚÙ[ŠBˆYˆ›ÝÙ\ÜÎœ™]\›ˆœÛÛšYžJ\œ›ÜH”Ù\ÜÚ[Ûˆ^\™YŠKˆ™]\›ˆœÛÛšYžJ]]YO\Ù\ÜË™Ù]
›]ŠKÛ™Ú]YO\Ù\ÜË™Ù]
›™ÈŠK›ÛÛO\Ù\ÜË™Ù]
™˜[˜XÚ×Þ›ÛÛH‹Œ
KÚYMZYÚM
B‚\™Ù]
‹Ù˜[˜XÚË[X\ÏÚÙ[ˆŠB™Yˆ˜[˜XÚ×ÛX\
ÚÙ[ŠN‚ˆÙ\ÜÏTÑTÔÒSÓ”Ë™Ù]
ÚÙ[ŠBˆYˆ›ÝÙ\ÜÎœ™]\›ˆ™\ÜÛœÙJ”Ù\ÜÚ[Ûˆ^\™Y‹Ý]\ÏM
BˆžN‚ˆYˆÙ\ÜË™Ù]
™˜[˜XÚ×ØØXÚHŠH\È›Û™N‚ˆO]\›X‹œ\œÙK\›[˜ÛÙJÈ˜Ù[\ˆŽ™‰ÞÜÙ\ÜÖÈ›]—_KÜÙ\ÜÖÈ›™È—_IËž›ÛÛHŽœÙ\ÜË™Ù]
™˜[˜XÚ×Þ›ÛÛH‹Œ
KœÚ^™HŽˆ‹œØØ[HŽˆŒˆ‹›X\\HŽˆœØ][]H‹™›Ü›X]Žˆœ™È‹šÙ^HŽœÙ\ÜÖÈšÙ^H—_JBˆ\›HšÎ‹ËÛX\Ë™ÛÛÙÛX\\Ë˜ÛÛKÛX\ËØ\KÜÝ]XÛX\ÈŠÜBˆÈÝ]XÈX\ÈÙ^\ÈX^H™H™\ÝšXÝYžH™Y™\œ™\‹ˆ™XØ]\ÙH\È\\ÂˆÈØØ[Ù[™HØ[YHØØ[ÜÝ™Y™\œ™\ˆHœ›ÝÜÙ\ˆ\Ù\È[œÝXYÙˆBˆÈ˜\™HÙ\™\‹\ÚYH™\]Y\Ýˆ\ÈÙ\È›ÝÚ[™ÙH[žH›ÛÙ‹[YX\Ý\™[Y[ÛÙK‚ˆXY\œÏ^È•\Ù\‹PYÙ[Žˆ”Ú[™ÛQÝX\™›ÛÙ\ÜÙ\ÜÛY[Ì‹Œ‹”™Y™\™\ˆŽœ™\]Y\ÝšÜÝÝ\›“ÜšYÚ[ˆŽœ™\]Y\ÝšÜÝÝ\›œœÝš\
‹ÈŠ_Bˆ™\O]\›X‹œ™\]Y\Ý”™\]Y\Ý
\›XY\œÏZXY\œÊBˆžN‚ˆÚ]\›X‹œ™\]Y\Ý\›Ü[Š™\K[Y[Ý]LLŠH\ÈŽ‚ˆÝ\‹šXY\œË™Ù]
ÛÛ[U\H‹š[XYÙKÜ™ÈŠNØ›ÙO\‹œ™XY

Bˆ^Ù\\›X‹™\œ›Ü‹’\œ›Üˆ\ÈN‚ˆ˜]ÏZKœ™XY

K™XÛÙJ]‹N‹œ™\XÙHŠVÎŒLŒBˆ˜]Ï\˜]Ëœ™\XÙJÙ\ÜË™Ù]
šÙ^HŠHÜˆˆ‹–ÐTHÑVH‘QPÕQHŠBˆ˜Z\ÙH˜[YQ\œ›ÜŠˆ‘ÛÛÙÛHX\ÈÝ]XÈÚK˜ÛÙ_NˆÜ˜]ßHŠBˆÙ\ÜÖÈ™˜[˜XÚ×ØØXÚH—OJÝ›ÙJBˆÝ›ÙO\Ù\ÜÖÈ™˜[˜XÚ×ØØXÚH—NÜ™]\›ˆ™\ÜÛœÙJ›ÙKÛÛ[Ý\OXÝ
Bˆ^Ù\^Ù\[Ûˆ\ÈN‚ˆ\ÙÏ\ÝŠJKœ™\XÙJÙ\ÜË™Ù]
šÙ^HŠHÜˆˆ‹–ÐTHÑVH‘QPÕQHŠBˆ™]\›ˆ™\ÜÛœÙJ\ÙËÝ]\ÏMÛÛ[Ý\OH^ÜZ[ŽÈÚ\œÙ]]]‹NŠB‚\™Ù]
‹Ü™Ø‹ÏÚÙ[ˆŠB™Yˆ™ØŠÚÙ[ŠN‚ˆÏTÑTÔÒSÓ”Ë™Ù]
ÚÙ[ŠBˆYˆ›ÝÎœ™]\›ˆ™\ÜÛœÙJ”Ù\ÜÚ[Ûˆ^\™Y‹Ý]\ÏM
BˆYˆX[X[Ü›ÛÙ—ÜÙ\ÜÚ[ÛŠÊNœ™]\›ˆ™\ÜÛœÙJ“X[X[›ÛÙš[™È[XYÙ\žH[˜]˜Z[X›Kˆ™]žHHY\šX[[XYÙNÈÛÛ\ˆ™XÛÝ™\žH\È\ØX›Yˆ‹Ý]\ÏMJBˆžN‚ˆYˆÖÈœ™Ø—ØØXÚH—H\È›Û™N‚ˆYˆ›ÝË™Ù]
œ™ØˆŠH[™Ë™Ù]
›[ÙHŠOOHœÝ\™˜XÙWÜÝ]XÈŽ‚ˆÈ™]Z[ˆH™KY^\Ý[™ÈÝ\ÝÛY\‹\™\Ü‘Ðˆ˜[˜XÚË]^H›Ü‚ˆÈÛÛ\ˆÛ›HÚ[ˆ]˜[˜XÚÈ\ÈXÝX[H™\]Y\ÝYˆ™]™\ˆ\ÙBˆÈ\ÙH›ÛÙˆ]X[]Y\ÈÈšXÙHHÝ\™˜XÙHYX\Ý\™[Y[‚ˆžN‚ˆXZ[XZ[[™ÊÖÈšÙ^H—KÖÈ›]—KÖÈ›™È—JBˆ]™Ë˜Y]\Ï\›ÛÙ—Ú[XYÙ\žWÜ™\]Y\Ý
XZ[ŠBˆ^Y\œÏ\ÛÛ\—Û^Y\œÊÖÈšÙ^H—K]™Ë˜Y]\ÊBˆË\]J][XZ[–È›]]YH—K™Ï[XZ[–È›Û™Ú]YH—JBˆ^Ù\ÛÛ\Z[[™Ó›Ý›Ý[™‚ˆ^Y\œÏ\ÛÛ\—Û^Y\œÊÖÈšÙ^H—KÖÈ›]—KÖÈ›™È—JBˆË\]J™Ø[^Y\œË™Ù]
œ™Ø•\›ŠKX\ÚÏ[^Y\œË™Ù]
›X\ÚÕ\›ŠK[ÙOHœÛÛ\ˆŠBˆÑTÔÒSÓ”Ëœ\œÚ\Ý
ÚÙ[ŠBˆYˆ›ÝË™Ù]
œ™ØˆŠNˆ™]\›ˆ™\ÜÛœÙJ”ÛÛ\ˆY\šX[[˜]˜Z[X›H‹Ý]\ÏM
Bˆ\›\ÖÈœ™Øˆ—NÜÙ\H‰ˆˆYˆÈˆ[ˆ\›[ÙHÈ‚ˆžN‚ˆÝ›ÙO\™\WØž]\Ê\›
ÜÙ\
ÈšÙ^OHŠÝ\›X‹œ\œÙKœ][ÝJÖÈšÙ^H—JK[Y[Ý]LL‹™]šY\ÏL
Bˆ^Ù\^Ù\[ÛŽ‚ˆÈYˆÛÛÙÛIÜÈš\œÝÚYÛ™Y‘ÐˆT“Ý[ËÙ˜Z[Ë\ÚÈÛÛ\ˆ›ÜˆH™]ËˆÈYÚ\ˆY\šX[^Y\ˆ[™žHÛ˜ÙH[Ü™Kˆ\È™]™[ÈŒ8 $ÎLÙXÛÛ™ØZ]Ë‚ˆO]\›X‹œ\œÙK\›[˜ÛÙJÈ›ØØ][Û‹›]]YHŽœË™Ù]
›]ŠK›ØØ][Û‹›Û™Ú]YHŽœË™Ù]
›™ÈŠKˆœ˜Y]\ÓY]\œÈŽŒÌšY]ÈŽˆ’SPQÑT–WÓVQT”È‹œ™\]Z\™Y]X[]HŽˆTÑH‹ˆœ^[Ú^™SY]\œÈŽŒKšÙ^HŽœÖÈšÙ^H—_JBˆË^Y\œÏ\™\WÚœÛÛŠšÎ‹ËÜÛÛ\‹™ÛÛÙÛX\\Ë˜ÛÛKÝŒKÙ]S^Y\œÎ™Ù]ÈŠÙJBˆYˆÈOLŒÜˆ›Ý^Y\œË™Ù]
œ™Ø•\›ŠN‚ˆ˜Z\ÙH˜[YQ\œ›ÜŠ‘ÛÛÙÛHY\šX[[XYÙ\žH[˜]˜Z[X›H›Üˆ\È›Ü\HšYÚ›ÝËˆŠBˆÖÈœ™Øˆ—O[^Y\œÖÈœ™Ø•\›—BˆÈÙY\HÜšYÚ[˜[YÚ\‹Y]Z[X\ÚÈYˆ][™XYH^\ÝÎÈÛ›H\ÙHBˆÈ˜[˜XÚÈX\ÚÈÚ[ˆ›Û™HØ\È™]\›™Y[ˆHš\œÝ™\]Y\Ý‚ˆYˆ›ÝË™Ù]
›X\ÚÈŠH[™^Y\œË™Ù]
›X\ÚÕ\›ŠNˆÖÈ›X\ÚÈ—O[^Y\œË™Ù]
›X\ÚÕ\›ŠBˆ\›\ÖÈœ™Øˆ—NÜÙ\H‰ˆˆYˆÈˆ[ˆ\›[ÙHÈ‚ˆÝ›ÙO\™\WØž]\Ê\›
ÜÙ\
ÈšÙ^OHŠÝ\›X‹œ\œÙKœ][ÝJÖÈšÙ^H—JK[Y[Ý]LL‹™]šY\ÏL
BˆÖÈœ™Ø—ØØXÚH—OJÝ›ÙJBˆÝ›ÙO\ÖÈœ™Ø—ØØXÚH—NÜ™]\›ˆ™\ÜÛœÙJ›ÙKÛÛ[Ý\OXÝ
Bˆ^Ù\^Ù\[Ûˆ\ÈNœ™]\›ˆ™\ÜÛœÙJÝŠJKÝ]\ÏM
B‚\™Ù]
‹ÛX\ÚËÏÚÙ[ˆŠB™YˆX\ÚÊÚÙ[ŠN‚ˆÏTÑTÔÒSÓ”Ë™Ù]
ÚÙ[ŠBˆYˆ›ÝÈÜˆ›ÝË™Ù]
›X\ÚÈŠNœ™]\›ˆ™\ÜÛœÙJ”›ÛÙˆX\ÚÈ[˜]˜Z[X›H‹Ý]\ÏM
BˆYˆX[X[Ü›ÛÙ—ÜÙ\ÜÚ[ÛŠÊNœ™]\›ˆ™\ÜÛœÙJ“X[X[›ÛÙš[™È[XYÙ\žH[˜]˜Z[X›Kˆ™]žHHY\šX[[XYÙNÈÛÛ\ˆ™XÛÝ™\žH\È\ØX›Yˆ‹Ý]\ÏMJBˆžN‚ˆYˆÖÈ›X\Ú×ØØXÚH—H\È›Û™N‚ˆ\›\ÖÈ›X\ÚÈ—NÜÙ\H‰ˆˆYˆÈˆ[ˆ\›[ÙHÈ‚ˆÝ›ÙO\™\WØž]\Ê\›
ÜÙ\
ÈšÙ^OHŠÝ\›X‹œ\œÙKœ][ÝJÖÈšÙ^H—JJBˆÖÈ›X\Ú×ØØXÚH—OJÝ›ÙJBˆÝ›ÙO\ÖÈ›X\Ú×ØØXÚH—NÜ™]\›ˆ™\ÜÛœÙJ›ÙKÛÛ[Ý\OXÝ
Bˆ^Ù\^Ù\[Ûˆ\ÈNœ™]\›ˆ™\ÜÛœÙJÝŠJKÝ]\ÏM
B‚\™Ù]
‹ÜÝ™Y]ÏÚÙ[ˆŠB™YˆÝ™Y]
ÚÙ[ŠN‚ˆÏTÑTÔÒSÓ”Ë™Ù]
ÚÙ[ŠBˆYˆ›ÝÈÜˆ›ÝË™Ù]
œÝ™Y]ŠNœ™]\›ˆ™\ÜÛœÙJ”Ý™Y]šY]È[˜]˜Z[X›H‹Ý]\ÏM
BˆžN‚ˆYˆÖÈœÝ™Y]ØØXÚH—H\È›Û™NœÖÈœÝ™Y]ØØXÚH—O\™\WØž]\ÊÖÈœÝ™Y]—JBˆÝ›ÙO\ÖÈœÝ™Y]ØØXÚH—NÜ™]\›ˆ™\ÜÛœÙJ›ÙKÛÛ[Ý\OXÝ
Bˆ^Ù\^Ù\[Ûˆ\ÈNœ™]\›ˆ™\ÜÛœÙJÝŠJKÝ]\ÏM
B‚šYˆ×Û˜[YW×ÏOH—×ÛXZ[—×ÈŽ‚ˆÜMLL‚ˆ™XY[™Ë•[Y\ŠKŒMK[X™NÙX˜œ›ÝÜÙ\‹›Ü[Šˆš‹ËÌLËŒŒŒNžÜÜHŠJKœÝ\

Bˆš[
QT’TUSÕH“ÓÑˆQPTÕT‘SQS•	ˆTÕSPUHŠBˆš[
ˆ“Ü[š[™ÈÚ›ÛYH]‹ËÌLËŒŒŒNžÜÜHŠBˆš[
“X]™H\ÈÚ[™ÝÈÜ[ˆÚ[H\Ý[™ËˆŠBˆ\œ[ŠÜÝHŒLËŒŒŒH‹Ü\ÜXYÏQ˜[ÙK\ÙWÜ™[ØY\Q˜[ÙJB‚‚