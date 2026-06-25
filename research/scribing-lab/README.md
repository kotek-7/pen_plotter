# Scribing Lab

テキストから、ペンプロッタで人間の手書きと判別されにくい日本語筆記を生成するための独立研究領域である。

この研究領域は既存アプリケーションの `src/` を直接使わない。既存コードベースは xDraw A4 送信や G-code 生成の参考実装として扱い、研究用の engine、runner、run 出力、評価はこの配下で独立して管理する。

この配下の文書を、日本語筆記エンジン研究の正本とする。ルートの `docs/scribing_engine.md` は、この研究領域への導線として管理する。

## 研究目標

入力テキストから、次の内部表現を生成する。

```text
x_mm, y_mm, t_ms, pen_state, pressure
```

この表現を、最終的に SVG、AxiDraw API、xDraw/GRBL G-code などへ変換する。初期ターゲットは日本語かなと頻出漢字であり、署名模倣や本人同意のない筆跡再現は対象外とする。

最終目標は単文字の自然さではなく、文章として紙面に出力したときに人間の手書きと判別されにくいことである。そのため、初期段階から短文、字間、行方向の揺れ、同じ文字の反復差分、実機出力スキャンを評価対象に含める。

## 現行の構成

```text
engines/            開発中の筆記 engine（text → trajectory）
renderer/            trajectory → preview.svg の変換基盤
exporter/            trajectory → G-code + safety の変換基盤
runner/             engine を実行し、変換基盤を使って成果物を runs/ に書く最小基盤
runs/               engine 実行結果の置き場（git 管理しない）
evaluation/         runs/ を読む評価領域（後段で設計）
docs/               研究文書
projects-archived/  旧研究コードの参照用アーカイブ
```

`engines/` 配下の各 engine は、1 つの生成方式として扱う。engine の責務は正準軌跡
（`x,y,t,pen_state,pressure`）の生成までで、preview と実機 G-code への変換は engine から
切り離し、`renderer/`・`exporter/` という独立基盤が担う。これは「生成軌跡とプロッタ固有命令は
分離する」という方針に沿う。`runner/` は engine から trajectory を受け取り、両基盤を使って
`runs/` に `trajectory.json`、`preview.svg`、`output.gcode`、`safety.json`、`memo.md` を
書き出す。既存 run からは `scribe-render` / `scribe-export` で preview・G-code を再生成できる。

`runs/` は出力を見るための置き場である。過度に規格化された実験台帳ではなく、実行条件は
`memo.md` に軽く残し、preview 確認や試し書きに使う。標準の run directory は
`YYYYMMDDTHHMMSS_<name>` 形式にする。評価は `evaluation/` で後から設計する。

旧 `projects/` 配下の研究コードは `projects-archived/` に移した。これは参照用であり、
現行の新規実装の基盤にはしない。

## 実行

runner は独立した `uv` project である。

```sh
cd research/scribing-lab/runner
uv sync --extra dev
uv run scribe-run "今日はよい天気です。" \
  --engine ../engines/basic_stroke_engine \
  --seed 1 \
  --name example-basic
```

## ドキュメント

推奨する読み順は、`00_overview.md`、`09_roadmap.md`、`07_evaluation.md`、`runner/README.md` である。

- [00_overview.md](docs/00_overview.md): 全体像と研究分割
- [01_prior_research.md](docs/01_prior_research.md): 先行研究と技術領域
- [02_data_assets.md](docs/02_data_assets.md): データ資産とライセンス
- [03_character_structure.md](docs/03_character_structure.md): 文字構造辞書
- [04_motion_model.md](docs/04_motion_model.md): Sigma-Lognormal 運動生成
- [05_writer_profile.md](docs/05_writer_profile.md): writer profile
- [06_plotter_output.md](docs/06_plotter_output.md): プロッタ出力
- [07_evaluation.md](docs/07_evaluation.md): 評価設計
- [evaluation/README.md](evaluation/README.md): run preview viewer
- [08_ethics_and_misuse.md](docs/08_ethics_and_misuse.md): 倫理・濫用対策
- [09_roadmap.md](docs/09_roadmap.md): ロードマップ
- [10_research_flow.md](docs/10_research_flow.md): 旧 evaluation-harness 中心の研究フロー。参照用
- [11_glossary.md](docs/11_glossary.md): 用語集と前提知識
- [12_research_plan.md](docs/12_research_plan.md): 研究計画書

## アーカイブ

旧研究コードは `projects-archived/` に残す。

- [character-dictionary](projects-archived/character-dictionary/research_plan.md): 日本語文字から画列・筆順・画種を得る旧実装
- [motion-synthesis](projects-archived/motion-synthesis/research_plan.md): 人間らしい筆記運動を生成する旧実装
- [writer-profile](projects-archived/writer-profile/research_plan.md): 筆者ごとの癖を推定・保存・適用する旧実装
- [plotter-export](projects-archived/plotter-export/research_plan.md): 生成軌跡をプロッタ制御へ変換する旧実装
- [evaluation-harness](projects-archived/evaluation-harness/research_plan.md): 自動評価と主観評価を設計する旧実装
- [neural-variation](projects-archived/neural-variation/research_plan.md): 神経モデルを補助的に導入する旧計画

## 基本方針

- まず engine を実行し、trajectory、preview、G-code を出せる状態を優先する。
- run の主役は成果物であり、実行条件は自由形式に近い `memo.md` に留める。
- 評価、比較、失敗分類、実験台帳は `runs/` の出力を見てから後段で設計する。
- engine ごとの内部構成は自由にし、研究上は engine 全体を 1 つの生成方式として扱う。
- 生成軌跡とプロッタ固有命令は分離する。
- データライセンスと本人同意を研究計画の一部として扱う。
