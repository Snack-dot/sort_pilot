from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from sort_pilot.classification import (
    E5SubjectClassifier,
    FastEmbedE5Encoder,
    HeldOutAxisResult,
    SubjectEvidence,
    TemplateClassifier,
    TemplateEvidence,
    calibrate_policy,
    load_calibrated_policy,
    load_phase8_optional_evidence,
    load_subject_profiles,
    load_template_profiles,
)
from sort_pilot.evaluation import CorpusCase, load_corpus


DEFAULT_MODEL_CACHE = Path("data/models/fastembed")
# A held-out routing threshold that only clears local-authority precision/accuracy
# targets via a near-zero top-two margin is not a safe auto-accept gate: it means
# some pair of candidates in the held-out set is a genuine near-tie. Empirically,
# 0.02 is comfortably below the real margin both axes settle on once the near-zero
# candidates are excluded (~0.038 subject, ~0.141 template on the current corpus)
# while staying well clear of the point where no threshold meets the targets at all.
MINIMUM_MARGIN_FLOOR = 0.02


def derive_policy(
    corpus: tuple[CorpusCase, ...],
    model_cache: Path,
):
    """Run both local axes on made-up held-out cases and calibrate their policy."""
    encoder = FastEmbedE5Encoder(model_cache, allow_download=False)
    subject_classifier = E5SubjectClassifier(encoder)
    template_classifier = TemplateClassifier(encoder)
    subject_profiles = load_subject_profiles()
    template_profiles = load_template_profiles()
    optional_evidence = load_phase8_optional_evidence()
    subject_results: list[HeldOutAxisResult] = []
    template_results: list[HeldOutAxisResult] = []
    for case in corpus:
        subject = subject_classifier.classify(
            SubjectEvidence(case.file_name, case.text),
            case.student,
            subject_profiles,
            lexical_weight=optional_evidence.subject_kiwi_lexical_weight,
            filename_weight=optional_evidence.subject_filename_weight,
        )
        template = template_classifier.classify(
            TemplateEvidence(case.file_name, case.text),
            template_profiles,
        )
        subject_results.append(
            HeldOutAxisResult(
                raw_score=subject.raw_score,
                margin=subject.margin,
                correct=subject.label == case.subject,
                abstained=subject.needs_review,
            )
        )
        template_results.append(
            HeldOutAxisResult(
                raw_score=template.raw_score,
                margin=template.margin,
                correct=template.label == case.template.value,
                abstained=template.needs_review,
            )
        )
    return calibrate_policy(
        tuple(subject_results),
        tuple(template_results),
        subject_minimum_margin=MINIMUM_MARGIN_FLOOR,
        template_minimum_margin=MINIMUM_MARGIN_FLOOR,
    )


def main(arguments: Sequence[str] | None = None) -> int:
    """Print Phase 5 held-out thresholds and optionally verify the packaged policy."""
    parser = argparse.ArgumentParser(
        description="Calibrate student subject/template policy from made-up held-out data."
    )
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--model-cache", type=Path, default=DEFAULT_MODEL_CACHE)
    parser.add_argument("--verify-policy", type=Path)
    args = parser.parse_args(arguments)

    report = derive_policy(load_corpus(args.corpus), args.model_cache)
    if args.verify_policy is not None:
        packaged = load_calibrated_policy(args.verify_policy)
        if packaged != report.policy:
            raise RuntimeError("패키지 보정 정책이 held-out 재계산 결과와 일치하지 않습니다.")
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
