"""Team game logs (goals for/against, shots for/against) for score-effect / strength features. Free NHL stats API.
-> challenger/team_games.pkl (one row per team-game; teamAbbrev = the other row's opponentTeamAbbrev)."""
import requests, pandas as pd, datetime as dt, os
B = 'https://api.nhle.com/stats/rest/en/team/summary'
rows = []
for s in range(2021, 2027):
    e = f'seasonId={s}{s+1} and gameTypeId=2'
    if s == 2026: e += f' and gameDate<"{dt.date.today().isoformat()}"'
    d, start = [], 0
    while True:  # API caps at 100 rows per call (Nov 19, 2026); page until total
        j = requests.get(B, params={'isAggregate': 'false', 'isGame': 'true', 'start': start, 'limit': 100,
                                    'sort': '[{"property":"gameId","direction":"ASC"},{"property":"teamId","direction":"ASC"}]',
                                    'cayenneExp': e}, timeout=90).json()
        d += j['data']; start += 100
        if not j['data'] or start >= j.get('total', 0): break
    for r in d: r['season'] = s
    rows += d; print(s, len(d), flush=True)
df = pd.DataFrame(rows)[['gameId', 'gameDate', 'season', 'homeRoad', 'opponentTeamAbbrev', 'goalsFor', 'goalsAgainst', 'shotsForPerGame', 'shotsAgainstPerGame']]
other = df[['gameId', 'opponentTeamAbbrev', 'homeRoad']].copy()
df = df.merge(other.rename(columns={'opponentTeamAbbrev': 'teamAbbrev', 'homeRoad': 'hr2'}), on='gameId')
df = df[df.hr2 != df.homeRoad].drop(columns='hr2').drop_duplicates(['gameId', 'teamAbbrev'])
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'team_games.pkl')
if len(df) < 5000: raise SystemExit(f'refusing to overwrite team_games.pkl: only {len(df)} rows (truncated fetch?)')
df.to_pickle(out)
print(len(df), df.gameDate.min(), df.gameDate.max())
