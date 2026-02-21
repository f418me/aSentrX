#!/usr/bin/env python3
"""
Diagnose Truth Social authentication behavior with and without proxy.

This script helps identify whether HTTP 403 responses are caused by:
- account credentials
- proxy credentials/configuration
- proxy IP reputation / WAF blocking

Supports two auth modes:
  1. username/password (default) – performs OAuth token exchange
  2. token (--use-token)         – uses a pre-existing Bearer token from
     TRUTHSOCIAL_TOKEN env var (extract from browser Local Storage key "truth:auth")
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
API_BASE_URL = "https://truthsocial.com/api"
AUTH_URL = f"{BASE_URL}/oauth/token"
VERIFY_URL = f"{API_BASE_URL}/v1/accounts/verify_credentials"
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


def _extract_response(resp, result: dict[str, Any]) -> dict[str, Any]:
    """Fill result dict from a curl_cffi response."""
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
    return result


def run_auth_attempt(use_proxy: bool, proxies: dict[str, str] | None) -> dict[str, Any]:
    """OAuth password-grant auth attempt (original behavior)."""
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
        _extract_response(resp, result)
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"

    return result


def run_token_attempt(use_proxy: bool, proxies: dict[str, str] | None) -> dict[str, Any]:
    """Use a pre-existing Bearer token to call /api/v1/accounts/verify_credentials."""
    from curl_cffi import requests as curl_requests

    token = os.getenv("TRUTHSOCIAL_TOKEN", "").strip()

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
            "GET",
            VERIFY_URL,
            proxies=(proxies if use_proxy else None),
            impersonate="chrome123",
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_2_1) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/123.0.0.0 Safari/537.36",
            },
            timeout=20,
        )
        _extract_response(resp, result)
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
    parser.add_argument(
        "--use-token",
        action="store_true",
        default=False,
        help="Use TRUTHSOCIAL_TOKEN (Bearer token) instead of username/password OAuth flow. "
             "Extract the token from your browser: DevTools → Application → Local Storage "
             "→ truthsocial.com → key 'truth:auth' → copy access_token value.",
    )
    args = parser.parse_args()

    # Match main.py behavior, but ensure the project .env is used regardless of CWD.
    load_dotenv(PROJECT_ROOT / ".env")

    proxy_dict = build_proxy_dict()
    proxy_enabled = proxy_dict is not None

    print("\nTruth Auth Diagnostics")
    print("-" * 90)

    if args.use_token:
        token = os.getenv("TRUTHSOCIAL_TOKEN", "").strip()
        print(f"auth_mode:     TOKEN (Bearer)")
        print(f"token:         {mask_secret(token, keep=6)}")
        if not token:
            print("ERROR: TRUTHSOCIAL_TOKEN is not set in .env")
            print("\nHow to get your token:")
            print("  1. Open https://truthsocial.com in your browser and log in")
            print("  2. Open DevTools (F12 / Cmd+Option+I)")
            print("  3. Go to Application → Local Storage → https://truthsocial.com")
            print("  4. Find the key 'truth:auth'")
            print("  5. Copy the 'access_token' value from the JSON")
            print("  6. Add to .env: TRUTHSOCIAL_TOKEN=your_token_here")
            return 2
    else:
        print(f"auth_mode:     PASSWORD (OAuth)")
        print(f"username:      {mask_secret(os.getenv('TRUTHSOCIAL_USERNAME', ''))}")
        print(f"password:      {mask_secret(os.getenv('TRUTHSOCIAL_PASSWORD', ''))}")
        print(f"client_id:     {mask_secret(os.getenv('TRUTHSOCIAL_CLIENT_ID', ''))}")
        print(f"client_secret: {mask_secret(os.getenv('TRUTHSOCIAL_CLIENT_SECRET', ''))}")

    print(f"proxy_enabled: {proxy_enabled}")
    if proxy_dict:
        print(f"proxy_url:     {sanitize_proxy_url(proxy_dict['http'])}")
    print(f"attempts:      {args.attempts}")
    print(f"endpoint:      {VERIFY_URL if args.use_token else AUTH_URL}")
    print("-" * 90)

    if not args.use_token:
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

    if not args.use_token:
        # Client keys can be provided via ENV; if absent we fall back to truthbrush defaults.
        if not os.getenv("TRUTHSOCIAL_CLIENT_ID", "").strip() or not os.getenv("TRUTHSOCIAL_CLIENT_SECRET", "").strip():
            print("Info: TRUTHSOCIAL_CLIENT_ID/TRUTHSOCIAL_CLIENT_SECRET not fully set in .env; using truthbrush defaults.")

    # Select the right attempt function
    attempt_fn = run_token_attempt if args.use_token else run_auth_attempt

    for label, use_proxy in modes:
        for i in range(1, args.attempts + 1):
            run_label = f"{label} - attempt {i}/{args.attempts}"
            result = attempt_fn(use_proxy=use_proxy, proxies=proxy_dict)
            print_result(run_label, result)

    print("\nInterpretation quick guide:")
    if args.use_token:
        print("- 200 => Token is valid, API access works!")
        print("- 401 => Token is expired or invalid, extract a fresh one from your browser")
        print("- 403 (Cloudflare) => IP/proxy blocked by WAF, token itself may still be valid")
        print("- DIRECT 200 + PROXY 403 => proxy IP blocked")
        print("- DIRECT 403 + PROXY 403 => broad Cloudflare blocking")
    else:
        print("- DIRECT 200 + PROXY 403 => proxy/IP likely blocked")
        print("- DIRECT 403 + PROXY 403 => account/client config issue or broad blocking")
        print("- PROXY rotating IPs but always 403 => proxy pool reputation likely insufficient")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
