# V11.6.85 — SELF-CONTAINED WEBSITE ROUTING
# V11.6.82 — ACCOUNT / WEBSITE SIGNUP READINESS
# V11.6.76 — FOCUSED MEASUREMENT INTERFACE
import re
# AERIQUOTE V11.6.74 — MULTI-MEASUREMENT INTERFACE
# AeriQuote V11.6.91 — SNOW REMOVAL WORKFLOW. Roofing V11.6.90 behavior preserved.
# Measurement calculations, API calls, pricing, estimates and PDF mechanics are unchanged.
from flask import Flask, request, jsonify, Response, render_template_string, session, redirect, send_from_directory
import urllib.request, urllib.parse, urllib.error
import json, webbrowser, threading, uuid, math, time, os, sqlite3, hmac, hashlib, secrets
from datetime import datetime
from activation_metrics import account_metrics, account_plan_report
from account_credits import init_credit_db, settings as credit_settings, lock_account, consume as consume_credit, register_credits, paid_usage, SUBSCRIPTION_LIMITS
from property_sessions import PropertySessions
from property_address import CANADIAN_PROVINCES, unit_address, building_address
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
MAPBOX_ACCESS_TOKEN = os.environ.get("MAPBOX_ACCESS_TOKEN", "").strip()
AERIAL_PROVIDER = os.environ.get("AERIQUOTE_AERIAL_PROVIDER", "google").strip().lower()
if AERIAL_PROVIDER not in {"google", "mapbox"}:
    raise ValueError("AERIQUOTE_AERIAL_PROVIDER must be google or mapbox")
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
    # V11.6.82 — website/signup-ready account data. Keep flexible onboarding fields in
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
.side{padding:12px}.street{width:100%;height:190px;object-fit:cover;background:#e8ece9;border-radius:9px;border:1px solid var(--line)}.section{margin-top:12px}.section h3{margin:0 0 7px;font-size:15px}.metric-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.metric{padding:9px;border:1px solid var(--line);border-radius:9px;background:#f8faf9}.metric b{display:block;font-size:18px;color:var(--green2);margin-top:2px}.structure{border:1px solid var(--line);border-radius:9px;padding:9px;margin:7px 0}.structure-head{display:flex;justify-content:space-between;gap:8px}.dot{width:9px;height:9px;border-radius:50%;display:inline-block;margin-right:6px}.house-dot{background:var(--house)}.garage-dot{background:var(--garage)}.manual-dot{background:var(--manual)}.calc{display:grid;grid-template-columns:1fr auto;gap:6px;font-size:13px}.calc div:nth-child(even){font-weight:800}.estimate{background:#f7faf8;border:1px solid var(--line);border-radius:9px;padding:10px;margin-top:9px}.line{display:flex;justify-content:space-between;gap:8px;padding:6px 0;border-bottom:1px solid #e5ece7}.line:last-child{border-bottom:0}.expandedPdfExport .structure-head>:first-child{min-width:0;overflow-wrap:anywhere}.expandedPdfExport .structure-head>:last-child{flex-shrink:0;white-space:nowrap}.reportPrice .line>:first-child,.expandedPdfExport .line>:first-child{min-width:0;overflow-wrap:anywhere}.reportPrice .line>:last-child,.expandedPdfExport .line>:last-child{flex-shrink:0;white-space:nowrap;text-align:right}.grand{font-size:17px;color:var(--green2);font-weight:900}.total{padding:11px;background:#edf7f0;border:1px solid #cde5d4;border-radius:9px;font-weight:800;margin-top:9px}.warning{padding:9px;background:var(--warn);border:1px solid #e5ca7e;border-radius:8px;color:#79520c;margin-top:8px;font-size:12px}.good{padding:9px;background:#edf7f0;border:1px solid #cde5d4;border-radius:8px;color:var(--green2);margin-top:8px;font-size:12px}.fallbackbox{display:none;background:#fff8e8;border:1px solid #e7c56f;border-radius:10px;padding:11px 12px;margin:10px 0;color:#6f4b08}.fallbackbox b{color:#5e3e05}
.dealer-settings{margin-top:10px;border:1px solid var(--line);border-radius:10px;background:#fff}.dealer-settings summary{cursor:pointer;padding:10px 12px;font-weight:800;color:var(--green2)}.settingsbody{padding:0 12px 12px}.savedmsg{padding:8px;border-radius:8px;background:#edf7f0;border:1px solid #cde5d4;color:var(--green2);font-size:12px;margin-top:8px}.usage{font-size:12px;color:var(--muted);margin-top:6px}
.dealer-branding-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:7px;margin-top:7px}.dealer-logo-tools{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:8px}.dealer-logo-preview{width:180px;height:64px;object-fit:contain;border:1px solid var(--line);border-radius:8px;background:#fff;padding:6px}.dealer-logo-note{font-size:11px;color:var(--muted);max-width:440px}.dealer-logo-clear{padding:7px 10px}.reportHead .dealerLogo{width:auto!important;height:auto!important;max-width:100%;max-height:120px;object-fit:contain;justify-self:center;transform:none;transform-origin:center center}.reportHead .dealerLogo.defaultDealerLogo{transform:none}.reportDealerSub{font-size:12px;color:#5b675f;text-align:center;margin-top:4px}.dealerContactCompact{margin-top:7px;font-size:13px;line-height:1.55}.dealerContactCompact .contactSep{opacity:.65;padding:0 7px}.dealerContactCompact #rDealerEmailWrap,.dealerContactCompact #rDealerAddressWrap,.dealerContactCompact #rPhoneWrap{display:inline-block}
.marketing-settings{margin-top:12px;border:1px solid var(--line);border-radius:10px;background:#f8fafc;padding:0}.marketing-settings>summary{cursor:pointer;padding:12px;font-weight:900;color:var(--green2);list-style-position:inside}.marketing-settings-body{padding:0 12px 12px}.marketing-toggle{display:flex;align-items:center;gap:8px;font-weight:800;margin-bottom:10px}.marketing-toggle input{width:auto}.benefit-editor{display:grid;grid-template-columns:90px 1fr 2fr;gap:7px;margin-top:7px}.marketing-cta-fields label{display:block;margin-top:8px}.marketing-cta-fields input{display:block;width:100%;margin-top:4px}.save-profile-btn.saved{background:#28612f!important;color:#fff!important}.reportHead .dealerLogo.noDealerLogo{visibility:hidden}.marketingWarranty{margin-top:8px;padding:9px 10px;border:1px solid var(--line);border-radius:8px;background:#f8faf9;font-size:13px}.marketingHidden{display:none!important}@media(max-width:800px){.benefit-editor{grid-template-columns:1fr}}
.historyModal{display:none;position:fixed;inset:0;background:#0008;z-index:6500;padding:30px;overflow:auto}.historyModal.open{display:block}.historyBox{max-width:1000px;margin:auto;background:#fff;border-radius:14px;padding:18px;box-shadow:0 16px 50px #0005}.historyHead{display:flex;justify-content:space-between;align-items:center;gap:12px}.historyResults{margin-top:14px}.historyRow{display:grid;grid-template-columns:1.15fr 2fr .75fr .75fr auto;gap:16px;align-items:center;padding:16px 10px;border-bottom:1px solid var(--line);font-size:13px}.historyRow:hover{background:#f8faf9}.historyCustomer b,.historyAddress b{font-size:14px}.historyDate,.historyAmount{white-space:nowrap}.historyActions{display:flex;gap:12px;align-items:center;justify-content:flex-end;flex-wrap:nowrap}.historyActions button{white-space:nowrap;margin:0;min-width:max-content}.historyColumns{display:grid;grid-template-columns:1.15fr 2fr .75fr .75fr auto;gap:16px;padding:10px 10px 6px;color:#66736b;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.04em;border-bottom:1px solid var(--line)}@media(max-width:800px){.historyColumns{display:none}.historyRow{grid-template-columns:1fr;gap:8px;padding:16px 6px}.historyActions{justify-content:flex-start}.historyModal{padding:10px}}
/* V11.5 dealer-simple UI only — measurement logic unchanged */
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
/* PDF CUSTOMER EXPORT — dealer editing controls are hidden and customer text is enlarged. */
.report.pdf-export{padding:14px;max-width:1320px}
.report.pdf-export .reportHead{grid-template-columns:240px 1fr 190px;gap:12px;padding-bottom:8px}
.report.pdf-export .reportHead .logo{width:220px}.report.pdf-export .reportHead .shield{width:170px}.report.pdf-export .reportHead h1{font-size:29px}
.report.pdf-export .reportMeta{margin:8px 0;gap:8px}.report.pdf-export .reportMeta div{padding:6px 8px;font-size:16px}
.report.pdf-export .reportGrid{gap:12px}.report.pdf-export .customerMap{height:430px}.report.pdf-export .reportDrawLayer{height:430px}
.report.pdf-export .reportStreet{height:205px}.report.pdf-export .reportTitle{padding:8px 10px;font-size:15px}
.report.pdf-export .reportBody{padding:10px;font-size:15px;line-height:1.25}.report.pdf-export .small{font-size:13.5px!important;line-height:1.3}
.report.pdf-export .structure,.report.pdf-export .metric{font-size:16px;line-height:1.25}
.report.pdf-export .benefit{padding:7px 0;font-size:14px;line-height:1.25}.report.pdf-export .benefitIcon{width:30px;height:30px}
.report.pdf-export .cta{padding:11px;margin-top:9px;font-size:13.5px;line-height:1.28}.report.pdf-export .cta strong{font-size:19px}
.report.pdf-export .reportPrice{margin-top:9px}.report.pdf-export .reportPrice .rphead,.report.pdf-export .reportPrice .rpbody{padding:8px 10px;font-size:16px;line-height:1.25}
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
 .reportActions,.pdfLayoutHelp{display:none!important}.estimateOutlineBar{display:none!important}
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

/* Manual main-roof tracing controls — layout only */
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

/* Dynamic manual main-roof pitch controls — layout only */
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

/* V11.6.79 — clean manual MAIN HOUSE control panel.
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
/* Manual Roofing has one stage-specific explanation; validators remain unchanged. */
.roof-guided .measure-intro,.roof-guided #jobMeasurements,.roof-guided #manualRoofWarning,.roof-guided #manualRoofHelp,.roof-guided #pitchReminder,.roof-guided #traceBanner,.roof-guided #roofSaveGuidance,.roof-guided #solarFallback,.roof-guided #quotePricingError,.roof-guided #manualRoofDetails>summary,.roof-guided #summary>.section,.roof-guided #summary>.structure,.roof-guided #summary>.warning,.roof-guided #summary>.good,.roof-guided #status.roof-task-status{display:none!important}
.roof-guided.roof-has-blocker #summary .estimate,.roof-guided.roof-has-blocker #appliedJobPrice{display:none}
.roof-guided #manualRoofDetails{border:0;background:none;margin:8px 0}
.roof-guided #manualRoofSections .structure{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.roof-guided #manualRoofSections .structure>span{flex:1;min-width:200px;font-weight:700}
.roof-guided #roofNextStep{padding:14px;border:1px solid #b9ccdd;border-radius:10px;background:#f2f7fc;margin:10px 0}
.roof-guided #roofNextStep p{margin:6px 0 10px}
.roof-guided .roof-next-action{outline:3px solid #9bc4ee;outline-offset:3px}
.roof-guided:not(.roof-property-next) #propertyActionBtn,.roof-guided:not(.roof-ready) #createEstimateBtn{background:#fff;color:#475569;border:1px solid #cbd5e1;box-shadow:none}

 .roof-guided.roof-drawing .manualrow{display:grid!important;grid-template-columns:minmax(0,260px) minmax(0,260px)!important;grid-template-areas:"pitch finish" "cancel undo" "clear clear"!important;gap:10px!important;padding:10px!important}
.roof-guided .manualrow #tracePitchControl,.roof-guided .manualrow #tracePitchControl select{width:100%!important;min-width:0!important}
.roof-guided .manualrow #clearManualBtn{width:auto!important}
.roof-guided .manualrow #manualPitchLabel{white-space:normal!important}
.roof-guided.roof-drawing #tracePitchControl{order:0}.roof-guided.roof-drawing #finishTrace{order:1;background:#1b5fb5;color:white;font-weight:800}
.roof-guided.roof-drawing #traceBtn{order:3}.roof-guided.roof-drawing #undoTraceBtn,.roof-guided.roof-drawing #clearManualBtn{order:4}
.roof-guided.roof-idle #tracePitchControl,.roof-guided.roof-idle #pitchDeg,.roof-guided.roof-idle #finishTrace,.roof-guided.roof-idle #undoTraceBtn,.roof-guided.roof-idle #clearManualBtn{display:none!important}
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
/* AeriQuote V11.6.70 — isolated Linear Measure workspace + saved total. Measurement engine unchanged. */
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
.roof-edit-handle{touch-action:none!important;cursor:move;display:flex!important;align-items:center;justify-content:center;background:transparent;border:0}.roof-edit-handle span{display:flex;align-items:center;justify-content:center;width:24px;height:24px;border:3px solid #d97706;border-radius:50%;background:#fff;color:#713f12;font-size:13px;font-weight:800;box-sizing:border-box;box-shadow:0 1px 4px #0008;pointer-events:none}
.surface-simple #jobMeasurements{display:none}.surface-simple .measure-toolbar{grid-template-columns:repeat(2,minmax(0,1fr))}.surface-simple #commercialAreaPanel{padding:12px!important;background:#fff;border-radius:10px!important}.surface-saved-area{display:grid;grid-template-columns:minmax(220px,1fr) minmax(235px,1fr) auto;gap:12px;align-items:center;padding:10px 0;border-top:1px solid #e4e9ed;margin-top:8px}.surface-saved-area .simple-actions{flex-wrap:wrap}.surface-saved-area button{font-size:12px;padding:8px}.surface-simple #areaStartBtn,.surface-simple #linearStartBtn,.surface-simple #linearSaveEditBtn{order:0}.surface-simple #areaCancelCorrectionBtn,.surface-simple #surfaceLineCancel,.surface-simple #linearCancelEditBtn{order:1}.surface-simple #areaUndoBtn,.surface-simple #linearUndoBtn{order:2}.surface-simple #areaClearBtn,.surface-simple #linearClearBtn{order:3}@media(max-width:1150px){.surface-saved-area{grid-template-columns:1fr}.surface-area-heading label{max-width:none}}.surface-area-heading,.surface-area-price{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:8px}.surface-area-heading label{flex:1;margin:0;max-width:420px}.surface-area-heading strong{white-space:nowrap}.surface-saved-area label{font-size:12px;color:#536579;font-weight:700}.surface-saved-area label input{display:block;margin-top:4px}.surface-area-price label{max-width:135px;margin:0}.surface-area-price .small{color:#39765a}.surface-simple #surfaceLineMore{margin-top:8px}.surface-simple #surfaceLineMore summary{font-size:13px;font-weight:700;color:#52677a;cursor:pointer}.surface-simple #surfaceLineMore .simple-actions{margin-top:8px}@media(max-width:600px){.surface-area-heading,.surface-area-price{flex-wrap:wrap}.surface-area-price .small{width:100%}}

.area-tool{margin:10px 0;border:1px solid #d9e3dc;border-radius:10px;background:#fbfdfc;overflow:hidden}.area-tool .area-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:11px 12px;background:#f7f5ff;border-bottom:1px solid #e6e0f5}.area-tool .area-title{font-weight:900;color:#102a43;letter-spacing:.2px}.area-tool .area-body{padding:10px 12px}.area-total{display:inline-flex;align-items:center;gap:7px;padding:8px 11px;border-radius:8px;background:#f1edff;color:#5630a5;font-weight:900;border:1px solid #d7ccf7}.area-point{width:12px;height:12px;border-radius:50%;background:#fff;border:3px solid #7357b8;box-shadow:0 1px 4px #0004}.area-label{background:#fff;border:2px solid #7357b8;border-radius:6px;padding:3px 6px;font-size:12px;font-weight:900;color:#49348a;white-space:nowrap;box-shadow:0 1px 4px #0003}.area-active #map{cursor:crosshair}

.measure-intro{display:flex;flex-direction:column;gap:3px;margin:4px 0 10px}.measure-intro b{font-size:20px;color:#102a43}.measure-intro span{color:#607080;font-size:13px}.measure-toolbar{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin:8px 0 12px}.measure-mode{min-height:70px;border:2px solid #d8e1e8;border-radius:11px;background:#fff;color:#17324d;text-align:left;padding:10px 12px;cursor:pointer}.measure-mode b{display:block;font-size:14px}.measure-mode small{display:block;margin-top:4px;color:#667788;font-weight:600}.measure-mode.active{border-color:#1677c8;background:#eef7ff;box-shadow:inset 0 0 0 1px #1677c8}.job-measurements{border:1px solid #d9e3dc;border-radius:10px;background:#fff;margin:0 0 12px;overflow:hidden}.jm-head{display:flex;justify-content:space-between;gap:10px;align-items:center;padding:9px 12px;background:#f6f8fa;border-bottom:1px solid #e4e9ed}.jm-list{display:grid;gap:0}.jm-row{display:grid;grid-template-columns:minmax(120px,1fr) auto auto;gap:10px;align-items:center;padding:9px 12px;border-top:1px solid #eef1f3}.jm-row:first-child{border-top:0}.jm-kind{font-weight:900;color:#17324d}.jm-value{font-weight:900;color:#102a43}.jm-status{font-size:11px;font-weight:800;color:#39765a;background:#edf8f1;border-radius:999px;padding:3px 7px}.jm-empty{padding:10px 12px;color:#6d7882;font-size:13px}.area-tool,.linear-tool{display:none}.measure-area .area-tool,.measure-linear .linear-tool{display:block}.measure-area .auto-only,.measure-linear .auto-only{display:none!important}.measure-auto .area-tool,.measure-auto .linear-tool{display:none}.measure-area #linearTool,.measure-linear #areaTool{display:none}.measure-area #areaTool,.measure-linear #linearTool{display:block}
/* V11.6.75 interface cleanup only — measurement engines unchanged */
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
 <div class="header"><div class="brand"><div class="brandLogoWrap"><a href="/site/" title="Back to AeriQuote website" aria-label="AeriQuote website"><img class="aeriquote-main-logo" src="/static/aeriquote-logo.png" alt="AeriQuote"></a><div id="industryBrandTag" class="industryBrandTag">ROOF MEASUREMENT &amp; ESTIMATE SOFTWARE</div></div></div><div class="header-actions" style="display:flex;gap:8px;align-items:center">{% if IS_HEAD_OFFICE %}<button type="button" class="secondary" onclick="window.location.href='/head-office/dealers'">ADMIN DASHBOARD</button>{% endif %}{% if IS_DEALER_OWNER %}<button type="button" class="secondary" onclick="window.location.href='/dealer-employees'">EMPLOYEES</button>{% endif %}<a href="{% if IS_DEALER_OWNER %}/site/pricing#extra-measurements{% else %}/site/pricing.html{% endif %}" style="display:inline-flex;align-items:center;justify-content:center;text-decoration:none;padding:11px 16px;border-radius:8px;font-weight:900;background:#f47b20;color:#fff;border:2px solid #e46d10;box-shadow:0 2px 6px #0002;white-space:nowrap">{% if IS_DEALER_OWNER %}PLANS / EXTRA MEASUREMENTS{% else %}VIEW PLANS / UPGRADE{% endif %}</a><button type="button" class="secondary" data-aq-help-topic="first-estimate">HELP / FIRST ESTIMATE</button><button type="button" class="secondary" onclick="openEstimateHistory()">PREVIOUS ESTIMATES</button><button type="button" class="ghost" onclick="window.location.href='/logout'">LOG OUT</button></div></div>
 <div class="stepbar"><div id="progress1" class="stepchip current"><strong><span class="stepnum">1</span>Property</strong>Enter address & load</div><div id="progress2" class="stepchip"><strong><span class="stepnum">2</span>Measure</strong>Choose measurement tools</div><div id="progress3" class="stepchip"><strong><span class="stepnum">3</span>Price</strong>Set this job's price</div><div id="progress4" class="stepchip"><strong><span class="stepnum">4</span>Customer</strong>Add customer details</div><div id="progress5" class="stepchip"><strong><span class="stepnum">5</span>Estimate</strong>Create customer estimate</div></div>
 <div class="setup">
  <div class="stepcard"><h2>STEP 1 — Enter the property</h2><button type="button" class="aq-context-help" data-aq-help-topic="property">Help with this step</button><div class="grid2"><div><label for="propertyCountry">Property Country</label><select id="propertyCountry" onchange="propertyCountryChanged()"><option value="CA">Canada</option><option value="US">United States</option></select><label>Property Address</label><input id="streetAddress" placeholder="Start typing the address — U.S. or Canada" value=""><div id="addressAutoStatus" class="small" style="margin-top:5px;color:#176b43;font-weight:700">City, state/province and ZIP/postal code will fill automatically when Google finds the address.</div><div id="addressParts" style="display:grid;grid-template-columns:1.2fr .55fr .8fr;gap:7px;margin-top:7px"><input id="cityTown" placeholder="City" value=""><select id="propertyProvince" aria-label="Property province or state" onchange="propertyProvinceChanged()"><option value="">Choose province / territory</option></select><input id="postalCode" placeholder="ZIP / Postal Code — filled by Google" readonly></div><input id="address" type="hidden"><div id="googleMatch" class="small" style="margin-top:5px;color:#176b43;font-weight:700"></div><div id="propertyVerify" class="small" style="display:none;margin-top:7px;font-weight:700"></div>
<details id="coordinateFallback" style="margin-top:10px;border:1px solid #d9e3dc;border-radius:9px;background:#fafcfb">
<summary style="cursor:pointer;padding:10px 12px;font-weight:900;color:#5b675f">CAN'T LOCATE THE PROPERTY? USE DROPPED PIN / COORDINATES</summary>
<div style="padding:0 12px 12px">
<label>Latitude, Longitude <span class="info-tip" tabindex="0" data-tip="Enter latitude first, then longitude. Example: 27.950575, -82.457178. You can also paste 27.950575° N, 82.457178° W. West longitude becomes negative automatically.">ⓘ</span></label>
<input id="coordinateInput" placeholder="Example: 27.950575, -82.457178">
<div class="small" style="margin-top:5px"><b>Example:</b> 27.950575, -82.457178 &nbsp;•&nbsp; Latitude first, Longitude second.</div>
<div class="simple-actions" style="margin-top:8px"><button type="button" class="secondary" onclick="loadExactCoordinates()">LOAD EXACT PIN LOCATION</button></div>
<div id="coordinateStatus" class="small" style="margin-top:6px;font-weight:700"></div>
</div></details>
</div></div><div class="simple-actions"><button id="propertyActionBtn" class="primarybig" onclick="loadProperty()">LOAD & MEASURE ROOF</button></div></div>
  <details class="dealer-settings" {% if IS_EMPLOYEE %}style="display:none"{% endif %}><summary>⚙ DEALER PROFILE / BRANDING — set once, then leave closed</summary><div class="settingsbody"><div class="savedmsg"><b>Set this up once.</b> Your company branding and optional marketing message will appear on customer estimates.</div><div class="grid3"><div><label for="dealerCountry">Country</label><select id="dealerCountry" onchange="countryChanged()"><option value="US">United States</option><option value="CA">Canada</option></select></div><div><label id="regionLabel" for="province">State</label><select id="province" onchange="provinceChanged()"><option value="AL">AL</option></select></div></div><div class="grid3"><div><label>Dealer / Contact Name</label><input id="dealerName" value=""></div><div><label>Company Name</label><input id="dealerCompany" placeholder="Your company name"></div><div><label>Dealer Phone</label><input id="dealerPhone" value=""></div></div><div class="dealer-branding-grid"><div><label>Dealer Email</label><input id="dealerEmail" type="email" placeholder="name@company.com"></div><div><label>Website</label><input id="dealerWebsite" placeholder="www.yourcompany.com"></div><div><label>Business Address</label><input id="dealerAddress" placeholder="City, State / Province"></div></div><div class="dealer-logo-tools"><div><label style="display:block;margin-bottom:4px">Dealer Logo</label><input id="dealerLogoFile" type="file" accept="image/png,image/jpeg,image/webp" onchange="dealerLogoChanged(event)"></div><img id="dealerLogoPreview" class="dealer-logo-preview" style="display:none" alt="Dealer logo preview"><button type="button" class="ghost dealer-logo-clear" onclick="clearDealerLogo()">REMOVE DEALER LOGO</button><div class="dealer-logo-note">Your logo is saved in this browser and used on the customer estimate. If no logo is uploaded, the estimate uses your company name without a fallback brand logo.</div></div><div class="grid3" style="margin-top:10px"><div><label>Default Price / sq. ft.</label><input id="price" type="number" step="0.01" value="0.85"></div><div id="coverageWrap"><label>Coverage / gallon (dealer only)</label><input id="coverage" type="number" value="330"></div><div><label>Business Type</label><select id="businessType" onchange="businessTypeChanged()"><option value="roofing">Roofing</option><option value="commercial">Commercial Properties</option><option value="snow">Snow Removal</option><option value="pressure">Pressure Washing</option><option value="paving">Paving &amp; Sealcoating</option><option value="landscaping">Landscaping</option></select><div class="small">Selected for your account. Change only if your business offers a different service.</div></div></div><div class="grid3" style="margin-top:7px"><div><label>Pricing Mode</label><select id="pricingMode" onchange="pricingChanged()"><option value="regular">Regular Price + Tax</option><option value="included">Taxes Included Promotion</option><option value="discount">Discount Promotion</option></select></div><div><label>Promotion Discount %</label><input id="discountPct" type="number" step="0.1" value="0" oninput="renderSummary()"></div></div><div class="grid3" style="margin-top:7px"><div><label id="primaryTaxLabel">Sales Tax %</label><input id="gst" type="number" step="any" aria-describedby="taxPercentHelp" value="0" oninput="renderSummary()"></div><div id="secondaryTaxWrap" style="display:none"><label>Provincial Tax %</label><input id="pst" type="number" step="any" aria-describedby="taxPercentHelp" value="0" oninput="renderSummary()"></div></div><div id="taxPercentHelp" class="small">Enter 5 for 5% (not 0.05). Enter 0 for a tax you do not charge. Decimal rates such as 7.25 are supported.</div>
<div id="warrantyShieldSettings" style="display:none;margin-top:12px"><label><input type="checkbox" id="showWarrantyShield" checked> Show warranty shield on Roofing estimates</label><div class="small">Optional. Turn this off when using your own company branding. Save your profile to keep this choice.</div><button type="button" class="ghost" onclick="useApprovedDealerLogo()">USE APPROVED BRAND LOGO</button></div>
<details id="marketingSettings" class="marketing-settings"><summary>Estimate Marketing Section</summary><div class="marketing-settings-body"><div class="small" style="margin-bottom:8px">Optional. Turn this on to add your own benefits, warranty/message and call-to-action to customer estimates.</div><label class="marketing-toggle"><input id="marketingEnabled" type="checkbox" onchange="toggleMarketingEditor()"> Show marketing section on estimates</label><div id="marketingEditor" style="display:none"><label>Section Heading</label><input id="marketingHeading" placeholder="Example: WHY CHOOSE US"><div class="small" style="margin-top:8px"><button type="button" class="secondary" id="commercialMarketingPresetButton" style="display:none;margin:10px 0" onclick="loadCommercialMarketingPreset()">LOAD 6 COMMERCIAL BENEFITS</button><b>Benefit boxes</b> — leave unused rows blank.</div><div class="benefit-editor"><select id="benefitIcon1"><option value="✓">✓ Check</option><option value="★">★ Star</option><option value="$">$ Savings</option><option value="◆">◆ Diamond</option><option value="●">● Dot</option><option value="W">W Warranty</option></select><input id="benefitTitle1" placeholder="Benefit 1 headline"><input id="benefitText1" placeholder="Short description"></div><div class="benefit-editor"><select id="benefitIcon2"><option value="✓">✓ Check</option><option value="★">★ Star</option><option value="$">$ Savings</option><option value="◆">◆ Diamond</option><option value="●">● Dot</option><option value="W">W Warranty</option></select><input id="benefitTitle2" placeholder="Benefit 2 headline"><input id="benefitText2" placeholder="Short description"></div><div class="benefit-editor"><select id="benefitIcon3"><option value="✓">✓ Check</option><option value="★">★ Star</option><option value="$">$ Savings</option><option value="◆">◆ Diamond</option><option value="●">● Dot</option><option value="W">W Warranty</option></select><input id="benefitTitle3" placeholder="Benefit 3 headline"><input id="benefitText3" placeholder="Short description"></div><div class="benefit-editor"><select id="benefitIcon4"><option value="✓">✓ Check</option><option value="★">★ Star</option><option value="$">$ Savings</option><option value="◆">◆ Diamond</option><option value="●">● Dot</option><option value="W">W Warranty</option></select><input id="benefitTitle4" placeholder="Benefit 4 headline"><input id="benefitText4" placeholder="Short description"></div><div class="benefit-editor"><select id="benefitIcon5"><option value="✓">✓ Check</option><option value="★">★ Star</option><option value="$">$ Savings</option><option value="◆">◆ Diamond</option><option value="●">● Dot</option><option value="W">W Warranty</option></select><input id="benefitTitle5" placeholder="Benefit 5 headline"><input id="benefitText5" placeholder="Short description"></div><div class="benefit-editor"><select id="benefitIcon6"><option value="✓">✓ Check</option><option value="★">★ Star</option><option value="$">$ Savings</option><option value="◆">◆ Diamond</option><option value="●">● Dot</option><option value="W">W Warranty</option></select><input id="benefitTitle6" placeholder="Benefit 6 headline"><input id="benefitText6" placeholder="Short description"></div><div class="grid2" style="margin-top:10px"><div><label>Optional Warranty / Guarantee Statement</label><textarea id="marketingWarranty" placeholder="Example: Backed by our 5-year workmanship warranty."></textarea></div><div><label>Bottom Call-to-Action</label><input id="marketingCtaHeading" placeholder="Example: READY TO GET STARTED?"><label style="margin-top:7px">Call-to-Action Message</label><input id="marketingCtaText" placeholder="Example: Contact us today to schedule your service."></div></div></div></div></details>
<div class="actions"><button id="saveDealerProfileBtn" class="save-profile-btn" type="button" onclick="saveDealerDefaults()">SAVE DEALER PROFILE & BRANDING</button></div><div id="savedMsg"></div></div></details>
  <button id="measureClicked" onclick="startGarageMode()" style="display:none" disabled></button><div class="usage" id="usageLine"></div>
 </div>
 <div id="status" class="status"></div>
 <div id="jobSummaryBar" class="job-summary-bar"><div><span class="js-label">PROPERTY</span><b id="jsProperty">No property loaded</b></div><div><span class="js-label">ROOFS</span><b id="jsRoofs">—</b></div><div><span class="js-label">TOTAL AREA</span><b id="jsArea">—</b></div><div><span class="js-label">ESTIMATE</span><b id="jsTotal">—</b></div></div>
 <div id="solarFallback" class="fallbackbox"><b>Manual Measurement Required</b><div id="solarFallbackText" class="small" style="margin-top:4px">Google does not have an automatic roof measurement for this property. Trace the shingled roof area below and confirm the roof pitch.</div><div class="small" style="margin-top:6px"><b>Important:</b> If the aerial appears older, verify the current roof layout with the homeowner or on site before sending the estimate.</div></div>
 <div class="main">
  <div class="panel"><div class="ptitle">STEP 2 — Measure the property</div><button type="button" class="aq-context-help" data-aq-help-topic="measure">Help with this step</button><div class="measure-intro"><b>What do you need to measure?</b><span>Use one tool or combine multiple measurements on the same property.</span></div><div class="measure-toolbar"><button id="toolAutoBtn" type="button" class="measure-mode active" onclick="selectMeasurementTool('auto')"><b>AUTOMEASURE</b><small>Roof • automatic</small></button><button id="toolAreaBtn" type="button" class="measure-mode" onclick="startServiceAreaTool()"><b>+ ADD AREA</b><small>Lawns • driveways • parking</small></button><button id="toolLinearBtn" type="button" class="measure-mode" onclick="selectMeasurementTool('linear')"><b>+ LINEAR</b><small>Gutters • fencing • curbing</small></button></div><div id="jobMeasurements" class="job-measurements"><div class="jm-head"><b>Measurements for This Job</b><span class="small">Saved measurements stay with the property.</span></div><div id="jobMeasurementsList" class="jm-list"></div></div>
   <div id="garageControls" class="good auto-only" style="margin:8px"><div id="garageSavedConfirm" class="good" style="display:none;margin-bottom:8px;padding:10px;border:2px solid #2f7d44;font-size:15px"></div><div class="nexthelp"><b id="garageGuide">Load the property first. Review the automatic outline if available, or trace the roof manually.</b></div><div class="simple-actions" style="margin-top:10px"><button id="measureClickedTop" class="secondary primarybig" onclick="startGarageMode()" disabled>+ ADD GARAGE / OTHER ROOF</button><button class="ghost" onclick="removeLastExtra()">UNDO LAST ADDED ROOF</button></div><div class="small" style="margin-top:7px">Only use Add Garage / Other Roof when another shingled structure should be included.</div></div>
   <div id="roofCheckCard" class="stepcard auto-only" style="margin:10px 0"><h2 style="margin-bottom:5px">Is AutoMeasure showing the correct MAIN HOUSE?</h2><div class="small">If the blue outline is on the correct main house, continue. Garage and other-roof corrections are handled separately below.</div><div class="simple-actions" style="margin-top:9px"><button class="primary" onclick="roofCheckGood()">YES — MAIN HOUSE IS CORRECT</button></div><div id="roofFixHelp" class="small" style="margin-top:7px"></div><details class="roof-advanced"><summary>ROOF CORRECTIONS / ADVANCED OPTIONS</summary><div class="roof-advanced-body"><details style="margin-top:8px"><summary>Wrong garage / extra roof included? <span class="info-tip" tabindex="0" data-tip="Use this when Google correctly measured the main house but included a garage or other roof you do not want in the quote.">ⓘ</span></summary><div class="small" style="padding:8px 0"><b>Remove only the wrong extra roof.</b> The main house stays in the quote. If you need the correct garage afterward, use <b>ADD / REMEASURE GARAGE OR OTHER ROOF</b> directly below.</div><div class="simple-actions" style="margin-top:8px"><button id="fixRoofBtn" class="ghost" onclick="toggleRoofFix()">REMOVE WRONG GARAGE / EXTRA ROOF</button></div></details><details style="margin-top:8px"><summary>Customer picture outline needs cleanup? <span class="info-tip" tabindex="0" data-tip="Picture only. Adjusting this outline does NOT change Google's square footage, pitch, or estimate price.">ⓘ</span></summary><div class="small" style="padding:8px 0">This changes the customer picture only — not square footage, pitch or price.</div><div class="simple-actions"><button id="adjustOutlineBtn" class="secondary" onclick="toggleOutlineAdjust()">ADJUST CUSTOMER OUTLINE</button><button id="finishOutlineBtn" class="primary" onclick="finishOutlineAdjust()" disabled style="display:none">FINISH OUTLINE</button><button id="undoOutlineBtn" class="ghost" onclick="undoOutlinePoint()" style="display:none">UNDO POINT</button><button id="clearOutlineBtn" class="ghost" onclick="clearAdjustedOutline()" style="display:none">USE GOOGLE OUTLINE</button></div><div id="outlineHelp" class="small" style="margin-top:7px"></div></details><details style="margin-top:12px;border-top:1px solid #d9e3dc;padding-top:9px"><summary><b>Main house measurement is wrong?</b></summary><div class="warning" style="margin-top:8px"><b>Only use this to replace the MAIN HOUSE measurement.</b> Do not use this button for a garage or other added roof.</div><div class="simple-actions" style="margin-top:8px"><button id="manualOverrideBtn" class="danger" onclick="startManualOverride()">REPLACE MAIN HOUSE MEASUREMENT</button></div></details></div></details></div><div id="commercialAreaPanel" style="display:none;padding:10px;border:1px solid #ccd7e4;border-radius:8px;margin-bottom:8px"><b>Commercial service areas</b><div id="commercialAreaList"></div><button type="button" class="secondary" id="commercialAddAreaBtn" onclick="startServiceAreaTool()">+ ADD ANOTHER SERVICE AREA</button></div><div id="areaTool" class="area-tool"><div class="area-head"><div><div class="area-title">AREA MEASURE</div><div class="small">Measure the selected service area in square feet.</div></div><div id="areaTotal" class="area-total">Area: 0 ft²</div></div><div class="area-body"><div class="simple-actions"><button id="areaCorrectBtn" type="button" class="secondary" onclick="correctAreaOutline()" style="display:none">CORRECT MEASUREMENT OUTLINE</button><button id="areaCancelCorrectionBtn" type="button" class="ghost" onclick="cancelAreaCorrection()" style="display:none">CANCEL CORRECTION</button><button id="areaStartBtn" type="button" class="secondary" onclick="toggleAreaMeasure()">START AREA MEASURE</button><button id="areaUndoBtn" type="button" class="ghost" onclick="undoAreaPoint()" style="display:none">UNDO LAST POINT</button><button id="areaClearBtn" type="button" class="ghost" onclick="clearAreaMeasure()" style="display:none">CLEAR AREA MEASUREMENT</button><button id="areaAutoBtn" type="button" class="ghost" onclick="returnAreaToAutoMeasure()" style="display:none">RETURN TO AUTOMEASURE</button></div><div id="areaHelp" class="small" style="margin-top:7px">Click Start Area Measure for a clean aerial workspace. Click around the outside edge of the service area, then save it.</div></div></div><div id="linearTool" class="linear-tool"><div class="linear-head"><div><div class="linear-title">LINEAR MEASURE</div><div class="small">Measure gutters, fencing, curbing, edging, crack sealing or any point-to-point distance.</div></div><div id="linearTotal" class="linear-total">Total: 0.0 ft</div></div><div class="linear-body"><div class="simple-actions"><button id="linearEditBtn" type="button" class="secondary" onclick="editLinearMeasure()" style="display:none">EDIT LINE</button><button id="linearSaveEditBtn" type="button" class="primary" onclick="saveLinearCorrection()" style="display:none">SAVE LINE CHANGES</button><button id="linearCancelEditBtn" type="button" class="ghost" onclick="cancelLinearCorrection()" style="display:none">CANCEL LINE EDIT</button><button id="linearStartBtn" type="button" class="secondary" onclick="toggleLinearMeasure()">START LINEAR MEASURE</button><button id="linearUndoBtn" type="button" class="ghost" onclick="undoLinearPoint()" style="display:none">UNDO LAST POINT</button><button id="linearClearBtn" type="button" class="ghost" onclick="clearLinearMeasure()" style="display:none">CLEAR LINEAR MEASUREMENT</button><button id="linearAutoBtn" type="button" class="ghost" onclick="returnToAutoMeasure()" style="display:none">RETURN TO AUTOMEASURE</button></div><div id="linearHelp" class="small" style="margin-top:7px">Click Start Linear Measure for a clean aerial workspace. Roof overlays hide while you draw. AeriQuote shows every segment and the running total. Use the measurement tools above to switch modes.</div></div></div><details id="manualRoofDetails" class="manualbox auto-only" open><summary id="manualRoofSummary">Add / Remeasure Garage or Other Roof</summary><div id="manualRoofWarning" class="warning" style="margin:8px 12px"><b>Google's confirmed MAIN HOUSE stays in the quote.</b> Use this to add or remeasure a garage, shed, addition, or other shingled roof.</div><div class="manualrow"><button id="traceBtn" class="orange" onclick="toggleTrace()">ADD / REMEASURE GARAGE OR OTHER ROOF</button><div id="tracePitchControl" class="pitch" style="display:none"><label id="manualPitchLabel" style="margin:0 0 3px" class="aeri-added-pitch-label">Pitch of Added Roof <span class="info-tip" tabindex="0" data-tip="Aerial imagery does not verify roof pitch. Independently confirm any assumed or default pitch, including 5/12. Pitch affects calculated roof area and pricing.">ⓘ</span></label><select id="pitchSel" onchange="pitchChanged()" class="pitch-select"><option value="">Select roof pitch</option><option value="18.43">4/12</option><option value="22.62" selected>5/12</option><option value="26.57">6/12</option><option value="30.26">7/12</option><option value="33.69">8/12</option><option value="36.87">9/12</option><option value="39.81">10/12</option><option value="42.51">11/12</option><option value="45">12/12</option><option value="custom">Custom°</option></select></div><input id="pitchDeg" type="hidden" value="22.62"><button id="finishTrace" class="secondary" onclick="finishTrace()" disabled style="display:none">SAVE & ADD ROOF</button><button id="undoTraceBtn" class="ghost" onclick="undoPoint()" style="display:none">UNDO LAST POINT</button><button id="clearManualBtn" class="danger" onclick="clearManual()" style="display:none">CLEAR CURRENT DRAWING</button></div><div id="pitchReminder" class="pitch-reminder"><b>Confirm the roof pitch.</b> Manual roofs start at 5/12. Independently confirm the pitch before saving; aerial imagery does not verify it. Pitch affects calculated roof area and pricing.</div><div id="manualRoofHelp" class="small" style="padding:0 12px 10px">Click around only the garage or other roof you want to add, confirm its pitch, then press SAVE & ADD ROOF. The Google main house stays unchanged.</div></details>
   <details id="advancedOptions" class="advanced"><summary>Show advanced roof display options</summary><div style="padding:8px 10px"><b>Roof Outlines:</b> <select id="outlineMode" onchange="redrawRoofData()" style="width:auto"><option value="smart">Actual Roof Outline (Recommended)</option><option value="all">Show Google segment boxes</option><option value="clean">Pitch labels only</option></select></div></details>
   <div id="aerialRoofAction" class="stepcard" hidden></div>
   <button type="button" id="widerMapboxAerial" hidden onclick="widenMapboxAerial()">Wider aerial</button>
   <div class="mapwrap"><div id="loading" class="loading" style="display:none">Loading aerial imagery…</div><div id="traceBanner" class="tracebanner">MANUAL MEASURE ON — click roof corners, then SAVE & ADD ROOF</div><div id="map"></div></div>
  </div>
  <div class="panel"><div class="ptitle">STEP 3 — Review & price</div><button type="button" class="aq-context-help" data-aq-help-topic="price">Help with this step</button><div class="side"><img id="street" class="street" alt="Actual Street View"><div id="streetMeta" class="small" style="margin-top:4px"></div><div id="jobPriceCard" class="stepcard measurement-price-card" style="margin-top:10px"><h2 id="jobPriceTitle">Price for this job</h2><label id="jobPriceLabel">Price for This Job / sq. ft. <span class="info-tip" tabindex="0" data-tip="Your dealer default loads here automatically. Change this number for any individual job and the quote recalculates immediately.">ⓘ</span></label><input id="jobPrice" type="number" step=".01" value=".95" oninput="jobPriceChanged()" onchange="jobPriceChanged()"><div id="jobPriceHelp" class="small">This is the price used for the quote. Change it anytime before creating the estimate.</div><div id="step3MeasurementRates"></div><div id="appliedJobPrice" class="good" style="margin-top:7px;padding:7px">Quote is using <b>$0.95 / sq. ft.</b></div></div><div id="estimatePeriodWrap" style="display:none;margin-top:10px"><label for="estimatePeriod">Price covers</label><select id="estimatePeriod" onchange="renderSummary()"><option value="one_time">One-time service</option><option value="visit">Per visit</option><option value="snowfall">Per snowfall</option><option value="month">Per month</option><option value="season">Per season</option><option value="year">Per year</option></select><div class="small">The calculated amount applies to this period. It is not multiplied by visits or months. Any additional services use the same period.</div></div><div id="summary"></div><div class="stepcard workflow-next"><h2>STEP 4 — Customer</h2><button type="button" class="aq-context-help" data-aq-help-topic="customer">Help with this step</button><div class="customer-grid"><div class="full"><label>Customer Name</label><input id="customerName" name="aq_job_customer_name" autocomplete="new-password" readonly onfocus="this.removeAttribute('readonly')" placeholder="Customer name" oninput="updateProgressSteps()"></div><div><label>Customer Phone</label><input id="customerPhone" name="aq_job_customer_phone" autocomplete="new-password" readonly onfocus="this.removeAttribute('readonly')" placeholder="Phone" oninput="updateProgressSteps()"></div><div><label>Customer Email</label><input id="customerEmail" name="aq_job_customer_email" autocomplete="new-password" readonly onfocus="this.removeAttribute('readonly')" type="email" placeholder="Email" oninput="updateProgressSteps()"></div><div class="full"><label>Customer / Job Notes <span class="small">(optional)</span></label><textarea id="customerNotes" name="aq_job_customer_notes" autocomplete="new-password" readonly onfocus="this.removeAttribute('readonly')" placeholder="Optional notes for this customer or job"></textarea></div></div></div><div class="stepcard workflow-next"><h2>STEP 5 — Create estimate</h2><button type="button" class="aq-context-help" data-aq-help-topic="estimate">Help with this step</button><label>Additional Services / Repairs <span class="small">(optional)</span></label><input id="extraServiceDescription" placeholder="Example: Replace damaged shingles, seal vent, minor roof repair" oninput="renderSummary()"><label style="margin-top:8px">Additional Services / Repairs Amount</label><input id="extraServiceAmount" type="number" min="0" step="0.01" value="0" oninput="renderSummary()"><div class="small" style="margin-top:5px">Added to the estimate and uses the same sales-tax setting as this job.</div><label style="margin-top:10px">Estimate images</label><select id="streetViewChoice"><option value="auto" selected>Use Aerial + Google Street View</option><option value="hide">Use Aerial + Property Assessment Placeholder</option><option value="none">Create Estimate Without Images</option></select><div class="simple-actions" style="margin-top:10px"><button id="createEstimateBtn" class="primarybig" onclick="showCustomerEstimate()" disabled>CREATE CUSTOMER ESTIMATE</button></div></div></div></div>
 </div>
</div></div>

<div id="historyModal" class="historyModal" role="dialog" aria-modal="true" aria-labelledby="historyTitle"><div class="historyBox"><div class="historyHead"><div><h2 id="historyTitle" style="margin:0;color:var(--green2)">Previous Estimates</h2><div class="small">Find and reopen a saved estimate or review its earlier versions.</div></div><button class="ghost" onclick="closeEstimateHistory()">CLOSE</button></div><div style="display:flex;gap:8px;margin-top:14px"><input id="historySearch" aria-label="Search previous estimates" placeholder="Search customer, address, phone or email" onkeydown="if(event.key==='Enter')searchEstimateHistory()"><button onclick="searchEstimateHistory()">SEARCH</button></div><div class="historyColumns"><div>Customer</div><div>Property</div><div>Date</div><div>Estimate</div><div>Actions</div></div><div id="historyResults" class="historyResults"><div class="small" style="padding:14px 0">Your saved estimates will appear here.</div></div></div></div>

<div id="trialLimitOverlay" class="trial-limit-overlay" role="dialog" aria-modal="true" aria-labelledby="trialLimitTitle"><div class="trial-limit-card"><h2 id="trialLimitTitle">You’ve Used Your 3 Free Property Measurements</h2><p>Your AeriQuote free trial included 3 property measurements and estimates.</p><p>Choose a plan to continue measuring properties and creating professional estimates.</p><div class="trial-limit-actions"><a href="/site/pricing.html">VIEW PLANS →</a><button type="button" onclick="closeTrialLimit();openEstimateHistory()">BACK TO MY ACCOUNT</button></div><p class="trial-note">No automatic billing. Choose a plan only when you're ready.</p></div></div>
<div id="reportOverlay"><div class="report" style="width:min(1320px,calc(100vw - 44px));">
 <div class="reportHead"><img id="rDealerLogo" class="logo dealerLogo noDealerLogo" alt="Dealer logo"><div><h1 id="rEstimateTitle">Property Measurement &amp; Estimate</h1><div id="rEstimateSubtitle" style="text-align:center;color:#28612f;font-weight:800;margin-top:6px"></div><div id="rEstimateDealerSub" class="reportDealerSub"></div></div><div><img id="rWarrantyShield" alt="6-Year Transferable Warranty" style="display:none;width:125px;max-width:100%;height:125px;object-fit:contain"></div></div>
 <div class="reportMeta"><div><b>Property Address</b><div id="rAddress"></div></div><div><b>Date Prepared</b><div id="rDate"></div></div><div><b>Prepared For</b><div id="rCustomerName">Homeowner</div><div id="rCustomerPhone" class="small"></div><div id="rCustomerEmail" class="small"></div></div></div>
 <div class="reportGrid"><div>
  <div class="reportPanel"><div class="reportTitle">PROPERTY ASSESSMENT</div><div class="reportMapWrap"><div id="customerMap" class="customerMap"></div><svg id="reportDrawLayer" class="reportDrawLayer" aria-label="Draw customer measurement outline"></svg></div><div id="reportOutlineControls" class="estimateOutlineBar"><div id="reportOutlineTargetButtons" style="display:flex;gap:7px;flex-wrap:wrap"></div><button id="reportCancelOutlineBtnTop" class="danger" onclick="cancelReportOutlineEdit()" style="display:none">CANCEL OUTLINE EDIT</button><button id="reportUndoOutlineBtnTop" class="ghost" onclick="undoReportOutlinePoint()" style="display:none">UNDO POINT</button><button id="reportSaveOutlineBtnTop" class="primary" onclick="saveReportOutline()" style="display:none" disabled>SAVE OUTLINE</button><button id="reportRedrawBtn" class="ghost" onclick="redrawSelectedReportMeasurement()" style="display:none">REDRAW</button><span id="reportOutlineHelpTop" class="reportEditHelp">Choose an outline to edit. Picture only — quote numbers do not change.</span></div><div id="customerMapPlaceholder" class="reportImagePlaceholder"><div><div class="big">PROPERTY ASSESSMENT</div><div style="margin-top:10px;font-weight:700">Professional property estimate prepared for this address.</div><div class="small" style="margin-top:8px">Property imagery omitted from this estimate.</div></div></div><div class="reportBody"><div id="rProperty"></div></div></div>
  <div class="reportPrice"><div class="rphead">ESTIMATE SUMMARY</div><div class="rpbody" id="rPricing"></div></div>
 </div><div>
  <div class="reportPanel"><div class="reportTitle">PROPERTY IMAGE</div><div class="reportBody">
<div id="streetPlaceholder" style="display:none;height:225px;border-radius:8px;border:1px solid #cde5d4;background:linear-gradient(135deg,#f3f7f4,#e6efe9);align-items:center;justify-content:center;text-align:center;padding:20px;color:#174f2b"><div><b style="font-size:18px">PROPERTY ASSESSMENT COMPLETED</b><br><span id="reportPropertyImageNote" class="small">Roof measured using available aerial imagery.</span></div></div>
<img id="rStreet" class="reportStreet"><div id="rStreetMeta" class="small" style="margin-top:4px"></div></div></div>
   <div id="rMarketingPanel" class="reportPanel marketingHidden" style="margin-top:12px"><div id="rMarketingHeading" class="reportTitle"></div><div id="rMarketingBenefits" class="reportBody"></div><div id="rMarketingWarranty" class="marketingWarranty marketingHidden"></div></div>
   <div class="cta"><strong id="rCtaHeading">YOUR ESTIMATE</strong><div id="rCtaText" style="margin-top:5px;color:#f59d0a;font-weight:800"></div><div style="margin-top:9px"><b id="rDealerCompany"></b></div><div id="rDealerName" style="margin-top:2px"></div><div class="dealerContactCompact"><span id="rPhoneWrap">Call or Text: <b id="rPhone"></b></span><span id="rDealerEmailWrap"><span class="contactSep">•</span><span id="rDealerEmail"></span></span><br><span id="rDealerWebsite"></span><span id="rDealerAddressWrap"><span class="contactSep">•</span><span id="rDealerAddress"></span></span></div></div>
 </div></div>
 <div class="reportFoot">Remote aerial measurements are used for estimating. Final property conditions and measurements should be confirmed before work begins.</div>
 <div class="reportActions"><span id="reportOutlineHelp" class="reportEditHelp" style="display:none"></span><label style="font-weight:700">PDF layout <select id="estimatePdfLayout" aria-label="PDF layout"><option value="single">Single page</option><option value="expanded">Expanded - aerial, then details</option>{% if VECTOR_PDF_QA_FLAG == "1" %}<option value="vector">Vector Diagram - QA only</option>{% endif %}</select></label><button id="downloadPdfBtn" class="primary" onclick="downloadEstimatePDF()">DOWNLOAD ESTIMATE PDF</button><button class="secondary" onclick="printEstimate()">PRINT ESTIMATE</button><button class="primary" onclick="startNewProperty()">NEW PROPERTY / NEXT ESTIMATE</button><button id="backToDealerBtn" class="secondary" onclick="closeReport(event)">Back to Dealer View</button></div>
 <p id="pdfLayoutHelp" class="pdfLayoutHelp" role="status" style="display:none;color:#664500;background:#fff7e6;padding:10px;border-radius:8px"></p>
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
let manualRoofEditScopeConfirmed=null;
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
const streetViewUnavailableMessage='Street View unavailable for this location. Your measurements and pricing are unchanged.';
function showStreetViewImage(image,source,caption,report=false){
 if(!image)return;
 image.onload=null;image.onerror=null;image.removeAttribute('src');
 image.dataset.streetUnavailable=source?'0':'1';
 const meta=el(report?'rStreetMeta':'streetMeta');
 const unavailable=()=>{
  image.dataset.streetUnavailable='1';
  if(report){image.style.display='none';if(el('streetPlaceholder'))el('streetPlaceholder').style.display='flex';if(el('reportPropertyImageNote'))el('reportPropertyImageNote').textContent=streetViewUnavailableMessage}
  else image.style.visibility='hidden';
  if(meta)meta.textContent=streetViewUnavailableMessage;
 };
 if(!source){unavailable();return}
 image.onload=()=>{image.dataset.streetUnavailable='0';if(report){image.style.display='block';if(el('streetPlaceholder'))el('streetPlaceholder').style.display='none'}else image.style.visibility='visible';if(meta)meta.textContent=caption||'Google Street View'};
 image.onerror=unavailable;
 if(meta)meta.textContent=caption||'Loading Google Street View…';
 image.src=source;
}

let savedEstimateEditContext=null,savedPropertyEditActive=false,savedJobDetails=null;
let exactPinDisplay=false;
let estimateOpenInProgress=false,customerMapBuildTimer=null,pdfInProgress=false;
let usage={property:0,structures:0,reports:0,saved:0,area:0,linear:0};
let lastHistorySaveKey='';

const legend=L.control({position:'bottomright'});legend.onAdd=()=>{const d=L.DomUtil.create('div');d.style.cssText='background:white;padding:7px 9px;border-radius:7px;box-shadow:0 1px 5px #0003;font-size:11px;line-height:1.5';d.innerHTML='<b>Roof Segments</b><br>Blue = Main House<br>Teal = Extra Structure<br>Gold = Pitch';return d};legend.addTo(map);if(legend.getContainer())legend.getContainer().classList.add('roof-legend');
map.on('click',e=>{if(areaMode){addAreaPoint(e.latlng);return}if(linearMode){addLinearPoint(e.latlng);return}if(outlineEditMode){addOutlinePoint(e.latlng);return}if(traceMode){if(manualRoofEditIndex!==null){status('Drag an existing roof corner to adjust this section. Save the changes or Cancel to restore it.','warn');return}addTracePoint(e.latlng);return}if(roofFixMode){removeClickedExtraRoof(e.latlng);return}if(locateRoofMode){retryRoofAt(e.latlng);return}if(!garageMode)return;clicked=e.latlng;if(clickMarker)clickMarker.remove();clickMarker=L.marker(e.latlng).addTo(map).bindPopup('Measuring selected roof…').openPopup();garageMode=false;measureClicked();});

function el(id){return document.getElementById(id)}function fmt(n){return Math.round(Number(n||0)).toLocaleString()}function currencyCode(){return (el('dealerCountry')?.value||'US')==='CA'?'CAD':'USD'}function money(n){const c=currencyCode();return new Intl.NumberFormat(c==='CAD'?'en-CA':'en-US',{style:'currency',currency:c}).format(Number(n||0))}function status(t,k=''){if(currentBusinessType()==='snow')t=translateSnowText(String(t));const surface=['commercial','paving','pressure','landscaping','snow'].includes(currentBusinessType());if(surface)t=String(t).replace(/AutoMeasure remains hidden until you return to it\.?/gi,'Your service measurement has been saved.').replace(/Roof AutoMeasure is not included in this service-area quote\.?/gi,'Only the selected service measurements are included in this quote.');el('status').textContent=t;el('status').className='status '+k;if(manualRoofQa())syncRoofNextAction()}function showLoad(v){el('loading').style.display=v?'block':'none'}
const AERIQUOTE_US_STATES=`<option value="AL">AL</option><option value="AK">AK</option><option value="AZ">AZ</option><option value="AR">AR</option><option value="CA">CA</option><option value="CO">CO</option><option value="CT">CT</option><option value="DE">DE</option><option value="FL">FL</option><option value="GA">GA</option><option value="HI">HI</option><option value="ID">ID</option><option value="IL">IL</option><option value="IN">IN</option><option value="IA">IA</option><option value="KS">KS</option><option value="KY">KY</option><option value="LA">LA</option><option value="ME">ME</option><option value="MD">MD</option><option value="MA">MA</option><option value="MI">MI</option><option value="MN">MN</option><option value="MS">MS</option><option value="MO">MO</option><option value="MT">MT</option><option value="NE">NE</option><option value="NV">NV</option><option value="NH">NH</option><option value="NJ">NJ</option><option value="NM">NM</option><option value="NY">NY</option><option value="NC">NC</option><option value="ND">ND</option><option value="OH">OH</option><option value="OK">OK</option><option value="OR">OR</option><option value="PA">PA</option><option value="RI">RI</option><option value="SC">SC</option><option value="SD">SD</option><option value="TN">TN</option><option value="TX">TX</option><option value="UT">UT</option><option value="VT">VT</option><option value="VA">VA</option><option value="WA">WA</option><option value="WV">WV</option><option value="WI">WI</option><option value="WY">WY</option><option value="DC">DC</option>`;
const AERIQUOTE_CA_PROVINCES=`<option value="AB">AB — Alberta</option><option value="BC">BC — British Columbia</option><option value="MB">MB — Manitoba</option><option value="NB">NB — New Brunswick</option><option value="NL">NL — Newfoundland and Labrador</option><option value="NS">NS — Nova Scotia</option><option value="NT">NT — Northwest Territories</option><option value="NU">NU — Nunavut</option><option value="ON">ON — Ontario</option><option value="PE">PE — Prince Edward Island</option><option value="QC">QC — Quebec</option><option value="SK">SK — Saskatchewan</option><option value="YT">YT — Yukon</option>`;
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
 roofing:{area:'Roof footprints • flat areas',linear:'Gutters • eaves • ridges',distance:'Measure gutters, eaves, ridges or other roof work priced by length.'},
 snow:{area:'Driveways • parking lots • service areas',linear:'Sidewalks • curbs • access runs',distance:'Measure sidewalks, curbs and access routes priced by length.'},
 pressure:{area:'Driveways • patios • sidewalks • parking',linear:'Gutters • fencing • cleaning runs',distance:'Measure gutters, fencing or other cleaning work priced by length.'},
 paving:{area:'Driveways • parking lots • paved areas',linear:'Curbing • edging • crack sealing',distance:'Measure curbing, edging and crack sealing priced by length.'},
 landscaping:{area:'Lawns • sod • garden beds • patios',linear:'Edging • borders • retaining walls',distance:'Measure edging, borders and retaining walls priced by length.'},
 commercial:{area:'Parking lots • walkways • grounds',linear:'Curbs • fencing • access routes',distance:'Measure curbs, fencing and other commercial services priced by length.'}
};
const _aeriOriginalText=new WeakMap();
const _aeriOriginalAttributes=new WeakMap();
function requestedBusinessType(){const value=new URLSearchParams(window.location.search).get('industry');return ['roofing','snow','pressure','paving','landscaping','commercial'].includes(value)?value:''}
function currentBusinessType(){const selected=(el('businessType')&&el('businessType').value)||'';const requested=new URLSearchParams(window.location.search).get('industry');return requested==='commercial'&&!quoteSnapshot?.savedPricing?'commercial':(selected||requested||'roofing')}
function translateSnowText(t){
 const rules=[
  [/Additional Services \/ Repairs/gi,'Additional Snow Services'],
  [/Main house measured\./gi,'Primary service area measured.'],
  [/Main house measurement is wrong\?/gi,'Primary service area measurement is wrong?'],
  [/MAIN HOUSE/g,'PRIMARY SERVICE AREA'],[/Main House/g,'Primary Service Area'],[/main house/g,'primary service area'],
  [/Choose which area outline to edit\.[\s\S]*?Picture only — measurements and price stay unchanged\./gi,'Choose which service area outline to edit. Primary and additional service areas can be edited separately. Picture only — measurements and price stay unchanged.'],
  [/Google(?:'|’|&#x27;)s confirmed PRIMARY SERVICE AREA stays in the quote\./gi,'The confirmed PRIMARY SERVICE AREA stays in the quote.'],
  [/Google(?:'|’|&#x27;)s confirmed primary service area stays in the quote\./gi,'The confirmed primary service area stays in the quote.'],
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
  [/Google Automatic Measurement — automatic area measurement/gi,'Automatic Area Measurement'],
  [/ROOF/g,'AREA'],[/Roof/g,'Area'],[/roof/g,'area']
 ];
 let out=t;for(const [a,b] of rules)out=out.replace(a,b);return out
}

function polishRoofingManualTraceControls(){
 if(currentBusinessType()!=='roofing')return;
 const leaves=Array.from(document.querySelectorAll('body *')).filter(x=>!x.children.length && !['SCRIPT','STYLE','OPTION'].includes(x.tagName));
 const pitchLabel=leaves.find(x=>(x.textContent||'').trim()==='Pitch of Added Roof ⓘ') ||
                  leaves.find(x=>/^Pitch of Added Roof/i.test((x.textContent||'').trim()));
 if(!pitchLabel)return;
 pitchLabel.textContent='Pitch of Main Roof ⓘ';
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
 [/Roof • automatic/gi,'Roof • automatic (Roofing only)'],
 [/Lawns • driveways • parking/gi,'Driveways • patios • sidewalks • parking'],
 [/ROOFS IN QUOTE/gi,'SURFACES IN QUOTE'],
 [/Roofs in Quote/gi,'Surfaces in Quote'],
 [/Google Roof Area/gi,'Measured Surface Area'],
 [/Main house will measure automatically/gi,'Select Area Measurement to outline the surface'],
 [/Review the automatic outline if available, or trace the roof manually/gi,'Select Area Measurement to outline the surface'],
 [/Finish the manual roof trace first/gi,'Finish and save a surface-area measurement first'],
 [/Trace the shingled roof around the customer property pin to unlock pricing and the customer estimate/gi,'Outline and save the cleaning surface to unlock pricing and the customer estimate'],
 [/Additional Services \/ Repairs/gi,'Additional Cleaning Services'],
 [/Example: Replace damaged shingles, seal vent, minor roof repair/gi,'Example: Additional patio, sidewalk or driveway cleaning']
 ];let v=t;for(const [re,to] of rules)v=v.replace(re,to);return v;
}
function translatePavingText(t){return translatePressureText(t).replace(/Gutters • fencing • curbing/g,'Curbing • edging • crack sealing').replace(/Additional Cleaning Services/g,'Additional Paving & Sealcoating Services').replace(/cleaning surface/gi,'paved surface').replace(/cleaning surfaces/gi,'paved surfaces').replace(/cleaning/gi,'paving & sealcoating');}
function translateLandscapingText(t){return translatePressureText(t).replace(/Driveways • patios • sidewalks • parking/g,'Lawns • sod • garden beds • patios').replace(/Gutters • fencing • curbing/g,'Edging • borders • retaining walls').replace(/Additional Cleaning Services/g,'Additional Landscaping Services').replace(/cleaning surface/gi,'landscaping area').replace(/cleaning surfaces/gi,'landscaping areas').replace(/cleaning/gi,'landscaping');}
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
 if(mode==='roofing'&&roofRemeasureTarget){if(el('manualPitchLabel'))el('manualPitchLabel').childNodes[0].nodeValue='Roof pitch — defaults to 5/12; change if needed ';if(el('manualRoofSummary'))el('manualRoofSummary').textContent='Replace measurement — '+roofRemeasureTarget.label;if(el('manualRoofWarning'))el('manualRoofWarning').textContent='Editing '+roofRemeasureTarget.label+' only. Its saved measurement stays unchanged until the replacement is saved.';if(el('clearManualBtn'))el('clearManualBtn').textContent='CLEAR THIS ROOF DRAWING'}
 const intro=document.querySelector('.measure-intro span');if(intro)intro.textContent=mode==='roofing'?(manualRoofQa()?"Load property → Trace roof → Confirm pitch → Price → Save. Trace different pitches as separate sections.":"Review an available automatic roof outline and confirm the pitch, or trace manually when needed. Use Area for flat footprints or Linear for lengths. Then apply your pricing and create a branded estimate."):'Use one tool or combine multiple measurements on the same property.';
 const copy=AERI_TOOL_COPY[mode]||AERI_TOOL_COPY.roofing;
 const areaToolButton=el('toolAreaBtn'),linearToolButton=el('toolLinearBtn');
 if(areaToolButton){areaToolButton.querySelector('b').textContent=manualRoofQa()?'TRACE ROOF':'+ ADD AREA';areaToolButton.querySelector('small').textContent=manualRoofQa()?'Roof sections • confirmed pitch':copy.area;}
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
   if(!snow && tx==='Service — Main House')x.textContent='Roofing Service — Main House';
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
     else if(/Main house and added areas can be edited separately/i.test(tx))x.textContent='Choose which service area outline to edit. Primary and additional service areas can be edited separately. Picture only — measurements and price stay unchanged.';
     else if(/^Service — Primary Service Area$/i.test(tx))x.textContent='Snow Removal Service — Primary Service Area';
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
   const areaBtn=el('toolAreaBtn'); if(areaBtn){areaBtn.querySelector('b').textContent='+ ADD AREA';areaBtn.querySelector('small').textContent='Driveways • parking lots • service areas'}
   const linearBtn=el('toolLinearBtn'); if(linearBtn){linearBtn.querySelector('b').textContent='LINEAR';linearBtn.querySelector('small').textContent='Sidewalks • curbs • access runs'}
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

function pressureMarketingDefaults(){return {heading:'WHY CHOOSE US',warranty:'',cta:'Schedule Your Pressure Washing Service',message:'Contact us to schedule professional pressure washing for your property.',benefits:[{icon:'✓',title:'Professional Cleaning',text:'Pressure washing tailored to your exterior surfaces.'},{icon:'✓',title:'Improve Curb Appeal',text:'Help remove built-up dirt and grime from driveways, patios and walkways.'},{icon:'$',title:'Clear Upfront Pricing',text:'Your estimate shows the measured cleaning area and pricing before work begins.'},{icon:'◆',title:'Property-Specific Service',text:'Cleaning areas and pricing are prepared for your individual property.'},{icon:'✓',title:'Reliable Service',text:'Professional pressure washing for your property.'}]}}
function pavingMarketingDefaults(){return {heading:'WHY CHOOSE US',warranty:'',cta:'Schedule Your Paving & Sealcoating Service',message:'Contact us to discuss paving, asphalt repair or sealcoating for your property.',benefits:[{icon:'✓',title:'Surface Preparation',text:'Every paving and sealcoating estimate is tailored to the condition of your surface.'},{icon:'✓',title:'Protect Asphalt Surfaces',text:'Sealcoating can help protect suitable asphalt surfaces from weathering and wear.'},{icon:'$',title:'Clear Upfront Pricing',text:'Your estimate clearly shows measured work areas and pricing.'},{icon:'◆',title:'Property-Specific Service',text:'Driveways and parking areas are measured for your individual property.'},{icon:'✓',title:'Professional Service',text:'Paving and sealcoating work planned around your property needs.'}]}}
function snowMarketingDefaults(){return {heading:'WHY CHOOSE US',warranty:'',cta:'Schedule Your Snow Removal Service',message:'Contact us to schedule snow removal service for your property.',benefits:[{icon:'✓',title:'Reliable Service',text:'Dependable snow removal service tailored to your property.'},{icon:'✓',title:'Help Keep Properties Safe',text:'Help keep parking lots, driveways and walkways clear and accessible.'},{icon:'$',title:'Clear Upfront Pricing',text:'Your estimate clearly shows the service areas and pricing before work begins.'},{icon:'◆',title:'Property-Specific Service',text:'Service areas and pricing are prepared for your individual property.'},{icon:'✓',title:'Detailed Written Estimate',text:'Review the included work, measured quantities and pricing.'}]}}
function landscapingMarketingDefaults(){return {heading:'WHY CHOOSE OUR LANDSCAPING SERVICE',warranty:'',cta:'READY TO IMPROVE YOUR OUTDOOR SPACE?',message:'Contact us to schedule your landscaping project.',benefits:[{icon:'✓',title:'Accurate Property Measurements',text:'Measured service areas for a clear estimate.'},{icon:'★',title:'Tailored Landscaping',text:'Lawns, sod, garden beds, patios and walkways.'},{icon:'$',title:'Clear Upfront Pricing',text:'Square-foot and linear-foot pricing.'},{icon:'◆',title:'Property-Specific Service',text:'Project scope tailored to your outdoor space.'},{icon:'✓',title:'Professional Service',text:'Careful lawn and landscape work.'},{icon:'★',title:'Reliable & Dependable Service',text:'Professional service from estimate through completion.'}]}}
function applySnowMarketingDefaultsIfNeeded(force=false){if(!['snow','pressure','paving','landscaping'].includes(currentBusinessType())||(!force&&el('marketingEnabled')?.checked===false))return;const d=currentBusinessType()==='landscaping'?landscapingMarketingDefaults():(currentBusinessType()==='paving'?pavingMarketingDefaults():(currentBusinessType()==='pressure'?pressureMarketingDefaults():snowMarketingDefaults())),roofWords=/roof|shingle|transferable warranty|protect your investment|property-specific assessment/i;const fields=[el('marketingWarranty')?.value,el('marketingCtaHeading')?.value,el('marketingCtaText')?.value,...[1,2,3,4,5,6].flatMap(n=>[el('benefitTitle'+n)?.value,el('benefitText'+n)?.value])].filter(Boolean).join(' ');const empty=!fields.trim();const wrongIndustry=['pressure','paving'].includes(currentBusinessType())&&/snow removal|snow service|keep parking lots|walkways clear/i.test(fields)||currentBusinessType()==='paving'&&/pressure washing|professional cleaning|curb appeal/i.test(fields);if(!(force||empty||roofWords.test(fields)||wrongIndustry))return;if(el('marketingEnabled'))el('marketingEnabled').checked=true;if(el('marketingHeading'))el('marketingHeading').value=d.heading;if(el('marketingWarranty')){el('marketingWarranty').value=d.warranty;el('marketingWarranty').placeholder='Optional: Add your company service guarantee or satisfaction policy.';}if(el('marketingCtaHeading'))el('marketingCtaHeading').value=d.cta;if(el('marketingCtaText'))el('marketingCtaText').value=d.message;d.benefits.forEach((b,j)=>{const n=j+1;if(el('benefitIcon'+n))el('benefitIcon'+n).value=b.icon;if(el('benefitTitle'+n))el('benefitTitle'+n).value=b.title;if(el('benefitText'+n))el('benefitText'+n).value=b.text});toggleMarketingEditor()}
function loadCommercialMarketingPreset(){
 if(currentBusinessType()!=='commercial'){alert('Select Commercial Properties under Business Type first.');return;}
 const defaults=[
  ['✓','Clear Upfront Pricing','Review measured areas and pricing before work begins.'],
  ['◆','Property-Specific Planning','Service areas and scope tailored to your property.'],
  ['✓','Professional Service','A clear plan for your commercial property project.'],
  ['★','Flexible Scheduling','Coordinate work around your property operations.'],
  ['✓','Detailed Estimate','Review project scope, quantities and pricing in one estimate.'],
  ['●','Clear Communication','Know what work is included before approving the project.']
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
  ['✓','Clear Upfront Pricing','Review measured areas and pricing before work begins.'],
  ['◆','Property-Specific Planning','Service areas and scope tailored to your property.'],
  ['✓','Professional Service','A clear plan for your commercial property project.'],
  ['★','Flexible Scheduling','Coordinate work around your property operations.'],
  ['✓','Detailed Estimate','Review project scope, quantities and pricing in one estimate.'],
  ['●','Clear Communication','Know what work is included before approving the project.']
 ]:[
  ['✓','Clear Upfront Pricing','Review the project scope and price before work begins.'],
  ['◆','Property-Specific Assessment','We assess each property and tailor the estimate to the work required.'],
  ['✓','Professional Service','A clear service plan from assessment through completion.'],
  ['★','Convenient Scheduling','Coordinate service at a time that works for your property.'],
  ['✓','Detailed Written Estimate','Review the included work, measured quantities and pricing.'],
  ['●','Clear Communication','Know what work is included before approving the project.']
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
  {icon:'✓',title:'Clear Upfront Pricing',text:'Review measured areas and pricing before work begins.'},
  {icon:'◆',title:'Property-Specific Planning',text:'Service areas and scope tailored to your property.'},
  {icon:'✓',title:'Professional Service',text:'A clear plan for your commercial property project.'},
  {icon:'★',title:'Flexible Scheduling',text:'Coordinate work around your property operations.'},
  {icon:'✓',title:'Detailed Estimate',text:'Review project scope, quantities and pricing in one estimate.'},
  {icon:'●',title:'Clear Communication',text:'Know what work is included before approving the project.'}
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
if(requestedBusinessType()&&el('businessType'))el('businessType').value=requestedBusinessType();
function captureIndustryMarketing(){return {marketingEnabled:!!el('marketingEnabled')?.checked,marketingHeading:el('marketingHeading')?.value||'',marketingWarranty:el('marketingWarranty')?.value||'',marketingCtaHeading:el('marketingCtaHeading')?.value||'',marketingCtaText:el('marketingCtaText')?.value||'',benefits:[1,2,3,4,5,6].map(n=>({icon:el('benefitIcon'+n)?.value||'✓',title:el('benefitTitle'+n)?.value||'',text:el('benefitText'+n)?.value||''}))}}
function switchIndustryMarketing(){
 const industry=currentBusinessType();
 if(marketingIndustry===industry)return;
 if(marketingIndustry)industryMarketingDrafts.set(marketingIndustry,captureIndustryMarketing());
 let draft=industryMarketingDrafts.get(industry);
 if(!draft){
  const d=industry==='snow'?snowMarketingDefaults():industry==='pressure'?pressureMarketingDefaults():industry==='paving'?pavingMarketingDefaults():industry==='landscaping'?landscapingMarketingDefaults():{
   heading:'WHY CHOOSE US',warranty:'',cta:industry==='roofing'?'Schedule Your Roofing Service':'Ready to Get Started?',message:industry==='roofing'?'Contact us to discuss roofing services for your property.':'Contact us to discuss your commercial property and request scheduling.',benefits:[{icon:'✓',title:industry==='roofing'?'Professional Roofing':'Commercial Property Services',text:industry==='roofing'?'Roofing services tailored to your property.':'Services tailored to your commercial property.'},{icon:'$',title:'Clear Upfront Pricing',text:'Review measured quantities and pricing before work begins.'},{icon:'◆',title:'Property-Specific Planning',text:'Review the included work and service scope for your property.'}]
  };
  draft={marketingEnabled:true,marketingHeading:d.heading,marketingWarranty:d.warranty,marketingCtaHeading:d.cta,marketingCtaText:d.message,benefits:Array.from({length:6},(_,i)=>d.benefits[i]||{icon:'✓',title:'',text:''})};
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
 const d={logoData:dealerLogoSrc(),showWarrantyShield:!!el("showWarrantyShield")?.checked,name:el('dealerName').value,company:el('dealerCompany')?el('dealerCompany').value:'',email:el('dealerEmail')?el('dealerEmail').value:'',website:el('dealerWebsite')?el('dealerWebsite').value:'',address:el('dealerAddress')?el('dealerAddress').value:'',price:el('price').value,coverage:el('coverage').value,country:el('dealerCountry')?el('dealerCountry').value:'US',businessType:el('businessType')?el('businessType').value:'roofing',province:el('province').value,pricingMode:el('pricingMode').value,discountPct:el('discountPct').value,gst:el('gst').value,pst:el('pst').value,phone:el('dealerPhone').value,marketingEnabled:!!el('marketingEnabled')?.checked,marketingHeading:el('marketingHeading')?.value||'',marketingWarranty:el('marketingWarranty')?.value||'',marketingCtaHeading:el('marketingCtaHeading')?.value||'',marketingCtaText:el('marketingCtaText')?.value||'',benefits:[1,2,3,4,5,6].map(n=>({icon:el('benefitIcon'+n)?.value||'✓',title:el('benefitTitle'+n)?.value||'',text:el('benefitText'+n)?.value||''}))};
 d.email=d.email.trim();if(!validDealerProfileEmail(d.email)){el('savedMsg').textContent='Enter a valid dealer email address, such as name@company.com. Your saved profile is unchanged.';el('dealerEmail')?.focus?.();return false;}
 dealerProfileSaveInProgress=true;
 const sb=el('saveDealerProfileBtn'),buttonText=sb?.textContent||'SAVE DEALER PROFILE & BRANDING';
 if(sb){sb.disabled=true;sb.textContent='SAVING…'}
 try{
  const response=await fetch('/api/account/profile',{method:'POST',headers:{'Content-Type':'application/json','X-AeriQuote-Account':el('aqAccountId')?.dataset?.accountId||''},body:JSON.stringify(d)});
  const result=await response.json().catch(()=>null);
  if(!response.ok||result?.ok!==true){const error=new Error(result?.error||'Profile save was not confirmed.');error.status=response.status;throw error}
  dealerLogoDirty=false;
  try{localStorage.setItem('sxDealerDefaults',JSON.stringify(d))}catch(e){}
  const savedPrice=parseFloat(d.price);if(Number.isFinite(savedPrice)&&savedPrice>=0&&el('jobPrice'))el('jobPrice').value=savedPrice.toFixed(2);const ds=document.querySelector('details.dealer-settings');if(ds)ds.open=true;const ms=el('marketingSettings');if(ms)ms.open=false;applyBusinessTerminology();renderSummary();el('savedMsg').innerHTML=`<div class="savedmsg"><b>✓ Dealer profile & branding saved.</b> Current quote updated to <b>${money(savedPrice)} / sq. ft.</b>. Your company information and marketing choices will appear on customer estimates.</div>`;
  return true;
 }catch(e){
  el('savedMsg').textContent=e.status===409?'Profile not saved. '+e.message:'Profile not saved. Your entries are still here. Check your connection or sign-in, then click SAVE DEALER PROFILE & BRANDING to retry.';
  return false;
 }finally{
  dealerProfileSaveInProgress=false;
  if(sb){sb.disabled=false;sb.textContent=buttonText}
 }
}
function applyOnboardingMarketing(d){if(!d)return;marketingIndustry=d.businessType||currentBusinessType();const warranty=(d.marketingWarranty||d.warrantyStatement||'').trim(),msg=(d.marketingCtaText||d.estimateMessage||'').trim(),cta=(d.marketingCtaHeading||d.ctaHeading||'').trim();const enabled=d.marketingEnabled===false?false:((d.marketingEnabled===true)||!!warranty||!!msg);if(el('marketingEnabled'))el('marketingEnabled').checked=enabled;if(el('marketingHeading'))el('marketingHeading').value=d.marketingHeading||'WHY CHOOSE US';if(el('marketingWarranty'))el('marketingWarranty').value=warranty;if(el('marketingCtaHeading'))el('marketingCtaHeading').value=cta||'Ready to Get Started?';if(el('marketingCtaText'))el('marketingCtaText').value=msg;(d.benefits||[]).slice(0,6).forEach((b,j)=>{const n=j+1;if(el('benefitIcon'+n))el('benefitIcon'+n).value=b.icon||'✓';if(el('benefitTitle'+n))el('benefitTitle'+n).value=b.title||'';if(el('benefitText'+n))el('benefitText'+n).value=b.text||''});}function clearNewJobCustomer(){if(savedEstimateEditContext||sessionToken||clearNewJobCustomer.preserve)return;['customerName','customerPhone','customerEmail','customerNotes'].forEach(id=>{const n=el(id);if(n){n.value='';n.setAttribute('readonly','readonly')}});updateProgressSteps();}
function prepareAccountBrandingCache(accountId){
 if(!accountId||dealerBrandingAccount===accountId)return;
 dealerBrandingAccount=accountId;dealerLogoData=null;dealerLogoDirty=false;
 try{if(localStorage.getItem('aqBrandingAccount')!==accountId){localStorage.removeItem('sxDealerDefaults');applyDealerLogo('',false);localStorage.setItem('aqBrandingAccount',accountId)}}catch(e){dealerLogoData=''}
}
document.addEventListener('input',event=>{if(['customerName','customerPhone','customerEmail','customerNotes'].includes(event.target?.id))clearNewJobCustomer.preserve=true;});
function loadDealerDefaults(){prepareAccountBrandingCache(el('aqAccountId')?.dataset.accountId||'');const logoRevision=dealerLogoRevision;fetch('/api/account/profile').then(r=>r.ok?r.json():null).then(a=>{if(!a)return;applyWarrantyAccount(a);if(sessionToken||linearMode||areaMode||savedEstimateEditContext)return;const d=a.profile||{};if(!Object.keys(d).length)return;try{localStorage.setItem('sxDealerDefaults',JSON.stringify(d))}catch(e){};if(!dealerLogoDirty&&logoRevision===dealerLogoRevision)applyDealerLogo(d.logoData||'',false);if(d.name!==undefined&&el('dealerName'))el('dealerName').value=d.name;if(d.company!==undefined&&el('dealerCompany'))el('dealerCompany').value=d.company;if(d.email!==undefined&&el('dealerEmail'))el('dealerEmail').value=d.email;if(d.phone!==undefined&&el('dealerPhone'))el('dealerPhone').value=d.phone;if(d.website!==undefined&&el('dealerWebsite'))el('dealerWebsite').value=d.website;if(d.address!==undefined&&el('dealerAddress'))el('dealerAddress').value=d.address;if(el('dealerCountry'))el('dealerCountry').value=(['CA','CANADA'].includes(String(d.country||'').toUpperCase())?'CA':'US');if(el('businessType')&&!industryChosenByUser)el('businessType').value=requestedBusinessType()||(d.businessType||a.industry||'roofing');if(['pressure','paving','landscaping','commercial'].includes(currentBusinessType())&&measurementViewMode==='auto'&&pendingMeasurementMode==='auto'){measurementViewMode='area';pendingMeasurementMode='area';updatePropertyActionButton();}applyBusinessTerminology();countryChanged(false);['price','coverage','province','pricingMode','discountPct','gst','pst'].forEach(id=>{if(d[id]!==undefined&&el(id))el(id).value=id==='price'?(d.pricingMethod==='manual'?'':currentBusinessType()==='pressure'&&!(parseFloat(d[id])>0)?'0.70':d[id]):d[id]});if(d.pricingMethod==='manual'&&el('commercialLinearRate'))el('commercialLinearRate').value='';if(d.price!==undefined&&el('jobPrice'))el('jobPrice').value=d.pricingMethod==='manual'?'':currentBusinessType()==='pressure'&&!(parseFloat(d.price)>0)?'0.70':d.price;if(!industryChosenByUser||currentBusinessType()===(d.businessType||a.industry||'roofing'))applyOnboardingMarketing(d);applySnowMarketingDefaultsIfNeeded(false);fillLandscapingBenefits();toggleMarketingEditor();pricingChanged();renderSummary()}).catch(()=>{});try{const d=JSON.parse(localStorage.getItem('sxDealerDefaults')||'null');if(d){if(d.name!==undefined&&el('dealerName'))el('dealerName').value=d.name;if(d.company!==undefined&&el('dealerCompany'))el('dealerCompany').value=d.company;if(d.email!==undefined&&el('dealerEmail'))el('dealerEmail').value=d.email;if(d.website!==undefined&&el('dealerWebsite'))el('dealerWebsite').value=d.website;if(d.address!==undefined&&el('dealerAddress'))el('dealerAddress').value=d.address;if(d.phone!==undefined&&el('dealerPhone'))el('dealerPhone').value=d.phone;if(el('dealerCountry'))el('dealerCountry').value=(['CA','CANADA'].includes(String(d.country||'').toUpperCase())?'CA':'US');if(el('businessType')&&!industryChosenByUser)el('businessType').value=requestedBusinessType()||(d.businessType||'roofing');countryChanged(false);['price','coverage','province','pricingMode','discountPct','gst','pst'].forEach(id=>{if(d[id]!==undefined&&el(id))el(id).value=id==='price'?(d.pricingMethod==='manual'?'':currentBusinessType()==='pressure'&&!(parseFloat(d[id])>0)?'0.70':d[id]):d[id]});if(d.pricingMethod==='manual'&&el('commercialLinearRate'))el('commercialLinearRate').value='';if(d.price!==undefined&&el('jobPrice'))el('jobPrice').value=d.pricingMethod==='manual'?'':currentBusinessType()==='pressure'&&!(parseFloat(d.price)>0)?'0.70':d.price;applyOnboardingMarketing(d);applySnowMarketingDefaultsIfNeeded(false);(d.benefits||[]).slice(0,6).forEach((b,j)=>{const n=j+1;if(el('benefitIcon'+n))el('benefitIcon'+n).value=b.icon||'✓';if(el('benefitTitle'+n))el('benefitTitle'+n).value=b.title||'';if(el('benefitText'+n))el('benefitText'+n).value=b.text||''});applySnowMarketingDefaultsIfNeeded(false);fillLandscapingBenefits();fillCommercialBenefits()}else if(el('price')&&el('jobPrice'))el('jobPrice').value=el('price').value}catch(e){}const logo=dealerLogoSrc();if(el('dealerLogoPreview')){if(logo){el('dealerLogoPreview').src=logo;el('dealerLogoPreview').style.display='block'}else{el('dealerLogoPreview').removeAttribute('src');el('dealerLogoPreview').style.display='none'}}toggleMarketingEditor();pricingChanged();clearNewJobCustomer();setTimeout(clearNewJobCustomer,250);setTimeout(clearNewJobCustomer,1000)};applyBusinessTerminology()

function toggleMarketingEditor(){if(el('marketingEnabled')?.checked)fillMissingMarketingBenefits();if(el('marketingEditor'))el('marketingEditor').style.display=el('marketingEnabled')?.checked?'block':'none';if(el('commercialMarketingPresetButton'))el('commercialMarketingPresetButton').style.display=currentBusinessType()==='commercial'?'inline-block':'none'}
function applyDealerMarketing(){applySnowMarketingDefaultsIfNeeded(false);fillLandscapingBenefits();fillCommercialBenefits();fillMissingMarketingBenefits();const enabled=!!el('marketingEnabled')?.checked,panel=el('rMarketingPanel'),benefitsBox=el('rMarketingBenefits'),warranty=el('rMarketingWarranty');if(panel)panel.classList.toggle('marketingHidden',!enabled);if(!enabled){if(el('rCtaHeading'))el('rCtaHeading').textContent='YOUR ESTIMATE';if(el('rCtaText'))el('rCtaText').textContent='';return}if(el('rMarketingHeading'))el('rMarketingHeading').textContent=(el('marketingHeading')?.value||'WHY CHOOSE US').trim();if(benefitsBox){benefitsBox.innerHTML='';[1,2,3,4,5,6].forEach(n=>{const title=(el('benefitTitle'+n)?.value||'').trim(),txt=(el('benefitText'+n)?.value||'').trim();if(!title&&!txt)return;const row=document.createElement('div');row.className='benefit';const icon=document.createElement('span');icon.className='benefitIcon';icon.textContent=el('benefitIcon'+n)?.value||'✓';const body=document.createElement('div'),b=document.createElement('b');b.textContent=title||'Benefit';body.appendChild(b);if(txt){body.appendChild(document.createElement('br'));const sm=document.createElement('span');sm.className='small';sm.textContent=txt;body.appendChild(sm)}row.appendChild(icon);row.appendChild(body);benefitsBox.appendChild(row)})}let wt=(el('marketingWarranty')?.value||'').trim();if(/^Example: We stand behind our snow removal service/i.test(wt)||/add your company(?:'s)? (?:service guarantee|warranty)/i.test(wt))wt='';if(/^6\s*[-–—]?\s*year\s+transferable\s+warranty$/i.test(wt))wt='6-Year Transferable Warranty';if(warranty){warranty.textContent=wt;warranty.classList.toggle('marketingHidden',!wt)}if(el('rCtaHeading'))el('rCtaHeading').textContent=(el('marketingCtaHeading')?.value||'YOUR ESTIMATE').trim();if(el('rCtaText'))el('rCtaText').textContent=(el('marketingCtaText')?.value||'').trim()}
function detectProvince(addr){const a=(' '+String(addr||'').toUpperCase().replace(/[.,]/g,' ')+' ');const states={AL:'ALABAMA',AK:'ALASKA',AZ:'ARIZONA',AR:'ARKANSAS',CA:'CALIFORNIA',CO:'COLORADO',CT:'CONNECTICUT',DE:'DELAWARE',FL:'FLORIDA',GA:'GEORGIA',HI:'HAWAII',ID:'IDAHO',IL:'ILLINOIS',IN:'INDIANA',IA:'IOWA',KS:'KANSAS',KY:'KENTUCKY',LA:'LOUISIANA',ME:'MAINE',MD:'MARYLAND',MA:'MASSACHUSETTS',MI:'MICHIGAN',MN:'MINNESOTA',MS:'MISSISSIPPI',MO:'MISSOURI',MT:'MONTANA',NE:'NEBRASKA',NV:'NEVADA',NH:'NEW HAMPSHIRE',NJ:'NEW JERSEY',NM:'NEW MEXICO',NY:'NEW YORK',NC:'NORTH CAROLINA',ND:'NORTH DAKOTA',OH:'OHIO',OK:'OKLAHOMA',OR:'OREGON',PA:'PENNSYLVANIA',RI:'RHODE ISLAND',SC:'SOUTH CAROLINA',SD:'SOUTH DAKOTA',TN:'TENNESSEE',TX:'TEXAS',UT:'UTAH',VT:'VERMONT',VA:'VIRGINIA',WA:'WASHINGTON',WV:'WEST VIRGINIA',WI:'WISCONSIN',WY:'WYOMING',DC:'DISTRICT OF COLUMBIA'};for(const [code,name] of Object.entries(states)){if(new RegExp('\\b'+code+'\\b').test(a)||a.includes(' '+name+' '))return code}return null}
function updateUsage(){if(currentBusinessType()!=='roofing')el('usageLine').textContent=`This session — property lookups: ${usage.property} • area measurements: ${usage.area} • linear measurements: ${usage.linear} • estimates created: ${usage.reports}`;else el('usageLine').textContent=`This session — property lookups: ${usage.property} • extra structures: ${usage.structures} • reports: ${usage.reports} • saved assessments: ${usage.saved}`}

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
async function startManualOverride(){if(!sessionToken){status('Load the property first.','error');return}cancelCurrentTrace();garageMode=false;roofFixMode=false;locateRoofMode=false;outlineEditMode=false;outlinePoints=[];clearOutlineTemp();clearOverlays();structures=[];manualPlanes=[];manualLayers.forEach(x=>{try{map.removeLayer(x)}catch(e){}});manualLayers=[];adjustedOutline=null;setManualCorrectionLayout(true);setManualUi(true);if(el('measureSource'))el('measureSource').value='manual';if(el('solarFallback'))el('solarFallback').style.display='block';if(el('solarFallbackText'))el('solarFallbackText').textContent='Manual measurement selected for this property. Trace the shingled roof around the customer property pin and confirm the pitch.';if(el('garageGuide'))el('garageGuide').innerHTML='<b>Manual measurement mode.</b> Google lines are hidden. Trace the customer roof shown at the property pin.';const details=el('manualRoofDetails');if(details)details.open=true;renderSummary();status('Preparing stable satellite image for manual measurement…','warn');await useStableManualAerial();setTimeout(()=>{if(!traceMode)toggleTrace()},60);status('Manual measurement mode is ready. Trace the roof corners, zoom as needed, then save.','warn')}
function mercatorLat(y){const n=Math.PI-2*Math.PI*y;return 180/Math.PI*Math.atan(.5*(Math.exp(n)-Math.exp(-n)))}
function staticMapBounds(lat,lng,zoom,w=640,h=640,tileSize=256){const scale=tileSize*Math.pow(2,zoom),x=(lng+180)/360*scale,s=Math.sin(lat*Math.PI/180),y=(.5-Math.log((1+s)/(1-s))/(4*Math.PI))*scale;const x1=x-w/2,x2=x+w/2,y1=y-h/2,y2=y+h/2;return L.latLngBounds([mercatorLat(y2/scale),(x1/scale)*360-180],[mercatorLat(y1/scale),(x2/scale)*360-180])}
async function loadFallbackAerial(token,targetMap=map,requestedZoom=null){
 const r=await fetch('/fallback-meta/'+token),d=await r.json();
 if(!r.ok)throw new Error(d.error||'Could not load fallback aerial.');
 if(requestedZoom!==null&&d.provider==='mapbox')d.zoom=requestedZoom;
 const b=staticMapBounds(d.latitude,d.longitude,d.zoom,d.width,d.height,d.tile_size||256);
 let proxyError='';
 try{
   const ir=await fetch('/fallback-map/'+token+'?zoom='+d.zoom+'&v='+Date.now());
   if(!ir.ok){proxyError=(await ir.text())||'Could not load Google satellite fallback.';throw new Error(proxyError)}
   const blob=await ir.blob(),obj=URL.createObjectURL(blob);
   try{const probe=new Image();probe.src=obj;await probe.decode()}catch(e){URL.revokeObjectURL(obj);throw new Error('Satellite image could not decode.')}
   const layer=L.imageOverlay(obj,b,{opacity:1,interactive:false});layer._sgAerial=true;layer._sgAerialType='static-satellite';layer._sgProvider=d.provider;layer._sgZoom=d.zoom;layer.addTo(targetMap);
   layer.once('remove',()=>{try{URL.revokeObjectURL(obj)}catch(e){}});
   return{layer,bounds:b,method:'proxy',provider:d.provider,zoom:d.zoom}
 }catch(e){proxyError=e.message||String(e)}
 // If a Google key uses browser/referrer restrictions, the local Python proxy can be
 // rejected even though the same Static Maps request is allowed from this page.
 // Try the browser context once before declaring the aerial unavailable.
 const key="{{GOOGLE_MAPS_API_KEY}}".trim();
 if(key&&d.provider!=='mapbox'){
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
function startLocateRoof(){if(!sessionToken||!fallbackMode){status('Load the property first.','error');return}locateRoofMode=true;garageMode=false;roofFixMode=false;status('Click once near the centre of the house roof. We’ll retry Google at that exact location.','warn');if(el('solarFallbackText'))el('solarFallbackText').textContent='Click once near the centre of the HOUSE roof on the aerial.'}
function setManualUi(pure=false){const manualRow=el('traceBtn')?el('traceBtn').closest('.manualrow'):null;if(manualRow)manualRow.classList.toggle('main-house-trace-row',!!pure);if(el('tracePitchControl'))el('tracePitchControl').classList.toggle('main-house-pitch-control',!!pure);if(el('manualRoofSummary'))el('manualRoofSummary').textContent=pure?'Manual Measurement — Trace Customer Roof':'Add / Remeasure Garage or Other Roof';if(el('manualRoofWarning'))el('manualRoofWarning').innerHTML=pure?'<b>Manual measurement for this property.</b> Trace the shingled MAIN HOUSE around the customer property pin, then confirm the pitch. 5/12 is only the starting default.':(structures.length?"<b>Google's confirmed MAIN HOUSE stays in the quote.</b> Use this to add or remeasure a garage, shed, addition, or other shingled roof.":'<b>Your manually measured MAIN HOUSE stays in the quote.</b> Use this to add the garage, shed, shop, or another shingled building.');if(el('manualRoofHelp'))el('manualRoofHelp').textContent=pure?'Click each outside corner of the MAIN HOUSE, confirm the pitch, then press FINISH MEASUREMENT.':'Click around only the garage or other roof you want to add, confirm its pitch, then press SAVE & ADD ROOF.';if(el('manualPitchLabel'))el('manualPitchLabel').childNodes[0].nodeValue=pure?'Pitch of Main Roof ':'Pitch of Added Roof ';if(el('traceBtn')&&!traceMode)el('traceBtn').textContent=pure?'START MANUAL MEASUREMENT':'ADD MISSING ROOF';if(el('finishTrace'))el('finishTrace').textContent=pure?'FINISH MEASUREMENT':'SAVE & ADD ROOF';if(el('traceBanner'))el('traceBanner').textContent=pure?'MANUAL MEASURE ON — click roof corners, then FINISH MEASUREMENT':'MANUAL MEASURE ON — click roof corners, then SAVE & ADD ROOF';if(el('clearManualBtn'))el('clearManualBtn').textContent=pure?'CLEAR MAIN HOUSE OUTLINE':'CLEAR ADDED ROOF DRAWING';}
function startManualFallback(){if(!sessionToken||!fallbackMode){status('Load the property first.','error');return}locateRoofMode=false;setManualUi(true);if(el('solarFallbackText'))el('solarFallbackText').textContent='Manual mode: trace the shingled roof and confirm the pitch. Google automatic measurement is unavailable for this property.';status('Manual measurement ready — open the manual roof section, trace the roof, and confirm pitch.','warn');const details=el('manualRoofDetails');if(details)details.open=true;}
async function retryRoofAt(ll){if(!sessionToken)return;locateRoofMode=false;if(clickMarker){try{map.removeLayer(clickMarker)}catch(e){}}clickMarker=L.marker(ll).addTo(map).bindPopup('Checking this roof with Google…').openPopup();try{showLoad(true);status('Checking the selected roof with Google…');const r=await fetch('/locate-building',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:sessionToken,latitude:ll.lat,longitude:ll.lng})}),d=await r.json();if(!r.ok){showSolarFallback(true,'Google still cannot automatically measure this roof. You can click a slightly different spot and retry, or choose MEASURE MANUALLY.');status(d.user_error||'Google automatic measurement is unavailable for this roof.','warn');return}structures=[{...d.main,label:'Main House'}];setManualCorrectionLayout(false);setManualUi(false);if(el('measureSource'))el('measureSource').value='google';if(fallbackLayer){try{map.removeLayer(fallbackLayer)}catch(e){}fallbackLayer=null}if(rgbLayer){try{map.removeLayer(rgbLayer)}catch(e){}rgbLayer=null}let rgb=await loadRaster('/rgb/'+sessionToken);rgbLayer=rgb.layer;mainBounds=rgb.bounds;frameAerial(map,rgb.bounds,0);roofMask=await loadRoofMask('/mask/'+sessionToken);structures[0].outline=outlineFromMask(roofMask,d.main.latitude,d.main.longitude);reviewAutomaticRoof(structures[0]);await loadStandardWideAerial();redrawRoofData();showSolarFallback(false);renderSummary();if(el('garageGuide'))el('garageGuide').innerHTML=roofQuoteNeedsReview()?'<b>Main roof requires review.</b> Use the roof action beside the aerial to review or trace it.': '<b>Main house measured.</b> If there is another roof to include, click <b>+ ADD GARAGE / OTHER ROOF</b>, then click once on that roof.';if(el('measureClicked'))el('measureClicked').disabled=false;if(el('measureClickedTop'))el('measureClickedTop').disabled=false;status((structures[0]?.needs_remeasure||structures[0]?.automatic_review_warning)?'Main roof coverage needs review. Use the roof action beside the aerial to review or trace it.':'Main house measured from the roof you selected.',(structures[0]?.needs_remeasure||structures[0]?.automatic_review_warning)?'warn':'ok')}catch(e){showSolarFallback(true,'Google still cannot automatically measure this roof. Try a slightly different point or choose MEASURE MANUALLY.');status('Google automatic measurement is unavailable for this roof.','warn')}finally{showLoad(false);if(clickMarker){try{map.removeLayer(clickMarker)}catch(e){}clickMarker=null}}}

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
 if(validOutline&&!outlineMatchesBuilding(outline,roof))issues.push('The extracted outline extends beyond Google’s matched building boundary.');
 if(Number.isFinite(roof.roof_coverage_ratio)&&roof.roof_coverage_ratio<.95)issues.push('Google’s roof data covers '+(roof.roof_coverage_ratio*100).toFixed(1)+'% of its reported building footprint.');
 if(ground>0&&(footprint/ground<.75||footprint/ground>1.25))issues.push('The extracted outline footprint differs from Google’s reported roof footprint by more than 25%.');
 if(ground>0&&area<ground*.98)issues.push('Automatic roof surface area is smaller than its ground footprint.');
 const segments=roof.segments;if(!Array.isArray(segments)||!segments.length||segments.some(seg=>!Number.isFinite(seg.pitch_degrees)||seg.pitch_degrees<0||seg.pitch_degrees>=80||!Number.isFinite(seg.area_sqft)||seg.area_sqft<=0))issues.push('Automatic roof sections or pitches are incomplete.');
 if(Array.isArray(segments)&&segments.length&&segments.every(seg=>Number.isFinite(seg.pitch_degrees)&&Number.isFinite(seg.area_sqft))){const segmentArea=segments.reduce((n,seg)=>n+seg.area_sqft,0),segmentGround=segments.reduce((n,seg)=>n+seg.area_sqft*Math.cos(seg.pitch_degrees*Math.PI/180),0);if(Math.abs(segmentArea-area)>Math.max(1,area*.01)||ground>0&&(segmentGround/ground<.75||segmentGround/ground>1.25))issues.push('Automatic roof sections do not match the complete roof area and pitch.')}
 return {issues,outline_ground_sqft:footprint,google_roof_ground_sqft:ground,google_roof_sqft:area};
}
function automaticRoofNeedsReview(roof,outline){return automaticRoofReviewDetails(roof,outline).issues.length>0}
function automaticRoofReviewHtml(roof){
 const review=roof.automatic_review;if(!review?.issues?.length)return '';
 return '<details class="small" style="margin-top:7px"><summary>Why this roof needs review</summary><div style="padding:7px 0">'+review.issues.map(t=>'<div>'+escapeHistory(t)+'</div>').join('')+'<div>Google returned roof area: '+fmt(review.google_roof_sqft)+' ft².</div><div>Google roof footprint: '+fmt(review.google_roof_ground_sqft)+' ft². Extracted outline footprint: '+fmt(review.outline_ground_sqft)+' ft².</div></div></details>';
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
function drawSegments(s,kind,targetMap=map,targetList=overlays,skipOutline=false){if(targetMap===map&&traceMode&&roofRemeasureTarget===s)return;const roofList=targetMap===map?structures:(quoteSnapshot?.structures||structures),compact=roofList.length>3,index=roofList.indexOf(s);if(s.needs_remeasure){const n=document.createElement('div');n.className='manual-label';n.textContent=s.label+' — needs remeasurement';targetList.push(L.marker([s.latitude,s.longitude],{interactive:false,icon:L.divIcon({className:'',html:n.outerHTML,iconAnchor:[70,10]})}).addTo(targetMap));return}const color=s.manually_measured?'#d97706':kind==='house'?'#2d6cdf':'#18a7a0',segs=(s.segments||[]),mode=(el('outlineMode')?el('outlineMode').value:'smart'),showBoxes=(mode==='all');if(s.manually_measured&&!compact){targetList.push(L.marker([s.latitude,s.longitude],{interactive:false,icon:L.divIcon({className:'',html:`<div class="manual-label">${Number(segs[0]?.pitch_degrees||0).toFixed(1)}° · ${fmt(s.total_roof_sqft)} ft²</div>`,iconAnchor:[65,10]})}).addTo(targetMap))}segs.forEach((seg)=>{const b=seg.bounding_box;if(!b||!b.sw||!b.ne)return;if(showBoxes){const rect=L.rectangle([[b.sw.latitude,b.sw.longitude],[b.ne.latitude,b.ne.longitude]],{color,weight:2,fillColor:color,fillOpacity:.08}).addTo(targetMap);targetList.push(rect)}if(compact)return;const c=seg.center||{latitude:(b.sw.latitude+b.ne.latitude)/2,longitude:(b.sw.longitude+b.ne.longitude)/2};const lab=L.marker([c.latitude,c.longitude],{interactive:false,icon:L.divIcon({className:'',html:`<div class="seg-label">${seg.pitch_degrees.toFixed(1)}°</div>`,iconAnchor:[24,10]})}).addTo(targetMap);targetList.push(lab)});if(compact){targetList.push(L.marker([s.latitude,s.longitude],{interactive:false,icon:L.divIcon({className:'',html:`<div class="seg-label" data-roof-summary="true">#${index+1} · ${fmt(s.total_roof_sqft)} ft²</div>`,iconAnchor:[45,10]})}).addTo(targetMap))}const visualOutline=(kind==='house'&&outlineEditMode)?null:((kind==='house'&&Array.isArray(adjustedOutline)&&adjustedOutline.length>=3)?adjustedOutline:s.outline);if(!skipOutline&&mode==='smart'&&Array.isArray(visualOutline)&&visualOutline.length>=3){const poly=L.polygon(visualOutline,{color,weight:5,fillColor:color,fillOpacity:.045,interactive:false,lineJoin:'round',smoothFactor:1.35}).addTo(targetMap);targetList.unshift(poly);if(targetMap===map&&!compact)drawEdgeMeasurements(visualOutline,color,targetMap,targetList,true)}}
function redrawRoofData(){clearOverlays();(structures||[]).forEach((st,i)=>drawSegments(st,i===0?'house':'garage'));}

function roofCheckGood(){if(structures[0]?.needs_remeasure||structures[0]?.automatic_review_warning){status('The main roof needs remeasurement in the Property Summary before it can be confirmed.','warn');return}if(structures[0])structures[0].automatic_review_confirmed=true;roofFixMode=false;if(el('fixRoofBtn')){el('fixRoofBtn').textContent='NO — REMOVE WRONG ROOF';el('fixRoofBtn').className='orange'}if(el('roofFixHelp'))el('roofFixHelp').innerHTML='<b>✓ Roofs confirmed.</b> Continue to price and estimate.';status('Roofs confirmed. Continue to price and estimate.','ok')}
function toggleRoofFix(){if(!structures.length){status('Load and measure the property first.','error');return}roofFixMode=!roofFixMode;if(el('fixRoofBtn')){el('fixRoofBtn').textContent=roofFixMode?'CANCEL FIX':'NO — REMOVE WRONG ROOF';el('fixRoofBtn').className=roofFixMode?'danger':'orange'}if(el('roofFixHelp'))el('roofFixHelp').innerHTML=roofFixMode?'<b>Click a wrong extra roof on the map to remove it.</b> If a roof is missing, use <b>+ ADD GARAGE / OTHER ROOF</b> above. Square footage and price recalculate automatically.':'Roof fix cancelled.';status(roofFixMode?'FIX ROOF ON — click the wrong extra roof to remove it.':'Roof fix cancelled.',roofFixMode?'warn':'ok')}
function removeClickedExtraRoof(ll){if(!roofFixMode||structures.length<2){roofFixMode=false;if(el('roofFixHelp'))el('roofFixHelp').textContent='No extra roof is available to remove. Use + Add Garage / Other Roof if a roof is missing.';status('No extra roof to remove.','warn');return}let best=-1,bestD=Infinity;for(let i=1;i<structures.length;i++){const st=structures[i],lat=Number(st.latitude),lng=Number(st.longitude);if(!Number.isFinite(lat)||!Number.isFinite(lng))continue;const dy=(ll.lat-lat)*111320,dx=(ll.lng-lng)*111320*Math.cos(ll.lat*Math.PI/180),d=Math.hypot(dx,dy);if(d<bestD){bestD=d;best=i}}if(best<1){status('Could not identify that extra roof. Click nearer its centre.','error');return}const removed=structures.splice(best,1)[0];roofFixMode=false;if(el('fixRoofBtn')){el('fixRoofBtn').textContent='NO — REMOVE WRONG ROOF';el('fixRoofBtn').className='orange'}redrawRoofData();renderSummary();if(el('roofFixHelp'))el('roofFixHelp').innerHTML='<b>✓ '+(removed.label||'Extra roof')+' removed.</b> Measurement and estimate recalculated. If the correct roof is missing, click <b>+ ADD GARAGE / OTHER ROOF</b>.';status((removed.label||'Extra roof')+' removed. Total and estimate recalculated.','ok')}
function outlineLooksGood(){status('Customer roof outline confirmed. Google measurement and price are unchanged.','ok');if(el('outlineHelp'))el('outlineHelp').innerHTML='<b>✓ Outline confirmed.</b> Google measurement remains '+fmt(googleTotal())+' ft².'}
function setOutlineButtons(editing){if(el('adjustOutlineBtn')){el('adjustOutlineBtn').textContent=editing?'CANCEL OUTLINE EDIT':'ADJUST CUSTOMER OUTLINE';el('adjustOutlineBtn').className=editing?'danger':'orange'};['finishOutlineBtn','undoOutlineBtn','clearOutlineBtn'].forEach(id=>{if(el(id))el(id).style.display=editing||adjustedOutline?'inline-block':'none'});if(el('finishOutlineBtn'))el('finishOutlineBtn').disabled=!editing||outlinePoints.length<3}
function clearOutlineTemp(){outlineTempLayers.forEach(x=>{try{map.removeLayer(x)}catch(e){}});outlineTempLayers=[]}
function toggleOutlineAdjust(){if(!structures.length){status('Load and measure the property first.','error');return}if(outlineEditMode){outlineEditMode=false;outlinePoints=[];clearOutlineTemp();redrawRoofData();setOutlineButtons(false);if(el('outlineHelp'))el('outlineHelp').textContent='Outline edit cancelled. Google measurement and price were not changed.';return}outlineEditMode=true;outlinePoints=[];clearOutlineTemp();redrawRoofData();setOutlineButtons(true);if(el('outlineHelp'))el('outlineHelp').innerHTML='<b>Click around the outside edge of the shingled roof.</b> Click each corner once, then Finish Outline. This changes the customer picture only.';status('Adjust Customer Outline ON — click the outside roof corners.','warn')}
function addOutlinePoint(ll){outlinePoints.push(ll);const n=outlinePoints.length,pt=L.marker(ll,{interactive:false,icon:L.divIcon({className:'',html:`<div class="point-label">${n}</div>`,iconAnchor:[12,12]})}).addTo(map);outlineTempLayers.push(pt);redrawOutlineTrace();setOutlineButtons(true)}
function redrawOutlineTrace(){outlineTempLayers.filter(x=>x._outlineLine).forEach(x=>{try{map.removeLayer(x)}catch(e){}});outlineTempLayers=outlineTempLayers.filter(x=>!x._outlineLine);if(outlinePoints.length>=2){let c=[...outlinePoints];if(outlinePoints.length>=3)c.push(outlinePoints[0]);let l=L.polyline(c,{color:'#2d6cdf',weight:5,dashArray:'8,5'}).addTo(map);l._outlineLine=true;outlineTempLayers.push(l)}}
function undoOutlinePoint(){if(!outlineEditMode||!outlinePoints.length)return;const keep=outlinePoints.slice(0,-1);outlinePoints=[];clearOutlineTemp();keep.forEach(addOutlinePoint);setOutlineButtons(true)}
function finishOutlineAdjust(){if(!outlineEditMode||outlinePoints.length<3)return;adjustedOutline=outlinePoints.map(p=>[p.lat,p.lng]);outlineEditMode=false;outlinePoints=[];clearOutlineTemp();redrawRoofData();setOutlineButtons(false);if(el('outlineHelp'))el('outlineHelp').innerHTML='<b>✓ Customer outline adjusted.</b> Google roof measurement stays at '+fmt(googleTotal())+' ft² and the estimate price is unchanged.';renderSummary();status('Customer outline updated. Google measurement and estimate price are unchanged.','ok')}
function clearAdjustedOutline(){adjustedOutline=null;outlineEditMode=false;outlinePoints=[];clearOutlineTemp();redrawRoofData();setOutlineButtons(false);if(el('outlineHelp'))el('outlineHelp').textContent='Using Google customer outline. Measurement and price are unchanged.';renderSummary();status('Google outline restored.','ok')}
function pitchChanged(){if(el('pitchSel').value!=='custom')el('pitchDeg').value=el('pitchSel').value;const custom=el('pitchSel').value==='custom';if(custom&&el('pitchDeg').type==='hidden')el('pitchDeg').value='';el('pitchDeg').type=custom?'number':'hidden';el('pitchDeg').placeholder='Pitch in degrees';el('pitchDeg').min='0';el('pitchDeg').max='79.9';el('pitchDeg').step='0.1';el('pitchDeg').setAttribute('aria-label','Roof pitch in degrees');el('tracePitchControl').append(el('pitchDeg'));el('pitchDeg').oninput=()=>{updateManualReplacementUi();if(manualRoofQa())renderSummary()};if(roofRemeasureTarget&&!roofOutlineReviewMode)updateManualReplacementUi();if(manualRoofQa())renderSummary()}
function commercialActive(){return ['commercial','paving','pressure','landscaping','snow'].includes(currentBusinessType())&&measurementViewMode==='area'}
function surfaceLinearJobRate(){return measurementViewMode==='linear'?currentJobPrice():(savedLinearJobRate===null?currentJobPrice():savedLinearJobRate)}
function savedSurfaceHasAreas(){return ['landscaping','paving','pressure','snow'].includes(currentBusinessType())&&multiAreaSaved()}
function surfaceServiceLabel(){return ({landscaping:'Landscaping',paving:'Paving & Sealcoating',pressure:'Pressure Washing',snow:'Snow Removal'})[currentBusinessType()]||'Service'}
function savedSurfacePriceLines(snap){return landscapingSavedPriceLines(snap).replace(/Landscaping Linear/g,surfaceServiceLabel()+' Linear')}
function landscapingHasAreas(){return currentBusinessType()==='landscaping'&&multiAreaSaved()}
function landscapingAreaSubtotal(){return commercialAreas.reduce((sum,a)=>sum+Number(a.sqft||0)*Number(a.rate||0),0)}
function landscapingSavedPriceLines(snap){return (snap.commercialAreas||[]).filter(a=>a.sqft>0).map(a=>`<div class="line"><span>${escapeHistory(a.name||'Service Area')} — ${fmt(a.sqft)} ft² × ${money(a.rate)}/ft²</span><b>${money(decimalCurrency('product',[a.sqft,a.rate]))}</b></div>`).join('')+(snap.linearFeet>0?`<div class="line"><span>${surfaceServiceLabel()} Linear — ${Number(snap.linearFeet).toFixed(1)} ft × ${money(snap.landscapingLinearRate)}/ft</span><b>${money(decimalCurrency('product',[snap.linearFeet,snap.landscapingLinearRate]))}</b></div>`:'')}
function multiAreaTotal(){return commercialAreas.reduce((n,a)=>n+(Number(a.sqft)||0),0)}
function multiAreaSaved(){return ['commercial','paving','pressure','landscaping','snow'].includes(currentBusinessType())&&commercialAreas.some(a=>a.sqft>0)}
function pavingCombined(){return currentBusinessType()==='paving'&&areaMeasurementSaved&&areaPoints.length>=3&&linearMeasurementSaved&&linearPoints.length>1}
function pavingAreaRate(){return Math.max(0,Number(el('pavingAreaRate')?.value||0))}
function pavingPriceLines(){return '<div class="line"><span>Paving Area — '+fmt(Math.round(multiAreaSaved()?multiAreaTotal():areaSqFtTotal()))+' ft² × '+money(pavingAreaRate())+'/ft²</span><b>'+money(decimalCurrency('product',[Math.round(multiAreaSaved()?multiAreaTotal():areaSqFtTotal()),pavingAreaRate()]))+'</b></div><div class="line"><span>Paving Linear — '+linearFeetTotal().toFixed(1)+' ft × '+money(currentJobPrice())+'/ft</span><b>'+money(decimalCurrency('product',[linearFeetTotal(),currentJobPrice()]))+'</b></div>'}
function pressureCombined(){return currentBusinessType()==='pressure'&&areaMeasurementSaved&&areaPoints.length>=3&&linearMeasurementSaved&&linearPoints.length>1}
function pressureAreaRate(){return Math.max(0,Number(el('pressureAreaRate')?.value||0))}
function pressurePriceLines(){return `<div class="line"><span>Pressure Washing Area — ${fmt(Math.round(multiAreaSaved()?multiAreaTotal():areaSqFtTotal()))} ft² × ${money(pressureAreaRate())}/ft²</span><b>${money(decimalCurrency('product',[Math.round(multiAreaSaved()?multiAreaTotal():areaSqFtTotal()),pressureAreaRate()]))}</b></div><div class="line"><span>Pressure Washing Linear — ${linearFeetTotal().toFixed(1)} ft × ${money(currentJobPrice())}/ft</span><b>${money(decimalCurrency('product',[linearFeetTotal(),currentJobPrice()]))}</b></div>`}
function landscapingCombined(){return currentBusinessType()==='landscaping'&&(multiAreaSaved()||(areaMeasurementSaved&&areaPoints.length>=3))&&linearMeasurementSaved&&linearPoints.length>1}
function landscapingAreaRate(){return Math.max(0,Number(el('landscapingAreaRate')?.value||0))}
function landscapingPriceLines(){if(landscapingHasAreas())return landscapingSavedPriceLines({commercialAreas,linearFeet:linearMeasurementSaved?linearFeetTotal():0,landscapingLinearRate:surfaceLinearJobRate()});return `<div class="line"><span>Landscaping Area — ${fmt(Math.round(multiAreaSaved()?multiAreaTotal():areaSqFtTotal()))} ft² × ${money(landscapingAreaRate())}/ft²</span><b>${money(decimalCurrency('product',[Math.round(multiAreaSaved()?multiAreaTotal():areaSqFtTotal()),landscapingAreaRate()]))}</b></div><div class="line"><span>Landscaping Linear — ${linearFeetTotal().toFixed(1)} ft × ${money(currentJobPrice())}/ft</span><b>${money(decimalCurrency('product',[linearFeetTotal(),currentJobPrice()]))}</b></div>`}
function commercialHasAreas(){return currentBusinessType()==='commercial'&&commercialAreas.some(a=>a.sqft>0)}
function commercialHasLinear(){return currentBusinessType()==='commercial'&&linearMeasurementSaved&&linearPoints.length>1}
function commercialLinearRate(){return Math.max(0,Number(el('commercialLinearRate')?.value||0))}
function commercialPriceLines(){return commercialAreas.filter(a=>a.sqft>0).map(a=>`<div class="line"><span>${escapeHistory(a.name||'Service Area')} — ${fmt(a.sqft)} ft² × ${money(a.rate)}/ft²</span><b>${money(decimalCurrency('product',[a.sqft,a.rate]))}</b></div>`).join('')+(commercialHasLinear()?`<div class="line"><span>Linear Service — ${linearFeetTotal().toFixed(1)} ft × ${money(commercialLinearRate())}/ft</span><b>${money(decimalCurrency('product',[linearFeetTotal(),commercialLinearRate()]))}</b></div>`:'')}
function commercialSyncCurrent(){if(!commercialActive()||!areaMeasurementSaved||areaPoints.length<3)return;if(commercialEditingIndex<0)commercialEditingIndex=commercialAreas.length;const old=commercialAreas[commercialEditingIndex]||{};commercialAreas[commercialEditingIndex]={name:old.name||'Service Area '+(commercialEditingIndex+1),rate:old.rate===undefined?(String(el('jobPrice')?.value??'').trim()===''?'':currentJobPrice()):old.rate,source:old.source||'manual',points:areaPoints.map(p=>[p.lat,p.lng]),sqft:Math.round(areaSqFtTotal())}}
function commercialAreaField(i,key,value){if(areaRemeasureMode)return;if(!commercialAreas[i])return;if(key==='rate'){commercialAreas[i].rate=String(value).trim()===''?null:Number(value);if(currentBusinessType()!=='commercial'&&el('jobPrice')&&measurementViewMode==='area'&&commercialAreas.length===1){el('jobPrice').value=String(commercialAreas[i].rate);const rateId={landscaping:'landscapingAreaRate',paving:'pavingAreaRate',pressure:'pressureAreaRate'}[currentBusinessType()];if(rateId&&el(rateId))el(rateId).value=String(commercialAreas[i].rate)}}else commercialAreas[i].name=value;if(key!=='rate')commercialAreaUi();renderSummary()}
function commercialAreaDrawSaved(){commercialAreaLayers.forEach(l=>{try{map.removeLayer(l)}catch(e){}});commercialAreaLayers=[];if(!['commercial','paving','pressure','landscaping','snow'].includes(currentBusinessType()))return;commercialAreas.forEach((a,i)=>{if((measurementViewMode==='area'&&i===commercialEditingIndex)||!a.points||a.points.length<3)return;const poly=L.polygon(a.points,{color:'#198b87',weight:3,fillOpacity:.1,interactive:false}).addTo(map);commercialAreaLayers.push(poly);drawCustomerAreaEdgeLabels(a.points,map,commercialAreaLayers);commercialAreaLayers.push(L.marker(poly.getBounds().getCenter(),{interactive:false,keyboard:false,icon:L.divIcon({className:'',html:`<div class="area-label">${fmt(a.sqft)} ft²</div>`,iconAnchor:[35,10]})}).addTo(map))})}
function commercialAreaUi(){
 const panel=el('commercialAreaPanel');if(!panel)return;
 const surface=['commercial','paving','pressure','landscaping','snow'].includes(currentBusinessType()),saved=commercialAreas.map((a,i)=>({a,i})).filter(x=>x.a.sqft>0);
 panel.style.display=surface&&saved.length?'block':'none';if(!surface)return;
 panel.querySelector('b').textContent='Saved areas — '+fmt(multiAreaTotal())+' ft²';
 const box=el('commercialAreaList');if(box)box.innerHTML=saved.map(({a,i})=>`<div class="surface-saved-area"><div class="surface-area-heading"><label>Area name<input aria-label="Service area name" value="${escapeHistory(a.name||'').replace(/"/g,'&quot;')}" onchange="commercialAreaField(${i},'name',this.value)"${areaRemeasureMode?' disabled':''}></label><strong>${fmt(a.sqft)} ft²</strong></div><div class="surface-area-price"><label>Rate / sq. ft.<input aria-label="Rate per square foot" data-area-job-rate="${i}" type="number" min="0" step="0.01" value="${a.rate}" oninput="commercialAreaField(${i},'rate',this.value)"${areaRemeasureMode?' disabled':''}></label><b>${a.rate!==null&&a.rate!==undefined&&String(a.rate).trim()!==''&&Number.isFinite(Number(a.rate))&&Number(a.rate)>=0?money(decimalCurrency('product',[a.sqft,a.rate])):'Rate required'}</b><span class="small">✓ Saved in this job</span></div><div class="simple-actions"><button type="button" class="primary" onclick="remeasureSurfaceArea(${i})"${areaMode||linearMode||linearCorrectionOriginal?' disabled':''}>REMEASURE AREA</button><button type="button" class="ghost" onclick="commercialEditArea(${i})"${areaMode||linearMode||linearCorrectionOriginal?' disabled':''}>EDIT OUTLINE</button><button type="button" class="ghost" onclick="commercialRemoveArea(${i})"${areaCorrectionOriginal||linearMode||linearCorrectionOriginal?' disabled':''}>REMOVE AREA</button></div></div>`).join('');
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
 area.style.display=areaMode?'block':'none';if(areaMode)el('areaTotal').textContent='Drawing: '+fmt(areaSqFtTotal())+' ft²';
 el('areaStartBtn').style.display=areaMode?'inline-block':'none';el('areaStartBtn').textContent=areaRemeasureMode?'SAVE REPLACEMENT AREA':areaCorrectionOriginal?'SAVE AREA CHANGES':'SAVE AREA';el('areaStartBtn').disabled=areaMode&&!!(areaRemeasureMode?replacementAreaError():measuredPolygonError(areaPoints));
 el('areaCorrectBtn').style.display='none';el('areaCancelCorrectionBtn').style.display=areaMode?'inline-block':'none';el('areaCancelCorrectionBtn').textContent='CANCEL';el('areaCancelCorrectionBtn').setAttribute('onclick','cancelSurfaceAreaDrawing()');
 el('areaClearBtn').style.display=areaMode&&areaPoints.length?'inline-block':'none';el('areaClearBtn').textContent='START OVER';el('areaClearBtn').setAttribute('onclick','restartSurfaceAreaDrawing()');
 if(areaMode&&areaRemeasureMode)el('areaHelp').textContent=areaPoints.length>=3&&replacementAreaError()?replacementAreaError():'Trace the replacement boundary in order. SAVE REPLACEMENT AREA confirms the new outline and price; Cancel keeps the original.';
 else if(areaMode)el('areaHelp').textContent=areaPoints.length>=3&&measuredPolygonError(areaPoints)?measuredPolygonError(areaPoints):areaCorrectionOriginal?'Drag the corner points or start over. Save Area Changes when finished; Cancel keeps the original outline.':areaPoints.length>=3?'Check the outline, then click SAVE AREA.':'Click around the outside edge. Place at least three corners, then SAVE AREA.';
 const savedLine=linearMeasurementSaved&&linearPoints.length>=2&&!linearMode&&!linearCorrectionOriginal;
 line.style.display=linearMode||linearCorrectionOriginal||savedLine?'block':'none';
 if(!more){more=document.createElement('details');more.id='surfaceLineMore';more.innerHTML='<summary>More line options</summary><div class="simple-actions"></div>';el('linearHelp').before(more)}
 if(savedLine){more.hidden=false;if(!more._wasSaved)more.open=false;more.querySelector('div').append(start,clear);start.style.display='inline-block';start.textContent='EXTEND LINE';clear.style.display='inline-block';clear.textContent='REMOVE LINE';clear.setAttribute('onclick','clearLinearMeasure()');el('linearHelp').textContent='✓ Saved in this job. Edit Line moves the points. More line options lets you extend or remove the line.'}
 else{more.hidden=true;for(const node of [start,clear])if(node.parentNode!==node._surfaceAnchor.parentNode)node._surfaceAnchor.parentNode.insertBefore(node,node._surfaceAnchor.nextSibling);clear.style.display=linearMode&&linearPoints.length?'inline-block':'none';clear.textContent='START OVER';clear.setAttribute('onclick','restartSurfaceLineDrawing()');start.textContent='SAVE LINE'}
 more._wasSaved=savedLine;start.disabled=areaMode||(linearMode&&(linearPoints.length<2||linearFeetTotal()<.001));clear.disabled=areaMode||!!linearCorrectionOriginal;
 el('linearSaveEditBtn').disabled=!!linearCorrectionOriginal&&linearFeetTotal()<.001;el('linearEditBtn').disabled=areaMode;
 if(!cancel){cancel=document.createElement('button');cancel.id='surfaceLineCancel';cancel.type='button';cancel.className='ghost';cancel.textContent='CANCEL';cancel.onclick=cancelSurfaceLineDrawing;start._surfaceAnchor.parentNode.append(cancel)}cancel.hidden=!linearMode;
 if(linearMode)el('linearHelp').textContent=linearPoints.length>=2&&linearFeetTotal()<.001?'The line needs two different points. Start over or Cancel.':linearPoints.length>=2?'Check the line, then click SAVE LINE.':'Click the starting point, then each turn or endpoint. Place at least two points, then SAVE LINE.';
 el('toolAreaBtn').disabled=false;el('toolLinearBtn').disabled=false;
 const button=el('createEstimateBtn');let guide=el('surfaceSaveGuidance');if(!guide){guide=document.createElement('div');guide.id='surfaceSaveGuidance';guide.setAttribute('role','status');guide.setAttribute('aria-live','polite');guide.style.marginTop='10px';button.closest('.simple-actions').after(guide)}
 guide.hidden=!sessionToken;const active=areaMode||linearMode||linearCorrectionOriginal,hasSaved=multiAreaSaved()||savedLine;
 guide.className=(active?'warning':'good')+' small';guide.textContent=active?'Finish the active drawing above the aerial: '+(areaMode?(areaRemeasureMode?'SAVE REPLACEMENT AREA':areaCorrectionOriginal?'SAVE AREA CHANGES':'SAVE AREA'):linearCorrectionOriginal?'SAVE LINE CHANGES':'SAVE LINE')+' or CANCEL. Saved measurements are kept.':hasSaved?'✓ Measurements saved in this job. Add customer details, then CREATE CUSTOMER ESTIMATE to save the completed estimate. Create it before leaving or refreshing.':'Choose ADD AREA or LINEAR above the aerial to start measuring.';
}
function updateAreaUi(){syncMeasurementEditMapDragging();const total=areaSqFtTotal(),surfaceOnly=['commercial','paving','pressure','landscaping','snow'].includes(currentBusinessType());commercialAreaUi();if(el("areaCorrectBtn"))el("areaCorrectBtn").style.display=areaMeasurementSaved&&!areaMode&&areaPoints.length>=3?"inline-block":"none";if(el("areaCancelCorrectionBtn"))el("areaCancelCorrectionBtn").style.display=areaCorrectionOriginal?"inline-block":"none";if(el('areaTotal'))el('areaTotal').textContent=`Area: ${fmt(multiAreaSaved()?multiAreaTotal():total)} ft²`;if(el('areaUndoBtn'))el('areaUndoBtn').style.display=areaMode&&areaPoints.length?'inline-block':'none';if(el('areaClearBtn'))el('areaClearBtn').style.display=(areaMode||measurementViewMode==='area')&&areaPoints.length?'inline-block':'none';if(el('areaAutoBtn'))el('areaAutoBtn').style.display=!surfaceOnly&&measurementViewMode==='area'?'inline-block':'none';if(el('areaHelp'))el('areaHelp').innerHTML=areaMode?(areaPoints.length>=3?`<b>Area Measure ON.</b> ${areaPoints.length} points placed • <b>${fmt(total)} ft²</b>. Keep clicking to adjust the outline, then Save Area Measurement.`:`<b>Area Measure ON.</b> Click at least three corners around the service area.`):(measurementViewMode==='area'&&areaMeasurementSaved?`<b>✓ Area measurement saved: ${fmt(total)} ft².</b> ${multiAreaSaved()?'All saved service areas are included in this quote.':currentBusinessType()==='paving'?'Only the saved paved surface is included in this quote.':currentBusinessType()==='pressure'?'Only the saved cleaning surface is included in this quote.':currentBusinessType()==='landscaping'?'Only the measured landscaping area is included in this quote.':'Only the selected service area is included in this quote.'}`:'Click Start Area Measure for a clean aerial workspace.');document.body.classList.toggle('area-active',areaMode);syncSurfaceMeasurementControls();}
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
}if(areaPoints.length>=3){const fill=L.polygon(areaPoints,{color:'#7357b8',weight:0,fillColor:'#7357b8',fillOpacity:.14,interactive:false}).addTo(map);areaLayers.push(fill);const c=fill.getBounds().getCenter(),lab=L.marker(c,{interactive:false,icon:L.divIcon({className:'',html:`<div class="area-label">${fmt(areaSqFtTotal())} ft²</div>`,iconAnchor:[35,10]})}).addTo(map);areaLayers.push(lab)}updateAreaUi()}
function addAreaPoint(ll){if(!areaMode)return;if(areaCorrectionOriginal&&!areaRemeasureMode){status('Drag an existing corner to adjust this outline. Save the changes or Cancel to restore the saved area.','warn');return}areaPoints.push(ll);areaMeasurementSaved=false;redrawAreaMeasure();renderSummary()}
function undoAreaPoint(){if(!areaMode||!areaPoints.length)return;areaPoints.pop();areaMeasurementSaved=false;redrawAreaMeasure();renderSummary()}
function clearAreaMeasure(){if(areaRemeasureMode){cancelSurfaceAreaDrawing();return}areaCorrectionOriginal=null;areaPoints=[];areaMeasurementSaved=false;if(commercialActive()&&commercialEditingIndex>=0){commercialAreas.splice(commercialEditingIndex,1);commercialEditingIndex=-1;commercialAreaDrawSaved()}clearAreaLayers();restoreSavedLineAfterLastArea();updateAreaUi();renderSummary();status('Area measurement cleared.','ok')}
function toggleAreaMeasure(){if(linearCorrectionOriginal)cancelLinearCorrection();if(!sessionToken){status('Load the property first.','error');return}if(commercialActive()&&!areaMode&&areaMeasurementSaved&&areaPoints.length>=3&&!areaCorrectionOriginal){commercialAddArea();return}if(areaMode){const problem=areaRemeasureMode?replacementAreaError():measuredPolygonError(areaPoints);if(problem){status(problem,'error');return}areaMode=false;if(!areaMeasurementSaved)usage.area++;areaMeasurementSaved=true;areaCorrectionOriginal=null;areaRemeasureMode=false;measurementViewMode='area';if(commercialActive()){commercialSyncCurrent();commercialAreaDrawSaved();}if(el('areaStartBtn')){el('areaStartBtn').textContent=commercialActive()?'START ANOTHER SERVICE AREA':'CONTINUE AREA MEASURE';el('areaStartBtn').className='secondary'}updateAreaUi();renderSummary();status(`✓ AREA MEASUREMENT SAVED — ${fmt(areaSqFtTotal())} ft².`,'ok');return}if(linearMode)stopLinearMode(false);linearMode=false;if(linearMeasurementSaved&&linearPoints.length>=2)redrawLinearMeasure();else clearLinearLayers();areaMode=true;areaMeasurementSaved=false;measurementViewMode='area';hideRoofDisplayForLinear();if(el('areaStartBtn')){el('areaStartBtn').textContent='FINISH & SAVE AREA';el('areaStartBtn').className='primary'}redrawAreaMeasure();updateAreaUi();renderSummary();status('AREA MEASURE ON — click around the outside edge of the service area.','warn')}
function returnAreaToAutoMeasure(){if(areaMode&&areaPoints.length){status('Finish and save or clear the current area before returning to AutoMeasure.','warn');return}areaMode=false;measurementViewMode='auto';areaMeasurementSaved=areaPoints.length>=3;if(el('areaStartBtn')){el('areaStartBtn').textContent='START AREA MEASURE';el('areaStartBtn').className='secondary'}clearAreaLayers();restoreAutoMeasureDisplay();updateAreaUi();renderSummary();status('AutoMeasure restored. Your saved area measurement is still available.','ok')}
function canReviewDetectedRoof(roof){
 if(roof.needs_remeasure||!detectedRoofReviewOutline(roof)||!outlineMatchesBuilding(roof.detected_outline||roof.outline,roof))return false;
 if(!roof.automatic_review_warning)return true;
 const issues=roof.automatic_review?.issues;
 return !!issues?.length&&issues.every(issue=>issue==='The extracted outline footprint differs from Google’s reported roof footprint by more than 25%.');
}
function roofRowActionHtml(roof,index){
 if(roofRemeasureTarget===roof)return '<span class="roof-editing-indicator">Editing this roof — use the controls beside the aerial.</span>';
 const flagged=roof.needs_remeasure||roof.automatic_review_warning;
 const saved=roof.manually_measured&&!flagged?'<div class="good small" style="margin:6px 0">✓ Saved in this job — no additional roof Save needed.</div>':'';
 const disabled=traceMode?' disabled':'';
 const canReview=!roof.manually_measured&&canReviewDetectedRoof(roof);
 if(!roof.manually_measured&&!canReview){
  const issues=roof.automatic_review?.issues||[];
  const reasons=[...issues];
  const outline=roof.detected_outline||roof.outline;
  if(!detectedRoofReviewOutline(roof))reasons.unshift('No usable roof boundary was detected.');
  else if(!outlineMatchesBuilding(outline,roof))reasons.unshift('The outline extends outside the matched building.');
  else if(!reasons.length)reasons.push(roof.needs_remeasure?'Automatic roof coverage is incomplete.':'The automatic outline could not be verified.');
  return '<div class="warning small">'+reasons.map(reason=>'<div>'+escapeHistory(reason)+'</div>').join('')+'<div>Trace the whole roof manually to unlock the estimate.</div></div><button class="secondary roof-row-action" type="button"'+disabled+' onclick="startRoofRemeasure('+index+')">TRACE ROOF MANUALLY</button>';
 }
 if(canReview)return '<div class="small">'+(flagged?'Google’s area does not match the outline and will not be used. ':'')+'Check that every edge is on the intended roof and confirm one uniform pitch to continue.</div><button class="secondary roof-row-action" type="button"'+disabled+' onclick="startDetectedRoofReview('+index+')">KEEP OUTLINE</button> <button class="ghost roof-row-action" type="button"'+disabled+' onclick="startRoofRemeasure('+index+')">REMEASURE</button>';
 return saved+'<button class="ghost roof-row-action" type="button"'+disabled+' onclick="correctSelectedRoof('+index+')">EDIT ROOF</button>';
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
 const aerialAction=el('aerialRoofAction');
 if(aerialAction){
  const index=currentBusinessType()==='roofing'&&measurementViewMode==='auto'&&!traceMode
   ?structures.findIndex(roof=>!roof.manually_measured): -1;
  aerialAction.hidden=index<0;
  aerialAction.innerHTML=index<0?'':'<strong>'+escapeHistory(structures[index].label)+'</strong>'+roofRowActionHtml(structures[index],index);
 }
 let help=el('roofSaveGuidance');
 if(!help){help=document.createElement('div');help.id='roofSaveGuidance';help.setAttribute('role','status');help.setAttribute('aria-live','polite');help.style.marginTop='10px';button.closest('.simple-actions').after(help)}
 const visible=currentBusinessType()==='roofing'&&measurementViewMode==='auto'&&(structures.length||manualPlanes.length);
 help.hidden=!visible;if(!visible){help.textContent='';return}
 const pending=structures.filter(s=>s.needs_remeasure||s.automatic_review_warning),saved=structures.filter(s=>s.manually_measured&&!s.needs_remeasure&&!s.automatic_review_warning);
 const savedText=saved.length?saved.map(s=>s.label).join(', ')+(saved.length===1?' is':' are')+' saved in this job. ':'';
 const confirmationRequired=manualRoofQa()&&manualPlanes.length&&!el('manualRoofScopeConfirmed')?.checked;
 help.className=(roofRemeasureTarget||pending.length||confirmationRequired?'warning':'good')+' small';
 help.textContent=roofRemeasureTarget?'Editing '+roofRemeasureTarget.label+'. Save or cancel this roof using the controls above the aerial before creating the estimate.':pending.length?savedText+'Estimate locked: '+pending.map(s=>s.label).join(', ')+(pending.length===1?' still needs':' still need')+' correction. Use the roof action beside the aerial or in Property Summary.':confirmationRequired?'Review each saved section’s pitch, then select “Confirm pitches and included roofs” beside the saved sections to continue.':savedText+'Roof measurements are ready. Add customer details, then click CREATE CUSTOMER ESTIMATE to save the completed estimate.';
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
 if(roofSq>0&&currentBusinessType()==='roofing')rows.push(`<div class="jm-row"><span class="jm-kind">Roof — ${manualRoofQa()&&manualPlanes.length&&!structures.length?'Manual roof sections':structures.some(st=>st.manually_measured)?'Measured with corrections':'AutoMeasure'}</span><span class="jm-value">${fmt(roofSq)} ft²</span><span class="jm-status">${structures.some(st=>st.needs_remeasure||st.automatic_review_warning)?'REVIEW REQUIRED':'SAVED'}</span></div>`);
 if(multiAreaSaved())commercialAreas.forEach((a,i)=>{if(a.sqft>0)rows.push(`<div class="jm-row"><span class="jm-kind">${escapeHistory(a.name||'Service Area '+(i+1))}</span><span class="jm-value">${fmt(a.sqft)} ft²</span><span class="jm-status">SAVED</span></div>`)});
 else if(areaMeasurementSaved&&areaPoints.length>=3)rows.push(`<div class="jm-row"><span class="jm-kind">Service Area — Area</span><span class="jm-value">${fmt(areaSqFtTotal())} ft²</span><span class="jm-status">SAVED</span></div>`);
 if(linearMeasurementSaved&&linearPoints.length>=2)rows.push(`<div class="jm-row"><span class="jm-kind">Service Length — Linear</span><span class="jm-value">${linearFeetTotal().toFixed(1)} ft</span><span class="jm-status">SAVED</span></div>`);
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
function updateLinearUi(){syncMeasurementEditMapDragging();const editing=!!linearCorrectionOriginal;if(el('linearEditBtn'))el('linearEditBtn').style.display=linearMeasurementSaved&&linearPoints.length>=2&&!linearMode&&!editing?'inline-block':'none';['linearSaveEditBtn','linearCancelEditBtn'].forEach(id=>{if(el(id))el(id).style.display=editing?'inline-block':'none'});if(el('linearStartBtn'))el('linearStartBtn').style.display=editing?'none':'inline-block';if(el('linearClearBtn'))el('linearClearBtn').disabled=editing;if(el('linearAutoBtn'))el('linearAutoBtn').disabled=editing;const total=linearFeetTotal(),surfaceOnly=['commercial','paving','pressure','landscaping','snow'].includes(currentBusinessType());if(el('linearTotal'))el('linearTotal').textContent=`Total: ${total.toFixed(1)} ft`;if(el('linearUndoBtn'))el('linearUndoBtn').style.display=linearMode&&linearPoints.length?'inline-block':'none';if(el('linearClearBtn'))el('linearClearBtn').style.display=(linearMode||measurementViewMode==='linear')&&linearPoints.length?'inline-block':'none';if(el('linearAutoBtn'))el('linearAutoBtn').style.display=!surfaceOnly&&measurementViewMode==='linear'?'inline-block':'none';if(el('linearHelp'))el('linearHelp').innerHTML=editing?'<b>Edit Line ON.</b> Drag the teal corner points, then Save Line Changes or Cancel Line Edit.':linearMode?(linearPoints.length?`<b>Linear Measure ON.</b> ${linearPoints.length} point${linearPoints.length===1?'':'s'} placed • Total <b>${total.toFixed(1)} ft</b>. Keep clicking to continue the run.`:'<b>Linear Measure ON.</b> Click the first point, then each turn or endpoint.'):(measurementViewMode==='linear'&&linearPoints.length?`<b>✓ Linear measurement saved: ${total.toFixed(1)} ft.</b> Continue measuring or select another measurement tool above.`:(linearPoints.length?`Saved linear measurement • <b>${total.toFixed(1)} ft</b>.`:'Click Start Linear Measure for a clean aerial workspace.'));document.body.classList.toggle('linear-active',linearMode);syncSurfaceMeasurementControls()}
function clearLinearLayers(){linearLayers.forEach(x=>{try{map.removeLayer(x)}catch(e){}});linearLayers=[]}
function redrawLinearMeasure(){clearLinearLayers();linearPoints.forEach((pt,i)=>{const dot=L.marker(pt,{draggable:!!linearCorrectionOriginal,interactive:!!linearCorrectionOriginal,autoPan:false,icon:L.divIcon({className:'',html:'<div class="linear-point"></div>',iconAnchor:[6,6]})}).addTo(map);if(linearCorrectionOriginal)dot.on('dragend',()=>{linearPoints[i]=dot.getLatLng();redrawLinearMeasure();renderSummary()});linearLayers.push(dot);if(i>0){const a=linearPoints[i-1],b=pt,feet=map.distance(a,b)*3.28084;const line=L.polyline([a,b],{color:'#0f8f83',weight:5,opacity:.95,lineCap:'round'}).addTo(map);linearLayers.push(line);const mid=L.latLng((a.lat+b.lat)/2,(a.lng+b.lng)/2);const lab=L.marker(mid,{interactive:false,icon:L.divIcon({className:'',html:`<div class="linear-seg-label">${feet.toFixed(1)} ft</div>`,iconAnchor:[24,9]})}).addTo(map);linearLayers.push(lab)}});updateLinearUi()}
function editLinearMeasure(){
 if(!sessionToken||!linearMeasurementSaved||linearPoints.length<2||linearMode)return;
 if(areaMode){status('Finish and save the area outline before editing the line.','warn');return}
 if(measurementViewMode!=='linear')selectMeasurementTool('linear');
 linearCorrectionOriginal=linearPoints.map(p=>L.latLng(p.lat,p.lng));
 redrawLinearMeasure();renderSummary();status('EDIT LINE ON — drag the teal points, then SAVE LINE CHANGES or CANCEL LINE EDIT.','warn');
}
function saveLinearCorrection(){
 if(!linearCorrectionOriginal)return;
 const issue=savedLinearGeometryError();if(issue){status(issue,'error');return}
 linearCorrectionOriginal=null;linearMeasurementSaved=true;redrawLinearMeasure();renderSummary();status(`LINE CHANGES SAVED — ${linearFeetTotal().toFixed(1)} ft.`,'ok');
}
function cancelLinearCorrection(){
 if(!linearCorrectionOriginal)return;
 linearPoints=linearCorrectionOriginal.map(p=>L.latLng(p.lat,p.lng));linearCorrectionOriginal=null;linearMeasurementSaved=true;redrawLinearMeasure();renderSummary();status('Line edit cancelled; original line restored.','ok');
}
function clearManualDisplayLayers(){manualLayers.forEach(x=>{try{map.removeLayer(x)}catch(e){}});manualLayers=[]}
function redrawManualDisplayLayers(){clearManualDisplayLayers();manualPlanes.forEach((plane,i)=>{const poly=L.polygon(plane.points,{color:'#d97706',weight:5,fillColor:'#f59e0b',fillOpacity:.12,lineJoin:'round'}).addTo(map),c=poly.getBounds().getCenter(),lab=L.marker(c,{interactive:false,icon:L.divIcon({className:'',html:`<div class="manual-label">M${i+1} • ${Number(plane.pitch_degrees||0).toFixed(1)}° • ${fmt(plane.surface_sqft)} ft²</div>`,iconAnchor:[65,10]})}).addTo(map);manualLayers.push(poly,lab);drawEdgeMeasurements(plane.points,'#d97706',map,manualLayers,true)})}
function hideRoofDisplayForLinear(){clearOverlays();clearManualDisplayLayers();if(clickMarker){try{map.removeLayer(clickMarker)}catch(e){}clickMarker=null}}
function restoreAutoMeasureDisplay(){redrawRoofData();redrawManualDisplayLayers()}
function stopLinearMode(restoreRoof=false){linearMode=false;if(el('linearStartBtn')){el('linearStartBtn').textContent='START LINEAR MEASURE';el('linearStartBtn').className='secondary'}if(restoreRoof){measurementViewMode='auto';restoreAutoMeasureDisplay()}updateLinearUi()}
function returnToAutoMeasure(){if(linearMode&&linearPoints.length&&!linearCorrectionOriginal){status('Finish and save or clear the current line before returning to AutoMeasure.','warn');return}linearMode=false;measurementViewMode='auto';linearMeasurementSaved=linearPoints.length>1;if(el('linearStartBtn')){el('linearStartBtn').textContent='START LINEAR MEASURE';el('linearStartBtn').className='secondary'}restoreAutoMeasureDisplay();updateLinearUi();renderSummary();status('AutoMeasure restored. Your saved linear measurement is still available.','ok')}
function toggleLinearMeasure(){if(surfaceIndustry()&&!linearMode&&!linearCorrectionOriginal&&measurementViewMode!=='linear'){selectMeasurementTool('linear');if(measurementViewMode!=='linear')return}if(surfaceIndustry()&&!linearMode&&!linearCorrectionOriginal&&sessionToken)surfaceLineDraftOriginal={points:linearPoints.map(p=>({lat:p.lat,lng:p.lng})),saved:linearMeasurementSaved,savedRate:savedLinearJobRate,jobRate:el('jobPrice')?.value};if(linearCorrectionOriginal){saveLinearCorrection();return}if(!sessionToken){status('Load the property first.','error');return}if(areaMode){areaMode=false;if(multiAreaSaved())commercialSyncCurrent();clearAreaLayers();commercialAreaDrawSaved();updateAreaUi()}if(linearMode){const issue=savedLinearGeometryError();if(issue){status(issue,'error');return}linearMode=false;if(!linearMeasurementSaved)usage.linear++;linearMeasurementSaved=true;surfaceLineDraftOriginal=null;measurementViewMode='linear';if(el('linearStartBtn')){el('linearStartBtn').textContent='CONTINUE LINEAR MEASURE';el('linearStartBtn').className='secondary'}hideRoofDisplayForLinear();redrawLinearMeasure();updateLinearUi();renderSummary();status(`LINEAR MEASUREMENT SAVED — ${linearFeetTotal().toFixed(1)} ft. ${currentBusinessType()==='roofing'?'AutoMeasure remains hidden until you return to it.':'You can continue measuring or create the estimate.'}`,'ok');return}if(traceMode)cancelCurrentTrace();if(outlineEditMode){outlineEditMode=false;outlinePoints=[];clearOutlineTemp();setOutlineButtons(false)}roofFixMode=false;locateRoofMode=false;garageMode=false;measurementViewMode='linear';linearMeasurementSaved=false;hideRoofDisplayForLinear();linearMode=true;if(el('linearStartBtn')){el('linearStartBtn').textContent='FINISH & SAVE LINEAR';el('linearStartBtn').className='primary'}updateLinearUi();renderSummary();status(currentBusinessType()==='roofing'?'LINEAR MEASURE ON — roof overlays are hidden. Click the first point, then each turn or endpoint.':'LINEAR MEASURE ON — click the first point, then each turn or endpoint.','warn')}
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
function roofMeasurementSourceLabel(roof){return roof.measurement_source==='dealer_reviewed_detected_outline'?'Dealer-reviewed detected outline • verified uniform pitch':roof.measurement_source==='dealer_reviewed_trace'?'Dealer-reviewed manual trace • verified uniform pitch':'Dealer traced • confirmed pitch'}
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
 if(el('roofReviewDraft'))el('roofReviewDraft').textContent=problem?problem:'Draft footprint: '+fmt(ground)+' ft².'+(validPitch?' Draft roof area at selected pitch: '+fmt(ground/Math.cos(pitch*Math.PI/180))+' ft².':' Select a verified pitch to calculate roof area.')+' Not saved or included in the estimate.';
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
 el('roofRemeasurePitch').innerHTML='<div class="warning"><b>Detected outline — requires your review.</b><br>This outline is not a verified whole-building measurement. Check every edge against the aerial. This method uses ONE uniform pitch across the entire selected outline. If slopes differ, cancel this review; this shortcut cannot measure mixed pitches.</div><label for="roofReviewPitchSelect">Verified uniform roof pitch</label><select id="roofReviewPitchSelect" onchange="reviewedRoofPitchChanged()"><option value="">Select verified pitch</option>'+[0,1,2,3,4,5,6,7,8,9,10,11,12].map(r=>'<option value="'+(Math.atan(r/12)*180/Math.PI)+'">'+r+'/12'+(r===0?' (flat)':'')+'</option>').join('')+'<option value="custom">Custom degrees</option></select><input id="roofReviewPitchDeg" type="number" min="0" max="79.9" step="0.1" placeholder="Verified pitch in degrees" aria-label="Verified pitch in degrees" style="display:none" oninput="reviewedRoofPitchChanged()"><label style="display:flex;gap:8px;align-items:center"><input id="roofReviewBoundaryConfirmed" type="checkbox" style="width:auto" onchange="updateReviewedRoofUi()">I checked every edge. This outline covers exactly the intended building roof, with no ground or neighbouring roofs included.</label><div id="roofReviewDraft" class="small"></div>';
 if(source==='trace'){
  const warning=el('roofRemeasurePitch').querySelector('.warning');warning.innerHTML='<b>Review your latest roof boundary.</b><br>Your latest manual trace is used, not the original detected outline. Check every edge. This method uses ONE verified uniform pitch. If slopes differ, cancel; this shortcut cannot measure mixed pitches.';
 }
 if(matches.length){const notice=document.createElement('label');notice.style.display='block';notice.innerHTML='<input id="roofReviewReplaceManualConfirmed" type="checkbox" style="width:auto" onchange="updateReviewedRoofUi()"> Replace these overlapping saved manual traces with this ONE reviewed roof when I save: '+matches.map(i=>'M'+(i+1)+' ('+fmt(manualPlanes[i].surface_sqft)+' ft²)').join(', ')+'. Cancel keeps them unchanged.';el('roofRemeasurePitch').append(notice)}
 el('manualRoofHelp').textContent='Drag the numbered corners to correct this roof boundary. Use START OVER to draw a new boundary. The original roof stays unchanged until you save.';
 el('tracePitchControl').style.display='none';el('undoTraceBtn').style.display='none';el('clearManualBtn').style.display='';
 el('traceBtn').textContent='CANCEL OUTLINE REVIEW';el('finishTrace').textContent='SAVE REVIEWED ROOF & PITCH';el('traceBanner').textContent='REVIEW '+roof.label+' — check outline and verified uniform pitch';
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
 if(el('manualPitchLabel'))el('manualPitchLabel').childNodes[0].nodeValue='Roof pitch — defaults to 5/12; change if needed ';el('finishTrace').textContent='SAVE REPLACEMENT ROOF';el('traceBanner').textContent='REMEASURE '+roof.label+' — trace roof, confirm pitch, then save';
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
 if(el('garageGuide'))el('garageGuide').textContent=original.label+' remeasured — '+fmt(surface)+' ft² included. '+(remaining?'Other roofs still need remeasurement; check the Property Summary.':'To include another roof, click + ADD GARAGE / OTHER ROOF.');
 if(el('garageSavedConfirm'))el('garageSavedConfirm').style.display='none';
 if(clickMarker){try{map.removeLayer(clickMarker)}catch(e){}clickMarker=null}clicked=null;
 status(original.label+' remeasured — '+fmt(surface)+' ft² replaces the previous area. Roof count is unchanged.','ok');
}
function manualRoofPitchLabel(deg){return Number(deg)===0?'0/12 (flat)':pitchRiseLabel(deg)}
function manualRoofConfirmationBlocked(){return traceMode||!manualPlanes.length||manualPlanes.some(p=>!p.pitch_confirmed||!Number.isFinite(Number(p.pitch_degrees))||Number(p.pitch_degrees)<0||Number(p.pitch_degrees)>=80)||!!manualRoofGeometryError(manualPlanes)}
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
 el('estimateRoofSectionPicker')?.remove();
 const plane=manualPlanes[index],confirmed=!!el('manualRoofScopeConfirmed')?.checked;
 beginManualRoofSection();manualRoofEditIndex=index;manualRoofEditScopeConfirmed=confirmed;
 if(el('manualRoofScopeConfirmed'))el('manualRoofScopeConfirmed').checked=confirmed;
 const pitch=Number(plane.pitch_degrees),valid=plane.pitch_confirmed&&Number.isFinite(pitch)&&pitch>=0&&pitch<80;
 const option=Array.from(el('pitchSel').options).find(o=>o.value!==''&&o.value!=='custom'&&Number(o.value)===pitch);
 el('pitchSel').value=valid?(option?option.value:'custom'):'';
 el('pitchDeg').value=valid?String(pitch):'';el('pitchDeg').type=valid&&!option?'number':'hidden';
 syncMeasurementEditMapDragging();
 const points=manualPlanes[index].points.map(p=>L.latLng(p.lat??p[0],p.lng??p[1]));
 map.fitBounds(L.latLngBounds(points).pad(.2),{padding:[35,35],maxZoom:20.5,animate:false});
 points.forEach(addTracePoint);clearTempTrace();
 tracePoints.forEach((p,i)=>{const marker=L.marker(p,{draggable:true,autoPan:false,title:'Drag roof corner '+(i+1),icon:L.divIcon({className:'roof-edit-handle',html:'<span>'+(i+1)+'</span>',iconSize:[44,44],iconAnchor:[22,22]})}).addTo(map);marker.on('drag',()=>{tracePoints[i]=marker.getLatLng();redrawTraceLine()});marker.on('dragend',()=>{tracePoints[i]=marker.getLatLng();redrawTraceLine();renderSummary()});tempTraceLayers.push(marker)});
 redrawTraceLine();el('finishTrace').textContent='SAVE SECTION CHANGES';
 renderSummary();status('Drag the numbered corners, then Save Section Changes. The saved pitch is retained; change it only if needed. Cancel preserves the saved section.','ok');
}
function deleteManualRoofSection(index){
 if(!manualRoofQa()||traceMode||!manualPlanes[index])return;
 manualPlanes.splice(index,1);manualRoofInvalidateScope();redrawManualDisplayLayers();renderSummary();
}
function syncRoofNextAction(){
 const guided=manualRoofQa()&&!structures.length&&(measurementViewMode==='auto'||!sessionToken);
 document.body.classList.toggle('roof-guided',guided);
 document.querySelectorAll('.roof-next-action').forEach(n=>n.classList.remove('roof-next-action'));
 if(!guided){
  const panel=el('manualRoofSections');if(panel)panel.style.display=manualRoofQa()&&measurementViewMode==='auto'?'':'none';
  if(manualRoofQa()&&structures.length&&el('roofNextTitle')){
   const confirmed=!!el('manualRoofScopeConfirmed')?.checked;
   el('roofNextTitle').textContent=confirmed?'Pitches and included roofs confirmed':'Roof confirmation required';
   el('roofNextExplanation').textContent='Review the saved roof measurements and any repair instructions in Property Summary before confirming.';
   el('confirmRoofPitches').style.display=manualPlanes.length&&!traceMode&&!confirmed?'':'none';
   el('roofConfirmedState').style.display=confirmed?'':'none';
  }
  return;
 }
 if(el('manualRoofSections'))el('manualRoofSections').style.display='';
 document.body.classList.toggle('roof-drawing',traceMode);document.body.classList.toggle('roof-idle',!traceMode);
 const card=el('roofNextStep');if(!card)return;
 const confirmed=!!el('manualRoofScopeConfirmed')?.checked,has=manualPlanes.length>0;
 let title='',explanation='',target='',step=2,blocked=true;
 if(!sessionToken){title='Load the property to start';explanation='Enter the address, then select LOAD PROPERTY & TRACE ROOF.';target='propertyActionBtn';step=1;}
 else if(traceMode){
  const issue=tracePoints.length>=3?manualRoofGeometryError(manualPlanes.filter((_,i)=>i!==manualRoofEditIndex).concat([{points:tracePoints}])):'';
  title=tracePoints.length<3?'Trace this roof section':!replacementPitchIsChosen()?'Select this section’s pitch':manualRoofEditIndex!==null?'Save this section’s changes':'Save this roof section';target=tracePoints.length<3?'map':!replacementPitchIsChosen()?'pitchSel':'finishTrace';
  explanation=issue||(!replacementPitchIsChosen()?'Trace the roof corners and select this section’s actual pitch beside Save. The default 5/12 is not confirmed.':tracePoints.length<3?'Click at least three outside corners, then save this section.':'Check the outline and selected pitch, then save. Cancel keeps the previously saved sections.');
 }
 else if(!has){title='Trace the first roof section';explanation='Select TRACE FIRST ROOF, then click its outside corners on the aerial.';target='traceBtn';}
 else if(!confirmed){title='Roof confirmation required';explanation=manualRoofGeometryError(manualPlanes)||'Review each saved area and pitch above. Include every roof you are pricing, then confirm pitches and included roofs.';target='confirmRoofPitches';}
 else{
  const issue=quotePricingError();
  if(issue){title=/rate|price/i.test(issue)?'Enter this job’s price':'Review this job’s details';explanation=issue;target=/tax/i.test(issue)?'gst':'jobPrice';step=3;}
  else if(!(el('customerName')?.value||'').trim()){title='Add customer details';explanation='Enter the customer name in Step 4.';target='customerName';step=4;blocked=false;}
  else{title='Create the customer estimate';explanation='Review pricing and customer details, then create the estimate.';target='createEstimateBtn';step=5;blocked=false;}
 }
 el('roofNextTitle').textContent=title;el('roofNextExplanation').textContent=explanation;
 card.dataset.step=String(step);document.body.classList.toggle('roof-has-blocker',blocked);document.body.classList.toggle('roof-property-next',step===1);document.body.classList.toggle('roof-ready',step===5&&!blocked);
 const action=el('confirmRoofPitches');if(action){action.style.display=has&&!traceMode&&!confirmed?'':'none';action.disabled=confirmed||manualRoofConfirmationBlocked();}
 if(el('roofConfirmedState'))el('roofConfirmedState').style.display=confirmed&&!traceMode?'':'none';
 const trace=el('traceBtn');if(trace){trace.style.display=sessionToken?'':'none';trace.className=traceMode?'ghost':'secondary';trace.textContent=traceMode?'CANCEL SECTION':has?'ADD ROOF SECTION / GARAGE':'TRACE FIRST ROOF';}
 if(el('manualPitchLabel'))el('manualPitchLabel').childNodes[0].nodeValue='This section’s pitch ';
 if(el('finishTrace'))el('finishTrace').textContent=manualRoofEditIndex!==null?'SAVE SECTION CHANGES':'SAVE ROOF SECTION';
 if(el('propertyActionBtn'))el('propertyActionBtn').textContent='LOAD PROPERTY & TRACE ROOF';
 if(target&&el(target))el(target).classList.add('roof-next-action');
 if(blocked&&el('jsTotal'))el('jsTotal').textContent=has&&!traceMode&&!confirmed?'Roof confirmation required':title;
 for(let i=1;i<=5;i++){const node=el('progress'+i);if(!node)continue;node.classList.toggle('done',i<step);node.classList.toggle('current',i===step);const number=node.querySelector('.stepnum');if(number)number.textContent=i<step?'✓':String(i);}
 const statusNode=el('status'),message=statusNode?.textContent||'';
 if(statusNode)statusNode.classList.toggle('roof-task-status',message===explanation||/^(Trace each roof section|Roof traced|Manual trace cancelled|Manual measurement ON|Added-roof trace ON|Roof section changes saved|Drag corners|Select and confirm the pitch|Property aerial loaded|Manual measurement mode is ready|✓.*roof)/i.test(message));
}
function syncManualRoofQa(){
 if(el('pitchSel')&&!el('pitchSel').querySelector('option[value="0"]')){const o=document.createElement('option');o.value='0';o.textContent='0/12 — Flat';el('pitchSel').append(o)}
 if(el('pitchReminder'))el('pitchReminder').textContent='Confirm the actual pitch of this section before saving. Different pitches require separate sections.';
 for(const id of ['toolAutoBtn','areaAutoBtn','linearAutoBtn','roofCheckCard','advancedOptions'])if(el(id))el(id).style.display='none';
 if(el('toolAreaBtn')){if(el('toolAreaBtn').querySelector('b'))el('toolAreaBtn').querySelector('b').textContent='TRACE ROOF';el('toolAreaBtn').disabled=traceMode}
 if(el('toolLinearBtn'))el('toolLinearBtn').disabled=traceMode;
 if(el('propertyActionBtn'))el('propertyActionBtn').textContent='LOAD PROPERTY';
 const details=el('manualRoofDetails');if(details){const anchor=details._roofWorkspaceAnchor;if(anchor&&details.parentNode!==anchor.parentNode)anchor.parentNode.insertBefore(details,anchor.nextSibling);details.open=true}
 if(el('manualRoofSummary'))el('manualRoofSummary').textContent='Trace roof sections → Confirm pitches → Review estimate';
 if(el('garageControls'))el('garageControls').style.display='none';
 if(el('garageGuide'))el('garageGuide').textContent='Load the property, then trace the main house and any other included roofs.';
 if(el('manualRoofWarning'))el('manualRoofWarning').textContent='Trace each roof section with its actual pitch. Include the main house and any garages or other roofs you are quoting.';
 if(el('manualRoofHelp'))el('manualRoofHelp').textContent=traceMode?'Trace one roof section with a single pitch. Confirm its pitch before saving. Add other slopes and garages separately.':'Use ADD ROOF SECTION / GARAGE to trace the main house and other included roofs. Select each section’s actual pitch before saving.';
 if(el('traceBtn'))el('traceBtn').textContent=traceMode?'CANCEL SECTION':'ADD ROOF SECTION / GARAGE';
 let panel=el('manualRoofSections');if(!panel){panel=document.createElement('div');panel.id='manualRoofSections';details.after(panel)}
 const confirmed=!!el('manualRoofScopeConfirmed')?.checked;
 panel.replaceChildren();
 manualPlanes.forEach((p,i)=>{const row=document.createElement('div');row.className='structure';const text=document.createElement('span');text.textContent='Roof section '+(i+1)+' · '+fmt(p.surface_sqft)+' ft² · '+manualRoofPitchLabel(p.pitch_degrees)+' pitch ';row.append(text);for(const [label,fn] of [['EDIT',editManualRoofSection],['DELETE',deleteManualRoofSection]]){const b=document.createElement('button');b.type='button';b.className='ghost';b.textContent=label;b.disabled=traceMode;b.onclick=()=>fn(i);row.append(b)}panel.append(row)});
 // Retain the persisted confirmation field for saved drafts; the visible action is a button.
 const check=document.createElement('input');check.type='checkbox';check.id='manualRoofScopeConfirmed';check.checked=confirmed;check.hidden=true;check.style.display='none';panel.append(check);
 const confirmation=document.createElement('div');confirmation.id='roofNextStep';confirmation.setAttribute('role','status');confirmation.setAttribute('aria-live','polite');
 const title=document.createElement('strong');title.id='roofNextTitle';confirmation.append(title);
 const help=document.createElement('p');help.id='roofNextExplanation';confirmation.append(help);
 const state=document.createElement('span');state.id='roofConfirmedState';state.className='good';state.textContent='✓ Pitches and included roofs confirmed';confirmation.append(state);
 const action=document.createElement('button');action.id='confirmRoofPitches';action.type='button';action.className='primarybig';action.textContent='Confirm pitches and included roofs';action.setAttribute('aria-pressed',String(confirmed));action.disabled=confirmed||manualRoofConfirmationBlocked();action.onclick=()=>{if(manualRoofConfirmationBlocked())return;check.checked=true;renderSummary()};confirmation.append(action);panel.append(confirmation);
 syncRoofNextAction();
}
function toggleTrace(forReplacement=false){if(manualRoofQa()&&!traceMode){el('pitchSel').value='';el('pitchDeg').value='';manualRoofInvalidateScope()}if(!traceMode&&!forReplacement&&structures.some(st=>st.needs_remeasure||st.automatic_review_warning)){status('To correct a flagged roof, use FIX ROOF in its Property Summary row. This keeps the replacement linked to that roof instead of adding another measurement.','warn');return}if(traceMode){cancelCurrentTrace();renderSummary();status('Manual trace cancelled.','ok');return}if(linearMode)stopLinearMode(false);const mainManual=(manualOverrideMode||fallbackMode)&&structures.length===0&&manualPlanes.length===0;setManualUi(mainManual);traceMode=true;tracePoints=[];clearTempTrace();setTraceControls(true);if(el('manualRoofHelp'))el('manualRoofHelp').innerHTML=mainManual?'Trace the MAIN HOUSE only.':'Trace only the garage or other roof you want to add. The main house stays unchanged.';if(!window.sgPitchReminderShown&&el('pitchReminder')){el('pitchReminder').style.display='block';window.sgPitchReminderShown=true;setTimeout(()=>{if(el('pitchReminder'))el('pitchReminder').style.display='none'},7000)}el('traceBtn').textContent='CANCEL TRACE';el('traceBtn').className='danger';el('traceBanner').style.display='block';el('finishTrace').disabled=true;status(mainManual?'Manual measurement ON — click the outside corners of the MAIN HOUSE.':'Added-roof trace ON — click the outside corners of the garage or other roof.','warn');syncRoofWorkspace();if(manualRoofQa())renderSummary()}
function addTracePoint(ll){if(roofOutlineReviewMode){status('Drag the numbered corners to correct this outline. Cancel and use Remeasure This Roof to draw a different boundary.','warn');return}tracePoints.push(ll);let n=tracePoints.length,pt=L.marker(ll,{interactive:false,icon:L.divIcon({className:'',html:`<div class="point-label">${n}</div>`,iconAnchor:[12,12]})}).addTo(map);tempTraceLayers.push(pt);redrawTraceLine();const ready=tracePoints.length>=3;el('finishTrace').disabled=!ready;if(ready){const action=roofRemeasureTarget?'SAVE REPLACEMENT ROOF':((manualOverrideMode||fallbackMode)&&structures.length===0&&manualPlanes.length===0)?'FINISH MEASUREMENT':'SAVE & ADD ROOF';if(el('manualRoofHelp'))el('manualRoofHelp').innerHTML=`<b>✓ Roof traced.</b> Confirm the pitch, then click <b>${action}</b>.`;status('Roof traced — confirm pitch, then save.','ok')}updateManualReplacementUi();if(manualRoofQa())syncRoofNextAction()}
function redrawTraceLine(){tempTraceLayers.filter(x=>x._traceLine).forEach(x=>map.removeLayer(x));tempTraceLayers=tempTraceLayers.filter(x=>!x._traceLine);if(tracePoints.length>=2){let c=[...tracePoints];if(tracePoints.length>=3)c.push(tracePoints[0]);let l=L.polyline(c,{color:'#d97706',weight:4,dashArray:'6,5'}).addTo(map);l._traceLine=true;tempTraceLayers.push(l)}}
function clearTempTrace(){tempTraceLayers.forEach(x=>{try{map.removeLayer(x)}catch(e){}});tempTraceLayers=[];if(traceSavePopup){try{map.closePopup(traceSavePopup)}catch(e){}traceSavePopup=null}}
function cancelCurrentTrace(){if(manualRoofQa()){if(manualRoofEditScopeConfirmed!==null&&el('manualRoofScopeConfirmed'))el('manualRoofScopeConfirmed').checked=manualRoofEditScopeConfirmed;manualRoofEditIndex=null;manualRoofEditScopeConfirmed=null;}el('traceBtn')?.closest('.manualrow')?.classList.remove('roof-replacement-row');if(el('manualRoofSaveFeedback'))el('manualRoofSaveFeedback').remove();const restoreRoofDisplay=!!roofRemeasureTarget;if(restoreRoofDisplay){el('pitchSel').value='22.62';el('pitchDeg').value='22.62';el('pitchDeg').type='hidden'}roofOutlineReviewMode=false;roofReviewBoundarySource='detected';roofReviewManualIndices=[];roofRemeasureTarget=null;if(el('roofRemeasurePitch'))el('roofRemeasurePitch').style.display='none';traceMode=false;tracePoints=[];clearTempTrace();setTraceControls(false);const mainManual=(manualOverrideMode||fallbackMode)&&structures.length===0&&manualPlanes.length===0;el('traceBtn').textContent=mainManual?'START MAIN HOUSE MEASUREMENT':'ADD / REMEASURE GARAGE OR OTHER ROOF';el('traceBtn').className='orange';el('traceBanner').style.display='none';el('finishTrace').textContent=mainManual?'FINISH MEASUREMENT':'SAVE & ADD ROOF';el('finishTrace').disabled=true;if(restoreRoofDisplay){redrawRoofData();redrawManualDisplayLayers();renderSummary()}syncRoofWorkspace()}
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
     lab=L.marker(c,{interactive:false,icon:L.divIcon({className:'',html:`<div class="manual-label">M${manualPlanes.length} • ${pitch.toFixed(1)}° • ${fmt(surface)} ft²</div>`,iconAnchor:[65,10]})}).addTo(map);
 manualLayers.push(poly,lab);drawEdgeMeasurements(plane.points,'#d97706',map,manualLayers,true);
 cancelCurrentTrace();
 const pureManual=structures.length===0;
 if(el('measureSource'))el('measureSource').value=pureManual?'manual':'hybrid';
 renderSummary();
 if(pureManual&&manualPlanes.length===1){setManualCorrectionLayout(false);setManualUi(false);if(el('garageGuide'))el('garageGuide').innerHTML='<b>Main house measured manually.</b> If there is another building to include, click <b>+ ADD GARAGE / OTHER ROOF</b>.';if(el('measureClickedTop'))el('measureClickedTop').disabled=false;if(el('measureClicked'))el('measureClicked').disabled=false;}
 status(pureManual?`✓ MANUAL ROOF SAVED — ${fmt(manualTotal())} ft² total. Add another roof if needed.`:`✓ MISSING ROOF ADDED — ${fmt(surface)} ft² added. New estimate area: ${fmt(googleTotal()+manualTotal())} ft².`,'ok');
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
  if(manualPlanes.length&&manualPlanes.some(p=>p.manual_roof_qa)&&!el('manualRoofScopeConfirmed')?.checked)return 'Review each saved roof section’s pitch, then select “Confirm pitches and included roofs” beside the saved sections to continue.';
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
  if(!savedAreas&&!commercialHasLinear()&&!valid(el('jobPrice')?.value))return 'Enter this job’s rate. Use 0 only for an intentionally free service.';
 }else{
  if((!savedAreas||measurementViewMode==='linear')&&!valid(el('jobPrice')?.value))return 'Enter this job’s rate. Use 0 only for an intentionally free service.';
  if(savedAreas&&linearMeasurementSaved&&!valid(surfaceLinearJobRate()))return 'Enter a linear service rate of 0 or more.';
  for(const [combined,id] of [[landscapingCombined(),'landscapingAreaRate'],[pressureCombined(),'pressureAreaRate'],[pavingCombined(),'pavingAreaRate']])if(combined&&!savedAreas&&!valid(el(id)?.value))return 'Enter an area service rate of 0 or more.';
 }
 const geometryIssue=savedAreaGeometryError();if(geometryIssue)return geometryIssue;
 const totals=calc||priceCalc();
 if(['subtotal','extraAmount','taxBase','gstAmt','pstAmt','total'].some(key=>!Number.isFinite(totals[key])||totals[key]<0))return 'Review the prices and taxes. The estimate must have valid, non-negative amounts.';
 return '';
}
function updateQuotePricingValidation(calc){
 const issue=quotePricingError(calc),label=/Confirm pitches and included roofs|roof section/.test(issue)?'Roof confirmation required':/outline|overlap|quantity/.test(issue)?'Measurement review required':'Price required';let box=el('quotePricingError');
 if(!box){box=document.createElement('div');box.id='quotePricingError';box.className='warning';box.setAttribute('role','alert');el('createEstimateBtn')?.before(box)}
 box.textContent=issue;box.style.display=issue?'block':'none';
 if(issue){
  if(el('createEstimateBtn'))el('createEstimateBtn').disabled=true;
  if(el('jsTotal'))el('jsTotal').textContent=label;
  el('summary')?.querySelectorAll('.price-summary,.estimate').forEach(preview=>{preview.innerHTML='<h3>'+label+'</h3><div class="warning">'+escapeHistory(issue)+'</div>'});
 }
}
function currentJobPrice(){const jp=el('jobPrice');const raw=jp?jp.value:'';const v=parseFloat(raw);if(Number.isFinite(v)&&v>=0)return v;const fallback=parseFloat((el('price')&&el('price').value)||0);return Number.isFinite(fallback)&&fallback>=0?fallback:0}
// Decimal inputs, integer arithmetic, ROUND_HALF_UP to cents: mirrors pricing_integrity.calculate.
function decimalCurrency(operation,values,factor=1){const ten=n=>10n**BigInt(n),decimal=value=>{if(!Number.isFinite(Number(value)))return null;const m=String(value).trim().match(/^([+-]?)(\d*)(?:\.(\d*))?(?:e([+-]?\d+))?$/i);if(!m||!(m[2]||m[3]))return null;let n=BigInt((m[2]||'0')+(m[3]||''))*(m[1]==='-'?-1n:1n),scale=(m[3]||'').length-Number(m[4]||0);if(scale<0){n*=ten(-scale);scale=0}return[n,scale]},add=(a,b)=>{if(!a||!b)return null;const scale=Math.max(a[1],b[1]);return[a[0]*ten(scale-a[1])+b[0]*ten(scale-b[1]),scale]},multiply=(a,b)=>a&&b?[a[0]*b[0],a[1]+b[1]]:null,round=(a,b=[1n,0])=>{if(!a||!b||!b[0])return NaN;let numerator=a[0]*ten(b[1]+2),denominator=b[0]*ten(a[1]);const sign=(numerator<0n)!==(denominator<0n)?-1n:1n;numerator=numerator<0n?-numerator:numerator;denominator=denominator<0n?-denominator:denominator;const cents=numerator/denominator+(numerator%denominator*2n>=denominator?1n:0n);return Number(sign*cents)/100},v=values.map(decimal);if(v.some(n=>!n))return NaN;if(operation==='sum')return round(v.reduce(add,[0n,0]));if(operation==='product')return round(v.reduce(multiply,[1n,0]));if(operation==='quantityProduct')return round(multiply(v.reduce(add,[0n,0]),decimal(factor)));if(operation==='percent')return round(multiply(v[0],v[1]),[100n,0]);if(operation==='includedBase')return round(multiply(v[0],[100n,0]),add(add([100n,0],v[1]),v[2]));return NaN}
function priceCalc(){if(commercialActive()&&areaMeasurementSaved)commercialSyncCurrent();let linearActive=measurementViewMode==='linear',areaActive=measurementViewMode==='area',area=linearActive?linearFeetTotal():(areaActive?(multiAreaSaved()?multiAreaTotal():Math.round(areaSqFtTotal())):estimateArea()),price=currentJobPrice(),mode=el('pricingMode').value,disc=Number(el('discountPct').value||0),gst=Number(el('gst').value||0),pst=Number(el('pst').value||0),subtotal=0,extraDescription=(el('extraServiceDescription')?.value||'').trim(),extraAmount=Math.max(0,Number(el('extraServiceAmount')?.value||0)),discount=0,taxBase=0,gstAmt=0,pstAmt=0,total=0;let charges=[];if(savedSurfaceHasAreas()||(currentBusinessType()==='commercial'&&(commercialHasAreas()||commercialHasLinear()))){charges=commercialAreas.filter(a=>a.sqft>0).map(a=>decimalCurrency('product',[a.sqft,a.rate]));if(linearMeasurementSaved&&linearPoints.length>1)charges.push(decimalCurrency('product',[linearFeetTotal(),currentBusinessType()==='commercial'?commercialLinearRate():surfaceLinearJobRate()]))}else if(landscapingCombined()||pressureCombined()||pavingCombined()){const areaRate=landscapingCombined()?landscapingAreaRate():pressureCombined()?pressureAreaRate():pavingAreaRate();charges=[decimalCurrency('product',[Math.round(multiAreaSaved()?multiAreaTotal():areaSqFtTotal()),areaRate]),decimalCurrency('product',[linearFeetTotal(),price])]}else charges=[decimalCurrency('product',[area,price])];if(!linearActive&&!areaActive&&currentBusinessType()==='roofing'&&typeof structures!=='undefined'&&typeof manualPlanes!=='undefined'){const source=el('measureSource')?.value||'google',auto=structures.map(r=>r.total_roof_sqft),manual=manualPlanes.map(p=>p.surface_sqft),quantities=source==='hybrid'?auto.concat(manual):source==='manual'?(manual.length?manual:auto):source==='adjusted'?[el('adjustedArea')?.value]:auto;charges=[decimalCurrency('quantityProduct',quantities,price)]};subtotal=decimalCurrency('sum',charges);taxBase=decimalCurrency('sum',[subtotal,extraAmount]);if(mode==='discount'){discount=decimalCurrency('percent',[subtotal,disc]);taxBase=decimalCurrency('sum',[subtotal,-discount,extraAmount]);gstAmt=decimalCurrency('percent',[taxBase,gst]);pstAmt=decimalCurrency('percent',[taxBase,pst]);total=decimalCurrency('sum',[taxBase,gstAmt,pstAmt])}else if(mode==='included'){total=decimalCurrency('sum',[subtotal,extraAmount]);taxBase=decimalCurrency('includedBase',[total,gst,pst]);gstAmt=decimalCurrency('percent',[taxBase,gst]);pstAmt=decimalCurrency('percent',[taxBase,pst]);taxBase=decimalCurrency('sum',[total,-gstAmt,-pstAmt])}else{taxBase=decimalCurrency('sum',[subtotal,extraAmount]);gstAmt=decimalCurrency('percent',[taxBase,gst]);pstAmt=decimalCurrency('percent',[taxBase,pst]);total=decimalCurrency('sum',[taxBase,gstAmt,pstAmt])}if(multiAreaSaved())area=multiAreaTotal();return{estimatePeriod:estimatePeriodValue(),area,price,mode,disc,subtotal,extraDescription,extraAmount,discount,taxBase,gst,pst,gstAmt,pstAmt,total,measurementMode:linearActive?'linear':(areaActive?'area':'auto'),unit:(commercialHasAreas()||savedSurfaceHasAreas())?'ft²':(linearActive?'linear ft':'ft²')}}
function roofQuoteNeedsReview(){return currentBusinessType()==='roofing'&&measurementViewMode==='auto'&&structures.some(st=>st.needs_remeasure||st.automatic_review_warning)}
function confidence(){if(structures.some(st=>st.needs_remeasure))return ['The automatic roof is incomplete. Select TRACE ROOF MANUALLY before creating the estimate.'];return structures.some(st=>st.automatic_review_warning)?['Roof area and outline may cover different scopes. Use the roof action beside the aerial before creating an estimate.']:[]}
function pitchLabel(deg){const d=Number(deg||0);if(!d)return '—';const rise=12*Math.tan(d*Math.PI/180);const rounded=Math.round(rise*2)/2;return `${d.toFixed(1)}° (approx. ${Number.isInteger(rounded)?rounded.toFixed(0):rounded.toFixed(1)}/12)`}
function pitchRiseLabel(deg){const d=Number(deg||0);if(!d)return '—';const rise=12*Math.tan(d*Math.PI/180);const rounded=Math.round(rise*2)/2;return `${Number.isInteger(rounded)?rounded.toFixed(0):rounded.toFixed(1)}/12`}
function structurePitchSummary(st){if(!st||!st.segments||!st.segments.length)return {complex:false,label:'—',detail:''};const vals=st.segments.map(x=>Number(x.pitch_degrees||0)).filter(x=>x>0);if(!vals.length)return {complex:false,label:'—',detail:''};const avg=vals.reduce((a,b)=>a+b,0)/vals.length,min=Math.min(...vals),max=Math.max(...vals);const rises=[...new Set(vals.map(pitchRiseLabel))];const complex=vals.length>=6&&(max-min>=8||rises.length>=3);if(complex)return {complex:true,label:'Multiple Roof Pitches',detail:`${pitchRiseLabel(min)}–${pitchRiseLabel(max)} (${min.toFixed(1)}°–${max.toFixed(1)}°)`};return {complex:false,label:pitchLabel(avg),detail:`${st.manually_measured?'Confirmed pitch from':'Average of'} ${vals.length} ${st.manually_measured?'traced':'Google'} roof segment${vals.length===1?'':'s'}`}}
function updateJobSummaryBar(calc,roofCount){
 const p=el('jsProperty'),r=el('jsRoofs'),a=el('jsArea'),t=el('jsTotal');if(!p||!r||!a||!t)return;
 const full=(el('address')&&el('address').value?el('address').value:'').trim();
 const typed=[el('streetAddress')?.value,el('cityTown')?.value,el('propertyProvince')?.value].filter(Boolean).join(', ');
 p.textContent=full||typed||'No property loaded';
 const has=calc&&Number(calc.area)>0;
 const summaryLabel=r.previousElementSibling;if(summaryLabel&&['pressure','paving','landscaping','commercial','snow'].includes(currentBusinessType()))summaryLabel.textContent=currentBusinessType()==='landscaping'?'SERVICE AREAS':'SURFACES';else if(summaryLabel)summaryLabel.textContent='ROOFS';
 r.textContent=['pressure','paving','landscaping','commercial','snow'].includes(currentBusinessType())?(multiAreaSaved()?String(commercialAreas.filter(a=>a.sqft>0).length):(areaMeasurementSaved&&areaPoints.length>=3?'1':'—')):(has?String(roofCount||1):'—');
 const savedSurfaceArea=multiAreaSaved()?multiAreaTotal():(areaMeasurementSaved&&areaPoints.length>=3?Math.round(areaSqFtTotal()):0);
 const savedLinearLength=linearMeasurementSaved&&linearPoints.length>=2?linearFeetTotal():0;
 a.textContent=savedSurfaceArea>0?fmt(savedSurfaceArea)+' ft²'+(savedLinearLength>0?' • '+savedLinearLength.toFixed(1)+' linear ft':''):(measurementViewMode==='linear'&&savedLinearLength>0?savedLinearLength.toFixed(1)+' linear ft':has?fmt(calc.area)+' ft²':'—');
 if(surfaceIndustry()&&(areaMode||linearMode||linearCorrectionOriginal)){a.textContent=savedSurfaceArea>0?fmt(savedSurfaceArea)+' ft² saved':'Unsaved drawing';t.textContent='Save measurement';return}
 if(roofQuoteNeedsReview()){a.textContent='Unverified roof area';t.textContent='Review required';return}
 t.textContent=has?money(calc.total):'—';
}
function updateProgressSteps(){
 const measured=priceCalc().area>0&&!roofQuoteNeedsReview()&&(!surfaceIndustry()||(!areaMode&&!linearMode&&!linearCorrectionOriginal&&(areaMeasurementSaved||multiAreaSaved()||linearMeasurementSaved)));
 const verified=!!(el('propertyVerify')&&el('propertyVerify').style.display!=='none'&&(el('propertyVerify').textContent||'').includes('verified'));
 const customerReady=!!((el('customerName')?.value||'').trim());
 const estimateOpen=document.body.classList.contains('report-open');
 let current=1;if(verified)current=2;if(measured)current=3;if(measured&&customerReady)current=5;if(estimateOpen)current=5;
 for(let i=1;i<=5;i++){const c=el('progress'+i);if(!c)continue;c.classList.remove('done','current');const n=c.querySelector('.stepnum');if(i<current){c.classList.add('done');if(n)n.textContent='✓'}else if(i===current){c.classList.add('current');if(n)n.textContent=String(i)}else{if(n)n.textContent=String(i)}}
 // Price is complete once a valid measured quote exists; Customer becomes current before Estimate.
 if(measured&&!customerReady){const p3=el('progress3'),p4=el('progress4');if(p3){p3.classList.add('done');p3.classList.remove('current');const n=p3.querySelector('.stepnum');if(n)n.textContent='✓'}if(p4){p4.classList.add('current');const n=p4.querySelector('.stepnum');if(n)n.textContent='4'}}
 if(manualRoofQa())syncRoofNextAction();
}
function updatePriceUnitUi(){const linear=measurementViewMode==='linear';if(linear&&commercialHasLinear()&&el('jobPrice')&&el('commercialLinearRate'))el('jobPrice').value=el('commercialLinearRate').value;if(el('jobPriceCard'))el('jobPriceCard').style.display='';if(el('jobPriceLabel'))el('jobPriceLabel').innerHTML=linear?'Price for This Job / linear ft. <span class="info-tip" tabindex="0" data-tip="Set the price charged for each linear foot measured.">ⓘ</span>':'Price for This Job / sq. ft. <span class="info-tip" tabindex="0" data-tip="Your dealer default loads here automatically. Change this number for any individual job and the quote recalculates immediately.">ⓘ</span>';if(el('jobPriceHelp'))el('jobPriceHelp').textContent=linear?'This price is multiplied by the saved linear footage for this job.':'This is the price used for the quote. Change it anytime before creating the estimate.';}

// These are views of the existing job rates, never dealer-profile defaults.
function step3LinearRateChanged(value){
 if(currentBusinessType()==='commercial'){el('commercialLinearRate').value=value}
 else {savedLinearJobRate=String(value).trim()===''?'':Number(value);if(measurementViewMode==='linear')el('jobPrice').value=value}
 renderSummary();
}
function updateStep3Rates(){
 const box=el('step3MeasurementRates');if(!box)return;
 const areas=surfaceIndustry()?commercialAreas.map((a,i)=>({a,i})).filter(x=>x.a.sqft>0):[];
 const line=surfaceIndustry()&&linearMeasurementSaved&&linearPoints.length>1;
 const managed=areas.length>0||(currentBusinessType()==='commercial'&&line);
 if(el('jobPriceCard'))el('jobPriceCard').style.display='';
 for(const id of ['jobPriceLabel','jobPrice'])if(el(id))el(id).style.display=managed?'none':'';
 box.style.display=managed?'':'none';
 const signature=JSON.stringify([areas.map(({a,i})=>[i,a.name,a.sqft]),line]);
 if(managed&&box.dataset.signature!==signature){
  box.innerHTML=areas.map(({a,i})=>`<label for="step3AreaRate${i}">${escapeHistory(a.name||'Service Area '+(i+1))} — $/sq. ft.</label><input id="step3AreaRate${i}" data-step3-area-rate="${i}" type="number" min="0" step="0.01" oninput="commercialAreaField(${i},'rate',this.value)">`).join('')+(line?'<label for="step3LinearRate">Linear measurement — $/linear ft.</label><input id="step3LinearRate" type="number" min="0" step="0.01" oninput="step3LinearRateChanged(this.value)">':'');
  box.dataset.signature=signature;
 }
 const sync=(input,value)=>{if(input&&document.activeElement!==input)input.value=value??''};
 areas.forEach(({a,i})=>{
  sync(el('step3AreaRate'+i),a.rate);
  document.querySelectorAll('[data-area-job-rate="'+i+'"]').forEach(input=>{sync(input,a.rate);const amount=input.closest('.surface-area-price')?.querySelector('b');if(amount)amount.textContent=a.rate!==null&&a.rate!==''&&Number.isFinite(Number(a.rate))&&Number(a.rate)>=0?money(decimalCurrency('product',[a.sqft,a.rate])):'Rate required'});
 });
 if(managed&&line)sync(el('step3LinearRate'),currentBusinessType()==='commercial'?el('commercialLinearRate').value:surfaceLinearJobRate());
 if(el('jobPriceHelp')&&managed)el('jobPriceHelp').textContent="Change this job's rates here or beside its measurements. Dealer defaults and older saved versions stay unchanged.";
}

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
function renderSummary(){try{recordFirstMeasurement();updateMeasurementInterface();if(currentBusinessType()==='paving'&&!el('pavingAreaRate')){const anchor=el('summary');if(anchor){const d=document.createElement('div');d.id='pavingAreaPriceBox';d.innerHTML='<label for="pavingAreaRate">Paving area rate ($ / sq. ft.)</label> <input id="pavingAreaRate" type="number" min="0" step="0.01" value="0" oninput="if(measurementViewMode===\'area\'&&el(\'jobPrice\'))el(\'jobPrice\').value=this.value;renderSummary()">';anchor.parentNode.insertBefore(d,anchor)}}if(el('pavingAreaPriceBox'))el('pavingAreaPriceBox').style.display=currentBusinessType()==='paving'&&measurementViewMode==='linear'&&!savedSurfaceHasAreas()?'block':'none';if(currentBusinessType()==='pressure'&&!el('pressureAreaRate')){const anchor=el('summary');if(anchor){const d=document.createElement('div');d.id='pressureAreaPriceBox';d.innerHTML='<label for="pressureAreaRate"><b>Pressure Washing area service rate ($ / sq. ft.)</b></label> <input id="pressureAreaRate" type="number" min="0" step="0.01" value="0" placeholder="Enter rate" style="width:105px;padding:7px" oninput="renderSummary()"><div class="small">Set your area rate. When area and linear measurements are both saved, both services are included in the estimate.</div>';anchor.parentNode.insertBefore(d,anchor)}}if(el('pressureAreaPriceBox'))el('pressureAreaPriceBox').style.display=currentBusinessType()==='pressure'&&measurementViewMode==='linear'&&!savedSurfaceHasAreas()?'block':'none';if(currentBusinessType()==='landscaping'&&!el('landscapingAreaRate')){const anchor=el('summary');if(anchor){const d=document.createElement('div');d.id='landscapingAreaPriceBox';d.innerHTML='<label for="landscapingAreaRate"><b>Landscaping area service rate ($ / sq. ft.)</b></label> <input id="landscapingAreaRate" type="number" min="0" step="0.01" value="0.15" style="width:105px;padding:7px" oninput="if(measurementViewMode===\'area\'&&el(\'jobPrice\'))el(\'jobPrice\').value=this.value;renderSummary()"><div class="small">When area and linear measurements are both saved, the area rate and linear job rate are added together.</div>';anchor.parentNode.insertBefore(d,anchor)}}if(el('landscapingAreaPriceBox'))el('landscapingAreaPriceBox').style.display=currentBusinessType()==='landscaping'&&measurementViewMode==='linear'&&!savedSurfaceHasAreas()?'block':'none';if(currentBusinessType()==='commercial'&&!el('commercialLinearRate')){const anchor=el('summary');if(anchor){const d=document.createElement('div');d.id='commercialLinearPriceBox';d.innerHTML='<label for="commercialLinearRate"><b>Commercial linear service rate ($ / linear ft)</b></label> <input id="commercialLinearRate" type="number" min="0" step="0.01" value="0.25" style="width:105px;padding:7px" oninput="renderSummary()"><div class="small">Saved linear and area measurements are combined on one commercial estimate.</div>';anchor.parentNode.insertBefore(d,anchor)}}if(el('commercialLinearPriceBox'))el('commercialLinearPriceBox').style.display=currentBusinessType()==='commercial'?'block':'none';if(commercialActive())commercialAreaUi();if(!el('summary'))return;updatePriceUnitUi();let g=googleTotal(),m=manualTotal(),coverage=Number(el('coverage').value||330),src=el('measureSource')?el('measureSource').value:'google',calc=priceCalc(),gallons=coverage?calc.area/coverage:0;let pureManual=src==='manual'&&m>0,hasMeasurement=calc.area>0,roofCount=pureManual?manualPlanes.length:structures.length+(src==='hybrid'?manualPlanes.length:0);if(measurementViewMode==='area'){const ready=areaMeasurementSaved&&areaPoints.length>=3&&calc.area>0&&(!commercialActive()||commercialAreas.every(a=>a.sqft>0));if(el('createEstimateBtn'))el('createEstimateBtn').disabled=!ready;updateJobSummaryBar(calc,1);let html=`<div class="measure-result-card"><div class="measure-result-head"><div><div class="measure-result-title">Area Measurement</div><div class="measure-result-value">${fmt(calc.area)} ft²</div></div>${ready?'<span class="measure-result-saved">✓ SAVED</span>':''}</div><div class="small" style="margin-top:8px">${ready?'This saved area is being used for the quote.':'Finish and save the area to use it for the quote.'} ${currentBusinessType()==='pressure'?'Only the saved cleaning surface is included in this price.':currentBusinessType()==='paving'?'Only the saved paved surface is included in this price.':currentBusinessType()==='landscaping'?'Only the saved landscaping area is included in this price.':'Area and linear measurements are saved with this quote.'}</div></div><div class="price-summary"><h3>Price</h3><div class="line"><span>${savedSurfaceHasAreas()?savedSurfacePriceLines({commercialAreas,linearFeet:linearMeasurementSaved?linearFeetTotal():0,landscapingLinearRate:surfaceLinearJobRate()}):pavingCombined()?pavingPriceLines():pressureCombined()?pressurePriceLines():landscapingCombined()?landscapingPriceLines():commercialHasAreas()?commercialPriceLines():`${fmt(calc.area)} ft² × ${money(calc.price)} / sq. ft.</span><b>${money(calc.subtotal)}</b></div>`}${calc.extraAmount>0?`<div class="line"><span>${escapeHistory(calc.extraDescription||'Additional Services / Repairs')}</span><b>${money(calc.extraAmount)}</b></div>`:''}${calc.discount?`<div class="line"><span>Promotion discount</span><b>-${money(calc.discount)}</b></div>`:''}${calc.mode==='included'?`<div class="line"><span>Pricing</span><b>Taxes Included</b></div>`:`<div class="line"><span>Sales Tax (${calc.gst}%)</span><b>${money(calc.gstAmt)}</b></div>${calc.pst?`<div class="line"><span>Additional Tax (${calc.pst}%)</span><b>${money(calc.pstAmt)}</b></div>`:''}`}<div class="line grand"><span>Total</span><span>${money(calc.total)}</span></div></div>${!ready?`<div class="warning"><b>Finish & save the area to continue.</b></div>`:''}`;el('summary').innerHTML=html;if(el('appliedJobPrice'))el('appliedJobPrice').innerHTML=savedSurfaceHasAreas()?`Quote uses <b>each saved area's rate</b>${linearMeasurementSaved?' + <b>'+money(surfaceLinearJobRate())+' / linear ft.</b>':''}`:(pressureCombined()||pavingCombined()||landscapingCombined())?`Quote is using <b>${money(pressureCombined()?pressureAreaRate():pavingCombined()?pavingAreaRate():landscapingAreaRate())} / sq. ft. (area)</b> + <b>${money(currentJobPrice())} / linear ft. (linear)</b>`:`Quote is using <b>${money(calc.price)} / sq. ft.</b>`;updateUsage();updateProgressSteps();return}if(measurementViewMode==='linear'){const ready=linearMeasurementSaved&&linearPoints.length>1&&linearFeetTotal()>0&&!linearCorrectionOriginal;if(el('createEstimateBtn'))el('createEstimateBtn').disabled=!ready;updateJobSummaryBar(calc,0);let html=`<div class="measure-result-card"><div class="measure-result-head"><div><div class="measure-result-title">Linear Measurement</div><div class="measure-result-value">${linearFeetTotal().toFixed(1)} linear ft</div></div>${ready?'<span class="measure-result-saved">✓ SAVED</span>':''}</div><div class="small" style="margin-top:8px">${ready?'This saved length is being used for the quote.':'Finish and save the line to use it for the quote.'} ${currentBusinessType()==='landscaping'?'Only the saved landscaping length is included in this price.':'Only the saved service measurements are included in this quote.'}</div></div><div class="price-summary"><h3>Price</h3><div class="line"><span>${savedSurfaceHasAreas()?savedSurfacePriceLines({commercialAreas,linearFeet:linearMeasurementSaved?linearFeetTotal():0,landscapingLinearRate:surfaceLinearJobRate()}):pavingCombined()?pavingPriceLines():pressureCombined()?pressurePriceLines():landscapingCombined()?landscapingPriceLines():commercialHasAreas()?commercialPriceLines():`${linearFeetTotal().toFixed(1)} ft × ${money(commercialHasLinear()?commercialLinearRate():calc.price)} / linear ft.</span><b>${money(calc.subtotal)}</b></div>`}${calc.extraAmount>0?`<div class="line"><span>${escapeHistory(calc.extraDescription||'Additional Services / Repairs')}</span><b>${money(calc.extraAmount)}</b></div>`:''}${calc.discount?`<div class="line"><span>Promotion discount</span><b>-${money(calc.discount)}</b></div>`:''}${calc.mode==='included'?`<div class="line"><span>Pricing</span><b>Taxes Included</b></div>`:`<div class="line"><span>Sales Tax (${calc.gst}%)</span><b>${money(calc.gstAmt)}</b></div>${calc.pst?`<div class="line"><span>Additional Tax (${calc.pst}%)</span><b>${money(calc.pstAmt)}</b></div>`:''}`}<div class="line grand"><span>Total</span><span>${money(calc.total)}</span></div></div>${!ready?`<div class="warning"><b>Finish & save the linear measurement to continue.</b></div>`:''}`;el('summary').innerHTML=html;if(el('appliedJobPrice'))el('appliedJobPrice').innerHTML=savedSurfaceHasAreas()?`Quote uses <b>each saved area's rate</b>${linearMeasurementSaved?' + <b>'+money(surfaceLinearJobRate())+' / linear ft.</b>':''}`:(pressureCombined()||pavingCombined()||landscapingCombined())?`Quote is using <b>${money(pressureCombined()?pressureAreaRate():pavingCombined()?pavingAreaRate():landscapingAreaRate())} / sq. ft. (area)</b> + <b>${money(currentJobPrice())} / linear ft. (linear)</b>`:`Quote is using <b>${money(commercialHasLinear()?commercialLinearRate():calc.price)} / linear ft.</b>`;updateUsage();updateProgressSteps();return}const roofReview=roofQuoteNeedsReview();if(el('createEstimateBtn'))el('createEstimateBtn').disabled=!hasMeasurement||roofReview||!!roofRemeasureTarget;updateJobSummaryBar(calc,roofCount);let mainPitch=structures.length?structurePitchSummary(structures[0]):null;let html=`<div class="section"><h3>Property Summary</h3><div class="metric-grid"><div class="metric">${roofReview?'Unverified Provider Area':pureManual?'Manual Roof Area':structures.some(st=>st.manually_measured)?'Measured Roof Area':'Google Roof Area'}<b>${fmt(pureManual?m:g)} ft²</b></div><div class="metric">Roofs in Quote<b>${roofCount}</b></div>${!pureManual&&mainPitch&&mainPitch.label!=='—'?`<div class="metric">${mainPitch.complex?'Roof Pitch':'Main Roof Pitch'}<b>${mainPitch.label}</b>${mainPitch.detail?`<span class="small" style="display:block;margin-top:3px">${mainPitch.detail}</span>`:''}</div>`:''}</div>${m&&!pureManual?`<div class="metric" style="margin-top:7px">Added Roof<b>+ ${fmt(m)} ft²</b></div>`:''}</div>`;structures.forEach((s,i)=>{let ps=structurePitchSummary(s);html+=`<div class="structure"><div class="structure-head"><div><span class="dot ${i===0?'house-dot':'garage-dot'}"></span><b>${structures.length>3?`#${i+1} · `:''}${s.label}</b></div><b>${s.needs_remeasure?'Needs remeasurement':s.automatic_review_warning?'Review required · '+fmt(s.total_roof_sqft)+' ft² unverified':fmt(s.total_roof_sqft)+' ft²'}</b></div>${currentBusinessType()==='roofing'?roofRowActionHtml(s,i):''}<div class="small">${s.manually_measured?roofMeasurementSourceLabel(s)+' • ':s.needs_remeasure?'Automatic coverage needs correction • area excluded • ':s.automatic_review_warning?'Automatic area and outline have mismatched scopes • ':''}${s.segment_count} ${s.manually_measured?(s.measurement_source?.startsWith('dealer_reviewed_')?'reviewed roof outline':'traced roof section'):'roof segments'} • ${ps.complex?`Multiple pitches ${ps.detail}`:`${s.manually_measured?'Confirmed':'Avg'} pitch ${ps.label}`}${s.manually_measured?'':` • ${s.imagery_quality||'—'} quality • Imagery ${s.imagery_date||'—'}`}</div>${s.manually_measured?'':automaticRoofReviewHtml(s)}</div>`});let suspiciousGoogleRoof=!pureManual&&structures.length===1&&g>0&&g<1000;if(suspiciousGoogleRoof){html+=`<div class="warning" style="margin-top:10px"><b>⚠ POSSIBLE INCOMPLETE ROOF MEASUREMENT</b><br>Google returned a small roof measurement. Trees, shadows or limited aerial imagery can sometimes prevent the entire roof from being identified. Review the aerial carefully before creating the estimate. If the full roof cannot be clearly identified, an on-site assessment may be required.</div>`}if(pureManual){manualPlanes.forEach((p,i)=>{html+=`<div class="structure"><div class="structure-head"><div><span class="dot manual-dot"></span><b>${manualPlanes.length===1?'Manual Roof':'Manual Roof '+(i+1)}</b></div><b>${fmt(p.surface_sqft)} ft²</b></div><div class="small">Dealer traced • ${manualRoofPitchLabel(p.pitch_degrees)} pitch${el('manualRoofScopeConfirmed')?.checked?' confirmed':' — confirmation required'}</div></div>`})}html+=`<div class="section"><h3>Quote Measurement</h3><input id="measureSource" type="hidden" value="${src}"><input id="adjustedArea" type="hidden" value="${src==='adjusted'?calc.area:''}"><div class="${hasMeasurement?'good':'warning'}"><b>${hasMeasurement?(structures.some(st=>st.manually_measured)?'✓ Roof measurement with dealer corrections — pitch included':src==='hybrid'?'✓ Google Measurement + Added Roof':src==='manual'?'✓ Dealer Manual Measurement':'✓ Google Automatic Measurement — pitch included'):'Manual measurement required'}</b><br>${hasMeasurement?(src==='hybrid'?`${fmt(g)} ft² measured + ${fmt(m)} ft² added = <b>${fmt(calc.area)} ft² total</b>`:`${fmt(calc.area)} ft² is being used for this estimate.`):'Trace the shingled roof around the customer property pin to unlock pricing and the customer estimate.'}${hasMeasurement&&src!=='manual'&&adjustedOutline?'<br><b>Customer outline adjusted — measurement and price unchanged.</b>':''}</div></div>`;html+=`<div class="section"><h3>Dealer-Only Calculation</h3><div class="calc"><div>Estimate measurement</div><div>${fmt(calc.area)} ft²</div><div>Coverage per gallon</div><div>${fmt(coverage)} ft²</div><div>Estimated product required</div><div>${gallons.toFixed(1)} gal</div><div>Price per sq. ft.</div><div>${money(calc.price)}</div></div></div><div class="estimate"><b>Dealer Estimate Preview</b><div class="line"><span>Subtotal before tax</span><b>${money(calc.taxBase)}</b></div>${calc.discount?`<div class="line"><span>Promotion discount</span><b>-${money(calc.discount)}</b></div>`:''}${calc.mode==='included'?`<div class="line"><span>Pricing</span><b>Taxes Included</b></div>`:`<div class="line"><span>Sales Tax (${calc.gst}%)</span><b>${money(calc.gstAmt)}</b></div>${calc.pst?`<div class="line"><span>Additional Tax (${calc.pst}%)</span><b>${money(calc.pstAmt)}</b></div>`:''}`}<div class="line grand"><span>Total Estimate</span><span>${money(calc.total)}</span></div></div>`;let w=confidence();html+=!hasMeasurement?`<div class="warning"><b>Finish the manual roof trace first.</b><br>Pricing and estimate creation stay locked until a roof area has been measured.</div>`:(w.length?`<div class="warning"><b>Review before sending:</b><br>${w.map(x=>'• '+x).join('<br>')}</div>`:`<div class="${manualRoofQa()&&!el('manualRoofScopeConfirmed')?.checked?'warning':'good'}"><b>${manualRoofQa()&&!el('manualRoofScopeConfirmed')?.checked?'Confirm pitches and included roofs to continue.':'Measurement looks ready.'}</b></div>`);if(roofReview){const reviewStart=html.indexOf('<div class="section"><h3>Quote Measurement</h3>');html=html.slice(0,reviewStart)+`<div class="section"><h3>Quote Measurement</h3><input id="measureSource" type="hidden" value="${src}"><input id="adjustedArea" type="hidden" value="${src==='adjusted'?calc.area:''}"><div class="warning"><b>REVIEW REQUIRED — estimate blocked</b><br>The provider area is unverified because it does not cover the same scope as the outline. No quote total or product quantity is ready. ${roofRemeasureTarget?'Finish editing '+escapeHistory(roofRemeasureTarget.label)+' using the controls beside the aerial. The price updates after you save.':'Use the roof action above the aerial to review or trace the roof.'}</div></div>`}el('summary').innerHTML=html;if(el('appliedJobPrice'))el('appliedJobPrice').innerHTML=savedSurfaceHasAreas()?`Quote uses <b>each saved area's rate</b>${linearMeasurementSaved?' + <b>'+money(surfaceLinearJobRate())+' / linear ft.</b>':''}`:(pressureCombined()||pavingCombined()||landscapingCombined())?`Quote is using <b>${money(pressureCombined()?pressureAreaRate():pavingCombined()?pavingAreaRate():landscapingAreaRate())} / sq. ft. (area)</b> + <b>${money(currentJobPrice())} / linear ft. (linear)</b>`:`Quote is using <b>${money(calc.price)} / sq. ft.</b>`;updateUsage();updateProgressSteps()}finally{updateQuotePricingValidation();updateEstimatePeriodUi();syncRoofNextAction();updateStep3Rates()}}

function resetReportForNewProperty(){
 document.body.classList.remove('report-open');
 const overlay=el('reportOverlay');if(overlay)overlay.style.display='none';
 if(customerMap){try{customerMap.remove()}catch(e){}customerMap=null}
 customerRgbLayer=null;customerOverlays=[];quoteSnapshot=null;reportOutlines={};reportOutlineTarget=null;reportOutlineEditMode=false;reportOutlinePoints=[];reportOutlineTemp=[];reportCloseArmedAt=0;estimateOpenInProgress=false;pdfInProgress=false;if(customerMapBuildTimer){clearTimeout(customerMapBuildTimer);customerMapBuildTimer=null}if(el('createEstimateBtn'))el('createEstimateBtn').disabled=false;if(el('downloadPdfBtn'))el('downloadPdfBtn').disabled=false;
 const report=document.querySelector('#reportOverlay .report');if(report)report.classList.remove('estimate-editing');
}
function resetMeasurementForNewProperty(){el('estimateRoofSectionPicker')?.remove();areaRemeasureMode=false;manualRoofEditIndex=null;manualRoofEditScopeConfirmed=null;manualRoofInvalidateScope();
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
 const m=s.match(/^([+-]?\d+(?:\.\d+)?)\s*(?:°\s*)?([NS])?\s*(?:,\s*|\s+)([+-]?\d+(?:\.\d+)?)\s*(?:°\s*)?([EW])?$/);
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
   if(msg){msg.textContent='Check the format — latitude first, longitude second. Example: 27.950575, -82.457178';msg.style.color='#a12622'}
   status('Could not read those coordinates. Check the example beside the field.','error');return;
 }
 const normalized=p.lat.toFixed(6)+', '+p.lng.toFixed(6);
 if(box)box.value=normalized;
 if(msg){msg.textContent='✓ Exact pin accepted: '+normalized;msg.style.color='#176b43'}
 if(el('streetAddress'))el('streetAddress').value=normalized;
 if(el('cityTown'))el('cityTown').value='';
 if(el('propertyProvince'))el('propertyProvince').value='';
 if(el('postalCode'))el('postalCode').value='';
 status('Loading the exact dropped-pin location…','warn');
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
  if(d.provider==='mapbox')ready=await loadFallbackAerial(d.token,staging,d.zoom??null);
  else if(surface||d.manual_roof_only){try{ready=await loadStandardWideAerial(d.token,staging,true,L.latLng(center.latitude,center.longitude))}catch(e){ready=d.exact_pin_display?await loadExactPinAerial(d.token,staging):await loadFallbackAerial(d.token,staging)}}
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
 syncWiderAerial();
}
function syncWiderAerial(){const b=el('widerMapboxAerial');if(b){b.hidden=fallbackLayer?._sgProvider!=='mapbox';b.disabled=!!widenMapboxAerial.inFlight||fallbackLayer?._sgZoom<=15}}
async function widenMapboxAerial(){
 if(widenMapboxAerial.inFlight||fallbackLayer?._sgProvider!=='mapbox')return;
 const token=sessionToken,zoom=fallbackLayer._sgZoom-1;
 if(zoom<15)return;
 widenMapboxAerial.inFlight=true;syncWiderAerial();let ready;
 try{
  const meta=await (await fetch('/fallback-meta/'+token)).json();
  ready=await preparePropertyImagery({provider:'mapbox',token,zoom,center:meta});
  if(sessionToken!==token)throw new Error('The property changed. Existing work is unchanged.');
  const r=await fetch('/mapbox-aerial/'+token+'/commit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({zoom})});
  if(!r.ok)throw new Error('Wider aerial could not be accepted. Retry; existing work is unchanged.');
  installPropertyImagery(ready);redrawRoofData();status('Wider aerial loaded. Your measured points and area are unchanged.','ok');ready=null;
 }catch(e){status(e.message||'Wider aerial unavailable. Your image and measurements are unchanged. Retry.','error')}
 finally{if(ready)URL.revokeObjectURL(ready.layer._url);widenMapboxAerial.inFlight=false;syncWiderAerial()}
}
function confirmMapboxProperty(d,ready){return new Promise(resolve=>{
 const dialog=document.createElement('dialog');dialog.id='mapboxPinConfirmation';dialog.style.cssText='max-width:560px;width:90%;border:2px solid #175bba;border-radius:12px;padding:16px';
 dialog.innerHTML='<h2>Confirm property and pin</h2><p class="matchedAddress"></p><p>Check that this address and the centre pin identify the roof you intend to measure. Cancel if they do not match.</p><div style="position:relative"><img style="width:100%;display:block"><span aria-label="Property pin" style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);color:#fff;background:#165ac7;border:2px solid white;border-radius:50%;padding:3px">●</span></div><p class="pinCoordinates"></p><button type="button" id="confirmMapboxPin">Use this address and pin</button> <button type="button" id="cancelMapboxPin">Cancel</button>';
 dialog.querySelector('.matchedAddress').textContent=d.formatted_address;
 dialog.querySelector('.pinCoordinates').textContent=d.center.latitude.toFixed(6)+', '+d.center.longitude.toFixed(6);
 dialog.querySelector('img').src=ready.layer._url;
 const done=value=>{dialog.close();dialog.remove();resolve(value)};
 dialog.querySelector('#confirmMapboxPin').onclick=()=>done(true);dialog.querySelector('#cancelMapboxPin').onclick=()=>done(false);dialog.oncancel=e=>{e.preventDefault();done(false)};
 document.body.appendChild(dialog);dialog.showModal();dialog.querySelector('#confirmMapboxPin').focus();
})}

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
const key="{{GOOGLE_MAPS_API_KEY}}",address=authoritativeAddress;if(("{{AERIAL_PROVIDER}}"!=="mapbox"&&!key)||!address){status('Enter API key and address.','error');return}
 try{
  status('Loading property…');showLoad(true);
  const payload=cc?{key,address,latitude:cc.lat,longitude:cc.lng,direct_coordinates:true}:{key,address,expected_city:enteredCity,expected_province:enteredProvince,expected_street_number:enteredNumber};
  clearTimeout(addressPreviewTimer);addressPreviewSeq++;
  payload.business_type=currentBusinessType();
  const requestKey=JSON.stringify(payload);if(loadProperty.pending?.key!==requestKey)loadProperty.pending={key:requestKey,id:typeof crypto!=='undefined'&&crypto.randomUUID?crypto.randomUUID():Date.now().toString(36)+'-'+Math.random().toString(36).slice(2)};
  let r=await fetch('/property',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':loadProperty.pending.id},body:JSON.stringify({...payload,prepare_only:true})}),d=await r.json();if(r.status===401)throw new Error('Your login expired. Keep this page open and sign in in another tab. Your previous measurements are unchanged.');if(!r.ok){if(r.status===410)loadProperty.pending=null;if(r.status===403&&d.code==='trial_limit_reached'){showLoad(false);showTrialLimit();status('Free trial complete — choose a plan to continue measuring properties.','warn');return}throw new Error(d.user_error||d.error||'Property request failed')}
  const verifyEl=el('propertyVerify');if(verifyEl){verifyEl.style.display='none';verifyEl.textContent=''}
  try{
    if(d.provider==='mapbox'){/* Strict server match plus explicit image/pin confirmation below. */}
    else if(cc){if(verifyEl){verifyEl.style.display='block';verifyEl.style.color='#176b43';verifyEl.textContent='✓ Using exact dropped-pin coordinates — address matching bypassed.'}}
    else{
    const vr=await fetch('/mapbox-test?address='+encodeURIComponent(d.formatted_address||address)),vd=await vr.json();
    if(verifyEl&&vr.ok&&vd.status==='warning'&&vd.nearby_same_number_alternatives?.length&&!skipAddressConflictOnce){
      const alt=vd.nearby_same_number_alternatives[0],matched=d.formatted_address||address;
      verifyEl.style.display='block';verifyEl.style.color='#9a6700';verifyEl.textContent='⚠ ADDRESS CONFLICT — measurement is paused until you confirm the correct property.';
      showLoad(false);
      const useMatched=window.confirm('ADDRESS CONFLICT — DO NOT MEASURE YET.\n\nGoogle matched:\n'+matched+'\n\nNearby same-number property:\n'+alt.address+'\n\nPress OK to CONFIRM THE GOOGLE MATCHED PROPERTY.\nPress Cancel to USE THE NEARBY ALTERNATIVE.');
      skipAddressConflictOnce=true;
      if(!useMatched){
        if(el('streetAddress'))el('streetAddress').value=alt.address;
        if(el('cityTown'))el('cityTown').value='';if(el('propertyProvince'))el('propertyProvince').value='';if(el('postalCode'))el('postalCode').value='';
        status('Review the alternative address, enter its City and State/Province, then load it. Your existing work is unchanged.','warn');return;
      }
      verifyEl.style.color='#176b43';verifyEl.textContent='✓ Dealer confirmed Google matched property: '+matched;
    }
    else if(verifyEl&&vr.ok){verifyEl.style.display='block';verifyEl.style.color='#176b43';verifyEl.textContent='✓ Property address verified'}
    }
  }catch(e){if(verifyEl&&!cc)verifyEl.style.display='none'}
  skipAddressConflictOnce=false;
  if(d.requires_address_confirmation&&!window.confirm('CONFIRM FOUND ADDRESS\n\nGoogle returned a partial match:\n'+d.formatted_address+'\n\nThe street number, street, municipality, province/state and country match. Confirm this is the intended property. Choose Cancel to keep your existing work.')){status('Property not changed. Review the found address and retry.','warn');return}
  const prepared=await preparePropertyImagery(d);
  if(d.provider==='mapbox'&&!await confirmMapboxProperty(d,prepared)){URL.revokeObjectURL(prepared.layer._url);status('Property not changed. Review the address and pin before continuing.','warn');return}
  if(workspaceSaveFingerprint()!==workspaceKey)throw new Error('Your measurements or pricing changed while loading. Save your work before replacing the property.');
  if(propertyInputAddressKey()!==enteredKey)throw new Error('The address changed while imagery was loading. Review it and retry.');
  const accepted=await fetch('/property/accept',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({operation_id:loadProperty.pending.id,token:d.token,address_pin_confirmed:d.provider==='mapbox',address_confirmed:!!d.requires_address_confirmation})});
  const acceptance=await accepted.json();
  if(!accepted.ok){if(accepted.status===410)loadProperty.pending=null;throw new Error(acceptance.error||'Property could not be accepted. Keep this page open and retry.');}
  loadProperty.pending=null;
 if((el('address')?.value||'')!==authoritativeAddress)['customerName','customerPhone','customerEmail','customerNotes'].forEach(id=>{if(el(id))el(id).value=''});
 resetReportForNewProperty();exactPinDisplay=false;if(el('address'))el('address').value=d.provider==='mapbox'?d.formatted_address:authoritativeAddress;syncPropertyProvince();
  resetMeasurementForNewProperty();locateRoofMode=false;fallbackMode=false;setManualCorrectionLayout(false);showSolarFallback(false);if(propertyMarker){try{map.removeLayer(propertyMarker)}catch(e){}propertyMarker=null};removeStaleAerialLayers();
  sessionToken=d.token;exactPinDisplay=!!d.exact_pin_display;lastLoadedStreet=el('streetAddress')?.value.trim()||'';applyAddressParts(d.parts);loadProperty.loadedAddressKey=propertyInputAddressKey();if(d.center)setPropertyMarker(d.center.latitude,d.center.longitude);else if(d.anchor)setPropertyMarker(d.anchor.latitude,d.anchor.longitude);if(el('addressAutoStatus'))el('addressAutoStatus').textContent='✓ '+(d.formatted_address||buildPropertyAddress());if(el('googleMatch'))el('googleMatch').textContent=(d.provider==='mapbox'?'Mapbox matched: ':'Google matched: ')+(d.formatted_address||buildPropertyAddress());
  let prov=detectProvince(d.formatted_address||address);if(prov){if(el('propertyProvince'))setPropertyRegion(prov);syncPropertyProvince()}
  showStreetViewImage(el('street'),d.provider==='mapbox'?'':'/street/'+sessionToken+'?v='+Date.now(),d.street_date?('Street View imagery: '+d.street_date):'Google Street View');usage.property++;
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
    status('Property aerial loaded — ready for '+(pendingMeasurementMode==='linear'?'Linear':'Area')+' measurement.','ok');
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
    showSolarFallback(!manualRoofQa(),manualRoofQa()?'':'Google does not have an automatic roof measurement for this property. Manual measurement is required. Trace the shingled roof below and confirm its pitch.');
    renderSummary();
    if(el('garageGuide'))el('garageGuide').innerHTML='<b>Manual measurement required.</b> Trace the shingled roof area shown below and confirm the pitch. If imagery appears older, verify the current roof layout before sending the estimate.';
    if(el('measureClicked'))el('measureClicked').disabled=true;if(el('measureClickedTop'))el('measureClickedTop').disabled=true;
    const details=el('manualRoofDetails');if(details)details.open=true;
    if(aerialLoaded){setTimeout(()=>{if(!traceMode)toggleTrace()},80)}
    status(manualRoofQa()?'Property aerial loaded — trace the roof and confirm its pitch before saving.':'Automatic measurement unavailable — manual roof tracing is ready. Confirm the pitch before saving.',manualRoofQa()?'ok':'warn');return;
  }
  structures=[{...d.main,label:'Main House'}];setManualCorrectionLayout(false);setManualUi(false);if(el('measureSource'))el('measureSource').value='google';roofMask=prepared.mask;d.main.outline=outlineFromMask(roofMask,d.main.latitude,d.main.longitude);structures[0].outline=d.main.outline;reviewAutomaticRoof(structures[0]);let rgb=prepared;redrawRoofData();if(exactPinDisplay)frameAerial(map,rgb.bounds,0);renderSummary();if(el('garageGuide'))el('garageGuide').innerHTML=roofQuoteNeedsReview()?'<b>Main roof requires review.</b> Use the roof action beside the aerial to review or trace it.': '<b>Main house measured.</b> If there is another roof to include, click <b>+ ADD GARAGE / OTHER ROOF</b>, then click once on that roof. It will measure automatically.';if(el('measureClicked'))el('measureClicked').disabled=false;if(el('measureClickedTop'))el('measureClickedTop').disabled=false;status((structures[0]?.needs_remeasure||structures[0]?.automatic_review_warning)?'Main roof coverage needs review. Use the roof action beside the aerial to review or trace it.':'Main roof detected. Select KEEP OUTLINE above the aerial, or Remeasure to trace it again.',(structures[0]?.needs_remeasure||structures[0]?.automatic_review_warning)?'warn':'ok');pendingMeasurementMode=requestedMeasurementMode;if(requestedMeasurementMode==='area'||requestedMeasurementMode==='linear'){selectMeasurementTool(requestedMeasurementMode)}else{measurementViewMode='auto';updatePropertyActionButton();updateMeasurementInterface()}
 }catch(e){status(e.message+' Your existing saved or unsaved work is unchanged. Retry Load Property when ready.','error')}finally{showLoad(false)}
}
function startGarageMode(){if(manualRoofQa()){beginManualRoofSection();return}if(measureClicked.pending){extraRoofStatus('The selected roof is still being measured. Please wait for its result.','warn');return}if(!sessionToken){status('Load the property first.','error');return}if(!structures.length){if(manualPlanes.length){garageMode=false;setManualCorrectionLayout(false);setManualUi(false);const details=el('manualRoofDetails');if(details)details.open=true;if(!traceMode)toggleTrace();status('Add Garage / Other Roof — trace the next shingled building, confirm its pitch, then save it.','warn');return}status('Finish the main-house manual measurement first.','warn');return}garageMode=true;clicked=null;if(el('garageSavedConfirm'))el('garageSavedConfirm').style.display='none';if(clickMarker){try{map.removeLayer(clickMarker)}catch(e){}clickMarker=null}if(el('garageGuide'))el('garageGuide').innerHTML='<b>Add Garage / Other Roof is ON.</b> Click once near the centre of the garage, shed or shop roof. It will measure automatically.';status('Click once near the centre of the extra roof to measure it automatically.','warn')}
function extraRoofStatus(message,kind=''){
 status(message,kind);
 const guide=el('garageGuide');if(guide)guide.textContent=message;
 if(clickMarker){const text=document.createElement('div');text.textContent=message;clickMarker.setPopupContent(text).openPopup()}
}
async function measureClicked(){if(measureClicked.pending)return;if(!sessionToken||!clicked){extraRoofStatus('Click the centre of the extra structure first.','error');return}measureClicked.pending=true;try{extraRoofStatus('Measuring selected structure…');let r=await fetch('/structure',{signal:AbortSignal.timeout(45000),method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:sessionToken,latitude:clicked.lat,longitude:clicked.lng})}),d=await r.json();if(!r.ok)throw new Error(d.error||'Structure request failed');let dup=structures.find(s=>(s.building_id&&d.building_id&&s.building_id===d.building_id)||(Math.abs(s.latitude-d.latitude)<.00003&&Math.abs(s.longitude-d.longitude)<.00003)||tracedRoofContains(s,d.latitude,d.longitude));if(dup){extraRoofStatus(dup.needs_remeasure?'That roof is already listed for correction. Use the roof action beside the aerial to review or trace it.':'That building is already included. Click nearer the centre of a different structure.','error');return}d.label=structures.length===1?'Detached Garage':`Extra Structure ${structures.length}`;extraRoofStatus('Roof measurement received. Loading its outline…');const ownMask=d.mask_url?await loadRoofMask(d.mask_url,true):null;d.outline=outlineFromMask(ownMask,d.latitude,d.longitude);delete d.mask_url;if(!d.outline){extraRoofStatus('Google measured this roof, but no usable outline was found in its imagery (AQ-MASK-CONTOUR). It has not been added.','warn');return}reviewAutomaticRoof(d,true);structures.push(d);redrawRoofData();fitEntireQuote(map);usage.structures++;renderSummary();if(d.needs_remeasure){extraRoofStatus('This automatic result may cover only part of the roof. No area has been included for it. Use the roof action beside the aerial to review or trace it.','warn');return}if(clickMarker){try{map.removeLayer(clickMarker)}catch(e){}clickMarker=null}clicked=null;if(el('garageGuide'))el('garageGuide').innerHTML=`<b>${d.label} is already saved in this quote.</b> To add another roof, click <b>+ ADD GARAGE / OTHER ROOF</b> again.`;if(el('garageSavedConfirm')){el('garageSavedConfirm').style.display='block';el('garageSavedConfirm').innerHTML=`<b>✓ ${d.label} SAVED TO QUOTE — ${fmt(d.total_roof_sqft)} ft² INCLUDED</b><br><span class="small">No other Save button is required. It is already included in Roofs in Quote and the estimate total.</span>`}extraRoofStatus(`${d.label} saved to quote — ${fmt(d.total_roof_sqft)} ft² included.`,'ok')}catch(e){extraRoofStatus(e.roofCode?'Google measured this roof, but its outline could not load ('+e.roofCode+'). It has not been added.':e.name==='TimeoutError'||e.name==='AbortError'?'This roof request timed out. It has not been added. Click + Add Garage / Other Roof to retry.':'This roof could not finish measuring. It has not been added. Try again or use Add Missing Roof.','warn')}finally{measureClicked.pending=false}}
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
 if(el('reportOutlineHelpTop'))el('reportOutlineHelpTop').textContent='✓ Estimate image corrected. Original measurement and price are unchanged.';
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
 if(!issue){const before=reportCorrectionWorkspace();try{applyReportCorrectionCandidate();const calc=priceCalc();message=quotePricingError(calc);if(!message){const quantity=c.mode==='area'?commercialAreas[c.index].sqft:linearFeetTotal();message=`${c.mode==='area'?'Area '+(c.index+1):'Linear'}: ${c.originalQuantity.toLocaleString()} → ${c.mode==='area'?fmt(quantity):quantity.toFixed(1)} ${c.mode==='area'?'ft²':'ft'}. Estimate total: ${money(c.originalTotal)} → ${money(calc.total)}. Save confirms this measurement and price change.`;}}finally{restoreReportCorrectionWorkspace(before)}}
 el('reportOutlineHelpTop').textContent=(c.mode==='area'?'RETRACE OUTLINE — tap the new boundary in order. Cancel keeps the original. ':'')+(c.error||message||'Adjust the points or select Redraw. Cancel keeps the original.');
 el('reportSaveOutlineBtnTop').disabled=!!issue||c.saving;
 el('reportSaveOutlineBtnTop').textContent=c.saving?'SAVING…':'SAVE MEASUREMENT & UPDATE ESTIMATE';
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
  (snap.commercialAreas||[]).forEach((area,i)=>{if(area.points?.length>=3)html+=`<button class="orange" onclick="correctSavedMeasurementFromReport('area',${i})">RETRACE OUTLINE — AREA ${i+1}</button>`});
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
function setReportOutlineButtons(editing){if(el('reportOutlineTargetButtons'))el('reportOutlineTargetButtons').style.display=editing?'none':'flex';if(el('reportCancelOutlineBtnTop'))el('reportCancelOutlineBtnTop').style.display=editing?'inline-block':'none';if(el('reportUndoOutlineBtnTop'))el('reportUndoOutlineBtnTop').style.display=editing?'inline-block':'none';if(el('reportSaveOutlineBtnTop')){el('reportSaveOutlineBtnTop').style.display=editing?'inline-block':'none';el('reportSaveOutlineBtnTop').disabled=reportOutlinePoints.length<3}if(el('downloadPdfBtn'))el('downloadPdfBtn').disabled=!!editing;const msg=editing?`Editing ${reportTargetLabel(reportOutlineTarget)}. Click each corner on the final estimate image, then SAVE OUTLINE. The PDF button unlocks after the outline is saved.`:'Choose which roof outline to edit. Main house and added roofs can be edited separately. Picture only — measurements and price stay unchanged.';['reportOutlineHelp','reportOutlineHelpTop'].forEach(id=>{if(el(id))el(id).textContent=msg});const svg=el('reportDrawLayer');if(svg){svg.classList.toggle('active',!!editing);if(editing)syncReportDrawLayer()}}
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
async function saveReportOutline(){if(reportMeasurementCorrection){await saveReportMeasurementCorrection();return}if(visualCorrectionMode){saveVisualCorrection().catch(e=>console.error('AQ:outline-render-failed'));return}if(!reportOutlineEditMode||reportOutlinePoints.length<3||!reportOutlineTarget)return;const target=reportOutlineTarget,label=reportTargetLabel(target);reportOutlines[target]=reportOutlinePoints.map(p=>[p.lat,p.lng]);reportOutlineEditMode=false;reportOutlinePoints=[];clearReportOutlineTemp();document.querySelector('#reportOverlay .report')?.classList.remove('estimate-editing');await buildCustomerMap();setReportOutlineButtons(false);if(el('reportOutlineHelpTop'))el('reportOutlineHelpTop').textContent=`✓ ${label} outline saved. You can now edit another roof. Measurements and price are unchanged.`}

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

function fitReportCanvas(host,canvas){
 const fit=()=>{
  const width=host.clientWidth,height=host.clientHeight;
  if(!width||!height||!canvas.width||!canvas.height)return;
  const scale=Math.min(width/canvas.width,height/canvas.height);
  Object.assign(canvas.style,{display:'block',width:(canvas.width*scale)+'px',height:(canvas.height*scale)+'px',maxWidth:'100%',maxHeight:'100%',flex:'none'});
 };
 host.style.display='flex';host.style.alignItems='center';host.style.justifyContent='center';
 host.aqCanvasResizeObserver?.disconnect();fit();
 if(typeof ResizeObserver!=='undefined'){host.aqCanvasResizeObserver=new ResizeObserver(fit);host.aqCanvasResizeObserver.observe(host)}
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
   drawSavedMeasurementLabels(ctx,labeledSnap,view,canvas.width,canvas.height);host.appendChild(canvas);fitReportCanvas(host,canvas);
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
     customerOverlays.push(L.marker(poly.getBounds().getCenter(),{interactive:false,icon:L.divIcon({className:'',html:`<div class="area-label">${fmt(Number(area.sqft||0))} ft²</div>`,iconAnchor:[35,10]})}).addTo(customerMap));
     customerOverlays.slice(overlayStart).forEach(l=>l._reportMeasurement={mode:'area',index:snap.commercialAreas.indexOf(area)});
    });
   }else{
   const overlayStart=customerOverlays.length;
   const pts=(reportOutlines['area-visual']||snap.areaPoints).map(p=>L.latLng(p[0],p[1]));
   const poly=L.polygon(pts,{color:'#7357b8',weight:5,fillColor:'#7357b8',fillOpacity:.14,interactive:false,lineJoin:'round'}).addTo(customerMap);
   customerOverlays.push(poly);allBounds.push(...pts);drawCustomerAreaEdgeLabels(reportOutlines['area-visual']||snap.areaPoints);
   const lab=L.marker(poly.getBounds().getCenter(),{interactive:false,icon:L.divIcon({className:'',html:`<div class="area-label">${fmt(Number(snap.areaSqFt||0))} ft²</div>`,iconAnchor:[35,10]})}).addTo(customerMap);
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
   // V11.6.67 — CUSTOMER ESTIMATE EDGE DIMENSIONS
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
 // This changes presentation only — measurement geometry and pricing are untouched.
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
 (areas.length?areas:[{points:snap.areaPoints||[],sqft:snap.areaSqFt}]).forEach(a=>{if(a.points.length<3)return;edges(a.points,true,'#7357b8');const lats=a.points.map(p=>p[0]),lngs=a.points.map(p=>p[1]);if(Number(a.sqft)>0)label([(Math.min(...lats)+Math.max(...lats))/2,(Math.min(...lngs)+Math.max(...lngs))/2],fmt(a.sqft)+' ft²','#7357b8')});
 if(snap.linearPoints?.length>=2)edges(snap.linearPoints,false,'#0f8f83');
 (snap.structures||[]).forEach((st,i)=>{
  if((snap.structures||[]).length>3){label([st.latitude,st.longitude],'#'+(i+1)+' · '+fmt(st.total_roof_sqft)+' ft²',st.manually_measured?'#d97706':i===0?'#2d6cdf':'#18a7a0',true);return}
  const color=st.manually_measured?'#d97706':i===0?'#2d6cdf':'#18a7a0',points=(st.outline||[]).map(p=>[Number(p.lat??p[0]),Number(p.lng??p[1])]);if(points.length>=3)edges(points,true,color);
  (st.segments||[]).forEach(seg=>{const c=seg.center,b=seg.bounding_box;const point=c?[c.latitude,c.longitude]:b?.sw&&b?.ne?[(b.sw.latitude+b.ne.latitude)/2,(b.sw.longitude+b.ne.longitude)/2]:null;if(point&&Number.isFinite(Number(seg.pitch_degrees)))label(point,Number(seg.pitch_degrees).toFixed(1)+'°','#7a3f08')});
 });
 (snap.manualPlanes||[]).forEach(st=>{const points=(st.points||[]).map(p=>[Number(p.lat??p[0]),Number(p.lng??p[1])]);if(points.length<3)return;edges(points,true,'#d97706');const bounds=L.latLngBounds(points).getCenter();label([bounds.lat,bounds.lng],Number(st.pitch_degrees||0).toFixed(1)+'°','#7a3f08')});
 return occupied;
}
function buildSavedRoofOutlineSnapshot(){
 const original=quoteSnapshot||captureQuoteSnapshot(),snap=activeSavedDiagramSnapshot(original);
 if(snap.businessType!=='roofing'||snap.measurementMode!=='auto')return false;
 const rings=[...snap.structures.map(s=>s.outline||[]),...snap.manualPlanes.map(p=>p.points||[])].filter(p=>p.length>=3);
 if(!rings.length)return false;
 const host=el('customerMap');if(!host)return false;
 const world=256*Math.pow(2,19),project=p=>{const lat=Number(p.lat??p[0]),lng=Number(p.lng??p[1]),v=Math.sin(lat*Math.PI/180);return[(lng+180)/360*world,(.5-Math.log((1+v)/(1-v))/(4*Math.PI))*world]};
 const projected=rings.map(r=>r.map(project)),points=projected.flat();
 if(points.some(p=>p.some(v=>!Number.isFinite(v))))throw new Error('Saved roof outline coordinates are invalid.');
 const xs=points.map(p=>p[0]),ys=points.map(p=>p[1]),cx=(Math.min(...xs)+Math.max(...xs))/2,cy=(Math.min(...ys)+Math.max(...ys))/2;
 const width=1280,height=840,span=Math.max(Math.max(...xs)-Math.min(...xs),(Math.max(...ys)-Math.min(...ys))*width/height,1)*1.35;
 const view={latitude:Math.atan(Math.sinh(Math.PI*(1-2*cy/world)))*180/Math.PI,longitude:cx/world*360-180,zoom:19,width:span,height:span*height/width};
 const canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;
 Object.assign(canvas.style,{display:'block',maxWidth:'100%',maxHeight:'100%',width:'auto',height:'auto',flex:'none'});
 canvas.dataset.savedRoofOutline='true';canvas.dataset.diagramScope=savedDiagramFingerprint(original);canvas.dataset.mapView=JSON.stringify(view);
 const ctx=canvas.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,width,height);
 projected.forEach((ring,i)=>{ctx.beginPath();ring.forEach((p,j)=>{const x=width/2+(p[0]-cx)*width/span,y=height/2+(p[1]-cy)*height/view.height;if(j)ctx.lineTo(x,y);else ctx.moveTo(x,y)});ctx.closePath();ctx.fillStyle='#f59e0b18';ctx.fill();ctx.strokeStyle=i<snap.structures.length?'#2d6cdf':'#d97706';ctx.lineWidth=4;ctx.stroke()});
 canvas.dataset.labelBoxes=JSON.stringify(drawSavedMeasurementLabels(ctx,snap,view,width,height));
 if(customerMap){customerMap.remove();customerMap=null}customerRgbLayer=null;customerOverlays=[];
 host.replaceChildren(canvas);host.style.display='flex';host.style.alignItems='center';host.style.justifyContent='center';
 if(el('customerMapPlaceholder'))el('customerMapPlaceholder').style.display='none';
 if(el('reportOutlineControls'))el('reportOutlineControls').style.display='none';
 return true;
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
   canvas.dataset.diagramScope=savedDiagramFingerprint(original);canvas.dataset.mapView=JSON.stringify(view);const ctx=canvas.getContext('2d');ctx.drawImage(img,0,0,canvas.width,canvas.height);canvas.dataset.labelBoxes=JSON.stringify(drawSavedMeasurementLabels(ctx,snap,view,canvas.width,canvas.height));host.appendChild(canvas);fitReportCanvas(host,canvas);if(el('customerMapPlaceholder'))el('customerMapPlaceholder').style.display='none';
 }finally{try{URL.revokeObjectURL(obj)}catch(e){}}
}

async function buildCustomerMap(){
 if(!sessionToken)return;
 const imageChoice=el('streetViewChoice')?.value||'auto';
 if(imageChoice==='none'&&buildSavedRoofOutlineSnapshot())return;
 const useAerial=imageChoice!=='none';
 const snap=activeSavedDiagramSnapshot(quoteSnapshot||captureQuoteSnapshot());
 const pureManual=(snap.measureSource==='manual'&&(snap.manualPlanes||[]).length>0&&!(snap.structures||[]).length);
 // V11.6.63 — MANUAL ESTIMATE PIXEL LOCK
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
let historyOpener=null,historyInert=[];
function openEstimateHistory(){
 const dialog=el('historyModal');
 if(!dialog.classList.contains('open')){
  historyOpener=document.activeElement;historyInert=[];
  for(let branch=dialog;branch&&branch!==document.body;branch=branch.parentElement){
   for(const node of branch.parentElement?.children||[]){if(node!==branch){historyInert.push([node,node.inert]);node.inert=true}}
  }
  dialog.classList.add('open');el('historySearch').focus();
 }
 searchEstimateHistory();
}
function closeEstimateHistory(){
 const dialog=el('historyModal');if(!dialog.classList.contains('open'))return;
 dialog.classList.remove('open');historyInert.forEach(([node,prior])=>node.inert=prior);historyInert=[];
 if(historyOpener?.isConnected)historyOpener.focus();historyOpener=null;
}
document.addEventListener('keydown',event=>{
 const dialog=el('historyModal');if(!dialog?.classList.contains('open'))return;
 if(event.key==='Escape'){event.preventDefault();closeEstimateHistory();return}
 if(event.key!=='Tab')return;
 const nodes=[...dialog.querySelectorAll('a[href],button,input,select,textarea,[tabindex]')].filter(n=>!n.disabled&&n.tabIndex>=0&&n.getClientRects().length);
 const first=nodes[0],last=nodes[nodes.length-1];
 if(!first)return;
 if(event.shiftKey&&(document.activeElement===first||!dialog.contains(document.activeElement))){event.preventDefault();last.focus()}
 else if(!event.shiftKey&&(document.activeElement===last||!dialog.contains(document.activeElement))){event.preventDefault();first.focus()}
});
async function searchEstimateHistory(){
 const q=(el('historySearch')?.value||'').trim(),box=el('historyResults');box.innerHTML='<div class="small" style="padding:14px 0">Searching…</div>';
 try{const r=await fetch('/api/estimates?q='+encodeURIComponent(q)),d=await r.json();if(!r.ok)throw new Error(d.error||'Search failed');if(!d.length){box.innerHTML='<div class="small" style="padding:14px 0">No saved estimates found.</div>';return}
 const shown=d;
 box.innerHTML=shown.map(x=>`<div class="historyRow"><div class="historyCustomer"><b>${escapeHistory(x.customer_name||'Homeowner')}</b><div class="small">${escapeHistory(x.customer_phone||'')}${x.customer_email?' • '+escapeHistory(x.customer_email):''}</div></div><div class="historyAddress"><b>${escapeHistory(x.address||'')}</b></div><div class="historyDate">${escapeHistory((x.created_at||'').slice(0,10))}</div><div class="historyAmount"><b>${money(x.total_price||0)}</b></div><div class="historyActions"><button class="secondary" onclick="viewSavedEstimate('${x.id}')">OPEN</button><button class="ghost" onclick="viewEstimateVersions('${x.id}')">VIEW HISTORY</button></div></div>`).join('');
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
 const snap=p.quote||{},industry=snap.businessType||p.business_type||'',hasAreas=(snap.commercialAreas||[]).some(a=>Number(a.sqft)>0)||Number(snap.areaSqFt)>0,linearOnly=!hasAreas&&(snap.measurementMode||p.measurement_mode)==='linear';
 if(linearOnly)return 'Service length: '+Number(p.linear_feet??snap.linearFeet??p.total_area??v.total_area??0).toFixed(1)+' linear ft';
 const roof=industry==='roofing'||(!industry&&(snap.structures?.length||snap.manualPlanes?.length)&&!hasAreas);
 return (roof?'Roof area: ':'Service area: ')+fmt(p.total_area??v.total_area??0)+' ft²';
}
function savedVersionCard(v,label,estimateId,versionIndex){
 const p=v.payload||{};
 return `<div style="padding:12px;border:1px solid var(--line);border-radius:10px;margin-top:9px;background:#fff"><div style="display:flex;justify-content:space-between;gap:12px;align-items:start"><div><b>${escapeHistory(label)}</b><div class="small">${escapeHistory((v.saved_at||v.created_at||v.revised_at||'').replace('T',' ').replace('Z',''))}</div></div><div style="font-size:18px;font-weight:900;color:var(--green2)">${money(p.total_price??v.total_price??0)}</div></div><div style="margin-top:7px"><b>${escapeHistory(p.customer_name||v.customer_name||'Homeowner')}</b></div><div class="small">${escapeHistory(p.address||v.address||'')}</div><div class="small">${savedMeasurementSummary(p,v)}${p.customer_phone?' • '+escapeHistory(p.customer_phone):''}${p.customer_email?' • '+escapeHistory(p.customer_email):''}</div>${p.customer_notes?'<details style="margin-top:8px"><summary>INTERNAL JOB NOTES</summary><div style="white-space:pre-wrap;padding:8px 0">'+escapeHistory(p.customer_notes)+'</div></details>':''}<div style="margin-top:10px"><button class="secondary" onclick="openHistoricalEstimate('${estimateId}',${versionIndex})">OPEN ESTIMATE</button></div></div>`;
}
function setSavedField(id,value){const n=el(id);if(n)n.value=value??''}
function restoreSavedQuoteFields(p,snap,pr){
 // Startup autofill cleanup must never erase acknowledged/restored customer text.
 clearNewJobCustomer.preserve=true;
 setSavedField('estimatePeriod',estimatePeriodValue(pr.estimatePeriod||'one_time',snap.businessType||'roofing'));
 const country=snap.dealerCountry||(/,\s*Canada\s*$/i.test(p.address||'')?'CA':(/,\s*(USA|United States)\s*$/i.test(p.address||'')?'US':null));if(country)setSavedField('dealerCountry',country);
 structures=JSON.parse(JSON.stringify(snap.structures||[]));manualPlanes=JSON.parse(JSON.stringify(snap.manualPlanes||[]));
 commercialAreas=JSON.parse(JSON.stringify(snap.commercialAreas||[]));commercialEditingIndex=commercialAreas.length?0:-1;
 areaPoints=(commercialAreas[0]?.points||snap.areaPoints||[]).map(p=>L.latLng(p[0],p[1]));areaMeasurementSaved=areaPoints.length>=3;areaMode=false;
 linearPoints=(snap.linearPoints||[]).map(p=>L.latLng(p[0],p[1]));linearMeasurementSaved=linearPoints.length>=2;linearMode=false;measurementViewMode=snap.measurementMode||'auto';pendingMeasurementMode=measurementViewMode;
 if(el('measureSource'))el('measureSource').value=snap.measureSource||((manualPlanes.length&&!structures.length)?'manual':(manualPlanes.length?'hybrid':'google'));
 for(const [id,value] of Object.entries({address:p.address||'',customerName:p.customer_name||'',customerPhone:p.customer_phone||'',customerEmail:p.customer_email||'',customerNotes:p.customer_notes||'',extraServiceDescription:p.extra_service_description||'',extraServiceAmount:Number(p.extra_service_amount||0).toFixed(2)}))setSavedField(id,value);
 if(Number.isFinite(Number(pr.price)))setSavedField('jobPrice',Number(pr.price).toFixed(2));
 if(pr.mode)setSavedField('pricingMode',pr.mode);
 if(Number.isFinite(Number(pr.disc)))setSavedField('discountPct',pr.disc);
 if(Number.isFinite(Number(pr.gst)))setSavedField('gst',pr.gst);
 if(Number.isFinite(Number(pr.pst)))setSavedField('pst',pr.pst);
 if(p.image_choice)setSavedField('streetViewChoice',p.image_choice);
 if(el('streetMeta'))el('streetMeta').textContent=p.street_meta||'Saved estimate';
 savedStreetImageData=String(p.street_image_data||'');
 if(snap.businessType&&el('businessType')?.querySelector('option[value="'+snap.businessType+'"]')){setSavedField('businessType',snap.businessType);industryChosenByUser=true;switchIndustryMarketing();applyBusinessTerminology()}
 const lineRate=Number(snap.landscapingLinearRate??snap.pressureLinearRate??snap.pavingLinearRate??pr.price??0);
 savedLinearJobRate=Number.isFinite(lineRate)?Math.max(0,lineRate):0;
 setSavedField('commercialLinearRate',snap.commercialLinearRate??0);
 for(const [id,value] of Object.entries({landscapingAreaRate:snap.landscapingAreaRate,pressureAreaRate:snap.pressureAreaRate,pavingAreaRate:snap.pavingAreaRate}))if(value!==undefined)setSavedField(id,value);
 if(surfaceIndustry())setSavedField('jobPrice',measurementViewMode==='linear'&&snap.businessType!=='commercial'?savedLinearJobRate:(commercialAreas[0]?.rate??pr.price??0));
 if(manualRoofQa()){renderSummary();if(el('manualRoofScopeConfirmed'))el('manualRoofScopeConfirmed').checked=!!snap.roofScopeConfirmed&&!manualRoofConfirmationBlocked();syncRoofNextAction()}
}
async function resumeSavedEstimateWorkspace(){
 const context=savedEstimateEditContext;if(!context)return;
 const r=await fetch('/api/estimates/'+encodeURIComponent(context.id)+'/editing-session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({version_index:context.versionIndex})}),d=await r.json();
 if(!r.ok)throw new Error(d.error||'Could not restore this saved job.');
 resetMeasurementForNewProperty();savedEstimateEditContext=context;restoreSavedQuoteFields(context.payload,context.snapshot,context.pricing);
 savedJobDetails=d.job_details||{};saveEstimateHistory.baseVersion=d.version||null;
 sessionToken=d.token;exactPinDisplay=false;fallbackMode=true;removeStaleAerialLayers();
 const parts=String(context.payload.address||'').split(',').map(s=>s.trim());
 setSavedField('streetAddress',parts[0]||context.payload.address||'');setSavedField('cityTown',parts[1]||'');setSavedField('postalCode','');
 const province=parts.slice(2).map(s=>s.match(/^([A-Z]{2})(?:\s|$)/)?.[1]).find(Boolean)||'';setPropertyRegion(province);lastLoadedStreet=el('streetAddress')?.value||'';loadProperty.loadedAddressKey=propertyInputAddressKey();
 setPropertyMarker(d.center.latitude,d.center.longitude);map.setView([d.center.latitude,d.center.longitude],18);
 if(d.provider==='mapbox')installPropertyImagery(await preparePropertyImagery(d));else await loadStandardWideAerial();map.fitBounds(d.bounds,{padding:[45,45],maxZoom:20});
 redrawRoofData();redrawManualDisplayLayers();redrawAreaMeasure();redrawLinearMeasure();
 savedPropertyEditActive=true;quoteSnapshot=null;lastHistorySaveKey='';
 updatePropertyActionButton();updateAreaUi();updateLinearUi();renderSummary();
 setSavedField('commercialLinearRate',context.snapshot.commercialLinearRate??0);
 setSavedField('measureSource',context.snapshot.measureSource||((manualPlanes.length&&!structures.length)?'manual':(manualPlanes.length?'hybrid':'google')));
 for(const [id,value] of Object.entries({landscapingAreaRate:context.snapshot.landscapingAreaRate,pressureAreaRate:context.snapshot.pressureAreaRate,pavingAreaRate:context.snapshot.pavingAreaRate}))if(value!==undefined)setSavedField(id,value);
 renderSummary();
 showStreetViewImage(el('street'),savedStreetImageData,context.payload.street_meta||'Saved Google Street View');
 if(el('addressAutoStatus'))el('addressAutoStatus').textContent='Saved property restored — measurements and rates retained.';
 if(el('googleMatch'))el('googleMatch').textContent='';
 savedEstimateEditContext=null;
 status('Saved job ready to edit. Create the updated estimate to save your changes.','ok');
}
async function openHistoricalEstimate(estimateId,versionIndex){
 try{
  const r=await fetch('/api/estimates/'+encodeURIComponent(estimateId)+'/versions'),d=await r.json();if(!r.ok)throw new Error(d.error||'History failed');
  const v=versionIndex<0?d.current:(d.revisions||[])[versionIndex];if(!v)throw new Error('Version not found');
  const p=v.payload||{},snap=p.quote||{},pr=p.pricing||{};
  if(!snap.structures?.length&&!snap.manualPlanes?.length&&!snap.areaPoints?.length&&!snap.commercialAreas?.length&&!snap.linearPoints?.length)throw new Error('Saved version has no measurement snapshot');
  restoreSavedQuoteFields(p,snap,pr);
  savedEstimateEditContext={id:estimateId,versionIndex,payload:JSON.parse(JSON.stringify(p)),snapshot:JSON.parse(JSON.stringify(snap)),pricing:JSON.parse(JSON.stringify(pr))};

  // Reset only report UI state. The roof measurement engine is not called.
  document.body.classList.remove('report-open');
  if(el('reportOverlay'))el('reportOverlay').style.display='none';
  if(customerMap){try{customerMap.remove()}catch(e){}customerMap=null}
  customerRgbLayer=null;customerOverlays=[];reportOutlines={};reportOutlineTarget=null;
  reportOutlineEditMode=false;reportOutlinePoints=[];clearReportOutlineTemp();
  estimateOpenInProgress=false;
  if(customerMapBuildTimer){clearTimeout(customerMapBuildTimer);customerMapBuildTimer=null}
  quoteSnapshot={...JSON.parse(JSON.stringify(snap)),structures:JSON.parse(JSON.stringify(structures)),manualPlanes:JSON.parse(JSON.stringify(manualPlanes)),savedPricing:pr,measureSource:(snap.measureSource||el('measureSource')?.value||'google')};

  if(snap.businessType&&el('businessType')?.querySelector('option[value="'+snap.businessType+'"]')){setSavedField('businessType',snap.businessType);industryChosenByUser=true;switchIndustryMarketing();applyBusinessTerminology()}
  closeEstimateHistory();
  // Let the modal finish closing before opening the report overlay.
  await new Promise(resolve=>setTimeout(resolve,60));
  await showCustomerEstimate(true,(v.saved_at||v.created_at||v.revised_at||'').slice(0,10));
 }catch(e){
  console.error('AQ:estimate-reopen-failed');
  const box=el('historyResults');
  if(box)box.insertAdjacentHTML('afterbegin',`<div class="error" style="padding:10px 0">Could not open this saved estimate: ${escapeHistory(e.message||'unknown error')}</div>`);
  status('Could not reopen that saved estimate.','error')
 }
}
async function viewSavedEstimate(id){
 try{const r=await fetch('/api/estimates/'+encodeURIComponent(id)),d=await r.json();if(!r.ok)throw new Error(d.error||'Not found');const p=d.payload||{};el('historyResults').innerHTML=`<div style="padding:12px;border:1px solid var(--line);border-radius:10px"><button class="ghost" onclick="searchEstimateHistory()">← BACK TO RESULTS</button><h3>${escapeHistory(p.customer_name||'Homeowner')}</h3><div><b>Property:</b> ${escapeHistory(p.address||'')}</div><div><b>Phone:</b> ${escapeHistory(p.customer_phone||'—')}</div><div><b>Email:</b> ${escapeHistory(p.customer_email||'—')}</div><div><b>Customer / Job Notes:</b> ${escapeHistory(p.customer_notes||'—')}</div><div>${savedMeasurementSummary(p,d)}</div><div><b>Estimate:</b> ${money(p.total_price||0)}</div><div><b>Date:</b> ${escapeHistory((d.created_at||'').slice(0,10))}</div><div style="margin-top:12px"><button class="secondary" onclick="viewEstimateVersions('${id}')">VIEW HISTORY</button></div></div>`}catch(e){status('Could not open that saved estimate.','error')}
}
async function viewEstimateVersions(id){
 const box=el('historyResults');box.innerHTML='<div class="small" style="padding:14px 0">Loading estimate history…</div>';
 try{
  const r=await fetch('/api/estimates/'+encodeURIComponent(id)+'/versions'),d=await r.json();if(!r.ok)throw new Error(d.error||'History failed');
  let html=`<button class="ghost" onclick="searchEstimateHistory()">← BACK TO RESULTS</button><h3 style="margin-bottom:4px">Estimate History</h3><div class="small">One property record. Earlier versions are stored as data only — no PDF files are stored.</div>`;
  html+=savedVersionCard(d.current,'CURRENT ESTIMATE',id,-1);
  (d.revisions||[]).forEach((v,i)=>{html+=savedVersionCard(v,`PREVIOUS VERSION ${i+1}`,id,i)});
  box.innerHTML=html;
 }catch(e){box.innerHTML='<div class="error" style="padding:14px 0">Could not load estimate history.</div>'}
}

function estimateActionMessage(message){
 const button=el('createEstimateBtn');if(!button)return;
 let box=el('estimateActionStatus');if(!box){box=document.createElement('div');box.id='estimateActionStatus';box.className='status error';box.setAttribute('role','status');box.setAttribute('aria-live','polite');(button.closest('.simple-actions')||button).after(box)}
 box.textContent=message;box.hidden=!message;
}
async function showCustomerEstimate(historicalMode=false,historicalDate='',correctionRefresh=false){
 if(!historicalMode&&!await confirmQaSubscriptionEditAccess())return;
 if(el('pdfLayoutHelp')){el('pdfLayoutHelp').textContent='';el('pdfLayoutHelp').style.display='none'}
 if(!historicalMode&&typeof manualRoofQa==='function'&&manualRoofQa()&&traceMode){status('Save or cancel the roof section before creating the estimate.','warn');return}
 if(!historicalMode){const issue=quotePricingError();if(issue){status(issue,'error');return}}
 if(el('backToDealerBtn'))el('backToDealerBtn').textContent=manualRoofQa()&&measurementViewMode==='auto'&&manualPlanes.length?'EDIT MEASUREMENT':historicalMode?'EDIT MEASUREMENTS / PRICE':'Back to Dealer View';
 // Historical aerials are frozen canvases, not interactive outline editors.
 // Never leave another report's roof/area/line buttons above the saved image.
 if(historicalMode&&el('reportOutlineControls')){el('reportOutlineControls').style.display='none';el('reportOutlineTargetButtons')?.replaceChildren()}
 const estimateRoofs=historicalMode?(quoteSnapshot?.structures||[]):structures;
 if(currentBusinessType()==='roofing'&&(historicalMode?(quoteSnapshot?.measurementMode||'auto'):measurementViewMode)==='auto')estimateRoofs.filter(st=>!st.manually_measured).forEach(st=>reviewAutomaticRoof(st));
 if((!historicalMode&&roofRemeasureTarget)||estimateRoofs.some(st=>st.needs_remeasure||st.automatic_review_warning)){status('Finish remeasuring the incomplete roof or roof with mismatched area and outline before creating the customer estimate.','warn');return}
 if(!historicalMode&&linearCorrectionOriginal){status('Save or cancel the line edit before creating the estimate.','warn');return}
 if((!historicalMode&&!sessionToken)||((measurementViewMode!=='linear'&&measurementViewMode!=='area')&&!structures.length&&!manualPlanes.length)){status('Load and measure a property first.','error');return}if(!historicalMode&&measurementViewMode==='linear'&&(!linearMeasurementSaved||linearPoints.length<2)){status('Save the linear measurement before creating the estimate.','error');return}if(!historicalMode&&measurementViewMode==='area'&&(!areaMeasurementSaved||areaPoints.length<3)){status('Save the area measurement before creating the estimate.','error');return}
 if(estimateOpenInProgress||(!correctionRefresh&&document.body.classList.contains('report-open')))return;
 estimateOpenInProgress=true;
 const createBtn=el('createEstimateBtn');if(createBtn)createBtn.disabled=true;
 let reportReady=false;
 try{
 estimateActionMessage('Preparing your estimate…');
 const estimatePricing=historicalMode&&quoteSnapshot.savedPricing?quoteSnapshot.savedPricing:priceCalc();
 if(!historicalMode)quoteSnapshot=captureQuoteSnapshot();
 if(customerMap){try{customerMap.remove()}catch(e){}customerMap=null}customerRgbLayer=null;customerOverlays=[];el('customerMap')?.replaceChildren();
 if(el('downloadPdfBtn'))el('downloadPdfBtn').disabled=true;
 reportOutlines={}; reportOutlineTarget=null; reportOutlineEditMode=false; reportOutlinePoints=[]; clearReportOutlineTemp();
 let calc=estimatePricing,snap=quoteSnapshot||captureQuoteSnapshot(),linearReport=snap.measurementMode==='linear',areaReport=snap.measurementMode==='area',reportStructures=snap.structures||[],reportManual=snap.manualPlanes||[],src=snap.measureSource||'google',reportManualTotal=reportManual.reduce((a,p)=>a+Number(p.surface_sqft||0),0),manualUsed=!linearReport&&!areaReport&&(src==='manual'&&reportManualTotal>0),hybridUsed=!linearReport&&!areaReport&&(src==='hybrid'&&reportManualTotal>0);
 el('rAddress').textContent=el('address').value;
 el('rDate').textContent=historicalDate?new Date(historicalDate+'T12:00:00').toLocaleDateString('en-US',{year:'numeric',month:'long',day:'numeric'}):new Date().toLocaleDateString('en-US',{year:'numeric',month:'long',day:'numeric'});if(el('rCustomerName'))el('rCustomerName').textContent=(el('customerName')?.value||'').trim()||(currentBusinessType()==='commercial'?'Property Manager / Client':'Homeowner');if(el('rCustomerPhone'))el('rCustomerPhone').textContent=(el('customerPhone')?.value||'').trim();if(el('rCustomerEmail'))el('rCustomerEmail').textContent=(el('customerEmail')?.value||'').trim();
 const dealerName=(el('dealerName')?el('dealerName').value.trim():'')||'';
 const dealerCompany=(el('dealerCompany')?el('dealerCompany').value.trim():'')||dealerName||'Your Company';
 const dealerEmail=(el('dealerEmail')?el('dealerEmail').value.trim():'')||'';
 const dealerWebsite=(el('dealerWebsite')?el('dealerWebsite').value.trim():'')||'';
 const dealerAddress=(el('dealerAddress')?el('dealerAddress').value.trim():'')||'';
 el('rPhone').textContent=el('dealerPhone').value;if(el('rPhoneWrap'))el('rPhoneWrap').style.display=el('dealerPhone').value.trim()?'inline':'none';if(el('rDealerCompany'))el('rDealerCompany').textContent=dealerCompany;if(el('rDealerName'))el('rDealerName').textContent=(dealerName&&dealerName!==dealerCompany)?dealerName:'';if(el('rDealerEmail'))el('rDealerEmail').textContent=dealerEmail;if(el('rDealerEmailWrap'))el('rDealerEmailWrap').style.display=dealerEmail?'inline':'none';if(el('rDealerWebsite'))el('rDealerWebsite').textContent=dealerWebsite;if(el('rDealerAddress'))el('rDealerAddress').textContent=dealerAddress;if(el('rDealerAddressWrap'))el('rDealerAddressWrap').style.display=dealerAddress?'inline':'none';if(el('rDealerLogo')){const rdl=el('rDealerLogo'),dls=dealerLogoSrc();if(dls){rdl.src=dls;rdl.classList.remove('noDealerLogo')}else{rdl.removeAttribute('src');rdl.classList.add('noDealerLogo')}}if(el('rEstimateSubtitle'))el('rEstimateSubtitle').textContent=dealerCompany;if(el('rEstimateDealerSub'))el('rEstimateDealerSub').textContent='Prepared by '+dealerCompany;if(el('rEstimateTitle'))el('rEstimateTitle').textContent=currentBusinessType()==='commercial'?'Commercial Property Measurement & Estimate':currentBusinessType()==='paving'?'Paving & Sealcoating Measurement & Estimate':currentBusinessType()==='landscaping'?'Landscaping Measurement & Estimate':currentBusinessType()==='pressure'?'Pressure Washing Measurement & Estimate':currentBusinessType()==='snow'?'Snow Removal Measurement & Estimate':(linearReport?'Linear Property Measurement & Estimate':(areaReport?'Area Property Measurement & Estimate':'Property Measurement & Estimate'));applyDealerMarketing()

 applyReportWarranty(snap,historicalMode);
 let imageChoice=((el('streetViewChoice')&&el('streetViewChoice').value)||'auto'),useSavedStreet=imageChoice==='auto'&&!!savedStreetImageData,useStreet=(!historicalMode&&!savedPropertyEditActive&&imageChoice==='auto'&&el('street')?.dataset.streetUnavailable!=='1')||useSavedStreet,useAerial=imageChoice!=='none';
 if(el('streetPlaceholder'))el('streetPlaceholder').style.display=useStreet?'none':'flex';
 if(el('customerMap'))el('customerMap').style.display=useAerial?'block':'none';
 if(el('customerMapPlaceholder'))el('customerMapPlaceholder').style.display=useAerial?'none':'flex';
 if(el('rStreet')){
   el('rStreet').style.display=useStreet?'block':'none';
   if(useStreet)showStreetViewImage(el('rStreet'),useSavedStreet?savedStreetImageData:'/street/'+sessionToken+'?v='+Date.now(),el('streetMeta').textContent,true);
   else{el('rStreet').removeAttribute('src');if(el('reportPropertyImageNote'))el('reportPropertyImageNote').textContent=imageChoice==='auto'?streetViewUnavailableMessage:'Property assessed using the selected imagery.'}
 }
 if(el('rStreetMeta'))el('rStreetMeta').textContent=useStreet?(historicalMode?(el('streetMeta').textContent||'Saved Google Street View'):el('streetMeta').textContent):(imageChoice==='none'?'Property imagery omitted':(imageChoice==='auto'?streetViewUnavailableMessage:(historicalMode?'Saved property aerial and roof outline':'Property assessment')));

 const snowReport=currentBusinessType()==='snow';
 let prop='';
 if(['landscaping','paving','pressure','snow'].includes(currentBusinessType())&&(snap.commercialAreas||[]).some(a=>a.sqft>0)){prop=`<div class="metric-grid"><div class="metric">Total Service Area<b>${fmt(snap.areaSqFt)} ft²</b></div></div>`+snap.commercialAreas.filter(a=>a.sqft>0).map(a=>`<div class="structure"><div class="structure-head"><b>${escapeHistory(a.name)}</b><b>${fmt(a.sqft)} ft²</b></div></div>`).join('')+(snap.linearFeet>0?`<div class="structure"><b>${surfaceServiceLabel()} Linear — ${Number(snap.linearFeet).toFixed(1)} ft</b></div>`:'')}
 else if(currentBusinessType()==='paving'&&snap.pavingCombined){prop='<div class="metric-grid"><div class="metric">Paved Area<b>'+fmt(Math.round(Number(snap.areaSqFt||0)))+' ft²</b></div><div class="metric">Linear Service<b>'+Number(snap.linearFeet||0).toFixed(1)+' ft</b></div></div>'}
 else if(currentBusinessType()==='pressure'&&snap.pressureCombined){prop=`<div class="metric-grid"><div class="metric">Cleaning Area<b>${fmt(Math.round(Number(snap.areaSqFt||0)))} ft²</b></div><div class="metric">Linear Cleaning<b>${Number(snap.linearFeet||0).toFixed(1)} ft</b></div></div>`}
 else if(currentBusinessType()==='landscaping'&&snap.landscapingCombined){prop=`<div class="metric-grid"><div class="metric">Landscaping Area<b>${fmt(Math.round(Number(snap.areaSqFt||0)))} ft²</b></div><div class="metric">Landscaping Linear<b>${Number(snap.linearFeet||0).toFixed(1)} ft</b></div></div>`}
 else if(currentBusinessType()==='commercial'&&(snap.commercialAreas||[]).some(a=>a.sqft>0)){prop=`<div class="metric-grid"><div class="metric">Total Measured Area<b>${fmt(calc.area)} ft²</b></div><div class="metric">Service Areas<b>${snap.commercialAreas.filter(a=>a.sqft>0).length}</b></div></div>`+(snap.commercialAreas||[]).filter(a=>a.sqft>0).map(a=>`<div class="structure"><div class="structure-head"><b>${escapeHistory(a.name||'Service Area')}</b><b>${fmt(a.sqft)} ft²</b></div></div>`).join('')+(snap.commercialLinearSaved?`<div class="structure"><div class="structure-head"><b>Linear Service</b><b>${Number(snap.linearFeet||0).toFixed(1)} ft</b></div></div>`:'')}
 else if(areaReport){prop=`<div class="metric-grid"><div class="metric">Area Measurement<b>${fmt(Number(snap.areaSqFt||calc.area))} ft²</b></div><div class="metric">Measurement Type<b>Area</b></div></div><div class="structure"><div class="structure-head"><b>Measured Service Area</b><b>${fmt(Number(snap.areaSqFt||calc.area))} ft²</b></div><div class="small">Measured from the service-area outline on the property aerial. Only the measured service area is included in this quote.</div></div>`}
 else if(linearReport){prop=`<div class="metric-grid"><div class="metric">Linear Measurement<b>${Number(snap.linearFeet||calc.area).toFixed(1)} ft</b></div><div class="metric">Measurement Type<b>Linear</b></div></div><div class="structure"><div class="structure-head"><b>Measured Service Length</b><b>${Number(snap.linearFeet||calc.area).toFixed(1)} linear ft</b></div><div class="small">Measured point-to-point on the property aerial. Only the measured service length is included in this quote.</div></div>`}
 else {prop=`<div class="metric-grid"><div class="metric">${snowReport?'Service Area':'Roof Area'}<b>${fmt(calc.area)} ft²</b></div><div class="metric">${snowReport?'Areas in Quote':'Roofs in Quote'}<b>${manualUsed?reportManual.length:reportStructures.length+(hybridUsed?reportManual.length:0)}</b></div></div>`;
 if(manualUsed){prop+=`<div class="structure"><div class="structure-head"><b>${snowReport?'Manual Area Measurement':'Dealer Manual Measurement'}</b><b>${fmt(reportManualTotal)} ft²</b></div><div class="small">${snowReport?'Only the service areas selected for this property are included in this estimate.':'Only the shingle roof planes traced by the dealer are included in this estimate.'}</div></div>`}else{reportStructures.forEach((st,i)=>{let ps=structurePitchSummary(st);prop+=`<div class="structure"><div class="structure-head"><b>${snowReport?(i===0?'Primary Service Area':'Additional Area '+i):(reportStructures.length>3?'#'+(i+1)+' · ':'')+st.label}</b><b>${fmt(st.total_roof_sqft)} ft²</b></div><div class="small">${snowReport?`Automatic area measurement • ${st.imagery_quality||'—'} quality`:`${st.manually_measured?roofMeasurementSourceLabel(st):'Google measured'} • ${ps.complex?`Multiple roof pitches ${ps.detail}`:`Pitch ${ps.label}`}${st.manually_measured?'':` • ${st.imagery_quality||'—'} quality`}`}</div></div>`});if(hybridUsed){reportManual.forEach((p,i)=>{prop+=`<div class="structure"><div class="structure-head"><b>${snowReport?(reportManual.length===1?'Additional Service Area':'Additional Service Area '+(i+1)):(reportManual.length===1?'Added Roof':'Added Roof '+(i+1))}</b><b>${fmt(p.surface_sqft)} ft²</b></div><div class="small">${snowReport?'Manual area measurement':`Dealer traced • ${p.pitch_degrees.toFixed(1)}° pitch used`}</div></div>`})}}}
 el('rProperty').innerHTML=prop;
 if(el('reportPropertyImageNote'))el('reportPropertyImageNote').textContent=imageChoice==='auto'&&!useStreet?streetViewUnavailableMessage:linearReport?'Linear service length measured using available aerial imagery.':(areaReport?'Service area measured using available aerial imagery.':(snowReport?'Service area measured using available aerial imagery.':'Roof measured using available aerial imagery.'));

 let price='';
 if(['landscaping','paving','pressure','snow'].includes(currentBusinessType())&&(snap.commercialAreas||[]).some(a=>a.sqft>0)){price+=savedSurfacePriceLines(snap)}
 else if(currentBusinessType()==='paving'&&snap.pavingCombined){price+='<div class="line"><span>Paving Area — '+fmt(Math.round(Number(snap.areaSqFt||0)))+' ft² × '+money(snap.pavingAreaRate)+'/ft²</span><b>'+money(decimalCurrency('product',[Math.round(Number(snap.areaSqFt||0)),Number(snap.pavingAreaRate||0)]))+'</b></div><div class="line"><span>Paving Linear — '+Number(snap.linearFeet||0).toFixed(1)+' ft × '+money(snap.pavingLinearRate)+'/ft</span><b>'+money(decimalCurrency('product',[Number(snap.linearFeet||0),Number(snap.pavingLinearRate||0)]))+'</b></div>'}
 else if(currentBusinessType()==='pressure'&&snap.pressureCombined){price+=`<div class="line"><span>Pressure Washing Area — ${fmt(Math.round(Number(snap.areaSqFt||0)))} ft² × ${money(snap.pressureAreaRate)}/ft²</span><b>${money(decimalCurrency('product',[Math.round(Number(snap.areaSqFt||0)),Number(snap.pressureAreaRate||0)]))}</b></div><div class="line"><span>Pressure Washing Linear — ${Number(snap.linearFeet||0).toFixed(1)} ft × ${money(snap.pressureLinearRate)}/ft</span><b>${money(decimalCurrency('product',[Number(snap.linearFeet||0),Number(snap.pressureLinearRate||0)]))}</b></div>`}
 else if(currentBusinessType()==='landscaping'&&snap.landscapingCombined){price+=`<div class="line"><span>Landscaping Area — ${fmt(Math.round(Number(snap.areaSqFt||0)))} ft² × ${money(snap.landscapingAreaRate)}/ft²</span><b>${money(decimalCurrency('product',[Math.round(Number(snap.areaSqFt||0)),Number(snap.landscapingAreaRate||0)]))}</b></div><div class="line"><span>Landscaping Linear — ${Number(snap.linearFeet||0).toFixed(1)} ft × ${money(snap.landscapingLinearRate)}/ft</span><b>${money(decimalCurrency('product',[Number(snap.linearFeet||0),Number(snap.landscapingLinearRate||0)]))}</b></div>`}
 else if(currentBusinessType()==='commercial'&&((snap.commercialAreas||[]).some(a=>a.sqft>0)||snap.commercialLinearSaved)){(snap.commercialAreas||[]).forEach(a=>{if(a.sqft>0)price+=`<div class="line"><span>${escapeHistory(a.name||'Service Area')} — ${fmt(a.sqft)} ft² × ${money(a.rate)}/ft²</span><b>${money(decimalCurrency('product',[a.sqft,a.rate]))}</b></div>`});if(snap.commercialLinearSaved)price+=`<div class="line"><span>Linear Service — ${Number(snap.linearFeet||0).toFixed(1)} ft × ${money(snap.commercialLinearRate)}/ft</span><b>${money(decimalCurrency('product',[Number(snap.linearFeet||0),Number(snap.commercialLinearRate||0)]))}</b></div>`}
 else if(areaReport){price+=`<div class="line"><span>${currentBusinessType()==='paving'?'Paving & Sealcoating':(currentBusinessType()==='pressure'?'Pressure Washing':currentBusinessType()==='landscaping'?'Landscaping Service':'Area Service')} — ${fmt(Number(snap.areaSqFt||calc.area))} ft² × ${money(calc.price)}</span><b>${money(calc.subtotal)}</b></div>`}
 else if(linearReport){price+=`<div class="line"><span>Linear Service — ${Number(snap.linearFeet||calc.area).toFixed(1)} ft × ${money(calc.price)}</span><b>${money(calc.subtotal)}</b></div>`}
 else if(manualUsed){
   price+=`<div class="line"><span>${snowReport?'Snow Removal Service — Manual Area Measurement':'Roofing Service — Manual Measurement'}</span><b>${money(calc.subtotal)}</b></div>`;
 }else{
   const totalArea=calc.area||1;
   structures.forEach((st,i)=>{
     let share=Number(st.total_roof_sqft||0)/totalArea;
     price+=`<div class="line"><span>${snowReport?'Snow Removal Service — '+(i===0?'Primary Service Area':'Additional Service Area '+i):'Service — '+st.label}</span><b>${money(calc.subtotal*share)}</b></div>`;
   });
   if(hybridUsed){reportManual.forEach((p,i)=>{let share=Number(p.surface_sqft||0)/totalArea;price+=`<div class="line"><span>Service — ${reportManual.length===1?'Added Area':'Added Area '+(i+1)}</span><b>${money(calc.subtotal*share)}</b></div>`})}
 }
 if(calc.extraAmount>0)price+=`<div class="line"><span>${escapeHistory(calc.extraDescription||'Additional Services / Repairs')}</span><b>${money(calc.extraAmount)}</b></div>`;
 if(calc.mode==='discount')price+=`<div class="line"><span>Promotion Discount (${calc.disc}%)</span><b>-${money(calc.discount)}</b></div>`;
 if(calc.mode==='included'){
   price+=`<div class="line"><span>Promotional Pricing</span><b>Taxes Included</b></div>`;
 }else{
   price+=`<div class="line"><span>Subtotal Before Tax</span><b>${money(calc.taxBase)}</b></div><div class="line"><span>Sales Tax (${calc.gst}%)</span><b>${money(calc.gstAmt)}</b></div>${calc.pst?`<div class="line"><span>Additional Tax (${calc.pst}%)</span><b>${money(calc.pstAmt)}</b></div>`:''}`;
 }
 price+=`<div class="line grand"><span>TOTAL (${currencyCode()})</span><span>${money(calc.total)}${escapeHistory(estimatePeriodSuffix(calc.estimatePeriod))}</span></div>`;
 el('rPricing').innerHTML=price;
 if(!historicalMode&&!correctionRefresh&&(await saveEstimateHistory())===false){estimateActionMessage(el('status')?.textContent||'Estimate was not saved. Your measurements are still here.');return}
 reportOpenedAt=Date.now();
 document.body.classList.add('report-open');
 el('reportOverlay').style.display='block';reportReady=true;estimateActionMessage('');
 if(historicalMode){const moneyIssue=savedEstimateMoneyIssue(quoteSnapshot?.savedPricing);if(moneyIssue){const moneyWarning=document.createElement('div');moneyWarning.className='warning';moneyWarning.setAttribute('role','alert');moneyWarning.textContent=moneyIssue;el('rPricing').appendChild(moneyWarning)}}
 if(!historicalMode&&!correctionRefresh){usage.reports++;updateUsage();}
 if(customerMapBuildTimer)clearTimeout(customerMapBuildTimer);
 try{if(!useAerial)buildSavedRoofOutlineSnapshot();else if(historicalMode)await buildSavedHistoricalSnapshot();else await buildCustomerMap()}catch(e){console.error('AQ:estimate-image-failed');if(el('customerMapPlaceholder')){el('customerMap').style.display='none';el('customerMapPlaceholder').style.display='flex';el('customerMapPlaceholder').textContent='Property image could not be rebuilt.'}}finally{customerMapBuildTimer=null;estimateOpenInProgress=false;if(createBtn)createBtn.disabled=false;if(el('downloadPdfBtn'))el('downloadPdfBtn').disabled=false}

 // Final business-specific estimate-summary label.
 if(currentBusinessType()==='roofing'){
   document.querySelectorAll('#reportCard .line span, #customerEstimate .line span, .report .line span').forEach(x=>{
     if((x.textContent||'').trim()==='Service — Main House')x.textContent='Roofing Service — Main House';
   });
 }
 }catch(e){
  console.error('AQ:estimate-prepare-failed');
  if(!reportReady){document.body.classList.remove('report-open');if(el('reportOverlay'))el('reportOverlay').style.display='none'}
  const message='Estimate could not be prepared. Your measurements are still here. Please try again.';
  estimateActionMessage(message);status(message,'error');
 }finally{
  estimateOpenInProgress=false;if(createBtn)createBtn.disabled=false;
  if(el('downloadPdfBtn'))el('downloadPdfBtn').disabled=!reportReady;
 }
}

function pdfRoofPointsForTarget(key,snap){
 if(key&&key.startsWith('structure-')){
   const i=Number(key.split('-')[1]),st=(snap.structures||[])[i];
   if(!st)return[];
   if(Array.isArray(reportOutlines[key])&&reportOutlines[key].length>=3)return reportOutlines[key];
   if(i===0&&Array.isArray(adjustedOutline)&&adjustedOutline.length>=3)return adjustedOutline;
   return Array.isArray(st.outline)?st.outline:[];
 }
 if(key&&key.startsWith('manual-')){
   const i=Number(key.split('-')[1]),p=(snap.manualPlanes||[])[i];
   if(!p)return[];
   if(Array.isArray(reportOutlines[key])&&reportOutlines[key].length>=3)return reportOutlines[key];
   return Array.isArray(p.points)?p.points:[];
 }
 return[];
}
function pdfDrawRoofPolygon(ctx,pts,color,fill,w,h){
 if(!customerMap||!Array.isArray(pts)||pts.length<3)return;
 const px=pts.map(ll=>customerMap.latLngToContainerPoint(L.latLng(ll[0],ll[1])));
 ctx.beginPath();ctx.moveTo(px[0].x,px[0].y);
 for(let i=1;i<px.length;i++)ctx.lineTo(px[i].x,px[i].y);
 ctx.closePath();ctx.fillStyle=fill;ctx.fill();
 ctx.strokeStyle=color;ctx.lineWidth=4;ctx.lineJoin='round';ctx.stroke();
}
function pdfDrawPitchLabel(ctx,lat,lng,text){
 if(!customerMap)return;
 const p=customerMap.latLngToContainerPoint(L.latLng(lat,lng));
 ctx.font='700 14px Arial, sans-serif';
 const padX=5,h=23,tw=Math.ceil(ctx.measureText(text).width)+padX*2,x=p.x-tw/2,y=p.y-h/2;
 ctx.fillStyle='rgba(255,255,255,.94)';ctx.strokeStyle='#d49b22';ctx.lineWidth=1.5;
 ctx.beginPath();
 if(ctx.roundRect)ctx.roundRect(x,y,tw,h,5);else ctx.rect(x,y,tw,h);
 ctx.fill();ctx.stroke();
 ctx.fillStyle='#5b4a22';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(text,p.x,p.y+1);
}
function customerPdfVectorSnapshot(){
 if(!customerMap)return null;
 const host=el('customerMap');if(!host)return null;
 const size=customerMap.getSize();
 const ns='http://www.w3.org/2000/svg';
 const svg=document.createElementNS(ns,'svg');
 svg.setAttribute('width',size.x);svg.setAttribute('height',size.y);svg.setAttribute('viewBox',`0 0 ${size.x} ${size.y}`);
 svg.style.position='absolute';svg.style.left='0';svg.style.top='0';svg.style.width='100%';svg.style.height='100%';svg.style.zIndex='450';svg.style.pointerEvents='none';
 const addPoly=(pts,stroke,fill,opacity)=>{if(!Array.isArray(pts)||pts.length<3)return;const xy=pts.map(v=>{const lat=v.lat!==undefined?v.lat:v[0],lng=v.lng!==undefined?v.lng:v[1],q=customerMap.latLngToContainerPoint([lat,lng]);return `${q.x.toFixed(1)},${q.y.toFixed(1)}`}).join(' ');const poly=document.createElementNS(ns,'polygon');poly.setAttribute('points',xy);poly.setAttribute('fill',fill);poly.setAttribute('fill-opacity',opacity);poly.setAttribute('stroke',stroke);poly.setAttribute('stroke-width','4');poly.setAttribute('stroke-linejoin','round');svg.appendChild(poly)};
 const snap=quoteSnapshot||captureQuoteSnapshot();
 (snap.structures||[]).forEach((st,i)=>{
   const key=`structure-${i}`;
   let pts=(Array.isArray(reportOutlines[key])&&reportOutlines[key].length>=3)?reportOutlines[key]:null;
   if(!pts&&i===0&&Array.isArray(adjustedOutline)&&adjustedOutline.length>=3)pts=adjustedOutline;
   if(!pts)pts=st.outline;
   addPoly(pts,i===0?'#2d6cdf':'#18a7a0',i===0?'#2d6cdf':'#18a7a0','0.055');
 });
 (snap.manualPlanes||[]).forEach((p,i)=>{
   const key=`manual-${i}`;
   const pts=(Array.isArray(reportOutlines[key])&&reportOutlines[key].length>=3)?reportOutlines[key]:p.points;
   addPoly(pts,'#d97706','#f59e0b','0.12');
 });
 host.appendChild(svg);
 const pane=customerMap.getPane('overlayPane'),old=pane?pane.style.visibility:'';if(pane)pane.style.visibility='hidden';
 return()=>{if(pane)pane.style.visibility=old;try{svg.remove()}catch(e){}};
}
function paintCustomerPdfLabels(ctx,host){
 const hidden=[],origin=host.getBoundingClientRect();
 customerOverlays.forEach(layer=>{const marker=layer.getElement?.(),node=marker?.querySelector('.aeri-edge-label,.linear-seg-label,.area-label,.edge-label,.seg-label,.manual-label');if(!node)return;
  const rect=node.getBoundingClientRect(),style=getComputedStyle(node),point=customerMap.latLngToContainerPoint(layer.getLatLng()),w=rect.width||node.textContent.length*7+14,h=rect.height||26,x=rect.width?rect.left-origin.left:point.x+(parseFloat(node.style.left)||-w/2),y=rect.height?rect.top-origin.top:point.y+(parseFloat(node.style.top)||-h/2);
  ctx.save();ctx.strokeStyle=style.color||'#7357b8';ctx.lineWidth=1;
  if(!node.dataset.roofSummary&&Math.hypot(x+w/2-point.x,y+h/2-point.y)>4){ctx.beginPath();ctx.moveTo(point.x,point.y);ctx.lineTo(x+w/2,y+h/2);ctx.stroke()}
  ctx.fillStyle='#fff';ctx.fillRect(x,y,w,h);ctx.strokeRect(x,y,w,h);ctx.fillStyle=style.color||'#283653';ctx.font=(style.fontWeight||'800')+' '+(style.fontSize||'12px')+' '+(style.fontFamily||'Arial');ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(node.textContent,x+w/2,y+h/2);ctx.restore();
  hidden.push({node:marker,visibility:marker.style.visibility});marker.style.visibility='hidden';
 });return hidden;
}
function fitExpandedStreetBlock(block,column,maxHeight){
 const image=block.querySelector('[data-expanded-street-image]');
 if(!image||column.scrollHeight<=maxHeight)return;
 const height=parseFloat(image.style.height),reduced=height-(column.scrollHeight-maxHeight)-2;
 if(reduced>=100){const width=parseFloat(image.style.width);image.style.width=(width*reduced/height)+'px';image.style.height=reduced+'px';}
}

function expandedAerialSize(width,height,maxWidth,maxHeight){
 if(![width,height,maxWidth,maxHeight].every(v=>Number.isFinite(v)&&v>0))throw new Error('Invalid expanded aerial dimensions. Reopen the estimate and retry.');
 const scale=Math.min(maxWidth/width,maxHeight/height);
 return{width:width*scale,height:height*scale};
}
function expandedLeaderSegments(start,end,boxes,gap=2){
 const dx=end.x-start.x,dy=end.y-start.y;if(Math.hypot(dx,dy)<.01)return[];
 const blocked=[];
 for(const box of boxes){
  let lo=0,hi=1,hit=true;
  for(const [origin,delta,min,max] of [[start.x,dx,box.x-gap,box.x+box.w+gap],[start.y,dy,box.y-gap,box.y+box.h+gap]]){
   if(Math.abs(delta)<1e-10){if(origin<min||origin>max){hit=false;break}}
   else{const a=(min-origin)/delta,b=(max-origin)/delta;lo=Math.max(lo,Math.min(a,b));hi=Math.min(hi,Math.max(a,b));if(lo>hi){hit=false;break}}
  }
  if(hit&&hi>=0&&lo<=1)blocked.push([Math.max(0,lo),Math.min(1,hi)]);
 }
 blocked.sort((a,b)=>a[0]-b[0]);const segments=[];let cursor=0;
 const point=t=>({x:start.x+dx*t,y:start.y+dy*t});
 for(const [lo,hi] of blocked){if(lo>cursor)segments.push([point(cursor),point(lo)]);cursor=Math.max(cursor,hi)}
 if(cursor<1)segments.push([point(cursor),point(1)]);
 return segments;
}

function savedAerialPoint(point,view,frame){
 const world=256*Math.pow(2,view.zoom),xy=(lat,lng)=>{const v=Math.sin(lat*Math.PI/180);return[(lng+180)/360*world,(.5-Math.log((1+v)/(1-v))/(4*Math.PI))*world]},q=xy(point[0],point[1]),c=xy(view.latitude,view.longitude);
 return{x:frame.x+frame.width/2+(q[0]-c[0])*frame.width/view.width,y:frame.y+frame.height/2+(q[1]-c[1])*frame.height/view.height};
}

async function buildExpandedEstimatePDF(report){
 // Reuse the approved map pixels. Never resize/refit Leaflet or alter quote data.
 const options={scale:2,useCORS:true,allowTaint:false,backgroundColor:'#ffffff',logging:false};
 const outlineOnly=(el('streetViewChoice')?.value||'auto')==='none'&&!!el('customerMap')?.querySelector('canvas[data-saved-roof-outline]');
 const hasAerial=(el('streetViewChoice')?.value||'auto')!=='none'||outlineOnly;
 const aerial=outlineOnly?el('customerMap').querySelector('canvas[data-saved-roof-outline]'):(hasAerial?await html2canvas(el('customerMap'),options):null);
 const areas=(activeSavedDiagramSnapshot(quoteSnapshot||{}).commercialAreas||[]).filter(a=>a.sqft>0&&a.points?.length>=3);
 if(aerial&&areas.length){const host=el('customerMap'),savedCanvas=host.querySelector('canvas'),savedView=savedCanvas?.dataset.mapView,view=savedView?JSON.parse(savedView):null,hostRect=host.getBoundingClientRect(),savedRect=savedCanvas?.getBoundingClientRect(),frame=savedRect?{x:savedRect.left-hostRect.left,y:savedRect.top-hostRect.top,width:savedRect.width,height:savedRect.height}:null;
 const project=p=>{if(customerMap)return customerMap.latLngToContainerPoint(L.latLng(p[0],p[1]));if(!view||!frame)throw new Error('Reopen this estimate to restore aerial coordinates before expanded export.');return savedAerialPoint(p,view,frame)};
 const occupied=customerMap?[...host.querySelectorAll('.aeri-edge-label,.linear-seg-label,.area-label,.edge-label,.seg-label,.manual-label')].map(n=>{const r=n.getBoundingClientRect(),h=host.getBoundingClientRect();return{x:r.left-h.left,y:r.top-h.top,w:r.width,h:r.height}}):JSON.parse(savedCanvas?.dataset.labelBoxes||'[]').map(b=>({x:frame.x+b.x*frame.width/savedCanvas.width,y:frame.y+b.y*frame.height/savedCanvas.height,w:b.w*frame.width/savedCanvas.width,h:b.h*frame.height/savedCanvas.height}));
 const ctx=aerial.getContext('2d'),scale=aerial.width/host.clientWidth;ctx.save();ctx.setTransform(1,0,0,1,0,0);ctx.scale(scale,scale);areas.forEach((a,i)=>{const pts=a.points.map(project),x=Math.max(17,Math.min(el('customerMap').clientWidth-17,(Math.min(...pts.map(p=>p.x))+Math.max(...pts.map(p=>p.x)))/2)),y=Math.max(17,Math.min(el('customerMap').clientHeight-17,(Math.min(...pts.map(p=>p.y))+Math.max(...pts.map(p=>p.y)))/2));const box=measurementLabelPosition(x,y,26,26,occupied,host.clientWidth,host.clientHeight,5),bx=box.x+13,by=box.y+13;if(Math.hypot(bx-x,by-y)>5){ctx.beginPath();for(const [from,to] of expandedLeaderSegments({x,y},{x:bx,y:by},occupied)){ctx.moveTo(from.x,from.y);ctx.lineTo(to.x,to.y)}ctx.strokeStyle='#0b193e';ctx.lineWidth=1.5;ctx.stroke()}ctx.beginPath();ctx.arc(bx,by,11,0,Math.PI*2);ctx.fillStyle='#0b193e';ctx.fill();ctx.strokeStyle='#fff';ctx.lineWidth=2;ctx.stroke();ctx.fillStyle='#fff';ctx.font='bold 14px Arial';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(String(i+1),bx,by)});ctx.restore()}

 const root=document.createElement('div');root.className='expandedPdfExport';
 Object.assign(root.style,{position:'absolute',left:'-20000px',top:'0',width:'1200px',color:'#18352a',background:'#fff',fontFamily:'Arial,sans-serif',fontSize:'17px',lineHeight:'1.35'});
 document.body.appendChild(root);
 const clone=node=>{if(!node)return null;const copy=node.cloneNode(true);copy.removeAttribute('id');copy.querySelectorAll('[id]').forEach(n=>n.removeAttribute('id'));return copy};
 function splitExpandedTextBlock(block,column,maxHeight){
  const text=block.textContent||'';if(!text.trim())return null;
  const fragment=(start,end)=>{const range=document.createRange(),walker=document.createTreeWalker(block,NodeFilter.SHOW_TEXT);let node,total=0,first=null,last=null;while(node=walker.nextNode()){const next=total+node.length;if(first===null&&start<=next)first={node,offset:Math.max(0,start-total)};if(end<=next){last={node,offset:Math.max(0,end-total)};break}total=next}if(!first||!last)return null;range.setStart(first.node,first.offset);range.setEnd(last.node,last.offset);const copy=block.cloneNode(false);copy.appendChild(range.cloneContents());return copy};
  const fits=end=>{const copy=fragment(0,end);if(!copy)return false;column.appendChild(copy);const ok=column.scrollHeight<=maxHeight;copy.remove();return ok};
  let lo=0,hi=text.length;while(lo<hi){const mid=Math.ceil((lo+hi)/2);if(fits(mid))lo=mid;else hi=mid-1}
  if(!lo||lo>=text.length)return null;
  const space=text.slice(0,lo).lastIndexOf(' ');if(space>lo*.8)lo=space+1;
  const head=fragment(0,lo),tail=fragment(lo,text.length);if(!head||!tail||!head.textContent.trim()||!tail.textContent.trim())return null;
  if(head.textContent+tail.textContent!==text)throw new Error('Expanded text pagination did not preserve the complete section.');
  return {head,tail};
 }
 const pages=[],bodies=[];
 function page(title){const box=document.createElement('div');box.className='aq-expanded-page';Object.assign(box.style,{width:'1200px',height:'927px',padding:'24px',boxSizing:'border-box',background:'#fff',position:'relative',overflow:'hidden'});root.appendChild(box);
 const head=document.createElement('div');Object.assign(head.style,{display:'flex',alignItems:'center',gap:'20px',borderBottom:'2px solid #0b193e',paddingBottom:'10px'});const logo=el('rDealerLogo');if(logo?.getAttribute('src')&&!logo.classList.contains('noDealerLogo')){const image=clone(logo);const ratio=(logo.naturalWidth||1)/(logo.naturalHeight||1),h=Math.min(65,170/ratio);Object.assign(image.style,{width:(h*ratio)+'px',height:h+'px',maxHeight:'65px',flexShrink:'0'});head.appendChild(image)}const text=document.createElement('div');const name=document.createElement('strong');name.textContent=el('rEstimateTitle').textContent;Object.assign(name.style,{fontSize:'23px',color:'#0b193e'});const company=document.createElement('div');company.textContent=el('rEstimateSubtitle').textContent;text.append(name,company);head.appendChild(text);const shield=el('rWarrantyShield');if(shield&&shield.style.display!=='none'&&shield.getAttribute('src')){const badge=clone(shield);Object.assign(badge.style,{display:'block',width:'80px',height:'80px',objectFit:'contain',marginLeft:'auto'});head.appendChild(badge)}box.appendChild(head);
 const meta=document.createElement('div');Object.assign(meta.style,{fontSize:'14px',margin:'10px 0',display:'grid',gridTemplateColumns:'minmax(0,1.5fr) minmax(0,1fr)',gap:'12px',overflowWrap:'anywhere'});const address=document.createElement('div');address.dataset.expandedAddress='true';address.textContent=el('rAddress').textContent;const customer=document.createElement('div');customer.dataset.expandedCustomer='true';const customerTitle=document.createElement('div');customerTitle.textContent=el('rCustomerName').textContent+' | '+el('rDate').textContent;customer.appendChild(customerTitle);for(const id of ['rCustomerPhone','rCustomerEmail']){const value=el(id)?.textContent?.trim();if(value){const contact=document.createElement('div');contact.textContent=value;customer.appendChild(contact)}}meta.append(address,customer);box.appendChild(meta);
 const heading=document.createElement('div');heading.className='reportTitle';heading.textContent=title;box.appendChild(heading);
 const body=document.createElement('div');Object.assign(body.style,{paddingTop:'12px',height:(877-(body.offsetTop||0))+'px'});box.appendChild(body);body.style.height=(877-body.offsetTop)+'px';
 const foot=document.createElement('div');Object.assign(foot.style,{position:'absolute',left:'24px',right:'24px',bottom:'14px',fontSize:'12px',display:'flex',justifyContent:'space-between'});const note=document.createElement('span');note.textContent=report.querySelector('.reportFoot')?.textContent||'';const number=document.createElement('span');number.dataset.pageNumber='true';foot.append(note,number);box.appendChild(foot);pages.push(box);bodies.push(body);return body}
 try{
  const mapBody=page(outlineOnly?'SAVED ROOF OUTLINE - IMAGERY OMITTED':'PROPERTY AERIAL - MEASURED SERVICE AREAS');
  if(aerial){const legend=document.createElement('div');Object.assign(legend.style,{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:'5px 14px',fontSize:'14px',paddingTop:'8px'});areas.forEach((a,i)=>{const item=document.createElement('div');item.textContent=(i+1)+'. '+(a.name||'Service Area')+' - '+fmt(a.sqft)+' ft²';legend.appendChild(item)});mapBody.appendChild(legend);const img=document.createElement('img');img.src=aerial.toDataURL('image/jpeg',.95);const fitted=expandedAerialSize(aerial.width,aerial.height,mapBody.clientWidth,mapBody.clientHeight-legend.offsetHeight-10);img.dataset.expandedAerial='true';Object.assign(img.style,{display:'block',width:fitted.width+'px',height:fitted.height+'px',margin:'0 auto'});mapBody.insertBefore(img,legend);await img.decode()}
  else{const note=document.createElement('p');note.textContent='Property imagery omitted from this estimate.';mapBody.appendChild(note)}
  const left=[],right=[];
  const title=text=>{const n=document.createElement('div');n.className='reportTitle';n.textContent=text;return n};
  left.push(title('MEASUREMENTS'));
  [...el('rProperty').children].forEach(n=>left.push(clone(n)));
  right.push(title('ESTIMATE SUMMARY'));
  [...el('rPricing').children].forEach(n=>right.push(clone(n)));
  const marketing=el('rMarketingPanel');if(marketing&&!marketing.classList.contains('marketingHidden')){const section=document.createElement('div');section.appendChild(clone(el('rMarketingHeading')));[...el('rMarketingBenefits').children].forEach(n=>section.appendChild(clone(n)));const warranty=el('rMarketingWarranty');if(warranty&&!warranty.classList.contains('marketingHidden'))section.appendChild(clone(warranty));left.push(section)}
  const cta=report.querySelector('.cta');if(cta)right.push(clone(cta));
  const street=el('rStreet');if(street&&street.style.display!=='none'&&street.complete&&street.naturalWidth){const image=clone(street);const fitted=expandedAerialSize(street.naturalWidth,street.naturalHeight,565,170);Object.assign(image.style,{display:'block',width:fitted.width+'px',height:fitted.height+'px',margin:'0 auto'});image.dataset.expandedStreetImage='true';const block=document.createElement('div');block.appendChild(image);block.appendChild(clone(el('rStreetMeta')));right.push(block)}
  let continuation=false;
  while(left.length||right.length){const body=page(continuation?'ESTIMATE DETAILS - CONTINUED':'MEASUREMENTS & ESTIMATE DETAILS');Object.assign(body.style,{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'22px',alignItems:'start'});
   for(const queue of [left,right]){const col=document.createElement('div');col.style.minWidth='0';body.appendChild(col);let added=0;
    while(queue.length){const block=queue[0];block.style.overflowWrap='anywhere';block.style.breakInside='avoid';col.appendChild(block);fitExpandedStreetBlock(block,col,body.clientHeight);
     if(col.scrollHeight>body.clientHeight){block.remove();if(!added){const split=splitExpandedTextBlock(block,col,body.clientHeight);if(!split)throw new Error('An estimate section cannot fit on an expanded page. Review that section before exporting.');col.appendChild(split.head);queue[0]=split.tail;}break}
     queue.shift();added++;
    }
   }continuation=true;
  }
  const {jsPDF}=window.jspdf,pdf=new jsPDF({orientation:'landscape',unit:'in',format:'letter',compress:true});
  let repeatedHeader=null;const repeatedHeaderHeight=pages[0].querySelector('.reportTitle').offsetTop;
  pages.forEach(p=>p.style.display='none');
  for(let i=0;i<pages.length;i++){pages[i].style.display='block';pages[i].querySelector('[data-page-number]').textContent='Page '+(i+1)+' of '+pages.length;const canvas=await html2canvas(pages[i],options);if(i)pdf.addPage();pdf.addImage(canvas.toDataURL('image/jpeg',.94),'JPEG',0,0,11,8.5,undefined,'FAST');
   // Reuse the first page header pixels so every continuation has identical branding.
   if(!i){const header=document.createElement('canvas');header.width=canvas.width;header.height=Math.round(canvas.height*repeatedHeaderHeight/927);header.getContext('2d').drawImage(canvas,0,0,header.width,header.height,0,0,header.width,header.height);repeatedHeader=header.toDataURL('image/jpeg',.95)}
   else if(repeatedHeader)pdf.addImage(repeatedHeader,'JPEG',0,0,11,repeatedHeaderHeight/927*8.5,undefined,'FAST');
   pages[i].style.display='none'}
  return pdf;
 }finally{root.remove()}
}

function singlePageReadability(report){
 // Measure the same export layout before rasterizing; 72 points per printed inch.
 // Footer, branding and aerial labels keep their existing styling. Financial,
 // measurement and primary customer text must stay at least 7 printed points.
 const box=report.getBoundingClientRect(),width=Math.max(box.width||0,report.scrollWidth||0),height=Math.max(box.height||0,report.scrollHeight||0),view=report.ownerDocument.defaultView;
 const nodes=[...report.querySelectorAll('.reportPrice .line,.reportPrice .line *,.reportBody .structure,.reportBody .metric,.reportMeta > div > div:not(.small)')];
 const fonts=nodes.filter(n=>n.textContent.trim()&&n.getClientRects().length).map(n=>parseFloat(view.getComputedStyle(n).fontSize)).filter(n=>Number.isFinite(n)&&n>0);
 if(!width||!height||!fonts.length)return{measured:false,readable:true}; // Layout-free DOM test doubles cannot supply print dimensions.
 const fontPx=Math.min(...fonts),points=fontPx*Math.min(10.64/width,8.14/height)*72;
 return{measured:true,width,height,fontPx,points,minimumPoints:7,readable:points>=7};
}
function assertSinglePageLegible(report){
 const fit=singlePageReadability(report);
 if(fit.measured&&!fit.readable){const error=new Error('This estimate has too much detail for a readable Single page. Expanded PDF is selected. Click DOWNLOAD ESTIMATE PDF to keep all details readable. Your saved estimate is unchanged.');error.code='SINGLE_PAGE_DENSE';throw error}
}

async function captureSinglePageEstimate(report){
 const options={scale:2,useCORS:true,allowTaint:false,backgroundColor:'#ffffff',logging:false,onclone:(doc,copy)=>{
  // Remove only spare vertical price-row padding in the export clone; keep type size and all content.
  copy.querySelectorAll('.reportPrice .line').forEach(n=>{n.style.paddingTop='4px';n.style.paddingBottom='4px'});
  assertSinglePageLegible(copy);
  // html2canvas ignores object-fit. Fit the original pixels inside the same photo box,
  // only in its export clone: no live layout, map, source URL or quote data changes.
  const source=report.querySelector('#rStreet'),image=copy.querySelector('.reportStreet');
  if(!image||!source?.complete||!source.naturalWidth||!source.naturalHeight||!image.clientWidth||!image.clientHeight)return;
  const frame=doc.createElement('canvas');frame.width=image.clientWidth*2;frame.height=image.clientHeight*2;frame.className=image.className;frame.id=image.id;frame.style.cssText=image.style.cssText;
  const scale=Math.min(frame.width/source.naturalWidth,frame.height/source.naturalHeight),width=source.naturalWidth*scale,height=source.naturalHeight*scale,ctx=frame.getContext('2d');
  ctx.fillStyle='#ffffff';ctx.fillRect(0,0,frame.width,frame.height);ctx.drawImage(source,(frame.width-width)/2,(frame.height-height)/2,width,height);image.replaceWith(frame);
 }};
 if(report.getBoundingClientRect().width>=900)return html2canvas(report,options);
 // Phone presentation must not become a tiny, tall strip on landscape paper.
 // Freeze the approved map pixels before cloning; never resize/refit live Leaflet.
 const sourceMap=report.querySelector('#customerMap');
 const savedPixels=sourceMap?.querySelector('canvas[data-map-view]');
 let mapPixels=null;
 if(sourceMap&&sourceMap.style.display!=='none'){
  if(savedPixels){mapPixels=document.createElement('canvas');mapPixels.width=savedPixels.width;mapPixels.height=savedPixels.height;mapPixels.getContext('2d').drawImage(savedPixels,0,0);}
  else mapPixels=await html2canvas(sourceMap,options);
 }
 const copy=report.cloneNode(true);copy.classList.add('pdf-export');
 Object.assign(copy.style,{position:'absolute',left:'-20000px',top:'0',width:'1320px',maxWidth:'none',margin:'0'});
 if(mapPixels){const host=copy.querySelector('#customerMap');host.replaceChildren(mapPixels);Object.assign(host.style,{height:'430px',position:'relative',display:'flex',alignItems:'center',justifyContent:'center'});}
 copy.querySelectorAll('.reportActions,#reportOutlineControls,.reportDrawLayer,.pdfLayoutHelp').forEach(n=>n.remove());
 copy.removeAttribute('id');copy.querySelectorAll('[id]').forEach(n=>n.removeAttribute('id'));
 document.body.appendChild(copy);
 try{
  if(mapPixels){const host=mapPixels.parentElement,fit=Math.min((host.clientWidth||850)/mapPixels.width,430/mapPixels.height);Object.assign(mapPixels.style,{display:'block',width:(mapPixels.width*fit)+'px',height:(mapPixels.height*fit)+'px',maxWidth:'100%'});}
  return await html2canvas(copy,{...options,windowWidth:1440});
 }finally{copy.remove()}
}

async function downloadVectorDiagramPDF(report){
 if('{{ VECTOR_PDF_QA_FLAG }}'!=='1'){status('Vector Diagram is available only to approved QA accounts.','error');return}
 if(!quoteSnapshot){status('Reopen a saved estimate before vector export.','error');return}
 if(!window.jspdf){status('PDF tools did not load. Reopen this estimate.','error');return}
 const btn=el('downloadPdfBtn'),oldText=btn?.textContent;pdfInProgress=true;if(btn){btn.disabled=true;btn.textContent='CREATING PDF…'}
 try{
  const snapshot=JSON.parse(JSON.stringify(quoteSnapshot));
  const frozenReport=report.cloneNode(true);
  frozenReport.querySelectorAll('svg,canvas,iframe,video,script').forEach(n=>n.remove());
  frozenReport.querySelectorAll('img').forEach(copy=>{
   if(!['rDealerLogo','rWarrantyShield'].includes(copy.id)){copy.remove();return}
   const original=report.querySelector('#'+copy.id);if(copy.style.display==='none'||copy.classList.contains('noDealerLogo')||!copy.getAttribute('src')){copy.remove();return}
   if(!original.complete||!original.naturalWidth)throw Error('Branding image is not ready. Wait and retry the vector download.');
   const canvas=document.createElement('canvas');canvas.width=original.naturalWidth;canvas.height=original.naturalHeight;canvas.getContext('2d').drawImage(original,0,0);copy.src=canvas.toDataURL('image/png');
  });
  const validation=await fetch('/qa-vector-diagram/validate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({quote:snapshot})});
  const checked=await validation.json();if(!validation.ok)throw Error(checked.error||'Sign in and reopen this estimate before vector export.');
  if(!window.AQVectorPDF)await new Promise((resolve,reject)=>{const script=document.createElement('script');script.src='/qa-vector-diagram.js';script.onload=resolve;script.onerror=()=>{script.remove();reject(Error('QA vector tools could not load. Retry the download.'))};document.head.appendChild(script)});
  const result=await window.AQVectorPDF.build(window.jspdf.jsPDF,snapshot,frozenReport);
  result.pdf.save('AeriQuote_Vector_Diagram_QA.pdf');status('Vector Diagram PDF downloaded.','ok');
 }catch(e){status(e.message||'Vector Diagram PDF could not be created.','error')}
 finally{pdfInProgress=false;if(btn){btn.disabled=false;btn.textContent=oldText}}
}
function savedEstimateMoneyIssue(pricing){
 if(!pricing)return '';
 const values=['taxBase','gstAmt','pstAmt','total'].map(key=>pricing[key]);
 if(values.some(value=>value===null||value===undefined||!Number.isFinite(Number(value))))return 'Saved estimate pricing is incomplete. Select EDIT MEASUREMENTS / PRICE, review the quote, then create a corrected estimate. Original saved amounts are unchanged.';
 const cents=value=>Math.round((Number(value)+Number.EPSILON)*100);
 return cents(values[0])+cents(values[1])+cents(values[2])===cents(values[3])?'':'Saved estimate totals do not reconcile. Select EDIT MEASUREMENTS / PRICE, review the quote, then create a corrected estimate. Original saved amounts are unchanged.';
}
async function confirmEstimateExportAccess(){
 const account=el('aqAccountId')?.dataset?.accountId||'';
 if(!account){status('Reopen this estimate from your signed-in business before exporting.','warn');return false}
 const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),10000);
 try{
  const response=await fetch('/api/account/profile',{headers:{'X-AeriQuote-Account':account},cache:'no-store',signal:controller.signal});
  if(response.status===403){try{const denied=await response.clone().json();if(String(denied.code||'').startsWith('subscription_')){status(denied.error,'warn');return false}}catch(e){}}
  if(!response.ok){status(response.status===409?'This estimate belongs to a different signed-in business. Sign in to the original business and reopen it before exporting.':'Your login expired or access changed. Sign in with an active account from this business and reopen the estimate before exporting.','warn');return false}
  const current=await response.json();
  if(String(current.id||'')!==account){status('This estimate belongs to another business. Reopen it from the correct account before exporting.','warn');return false}
  return true;
 }catch(e){status('Could not verify your access. Your estimate is unchanged. Check your connection and retry the export.','warn');return false}
 finally{clearTimeout(timeout)}
}
async function printEstimate(){if(!await confirmEstimateExportAccess())return;if(typeof savedDiagramGeometryError==='function'){const issue=savedDiagramGeometryError(quoteSnapshot);if(issue){status(issue,'warn');return}}if(typeof pricedRoofGeometryError==='function'){const issue=pricedRoofGeometryError(quoteSnapshot);if(issue){status(issue,'warn');return}}if(reportMeasurementCorrection){el('reportOutlineHelpTop').textContent='Save or cancel the measurement correction before printing.';return}window.print()}
async function downloadEstimatePDF(){
 if(!await confirmEstimateExportAccess())return;
 if(typeof savedDiagramGeometryError==='function'){const issue=savedDiagramGeometryError(quoteSnapshot);if(issue){status(issue,'warn');return}}
 if(typeof pricedRoofGeometryError==='function'){const issue=pricedRoofGeometryError(quoteSnapshot);if(issue){status(issue,'warn');return}}
 if(typeof reportMeasurementCorrection!=='undefined'&&reportMeasurementCorrection){el('reportOutlineHelpTop').textContent='Save or cancel the measurement correction before downloading.';return}
 if(quoteSnapshot?.linearPoints?.length||quoteSnapshot?.linearFeet>0){const issue=savedLinearGeometryError(quoteSnapshot.linearPoints,Number(quoteSnapshot.linearFeet));if(issue){status(issue,'warn');return}}
 const moneyIssue=savedEstimateMoneyIssue(quoteSnapshot?.savedPricing);if(moneyIssue){status(moneyIssue,'warn');return}
 if((quoteSnapshot?.structures||[]).some(st=>st.needs_remeasure||st.automatic_review_warning)){status('This estimate contains a roof with unverified coverage. Remeasure it and create a corrected estimate before downloading a PDF.','warn');return}
 const btn=el('downloadPdfBtn'),report=document.querySelector('#reportOverlay .report');
 if(!report){status('Create the customer estimate first.','error');return}
 if(reportOutlineEditMode){if(el('reportOutlineHelpTop'))el('reportOutlineHelpTop').textContent='Save the outline before downloading the PDF.';return}
 if(estimateOpenInProgress){status('Wait for the current estimate aerial to finish loading before downloading.','warn');return}
 if(pdfInProgress)return;
 if(el('estimatePdfLayout')?.value==='vector')return await downloadVectorDiagramPDF(report);
 if(typeof html2canvas==='undefined'||!window.jspdf){status('PDF tools did not load. Check the internet connection, then reopen the estimate.','error');return}
 if(el('pdfLayoutHelp')){el('pdfLayoutHelp').textContent='';el('pdfLayoutHelp').style.display='none'}
 pdfInProgress=true;
 const src=(el('measureSource')&&el('measureSource').value)||'google';
 const oldText=btn?btn.textContent:'';if(btn){btn.disabled=true;btn.textContent='CREATING PDF…'}
 try{
  // IMPORTANT: capture the SAME interactive estimate map the dealer just approved.
  // Do not rebuild the manual aerial and do not refit/recenter the map before capture.
  // The saved outline and the PDF therefore use the exact same Leaflet viewport + geometry.
  const useAerial=(el('streetViewChoice')?.value||'auto')!=='none';
  if(!useAerial)buildSavedRoofOutlineSnapshot();
  else if(!customerMap){if(quoteSnapshot?.savedPricing){if(el('customerMap')?.querySelector('canvas')?.dataset.diagramScope!==savedDiagramFingerprint(quoteSnapshot))await buildSavedHistoricalSnapshot()}else{await buildCustomerMap();await new Promise(r=>setTimeout(r,220))}}
  else if(customerMap){await new Promise(r=>setTimeout(r,160))}
  const actions=report.querySelector('.reportActions'),outlineControls=el('reportOutlineControls');
  const oldActionsDisplay=actions?actions.style.display:'',oldOutlineDisplay=outlineControls?outlineControls.style.display:'';
  if(actions)actions.style.display='none';if(outlineControls)outlineControls.style.display='none';
  // Leaflet SVG paths can be offset by html2canvas when map panes have CSS
  // transforms. Draw the approved geometry in the map's own pixel coordinate
  // system onto a temporary canvas, then capture that canvas in the PDF.
  let pdfTraceCanvas=null;
  // Detach every vector SVG during capture. Keeping the original transformed SVG
  // alongside the pixel canvas can produce a second, displaced outline in html2canvas.
  // Satellite images and labels remain in the map; restore SVGs even if capture fails.
  const pdfVectors=[],pdfLabels=[];
  try{
    const snap=activeSavedDiagramSnapshot(quoteSnapshot||captureQuoteSnapshot());
    // Capture all commercial area polygons and the linear trace together.
    // The old PDF path chose just one outline based on the selected tool.
    const traces=[];
    const commercialPolys=Array.isArray(snap.commercialAreas)?snap.commercialAreas.filter(a=>Array.isArray(a.points)&&a.points.length>=3):[];
    if(commercialPolys.length){
      commercialPolys.forEach(a=>traces.push({points:a.points,area:true}));
    }else if(Array.isArray(snap.areaPoints)&&snap.areaPoints.length>=3){
      traces.push({points:reportOutlines['area-visual']||snap.areaPoints,area:true});
    }
    if(Array.isArray(snap.linearPoints)&&snap.linearPoints.length>=2){
      traces.push({points:reportOutlines['linear-visual']||snap.linearPoints,area:false});
    }
    // Roofing: export the exact polygons already approved on the report map.
    // Reuse their LatLngs and style, rather than capturing transformed Leaflet SVG.
    if(customerMap&&!traces.length){customerOverlays.forEach(layer=>{
      if(!(layer instanceof L.Polygon))return;
      const rings=layer.getLatLngs(),ring=Array.isArray(rings[0])?rings[0]:rings;
      if(ring.length>=3)traces.push({points:ring.map(p=>[p.lat,p.lng]),area:true,color:layer.options.color||'#2d6cdf',fillOpacity:layer.options.fillOpacity??.045});
    })}
    if(customerMap&&traces.length){
      const host=el('customerMap'),size=customerMap.getSize();
      pdfTraceCanvas=document.createElement('canvas');
      pdfTraceCanvas.width=Math.round(size.x*2);pdfTraceCanvas.height=Math.round(size.y*2);
      Object.assign(pdfTraceCanvas.style,{position:'absolute',left:'0',top:'0',width:size.x+'px',height:size.y+'px',zIndex:'450',pointerEvents:'none'});
      const ctx=pdfTraceCanvas.getContext('2d');ctx.scale(2,2);
      traces.forEach(trace=>{
        ctx.beginPath();
        trace.points.forEach((p,i)=>{
          const pt=customerMap.latLngToContainerPoint(L.latLng(p[0],p[1]));
          if(i===0)ctx.moveTo(pt.x,pt.y);else ctx.lineTo(pt.x,pt.y);
        });
        if(trace.area){ctx.closePath();ctx.fillStyle=trace.color||'rgba(115,87,184,0.14)';if(trace.color)ctx.globalAlpha=trace.fillOpacity;ctx.fill();ctx.globalAlpha=1;}
        ctx.strokeStyle=trace.color||(trace.area?'#7357b8':'#0f8f83');
        ctx.lineWidth=5;ctx.lineJoin='round';ctx.lineCap='round';ctx.stroke();
      });
      pdfLabels.push(...paintCustomerPdfLabels(ctx,host));
      host.appendChild(pdfTraceCanvas);
      customerMap.getPane('overlayPane')?.querySelectorAll('svg').forEach(svg=>{const anchor=document.createComment('PDF vector replacement');svg.replaceWith(anchor);pdfVectors.push({svg,anchor})});
    }
    var expandedPdf=el('estimatePdfLayout')?.value==='expanded'?await buildExpandedEstimatePDF(report):null;
    var canvas=expandedPdf?null:await captureSinglePageEstimate(report);
  }finally{
    if(pdfTraceCanvas)pdfTraceCanvas.remove();
    pdfLabels.forEach(({node,visibility})=>node.style.visibility=visibility);
    pdfVectors.forEach(({svg,anchor})=>anchor.replaceWith(svg));
    if(actions)actions.style.display=oldActionsDisplay;if(outlineControls)outlineControls.style.display=oldOutlineDisplay;
  }

  const {jsPDF}=window.jspdf;const pdf=expandedPdf||new jsPDF({orientation:'landscape',unit:'in',format:'letter',compress:true});
  if(!expandedPdf){
  const pageW=11,pageH=8.5,margin=.18,maxW=pageW-margin*2,maxH=pageH-margin*2;
  const ratio=Math.min(maxW/canvas.width,maxH/canvas.height);const w=canvas.width*ratio,h=canvas.height*ratio;
  pdf.addImage(canvas.toDataURL('image/jpeg',0.92),'JPEG',(pageW-w)/2,(pageH-h)/2,w,h,undefined,'FAST');
  }
  const raw=(el('address')?.value||'Customer').split(',')[0].trim()||'Customer';const safe=raw.replace(/[^a-z0-9]+/gi,'_').replace(/^_+|_+$/g,'');
  pdf.save(`AeriQuote_Estimate_${safe||'Customer'}.pdf`);status('Estimate PDF downloaded.','ok');
 }catch(e){if(e.code==='SINGLE_PAGE_DENSE'){if(el('estimatePdfLayout'))el('estimatePdfLayout').value='expanded';const help=el('pdfLayoutHelp');if(help){help.textContent=e.message;help.style.display='block';help.scrollIntoView({block:'nearest'})}status(e.message,'warn')}else{console.error('AQ:pdf-generation-failed');status('PDF could not be created. Use PRINT ESTIMATE while this is corrected.','error')}}
 finally{
   pdfInProgress=false;if(btn){btn.disabled=!!reportOutlineEditMode;btn.textContent=oldText||'DOWNLOAD ESTIMATE PDF'}
 }
}
function openEstimateRoofEditor(){
 if(!manualRoofQa()||measurementViewMode!=='auto'||!manualPlanes.length)return;
 el('estimateRoofSectionPicker')?.remove();
 if(manualPlanes.length===1){editManualRoofSection(0);el('map')?.scrollIntoView({block:'center'});return}
 const picker=document.createElement('section');picker.id='estimateRoofSectionPicker';picker.className='stepcard';picker.setAttribute('aria-label','Choose roof section to edit');
 const title=document.createElement('h2');title.textContent='Choose the roof section to edit';picker.append(title);
 const help=document.createElement('p');help.textContent='Select one section below. Its corners open for editing immediately; saved pitches stay unchanged.';picker.append(help);
 manualPlanes.forEach((p,i)=>{const b=document.createElement('button');b.type='button';b.className='secondary';b.style.cssText='display:block;width:100%;margin:8px 0;text-align:left';b.textContent='EDIT ROOF SECTION '+(i+1)+' — '+fmt(p.surface_sqft)+' ft² · '+manualRoofPitchLabel(p.pitch_degrees)+' pitch';b.onclick=()=>{editManualRoofSection(i);el('map')?.scrollIntoView({block:'center'})};picker.append(b)});
 const cancel=document.createElement('button');cancel.type='button';cancel.className='ghost';cancel.textContent='CANCEL SECTION SELECTION';cancel.onclick=()=>picker.remove();picker.append(cancel);
 el('map').before(picker);picker.scrollIntoView({block:'center'});
}
async function confirmQaSubscriptionEditAccess(){
 if(!document.querySelector('meta[name="aq-subscription-qa"]'))return true;
 try{
  const r=await fetch('/qa/subscription-policy',{cache:'no-store'}),d=await r.json();
  if(!r.ok)throw Error(d.error||'Could not check account access.');
  if(['retained_read_only','expired'].includes(d.state)){
   status(d.message||'Saved estimate access is restricted. Your work is still here.','warn');
   if(el('reportOutlineHelpTop'))el('reportOutlineHelpTop').textContent=d.message||'Your work is still here.';
   return false;
  }
  return true;
 }catch(e){status('Could not confirm current access. Keep this page open; your work is still here.','warn');return false}
}
let reportCloseInProgress=false;
async function closeReport(e){
 if(reportMeasurementCorrection||reportCloseInProgress)return;
 const b=el('backToDealerBtn');
 if(!e||!b||e.currentTarget!==b)return;
 if(!await confirmQaSubscriptionEditAccess())return;
 reportCloseInProgress=true;const label=b.textContent;b.disabled=true;b.textContent='OPENING EDITOR…';
 try{
  if(savedEstimateEditContext)await resumeSavedEstimateWorkspace();
  document.body.classList.remove('report-open');el('reportOverlay').style.display='none';
  if(customerMap){try{customerMap.remove()}catch(err){}customerMap=null}
  customerRgbLayer=null;customerOverlays=[];
  openEstimateRoofEditor();
 }catch(err){const message=err.message||'Could not restore saved job for editing.';status(message,'error');if(el('reportOutlineHelpTop'))el('reportOutlineHelpTop').textContent=message+' Please try Edit Measurements / Price again.';}
 finally{reportCloseInProgress=false;b.disabled=false;b.textContent=label}
}
function saveAssessment(){if(!structures.length&&!manualPlanes.length){status('Measure a property first.','error');return}let rec={date:new Date().toISOString(),address:el('address').value,structures:structures.map(s=>({label:s.label,area:s.total_roof_sqft,segments:s.segment_count,pitch:s.segments.length?s.segments.reduce((a,x)=>a+x.pitch_degrees,0)/s.segments.length:0,date:s.imagery_date,quality:s.imagery_quality})),manualArea:manualTotal(),measurementSource:el('measureSource')?el('measureSource').value:'google',pricing:priceCalc(),streetDate:el('streetMeta').textContent};let h=[];try{h=JSON.parse(localStorage.getItem('sgSavedAssessments')||'[]')}catch(e){}h.unshift(rec);localStorage.setItem('sgSavedAssessments',JSON.stringify(h.slice(0,50)));usage.saved++;updateUsage();status('Assessment saved in this browser for the demo. Production CRM will save it to the customer record.','ok')}

function clearLoadedPropertyForNewAddress(){
 const hadLoaded=!!sessionToken||structures.length||manualPlanes.length||fallbackMode;
 if(!hadLoaded){if(el('postalCode'))el('postalCode').value='';if(el('address'))el('address').value='';if(el('googleMatch'))el('googleMatch').textContent='';if(el('propertyVerify')){el('propertyVerify').style.display='none';el('propertyVerify').textContent=''}return;}
 // New property means a new customer. Do not carry customer details from a previous/saved estimate.
 ['customerName','customerPhone','customerEmail','customerNotes'].forEach(id=>{const n=el(id);if(n)n.value=''});
 sessionToken=null;resetMeasurementForNewProperty();locateRoofMode=false;fallbackMode=false;fallbackBounds=null;showSolarFallback(false);
 removeStaleAerialLayers();
 if(clickMarker){try{map.removeLayer(clickMarker)}catch(e){}clickMarker=null}
 const city=el('cityTown'),prov=el('propertyProvince'),postal=el('postalCode'),hidden=el('address');
 if(city)city.value='';if(prov)prov.value='';if(postal)postal.value='';if(hidden)hidden.value='';
 if(el('googleMatch'))el('googleMatch').textContent='';
 if(el('street')){el('street').removeAttribute('src');el('street').style.visibility='hidden'}
 if(el('streetMeta'))el('streetMeta').textContent='';
 if(el('garageGuide'))el('garageGuide').textContent='Load the property first. Review the automatic outline if available, or trace the roof manually.';if(el('garageSavedConfirm')){el('garageSavedConfirm').style.display='none';el('garageSavedConfirm').innerHTML='';}
 if(el('measureClicked'))el('measureClicked').disabled=true;if(el('measureClickedTop'))el('measureClickedTop').disabled=true;
 setManualUi(false);renderSummary();status('New property — finish the address, then click LOAD & MEASURE ROOF.','ok');
}
function startNewProperty(){if(reportMeasurementCorrection){el('reportOutlineHelpTop').textContent='Save or cancel the measurement correction before starting another property.';return}
 resetReportForNewProperty();
 clearLoadedPropertyForNewAddress();
 skipAddressConflictOnce=false;
 clicked=null;lastLoadedStreet='';
 const street=el('streetAddress');if(street)street.value='';
 const city=el('cityTown');if(city)city.value='';
 const prov=el('propertyProvince');if(prov)prov.value='';
 const postal=el('postalCode');if(postal)postal.value='';
 const hidden=el('address');if(hidden)hidden.value='';
 if(el('googleMatch'))el('googleMatch').textContent='';
 if(el('propertyVerify')){el('propertyVerify').style.display='none';el('propertyVerify').textContent=''}
 if(el('addressAutoStatus'))el('addressAutoStatus').textContent='City, state/province and ZIP/postal code will fill automatically when Google finds the address.';
 const defaultPrice=parseFloat(el('price')?.value||0);if(el('jobPrice')){if(String(el('price')?.value??'').trim()==='')el('jobPrice').value='';else if(Number.isFinite(defaultPrice)&&defaultPrice>=0)el('jobPrice').value=defaultPrice.toFixed(2);}
 renderSummary();
 status('Ready for the next property. Enter the new address and click LOAD & MEASURE ROOF.','ok');
 window.scrollTo({top:0,behavior:'smooth'});
 setTimeout(()=>{if(street)street.focus()},250);
}
function unitAddressSuggestion(street,province){const m=String(street||'').trim().match(/^(\d+[A-Za-z]?)\s+(\d{3,}[A-Za-z]?)\s+([A-Za-z].*)$/);return m&&Number(m[1])<Number(m[2])&&CANADIAN_PROVINCES.has(String(province||'').toUpperCase())?{unit:m[1],number:m[2],address:m[2]+' '+m[3]+' #'+m[1]}:null}
function enteredStreetNumber(){const v=(el('streetAddress')?.value||'').trim();const m=v.match(/^\s*(\d+[A-Za-z]?)(?:\s|,|$)/);return m?m[1]:''}
function applyAddressParts(parts){if(!parts)return;if(parts.city&&el('cityTown'))el('cityTown').value=parts.city;if(parts.province&&el('propertyProvince')){setPropertyRegion(parts.province);syncPropertyProvince()}if(parts.postal&&el('postalCode'))el('postalCode').value=parts.postal}
function clearAddressVerificationState(message='Address changed — enter/confirm city and state, then Google will verify it.'){
 addressPreviewSeq++;
 if(el('postalCode'))el('postalCode').value='';
 if(!sessionToken&&el('address'))el('address').value='';
 if(el('googleMatch'))el('googleMatch').textContent='';
 if(el('propertyVerify')){el('propertyVerify').style.display='none';el('propertyVerify').textContent='';}
 if(el('addressAutoStatus')){el('addressAutoStatus').textContent=message;el('addressAutoStatus').style.color='#666';}
}
const CANADIAN_PROVINCES=new Set(['AB','BC','MB','NB','NL','NS','NT','NU','ON','PE','QC','SK','YT']);
// Property location is independent of business tax defaults and saved quotes.
function filterPropertyRegions(country,selected=''){
 const region=el('propertyProvince'),field=el('propertyCountry');if(!region||!field)return;
 const memory=region._countryRegions||(region._countryRegions={});if(region.dataset.country)memory[region.dataset.country]=region.value;
 field.value=country==='US'?'US':'CA';
 region.innerHTML='<option value="">Choose '+(field.value==='CA'?'province / territory':'state')+'</option>'+(field.value==='CA'?AERIQUOTE_CA_PROVINCES:AERIQUOTE_US_STATES);
 region.value=[...region.options].some(o=>o.value===selected)?selected:'';region.dataset.country=field.value;
}
function setPropertyRegion(value){
 const code=String(value||'').trim().toUpperCase();
 filterPropertyRegions(code?(CANADIAN_PROVINCES.has(code)?'CA':'US'):(el('propertyCountry')?.value||'CA'),code);
}
function initializePropertyRegions(){
 const region=el('propertyProvince'),field=el('propertyCountry');if(!region||!field)return;
 if(region.value){setPropertyRegion(region.value);return}
 if(!field.dataset.chosen&&!sessionToken&&!(el('streetAddress')?.value||'').trim())filterPropertyRegions(el('dealerCountry')?.value||'CA');
 else if(!region.dataset.country)filterPropertyRegions(field.value);
}
function propertyCountryChanged(){
 const field=el('propertyCountry'),region=el('propertyProvince');if(!field||!region)return;
 field.dataset.chosen='1';filterPropertyRegions(field.value,region._countryRegions?.[field.value]||'');
 // The old accepted address, measurements, customer and taxes remain untouched.
 clearTimeout(addressPreviewTimer);addressPreviewSeq++;renderSummary();
}
function propertyCountryFromProvince(prov){return CANADIAN_PROVINCES.has(String(prov||'').toUpperCase())?'Canada':'USA'}
function propertyLookupProvince(){
 const selected=(el('propertyProvince')?.value||'').trim();
 if(selected)return selected; // PROPERTY province is authoritative. Dealer profile province is never used for locating a property.
 const detected=detectProvince(el('streetAddress')?.value||'')||'',country=el('propertyCountry')?.value;
 return detected&&country&&((CANADIAN_PROVINCES.has(detected)?'CA':'US')!==country)?'':detected;
}
async function previewAddress(){
 const seq=addressPreviewSeq;
 const key="{{GOOGLE_MAPS_API_KEY}}",street=(el('streetAddress')?.value||'').trim();if(!key||!street||street.length<4)return;
 const city=(el('cityTown')?.value||'').trim(),prov=propertyLookupProvince();
 if(!city||!prov){if(el('addressAutoStatus')){el('addressAutoStatus').textContent='Enter the City and State/Province. ZIP/postal code is not required.';el('addressAutoStatus').style.color='#666'}return}
 const unitGuess=unitAddressSuggestion(street,prov);if(unitGuess){if(el('addressAutoStatus')){el('addressAutoStatus').textContent='Unit address? Use '+unitGuess.address+', or select Load Property to confirm.';el('addressAutoStatus').style.color='#9a6700'}return}
 const q=[street,city,prov,propertyCountryFromProvince(prov)].join(', ');
 try{if(el('addressAutoStatus')){el('addressAutoStatus').textContent='Checking '+city+', '+prov+'…';el('addressAutoStatus').style.color='#666'}
  const r=await fetch('/address-preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key,address:q,expected_city:city,expected_province:prov,expected_street_number:enteredStreetNumber()})});const d=await r.json();if(seq!==addressPreviewSeq)return;
  if(r.status===409){if(el('addressAutoStatus')){el('addressAutoStatus').textContent='⚠ ADDRESS DOESN\'T MATCH — '+(d.user_error||'Google found a different address.');el('addressAutoStatus').style.color='#9a1f16'}return}
  if(!r.ok||!d.formatted_address){if(el('addressAutoStatus')){el('addressAutoStatus').textContent='Google could not verify this exact street, city and state/province yet.';el('addressAutoStatus').style.color='#9a6700'}return}
  // Preview is DISPLAY ONLY. It must never overwrite city, province or ZIP code.
  if(el('addressAutoStatus')){el('addressAutoStatus').textContent='Google found: '+d.formatted_address;el('addressAutoStatus').style.color='#176b43'}
 }catch(e){if(el('addressAutoStatus')){el('addressAutoStatus').textContent='Google could not verify this address yet.';el('addressAutoStatus').style.color='#9a6700'}}
}
function propertyInputAddressKey(){
 const coords=coordinatesEntered();
 return JSON.stringify(coords?[coords.lat,coords.lng]:['streetAddress','cityTown','propertyProvince'].map(id=>(el(id)?.value||'').trim().toLowerCase()));
}
function propertyAddressNeedsReload(){return !!sessionToken&&!!loadProperty.loadedAddressKey&&loadProperty.loadedAddressKey!==propertyInputAddressKey()}
function addressFieldChanged(){
 clearAddressVerificationState();
 clearTimeout(addressPreviewTimer);addressPreviewTimer=setTimeout(previewAddress,650);
 renderSummary();
}
function addressTyped(){
 // Keep the old workspace until a new property is accepted; require explicit city/province.
 const hadLoaded=!!sessionToken||structures.length||manualPlanes.length||fallbackMode;
 if(hadLoaded){
  if(el('cityTown'))el('cityTown').value='';
  if(el('propertyProvince'))el('propertyProvince').value='';
  if(el('postalCode'))el('postalCode').value='';
 }
 addressFieldChanged();
}
function propertyProvinceChanged(){syncPropertyProvince();addressFieldChanged()}
window.addEventListener('DOMContentLoaded',()=>{initializePropertyRegions();loadDealerDefaults();updateUsage();const jp=el('jobPrice');if(jp){jp.addEventListener('input',jobPriceChanged);jp.addEventListener('change',jobPriceChanged);jp.addEventListener('keyup',jobPriceChanged);}const street=el('streetAddress'),city=el('cityTown');if(street)street.addEventListener('input',addressTyped);if(city)city.addEventListener('input',addressFieldChanged);renderSummary()});
function buildPropertyAddress(){
 const street=(el('streetAddress')?.value||'').trim(),city=(el('cityTown')?.value||'').trim(),prov=propertyLookupProvince();
 // Postal code is intentionally NEVER included in a property lookup. Google supplies it only after verification.
 const a=[street,city,prov,propertyCountryFromProvince(prov)].filter(Boolean).join(', ');
 if(el('address'))el('address').value=a;return a
}
function jobPriceChanged(){const jp=el('jobPrice');if(!jp)return;const v=parseFloat(jp.value);if(!Number.isFinite(v)||v<0){renderSummary();return}if(measurementViewMode==='linear')savedLinearJobRate=v;if(['landscaping','paving','pressure','snow'].includes(currentBusinessType())&&measurementViewMode==='area'){const rateId={landscaping:'landscapingAreaRate',paving:'pavingAreaRate',pressure:'pressureAreaRate'}[currentBusinessType()];if(rateId&&el(rateId))el(rateId).value=String(v);if(commercialAreas[commercialEditingIndex])commercialAreas[commercialEditingIndex].rate=v;}renderSummary();if(el('reportOverlay')&&el('reportOverlay').style.display==='block')showCustomerEstimate()}
function syncJobPrice(){jobPriceChanged()}
function setJobPrice(v){const n=parseFloat(v);if(!Number.isFinite(n)||n<0)return;if(el('jobPrice'))el('jobPrice').value=n.toFixed(2);jobPriceChanged()}
function syncProvinceTax(){renderSummary()}

let reportOpenedAt=0;
let manualCorrectionMode='add';
function setManualMode(mode){
 manualCorrectionMode=mode;
 const n=el('manualModeNote');
 if(n)n.textContent=mode==='exclude'
  ? 'EXCLUDE mode: trace the non-shingle section (for example a solarium). The traced area will be recorded as excluded from treatment.'
  : 'ADD mode: trace only the missing shingled roof. The Google roof already in the quote will stay there.';
}
function startExistingManualTrace(){
 const candidates=[...document.querySelectorAll('button')];
 const b=candidates.find(x=>/Start Manual Trace/i.test(x.textContent||''));
 if(b)b.click(); else alert('Open the manual measurement section and start a manual trace.');
}
function coordinatesEntered(){
 const raw=(el('streetAddress')?.value||'').trim();
 try{const u=new URL(raw);return parseDealerCoordinates(u.searchParams.get('coordinate')||'')}catch(e){}
 return parseDealerCoordinates(raw);
}


function syncPropertyProvince(){if(el('propertyProvince')?.value)setPropertyRegion(el('propertyProvince').value);renderSummary();}
const _aeriRenderSummary=renderSummary;renderSummary=function(){const r=_aeriRenderSummary.apply(this,arguments);setTimeout(()=>applyBusinessTerminology(),0);return r};
</script>
<script src="/static/workspace_drafts.js"></script>
</body></html>"""

def req_json(url):
    req=urllib.request.Request(url,headers={"User-Agent":"ShingleGuardRoofAssessment/2.0"})
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            return r.status,json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try: body=json.loads(e.read().decode())
        except: body={"error":{"message":str(e)}}
        return e.code,body

def req_bytes(url,timeout=12,retries=1):
    # Keep imagery failures fast. One short retry is enough; the RGB route has a
    # second, lighter Google Solar request as a fallback instead of waiting 60–90s.
    last=None
    for attempt in range(retries+1):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"ShingleGuardRoofAssessment/2.0"})
            with urllib.request.urlopen(req,timeout=timeout) as r:
                return r.headers.get("Content-Type","application/octet-stream"),r.read()
        except Exception as e:
            last=e
            if attempt<retries: time.sleep(0.25)
    raise last

def date_text(d):
    d=d or {};vals=[d.get("year"),d.get("month"),d.get("day")]
    return "-".join(str(x) for x in vals if x is not None)

class SolarBuildingNotFound(Exception):
    pass

def building(key,lat,lng):
    q=urllib.parse.urlencode({"location.latitude":lat,"location.longitude":lng,"requiredQuality":"BASE","key":key})
    status,data=req_json("https://solar.googleapis.com/v1/buildingInsights:findClosest?"+q)
    if status==404:raise SolarBuildingNotFound((data.get("error") or {}).get("message") or "Building not found")
    if status!=200:raise ValueError((data.get("error") or {}).get("message") or f"Solar API error {status}")
    sp=data.get("solarPotential") or {};whole=sp.get("wholeRoofStats") or {};segs=[]
    for seg in sp.get("roofSegmentStats") or []:
        stats=seg.get("stats") or {};box=seg.get("boundingBox") or {}
        segs.append({
            "area_sqft":float(stats.get("areaMeters2") or 0)*10.76391041671,
            "pitch_degrees":float(seg.get("pitchDegrees") or 0),
            "azimuth_degrees":float(seg.get("azimuthDegrees") or 0),
            "center":seg.get("center"),"bounding_box":{"sw":box.get("sw"),"ne":box.get("ne")}
        })
    c=data.get("center") or {"latitude":lat,"longitude":lng}
    return {"building_id":data.get("name"),"bounding_box":data.get("boundingBox"),"latitude":float(c.get("latitude",lat)),"longitude":float(c.get("longitude",lng)),
            "total_roof_sqft":float(whole.get("areaMeters2") or 0)*10.76391041671,
            "roof_coverage_ratio":(float(whole.get("groundAreaMeters2") or 0)/float((sp.get("buildingStats") or {}).get("groundAreaMeters2") or 1)) if whole.get("groundAreaMeters2") and (sp.get("buildingStats") or {}).get("groundAreaMeters2") else None,
            "roof_ground_sqft":float(whole.get("groundAreaMeters2") or 0)*10.76391041671,
            "building_ground_sqft":float((sp.get("buildingStats") or {}).get("groundAreaMeters2") or 0)*10.76391041671,
            "segment_count":len(segs),"segments":segs,"imagery_quality":data.get("imageryQuality"),
            "imagery_date":date_text(data.get("imageryDate"))}

def bearing(lat1,lon1,lat2,lon2):
    p1,p2=math.radians(lat1),math.radians(lat2);dl=math.radians(lon2-lon1)
    y=math.sin(dl)*math.cos(p2);x=math.cos(p1)*math.sin(p2)-math.sin(p1)*math.cos(p2)*math.cos(dl)
    return (math.degrees(math.atan2(y,x))+360)%360


LOGIN_HTML = r"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta id="aqAccountId" data-account-id="{{ACCOUNT_ID}}"><title>AeriQuote Login</title><style>body{font-family:Arial;background:#f1f5f9;color:#17212b}.box{max-width:430px;margin:8vh auto;background:white;padding:30px;border-radius:18px;box-shadow:0 10px 35px #0002}h1{color:#102a43}label{font-weight:800;display:block;margin:12px 0 5px}input{width:100%;box-sizing:border-box;padding:12px;border:1px solid #cbd5ce;border-radius:9px}button{width:100%;margin-top:18px;padding:13px;border:0;border-radius:9px;background:#1677c8;color:white;font-weight:900}.err{background:#fff0f0;color:#a11;padding:10px;border-radius:8px}</style><link rel="icon" type="image/svg+xml" href="/site/assets/favicon.svg"><link rel="stylesheet" href="/site/account-ui.css?v=20261015"></head><body class="aq-account-page"><div class="box"><a href="/site/" aria-label="AeriQuote home"><img src="/static/aeriquote-logo.png" alt="AeriQuote" style="display:block;width:100%;max-width:360px;height:auto;margin:0 auto 16px"></a><h1>Log in to AeriQuote</h1>{% if error %}<div class="err" role="alert">{{error}}</div>{% endif %}<form method="post"><label for="loginEmail">Email</label><input id="loginEmail" autocomplete="username" name="email" type="email" required><label for="loginPassword">Password</label><input id="loginPassword" autocomplete="current-password" name="password" type="password" required><button>LOG IN</button></form><p><a href="/forgot-password">Forgot password?</a></p></div><footer class="aq-account-footer"><a href="/site/contact-support">Contact &amp; Support</a><a href="/site/privacy-policy">Privacy</a><a href="/site/terms-of-use">Terms</a></footer></body></html>"""

@app.route("/dealer-login",methods=["GET","POST"])
def dealer_login():
    if request.method=="POST":
        email=str(request.form.get("email") or "").strip().lower(); password=str(request.form.get("password") or "")
        # Opt-in recovery-only diagnostics: fixed decisions and random request ID,
        # never credentials, identity values, hashes, request bodies or cookies.
        diagnostic_email=os.environ.get('AERIQUOTE_LOGIN_DIAGNOSTIC_EMAIL','').strip().lower()
        diagnostic_id=uuid.uuid4().hex if (is_recovery_test_service() and diagnostic_email and email==diagnostic_email) else None
        def diagnostic(stage):
            if diagnostic_id:app.logger.warning('AQ login diagnostic stage=%s id=%s',stage,diagnostic_id)
        def login_response(response,stage):
            diagnostic(stage)
            response=app.make_response(response)
            if diagnostic_id:response.headers['X-AeriQuote-Login-Diagnostic']=diagnostic_id
            return response
        diagnostic('received')
        con=estimate_db()
        try:
            ip_blocked=limited(con,"login-ip:"+str(request.remote_addr),100)
            email_blocked=limited(con,"login-email:"+email,20)
            if ip_blocked or email_blocked:return login_response((render_template_string(LOGIN_HTML,error="Too many login attempts. Please try again in 15 minutes."),429),'rate_limited')
            # Read credentials and their revocation version in one DB snapshot.
            row=con.execute("SELECT d.*,COALESCE(v.version,0) AS login_version FROM dealers d LEFT JOIN account_auth_versions v ON v.account_type='owner' AND v.account_id=d.id WHERE LOWER(d.email)=?",(email,)).fetchone()
        finally: con.close()
        diagnostic('owner_found' if row else 'owner_missing')
        owner_active=bool(row and str(row['status']).lower()=='active')
        if row and not owner_active:diagnostic('owner_inactive')
        owner_verified=owner_active and password_ok(password,row['password_hash'])
        if owner_active:diagnostic('owner_verifier_pass' if owner_verified else 'owner_verifier_fail')
        if owner_verified:
            session.clear();session["dealer_id"]=row["id"];session["dealer_name"]=row["dealer_name"];session["account_type"]="owner";session["auth_version"]=int(row["login_version"] or 0)
            return login_response(redirect('/'),'session_created')
        con=estimate_db()
        try:
            emp=con.execute("SELECT e.*,d.dealer_name,d.status AS dealer_status,COALESCE(v.version,0) AS login_version FROM dealer_employees e JOIN dealers d ON d.id=e.dealer_id LEFT JOIN account_auth_versions v ON v.account_type='employee' AND v.account_id=e.id WHERE LOWER(e.email)=?",(email,)).fetchone()
        finally: con.close()
        diagnostic('employee_found' if emp else 'employee_missing')
        employee_active=bool(emp and str(emp['status']).lower()=='active' and str(emp['dealer_status']).lower()=='active')
        if emp and not employee_active:diagnostic('employee_inactive')
        employee_verified=employee_active and password_ok(password,emp['password_hash'])
        if employee_active:diagnostic('employee_verifier_pass' if employee_verified else 'employee_verifier_fail')
        if employee_verified:
            session.clear();session["dealer_id"]=emp["dealer_id"];session["dealer_name"]=emp["dealer_name"];session["employee_id"]=emp["id"];session["employee_name"]=emp["employee_name"];session["account_type"]="employee";session["auth_version"]=int(emp["login_version"] or 0)
            return login_response(redirect('/'),'session_created')
        return login_response(render_template_string(LOGIN_HTML,error="Email or password is incorrect."),'rejected')
    return render_template_string(LOGIN_HTML,error=None)

@app.get("/dealer-logout")
def dealer_logout():
    session.clear();return redirect("/dealer-login")

SETUP_DEALER_HTML=r"""<!doctype html><html><head><meta charset="utf-8"><title>Create AeriQuote Dealer</title>
<style>body{font-family:Arial;background:#f1f5f9;color:#17212b}.box{max-width:480px;margin:6vh auto;background:#fff;padding:30px;border-radius:18px;box-shadow:0 10px 35px #0002}h1{color:#102a43}label{font-weight:800;display:block;margin:12px 0 5px}input{width:100%;box-sizing:border-box;padding:12px;border:1px solid #cbd5ce;border-radius:9px;font-size:16px}button{width:100%;margin-top:18px;padding:13px;border:0;border-radius:9px;background:#1677c8;color:#fff;font-weight:900;font-size:16px}.msg{padding:11px;border-radius:8px;background:#eef8ee}.err{padding:11px;border-radius:8px;background:#fff0f0;color:#a11}</style></head>
<body><div class="box"><h1>Create Dealer Account</h1><p>AeriQuote Head Office setup</p>
{% if message %}<div class="msg">{{message}}</div>{% endif %}{% if error %}<div class="err" role="alert">{{error}}</div>{% endif %}
<form method="post">
<label>Admin Setup Key</label><input name="setup_key" type="password" required>
<label>Dealer Name</label><input name="dealer_name" value="AeriQuote Head Office" required>
<label>Email</label><input name="email" type="email" value="sdusome@diitalk.com" required>
<label>State</label><input name="state" value="Florida">
<label>Password</label><input name="password" type="password" minlength="8" required>
<button type="submit">CREATE DEALER ACCOUNT</button></form></div></body></html>"""

def login_email_in_use(con,email):
    # Share the employee-creation identity lock until the caller commits/closes.
    if con.postgres:con.execute("SELECT pg_advisory_xact_lock(?)",(614728194,))
    else:con.execute("BEGIN IMMEDIATE")
    return bool(con.execute("SELECT id FROM dealers WHERE LOWER(email)=? UNION ALL SELECT id FROM dealer_employees WHERE LOWER(email)=?",(email,email)).fetchone())

@app.route("/setup-dealer",methods=["GET","POST"],strict_slashes=False)
def setup_dealer():
    if request.method=="POST":
        expected=os.environ.get("ADMIN_SETUP_KEY","")
        supplied=str(request.form.get("setup_key") or "")
        if not expected or not hmac.compare_digest(supplied,expected):
            return render_template_string(SETUP_DEALER_HTML,error="Admin Setup Key is incorrect.",message=None),403
        name=str(request.form.get("dealer_name") or "").strip()
        email=str(request.form.get("email") or "").strip().lower()
        state=str(request.form.get("state") or "").strip()
        password=str(request.form.get("password") or "")
        if not name or not email or len(password)<8:
            return render_template_string(SETUP_DEALER_HTML,error="Name, email and a password of at least 8 characters are required.",message=None),400
        con=estimate_db()
        try:
            existing=login_email_in_use(con,email)
            if existing:
                return render_template_string(SETUP_DEALER_HTML,error="A dealer account with that email already exists.",message=None),400
            did=str(uuid.uuid4()); created=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())
            con.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,state,status,lookup_limit,estimate_limit,created_at) VALUES(?,?,?,?,?,'active',250,150,?)",(did,name,email,password_hash(password),state,created))
            # Claim legacy estimates created before dealer accounts existed.
            try:
                con.execute("UPDATE estimates SET dealer_id=? WHERE dealer_id IS NULL OR dealer_id=''",(did,))
                con.execute("UPDATE estimate_revisions SET dealer_id=? WHERE dealer_id IS NULL OR dealer_id=''",(did,))
            except Exception:
                pass
            con.commit()
        finally: con.close()
        return render_template_string(SETUP_DEALER_HTML,error=None,message="Dealer account created. You can now return to the Dealer Login.")
    return render_template_string(SETUP_DEALER_HTML,error=None,message=None)

@app.post("/api/admin/create-dealer")
def create_dealer():
    expected=os.environ.get("ADMIN_SETUP_KEY",""); supplied=request.headers.get("X-Admin-Setup-Key","")
    if not expected or not hmac.compare_digest(supplied,expected):return jsonify(error="Unauthorized"),403
    d=request.get_json(silent=True) or {}; name=str(d.get("dealer_name") or "").strip(); email=str(d.get("email") or "").strip().lower(); password=str(d.get("password") or "")
    if not name or not email or len(password)<8:return jsonify(error="Dealer name, email and password (8+ characters) required"),400
    did=str(uuid.uuid4()); created=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()); con=estimate_db()
    try:
        if login_email_in_use(con,email):return jsonify(error="An AeriQuote login already exists with that email."),409
        con.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,state,status,lookup_limit,estimate_limit,created_at) VALUES(?,?,?,?,?,'active',250,150,?)",(did,name,email,password_hash(password),str(d.get("state") or ""),created));con.commit()
    except Exception:return jsonify(error="Could not create dealer"),400
    finally:con.close()
    return jsonify(id=did,dealer_name=name,email=email,status="active",lookup_limit=250,estimate_limit=150)


PLAN_LIMITS={"trial":3,"basic":25,"pro":75,"business":200,"legacy":250}

def _account_profile(dealer_id):
    con=estimate_db()
    try:
        d=con.execute("SELECT id,dealer_name,email,state,status,lookup_limit,estimate_limit,plan_code,industry FROM dealers WHERE id=?",(dealer_id,)).fetchone()
        if not d:return None
        pr=con.execute("SELECT profile_json FROM dealer_profiles WHERE dealer_id=?",(dealer_id,)).fetchone()
        profile={}
        if pr:
            try: profile=json.loads(pr["profile_json"] or "{}")
            except Exception: profile={}
        out=dict(d);out["profile"]=profile;out["allowance"]=credit_settings(con,dealer_id);out["subscription_usage"]=None if out["allowance"]["complimentary"] else paid_usage(con,dealer_id)
        return out
    finally:con.close()

def valid_dealer_profile_email(value):
    if not isinstance(value,str):return False
    email=value.strip()
    if not email or len(email)>254 or email.count('@')!=1:return False
    local,domain=email.split('@')
    if not local or len(local)>64 or local.startswith('.') or local.endswith('.') or '..' in local or not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+",local):return False
    labels=domain.split('.')
    return len(labels)>=2 and all(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?",label) for label in labels) and bool(re.fullmatch(r"[A-Za-z]{2,63}",labels[-1]))

@app.route("/api/account/profile",methods=["GET","POST"])
def account_profile_api():
    dealer_id=str(session.get("dealer_id") or "")
    if not dealer_id:return jsonify(error="Login required"),401
    if request.method=="GET":
        data=_account_profile(dealer_id)
        return (jsonify(data) if data else (jsonify(error="Account not found"),404))
    if is_employee():return jsonify(error="Business owner permission required to change settings."),403
    d=request.get_json(silent=True) or {}
    if not isinstance(d,dict):return jsonify(error="Dealer profile must be an object."),400
    if 'email' in d:
        if not valid_dealer_profile_email(d['email']):return jsonify(error="Enter a valid dealer email address, such as name@company.com. Your saved profile is unchanged."),400
        d['email']=d['email'].strip()
    allowed={"name","company","phone","email","website","address","country","businessType","province","price","coverage","pricingMode","discountPct","gst","pst","marketingEnabled","marketingHeading","marketingWarranty","marketingCtaHeading","marketingCtaText","benefits","pricingMethod","includeRoofImage","includePitch","estimateTemplate","warrantyStatement","estimateMessage","ctaHeading","services","propertyTypes","logoData","showWarrantyShield"}
    profile={k:d[k] for k in allowed if k in d}
    con=estimate_db()
    try:
        row=con.execute("SELECT profile_json FROM dealer_profiles WHERE dealer_id=?",(dealer_id,)).fetchone()
        current={}
        if row:
            try:current=json.loads(row["profile_json"] or "{}")
            except Exception:current={}
        current.update(profile)
        now=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())
        if row:con.execute("UPDATE dealer_profiles SET profile_json=?,updated_at=? WHERE dealer_id=?",(json.dumps(current),now,dealer_id))
        else:con.execute("INSERT INTO dealer_profiles(dealer_id,profile_json,updated_at) VALUES(?,?,?)",(dealer_id,json.dumps(current),now))
        # Keep core searchable account fields synchronized.
        owner_name=str(current.get("name") or "").strip(); region=str(current.get("province") or "").strip(); industry=str(current.get("businessType") or "roofing").strip().lower()
        if owner_name:con.execute("UPDATE dealers SET dealer_name=? WHERE id=?",(owner_name,dealer_id))
        con.execute("UPDATE dealers SET state=?,industry=? WHERE id=?",(region,industry,dealer_id));con.commit()
    finally:con.close()
    return jsonify(ok=True,account=_account_profile(dealer_id))

@app.post("/api/admin/create-signup-account")
def create_signup_account():
    """Bridge endpoint for the public website/backend. Protected by ADMIN_SETUP_KEY until payment/auth service is connected."""
    expected=os.environ.get("ADMIN_SETUP_KEY",""); supplied=request.headers.get("X-Admin-Setup-Key","")
    if not expected or not hmac.compare_digest(supplied,expected):return jsonify(error="Unauthorized"),403
    d=request.get_json(silent=True) or {}; name=str(d.get("name") or d.get("dealer_name") or "").strip(); company=str(d.get("company") or "").strip(); email=str(d.get("email") or "").strip().lower(); password=str(d.get("password") or "")
    plan=str(d.get("plan") or "trial").strip().lower(); industry=str(d.get("industry") or d.get("businessType") or "roofing").strip().lower()
    if plan not in PLAN_LIMITS: return jsonify(error="Unknown plan"),400
    if not name or not email or len(password)<8:return jsonify(error="Name, email and password (8+ characters) required"),400
    limit=PLAN_LIMITS[plan]; did=str(uuid.uuid4()); created=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())
    profile=dict(d.get("profile") or {}); profile.update({k:v for k,v in {"name":name,"company":company,"email":email,"country":d.get("country"),"businessType":industry}.items() if v not in (None,"")})
    con=estimate_db()
    try:
        if login_email_in_use(con,email):return jsonify(error="An AeriQuote login already exists with that email."),409
        con.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,state,status,lookup_limit,estimate_limit,created_at,plan_code,industry) VALUES(?,?,?,?,?,'active',?,?,?,?,?)",(did,name,email,password_hash(password),str(d.get("state") or d.get("province") or ""),limit,limit,created,plan,industry))
        con.execute("INSERT INTO dealer_profiles(dealer_id,profile_json,updated_at) VALUES(?,?,?)",(did,json.dumps(profile),created));con.commit()
    except Exception:return jsonify(error="Could not create account. The email may already be in use."),400
    finally:con.close()
    return jsonify(id=did,name=name,company=company,email=email,plan=plan,industry=industry,measurement_limit=limit,status="active")



# Public website packaging: never fall back to obsolete embedded marketing.
PUBLIC_SITE_UNAVAILABLE = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AeriQuote website temporarily unavailable</title><style>body{font:17px/1.6 system-ui,sans-serif;color:#102a43;margin:0;padding:24px}main{max-width:720px;margin:auto}li{margin:12px 0}a{overflow-wrap:anywhere;color:#0757a6}</style><main><h1>Website files are incomplete</h1><p>The full website and policy drafts are temporarily unavailable. This is not a checkout or a substitute for the complete policies.</p><h2>Approved plans — purchasing unavailable</h2><ul><li>Basic: USD $29/month — 25 property lookups and 25 new saved estimates.</li><li>Pro: USD $59/month — 75 property lookups and 75 new saved estimates.</li><li>Business: USD $99/month — 200 property lookups and 200 new saved estimates.</li></ul><p>Prices in USD. Applicable taxes are added at future checkout after configuration is reviewed.</p><p><strong>Policy draft: payments unavailable. Stripe work is paused until Sean approves after site readiness. No payment, upgrade or subscription starts here.</strong> Approved policies still require operational and legal review; imagery licensing remains unresolved.</p><p>AeriQuote is operated by Shingle Guard Ltd. Email support, privacy and deletion requests: <a href="mailto:support@aeriquote.com">support@aeriquote.com</a>. Mailbox delivery remains unverified.</p></main></html>"""

def _public_site_package_ready(filename):
    try:
        with open(os.path.join(SITE_DIR, "public-package.json"), encoding="utf-8") as handle:
            manifest=json.load(handle)
        files=manifest["files"]
        complete=(manifest["schema"]==1 and isinstance(files,dict) and bool(files) and all(
            isinstance(name,str) and not os.path.isabs(name) and ".." not in name.split("/")
            and os.path.isfile(os.path.join(SITE_DIR,name)) for name in files))
        if not complete or filename not in files:
            return False
        with open(os.path.join(SITE_DIR, filename), "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()==files[filename]
    except (OSError,ValueError,KeyError,TypeError):
        return False


def _public_site_account_industry():
    """Read-only navigation hint, with the same active-session checks as the app.

    This never grants app access: protected routes still validate every request.
    Public pages remain available when a session is absent, disabled or revoked.
    """
    dealer_id=session.get('dealer_id')
    if not dealer_id:return None
    con=estimate_db()
    try:
        account=con.execute('SELECT status,industry FROM dealers WHERE id=?',(dealer_id,)).fetchone()
        if not account or str(account['status']).lower()!='active':return None
        employee_id=session.get('employee_id') if is_employee() else None
        if is_employee() and not employee_id:return None
        if employee_id:
            employee=con.execute('SELECT status FROM dealer_employees WHERE id=? AND dealer_id=?',(employee_id,dealer_id)).fetchone()
            if not employee or str(employee['status']).lower()!='active':return None
        kind='employee' if is_employee() else 'owner'
        if int(session.get('auth_version') or 0)!=auth_version(con,kind,employee_id or dealer_id):return None
        from public_site_navigation import INDUSTRIES
        return account['industry'] if account['industry'] in INDUSTRIES else 'roofing'
    finally:con.close()


def _serve_site_resource(filename):
    disk_path=os.path.join(SITE_DIR, filename)
    if filename.endswith(".html") and (not _public_site_package_ready(filename) or not os.path.isfile(disk_path)):
        return Response(PUBLIC_SITE_UNAVAILABLE, status=503, content_type="text/html; charset=utf-8",
                        headers={"Cache-Control":"no-store"})
    if filename.endswith('.html') and os.path.isfile(disk_path):
        from public_site_navigation import signed_in_links, industry_for, measuring_url, TRIAL_PATHS
        industry=_public_site_account_industry()
        if industry and '/site/'+filename.removesuffix('.html') in TRIAL_PATHS:
            response=redirect(measuring_url(industry_for(filename,industry,request.query_string.decode('latin-1'))))
        else:
            with open(disk_path,encoding='utf-8') as handle:document=handle.read()
            response=Response(signed_in_links(document,filename,industry) if industry else document,
                              content_type='text/html; charset=utf-8')
        response.headers['Cache-Control']='private, no-store'
        response.vary.add('Cookie')
        return response
    if os.path.isfile(disk_path):
        return send_from_directory(SITE_DIR, filename)
    return Response("Required website asset unavailable", status=404, content_type="text/plain; charset=utf-8")

# V11.6.84 — integrated public website + trial signup bridge.
# Use an absolute folder based on app.py so Render can serve the website even if
# the service working directory differs from the project directory.
SITE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site")

@app.get("/site")
@app.get("/site/")
def public_site_home():
    return _serve_site_resource("index.html")

PUBLIC_SITE_PAGES=frozenset(['help', 'privacy-policy', 'about', 'roofer-setup', 'pressure-setup', 'refund-cancellation', 'commercial-setup', 'terms-of-use', 'contact-support', 'upgrade', 'landscaping-setup', 'pricing', 'features', 'login', 'faq', 'start-free-trial', 'trial-signup', 'paving-setup', 'snow-setup', 'choose-plan', 'checkout', 'how-it-works', 'industries/paving-sealcoating', 'industries/pressure-washing', 'industries/roofing', 'industries/commercial-property', 'industries/landscaping', 'industries/snow-removal'])

def public_page_redirect(destination):
    query=request.query_string.decode("latin-1")
    return redirect(destination+("?"+query if query else ""),code=308)

@app.get("/site/<path:filename>")
def public_site_file(filename):
    if filename in {"login","login.html"}:return public_page_redirect("/dealer-login")
    if filename=="index.html":return public_page_redirect("/site/")
    if filename.endswith(".html") and filename[:-5] in PUBLIC_SITE_PAGES:
        return public_page_redirect("/site/"+filename[:-5])
    if filename in PUBLIC_SITE_PAGES:filename+=".html"
    return _serve_site_resource(filename)

@app.get("/favicon.ico")
def public_favicon():
    return _serve_site_resource("assets/favicon.svg")

@app.get("/pricing")
@app.get("/pricing.html")
def public_pricing_direct():
    return public_page_redirect("/site/pricing")

# Friendly direct routes used during signup testing.
@app.get("/trial-signup.html")
def public_trial_signup_direct():
    return public_page_redirect("/site/trial-signup")

@app.get("/roofer-setup.html")
def public_roofer_setup_direct():
    return public_page_redirect("/site/roofer-setup")

@app.post("/api/public/signup")
def public_signup():
    d=request.get_json(silent=True) or {}
    name=str(d.get("name") or "").strip(); company=str(d.get("company") or "").strip()
    email=str(d.get("email") or "").strip().lower(); password=str(d.get("password") or "")
    country=str(d.get("country") or "Canada").strip()
    industry=str(d.get("industry") or "roofing").strip().lower()
    if industry not in {"roofing","snow","pressure","paving","landscaping","commercial"}: industry="roofing"
    if not name or not company or not email or len(password)<8:
        return jsonify(error="Name, business name, email and a password of at least 8 characters are required."),400
    did=str(uuid.uuid4()); created=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()); limit=PLAN_LIMITS["trial"]
    profile={"name":name,"company":company,"email":email,"country":"CA" if country.lower().startswith("can") else "US","businessType":industry}
    con=estimate_db()
    try:
        if login_email_in_use(con,email):
            return jsonify(error="An AeriQuote account already exists with that email."),409
        con.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,state,status,lookup_limit,estimate_limit,created_at,plan_code,industry) VALUES(?,?,?,?,?,'active',?,?,?,?,?)",(did,name,email,password_hash(password),"",limit,limit,created,"trial",industry))
        con.execute("INSERT INTO dealer_profiles(dealer_id,profile_json,updated_at) VALUES(?,?,?)",(did,json.dumps(profile),created));con.commit()
    finally: con.close()
    session.clear();session["dealer_id"]=did;session["dealer_name"]=name;session["account_type"]="owner"
    return jsonify(ok=True,redirect=("/site/snow-setup.html" if industry=="snow" else "/site/pressure-setup.html" if industry=="pressure" else "/site/paving-setup.html" if industry=="paving" else "/site/landscaping-setup.html" if industry=="landscaping" else "/site/commercial-setup.html" if industry=="commercial" else "/site/roofer-setup.html"),plan="trial",industry=industry,measurement_limit=limit)


HEAD_OFFICE_DEALERS_HTML=r"""<!doctype html><html><head><meta charset="utf-8"><title>AeriQuote Dealer Management</title>
<style>body{font-family:Arial;background:#f1f5f9;color:#17212b;margin:0}.wrap{max-width:1050px;margin:28px auto;padding:0 16px}.card{background:#fff;border-radius:16px;box-shadow:0 8px 28px #0002;padding:22px;margin-bottom:18px}h1,h2{color:#102a43;margin-top:0}.top{display:flex;justify-content:space-between;align-items:center;gap:12px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.full{grid-column:1/-1}label{font-weight:800;display:block;margin:5px 0}input,select{width:100%;box-sizing:border-box;padding:11px;border:1px solid #cbd5ce;border-radius:8px;font-size:15px}button,.btn{display:inline-block;border:0;border-radius:9px;padding:11px 15px;background:#1677c8;color:#fff;font-weight:900;text-decoration:none;cursor:pointer}.secondary{background:#fff;color:#1677c8;border:1px solid #1677c8}.msg{padding:10px;border-radius:8px;background:#edf7f0;color:#174f2b;margin-bottom:12px}.err{padding:10px;border-radius:8px;background:#fff0f0;color:#a11;margin-bottom:12px}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:10px;border-bottom:1px solid #d9e3ea;font-size:14px}th{color:#102a43;background:#f8faf9}.pill{display:inline-block;padding:4px 8px;border-radius:999px;background:#edf7f0;font-weight:800;font-size:12px}.networkDashboard{margin-top:18px}.networkTotals{display:grid;grid-template-columns:repeat(4,1fr);gap:9px;margin:12px 0 14px}.networkMetric{background:#f8fafc;border:1px solid #d9e3ea;border-radius:9px;padding:10px}.networkMetric span{display:block;font-size:11px;font-weight:900;color:#5b6770;text-transform:uppercase}.networkMetric b{display:block;margin-top:3px;font-size:18px;color:#102a43}.networkTableWrap{overflow:auto}.networkTable{width:100%;border-collapse:collapse;font-size:12px}.networkTable th,.networkTable td{padding:8px 9px;border-bottom:1px solid #e3e9ee;text-align:right;white-space:nowrap}.networkTable th:first-child,.networkTable td:first-child{text-align:left}.inventoryGrid{display:grid;grid-template-columns:repeat(4,1fr);gap:9px;margin:12px 0}.inventoryForm{display:flex;gap:10px;align-items:end;flex-wrap:wrap}.inventoryForm>div{min-width:180px;flex:1}.inventoryBar{height:12px;background:#e6ebef;border-radius:999px;overflow:hidden;margin-top:10px}.inventoryBarFill{height:100%;background:#334e68;border-radius:999px}.reorderAlert{margin-top:12px;padding:12px;border-radius:9px;font-weight:900;background:#fff3cd;border:1px solid #e0b84f;color:#6b4e00}.inventoryOK{margin-top:12px;padding:10px;border-radius:9px;font-weight:800;background:#edf7f0;border:1px solid #b9d9c2;color:#245c32}
@media(max-width:700px){.grid{grid-template-columns:1fr}.full{grid-column:auto}.top{align-items:flex-start;flex-direction:column}table{display:block;overflow:auto}.networkTotals{grid-template-columns:1fr 1fr}.inventoryGrid{grid-template-columns:1fr 1fr}}</style></head>
<body><div class="wrap"><div class="top"><div><h1>AeriQuote — Dealer Management</h1><div>Head Office</div></div><div><a class="btn secondary" href="/">BACK TO ROOF ASSESSMENT</a> <a class="btn secondary" href="/logout">LOG OUT</a></div></div>
<div class="card networkDashboard"><h2>Head Office Network Dashboard</h2>
<div class="networkTotals">
<div class="networkMetric"><span>Total Dealers</span><b>{{network_totals["total_dealers"]}}</b></div>
<div class="networkMetric"><span>Active Dealers</span><b>{{network_totals["active_dealers"]}}</b></div>
<div class="networkMetric"><span>Estimates</span><b>{{network_totals["estimates"]}}</b></div>
<div class="networkMetric"><span>Booked</span><b>{{network_totals["booked"]}}</b></div>
<div class="networkMetric"><span>Completed</span><b>{{network_totals["completed"]}}</b></div>
<div class="networkMetric"><span>Property Lookups</span><b>{{network_totals["lookups"]}}</b></div>
<div class="networkMetric"><span>Estimate Value</span><b>${{"{:,.2f}".format(network_totals["estimate_value"])}}</b></div>
<div class="networkMetric"><span>Booked Value</span><b>${{"{:,.2f}".format(network_totals["booked_value"])}}</b></div>
<div class="networkMetric"><span>Completed Value</span><b>${{"{:,.2f}".format(network_totals["completed_value"])}}</b></div>
<div class="networkMetric"><span>Amount Paid</span><b>${{"{:,.2f}".format(network_totals["amount_paid"])}}</b></div>
<div class="networkMetric"><span>Outstanding</span><b>${{"{:,.2f}".format(network_totals["balance"])}}</b></div>
</div>
<div class="networkTableWrap"><table class="networkTable"><thead><tr><th>Dealer</th><th>Estimates</th><th>Booked</th><th>Completed</th><th>Estimate Value</th><th>Paid</th><th>Balance</th><th>Lookups</th><th>Estimate Usage</th><th>Last Activity</th></tr></thead><tbody>
{% for n in network_dealers %}<tr><td><b>{{n.dealer_name}}</b><br><span style="color:#5b6770">{{n.state or ''}}{% if n.status!='active' %} • Disabled{% endif %}</span></td><td>{{n["estimate_used"]}}</td><td>{{n["booked"]}}</td><td>{{n["completed"]}}</td><td>${{"{:,.2f}".format(n["estimate_value"])}}</td><td>${{"{:,.2f}".format(n["amount_paid"])}}</td><td>${{"{:,.2f}".format(n["balance"])}}</td><td>{{n["lookup_used"]}} / {{n["lookup_limit"]}}</td><td>{{n["estimate_used"]}} / {{n["estimate_limit"]}}</td><td>{{n["last_activity"] or "—"}}</td></tr>{% endfor %}
</tbody></table></div></div>
<div class="card"><h2>Season Product Inventory</h2>
<div style="color:#5b6770;font-size:13px">Network-wide planning estimate based only on jobs marked Completed.</div>
<div class="inventoryGrid">
<div class="networkMetric"><span>Starting Inventory</span><b>{{"{:,.1f}".format(inventory.starting_gallons)}} gal</b></div>
<div class="networkMetric"><span>Product Added</span><b>{{"{:,.1f}".format(inventory.product_added)}} gal</b></div>
<div class="networkMetric"><span>Total Product Available</span><b>{{"{:,.1f}".format(inventory.total_available)}} gal</b></div>
<div class="networkMetric"><span>Completed Roof Area</span><b>{{"{:,.0f}".format(inventory.completed_area)}} sq. ft.</b></div>
<div class="networkMetric"><span>Estimated Used</span><b>{{"{:,.1f}".format(inventory.used_gallons)}} gal</b></div>
<div class="networkMetric"><span>Estimated Remaining</span><b>{{"{:,.1f}".format(inventory.remaining_gallons)}} gal</b></div>
<div class="networkMetric"><span>Inventory Used</span><b>{{"{:,.1f}".format(inventory.used_percent)}}%</b></div>
<div class="networkMetric"><span>Gallons Above Reorder Level</span><b>{{"{:,.1f}".format(inventory.gallons_above_reorder)}} gal</b></div>
</div>
<div class="inventoryBar"><div class="inventoryBarFill" style="width:{{inventory.bar_percent}}%"></div></div>
{% if inventory.starting_gallons>0 and inventory.remaining_gallons<=inventory.reorder_level %}
<div class="reorderAlert">PRODUCTION REORDER LEVEL REACHED — Estimated remaining inventory is {{ "{:,.1f}".format(inventory.remaining_gallons) }} gallons.</div>
{% elif inventory.starting_gallons>0 %}
<div class="inventoryOK">Inventory is above the production reorder level of {{ "{:,.1f}".format(inventory.reorder_level) }} gallons.</div>
{% endif %}
<form class="inventoryForm" method="post" action="/head-office/inventory-settings" style="margin-top:14px">
<div><label>Season Start Date</label><input name="season_start_date" type="date" value="{{inventory.season_start_date}}" required></div>
<div><label>Season Starting Gallons</label><input name="starting_gallons" type="number" min="0" step="0.1" value="{{inventory.starting_gallons}}" required></div>
<div><label>Product Added This Season (gal)</label><input name="product_added" type="number" min="0" step="0.1" value="{{inventory.product_added}}" required></div>
<div><label>Coverage per Gallon (sq. ft.)</label><input name="coverage_per_gallon" type="number" min="1" step="0.1" value="{{inventory.coverage_per_gallon}}" required></div>
<div><label>Production Reorder Level (gal)</label><input name="reorder_level" type="number" min="0" step="0.1" value="{{inventory.reorder_level}}" required></div>
<div><button type="submit">SAVE INVENTORY SETTINGS</button></div>
</form></div>
<div class="card"><a href="/head-office/support">Support requests</a> · <a href="/head-office/storage">Deployment storage check</a></div><div class="card"><h2>Create Dealer Account</h2>{% if message %}<div class="msg">{{message}}</div>{% endif %}{% if error %}<div class="err" role="alert">{{error}}</div>{% endif %}
<form method="post"><div class="grid"><div><label>Dealer / Owner Name</label><input name="dealer_name" required></div><div><label>Company Name</label><input name="company"></div><div><label>Email / Login</label><input name="email" type="email" required></div><div><label for="adminCountry">Country</label><select id="adminCountry" onchange="filterAdminRegions()"><option value="CA">Canada</option><option value="US">United States</option></select></div><div><label for="adminRegion">Province / State</label><select id="adminRegion" name="state"><option value="">Choose region</option><optgroup label="CA"><option>AB</option><option>BC</option><option>MB</option><option>NB</option><option>NL</option><option>NS</option><option>NT</option><option>NU</option><option>ON</option><option>PE</option><option>QC</option><option>SK</option><option>YT</option></optgroup><optgroup label="US">{% for s in states %}<option value="{{s}}">{{s}}</option>{% endfor %}</optgroup></select></div><div><label>Temporary Password</label><input name="password" type="password" minlength="8" required></div><div><label>Account Status</label><select name="status"><option value="active">Active</option><option value="disabled">Disabled</option></select></div><div class="full"><label>Permission Level</label><input value="Dealer Owner" readonly></div><div class="full"><button type="submit">CREATE DEALER ACCOUNT</button></div></div></form></div>
<div class="card"><h2>Dealer Accounts</h2>
{% for d in dealers %}
<div style="border:1px solid #d9e3ea;border-radius:12px;padding:14px;margin:12px 0">
<div style="display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap"><div><strong>{{d.dealer_name}}</strong> &nbsp; {{d.email}} &nbsp; {{d.state or ''}}<div style="margin-top:6px;font-size:13px"><b>Property Lookups:</b> {{d.lookup_used}} / {{d.lookup_limit}} &nbsp; • &nbsp; <b>Estimates:</b> {{d.estimate_used}} / {{d.estimate_limit}}</div></div><span class="pill">{{d.status|title}}</span></div>
{% if 'head office' not in d.dealer_name|lower %}
<details style="margin-top:12px"><summary style="font-weight:800;cursor:pointer">EDIT DEALER</summary>
<form method="post" action="/head-office/dealers/{{d.id}}/edit"><div class="grid" style="margin-top:12px">
<div><label>Dealer / Owner Name</label><input name="dealer_name" value="{{d.dealer_name}}" required></div>
<div><label>Email / Login</label><input name="email" type="email" value="{{d.email}}" required></div>
<div><label>State</label><input name="state" value="{{d.state or ''}}" maxlength="2"></div>
<div><label>Property Lookup Limit</label><input name="lookup_limit" type="number" min="0" value="{{d.lookup_limit}}"></div>
<div><label>Estimate Limit</label><input name="estimate_limit" type="number" min="0" value="{{d.estimate_limit}}"></div>
<div style="align-self:end"><button type="submit">SAVE DEALER CHANGES</button></div></div></form></details>
<details style="margin-top:10px"><summary style="font-weight:800;cursor:pointer">RESET PASSWORD</summary>
<form method="post" action="/head-office/dealers/{{d.id}}/password" style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap"><input style="max-width:320px" name="password" type="password" minlength="8" placeholder="New temporary password" required><button type="submit">SAVE NEW PASSWORD</button></form></details>
<form method="post" action="/head-office/dealers/{{d.id}}/status" style="margin-top:12px"><input type="hidden" name="action" value="{{'activate' if d.status=='disabled' else 'disable'}}"><button type="submit" style="background:{{'#1677c8' if d.status=='disabled' else '#7a263a'}}">{{'ACTIVATE DEALER' if d.status=='disabled' else 'DISABLE DEALER'}}</button></form>
{% else %}<div style="margin-top:10px;font-size:13px"><strong>Head Office</strong> — protected account</div>{% endif %}
</div>{% endfor %}</div></div><script>
const adminRegionGroups=Array.from(document.querySelectorAll('#adminRegion optgroup')).map(g=>({country:g.label,options:Array.from(g.querySelectorAll('option')).map(o=>({value:o.value,text:o.textContent}))}));
const adminRegionMemory={};let adminPreviousCountry='';
function filterAdminRegions(){const country=document.getElementById('adminCountry').value,region=document.getElementById('adminRegion');if(adminPreviousCountry)adminRegionMemory[adminPreviousCountry]=region.value;region.replaceChildren(new Option('Choose '+(country==='CA'?'province / territory':'state'),''));for(const o of adminRegionGroups.find(g=>g.country===country).options)region.add(new Option(o.text,o.value));region.value=adminRegionMemory[country]||'';adminPreviousCountry=country}
filterAdminRegions();
</script></body></html>"""

US_STATES=['AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY','DC']

def is_head_office():
    if session.get("account_type") != "owner" or not session.get("dealer_id"):
        return False
    con=estimate_db()
    try:
        row=con.execute("SELECT dealer_name,email,status FROM dealers WHERE id=?",(session["dealer_id"],)).fetchone()
        return bool(row and str(row["status"]).lower()=="active" and (str(row["email"]).strip().lower()=="sdusome@diitalk.com" or con.execute("SELECT dealer_id FROM account_admin_roles WHERE dealer_id=?",(session["dealer_id"],)).fetchone()))
    finally:
        con.close()


AERIQUOTE_ADMIN_HTML=r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AeriQuote | Admin Dashboard</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f3f6fa;color:#172b45;font:15px system-ui,-apple-system,Segoe UI,Arial,sans-serif}header{background:#102b4a;color:white;padding:24px max(22px,calc((100vw - 1140px)/2));display:flex;justify-content:space-between;align-items:center;gap:18px;flex-wrap:wrap}header h1{margin:0;font-size:25px}header p{margin:4px 0 0;color:#bcd2e8}a{color:#1469b0}header a{color:white;text-decoration:none;border:1px solid #607d9d;border-radius:9px;padding:9px 13px}main{max-width:1140px;margin:30px auto;padding:0 18px}.intro{display:flex;justify-content:space-between;align-items:center;gap:15px;flex-wrap:wrap}.intro h2{margin:0}.muted{color:#64748b}.metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:15px;margin:23px 0}.metric,.panel{background:white;border:1px solid #e1e8f1;border-radius:14px;box-shadow:0 4px 14px #12243b08}.metric{padding:20px}.metric span{color:#607086;font-size:13px;display:block}.metric strong{display:block;font-size:27px;margin-top:9px}.panel{padding:23px;margin:18px 0}.panel h3{margin:0 0 8px;font-size:19px}.pill{display:inline-block;border-radius:50px;padding:5px 11px;background:#edf2f8;color:#42566d;font-size:12px;font-weight:700}.note{padding:14px 16px;background:#f4f7fb;border-radius:10px;border:1px solid #dce5f0;margin-top:15px}table{width:100%;border-collapse:collapse;min-width:680px}th,td{text-align:left;border-bottom:1px solid #e7edf4;padding:13px 10px;font-size:14px}th{color:#607086;font-size:12px;text-transform:uppercase;letter-spacing:.04em}td strong{display:block}td small{color:#64748b}.scroll{overflow:auto}input{padding:11px 12px;border:1px solid #cdd9e6;border-radius:9px;font:inherit;width:100%;max-width:350px}.tag{background:#eaf5ef;color:#18643a;border-radius:6px;padding:4px 8px;font-size:12px}.tag.off{background:#f3f4f6;color:#64748b}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.disabled{opacity:.55;cursor:not-allowed;border:0;background:#cbd5e1;color:#334155;padding:10px 15px;border-radius:8px;font-weight:700}button:not(.disabled){cursor:pointer}@media(max-width:720px){.metrics,.grid{grid-template-columns:1fr}.panel{padding:16px}header{padding:20px}}
</style></head><body>
<header><div><h1>AeriQuote <span style="font-weight:400">/ Admin</span></h1><p>Activations, conversion & revenue</p></div><nav aria-label="Admin navigation" style="display:flex;flex-wrap:wrap;gap:10px"><a href="/head-office/support">Support requests</a><a href="/head-office/storage">Deployment storage check</a><a href="/site/index.html">AeriQuote Website</a><a href="/logout">Log Out</a></nav></header>
<main><div class="intro"><div><h2>Overview</h2><p class="muted">Manage AeriQuote software accounts. Business estimates remain private to each business.</p></div><span class="pill">Head Office</span></div>
<div class="metrics"><div class="metric"><span>Registered Customer Accounts</span><strong>{{total_accounts}}</strong></div><div class="metric"><span>Enabled Customer Accounts</span><strong>{{active_accounts}}</strong></div><div class="metric"><span>Subscription Revenue</span><strong>—</strong><small class="muted">Awaiting Stripe connection</small></div></div>
<section class="panel"><h3>Subscriptions &amp; Trials</h3><p class="muted">Paid subscriptions, upgrades, cancellations and subscription revenue: <strong>Not connected</strong>. These figures require verified billing records. Enabled accounts and assigned plans do not confirm payment.</p><div class="scroll"><table aria-label="Registrations by reporting period"><thead><tr><th>Period</th><th>Customer signups</th><th>Currently trial</th><th>Currently Basic / Pro / Business</th><th>Complimentary dealers</th><th>Legacy / other</th><th>QA signups excluded</th></tr></thead><tbody>{% for m in plan_report.periods %}<tr><td><strong>{{m.name}}</strong><small>Since {{m.start}}</small></td><td>{{m.signups}}</td><td>{{m.trials}}</td><td>{{m.assigned_plans}}</td><td>{{m.complimentary}}</td><td>{{m.legacy}}</td><td>{{m.qa}}</td></tr>{% endfor %}</tbody></table></div><p class="muted">Registration dates grouped by each account's current plan. This is not a count of new paid subscriptions or historical plan changes. America/Edmonton calendar periods; weeks begin Monday.</p><div class="scroll"><table aria-label="Current account plans"><thead><tr><th>Current plan</th><th>Accounts</th><th>Enabled accounts</th></tr></thead><tbody>{% for p in plan_report.plans %}<tr><td>{{p.label}}</td><td>{{p.total}}</td><td>{{p.enabled}}</td></tr>{% endfor %}</tbody></table></div><div class="note">{{plan_report.qa_count}} explicitly labelled QA accounts excluded from customer totals and activation reporting. A business owner or company name beginning with “QA TEST” marks a QA account. Other internal accounts must be labelled to exclude them. Employees do not count as subscriptions.</div></section>
<section class="panel"><h3>Account Activations & Revenue</h3><p class="muted">An account activates after its first successful property measurement. Each business counts once, including measurements by its employees.</p><div class="scroll"><table><thead><tr><th>Period</th><th>Signups</th><th>First measurements</th><th>Signup conversion</th><th>Revenue</th></tr></thead><tbody>{% for m in metrics %}<tr><td><strong>{{m.name}}</strong><small>Since {{m.start}}</small></td><td>{{m.signups}}</td><td>{{m.activations}}</td><td>{% if m.conversion is not none %}{{m.conversion}}%<small style="display:block">{{m.cohort_activated}} of {{m.signups}} signups activated</small>{% else %}—{% endif %}</td><td><strong>Not connected</strong></td></tr>{% endfor %}</tbody></table></div><p class="muted">Reporting timezone: America/Edmonton. Weeks begin Monday. Conversion follows accounts registered in each period; first measurements also include older accounts activating during that period.</p><div class="note"><b>{{activated_accounts}} recorded account activations.</b> First-measurement tracking begins with this update. Earlier measurements have no verified activation timestamp and are not backdated. <br><b>Revenue is not connected.</b> Confirmed subscription payment records will supply revenue after payments are connected.</div></section>
<section class="panel"><div class="intro"><div><h3>Customer Accounts</h3><p class="muted">Find an account by business name or email. Usage and estimates are available to business owners in their own workspace.</p></div><input id="search" type="search" placeholder="Search business or email..." aria-label="Search customer accounts" oninput="filterAccounts()"></div><div class="scroll"><table id="accounts"><thead><tr><th>Business / Owner</th><th>Login Email</th><th>Plan</th><th>Account</th><th>Activation</th></tr></thead><tbody>{% for a in accounts %}<tr><td><strong>{{a.dealer_name}}</strong></td><td>{{a.email}}</td><td>{{'Complimentary dealer — 200 monthly' if a.complimentary else (a.plan_code or 'Legacy')|title}}</td><td>{% if a.status|lower == 'active' %}<span class="tag">Active</span>{% else %}<span class="tag off">{{a.status|title}}</span>{% endif %}</td><td>{% if a.first_measured_at %}<span class="tag">Measured</span>{% else %}<span class="muted">Not recorded</span>{% endif %}</td></tr>{% endfor %}</tbody></table></div></section>
<section class="panel"><details><summary style="cursor:pointer;font-weight:700;font-size:19px">Employee Login Lookup</summary><p class="muted">Find which business owns an employee login. Access is read-only; business owners manage their employees.</p><input type="search" placeholder="Search employee name or login..." aria-label="Search employee logins" oninput="document.querySelectorAll('#employeeLookup tbody tr').forEach(row=>row.hidden=!row.textContent.toLowerCase().includes(this.value.toLowerCase()))"><div class="scroll"><table id="employeeLookup"><thead><tr><th>Employee</th><th>Employee login</th><th>Status</th><th>Business</th><th>Owner login email</th></tr></thead><tbody>{% for e in employee_accounts %}<tr><td>{{e.employee_name}}</td><td>{{e.employee_email}}</td><td>{{e.employee_status|title}}</td><td>{{e.business_name}}</td><td>{{e.owner_email}}</td></tr>{% else %}<tr><td colspan="5">No employee logins recorded.</td></tr>{% endfor %}</tbody></table></div></details></section>
<div class="grid"><section class="panel"><h3>Measurement Credits and Dealer Access</h3><p>Add 25, 75 or 150 measurement and estimate credits, manage complimentary dealer allowances, and assign warranty branding.</p><p><a href="/head-office/credits">MANAGE CREDITS AND DEALER ACCESS</a></p><small class="muted">Usage credits only. No money is refunded or charged.</small></section><section class="panel"><h3>Refund a Purchase</h3><p class="muted">Review an original payment and issue a full or partial refund.</p><p><button class="disabled" disabled title="Available after Stripe integration">Issue Refund — Coming Later</button></p><small class="muted">No money can move from this dashboard yet.</small></section></div>
<p class="muted" style="margin:24px 0 38px">Development dashboard · Billing integration deferred until AeriQuote industry workflows are complete.</p></main>
<script>function filterAccounts(){const q=document.getElementById('search').value.toLowerCase().trim();document.querySelectorAll('#accounts tbody tr').forEach(r=>{r.hidden=!r.textContent.toLowerCase().includes(q)})}</script></body></html>"""

@app.post("/api/account/activation")
def record_account_activation():
    did=str(session.get("dealer_id") or "")
    data=request.get_json(silent=True) or {}
    token=str(data.get("token") or "")
    measurement=SESSIONS.get(token)
    try: amount=float(data.get("amount") or 0)
    except (TypeError,ValueError): amount=0
    if not measurement or measurement.get("dealer_id")!=did or not math.isfinite(amount) or amount<=0 or data.get("kind") not in {"roof","area","linear"}:
        return jsonify(error="A successful measurement on your property session is required."),400
    con=estimate_db()
    try:
        account=con.execute("SELECT status FROM dealers WHERE id=?",(did,)).fetchone()
        if not account or str(account["status"]).lower()!="active":return jsonify(error="Active account required."),403
        con.execute("INSERT INTO account_activations(dealer_id,first_measured_at) VALUES(?,?) ON CONFLICT(dealer_id) DO NOTHING",(did,datetime.utcnow().isoformat()+"Z"))
        con.commit()
    finally:con.close()
    return jsonify(recorded=True)

register_credits(app, estimate_db, is_head_office)

@app.get("/head-office/dealers")
def aeriquote_admin_dashboard():
    if not is_head_office():return Response("Head Office permission required.",status=403)
    con=estimate_db()
    try:
        rows=con.execute("SELECT d.dealer_name,d.email,d.status,d.plan_code,d.created_at,a.first_measured_at,p.profile_json,COALESCE(ca.complimentary,0) AS complimentary FROM dealers d LEFT JOIN account_allowances ca ON ca.dealer_id=d.id LEFT JOIN account_activations a ON a.dealer_id=d.id LEFT JOIN dealer_profiles p ON p.dealer_id=d.id WHERE lower(d.email)<>? AND lower(d.dealer_name)<>? ORDER BY d.created_at DESC",("sdusome@diitalk.com","head office")).fetchall()
        accounts=[dict(row) for row in rows]
        for account in accounts:
            try: account["company"]=json.loads(account.pop("profile_json") or "{}").get("company", "")
            except (ValueError, TypeError, AttributeError): account["company"]=""
        plan_report=account_plan_report(accounts)
        customer_accounts=plan_report["customers"]
        employee_accounts=[dict(row) for row in con.execute("SELECT e.employee_name,e.email AS employee_email,e.status AS employee_status,d.dealer_name AS business_name,d.email AS owner_email FROM dealer_employees e JOIN dealers d ON d.id=e.dealer_id ORDER BY lower(e.email)").fetchall()]
    finally:
        con.close()
    return render_template_string(AERIQUOTE_ADMIN_HTML,accounts=accounts,employee_accounts=employee_accounts,plan_report=plan_report,total_accounts=len(customer_accounts),active_accounts=sum(str(a["status"]).lower()=="active" for a in customer_accounts),metrics=account_metrics(customer_accounts),activated_accounts=sum(bool(a["first_measured_at"]) for a in customer_accounts))

@app.route("/head-office/legacy-dealers",methods=["GET","POST"])
def head_office_dealers():
    if not is_head_office(): return Response("Head Office permission required.",status=403)
    message=None; error=None
    if request.method=="POST":
        name=str(request.form.get("dealer_name") or "").strip()
        email=str(request.form.get("email") or "").strip().lower()
        state=str(request.form.get("state") or "").strip().upper()
        password=str(request.form.get("password") or "")
        status_value=str(request.form.get("status") or "active").strip().lower()
        if status_value not in {"active","disabled"}: status_value="active"
        if not name or not email or len(password)<8:
            error="Dealer name, email and a temporary password of at least 8 characters are required."
        else:
            con=estimate_db()
            try:
                existing=login_email_in_use(con,email)
                if existing: error="A dealer account with that email already exists."
                else:
                    did=str(uuid.uuid4()); created=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())
                    con.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,state,status,lookup_limit,estimate_limit,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                                (did,name,email,password_hash(password),state,status_value,250,150,created))
                    con.commit(); message="Dealer account created. You can now log out and test that dealer's access."
            finally: con.close()
    con=estimate_db()
    try:
        raw_dealers=con.execute("SELECT id,dealer_name,email,state,status,lookup_limit,estimate_limit,created_at FROM dealers ORDER BY created_at ASC").fetchall()
        dealers=[]
        for r in raw_dealers:
            d=dict(r)
            u=con.execute("SELECT property_lookups FROM dealer_usage WHERE dealer_id=?",(d["id"],)).fetchone()
            d["lookup_used"]=int(u["property_lookups"] if u else 0)
            estimate_rows=con.execute("SELECT total_price,payload,created_at FROM estimates WHERE dealer_id=? ORDER BY created_at DESC",(d["id"],)).fetchall()
            d["estimate_used"]=len(estimate_rows)
            d["booked"]=0; d["completed"]=0; d["estimate_value"]=0.0; d["booked_value"]=0.0; d["completed_value"]=0.0; d["amount_paid"]=0.0; d["last_activity"]=""; d["completed_area"]=0.0
            for er in estimate_rows:
                d["estimate_value"]+=float(er["total_price"] or 0)
                try: ep=json.loads(er["payload"] or "{}")
                except Exception: ep={}
                es=str(ep.get("job_status") or "Estimate")
                if es=="Booked":
                    d["booked"]+=1; d["booked_value"]+=float(er["total_price"] or 0)
                elif es=="Completed":
                    d["completed"]+=1; d["completed_value"]+=float(er["total_price"] or 0)
                    try: d["completed_area"]+=max(0.0,float(ep.get("total_area") or 0))
                    except Exception: pass
                try: d["amount_paid"]+=max(0.0,float(ep.get("amount_paid") or 0))
                except Exception: pass
            d["balance"]=max(0.0,d["estimate_value"]-d["amount_paid"])
            if estimate_rows:
                raw_activity=estimate_rows[0]["created_at"]
                if raw_activity:
                    try:
                        d["last_activity"]=raw_activity.strftime("%Y-%m-%d")
                    except Exception:
                        activity_text=str(raw_activity)
                        m=re.search(r"\d{4}-\d{2}-\d{2}",activity_text)
                        d["last_activity"]=m.group(0) if m else activity_text
                else:
                    d["last_activity"]=""
            dealers.append(d)
    finally: con.close()
    network_dealers=dealers
    network_totals={"total_dealers":len(dealers),
                    "active_dealers":sum(1 for d in dealers if str(d["status"] or "").lower()=="active"),
                    "estimates":sum(d["estimate_used"] for d in dealers),
                    "booked":sum(d["booked"] for d in dealers),
                    "completed":sum(d["completed"] for d in dealers),
                    "estimate_value":sum(d["estimate_value"] for d in dealers),
                    "booked_value":sum(d["booked_value"] for d in dealers),
                    "completed_value":sum(d["completed_value"] for d in dealers),
                    "amount_paid":sum(d["amount_paid"] for d in dealers),
                    "balance":sum(d["balance"] for d in dealers),
                    "lookups":sum(d["lookup_used"] for d in dealers)}
    con=estimate_db()
    try:
        setting_rows=con.execute("SELECT setting_key,setting_value FROM head_office_settings WHERE setting_key IN (?,?,?,?,?)",("starting_gallons","coverage_per_gallon","reorder_level","season_start_date","product_added")).fetchall()
        settings={r["setting_key"]:r["setting_value"] for r in setting_rows}
    finally: con.close()
    try: starting_gallons=max(0.0,float(settings.get("starting_gallons","0")))
    except Exception: starting_gallons=0.0
    season_start_date=str(settings.get("season_start_date") or "2026-01-01")
    try: product_added=max(0.0,float(settings.get("product_added","0")))
    except Exception: product_added=0.0
    try: coverage_per_gallon=max(1.0,float(settings.get("coverage_per_gallon","325")))
    except Exception: coverage_per_gallon=325.0
    try: reorder_level=max(0.0,float(settings.get("reorder_level","600")))
    except Exception: reorder_level=600.0
    completed_area=0.0
    con=estimate_db()
    try:
        season_rows=con.execute("SELECT payload FROM estimates").fetchall()
        for sr in season_rows:
            try: sp=json.loads(sr["payload"] or "{}")
            except Exception: sp={}
            if str(sp.get("job_status") or "Estimate")!="Completed": continue
            completion_date=str(sp.get("completion_date") or "")[:10]
            if completion_date and completion_date < season_start_date: continue
            try: completed_area+=max(0.0,float(sp.get("total_area") or 0))
            except Exception: pass
    finally: con.close()
    total_available=starting_gallons+product_added
    used_gallons=completed_area/coverage_per_gallon
    remaining_gallons=max(0.0,total_available-used_gallons)
    used_percent=(used_gallons/total_available*100.0) if total_available>0 else 0.0
    inventory={"starting_gallons":starting_gallons,"product_added":product_added,"total_available":total_available,
               "season_start_date":season_start_date,"coverage_per_gallon":coverage_per_gallon,
               "completed_area":completed_area,"used_gallons":used_gallons,"remaining_gallons":remaining_gallons,
               "used_percent":used_percent,"bar_percent":min(100.0,max(0.0,used_percent)),"reorder_level":reorder_level,
               "gallons_above_reorder":max(0.0,remaining_gallons-reorder_level)}
    return render_template_string(HEAD_OFFICE_DEALERS_HTML,dealers=dealers,states=US_STATES,message=message,error=error,network_dealers=network_dealers,network_totals=network_totals,inventory=inventory)


@app.post("/head-office/inventory-settings")
def head_office_inventory_settings():
    if not is_head_office(): return Response("Head Office permission required.",status=403)
    try:
        starting=max(0.0,float(request.form.get("starting_gallons") or 0))
        product_added=max(0.0,float(request.form.get("product_added") or 0))
        coverage=max(1.0,float(request.form.get("coverage_per_gallon") or 325))
        reorder_level=max(0.0,float(request.form.get("reorder_level") or 600))
        season_start_date=str(request.form.get("season_start_date") or "").strip()
        if not season_start_date: return Response("Season start date is required.",status=400)
    except Exception:
        return Response("Inventory settings must be valid numbers.",status=400)
    con=estimate_db()
    try:
        for key,value in (("starting_gallons",starting),("product_added",product_added),("coverage_per_gallon",coverage),("reorder_level",reorder_level),("season_start_date",season_start_date)):
            if DATABASE_URL:
                con.execute("""INSERT INTO head_office_settings(setting_key,setting_value) VALUES(?,?)
                               ON CONFLICT(setting_key) DO UPDATE SET setting_value=EXCLUDED.setting_value""",(key,str(value)))
            else:
                con.execute("""INSERT INTO head_office_settings(setting_key,setting_value) VALUES(?,?)
                               ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value""",(key,str(value)))
        con.commit()
    finally: con.close()
    return redirect("/head-office/dealers")

@app.post("/head-office/dealers/<dealer_id>/status")
def head_office_dealer_status(dealer_id):
    if not is_head_office(): return Response("Head Office permission required.",status=403)
    action=str(request.form.get("action") or "").strip().lower()
    new_status="disabled" if action=="disable" else "active"
    con=estimate_db()
    try:
        row=con.execute("SELECT dealer_name FROM dealers WHERE id=?",(dealer_id,)).fetchone()
        if not row:return Response("Dealer not found.",status=404)
        if "head office" in str(row["dealer_name"] or "").lower():
            return Response("The Head Office account cannot be disabled here.",status=400)
        con.execute("UPDATE dealers SET status=? WHERE id=?",(new_status,dealer_id));con.commit()
    finally: con.close()
    return redirect("/head-office/dealers")

@app.post("/head-office/dealers/<dealer_id>/password")
def head_office_dealer_password(dealer_id):
    if not is_head_office(): return Response("Head Office permission required.",status=403)
    password=str(request.form.get("password") or "")
    if len(password)<8:return Response("Temporary password must be at least 8 characters.",status=400)
    con=estimate_db()
    try:
        row=con.execute("SELECT id FROM dealers WHERE id=?",(dealer_id,)).fetchone()
        if not row:return Response("Dealer not found.",status=404)
        con.execute("UPDATE dealers SET password_hash=? WHERE id=?",(password_hash(password),dealer_id))
        con.execute("INSERT INTO account_auth_versions(account_type,account_id,version) VALUES('owner',?,1) ON CONFLICT(account_type,account_id) DO UPDATE SET version=account_auth_versions.version+1",(dealer_id,));con.commit()
    finally: con.close()
    return redirect("/head-office/dealers")

@app.post("/head-office/dealers/<dealer_id>/edit")
def head_office_dealer_edit(dealer_id):
    if not is_head_office(): return Response("Head Office permission required.",status=403)
    name=str(request.form.get("dealer_name") or "").strip()
    email=str(request.form.get("email") or "").strip().lower()
    state=str(request.form.get("state") or "").strip().upper()
    lookup_limit_raw=str(request.form.get("lookup_limit") or "250").strip()
    estimate_limit_raw=str(request.form.get("estimate_limit") or "150").strip()
    if not name or not email:return Response("Dealer name and email are required.",status=400)
    try:
        lookup_limit=max(0,int(lookup_limit_raw));estimate_limit=max(0,int(estimate_limit_raw))
    except Exception:return Response("Lookup and estimate limits must be whole numbers.",status=400)
    con=estimate_db()
    try:
        duplicate=con.execute("SELECT id FROM dealers WHERE LOWER(email)=? AND id<>? UNION ALL SELECT id FROM dealer_employees WHERE LOWER(email)=?",(email,dealer_id,email)).fetchone()
        if duplicate:return Response("Another dealer already uses that email.",status=400)
        con.execute("UPDATE dealers SET dealer_name=?,email=?,state=?,lookup_limit=?,estimate_limit=? WHERE id=?",
                    (name,email,state,lookup_limit,estimate_limit,dealer_id));con.commit()
    finally: con.close()
    return redirect("/head-office/dealers")


def is_employee():
    return str(session.get("account_type") or "")=="employee"

def is_dealer_owner():
    return bool(session.get("dealer_id")) and not is_head_office() and not is_employee()

DEALER_EMPLOYEES_HTML=r"""<!doctype html><html><head><meta charset="utf-8"><title>AeriQuote Employees</title>
<style>body{font-family:Arial;background:#f1f5f9;color:#17212b;margin:0}.wrap{max-width:900px;margin:28px auto;padding:0 16px}.card{background:#fff;border-radius:16px;box-shadow:0 8px 28px #0002;padding:22px;margin-bottom:18px}h1,h2{color:#102a43}.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}label{font-weight:800;display:block;margin:5px 0}input{width:100%;box-sizing:border-box;padding:11px;border:1px solid #cbd5ce;border-radius:8px}button,.btn{display:inline-block;border:0;border-radius:9px;padding:11px 15px;background:#1677c8;color:#fff;font-weight:900;text-decoration:none;cursor:pointer}.danger{background:#7a263a}.row{border:1px solid #d9e3ea;border-radius:12px;padding:14px;margin:10px 0}.err{background:#fff0f0;color:#a11;padding:10px;border-radius:8px}.msg{background:#edf7f0;color:#174f2b;padding:10px;border-radius:8px}@media(max-width:650px){.grid{grid-template-columns:1fr}}</style></head>
<body><div class="wrap"><p><a class="btn" href="/">BACK TO ROOF ASSESSMENT</a></p><div class="card"><h1>Manage Employees</h1><p>Employees share your dealership's estimates and usage allowance. They cannot manage dealership settings or other employees.</p>
{% if message %}<div class="msg">{{message}}</div>{% endif %}{% if error %}<div class="err" role="alert">{{error}}</div>{% endif %}
<h2>Create Employee Login</h2><form method="post"><div class="grid"><div><label>Employee Name</label><input name="employee_name" required></div><div><label>Email / Login</label><input name="email" type="email" required></div><div><label>Temporary Password</label><input name="password" type="password" minlength="8" required></div><div style="align-self:end"><button>CREATE EMPLOYEE</button></div></div></form></div>
<div class="card"><h2>Employees</h2>{% if not employees %}<p>No employees yet.</p>{% endif %}{% for e in employees %}<div class="row"><b>{{e.employee_name}}</b> — {{e.email}} — <b>{{e.status|title}}</b><form method="post" action="/dealer-employees/{{e.id}}/status" style="margin-top:10px"><input type="hidden" name="action" value="{{'activate' if e.status=='disabled' else 'disable'}}"><button class="{{'' if e.status=='disabled' else 'danger'}}">{{'ACTIVATE' if e.status=='disabled' else 'DISABLE'}}</button></form></div>{% endfor %}</div></div></body></html>"""

@app.route("/dealer-employees",methods=["GET","POST"])
def dealer_employees():
    if not is_dealer_owner(): return Response("Dealer Owner permission required.",status=403)
    did=str(session["dealer_id"]);message=None;error=None
    if request.method=="POST":
        name=str(request.form.get("employee_name") or "").strip();email=str(request.form.get("email") or "").strip().lower();password=str(request.form.get("password") or "")
        if not name or not email or len(password)<8:error="Employee name, email and a temporary password of at least 8 characters are required."
        elif not valid_dealer_profile_email(email):error="Enter a valid employee login email address, such as name@company.com."
        else:
            con=estimate_db()
            try:
                # All employee creators share one identity lock, including different owners.
                if con.postgres:con.execute("SELECT pg_advisory_xact_lock(?)",(614728194,))
                lock_account(con,did)
                dup1=con.execute("SELECT id FROM dealers WHERE LOWER(email)=?",(email,)).fetchone()
                dup2=con.execute("SELECT id FROM dealer_employees WHERE LOWER(email)=?",(email,)).fetchone()
                if dup1 or dup2:error="That email is already used by another login."
                else:
                    con.execute("INSERT INTO dealer_employees(id,dealer_id,employee_name,email,password_hash,status,created_at) VALUES(?,?,?,?,?,'active',?)",(str(uuid.uuid4()),did,name,email,password_hash(password),time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())));con.commit();message="Employee login created."
            finally:con.close()
    con=estimate_db()
    try:employees=con.execute("SELECT id,employee_name,email,status,created_at FROM dealer_employees WHERE dealer_id=? ORDER BY created_at ASC",(did,)).fetchall()
    finally:con.close()
    return render_template_string(DEALER_EMPLOYEES_HTML,employees=employees,message=message,error=error)

@app.post("/dealer-employees/<employee_id>/status")
def dealer_employee_status(employee_id):
    if not is_dealer_owner(): return Response("Dealer Owner permission required.",status=403)
    action=str(request.form.get("action") or "").lower()
    if action not in {"activate","disable"}:return Response("Choose activate or disable for this employee.",status=400)
    did=str(session["dealer_id"]);new_status="disabled" if action=="disable" else "active"
    con=estimate_db()
    try:
        lock_account(con,did)
        current=con.execute("SELECT status FROM dealer_employees WHERE id=? AND dealer_id=?",(employee_id,did)).fetchone()
        if current and str(current["status"]).lower()!=new_status:
            con.execute("UPDATE dealer_employees SET status=? WHERE id=? AND dealer_id=?",(new_status,employee_id,did))
            if new_status=="disabled":con.execute("INSERT INTO account_auth_versions(account_type,account_id,version) VALUES('employee',?,1) ON CONFLICT(account_type,account_id) DO UPDATE SET version=account_auth_versions.version+1",(employee_id,))
        con.commit()
    finally:con.close()
    return redirect("/dealer-employees")

def is_recovery_test_service():
    """Unrestricted recovery testing only on the explicitly identified Render test service."""
    return (os.environ.get("RENDER_SERVICE_ID", "") == "srv-db5a2g5ckfvc739fui70"
            or os.environ.get("RENDER_EXTERNAL_HOSTNAME", "") == "aeriquote-commercial-test.onrender.com")

def allowance_maintenance_gate():
    # Draft autosaves and reads remain available during a controlled writer pause.
    if request.method=='POST' and request.path in {'/property','/property/accept','/api/estimates','/head-office/credits'}:
        con=estimate_db()
        try:
            if con.execute('SELECT mode FROM allowance_writer_control WHERE id=1').fetchone()['mode']=='paused':
                return jsonify(error='Allowance maintenance is in progress. Your work is unchanged. Retry after maintenance.'),503
        finally:con.close()

def consume_property_lookup(dealer_id, connection=None, operation_id=None):
    con=connection or estimate_db()
    try:
        d=lock_account(con,dealer_id) if connection is None else con.execute("SELECT * FROM dealers WHERE id=?",(dealer_id,)).fetchone()
        if not d or str(d["status"]).lower()!="active":return False,0,0
        cfg=credit_settings(con,dealer_id)
        u=con.execute("SELECT property_lookups FROM dealer_usage WHERE dealer_id=?",(dealer_id,)).fetchone()
        used=int(u["property_lookups"] if u else 0);limit=int(d["lookup_limit"] or 0)
        if is_head_office() or ((is_recovery_test_service() or not DATABASE_URL) and not cfg["complimentary"] and d["plan_code"] not in SUBSCRIPTION_LIMITS):
            return True,used,limit
        allowed,used,limit=consume_credit(con,dealer_id,"lookups",used,limit,operation_id=operation_id)
        if allowed:
            con.execute("INSERT INTO dealer_usage(dealer_id,property_lookups) VALUES(?,1) ON CONFLICT(dealer_id) DO UPDATE SET property_lookups=dealer_usage.property_lookups+1",(dealer_id,))
            if connection is None:con.commit()
        return allowed,used,limit
    finally:
        if connection is None:con.close()


def reset_trial_usage_for_v1196_testing_once():
    con=estimate_db()
    try:
        con.execute("CREATE TABLE IF NOT EXISTS app_migrations (migration_key TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
        key="v11_6_96_trial_test_reset"
        if con.execute("SELECT 1 FROM app_migrations WHERE migration_key=?",(key,)).fetchone():return
        con.execute("UPDATE dealer_usage SET property_lookups=0 WHERE dealer_id IN (SELECT id FROM dealers WHERE lower(COALESCE(plan_code,''))='trial')")
        con.execute("INSERT INTO app_migrations(migration_key,applied_at) VALUES(?,?)",(key,datetime.utcnow().isoformat()))
        con.commit()
    finally:con.close()

reset_trial_usage_for_v1196_testing_once()

@app.before_request
def require_dealer_login():
    path=(request.path or "").rstrip("/") or "/"
    if path in {"/site","/favicon.ico","/pricing","/pricing.html","/trial-signup.html","/roofer-setup.html","/dealer-login","/forgot-password","/reset-password","/setup-dealer","/health","/api/admin/create-dealer","/api/public/signup","/api/public/support","/api/public/support/config","/api/public/support/inbound"} or path.startswith("/static/") or path.startswith("/site/"):return None
    if not session.get("dealer_id"):
        if request.path.startswith("/api/") or request.is_json:return jsonify(error="Dealer login required"),401
        return redirect("/dealer-login")
    con=estimate_db()
    try:
        account=con.execute("SELECT status FROM dealers WHERE id=?",(session["dealer_id"],)).fetchone()
        active=bool(account and str(account["status"]).lower()=="active")
        if active and is_employee():
            employee=con.execute("SELECT status FROM dealer_employees WHERE id=? AND dealer_id=?",(str(session.get("employee_id") or ""),session["dealer_id"])).fetchone()
            active=bool(employee and str(employee["status"]).lower()=="active")
        if active:
            kind="employee" if is_employee() else "owner"
            account_id=str(session.get("employee_id") or "") if is_employee() else session["dealer_id"]
            active=int(session.get("auth_version") or 0)==auth_version(con,kind,account_id)
    finally:con.close()
    if not active:
        session.clear()
        if request.path.startswith("/api/") or request.is_json:return jsonify(error="Account access disabled. Please log in again."),401
        return redirect("/dealer-login")


    # Browsers must not grant or change employee access from a foreign page.
    if request.method=="POST" and (path=="/dealer-employees" or (path.startswith("/dealer-employees/") and path.endswith("/status"))):
        origin=request.headers.get("Origin","").strip().lower()
        host=request.host.lower()
        if request.headers.get("Sec-Fetch-Site","").lower()=="cross-site" or (origin and origin not in {"https://"+host,"http://"+host}):
            return Response("Employee access changes must come from this AeriQuote site. Reload Manage Employees and try again.",status=403)

    # An old browser tab must not save its draft into a different business after re-login.
    expected_account=request.headers.get("X-AeriQuote-Account", "")
    if expected_account and expected_account!=str(session.get("dealer_id") or ""):
        if path.startswith('/api/workspace-drafts'):
            return jsonify(error="This tab's saved account context does not match the current login. No draft was changed. Keep this tab open and sign in to its original account in another tab before retrying.",code="draft_account_context"),409
        return jsonify(error="This page belongs to another business. Keep it open, sign in to the original business in another tab, then retry. Your unsaved entries are still here."),409


# Default-OFF, disposable local QA only; existing authentication runs first.
from subscription_access_qa import register as register_subscription_access_qa
register_subscription_access_qa(app, estimate_db, lambda: ESTIMATE_DB if not DATABASE_URL else None, is_head_office)

app.before_request(allowance_maintenance_gate)

from qa_purchase_screen import register as register_qa_purchase_screen
register_qa_purchase_screen(app, estimate_db, is_employee)

@app.get("/logout")
def logout():
    session.clear()
    return redirect("/")

def vector_pdf_qa_enabled():
    allowed={v.strip() for v in os.environ.get("AERIQUOTE_VECTOR_PDF_QA_IDS", "").split(",") if v.strip()}
    return os.environ.get("AERIQUOTE_VECTOR_PDF_QA", "")=="1" and str(session.get("dealer_id") or "") in allowed

@app.post("/qa-vector-diagram/validate")
def vector_pdf_qa_validate():
    if not vector_pdf_qa_enabled():return jsonify(error="Not found"),404
    from measurement_integrity import snapshot_error
    data=request.get_json(silent=True)
    if not isinstance(data,dict):return jsonify(error="A saved measurement snapshot is required."),400
    error=snapshot_error({"quote":data.get("quote")})
    if error:return jsonify(error=error),400
    return jsonify(ok=True)

@app.get("/qa-vector-diagram.js")
def vector_pdf_qa_script():
    if not vector_pdf_qa_enabled():return "Not found",404
    from pathlib import Path
    import base64
    font=base64.b64encode((Path(__file__).parent/"qa_assets"/"DejaVuSans.ttf").read_bytes()).decode("ascii")
    bold_font=base64.b64encode((Path(__file__).parent/"qa_assets"/"DejaVuSans-Bold.ttf").read_bytes()).decode("ascii")
    notice=(Path(__file__).parent/"qa_assets"/"DejaVu-LICENSE.txt").read_text().replace("*/", "* /")
    response=app.response_class("/* "+notice+" */\nwindow.AQVectorPDFFont="+json.dumps(font)+";\nwindow.AQVectorPDFBoldFont="+json.dumps(bold_font)+";\n"+Path(__file__).with_name("qa_vector_pdf.js").read_text(),mimetype="application/javascript")
    response.headers["Cache-Control"]="private, no-store"
    return response

def manual_roof_qa_enabled():
    """Manual roofing is the customer default; automatic testing stays isolated."""
    allowed={v.strip() for v in os.environ.get("AERIQUOTE_AUTOMEASURE_QA_IDS","").split(",") if v.strip()}
    isolated=request.host.split(":")[0] in ("127.0.0.1","localhost") and not os.environ.get("RENDER_SERVICE_ID") and not os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    automatic_test=isolated and os.environ.get("AERIQUOTE_AUTOMEASURE_QA")=="1" and str(session.get("dealer_id") or "") in allowed
    return not automatic_test

def manual_roof_session(sess):
    return bool(sess and sess.get("mode")=="manual_roof_static")

@app.route("/")
def home():return render_template_string(HTML, VECTOR_PDF_QA_FLAG="1" if vector_pdf_qa_enabled() else "0", MANUAL_ROOF_QA_FLAG="1" if manual_roof_qa_enabled() else "0", ACCOUNT_ID=str(session.get("dealer_id") or ""), DRAFT_PRINCIPAL=__import__("workspace_drafts").principal(session), GOOGLE_MAPS_API_KEY=GOOGLE_MAPS_API_KEY, AERIAL_PROVIDER=AERIAL_PROVIDER, IS_HEAD_OFFICE=is_head_office(), IS_EMPLOYEE=is_employee(), IS_DEALER_OWNER=is_dealer_owner())
@app.get("/mapbox-test")
def mapbox_test():
    address = request.args.get("address", "").strip()
    if not address:
        return jsonify({"error": "Enter an address"}), 400
    try:
        q = urllib.parse.quote(address)
        url = f"https://api.mapbox.com/search/geocode/v6/forward?q={q}&access_token={urllib.parse.quote(MAPBOX_ACCESS_TOKEN)}&country=ca&limit=5"
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
        features = data.get("features", [])
        primary = features[0] if features else None
        warnings = []
        if primary:
            p = primary.get("properties", {})
            ctx = p.get("context", {})
            primary_addr = (ctx.get("address") or {}).get("address_number", "")
            primary_street = (ctx.get("address") or {}).get("street_name", "")
            pcoords = (primary.get("geometry") or {}).get("coordinates", [])

            if primary_addr and len(pcoords) == 2:
                for alt in features[1:]:
                    ap = alt.get("properties", {})
                    actx = ap.get("context", {})
                    alt_addr = (actx.get("address") or {}).get("address_number", "")
                    alt_street = (actx.get("address") or {}).get("street_name", "")
                    acoords = (alt.get("geometry") or {}).get("coordinates", [])

                    if alt_addr == primary_addr and alt_street and alt_street != primary_street and len(acoords) == 2:
                        lat1, lon1 = pcoords[1], pcoords[0]
                        lat2, lon2 = acoords[1], acoords[0]
                        dx = (lon2-lon1) * 111320 * math.cos(math.radians((lat1+lat2)/2))
                        dy = (lat2-lat1) * 110540
                        distance = math.sqrt(dx*dx + dy*dy)

                        if distance <= 250:
                            warnings.append({
                                "address": ap.get("full_address", ""),
                                "distance_m": round(distance)
                            })

        return jsonify({
            "status": "warning" if warnings else "safe",
            "primary": primary,
            "nearby_same_number_alternatives": warnings
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400
def geocode_parts(g):
    parts={"street":"","city":"","province":"","postal":"","country":"","route":"","street_number":""}
    comps=g.get("address_components") or []
    # Component order is not a hierarchy. Prefer the actual municipality over
    # a sublocality regardless of Google's ordering.
    for kind in ("locality","postal_town","administrative_area_level_3","sublocality_level_1","sublocality"):
        found=next((c.get("long_name") for c in comps if kind in (c.get("types") or []) and c.get("long_name")),"")
        if found:parts["city"]=found;break
    for c in comps:
        types=set(c.get("types") or [])
        if "street_number" in types:parts["street_number"]=c.get("long_name") or ""
        if "route" in types:parts["route"]=c.get("long_name") or ""
        if "administrative_area_level_1" in types:parts["province"]=c.get("short_name") or ""
        if "country" in types:parts["country"]=c.get("short_name") or ""
        if "postal_code" in types:parts["postal"]=c.get("long_name") or ""
    parts["street"]=(parts["street_number"]+" "+parts["route"]).strip()
    return parts

def usa_address_variants(address):
    address=str(address or "").strip()
    out=[address] if address else []
    if not address:return out
    first, sep, tail=address.partition(",")
    import re
    m=re.match(r"^\s*(\d+[A-Za-z]?)\s*[-/]\s*(\d+[A-Za-z]?)\s+(.+?)\s*$",first)
    if m:
        unit,street_no,street_rest=m.groups();suffix=(","+tail) if sep else ""
        for q in (f"{street_no} {street_rest} #{unit}{suffix}",f"{street_no} {street_rest} Unit {unit}{suffix}",f"{street_no} {street_rest} {unit}{suffix}"):
            if q not in out:out.append(q)
    return out

def google_geocode_first(key,address,components_country=False,expected_province=""):
    last=None
    canadian={"AB","BC","MB","NB","NL","NS","NT","NU","ON","PE","QC","SK","YT"}
    is_canada=str(expected_province or "").strip().upper() in canadian
    normalized,_=unit_address(address,expected_province)
    queries=list(dict.fromkeys([normalized]+usa_address_variants(address)))
    for q in queries:
        params={"address":q,"key":key}
        if components_country:
            params["components"]="country:CA" if is_canada else "country:US"
            params["region"]="ca" if is_canada else "us"
        gq=urllib.parse.urlencode(params);gs,geo=req_json("https://maps.googleapis.com/maps/api/geocode/json?"+gq);last=(gs,geo,q)
        if gs==200 and geo.get("status")=="OK" and geo.get("results"):return gs,geo,q
    return last if last else (400,{"status":"ZERO_RESULTS"},address)

def _norm_place(v):
    import re
    return re.sub(r"[^a-z0-9]", "", str(v or "").lower())

def _norm_route(value):
    # Exact token equality with conventional street-type/direction abbreviations;
    # never substring equality or removal of locality prefixes such as "Old".
    aliases={"st":"street","rd":"road","ave":"avenue","av":"avenue","blvd":"boulevard","dr":"drive","cres":"crescent","ct":"court","ln":"lane","pl":"place","hwy":"highway","pkwy":"parkway","ter":"terrace","trl":"trail","n":"north","s":"south","e":"east","w":"west","ne":"northeast","nw":"northwest","se":"southeast","sw":"southwest"}
    return " ".join(aliases.get(t,t) for t in re.findall(r"[a-z0-9]+",str(value or "").lower()))

def address_mismatch(expected_city,expected_province,parts,expected_street_number="",expected_address=""):
    parts=parts or {}
    ec=_norm_place(expected_city);ep=_norm_place(expected_province)
    ac=_norm_place(parts.get("city"));ap=_norm_place(parts.get("province"));country=str(parts.get("country") or "").upper()
    # Reviewed municipality relationship only. Old Toronto is the former central
    # municipality within Toronto, Ontario, Canada (City of Toronto archives).
    toronto_pair={ec,ac}<={"toronto","oldtoronto"} and bool(ec and ac) and ep==ap=="on" and country=="CA"
    city_bad=bool(ec and (not ac or (ec!=ac and not toronto_pair)))
    prov_bad=bool(ep and (not ap or ep!=ap))
    en=_norm_place(expected_street_number)
    found_number=parts.get("street_number")
    if not found_number:
        found_match=re.match(r"^\s*(\d+[A-Za-z]?)\b",str(parts.get("street") or ""))
        found_number=found_match[1] if found_match else ""
    number_bad=bool(en and en!=_norm_place(found_number))
    # Query carries street, city, region and country. Keep all of these hard
    # safeguards even when a reviewed municipality alias is accepted.
    route_bad=country_bad=False
    if expected_address:
        first=building_address(expected_address).split(",",1)[0]
        match=re.match(r"^\s*\d+[A-Za-z]?\s+(.+)$",first)
        route_bad=not match or _norm_route(match[1])!=_norm_route(parts.get("route"))
        expected_country="CA" if str(expected_province).upper() in CANADIAN_PROVINCES else "US"
        tail=expected_address.rsplit(",",1)[-1].strip().upper()
        explicit={"CANADA":"CA","CA":"CA","US":"US","USA":"US","UNITED STATES":"US","UNITED STATES OF AMERICA":"US"}.get(tail)
        country_bad=country!=expected_country or bool(explicit and country!=explicit)
    return city_bad or prov_bad or number_bad or route_bad or country_bad

def mismatch_message(expected_city,expected_province,parts):
    found=", ".join(x for x in [(parts or {}).get("street",""),(parts or {}).get("city",""),(parts or {}).get("province",""),(parts or {}).get("country","")] if x) or "a different location"
    return f"Google found {found}, which does not match the entered street number, street, city, province/state or country. Check the address and retry. Existing work is unchanged."

@app.post("/address-preview")
def address_preview():
    d=request.get_json(silent=True) or {};key=str(d.get("key") or "").strip();address=str(d.get("address") or "").strip() # authoritative query is street + city + property province; ZIP code is never sent
    if not key or len(address)<4:return jsonify(error="Address and API key are required."),400
    try:
        expected_city=str(d.get("expected_city") or "").strip();expected_province=str(d.get("expected_province") or "").strip();expected_street_number=str(d.get("expected_street_number") or "").strip()
        normalized_address,unit_number=unit_address(address,expected_province)
        expected_street_number=unit_number or expected_street_number
        gs,geo,_matched_query=google_geocode_first(key,address,components_country=True,expected_province=expected_province)
        if gs!=200 or geo.get("status")!="OK" or not geo.get("results"):return jsonify(error="Address not found"),404
        g=geo["results"][0];parts=geocode_parts(g)
        if address_mismatch(expected_city,expected_province,parts,expected_street_number,address):
            return jsonify(error="ADDRESS DOESN'T MATCH",user_error=mismatch_message(expected_city,expected_province,parts),formatted_address=g.get("formatted_address"),parts=parts),409
        return jsonify(formatted_address=g.get("formatted_address"),parts=parts)
    except Exception as e:return jsonify(error=str(e)),400

def street_view_info(key,address,lat,lng,target_lat,target_lng):
    mq=urllib.parse.urlencode({"location":building_address(address),"key":key,"source":"outdoor"})
    ms,meta=req_json("https://maps.googleapis.com/maps/api/streetview/metadata?"+mq)
    if ms==200 and meta.get("status")=="ZERO_RESULTS" and lat is not None and lng is not None:
        mq=urllib.parse.urlencode({"location":f"{lat},{lng}","key":key,"source":"outdoor"})
        ms,meta=req_json("https://maps.googleapis.com/maps/api/streetview/metadata?"+mq)
    street_url=None;street_date=None
    if ms==200 and meta.get("status")=="OK":
        ploc=meta.get("location") or {};head=bearing(float(ploc.get("lat",lat)),float(ploc.get("lng",lng)),target_lat,target_lng)
        sq=urllib.parse.urlencode({"size":"640x360","pano":meta.get("pano_id"),"heading":round(head,2),"pitch":5,"fov":85,"return_error_code":"true","key":key})
        street_url="https://maps.googleapis.com/maps/api/streetview?"+sq;street_date=meta.get("date")
    return street_url,street_date

def roof_imagery_request(main,minimum=100,maximum=100):
    # Request Google Solar's full supported 100 m aerial radius for every property.
    # This gives the dealer substantially more surrounding imagery for garages,
    # neighboring buildings and larger complexes without changing roof measurements.
    # Large/complex roofs use the centre of the full Google segment extent so an
    # asymmetric condo/X-shaped building is not clipped on one side of the raster.
    base_lat=float(main.get("latitude") or 0);base_lng=float(main.get("longitude") or 0)
    corners=[]
    for seg in main.get("segments") or []:
        box=seg.get("bounding_box") or {}
        sw,ne=box.get("sw"),box.get("ne")
        if sw and ne:
            corners.extend([
                (float(sw.get("latitude",base_lat)),float(sw.get("longitude",base_lng))),
                (float(ne.get("latitude",base_lat)),float(ne.get("longitude",base_lng))),
                (float(sw.get("latitude",base_lat)),float(ne.get("longitude",base_lng))),
                (float(ne.get("latitude",base_lat)),float(sw.get("longitude",base_lng))),
            ])
    if not corners:return base_lat,base_lng,minimum
    minlat=min(x[0] for x in corners);maxlat=max(x[0] for x in corners)
    minlng=min(x[1] for x in corners);maxlng=max(x[1] for x in corners)
    center_lat=(minlat+maxlat)/2.0;center_lng=(minlng+maxlng)/2.0
    def dist_m(lat,lng):
        dy=(lat-center_lat)*111320.0
        dx=(lng-center_lng)*111320.0*math.cos(math.radians(center_lat))
        return math.hypot(dx,dy)
    needed=max(dist_m(lat,lng) for lat,lng in corners)+14.0
    if needed<=minimum:return base_lat,base_lng,minimum
    return center_lat,center_lng,max(minimum,min(maximum,int(math.ceil(needed))))


def exact_pin_display_request(main):
    base_lat=float(main.get("latitude") or 0);base_lng=float(main.get("longitude") or 0)
    corners=[]
    for seg in main.get("segments") or []:
        box=seg.get("bounding_box") or {};sw,ne=box.get("sw"),box.get("ne")
        if sw and ne:
            corners.extend([
                (float(sw.get("latitude",base_lat)),float(sw.get("longitude",base_lng))),
                (float(ne.get("latitude",base_lat)),float(ne.get("longitude",base_lng))),
                (float(sw.get("latitude",base_lat)),float(ne.get("longitude",base_lng))),
                (float(ne.get("latitude",base_lat)),float(sw.get("longitude",base_lng))),
            ])
    if not corners:return base_lat,base_lng,19
    minlat=min(x[0] for x in corners);maxlat=max(x[0] for x in corners)
    minlng=min(x[1] for x in corners);maxlng=max(x[1] for x in corners)
    clat=(minlat+maxlat)/2.0;clng=(minlng+maxlng)/2.0
    height=max(1.0,(maxlat-minlat)*111320.0)
    width=max(1.0,(maxlng-minlng)*111320.0*math.cos(math.radians(clat)))
    # Leave generous room around the roof so the dealer can see the whole building,
    # but never alter the measurement itself.
    desired=max(100.0,width*1.38,height*1.38)
    z=math.floor(math.log2((156543.03392*max(0.2,math.cos(math.radians(clat)))*640.0)/desired))
    zoom=max(16,min(20,int(z)))
    return clat,clng,zoom

def solar_layers(key,lat,lng,radius=34):
    radius=max(20,min(100,int(radius)))
    dq=urllib.parse.urlencode({"location.latitude":lat,"location.longitude":lng,"radiusMeters":radius,"view":"IMAGERY_LAYERS","requiredQuality":"BASE","pixelSizeMeters":0.25,"key":key})
    ds,layers=req_json("https://solar.googleapis.com/v1/dataLayers:get?"+dq)
    if ds!=200:raise ValueError("Solar aerial imagery unavailable for this roof.")
    rgb=layers.get("rgbUrl")
    if not rgb:raise ValueError("Google returned roof data but not RGB aerial imagery.")
    return layers

def create_session(key,lat,lng,street_url=None,mode="solar",layers=None,anchor_lat=None,anchor_lng=None,formatted_address=None):
    token=uuid.uuid4().hex
    SESSIONS[token]={"key":key,"rgb":layers.get("rgbUrl") if layers else None,"rgb_cache":None,"mask":layers.get("maskUrl") if layers else None,"mask_cache":None,"street":street_url,"street_cache":None,"lat":lat,"lng":lng,"created":time.time(),"mode":mode,"fallback_cache":None,"fallback_zoom":19,"anchor_lat":anchor_lat if anchor_lat is not None else lat,"anchor_lng":anchor_lng if anchor_lng is not None else lng,"formatted_address":formatted_address,"dealer_id":str(session.get("dealer_id") or "")}
    for t in list(SESSIONS):
        if time.time()-SESSIONS[t]["created"]>3600:SESSIONS.pop(t,None)
    return token

@app.after_request
def retain_property_session(response):
    if request.path in {'/','/static/workspace_drafts.js'} or request.path.startswith('/api/workspace-drafts'):
        response.headers['Cache-Control']='private, no-store'
    if request.method == "POST" and response.status_code == 200 and request.path in {"/property","/structure","/locate-building"}:
        result = response.get_json(silent=True) or {}
        data = request.get_json(silent=True) or {}
        token = result.get("token") or data.get("token")
        if token:
            try:
                SESSIONS.persist(token)
            except Exception:
                app.logger.warning("Property imagery recovery metadata could not be retained")
    return response

@app.post("/property")
def property_data():
    dealer_id=str(session.get("dealer_id") or "")
    d=request.get_json(silent=True) or {}
    if not isinstance(d,dict):return jsonify(error="Property details must be an object."),400
    operation=str(request.headers.get("Idempotency-Key") or "")
    if operation and not re.fullmatch(r"[A-Za-z0-9_-]{1,128}",operation):return jsonify(error="Invalid lookup identifier."),400
    try:digest=estimate_version(d)
    except (ValueError,TypeError):return jsonify(error="Invalid property details."),400
    con=estimate_db()
    try:
        lock_account(con,dealer_id)
        if d.get('prepare_only'):
            if not operation:return jsonify(error="Lookup identifier required."),400
            old=con.execute("SELECT payload_hash,response_json FROM estimate_save_receipts WHERE dealer_id=? AND operation_id=?",(dealer_id,"prepared:"+operation)).fetchone()
            if old:
                if old["payload_hash"]!=digest:return jsonify(error="This lookup identifier was used for a different property."),409
                prepared=json.loads(old["response_json"])
                if not SESSIONS.get(prepared.get("token")):return jsonify(error="Property preparation expired. Retry Load Property."),410
                return jsonify(prepared)
            # Check current allowance without spending it while images are pending.
            con.execute("SAVEPOINT image_allowance")
            allowed,used,limit=consume_property_lookup(dealer_id,con,operation_id="lookup:"+operation if operation else None)
            con.execute("ROLLBACK TO SAVEPOINT image_allowance");con.execute("RELEASE SAVEPOINT image_allowance")
            if not allowed:
                row=con.execute("SELECT plan_code FROM dealers WHERE id=?",(dealer_id,)).fetchone()
                if row and str(row["plan_code"] or "").lower()=="trial":return jsonify(error="Free trial complete.",code="trial_limit_reached"),403
                return jsonify(error="Property lookup allowance reached."),403
            response=app.make_response(perform_property_lookup(d))
            if response.status_code==200:
                con.execute("INSERT INTO estimate_save_receipts(dealer_id,operation_id,payload_hash,response_json) VALUES(?,?,?,?)",(dealer_id,"prepared:"+operation,digest,json.dumps(response.get_json())))
                con.commit()
            return response
        if operation:
            old=con.execute("SELECT payload_hash,response_json FROM estimate_save_receipts WHERE dealer_id=? AND operation_id=?",(dealer_id,"lookup:"+operation)).fetchone()
            if old:
                if old["payload_hash"]!=digest:return jsonify(error="This lookup identifier was used for a different property."),409
                return jsonify(json.loads(old["response_json"]))
        allowed,used,limit=consume_property_lookup(dealer_id,con,operation_id="lookup:"+operation if operation else None)
        if not allowed:
            row=con.execute("SELECT plan_code FROM dealers WHERE id=?",(dealer_id,)).fetchone()
            if row and str(row["plan_code"] or "").lower()=="trial":return jsonify(error="Free trial complete.",code="trial_limit_reached",user_error="You’ve used all 3 free property measurements included with your AeriQuote trial."),403
            return jsonify(error="Property lookup allowance reached.",user_error=f"Your account has used all {limit} property measurements included with the current plan."),403
        response=app.make_response(perform_property_lookup(d))
        if response.status_code==200:
            if operation:con.execute("INSERT INTO estimate_save_receipts(dealer_id,operation_id,payload_hash,response_json) VALUES(?,?,?,?)",(dealer_id,"lookup:"+operation,digest,json.dumps(response.get_json())))
            con.commit()
        return response
    finally:con.close()

@app.post("/property/accept")
def accept_property():
    dealer_id=str(session.get("dealer_id") or "");d=request.get_json(silent=True) or {}
    if not isinstance(d,dict):return jsonify(error="Invalid property confirmation."),400
    operation=str(d.get("operation_id") or "");token=str(d.get("token") or "")
    con=estimate_db()
    try:
        lock_account(con,dealer_id)
        pending=con.execute("SELECT payload_hash,response_json FROM estimate_save_receipts WHERE dealer_id=? AND operation_id=?",(dealer_id,"prepared:"+operation)).fetchone()
        if not pending:return jsonify(error="Property preparation not found. Retry Load Property."),404
        result=json.loads(pending["response_json"])
        if result.get("token")!=token:return jsonify(error="Property confirmation does not match."),409
        receipt=con.execute("SELECT response_json FROM estimate_save_receipts WHERE dealer_id=? AND operation_id=?",(dealer_id,"lookup:"+operation)).fetchone()
        if receipt:return jsonify(ok=True)
        if not SESSIONS.get(token):return jsonify(error="Property preparation expired. Retry Load Property."),410
        if SESSIONS[token].get("provider")=="mapbox" and d.get("address_pin_confirmed") is not True:
            return jsonify(error="Confirm this address and pin before tracing."),409
        if result.get("requires_address_confirmation") and d.get("address_confirmed") is not True:
            return jsonify(error="Confirm the full Google found address before loading this property."),409
        allowed,used,limit=consume_property_lookup(dealer_id,con,operation_id="lookup:"+operation if operation else None)
        if not allowed:return jsonify(error="Property lookup allowance reached. Existing work is unchanged."),403
        con.execute("INSERT INTO estimate_save_receipts(dealer_id,operation_id,payload_hash,response_json) VALUES(?,?,?,?)",(dealer_id,"lookup:"+operation,pending["payload_hash"],pending["response_json"]))
        con.commit();return jsonify(ok=True)
    finally:con.close()

def mapbox_property_lookup(d):
    from mapbox_provider import verified_address
    address=str(d.get("address") or "").strip()
    if not address or d.get("direct_coordinates"):
        return jsonify(error="Mapbox requires a street address with a verified rooftop pin."),400
    if not d.get("prepare_only"):
        return jsonify(error="Confirm the address, pin and aerial before accepting this property."),409
    industry=d.get("business_type","roofing")
    if not isinstance(industry,str) or industry not in {"roofing","snow","pressure","paving","landscaping","commercial"}:
        return jsonify(error="Unknown measurement industry."),400
    if not MAPBOX_ACCESS_TOKEN:return jsonify(error="Mapbox is not configured."),503
    try:
        query=urllib.parse.urlencode({"q":address,"access_token":MAPBOX_ACCESS_TOKEN,"limit":1,"autocomplete":"false"})
        with urllib.request.urlopen("https://api.mapbox.com/search/geocode/v6/forward?"+query,timeout=12) as upstream:
            result=json.loads(upstream.read(1_000_000))
        features=result.get("features") or []
        if not features:return jsonify(error="Mapbox could not find that address. Check it and retry."),404
        try:formatted,lat,lng=verified_address(features[0],address)
        except ValueError as error:
            return jsonify(error=str(error),matched_address=(features[0].get("properties") or {}).get("full_address")),409
        token=create_session('',lat,lng,mode="manual_roof_static" if industry=="roofing" else "surface_static",formatted_address=formatted)
        SESSIONS[token].update(provider="mapbox",fallback_zoom=19)
        return jsonify(provider="mapbox",token=token,manual_roof_only=industry=="roofing",fallback=True,center={"latitude":lat,"longitude":lng},formatted_address=formatted,parts={},requires_pin_confirmation=True)
    except (OSError,ValueError,TypeError,KeyError):
        return jsonify(error="Mapbox address lookup is unavailable. Existing work is unchanged. Retry."),502

def perform_property_lookup(d):
    key=str(d.get("key") or "").strip();address=str(d.get("address") or "").strip()
    if AERIAL_PROVIDER=="mapbox":return mapbox_property_lookup(d)
    if not key or not address:return jsonify(error="API key and address are required."),400
    industry=d.get("business_type","roofing")
    if not isinstance(industry,str) or industry not in {"roofing","snow","pressure","paving","landscaping","commercial"}:
        return jsonify(error="Unknown measurement industry."),400
    try:
        direct=bool(d.get("direct_coordinates"));g={}
        if direct:
            lat=float(d.get("latitude"));lng=float(d.get("longitude"))
            if not math.isfinite(lat) or not math.isfinite(lng) or abs(lat)>85.05112878 or abs(lng)>180: return jsonify(error="Invalid coordinates.",user_error="Enter valid latitude and longitude coordinates."),400
            formatted=f"{lat:.6f}, {lng:.6f}"
        else:
            expected_city=str(d.get("expected_city") or "").strip();expected_province=str(d.get("expected_province") or "").strip();expected_street_number=str(d.get("expected_street_number") or "").strip()
            normalized_address,unit_number=unit_address(address,expected_province)
            expected_street_number=unit_number or expected_street_number
            gs,geo,_matched_query=google_geocode_first(key,address,components_country=True,expected_province=expected_province)
            if gs!=200 or geo.get("status")!="OK" or not geo.get("results"):return jsonify(error="Google could not find that address. Check the address and try again.",user_error="Google could not find that address. Check the address and try again."),404
            g=geo["results"][0];parts=geocode_parts(g)
            if address_mismatch(expected_city,expected_province,parts,expected_street_number,address):
                return jsonify(error="ADDRESS DOESN'T MATCH",user_error=mismatch_message(expected_city,expected_province,parts),formatted_address=g.get("formatted_address"),parts=parts),409
            if g.get("partial_match") and not d.get("prepare_only"):
                return jsonify(error="Confirm the found address before loading this partial match.",formatted_address=g.get("formatted_address")),409
            loc=g["geometry"]["location"];lat=float(loc["lat"]);lng=float(loc["lng"]);formatted=g.get("formatted_address") or address
        if industry!="roofing" or manual_roof_qa_enabled():
            # Service-area/linear geometry is measured locally over the same Static
            # Maps imagery. Solar roof data is unused in these five workflows.
            street_url,street_date=street_view_info(key,formatted,lat,lng,lat,lng)
            token=create_session(key,lat,lng,street_url=street_url,mode="manual_roof_static" if industry=="roofing" else "surface_static",anchor_lat=lat,anchor_lng=lng,formatted_address=formatted)
            if direct:SESSIONS[token].update({"exact_pin":True,"display_lat":lat,"display_lng":lng,"display_zoom":19})
            return jsonify(token=token,manual_roof_only=industry=="roofing",fallback=True,fallback_aerial="static",center={"latitude":lat,"longitude":lng},formatted_address=formatted,parts=geocode_parts(g),street_date=street_date,exact_pin_display=bool(direct),requires_address_confirmation=bool(g.get("partial_match")))
        try:
            main=building(key,lat,lng)
        except SolarBuildingNotFound:
            # Building Insights can be unavailable even when Google still has usable
            # Solar aerial data for the area. Try that existing Solar Data Layers API
            # first so the dealer can trace manually without another Google product.
            street_url,street_date=street_view_info(key,formatted,lat,lng,lat,lng)
            try:
                fallback_layers=solar_layers(key,lat,lng)
                token=create_session(key,lat,lng,street_url=street_url,mode="manual_solar",layers=fallback_layers,anchor_lat=lat,anchor_lng=lng,formatted_address=formatted)
                return jsonify(token=token,fallback=True,fallback_aerial="solar",center={"latitude":lat,"longitude":lng},formatted_address=formatted,parts=geocode_parts(g),street_date=street_date,requires_address_confirmation=bool(g.get("partial_match")))
            except Exception:
                # Last display fallback only. If Maps Static is not enabled the UI
                # gives a clear setup message instead of exposing a raw Google error.
                token=create_session(key,lat,lng,street_url=street_url,mode="manual_static",layers=None,anchor_lat=lat,anchor_lng=lng,formatted_address=formatted)
                return jsonify(token=token,fallback=True,fallback_aerial="static",center={"latitude":lat,"longitude":lng},formatted_address=formatted,parts=geocode_parts(g),street_date=street_date,requires_address_confirmation=bool(g.get("partial_match")))
        img_lat,img_lng,img_radius=roof_imagery_request(main);layers=solar_layers(key,img_lat,img_lng,img_radius)
        street_url,street_date=street_view_info(key,formatted,lat,lng,lat,lng)
        token=create_session(key,main["latitude"],main["longitude"],street_url=street_url,mode="solar",layers=layers,anchor_lat=lat,anchor_lng=lng,formatted_address=formatted)
        if direct:
            dl,do,dz=exact_pin_display_request(main)
            SESSIONS[token].update({"exact_pin":True,"display_lat":dl,"display_lng":do,"display_zoom":dz,"fallback_zoom":dz})
        return jsonify(token=token,main=main,formatted_address=formatted,parts=geocode_parts(g),street_date=street_date,anchor={"latitude":lat,"longitude":lng},exact_pin_display=bool(direct),requires_address_confirmation=bool(g.get("partial_match")))
    except Exception as e:
        return jsonify(error=str(e),user_error="Google could not complete the automatic roof measurement for this property. Try again, or use the manual fallback if offered."),400

@app.post("/structure")
def structure():
    d=request.get_json(silent=True) or {};sess=SESSIONS.get(str(d.get("token") or ""))
    if not sess or sess.get("dealer_id")!=str(session.get("dealer_id") or ""):return jsonify(error="Property session expired. Reload the property.",user_error="Property session expired. Reload the property."),400
    if manual_roof_session(sess) or manual_roof_qa_enabled():return jsonify(error="Automatic roofing is unavailable in the manual roofing workflow."),409
    try:
        roof=building(sess["key"],float(d["latitude"]),float(d["longitude"]))
        # Fetch imagery only when the client has accepted this distinct building.
        mask_id=uuid.uuid4().hex
        sess.setdefault("structure_masks",{})[mask_id]={"roof":roof,"mask_cache":None}
        roof["mask_url"]="/structure-mask/"+str(d["token"])+"/"+mask_id
        return jsonify(roof)
    except SolarBuildingNotFound:return jsonify(error="Building not found",user_error="Google could not automatically match that roof. Click closer to the centre or add it manually."),404
    except Exception as e:return jsonify(error=str(e),user_error="Google could not measure that roof right now."),400

@app.get("/structure-mask/<token>/<mask_id>")
def structure_mask(token,mask_id):
    sess=SESSIONS.get(token)
    if not sess or sess.get("dealer_id")!=str(session.get("dealer_id") or ""):
        return jsonify(code="AQ-MASK-SESSION"),404
    if manual_roof_session(sess) or manual_roof_qa_enabled():return jsonify(code="AQ-MANUAL-ONLY"),409
    item=(sess.get("structure_masks") or {}).get(mask_id)
    if not item:return jsonify(code="AQ-MASK-REFERENCE"),404
    stage="LAYERS"
    try:
        if item["mask_cache"] is None:
            lat,lng,radius=roof_imagery_request(item["roof"])
            layers=solar_layers(sess["key"],lat,lng,radius)
            url=layers.get("maskUrl")
            if not url:return jsonify(code="AQ-MASK-NOT-PROVIDED"),404
            sep="&" if "?" in url else "?"
            stage="DOWNLOAD"
            item["mask_cache"]=req_bytes(url+sep+"key="+urllib.parse.quote(sess["key"]))
        ct,body=item["mask_cache"]
        return Response(body,content_type=ct)
    except Exception as e:
        upstream=getattr(e,"code",None)
        suffix="-"+str(upstream) if isinstance(upstream,int) else ""
        return jsonify(code="AQ-MASK-"+stage+suffix),503

@app.post("/locate-building")
def locate_building():
    d=request.get_json(silent=True) or {};sess=SESSIONS.get(str(d.get("token") or ""))
    if not sess:return jsonify(error="Property session expired.",user_error="Property session expired. Reload the property."),400
    if manual_roof_session(sess) or manual_roof_qa_enabled():return jsonify(error="Automatic roofing is unavailable in the manual roofing workflow."),409
    try:
        lat=float(d["latitude"]);lng=float(d["longitude"]);main=building(sess["key"],lat,lng);img_lat,img_lng,img_radius=roof_imagery_request(main);layers=solar_layers(sess["key"],img_lat,img_lng,img_radius)
        street_url,street_date=street_view_info(sess["key"],sess.get("formatted_address") or "",sess.get("anchor_lat"),sess.get("anchor_lng"),sess.get("anchor_lat"),sess.get("anchor_lng"))
        sess.update({"rgb":layers.get("rgbUrl"),"rgb_cache":None,"mask":layers.get("maskUrl"),"mask_cache":None,"lat":main["latitude"],"lng":main["longitude"],"mode":"solar","street":street_url,"street_cache":None})
        return jsonify(main=main,street_date=street_date)
    except SolarBuildingNotFound:return jsonify(error="Building not found",user_error="Google still cannot automatically measure this roof. Try a nearby point or choose manual measurement."),404
    except Exception as e:return jsonify(error=str(e),user_error="Google could not complete automatic measurement at that point. You can use manual measurement."),400

@app.post("/manual-report-map/<token>")
def manual_report_map(token):
    """Report-only image: Google satellite + dealer manual outline baked together."""
    sess=SESSIONS.get(token)
    if not sess:return Response("Session expired",status=404)
    try:
        data=request.get_json(silent=True) or {};planes=data.get("planes") or []
        clean=[]
        for plane in planes:
            pts=[]
            for v in (plane or []):
                try:
                    lat=float(v.get("lat"));lng=float(v.get("lng"))
                    if -90<=lat<=90 and -180<=lng<=180:pts.append((lat,lng))
                except Exception:pass
            if len(pts)>=3:clean.append(pts)
        if not clean:return Response("No valid manual roof outline",status=400)
        allpts=[pt for plane in clean for pt in plane]
        def merc_xy(lat,lng):
            lat=max(-85.05112878,min(85.05112878,lat))
            x=(lng+180.0)/360.0
            siny=math.sin(math.radians(lat))
            y=0.5-math.log((1+siny)/(1-siny))/(4*math.pi)
            return x,y
        xy=[merc_xy(lat,lng) for lat,lng in allpts]
        xs=[q[0] for q in xy];ys=[q[1] for q in xy]
        xmin,xmax=min(xs),max(xs);ymin,ymax=min(ys),max(ys)
        dx=max(xmax-xmin,1e-9);dy=max(ymax-ymin,1e-9)
        fit_w=640*0.55;fit_h=420*0.55
        zx=math.log(fit_w/(256.0*dx),2);zy=math.log(fit_h/(256.0*dy),2)
        zoom=max(19,min(21,int(math.floor(min(zx,zy)))))
        cx=(xmin+xmax)/2.0;cy=(ymin+ymax)/2.0
        center_lng=cx*360.0-180.0
        n=math.pi-2.0*math.pi*cy
        center_lat=math.degrees(math.atan(math.sinh(n)))
        params=[("size","640x420"),("scale","2"),("center",f"{center_lat:.7f},{center_lng:.7f}"),("zoom",str(zoom)),("maptype","satellite"),("format","png")]
        for pts in clean:
            path="color:0xd97706ff|weight:4|fillcolor:0xf59e0b22|"+"|".join(f"{lat:.7f},{lng:.7f}" for lat,lng in pts+[pts[0]])
            params.append(("path",path))
        params.append(("key",sess["key"]))
        url="https://maps.googleapis.com/maps/api/staticmap?"+urllib.parse.urlencode(params)
        headers={"User-Agent":"ShingleGuardRoofAssessment/2.0","Referer":request.host_url,"Origin":request.host_url.rstrip("/")}
        req=urllib.request.Request(url,headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=15) as rr:ct=rr.headers.get("Content-Type","image/png");body=rr.read()
        except urllib.error.HTTPError as he:
            raw=he.read().decode("utf-8","replace")[:1200].replace(sess.get("key") or "","[API KEY REDACTED]")
            raise ValueError(f"Google Maps Static HTTP {he.code}: {raw}")
        return Response(body,content_type=ct,headers={"X-AeriQuote-Map-View":json.dumps({"latitude":round(center_lat,7),"longitude":round(center_lng,7),"zoom":zoom,"width":640,"height":420})})
    except Exception as e:
        return Response(str(e).replace(sess.get("key") or "","[API KEY REDACTED]"),status=400,content_type="text/plain; charset=utf-8")



@app.post("/saved-estimate-report-map")
def saved_estimate_report_map():
    """Rebuild a saved estimate aerial from its frozen roof geometry without a live measurement session."""
    key=GOOGLE_MAPS_API_KEY
    if not key:return Response("Google Maps API key is not configured",status=500)
    try:
        data=request.get_json(silent=True) or {};incoming=data.get("roofs") or [];roofs=[]
        for roof in incoming:
            kind=str((roof or {}).get("kind") or "house");pts=[]
            for v in ((roof or {}).get("points") or []):
                try:
                    lat=float(v.get("lat"));lng=float(v.get("lng"))
                    if -90<=lat<=90 and -180<=lng<=180:pts.append((lat,lng))
                except Exception:pass
            if len(pts)>=(2 if kind=="linear" else 3):roofs.append((kind,pts))
        if not roofs:return Response("No valid saved roof outline",status=400)
        allpts=[pt for _,pts in roofs for pt in pts]
        def merc_xy(lat,lng):
            lat=max(-85.05112878,min(85.05112878,lat));x=(lng+180.0)/360.0;siny=math.sin(math.radians(lat));y=0.5-math.log((1+siny)/(1-siny))/(4*math.pi);return x,y
        xy=[merc_xy(lat,lng) for lat,lng in allpts];xs=[q[0] for q in xy];ys=[q[1] for q in xy]
        xmin,xmax=min(xs),max(xs);ymin,ymax=min(ys),max(ys);dx=max(xmax-xmin,1e-9);dy=max(ymax-ymin,1e-9)
        zx=math.log((640*.58)/(256.0*dx),2);zy=math.log((420*.58)/(256.0*dy),2);zoom=max(1 if any(kind in ("area","linear") for kind,_ in roofs) else 18,min(21,int(math.floor(min(zx,zy)))))
        cx=(xmin+xmax)/2.0;cy=(ymin+ymax)/2.0;center_lng=cx*360.0-180.0;n=math.pi-2.0*math.pi*cy;center_lat=math.degrees(math.atan(math.sinh(n)))
        params=[("size","640x420"),("scale","2"),("center",f"{center_lat:.7f},{center_lng:.7f}"),("zoom",str(zoom)),("maptype","satellite"),("format","png")]
        for kind,pts in roofs:
            if kind=="garage":color,fill="0x18a7a0ff","0x18a7a018"
            elif kind=="manual":color,fill="0xd97706ff","0xf59e0b20"
            elif kind=="area":color,fill="0x7357b8ff","0x7357b820"
            elif kind=="linear":color,fill="0x0f8f83ff","0x00000000"
            else:color,fill="0x2d6cdfff","0x2d6cdf16"
            closed=pts if kind=="linear" else pts+[pts[0]];params.append(("path",f"color:{color}|weight:4|fillcolor:{fill}|"+"|".join(f"{a:.7f},{b:.7f}" for a,b in closed)))
        params.append(("key",key));url="https://maps.googleapis.com/maps/api/staticmap?"+urllib.parse.urlencode(params)
        headers={"User-Agent":"ShingleGuardRoofAssessment/2.0","Referer":request.host_url,"Origin":request.host_url.rstrip("/")};req=urllib.request.Request(url,headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=15) as rr:ct=rr.headers.get("Content-Type","image/png");body=rr.read()
        except urllib.error.HTTPError as he:
            raw=he.read().decode("utf-8","replace")[:1200].replace(key,"[API KEY REDACTED]");raise ValueError(f"Google Maps Static HTTP {he.code}: {raw}")
        return Response(body,content_type=ct,headers={"X-AeriQuote-Map-View":json.dumps({"latitude":round(center_lat,7),"longitude":round(center_lng,7),"zoom":zoom,"width":640,"height":420})})
    except Exception as e:return Response(str(e).replace(key,"[API KEY REDACTED]"),status=400,content_type="text/plain; charset=utf-8")


@app.post("/exact-pin-report-map/<token>")
def exact_pin_report_map(token):
    """Exact-pin customer estimate: stable Google satellite image + saved roof outlines baked together."""
    sess=SESSIONS.get(token)
    if not sess:return Response("Session expired",status=404)
    try:
        data=request.get_json(silent=True) or {}
        incoming=data.get("roofs") or []
        roofs=[]
        for roof in incoming:
            kind=str((roof or {}).get("kind") or "house")
            pts=[]
            for v in ((roof or {}).get("points") or []):
                try:
                    lat=float(v.get("lat"));lng=float(v.get("lng"))
                    if -90<=lat<=90 and -180<=lng<=180:pts.append((lat,lng))
                except Exception:
                    pass
            if len(pts)>=3:roofs.append((kind,pts))
        if not roofs:return Response("No valid exact-pin roof outline",status=400)

        # Use the exact same center/zoom that passed on the dealer screen.
        lat=float(sess.get("display_lat",sess.get("lat")))
        lng=float(sess.get("display_lng",sess.get("lng")))
        zoom=int(sess.get("display_zoom",19))

        params=[
            ("size","640x420"),
            ("scale","2"),
            ("center",f"{lat:.7f},{lng:.7f}"),
            ("zoom",str(zoom)),
            ("maptype","satellite"),
            ("format","png"),
        ]

        for kind,pts in roofs:
            if kind=="garage":
                color="0x18a7a0ff";fill="0x18a7a018"
            elif kind=="manual":
                color="0xd97706ff";fill="0xf59e0b20"
            else:
                color="0x2d6cdfff";fill="0x2d6cdf16"
            closed=pts+[pts[0]]
            path=f"color:{color}|weight:4|fillcolor:{fill}|"+"|".join(f"{a:.7f},{b:.7f}" for a,b in closed)
            params.append(("path",path))

        params.append(("key",sess["key"]))
        url="https://maps.googleapis.com/maps/api/staticmap?"+urllib.parse.urlencode(params)
        headers={"User-Agent":"ShingleGuardRoofAssessment/2.0","Referer":request.host_url,"Origin":request.host_url.rstrip("/")}
        req=urllib.request.Request(url,headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=15) as rr:
                ct=rr.headers.get("Content-Type","image/png")
                body=rr.read()
        except urllib.error.HTTPError as he:
            raw=he.read().decode("utf-8","replace")[:1200].replace(sess.get("key") or "","[API KEY REDACTED]")
            raise ValueError(f"Google Maps Static HTTP {he.code}: {raw}")
        return Response(body,content_type=ct)
    except Exception as e:
        return Response(str(e).replace(sess.get("key") or "","[API KEY REDACTED]"),status=400,content_type="text/plain; charset=utf-8")


@app.get("/api/estimate-storage-status")
def estimate_storage_status():
    dealer_id=str(session.get("dealer_id") or "")
    con=estimate_db()
    try:
        estimate_count=con.execute("SELECT COUNT(*) AS total FROM estimates WHERE dealer_id=?",(dealer_id,)).fetchone()["total"]
        revision_count=con.execute("SELECT COUNT(*) AS total FROM estimate_revisions WHERE dealer_id=?",(dealer_id,)).fetchone()["total"]
    finally:
        con.close()
    return jsonify(
        persistent=bool(DATABASE_URL),
        estimate_count=estimate_count,
        revision_count=revision_count
    )

from measurement_integrity import snapshot_error
from pricing_integrity import pricing_error

def estimate_pricing_error(payload):
    if not isinstance(payload,dict):return "Estimate details must be an object."
    def valid(value,maximum=float("inf")):
        try:return value is not None and not isinstance(value,bool) and str(value).strip()!="" and math.isfinite(float(value)) and 0<=float(value)<=maximum
        except (TypeError,ValueError,OverflowError):return False
    for key in ("total_price","total_area","extra_service_amount","linear_feet","area_sqft","amount_paid"):
        if key in payload and not valid(payload[key]):return "Enter valid non-negative estimate amounts and quantities."
    pricing=payload.get("pricing",{})
    if not isinstance(pricing,dict):return "Pricing details must be an object."
    for key in ("subtotal","price","extraAmount","taxBase","gstAmt","pstAmt","total"):
        if key in pricing and not valid(pricing[key]):return "Enter valid non-negative prices and taxes."
    for key in ("gst","pst"):
        if key in pricing and not valid(pricing[key],100):return "Tax percentages must be from 0 to 100."
    if pricing.get("mode")=="discount" and not valid(pricing.get("disc"),100):return "Discount must be from 0 to 100%."
    # Reject inconsistent client snapshots before creating revisions or consuming credit.
    if "total_price" in payload and "total" in pricing and abs(float(payload["total_price"])-float(pricing["total"]))>0.005:
        return "Estimate total does not match its pricing details. Recreate the estimate."
    if all(key in pricing for key in ("taxBase","gstAmt","pstAmt","total")):
        if abs(sum(float(pricing[key]) for key in ("taxBase","gstAmt","pstAmt"))-float(pricing["total"]))>0.005:
            return "Estimate total does not match its tax breakdown. Recreate the estimate."
    if "quote" in payload:
        quote=payload["quote"]
        if not isinstance(quote,dict):return "Measurement snapshot must be an object."
        for key in ("linearFeet","areaSqFt"):
            if key in quote and not valid(quote[key]):return "Enter valid measurement quantities."
        areas=quote.get("commercialAreas",[])
        if not isinstance(areas,list):return "Saved service areas must be a list."
        for area in areas:
            if not isinstance(area,dict) or not valid(area.get("sqft")) or not valid(area.get("rate")):
                return "Every saved service area needs a valid quantity and rate."
            if float(area["sqft"])<=0:return "Finish saving or cancel the unfinished service area before creating an estimate."
        roofs=quote.get("structures",[])
        if not isinstance(roofs,list) or any(not isinstance(roof,dict) for roof in roofs):return "Saved roofs must be a list."
        if any(roof.get("needs_remeasure") or roof.get("automatic_review_warning") for roof in roofs):
            return "Remeasure the flagged roof before saving an estimate."
    return snapshot_error(payload) or pricing_error(payload)

def estimate_version(payload):
    if isinstance(payload,str):payload=json.loads(payload)
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()

def draft_identity():
    import workspace_drafts as drafts
    dealer=str(session.get("dealer_id") or "")
    user=drafts.principal(session)
    if request.headers.get("X-AeriQuote-Principal") != user:
        raise drafts.DraftError("This tab's user context does not match the current login. Keep it open and sign in to its original user account in another tab before retrying.",409,code="draft_user_context")
    origin=request.headers.get("Origin","").lower()
    if request.headers.get("Sec-Fetch-Site","")=="cross-site" or (origin and origin not in {"https://"+request.host.lower(),"http://"+request.host.lower()}):
        raise drafts.DraftError("Recovery requests must come from this AeriQuote page.",403)
    return dealer,user

@app.route("/api/workspace-drafts",methods=["GET"])
@app.route("/api/workspace-drafts/<draft_id>",methods=["GET","PUT","DELETE"])
def workspace_draft_api(draft_id=None):
    import workspace_drafts as drafts
    con=estimate_db()
    try:
        dealer,user=draft_identity()
        lock_account(con,dealer)
        drafts.purge(con)
        if draft_id is None:
            rows=con.execute("SELECT draft_id,version,expires_at FROM workspace_drafts WHERE dealer_id=? AND principal=? AND closed=0 ORDER BY expires_at DESC",(dealer,user)).fetchall()
            con.commit()
            return jsonify(drafts=[dict(r) for r in rows],server_time=time.time())
        if request.method=="DELETE":
            cleanup=request.get_json(silent=True) or {}
            if not isinstance(cleanup,dict):return jsonify(error="Recovery cleanup must be an object."),400
            expected=cleanup.get('version')
            if isinstance(expected,bool) or not isinstance(expected,int) or expected<0:
                return jsonify(error="This older page cannot safely discard without the saved draft version. Keep this tab open. Open a fresh AeriQuote tab for the same account to review and discard the draft there.",code="draft_version_required"),428
            row=con.execute('SELECT version,closed FROM workspace_drafts WHERE dealer_id=? AND principal=? AND draft_id=?',(dealer,user,draft_id)).fetchone()
            if not row:
                if cleanup.get('intent')!='discard':return jsonify(deleted=False)
                return jsonify(error="This recovery draft is unavailable or its 24-hour window ended. Current work is unchanged.",code="draft_unavailable"),404
            if cleanup.get('intent')=='discard' and row['closed'] and row['version']==expected:
                con.commit();return jsonify(deleted=True,already_closed=True)
            deleted=drafts.close(con,dealer,user,draft_id,expected_version=cleanup.get("version"))
            if not deleted and cleanup.get('intent')=='discard':
                return jsonify(error="This draft changed after it was listed. The newer saved work was kept. Review the refreshed draft before retrying Discard.",code="draft_changed"),409
            con.commit();return jsonify(deleted=deleted)
        if request.method=="GET":
            row=drafts.load(con,dealer,user,draft_id)
            con.commit()
            return jsonify(draft_id=draft_id,version=row["version"],expires_at=row["expires_at"],workspace=json.loads(row["payload"]))
        body=request.get_json(silent=True)
        if not isinstance(body,dict):return jsonify(error="Recovery workspace must be an object."),400
        # Only metadata from a previously accepted, owned imagery session is retained.
        token=body.get("workspace",{}).get("sessionToken") if isinstance(body.get("workspace"),dict) else None
        source=SESSIONS.get(token) if isinstance(token,str) else None
        metadata=None
        if source:
            from property_sessions import FIELDS,image_url
            metadata={k:source[k] for k in FIELDS if k in source}
            for k in ("rgb","mask","street"):
                if k in metadata:metadata[k]=image_url(metadata[k])
        result=drafts.put(con,dealer,user,draft_id,body.get("version"),body.get("workspace"),metadata)
        con.commit();return jsonify(result)
    except drafts.DraftError as e:
        return jsonify(error=str(e),code=e.code),e.status
    finally:con.close()

@app.post("/api/workspace-drafts/<draft_id>/save-status")
def workspace_draft_save_status(draft_id):
    import workspace_drafts as drafts
    con=estimate_db()
    try:
        dealer,user=draft_identity();drafts.validate_id(draft_id)
        operation=(request.get_json(silent=True) or {}).get("operation_id")
        row=con.execute("SELECT save_operation FROM workspace_drafts WHERE dealer_id=? AND principal=? AND draft_id=? AND expires_at>? AND closed=1",(dealer,user,draft_id,time.time())).fetchone()
        if not row or not operation or row["save_operation"]!=operation:return jsonify(saved=False)
        receipt=con.execute("SELECT response_json FROM estimate_save_receipts WHERE dealer_id=? AND operation_id=?",(dealer,operation)).fetchone()
        return jsonify(saved=bool(receipt),result=json.loads(receipt["response_json"]) if receipt else None)
    except drafts.DraftError as e:return jsonify(error=str(e)),e.status
    finally:con.close()

@app.post("/api/workspace-drafts/<draft_id>/imagery-session")
def workspace_draft_imagery(draft_id):
    import workspace_drafts as drafts
    con=estimate_db()
    try:
        dealer,user=draft_identity()
        row=drafts.load(con,dealer,user,draft_id)
        metadata=json.loads(row["property_metadata"] or "null")
        if not metadata:return jsonify(error="Property imagery was not acknowledged before interruption. Your measurements are retained; retry the original property loading step."),409
        provider=metadata.get("provider", "google")
        credential=MAPBOX_ACCESS_TOKEN if provider=="mapbox" else GOOGLE_MAPS_API_KEY
        if not credential:return jsonify(error="Imagery is unavailable. Your draft remains available; retry later."),503
        token=uuid.uuid4().hex
        metadata.update(key=GOOGLE_MAPS_API_KEY if provider=="google" else "",created=time.time(),dealer_id=dealer)
        from property_sessions import CACHES,image_url
        metadata.update({k:None for k in CACHES})
        if metadata.get("street"):metadata["street"]=image_url(metadata["street"],GOOGLE_MAPS_API_KEY)
        metadata["structure_masks"]={}
        SESSIONS[token]=metadata;SESSIONS.persist(token)
        return jsonify(token=token,provider=provider,center={"latitude":metadata["lat"],"longitude":metadata["lng"]})
    except drafts.DraftError as e:return jsonify(error=str(e)),e.status
    finally:con.close()

@app.route("/api/estimates", methods=["GET","POST"])
def estimate_history_api():
    dealer_id=str(session.get("dealer_id") or "")
    con=estimate_db()
    try:
        if request.method=="POST":
            lock_account(con,dealer_id)
            recovery_id=request.headers.get("X-AeriQuote-Draft")
            if recovery_id:
                import workspace_drafts as drafts
                try:
                    _,recovery_user=draft_identity();drafts.validate_id(recovery_id)
                except drafts.DraftError as e:return jsonify(error=str(e)),e.status
            d=request.get_json(silent=True) or {}
            pricing_error=estimate_pricing_error(d)
            if pricing_error:return jsonify(error=pricing_error),400
            address=str(d.get("address") or "").strip()
            if not address:return jsonify(error="Property address is required"),400
            operation=str(request.headers.get("Idempotency-Key") or "")
            if operation and not re.fullmatch(r"[A-Za-z0-9_-]{1,128}",operation):return jsonify(error="Invalid save request identifier."),400
            try:request_hash=estimate_version(d)
            except (ValueError,TypeError):return jsonify(error="Estimate contains invalid values."),400
            if operation:
                receipt=con.execute("SELECT payload_hash,response_json FROM estimate_save_receipts WHERE dealer_id=? AND operation_id=?",(dealer_id,operation)).fetchone()
                if receipt:
                    if receipt["payload_hash"]!=request_hash:return jsonify(error="This save identifier was already used for different estimate details."),409
                    if recovery_id:
                        drafts.close(con,dealer_id,recovery_user,recovery_id,operation=operation);con.commit()
                    return jsonify(json.loads(receipt["response_json"]))
            def finish_save(result):
                if recovery_id:drafts.close(con,dealer_id,recovery_user,recovery_id,operation=operation)
                result["version"]=estimate_version(d)
                if operation:con.execute("INSERT INTO estimate_save_receipts(dealer_id,operation_id,payload_hash,response_json) VALUES(?,?,?,?)",(dealer_id,operation,request_hash,json.dumps(result)))
                con.commit()
                return jsonify(result)
            # One active estimate per property PER DEALER. Another dealer can quote
            # the same address without seeing or overwriting this dealer's record.
            norm=lambda v:" ".join(str(v or "").lower().replace(","," ").replace("."," ").split())
            address_key=norm(address)
            existing=None
            for row in con.execute("SELECT * FROM estimates WHERE dealer_id=? ORDER BY created_at DESC",(dealer_id,)).fetchall():
                if norm(row["address"])==address_key:
                    existing=row;break
            if existing:
                base=request.headers.get("If-Match")
                if base and base!=estimate_version(existing["payload"]):return jsonify(error="This estimate changed in another session. Your measurements are still here. Reopen the latest saved version before saving changes."),409
                # Pricing edits do not own booking/payment fields; dedicated endpoints do.
                saved=json.loads(existing["payload"])
                for key in ("job_status","scheduled_date","completion_date","amount_paid"):
                    if key in saved:d[key]=saved[key]
                if estimate_version(d)==estimate_version(saved):
                    return finish_save(dict(id=existing["id"],created_at=existing["created_at"],updated=False))
            if not existing:
                cfg=credit_settings(con,dealer_id)
                dealer_row=con.execute("SELECT estimate_limit,plan_code FROM dealers WHERE id=?",(dealer_id,)).fetchone()
                paid_plan=bool(dealer_row and dealer_row["plan_code"] in SUBSCRIPTION_LIMITS)
                if not is_head_office() and (paid_plan or cfg["complimentary"] or not is_recovery_test_service()):
                    estimate_limit=int(dealer_row["estimate_limit"] or 0) if dealer_row else 0
                    estimate_used=int(con.execute("SELECT COUNT(*) AS estimate_count FROM estimates WHERE dealer_id=?",(dealer_id,)).fetchone()["estimate_count"])
                    allowed,_,_=consume_credit(con,dealer_id,"estimates",estimate_used,estimate_limit,operation_id="save:"+operation if operation else None)
                    if not allowed:
                        return jsonify(error="Estimate allowance reached.",user_error="Your estimate allowance is used. Contact AeriQuote support for extra credits."),403

            created=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())
            payload_json=json.dumps(d,separators=(",",":"))
            vals=(str(d.get("customer_name") or ""),str(d.get("customer_phone") or ""),str(d.get("customer_email") or ""),address,float(d.get("total_area") or 0),float(d.get("total_price") or 0),payload_json)
            if existing:
                con.execute("INSERT INTO estimate_revisions(revision_id,estimate_id,revised_at,customer_name,customer_phone,customer_email,address,total_area,total_price,payload,dealer_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(str(uuid.uuid4()),existing["id"],created,existing["customer_name"],existing["customer_phone"],existing["customer_email"],existing["address"],existing["total_area"],existing["total_price"],existing["payload"],dealer_id))
                con.execute("UPDATE estimates SET created_at=?,customer_name=?,customer_phone=?,customer_email=?,address=?,total_area=?,total_price=?,payload=? WHERE id=? AND dealer_id=?",(created,*vals,existing["id"],dealer_id))
                return finish_save(dict(id=existing["id"],created_at=created,updated=True))
            eid=str(uuid.uuid4())
            con.execute("INSERT INTO estimates(id,created_at,customer_name,customer_phone,customer_email,address,total_area,total_price,payload,dealer_id) VALUES(?,?,?,?,?,?,?,?,?,?)",(eid,created,*vals,dealer_id))
            return finish_save(dict(id=eid,created_at=created,updated=False))
        q=str(request.args.get("q") or "").strip()
        if q:
            like="%"+q+"%"; rows=con.execute("SELECT id,created_at,customer_name,customer_phone,customer_email,address,total_area,total_price FROM estimates WHERE dealer_id=? AND (customer_name LIKE ? OR customer_phone LIKE ? OR customer_email LIKE ? OR address LIKE ?) ORDER BY created_at DESC LIMIT 100",(dealer_id,like,like,like,like)).fetchall()
        else: rows=con.execute("SELECT id,created_at,customer_name,customer_phone,customer_email,address,total_area,total_price FROM estimates WHERE dealer_id=? ORDER BY created_at DESC LIMIT 50",(dealer_id,)).fetchall()
        result=[]
        for r in rows:
            item=dict(r)
            try:
                full=con.execute("SELECT payload FROM estimates WHERE id=? AND dealer_id=?",(item["id"],dealer_id)).fetchone()
                payload=json.loads(full["payload"] or "{}") if full else {}
            except Exception:
                payload={}
            item["job_status"]=str(payload.get("job_status") or "Estimate")
            item["scheduled_date"]=str(payload.get("scheduled_date") or "")
            item["completion_date"]=str(payload.get("completion_date") or "")
            try: item["amount_paid"]=float(payload.get("amount_paid") or 0)
            except Exception: item["amount_paid"]=0.0
            result.append(item)
        return jsonify(result)
    finally: con.close()

@app.post("/api/estimates/<estimate_id>/completion-date")
def estimate_completion_date(estimate_id):
    dealer_id=session.get("dealer_id")
    if not dealer_id:return jsonify(ok=False,error="Login required."),401
    d=request.get_json(silent=True) or {};completion_date=str(d.get("completion_date") or "").strip()
    if completion_date:
        try: time.strptime(completion_date,"%Y-%m-%d")
        except ValueError:return jsonify(ok=False,error="Invalid completion date."),400
    con=estimate_db()
    try:
        lock_account(con,str(dealer_id))
        row=con.execute("SELECT payload FROM estimates WHERE id=? AND dealer_id=?",(estimate_id,dealer_id)).fetchone()
        if not row:return jsonify(ok=False,error="Estimate not found."),404
        raw=row["payload"] if hasattr(row,"keys") else row[0];payload=json.loads(raw or "{}");payload["completion_date"]=completion_date
        con.execute("UPDATE estimates SET payload=? WHERE id=? AND dealer_id=?",(json.dumps(payload),estimate_id,dealer_id));con.commit()
        return jsonify(ok=True,completion_date=completion_date)
    finally: con.close()

@app.post("/api/estimates/<estimate_id>/amount-paid")
def estimate_amount_paid(estimate_id):
    dealer_id=session.get("dealer_id")
    if not dealer_id:return jsonify(ok=False,error="Login required."),401
    d=request.get_json(silent=True) or {}
    try:
        raw_amount=d.get("amount_paid",0)
        amount_paid=float(raw_amount)
        if isinstance(raw_amount,bool) or not math.isfinite(amount_paid) or amount_paid<0:raise ValueError()
    except (TypeError,ValueError,OverflowError):return jsonify(ok=False,error="Invalid amount."),400
    con=estimate_db()
    try:
        lock_account(con,str(dealer_id))
        row=con.execute("SELECT payload FROM estimates WHERE id=? AND dealer_id=?",(estimate_id,dealer_id)).fetchone()
        if not row:return jsonify(ok=False,error="Estimate not found."),404
        raw=row["payload"] if hasattr(row,"keys") else row[0];payload=json.loads(raw or "{}");payload["amount_paid"]=amount_paid
        con.execute("UPDATE estimates SET payload=? WHERE id=? AND dealer_id=?",(json.dumps(payload),estimate_id,dealer_id));con.commit()
        return jsonify(ok=True,amount_paid=amount_paid)
    finally: con.close()

@app.post("/api/estimates/<estimate_id>/scheduled-date")
def estimate_scheduled_date(estimate_id):
    dealer_id=session.get("dealer_id")
    if not dealer_id:return jsonify(ok=False,error="Login required."),401
    d=request.get_json(silent=True) or {}
    scheduled_date=str(d.get("scheduled_date") or "").strip()
    if scheduled_date:
        try: time.strptime(scheduled_date,"%Y-%m-%d")
        except ValueError:return jsonify(ok=False,error="Invalid scheduled date."),400
    con=estimate_db()
    try:
        lock_account(con,str(dealer_id))
        row=con.execute("SELECT payload FROM estimates WHERE id=? AND dealer_id=?",(estimate_id,dealer_id)).fetchone()
        if not row:return jsonify(ok=False,error="Estimate not found."),404
        raw=row["payload"] if hasattr(row,"keys") else row[0]
        payload=json.loads(raw or "{}")
        payload["scheduled_date"]=scheduled_date
        con.execute("UPDATE estimates SET payload=? WHERE id=? AND dealer_id=?",(json.dumps(payload),estimate_id,dealer_id))
        con.commit()
        return jsonify(ok=True,scheduled_date=scheduled_date)
    finally:
        con.close()

@app.post("/api/estimates/<estimate_id>/status")
def estimate_job_status(estimate_id):
    dealer_id=str(session.get("dealer_id") or "")
    d=request.get_json(silent=True) or {}
    job_status=str(d.get("job_status") or "").strip()
    if job_status not in ("Estimate","Booked","Completed"):
        return jsonify(error="Invalid job status"),400
    con=estimate_db()
    try:
        lock_account(con,str(dealer_id))
        row=con.execute("SELECT payload FROM estimates WHERE id=? AND dealer_id=?",(estimate_id,dealer_id)).fetchone()
        if not row:return jsonify(error="Estimate not found"),404
        try: payload=json.loads(row["payload"] or "{}")
        except Exception: payload={}
        payload["job_status"]=job_status
        con.execute("UPDATE estimates SET payload=? WHERE id=? AND dealer_id=?",(json.dumps(payload,separators=(",",":")),estimate_id,dealer_id))
        con.commit()
        return jsonify(ok=True,job_status=job_status)
    finally:
        con.close()

@app.get("/api/estimates/<estimate_id>")
def estimate_history_one(estimate_id):
    dealer_id=str(session.get("dealer_id") or "")
    con=estimate_db()
    try: row=con.execute("SELECT * FROM estimates WHERE id=? AND dealer_id=?",(estimate_id,dealer_id)).fetchone()
    finally: con.close()
    if not row:return jsonify(error="Estimate not found"),404
    d=dict(row);d["payload"]=json.loads(d.get("payload") or "{}");return jsonify(d)

@app.get("/api/estimates/<estimate_id>/versions")
def estimate_history_versions(estimate_id):
    dealer_id=str(session.get("dealer_id") or "")
    con=estimate_db()
    try:
        current=con.execute("SELECT * FROM estimates WHERE id=? AND dealer_id=?",(estimate_id,dealer_id)).fetchone()
        if not current:return jsonify(error="Estimate not found"),404
        revisions=con.execute("SELECT * FROM estimate_revisions WHERE estimate_id=? AND dealer_id=? ORDER BY revised_at ASC",(estimate_id,dealer_id)).fetchall()
        def unpack(row,date_field):
            d=dict(row)
            d["payload"]=json.loads(d.get("payload") or "{}")
            d["saved_at"]=d.get(date_field) or ""
            return d
        return jsonify(current=unpack(current,"created_at"),revisions=[unpack(r,"revised_at") for r in revisions])
    finally:
        con.close()

@app.post("/api/estimates/<estimate_id>/editing-session")
def saved_estimate_editing_session(estimate_id):
    from saved_estimate_edit import measurement_bounds
    versions=estimate_history_versions(estimate_id)
    if isinstance(versions,tuple):return versions
    data=versions.get_json()
    try:
        index=(request.get_json(silent=True) or {}).get("version_index",-1)
        if isinstance(index,bool) or not isinstance(index,int) or index < -1:raise ValueError("Invalid saved version")
        version=data["current"] if index==-1 else data["revisions"][index]
        payload=version.get("payload") or {};bounds=measurement_bounds(payload)
    except (ValueError,IndexError,KeyError) as e:return jsonify(error=str(e) or "Saved version unavailable"),400
    provider=AERIAL_PROVIDER
    credential=MAPBOX_ACCESS_TOKEN if provider=="mapbox" else GOOGLE_MAPS_API_KEY
    if not credential:return jsonify(error="The selected aerial provider is unavailable"),503
    lat=(bounds[0][0]+bounds[1][0])/2;lng=(bounds[0][1]+bounds[1][1])/2
    token=uuid.uuid4().hex
    SESSIONS[token]={"provider":provider,"fallback_zoom":19 if provider=="mapbox" else 20,"key":GOOGLE_MAPS_API_KEY if provider=="google" else "","dealer_id":str(session.get("dealer_id") or ""),"created":time.time(),"mode":"manual_roof_static" if manual_roof_qa_enabled() or (payload.get("quote") or {}).get("manualRoofWorkflow") else "fallback","lat":lat,"lng":lng,"anchor_lat":lat,"anchor_lng":lng,"formatted_address":payload.get("address") or "","rgb":None,"mask":None,"street":None,"rgb_cache":None,"mask_cache":None,"street_cache":None,"fallback_cache":None,"exact_pin_cache":None,"structure_masks":{}}
    SESSIONS.persist(token)
    return jsonify(token=token,provider=provider,version=estimate_version(data["current"]["payload"]),center={"latitude":lat,"longitude":lng},bounds=bounds,job_details={k:(data["current"].get("payload") or {}).get(k) for k in ("job_status","scheduled_date","completion_date","amount_paid")})

@app.get("/exact-pin-meta/<token>")
def exact_pin_meta(token):
    sess=SESSIONS.get(token)
    if not sess:return jsonify(error="Session expired"),404
    return jsonify(latitude=sess.get("display_lat",sess.get("lat")),longitude=sess.get("display_lng",sess.get("lng")),zoom=sess.get("display_zoom",19),width=640,height=640)

@app.get("/exact-pin-map/<token>")
def exact_pin_map(token):
    sess=SESSIONS.get(token)
    if not sess:return Response("Session expired",status=404)
    try:
        if sess.get("exact_pin_cache") is None:
            lat=sess.get("display_lat",sess.get("lat"));lng=sess.get("display_lng",sess.get("lng"));zoom=sess.get("display_zoom",19)
            q=urllib.parse.urlencode({"center":f"{lat},{lng}","zoom":zoom,"size":"640x640","maptype":"satellite","format":"png","key":sess["key"]})
            url="https://maps.googleapis.com/maps/api/staticmap?"+q
            headers={"User-Agent":"ShingleGuardRoofAssessment/2.0","Referer":request.host_url,"Origin":request.host_url.rstrip("/")}
            req=urllib.request.Request(url,headers=headers)
            try:
                with urllib.request.urlopen(req,timeout=12) as r:ct=r.headers.get("Content-Type","image/png");body=r.read()
            except urllib.error.HTTPError as he:
                raw=he.read().decode("utf-8","replace")[:1200].replace(sess.get("key") or "","[API KEY REDACTED]")
                raise ValueError(f"Google Maps Static HTTP {he.code}: {raw}")
            sess["exact_pin_cache"]=(ct,body)
        ct,body=sess["exact_pin_cache"];return Response(body,content_type=ct)
    except Exception as e:
        return Response(str(e).replace(sess.get("key") or "","[API KEY REDACTED]"),status=400,content_type="text/plain; charset=utf-8")

@app.get("/wide-aerial/<token>")
def wide_aerial(token):
    sess=SESSIONS.get(token)
    if not sess:return Response("Session expired",status=404)
    try:
        lat=float(request.args.get("lat",sess.get("lat")));lng=float(request.args.get("lng",sess.get("lng")))
        zoom=int(float(request.args.get("zoom",17)))
        if not (-90<=lat<=90 and -180<=lng<=180):raise ValueError("Invalid map centre")
        zoom=max(15,min(20,zoom))
        q=urllib.parse.urlencode({"center":f"{lat},{lng}","zoom":zoom,"size":"640x640","scale":"2","maptype":"satellite","format":"png","key":sess["key"]})
        url="https://maps.googleapis.com/maps/api/staticmap?"+q
        headers={"User-Agent":"ShingleGuardRoofAssessment/2.0","Referer":request.host_url,"Origin":request.host_url.rstrip("/")}
        req=urllib.request.Request(url,headers=headers)
        with urllib.request.urlopen(req,timeout=12) as r:
            ct=r.headers.get("Content-Type","image/png");body=r.read()
        return Response(body,content_type=ct)
    except Exception as e:
        return Response(str(e).replace(sess.get("key") or "","[API KEY REDACTED]"),status=400,content_type="text/plain; charset=utf-8")

@app.post("/mapbox-aerial/<token>/commit")
def commit_mapbox_aerial(token):
    sess=SESSIONS.get(token)
    if not sess or sess.get("dealer_id")!=str(session.get("dealer_id") or ""):
        return jsonify(error="Property session expired."),404
    zoom=(request.get_json(silent=True) or {}).get("zoom")
    if sess.get("provider")!="mapbox" or type(zoom) is not int or zoom not in sess.get("mapbox_frames",{}):
        return jsonify(error="Load the replacement aerial before accepting it."),409
    sess["fallback_zoom"]=zoom;sess["fallback_cache"]=sess["mapbox_frames"][zoom]
    SESSIONS.persist(token)
    return jsonify(ok=True)

@app.get("/fallback-meta/<token>")
def fallback_meta(token):
    sess=SESSIONS.get(token)
    if not sess:return jsonify(error="Session expired"),404
    return jsonify(latitude=sess.get("lat"),longitude=sess.get("lng"),zoom=sess.get("fallback_zoom",19 if sess.get("provider")=="mapbox" else 20),width=640,height=640,provider=sess.get("provider","google"),tile_size=512 if sess.get("provider")=="mapbox" else 256)

@app.get("/fallback-map/<token>")
def fallback_map(token):
    sess=SESSIONS.get(token)
    if not sess:return Response("Session expired",status=404)
    if sess.get("provider")=="mapbox":
        if not MAPBOX_ACCESS_TOKEN:return Response("Mapbox imagery unavailable",status=503)
        try:zoom=int(request.args.get("zoom",sess.get("fallback_zoom",19)))
        except (ValueError,TypeError):return Response("Invalid aerial zoom",status=400)
        if not 15<=zoom<=19:return Response("Invalid aerial zoom",status=400)
        frames=sess.setdefault("mapbox_frames",{})
        if zoom not in frames:
            url=f'https://api.mapbox.com/styles/v1/mapbox/satellite-v9/static/{sess["lng"]},{sess["lat"]},{zoom},0,0/640x640?'
            try:
                with urllib.request.urlopen(url+urllib.parse.urlencode({"access_token":MAPBOX_ACCESS_TOKEN}),timeout=12) as upstream:
                    content_type=upstream.headers.get_content_type();body=upstream.read(5_000_001)
                if not content_type.startswith("image/") or not 0<len(body)<=5_000_000:
                    return Response("Mapbox imagery unavailable",status=502)
            except (OSError,ValueError):return Response("Mapbox imagery unavailable",status=502)
            frames[zoom]=(content_type,body)
        content_type,body=frames[zoom]
        return Response(body,content_type=content_type)
    try:
        if sess.get("fallback_cache") is None:
            q=urllib.parse.urlencode({"center":f'{sess["lat"]},{sess["lng"]}',"zoom":sess.get("fallback_zoom",20),"size":"640x640","scale":"2","maptype":"satellite","format":"png","key":sess["key"]})
            url="https://maps.googleapis.com/maps/api/staticmap?"+q
            # Static Maps keys may be restricted by HTTP referrer. Because this app is
            # local, send the same localhost referrer the browser uses instead of a
            # bare server-side request. This does not change any roof-measurement code.
            headers={"User-Agent":"ShingleGuardRoofAssessment/2.0","Referer":request.host_url,"Origin":request.host_url.rstrip("/")}
            req=urllib.request.Request(url,headers=headers)
            try:
                with urllib.request.urlopen(req,timeout=12) as r:
                    ct=r.headers.get("Content-Type","image/png");body=r.read()
            except urllib.error.HTTPError as he:
                raw=he.read().decode("utf-8","replace")[:1200]
                raw=raw.replace(sess.get("key") or "","[API KEY REDACTED]")
                raise ValueError(f"Google Maps Static HTTP {he.code}: {raw}")
            sess["fallback_cache"]=(ct,body)
        ct,body=sess["fallback_cache"];return Response(body,content_type=ct)
    except Exception as e:
        msg=str(e).replace(sess.get("key") or "","[API KEY REDACTED]")
        return Response(msg,status=400,content_type="text/plain; charset=utf-8")

@app.get("/rgb/<token>")
def rgb(token):
    s=SESSIONS.get(token)
    if not s:return Response("Session expired",status=404)
    if manual_roof_session(s):return Response("Manual roofing imagery unavailable. Retry the aerial image; Solar recovery is disabled.",status=409)
    try:
        if s["rgb_cache"] is None:
            if not s.get("rgb") and s.get("mode")=="surface_static":
                # Retain the pre-existing customer-report RGB fallback, but pay for
                # Solar only when that fallback is actually requested. Never use
                # these roof quantities to price a surface measurement.
                try:
                    main=building(s["key"],s["lat"],s["lng"])
                    lat,lng,radius=roof_imagery_request(main)
                    layers=solar_layers(s["key"],lat,lng,radius)
                    s.update(lat=main["latitude"],lng=main["longitude"])
                except SolarBuildingNotFound:
                    layers=solar_layers(s["key"],s["lat"],s["lng"])
                s.update(rgb=layers.get("rgbUrl"),mask=layers.get("maskUrl"),mode="solar")
                SESSIONS.persist(token)
            if not s.get("rgb"): return Response("Solar aerial unavailable",status=404)
            url=s["rgb"];sep="&" if "?" in url else "?"
            try:
                ct,body=req_bytes(url+sep+"key="+urllib.parse.quote(s["key"]),timeout=12,retries=0)
            except Exception:
                # If Google's first signed RGB URL stalls/fails, ask Solar for a new,
                # lighter aerial layer and try once more. This prevents 60–90 second waits.
                dq=urllib.parse.urlencode({"location.latitude":s.get("lat"),"location.longitude":s.get("lng"),
                                           "radiusMeters":30,"view":"IMAGERY_LAYERS","requiredQuality":"BASE",
                                           "pixelSizeMeters":0.5,"key":s["key"]})
                ds,layers=req_json("https://solar.googleapis.com/v1/dataLayers:get?"+dq)
                if ds!=200 or not layers.get("rgbUrl"):
                    raise ValueError("Google aerial imagery unavailable for this property right now.")
                s["rgb"]=layers["rgbUrl"]
                # Keep the original higher-detail mask if it already exists; only use a
                # fallback mask when none was returned in the first request.
                if not s.get("mask") and layers.get("maskUrl"): s["mask"]=layers.get("maskUrl")
                url=s["rgb"];sep="&" if "?" in url else "?"
                ct,body=req_bytes(url+sep+"key="+urllib.parse.quote(s["key"]),timeout=12,retries=0)
            s["rgb_cache"]=(ct,body)
        ct,body=s["rgb_cache"];return Response(body,content_type=ct)
    except Exception as e:return Response(str(e),status=400)

@app.get("/mask/<token>")
def mask(token):
    s=SESSIONS.get(token)
    if not s or not s.get("mask"):return Response("Roof mask unavailable",status=404)
    if manual_roof_session(s):return Response("Manual roofing imagery unavailable. Retry the aerial image; Solar recovery is disabled.",status=409)
    try:
        if s["mask_cache"] is None:
            url=s["mask"];sep="&" if "?" in url else "?"
            ct,body=req_bytes(url+sep+"key="+urllib.parse.quote(s["key"]))
            s["mask_cache"]=(ct,body)
        ct,body=s["mask_cache"];return Response(body,content_type=ct)
    except Exception as e:return Response(str(e),status=400)

@app.get("/street/<token>")
def street(token):
    s=SESSIONS.get(token)
    if not s or not s.get("street"):return Response("Street View unavailable",status=404)
    try:
        if s["street_cache"] is None:s["street_cache"]=req_bytes(s["street"])
        ct,body=s["street_cache"];return Response(body,content_type=ct)
    except Exception:return Response("Street View image could not be loaded. Please retry; your saved work is unchanged.",status=503)

if __name__=="__main__":
    port=5102
    threading.Timer(1.15,lambda:webbrowser.open(f"http://127.0.0.1:{port}")).start()
    print("AERIQUOTE ROOF MEASUREMENT & ESTIMATE")
    print(f"Opening Chrome at http://127.0.0.1:{port}")
    print("Leave this window open while testing.")
    app.run(host="127.0.0.1",port=port,debug=False,use_reloader=False)


