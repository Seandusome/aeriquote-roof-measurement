"""Account activation reporting; event counts are distinct from signup-cohort conversion."""
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

REPORT_TIMEZONE = 'America/Edmonton'

def parse_event_time(value):
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment
    except (ValueError, TypeError):
        return None

def account_metrics(accounts, now=None):
    zone = ZoneInfo(REPORT_TIMEZONE)
    current = (now or datetime.now(timezone.utc)).astimezone(zone)
    day = current.replace(hour=0, minute=0, second=0, microsecond=0)
    starts = [('Today', day), ('This week', day-timedelta(days=day.weekday())),
              ('This month', day.replace(day=1))]
    rows = []
    for name, start in starts:
        signups = activations = cohort_activated = 0
        for account in accounts:
            signup = parse_event_time(account.get('created_at'))
            activation = parse_event_time(account.get('first_measured_at'))
            in_cohort = signup is not None and start <= signup.astimezone(zone) <= current
            signups += int(in_cohort)
            activations += int(activation is not None and start <= activation.astimezone(zone) <= current)
            cohort_activated += int(in_cohort and activation is not None and activation <= current)
        rows.append(dict(name=name, start=start.strftime('%b %d, %Y'), signups=signups,
                         activations=activations, cohort_activated=cohort_activated,
                         conversion=round(100*cohort_activated/signups,1) if signups else None))
    return rows


def account_plan_report(accounts, now=None):
    """Current plan assignments are not verified billing subscriptions.

    Periods group registration dates by the CURRENT plan, never a historical
    payment, upgrade or cancellation date. Only explicitly QA-labelled businesses
    are excluded; customer estimate contents are never inspected.
    """
    import re
    def is_qa(account):
        return any(re.match(r'^qa[ -]+test(?:\b|_)', str(account.get(key) or '').strip(), re.I)
                   for key in ('dealer_name', 'company'))
    qa = [a for a in accounts if is_qa(a)]
    customers = [a for a in accounts if not is_qa(a)]
    plans = []
    for code, label in [('trial', 'Free trial'), ('basic', 'Basic'), ('pro', 'Pro'),
                        ('business', 'Business'), ('legacy', 'Legacy / other')]:
        group = [a for a in customers if (str(a.get('plan_code') or 'legacy').lower()
                 if str(a.get('plan_code') or 'legacy').lower() in {'trial','basic','pro','business'}
                 else 'legacy') == code]
        plans.append(dict(label=label, total=len(group),
                          enabled=sum(str(a.get('status') or '').lower()=='active' for a in group)))
    periods = account_metrics(customers, now)
    for i, row in enumerate(periods):
        row['trials'] = account_metrics([a for a in customers if a.get('plan_code')=='trial'], now)[i]['signups']
        row['assigned_plans'] = account_metrics([a for a in customers if a.get('plan_code') in {'basic','pro','business'}], now)[i]['signups']
        row['legacy'] = row['signups']-row['trials']-row['assigned_plans']
        row['qa'] = account_metrics(qa, now)[i]['signups']
    return dict(customers=customers, qa_count=len(qa), plans=plans, periods=periods)
