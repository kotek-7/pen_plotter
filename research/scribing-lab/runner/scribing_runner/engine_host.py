"""エンジンの uv 環境内で動く実行ホスト。

runner から ``uv run --project <engine_dir> python engine_host.py <engine_dir> <out>``
として起動される。request JSON を stdin で受け取り、engine.py の ``generate`` を呼び、
result JSON を ``<out>`` へ書く。これによりエンジンの依存 (torch 等) は engine 側の
環境に閉じ、runner 本体の環境からは分離される。

scribing_runner には依存しない (エンジン環境には入っていないため)。stdlib のみ。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_engine(engine_dir: Path):
    engine_file = engine_dir / "engine.py"
    if not engine_file.exists():
        raise SystemExit(f"engine.py not found: {engine_file}")
    sys.path.insert(0, str(engine_dir))
    spec = importlib.util.spec_from_file_location("scribing_engine_module", engine_file)
    if spec is None or spec.loader is None:
        raise SystemExit(f"failed to load engine: {engine_file}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: engine_host.py <engine_dir> <output_json>")
    engine_dir = Path(sys.argv[1]).resolve()
    out_path = Path(sys.argv[2])

    request = json.load(sys.stdin)
    module = _load_engine(engine_dir)
    generate = getattr(module, "generate", None)
    if not callable(generate):
        raise SystemExit("engine must expose generate(request)")
    result = generate(request)
    if not isinstance(result, dict) or "trajectory" not in result:
        raise SystemExit("engine result missing required key: trajectory")
    out_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
