# Evaluation Harness

手書きらしさを自動評価と人間評価で測る研究プロジェクトである。

詳細は [research_plan.md](research_plan.md) を参照する。

## 現在の最小実装

このプロジェクト配下に、評価駆動研究の最初の基盤を配置している。

- `ExperimentRegistry`: JSONL の experiment registry。
- `ArtifactStore`: 実験 ID ごとの成果物保存。
- `compute_trajectory_metrics`: 最小 trajectory metrics。
- `preview_metrics`: preview の画像統計と SSIM 近似比較。
- `render_markdown_report`: 実験レビュー向け report。
- `FAILURE_TAGS`: 固定 failure taxonomy。
- `baseline-outline-batch`: `fixed` / `review` / `wide` を選べる batch runner。
- `review_packet.md`: batch 実験のレビュー束。
- `compare`: baseline との差分比較レポート。
- `compare-preview-fixed-inputs`: 固定評価入力セットの preview 差分レポート。
- `recommend-preview-fixed-inputs`: preview 候補の選定と次の改版案。
- `propose-preview-fixed-inputs`: preview 選定候補からの改版提案。
- `preview-iteration-fixed-inputs`: preview 比較から改版提案までの 1 ラウンド集約。
- `apply-preview-revision-fixed-inputs`: preview 改版案を適用して再生成する 1 ラウンド実行。
- `summarize-preview-revision-loops`: 複数ラウンドの設計原理と失敗傾向の要約。
- `propose-stable-writer-profiles`: 要約から安定候補 profile 群を生成。
- `evaluate-stable-writer-profiles`: 安定候補 profile 群を固定入力セットで評価し、採択候補を選定。
- `evaluate-data-driven-writer-prior`: JSONL のオンライン筆記サンプルから推定した prior を評価。
- `offline-review`: 人間レビュー前の artifact / metrics ベースの候補整理。
- `human-review-packet`: 生成 preview / metrics の目視レビュー束。
- `human-feedback-loop`: packet, response template, validation summary, calibration summary, next actions を 1 つにまとめた人間主観 FB ループ束。
- `human-review-agreement`: reviewer 間の decision / reason tag の一致度集計。
- `human-feedback-ui`: packet を画面に並べて response を入力・検証・保存する Qt UI。
- `preview-review-packet`: preview を主軸にしたレビュー束の別名。
- `validate-human-review`: 目視レビュー response の検証と集計。
- `plot-ready-packet`: accepted record の G-code / safety / preview 束。
- `ScanMetadata`: 必要時だけ使う実機監査用 metadata schema。
- `AbxItem` / `AbxResponse`: 小規模 ABX 評価の最小 schema。
- `Bradley-Terry`: ABX の paired comparison を順位化する比較モデル。

固定評価入力セットは、かな・漢字・数字・Latin・記号を含む拡張コーパスを使う。
広い評価セットは、常用文字を広く含む 100 種類以上の文字・文章を扱う。
人間レビューはこの広い評価セットを大きめの束にして、`human-feedback-ui` で連続的に確認する。
`human-review-packet --target-count 72` のように束の大きさを調整できる。
preview / ABX は人間レビューの前段で候補を絞る補助として使う。

## 採用した外部手法

- SSIM: [Wang et al., 2004](https://ece.uwaterloo.ca/~z70wang/publications/ssim.pdf)
  - preview の画像比較に使う。
- Cohen's kappa: [Cohen, 1960](https://doi.org/10.1177/001316446002000104)
  - reviewer 間の一致度に使う。
- Bradley-Terry: [Bradley & Terry, 1952](http://www.jstor.org/stable/2334029)
  - ABX の paired comparison を順位化する。
- uncertainty sampling: [survey](https://arxiv.org/abs/2210.10109)
  - human review の代表選定で不確実な候補を優先する。

## 実行

`research/scribing-lab/projects/evaluation-harness` を作業ディレクトリにして実行する。

```sh
python3 -m evaluation_harness smoke --root runs/smoke
```

`self-check` は、固定入力セットに対する baseline / candidate 比較、review、plot-ready までの経路をまとめて検証する。
`Reference Basis` には KanjiVG、IAM-OnDB、DeepWriting、DeepWriteSYN、sigma-lognormal、CASHG を含め、構造・spacing・運動・style 分離の観点を固定している。

```sh
python3 -m evaluation_harness self-check --root runs/self-check
```

`goal-audit` は、評価器の終了条件を監査する。
同じ seed で self-check を 2 回実行して主要サマリの再現性を確認し、
preview の SSIM 近似、human feedback loop、ABX の順位化が接続されているかを
1 つの JSON / Markdown にまとめる。

```sh
python3 -m evaluation_harness goal-audit --root runs/goal-audit
```

終了条件の最小判定は次の 5 点である。

- fixed input の self-check が再実行可能で、主要サマリが一致する。
- preview comparison に `ssim_proxy` がある。
- human feedback loop が response summary, calibration summary, agreement summary を返す。
- 不確実な候補が human review の代表選定に入る。
- ABX が `bradley_terry_ranking` を返す。

現行アプリの `font outline + jitter/wobble` を `baseline-outline` として固定し、
registry / artifact / report に保存する場合:

```sh
python3 -m evaluation_harness baseline-outline \
  --root runs/baseline-outline \
  --experiment-id exp-baseline-000001 \
  --input-text "永" \
  --seed 1
```

固定・レビュー・広い評価入力セットを複数 seed で一括登録する場合:

```sh
python3 -m evaluation_harness baseline-outline-batch \
  --root runs/baseline-outline \
  --seeds 1,2,3 \
  --input-set wide
```

registry 内の候補実験を `baseline-outline` と比較する場合:

```sh
python3 -m evaluation_harness compare \
  --root runs/baseline-outline \
  --baseline-generator baseline-outline
```

固定・レビュー・広い評価入力セットの比較完備性を確認する場合:

```sh
python3 -m evaluation_harness compare-fixed-inputs \
  --root runs/baseline-outline \
  --seeds 1,2,3 \
  --input-set wide
```

固定・レビュー・広い評価入力セットの preview 由来の差分を確認する場合:

```sh
python3 -m evaluation_harness compare-preview-fixed-inputs \
  --root runs/baseline-outline \
  --seeds 1,2,3 \
  --input-set wide
```

`compare-preview-fixed-inputs` は、baseline と candidate の `preview` artifact の
存在、サイズ、SHA-256 を比較し、preview が更新されたかを記録する。

`recommend-preview-fixed-inputs` は、preview がある候補の中から各 input / seed ごとに
最小 failure tag の候補を選び、次に直すべき profile / layout / motion の提案を出す。

`propose-preview-fixed-inputs` は、選定候補ごとに `motion`、`layout`、`dictionary`、
`profile`、`safety` のどれを変えるべきかを revision plan として出力する。

`preview-iteration-fixed-inputs` は、preview 差分、候補選定、改版提案を 1 ラウンドとして
束ね、次の実験に渡すための summary を保存する。

`apply-preview-revision-fixed-inputs` は、選定候補の `revision plan` を derived profile に
反映し、同じ input / seed で再生成した結果を registry に追加する。
このループでは、before / after の比較に加えて、`design_principles` と
`comparison_summary` を記録し、どの変更が効いたかを後から追えるようにする。

`summarize-preview-revision-loops` は、複数の revision loop packet をまとめて、
安定して繰り返し出る design principle と failure tag を抽出する。

`propose-stable-writer-profiles` は、安定して効く design principle から
derived writer profile 候補を作る。

`evaluate-stable-writer-profiles` は、候補 profile を固定評価入力セットへ流し、
baseline と比較して新しい failure tag が出ない候補だけを採択する。
評価結果は `selected_profile_ids` と `selection_summary` に保存される。

`evaluate-data-driven-writer-prior` は、`samples.jsonl` から推定した derived profile を
固定評価入力セットへ流し、baseline と比較して prior が実際に改善するかを確認する。

生成 preview の前段で、registry 内の metrics / failure tags から次の調整候補を出す場合:

```sh
python3 -m evaluation_harness offline-review \
  --root runs/structure-motion
```

`offline-review` は `offline_review.md` と `offline_review.json` を生成する。
`too-uniform`、`line-too-mechanical`、`over-jittered`、`plotter-unsafe` などを
preview / trajectory / G-code safety の前段評価として扱い、次に調整する対象を記録する。

自動評価を通った候補を生成 preview ベースで目視レビュー用に束ねる場合:

```sh
python3 -m evaluation_harness human-review-packet \
  --root runs/structure-motion
```

`human-review-packet` と `preview-review-packet` は、代表 seed の preview、主要 metrics、
failure tags と、input ごとの全 preview path を `human_review_packet.md` / `.json`
または `preview_review_packet.md` / `.json` に保存する。
`--target-count` で代表項目数を増やせるので、大きめの人間レビュー束をそのまま作れる。

```sh
python3 -m evaluation_harness human-feedback-loop \
  --root runs/structure-motion
```

`human-feedback-loop` は response template 付きの統合束を `human_feedback_loop.md` / `.json`
に保存する。responses を渡すと、検証結果と次アクションも同じ束に入る。
`--target-count` を指定すると、UI で扱う人間レビュー束の大きさを増やせる。

`human-abx-packet` は preview 由来の候補を ABX 形式にまとめる。
`--recommendation-json` を使うと、既存の `recommend_preview_fixed_inputs` 生成物を再利用して
再計算を避けられる。
`--recommendation-json` を使う場合は `--root` なしでも直接実行できる。
`--focus-areas layout,motion` のように指定すると、ABX 用の束を focus area で絞り込める。
`--max-items 36` を併用すると、口頭 FB 用の小さな束を作りやすい。

`human-abx-feedback-loop` は ABX packet と response をまとめて、候補比較の集計、
response template、次アクションを 1 つの束にする。responses がない場合は、
そのまま記入用テンプレートとして使える。
`--recommendation-json` を使うと、`human-abx-packet` を挟まずに recommendation から
直接 feedback loop を作れる。`--focus-areas layout,motion` と `--max-items 36` を
合わせると、小さな口頭 FB 用の束にしやすい。
`--max-items` で代表項目数を絞れるので、口頭 FB 用には小さめの束を作る。
`--template-json-output` で、埋め戻し用の response template を別ファイルに保存できる。
`abx-workbook` は、候補ごとの表形式 workbook を出して、`choice` / `confidence` / `note`
を埋めやすくする。
`abx-workbook` の JSON を編集して `choice` と `confidence` を入れると、
responses JSON としてそのまま戻せる。
`--recommendation-json` を使う場合は `--root` なしでも直接実行できる。
`--recommendation-json` と `--focus-areas layout,motion` を使うと、packet を挟まずに
focused workbook を作れる。
`human-abx-bundle` は、focused packet / workbook / feedback loop / response template /
responses scaffold を 1 回でまとめて出力する。`layout` と `motion` を分けて回すときに使う。
`--output-dir` と `--output-prefix` を指定すると、束の保存先と名前をそのまま揃えられる。
responses を回収した後は `human-abx-bundle-followup` で、response summary / feedback loop /
revision plan / revision run を bundle からまとめて生成できる。
`--workbook-json` を省略すると、bundle 内の `<prefix>_workbook.json` を使う。
`--responses-json` を使う場合は、その JSON を直接読み込める。
workbook には completed / pending の row 数と completion ratio も保存される。
follow-up は正規化した `<prefix>_responses.json` も bundle に保存する。
`--pending-only` を付けると、未回答行だけを抜き出した pending workbook も保存する。
同じく `pending packet` も保存されるので、そのまま次ラウンドの bundle に使える。
`--next-bundle-dir` と `--next-bundle-prefix` を指定すると、pending packet から次ラウンド bundle を直接保存できる。
`--chain-next-bundle` を付けると、`_v1` から `_v2` のように bundle 名を自動で進められる。
`bundle-prefix` に `_vN` を付けていても、同じ中身の prefix へフォールバックして読む。
`human-abx-bundle-chain-status` は、bundle の連番ごとの packet / workbook / completion ratio を一覧化する。
`human-abx-bundle-sweep-status` は、`goal-wide` 配下の bundle 系をまとめて一覧化する。
どちらの status も、`revision_rerun_count` と `revision_preview_changed_count` を含む。
```sh
python3 -m evaluation_harness human-abx-bundle-chain-status \
  --bundle-dir runs/goal-wide/layout_bundle_v1 \
  --bundle-prefix layout_abx
```

ABX の回答 JSON を集計する場合は `validate-abx-responses` を使う。
packet と responses を渡すと、choice 集計、Bradley-Terry、次アクションを出力する。
ABX は人間レビューの前段で候補を絞る補助として使う。

ABX feedback loop から preview 修正案へ戻す場合は `abx-revision-plan` を使う。
feedback loop JSON を渡すか、packet JSON と responses JSON を渡すと、代表 item ごとの
proposed_changes と次の実験ヒントをまとめる。
`--recommendation-json` と `--focus-areas layout,motion` を使うと、packet を挟まずに
focused な revision plan を作れる。

`abx-revision-run` は、ABX revision plan をそのまま実行して、選ばれた候補を
修正版 profile で再生成する。`feedback-loop-json` を渡すか、`packet-json` と
`responses-json` を渡して、同じ流れで preview 再実行まで進められる。
実行結果には `rerun_count` と `preview_changed_count` が出る。
`--recommendation-json` と `--focus-areas layout,motion` を使うと、focused な packet
から直接 rerun まで進められる。

```sh
python3 -m evaluation_harness human-feedback-ui \
  --root runs/structure-motion
```

`human-feedback-ui` は代表 preview を画面上で切り替えながら、`accept` / `reject` /
`needs-tuning` と reason tags を入力し、`human_review_responses.json` と
`human_review_response_summary.json` を保存する。`Revision Brief` タブと `Export Brief`
ボタンで、note をそのまま次回修正用の brief に書き出せる。`Export Preview Run`
ボタンを使うと、今開いている packet の input / seed 軸に沿って brief と plan を
まとめて preview rerun まで出力できる。UI は Qt ベースなので、日本語と英字の表示品質が
Tkinter 版より安定している。`Preview Run` タブでは、現在の brief から作った preview
revision plan をその場で確認できる。
`Export Review Bundle` は、responses / brief / plan / preview run をまとめて保存する。
起動時に保存先を明示したい場合は `--preview-run-json` と `--preview-run-markdown` を指定する。
`Revision Plan` は `human-feedback-preview-revision-plan` で preview revision plan に直結できる。
その plan は `apply-preview-revision-fixed-inputs --revision-plan-json ...` に渡して rerun まで進められる。

`--target-count` を指定すると、`root` から束を作る場合の代表項目数を増やせる。
各 item の note は summary と next_actions にそのまま残るので、UI で書いた改善点を次回の修正に使いやすい。

既存の review packet から開く場合は `--packet-json` を使う。既存の回答を読み込んで
続きからレビューする場合は `--responses-json`、保存先を明示したい場合は
 `--summary-json` を併用する。

`human-feedback-loop` は、同じ review packet に加えて response template と validation summary を
1 つの `human_feedback_loop.md` / `.json` にまとめる。responses を渡すと、
`accept` / `reject` / `needs-tuning` の集計、自由記述の note 要約、revision brief、次アクションまで出力する。
note は summary と revision brief にそのまま残るので、UI で書いた改善点を次回の修正に使いやすい。
`--brief-only` を付けると、次回修正用の brief を優先して出力できる。

目視レビュー結果を packet と照合して集計する場合:

```sh
python3 -m evaluation_harness validate-human-review \
  --packet-json runs/structure-motion/human_review_packet.json \
  --responses-json runs/structure-motion/human_review_responses.json
```

response は `accept`、`reject`、`needs-tuning` のいずれかを記録する。
`validate-human-review` は代表 record との対応、未回答、未知 ID、重複を検証し、
`can_proceed_to_plot` を summary に保存する。

実機送信前に accepted record の G-code と safety を束ねる場合:

```sh
python3 -m evaluation_harness plot-ready-packet \
  --root runs/structure-motion \
  --human-summary-json runs/structure-motion/human_review_response_summary.json
```

`plot-ready-packet` は G-code を自動送信しない。`gcode_safety_ok` と
`gcode_safety` artifact を再確認し、xDraw A4 のホーミング、`G92 X0 Y297 Z0`、
Z 軸ペン制御を checklist として保存する。scan は必要時のみ追加する監査手段とする。

必要時だけ実機スキャンを既存 experiment に紐付ける場合:

```sh
python3 -m evaluation_harness attach-scan \
  --root runs/plotter-export-final \
  --experiment-id exp-motion-i01-s001 \
  --scan-path plotted_scan.png \
  --metadata-json examples/scan_metadata.example.json
```

`attach-scan` は、対象 experiment の `gcode_safety_ok` が `1` で、`gcode_safety`
artifact が存在する場合だけ登録する。実機送信前に `gcode_safety.json` の
`ok: true` と `violations: []` を確認する。通常の比較ループは preview を主軸に回す。

生成物は `runs/` に保存される。`runs/` は実験出力なので git 管理しない。

## テスト

既存リポジトリの仮想環境を使う場合:

```sh
cd /home/kotek/dev/pen_plotter/research/scribing-lab/projects/evaluation-harness
/home/kotek/dev/pen_plotter/.venv/bin/python -m pytest
```
