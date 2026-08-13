from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from sort_pilot.classifier import LocalPipelineAnalyzer, RuleBasedAnalyzer
from sort_pilot.classifier_engine.topics import TopicClassifier, TopicProfileStore


class ClassifierContractTests(unittest.TestCase):
    def _analyzer(self) -> LocalPipelineAnalyzer:
        analyzer = LocalPipelineAnalyzer.__new__(LocalPipelineAnalyzer)
        analyzer.fallback = RuleBasedAnalyzer()
        analyzer.pipeline = None
        analyzer.topic_classifier = TopicClassifier()
        analyzer.profile_store = SimpleNamespace(load=TopicProfileStore._default_profiles)
        return analyzer

    def test_single_json_object_contract_uses_nested_folder(self) -> None:
        result = self._analyzer().analyze_json(
            Path("C:/Users/user/Downloads/운영체제과제.pdf")
        )
        self.assertEqual(
            result,
            {
                "filepath": "C:/Users/user/Downloads/운영체제과제.pdf",
                "folder": "문서/학교",
            },
        )

    def test_many_json_object_contract_preserves_order(self) -> None:
        result = self._analyzer().analyze_many_json(
            [Path("C:/Downloads/assignment.pdf"), Path("C:/Downloads/second.pdf")]
        )
        self.assertEqual(
            result,
            {
                "results": [
                    {"filepath": "C:/Downloads/assignment.pdf", "folder": "문서/학교"},
                    {"filepath": "C:/Downloads/second.pdf", "folder": "문서/미분류"},
                ]
            },
        )


if __name__ == "__main__":
    unittest.main()
