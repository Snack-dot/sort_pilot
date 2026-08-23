# Sandbox-Only User-File Boundary

Date: 2026-08-23
Repository: `https://github.com/Snack-dot/sort_pilot.git`
Active branch: `architecture-srs-implementation`

## Purpose

This session restricts Sort Pilot's user-file analysis and mutation boundary to `~/Downloads/sandbox` before any logistic-regression training work begins. The training algorithm itself is intentionally out of scope for this session.

## Contents

- `conversation.md` — request and agreed scope.
- `decisions.md` — boundary design and compatibility decisions.
- `evidence.md` — verification performed and environment limitations.
- `implementation-outcome.md` — delivered behavior and remaining work.

## Result

The active app, default classifier adapter, transactional organizer, legacy action executor, and Undo path now reject user files outside the sandbox. Application-owned settings, caches, model artifacts, and history retain their existing local storage locations.
