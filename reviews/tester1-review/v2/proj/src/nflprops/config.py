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


def model_key(cfg: dict) -> dict:
    """The parts of the config that change model predictions (betting params do not)."""
    return {"model": cfg["model"], "lines": cfg["lines"], "markets": cfg["markets"], "data": cfg["data"],
            "universe": cfg.get("universe", {})}
