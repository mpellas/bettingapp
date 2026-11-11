"""12-hour stale-lineup skip (added 2026-11-03, testers' approved rule; Tester2).
A side is skipped when the DailyFaceoff lineup used for the gate/role checks (DFO 'updatedAt', stored as dfo_updated
in the GATE csv) is more than 12 hours older than the list build time. Missing/unparseable timestamp -> SKIP
(we cannot prove the lineup is fresh). Exactly 12h is still fresh. Never touches the model, features or --rescore."""
from datetime import datetime, timezone
import pandas as pd
STALE_H = 12.0
REASON_STALE = 'lineup stale >12h'
REASON_MISSING = 'lineup timestamp missing'

def age_hours(updated, now=None):
    """Hours between DFO updatedAt and now (UTC). None if missing/unparseable."""
    if updated is None or (isinstance(updated, float) and pd.isna(updated)) or str(updated).strip() in ('', 'nan', 'None'):
        return None
    try:
        t = pd.Timestamp(str(updated))
        t = t.tz_localize('UTC') if t.tzinfo is None else t.tz_convert('UTC')
    except Exception:
        return None
    now = pd.Timestamp(now or datetime.now(timezone.utc))
    now = now.tz_localize('UTC') if now.tzinfo is None else now.tz_convert('UTC')
    return (now - t).total_seconds() / 3600.0

def stale_reason(updated, now=None):
    """'' if fresh, else the skip reason text."""
    a = age_hours(updated, now)
    if a is None: return REASON_MISSING
    if a > STALE_H: return f'{REASON_STALE} ({a:.1f}h old)'
    return ''
