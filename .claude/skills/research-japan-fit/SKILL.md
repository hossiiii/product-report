---
name: research-japan-fit
description: Product Hunt から週次トレンドを取得し、各プロダクトの日本市場適合度を WebSearch で深掘り調査して TOP20 レポートを生成、commit & push する。
---

# research-japan-fit

このスキルは Product Hunt から週次トレンドを取得し、Top30 候補それぞれの
日本市場適合度を WebSearch で能動的に調査して、TOP20 を選び抜いた MD レポートを
生成し、リポジトリに commit & push する。

ユーザーがこのスキルを呼び出した時点で、collect / enrich / report / git push の
完全自動実行が承認されたものとする。途中で確認は求めない。
（ただし git push で auth / conflict / network エラーが出た場合は中断して報告）

## 前提

- 作業ディレクトリ: `/Users/kentahoshikawa/code/product-report`
- 環境: `.env` に `PRODUCT_HUNT_TOKEN` が設定済み
- 依存: `uv sync` 済み

## 実行手順

### Step 0 — 環境確認

```bash
cd /Users/kentahoshikawa/code/product-report
test -f .env || (echo ".env not found" >&2; exit 1)
```

引数で `--week YYYY-Www` を受け取れる。省略時は今週。

```bash
WEEK="${WEEK:-$(date +%G-W%V)}"
CANDIDATES=30
```

### Step 1 — collect

```bash
uv run prr collect
```

PH の post を差分取得して `data/posts/<week>.jsonl` を更新する。
新規ゼロでも続行する。

### Step 2 — prep（PH 詳細 + landing）

```bash
uv run prr prep --week "$WEEK" --candidates "$CANDIDATES"
```

候補プール上位 30 件について、PH 単発取得（topics/makers/comments/long_desc/media）
と landing fetch（meta/text/pricing_signals）を Python が機械的に実行し、
`data/enriched/<ph_id>.json` の初期データを作る。AI フィールドはまだ空。

### Step 3 — AI 未充足の ph_id を取得

```bash
uv run prr enrich-list --week "$WEEK" --candidates "$CANDIDATES"
```

stdout に 1 行 1 個で ph_id が出る。これが Claude が調査する対象。
（すでに japan_fit_at が立っているものはキャッシュ済みなのでスキップされる）

### Step 4 — 各 ph_id を Agent 並列で調査

未充足 ph_id を **5 件ずつのバッチ** に分け、1 メッセージで複数 Agent を並列起動する
（並列上限の目安: 同時 5 件、つまり 30 件なら 6 バッチを順次）。

各 Agent への指示は以下の固定テンプレ：

> ファイル `.claude/skills/research-japan-fit/RESEARCH_PROMPT.md` の内容を読み、
> その内容を **そのまま** prompt として使う。`{{PH_ID}}` プレースホルダだけを
> 実際の値で置換する。それ以外の改変は禁止（再現性のため）。

Agent 呼び出し仕様：
- `subagent_type: "general-purpose"`
- `description: "Research japan-fit for <ph_id>"`
- `prompt: <上のテンプレに ph_id を埋めたもの>`

各 Agent は WebSearch を最大 5 回まで使い、JSON を該当ファイルに merge-write して
1 行で `ok` または `failed: <理由>` を返す。

### Step 5 — JSON schema 検証

```bash
uv run prr validate-enriched --week "$WEEK" --candidates "$CANDIDATES"
```

exit 1 だった場合、不適合な ph_id だけ Step 4 を **再試行**（最大 2 回まで）。
再試行時は Agent prompt の末尾に以下を追記する：

> 【再試行】前回の試行は JSON schema 不適合で失敗した。
> エラー: <validate の出力>
> 同じファイルを修正して書き戻し、`ok` を返せ。

### Step 6 — 最終検証

```bash
uv run prr verify-week --week "$WEEK" --candidates "$CANDIDATES"
```

exit 0 を確認する。exit 1 ならユーザーに不適合 ph_id 一覧を報告して中断
（push しない）。

### Step 7 — レポート生成

```bash
uv run prr report --week "$WEEK" --candidates "$CANDIDATES" --limit 20
```

`reports/<week>/top20.md` が生成される。

### Step 8 — commit & push

```bash
git add data/ reports/
if git diff --cached --quiet; then
  echo "no changes to commit"
else
  git commit -m "research($WEEK): top20 japan-fit ranking"
  git push
fi
```

push で失敗した場合は中断してユーザーに報告。`--no-verify` や `--force` は禁止。

### Step 9 — ユーザーへの結果報告（1 メッセージ）

以下を 1 メッセージにまとめて返答：

1. 生成された report のパス（`reports/<week>/top20.md`）
2. TOP10 を表形式で:
   ```
   #1  🇯🇵 X/10  verdict   ProductName
   #2  🇯🇵 X/10  verdict   ProductName
   ...
   ```
3. composite_score の分布（例: 8 点以上=3 件 / 7 点=5 件 / 6 点=8 件 / ...）
4. push した場合は最新 commit の hash（`git rev-parse --short HEAD`）
5. 国内既存プレイヤーが発見された件数

長い解説は不要。簡潔に。

## 失敗時の挙動

- **PH API rate limit**: `prr collect` / `prr prep` は内部で自動 retry する。スキル側は気にしない。
- **landing fetch 失敗**: 一部 URL で取れなくても続行（`landing_meta` が「(取得失敗)」になるだけ）。
- **Agent 失敗（ok 以外を返した）**: 該当 ph_id を Step 5 の再試行対象に含める。
- **validate-enriched が 2 回 retry しても通らない**: ユーザーに該当 ph_id とエラーを報告して中断。push しない。
- **git push 失敗**: 中断してユーザーに報告。conflict があれば pull/rebase をユーザーに任せる。

## 再現性ポリシー

- `RESEARCH_PROMPT.md` の中身は加工しない（プレースホルダ置換のみ）
- 候補プールは `decayed_score` 降順で決定的に決まる
- ph_id 昇順で処理（Agent 起動順）
- 既存 `data/enriched/<ph_id>.json` の `japan_fit_at` があれば再評価しない（冪等）

## 関連ファイル

- `RESEARCH_PROMPT.md` — sub-agent への固定プロンプト
- `SCHEMA.json` — JSON schema（`prr export-schema` で再生成可能）
- `src/microsaas_research/schemas.py` — schema 定義の source of truth
- `src/microsaas_research/prep.py` — candidate prep 実装
