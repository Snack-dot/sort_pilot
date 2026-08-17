from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from .curriculum import (
    OCCUPATION,
    SUBJECT_CATALOG_VERSION,
    Semester,
    StudentProfile,
    StudentType,
    load_subject_catalog,
)


class StudentOnboardingDialog(QDialog):
    """Collect only the bounded student settings required by the MVP hierarchy."""

    def __init__(
        self,
        current: StudentProfile | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Build a fixed-choice form and optionally preselect a saved profile."""
        super().__init__(parent)
        self.profile: StudentProfile | None = None
        self.setWindowTitle("Sort Pilot - 학생 설정")
        self.setModal(True)
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        introduction = QLabel(
            "파일을 정리할 학생 경로를 설정합니다. 학교명, 시간표, 교육기관 정보는 수집하지 않습니다."
        )
        introduction.setWordWrap(True)
        layout.addWidget(introduction)

        form = QFormLayout()
        form.addRow("직업", QLabel(OCCUPATION))

        self.student_type = QComboBox()
        for value in StudentType:
            self.student_type.addItem(value.value, value.value)
        form.addRow("학생 유형", self.student_type)

        self.grade = QComboBox()
        for value in (1, 2, 3):
            self.grade.addItem(f"{value}학년", value)
        form.addRow("학년", self.grade)

        self.semester = QComboBox()
        for value in Semester:
            self.semester.addItem(value.value, value.value)
        form.addRow("학기", self.semester)
        form.addRow("과목 기준", QLabel(SUBJECT_CATALOG_VERSION))
        layout.addLayout(form)

        self.subjects = QLabel()
        self.subjects.setWordWrap(True)
        layout.addWidget(self.subjects)

        note = QLabel("학년과 학기는 폴더 경로에만 사용되며 과목 시간표를 추정하지 않습니다.")
        note.setWordWrap(True)
        layout.addWidget(note)

        buttons = QDialogButtonBox()
        buttons.addButton("저장", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton("취소", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.student_type.currentIndexChanged.connect(lambda _index: self._update_subjects())
        if current is not None:
            self.student_type.setCurrentText(current.student_type.value)
            self.grade.setCurrentText(f"{current.grade}학년")
            self.semester.setCurrentText(current.semester.value)
        self._update_subjects()

    def _selected_profile(self) -> StudentProfile:
        """Convert the current fixed-choice selections into a validated profile."""
        return StudentProfile(
            student_type=StudentType(str(self.student_type.currentData())),
            grade=int(self.grade.currentData()),
            semester=Semester(str(self.semester.currentData())),
        )

    def _update_subjects(self) -> None:
        """Show the exact catalog candidates for the selected student type."""
        student_type = StudentType(str(self.student_type.currentData()))
        values = load_subject_catalog().subjects_for(student_type)
        self.subjects.setText("사용 가능한 과목: " + ", ".join(values))

    def _accept(self) -> None:
        """Freeze the validated selections for the controller to persist."""
        self.profile = self._selected_profile()
        self.accept()
