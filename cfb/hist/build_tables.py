"""Build empirical CFB landing tables from ESPN finals + ESPN core-API pregame lines (FBS scoreboard groups=80,
seasons 2019, 2021-2025; 2020 skipped as COVID-distorted). Output: landing_tables.json used by price_check.py.
spread[k]: P(favorite margin == k | closing |spread| within +/-3 of the line being converted), k=1..45, k=0 never (OT).
Stored per |spread| anchor 0.5..30 step 0.5.  total[k]: P(total points == k | closing total within +/-4 of anchor),
anchors 35..80 step 0.5. Kernel windows give >=150 games per anchor in the core range; counts stored."""
import pandas as pd, numpy as np, json
r = pd.read_csv('fbs_results.csv'); o = pd.read_csv('fbs_odds.csv')
d = r.merge(o, on='event_id'); d = d[d.provider.notna() & ~d.provider.isin(['ERR'])]
d['m'] = d.hs - d['as']; d['tp'] = d.hs + d['as']
s = d.dropna(subset=['home_spread']).copy(); s = s[s.home_spread != 0]
s['fs'] = s.home_spread.abs(); s['fm'] = np.where(s.home_spread < 0, s.m, -s.m)  # favorite margin
t = d.dropna(subset=['total']).copy()
out = {'sample': {'spread_games': int(len(s)), 'total_games': int(len(t)), 'seasons': sorted(map(int, d.season.unique())),
       'providers': d.provider.value_counts().to_dict()}, 'spread': {}, 'total': {}}
for a in np.arange(0.5, 30.01, 0.5):
    g = s[(s.fs - a).abs() <= 3]; n = len(g)
    out['spread'][f'{a:g}'] = {'n': n, 'p': {int(k): round(float((g.fm == k).mean()), 4) for k in range(-30, 60) if k != 0}}
for a in np.arange(35, 85.01, 0.5):
    g = t[(t.total - a).abs() <= 4]; n = len(g)
    out['total'][f'{a:g}'] = {'n': n, 'p': {int(k): round(float((g.tp == k).mean()), 4) for k in range(0, 140)}}
json.dump(out, open('landing_tables.json', 'w'))
print(out['sample'])
for a in ('2.5','3','6.5','7','10','14','21'):
    e = out['spread'][a]; print('spread', a, 'n', e['n'], {k: e['p'][k] for k in (3, 4, 6, 7, 10, 14, 17, 21)})
for a in ('45','52','58','65'):
    e = out['total'][a]; top = sorted(e['p'].items(), key=lambda x: -x[1])[:6]; print('total', a, 'n', e['n'], top)
# unconditional
print('fav margin landing overall', {k: round(float((s.fm == k).mean()), 4) for k in (1,2,3,4,6,7,8,10,14,17,21)})
print('total landing overall top', (t.tp.value_counts(normalize=True).head(10).round(4)).to_dict())
