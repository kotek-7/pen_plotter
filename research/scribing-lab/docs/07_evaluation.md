# 07 Evaluation

## 目的

「手書きと区別がつかない」を、再現可能な評価に分解する。主観評価だけでは研究の反復が遅いため、自動評価と人間評価を併用する。

この評価基盤は、研究を反復するための最初の必須基盤である。生成モデルの実装より先に、実験設定、成果物、評価結果、失敗分類、次実験提案を記録できる状態にする。

## Experiment Requirements

各実験では次を必ず残す。

- experiment id。
- 仮説。
- 入力テキスト。
- generator version。
- writer profile id。
- random seed。
- exporter target。
- generated trajectory。
- preview artifact。
- G-code または SVG。
- plotted scan artifact。実機未使用の実験では `null` とし、理由を残す。
- metrics。
- 失敗分類。
- 次に試す変更。

motion model や neural variation の本格実装は、評価基盤がこれらを保存できる状態で進める。

## 評価層

| 層 | 指標 | 目的 |
|---|---|---|
| 字形 | bbox, IoU, chamfer distance, OCR/認識器 | 文字として読めるか |
| 軌跡 | DTW, DDTW, stroke count | 実筆軌跡に近いか |
| 運動 | velocity peaks, acceleration, jerk | 等速機械感がないか |
| spacing | 字間、行方向 drift、接続性 | 文として自然か |
| writer | writer classifier, style consistency | 同一筆者らしいか |
| 実機 | scan mismatch, line quality, pen-up artifact | 紙面出力で破綻しないか |
| 人間評価 | ABX, Turing-style | 判別されにくいか |

## Experiment Registry

実験はファイルまたは軽量 DB で管理する。初期は JSON Lines でよい。

```json
{
  "experiment_id": "exp-000001",
  "hypothesis": "Sigma timing reduces uniform machine feel.",
  "input_text": "永",
  "generator": "motion-mvp",
  "writer_profile": "baseline-neat",
  "seed": 1,
  "artifacts": {
    "trajectory": "artifacts/exp-000001/trajectory.json",
    "preview": "artifacts/exp-000001/preview.png",
    "gcode": "artifacts/exp-000001/output.gcode",
    "plotted_scan": null,
    "scan_metadata": null
  },
  "metrics": {
    "stroke_count": 5,
    "velocity_peak_count": 7,
    "penup_distance_mm": 32.4
  },
  "failure_tags": ["terminal-too-uniform"],
  "next_action": "increase harai pressure decay and rerun same seed set"
}
```

## Failure Taxonomy

失敗を同じ語彙で分類できるよう、タグを固定する。

- `unreadable`: 文字として読みにくい。
- `wrong-stroke-order`: 筆順が破綻している。
- `too-uniform`: 等速・均一で機械的。
- `over-jittered`: 震えが強すぎる。
- `spacing-unnatural`: 字間や行方向が不自然。
- `terminal-too-uniform`: 払い・はね・とめの差が弱い。
- `penup-artifact`: ペンアップ移動が紙面に悪影響を出している。
- `plotter-unsafe`: Z 値、速度、範囲が危険。
- `profile-inconsistent`: 同一 profile 内の癖が一貫しない。
- `too-font-like`: 手書きではなくフォント輪郭由来に見える。
- `skeleton-too-rigid`: 文字骨格が硬く、手書きの崩れが足りない。
- `line-too-mechanical`: 文章や行全体として機械的に揃いすぎている。
- `paragraph-spacing-unnatural`: 短文・複数行で字間や行間の揺れが不自然。
- `repeated-char-too-identical`: 同じ文字の反復が不自然に同一である。
- `scan-mismatch`: preview や trajectory の想定と実機スキャンが大きく異なる。
- `plotter-line-quality-bad`: ペン、紙、速度、Z の組合せで線質が崩れている。

## Baseline

比較対象を固定する。

1. `baseline-outline`: 既存の font outline + jitter/wobble。
2. 筆順保持の構造辞書 + 等速。
3. 構造辞書 + Sigma-Lognormal。
4. 構造辞書 + Sigma-Lognormal + writer profile。
5. 神経 shape variation 追加版。

`baseline-outline` は、現行 `scripts/text_to_gcode.py` と `src/textplot` / `src/gcode`
を研究上の比較対象として固定した名前である。以後の方式は、同じ入力、同じ seed、
同じ artifact/report 形式で比較する。

## Scan Artifacts

実機評価を行う実験では、次の artifact を experiment ID に紐付ける。

```text
plotted_scan.png
scan_metadata.json
plotter_config.json
pen_profile.json
paper_profile.json
```

`scan_metadata.json` には、scanner または camera、resolution、crop method、pen type、
paper type、plotter、date、operator note を残す。実機未使用の実験では、
`plotted_scan` を `null` にし、report に未使用理由を記録する。

## ABX 評価

評価者には、生成方法を伏せて紙面またはスキャン画像を提示する。

質問:

- どちらが人間の手書きに見えるか。
- どちらが同じ筆者の文字に見えるか。
- どちらが機械的に見えるか。

最小設計:

- 評価者 30 人。
- 各評価者 40 ペア。
- 文字単位と短文単位を混ぜる。

## 自動評価データセット

初期セット:

- `永`
- `あいうえお`
- `今日はよい天気です。`
- `春の川をゆっくり歩く。`
- `本日はありがとうございました。`

辞書・運動モデルの局所評価では、ひらがな 10 字、頻出漢字 20 字を追加する。

拡張セット:

- ひらがな全字。
- カタカナ全字。
- 頻出漢字 300 字。
- 文脈付き短文 50 種。

## CI ゲート候補

- 同一 seed の生成結果が一致する。
- stroke count が不自然に増減しない。
- 速度分布が等速に退行しない。
- pen-up 距離が異常に伸びない。
- spacing variance と baseline drift が固定入力セットで極端に退行しない。
- repeated character similarity が高すぎない。
- G-code の Z 値が安全範囲を超えない。
- experiment registry に成果物と metrics が記録されている。
- writer profile id と generator version が未記録の成果物を失敗扱いにする。

## Review Packet

次の判断を行うため、各実験のレビュー入力は次の束にする。

- 実験設定 JSON。
- preview 画像。
- plotted scan 画像。未使用時はその理由。
- trajectory summary。
- metrics summary。
- G-code safety summary。
- 前回実験との差分。
- failure tags。

レビューの役割は、主観的な採点だけではなく、次に検証すべき仮説と最小変更を提案することである。

## 参照

- [CASHG](https://arxiv.org/abs/2604.02103)
- [IAM-OnDB](https://fki.tic.heia-fr.ch/databases/download-the-iam-on-line-handwriting-database)
- [DeepWriteSYN](https://arxiv.org/abs/2009.06308)
