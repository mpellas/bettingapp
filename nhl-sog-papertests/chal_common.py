"""Paper challenger A: frozen-model feature set + opponent shots allowed split by F vs D (r20), as in
/workspace/feature-audit-nhl-20261102/ablate.py variant A_opp_by_pos. Read-only use of /workspace/nhl-sog code/data."""
import sys,os; sys.path.insert(0,'/workspace/nhl-sog')
import pandas as pd,numpy as np,json
from features import load,feats
def add_pos(df):
    t=df.groupby(['gameId','opponentTeamAbbrev','D','date'],as_index=False).shots.sum().sort_values('date')
    t['opp_sa_pos_r20']=t.groupby(['opponentTeamAbbrev','D']).shots.transform(lambda s:s.shift(1).rolling(20,min_periods=3).mean())
    return df.drop(columns=[c for c in ['opp_sa_pos_r20'] if c in df]).merge(t[['gameId','opponentTeamAbbrev','D','opp_sa_pos_r20']],on=['gameId','opponentTeamAbbrev','D'],how='left')
BASE=json.load(open('/workspace/nhl-sog/models/model_c3ab760178.json'))['features']
FEATS=BASE+['opp_sa_pos_r20']
