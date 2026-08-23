# Decision Record

## D1 — Preserve the AI branch's active contracts during integration

The AI branch versions of conflicting classifier, history, organizer, application-controller, and preview files were selected because they contain the active two-axis educational workflow, immutable organization plans, JSON history migration, and exact-path execution. The older UI branch's flat preview workflow was not allowed to replace those contracts.

## D2 — Use a summary-plus-filtered-detail layout

The preview displays destination groups first. Each row contains the relative destination, file count, and a deterministic alphabetical representative filename plus the remaining count. Selecting a group filters the existing detailed table instead of removing it, retaining per-file root, subject, template, destination, and inclusion controls.

## D3 — Keep Needs Review separate and last

Any output with an unresolved subject or template is grouped under `확인이 필요한 파일`, styled as a warning, and sorted after resolved destination groups.

## D4 — Group the final confirmation too

The final confirmation groups frozen exact destinations by parent folder and shows one exact representative path plus the remaining count. Exact collision-resolved paths are still frozen before execution.
