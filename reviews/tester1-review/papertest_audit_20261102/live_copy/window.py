"""Pass-window helpers for extra NHL list passes (added 2026-10-17).

in_window(start, now, has_snapshot): puck drop 150-210 min from now, or 210-240 min if a D snapshot exists.
pre_noon(start): puck drop before 12:00 PM America/Los_Angeles (draft prereg: never scored in window mode).
merge_keep(path, new_df, replace_ids, key='gameId'): text-level merge into an existing CSV.
  - rows of games NOT in replace_ids are kept byte-identical (raw lines copied)
  - rows of games in replace_ids are dropped, and new_df rows (aligned to the existing header) appended
  Returns (kept_games, written_games)."""
import csv, io, os
import pandas as pd
from zoneinfo import ZoneInfo
PT = ZoneInfo('America/Los_Angeles')
WIN_LO, WIN_HI, WIN_MAX = 150, 210, 240

def ts(s):
    t = pd.Timestamp(s)
    return t.tz_localize('UTC') if t.tzinfo is None else t

def mins_to(start, now): return (ts(start) - ts(now)).total_seconds() / 60

PRE_NOON_LAST_DATE = '2026-11-01'  # 2026-11-02: exclusion removed per user approval (Nov 1); games from Nov 2 on are eligible
def pre_noon(start):
    t = ts(start).tz_convert(PT)
    return t.hour < 12 and t.strftime('%Y-%m-%d') <= PRE_NOON_LAST_DATE

def in_window(start, now, has_snapshot=True):
    m = mins_to(start, now)
    return WIN_LO <= m <= WIN_HI or (has_snapshot and WIN_HI < m <= WIN_MAX)

def existing_ids(path, key='gameId'):
    if not os.path.exists(path): return set()
    try: return set(pd.read_csv(path, usecols=[key])[key].astype(int))
    except Exception: return set()

def merge_keep(path, new_df, replace_ids, key='gameId'):
    replace_ids = {int(x) for x in replace_ids}
    if not os.path.exists(path):
        new_df.to_csv(path, index=False); return set(), set(new_df[key].astype(int))
    raw = open(path, newline='').read().splitlines(keepends=True)
    header = next(csv.reader([raw[0]])); ki = header.index(key)
    body = [l for l in raw[1:] if l.strip()]
    assert len(body) == len(pd.read_csv(path)), f'{path}: multi-line CSV fields; cannot merge at text level'
    keep = [l for l in body if int(float(next(csv.reader([l]))[ki])) not in replace_ids]
    kept_games = {int(float(next(csv.reader([l]))[ki])) for l in keep}
    extra = [c for c in new_df.columns if c not in header]
    if extra: print(f'merge_keep: dropping columns not in {os.path.basename(path)} header: {extra}')
    buf = io.StringIO(); new_df.reindex(columns=header).to_csv(buf, index=False, header=False)
    new_lines = buf.getvalue().splitlines(keepends=True)
    nl = '\r\n' if raw[0].endswith('\r\n') else '\n'
    if keep and not keep[-1].endswith(('\n', '\r')): keep[-1] += nl
    open(path, 'w', newline='').write(raw[0] + ''.join(keep) + ''.join(new_lines))
    return kept_games, set(new_df[key].astype(int))
