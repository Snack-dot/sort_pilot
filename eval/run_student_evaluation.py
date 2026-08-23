from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from sort_pilot.evaluation import evaluate_predictions, load_corpus, load_predictions


def main(arguments: Sequence[str] | None = None) -> int:
    """Print aggregate Phase 2 measures for one corpus and ordered predictions."""
    parser = argparse.ArgumentParser(description="Evaluate student subject/template predictions.")
    parser.add_argument("corpus", type=Path)
    parser.add_argument("predictions", type=Path)
    args = parser.parse_args(arguments)

    report = evaluate_predictions(load_corpus(args.corpus), load_predictions(args.predictions))
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
