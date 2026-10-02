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
