"""Append X call counts and relevant social posts. Usage:
python3 log_x.py calls N "note"           -> x_calls.csv (run_pt, calls, day_total for the X day window = UTC date, note); prints day total
python3 log_x.py posts posts.json         -> social_log.csv rows (list of dicts: gameId, source, author, time_pt, url, text, players_named, dfo_reflected)"""
import sys,os,json,pandas as pd
H='/workspace/nhl-sog-papertests'; now=pd.Timestamp.now(tz='UTC'); pt=now.tz_convert('America/Los_Angeles').strftime('%Y-%m-%d %H:%M:%S PT')
if sys.argv[1]=='calls':
    f=f'{H}/x_calls.csv'; old=pd.read_csv(f) if os.path.exists(f) else pd.DataFrame(columns=['run_pt','x_day_utc','calls','day_total','note'])
    day=now.strftime('%Y-%m-%d'); tot=int(old[old.x_day_utc==day].calls.sum())+int(sys.argv[2])
    pd.concat([old,pd.DataFrame([dict(run_pt=pt,x_day_utc=day,calls=int(sys.argv[2]),day_total=tot,note=sys.argv[3] if len(sys.argv)>3 else '')])]).to_csv(f,index=False)
    print('X day total',tot,'(stop at 800)')
else:
    rows=json.load(open(sys.argv[2])); f=f'{H}/social_log.csv'
    for r in rows: r.setdefault('run_pt',pt)
    pd.DataFrame(rows).to_csv(f,mode='a',header=not os.path.exists(f),index=False); print(len(rows),'posts logged')
