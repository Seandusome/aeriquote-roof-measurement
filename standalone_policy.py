"""Pure AeriQuote policy calculations. NOT imported by the application.

Explicit, trusted snapshots only; outputs are advisory, never authorization.
No I/O, wall clock, database, network, event persistence or destructive actions.
See docs/STANDALONE_POLICY_EVALUATOR.md for the input contract and limitations.
"""
from datetime import datetime, timedelta, timezone
import calendar
import json

UTC = timezone.utc
LIMITS = {'basic': 25, 'pro': 75, 'business': 200}
CHANNELS = ('lookups', 'estimates')


class PolicyInputError(ValueError):
    pass


def instant(value):
    if not isinstance(value, str):
        raise PolicyInputError('Explicit timezone-aware timestamp required')
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise PolicyInputError('Invalid timestamp') from exc
    if result.tzinfo is None:
        raise PolicyInputError('Naive timestamps are not accepted')
    return result.astimezone(UTC)


def stamp(value):
    return value.isoformat(timespec='microseconds').replace('+00:00', 'Z')


def integer(value):
    if type(value) is not int or value < 0:
        raise PolicyInputError('Nonnegative integer required')
    return value


def boolean(value):
    if type(value) is not bool:
        raise PolicyInputError('Explicit boolean required')
    return value


def plan(value):
    if value not in LIMITS:
        raise PolicyInputError('Unknown plan')
    return value


def monthly_boundary(anchor, index):
    """UTC monthly anniversary; clamp short months using ORIGINAL anchor day."""
    anchor = instant(anchor)
    index = integer(index)
    year, month = divmod(anchor.year * 12 + anchor.month - 1 + index, 12)
    month += 1
    return stamp(anchor.replace(year=year, month=month,
                               day=min(anchor.day, calendar.monthrange(year, month)[1])))


def _unique(records):
    """Same ID+identical facts collapse; changed facts for same ID are ambiguous."""
    if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
        raise PolicyInputError('Explicit event-record list required')
    found = {}
    for record in records:
        key = record.get('id')
        if not isinstance(key, str) or not key:
            raise PolicyInputError('Event ID required')
        encoded = json.dumps(record, sort_keys=True, allow_nan=False)
        if key in found and found[key][0] != encoded:
            raise PolicyInputError('Conflicting facts for repeated event ID')
        found[key] = (encoded, record)
    return [item[1] for item in found.values()]


def _deadline(base, promise):
    status = promise['status']
    if status == 'unknown':
        return None  # Unknown protected promise cannot be shortened to base.
    if status == 'none':
        return base
    if status == 'known':
        return max(base, instant(promise['deadline']))
    raise PolicyInputError('Unknown legacy promise status')


def access(snapshot):
    """Selected retained record only: full and lightweight scopes stay separate."""
    now = instant(snapshot['now'])
    p = snapshot['period']
    start, end = instant(p['start']), instant(p['end'])
    if start >= end:
        raise PolicyInputError('Invalid paid period')
    if p['payment_status'] not in ('succeeded', 'pending', 'failed'):
        raise PolicyInputError('Unknown period payment status')
    paid = p['payment_status'] == 'succeeded' and start <= now < end
    r = snapshot['retention']
    previous_end = instant(r['paid_access_end'])
    if not paid and now < previous_end:
        raise PolicyInputError('Unconfirmed access before supplied paid-access end; reconcile period')
    base = previous_end + timedelta(days=120)
    full = _deadline(base, r['legacy_full'])
    light = _deadline(base, r['legacy_lightweight'])
    if full is None:
        light = None  # Unknown full promise also protects its lightweight fields.
    if full is not None and light is not None:
        light = max(full, light)  # Full content includes its lightweight fields.
    present = boolean(r['full_present'])
    light_present = boolean(r['lightweight_present'])
    if present and not light_present:
        raise PolicyInputError('Full content requires lightweight record presence')
    candidates = {}
    for key, deadline, exists in [('full', full, present), ('lightweight', light, light_present)]:
        candidates[key] = None if exists and deadline is None else bool(exists and now < deadline) if deadline is not None else False
    activation = snapshot.get('reactivation')
    eligible = {'full': False, 'lightweight': False}
    restored = {'full': False, 'lightweight': False}
    unknown_activation = False
    if activation is not None:
        if activation['payment_status'] not in ('succeeded', 'pending', 'failed'):
            raise PolicyInputError('Unknown reactivation payment status')
        if activation['payment_status'] == 'succeeded':
            confirmed = instant(activation['confirmed_at'])
            if confirmed > now or activation['period_id'] != p['id'] or not paid:
                raise PolicyInputError('Reactivation requires a matching confirmed current paid period')
            if confirmed < instant(r['paid_access_end']):
                raise PolicyInputError('Reactivation precedes end of previous paid access')
            for key, deadline, exists in [('full', full, present), ('lightweight', light, light_present)]:
                eligible[key] = None if deadline is None and exists else bool(exists and confirmed < deadline) if deadline is not None else False
                restored[key] = eligible[key]
            unknown_activation = any(v is None for v in eligible.values())
    retained_full = present and (full is None or now < full)
    retained_light = light_present and (light is None or now < light)
    # Do not declare an unknown legacy promise expired or promise restoration.
    unknown = (present and full is None) or (light_present and light is None)
    if not boolean(snapshot['security_eligible']):
        state = 'denied'
    elif paid:
        state = 'paid_active'
    elif unknown:
        state = 'review_required'
    elif retained_full or retained_light:
        state = 'retained_read_only'
    else:
        state = 'expired'
    scopes = {
        'full': bool(present and ((paid and not activation) or restored['full'] is True or (full is not None and now < full))),
        'lightweight': bool(light_present and ((paid and not activation) or restored['lightweight'] is True or (light is not None and now < light))),
    }
    if state in ('denied', 'review_required', 'expired'):
        scopes = dict(full=False, lightweight=False)
    return dict(state=state, base_expiry=stamp(base), full_expiry=stamp(full) if full else None,
                lightweight_expiry=stamp(light) if light else None,
                deadline_label=(stamp(full) + ' (UTC)') if full else 'Unknown — preserve prior promise; review required',
                reactivation_candidate_scopes=candidates,
                reactivation_eligible=eligible, restored_scopes=restored,
                readable_scopes=scopes, can_create_or_edit=state == 'paid_active',
                can_download_full=scopes['full'], recovery_of_deleted_work=False,
                review_required=unknown or unknown_activation)


def entitlements(snapshot):
    """Calculate current-period caps; attribution is mandatory for paid upgrades.

    Reversal removes delta-consumed, preserving consumed benefits and all usage.
    A complete immutable ledger is an INPUT, not a persisted event processor.
    """
    p = snapshot['period']
    if not isinstance(p['id'], str) or not p['id']:
        raise PolicyInputError('Explicit period ID required')
    if p['payment_status'] != 'succeeded':
        raise PolicyInputError('Confirmed period payment required; do not mint allowance')
    current_plan = plan(p['plan'])
    cap = {c: LIMITS[current_plan] for c in CHANNELS}
    used = {c: integer(snapshot['used'][c]) for c in CHANNELS}
    extras = {c: integer(snapshot['extras'][c]) for c in CHANNELS}
    consumed_total = dict.fromkeys(CHANNELS, 0)
    all_delta = 0
    upgrades = _unique(snapshot['upgrades'])
    paid = []
    for event in upgrades:
        if event['business_id'] != snapshot['business_id']:
            raise PolicyInputError('Upgrade belongs to another business')
        if event['period_id'] != p['id']:
            raise PolicyInputError('Upgrade belongs to another period; reconcile explicitly')
        status = event['payment_status']
        if status not in ('succeeded', 'pending', 'failed'):
            raise PolicyInputError('Unknown upgrade payment status')
        if status == 'succeeded':
            when = instant(event['confirmed_at'])
            if not instant(p['start']) <= when < instant(p['end']) or when > instant(snapshot['now']):
                raise PolicyInputError('Upgrade confirmation outside the evaluated period/time')
            paid.append((when, event['id'], event))
    results = []
    for _, _, event in sorted(paid):
        before, target = plan(event['from_plan']), plan(event['to_plan'])
        if before != current_plan or LIMITS[target] <= LIMITS[before]:
            raise PolicyInputError('Upgrade chain is ambiguous')
        if not isinstance(event.get('attribution_source'), str) or not event['attribution_source']:
            raise PolicyInputError('Upgrade consumption attribution source required')
        delta = LIMITS[target] - LIMITS[before]
        consumed = {c: integer(event['consumed'][c]) for c in CHANNELS}
        if any(n > delta for n in consumed.values()):
            raise PolicyInputError('Consumed upgrade attribution exceeds its delta')
        reversals = _unique(event['reversals'])
        confirmed_reversals = []
        for reversal in reversals:
            if reversal['status'] not in ('succeeded', 'pending', 'failed'):
                raise PolicyInputError('Unknown reversal status')
            if reversal['status'] == 'succeeded':
                if reversal['kind'] != 'full':
                    raise PolicyInputError('Partial reversal needs explicit attributable unit allocation')
                at = instant(reversal['confirmed_at'])
                if at < instant(event['confirmed_at']) or at > instant(snapshot['now']):
                    raise PolicyInputError('Invalid reversal confirmation time')
                if at >= instant(p['end']):
                    raise PolicyInputError('Cross-period reversal needs explicit reconciliation')
                confirmed_reversals.append(reversal)
        if len(confirmed_reversals) > 1:
            raise PolicyInputError('Multiple distinct full reversals require reconciliation')
        reversed_ = bool(confirmed_reversals)
        if reversed_ and len(paid) > 1:
            raise PolicyInputError('Reversed multi-upgrade chain needs explicit reconciliation')
        removed = {c: delta - consumed[c] if reversed_ else 0 for c in CHANNELS}
        for c in CHANNELS:
            cap[c] += delta - removed[c]
            consumed_total[c] += consumed[c]
        all_delta += delta
        if not reversed_:
            current_plan = target
        results.append(dict(id=event['id'], delta=delta, removed_unused=removed,
                            preserved_consumed=consumed, reversed=reversed_))
    base = LIMITS[plan(p['plan'])]
    if any(consumed_total[c] > used[c] or used[c] - consumed_total[c] > base
           or used[c] > base + all_delta for c in CHANNELS):
        raise PolicyInputError('Recorded usage and attributable upgrade consumption disagree')
    remaining = {c: max(0, cap[c] - used[c]) for c in CHANNELS}
    return dict(plan=current_plan, caps=cap, used=used, extras=extras,
                remaining_monthly=remaining,
                remaining_with_extras={c: remaining[c] + extras[c] for c in CHANNELS},
                upgrades=results, deduction_order='monthly_then_relevant_extras',
                period_id=p['id'], renewal_at=stamp(instant(p['end'])))


def schedule(snapshot):
    p = snapshot['period']
    start, end = instant(p['start']), instant(p['end'])
    if start >= end:
        raise PolicyInputError('Invalid period')
    anchor = instant(p['renewal_anchor'])
    if anchor > start:
        raise PolicyInputError('Renewal anchor cannot be later than period start')
    index = (end.year - anchor.year) * 12 + end.month - anchor.month
    if index < 1 or instant(monthly_boundary(p['renewal_anchor'], index)) != end:
        raise PolicyInputError('Period end does not match original monthly billing anchor')
    if instant(monthly_boundary(p['renewal_anchor'], index - 1)) != start:
        raise PolicyInputError('Period start does not match original monthly billing anchor')
    cancel = snapshot.get('cancellation')
    effective = None
    if cancel is not None:
        if instant(cancel['requested_at']) > instant(snapshot['now']):
            raise PolicyInputError('Future cancellation request')
        effective = stamp(end)
    effective_plan = entitlements(snapshot)['plan']
    downgrade = snapshot.get('downgrade')
    target = plan(downgrade) if downgrade is not None else None
    if target and LIMITS[target] >= LIMITS[effective_plan]:
        raise PolicyInputError('Scheduled downgrade must reduce current base plan')
    return dict(cancellation_effective_at=effective, renewal_scheduled=cancel is None,
                next_renewal_at=stamp(end) if cancel is None else None,
                following_boundary=monthly_boundary(p['renewal_anchor'], index + 1),
                next_plan_if_success=target or effective_plan,
                renewal_status='canceled' if cancel else ('due_unconfirmed' if instant(snapshot['now']) >= end else 'upcoming'),
                downgrade_effective_at=stamp(end) if target else None,
                downgrade_requires_successful_renewal=bool(target),
                monthly_reset_requires_confirmed_success=True,
                reset_applied=False, payment_proration_calculated=False)


def evaluate(snapshot):
    """Return advisory calculations; malformed/ambiguous input never guessed."""
    if not isinstance(snapshot, dict):
        return dict(advisory_only=True, review_required=True, issues=['Snapshot object required'])
    result = dict(schema=1, business_id=snapshot.get('business_id'), advisory_only=True,
                  review_required=False, issues=[], access=None, schedule=None, entitlements=None)
    if snapshot.get('schema') != 1 or type(snapshot.get('schema')) is not int:
        result['review_required'] = True
        result['issues'].append('Explicit supported schema=1 required')
        return result
    if not isinstance(snapshot.get('business_id'), str) or not snapshot['business_id']:
        result['review_required'] = True
        result['issues'].append('business_id: explicit fictional/business identity required')
        return result
    for name, calculation in [('access', access), ('schedule', schedule), ('entitlements', entitlements)]:
        try:
            result[name] = calculation(snapshot)
        except (KeyError, PolicyInputError, TypeError, ValueError, OverflowError) as exc:
            result['review_required'] = True
            result['issues'].append(name + ': ' + str(exc))
    if result['access'] and result['access']['review_required']:
        result['review_required'] = True
    # Never present an actionable permission when any required input is unresolved.
    if result['review_required'] and result['access']:
        result['access']['can_create_or_edit'] = False
        result['access']['can_download_full'] = False
        result['access']['readable_scopes'] = dict(full=False, lightweight=False)
    return result
