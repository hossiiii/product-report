"""enriched JSON のスキーマ定義と検証ロジック。

Claude 側で生成される JSON フィールドの構造を厳格に固定する。スキル経由で書き戻された
JSON は必ず `validate_enriched` を通すことで、レンダリング段でテンプレが壊れない。

2 層構造:
- japan_fit: 市場機会の評価（5 軸、composite 1-10）
- business_viability: 事業成立性の評価（5 軸、composite 1-10）
- advisor_view: 具体的な事業判断（課金モデル、TAM、GTM、go/no_go 等）
- overall_score: 上記 2 軸の加重平均（市場機会 40% + 事業成立性 60%）
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

_AXIS_SCHEMA = {
    "type": "object",
    "required": ["score", "reason"],
    "properties": {
        "score": {"type": "integer", "minimum": 1, "maximum": 10},
        "reason": {"type": "string", "maxLength": 300},
    },
}

ENRICHED_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "description_ja",
        "summary_ja",
        "tldr_ja",
        "review_guide_ja",
        "japan_fit",
        "business_viability",
        "advisor_view",
        "overall_score",
    ],
    "properties": {
        "description_ja": {"type": "string", "minLength": 10, "maxLength": 200},
        "summary_ja": {"type": "string", "minLength": 20, "maxLength": 400},
        "tldr_ja": {"type": "string", "minLength": 30, "maxLength": 200},
        "overall_score": {"type": "integer", "minimum": 1, "maximum": 10},
        "review_guide_ja": {
            "type": "object",
            "required": ["what", "for_who", "reproducibility", "signals", "concerns"],
            "properties": {
                "what": {"type": "string", "maxLength": 600},
                "for_who": {"type": "string", "maxLength": 300},
                "reproducibility": {
                    "type": "object",
                    "required": ["level", "reason"],
                    "properties": {
                        "level": {"enum": ["easy", "medium", "hard"]},
                        "reason": {"type": "string", "maxLength": 200},
                    },
                },
                "signals": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 5,
                    "items": {"type": "string"},
                },
                "concerns": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 5,
                    "items": {"type": "string"},
                },
            },
        },
        "japan_fit": {
            "type": "object",
            "required": [
                "japan_fit_score",
                "verdict",
                "axes",
                "opportunity",
                "rationale",
            ],
            "properties": {
                "japan_fit_score": {"type": "integer", "minimum": 1, "maximum": 10},
                "verdict": {"enum": ["build", "watch", "skip", "no_fit"]},
                "axes": {
                    "type": "object",
                    "required": [
                        "demand",
                        "competition",
                        "regulation",
                        "localization",
                        "business_custom",
                    ],
                    "properties": {
                        "demand": _AXIS_SCHEMA,
                        "competition": _AXIS_SCHEMA,
                        "regulation": _AXIS_SCHEMA,
                        "localization": _AXIS_SCHEMA,
                        "business_custom": _AXIS_SCHEMA,
                    },
                },
                "existing_competitors_jp": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["name", "note"],
                        "properties": {
                            "name": {"type": "string"},
                            "url": {"type": "string"},
                            "note": {"type": "string", "maxLength": 200},
                        },
                    },
                },
                "regulatory_findings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["law", "impact"],
                        "properties": {
                            "law": {"type": "string"},
                            "impact": {"type": "string", "maxLength": 300},
                        },
                    },
                },
                "opportunity": {"type": "string", "maxLength": 500},
                "rationale": {"type": "string", "maxLength": 700},
            },
        },
        "business_viability": {
            "type": "object",
            "required": ["business_viability_score", "axes", "rationale"],
            "properties": {
                "business_viability_score": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                },
                "axes": {
                    "type": "object",
                    "required": [
                        "monetization",
                        "market_size",
                        "gtm",
                        "timing",
                        "solo_ops",
                    ],
                    "properties": {
                        "monetization": _AXIS_SCHEMA,
                        "market_size": _AXIS_SCHEMA,
                        "gtm": _AXIS_SCHEMA,
                        "timing": _AXIS_SCHEMA,
                        "solo_ops": _AXIS_SCHEMA,
                    },
                },
                "rationale": {"type": "string", "maxLength": 700},
            },
        },
        "advisor_view": {
            "type": "object",
            "required": [
                "recommended_pricing",
                "reachable_market_jp",
                "recommended_gtm",
                "time_window_months",
                "solo_dev_continuable",
                "critical_risks",
                "go_no_go",
            ],
            "properties": {
                "recommended_pricing": {
                    "type": "object",
                    "required": ["model", "arpu_jpy", "plans"],
                    "properties": {
                        "model": {
                            "enum": [
                                "monthly",
                                "annual",
                                "one_time",
                                "usage",
                                "freemium",
                                "open_source",
                            ]
                        },
                        "arpu_jpy": {"type": "integer", "minimum": 0},
                        "plans": {
                            "type": "array",
                            "maxItems": 5,
                            "items": {"type": "string", "maxLength": 200},
                        },
                    },
                },
                "reachable_market_jp": {
                    "type": "object",
                    "required": [
                        "target_segment",
                        "target_count",
                        "capture_pct_year3",
                        "monthly_revenue_target_jpy",
                    ],
                    "properties": {
                        "target_segment": {"type": "string", "maxLength": 300},
                        "target_count": {"type": "integer", "minimum": 0},
                        "capture_pct_year3": {"type": "number", "minimum": 0, "maximum": 100},
                        "monthly_revenue_target_jpy": {"type": "integer", "minimum": 0},
                    },
                },
                "recommended_gtm": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 6,
                    "items": {"type": "string", "maxLength": 200},
                },
                "time_window_months": {"type": "integer", "minimum": 0, "maximum": 120},
                "solo_dev_continuable": {"enum": ["yes", "hard", "no"]},
                "critical_risks": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 5,
                    "items": {"type": "string", "maxLength": 250},
                },
                "go_no_go": {"enum": ["go", "consider", "no_go"]},
            },
        },
    },
}


def export_schema(path: Path) -> None:
    """Skill 側から参照する用に JSON ファイルへ書き出す。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(ENRICHED_SCHEMA, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def validate_enriched(data: dict) -> list[str]:
    """enriched dict を検証してエラーメッセージのリストを返す。空なら適合。"""
    validator = jsonschema.Draft7Validator(ENRICHED_SCHEMA)
    errors = []
    for err in sorted(validator.iter_errors(data), key=lambda e: e.path):
        loc = ".".join(str(p) for p in err.absolute_path) or "<root>"
        errors.append(f"{loc}: {err.message}")
    return errors
