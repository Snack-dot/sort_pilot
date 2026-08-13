from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sort_pilot.classifier_engine.topics import (
    AnalysisRecord,
    TopicClassifier,
    TopicProfileStore,
)


class MvpTemplateTests(unittest.TestCase):
    def test_empty_store_gets_test_template_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = TopicProfileStore(Path(directory) / "profiles.json")
            first = store.install_test_template_if_empty()
            second = store.install_test_template_if_empty()

            self.assertEqual(len(first), 8)
            self.assertEqual([item.id for item in first], [item.id for item in second])

    def test_template_classifies_common_file_terms(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = TopicProfileStore(Path(directory) / "profiles.json")
            profiles = store.install_test_template_if_empty()
            records = [
                AnalysisRecord("과제.pdf", "과제.pdf", "과제.pdf", "문서", {"과제": 3}),
                AnalysisRecord("영수증.pdf", "영수증.pdf", "영수증.pdf", "문서", {"영수증": 3}),
                AnalysisRecord("스크린샷.png", "스크린샷.png", "스크린샷.png", "이미지", {"스크린샷": 3}),
            ]

            TopicClassifier().assign_existing(records, profiles)

            self.assertEqual([record.folder for record in records], [
                "문서/학업",
                "문서/금융",
                "이미지/스크린샷",
            ])


if __name__ == "__main__":
    unittest.main()
