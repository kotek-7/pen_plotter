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

`--data` は既定で `../../handwriting-collector/datasets/*.jsonl` を glob する。拡張データ
（`dataset-augment` の出力）を同じ `datasets/` に置けば、元＋拡張がまとめて学習対象になる。

```sh
uv run hw-train --epochs 400 --name aug          # datasets/*.jsonl 全部 (元+拡張) で学習
uv run hw-train --epochs 400 --data "../../handwriting-collector/datasets/*.aug4x.jsonl" --name augonly
```

checkpoint は **日付・名前つき**で `data/checkpoints/<YYYYMMDDTHHMMSS>_<name>.pt`（＋ `.stats.json`）
として出力する（上書きせず学習ごとに別ファイル、gitignore 対象）。`--name` 既定は `model`、
`--out <path>` で保存先を明示指定もできる。

`--epochs` は上限で、**val が改善しないまま `--patience`（既定 40）エポック続くと早期終了**する。
保存されるのは常に最良 val 時点の checkpoint。`--epochs` は大きめにして patience に任せてよい
（`--patience 0` で早期終了を無効化）。

## GPU 学習（別マシン）

学習は device 非依存。`--device`（既定 `auto`＝cuda > mps > xpu > cpu の順で自動選択）で
実行先を選ぶ。漢字込みで規模が大きいので、重い学習は **CUDA マシンで回す想定**。

このリポジトリの torch は CPU 版に固定（`pyproject.toml` の uv index）しているため、CUDA
マシンでは torch を CUDA ビルドに差し替えてから学習する。

```sh
# CUDA マシン側 (例: CUDA 12.4)。pyproject を編集せず差し替える方法:
uv sync --extra dev
uv pip install --reinstall torch --index-url https://download.pytorch.org/whl/cu124
uv run --no-sync hw-train --device cuda \
  --epochs 600 --patience 40 --batch-size 128 --name kanji
#  (恒久的にしたいなら pyproject の torch index を pytorch-cu124 に変えて uv sync でもよい)
```

`--device cuda` 指定時は CUDA を必須化（無ければ torch がエラー）。checkpoint は CPU で
読み戻せる形（`map_location="cpu"`）で保存するので、生成した `.pt` を CPU マシンへ持ち帰れば
そのまま `hw-sample` / runner で推論できる。**推論（generate / engine）は CPU 据え置き**。

## 生成（確認用 SVG）

```sh
uv run hw-sample --chars "あいうえお" --count 5 --bias 1.0     # 既定: 最新 checkpoint
uv run hw-sample --checkpoint 20260627T212527_aug --chars "あ"  # 名前/パス指定
# -> data/samples/samples.svg （文字×サンプルのグリッド）
```

checkpoint の解決順は「パスとして存在 → `data/checkpoints/<名前>(.pt)` → 最新」。`--checkpoint`
省略時は `data/checkpoints/` の最新（無ければ旧 `data/checkpoint.pt`）を使う。

## runner からの利用

`engine.py` が `generate(request)` を公開する。このエンジンは `pyproject.toml` を持つ
uv project なので、runner は**このエンジンの環境でサブプロセス実行**する（torch 等の
依存は engine 側に閉じ、runner 本体には不要）。

```sh
cd research/scribing-lab
make run TEXT="あいう" NAME=lstm-smoke ENGINE=engines/lstm_mdn_engine   # 既定: 最新 checkpoint
make convert RUN=runs/<run-dir>
```

engine は `params` で挙動を変えられる（`checkpoint`＝パス or `data/checkpoints/` 配下の名前で
既定は最新、`bias`、`char_size`、`baseline` など）。`make run` は param 非対応なので、param を
渡すときは runner の `scribe-run --param` を直接使う。

文字配置 (DR Phase5 の layout) は完全分離せず engine 内の軽量レイアウト (`lstm_mdn/layout.py`)
で行う。**サイズ正規化はせず**（字面の大きさはモデル出力の素のまま＝セル正規化 × `char_size`）、
**位置だけ**揃える: box (セル) / baseline (`baseline`＝セル上端からの比率で字面下端を揃える) /
水平中央寄せ / spacing (`advance_ratio`＋`char_spacing`、改行は `line_height`)。bbox は中心・下端の
算出にのみ使い拡縮はしない。

```sh
cd research/scribing-lab/runner
uv run scribe-run "あいう" --engine ../engines/lstm_mdn_engine \
  --param checkpoint=20260627T212527_aug --param bias=2.0 --name lstm-aug
```

学習前 (checkpoint 無し) に呼ぶと、学習を促すエラーになる。未学習のうちは紙面外へはみ出し
`safety` が `ok=False` になることがある（モデル品質の問題で、学習を進めると収束）。未学習のうちは紙面外へ
はみ出し `safety` が `ok=False` になることがある（モデル品質の問題で、学習を進めると収束）。

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
