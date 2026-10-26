# OneCase — Security Requirements and Recent Threat Review

Version: 1.0 | Research checked: 26 October 2026, Asia/Kolkata | Project: SIH26264

Status: proposed implementation requirements. No source-code review, dependency inventory, vulnerability scan, penetration test, or incident investigation has been performed for OneCase in preparing this document. Recent advisories below are risk inputs, not evidence that this project is affected.

## 1. Purpose and scope

Protect complaint confidentiality, officer identity, evidence integrity, accountable ownership, and service availability in the existing React/TypeScript, Flask, PostgreSQL, and local semantic-matching design.

The required matching pipeline remains Sentence Transformer embeddings, cosine/top-k retrieval, Cross-Encoder reranking, hybrid scoring, and human review. This document adds security requirements to that design; it does not add a chatbot, autonomous agent, public grievance portal, blockchain, or unrelated security product.

The other eight Markdown files remain unchanged. Requirements here must be incorporated and verified during implementation.

## 2. Recent developments and applicability

This is a dated snapshot, not a claim to cover every incident. Check the linked advisories again when building or deploying.

| Published date | Verified source finding | OneCase relevance and action |
| --- | --- | --- |
| 21 October 2026 | Node.js published security releases addressing DNS/TLS validation issues and CVE-2026-111497 in its Brotli decoder, among other fixes. [Node.js advisory](https://nodejs.org/en/blog/vulnerability/october-2026-security-releases) | Inventory Node in development, CI, build images, and any preview/proxy service. Use a supported patched release and rebuild artifacts. A static React bundle does not itself run the Node server runtime; affected behavior depends on the actual deployed components and input paths. |
| 23 October 2026 | CERT-In advisory CIAD-2026-0053 describes a reported compromise of LiteLLM 1.107.0 and associated images, with credential theft and code-execution risks. [CERT-In advisory](https://www.cert-in.org.in/s2cMainServlet?VLCODE=CIAD-2026-0053&pageid=PUBVLNOTES02) | LiteLLM is not part of the specified OneCase stack. Check actual direct/transitive packages, development environments, caches, and images before declaring unaffected. Do not add it merely because this project uses AI. If exposure is found, follow containment and clean rebuild/credential-revocation procedures; package removal alone is insufficient evidence of recovery. |
| 28 July 2026 | GitHub documented package/CI supply-chain attack patterns targeting credentials and changes intended to disrupt them. [GitHub security update](https://github.blog/security/supply-chain-security/disrupting-supply-chain-attacks-on-npm-and-github-actions/) | Treat npm/pip installation, build workflows, and release credentials as security boundaries. Review exact package identities, restrict build privileges, and prevent untrusted code from accessing deployment secrets. |

OWASP Top 10:2025 highlights broken access control, software supply-chain failures, and exceptional-condition handling among relevant application risks. Use these categories to organize checks, not as proof of compliance. [Access control](https://top10.owasp.org/2025/A01_2025-Broken_Access_Control/index.html), [Supply chain](https://top10.owasp.org/2025/A03_2025-Software_Supply_Chain_Failures/), [Introduction](https://top10.owasp.org/2025/0x00_2025-Introduction/).

## 3. Threat model

### Assets

- Complaint descriptions and personal information.
- Salary/service records, certificates, and other supporting evidence.
- Officer credentials, session cookies, database credentials, and deployment secrets.
- Institution identity, current ownership, deadline policies, committee/proceeding records, and decisions.
- Model artifacts, embeddings, scoring configurations, review labels, and evaluation datasets.
- Action history, audit evidence, backups, and generated case packets.

### Main threats

| Threat | Example | Required defense |
| --- | --- | --- |
| Cross-bureau disclosure | Changing a case ID retrieves another bureau's salary evidence | Object/field authorization on every backend operation |
| Account takeover | Phished officer session is used to download documents | Strong authentication, revocation, step-up checks, and anomaly alerts |
| Insider misuse | Respondent or conflicted officer verifies its own compliance | Explicit role separation and case-specific conflict checks |
| Malicious attachment | Evidence file attacks a parser or viewer | Quarantine, validation, isolation, and resource limits |
| Supply-chain compromise | Dependency install steals database/CI secrets | Locked trusted artifacts, isolated builds, restricted secrets, clean rebuilds |
| Unsafe model loading | Downloaded serialized weights execute code | Reviewed pinned models, safer formats, no unreviewed remote code |
| Workflow tampering | Concurrent requests change owner or close a case improperly | Version checks, transactional events, idempotency, and authorized transitions |
| Resource exhaustion | Large descriptions or repeated reranking requests overload workers | Size/rate/queue limits and bounded inference |
| Ransomware/data destruction | Case data or backups are encrypted or deleted | Separate backup privileges and verified restoration |

Trust boundaries: browser/API, API/database, upload/parser/storage, worker/model artifacts, build/deployment, and OneCase/external correspondence. Internal networks and background jobs are not automatically trusted.

## 4. Implementation priorities

- **P0 — before any shared demo:** synthetic-only data, provisioned accounts, backend authorization, secure secret handling, private evidence, input limits, transactional history, and clean dependency/model artifacts.
- **P0 — before real-data or internet deployment:** HTTPS, hardened production configuration, privileged-user MFA, session revocation, verified attachment quarantine/scanning, sensitive-data protection, monitoring, tested backups, and incident ownership.
- **P1 — operational hardening:** centralized alerting, periodic grant review, automated dependency/model inventory checks, case-specific exposure review, and incident exercises.

These are OneCase release priorities, not externally mandated patch or reporting deadlines. A control marked required is not considered implemented until evidence exists.

## 5. Identity, authentication, and sessions

**SEC-01 — Officer accounts:** provision accounts through an authorized process. No public form or client-supplied role may grant officer, reviewer, or administrator privilege. Disable inactive/compromised accounts and revoke their sessions promptly.

**SEC-02 — Passwords:** use Argon2id through the selected maintained library with per-password salts. Permit long passphrases and password managers. Reject known-compromised passwords using an approved mechanism that does not disclose the plaintext. Do not invent password-storage cryptography or require arbitrary periodic changes instead of responding to compromise.

**SEC-03 — Authentication abuse:** use generic failure responses and layered account/IP throttling with bounded backoff. Avoid permanent lockout behavior that lets an attacker deny access to another officer. Restrict administrative account recovery and audit it.

**SEC-04 — MFA and sensitive actions:** require MFA for production privileged access and prefer phishing-resistant WebAuthn/passkeys where supported. Require recent authentication for role changes, bulk sensitive downloads, and credential changes. These controls need a tested recovery process; a decorative MFA screen is insufficient. [Authentication guidance](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html).

**SEC-05 — Sessions:** retain opaque server-side sessions with stored token digests. Use HttpOnly cookies, Secure in HTTPS deployment, an appropriate SameSite setting, and CSRF validation. Set idle and absolute expiry; rotate on authentication/privilege changes and revoke on logout/account compromise. Restrict cookie scope; use a host-only cookie where practical. Never put session tokens in URLs or localStorage. [Session guidance](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).

## 6. Authorization and privacy boundaries

**SEC-06 — Deny by default:** apply the detailed roles document's effective permission, bureau/region/institution/case scope, appointment validity, field permissions, and conflict constraints on the server.

Check authorization on case reads, mutation endpoints, pair retrieval, downloads, search results/facets, counts, notifications, reports, case packets, and background job result delivery. A random identifier is not access control. UI hiding is not enforcement.

**SEC-07 — Pair confidentiality:** a reviewer must be permitted to see both cases before receiving a comparison, score explanation, or candidate count. Do not leak an inaccessible complaint through a title, category, snippet, notification, or total.

**SEC-08 — Grant and cache lifetime:** enforce revoked/expired grants on the next protected operation. Key cached aggregates/results by effective scope, invalidate affected caches on membership changes, and avoid public/shared caching of authenticated content. Clear browser identity-specific state on logout/account change.

**SEC-09 — Separation:** respondents cannot approve their own compliance evidence. Administrators do not gain complaint-content access by default. Committee roles are case/proceeding-bound. No service identity may create a human-confirmed relationship or final compliance decision.

Minimize personal data in screens, logs, derived matching text, support screenshots, and testing fixtures. Retention, lawful disclosure, hosting location, deletion, and legal hold rules must be supplied by the competent organization; this document does not declare legal compliance or invent retention periods.

## 7. Evidence uploads, parsing, and downloads

**SEC-10 — Controlled upload flow:** intake accepts evidence only through authenticated, authorized endpoints or a separately approved submission mechanism. Suggested initial allowlist: PDF, JPEG, PNG; any additional type needs a parser and threat review. Reject executable/script/HTML/SVG and archive uploads by default. Check extension, media signature, size, file count, and parser acceptance; client MIME and filenames are untrusted. Store randomized internal keys outside public web paths. [Upload guidance](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html).

Quarantine new files. Permit general retrieval/preview only after validation and malware checks succeed. If scanning is unavailable, keep evidence pending and show the state; do not silently mark it clean. Preserve the complaint itself independently of the scan result. Record rejected/superseded evidence metadata without serving rejected bytes.

**SEC-11 — Parser isolation:** document conversion/OCR, if required, runs with bounded CPU, memory, time, pages, and output size; no application secrets, public network access, or writable application directories. Patch actual PDF/image/compression libraries. Reject malformed input and stop decompression at limits. Do not treat antivirus success as proof that a file is safe to render with an unsafe parser.

**SEC-12 — Download control:** recheck case/field access on every download. Avoid public storage URLs; any signed delivery URL must be short-lived and scoped, with revocation limitations understood. Use controlled content type, `nosniff`, and attachment disposition for untrusted originals. If inline preview is necessary, isolate it from the authenticated application origin. Preserve immutable originals and checksums; previews are derived artifacts.

Do not fetch arbitrary evidence URLs server-side. Store a link as untrusted metadata unless an approved ingestion path validates scheme, destination, redirects, DNS/IP results, and network reachability with egress restrictions. This prevents the attachment feature becoming an internal-network request proxy.

## 8. API and workflow integrity

**SEC-13 — Input handling:** validate explicit request schemas and length/count limits. Use parameterized database operations and allowlists for sortable/filterable fields. Render complaint text as escaped text; sanitize any deliberately supported rich text. Never execute uploaded content, shell snippets, or instructions embedded in documents.

**SEC-14 — State changes:** client JSON cannot set protected actor IDs, permissions, verified-compliance state, machine scores, or system timestamps. Server commands validate the current version, permitted transition, recipient eligibility, and reason.

Transfer ownership, assignment history, action event, and notification job atomically. Idempotency keys are scoped by actor/operation and request digest. Replaying a changed payload with an existing key must fail rather than mutate a different case.

**SEC-15 — Sensitive decisions:** record the authorized actor, evidence, reason, and approved document for overlap decisions, compliance verification, disposition, reopening, proceeding finalization, and policy change. Similarity, inactivity, a missed deadline, or a respondent's assertion must never independently trigger final outcomes.

**SEC-16 — Failure behavior:** authorization/configuration errors fail closed. A missing model or failed scan cannot become successful review/clean evidence. A worker crash cannot erase an owner. Preserve committed intake and expose pending work instead of falsely reporting completion. Return safe errors with correlation IDs rather than stack traces or complaint payloads.

## 9. AI matching and model supply-chain security

**SEC-17 — Approved model bundle:** obtain embedding/reranker artifacts from reviewed publishers and pin immutable revisions. Record hashes, dependency versions, tokenizer/config files, and scoring settings. Prefer safetensors weights where supported; do not load user-supplied pickle/joblib/model archives. Treat any serialized Python artifact as executable-risk material unless it is internally built and integrity-verified. [Hugging Face pickle security](https://huggingface.co/docs/hub/en/security-pickle).

Set remote-code execution opt-in flags to false for the approved standard-model path. Models requiring custom code need explicit code review and isolation before acceptance, not a blanket flag enabling. Safer weight serialization does not make accompanying model code or dependencies harmless. [Custom model loading](https://huggingface.co/docs/transformers/en/custom_models).

**SEC-18 — Worker boundary:** use local inference with restricted service permissions. Production workers load approved artifacts from read-only storage and do not download arbitrary models during a complaint request. Restrict outbound network access and resource usage. Separate model acquisition/build credentials from runtime credentials.

**SEC-19 — Derived-data privacy:** embeddings, explanations, vectors, and evaluation data remain access-controlled complaint-derived information; do not assume embeddings are anonymous. Never publish them or use complaint data for external training by default. Compare only the approved candidate scope and return only user-authorized results.

**SEC-20 — Ranking abuse:** bound text length, chunk count, top-k, pair count, inference concurrency, retries, and per-user job creation. Detect excessive repeated text/boilerplate and record normalization. Do not allow complainants to supply final labels, scores, thresholds, or reviewer identity. Curate evaluation labels and preserve provenance to reduce poisoning and manipulated reviewer feedback.

**SEC-21 — Human authority:** the selected bi-encoder/Cross-Encoder pipeline is not an autonomous tool-using agent. Complaint text is model input, never an operational instruction. The central risks are data leakage, malicious artifacts, adversarial ranking, poisoning, and resource exhaustion. If generative summaries/agents are introduced later, separately review prompt injection, tool access, data exfiltration, and output grounding before enabling them.

## 10. Dependencies, build tools, and deployment

**SEC-22 — Inventory:** maintain direct/transitive npm and Python inventories, runtime versions, container digests, model revisions, PDF/compression libraries, and operating-system packages. Include development and CI tools. A package not listed in the design can still appear transitively or share the developer environment.

Use committed lockfiles and reviewed integrity/hash controls. Install exact intended package identities from approved registries. Review new maintainers, install-time scripts, dependency changes, and model code. Do not run package installation on a machine holding production complaint data or long-lived deployment secrets. An audit tool is one signal, not a guarantee that no malicious package exists.

**SEC-23 — CI/build isolation:** do not expose deployment secrets to untrusted pull requests or their code. Restrict workflow token permissions, pin third-party action revisions, separate build from deploy, and review changes to release workflows. Provenance identifies a build origin but does not independently prove the built code is benign. Produce an approved artifact inventory with the release.

**SEC-24 — Runtime hardening:** use supported patched runtimes and base images, non-root containers where used, least-privilege database accounts, a production WSGI server, and no public debugger. Production serves the compiled React assets; do not expose the Vite development server as the deployed application.

Enforce HTTPS and certificate validation; never disable TLS verification to work around a certificate incident. Update relevant runtime/OS trust components according to vendor guidance and verify outbound clients. Treat reverse-proxy forwarding headers as trusted only from configured proxies. Keep database, worker administration, and private storage off public interfaces.

Use a restrictive tested CSP, frame restrictions, `nosniff`, and appropriate referrer/cache policies. Bundle application scripts instead of runtime CDN injection. Configure limits on requests and timeouts at proxy and API layers; CORS must not allow arbitrary credentialed origins.

## 11. Audit, confidentiality, and recovery

**SEC-25 — Audit:** successful domain changes and events share a transaction. Log authentication failures, denied sensitive operations, role/policy changes, downloads, dispatch, verification, and security-relevant worker failures under an approved policy. Keep security events distinct from successful business actions.

Record actor, object, action, outcome, UTC time, request ID, and safe change metadata. Exclude passwords, raw session tokens, secrets, full salary records, and unrestricted descriptions. Validate log fields to prevent forged entries. Restrict log access and protect its storage. Application append-only controls are not proof of cryptographic immutability or protection against database administrators.

**SEC-26 — Data protection:** encrypt database volumes, evidence storage, and backups in real-data deployments, using protected keys and separate access paths. TLS and encrypted volumes do not replace authorization. Limit export/packet scope, record generation/download, and avoid uncontrolled copies in public folders or repositories.

**SEC-27 — Restore:** back up database and evidence coherently with separate deletion privileges. Keep protected recovery copies and verify restoration with a synthetic case, evidence checksum, ownership history, and review decision. Record recovery targets and measured restore time; do not invent uptime/recovery claims.

## 12. Monitoring and incident response

Alert on unusual login failures, new privileged grants, cross-scope access attempts, mass document downloads, scan failures, repeated ownership conflicts, model-bundle changes, unexplained worker egress, and growing job backlog. Deduplicate alerts and restrict their sensitive content. Assign an accountable recipient; logging without review is insufficient.

Incident sequence:

1. Triage signal and identify affected application/build/model components and records.
2. Contain suspected identities/workloads without destroying necessary evidence.
3. Preserve relevant logs, artifact identities, timestamps, and scope observations under controlled access.
4. Revoke exposed sessions/credentials and rotate secrets from a clean trusted environment.
5. Rebuild affected workloads from verified artifacts; restoring the same compromised image is not recovery.
6. Assess complaint/document exposure, unauthorized decisions, and policy changes; correct business state through auditable events.
7. Restore service after verification and monitor for continued misuse.
8. Notify the responsible organization and applicable authorities/affected parties under confirmed policy and legal requirements. Do not invent a universal reporting deadline here.
9. Document cause, impact, remediation, and prevention actions without publishing sensitive evidence.

For a reported dependency compromise, check development hosts, CI credentials, package caches, and images as well as production. A vulnerability alert without installed-version/reachability evidence does not establish exposure; a confirmed compromised artifact requires incident handling beyond routine patching.

## 13. Security acceptance tests

| Test | Required evidence |
| --- | --- |
| Cross-scope case/document IDs | Unauthorized fields/bytes/counts remain inaccessible through direct API requests. |
| Matching pair visibility | Access to one case never reveals a restricted second case. |
| Stolen/revoked session | Revoked/expired sessions and disabled accounts fail protected requests; client caches clear. |
| CSRF and role tampering | Cross-origin unauthorized mutations and client-supplied privileged fields are rejected. |
| Respondent self-verification | Compliance approval and disposition fail without the independent required grant. |
| Malformed/oversized evidence | Reject or quarantine safely; no parser execution, public access, or unbounded resource use. |
| Scanner/model unavailable | Evidence and scoring remain pending/failed; complaint intake persists. |
| Unsafe artifact | Unapproved model/code/serialized file fails acquisition/load controls without execution. |
| Worker resource abuse | Text/pair/job limits hold while unrelated legitimate requests remain usable. |
| Concurrency and retries | One valid owner, one intended decision, no duplicate event/alert under retries. |
| Build/dependency review | Recorded inventory, relevant advisory assessment, locked approved artifacts, no exposed CI secrets. |
| Audit leakage | Logs contain sufficient accountability metadata without credentials or unrestricted evidence. |
| Restore exercise | Case, attachment checksum, owner, and action/review history recover consistently. |

Run invasive tests only in an authorized isolated environment with synthetic data. Track test date, scope, result, evidence reference, accountable owner, and unresolved issue. This document does not assert any test has passed.

## 14. Ownership and release gate

- Backend owner: identity, authorization, schemas, transitions, evidence endpoints, transactions, and safe events.
- Frontend owner: safe rendering, permission-aware states, cache isolation, secure component integration, and session-expiry behavior.
- ML owner: artifact provenance, inference isolation, derived-data controls, resource bounds, and scoring provenance.
- Deployment owner: runtime inventory/patches, secrets, TLS, private storage, backups, and incident containment.
- Product/competent authority: approved access, retention, deadline policy, conflicts, and required notifications.

Production release requires evidence for applicable P0 controls and no unresolved known-exploited or critical/high reachable issue affecting protected paths without a documented authorized mitigation/exception. An exception is a reviewed risk decision, not a reason to label an unimplemented control complete.

Review advisories before each release and at least weekly as a proposed operating routine. Assess actively exploited/reachable critical issues immediately; define actual response deadlines with the operating organization. Keep a register of component/version, advisory, exposure analysis, remediation, owner, and verification date. This document does not create a scheduled automation.

## 15. Changes to incorporate into existing specifications

| Document | Incorporate |
| --- | --- |
| [PRD](01_PRD.md) | P0 security acceptance and protected-data requirements |
| [Tech Stack](02_Tech_Stack.md) | Patched runtimes, approved dependency/model inventory, isolation, and real-data MFA requirements |
| [Architecture](03_Architecture.md) | Explicit API/storage/parser/worker/build trust boundaries and restricted credentials |
| [Workflow](04_Workflow.md) | Secure intake, quarantine, grant checks, independent verification, and safe failure states |
| [Algorithm](05_Algorithm.md) | Pinned safe model bundles, private derived data, bounded retrieval/reranking, and human-only decisions |
| [UI/UX](06_UI_UX_Design.md) | Safe text/preview rendering, no privilege self-selection, session states, and pending/failed evidence/scoring indicators |
| [Workflow Changes](07_Workflow_Improvement_Changes.md) | Protect notices, case packets, external dispatch, compliance evidence, and policy clocks |
| [Users and Roles](08_Users_and_Detailed_Roles.md) | Enforce backend scope, conflicts, grant expiry, and no administrative content access by default |

## 16. Source-use note

Recent incident dates and mechanisms are attributed inline to primary vendor/government sources. OneCase applicability and control priorities are design recommendations inferred from its specified stack and sensitive workflows, not findings from an inspected deployment. Sources may be updated after 26 October 2026; verify vendor remediation for the versions actually selected.
