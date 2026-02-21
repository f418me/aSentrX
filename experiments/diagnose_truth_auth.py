#!/usr/bin/env python3
"""
Diagnose Truth Social authentication behavior with and without proxy.

This script helps identify whether HTTP 403 responses are caused by:
- account credentials
- proxy credentials/configuration
- proxy IP reputation / WAF blocking
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Ensure project imports work when executed from experiments/
sys.path.insert(0, str(Path(__file__).parent.parent))


BASE_URL = "https://truthsocial.com"
AUTH_URL = f"{BASE_URL}/oauth/token"
IPIFY_URL = "https://api.ipify.org?format=json"
PROJECT_ROOT = Path(__file__).parent.parent


def mask_secret(value: str | None, keep: int = 3) -> str:
    if not value:
        return "(empty)"
    if len(value) <= keep:
        return "*" * len(value)
    return f"{value[:keep]}***"


def sanitize_proxy_url(url: str) -> str:
    # Hide inline credentials: http://user:pass@host -> http://host
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
        return str(resp.json().get("ip", "unknown")) if resp.ok else f"ipify-status-{resp.status_code}"
    except Exception as exc:
        return f"ip-check-failed: {type(exc).__name__}: {exc}"


def run_auth_attempt(use_proxy: bool, proxies: dict[str, str] | None) -> dict[str, Any]:
    from curl_cffi import requests as curl_requests
    from truthbrush.api import CLIENT_ID as DEFAULT_CLIENT_ID
    from truthbrush.api import CLIENT_SECRET as DEFAULT_CLIENT_SECRET

    username = os.getenv("TRUTHSOCIAL_USERNAME", "").strip()
    password = os.getenv("TRUTHSOCIAL_PASSWORD", "").strip()
    client_id = os.getenv("TRUTHSOCIAL_CLIENT_ID", DEFAULT_CLIENT_ID).strip()
    client_secret = os.getenv("TRUTHSOCIAL_CLIENT_SECRET", DEFAULT_CLIENT_SECRET).strip()

    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "password",
        "username": username,
        "password": password,
        "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
        "scope": "read",
    }

    result: dict[str, Any] = {
        "use_proxy": use_proxy,
        "ip": get_current_ip(use_proxy, proxies),
        "status_code": None,
        "reason": "",
        "headers": {},
        "body_snippet": "",
        "error": None,
    }

    try:
        resp = curl_requests.request(
            "POST",
            AUTH_URL,
            json=payload,
            proxies=(proxies if use_proxy else None),
            impersonate="chrome123",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=20,
        )
        result["status_code"] = resp.status_code
        result["reason"] = getattr(resp, "reason", "")
        result["headers"] = {
            "server": resp.headers.get("server", ""),
            "cf-ray": resp.headers.get("cf-ray", ""),
            "cf-cache-status": resp.headers.get("cf-cache-status", ""),
            "content-type": resp.headers.get("content-type", ""),
        }

        text = ""
        try:
            text = resp.text or ""
        except Exception:
            text = "<unreadable body>"
        result["body_snippet"] = text[:400].replace("\n", " ")

    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"

    return result


def print_result(label: str, data: dict[str, Any]) -> None:
    print("\n" + "=" * 90)
    print(label)
    print("=" * 90)
    print(f"use_proxy:     {data['use_proxy']}")
    print(f"ip:            {data['ip']}")
    print(f"status_code:   {data['status_code']}")
    print(f"reason:        {data['reason']}")
    print(f"error:         {data['error']}")
    print("headers:")
    for key, value in data["headers"].items():
        print(f"  {key}: {value}")
    print(f"body_snippet:  {data['body_snippet']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose Truth Social auth 403 with and without proxy.")
    parser.add_argument("--attempts", type=int, default=2, help="Attempts per mode (default: 2)")
    parser.add_argument(
        "--mode",
        choices=["both", "direct", "proxy"],
        default="both",
        help="Test mode: both/direct/proxy",
    )
    args = parser.parse_args()

    # Match main.py behavior, but ensure the project .env is used regardless of CWD.
    load_dotenv(PROJECT_ROOT / ".env")

    proxy_dict = build_proxy_dict()
    proxy_enabled = proxy_dict is not None

    print("\nTruth Auth Diagnostics")
    print("-" * 90)
    print(f"username:      {mask_secret(os.getenv('TRUTHSOCIAL_USERNAME', ''))}")
    print(f"password:      {mask_secret(os.getenv('TRUTHSOCIAL_PASSWORD', ''))}")
    print(f"client_id:     {mask_secret(os.getenv('TRUTHSOCIAL_CLIENT_ID', ''))}")
    print(f"client_secret: {mask_secret(os.getenv('TRUTHSOCIAL_CLIENT_SECRET', ''))}")
    print(f"proxy_enabled: {proxy_enabled}")
    if proxy_dict:
        print(f"proxy_url:     {sanitize_proxy_url(proxy_dict['http'])}")
    print(f"attempts:      {args.attempts}")
    print("-" * 90)

    missing_auth = [
        key for key in ("TRUTHSOCIAL_USERNAME", "TRUTHSOCIAL_PASSWORD")
        if not os.getenv(key, "").strip()
    ]
    if missing_auth:
        print(f"Missing required auth env vars in .env: {', '.join(missing_auth)}")
        return 2

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
        proxy_flag = os.getenv("DECODO_PROXY_ENABLED", "False").lower() == "true"
        if not proxy_flag:
            print("Warning: DECODO_PROXY_ENABLED is not True. Proxy mode may not reflect main runtime settings.")
        if missing_proxy:
            print(f"Missing proxy env vars for proxy diagnostics: {', '.join(missing_proxy)}")
            return 2

    # Client keys can be provided via ENV; if absent we fall back to truthbrush defaults.
    if not os.getenv("TRUTHSOCIAL_CLIENT_ID", "").strip() or not os.getenv("TRUTHSOCIAL_CLIENT_SECRET", "").strip():
        print("Info: TRUTHSOCIAL_CLIENT_ID/TRUTHSOCIAL_CLIENT_SECRET not fully set in .env; using truthbrush defaults.")

    for label, use_proxy in modes:
        for i in range(1, args.attempts + 1):
            run_label = f"{label} - attempt {i}/{args.attempts}"
            result = run_auth_attempt(use_proxy=use_proxy, proxies=proxy_dict)
            print_result(run_label, result)

    print("\nInterpretation quick guide:")
    print("- DIRECT 200 + PROXY 403 => proxy/IP likely blocked")
    print("- DIRECT 403 + PROXY 403 => account/client config issue or broad blocking")
    print("- PROXY rotating IPs but always 403 => proxy pool reputation likely insufficient")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
