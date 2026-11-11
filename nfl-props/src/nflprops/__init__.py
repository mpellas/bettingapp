"""nflprops: NFL player-prop research pipeline (walk-forward, leakage-safe)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
CACHE = DATA / "cache"
REPORTS = ROOT / "reports"
EXPERIMENTS = ROOT / "experiments"
CONFIGS = ROOT / "configs"
