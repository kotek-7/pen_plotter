# Plotter Export

> Archived: このプロジェクトは旧 `projects/` 分割と evaluation-harness 中心の研究運用を前提にした参照用コードである。現行の `engines/`、`runner/`、`runs/`、`evaluation/` 方針とは意図的にズレている。

内部軌跡を SVG、AxiDraw API、xDraw/GRBL G-code へ変換する研究プロジェクトである。

`x,y,t,pen_state,pressure` の trajectory を検証してから、安全な xDraw/GRBL G-code に変換する。

詳細は [research_plan.md](research_plan.md) を参照する。
