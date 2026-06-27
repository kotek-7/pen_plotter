from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any

from scribing_runner.artifacts import default_engine_path, default_run_dir, write_run_artifacts
from scribing_runner.contracts import RunRequest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a scribing engine.")
    parser.add_argument("text", nargs="?", help="Input text")
    parser.add_argument("-f", "--file", type=Path, help="Read input text from a file")
    parser.add_argument("-e", "--engine", type=Path, default=default_engine_path())
    parser.add_argument("-s", "--seed", type=int, default=1)
    parser.add_argument("-p", "--param", action="append", default=[], help="Engine parameter as key=value")
    parser.add_argument("-n", "--name", help="Run label used after the timestamp prefix")
    parser.add_argument("-o", "--out", type=Path, help="Output run directory")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    request = RunRequest(
        text=_read_text(args.text, args.file),
        seed=args.seed,
        params=_parse_params(args.param),
        engine_path=args.engine,
    )
    result = run_engine(args.engine, request)
    engine_id = str(result.get("engine_id", "unknown-engine"))
    run_dir = args.out or default_run_dir(engine_id, run_name=args.name)
    artifacts = write_run_artifacts(run_dir=run_dir, request=request, result=result)
    print(f"run: {artifacts.run_dir}")
    print(f"trajectory: {artifacts.trajectory}")
    print("next: scribe-render / scribe-export <run> で preview / gcode を生成")


def _read_text(text: str | None, file: Path | None) -> str:
    if file is not None:
        return file.read_text(encoding="utf-8")
    if text:
        return text
    raise SystemExit("text or --file is required")


def _parse_params(items: list[str]) -> dict[str, str]:
    params: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise SystemExit(f"--param must be key=value: {item}")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise SystemExit(f"--param key is empty: {item}")
        params[key] = value.strip()
    return params


def _load_engine(engine_path: Path) -> ModuleType:
    path = engine_path.resolve()
    engine_file = path / "engine.py" if path.is_dir() else path
    if not engine_file.exists():
        raise SystemExit(f"engine.py not found: {engine_file}")

    spec = importlib.util.spec_from_file_location("scribing_engine_module", engine_file)
    if spec is None or spec.loader is None:
        raise SystemExit(f"failed to load engine: {engine_file}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _run_engine(engine: ModuleType, request: RunRequest) -> dict[str, Any]:
    generate = getattr(engine, "generate", None)
    if not callable(generate):
        raise SystemExit("engine must expose generate(request)")
    result = generate(request.to_engine_dict())
    if not isinstance(result, dict):
        raise SystemExit("engine generate(request) must return dict")
    if "trajectory" not in result:
        raise SystemExit("engine result missing required key: trajectory")
    return result


def run_engine(engine_path: Path, request: RunRequest) -> dict[str, Any]:
    """エンジンを実行する。

    エンジンディレクトリが uv project (``pyproject.toml`` あり) の場合は、その環境で
    サブプロセス実行して依存を分離する。純 stdlib エンジンは従来どおり in-process。
    """
    path = engine_path.resolve()
    engine_dir = path if path.is_dir() else path.parent
    if (engine_dir / "pyproject.toml").exists():
        return _run_engine_subprocess(engine_dir, request)
    return _run_engine(_load_engine(engine_path), request)


def _run_engine_subprocess(engine_dir: Path, request: RunRequest) -> dict[str, Any]:
    host = Path(__file__).resolve().parent / "engine_host.py"
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
        out_path = Path(tmp.name)
    try:
        proc = subprocess.run(
            ["uv", "run", "--project", str(engine_dir), "python", str(host), str(engine_dir), str(out_path)],
            input=json.dumps(request.to_engine_dict(), ensure_ascii=False),
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise SystemExit(
                f"engine subprocess failed (exit {proc.returncode}):\n{proc.stderr.strip()}"
            )
        result = json.loads(out_path.read_text(encoding="utf-8"))
    finally:
        out_path.unlink(missing_ok=True)
    if not isinstance(result, dict) or "trajectory" not in result:
        raise SystemExit("engine result missing required key: trajectory")
    return result


if __name__ == "__main__":
    main()
