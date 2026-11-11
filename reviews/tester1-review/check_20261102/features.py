"""Shared data loading + strictly as-of features."""
import pandas as pd,numpy as np,lightgbm as lgb,glob,json,sys
from scipy import stats,optimize
def load():
    df=pd.concat([pd.read_pickle(f) for f in sorted(glob.glob('data/s*.pkl'))]).drop_duplicates(['playerId','gameId'])
    df=df.sort_values(['gameDate','gameId']).reset_index(drop=True)
    df['toi']=df.timeOnIcePerGame/60; df['pptoi']=df.ppTimeOnIce.fillna(0)/60; df['att']=df.totalShotAttempts
    df['date']=pd.to_datetime(df.gameDate); df['home']=(df.homeRoad=='H').astype(int); df['D']=(df.positionCode=='D').astype(int)
    return df
def feats(df):
    g=df.groupby('playerId',sort=False)
    sh=lambda c:g[c].shift(1)   # strictly prior games
    for w in (5,10,30):
        for c in ['shots','toi','pptoi','att']:
            df[f'{c}_r{w}']=g[c].transform(lambda s:s.shift(1).rolling(w,min_periods=1).mean())
        df[f'sog60_r{w}']=df[f'shots_r{w}']/df[f'toi_r{w}']*60; df[f'att60_r{w}']=df[f'att_r{w}']/df[f'toi_r{w}']*60
    df['shots_car']=g.shots.transform(lambda s:s.shift(1).expanding().mean())
    df['n_prior']=g.cumcount()
    df['rest']=(df.date-g.date.shift(1)).dt.days.clip(upper=10); df['b2b']=(df.rest==1).astype(int)
    # opponent shots allowed per game, prior games only
    tg=df.groupby(['gameId','opponentTeamAbbrev','date'],as_index=False).shots.sum().sort_values('date')
    tg['opp_sa_r20']=tg.groupby('opponentTeamAbbrev').shots.transform(lambda s:s.shift(1).rolling(20,min_periods=3).mean())
    tf=df.groupby(['gameId','teamAbbrev','date'],as_index=False).shots.sum().sort_values('date')
    tf['team_sf_r20']=tf.groupby('teamAbbrev').shots.transform(lambda s:s.shift(1).rolling(20,min_periods=3).mean())
    df=df.drop(columns=[c for c in ['opp_sa_r20','team_sf_r20'] if c in df]).merge(tg[['gameId','opponentTeamAbbrev','opp_sa_r20']],on=['gameId','opponentTeamAbbrev'],how='left').merge(tf[['gameId','teamAbbrev','team_sf_r20']],on=['gameId','teamAbbrev'],how='left')
    return df
FEATS=lambda df:[c for c in df if '_r' in c or c in ['shots_car','n_prior','rest','b2b','home','D']]
