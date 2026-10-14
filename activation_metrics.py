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
