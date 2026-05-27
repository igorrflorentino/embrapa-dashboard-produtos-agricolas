#!/usr/bin/env python
"""Tier 2 — headless-browser visual check of the Dash dashboard.

Loads each key view in real Chromium, asserts the blocking error overlay is
absent and that the page actually rendered content, and writes a screenshot
per view to ``artifacts/`` so the visual result can be eyeballed before a
release. Reuses the launch/health helpers from ``dashboard_smoke.py``.

Requires the ``visual`` extra and a one-time browser download:
    uv sync --extra visual
    uv run --extra visual python -m playwright install chromium

Usage:
    python scripts/dashboard_visual_check.py                       # launch + check
    python scripts/dashboard_visual_check.py --no-launch --url https://...  # deployed
"""

from __future__ import annotations

import argparse
import contextlib
import sys
from pathlib import Path

from dashboard_smoke import launch_server, stop_server, wait_for_health

REPO_ROOT = Path(__file__).resolve().parent.parent

# (slug, screenshot filename). Canonical source-scoped paths under /ibge-pevs.
# The 4 primary views after the Task #5 refactor — produto / tabela / export
# / glossario / dados were absorbed (see plan: voc-um-especialista-lively-treasure.md).
VIEWS = [
    ("visao-geral", "overview"),
    ("qualidade-dados", "quality"),
    ("valor-e-volume", "value-volume"),
    ("geografia", "geography"),
]

# Any of these marks "real content rendered" for a view (charts, tables, heroes).
CONTENT_SELECTOR = (
    "#page-container .page-hero, #page-container .section-title, "
    "#page-container table, #page-container .js-plotly-plot"
)


def check_view(page, base: str, slug: str, shot_name: str, out_dir: Path) -> tuple[bool, str]:
    url = f"{base}/ibge-pevs/{slug}"
    try:
        page.goto(url, wait_until="networkidle", timeout=60_000)
        page.wait_for_selector(CONTENT_SELECTOR, timeout=30_000)
        page.wait_for_timeout(1_500)  # let Plotly finish painting before the shot
    except Exception as e:
        _shot(page, out_dir / f"{shot_name}.png")
        return False, f"did not render within timeout: {e}"

    shot_path = out_dir / f"{shot_name}.png"
    _shot(page, shot_path)

    overlay_cls = (page.get_attribute("#error-overlay", "class") or "").split()
    if "visible" in overlay_cls:
        msg = page.inner_text("#error-overlay")[:200].replace("\n", " ")
        return False, f"error overlay shown: {msg} (see {shot_path.name})"

    child_count = page.eval_on_selector("#page-container", "el => el.childElementCount")
    if not child_count:
        return False, f"page-container is empty (see {shot_path.name})"

    return True, f"rendered, no error overlay -> {shot_path.name}"


def _shot(page, path: Path) -> None:
    with contextlib.suppress(Exception):
        page.screenshot(path=str(path), full_page=True)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8053")
    parser.add_argument("--launch", dest="launch", action="store_true", default=True)
    parser.add_argument("--no-launch", dest="launch", action="store_false")
    parser.add_argument("--port", type=int, default=8053)
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--out", default=str(REPO_ROOT / "artifacts"))
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright is not installed. Run:")
        print("  uv sync --extra visual")
        print("  uv run --extra visual python -m playwright install chromium")
        return 3

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    proc = None
    base = args.url
    log_path = out_dir / "dashboard_visual_server.log"
    try:
        if args.launch:
            base = f"http://127.0.0.1:{args.port}"
            print(f"Launching dashboard on {base} (log: {log_path}) ...")
            proc = launch_server(args.port, log_path)
            if not wait_for_health(base, args.timeout):
                print(f"FAILED: server did not become healthy within {args.timeout:.0f}s")
                return 2
            print("Server healthy. Capturing views ...\n")
        else:
            print(f"Capturing views from {base} ...\n")

        results: list[tuple[str, bool, str]] = []
        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch(headless=True)
            except Exception as e:
                print(f"Could not launch Chromium ({e}).")
                print("Run: uv run --extra visual python -m playwright install chromium")
                return 3
            context = browser.new_context(viewport={"width": 1440, "height": 1024})
            page = context.new_page()
            for slug, shot_name in VIEWS:
                ok, detail = check_view(page, base, slug, shot_name, out_dir)
                results.append((f"/ibge-pevs/{slug}", ok, detail))
            browser.close()
    finally:
        if proc is not None:
            stop_server(proc)

    all_ok = True
    for name, ok, detail in results:
        mark = "[PASS]" if ok else "[FAIL]"
        all_ok = all_ok and ok
        print(f"{mark} {name}\n       {detail}")

    print(f"\nScreenshots in: {out_dir}")
    if all_ok:
        print("All visual checks passed.")
        return 0
    print("Visual checks FAILED.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
