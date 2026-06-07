from __future__ import annotations

import argparse
from pathlib import Path

from character_dictionary.dictionary import BUILTIN_CHARACTER_ORDER, KANJIVG_ASSET_PATH
from character_dictionary.kanjivg import dump_kanjivg_asset


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate KanjiVG template asset")
    parser.add_argument(
        "--output",
        default=str(KANJIVG_ASSET_PATH),
        help="Output JSON asset path",
    )
    args = parser.parse_args()

    literals = [literal for literal in BUILTIN_CHARACTER_ORDER if len(literal) == 1 and not literal.isascii()]
    dump_kanjivg_asset(Path(args.output), literals)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
