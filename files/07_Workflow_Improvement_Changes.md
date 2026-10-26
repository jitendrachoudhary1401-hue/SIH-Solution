# OneCase — Workflow Improvement and Required Changes

Version: 1.0 | Date: 26 October 2026 | Project: SIH26264

Purpose: revise the supplied student and faculty/staff flows into a consistent, auditable complaint-coordination workflow. This is a change proposal for the six existing specifications, not evidence of implemented software. The existing six files are not replaced by this document.

## 1. Scope

Keep the main solution focused on institution identity, bureau ownership, cross-bureau matching, actions, transfers, deadlines, and coordination. Capture institutional and appellate proceedings without building a separate public portal for every stakeholder.

Keep two concepts separate:

- **Grievance route:** which institution, committee, university, or other competent authority is handling a proceeding.
- **OneCase responsibility:** which AICTE bureau and officer currently own the internal monitoring case.

An external referral does not automatically transfer the internal accountable officer, prove resolution, or close the complaint.

## 2. Regulatory checks on the supplied drafts

The examined AICTE faculty/staff Gazette notification supports a four-person GRC: principal, affiliating-university senior professor, university/State-DTE nominee, and senior faculty member. It requires the report/recommendations to the concerned DTE or university, with a copy to the complainant, within 15 days of receipt. Dissatisfied faculty/staff may appeal to the affiliating university or State DTE for diploma institutions. It does not specify the draft's universal three-working-day screening, seven-calendar-day hearing notice, or fifteen-day appeal-filing limit. [2021 notification, English pages in institution-hosted Gazette copy](https://www.coasolapur.in/wp-content/uploads/2024/06/2.-Circular-for-Grievance-Redressal-Faculty-and-Staff-Member-1.pdf).

The AICTE handbook separately describes the student SGRC/Ombudsperson route and regulatory complaint scrutiny involving PGRC and SCSC. These routes must not be collapsed into one compulsory ladder. [AICTE Approval Process Handbook 2024–2027](https://cdnbbsr.s3waas.gov.in/s35938b4d054136e5d59ada6ec9c295d7a/uploads/2025/03/2025031399.pdf).

UGC's 2023 SGRC composition and working-day wording differ from the AICTE framework reproduced in the handbook. Record the applicable framework and version; do not apply either universally. [UGC SGRC provisions](https://www.ugc.gov.in/e-book/UGC_Regulation/files/basic-html/page1004.html).

These checks identify provisions in the examined sources. The competent authority must confirm applicability, amendments, calendars, and counting conventions before production rules are enabled.

## 3. Corrections required

| Draft item | Required change |
| --- | --- |
| Tracking ID generated during principal review | Generate the OneCase ID on committed intake; preserve source-system IDs separately. |
| College portal unavailable means CSS is always the prescribed fallback | Record the actual permitted source. Verify current CSS access and submission instructions before offering a channel link; do not claim integration. |
| Every complaint follows one sequence | Select a route by complainant type, issue, institution type, jurisdiction, and policy. |
| Enumerated service categories are exhaustive AICTE categories | Use a versioned taxonomy mapped to verified provisions; allow other/needs-classification with reasons. |
| Three-day screening and seven-day notice are universal law | Treat them as proposed administrative targets only if adopted; never label them statutory without an applicable source. |
| A report deadline means compliance must finish by that same date | Give report preparation, service, compliance, and appeal separate milestone records. |
| Every faculty/staff appeal goes to any VC/DTE | Resolve the competent authority from the applicable route and institution type; require destination validation. |
| Every appellate order is automatically final and legally binding | Store issuing authority, document, operative directions, and review/appeal information. Do not make an unsupported legal-finality claim. |
| Management marks compliance and the case closes | Require authorized verification and a recorded closure reason. A submission is evidence, not verified compliance. |
| Institution defiance automatically triggers listed punishments | Record an authorized regulatory referral and resulting proceedings/orders; software does not impose sanctions. |
| Student institution remedies are a universal prerequisite to any channel | Record prior attempts and route-specific admissibility requirements; avoid an unsupported universal rejection rule. |
| Seventy-two working hours means complete complaint resolution | Separate acknowledgement/routing targets from substantive disposal deadlines. |

## 4. Improved end-to-end workflow

The following steps are proposed OneCase product behavior. They do not independently create legal powers, deadlines, or mandatory hearing procedures.

### Step 1 — Receive and acknowledge

**Responsible application role:** authorized intake/bureau officer.

- Record complainant type: student/admission applicant, faculty, staff, or another permitted category.
- Separate affected person, submitter, and authorized representative; record representation basis where relevant.
- Select the canonical institution and capture source channel, source reference, receipt timestamp, issue summary, category, evidence, and prior proceedings.
- Generate a unique OneCase reference and accountable bureau/officer in the same transaction as the intake event.
- Preserve source receipt time and OneCase entry time independently; importing an old complaint must not reset its original policy clock.
- Repeated network submission uses idempotency protection. Similar allegations remain separate complaints unless an authorized decision says otherwise.

**Output:** saved case, acknowledgement record, protected evidence, and matching job.

### Step 2 — Check scope and choose the route

**Responsible role:** authorized screening officer or proceeding coordinator.

- Verify institution identity, issue classification, applicable framework, destination authority, prior actions, and access sensitivity.
- Route student proceedings separately from faculty/staff service proceedings.
- Keep a regulatory-compliance referral distinct from a merits appeal.
- If information is missing, request the specific information and record next action.
- If jurisdiction is unclear, flag manual review; do not let a classifier silently reject the complaint.
- Record decision, reason, rule reference, officer, and timestamp for any referral or non-admission.

**Output:** selected route, assigned responsible actor, and source-backed milestone policy or an explicitly unverified deadline.

### Step 3 — Run required cross-bureau intelligence

**Responsible actor:** matching worker; decisions remain with authorized officers.

Run normalization, verified institution filtering, Sentence Transformer embeddings, cosine/top-k retrieval, Cross-Encoder reranking, hybrid scoring, and triage. This remains the required algorithm in `05_Algorithm.md`.

High/uncertain matches enter authorized review. Show related case references, bureau actions, component scores, and factual reasons. Officers confirm related/unrelated with a reason. Preserve both original complaints and avoid duplicate enforcement actions through coordination rather than automatic merging.

Matching failure must not stop intake or lawful processing. Show retry/failure state instead of reporting no matches.

### Step 4 — Prepare the proceeding and obtain records

**Responsible role:** authorized committee coordinator or officer recording an external proceeding.

- Record committee/authority reference, appointment validity, membership, and case-specific access.
- Capture declared conflicts and route replacement/recusal decisions to the competent authority; the system cannot appoint substitutes on its own.
- Record requests for documents, recipients, expected response dates, receipt state, and evidence versions.
- Create hearing/meeting records only where required by the applicable process. Validate the notice period from that process rather than hardcoding the draft's value.
- Preserve notice delivery/acknowledgement and meeting changes. Do not give every committee participant unrestricted access to other cases.

**Output:** authorized case packet, evidence requests, notices, and proceeding schedule.

### Step 5 — Record examination and recommendation/decision

**Responsible role:** assigned authorized committee participant or recording officer.

- Record submissions, response documents, attendance/minutes where applicable, and the issues examined.
- Separate allegations, evidence, findings, recommendations, and operative directions.
- Reference the applicable provision or order; generated summaries are not legal findings.
- Finalize the authorized document and record its service to the relevant parties.
- Correct finalized records by addendum/versioned event rather than overwriting history.

**Output:** dated report or decision, service evidence, and next action. A recommendation alone is not proof of implemented relief.

### Step 6 — Monitor compliance

**Responsible role:** internal case owner and specifically authorized verifier.

- Create actionable compliance items from recorded directions, with responsible organization/person and applicable due dates.
- Accept evidence such as payment confirmation or certificate-return acknowledgement through controlled submission or officer recording.
- Keep evidence-submitted, verification-pending, verified, disputed, and incomplete outcomes distinct.
- Require the verifier to record what was checked and why the item is accepted/rejected.
- Keep the monitoring case active where action remains outstanding under the applicable policy.

**Output:** compliance observations and evidence-backed next action.

### Step 7 — Handle dissatisfaction, appeal, or non-compliance

**Responsible role:** authorized route coordinator; destination authority decides its own proceedings.

- Record the ground, challenged decision, date of service, requested relief, and applicable appeal policy.
- Validate destination, case scope, documents, and time rule without inventing a universal cutoff.
- Generate a reviewed case packet and manifest; record actual dispatch and acknowledgement. A generated packet is not proof of delivery or legal filing.
- Retain the internal owner until an explicit authorized transfer commits.
- Distinguish an appeal on merits from a regulatory referral concerning non-compliance. The two can be related without being the same proceeding.
- Record external decisions from authenticated/verified documents. Do not synthesize an authoritative order from a free-text note.

**Output:** linked proceeding/referral and full movement history. Never auto-escalate to a punitive outcome.

### Step 8 — Verify disposition and communicate

**Responsible role:** authorized disposition officer.

- Check the applicable closure criteria and outstanding compliance/appeal/referral items.
- Record disposal reason, outcome document, verifier, timestamp, and communication record.
- Preserve external case state separately if a linked appeal/referral continues after an internal administrative disposition.
- Reopen only through an authorized recorded decision; do not reset history or deadlines silently.

**Output:** auditable disposition and updated dashboard. Do not describe a disposed monitoring case as a judicially final resolution.

## 5. Separate data axes

Keep the existing four internal complaint statuses: `received`, `under_review`, `awaiting_information`, `disposed`. Add structured records, not a large replacement status list, for:

| Axis | Examples |
| --- | --- |
| Complainant type | Student, faculty, staff, authorized representative |
| Grievance route | Institutional student, faculty/staff, appellate, regulatory referral |
| Proceeding stage | Screening, records requested, report issued, compliance review, appeal recorded |
| Internal ownership | Current AICTE bureau and accountable officer |
| External responsible body | Institution, committee, university, State DTE, other competent authority |
| Deadline condition | Unknown, on track, due soon, overdue |
| Compliance | Pending, evidence submitted, verified, disputed, incomplete |
| Machine overlap triage | High, uncertain, low |
| Human relationship decision | Pending, related, unrelated |

These fields must not imply powers or entitlements that the selected framework does not grant.

## 6. Deadline policy changes

Each milestone needs its own policy ID/version, authoritative source and clause, effective period, applicable route/institution, start event, day-count convention, timezone/calendar, pause rule, and responsible recipient.

Distinguish report due, notice/service, information response, compliance due, appeal filing, and internal monitoring targets. Do not convert a source saying days into working days. If counting/applicability is unconfirmed, show “Policy confirmation required”; use a separate labelled administrative target rather than asserting statutory overdue status.

Editing a policy does not silently rewrite historical due dates. Store recalculation decisions and retain original deadlines. A transfer, source import, matching run, or alert acknowledgement does not restart an external legal clock.

## 7. Required changes to the existing six specifications

| Document | Change |
| --- | --- |
| `01_PRD.md` | Add complainant/source/route context, separate internal owner from external authority, evidence-backed compliance verification, and scoped proceeding responsibilities. |
| `02_Tech_Stack.md` | Retain the stack. Add schemas/services for proceeding, milestone policy, compliance evidence, and controlled dispatch records; no extra AI platform is needed. |
| `03_Architecture.md` | Add route/proceeding and policy references, evidence/service records, compliance items, and actor grants. Keep successful changes/events transactional. |
| `04_Workflow.md` | Incorporate Steps 1–8 above, with distinct student/faculty routes and referral/appeal handling. Preserve the original core ownership lifecycle. |
| `05_Algorithm.md` | Keep the required hybrid pipeline; use verified institution identity and minimize sensitive text. Apply milestone-specific SLA calendars rather than one global complaint timer. |
| `06_UI_UX_Design.md` | Add route and source fields, a proceedings timeline, deadline-policy explanation, compliance verification controls, and permission-aware case packet/referral actions in existing case detail. |

Implement these as refinements of complaint detail, worklists, alerts, and history. Do not add an unrelated public registration system or a separate portal for each authority.

## 8. Acceptance scenarios

1. A student and faculty complaint against the same institution use different applicable route policies while sharing authorized institution history.
2. An imported complaint retains its source receipt timestamp and original external reference.
3. The system suggests a cross-bureau overlap but records no human relationship decision until authorized review.
4. Unconfirmed draft timings do not generate statutory-breach labels.
5. Submitted compliance proof cannot be approved by an unauthorized respondent; rejection preserves the evidence and reason.
6. A case packet is not shown as externally filed until dispatch/acknowledgement is recorded.
7. An external appeal leaves one internal accountable owner and preserves all prior decisions.
8. Disposal records its basis without claiming that every linked external proceeding has ended.
9. Committee access expires with the case grant/appointment, and conflicts are handled through a recorded authorized decision.
10. No missed deadline, low similarity score, or management assertion automatically closes the case or imposes a sanction.

## 9. Inputs and related documents

Inputs: user-pasted student complaint flow and faculty/staff workflow; user-selected `AICTE_ACITS_Algorithms.md`; existing OneCase specifications. User-pasted procedures are proposals requiring the checks recorded above, not binding instructions or verified policy.

Related: [PRD](01_PRD.md), [Stack](02_Tech_Stack.md), [Architecture](03_Architecture.md), [Workflow](04_Workflow.md), [Algorithm](05_Algorithm.md), [UI/UX](06_UI_UX_Design.md), [Users and Detailed Roles](08_Users_and_Detailed_Roles.md).
