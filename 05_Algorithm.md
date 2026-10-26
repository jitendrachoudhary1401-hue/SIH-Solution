# OneCase / AICTE ACITS — Algorithm Implementation Specification

Version: 1.1 | Date: 26 October 2026

Required reference: user-selected `AICTE_ACITS_Algorithms.md`. This is the algorithm to implement, not a claim that it already exists in source code. OneCase is the product name; ACITS in the reference denotes the same project.

## 1. Required primary pipeline

Implement **Hybrid Semantic Complaint Matching**:

```text
New or revised complaint
 -> text and structured-field normalization
 -> verified institution matching and candidate filtering
 -> Sentence Transformer embeddings
 -> cosine similarity and top-k retrieval
 -> Cross-Encoder reranking
 -> hybrid scoring with structured evidence
 -> configurable triage thresholds and explanations
 -> authorized human related/unrelated decision
 -> preserved audit history and evaluation feedback
```

Every stage is required for the target solution. Exact rules and TF-IDF are research comparison baselines, not substitutes for the completed semantic/reranked engine. The reference's optional graph visualization is excluded from this focused implementation.

The system suggests relationships. It must never decide guilt, automatically merge complaints, change ownership, or dispose a case because of similarity.

## 2. Inputs, model artifacts, and outputs

Inputs: complaint ID/revision, canonical institution ID and verification state, normalized title/description, category, bureau, receipt timestamp, incident period where supplied, and approved reference identifiers. Minimize personal data in derived matching text while retaining protected original evidence.

Pin the embedding/reranker model revisions, tokenizer revisions, preprocessing, text-length policy, vector normalization, retrieval configuration, top-k, score transforms, hybrid weights, and triage thresholds. Store the bundle version with every run. Never compare embeddings from different model spaces.

Starting embedding candidate: `sentence-transformers/all-MiniLM-L6-v2`. Its model card describes 384-dimensional embeddings; validate the selected revision's language and input-length coverage on complaint data. Do not assume multilingual performance. [Model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2).

Starting Cross-Encoder candidate: `cross-encoder/ms-marco-MiniLM-L6-v2`, subject to labelled evaluation. It is not an AICTE-trained model. Keep the accepted model configurable and revision-pinned. [Cross-Encoder documentation](https://sbert.net/examples/cross_encoder/applications/README.html).

Persist run state, input revisions, eligible/retrieved candidate counts, retrieved IDs/ranks, model/configuration versions, component scores, final score, triage band, explanation, and stage timings. Preserve human decisions independently of machine score runs.

## 3. Normalization and structured matching

1. Normalize Unicode, case, whitespace, punctuation, institution identifiers, and categories using versioned rules.
2. Remove markup safely and documented repeated boilerplate.
3. Preserve negation, meaningful numbers, fees, and dates; redact unnecessary personal identifiers in derived text.
4. Resolve verified external identifiers and approved aliases to a canonical institution record.
5. Do not establish institution identity from a similar name alone. Conflicting/unverified records require manual verification.
6. Select eligible complaints for the same verified institution, excluding the incoming case and including disposed cases.
7. Treat category, reference, and incident dates as scoring/context features. Avoid hard category/date gates initially because misclassification and delayed reporting can hide relationships.

Exact source references are scoped evidence, not permission to suppress a distinct complaint. Similar text does not mean the incoming network request is a duplicate.

## 4. Sentence Transformer embeddings

Load the pinned model locally in the worker. Encode normalized descriptions in bounded batches and persist vectors with model revision, input digest, and complaint revision. L2-normalize nonzero embeddings for cosine retrieval.

Detect text beyond tokenizer/model limits. Select a deterministic chunking/aggregation policy on validation data, or explicitly record truncation and route incomplete evidence for review. Do not silently truncate and claim the entire complaint was compared. Record the applied policy for each input.

Empty text, unsupported language, zero vectors, and inference failures are explicit insufficient-input or failed-processing states. Do not display them as unrelated or silently replace the required algorithm with TF-IDF.

## 5. Cosine and top-k retrieval

```text
cos(A, B) = dot(A, B) / (norm(A) * norm(B))
```

Retrieve `min(k, eligible_count)` candidates from the verified institution's compatible embeddings. Semantic cosine may be negative; retain raw values. Use stable case-ID tie-breaking.

Initial implementation uses exact NumPy/scikit-learn dot products over an institution-scoped vector snapshot. This implements required top-k vector search without requiring a separate vector database. If approximate indexing is introduced, benchmark its retrieval loss against exact search.

Select k using validation recall@k and reranking latency. A temporary demo value such as k=20 is unvalidated, not an operational claim. Record shortlist truncation. Missed candidates cannot be recovered by later reranking; provide authorized manual related-case lookup.

Regenerate incompatible embeddings after input/model changes, invalidate stale cached snapshots, and recheck input revisions before saving results.

## 6. Cross-Encoder reranking

Jointly score each retrieved complaint pair with the selected Cross-Encoder, in bounded batches. Preserve retrieval and reranked positions. This model consumes both texts together rather than producing the independent embeddings used in retrieval. [Retrieve-and-rerank reference](https://sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html).

Inspect the actual model's output configuration: raw logits are not automatically bounded scores. Store raw outputs and a documented normalization. A sigmoid transform creates a bounded signal, not a calibrated duplication probability.

Fix pair ordering. If the selected model is asymmetric, define deterministic ordering or evaluate both directions and aggregate using a versioned rule. Test truncation of combined pairs explicitly. On failure, retry and expose processing state; do not publish partially scored results as final.

## 7. Hybrid relevance score

Use a configurable scoring function combining normalized model signals and reliable structured evidence:

```text
H = w_sem * N_sem(cosine)
  + w_ce  * N_ce(cross_encoder_output)
  + w_cat * category_agreement
  + w_ref * verified_reference_agreement
  + w_time * incident_period_overlap

w_i >= 0
sum(w_i) = 1 over available signals
```

Verified institution identity is the eligibility gate. Do not add it again as a constant positive feature that inflates every eligible pair. Explicitly define each structured feature. Missing data differs from known disagreement; exclude missing optional signals and renormalize weights under a documented rule, storing effective weights. Evaluate missing-data patterns separately.

Select model score transforms, weights, k, and thresholds on labelled validation data. Do not use per-request min-max scaling, whose meaning changes with candidate batches. No untested weights are claimed as correct. Neither the final score nor its component signals are probabilities that a complaint is duplicated or true.

Show factual explanations: same verified institution, category agreement/disagreement, known incident-period overlap, verified shared references, and relevant lexical phrases. Shared phrases are supporting evidence, not proof of what a neural model understood. Receipt date must not stand in for unknown incident date.

## 8. Triage and human decision

Choose ordered thresholds `T_low < T_high` on validation data.

| Score | Machine band | Action |
| --- | --- | --- |
| H >= T_high | High relevance | Prioritize authorized review |
| T_low <= H < T_high | Uncertain | Review with uncertainty visible |
| H < T_low | Low relevance | Retain machine evidence; no automatic human rejection |

Human review states are separately `pending`, `related`, and `unrelated`. High relevance still requires a human decision. Check access to both cases and store reviewer, reason, timestamp, and input revisions. Preserve earlier decisions after rescoring; material changes may create an explicit re-review request.

## 9. Processing contract

```text
process_job(case_id, expected_revision, bundle_id):
    validate input revision and verified institution
    snapshot eligible records and revisions
    normalize text and structured fields
    load coherent pinned model bundle
    generate/reuse compatible embeddings
    retrieve cosine top-k candidates
    Cross-Encoder score and rerank pairs
    normalize signals and calculate hybrid scores
    derive bands and factual explanations
    begin transaction
        verify captured revisions are still current
        reject stale result and enqueue newer run if necessary
        save canonical pair/run evidence
        preserve human decisions
        enqueue deduplicated actionable review alerts
        mark completed
    commit
```

Pair keys use ordered case IDs with a uniqueness constraint. Retry jobs safely under at-least-once delivery. Background service processing scope does not grant ordinary officers visibility of all candidates. “No suggestions” is valid only after a completed run.

## 10. SLA calculation and escalation

Configure applicable bureau/category, policy version, origin, duration, elapsed/business-time mode, timezone, working intervals, holidays, permitted pauses, warning thresholds, escalation stages, and recipients. No official AICTE SLA duration is invented; demo rules are labelled illustrative.

For business-time rules, walk local working intervals from the origin, skipping holidays/nonworking periods and approved pause intervals; consume eligible minutes until the duration is exhausted. For elapsed-time rules, consume elapsed duration with only explicitly authorized pause exclusions. Store the final deadline in UTC. Define daylight-saving boundary behavior for any selected calendar timezone.

Record pause/resume events with reasons and avoid double-counting overlapping pauses. Awaiting-information status alone does not pause the clock. Persist calendar/rule/deadline revisions; authorized recalculation supersedes obsolete alert occurrences.

A periodic scan classifies active cases as on track, due soon, or overdue using explicit boundaries. Insert escalation events and recipient alerts with unique complaint/deadline-revision/stage/recipient keys. Acknowledgement does not erase an overdue condition. Disposal stops new active alerts; reopening requires an explicit deadline-policy decision.

## 11. Priority queues and bottleneck detection

Sort active cases by descending urgency band (overdue, due soon, on track), descending assigned priority, earliest valid due date with missing dates last, oldest receipt, then stable case ID. Show the reason for urgency.

Apply versioned rule thresholds to long assignment/acknowledgement waits, repeated transfers within a window, and excessive overdue bureau backlog. Ratio rules require an explicit denominator and minimum sample size. Flags contain entity, rule/version, observation window, measured value, threshold, responsible recipient, and resolution state. Deduplicate by rule/entity/window. A flag does not assign blame, change owner, or close a case.

## 12. Supporting technical methods

| Method | Required behavior |
| --- | --- |
| RBAC | Check role and permitted institution/bureau/region/case scope server-side. |
| Argon2id | Hash self-managed passwords with maintained library and random per-password salts. |
| Session validation | Enforce expiry, revocation, account state, and secure session handling. |
| Idempotency | Scope request keys by actor/operation; same key and digest replays result, changed payload conflicts. Never suppress separate complaints on text similarity. |
| Audit | Save successful mutation and event atomically; distinguish failed/denied attempts and exclude secrets. |
| Search/indexing | Authorized filters, appropriate database indexes, deterministic order, cursor pagination. |
| Notifications | Deduplicate event/stage/recipient occurrences; persist delivery/read/acknowledgement state. |
| Analytics | Define period/cohort/denominator for actual permitted totals, workload, ageing, confirmed pairs, pending reviews, resolution duration, and SLA compliance. |

Resolution duration is measured by defined lifecycle episodes so reopen/dispose cycles are not silently mixed. SLA compliance uses episodes with known applicable deadlines; report unknown-policy exclusions separately.

## 13. Evaluation and research comparison

Compare four methods on the same labelled corpus: exact rules; TF-IDF/cosine; Sentence Transformer cosine/top-k; required hybrid plus Cross-Encoder approach. Fit TF-IDF only on training data.

Split by institution. Tune weights, k, transforms, and thresholds on validation only; freeze before held-out testing. Include paraphrases, same-institution unrelated issues, similar institution names, negation, boilerplate, long text, missing fields, and tested language variants.

| Metric | Definition |
| --- | --- |
| Precision | TP / (TP + FP) |
| Recall | TP / (TP + FN), including candidate/gate misses |
| F1 | Harmonic mean of precision and recall |
| False-positive rate | FP / (FP + TN), on an explicitly defined labelled pair universe |
| Candidate recall@k | True related candidates retrieved in top-k / all known related eligible candidates, with stated averaging |
| Gate coverage | Known related pairs retained by candidate gates / all known related pairs |
| Latency | Queue wait, embedding, retrieval, reranking, scoring, and total; report p50/p95 and hardware |
| Reviewer workload | High/uncertain suggestions per case and observed decisions |

Report sample sizes, class balance, confusion counts, dataset split, model/configuration versions, and undefined metrics when denominators are zero. Ordinary officer feedback is not automatically a research ground-truth label. Do not invent accuracy results.

## 14. Implementation order and completion

1. Database, institution lookup, complaint persistence, RBAC/session validation, search, idempotency, and audit.
2. Assignments/transfers, SLA calendars/pauses, escalation, priority sorting, bottleneck rules, and functional analytics.
3. Reproducible exact/TF-IDF comparison baselines.
4. Required embeddings, top-k retrieval, Cross-Encoder reranking, hybrid scoring, triage, and human review together.
5. Held-out comparison, latency measurement, authorization/concurrency/retry tests, and end-to-end demonstration.

Completion requires all required algorithm stages with persisted revisions and human decision history. Demonstrate two paraphrased RB/PGRC complaints and an unrelated same-institution complaint, reporting actual outcomes. Baseline-only results must not be labelled as completed hybrid intelligence.

## 15. References and related documents

- User-selected `AICTE_ACITS_Algorithms.md`: algorithm scope and technical-method inventory.
- [Sentence-BERT paper](https://arxiv.org/abs/1908.10084): semantic embedding research.
- [Retrieve and rerank](https://sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html): two-stage model pattern.
- [Cross-Encoder documentation](https://sbert.net/examples/cross_encoder/applications/README.html): pair scoring.
- [all-MiniLM-L6-v2 model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2): model characteristics and limitations.
- [scikit-learn text features](https://scikit-learn.org/stable/modules/feature_extraction.html#text-feature-extraction): TF-IDF baseline.

Sources support mechanisms, not measured OneCase performance. Related: [PRD](01_PRD.md), [Tech Stack](02_Tech_Stack.md), [Architecture](03_Architecture.md), [Workflow](04_Workflow.md), [UI/UX](06_UI_UX_Design.md).
