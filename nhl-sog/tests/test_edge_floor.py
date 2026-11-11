"""5.0-pt model-edge floor (2026-10-20, testers' Oct 12-16 rule): sides with model minus no-vig under 5 pts are
Skipped with 'edge below 5-pt floor' on both the Fliff-check and DraftKings lists. Formenton Oct 20 1508 (+3.1)."""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd, build_sheet as B
def row(player, edge, ev=-0.01, rm=0.05):
    return dict(player=player, _side='under', _edge=edge, _rmargin=rm, _ev=ev, _role='', _veto='',
                flag_shop_ok='yes', flag_within_12_novig='yes', flag_slot_veto='no', flag_milestone='yes', flag_lineup_gate='yes')
df = pd.DataFrame([row('Kapanen', .081), row('Kaprizov', .085), row('Formenton', .031), row('Shabanov', .090),
                   row('AtFloor', .050), row('DKthin', .040, ev=0.02), row('DKok', .070, ev=0.02), row('Thin', .005)])
S = B.assign_status(df, '_rmargin').set_index('player')
assert S.at['Formenton', 'status'] == 'Skipped' and S.at['Formenton', 'status_reason'].startswith('edge below 5-pt floor'), S.loc['Formenton']
assert S.at['AtFloor', 'status'] == 'Fliff check'          # exactly 5.0 passes
for p in ('Kapanen', 'Kaprizov', 'Shabanov'): assert S.at[p, 'status'] == 'Fliff check', p
assert S.at['DKthin', 'status'] == 'Skipped' and 'edge below 5-pt floor' in S.at['DKthin', 'status_reason']
assert S.at['DKok', 'status'] == 'DK bet'
assert S.at['Thin', 'status_reason'].startswith('thin edge')  # thin-edge reason kept
print('ok')
