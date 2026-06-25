# Evaluation

`runs/` に保存された engine 実行結果を評価するための領域。

まずは評価 schema を固定せず、run 出力を直接見るための viewer を置く。
比較方法や metrics は、engine と run の実態が見えてから設計する。

## Viewer

`runs/` にある各 run の `preview.svg` を、ズーム・パン付きで確認するローカル viewer。

```sh
cd research/scribing-lab/evaluation
uv sync --extra dev
uv run scribing-evaluate view
```

既定では `../runs/` を読む。1 つの run directory だけを見る場合:

```sh
uv run scribing-evaluate view --run ../runs/20260626T123456_example-basic
```

起動後、表示された `http://127.0.0.1:8765/` をブラウザで開く。
