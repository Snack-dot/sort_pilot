# Decision Record

## D1 — One resolved user-file root

`~/Downloads/sandbox` is the default and only active user-file root. Paths are expanded and resolved before containment checks so sibling-prefix paths and existing symlink escapes are rejected.

## D2 — Enforce at entry and mutation layers

The app validates scan and analysis inputs, while the organizer validates the complete operation batch before the first move. This prevents a future UI, training command, forged plan, or stale history entry from bypassing the boundary.

## D3 — Undo is not exempt

Undo validates recorded sources, destinations, and created directories before changing anything. Older history that references Desktop, Downloads, or another location is rejected rather than replayed.

## D4 — Preserve injectable test roots

Low-level constructors and move functions accept an explicit sandbox root for isolated tests. Production defaults remain `~/Downloads/sandbox`.

## D5 — Internal application state remains local

Settings, caches, model artifacts, SQLite/JSON state, and the process lock remain in established local application-data paths. The sandbox rule protects user documents; it does not relocate private application internals or upload anything.
