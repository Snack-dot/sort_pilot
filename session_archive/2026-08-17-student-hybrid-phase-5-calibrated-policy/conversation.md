# Conversation Reconstruction

Date: 2026-08-17 (Asia/Seoul)

The user instructed the assistant to continue after Phase 4. Before editing Phase 5 behavior, the assistant read `docs/AGENTS.md`, `README.md`, the supreme plan, the newest Phase 4 archive, Git status, and recent commits.

Phase 5 was confirmed as the first unfinished phase. Its exact requirement is to calibrate per-axis local acceptance, Gemma escalation, and abstention thresholds using held-out data.

The assistant audited the existing `RoutingThresholds`, `route_axis`, Phase 2 evaluation data, tests, and threshold references. The current educational policy contains provisional example values only in tests. A legacy classifier function uses a `0.97` accuracy floor, but that function is outside the supreme educational plan and cannot silently define Phase 5.

The supreme plan does not state the minimum held-out precision required for local acceptance or the held-out plausibility level that separates Gemma escalation from Needs Review. Because the user previously required the assistant to stop and ask whenever the plan does not provide an answer, no numerical thresholds or held-out operating targets were invented. The assistant asked the user to specify or approve them.

The user answered: local at 90% and Gemma at 50%. These became the exact Phase 5 operating targets for both axes, with thresholds derived independently for subject and template.

The assistant added a new 50-case made-up held-out corpus. It contains no repeated filename/text pair from the Phase 2 corpus, covers all 18 catalog subjects and all five templates, and was not used to create or revise profiles.

The existing cache-only E5 classifiers produced subject and template raw scores and margins for each case. The calibration code exhaustively searched observed score and margin values. It selected the broadest authoritative local region meeting 90% precision, then the broadest remaining Gemma-escalation region meeting 50% top-label accuracy. Explicit abstention and scores below the escalation threshold remain Needs Review.

The derived subject policy accepted 7 cases with 7 correct, escalated 32 cases with 16 correct, and reviewed 11. The derived template policy accepted 49 cases with 46 correct, escalated one correct case, and reviewed none. The packaged policy was then reproduced and verified exactly by a second cache-only run.

Focused calibration and documentation tests passed. Complete-suite and final repository verification are recorded in `evidence.md`. No Phase 6 behavior, production integration, commit, or push was performed.
