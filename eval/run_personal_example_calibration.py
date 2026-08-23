from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

import numpy as np

from sort_pilot.classification import (
    FastEmbedE5Encoder,
    E5SubjectClassifier,
    SubjectEvidence,
    TemplateClassifier,
    TemplateEvidence,
    load_calibrated_policy,
    load_phase8_optional_evidence,
    load_subject_profiles,
    load_template_profiles,
)
from sort_pilot.classification.personal_calibration import (
    PersonalCalibrationCase,
    calibrate_personal_examples,
)
from sort_pilot.classification.personal_examples import load_personal_example_policy
from sort_pilot.classification.result import CandidateScore
from sort_pilot.evaluation import CorpusCase, load_corpus


DEFAULT_MODEL_CACHE = Path("data/models/fastembed")


def _nearest_by_label(
    query: np.ndarray,
    training: tuple[CorpusCase, ...],
    training_embeddings: np.ndarray,
    label,
    allowed_labels: set[str],
) -> tuple[CandidateScore, ...]:
    """Return maximum made-up training similarity per eligible approved label."""
    scores: dict[str, float] = {}
    for case, embedding in zip(training, training_embeddings, strict=True):
        value = label(case)
        if value not in allowed_labels:
            continue
        similarity = float(query @ embedding)
        scores[value] = max(scores.get(value, -1.0), similarity)
    return tuple(
        CandidateScore(value, score)
        for value, score in sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    )


def derive_personal_example_policy(
    training: tuple[CorpusCase, ...],
    held_out: tuple[CorpusCase, ...],
    model_cache: Path,
):
    """Calibrate nearest-example influence from made-up training and held-out cases."""
    encoder = FastEmbedE5Encoder(model_cache, allow_download=False)
    subject_classifier = E5SubjectClassifier(encoder)
    template_classifier = TemplateClassifier(encoder)
    subject_profiles = load_subject_profiles()
    template_profiles = load_template_profiles()
    policy = load_calibrated_policy()
    optional_evidence = load_phase8_optional_evidence()
    training_embeddings = encoder.encode(
        tuple(f"query: {SubjectEvidence(case.file_name, case.text).embedding_text}" for case in training)
    )
    held_out_embeddings = encoder.encode(
        tuple(f"query: {SubjectEvidence(case.file_name, case.text).embedding_text}" for case in held_out)
    )
    template_scales = {
        profile.evidence_weights.personal_example / profile.evidence_weights.total
        for profile in template_profiles
    }
    if len(template_scales) != 1:
        raise RuntimeError("템플릿별 개인 예시 기여 배율이 달라 보정할 수 없습니다.")
    template_scale = next(iter(template_scales))
    subject_cases: list[PersonalCalibrationCase] = []
    template_cases: list[PersonalCalibrationCase] = []
    template_labels = {item.template.value for item in template_profiles}
    for case, query in zip(held_out, held_out_embeddings, strict=True):
        subject = subject_classifier.classify(
            SubjectEvidence(case.file_name, case.text),
            case.student,
            subject_profiles,
            query_embedding=query,
            lexical_weight=optional_evidence.subject_kiwi_lexical_weight,
            filename_weight=optional_evidence.subject_filename_weight,
            pmi_weight=optional_evidence.subject_pmi_weight,
            language_weight=optional_evidence.subject_language_weight,
        )
        template = template_classifier.classify(
            TemplateEvidence(case.file_name, case.text),
            template_profiles,
            query_embedding=query,
            personal_example_weight=0.0,
        )
        subject_cases.append(
            PersonalCalibrationCase(
                candidates=subject.candidates,
                similarities=_nearest_by_label(
                    query,
                    training,
                    training_embeddings,
                    lambda item: item.subject,
                    set(case.student.allowed_subjects),
                ),
                correct_label=case.subject,
            )
        )
        template_cases.append(
            PersonalCalibrationCase(
                candidates=template.candidates,
                similarities=_nearest_by_label(
                    query,
                    training,
                    training_embeddings,
                    lambda item: item.template.value,
                    template_labels,
                ),
                correct_label=case.template.value,
                contribution_scale=template_scale,
            )
        )
    return calibrate_personal_examples(
        tuple(subject_cases),
        tuple(template_cases),
        policy.subject,
        policy.template,
        policy.targets,
    )


def main(arguments: Sequence[str] | None = None) -> int:
    """Print Phase 7 calibration and optionally verify the packaged influence."""
    parser = argparse.ArgumentParser(
        description="Calibrate personal-example influence from made-up student data."
    )
    parser.add_argument("training_corpus", type=Path)
    parser.add_argument("held_out_corpus", type=Path)
    parser.add_argument("--model-cache", type=Path, default=DEFAULT_MODEL_CACHE)
    parser.add_argument("--verify-policy", type=Path)
    args = parser.parse_args(arguments)
    report = derive_personal_example_policy(
        load_corpus(args.training_corpus),
        load_corpus(args.held_out_corpus),
        args.model_cache,
    )
    if args.verify_policy is not None:
        packaged = load_personal_example_policy(args.verify_policy)
        if packaged != report.policy:
            raise RuntimeError("패키지 개인 예시 정책이 made-up 재계산 결과와 일치하지 않습니다.")
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
