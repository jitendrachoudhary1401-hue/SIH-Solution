# OneCase — Product Requirements Document

Version: 1.1 | Date: 26 October 2026 | Problem statement: SIH26264

Status: proposed implementation specification, not an account of an existing deployed system or official AICTE policy.

Algorithm authority: user-selected `AICTE_ACITS_Algorithms.md`. OneCase is the product name used here; ACITS in the reference denotes the same complaint coordination project. Its Hybrid Semantic Complaint Matching pipeline is required for the target implementation. TF-IDF is a research baseline, not the final matching engine.

## 1. Product purpose

OneCase is an officer-facing platform for monitoring institution-related complaint cases across AICTE bureaus and cells, including the Regulation Bureau (RB) and Public Grievance Redressal Cell (PGRC). It connects institution identity, complaint ownership, possible overlaps, deadlines, actions, and reports in one authorized workspace.

The core problem is coordination: officials need to know whether another bureau is working on a related issue, who currently owns each complaint, what has happened, and what requires action next. These are design problems inferred from the project brief, not verified claims about deficiencies in current AICTE systems.

## 2. Goals and success criteria

| Goal | Acceptance evidence |
| --- | --- |
| Consolidate institution history | A verified institution lookup returns all complaints the officer is permitted to see, across participating bureaus. |
| Make ownership unambiguous | Every active case has one current bureau and one accountable officer; transfer tests preserve this invariant. |
| Surface possible overlap | Labelled related pairs are evaluated; suggestions include scores and reasons for human review. |
| Preserve accountability | Successful case mutations and action events commit atomically and survive restart. |
| Expose delays | Configured approaching/overdue cases produce persistent, deduplicated alerts. |
| Produce trustworthy analytics | Dashboard counts and report exports reconcile with scoped complaint queries. |
| Protect access | Negative API tests block unauthorized cases, documents, counts, and audit fields. |

No accuracy, latency, availability, or operational improvement is claimed before measurement.

## 3. Users and proposed access model

Permissions combine a role, bureau membership, case assignment, explicit collaboration grants, and field sensitivity. Default is deny. Role names below are proposed project defaults.

| Persona | Default capability |
| --- | --- |
| Bureau officer | Register and handle permitted cases in the officer's bureau; act on assigned cases. |
| Bureau lead | Assign and transfer cases within authorized scope; review bureau workload. |
| Cross-bureau reviewer | Compare explicitly authorized candidate cases and record relationship decisions. |
| Executive viewer | View approved aggregate reports; detailed case access requires a separate grant. |
| Auditor | Read approved audit scopes and exports; cannot change case outcomes. |
| System administrator | Manage users, roles, configuration, and operations; no automatic access to sensitive complaint content. |

An account may hold multiple roles. Account provisioning is administrative or invitation-based; public self-registration does not grant officer access.

## 4. Scope and priorities

### P0 — core release

| ID | Requirement | Observable acceptance |
| --- | --- | --- |
| FR-01 | Officer authentication and server-enforced authorization | Login, refresh, expiry, logout, and forbidden API tests pass. |
| FR-02 | Institution directory and identity verification | Internal institution IDs remain stable; unverified external identifiers cannot trigger automatic identity linking. |
| FR-03 | Complaint registration and detail | Server creates a unique reference, validates required fields, and persists owner and initial event. |
| FR-04 | Controlled status lifecycle | Invalid transitions fail; disposal and reopening require reasons. |
| FR-05 | Assignment and transfer | Transfer changes current ownership atomically and records sender, receiver, reason, and timestamp. |
| FR-06 | Action history and restricted audit | Authorized history remains readable after transfer and restart, subject to explicit visibility policy. |
| FR-07 | Hybrid Semantic Complaint Matching and review queue | Normalization and institution matching lead to Sentence Transformer embeddings, cosine/top-k retrieval, Cross-Encoder reranking, structured hybrid scoring, and configurable triage. Related/unrelated decisions preserve both original complaints and review history. |
| FR-08 | Deadline monitoring and alerts | A repeat worker run does not create duplicate alerts for the same rule occurrence. |
| FR-09 | Scoped dashboard and search | KPI drill-downs match the selected authorized records. |
| FR-10 | Protected document handling | Upload validation and authenticated downloads reject unauthorized access. |
| FR-11 | Priority worklists and bottleneck flags | Queues sort by urgency, overdue state, priority, and due date; configured long assignment waits, repeated transfers, and overdue backlogs are flagged with reasons. |
| FR-12 | Matching evaluation | Compare exact rules, TF-IDF, semantic retrieval, and the required hybrid/reranked approach using held-out labels, precision, recall, F1, false-positive rate, recall@k, and measured latency. |

### Scope boundary

This specification covers the main officer-facing complaint coordination solution only. It does not add public registration, unrelated AI features, external AICTE integration, or the reference's optional graph visualization. Matching uses the required hybrid pipeline in the algorithm document.

## 5. Canonical business rules

- Institution and complaint are separate entities. A shared institution does not prove two complaints are related.
- Complaint statuses: `received`, `under_review`, `awaiting_information`, `disposed`.
- Active means any status except `disposed`. Reopening is a recorded transition from `disposed` to `under_review`.
- Transfer is an ownership event, overdue is a computed deadline condition, and overlap is a relationship review. None is a complaint status.
- Every complaint has a current bureau and accountable officer. Registration must select a valid owner; do not silently leave a case unowned.
- Ownership changes immediately when a validated transfer commits. Recipient acknowledgement is tracked separately; lack of acknowledgement never makes the case disappear.
- Deadline rules are configurable. Demonstration rules are labelled illustrative; no official timeline is invented.
- System-generated matching suggestions never merge, dispose, or change the owner of a complaint.
- Hybrid scores combine documented normalized semantic, reranker, and structured signals. Weights, top-k, and triage thresholds are selected on labelled validation data; scores are not probabilities of duplication.
- SLA calculations use versioned timezone/calendar/business-hour/holiday/pause rules. A pause requires a permitted recorded event and never follows automatically from a status label.
- Corrections to historical actions are new events referencing the original. Ordinary users cannot edit/delete action history.
- Application-level append-only history is not a claim of cryptographic tamper resistance.

## 6. Principal user stories

1. An officer registers a complaint against a selected institution and sees a permanent case reference and owner.
2. A reviewer compares two differently worded complaints from RB and PGRC, reads the matching evidence, and records a reasoned decision.
3. A lead transfers a case and confirms that the recipient queue, action history, and dashboard reflect the saved owner.
4. An officer receives an approaching-deadline alert and records the next action.
5. An executive filters the dashboard by bureau and date and drills into a permitted case list.
6. An auditor follows the action sequence and exports only the approved scope.

## 7. Reporting definitions

| Metric | Definition |
| --- | --- |
| Total complaints | Distinct complaint IDs in authorized scope, filtered by receipt date when a receipt period is selected. |
| Active complaints | The same cohort whose current status is not disposed. |
| Overdue complaints | Active cohort members with a due timestamp earlier than the report `asOf`. |
| Awaiting overlap review | Distinct pending candidate pairs with both cases authorized; include pairs where at least one case belongs to the filtered cohort. Label as pairs. |
| Confirmed overlaps | Distinct human-confirmed related pairs in authorized scope; never count machine high-relevance pairs as confirmed. |
| Received series | Distinct complaints received in each weekly bucket, using chart-period filters. |
| Disposal series | Disposal events in each bucket; a reopened and subsequently disposed complaint produces another event. Label as disposal events. |
| Ageing | Active cases grouped by elapsed time since receipt at `asOf`; bucket boundaries are explicit. |
| Resolution duration | Time between start and disposal of a defined lifecycle episode; reopened episodes are distinguished. |
| SLA compliance | Eligible disposed episodes completed within the applicable versioned deadline, divided by disposed episodes with known applicable deadlines; report exclusions and period. |

Dashboard snapshot cards and event-throughput charts answer different questions. Their subtitles must explain receipt-cohort versus event-period scope. Historical snapshots require historical reconstruction; current-state data must not be presented as a past snapshot.

## 8. Nonfunctional requirements

- Use UTC persistence and timezone-aware API timestamps; default presentation/reporting timezone is Asia/Kolkata.
- Support keyboard access, labelled controls, visible focus, reduced motion, and a target of WCAG 2.2 AA subject to actual verification.
- Protect credentials with password hashing, secure deployment cookies, session revocation, CSRF controls, and rate limits.
- Apply row/field authorization before aggregation, pagination, facets, and export.
- Use transactional writes, concurrency checks, durable job retries, backups, and tested restoration.
- Proposed demo performance target: p95 filtered reads below 1 second and match completion below 10 seconds on a documented 10,000-complaint synthetic dataset and documented hardware. These are test targets, not results or production SLAs.
- Record application health and worker lag without logging secrets or unrestricted complaint text.

## 9. Delivery stages and release gate

1. Foundation: schema, migrations, seeded synthetic institutions, officer access, permission tests.
2. Case lifecycle: registration, detail, assignments, actions, documents, transfers.
3. Coordination: exact/TF-IDF baselines, required semantic top-k retrieval, Cross-Encoder reranking, hybrid triage, review queue, decisions, and notifications.
4. Monitoring: SLA/calendar calculations, escalation jobs, priority queues, bottleneck flags, dashboard, and filters.
5. Verification: end-to-end demonstration, matching evaluation, accessibility checks, backup/restore exercise.

Release gate: create a PGRC complaint, create a differently worded RB complaint, review the suggestion, transfer one case, trigger an illustrative deadline alert, dispose and reopen a case, and demonstrate consistent history and counts. Also demonstrate a denied direct API request.

## 10. Dependencies and open decisions

Authority must confirm official institution identifiers, bureau hierarchy, roles, retention policy, deadline rules, reopening authority, cross-bureau field access, SSO, and production hosting. Until confirmed, use labelled demo policies and synthetic records. No real credentials or complaint data belong in seeds or documentation.

## 11. Related specifications and sources

- [Tech Stack](02_Tech_Stack.md), [Architecture](03_Architecture.md), [Workflow](04_Workflow.md), [Algorithm](05_Algorithm.md), [UI/UX Design](06_UI_UX_Design.md).
- User-provided `SIH26264_Research_Papers_and_Websites.pdf` and earlier complaint-dashboard analysis; treated as project reference material, not independently verified official policy.
- [Sentence-BERT paper](https://arxiv.org/abs/1908.10084) supplies research context for the required semantic-matching implementation, not evidence of OneCase performance.
