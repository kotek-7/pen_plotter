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
- `offline-review`: 実機スキャン前の artifact / metrics ベースのレビュー。
- `human-review-packet`: 実機出力前の目視レビュー向け preview / metrics 束。
- `validate-human-review`: 目視レビュー response の検証と集計。
- `ScanMetadata`: 実機スキャン artifact の metadata schema。
- `AbxItem` / `AbxResponse`: 小規模 ABX 評価の最小 schema。

## 実行

`research/scribing-lab/projects/evaluation-harness` を作業ディレクトリにして実行する。

```sh
python3 -m evaluation_harness smoke --root runs/smoke
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

実機出力の前に、registry 内の metrics / failure tags から次の調整候補を出す場合:

```sh
python3 -m evaluation_harness offline-review \
  --root runs/structure-motion
```

`offline-review` は `offline_review.md` と `offline_review.json` を生成する。
`too-uniform`、`line-too-mechanical`、`over-jittered`、`plotter-unsafe` などを
preview / trajectory / G-code safety の前段評価として扱い、次に調整する対象を記録する。

自動評価を通った候補を目視レビュー用に束ねる場合:

```sh
python3 -m evaluation_harness human-review-packet \
  --root runs/structure-motion
```

`human-review-packet` は、代表 seed の preview、主要 metrics、failure tags と、
input ごとの全 preview path を `human_review_packet.md` / `.json` に保存する。

目視レビュー結果を packet と照合して集計する場合:

```sh
python3 -m evaluation_harness validate-human-review \
  --packet-json runs/structure-motion/human_review_packet.json \
  --responses-json runs/structure-motion/human_review_responses.json
```

response は `accept`、`reject`、`needs-tuning` のいずれかを記録する。
`validate-human-review` は代表 record との対応、未回答、未知 ID、重複を検証し、
`can_proceed_to_plot` を summary に保存する。

実機スキャンを既存 experiment に紐付ける場合:

```sh
python3 -m evaluation_harness attach-scan \
  --root runs/plotter-export-final \
  --experiment-id exp-motion-i01-s001 \
  --scan-path plotted_scan.png \
  --metadata-json examples/scan_metadata.example.json
```

`attach-scan` は、対象 experiment の `gcode_safety_ok` が `1` で、`gcode_safety`
artifact が存在する場合だけ登録する。実機送信前に `gcode_safety.json` の
`ok: true` と `violations: []` を確認する。

生成物は `runs/` に保存される。`runs/` は実験出力なので git 管理しない。

## テスト

既存リポジトリの仮想環境を使う場合:

```sh
cd /home/kotek/dev/pen_plotter/research/scribing-lab/projects/evaluation-harness
/home/kotek/dev/pen_plotter/.venv/bin/python -m pytest
```
