# 09 Roadmap

> 現行メモ: このロードマップには、旧 `projects/` 分割と evaluation-harness を先に作る
> 方針が残っている。現在は `engines/` と `runner/` による最小実行基盤を優先し、
> 評価は `runs/` の出力を見てから `evaluation/` で再設計する。

## 原則

研究を反復的に進めるため、最初に評価基盤と実験記録基盤を作る。生成モデル、writer adaptation、neural variation は、比較可能な実験単位で評価できる状態になってから進める。

最終目標は、単文字ではなく文章をペンプロッタで出力したときに人間の手書きと判別されにくいことである。したがって、短文、字間、行方向の揺れ、反復文字の差分を初期段階から評価対象に含める。評価は preview と human_abx を主軸にし、実機スキャンは後段の確認に回す。

このロードマップは、実装順の一覧ではなく、検証すべき仮説の順序として読む。各 phase では「何を作るか」より先に「何が改善したら次へ進むか」を定義する。

## Phase 0: 調査と基準線

期間: 1〜2 週間

成果物:

- 先行研究メモ。
- データ資産リスト。
- 対象文字セットの決定。
- baseline 生成方式の評価観点。
- experiment registry の最小スキーマ。
- preview 中心の review packet。
- failure taxonomy。
- 固定評価入力セット。
- 100 種類以上の評価入力セット案。

完了条件:

- 最初の評価文字列が決まっている。
- preview と human_abx を使う最小設計がある。
- 実験レポート形式が決まっている。
- 各実験が baseline と比較され、次の仮説へ接続できる。

## Phase 0.5: Baseline 固定

期間: 1 週間

成果物:

- `baseline-outline` generator 定義。
- 現行 font outline + jitter/wobble の実験 runner。
- preview / G-code / metrics / report の保存。
- 固定評価入力セットの baseline report。

固定評価入力セット:

- `永`
- `あいうえお`
- `今日はよい天気です。`
- `春の川をゆっくり歩く。`
- `本日はありがとうございました。`

完了条件:

- 同一 seed で baseline 実験を再実行できる。
- baseline と新方式を同じ registry、artifact、report 形式で比較できる。
- baseline の欠点が failure tags と metrics で説明できる。

## Phase 1: Evaluation And Experiment Harness

期間: 2〜3 週間

成果物:

- experiment registry。
- artifact store。
- preview review packet。
- human_abx 用の比較束。
- metric runner。
- report template。
- baseline runner。
- failure tag validator。
- scan artifact schema。
- 文章評価用 metrics。

完了条件:

- すべての実験が ID 付きで記録される。
- preview、G-code、metrics、必要時の実機スキャンを同じ ID で追跡できる。
- baseline と新方式を同じ手順で比較できる。
- 成果物が評価結果とセットで登録される。
- 単文字、短文、文章の失敗を同じ failure taxonomy で分類できる。
- レポートから次の実験仮説を 1 つ以上抽出できる。

## Phase 2: Core Schemas And Profile Registry

期間: 2〜3 週間

成果物:

- 正準 trajectory schema。
- writer profile schema。
- profile registry。
- stroke template schema。
- seed 固定生成の実験 CLI。
- pen / paper / plotter profile schema。

完了条件:

- `x,y,t,pen_state,pressure` を生成・保存・読み込みできる。
- writer profile id、seed、generator version が experiment registry に記録される。
- 実機出力条件を experiment artifact として保存できる。
- profile を変えたときに、何が改善し何が悪化したかを比較できる。

## Phase 3: 文字構造辞書 MVP

期間: 3〜4 週間

成果物:

- KanjiVG parser。
- 小規模 stroke template 辞書。
- `永` とかなの筆順保持生成。
- terminal event mapping table。
- skeleton rigidity review。

完了条件:

- 筆順を変えずに画列を出力できる。
- xDraw 用の座標へ配置できる。
- 辞書生成の失敗が evaluation harness 上で分類できる。
- `too-font-like` と `skeleton-too-rigid` を評価で検出できる。
- terminal event を exporter へ渡せる。
- 文字構造を増やす前に、既存文字での失敗タグ改善が確認できる。

## Phase 4: Motion MVP

期間: 4〜6 週間

成果物:

- Sigma-Lognormal 風の速度生成。
- pressure event model。
- drift/tremor model。
- repeated character variation。
- pen-up timing model。
- xDraw G-code exporter。

完了条件:

- 固定評価入力セットを等速ではない速度で書ける。
- harai/hane/tome の終端差が実機で観察できる。
- 等速 baseline との差分が metrics とレビュー成果物で説明できる。
- 短文で字間、行方向、反復文字が明らかに破綻しない。
- 速度、筆圧、終端、字間のうち、どれを変えると自然さが改善するかが分かる。

## Phase 5: Writer Profile Expansion

期間: 3〜5 週間

成果物:

- profile parameter editor。
- profile 適用器。
- 自前サンプルからの統計推定。
- global / char_class / stroke_type / line_context を持つ階層 profile schema。
- manual profile examples: neat、fast casual、shaky slow。

完了条件:

- profile を変えると、字間・傾き・速度・終端が一貫して変わる。
- profile 変更ごとの評価結果を experiment registry で比較できる。
- 既存 profile を破壊的に上書きせず、version または派生 profile として追跡できる。
- profile パラメータの変更理由を `next_action` に書ける。

## Phase 6: Data-Driven Prior

期間: 4〜8 週間

成果物:

- 自前オンライン筆記データ取り込み。
- TUAT 利用可否の判断。
- 画種別 prior 推定。

完了条件:

- 手設計 prior より自然な速度・終端が得られる。
- 改善が見えない場合は、データ拡張か特徴量設計のどちらを直すべきか分かる。

## Phase 7: Neural Variation

期間: 6〜10 週間

成果物:

- 画単位 VAE/RNN baseline。
- writer embedding 実験。
- structure-constrained variation。

完了条件:

- 文字構造を壊さず、自然な形状変動が増える。
- 既存のルールベースより良い点と悪い点を同じ report で説明できる。

着手条件:

- baseline registry がある。
- scan artifact loop がある。
- 小規模文字構造辞書がある。
- motion MVP が baseline より良い点と悪い点を metrics と report で説明できる。
- failure tags が安定している。

## 優先順位

1. `baseline-outline` を evaluation harness に接続する。
2. preview と human_abx を使う review packet を安定化する。
3. 固定評価入力セットと 100 種類以上の補助評価セットを確定する。
4. failure taxonomy を文章・実機向けに整える。
5. 正準表現と profile registry を固める。
6. KanjiVG small dictionary MVP を作る。
7. terminal event mapping を exporter へ接続する。
8. Sigma-Lognormal 風 motion MVP を作る。
9. writer profile を階層化する。
10. neural variation を画単位補助として検証する。

神経モデルは最後でよい。最初に必要なのは、毎回同じ形式で実験を実行し、文章と実機出力の失敗を分類し、次の仮説を立てられる評価基盤である。
