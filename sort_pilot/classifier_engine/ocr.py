from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import urllib.request
from dataclasses import dataclass
from importlib.resources import as_file, files
from pathlib import Path

from sort_pilot.sandbox import default_sandbox_root, require_in_sandbox


OCR_ASSET_VERSION = "rapidocr-3.5.0-korean-ppocrv5-v1"
OCR_MODEL_DIRECTORY = Path(".sort_pilot_state") / "models" / "rapidocr"
RECOGNIZER_URL = (
    "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.5.0/"
    "onnx/PP-OCRv5/rec/korean_PP-OCRv5_rec_mobile_infer.onnx"
)
RECOGNIZER_SHA256 = "cd6e2ea50f6943ca7271eb8c56a877a5a90720b7047fe9c41a2e541a25773c9b"
DETECTOR_BUNDLED_NAME = "ch_PP-OCRv4_det_infer.onnx"
CLASSIFIER_BUNDLED_NAME = "ch_ppocr_mobile_v2.0_cls_infer.onnx"
DETECTOR_SHA256 = "d2a7720d45a54257208b1e13e36a8479894cb74155a5efe29462512d42f49da9"
CLASSIFIER_SHA256 = "e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c"


@dataclass(frozen=True, slots=True)
class KoreanOCRAssets:
    """Verified local-only RapidOCR model paths inside the configured sandbox."""

    detector: Path
    classifier: Path
    recognizer: Path
    dictionary: Path

    @classmethod
    def load(cls, sandbox_root: Path | None = None) -> "KoreanOCRAssets":
        """Load and verify installed assets without attempting any network access."""
        sandbox = (sandbox_root or default_sandbox_root()).resolve()
        root = require_in_sandbox(
            sandbox / OCR_MODEL_DIRECTORY,
            sandbox,
            label="OCR model directory",
        )
        manifest_path = require_in_sandbox(root / "manifest.json", sandbox, label="OCR manifest")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                "Korean OCR assets are not installed. Run eval/install_korean_ocr.py once."
            ) from exc
        if not isinstance(manifest, dict) or set(manifest) != {"version", "files", "source"}:
            raise RuntimeError("Korean OCR asset manifest is invalid.")
        if manifest["version"] != OCR_ASSET_VERSION or manifest["source"] != RECOGNIZER_URL:
            raise RuntimeError("Korean OCR asset version or source does not match the application.")
        file_specs = manifest["files"]
        expected_names = {
            "detector": "detector.onnx",
            "classifier": "classifier.onnx",
            "recognizer": "korean_PP-OCRv5_mobile_rec.onnx",
            "dictionary": "korean_PP-OCRv5_mobile_rec_dict.txt",
        }
        if not isinstance(file_specs, dict) or set(file_specs) != set(expected_names):
            raise RuntimeError("Korean OCR asset file list is invalid.")
        paths: dict[str, Path] = {}
        for key, expected_name in expected_names.items():
            spec = file_specs[key]
            if not isinstance(spec, dict) or set(spec) != {"name", "sha256"}:
                raise RuntimeError("Korean OCR asset entry is invalid.")
            if spec["name"] != expected_name or not _valid_sha256(spec["sha256"]):
                raise RuntimeError("Korean OCR asset name or hash is invalid.")
            path = require_in_sandbox(root / expected_name, sandbox, label=f"OCR {key}")
            if not path.is_file() or _sha256(path) != spec["sha256"]:
                raise RuntimeError(f"Korean OCR {key} is missing or failed SHA-256 verification.")
            paths[key] = path
        if file_specs["detector"]["sha256"] != DETECTOR_SHA256:
            raise RuntimeError("Unexpected RapidOCR detector artifact.")
        if file_specs["classifier"]["sha256"] != CLASSIFIER_SHA256:
            raise RuntimeError("Unexpected RapidOCR orientation classifier artifact.")
        if file_specs["recognizer"]["sha256"] != RECOGNIZER_SHA256:
            raise RuntimeError("Unexpected Korean PP-OCRv5 recognizer artifact.")
        _verify_dictionary_matches_model(paths["recognizer"], paths["dictionary"])
        return cls(**paths)

    def rapidocr_params(self) -> dict[str, object]:
        """Return explicit local paths so RapidOCR cannot select or download defaults."""
        from rapidocr import LangRec, OCRVersion

        return {
            "Global.log_level": "warning",
            "Det.model_path": str(self.detector),
            "Cls.model_path": str(self.classifier),
            "Rec.model_path": str(self.recognizer),
            "Rec.rec_keys_path": str(self.dictionary),
            "Rec.lang_type": LangRec.KOREAN,
            "Rec.ocr_version": OCRVersion.PPOCRV5,
            "Rec.rec_img_shape": [3, 48, 320],
        }


def install_korean_ocr_assets(sandbox_root: Path | None = None) -> KoreanOCRAssets:
    """Install verified OCR assets once; this is the only network-capable OCR function."""
    sandbox = (sandbox_root or default_sandbox_root()).resolve()
    root = require_in_sandbox(
        sandbox / OCR_MODEL_DIRECTORY,
        sandbox,
        label="OCR model directory",
    )
    try:
        return KoreanOCRAssets.load(sandbox)
    except RuntimeError:
        pass
    root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix="ocr-install-", dir=root))
    try:
        detector = temporary / "detector.onnx"
        classifier = temporary / "classifier.onnx"
        recognizer = temporary / "korean_PP-OCRv5_mobile_rec.onnx"
        dictionary = temporary / "korean_PP-OCRv5_mobile_rec_dict.txt"
        _copy_bundled_model(DETECTOR_BUNDLED_NAME, detector, DETECTOR_SHA256)
        _copy_bundled_model(CLASSIFIER_BUNDLED_NAME, classifier, CLASSIFIER_SHA256)
        _download_verified(RECOGNIZER_URL, recognizer, RECOGNIZER_SHA256)
        _write_embedded_dictionary(recognizer, dictionary)
        manifest = {
            "version": OCR_ASSET_VERSION,
            "source": RECOGNIZER_URL,
            "files": {
                "detector": {"name": detector.name, "sha256": DETECTOR_SHA256},
                "classifier": {"name": classifier.name, "sha256": CLASSIFIER_SHA256},
                "recognizer": {"name": recognizer.name, "sha256": RECOGNIZER_SHA256},
                "dictionary": {"name": dictionary.name, "sha256": _sha256(dictionary)},
            },
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        for source in temporary.iterdir():
            os.replace(source, root / source.name)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)
    return KoreanOCRAssets.load(sandbox)


def _copy_bundled_model(name: str, destination: Path, expected_sha256: str) -> None:
    resource = files("rapidocr").joinpath("models", name)
    with as_file(resource) as source:
        if _sha256(source) != expected_sha256:
            raise RuntimeError(f"Bundled RapidOCR model failed SHA-256 verification: {name}")
        shutil.copyfile(source, destination)
    if _sha256(destination) != expected_sha256:
        raise RuntimeError(f"Copied RapidOCR model failed SHA-256 verification: {name}")


def _download_verified(url: str, destination: Path, expected_sha256: str) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "sort-pilot/0.1"})
    digest = hashlib.sha256()
    with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as stream:
        while block := response.read(1024 * 1024):
            digest.update(block)
            stream.write(block)
        stream.flush()
        os.fsync(stream.fileno())
    if digest.hexdigest() != expected_sha256:
        destination.unlink(missing_ok=True)
        raise RuntimeError("Downloaded Korean PP-OCRv5 model failed SHA-256 verification.")


def _write_embedded_dictionary(model_path: Path, destination: Path) -> None:
    from onnxruntime import InferenceSession

    session = InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    characters = session.get_modelmeta().custom_metadata_map.get("character", "").splitlines()
    if not characters or any("\n" in value or "\r" in value for value in characters):
        raise RuntimeError("Korean PP-OCRv5 model has no valid embedded character dictionary.")
    destination.write_text("\n".join(characters) + "\n", encoding="utf-8", newline="\n")


def _verify_dictionary_matches_model(model_path: Path, dictionary_path: Path) -> None:
    from onnxruntime import InferenceSession

    session = InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    embedded = session.get_modelmeta().custom_metadata_map.get("character", "").splitlines()
    local = dictionary_path.read_text(encoding="utf-8").splitlines()
    if not embedded or local != embedded:
        raise RuntimeError("Local Korean OCR dictionary does not match the verified model.")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _valid_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )
