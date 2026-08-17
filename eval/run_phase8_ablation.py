from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Sequence

import numpy as np
import psutil

from sort_pilot.classification import (
    E5SubjectClassifier,
    FastEmbedE5Encoder,
    Phase8OptionalEvidence,
    PolicyRoute,
    SubjectEvidence,
    TemplateClassifier,
    TemplateEvidence,
    load_calibrated_policy,
    load_phase8_optional_evidence,
    load_subject_profiles,
    load_template_profiles,
    route_axis,
)
from sort_pilot.classification.e5 import _embedding_matrix
from sort_pilot.classifier_engine.extract import tokenize
from sort_pilot.evaluation import (
    Phase8Case,
    Phase8GateReport,
    ResourceMeasurement,
    load_phase8_corpus,
    paired_accuracy,
)


DEFAULT_MODEL_CACHE = Path("data/models/fastembed")
DEFAULT_VISION_MODEL = Path("data/models/yolov8n.onnx")
DEFAULT_SYNTHETIC_IMAGE = Path("eval/synthetic_phase8_image.ppm")
RESOURCE_REPETITIONS = 20
PILOT_SUBJECT_LEXICAL_WEIGHT = 0.05
_RESOURCE_MARKER = "PHASE8_RESOURCE="


def _percentile(values: Sequence[float], quantile: float) -> float:
    """Return one linearly interpolated percentile for resource measurements."""
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("resource percentile에는 하나 이상의 값이 필요합니다.")
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _variant_outcomes(
    cases: tuple[Phase8Case, ...],
    subject_classifier: E5SubjectClassifier,
    template_classifier: TemplateClassifier,
    subject_embeddings: np.ndarray,
    template_embeddings: np.ndarray,
    *,
    use_layout: bool,
    use_pmi: bool,
    use_visual: bool,
    subject_lexical_weight: float,
) -> tuple[tuple[bool, ...], tuple[bool, ...], tuple[bool, ...]]:
    """Rank one ordered evidence variant and return per-axis correctness values."""
    subject_profiles = load_subject_profiles()
    template_profiles = load_template_profiles()
    policy = load_calibrated_policy()
    subject_correct: list[bool] = []
    template_correct: list[bool] = []
    for case, subject_embedding, template_embedding in zip(
        cases,
        subject_embeddings,
        template_embeddings,
        strict=True,
    ):
        text = case.layout_text if use_layout else case.phase7_text
        subject = subject_classifier.classify(
            SubjectEvidence(case.file_name, text, tuple(tokenize(text))),
            case.student,
            subject_profiles,
            query_embedding=subject_embedding,
            lexical_weight=subject_lexical_weight,
        )
        template = template_classifier.classify(
            TemplateEvidence(
                file_name=case.file_name,
                natural_text=text,
                pmi_collocations=case.pmi_collocations if use_pmi else (),
                ocr_layout_terms=case.ocr_layout_evidence if use_layout else (),
                visual_terms=case.visual_evidence if use_visual else (),
            ),
            template_profiles,
            query_embedding=template_embedding,
            personal_example_weight=0.0,
        )
        subject_route = route_axis(subject, policy.subject, policy.version)
        template_route = route_axis(template, policy.template, policy.version)
        subject_correct.append(
            subject_route.route is PolicyRoute.ACCEPT_LOCAL
            and subject.label == case.subject
        )
        template_correct.append(
            template_route.route is PolicyRoute.ACCEPT_LOCAL
            and template.label == case.template.value
        )
    subject_values = tuple(subject_correct)
    template_values = tuple(template_correct)
    return (
        subject_values,
        template_values,
        tuple(
            subject and template
            for subject, template in zip(subject_values, template_values, strict=True)
        ),
    )


def _accuracy_rates(
    outcomes: tuple[tuple[bool, ...], tuple[bool, ...], tuple[bool, ...]],
) -> dict[str, float]:
    """Serialize subject, template, and combined-path rates for one variant."""
    subject, template, combined = outcomes
    return {
        "subject_accuracy": sum(subject) / len(subject),
        "template_accuracy": sum(template) / len(template),
        "combined_path_accuracy": sum(combined) / len(combined),
    }


def _measure_resource_child(
    variant: str,
    model_cache: Path,
    vision_model: Path,
    image_path: Path,
) -> ResourceMeasurement:
    """Measure one isolated baseline or scheduled local-model process."""
    from sort_pilot.classifier_engine.vision import infer

    include_visual = variant == "baseline"
    encoder = FastEmbedE5Encoder(model_cache, allow_download=False)
    encoder.encode(("query: 과목과 템플릿을 분류하는 짧은 문장",))
    latencies: list[float] = []
    for _ in range(RESOURCE_REPETITIONS):
        started = time.perf_counter()
        encoder.encode(("query: 과목과 템플릿을 분류하는 짧은 문장",))
        if include_visual:
            infer(image_path, vision_model)
        latencies.append((time.perf_counter() - started) * 1000.0)
    memory = psutil.Process().memory_info()
    peak_bytes = float(getattr(memory, "peak_wset", memory.rss))
    return ResourceMeasurement(
        p95_latency_ms=_percentile(latencies, 0.95),
        peak_memory_mb=peak_bytes / (1024 * 1024),
    )


def _measure_resource_subprocess(
    variant: str,
    corpus: Path,
    model_cache: Path,
    vision_model: Path,
    image_path: Path,
) -> ResourceMeasurement:
    """Run one resource variant in a fresh process so peak memory stays independent."""
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        str(corpus),
        "--model-cache",
        str(model_cache),
        "--vision-model",
        str(vision_model),
        "--synthetic-image",
        str(image_path),
        "--resource-child",
        variant,
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    line = next(
        (value for value in completed.stdout.splitlines() if value.startswith(_RESOURCE_MARKER)),
        None,
    )
    if line is None:
        raise RuntimeError("Phase 8 resource child가 측정 결과를 반환하지 않았습니다.")
    raw = json.loads(line.removeprefix(_RESOURCE_MARKER))
    return ResourceMeasurement(
        p95_latency_ms=raw["p95_latency_ms"],
        peak_memory_mb=raw["peak_memory_mb"],
    )


def run_ablation(
    corpus_path: Path,
    model_cache: Path,
    vision_model: Path,
    image_path: Path,
    selected_evidence: Phase8OptionalEvidence | None = None,
) -> dict:
    """Run paired local evidence ablations and the complete agreed Phase 8 gate."""
    cases = load_phase8_corpus(corpus_path)
    encoder = FastEmbedE5Encoder(model_cache, allow_download=False)
    subject_classifier = E5SubjectClassifier(encoder)
    template_classifier = TemplateClassifier(encoder)
    phase7_texts = tuple(
        f"query: {SubjectEvidence(case.file_name, case.phase7_text).embedding_text}"
        for case in cases
    )
    layout_texts = tuple(
        f"query: {SubjectEvidence(case.file_name, case.layout_text).embedding_text}"
        for case in cases
    )
    phase7_embeddings = _embedding_matrix(encoder.encode(phase7_texts), len(cases))
    layout_embeddings = _embedding_matrix(encoder.encode(layout_texts), len(cases))

    variants: dict[str, tuple[tuple[bool, ...], tuple[bool, ...], tuple[bool, ...]]] = {}
    for name, use_layout, use_pmi, use_visual, subject_lexical_weight in (
        ("phase7", False, True, True, 0.0),
        ("full", True, True, True, PILOT_SUBJECT_LEXICAL_WEIGHT),
        ("without_ocr_layout", False, True, True, 0.0),
        ("without_pmi", True, False, True, PILOT_SUBJECT_LEXICAL_WEIGHT),
        ("without_visual", True, True, False, PILOT_SUBJECT_LEXICAL_WEIGHT),
        ("layout_only", True, False, False, PILOT_SUBJECT_LEXICAL_WEIGHT),
    ):
        variants[name] = _variant_outcomes(
            cases,
            subject_classifier,
            template_classifier,
            layout_embeddings if use_layout else phase7_embeddings,
            phase7_embeddings,
            use_layout=use_layout,
            use_pmi=use_pmi,
            use_visual=use_visual,
            subject_lexical_weight=subject_lexical_weight,
        )

    full = variants["full"]
    pmi_contribution = paired_accuracy(variants["without_pmi"][1], full[1])
    visual_contribution = paired_accuracy(variants["without_visual"][1], full[1])
    if selected_evidence is not None and (
        not selected_evidence.ocr_layout
        or selected_evidence.subject_kiwi_lexical_weight
        != PILOT_SUBJECT_LEXICAL_WEIGHT
    ):
        raise ValueError("고정된 Phase 8 선택이 개발 측정과 일치하지 않습니다.")
    retain_pmi = (
        pmi_contribution.passes
        if selected_evidence is None
        else selected_evidence.pmi
    )
    retain_visual = (
        visual_contribution.passes
        if selected_evidence is None
        else selected_evidence.yolo_lvis_visual
    )
    selected_name = (
        "full"
        if retain_pmi and retain_visual
        else "without_visual"
        if retain_pmi
        else "without_pmi"
        if retain_visual
        else "layout_only"
    )
    selected = variants[selected_name]
    baseline_resources = _measure_resource_subprocess(
        "baseline",
        corpus_path,
        model_cache,
        vision_model,
        image_path,
    )
    candidate_resources = _measure_resource_subprocess(
        "candidate",
        corpus_path,
        model_cache,
        vision_model,
        image_path,
    )
    gate = Phase8GateReport(
        subject=paired_accuracy(variants["phase7"][0], selected[0]),
        template=paired_accuracy(variants["phase7"][1], selected[1]),
        combined_path=paired_accuracy(variants["phase7"][2], selected[2]),
        baseline_resources=baseline_resources,
        candidate_resources=candidate_resources,
    )
    return {
        "corpus_cases": len(cases),
        "host_total_memory_mb": psutil.virtual_memory().total / (1024 * 1024),
        "variants": {name: _accuracy_rates(value) for name, value in variants.items()},
        "channel_contribution": {
            "pmi": pmi_contribution.to_dict(),
            "visual": visual_contribution.to_dict(),
        },
        "selected_configuration": {
            "source": "development_ablation" if selected_evidence is None else "fixed_selection",
            "variant": selected_name,
            "ocr_layout": True,
            "subject_kiwi_lexical_weight": PILOT_SUBJECT_LEXICAL_WEIGHT,
            "pmi": retain_pmi,
            "yolo_lvis_visual": retain_visual,
            "model_session_scheduling": False,
        },
        "gate_report": gate.to_dict(),
    }


def main(arguments: Sequence[str] | None = None) -> int:
    """Print aggregate made-up Phase 8 ablation and resource measurements."""
    parser = argparse.ArgumentParser(
        description="Measure Phase 8 optional evidence using only made-up cases."
    )
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--model-cache", type=Path, default=DEFAULT_MODEL_CACHE)
    parser.add_argument("--vision-model", type=Path, default=DEFAULT_VISION_MODEL)
    parser.add_argument("--synthetic-image", type=Path, default=DEFAULT_SYNTHETIC_IMAGE)
    parser.add_argument("--verify-selection", type=Path)
    parser.add_argument(
        "--resource-child",
        choices=("baseline", "candidate"),
    )
    args = parser.parse_args(arguments)
    if args.resource_child is not None:
        measurement = _measure_resource_child(
            args.resource_child,
            args.model_cache,
            args.vision_model,
            args.synthetic_image,
        )
        print(_RESOURCE_MARKER + json.dumps(measurement.to_dict()))
        return 0
    report = run_ablation(
        args.corpus,
        args.model_cache,
        args.vision_model,
        args.synthetic_image,
        (
            load_phase8_optional_evidence(args.verify_selection)
            if args.verify_selection is not None
            else None
        ),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["gate_report"]["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
