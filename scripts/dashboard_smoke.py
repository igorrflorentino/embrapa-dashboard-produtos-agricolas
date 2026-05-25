#!/usr/bin/env python
"""HTTP + callback smoke test for the Dash dashboard.

Boots the dashboard server (or targets an already-running URL) and drives
its real HTTP surface to catch gross initialization and data-path errors
without a browser. Stdlib only — runs under bare ``uv run python`` and
against any URL (local or a deployed Cloud Run service).

Checks:
  1. GET /_health            -> 200 and {"status": "ok"}
  2. GET /                   -> 200 and the Dash bootstrap is present
  3. GET /_dash-dependencies -> 200 and a non-empty callback list
                                (proves every view's register_fn ran)
  4. POST /_dash-update-component for the route callback rendering
     /ibge-pevs/visao-geral -> 200, global-error null, page-container
     populated. This forces the live BigQuery snapshot load.

Exit code 0 only if all checks pass.

Usage:
    python scripts/dashboard_smoke.py                 # launch + smoke
    python scripts/dashboard_smoke.py --no-launch --url https://...  # gate a deploy
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VIEW_PATH = "/ibge-pevs/visao-geral"


# ── HTTP helpers (stdlib) ───────────────────────────────────────────────────
def http_get(url: str, timeout: float = 60.0) -> tuple[int, bytes]:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def http_post_json(url: str, obj: dict, timeout: float = 120.0) -> tuple[int, bytes]:
    data = json.dumps(obj).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


# ── Server lifecycle (reused by the visual checker) ─────────────────────────
def _server_python() -> str:
    """The project venv interpreter — launched directly (not via ``uv run``) so
    the spawned process IS the server and terminate() reaps it. Going through
    ``uv run`` leaves an unkillable python grandchild that holds the port and
    venv files. Falls back to the current interpreter if the venv is missing.
    """
    cand = REPO_ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return str(cand) if cand.exists() else sys.executable


def launch_server(port: int, log_path: Path) -> subprocess.Popen:
    """Spawn the dashboard dev server with PORT=<port>; tee output to log_path."""
    env = dict(os.environ)
    env["PORT"] = str(port)
    env.setdefault("DASH_DEBUG", "")  # single process, no reloader
    log_file = open(log_path, "w", encoding="utf-8")  # noqa: SIM115 (held for proc lifetime)
    proc = subprocess.Popen(
        [_server_python(), "-m", "embrapa_commodities.dashboard.app"],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    proc._smoke_log_file = log_file  # type: ignore[attr-defined]
    return proc


def wait_for_health(base: str, timeout: float = 90.0) -> bool:
    """Poll /_health until 200 or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            status, _ = http_get(f"{base}/_health", timeout=5.0)
            if status == 200:
                return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.5)
    return False


def stop_server(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)
    log_file = getattr(proc, "_smoke_log_file", None)
    if log_file is not None:
        log_file.close()


# ── Dash callback wiring ────────────────────────────────────────────────────
def find_route_callback(deps: list[dict]) -> dict | None:
    """The server-side callback whose inputs include url.pathname (= _route)."""
    for entry in deps:
        if entry.get("clientside_function"):
            continue
        for inp in entry.get("inputs", []):
            if inp.get("id") == "url" and inp.get("property") == "pathname":
                return entry
    return None


def parse_output_spec(output: str) -> list[dict]:
    """Parse a Dash callback output id into [{id, property}, ...].

    Multi-output is serialized as ``..a.b...c.d..``; single as ``a.b``.
    """
    if output.startswith("..") and output.endswith(".."):
        parts = output[2:-2].split("...")
    else:
        parts = [output]
    specs = []
    for p in parts:
        cid, _, prop = p.rpartition(".")
        specs.append({"id": cid, "property": prop})
    return specs


def build_route_body(entry: dict, pathname: str) -> dict:
    inputs = []
    for inp in entry.get("inputs", []):
        value = pathname if (inp.get("id") == "url" and inp.get("property") == "pathname") else None
        inputs.append({"id": inp["id"], "property": inp["property"], "value": value})
    state = [
        {"id": s["id"], "property": s["property"], "value": None} for s in entry.get("state", [])
    ]
    return {
        "output": entry["output"],
        "outputs": parse_output_spec(entry["output"]),
        "inputs": inputs,
        "state": state,
        "changedPropIds": ["url.pathname"],
    }


# ── Checks ──────────────────────────────────────────────────────────────────
def run_checks(base: str) -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []

    # 1. health
    try:
        status, body = http_get(f"{base}/_health")
        ok = status == 200 and json.loads(body or b"{}").get("status") == "ok"
        results.append(("GET /_health -> {status: ok}", ok, f"HTTP {status} {body[:80]!r}"))
    except Exception as e:
        results.append(("GET /_health -> {status: ok}", False, f"error: {e}"))

    # 2. index / Dash bootstrap
    try:
        status, body = http_get(f"{base}/")
        text = body.decode("utf-8", "replace")
        ok = status == 200 and ("_dash-config" in text or "react-entry-point" in text)
        results.append(("GET / -> Dash bootstrap", ok, f"HTTP {status}, {len(body)} bytes"))
    except Exception as e:
        results.append(("GET / -> Dash bootstrap", False, f"error: {e}"))

    # 3. dependencies (init-error gate)
    deps: list[dict] = []
    try:
        status, body = http_get(f"{base}/_dash-dependencies")
        deps = json.loads(body) if status == 200 else []
        ok = status == 200 and isinstance(deps, list) and len(deps) > 0
        results.append(
            ("GET /_dash-dependencies -> callbacks", ok, f"HTTP {status}, {len(deps)} callbacks")
        )
    except Exception as e:
        results.append(("GET /_dash-dependencies -> callbacks", False, f"error: {e}"))

    # 4. route render (live BigQuery gate)
    route = find_route_callback(deps) if deps else None
    if route is None:
        results.append(
            (
                f"POST route render {DEFAULT_VIEW_PATH}",
                False,
                "could not locate the url.pathname route callback",
            )
        )
        return results
    try:
        body_obj = build_route_body(route, DEFAULT_VIEW_PATH)
        status, raw = http_post_json(f"{base}/_dash-update-component", body_obj)
        detail, ok = _interpret_route_response(status, raw)
        results.append((f"POST route render {DEFAULT_VIEW_PATH}", ok, detail))
    except Exception as e:
        results.append((f"POST route render {DEFAULT_VIEW_PATH}", False, f"error: {e}"))

    return results


def _interpret_route_response(status: int, raw: bytes) -> tuple[str, bool]:
    if status != 200:
        return f"HTTP {status}: {raw[:300].decode('utf-8', 'replace')}", False
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return f"non-JSON response: {raw[:200]!r}", False
    response = payload.get("response", {})
    page = response.get("page-container", {})
    has_page = bool(page.get("children"))
    global_error = response.get("global-error", {}).get("data")
    if global_error:
        where = global_error.get("where", "?")
        msg = global_error.get("message", "?")
        return f"layout raised in {where}: {msg}", False
    if not has_page:
        return "page-container.children empty (no render, no error reported)", False
    return "page rendered, no error overlay (live BQ snapshot loaded)", True


# ── Main ────────────────────────────────────────────────────────────────────
def main() -> int:
    # The dashboard is pt-BR; error details carry ã/ç/õ. Force UTF-8 stdout so
    # they don't mojibake under the Windows console codepage.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8051",
        help="Base URL to test (default: the launched local server).",
    )
    parser.add_argument(
        "--launch",
        dest="launch",
        action="store_true",
        default=True,
        help="Launch the dashboard server (default).",
    )
    parser.add_argument(
        "--no-launch",
        dest="launch",
        action="store_false",
        help="Test an already-running --url (e.g. a deployed service).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8051,
        help="Port for the launched server (default 8051; avoids 8080 dev server).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=90.0,
        help="Seconds to wait for the server to become healthy.",
    )
    args = parser.parse_args()

    proc = None
    log_path = REPO_ROOT / "artifacts" / "dashboard_smoke_server.log"
    base = args.url

    try:
        if args.launch:
            base = f"http://127.0.0.1:{args.port}"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            print(f"Launching dashboard on {base} (log: {log_path}) ...")
            proc = launch_server(args.port, log_path)
            if not wait_for_health(base, args.timeout):
                print(f"FAILED: server did not become healthy within {args.timeout:.0f}s")
                _print_log_tail(log_path)
                return 2
            print("Server healthy. Running checks ...\n")
        else:
            print(f"Testing already-running server at {base} ...\n")

        results = run_checks(base)
    finally:
        if proc is not None:
            stop_server(proc)

    all_ok = True
    for name, ok, detail in results:
        mark = "[PASS]" if ok else "[FAIL]"
        all_ok = all_ok and ok
        print(f"{mark} {name}\n       {detail}")

    print()
    if all_ok:
        print("All smoke checks passed.")
        return 0
    print("Smoke FAILED.")
    if args.launch:
        _print_log_tail(log_path)
    return 1


def _print_log_tail(log_path: Path, lines: int = 40) -> None:
    if not log_path.exists():
        return
    tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
    print(f"\n--- last {len(tail)} lines of server log ({log_path}) ---")
    for line in tail:
        print(f"  {line}")


if __name__ == "__main__":
    sys.exit(main())
