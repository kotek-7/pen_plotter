# 02 Data Assets

## 方針

データ資産は、運動データ、構造データ、オフライン画像データ、補助データに分ける。すべてを同じ学習データとして扱わず、用途とライセンスを分離する。

## 正準データ契約

すべてのオンラインデータは次へ変換する。

```text
sample_id
writer_id
char_or_text
x_mm
y_mm
t_ms
pen_state
pressure_optional
source
license_scope
```

pressure がないデータでは `pressure_optional = null` とする。後段の pressure model は仮想 pressure として別に生成する。

## TUAT Nakagawa Lab. HANDS

用途:

- 日本語オンライン手書きの主データ候補。
- 文字単位の運動 prior。
- writer profile 学習。
- 字間、行方向、文脈依存 spacing の解析。

確認事項:

- 公式ページに `HANDS-nakayosi_t-98-09` と `HANDS-kuchibue_d-97-06` が掲載されている。
- 利用には条件があり、再配布は禁止される。
- 商用利用や組織外利用には別条件がある。

リスク:

- 入手手続きと利用条件。
- 研究成果物にデータそのものを含められない。
- CI に実データを置けない可能性が高い。

参照:

- [TUAT database index](https://web.tuat.ac.jp/~nakagawa/database/index.html)
- [TUAT database conditions example](https://web.tuat.ac.jp/~nakagawa/database/en/kondate_proc.html)

## 自前オンライン筆記データ

TUAT がすぐ使えない場合の代替主データ。Wacom、iPad、Android stylus、またはブラウザ Pointer Events で収集する。

最小収集設計:

- writer 10 人。
- ひらがな 46 字。
- 頻出漢字 100 字。
- 短文 10 文。
- 各 writer 2 セッション。

収集すべき情報:

- 筆点時系列。
- pen-up/down。
- 筆圧が取れる端末では pressure。
- device id と sampling rate。
- 同意情報。

## IAM-OnDB

用途:

- 英語オンライン手書きの比較データ。
- writer-id 付き sequence model の事前学習。
- evaluation harness の実装検証。

制約:

- 日本語字形には直接使わない。
- ライセンス条件を確認し、研究用途に限定する。

参照:

- [IAM-OnDB download page](https://fki.tic.heia-fr.ch/databases/download-the-iam-on-line-handwriting-database)

## ETL Character Database

用途:

- オフライン画像としての字形評価。
- 生成画像の識別器・OCR 評価の補助。
- stroke recovery 研究の比較用。

制約:

- 時間軸がないため、運動生成の主データにはしない。
- データ再配布条件を確認する。

参照:

- [ETL Character Database](https://etlcdb.db.aist.go.jp/?lang=en)

## Quick, Draw!

用途:

- timestamped vector drawing の前処理パイプライン検証。
- 汎用的な tremor/noise/segmentation の補助実験。

制約:

- 日本語文字ではない。
- writer-id が主用途として整備されていない。
- 主学習データにはしない。

参照:

- [Quick Draw dataset overview](https://www.sourcepulse.org/projects/1566647)

## KanjiVG

用途:

- 筆順。
- stroke path。
- stroke type。
- 部品構造。

制約:

- CC BY-SA 3.0。
- 生成辞書や派生データを配布する場合、継承条件が問題になる可能性がある。

参照:

- [KanjiVG GitHub](https://github.com/KanjiVG/kanjivg)

## MJ 文字情報一覧表

用途:

- UCS/IVS/MJ 文字図形名の対応。
- 異体字管理。
- 人名漢字などの文字同定。

制約:

- CC BY-SA 2.1 JP。
- 文字図形そのものではなく対応表として使う。

参照:

- [MJ 文字情報一覧表](https://moji.or.jp/mojikiban/mjlist/)

## データ取得順

1. KanjiVG を取得して小規模辞書を構築する。
2. 自前オンライン筆記データを最小収集する。
3. TUAT の利用可否を確認する。
4. IAM-OnDB で evaluation harness と style encoder の実験を行う。
5. ETL は画像評価の補助として追加する。
