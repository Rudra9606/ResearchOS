"""Structured research report rendering, export, and persistence helpers."""

import html
import re
from pathlib import Path
from uuid import UUID
from xml.sax.saxutils import escape as xml_escape

from sqlalchemy.orm import Session

from app.crud.research_report import (
    create_research_report,
    delete_research_report,
    get_research_report_by_id,
    get_research_run_reports,
    update_research_report,
)
from app.schemas.report_document import StructuredResearchReport
from app.schemas.research_report import ResearchReportCreate

REPORT_DIR = Path("reports")


def ensure_report_dir() -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    return REPORT_DIR


def safe_report_path(user_id: UUID, report_id: UUID, report_format: str) -> Path:
    if report_format not in {"pdf", "docx", "html"}:
        raise ValueError("Unsupported report format.")
    user_dir = (ensure_report_dir() / str(user_id)).resolve()
    user_dir.mkdir(parents=True, exist_ok=True)
    path = (user_dir / f"{report_id}.{report_format}").resolve()
    if user_dir not in path.parents:
        raise ValueError("Invalid report path.")
    return path


def create_research_report_record(
    db: Session, research_run_id: UUID, user_id: UUID, report_data: ResearchReportCreate
):
    return create_research_report(db, research_run_id, user_id, report_data)


def get_report(db: Session, report_id: UUID, user_id: UUID):
    return get_research_report_by_id(db, report_id, user_id)


def list_run_reports(db: Session, research_run_id: UUID, user_id: UUID, skip=0, limit=100):
    return get_research_run_reports(db, research_run_id, user_id, skip, limit)


def update_report_status(
    db: Session,
    report_id: UUID,
    user_id: UUID,
    generation_status: str | None = None,
    content: str | None = None,
    file_path: str | None = None,
):
    return update_research_report(
        db, report_id, user_id, generation_status, content, file_path
    )


def delete_report(db: Session, report_id: UUID, user_id: UUID) -> bool:
    return delete_research_report(db, report_id, user_id)


def render_report_markdown(report: StructuredResearchReport | str) -> str:
    if isinstance(report, str):
        return report
    lines = [f"# {report.title}", ""]
    sections = [
        report.executive_summary,
        report.research_objectives,
        report.research_questions,
        report.methodology,
        report.web_research_findings,
        report.academic_research_findings,
        report.document_analysis_findings,
        report.dataset_analysis_findings,
        report.verified_claims,
        report.limitations,
        report.conclusion,
    ]
    for section in sections:
        lines.extend([f"## {section.title}", ""])
        if not section.available:
            lines.extend(["Evidence unavailable for this section.", ""])
        else:
            lines.extend([section.content, ""])
    lines.extend(["## References", ""])
    for index, citation in enumerate(report.references, start=1):
        authors = ", ".join(citation.authors) or "Unknown author"
        lines.append(
            f"{index}. {authors}. {citation.title}. "
            f"{citation.publisher_or_venue or citation.source_type}. "
            f"{citation.url or ''}"
        )
    return "\n".join(lines)


def _paragraphs(content: str):
    for block in re.split(r"\n\s*\n", content):
        block = block.strip()
        if block:
            yield block.replace("\n", "<br/>")


def generate_pdf_report(
    content: StructuredResearchReport | str, title: str, output_path: str
) -> str:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
    )

    markdown = render_report_markdown(content)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CoverTitle", parent=styles["Title"], alignment=TA_CENTER, fontSize=24))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], spaceBefore=14, textColor=colors.HexColor("#183B56")))
    story = [
        Spacer(1, 2.2 * inch),
        Paragraph(xml_escape(title), styles["CoverTitle"]),
        Spacer(1, 0.3 * inch),
        Paragraph("ResearchOS Evidence Report", styles["Normal"]),
        PageBreak(),
        Paragraph("Table of Contents", styles["Heading1"]),
    ]
    headings = [line[3:].strip() for line in markdown.splitlines() if line.startswith("## ")]
    story.extend(Paragraph(f"{index}. {xml_escape(heading)}", styles["Normal"]) for index, heading in enumerate(headings, 1))
    story.append(PageBreak())
    for block in markdown.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if block.startswith("# "):
            story.append(Paragraph(xml_escape(block[2:]), styles["Title"]))
        elif block.startswith("## "):
            story.append(Paragraph(xml_escape(block[3:]), styles["Section"]))
        else:
            story.append(Paragraph(xml_escape(block).replace("\n", "<br/>"), styles["BodyText"]))
        story.append(Spacer(1, 8))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawString(0.7 * inch, 0.45 * inch, "ResearchOS")
        canvas.drawRightString(7.8 * inch, 0.45 * inch, f"Page {doc.page}")
        canvas.restoreState()

    SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=0.7 * inch,
        leftMargin=0.7 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
        title=title,
    ).build(story, onFirstPage=footer, onLaterPages=footer)
    return output_path


def generate_docx_report(
    content: StructuredResearchReport | str, title: str, output_path: str
) -> str:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt

    document = Document()
    section = document.sections[0]
    section.top_margin = Inches(0.7)
    section.bottom_margin = Inches(0.7)
    title_paragraph = document.add_paragraph()
    title_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title_paragraph.add_run(title)
    run.bold = True
    run.font.size = Pt(24)
    document.add_page_break()
    for line in render_report_markdown(content).splitlines():
        if line.startswith("# "):
            document.add_heading(line[2:], level=0)
        elif line.startswith("## "):
            document.add_heading(line[3:], level=1)
        elif line.strip():
            document.add_paragraph(line)

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer_run = footer.add_run("ResearchOS | Page ")
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    footer._p.append(field)
    document.save(output_path)
    return output_path


def generate_html_report(
    content: StructuredResearchReport | str, title: str, output_path: str
) -> str:
    markdown = render_report_markdown(content)
    body = []
    for block in markdown.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if block.startswith("# "):
            body.append(f"<h1>{html.escape(block[2:])}</h1>")
        elif block.startswith("## "):
            body.append(f"<h2>{html.escape(block[3:])}</h2>")
        else:
            body.append(f"<p>{html.escape(block).replace(chr(10), '<br>')}</p>")
    if isinstance(content, StructuredResearchReport):
        references = []
        for citation in content.references:
            label = html.escape(citation.title)
            url = str(citation.url) if citation.url else ""
            if url:
                label = f'<a href="{html.escape(url, quote=True)}" rel="noopener">{label}</a>'
            references.append(f"<li>{label}</li>")
        body.append('<h2 id="references">References</h2><ol>' + "".join(references) + "</ol>")
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;line-height:1.6;color:#243447}}
h1{{border-bottom:3px solid #183B56;padding-bottom:.5rem}}h2{{color:#183B56;margin-top:2rem}}
a{{color:#1261A0}}@media print{{body{{max-width:none}}}}</style></head>
<body><nav><a href="#report">Report</a> | <a href="#references">References</a></nav>
<main id="report">{"".join(body)}</main></body></html>"""
    Path(output_path).write_text(document, encoding="utf-8")
    return output_path


def export_report_document(
    report: StructuredResearchReport | str,
    title: str,
    report_format: str,
    output_path: str,
) -> str:
    if report_format == "pdf":
        return generate_pdf_report(report, title, output_path)
    if report_format == "docx":
        return generate_docx_report(report, title, output_path)
    if report_format == "html":
        return generate_html_report(report, title, output_path)
    raise ValueError("Unsupported report format.")
