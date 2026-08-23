$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot

$branch = (& git branch --show-current).Trim()
if ($branch -ne "architecture-srs-implementation") {
    throw "Expected architecture-srs-implementation, found '$branch'."
}

$dirty = & git status --porcelain
if ($dirty) {
    throw "The repository has uncommitted changes. Review them before resuming training."
}

$pythonCandidates = @(
    (Join-Path $repoRoot ".venv\Scripts\python.exe"),
    (Join-Path $repoRoot "..\ai-file-organizer-team-mvp-fixed\.venv\Scripts\python.exe")
)
$pythonExe = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if (-not $pythonExe) {
    throw "No compatible local virtual-environment Python was found."
}

$env:PYTHONPATH = $repoRoot

Write-Output "STEP=verify-local-ocr-assets"
& $pythonExe -c "from sort_pilot.classifier_engine.ocr import KoreanOCRAssets; a=KoreanOCRAssets.load(); print('OCR_ASSETS=verified'); print('OCR_MODEL=' + str(a.recognizer)); print('OCR_DICTIONARY=' + str(a.dictionary))"
if ($LASTEXITCODE -ne 0) { throw "Local Korean OCR asset verification failed." }

Write-Output "STEP=focused-tests"
& $pythonExe -m pytest -q `
    tests\test_ocr_pdf_pipeline.py `
    tests\test_classifier_pipeline.py `
    tests\test_tfidf.py `
    tests\test_educational_service.py `
    tests\test_academic_logistic.py `
    tests\test_hwp_extract.py `
    tests\test_sandbox.py
if ($LASTEXITCODE -ne 0) { throw "Focused tests failed; training was not started." }

Write-Output "STEP=train-academic-logistic-v2"
& $pythonExe eval\train_academic_logistic.py
if ($LASTEXITCODE -ne 0) { throw "Academic logistic training failed." }

Write-Output "STEP=verify-training-report"
& $pythonExe -c "import json; from pathlib import Path; p=Path.home()/'Downloads'/'sandbox'/'.sort_pilot_state'/'logistic'/'training_report.json'; d=json.loads(p.read_text(encoding='utf-8')); assert d['version']=='academic-logistic-training-v2'; assert d['scope']['labels'] >= 300; assert d['privacy']['raw_text_persisted'] is False; assert d['privacy']['ocr_text_persisted'] is False; print('TRAINING_REPORT=verified'); print('LABELS=' + str(d['scope']['labels']))"
if ($LASTEXITCODE -ne 0) { throw "The v2 training report did not pass validation." }

Write-Output "RESUME_RESULT=complete"
