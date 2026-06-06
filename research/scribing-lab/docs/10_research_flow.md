# 10 Research Flow

この文書は、`scribing-lab` の研究フローを、実装済みの CLI・成果物・評価基盤に沿って整理した実務ガイドである。

目的は、どのコマンドをどの順で使い、何が registry に残り、どの成果物を比較材料にするのかを一目で追えるようにすることである。

## 研究フロー図

| 段階 | 何をするか | 主なコマンド / 実装 | 主な出力 |
|---|---|---|---|
| 1 | 仮説と条件を決める | `experiment_id`, `input_text`, `seed`, `profile_id`, `generator` | 比較条件の固定 |
| 2 | 生成を実行する | `baseline-outline` / `structure-uniform` / `structure-motion` | `trajectory` / `gcode` / `preview` |
| 3 | 数値評価を行う | `compute_trajectory_metrics` | `metrics` |
| 4 | 失敗を分類する | `failure tags` | `failure_tags` |
| 5 | レポートを書く | `render_markdown_report` | `report.md` |
| 6 | 台帳へ登録する | `ExperimentRegistry.append()` | `registry.jsonl` |
| 7 | baseline と比較する | `compare` | `comparison_report.md` |
| 8 | 実機前レビューを行う | `offline-review` | `offline_review.md` / `offline_review.json` |
| 9 | 必要なら実機スキャンを紐付ける | `attach-scan` | `plotted_scan.png` / `scan_metadata.json` |
| 10 | 次の仮説へ進む | `next_action` | 次実験の設計 |

現在の主要ループは、以下の 2 本で整理すると追いやすい。

| ループ | 流れ |
|---|---|
| baseline ループ | `baseline-outline` -> `registry + artifacts + report` -> `compare` / `offline-review` |
| 構造・運動ループ | `structure-uniform` -> `structure-motion` -> `gcode_safety` -> `scan registration` |

## CLI と役割

### smoke

`smoke` は、評価基盤が最低限動くかを確かめるための疎通確認である。

入力は `--root`、`--experiment-id`、`--input-text` だけでよい。小さなダミー実験を 1 件作り、registry と report が書けるかを確認する用途で使う。

### baseline-outline

`baseline-outline` は、現行の基準方式を 1 件実行して登録する。

入力は、テキスト、seed、profile、outline の細かいパラメータである。出力として、trajectory、G-code、preview、設定 JSON、report が保存される。ここが比較の起点になる。

### baseline-outline-batch

`baseline-outline-batch` は、固定入力セットを複数 seed でまとめて流す。

研究では 1 文だけでは判断できないため、短文セットを同じ形式で回して summary を作る。これにより baseline の癖が見えやすくなる。

### compare

`compare` は、registry にある実験群を baseline と比較する。

このコマンドは新しい生成を行わない。すでに登録された実験について、メトリクスの差分と失敗タグの差分をレポートにする。比較の焦点は「何が改善し、何が悪化したか」である。

### offline-review

`offline-review` は、実機スキャンがなくても、artifacts と metrics から次の調整候補を抽出する。

これは「今ある成果物をどう読むか」の道具である。例えば、`too-uniform` なら運動変化を増やす、`plotter-unsafe` なら安全性を先に直す、という形で次の一手が決まる。

### attach-scan

`attach-scan` は、実機で出力したスキャン画像を既存実験へ紐付ける。

ここでは、対象実験の G-code 安全性が確認されていることが前提になる。安全確認済みの実験にだけ scan を付与することで、危険な出力を後追いで正当化しないようにする。

### structure-uniform

`structure-uniform` は、文字構造辞書を使った比較実験である。

ここでの目的は、字体の骨格や終端種別を保持したまま、均一タイミングの限界を見ることだ。baseline-outline との違いは、輪郭ではなく構造テンプレートに移る点にある。

### structure-motion

`structure-motion` は、文字構造に時間変化と終端変化を加えた比較実験である。

この段階では、`x,y,t,pen_state,pressure` の時系列が中心になる。G-code 安全性チェックも通すので、研究上の「自然さ」と「実機安全性」を同時に見る段階になる。

## 典型的な使い方

1. `baseline-outline-batch` で基準線を固定する。
2. `compare` で baseline と候補の差分を見る。
3. `offline-review` で失敗タグと次の一手を整理する。
4. `structure-uniform` で文字構造の効果を見る。
5. `structure-motion` で時間軸と終端イベントを足す。
6. 必要なら `attach-scan` で実機スキャンを紐付ける。

この順序は、研究を「比較可能な実験」に保つための順序でもある。先に実験基盤を固め、その上で自然さの要素を段階的に増やす。

## 成果物の見方

### registry.jsonl

1 行 1 実験の台帳である。まずここを見れば、何を回したかが分かる。

### artifacts/

各実験 ID の成果物が入る。preview、G-code、trajectory、設定、安全性検査、report などが並ぶ。

### summary.md / summary.json

batch 実行の集計である。複数 seed の傾向を見るときに使う。

### comparison_report.md

baseline との差分を見る文書である。候補方式が何を改善したか、何を悪化させたかを確認する。

### offline_review.md / offline_review.json

実機に進む前のレビュー文書である。失敗タグと次アクションの対応を見る。

### gcode_safety.json

実機送信前に危険がないかを示す安全性レポートである。`structure-motion` のように機械出力へ近い段階では重要になる。

### scan_metadata.json

実機スキャンの条件を残すメタデータである。スキャン画像単体より、条件込みで比較するために必要になる。

## 研究での読み方

このプロジェクトでは、コマンドを単なるスクリプトではなく、研究の段階を分ける装置として扱う。

- `baseline-outline` は基準線を作る
- `structure-uniform` は構造制約の効果を見る
- `structure-motion` は運動と終端の効果を見る
- `compare` と `offline-review` は、次の仮説を作る
- `attach-scan` は、机上評価を実機評価へ接続する

この流れを崩さないことが、比較可能性と安全性の両方を保つ条件になる。
