# 日本語筆記エンジン研究

この文書は、日本語筆記エンジン研究への入口である。研究計画、先行研究、データ資産、engine 実行基盤、評価領域の正本は [research/scribing-lab](../research/scribing-lab/README.md) に置く。

## 位置づけ

この文書は、既存アプリの補助ドキュメントと独立研究プロジェクトの境界を示す。詳細な研究計画や技術調査は、研究プロジェクト配下の文書で管理する。

ドキュメントの配置方針は次の通り。

- 既存アプリの実装・実機運用ドキュメントは `docs/` に置く。
- 日本語筆記エンジンの研究ドキュメントは `research/scribing-lab/` に置く。
- 先行研究の要約と参照リンクは [01_prior_research.md](../research/scribing-lab/docs/01_prior_research.md) を正本にする。
- データ資産とライセンスの整理は [02_data_assets.md](../research/scribing-lab/docs/02_data_assets.md) を正本にする。
- 研究 engine の実行は `research/scribing-lab/runner/` から行い、preview と G-code への変換は `renderer/` と `exporter/` が担う。
- 通常の実行導線は `research/scribing-lab/Makefile` から `run`、`convert`、`view` を使う。
- 旧 `projects/` 配下の研究コードは `research/scribing-lab/projects-archived/` に移し、参照用アーカイブとして扱う。

## 研究の概要

目標は、テキストから `x_mm, y_mm, t_ms, pen_state, pressure` の時系列を生成し、ペンプロッタで人間の手書きと判別されにくい日本語筆記を行うことである。

初期方針は次の通り。

- 文字内容は KanjiVG などの文字構造辞書で拘束する。
- 筆記運動は Sigma-Lognormal 系の運動モデルを中心に扱う。
- 個人差は writer profile として明示的に管理する。
- 神経モデルは最初から主系にせず、画形状の変動や profile 推定の補助として扱う。
- まず engine を実行して trajectory を生成し、preview と G-code へ変換して確認できる最小基盤を整える。
- 評価基盤は `runs/` の出力を読む後段として設計する。

## 読む順序

1. [research/scribing-lab/README.md](../research/scribing-lab/README.md)
2. [13_rebuild_summary.md](../research/scribing-lab/docs/13_rebuild_summary.md)
3. [00_overview.md](../research/scribing-lab/docs/00_overview.md)
4. [runner README](../research/scribing-lab/runner/README.md)
5. 必要に応じて `research/scribing-lab/docs/` と `research/scribing-lab/projects-archived/` の各文書

## 注意

この研究は、本人同意のない筆跡模倣や署名生成を目的にしない。倫理・濫用対策は [08_ethics_and_misuse.md](../research/scribing-lab/docs/08_ethics_and_misuse.md) を正本にする。
