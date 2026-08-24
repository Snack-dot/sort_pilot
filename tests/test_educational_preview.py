from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QLabel,
    QTableWidget,
)

from sort_pilot.classification import (
    AxisDecision,
    CandidateScore,
    DecisionSource,
    E5_MODEL_ID,
    E5_VECTOR_SIZE,
    EducationalClassificationOutput,
    EducationalClassificationResult,
    OrganizationPlan,
    Template,
)
from sort_pilot.curriculum import Semester, StudentType, default_profile
from sort_pilot.educational_preview import (
    ClickOnlyComboBox,
    EducationalPreviewDialog,
    REVIEW_GROUP_KEY,
    _confirmation_message,
    apply_preview_selection,
    build_preview_groups,
    freeze_organization_plan,
)
from sort_pilot.history import HistoryStore
from sort_pilot.organizer import execute_organization_plans, undo_latest


def _decision(
    labels: tuple[str, ...],
    *,
    label: str | None = None,
    model_version: str = E5_MODEL_ID,
) -> AxisDecision:
    candidates = tuple(
        CandidateScore(value, 0.9 - index * 0.1)
        for index, value in enumerate(labels)
    )
    unresolved = label is None
    return AxisDecision(
        label=label,
        raw_score=candidates[0].raw_score,
        calibrated_confidence=None,
        margin=0.1,
        candidates=candidates,
        evidence=(),
        source=DecisionSource.REVIEW if unresolved else DecisionSource.LOCAL,
        model_version=model_version,
        profile_version="profiles-v1",
        policy_version="policy-v1",
        needs_review=unresolved,
    )


def _classification(*, unresolved_subject: bool = False, subject: str = "수학"):
    subject_labels = ("수학", "과학", "국어")
    template_labels = tuple(item.value for item in Template)
    return EducationalClassificationResult(
        default_profile(StudentType.MIDDLE, 1, Semester.FIRST),
        _decision(subject_labels, label=None if unresolved_subject else subject),
        _decision(template_labels, label=Template.ASSIGNMENT.value),
    )


def _output(
    source: Path,
    *,
    unresolved_subject: bool = False,
    subject: str = "수학",
):
    return EducationalClassificationOutput(
        source=source,
        fingerprint="a" * 40,
        classification=_classification(
            unresolved_subject=unresolved_subject,
            subject=subject,
        ),
        embedding=(1.0, *(0.0 for _ in range(E5_VECTOR_SIZE - 1))),
        lexical_evidence=("함수", "문제"),
    )


def test_preview_resolves_needs_review_and_records_user_source(tmp_path: Path):
    output = _output(tmp_path / "함수자료.pdf", unresolved_subject=True)

    resolved = apply_preview_selection(
        output.classification,
        "과학",
        Template.ASSIGNMENT.value,
    )

    assert resolved.subject.label == "과학"
    assert resolved.subject.source is DecisionSource.USER
    assert resolved.template.source is DecisionSource.LOCAL
    assert not resolved.needs_review
    assert resolved.folder.endswith("/과학/과제")


def test_preview_groups_paths_with_representative_file_and_review_last(
    tmp_path: Path,
) -> None:
    outputs = (
        _output(tmp_path / "zeta.pdf"),
        _output(tmp_path / "alpha.pdf"),
        _output(tmp_path / "검토.pdf", unresolved_subject=True),
    )

    groups = build_preview_groups(outputs)

    assert len(groups) == 2
    assert groups[0].title.endswith("/수학/과제")
    assert groups[0].count == 2
    assert groups[0].representative_file == "alpha.pdf"
    assert groups[0].file_preview == "alpha.pdf 외 1개"
    assert groups[1].key == REVIEW_GROUP_KEY
    assert groups[1].title == "확인이 필요한 파일"
    assert groups[1].file_preview == "검토.pdf"


def test_dialog_keeps_flat_file_table_out_of_the_main_preview(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    outputs = (
        _output(tmp_path / "desktop" / "zeta.pdf"),
        _output(tmp_path / "desktop" / "alpha.pdf"),
        _output(tmp_path / "downloads" / "검토.pdf", unresolved_subject=True),
    )
    dialog = EducationalPreviewDialog(
        outputs,
        tmp_path / "desktop",
        tmp_path / "downloads",
    )
    try:
        assert dialog.summary.topLevelItemCount() == 2
        assert dialog.summary.topLevelItem(0).text(0) == ""
        assert dialog.table.isHidden()
        destination = dialog.summary.itemWidget(dialog.summary.topLevelItem(0), 1)
        assert isinstance(destination, QComboBox)
        assert isinstance(destination, ClickOnlyComboBox)
        assert not destination.view().dragEnabled()
        assert (
            destination.view().dragDropMode()
            is QAbstractItemView.DragDropMode.NoDragDrop
        )
        assert destination.currentData() is None
        destination.setCurrentIndex(destination.findData("desktop"))
        app.processEvents()
        for row in dialog.groups[0].row_indexes:
            row_destination = dialog.table.cellWidget(row, 2)
            assert isinstance(row_destination, QComboBox)
            assert row_destination.currentData() == "desktop"
        assert destination.minimumWidth() == 240
        assert dialog.summary.columnWidth(1) == 240
        assert dialog.summary.columnWidth(2) == 180
        assert dialog.summary.objectName() == "destinationSummary"
        assert dialog.organize_button.objectName() == "primaryAction"
        assert "bulkDestinationCard" in dialog.styleSheet()
        path_labels = dialog.summary.findChildren(QLabel, "summaryPath")
        preview_labels = dialog.summary.findChildren(QLabel, "summaryFilePreview")
        assert path_labels[0].text().endswith("/수학/과제")
        assert path_labels[1].text() == "확인이 필요한 파일"
        assert preview_labels[0].text() == "alpha.pdf 외 1개"
        assert path_labels[1].property("review") is True
        assert preview_labels[1].property("review") is True
        assert "#dc2626" in dialog.styleSheet()
        assert dialog.summary.topLevelItem(0).sizeHint(0).height() == 64
        assert "QLabel#summaryPath" in dialog.styleSheet()
        assert "QLabel#summaryFilePreview { color: #8a8a8a" in dialog.styleSheet()
        assert "#4f7cff" not in dialog.styleSheet()
        assert "#b45309" not in dialog.styleSheet()
        assert "QPushButton#primaryAction { background: #000000" in dialog.styleSheet()
        count_alignment = dialog.summary.topLevelItem(0).textAlignment(2)
        assert count_alignment & Qt.AlignmentFlag.AlignRight
        assert dialog.organize_button.text() == "3개 파일 이동"
    finally:
        dialog.close()


def test_dialog_applies_one_destination_to_every_group(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    outputs = (
        _output(tmp_path / "desktop" / "자료.pdf"),
        _output(tmp_path / "downloads" / "과학.pdf", subject="과학"),
        _output(
            tmp_path / "desktop" / "검토.pdf",
            unresolved_subject=True,
        ),
    )
    dialog = EducationalPreviewDialog(
        outputs,
        tmp_path / "desktop",
        tmp_path / "downloads",
    )
    try:
        selector = dialog.bulk_destination_selector
        assert selector.currentData() is None
        selector.setCurrentIndex(selector.findData("downloads"))
        app.processEvents()

        resolved_groups = [group for group in dialog.groups if not group.needs_review]
        review_group = next(group for group in dialog.groups if group.needs_review)
        assert all(
            dialog._group_destination_selectors[group.key].currentData()
            == "downloads"
            for group in resolved_groups
        )
        assert dialog._group_destination_selectors[review_group.key].currentData() is None
        review_row_selector = dialog.table.cellWidget(review_group.row_indexes[0], 2)
        assert isinstance(review_row_selector, QComboBox)
        assert review_row_selector.currentData() == "desktop"

        first_group = resolved_groups[0]
        group_selector = dialog._group_destination_selectors[first_group.key]
        group_selector.setCurrentIndex(group_selector.findData("desktop"))
        app.processEvents()
        assert selector.currentData() is None
    finally:
        dialog.close()


def test_group_details_are_alphabetical_and_column_aligned(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = QApplication.instance() or QApplication([])
    dialog = EducationalPreviewDialog(
        (
            _output(tmp_path / "zeta.pdf"),
            _output(tmp_path / "alpha.pdf"),
        ),
        tmp_path / "desktop",
        tmp_path / "downloads",
    )
    captured: list[QDialog] = []

    def reject_details(detail_dialog: QDialog) -> QDialog.DialogCode:
        captured.append(detail_dialog)
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(QDialog, "exec", reject_details)
    try:
        dialog._open_group_details(dialog.summary.topLevelItem(0), 0)
        app.processEvents()
        details = captured[0].findChild(QTableWidget, "groupDetailTable")
        assert details is not None
        assert details.item(0, 0).text() == "alpha.pdf"
        assert details.item(1, 0).text() == "zeta.pdf"
        assert details.verticalHeader().defaultSectionSize() == 46
        subject_selector = details.cellWidget(0, 2)
        assert isinstance(subject_selector, ClickOnlyComboBox)
        assert not subject_selector.view().dragEnabled()
        assert (
            subject_selector.view().dragDropMode()
            is QAbstractItemView.DragDropMode.NoDragDrop
        )
        assert details.columnWidth(2) == 150
        assert details.columnWidth(3) == 150
        assert details.columnWidth(4) == 72
        assert details.item(0, 4).textAlignment() & Qt.AlignmentFlag.AlignCenter
    finally:
        dialog.close()


def test_dialog_uses_product_labels_in_non_mutating_demo_mode(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    dialog = EducationalPreviewDialog(
        (_output(tmp_path / "desktop" / "자료.pdf"),),
        tmp_path / "desktop",
        tmp_path / "downloads",
        test_mode=True,
    )
    try:
        app.processEvents()
        assert dialog.test_mode
        assert dialog.organize_button.text() == "1개 파일 이동"
        approved = dialog.approved_plans()
        message = _confirmation_message(approved, test_mode=True)
        assert "1개 파일을 이동할까요?" in message
        assert "테스트" not in message
    finally:
        dialog.close()


def test_personal_example_records_the_embedding_model_after_gemma_correction(
    tmp_path: Path,
) -> None:
    output = _output(tmp_path / "함수자료.pdf")
    original = EducationalClassificationResult(
        output.classification.student,
        _decision(("수학", "과학", "국어"), label="수학", model_version="gemma-local"),
        output.classification.template,
    )
    gemma_output = EducationalClassificationOutput(
        source=output.source,
        fingerprint=output.fingerprint,
        classification=original,
        embedding=output.embedding,
        lexical_evidence=output.lexical_evidence,
    )

    approved = freeze_organization_plan(
        gemma_output,
        tmp_path / "sorted",
        "과학",
        Template.ASSIGNMENT.value,
    )

    example = approved.personal_example()
    assert example is not None
    assert example.versions.embedding_model_version == E5_MODEL_ID


def test_preview_rejects_subject_or_template_outside_fixed_choices(tmp_path: Path):
    classification = _output(tmp_path / "자료.pdf").classification

    with pytest.raises(ValueError, match="과목 카탈로그"):
        apply_preview_selection(classification, "물리학", "과제")
    with pytest.raises(ValueError, match="다섯 템플릿"):
        apply_preview_selection(classification, "수학", "기타")


def test_approval_freezes_exact_collision_resolved_paths(tmp_path: Path):
    source = tmp_path / "incoming" / "자료.pdf"
    source.parent.mkdir()
    source.write_bytes(b"made-up")
    destination_root = tmp_path / "organized"
    existing = (
        destination_root
        / "학생"
        / "중학생"
        / "1학년"
        / "1학기"
        / "수학"
        / "과제"
        / source.name
    )
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"existing")

    approved = freeze_organization_plan(
        _output(source),
        destination_root,
        "수학",
        "과제",
    )

    assert approved.plan.source == source
    assert approved.plan.destination == existing.with_name("자료_1.pdf")
    with pytest.raises(FrozenInstanceError):
        approved.plan.destination = tmp_path / "changed.pdf"


def test_batch_reservations_freeze_distinct_collision_paths(tmp_path: Path):
    first = tmp_path / "first" / "자료.pdf"
    second = tmp_path / "second" / "자료.pdf"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    reserved: set[Path] = set()

    one = freeze_organization_plan(_output(first), tmp_path / "out", "수학", "과제", reserved)
    two = freeze_organization_plan(_output(second), tmp_path / "out", "수학", "과제", reserved)

    assert one.plan.destination.name == "자료.pdf"
    assert two.plan.destination.name == "자료_1.pdf"


def test_final_confirmation_names_the_exact_collision_resolved_path(tmp_path: Path) -> None:
    source = tmp_path / "desktop" / "자료.pdf"
    source.parent.mkdir()
    source.write_bytes(b"made-up")
    expected = source.parent.joinpath(
        "학생",
        "중학생",
        "1학년",
        "1학기",
        "수학",
        "과제",
        "자료.pdf",
    )
    expected.parent.mkdir(parents=True)
    expected.write_bytes(b"existing")
    approved = freeze_organization_plan(
        _output(source),
        source.parent,
        "수학",
        "과제",
    )
    exact = expected.with_name("자료_1.pdf")

    assert approved.plan.destination == exact
    assert str(exact) in _confirmation_message((approved,))


def test_preview_correction_builds_separate_path_free_personal_example(tmp_path: Path):
    source = tmp_path / "자료.pdf"
    approved = freeze_organization_plan(
        _output(source),
        tmp_path / "out",
        "과학",
        "증빙서류",
    )

    example = approved.personal_example()

    assert example is not None
    assert example.approved_subject == "과학"
    assert example.approved_template == "증빙서류"
    assert example.original_prediction.subject == "수학"
    assert example.original_prediction.template == "과제"
    assert "path" not in str(example.to_dict()).casefold()


def test_unchanged_preview_does_not_create_personal_example(tmp_path: Path):
    approved = freeze_organization_plan(
        _output(tmp_path / "자료.pdf"),
        tmp_path / "out",
        "수학",
        "과제",
    )

    assert approved.personal_example() is None


def test_exact_approved_plan_executes_and_existing_undo_restores(tmp_path: Path):
    source = tmp_path / "incoming" / "자료.pdf"
    source.parent.mkdir()
    source.write_bytes(b"made-up")
    approved = freeze_organization_plan(
        _output(source),
        tmp_path / "out",
        "수학",
        "과제",
    )
    history = HistoryStore(tmp_path / "history.json")

    completed = execute_organization_plans([approved.plan], history)

    assert completed[0].destination_path == approved.plan.destination.resolve()
    assert approved.plan.destination.is_file()
    assert not source.exists()
    restored = undo_latest(history)
    assert len(restored) == 1
    assert source.is_file()
    assert not approved.plan.destination.exists()


def test_organization_plan_rejects_arbitrary_filename_change(tmp_path: Path):
    source = tmp_path / "자료.pdf"
    classification = _classification()
    destination = tmp_path.joinpath(*classification.folder.split("/"), "바뀐이름.pdf")

    with pytest.raises(ValueError, match="파일 이름"):
        OrganizationPlan(source, destination, classification)
