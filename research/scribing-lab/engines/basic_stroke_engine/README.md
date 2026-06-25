# Basic Stroke Engine

runner と runs の MVP を確認するための最小 engine。

この engine は手書き品質を目指さない。既存 `src/` や `projects-archived/*` に依存せず、
標準ライブラリだけで次を生成する。

- `trajectory.json`
- `preview.svg`
- `output.gcode`
- `safety.json`

文字は実グリフではなく、文字コードと seed から決まる簡単なストロークパターンとして描く。
目的は、engine の実行単位と成果物保存の形を確認することである。
