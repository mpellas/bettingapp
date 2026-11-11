"""Paper-only 'att' (shot-attempts) evidence signal. Definition: see README.md (fixed before results).
Usage:
  python3 att_signal.py <sheet.xlsx | GATE.csv> [--date YYYYMMDD] [--out out/xxx.csv]
A GATE csv is paired with sheets/<same stem>_picks.xlsx for agrees_n when it exists (agrees_n is copied, never recomputed).
Reads /workspace/nhl-sog by absolute path only; writes only under this folder."""
import sys, os, re, glob, argparse, unicodedata
import numpy as np, pandas as pd
NHL = '/workspace/nhl-sog'
HERE = os.path.dirname(os.path.abspath(__file__))
N_RECENT, N_BASE, MIN_BASE, MIN_ATT, BAND = 10, 82, 30, 15, 0.10

def load_logs():
    fs = sorted(glob.glob(f'{NHL}/data/s20*.pkl'))
    df = pd.concat([pd.read_pickle(f) for f in fs]).drop_duplicates(['playerId', 'gameId'])
    df = df[df.timeOnIcePerGame.fillna(0) > 0].copy()
    df['hrs'] = df.timeOnIcePerGame / 3600.0
    df['att'] = df.totalShotAttempts.astype(float)
    return df.sort_values(['playerId', 'gameDate', 'gameId']).reset_index(drop=True)

def _sgn(x):
    if x is None or not np.isfinite(x): return 0
    return 1 if x >= BAND else (-1 if x <= -BAND else 0)

def compute(sog_r, att_r, hrs_r, sog_b, att_b, hrs_b, n_r, n_b):
    """Pooled sums for RECENT (r) and BASE (b) windows -> dict of numbers + over-side vote."""
    d = dict(n_recent=n_r, n_base=n_b, att_r10=att_r)
    ok = n_r >= N_RECENT and n_b >= MIN_BASE and att_r >= MIN_ATT and hrs_r > 0 and hrs_b > 0 and att_b > 0
    with np.errstate(divide='ignore', invalid='ignore'):
        d['att60_r10'] = att_r / hrs_r if hrs_r > 0 else np.nan
        d['att60_base'] = att_b / hrs_b if hrs_b > 0 else np.nan
        d['acc_r10'] = sog_r / att_r if att_r > 0 else np.nan
        d['acc_base'] = sog_b / att_b if att_b > 0 else np.nan
        d['sog60_r10'] = sog_r / hrs_r if hrs_r > 0 else np.nan
        d['sog60_base'] = sog_b / hrs_b if hrs_b > 0 else np.nan
        d['a_vol'] = d['att60_r10'] / d['att60_base'] - 1
        d['b_acc'] = (d['acc_base'] / d['acc_r10'] - 1) if (d['acc_r10'] or 0) > 0 else np.nan
        d['proj_sog60'] = d['att60_r10'] * d['acc_base']
    if not ok:
        d['att_over'] = 0; d['att_why'] = 'n/a (min games/attempts not met)'; return d
    va, vb = _sgn(d['a_vol']), _sgn(d['b_acc'])
    d['att_over'] = int(np.sign(va + vb))
    d['att_why'] = (f"att/60 last10 {d['att60_r10']:.1f} vs base {d['att60_base']:.1f} ({d['a_vol']*100:+.0f}%); "
                    f"SOG/att last10 {d['acc_r10']:.2f} vs base {d['acc_base']:.2f} (regression {d['b_acc']*100:+.0f}%)")
    return d

def features_for(logs_by_pid, pid, date_iso):
    g = logs_by_pid.get(int(pid))
    if g is None: return compute(0, 0, 0, 0, 0, 0, 0, 0)
    g = g[g.gameDate < date_iso]
    r = g.iloc[-N_RECENT:]; b = g.iloc[-(N_RECENT + N_BASE):-N_RECENT] if len(g) > N_RECENT else g.iloc[0:0]
    return compute(r.shots.sum(), r.att.sum(), r.hrs.sum(), b.shots.sum(), b.att.sum(), b.hrs.sum(), len(r), len(b))

def vectorized(logs):
    """Same features for every player-game row (as-of before that game). Used for the 2025-26 proxy."""
    g = logs.groupby('playerId', sort=False)
    out = logs.copy()
    for c in ['shots', 'att', 'hrs']:
        s = g[c].shift(1)
        r = s.groupby(logs.playerId).rolling(N_RECENT, min_periods=1).sum().reset_index(level=0, drop=True)
        t = s.groupby(logs.playerId).rolling(N_RECENT + N_BASE, min_periods=1).sum().reset_index(level=0, drop=True)
        out[f'{c}_R'] = r; out[f'{c}_B'] = t - r
    k = g.cumcount()
    out['n_R'] = k.clip(upper=N_RECENT); out['n_B'] = (k - N_RECENT).clip(lower=0, upper=N_BASE)
    return out

def _norm(s):
    return re.sub(r'[^a-z]', '', unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().lower())

def load_pass(path):
    """Returns (sides df with player, side, line, game, agrees_n, nhl_id, ...), date."""
    base = os.path.basename(path); date = re.match(r'(\d{8})', base).group(1)
    sheet, gate = None, None
    if path.endswith('.xlsx'):
        sheet = path; stem = base.replace('_picks.xlsx', '')
        gp = f'{NHL}/picks/{stem}_GATE.csv'; gate = gp if os.path.exists(gp) else None
    else:
        gate = path; stem = base.replace('_GATE.csv', '')
        sp = f'{NHL}/sheets/{stem}_picks.xlsx'; sheet = sp if os.path.exists(sp) else None
    G = pd.read_csv(gate) if gate else None
    if sheet:
        S = pd.read_excel(sheet, sheet_name='Picks')
        S['side'] = S.side.astype(str).str.lower()
        S = S[S.side.isin(['over', 'under'])].copy()
    else:
        S = pd.concat([G.assign(side='over', dk_price=G.over), G.assign(side='under', dk_price=G.under)])
        S['agrees_n'] = np.nan
    if 'nhl_id' not in S and G is not None:
        m = {(_norm(p), float(l)): int(i) for p, l, i in zip(G.player, G.line, G.nhl_id)}
        S['nhl_id'] = [m.get((_norm(p), float(l))) for p, l in zip(S.player, S.line)]
    return S.reset_index(drop=True), date, sheet, gate

def annotate(S, date, logs=None):
    logs = load_logs() if logs is None else logs
    by = {k: v for k, v in logs.groupby('playerId')}
    iso = f'{date[:4]}-{date[4:6]}-{date[6:]}'
    rows = []
    for _, r in S.iterrows():
        f = features_for(by, r.nhl_id, iso) if pd.notna(r.get('nhl_id')) else compute(0, 0, 0, 0, 0, 0, 0, 0)
        v = f['att_over'] if r.side == 'over' else -f['att_over']
        rows.append(dict(att={1: '+', -1: '-', 0: '0'}[v], **{k: f[k] for k in
                    ['n_recent', 'n_base', 'att60_r10', 'att60_base', 'acc_r10', 'acc_base', 'sog60_r10', 'sog60_base',
                     'a_vol', 'b_acc', 'proj_sog60']}, att_why=f['att_why']))
    A = pd.DataFrame(rows)
    out = pd.concat([S.reset_index(drop=True), A], axis=1)
    out['agrees_n_plus_att'] = out.agrees_n + (out.att == '+').astype(int)
    out['of_8_label'] = [f'{int(x)} of 8' if pd.notna(x) else '' for x in out.agrees_n_plus_att]
    return out

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('path'); ap.add_argument('--out'); a = ap.parse_args()
    S, date, sheet, gate = load_pass(a.path)
    out = annotate(S, date)
    cols = ['game', 'player', 'side', 'line', 'dk_price', 'status', 'agrees_n', 'att', 'agrees_n_plus_att', 'of_8_label',
            'att60_r10', 'att60_base', 'a_vol', 'acc_r10', 'acc_base', 'b_acc', 'sog60_r10', 'sog60_base', 'proj_sog60',
            'n_recent', 'n_base', 'att_why', 'nhl_id']
    cols = [c for c in cols if c in out]
    o = a.out or os.path.join(HERE, 'out', os.path.basename(a.path).split('.')[0] + '_att.csv')
    out[cols].round(3).to_csv(o, index=False)
    print('sheet', sheet, '\ngate', gate, '\nwrote', o, len(out), 'sides')
    print(out.att.value_counts().to_dict())
    m = out[out.agrees_n >= 4]
    print('4+ of 7:', len(m), m.att.value_counts().to_dict(), '| 5+ of 8:', int((out.agrees_n_plus_att >= 5).sum()))
