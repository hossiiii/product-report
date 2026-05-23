.DEFAULT_GOAL := help
SHELL := /bin/bash
WEEK ?= $(shell date +%G-W%V)
CANDIDATES ?= 30
LIMIT ?= 20

.PHONY: help install collect prep enrich-list validate verify report test fmt lint

help: ## このヘルプを表示
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS=":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## uv sync
	uv sync

collect: ## Product Hunt から増分取得
	uv run prr collect

prep: ## candidate 件分の PH 詳細 + landing を取得（AI なし）
	uv run prr prep --week $(WEEK) --candidates $(CANDIDATES)

enrich-list: ## AI 未充足の ph_id を列挙
	uv run prr enrich-list --week $(WEEK) --candidates $(CANDIDATES)

validate: ## enriched JSON を schema 検証
	uv run prr validate-enriched --week $(WEEK) --candidates $(CANDIDATES)

verify: ## push 直前の最終検証
	uv run prr verify-week --week $(WEEK) --candidates $(CANDIDATES)

report: ## 週次レポート生成
	uv run prr report --week $(WEEK) --candidates $(CANDIDATES) --limit $(LIMIT)

test: ## pytest
	uv run pytest

fmt: ## ruff format
	uv run ruff format .

lint: ## ruff check
	uv run ruff check .
