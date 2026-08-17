from __future__ import annotations

import math
import mimetypes
import re
import threading
import time
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree

from stop_words import get_stop_words

from .types import Feature, FeatureVector, path_id

IN_PROGRESS = {".crdownload", ".part", ".tmp", ".download"}
KO_PARTICLES = ("에서는", "으로", "에게", "에서", "부터", "까지", "처럼", "보다", "은", "는", "이", "가", "을", "를", "에", "의", "도", "와", "과")
STOP = frozenset(get_stop_words("en")) | frozenset(get_stop_words("ko")) | {"그리고", "합니다", "있는", "없는"}
MAX_BODY_TERMS = 160
MAX_COLLOCATIONS = 40
MIN_COLLOCATION_COUNT = 2
MIN_COLLOCATION_PMI = 2.0
COLLOCATION_PREFIXES = {2: "bi:", 3: "tri:"}
SEMANTIC_FEATURE_SOURCES = frozenset({"body", "ocr", "obj", "pair"})
CONTENT_ANALYSIS_SUFFIXES = frozenset({
    ".txt", ".md", ".csv", ".rtf", ".pdf", ".docx", ".odt", ".pptx", ".xlsx",
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".heic",
})
_KIWI = None
_OCR_LOCAL = threading.local()


def supports_content_analysis(path: Path) -> bool:
    """Return whether the bundled extractors can derive semantic content evidence."""
    return path.suffix.casefold() in CONTENT_ANALYSIS_SUFFIXES


def normalize_filename(path: Path) -> list[str]:
    """Normalize timestamp, copy, case, and separator patterns into tokens."""
    stem = re.sub(r"_?\d{8}_\d{6}", "", path.stem)
    stem = re.sub(r"\s*\(\d+\)$", "", stem)
    if stem.lower().rstrip("_") == "kakaotalk":
        return ["kakaotalk"]
    stem = re.sub(r"([a-z])([A-Z])", r"\1 \2", stem)
    return tokenize(re.sub(r"[_\-.]+", " ", stem))


def tokenize(text: str) -> list[str]:
    """Tokenize Korean and Latin text using Kiwi with a regex fallback."""
    global _KIWI
    try:
        if _KIWI is None:
            from kiwipiepy import Kiwi
            _KIWI = Kiwi()
        result = []
        for token in _KIWI.tokenize(text):
            if token.tag.startswith(("NN", "VV", "VA")) or token.tag in {"SL"}:
                form = token.form.lower()
                if form not in STOP and (len(form) >= 2 or re.search(r"[가-힣]", form)):
                    result.append(form)
        return result
    except ImportError:
        pass
    raw = re.findall(r"[가-힣]+|[A-Za-z][A-Za-z0-9]*", text.lower())
    result = []
    for token in raw:
        if re.search(r"[가-힣]", token):
            for particle in KO_PARTICLES:
                if token.endswith(particle) and len(token) > len(particle) + 1:
                    token = token[:-len(particle)]; break
        if token not in STOP and (len(token) >= 2 or re.search(r"[가-힣]", token)):
            result.append(token)
    return result


def collocations(tokens: list[str], n: int) -> Counter[str]:
    """Extract adjacent n-grams whose joint frequency exceeds chance (pointwise mutual information)."""
    if len(tokens) < n:
        return Counter()
    unigram_counts = Counter(tokens)
    total = len(tokens)
    ngram_counts = Counter(tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1))
    total_ngrams = sum(ngram_counts.values())
    kept: Counter[str] = Counter()
    for ngram, count in ngram_counts.items():
        if count < MIN_COLLOCATION_COUNT:
            continue
        joint = count / total_ngrams
        independent = 1.0
        for word in ngram:
            independent *= unigram_counts[word] / total
        pmi = math.log(joint / independent) if independent > 0 else 0.0
        if pmi >= MIN_COLLOCATION_PMI:
            kept[COLLOCATION_PREFIXES[n] + " ".join(ngram)] = count
    return kept


def _read_text(path: Path, limit: int) -> str:
    """Read bounded plain text using common Korean and Unicode encodings."""
    for encoding in ("utf-8-sig", "cp949", "utf-16"):
        try: return path.read_text(encoding=encoding)[:limit]
        except (UnicodeError, OSError): continue
    return ""


def _docx(path: Path, limit: int) -> str:
    """Extract bounded text directly from a DOCX document XML payload."""
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))
    return " ".join(node.text or "" for node in root.iter())[:limit]


def _odt(path: Path, limit: int) -> str:
    """Extract bounded paragraph and table text from an ODT content payload."""
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("content.xml"))
    return " ".join(node.text or "" for node in root.iter())[:limit]


def _archive(path: Path) -> str:
    """Extract representative top-level names from a ZIP archive."""
    if path.suffix.lower() != ".zip": return ""
    with zipfile.ZipFile(path) as archive:
        return " ".join(Path(name).parts[0] for name in archive.namelist()[:500])


def _pdf(path: Path, max_chars: int, max_pages: int = 5) -> str:
    """Extract bounded text from the first pages of a PDF."""
    import pymupdf
    with pymupdf.open(path) as document:
        return " ".join(page.get_text() for page in list(document)[:max_pages])[:max_chars]


def _pptx(path: Path, limit: int) -> str:
    """Extract bounded text from PowerPoint slide text frames."""
    from pptx import Presentation
    deck = Presentation(path)
    return " ".join(shape.text for slide in deck.slides for shape in slide.shapes if hasattr(shape, "text_frame"))[:limit]


def _xlsx(path: Path, limit: int) -> str:
    """Extract bounded sheet names and cell values from a workbook."""
    from openpyxl import load_workbook
    book = load_workbook(path, read_only=True, data_only=True)
    values = []
    try:
        for sheet in book.worksheets:
            values.append(sheet.title)
            for row in sheet.iter_rows(max_row=50, max_col=20, values_only=True):
                values.extend(str(value) for value in row if value is not None)
                if sum(map(len, values)) >= limit: break
    finally: book.close()
    return " ".join(values)[:limit]


def _image_features(path: Path) -> tuple[str, list[Feature]]:
    """Route an image and derive camera, aspect, and color metadata."""
    from PIL import Image, ImageStat
    with Image.open(path) as image:
        exif = image.getexif(); width, height = image.size
        has_camera = bool(exif.get(271) or exif.get(272))
        known = {(1920, 1080), (2560, 1440), (1366, 768), (3840, 2160)}
        route = "photo" if has_camera else "screenshot" if image.size in known or path.suffix.lower() == ".png" else "ambiguous"
        features = [Feature(f"image:{route}", "meta"), Feature("aspect:" + ("portrait" if height > width else "square" if abs(width-height)/max(width,height)<.1 else "landscape"), "meta")]
        if has_camera: features.append(Feature("exif:camera_present", "meta"))
        sample = image.convert("RGB"); sample.thumbnail((80, 80)); mean = ImageStat.Stat(sample).mean
        features.append(Feature("color:warm" if mean[0] > mean[2] * 1.08 else "color:cool", "meta"))
        return route, features


def _ocr_engine():
    """Return one lazily initialized RapidOCR engine per worker thread."""
    from rapidocr import RapidOCR

    engine = getattr(_OCR_LOCAL, "engine", None)
    if engine is None:
        engine = RapidOCR()
        _OCR_LOCAL.engine = engine
    return engine


def _ocr_evidence(path: Path) -> tuple[str, list[Feature]]:
    """Extract bounded OCR natural text and at most forty lexical features."""
    result = _ocr_engine()(str(path))
    texts = getattr(result, "txts", None) or []
    natural_text = " ".join(str(value) for value in texts)[:20_000]
    _OCR_LOCAL.last_text = natural_text
    return natural_text, [Feature(token, "ocr") for token in tokenize(natural_text)[:40]]


def _ocr(path: Path) -> list[Feature]:
    """Return OCR lexical features for the legacy extractor interface."""
    return _ocr_evidence(path)[1]


def extract(path: Path, max_content_mb=200, max_chars=20_000) -> FeatureVector:
    """Build a bounded local feature vector from filename, content, and media."""
    started = time.perf_counter(); stat = path.stat(); features = []
    features.extend(Feature(t, "filename") for t in normalize_filename(path))
    features.append(Feature(path.suffix.lower().lstrip(".") or "no_ext", "ext"))
    if re.match(r"(?i)^KakaoTalk_\d{8}_\d{6}", path.name): features.append(Feature("kakao_export", "meta"))
    partial = stat.st_size > max_content_mb * 1024 * 1024
    text = ""; suffix = path.suffix.lower()
    if not partial:
        try:
            if suffix in {".txt", ".md", ".csv", ".rtf"}: text = _read_text(path, max_chars)
            elif suffix == ".pdf": text = _pdf(path, max_chars)
            elif suffix == ".docx": text = _docx(path, max_chars)
            elif suffix == ".odt": text = _odt(path, max_chars)
            elif suffix == ".pptx": text = _pptx(path, max_chars)
            elif suffix == ".xlsx": text = _xlsx(path, max_chars)
            elif suffix == ".zip": text = _archive(path)
        except Exception:
            partial = True
    body_tokens = tokenize(text)
    for token, count in Counter(body_tokens).most_common(MAX_BODY_TERMS):
        features.append(Feature(token, "body", float(count)))
    for n in (2, 3):
        for ngram, count in collocations(body_tokens, n).most_common(MAX_COLLOCATIONS):
            features.append(Feature(ngram, "body", float(count)))
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    route = "text" if text else "metadata"
    if mime.startswith("image/"):
        try:
            route, image_features = _image_features(path); features.extend(image_features)
            if route in {"screenshot", "ambiguous"}:
                _OCR_LOCAL.last_text = ""
                features.extend(_ocr(path))
                ocr_text = getattr(_OCR_LOCAL, "last_text", "")
                if not text:
                    text = ocr_text[:max_chars]
            model_path = Path(__file__).parents[2] / "data" / "models" / "yolov8n.onnx"
            if model_path.exists():
                from .vision import infer
                vision_features, _ = infer(path, model_path); features.extend(vision_features)
        except Exception:
            partial = True; route = "image"
    return FeatureVector(
        path_id(path),
        str(path),
        stat.st_size,
        features,
        partial,
        route,
        {"total": (time.perf_counter()-started)*1000},
        natural_text=text,
    )


def is_processable(path: Path, exclusions=()) -> bool:
    """Reject directories, partial downloads, office locks, and excluded paths."""
    import fnmatch
    return path.is_file() and path.suffix.lower() not in IN_PROGRESS and not path.name.startswith("~$") and not any(fnmatch.fnmatch(str(path), p) for p in exclusions)


def is_stable(path: Path, interval=2.0) -> bool:
    """Check that file size and modification time remain unchanged."""
    try:
        first = path.stat(); time.sleep(interval); second = path.stat()
        if (first.st_size, first.st_mtime_ns) != (second.st_size, second.st_mtime_ns): return False
        with path.open("rb"): pass
        return True
    except (OSError, PermissionError): return False
