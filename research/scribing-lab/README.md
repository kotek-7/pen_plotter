# Scribing Lab

テキストから、ペンプロッタで人間の手書きと判別されにくい日本語筆記を生成するための独立研究プロジェクトである。

この研究領域は既存アプリケーションの `src/` を直接使わない。既存コードベースは xDraw A4 送信や G-code 生成の参考実装として扱い、研究用のモデル、データ契約、評価、実験計画はこの配下で独立して管理する。

この配下の文書を、日本語筆記エンジン研究の正本とする。ルートの `docs/scribing_engine.md` は、この研究領域への導線として管理する。

## 研究目標

入力テキストから、次の内部表現を生成する。

```text
x_mm, y_mm, t_ms, pen_state, pressure
```

この表現を、最終的に SVG、AxiDraw API、xDraw/GRBL G-code などへ変換する。初期ターゲットは日本語かなと頻出漢字であり、署名模倣や本人同意のない筆跡再現は対象外とする。

最終目標は単文字の自然さではなく、文章として紙面に出力したときに人間の手書きと判別されにくいことである。そのため、初期段階から短文、字間、行方向の揺れ、同じ文字の反復差分、実機出力スキャンを評価対象に含める。

## 評価駆動の研究ワークフロー

この研究は、仮説立案、実験設定、実装、評価、次実験の提案を反復して進める。そのため、生成モデルや辞書実装へ着手する前に、評価基盤と実験記録基盤を先に作る。

motion model、writer adaptation、neural variation の本格実装は、次の基盤が利用できる状態で進める。

- experiment registry: 実験 ID、仮説、設定、seed、入力文字列、成果物を記録する。
- artifact store: trajectory、preview、G-code、実機スキャン、ログ、評価結果を対応付ける。
- metric runner: 生成物に対して最低限の自動評価を実行する。
- report template: 実験結果、失敗分類、次に試す変更を同じ形式で残す。
- profile registry: writer profile と生成結果・評価結果の対応を追跡する。

## ドキュメント

推奨する読み順は、`00_overview.md`、`09_roadmap.md`、`07_evaluation.md`、各 `projects/*/research_plan.md` である。

- [00_overview.md](docs/00_overview.md): 全体像と研究分割
- [01_prior_research.md](docs/01_prior_research.md): 先行研究と技術領域
- [02_data_assets.md](docs/02_data_assets.md): データ資産とライセンス
- [03_character_structure.md](docs/03_character_structure.md): 文字構造辞書
- [04_motion_model.md](docs/04_motion_model.md): Sigma-Lognormal 運動生成
- [05_writer_profile.md](docs/05_writer_profile.md): writer profile
- [06_plotter_output.md](docs/06_plotter_output.md): プロッタ出力
- [07_evaluation.md](docs/07_evaluation.md): 評価設計
- [08_ethics_and_misuse.md](docs/08_ethics_and_misuse.md): 倫理・濫用対策
- [09_roadmap.md](docs/09_roadmap.md): ロードマップ
- [10_research_flow.md](docs/10_research_flow.md): 研究フローと CLI の実務ガイド

## 個別研究プロジェクト

各研究プロジェクトは、実装、テスト、計画、実験出力の除外設定を対応する `projects/<name>/` 配下にまとめる。

- [character-dictionary](projects/character-dictionary/research_plan.md): 日本語文字から画列・筆順・画種を得る
- [motion-synthesis](projects/motion-synthesis/research_plan.md): 人間らしい筆記運動を生成する
- [writer-profile](projects/writer-profile/research_plan.md): 筆者ごとの癖を推定・保存・適用する
- [plotter-export](projects/plotter-export/research_plan.md): 生成軌跡をプロッタ制御へ変換する
- [evaluation-harness](projects/evaluation-harness/research_plan.md): 自動評価と主観評価を設計する
- [neural-variation](projects/neural-variation/research_plan.md): 神経モデルを補助的に導入する

## 基本方針

- 評価基盤と実験記録基盤を最初に作る。
- 現行の font outline + jitter/wobble を `baseline-outline` として固定し、以後の方式は同じ入力・seed・report で比較する。
- 単文字だけで採択せず、短文と実機スキャンを初期評価に含める。
- 文字内容は構造辞書で拘束する。
- 運動の自然さは Sigma-Lognormal 系モデルで作る。
- 個人差は writer profile として明示的に扱う。
- 神経モデルは最初から主系にせず、画形状の変動や few-shot 適応の補助として使う。
- 生成軌跡とプロッタ固有命令を分離する。
- データライセンスと本人同意を研究計画の一部として扱う。
