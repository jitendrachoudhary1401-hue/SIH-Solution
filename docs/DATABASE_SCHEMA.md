# Database schema and migration notes

The schema is defined in `backend/app/models.py` and versioned in `backend/migrations/versions`. It uses Neon Postgres in deployment. SQLite exists only for isolated local tests/legacy demo data.

## Entity groups

| Group | Tables | Main separation |
| --- | --- | --- |
| Officer access | `user`, `bureau`, `session`, `role_assignment`, `permission_grant`, `grant`, `appointment`, `case_conflict` | Login accounts and application permissions are distinct from external people and committee designations. |
| Complaint ownership | `complaint`, `assignment`, `transfer`, `action_event`, `idempotency` | Each complaint keeps its own reference, current owner, lifecycle and append-only application history. |
| Institution geography | `institution`, `campus`, `location`, `identity_issuer` | Institution identity, campus identity and geography are separate records. |
| External people | `person`, `person_contact`, `identity_claim`, `identity_verification`, `person_location` | Stable opaque person IDs; shared names/contacts are permitted; checks are specific rather than one global verified-person flag. |
| Participation/source | `complaint_participant`, `representative_authorization`, `complaint_source` | Affected person, submitter, representative and source-system record are separate concepts. |
| Individual issues | `complaint_issue`, `issue_evidence`, `incident_record`, `issue_incident_link` | One complaint can contain several distinguishable issues; an incident relationship requires an explicit reviewed record. |
| Relationship evidence | `embedding`, `matching_run`, `pair`, `pair_score`, `review`, `issue_pair_finding`, `issue_review` | Durable case pairs, machine runs, issue findings and human decisions have separate provenance. |
| Proceedings | `proceeding`, `proceeding_record`, `milestone_policy`, `milestone`, `dispatch_packet` | External authority, case owner, approved report, milestone clocks and actual dispatch are distinct. |
| Compliance | `compliance_item`, `compliance_submission`, `compliance_verification` | Submitted evidence is distinct from independent verification. |
| Evidence/operations | `attachment`, `notification`, `job`, `sla_pause`, `login_attempt` | Private bytes, scan status, delivery state and background work remain separate from final case outcomes. |

## Database-enforced invariants

- Unique complaint references, unique session digests, canonical case-pair uniqueness and distinct case IDs.
- Names are indexed for search and are **not unique** person keys. Person/contact values do not automatically merge people.
- UUID-like opaque IDs identify the new person/location/issue records independently of names or addresses.
- Complaint `(id, institution_id)` and campus `(id, institution_id)` keys support composite issue foreign keys. An issue cannot refer to a campus from another institution.
- Issue-evidence composite foreign keys require the issue and attachment to belong to the same complaint.
- Incident and identity-claim validity ranges reject reversed dates; unknown incident precision is retained.
- Source records have a nullable unique guaranteed-source key, so uniqueness is applied only where the source provides that guarantee.
- Representative and represented person IDs must differ.
- Existing complaint status and priority constraints remain; identity/schema changes do not create new internal complaint statuses.

## Service-enforced checks

The Flask policy checks live sessions, role grants, case/bureau scope, appointment expiry, conflicts, document permissions, current versions and allowed operations. The workflow service separately checks authenticated document use, independent compliance verification, disposition evidence/communication, destination validation and actual dispatch timestamps.

Database foreign keys prove association integrity; they do not authorize a caller. Every protected operation must still pass backend scope checks before serialization, counts, downloads or mutation.

## Additive migration chain

1. `423a5674c47d`: original complaint/assignment/audit/matching foundation.
2. `550b01638e99`: case intake context, expiring access, proceedings, compliance, milestones, MFA/session controls and private-storage provenance.
3. `40177bd277c9`: normalized people/geography/participants/sources/issues and issue-relationship structures, composite association constraints, and legacy backfill.

The third migration creates parent composite keys before new child foreign keys. It backfills one **Legacy/default issue** and source-provenance record per old complaint. It preserves original text, complaint reference and receipt time, uses unknown incident dates, and does not infer people or verification outcomes from names. Existing relationship decisions remain in their original tables.

SQLite table recreation temporarily suspends foreign-key enforcement only on the migration connection, then checks referential integrity and restores enforcement. Application connections always enable it. The workflow migration is resumable for the earlier interrupted local SQLite attempt. No database reset or destructive identity consolidation is part of setup.

All three migrations passed on an isolated Neon branch before application to the empty intended `production` branch. The latter completed successfully. The isolated branch uses synthetic data and expires automatically.

## Implementation boundary

These migrations establish the normalized database scheme requested in `10_Identity_Verification_and_Complaint_Separation_Changes.md`. They do not by themselves implement or verify every identity-check UI, import-resolution flow, issue-level model evaluation or migration of existing matching inputs. The current complaint-level pipeline remains available while those refinements are completed deliberately. Do not describe the presence of an identity table as verified legal identity or a completed false-positive safeguard.
