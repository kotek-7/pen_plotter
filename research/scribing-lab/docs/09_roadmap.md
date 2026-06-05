# 09 Roadmap

## 原則

LLM エージェントが研究を主導するため、最初に評価基盤と実験記録基盤を作る。生成モデル、writer adaptation、neural variation は、比較可能な実験単位で評価できる状態になってから進める。

## Phase 0: 調査と基準線

期間: 1〜2 週間

成果物:

- 先行研究メモ。
- データ資産リスト。
- 対象文字セットの決定。
- baseline 生成方式の評価観点。
- experiment registry の最小スキーマ。
- failure taxonomy。

完了条件:

- 最初の評価文字列が決まっている。
- 自動評価と主観評価の最小設計がある。
- LLM エージェントが使う実験レポート形式が決まっている。

## Phase 1: Evaluation And Experiment Harness

期間: 2〜3 週間

成果物:

- experiment registry。
- artifact store。
- metric runner。
- report template。
- baseline runner。
- failure tag validator。

完了条件:

- すべての実験が ID 付きで記録される。
- trajectory、preview、G-code、metrics を同じ ID で追跡できる。
- baseline と新方式を同じ手順で比較できる。
- 評価基盤なしの成果物を研究進捗として扱わない運用になっている。

## Phase 2: Core Schemas And Profile Registry

期間: 2〜3 週間

成果物:

- 正準 trajectory schema。
- writer profile schema。
- profile registry。
- stroke template schema。
- seed 固定生成の実験 CLI。

完了条件:

- `x,y,t,pen_state,pressure` を生成・保存・読み込みできる。
- writer profile id、seed、generator version が experiment registry に記録される。

## Phase 3: 文字構造辞書 MVP

期間: 3〜4 週間

成果物:

- KanjiVG parser。
- 小規模 stroke template 辞書。
- `永` とかなの筆順保持生成。

完了条件:

- 筆順を変えずに画列を出力できる。
- xDraw 用の座標へ配置できる。
- 辞書生成の失敗が evaluation harness 上で分類できる。

## Phase 4: Motion MVP

期間: 4〜6 週間

成果物:

- Sigma-Lognormal 風の速度生成。
- pressure event model。
- drift/tremor model。
- xDraw G-code exporter。

完了条件:

- `永` と短文を等速ではない速度で書ける。
- harai/hane/tome の終端差が実機で観察できる。
- 等速 baseline との差分が metrics とレビュー成果物で説明できる。

## Phase 5: Writer Profile Expansion

期間: 3〜5 週間

成果物:

- profile parameter editor。
- profile 適用器。
- 自前サンプルからの統計推定。

完了条件:

- profile を変えると、字間・傾き・速度・終端が一貫して変わる。
- profile 変更ごとの評価結果を experiment registry で比較できる。

## Phase 6: Data-Driven Prior

期間: 4〜8 週間

成果物:

- 自前オンライン筆記データ取り込み。
- TUAT 利用可否の判断。
- 画種別 prior 推定。

完了条件:

- 手設計 prior より自然な速度・終端が得られる。

## Phase 7: Neural Variation

期間: 6〜10 週間

成果物:

- 画単位 VAE/RNN baseline。
- writer embedding 実験。
- structure-constrained variation。

完了条件:

- 文字構造を壊さず、自然な形状変動が増える。

## 優先順位

1. evaluation harness。
2. experiment registry。
3. artifact store。
4. 正準表現。
5. profile registry。
6. 文字構造辞書。
7. Sigma-Lognormal 運動生成。
8. xDraw exporter。
9. writer profile expansion。
10. neural variation。

神経モデルは最後でよい。最初に必要なのは、LLM エージェントが毎回同じ形式で実験を実行し、失敗を分類し、次の仮説を立てられる評価基盤である。
