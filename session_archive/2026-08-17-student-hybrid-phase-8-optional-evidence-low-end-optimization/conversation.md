# Conversation Reconstruction

Date: 2026-08-17 (Asia/Seoul)

The user required literal adherence to `plans/HYBRID_EDUCATIONAL_CLASSIFIER_PLAN.md`, exact plan vocabulary, exactly the subject and template axes, and exactly the five templates `학습자료`, `과제`, `교내활동`, `교외활동`, and `증빙서류`. When a material decision is absent from the plan, work must stop and ask the user first. Reference documents cannot override the main plan, and every session must be recorded under `session_archive/`.

The user permitted tracked labels only for entirely made-up evaluation cases. Any evaluation involving real local files, filenames, extracted text, labels, predictions, or corrections must remain under Git-ignored `eval/local/` and must never be committed or uploaded to GitHub.

Before Phase 8, the user authorized a retrospective phase-by-phase Git reconstruction from commit `66f1a84`, required a temporary local safety branch, byte-for-byte final-tree comparison, complete verification, no automatic push, and retention of the safety branch. That reconstruction produced separate Phase 0–7 commits and retained `safety/phase-0-7-complete-20260817`.

For Phase 8, the main plan said to add OCR-layout, PMI, YOLO/LVIS, and model-session scheduling only when ablation and low-memory measurements justify them, but it did not specify numeric gates. The assistant stopped and asked. Through the following exchange, the user required significant increases in all three accuracy measures—subject accuracy, template accuracy, and combined-path accuracy—and allowed latency to remain about the same or become only slightly higher.

The agreed complete gate became: at least five percentage points improvement and exact paired `p < 0.05` for each of the three accuracy measures; candidate P95 latency no more than 10% above the Phase 7 baseline; and candidate peak process memory at or below 2 GB. The selected complete configuration had to pass every gate.

The initial development ablation showed significant template and combined-path gains but insufficient authoritative subject resolution. The assistant kept the Phase 5 thresholds unchanged, added a bounded structured Kiwi lexical contribution for subject ranking, and selected weight `0.05` on made-up development cases. A separate made-up held-out corpus was then reserved for the final check.

During implementation, the assistant corrected two measurement issues before completion. First, template semantic intent now uses the original OCR detection order while subject semantic intent uses layout-ordered OCR; this avoids allowing subject-oriented reordering to distort the independent template task. Second, the implemented lexical normalization was corrected to match the complete subject-profile set used in development. This restored at least 90% authoritative-local subject precision without changing the Phase 5 routing thresholds.

The development ablation retained PMI and rejected visual evidence. That selection was frozen before the held-out run. The held-out runner verified the frozen selection rather than selecting evidence from held-out labels. The final active selection retains OCR layout, subject Kiwi weight `0.05`, and PMI; it disables YOLO/LVIS and does not add model-session scheduling. The active educational extractor therefore no longer runs YOLO.

No real local evaluation data, model download, network call, file organization, deletion, or push was performed during Phase 8.
