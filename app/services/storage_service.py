import os
import uuid
from datetime import datetime
from pathlib import Path

import aiofiles
import structlog

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

ALLOWED_EXTENSIONS = {".pdf", ".docx"}
MAX_FILE_SIZE_MB = 10


class StorageService:
    def __init__(self):
        self.upload_path = Path(settings.UPLOAD_PATH)
        self.generated_path = Path(settings.GENERATED_FILES_PATH)
        self.upload_path.mkdir(parents=True, exist_ok=True)
        self.generated_path.mkdir(parents=True, exist_ok=True)

    async def save_resume(self, file_bytes: bytes, original_filename: str, user_id: str) -> dict:
        """Save uploaded resume file. Returns file metadata."""
        ext = Path(original_filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(f"File type {ext} not allowed. Use PDF or DOCX.")

        size_mb = len(file_bytes) / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            raise ValueError(f"File too large: {size_mb:.1f}MB. Max {MAX_FILE_SIZE_MB}MB.")

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"{user_id}_{timestamp}_{unique_id}{ext}"
        file_path = self.upload_path / filename

        async with aiofiles.open(file_path, "wb") as f:
            await f.write(file_bytes)

        logger.info("resume_saved", path=str(file_path), size_mb=round(size_mb, 2))
        return {
            "file_path": str(file_path),
            "original_filename": original_filename,
            "stored_filename": filename,
            "file_type": ext.lstrip("."),
            "size_bytes": len(file_bytes),
            "size_mb": round(size_mb, 2),
        }

    async def read_file(self, file_path: str) -> bytes:
        """Read file bytes from path."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        async with aiofiles.open(path, "rb") as f:
            return await f.read()

    async def delete_file(self, file_path: str) -> bool:
        """Delete a file."""
        path = Path(file_path)
        if path.exists():
            os.remove(path)
            logger.info("file_deleted", path=file_path)
            return True
        return False

    def get_file_url(self, file_path: str) -> str:
        """Generate a relative URL for file download."""
        return f"/api/v1/files/{Path(file_path).name}"

    async def save_generated_file(self, content: bytes, filename: str, subfolder: str = "") -> str:
        """Save AI-generated file (cover letter, resume PDF). Returns path."""
        target_dir = self.generated_path / subfolder if subfolder else self.generated_path
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / filename
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)
        return str(file_path)