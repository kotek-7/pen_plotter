# 05 Writer Profile

## 目的

writer profile は、筆者ごとの癖を保持し、生成結果に一貫した個人差を与える。研究初期では、深層埋め込みだけにせず、解釈可能なパラメータを中心に扱う。

## 初期スキーマ

```json
{
  "writer_id": "demo_001",
  "params": {
    "slant_deg": 2.0,
    "baseline_drift_mm_per_char": 0.03,
    "spacing_mean_mm": 1.2,
    "spacing_cv": 0.18,
    "speed_mean_mm_s": 40.0,
    "speed_cv": 0.20,
    "tremor_gain_mm": 0.02,
    "tremor_freq_hz": 7.0,
    "harai_gain": 1.0,
    "hane_gain": 1.0,
    "tome_gain": 1.0,
    "stroke_merge_prob": 0.0,
    "stroke_omit_prob": 0.0
  }
}
```

## profile が制御するもの

- 字形の傾き。
- 字間。
- 行方向の傾き。
- 速度の平均とばらつき。
- 震え。
- 払い、はね、とめの強さ。
- 画の省略・接続傾向。

## few-shot 適応

初期目標は、10〜30 文字程度の筆記サンプルから profile を推定することである。

段階:

1. 手動調整 UI または設定ファイルで profile を作る。
2. 自前オンライン筆記サンプルから統計量を推定する。
3. writer-id 付きデータで profile estimator を学習する。
4. neural embedding と明示パラメータを併用する。

## 評価

- 同一 profile で複数文を生成したとき、一貫した癖が見えるか。
- 異なる profile 間で区別可能な差が出るか。
- 実サンプルと生成サンプルを writer classifier が混同するか。
- 人間評価で「同じ人らしい」と判定されるか。

## リスク

- 本人筆跡の無断模倣に使える。
- 少量サンプルでは過剰適合しやすい。
- 文字種ごとの癖と writer 全体の癖を混同しやすい。

## 参照

- [DeepWriting](https://huggingface.co/papers/1801.08379)
- [Disentangling Writer and Character Styles for Handwriting Generation](https://arxiv.org/abs/2303.14736)
- [CASHG](https://arxiv.org/abs/2604.02103)
