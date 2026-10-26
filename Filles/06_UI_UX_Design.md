# OneCase — UI/UX Design

Version: 1.1 | Date: 26 October 2026 | Status: implementation design specification

## 1. Design purpose

Help an authorized officer answer five questions quickly: Which institution is involved? Who owns this case? What action occurred? Could another bureau be handling a related issue? What must happen next?

Use the three supplied components as design references: `app-1.tsx` dashboard, `modern-login-signup.tsx` authentication card, and `interactive-logs-table-shadcnui.tsx` expandable history. Preserve their intended layouts while replacing generic project/account/service-log content with actual OneCase records.

## 2. Information architecture

| Screen | Route | Primary task |
| --- | --- | --- |
| Officer sign-in | `/officer/login` | Authenticate a provisioned officer |
| Dashboard | `/dashboard` | Identify workload, overdue cases, and pending overlap review |
| Complaint list | `/complaints` | Search/filter cases |
| Complaint detail | `/complaints/:id` | Inspect issue, owner, next action, evidence, and history |
| Institution directory | `/institutions` | Find the canonical institution |
| Institution detail | `/institutions/:id` | View permitted cross-bureau complaint history |
| Overlap queue | `/overlaps` | Review possible relationships |
| Overlap comparison | `/overlaps/:id` | Compare two cases and record a decision |
| Alerts | `/alerts` | Act on assignment, deadline, and review notifications |
| Action logs | `/audit-logs` | Inspect authorized event history |

Transfer is a case-detail action with recorded history, rather than an extra decorative page. Show only implemented, authorized navigation. User provisioning and policy configuration need only the minimal authorized controls required by the core solution.

## 3. Visual system

- Use Tailwind and shadcn semantic tokens for background, foreground, card, border, muted text, primary action, warning, and destructive feedback.
- Dashboard and history support light and dark themes. Preserve the source authentication screen's dark visual treatment with readable contrast.
- Use restrained cards, thin borders, consistent rounding, and an 8px-based spacing rhythm, with smaller 4px adjustments where needed.
- Use the existing project font or a locally available sans-serif stack. Use tabular numerals for counts and timestamps.
- Apply status labels and icons alongside color. Color alone must not distinguish case states or severity.
- Use approved OneCase branding or a simple text mark. Do not invent AICTE logos or fill officer profiles with stock photos.
- Default dates/times to Asia/Kolkata and visibly label the timezone. Expanded events also expose the original UTC timestamp.

## 4. Officer authentication

Preserve the black background, white dot animation, vignette, centered dark card around 400px wide, subtle border, and full-width buttons.

Content:

- Brand: “OneCase”.
- Heading: “Officer sign in”.
- Description: “Access your authorized bureau workspace and case records.”
- Labelled email and password fields, password visibility toggle, and “Sign in” action.
- Generic failure feedback, submitting state, retry behavior, and session-expiry message.

The source login form prevents submission without authenticating; replace it with a working backend call. Remove Vercel copy, consumer social-login buttons, and public sign-up. Accounts are provisioned by an authorized administrator. Do not show unsupported SSO or recovery actions.

Bundle Three.js rather than injecting a CDN script. Use a typed background component, correct shader configuration, container-aware sizing, bounded pixel ratio, and full cleanup of listeners/resources. Reduced motion and unavailable WebGL use a static dot pattern. The decorative canvas is hidden from assistive technology and cannot intercept input.

Use mobile gutters and a scrollable viewport so short screens and the on-screen keyboard do not obscure the form.

## 5. Dashboard

Preserve the source collapsible sidebar, sticky header, four KPI cards, wide area chart, and lower two-card grid. Retain `min-w-0` on the sidebar inset. Recreate missing sidebar/data helpers with OneCase feature components and backend adapters; do not leave unresolved `app-1-utils` imports.

### Header and filters

Show authenticated officer name and bureau, institution/case search, persistent notifications, and profile/logout controls. Provide compact bureau, institution, region, category, and date filters. Store filters in the URL; show applied scope and freshness.

### KPI row

1. Total complaints.
2. Active complaints.
3. Overdue complaints.
4. Potential overlap pairs awaiting review.

Use PRD definitions. Counts come from the backend and drill into equivalent scoped lists. Never show fabricated deltas. Overlap counts describe pairs, not complaint counts.

### Trend chart

Title: “Complaints received and disposal events”. Preserve the source eight-week dashed received series and filled disposal series, legend, and tooltip. Explicitly label event-period scope and weekly boundaries. Provide an accessible summary/table. Distinguish a true zero from a failed request.

### Lower cards

**Cases requiring attention:** case reference, institution, category, status, bureau/officer, next action, and due date. Preserve the source progress treatment only as “Deadline window elapsed” when a valid origin and due date exist; show overdue duration separately. Never display a fictional complaint-completion percentage.

**Recent case actions:** real server-recorded events showing actor, action, case reference, and timestamp, with permission-safe detail links. Use the same event source as case history.

## 6. Complaint and institution views

Complaint list columns: reference, institution, category, status, owner, receipt date, and deadline condition. Search by reference, institution name, and verified AICTE identifier. Filters and pagination run server-side.

Complaint detail uses a clear header containing reference, status, institution link, and current bureau/officer. Organize the body into overview, actions/history, evidence, and related cases. Keep next action and due date visible near the owner.

Registration uses an institution picker, category, description, receipt date, priority, accountable owner, and applicable deadline. Explain validation beside the field. Prevent double submission and focus the first invalid field. A saved case displays its permanent reference.

Institution detail shows verified identity and permitted complaint history across bureaus. Mark unverified identifiers. Never imply that one institution's multiple complaints prove misconduct or duplication.

## 7. Overlap review

Display two cases side by side on desktop and stacked on mobile. Show institution identity, descriptions, categories, incident periods where known, bureaus, owners, current actions, matching terms, and text-similarity score.

Use the label “Possible overlap — review required”. Show the required algorithm's semantic retrieval score, Cross-Encoder relevance signal, structured evidence, final hybrid score, and high/uncertain triage band in an expandable explanation. Label normalized signals accurately; neither raw logits nor normalized relevance scores are probabilities of duplication. High means prioritized human review, not automatic confirmation. Low-scoring machine results are not displayed as officer rejection.

Provide “Mark related” and “Mark unrelated”, both with a required reason and server permission check. Pending review remains available when evidence is insufficient. Preserve original cases and show previous decisions. Display matching-stage status (retrieving, reranking, scoring, completed, failed) without falsely reporting zero matches during processing. Evidence details include model/scoring version, evaluated complaint revisions, and whether long text was truncated or chunked. Matching explanations must distinguish actual structured/lexical evidence from neural model attribution.

Do not label similarity as a probability of guilt. Do not offer automatic merging or automatic disposal. If either case is restricted, do not expose it through the pair's text, count, or filters.

## 8. Transfer interaction

Use a case-detail dialog or sheet with current owner, receiving bureau/officer, reason, and a concise confirmation summary. Disable invalid recipients and submit against the displayed complaint version.

Success shows the committed new owner and recorded event. A stale-version conflict explains that another officer changed the case and requests review of refreshed data. Recipient acknowledgement appears as a separate history item. No intermediate screen may imply that the case has no owner.

### SLA, priority, and bottleneck presentation

Show on-track/due-soon/overdue as a deadline condition distinct from complaint status. Deadline details expose applicable rule, timezone, business calendar, holidays, and recorded pause periods. A pause requires a permitted action and reason; status alone does not pause the clock. Identify illustrative demo rules visibly.

Sort the attention/work queue by configured urgency, priority, due date, receipt date, and case ID. Add concise reason badges for overdue work and rule-defined bottlenecks: long assignment acknowledgement, repeated transfers, or overdue bureau backlog. Place flags in existing attention/alert views; do not add an unrelated feature page.

## 9. Expandable action logs

Preserve compact rows, severity badges, chevron rotation, animated expansion, search header, filter count, and 280px desktop filter panel.

Replace infrastructure fields as follows:

| Original | OneCase presentation |
| --- | --- |
| Service | Bureau/cell |
| Message | Action summary |
| HTTP status | Action outcome: succeeded, failed, denied |
| Duration | Case age at action, only if derived from recorded dates |
| Expanded message | Authorized reason, change details, transfer/review context |
| Tags | Recorded event/category labels |

Rows show date/time, case reference, bureau, actor, summary, severity, and outcome. Keep severity, outcome, and complaint status visibly distinct. Expanded fields include safe before/after values, reasons, actor snapshot, and UTC timestamp. Never expose secrets or unrestricted complaint details.

Search/filter by date, case, institution, actor, bureau, event type, severity, and outcome. Use OR inside a category and AND across categories. Derive facets and counts from authorized backend scope rather than the loaded page. Use stable cursor pagination and server sorting.

Use one expanded row at a time, stable event keys, `aria-expanded`, and `aria-controls`. Keep links outside row-toggle buttons. On mobile use a filter sheet and stacked rows. Respect reduced motion and cap animation stagger delays.

## 10. Common feedback and accessibility

| State | Required behavior |
| --- | --- |
| Loading | Layout-preserving skeleton and meaningful status label |
| Empty | Explain absence of records and show a permitted next action |
| No matches | Offer clear filters without inventing sample rows |
| Error | Preserve context and offer retry |
| Stale | Retain data with visible last-updated warning |
| Forbidden | Give a concise access message without leaking protected content |
| Conflict | Refresh current state and require review before resubmission |
| Processing | Distinguish queued matching from completed “no suggestions” |

Target WCAG 2.2 AA and verify it; do not claim conformance from design alone. Require visible focus, descriptive labels, keyboard navigation, appropriate dialog focus/return behavior, non-color indicators, reduced motion, readable contrast, and no page-level horizontal overflow. Icon-only controls require accessible names. Status announcements must not repeatedly interrupt screen-reader users.

## 11. Acceptance checklist

- Core journey works through actual APIs with database persistence.
- No generic project, Vercel, payment-service, fake officer, random count, or placeholder link remains.
- Verify 360px mobile, 768px tablet, and 1440px desktop layouts, short viewports, and browser zoom.
- Verify sign-in without WebGL, reduced-motion history, keyboard-only transfer/review, and accessible chart alternatives.
- Counts and drill-downs agree with PRD definitions; restricted fields stay absent from responses and UI.
- All visible actions have implemented behavior and correct loading/failure states.
- Required semantic retrieval, Cross-Encoder, hybrid triage, and human decision states are represented; a TF-IDF-only run is not labelled as the completed target algorithm.

Related: [PRD](01_PRD.md), [Architecture](03_Architecture.md), [Workflow](04_Workflow.md), [Algorithm](05_Algorithm.md).
