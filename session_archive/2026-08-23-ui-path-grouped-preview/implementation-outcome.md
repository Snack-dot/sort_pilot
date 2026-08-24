# Implementation Outcome

Status: implemented on local `ui`; AI/UI integration prepared locally and not pushed.

## Delivered

- Merged the current AI work from `architecture-srs-implementation` into `ui`.
- Added `PreviewGroup` and `build_preview_groups` in `sort_pilot/educational_preview.py`.
- Added the path summary showing destination, `파일 N개`, and `대표 파일 외 N개`.
- Added a distinct warning-styled `확인이 필요한 파일` group.
- Removed the flat per-file table from the main preview; summary selection opens a separate on-demand detail dialog.
- Added a Desktop/Downloads selector directly to every path summary row and required a choice before approval.
- Added one top-level Desktop/Downloads selector that applies to every group while preserving per-group overrides.
- Replaced the remaining native-looking preview controls with a consistent card, list-header, combo-box, hover/focus, and primary-action visual system.
- Converted the preview palette to black, white, and neutral grays, including review, focus, selection, and primary-action states.
- Split each path row into a bold destination label and a smaller light-gray representative-file preview.
- Removed the underlying native tree text and increased row height so the two-line custom labels render without overlap.
- Styled Needs Review text in red and excluded that group from bulk Desktop/Downloads assignment.
- Sorted detail-popup files alphabetically and aligned rows, selector columns, text, and move checkboxes to fixed geometry.
- Made every preview combo box click-only by blocking drag selection, drops, and wheel-based value changes.
- Changed the primary action to show the current approved file count.
- Grouped the final frozen-path confirmation using the same representative-file pattern.
- Added pure grouping and live Qt widget tests.
- Updated `docs/FUNCTION_MAP.md` for the new callables.

## Preserved behavior

- Fixed catalog subject and five-template choices.
- Desktop/Downloads destination-root selection.
- Per-file exclusion.
- Collision-resolved exact destination freezing.
- Explicit final approval, transactional execution, personal correction examples, and Undo.

## Not performed

- No remote push.
- No project dependency installation.
