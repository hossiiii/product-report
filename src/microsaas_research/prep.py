"""Claude スキル実行前の機械的 enrichment。

candidate プールに対して PH 単発取得（topics/makers/comments/media/long_desc）と
landing fetch（meta/text/pricing_signals）を行い、結果を data/enriched/<ph_id>.json
に書き出す。AI フィールド（description_ja / summary_ja / review_guide_ja /
japan_fit）は触らない — それらは Claude スキルが後段で埋める。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from . import landing, producthunt, storage
from .report import _fetch_candidates


def _strip_query(url: str | None) -> str | None:
    if not url:
        return None
    return url.split("?", 1)[0]


def _prep_ph(row: dict) -> bool:
    """PH 単発取得。in-memory row と enriched ファイルを更新。"""
    if row.get("ph_enriched_at"):
        return False
    post = producthunt.fetch_post(row["ph_id"])
    if not post:
        return False
    topics = [
        e["node"]["name"]
        for e in (post.get("topics") or {}).get("edges", [])
        if e.get("node", {}).get("name")
    ]
    makers = post.get("makers") or []
    top_comments = [
        {
            "body": e["node"].get("body", ""),
            "votesCount": e["node"].get("votesCount", 0),
            "user": (e["node"].get("user") or {}).get("name"),
        }
        for e in (post.get("comments") or {}).get("edges", [])
    ]
    long_desc = post.get("description") or row.get("long_description")
    featured_at = post.get("featuredAt")
    thumbnail_url = _strip_query((post.get("thumbnail") or {}).get("url"))
    media_items = [
        {"type": m.get("type"), "url": _strip_query(m.get("url"))}
        for m in (post.get("media") or [])
        if m.get("url")
    ]
    updates: dict[str, Any] = {
        "topics": topics,
        "makers": makers,
        "top_comments": top_comments,
        "long_description": long_desc,
        "featured_at": featured_at,
        "thumbnail_url": thumbnail_url,
        "media": media_items,
        "ph_enriched_at": datetime.now().isoformat(timespec="seconds"),
    }
    row.update(updates)
    storage.merge_enriched(row["ph_id"], **updates)
    return True


def _prep_landing(row: dict) -> bool:
    if row.get("landing_fetched_at"):
        return False
    target = row.get("website") or row.get("ph_url")
    if not target:
        return False
    res = landing.fetch(target)
    if not res:
        return False
    updates = {
        "landing_meta": res.get("landing_meta"),
        "landing_text": res.get("landing_text"),
        "pricing_signals": res.get("pricing_signals") or [],
        "landing_fetched_at": datetime.now().isoformat(timespec="seconds"),
    }
    row.update(updates)
    storage.merge_enriched(row["ph_id"], **updates)
    return True


def _seed_base_fields(row: dict) -> None:
    """jsonl の name / description / ph_url / website / launched_at /
    upvotes / comments を enriched ファイルにも書いておく（スキル側で再利用するため）。"""
    base = {
        "name": row.get("name"),
        "description": row.get("description"),
        "ph_url": row.get("ph_url"),
        "website": row.get("website"),
        "launched_at": row.get("launched_at"),
        "upvotes": row.get("upvotes"),
        "comments": row.get("comments"),
    }
    storage.merge_enriched(row["ph_id"], **base)


def prep(week: str, candidates: int = 30) -> tuple[int, int]:
    """candidates 件分の PH 詳細 + landing を取得。
    Returns: (PH 詳細取得件数, landing 取得件数)
    """
    rows = _fetch_candidates(week, pool=candidates)
    ph_done = 0
    landing_done = 0
    print(f"[prep] {len(rows)} candidates to prepare", flush=True)
    for i, r in enumerate(rows, 1):
        _seed_base_fields(r)
        if _prep_ph(r):
            ph_done += 1
        if _prep_landing(r):
            landing_done += 1
        print(f"[prep] {i}/{len(rows)} ph={ph_done} landing={landing_done}", flush=True)
    return ph_done, landing_done


def needs_ai(week: str, candidates: int = 30) -> list[str]:
    """AI フィールドが未充足の ph_id を返す。advisor_view_at（最終ステップ）で判定。"""
    rows = _fetch_candidates(week, pool=candidates)
    missing = []
    for r in rows:
        enriched = storage.load_enriched(r["ph_id"])
        if not enriched.get("advisor_view_at"):
            missing.append(str(r["ph_id"]))
    return sorted(missing)


def reset_ai_fields(week: str, candidates: int = 30) -> int:
    """candidate プールの enriched から AI 生成フィールドを削除して再評価可能にする。
    PH 詳細・landing 等の機械的データは温存。"""
    ai_keys = {
        "description_ja",
        "summary_ja",
        "review_guide_ja",
        "review_guide_at",
        "japan_fit",
        "japan_fit_at",
        "business_viability",
        "business_viability_at",
        "advisor_view",
        "advisor_view_at",
        "overall_score",
    }
    rows = _fetch_candidates(week, pool=candidates)
    reset_count = 0
    for r in rows:
        enriched = storage.load_enriched(r["ph_id"])
        if not enriched:
            continue
        before = set(enriched)
        cleaned = {k: v for k, v in enriched.items() if k not in ai_keys}
        if set(cleaned) != before:
            storage.save_enriched(r["ph_id"], cleaned)
            reset_count += 1
    return reset_count


def verify(week: str, candidates: int = 30) -> tuple[bool, list[str]]:
    """週次サイクル仕上げの最終検証。
    すべての candidate に japan_fit があり、JSON schema にも適合することを確認。
    """
    from .schemas import validate_enriched

    rows = _fetch_candidates(week, pool=candidates)
    issues = []
    for r in rows:
        enriched = storage.load_enriched(r["ph_id"])
        if not enriched:
            issues.append(f"{r['ph_id']}: enriched ファイルなし")
            continue
        errs = validate_enriched(enriched)
        for e in errs:
            issues.append(f"{r['ph_id']}: {e}")
    return (not issues, issues)
