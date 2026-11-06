"""Minimal fal.ai queue client (stdlib only).

POST https://queue.fal.run/{model} -> {request_id, status_url, response_url}
GET status_url until COMPLETED, then GET response_url for the output.
Auth: ``Authorization: Key $FAL_KEY``.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

QUEUE = "https://queue.fal.run"
UA = "agent-choir/0.1"


class FalError(RuntimeError):
    pass


def _key() -> str:
    k = os.environ.get("FAL_KEY")
    if not k:
        raise FalError("FAL_KEY is not set (get one at https://fal.ai/dashboard/keys)")
    return k


def _req(method: str, url: str, body: dict | None = None, timeout: float = 60) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Key {_key()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": UA,
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:800]
        raise FalError(f"{method} {url} -> {e.code}: {detail}") from None


def run(model: str, payload: dict, timeout_s: float = 900, poll_s: float = 3.0, log=print) -> dict:
    sub = _req("POST", f"{QUEUE}/{model}", payload)
    status_url, response_url = sub["status_url"], sub["response_url"]
    log(f"  queued {model} ({sub.get('request_id', '?')})")
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        st = _req("GET", status_url)
        status = st.get("status")
        if status != last:
            log(f"  {model}: {status}")
            last = status
        if status == "COMPLETED":
            if st.get("error"):
                raise FalError(f"{model} failed: {st['error']}")
            return _req("GET", response_url)
        time.sleep(poll_s)
    raise FalError(f"{model} timed out after {timeout_s:.0f}s")


def download(url: str, dest: Path) -> Path:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        dest.write_bytes(r.read())
    return dest
