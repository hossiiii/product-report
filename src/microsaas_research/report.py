from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import storage
from .config import settings

_TEMPLATES = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(_TEMPLATES),
    autoescape=select_autoescape(default=False),
    keep_trailing_newline=True,
)


def _iso_week_bounds(week: str) -> tuple[datetime, datetime]:
    year_str, week_str = week.split("-W")
    year, w = int(year_str), int(week_str)
    monday = datetime.fromisocalendar(year, w, 1).replace(tzinfo=UTC)
    return monday, monday + timedelta(days=7)


def _decayed(upvotes: int, age_days: float) -> float:
    return float(upvotes) * math.exp(-age_days / 14.0)


def _fetch_candidates(week: str, pool: int) -> list[dict]:
    posts = storage.load_posts(week)
    if not posts:
        return []
    week_start, week_end = _iso_week_bounds(week)
    now = datetime.now(tz=UTC)

    rows: list[dict] = []
    for p in posts:
        launched = datetime.fromisoformat(p["launched_at"].replace("Z", "+00:00"))
        if not (week_start <= launched < week_end):
            continue
        upvotes = int(p.get("upvotes") or 0)
        age_days = max(0.0, (now - launched).total_seconds() / 86400.0)
        row = dict(p)
        row["total_upvotes"] = upvotes
        row["total_comments"] = int(p.get("comments") or 0)
        row["decayed_score"] = _decayed(upvotes, age_days)
        row["first_seen"] = launched
        row["last_seen"] = launched
        rows.append(row)

    rows.sort(key=lambda r: r["decayed_score"], reverse=True)
    top = rows[:pool]
    for r in top:
        r.update(storage.load_enriched(r["ph_id"]))
    return top


_GO_NO_GO_RANK = {"go": 2, "consider": 1, "no_go": 0}


def _overall_score(row: dict) -> int:
    try:
        return int(row.get("overall_score") or 0)
    except (TypeError, ValueError):
        return 0


def _go_rank(row: dict) -> int:
    av = row.get("advisor_view") or {}
    return _GO_NO_GO_RANK.get(av.get("go_no_go"), -1)


def _jp_score(row: dict) -> int:
    jf = row.get("japan_fit") or {}
    try:
        return int(jf.get("japan_fit_score") or 0)
    except (TypeError, ValueError):
        return 0


def generate(week: str, limit: int = 20, candidates: int = 30) -> Path:
    rows = _fetch_candidates(week, pool=candidates)
    # overall_score 降順 → go_no_go 優先度 → japan_fit_score → decayed_score でソート
    rows.sort(
        key=lambda r: (
            _overall_score(r),
            _go_rank(r),
            _jp_score(r),
            r.get("decayed_score", 0.0),
        ),
        reverse=True,
    )
    rows = rows[:limit]
    template = _env.get_template("top20.md.j2")
    text = template.render(
        week=week,
        rows=rows,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
    out_dir = settings.reports_dir / week
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "top20.md"
    out_path.write_text(text, encoding="utf-8")
    return out_path
