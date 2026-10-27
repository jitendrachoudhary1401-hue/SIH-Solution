"""Frozen closure reports. PDF bytes are saved in the closing transaction."""
import hashlib
import io
import json
from html import escape
from flask import Blueprint, abort, send_file
from sqlalchemy import select
from .auth import authenticated, case_or_404, has_content
from .models import db, ComplaintReport, ActionEvent, Attachment, Assignment, User, iso, now

report_api = Blueprint('complaint_reports', __name__)


def build_pdf(case, closure):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    output = io.BytesIO()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle('Record', parent=styles['BodyText'], fontSize=9, leading=14, spaceAfter=7, splitLongWords=True))
    story = []

    def text(value, style='Record'):
        story.append(Paragraph(escape(str(value or 'Not recorded')).replace('\n', '<br/>'), styles[style]))

    def field(title, value):
        text(title, 'Heading3')
        text(value)

    def page(canvas, document):
        width, height = A4
        canvas.saveState()
        canvas.setFillColor(colors.Color(.80, .85, .91, alpha=.32))
        canvas.translate(width / 2, height / 2)
        canvas.rotate(42)
        canvas.setFont('Helvetica-Bold', 42)
        canvas.drawCentredString(0, 0, 'ONECASE')
        canvas.setFont('Helvetica', 15)
        canvas.drawCentredString(0, -27, 'COMPLAINT RECORD')
        canvas.restoreState()
        canvas.saveState()
        canvas.setFillColor(colors.HexColor('#24425f'))
        canvas.setFont('Helvetica-Bold', 9)
        canvas.drawString(42, height - 31, 'ONECASE / CLOSURE REPORT')
        canvas.setFont('Helvetica', 8)
        canvas.drawString(42, 28, f'Closure event #{closure.id} | UTC timestamps | Private complaint record')
        canvas.drawRightString(width - 42, 28, f'Page {document.page}')
        canvas.restoreState()

    text('Complaint closure report', 'Title')
    text(case.reference, 'Heading2')
    text(f'Frozen at closure: {iso(closure.created_at)}. Later actions and reopenings do not alter this copy.')
    for title, value in [
        ('Institution / region', f'{case.institution.name} / {case.institution.region}'),
        ('Submitter / applicant type', f'{case.submitter_name} / {case.complainant_type}'),
        ('Affected person / representation', f'{case.affected_person}\n{case.representation_basis}'),
        ('Category / summary', f'{case.category}\n{case.issue_summary}'),
        ('Complaint description', case.description),
        ('Source / reference', f'{case.source_channel} / {case.source_reference}'),
        ('Previous proceedings', case.prior_proceedings),
        ('Receipt / entry', f'{iso(case.received_at)} / {iso(case.entered_at)}'),
        ('Final status / accountable officer', f'{case.status} / {case.owner.name} / {case.bureau.code}'),
        ('Deadline / next action', f'{iso(case.due_at)} / {case.deadline_policy}\n{case.next_action}'),
        ('Closure decision', f'{closure.actor_name}\n{closure.reason}\n{closure.changes.get("communication", "")}'),
    ]:
        field(title, value)
    text('Assignment history', 'Heading1')
    for item in db.session.scalars(select(Assignment).where(Assignment.complaint_id == case.id).order_by(Assignment.id)):
        user = db.session.get(User, item.owner_id)
        text(f'{user.name if user else item.owner_id} | {iso(item.started_at)} to {iso(item.ended_at) or "Closure"}\n{item.reason}')
    text('Complete action timeline', 'Heading1')
    for item in db.session.scalars(select(ActionEvent).where(ActionEvent.complaint_id == case.id, ActionEvent.id <= closure.id).order_by(ActionEvent.id)):
        text(f'#{item.id} | {item.summary}', 'Heading3')
        text(f'Who: {item.actor_name} (account #{item.actor_id or "system"}) | When: {iso(item.created_at)}\nAction: {item.kind} | Outcome: {item.outcome}\n{item.reason}')
        if item.changes:
            text(json.dumps(item.changes, ensure_ascii=False, indent=2))
    text('Supporting proof manifest', 'Heading1')
    attachments = db.session.scalars(select(Attachment).where(Attachment.complaint_id == case.id).order_by(Attachment.id)).all()
    if not attachments:
        text('No supporting files were recorded at closure.')
    for item in attachments:
        uploader = db.session.get(User, item.uploaded_by) if item.uploaded_by else None
        field(f'Proof #{item.id}: {item.filename}',
              f'Type: {item.media_type} | Size: {item.size} bytes\nUploaded by: {uploader.name if uploader else "Legacy upload - account not recorded"}\nUploaded: {iso(item.created_at)} | Scan state at closure: {item.scan_state}\nSHA-256: {item.checksum}')
    text('Proof files remain in private storage and require an authorized session. Video files are listed as references. This watermark identifies the record; it is not a digital signature.')
    story.append(Spacer(1, 10))
    SimpleDocTemplate(output, pagesize=A4, leftMargin=42, rightMargin=42, topMargin=55, bottomMargin=48,
                      title=f'OneCase closure - {case.reference}', author='OneCase').build(story, onFirstPage=page, onLaterPages=page)
    return output.getvalue()


def freeze_report(case, closure):
    from .api import notify
    db.session.flush()
    content = build_pdf(case, closure)
    report = ComplaintReport(complaint_id=case.id, closure_event_id=closure.id, created_at=now(),
                             pdf=content, checksum=hashlib.sha256(content).hexdigest())
    db.session.add(report)
    db.session.flush()
    recipients = set(db.session.scalars(select(User.id).where(User.role == 'admin', User.active.is_(True))))
    if case.submitter_user_id:
        recipients.add(case.submitter_user_id)
    for user_id in recipients:
        notify(user_id, case, 'closure_report', f'{case.reference} closed. Your watermarked PDF is ready in the complaint record.', f'closure-report:{report.id}:{user_id}')


@report_api.get('/complaints/<int:case_id>/reports/<int:report_id>.pdf')
@authenticated
def download_report(case_id, report_id):
    case = case_or_404(case_id)
    if not has_content(case):
        abort(403)
    report = db.session.scalar(select(ComplaintReport).where(ComplaintReport.id == report_id, ComplaintReport.complaint_id == case.id))
    if not report:
        abort(404)
    response = send_file(io.BytesIO(report.pdf), mimetype='application/pdf', as_attachment=True,
                         download_name=f'{case.reference}-closure-{report.id}.pdf')
    response.headers['X-Content-SHA256'] = report.checksum
    return response
