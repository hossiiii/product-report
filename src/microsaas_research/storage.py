"""ファイルベースのストレージ層。DB の代わりにリポジトリ内 JSON/JSONL を読み書きする。

レイアウト：
  data/posts/YYYY-Www.jsonl   PH の post を ISO 週ごとに 1 行 1 件
  data/enriched/<ph_id>.json  TOP20 入りした post の enrichment キャッシュ
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .config import settings


def iso_week(dt: datetime) -> str:
    iso = dt.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _posts_path(week: str) -> Path:
    return settings.posts_dir / f"{week}.jsonl"


def _enriched_path(ph_id: str) -> Path:
    return settings.enriched_dir / f"{ph_id}.json"


def load_posts(week: str) -> list[dict]:
    path = _posts_path(week)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def save_posts(week: str, posts: list[dict]) -> None:
    path = _posts_path(week)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(json.dumps(p, ensure_ascii=False) for p in posts) + "\n"
    path.write_text(body, encoding="utf-8")


def upsert_posts(new_posts: list[dict]) -> int:
    """週ごとにグルーピングして既存 jsonl にマージ。新規挿入件数を返す。"""
    grouped: dict[str, list[dict]] = {}
    for p in new_posts:
        launched = datetime.fromisoformat(p["launched_at"].replace("Z", "+00:00"))
        grouped.setdefault(iso_week(launched), []).append(p)

    inserted = 0
    for week, items in grouped.items():
        existing = load_posts(week)
        idx = {p["ph_id"]: i for i, p in enumerate(existing)}
        for p in items:
            if p["ph_id"] in idx:
                existing[idx[p["ph_id"]]] = {**existing[idx[p["ph_id"]]], **p}
            else:
                existing.append(p)
                idx[p["ph_id"]] = len(existing) - 1
                inserted += 1
        save_posts(week, existing)
    return inserted


def last_launched_at() -> datetime | None:
    """直近 2 週分の jsonl から最大 launched_at を返す。空なら None。"""
    if not settings.posts_dir.exists():
        return None
    weeks = sorted((p.stem for p in settings.posts_dir.glob("*.jsonl")), reverse=True)
    latest: datetime | None = None
    for week in weeks[:2]:
        for p in load_posts(week):
            dt = datetime.fromisoformat(p["launched_at"].replace("Z", "+00:00"))
            if latest is None or dt > latest:
                latest = dt
    return latest


def load_enriched(ph_id: str) -> dict:
    path = _enriched_path(ph_id)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_enriched(ph_id: str, data: dict) -> None:
    path = _enriched_path(ph_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def merge_enriched(ph_id: str, **updates) -> dict:
    data = load_enriched(ph_id)
    data.update(updates)
    save_enriched(ph_id, data)
    return data
