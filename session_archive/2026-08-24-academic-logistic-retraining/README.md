# Academic logistic retraining logs

This directory preserves the model-training events recovered from the local Codex session logs. Times use Asia/Seoul (UTC+09:00).

The `raw/` directory contains the complete source JSONL session logs, including unrelated conversation and Codex application metadata. The two filtered `.log` files retain only the training commands, progress milestones, completion status, artifact behavior, and report verification needed for a quick model-history audit.

## Source-log integrity

| Source session | SHA-256 |
| --- | --- |
| `rollout-2026-08-23T19-08-55-01a02e18-3c5f-76f3-a7d9-3cd5a6e17c13.jsonl` | `9FD4CB1818D63765063410EC24F748FA235526B609D1C16D3F6EDB6D587028FE` |
| `rollout-2026-08-24T12-36-05-01a031d6-f1ff-72f2-8290-73f2ee5824b7.jsonl` | `7614679BACE4198ECB409552A1695770E180361D9BF94286EB741642FD290A17` |
| `rollout-2026-08-24T15-48-22-01a03286-fece-7d22-b7f4-e027ac26f71f.jsonl` | `E8E5605292CCE245983F2C8FD563BAEC65844733A07E699D5546EB5D2C659807` |

## Artifact behavior

Every completed run wrote atomically to `Downloads/sandbox/.sort_pilot_state/logistic`. The trainer used fixed artifact names and did not create versioned backups. A successful run therefore replaced the preceding model bundle; interrupted or failed runs did not replace it.
