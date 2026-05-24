"""GitHub Pages 用 HTML を `docs/` 配下に生成。

- `docs/index.html`: 全週リスト（トップ）
- `docs/<week>/index.html`: 週サマリー
- `docs/<week>/<ph_id>.html`: プロダクト詳細
- `docs/styles.css`: 共通 CSS

すべてのページは同じ Jinja2 テンプレ + 共有 CSS から生成される。
過去週も `prr publish` を打てば全件再生成される（フォーマット統一）。
"""

from __future__ import annotations

import re
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import PROJECT_ROOT
from .report import _fetch_candidates, _go_rank, _jp_score, _overall_score

_TEMPLATES = Path(__file__).parent / "templates" / "html"
_env = Environment(
    loader=FileSystemLoader(_TEMPLATES),
    autoescape=select_autoescape(default=True),
    keep_trailing_newline=True,
)

_WEEK_RE = re.compile(r"^\d{4}-W\d{2}$")


def _docs_dir() -> Path:
    return PROJECT_ROOT / "docs"


def _detect_weeks() -> list[str]:
    """reports/<week>/ ディレクトリから生成済み週を列挙（新しい順）。"""
    base = PROJECT_ROOT / "reports"
    if not base.exists():
        return []
    weeks = [p.name for p in base.iterdir() if p.is_dir() and _WEEK_RE.match(p.name)]
    return sorted(weeks, reverse=True)


def _verdict_stats(rows: list[dict]) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for r in rows:
        av = r.get("advisor_view") or {}
        v = av.get("go_no_go") or "unknown"
        counter[v] += 1
    order = ["build", "consider", "no_go", "unknown"]
    return [(k, counter[k]) for k in order if counter[k]]


def _overall_stats(rows: list[dict]) -> list[tuple[int, int]]:
    counter: Counter[int] = Counter()
    for r in rows:
        counter[_overall_score(r)] += 1
    return sorted(counter.items(), reverse=True)


def _build_top_rows(week: str, candidates: int, limit: int) -> list[dict]:
    rows = _fetch_candidates(week, pool=candidates)
    rows.sort(
        key=lambda r: (
            _overall_score(r),
            _go_rank(r),
            _jp_score(r),
            r.get("decayed_score", 0.0),
        ),
        reverse=True,
    )
    return rows[:limit]


def _render(template_name: str, **ctx) -> str:
    tpl = _env.get_template(template_name)
    return tpl.render(**ctx)


def publish(candidates: int = 30, limit: int = 20) -> dict:
    """全週分の HTML を `docs/` に生成して、生成サマリを返す。"""
    docs = _docs_dir()
    docs.mkdir(parents=True, exist_ok=True)
    # CSS
    shutil.copyfile(_TEMPLATES / "styles.css", docs / "styles.css")

    weeks = _detect_weeks()
    week_summaries: list[dict] = []
    generated_count = 0
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    for week in weeks:
        rows = _build_top_rows(week, candidates=candidates, limit=limit)
        if not rows:
            continue
        week_dir = docs / week
        week_dir.mkdir(parents=True, exist_ok=True)

        # week index.html
        verdict_stats = _verdict_stats(rows)
        overall_stats = _overall_stats(rows)
        html = _render(
            "week.html.j2",
            page_title=f"Week {week}",
            css_href="../styles.css",
            home_href="../index.html",
            generated_at=now_str,
            week=week,
            rows=rows,
            verdict_stats=verdict_stats,
            overall_stats=overall_stats,
            candidate_count=candidates,
        )
        (week_dir / "index.html").write_text(html, encoding="utf-8")
        generated_count += 1

        # product pages
        for r in rows:
            ph_id = str(r["ph_id"])
            html = _render(
                "product.html.j2",
                page_title=f"{r.get('name') or ph_id} (Week {week})",
                css_href="../styles.css",
                home_href="../index.html",
                generated_at=now_str,
                week=week,
                r=r,
            )
            (week_dir / f"{ph_id}.html").write_text(html, encoding="utf-8")
            generated_count += 1

        # 週サマリ情報（トップページ用）
        top3 = [
            {
                "name": r.get("name") or r.get("ph_id"),
                "overall_score": _overall_score(r),
                "ph_id": r["ph_id"],
            }
            for r in rows[:3]
        ]
        week_summaries.append({
            "week": week,
            "generated_at": now_str,
            "candidate_count": candidates,
            "limit": limit,
            "verdict_stats": verdict_stats,
            "top3": top3,
        })

    # top index.html
    html = _render(
        "index.html.j2",
        page_title="トップ",
        css_href="styles.css",
        home_href="index.html",
        generated_at=now_str,
        weeks=week_summaries,
    )
    (docs / "index.html").write_text(html, encoding="utf-8")
    generated_count += 1

    return {
        "docs_dir": str(docs),
        "weeks": [w["week"] for w in week_summaries],
        "files_generated": generated_count,
    }


def verify_published(week: str, candidates: int = 30, limit: int = 20) -> tuple[bool, list[str]]:
    """指定週の HTML が揃っているか検証。
    - docs/<week>/index.html
    - docs/<week>/<ph_id>.html × limit
    """
    docs = _docs_dir()
    week_dir = docs / week
    issues = []
    if not (week_dir / "index.html").exists():
        issues.append(f"missing: {week}/index.html")
    rows = _build_top_rows(week, candidates=candidates, limit=limit)
    for r in rows:
        ph_id = str(r["ph_id"])
        if not (week_dir / f"{ph_id}.html").exists():
            issues.append(f"missing: {week}/{ph_id}.html")
    if not (docs / "styles.css").exists():
        issues.append("missing: styles.css")
    if not (docs / "index.html").exists():
        issues.append("missing: index.html")
    return (not issues, issues)
