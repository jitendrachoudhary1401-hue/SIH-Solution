# OneCase — Identity Verification and Complaint Separation Changes

Version: 1.0 | Date: 26 October 2026 | Project: SIH26264

Document type: implementation brief for the agent working in the application repository. This file specifies changes to implement and test. It does not claim those changes already exist in the application.

## 1. Requested outcome

Improve the database, verification process, matching algorithm, and interface so that:

1. Different people with the same name, state, city, or locality remain separate.
2. A person who changes address does not become a different person automatically.
3. Different complaints at the same institution/place are not treated as the same problem merely because their wording or category is similar.
4. Multiple people affected by a common issue can have related complaints without losing separate identities, evidence, requested relief, ownership, and histories.
5. Verification records show exactly what was checked; a contact OTP does not become a claim of verified legal identity or proven allegation.
6. The required semantic retrieval, Cross-Encoder, hybrid scoring, and human review pipeline remains in place with better issue-level evidence and safeguards against false links.

Keep these changes inside existing intake, complaint detail, overlap review, and administration workflows. Do not build unrelated portals, a new identity-provider product, or automatic complaint merging.

## 2. Inspect and map before implementation

In the actual repository, inspect the schema/models, migrations, authentication, complaint intake, source import, institution/campus directory, matching jobs, review decisions, permissions, and tests. Map the names below to existing equivalents instead of creating duplicate tables or services.

Preserve working routes, historical records, the selected stack, and the four internal statuses: `received`, `under_review`, `awaiting_information`, `disposed`. Read the existing OneCase specifications and apply this brief as a refinement of the main solution.

Acknowledge any incompatible current design in the implementation report and resolve it with an additive migration where possible. Do not reset the database or infer missing identities from names during backfill.

## 3. Fundamental separation rules

| Concept | Identity rule | Must not be used as a substitute |
| --- | --- | --- |
| Login account | Authentication identity with server-assigned account ID | Complainant record or proof of allegation |
| Person | Stable internal person ID | Name/address/phone combination |
| Contact channel | Person-associated address/number with its own verification | Unique real-world identity |
| Institution | Canonical internal ID and verified external identifier | Display name or postal address alone |
| Campus | Institution-linked location with verification provenance | Every institution sharing a city |
| Complaint | Unique saved case ID/reference | Person ID, text fingerprint, or institution ID |
| Complaint issue | One distinguishable alleged problem inside a complaint | Broad category or embedding alone |
| Incident reference | Reviewed event/context linkage, when established | An automatically inferred common incident |
| Related pair | Reviewed relationship between records | Database row deduplication or case closure |

Names and addresses are search/display fields, not unique keys. Two people may legitimately share a household phone or email contact. Unique login credentials may remain unique in the authentication system without imposing that restriction on all external complainants.

## 4. Schema changes

Use server-generated opaque primary keys, foreign keys, timestamps, explicit source/provenance, and revision tracking. The table names below are proposed logical names; implement equivalent normalized entities in the repository.

### 4.1 Persons and contact verification

| Entity | Required fields and behavior |
| --- | --- |
| `persons` | ID, recorded display/full name, person-record state, created/updated timestamps, version. Allow identical names. Do not use one misleading global verified boolean. |
| `person_contacts` | ID, person ID, contact type, normalized value, purpose/source, current state, verification method/time, expiry/revocation if applicable. Protect sensitive values. Shared contact values are permitted. |
| `identity_claims` | ID, person ID, claim type, issuing organization ID, scoped identifier where approved, source/evidence reference, validity period, recorded state. A student/employee number is scoped to its issuer and identifier namespace. |
| `identity_verifications` | ID, person ID and optional claim/contact ID, check type, method, outcome, reviewed evidence reference, actor/service identity, timestamp, validity, reason, and revocation/superseding reference. |
| `person_locations` | Person ID, location/address record, relationship type, effective interval, recorded source, and whether self-declared or checked. Keep historical addresses rather than overwriting identity. |

Reuse an existing organization directory for identity issuers, or add the minimal issuer entity needed to distinguish institution, university, and other approved issuers. Never accept a client-provided verified state.

Do not collect Aadhaar, biometrics, or broad identity-document bundles by default. Select the minimum authorized verification method required for the specific process. Encrypt/restrict approved sensitive identifier values; do not put them in URLs, logs, model text, or public fixtures.

### 4.2 Geography and institution identity

| Entity | Required fields and behavior |
| --- | --- |
| `locations` or equivalent | Country/state/district/city/locality text and official codes where available, postal information, source, verification state. Missing subdivisions remain unknown; do not fabricate a code. |
| `institutions` | Existing canonical institution ID and external identifier verification. Same/similar institution names are allowed when identifiers differ. |
| `campuses` | Campus ID, institution ID, name, location reference, verification state and source. One institution may have several campuses. |

Record complainant residence, institution/campus location, and incident location as different relationships. The place where a person lives must not silently determine the institution complained against or the competent bureau.

Official-code uniqueness, if used, is scoped to its issuing code system and geographic level. A postal code or locality name does not identify a person or institution.

### 4.3 Complaint participation and individual issues

| Entity | Required fields and behavior |
| --- | --- |
| `complaint_participants` | Complaint ID, person ID, participant role (affected person, submitter, representative, witness, or permitted respondent contact), source and validity. Support multiple affected people. |
| `representative_authorizations` | Representative, represented person(s), case scope, authorization basis/evidence, effective/expiry/revocation, and permitted communication/disclosure scope. A shared surname or contact proves no authorization. |
| `complaint_sources` | Complaint, source system/organization namespace, source reference, original receipt timestamp, imported timestamp, payload digest, and import provenance. Preserve multiple genuine source references. |
| `complaint_issues` | Issue ID, complaint ID, controlled category/subcategory, issue summary/description, relevant campus/incident location, incident start/end and precision, requested relief, revision, and recorded source. Every new complaint has at least one issue. |
| `issue_evidence` | Issue ID and protected attachment/evidence ID, relevance note, actor and timestamp. One file may support several issues through explicit links. |
| `incident_records` and `issue_incident_links` | Optional reviewed event record and its authorized issue links, with reviewer, basis, uncertainty, and correction history. Do not auto-create a shared incident merely from text similarity. |

A complaint containing fee-refund and certificate-retention issues must support both issue records without silently splitting, deleting, or merging the original complaint. Display any related finding at issue level. One issue being addressed must not automatically dispose the parent complaint while another remains unresolved under the applicable policy.

Use the existing protected evidence store; do not create unprotected identity/evidence copies.

### 4.4 Matching and human relationship records

- Extend existing matching inputs/embeddings with issue ID, issue revision, institution/campus context, derived-text digest, and model revision. Reuse the current embedding table where practical.
- Extend pair-score evidence to retain the particular issues compared, their input revisions, known/missing contextual features, raw/normalized neural scores, effective weights, triage band, explanation, and model/scoring version.
- Keep existing canonical complaint-pair records, but attach one or more issue-pair findings. A case-level badge must show which issue is potentially related.
- Human decisions remain `pending`, `related`, or `unrelated`. For a `related` decision, record a reviewed relation kind such as `related_issue`, `same_incident`, or `possible_duplicate`, plus reason and reviewed scope. These labels do not merge records.
- Preserve decisions and corrections as events. Store identity-resolution decisions separately from complaint-relationship decisions.

## 5. Constraints and database integrity

1. Primary keys identify records, not display names. Index normalized names for search without declaring them unique.
2. Use unique complaint references and scoped source-reference constraints where that source guarantees uniqueness. Same reference text from two different source namespaces is not a collision.
3. An issuer-scoped identifier may need a validity period because identifiers can be reused. Apply verified-claim uniqueness only within the confirmed issuer/type/time semantics. Conflicting claims enter review; do not automatically combine people.
4. Validate date ranges and preserve unknown precision. Reject an end before a start; do not substitute receipt date for unknown incident date.
5. Ensure selected campus belongs to the complaint's institution. Prefer a suitable composite foreign key or equivalent database-enforced design rather than an unchecked client field.
6. Validate person/contact/claim associations and complaint/issue/evidence associations. A foreign key proving an object exists does not itself prove that its case scope is correct.
7. Canonically order relationship pairs, forbid self-pairs where appropriate, and enforce uniqueness under concurrency. Version individual score runs separately from the durable pair.
8. Keep successful identity decisions, issue changes, verification events, and relationship decisions transactional with their audit records.
9. Preserve one internal accountable bureau/officer per complaint; an identity or matching update must not reassign ownership.
10. Use row versions and idempotency keys on repeated/conflicting mutations. Do not use same text, address, contact, or attachment hash as a unique complaint key.

Use actual database constraints for the invariant where possible. PostgreSQL CHECK constraints are not a substitute for cross-row consistency checks; select foreign-key/unique/exclusion constraints or carefully tested transactional logic as appropriate. [PostgreSQL constraints reference](https://www.postgresql.org/docs/current/ddl-constraints.html).

## 6. Verification process

### A. Create or select the person record

Look up a trusted existing reference when available. If only a name/contact/address resembles an existing record, present a restricted possible-match review instead of automatically attaching the new complaint to that person. Create a separate provisional record when identity cannot safely be established.

Do not expose another person's full details while attempting to disambiguate. If a record is entered by an officer from correspondence, do not falsely claim that the complainant authenticated directly.

### B. Verify specific claims

Track each check independently:

- Contact control: approved OTP/link or documented contact check, where supported.
- Institutional affiliation: approved source or issuer-scoped student/employee record.
- Representative authority: recorded case-specific basis.
- Institution/campus identity: verified directory/identifier evidence.
- Documentary evidence authenticity: separate authorized assessment where needed.

Contact control does not prove legal identity, employment, authority to represent another person, or the truth of allegations. A matching name on an uploaded file is not sufficient proof.

### C. Resolve uncertainty

Use check outcomes such as pending, passed, failed, expired, revoked, and needs-review. Record method, source, reviewer, date, and reason. High-risk conflicts require authorized manual review. Do not let missing optional identifiers or a matching person name automatically reject an otherwise admissible complaint.

Do not perform person consolidation automatically. Any permitted correction/consolidation needs a reviewed source-to-canonical mapping, preserved original references, conflict checks, reversal strategy, and append-only history. The default implementation can leave uncertain records separate.

## 7. Required improvements to overlap detection

Retain the selected algorithm; refine its evidence granularity:

```text
Complaint intake
 -> preserve person and source identity independently
 -> verify institution/campus context
 -> record one or more distinguishable complaint issues
 -> normalize issue text and retain incident-date precision
 -> Sentence Transformer embeddings per issue
 -> institution-scoped cosine top-k retrieval
 -> Cross-Encoder pair comparison
 -> hybrid scoring with known issue/event evidence
 -> high / uncertain / low machine triage
 -> authorized issue-scoped human decision
 -> separate complaint records and audit history
```

### Features and decision safeguards

- Same name, state, city, locality, or residence is never sufficient for person identity or complaint relationship.
- Institution identity remains an eligibility gate for this pipeline, not a score bonus or proof of duplication.
- Compare issue, action complained of, known incident period, applicable campus/context, affected cohort, reference documents, and requested relief where available and authorized.
- Same broad category is weak evidence; fee complaints can concern different amounts, policies, dates, people, or incidents.
- Known contrary context must be shown. Missing context is unknown, not agreement and not automatic disagreement.
- Different campuses or dates can still concern a common central policy/continuing event. Do not blanket hard-block these without validated rules.
- Different complainants can be affected by the same incident. Their person IDs must not become a hard rule making related issues unrelated.
- Do not add personal names, phone numbers, home addresses, or sensitive identity identifiers to semantic text just to increase matching strength.
- Retrieve candidates per issue and preserve shortlist provenance. Evaluate recall@k and workload after this change; do not silently expand inference without limits.
- A high text or hybrid score only prioritizes review. It cannot establish that two issues are the same event.
- Case summaries must distinguish “one potentially related issue” from “all allegations are duplicates”. Never inherit a relation across every issue of a multi-issue complaint.
- Ground-truth labels and thresholds require held-out evaluation. Do not promise zero false positives or a fixed accuracy percentage.

## 8. Repeat requests, repeat reports, and related problems

| Situation | Correct behavior |
| --- | --- |
| Network retry of the same submitted request | Idempotency returns the same saved result for the same actor/operation/key and payload digest. |
| Same person files a genuinely new issue | Create a separate complaint/issue record. |
| Same source record is imported again | Apply source-scoped idempotent import/update rules and preserve versions. |
| Similar complaint arrives through another channel | Preserve source provenance and require reviewed linkage; do not silently drop it. |
| Two people share name/address/contact | Keep identities separate unless stronger authorized evidence establishes identity. |
| Several people report the same incident | Preserve each person's case/standing and link authorized related issues. |
| One institution has unrelated fee and laboratory complaints | Keep issues and cases separate; no relation from place alone. |

## 9. API/service changes

Adapt existing APIs instead of adding duplicate route families. Required capabilities are:

- Person record creation/selection with scoped disambiguation and no name-based auto-link.
- Recording individual verification checks; server-only state transitions with evidence and permission.
- Multiple complaint participants and valid representation links.
- Issue create/update operations with institution/campus/date validation and revision increments.
- Source-scoped import/idempotency handling.
- Issue-level matching jobs and safe, permission-filtered candidate explanations.
- Human review of the selected issue pair with a reason, relation kind where related, and immutable decision history.
- Authorized correction flows that preserve previous references and recheck affected matching evidence.

Server requests must not accept trusted person verification, reviewer identity, score, or final relationship state merely because a client sends it. Authorization applies before searches, facets, duplicate warnings, case counts, and disclosure of possible identity matches.

## 10. UI changes

**Intake:** show affected person, submitter/representative, complainant location, institution/campus, incident location, and issue details as separate fields. Use contextual suggestions without exposing other people's cases. Permit more than one issue and explicitly unknown incident dates.

**Verification panel:** show what was checked and by whom, with pending/expired states. Use specific badges such as “contact checked” or “institution record verified”; avoid a single “verified person” badge that implies unrelated checks passed.

**Complaint detail:** retain a stable case reference and display participants, individual issues, incident context, source records, and separate histories. Mask sensitive identity details.

**Overlap review:** compare the specific issues, not just college names and full-document scores. Show agreement, contradiction, and missing data side by side. Ask for an explicit reason before linking; preserve manual lookup for missed candidates.

**Location filters:** support institution and incident geography separately from complainant residence. Missing locations must not be silently assigned to a guessed city or state.

## 11. Migration and implementation sequence

1. Inventory current data, schema constraints, read/write APIs, and matching contracts.
2. Add normalized identity/participant/location/issue/verification entities or equivalent existing extensions.
3. Backfill one explicitly legacy/default issue per old complaint, preserving original text and timestamps; do not invent incident dates or verification outcomes.
4. Backfill person links only from trusted existing identifiers. Leave uncertain associations unresolved rather than combining same-name records.
5. Add/review constraints and indexes after identifying conflicts. Produce a collision report for manual resolution, not destructive cleanup.
6. Update transactional intake, imports, verification, and permission enforcement.
7. Regenerate embeddings with issue/input/model provenance in a controlled background migration. Preserve old decisions and mark superseded evidence.
8. Update review UI, filters, and issue-scoped decision recording. Keep old clients compatible through a deliberate transition or versioned contract.
9. Run the acceptance scenarios and evaluate matching changes before activating new thresholds.
10. Document deployment/backfill progress and rollback behavior. Rollback must not delete newly recorded evidence or decisions.

Do not disable constraints permanently, reset production data, load real records into public demo fixtures, or upgrade unrelated technologies as part of this change.

## 12. Mandatory acceptance scenarios

| Scenario | Expected identity behavior | Expected complaint/matching behavior |
| --- | --- | --- |
| Same full name and state, different localities | Separate person IDs; no automatic consolidation | Cases remain independent. |
| Same full name, locality, and shared household number | Shared fields do not establish identity | No automatic link or disclosure. |
| One person changes address | Preserve person continuity only through trusted linkage; retain address history | No new complaint/person forced by address change. |
| Same student/employee number at two issuers | Distinct scoped identity claims | No global-number collision. |
| Contact OTP succeeds but affiliation is unknown | Mark contact control only | Do not grant institution role or claim allegations verified. |
| Same college and city, fee refund versus broken laboratory equipment | Person identities handled independently | Unrelated issues are not linked merely by location. |
| Same college and category, different incidents | No identity inference from category | Show contrasting dates/context; require human decision. |
| Different people report one incident | Keep distinct people and evidence | Related-issue/incident linkage possible after review; no merge. |
| Similar wording at different verified institutions | No person linkage | No same-institution-pipeline match. |
| Different campuses affected by one central policy | Campus records remain distinct | Context may support review; no blanket campus rejection. |
| Incident dates missing | No fabricated date | Explain uncertainty; never treat missing dates as agreement. |
| Multi-issue complaint, only one related issue | Preserve all participants | Link only reviewed scope; unresolved issue remains visible. |
| Retries or concurrent pair decisions | Stable identifiers and conflict handling | No duplicate case, pair, or audit event. |
| Restricted person or candidate lookup | No unauthorized field leakage | Hidden records remain absent from warnings/counts/explanations. |

Use labelled synthetic fixtures covering these cases. Report actual false positives, false negatives, precision, recall, F1, candidate recall@k, latency, and reviewer workload. Separate deterministic schema/permission tests from model evaluation; do not assert that a neural model will classify every example correctly without measurement.

## 13. Completion report required from the implementing agent

Return the actual changed application files, schema migration/backfill plan, invariants enforced in the database versus services, API/UI changes, tests executed and results, matching evaluation changes, known limitations, and unresolved policy/identity-source decisions.

Mark only verified behavior as implemented. Creating this Markdown file alone does not implement verification or guarantee that false overlap suggestions cannot occur.

## 14. Related specifications

- [PRD](01_PRD.md), [Tech Stack](02_Tech_Stack.md), [Architecture](03_Architecture.md), [Workflow](04_Workflow.md).
- [Algorithm](05_Algorithm.md), [UI/UX](06_UI_UX_Design.md), [Workflow Changes](07_Workflow_Improvement_Changes.md).
- [Users and Detailed Roles](08_Users_and_Detailed_Roles.md), [Security](09_Security.md).

Design source: the user's same-name/different-locality and same-place/different-problem scenarios. PostgreSQL documentation supports constraint mechanisms; identity, review, and migration policies above are proposed OneCase implementation decisions.
