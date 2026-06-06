# Evaluation Harness Research Plan

## 目的

生成結果の改善を、感覚だけでなく再現可能な評価で判断する。字形、軌跡、運動、writer style、人間判定を分けて測る。
主評価は G-code から生成した preview に置き、実機スキャンは必要時の監査に回す。

このプロジェクトは最初に着手する。評価 harness は単なる後処理ではなく、研究ループを成立させる実行基盤である。

## 背景

「人間らしい」は単一指標ではない。速度が自然でも文字が読めなければ失敗であり、字形が正しくても等速なら機械的に見える。評価 harness は研究全体のゲートになる。

## 主要仮説

1. 自動指標は主観評価の完全代替にはならないが、退行検知には有効である。
2. DTW だけでは spacing や速度自然性を捉えきれない。
3. 生成 preview の評価だけでも大半の比較ループは回せる。
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
- preview metrics。
- baseline-outline runner。
- repeated character metrics。
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
4. preview、trajectory、G-code、ログ、必要に応じて実機スキャンを artifact store に保存する。
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

この実験の前に、現行 `font outline + jitter/wobble` を `baseline-outline` として固定し、
次の入力セットで再実行可能にする。

- `永`
- `あいうえお`
- `今日はよい天気です。`
- `春の川をゆっくり歩く。`
- `本日はありがとうございました。`

比較:

- baseline-outline。
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

### Experiment 5: preview-centric review loop

生成 preview を主評価として人間レビューへ回し、必要時のみ実機監査を追加する。

評価:

- preview と experiment ID が紐付く。
- preview path、G-code、安全性、profile が metadata として残る。
- `preview-shape-odd` と `plotter-line-quality-bad` を failure tags として記録できる。

### Experiment 6: preview recommendation loop

preview 差分と failure tag から、各 input / seed で次に採る候補と改版案を選ぶ。

評価:

- 各 group に selected candidate が 1 つ決まる。
- selected candidate から next action が自動生成される。
- selected candidate の profile / layout / motion / dictionary のどこを直すかが説明できる。

### Experiment 7: revision plan export

preview から選定した候補について、次実験で変えるべき parameter と再生成ヒントを出力する。

評価:

- `motion`、`layout`、`dictionary`、`profile`、`safety` のいずれかに分類できる。
- 変更候補が具体的な parameter 名と direction を持つ。
- 同一 input / seed の再生成方針を Markdown と JSON で保存できる。

### Experiment 8: preview iteration loop

preview 比較、候補選定、改版提案を 1 ラウンドに束ね、次の実験へそのまま渡せる形にする。

評価:

- 1 ラウンドの status を JSON と Markdown で保存できる。
- selected candidate がある group とない group を区別できる。
- 次の実験ヒントを 1 つの summary で確認できる。

### Experiment 9: preview revision application

revision plan を derived profile に変換して再生成し、同じ input / seed で再比較する。

評価:

- applied / unapplied changes を分離して記録できる。
- 再生成した experiment が registry に追加される。
- before / after の preview iteration を Markdown と JSON で保存できる。

### Experiment 10: design principle extraction

revision loop の比較結果から、再現可能な設計原理を抽出して残す。

評価:

- comparison summary が `metric_names` と `resolved_failure_tags` を持つ。
- design principles が change target ごとに出力される。
- ループ結果から安定版候補を説明できる。

### Experiment 11: revision stability summary

複数ラウンドの revision loop packet をまとめ、何度回しても効く設計原理を抽出する。

評価:

- stable design principles を抽出できる。
- recurring failure tags と metric 名が複数ラウンドで集約できる。
- 安定版 writer profile 群の候補を説明できる。

### Experiment 12: stable writer profile candidates

安定して繰り返し効く design principle から、derived writer profile 候補を生成する。

評価:

- summary から profile candidate bundle を作れる。
- stable / recurring の候補を区別して出力できる。
- 候補 profile が実験ログと接続できる。

### Experiment 13: stable writer profile evaluation

生成した候補 profile を固定入力セットで実際に評価し、baseline との差分から採択候補を確定する。

評価:

- 候補 profile を registry に接続したまま再現実行できる。
- baseline と比較して、新しい failure tag が出ない候補だけを採択できる。
- selected profile ids と selection summary を保存できる。

### Experiment 14: data-driven prior evaluation

JSONL 形式のオンライン筆記サンプルから推定した prior を、固定入力セットで手設計 profile と比較する。

評価:

- samples.jsonl から derived profile を作れる。
- baseline profile と同じ fixed input set で再生成できる。
- preview / metrics / failure tags の比較から、prior の改善点と副作用を記録できる。

## 成果物

- metrics spec。
- experiment registry schema。
- artifact directory convention。
- failure taxonomy。
- evaluation dataset definition。
- ABX protocol。
- scan naming convention。
- scan metadata schema。
- baseline report template。

## 評価指標

- DTW/DDTW。
- velocity peak count。
- acceleration/jerk。
- spacing variance。
- baseline drift。
- repeated character similarity。
- preview mismatch summary。
- ABX 正答率。

## リスク

- 自動指標に過適合する。
- 評価者数が少ないと結論が不安定。
- スキャン環境差が結果に混ざる。必要時のみ使うため影響は限定する。
- 評価結果なしに次実験を進める。
- failure tags が増えすぎて比較不能になる。
- baseline が固定されず、新方式との差分を説明できなくなる。

## 参照

- [CASHG](https://arxiv.org/abs/2604.02103)
- [DeepWriteSYN](https://arxiv.org/abs/2009.06308)
- [IAM-OnDB](https://fki.tic.heia-fr.ch/databases/download-the-iam-on-line-handwriting-database)
