# Neural Variation Research Plan

## 目的

構造辞書と Sigma-Lognormal だけでは足りない自然な形状変動や writer adaptation を、神経モデルで補助する。

## 背景

RNN、VAE、Transformer はオンライン手書き生成で有効だが、文字構造を直接保証するわけではない。日本語漢字では、生成モデルが画を欠落・崩壊させるリスクがある。そのため主系ではなく、画単位または短画列の variation として使う。

## 主要仮説

1. 画単位 VAE は、文字全体生成より構造破綻が少ない。
2. writer embedding は、明示 profile の推定補助として有効である。
3. Transformer は文脈 spacing には有望だが、MVP には重すぎる。

## スコープ

含む:

- 画単位 VAE/RNN baseline。
- writer embedding 実験。
- structure-constrained sampling。
- neural model と motion model の接続設計。

含まない:

- GAN による画像生成。
- 文字全体を end-to-end で直接生成する方式。
- 評価器回避を目的とした adversarial training。

## 実験

### Experiment 1: short segment VAE

短いオンライン筆記セグメントを VAE で再構成・サンプリングする。

評価:

- shape reconstruction。
- stroke endpoint preservation。
- motion model への接続しやすさ。

### Experiment 2: writer embedding

writer-id 付きデータで embedding を学習し、明示 profile との相関を見る。

評価:

- writer classification。
- profile parameter prediction。
- few-shot stability。

### Experiment 3: context spacing model

文字間 spacing と接続性だけを学習対象にする。

評価:

- 字間分布。
- 文レベル自然さ。
- CASHG 系指標との比較。

## 成果物

- neural variation の採用判断メモ。
- VAE/RNN baseline。
- writer embedding 実験レポート。
- structure constraint 仕様。

## 評価指標

- reconstruction error。
- endpoint drift。
- stroke order preservation。
- writer classification accuracy。
- ABX での自然さ改善。

## リスク

- データ不足。
- 日本語構造の破綻。
- モデルが評価指標に過適合する。
- 実装コストが高く、MVP を遅らせる。

## 参照

- [Generating Sequences With Recurrent Neural Networks](https://arxiv.org/abs/1308.0850)
- [DeepWriteSYN](https://arxiv.org/abs/2009.06308)
- [DeepWriting](https://huggingface.co/papers/1801.08379)
- [Disentangling Writer and Character Styles for Handwriting Generation](https://arxiv.org/abs/2303.14736)
- [CASHG](https://arxiv.org/abs/2604.02103)
