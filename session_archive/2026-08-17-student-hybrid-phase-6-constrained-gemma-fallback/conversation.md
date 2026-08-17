# Conversation Reconstruction

Date: 2026-08-17 (Asia/Seoul)

The user had already established that the authoritative plan must be followed literally, with no invented classification vocabulary or additional axis. The classifier has exactly two axes, subject and template. The five templates remain exactly `학습자료`, `과제`, `교내활동`, `교외활동`, and `증빙서류`. Reference documents cannot override the authoritative plan, every session must be archived, and work must stop for user direction when a material answer is absent from the plan.

The user had also established the evaluation privacy boundary: only made-up corpus contents and labels may be tracked. Anything involving real local files, filenames, extracted text, labels, predictions, or corrections must stay under Git-ignored `eval/local/` and must never be committed or uploaded.

Phases 0–5 were complete at the previous checkpoint. Phase 5 used the user's exact operating targets: 90% held-out precision for authoritative local results and 50% held-out top-label accuracy for Gemma escalation. The user then instructed the assistant to continue.

Before editing, the assistant read `docs/AGENTS.md`, the authoritative plan, the latest Phase 5 archive, Git status, and the latest commits. Phase 6 was the first unfinished phase. The assistant compared the current local Gemma code with the `fix` branch directly, without switching branches.

The comparison separated reliable operational behavior from obsolete classification behavior. The reusable behavior was one loopback server session, bounded batches, retry of unresolved items, explicit cancellation, immediate atomic caching, progress, and forced server shutdown. The old branch's roles, areas, topics, document-type values, and folder-producing output were rejected because they do not belong to the authoritative student plan.

The assistant implemented a new educational Phase 6 module rather than changing the legacy cluster-naming interface. The first implementation constrained output to supplied candidates or Needs Review. A compliance pass then tightened the request boundary so every request also requires a validated student profile and every subject candidate must be in that selected profile's `KR_STUDENT_2026_MVP_V1` subject list. Template requests require exactly the five fixed templates.

Focused tests covered routing authority, catalog and template constraints, evidence bounds, exact output, retry, cancellation, caching, cache invalidation, and safe review behavior. Active documentation and this archive were updated. The complete suite passed. Phase 7 production integration, preview behavior, correction storage, commits, pushes, and real-file evaluation were not performed.
