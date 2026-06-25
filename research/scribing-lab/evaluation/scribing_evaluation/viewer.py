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


_STATIC_DIR = Path(__file__).resolve().parent / "static"
_STATIC_FILES: dict[str, str] = {
    "/": "index.html",
    "/static/viewer.css": "viewer.css",
    "/static/viewer.js": "viewer.js",
}


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
            if parsed.path in _STATIC_FILES:
                self._send_static_file(_STATIC_FILES[parsed.path])
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

        def _send_static_file(self, filename: str) -> None:
            target = _STATIC_DIR / filename
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
