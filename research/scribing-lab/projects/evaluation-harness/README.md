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
