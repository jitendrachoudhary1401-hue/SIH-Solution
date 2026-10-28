from datetime import datetime, timedelta, timezone, date
import pytest
from conftest import login
from app.matching import normalize, hybrid, process
from app.models import db, Pair, PairScore, Complaint, Job
from app.jobs import tick
from app.sla import Calendar, calculate
from sqlalchemy import select, func


class DeterministicModels:
    """Injected test double verifies orchestration, never claimed as semantic accuracy."""
    bundle = {"embedding": {"model": "test", "revision": "test-1"}, "reranker": {"model": "test", "revision": "test-1"},
              "top_k": 20, "weights": {"semantic": .35, "reranker": .55, "category": .10},
              "low_threshold": .45, "high_threshold": .72, "validated": False, "scoring_version": "test"}

    def encode(self, texts):
        return [[1., 0.] if any(word in text for word in ("refund", "tuition")) else [0., 1.] for text in texts]

    def truncated(self, text):
        return False

    def pair_truncated(self, a, b):
        return False

    def rerank(self, pairs):
        return [4. if all(any(word in text for word in ("refund", "tuition")) for text in pair) else -4. for pair in pairs]


def test_normalization_scoring_and_calendar():
    text = normalize("<p>NOT refunded ₹5000. Email PERSON@example.com</p>")
    assert "not refunded" in text and "5000" in text and "person@example.com" not in text
    assert hybrid(.9, 4, True)[0] > hybrid(.1, -4, False)[0]
    origin = datetime(2026, 10, 23, 10, 30, tzinfo=timezone.utc)  # Friday 16:00 IST
    deadline = calculate(origin, 120, "business")
    assert deadline == datetime(2026, 10, 26, 4, 30, tzinfo=timezone.utc)  # Monday 10:00 IST
    holiday = Calendar(holidays=frozenset([date(2026, 10, 26)]))
    assert calculate(origin, 120, "business", holiday) == deadline + timedelta(days=1)
    assert calculate(origin, 120, pauses=[(origin + timedelta(minutes=30), origin + timedelta(minutes=90)), (origin + timedelta(minutes=60), origin + timedelta(minutes=120))]) == origin + timedelta(minutes=210)
    with pytest.raises(ValueError):
        calculate(datetime(2026, 1, 1), 60)


def test_pipeline_review_scope_and_persisted_evidence(app, client):
    with app.app_context():
        assert process(1, 1, DeterministicModels()) == "completed"
        pair = db.session.scalar(select(Pair).where(Pair.case_a_id == 1, Pair.case_b_id == 2))
        pair_id = pair.id
        assert pair.band == "high"
        assert pair.evidence["revisions"] == {"1": 1, "2": 1}
        assert db.session.scalar(select(func.count()).select_from(PairScore)) == 2
    login(client)
    assert client.get(f"/api/overlaps/{pair_id}").status_code == 404
    headers = login(client, "reviewer@onecase.demo")
    data = client.get(f"/api/overlaps/{pair_id}").json
    result = client.post(f"/api/overlaps/{pair_id}/review", headers=headers, json={"version": data["version"], "decision": "related", "reason": "Both describe the same fee return request"})
    assert result.status_code == 200 and result.json["state"] == "related"
    assert result.json['reviews'][0]['reason'] == 'Both describe the same fee return request'
    owner_client = app.test_client(); login(owner_client)
    history = owner_client.get('/api/complaints/1/actions').json['items']
    assert all(e['reason'] != 'Both describe the same fee return request' for e in history if e['kind'] == 'overlap_reviewed')
    with app.app_context():
        assert process(1, 1, DeterministicModels()) == "completed"
        assert db.session.get(Pair, pair_id).state == "related"
        db.session.get(Complaint, 1).content_revision += 1
        db.session.commit()
    stale = client.get(f"/api/overlaps/{pair_id}").json
    assert stale["stale"]
    assert client.post(f"/api/overlaps/{pair_id}/review", headers=headers, json={"version": stale["version"], "decision": "unrelated", "reason": "Must reject stale model evidence"}).status_code == 409


def test_worker_retry_and_stale_inputs(app):
    with app.app_context():
        assert process(1, 99, DeterministicModels()) == "superseded"
        assert tick(DeterministicModels())
        assert db.session.get(Job, 1).state == "completed"
        assert db.session.get(Complaint, 1).matching_state == "completed"


def test_no_silent_baseline_fallback(app):
    class FailingModels(DeterministicModels):
        def encode(self, texts):
            raise RuntimeError("inference unavailable")
    with app.app_context():
        assert tick(FailingModels())
        assert db.session.get(Complaint, 1).matching_state == "failed"
        assert db.session.scalar(select(func.count()).select_from(Pair)) == 0
