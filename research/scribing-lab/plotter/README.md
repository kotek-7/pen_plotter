# Plotter

正準軌跡(`x, y, t, pen_state, pressure`)を xDraw A4 / GRBL 用の G-code に変換し、
紙面範囲・Z・feed の最低限の安全確認を行う基盤。

engine から切り離した実機 export 専用の基盤として扱う。出力骨格(ホーミング、
`G92 X0 Y297 Z0` の紙座標設定、Z 軸ペン制御、travel/home 移動)は、実機での動作実績がある
ルートの G-code 生成を正として移植している。

## 変換規則

- header: `$H` → `G4 P1` → `G92 X0 Y{paper_height} Z0` → `G90` → ペンアップ。
- `pen_state` の遷移でペンアップ/ダウン(Z 軸コマンド)と travel を切り替える。
- feed は軌跡の時刻差から mm/min を算出し、`[min_draw_feed, max_draw_feed]` にクランプする。
- pressure は仮想量として Z 高さへ写像する(`finish_lift_z`〜`pen_down_z`)。実機での
  詰めは後段(実機スキャン)で行う前提の暫定写像。

機械パラメータは `PlotterConfig` に集約している。

## 使い方

ライブラリ:

```py
from scribing_plotter import PlotterConfig, trajectory_to_gcode, validate_gcode

gcode = trajectory_to_gcode(trajectory, PlotterConfig())
safety = validate_gcode(gcode, PlotterConfig())
```

CLI(既存 run の `trajectory.json` から `output.gcode` と `safety.json` を再生成):

```sh
cd research/scribing-lab/plotter
uv sync --extra dev
uv run scribe-export ../runs/20260626T123456_example
```
