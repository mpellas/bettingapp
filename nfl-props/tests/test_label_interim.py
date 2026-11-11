import importlib.util, pathlib
spec = importlib.util.spec_from_file_location('li', pathlib.Path(__file__).parents[1] / 'scripts/label_interim.py')
li = importlib.util.module_from_spec(spec); spec.loader.exec_module(li)

def test_fail_becomes_interim_and_raw_kept():
    d = li.relabel({'decision_this_week_only': {'label': 'FAIL', 'signal': 1}})
    x = d['decision_this_week_only']
    assert x['label'].startswith('INTERIM') and x['label_raw_week_only'] == 'FAIL' and x['signal'] == 1

def test_idempotent():
    d = li.relabel(li.relabel({'decision_this_week_only': {'label': 'PASS'}}))
    assert d['decision_this_week_only']['label_raw_week_only'] == 'PASS'
