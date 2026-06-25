# Runner

筆記 engine を統一した作法で実行し、`runs/` に成果物を書き出すための最小基盤。

runner は評価をしない。`failure_tags`、metrics、`next_action` のような実験台帳は持たない。
run の主役は成果物であり、条件は `memo.md` に自由形式に近い薄いメモとして残す。

## Run Directory

標準の run directory は `../runs/YYYYMMDDTHHMMSS_<name>/` である。

`--name` を指定すると、日時 prefix の後ろに付く label を決められる。`--name` を省略した場合は、
engine id から label を作る。同じ秒に同名 run がある場合は `-02`、`-03` のような suffix を付ける。

`--out` は出力先を完全に上書きする escape hatch である。通常の研究 run では `--name` を使う。

## Run Artifacts

runner が書く標準成果物は次の通り。

- `memo.md`: engine、seed、入力ファイル、手動指定 parameter、engine parameter snapshot を書く自由形式に近いメモ
- `input.txt`: engine に渡した入力テキスト
- `trajectory.json`: engine が生成した内部軌跡
- `preview.svg`: 目視確認用 preview
- `output.gcode`: xDraw/GRBL で試し書きするための G-code
- `safety.json`: G-code と紙面範囲の最低限の安全確認結果

このうち `preview.svg`、`output.gcode`、`safety.json` は engine が作るのではなく、
`trajectory` から専用基盤(`../renderer`、`../exporter`)が生成する。runner は engine から
`trajectory` を受け取り、両基盤を使って残りの成果物を書き出す。既存 run の `trajectory.json`
からは `scribe-render` / `scribe-export` で再生成できる。

run は成果物を見るための単位であり、厳密な実験 schema ではない。後段の評価は、この成果物群を読む。

## Engine Interface

engine は `engine.py` を公開し、`generate(request)` を実装する。

runner から渡される `request` は次の dict である。

```py
{
    "text": str,
    "seed": int,
    "params": dict[str, str],
}
```

engine は次の key を持つ dict を返す。

```py
{
    "engine_id": str,                 # 任意。省略時は unknown-engine 扱い
    "engine_parameters": dict,        # 任意。memo.md に snapshot として残る
    "trajectory": list[dict],         # 必須
}
```

`trajectory` の各点は、原則として `x_mm`、`y_mm`、`t_ms`、`pen_state`、`pressure` を持つ。
engine の責務はこの正準軌跡の生成までで、preview と G-code への変換は専用基盤が担う。
engine 内部では文字構造、レイアウト、運動生成を自由に分けてよいが、runner から見る実行単位は
engine 全体である。`preview_svg` / `gcode` / `safety` を engine が返した場合は、基盤による
生成を上書きする escape hatch として扱う。

## Example

```sh
cd research/scribing-lab/runner
uv sync --extra dev
uv run scribe-run "今日はよい天気です。" \
  --seed 1 \
  --name first-smoke
```

出力先を完全に指定する場合:

```sh
uv run scribe-run "Hello" \
  --engine ../engines/basic_stroke_engine \
  --seed 1 \
  --param char_size=10 \
  --out ../runs/hello-basic
```
