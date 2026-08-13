from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from sort_pilot.classifier import LocalPipelineAnalyzer


class ClassifierContractTests(unittest.TestCase):
    def _analyzer(self) -> LocalPipelineAnalyzer:
        analyzer = LocalPipelineAnalyzer.__new__(LocalPipelineAnalyzer)
        analyzer.fallback = SimpleNamespace(
            _clean_name=lambda path: path.name,
            analyze=lambda path: SimpleNamespace(
                file_path=str(path.resolve()),
                file_name=path.name,
                suggested_name=path.name,
                folder="기타",
                reason="fallback",
            ),
        )
        analyzer.pipeline = SimpleNamespace(
            safe_classify=lambda path: (
                None,
                SimpleNamespace(category="학교", tier="t1", action="auto", margin=1.0),
                1,
            )
        )
        return analyzer

    def test_single_json_object_contract(self) -> None:
        result = self._analyzer().analyze_json(
            Path("C:/Users/user/Downloads/운영체제과제.pdf")
        )
        self.assertEqual(
            result,
            {
                "filepath": "C:/Users/user/Downloads/운영체제과제.pdf",
                "folder": "학교",
            },
        )

    def test_many_json_object_contract_preserves_order(self) -> None:
        result = self._analyzer().analyze_many_json(
            [Path("C:/Downloads/첫번째.pdf"), Path("C:/Downloads/second.pdf")]
        )
        self.assertEqual(
            result,
            {
                "results": [
                    {"filepath": "C:/Downloads/첫번째.pdf", "folder": "학교"},
                    {"filepath": "C:/Downloads/second.pdf", "folder": "학교"},
                ]
            },
        )


if __name__ == "__main__":
    unittest.main()
