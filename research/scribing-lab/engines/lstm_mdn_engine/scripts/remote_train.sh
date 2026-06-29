#!/usr/bin/env bash
# lstm_mdn_engine をリモート GPU マシンで学習する。
#   ssh 接続 → rsync 転送(engine + datasets) → 学習実行(ログ) → checkpoint 回収
#
# 使い方:
#   scripts/remote_train.sh <user@host> [-d REMOTE_DIR] [-i TORCH_INDEX] [-- <hw-train 引数...>]
#
# 例:
#   scripts/remote_train.sh me@gpu-box
#   scripts/remote_train.sh me@gpu-box -d ~/work/scribing -- --epochs 600 --patience 40 \
#       --batch-size 128 --hidden 256 --name kanji
#
# 前提: リモートに ssh 接続でき、CUDA ドライバ導入済み。uv は無ければ自動導入する。
# 既定の torch は CUDA 12.4 ビルド (-i で変更可)。
set -uo pipefail

usage() { sed -n '2,16p' "$0"; }

REMOTE=""
REMOTE_DIR="scribing-train"
TORCH_INDEX="https://download.pytorch.org/whl/cu124"
TRAIN_ARGS=(--device cuda --epochs 600 --patience 40 --batch-size 128 --name remote)

while [[ $# -gt 0 ]]; do
  case "$1" in
    -d|--remote-dir) REMOTE_DIR="$2"; shift 2 ;;
    -i|--torch-index) TORCH_INDEX="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    --) shift; TRAIN_ARGS=("$@"); break ;;
    -*) echo "unknown option: $1" >&2; usage; exit 1 ;;
    *) if [[ -z "$REMOTE" ]]; then REMOTE="$1"; shift; else echo "unexpected arg: $1" >&2; exit 1; fi ;;
  esac
done
[[ -n "$REMOTE" ]] || { echo "error: <user@host> が必要です" >&2; usage; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LAB_DIR="$(cd "$ENGINE_DIR/../.." && pwd)"
DATASETS_DIR="$LAB_DIR/handwriting-collector/datasets"
REMOTE_ENGINE="$REMOTE_DIR/engines/lstm_mdn_engine"

EXCLUDES=(--exclude '.venv' --exclude '__pycache__' --exclude '*.pyc'
          --exclude '.pytest_cache' --exclude '.ruff_cache' --exclude 'dist'
          --exclude 'data')

echo ">> [1/4] transfer -> $REMOTE:$REMOTE_DIR  (train args: ${TRAIN_ARGS[*]})"
ssh "$REMOTE" "mkdir -p '$REMOTE_ENGINE' '$REMOTE_DIR/handwriting-collector/datasets'"
rsync -az --delete "${EXCLUDES[@]}" "$ENGINE_DIR/" "$REMOTE:$REMOTE_ENGINE/"
rsync -az "$DATASETS_DIR/" "$REMOTE:$REMOTE_DIR/handwriting-collector/datasets/"

echo ">> [2/4] remote setup + train (出力は標準出力に流れる)"
ssh "$REMOTE" bash -l 2>&1 <<EOF
set -e
cd "$REMOTE_ENGINE"
command -v uv >/dev/null 2>&1 || curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="\$HOME/.local/bin:\$PATH"
uv venv
. .venv/bin/activate
uv pip install --quiet numpy torch --index-url "$TORCH_INDEX"
python -c 'import torch; print("torch", torch.__version__, "cuda", torch.cuda.is_available())'
python -m lstm_mdn.train ${TRAIN_ARGS[*]}
EOF
rc=$?

echo ">> [3/4] retrieve checkpoints (rc=$rc; 失敗時も best-val を回収)"
mkdir -p "$ENGINE_DIR/data/checkpoints"
rsync -az "$REMOTE:$REMOTE_ENGINE/data/checkpoints/" "$ENGINE_DIR/data/checkpoints/" || true

echo ">> [4/4] done (rc=$rc)"
ls -t "$ENGINE_DIR/data/checkpoints/"*.pt 2>/dev/null | head -3 || echo "(no checkpoints retrieved)"
exit "$rc"
