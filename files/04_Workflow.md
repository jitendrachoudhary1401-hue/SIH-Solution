# OneCase — Workflow

Version: 1.1 | Date: 26 October 2026 | Status: target operating workflow

## 1. Main journey

```text
Officer signs in
  -> searches/selects institution
  -> registers complaint with accountable owner
  -> system saves case and checks possible overlap
  -> authorized reviewer compares candidate cases
  -> officer records action or transfers responsibility
  -> system monitors deadlines and notifies responsible users
  -> authorized officer disposes case with reason
  -> dashboard and action history reflect saved records
```

Every workflow uses the same complaint, institution, user, and event identifiers. UI success follows committed backend state.

## 2. Sign-in

1. Officer submits email and password for a provisioned account.
2. Server validates credentials, account status, and rate limits.
3. Server creates a rotated, expiring session and returns authorized identity/scope.
4. Browser loads the permitted workspace and dashboard.
5. Logout revokes the session and clears identity-specific client cache.

Failure: show a generic authentication error. An expired session redirects to login and does not silently discard a long case form; preserve only safe local draft state according to policy, never credentials.

## 3. Institution selection and registration

**Actor:** authorized bureau officer.

1. Search institution name, internal ID, or verified AICTE Permanent ID.
2. Select the canonical record and inspect visible complaint history.
3. If identity is uncertain, route the institution for authorized verification. Do not link institutions solely on similar names.
4. Enter complaint category, description, receipt date, priority, accountable bureau/officer, and next action. Add a due date only under an identified rule or authorized explicit decision.
5. Upload evidence through the validated private attachment flow.
6. Submit. Server validates scope, fields, institution, owner, and idempotency key.
7. Transaction creates case/reference, status `received`, assignment, creation event, and matching job.
8. Display the saved detail and matching-processing state. Invalidate relevant dashboard/list queries.

Failure: validation leaves no partial complaint. Repeated submission with the same idempotency key returns the original result. Matching failure does not roll back an already saved complaint; the worker exposes retry/failure state.

## 4. Complaint lifecycle

| From | To | Required condition |
| --- | --- | --- |
| `received` | `under_review` | Authorized officer starts examination. |
| `received` | `disposed` | Authorized disposal with recorded reason. |
| `under_review` | `awaiting_information` | Record information requested and next action. |
| `awaiting_information` | `under_review` | Record receipt of information or reason to resume. |
| `under_review` | `disposed` | Authorized disposal with reason and supporting action. |
| `awaiting_information` | `disposed` | Authorized reasoned disposal; no silent timeout closure. |
| `disposed` | `under_review` | Authorized reopening with mandatory reason. |

Registration creates `received`; arbitrary status edits are forbidden. `received`, `under_review`, and `awaiting_information` are active states. Awaiting information does not pause a deadline unless a confirmed, versioned policy explicitly provides that behavior. A transfer does not change status.

## 5. Possible overlap and human decision

**Actors:** background matching worker, authorized cross-bureau reviewer.

1. Worker normalizes text and structured fields, resolves verified institution identity, and selects same-institution candidate records.
2. It creates a Sentence Transformer embedding, retrieves cosine top-k candidates, jointly reranks shortlisted pairs with a Cross-Encoder, and combines normalized model scores with documented structured evidence.
3. It applies calibrated high/uncertain/low triage thresholds and saves run evidence, component/final scores, versions, input revisions, and candidate coverage. High and uncertain bands enter human review; low scores remain machine evidence, not human rejection.
4. Responsible reviewers receive persistent alerts; restricted officers are not shown inaccessible case names or counts.
5. Reviewer opens side-by-side complaints: institution, issue, dates, bureau, owner, current actions, matching evidence, hybrid score, and triage band.
6. Reviewer chooses `related` or `unrelated` and supplies a reason. The pair may remain `pending` until a decision can be made.
7. Backend checks reviewer access to both cases and saves the decision and immutable event.
8. A related decision creates/updates the relationship; both original complaints and ownership records remain separate.

Recalculation never erases earlier decisions. A materially revised complaint may require a separately recorded re-review; it must not silently overwrite the review state. Suggestions are not findings of misconduct and must not trigger automatic disposal or merging.

## 6. Assignment and transfer

**Actor:** authorized bureau lead or officer with transfer permission.

1. Select an active receiving bureau and eligible accountable officer.
2. Enter reason and review current owner/status.
3. Submit the expected complaint version.
4. Server checks scope, recipient eligibility, and freshness.
5. One transaction closes the old assignment, creates the new assignment, updates current owner, records transfer/action history, and enqueues notification.
6. Recipient queue shows the case immediately after commit. Sender sees the transfer receipt; continued case access follows explicit permission policy.
7. Recipient acknowledgement is recorded separately with timestamp and actor.

If a version conflict occurs, reload and ask the officer to review the new state before resubmitting. If notification delivery fails, ownership remains valid and the delivery job retries. Never create a gap with no accountable owner.

## 7. Action and evidence recording

1. Authorized officer opens a case and chooses the permitted action type.
2. Officer enters the action summary, required reason/remark, and next action/date where relevant.
3. Server validates current version and permissions.
4. Save the action and allowed case changes atomically with actor and timestamp generated on the server.
5. Display the new event in case history and recent dashboard activity.

Evidence is available only after validation. Recheck case/document authorization on download. Corrections append a new event referencing the earlier one; successful historical actions cannot be rewritten through the UI.

## 8. Deadline monitoring

1. Authorized policy defines the deadline origin, timezone, elapsed or business-hour calculation, working intervals, holidays, permitted pauses, warning window, and escalation recipients.
2. Store the rule version and calculated due timestamp on the case. Label demo rules visibly.
3. Worker scans active cases with valid deadlines at a configured interval; demo default is once per minute.
4. At the warning threshold, create one approaching-deadline alert per recipient and occurrence.
5. After the due timestamp, create an overdue/escalation event under the applicable rule.
6. Persist alerts and acknowledgement state. Show worker freshness on monitoring views.
7. Disposal stops future active-case alerts. A deadline change supersedes obsolete pending alerts and creates a new rule occurrence.

Reopening does not automatically grant a new deadline; retain or revise it through a recorded authorized policy decision. Missing due dates display “Deadline not set” and do not count as overdue.

### Work queue and bottleneck handling

Sort active cases by descending configured urgency band (overdue, due soon, on track), descending assigned priority, earliest valid due date with missing dates last, oldest receipt, then stable case ID. Show why a case is urgent.

Evaluate versioned rules for assignment/acknowledgement wait, transfer count within a window, and bureau overdue backlog. A flag contains the observed value, configured limit, scope, window, and responsible recipient. These are operational signals for investigation, not findings of fault; they do not change ownership or close cases.

## 9. Dashboard and action history

1. Apply authorized bureau, institution, region, category, and period filters.
2. Server calculates cards and chart series using the PRD metric definitions.
3. Card click opens a case/pair list with identical criteria.
4. Detail links show only permitted records; event expansion shows safe actor/reason/change fields.
5. Display explicit loading, empty, stale, forbidden, and retry states.

## 10. End-to-end acceptance scenario

Use synthetic Institution A, two related fee-return complaints assigned to PGRC and RB, and an unrelated laboratory complaint for the same institution. Register all three, evaluate suggestions, record human decisions, transfer one complaint, trigger a labelled demo overdue rule, record an action, dispose/reopen, and verify the event history and metrics. Demonstrate an unauthorized API attempt and a rejected stale update.

No case must be merged, lost during transfer, or shown as resolved merely because a similarity score is high.

Related: [PRD](01_PRD.md), [Architecture](03_Architecture.md), [Algorithm](05_Algorithm.md), [UI/UX](06_UI_UX_Design.md).
