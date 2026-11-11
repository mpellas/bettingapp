#!/usr/bin/env python3
"""Fill the candidate pre-registration's hash fields from the CURRENT git HEAD (which must be clean for code files).

    .venv/bin/python scripts/update_prereg_hashes.py [--check-file reports/pregame_asof_check_2026_wk04.json]

Writes: frozen_procedure.git_commit (full HEAD), file_sha1 (git blob content sha1 of key files at HEAD, i.e. plain
sha1 of the file bytes), code_version, champion hash, and data_checks.pre_freeze_check_result_sha256 if given.
Refuses if any tracked file outside prereg/, data/, reports/ differs from HEAD (the pinned commit must be the code
that runs). Does not commit or publish anything.
"""
import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PRE = ROOT / "prereg" / "prereg_2026_wk5-18_CANDIDATE.yaml"
FILES = ["src/nflprops/pregame.py", "src/nflprops/track.py", "src/nflprops/snapshot.py", "src/nflprops/snaplines.py",
         "src/nflprops/calibration.py", "src/nflprops/betting.py", "src/nflprops/config.py", "src/nflprops/metrics.py",
         "src/nflprops/features.py", "src/nflprops/model.py", "src/nflprops/data.py", "configs/default.yaml",
         "experiments/champion.json", "scripts/snapshot_loop.sh", "scripts/snapshot_supervisor.sh"]


def git(*a, strip=True):
    out = subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return out.strip() if strip else out


ap = argparse.ArgumentParser()
ap.add_argument("--check-file", default=None)
a = ap.parse_args()
dirty = [l[3:] for l in git("status", "--porcelain", strip=False).splitlines()
         if not re.match(r"(prereg|data|reports|logs)/", l[3:])]
if dirty:
    sys.exit(f"refusing: uncommitted changes outside prereg/data/reports: {dirty}")
head = git("rev-parse", "HEAD")
y = PRE.read_text()
y = re.sub(r"(  git_commit: )\S+", rf"\g<1>{head}", y, count=1)
blk = "".join(f"    {f}: {hashlib.sha1((ROOT / f).read_bytes()).hexdigest()}\n" for f in FILES)
y = re.sub(r"(  file_sha1:[^\n]*\n)(    [^\n]*\n)+", lambda m: m.group(1) + blk, y, count=1)
sys.path.insert(0, str(ROOT / "src"))
from nflprops.backtest import CODE_FILES  # noqa: E402
from nflprops.features import code_version  # noqa: E402
y = re.sub(r"(  code_version: )\S+", rf"\g<1>{code_version(CODE_FILES)}", y, count=1)
ch = json.loads((ROOT / "experiments" / "champion.json").read_text())["champion_hash"]
csha = hashlib.sha1((ROOT / "experiments" / "champion.json").read_bytes()).hexdigest()
y = re.sub(r"(  champion_config_hash: )\S+(\s+# experiments/champion.json sha1 )\S+", rf"\g<1>{ch}\g<2>{csha}", y, count=1)
if a.check_file:
    h = hashlib.sha256((ROOT / a.check_file).read_bytes()).hexdigest()
    y = re.sub(r"(  pre_freeze_check_result_sha256: ).*", rf"\g<1>{h}   # {a.check_file}", y, count=1)
PRE.write_text(y)
print(f"git_commit {head}\nprereg sha1 {hashlib.sha1(PRE.read_bytes()).hexdigest()} (not published)")
