# 11 Glossary

この文書は `scribing-lab` で頻出する用語をまとめる。語彙は「現行語彙」と「アーカイブ語彙」に
分ける。現行の実装・運用で使うのは現行語彙である。アーカイブ語彙は、`projects-archived/` の旧
コードや旧方針の docs（`00`、`07`、`09`、`10` など）を読むためだけに残す。

用語の正本は `13_rebuild_summary.md`、`README.md`、各現行 project の README、実際の CLI とする。

## 現行語彙

### engine

text から trajectory を生成する研究上の実行単位。`engines/<name>/engine.py` が
`generate(request)` を公開する。内部で文字構造・layout・motion などを自由に分けてよいが、
研究上は engine 全体を 1 つの生成方式として扱う。（旧語の `generator` に相当する。）

### runner

engine をロードして実行し、`runs/` に trajectory と run メタデータ（`input.txt`、`memo.md`）を
書く最小基盤。preview や G-code は生成しない。CLI は `scribe-run`。

### run

1 回の engine 実行の出力単位。`runs/YYYYMMDDTHHMMSS_<name>/` に置く。厳密な実験 record では
なく、出力を確認するための置き場であり、実行条件は `memo.md` に軽く残す。（旧語の experiment /
experiment_id に相当するが、台帳化はしない。）

### trajectory

engine が出力する正準軌跡。`x, y, t, pen_state, pressure` を持つ点の時系列で、
`runs/<run>/trajectory.json` に保存する。renderer / exporter はこのキーを直接読む。

- `x`, `y`: 紙面座標（mm, Y-UP, A4 左下原点）
- `t`: 累積時刻（ms, 単調非減少。ペン遷移で同値が連続しうる）
- `pen_state`: 接地状態（0=up / 1=down）
- `pressure`: 仮想筆圧（0..1）。xDraw に真の筆圧はないため、exporter が Z 高さや feed へ写像する

### motion

trajectory のうち時間軸に関わる側面。速度変化、終筆（払い・はね・とめ）の抜き、ペンアップの
間合いなどを指す。engine 内部の関心であり、独立した基盤ではない。finish 種別などの意味ラベルは
下流へ渡さず、engine が `pressure` と `t` の配分として trajectory に焼き込む。

### stroke

`pen_state == 1` が連続する 1 画ぶんの点列。renderer はこの単位でポリラインを描く。

### renderer

trajectory から `preview.svg` を生成する基盤。見た目の調整はここに閉じる。CLI は `scribe-render`。

### exporter

trajectory から `output.gcode` と `safety.json` を生成する基盤。実機（xDraw A4 / GRBL）の安全
境界はここに閉じる。CLI は `scribe-export`。（旧語では「実機命令への変換ラベル」を指したが、
現在は基盤そのものを指す。）

### preview

trajectory の目視確認用 SVG（`preview.svg`）。現在の主評価は、`scribe-view` でこれを確認する
ことである。

### safety

exporter が出す `safety.json`。紙面範囲・Z・feed が許容内かの最低限の検査結果。

### evaluation

`runs/` を読む領域。現在は `scribe-view` で preview を確認するのみで、評価 schema や metrics は
出力の実態が見えてから後段で設計する。

## アーカイブ語彙

次の語は旧 evaluation-harness と `projects/` 分割を前提にした語彙である。現行の実行導線では
使わない。`projects-archived/` や旧 docs を読むときの参照として残す。

### generator

生成方式のラベル。`baseline-outline`、`structure-uniform`、`structure-motion` のように方式単位で
固定していた。現行では `engine` がこの役割を担う。

### experiment registry / experiment_id / artifact store

実験を JSONL 台帳に記録し、一意の `experiment_id` で入力・seed・生成器・成果物・評価を紐付ける旧
基盤。現行では `run` と `runs/` がこれに代わるが、台帳化はしない。

### metrics / failure tags / report

自動メトリクス（速度ピーク数、jerk、字間ばらつき等）、失敗の型ラベル（`too-uniform`、
`plotter-unsafe` 等）、1 実験の要約文書。評価を先に固める旧方針の中心要素。現行では出力を見てから
設計する。

### baseline-outline / structure-uniform / structure-motion

旧 generator の方式名。font outline + jitter/wobble、文字構造のみで均一タイミング、文字構造に運動
時間と終端変化を加えた方式、という段階区分を表す。

### ScanMetadata / profile_id

実機スキャン条件のメタデータ（スキャナ、解像度、紙種、ペン種など）と、writer profile の識別子。
後段の実機評価・個人差研究で使う想定だった旧語。
