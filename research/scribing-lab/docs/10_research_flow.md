# 10 Research Flow

この文書は、`scribing-lab` の研究フローを、実装済みの CLI・成果物・評価基盤に沿って整理した実務ガイドである。

目的は、どのコマンドをどの順で使い、何が registry に残り、どの成果物を比較材料にするのかを一目で追えるようにすることである。

## 前提知識

### experiment registry

`experiment registry` は、実験の台帳である。各実験の識別子、仮説、入力、seed、生成器、出力器、成果物、メトリクス、失敗タグ、次の一手を 1 レコードとして保存する。

このプロジェクトでは JSONL 形式を使う。JSONL は「1 行 = 1 JSON オブジェクト」の保存形式で、追記しやすく、差分比較しやすい。研究では、後から「何を試したか」を復元できることが重要なので、実験ログを表計算ではなく台帳として持つ。

### artifact store

`artifact store` は、実験ごとの成果物置き場である。画像、G-code、軌跡 JSON、設定 JSON、レポートなどを、同じ `experiment_id` の下にまとめる。

ここでの成果物は「結果を説明する証拠」である。生成物そのものだけでなく、生成条件や安全性の検査結果も同じ実験 ID に紐付けることで、再実行時の比較対象が揃う。

### experiment_id

`experiment_id` は、1 回の実験を一意に識別する ID である。例: `exp-baseline-000001`。

この ID が実験全体の主キーになる。registry、artifact、report、scan を全部この ID でつなぐため、途中で名前を変えないことが重要である。

### generator

`generator` は、何が生成したかを表すラベルである。`baseline-outline`、`structure-uniform`、`structure-motion` のように、研究上の方式単位で固定する。

この値が変わると比較の意味も変わる。したがって「同じ入力・同じ seed で generator だけを変える」ことが、研究の基本比較になる。

### exporter

`exporter` は、内部表現をどの実機向け命令へ変換したかを示す。現在の主な値は `xdraw-gcode` である。

研究では、生成器と出力器を分離して扱う。これは、文字の自然さと機械命令の安全性を別々に評価したいからである。

### trajectory

`trajectory` は、`x_mm, y_mm, t_ms, pen_state, pressure` を持つ時系列データである。

`x_mm` と `y_mm` は紙面上の座標、`t_ms` は時刻、`pen_state` はペンが紙に触れているかどうか、`pressure` は筆圧の代替量である。xDraw では真の筆圧がないため、pressure は Z 高さや feedrate に写像する前提で扱う。

### metrics

`metrics` は、実験結果を数値で要約したものだ。速度ピーク数、加速度、jerk、字間のばらつき、baseline drift などを含む。

自動メトリクスは主観評価の代替ではないが、退行検知には有効である。研究では「見た目が良い気がする」だけでは足りず、同じ条件で再現できる比較指標が必要になる。

### failure tags

`failure tags` は、失敗の型を短いラベルで表す。例として `too-uniform`、`line-too-mechanical`、`plotter-unsafe` などがある。

タグの役割は、問題を「どの層で直すべきか」に分けることにある。字形の問題なのか、運動の問題なのか、機械安全の問題なのかを分離できると、次の修正方針が立てやすい。

### report

`report` は、1 実験の要約文書である。仮説、設定、成果物、メトリクス、失敗タグ、次のアクションを 1 ページにまとめる。

研究では、コードだけでなくレポートも成果物である。実験の意味が残らないと、後で比較できないからである。

### baseline-outline

`baseline-outline` は、現行の font outline + jitter/wobble を固定した比較基準である。

これは「最初の基準線」であって、最終目標ではない。研究では、まず基準を固定してから、その上で構造辞書や運動モデルがどれだけ改善するかを測る。

### structure-uniform

`structure-uniform` は、`character-dictionary` の骨格を使って、終端イベントを保ちながら均一なタイミングで出力する比較方式である。

ここでは、文字構造の効果を見たい。つまり「字形の制約だけでどこまで行けるか」を確認する段階である。

### structure-motion

`structure-motion` は、文字構造に運動時間と終端変化を加えた方式である。

この段階では、`motion-synthesis` と `plotter-export` が入る。研究上は「構造だけ」より一段上で、自然な速度変化や終筆の抜きが見えるかを評価する。

### ScanMetadata

`ScanMetadata` は、実機スキャンの条件を記録するメタデータである。スキャナ、解像度、紙種、ペン種、プロッタ名、撮影日時などを含む。

スキャン画像だけでは再現条件が分からない。評価では、成果物そのものと同じくらい、どの条件で取得したかが重要である。

### profile_id

`profile_id` は、writer profile や baseline profile を識別する ID である。

将来の個人差研究では、同じ文字でも筆者ごとの癖を比較したい。そのため、入力文や seed だけでなく、どの profile を使ったかも実験条件になる。

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
