# Evaluation Harness Research Plan

## 目的

生成結果の改善を、感覚だけでなく再現可能な評価で判断する。字形、軌跡、運動、writer style、人間判定を分けて測る。

このプロジェクトは最初に着手する。評価 harness は単なる後処理ではなく、研究ループを成立させる実行基盤である。

## 背景

「人間らしい」は単一指標ではない。速度が自然でも文字が読めなければ失敗であり、字形が正しくても等速なら機械的に見える。評価 harness は研究全体のゲートになる。

## 主要仮説

1. 自動指標は主観評価の完全代替にはならないが、退行検知には有効である。
2. DTW だけでは spacing や速度自然性を捉えきれない。
3. 実機出力のスキャン画像評価が最終判断に必要である。
4. 評価結果と成果物を同じ ID で参照できれば、次実験の提案精度が上がる。
5. 評価基盤なしで生成モデルを改善すると、比較不能な成果物が増える。

## スコープ

含む:

- experiment registry。
- artifact store。
- report template。
- failure taxonomy。
- trajectory metrics。
- velocity metrics。
- spacing metrics。
- ABX 評価設計。
- baseline 比較。

含まない:

- 大規模クラウド評価基盤。
- 商用品質の判別器。
- 個人識別用途の classifier 公開。
- 主観評価だけに依存する採択判定。

## Research Workflow

研究は次の順序で進める。

1. 仮説を 1 つ書く。
2. 実験設定を registry に登録する。
3. generator/exporter を実行する。
4. preview、trajectory、G-code、ログを artifact store に保存する。
5. metric runner を実行する。
6. failure tags を付与する。
7. 実験レポートを生成する。
8. 次に試す最小変更を提案する。

この workflow が未実装の間は、motion-synthesis や neural-variation の本格実装に進まない。

## 最小データ構造

```json
{
  "experiment_id": "exp-000001",
  "hypothesis": "baseline generation is too uniform",
  "input_text": "永",
  "profile_id": "baseline-neat",
  "seed": 1,
  "generator": "baseline-outline",
  "exporter": "preview-only",
  "artifacts": {},
  "metrics": {},
  "failure_tags": [],
  "next_action": ""
}
```

## 実験

### Experiment 1: registry smoke test

最小の fake artifact を登録し、実験 ID、成果物、metrics、failure tags が対応付くことを確認する。

評価:

- schema validation。
- missing artifact detection。
- duplicate id detection。
- report generation。

### Experiment 2: baseline comparison

比較:

- font outline + jitter。
- structure + uniform speed。
- structure + motion model。

評価:

- 自動指標。
- 目視。
- 小規模 ABX。

### Experiment 3: motion metric validation

速度ピーク、加速度、jerk が人間評価と相関するかを見る。

### Experiment 4: profile consistency

同一 profile と異 profile の区別を評価する。

## 成果物

- metrics spec。
- experiment registry schema。
- artifact directory convention。
- failure taxonomy。
- evaluation dataset definition。
- ABX protocol。
- scan naming convention。
- baseline report template。

## 評価指標

- DTW/DDTW。
- velocity peak count。
- acceleration/jerk。
- spacing variance。
- baseline drift。
- ABX 正答率。

## リスク

- 自動指標に過適合する。
- 評価者数が少ないと結論が不安定。
- スキャン環境差が結果に混ざる。
- 評価結果なしに次実験を進める。
- failure tags が増えすぎて比較不能になる。

## 参照

- [CASHG](https://arxiv.org/abs/2604.02103)
- [DeepWriteSYN](https://arxiv.org/abs/2009.06308)
- [IAM-OnDB](https://fki.tic.heia-fr.ch/databases/download-the-iam-on-line-handwriting-database)
