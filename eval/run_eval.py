from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from tidy.pipeline import Pipeline


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("labels", type=Path); args = parser.parse_args()
    rows = list(csv.DictReader(args.labels.open(encoding="utf-8-sig"))); pipeline = Pipeline()
    total = correct = auto = auto_correct = 0
    for row in rows:
        _, decision, _ = pipeline.safe_classify(Path(row["path"])); total += 1
        correct += decision.category == row["category"]
        if decision.action == "auto": auto += 1; auto_correct += decision.category == row["category"]
    print(f"files={total} top1={correct/max(total,1):.3f} auto_precision={auto_correct/max(auto,1):.3f} coverage={auto/max(total,1):.3f}")


if __name__ == "__main__": main()

