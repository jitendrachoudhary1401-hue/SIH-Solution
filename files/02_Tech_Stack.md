# OneCase — Tech Stack

Version: 1.1 | Date: 26 October 2026 | Status: target implementation stack

## 1. Decision

Use a React/Vite TypeScript frontend and a Flask modular backend with PostgreSQL. Keep matching in the Python backend package and run durable background jobs in a separate worker process. Implement the Hybrid Semantic Complaint Matching pipeline selected in `AICTE_ACITS_Algorithms.md`; TF-IDF remains a comparison baseline. This supports the supplied shadcn/Tailwind components without changing the core project purpose.

This is a specification for a new implementation. An existing repository should be inspected before replacing working infrastructure. Exact dependency versions must be selected together, locked, and verified during setup; no untested version combination is prescribed here.

## 2. Selected technologies

| Layer | Selection | Responsibility |
| --- | --- | --- |
| Frontend | React + TypeScript + Vite | Officer application and typed UI |
| Routing | React Router | Public auth routes and protected workspace |
| Styling | Tailwind CSS | Responsive layout and design tokens |
| UI primitives | shadcn/ui using its supported primitive dependencies | Forms, sidebar, dialog, sheet, tables, badges |
| Server state | TanStack Query | Fetching, invalidation, retries, stale state |
| Forms | React Hook Form + Zod | Client form state and validation feedback |
| Charts | Recharts with shadcn chart wrappers | Received/disposal trends and report views |
| Icons | lucide-react | Functional interface icons |
| Log transitions | framer-motion | Source-compatible row and filter animations |
| Auth background | Three.js + matching TypeScript declarations | Optional decorative dot field with static fallback |
| API | Python + Flask | Authentication, authorization, workflows, reports |
| Persistence | SQLAlchemy + Alembic | Models, transactions, schema migration |
| Database | PostgreSQL + psycopg | Shared multi-user source of truth |
| Input schemas | Pydantic | Explicit server-side request/response validation |
| Passwords | Argon2id through argon2-cffi with library-managed random salts | Password hashing and verification |
| Matching baseline | scikit-learn + SciPy | TF-IDF sparse features and cosine similarity |
| Required semantic matching | sentence-transformers + compatible PyTorch/Transformers | Sentence embeddings and Cross-Encoder inference |
| Candidate retrieval | L2-normalized embeddings, NumPy/scikit-learn exact cosine top-k within verified institution | Shortlist candidates before pairwise reranking |
| Hybrid ranking | Versioned Python scoring and triage configuration | Normalize model outputs, combine structured evidence, apply validated thresholds |
| SLA calculations | Python timezone-aware datetime + zoneinfo and versioned calendar rules | Business/elapsed-time deadlines, holidays, approved pauses |
| Async work | Database-backed job/outbox tables + Python worker | Matching, notifications, exports, deadline checks |
| Documents | Private filesystem in demo; private S3-compatible storage for deployment | Attachment bytes behind authorized access |
| API contract | OpenAPI maintained with backend schemas | Client/server agreement |
| Frontend checks | ESLint, TypeScript, Vitest, React Testing Library | Static checks and meaningful UI tests |
| Backend checks | pytest | Workflow, permission, transaction, algorithm tests |
| End-to-end | Playwright | Officer journey and responsive/accessibility checks |
| Packaging | Docker Compose for reproducible local deployment | Web, API, worker, database |

SQLite is permitted only for isolated local experiments. Shared demos and concurrency/integration tests use PostgreSQL. Redis and a distributed task framework are not baseline requirements. Exact institution-scoped vector search is the initial retrieval implementation; a separate vector database is unnecessary until measured scale requires one. Top-k retrieval remains a required stage even when implemented without approximate indexing.

### Required model configuration

- Starting embedding candidate: `sentence-transformers/all-MiniLM-L6-v2`; validate its language coverage and complaint performance before acceptance.
- Cross-Encoder: select a compatible pair-relevance model through labelled evaluation. `cross-encoder/ms-marco-MiniLM-L6-v2` is a starting candidate, not a verified AICTE-specific model.
- Pin model revisions/tokenizers and download artifacts during controlled setup. Run inference locally in the worker; do not send complaints to an external model API.
- Keep raw and normalized scores separately. A reranker's logits are not automatically probabilities; its output interpretation belongs in the manifest.
- Record truncation/chunking, embedding dimensions, top-k, scoring weights, thresholds, and model/index versions. Benchmark CPU first; record any GPU requirement based on measurement.
- Do not silently fall back to TF-IDF if required inference fails. Mark the matching run failed/degraded explicitly and retry.

## 3. Application organization

```text
onecase/
  frontend/
    src/
      app/                  # Router, providers, shell
      components/ui/        # Reusable shadcn primitives
      features/
        auth/
        dashboard/
        institutions/
        complaints/
        overlaps/
        notifications/
        reports/
        audit/
      lib/                  # API client, date formatting, utilities
      types/                # Shared generated/validated contracts
      styles/
  backend/
    app/
      api/                  # Thin route handlers
      auth/                 # Sessions and authorization policy
      models/
      schemas/
      services/             # Transactional domain operations
      matching/             # Normalize, embed, retrieve, rerank, hybrid-score, triage
      jobs/
    migrations/
    tests/
    worker.py
  docs/
  compose.yaml
  .env.example
```

These are repository-relative proposed paths. Preserve an established alias/layout when integrating into an existing project. Configure `@/` consistently in the bundler and TypeScript. Primitive location is a convention, not a requirement to duplicate folders.

## 4. Setup requirements

1. Select supported Node.js and Python runtimes; record them in project tooling.
2. Scaffold Vite with React TypeScript only if a frontend is absent.
3. Configure Tailwind using the Vite integration appropriate to the selected major version. Do not combine old and new installation recipes.
4. Initialize shadcn for the existing project and configure aliases, CSS tokens, and primitive paths.
5. Add only missing primitives: avatar, badge, button, card, chart, progress, sidebar, input, label, separator, skeleton, tooltip, sheet, dialog, select, textarea, and table as required.
6. Install feature dependencies using the project's package manager and commit the lockfile.
7. Create the Python environment, lock dependencies, and configure PostgreSQL credentials through environment variables.
8. Run migrations, provision an initial administrator securely, and load explicitly synthetic demo fixtures through a separate command.
9. Start API and worker separately. Serve the browser and `/api` through one origin in deployment; use a Vite proxy for local development.
10. Run type checks, tests, production build, and a PostgreSQL integration smoke test.

## 5. Authentication and state decisions

Use opaque server-side sessions stored in PostgreSQL; store a digest of the session token and send the token only in an HttpOnly cookie. Configure Secure in HTTPS deployment, appropriate SameSite behavior, CSRF validation, expiration, rotation, and logout revocation. Never persist credentials or session tokens in localStorage.

TanStack Query owns fetched domain data. Local React state owns expansion, dialogs, and transient inputs. URL parameters own shareable filters. Clear identity-dependent caches when the session changes. Backend schemas and authorization remain authoritative even when client validation succeeds.

## 6. Jobs and hosting

Run a worker that leases jobs, retries with bounded exponential backoff, and records terminal failures. A scheduler process or worker loop inserts deadline scans using unique schedule keys. Jobs and consumers are idempotent. Scaling to several workers requires database-safe leasing; deployment must not accidentally run uncoordinated schedulers in each web process.

Use a production WSGI server appropriate to the host, such as Gunicorn in Linux containers, behind an HTTPS reverse proxy. Do not deploy Flask's development server. Back up database and attachment storage together; document a tested restoration procedure.

## 7. Configuration inventory

| Setting | Purpose |
| --- | --- |
| `DATABASE_URL` | Database connection; secret |
| `SECRET_KEY` | Framework/CSRF secret; secret |
| `APP_ORIGIN` | Expected browser origin |
| `COOKIE_SECURE` | Enabled for HTTPS deployment |
| `SESSION_TTL_SECONDS` | Session expiry policy |
| `ATTACHMENT_STORAGE_ROOT` | Private local storage path |
| `MAX_UPLOAD_BYTES` | Validated upload ceiling |
| `MATCH_MODEL_VERSION` | Immutable embedding/reranker/scoring bundle reference |
| `EMBEDDING_MODEL_ID` | Selected pinned Sentence Transformer model |
| `RERANKER_MODEL_ID` | Selected pinned Cross-Encoder model |
| `MATCH_TOP_K` | Validated candidate shortlist size |
| `SLA_TIMEZONE` | Default calendar timezone; per-rule override supported |
| `DEMO_MODE` | Visible synthetic-data indicator and demo-only policies |

Deadline rules, permission mappings, thresholds, and notification preferences are versioned database configuration where appropriate. `.env.example` contains names and safe placeholders only. Frontend-exposed environment variables must never contain secrets.

## 8. Primary implementation references

- [shadcn Vite installation](https://ui.shadcn.com/docs/installation/vite).
- [Tailwind Vite installation](https://tailwindcss.com/docs/installation/using-vite).
- [Flask documentation](https://flask.palletsprojects.com/en/stable/).
- [scikit-learn feature extraction](https://scikit-learn.org/stable/modules/feature_extraction.html#text-feature-extraction).
- [Sentence Transformers similarity](https://sbert.net/docs/sentence_transformer/usage/semantic_textual_similarity.html).
- [Retrieve and rerank](https://sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html).
- [Cross-Encoder pair scoring](https://sbert.net/examples/cross_encoder/applications/README.html).
- [Embedding model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2).

Sources were consulted on 26 October 2026. They inform technology use; the selections and deployment structure above are OneCase design decisions.
