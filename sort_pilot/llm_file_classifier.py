from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path, PurePosixPath

from .classifier_engine.topics import AnalysisRecord, humanize_term
from .models import FileSuggestion

PROMPT_VERSION = 1
TEMPLATE_VERSION = 1
MODEL_ID = "gemma-3-1b-it"

ROLE_TEMPLATES = {
    "선생님": ("수업", "학생관리", "학교업무", "연구", "개인", "기타"),
    "학생": ("학업", "학교생활", "취업준비", "개인", "기타"),
    "직장인": ("업무", "회사행정", "재무", "계약", "교육", "개인", "기타"),
}


class ClassificationCache:
    """Atomic JSON cache keyed by content and every classification policy input."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, dict[str, str]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return dict(data.get("entries", {}))
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
            return {}

    def save(self, entries: dict[str, dict[str, str]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(dir=self.path.parent, prefix="classification-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump({"version": 1, "entries": entries}, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)


class LlmFileClassifier:
    """Use a local LLM for final role-aware classification and cache stable results."""

    def __init__(self, backend, cache: ClassificationCache) -> None:
        self.backend = backend
        self.cache = cache

    def classify(self, records: list[AnalysisRecord], user_type: str, progress=None, cancelled=None) -> list[FileSuggestion]:
        if user_type not in ROLE_TEMPLATES:
            raise ValueError("지원하지 않는 사용자 유형입니다.")
        entries = self.cache.load()
        suggestions: dict[int, FileSuggestion] = {}
        requests: list[dict] = []
        request_indexes: dict[str, tuple[int, str]] = {}
        completed = 0
        for index, record in enumerate(records):
            if cancelled and cancelled():
                raise RuntimeError("LLM 분류가 취소되었습니다.")
            key = self.cache_key(record.source, user_type)
            cached = entries.get(key)
            if cached:
                suggestions[index] = self._suggestion(record, cached["folder"], cached["reason"], "캐시")
                completed += 1
                if progress:
                    progress(completed, len(records))
                continue
            request_id = hashlib.sha256(f"{key}:{index}".encode()).hexdigest()[:16]
            requests.append(self._request(request_id, record, user_type))
            request_indexes[request_id] = (index, key)

        def backend_progress(done: int, _total: int) -> None:
            if progress:
                progress(completed + done, len(records))

        results = self.backend.classify_files(requests, backend_progress, cancelled) if requests else {}
        if cancelled and cancelled():
            raise RuntimeError("LLM 분류가 취소되었습니다.")
        changed = False
        for request_id, (index, key) in request_indexes.items():
            record = records[index]
            result = results.get(request_id)
            if result is None:
                suggestions[index] = self._suggestion(record, "기타/확인필요", "로컬 LLM 분류 실패", "LLM")
                continue
            folder, reason = result
            try:
                folder = self.validate_folder(folder, user_type)
            except ValueError as exc:
                fallback = f"{ROLE_TEMPLATES[user_type][-1]}/확인필요"
                suggestions[index] = self._suggestion(record, fallback, str(exc), "LLM")
                continue
            entries[key] = {"folder": folder, "reason": reason}
            changed = True
            suggestions[index] = self._suggestion(record, folder, reason, "LLM")
        if changed:
            self.cache.save(entries)
        return [suggestions[index] for index in range(len(records))]

    @staticmethod
    def cache_key(path: Path, user_type: str) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        policy = f"{user_type}|{MODEL_ID}|{PROMPT_VERSION}|{TEMPLATE_VERSION}"
        return hashlib.sha256((digest.hexdigest() + "|" + policy).encode()).hexdigest()

    @staticmethod
    def validate_folder(folder: str, user_type: str) -> str:
        normalized = folder.strip().replace("\\", "/")
        path = PurePosixPath(normalized)
        parts = path.parts
        if path.is_absolute() or not 1 <= len(parts) <= 4 or any(part in {"", ".", ".."} for part in parts):
            raise ValueError("LLM이 안전하지 않은 폴더 경로를 반환했습니다.")
        if len(parts) == 1:
            parts = (ROLE_TEMPLATES[user_type][0], parts[0])
        if parts[0] not in ROLE_TEMPLATES[user_type]:
            raise ValueError("LLM 결과가 사용자 유형 템플릿을 벗어났습니다.")
        return "/".join(parts)

    @staticmethod
    def _request(request_id: str, record: AnalysisRecord, user_type: str) -> dict:
        evidence = [word for word in (humanize_term(term) for term in record.terms) if word][:40]
        return {
            "id": request_id,
            "user_type": user_type,
            "allowed_roots": list(ROLE_TEMPLATES[user_type]),
            "file_name": record.file_name,
            "file_family": record.family,
            "content_terms": evidence,
        }

    @staticmethod
    def _suggestion(record: AnalysisRecord, folder: str, reason: str, source: str) -> FileSuggestion:
        return FileSuggestion(
            record.file_path,
            record.file_name,
            record.suggested_name,
            folder,
            f"[{source}] {reason}",
        )
