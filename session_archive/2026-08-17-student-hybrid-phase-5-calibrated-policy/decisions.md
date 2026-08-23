# Phase 5 Decisions So Far

- Subject and template thresholds must be calibrated independently.
- Calibration data must be held out from profile creation and profile wording changes.
- Only made-up held-out cases and labels may be tracked.
- Any held-out calibration involving real local material must stay under Git-ignored `eval/local/` and must never be uploaded.
- Explicit local abstention always routes to Needs Review.
- High-score, sufficient-margin local decisions are authoritative and cannot be overridden by Gemma.
- Plausible but ambiguous evidence routes to Gemma escalation.
- Insufficient evidence routes to Needs Review.
- Raw score must not be called probability.
- The legacy classifier's `0.97` default is not authoritative for this educational plan.
- The user-approved local-acceptance target is 90% held-out precision.
- The user-approved Gemma-escalation target is 50% held-out top-label accuracy.
- Subject and template use the same approved targets but receive independently derived raw-score and margin thresholds.
- Threshold candidates come only from observed held-out raw scores and margins.
- Selection maximizes the number of authoritative local decisions first, then Gemma escalations, while both approved targets remain satisfied.
- The new 50-case held-out corpus must not be used to revise profiles.
- The centralized policy stores targets and thresholds, not held-out filenames or text.
- The Phase 4 evidence weights remain neutral; Phase 5 calibrates the three routing thresholds named by the supreme plan.
