from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class GenerateCoverLetterRequest(BaseModel):
    job_id: str
    resume_id: str
    tone: str = "professional"  # professional | friendly | formal


class CoverLetterResponse(BaseModel):
    id: str
    company_name: str
    role_title: str
    tone: str
    content: str
    file_path: Optional[str]
    version: int
    created_at: datetime