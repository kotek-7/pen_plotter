# Runner

筆記 engine を統一した作法で実行し、`runs/` に成果物を書き出すための最小基盤。

runner は評価をしない。`failure_tags`、metrics、`next_action` のような実験台帳は持たない。
run の主役は成果物であり、条件は `memo.md` に自由形式に近い薄いメモとして残す。

## Example

```sh
cd research/scribing-lab/runner
uv sync --extra dev
uv run scribing-runner run \
  --text "今日はよい天気です。" \
  --seed 1
```

出力先を指定する場合:

```sh
uv run scribing-runner run \
  --engine ../engines/basic_stroke_engine \
  --text "Hello" \
  --seed 1 \
  --param char_size=10 \
  --out ../runs/hello-basic
```
