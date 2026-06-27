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

runner の責務は engine を実行し、正準軌跡(`trajectory`)と run メタデータを書き出すまでである。
preview / G-code への変換は runner の責務ではなく、独立した renderer / exporter 基盤が担う。
runner はこれらに依存しない。run 後に `scribe-render` / `scribe-export` を `trajectory.json`
へ適用して `preview.svg` / `output.gcode` / `safety.json` を生成する。

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

`trajectory` の各点は、原則として `x`、`y`、`t`、`pen_state`、`pressure` を持つ
（`x`・`y` は紙面 mm の Y-UP 座標、`t` は ms、`pen_state` は 0=up / 1=down、`pressure` は 0..1 の仮想筆圧）。
engine の責務はこの正準軌跡の生成までで、preview と G-code への変換は専用基盤が担う。
engine 内部では文字構造、レイアウト、運動生成を自由に分けてよいが、runner から見る実行単位は
engine 全体である。`preview_svg` / `gcode` / `safety` を engine が返した場合は、基盤による
生成を上書きする escape hatch として扱う。

## Engine の実行環境分離

engine の依存が runner 本体へ流れ込むのを避けるため、実行方式を engine ごとに分ける。

- **engine が uv project（`pyproject.toml` を持つ）の場合**: その engine の環境で
  サブプロセス実行する（`uv run --project <engine_dir>` 経由で `engine_host.py` を起動し、
  request/result を JSON でやり取り）。torch などの重い依存は engine 側に閉じ、runner には
  入らない。`uv run` が未 sync の環境を自動 sync するため、追加の手当ては不要。
- **純 stdlib engine（`pyproject.toml` なし）**: 従来どおり runner プロセス内に import する。

contract（`generate(request) -> result`）は両方式で同一。サブプロセス実行のため、engine は
`generate` 中に **stdout へ出力しない**こと（ログは stderr へ。result は別ファイル経由で受け渡す）。

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
