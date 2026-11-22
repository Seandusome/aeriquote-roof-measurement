"""Offline advisory planning only. No app imports, I/O, clock, DB or mutations.

Explicit inventories and ledger attestations are inputs, not authenticated facts.
See docs/RETENTION_RESTORE_PLANNER.md. Outputs NEVER grant access or delete data.
"""
from datetime import timedelta
import json

from standalone_policy import access, instant, stamp, PolicyInputError


class PlannerInputError(ValueError):
    pass


def _required_text(value):
    if not isinstance(value, str) or not value.strip():
        raise PlannerInputError('Nonempty explicit identifier/provenance required')
    return value


def _identity(record):
    return (_required_text(record.get('business_id')),
            _required_text(record.get('id')))


def _encode(value):
    return json.dumps(value, sort_keys=True, allow_nan=False)


def _affects(event, scope):
    # Full content includes its lightweight fields; never expose a full composite
    # whose lightweight data was deleted. Full-only suppression leaves a separate
    # lightweight record intact, but must still reach full child imagery.
    return event['scope'] in ('all', scope) or (scope == 'full' and event['scope'] == 'lightweight')


def _ledger(raw, now, snapshot_at):
    """Fail closed for restore release; never invent a ledger freshness window."""
    issues, entries, covered = [], {}, set()
    try:
        if not isinstance(raw, dict):
            raise PlannerInputError('Deletion ledger missing')
        if raw.get('authoritative') is not True:
            issues.append('Deletion ledger authority unconfirmed')
        through = instant(raw.get('complete_through'))
        if through != now:
            issues.append('Deletion coverage must be explicitly complete through planning time; stale/future coverage unresolved')
        if snapshot_at is not None and raw.get('independent_of_snapshot') is not True:
            issues.append('Ledger must be independent of the restored snapshot')
        businesses = raw.get('covered_business_ids')
        if not isinstance(businesses, list):
            raise PlannerInputError('Explicit ledger business coverage required')
        covered = {_required_text(b) for b in businesses}
        records = raw.get('entries')
        if not isinstance(records, list):
            raise PlannerInputError('Explicit deletion event list required')
        seen, sequences = {}, {}
        for e in records:
            if not isinstance(e, dict):
                raise PlannerInputError('Invalid deletion event')
            eid = _required_text(e.get('event_id'))
            business, rid = _identity({'business_id': e.get('business_id'), 'id': e.get('record_id')})
            if business not in covered:
                raise PlannerInputError('Deletion event outside attested business coverage')
            key = (business, eid)
            encoded = _encode(e)
            if key in seen:
                if seen[key] != encoded:
                    raise PlannerInputError('Conflicting repeated deletion event')
                continue
            seen[key] = encoded
            seq = e.get('sequence')
            if type(seq) is not int or seq < 1:
                raise PlannerInputError('Positive deletion event sequence required')
            skey = (business, seq)
            if skey in sequences:
                raise PlannerInputError('Conflicting deletion event sequence')
            sequences[skey] = eid
            if e.get('kind') not in ('deleted', 'draft_closed') or e.get('scope') not in ('all', 'full', 'lightweight'):
                raise PlannerInputError('Unknown deletion event kind/scope')
            when = instant(e.get('effective_at'))
            if when > now or when > through:
                raise PlannerInputError('Deletion event beyond attested coverage')
            _required_text(e.get('provenance'))
            entries.setdefault((business, rid), []).append(e)
    except (PlannerInputError, PolicyInputError, TypeError, ValueError) as exc:
        issues.append(str(exc))
    return entries, covered, sorted(set(issues))


def _retention(record, now):
    scope = record.get('scope')
    if scope not in ('full', 'lightweight'):
        raise PlannerInputError('Explicit full/lightweight scope required')
    if record['kind'] == 'imagery' and scope != 'full':
        raise PlannerInputError('Imagery cannot be classified as lightweight')
    p = record.get('policy')
    if not isinstance(p, dict) or p.get('business_id') != record['business_id']:
        raise PlannerInputError('Missing or mismatched business policy inputs')
    _required_text(p.get('provenance'))
    retention = p['retention']
    if not isinstance(retention, dict) or not isinstance(p.get('period'), dict):
        raise PlannerInputError('Explicit period and retention mappings required')
    for name in ('legacy_full', 'legacy_lightweight'):
        promise = retention[name]
        if not isinstance(promise, dict):
            raise PlannerInputError('Explicit legacy promise mapping required')
        if promise.get('status') != 'unknown':
            _required_text(promise.get('provenance'))
    result = access(dict(p, now=stamp(now), security_eligible=True))
    # Unknown promises remain unknown even for a current paid account.
    expiry = result[scope + '_expiry']
    if result['review_required'] or expiry is None:
        raise PlannerInputError('Unknown historical promise/deadline; preserve for review')
    if retention[scope + '_present'] is not True:
        raise PlannerInputError('Inventory contradicts supplied scope presence')
    if 'recorded_expiry' in record and instant(record['recorded_expiry']) != instant(expiry):
        raise PlannerInputError('Recorded expiry conflicts with protected calculated deadline')
    if record.get('exceptions') not in (None, []):
        raise PlannerInputError('Scoped exception/hold requires separate review, not customer exposure')
    state = {'paid_active': 'active', 'retained_read_only': 'read_only',
             'expired': 'expired'}.get(result['state'], 'unknown')
    if not result['readable_scopes'][scope]:
        state = 'expired'
    return state, expiry, p['provenance']


def _draft(record, now):
    """Accepted-write clock; retry/login/import is never an accepted write."""
    _required_text(record.get('principal'))
    if record.get('scope', 'all') != 'all':
        raise PlannerInputError('Draft tombstones cover the whole draft')
    provenance = _required_text(record.get('clock_provenance'))
    accepted = instant(record.get('last_accepted_at'))
    if accepted > now:
        raise PlannerInputError('Draft accepted-write clock is in the future')
    expiry = accepted + timedelta(hours=24)
    if 'expires_at' in record and instant(record['expires_at']) != expiry:
        raise PlannerInputError('Draft expiry conflicts with rolling 24-hour accepted-write clock')
    if type(record.get('closed')) is not bool:
        raise PlannerInputError('Explicit draft closed state required')
    if 'save_operation' not in record:
        raise PlannerInputError('Draft save-operation identity/presence must be explicit')
    if record['save_operation'] is not None:
        _required_text(record['save_operation'])
    return ('expired' if record['closed'] or now >= expiry else 'active',
            stamp(expiry), provenance)


def plan_retention(inventory):
    """Return a new plan; invalid top-level contract raises, record gaps HOLD.

    No wall clock is read. Ledger complete_through must equal explicit `now`;
    this is an attestation requirement, NOT proof of actual ledger completeness.
    """
    if not isinstance(inventory, dict) or type(inventory.get('schema')) is not int or inventory['schema'] != 1:
        raise PlannerInputError('Planner schema 1 required')
    now = instant(inventory.get('now'))
    mode = inventory.get('mode')
    if mode not in ('inventory', 'restore'):
        raise PlannerInputError('Explicit inventory/restore mode required')
    snapshot = instant(inventory.get('snapshot_at')) if mode == 'restore' else None
    if snapshot is not None and snapshot > now:
        raise PlannerInputError('Snapshot cannot be in the future')
    records = inventory.get('records')
    if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
        raise PlannerInputError('Explicit record list required')
    # Reject ambiguous/missing identities before emitting any release-looking plan.
    indexed, collisions = {}, set()
    for record in records:
        key = _identity(record)
        if key in indexed:
            collisions.add(key)
        else:
            indexed[key] = record
    events, covered, ledger_issues = _ledger(inventory.get('deletion_ledger'), now, snapshot)
    outputs = {}
    for key, record in sorted(indexed.items()):
        reasons, state, expiry, provenance = [], 'unknown', None, None
        kind = record.get('kind')
        try:
            if key in collisions:
                raise PlannerInputError('Duplicate inventory identity; reconcile copies before release')
            if kind == 'draft':
                state, expiry, provenance = _draft(record, now)
            elif kind in ('estimate', 'revision', 'imagery'):
                state, expiry, provenance = _retention(record, now)
            else:
                raise PlannerInputError('Unsupported record kind')
        except (PlannerInputError, PolicyInputError, KeyError, TypeError, ValueError, OverflowError) as exc:
            state, expiry = 'unknown', None
            reasons.append('Retention facts unresolved: ' + str(exc))
        retention_action = {'active': 'KEEP', 'read_only': 'READ-ONLY',
                            'expired': 'SUPPRESS-ON-RESTORE', 'unknown': 'HOLD'}[state]
        if state != 'unknown':
            reasons.append('Confirmed current paid period/accepted draft clock' if state == 'active' else
                           'Within protected read-only deadline' if state == 'read_only' else
                           'Exact deadline reached or content scope unavailable/closed')
        unresolved = list(ledger_issues)
        if key[0] not in covered:
            unresolved.append('Business not covered by deletion ledger')
        scope = record.get('scope', 'all')
        matching = [e for e in events.get(key, []) if _affects(e, scope)]
        # A draft-closed event may never act on an estimate with the same ID.
        if any((e['kind'] == 'draft_closed') != (kind == 'draft') for e in matching):
            unresolved.append('Deletion event kind does not match record kind')
        closed = kind == 'draft' and record.get('closed') is True
        known_deleted = bool(matching) and not unresolved
        action = 'HOLD' if unresolved or state == 'unknown' else retention_action
        if closed or known_deleted:
            action = 'SUPPRESS-ON-RESTORE'
            reasons.append('Closed draft/tombstone: preserve closed ID and save-operation identity' if closed else
                           'Authoritative scoped deletion event forbids restoration to customer access')
        if unresolved:
            reasons += unresolved
        outputs[key] = dict(business_id=key[0], id=key[1], kind=kind, scope=scope,
                            state=state, expiry=expiry, provenance=provenance,
                            retention_action=retention_action, restore_action=action,
                            proposed_action=action if mode == 'restore' else retention_action,
                            quarantine_required=action in ('HOLD', 'SUPPRESS-ON-RESTORE'),
                            review_required=bool(unresolved) or state == 'unknown',
                            deletion_history='unresolved' if unresolved else 'known_deleted' if known_deleted else 'covered_no_deletion',
                            deletion_event_ids=sorted(e['event_id'] for e in matching),
                            reasons=sorted(set(reasons)))
    # All parents must be in the same business inventory. Never join on ID alone.
    def ancestors(key):
        seen = {key}
        current = key
        while True:
            r = indexed[current]
            parent = r.get('parent_id')
            if parent is None:
                if r.get('kind') in ('revision', 'imagery'):
                    raise PlannerInputError('Revision/media requires its parent inventory record')
                return
            target = (key[0], _required_text(parent))
            if target not in indexed:
                raise PlannerInputError('Missing or cross-business parent; cannot release linked content')
            if target in seen:
                raise PlannerInputError('Cyclic parent references')
            parent_kind = indexed[target].get('kind')
            if ((r.get('kind') == 'revision' and parent_kind != 'estimate') or
                    (r.get('kind') == 'imagery' and parent_kind not in ('estimate', 'revision')) or
                    r.get('kind') not in ('revision', 'imagery')):
                raise PlannerInputError('Invalid parent record kind')
            seen.add(target)
            yield target
            current = target
    # Propagate from direct ancestry, not iteration order. A suppressed/held parent
    # quarantines revisions/media too; it never triggers physical deletion.
    original = {k: v['restore_action'] for k, v in outputs.items()}
    for key, out in outputs.items():
        try:
            chain = list(ancestors(key))
            inherited = [e for parent in chain for e in events.get(parent, [])
                         if _affects(e, out['scope']) and e['kind'] == 'deleted']
            if inherited and not ledger_issues and key[0] in covered:
                out['restore_action'] = 'SUPPRESS-ON-RESTORE'
                out['quarantine_required'] = True
                out['deletion_history'] = 'known_deleted'
                out['deletion_event_ids'] = sorted(set(out['deletion_event_ids'] + [e['event_id'] for e in inherited]))
                out['reasons'].append('Authoritative ancestor deletion applies to this content scope')
                if mode == 'restore':
                    out['proposed_action'] = out['restore_action']
            if any(original[p] in ('HOLD', 'SUPPRESS-ON-RESTORE') for p in chain):
                raise PlannerInputError('Parent scope suppressed or unresolved; quarantine linked content')
        except PlannerInputError as exc:
            if out['restore_action'] != 'SUPPRESS-ON-RESTORE':
                out['restore_action'] = 'HOLD'
            if mode == 'restore':
                out['proposed_action'] = out['restore_action']
            out['quarantine_required'] = True
            out['review_required'] = True
            out['reasons'].append(str(exc))
    return dict(schema=1, now=stamp(now), mode=mode,
                snapshot_at=stamp(snapshot) if snapshot else None,
                advisory_only=True, writes_performed=False, access_granted=False,
                provider_backup_lifetimes='unknown', ledger_issues=ledger_issues,
                records=list(outputs.values()),
                restore_release_recommended=all(not v['quarantine_required'] for v in outputs.values()) and not ledger_issues,
                requires_independent_release_review=True)
