from __future__ import annotations

from pathlib import Path

from sort_pilot.app import AppController
from sort_pilot.curriculum import Semester, StudentProfile, StudentType
from sort_pilot.onboarding import StudentOnboardingDialog


class _Selection:
    def __init__(self, value: object) -> None:
        self.value = value

    def currentData(self) -> object:
        return self.value


class _Store:
    def __init__(self, value) -> None:
        self.value = value

    def load(self):
        return self.value


class _StartupStub:
    def __init__(self, student, topics, onboarding_result: bool = True) -> None:
        self.student_profile_store = _Store(student)
        self.profile_store = _Store(topics)
        self.downloads_folder = Path("Downloads")
        self._pending_organize = None
        self.onboarding_result = onboarding_result
        self.onboarding_calls = 0
        self.calibration_calls = 0

    def manage_student_profile(self) -> bool:
        self.onboarding_calls += 1
        return self.onboarding_result

    def _require_student_profile(self) -> bool:
        return AppController._require_student_profile(self)

    @staticmethod
    def _desktop_folder() -> Path:
        return Path("Desktop")

    def calibrate_topics(self) -> None:
        self.calibration_calls += 1


class _IdleAnalysis:
    busy = False


class _BlockedFlowStub:
    def __init__(self) -> None:
        self.analysis = _IdleAnalysis()
        self.require_calls = 0

    def _require_student_profile(self) -> bool:
        self.require_calls += 1
        return False


class _SandboxActionStub:
    def __init__(self) -> None:
        self.sandbox_folder = Path("Downloads") / "sandbox"
        self.calls: list[tuple[list[Path], str]] = []

    def _organize_existing_files(self, folders: list[Path], label: str) -> None:
        self.calls.append((folders, label))


def test_dialog_selection_builds_only_the_fixed_student_profile() -> None:
    form = type(
        "Form",
        (),
        {
            "student_type": _Selection("고등학생"),
            "grade": _Selection(3),
            "semester": _Selection("2학기"),
        },
    )()

    profile = StudentOnboardingDialog._selected_profile(form)

    assert profile == StudentProfile(StudentType.HIGH, 3, Semester.SECOND)
    assert profile.to_dict() == {
        "occupation": "학생",
        "student_type": "고등학생",
        "grade": 3,
        "semester": "2학기",
        "catalog_version": "KR_STUDENT_2026_MVP_V1",
    }


def test_first_run_cancellation_does_not_start_followup_calibration() -> None:
    controller = _StartupStub(None, [], onboarding_result=False)

    AppController._start_initial_workflow(controller)

    assert controller.onboarding_calls == 1
    assert controller.calibration_calls == 0
    assert controller._pending_organize is None


def test_completed_onboarding_does_not_start_the_older_topic_calibration() -> None:
    controller = _StartupStub(None, [], onboarding_result=True)

    AppController._start_initial_workflow(controller)

    assert controller.onboarding_calls == 1
    assert controller.calibration_calls == 0
    assert controller._pending_organize is None


def test_saved_onboarding_is_reused_without_prompting() -> None:
    student = StudentProfile(StudentType.MIDDLE, 1, Semester.FIRST)
    controller = _StartupStub(student, ["existing topic"])

    AppController._start_initial_workflow(controller)

    assert controller.onboarding_calls == 0
    assert controller.calibration_calls == 0


def test_every_classification_and_organization_entry_stops_without_saved_profile() -> None:
    controller = _BlockedFlowStub()

    AppController.calibrate_topics(controller)
    AppController.migrate_folders(controller)
    AppController._organize_existing_files(controller, [Path("Downloads")], "downloads")
    AppController._start_analysis(controller, [Path("file.pdf")], "organize", "analysis")
    AppController._complete_organization(controller, [])
    AppController._show_preview(controller, [])

    assert controller.require_calls == 6


def test_all_legacy_organization_actions_route_only_to_sandbox() -> None:
    controller = _SandboxActionStub()

    AppController.organize_desktop(controller)
    AppController.organize_downloads(controller)
    AppController.organize_all(controller)

    assert controller.calls == [
        ([controller.sandbox_folder], "Sandbox"),
        ([controller.sandbox_folder], "Sandbox"),
        ([controller.sandbox_folder], "Sandbox"),
    ]
