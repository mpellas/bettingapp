"""Fliff second pull for NHL shots on goal (approved by yinzerduck 2026-11-03).

Usage: python3 fliff_repull.py [YYYYMMDD] [--dry-run] [--now 'YYYY-MM-DDTHH:MM'] [--cap 10] [--mock DIR]
  Scheduled use: python3 fliff_repull.py            (today, real pull for games 50-75 min out)
  --dry-run : no Odds API call at all (no /events, no /odds); reports what would be pulled.
  --now     : pretend the PT clock reads this time (testing the 50-75 min window).
  --mock DIR: read <DIR>/<odds_event_id>.json instead of the paid call (testing; logs cost 0).

Sides: every side on the day's posted lists whose Fliff result was "not posted" / "not offered on Fliff (yet)":
  - picks/<date>_*_room.txt and _post.txt lines containing "Fliff not posted" or "not offered on Fliff"
  - fliff_prices/<date>_*.csv rows with fliff_status starting "not offered" (first pull results)
  game / shop-at come from sheets/<date>_*.xlsx (Picks tab), gameId / odds event from the D files and first-pull csvs.
Window: puck drop (game_starts.starts_for, local captures then free NHL API) 50-75 min after now.
Per game: ONE paid call, same as fliff_prices.py (/events/{id}/odds, markets=player_shots_on_goal,
  bookmakers=fliff,draftkings, ~1 credit). Marker fliff_repull_done/<date>_<event>: never pulled twice.
Cap: the shared fliff_credits_<date>.csv (same file and accounting as fliff_prices.py: sum of cost,
  expected = last cost or 1); skipped and logged if spent + expected > cap.
Output: fliff_repull_log.csv (one row per side, for grading), raw json in captures/fliff_<date>_<HHMM>_<event>.json,
  room-ready summary on stdout (nothing if no game is due). Paper only: never edits picks/, sheets/, the model,
  predict.py, graders or --rescore."""
import sys, os, re, glob, csv, json, argparse, datetime as dt
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE); sys.path.insert(0, HERE)
import fliff_prices as fp
import game_starts
PT = fp.PT; LOG = 'fliff_repull_log.csv'; MARK = 'fliff_repull_done'
TXT_RE = re.compile(r'^-\s*(.+?)\s+(over|under)\s+([\d.]+)\s.*?(Fliff not posted|not offered on Fliff)', re.I)
COLS = ['run_time_pt', 'date', 'player', 'game', 'side', 'line', 'gameId', 'odds_event', 'puck_drop_pt', 'mins_to_drop',
        'first_status', 'source', 'repull_status', 'fliff_line', 'fliff_price', 'fliff_shop_at', 'beats_shop_at',
        'dk_line_now', 'dk_price_now', 'credits_after', 'dry_run']

def collect(date):
    rows = []
    for f in sorted(glob.glob(f'picks/{date}_*_room.txt') + glob.glob(f'picks/{date}_*_post.txt')):
        for ln in open(f).read().splitlines():
            m = TXT_RE.match(ln.strip())
            if m: rows.append(dict(player=m[1].strip(), side=m[2].upper(), line=float(m[3]), first_status='not posted', source=os.path.basename(f)))
    for f in sorted(glob.glob(f'fliff_prices/{date}_*.csv')):
        d = pd.read_csv(f)
        for _, r in d[d.fliff_status.astype(str).str.startswith('not offered')].iterrows():
            rows.append(dict(player=r.player, side=r.side.upper(), line=float(r.line), first_status=r.fliff_status, source=os.path.basename(f),
                             game=r.game, gameId=r.gameId, odds_event=r.odds_event, fliff_shop_at=r.fliff_shop_at))
    if not rows: return pd.DataFrame()
    S = pd.DataFrame(rows); S['_k'] = S.player.map(fp.norm) + '|' + S.side + '|' + S.line.astype(str)
    # a side the first pull later found offered is not "not offered": drop it if any later pull of the same side was offered
    offered = set()
    for f in sorted(glob.glob(f'fliff_prices/{date}_*.csv')):
        d = pd.read_csv(f); d = d[d.fliff_status.astype(str).isin(['offered', 'different line'])]
        offered |= set(d.player.map(fp.norm) + '|' + d.side.str.upper() + '|' + d.line.astype(float).astype(str))
    S = S[~S._k.isin(offered)]
    # fill game / shop-at from sheets, gameId from D files, odds_event from any first-pull csv
    sh = [pd.read_excel(f, sheet_name=0) for f in sorted(glob.glob(f'sheets/{date}_*.xlsx'))]
    if sh:
        X = pd.concat(sh); X['_k'] = X.player.map(fp.norm) + '|' + X.side.str.upper() + '|' + X.line.astype(float).astype(str)
        X = X.drop_duplicates('_k', keep='last').set_index('_k')
        for c in ('game', 'fliff_shop_at'):
            S[c] = S[c].where(S[c].notna(), S._k.map(X[c])) if c in S else S._k.map(X[c])
    D = [pd.read_csv(f) for f in sorted(glob.glob(f'picks/{date}_D*.csv')) if 'GATE' not in f and 'verify' not in f]
    if D:
        D = pd.concat(D); D = D[D.game.notna() & D.gameId.notna()].drop_duplicates('game', keep='last').set_index('game')
        S['gameId'] = S['gameId'].where(S['gameId'].notna(), S.game.map(D.gameId)) if 'gameId' in S else S.game.map(D.gameId)
    ev = S.dropna(subset=['odds_event']).drop_duplicates('game').set_index('game').odds_event if 'odds_event' in S else pd.Series(dtype=str)
    S['odds_event'] = S.game.map(ev)
    # keep the first-pull wording when both sources name the side
    S = S.sort_values('source', key=lambda s: s.str.endswith('.csv'), ascending=False).drop_duplicates('_k')
    S['skip'] = gate_failures(date, S, X if sh else None)
    return S.reset_index(drop=True)

AGREE_MIN = 3          # room 2-of-7 rule: a side with only 2 (or fewer) of 7 signals agreeing is skipped
SHOP_FLOOR = -150      # price band: a shop-at price below -150 can never be bet
ROOM_AGREE = re.compile(r'^-\s*(.+?)\s+(over|under)\s+([\d.]+)\s.*?(\d+) of 7 agree', re.I)

def gate_failures(date, S, X):
    """Every gate except the Fliff price, from recorded data: sheet status (edge floor, vetoes, lineup/stale gates),
    agreement count (room text, which records manual adjustments, else sheet agrees_n), shop-at band.
    Returns '' for a real candidate, else 'skipped: failed <gate>; ...'."""
    room = {}
    for f in sorted(glob.glob(f'picks/{date}_*_room.txt')):
        for ln in open(f).read().splitlines():
            m = ROOM_AGREE.match(ln.strip())
            if m: room[fp.norm(m[1].strip()) + '|' + m[2].upper() + '|' + str(float(m[3]))] = int(m[4])
    out = []
    for _, s in S.iterrows():
        why = []
        r = X.loc[s._k] if X is not None and s._k in X.index else None
        if r is not None and str(r.get('status', '')).strip().lower() != 'fliff check':
            why.append(f"sheet status {r.get('status')} ({r.get('status_reason')})")
        n = room.get(s._k, r.get('agrees_n') if r is not None else None)
        if n is None or pd.isna(n): why.append('agreement (no agrees_n recorded)')
        elif int(n) < AGREE_MIN: why.append(f'2-of-7 agreement rule ({int(n)} of 7 agree)')
        shop = s.get('fliff_shop_at')
        if pd.isna(shop): why.append('price band (no shop-at recorded)')
        elif shop < SHOP_FLOOR: why.append(f'price band (shop-at {int(shop):+d} below {SHOP_FLOOR})')
        out.append('skipped: failed ' + '; '.join(why) if why else '')
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('date', nargs='?')
    ap.add_argument('--dry-run', action='store_true'); ap.add_argument('--now'); ap.add_argument('--cap', type=int, default=10)
    ap.add_argument('--mock'); ap.add_argument('--min', type=int, default=50); ap.add_argument('--max', type=int, default=75)
    a = ap.parse_args()
    now = dt.datetime.fromisoformat(a.now).replace(tzinfo=PT) if a.now else dt.datetime.now(PT)
    date = a.date or now.strftime('%Y%m%d'); hhmm = now.strftime('%H%M')
    credit_log = f'fliff_credits_{date}.csv'
    S = collect(date)
    if S.empty: return
    starts = game_starts.starts_for(S.gameId.dropna().astype(int).unique())
    S['puck'] = S.gameId.map(lambda g: starts.get(int(g)) if pd.notna(g) else None)
    S['mins'] = S.puck.map(lambda p: (p - now).total_seconds() / 60 if p is not None else None)
    due = S[S.mins.between(a.min, a.max)].copy()
    if due.empty: return
    lines, notes, out = [], [], []
    events = None
    for game, G in due.groupby('game', sort=False):
        ev = G.odds_event.iloc[0]
        if pd.isna(ev) and (G.skip == '').any():
            if a.dry_run: notes.append(f'{game}: odds event not in first-pull csv; live run would look it up (free /events)'); ev = None
            else:
                if events is None: events, _ = fp.get(f'{fp.BASE}/events?apiKey={fp.key()}')
                ev = (fp.match_event(game, events) or {}).get('id')
        C = G[G.skip == '']
        if C.empty:
            notes.append(f'{game}: no side cleared every gate except the Fliff price; not pulled (0 credits)')
            lines.append(f"{game} (puck drop {G.puck.iloc[0].strftime('%-I:%M %p')} PT, {G.mins.iloc[0]:.0f} min out): not pulled")
            for _, s in G.iterrows():
                lines.append(f"- {s.player} {s.side.lower()} {s.line:g}: {s.skip}")
                out.append(dict(run_time_pt=now.isoformat(timespec='seconds'), date=date, player=s.player, game=game, side=s.side, line=s.line,
                                gameId=s.gameId, odds_event=ev, puck_drop_pt=s.puck.isoformat(), mins_to_drop=round(s.mins),
                                first_status=s.first_status, source=s.source, repull_status=s.skip, fliff_shop_at=s.get('fliff_shop_at'),
                                credits_after=fp.spent(credit_log)[0], dry_run=a.dry_run))
            continue
        mk = os.path.join(MARK, f'{date}_{ev or fp.norm(game)}')
        tot, last = fp.spent(credit_log); exp = last or 1
        d = None; status_all = None
        if os.path.exists(mk): notes.append(f'{game}: already re-pulled ({open(mk).read().strip()}); not pulled again'); continue
        if ev is None and not a.dry_run: status_all = 'game not found in Odds API events'
        elif tot + exp > a.cap:
            status_all = f'skipped: cap reached ({tot}/{a.cap} credits today)'; notes.append(f'{game}: {status_all}')
        elif a.dry_run: status_all = f'dry run: would pull (~{exp} credit, {tot}/{a.cap} used)'
        else:
            if a.mock: d, h = json.load(open(os.path.join(a.mock, f'{ev}.json'))), {'x-requests-last': '0', 'x-requests-remaining': 'mock'}
            else: d, h = fp.get(f'{fp.BASE}/events/{ev}/odds?apiKey={fp.key()}&markets=player_shots_on_goal&bookmakers=fliff,draftkings&oddsFormat=american')
            t = dt.datetime.now(PT)
            os.makedirs('captures', exist_ok=True)
            json.dump(d, open(f'captures/fliff_{date}_{hhmm}_{ev}.json', 'w'))
            new = not os.path.exists(credit_log)
            with open(credit_log, 'a', newline='') as f:
                w = csv.writer(f)
                if new: w.writerow(['time_pt', 'event', 'cost', 'x_requests_remaining'])
                w.writerow([t.isoformat(timespec='seconds'), ev, h.get('x-requests-last', ''), h.get('x-requests-remaining', '')])
            os.makedirs(MARK, exist_ok=True); open(mk, 'w').write(f'{t.isoformat(timespec="seconds")} repull{" (mock)" if a.mock else ""}\n')
        book = {}
        for bk in (d or {}).get('bookmakers', []):
            for m in bk.get('markets', []):
                if m.get('key') != 'player_shots_on_goal': continue
                for o in m.get('outcomes', []):
                    book.setdefault(bk['key'], {}).setdefault(fp.norm(o.get('description', '')), []).append((o['name'].upper(), float(o['point']), int(o['price'])))
        cred, _ = fp.spent(credit_log)
        lines.append(f"{game} (puck drop {G.puck.iloc[0].strftime('%-I:%M %p')} PT, {G.mins.iloc[0]:.0f} min out):")
        for _, s in G.iterrows():
            def find(b):
                o = [x for x in book.get(b, {}).get(fp.norm(s.player), []) if x[0] == s.side]
                return ([x for x in o if x[1] == s.line] or o or [None])[0]
            f, k = find('fliff'), find('draftkings'); beats = None; shop = s.get('fliff_shop_at')
            if s.skip: st = s.skip; f = k = None; beats = None
            elif status_all: st = status_all
            elif f is None: st = 'still not offered'
            elif f[1] != s.line: st = 'different line'
            else:
                st = 'offered'; beats = pd.notna(shop) and fp.dec(f[2]) >= fp.dec(shop)
            shop_s = f'{int(shop):+d}' if pd.notna(shop) else '?'
            if st == 'offered': txt = f"Fliff {f[2]:+d}, {'beats' if beats else 'worse than'} shop-at {shop_s}"
            elif st == 'different line': txt = f'different line on Fliff ({s.side} {f[1]:g} at {f[2]:+d}); shop-at {shop_s} does not apply'
            elif s.skip: txt = st
            else: txt = f'{st} (shop-at {shop_s})'
            lines.append(f"- {s.player} {s.side.lower()} {s.line:g}: {txt}")
            out.append(dict(run_time_pt=now.isoformat(timespec='seconds'), date=date, player=s.player, game=game, side=s.side, line=s.line,
                            gameId=s.gameId, odds_event=ev, puck_drop_pt=s.puck.isoformat(), mins_to_drop=round(s.mins),
                            first_status=s.first_status, source=s.source, repull_status=st, fliff_line=f[1] if f else None,
                            fliff_price=f[2] if f else None, fliff_shop_at=shop, beats_shop_at=beats,
                            dk_line_now=k[1] if k else None, dk_price_now=k[2] if k else None, credits_after=cred, dry_run=a.dry_run))
    if out and not a.dry_run:
        new = not os.path.exists(LOG)
        with open(LOG, 'a', newline='') as f:
            w = csv.DictWriter(f, fieldnames=COLS)
            if new: w.writeheader()
            w.writerows(out)
    if not lines and not notes: return
    tot, _ = fp.spent(credit_log)
    print(f"{'[DRY RUN] ' if a.dry_run else ''}Fliff second pull, NHL shots on goal, {date} ({now.strftime('%-I:%M %p')} PT). Paper only.")
    for l in lines: print(l)
    for n in notes: print('  note:', n)
    print(f'Fliff credits: {tot} of {a.cap} used today.' + ('' if a.dry_run else f'  Log: {LOG}'))

if __name__ == '__main__': main()
