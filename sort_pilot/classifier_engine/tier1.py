from __future__ import annotations

import json
import re
from pathlib import Path

from .types import Decision, Feature

DEFAULT_RULES = [
    {"id": "installers", "ext": ["exe", "msi", "dmg", "pkg", "appimage"], "category": "Installers"},
    {"id": "kakao-export", "regex": r"^KakaoTalk_\d{8}_\d{6}", "mark": ["kakao_export", "needs_content"]},
    {"id": "coursework", "regex": r"(과제|report|assignment|hw\d|lab\d)", "category": "School"},
    {"id": "finance", "regex": r"(거래내역|명세서|statement|invoice|세금계산서|영수증)", "category": "Finance"},
]


def load_rules(path: Path | None) -> list[dict]:
    """Load ordered Tier 1 rules or return built-in safe defaults."""
    if path and path.exists(): return json.loads(path.read_text(encoding="utf-8")).get("rules", DEFAULT_RULES)
    return DEFAULT_RULES


def evaluate(path: Path, rules: list[dict]) -> tuple[Decision | None, list[Feature]]:
    """Evaluate ordered rules and return a decision plus feature marks."""
    marks = []
    for rule in rules:
        if "ext" in rule and path.suffix.lower().lstrip(".") not in rule["ext"]: continue
        if "regex" in rule and not re.search(rule["regex"], path.name, re.IGNORECASE): continue
        if rule.get("exclude"): return Decision(None, 0, 0, 0, "exclude", "t1"), marks
        if "mark" in rule: marks.extend(Feature(x, "meta") for x in rule["mark"]); continue
        if category := rule.get("category"): return Decision(category, 1, 1, 1, "auto", "t1", [{"rule": rule["id"]}]), marks
    return None, marks
