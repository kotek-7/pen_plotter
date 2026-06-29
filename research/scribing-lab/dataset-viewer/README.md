# dataset-viewer

`handwriting-collector` で収集した JSONL 筆跡データセットを一覧プレビューするツール。
各サンプル（1 行 = 1 文字）のストロークを SVG サムネイルとしてグリッド表示し、文字での
絞り込みとサンプル詳細の確認ができる。`evaluation` の run viewer と同じく、Python 標準
ライブラリの http サーバ + 静的フロントで構成し、依存は持たない。

## 使い方

```sh
cd research/scribing-lab/dataset-viewer
uv sync --extra dev
uv run scribe-dataset-view              # 既定: ../datasets を表示
uv run scribe-dataset-view <dir> -p 8766
```

表示される `http://127.0.0.1:8766/` を開く。

## 機能

- 左: データセット（`*.jsonl`）一覧（writer / charset / サンプル数）
- 中央: 各サンプルのストロークを SVG サムネイルでグリッド表示、`+`/`-` でサイズ調整
- 文字フィルタ: 文字チップで該当サンプルのみ表示
- 右: サムネイルクリックで詳細（拡大表示＋ char / sampleId / strokes / points / t / pressure / canvas / guide.cell）

レンダリングはクライアント側で行う。サーバは `*.jsonl` の一覧（`/api/datasets`）と本体
（`/dataset/<name>`）を返すだけで、ストローク描画はブラウザが担う。

## 構成

```text
scribing_dataset_viewer/
  cli.py        CLI (scribe-dataset-view)
  viewer.py     http サーバ・データセット列挙
  static/       index.html / viewer.css / viewer.js (クライアント描画)
tests/          列挙・ルート解析のテスト
```
