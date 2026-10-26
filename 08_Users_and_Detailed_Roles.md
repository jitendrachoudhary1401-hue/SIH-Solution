# OneCase — Users, Stakeholders, and Detailed Roles

Version: 1.0 | Date: 26 October 2026 | Project: SIH26264

Purpose: define who participates, who needs application access, who may act on a case, and what each role must not do. This is a proposed OneCase permission model, not an official list of AICTE job titles.

## 1. Three distinct concepts

- **Stakeholder:** a person or organization involved in a complaint, even without a OneCase account.
- **Designation/membership:** an institutional post or committee appointment recorded with its scope and validity.
- **Application role:** a controlled bundle of operations, further restricted by bureau, region, institution, case, proceeding, field sensitivity, and time.

Examples: a principal may be a respondent and also hold a committee designation. Neither fact permits unrestricted access or self-verification of management compliance. A student special invitee is not automatically a full-access committee officer.

## 2. Stakeholder inventory

| Stakeholder | What OneCase records | Default application access |
| --- | --- | --- |
| Student/admission applicant | Affected person, complaint details, relevant references, communication needs | No officer access merely because a complaint exists. |
| Faculty/staff member | Employment-related complaint context and protected evidence | No bureau/committee permission by default. |
| Parent/guardian/other representative | Represented person, authorization basis, scope, and validity | No automatic access to the person's full case history. |
| Institution management/principal | Respondent organization/person, requests, replies, and compliance evidence | Controlled submission through an authorized channel; no decision-verification rights by default. |
| Institutional grievance committee | Committee type, appointment, members, validity, assigned proceedings | Case/proceeding-specific access only when provisioned. |
| Class advisor/warden/course contact | Relevant local contact or prior-action actor | No mandatory gateway role or automatic case access. |
| University/ombudsperson | Applicable referral/appeal authority and received decision | Scoped participation or external document record, according to verified route. |
| State DTE | Relevant state authority and proceeding/contact reference | Scoped participation only where applicable. |
| AICTE PGRC, RB, other bureaus | Internal handling organization, officers, actions, ownership | Role and bureau-based access as configured. |
| SCSC/EVC/SHC/appellate or competent decision body | Proceeding, membership reference, recommendation, order | Appointment- and case-bound permissions if using OneCase. |
| MoE/other referring organization | Referral origin, destination, correspondence, and source reference | No system-wide access by virtue of being a source. |
| CSS/CPGRAMS/other portal | Source system and original reference, receipt and referral timestamps | A portal is a channel, not a human role; integration is not assumed. |

Faculty/staff and student mechanisms have different frameworks. The AICTE handbook identifies student committees and regulatory complaint processing; UGC 2023 separately defines student SGRC arrangements. Store applicability rather than merging committee compositions. [AICTE handbook](https://cdnbbsr.s3waas.gov.in/s35938b4d054136e5d59ada6ec9c295d7a/uploads/2025/03/2025031399.pdf), [UGC student SGRC provisions](https://www.ugc.gov.in/e-book/UGC_Regulation/files/basic-html/page1004.html).

## 3. Application roles

### R1 — Intake / Bureau Officer

**Purpose:** receive, maintain, and act on assigned or bureau-permitted cases.

May register cases, select verified institutions, record source references, request information, add authorized remarks/evidence, maintain next actions, and view permitted institutional history. Receives assignment/deadline alerts. May perform status transitions only where separately granted.

Must not browse another bureau's restricted records, modify finalized event history, grant roles, self-approve a transfer without permission, or treat a machine suggestion as a confirmed relationship.

### R2 — Bureau Lead / Case Coordinator

**Purpose:** maintain accountability and coordinate the bureau's work.

May assign eligible officers, approve/perform authorized transfers, review workload/bottleneck flags, manage next actions, validate route destinations, and authorize case packet dispatch within scope. May record external proceedings without pretending to act as the external authority.

Must not override statutory authority, invent official deadlines, erase assignment history, or silently reassign a case based on an AI recommendation. A lead role does not automatically include cross-bureau sensitive-data access.

### R3 — Overlap Reviewer

**Purpose:** decide whether suggested complaints should be linked as related.

May compare both cases only when both are authorized, inspect matching evidence, record related/unrelated decisions with reasons, request more information, and initiate an explicit review correction/re-review.

Must not automatically merge/dispose cases, impose findings of misconduct, expose restricted candidate references, alter model scores as if machine-generated, or transfer ownership solely through a relationship decision.

### R4 — Proceeding Participant / Committee Coordinator

**Purpose:** support an assigned authorized committee or external-authority proceeding.

Use granular permissions for coordinator, participating member, and finalizing authority. The coordinator may prepare notices/packets and record receipt; participants may contribute permitted observations; only the recorded authorized finalizer may publish the proceeding's approved report in OneCase. Imported signed documents retain their external issuer.

Access requires a valid appointment or explicit case grant, permitted proceeding, and field scope. Record recusal/conflict decisions and appointment expiry. Being a member does not grant access to all institutional complaints. This role cannot create legal powers to compel documents or cross-examine parties beyond the applicable process.

### R5 — Compliance Verifier / Disposition Officer

**Purpose:** check evidence and record permitted outcomes.

May inspect assigned compliance items, accept/reject evidence with a reason, record verified observations, and dispose/reopen the internal case when a separate transition permission and applicable criteria allow it.

Must not accept the respondent's assertion as verification by default, overwrite the order being checked, ignore an applicable conflict, label all external proceedings final, or dispose automatically because an SLA expired. The submitter/respondent must not self-verify the same compliance item. Other combined roles require explicit conflict checks.

### R6 — Senior Monitoring Official

**Purpose:** monitor permitted bureau/institution/region workload and coordination.

May view scoped aggregates, overdue/ageing indicators, pending review/compliance indicators, and approved reports. Detailed case access and actions require separate grants.

Must not obtain hidden complaint details through counts, facets, downloads, or drill-downs. Monitoring access is not an implicit decision-making or sanctioning permission.

### R7 — Auditor

**Purpose:** inspect accountability evidence within an approved audit scope.

May read permitted action history, assignment/transfer records, policy revisions, score/review provenance, and compliance/disposition reasons. Any export permission is separate and audited.

Must not change case outcomes, review decisions, model evidence, or audit history. Access to personal/financial documents must be minimized and explicitly justified by scope.

### R8 — System Administrator

**Purpose:** manage the application, not decide complaint merits.

May provision/deactivate accounts, assign approved roles/scopes, revoke sessions, configure approved policies, monitor failed jobs, and maintain operations. Policy configuration requires an approval/source record rather than arbitrary official-rule claims.

Must not receive case-content visibility by default, self-authorize a grievance decision, impersonate an external authority, delete audit events through normal application controls, or convert proposed targets into statutory rules without approval.

### Machine service identity — Worker

Runs matching, deadline calculations, deduplicated notifications, and operational scans under a dedicated restricted service identity. Records bundle/rule versions and job outcomes.

May write machine evidence and system events. Cannot make human overlap decisions, approve compliance, impose sanctions, or grant user permissions. A retry retains job identity and does not pretend to be a human action.

## 4. Permission matrix

`Scoped` means explicit backend permission plus valid object/field scope. It does not mean every holder can perform that action everywhere.

| Operation | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Register complaint | Scoped | Scoped | No | No | No | No | No | No |
| Read case detail | Scoped | Scoped | Both compared cases | Assigned proceeding | Assigned verification | Separate grant | Audit scope | No default |
| Add case action/evidence | Scoped | Scoped | Review note only | Proceeding only | Verification only | No | No | No |
| Assign/transfer internal owner | Separate grant | Scoped | No | No | No | No | No | No |
| Confirm/reject overlap | No | Separate reviewer grant | Scoped | No | No | No | No | No |
| Prepare proceeding packet | Separate grant | Scoped | No | Coordinator grant | No | No | No | No |
| Finalize proceeding report | No | No | No | Finalizer grant | No | No | No | No |
| Verify compliance | No | Separate verifier grant | No | No | Scoped | No | No | No |
| Dispose/reopen | Separate grant | Separate grant | No | No | Separate grant | No | No | No |
| View dashboard | Scoped | Scoped | Review scope | No default | Assigned scope | Approved scope | Audit scope | Operational health only |
| Read broad audit history | No | Separate grant | Own review scope | Own proceeding scope | Own verification scope | No default | Scoped | Security/operations only |
| Manage accounts/scopes | No | No | No | No | No | No | No | Approved administrative scope |

Finalizing a report in the application means recording an authorized document. It does not make OneCase the legal issuer when the issuing authority operates externally.

## 5. Access decision

```text
Allow operation only if:
  session is valid and account active
  AND effective role grants the operation
  AND bureau/region/institution/case scope permits it
  AND appointment/case grant remains valid where required
  AND requested fields/documents are permitted
  AND conflict/separation constraints are satisfied
  AND expected object revision and workflow transition are valid
Otherwise deny and record an appropriate safe event.
```

Apply the decision before serialization, aggregation, search facets, pair counts, document download, and packet/export generation. Hiding a button is insufficient. Unknown role combinations or scope conflicts default to denial.

## 6. Responsibility by workflow stage

| Stage | Responsible application role | Other participants |
| --- | --- | --- |
| Intake/acknowledgement | R1 | Complainant/representative as recorded stakeholders |
| Scope and route validation | R2 or authorized R1 | Competent external authority where applicable |
| Matching | Worker | R3 receives only authorized suggestions |
| Human relationship decision | R3 | Case owners coordinate subsequent action |
| Committee/proceeding records | R4 | Institution, complainant, and appointed participants |
| Compliance review | R5 | Respondent submits evidence through permitted channel |
| Referral/dispatch | R2 or authorized R4 | Receiving authority acknowledges through actual channel |
| Disposal/reopening | Explicitly authorized R5/R2/R1 | Relevant verification and communication records |
| Monitoring | R6 | R2 handles operational follow-up |
| Audit and administration | R7 and R8 separately | Neither replaces the merits authority |

## 7. Required identity and grant records

- User ID, display name, account state, and verified login identity.
- Role assignments and explicit permissions, approving actor, validity, and reason.
- Organization/bureau/region membership with effective periods.
- Institution/committee designation and appointment reference, separately from application role.
- Case/proceeding/field grants with expiry and revocation events.
- Representation basis and permitted communication/disclosure scope for external representatives.
- Conflict/recusal record and competent approval of replacement where needed.

Use minimum necessary information. Do not automatically collect committee members' caste or other sensitive demographic evidence solely to support application access; any compliance evidence needs a separate lawful, protected purpose.

## 8. Minimal interface behavior

- One officer sign-in and permission-aware workspace; no public role selector that grants privilege.
- Dashboard/list scope follows effective grants and shows the applied bureau/region filters.
- Case detail exposes only permitted actions and fields.
- Committee participation is attached to assigned proceedings, not unrestricted committee-wide search.
- The respondent and verifier have distinct recorded actions.
- Role or account changes revoke/refresh affected sessions and client caches as required.
- External stakeholders may be represented by controlled correspondence/documents without new login systems.

## 9. Access acceptance tests

1. Changing a case ID or attachment ID cannot bypass bureau/field scope.
2. A reviewer cannot view a pair unless both cases are permitted.
3. A committee participant loses access after grant/appointment expiry or recorded recusal.
4. A respondent cannot verify its own evidence or close the case.
5. An administrator can disable an account without reading its complaint documents.
6. An executive cannot infer restricted details through counts, facets, or drill-downs.
7. A worker cannot record a human-confirmed relationship or compliance approval.
8. Combined roles remain subject to case-specific conflicts and separation constraints.
9. External referral leaves the internal owner intact until a valid transfer transaction.
10. Permission changes and sensitive operations produce safe append-only events.

Related: [Workflow Improvement Changes](07_Workflow_Improvement_Changes.md), [PRD](01_PRD.md), [Architecture](03_Architecture.md), [Workflow](04_Workflow.md), [Algorithm](05_Algorithm.md), [UI/UX](06_UI_UX_Design.md).
