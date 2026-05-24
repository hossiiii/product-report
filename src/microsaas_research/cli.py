from __future__ import annotations

from datetime import datetime
from typing import Annotated

import typer

from . import prep as prep_module
from . import producthunt, report, storage
from . import publish as publish_module
from .config import settings
from .schemas import export_schema, validate_enriched

app = typer.Typer(help="Micro-SaaS trend research CLI")


def _default_week() -> str:
    now = datetime.now()
    iso = now.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


@app.command("collect")
def collect(
    since_days: Annotated[
        int | None,
        typer.Option("--since-days", help="過去 N 日分を取得（省略時は直近 jsonl の最大 launched_at 以降）"),
    ] = None,
) -> None:
    """Product Hunt から取得して data/posts/<week>.jsonl にマージ。"""
    inserted = producthunt.collect(since_days=since_days)
    typer.echo(f"collected: {inserted} new posts")


@app.command("prep")
def prep_cmd(
    week: Annotated[str, typer.Option("--week")] = "",
    candidates: Annotated[int, typer.Option("--candidates")] = 30,
) -> None:
    """candidate プールに対して PH 詳細 + landing を機械的に取得（AI は呼ばない）。"""
    week = week or _default_week()
    ph_done, landing_done = prep_module.prep(week, candidates=candidates)
    typer.echo(f"prep done: ph_enriched +{ph_done}, landing +{landing_done}")


@app.command("reset-ai")
def reset_ai_cmd(
    week: Annotated[str, typer.Option("--week")] = "",
    candidates: Annotated[int, typer.Option("--candidates")] = 30,
) -> None:
    """candidate の AI 生成フィールドを削除（PH/landing は温存）。スキーマ変更時等に。"""
    week = week or _default_week()
    n = prep_module.reset_ai_fields(week, candidates=candidates)
    typer.echo(f"reset AI fields in {n} file(s)")


@app.command("enrich-list")
def enrich_list(
    week: Annotated[str, typer.Option("--week")] = "",
    candidates: Annotated[int, typer.Option("--candidates")] = 30,
) -> None:
    """AI 未充足の ph_id を 1 行 1 個で stdout に出す（Claude スキル向け）。"""
    week = week or _default_week()
    for ph_id in prep_module.needs_ai(week, candidates=candidates):
        typer.echo(ph_id)


@app.command("validate-enriched")
def validate_enriched_cmd(
    week: Annotated[str, typer.Option("--week")] = "",
    candidates: Annotated[int, typer.Option("--candidates")] = 30,
) -> None:
    """enriched JSON 全件を JSON schema で検証。NG があれば exit 1。"""
    week = week or _default_week()
    from .report import _fetch_candidates

    rows = _fetch_candidates(week, pool=candidates)
    bad = 0
    for r in rows:
        enriched = storage.load_enriched(r["ph_id"])
        if not enriched:
            typer.echo(f"{r['ph_id']}: missing")
            bad += 1
            continue
        errs = validate_enriched(enriched)
        for e in errs:
            typer.echo(f"{r['ph_id']}: {e}")
        if errs:
            bad += 1
    if bad:
        typer.echo(f"{bad} enriched file(s) invalid", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"ok: {len(rows)} files valid")


@app.command("verify-week")
def verify_week(
    week: Annotated[str, typer.Option("--week")] = "",
    candidates: Annotated[int, typer.Option("--candidates")] = 30,
) -> None:
    """push 直前の最終検証。candidate 全件に japan_fit があり schema 適合か確認。"""
    week = week or _default_week()
    ok, issues = prep_module.verify(week, candidates=candidates)
    for line in issues:
        typer.echo(line)
    if not ok:
        typer.echo(f"verify failed: {len(issues)} issue(s)", err=True)
        raise typer.Exit(code=1)
    typer.echo("verify ok")


@app.command("export-schema")
def export_schema_cmd() -> None:
    """スキル参照用に SCHEMA.json を最新化。"""
    out = settings.skill_schema_path
    export_schema(out)
    typer.echo(f"schema exported: {out}")


@app.command("publish")
def publish_cmd(
    candidates: Annotated[int, typer.Option("--candidates")] = 30,
    limit: Annotated[int, typer.Option("--limit")] = 20,
) -> None:
    """全週の HTML を docs/ に生成（GitHub Pages 公開ルート）。"""
    result = publish_module.publish(candidates=candidates, limit=limit)
    typer.echo(f"published: {result['files_generated']} files for {len(result['weeks'])} week(s)")


@app.command("verify-published")
def verify_published_cmd(
    week: Annotated[str, typer.Option("--week")] = "",
    candidates: Annotated[int, typer.Option("--candidates")] = 30,
    limit: Annotated[int, typer.Option("--limit")] = 20,
) -> None:
    """指定週の HTML が docs/ に揃っているか検証。"""
    week = week or _default_week()
    ok, issues = publish_module.verify_published(week, candidates=candidates, limit=limit)
    for line in issues:
        typer.echo(line)
    if not ok:
        typer.echo(f"verify-published failed: {len(issues)} issue(s)", err=True)
        raise typer.Exit(code=1)
    typer.echo("verify-published ok")


@app.command("report")
def report_cmd(
    week: Annotated[str, typer.Option("--week", help="ISO 週 YYYY-Www")] = "",
    limit: Annotated[int, typer.Option("--limit", help="最終レポート件数")] = 20,
    candidates: Annotated[
        int,
        typer.Option(
            "--candidates",
            help="候補プール件数（upvotes 上位 N の中から japan_fit で再ランキング）",
        ),
    ] = 30,
) -> None:
    """週次 MD レポートを生成（enrichment は別途スキルで実行済み前提）。"""
    week = week or _default_week()
    path = report.generate(week, limit=limit, candidates=candidates)
    typer.echo(f"report: {path}")


if __name__ == "__main__":
    app()
