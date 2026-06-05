# Plotter Export Research Plan

## 目的

研究モデルが生成した `x,y,t,pen_state,pressure` を、実機が安全に実行できる命令へ変換する。モデルと機械依存制御を分離する。

## 背景

xDraw A4 は Z 軸でペン上下を制御する。AxiDraw API は pen height、速度、遅延を持つ。pressure を直接実現できない機械でも、Z 高さ、速度、遅延へ写像することで線質を近づけられる可能性がある。

## 主要仮説

1. pressure を Z 高さと feedrate へ写像すれば、終端の抜きは表現できる。
2. 内部 trajectory を機械非依存にすれば、xDraw と AxiDraw の比較が容易になる。
3. exporter は安全シーケンスと制約チェックを持つべきである。

## スコープ

含む:

- trajectory to G-code。
- trajectory to SVG。
- pressure to Z/feedrate mapping。
- safety validation。

含まない:

- GUI。
- 実機自動キャリブレーション。
- force sensor 制御。

## 実験

### Experiment 1: static export

同じ trajectory を SVG と G-code に出す。

評価:

- 座標一致。
- pen-up/down 区間。
- deterministic output。

### Experiment 2: pressure mapping

pressure を Z と feedrate へ変換する。

評価:

- Z 範囲。
- 終端の線幅。
- 実機での破綻。

### Experiment 3: hardware comparison

可能なら xDraw と AxiDraw 系で同じ SVG/G-code 相当を比較する。

評価:

- 線幅。
- 角の崩れ。
- ペンアップ跡。
- plot time。

## 成果物

- exporter interface。
- xDraw G-code exporter。
- SVG exporter。
- pressure mapping table。
- safety validator。

## 評価指標

- G-code safety violations。
- Z min/max。
- feedrate min/max。
- plot time。
- 実機エラー率。

## リスク

- pressure と実際の濃淡がペン種に強く依存する。
- xDraw の Z 応答が遅く、細かい pressure 変化に追従しない。
- AxiDraw API と xDraw G-code の抽象差が大きい。

## 参照

- [AxiDraw Python API Reference](https://axidraw.com/doc/py_api/)
