from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ArtifactStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def experiment_dir(self, experiment_id: str) -> Path:
        path = self.root / experiment_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_json(self, experiment_id: str, name: str, data: Any) -> str:
        path = self.experiment_dir(experiment_id) / name
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return str(path)

    def write_text(self, experiment_id: str, name: str, text: str) -> str:
        path = self.experiment_dir(experiment_id) / name
        path.write_text(text, encoding="utf-8")
        return str(path)

    def require(self, artifact_paths: dict[str, str]) -> None:
        missing = [name for name, path in artifact_paths.items() if not Path(path).exists()]
        if missing:
            raise FileNotFoundError(f"Missing artifacts: {', '.join(sorted(missing))}")
