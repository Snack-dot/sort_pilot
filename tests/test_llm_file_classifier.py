from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from sort_pilot.classifier_engine.topics import AnalysisRecord
from sort_pilot.llm_file_classifier import ClassificationCache, LlmFileClassifier
from sort_pilot.local_tagger import LocalTagger


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

    def test_extraction_failure_skips_llm_and_is_not_cached(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "unreadable.pdf"
            path.write_bytes(b"not a readable PDF")
            backend = FakeBackend()
            cache = ClassificationCache(root / "cache.json")
            classifier = LlmFileClassifier(backend, cache)
            record = AnalysisRecord(
                str(path),
                path.name,
                path.name,
                "문서",
                {},
                content_extraction_failed=True,
            )
            progress = []
            result = classifier.classify(
                [record], "학생", lambda done, total: progress.append((done, total))
            )
            self.assertEqual(result[0].folder, "기타/확인필요")
            self.assertEqual(backend.calls, 0)
            self.assertEqual(cache.load(), {})
            self.assertEqual(progress, [(1, 1)])

    def test_cached_files_are_partitioned_before_analysis(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cached_path = root / "cached.txt"
            new_path = root / "new.txt"
            cached_path.write_text("이미 분석됨", encoding="utf-8")
            new_path.write_text("새 파일", encoding="utf-8")
            cache = ClassificationCache(root / "cache.json")
            classifier = LlmFileClassifier(FakeBackend(), cache)
            key = classifier.cache_key(cached_path, "학생")
            cache.save({key: {"folder": "학업/필기"}})
            cached, uncached = classifier.partition_cached([cached_path, new_path], "학생")
            self.assertEqual([item.source for item in cached], [cached_path])
            self.assertEqual(cached[0].folder, "학업/필기")
            self.assertEqual(uncached, [new_path])

    def test_batch_retries_only_missing_files(self):
        installer = SimpleNamespace(ready=True, server_path=Path("llama-server"), model_path=Path("model"))
        tagger = LocalTagger(installer)
        tagger._free_port = lambda: 12345
        tagger._wait_until_ready = lambda process, port: None
        responses = iter([
            {"choices": [{"message": {"content": '{"0":{"area":"학업","topic":"","document_type":"강의자료"}}'}}]},
            {"choices": [{"message": {"content": '{"0":{"area":"학업","topic":"","document_type":"필기"}}'}}]},
        ])
        tagger._post_json = Mock(side_effect=responses)
        process = Mock()
        process.poll.return_value = 0
        progress = []
        requests = [
            {"id": "a", "user_type": "학생", "allowed_roots": ["학업"], "file_name": "a.pdf"},
            {"id": "b", "user_type": "학생", "allowed_roots": ["학업"], "file_name": "b.pdf"},
        ]
        with patch("sort_pilot.local_tagger.subprocess.Popen", return_value=process):
            results = tagger.classify_files(
                requests,
                lambda done, total: progress.append((done, total)),
            )
        self.assertEqual(results, {"a": "학업/강의자료", "b": "학업/필기"})
        self.assertEqual(tagger._post_json.call_count, 2)
        second_payload = tagger._post_json.call_args_list[1].args[1]
        self.assertIn('"file_name": "b.pdf"', second_payload["messages"][0]["content"])
        self.assertNotIn('"file_name": "a.pdf"', second_payload["messages"][0]["content"])
        self.assertNotIn('"id"', second_payload["messages"][0]["content"])
        self.assertEqual(progress, [(1, 2), (2, 2)])

    def test_role_markdown_guide_is_included_once_per_batch(self):
        allowed_roots = ["학업", "학교생활", "취업준비", "개인", "기타"]
        payload = LocalTagger._file_request_payload([
            {"id": "a", "user_type": "학생", "allowed_roots": allowed_roots},
            {"id": "b", "user_type": "학생", "allowed_roots": allowed_roots},
        ])
        prompt = payload["messages"][0]["content"]
        self.assertEqual(prompt.count("# 학생 파일 분류 지침"), 1)
        self.assertIn("명확한 근거가 있을 때만 `과제`", prompt)
        self.assertNotIn("reason", prompt)
        schema = payload["response_format"]["json_schema"]["schema"]
        self.assertEqual(schema["required"], ["0", "1"])
        self.assertEqual(set(schema["properties"]), {"0", "1"})
        self.assertEqual(
            schema["properties"]["0"]["required"],
            ["area", "topic", "document_type"],
        )
        self.assertFalse(schema["properties"]["0"]["additionalProperties"])
        document_types = schema["properties"]["0"]["properties"]["document_type"]["enum"]
        self.assertIn("강의자료", document_types)
        self.assertIn("필기", document_types)
        self.assertIn("확인필요", document_types)

    def test_fixed_position_response_builds_two_or_three_level_folders(self):
        items = [
            {
                "id": "a",
                "user_type": "학생",
                "allowed_roots": ["학업", "기타"],
                "content_terms": ["운영체제"],
            },
            {"id": "b", "user_type": "학생", "allowed_roots": ["학업", "기타"]},
            {"id": "c", "user_type": "학생", "allowed_roots": ["학업", "기타"]},
        ]
        content = (
            '{"0":{"area":"학업","topic":"운영체제","document_type":"강의자료"},'
            '"1":{"area":"학업","topic":"","document_type":"과제"},'
            '"2":{"area":"기타","topic":"","document_type":"확인필요"}}'
        )
        self.assertEqual(
            LocalTagger._parse_file_batch_response(content, items),
            {
                "a": "학업/운영체제/강의자료",
                "b": "학업/과제",
                "c": "기타/확인필요",
            },
        )

    def test_invalid_component_is_left_pending_for_retry(self):
        items = [
            {"id": "a", "user_type": "학생", "allowed_roots": ["학업", "기타"]},
            {"id": "b", "user_type": "학생", "allowed_roots": ["학업", "기타"]},
        ]
        content = (
            '{"0":{"area":"학업","topic":"운영체제/과제","document_type":"강의자료"},'
            '"1":{"area":"학업","topic":"","document_type":"필기"}}'
        )
        self.assertEqual(
            LocalTagger._parse_file_batch_response(content, items),
            {"b": "학업/필기"},
        )

    def test_guide_repairs_area_and_drops_ungrounded_topic(self):
        items = [
            {
                "id": "a",
                "user_type": "학생",
                "allowed_roots": ["학업", "학교생활", "취업준비", "개인", "기타"],
                "file_name": "notes.txt",
                "content_terms": ["운영체제", "요약", "필기"],
            }
        ]
        content = (
            '{"0":{"area":"기타","topic":"강의",'
            '"document_type":"필기"}}'
        )
        self.assertEqual(
            LocalTagger._parse_file_batch_response(content, items),
            {"a": "학업/필기"},
        )

    def test_topic_rejects_whole_file_name_and_extension(self):
        file_name = "대구 해외 유사지역 비교연구와 초기 후보군 선정.pdf"
        item = {"file_name": file_name, "content_terms": ["대구", "유사지역", "비교연구"]}
        self.assertEqual(LocalTagger._validated_topic(file_name, item), "")
        self.assertEqual(LocalTagger._validated_topic(Path(file_name).stem, item), "")
        self.assertEqual(LocalTagger._validated_topic("지역 비교연구.pdf", item), "")
        self.assertEqual(LocalTagger._validated_topic("비교연구", item), "비교연구")


if __name__ == "__main__":
    unittest.main()
