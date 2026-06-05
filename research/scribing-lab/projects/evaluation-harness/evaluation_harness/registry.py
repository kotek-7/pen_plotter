from __future__ import annotations

import json
from pathlib import Path

from evaluation_harness.models import ExperimentRecord
from evaluation_harness.taxonomy import validate_failure_tags


class ExperimentRegistry:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load_all(self) -> list[ExperimentRecord]:
        if not self.path.exists():
            return []

        records: list[ExperimentRecord] = []
        with self.path.open("r", encoding="utf-8") as fp:
            for line_no, raw in enumerate(fp, start=1):
                line = raw.strip()
                if not line:
                    continue
                try:
                    records.append(ExperimentRecord.from_dict(json.loads(line)))
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    raise ValueError(f"Invalid registry line {line_no}: {exc}") from exc
        return records

    def ids(self) -> set[str]:
        return {record.experiment_id for record in self.load_all()}

    def append(self, record: ExperimentRecord) -> None:
        self._validate_record(record)
        if record.experiment_id in self.ids():
            raise ValueError(f"Duplicate experiment id: {record.experiment_id}")

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")

    def get(self, experiment_id: str) -> ExperimentRecord:
        for record in self.load_all():
            if record.experiment_id == experiment_id:
                return record
        raise KeyError(experiment_id)

    def _validate_record(self, record: ExperimentRecord) -> None:
        required = {
            "experiment_id": record.experiment_id,
            "hypothesis": record.hypothesis,
            "input_text": record.input_text,
            "profile_id": record.profile_id,
            "generator": record.generator,
            "exporter": record.exporter,
        }
        missing = [name for name, value in required.items() if not value.strip()]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")
        if record.seed < 0:
            raise ValueError("seed must be non-negative")
        validate_failure_tags(record.failure_tags)
