"""CollegeFootballData.com client (needs CFBD_API_KEY env var; free tier = 1,000 calls/month).

* The key is read from the environment only and is never printed or written anywhere.
* Every response is cached under data/cfbd/ (past seasons forever, current season with a TTL),
  and every *network* call is appended to data/cfbd/calls.log (timestamp, path, params, status)
  so quota usage is auditable.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime
from pathlib import Path

import requests

from .net import ROOT

BASE = "https://api.collegefootballdata.com"
CACHE = ROOT / "data" / "cfbd"
CACHE.mkdir(parents=True, exist_ok=True)
CALL_LOG = CACHE / "calls.log"
_session_calls = {"network": 0, "cached": 0}


class CFBDError(RuntimeError):
    pass


def available() -> bool:
    return bool(os.environ.get("CFBD_API_KEY"))


def _path(endpoint: str, params: dict) -> Path:
    key = endpoint + "?" + json.dumps(params, sort_keys=True)
    slug = endpoint.strip("/").replace("/", "_")
    return CACHE / f"{slug}_{hashlib.sha1(key.encode()).hexdigest()[:12]}.json"


def get(endpoint: str, params: dict | None = None, ttl: float | None = None, use_cache: bool = True):
    """Cached GET. ttl=None caches forever (use for completed seasons)."""
    params = params or {}
    p = _path(endpoint, params)
    if use_cache and p.exists() and (ttl is None or time.time() - p.stat().st_mtime < ttl):
        _session_calls["cached"] += 1
        return json.loads(p.read_text())
    key = os.environ.get("CFBD_API_KEY")
    if not key:
        raise CFBDError("CFBD_API_KEY not set")
    r = requests.get(BASE + endpoint, params=params, timeout=60,
                     headers={"Authorization": f"Bearer {key}", "Accept": "application/json"})
    _session_calls["network"] += 1
    with open(CALL_LOG, "a") as f:
        f.write(f"{datetime.now().isoformat(timespec='seconds')}\t{endpoint}\t{json.dumps(params, sort_keys=True)}\t{r.status_code}\n")
    if r.status_code != 200:
        raise CFBDError(f"{endpoint} {params} -> HTTP {r.status_code}: {r.text[:200]}")
    data = r.json()
    if use_cache:
        p.write_text(json.dumps(data))
    return data


def quota() -> dict | None:
    """Remaining-call info (never cached)."""
    try:
        return get("/info", use_cache=False)
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def network_calls_logged() -> int:
    return sum(1 for _ in open(CALL_LOG)) if CALL_LOG.exists() else 0


def session_stats() -> dict:
    return dict(_session_calls)
