"""Immediate text suggestions and explicit, scoped coordination decisions."""
import html
import re
import unicodedata
from datetime import timezone
from difflib import SequenceMatcher
from flask import abort, g
from sqlalchemy import select
from pydantic import Field
from .models import (db, Complaint, Pair, MatchingRun, PairScore, User, Review,
                     CoordinationGroup, CoordinationMember, Bureau, CaseRecurrence, ActionEvent, iso)
from .auth import authenticated, roles, scope, has_content, allowed, check_version
from .api import api, Input, parse, notify, event, authorized_pairs


def text_key(value):
    # Preserve numbers, names and contact details: redaction must not manufacture equality.
    value = html.unescape(re.sub(r'<[^>]*>', ' ', value))
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', value).casefold()).strip()


def location_key(value):
    # A location is plain text. Do not strip meaningful labels like "Room <A>".
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', value or '').casefold()).strip()


ISSUE_WORD_FORMS = {
    'fees': 'fee', 'charged': 'charge', 'charging': 'charge', 'charges': 'charge',
    'excess': 'extra', 'excessive': 'extra', 'additional': 'extra',
    'refunded': 'refund', 'refunds': 'refund', 'refunding': 'refund',
    'reimbursement': 'refund', 'reimbursements': 'refund',
    'received': 'receive', 'receiving': 'receive',
    'cancelled': 'cancel', 'canceled': 'cancel', 'cancellation': 'cancel',
    'withdrawn': 'withdraw', 'withdrawal': 'withdraw',
    'withheld': 'withhold', 'withholding': 'withhold',
    'documents': 'document', 'certificates': 'certificate',
    'returned': 'return', 'returning': 'return',
}
ISSUE_STOP_WORDS = set('a an the by of to from for in on at and or my me i we our us is are was were be been being has have had do does did please college institution university'.split())
NEGATIONS = {'not', 'no', 'never', 'without'}


def wording_similarity(a, b):
    """Explicit lexical rules, not an embedding model or a duplication probability."""
    def terms(value):
        value = re.sub(r"\b(\w+)n['’]t\b", r'\1 not', value)
        return {ISSUE_WORD_FORMS.get(t, t) for t in re.findall(r'\b\w+\b', value) if t not in ISSUE_STOP_WORDS}
    first, second = terms(a), terms(b)
    shared = first & second
    raw = (1.0 if a == b else 0.0) if max(len(a), len(b)) > 4000 else SequenceMatcher(None, a, b, autojunk=False).ratio()
    # Removing a negation or changing an amount/date must not manufacture a match.
    compatible = (first & NEGATIONS == second & NEGATIONS and
                  {t for t in first if t.isdigit()} == {t for t in second if t.isdigit()})
    normalized = 2 * len(shared) / (len(first) + len(second)) if first and second else 0.0
    normalized_match = compatible and len(shared) >= 3 and normalized >= .90
    score = max(raw, normalized if normalized_match else 0.0) if compatible else 0.0
    return score, {'raw_wording': raw, 'normalized_issue_terms': normalized,
                   'normalized_match': normalized_match, 'shared_terms': sorted(shared)[:12]}


def is_stale(pair):
    return (pair.a.status == 'disposed' or pair.b.status == 'disposed' or not same_context(pair.a, pair.b) or
            pair.evidence.get('revisions') != {str(pair.a.id): pair.a.content_revision, str(pair.b.id): pair.b.content_revision})


def same_context(a, b):
    location = location_key(a.incident_location)
    return (len(location) >= 2 and location == location_key(b.incident_location) and
            a.institution_id == b.institution_id and a.category == b.category and
            (a.bureau.code == 'PUBLIC-DEMO') == (b.bureau.code == 'PUBLIC-DEMO'))


def record_recurrence(case, previous):
    if case.status == 'disposed' or previous.status != 'disposed' or not same_context(case, previous):
        return
    closure = db.session.scalar(select(ActionEvent).where(ActionEvent.complaint_id == previous.id,
        ActionEvent.kind == 'status_changed', ActionEvent.changes['status']['after'].as_string() == 'disposed').order_by(ActionEvent.id.desc()).limit(1))
    if not closure or closure.changes.get('outcome') == 'not_upheld' or closure.created_at.replace(tzinfo=timezone.utc) >= case.received_at.replace(tzinfo=timezone.utc):
        return
    existing = db.session.scalar(select(CaseRecurrence).where(CaseRecurrence.complaint_id == case.id,
        CaseRecurrence.previous_complaint_id == previous.id, CaseRecurrence.closure_event_id == closure.id,
        CaseRecurrence.revision == case.content_revision))
    if existing:
        return
    record = CaseRecurrence(complaint_id=case.id, previous_complaint_id=previous.id,
        closure_event_id=closure.id, revision=case.content_revision, previous_revision=previous.content_revision)
    db.session.add(record)
    db.session.flush()
    event(case, 'repeat_issue_detected', 'Possible repeat of an earlier resolved issue',
          'A similar issue at the same incident location was resolved before this complaint was received. Authorized staff can compare the earlier resolution timeline.', actor=False)
    owner = db.session.get(User, case.owner_id)
    if owner and owner.active and db.session.scalar(select(Complaint.id).where(Complaint.id == case.id, scope(owner))):
        # Prior-case details are added at read time after checking live access.
        message = f'{case.reference}: Possible repeat issue at this institution and location. An earlier complaint was resolved before this receipt. Open the case to compare authorized records.'
        notify(owner.id, case, 'repeat_issue', message,
               f'repeat:{record.id}:{owner.id}')


def recurrence_notification_message(item):
    key = item.dedup_key.split(':')
    if len(key) != 3 or key[0] != 'repeat' or not key[1].isdigit():
        return item.message
    record = db.session.get(CaseRecurrence, int(key[1]))
    if not record or record.complaint_id != item.complaint_id:
        return item.message
    previous = db.session.scalar(select(Complaint).where(Complaint.id == record.previous_complaint_id, scope()))
    case = db.session.get(Complaint, record.complaint_id)
    if not previous or not has_content(previous) or record.revision != case.content_revision or record.previous_revision != previous.content_revision or previous.status != 'disposed' or not same_context(case, previous):
        return item.message
    closure = db.session.get(ActionEvent, record.closure_event_id)
    from zoneinfo import ZoneInfo
    def date(value):
        return value.replace(tzinfo=timezone.utc).astimezone(ZoneInfo('Asia/Kolkata')).strftime('%d %b %Y, %I:%M %p IST')
    return f'{case.reference}: Possible repeat issue. Earlier case {previous.reference} resolved {date(closure.created_at)}; new complaint received {date(case.received_at)}. This is a separate complaint, not an active overlap.'


def recurrence_json(case):
    records = db.session.scalars(select(CaseRecurrence).where(CaseRecurrence.complaint_id == case.id, CaseRecurrence.revision == case.content_revision).order_by(CaseRecurrence.id.desc()))
    result = []
    for record in records:
        previous = db.session.scalar(select(Complaint).where(Complaint.id == record.previous_complaint_id, scope()))
        if not previous or not has_content(previous) or previous.status != 'disposed' or previous.content_revision != record.previous_revision or not same_context(case, previous):
            continue
        closure = db.session.get(ActionEvent, record.closure_event_id)
        result.append({'id': record.id, 'previous_case_id': previous.id, 'reference': previous.reference,
                       'previous_received_at': iso(previous.received_at), 'resolved_at': iso(closure.created_at),
                       'new_received_at': iso(case.received_at), 'detected_at': iso(record.detected_at)})
    return result


def can_decide(pair):
    return ('reviewer' in roles() or
            bool(roles() & {'officer', 'lead'}) and allowed(pair.a, 'case.action') and allowed(pair.b, 'case.action'))


def alert_owners(pair):
    if pair.band == 'low' or pair.state != 'pending' or is_stale(pair):
        return
    for case in (pair.a, pair.b):
        owner = db.session.get(User, case.owner_id)
        if owner and owner.active and roles(owner) & {'officer', 'lead'} and db.session.scalar(
                select(Complaint.id).where(Complaint.id == case.id, scope(owner))):
            revisions = pair.evidence['revisions']
            notify(owner.id, case, 'overlap', f'{case.reference}: Possible overlapping complaint detected. Open Overlap review to compare and decide.',
                   f"pair-owner:{pair.id}:{revisions[str(pair.a.id)]}:{revisions[str(pair.b.id)]}:{case.id}:{owner.id}")


def active_notification_keys():
    """Only live, ongoing suggestions count as actionable overlap notifications."""
    visible = select(Complaint.id).where(scope())
    pairs = db.session.scalars(select(Pair).where(Pair.state == 'pending', Pair.band != 'low',
        (Pair.case_a_id.in_(visible)) | (Pair.case_b_id.in_(visible)),
        Pair.a.has(Complaint.status != 'disposed'), Pair.b.has(Complaint.status != 'disposed')))
    keys = []
    for pair in pairs:
        if is_stale(pair):
            continue
        revisions = pair.evidence['revisions']
        revision_key = f'{revisions[str(pair.a.id)]}:{revisions[str(pair.b.id)]}'
        for case in (pair.a, pair.b):
            if case.owner_id == g.user.id:
                keys.append(f'pair-owner:{pair.id}:{revision_key}:{case.id}:{g.user.id}')
        if 'reviewer' in roles() and db.session.scalar(authorized_pairs().where(Pair.id == pair.id)):
            keys.append(f'pair:{pair.id}:{revision_key}:{g.user.id}')
    return keys


def detect_text_overlaps(case):
    """Bounded, cheap text check, independent of neural-worker availability.

    This supplements semantic retrieval; it never marks the queued semantic job complete.
    """
    if not case.institution.verified or case.status == 'disposed' or len(location_key(case.incident_location)) < 2:
        return
    key = text_key(case.description)
    if len(key) < 20:
        return
    demo = case.bureau.code == 'PUBLIC-DEMO'
    candidates = db.session.scalars(select(Complaint).join(Bureau).where(
        Complaint.institution_id == case.institution_id, Complaint.category == case.category,
        Complaint.id != case.id,
        (Bureau.code == 'PUBLIC-DEMO') if demo else (Bureau.code != 'PUBLIC-DEMO')
    ).order_by(Complaint.id.desc()).limit(200)).all()
    run = None
    for other in candidates:
        if not same_context(case, other):
            continue
        other_key = text_key(other.description)
        similarity, wording = wording_similarity(key, other_key)
        if similarity < .85:
            continue
        if other.status == 'disposed':
            record_recurrence(case, other)
            continue
        a, b = sorted((case.id, other.id))
        pair = db.session.scalar(select(Pair).where(Pair.case_a_id == a, Pair.case_b_id == b).with_for_update())
        if pair and not is_stale(pair) and (pair.state != 'pending' or pair.band != 'low'):
            alert_owners(pair)
            continue
        if run is None:
            run = MatchingRun(complaint_id=case.id, revision=case.content_revision,
                              bundle={'scoring_version': 'text-similarity-v2', 'normalization': 'issue-word-forms-v1', 'validated': False},
                              evidence={'method': 'text_similarity', 'candidate_limit': 200})
            db.session.add(run)
            db.session.flush()
        evidence = {'method': 'text_similarity', 'text_similarity': similarity, 'hybrid': similarity,
                    'wording': wording,
                    'bundle': run.bundle, 'revisions': {str(case.id): case.content_revision, str(other.id): other.content_revision},
                    'explanation': 'Similar issue wording at the same reported incident location, verified institution and category. The wording check compares character similarity and normalized issue words, including common forms such as charged/charging and excess/extra. Word order may differ; negations and numbers are preserved. This is a suggestion for human review, not proof of a duplicate or a neural model result.',
                    'shared_terms': wording['shared_terms'], 'truncated': False}
        if pair is None:
            pair = Pair(case_a_id=a, case_b_id=b, run_id=run.id, band='high', state='pending', evidence=evidence)
            db.session.add(pair)
        else:
            pair.run_id, pair.band, pair.state, pair.evidence = run.id, 'high', 'pending', evidence
            pair.version += 1
        db.session.flush()
        db.session.add(PairScore(pair_id=pair.id, run_id=run.id, evidence=evidence))
        alert_owners(pair)


class PairSnapshot(Input):
    id: int = Field(gt=0)
    version: int = Field(gt=0)


class BulkDecision(Input):
    pairs: list[PairSnapshot] = Field(min_length=1, max_length=100)
    action: str
    reason: str = Field(min_length=5, max_length=2000)
    primary_complaint_id: int | None = Field(default=None, gt=0)


@api.post('/overlaps/scan')
@authenticated
def scan_overlaps():
    if not roles() & {'officer', 'lead', 'reviewer'}:
        abort(403)
    # Visit only the newest 100 authorized active cases. Existing semantic evidence is preserved.
    cases = db.session.scalars(select(Complaint).where(scope(), Complaint.status != 'disposed').order_by(Complaint.id.desc()).limit(100)).all()
    cases = [c for c in cases if has_content(c)]
    missing = [{'id': c.id, 'reference': c.reference} for c in cases if len(location_key(c.incident_location)) < 2]
    unverified = [{'id': c.id, 'reference': c.reference} for c in cases if not c.institution.verified]
    for case in cases:
        detect_text_overlaps(case)
    # Reconcile existing neural suggestions too (e.g. cases assigned after inference).
    for pair in db.session.scalars(authorized_pairs().where(Pair.state == 'pending', Pair.band != 'low')):
        alert_owners(pair)
    db.session.commit()
    pending = [p for p in db.session.scalars(authorized_pairs().where(Pair.state == 'pending', Pair.band != 'low')) if not is_stale(p)]
    return {'checked': len(cases), 'message': 'Text check finished. Semantic matching continues separately.', 'case_limit': 100,
            'missing_location': missing, 'unverified_institution': unverified,
            'pending_pairs': len(pending),
            'eligible': sum(c.institution.verified and len(location_key(c.incident_location)) >= 2 for c in cases)}


@api.post('/overlaps/bulk')
@authenticated
def bulk_decision():
    data = parse(BulkDecision)
    if data.action not in ('reject', 'merge') or len({p.id for p in data.pairs}) != len(data.pairs):
        abort(422, description='Choose merge or reject and provide distinct suggestion IDs.')
    # Lock in deterministic order; validate the complete snapshot before changing anything.
    pairs = []
    for snapshot in sorted(data.pairs, key=lambda p: p.id):
        pair = db.session.scalar(authorized_pairs().where(Pair.id == snapshot.id).with_for_update())
        if not pair:
            abort(404, description='A suggestion is unavailable in your authorized scope.')
        if not can_decide(pair):
            abort(403, description='An assigned officer for both complaints, their bureau lead, or an authorized reviewer must decide.')
        check_version(pair, snapshot.version)
        if pair.state != 'pending' or pair.band == 'low' or is_stale(pair):
            abort(409, description='A suggestion changed or was already reviewed. Refresh before deciding.')
        pairs.append(pair)
    case_ids = {cid for p in pairs for cid in (p.case_a_id, p.case_b_id)}
    db.session.scalars(select(Complaint).where(Complaint.id.in_(case_ids)).order_by(Complaint.id).with_for_update().execution_options(populate_existing=True)).all()
    if any(is_stale(p) for p in pairs):
        abort(409, description='Complaint facts changed during review. Refresh before deciding.')
    group = None
    if data.action == 'merge':
        if data.primary_complaint_id not in case_ids:
            abort(422, description='Choose a primary complaint from the suggestions shown.')
        # Only connected suggestions can form one coordination group.
        connected = {data.primary_complaint_id}
        while True:
            expanded = connected | {cid for p in pairs if {p.case_a_id, p.case_b_id} & connected for cid in (p.case_a_id, p.case_b_id)}
            if expanded == connected:
                break
            connected = expanded
        if connected != case_ids:
            abort(422, description='Select one connected overlap group at a time.')
        members = db.session.scalars(select(CoordinationMember).where(CoordinationMember.complaint_id.in_(case_ids)).with_for_update()).all()
        old_group_ids = {m.group_id for m in members}
        old_members = db.session.scalars(select(CoordinationMember).where(CoordinationMember.group_id.in_(old_group_ids)).with_for_update()).all() if old_group_ids else []
        case_ids |= {m.complaint_id for m in old_members}
        if len(case_ids) > 100:
            abort(422, description='A coordination group is limited to 100 complaints.')
        cases = db.session.scalars(select(Complaint).where(Complaint.id.in_(case_ids), scope()).order_by(Complaint.id).with_for_update()).all()
        if {c.id for c in cases} != case_ids or any(not has_content(c) or not ('reviewer' in roles() or allowed(c, 'case.action')) for c in cases):
            abort(403, description='The complete existing coordination group must be authorized before merging.')
        if len({c.institution_id for c in cases}) != 1 or len({c.bureau.code == 'PUBLIC-DEMO' for c in cases}) != 1:
            abort(422, description='Merge requires the same institution and workspace type.')
        if any(c.status == 'disposed' for c in cases):
            abort(409, description='Resolved complaints cannot be merged. Reopen through the authorized workflow first.')
        if any(not same_context(cases[0], c) for c in cases):
            abort(422, description='Merge requires the same incident location and issue category for every complaint.')
        rejected = db.session.scalars(select(Pair).where(Pair.case_a_id.in_(case_ids), Pair.case_b_id.in_(case_ids), Pair.state == 'unrelated')).all()
        if any(not is_stale(p) for p in rejected):
            abort(409, description='An existing review marks two complaints in this group unrelated. Review that decision before merging them.')
        group = CoordinationGroup(primary_complaint_id=data.primary_complaint_id, actor_id=g.user.id, reason=data.reason)
        db.session.add(group)
        db.session.flush()
        membership = {m.complaint_id: m for m in old_members}
        for case in cases:
            if case.id in membership:
                membership[case.id].group_id = group.id
            else:
                db.session.add(CoordinationMember(complaint_id=case.id, group_id=group.id))
            event(case, 'overlap_merged', 'Complaint linked to a coordination group',
                  'Original complaint, access controls, evidence, deadlines and appeal rights retained.', {'group_id': group.id})
    for pair in pairs:
        pair.state = 'related' if group else 'unrelated'
        pair.version += 1
        db.session.add(Review(pair_id=pair.id, user_id=g.user.id, decision=pair.state, reason=data.reason, revisions=pair.evidence['revisions']))
        for case in (pair.a, pair.b):
            event(case, 'overlap_reviewed', 'Overlap suggestion ' + ('merged for coordination' if group else 'rejected'),
                  'Reason recorded in the authorized overlap review. The complaint remains active.', {'pair_id': pair.id})
            owner = db.session.get(User, case.owner_id)
            if owner and owner.active and db.session.scalar(select(Complaint.id).where(Complaint.id == case.id, scope(owner))):
                notify(owner.id, case, 'overlap_review', f'{case.reference}: Overlap suggestion {"merged for coordination" if group else "rejected"}.', f'pair-decision:{pair.id}:{pair.version}:{case.id}:{owner.id}')
    db.session.commit()
    return {'updated': len(pairs), 'group_id': group.id if group else None}


def coordination_json(case):
    member = db.session.get(CoordinationMember, case.id)
    if not member:
        return None
    group = db.session.get(CoordinationGroup, member.group_id)
    visible = db.session.scalars(select(Complaint).join(CoordinationMember, CoordinationMember.complaint_id == Complaint.id).where(
        CoordinationMember.group_id == group.id, scope()).order_by(Complaint.id)).all()
    return {'id': group.id, 'primary_complaint_id': group.primary_complaint_id if any(c.id == group.primary_complaint_id for c in visible) else None,
            'members': [{'id': c.id, 'reference': c.reference} for c in visible if has_content(c)]}
