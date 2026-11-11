"""Apply data/stat_overrides.csv (gameId,playerId,field,old,new,...) to a game-log DataFrame. Called by fetch.py so re-fetches keep official-boxscore corrections.
Only applies where the current value equals `old` (or already `new`); a different value is reported, not overwritten."""
import os, pandas as pd
def apply(df, path='data/stat_overrides.csv'):
    if not os.path.exists(path): return df
    for r in pd.read_csv(path).itertuples():
        m = (df.gameId == r.gameId) & (df.playerId == r.playerId)
        if not m.any(): continue
        cur = df.loc[m, r.field].iloc[0]
        if cur == r.new: continue
        if cur != r.old: print(f'override skipped {r.gameId}/{r.playerId}.{r.field}: have {cur}, expected {r.old}'); continue
        df.loc[m, r.field] = r.new; print(f'override applied {r.gameId}/{r.playerId}.{r.field}: {r.old}->{r.new}')
    return df
if __name__ == '__main__':
    import sys; f = sys.argv[1] if len(sys.argv) > 1 else 'data/s2026.pkl'
    apply(pd.read_pickle(f)).to_pickle(f)
