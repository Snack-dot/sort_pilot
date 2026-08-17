# Conversation Reconstruction

Date: 2026-08-17 (Asia/Seoul)

The user established that the authoritative hybrid educational classifier plan must be followed literally. Product vocabulary must come from that plan, the classifier has exactly the subject and template axes, and the five templates are exactly `학습자료`, `과제`, `교내활동`, `교외활동`, and `증빙서류`. If a material choice is not in the plan, work must stop and ask the user first.

The user also established the documentation hierarchy: `plans/HYBRID_EDUCATIONAL_CLASSIFIER_PLAN.md` is supreme; superseded plans, the older Korean-student material, architecture, SRS, and third-party documents are references only. Every session must be recorded under `session_archive/`.

For evaluation privacy, the user permitted a labeled corpus made entirely from invented examples. Any evaluation or correction involving real local files, filenames, extracted text, labels, predictions, or corrections must stay local, must be ignored by Git, and must never be uploaded to GitHub.

Phases 0–6 were complete at the prior checkpoint. The user had approved 90% held-out precision for authoritative local decisions and 50% held-out top-label accuracy for Gemma escalation. The user instructed the assistant to continue.

At the beginning of Phase 7, the plan required future files to use nearest personal-example similarity but did not give a numeric weight or minimum similarity. The assistant raised that missing material choice. When the user asked “What do you mean?”, the assistant clarified that it proposed deriving a conservative value independently for subject and template from only the made-up corpus and held-out cases, retaining the Phase 5 thresholds and the already approved 90%/50% targets. The user answered “Sure.”

Before editing, the assistant read `docs/AGENTS.md`, `README.md`, the authoritative plan, the complete newest Phase 6 archive, Git status, the active branch, and the latest commits. Phase 7 was the first unfinished phase.

The implementation then added strict personal examples and calibrated nearest-example evidence; propagated transient extracted natural text and separate structured evidence; composed the E5 classifiers, independent routing, personal evidence, and constrained Gemma fallback; added the fixed-choice educational preview; froze collision-resolved paths; reused the transactional mover and Undo; and changed the active tray organization route from the older topic workflow to the educational subject/template workflow.

Focused tests and the made-up calibration reproduction were run throughout. Active documentation was updated, and this archive was written. No real-file evaluation, model download, file organization run, commit, or push was performed.
