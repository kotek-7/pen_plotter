from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from scribing_runner.artifacts import default_engine_path, default_run_dir, write_run_artifacts
from scribing_runner.contracts import RunRequest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a scribing engine and write artifacts.")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run one engine")
    run.add_argument("--engine", type=Path, default=default_engine_path())
    run.add_argument("--text", default="")
    run.add_argument("--text-file", type=Path)
    run.add_argument("--seed", type=int, default=1)
    run.add_argument("--param", action="append", default=[], help="Engine parameter as key=value")
    run.add_argument("--out", type=Path, help="Output run directory")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "run":
        request = RunRequest(
            text=_read_text(args.text, args.text_file),
            seed=args.seed,
            params=_parse_params(args.param),
            engine_path=args.engine,
        )
        engine = _load_engine(args.engine)
        result = _run_engine(engine, request)
        engine_id = str(result.get("engine_id", getattr(engine, "ENGINE_ID", "unknown-engine")))
        run_dir = args.out or default_run_dir(engine_id)
        artifacts = write_run_artifacts(run_dir=run_dir, request=request, result=result)
        print(f"run_dir: {artifacts.run_dir}")
        print(f"preview: {artifacts.preview}")
        print(f"gcode: {artifacts.gcode}")
        print(f"safety: {artifacts.safety}")


def _read_text(text: str, text_file: Path | None) -> str:
    if text_file is not None:
        return text_file.read_text(encoding="utf-8")
    if text:
        return text
    raise SystemExit("--text or --text-file is required")


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
    for key in ("trajectory", "preview_svg", "gcode", "safety"):
        if key not in result:
            raise SystemExit(f"engine result missing required key: {key}")
    return result


if __name__ == "__main__":
    main()
