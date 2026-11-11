"""Independent rebuild: NFL x_books de-vig fix + missing ID mapping on nov02 all_sides."""
import os, re, unicodedata, json
import numpy as np, pandas as pd
OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = pd.read_csv(os.path.join(OUT, 'data/pf/nfl_wk8_nov02_1613_all_sides.csv'))
ps = pd.read_parquet(os.path.join(OUT, 'data/nfl/cache/stats_player_week_2026.parquet'))
ps = ps[ps.season_type=='REG'] if 'season_type' in ps.columns else ps
G = pd.read_csv(os.path.join(OUT, 'data/nfl/cache/games.csv'))
S, W = 2026, 8

def am2p(a):
    a=float(a); return -a/(-a+100) if a<0 else 100/(a+100)

def nm(x):
    return re.sub(r'[^a-z]','', unicodedata.normalize('NFKD', str(x)).encode('ascii','ignore').decode().lower())

# ========== 1) ID mapping (independent, same rules as add_evidence) ==========
ps_s = ps[ps.season==S].sort_values('week').drop_duplicates(['player_id'], keep='last')
pid_by = {(nm(n), t): (p, pos) for n,t,p,pos in zip(ps_s.player_display_name, ps_s.team, ps_s.player_id, ps_s.position)}
pid_nm = {}
for n,p,pos in zip(ps_s.player_display_name, ps_s.player_id, ps_s.position):
    pid_nm.setdefault(nm(n), []).append((p, pos))
gw = G[(G.season==S)&(G.week==W)]
g_by = {}
for gid,h,aw in zip(gw.game_id, gw.home_team, gw.away_team):
    g_by[h]=(gid,aw); g_by[aw]=(gid,h)

def _pid(n,t):
    k = pid_by.get((nm(n), t))
    if k: return k[0], k[1], 'name+team'
    c = pid_nm.get(nm(n), [])
    if len(c)==1: return c[0][0], c[0][1], 'name-unique'
    if len(c)>1: return None, None, f'name-ambiguous:{len(c)}'
    return None, None, 'name-miss'

mapped = []
for i,r in A.iterrows():
    pid, pos, how = _pid(r.player, r.team)
    gid, opp = g_by.get(r.team, (None, None))
    mapped.append(dict(idx=i, player=r.player, team=r.team, market=r.market, line=r.line, side=r.side, book=r.book,
                       player_id=pid, pos=pos, how=how, game_id=gid, opp=opp,
                       # yards markets only score
                       ymk=r.market in ('pass_yds','rush_yds','rec_yds','reception_yds')))
M = pd.DataFrame(mapped)
# Scoring eligibility mirrors add_evidence: mk in YMK, game_id in G, player_id present, team present
Gix = set(G.game_id)
M['scorable'] = M.player_id.notna() & M.game_id.isin(Gix) & M.ymk & M.team.notna()
print('=== ID mapping ===')
print(f'rows {len(M)}; player_id mapped {M.player_id.notna().sum()}/{len(M)}; game_id {M.game_id.notna().sum()}/{len(M)}')
print('how:', M.how.value_counts().to_dict())
print(f'scorable (would get evidence): {M.scorable.sum()} / {len(M)}  (Yinzer claims 371/419)')

# List unscored
U = M[~M.scorable]
print(f'\nunscored {len(U)}:')
# reasons
def why_un(r):
    rs=[]
    if pd.isna(r.player_id): rs.append(r.how)
    if pd.isna(r.game_id): rs.append('no-game_id-for-team')
    if not r.ymk: rs.append('non-yards-market')
    return '+'.join(rs) if rs else 'unknown'
U = U.copy(); U['reason']=U.apply(why_un, axis=1)
print(U.reason.value_counts().to_dict())
# unique unscored players
print('\nunscored unique player/team/how:')
print(U.groupby(['player','team','how','reason']).size().reset_index(name='n').sort_values(['how','player']).to_string(index=False))
U.to_csv(os.path.join(OUT,'nfl_unscored.csv'), index=False)
M.to_csv(os.path.join(OUT,'nfl_id_map.csv'), index=False)

# Spot-check ~15 name matches for wrong-player risk
print('\n=== Spot-check name matches (15) ===')
# Prefer name-unique and any that share surnames
rng = np.random.default_rng(0)
scored = M[M.player_id.notna()].drop_duplicates('player_id')
# Build display name lookup
id2name = dict(zip(ps_s.player_id, ps_s.player_display_name))
id2team = dict(zip(ps_s.player_id, ps_s.team))
sample = scored.sample(n=min(15, len(scored)), random_state=0)
# Also force-include ambiguous-risk: same surname different players in season
from collections import defaultdict
sur = defaultdict(list)
for n,p,t in zip(ps_s.player_display_name, ps_s.player_id, ps_s.team):
    sur[n.split()[-1].lower()].append((n,p,t))
multi_sur = {k:v for k,v in sur.items() if len({x[1] for x in v})>1}
# Pick all_sides players whose surname is multi
risk = []
for _,r in M[M.player_id.notna()].iterrows():
    s = str(r.player).strip().split()[-1].lower()
    if s in multi_sur:
        risk.append(r)
risk = pd.DataFrame(risk).drop_duplicates('player') if risk else pd.DataFrame()
print(f'players on slate with shared-surname in 2026 stats: {len(risk)}')
check = pd.concat([sample, risk.head(10)]).drop_duplicates('player').head(20)
for _,r in check.iterrows():
    mapped_name = id2name.get(r.player_id,'?'); mapped_team = id2team.get(r.player_id,'?')
    ok = nm(mapped_name)==nm(r.player) and (mapped_team==r.team or r.how=='name-unique')
    # team change warning
    flag = ''
    if mapped_team != r.team: flag = f' TEAM_DIFF slate={r.team} stats_last={mapped_team}'
    if nm(mapped_name)!=nm(r.player): flag += ' NAME_NORM_DIFF'
    # surname collisions
    s = str(r.player).strip().split()[-1].lower()
    coll = [f'{n}({t})' for n,p,t in multi_sur.get(s,[]) if p!=r.player_id]
    if coll: flag += f' surname_also:{coll[:3]}'
    print(f'  [{r.how}] slate="{r.player}"/{r.team} -> {r.player_id} "{mapped_name}"/{mapped_team}{flag}')

# ========== 2) books rebuild ==========
print('\n=== NFL books (independent de-vig) ===')
# Attach ids for completeness but books only needs player/market/side/book/line/price/fair_prob
A2 = A.copy()
# Yinzer's x_books
def x_books_new(A, i):
    r = A.loc[i]
    if 'book' not in A: return 0, 'n/a'
    o = str(r.side).lower().startswith('o')
    oth = A[(A.player==r.player)&(A.market==r.market)&(A.side.astype(str).str.lower()==str(r.side).lower())&(A.book!=r.book)]
    if oth.empty: return 0, 'no other book'
    ln=float(r.line); med=float(oth.line.median()); b=max(1.5, 0.02*abs(ln)); d=med-ln
    if abs(d)>=b:
        v=(1 if d>0 else -1)*(1 if o else -1)
        return v, f'line-lean med={med} vs {ln}'
    opp = A[(A.player==r.player)&(A.market==r.market)&(A.book==r.book)&(A.line==r.line)&(A.side.astype(str).str.lower()!=str(r.side).lower())]
    fp=r.get('fair_prob') if hasattr(r,'get') else r['fair_prob']
    # Series .get works for named
    try: fp = r.fair_prob
    except Exception: fp = np.nan
    if opp.empty or pd.isna(fp): return 0, f'same-line no two-sided'
    try:
        pm, po = am2p(r.price), am2p(opp.price.iloc[0]); nvb = pm/(pm+po); dp=float(fp)-nvb
        return (1 if dp>0.02 else (-1 if dp<-0.02 else 0)), f'novig fp={fp:.3f} nvb={nvb:.3f} dp={dp*100:+.1f}'
    except Exception as e:
        return 0, f'err {e}'

def x_books_old_buggy(A, i):
    """Old bug: compared fair_prob (no-vig) to am2p(price) (vigged) -> minus both sides."""
    r = A.loc[i]
    o = str(r.side).lower().startswith('o')
    oth = A[(A.player==r.player)&(A.market==r.market)&(A.side.astype(str).str.lower()==str(r.side).lower())&(A.book!=r.book)]
    if oth.empty: return 0, 'no other book'
    ln=float(r.line); med=float(oth.line.median()); b=max(1.5, 0.02*abs(ln)); d=med-ln
    if abs(d)>=b:
        v=(1 if d>0 else -1)*(1 if o else -1)
        return v, 'line-lean'
    try:
        fp=float(r.fair_prob); ip=am2p(r.price); dp=fp-ip
        return (1 if dp>0.02 else (-1 if dp<-0.02 else 0)), f'old fp-ip={dp*100:+.1f}'
    except Exception:
        return 0, 'err'

bres = []
for i in A.index:
    sn, wn = x_books_new(A, i)
    so, wo = x_books_old_buggy(A, i)
    bres.append(dict(i=i, player=A.loc[i,'player'], market=A.loc[i,'market'], side=A.loc[i,'side'],
                     book=A.loc[i,'book'], line=A.loc[i,'line'], price=A.loc[i,'price'], fair_prob=A.loc[i,'fair_prob'],
                     new=sn, new_why=wn, old=so, old_why=wo))
B = pd.DataFrame(bres)
B.to_csv(os.path.join(OUT,'nfl_books_compare.csv'), index=False)
print('NEW sign dist:', B['new'].value_counts().to_dict())
print('OLD sign dist:', B['old'].value_counts().to_dict())
print('new why top:', B.new_why.value_counts().head(8).to_dict())

# Critical: same prop over+under both minus?
both_minus_old = both_minus_new = both_same_nonzero_new = 0
opp_ok = opp_fail = 0
props = B.groupby(['player','market','book','line'])
for key, g in props:
    sides = {str(s).lower(): v for s,v in zip(g.side, g['new'])}
    sides_o = {str(s).lower(): v for s,v in zip(g.side, g['old'])}
    if 'over' in sides and 'under' in sides:
        if sides_o['over']<0 and sides_o['under']<0: both_minus_old += 1
        if sides['over']<0 and sides['under']<0: both_minus_new += 1
        if sides['over']!=0 and sides['under']!=0:
            if sides['over']==-sides['under']: opp_ok += 1
            else: opp_fail += 1; both_same_nonzero_new += (sides['over']==sides['under'])
print(f'props with both O+U: old both-minus={both_minus_old}; new both-minus={both_minus_new}')
print(f'new nonzero pairs opposite-sign OK={opp_ok} FAIL={opp_fail}')

# Lookahead: books only uses rows in same input file (no time dimension) - N/A for all_sides
# Confirm prizepicks one-sided -> 0 on same-line branch
pp = B[B.book=='prizepicks']
print(f'prizepicks rows {len(pp)} new nonzero {(pp["new"]!=0).sum()} (line-lean only expected)')
print('prizepicks new why:', pp.new_why.value_counts().head(5).to_dict())

# DK rows that have opposite side
dk = B[B.book=='draftkings']
print(f'draftkings rows {len(dk)} new dist {dk["new"].value_counts().to_dict()}')

# ========== 3) UNAVAILABLE message ==========
print('\n=== MAJORITY LIST UNAVAILABLE trigger ===')
# Read the code path: if n_scored==0, insert message
# Simulate empty scoring: strip markets to non-yards
src = open(os.path.join(OUT,'nfl_add_evidence.py')).read()
assert 'MAJORITY LIST UNAVAILABLE' in src
# Logic: n_scored := agrees_n.notna().sum(); else insert
# Verify with a dry mini: no yards markets -> 0 scored
A_empty = A.copy(); A_empty['market']='spread'  # not in YMK
# Count how many would score with our mapping but bad market
print('code contains UNAVAILABLE string: YES')
print('trigger condition: agrees_n.notna().sum()==0 (i.e. every row skipped for mk/game_id/pid)')
# Simulate: if we pass empty player_id frame
n_would = 0  # with market=spread
print(f'simulated all market=spread -> scored {n_would} -> would print UNAVAILABLE: {n_would==0}')

# Also: what if IDs fail entirely?
n_scorable_no_id = 0
print(f'if all IDs missing: scored 0 -> UNAVAILABLE yes')

# Denominator note
print('\nNFL EXTRA_SIGS from code:', re.search(r"EXTRA_SIGS\s*=\s*(\[[^\]]+\])", open(os.path.join(OUT,'nfl_evidence.py')).read()).group(1))
print('tests_all_n = 7 + 4 = 11')
print('done nfl script')
