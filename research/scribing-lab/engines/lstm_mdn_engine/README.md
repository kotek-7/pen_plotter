# lstm_mdn_engine

char 条件付き LSTM-MDN による日本語単文字筆記生成エンジン（Graves 2013 を日本語かなに適用）。
`handwriting-collector` で収集したオンライン筆跡 (JSONL) を学習し、文字 ID を条件に
`(Δx, Δy, pen)` 系列を自己回帰生成する。runner 契約 `generate(request) -> trajectory` に準拠する。

## モデル

- 入力: `(Δx, Δy, pen one-hot[3])` ＋ 文字埋め込み（各時刻に連結）
- LSTM → MDN ヘッド（M 個の二変量ガウス）＋ pen 3 状態 softmax
- 損失: GMM の NLL ＋ pen の cross-entropy（padding mask 付き）
- 前処理: `guide.cell` 基準で正規化 → 弧長等間隔リサンプル → `Δ` をデータセット標準偏差で標準化
- pressure は不使用（Graves/Sketch-RNN 標準の `(Δx,Δy,pen)` のみ）

PoC 規模（単一筆者・1 字 10 サンプル・計 460）であり、生成の多様性は限定的。

## セットアップ

torch は CPU 版に固定済み（`pyproject.toml` の uv index）。

```sh
cd research/scribing-lab/engines/lstm_mdn_engine
uv sync --extra dev
```

## 学習

```sh
uv run hw-train                       # 既定: ../../handwriting-collector/datasets/*.jsonl
uv run hw-train --epochs 400 --hidden 256 --mixtures 20
```

`data/checkpoint.pt` と `data/stats.json`（語彙・Δ標準偏差・モデル設定）を出力する（gitignore 対象）。

## 生成（確認用 SVG）

```sh
uv run hw-sample --chars "あいうえお" --count 5 --bias 1.0
# -> data/samples/samples.svg （文字×サンプルのグリッド）
```

## runner からの利用

`engine.py` が `generate(request)` を公開する。runner はエンジンをプロセス内に取り込むため、
runner 側の環境に torch が必要（このエンジンは torch を遅延 import する）。

```sh
cd research/scribing-lab
make run TEXT="あいう" NAME=lstm-smoke ENGINE=engines/lstm_mdn_engine
make convert RUN=runs/<run-dir>
```

学習前 (checkpoint 無し) に呼ぶと、学習を促すエラーになる。

## テスト

```sh
uv run pytest          # 前処理形状 / pen 符号化 / MDN 損失が有限・1バッチ overfit
```

## 構成

```text
engine.py            runner 契約 generate(request)
lstm_mdn/
  config.py          ハイパラ・パス・pen 定数
  data.py            JSONL 読込・正規化・リサンプル・系列化
  mdn.py             GMM 損失・サンプリング
  model.py           CharCondLSTMMDN
  train.py           学習ループ (CLI hw-train)
  sample.py          生成・SVG 可視化 (CLI hw-sample)
  sampler.py         自己回帰サンプリング
  trajectory.py      セル座標→紙面 mm canonical trajectory / 確認用 SVG
  artifacts.py       checkpoint 入出力
data/                checkpoint.pt / stats.json / samples/ (gitignore)
```
