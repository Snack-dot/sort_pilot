# Decision Record

## D1 — Preserve the AI branch's active contracts during integration

The AI branch versions of conflicting classifier, history, organizer, application-controller, and preview files were selected because they contain the active two-axis educational workflow, immutable organization plans, JSON history migration, and exact-path execution. The older UI branch's flat preview workflow was not allowed to replace those contracts.

## D2 — Use a summary with on-demand separate details

The preview displays only destination groups. Each row contains the relative destination, file count, and a deterministic alphabetical representative filename plus the remaining count. The flat table is not rendered beneath the summary. Clicking a group opens its per-file root, subject, template, and inclusion controls in a separate dialog.

## D3 — Keep Needs Review separate and last

Any output with an unresolved subject or template is grouped under `확인이 필요한 파일`, styled as a warning, and sorted after resolved destination groups.

## D4 — Group the final confirmation too

The final confirmation groups frozen exact destinations by parent folder and shows one exact representative path plus the remaining count. Exact collision-resolved paths are still frozen before execution.

## D5 — Select the root once per path group

Each summary row includes an explicit `바탕화면`/`다운로드 폴더` selector. The choice applies to every included file in that group, and final approval is blocked until all included groups have a root selection.

## D6 — Provide one bulk root choice

One top-level `전체 옮길 위치` selector applies Desktop or Downloads to every summary group and hidden file row. Per-group selectors remain available for exceptions, and the bulk selector returns to its unresolved state when group choices become mixed.

## D7 — Replace native-looking controls with one restrained visual system

Keep the accepted slate-and-blue palette while presenting the bulk action as a card and applying consistent radii, spacing, hover/focus states, header treatment, and primary/secondary button hierarchy across the dialog.

## D8 — Use a monochrome palette

Replace blue and orange accents with black, white, and neutral grays. Use black for the primary move action and focus borders, with light gray for hover and selection feedback.

## D9 — Separate path and file-preview hierarchy

Render each destination path as a bold dark label and its representative-file summary directly beneath it in smaller light-gray text, while preserving the row as one clickable group.

## D10 — Keep Needs Review outside bulk destination changes

Render the Needs Review row in red and exclude it from the top-level destination action. Its destination remains unresolved until the user handles that group explicitly.

## D11 — Keep detail rows deterministic and geometrically aligned

Sort files alphabetically in the on-demand detail dialog and use fixed control columns, 46-pixel rows, vertically centered text, and centered move checkboxes so native widget sizes cannot distort the table.

## D12 — Make combo boxes click-only

Use one combo-box subclass throughout the preview that rejects drag selection, drag/drop, and wheel-based value changes. Leave the surrounding summary and detail table behavior unchanged.
