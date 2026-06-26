# Dictionary Stroke Engine

文字構造辞書から、筆順付き stroke skeleton を A4 紙面上の正準 `trajectory` に変換する MVP engine。

この engine は `docs/03_character_structure.md` の最小データモデルを確認するための実装である。
KanjiVG `r20250816` の main release から生成した正規化済みテンプレートを
`data/kanjivg_templates.json` として同梱し、stroke order、
skeleton points、terminal event を使う。英数字は Hershey 由来の stroke template を使い、
句読点・括弧・演算記号などの基本記号は hand-authored template を使う。未収録文字は簡易 fallback へ落とす。

KanjiVG 由来データの license は CC BY-SA 3.0 である。`engine_parameters.dictionary.sources` に
source / license metadata を残す。

## Contract

`engine.py` が `generate(request)` を公開する。

```py
{
    "text": str,
    "seed": int,
    "params": dict[str, str],
}
```

返り値は runner contract に従う。

```py
{
    "engine_id": "dictionary-stroke-engine",
    "engine_parameters": {...},
    "trajectory": [
        {"x": 12.0, "y": 281.0, "t": 0, "pen_state": 0, "pressure": 0.0}
    ],
}
```

## Parameters

- `char_size`: 文字サイズ mm。既定値 `12.0`
- `char_spacing`: 字間 mm。既定値 `2.5`
- `margin_left`: 左余白 mm。既定値 `12.0`
- `margin_top`: 上余白 mm。既定値 `16.0`
- `kana_scale`: かな・カナの文字サイズ比。既定値 `1.0`
- `latin_scale`: 英数字の文字サイズ比。既定値 `0.62`
- `symbol_scale`: 記号の文字サイズ比。既定値 `0.45`
- `draw_speed_mm_s`: 筆記速度。既定値 `32.0`
- `penup_speed_mm_s`: ペンアップ移動速度。既定値 `110.0`

全角の日本語グリフ（かな・カナ・漢字）は KanjiVG の em-box を共有し、`char_size` の正方セルを基準に配置する。かな・カナは KanjiVG が em-box 内に適切なサイズで収めているため既定で `kana_scale=1.0`（漢字と同サイズ）とする。`baseline_y` を持たないグリフ（全角・記号）は em-box 中心を基準に拡縮するため、小書きかな・長音 `ー`・句読点も漢字の em-box と縦位置が揃う。英数字は `baseline_y` でベースラインを固定する。

現段階の本 engine は人間らしさを加えない純粋なフォント出力 engine である。位置揺れ・筆圧変調・運動速度変化などの humanization は持たず、`trajectory` は決定論的に生成する。`pressure` は接地中 `1.0`・非接地中 `0.0` の定数、`t` は `draw_speed_mm_s` の一様速度から距離比例で算出する。`seed` は contract 上受け取るが出力には影響しない。

## Usage

```sh
cd research/scribing-lab
make run TEXT="今日はABC123、カナもOK！" NAME=dict-smoke ENGINE=engines/dictionary_stroke_engine
make convert RUN=runs/<run-dir>
make view RUN=runs/<run-dir>
```

KanjiVG asset を更新する場合:

```sh
python engines/dictionary_stroke_engine/scripts/generate_kanjivg_templates.py
```

Hershey asset を更新する場合:

```sh
uv run --with Hershey-Fonts python engines/dictionary_stroke_engine/scripts/generate_hershey_templates.py
```
