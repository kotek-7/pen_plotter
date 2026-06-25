# Engines

開発中の筆記エンジンを置く。

ここでの engine は、入力テキストから筆記成果物を生成する 1 つの方式である。
engine 内部では、文字構造、レイアウト、運動生成、export、preview などを自由に分けてよい。
ただし、研究上は engine 全体を 1 つの生成単位として扱う。

最小 contract は、engine ディレクトリ直下の `engine.py` が `generate(request)` を公開すること。
`request` は通常の `dict` で、runner 側の実装に依存しない。

## Current Engines

- `basic_stroke_engine/`: runner と runs の MVP 確認用。実グリフは持たない。
- `dictionary_stroke_engine/`: KanjiVG 由来の文字構造辞書から stroke skeleton を引き、正準 trajectory を生成する MVP。
