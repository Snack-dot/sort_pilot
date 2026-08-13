# SRS — Local File Classifier (working name: `tidy`)

> **Implementation note (2026-08-13):** The integrated desktop MVP uses explicit Desktop/Downloads batch actions and a cancellable two-worker in-process queue. Watcher-oriented requirements below are retained as historical/future requirements and are not part of the current app workflow. The engine package is now `sort_pilot.classifier_engine`; its data directory remains `%APPDATA%\tidy` for compatibility.
>
> The current destination model is hierarchical: one fixed Korean file-type root plus one family-specific semantic topic. User profiles override built-ins; unmatched files use `미분류`; current-batch TF-IDF discovery never creates a topic without explicit approval.

**Status:** Draft v0.3 · **Owner:** you · **Target:** MVP, Windows-first, Korean + English
**Context:** 공모전 submission and personal daily-driver. Single user, single machine, no distribution.

That context sets the priority order for everything below:

1. **It must actually work on your own files.** You are user zero and the only user. A demo that impresses judges but that you stop using in week two has failed.
2. **It must demo in three minutes.** Judges see a narrow slice. The slice that sells this is a KakaoTalk folder full of `KakaoTalk_20260809_123456.jpg` turning into sorted categories in front of them — no filenames, no metadata, pure content understanding.
3. **The resource argument is the thesis.** Your differentiator against a VLM approach is measurable: RAM, CPU, latency. Instrument it from day one so you can put real numbers on a slide. An unmeasured claim is worth nothing in judging.
4. Robustness matters only where it protects *your* files.

Requirements marked ★ are demo-critical. Requirements marked ○ are relaxed or optional given single-user scope — they are kept in the document because they are the right answer if this ever ships, not because you should build them for the deadline.

---

## 1. What this product is

A background tray utility that watches two or three noisy folders, works out what each new file *is*, and either files it or asks. It runs on a 4–8 GB laptop without the user noticing it exists.

The classifier is a Naive Bayes model over cheap text features, stored as a plain dictionary and updated every time the user corrects it. A local VLM is an optional, off-by-default escape hatch — not the engine.

**The one metric that matters:** a wrong auto-move costs far more trust than a deferral. Optimise for precision, then coverage.

---

## 2. Scope

### In scope (MVP)

- Watch `Downloads` and the KakaoTalk received-files folder. ★
- Tier 1 (filename/metadata rules) and Tier 2a (text keywords) fully working.
- Tier 2b (OCR on images), Korean + English. ★
- Tier 2c (vision: object detection plus derived co-occurrence and context features). ★
- Suggestion queue UI + one-click accept/correct, with undo.
- Bootstrap from existing folder structure. ★
- Resource instrumentation: live RAM/CPU/latency readout, exportable. ★

### Out of scope (MVP)

- Tier 3 LLM/VLM fallback (interface defined, implementation deferred).
- macOS/Linux builds.
- Installer and packaging ○ — run from source in your own venv.
- Cloud anything. Sync, accounts, telemetry, remote models — excluded permanently.
- Content search / semantic search over the index.

---

## 3. Definitions

| Term | Meaning |
| --- | --- |
| **Feature** | A single token extracted from a file: a filename fragment, a body keyword, an OCR word, an extension, or a metadata flag. |
| **Feature vector** | The bag of features for one file, with per-feature source and count. |
| **Category** | A destination folder, e.g. `Finance`, `School`. One label per file. |
| **Decision** | `(category, score, margin, action)` produced by the classifier for one file. |
| **Margin** | `score(top1) − score(top2)` in log space, length-normalised. The confidence signal actually used for gating. |
| **Auto-move** | The app moves a file without asking. |
| **Suggestion** | The app proposes a destination and waits. |
| **Journal** | Append-only record of every action taken, sufficient to reverse it. |

---

## 4. Operating principles

These constrain every requirement below. When a requirement conflicts with one of these, the principle wins.

1. **Never lose a file.** Every move is journalled and reversible for at least 30 days.
2. **Never touch a file that is still being written.** Stability check before any read.
3. **Uncertainty is a normal outcome, not a failure.** Low margin → suggestion queue, not a guess.
4. **The user's corrections are the training set.** There is no other one.
5. **Nothing leaves the device.** No network calls in the classification path, ever.
6. **Idle means idle.** Zero CPU when no file events are pending.

---

## 5. Functional requirements

IDs are stable. Reference them in commits and in Claude Code prompts (`implement FR-210 and FR-211`).

### 5.1 File capture (FR-1xx)

| ID | Requirement | Acceptance |
| --- | --- | --- |
| FR-101 | Watch a configurable list of directories using OS-native filesystem events (`watchdog`). Non-recursive by default; recursion is per-directory config. | Dropping a file into a watched dir enqueues it within 2 s. |
| FR-102 | On startup, reconcile: scan watched dirs and enqueue any file whose `(path, mtime, size)` is absent from the seen-index. | App closed → 5 files added → app opened → all 5 enqueued exactly once. |
| FR-103 | Debounce each path by a configurable settle window (default 5 s from last write event). | A 200 MB download fires one enqueue, not hundreds. |
| FR-104 | Skip files matching in-progress patterns: `*.crdownload`, `*.part`, `*.tmp`, `*.download`, `~$*`, and any file with a shared-write lock on Windows. | A partial Chrome download is never read or moved. |
| FR-105 | Verify stability before processing: size and mtime unchanged across two probes ≥ 2 s apart. | A file being copied over the network is deferred until it settles. |
| FR-106 | Skip files above a configurable size ceiling (default 200 MB) for content extraction; classify by Tier 1 signals only. | A 4 GB ISO is never opened for reading. |
| FR-107 | Honour an exclusion list of glob patterns and absolute paths. Directories inside watched dirs that are themselves destination categories are always excluded. | Files already sorted into `Downloads/Finance/` are not re-processed. |
| FR-108 | Maintain a processing queue with at most one worker. Queue survives restart. | Killing the app mid-queue loses no pending items. |

### 5.2 Feature extraction (FR-2xx)

| ID | Requirement | Acceptance |
| --- | --- | --- |
| FR-201 | Emit a feature vector for every file, tagged by source (`filename`, `ext`, `body`, `ocr`, `meta`). | Vector schema validates against `feature_vector.schema.json`. |
| FR-202 | **Filename features:** split on separators, camelCase, and digit boundaries; strip timestamps and counters (`(1)`, `_20260809_123456`); lowercase; keep tokens ≥ 2 chars. | `KakaoTalk_20260809_123456.jpg` → `["kakaotalk"]` + meta flag `kakao_export`. |
| FR-203 | **Korean tokenisation:** run Korean text through a morphological analyser and keep noun/verb-stem morphemes only. Naive whitespace splitting is not acceptable. | `회의록에서` and `회의록을` both yield `회의록`. |
| FR-204 | **Text documents:** extract raw text from PDF, DOCX, TXT, MD, HWP, RTF. Cap extraction at the first N pages / M characters (defaults: 5 pages, 20 000 chars). | A 400-page PDF extracts in under 300 ms. |
| FR-205 | Rank body tokens by TF·IDF using an **incrementally maintained document-frequency table over the user's own corpus**, seeded with a shipped DF table. Keep top K (default 30). | DF table updates after each processed file; cold start still produces sane rankings. |
| FR-206 | Remove stop-words for Korean and English from a shipped, editable list. | `그리고`, `the`, `합니다` never appear in a feature vector. |
| FR-207 | **Images:** classify as screenshot vs. photo using EXIF presence, dimensions matching known screen resolutions, and format. Emit the verdict as a meta feature. | A phone photo with EXIF → `photo`; a PNG at 2560×1440 with no EXIF → `screenshot`. |
| FR-208 | **OCR (Tier 2b):** run local OCR on screenshots and on images under a size threshold, in Korean + English. Emit recognised words as `ocr` features. | A KakaoTalk chat screenshot yields ≥ 10 usable tokens. |
| FR-209 | **Metadata features:** extension, MIME sniff, EXIF camera model presence, PDF producer string, archive contents listing (top-level names only, no extraction). | A `.zip` yields the names of its entries as features without unpacking. |
| FR-210 | Every extractor runs under a hard timeout (default 10 s) and a memory guard. On timeout, emit whatever features exist and mark the vector `partial`. | A malformed PDF cannot hang the worker. |
| FR-211 | Extractors are isolated: a crash in one extractor never kills the worker process. | Feeding 100 corrupt files leaves the app running. |
| FR-212 ★ | **Object detection (Tier 2c):** run YOLOv8n via ONNX Runtime on photos. Emit detected class labels above a confidence floor as `obj` features, with per-detection confidence carried as the feature weight. | A photo of a desk yields `laptop`, `book`, `cup`, `keyboard`. |
| FR-213 ★ | **Derived visual features:** from the same detections, emit pairwise conjunction tokens (`pair:a+b`) over the top-5 classes, object-count buckets, and subject-size flags. Emit context features from EXIF, colour statistics, and aspect ratio. | One photo with 5 detections yields ≥ 12 features total. |
| FR-214 | Vision and OCR share one image decode. An image is loaded, resized, and passed to every enabled vision model in a single subprocess invocation. | Processing one photo decodes it once, not three times. |

### 5.3 Classification (FR-3xx)

| ID | Requirement | Acceptance |
| --- | --- | --- |
| FR-301 | Tier 1 evaluates deterministic rules (extension map, filename regex, source-URL metadata on Windows Zone.Identifier) before any file read. A Tier 1 hit short-circuits the pipeline. | `설치파일.exe` is routed with zero file reads. |
| FR-302 | Tier 1 rules are user-editable in a config file, ordered, with first-match-wins semantics. | User adds a rule and it takes effect without restart. |
| FR-303 | Tier 2 scores every category with multinomial Naive Bayes over the feature vector, with per-source feature weights and Laplace smoothing. | Scores reproducible: same vector + same model → same output. |
| FR-304 | The decision gate uses **length-normalised margin**, not raw posterior. Two thresholds: `θ_auto` (auto-move) and `θ_suggest` (show suggestion). Below `θ_suggest` → `Unsorted`. | Documented in `ARCHITECTURE.md` §5.3; thresholds live in config. |
| FR-305 | Every decision records its top 8 contributing features with signed contributions, for display to the user. | The UI can answer "why did you think this was Finance?" |
| FR-306 | If Tier 2 falls below `θ_suggest` **and** Tier 3 is enabled, escalate to Tier 3. If Tier 3 is disabled, route to the suggestion queue as `Unsorted`. | With Tier 3 off, no file is ever silently dropped. |
| FR-307 | Tier 3 is defined as an interface (`Classifier.classify(vector, candidates) -> Decision`) with a stub implementation in MVP. | A future local-LLM backend drops in without touching the pipeline. |
| FR-308 | Category vocabulary is derived from the user's chosen destination root: each immediate subdirectory is a category. Users may add, rename, merge, or hide categories. | Renaming a folder on disk does not orphan its learned weights. |

### 5.4 Learning and calibration (FR-4xx)

| ID | Requirement | Acceptance |
| --- | --- | --- |
| FR-401 | **Bootstrap wizard:** on first run, offer to learn from existing organised folders. Sample up to N files (default 200) per category, extract features, populate counts. | After bootstrap on a real user's Documents tree, top-1 accuracy on held-out files ≥ 70 %. |
| FR-402 | Ship a **seed lexicon** (Korean + English) mapping common terms to default categories, loaded as prior pseudo-counts. | On a fresh profile with no bootstrap, `세금계산서.pdf` still routes to Finance. |
| FR-403 | Accepting a suggestion increments counts for the chosen category. | Model file changes; the same file re-classified scores higher. |
| FR-404 | Correcting a suggestion increments the correct category **and** applies a configurable decrement to the wrongly predicted one (default: partial, not full). | Two corrections flip a borderline term's routing; one does not whipsaw it. |
| FR-405 | Every model update is journalled with the exact count deltas, so it can be reversed. | Undoing a move also undoes its learning. |
| FR-406 | Vocabulary is pruned on a schedule: drop tokens with total count < 2 unseen for 90 days. Hard cap 30 000 tokens. | Model file stays under 5 MB after a year of use. |
| FR-407 | Thresholds are recalibrated from observed accept/correct history once there are ≥ 50 labelled decisions, targeting the configured precision floor. | `θ_auto` moves measurably after a user who corrects often vs. one who never does. |
| FR-408 | Export and import the full model as JSON for inspection, backup, and sharing. | `classifier_weights.json` is human-readable and round-trips. |

### 5.5 Actions and safety (FR-5xx)

| ID | Requirement | Acceptance |
| --- | --- | --- |
| FR-501 | Moves are atomic within a volume (`os.replace`); cross-volume moves are copy-verify-delete with hash check. | Pulling the plug mid-move leaves either the source or a complete destination, never a truncated file. |
| FR-502 | Name collisions resolve by suffixing ` (2)`, ` (3)`, …; never overwrite. | Two `invoice.pdf` files coexist in the destination. |
| FR-503 | **Undo journal:** every move records source path, destination path, timestamp, decision, and model deltas. Retained 30 days minimum. | "Undo last 10 actions" restores all ten files to their original paths. |
| FR-504 | **Dry-run mode:** log what would happen, touch nothing. Default ON for the first 7 days of use. | A new install moves zero files in week one unless the user opts in. |
| FR-505 | Never move files that live inside a cloud-sync folder unless the user explicitly enables it; warn when detected. | OneDrive/Dropbox/Google Drive roots are detected and flagged. |
| FR-506 | Never move a file that is currently open or locked; defer and retry with backoff. | An open Excel file is not moved out from under Excel. |
| FR-507 | Never delete anything. Ever. The app has no delete path. | Grep the codebase: no `os.remove` outside cache/temp management. |

### 5.6 Interface (FR-6xx)

| ID | Requirement | Acceptance |
| --- | --- | --- |
| FR-601 | System tray icon with state (idle / working / N pending). Left-click opens the review queue. | — |
| FR-602 | Review queue lists pending files with thumbnail/icon, proposed category, margin as a plain-language confidence, and the top contributing features. | User can accept, change category, or say "leave it" in one click each. |
| FR-603 | Batch operations: select multiple, apply one category. | 20 KakaoTalk images filed in one action. |
| FR-604 | Activity log showing recent auto-moves with per-item undo. | — |
| FR-605 | Notifications are opt-in and batched (default: one summary per hour, max). | The app never interrupts more than once an hour. |
| FR-606 | Settings: watched folders, destination root, categories, thresholds (as a simple aggressive↔cautious slider), tier toggles, exclusions, dry-run. | — |

### 5.7 Privacy (FR-7xx)

| ID | Requirement | Acceptance |
| --- | --- | --- |
| FR-701 | No outbound network connections from the classification path. Enforced by test. | Integration test with network blocked passes end to end. |
| FR-702 | No telemetry, no crash reporting to a server, no update pings without explicit opt-in. | — |
| FR-703 | The feature index and model constitute a searchable digest of the user's document contents. Store under user-only file permissions and document this in the UI. | Data directory is `0700` / user-only ACL. |
| FR-704 | OCR of screenshots may capture credentials and banking data. Provide a "don't OCR" folder list and never persist raw OCR text — only the pruned token set. | Raw OCR output exists in memory only. |
| FR-705 | "Delete all learned data" wipes model, index, and journal in one action. | — |

---

## 6. Non-functional requirements

### 6.1 Resource budget

Measured on the reference machine: 4 GB RAM, 4-core mobile CPU, HDD or slow SSD, Windows 11.

| ID | Requirement | Limit |
| --- | --- | --- |
| NFR-101 | Idle RSS, worker process, queue empty | ≤ 80 MB |
| NFR-102 | Idle CPU, queue empty | 0.0 % (event-driven; no polling loop) |
| NFR-103 | Peak RSS during Tier 2a (text) | ≤ 200 MB |
| NFR-104 | Peak RSS during Tier 2b (OCR) | ≤ 450 MB |
| NFR-105 | Peak RSS during Tier 2c (vision) | ≤ 400 MB |
| NFR-106 | Peak RSS, OCR + vision in one subprocess pass | ≤ 600 MB |
| NFR-107 | Concurrent extraction workers | exactly 1 |
| NFR-108 | Process priority | below-normal / idle I/O priority |
| NFR-109 | Tiers 2b/2c suspended on battery below a configurable level (default 30 %) | verified on a laptop |
| NFR-110 | UI process runs only while a window is open | — |
| NFR-111 ★ | Every stage records wall time and peak RSS into `decisions`, exportable as CSV | you can produce the resource comparison chart from real data |

NFR-106 is roughly 7× NFR-101. That is the honest cost of running two vision models, and it still lands well under a 2B VLM at Q4 (~1.8–2.5 GB resident, held for the process lifetime rather than released). The comparison that wins the argument is not peak but **time-integrated**: your heavy tiers hold 600 MB for two seconds and then return to 80 MB, while a resident VLM holds 2 GB for eight hours. Measure and present it that way (NFR-111).

Do not quote a single "Tier 2 costs 10–50 MB" figure. The text path and the vision path differ by an order of magnitude (§11, ADR-002).

### 6.2 Latency

| ID | Stage | Budget (p95) |
| --- | --- | --- |
| NFR-201 | Tier 1 decision | ≤ 5 ms |
| NFR-202 | Tier 2a, 20-page PDF | ≤ 300 ms |
| NFR-203 | Tier 2a, DOCX/TXT | ≤ 100 ms |
| NFR-204 | Tier 2b, 1080p screenshot OCR | ≤ 3 s |
| NFR-205 | Tier 2c, YOLOv8n @ 640×640, CPU | ≤ 1.5 s |
| NFR-206 | Tier 2c, derived + context features per image | ≤ 30 ms |
| NFR-207 | Vision subprocess cold start (ORT session init + model load) | ≤ 1.5 s |
| NFR-208 | Classifier scoring, 30 features × 20 categories | ≤ 2 ms |
| NFR-209 | Cold start to watching | ≤ 3 s |

NFR-207 is why batching matters: paying 1.5 s of session init per photo is unacceptable for a folder of 200 KakaoTalk images. The vision subprocess must accept a batch of paths, initialise once, and stream results back (see `ARCHITECTURE.md` §3.6).

### 6.3 Quality

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-301 | Precision of auto-moves, measured on the eval corpus | ≥ 97 % |
| NFR-302 | Top-1 accuracy of suggestions | ≥ 85 % |
| NFR-303 | Coverage: share of files auto-handled after 2 weeks of normal use | ≥ 60 % |
| NFR-304 | Vision escalation rate (share of all files reaching Tier 2b or 2c) | ≤ 25 % |
| NFR-305 | Files landing in `Unsorted` after bootstrap | ≤ 15 % |

An eval corpus of ≥ 300 hand-labelled real files across ≥ 8 categories, split by source folder, is a prerequisite for claiming any of these. Build it before tuning anything.

### 6.4 Reliability

| ID | Requirement |
| --- | --- |
| NFR-401 | Any unhandled exception in extraction or classification results in the file being queued as `Unsorted`, never in a crash or a move. |
| NFR-402 | Model file writes are atomic (write temp → fsync → replace). A crash mid-write never corrupts the model. |
| NFR-403 | Corrupt model or index files are detected on load and rebuilt from the journal, with the user notified. |
| NFR-404 | The app survives its watched directory being deleted, renamed, or unmounted. |

### 6.5 Licensing ○

Not a constraint on personal, non-distributed use. AGPL obligations trigger on conveying the work to others or offering it over a network; neither applies to a tool running on your own laptop. **Ultralytics YOLOv8 and PyMuPDF are both fine.**

| ID | Requirement |
| --- | --- |
| NFR-501 | If the contest requires submitting a binary or repository, that is distribution and AGPL terms apply — publishing the source under AGPL-3.0 satisfies them. Decide this before submission day, not on it. |
| NFR-502 | Maintain `THIRD_PARTY.md` with dependency, version, and license anyway. It takes twenty minutes and judges of technical contests do look. |

### 6.6 Packaging ○

Out of scope. Run from source in a venv. If a judge needs to run it, `uv sync && uv run tidy` is an acceptable answer; spend the time on the demo instead.

| ID | Requirement |
| --- | --- |
| NFR-601 | Model files (YOLOv8n ~12 MB, OCR ~15 MB) live in `data/models/`, downloaded by a setup script, gitignored. |
| NFR-602 ★ | `README.md` gets a working from-scratch setup path, verified on a clean venv. |

---

## 7. Configuration defaults

### 7.1 Watched paths (Windows)

```
%USERPROFILE%\Downloads
%USERPROFILE%\Documents\카카오톡 받은 파일
```

The KakaoTalk path varies by version, locale, and user setting — resolve it from the KakaoTalk registry key or config if possible, and fall back to a folder picker. Do not hard-code it as the only strategy.

### 7.2 Destination root

Default: `%USERPROFILE%\Documents\Sorted`, with the bootstrap wizard offering to use an existing organised tree instead.

### 7.3 Tier enablement

| Tier | Default | Rationale |
| --- | --- | --- |
| Tier 1 | on | free |
| Tier 2a (text) | on | cheap, high yield |
| Tier 2b (OCR) | on for images routed as *screenshot* | filenames carry nothing there; OCR carries everything |
| Tier 2c (vision) | on for images routed as *photo* | same, in the other direction |
| Tier 3 (LLM) | off, not implemented in MVP | — |

The screenshot/photo router (FR-207) is what keeps this affordable: each image pays for one vision path, not both. A KakaoTalk folder is typically a mix of both, which makes it the ideal demo — the router visibly sends each image down a different branch.

---

## 8. Constraints

- Reference hardware is 4 GB RAM. Every design choice is judged against that, not against a dev machine.
- Windows filesystem semantics govern: locked files, path length limits, ACLs, `Zone.Identifier` alternate data streams.
- Korean is a first-class language, not an afterthought. Any component that assumes whitespace tokenisation or Latin script is disqualified.
- No dependency may require a compiler at install time on the user's machine.

---

## 9. Milestones

| Milestone | Contents | Done when |
| --- | --- | --- |
| **M0 — Eval harness** | Labelled corpus from *your own* Downloads and KakaoTalk folders, metrics script, resource instrumentation | You can measure a change |
| **M1 — Skeleton** | Watcher, queue, journal, dry-run logging, tray icon | Files detected and logged; nothing moves |
| **M2 — Tier 1** | Rules engine, extension map, filename normalisation | ≥ 30 % of Downloads handled by rules alone |
| **M3 — Tier 2a** | Text extraction, Korean tokenisation, NB classifier, seed lexicon | NFR-302 met on the document subset |
| **M4 — Learning** | Bootstrap from existing folders, feedback loop | Accuracy measurably improves over 50 corrections |
| **M5 — Vision** | Screenshot/photo router, OCR, YOLO, pair + context features, batch subprocess | KakaoTalk folder sorts end-to-end ★ |
| **M6 — Review UI** | Queue, batch actions, undo, explanations | You use it daily for a week |
| **M7 — Demo** | Resource comparison chart, scripted 3-min walkthrough, README | Rehearsed twice, on the 4 GB machine |

Do M0 first. Everything after it is guesswork otherwise — and M0 is also where the contest chart comes from.

**If time runs short, cut in this order:** threshold calibration (FR-407) → batch UI operations (FR-603) → cross-volume move support (FR-501, second half) → context features (keep pairs). Do not cut M0, M5, or M7.

**M7 is not optional.** A working classifier presented badly loses to a worse one presented well. Budget real time for it: the resource chart, a before/after of a real KakaoTalk folder, and one slide showing the tier escalation rates that prove most files never touch a neural network at all.

---

## 10. Open questions

| # | Question | Blocks |
| --- | --- | --- |
| Q1 | Does the target user already have an organised folder tree to bootstrap from, or are we creating the taxonomy for them? Changes M4 substantially. | M4 |
| Q2 | UI framework: Qt (heavy, native tray, one process) vs. tray + local web UI (lighter idle, more moving parts)? | M5 |
| Q3 | Distribution model — open source, or closed? Determines which licenses are usable (NFR-501). | M3 |
| Q4 | Are archives (`.zip`) classified by contents, or always routed to a single category? | M2 |
| Q5 | What happens to a file the user manually moves out of a destination folder? Signal for unlearning, or ignore? | M4 |

---

## 11. Decision record

**ADR-001 — Multinomial Naive Bayes, with co-occurrence expressed as conjunction features.** *(Revised in v0.3.)*

The source plan uses "Naive Bayes classifier" and "co-occurrence matrix" interchangeably, and they are not the same model. NB assumes features are conditionally independent given the category and sums per-feature log-likelihoods; it has no pairwise term. A true co-occurrence matrix is quadratic in vocabulary and needs far more data than a personal tool will ever see.

But the plan's *intent* — that combinations carry context single features do not — is sound, and it does not require abandoning NB. You inject interaction terms by emitting conjunctions as synthetic tokens: `pair:book+laptop` is one token that the model scores independently of `obj:book` and `obj:laptop`, and it learns from user corrections that the conjunction is more indicative than either constituent. Vocabulary growth is bounded by capping the number of classes that participate in pairing and by the existing pruning rule.

**Decision:** multinomial NB over a feature set that includes conjunction tokens for visual features (`ARCHITECTURE.md` §3.5). Do not build a co-occurrence matrix as a separate structure. Do not use "co-occurrence matrix" as a synonym for the model in code or docs — it describes one *feature family*, not the classifier.

Note that pair features are correlated with their constituents, which formally violates NB's independence assumption. This is a known and tolerable trade: NB's *ranking* stays useful under correlated features even as its posteriors grow miscalibrated, which is exactly why the decision gate uses margin instead of raw probability.

Text features do not get pairing. A 30-token document already has enough evidence, and pairing them would add ~450 tokens per file for no gain.

**ADR-002 — Split Tier 2 into 2a and 2b.** Text extraction and OCR differ by roughly 10× in memory and 30× in latency. A single tier with a single cost figure will produce a scheduler that treats them alike, which is how a background app stops being in the background. **Decision:** separate tiers, separate budgets, separately toggleable per watched folder.

**ADR-003 — Suggest before moving.** The plan implies automatic filing from day one, but the model is empty on day one. **Decision:** ship in dry-run/suggest mode; auto-move unlocks per category after the user has accepted N suggestions in that category with no corrections. This also produces the labelled data the model needs.

**ADR-004 — Object detection only; scene emerges from co-occurrence.** *(Revised twice. v0.2 reinstated YOLO on licensing grounds. v0.3 removes the scene classifier.)*

The emergent-context argument in §4 of the source plan is right, and my v0.2 objection was wrong. Naive Bayes does not need a token spelling out `coffee_shop`; it needs `P(features | category)` to differ across categories. If your `공부` photos reliably contain `laptop`, `book`, `cup` and your `가족` photos reliably contain `person`, `cake`, `dining table`, the model separates them without any component ever representing what a café is. The scene label is a convenience, not a requirement, and it is one the user's own corrections supply for free.

The constraint that does bite is **evidence density**, not label vocabulary. A photo yields 2–5 detections where a PDF yields 30 tokens, and the margin gate is normalised by evidence count — so sparse photos fail as `Unsorted` rather than as wrong answers. `ARCHITECTURE.md` §3.5 addresses this with four cheap measures: a lower confidence floor, count and geometry features, pairwise conjunction tokens, and EXIF/colour context. Together they take one photo from 5 features to roughly 14.

**Decision:** YOLOv8n only. Add a scene classifier only if the eval says you need one — the trigger condition and the query are in `ARCHITECTURE.md` §3.5.

**Demo note:** the detected tags are the most legible part of the whole system to a non-technical judge. Show them in the review UI next to each photo. "Here is what the app saw, here are the combinations it weighed, here is why it chose this folder" beats any accuracy number in three seconds — and it demonstrates the emergent-context thesis visually rather than asserting it on a slide.

**ADR-005 — TF·IDF needs a corpus; use the user's own.** IDF is undefined for a single file. **Decision:** maintain an incremental document-frequency table across processed files, seeded with a shipped table so cold start behaves. It is a second JSON dictionary, consistent with the plan's storage philosophy.
