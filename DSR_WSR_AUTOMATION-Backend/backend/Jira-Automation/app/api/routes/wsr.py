from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.wsr import (
    WsrContentSlide,
    WsrGenerateRequest,
    WsrGenerateResponse,
    WsrGenerationCheckResponse,
    WsrJobStartResponse,
    WsrMeta,
    WsrPreviewSlide,
    WsrStatusResponse,
    WsrTemplateInfoResponse,
    WsrTemplateItemResponse,
    WsrTemplateListResponse,
    WsrTemplateStageResponse,
    WsrTemplateUploadResponse,
    WsrWeekListResponse,
    WsrWeekSummary,
)
from app.paths import wsr_output_paths
from app.services.pptx_editor_service import (
    export_editor_document_to_pptx,
    load_wsr_editor_deck,
    save_wsr_editor_deck,
)
from app.services.wsr_job_service import get_job, start_wsr_job
from app.services.wsr_preview_service import (
    export_wsr_slide_previews,
    resolve_preview_image_path,
)
from app.services.cloud_upload_service import (
    cloud_response_fields_from_upload,
    try_upload_wsr_ppt,
)
from app.services.wsr_service import (
    generate_wsr_deck,
    list_generated_wsr_weeks,
    load_wsr_week,
    resolve_wsr_ppt_path,
)
from app.services.wsr_variant_service import check_wsr_generation
from app.services.wsr_template_upload_service import (
    cancel_draft_template,
    export_template_slide_previews,
    get_draft_template_info,
    get_uploaded_template_info,
    list_saved_templates,
    resolve_template_path,
    resolve_template_preview_image_path,
    save_draft_template,
    save_uploaded_template,
    stage_template_upload,
)

router = APIRouter(prefix="/api/wsr", tags=["wsr"])


class EditorDocumentPayload(BaseModel):
    document: dict



def _build_generate_response(result: dict) -> WsrGenerateResponse:
    return WsrGenerateResponse(
        report_start_date=date.fromisoformat(result["report_start_date"]),
        report_end_date=date.fromisoformat(result["report_end_date"]),
        meta=WsrMeta(**result["meta"]),
        preview=result["preview"],
        filename=result["filename"],
        download_url=result["download_url"],
        slides=[WsrContentSlide(**slide) for slide in result.get("slides", [])],
        preview_slides=[
            WsrPreviewSlide(**slide) for slide in result.get("preview_slides", [])
        ],
        onedrive_web_url=result.get("onedrive_web_url"),
        cloud_web_url=result.get("cloud_web_url"),
        cloud_provider=result.get("cloud_provider"),
        variant=int(result.get("variant") or 1),
        variant_label=str(result.get("variant_label") or "WSR"),
        template_id=result.get("template_id"),
        template_name=result.get("template_name"),
    )


@router.get("/weeks", response_model=WsrWeekListResponse)
def list_wsr_weeks() -> WsrWeekListResponse:
    """List all previously generated WSR decks (newest report week first)."""
    weeks = [
        WsrWeekSummary(**item) for item in list_generated_wsr_weeks()
    ]
    return WsrWeekListResponse(count=len(weeks), weeks=weeks)


@router.get("/week", response_model=WsrGenerateResponse)
def get_wsr_week(
    start_date: date = Query(..., description="WSR week start (Monday)"),
    end_date: date = Query(..., description="WSR week end (Friday)"),
    variant: int = Query(1, ge=1, description="WSR deck variant (1=primary, 2=V2, …)"),
) -> WsrGenerateResponse:
    """Load an existing generated WSR deck for a week without regenerating."""
    try:
        result = load_wsr_week(start_date, end_date, variant=variant)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _build_generate_response(result)


@router.get("/generate/check", response_model=WsrGenerationCheckResponse)
def check_wsr_generation_route(
    start_date: date = Query(..., description="WSR week start (Monday)"),
    end_date: date = Query(..., description="WSR week end (Friday)"),
    template_id: str = Query(..., description="Saved WSR template id"),
) -> WsrGenerationCheckResponse:
    """Check whether a week can be generated with the selected template."""
    try:
        resolve_template_path(template_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail=(
                f"start_date ({start_date}) must be on or before "
                f"end_date ({end_date})."
            ),
        )

    result = check_wsr_generation(start_date, end_date, template_id)
    return WsrGenerationCheckResponse(**result)


@router.post("/generate", response_model=WsrJobStartResponse, status_code=202)
def generate_wsr(
    body: WsrGenerateRequest,
    db: Session = Depends(get_db),
) -> WsrJobStartResponse:
    """
    Queue WSR generation on a background thread.

    Poll GET /api/wsr/status until status is completed or failed.
    """
    del db  # generation uses its own DB session in the worker thread

    if body.start_date > body.end_date:
        raise HTTPException(
            status_code=400,
            detail=(
                f"start_date ({body.start_date}) must be on or before "
                f"end_date ({body.end_date})."
            ),
        )

    try:
        resolve_template_path(body.template_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    generation_check = check_wsr_generation(
        body.start_date,
        body.end_date,
        body.template_id,
    )
    if not generation_check["can_generate"]:
        raise HTTPException(
            status_code=409,
            detail=generation_check["message"],
        )

    job = start_wsr_job(
        start_date=body.start_date,
        end_date=body.end_date,
        template_id=body.template_id,
        force=body.force,
    )
    return WsrJobStartResponse(
        job_id=job.job_id,
        status=job.status,
        report_start_date=body.start_date,
        report_end_date=body.end_date,
        message=(
            "WSR generation started in the background. "
            "Poll GET /api/wsr/status for progress."
        ),
    )


@router.get("/status", response_model=WsrStatusResponse)
def get_wsr_status(
    start_date: date = Query(..., description="WSR week start (Monday)"),
    end_date: date = Query(..., description="WSR week end (Friday)"),
) -> WsrStatusResponse:
    """Poll background WSR generation for a week."""
    job = get_job(start_date, end_date)
    if job is None:
        return WsrStatusResponse(status="not_found")

    response = WsrStatusResponse(
        status=job.status,
        job_id=job.job_id,
        report_start_date=job.start_date,
        report_end_date=job.end_date,
        error=job.error,
    )
    if job.status == "completed" and job.result is not None:
        if "download_url" not in job.result:
            variant = int(job.result.get("variant") or 1)
            job.result["download_url"] = (
                f"/api/wsr/download?start_date={start_date.isoformat()}"
                f"&end_date={end_date.isoformat()}"
                f"&variant={variant}"
            )
        response.result = _build_generate_response(job.result)
    return response


@router.get("/preview/slides", response_model=list[WsrPreviewSlide])
def list_wsr_preview_slides(
    start_date: date = Query(..., description="WSR week start (Monday)"),
    end_date: date = Query(..., description="WSR week end (Friday)"),
    variant: int = Query(1, ge=1, description="WSR deck variant (1=primary, 2=V2, …)"),
) -> list[WsrPreviewSlide]:
    """Return rendered slide previews for an existing WSR deck."""
    try:
        slides = export_wsr_slide_previews(
            start_date=start_date,
            end_date=end_date,
            variant=variant,
            use_cache=True,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"WSR preview export failed: {exc}",
        ) from exc
    return [WsrPreviewSlide(**slide) for slide in slides]


@router.get("/preview/image")
def get_wsr_preview_image(
    start_date: date = Query(..., description="WSR week start (Monday)"),
    end_date: date = Query(..., description="WSR week end (Friday)"),
    slide_index: int = Query(..., ge=1, description="1-based slide index"),
    variant: int = Query(1, ge=1, description="WSR deck variant (1=primary, 2=V2, …)"),
) -> FileResponse:
    """Serve a rendered PNG preview for one slide of the generated WSR deck."""
    try:
        image_path = resolve_preview_image_path(
            start_date=start_date,
            end_date=end_date,
            slide_index=slide_index,
            variant=variant,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path=Path(image_path), media_type="image/png")


@router.get("/download")
def download_wsr_deck(
    start_date: date = Query(..., description="WSR week start (Monday)"),
    end_date: date = Query(..., description="WSR week end (Friday)"),
    variant: int = Query(1, ge=1, description="WSR deck variant (1=primary, 2=V2, …)"),
) -> FileResponse:
    """Download the generated PowerPoint for a WSR week."""
    ppt_path = resolve_wsr_ppt_path(start_date, end_date, variant=variant)
    if not ppt_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=(
                f"No deck found for {start_date} to {end_date}. "
                "Call POST /api/wsr/generate first."
            ),
        )
    return FileResponse(
        path=Path(ppt_path),
        media_type=(
            "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        ),
        filename=ppt_path.name,
    )


@router.get("/editor/deck")
def get_editor_deck(
    start_date: date = Query(..., description="WSR week start (Monday)"),
    end_date: date = Query(..., description="WSR week end (Friday)"),
) -> dict:
    """Parse the generated WSR .pptx into an editable JSON document."""
    preview_slides: list[dict] = []
    try:
        preview_slides = export_wsr_slide_previews(
            start_date=start_date,
            end_date=end_date,
            use_cache=True,
        )
    except Exception:
        preview_slides = []

    if not preview_slides:
        try:
            preview_slides = export_wsr_slide_previews(
                start_date=start_date,
                end_date=end_date,
                use_cache=False,
            )
        except Exception:
            preview_slides = []

    try:
        return load_wsr_editor_deck(
            start_date,
            end_date,
            preview_slides=preview_slides,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load editor deck: {exc}",
        ) from exc


@router.put("/editor/deck")
def save_editor_deck(
    body: EditorDocumentPayload,
    start_date: date = Query(..., description="WSR week start (Monday)"),
    end_date: date = Query(..., description="WSR week end (Friday)"),
) -> dict:
    """Persist the in-browser editor document for a WSR week."""
    path = save_wsr_editor_deck(start_date, end_date, body.document)
    return {"saved": True, "path": str(path)}


@router.post("/editor/sync")
def sync_editor_deck(
    body: EditorDocumentPayload,
    start_date: date = Query(..., description="WSR week start (Monday)"),
    end_date: date = Query(..., description="WSR week end (Friday)"),
) -> dict:
    """Apply editor changes directly to the .pptx and refresh slide preview images."""
    paths = wsr_output_paths(start_date, end_date)
    try:
        export_editor_document_to_pptx(body.document, paths.ppt_path)
        save_wsr_editor_deck(start_date, end_date, body.document)
        preview_slides = export_wsr_slide_previews(
            start_date=start_date,
            end_date=end_date,
            use_cache=False,
        )
        cloud_upload = try_upload_wsr_ppt(
            paths.ppt_path,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Sync to PowerPoint failed: {exc}",
        ) from exc
    return {
        "ok": True,
        "preview_slides": preview_slides,
        **cloud_response_fields_from_upload(cloud_upload),
    }


@router.post("/editor/export")
def export_editor_deck(
    body: EditorDocumentPayload,
    start_date: date = Query(..., description="WSR week start (Monday)"),
    end_date: date = Query(..., description="WSR week end (Friday)"),
) -> FileResponse:
    """Export the edited document back to .pptx."""
    paths = wsr_output_paths(start_date, end_date)
    try:
        export_editor_document_to_pptx(body.document, paths.ppt_path)
        save_wsr_editor_deck(start_date, end_date, body.document)
        try:
            export_wsr_slide_previews(
                start_date=start_date,
                end_date=end_date,
                use_cache=False,
            )
        except Exception:
            pass
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Export failed: {exc}",
        ) from exc
    return FileResponse(
        path=paths.ppt_path,
        media_type=(
            "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        ),
        filename=paths.ppt_path.name,
    )


@router.get("/templates", response_model=WsrTemplateListResponse)
def list_wsr_templates() -> WsrTemplateListResponse:
    """List saved WSR templates (newest first) and any staged draft."""
    templates = [WsrTemplateItemResponse(**item) for item in list_saved_templates()]
    draft_info = get_draft_template_info()
    draft = WsrTemplateItemResponse(**draft_info) if draft_info else None
    return WsrTemplateListResponse(templates=templates, draft=draft)


@router.get("/template", response_model=WsrTemplateInfoResponse | None)
def get_wsr_uploaded_template() -> WsrTemplateInfoResponse | None:
    """Return metadata for the newest saved WSR template."""
    info = get_uploaded_template_info()
    if info is None:
        return None
    return WsrTemplateInfoResponse(**info)


@router.post("/template/stage", response_model=WsrTemplateStageResponse)
async def stage_wsr_template(
    file: UploadFile = File(..., description="WSR template .pptx file"),
) -> WsrTemplateStageResponse:
    """Stage an uploaded template for preview; call /template/save to persist it."""
    filename = file.filename or "template.pptx"
    if not filename.lower().endswith(".pptx"):
        raise HTTPException(status_code=400, detail="Only .pptx files are supported.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        result = stage_template_upload(content=content, original_filename=filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Template staging failed: {exc}",
        ) from exc

    preview_slides = [
        WsrPreviewSlide(**slide) for slide in result.get("preview_slides", [])
    ]
    return WsrTemplateStageResponse(
        id=result["id"],
        filename=result["filename"],
        original_filename=result["original_filename"],
        updated_at=result["updated_at"],
        slide_count=result["slide_count"],
        file_size_bytes=result["file_size_bytes"],
        is_draft=result.get("is_draft", True),
        thumbnail_url=result["thumbnail_url"],
        preview_slides=preview_slides,
    )


@router.post("/template/save", response_model=WsrTemplateItemResponse)
def save_staged_wsr_template() -> WsrTemplateItemResponse:
    """Persist a staged draft template into the saved template library."""
    try:
        info = save_draft_template()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Template save failed: {exc}",
        ) from exc
    return WsrTemplateItemResponse(**info)


@router.delete("/template/draft", status_code=204)
def discard_staged_wsr_template() -> None:
    """Discard the staged draft template without saving."""
    cancel_draft_template()


@router.post("/template/upload", response_model=WsrTemplateUploadResponse)
async def upload_wsr_template(
    file: UploadFile = File(..., description="WSR template .pptx file"),
) -> WsrTemplateUploadResponse:
    """Save an uploaded template directly to the template library."""
    filename = file.filename or "template.pptx"
    if not filename.lower().endswith(".pptx"):
        raise HTTPException(status_code=400, detail="Only .pptx files are supported.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        result = save_uploaded_template(content=content, original_filename=filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Template upload failed: {exc}",
        ) from exc

    preview_slides = [
        WsrPreviewSlide(**slide) for slide in result.get("preview_slides", [])
    ]
    return WsrTemplateUploadResponse(
        filename=result["filename"],
        original_filename=result["original_filename"],
        uploaded_at=result["uploaded_at"],
        slide_count=result["slide_count"],
        file_size_bytes=result["file_size_bytes"],
        preview_slides=preview_slides,
    )


@router.get("/template/preview/slides", response_model=list[WsrPreviewSlide])
def list_wsr_template_preview_slides(
    template_id: str | None = Query(
        None,
        description="Saved template id or __draft__ for staged upload",
    ),
) -> list[WsrPreviewSlide]:
    """Return rendered slide previews for a saved or staged WSR template."""
    try:
        slides = export_template_slide_previews(
            template_id=template_id,
            use_cache=True,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Template preview export failed: {exc}",
        ) from exc
    return [WsrPreviewSlide(**slide) for slide in slides]


@router.get("/template/preview/image")
def get_wsr_template_preview_image(
    slide_index: int = Query(..., ge=1, description="1-based slide index"),
    template_id: str | None = Query(
        None,
        description="Saved template id or __draft__ for staged upload",
    ),
    thumb: int = Query(0, ge=0, le=1, description="Reserved for thumbnail requests"),
) -> FileResponse:
    """Serve a rendered PNG preview for one slide of a WSR template."""
    del thumb
    try:
        image_path = resolve_template_preview_image_path(
            slide_index=slide_index,
            template_id=template_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path=image_path, media_type="image/png")

