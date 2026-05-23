"""ランディングページ取得・抜粋・収益シグナル抽出。

各 product の canonical_url を実際に GET し、meta description / og:description /
本文先頭 2000 字 / 価格モデル示唆キーワードを抽出して DB に保存する。
JS-only サイトや 403/Cloudflare で取れない場合は landing_meta に '(取得失敗)' 等を記録。
"""

from __future__ import annotations

import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# 価格モデル示唆のキーワード（小文字で照合）
_PRICING_KEYWORDS = [
    "free trial",
    "free forever",
    "freemium",
    "open source",
    "open-source",
    "self-hosted",
    "self host",
    "lifetime deal",
    "pay once",
    "subscription",
    "monthly plan",
    "yearly plan",
    "pricing",
    "free plan",
    "premium",
]

_PRICE_RE = re.compile(r"\$\s?\d+(?:\.\d+)?(?:\s?/\s?(?:mo|month|yr|year|user))?", re.I)


def _ensure_url(url: str) -> str:
    if "://" not in url:
        return f"https://{url}"
    return url


def _extract_signals(text: str) -> list[str]:
    found: list[str] = []
    lo = text.lower()
    for kw in _PRICING_KEYWORDS:
        if kw in lo and kw not in found:
            found.append(kw)
    for m in _PRICE_RE.findall(text):
        m = m.strip()
        if m not in found:
            found.append(m)
        if len(found) >= 12:
            break
    return found[:12]


def _clean_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript", "svg", "header", "footer", "nav"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text)


def fetch(url: str) -> dict[str, Any] | None:
    """指定 URL の meta / 抜粋 / pricing_signals を返す。失敗時は None。"""
    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=15.0,
            headers={"User-Agent": _BROWSER_UA, "Accept-Language": "en,ja;q=0.8"},
        ) as c:
            r = c.get(_ensure_url(url))
            if r.status_code >= 400:
                return {
                    "landing_meta": f"(取得失敗: HTTP {r.status_code})",
                    "landing_text": None,
                    "pricing_signals": [],
                }
            html = r.text
    except httpx.HTTPError as e:
        return {
            "landing_meta": f"(取得失敗: {type(e).__name__})",
            "landing_text": None,
            "pricing_signals": [],
        }

    soup = BeautifulSoup(html, "lxml")

    title = (soup.title.string or "").strip() if soup.title else ""
    meta = ""
    for sel in [
        ('meta', {"name": "description"}),
        ('meta', {"property": "og:description"}),
        ('meta', {"name": "twitter:description"}),
    ]:
        tag = soup.find(*sel)
        if tag and tag.get("content"):
            meta = tag["content"].strip()
            break

    landing_meta_parts = [p for p in (title, meta) if p]
    landing_meta = " — ".join(landing_meta_parts)[:500] or None

    body_text = _clean_text(soup)[:2000] or None
    signals = _extract_signals(html)
    return {
        "landing_meta": landing_meta,
        "landing_text": body_text,
        "pricing_signals": signals,
    }
