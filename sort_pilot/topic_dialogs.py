from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .classifier_engine.hierarchy import TYPE_FAMILIES
from .classifier_engine.topics import (
    TopicProfile,
    TopicProfileStore,
    normalize_tag,
    validate_topic_name,
)
from .filters import is_safe_candidate


@dataclass(frozen=True, slots=True)
class ProfileEditRequest:
    """One validated profile edit plus learn-only example file paths."""

    profile: TopicProfile
    example_paths: tuple[Path, ...]


class ExampleDropList(QListWidget):
    """List widget accepting safe local files as learn-only topic examples."""

    paths_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Enable URL drops and extended selection for removable examples."""
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

    def dragEnterEvent(self, event) -> None:
        """Accept drags containing one or more local file URLs."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        """Keep an accepted local-file drag active over the list."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        """Add unique safe files from a URL drop without moving them."""
        self.add_paths(Path(url.toLocalFile()) for url in event.mimeData().urls())
        event.acceptProposedAction()

    def add_paths(self, paths) -> None:
        """Append unique safe example paths and reject folders/executables."""
        known = {self.item(index).data(Qt.ItemDataRole.UserRole) for index in range(self.count())}
        for path in paths:
            resolved = path.resolve()
            value = str(resolved)
            if value not in known and is_safe_candidate(resolved):
                item = QListWidgetItem(resolved.name)
                item.setData(Qt.ItemDataRole.UserRole, value)
                item.setToolTip(value)
                self.addItem(item)
                known.add(value)
        self.paths_changed.emit()

    def paths(self) -> tuple[Path, ...]:
        """Return all currently listed example paths in display order."""
        return tuple(
            Path(self.item(index).data(Qt.ItemDataRole.UserRole))
            for index in range(self.count())
        )


class TopicManagerDialog(QDialog):
    """Create and maintain family-specific topic names, tags, and examples."""

    def __init__(self, store: TopicProfileStore, parent=None) -> None:
        """Build the profile browser/editor without creating physical folders."""
        super().__init__(parent)
        self.store = store
        self.profiles = store.load()
        self.request: ProfileEditRequest | None = None
        self.current_profile: TopicProfile | None = None
        self.setWindowTitle("Sort Pilot - 폴더/태그 관리")
        self.resize(720, 560)

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.family = QComboBox()
        self.family.addItems(TYPE_FAMILIES)
        self.family.currentTextChanged.connect(self._refresh_profiles)
        self.profile_list = QListWidget()
        self.profile_list.currentRowChanged.connect(self._load_selected)
        top.addWidget(self.family, 1)
        new_button = QPushButton("새 주제")
        new_button.clicked.connect(self._new_profile)
        top.addWidget(new_button)
        delete_button = QPushButton("선택 삭제")
        delete_button.clicked.connect(self._delete_selected)
        top.addWidget(delete_button)
        self.delete_button = delete_button
        layout.addLayout(top)
        layout.addWidget(self.profile_list)

        form = QFormLayout()
        self.name = QLineEdit()
        self.tags = QTextEdit()
        self.tags.setPlaceholderText("쉼표 또는 줄바꿈으로 태그 입력")
        self.enabled = QCheckBox("분류에 사용")
        self.enabled.setChecked(True)
        form.addRow("주제 폴더 이름", self.name)
        form.addRow("태그 목록", self.tags)
        form.addRow("상태", self.enabled)
        layout.addLayout(form)

        layout.addWidget(QLabel("예시 파일 (학습만 하며 이동하지 않음)"))
        self.examples = ExampleDropList()
        layout.addWidget(self.examples)
        example_buttons = QHBoxLayout()
        add_examples = QPushButton("예시 파일 선택")
        add_examples.clicked.connect(self._choose_examples)
        remove_examples = QPushButton("선택 제거")
        remove_examples.clicked.connect(self._remove_examples)
        example_buttons.addWidget(add_examples)
        example_buttons.addWidget(remove_examples)
        layout.addLayout(example_buttons)
        self.add_examples_button = add_examples
        self.remove_examples_button = remove_examples

        buttons = QDialogButtonBox()
        save_button = buttons.addButton("저장", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton("닫기", QDialogButtonBox.ButtonRole.RejectRole)
        save_button.clicked.connect(self._prepare_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._refresh_profiles()

    def _refresh_profiles(self) -> None:
        """Reload profiles for the selected family after edits or deletion."""
        self.profiles = self.store.load()
        family = self.family.currentText()
        visible = [profile for profile in self.profiles if profile.family == family]
        self.profile_list.clear()
        for profile in visible:
            label = profile.name
            if not profile.enabled:
                label += " [비활성]"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, profile.id)
            self.profile_list.addItem(item)
        self._new_profile()

    def _load_selected(self, row: int) -> None:
        """Populate editor fields for the selected persisted profile."""
        if row < 0:
            return
        profile_id = self.profile_list.item(row).data(Qt.ItemDataRole.UserRole)
        profile = next((item for item in self.profiles if item.id == profile_id), None)
        if profile is None:
            return
        self.current_profile = profile
        self.name.setText(profile.name)
        self.tags.setPlainText("\n".join(profile.tags))
        self.enabled.setChecked(profile.enabled)
        self.name.setReadOnly(False)
        self.tags.setReadOnly(False)
        self.examples.clear()
        self.examples.setEnabled(True)
        self.add_examples_button.setEnabled(True)
        self.remove_examples_button.setEnabled(True)
        self.delete_button.setEnabled(True)

    def _new_profile(self) -> None:
        """Reset the editor for a new user profile in the selected family."""
        self.current_profile = None
        self.profile_list.clearSelection()
        self.name.clear()
        self.tags.clear()
        self.enabled.setChecked(True)
        self.name.setReadOnly(False)
        self.tags.setReadOnly(False)
        self.examples.clear()
        self.examples.setEnabled(True)
        self.add_examples_button.setEnabled(True)
        self.remove_examples_button.setEnabled(True)
        self.delete_button.setEnabled(False)

    def _choose_examples(self) -> None:
        """Open a file picker and append selected learn-only examples."""
        values, _ = QFileDialog.getOpenFileNames(self, "예시 파일 선택")
        self.examples.add_paths(Path(value) for value in values)

    def _remove_examples(self) -> None:
        """Remove selected examples from the pending edit only."""
        for item in self.examples.selectedItems():
            self.examples.takeItem(self.examples.row(item))

    def _delete_selected(self) -> None:
        """Delete a user profile after confirmation without touching folders."""
        if self.current_profile is None:
            return
        answer = QMessageBox.question(
            self,
            "주제 삭제",
            "프로필만 삭제합니다. 기존 폴더와 파일은 그대로 둡니다. 계속할까요?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.store.delete(self.current_profile.id)
            self._refresh_profiles()

    def _prepare_save(self) -> None:
        """Validate fields and expose one edit request to the application."""
        try:
            tags = tuple(
                filter(
                    None,
                    (normalize_tag(value) for line in self.tags.toPlainText().splitlines() for value in line.split(",")),
                )
            )
            if self.current_profile is None:
                profile = self.store.new_profile(self.family.currentText(), self.name.text(), tags)
            else:
                profile = replace(
                    self.current_profile,
                    name=validate_topic_name(self.name.text()),
                    tags=tags,
                    enabled=self.enabled.isChecked(),
                )
            candidates = [item for item in self.profiles if item.id != profile.id]
            self.store._validate_profiles(candidates + [profile])
        except ValueError as exc:
            QMessageBox.warning(self, "프로필 저장 불가", str(exc))
            return
        self.request = ProfileEditRequest(profile, self.examples.paths())
        self.accept()
