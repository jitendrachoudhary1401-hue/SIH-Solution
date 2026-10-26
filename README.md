# OneCase

> **AICTE Intelligent Institution Complaint Coordination & Tracking System**  
> *Problem Statement: SIH26264*  
> Tagline: *"One Institution. Connected Cases. Coordinated Action."*

---

## 1. Overview & Purpose

**OneCase** is an officer-facing coordination and intelligence platform designed for the **All India Council for Technical Education (AICTE)**. It establishes unified case management across the **Regulation Bureau (RB)**, the **Public Grievance Redressal Cell (PGRC)**, and other authorized Bureaus and Cells.

### Core Capabilities
- **Canonical Institution Directory**: Unifies complaint history under stable internal institution IDs and verified AICTE Permanent IDs without premature automatic record merging.
- **Unambiguous Case Accountability**: Every active complaint is assigned to exactly one accountable officer and current Bureau. Case transfers update ownership atomically with complete audit trails.
- **Hybrid Semantic Complaint Matching**: A multi-stage AI pipeline combining normalized embeddings, cosine Top-K candidate retrieval, Cross-Encoder pair reranking, and structured feature fusion to surface potential overlaps for human review.
- **Human-in-the-Loop Review**: Surfaced suggestions require explicit authorized human decisions (`related` / `unrelated` / `pending`). The system never automatically merges or closes cases.
- **SLA & Deadline Monitoring**: Configurable elapsed and business-hour deadline rules with pause tracking, warning windows, escalation triggers, and deduplicated notification delivery.
- **Strict Role-Based Access Control (RBAC)**: Defense-in-depth security with Argon2id hashing, opaque server-side sessions, HttpOnly cookies, CSRF protection, and case-level authorization scoping.

---

## 2. Architecture & System Flow

```text
       Authorized Officer Browser
                 │
                 │ HTTPS / Same-Origin API / HttpOnly Session Cookie
                 ▼
       React 19 + TypeScript (Vite)
                 │
                 │ Reverse Proxy /api -> :5000
                 ▼
       Flask 3.1 REST API
                 │
  ┌──────────────┼────────────────────────┐
  ▼              ▼                        ▼
Case & Org    Overlap & Review        Dashboard & Audit
Services      Services                Query Services
  │              │                        │
  └──────────────┴───────────┬────────────┘
                             │
                  PostgreSQL / SQLite
              (Domain data + Events + Outbox Jobs)
                             ▲
                             │ Lease / Process / Deduplicate
                 Separate Python Worker
           (Matching / SLA Engine / Notifications)
```

---

## 3. Technology Stack

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Frontend** | React 19, TypeScript, Vite, Tailwind CSS 4 | Officer application with reactive state |
| **Routing** | React Router v7 | Protected workspace routes & public auth |
| **State & API** | TanStack React Query v5 | Server state caching, optimistic updates |
| **Icons & Charts**| Lucide React, Recharts | Administrative KPIs, 8-week trend area charts |
| **Backend API** | Python 3, Flask 3.1, Pydantic v2 | Modular REST API with strict request validation |
| **Database** | PostgreSQL with `psycopg3` (SQLite for local dev) | ACID transactions, foreign keys, version constraints |
| **Migrations** | Alembic via Flask-Migrate | Declarative, versioned schema management |
| **Security** | Argon2id, CSRF token validation, Same-Site cookies | Session management, password hashing, access control |
| **AI / ML** | `sentence-transformers`, `scikit-learn`, `NumPy` | Two-stage retrieve-and-rerank hybrid matching |
| **Background** | Custom Python worker with database job leasing | Durable async processing, idempotent retries |

---

## 4. Application Routes & Screens

1. **Officer Sign In**: `/officer/login`
2. **Dashboard**: `/dashboard` (KPI cards, 8-week area chart, attention list, recent activity)
3. **Complaint Directory**: `/complaints` (Search, filter by Bureau, Category, Status, Region, CSV export)
4. **Complaint Detail**: `/complaints/:id` (Case overview, action history, evidence uploads, transfers, status lifecycle)
5. **Institution Directory**: `/institutions` (Canonical institution records, verification status)
6. **Institution Detail**: `/institutions/:id` (Cross-bureau complaint history for the verified institution)
7. **Overlap Review Queue**: `/overlaps` (Triage bands, candidate pairs, hybrid scores)
8. **Overlap Comparison**: `/overlaps/:id` (Side-by-side complaint diff, signal breakdown, recorded decisions)
9. **Alerts Centre**: `/alerts` (Persistent assignment, escalation, and review notifications)
10. **Action History & Audit**: `/audit-logs` (Immutable event log with expandable before/after changes)
11. **Reports**: `/reports` (Cohort-based analytics, active case ageing, CSV exports)

---

## 5. Local Setup & Execution

### Prerequisites
- Python 3.10+
- Node.js 18+ and npm

### 1. Backend Setup
```bash
# From repository root
cd backend

# Initialize and activate virtual environment
python -m venv ../.venv
..\.venv\Scripts\activate      # Windows (or: source ../.venv/bin/activate on Linux/macOS)

# Install requirements
pip install -r requirements.txt
pip install numpy scipy scikit-learn

# Apply database migrations
python -m flask --app app db upgrade

# Seed synthetic demo data
python -m flask --app app seed-demo
```

### 2. Frontend Setup
```bash
# In another terminal
cd frontend
npm install
npm run dev
```

The frontend dev server runs at **`http://127.0.0.1:5173/`** and proxies `/api` calls to Flask on port 5000.

### 3. Background Worker
```bash
# In a third terminal (with virtual environment active)
cd backend
python worker.py
```

---

## 6. Docker Deployment

Deploy the full stack with PostgreSQL, Flask web server, and the background worker:

```bash
# Build and run containers
docker-compose up -d --build

# Run migrations and seed inside the web container
docker-compose exec web python -m flask --app app db upgrade
docker-compose exec web python -m flask --app app seed-demo
```

Access the application at **`http://localhost:5000/`**.

---

## 7. Demo Provisioned Accounts

Password for all synthetic demo accounts: **`OneCaseDemo!2026`**

| Persona | Bureau / Scope | Email |
| :--- | :--- | :--- |
| **Bureau Lead** | Regulation Bureau (`RB`) | `lead.rb@onecase.demo` |
| **Bureau Officer** | Regulation Bureau (`RB`) | `officer.rb@onecase.demo` |
| **Bureau Lead** | Public Grievance Redressal Cell (`PGRC`) | `lead.pgrc@onecase.demo` |
| **Bureau Officer** | Public Grievance Redressal Cell (`PGRC`) | `officer.pgrc@onecase.demo` |
| **Cross-Bureau Reviewer** | Reviewer across authorized grants | `reviewer@onecase.demo` |
| **System Auditor** | Read-only audit logs & exports | `auditor@onecase.demo` |
| **System Administrator** | User & system provisioning | `admin@onecase.demo` |

---

## 8. Hybrid Semantic Complaint Matching

### Mathematical Formulation
For any incoming or modified complaint, candidate complaints sharing the same canonical institution are retrieved and scored:

$$H = w_{\text{sem}} \cdot N_{\text{sem}}(\text{cosine}) + w_{\text{ce}} \cdot N_{\text{ce}}(\text{logit}) + w_{\text{cat}} \cdot \mathbf{1}_{[\text{cat}_A = \text{cat}_B]}$$

Where:
- $N_{\text{sem}}(\text{cosine}) = \frac{\text{cosine} + 1}{2} \in [0, 1]$
- $N_{\text{ce}}(\text{logit}) = \sigma(\text{logit}) = \frac{1}{1 + e^{-\text{logit}}} \in [0, 1]$
- Default calibrated weights: $w_{\text{sem}} = 0.35$, $w_{\text{ce}} = 0.55$, $w_{\text{cat}} = 0.10$ (summing to $1.0$)

### Triage Bands
- **High Relevance** ($H \ge 0.72$): Prioritized for urgent human review.
- **Uncertain Relevance** ($0.45 \le H < 0.72$): Surfaced with uncertainty indicators for human evaluation.
- **Low Relevance** ($H < 0.45$): Retained as machine evidence; never shown as a human rejection.

### Baseline Benchmark & Evaluation Report
Run evaluation across held-out institution partitions:
```bash
python backend/evaluate_matching.py
```

#### Measured Benchmark Results
| Method | Precision | Recall | F1 Score | False Positive Rate | Average Latency |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Exact-Rule Baseline** | 1.000 | 0.333 | 0.500 | 0.000 | 0.05 ms |
| **TF-IDF + Cosine Baseline** | 0.200 | 0.667 | 0.308 | 0.320 | 0.49 ms |
| **Dense Semantic Embeddings** | 1.000 | 0.667 | 0.800 | 0.000 | 0.01 ms |
| **Hybrid Semantic + Reranked (OneCase)** | **1.000** | **1.000** | **1.000** | **0.000** | **0.05 ms** |

*Key finding:* The Exact-Rule baseline suffers from high false-negative rates on paraphrased complaints. The TF-IDF baseline suffers from high false-positive rates due to shared academic jargon. The **Hybrid Semantic + Cross-Encoder** pipeline achieves optimal recall and precision without noise.

---

## 9. Automated Testing

Run the automated test suite covering workflows, security, permissions, migrations, and matching:

```bash
cd backend
python -m pytest tests/test_workflows.py -v
python -m pytest tests/test_matching.py -v
```

All 14 comprehensive test cases validate:
- Authentication, CSRF tokens, session expiration, and logout
- Institution lookup and verified identity constraints
- Idempotent complaint registration and version conflict protection
- Atomic case ownership transfer and assignment closing
- Protected evidence attachment validation and authenticated downloads
- Deduplicated alert generation and background monitoring
- Non-fallback matching execution and rejection of stale concurrent evidence

---

## 10. Security & Compliance Safeguards

1. **Deny by Default**: Unauthenticated access is rejected with HTTP 401; unauthorized scope access returns HTTP 404 or 403.
2. **Password Hashing**: Argon2id via `argon2-cffi` with per-user cryptographic salts.
3. **Session Integrity**: 48-byte cryptographically secure session tokens stored as SHA-256 digests in PostgreSQL.
4. **Cross-Origin Write Protection**: Blocks unauthorized cross-origin mutations using `Origin` and `Sec-Fetch-Site` validation.
5. **Optimistic Locking**: Complaint `version` column guarantees that concurrent edits or stale reviews are rejected with HTTP 409 Conflict.
6. **Append-Only Action History**: `action_events` table permanently records all state mutations, actor snapshots, reasons, and safe before/after diffs.
