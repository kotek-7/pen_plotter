from pathlib import Path

import pytest

from evaluation_harness.models import ExperimentRecord
from evaluation_harness.registry import ExperimentRegistry


def _record(experiment_id: str = "exp-000001") -> ExperimentRecord:
    return ExperimentRecord(
        experiment_id=experiment_id,
        hypothesis="test hypothesis",
        input_text="永",
        profile_id="baseline-neat",
        seed=1,
        generator="test-generator",
        exporter="test-exporter",
    )


def test_registry_appends_and_loads_record(tmp_path: Path) -> None:
    registry = ExperimentRegistry(tmp_path / "registry.jsonl")

    registry.append(_record())

    records = registry.load_all()
    assert len(records) == 1
    assert records[0].experiment_id == "exp-000001"
    assert records[0].input_text == "永"


def test_registry_rejects_duplicate_id(tmp_path: Path) -> None:
    registry = ExperimentRegistry(tmp_path / "registry.jsonl")
    registry.append(_record())

    with pytest.raises(ValueError, match="Duplicate experiment id"):
        registry.append(_record())


def test_registry_rejects_unknown_failure_tag(tmp_path: Path) -> None:
    registry = ExperimentRegistry(tmp_path / "registry.jsonl")
    record = ExperimentRecord(
        experiment_id="exp-000002",
        hypothesis="test hypothesis",
        input_text="永",
        profile_id="baseline-neat",
        seed=1,
        generator="test-generator",
        exporter="test-exporter",
        failure_tags=["not-a-real-tag"],
    )

    with pytest.raises(ValueError, match="Unknown failure tags"):
        registry.append(record)


def test_registry_accepts_extended_failure_tags(tmp_path: Path) -> None:
    registry = ExperimentRegistry(tmp_path / "registry.jsonl")
    record = ExperimentRecord(
        experiment_id="exp-000003",
        hypothesis="test hypothesis",
        input_text="永",
        profile_id="baseline-neat",
        seed=1,
        generator="test-generator",
        exporter="test-exporter",
        failure_tags=["too-font-like", "scan-mismatch", "plotter-line-quality-bad"],
    )

    registry.append(record)

    assert registry.get("exp-000003").failure_tags == [
        "too-font-like",
        "scan-mismatch",
        "plotter-line-quality-bad",
    ]


def test_registry_replaces_existing_record(tmp_path: Path) -> None:
    registry = ExperimentRegistry(tmp_path / "registry.jsonl")
    original = _record()
    registry.append(original)

    registry.replace(
        ExperimentRecord(
            **{
                **original.to_dict(),
                "metrics": {"duration_ms": 1200},
            }
        )
    )

    assert registry.get("exp-000001").metrics["duration_ms"] == 1200
