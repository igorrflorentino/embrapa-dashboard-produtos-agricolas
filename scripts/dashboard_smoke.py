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

Cloud Run auth:
  When --url targets a ``*.run.app`` host (i.e. a private Cloud Run service),
  the script auto-mints a Google identity token via ``gcloud auth
  print-identity-token --audiences=<url>`` and sends it as a bearer header.
  The caller must hold ``roles/run.invoker`` on the service. See
  ``docs/auth.md``. Pass ``--no-auth`` to skip (e.g. testing the 403 path).

Usage:
    python scripts/dashboard_smoke.py                 # launch + smoke
    python scripts/dashboard_smoke.py --no-launch --url https://...  # gate a deploy
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VIEW_PATH = "/ibge-pevs/visao-geral"


# ── HTTP helpers (stdlib) ───────────────────────────────────────────────────
def http_get(
    url: str, timeout: float = 60.0, extra_headers: dict[str, str] | None = None
) -> tuple[int, bytes]:
    req = urllib.request.Request(url, method="GET", headers=extra_headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def http_post_json(
    url: str,
    obj: dict,
    timeout: float = 120.0,
    extra_headers: dict[str, str] | None = None,
) -> tuple[int, bytes]:
    data = json.dumps(obj).encode("utf-8")
    headers = {"Content-Type": "application/json", **(extra_headers or {})}
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


# ── Cloud Run identity-token minting ────────────────────────────────────────
# The dashboard service is deployed with --no-allow-unauthenticated. To gate a
# deploy from a developer machine, we mint a Google-signed identity token via
# gcloud and pass it as a bearer header. Two cases:
#   - User account: `gcloud auth print-identity-token` (no --audiences). The
#     token's aud is gcloud's OAuth client ID, which Cloud Run whitelists.
#     Passing --audiences FAILS for user accounts ("Invalid account type").
#   - Service account: must pass --audiences=<url> so the token's aud matches
#     the receiving service URL; Cloud Run validates strictly.
# See docs/auth.md.
def _resolve_gcloud() -> str | None:
    """Locate the gcloud executable. shutil.which respects PATHEXT on Windows
    (where gcloud is a .cmd shim), so this works on both POSIX and Windows.
    subprocess.run with a bare ``"gcloud"`` argv element does NOT respect
    PATHEXT and fails with FileNotFoundError on Windows — hence this helper.
    """
    return shutil.which("gcloud")


def _account_is_service_account(gcloud: str) -> bool:
    """True if `gcloud config get-value account` returns a *.gserviceaccount.com."""
    try:
        result = subprocess.run(
            [gcloud, "config", "get-value", "account"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False
    return (result.stdout or "").strip().lower().endswith(".gserviceaccount.com")


def _mint_identity_token(gcloud: str, audience: str) -> str | None:
    """Mint an identity token via gcloud. Returns None on failure."""
    cmd = [gcloud, "auth", "print-identity-token"]
    if _account_is_service_account(gcloud):
        cmd.append(f"--audiences={audience}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=True)
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip()[:300]
        print(
            f"WARN: `gcloud auth print-identity-token` failed: {stderr}\n"
            "      Run `gcloud auth login` then retry, or pass --no-auth.",
            file=sys.stderr,
        )
        return None
    except subprocess.TimeoutExpired:
        print("WARN: gcloud token mint timed out after 15s.", file=sys.stderr)
        return None
    return (result.stdout or "").strip() or None


def cloud_run_auth_headers(base: str, *, enabled: bool = True) -> dict[str, str]:
    """Return an Authorization header for Cloud Run targets; {} otherwise.

    Auto-detects Cloud Run by the ``.run.app`` host suffix so localhost smoke
    runs are untouched. Pass ``enabled=False`` to disable for custom domains
    or to test unauthenticated behavior.
    """
    if not enabled:
        return {}
    host = (urllib.parse.urlparse(base).hostname or "").lower()
    if not host.endswith(".run.app"):
        return {}
    gcloud = _resolve_gcloud()
    if gcloud is None:
        print(
            "WARN: gcloud not on PATH — cannot mint identity token for Cloud Run.\n"
            "      Install Google Cloud SDK or pass --no-auth to skip.",
            file=sys.stderr,
        )
        return {}
    token = _mint_identity_token(gcloud, base)
    return {"Authorization": f"Bearer {token}"} if token else {}


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
def run_checks(
    base: str, extra_headers: dict[str, str] | None = None
) -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []
    h = extra_headers or {}

    # 1. health
    try:
        status, body = http_get(f"{base}/_health", extra_headers=h)
        ok = status == 200 and json.loads(body or b"{}").get("status") == "ok"
        results.append(("GET /_health -> {status: ok}", ok, f"HTTP {status} {body[:80]!r}"))
    except Exception as e:
        results.append(("GET /_health -> {status: ok}", False, f"error: {e}"))

    # 2. index / Dash bootstrap
    try:
        status, body = http_get(f"{base}/", extra_headers=h)
        text = body.decode("utf-8", "replace")
        ok = status == 200 and ("_dash-config" in text or "react-entry-point" in text)
        results.append(("GET / -> Dash bootstrap", ok, f"HTTP {status}, {len(body)} bytes"))
    except Exception as e:
        results.append(("GET / -> Dash bootstrap", False, f"error: {e}"))

    # 3. dependencies (init-error gate)
    deps: list[dict] = []
    try:
        status, body = http_get(f"{base}/_dash-dependencies", extra_headers=h)
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
        status, raw = http_post_json(f"{base}/_dash-update-component", body_obj, extra_headers=h)
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


# ── Public orchestrator (used by main() and by tests/test_dashboard_smoke.py)
def run_smoke(
    *,
    url: str = "http://127.0.0.1:8051",
    launch: bool = True,
    port: int = 8051,
    timeout: float = 90.0,
    log_path: Path | None = None,
    extra_headers: dict[str, str] | None = None,
) -> list[tuple[str, bool, str]]:
    """Launch (or target) the dashboard, run the HTTP+callback smoke, return results.

    Each result is ``(check_name, passed, detail)``. The caller decides how to
    surface them (print for the CLI; assert for pytest). Raises ``RuntimeError``
    if ``launch=True`` and the server never becomes healthy within ``timeout``.

    Keeping orchestration here — instead of in ``main()`` — lets the pytest
    wrapper reuse the exact same launch/check/teardown flow without re-implementing
    the server lifecycle, and guarantees both code paths surface the same failures.

    ``extra_headers`` is forwarded to every check request — used by the CLI to
    inject a Cloud Run bearer token when targeting a private ``*.run.app``
    service; pytest can compute and pass its own headers (e.g. WIF-issued
    identity token) the same way.
    """
    proc = None
    base = url
    resolved_log = log_path or REPO_ROOT / "artifacts" / "dashboard_smoke_server.log"
    try:
        if launch:
            base = f"http://127.0.0.1:{port}"
            resolved_log.parent.mkdir(parents=True, exist_ok=True)
            proc = launch_server(port, resolved_log)
            if not wait_for_health(base, timeout):
                raise RuntimeError(
                    f"dashboard server did not become healthy within {timeout:.0f}s "
                    f"(see {resolved_log})"
                )
        return run_checks(base, extra_headers=extra_headers)
    finally:
        if proc is not None:
            stop_server(proc)


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
    parser.add_argument(
        "--no-auth",
        dest="auth",
        action="store_false",
        default=True,
        help=(
            "Skip Cloud Run identity-token minting. By default a token is auto-"
            "minted via gcloud when --url targets a *.run.app host. See docs/auth.md."
        ),
    )
    args = parser.parse_args()

    log_path = REPO_ROOT / "artifacts" / "dashboard_smoke_server.log"
    if args.launch:
        base = f"http://127.0.0.1:{args.port}"
        print(f"Launching dashboard on {base} (log: {log_path}) ...")
    else:
        print(f"Testing already-running server at {args.url} ...\n")

    # Mint a Cloud Run identity token when targeting a *.run.app URL. The
    # local launched-server path keeps {} headers (localhost is unaffected).
    auth_headers = cloud_run_auth_headers(args.url, enabled=args.auth)
    if auth_headers:
        print("Auth: minted gcloud identity token for Cloud Run target.\n")

    try:
        results = run_smoke(
            url=args.url,
            launch=args.launch,
            port=args.port,
            timeout=args.timeout,
            log_path=log_path,
            extra_headers=auth_headers,
        )
    except RuntimeError as e:
        print(f"FAILED: {e}")
        _print_log_tail(log_path)
        return 2

    if args.launch:
        print("Server healthy. Checks complete.\n")

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
