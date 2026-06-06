# Evaluation Harness

手書きらしさを自動評価と人間評価で測る研究プロジェクトである。

詳細は [research_plan.md](research_plan.md) を参照する。

## 現在の最小実装

このプロジェクト配下に、評価駆動研究の最初の基盤を配置している。

- `ExperimentRegistry`: JSONL の experiment registry。
- `ArtifactStore`: 実験 ID ごとの成果物保存。
- `compute_trajectory_metrics`: 最小 trajectory metrics。
- `render_markdown_report`: 実験レビュー向け report。
- `FAILURE_TAGS`: 固定 failure taxonomy。
- `baseline-outline-batch`: 固定評価入力セットの batch runner。
- `review_packet.md`: batch 実験のレビュー束。
- `compare`: baseline との差分比較レポート。
- `compare-preview-fixed-inputs`: 固定評価入力セットの preview 差分レポート。
- `recommend-preview-fixed-inputs`: preview 候補の選定と次の改版案。
- `propose-preview-fixed-inputs`: preview 選定候補からの改版提案。
- `preview-iteration-fixed-inputs`: preview 比較から改版提案までの 1 ラウンド集約。
- `apply-preview-revision-fixed-inputs`: preview 改版案を適用して再生成する 1 ラウンド実行。
- `summarize-preview-revision-loops`: 複数ラウンドの設計原理と失敗傾向の要約。
- `propose-stable-writer-profiles`: 要約から安定候補 profile 群を生成。
- `evaluate-stable-writer-profiles`: 安定候補 profile 群を固定入力セットで評価し、採択候補を選定。
- `evaluate-data-driven-writer-prior`: JSONL のオンライン筆記サンプルから推定した prior を評価。
- `offline-review`: 実機スキャン前の artifact / metrics ベースのレビュー。
- `human-review-packet`: 生成 preview / metrics の目視レビュー束。
- `human-feedback-loop`: packet, response template, validation summary, next actions を 1 つにまとめた人間主観 FB ループ束。
- `human-feedback-ui`: packet を画面に並べて response を入力・検証・保存する Qt UI。
- `preview-review-packet`: preview を主軸にしたレビュー束の別名。
- `validate-human-review`: 目視レビュー response の検証と集計。
- `plot-ready-packet`: accepted record の G-code / safety / preview 束。
- `ScanMetadata`: 必要時だけ使う実機監査用 metadata schema。
- `AbxItem` / `AbxResponse`: 小規模 ABX 評価の最小 schema。

## 実行

`research/scribing-lab/projects/evaluation-harness` を作業ディレクトリにして実行する。

```sh
python3 -m evaluation_harness smoke --root runs/smoke
```

`self-check` は、固定入力セットに対する baseline / candidate 比較、review、plot-ready までの経路をまとめて検証する。
`Reference Basis` には KanjiVG、IAM-OnDB、DeepWriting、DeepWriteSYN、sigma-lognormal、CASHG を含め、構造・spacing・運動・style 分離の観点を固定している。

```sh
python3 -m evaluation_harness self-check --root runs/self-check
```

現行アプリの `font outline + jitter/wobble` を `baseline-outline` として固定し、
registry / artifact / report に保存する場合:

```sh
python3 -m evaluation_harness baseline-outline \
  --root runs/baseline-outline \
  --experiment-id exp-baseline-000001 \
  --input-text "永" \
  --seed 1
```

固定評価入力セット 5 件を複数 seed で一括登録する場合:

```sh
python3 -m evaluation_harness baseline-outline-batch \
  --root runs/baseline-outline \
  --seeds 1,2,3
```

registry 内の候補実験を `baseline-outline` と比較する場合:

```sh
python3 -m evaluation_harness compare \
  --root runs/baseline-outline \
  --baseline-generator baseline-outline
```

固定評価入力セットの比較完備性を確認する場合:

```sh
python3 -m evaluation_harness compare-fixed-inputs \
  --root runs/baseline-outline \
  --seeds 1,2,3
```

固定評価入力セットの preview 由来の差分を確認する場合:

```sh
python3 -m evaluation_harness compare-preview-fixed-inputs \
  --root runs/baseline-outline \
  --seeds 1,2,3
```

`compare-preview-fixed-inputs` は、baseline と candidate の `preview` artifact の
存在、サイズ、SHA-256 を比較し、preview が更新されたかを記録する。

`recommend-preview-fixed-inputs` は、preview がある候補の中から各 input / seed ごとに
最小 failure tag の候補を選び、次に直すべき profile / layout / motion の提案を出す。

`propose-preview-fixed-inputs` は、選定候補ごとに `motion`、`layout`、`dictionary`、
`profile`、`safety` のどれを変えるべきかを revision plan として出力する。

`preview-iteration-fixed-inputs` は、preview 差分、候補選定、改版提案を 1 ラウンドとして
束ね、次の実験に渡すための summary を保存する。

`apply-preview-revision-fixed-inputs` は、選定候補の `revision plan` を derived profile に
反映し、同じ input / seed で再生成した結果を registry に追加する。
このループでは、before / after の比較に加えて、`design_principles` と
`comparison_summary` を記録し、どの変更が効いたかを後から追えるようにする。

`summarize-preview-revision-loops` は、複数の revision loop packet をまとめて、
安定して繰り返し出る design principle と failure tag を抽出する。

`propose-stable-writer-profiles` は、安定して効く design principle から
derived writer profile 候補を作る。

`evaluate-stable-writer-profiles` は、候補 profile を固定評価入力セットへ流し、
baseline と比較して新しい failure tag が出ない候補だけを採択する。
評価結果は `selected_profile_ids` と `selection_summary` に保存される。

`evaluate-data-driven-writer-prior` は、`samples.jsonl` から推定した derived profile を
固定評価入力セットへ流し、baseline と比較して prior が実際に改善するかを確認する。

生成 preview の前段で、registry 内の metrics / failure tags から次の調整候補を出す場合:

```sh
python3 -m evaluation_harness offline-review \
  --root runs/structure-motion
```

`offline-review` は `offline_review.md` と `offline_review.json` を生成する。
`too-uniform`、`line-too-mechanical`、`over-jittered`、`plotter-unsafe` などを
preview / trajectory / G-code safety の前段評価として扱い、次に調整する対象を記録する。

自動評価を通った候補を生成 preview ベースで目視レビュー用に束ねる場合:

```sh
python3 -m evaluation_harness human-review-packet \
  --root runs/structure-motion
```

`human-review-packet` と `preview-review-packet` は、代表 seed の preview、主要 metrics、
failure tags と、input ごとの全 preview path を `human_review_packet.md` / `.json`
または `preview_review_packet.md` / `.json` に保存する。

```sh
python3 -m evaluation_harness human-feedback-loop \
  --root runs/structure-motion
```

`human-feedback-loop` は response template 付きの統合束を `human_feedback_loop.md` / `.json`
に保存する。responses を渡すと、検証結果と次アクションも同じ束に入る。

```sh
python3 -m evaluation_harness human-feedback-ui \
  --root runs/structure-motion
```

`human-feedback-ui` は代表 preview を画面上で切り替えながら、`accept` / `reject` /
`needs-tuning` と reason tags を入力し、`human_review_responses.json` と
`human_review_response_summary.json` を保存する。UI は Qt ベースなので、日本語と英字の
表示品質が Tkinter 版より安定している。

既存の review packet から開く場合は `--packet-json` を使う。既存の回答を読み込んで
続きからレビューする場合は `--responses-json`、保存先を明示したい場合は
`--summary-json` を併用する。

`human-feedback-loop` は、同じ review packet に加えて response template と validation summary を
1 つの `human_feedback_loop.md` / `.json` にまとめる。responses を渡すと、
`accept` / `reject` / `needs-tuning` の集計と次アクションまで出力する。

目視レビュー結果を packet と照合して集計する場合:

```sh
python3 -m evaluation_harness validate-human-review \
  --packet-json runs/structure-motion/human_review_packet.json \
  --responses-json runs/structure-motion/human_review_responses.json
```

response は `accept`、`reject`、`needs-tuning` のいずれかを記録する。
`validate-human-review` は代表 record との対応、未回答、未知 ID、重複を検証し、
`can_proceed_to_plot` を summary に保存する。

実機送信前に accepted record の G-code と safety を束ねる場合:

```sh
python3 -m evaluation_harness plot-ready-packet \
  --root runs/structure-motion \
  --human-summary-json runs/structure-motion/human_review_response_summary.json
```

`plot-ready-packet` は G-code を自動送信しない。`gcode_safety_ok` と
`gcode_safety` artifact を再確認し、xDraw A4 のホーミング、`G92 X0 Y297 Z0`、
Z 軸ペン制御を checklist として保存する。scan は必要時のみ追加する監査手段とする。

必要時だけ実機スキャンを既存 experiment に紐付ける場合:

```sh
python3 -m evaluation_harness attach-scan \
  --root runs/plotter-export-final \
  --experiment-id exp-motion-i01-s001 \
  --scan-path plotted_scan.png \
  --metadata-json examples/scan_metadata.example.json
```

`attach-scan` は、対象 experiment の `gcode_safety_ok` が `1` で、`gcode_safety`
artifact が存在する場合だけ登録する。実機送信前に `gcode_safety.json` の
`ok: true` と `violations: []` を確認する。通常の比較ループは preview を主軸に回す。

生成物は `runs/` に保存される。`runs/` は実験出力なので git 管理しない。

## テスト

既存リポジトリの仮想環境を使う場合:

```sh
cd /home/kotek/dev/pen_plotter/research/scribing-lab/projects/evaluation-harness
/home/kotek/dev/pen_plotter/.venv/bin/python -m pytest
```
