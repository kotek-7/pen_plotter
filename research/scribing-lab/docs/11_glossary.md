# 11 Glossary

この文書は、`scribing-lab` で頻出する用語の前提知識をまとめた用語集である。

`10_research_flow.md` はフローの実務ガイドとして短く保ち、この文書に詳細を集約する。

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
