# Verification record

This file records observable checks for the local implementation, not production certification.

## Backend

The pytest suite checks sessions/expiry/logout/CSRF, same-origin writes, rate limits, bureau and owner authorization, administrator denial, idempotent creation and rollback, stale versions, lifecycle transitions, scoped counts/export/pagination, protected uploads/downloads, atomic transfer/acknowledgement, deduplicated monitoring, SLA arithmetic/pauses, worker failure without a baseline fallback, persisted matching evidence/review decisions, and database/evidence backup restoration.

Deterministic injected model doubles isolate pipeline transaction tests. Separate evaluation and browser tests use the actual downloaded embedding and Cross-Encoder models.

## Real-model demonstration

The eight-record local seed produced:

| Pair | Actual hybrid score | Band |
| --- | --- | --- |
| Fee-refund complaints 1 / 2 | 0.903 | High relevance; human review required |
| Fee-refund / laboratory complaints 1 / 3 | 0.202 | Low |
| Fee-refund / laboratory complaints 2 / 3 | 0.210 | Low |

The unverified institution's complaint exposes a failed processing state; the worker does not establish institution identity by similar name. These results describe synthetic examples only. Full model revisions, configuration, latency and small held-out comparison metrics are in `evaluation.json` and local database run records.

## Browser verification

Playwright covers sign-in, registration with a business calendar, case action/history, disposal and reopening, cross-bureau transfer, recipient acknowledgement, navigation, dark theme, expanding history, institution history, direct API denial, mobile navigation focus/escape handling, and no document overflow at 360/768/1440px. With `E2E_MATCHING=1`, the reviewer comparison and related-decision journey uses real model outputs.

## Operational limits

Local tests use SQLite. PostgreSQL/Compose execution, concurrent-worker guarantees, PostgreSQL backup recovery, multilingual model quality and the proposed 10,000-case latency target have not been verified in this environment. The CSS login decoration works without WebGL. Reduced motion disables animation. Keyboard and responsive checks do not establish complete WCAG 2.2 AA conformance.
