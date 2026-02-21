import html
import logging
import time
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from playwright_stealth import Stealth


logger = logging.getLogger("aSentrX.PlaywrightClient")


class PlaywrightTruthClient:
    """Fetch public Truth Social statuses using browser automation."""

    def __init__(self, proxy_config: dict | None = None, headless: bool = True, timeout_ms: int = 60000):
        self.proxy_config = proxy_config
        self.headless = headless
        self.timeout_ms = timeout_ms

    def _build_playwright_proxy(self) -> dict | None:
        if not self.proxy_config:
            return None
        # Accept both shapes:
        # 1) {"proxies": {"http": "...", "https": "..."}}
        # 2) {"http": "...", "https": "..."} (used by diagnostics script)
        if "proxies" in self.proxy_config:
            proxy_url = self.proxy_config["proxies"]["http"]
        else:
            proxy_url = self.proxy_config["http"]
        parsed = urlsplit(proxy_url)
        proxy: dict[str, str] = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
        if parsed.username:
            proxy["username"] = parsed.username
        if parsed.password:
            proxy["password"] = parsed.password
        return proxy

    @staticmethod
    def _is_cloudflare_challenge(title: str, body: str) -> bool:
        """Detect Cloudflare challenge pages using multiple indicators."""
        title_lower = title.lower()
        body_lower = body.lower()
        cf_title_patterns = ["attention required", "just a moment", "access denied", "please wait"]
        cf_body_patterns = [
            "cloudflare", "cf-challenge", "cf-turnstile", "cf-browser-verification",
            "challenge-platform", "ray id", "_cf_chl",
        ]
        if any(p in title_lower for p in cf_title_patterns):
            return True
        if any(p in body_lower for p in cf_body_patterns):
            return True
        return False

    def pull_statuses(self, username: str, replies: bool = False, verbose: bool = False, since_id: str | None = None):
        del replies  # Public timeline page already filters to visible posts.

        url = f"https://truthsocial.com/@{username}"
        proxy = self._build_playwright_proxy()

        with Stealth().use_sync(sync_playwright()) as p:
            browser = p.chromium.launch(
                headless=self.headless,
                proxy=proxy,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
                locale="en-US",
            )
            page = context.new_page()
            page.set_default_timeout(self.timeout_ms)
            try:
                page.goto(url, wait_until="domcontentloaded")

                # Smart wait: try to detect when actual content has loaded,
                # falling back to a short static wait if no selector appears.
                try:
                    page.wait_for_selector(
                        'article, [data-testid="status"], div[class*="status"]',
                        timeout=8000,
                    )
                except PlaywrightTimeout:
                    # Selector not found – page may still be loading or is a challenge page.
                    page.wait_for_timeout(3000)

                title = page.title().lower()
                body = page.content()

                if self._is_cloudflare_challenge(title, body):
                    logger.warning(
                        "Cloudflare challenge detected while loading %s", url
                    )
                    raise RuntimeError(
                        "Cloudflare challenge detected while loading timeline"
                    )

                body_lower = body.lower()
                if "something went wrong" in body_lower:
                    raise RuntimeError("Truth Social returned 'Something went wrong' error page")

                statuses = page.evaluate(
                    """
                    async (username) => {
                  const sleep = (ms) => new Promise(r => setTimeout(r, ms));

                  // Primary path: use Truth Social's public web API from browser context.
                  try {
                    const lookupResp = await fetch(
                      `https://truthsocial.com/api/v1/accounts/lookup?acct=${encodeURIComponent(username)}`,
                      { method: 'GET', credentials: 'omit' }
                    );
                    if (lookupResp.ok) {
                      const acct = await lookupResp.json();
                      if (acct && acct.id) {
                        // Retry up to 3 times with exponential back-off for rate limits (429).
                        let statusesResp = null;
                        for (let attempt = 0; attempt < 3; attempt++) {
                          statusesResp = await fetch(
                            `https://truthsocial.com/api/v1/accounts/${acct.id}/statuses?exclude_replies=true&limit=40`,
                            { method: 'GET', credentials: 'omit' }
                          );
                          if (statusesResp.status !== 429) break;
                          await sleep(2000 * (attempt + 1));
                        }
                        if (statusesResp && statusesResp.ok) {
                          const rows = await statusesResp.json();
                          if (Array.isArray(rows)) {
                            return rows.map(r => ({
                              id: String(r.id || ''),
                              created_at: r.created_at || '',
                              content: (typeof r.content === 'string' ? r.content : ''),
                              account: { username: (r.account && r.account.username) ? r.account.username : username },
                            })).filter(r => r.id);
                          }
                        }
                      }
                    }
                  } catch (_) {
                    // Fallback to DOM parsing below.
                  }

                  // Fallback path: parse rendered DOM links.
                  const out = [];
                  const patterns = [
                    new RegExp(`/@${username}/(\\\\d+)`, 'i'),
                    new RegExp(`/@${username}/statuses/(\\\\d+)`, 'i'),
                    new RegExp(`/users/${username}/statuses/(\\\\d+)`, 'i'),
                    new RegExp(`/@${username}/posts/(\\\\d+)`, 'i'),
                  ];
                  const extractId = (href) => {
                    for (const rx of patterns) {
                      const m = href.match(rx);
                      if (m && m[1]) return m[1];
                    }
                    const generic = href.match(/\\/(\\d{8,})$/);
                    return generic ? generic[1] : null;
                  };

                  const links = Array.from(document.querySelectorAll('a[href*="/@"], a[href*="/users/"]'));
                  const seen = new Set();
                  for (const a of links) {
                    const href = a.getAttribute('href') || '';
                    const id = extractId(href);
                    if (!id || seen.has(id)) continue;
                    seen.add(id);
                    const container = a.closest('article') || a.parentElement || a;
                    const timeEl = container.querySelector('time');
                    const createdAt = timeEl ? (timeEl.getAttribute('datetime') || '') : '';
                    const pTexts = Array.from(container.querySelectorAll('p')).map(p => p.innerText.trim()).filter(Boolean);
                    const text = (pTexts.length ? pTexts.join('\\n') : (container.innerText || '')).trim();
                    out.push({
                      id,
                      created_at: createdAt,
                      content: text,
                      account: { username },
                    });
                  }
                  return out;
                    }
                    """,
                    username,
                )
            finally:
                browser.close()

        # Deduplicate by ID and sort newest first.
        unique_by_id: dict[str, dict] = {}
        for st in statuses:
            sid = str(st.get("id"))
            if sid and sid not in unique_by_id:
                unique_by_id[sid] = st

        result = list(unique_by_id.values())
        result.sort(key=lambda s: int(str(s["id"])), reverse=True)

        if since_id:
            try:
                since_int = int(since_id)
                result = [s for s in result if int(str(s["id"])) > since_int]
            except ValueError:
                result = [s for s in result if str(s["id"]) > since_id]

        if verbose:
            logger.debug(f"Playwright fetched {len(result)} statuses from {url}")

        # Keep the same contract as the old client: generator newest->oldest
        for st in result:
            # Keep content parser compatibility by returning HTML-like text field.
            st["content"] = f"<p>{html.escape(st.get('content', ''))}</p>" if st.get("content") else "<p></p>"
            yield st
