from __future__ import annotations

import threading
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .calibration import CalibrationCluster, CalibrationDraft
from .classifier_engine.hierarchy import TYPE_FAMILIES
from .classifier_engine.topics import TopicProfile, normalize_tag, validate_topic_name
from .local_tagger import GEMMA_TERMS_URL, MODEL, InstallCancelled, LocalModelInstaller


class CalibrationFileList(QListWidget):
    """Cross-card move list retaining record indexes as item data."""

    def __init__(self, parent=None) -> None:
        """Enable selection and move-style drag/drop between topic cards."""
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)


class ClusterCard(QFrame):
    """One editable topic and its draggable calibration examples."""

    def __init__(self, cluster: CalibrationCluster, records, *, excluded: bool = False) -> None:
        """Render editable metadata and the cluster's current sample files."""
        super().__init__()
        self.cluster_id = cluster.id
        self.existing_profile_id = cluster.existing_profile_id
        self.excluded = excluded
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        self.merge = QCheckBox("병합 선택")
        self.name = QLineEdit(cluster.topic)
        self.name.setPlaceholderText("주제 이름")
        if excluded:
            self.name.setText("학습에서 제외")
            self.name.setReadOnly(True)
            self.merge.setEnabled(False)
        header.addWidget(self.merge)
        header.addWidget(self.name, 1)
        layout.addLayout(header)
        self.tags = QLineEdit(", ".join(cluster.tags))
        self.tags.setPlaceholderText("태그: 쉼표로 구분")
        self.tags.setReadOnly(excluded)
        layout.addWidget(self.tags)
        self.files = CalibrationFileList()
        self.files.setMinimumHeight(110)
        for index in cluster.record_indexes:
            item = QListWidgetItem(records[index].file_name)
            item.setData(Qt.ItemDataRole.UserRole, index)
            item.setToolTip(records[index].file_path)
            self.files.addItem(item)
        layout.addWidget(self.files)

    def indexes(self) -> list[int]:
        """Return record indexes in their current visual order."""
        return [
            int(self.files.item(index).data(Qt.ItemDataRole.UserRole))
            for index in range(self.files.count())
        ]

    def tag_values(self) -> list[str]:
        """Return normalized, deduplicated tags from the line editor."""
        return list(
            dict.fromkeys(
                tag
                for tag in (normalize_tag(value) for value in self.tags.text().split(","))
                if tag
            )
        )


class FamilyCalibrationPage(QWidget):
    """Manage topic cards for one immutable file family."""

    def __init__(self, family: str, draft: CalibrationDraft, existing: list[TopicProfile]) -> None:
        """Build cards for proposed and existing topics in one family."""
        super().__init__()
        self.family = family
        self.draft = draft
        self.cards: list[ClusterCard] = []
        outer = QVBoxLayout(self)
        actions = QHBoxLayout()
        new_button = QPushButton("새 주제")
        new_button.clicked.connect(self.new_group)
        split_button = QPushButton("선택 파일 분리")
        split_button.clicked.connect(self.split_selected)
        merge_button = QPushButton("선택 주제 병합")
        merge_button.clicked.connect(self.merge_selected)
        actions.addWidget(new_button)
        actions.addWidget(split_button)
        actions.addWidget(merge_button)
        actions.addStretch(1)
        outer.addLayout(actions)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self.card_layout = QVBoxLayout(container)
        self.card_layout.addStretch(1)
        scroll.setWidget(container)
        outer.addWidget(scroll)

        used_profile_ids: set[str] = set()
        for cluster in draft.clusters:
            if cluster.family != family:
                continue
            match = next(
                (
                    profile
                    for profile in existing
                    if profile.family == family and profile.name.casefold() == cluster.topic.casefold()
                ),
                None,
            )
            if match:
                cluster.existing_profile_id = match.id
                used_profile_ids.add(match.id)
            self._add_card(cluster)
        for profile in existing:
            if profile.family == family and profile.id not in used_profile_ids:
                self._add_card(
                    CalibrationCluster(
                        id=f"existing:{profile.id}",
                        family=family,
                        record_indexes=[],
                        topic=profile.name,
                        tags=list(profile.tags),
                        existing_profile_id=profile.id,
                    )
                )
        self.excluded = self._add_card(
            CalibrationCluster("excluded", family, [], "", [], excluded=True),
            excluded=True,
        )

    def _add_card(self, cluster: CalibrationCluster, *, excluded: bool = False) -> ClusterCard:
        """Append one card before the page's stretch spacer."""
        card = ClusterCard(cluster, self.draft.records, excluded=excluded)
        self.cards.append(card)
        self.card_layout.insertWidget(self.card_layout.count() - 1, card)
        return card

    def new_group(self) -> ClusterCard:
        """Create and return one empty user-named topic card."""
        return self._add_card(
            CalibrationCluster(f"new:{len(self.cards)}", self.family, [], "", [])
        )

    def split_selected(self) -> None:
        """Move selected sample files into a newly created topic card."""
        selected: list[tuple[ClusterCard, QListWidgetItem]] = []
        for card in self.cards:
            if card is self.excluded:
                continue
            selected.extend((card, item) for item in card.files.selectedItems())
        if not selected:
            return
        target = self.new_group()
        for source, item in selected:
            source.files.takeItem(source.files.row(item))
            target.files.addItem(item)

    def merge_selected(self) -> None:
        """Combine checked topic cards into the first checked card."""
        selected = [card for card in self.cards if card is not self.excluded and card.merge.isChecked()]
        if len(selected) < 2:
            return
        target = selected[0]
        merged_tags = target.tag_values()
        for card in selected[1:]:
            merged_tags.extend(card.tag_values())
            while card.files.count():
                target.files.addItem(card.files.takeItem(0))
            self.cards.remove(card)
            card.deleteLater()
        target.tags.setText(", ".join(dict.fromkeys(merged_tags)))
        target.merge.setChecked(False)

    def export(self) -> list[CalibrationCluster]:
        """Validate and serialize all nonempty cards into draft clusters."""
        clusters: list[CalibrationCluster] = []
        for card in self.cards:
            indexes = card.indexes()
            if card is self.excluded:
                if indexes:
                    clusters.append(
                        CalibrationCluster(card.cluster_id, self.family, indexes, "Excluded", [], True)
                    )
                continue
            if not indexes:
                continue
            clusters.append(
                CalibrationCluster(
                    card.cluster_id,
                    self.family,
                    indexes,
                    validate_topic_name(card.name.text()),
                    card.tag_values(),
                    existing_profile_id=card.existing_profile_id,
                )
            )
        return clusters


class CalibrationDialog(QDialog):
    """Review all sampled files before creating or updating topic profiles."""

    def __init__(self, draft: CalibrationDraft, existing: list[TopicProfile], parent=None) -> None:
        """Build one family tab for every file type present in the sample."""
        super().__init__(parent)
        self.draft = draft
        self.setWindowTitle("Sort Pilot - 주제 보정")
        self.resize(980, 700)
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "표본 분석 결과를 확인하세요. 파일을 주제 사이로 끌어 옮기고 이름과 태그를 수정할 수 있습니다. "
                "이 단계에서는 파일을 이동하지 않습니다."
            )
        )
        self.tabs = QTabWidget()
        self.pages: list[FamilyCalibrationPage] = []
        families = [family for family in TYPE_FAMILIES if any(r.family == family for r in draft.records)]
        for family in families:
            page = FamilyCalibrationPage(family, draft, existing)
            self.pages.append(page)
            self.tabs.addTab(page, family)
        layout.addWidget(self.tabs)
        buttons = QDialogButtonBox()
        save = buttons.addButton("확인하고 학습", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton("취소", QDialogButtonBox.ButtonRole.RejectRole)
        save.clicked.connect(self._confirm)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _confirm(self) -> None:
        """Require complete assignment and unique safe names before acceptance."""
        try:
            clusters = [cluster for page in self.pages for cluster in page.export()]
            assigned = {index for cluster in clusters for index in cluster.record_indexes}
            if assigned != set(range(len(self.draft.records))):
                raise ValueError("모든 표본을 주제에 넣거나 학습에서 제외해야 합니다.")
            names: set[tuple[str, str]] = set()
            for cluster in clusters:
                if cluster.excluded:
                    continue
                key = cluster.family, cluster.topic.casefold()
                if key in names:
                    raise ValueError(f"같은 파일 유형에 중복된 주제 이름이 있습니다: {cluster.topic}")
                names.add(key)
            self.draft.clusters = clusters
        except ValueError as exc:
            QMessageBox.warning(self, "주제 보정", str(exc))
            return
        self.accept()


def ensure_local_model(parent, installer: LocalModelInstaller) -> bool:
    """Ask for Gemma consent and install with a cancellable progress dialog."""
    if installer.ready:
        return True
    message = QMessageBox(parent)
    message.setWindowTitle("로컬 AI 모델 설치")
    message.setTextFormat(Qt.TextFormat.RichText)
    message.setText(
        f"주제 이름과 태그 제안을 위해 Google Gemma 3 1B 모델({MODEL.size / 1_000_000:.0f}MB)을 "
        f"이 PC에만 설치합니다.<br><a href='{GEMMA_TERMS_URL}'>Gemma 사용 조건</a>에 동의하시겠습니까?"
    )
    message.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    if message.exec() != QMessageBox.StandardButton.Yes:
        return False
    installer.record_consent()
    cancelled = threading.Event()
    progress = QProgressDialog("로컬 AI 모델 준비 중", "취소", 0, MODEL.size + 20_000_000, parent)
    progress.setWindowTitle("Sort Pilot")
    progress.setMinimumDuration(0)

    def update(name: str, current: int, total: int) -> None:
        offset = 0 if name == MODEL.name else MODEL.size
        progress.setMaximum(MODEL.size + 20_000_000)
        progress.setValue(offset + min(current, total))
        progress.setLabelText(f"{name}: {current / 1_000_000:.0f}/{total / 1_000_000:.0f}MB")
        QApplication.processEvents()
        if progress.wasCanceled():
            cancelled.set()

    try:
        installer.install(update, cancelled)
        progress.close()
        return True
    except InstallCancelled:
        progress.close()
        return False
    except Exception as exc:
        progress.close()
        QMessageBox.warning(parent, "로컬 AI 모델", f"모델 설치에 실패했습니다. TF-IDF 제안을 사용합니다.\n{exc}")
        return False
