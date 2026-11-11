import os, glob
import pandas as pd
NHL = '/workspace/nhl-sog'
def yinzer_logs():   # same as nhl-sog shrink.gamelogs(), read only
    hist = [pd.read_pickle(f) for f in sorted(glob.glob(f'{NHL}/data/s202[1-5].pkl'))]
    cands = [pd.read_pickle(f) for f in (f'{NHL}/shadow/s2026_live.pkl', f'{NHL}/data/s2026.pkl') if os.path.exists(f)]
    parts = hist + [max(cands, key=lambda c: (c.gameDate.max(), len(c)))]
    df = pd.concat([p[['playerId', 'gameId', 'gameDate', 'shots', 'timeOnIcePerGame', 'positionCode']] for p in parts])
    df = df.drop_duplicates(['playerId', 'gameId']).sort_values(['gameDate', 'gameId']); df['hrs'] = df.timeOnIcePerGame / 3600.0
    return df
