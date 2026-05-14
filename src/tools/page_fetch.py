"""
Headless Chromium fetch for internal research (About / Team / Contact pages).
"""

import logging
import re
from urllib.parse import urlparse

from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from agents import function_tool

logger = logging.getLogger(__name__)

_MAX_DEFAULT = 14_000


def _safe_http_url(url: str) -> str | None:
    u = (url or "").strip()
    if not u.lower().startswith(("http://", "https://")):
        return None
    try:
        p = urlparse(u)
        if p.scheme not in ("http", "https") or not p.netloc:
            return None
    except Exception:
        return None
    return u


@function_tool(strict_mode=False)
async def fetch_url_main_text(url: str, max_chars: int = _MAX_DEFAULT) -> dict:
    """
    Load a page and return visible text (scripts stripped).
    LinkedIn and similar sites may return empty or errors under automation.
    """
    u = _safe_http_url(url)
    if not u:
        return {"url": url, "error": "invalid or non-http(s) URL", "title": "", "text": ""}

    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()
        try:
            await page.goto(u, wait_until="domcontentloaded", timeout=45_000)
            await page.wait_for_timeout(1800)
            await page.evaluate(
                """() => {
                  document.querySelectorAll('script,style,noscript,svg,iframe').forEach(n => n.remove());
                }"""
            )
            title = (await page.title()) or ""
            text = ""
            for sel in ("main", "article", "[role='main']", "#content", "body"):
                loc = page.locator(sel).first
                if await loc.count() == 0:
                    continue
                try:
                    chunk = (await loc.inner_text()).strip()
                except Exception:
                    continue
                if len(chunk) > len(text):
                    text = chunk
            text = re.sub(r"\n{3,}", "\n\n", text)
            return {
                "url": u,
                "final_url": page.url,
                "title": title[:500],
                "text": text[:max_chars],
            }
        except Exception as e:
            logger.warning("fetch_url_main_text failed %s: %s", u, e)
            return {"url": u, "error": str(e), "title": "", "text": ""}
        finally:
            await browser.close()
