"""Pydantic models for IVY AI Counsellor."""
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=100)
    message: str = Field(..., min_length=1, max_length=500)


class ExtractedProfile(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    target_course: str | None = None
    target_country: str | None = None
    target_intake: str | None = None
    budget_inr: str | None = None
    ielts_score: str | None = None
    percentage: str | None = None


class IntentResult(BaseModel):
    intent_level: str  # BROWSING | RESEARCHING | CONSIDERING | HOT_LEAD
    lead_score: int = 0
    extracted_profile: ExtractedProfile = Field(default_factory=ExtractedProfile)
    conversation_summary: str = ""
    recommended_action: str = ""


class LeadOut(BaseModel):
    id: int
    session_id: str
    name: str | None
    phone: str | None
    email: str | None
    target_course: str | None
    target_country: str | None
    target_intake: str | None
    budget_inr: int | None
    ielts_score: str | None
    percentage: str | None
    lead_score: int
    intent_level: str | None
    conversation_summary: str | None
    recommended_action: str | None
    notified_at: str | None
    created_at: str

    class Config:
        from_attributes = True


class PDFUploadOut(BaseModel):
    pdf_id: str
    filename: str
    category: str
    chunk_count: int
    status: str
    upload_date: str

    class Config:
        from_attributes = True


class GapQueryOut(BaseModel):
    query_text: str
    frequency: int
    fallback_type: str | None
