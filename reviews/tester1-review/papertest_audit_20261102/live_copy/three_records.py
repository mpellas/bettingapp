"""Nightly grader for the three NHL records (Tester2, item 6, added 2026-10-26).
(a) as posted: every 'Fliff check' side in picks/<date>[_HHMM]_post.txt (includes 20261017_post.txt, which list_track's glob skips)
(b) final card after tester skips, (c) skipped sides. Every side is in exactly one of (b)/(c), from card_decisions.csv
    (default = card; FINAL CALL cards live in chat, so new skips must be appended to card_decisions.csv each night).
Shots: fresh from api-web.nhle.com (score/<date> -> boxscore). Units: flat 1u at the DK list price. Paper only; read-only on models.
Usage: .venv/bin/python three_records.py [YYYYMMDD ...]   (default: all dates with post files)
Writes graded/three_records_sides.csv and graded/three_records.md; prints the md."""
import re, glob, os, sys, json, urllib.request, fnmatch
import pandas as pd
os.chdir(os.path.dirname(os.path.abspath(__file__)))
PAT = re.compile(r'^Fliff check: (.+?) (OVER|UNDER) ([\d.]+) \(DK ([+-]?\d+), Fliff at ([+-]?\d+) or better\)')
FLOOR_FROM = '20261020_1513'
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'}), timeout=20) as r: return json.load(r)
_box = {}
def shots(date, name):
    d = f'{date[:4]}-{date[4:6]}-{date[6:]}'
    if d not in _box:
        P = {}
        for g in get(f'https://api-web.nhle.com/v1/score/{d}').get('games', []):
            b = get(f'https://api-web.nhle.com/v1/gamecenter/{g["id"]}/boxscore')
            fin = b.get('gameState') in ('OFF', 'FINAL')
            for t in ('awayTeam', 'homeTeam'):
                for grp in ('forwards', 'defense'):
                    for p in b.get('playerByGameStats', {}).get(t, {}).get(grp, []):
                        P[p['name']['default'] + '#' + str(p['playerId'])] = (p.get('sog'), fin, g['id'])
        _box[d] = P
    P = _box[d]; parts = name.split(); key = f'{parts[0][0]}. {" ".join(parts[1:])}'
    gp = f'graded/{date}.csv'; nid = None
    if os.path.exists(gp):
        G = pd.read_csv(gp); x = G[G.player == name].nhl_id.dropna()
        if len(x): nid = str(int(x.iloc[0]))
    hits = [v for k, v in P.items() if nid and k.endswith('#' + nid)] or [v for k, v in P.items() if k.split('#')[0] == key]
    if not nid and len(hits) > 1: print(f'WARN ambiguous name {name} {date}', file=sys.stderr)
    return hits[0] if hits else (None, False, None)
def dec(a): return 1 + (a / 100 if a > 0 else 100 / -a)
def posts(dates):
    fs = sorted(glob.glob('picks/2026????_post.txt') + glob.glob('picks/2026????_????_post.txt'))
    return [f for f in fs if os.path.basename(f)[:8] in dates] if dates else fs
def build(dates):
    C = pd.read_csv('card_decisions.csv')
    R = []
    for pf in posts(dates):
        b = os.path.basename(pf); date = b[:8]; lst = b[:13] if b[8] == '_' and b[9:13].isdigit() else date + '_post'
        for ln in open(pf):
            m = PAT.match(ln)
            if not m: continue
            pl, side, line, dk = m.group(1), m.group(2), float(m.group(3)), int(m.group(4))
            c = C[[fnmatch.fnmatch(lst, l) and fnmatch.fnmatch(pl, p) and fnmatch.fnmatch(side, s) for l, p, s in zip(C.list, C.player, C.side)]]
            # 2026-10-31 (Tester2): (b) counts only sides with an actual card play decision. A list counts only if
            # card_decisions.csv has a row for it; list-level NO BETS (blank/ALL/'NO BETS' player) excludes the whole list.
            LR = C[[fnmatch.fnmatch(lst, l) for l in C.list]]
            list_nb = LR.player.isna() | LR.player.isin(['ALL', 'NO BETS'])
            d0 = c.decision.iloc[0] if len(c) else None
            if d0 == 'skip': bucket = 'skipped'
            elif len(LR) == 0: bucket = 'no_decision'
            elif list_nb.any() or d0 == 'no_bets': bucket = 'no_bets'
            elif isinstance(d0, str) and d0.startswith('hold'): bucket = 'card'  # 2026-10-31 room: explicit cleared hold row (e.g. hold_prizepicks) = card play
            elif os.path.exists(f'picks/finalcall_done/{lst}.txt') or d0 == 'card': bucket = 'card'
            else: bucket = 'no_marker'  # 2026-10-31 room rule: official card needs a finalcall_done marker or an explicit card row
            sog, fin, gid = shots(date, pl)
            hit = None if sog is None or not fin else int(sog > line if side == 'OVER' else sog < line)
            R.append(dict(list=lst, date=date, era='post-floor' if lst >= FLOOR_FROM else 'pre-floor', player=pl, side=side, line=line, dk=dk,
                          shop_at=int(m.group(5)), bucket=bucket, decision_src=c.source.iloc[0] if len(c) else ('default card (no skip found)' if bucket == 'card' else (f"card_decisions.csv {lst} NO BETS row" + (f" ({LR[list_nb].source.iloc[0]})" if isinstance(LR[list_nb].source.iloc[0], str) else '') if list_nb.any() else 'no side row')),
                          gameId=gid, actual=sog, hit=hit, u_dk=None if hit is None else (dec(dk) - 1 if hit else -1.0),
                          u_shop=None if hit is None else (dec(int(m.group(5))) - 1 if hit else -1.0)))
    return pd.DataFrame(R)
def md(R):
    def s(lbl, r):
        g = r.dropna(subset=['hit']); w = int(g.hit.sum())
        return f'| {lbl} | {len(r)} | {w}-{len(g) - w} | {g.u_dk.sum():+.2f} |'
    L = ['| record | sides | W-L | units @ DK |', '|---|---|---|---|', s('(a) as posted', R), s('(b) final card (i) official (marker or card row)', R[R.bucket == 'card']), s('(b) final card (ii) + no_decision/no_marker lists', R[R.bucket.isin(['card', 'no_decision', 'no_marker'])]), s('(c) skipped sides', R[R.bucket == 'skipped'])]
    L += ['', 'Not on a final card (in (a) only): ' + ', '.join(f'{k} {v}' for k, v in R.bucket.value_counts().items() if k not in ('card', 'skipped')) + '. (b) = card play decisions only (2026-10-31).']
    L += ['', '| date | (a) | (b) card | (c) skipped |', '|---|---|---|---|']
    for d, r in R.groupby('date'):
        f = lambda x: (lambda g: f'{len(x)} {int(g.hit.sum())}-{len(g)-int(g.hit.sum())} {g.u_dk.sum():+.2f}')(x.dropna(subset=['hit']))
        L.append(f'| {d} | {f(r)} | {f(r[r.bucket=="card"])} | {f(r[r.bucket=="skipped"])} |')
    for e in ('pre-floor', 'post-floor'):
        r = R[R.era == e]; L.append(f'| **{e}** | {s("", r).split("|",2)[2][:-2]} | {s("", r[r.bucket=="card"]).split("|",2)[2][:-2]} | {s("", r[r.bucket=="skipped"]).split("|",2)[2][:-2]} |')
    return '\n'.join(L)
if __name__ == '__main__':
    R = build(sys.argv[1:])
    assert not R.duplicated(['list', 'player', 'side', 'line']).any()
    R.to_csv('graded/three_records_sides.csv', index=False); out = md(R); open('graded/three_records.md', 'w').write(out + '\n'); print(out)
