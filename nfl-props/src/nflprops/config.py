from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import yaml

from . import CONFIGS


def load_config(path: str | Path | None = None) -> dict:
    p = Path(path) if path else CONFIGS / "default.yaml"
    return yaml.safe_load(p.read_text())


def deep_update(base: dict, upd: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in upd.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_update(out[k], v)
        else:
            out[k] = v
    return out


def chash(obj) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:10]


def rel_path(p: str | Path) -> str:
    """Path relative to the project root when inside it (cache keys must not depend on where the project lives)."""
    from . import ROOT
    q = Path(p)
    q = q if q.is_absolute() else ROOT / q
    try:
        return str(q.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(q)


def _file_sha1(p: str | Path) -> str | None:
    from . import ROOT
    q = Path(p)
    q = q if q.is_absolute() else ROOT / q
    return hashlib.sha1(q.read_bytes()).hexdigest()[:10] if q.exists() else None


def model_key(cfg: dict) -> dict:
    """The parts of the config that change model predictions (betting params do not). Line-CSV paths are made
    project-relative and the CSV's content hash is included (Tester1 N9 / N3); for line source 'none' the
    simulator settings are irrelevant and dropped."""
    lines = copy.deepcopy(cfg["lines"])
    src = lines.get("source")
    if src == "csv":
        lines = {"source": "csv", "csv_path": rel_path(lines["csv_path"]), "csv_sha1": _file_sha1(lines["csv_path"])}
    elif src == "none":
        lines = {"source": "none"}
    else:
        lines.pop("csv_path", None)
    return {"model": cfg["model"], "lines": lines, "markets": cfg["markets"], "data": cfg["data"],
            "universe": cfg.get("universe", {})}
