# Basic Stroke Engine

runner と runs の MVP を確認するための最小 engine。

この engine は手書き品質を目指さない。既存 `src/` や `projects-archived/*` に依存せず、
標準ライブラリだけで正準軌跡(`x, y, t, pen_state, pressure`)を生成する。

preview と G-code への変換は engine の責務ではなく、`../../renderer`・`../../exporter` の
変換基盤が trajectory から生成する。runner がそれらを呼び出して `runs/` に成果物を書く。

文字は実グリフではなく、文字コードと seed から決まる簡単なストロークパターンとして描く。
目的は、engine の実行単位と成果物保存の形を確認することである。
