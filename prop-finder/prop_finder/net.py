"""Small HTTP helper with on-disk caching and retries."""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

_session = requests.Session()
_session.headers.update({"User-Agent": "prop-finder/0.1 (personal research tool)",
                         "Accept-Encoding": "gzip, deflate"})


class FetchError(RuntimeError):
    pass


def _cache_path(url: str, params: dict | None, suffix: str) -> Path:
    key = url + "?" + json.dumps(params or {}, sort_keys=True)
    h = hashlib.sha1(key.encode()).hexdigest()[:20]
    return CACHE_DIR / f"{h}{suffix}"


def get_json(url: str, params: dict | None = None, ttl: float | None = 3600,
             retries: int = 3, timeout: float = 20, headers: dict | None = None,
             cache: bool = True, allow_404: bool = False):
    """GET JSON. ttl=None -> cache forever; ttl=0 -> always refetch.
    Returns parsed JSON, or None for 404 when allow_404."""
    path = _cache_path(url, params, ".json")
    if cache and path.exists() and (ttl is None or time.time() - path.stat().st_mtime < ttl):
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    last = None
    for attempt in range(retries):
        try:
            r = _session.get(url, params=params, timeout=timeout, headers=headers)
            if r.status_code == 404 and allow_404:
                return None
            if r.status_code == 429:
                time.sleep(2 + 3 * attempt)
                last = FetchError(f"429 rate limited: {url}")
                continue
            r.raise_for_status()
            data = r.json()
            if cache:
                path.write_text(json.dumps(data))
            return data
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1 + attempt)
    raise FetchError(f"GET failed {url}: {last}")


def get_file(url: str, dest: Path, ttl: float | None = 6 * 3600, timeout: float = 120) -> Path:
    """Download a (large) file to dest with TTL-based reuse."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and (ttl is None or time.time() - dest.stat().st_mtime < ttl):
        return dest
    last = None
    for attempt in range(3):
        try:
            with _session.get(url, stream=True, timeout=timeout, allow_redirects=True) as r:
                r.raise_for_status()
                tmp = dest.with_suffix(dest.suffix + ".part")
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(1 << 16):
                        f.write(chunk)
                os.replace(tmp, dest)
            return dest
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1 + attempt)
    if dest.exists():  # stale copy is better than nothing; caller is told via return
        return dest
    raise FetchError(f"download failed {url}: {last}")
