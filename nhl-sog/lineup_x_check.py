#!/usr/bin/env python3
"""PAPER ONLY. X line-rush lineup shadow check (Tester2, 2026-11-03).

usage:
  lineup_x_check.py YYYYMMDD HHMM --queries   # print one X search per team (JSON)
  lineup_x_check.py YYYYMMDD HHMM             # parse cached results -> shadow/xlineup/<date>_<HHMM>.csv

The X API is reached through the agent's `x` MCP namespace (search_posts_all),
which Python can't call directly. The agent runs each printed query once and
saves the raw JSON response to shadow/xlineup/raw/<date>_<HHMM>/<slug>.json.
One search per team per pass; the MCP footer reports the limit (30/min, 1000/day).
Never touches picks/, sheets/, build_sheet.py, shop_gate.py or the model.
"""
import sys, os, re, json, csv, unicodedata
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import pandas as pd

PT = ZoneInfo('America/Los_Angeles')
HERE = os.path.dirname(os.path.abspath(__file__))
NICK = {}  # 'Winnipeg Jets' -> 'Jets'
def nick(team):
    return NICK.get(team) or (' '.join(team.split()[-2:]) if team.split()[-1] in ('Wings','Jackets','Leafs','Knights') else team.split()[-1])
def slug(team): return re.sub(r'[^a-z]+', '_', team.lower()).strip('_')
# aggregators that mostly copy DailyFaceoff / betting spam -> lower priority
AGG = {'dailyfaceoff','32hockeyupdates','hockeyinformhq','bet_105','lilbitgame'}

def norm(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii','ignore').decode().lower().replace('-', ' ')
    return re.sub(r'[^a-z ]', '', s).strip()

def query(team, date, hhmm):
    n = nick(team)
    start = datetime.strptime(date, '%Y%m%d').replace(tzinfo=PT).astimezone(timezone.utc)
    end = datetime.strptime(date+hhmm, '%Y%m%d%H%M').replace(tzinfo=PT).astimezone(timezone.utc)
    end = min(end, datetime.now(timezone.utc) - timedelta(seconds=30))
    return dict(query=f'("{n}" OR "{team}") ("line rushes" OR rushes OR "projected lines" OR lines) -is:retweet',
                start_time=start.strftime('%Y-%m-%dT%H:%M:%SZ'), end_time=end.strftime('%Y-%m-%dT%H:%M:%SZ'),
                max_results=25, sort_order='relevancy', expansions='author_id',
                **{'user.fields':'username,name', 'post.fields':'created_at,author_id,note_tweet'})

SEP = re.compile(r'\s+[-–—]\s*|\s*[-–—]\s+')
def parse_post(text):
    """-> dict with ev {name: f1..f4/d1..d3}, pp {name: pp1/pp2}, scratched set, team_hint lines.
    Lines parse only from 'A - B - C' text rows (3 fwd = forward line, 2 = D pair).
    Image-only posts (most beat writers) parse to nothing."""
    ev, pp, scr = {}, {}, set()
    f = d = 0; ppn = 0; block = None  # block: 'F' forward block, 'D' after it, 'PP'
    for raw in text.split('\n'):
        line = raw.strip(); lo = line.lower()
        if not line:
            if block == 'F' and f >= 3: block = 'D'
            elif block == 'D' and d: block = 'done'
            continue
        if re.match(r'^(pp|power ?play)\s*#?\s*\d?', lo):
            m = re.search(r'([12])', lo); ppn = int(m.group(1)) if m else ppn + 1; block = 'PP'
            rest = line.split(':', 1)[1] if ':' in line else ''
            for x in re.split(r'[,]|\s+[-–—]\s*|\s*[-–—]\s+', rest):
                if norm(x): pp[norm(x)] = f'pp{min(ppn,2)}'
            continue
        if re.match(r'^(healthy )?scratch', lo):
            for x in re.split(r'[,;/]| and ', line.split(':', 1)[-1]):
                if norm(x): scr.add(norm(x))
            continue
        parts = [p for p in SEP.split(line) if p.strip()]
        if block == 'D' and len(parts) == 1 and len(line) <= 30 and d:
            ev[norm(line)] = 'extra'; continue  # 7th D / extra skater
        if len(parts) < 2 or any(len(p) > 30 for p in parts): continue
        if block == 'PP':
            for p in parts: pp[norm(p)] = f'pp{min(ppn,2)}'
            continue
        if block in (None, 'F') and len(parts) >= 2 and f < 4 and (len(parts) == 3 or block == 'F'):
            block = 'F'; f += 1
            for p in parts: ev[norm(p)] = f'f{f}'
        elif block == 'D' and len(parts) == 2 and d < 3:
            d += 1
            for p in parts: ev[norm(p)] = f'd{d}'
    return ev, pp, scr

def lookup(m, player):
    n = norm(player); last = n.split()[-1] if n else ''
    if n in m: return m[n]
    first = n.split()[0][:1] if n else ''
    ini = [v for k, v in m.items() if len(k.split()) == 2 and len(k.split()[0]) == 1 and k.split()[0] == first and k.split()[1] == last]
    if ini: return ini[0]
    hits = [v for k, v in m.items() if k.split() and k.split()[-1] == last]
    hits += [v for k, v in m.items() if k == last]
    return hits[0] if len(set(hits)) == 1 and hits else None

def best_post(resp, team):
    users = {u['id']: u['username'] for u in resp.get('includes', {}).get('users', [])}
    n = nick(team).lower(); best = None
    for p in resp.get('data', []) or []:
        text = (p.get('note_tweet') or {}).get('text') or p['text']
        head = '\n'.join(text.split('\n')[:2]).lower()
        if n not in head and team.lower() not in head: continue
        ev, pp, scr = parse_post(text)
        nf = sum(1 for v in ev.values() if v.startswith('f'))
        if nf < 9: continue
        # the post must be about this team's lines, not the opponent's
        if not re.search(re.escape(n) + r"('?s)?\s+(projected\s+)?(lines|line rushes|rushes)", head) and 'line rushes' not in head:
            continue
        au = users.get(p['author_id'], '')
        score = (au.lower() not in AGG, p['created_at'])
        if best is None or score > best[0]:
            best = (score, dict(url=p.get('url',''), author=au, ev=ev, pp=pp, scr=scr, created=p['created_at']))
    return best[1] if best else None

def main():
    date, hhmm = sys.argv[1], sys.argv[2]
    gate = pd.read_csv(os.path.join(HERE, 'picks', f'{date}_D_{hhmm}_GATE.csv'))
    teams = sorted(gate.team_dfo.dropna().unique())
    raw = os.path.join(HERE, 'shadow', 'xlineup', 'raw', f'{date}_{hhmm}')
    if '--queries' in sys.argv:
        print(json.dumps({slug(t): query(t, date, hhmm) for t in teams}, indent=1)); return
    rows, summ = [], {}
    src = gate['lineup_source'] if 'lineup_source' in gate else pd.Series(['pre_fallback'] * len(gate))
    posts = {}
    for t in teams:
        fp = os.path.join(raw, slug(t) + '.json')
        resp = None
        if os.path.exists(fp):
            txt = open(fp).read(); resp, _ = json.JSONDecoder().raw_decode(txt[txt.find('{'):])
        posts[t] = best_post(resp, t) if resp else None
        summ[t] = 'usable' if posts[t] else ('no X post' if resp else 'not searched')
    for i, r in gate.iterrows():
        t = r.team_dfo
        if not isinstance(t, str): continue
        g_ev, g_pp = (r.ev_now if isinstance(r.ev_now, str) else ''), (r.pp_now if isinstance(r.pp_now, str) else '')
        p = posts.get(t)
        base = dict(player=r.player, team=t, lineup_source=src.iloc[i], gate_ev=g_ev, gate_pp=g_pp)
        if not p:
            rows.append({**base, 'x_ev':'', 'x_pp':'', 'x_url':'', 'post_time_pt':'', 'author':'', 'would_skip':'no', 'reason':summ[t]}); continue
        x_ev, x_pp = lookup(p['ev'], r.player) or '', lookup(p['pp'], r.player) or ''
        why = []
        if lookup({k:1 for k in p['scr']}, r.player): why.append('scratched on X')
        elif not x_ev: why.append('missing from X lines')
        elif x_ev == 'extra': why.append('extra/7th D on X (not in pairs)')
        elif g_ev and x_ev != g_ev: why.append(f'line {g_ev}->{x_ev}')
        if p['pp'] and g_pp != x_pp and (g_pp or x_pp): why.append(f'PP {g_pp or "none"}->{x_pp or "none"}')
        pt = datetime.fromisoformat(p['created'].replace('Z','+00:00')).astimezone(PT).strftime('%Y-%m-%d %H:%M PT')
        rows.append({**base, 'x_ev':x_ev, 'x_pp':x_pp if p['pp'] else 'n/a', 'x_url':p['url'], 'post_time_pt':pt, 'author':p['author'],
                     'would_skip':'yes' if why else 'no', 'reason':'; '.join(why) or 'agrees'})
    out = os.path.join(HERE, 'shadow', 'xlineup', f'{date}_{hhmm}.csv'); os.makedirs(os.path.dirname(out), exist_ok=True)
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f'{date} {hhmm}: {sum(v=="usable" for v in summ.values())}/{len(teams)} teams usable X post')
    for t, v in summ.items(): print(f'  {t}: {v}' + (f" ({posts[t]['author']} {posts[t]['url']})" if posts[t] else ''))
    ws = [x for x in rows if x['would_skip'] == 'yes']
    print(f'  would_skip rows: {len(ws)} -> {out}')
    for x in ws: print(f"   {x['team']}: {x['player']} gate {x['gate_ev']}/{x['gate_pp']} X {x['x_ev']}/{x['x_pp']} :: {x['reason']}")

if __name__ == '__main__': main()
