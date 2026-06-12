# 10 Research Flow

この文書は、`scribing-lab` の研究フローを、実装済みの CLI・成果物・評価基盤に沿って整理した実務ガイドである。

目的は、どのコマンドをどの順で使い、何が registry に残り、どの成果物を比較材料にするのかを一目で追えるようにすることである。

この文書は、作業の段取りではなく、研究を止めずに回すための運用規約である。実装や schema の追加があっても、比較実験と次仮説まで到達しない限り、研究は完了扱いにしない。

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

## 研究の回し方

1. 仮説を 1 つだけ書く。
2. 最小の変更で検証する。
3. baseline か直前候補と比較する。
4. failure tags を付ける。
5. review packet を読む。
6. 次の仮説を 1 つだけ決める。

この 6 段を 1 サイクルとして回す。新しい実装が増えただけで比較が増えていない場合、その作業は研究ではなく基盤整備として扱う。

現在の主要ループは、以下の 2 本で整理すると追いやすい。

| ループ | 流れ |
|---|---|
| baseline ループ | `baseline-outline` -> `registry + artifacts + report` -> `compare` / `offline-review` |
| 構造・運動ループ | `structure-uniform` -> `structure-motion` -> `gcode_safety` -> `scan registration` |

どちらのループも、最後は `next_action` が残ることを必須条件にする。`next_action` が書けない実験は、比較が足りないか、仮説が曖昧すぎる。

## CLI と役割

### smoke

`smoke` は、評価基盤が最低限動くかを確かめるための疎通確認である。

入力は `--root`、`--experiment-id`、`--input-text` だけでよい。小さなダミー実験を 1 件作り、registry と report が書けるかを確認する用途で使う。

### baseline-outline

`baseline-outline` は、現行の基準方式を 1 件実行して登録する。

入力は、テキスト、seed、profile、outline の細かいパラメータである。出力として、trajectory、G-code、preview、設定 JSON、report が保存される。ここが比較の起点になる。

このコマンドの役割は、基準線を固定し、以後の変更を比較可能にすることである。単体で良し悪しを判断する用途には使わない。

### baseline-outline-batch

`baseline-outline-batch` は、固定入力セットを複数 seed でまとめて流す。

研究では 1 文だけでは判断できないため、短文セットを同じ形式で回して summary を作る。これにより baseline の癖が見えやすくなる。

### compare

`compare` は、registry にある実験群を baseline と比較する。

このコマンドは新しい生成を行わない。すでに登録された実験について、メトリクスの差分と失敗タグの差分をレポートにする。比較の焦点は「何が改善し、何が悪化したか」である。

比較結果から、次に変えるべき factor を 1 つに絞る。改善が複数にまたがるなら、まだ仮説が粗い。

### offline-review

`offline-review` は、実機スキャンがなくても、artifacts と metrics から次の調整候補を抽出する。

これは「今ある成果物をどう読むか」の道具である。例えば、`too-uniform` なら運動変化を増やす、`plotter-unsafe` なら安全性を先に直す、という形で次の一手が決まる。

評価の役割は点数付けではなく、次に試す最小変更を 1 つ決めることにある。

### attach-scan

`attach-scan` は、実機で出力したスキャン画像を既存実験へ紐付ける。

ここでは、対象実験の G-code 安全性が確認されていることが前提になる。安全確認済みの実験にだけ scan を付与することで、危険な出力を後追いで正当化しないようにする。

### structure-uniform

`structure-uniform` は、文字構造辞書を使った比較実験である。

ここでの目的は、字体の骨格や終端種別を保持したまま、均一タイミングの限界を見ることだ。baseline-outline との違いは、輪郭ではなく構造テンプレートに移る点にある。

この段階では、辞書を増やすこと自体が目的ではない。字形の崩れ、終端の不自然さ、文字種ごとの差がどれだけ改善したかを見る。

### structure-motion

`structure-motion` は、文字構造に時間変化と終端変化を加えた比較実験である。

この段階では、`x,y,t,pen_state,pressure` の時系列が中心になる。G-code 安全性チェックも通すので、研究上の「自然さ」と「実機安全性」を同時に見る段階になる。

判断は、モデルの複雑さではなく、速度、筆圧、終端、字間、反復差分のどれが自然さに効いたかで行う。

## 典型的な使い方

1. `baseline-outline-batch` で基準線を固定する。
2. `compare` で baseline と候補の差分を見る。
3. `offline-review` で失敗タグと次の一手を整理する。
4. `structure-uniform` で文字構造の効果を見る。
5. `structure-motion` で時間軸と終端イベントを足す。
6. 必要なら `attach-scan` で実機スキャンを紐付ける。

この順序は、研究を「比較可能な実験」に保つための順序でもある。先に実験基盤を固め、その上で自然さの要素を段階的に増やす。

各ラウンドで、最低でも次の 3 点が出ていなければやり直す。

- 何を変えたか。
- 何が良くなったか / 悪くなったか。
- 次に何を試すか。

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

どのコマンドも、次の仮説が書けなければ完了ではない。比較のない実装追加は、研究進行としては未完了である。

この流れを崩さないことが、比較可能性と安全性の両方を保つ条件になる。
