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
class DatasetInfo:
    name: str
    path: Path
    sample_count: int
    writer: str
    charset: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "data_url": f"/dataset/{quote(self.name)}",
            "sample_count": self.sample_count,
            "writer": self.writer,
            "charset": self.charset,
        }


@dataclass(frozen=True)
class ViewerConfig:
    datasets_dir: Path
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


def default_datasets_dir() -> Path:
    return default_lab_root() / "handwriting-collector" / "datasets"


def _count_lines(path: Path) -> int:
    count = 0
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                count += 1
    return count


def _meta_for(path: Path) -> dict[str, Any]:
    """同梱の metadata JSON、無ければ先頭サンプルから writer/charset を拾う。"""
    meta_path = path.with_name(path.name.replace("_raw_", "_meta_")).with_suffix(".json")
    if meta_path.exists():
        try:
            raw = json.loads(meta_path.read_text(encoding="utf-8"))
            return {"writer": str(raw.get("writer_id", "")), "charset": str(raw.get("charset", ""))}
        except (json.JSONDecodeError, OSError):
            pass
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    first = json.loads(line)
                    return {
                        "writer": str(first.get("writerId", "")),
                        "charset": str(first.get("charsetName", "")),
                    }
    except (json.JSONDecodeError, OSError):
        pass
    return {"writer": "", "charset": ""}


def list_datasets(datasets_dir: Path) -> list[DatasetInfo]:
    if not datasets_dir.exists():
        return []
    infos: list[DatasetInfo] = []
    for path in sorted(datasets_dir.glob("*.jsonl"), key=lambda p: p.name, reverse=True):
        meta = _meta_for(path)
        infos.append(
            DatasetInfo(
                name=path.name,
                path=path,
                sample_count=_count_lines(path),
                writer=meta["writer"],
                charset=meta["charset"],
            )
        )
    return infos


def serve_viewer(config: ViewerConfig) -> None:
    handler = _make_handler(config)
    server = ThreadingHTTPServer((config.host, config.port), handler)
    url = f"http://{config.host}:{config.port}/"
    print(f"dataset viewer: {url}")
    print(f"datasets: {config.datasets_dir}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nviewer stopped")


def _dataset_name_from_path(path: str) -> str | None:
    if not path.startswith("/dataset/"):
        return None
    return unquote(path.removeprefix("/dataset/")).strip("/")


def _make_handler(config: ViewerConfig) -> type[BaseHTTPRequestHandler]:
    class ViewerHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path in _STATIC_FILES:
                self._send_static_file(_STATIC_FILES[parsed.path])
                return
            if parsed.path == "/api/datasets":
                datasets = [d.to_dict() for d in list_datasets(config.datasets_dir)]
                self._send_json({"datasets": datasets})
                return
            if parsed.path.startswith("/dataset/"):
                self._send_dataset(parsed.path)
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
            self._write(target.read_bytes(), content_type)

        def _send_dataset(self, path: str) -> None:
            name = _dataset_name_from_path(path)
            # 名前のみ許可 (パストラバーサル防止)。
            if not name or name != Path(name).name or not name.endswith(".jsonl"):
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            target = config.datasets_dir / name
            if not target.exists():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            self._write(target.read_bytes(), "application/x-ndjson")

        def _send_json(self, payload: dict[str, Any]) -> None:
            self._write(json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json")

        def _write(self, data: bytes, content_type: str) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return ViewerHandler
