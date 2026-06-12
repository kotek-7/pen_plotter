# Writer Profile

筆者ごとの癖を推定・保存・適用する研究プロジェクトである。

実装済みの MVP は、`baseline-neat` / `glyph-neat` / `kana-neat` / `kanji-neat` / `steady-neat` / `fast-casual` / `compact-casual` / `micro-casual` / `flow-casual` / `textured-casual` / `textured-steady` / `textured-tight` / `shaky-slow` の 13 種類の手動 profile を登録し、
`structure-uniform` と `structure-motion` に適用できるレジストリである。

`writer_profile.prior` は、JSONL 形式のオンライン筆記サンプルから統計を推定し、
data-driven な derived profile を作る最小実装である。大きいデータセットでは writer ごとに
集計してから統合するため、サンプル数の偏りに引っ張られにくい。

公開の stroke dataset を取り込むときは、`session_id` などのセッション情報を
writer_id の代理として canonical JSONL に変換してから渡す。

```py
from writer_profile import estimate_writer_profile_from_jsonl

estimate = estimate_writer_profile_from_jsonl("samples.jsonl")
profile = estimate["profile"]
```

公開データの変換例:

```sh
python scripts/import_handwriting_v1.py --output runs/handwriting-v1/canonical.jsonl
```

詳細は [research_plan.md](research_plan.md) を参照する。
