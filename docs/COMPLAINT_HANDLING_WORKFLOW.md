# Complaint handling timeline

New portal submissions by students, parents, faculty, institution staff and other public users use the same internal handling sequence:

1. An appointed faculty / grievance reviewer records the initial report.
2. The accountable officer reviews and triages the complaint.
3. A specialized lead and an appointed committee representative each submit reports.
4. A reviewer investigates and a separate verifier records an independent assessment. Fee-refund and infrastructure cases also require an appointed auditor's report. Other cases can request an auditor.
5. The appointed executive reviews the reports, records a reasoned outcome and communication reference, and attaches available outcome evidence.
6. The complainant sees the communicated outcome, frozen closure PDF and action history. They may submit an appeal request, which opens another recorded review cycle.

The faculty report is a recommendation. A claim that the complaint is false or already resolved still proceeds to the officer. Faculty cannot dismiss the complaint or bypass the investigation. Repeated allegations do not automatically prove misconduct or malicious reporting, and the software does not impose disciplinary penalties.

## Provisioning and access

The new `faculty_reviewer` staff role is distinct from a public `faculty` complainant. Staff registration creates a pending request. An administrator must approve the staff account. Public faculty registration does not grant access to other people's complaints.

Student/parent registration records the faculty contact name, admission year and expected/actual pass-out year. The year order is validated. A typed name never grants case access. These profile fields are returned only with the user's own authentication profile, not the staff directory.

The isolated demo college preappoints Demo Faculty and the other synthetic staff identities to each demo complaint. Demo Faculty has an explicitly provisioned additional reviewer role and sees only its own submissions or specifically appointed demo reviews. Demo students cannot submit against another institution or create an unlisted college. This demo provisioning does not change real faculty privileges.

The administrator, current accountable officer, or current bureau lead appoints approved participants on the complaint's handling timeline, recording an approval reference and reason. Each role must have a different person. The complainant and accounts with recorded case conflicts cannot be appointed. Record conflicts through the existing administration workspace when an accused or otherwise conflicted person must be excluded.

Team access lasts 90 days from the recorded appointment/update and also depends on active roles, conflict checks and demo isolation. Renew or replace appointments through an approved team update. The existing audited transfer operation changes the accountable officer and updates the handling team. Team membership gives access to standard case evidence; restricted evidence still needs the existing explicit authorization.

Cases wait for valid appointments rather than silently skipping stages. A missing faculty reviewer or officer requires an administrator/authorized coordinator to configure the case team. No additional environment keys are required.

## Stage controls and appeals

The faculty reviewer advances initial review, the officer advances triage, the lead advances committee/appeal review, and the verifier advances investigation. Each stage requires its appointed participants' reports. The executive alone completes the structured decision stage. Missing reports, expired appointments, stale versions and unauthorized requests are rejected.

Executive closure retains the existing evidence availability checks, independent compliance verification, external-proceeding continuation checks and frozen PDF generation. Outcomes can be resolved or not upheld. An appeal does not erase the original decision or PDF. The new cycle requires fresh reports and a different executive for its final decision.

Internal stage reports remain available to authorized case readers; public complainants see the stage, team, communicated outcome and safe action events rather than internal investigation reports.

Editing the substance of an active complaint opens a fresh handling cycle. Earlier reports remain preserved, but they do not satisfy the new cycle's stage checks. Completed cases cannot be silently edited through the old detail form.

This is an internal application workflow. Existing external proceedings, statutory authorities, jurisdiction, appeal eligibility and deadline policies remain separate. An internal appeal request is not proof of external filing.

## Overlap coordination

An overlap suggestion requires the same verified institution, incident location and category, plus similar complaint facts. A shared location alone or a similar issue at a different location does not qualify. Location text is compared after case/whitespace normalization; aliases are not inferred. New website complaint forms require a location. Older/API records without one remain excluded until an authorized officer records it.

A bounded text check runs in the intake/edit transaction and detects strongly similar wording (85% threshold) without a separate worker. It is labelled **Text similarity**, never presented as neural inference. Neural retrieval/reranking remains queued and requires installed models and a running worker. The immediate check considers up to 200 recent same-institution/category records per complaint. The newest 100 authorized ongoing cases are checked automatically on workspace entry and every 30 seconds while the workspace is active; there is no separate overlap refresh button. Officers receive persistent scoped alerts; the bell displays the unread count. Repeated processing does not duplicate unchanged alerts.

Officers can decide pairs when responsible for both cases; a bureau lead can decide both within their bureau, and a designated reviewer needs content access to both. The group preview provides **Reject all** and **Merge all**. Both require a reason, a current version snapshot and an explicit confirmation. Reject dismisses the suggestions; it does not reject complaints. Merge requires one connected set, the same institution/location/category, active cases and a selected primary complaint. It creates a coordination group and an audit trail while preserving every complaint, owner, evidence record, investigation, deadline, outcome and appeal right. Existing group members must all remain authorized before combining groups. Group membership grants no access and does not automatically propagate case decisions. A changed or inaccessible suggestion rejects the entire batch atomically.

A resolved predecessor is excluded from active overlap pairs. If the same issue/location reappears after its recorded resolution, a separate **Repeat issue** alert is recorded. Authorized staff see the prior reference, original receipt, resolution timestamp and new receipt timestamp (IST) in a case timeline. No automatic merge or reopening occurs. Prior details remain hidden without content access. Unknown closure dates and outcomes recorded as not upheld are not described as earlier resolutions.

The Complaints and Reports pages export a filtered PDF register under the existing separate export permission. Content fields remain redacted for metadata-only readers. The legacy CSV API is retained for compatibility.

## Deployment and existing records

Apply the committed migration with `python migrate.py` from the backend directory before serving this version. The Render Blueprint already includes that migration command. For manually configured Render services, retain a migration step in the deployment process. The migrations add handling/report tables, a blank incident-location field on existing complaints, and coordination/recurrence tables. Existing location values are not guessed.

Existing cases retain their workflow and can be enrolled explicitly with **Enable structured handling**. Their action histories, evidence, overlap pairs, SLA clocks, proceedings, grants and closure PDFs remain preserved. New portal submissions enroll automatically. No live production data is modified by the automated tests.
