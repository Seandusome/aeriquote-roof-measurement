import re
# SHINGLEXTRA U.S. V1 — based on protected V11.6.64G measurement engine — isolated from successful V11.6.64E dealer view
from flask import Flask, request, jsonify, Response, render_template_string, session, redirect
import urllib.request, urllib.parse, urllib.error
import json, webbrowser, threading, uuid, math, time, os, sqlite3, hmac, hashlib, secrets
try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg=None
    dict_row=None

app = Flask(__name__, static_folder=".", static_url_path="/static")
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)

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
SESSIONS = {}
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_API_KEY", "") or os.environ.get("GOOGLE_MAPS_API_KEY", "")
MAPBOX_ACCESS_TOKEN = os.environ.get("MAPBOX_ACCESS_TOKEN", "")
# Persistent estimate storage:
# - Render production uses PostgreSQL whenever DATABASE_URL is present.
# - Local development falls back to SQLite.
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
ESTIMATE_DB = os.environ.get("ESTIMATE_DB_PATH", os.path.join(os.path.dirname(__file__), "shinglextra_estimates.db"))

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

def estimate_db():
    if DATABASE_URL:
        if psycopg is None:
            raise RuntimeError("DATABASE_URL is configured but psycopg is not installed. Add psycopg[binary] to requirements.txt.")
        raw=psycopg.connect(DATABASE_URL, row_factory=dict_row)
        con=DBCompat(raw, True)
    else:
        raw=sqlite3.connect(ESTIMATE_DB)
        raw.row_factory=sqlite3.Row
        con=DBCompat(raw, False)
    con.execute("""CREATE TABLE IF NOT EXISTS estimates (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, customer_name TEXT, customer_phone TEXT, customer_email TEXT, address TEXT NOT NULL, total_area REAL, total_price REAL, payload TEXT NOT NULL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS estimate_revisions (revision_id TEXT PRIMARY KEY, estimate_id TEXT NOT NULL, revised_at TEXT NOT NULL, customer_name TEXT, customer_phone TEXT, customer_email TEXT, address TEXT NOT NULL, total_area REAL, total_price REAL, payload TEXT NOT NULL)""")
    con.execute("CREATE INDEX IF NOT EXISTS idx_estimates_address ON estimates(address)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_estimates_customer ON estimates(customer_name)")
    con.execute("""CREATE TABLE IF NOT EXISTS dealers (id TEXT PRIMARY KEY, dealer_name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, state TEXT, status TEXT NOT NULL DEFAULT 'active', lookup_limit INTEGER NOT NULL DEFAULT 250, estimate_limit INTEGER NOT NULL DEFAULT 150, created_at TEXT NOT NULL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS dealer_employees (id TEXT PRIMARY KEY, dealer_id TEXT NOT NULL, employee_name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL)""")
    con.execute("CREATE INDEX IF NOT EXISTS idx_dealer_employees_dealer ON dealer_employees(dealer_id)")
    con.execute("""CREATE TABLE IF NOT EXISTS dealer_usage (dealer_id TEXT PRIMARY KEY, property_lookups INTEGER NOT NULL DEFAULT 0)""")
    con.execute("""CREATE TABLE IF NOT EXISTS head_office_settings (setting_key TEXT PRIMARY KEY, setting_value TEXT NOT NULL)""")
    # Dealer ownership migration. Existing installations pre-date dealer separation.
    # PostgreSQL must use IF NOT EXISTS: catching a duplicate-column error without a
    # rollback leaves the whole transaction aborted and breaks Previous Estimates.
    if DATABASE_URL:
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
    con.commit()
    return con
HTML = r"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>AeriQuote Roof Measurement & Estimate</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
:root{--green:#1456c0;--green2:#0b1739;--orange:#e35b21;--dark:#111827;--gold:#e35b21;--bg:#f3f6fa;--line:#d8e0eb;--muted:#5f6b7a;--house:#1456c0;--garage:#1596d2;--manual:#e35b21;--warn:#fff4e8}
*{box-sizing:border-box} body{font-family:Arial,sans-serif;background:var(--bg);margin:0;color:var(--dark)}
.wrap{max-width:1560px;margin:14px auto;padding:0 12px}.card{background:#fff;border-radius:16px;box-shadow:0 8px 28px rgba(0,0,0,.08);overflow:hidden}
.header{padding:14px 20px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;gap:14px;align-items:center}.brand{display:flex;align-items:center;gap:13px}.brand img.aeriquote-main-logo{width:390px;height:auto;max-height:92px;object-fit:contain;object-position:left center}.aeri-wordmark{font-size:34px;font-weight:900;letter-spacing:-1.5px;line-height:1}.aeri-wordmark .aeri{color:#090d18}.aeri-wordmark .quote{color:#1456c0}.aeri-wordmark .pointer{color:#e35b21;font-size:22px;vertical-align:5px;margin-left:-7px}.aeri-tag{font-size:10px;font-weight:900;letter-spacing:3.2px;color:#111827;margin-top:6px}.brand h1{margin:0;color:var(--green2);font-size:27px}.sub{color:var(--muted);margin-top:3px}.badge{background:#edf7f0;color:var(--green2);border:1px solid #cfe5d5;padding:8px 11px;border-radius:999px;font-weight:800;font-size:12px}
.setup{padding:13px 20px;background:#fbfcfb;border-bottom:1px solid var(--line)}.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}.grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px} label{font-weight:800;display:block;margin:4px 0 5px} input,select,textarea{width:100%;padding:10px 11px;border:1px solid #cbd5ce;border-radius:8px;font-size:14px;font-family:inherit}textarea{min-height:70px;resize:vertical}.small{font-size:12px;color:var(--muted)}
.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}button{background:var(--green);color:#fff;border:0;border-radius:9px;padding:10px 14px;font-weight:800;cursor:pointer}button.secondary{background:#fff;color:var(--green);border:1px solid var(--green)}button.orange{background:var(--manual)}button.ghost{background:#f3f6f4;color:var(--dark);border:1px solid var(--line)}button.danger{background:#fff;color:#a12622;border:1px solid #d8a7a4}button:disabled{opacity:.45;cursor:not-allowed}
.status{padding:9px 20px;font-weight:800}.ok{color:var(--green)}.error{color:#a12622}.warn{color:#8a5a08}
.workflow{padding:9px 20px;border-bottom:1px solid var(--line);background:#edf7f0;font-size:13px}.workflow b{color:var(--green2)}
.job-summary-bar{display:grid;grid-template-columns:2fr .55fr .8fr .8fr;gap:0;margin:0 20px 12px;border:1px solid #cfe0d3;border-radius:11px;background:#f7fbf8;overflow:hidden}.job-summary-bar>div{padding:9px 12px;border-right:1px solid #dbe7de;min-width:0}.job-summary-bar>div:last-child{border-right:0}.job-summary-bar b{display:block;margin-top:2px;color:var(--green2);font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.js-label{font-size:10px;font-weight:900;letter-spacing:.55px;color:var(--muted)}
.main{display:grid;grid-template-columns:2.15fr .72fr;gap:13px;padding:0 20px 20px}.panel{border:1px solid var(--line);border-radius:12px;overflow:hidden;background:#fff}.ptitle{padding:11px 13px;background:#f8faf9;border-bottom:1px solid var(--line);font-weight:800}
#map{height:760px;background:#e9efeb}.mapwrap{position:relative;overflow:hidden}.loading{position:absolute;z-index:1200;left:14px;top:14px;background:rgba(255,255,255,.95);border:1px solid var(--line);padding:9px 12px;border-radius:8px;font-weight:800;box-shadow:0 2px 8px #0002}.tracebanner{display:none;position:absolute;z-index:1200;left:50%;top:14px;transform:translateX(-50%);background:#fff7ed;border:2px solid var(--manual);color:#8a5208;padding:8px 13px;border-radius:8px;font-weight:800}.leaflet-zoom-animated{transition-duration:.22s!important}.leaflet-fade-anim .leaflet-tile{transition:opacity .12s linear!important}
.manualbox{background:#fff7ed;border-bottom:1px solid #efd4aa}.manualbox summary{cursor:pointer;padding:10px 12px;font-weight:800;color:#8a5208}.manualrow{padding:0 12px 10px;display:flex;gap:8px;align-items:end;flex-wrap:wrap}.pitch{width:120px}.point-label{background:#fff;border:2px solid var(--manual);border-radius:50%;width:25px;height:25px;text-align:center;padding-top:3px;color:#8a5208;font-size:12px;font-weight:800}.manual-label{background:#fff;border:2px solid var(--manual);border-radius:6px;padding:3px 6px;color:#8a5208;font-size:12px;font-weight:800;white-space:nowrap}.seg-label{background:#fff;border:2px solid var(--gold);border-radius:6px;padding:3px 6px;font-weight:800;color:#5d4613;box-shadow:0 1px 4px #0003;white-space:nowrap;font-size:12px}
.side{padding:12px}.street{width:100%;height:190px;object-fit:cover;background:#e8ece9;border-radius:9px;border:1px solid var(--line)}.section{margin-top:12px}.section h3{margin:0 0 7px;font-size:15px}.metric-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.metric{padding:9px;border:1px solid var(--line);border-radius:9px;background:#f8faf9}.metric b{display:block;font-size:18px;color:var(--green2);margin-top:2px}.structure{border:1px solid var(--line);border-radius:9px;padding:9px;margin:7px 0}.structure-head{display:flex;justify-content:space-between;gap:8px}.dot{width:9px;height:9px;border-radius:50%;display:inline-block;margin-right:6px}.house-dot{background:var(--house)}.garage-dot{background:var(--garage)}.manual-dot{background:var(--manual)}.calc{display:grid;grid-template-columns:1fr auto;gap:6px;font-size:13px}.calc div:nth-child(even){font-weight:800}.estimate{background:#f7faf8;border:1px solid var(--line);border-radius:9px;padding:10px;margin-top:9px}.line{display:flex;justify-content:space-between;gap:8px;padding:6px 0;border-bottom:1px solid #e5ece7}.line:last-child{border-bottom:0}.grand{font-size:17px;color:var(--green2);font-weight:900}.total{padding:11px;background:#edf7f0;border:1px solid #cde5d4;border-radius:9px;font-weight:800;margin-top:9px}.warning{padding:9px;background:var(--warn);border:1px solid #e5ca7e;border-radius:8px;color:#79520c;margin-top:8px;font-size:12px}.good{padding:9px;background:#edf7f0;border:1px solid #cde5d4;border-radius:8px;color:var(--green2);margin-top:8px;font-size:12px}.fallbackbox{display:none;background:#fff8e8;border:1px solid #e7c56f;border-radius:10px;padding:11px 12px;margin:10px 0;color:#6f4b08}.fallbackbox b{color:#5e3e05}
.dealer-settings{margin-top:10px;border:1px solid var(--line);border-radius:10px;background:#fff}.dealer-settings summary{cursor:pointer;padding:10px 12px;font-weight:800;color:var(--green2)}.settingsbody{padding:0 12px 12px}.savedmsg{padding:8px;border-radius:8px;background:#edf7f0;border:1px solid #cde5d4;color:var(--green2);font-size:12px;margin-top:8px}.usage{font-size:12px;color:var(--muted);margin-top:6px}
.dealer-branding-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:7px;margin-top:7px}.dealer-logo-tools{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:8px}.dealer-logo-preview{width:180px;height:64px;object-fit:contain;border:1px solid var(--line);border-radius:8px;background:#fff;padding:6px}.dealer-logo-note{font-size:11px;color:var(--muted);max-width:440px}.dealer-logo-clear{padding:7px 10px}.reportHead .dealerLogo{width:auto!important;height:auto!important;max-width:100%;max-height:120px;object-fit:contain;justify-self:center;transform:none;transform-origin:center center}.reportHead .dealerLogo.defaultShingleXtraLogo{transform:none}.reportDealerSub{font-size:12px;color:#5b675f;text-align:center;margin-top:4px}.dealerContactCompact{margin-top:7px;font-size:13px;line-height:1.45}.dealerContactCompact .contactSep{opacity:.65;padding:0 5px}
.historyModal{display:none;position:fixed;inset:0;background:#0008;z-index:6500;padding:30px;overflow:auto}.historyModal.open{display:block}.historyBox{max-width:1000px;margin:auto;background:#fff;border-radius:14px;padding:18px;box-shadow:0 16px 50px #0005}.historyHead{display:flex;justify-content:space-between;align-items:center;gap:12px}.historyResults{margin-top:12px}.historyRow{display:grid;grid-template-columns:1.2fr 1.8fr .8fr .7fr auto;gap:10px;align-items:center;padding:10px;border-bottom:1px solid var(--line);font-size:13px}.historyRow:hover{background:#f8faf9}.jobStatusSelect{width:auto;min-width:112px;padding:7px 8px;font-size:12px;font-weight:800}.scheduledDateInput{width:145px;padding:7px 8px;font-size:12px}.historyMoneyInput{width:105px;padding:7px 8px;font-size:12px}.historyFinance{font-size:11px;line-height:1.35;white-space:nowrap}.historyFilters{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px}.historyFilters button.active{background:var(--green2);color:#fff}@media(max-width:800px){.historyRow{grid-template-columns:1fr}.historyModal{padding:10px}}
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
@media(max-width:980px){.main,.grid2,.grid3,.reportGrid,.reportHead,.reportMeta{grid-template-columns:1fr}#map{height:560px}.reportHead h1{text-align:left}}
@page{size:letter landscape;margin:.22in}
@media print{
 html,body{width:11in;height:8.5in;margin:0;padding:0;background:#fff;overflow:hidden}
 .wrap{display:none}
 #reportOverlay{display:block!important;position:static;background:#fff;padding:0;margin:0}
 .report{box-shadow:none;width:10.56in;height:8.02in;max-width:none;border-radius:0;padding:.12in;overflow:hidden;transform:none}
 .reportHead{grid-template-columns:1.85in 1fr 1.55in;gap:.08in;padding-bottom:.05in}
 .reportHead .logo{width:1.65in}.reportHead .dealerLogo{width:auto!important;height:auto!important;max-width:1.65in;max-height:1.08in;transform:scale(1.55);transform-origin:center center}.reportHead .dealerLogo.defaultShingleXtraLogo{transform:scale(1.75);transform-origin:center center}.reportHead .shield{width:1.28in}.reportHead h1{font-size:18pt}
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
</style>
<style>
.estimate-hide-street #reportStreet img,.estimate-hide-street .report-street img{visibility:hidden}
.estimate-hide-street #reportStreet,.estimate-hide-street .report-street{background:linear-gradient(135deg,#f3f7f4,#e6efe9);position:relative}
.estimate-hide-street #reportStreet:after,.estimate-hide-street .report-street:after{content:"PROPERTY ASSESSMENT COMPLETED\A Roof measured using available aerial imagery.";white-space:pre;text-align:center;font-weight:700;color:#174f2b;position:absolute;inset:0;display:flex;align-items:center;justify-content:center}
</style><style>
.estimate-hide-street #rStreet{visibility:hidden}
.estimate-hide-street .reportPanel:has(#rStreet) .reportBody{min-height:150px;background:linear-gradient(135deg,#f3f7f4,#e6efe9);position:relative}
.estimate-hide-street .reportPanel:has(#rStreet) .reportBody:before{content:"PROPERTY ASSESSMENT COMPLETED\A Roof measured using available aerial imagery.";white-space:pre;text-align:center;font-weight:800;color:#174f2b;position:absolute;inset:0;display:flex;align-items:center;justify-content:center}
</style><style>
.reportImagePlaceholder{display:none;min-height:465px;background:linear-gradient(135deg,#f3f7f4,#e6efe9);align-items:center;justify-content:center;text-align:center;padding:32px;color:#174f2b;border-bottom:1px solid var(--line)}
.reportImagePlaceholder .big{font-size:24px;font-weight:900;letter-spacing:.3px}.reportImagePlaceholder .miniShield{width:95px;margin:0 auto 14px;display:block}
.reportEditHelp{font-size:12px;color:#5b675f;margin-left:6px;align-self:center}.estimate-editing #customerMap{outline:4px solid #f59d0a;outline-offset:-4px;cursor:crosshair}
@media print{ #streetPlaceholder{height:1.38in!important}.reportStreet[style*="display: none"]{display:none!important}.reportImagePlaceholder{min-height:3.2in!important}}
</style></head>
<body>
<div class="wrap"><div class="card">
 <div class="header"><div class="brand"><img class="aeriquote-main-logo" src="/static/aeriquote-logo.png" alt="AeriQuote - Roof Measurement & Estimate Software"></div><div style="display:flex;gap:8px;align-items:center">{% if IS_HEAD_OFFICE %}<button type="button" class="secondary" onclick="window.location.href='/head-office/dealers'">DEALER MANAGEMENT</button>{% endif %}{% if IS_DEALER_OWNER %}<button type="button" class="secondary" onclick="window.location.href='/dealer-employees'">EMPLOYEES</button>{% endif %}<button type="button" class="secondary" onclick="openEstimateHistory()">PREVIOUS ESTIMATES</button><button type="button" class="ghost" onclick="window.location.href='/logout'">LOG OUT</button></div></div>
 <div class="stepbar"><div id="progress1" class="stepchip current"><strong><span class="stepnum">1</span>Property</strong>Enter address & load</div><div id="progress2" class="stepchip"><strong><span class="stepnum">2</span>Roof</strong>Check roof measurement</div><div id="progress3" class="stepchip"><strong><span class="stepnum">3</span>Price</strong>Set this job's price</div><div id="progress4" class="stepchip"><strong><span class="stepnum">4</span>Customer</strong>Add customer details</div><div id="progress5" class="stepchip"><strong><span class="stepnum">5</span>Estimate</strong>Create customer estimate</div></div>
 <div class="setup">
  <div class="stepcard"><h2>STEP 1 — Enter the property</h2><div class="grid2"><div><label>Property Address</label><input id="streetAddress" placeholder="Start typing the address — U.S. or Canada" value=""><div id="addressAutoStatus" class="small" style="margin-top:5px;color:#176b43;font-weight:700">City, state/province and ZIP/postal code will fill automatically when Google finds the address.</div><div id="addressParts" style="display:grid;grid-template-columns:1.2fr .55fr .8fr;gap:7px;margin-top:7px"><input id="cityTown" placeholder="City" value=""><select id="propertyProvince" onchange="propertyProvinceChanged()"><option value="">State / Province</option><optgroup label="United States"><option>AL</option><option>AK</option><option>AZ</option><option>AR</option><option>CA</option><option>CO</option><option>CT</option><option>DE</option><option>FL</option><option>GA</option><option>HI</option><option>ID</option><option>IL</option><option>IN</option><option>IA</option><option>KS</option><option>KY</option><option>LA</option><option>ME</option><option>MD</option><option>MA</option><option>MI</option><option>MN</option><option>MS</option><option>MO</option><option>MT</option><option>NE</option><option>NV</option><option>NH</option><option>NJ</option><option>NM</option><option>NY</option><option>NC</option><option>ND</option><option>OH</option><option>OK</option><option>OR</option><option>PA</option><option>RI</option><option>SC</option><option>SD</option><option>TN</option><option>TX</option><option>UT</option><option>VT</option><option>VA</option><option>WA</option><option>WV</option><option>WI</option><option>WY</option><option>DC</option></optgroup><optgroup label="Canada"><option>AB</option><option>BC</option><option>MB</option><option>NB</option><option>NL</option><option>NS</option><option>NT</option><option>NU</option><option>ON</option><option>PE</option><option>QC</option><option>SK</option><option>YT</option></optgroup></select><input id="postalCode" placeholder="ZIP / Postal Code — filled by Google" readonly></div><input id="address" type="hidden"><div id="googleMatch" class="small" style="margin-top:5px;color:#176b43;font-weight:700"></div><div id="propertyVerify" class="small" style="display:none;margin-top:7px;font-weight:700"></div>
<details id="coordinateFallback" style="margin-top:10px;border:1px solid #d9e3dc;border-radius:9px;background:#fafcfb">
<summary style="cursor:pointer;padding:10px 12px;font-weight:900;color:#5b675f">CAN'T LOCATE THE PROPERTY? USE DROPPED PIN / COORDINATES</summary>
<div style="padding:0 12px 12px">
<label>Latitude, Longitude <span class="info-tip" tabindex="0" data-tip="Enter latitude first, then longitude. Example: 27.950575, -82.457178. You can also paste 27.950575° N, 82.457178° W. West longitude becomes negative automatically.">ⓘ</span></label>
<input id="coordinateInput" placeholder="Example: 27.950575, -82.457178">
<div class="small" style="margin-top:5px"><b>Example:</b> 27.950575, -82.457178 &nbsp;•&nbsp; Latitude first, Longitude second.</div>
<div class="simple-actions" style="margin-top:8px"><button type="button" class="secondary" onclick="loadExactCoordinates()">LOAD EXACT PIN LOCATION</button></div>
<div id="coordinateStatus" class="small" style="margin-top:6px;font-weight:700"></div>
</div></details>
</div></div><div class="simple-actions"><button class="primarybig" onclick="loadProperty()">LOAD & MEASURE ROOF</button></div></div>
  <details class="dealer-settings" {% if IS_EMPLOYEE %}style="display:none"{% endif %}><summary>⚙ DEALER PROFILE / BRANDING — set once, then leave closed</summary><div class="settingsbody"><div class="savedmsg"><b>Set this up once.</b> Your saved dealer branding will appear on customer estimates. ShingleXtra treatment identification and the <b>6-Year Transferable Warranty</b> remain on every estimate.</div><div class="grid3"><div><label>Dealer / Contact Name</label><input id="dealerName" value=""></div><div><label>Company Name</label><input id="dealerCompany" placeholder="Your company name"></div><div><label>Dealer Phone</label><input id="dealerPhone" value=""></div></div><div class="dealer-branding-grid"><div><label>Dealer Email</label><input id="dealerEmail" type="email" placeholder="name@company.com"></div><div><label>Website</label><input id="dealerWebsite" placeholder="www.yourcompany.com"></div><div><label>Business Address</label><input id="dealerAddress" placeholder="City, State"></div></div><div class="dealer-logo-tools"><div><label style="display:block;margin-bottom:4px">Dealer Logo</label><input id="dealerLogoFile" type="file" accept="image/png,image/jpeg,image/webp" onchange="dealerLogoChanged(event)"></div><img id="dealerLogoPreview" class="dealer-logo-preview" src="/static/shinglextra-logo-inline.jpg" alt="Dealer logo preview"><button type="button" class="ghost dealer-logo-clear" onclick="clearDealerLogo()">REMOVE DEALER LOGO</button><div class="dealer-logo-note">Your logo is saved in this browser and used on the customer estimate. If no dealer logo is uploaded, the ShingleXtra logo is used.</div></div><div class="grid3" style="margin-top:10px"><div><label>Default Price / sq. ft.</label><input id="price" type="number" step="0.01" value="0.85"></div><div><label>Coverage / gallon (dealer only)</label><input id="coverage" type="number" value="330"></div><div><label>State</label><select id="province" onchange="provinceChanged()"><option value="AL">AL</option><option value="AK">AK</option><option value="AZ">AZ</option><option value="AR">AR</option><option value="CA">CA</option><option value="CO">CO</option><option value="CT">CT</option><option value="DE">DE</option><option value="FL">FL</option><option value="GA">GA</option><option value="HI">HI</option><option value="ID">ID</option><option value="IL">IL</option><option value="IN">IN</option><option value="IA">IA</option><option value="KS">KS</option><option value="KY">KY</option><option value="LA">LA</option><option value="ME">ME</option><option value="MD">MD</option><option value="MA">MA</option><option value="MI">MI</option><option value="MN">MN</option><option value="MS">MS</option><option value="MO">MO</option><option value="MT">MT</option><option value="NE">NE</option><option value="NV">NV</option><option value="NH">NH</option><option value="NJ">NJ</option><option value="NM">NM</option><option value="NY">NY</option><option value="NC">NC</option><option value="ND">ND</option><option value="OH">OH</option><option value="OK">OK</option><option value="OR">OR</option><option value="PA">PA</option><option value="RI">RI</option><option value="SC">SC</option><option value="SD">SD</option><option value="TN">TN</option><option value="TX">TX</option><option value="UT">UT</option><option value="VT">VT</option><option value="VA">VA</option><option value="WA">WA</option><option value="WV">WV</option><option value="WI">WI</option><option value="WY">WY</option><option value="DC">DC</option></select></div></div><div class="grid3" style="margin-top:7px"><div><label>Pricing Mode</label><select id="pricingMode" onchange="pricingChanged()"><option value="regular">Regular Price + Tax</option><option value="included">Taxes Included Promotion</option><option value="discount">Discount Promotion</option></select></div><div><label>Promotion Discount %</label><input id="discountPct" type="number" step="0.1" value="0" oninput="renderSummary()"></div><div><label>Sales Tax %</label><input id="gst" type="number" step="0.1" value="0" oninput="renderSummary()"></div></div><input id="pst" type="hidden" value="0"><div class="actions"><button type="button" onclick="saveDealerDefaults()">SAVE DEALER PROFILE & BRANDING</button></div><div id="savedMsg"></div></div></details>
  <button id="measureClicked" onclick="startGarageMode()" style="display:none" disabled></button><div class="usage" id="usageLine"></div>
 </div>
 <div id="status" class="status"></div>
 <div id="jobSummaryBar" class="job-summary-bar"><div><span class="js-label">PROPERTY</span><b id="jsProperty">No property loaded</b></div><div><span class="js-label">ROOFS</span><b id="jsRoofs">—</b></div><div><span class="js-label">TOTAL AREA</span><b id="jsArea">—</b></div><div><span class="js-label">ESTIMATE</span><b id="jsTotal">—</b></div></div>
 <div id="solarFallback" class="fallbackbox"><b>Manual Measurement Required</b><div id="solarFallbackText" class="small" style="margin-top:4px">Google does not have an automatic roof measurement for this property. Trace the shingled roof area below and confirm the roof pitch.</div><div class="small" style="margin-top:6px"><b>Important:</b> If the aerial appears older, verify the current roof layout with the homeowner or on site before sending the estimate.</div></div>
 <div class="main">
  <div class="panel"><div class="ptitle">STEP 2 — Check the roof measurement</div>
   <div id="garageControls" class="good" style="margin:8px"><div id="garageSavedConfirm" class="good" style="display:none;margin-bottom:8px;padding:10px;border:2px solid #2f7d44;font-size:15px"></div><div class="nexthelp"><b id="garageGuide">Load the property first. The main house will measure automatically.</b></div><div class="simple-actions" style="margin-top:10px"><button id="measureClickedTop" class="secondary primarybig" onclick="startGarageMode()" disabled>+ ADD GARAGE / OTHER ROOF</button><button class="ghost" onclick="removeLastExtra()">UNDO LAST ADDED ROOF</button></div><div class="small" style="margin-top:7px">Only use Add Garage / Other Roof when another shingled structure should be included.</div></div>
   <div id="roofCheckCard" class="stepcard" style="margin:10px 0"><h2 style="margin-bottom:5px">Is Google measuring the correct MAIN HOUSE?</h2><div class="small">If the blue outline is on the correct main house, continue. Garage and other-roof corrections are handled separately below.</div><div class="simple-actions" style="margin-top:9px"><button class="primary" onclick="roofCheckGood()">YES — MAIN HOUSE IS CORRECT</button></div><div id="roofFixHelp" class="small" style="margin-top:7px"></div><details class="roof-advanced"><summary>ROOF CORRECTIONS / ADVANCED OPTIONS</summary><div class="roof-advanced-body"><details style="margin-top:8px"><summary>Wrong garage / extra roof included? <span class="info-tip" tabindex="0" data-tip="Use this when Google correctly measured the main house but included a garage or other roof you do not want in the quote.">ⓘ</span></summary><div class="small" style="padding:8px 0"><b>Remove only the wrong extra roof.</b> The main house stays in the quote. If you need the correct garage afterward, use <b>ADD / REMEASURE GARAGE OR OTHER ROOF</b> directly below.</div><div class="simple-actions" style="margin-top:8px"><button id="fixRoofBtn" class="ghost" onclick="toggleRoofFix()">REMOVE WRONG GARAGE / EXTRA ROOF</button></div></details><details style="margin-top:8px"><summary>Customer picture outline needs cleanup? <span class="info-tip" tabindex="0" data-tip="Picture only. Adjusting this outline does NOT change Google's square footage, pitch, or estimate price.">ⓘ</span></summary><div class="small" style="padding:8px 0">This changes the customer picture only — not square footage, pitch or price.</div><div class="simple-actions"><button id="adjustOutlineBtn" class="secondary" onclick="toggleOutlineAdjust()">ADJUST CUSTOMER OUTLINE</button><button id="finishOutlineBtn" class="primary" onclick="finishOutlineAdjust()" disabled style="display:none">FINISH OUTLINE</button><button id="undoOutlineBtn" class="ghost" onclick="undoOutlinePoint()" style="display:none">UNDO POINT</button><button id="clearOutlineBtn" class="ghost" onclick="clearAdjustedOutline()" style="display:none">USE GOOGLE OUTLINE</button></div><div id="outlineHelp" class="small" style="margin-top:7px"></div></details><details style="margin-top:12px;border-top:1px solid #d9e3dc;padding-top:9px"><summary><b>Main house measurement is wrong?</b></summary><div class="warning" style="margin-top:8px"><b>Only use this to replace the MAIN HOUSE measurement.</b> Do not use this button for a garage or other added roof.</div><div class="simple-actions" style="margin-top:8px"><button id="manualOverrideBtn" class="danger" onclick="startManualOverride()">REPLACE MAIN HOUSE MEASUREMENT</button></div></details></div></details></div><details id="manualRoofDetails" class="manualbox" open><summary id="manualRoofSummary">Add / Remeasure Garage or Other Roof</summary><div id="manualRoofWarning" class="warning" style="margin:8px 12px"><b>Google's confirmed MAIN HOUSE stays in the quote.</b> Use this to add or remeasure a garage, shed, addition, or other shingled roof.</div><div class="manualrow"><button id="traceBtn" class="orange" onclick="toggleTrace()">ADD / REMEASURE GARAGE OR OTHER ROOF</button><div id="tracePitchControl" class="pitch" style="display:none"><label id="manualPitchLabel" style="margin:0 0 3px">Pitch of Added Roof <span class="info-tip" tabindex="0" data-tip="Google supplies pitch for automatically measured roofs. For a manually traced roof, the dealer must confirm the pitch. 5/12 is only the starting default.">ⓘ</span></label><select id="pitchSel" onchange="pitchChanged()"><option value="18.43">4/12</option><option value="22.62" selected>5/12</option><option value="26.57">6/12</option><option value="30.26">7/12</option><option value="33.69">8/12</option><option value="36.87">9/12</option><option value="39.81">10/12</option><option value="42.51">11/12</option><option value="45">12/12</option><option value="custom">Custom°</option></select></div><input id="pitchDeg" type="hidden" value="22.62"><button id="finishTrace" class="secondary" onclick="finishTrace()" disabled style="display:none">SAVE & ADD ROOF</button><button id="undoTraceBtn" class="ghost" onclick="undoPoint()" style="display:none">UNDO LAST POINT</button><button id="clearManualBtn" class="danger" onclick="clearManual()" style="display:none">CLEAR CURRENT DRAWING</button></div><div id="pitchReminder" class="pitch-reminder"><b>Confirm the roof pitch.</b> Manual roofs start at 5/12. Change it if needed before saving.</div><div id="manualRoofHelp" class="small" style="padding:0 12px 10px">Click around only the garage or other roof you want to add, confirm its pitch, then press SAVE & ADD ROOF. The Google main house stays unchanged.</div></details>
   <details id="advancedOptions" class="advanced"><summary>Show advanced roof display options</summary><div style="padding:8px 10px"><b>Roof Outlines:</b> <select id="outlineMode" onchange="redrawRoofData()" style="width:auto"><option value="smart">Actual Roof Outline (Recommended)</option><option value="all">Show Google segment boxes</option><option value="clean">Pitch labels only</option></select></div></details>
   <div class="mapwrap"><div id="loading" class="loading" style="display:none">Loading aerial imagery…</div><div id="traceBanner" class="tracebanner">MANUAL MEASURE ON — click roof corners, then SAVE & ADD ROOF</div><div id="map"></div></div>
  </div>
  <div class="panel"><div class="ptitle">STEP 3 — Review & price</div><div class="side"><img id="street" class="street" alt="Actual Street View"><div id="streetMeta" class="small" style="margin-top:4px"></div><div class="stepcard" style="margin-top:10px"><h2>Price for this job</h2><label>Price for This Job / sq. ft. <span class="info-tip" tabindex="0" data-tip="Your dealer default loads here automatically. Change this number for any individual job and the quote recalculates immediately.">ⓘ</span></label><input id="jobPrice" type="number" step=".01" value=".95" oninput="jobPriceChanged()" onchange="jobPriceChanged()"><div class="small">This is the price used for the quote. Change it anytime before creating the estimate.</div><div id="appliedJobPrice" class="good" style="margin-top:7px;padding:7px">Quote is using <b>$0.95 / sq. ft.</b></div></div><div id="summary"></div><div class="stepcard"><h2>STEP 4 — Customer</h2><div class="customer-grid"><div class="full"><label>Customer Name</label><input id="customerName" placeholder="Customer name" oninput="updateProgressSteps()"></div><div><label>Customer Phone</label><input id="customerPhone" placeholder="Phone" oninput="updateProgressSteps()"></div><div><label>Customer Email</label><input id="customerEmail" type="email" placeholder="Email" oninput="updateProgressSteps()"></div><div class="full"><label>Customer / Job Notes <span class="small">(optional)</span></label><textarea id="customerNotes" placeholder="Optional notes for this customer or job"></textarea></div></div></div><div class="stepcard"><h2>STEP 5 — Create estimate</h2><label>Additional Services / Repairs <span class="small">(optional)</span></label><input id="extraServiceDescription" placeholder="Example: Replace damaged shingles, seal vent, minor roof repair" oninput="renderSummary()"><label style="margin-top:8px">Additional Services / Repairs Amount</label><input id="extraServiceAmount" type="number" min="0" step="0.01" value="0" oninput="renderSummary()"><div class="small" style="margin-top:5px">Added to the estimate and uses the same sales-tax setting as this job.</div><label style="margin-top:10px">Estimate images</label><select id="streetViewChoice"><option value="auto" selected>Use Aerial + Google Street View</option><option value="hide">Use Aerial + ShingleXtra Placeholder</option><option value="none">Create Estimate Without Images</option></select><div class="simple-actions" style="margin-top:10px"><button id="createEstimateBtn" class="primarybig" onclick="showCustomerEstimate()" disabled>CREATE CUSTOMER ESTIMATE</button></div></div></div></div>
 </div>
</div></div>

<div id="historyModal" class="historyModal"><div class="historyBox"><div class="historyHead"><div><h2 style="margin:0;color:var(--green2)">Previous Estimates</h2><div class="small">Search by customer name, property address, phone or email.</div></div><button class="ghost" onclick="closeEstimateHistory()">CLOSE</button></div><div style="display:flex;gap:8px;margin-top:14px"><input id="historySearch" placeholder="Search name, address, phone or email" onkeydown="if(event.key==='Enter')searchEstimateHistory()"><button onclick="searchEstimateHistory()">SEARCH</button></div><div class="historyFilters"><button type="button" class="secondary active" data-status-filter="All" onclick="setHistoryStatusFilter('All',this)">ALL</button><button type="button" class="secondary" data-status-filter="Estimate" onclick="setHistoryStatusFilter('Estimate',this)">ESTIMATES</button><button type="button" class="secondary" data-status-filter="Booked" onclick="setHistoryStatusFilter('Booked',this)">BOOKED</button><button type="button" class="secondary" data-status-filter="Completed" onclick="setHistoryStatusFilter('Completed',this)">COMPLETED</button></div><div id="historyResults" class="historyResults"><div class="small" style="padding:14px 0">Your saved estimates will appear here.</div></div></div></div>

<div id="reportOverlay"><div class="report" style="width:min(1320px,calc(100vw - 44px));">
 <div class="reportHead"><img id="rDealerLogo" class="logo dealerLogo defaultShingleXtraLogo" src="/static/shinglextra-logo-inline.jpg"><div><h1>Your ShingleXtra<br>Roof Treatment Estimate</h1><div style="text-align:center;color:#28612f;font-weight:800;margin-top:6px">Protecting Your Roof. Protecting Your Investment.</div><div class="reportDealerSub">Treatment & 6-Year Transferable Warranty by ShingleXtra</div></div><img class="shield" src="/static/warranty-shield-premium.png"></div>
 <div class="reportMeta"><div><b>Property Address</b><div id="rAddress"></div></div><div><b>Date Prepared</b><div id="rDate"></div></div><div><b>Prepared For</b><div id="rCustomerName">Homeowner</div><div id="rCustomerPhone" class="small"></div><div id="rCustomerEmail" class="small"></div></div></div>
 <div class="reportGrid"><div>
  <div class="reportPanel"><div class="reportTitle">ROOF ASSESSMENT</div><div class="reportMapWrap"><div id="customerMap" class="customerMap"></div><svg id="reportDrawLayer" class="reportDrawLayer" aria-label="Draw customer roof outline"></svg></div><div id="reportOutlineControls" class="estimateOutlineBar"><div id="reportOutlineTargetButtons" style="display:flex;gap:7px;flex-wrap:wrap"></div><button id="reportCancelOutlineBtnTop" class="danger" onclick="cancelReportOutlineEdit()" style="display:none">CANCEL OUTLINE EDIT</button><button id="reportUndoOutlineBtnTop" class="ghost" onclick="undoReportOutlinePoint()" style="display:none">UNDO POINT</button><button id="reportSaveOutlineBtnTop" class="primary" onclick="saveReportOutline()" style="display:none" disabled>SAVE OUTLINE</button><span id="reportOutlineHelpTop" class="reportEditHelp">Choose which roof to edit. Picture only — quote numbers do not change.</span></div><div id="customerMapPlaceholder" class="reportImagePlaceholder"><div><img class="miniShield" src="/static/warranty-shield-premium.png"><div class="big">SHINGLEXTRA ROOF ASSESSMENT</div><div style="margin-top:10px;font-weight:700">Professional roof treatment estimate prepared for this property.</div><div class="small" style="margin-top:8px">Property imagery omitted from this estimate.</div></div></div><div class="reportBody"><div id="rProperty"></div></div></div>
  <div class="reportPrice"><div class="rphead">ESTIMATE SUMMARY</div><div class="rpbody" id="rPricing"></div></div>
 </div><div>
  <div class="reportPanel"><div class="reportTitle">PROPERTY IMAGE</div><div class="reportBody">
<div id="streetPlaceholder" style="display:none;height:225px;border-radius:8px;border:1px solid #cde5d4;background:linear-gradient(135deg,#f3f7f4,#e6efe9);align-items:center;justify-content:center;text-align:center;padding:20px;color:#174f2b"><div><b style="font-size:18px">PROPERTY ASSESSMENT COMPLETED</b><br><span class="small">Roof measured using available aerial imagery.</span></div></div>
<img id="rStreet" class="reportStreet"><div id="rStreetMeta" class="small" style="margin-top:4px"></div></div></div>
  <div class="reportPanel" style="margin-top:12px"><div class="reportTitle">THE SHINGLEXTRA ADVANTAGE</div><div class="reportBody"><div class="benefit"><span class="benefitIcon">✓</span><div><b>EXTENDS ROOF LIFE</b><br><span class="small">Helps extend the usable service life of asphalt shingles.</span></div></div><div class="benefit"><span class="benefitIcon">☂</span><div><b>WEATHER PROTECTION</b><br><span class="small">Adds protection from UV, moisture and weather exposure.</span></div></div><div class="benefit"><span class="benefitIcon">$</span><div><b>SAVE THOUSANDS</b><br><span class="small">Up to 80% less than the cost of a full roof replacement.</span></div></div><div class="benefit"><span class="benefitIcon">◆</span><div><b>NO TEAR-OFF</b><br><span class="small">Protect your existing asphalt shingles without replacement.</span></div></div><div class="benefit"><span class="benefitIcon">6</span><div><b>TRANSFERABLE WARRANTY</b><br><span class="small">Backed by ShingleXtra's 6-Year Transferable Warranty.</span></div></div></div></div>
  <div class="cta"><strong>READY TO PROTECT YOUR ROOF?</strong><div style="margin-top:5px;color:#f59d0a;font-weight:800">This is a FREE, no-obligation estimate.</div><div style="margin-top:9px"><b id="rDealerCompany"></b></div><div id="rDealerName" style="margin-top:2px"></div><div class="dealerContactCompact"><span>Call or Text: <b id="rPhone"></b></span><span id="rDealerEmailWrap"><span class="contactSep">•</span><span id="rDealerEmail"></span></span><br><span id="rDealerWebsite"></span><span id="rDealerAddressWrap"><span class="contactSep">•</span><span id="rDealerAddress"></span></span></div><div style="margin-top:6px;font-size:11px;opacity:.9">ShingleXtra treatment & warranty • shinglextra.com</div></div>
 </div></div>
 <div class="reportFoot">Remote aerial measurements are used for estimating. Final roof condition and measurements should be confirmed before application.</div>
 <div class="reportActions"><span id="reportOutlineHelp" class="reportEditHelp" style="display:none"></span><button id="downloadPdfBtn" class="primary" onclick="downloadEstimatePDF()">DOWNLOAD ESTIMATE PDF</button><button class="secondary" onclick="window.print()">PRINT ESTIMATE</button><button class="primary" onclick="startNewProperty()">NEW PROPERTY / NEXT ESTIMATE</button><button id="backToDealerBtn" class="secondary" onpointerdown="armReportClose(event)" onclick="closeReport(event)">Back to Dealer View</button></div>
</div></div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/georaster"></script>
<script src="https://unpkg.com/georaster-layer-for-leaflet"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
<!-- AERIQUOTE V1 CANADA + USA: dealer polish built directly from VERIFIED V11.6.56. Only dealer-facing version cleanup and the read-only job summary strip were added. Measurement, address, map, outline, dealer branding and PDF capture mechanics are unchanged. -->
<script>
let map=L.map('map',{maxZoom:22,zoomControl:true,zoomSnap:.25,zoomDelta:.5}).setView([52.1522,-106.6595],19);
let skipAddressConflictOnce=false;
L.control.scale({imperial:true,metric:true}).addTo(map);
let rgbLayer=null,roofMask=null,sessionToken=null,clicked=null,clickMarker=null,structures=[],overlays=[],mainBounds=null;
let traceMode=false,tracePoints=[],tempTraceLayers=[],manualPlanes=[],manualLayers=[],garageMode=false,roofFixMode=false,locateRoofMode=false,fallbackMode=false,fallbackLayer=null,fallbackBounds=null,traceSavePopup=null;
let outlineEditMode=false,outlinePoints=[],outlineTempLayers=[],adjustedOutline=null,adjustedOutlineLayer=null,addressPreviewTimer=null,addressPreviewSeq=0,lastLoadedStreet='',propertyMarker=null,manualOverrideMode=false,manualAerialSwitching=false;
let customerMap=null,customerRgbLayer=null,customerOverlays=[],reportOutlines={},reportOutlineTarget=null,reportOutlineEditMode=false,reportOutlinePoints=[],reportOutlineTemp=[];
let quoteSnapshot=null;
let savedStreetImageData='';
let exactPinDisplay=false;
let estimateOpenInProgress=false,customerMapBuildTimer=null,pdfInProgress=false;
let usage={property:0,structures:0,reports:0,saved:0};
let lastHistorySaveKey='';
let historyStatusFilter='All';

const legend=L.control({position:'bottomright'});legend.onAdd=()=>{const d=L.DomUtil.create('div');d.style.cssText='background:white;padding:7px 9px;border-radius:7px;box-shadow:0 1px 5px #0003;font-size:11px;line-height:1.5';d.innerHTML='<b>Roof Segments</b><br>Blue = Main House<br>Teal = Extra Structure<br>Gold = Pitch';return d};legend.addTo(map);
map.on('click',e=>{if(outlineEditMode){addOutlinePoint(e.latlng);return}if(traceMode){addTracePoint(e.latlng);return}if(roofFixMode){removeClickedExtraRoof(e.latlng);return}if(locateRoofMode){retryRoofAt(e.latlng);return}if(!garageMode)return;clicked=e.latlng;if(clickMarker)clickMarker.remove();clickMarker=L.marker(e.latlng).addTo(map).bindPopup('Measuring selected roof…').openPopup();garageMode=false;measureClicked();});

function el(id){return document.getElementById(id)}function fmt(n){return Math.round(Number(n||0)).toLocaleString()}function money(n){return new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(Number(n||0))}function status(t,k=''){el('status').textContent=t;el('status').className='status '+k}function showLoad(v){el('loading').style.display=v?'block':'none'}
function provinceRules(code){return [Number(el('gst')?.value||0),0]}
function provinceChanged(){renderSummary()}function pricingChanged(){el('discountPct').disabled=el('pricingMode').value!=='discount';renderSummary()}
function dealerLogoChanged(event){
 const file=event&&event.target&&event.target.files?event.target.files[0]:null;if(!file)return;
 if(!/^image\/(png|jpeg|webp)$/i.test(file.type)){status('Please choose a PNG, JPG or WEBP logo.','error');if(el('dealerLogoFile'))el('dealerLogoFile').value='';return}
 if(file.size>4000000){status('That logo file is too large. Please use an image under 4 MB.','error');if(el('dealerLogoFile'))el('dealerLogoFile').value='';return}
 const reader=new FileReader();reader.onload=()=>{const img=new Image();img.onload=()=>{try{const maxW=700,maxH=240,scale=Math.min(1,maxW/img.width,maxH/img.height),w=Math.max(1,Math.round(img.width*scale)),h=Math.max(1,Math.round(img.height*scale)),c=document.createElement('canvas');c.width=w;c.height=h;const ctx=c.getContext('2d');ctx.clearRect(0,0,w,h);ctx.drawImage(img,0,0,w,h);const data=c.toDataURL('image/png');localStorage.setItem('sxDealerLogo',data);if(el('dealerLogoPreview'))el('dealerLogoPreview').src=data;status('Dealer logo ready. Click SAVE DEALER PROFILE & BRANDING to save the rest of the profile.','ok')}catch(e){status('Could not prepare that logo. Try a different image.','error')}};img.onerror=()=>status('Could not read that logo image.','error');img.src=reader.result};reader.onerror=()=>status('Could not read that logo file.','error');reader.readAsDataURL(file)
}
function clearDealerLogo(){localStorage.removeItem('sxDealerLogo');if(el('dealerLogoPreview'))el('dealerLogoPreview').src='/static/shinglextra-logo-inline.jpg';if(el('dealerLogoFile'))el('dealerLogoFile').value='';status('Dealer logo removed. ShingleXtra logo will be used on estimates.','ok')}
function dealerLogoSrc(){try{return localStorage.getItem('sxDealerLogo')||'/static/shinglextra-logo-inline.jpg'}catch(e){return'/static/shinglextra-logo-inline.jpg'}}
function saveDealerDefaults(){const d={name:el('dealerName').value,company:el('dealerCompany')?el('dealerCompany').value:'',email:el('dealerEmail')?el('dealerEmail').value:'',website:el('dealerWebsite')?el('dealerWebsite').value:'',address:el('dealerAddress')?el('dealerAddress').value:'',price:el('price').value,coverage:el('coverage').value,province:el('province').value,pricingMode:el('pricingMode').value,discountPct:el('discountPct').value,gst:el('gst').value,pst:el('pst').value,phone:el('dealerPhone').value};localStorage.setItem('sxDealerDefaults',JSON.stringify(d));const savedPrice=parseFloat(d.price);if(Number.isFinite(savedPrice)&&savedPrice>=0&&el('jobPrice'))el('jobPrice').value=savedPrice.toFixed(2);const ds=document.querySelector('details.dealer-settings');if(ds)ds.open=true;renderSummary();el('savedMsg').innerHTML=`<div class="savedmsg"><b>✓ Dealer profile & branding saved.</b> Current quote updated to <b>${money(savedPrice)} / sq. ft.</b>. Your dealer identity will appear on customer estimates while the ShingleXtra treatment and 6-Year Warranty remain visible.</div>`}
function loadDealerDefaults(){try{const d=JSON.parse(localStorage.getItem('sxDealerDefaults')||'null');if(d){if(d.name!==undefined&&el('dealerName'))el('dealerName').value=d.name;if(d.company!==undefined&&el('dealerCompany'))el('dealerCompany').value=d.company;if(d.email!==undefined&&el('dealerEmail'))el('dealerEmail').value=d.email;if(d.website!==undefined&&el('dealerWebsite'))el('dealerWebsite').value=d.website;if(d.address!==undefined&&el('dealerAddress'))el('dealerAddress').value=d.address;if(d.phone!==undefined&&el('dealerPhone'))el('dealerPhone').value=d.phone;['price','coverage','province','pricingMode','discountPct','gst','pst'].forEach(id=>{if(d[id]!==undefined&&el(id))el(id).value=d[id]});if(d.price!==undefined&&el('jobPrice'))el('jobPrice').value=d.price}else if(el('price')&&el('jobPrice'))el('jobPrice').value=el('price').value}catch(e){}if(el('dealerLogoPreview'))el('dealerLogoPreview').src=dealerLogoSrc();pricingChanged()}
function detectProvince(addr){const a=(' '+String(addr||'').toUpperCase().replace(/[.,]/g,' ')+' ');const states={AL:'ALABAMA',AK:'ALASKA',AZ:'ARIZONA',AR:'ARKANSAS',CA:'CALIFORNIA',CO:'COLORADO',CT:'CONNECTICUT',DE:'DELAWARE',FL:'FLORIDA',GA:'GEORGIA',HI:'HAWAII',ID:'IDAHO',IL:'ILLINOIS',IN:'INDIANA',IA:'IOWA',KS:'KANSAS',KY:'KENTUCKY',LA:'LOUISIANA',ME:'MAINE',MD:'MARYLAND',MA:'MASSACHUSETTS',MI:'MICHIGAN',MN:'MINNESOTA',MS:'MISSISSIPPI',MO:'MISSOURI',MT:'MONTANA',NE:'NEBRASKA',NV:'NEVADA',NH:'NEW HAMPSHIRE',NJ:'NEW JERSEY',NM:'NEW MEXICO',NY:'NEW YORK',NC:'NORTH CAROLINA',ND:'NORTH DAKOTA',OH:'OHIO',OK:'OKLAHOMA',OR:'OREGON',PA:'PENNSYLVANIA',RI:'RHODE ISLAND',SC:'SOUTH CAROLINA',SD:'SOUTH DAKOTA',TN:'TENNESSEE',TX:'TEXAS',UT:'UTAH',VT:'VERMONT',VA:'VIRGINIA',WA:'WASHINGTON',WV:'WEST VIRGINIA',WI:'WISCONSIN',WY:'WYOMING',DC:'DISTRICT OF COLUMBIA'};for(const [code,name] of Object.entries(states)){if(new RegExp('\\b'+code+'\\b').test(a)||a.includes(' '+name+' '))return code}return null}
function updateUsage(){el('usageLine').textContent=`This session — property lookups: ${usage.property} • extra structures: ${usage.structures} • reports: ${usage.reports} • saved assessments: ${usage.saved}`}

async function loadRaster(url,targetMap=map){const res=await fetch(url);if(!res.ok)throw new Error('Could not load Google aerial imagery.');const arr=await res.arrayBuffer();const gr=await parseGeoraster(arr);const layer=new GeoRasterLayer({georaster:gr,opacity:1,resolution:64,updateWhenIdle:true,updateWhenZooming:false,keepBuffer:8,resampleMethod:'nearest',pixelValuesToColorFn:vals=>{if(!vals||vals.length<3||vals.every(v=>v===null||v===undefined||Number.isNaN(v)))return null;const r=Number(vals[0]),g=Number(vals[1]),b=Number(vals[2]);if(!Number.isFinite(r)||!Number.isFinite(g)||!Number.isFinite(b))return null;return `rgb(${Math.max(0,Math.min(255,r))},${Math.max(0,Math.min(255,g))},${Math.max(0,Math.min(255,b))})`}});layer._sgAerial=true;layer._sgAerialType='solar-rgb';layer.addTo(targetMap);return{layer,bounds:layer.getBounds()}}
function removeStaleAerialLayers(keep=null){
 map.eachLayer(layer=>{if(layer&&layer._sgAerial&&layer!==keep){try{map.removeLayer(layer)}catch(e){}}});
 if(rgbLayer&&rgbLayer!==keep){try{map.removeLayer(rgbLayer)}catch(e){}rgbLayer=null}
 if(fallbackLayer&&fallbackLayer!==keep){try{map.removeLayer(fallbackLayer)}catch(e){}fallbackLayer=null}
}
async function loadStandardWideAerial(){
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
function setPropertyMarker(lat,lng){if(propertyMarker){try{map.removeLayer(propertyMarker)}catch(e){}}propertyMarker=L.marker([lat,lng]).addTo(map).bindTooltip('Customer Property',{permanent:false,direction:'top',offset:[0,-18]});}
function setManualCorrectionLayout(on){manualOverrideMode=!!on;if(el('garageControls'))el('garageControls').style.display=on?'none':'';if(el('roofCheckCard'))el('roofCheckCard').style.display=on?'none':'';if(el('advancedOptions'))el('advancedOptions').style.display=on?'none':'';}
async function startManualOverride(){if(!sessionToken){status('Load the property first.','error');return}cancelCurrentTrace();garageMode=false;roofFixMode=false;locateRoofMode=false;outlineEditMode=false;outlinePoints=[];clearOutlineTemp();clearOverlays();structures=[];manualPlanes=[];manualLayers.forEach(x=>{try{map.removeLayer(x)}catch(e){}});manualLayers=[];adjustedOutline=null;setManualCorrectionLayout(true);setManualUi(true);if(el('measureSource'))el('measureSource').value='manual';if(el('solarFallback'))el('solarFallback').style.display='block';if(el('solarFallbackText'))el('solarFallbackText').textContent='Manual measurement selected for this property. Trace the shingled roof around the customer property pin and confirm the pitch.';if(el('garageGuide'))el('garageGuide').innerHTML='<b>Manual measurement mode.</b> Google lines are hidden. Trace the customer roof shown at the property pin.';const details=el('manualRoofDetails');if(details)details.open=true;renderSummary();status('Preparing stable satellite image for manual measurement…','warn');await useStableManualAerial();setTimeout(()=>{if(!traceMode)toggleTrace()},60);status('Manual measurement mode is ready. Trace the roof corners, zoom as needed, then save.','warn')}
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
function startLocateRoof(){if(!sessionToken||!fallbackMode){status('Load the property first.','error');return}locateRoofMode=true;garageMode=false;roofFixMode=false;status('Click once near the centre of the house roof. We’ll retry Google at that exact location.','warn');if(el('solarFallbackText'))el('solarFallbackText').textContent='Click once near the centre of the HOUSE roof on the aerial.'}
function setManualUi(pure=false){if(el('manualRoofSummary'))el('manualRoofSummary').textContent=pure?'Manual Measurement — Trace Customer Roof':'Add / Remeasure Garage or Other Roof';if(el('manualRoofWarning'))el('manualRoofWarning').innerHTML=pure?'<b>Manual measurement for this property.</b> Trace the shingled MAIN HOUSE around the customer property pin, then confirm the pitch. 5/12 is only the starting default.':(structures.length?"<b>Google's confirmed MAIN HOUSE stays in the quote.</b> Use this to add or remeasure a garage, shed, addition, or other shingled roof.":'<b>Your manually measured MAIN HOUSE stays in the quote.</b> Use this to add the garage, shed, shop, or another shingled building.');if(el('manualRoofHelp'))el('manualRoofHelp').textContent=pure?'Click each outside corner of the MAIN HOUSE, confirm the pitch, then press FINISH MEASUREMENT.':'Click around only the garage or other roof you want to add, confirm its pitch, then press SAVE & ADD ROOF.';if(el('manualPitchLabel'))el('manualPitchLabel').childNodes[0].nodeValue=pure?'Pitch of Main House ':'Pitch of Added Roof ';if(el('traceBtn')&&!traceMode)el('traceBtn').textContent=pure?'START MANUAL MEASUREMENT':'ADD MISSING ROOF';if(el('finishTrace'))el('finishTrace').textContent=pure?'FINISH MEASUREMENT':'SAVE & ADD ROOF';if(el('clearManualBtn'))el('clearManualBtn').textContent=pure?'CLEAR MAIN HOUSE OUTLINE':'CLEAR ADDED ROOF DRAWING';}
function startManualFallback(){if(!sessionToken||!fallbackMode){status('Load the property first.','error');return}locateRoofMode=false;setManualUi(true);if(el('solarFallbackText'))el('solarFallbackText').textContent='Manual mode: trace the shingled roof and confirm the pitch. Google automatic measurement is unavailable for this property.';status('Manual measurement ready — open the manual roof section, trace the roof, and confirm pitch.','warn');const details=el('manualRoofDetails');if(details)details.open=true;}
async function retryRoofAt(ll){if(!sessionToken)return;locateRoofMode=false;if(clickMarker){try{map.removeLayer(clickMarker)}catch(e){}}clickMarker=L.marker(ll).addTo(map).bindPopup('Checking this roof with Google…').openPopup();try{showLoad(true);status('Checking the selected roof with Google…');const r=await fetch('/locate-building',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:sessionToken,latitude:ll.lat,longitude:ll.lng})}),d=await r.json();if(!r.ok){showSolarFallback(true,'Google still cannot automatically measure this roof. You can click a slightly different spot and retry, or choose MEASURE MANUALLY.');status(d.user_error||'Google automatic measurement is unavailable for this roof.','warn');return}structures=[{...d.main,label:'Main House'}];setManualCorrectionLayout(false);setManualUi(false);if(el('measureSource'))el('measureSource').value='google';if(fallbackLayer){try{map.removeLayer(fallbackLayer)}catch(e){}fallbackLayer=null}if(rgbLayer){try{map.removeLayer(rgbLayer)}catch(e){}rgbLayer=null}let rgb=await loadRaster('/rgb/'+sessionToken);rgbLayer=rgb.layer;mainBounds=rgb.bounds;frameAerial(map,rgb.bounds,0);roofMask=await loadRoofMask('/mask/'+sessionToken);structures[0].outline=outlineFromMask(roofMask,d.main.latitude,d.main.longitude);await loadStandardWideAerial();redrawRoofData();showSolarFallback(false);renderSummary();if(el('garageGuide'))el('garageGuide').innerHTML='<b>Main house measured.</b> If there is another roof to include, click <b>+ ADD GARAGE / OTHER ROOF</b>, then click once on that roof.';if(el('measureClicked'))el('measureClicked').disabled=false;if(el('measureClickedTop'))el('measureClickedTop').disabled=false;status('Main house measured from the roof you selected.','ok')}catch(e){showSolarFallback(true,'Google still cannot automatically measure this roof. Try a slightly different point or choose MEASURE MANUALLY.');status('Google automatic measurement is unavailable for this roof.','warn')}finally{showLoad(false);if(clickMarker){try{map.removeLayer(clickMarker)}catch(e){}clickMarker=null}}}

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
async function loadRoofMask(url){
 try{const res=await fetch(url);if(!res.ok)return null;const gr=await parseGeoraster(await res.arrayBuffer());let values=gr.values;if(!values&&gr.getValues)values=await gr.getValues({top:0,left:0,bottom:0,right:0,width:gr.width,height:gr.height});if(!values||!values[0])return null;const helper=new GeoRasterLayer({georaster:gr,resolution:16});let toRaster=null,toWgs=null;try{toRaster=helper.getProjector(4326,gr.projection).forward;toWgs=helper.getProjector(gr.projection,4326).forward}catch(e){return null}return{gr,band:values[0],toRaster,toWgs}}catch(e){console.warn('Roof mask unavailable',e);return null}
}
function maskValue(mask,r,c){if(r<0||c<0||r>=mask.gr.height||c>=mask.gr.width)return 0;const row=mask.band[r];return row&&Number(row[c])>0?1:0}
function nearestMaskPixel(mask,lat,lng){
 let xy;try{xy=mask.toRaster([lng,lat])}catch(e){return null}const gr=mask.gr,c0=Math.floor((xy[0]-gr.xmin)/Math.abs(gr.pixelWidth)),r0=Math.floor((gr.ymax-xy[1])/Math.abs(gr.pixelHeight));if(maskValue(mask,r0,c0))return[r0,c0];
 const maxR=Math.min(60,Math.max(12,Math.round(12/Math.max(.1,Math.abs(gr.pixelWidth||.25)))));for(let d=1;d<=maxR;d++){for(let dc=-d;dc<=d;dc++){for(const rr of [r0-d,r0+d])if(maskValue(mask,rr,c0+dc))return[rr,c0+dc]}for(let dr=-d+1;dr<=d-1;dr++){for(const cc of [c0-d,c0+d])if(maskValue(mask,r0+dr,cc))return[r0+dr,cc]}}return null
}
function outlineFromMask(mask,lat,lng){
 if(!mask)return null;const seed=nearestMaskPixel(mask,lat,lng);if(!seed)return null;const H=mask.gr.height,W=mask.gr.width,seen=new Uint8Array(H*W),q=[seed],cells=[],key=(r,c)=>r*W+c;seen[key(seed[0],seed[1])]=1;
 for(let qi=0;qi<q.length;qi++){const [r,c]=q[qi];cells.push([r,c]);for(const [dr,dc] of [[-1,0],[1,0],[0,-1],[0,1]]){const nr=r+dr,nc=c+dc;if(nr<0||nc<0||nr>=H||nc>=W)continue;const k=key(nr,nc);if(!seen[k]&&maskValue(mask,nr,nc)){seen[k]=1;q.push([nr,nc])}}}
 if(cells.length<8)return null;const inside=(r,c)=>r>=0&&c>=0&&r<H&&c<W&&seen[key(r,c)]===1,edges=[],vkey=(r,c)=>r+','+c;
 for(const [r,c] of cells){if(!inside(r-1,c))edges.push([[r,c],[r,c+1]]);if(!inside(r,c+1))edges.push([[r,c+1],[r+1,c+1]]);if(!inside(r+1,c))edges.push([[r+1,c+1],[r+1,c]]);if(!inside(r,c-1))edges.push([[r+1,c],[r,c]])}
 const byStart=new Map();edges.forEach((e,i)=>{const k=vkey(e[0][0],e[0][1]);if(!byStart.has(k))byStart.set(k,[]);byStart.get(k).push(i)});const used=new Uint8Array(edges.length),loops=[];
 for(let i=0;i<edges.length;i++){if(used[i])continue;let loop=[],cur=i,startKey=vkey(edges[i][0][0],edges[i][0][1]),guard=0;while(cur!==undefined&&!used[cur]&&guard++<edges.length+5){used[cur]=1;const e=edges[cur];loop.push(e[0]);const nk=vkey(e[1][0],e[1][1]);if(nk===startKey){loop.push(e[1]);break}const nexts=(byStart.get(nk)||[]).filter(j=>!used[j]);cur=nexts.length?nexts[0]:undefined}if(loop.length>=4)loops.push(loop)}
 if(!loops.length)return null;let loop=loops.sort((a,b)=>b.length-a.length)[0];loop=simplifyClosedContour(loop,3.2);if(loop.length<3)return null;const gr=mask.gr,pts=[];for(const [r,c] of loop){const x=gr.xmin+c*Math.abs(gr.pixelWidth),y=gr.ymax-r*Math.abs(gr.pixelHeight);let ll;try{ll=mask.toWgs([x,y])}catch(e){return null}pts.push([ll[1],ll[0]])}return pts
}
function drawSegments(s,kind,targetMap=map,targetList=overlays,skipOutline=false){const color=kind==='house'?'#2d6cdf':'#18a7a0',segs=(s.segments||[]),mode=(el('outlineMode')?el('outlineMode').value:'smart'),showBoxes=(mode==='all');segs.forEach((seg)=>{const b=seg.bounding_box;if(!b||!b.sw||!b.ne)return;if(showBoxes){const rect=L.rectangle([[b.sw.latitude,b.sw.longitude],[b.ne.latitude,b.ne.longitude]],{color,weight:2,fillColor:color,fillOpacity:.08}).addTo(targetMap);targetList.push(rect)}const c=seg.center||{latitude:(b.sw.latitude+b.ne.latitude)/2,longitude:(b.sw.longitude+b.ne.longitude)/2};const lab=L.marker([c.latitude,c.longitude],{interactive:false,icon:L.divIcon({className:'',html:`<div class="seg-label">${seg.pitch_degrees.toFixed(1)}°</div>`,iconAnchor:[24,10]})}).addTo(targetMap);targetList.push(lab)});const visualOutline=(kind==='house'&&outlineEditMode)?null:((kind==='house'&&Array.isArray(adjustedOutline)&&adjustedOutline.length>=3)?adjustedOutline:s.outline);if(!skipOutline&&mode==='smart'&&Array.isArray(visualOutline)&&visualOutline.length>=3){const poly=L.polygon(visualOutline,{color,weight:4,fillColor:color,fillOpacity:.055,interactive:false,lineJoin:'round',smoothFactor:1.8}).addTo(targetMap);targetList.unshift(poly)}}
function redrawRoofData(){clearOverlays();(structures||[]).forEach((st,i)=>drawSegments(st,i===0?'house':'garage'));}

function roofCheckGood(){roofFixMode=false;if(el('fixRoofBtn')){el('fixRoofBtn').textContent='NO — REMOVE WRONG ROOF';el('fixRoofBtn').className='orange'}if(el('roofFixHelp'))el('roofFixHelp').innerHTML='<b>✓ Roofs confirmed.</b> Continue to price and estimate.';status('Roofs confirmed. Continue to price and estimate.','ok')}
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
function pitchChanged(){if(el('pitchSel').value!=='custom')el('pitchDeg').value=el('pitchSel').value}
function localPolygonAreaM2(points){if(points.length<3)return 0;const R=6378137,lat0=points.reduce((a,p)=>a+p.lat,0)/points.length*Math.PI/180,xy=points.map(p=>({x:R*(p.lng*Math.PI/180)*Math.cos(lat0),y:R*(p.lat*Math.PI/180)}));let a=0;for(let i=0;i<xy.length;i++){const j=(i+1)%xy.length;a+=xy[i].x*xy[j].y-xy[j].x*xy[i].y}return Math.abs(a)/2}
function setTraceControls(active){['tracePitchControl','finishTrace','undoTraceBtn','clearManualBtn'].forEach(id=>{if(el(id))el(id).style.display=active?'':'none'})}
function toggleTrace(){if(traceMode){cancelCurrentTrace();status('Manual trace cancelled.','ok');return}const mainManual=(manualOverrideMode||fallbackMode)&&structures.length===0&&manualPlanes.length===0;traceMode=true;tracePoints=[];clearTempTrace();setTraceControls(true);if(el('manualRoofHelp'))el('manualRoofHelp').innerHTML=mainManual?'Trace the MAIN HOUSE only.':'Trace only the garage or other roof you want to add. The main house stays unchanged.';if(!window.sgPitchReminderShown&&el('pitchReminder')){el('pitchReminder').style.display='block';window.sgPitchReminderShown=true;setTimeout(()=>{if(el('pitchReminder'))el('pitchReminder').style.display='none'},7000)}el('traceBtn').textContent='CANCEL TRACE';el('traceBtn').className='danger';el('traceBanner').style.display='block';el('finishTrace').disabled=true;status(mainManual?'Manual measurement ON — click the outside corners of the MAIN HOUSE.':'Added-roof trace ON — click the outside corners of the garage or other roof.','warn')}
function addTracePoint(ll){tracePoints.push(ll);let n=tracePoints.length,pt=L.marker(ll,{interactive:false,icon:L.divIcon({className:'',html:`<div class="point-label">${n}</div>`,iconAnchor:[12,12]})}).addTo(map);tempTraceLayers.push(pt);redrawTraceLine();const ready=tracePoints.length>=3;el('finishTrace').disabled=!ready;if(ready){const action=((manualOverrideMode||fallbackMode)&&structures.length===0&&manualPlanes.length===0)?'FINISH MEASUREMENT':'SAVE & ADD ROOF';if(el('manualRoofHelp'))el('manualRoofHelp').innerHTML=`<b>✓ Roof traced.</b> Confirm the pitch, then click <b>${action}</b>.`;status('Roof traced — confirm pitch, then save.','ok')}}
function redrawTraceLine(){tempTraceLayers.filter(x=>x._traceLine).forEach(x=>map.removeLayer(x));tempTraceLayers=tempTraceLayers.filter(x=>!x._traceLine);if(tracePoints.length>=2){let c=[...tracePoints];if(tracePoints.length>=3)c.push(tracePoints[0]);let l=L.polyline(c,{color:'#d97706',weight:4,dashArray:'6,5'}).addTo(map);l._traceLine=true;tempTraceLayers.push(l)}}
function clearTempTrace(){tempTraceLayers.forEach(x=>{try{map.removeLayer(x)}catch(e){}});tempTraceLayers=[];if(traceSavePopup){try{map.closePopup(traceSavePopup)}catch(e){}traceSavePopup=null}}
function cancelCurrentTrace(){traceMode=false;tracePoints=[];clearTempTrace();setTraceControls(false);const mainManual=(manualOverrideMode||fallbackMode)&&structures.length===0&&manualPlanes.length===0;el('traceBtn').textContent=mainManual?'START MAIN HOUSE MEASUREMENT':'ADD / REMEASURE GARAGE OR OTHER ROOF';el('traceBtn').className='orange';el('traceBanner').style.display='none';el('finishTrace').disabled=true}
function undoPoint(){if(!traceMode||!tracePoints.length)return;let keep=tracePoints.slice(0,-1);tracePoints=[];clearTempTrace();keep.forEach(addTracePoint)}
function finishTrace(){
 if(tracePoints.length<3)return;
 let pitch=Number(el('pitchDeg').value||0);
 if(pitch<0||pitch>=80){alert('Enter a pitch from 0 to 79 degrees.');return}
 let flat=localPolygonAreaM2(tracePoints),surface=flat/Math.cos(pitch*Math.PI/180)*10.76391041671;
 let plane={points:tracePoints.map(p=>({lat:p.lat,lng:p.lng})),pitch_degrees:pitch,surface_sqft:surface};
 manualPlanes.push(plane);
 let poly=L.polygon(plane.points,{color:'#d97706',weight:4,fillColor:'#f59e0b',fillOpacity:.16}).addTo(map),
     c=poly.getBounds().getCenter(),
     lab=L.marker(c,{interactive:false,icon:L.divIcon({className:'',html:`<div class="manual-label">M${manualPlanes.length} • ${pitch.toFixed(1)}° • ${fmt(surface)} ft²</div>`,iconAnchor:[65,10]})}).addTo(map);
 manualLayers.push(poly,lab);
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
 if(manualLayers.length>=2){map.removeLayer(manualLayers.pop());map.removeLayer(manualLayers.pop())}
 if(el('measureSource'))el('measureSource').value=manualPlanes.length?(structures.length?'hybrid':'manual'):(structures.length?'google':'manual');
 renderSummary();
}
function clearManual(){
 const mainStage=(manualOverrideMode||fallbackMode)&&structures.length===0&&manualPlanes.length===0;
 if(traceMode){tracePoints=[];clearTempTrace();if(el('finishTrace'))el('finishTrace').disabled=true;status(mainStage?'Main-house drawing cleared. Click the roof corners again.':'Added-roof drawing cleared. The saved main house and other roofs were not changed.','ok');return}
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
function currentJobPrice(){const jp=el('jobPrice');const raw=jp?jp.value:'';const v=parseFloat(raw);if(Number.isFinite(v)&&v>=0)return v;const fallback=parseFloat((el('price')&&el('price').value)||0);return Number.isFinite(fallback)&&fallback>=0?fallback:0}
function priceCalc(){let area=estimateArea(),price=currentJobPrice(),mode=el('pricingMode').value,disc=Number(el('discountPct').value||0),gst=Number(el('gst').value||0),pst=Number(el('pst').value||0),subtotal=area*price,extraDescription=(el('extraServiceDescription')?.value||'').trim(),extraAmount=Math.max(0,Number(el('extraServiceAmount')?.value||0)),discount=0,taxBase=subtotal+extraAmount,gstAmt=0,pstAmt=0,total=0;if(mode==='discount'){discount=subtotal*(disc/100);taxBase=subtotal-discount+extraAmount;gstAmt=taxBase*gst/100;pstAmt=taxBase*pst/100;total=taxBase+gstAmt+pstAmt}else if(mode==='included'){total=subtotal+extraAmount;taxBase=total/(1+(gst+pst)/100);gstAmt=taxBase*gst/100;pstAmt=taxBase*pst/100}else{taxBase=subtotal+extraAmount;gstAmt=taxBase*gst/100;pstAmt=taxBase*pst/100;total=taxBase+gstAmt+pstAmt}return{area,price,mode,disc,subtotal,extraDescription,extraAmount,discount,taxBase,gst,pst,gstAmt,pstAmt,total}}
function confidence(){return []}
function pitchLabel(deg){const d=Number(deg||0);if(!d)return '—';const rise=12*Math.tan(d*Math.PI/180);const rounded=Math.round(rise*2)/2;return `${d.toFixed(1)}° (approx. ${Number.isInteger(rounded)?rounded.toFixed(0):rounded.toFixed(1)}/12)`}
function pitchRiseLabel(deg){const d=Number(deg||0);if(!d)return '—';const rise=12*Math.tan(d*Math.PI/180);const rounded=Math.round(rise*2)/2;return `${Number.isInteger(rounded)?rounded.toFixed(0):rounded.toFixed(1)}/12`}
function structurePitchSummary(st){if(!st||!st.segments||!st.segments.length)return {complex:false,label:'—',detail:''};const vals=st.segments.map(x=>Number(x.pitch_degrees||0)).filter(x=>x>0);if(!vals.length)return {complex:false,label:'—',detail:''};const avg=vals.reduce((a,b)=>a+b,0)/vals.length,min=Math.min(...vals),max=Math.max(...vals);const rises=[...new Set(vals.map(pitchRiseLabel))];const complex=vals.length>=6&&(max-min>=8||rises.length>=3);if(complex)return {complex:true,label:'Multiple Roof Pitches',detail:`${pitchRiseLabel(min)}–${pitchRiseLabel(max)} (${min.toFixed(1)}°–${max.toFixed(1)}°)`};return {complex:false,label:pitchLabel(avg),detail:`Average of ${vals.length} Google roof segment${vals.length===1?'':'s'}`}}
function updateJobSummaryBar(calc,roofCount){
 const p=el('jsProperty'),r=el('jsRoofs'),a=el('jsArea'),t=el('jsTotal');if(!p||!r||!a||!t)return;
 const full=(el('address')&&el('address').value?el('address').value:'').trim();
 const typed=[el('streetAddress')?.value,el('cityTown')?.value,el('propertyProvince')?.value].filter(Boolean).join(', ');
 p.textContent=full||typed||'No property loaded';
 const has=calc&&Number(calc.area)>0;
 r.textContent=has?String(roofCount||1):'—';
 a.textContent=has?fmt(calc.area)+' ft²':'—';
 t.textContent=has?money(calc.total):'—';
}
function updateProgressSteps(){
 const measured=priceCalc().area>0;
 const verified=!!(el('propertyVerify')&&el('propertyVerify').style.display!=='none'&&(el('propertyVerify').textContent||'').includes('verified'));
 const customerReady=!!((el('customerName')?.value||'').trim());
 const estimateOpen=document.body.classList.contains('report-open');
 let current=1;if(verified)current=2;if(measured)current=3;if(measured&&customerReady)current=5;if(estimateOpen)current=5;
 for(let i=1;i<=5;i++){const c=el('progress'+i);if(!c)continue;c.classList.remove('done','current');const n=c.querySelector('.stepnum');if(i<current){c.classList.add('done');if(n)n.textContent='✓'}else if(i===current){c.classList.add('current');if(n)n.textContent=String(i)}else{if(n)n.textContent=String(i)}}
 // Price is complete once a valid measured quote exists; Customer becomes current before Estimate.
 if(measured&&!customerReady){const p3=el('progress3'),p4=el('progress4');if(p3){p3.classList.add('done');p3.classList.remove('current');const n=p3.querySelector('.stepnum');if(n)n.textContent='✓'}if(p4){p4.classList.add('current');const n=p4.querySelector('.stepnum');if(n)n.textContent='4'}}
}
function renderSummary(){if(!el('summary'))return;let g=googleTotal(),m=manualTotal(),coverage=Number(el('coverage').value||330),src=el('measureSource')?el('measureSource').value:'google',calc=priceCalc(),gallons=coverage?calc.area/coverage:0;let pureManual=src==='manual'&&m>0,hasMeasurement=calc.area>0,roofCount=pureManual?manualPlanes.length:structures.length+(src==='hybrid'?manualPlanes.length:0);if(el('createEstimateBtn'))el('createEstimateBtn').disabled=!hasMeasurement;updateJobSummaryBar(calc,roofCount);let mainPitch=structures.length?structurePitchSummary(structures[0]):null;let html=`<div class="section"><h3>Property Summary</h3><div class="metric-grid"><div class="metric">${pureManual?'Manual Roof Area':'Google Roof Area'}<b>${fmt(pureManual?m:g)} ft²</b></div><div class="metric">Roofs in Quote<b>${roofCount}</b></div>${!pureManual&&mainPitch&&mainPitch.label!=='—'?`<div class="metric">${mainPitch.complex?'Roof Pitch':'Main Roof Pitch'}<b>${mainPitch.label}</b>${mainPitch.detail?`<span class="small" style="display:block;margin-top:3px">${mainPitch.detail}</span>`:''}</div>`:''}</div>${m&&!pureManual?`<div class="metric" style="margin-top:7px">Added Roof<b>+ ${fmt(m)} ft²</b></div>`:''}</div>`;structures.forEach((s,i)=>{let ps=structurePitchSummary(s);html+=`<div class="structure"><div class="structure-head"><div><span class="dot ${i===0?'house-dot':'garage-dot'}"></span><b>${s.label}</b></div><b>${fmt(s.total_roof_sqft)} ft²</b></div><div class="small">${s.segment_count} roof segments • ${ps.complex?`Multiple pitches ${ps.detail}`:`Avg pitch ${ps.label}`} • ${s.imagery_quality||'—'} quality • Imagery ${s.imagery_date||'—'}</div></div>`});let suspiciousGoogleRoof=!pureManual&&structures.length===1&&g>0&&g<1000;if(suspiciousGoogleRoof){html+=`<div class="warning" style="margin-top:10px"><b>⚠ POSSIBLE INCOMPLETE ROOF MEASUREMENT</b><br>Google returned a small roof measurement. Trees, shadows or limited aerial imagery can sometimes prevent the entire roof from being identified. Review the aerial carefully before creating the estimate. If the full roof cannot be clearly identified, an on-site assessment may be required.</div>`}if(pureManual){manualPlanes.forEach((p,i)=>{html+=`<div class="structure"><div class="structure-head"><div><span class="dot manual-dot"></span><b>${manualPlanes.length===1?'Manual Roof':'Manual Roof '+(i+1)}</b></div><b>${fmt(p.surface_sqft)} ft²</b></div><div class="small">Dealer traced • ${p.pitch_degrees.toFixed(1)}° pitch confirmed</div></div>`})}html+=`<div class="section"><h3>Quote Measurement</h3><input id="measureSource" type="hidden" value="${src}"><input id="adjustedArea" type="hidden" value="${src==='adjusted'?calc.area:''}"><div class="${hasMeasurement?'good':'warning'}"><b>${hasMeasurement?(src==='hybrid'?'✓ Google Measurement + Added Roof':src==='manual'?'✓ Dealer Manual Measurement':'✓ Google Automatic Measurement — pitch included'):'Manual measurement required'}</b><br>${hasMeasurement?(src==='hybrid'?`${fmt(g)} ft² Google + ${fmt(m)} ft² added = <b>${fmt(calc.area)} ft² total</b>`:`${fmt(calc.area)} ft² is being used for this estimate.`):'Trace the shingled roof around the customer property pin to unlock pricing and the customer estimate.'}${hasMeasurement&&src!=='manual'&&adjustedOutline?'<br><b>Customer outline adjusted — measurement and price unchanged.</b>':''}</div></div>`;html+=`<div class="section"><h3>Dealer-Only Calculation</h3><div class="calc"><div>Estimate measurement</div><div>${fmt(calc.area)} ft²</div><div>Coverage per gallon</div><div>${fmt(coverage)} ft²</div><div>Estimated product required</div><div>${gallons.toFixed(1)} gal</div><div>Price per sq. ft.</div><div>${money(calc.price)}</div></div></div><div class="estimate"><b>Dealer Estimate Preview</b><div class="line"><span>Subtotal before tax</span><b>${money(calc.taxBase)}</b></div>${calc.discount?`<div class="line"><span>Promotion discount</span><b>-${money(calc.discount)}</b></div>`:''}${calc.mode==='included'?`<div class="line"><span>Pricing</span><b>Taxes Included</b></div>`:`<div class="line"><span>Sales Tax (${calc.gst}%)</span><b>${money(calc.gstAmt)}</b></div>${calc.pst?`<div class="line"><span>Additional Tax (${calc.pst}%)</span><b>${money(calc.pstAmt)}</b></div>`:''}`}<div class="line grand"><span>Total Estimate</span><span>${money(calc.total)}</span></div></div>`;let w=confidence();html+=!hasMeasurement?`<div class="warning"><b>Finish the manual roof trace first.</b><br>Pricing and estimate creation stay locked until a roof area has been measured.</div>`:(w.length?`<div class="warning"><b>Review before sending:</b><br>${w.map(x=>'• '+x).join('<br>')}</div>`:`<div class="good"><b>Measurement looks ready.</b></div>`);el('summary').innerHTML=html;if(el('appliedJobPrice'))el('appliedJobPrice').innerHTML=`Quote is using <b>${money(calc.price)} / sq. ft.</b>`;updateUsage();updateProgressSteps()}

function resetReportForNewProperty(){
 document.body.classList.remove('report-open');
 const overlay=el('reportOverlay');if(overlay)overlay.style.display='none';
 if(customerMap){try{customerMap.remove()}catch(e){}customerMap=null}
 customerRgbLayer=null;customerOverlays=[];quoteSnapshot=null;reportOutlines={};reportOutlineTarget=null;reportOutlineEditMode=false;reportOutlinePoints=[];reportOutlineTemp=[];reportCloseArmedAt=0;estimateOpenInProgress=false;pdfInProgress=false;if(customerMapBuildTimer){clearTimeout(customerMapBuildTimer);customerMapBuildTimer=null}if(el('createEstimateBtn'))el('createEstimateBtn').disabled=false;if(el('downloadPdfBtn'))el('downloadPdfBtn').disabled=false;
 const report=document.querySelector('#reportOverlay .report');if(report)report.classList.remove('estimate-editing');
}
function resetMeasurementForNewProperty(){
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
 if(!s)return null;
 const nums=s.match(/[-+]?\d+(?:\.\d+)?/g);
 if(!nums||nums.length<2)return null;
 let lat=Number(nums[0]),lng=Number(nums[1]);
 if(!Number.isFinite(lat)||!Number.isFinite(lng))return null;
 const idx=s.indexOf(nums[1]),a=s.slice(0,idx),b=s.slice(idx);
 if(/\bS\b/.test(a))lat=-Math.abs(lat); else if(/\bN\b/.test(a))lat=Math.abs(lat);
 if(/\bW\b/.test(b))lng=-Math.abs(lng); else if(/\bE\b/.test(b))lng=Math.abs(lng);
 if(Math.abs(lat)>90||Math.abs(lng)>180)return null;
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
 if(el('address'))el('address').value=normalized;
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

async function loadProperty(){
 const enteredStreet=(el('streetAddress')?.value||'').trim(),enteredCity=(el('cityTown')?.value||'').trim(),enteredProvince=propertyLookupProvince(),enteredNumber=enteredStreetNumber();
 const cc=coordinatesEntered();
 if(!cc&&(!enteredStreet||!enteredCity||!enteredProvince)){status('Enter the street address, City and State/Province. ZIP/postal code is not required.','error');return}
 // Freeze exactly what the dealer entered BEFORE any report/measurement reset can change UI state.
 const authoritativeAddress=cc?(cc.lat.toFixed(6)+','+cc.lng.toFixed(6)):[enteredStreet,enteredCity,enteredProvince,propertyCountryFromProvince(enteredProvince)].join(', ');
 resetReportForNewProperty();exactPinDisplay=false;if(el('address'))el('address').value=authoritativeAddress;syncPropertyProvince();
 if(cc&&el('googleMatch'))el('googleMatch').textContent='Loading exact coordinates: '+authoritativeAddress;
const key="{{GOOGLE_MAPS_API_KEY}}",address=authoritativeAddress;if(!key||!address){status('Enter API key and address.','error');return}
 try{
  status('Loading property…');showLoad(true);resetMeasurementForNewProperty();locateRoofMode=false;fallbackMode=false;setManualCorrectionLayout(false);showSolarFallback(false);if(propertyMarker){try{map.removeLayer(propertyMarker)}catch(e){}propertyMarker=null}
  removeStaleAerialLayers();
  const payload=cc?{key,address,latitude:cc.lat,longitude:cc.lng,direct_coordinates:true}:{key,address,expected_city:enteredCity,expected_province:enteredProvince,expected_street_number:enteredNumber};
  let r=await fetch('/property',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}),d=await r.json();if(!r.ok)throw new Error(d.user_error||d.error||'Property request failed');
  sessionToken=d.token;exactPinDisplay=!!d.exact_pin_display;lastLoadedStreet=el('streetAddress')?.value.trim()||'';applyAddressParts(d.parts);if(d.center)setPropertyMarker(d.center.latitude,d.center.longitude);else if(d.anchor)setPropertyMarker(d.anchor.latitude,d.anchor.longitude);if(el('addressAutoStatus'))el('addressAutoStatus').textContent='✓ '+(d.formatted_address||buildPropertyAddress());if(el('googleMatch'))el('googleMatch').textContent='Google matched: '+(d.formatted_address||buildPropertyAddress());
  const verifyEl=el('propertyVerify');if(verifyEl){verifyEl.style.display='none';verifyEl.textContent=''}
  try{
    if(cc){if(verifyEl){verifyEl.style.display='block';verifyEl.style.color='#176b43';verifyEl.textContent='✓ Using exact dropped-pin coordinates — address matching bypassed.'}}
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
        if(el('cityTown'))el('cityTown').value='';if(el('propertyProvince'))el('propertyProvince').value='';if(el('postalCode'))el('postalCode').value='';if(el('address'))el('address').value='';
        status('Loading the confirmed nearby property…','warn');return loadProperty();
      }
      verifyEl.style.color='#176b43';verifyEl.textContent='✓ Dealer confirmed Google matched property: '+matched;
    }
    else if(verifyEl&&vr.ok){verifyEl.style.display='block';verifyEl.style.color='#176b43';verifyEl.textContent='✓ Property address verified'}
    }
  }catch(e){if(verifyEl&&!cc)verifyEl.style.display='none'}
  skipAddressConflictOnce=false;
  let prov=detectProvince(d.formatted_address||address);if(prov){if(el('propertyProvince'))el('propertyProvince').value=prov;syncPropertyProvince()}
  el('street').style.visibility='visible';el('street').src='/street/'+sessionToken+'?v='+Date.now();el('streetMeta').textContent=d.street_date?('Street View imagery: '+d.street_date):'Actual Street View';usage.property++;
  if(d.fallback){
    structures=[];setManualCorrectionLayout(true);setManualUi(true);if(el('measureSource'))el('measureSource').value='manual';
    let aerialLoaded=false;
    try{
      // Manual mode always uses one stable Static Maps satellite image. This avoids
      // the rectangular Solar GeoRaster/no-data box that could appear after zooming.
      let fb=await loadFallbackAerial(sessionToken);fallbackLayer=fb.layer;fallbackBounds=fb.bounds;removeStaleAerialLayers(fallbackLayer);frameAerial(map,fb.bounds,0);aerialLoaded=true
    }catch(aerialErr){
      const reason=(aerialErr&&aerialErr.message)?aerialErr.message:'Google satellite fallback could not load.';
      showSolarFallback(true,'Google automatic measurement is unavailable and the manual aerial could not load. '+reason);
      if(el('garageGuide'))el('garageGuide').innerHTML='<b>Automatic measurement unavailable.</b> Manual aerial could not load. The message above shows the Google response so this can be corrected without guessing.';
      renderSummary();status('Manual aerial could not load: '+reason,'error');return;
    }
    showSolarFallback(true,'Google does not have an automatic roof measurement for this property. Manual measurement is required. Trace the shingled roof below and confirm its pitch.');
    renderSummary();
    if(el('garageGuide'))el('garageGuide').innerHTML='<b>Manual measurement required.</b> Trace the shingled roof area shown below and confirm the pitch. If imagery appears older, verify the current roof layout before sending the estimate.';
    if(el('measureClicked'))el('measureClicked').disabled=true;if(el('measureClickedTop'))el('measureClickedTop').disabled=true;
    const details=el('manualRoofDetails');if(details)details.open=true;
    if(aerialLoaded){setTimeout(()=>{if(!traceMode)toggleTrace()},80)}
    status('Automatic measurement unavailable — manual roof tracing is ready. Confirm the pitch before saving.','warn');return;
  }
  structures=[{...d.main,label:'Main House'}];setManualCorrectionLayout(false);setManualUi(false);if(el('measureSource'))el('measureSource').value='google';let rgb=exactPinDisplay?await loadExactPinAerial(sessionToken):await loadRaster('/rgb/'+sessionToken);rgbLayer=rgb.layer;mainBounds=rgb.bounds;frameAerial(map,rgb.bounds,0);roofMask=await loadRoofMask('/mask/'+sessionToken);d.main.outline=outlineFromMask(roofMask,d.main.latitude,d.main.longitude);structures[0].outline=d.main.outline;if(!exactPinDisplay){await loadStandardWideAerial()}drawSegments(d.main,'house');if(exactPinDisplay)frameAerial(map,rgb.bounds,0);renderSummary();if(el('garageGuide'))el('garageGuide').innerHTML='<b>Main house measured.</b> If there is another roof to include, click <b>+ ADD GARAGE / OTHER ROOF</b>, then click once on that roof. It will measure automatically.';if(el('measureClicked'))el('measureClicked').disabled=false;if(el('measureClickedTop'))el('measureClickedTop').disabled=false;status('Main house measured. Use + Add Garage / Other Roof if needed.','ok')
 }catch(e){status(e.message,'error')}finally{showLoad(false)}
}
function startGarageMode(){if(!sessionToken){status('Load the property first.','error');return}if(!structures.length){if(manualPlanes.length){garageMode=false;setManualCorrectionLayout(false);setManualUi(false);const details=el('manualRoofDetails');if(details)details.open=true;if(!traceMode)toggleTrace();status('Add Garage / Other Roof — trace the next shingled building, confirm its pitch, then save it.','warn');return}status('Finish the main-house manual measurement first.','warn');return}garageMode=true;clicked=null;if(clickMarker){try{map.removeLayer(clickMarker)}catch(e){}clickMarker=null}if(el('garageGuide'))el('garageGuide').innerHTML='<b>Add Garage / Other Roof is ON.</b> Click once near the centre of the garage, shed or shop roof. It will measure automatically.';status('Click once near the centre of the extra roof to measure it automatically.','warn')}
async function measureClicked(){if(!sessionToken||!clicked){status('Click the centre of the extra structure first.','error');return}try{status('Measuring selected structure…');let r=await fetch('/structure',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:sessionToken,latitude:clicked.lat,longitude:clicked.lng})}),d=await r.json();if(!r.ok)throw new Error(d.error||'Structure request failed');let dup=structures.some(s=>Math.abs(s.latitude-d.latitude)<.00003&&Math.abs(s.longitude-d.longitude)<.00003);if(dup){status('That building is already measured. Click nearer the centre of a different structure.','error');return}d.label=structures.length===1?'Detached Garage':`Extra Structure ${structures.length}`;d.outline=outlineFromMask(roofMask,d.latitude,d.longitude);structures.push(d);drawSegments(d,'garage');fitEntireQuote(map);usage.structures++;renderSummary();if(clickMarker){try{map.removeLayer(clickMarker)}catch(e){}clickMarker=null}clicked=null;if(el('garageGuide'))el('garageGuide').innerHTML=`<b>${d.label} is already saved in this quote.</b> To add another roof, click <b>+ ADD GARAGE / OTHER ROOF</b> again.`;if(el('garageSavedConfirm')){el('garageSavedConfirm').style.display='block';el('garageSavedConfirm').innerHTML=`<b>✓ ${d.label} SAVED TO QUOTE — ${fmt(d.total_roof_sqft)} ft² INCLUDED</b><br><span class="small">No other Save button is required. It is already included in Roofs in Quote and the estimate total.</span>`}status(`${d.label} saved to quote — ${fmt(d.total_roof_sqft)} ft² included.`,'ok')}catch(e){status('Google could not automatically match that extra roof. Click closer to its centre or add it manually.','warn')}}
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
 quoteSnapshot={structures:clone(structures),manualPlanes:clone(manualPlanes),measureSource:(el('measureSource')&&el('measureSource').value)||'google'};
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
function renderReportOutlineTargetButtons(){
 const box=el('reportOutlineTargetButtons');if(!box)return;
 const snap=quoteSnapshot||captureQuoteSnapshot();let html='';
 (snap.structures||[]).forEach((st,i)=>{
   const key=`structure-${i}`;
   const label=i===0?'EDIT MAIN HOUSE OUTLINE':`EDIT ${reportTargetLabel(key)} OUTLINE`;
   html+=`<button class="orange" onclick="startReportOutlineEdit('${key}')">${label}</button>`;
 });
 (snap.manualPlanes||[]).forEach((p,i)=>{
   const key=`manual-${i}`;
   html+=`<button class="orange" onclick="startReportOutlineEdit('${key}')">EDIT ${reportTargetLabel(key)} OUTLINE</button>`;
 });
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
     try{await buildInteractiveCustomerMap()}catch(e){console.error(e);if(el('reportOutlineHelpTop'))el('reportOutlineHelpTop').textContent='Could not open outline editor. Close and reopen the estimate, then try again.';return}
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
function cancelReportOutlineEdit(){reportOutlineEditMode=false;reportOutlinePoints=[];clearReportOutlineTemp();document.querySelector('#reportOverlay .report')?.classList.remove('estimate-editing');setReportOutlineButtons(false);buildCustomerMap().catch(e=>console.error(e))}
function undoReportOutlinePoint(){if(!reportOutlineEditMode||!reportOutlinePoints.length)return;reportOutlinePoints.pop();drawReportOutlineTemp();setReportOutlineButtons(true)}
async function saveReportOutline(){if(!reportOutlineEditMode||reportOutlinePoints.length<3||!reportOutlineTarget)return;const target=reportOutlineTarget,label=reportTargetLabel(target);reportOutlines[target]=reportOutlinePoints.map(p=>[p.lat,p.lng]);reportOutlineEditMode=false;reportOutlinePoints=[];clearReportOutlineTemp();document.querySelector('#reportOverlay .report')?.classList.remove('estimate-editing');await buildCustomerMap();setReportOutlineButtons(false);if(el('reportOutlineHelpTop'))el('reportOutlineHelpTop').textContent=`✓ ${label} outline saved. You can now edit another roof. Measurements and price are unchanged.`}

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
 const blob=await r.blob(),obj=URL.createObjectURL(blob);
 try{
   const img=await new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(new Error('Manual report aerial could not be decoded.'));im.src=obj});
   const canvas=document.createElement('canvas');canvas.width=img.naturalWidth||1280;canvas.height=img.naturalHeight||840;canvas.style.width='100%';canvas.style.height='100%';canvas.style.display='block';
   canvas.getContext('2d').drawImage(img,0,0,canvas.width,canvas.height);host.appendChild(canvas);
 }finally{try{URL.revokeObjectURL(obj)}catch(e){}}
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
 customerMap.on('click',reportOutlineClick);
 await new Promise(r=>setTimeout(r,180));
 customerMap.invalidateSize(true);
 let rgb=exactPinDisplay?await loadExactPinAerial(sessionToken,customerMap):(fallbackMode?await loadFallbackAerial(sessionToken,customerMap):await loadRaster('/rgb/'+sessionToken,customerMap));
 customerRgbLayer=rgb.layer;
 customerMap.invalidateSize(true);
 frameAerial(customerMap,rgb.bounds,0);
 await new Promise(r=>setTimeout(r,220));
 customerMap.invalidateSize(true);
 frameAerial(customerMap,rgb.bounds,0);
 const snap=quoteSnapshot||captureQuoteSnapshot();
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
 setReportOutlineButtons(false);
}
async function buildSavedHistoricalSnapshot(){
 const host=el('customerMap');if(!host)return;
 if(customerMap){try{customerMap.remove()}catch(e){}customerMap=null;customerRgbLayer=null;customerOverlays=[]}
 host.innerHTML='';host.style.position='relative';host.style.overflow='hidden';host.style.display='block';
 const snap=quoteSnapshot||captureQuoteSnapshot(),roofs=[];
 (snap.structures||[]).forEach((st,i)=>{
   const pts=st.outline;
   if(Array.isArray(pts)&&pts.length>=3)roofs.push({kind:i===0?'house':'garage',points:pts.map(v=>({lat:Number(v.lat!==undefined?v.lat:v[0]),lng:Number(v.lng!==undefined?v.lng:v[1])}))});
 });
 (snap.manualPlanes||[]).forEach(p=>{
   const pts=p.points;
   if(Array.isArray(pts)&&pts.length>=3)roofs.push({kind:'manual',points:pts.map(v=>({lat:Number(v.lat!==undefined?v.lat:v[0]),lng:Number(v.lng!==undefined?v.lng:v[1])}))});
 });
 if(!roofs.length)throw new Error('Saved estimate has no roof outline for the aerial image.');
 const r=await fetch('/saved-estimate-report-map',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({roofs})});
 if(!r.ok)throw new Error((await r.text())||'Could not rebuild saved estimate aerial.');
 const blob=await r.blob(),obj=URL.createObjectURL(blob);
 try{
   const img=await new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(new Error('Saved estimate aerial could not be decoded.'));im.src=obj});
   const canvas=document.createElement('canvas');canvas.width=img.naturalWidth||1280;canvas.height=img.naturalHeight||840;canvas.style.width='100%';canvas.style.height='100%';canvas.style.display='block';
   canvas.getContext('2d').drawImage(img,0,0,canvas.width,canvas.height);host.appendChild(canvas);
 }finally{try{URL.revokeObjectURL(obj)}catch(e){}}
}

async function buildCustomerMap(){
 if(!sessionToken)return;
 const imageChoice=el('streetViewChoice')?.value||'auto';
 const useAerial=imageChoice!=='none';
 const snap=quoteSnapshot||captureQuoteSnapshot();
 const pureManual=(snap.measureSource==='manual'&&(snap.manualPlanes||[]).length>0&&!(snap.structures||[]).length);
 // V11.6.63 — MANUAL ESTIMATE PIXEL LOCK
 // For a pure dealer-manual quote, do not re-project the saved trace onto a
 // second Leaflet map. Ask Google Static Maps to render the satellite image
 // AND the dealer's saved outline in the same image. Because the imagery and
 // orange path are baked together by Google, the outline cannot drift between
 // manual measurement, customer estimate, and PDF capture.
 if(exactPinDisplay&&useAerial){
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
async function saveEstimateHistory(){
 try{
  const calc=priceCalc(),snap=quoteSnapshot||captureQuoteSnapshot();
  let streetImageData='';
  const imageChoice=(el('streetViewChoice')?.value||'auto');
  if(imageChoice==='auto'&&sessionToken){
   try{
    const sr=await fetch('/street/'+sessionToken+'?save=1');
    if(sr.ok){
     const blob=await sr.blob();
     streetImageData=await new Promise((resolve,reject)=>{const fr=new FileReader();fr.onload=()=>resolve(String(fr.result||''));fr.onerror=()=>reject(new Error('Street View capture failed'));fr.readAsDataURL(blob)});
    }
   }catch(e){console.warn('Street View could not be stored with estimate',e)}
  }
  const payload={customer_name:(el('customerName')?.value||'').trim(),customer_phone:(el('customerPhone')?.value||'').trim(),customer_email:(el('customerEmail')?.value||'').trim(),customer_notes:(el('customerNotes')?.value||'').trim(),extra_service_description:(el('extraServiceDescription')?.value||'').trim(),extra_service_amount:Math.max(0,Number(el('extraServiceAmount')?.value||0)),job_status:'Estimate',scheduled_date:'',completion_date:'',amount_paid:0,address:(el('address')?.value||'').trim(),total_area:Number(calc.area||0),total_price:Number(calc.total||0),quote:snap,pricing:calc,street_meta:(el('streetMeta')?.textContent||''),image_choice:imageChoice,street_image_data:streetImageData};
  const saveKey=[payload.address,payload.customer_name,payload.customer_phone,payload.customer_email,payload.total_area,payload.total_price].join('|');
  if(saveKey===lastHistorySaveKey)return;
  const r=await fetch('/api/estimates',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});if(!r.ok)throw new Error('save failed');
  lastHistorySaveKey=saveKey;
 }catch(e){console.warn('Estimate history save failed',e)}
}
function openEstimateHistory(){el('historyModal').classList.add('open');searchEstimateHistory()}
function closeEstimateHistory(){el('historyModal').classList.remove('open')}
async function searchEstimateHistory(){
 const q=(el('historySearch')?.value||'').trim(),box=el('historyResults');box.innerHTML='<div class="small" style="padding:14px 0">Searching…</div>';
 try{const r=await fetch('/api/estimates?q='+encodeURIComponent(q)),d=await r.json();if(!r.ok)throw new Error(d.error||'Search failed');if(!d.length){box.innerHTML='<div class="small" style="padding:14px 0">No saved estimates found.</div>';return}
 const shown=historyStatusFilter==='All'?d:d.filter(x=>(x.job_status||'Estimate')===historyStatusFilter);
 if(!shown.length){box.innerHTML='<div class="small" style="padding:14px 0">No jobs in this status.</div>';return}
 box.innerHTML=shown.map(x=>`<div class="historyRow"><div><b>${escapeHistory(x.customer_name||'Homeowner')}</b><div class="small">${escapeHistory(x.customer_phone||'')}${x.customer_email?' • '+escapeHistory(x.customer_email):''}</div></div><div><b>${escapeHistory(x.address||'')}</b></div><div>${escapeHistory((x.created_at||'').slice(0,10))}</div><div><b>${money(x.total_price||0)}</b></div><div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center"><select class="jobStatusSelect" aria-label="Job status" onchange="updateJobStatus('${x.id}',this.value)"><option value="Estimate" ${x.job_status==='Estimate'?'selected':''}>Estimate</option><option value="Booked" ${x.job_status==='Booked'?'selected':''}>Booked</option><option value="Completed" ${x.job_status==='Completed'?'selected':''}>Completed</option></select><input class="scheduledDateInput" type="date" title="Scheduled Date" value="${escapeHistory(x.scheduled_date||'')}" onchange="updateScheduledDate('${x.id}',this.value)"><input class="scheduledDateInput" type="date" title="Completion Date" value="${escapeHistory(x.completion_date||'')}" onchange="updateCompletionDate('${x.id}',this.value)"><div class="historyFinance">Paid $<input class="historyMoneyInput" type="number" min="0" step="0.01" value="${Number(x.amount_paid||0).toFixed(2)}" onchange="updateAmountPaid('${x.id}',this.value)"><br><b>Balance: ${money(Math.max(0,Number(x.total_price||0)-Number(x.amount_paid||0)))}</b></div><button class="secondary" onclick="viewSavedEstimate('${x.id}')">CURRENT</button><button class="ghost" onclick="viewEstimateVersions('${x.id}')">VIEW HISTORY</button></div></div>`).join('');
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
function savedVersionCard(v,label,estimateId,versionIndex){
 const p=v.payload||{};
 return `<div style="padding:12px;border:1px solid var(--line);border-radius:10px;margin-top:9px;background:#fff"><div style="display:flex;justify-content:space-between;gap:12px;align-items:start"><div><b>${escapeHistory(label)}</b><div class="small">${escapeHistory((v.saved_at||v.created_at||v.revised_at||'').replace('T',' ').replace('Z',''))}</div></div><div style="font-size:18px;font-weight:900;color:var(--green2)">${money(p.total_price??v.total_price??0)}</div></div><div style="margin-top:7px"><b>${escapeHistory(p.customer_name||v.customer_name||'Homeowner')}</b></div><div class="small">${escapeHistory(p.address||v.address||'')}</div><div class="small">Roof area: ${fmt(p.total_area??v.total_area??0)} ft²${p.customer_phone?' • '+escapeHistory(p.customer_phone):''}${p.customer_email?' • '+escapeHistory(p.customer_email):''}</div><div style="margin-top:10px"><button class="secondary" onclick="openHistoricalEstimate('${estimateId}',${versionIndex})">OPEN ESTIMATE</button></div></div>`;
}
function setSavedField(id,value){const n=el(id);if(n)n.value=value??''}
async function openHistoricalEstimate(estimateId,versionIndex){
 try{
  const r=await fetch('/api/estimates/'+encodeURIComponent(estimateId)+'/versions'),d=await r.json();if(!r.ok)throw new Error(d.error||'History failed');
  const v=versionIndex<0?d.current:(d.revisions||[])[versionIndex];if(!v)throw new Error('Version not found');
  const p=v.payload||{},snap=p.quote||{},pr=p.pricing||{};
  structures=JSON.parse(JSON.stringify(snap.structures||[]));
  manualPlanes=JSON.parse(JSON.stringify(snap.manualPlanes||[]));
  if(!structures.length&&!manualPlanes.length)throw new Error('Saved version has no roof snapshot');
  if(el('measureSource'))el('measureSource').value=snap.measureSource||((manualPlanes.length&&!structures.length)?'manual':(manualPlanes.length?'hybrid':'google'));
  setSavedField('address',p.address||'');
  setSavedField('customerName',p.customer_name||'');
  setSavedField('customerPhone',p.customer_phone||'');
  setSavedField('customerEmail',p.customer_email||'');
  setSavedField('customerNotes',p.customer_notes||'');
  setSavedField('extraServiceDescription',p.extra_service_description||'');
  setSavedField('extraServiceAmount',Number(p.extra_service_amount||0).toFixed(2));
  if(Number.isFinite(Number(pr.price)))setSavedField('jobPrice',Number(pr.price).toFixed(2));
  if(pr.mode)setSavedField('pricingMode',pr.mode);
  if(Number.isFinite(Number(pr.disc)))setSavedField('discountPct',pr.disc);
  if(Number.isFinite(Number(pr.gst)))setSavedField('gst',pr.gst);
  if(Number.isFinite(Number(pr.pst)))setSavedField('pst',pr.pst);
  if(p.image_choice)setSavedField('streetViewChoice',p.image_choice);
  if(el('streetMeta'))el('streetMeta').textContent=p.street_meta||'Saved estimate';
  savedStreetImageData=String(p.street_image_data||'');

  // Reset only report UI state. The roof measurement engine is not called.
  document.body.classList.remove('report-open');
  if(el('reportOverlay'))el('reportOverlay').style.display='none';
  if(customerMap){try{customerMap.remove()}catch(e){}customerMap=null}
  customerRgbLayer=null;customerOverlays=[];reportOutlines={};reportOutlineTarget=null;
  reportOutlineEditMode=false;reportOutlinePoints=[];clearReportOutlineTemp();
  estimateOpenInProgress=false;
  if(customerMapBuildTimer){clearTimeout(customerMapBuildTimer);customerMapBuildTimer=null}
  quoteSnapshot={structures:JSON.parse(JSON.stringify(structures)),manualPlanes:JSON.parse(JSON.stringify(manualPlanes)),measureSource:(snap.measureSource||el('measureSource')?.value||'google')};

  closeEstimateHistory();
  // Let the modal finish closing before opening the report overlay.
  await new Promise(resolve=>setTimeout(resolve,60));
  await showCustomerEstimate(true,(v.saved_at||v.created_at||v.revised_at||'').slice(0,10));
 }catch(e){
  console.error('Historical estimate open failed:',e);
  const box=el('historyResults');
  if(box)box.insertAdjacentHTML('afterbegin',`<div class="error" style="padding:10px 0">Could not open this saved estimate: ${escapeHistory(e.message||'unknown error')}</div>`);
  status('Could not reopen that saved estimate.','error')
 }
}
async function viewSavedEstimate(id){
 try{const r=await fetch('/api/estimates/'+encodeURIComponent(id)),d=await r.json();if(!r.ok)throw new Error(d.error||'Not found');const p=d.payload||{};el('historyResults').innerHTML=`<div style="padding:12px;border:1px solid var(--line);border-radius:10px"><button class="ghost" onclick="searchEstimateHistory()">← BACK TO RESULTS</button><h3>${escapeHistory(p.customer_name||'Homeowner')}</h3><div><b>Property:</b> ${escapeHistory(p.address||'')}</div><div><b>Phone:</b> ${escapeHistory(p.customer_phone||'—')}</div><div><b>Email:</b> ${escapeHistory(p.customer_email||'—')}</div><div><b>Customer / Job Notes:</b> ${escapeHistory(p.customer_notes||'—')}</div><div><b>Job Status:</b> ${escapeHistory(p.job_status||'Estimate')}</div><div><b>Scheduled Date:</b> ${escapeHistory(p.scheduled_date||'—')}</div><div><b>Completion Date:</b> ${escapeHistory(p.completion_date||'—')}</div><div><b>Amount Paid:</b> ${money(Number(p.amount_paid||0))}</div><div><b>Balance Due:</b> ${money(Math.max(0,Number(p.total_price||0)-Number(p.amount_paid||0)))}</div><div><b>Roof area:</b> ${fmt(p.total_area||0)} ft²</div><div><b>Estimate:</b> ${money(p.total_price||0)}</div><div><b>Date:</b> ${escapeHistory((d.created_at||'').slice(0,10))}</div><div style="margin-top:12px"><button class="secondary" onclick="viewEstimateVersions('${id}')">VIEW HISTORY</button></div></div>`}catch(e){status('Could not open that saved estimate.','error')}
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

async function showCustomerEstimate(historicalMode=false,historicalDate=''){
 if((!historicalMode&&!sessionToken)||(!structures.length&&!manualPlanes.length)){status('Load and measure a property first.','error');return}
 if(estimateOpenInProgress||document.body.classList.contains('report-open'))return;
 estimateOpenInProgress=true;
 const createBtn=el('createEstimateBtn');if(createBtn)createBtn.disabled=true;
 quoteSnapshot=captureQuoteSnapshot(); reportOutlines={}; reportOutlineTarget=null; reportOutlineEditMode=false; reportOutlinePoints=[]; clearReportOutlineTemp();
 let calc=priceCalc(),snap=quoteSnapshot||captureQuoteSnapshot(),reportStructures=snap.structures||[],reportManual=snap.manualPlanes||[],src=snap.measureSource||'google',reportManualTotal=reportManual.reduce((a,p)=>a+Number(p.surface_sqft||0),0),manualUsed=(src==='manual'&&reportManualTotal>0),hybridUsed=(src==='hybrid'&&reportManualTotal>0);
 el('rAddress').textContent=el('address').value;
 el('rDate').textContent=historicalDate?new Date(historicalDate+'T12:00:00').toLocaleDateString('en-US',{year:'numeric',month:'long',day:'numeric'}):new Date().toLocaleDateString('en-US',{year:'numeric',month:'long',day:'numeric'});if(el('rCustomerName'))el('rCustomerName').textContent=(el('customerName')?.value||'').trim()||'Homeowner';if(el('rCustomerPhone'))el('rCustomerPhone').textContent=(el('customerPhone')?.value||'').trim();if(el('rCustomerEmail'))el('rCustomerEmail').textContent=(el('customerEmail')?.value||'').trim();
 const dealerName=(el('dealerName')?el('dealerName').value.trim():'')||'';
 const dealerCompany=(el('dealerCompany')?el('dealerCompany').value.trim():'')||dealerName||'ShingleXtra';
 const dealerEmail=(el('dealerEmail')?el('dealerEmail').value.trim():'')||'';
 const dealerWebsite=(el('dealerWebsite')?el('dealerWebsite').value.trim():'')||'';
 const dealerAddress=(el('dealerAddress')?el('dealerAddress').value.trim():'')||'';
 el('rPhone').textContent=el('dealerPhone').value;if(el('rDealerCompany'))el('rDealerCompany').textContent=dealerCompany;if(el('rDealerName'))el('rDealerName').textContent=(dealerName&&dealerName!==dealerCompany)?dealerName:'';if(el('rDealerEmail'))el('rDealerEmail').textContent=dealerEmail;if(el('rDealerEmailWrap'))el('rDealerEmailWrap').style.display=dealerEmail?'inline':'none';if(el('rDealerWebsite'))el('rDealerWebsite').textContent=dealerWebsite;if(el('rDealerAddress'))el('rDealerAddress').textContent=dealerAddress;if(el('rDealerAddressWrap'))el('rDealerAddressWrap').style.display=dealerAddress?'inline':'none';if(el('rDealerLogo')){const rdl=el('rDealerLogo'),dls=dealerLogoSrc();rdl.src=dls;rdl.classList.toggle('defaultShingleXtraLogo',dls==='/static/shinglextra-logo-inline.jpg')}

 let imageChoice=((el('streetViewChoice')&&el('streetViewChoice').value)||'auto'),useSavedStreet=historicalMode&&imageChoice==='auto'&&!!savedStreetImageData,useStreet=(!historicalMode&&imageChoice==='auto')||useSavedStreet,useAerial=imageChoice!=='none';
 if(el('streetPlaceholder'))el('streetPlaceholder').style.display=useStreet?'none':'flex';
 if(el('customerMap'))el('customerMap').style.display=useAerial?'block':'none';
 if(el('customerMapPlaceholder'))el('customerMapPlaceholder').style.display=useAerial?'none':'flex';
 if(el('rStreet')){
   el('rStreet').style.display=useStreet?'block':'none';
   if(useSavedStreet)el('rStreet').src=savedStreetImageData;
   else if(useStreet)el('rStreet').src='/street/'+sessionToken+'?v='+Date.now();
 }
 if(el('rStreetMeta'))el('rStreetMeta').textContent=useStreet?(historicalMode?(el('streetMeta').textContent||'Saved Google Street View'):el('streetMeta').textContent):(imageChoice==='none'?'Property imagery omitted':(historicalMode?'Saved property aerial and roof outline':'ShingleXtra property assessment'));

 let prop=`<div class="metric-grid"><div class="metric">Treatment Area<b>${fmt(calc.area)} ft²</b></div><div class="metric">Roofs in Quote<b>${manualUsed?reportManual.length:reportStructures.length+(hybridUsed?reportManual.length:0)}</b></div></div>`;
 if(manualUsed){
   prop+=`<div class="structure"><div class="structure-head"><b>Dealer Manual Measurement</b><b>${fmt(reportManualTotal)} ft²</b></div><div class="small">Only the shingle roof planes traced by the dealer are included in this estimate.</div></div>`;
 }else{
   reportStructures.forEach((st,i)=>{
     let ps=structurePitchSummary(st);
     prop+=`<div class="structure"><div class="structure-head"><b>${st.label}</b><b>${fmt(st.total_roof_sqft)} ft²</b></div><div class="small">Google measured • ${ps.complex?`Multiple roof pitches ${ps.detail}`:`Avg pitch ${ps.label}`} • ${st.imagery_quality||'—'} quality</div></div>`;
   });
   if(hybridUsed){reportManual.forEach((p,i)=>{prop+=`<div class="structure"><div class="structure-head"><b>${reportManual.length===1?'Added Roof':'Added Roof '+(i+1)}</b><b>${fmt(p.surface_sqft)} ft²</b></div><div class="small">Dealer traced • ${p.pitch_degrees.toFixed(1)}° pitch used</div></div>`})}
 }
 el('rProperty').innerHTML=prop;

 let price='';
 if(manualUsed){
   price+=`<div class="line"><span>ShingleXtra Roof Treatment — Manual Measurement</span><b>${money(calc.subtotal)}</b></div>`;
 }else{
   const totalArea=calc.area||1;
   structures.forEach(st=>{
     let share=Number(st.total_roof_sqft||0)/totalArea;
     price+=`<div class="line"><span>ShingleXtra — ${st.label}</span><b>${money(calc.subtotal*share)}</b></div>`;
   });
   if(hybridUsed){reportManual.forEach((p,i)=>{let share=Number(p.surface_sqft||0)/totalArea;price+=`<div class="line"><span>ShingleXtra — ${reportManual.length===1?'Added Roof':'Added Roof '+(i+1)}</span><b>${money(calc.subtotal*share)}</b></div>`})}
 }
 if(calc.extraAmount>0)price+=`<div class="line"><span>${escapeHistory(calc.extraDescription||'Additional Services / Repairs')}</span><b>${money(calc.extraAmount)}</b></div>`;
 if(calc.mode==='discount')price+=`<div class="line"><span>Promotion Discount (${calc.disc}%)</span><b>-${money(calc.discount)}</b></div>`;
 if(calc.mode==='included'){
   price+=`<div class="line"><span>Promotional Pricing</span><b>Taxes Included</b></div>`;
 }else{
   price+=`<div class="line"><span>Subtotal Before Tax</span><b>${money(calc.taxBase)}</b></div><div class="line"><span>Sales Tax (${calc.gst}%)</span><b>${money(calc.gstAmt)}</b></div>${calc.pst?`<div class="line"><span>Additional Tax (${calc.pst}%)</span><b>${money(calc.pstAmt)}</b></div>`:''}`;
 }
 price+=`<div class="line grand"><span>TOTAL (USD)</span><span>${money(calc.total)}</span></div>`;
 el('rPricing').innerHTML=price;
 if(!historicalMode)await saveEstimateHistory();
 reportOpenedAt=Date.now();
 document.body.classList.add('report-open');
 el('reportOverlay').style.display='block';
 if(!historicalMode){usage.reports++;updateUsage();}
 if(customerMapBuildTimer)clearTimeout(customerMapBuildTimer);
 customerMapBuildTimer=setTimeout(async()=>{try{if(historicalMode){if(useAerial)await buildSavedHistoricalSnapshot()}else await buildCustomerMap()}catch(e){console.error(e);if(historicalMode&&el('customerMapPlaceholder')){el('customerMap').style.display='none';el('customerMapPlaceholder').style.display='flex';el('customerMapPlaceholder').textContent='Saved property image could not be rebuilt.'}}finally{customerMapBuildTimer=null;estimateOpenInProgress=false;if(createBtn)createBtn.disabled=false}},350);
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
async function downloadEstimatePDF(){
 const btn=el('downloadPdfBtn'),report=document.querySelector('#reportOverlay .report');
 if(!report){status('Create the customer estimate first.','error');return}
 if(reportOutlineEditMode){if(el('reportOutlineHelpTop'))el('reportOutlineHelpTop').textContent='Save the outline before downloading the PDF.';return}
 if(pdfInProgress)return;
 if(typeof html2canvas==='undefined'||!window.jspdf){status('PDF tools did not load. Check the internet connection, then reopen the estimate.','error');return}
 pdfInProgress=true;
 const src=(el('measureSource')&&el('measureSource').value)||'google';
 const oldText=btn?btn.textContent:'';if(btn){btn.disabled=true;btn.textContent='CREATING PDF…'}
 try{
  // IMPORTANT: capture the SAME interactive estimate map the dealer just approved.
  // Do not rebuild the manual aerial and do not refit/recenter the map before capture.
  // The saved outline and the PDF therefore use the exact same Leaflet viewport + geometry.
  const useAerial=(el('streetViewChoice')?.value||'auto')!=='none';
  if(useAerial&&!customerMap){await buildCustomerMap();await new Promise(r=>setTimeout(r,220))}
  else if(customerMap){customerMap.invalidateSize(false);await new Promise(r=>setTimeout(r,160))}
  const actions=report.querySelector('.reportActions'),outlineControls=el('reportOutlineControls');
  const oldActionsDisplay=actions?actions.style.display:'',oldOutlineDisplay=outlineControls?outlineControls.style.display:'';
  if(actions)actions.style.display='none';if(outlineControls)outlineControls.style.display='none';
  // Preserve the exact approved estimate viewport. Do not restyle/reflow the report before vector capture.
  const pdfOverlayPane=customerMap?customerMap.getPane('overlayPane'):null,oldPdfOverlayVisibility=pdfOverlayPane?pdfOverlayPane.style.visibility:'';
  if(pdfOverlayPane)pdfOverlayPane.style.visibility='hidden';
  let canvas;
  try{canvas=await html2canvas(report,{scale:2,useCORS:true,allowTaint:false,backgroundColor:'#ffffff',logging:false})}
  finally{
    if(pdfOverlayPane)pdfOverlayPane.style.visibility=oldPdfOverlayVisibility;
    if(actions)actions.style.display=oldActionsDisplay;if(outlineControls)outlineControls.style.display=oldOutlineDisplay;
  }

  const {jsPDF}=window.jspdf;const pdf=new jsPDF({orientation:'landscape',unit:'in',format:'letter',compress:true});
  const pageW=11,pageH=8.5,margin=.18,maxW=pageW-margin*2,maxH=pageH-margin*2;
  const ratio=Math.min(maxW/canvas.width,maxH/canvas.height);const w=canvas.width*ratio,h=canvas.height*ratio;
  pdf.addImage(canvas.toDataURL('image/jpeg',0.92),'JPEG',(pageW-w)/2,(pageH-h)/2,w,h,undefined,'FAST');
  const raw=(el('address')?.value||'Customer').split(',')[0].trim()||'Customer';const safe=raw.replace(/[^a-z0-9]+/gi,'_').replace(/^_+|_+$/g,'');
  pdf.save(`ShingleXtra_Estimate_${safe||'Customer'}.pdf`);status('ShingleXtra estimate PDF downloaded.','ok');
 }catch(e){console.error(e);status('PDF could not be created. Use PRINT ESTIMATE while this is corrected.','error')}
 finally{
   pdfInProgress=false;if(btn){btn.disabled=!!reportOutlineEditMode;btn.textContent=oldText||'DOWNLOAD ESTIMATE PDF'}
 }
}
let reportCloseArmedAt=0;
function armReportClose(e){
 const b=el('backToDealerBtn');
 if(!b||!e||e.currentTarget!==b)return;
 reportCloseArmedAt=Date.now();
}
function closeReport(e){
 const b=el('backToDealerBtn');
 const deliberate=!!(e&&b&&e.currentTarget===b&&reportCloseArmedAt&&Date.now()-reportCloseArmedAt<1500);
 reportCloseArmedAt=0;
 if(!deliberate)return;
 document.body.classList.remove('report-open');
 el('reportOverlay').style.display='none';
 if(customerMap){try{customerMap.remove()}catch(err){}customerMap=null}
 customerRgbLayer=null;customerOverlays=[];
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
 if(el('garageGuide'))el('garageGuide').textContent='Load the property first. The main house will measure automatically.';if(el('garageSavedConfirm')){el('garageSavedConfirm').style.display='none';el('garageSavedConfirm').innerHTML='';}
 if(el('measureClicked'))el('measureClicked').disabled=true;if(el('measureClickedTop'))el('measureClickedTop').disabled=true;
 setManualUi(false);renderSummary();status('New property — finish the address, then click LOAD & MEASURE ROOF.','ok');
}
function startNewProperty(){
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
 const defaultPrice=parseFloat(el('price')?.value||0);if(Number.isFinite(defaultPrice)&&defaultPrice>=0&&el('jobPrice'))el('jobPrice').value=defaultPrice.toFixed(2);
 renderSummary();
 status('Ready for the next property. Enter the new address and click LOAD & MEASURE ROOF.','ok');
 window.scrollTo({top:0,behavior:'smooth'});
 setTimeout(()=>{if(street)street.focus()},250);
}
function enteredStreetNumber(){const v=(el('streetAddress')?.value||'').trim();const m=v.match(/^\s*(\d+[A-Za-z]?)(?:\s|,|$)/);return m?m[1]:''}
function applyAddressParts(parts){if(!parts)return;if(parts.city&&el('cityTown'))el('cityTown').value=parts.city;if(parts.province&&el('propertyProvince')){el('propertyProvince').value=parts.province;syncPropertyProvince()}if(parts.postal&&el('postalCode'))el('postalCode').value=parts.postal}
function clearAddressVerificationState(message='Address changed — enter/confirm city and state, then Google will verify it.'){
 addressPreviewSeq++;
 if(el('postalCode'))el('postalCode').value='';
 if(el('address'))el('address').value='';
 if(el('googleMatch'))el('googleMatch').textContent='';
 if(el('propertyVerify')){el('propertyVerify').style.display='none';el('propertyVerify').textContent='';}
 if(el('addressAutoStatus')){el('addressAutoStatus').textContent=message;el('addressAutoStatus').style.color='#666';}
}
const CANADIAN_PROVINCES=new Set(['AB','BC','MB','NB','NL','NS','NT','NU','ON','PE','QC','SK','YT']);
function propertyCountryFromProvince(prov){return CANADIAN_PROVINCES.has(String(prov||'').toUpperCase())?'Canada':'USA'}
function propertyLookupProvince(){
 const selected=(el('propertyProvince')?.value||'').trim();
 if(selected)return selected; // PROPERTY province is authoritative. Dealer profile province is never used for locating a property.
 return detectProvince(el('streetAddress')?.value||'')||'';
}
async function previewAddress(){
 const seq=addressPreviewSeq;
 const key="{{GOOGLE_MAPS_API_KEY}}",street=(el('streetAddress')?.value||'').trim();if(!key||!street||street.length<4)return;
 const city=(el('cityTown')?.value||'').trim(),prov=propertyLookupProvince();
 if(!city||!prov){if(el('addressAutoStatus')){el('addressAutoStatus').textContent='Enter the City and State/Province. ZIP/postal code is not required.';el('addressAutoStatus').style.color='#666'}return}
 const q=[street,city,prov,propertyCountryFromProvince(prov)].join(', ');
 try{if(el('addressAutoStatus')){el('addressAutoStatus').textContent='Checking '+city+', '+prov+'…';el('addressAutoStatus').style.color='#666'}
  const r=await fetch('/address-preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key,address:q,expected_city:city,expected_province:prov,expected_street_number:enteredStreetNumber()})});const d=await r.json();if(seq!==addressPreviewSeq)return;
  if(r.status===409){if(el('addressAutoStatus')){el('addressAutoStatus').textContent='⚠ ADDRESS DOESN\'T MATCH — '+(d.user_error||'Google found a different address.');el('addressAutoStatus').style.color='#9a1f16'}return}
  if(!r.ok||!d.formatted_address){if(el('addressAutoStatus')){el('addressAutoStatus').textContent='Google could not verify this exact street, city and state/province yet.';el('addressAutoStatus').style.color='#9a6700'}return}
  // Preview is DISPLAY ONLY. It must never overwrite city, province or ZIP code.
  if(el('addressAutoStatus')){el('addressAutoStatus').textContent='Google found: '+d.formatted_address;el('addressAutoStatus').style.color='#176b43'}
 }catch(e){if(el('addressAutoStatus')){el('addressAutoStatus').textContent='Google could not verify this address yet.';el('addressAutoStatus').style.color='#9a6700'}}
}
function addressFieldChanged(){
 const hadLoaded=!!sessionToken||structures.length||manualPlanes.length||fallbackMode;
 const street=(el('streetAddress')?.value||'').trim(),city=(el('cityTown')?.value||'').trim(),prov=(el('propertyProvince')?.value||'').trim();
 if(hadLoaded){clearLoadedPropertyForNewAddress();if(el('streetAddress'))el('streetAddress').value=street;if(el('cityTown'))el('cityTown').value=city;if(el('propertyProvince'))el('propertyProvince').value=prov;}
 clearAddressVerificationState();
 clearTimeout(addressPreviewTimer);addressPreviewTimer=setTimeout(previewAddress,650);
}
function addressTyped(){
 // A street-address edit starts a new property. Never carry the prior city's/state's values forward.
 const hadLoaded=!!sessionToken||structures.length||manualPlanes.length||fallbackMode;
 if(hadLoaded){
  const street=(el('streetAddress')?.value||'').trim();
  clearLoadedPropertyForNewAddress();
  if(el('streetAddress'))el('streetAddress').value=street;
  if(el('cityTown'))el('cityTown').value='';
  if(el('propertyProvince'))el('propertyProvince').value='';
  if(el('postalCode'))el('postalCode').value='';
  clearAddressVerificationState('New address — enter/confirm city and state/province, then Google will verify it.');
  clearTimeout(addressPreviewTimer);addressPreviewTimer=setTimeout(previewAddress,650);
  return;
 }
 addressFieldChanged();
}
function propertyProvinceChanged(){syncPropertyProvince();addressFieldChanged()}
window.addEventListener('DOMContentLoaded',()=>{loadDealerDefaults();updateUsage();const jp=el('jobPrice');if(jp){jp.addEventListener('input',jobPriceChanged);jp.addEventListener('change',jobPriceChanged);jp.addEventListener('keyup',jobPriceChanged);}const street=el('streetAddress'),city=el('cityTown');if(street)street.addEventListener('input',addressTyped);if(city)city.addEventListener('input',addressFieldChanged);renderSummary()});
function buildPropertyAddress(){
 const street=(el('streetAddress')?.value||'').trim(),city=(el('cityTown')?.value||'').trim(),prov=propertyLookupProvince();
 // Postal code is intentionally NEVER included in a property lookup. Google supplies it only after verification.
 const a=[street,city,prov,propertyCountryFromProvince(prov)].filter(Boolean).join(', ');
 if(el('address'))el('address').value=a;return a
}
function jobPriceChanged(){const jp=el('jobPrice');if(!jp)return;const v=parseFloat(jp.value);if(!Number.isFinite(v)||v<0)return;renderSummary();if(el('reportOverlay')&&el('reportOverlay').style.display==='block')showCustomerEstimate()}
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
 if(!raw)return null;
 let m=raw.match(/^\s*(-?\d{1,2}(?:\.\d+)?)\s*[, ]\s*(-?\d{1,3}(?:\.\d+)?)\s*$/);
 if(!m){
   try{
     const u=new URL(raw);
     const c=u.searchParams.get('coordinate');
     if(c)m=c.match(/^\s*(-?\d{1,2}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)\s*$/);
   }catch(e){}
 }
 if(!m)return null;
 const lat=Number(m[1]),lng=Number(m[2]);
 if(!Number.isFinite(lat)||!Number.isFinite(lng)||Math.abs(lat)>90||Math.abs(lng)>180)return null;
 return {lat,lng};
}


function syncPropertyProvince(){renderSummary();}
</script>
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
    return {"latitude":float(c.get("latitude",lat)),"longitude":float(c.get("longitude",lng)),
            "total_roof_sqft":float(whole.get("areaMeters2") or 0)*10.76391041671,
            "segment_count":len(segs),"segments":segs,"imagery_quality":data.get("imageryQuality"),
            "imagery_date":date_text(data.get("imageryDate"))}

def bearing(lat1,lon1,lat2,lon2):
    p1,p2=math.radians(lat1),math.radians(lat2);dl=math.radians(lon2-lon1)
    y=math.sin(dl)*math.cos(p2);x=math.cos(p1)*math.sin(p2)-math.sin(p1)*math.cos(p2)*math.cos(dl)
    return (math.degrees(math.atan2(y,x))+360)%360


LOGIN_HTML=r"""<!doctype html><html><head><meta charset="utf-8"><title>AeriQuote Login</title><style>body{font-family:Arial;background:#f1f5f9;color:#17212b}.box{max-width:430px;margin:8vh auto;background:white;padding:30px;border-radius:18px;box-shadow:0 10px 35px #0002}h1{color:#102a43}label{font-weight:800;display:block;margin:12px 0 5px}input{width:100%;box-sizing:border-box;padding:12px;border:1px solid #cbd5ce;border-radius:9px}button{width:100%;margin-top:18px;padding:13px;border:0;border-radius:9px;background:#1677c8;color:white;font-weight:900}.err{background:#fff0f0;color:#a11;padding:10px;border-radius:8px}</style></head><body><div class="box"><img src="/static/aeriquote-logo.png" alt="AeriQuote" style="display:block;width:100%;max-width:360px;height:auto;margin:0 auto 16px"><p style="text-align:center">Roof Measuring & Estimate Software</p>{% if error %}<div class="err">{{error}}</div>{% endif %}<form method="post"><label>Email</label><input name="email" type="email" required><label>Password</label><input name="password" type="password" required><button>DEALER LOGIN</button></form></div></body></html>"""

@app.route("/dealer-login",methods=["GET","POST"])
def dealer_login():
    if request.method=="POST":
        email=str(request.form.get("email") or "").strip().lower(); password=str(request.form.get("password") or "")
        con=estimate_db()
        try: row=con.execute("SELECT * FROM dealers WHERE LOWER(email)=?",(email,)).fetchone()
        finally: con.close()
        if row and str(row["status"]).lower()=="active" and password_ok(password,row["password_hash"]):
            session.clear();session["dealer_id"]=row["id"];session["dealer_name"]=row["dealer_name"];session["account_type"]="owner"
            return redirect("/")
        con=estimate_db()
        try:
            emp=con.execute("SELECT e.*,d.dealer_name,d.status AS dealer_status FROM dealer_employees e JOIN dealers d ON d.id=e.dealer_id WHERE LOWER(e.email)=?",(email,)).fetchone()
        finally: con.close()
        if emp and str(emp["status"]).lower()=="active" and str(emp["dealer_status"]).lower()=="active" and password_ok(password,emp["password_hash"]):
            session.clear();session["dealer_id"]=emp["dealer_id"];session["dealer_name"]=emp["dealer_name"];session["employee_id"]=emp["id"];session["employee_name"]=emp["employee_name"];session["account_type"]="employee"
            return redirect("/")
        return render_template_string(LOGIN_HTML,error="Email or password is incorrect.")
    return render_template_string(LOGIN_HTML,error=None)

@app.get("/dealer-logout")
def dealer_logout():
    session.clear();return redirect("/dealer-login")

SETUP_DEALER_HTML=r"""<!doctype html><html><head><meta charset="utf-8"><title>Create ShingleXtra Dealer</title>
<style>body{font-family:Arial;background:#f1f5f9;color:#17212b}.box{max-width:480px;margin:6vh auto;background:#fff;padding:30px;border-radius:18px;box-shadow:0 10px 35px #0002}h1{color:#102a43}label{font-weight:800;display:block;margin:12px 0 5px}input{width:100%;box-sizing:border-box;padding:12px;border:1px solid #cbd5ce;border-radius:9px;font-size:16px}button{width:100%;margin-top:18px;padding:13px;border:0;border-radius:9px;background:#1677c8;color:#fff;font-weight:900;font-size:16px}.msg{padding:11px;border-radius:8px;background:#eef8ee}.err{padding:11px;border-radius:8px;background:#fff0f0;color:#a11}</style></head>
<body><div class="box"><h1>Create Dealer Account</h1><p>ShingleXtra Head Office setup</p>
{% if message %}<div class="msg">{{message}}</div>{% endif %}{% if error %}<div class="err">{{error}}</div>{% endif %}
<form method="post">
<label>Admin Setup Key</label><input name="setup_key" type="password" required>
<label>Dealer Name</label><input name="dealer_name" value="ShingleXtra Head Office" required>
<label>Email</label><input name="email" type="email" value="sdusome@diitalk.com" required>
<label>State</label><input name="state" value="Florida">
<label>Password</label><input name="password" type="password" minlength="8" required>
<button type="submit">CREATE DEALER ACCOUNT</button></form></div></body></html>"""

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
            existing=con.execute("SELECT id FROM dealers WHERE LOWER(email)=?",(email,)).fetchone()
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
        con.execute("INSERT INTO dealers(id,dealer_name,email,password_hash,state,status,lookup_limit,estimate_limit,created_at) VALUES(?,?,?,?,?,'active',250,150,?)",(did,name,email,password_hash(password),str(d.get("state") or ""),created));con.commit()
    except Exception:return jsonify(error="Could not create dealer"),400
    finally:con.close()
    return jsonify(id=did,dealer_name=name,email=email,status="active",lookup_limit=250,estimate_limit=150)


HEAD_OFFICE_DEALERS_HTML=r"""<!doctype html><html><head><meta charset="utf-8"><title>ShingleXtra Dealer Management</title>
<style>body{font-family:Arial;background:#f1f5f9;color:#17212b;margin:0}.wrap{max-width:1050px;margin:28px auto;padding:0 16px}.card{background:#fff;border-radius:16px;box-shadow:0 8px 28px #0002;padding:22px;margin-bottom:18px}h1,h2{color:#102a43;margin-top:0}.top{display:flex;justify-content:space-between;align-items:center;gap:12px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.full{grid-column:1/-1}label{font-weight:800;display:block;margin:5px 0}input,select{width:100%;box-sizing:border-box;padding:11px;border:1px solid #cbd5ce;border-radius:8px;font-size:15px}button,.btn{display:inline-block;border:0;border-radius:9px;padding:11px 15px;background:#1677c8;color:#fff;font-weight:900;text-decoration:none;cursor:pointer}.secondary{background:#fff;color:#1677c8;border:1px solid #1677c8}.msg{padding:10px;border-radius:8px;background:#edf7f0;color:#174f2b;margin-bottom:12px}.err{padding:10px;border-radius:8px;background:#fff0f0;color:#a11;margin-bottom:12px}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:10px;border-bottom:1px solid #d9e3ea;font-size:14px}th{color:#102a43;background:#f8faf9}.pill{display:inline-block;padding:4px 8px;border-radius:999px;background:#edf7f0;font-weight:800;font-size:12px}.networkDashboard{margin-top:18px}.networkTotals{display:grid;grid-template-columns:repeat(4,1fr);gap:9px;margin:12px 0 14px}.networkMetric{background:#f8fafc;border:1px solid #d9e3ea;border-radius:9px;padding:10px}.networkMetric span{display:block;font-size:11px;font-weight:900;color:#5b6770;text-transform:uppercase}.networkMetric b{display:block;margin-top:3px;font-size:18px;color:#102a43}.networkTableWrap{overflow:auto}.networkTable{width:100%;border-collapse:collapse;font-size:12px}.networkTable th,.networkTable td{padding:8px 9px;border-bottom:1px solid #e3e9ee;text-align:right;white-space:nowrap}.networkTable th:first-child,.networkTable td:first-child{text-align:left}.inventoryGrid{display:grid;grid-template-columns:repeat(4,1fr);gap:9px;margin:12px 0}.inventoryForm{display:flex;gap:10px;align-items:end;flex-wrap:wrap}.inventoryForm>div{min-width:180px;flex:1}.inventoryBar{height:12px;background:#e6ebef;border-radius:999px;overflow:hidden;margin-top:10px}.inventoryBarFill{height:100%;background:#334e68;border-radius:999px}.reorderAlert{margin-top:12px;padding:12px;border-radius:9px;font-weight:900;background:#fff3cd;border:1px solid #e0b84f;color:#6b4e00}.inventoryOK{margin-top:12px;padding:10px;border-radius:9px;font-weight:800;background:#edf7f0;border:1px solid #b9d9c2;color:#245c32}
@media(max-width:700px){.grid{grid-template-columns:1fr}.full{grid-column:auto}.top{align-items:flex-start;flex-direction:column}table{display:block;overflow:auto}.networkTotals{grid-template-columns:1fr 1fr}.inventoryGrid{grid-template-columns:1fr 1fr}}</style></head>
<body><div class="wrap"><div class="top"><div><h1>ShingleXtra — Dealer Management</h1><div>Head Office</div></div><div><a class="btn secondary" href="/">BACK TO ROOF ASSESSMENT</a> <a class="btn secondary" href="/logout">LOG OUT</a></div></div>
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
<div class="card"><h2>Create Dealer Account</h2>{% if message %}<div class="msg">{{message}}</div>{% endif %}{% if error %}<div class="err">{{error}}</div>{% endif %}
<form method="post"><div class="grid"><div><label>Dealer / Owner Name</label><input name="dealer_name" required></div><div><label>Company Name</label><input name="company"></div><div><label>Email / Login</label><input name="email" type="email" required></div><div><label>State</label><select name="state"><option value="">Select State</option>{% for s in states %}<option value="{{s}}">{{s}}</option>{% endfor %}</select></div><div><label>Temporary Password</label><input name="password" type="password" minlength="8" required></div><div><label>Account Status</label><select name="status"><option value="active">Active</option><option value="disabled">Disabled</option></select></div><div class="full"><label>Permission Level</label><input value="Dealer Owner" readonly></div><div class="full"><button type="submit">CREATE DEALER ACCOUNT</button></div></div></form></div>
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
</div>{% endfor %}</div></div></body></html>"""

US_STATES=['AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY','DC']

def is_head_office():
    return "head office" in str(session.get("dealer_name") or "").lower()

@app.route("/head-office/dealers",methods=["GET","POST"])
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
                existing=con.execute("SELECT id FROM dealers WHERE LOWER(email)=?",(email,)).fetchone()
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
        con.execute("UPDATE dealers SET password_hash=? WHERE id=?",(password_hash(password),dealer_id));con.commit()
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
        duplicate=con.execute("SELECT id FROM dealers WHERE LOWER(email)=? AND id<>?",(email,dealer_id)).fetchone()
        if duplicate:return Response("Another dealer already uses that email.",status=400)
        con.execute("UPDATE dealers SET dealer_name=?,email=?,state=?,lookup_limit=?,estimate_limit=? WHERE id=?",
                    (name,email,state,lookup_limit,estimate_limit,dealer_id));con.commit()
    finally: con.close()
    return redirect("/head-office/dealers")


def is_employee():
    return str(session.get("account_type") or "")=="employee"

def is_dealer_owner():
    return bool(session.get("dealer_id")) and not is_head_office() and not is_employee()

DEALER_EMPLOYEES_HTML=r"""<!doctype html><html><head><meta charset="utf-8"><title>ShingleXtra Employees</title>
<style>body{font-family:Arial;background:#f1f5f9;color:#17212b;margin:0}.wrap{max-width:900px;margin:28px auto;padding:0 16px}.card{background:#fff;border-radius:16px;box-shadow:0 8px 28px #0002;padding:22px;margin-bottom:18px}h1,h2{color:#102a43}.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}label{font-weight:800;display:block;margin:5px 0}input{width:100%;box-sizing:border-box;padding:11px;border:1px solid #cbd5ce;border-radius:8px}button,.btn{display:inline-block;border:0;border-radius:9px;padding:11px 15px;background:#1677c8;color:#fff;font-weight:900;text-decoration:none;cursor:pointer}.danger{background:#7a263a}.row{border:1px solid #d9e3ea;border-radius:12px;padding:14px;margin:10px 0}.err{background:#fff0f0;color:#a11;padding:10px;border-radius:8px}.msg{background:#edf7f0;color:#174f2b;padding:10px;border-radius:8px}@media(max-width:650px){.grid{grid-template-columns:1fr}}</style></head>
<body><div class="wrap"><p><a class="btn" href="/">BACK TO ROOF ASSESSMENT</a></p><div class="card"><h1>Manage Employees</h1><p>Employees share your dealership's estimates and usage allowance. They cannot manage dealership settings or other employees.</p>
{% if message %}<div class="msg">{{message}}</div>{% endif %}{% if error %}<div class="err">{{error}}</div>{% endif %}
<h2>Create Employee Login</h2><form method="post"><div class="grid"><div><label>Employee Name</label><input name="employee_name" required></div><div><label>Email / Login</label><input name="email" type="email" required></div><div><label>Temporary Password</label><input name="password" type="password" minlength="8" required></div><div style="align-self:end"><button>CREATE EMPLOYEE</button></div></div></form></div>
<div class="card"><h2>Employees</h2>{% if not employees %}<p>No employees yet.</p>{% endif %}{% for e in employees %}<div class="row"><b>{{e.employee_name}}</b> — {{e.email}} — <b>{{e.status|title}}</b><form method="post" action="/dealer-employees/{{e.id}}/status" style="margin-top:10px"><input type="hidden" name="action" value="{{'activate' if e.status=='disabled' else 'disable'}}"><button class="{{'' if e.status=='disabled' else 'danger'}}">{{'ACTIVATE' if e.status=='disabled' else 'DISABLE'}}</button></form></div>{% endfor %}</div></div></body></html>"""

@app.route("/dealer-employees",methods=["GET","POST"])
def dealer_employees():
    if not is_dealer_owner(): return Response("Dealer Owner permission required.",status=403)
    did=str(session["dealer_id"]);message=None;error=None
    if request.method=="POST":
        name=str(request.form.get("employee_name") or "").strip();email=str(request.form.get("email") or "").strip().lower();password=str(request.form.get("password") or "")
        if not name or not email or len(password)<8:error="Employee name, email and a temporary password of at least 8 characters are required."
        else:
            con=estimate_db()
            try:
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
    did=str(session["dealer_id"]);new_status="disabled" if str(request.form.get("action") or "").lower()=="disable" else "active"
    con=estimate_db()
    try:con.execute("UPDATE dealer_employees SET status=? WHERE id=? AND dealer_id=?",(new_status,employee_id,did));con.commit()
    finally:con.close()
    return redirect("/dealer-employees")

def consume_property_lookup(dealer_id):
    con=estimate_db()
    try:
        d=con.execute("SELECT lookup_limit FROM dealers WHERE id=?",(dealer_id,)).fetchone()
        if not d:return False,0,0
        limit=int(d["lookup_limit"] or 0)
        u=con.execute("SELECT property_lookups FROM dealer_usage WHERE dealer_id=?",(dealer_id,)).fetchone()
        used=int(u["property_lookups"] if u else 0)
        if limit>0 and used>=limit:return False,used,limit
        if u:con.execute("UPDATE dealer_usage SET property_lookups=property_lookups+1 WHERE dealer_id=?",(dealer_id,))
        else:con.execute("INSERT INTO dealer_usage(dealer_id,property_lookups) VALUES(?,1)",(dealer_id,))
        con.commit();return True,used+1,limit
    finally:con.close()

@app.before_request
def require_dealer_login():
    path=(request.path or "").rstrip("/") or "/"
    if path in {"/dealer-login","/setup-dealer","/health","/api/admin/create-dealer"} or path.startswith("/static/"):return None
    if not session.get("dealer_id"):
        if request.path.startswith("/api/"):return jsonify(error="Dealer login required"),401
        return redirect("/dealer-login")


@app.get("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.get("/")
def home():return render_template_string(HTML, GOOGLE_MAPS_API_KEY=GOOGLE_MAPS_API_KEY, IS_HEAD_OFFICE=is_head_office(), IS_EMPLOYEE=is_employee(), IS_DEALER_OWNER=is_dealer_owner())
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
    parts={"street":"","city":"","province":"","postal":""}
    comps=g.get("address_components") or []
    num=route=""
    for c in comps:
        types=set(c.get("types") or [])
        if "street_number" in types:num=c.get("long_name") or ""
        if "route" in types:route=c.get("long_name") or ""
        if not parts["city"] and types.intersection({"locality","postal_town","sublocality","administrative_area_level_3"}):parts["city"]=c.get("long_name") or ""
        if "administrative_area_level_1" in types:parts["province"]=c.get("short_name") or ""
        if "postal_code" in types:parts["postal"]=c.get("long_name") or ""
    parts["street"]=(num+" "+route).strip()
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
    for q in usa_address_variants(address):
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

def address_mismatch(expected_city,expected_province,parts,expected_street_number=""):
    ec=_norm_place(expected_city); ep=_norm_place(expected_province)
    ac=_norm_place((parts or {}).get("city")); ap=_norm_place((parts or {}).get("province"))
    city_bad=bool(ec and (not ac or ec!=ac))
    prov_bad=bool(ep and (not ap or ep!=ap))
    import re
    en=re.sub(r"[^0-9a-z]","",str(expected_street_number or "").lower())
    found_street=str((parts or {}).get("street") or "").strip()
    m=re.match(r"^\s*(\d+[A-Za-z]?)\b",found_street)
    an=re.sub(r"[^0-9a-z]","",(m.group(1) if m else "").lower())
    number_bad=bool(en and en!=an)  # also rejects a street-only Google result with no civic number
    return city_bad or prov_bad or number_bad

def mismatch_message(expected_city,expected_province,parts):
    wanted=", ".join(x for x in [str(expected_city or "").strip(),str(expected_province or "").strip()] if x) or "the location entered"
    found=", ".join(x for x in [(parts or {}).get("city",""),(parts or {}).get("province","")] if x) or "a different location"
    return f"You entered {wanted} but Google found {found}. Correct the address or use exact dropped-pin coordinates."

@app.post("/address-preview")
def address_preview():
    d=request.get_json(silent=True) or {};key=str(d.get("key") or "").strip();address=str(d.get("address") or "").strip() # authoritative query is street + city + property province; ZIP code is never sent
    if not key or len(address)<4:return jsonify(error="Address and API key are required."),400
    try:
        expected_city=str(d.get("expected_city") or "").strip();expected_province=str(d.get("expected_province") or "").strip();expected_street_number=str(d.get("expected_street_number") or "").strip()
        gs,geo,_matched_query=google_geocode_first(key,address,components_country=True,expected_province=expected_province)
        if gs!=200 or geo.get("status")!="OK" or not geo.get("results"):return jsonify(error="Address not found"),404
        g=geo["results"][0];parts=geocode_parts(g)
        if address_mismatch(expected_city,expected_province,parts,expected_street_number):
            return jsonify(error="ADDRESS DOESN'T MATCH",user_error=mismatch_message(expected_city,expected_province,parts),formatted_address=g.get("formatted_address"),parts=parts),409
        return jsonify(formatted_address=g.get("formatted_address"),parts=parts)
    except Exception as e:return jsonify(error=str(e)),400

def street_view_info(key,address,lat,lng,target_lat,target_lng):
    mq=urllib.parse.urlencode({"location":address,"key":key,"source":"outdoor"})
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
    SESSIONS[token]={"key":key,"rgb":layers.get("rgbUrl") if layers else None,"rgb_cache":None,"mask":layers.get("maskUrl") if layers else None,"mask_cache":None,"street":street_url,"street_cache":None,"lat":lat,"lng":lng,"created":time.time(),"mode":mode,"fallback_cache":None,"fallback_zoom":19,"anchor_lat":anchor_lat if anchor_lat is not None else lat,"anchor_lng":anchor_lng if anchor_lng is not None else lng,"formatted_address":formatted_address}
    for t in list(SESSIONS):
        if time.time()-SESSIONS[t]["created"]>3600:SESSIONS.pop(t,None)
    return token

@app.post("/property")
def property_data():
    d=request.get_json(silent=True) or {};key=str(d.get("key") or "").strip();address=str(d.get("address") or "").strip()
    if not key or not address:return jsonify(error="API key and address are required."),400
    allowed,used,limit=consume_property_lookup(str(session.get("dealer_id") or ""))
    if not allowed:return jsonify(error="Property lookup allowance reached.",user_error=f"Your dealership has used all {limit} property lookups. Contact AeriQuote support to increase the allowance."),403
    try:
        direct=bool(d.get("direct_coordinates"));g={}
        if direct:
            lat=float(d.get("latitude"));lng=float(d.get("longitude"))
            if abs(lat)>90 or abs(lng)>180: return jsonify(error="Invalid coordinates.",user_error="Enter valid latitude and longitude coordinates."),400
            formatted=f"{lat:.6f}, {lng:.6f}"
        else:
            expected_city=str(d.get("expected_city") or "").strip();expected_province=str(d.get("expected_province") or "").strip();expected_street_number=str(d.get("expected_street_number") or "").strip()
            gs,geo,_matched_query=google_geocode_first(key,address,components_country=True,expected_province=expected_province)
            if gs!=200 or geo.get("status")!="OK" or not geo.get("results"):return jsonify(error="Google could not find that address. Check the address and try again.",user_error="Google could not find that address. Check the address and try again."),404
            g=geo["results"][0];parts=geocode_parts(g)
            if address_mismatch(expected_city,expected_province,parts,expected_street_number):
                return jsonify(error="ADDRESS DOESN'T MATCH",user_error=mismatch_message(expected_city,expected_province,parts),formatted_address=g.get("formatted_address"),parts=parts),409
            loc=g["geometry"]["location"];lat=float(loc["lat"]);lng=float(loc["lng"]);formatted=g.get("formatted_address") or address
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
                return jsonify(token=token,fallback=True,fallback_aerial="solar",center={"latitude":lat,"longitude":lng},formatted_address=formatted,parts=geocode_parts(g),street_date=street_date)
            except Exception:
                # Last display fallback only. If Maps Static is not enabled the UI
                # gives a clear setup message instead of exposing a raw Google error.
                token=create_session(key,lat,lng,street_url=street_url,mode="manual_static",layers=None,anchor_lat=lat,anchor_lng=lng,formatted_address=formatted)
                return jsonify(token=token,fallback=True,fallback_aerial="static",center={"latitude":lat,"longitude":lng},formatted_address=formatted,parts=geocode_parts(g),street_date=street_date)
        img_lat,img_lng,img_radius=roof_imagery_request(main);layers=solar_layers(key,img_lat,img_lng,img_radius)
        street_url,street_date=street_view_info(key,formatted,lat,lng,lat,lng)
        token=create_session(key,main["latitude"],main["longitude"],street_url=street_url,mode="solar",layers=layers,anchor_lat=lat,anchor_lng=lng,formatted_address=formatted)
        if direct:
            dl,do,dz=exact_pin_display_request(main)
            SESSIONS[token].update({"exact_pin":True,"display_lat":dl,"display_lng":do,"display_zoom":dz,"fallback_zoom":dz})
        return jsonify(token=token,main=main,formatted_address=formatted,parts=geocode_parts(g),street_date=street_date,anchor={"latitude":lat,"longitude":lng},exact_pin_display=bool(direct))
    except Exception as e:
        return jsonify(error=str(e),user_error="Google could not complete the automatic roof measurement for this property. Try again, or use the manual fallback if offered."),400

@app.post("/structure")
def structure():
    d=request.get_json(silent=True) or {};sess=SESSIONS.get(str(d.get("token") or ""))
    if not sess:return jsonify(error="Property session expired. Reload the property.",user_error="Property session expired. Reload the property."),400
    try:return jsonify(building(sess["key"],float(d["latitude"]),float(d["longitude"])))
    except SolarBuildingNotFound:return jsonify(error="Building not found",user_error="Google could not automatically match that roof. Click closer to the centre or add it manually."),404
    except Exception as e:return jsonify(error=str(e),user_error="Google could not measure that roof right now."),400

@app.post("/locate-building")
def locate_building():
    d=request.get_json(silent=True) or {};sess=SESSIONS.get(str(d.get("token") or ""))
    if not sess:return jsonify(error="Property session expired.",user_error="Property session expired. Reload the property."),400
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
        return Response(body,content_type=ct)
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
            if len(pts)>=3:roofs.append((kind,pts))
        if not roofs:return Response("No valid saved roof outline",status=400)
        allpts=[pt for _,pts in roofs for pt in pts]
        def merc_xy(lat,lng):
            lat=max(-85.05112878,min(85.05112878,lat));x=(lng+180.0)/360.0;siny=math.sin(math.radians(lat));y=0.5-math.log((1+siny)/(1-siny))/(4*math.pi);return x,y
        xy=[merc_xy(lat,lng) for lat,lng in allpts];xs=[q[0] for q in xy];ys=[q[1] for q in xy]
        xmin,xmax=min(xs),max(xs);ymin,ymax=min(ys),max(ys);dx=max(xmax-xmin,1e-9);dy=max(ymax-ymin,1e-9)
        zx=math.log((640*.58)/(256.0*dx),2);zy=math.log((420*.58)/(256.0*dy),2);zoom=max(18,min(21,int(math.floor(min(zx,zy)))))
        cx=(xmin+xmax)/2.0;cy=(ymin+ymax)/2.0;center_lng=cx*360.0-180.0;n=math.pi-2.0*math.pi*cy;center_lat=math.degrees(math.atan(math.sinh(n)))
        params=[("size","640x420"),("scale","2"),("center",f"{center_lat:.7f},{center_lng:.7f}"),("zoom",str(zoom)),("maptype","satellite"),("format","png")]
        for kind,pts in roofs:
            if kind=="garage":color,fill="0x18a7a0ff","0x18a7a018"
            elif kind=="manual":color,fill="0xd97706ff","0xf59e0b20"
            else:color,fill="0x2d6cdfff","0x2d6cdf16"
            closed=pts+[pts[0]];params.append(("path",f"color:{color}|weight:4|fillcolor:{fill}|"+"|".join(f"{a:.7f},{b:.7f}" for a,b in closed)))
        params.append(("key",key));url="https://maps.googleapis.com/maps/api/staticmap?"+urllib.parse.urlencode(params)
        headers={"User-Agent":"ShingleGuardRoofAssessment/2.0","Referer":request.host_url,"Origin":request.host_url.rstrip("/")};req=urllib.request.Request(url,headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=15) as rr:ct=rr.headers.get("Content-Type","image/png");body=rr.read()
        except urllib.error.HTTPError as he:
            raw=he.read().decode("utf-8","replace")[:1200].replace(key,"[API KEY REDACTED]");raise ValueError(f"Google Maps Static HTTP {he.code}: {raw}")
        return Response(body,content_type=ct)
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
        estimate_count=con.execute("SELECT COUNT(*) FROM estimates WHERE dealer_id=?",(dealer_id,)).fetchone()[0]
        revision_count=con.execute("SELECT COUNT(*) FROM estimate_revisions WHERE dealer_id=?",(dealer_id,)).fetchone()[0]
    finally:
        con.close()
    return jsonify(
        persistent=bool(DATABASE_URL),
        estimate_count=estimate_count,
        revision_count=revision_count
    )

@app.route("/api/estimates", methods=["GET","POST"])
def estimate_history_api():
    dealer_id=str(session.get("dealer_id") or "")
    con=estimate_db()
    try:
        if request.method=="POST":
            d=request.get_json(silent=True) or {}
            address=str(d.get("address") or "").strip()
            if not address:return jsonify(error="Property address is required"),400
            # One active estimate per property PER DEALER. Another dealer can quote
            # the same address without seeing or overwriting this dealer's record.
            norm=lambda v:" ".join(str(v or "").lower().replace(","," ").replace("."," ").split())
            address_key=norm(address)
            existing=None
            for row in con.execute("SELECT * FROM estimates WHERE dealer_id=? ORDER BY created_at DESC",(dealer_id,)).fetchall():
                if norm(row["address"])==address_key:
                    existing=row;break
            if not existing:
                dealer_row=con.execute("SELECT estimate_limit FROM dealers WHERE id=?",(dealer_id,)).fetchone()
                estimate_limit=int(dealer_row["estimate_limit"] or 0) if dealer_row else 0
                estimate_used=int(con.execute("SELECT COUNT(*) AS estimate_count FROM estimates WHERE dealer_id=?",(dealer_id,)).fetchone()["estimate_count"])
                if estimate_limit>0 and estimate_used>=estimate_limit:
                    return jsonify(error="Estimate allowance reached.",user_error=f"Your dealership has used all {estimate_limit} estimates. Contact AeriQuote support to increase the allowance."),403
            created=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())
            payload_json=json.dumps(d,separators=(",",":"))
            vals=(str(d.get("customer_name") or ""),str(d.get("customer_phone") or ""),str(d.get("customer_email") or ""),address,float(d.get("total_area") or 0),float(d.get("total_price") or 0),payload_json)
            if existing:
                con.execute("INSERT INTO estimate_revisions(revision_id,estimate_id,revised_at,customer_name,customer_phone,customer_email,address,total_area,total_price,payload,dealer_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(str(uuid.uuid4()),existing["id"],created,existing["customer_name"],existing["customer_phone"],existing["customer_email"],existing["address"],existing["total_area"],existing["total_price"],existing["payload"],dealer_id))
                con.execute("UPDATE estimates SET created_at=?,customer_name=?,customer_phone=?,customer_email=?,address=?,total_area=?,total_price=?,payload=? WHERE id=? AND dealer_id=?",(created,*vals,existing["id"],dealer_id))
                con.commit();return jsonify(id=existing["id"],created_at=created,updated=True)
            eid=str(uuid.uuid4())
            con.execute("INSERT INTO estimates(id,created_at,customer_name,customer_phone,customer_email,address,total_area,total_price,payload,dealer_id) VALUES(?,?,?,?,?,?,?,?,?,?)",(eid,created,*vals,dealer_id))
            con.commit();return jsonify(id=eid,created_at=created,updated=False)
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
    try: amount_paid=max(0.0,float(d.get("amount_paid") or 0))
    except (TypeError,ValueError):return jsonify(ok=False,error="Invalid amount."),400
    con=estimate_db()
    try:
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
        zoom=max(15,min(18,zoom))
        q=urllib.parse.urlencode({"center":f"{lat},{lng}","zoom":zoom,"size":"640x640","maptype":"satellite","format":"png","key":sess["key"]})
        url="https://maps.googleapis.com/maps/api/staticmap?"+q
        headers={"User-Agent":"ShingleGuardRoofAssessment/2.0","Referer":request.host_url,"Origin":request.host_url.rstrip("/")}
        req=urllib.request.Request(url,headers=headers)
        with urllib.request.urlopen(req,timeout=12) as r:
            ct=r.headers.get("Content-Type","image/png");body=r.read()
        return Response(body,content_type=ct)
    except Exception as e:
        return Response(str(e).replace(sess.get("key") or "","[API KEY REDACTED]"),status=400,content_type="text/plain; charset=utf-8")

@app.get("/fallback-meta/<token>")
def fallback_meta(token):
    sess=SESSIONS.get(token)
    if not sess:return jsonify(error="Session expired"),404
    return jsonify(latitude=sess.get("lat"),longitude=sess.get("lng"),zoom=sess.get("fallback_zoom",20),width=640,height=640)

@app.get("/fallback-map/<token>")
def fallback_map(token):
    sess=SESSIONS.get(token)
    if not sess:return Response("Session expired",status=404)
    try:
        if sess.get("fallback_cache") is None:
            q=urllib.parse.urlencode({"center":f'{sess["lat"]},{sess["lng"]}',"zoom":sess.get("fallback_zoom",20),"size":"640x640","maptype":"satellite","format":"png","key":sess["key"]})
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
    try:
        if s["rgb_cache"] is None:
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
    except Exception as e:return Response(str(e),status=404)

if __name__=="__main__":
    port=5102
    threading.Timer(1.15,lambda:webbrowser.open(f"http://127.0.0.1:{port}")).start()
    print("SHINGLEXTRA U.S. ROOF ASSESSMENT V1")
    print(f"Opening Chrome at http://127.0.0.1:{port}")
    print("Leave this window open while testing.")
    app.run(host="127.0.0.1",port=port,debug=False,use_reloader=False)
