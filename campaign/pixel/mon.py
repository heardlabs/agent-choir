"""Tiny Monid CLI wrapper: run an endpoint, poll, return the output JSON."""
import json, re, subprocess, time

def run(provider, endpoint, body, timeout=600):
    r = subprocess.run(["monid", "run", "-p", provider, "-e", endpoint, "-i", json.dumps(body)], capture_output=True, text=True)
    m = re.search(r"Run ID: (\w+)", r.stdout + r.stderr)
    if not m: raise RuntimeError((r.stdout + r.stderr)[-800:])
    rid, t0 = m.group(1), time.time()
    while time.time() - t0 < timeout:
        g = subprocess.run(["monid", "runs", "get", "-r", rid, "-j"], capture_output=True, text=True).stdout
        try: d = json.loads(g)
        except Exception: d = {}
        st = str(d.get("status", "")).upper()
        if st == "COMPLETED": return d
        if st in ("FAILED", "ERROR", "CANCELLED"): raise RuntimeError(g[-800:])
        time.sleep(4)
    raise TimeoutError(rid)
