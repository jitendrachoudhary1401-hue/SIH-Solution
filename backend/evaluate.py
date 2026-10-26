"""Small, reproducible SYNTHETIC smoke evaluation. Not an operational accuracy claim.

Split by institution, fit TF-IDF on training text only, tune on validation pairs,
freeze configuration, then evaluate held-out institutions. Output includes misses.
"""
import argparse
import json
import platform
import time
from itertools import combinations
from pathlib import Path
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix
from app.matching import LocalModels, normalize, hybrid


def corpus():
    topics = [
        ("Fee refund", "The college has not returned the tuition deposit after cancellation of admission.", "Admission was cancelled in time, yet the student is still waiting for reimbursement of the paid fees.", "Infrastructure", "The physics laboratory has broken equipment and no fire extinguishers."),
        ("Faculty", "Two core engineering subjects have no permanent lecturer assigned this term.", "Students report a shortage of qualified teaching staff for required engineering classes.", "Admissions", "The college is holding original school certificates after a withdrawal request."),
        ("Fee refund", "My security deposit remains unpaid after I withdrew from the programme before the deadline.", "The student requests return of the admission deposit following an eligible withdrawal.", "Examination", "Internal assessment marks do not agree with the evaluated answer sheets."),
        ("Infrastructure", "The wheelchair ramp at the main entrance is blocked and the lift does not work.", "A disabled student cannot access the classrooms because the elevator and accessible entrance are unusable.", "Faculty", "There is no faculty member to teach the approved electrical engineering course."),
        ("Fee refund", "The institution retained all fees despite an acknowledged cancellation before classes began.", "A timely admission withdrawal has not resulted in the promised repayment of tuition fees.", "Infrastructure", "The chemistry lab has no functioning ventilation or protective safety equipment."),
        ("Admissions", "The institution is refusing to return original educational certificates after withdrawal.", "After leaving the college the student still cannot obtain the original school records held by admissions.", "Fee refund", "A student wants a written explanation of the hostel fee schedule for next year."),
    ]
    records = []
    for institution, (category, a, b, other_category, c) in enumerate(topics):
        for index, (text, cat) in enumerate([(a, category), (b, category), (c, other_category)]):
            records.append({"id": len(records), "institution": institution, "text": normalize(text), "category": cat,
                            "split": "train" if institution < 2 else "validation" if institution < 4 else "test", "topic": index < 2})
    return records


def metrics(labels, predictions):
    tn, fp, fn, tp = confusion_matrix(labels, predictions, labels=[False, True]).ravel().tolist()
    precision, recall, f1, _ = precision_recall_fscore_support(labels, predictions, average="binary", zero_division=0)
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn, "precision": float(precision) if tp + fp else None,
            "recall": float(recall) if tp + fn else None, "f1": float(f1), "false_positive_rate": fp / (fp + tn) if fp + tn else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", default=str(Path(__file__).resolve().parents[1] / ".runtime" / "models"))
    parser.add_argument("--output", default="docs/evaluation.json")
    args = parser.parse_args()
    models, records = LocalModels(args.models), corpus()
    vectorizer = TfidfVectorizer(ngram_range=(1, 2))
    vectorizer.fit([r["text"] for r in records if r["split"] == "train"])
    tfidf = vectorizer.transform([r["text"] for r in records])
    start = time.perf_counter()
    vectors = models.encode([r["text"] for r in records])
    embed_ms = (time.perf_counter() - start) * 1000
    pairs = []
    for institution in range(6):
        group = [r for r in records if r["institution"] == institution]
        for a, b in combinations(group, 2):
            start = time.perf_counter()
            raw = float(models.rerank([[a["text"], b["text"]]])[0])
            elapsed = (time.perf_counter() - start) * 1000
            cosine = float(np.dot(vectors[a["id"]], vectors[b["id"]]))
            pairs.append({"a": a, "b": b, "label": a["topic"] and b["topic"], "cosine": cosine,
                          "logit": raw, "tfidf": float((tfidf[a["id"]] @ tfidf[b["id"]].T).toarray()[0][0]), "rerank_ms": elapsed})
    validation = [p for p in pairs if p["a"]["split"] == "validation"]
    test = [p for p in pairs if p["a"]["split"] == "test"]
    labels = [p["label"] for p in validation]
    thresholds = [i / 100 for i in range(5, 100, 5)]
    tuned = {}
    for method in ["tfidf", "cosine"]:
        tuned[method] = max(thresholds, key=lambda t: (metrics(labels, [p[method] >= t for p in validation])["f1"], t))
    configurations = []
    for semantic in [.25, .35, .45]:
        weights = {"semantic": semantic, "reranker": .9 - semantic, "category": .1}
        for threshold in thresholds:
            predicted = [hybrid(p["cosine"], p["logit"], p["a"]["category"] == p["b"]["category"], weights)[0] >= threshold for p in validation]
            configurations.append((metrics(labels, predicted)["f1"], threshold, semantic, weights))
    _, hybrid_threshold, _, weights = max(configurations, key=lambda c: (c[0], c[1], c[2]))
    tuned["hybrid"] = {"threshold": hybrid_threshold, "weights": weights, "top_k": 2, "note": "All two eligible candidates retained in this tiny corpus; production k requires larger validation."}
    # Configuration is now frozen; nothing below tunes against held-out labels.
    result = {}
    for method in ["exact", "tfidf", "cosine", "hybrid"]:
        predictions = []
        for p in test:
            prediction = p["a"]["text"] == p["b"]["text"] if method == "exact" else (
                hybrid(p["cosine"], p["logit"], p["a"]["category"] == p["b"]["category"], weights)[0] >= hybrid_threshold if method == "hybrid" else p[method] >= tuned[method])
            predictions.append(prediction)
        result[method] = metrics([p["label"] for p in test], predictions)
    report = {"scope": "Synthetic smoke evaluation only: 18 complaints / 6 institutions; 2 institutions each in train, validation, held-out test. Not evidence of deployment accuracy.",
              "test_pairs": len(test), "test_related": sum(p["label"] for p in test), "configuration": tuned,
              "model_bundle": models.bundle, "metrics": result,
              "candidate_recall_at_k": 1., "gate_coverage": 1., "candidate_note": "Top-k=2 includes all eligible candidates in each 3-record institution. No cross-institution labelled positives in this fixture.",
              "hardware": {"platform": platform.platform(), "processor": platform.processor(), "python": platform.python_version(), "device": "CPU"},
              "latency_ms": {"embedding_batch_18": embed_ms, "rerank_pair_p50": float(np.percentile([p["rerank_ms"] for p in test], 50)), "rerank_pair_p95": float(np.percentile([p["rerank_ms"] for p in test], 95))},
              "limitations": ["Tiny English-only synthetic fixture", "No operational quality threshold established", "No 10,000-record load test", "No queue-wait latency in this isolated inference evaluation", "Application demo weights remain unvalidated; this report does not silently change runtime configuration"]}
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(target), "test_pairs": len(test), "metrics": result}, indent=2))


if __name__ == "__main__":
    main()
