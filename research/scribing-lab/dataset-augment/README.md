# dataset-augment

`handwriting-collector` で収集した JSONL 筆跡データセットを、小さな幾何変換で水増し
(オフライン augmentation) するツール。学習データが少ない単文字筆記モデル向け。依存なし
(stdlib のみ)。

## 拡張内容

deep-research の指針 (§8) に準拠した保守的な変換を、各サンプルに適用する。

- scale 0.90–1.10 (x/y 独立)
- rotation ±3°
- shear ±0.05
- 点ごとの微小ガウスジッタ (既定 0.3px)

変換は `guide.cell` 中心まわりで行い、文字をセル内に保つ。**平行移動・反転・stroke 順序
変更は行わない**(文字の同一性・構造を保つため)。`t` / `pressure` / stroke 構造 / `guide.cell` /
`char` は保持し、拡張サンプルには `augmentedFrom` と `augment`(適用パラメータ) を付与する。

## 使い方

```sh
cd research/scribing-lab/dataset-augment
uv sync --extra dev
uv run scribe-augment ../handwriting-collector/datasets/handwriting_raw_self_001_hiragana_basic_*.jsonl
```

既定では入力と同じディレクトリに `<stem>.aug4x.jsonl` を出力する (拡張分のみ)。engine の
学習は `datasets/*.jsonl` を glob で拾うため、元ファイルと並べて置けば**元 + 拡張**が
まとめて学習対象になる (既定 copies=4 で 1 字 10→50、計 460→2300。deep-research §9.1 と一致)。

```sh
uv run scribe-augment INPUT.jsonl -o OUT.jsonl --copies 4 --seed 1 \
  --rotate-deg 3 --scale 0.10 --shear 0.05 --jitter 0.3 [--include-originals]
```

拡張結果は `dataset-viewer` でそのままプレビューして確認できる。

## 構成

```text
scribing_dataset_augment/
  cli.py        CLI (scribe-augment)
  augment.py    幾何変換と dataset 拡張ロジック
tests/          件数・構造保持・恒等・決定性のテスト
```
