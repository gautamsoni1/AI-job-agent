import os
from datetime import datetime
from pathlib import Path

import structlog
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

logger = structlog.get_logger()

TEMPLATES_DIR = Path("app/templates")
OUTPUT_DIR = Path("generated_resumes")


class ResumeGeneratorService:
    def __init__(self):
        OUTPUT_DIR.mkdir(exist_ok=True)
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=True
        )

    async def generate_pdf(self, resume_data: dict, template: str = "resume_ats_clean", user_id: str = "") -> str:
        """Generate PDF resume from structured data. Returns file path."""
        html_content = self._render_template(f"{template}.html", resume_data)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"resume_{user_id}_{timestamp}.pdf"
        output_path = OUTPUT_DIR / filename

        try:
            HTML(string=html_content, base_url=str(TEMPLATES_DIR)).write_pdf(str(output_path))
            logger.info("resume_pdf_generated", path=str(output_path))
            return str(output_path)
        except Exception as e:
            logger.error("resume_pdf_failed", error=str(e))
            raise

    async def generate_docx(self, resume_data: dict, user_id: str = "") -> str:
        """Generate DOCX resume. Returns file path."""
        from docx import Document
        from docx.shared import Pt, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        doc = Document()

        # Title — candidate name
        name = resume_data.get("full_name", "")
        title_para = doc.add_paragraph()
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = title_para.add_run(name)
        run.bold = True
        run.font.size = Pt(18)

        # Contact info
        contact = resume_data.get("contact", {})
        contact_line = " | ".join(filter(None, [
            contact.get("email"), contact.get("phone"),
            contact.get("linkedin"), contact.get("location")
        ]))
        contact_para = doc.add_paragraph(contact_line)
        contact_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

        doc.add_paragraph()

        # Summary
        if resume_data.get("summary"):
            doc.add_heading("Professional Summary", level=2)
            doc.add_paragraph(resume_data["summary"])

        # Experience
        if resume_data.get("experience"):
            doc.add_heading("Work Experience", level=2)
            for exp in resume_data["experience"]:
                p = doc.add_paragraph()
                run = p.add_run(f"{exp.get('title', '')} — {exp.get('company', '')}")
                run.bold = True
                doc.add_paragraph(f"{exp.get('start_date', '')} – {exp.get('end_date', 'Present')} | {exp.get('location', '')}")
                for bullet in exp.get("bullets", []):
                    doc.add_paragraph(f"• {bullet}")

        # Education
        if resume_data.get("education"):
            doc.add_heading("Education", level=2)
            for edu in resume_data["education"]:
                p = doc.add_paragraph()
                run = p.add_run(f"{edu.get('degree', '')} — {edu.get('institution', '')}")
                run.bold = True
                doc.add_paragraph(f"{edu.get('year', '')}")

        # Skills
        if resume_data.get("skills"):
            doc.add_heading("Skills", level=2)
            doc.add_paragraph(", ".join(resume_data["skills"]))

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"resume_{user_id}_{timestamp}.docx"
        output_path = OUTPUT_DIR / filename
        doc.save(str(output_path))
        logger.info("resume_docx_generated", path=str(output_path))
        return str(output_path)

    def _render_template(self, template_name: str, data: dict) -> str:
        try:
            template = self.jinja_env.get_template(template_name)
            return template.render(**data)
        except Exception as e:
            logger.error("template_render_failed", template=template_name, error=str(e))
            raise