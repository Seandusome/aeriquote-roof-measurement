"""24-hour recovery records, separate from estimates and credit accounting.

All callers supply the authenticated business AND individual principal. Closed IDs
retain no workspace data; their short-lived tombstones reject delayed autosaves.
"""
import json
import re
import time

TTL = 24 * 60 * 60
MAX_BYTES = 2_000_000
ID = re.compile(r'^[A-Za-z0-9_-]{16,128}$')


class DraftError(Exception):
    def __init__(self, message, status=409):
        self.status = status
        super().__init__(message)


def initialize(con):
    con.execute('''CREATE TABLE IF NOT EXISTS workspace_drafts (
        dealer_id TEXT NOT NULL, principal TEXT NOT NULL, draft_id TEXT NOT NULL,
        version INTEGER NOT NULL, expires_at DOUBLE PRECISION NOT NULL,
        payload TEXT, property_metadata TEXT, closed INTEGER NOT NULL DEFAULT 0, save_operation TEXT,
        PRIMARY KEY(dealer_id,principal,draft_id))''')
    con.execute('CREATE INDEX IF NOT EXISTS idx_workspace_drafts_expiry ON workspace_drafts(expires_at)')


def principal(session):
    if session.get('account_type') == 'employee':
        return 'employee:' + str(session.get('employee_id') or '')
    return 'owner:' + str(session.get('dealer_id') or '')


def validate_id(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise DraftError('Invalid recovery draft identifier.', 400)
    return value


def purge(con, now=None):
    con.execute('DELETE FROM workspace_drafts WHERE expires_at <= ?', (time.time() if now is None else now,))


def load(con, dealer, user, draft_id, now=None):
    validate_id(draft_id)
    row = con.execute('SELECT * FROM workspace_drafts WHERE dealer_id=? AND principal=? AND draft_id=? AND expires_at>? AND closed=0',
                      (dealer, user, draft_id, time.time() if now is None else now)).fetchone()
    if not row:
        raise DraftError('This recovery draft is unavailable or its 24-hour window has ended.', 404)
    return row


def put(con, dealer, user, draft_id, expected, payload, metadata=None, now=None):
    validate_id(draft_id)
    now = time.time() if now is None else now
    if isinstance(expected, bool) or not isinstance(expected, int) or expected < 0:
        raise DraftError('Recovery version is required.', 400)
    if not isinstance(payload, dict) or payload.get('schema') != 1:
        raise DraftError('Unsupported recovery workspace.', 400)
    try:
        encoded = json.dumps(payload, allow_nan=False, separators=(',', ':'))
    except (ValueError, TypeError):
        raise DraftError('Recovery workspace contains invalid values.', 400)
    if len(encoded.encode()) > MAX_BYTES:
        raise DraftError('Recovery workspace is too large. Keep this tab open.', 413)
    # Never accept image bytes, credentials or provider URLs in recovery JSON.
    forbidden = {'password', 'password_hash', 'api_key', 'key', 'street_image_data', 'cookie', 'authorization'}
    def inspect(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key.lower() in forbidden and child:
                    raise DraftError('Recovery workspace contains unsupported private data.', 400)
                inspect(child)
        elif isinstance(value, list):
            for child in value: inspect(child)
        elif isinstance(value, str) and (value.startswith('data:image/') or 'key=' in value.lower()):
            raise DraftError('Recovery workspace must not contain image bytes or API credentials.', 400)
    inspect(payload)
    row = con.execute('SELECT * FROM workspace_drafts WHERE dealer_id=? AND principal=? AND draft_id=?', (dealer, user, draft_id)).fetchone()
    if row:
        if row['closed'] or row['expires_at'] <= now:
            raise DraftError('This recovery draft has ended. Start a new recovery draft.')
        if row['version'] != expected:
            # A lost acknowledgement may be retried, but stale edits never overwrite.
            if row['payload'] == encoded and row['version'] == expected + 1:
                return dict(version=row['version'], expires_at=row['expires_at'])
            raise DraftError('This recovery draft changed in another tab. Keep this tab open and restore a separate draft.')
        metadata_json = json.dumps(metadata) if metadata else row['property_metadata']
        con.execute('UPDATE workspace_drafts SET version=?,payload=?,property_metadata=?,expires_at=? WHERE dealer_id=? AND principal=? AND draft_id=?',
                    (expected + 1, encoded, metadata_json, now + TTL, dealer, user, draft_id))
    else:
        if expected != 0:
            raise DraftError('This recovery draft has expired or was deleted.')
        con.execute('INSERT INTO workspace_drafts(dealer_id,principal,draft_id,version,expires_at,payload,property_metadata,closed) VALUES(?,?,?,?,?,?,?,0)',
                    (dealer, user, draft_id, 1, now + TTL, encoded, json.dumps(metadata) if metadata else None))
    return dict(version=expected + 1, expires_at=now + TTL)


def close(con, dealer, user, draft_id, now=None, operation=None):
    validate_id(draft_id)
    now = time.time() if now is None else now
    # Scope matches even on receipt replay. Payload and imagery metadata are erased
    # in the same transaction as the estimate, before acknowledging success.
    con.execute('INSERT INTO workspace_drafts(dealer_id,principal,draft_id,version,expires_at,payload,property_metadata,closed,save_operation) VALUES(?,?,?,?,?,NULL,NULL,1,?) ON CONFLICT(dealer_id,principal,draft_id) DO UPDATE SET closed=1,payload=NULL,property_metadata=NULL,expires_at=excluded.expires_at,save_operation=excluded.save_operation',
                (dealer, user, draft_id, 0, now + TTL, operation))
