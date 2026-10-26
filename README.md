# OneCase

> **AICTE Intelligent Institution Complaint Coordination & Tracking System**  
> *Problem Statement: SIH26264*  
> Tagline: *"One Institution. One View. Coordinated Action."*

---

## 1. Overview & Purpose

**OneCase** is an officer-facing coordination and tracking platform designed for the **All India Council for Technical Education (AICTE)**. It establishes unified case management across the **Regulation Bureau (RB)**, the **Public Grievance Redressal Cell (PGRC)**, and other authorized Bureaus and Cells.

### Zero-Mock Policy & Traceability
OneCase strictly adheres to real data persistence and verifiable computations:
- **No Mock or Fabricated Records**: Dashboard metrics, complaints, institutions, notifications, and audit logs are fetched directly from actual database records via authorized backend queries.
- **Explicit Empty States**: When the database contains no records, clear empty states are displayed instead of placeholder or sample content.
- **Transparent Degradation**: If the database, AI model, or background worker is unavailable, the application displays an explicit error or degraded state rather than silently substituting fabricated results.
- **Authorized Provisioning Only**: Users and institutions are created strictly through authorized administrative workflows. No default administrator credentials or synthetic dummy records are seeded on startup.

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
                  PostgreSQL (Primary)
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
| **Frontend** | React 19, TypeScript, Vite, Tailwind CSS 4 | Officer application with reactive state & accessible primitives |
| **Routing** | React Router v7 | Protected workspace routes & officer authentication |
| **State & API** | TanStack React Query v5 | Server state caching, optimistic updates, query invalidation |
| **Icons & Charts**| Lucide React, Recharts | Official branding, KPI cards, 8-week trend area charts |
| **Backend API** | Python 3, Flask 3.1, Pydantic v2 | Modular REST API with strict request validation & RBAC |
| **Primary Database** | PostgreSQL with `psycopg3` driver | ACID transactions, foreign keys, version constraints, SKIP LOCKED leasing |
| **Migrations** | Alembic via Flask-Migrate | Declarative, versioned schema management (schema only, no fake data) |
| **Security** | Argon2id, CSRF token validation, Same-Site cookies | Session management, password hashing, access control |
| **AI / ML** | `sentence-transformers`, `scikit-learn`, `NumPy` | Two-stage retrieve-and-rerank hybrid matching pipeline |
| **Background** | Python worker with database job leasing | Durable async processing, idempotent retries |

---

## 4. Application Routes & Screens

1. **Officer Sign In**: `/officer/login`
2. **Dashboard**: `/dashboard` (KPI cards, 8-week area chart, attention list, recent activity, empty state)
3. **Complaint Directory**: `/complaints` (Search, filter by Bureau, Category, Status, Region, CSV export)
4. **Complaint Detail**: `/complaints/:id` (Case overview, action history, evidence uploads, transfers, status lifecycle)
5. **Institution Directory**: `/institutions` (Canonical institution records, verified AICTE IDs, Add Institution modal)
6. **Institution Detail**: `/institutions/:id` (Cross-bureau complaint history for the verified institution)
7. **Overlap Review Queue**: `/overlaps` (Triage bands, candidate pairs, hybrid scores, human review required)
8. **Overlap Comparison**: `/overlaps/:id` (Side-by-side complaint diff, signal breakdown, recorded decisions)
9. **Alerts Centre**: `/alerts` (Persistent assignment, escalation, and review notifications)
10. **Action History & Audit**: `/audit-logs` (Immutable event log with expandable before/after changes)
11. **Reports**: `/reports` (Cohort-based analytics, active case ageing, CSV exports)

---

## 5. Local Setup & Execution

### Prerequisites
- Python 3.10+
- Node.js 18+ and npm
- PostgreSQL database (or Docker)

### 1. Database Configuration
Configure `.env` in the project root:
```env
DATABASE_URL=postgresql+psycopg://username:password@localhost:5432/onecase
COOKIE_SECURE=false
SECRET_KEY=generate_a_random_32_byte_hex_string_here
STORAGE_PATH=/path/to/secure/storage/documents
MODEL_PATH=/path/to/pinned/models
```

### 2. Backend Initialization
```bash
# Navigate to backend directory
cd backend

# Initialize and activate virtual environment
python -m venv ../.venv
..\.venv\Scripts\activate      # Windows (or: source ../.venv/bin/activate on Linux/macOS)

# Install requirements
pip install -r requirements.txt
pip install numpy scipy scikit-learn

# Apply database migrations (creates schema, indexes, and constraints only)
python -m flask --app app db upgrade

# Initialize official bureau configuration (RB, PGRC)
python -m flask --app app init-system
```

### 3. Provisioning Authorized Accounts & Institutions
```bash
# Provision an administrator account
python -m flask --app app create-user --name "Admin Name" --email "admin@aicte.gov.in" --role admin

# Provision Bureau Leads and Officers
python -m flask --app app create-user --name "RB Lead" --email "rb.lead@aicte.gov.in" --role lead --bureau RB
python -m flask --app app create-user --name "PGRC Lead" --email "pgrc.lead@aicte.gov.in" --role lead --bureau PGRC

# Provision a Cross-Bureau Reviewer
python -m flask --app app create-user --name "Triage Reviewer" --email "reviewer@aicte.gov.in" --role reviewer

# Add an authorized institution to the canonical directory
python -m flask --app app add-institution --name "Institution Name" --external-id "1-123456789" --region "North" --address "Campus Address, City" --verified
```

### 4. Running the Application
```bash
# Terminal 1: Run Flask backend
cd backend
python -m flask --app app run --port 5000

# Terminal 2: Run background worker
cd backend
python worker.py

# Terminal 3: Run Vite frontend development server
cd frontend
npm install
npm run dev
```

The application will be accessible at **`http://127.0.0.1:5173/`**.

---

## 6. Hybrid Semantic Complaint Matching

### Algorithm Pipeline
1. **Normalization**: Unicode NFKC normalization, whitespace cleanup, PII redaction (emails, phone numbers).
2. **Eligibility Gating**: Candidate complaints must share the same verified AICTE institution.
3. **Dense Embedding**: Encoded locally with pinned `sentence-transformers/all-MiniLM-L6-v2` (384-d L2-normalized).
4. **Top-K Cosine Retrieval**: Exact institution-scoped dot product retrieval ranking.
5. **Cross-Encoder Reranking**: Jointly scored with pinned `cross-encoder/ms-marco-MiniLM-L6-v2`.
6. **Hybrid Scoring**: Combines semantic cosine, sigmoid-transformed reranker logits, and category agreement:
   $$H = 0.35 \cdot N_{\text{sem}}(\text{cosine}) + 0.55 \cdot \sigma(\text{logit}) + 0.10 \cdot \mathbf{1}_{[\text{cat}_A = \text{cat}_B]}$$
7. **Triage Classification**:
   - **High Relevance** ($H \ge 0.72$): Prioritized for human review.
   - **Uncertain Relevance** ($0.45 \le H < 0.72$): Flagged with uncertainty indicators.
   - **Low Relevance** ($H < 0.45$): Retained as machine evidence.
8. **Human Decision**: Surfaced suggestions require explicit authorized officer decisions (`related` / `unrelated` / `pending`). The system never automatically merges or disposes complaints.

---

## 7. Automated Testing & Verification

Run the full pytest suite (14 automated tests covering workflows, permissions, optimistic locking, and matching evaluation):
```bash
cd backend
python -m pytest tests/test_workflows.py tests/test_matching.py
```

Run the matching evaluation benchmark:
```bash
cd backend
python evaluate_matching.py
```
