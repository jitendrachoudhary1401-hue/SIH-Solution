"""Scoped complaint register PDF, using the same permissions and filters as CSV."""
import io
from html import escape
from flask import abort, send_file
from .complaint_reports import report_api
from .auth import authenticated, allowed, has_content
from .models import db, now, iso, Complaint


def build_register(cases, exported_by):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, LongTable, TableStyle, Spacer
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import reportlab
    from pathlib import Path
    font = 'OneCaseRegister'
    if font not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(font, str(Path(reportlab.__file__).parent / 'fonts' / 'Vera.ttf')))
    ink, accent = colors.HexColor('#352c24'), colors.HexColor('#9d452d')
    body = ParagraphStyle('RegisterBody', fontName=font, fontSize=8, leading=12, textColor=ink, splitLongWords=True)
    title = ParagraphStyle('RegisterTitle', parent=body, fontSize=22, leading=28, spaceAfter=10)
    def paragraph(value):
        return Paragraph(escape(str(value or 'Not recorded')).replace('\n', '<br/>'), body)
    output = io.BytesIO()
    width, height = landscape(A4)
    rows = [[paragraph(s) for s in ['Complaint / institution', 'Issue / incident location', 'Status / accountable owner', 'Received / deadline (IST)']]]
    from zoneinfo import ZoneInfo
    from datetime import timezone
    def local(value):
        return value.replace(tzinfo=timezone.utc).astimezone(ZoneInfo('Asia/Kolkata')).strftime('%d %b %Y, %I:%M %p') if value else 'Not set'
    for c in cases:
        detail = f'{c.category}\n{c.issue_summary}\nLocation: {c.incident_location or "Not recorded"}' if has_content(c) else f'{c.category}\nComplaint details restricted'
        rows.append([paragraph(f'{c.reference}\n{c.institution.name}'), paragraph(detail),
                     paragraph(f'{c.status.replace("_", " ")}\n{c.owner.name}\n{c.bureau.code}'), paragraph(f'Received: {local(c.received_at)}\nDue: {local(c.due_at)}')])
    table = LongTable(rows, colWidths=[210, 220, 155, width - 72 - 585], repeatRows=1, hAlign='LEFT')
    table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor('#eee3d2')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#faf6ef')]),
        ('VALIGN', (0,0), (-1,-1), 'TOP'), ('GRID', (0,0), (-1,-1), .4, colors.HexColor('#dcc7ad')),
        ('LEFTPADDING', (0,0), (-1,-1), 9), ('RIGHTPADDING', (0,0), (-1,-1), 9),
        ('TOPPADDING', (0,0), (-1,-1), 9), ('BOTTOMPADDING', (0,0), (-1,-1), 9)]))
    generated = iso(now())
    story = [Paragraph('OneCase | Complaint register', title), paragraph(f'{len(cases)} authorized records | Exported by {exported_by} | Generated {generated}'),
             paragraph('Current filters and export permissions apply. Only authorized records are included. Dates below use Asia/Kolkata (IST).'), Spacer(1, 16), table]
    def decorate(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(accent)
        canvas.setLineWidth(3)
        canvas.line(36, height-27, width-36, height-27)
        canvas.setFont(font, 8)
        canvas.setFillColor(ink)
        canvas.drawString(36, 22, 'ONECASE / PRIVATE COMPLAINT REGISTER')
        canvas.drawRightString(width-36, 22, f'Page {document.page}')
        canvas.restoreState()
    SimpleDocTemplate(output, pagesize=landscape(A4), leftMargin=36, rightMargin=36, topMargin=43, bottomMargin=40,
                      title='OneCase complaint register', author='OneCase').build(story, onFirstPage=decorate, onLaterPages=decorate)
    return output.getvalue()


@report_api.get('/reports/complaints.pdf')
@authenticated
def export_register_pdf():
    from flask import g
    from .api import filtered_cases, event
    query = filtered_cases().order_by(Complaint.id)
    cases = [c for c in db.session.scalars(query) if allowed(c, 'case.export')]
    if not cases and db.session.scalar(filtered_cases().limit(1)):
        abort(403, description='A separate export grant is required for these records.')
    content = build_register(cases, g.user.name)
    event(None, 'exported', 'Scoped complaint register PDF exported', changes={'record_count': len(cases), 'format': 'pdf'})
    db.session.commit()
    return send_file(io.BytesIO(content), mimetype='application/pdf', as_attachment=True, download_name='onecase-complaints.pdf')
