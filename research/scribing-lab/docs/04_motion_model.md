# 04 Motion Model

## 目的

画骨格から、人間らしい時間軸付き軌跡を生成する。対象出力は `x,y,t,pen_state,pressure` である。

## 基本方針

初期実装では、神経モデルではなく Sigma-Lognormal 系の運動モデルを主系にする。理由は、プロッタ制御に必要な速度・時間・終筆の意味を保ちやすく、各パラメータを解釈できるためである。

## Sigma-Lognormal で扱う要素

- 画の開始時刻。
- 速度ピーク位置。
- 速度ピーク幅。
- 始点方向。
- 終点方向。
- 複数成分の重ね合わせ。

## 生成パイプライン

```text
stroke skeleton
  -> resample control points
  -> assign lognormal components
  -> generate velocity profile
  -> integrate to x,y,t
  -> add pressure event
  -> add drift/tremor
  -> add pen-up timing
  -> add line-level spacing and repeated-character variation
```

## pressure event

pressure は実機の荷重ではなく、初期段階では仮想筆圧である。

| event | pressure | xDraw への写像 |
|---|---|---|
| tome | 終端でやや維持または増加 | Z 維持、低速化 |
| harai | 終端で滑らかに減衰 | Z を上げる、速度を落とす |
| hane | 終端直前に短いピーク後に抜く | Z を上げる、速度を上げる |
| none | 一定 | 通常線 |

## drift / tremor

揺れは二種類に分ける。

- low-frequency drift: 行方向、字高、ベースラインのゆらぎ。
- local tremor: 点列レベルの小さい震え。

これらは writer profile で強度を制御する。

文章では、同じ文字が不自然に同一にならないこと、行全体が機械的に揃いすぎないことも重要である。motion model は、画単位の速度だけでなく、字間、pen-up 移動時間、反復文字の微小差分、文章後半の速度変化を扱う。

## 学習なし MVP

最初は手設計 prior で実装する。

- 画長から duration を決める。
- 曲率が高い部分で速度を少し落とす。
- 画種ごとに終端 pressure event を決める。
- pen-up 移動にも距離に応じた時間を与える。
- 同じ文字の反復に seed 付きの小さな差分を入れる。
- 同一 seed で再現可能にする。

## データ駆動版

次段階では、TUAT または自前オンライン筆記データから prior を推定する。

- 文字種別。
- 画種別。
- writer cluster 別。
- 字内位置別。
- 文中位置別。

## 評価指標

- 速度ピーク数。
- peak timing。
- 速度分布。
- 加速度・jerk。
- DTW/DDTW。
- 終端イベントの線幅変化。
- プロッタ実機での破綻率。
- repeated character similarity。
- spacing variance。

## 参照

- [A sigma-lognormal model-based approach to generating large synthetic online handwriting sample databases](https://digitalcommons.isical.ac.in/journal-articles/2438/)
- [The lognormal handwriter](https://pmc.ncbi.nlm.nih.gov/articles/PMC3867641/)
