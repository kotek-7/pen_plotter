from __future__ import annotations

import json
import mimetypes
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlparse


@dataclass(frozen=True)
class RunPreview:
    name: str
    path: Path
    has_memo: bool

    def to_dict(self) -> dict[str, Any]:
        encoded = quote(self.name)
        return {
            "name": self.name,
            "preview_url": f"/preview/{encoded}/preview.svg",
            "memo_url": f"/memo/{encoded}",
            "has_memo": self.has_memo,
        }


@dataclass(frozen=True)
class ViewerConfig:
    runs_dir: Path
    run_dir: Path | None
    host: str
    port: int


def default_lab_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_runs_dir() -> Path:
    return default_lab_root() / "runs"


def list_run_previews(runs_dir: Path, *, run_dir: Path | None = None) -> list[RunPreview]:
    if run_dir is not None:
        runs = [run_dir]
    elif runs_dir.exists():
        runs = [path for path in runs_dir.iterdir() if path.is_dir()]
    else:
        runs = []

    previews: list[RunPreview] = []
    for path in sorted(runs, key=lambda item: item.name, reverse=True):
        preview = path / "preview.svg"
        if preview.exists():
            previews.append(RunPreview(name=path.name, path=path, has_memo=(path / "memo.md").exists()))
    return previews


def serve_viewer(config: ViewerConfig) -> None:
    handler = _make_handler(config)
    server = ThreadingHTTPServer((config.host, config.port), handler)
    url = f"http://{config.host}:{config.port}/"
    print(f"viewer: {url}")
    print(f"runs: {config.runs_dir}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nviewer stopped")


def _make_handler(config: ViewerConfig) -> type[BaseHTTPRequestHandler]:
    class ViewerHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send_html(_render_index())
                return
            if parsed.path == "/api/runs":
                runs = [run.to_dict() for run in list_run_previews(config.runs_dir, run_dir=config.run_dir)]
                self._send_json({"runs": runs})
                return
            if parsed.path.startswith("/preview/"):
                self._send_run_file(parsed.path, filename="preview.svg")
                return
            if parsed.path.startswith("/memo/"):
                self._send_run_file(parsed.path, filename="memo.md")
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send_run_file(self, path: str, *, filename: str) -> None:
            run_name = _run_name_from_path(path, filename=filename)
            if run_name is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            run = _find_run(config, run_name)
            if run is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return

            target = run.path / filename
            if not target.exists():
                self.send_error(HTTPStatus.NOT_FOUND)
                return

            content_type = mimetypes.guess_type(target.name)[0] or "text/plain"
            data = target.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_html(self, body: str) -> None:
            data = body.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_json(self, payload: dict[str, Any]) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return ViewerHandler


def _find_run(config: ViewerConfig, name: str) -> RunPreview | None:
    for run in list_run_previews(config.runs_dir, run_dir=config.run_dir):
        if run.name == name:
            return run
    return None


def _run_name_from_path(path: str, *, filename: str) -> str | None:
    if filename == "preview.svg":
        if not path.startswith("/preview/") or not path.endswith("/preview.svg"):
            return None
        return unquote(path.removeprefix("/preview/").removesuffix("/preview.svg")).strip("/")
    if filename == "memo.md":
        if not path.startswith("/memo/"):
            return None
        return unquote(path.removeprefix("/memo/")).strip("/")
    return None


def _render_index() -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Scribing Run Viewer</title>
  <style>{_CSS}</style>
</head>
<body>
  <aside class="sidebar">
    <header class="topbar">
      <h1>Runs</h1>
      <button id="reload" title="Reload">R</button>
    </header>
    <div id="runList" class="run-list"></div>
  </aside>
  <main class="workspace">
    <header class="toolbar">
      <div id="activeRun" class="active-run"></div>
      <div class="tools">
        <button id="zoomOut" title="Zoom out">-</button>
        <button id="zoomIn" title="Zoom in">+</button>
        <button id="fit" title="Fit">Fit</button>
        <button id="reset" title="Reset">Reset</button>
      </div>
    </header>
    <section id="viewport" class="viewport">
      <img id="preview" alt="">
      <div id="empty" class="empty">No preview</div>
    </section>
    <pre id="memo" class="memo"></pre>
  </main>
  <script>{_JS}</script>
</body>
</html>
"""


_CSS = """
:root {
  color-scheme: light;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #f7f7f4;
  color: #242520;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  display: grid;
  grid-template-columns: 280px 1fr;
}
button {
  height: 32px;
  min-width: 32px;
  border: 1px solid #c8c7be;
  background: #ffffff;
  color: #242520;
  cursor: pointer;
}
button:hover { background: #efeee7; }
.sidebar {
  border-right: 1px solid #d8d6cc;
  background: #eeeee7;
  min-width: 0;
}
.topbar, .toolbar {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid #d8d6cc;
}
h1 {
  margin: 0;
  font-size: 15px;
  font-weight: 650;
}
.run-list {
  overflow: auto;
  height: calc(100vh - 48px);
}
.run-item {
  width: 100%;
  display: block;
  height: auto;
  min-height: 42px;
  padding: 8px 12px;
  border: 0;
  border-bottom: 1px solid #d8d6cc;
  background: transparent;
  text-align: left;
  font: inherit;
}
.run-item.active {
  background: #ffffff;
  box-shadow: inset 3px 0 0 #2f6f73;
}
.workspace {
  min-width: 0;
  display: grid;
  grid-template-rows: 48px minmax(0, 1fr) 148px;
  height: 100vh;
}
.active-run {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
  font-weight: 620;
}
.tools {
  display: flex;
  gap: 6px;
}
.viewport {
  position: relative;
  overflow: hidden;
  background:
    linear-gradient(90deg, rgba(0,0,0,0.035) 1px, transparent 1px),
    linear-gradient(rgba(0,0,0,0.035) 1px, transparent 1px),
    #fbfbf8;
  background-size: 24px 24px;
  cursor: grab;
}
.viewport.dragging { cursor: grabbing; }
#preview {
  position: absolute;
  transform-origin: 0 0;
  user-select: none;
  -webkit-user-drag: none;
  max-width: none;
}
.empty {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: #77776f;
}
.memo {
  margin: 0;
  padding: 12px;
  overflow: auto;
  border-top: 1px solid #d8d6cc;
  background: #ffffff;
  color: #34352f;
  font-size: 12px;
  line-height: 1.45;
  white-space: pre-wrap;
}
@media (max-width: 760px) {
  body { grid-template-columns: 1fr; grid-template-rows: 220px 1fr; }
  .sidebar { border-right: 0; border-bottom: 1px solid #d8d6cc; }
  .run-list { height: 172px; }
  .workspace { height: calc(100vh - 220px); }
}
"""


_JS = """
const state = {
  runs: [],
  active: null,
  scale: 1,
  x: 0,
  y: 0,
  dragging: false,
  dragStart: null,
};

const runList = document.getElementById('runList');
const activeRun = document.getElementById('activeRun');
const viewport = document.getElementById('viewport');
const preview = document.getElementById('preview');
const empty = document.getElementById('empty');
const memo = document.getElementById('memo');

function applyTransform() {
  preview.style.transform = `translate(${state.x}px, ${state.y}px) scale(${state.scale})`;
}

function setScale(nextScale, originX = viewport.clientWidth / 2, originY = viewport.clientHeight / 2) {
  const clamped = Math.max(0.05, Math.min(20, nextScale));
  const beforeX = (originX - state.x) / state.scale;
  const beforeY = (originY - state.y) / state.scale;
  state.scale = clamped;
  state.x = originX - beforeX * state.scale;
  state.y = originY - beforeY * state.scale;
  applyTransform();
}

function fitPreview() {
  if (!preview.naturalWidth || !preview.naturalHeight) return;
  const padding = 28;
  const sx = (viewport.clientWidth - padding * 2) / preview.naturalWidth;
  const sy = (viewport.clientHeight - padding * 2) / preview.naturalHeight;
  state.scale = Math.max(0.05, Math.min(sx, sy));
  state.x = (viewport.clientWidth - preview.naturalWidth * state.scale) / 2;
  state.y = (viewport.clientHeight - preview.naturalHeight * state.scale) / 2;
  applyTransform();
}

function resetPreview() {
  state.scale = 1;
  state.x = 24;
  state.y = 24;
  applyTransform();
}

async function loadRuns() {
  const response = await fetch('/api/runs');
  const payload = await response.json();
  state.runs = payload.runs;
  renderRuns();
  if (!state.active && state.runs.length) {
    selectRun(state.runs[0].name);
  }
  if (!state.runs.length) {
    activeRun.textContent = '';
    empty.style.display = 'grid';
    memo.textContent = '';
  }
}

function renderRuns() {
  runList.replaceChildren();
  for (const run of state.runs) {
    const button = document.createElement('button');
    button.className = `run-item${state.active === run.name ? ' active' : ''}`;
    button.textContent = run.name;
    button.title = run.name;
    button.addEventListener('click', () => selectRun(run.name));
    runList.appendChild(button);
  }
}

async function selectRun(name) {
  const run = state.runs.find(item => item.name === name);
  if (!run) return;
  state.active = run.name;
  activeRun.textContent = run.name;
  renderRuns();
  empty.style.display = 'none';
  preview.src = `${run.preview_url}?t=${Date.now()}`;
  memo.textContent = '';
  if (run.has_memo) {
    const response = await fetch(run.memo_url);
    if (response.ok) memo.textContent = await response.text();
  }
}

preview.addEventListener('load', fitPreview);
document.getElementById('reload').addEventListener('click', loadRuns);
document.getElementById('zoomOut').addEventListener('click', () => setScale(state.scale / 1.2));
document.getElementById('zoomIn').addEventListener('click', () => setScale(state.scale * 1.2));
document.getElementById('fit').addEventListener('click', fitPreview);
document.getElementById('reset').addEventListener('click', resetPreview);

viewport.addEventListener('wheel', event => {
  event.preventDefault();
  const rect = viewport.getBoundingClientRect();
  const factor = event.deltaY < 0 ? 1.12 : 1 / 1.12;
  setScale(state.scale * factor, event.clientX - rect.left, event.clientY - rect.top);
}, { passive: false });

viewport.addEventListener('pointerdown', event => {
  state.dragging = true;
  state.dragStart = { pointerX: event.clientX, pointerY: event.clientY, x: state.x, y: state.y };
  viewport.classList.add('dragging');
  viewport.setPointerCapture(event.pointerId);
});

viewport.addEventListener('pointermove', event => {
  if (!state.dragging || !state.dragStart) return;
  state.x = state.dragStart.x + event.clientX - state.dragStart.pointerX;
  state.y = state.dragStart.y + event.clientY - state.dragStart.pointerY;
  applyTransform();
});

viewport.addEventListener('pointerup', event => {
  state.dragging = false;
  state.dragStart = null;
  viewport.classList.remove('dragging');
  viewport.releasePointerCapture(event.pointerId);
});

window.addEventListener('resize', fitPreview);
loadRuns();
"""
