import re
from ast import literal_eval
from datetime import datetime
from typing import Optional

import structlog
from google.oauth2 import service_account
from googleapiclient.discovery import build

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

COLUMNS = [
    "Company Name", "Role", "Location", "Experience", "Salary",
    "Package", "Required Skills", "Match Score", "ATS Score",
    "Apply Link", "Application Deadline", "Source", "Posted Date",
    "Status", "Notes", "Date Added", "Application Status",
    "Resume Version Used", "Cover Letter Version Used",
    "Interview Date", "Offer Status", "Last Updated"
]


class GoogleSheetsService:
    def __init__(self):
        self._service = None

    def _get_service(self):
        if self._service:
            return self._service
        try:
            creds = service_account.Credentials.from_service_account_file(
                settings.GOOGLE_SERVICE_ACCOUNT_FILE,
                scopes=SCOPES
            )
            self._service = build("sheets", "v4", credentials=creds)
            return self._service
        except Exception as e:
            logger.error("google_sheets_auth_failed", error=str(e))
            raise

    async def ensure_header(self) -> bool:
        """Create header row if sheet is empty."""
        try:
            service = self._get_service()
            result = service.spreadsheets().values().get(
                spreadsheetId=settings.GOOGLE_SHEET_ID,
                range="Sheet1!A1:V1"
            ).execute()
            values = result.get("values", [])
            if not values:
                service.spreadsheets().values().update(
                    spreadsheetId=settings.GOOGLE_SHEET_ID,
                    range="Sheet1!A1",
                    valueInputOption="RAW",
                    body={"values": [COLUMNS]}
                ).execute()
            return True
        except Exception as e:
            logger.error("sheets_header_failed", error=str(e))
            return False

    async def sync_job(self, job: dict, match_score: float = 0.0, ats_score: float = 0.0) -> dict:
        """Append a job row to the sheet."""
        try:
            await self.ensure_header()
            service = self._get_service()
            row = [
                self._value(job.get("company"), "Company not provided"),
                self._value(job.get("title"), "Role not provided"),
                self._value(job.get("location"), "Location not provided"),
                self._value(job.get("experience_required"), "Experience not provided"),
                self._value(job.get("salary_range"), "Salary not provided"),
                self._value(job.get("package") or job.get("bond"), "Package/bond not provided"),
                self._skills(job.get("required_skills")),
                str(round(match_score, 1)),
                str(round(ats_score, 1)),
                self._value(job.get("apply_link"), "Apply link not provided"),
                self._value(job.get("deadline"), "Deadline not provided"),
                self._value(job.get("source"), "Source not provided"),
                self._value(job.get("posted_at") or job.get("posted_date"), "Posted date not provided"),
                "New",
                self._notes(job),
                datetime.utcnow().strftime("%Y-%m-%d"),
                "Not Applied",
                "Resume version not selected",
                "Cover letter not generated",
                "Interview not scheduled",
                "Offer not received",
                datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
            ]
            result = service.spreadsheets().values().append(
                spreadsheetId=settings.GOOGLE_SHEET_ID,
                range="Sheet1!A1",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": [row]}
            ).execute()
            updated_range = result.get("updates", {}).get("updatedRange", "")
            row_number = self._extract_row_number(updated_range)
            logger.info("job_synced_to_sheets", company=job.get("company"), row=row_number)
            return {"success": True, "row_number": row_number}
        except Exception as e:
            logger.error("sheets_sync_failed", error=str(e))
            return {"success": False, "error": str(e)}

    def _value(self, value, fallback: str) -> str:
        if value is None:
            return fallback
        if isinstance(value, str) and value.strip().startswith("{"):
            try:
                value = literal_eval(value)
            except (ValueError, SyntaxError):
                pass
        if isinstance(value, str) and not value.strip():
            return fallback
        if isinstance(value, dict):
            for key in ("name", "title", "value", "text"):
                if value.get(key):
                    return str(value[key])
            return fallback
        if isinstance(value, list):
            return ", ".join(str(item) for item in value if item) or fallback
        return str(value)

    def _skills(self, skills) -> str:
        return self._value(skills, "Skills not provided")

    def _notes(self, job: dict) -> str:
        description = re.sub(r"<[^>]+>", " ", self._value(job.get("description"), "Description not provided"))
        description = re.sub(r"\s+", " ", description).strip()
        employment = self._value(job.get("employment_type"), "Employment type not provided")
        work_type = self._value(job.get("work_type"), "Work type not provided")
        return f"{employment}; {work_type}; {description[:500]}"

    async def update_application_status(self, row_number: int, status: str) -> bool:
        try:
            service = self._get_service()
            status_col = "Q"  # Column Q = Application Status (index 16)
            updated_col = "V"  # Column V = Last Updated
            service.spreadsheets().values().batchUpdate(
                spreadsheetId=settings.GOOGLE_SHEET_ID,
                body={
                    "valueInputOption": "RAW",
                    "data": [
                        {"range": f"Sheet1!{status_col}{row_number}", "values": [[status]]},
                        {"range": f"Sheet1!{updated_col}{row_number}", "values": [[datetime.utcnow().strftime("%Y-%m-%d %H:%M")]]},
                    ]
                }
            ).execute()
            return True
        except Exception as e:
            logger.error("sheets_status_update_failed", error=str(e))
            return False

    async def check_duplicate(self, company: str, role: str, apply_link: str) -> bool | int:
        """Returns False if no duplicate, row_number if duplicate found."""
        try:
            service = self._get_service()
            result = service.spreadsheets().values().get(
                spreadsheetId=settings.GOOGLE_SHEET_ID,
                range="Sheet1!A:J"
            ).execute()
            values = result.get("values", [])
            for i, row in enumerate(values[1:], start=2):
                if len(row) >= 10:
                    row_company = row[0].strip().lower()
                    row_role = row[1].strip().lower()
                    row_link = row[9].strip()
                    if row_link == apply_link or (row_company == company.lower() and row_role == role.lower()):
                        return i
            return False
        except Exception as e:
            logger.error("sheets_duplicate_check_failed", error=str(e))
            return False

    def _extract_row_number(self, updated_range: str) -> int:
        try:
            parts = updated_range.split("!")
            if len(parts) > 1:
                cell_ref = parts[1].split(":")[0]
                row_str = "".join(c for c in cell_ref if c.isdigit())
                return int(row_str) if row_str else 0
        except Exception:
            pass
        return 0
