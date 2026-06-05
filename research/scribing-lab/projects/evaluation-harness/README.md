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

## 実行

`research/scribing-lab/projects/evaluation-harness` を作業ディレクトリにして実行する。

```sh
python3 -m evaluation_harness smoke --root runs/smoke
```

生成物は `runs/` に保存される。`runs/` は実験出力なので git 管理しない。

## テスト

既存リポジトリの仮想環境を使う場合:

```sh
cd /home/kotek/dev/pen_plotter/research/scribing-lab/projects/evaluation-harness
/home/kotek/dev/pen_plotter/.venv/bin/python -m pytest
```
