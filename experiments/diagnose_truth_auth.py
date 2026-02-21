#!/usr/bin/env python3
"""
Diagnose Truth Social access via Playwright browser simulation.

This script validates the same runtime path used by the application:
- direct connection (no proxy)
- optional proxy connection (Decodo)

It reports:
- current egress IP
- whether Cloudflare challenge is detected
- fetch success/failure
- number of statuses and newest status ID
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

from socialmedia.playwright_client import PlaywrightTruthClient  # noqa: E402


IPIFY_URL = "https://api.ipify.org?format=json"
PROJECT_ROOT = Path(__file__).parent.parent


def sanitize_proxy_url(url: str) -> str:
    import re
    return re.sub(r"://[^:]+:[^@]+@", "://", url)


def build_proxy_dict() -> dict[str, str] | None:
    enabled = os.getenv("DECODO_PROXY_ENABLED", "False").lower() == "true"
    if not enabled:
        return None

    proxy_url = os.getenv("DECODO_PROXY_URL", "").strip()
    if not proxy_url:
        return None

    proxy_user = os.getenv("DECODO_PROXY_USERNAME", "").strip()
    proxy_pass = os.getenv("DECODO_PROXY_PASSWORD", "").strip()

    if proxy_user and proxy_pass:
        scheme, rest = proxy_url.split("://", 1)
        proxy_url = f"{scheme}://{proxy_user}:{proxy_pass}@{rest}"

    return {"http": proxy_url, "https": proxy_url}


def get_current_ip(use_proxy: bool, proxies: dict[str, str] | None) -> str:
    try:
        import requests

        resp = requests.get(IPIFY_URL, proxies=(proxies if use_proxy else None), timeout=8)
        if resp.ok:
            return str(resp.json().get("ip", "unknown"))
        return f"ipify-status-{resp.status_code}"
    except Exception as exc:
        return f"ip-check-failed: {type(exc).__name__}: {exc}"


def run_playwright_attempt(
    username: str,
    since_id: str | None,
    use_proxy: bool,
    proxies: dict[str, str] | None,
    headless: bool,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "use_proxy": use_proxy,
        "ip": get_current_ip(use_proxy, proxies),
        "ok": False,
        "error": None,
        "cloudflare_detected": False,
        "count": 0,
        "newest_id": None,
    }

    try:
        client = PlaywrightTruthClient(
            proxy_config=({"proxies": proxies} if use_proxy and proxies else None),
            headless=headless,
            timeout_ms=30000,
        )
        statuses = list(client.pull_statuses(username=username, since_id=since_id, verbose=False))
        result["ok"] = True
        result["count"] = len(statuses)
        if statuses:
            result["newest_id"] = str(statuses[0].get("id"))
        elif not statuses:
            result["error"] = "API returned 0 statuses (possible silent rate-limit or empty feed)"
    except Exception as exc:
        error_str = str(exc)
        result["error"] = f"{type(exc).__name__}: {error_str}"
        if "cloudflare" in error_str.lower() or "attention required" in error_str.lower():
            result["cloudflare_detected"] = True
        if "something went wrong" in error_str.lower():
            result["error"] += " [page error detected]"

    return result


def print_result(label: str, data: dict[str, Any]) -> None:
    print("\n" + "=" * 90)
    print(label)
    print("=" * 90)
    print(f"use_proxy:            {data['use_proxy']}")
    print(f"ip:                   {data['ip']}")
    print(f"ok:                   {data['ok']}")
    print(f"cloudflare_detected:  {data['cloudflare_detected']}")
    print(f"count:                {data['count']}")
    print(f"newest_id:            {data['newest_id']}")
    print(f"error:                {data['error']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose Truth Social access via Playwright.")
    parser.add_argument("--attempts", type=int, default=2, help="Attempts per mode (default: 2)")
    parser.add_argument(
        "--mode",
        choices=["both", "direct", "proxy"],
        default="both",
        help="Test mode: both/direct/proxy",
    )
    parser.add_argument(
        "--username",
        default=None,
        help="Truth Social username to fetch (default: TARGET_USERNAME from .env)",
    )
    parser.add_argument(
        "--since-id",
        default=None,
        help="Optional since_id filter (default: none)",
    )
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / ".env")

    username = (args.username or os.getenv("TARGET_USERNAME", "realDonaldTrump")).strip()
    headless = os.getenv("PLAYWRIGHT_HEADLESS", "True").lower() == "true"
    proxy_dict = build_proxy_dict()

    print("\nTruth Access Diagnostics (Playwright)")
    print("-" * 90)
    print(f"username:      {username}")
    print(f"headless:      {headless}")
    print(f"attempts:      {args.attempts}")
    print(f"proxy_enabled: {proxy_dict is not None}")
    if proxy_dict:
        print(f"proxy_url:     {sanitize_proxy_url(proxy_dict['http'])}")
    print("-" * 90)

    modes: list[tuple[str, bool]] = []
    if args.mode in ("both", "direct"):
        modes.append(("DIRECT (no proxy)", False))
    if args.mode in ("both", "proxy"):
        modes.append(("PROXY", True))

    if any(use_proxy for _, use_proxy in modes):
        missing_proxy = [
            key for key in ("DECODO_PROXY_URL", "DECODO_PROXY_USERNAME", "DECODO_PROXY_PASSWORD")
            if not os.getenv(key, "").strip()
        ]
        if missing_proxy:
            print(f"Missing proxy env vars for proxy diagnostics: {', '.join(missing_proxy)}")
            return 2

    for label, use_proxy in modes:
        for i in range(1, args.attempts + 1):
            run_label = f"{label} - attempt {i}/{args.attempts}"
            result = run_playwright_attempt(
                username=username,
                since_id=args.since_id,
                use_proxy=use_proxy,
                proxies=proxy_dict,
                headless=headless,
            )
            print_result(run_label, result)

    print("\nInterpretation quick guide:")
    print("- direct ok + proxy fail => proxy path issue")
    print("- direct fail + proxy fail + cloudflare_detected => broad WAF blocking")
    print("- proxy IP rotates but always fails => proxy pool likely blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
