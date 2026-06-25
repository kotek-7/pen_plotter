.PHONY: help sync run render export convert view test lint format

# Makefile 自身の位置を基準にするため、どの cwd から呼んでも動く。
ROOT := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))
PROJECTS := renderer exporter runner evaluation

TEXT ?=
NAME ?=
SEED ?=
ENGINE ?=
RUN ?=

help: ## ヘルプを表示
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

sync: ## 全 project を uv sync
	@for d in $(PROJECTS); do echo ">> $$d"; (cd $(ROOT)/$$d && uv sync --extra dev) || exit 1; done

run: ## engine を実行し trajectory を生成 (TEXT=... [NAME=...] [SEED=...] [ENGINE=...])
	@[ -n "$(TEXT)" ] || { echo "TEXT=... が必要です"; exit 1; }
	cd $(ROOT)/runner && uv run scribe-run "$(TEXT)" \
		$(if $(ENGINE),--engine $(abspath $(ENGINE)),) \
		$(if $(SEED),--seed $(SEED),) \
		$(if $(NAME),--name $(NAME),)

render: ## RUN の trajectory から preview.svg を生成 (RUN=<run dir>)
	@[ -n "$(RUN)" ] || { echo "RUN=<run dir> が必要です"; exit 1; }
	cd $(ROOT)/renderer && uv run scribe-render "$(abspath $(RUN))"

export: ## RUN の trajectory から output.gcode/safety.json を生成 (RUN=<run dir>)
	@[ -n "$(RUN)" ] || { echo "RUN=<run dir> が必要です"; exit 1; }
	cd $(ROOT)/exporter && uv run scribe-export "$(abspath $(RUN))"

convert: render export ## RUN を preview と gcode の両方へ変換 (RUN=<run dir>)

view: ## run preview viewer を起動 ([RUN=<run dir>])
	cd $(ROOT)/evaluation && uv run scribe-view $(if $(RUN),$(abspath $(RUN)),)

test: ## 全 project の pytest
	@for d in $(PROJECTS); do echo ">> $$d"; (cd $(ROOT)/$$d && uv run pytest -q) || exit 1; done

lint: ## 全 project の ruff check
	@for d in $(PROJECTS); do echo ">> $$d"; (cd $(ROOT)/$$d && uv run ruff check .) || exit 1; done

format: ## 全 project の ruff format
	@for d in $(PROJECTS); do echo ">> $$d"; (cd $(ROOT)/$$d && uv run ruff format .) || exit 1; done
