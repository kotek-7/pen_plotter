#!/usr/bin/env bash
# lstm_mdn_engine をリモート GPU マシンで学習する (tmux 対応)。
#   ssh 接続 → rsync 転送(engine + datasets) → tmux で学習 → checkpoint 回収
#
# 学習はリモートの detached tmux セッションで走るので、ssh が切れても継続する。
# ssh は ControlMaster で多重化するので、認証(パスワード等)は最初の一回だけ。
#
# 使い方:
#   remote_train.sh <user@host> [opts] [-- <hw-train 引数...>]   学習開始 (転送+tmux起動+attach)
#   remote_train.sh <user@host> attach [opts]                    実行中セッションへ再接続
#   remote_train.sh <user@host> status [opts]                    実行状態を確認
#   remote_train.sh <user@host> fetch  [opts]                    checkpoint を回収
#   remote_train.sh <user@host> kill   [opts]                    セッションを停止
#
#   opts: -d REMOTE_DIR (既定 scribing-train) / -i TORCH_INDEX (既定 cu124)
#         -s SESSION (tmux名, 既定 scribe-train) / -p PYVER (venv の Python, 既定 3.12)
#         --foreground (tmux使わず同期実行+自動回収)
#
# 例:
#   remote_train.sh me@gpu-box -- --epochs 600 --patience 40 --batch-size 128 --name kanji
#   remote_train.sh me@gpu-box status / attach / fetch / kill
#
# 前提: リモートに ssh 接続でき、CUDA ドライバと tmux 導入済み。uv は無ければ自動導入。
# パスワード入力が毎回煩わしい場合は鍵認証 (ssh-copy-id <host>) を推奨。
set -uo pipefail

usage() { sed -n '2,24p' "$0"; }

HOST=""
CMD="run"
REMOTE_DIR="scribing-train"
TORCH_INDEX="https://download.pytorch.org/whl/cu124"
SESSION="scribe-train"
FOREGROUND=0
PYVER="3.12"  # torch wheel のある Python。リモート既定が 3.14 等だと torch が入らないため固定
TRAIN_ARGS=(--device cuda --epochs 600 --patience 40 --batch-size 128 --name remote)

while [[ $# -gt 0 ]]; do
  case "$1" in
    -d|--remote-dir) REMOTE_DIR="$2"; shift 2 ;;
    -i|--torch-index) TORCH_INDEX="$2"; shift 2 ;;
    -s|--session) SESSION="$2"; shift 2 ;;
    -p|--python) PYVER="$2"; shift 2 ;;
    --foreground) FOREGROUND=1; shift ;;
    -h|--help) usage; exit 0 ;;
    --) shift; TRAIN_ARGS=("$@"); break ;;
    attach|status|fetch|kill) CMD="$1"; shift ;;
    -*) echo "unknown option: $1" >&2; usage; exit 1 ;;
    *) if [[ -z "$HOST" ]]; then HOST="$1"; shift; else echo "unexpected arg: $1" >&2; exit 1; fi ;;
  esac
done
[[ -n "$HOST" ]] || { echo "error: <user@host> が必要です" >&2; usage; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LAB_DIR="$(cd "$ENGINE_DIR/../.." && pwd)"
DATASETS_DIR="$LAB_DIR/datasets"
REMOTE_ENGINE="$REMOTE_DIR/engines/lstm_mdn_engine"
DONE_MARKER=".train_done"

# --- ssh 多重化: 認証は最初の一回だけ。残りは同じマスター接続を再利用 ---
CTRL_DIR="$(mktemp -d "${TMPDIR:-/tmp}/scribe-cm.XXXXXX")"
CTRL="$CTRL_DIR/sock"
SSH=(ssh -o ControlMaster=auto -o "ControlPath=$CTRL" -o ControlPersist=300)
RSYNC_E="ssh -o ControlPath=$CTRL -o ControlMaster=auto -o ControlPersist=300"
cleanup() { ssh -o "ControlPath=$CTRL" -O exit "$HOST" 2>/dev/null || true; rm -rf "$CTRL_DIR"; }
trap cleanup EXIT
"${SSH[@]}" -fN "$HOST" || { echo "ssh 接続に失敗しました: $HOST" >&2; exit 1; }

transfer() {
  echo ">> transfer -> $HOST:$REMOTE_DIR"
  "${SSH[@]}" "$HOST" "mkdir -p '$REMOTE_ENGINE' '$REMOTE_DIR/datasets'"
  rsync -az --delete -e "$RSYNC_E" \
    --exclude '.venv' --exclude '__pycache__' --exclude '*.pyc' \
    --exclude '.pytest_cache' --exclude '.ruff_cache' --exclude 'dist' --exclude 'data' \
    "$ENGINE_DIR/" "$HOST:$REMOTE_ENGINE/"
  rsync -az -e "$RSYNC_E" "$DATASETS_DIR/" "$HOST:$REMOTE_DIR/datasets/"
}

push_run_script() {
  local tmp; tmp="$(mktemp)"
  cat >"$tmp" <<EOF
#!/usr/bin/env bash
set -e
cd "\$(dirname "\$(readlink -f "\$0")")"
rm -f "$DONE_MARKER"
command -v uv >/dev/null 2>&1 || curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="\$HOME/.local/bin:\$PATH"
uv venv --python "$PYVER"
. .venv/bin/activate
uv pip install numpy torch --index-url "$TORCH_INDEX"
python -c 'import torch; print("torch", torch.__version__, "cuda", torch.cuda.is_available())'
python -m lstm_mdn.train ${TRAIN_ARGS[*]}
echo "[remote_train] finished rc=\$?"
touch "$DONE_MARKER"
EOF
  rsync -az -e "$RSYNC_E" "$tmp" "$HOST:$REMOTE_ENGINE/.remote_run.sh"
  rm -f "$tmp"
}

fetch() {
  echo ">> fetch checkpoints <- $HOST"
  mkdir -p "$ENGINE_DIR/data/checkpoints"
  rsync -az -e "$RSYNC_E" "$HOST:$REMOTE_ENGINE/data/checkpoints/" "$ENGINE_DIR/data/checkpoints/" || true
  ls -t "$ENGINE_DIR/data/checkpoints/"*.pt 2>/dev/null | head -3 || echo "(no checkpoints)"
}

case "$CMD" in
  attach) "${SSH[@]}" -t "$HOST" "tmux attach -t $SESSION" ;;
  status)
    "${SSH[@]}" "$HOST" "if [ -f '$REMOTE_ENGINE/$DONE_MARKER' ]; then echo 'finished (.train_done あり)'; \
      elif tmux has-session -t $SESSION 2>/dev/null; then echo 'running (tmux 稼働中)'; \
      else echo 'not running (session も done marker も無し)'; fi"
    ;;
  fetch) fetch ;;
  kill) "${SSH[@]}" "$HOST" "tmux kill-session -t $SESSION 2>/dev/null && echo killed || echo 'no session'" ;;
  run)
    transfer
    push_run_script
    if [[ "$FOREGROUND" == 1 ]]; then
      echo ">> train (foreground; 出力は標準出力)"
      "${SSH[@]}" "$HOST" bash -l "$REMOTE_ENGINE/.remote_run.sh" 2>&1
      rc=$?
      fetch
      exit "$rc"
    fi
    echo ">> start tmux session '$SESSION' (学習開始)"
    "${SSH[@]}" "$HOST" "command -v tmux >/dev/null 2>&1 || { echo 'remote: tmux not found' >&2; exit 127; }; \
      tmux kill-session -t $SESSION 2>/dev/null; \
      tmux new-session -d -s $SESSION 'bash -l \"$REMOTE_ENGINE/.remote_run.sh\"; exec bash'"
    echo ">> attaching (detach: Ctrl-b d / 学習は継続)"
    "${SSH[@]}" -t "$HOST" "tmux attach -t $SESSION" || true
    echo ">> detached. 学習は継続中の可能性があります。"
    echo "   状態:   $(basename "$0") $HOST status"
    echo "   再接続: $(basename "$0") $HOST attach"
    echo "   回収:   $(basename "$0") $HOST fetch"
    ;;
  *) echo "unknown command: $CMD" >&2; usage; exit 1 ;;
esac
