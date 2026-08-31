from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class WsrGenerateRequest(BaseModel):
    start_date: date = Field(description="WSR report period start (Monday, inclusive)")
    end_date: date = Field(description="WSR report period end (Friday, inclusive)")
    template_id: str = Field(
        description="Saved WSR template id from POST /api/wsr/template/upload or /save",
    )
    force: bool = Field(
        default=False,
        description="Start a new background job even if one is already running",
    )


class WsrGenerationCheckResponse(BaseModel):
    can_generate: bool
    reason: Literal["new_week", "different_template", "same_template"]
    variant: int = 1
    variant_label: str = "WSR"
    template_id: str | None = None
    template_name: str | None = None
    message: str
    existing_variants: list[dict] = Field(default_factory=list)


class WsrJobStartResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    report_start_date: date
    report_end_date: date
    message: str


class WsrStatusResponse(BaseModel):
    status: Literal["not_found", "queued", "running", "completed", "failed"]
    job_id: str | None = None
    report_start_date: date | None = None
    report_end_date: date | None = None
    error: str | None = None
    result: "WsrGenerateResponse | None" = None


class WsrMeta(BaseModel):
    story_count: int
    slide_count: int
    titles_from_db: int = 0
    titles_fallback_summary: int = 0
    titles_generated: int = 0
    titles_reused: int = 0


class WsrWeekSummary(BaseModel):
    report_start_date: date
    report_end_date: date
    variant: int = 1
    variant_label: str = "WSR"
    template_id: str | None = None
    template_name: str | None = None
    filename: str
    generated_at: datetime
    story_count: int = 0
    slide_count: int = 0
    thumbnail_url: str | None = None
    download_url: str


class WsrWeekListResponse(BaseModel):
    count: int
    weeks: list[WsrWeekSummary]


class WsrContentSection(BaseModel):
    sprint_name: str
    sprint_dates: str
    sprint_status: str
    released: list[str]
    inprogress: list[str]
    completed: list[str]


class WsrContentSlide(BaseModel):
    project_key: str
    project_name: str
    title: str
    sections: list[WsrContentSection]
    key_activities: list[str]


class WsrPreviewSlide(BaseModel):
    slide_index: int
    title: str
    image_url: str


class WsrTemplateInfoResponse(BaseModel):
    filename: str
    original_filename: str
    uploaded_at: str
    slide_count: int
    file_size_bytes: int


class WsrTemplateItemResponse(BaseModel):
    id: str
    filename: str
    original_filename: str
    updated_at: str
    slide_count: int
    file_size_bytes: int
    is_draft: bool = False
    thumbnail_url: str


class WsrTemplateListResponse(BaseModel):
    templates: list[WsrTemplateItemResponse] = Field(default_factory=list)
    draft: WsrTemplateItemResponse | None = None


class WsrTemplateUploadResponse(WsrTemplateInfoResponse):
    preview_slides: list[WsrPreviewSlide] = Field(default_factory=list)


class WsrTemplateStageResponse(WsrTemplateItemResponse):
    preview_slides: list[WsrPreviewSlide] = Field(default_factory=list)


class WsrGenerateResponse(BaseModel):
    report_start_date: date
    report_end_date: date
    meta: WsrMeta
    preview: str
    filename: str
    download_url: str
    slides: list[WsrContentSlide]
    preview_slides: list[WsrPreviewSlide] = Field(default_factory=list)
    onedrive_web_url: str | None = None
    cloud_web_url: str | None = None
    cloud_provider: str | None = None
    variant: int = 1
    variant_label: str = "WSR"
    template_id: str | None = None
    template_name: str | None = None


WsrStatusResponse.model_rebuild()
