"""Spot-check stored shots (data/s*.pkl, NHL stats API) against ESPN box scores (independent source). Free.
ESPN summary label 'S' = shots on goal (verified vs NHL rows). Matches players by normalized last name + team.
Usage: .venv/bin/python audit/espn_spotcheck.py -> audit/espn_spotcheck.csv"""
import requests, pandas as pd, glob, re, unicodedata, random, os
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
norm = lambda x: re.sub(r'[^a-z]', '', unicodedata.normalize('NFKD', x).encode('ascii', 'ignore').decode().lower())
ESPN2NHL = {'NJ': 'NJD', 'TB': 'TBL', 'LA': 'LAK', 'SJ': 'SJS', 'UTAH': 'UTA', 'WSH': 'WSH', 'MON': 'MTL', 'NAS': 'NSH'}
df = pd.concat([pd.read_pickle(f) for f in sorted(glob.glob(f'{ROOT}/data/s*.pkl'))])
DATES = ['20260929', '20261012', '20261013', '20261014', '20261015', '20261016', '20251218', '20230326', '20220429']
random.seed(17); out = []
for d in DATES:
    iso = f'{d[:4]}-{d[4:6]}-{d[6:]}'; ev = requests.get(f'https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard?dates={d}', timeout=30).json()['events']
    for e in random.sample(ev, min(2, len(ev))):
        b = requests.get(f'https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/summary?event={e["id"]}', timeout=30).json()
        for tp in b['boxscore']['players']:
            ab = ESPN2NHL.get(tp['team']['abbreviation'], tp['team']['abbreviation'])
            ours = df[(df.gameDate == iso) & (df.teamAbbrev == ab)]
            for st in tp['statistics']:
                if st.get('name') not in ('forwards', 'defenses'): continue
                i = st['labels'].index('S')
                for a in random.sample(st['athletes'], min(2, len(st['athletes']))):
                    nm = a['athlete']['displayName']; m = ours[ours.skaterFullName.map(norm) == norm(nm)]
                    out.append(dict(date=iso, espn_event=e['id'], game=e['shortName'], team=ab, player=nm, espn_sog=int(a['stats'][i]) if a['stats'] else None,
                                    nhl_sog=int(m.shots.iloc[0]) if len(m) else None, gameId=int(m.gameId.iloc[0]) if len(m) else None))
o = pd.DataFrame(out); o['match'] = o.espn_sog == o.nhl_sog; o.to_csv(f'{HERE}/espn_spotcheck.csv', index=False)
print(len(o), 'rows;', int(o.match.sum()), 'match;', int(o.nhl_sog.isna().sum()), 'name not found'); print(o[~o.match].to_string())
