from datetime import datetime

from pydantic import BaseModel


class UploadedFile(BaseModel):
    filename: str
    size: int
    content_type: str | None = None


class UploadResponse(BaseModel):
    success: bool
    job_id: str
    uploaded_at: datetime
    total_files: int
    files: list[UploadedFile]