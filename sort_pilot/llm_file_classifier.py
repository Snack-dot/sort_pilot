from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path, PurePosixPath

from .classifier_engine.topics import AnalysisRecord, humanize_term
from .models import FileSuggestion

PROMPT_VERSION = 6
TEMPLATE_VERSION = 2
DEFAULT_MODEL_ID = "local-model"

ROLE_TEMPLATES = {
    "선생님": ("수업", "학생관리", "학교업무", "연구", "개인", "기타"),
    "학생": ("학업", "학교생활", "취업준비", "개인", "기타"),
    "직장인": ("업무", "회사행정", "재무", "계약", "교육", "개인", "기타"),
}


class ClassificationCache:
    """Atomic JSON cache keyed by content and every classification policy input."""

    def __init__(self, path: Path) -> None:
        """Store the private cache document at the given path."""
        self.path = path

    def load(self) -> dict[str, dict[str, str]]:
        """Return valid cached entries or an empty mapping when unavailable."""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return dict(data.get("entries", {}))
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
            return {}

    def save(self, entries: dict[str, dict[str, str]]) -> None:
        """Atomically replace the cache with the supplied entries."""
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
        """Bind one local inference backend and its persistent result cache."""
        self.backend = backend
        self.cache = cache
        self.model_id = str(getattr(backend, "model_id", DEFAULT_MODEL_ID))

    def classify(self, records: list[AnalysisRecord], user_type: str, progress=None, cancelled=None) -> list[FileSuggestion]:
        """Return ordered role-aware suggestions, reusing only successful cached results."""
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
                suggestions[index] = self._suggestion(record, cached["folder"])
                completed += 1
                if progress:
                    progress(completed, len(records))
                continue
            if record.content_extraction_failed:
                fallback = f"{ROLE_TEMPLATES[user_type][-1]}/확인필요"
                suggestions[index] = self._suggestion(record, fallback)
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

        def cache_result(request_id: str, raw_folder: str) -> bool:
            index, key = request_indexes[request_id]
            try:
                folder = self.validate_folder(raw_folder, user_type)
            except ValueError:
                return False
            entries[key] = {"folder": folder}
            self.cache.save(entries)
            suggestions[index] = self._suggestion(records[index], folder)
            return True

        results = self.backend.classify_files(
            requests, backend_progress, cancelled, cache_result
        ) if requests else {}
        if cancelled and cancelled():
            raise RuntimeError("LLM 분류가 취소되었습니다.")
        for request_id, (index, key) in request_indexes.items():
            if index in suggestions:
                continue
            record = records[index]
            result = results.get(request_id)
            if result is None:
                fallback = f"{ROLE_TEMPLATES[user_type][-1]}/확인필요"
                entries[key] = {"folder": fallback}
                self.cache.save(entries)
                suggestions[index] = self._suggestion(record, fallback)
                continue
            folder = result
            try:
                folder = self.validate_folder(folder, user_type)
            except ValueError:
                fallback = f"{ROLE_TEMPLATES[user_type][-1]}/확인필요"
                suggestions[index] = self._suggestion(record, fallback)
                continue
            entries[key] = {"folder": folder}
            self.cache.save(entries)
            suggestions[index] = self._suggestion(record, folder)
        return [suggestions[index] for index in range(len(records))]

    def partition_cached(
        self, paths: list[Path], user_type: str
    ) -> tuple[list[FileSuggestion], list[Path]]:
        """Split files by cache before expensive content extraction or LLM inference."""
        if user_type not in ROLE_TEMPLATES:
            raise ValueError("지원하지 않는 사용자 유형입니다.")
        entries = self.cache.load()
        cached: list[FileSuggestion] = []
        uncached: list[Path] = []
        for path in paths:
            entry = entries.get(self.cache_key(path, user_type))
            if entry and entry.get("folder"):
                cached.append(
                    FileSuggestion(str(path), path.name, path.name, str(entry["folder"]), "")
                )
            else:
                uncached.append(path)
        return cached, uncached

    def cache_key(self, path: Path, user_type: str) -> str:
        """Hash file content together with model and classification policy inputs."""
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        policy = f"{user_type}|{self.model_id}|{PROMPT_VERSION}|{TEMPLATE_VERSION}"
        return hashlib.sha256((digest.hexdigest() + "|" + policy).encode()).hexdigest()

    @staticmethod
    def validate_folder(folder: str, user_type: str) -> str:
        """Validate and normalize an untrusted role-relative folder path."""
        normalized = folder.strip().replace("\\", "/")
        path = PurePosixPath(normalized)
        parts = path.parts
        if path.is_absolute() or not 1 <= len(parts) <= 3 or any(part in {"", ".", ".."} for part in parts):
            raise ValueError("LLM이 안전하지 않은 폴더 경로를 반환했습니다.")
        if len(parts) == 1:
            parts = (ROLE_TEMPLATES[user_type][0], parts[0])
        if parts[0] not in ROLE_TEMPLATES[user_type]:
            raise ValueError("LLM 결과가 사용자 유형 템플릿을 벗어났습니다.")
        return "/".join(parts)

    @staticmethod
    def _request(request_id: str, record: AnalysisRecord, user_type: str) -> dict:
        """Build bounded file metadata for one local-model classification item."""
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
    def _suggestion(record: AnalysisRecord, folder: str) -> FileSuggestion:
        """Convert one analysis record and approved folder into a UI suggestion."""
        return FileSuggestion(
            record.file_path,
            record.file_name,
            record.suggested_name,
            folder,
            "",
        )
