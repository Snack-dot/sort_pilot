from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sort_pilot.classifier_engine.topics import AnalysisRecord
from sort_pilot.llm_file_classifier import ClassificationCache, LlmFileClassifier


class FakeBackend:
    def __init__(self) -> None:
        self.calls = 0

    def classify_files(self, requests, progress=None, cancelled=None, result_callback=None):
        self.calls += 1
        results = {}
        for completed, item in enumerate(requests, 1):
            results[item["id"]] = "학업/운영체제/과제"
            if result_callback:
                result_callback(item["id"], results[item["id"]])
            if progress:
                progress(completed, len(requests))
        return results


class LlmFileClassifierTests(unittest.TestCase):
    def test_same_content_and_policy_uses_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "과제.txt"
            path.write_text("프로세스 스케줄링 과제", encoding="utf-8")
            record = AnalysisRecord(str(path), path.name, path.name, "문서", {"과제": 3})
            backend = FakeBackend()
            classifier = LlmFileClassifier(backend, ClassificationCache(root / "cache.json"))
            first = classifier.classify([record], "학생")
            second = classifier.classify([record], "학생")
            self.assertEqual(first[0].folder, "학업/운영체제/과제")
            self.assertEqual(second[0].folder, first[0].folder)
            self.assertEqual(backend.calls, 1)
            self.assertEqual(second[0].reason, "")

    def test_content_or_user_type_change_reclassifies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "과제.txt"
            path.write_text("초안", encoding="utf-8")
            backend = FakeBackend()
            classifier = LlmFileClassifier(backend, ClassificationCache(root / "cache.json"))
            record = AnalysisRecord(str(path), path.name, path.name, "문서", {"과제": 1})
            classifier.classify([record], "학생")
            path.write_text("수정된 내용", encoding="utf-8")
            classifier.classify([record], "학생")
            teacher = classifier.classify([record], "선생님")
            self.assertEqual(teacher[0].folder, "기타/확인필요")
            self.assertEqual(backend.calls, 3)

    def test_unsafe_folder_is_rejected(self):
        self.assertRaises(ValueError, LlmFileClassifier.validate_folder, "../../Windows", "학생")

    def test_one_level_llm_result_is_scoped_to_role_default(self):
        self.assertEqual(LlmFileClassifier.validate_folder("과제", "학생"), "학업/과제")

    def test_two_and_three_level_paths_are_allowed(self):
        self.assertEqual(LlmFileClassifier.validate_folder("학업/강의자료", "학생"), "학업/강의자료")
        self.assertEqual(
            LlmFileClassifier.validate_folder("학업/운영체제/강의자료", "학생"),
            "학업/운영체제/강의자료",
        )

    def test_four_level_path_is_rejected(self):
        self.assertRaises(
            ValueError,
            LlmFileClassifier.validate_folder,
            "학업/컴퓨터공학/운영체제/강의자료",
            "학생",
        )

    def test_progress_includes_cached_and_new_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first_path = root / "first.txt"
            second_path = root / "second.txt"
            first_path.write_text("첫 파일", encoding="utf-8")
            second_path.write_text("둘째 파일", encoding="utf-8")
            backend = FakeBackend()
            classifier = LlmFileClassifier(backend, ClassificationCache(root / "cache.json"))
            first = AnalysisRecord(str(first_path), first_path.name, first_path.name, "문서", {"첫": 1})
            second = AnalysisRecord(str(second_path), second_path.name, second_path.name, "문서", {"둘": 1})
            classifier.classify([first], "학생")
            updates = []
            classifier.classify([first, second], "학생", lambda done, total: updates.append((done, total)))
            self.assertEqual(updates, [(1, 2), (2, 2)])

    def test_each_result_is_cached_immediately(self):
        class InterruptedBackend(FakeBackend):
            def classify_files(self, requests, progress=None, cancelled=None, result_callback=None):
                first = requests[0]
                if result_callback:
                    result_callback(first["id"], "학업/강의자료")
                raise RuntimeError("중단")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "lecture.pdf"
            path.write_bytes(b"lecture")
            cache = ClassificationCache(root / "cache.json")
            classifier = LlmFileClassifier(InterruptedBackend(), cache)
            record = AnalysisRecord(str(path), path.name, path.name, "문서", {"강의": 1})
            with self.assertRaises(RuntimeError):
                classifier.classify([record], "학생")
            self.assertTrue(cache.load())


if __name__ == "__main__":
    unittest.main()
