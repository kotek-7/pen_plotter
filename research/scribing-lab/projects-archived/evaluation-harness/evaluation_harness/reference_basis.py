from __future__ import annotations

from typing import Any


REFERENCE_SOURCES: tuple[dict[str, str | tuple[str, ...]], ...] = (
    {
        "name": "KanjiVG",
        "url": "https://kanjivg.tagaini.net/svg-format.html",
        "axes": ("structure", "stroke order", "stroke type"),
    },
    {
        "name": "IAM-OnDB",
        "url": "https://fki.tic.heia-fr.ch/databases/download-the-iam-on-line-handwriting-database",
        "axes": ("online trajectory", "line-level comparability", "fixed splits"),
    },
    {
        "name": "DeepWriting",
        "url": "https://arxiv.org/abs/1801.08379",
        "axes": ("style/content disentanglement", "editable digital ink"),
    },
    {
        "name": "DeepWriteSYN",
        "url": "https://arxiv.org/abs/2009.06308",
        "axes": ("short-term segments", "natural variation", "subject-level consistency"),
    },
    {
        "name": "sigma-lognormal",
        "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC3867641/",
        "axes": ("velocity profile", "kinematic naturalness", "terminal events"),
    },
    {
        "name": "human-like kinematics",
        "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC9292284/",
        "axes": ("human preference", "uniform-vs-natural movement", "boundary naturalness"),
    },
    {
        "name": "CASHG",
        "url": "https://arxiv.org/abs/2604.02103",
        "axes": ("connectivity", "spacing", "sentence-level context"),
    },
)


EVALUATION_AXES: tuple[dict[str, str | tuple[str, ...]], ...] = (
    {
        "name": "structure",
        "description": "stroke order, component structure, and terminal type should remain coherent",
        "sources": ("KanjiVG",),
    },
    {
        "name": "layout",
        "description": "glyph size, line spacing, and paragraph spacing should remain legible and consistent",
        "sources": ("KanjiVG", "IAM-OnDB", "CASHG"),
    },
    {
        "name": "motion",
        "description": "velocity profile, terminal pressure, and jerk should avoid uniform or over-jittered motion",
        "sources": ("sigma-lognormal", "human-like kinematics"),
    },
    {
        "name": "style",
        "description": "style and content should be separable enough to explain writer differences",
        "sources": ("DeepWriting", "DeepWriteSYN"),
    },
    {
        "name": "review",
        "description": "blind review and fixed benchmark comparison should reproduce the same decision",
        "sources": ("IAM-OnDB", "DeepWriting", "DeepWriteSYN"),
    },
)


def build_reference_basis() -> dict[str, Any]:
    return {
        "source_count": len(REFERENCE_SOURCES),
        "sources": [
            {
                "name": item["name"],
                "url": item["url"],
                "axes": list(item["axes"]),
            }
            for item in REFERENCE_SOURCES
        ],
        "axis_count": len(EVALUATION_AXES),
        "axes": [
            {
                "name": item["name"],
                "description": item["description"],
                "sources": list(item["sources"]),
            }
            for item in EVALUATION_AXES
        ],
    }


def render_reference_basis_markdown(reference_basis: dict[str, Any]) -> str:
    lines = [
        "## Reference Basis",
        "",
        f"- source_count: `{reference_basis['source_count']}`",
        f"- axis_count: `{reference_basis['axis_count']}`",
        "",
        "### Sources",
        "",
    ]
    for item in reference_basis["sources"]:
        lines.append(
            f"- [{item['name']}]({item['url']}): `{item['axes']}`"
        )
    lines.extend(["", "### Axes", ""])
    for item in reference_basis["axes"]:
        lines.append(
            f"- {item['name']}: `{item['description']}` from `{item['sources']}`"
        )
    return "\n".join(lines)
