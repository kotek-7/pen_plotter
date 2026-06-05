# 06 Plotter Output

## 目的

内部軌跡 `x,y,t,pen_state,pressure` を、実機プロッタで安全に実行できる命令へ変換する。研究モデルと機械依存命令を分離する。

## 出力ターゲット

| target | 優先度 | 目的 |
|---|---:|---|
| xDraw/GRBL G-code | 高 | 現在の実機に合わせる |
| SVG | 高 | 可視化と AxiDraw 互換 |
| AxiDraw API | 中 | 研究用比較ターゲット |
| HPGL | 低 | 将来の他機種対応 |

## xDraw/GRBL 方針

xDraw A4 では Z 軸でペン上下を制御する。

- pen up: `G1G90 Z0.5 F5000`
- pen down: `G1G90 Z3.5 F5000`
- home: `$H`
- paper origin: `G92 X0 Y297 Z0`

pressure は次へ写像する。

- 高 pressure: pen down Z に近い。
- 低 pressure: finish_lift_z に近い。
- harai: 終端で Z を上げ、速度を落とす。
- hane: 終端で Z を上げ、速度を上げる。

## AxiDraw 方針

AxiDraw API は pen height、pen up/down speed、XY speed、delay を制御できる。pressure を直接出すのではなく、ペン高さ、速度、遅延で結果としての濃淡や線幅へ寄せる。

参照:

- [AxiDraw Python API Reference](https://axidraw.com/doc/py_api/)

## exporter の責務

- 座標系変換。
- feedrate 生成。
- pen up/down 区間の明示。
- pressure の機械依存写像。
- 安全な開始・終了シーケンス。
- 実機で危険な自動 pen-down を避ける。

## 非責務

- 文字構造の解決。
- writer profile 推定。
- 神経モデル推論。
- 実機キャリブレーション値の自動決定。

## テスト方針

- 同一 trajectory から deterministic な G-code が出る。
- pen-down 区間だけ描画線になる。
- pen-up 移動が線として出ない。
- Z 値が安全範囲内に収まる。
- `$H` と `G92 X0 Y297 Z0` が必要な場面で出る。

## 実機評価

- 同じ軌跡を速度だけ変えて線の濃さ・にじみ・角の崩れを見る。
- harai/hane/tome の終端が紙面で区別できるかを見る。
- ペン種ごとの最適 parameter を記録する。
