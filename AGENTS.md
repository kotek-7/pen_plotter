# AGENTS.md

## プロジェクト概要

このリポジトリは、プレーンテキストを xDraw A4 ペンプロッタ向けの G-code に変換し、
必要に応じて Windows 側の Tkinter GUI から送信するための軽量 Python アプリケーションです。

中心の流れは次の 1 本です。

```text
text -> font outline strokes in paper mm -> G-code -> xDraw A4 sender
```

このアプリはテキストから G-code を作る処理と、生成済み G-code の送信だけを扱います。

## 技術スタック

- Python 3.11+
- パッケージ管理: `uv`
- ストローク生成: Matplotlib `TextPath`
- 数値処理: NumPy
- 実機通信: pyserial, GRBL 互換 xDraw A4
- 送信 GUI: Tkinter
- テスト: pytest
- リント/フォーマット: ruff

## 主要コマンド

```sh
make gcode TEXT="Hello"
make preview TEXT="Hello"
make sender
make test
make lint
make format
```

直接実行する場合:

```sh
python scripts/text_to_gcode.py --text "Hello" -o output.gcode --preview preview.png
python scripts/run_plotter_gui.py
python -m src.plotter_gui
```

## ディレクトリ構成

- `src/textplot/`: テキストから紙面 mm 座標ストロークを生成する軽量コア
- `src/gcode/`: xDraw A4 用 G-code 生成、順序最適化、プレビュー
- `src/comm/`: GRBL シリアル通信、ポート検出
- `src/plotter_gui/`: `.gcode` ファイル送信用 Tkinter GUI
- `scripts/`: CLI 入口
- `tests/`: pytest テスト
- `docs/`: 実機 GUI のチェックリスト
- `research/scribing-lab/`: 手書きと判別されにくい日本語筆記生成の独立研究プロジェクト

## 座標系

- `src/textplot` の出力: Y-UP, 単位 mm, A4 左下 `(0, 0)`, 右上 `(210, 297)`
- `src/gcode` の入力: Y-UP, 単位 mm
- xDraw A4 紙座標: Y-UP, 左下 `(0, 0)`, 右上 `(210, 297)`

プレビューで `invert_yaxis()` は使わないでください。

## xDraw A4 / GRBL 注意

- USB: CH340
- ボーレート: 115200
- ペン制御は Z 軸です。M3/M5 ではありません。
- ペンアップ: `G1G90 Z0.5 F5000`
- ペンダウン: `G1G90 Z3.5 F5000`
- ホーミング: `$H`
- ホーミング後の紙座標設定: `G92 X0 Y297 Z0`

実機送信 GUI と USB 制御は Windows ネイティブ Python で確認してください。
実機操作を伴う変更では `docs/plotter_gui_checklist.md` を確認し、
危険な自動送信やペンダウン動作を勝手に追加しないでください。

## 開発方針

- 新機能・バグ修正は対応するテストを追加または更新する。
- 実機境界は `src/gcode/`, `src/comm/`, `src/plotter_gui/` に閉じ込める。
- `src/textplot` は G-code 文字列を扱わず、紙面 mm ストロークだけを返す。
- `research/scribing-lab/` は既存 `src/` を実装基盤にしない独立研究領域として扱う。
- 研究プロジェクトの実装・テスト・計画は、原則として対応する `research/scribing-lab/projects/<name>/` 配下にまとめる。
