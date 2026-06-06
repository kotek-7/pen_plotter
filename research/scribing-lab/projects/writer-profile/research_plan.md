# Writer Profile Research Plan

## 目的

同じ文字内容でも、筆者ごとに異なる傾き、字間、速度、震え、終筆癖を再現する。初期段階では、解釈可能な profile parameter を中心に扱う。

writer profile は単なる個人癖モデルではなく、実験条件として versioning され、評価結果と対応付けられる探索対象である。

## MVP 状況

以下は実装済みである。

- `baseline-neat` / `fast-casual` / `shaky-slow` の手動 profile registry。
- `structure-uniform` / `structure-motion` への profile 適用。
- `writer_profile.json` artifact の保存。
- `profile_id` と profile パラメータの experiment record への記録。

## 背景

深層 style embedding は強力だが、実機出力や安全性の調整が難しい。研究初期では、明示パラメータを持ち、少量サンプルから統計推定できる構成が扱いやすい。

## 主要仮説

1. 低次元 profile だけでも、機械的な均一感を大きく減らせる。
2. 速度、字間、baseline drift、終筆癖は writer individuality に強く効く。
3. neural embedding は後段で profile 推定の補助として導入すればよい。
4. profile を experiment registry と結合すると、評価結果から次の profile 変更を提案しやすい。
5. 文章としての一貫性には、global parameter だけでなく、文字種、画種、行文脈ごとの階層 parameter が必要になる。

## スコープ

含む:

- writer profile schema。
- profile registry。
- profile versioning。
- profile による生成差分。
- 自前サンプルからの統計推定。
- profile 比較評価。
- global / char_class / stroke_type / line_context を持つ階層 profile。

含まない:

- 署名 profile。
- 本人同意のない筆跡模倣。
- 大規模 metric learning の本格実装。

## Profile Registry

profile は ID と version を持つ。

```json
{
  "profile_id": "baseline-neat",
  "version": 1,
  "source": "manual",
  "allowed_use": "research-baseline",
  "params": {
    "slant_deg": 2.0,
    "spacing_mean_mm": 1.2,
    "speed_mean_mm_s": 40.0,
    "harai_gain": 1.0,
    "hane_gain": 1.0,
    "tome_gain": 1.0
  },
  "parent_profile": null,
  "created_from_experiment": null
}
```

profile を変更する場合は、新しい version または派生 profile として保存する。既存 profile を破壊的に上書きしない。

拡張版では、文章単位の一貫性を扱うために次の階層を持たせる。

```json
{
  "global": {},
  "char_class": {
    "hiragana": {},
    "kanji": {},
    "punctuation": {}
  },
  "stroke_type": {
    "harai": {},
    "hane": {},
    "tome": {}
  },
  "line_context": {
    "baseline_drift": {},
    "fatigue": {},
    "spacing_variation": {}
  }
}
```

## Feedback Loop

評価結果から profile を変える場合、次を記録する。

- 元 profile。
- 失敗タグ。
- 変更した parameter。
- 変更理由。
- 比較対象 experiment id。
- 改善した metric。
- 悪化した metric。

例:

```text
failure_tags: terminal-too-uniform, too-uniform
change: harai_gain 1.00 -> 1.15, speed_cv 0.20 -> 0.25
reason: increase terminal variation and reduce uniform timing
```

## 実験

### Experiment 1: profile registry smoke test

manual profile を登録し、experiment registry から参照できることを確認する。

評価:

- profile id が一意である。
- version が追跡できる。
- experiment report に profile id が記録される。

### Experiment 2: manual profiles

3 種類の profile を手で作る。

- neat。
- fast casual。
- shaky slow。

評価:

- 同じ文で違いが視認できるか。
- 同一 profile 内で一貫性があるか。
- 短文で字間、行方向、終筆癖が一貫して変化するか。

### Experiment 3: sample statistics

自前収集データから基本統計を推定する。

推定対象:

- 平均速度。
- 速度 CV。
- 字間。
- baseline drift。
- tremor strength。

### Experiment 4: profile feedback update

evaluation harness の failure tags をもとに profile を派生させる。

評価:

- 変更理由が experiment report に残る。
- 変更前後を同一入力・同一 seed で比較できる。
- 改善と副作用が metrics で見える。

### Experiment 5: profile ABX

人間評価で、同じ profile から生成された文字列が同じ人らしいかを見る。

## 成果物

- `writer-profile.schema.json` 案。
- profile registry schema。
- manual profile examples。
- hierarchical profile schema。
- profile application spec。
- profile update protocol。
- 自前サンプル統計推定手順。
- profile ABX 評価設計。

## 評価指標

- profile 間距離。
- 同一 profile consistency。
- writer classifier confusion。
- 主観的な同一筆者判定。

## リスク

- 少量サンプルでは profile が不安定。
- 本人筆跡模倣への濫用。
- 文字種固有の癖と writer 固有の癖を分離しにくい。
- 評価 metric だけに合わせて profile を過剰最適化する。
- 既存 profile を上書きし、比較可能性を失う。
- 階層 profile を早く複雑にしすぎると、少ない実験では原因切り分けが難しくなる。

## 参照

- [DeepWriting](https://huggingface.co/papers/1801.08379)
- [Disentangling Writer and Character Styles for Handwriting Generation](https://arxiv.org/abs/2303.14736)
- [CASHG](https://arxiv.org/abs/2604.02103)
