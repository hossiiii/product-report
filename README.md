# Micro-SaaS Trend Research

Product Hunt の launch を週次で取得し、Claude Code のスキル経由で WebSearch を使って日本市場での適合度を深掘り調査する。`/research-japan-fit` を呼ぶだけで TOP20 レポート生成と Git push まで自動で完走する。

API 課金ゼロ（Anthropic サブスクリプション内）、すべてリポジトリ内のファイルで完結。

## GitHub Pages 公開

レポートは `docs/` 配下に静的 HTML として生成され、GitHub Pages 経由で公開できます。

**初回セットアップ（1 回のみ）**:

1. リポジトリを GitHub に push
2. Settings → Pages → Source を `Deploy from a branch` に
3. Branch: `main` / Folder: `/docs` を選択 → Save
4. 数分後 `https://<user>.github.io/<repo>/` で公開

以降は `/research-japan-fit` 実行で `docs/` が自動更新され、push と同時にデプロイされます。

ページ構成:
- `/` トップ → 過去週リスト
- `/<week>/` 週サマリー → TOP20 一覧（概要・総括 1 行 + スコアバッジ）
- `/<week>/<ph_id>.html` プロダクト詳細

## アーキテクチャ

```
[Claude Code]                          [Python]
  /research-japan-fit                   prr collect       PH GraphQL
        │                               prr prep          PH 詳細 + landing
        ├─ Bash ─────────────────►      prr enrich-list   未調査 ph_id 列挙
        │                               prr validate-...  JSON schema 検証
        │                               prr verify-week   最終整合性チェック
        │                               prr report        Jinja2 で MD レンダ
        │
        ├─ Agent 並列 (5x6 batch) ───►  WebSearch + Read/Write
        │                               各 ph_id を独立調査
        │                               data/enriched/<ph_id>.json に書込
        │
        └─ Bash ─────────────────►      git add / commit / push
```

決定的処理は全て Python スクリプト、AI 判断のみ Claude（Opus 4.7）が担当する設計。再現性は JSON schema 検証 + 固定プロンプトテンプレートで担保。

## セットアップ

```bash
cp .env.example .env
# .env の PRODUCT_HUNT_TOKEN を発行: https://api.producthunt.com/v2/oauth/applications

make install
```

## 使い方

Claude Code を起動して：

```
/research-japan-fit
```

これで以下が自動で動く（合計 15-30 分）：

1. PH から差分取得 → `data/posts/<week>.jsonl`
2. 候補プール 30 件の PH 詳細 + landing 取得 → `data/enriched/<ph_id>.json`
3. 各 ph_id を並列 Agent で WebSearch 調査 → JSON マージ書込
4. JSON schema 検証（失敗時は最大 2 回 retry）
5. `reports/<week>/top20.md` 生成
6. `git add / commit / push` （main へ直 push）

## 手動 CLI（スキルを使わない場合）

```bash
make collect                          # PH 増分取得
make prep WEEK=2026-W21 CANDIDATES=30 # PH 詳細 + landing
make enrich-list WEEK=2026-W21        # 未調査 ph_id 一覧
# ... (ここで手動で AI 評価を JSON に埋める or 別ツールに渡す) ...
make validate WEEK=2026-W21           # schema 検証
make verify WEEK=2026-W21             # 最終検証
make report WEEK=2026-W21             # レポート生成
```

## ファイル構成

```
src/microsaas_research/
  cli.py            collect / prep / enrich-list / validate-enriched / verify-week / report / export-schema
  config.py
  storage.py        JSONL/JSON I/O
  producthunt.py    PH GraphQL（collect + fetch_post）
  landing.py        landing GET + bs4 解析
  prep.py           candidate プールの機械的 enrichment
  schemas.py        JSON schema 定義 + 検証
  report.py         Jinja2 レンダリング
  templates/top20.md.j2

.claude/skills/research-japan-fit/
  SKILL.md          orchestration（Claude への指示書）
  RESEARCH_PROMPT.md sub-agent プロンプト（固定テンプレ、改変禁止）
  SCHEMA.json       JSON schema (`prr export-schema` で再生成可能)

data/
  posts/<week>.jsonl       PH 全 post（週単位）
  enriched/<ph_id>.json    候補プールの enrichment データ

reports/<week>/top20.md    最終成果物
```

## 再現性メモ

- 候補プール 30 件は `decayed_score` 降順で決定的に選択
- ph_id 昇順で Agent 起動
- `data/enriched/<ph_id>.json` の `japan_fit_at` が立っていれば再評価しない（冪等）
- JSON schema は `prr export-schema` で `schemas.py` から `SCHEMA.json` に書き出される（手書き禁止）
- プロンプトテンプレートは `RESEARCH_PROMPT.md` に固定（スキル内でインライン生成しない）

## 拡張ポイント

- 別ソース追加（HN, Indie Hackers 等）→ `producthunt.py` を模した collector を追加し、`storage.py` の post 構造を polymorphic に
- スコアリング式の変更 → `schemas.py` の 5 軸 + `RESEARCH_PROMPT.md` の加重を更新
- web 検索結果のキャッシュ → Claude 側に持たせるか、別 JSON ファイルに切り出す
