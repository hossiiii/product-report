from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from . import storage
from .config import settings

GRAPHQL_ENDPOINT = "https://api.producthunt.com/v2/api/graphql"

_QUERY = """
query Posts($after: String, $postedAfter: DateTime) {
  posts(first: 20, after: $after, postedAfter: $postedAfter, order: NEWEST) {
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        id
        name
        tagline
        description
        url
        website
        votesCount
        commentsCount
        createdAt
      }
    }
  }
}
"""

# 単発取得用：1 投稿のリッチ情報（topics / makers / 上位コメント / featuredAt / 画像）
_POST_QUERY = """
query Post($id: ID!) {
  post(id: $id) {
    id
    name
    tagline
    description
    featuredAt
    thumbnail { url }
    media { type url }
    topics(first: 5) { edges { node { name slug } } }
    makers { id name twitterUsername headline }
    comments(first: 3, order: VOTES_COUNT) {
      edges { node { id body votesCount user { name } } }
    }
  }
}
"""


def _client() -> httpx.Client:
    if not settings.product_hunt_token:
        raise RuntimeError(
            "PRODUCT_HUNT_TOKEN is not set. "
            "https://api.producthunt.com/v2/oauth/applications でトークンを発行して "
            ".env / GHA secret に設定してください。"
        )
    return httpx.Client(
        base_url=GRAPHQL_ENDPOINT,
        headers={
            "Authorization": f"Bearer {settings.product_hunt_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=30.0,
    )


_RATE_BUFFER = 500  # 残量がこれを下回ったらリセットまで待つ


def _post(client: httpx.Client, variables: dict[str, Any]) -> tuple[dict[str, Any], httpx.Headers]:
    """1 ページ取得。429 はリセットを待って 1 回だけ自動再試行。"""

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
    def _attempt() -> httpx.Response:
        return client.post("", json={"query": _QUERY, "variables": variables})

    resp = _attempt()
    if resp.status_code == 429:
        body = resp.json() if resp.content else {}
        reset_in = int(resp.headers.get("x-rate-limit-reset") or 0)
        for err in body.get("errors") or []:
            reset_in = max(reset_in, int(err.get("details", {}).get("reset_in") or 0))
        wait = max(reset_in, 30) + 5
        print(f"[producthunt] rate limited; sleeping {wait}s for reset", flush=True)
        time.sleep(wait)
        resp = _attempt()
    resp.raise_for_status()
    payload = resp.json()
    if "errors" in payload:
        raise RuntimeError(f"GraphQL errors: {payload['errors']}")
    return payload["data"], resp.headers


def _maybe_throttle(headers: httpx.Headers) -> None:
    remaining = int(headers.get("x-rate-limit-remaining") or 9999)
    reset_in = int(headers.get("x-rate-limit-reset") or 0)
    if remaining < _RATE_BUFFER and reset_in > 0:
        wait = reset_in + 5
        print(
            f"[producthunt] remaining={remaining} (< {_RATE_BUFFER}); "
            f"sleeping {wait}s until reset",
            flush=True,
        )
        time.sleep(wait)


def _to_post(node: dict[str, Any]) -> dict[str, Any]:
    """GraphQL node → storage 用 dict。"""
    return {
        "ph_id": node["id"],
        "name": node.get("name"),
        "description": node.get("tagline") or node.get("description"),
        "ph_url": node.get("url") or f"https://www.producthunt.com/posts/{node['id']}",
        "website": node.get("website"),
        "launched_at": node["createdAt"],
        "upvotes": node.get("votesCount"),
        "comments": node.get("commentsCount"),
        "raw": node,
    }


def collect(since_days: int | None = None) -> int:
    if since_days is not None:
        posted_after = datetime.now(tz=UTC) - timedelta(days=since_days)
    else:
        last = storage.last_launched_at()
        # 既存データがあれば最新の 1 時間前から、無ければ 7 日（=GHA の週次サイクル幅）。
        posted_after = (last - timedelta(hours=1)) if last else (
            datetime.now(tz=UTC) - timedelta(days=7)
        )

    page_n = 0
    cursor: str | None = None
    buffer: list[dict] = []
    inserted = 0
    flush_every = 10  # ページ単位で逐次保存（rate limit 中断時にも進捗が残る）
    with _client() as client:
        while True:
            data, headers = _post(
                client,
                {"after": cursor, "postedAfter": posted_after.isoformat()},
            )
            page = data["posts"]
            page_n += 1
            for edge in page["edges"]:
                buffer.append(_to_post(edge["node"]))
            remaining = headers.get("x-rate-limit-remaining", "?")
            print(
                f"[producthunt] page {page_n}: +{len(page['edges'])} fetched "
                f"(buffer {len(buffer)}, rate remaining={remaining})",
                flush=True,
            )
            if buffer and (page_n % flush_every == 0):
                inserted += storage.upsert_posts(buffer)
                buffer = []
            if not page["pageInfo"]["hasNextPage"]:
                break
            cursor = page["pageInfo"]["endCursor"]
            _maybe_throttle(headers)
            time.sleep(0.5)
    if buffer:
        inserted += storage.upsert_posts(buffer)
    return inserted


def fetch_post(post_id: str) -> dict | None:
    """単発で 1 PH post の詳細を取得（既存 post を後追い enrich する用途）。"""
    if not settings.product_hunt_token:
        return None
    try:
        with _client() as client:
            resp = client.post("", json={"query": _POST_QUERY, "variables": {"id": post_id}})
            if resp.status_code == 429:
                reset_in = int(resp.headers.get("x-rate-limit-reset") or 60)
                print(f"[producthunt] fetch_post rate limited; sleeping {reset_in + 5}s", flush=True)
                time.sleep(reset_in + 5)
                resp = client.post("", json={"query": _POST_QUERY, "variables": {"id": post_id}})
            resp.raise_for_status()
            payload = resp.json()
            if "errors" in payload:
                print(f"[producthunt] fetch_post errors: {payload['errors']}", flush=True)
                return None
            return payload["data"]["post"]
    except (httpx.HTTPError, RuntimeError) as e:
        print(f"[producthunt] fetch_post failed for {post_id}: {e}", flush=True)
        return None


__all__ = ["collect", "fetch_post"]
