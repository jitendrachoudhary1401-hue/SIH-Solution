# OneCase — Architecture

Version: 1.1 | Date: 26 October 2026 | Status: target implementation design

## 1. Architecture overview

OneCase uses a modular Flask backend, a React TypeScript frontend, PostgreSQL, private document storage, and a background worker. The purpose is to coordinate institution complaints across bureaus while preserving clear ownership and a complete history.

```text
Authorized officer browser
          |
          | HTTPS, same-origin API, secure session cookie
          v
React application / reverse proxy
          |
          v
Flask API
  Authentication and scope checks
          |
  +-------+----------------+------------------+
  |                        |                  |
Case / institution    Overlap review     Dashboard / audit
services              services           query services
  |                        |                  |
  +------------------------+------------------+
                           |
                    PostgreSQL
             domain data + events + jobs
                           |
                     Python worker
             matching / SLA / escalation / alerts

Flask API <---- authorized document access ----> Private storage
```

The browser never connects directly to PostgreSQL or receives private storage credentials. The matching implementation is a backend module, not a separate public AI service.

## 2. Component responsibilities

| Component | Main responsibility |
| --- | --- |
| Frontend | Officer sign-in, dashboard, complaint forms, institution history, overlap comparison, transfers, and action logs |
| Authentication module | Validate credentials, maintain sessions, resolve effective permissions |
| Authorization policy | Enforce bureau/case/field scope before reads, writes, counts, and document delivery |
| Complaint service | Register complaints, validate transitions, assign officers, and record actions |
| Institution service | Resolve institution records and verified AICTE identifiers |
| Transfer service | Change current owner atomically and preserve the transfer history |
| Matching module | Normalize text/fields, embed using Sentence Transformers, retrieve cosine top-k, Cross-Encoder rerank, hybrid-score, and triage same-institution candidate pairs |
| Review service | Save a human decision without merging original complaints |
| Deadline worker | Calculate SLA dates with calendars/pauses, evaluate escalation rules, and create persistent alerts |
| Queue/bottleneck module | Deterministically sort urgent work and flag rule-defined assignment waits, repeated transfers, and overdue backlog |
| Query services | Calculate scoped dashboard counts and retrieve ordered history |
| Private storage | Store attachments outside public web paths |

## 3. Data model

All internal identifiers are server-generated. External AICTE identifiers are stored separately with verification status. Store timestamps in UTC with timezone information.

| Entity | Essential fields and relationships |
| --- | --- |
| `institutions` | ID, name, normalized verified AICTE ID, address, region, verification state |
| `bureaus` | ID, code, display name, active flag |
| `users` | ID, name, email, password hash, account status |
| `roles`, `user_roles`, `user_bureaus` | Role and bureau membership with explicit permission rules |
| `sessions` | Token digest, user ID, issued/expiry timestamps, revocation state |
| `complaints` | ID, unique reference, institution ID, category, description, priority, status, receipt date, due date, next action, current bureau/officer, version |
| `assignments` | Complaint, bureau/officer, start/end timestamps, reason, initiating actor |
| `transfers` | Complaint, previous/new bureau and officer, reason, actor, transfer time, acknowledgement state/time |
| `action_events` | ID, complaint if applicable, actor snapshot, event type, outcome, severity, timestamp, safe changes, reason, request ID, sequence |
| `related_cases` | Canonical pair, latest evidence/run reference, triage band, human review state |
| `matching_runs`, `pair_scores` | Input revisions, embedding/reranker/scoring versions, top-k, raw/normalized scores, structured features, final hybrid score, explanations, processing state and stage latency |
| `complaint_embeddings` | Complaint revision, derived-text digest, model revision, vector/dimension, generation time; never mix model spaces |
| `overlap_reviews` | Pair ID, reviewer, decision, reason, timestamp; prior decisions remain preserved |
| `attachments` | Complaint, storage key, original name, media type, size, checksum, validation state, uploader |
| `notifications` | Event/rule reference, recipient, kind, severity, read/acknowledged state, unique delivery key |
| `deadline_rules`, `sla_pauses` | Versioned timezone/business calendar/holiday/duration rules, warning/escalation settings, demo flag; authorized pause/resume intervals and reasons |
| `bottleneck_flags` | Rule/version, case or bureau scope, evaluation window, observed measure, threshold, evidence event, resolution state |
| `jobs` | Type, payload reference, deduplication key, lease, attempts, next retry, outcome |

### Database invariants

- Foreign keys prevent orphaned complaints, actions, and attachments.
- Complaint reference is unique; a verified external institution ID cannot identify two canonical institutions.
- Each complaint has one current bureau and accountable officer. The current assignment history agrees with these fields.
- Candidate pairs use `case_a_id < case_b_id` and a unique pair constraint.
- `action_events` are append-only through application permissions. Database administration remains a separate trust boundary.
- Complaint version changes on mutations. An outdated client version produces a conflict rather than a silent overwrite.
- Job/notification deduplication constraints enforce retry safety.

Index institution ID, complaint reference, current bureau/officer, status, due date, receipt date, action `(timestamp, id)`, and candidate review state. Verify query plans with the chosen dataset before adding further indexes.

### Required matching data path

```text
Committed complaint revision
  -> normalization + verified institution/field matching
  -> pinned Sentence Transformer embedding
  -> institution-scoped cosine top-k retrieval
  -> pinned Cross-Encoder pair reranking
  -> documented signal normalization + hybrid scoring
  -> configured high / uncertain / low triage
  -> authorized review queue + append-only decision history
```

Persist embeddings and their model/input references in PostgreSQL. A bounded worker cache may accelerate exact retrieval; validate cached revisions before use. Load a coherent model/index snapshot and invalidate it on case edits or model changes. Search and rerank inside the worker; API reads stored results. The required pipeline must not be represented as completed when only TF-IDF has run.

## 4. Transaction boundaries

### Register complaint

In one transaction: validate institution and owner, create complaint, create initial assignment, append creation event, and enqueue a matching job. Commit before returning success. If matching later fails, retain the complaint and show matching as pending/failed with retry visibility.

### Transfer complaint

Check permission and expected version, validate an active receiving officer in the target bureau, close the previous assignment, create the new assignment, update current ownership, append the transfer/event, and enqueue recipient notification in one transaction. The current owner changes at commit. Acknowledgement is a separate event and never leaves the complaint ownerless.

### Change status or review a pair

Validate allowed transition or reviewer access, save the result and reason, append its event, and enqueue relevant alerts in the same transaction. Failed and denied attempts are recorded separately from successful domain changes without secrets.

### Background processing

Workers lease jobs and process them with at-least-once delivery. Unique business keys make repeated processing harmless. Model scoring may happen outside a transaction; before persisting, confirm that compared complaint revisions still match the captured inputs. Retry or supersede stale results.

SLA deadline calculation records policy/calendar revisions and approved pause intervals. Recalculation records a reason and supersedes stale alert occurrences. Bottleneck scans and notifications use unique rule/window/entity keys to avoid repeated flags.

## 5. API boundaries

All routes below are proposed OneCase endpoints, not official AICTE integrations.

| Method and path | Responsibility |
| --- | --- |
| `POST /api/auth/login` | Authenticate provisioned officer |
| `GET /api/auth/me` | Return officer and effective scope |
| `POST /api/auth/logout` | Revoke session |
| `GET /api/institutions` | Scoped institution search |
| `GET /api/institutions/{id}/complaints` | Authorized institution complaint history |
| `GET /api/complaints` | Filtered, paginated case list |
| `POST /api/complaints` | Register complaint |
| `GET /api/complaints/{id}` | Retrieve permitted case fields |
| `PATCH /api/complaints/{id}` | Update permitted ordinary fields with version check |
| `POST /api/complaints/{id}/status` | Controlled status transition |
| `POST /api/complaints/{id}/actions` | Record authorized remark/action |
| `POST /api/complaints/{id}/transfer` | Transfer current ownership |
| `POST /api/transfers/{id}/acknowledge` | Record receiving officer acknowledgement |
| `GET /api/overlaps` | List permitted candidate pairs |
| `POST /api/overlaps/{id}/review` | Record reasoned review decision |
| `GET /api/dashboard/summary` | Scoped metrics and trend buckets |
| `GET /api/notifications` | Current officer alerts |
| `PATCH /api/notifications/{id}` | Save read/acknowledged state |
| `GET /api/complaints/{id}/actions` | Case action history |
| `GET /api/audit-logs` | Separately authorized audit scope |
| `POST /api/complaints/{id}/attachments` | Validate and store evidence |
| `GET /api/attachments/{id}/download` | Recheck access and deliver permitted file |

Use ISO 8601 timestamps, stable identifiers, and consistent validation errors. List responses include `items`, `nextCursor`, `asOf`, and applied filters; include `total` only if actually calculated. Return 401 for missing/expired sessions, 403 for forbidden operations, 409 for stale versions, and structured validation errors for invalid input. Avoid leaking resource existence in restricted lookups.

## 6. Security and operational boundary

Apply authorization before aggregation and serialization. A reviewer must be permitted to see both complaints before comparison details are returned. Use field minimization, CSRF checks, upload validation, private storage, and session revocation. Log actor/action/outcome without credentials or unrestricted document contents, following [OWASP logging guidance](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html).

Health monitoring covers API availability, failed jobs, worker lag, and failed deadline scans. Backups include database and attachment metadata/bytes. Restoration is verified using a synthetic case with its history and attachment.

## 7. Consistency checks

Test transfer rollback, competing officer updates, repeated job delivery, expired sessions, unauthorized cross-bureau reads, stale matching inputs, and counts after disposal/reopening. SQLAlchemy's [version-counter documentation](https://docs.sqlalchemy.org/en/20/orm/versioning.html) informs optimistic concurrency; enforce it on every relevant mutation path, including any bulk operations.

Related: [PRD](01_PRD.md), [Tech Stack](02_Tech_Stack.md), [Workflow](04_Workflow.md), [Algorithm](05_Algorithm.md), [UI/UX](06_UI_UX_Design.md).
