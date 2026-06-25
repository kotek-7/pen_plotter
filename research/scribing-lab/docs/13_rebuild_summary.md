# 13 Rebuild Summary

## 目的

この文書は、`scribing-lab` の大規模な再構成の動機、再構成前後の状態、現在の研究領域の見取り図をまとめる。

再構成の主目的は、評価基盤を先に固める進め方をやめ、まず engine を実行して `runs/` に成果物を残し、preview と G-code を素早く確認できる研究基盤へ戻すことである。

## 再構成の動機

旧構成では、研究の中心が evaluation-harness と個別 component project に寄りすぎていた。

- 実験条件、入力、parameter、registry、failure taxonomy が先に規格化され、出力を見ながら研究する速度が落ちていた。
- `character-dictionary`、`motion-synthesis`、`writer-profile`、`plotter-export` などが独立 project として分かれていたが、各層単体では実行・評価しづらかった。
- 実際の研究単位は component ではなく、それらを組み合わせて text から trajectory を生成する engine 全体だった。
- preview や実機試し書きよりも、実験台帳と評価 schema の整備が先行し、研究対象である筆記出力そのものを見にくくなっていた。

そのため、component 分割を研究管理の単位にするのではなく、engine を研究上の実行単位とし、内部構造は各 engine が自由に持つ形へ戻した。

## 再構成前

再構成前の中心は `projects/` だった。

```text
projects/
  character-dictionary/
  motion-synthesis/
  writer-profile/
  plotter-export/
  evaluation-harness/
  neural-variation/
```

この構成は、研究領域を辞書、運動生成、筆者 profile、plotter export、評価基盤に分ける発想だった。個別要素の整理には有効だったが、text から実際の出力までを通して確認する導線が重くなりやすかった。

特に evaluation-harness は、registry、artifact store、metrics、report、human review などを早期にまとめようとしていた。この方向は将来的な評価基盤としては有用だが、初期の engine 探索では過剰だった。

旧 `projects/` は現在 `projects-archived/` に移している。中の README、research plan、CLI、schema、テストは旧方針に基づく参照用アーカイブであり、現行実装の基盤ではない。

## 再構成後

現行構成では、研究の流れを次の 1 本に戻している。

```text
text
  -> engine
  -> trajectory.json
  -> preview.svg
  -> output.gcode / safety.json
  -> viewer / plotter trial
```

ディレクトリ構成は次の通り。

```text
engines/            text -> trajectory を担う engine 群
runner/             engine を実行し runs/ に trajectory と memo を保存する
renderer/           trajectory から preview.svg を生成する
exporter/           trajectory から output.gcode と safety.json を生成する
runs/               実行結果の置き場。git 管理しない
evaluation/         runs を読む viewer と、将来の評価基盤
docs/               研究文書
projects-archived/  旧 projects の参照用アーカイブ
```

`runner` は engine 実行に集中する。preview と G-code は runner から切り離し、`renderer` と `exporter` が `trajectory.json` を読む。これにより、engine は筆記軌跡生成に集中し、描画スタイルや実機 export の調整を engine から独立して進められる。

`runs/` の各 run は、厳密な実験 record ではなく、出力確認の単位である。標準の directory 名は `YYYYMMDDTHHMMSS_<name>` とし、実行条件は `memo.md` に軽く残す。

## 新旧コードと文書の立ち位置

再構成後のコードベースには、現行基盤、参照用アーカイブ、旧方針を含む研究文書が共存している。読むときは立ち位置を分ける。

### 現行の実装基盤

次の directory は、現在の研究実装で使う。

```text
engines/
runner/
renderer/
exporter/
evaluation/
runs/
Makefile
```

`engines/`、`runner/`、`renderer/`、`exporter/`、`evaluation/` は、それぞれ独立した最小基盤として扱う。`Makefile` はこれらを束ねる薄いランチャであり、各 project の独立性を崩さない。

新しい engine、runner の契約変更、preview 生成、G-code export、viewer は、この現行基盤に対して行う。

### 参照用アーカイブ

`projects-archived/` は旧 `projects/` の移動先である。

```text
projects-archived/
  character-dictionary/
  motion-synthesis/
  writer-profile/
  plotter-export/
  evaluation-harness/
  neural-variation/
```

ここにある code、README、research plan、schema、test は旧方針に基づく。現行方針とは意図的にズレているため、新規実装の依存先にしない。

読む目的は、文字構造、運動生成、writer profile、plotter export、評価設計などの知見を取り出すことである。必要な考え方だけを現行 engine や周辺基盤へ移植する。

### 旧方針を含む研究文書

`docs/00_overview.md`、`docs/07_evaluation.md`、`docs/09_roadmap.md`、`docs/10_research_flow.md`、`docs/11_glossary.md` には、旧 `projects/` 分割や evaluation-harness 中心の方針が残っている。

これらは研究の背景、評価観点、用語、候補設計を読む資料として残す。現在の実行導線や実装単位の正本ではない。現在の実装導線は、この文書、`README.md`、各現行 project の README、実際の CLI を優先する。

### ルートアプリケーション

リポジトリ直下の `src/`、`scripts/`、`tests/` は、既存の xDraw A4 向け軽量アプリケーションである。

`research/scribing-lab/` は、この既存アプリケーションから独立した研究領域として扱う。既存アプリの G-code 生成や実機送信の知見は参考にするが、研究基盤の実装依存にはしない。

## 現在の CLI

通常は `research/scribing-lab/Makefile` を使う。

```sh
cd research/scribing-lab
make sync
make run TEXT="今日はよい天気です。" NAME=example
make convert RUN=runs/<run-dir>
make view RUN=runs/<run-dir>
```

各 project を直接使う場合は、それぞれの directory で `uv run` する。

```sh
cd research/scribing-lab/runner
uv run scribe-run "今日はよい天気です。" --name example

cd ../renderer
uv run scribe-render ../runs/<run-dir>

cd ../exporter
uv run scribe-export ../runs/<run-dir>

cd ../evaluation
uv run scribe-view ../runs/<run-dir>
```

CLI 名は短く保つ。`scribe-run`、`scribe-render`、`scribe-export`、`scribe-view` はそれぞれの責務をそのまま表す。

## 現在の成果物契約

`runner` が生成する標準成果物は次の通り。

- `input.txt`: engine に渡した入力テキスト
- `memo.md`: engine、seed、parameter snapshot などを記録する自由形式に近いメモ
- `trajectory.json`: 正準軌跡

`renderer` と `exporter` が追加で生成する成果物は次の通り。

- `preview.svg`: trajectory の目視確認用 SVG
- `output.gcode`: xDraw A4 / GRBL 用 G-code
- `safety.json`: 紙面範囲、Z、feed などの最低限の安全確認結果

`evaluation` は現時点では評価 schema を固定しない。まず `scribe-view` で `runs/` の preview をズーム・パン付きで確認する。

## 設計上の境界

現行の境界は次の通り。

- `engines/`: engine ごとの生成方式を置く。内部では文字構造、layout、motion、profile などを自由に分けてよい。
- `runner/`: engine をロードし、text、seed、params を渡し、trajectory と memo を保存する。
- `renderer/`: trajectory を preview SVG にする。見た目の調整はここに閉じる。
- `exporter/`: trajectory を plotter 用 G-code にする。実機安全境界はここに閉じる。
- `evaluation/`: `runs/` を読む。評価 schema や metrics は、出力の実態が見えてから追加する。

この分け方は、旧 `projects/` の component 分割とは異なる。component は engine 内部の tidy を保つために使い、研究管理上の単位は engine と run に寄せる。

## 今後の進め方

次の段階では、旧 `projects-archived/` から概念だけを選んで、新しい engine に取り込む。

- `character-dictionary`: 文字構造と筆順の知見
- `motion-synthesis`: 速度変化、終筆、時間軸の知見
- `writer-profile`: 筆者差分を parameter 化する考え方
- `plotter-export`: 実機安全と G-code 生成の知見
- `evaluation-harness`: 後段評価、主観評価、比較設計の知見

ただし、旧 code を直接基盤に戻さない。まずは 1 つの engine が text から自然な trajectory を出し、それを `renderer`、`exporter`、`viewer` で確認できる状態を保つ。

## 判断基準

今後の変更は、次の基準で判断する。

- 出力を見て研究を進めやすくなるか。
- engine の実行単位が明確に保たれるか。
- preview と G-code の調整が engine から独立しているか。
- `runs/` が過度な実験台帳にならず、成果物置き場として使えるか。
- 評価 schema を早く固定しすぎて、engine 間の特徴差を潰していないか。
