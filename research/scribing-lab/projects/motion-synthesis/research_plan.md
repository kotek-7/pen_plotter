# Motion Synthesis Research Plan

## 目的

stroke template から `x,y,t,pen_state,pressure` を生成する。字形だけでなく、速度、加速度、終筆、ペンアップ移動を人間らしくする。

## 背景

手書きらしさは、静的な線の揺れだけでは不十分である。人間の筆記には加減速と終筆イベントがある。Sigma-Lognormal 系モデルは、この運動生成を説明しやすい。

## 主要仮説

1. 等速補間より、Sigma-Lognormal 風の速度生成の方が人間らしく見える。
2. pressure event を Z 高さと速度に写像すれば、xDraw でも払い・はね・とめの差を表現できる。
3. drift と tremor は別成分として扱う方が制御しやすい。
4. 文章としての自然さには、画単位の速度だけでなく、pen-up timing、字間、行方向 drift、反復文字の差分が必要である。

## スコープ

含む:

- 画単位の速度生成。
- pressure event model。
- pen-up 区間の時間生成。
- line-level drift。
- repeated character variation。
- deterministic seed。

含まない:

- 深層生成モデル。
- force sensor 前提の閉ループ制御。
- 筆記中の実機フィードバック補正。

## 実験

### Experiment 1: basic strokes

対象:

- 横画。
- 縦画。
- 点。
- 左払い。
- はね。

比較:

- 等速。
- S 字 feedrate。
- Sigma-Lognormal 風速度。

評価:

- velocity peak。
- jerk。
- 実機出力の線質。

### Experiment 2: `永`

`永` を辞書から生成し、各画に終端イベントを付与する。

評価:

- harai/hane/tome の見た目差。
- pen-up 移動の自然さ。
- 文字としての読みやすさ。

### Experiment 3: short sentence

短文 3 種で字間、行方向、速度ばらつきを評価する。

評価:

- 字間分布。
- baseline drift。
- repeated character similarity。
- line-too-mechanical / paragraph-spacing-unnatural の failure tags。
- 主観 ABX。

## 成果物

- trajectory schema 実装案。
- motion generator 仕様。
- pressure event table。
- seed 固定テストケース。
- pen-up timing model。
- repeated character variation spec。
- basic strokes の比較レポート。

## 評価指標

- 速度ピーク数。
- peak timing。
- 加速度・jerk。
- DTW/DDTW。
- 実機破綻率。
- repeated character similarity。
- spacing variance。
- 人間評価での自然さ。

## リスク

- xDraw の feedrate/Z 応答が理論通りの線幅にならない。
- 短い画では lognormal 速度が過剰になる。
- jitter と tremor を入れすぎると文字品質が落ちる。
- 単文字で改善しても、短文では字間や反復文字が不自然に見える。

## 参照

- [A sigma-lognormal model-based approach to generating large synthetic online handwriting sample databases](https://digitalcommons.isical.ac.in/journal-articles/2438/)
- [The lognormal handwriter](https://pmc.ncbi.nlm.nih.gov/articles/PMC3867641/)
