# Complaint handling timeline

New portal submissions by students, parents, faculty, institution staff and other stakeholders use the same internal handling sequence:

1. An appointed faculty / grievance reviewer records the initial report.
2. The accountable officer reviews and triages the complaint.
3. A specialized lead and an appointed committee representative each submit reports.
4. A reviewer investigates and a separate verifier records an independent assessment. Fee-refund and infrastructure cases also require an appointed auditor's report. Other cases can request an auditor.
5. The appointed executive reviews the reports, records a reasoned outcome and communication reference, and attaches available outcome evidence.
6. The complainant sees the communicated outcome, frozen closure PDF and action history. They may submit an appeal request, which opens another recorded review cycle.

The faculty report is a recommendation. A claim that the complaint is false or already resolved still proceeds to the officer. Faculty cannot dismiss the complaint or bypass the investigation. Repeated allegations do not automatically prove misconduct or malicious reporting, and the software does not impose disciplinary penalties.

## Provisioning and access

The new `faculty_reviewer` staff role is distinct from a public `faculty` complainant. Staff registration creates a pending request. An administrator must approve the staff account. Public faculty registration does not grant access to other people's complaints.

The administrator, current accountable officer, or current bureau lead appoints approved participants on the complaint's handling timeline, recording an approval reference and reason. Each role must have a different person. The complainant and accounts with recorded case conflicts cannot be appointed. Record conflicts through the existing administration workspace when an accused or otherwise conflicted person must be excluded.

Team access lasts 90 days from the recorded appointment/update and also depends on active roles, conflict checks and demo isolation. Renew or replace appointments through an approved team update. The existing audited transfer operation changes the accountable officer and updates the handling team. Team membership gives access to standard case evidence; restricted evidence still needs the existing explicit authorization.

Cases wait for valid appointments rather than silently skipping stages. A missing faculty reviewer or officer requires an administrator/authorized coordinator to configure the case team. No additional environment keys are required.

## Stage controls and appeals

The faculty reviewer advances initial review, the officer advances triage, the lead advances committee/appeal review, and the verifier advances investigation. Each stage requires its appointed participants' reports. The executive alone completes the structured decision stage. Missing reports, expired appointments, stale versions and unauthorized requests are rejected.

Executive closure retains the existing evidence availability checks, independent compliance verification, external-proceeding continuation checks and frozen PDF generation. Outcomes can be resolved or not upheld. An appeal does not erase the original decision or PDF. The new cycle requires fresh reports and a different executive for its final decision.

Internal stage reports remain available to authorized case readers; public complainants see the stage, team, communicated outcome and safe action events rather than internal investigation reports.

This is an internal application workflow. Existing external proceedings, statutory authorities, jurisdiction, appeal eligibility and deadline policies remain separate. An internal appeal request is not proof of external filing.

## Overlap coordination

The existing local matching worker still compares descriptions within a verified institution and produces suggestions for human review. It now alerts the active assigned officers of both shortlisted non-low-band cases. Each officer's notification identifies only their own complaint and links to that case. A reviewer receives a comparison alert only when permitted to read both complaints. Reviewer decisions also notify the current officers without disclosing the other complaint's content.

Repeated processing of the same pair/content revisions does not duplicate the same officer alert. Similarity is a relevance signal, not proof that a complaint is false, duplicated or established.

## Deployment and existing records

Apply the committed migration with `python migrate.py` from the backend directory before serving this version. The Render Blueprint already includes that migration command. For manually configured Render services, retain a migration step in the deployment process. The migration adds handling and report tables; it does not rewrite existing complaints.

Existing cases retain their workflow and can be enrolled explicitly with **Enable structured handling**. Their action histories, evidence, overlap pairs, SLA clocks, proceedings, grants and closure PDFs remain preserved. New portal submissions enroll automatically. No live production data is modified by the automated tests.
