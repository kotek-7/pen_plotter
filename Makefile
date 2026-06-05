.PHONY: gcode preview sender test lint format help

VENV := . .venv/bin/activate &&
TEXT ?= Hello
OUT ?= output.gcode
PREVIEW ?= preview.png

help: ## ヘルプを表示
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

gcode: ## TEXT から G-code を生成
	$(VENV) python scripts/text_to_gcode.py --text "$(TEXT)" --output "$(OUT)"

preview: ## TEXT から G-code とプレビュー画像を生成
	$(VENV) python scripts/text_to_gcode.py --text "$(TEXT)" --output "$(OUT)" --preview "$(PREVIEW)"

sender: ## xDraw A4 送信 GUI を起動
	$(VENV) python scripts/run_plotter_gui.py

test: ## テスト実行
	$(VENV) pytest

lint: ## リント
	$(VENV) ruff check src/ tests/ scripts/

format: ## フォーマット
	$(VENV) ruff format src/ tests/ scripts/
