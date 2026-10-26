# OneCase Security Specification

**Document type:** Security requirements and implementation guidance  
**Project:** OneCase — AICTE Institution Complaint Coordination & Tracking System  
**Status:** Proposed requirements; implementation and institutional approval must be verified  
**Scope:** Authentication, account registration, authorization, complaint data, attachments, AI matching, audit logs, and deployment security

---

## 1. Purpose

This document defines security requirements for OneCase. It is intended to guide implementation and security testing; it does **not** certify that the application is secure or approved for production use.

OneCase must protect student and officer accounts, institution information, complaint records, attachments, AI matching results, and audit history against unauthorized access, alteration, disclosure, and loss.

## 2. Security Principles

1. **Deny by default:** Access is denied unless explicitly authorized.
2. **Least privilege:** Give users only the permissions needed for their assigned duties.
3. **Backend enforcement:** Never rely on hidden buttons or frontend checks as the security boundary.
4. **Data minimization:** Collect and retain only information needed for a defined purpose.
5. **Separation of duties:** Separate account verification, role assignment, system administration, and audit review where practical.
6. **Traceability:** Record security-relevant actions in protected audit logs.
7. **Fail securely:** If authentication, authorization, database access, or AI processing fails, do not expose data or fabricate results.
8. **No mock business data:** Do not seed fake users, institutions, complaints, account requests, or AI results into the application.

## 3. User Types and Account Provisioning

Proposed user categories are:
- Student
- College representative (ASOP; exact designation and responsibilities require confirmation)
- AICTE officer
- Verification administrator
- System administrator
- Audit/compliance reviewer

These roles and their exact permissions must be confirmed against the approved institutional workflow before production use.

### 3.1 Account request workflow

1. Applicant submits the appropriate request form.
2. Flask backend validates and normalizes input.
3. Request is saved in PostgreSQL with `PENDING` status.
4. An authorized reviewer verifies identity, affiliation, designation/enrollment, and requested access using an approved process.
5. Reviewer approves or rejects the request and records a reason.
6. Only after required verification and approval may the system provision an account and send a secure activation invitation.
7. Account activation must not automatically grant permissions beyond those explicitly approved.

### 3.2 Registration requirements

- Do not allow public self-assignment of privileged roles.
- Do not allow applicants to approve their own requests.
- Do not treat email verification alone as proof of employment, designation, or student enrollment.
- Do not invent an AICTE API, staff directory, or student directory.
- If no authorized verification source/process is available, keep the request pending and document the dependency.
- Prevent duplicate pending requests where appropriate using application checks and database constraints.
- Apply rate limits and abuse protection to request submission and activation endpoints.
- Do not create a default administrator account or hardcoded credentials. Initial administrator provisioning must use a documented, authorized, secure process.

## 4. Authentication and Session Management

For local password authentication:

- Hash passwords using Argon2id through a maintained library; never store plaintext passwords.
- Use server-side sessions and random, high-entropy session identifiers.
- Store session identifiers in cookies configured with `HttpOnly`, `Secure` in HTTPS deployments, and an appropriate `SameSite` policy.
- Do not store session IDs, access tokens, or passwords in `localStorage`.
- Rotate the session identifier after login and privilege changes.
- Enforce idle and absolute session expiration.
- Revoke sessions on logout, account suspension, password reset where appropriate, and security-sensitive account changes.
- Implement secure password reset and account activation tokens: cryptographically random, single-use, time-limited, and stored safely (preferably as hashes).
- Avoid responses that reveal whether a particular email address or account exists.
- Apply login rate limiting and monitor repeated failures.
- Require MFA for privileged accounts where supported and approved; consider it a production requirement for sensitive administrative access.
- Use HTTPS in production.

If an approved institutional identity provider is later selected, document its integration and retain application-level authorization checks.

## 5. Authorization and Access Control

Implement role-based access control (RBAC) together with resource-level authorization. A role alone is not sufficient to grant access to every record.

For every protected API operation, verify:
1. The user is authenticated.
2. The account is active and not suspended.
3. The user has the required permission.
4. The user is authorized for the specific institution, Bureau, complaint, attachment, or action.
5. The requested state transition is permitted.

Authorization must apply consistently to:
- Complaint details and search results
- Dashboard counts and analytics
- Exports and reports
- Attachments and downloads
- AI matching candidates and explanations
- Account requests and administrative actions
- Audit logs

Never assume that a user may access a record simply because its identifier is known. Prevent horizontal and vertical privilege escalation. Verify that transfers, suspensions, and role changes update effective access promptly.

### 5.1 Proposed role boundaries

- **Student:** Only their own permitted profile, submissions, and responses/status information, if student-facing complaint features are in approved scope.
- **College representative:** Only records and actions explicitly authorized for the verified college and role.
- **AICTE officer:** Only cases allowed by Bureau membership, assignment, explicit collaboration grants, and field-level sensitivity rules.
- **Verification administrator:** Review account requests and make approved verification decisions; no automatic unrestricted complaint access.
- **System administrator:** Manage approved system and account configuration; no automatic unrestricted access to confidential complaint contents.
- **Audit/compliance reviewer:** Read permitted audit records; no automatic permission to alter complaints or assign roles.

Final role definitions require institutional confirmation.

## 6. Input Validation and Web Application Protection

- Validate all input on the backend using explicit schemas and sensible length/format limits.
- Normalize inputs consistently before validation and processing.
- Use SQLAlchemy/parameterized database operations; never construct SQL by concatenating untrusted input.
- Render user-supplied text safely and use context-appropriate output encoding to prevent XSS.
- Apply a suitable Content Security Policy and other security headers.
- Use CSRF protection for cookie-authenticated state-changing requests.
- Configure CORS with explicit trusted origins; do not use wildcard origins with credentialed requests.
- Limit request sizes and apply rate limiting to authentication, registration, search, uploads, and other abuse-prone endpoints.
- Return generic production error messages; do not expose stack traces, secrets, SQL, or internal paths.
- Validate allowed state transitions on the backend, not only in the UI.
- Keep dependencies updated and scan for known vulnerabilities.

## 7. PostgreSQL and Secrets Management

- Do not expose PostgreSQL directly to the public internet unless an explicitly approved architecture requires it.
- Restrict database network access to trusted application/worker infrastructure.
- Use a dedicated application database role with least privilege; do not run the application as a PostgreSQL superuser.
- Keep credentials and secret keys out of source control and frontend bundles.
- Use environment variables for local development and an appropriate secrets manager for production.
- Use separate credentials and databases/environments for development, testing, and production.
- Encrypt network connections to the database where supported and required.
- Apply migrations through a controlled process and review destructive changes before execution.
- Use transactions, foreign keys, unique constraints, and optimistic concurrency controls where needed to preserve integrity.
- Protect backups, restrict who can restore them, and test restoration regularly.

## 8. Complaint Attachments and File Storage

- Store sensitive files in private storage, not a publicly served directory.
- Check user authorization on every upload, preview, and download.
- Enforce file-size limits and a strict allowlist of permitted file types.
- Validate actual file content, not only the filename extension or browser-provided MIME type.
- Generate safe server-side filenames; prevent path traversal.
- Scan files for malware where suitable scanning infrastructure is available.
- Do not execute uploaded files.
- Avoid permanent public URLs. If signed URLs are used, make them short-lived and restrict their scope.
- Record appropriate attachment metadata and access events without logging sensitive document contents.
- Apply retention and deletion rules approved by the data owner.

## 9. AI Matching and Background Workers

- Run matching in the authorized Python backend/worker; do not expose database credentials or model internals to the browser.
- Limit candidate generation to eligible complaints from verified institutions and apply access rules to the results.
- Do not disclose restricted complaint text, attachments, or sensitive fields through match explanations.
- Treat model output as a suggestion, not a confirmed duplicate or an administrative decision.
- Never automatically merge, close, transfer, assign, or dispose of complaints based only on similarity.
- Require an authorized human decision for related/unrelated review and retain its reason and audit history.
- Record model name/revision, matching pipeline version, scoring configuration, thresholds, and relevant processing status.
- Do not interpret an uncalibrated similarity score as a probability.
- Do not send sensitive complaint data to external AI services without explicit authorization and applicable data-governance approval.
- If a model or worker fails, show a truthful failure/degraded state; never invent matching results or silently switch algorithms.
- Restrict worker permissions to the data and actions required for processing.
- Validate and safely handle queued job payloads; use retries and idempotency to avoid duplicate side effects.

## 10. Audit Logging and Monitoring

Record security-relevant events, such as:
- Login success/failure and logout
- Account request submission and decision
- Account activation, suspension, and role changes
- Complaint creation, assignment, transfer, status change, and disposal
- Overlap review decisions
- Attachment access where required
- Permission failures and significant security events

Audit records should include an actor, action, target/reference, timestamp, and relevant outcome. Avoid unnecessary personal information, passwords, tokens, and full sensitive complaint text.

- Restrict audit-log read access.
- Prevent ordinary users from modifying or deleting audit records.
- Consider append-only or tamper-evident storage for production.
- Monitor repeated authentication failures, authorization denials, and unusual access patterns.
- Define alert handling and incident-response responsibilities before production use.

## 11. Data Privacy, Retention, and Data Residency

- Collect only information necessary for the approved workflow.
- Define data classification and access rules for public, internal, confidential, and sensitive fields.
- Establish approved retention and deletion schedules for complaints, attachments, account requests, sessions, and logs.
- Avoid copying production personal data into development or test environments.
- Do not use real personal or complaint data for testing without authorization.
- Confirm hosting region, backup location, subprocessors, and applicable institutional/legal requirements before selecting production services.
- Document the data owner, authorized purpose, access approvals, and incident contacts.

This document does not assert that any particular cloud service or architecture is approved for AICTE. That must be confirmed by the relevant authority.

## 12. Backups, Availability, and Recovery

- Define backup frequency, retention, encryption, and access restrictions.
- Test restore procedures and record the results.
- Define recovery objectives with the data owner.
- Monitor database health, worker failures, storage capacity, and service availability.
- Use transactions and idempotent job handling to avoid partial or duplicate operations.
- Do not display stale data as current without indicating its state where freshness matters.

## 13. Security Testing Checklist

Before release, test at least the following:

### Authentication
- [ ] Plaintext passwords are never stored.
- [ ] Login rate limiting works.
- [ ] Three consecutive failed password attempts trigger a backend-enforced 60-second temporary lockout, including concurrent-request tests.
- [ ] Required CAPTCHA tokens are verified server-side and invalid/missing tokens fail safely.
- [ ] OTP expires after five minutes, is single-use, and permits at most three incorrect attempts per challenge.
- [ ] Resending an OTP invalidates the previous challenge and send/resend endpoints are rate-limited.
- [ ] OTPs, SMTP credentials, CAPTCHA secrets, and session tokens never appear in logs or frontend bundles.
- [ ] OTP delivery failure never results in successful authentication or a false “sent” message.
- [ ] Development-only OTP bypasses cannot be enabled in production.
- [ ] Session ID changes after login.
- [ ] Logout and suspension revoke sessions.
- [ ] Expired activation/reset tokens are rejected.
- [ ] MFA or an approved alternative is configured for privileged access as required.

### Authorization
- [ ] Anonymous users cannot access protected APIs.
- [ ] Students cannot access other students' restricted records.
- [ ] College representatives cannot access unauthorized institutions.
- [ ] Officers cannot access cases outside their permissions.
- [ ] Pending and rejected applicants cannot access protected dashboards.
- [ ] Users cannot grant themselves roles or approve their own requests.
- [ ] Dashboard counts, exports, search, and downloads enforce the same access rules.

### Application and data
- [ ] SQL injection tests pass.
- [ ] XSS and CSRF protections are tested.
- [ ] CORS is restricted to intended origins.
- [ ] Upload validation and unauthorized file-download tests pass.
- [ ] Secrets are absent from source control and frontend bundles.
- [ ] Database is not unintentionally publicly accessible.
- [ ] Backups can be restored.
- [ ] Audit logs cannot be changed by ordinary users.

### AI and operations
- [ ] Unauthorized complaint data is not exposed through matching results.
- [ ] AI output cannot automatically dispose, merge, or transfer complaints.
- [ ] Worker failure is visible and does not produce fabricated results.
- [ ] Dependencies are scanned and updated.
- [ ] Security-relevant events are monitored.
- [ ] Existing functionality is regression-tested.

Record the test date, environment, outcome, defects, and remediation. Do not claim a test passed unless it was actually run.

## 14. Production Readiness Gate

Do not treat the application as production-ready until the responsible organization has reviewed and approved:
- Identity and account-provisioning procedures
- Role/permission matrix
- Data classification and retention
- Hosting, data residency, backups, and disaster recovery
- Security testing and remediation
- Incident response and monitoring
- Required privacy, legal, procurement, and security approvals

## 15. Implementation Notes

This is a requirements document, not proof of implementation. Before coding changes, inspect the current repository, existing six project specification files, database schema, authentication system, and deployment configuration. Make minimal changes, preserve existing functionality, add tests, and report any unresolved dependency or risk.

## 4.1 Login Protection: CAPTCHA, Failed Attempts, and Temporary Lockout

- Add CAPTCHA/human-verification as a bot-abuse control. It may be risk-based or mandatory according to the approved security policy. Verify CAPTCHA tokens on the Flask backend with the provider; never trust a frontend-only result.
- If CAPTCHA is configured as required and verification fails, is missing, expired, or invalid, stop the login attempt. If the CAPTCHA provider is unavailable, fail securely rather than silently bypassing verification.
- After three consecutive failed password attempts, temporarily block further password authentication for that account for 60 seconds. Enforce this on the backend using server-side time; a frontend countdown is informational only.
- Use atomic database updates/transactions or equivalent concurrency controls so parallel requests cannot bypass the attempt limit.
- Add IP/network and endpoint rate limiting as well as account-based controls. Avoid permanent account lockouts that could let an attacker deny service to another user.
- Use generic error responses that do not disclose whether an account exists. Do not log passwords, OTPs, CAPTCHA secrets, or session tokens.

## 4.2 Email OTP / MFA Requirements

For the initial prototype, OneCase may use email OTP through an approved SMTP or email-delivery provider, without requiring Firebase Authentication. This is an implementation option, not a guarantee of free or production-grade email delivery.

### Authentication sequence

1. User submits email and password.
2. Backend validates required CAPTCHA according to policy and verifies the password.
3. After successful password verification, backend creates an OTP challenge and sends the OTP to the account's verified email address.
4. User submits the OTP.
5. Backend validates the challenge and OTP; only after successful verification may it establish the authenticated session.
6. Backend enforces the user's active status, role, institution/Bureau membership, assignment, and resource permissions on subsequent requests.

Do not initiate OTP delivery for an incorrect password. Do not create a fully authenticated session before the OTP/MFA step succeeds.

### OTP challenge controls

- Generate a six-digit OTP using a cryptographically secure random generator.
- Expire the OTP after five minutes.
- Allow no more than three incorrect attempts per challenge; then invalidate/block that challenge and require a safe new challenge flow.
- OTPs must be single-use. Successful verification consumes the OTP.
- Resending an OTP invalidates the previous challenge/code.
- Rate-limit OTP sends and resends per account and source IP/network; add a cooldown to prevent email flooding and cost abuse.
- Bind the challenge to the intended account and login transaction. Do not allow an OTP for one account or session to verify another.
- Store only a protected OTP verifier (for example, a keyed HMAC using a secret stored outside the database) plus challenge metadata, not plaintext OTPs. Keep the key in an environment secret or approved secrets manager.
- Never include OTP values in application logs, audit logs, analytics, error reports, URLs, or frontend bundles. Do not expose the OTP in the UI outside an explicitly isolated local-development test mode.
- Use generic responses and avoid account enumeration through OTP-send endpoints.
- Clear expired challenges and define safe cleanup/retention behavior.
- OTP/email verification proves control of the email inbox at that time; it does not prove student enrollment, employment, official designation, or authorization to access a particular complaint.

### Low-cost email delivery for development

- Gmail SMTP with a Google App Password may be considered for a small prototype if permitted by the account/provider terms and current sending limits. A free tier is not guaranteed, sending is not guaranteed, and production suitability must be assessed separately.
- Enable the required account security settings and use an App Password where supported; never use or store the user's normal Gmail password in the application.
- Store SMTP host, port, sender address, username, and App Password in environment variables or a secrets manager. Keep `.env` out of version control and provide a safe `.env.example` containing placeholder names only.
- Use TLS for SMTP connections and handle provider errors without leaking credentials or OTPs.
- Add delivery timeouts, safe retry behavior, and user-facing failure handling. If email delivery fails, do not report that an OTP was sent or authenticate the user; allow a rate-limited retry.
- Before production, evaluate an approved transactional email provider, verified sender/domain requirements, sending limits, deliverability, privacy terms, cost, and data-location requirements.
- Do not use fake OTPs, fixed OTPs, or a publicly visible development bypass in production. Any test-only bypass must be isolated to automated tests/local development, guarded by explicit environment configuration, and impossible to enable accidentally in production.

### MFA policy

- Require MFA for privileged accounts when mandated by the approved policy; prefer authenticator-based TOTP or an approved stronger method for administrators and sensitive roles where feasible.
- Email OTP may be a practical prototype option but is generally weaker than phishing-resistant authentication and depends on the security of the email account.
- Recovery and factor-reset procedures must verify the requester and be audited. Do not let an applicant reset MFA or elevate roles solely through a self-reported email address.

## 4.3 Authentication Configuration and Failure Behavior

- Keep CAPTCHA and email delivery behind backend interfaces/configuration so providers can be changed without rewriting business logic.
- Use explicit configuration flags for local development, testing, and production. Production must fail startup or fail the relevant operation safely when required security settings are missing; it must not silently disable CAPTCHA/MFA or use development OTPs.
- Never expose provider secrets to React/Vite environment variables that are bundled into the browser. Only public CAPTCHA site keys may be placed in the frontend; secret keys remain server-side.
- Document which controls are implemented, configured, and tested separately. A configured-looking UI is not evidence that backend verification works.
