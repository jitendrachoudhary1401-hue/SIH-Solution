"""Local retrieve/rerank matching. Demo weights are unvalidated, never probabilities."""
import hashlib
import html
import json
import math
import re
import time
import unicodedata
from pathlib import Path
from flask import current_app
from sqlalchemy import select
from .models import db, Complaint, Embedding, MatchingRun, Pair, PairScore, now


def normalize(text):
    text = html.unescape(re.sub(r"<[^>]*>", " ", text))
    text = unicodedata.normalize("NFKC", text).casefold()
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", " [email] ", text)
    text = re.sub(r"(?<!\d)(?:\+91[ -]?)?[6-9]\d{9}(?!\d)", " [phone] ", text)
    return re.sub(r"\s+", " ", text).strip()


def hybrid(cosine, logit, category_agrees, weights=None):
    weights = weights or {"semantic": .35, "reranker": .55, "category": .10}
    if any(v < 0 for v in weights.values()) or abs(sum(weights.values()) - 1) > 1e-6:
        raise ValueError("Hybrid weights must be nonnegative and sum to one")
    signals = {"semantic": max(0., min(1., (float(cosine) + 1) / 2)),
               "reranker": 1 / (1 + math.exp(-max(-80., min(80., float(logit))))),
               "category": float(category_agrees)}
    return sum(weights[k] * signals[k] for k in weights), signals


class LocalModels:
    def __init__(self, root):
        import torch
        from sentence_transformers import SentenceTransformer, CrossEncoder
        root = Path(root)
        manifest = root / "manifest.json"
        if not manifest.exists():
            raise RuntimeError("Local models are not installed. Run backend/download_models.py, then retry matching.")
        self.manifest = json.loads(manifest.read_text(encoding="utf-8"))
        self.encoder = SentenceTransformer(str(root / "embedding"), device="cpu", local_files_only=True, trust_remote_code=False)
        self.reranker = CrossEncoder(str(root / "reranker"), device="cpu", local_files_only=True, trust_remote_code=False,
                                    max_length=512, activation_fn=torch.nn.Identity())
        self.bundle = {**self.manifest, "scoring_version": "hybrid-demo-v1", "normalization": "nfkc-redact-v1",
                       "top_k": 20, "low_threshold": .45, "high_threshold": .72,
                       "weights": {"semantic": .35, "reranker": .55, "category": .10},
                       "validated": False, "semantic_transform": "(cosine + 1) / 2", "reranker_transform": "sigmoid(raw logit)",
                       "text_policy": "tokenizer truncation, explicitly flagged; canonical ascending case-ID pair order"}

    def encode(self, texts):
        return self.encoder.encode(texts, normalize_embeddings=True, show_progress_bar=False, batch_size=16)

    def truncated(self, text):
        return len(self.encoder.tokenizer.encode(text, truncation=False)) > self.encoder.max_seq_length

    def pair_truncated(self, a, b):
        return len(self.reranker.tokenizer.encode(a, b, truncation=False)) > 512

    def rerank(self, pairs):
        return self.reranker.predict(pairs, show_progress_bar=False, batch_size=16)


_models = None


def get_models():
    global _models
    if _models is None:
        _models = LocalModels(current_app.config["MODEL_PATH"])
    return _models


def process(case_id, revision, models=None):
    import numpy as np
    from .api import notify
    from .models import Grant, User
    started = time.perf_counter()
    case = db.session.get(Complaint, case_id)
    if not case or case.content_revision != revision:
        return "superseded"
    if not case.institution.verified:
        raise ValueError("Institution identity is unverified; matching requires verification.")
    models = models or get_models()
    snapshot = db.session.scalars(select(Complaint).where(Complaint.institution_id == case.institution_id).order_by(Complaint.id)).all()
    revisions = {c.id: c.content_revision for c in snapshot}
    texts = {c.id: normalize(c.description) for c in snapshot}
    if any(not text for text in texts.values()):
        raise ValueError("Insufficient normalized complaint text")
    model_key = models.bundle["embedding"]["revision"]
    vectors, truncations = {}, {}
    embed_start = time.perf_counter()
    for c in snapshot:
        stored = db.session.scalar(select(Embedding).where(Embedding.complaint_id == c.id, Embedding.revision == c.content_revision, Embedding.model == model_key))
        if stored:
            vectors[c.id], truncations[c.id] = np.array(stored.vector), stored.truncated
        else:
            vec = np.asarray(models.encode([texts[c.id]])[0], dtype=float)
            norm = np.linalg.norm(vec)
            if not np.isfinite(vec).all() or norm <= 0:
                raise ValueError("Embedding produced an invalid vector")
            vec = vec / norm
            truncated = models.truncated(texts[c.id])
            vectors[c.id], truncations[c.id] = vec, truncated
            db.session.add(Embedding(complaint_id=c.id, revision=c.content_revision, model=model_key,
                                     digest=hashlib.sha256(texts[c.id].encode()).hexdigest(), vector=vec.tolist(), truncated=truncated))
    embedding_ms = (time.perf_counter() - embed_start) * 1000
    retrieval_start = time.perf_counter()
    candidates = [(c, float(np.dot(vectors[case.id], vectors[c.id]))) for c in snapshot if c.id != case.id]
    candidates.sort(key=lambda x: (-x[1], x[0].id))
    shortlist = candidates[:models.bundle["top_k"]]
    retrieval_ms = (time.perf_counter() - retrieval_start) * 1000
    pairs = [[texts[min(case.id, c.id)], texts[max(case.id, c.id)]] for c, _ in shortlist]
    rerank_start = time.perf_counter()
    logits = list(models.rerank(pairs)) if pairs else []
    reranking_ms = (time.perf_counter() - rerank_start) * 1000
    if len(logits) != len(shortlist):
        raise ValueError("Incomplete Cross-Encoder outputs")
    # Model inference can take time: recheck every captured revision before committing.
    db.session.expire_all()
    for cid, version in revisions.items():
        fresh = db.session.scalar(select(Complaint).where(Complaint.id == cid).with_for_update())
        if fresh.content_revision != version:
            db.session.rollback()
            return "superseded"
    case = db.session.get(Complaint, case_id)
    run = MatchingRun(complaint_id=case.id, revision=revision, bundle=models.bundle,
                      evidence={"eligible_count": len(candidates), "retrieved_count": len(shortlist),
                                "shortlist_truncated": len(candidates) > len(shortlist),
                                "retrieved_ids": [c.id for c, _ in shortlist],
                                "latency_ms": {"embedding": embedding_ms, "retrieval": retrieval_ms, "reranking": reranking_ms,
                                               "total": (time.perf_counter() - started) * 1000}})
    db.session.add(run)
    db.session.flush()
    rank_order = sorted(range(len(logits)), key=lambda i: (-float(logits[i]), shortlist[i][0].id))
    reranked = {index: rank + 1 for rank, index in enumerate(rank_order)}
    for index, ((other, cosine), logit) in enumerate(zip(shortlist, logits)):
        raw = float(logit)
        if not math.isfinite(raw):
            raise ValueError("Invalid Cross-Encoder output")
        score, signals = hybrid(cosine, raw, case.category == other.category, models.bundle["weights"])
        band = "high" if score >= models.bundle["high_threshold"] else "uncertain" if score >= models.bundle["low_threshold"] else "low"
        a, b = sorted((case.id, other.id))
        tokens_a = set(re.findall(r"\b\w{4,}\b", texts[a]))
        tokens_b = set(re.findall(r"\b\w{4,}\b", texts[b]))
        evidence = {"cosine": cosine, "reranker_raw": raw, "signals": signals, "hybrid": score,
                    "retrieval_rank": index + 1, "reranked_rank": reranked[index], "bundle": models.bundle,
                    "revisions": {str(a): revisions[a], str(b): revisions[b]},
                    "truncated": truncations[a] or truncations[b] or models.pair_truncated(texts[a], texts[b]),
                    "category_agreement": case.category == other.category,
                    "shared_terms": sorted(tokens_a & tokens_b)[:12],
                    "explanation": "Same verified institution. Category agreement is structured evidence; shared terms are lexical evidence, not neural attribution. Incident dates and verified references were not supplied; their weights are excluded."}
        pair = db.session.scalar(select(Pair).where(Pair.case_a_id == a, Pair.case_b_id == b))
        if pair:
            pair.run_id, pair.evidence, pair.band = run.id, evidence, band
            pair.version += 1
        else:
            pair = Pair(case_a_id=a, case_b_id=b, run_id=run.id, evidence=evidence, band=band)
            db.session.add(pair)
        db.session.flush()
        db.session.add(PairScore(pair_id=pair.id, run_id=run.id, evidence=evidence))
        if band != "low":
            for reviewer in db.session.scalars(select(User).where(User.role == "reviewer", User.active.is_(True))):
                granted = set(db.session.scalars(select(Grant.complaint_id).where(Grant.user_id == reviewer.id, Grant.complaint_id.in_([a, b]))))
                if granted == {a, b}:
                    notify(reviewer.id, case, "overlap", "A possible overlap is ready for review.", f"pair:{pair.id}:{revision}:{reviewer.id}")
    case.matching_state, case.matching_error = "completed", None
    db.session.commit()
    return "completed"
