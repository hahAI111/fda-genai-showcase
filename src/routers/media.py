from __future__ import annotations

import inspect
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.governance.guardrails import GuardrailViolation

router = APIRouter(tags=["media"])

_media_agent = None
_guardrail_pipeline = None
_cosmos_store = None
_postgres_store = None
_logger = None


def _resolve_runtime(name: str, local_value):
    """Fallback to src.main globals when router-local runtime is not yet bound.

    This keeps the router compatible with tests that patch `src.main` globals
    directly without running the full lifespan startup sequence.
    """
    if local_value is not None:
        return local_value
    try:
        import src.main as main_module

        return getattr(main_module, name, None)
    except Exception:
        return None


async def _invoke_create_media(media_agent, **kwargs):
    """Call media_agent.create_media with only the kwargs it accepts.

    This keeps the route compatible with lightweight stubs used in tests while
    still passing the full richer parameter set to the production implementation.
    """
    create_media = media_agent.create_media
    try:
        signature = inspect.signature(create_media)
        accepted = {
            name for name, parameter in signature.parameters.items()
            if parameter.kind in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            )
        }
        filtered_kwargs = {key: value for key, value in kwargs.items() if key in accepted}
    except (TypeError, ValueError):
        filtered_kwargs = kwargs

    return await create_media(**filtered_kwargs)


def bind_media_runtime(*, media_agent, guardrail_pipeline, cosmos_store, postgres_store, logger) -> None:
    """Bind runtime dependencies initialized in app lifespan."""
    global _media_agent, _guardrail_pipeline, _cosmos_store, _postgres_store, _logger
    _media_agent = media_agent
    _guardrail_pipeline = guardrail_pipeline
    _cosmos_store = cosmos_store
    _postgres_store = postgres_store
    _logger = logger


class MediaImageRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    size: str = Field(default="1024x1024")
    quality: str = Field(default="high")
    background: str = Field(default="auto")
    output_format: str = Field(default="png")
    style: str = Field(default="professional")
    image_urls: list[str] = Field(default_factory=list, max_length=4)
    image_data: list[str] = Field(default_factory=list, max_length=4)


class MediaVideoRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    seconds: str = Field(default="4", pattern=r"^(4|8|12)$")
    size: str = Field(default="1280x720")
    reference_image_url: str | None = Field(default=None)


class MediaPPTRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=4000)
    audience: str = Field(default="enterprise stakeholders")
    style: str = Field(default="professional")
    slides: int = Field(default=6, ge=3, le=15)


@router.post("/media/image")
async def generate_image(request: MediaImageRequest):
    media_agent = _resolve_runtime("media_agent", _media_agent)
    guardrail_pipeline = _resolve_runtime("guardrail_pipeline", _guardrail_pipeline)
    cosmos_store = _resolve_runtime("cosmos_store", _cosmos_store)
    postgres_store = _resolve_runtime("postgres_store", _postgres_store)
    logger = _resolve_runtime("logger", _logger)

    if media_agent is None:
        raise HTTPException(status_code=503, detail="Media agent is not initialized")

    try:
        if guardrail_pipeline is not None:
            pre = guardrail_pipeline.screen_input(request.prompt)
            if pre.is_blocked:
                raise GuardrailViolation("input", pre.violations)

        agent_response = await _invoke_create_media(
            media_agent,
            request=request.prompt,
            media_type="image",
            image_urls=request.image_urls or [],
            image_data=request.image_data or [],
            image_size=request.size,
            image_quality=request.quality,
            image_background=request.background,
            image_output_format=request.output_format,
        )
        result = (agent_response.metadata or {}).get("result") or {}
        record_id = None
        if cosmos_store is not None:
            record_id = cosmos_store.save_media("image", request.prompt, result)
        if postgres_store is not None:
            try:
                postgres_store.save_media_asset(
                    media_type="image",
                    metadata=result,
                    record_id=record_id,
                    file_path=result.get("file_path"),
                )
            except Exception as exc:
                if logger is not None:
                    logger.warning("media.image_postgres_failed", error=str(exc))
        return {**result, "record_id": record_id}
    except GuardrailViolation as exc:
        raise HTTPException(status_code=400, detail=f"Guardrail blocked: {exc.violations}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Image generation failed: {exc}") from exc


@router.post("/media/video")
async def generate_video(request: MediaVideoRequest):
    media_agent = _resolve_runtime("media_agent", _media_agent)
    guardrail_pipeline = _resolve_runtime("guardrail_pipeline", _guardrail_pipeline)
    cosmos_store = _resolve_runtime("cosmos_store", _cosmos_store)
    postgres_store = _resolve_runtime("postgres_store", _postgres_store)
    logger = _resolve_runtime("logger", _logger)

    if media_agent is None:
        raise HTTPException(status_code=503, detail="Media agent is not initialized")

    try:
        if guardrail_pipeline is not None:
            pre = guardrail_pipeline.screen_input(request.prompt)
            if pre.is_blocked:
                raise GuardrailViolation("input", pre.violations)

        agent_response = await _invoke_create_media(
            media_agent,
            request=request.prompt,
            media_type="video",
            video_seconds=request.seconds,
            video_size=request.size,
            video_reference_image_url=request.reference_image_url,
        )
        result = (agent_response.metadata or {}).get("result") or {}
        record_id = None
        if cosmos_store is not None:
            record_id = cosmos_store.save_media("video", request.prompt, result)
        if postgres_store is not None:
            try:
                postgres_store.save_media_asset(
                    media_type="video",
                    metadata=result,
                    record_id=record_id,
                    file_path=result.get("file_path"),
                    job_id=result.get("job_id"),
                )
            except Exception as exc:
                if logger is not None:
                    logger.warning("media.video_postgres_failed", error=str(exc))
        return {**result, "record_id": record_id}
    except GuardrailViolation as exc:
        raise HTTPException(status_code=400, detail=f"Guardrail blocked: {exc.violations}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Video generation failed: {exc}") from exc


@router.get("/media/video/{job_id}")
async def get_video_status(job_id: str):
    media_agent = _resolve_runtime("media_agent", _media_agent)
    if media_agent is None:
        raise HTTPException(status_code=503, detail="Media agent is not initialized")
    try:
        result = media_agent.get_video_status(job_id)
        if str(result.get("status", "")).lower() == "completed" and not result.get("video_url"):
            result["video_url"] = f"/media/video/{job_id}/stream"
        return result
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get video status: {exc}") from exc


@router.get("/media/video/{job_id}/stream")
async def stream_video(job_id: str):
    media_agent = _resolve_runtime("media_agent", _media_agent)
    if media_agent is None:
        raise HTTPException(status_code=503, detail="Media agent is not initialized")
    try:
        video_bytes = media_agent.download_video_bytes(job_id)
        if video_bytes is None:
            raise HTTPException(status_code=404, detail="Video content not available yet")
        return StreamingResponse(
            iter([video_bytes]),
            media_type="video/mp4",
            headers={
                "Content-Disposition": f'inline; filename="video-{job_id}.mp4"',
                "Content-Length": str(len(video_bytes)),
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Video download failed: {exc}") from exc


@router.post("/media/ppt")
async def generate_ppt(request: MediaPPTRequest):
    media_agent = _resolve_runtime("media_agent", _media_agent)
    guardrail_pipeline = _resolve_runtime("guardrail_pipeline", _guardrail_pipeline)
    cosmos_store = _resolve_runtime("cosmos_store", _cosmos_store)
    postgres_store = _resolve_runtime("postgres_store", _postgres_store)
    logger = _resolve_runtime("logger", _logger)

    if media_agent is None:
        raise HTTPException(status_code=503, detail="Media agent is not initialized")

    try:
        if guardrail_pipeline is not None:
            pre = guardrail_pipeline.screen_input(request.topic)
            if pre.is_blocked:
                raise GuardrailViolation("input", pre.violations)

        agent_response = await _invoke_create_media(
            media_agent,
            request=request.topic,
            media_type="ppt",
            ppt_audience=request.audience,
            ppt_style=request.style,
            ppt_slides=request.slides,
        )
        result = (agent_response.metadata or {}).get("result") or {}
        record_id = None
        if cosmos_store is not None:
            record_id = cosmos_store.save_media("ppt", request.topic, result)
        if postgres_store is not None:
            try:
                postgres_store.save_media_asset(
                    media_type="ppt",
                    metadata=result,
                    record_id=record_id,
                    file_path=result.get("file_path"),
                )
            except Exception as exc:
                if logger is not None:
                    logger.warning("media.ppt_postgres_failed", error=str(exc))
        return {**result, "record_id": record_id}
    except GuardrailViolation as exc:
        raise HTTPException(status_code=400, detail=f"Guardrail blocked: {exc.violations}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PPT generation failed: {exc}") from exc


@router.get("/media/history")
async def media_history(media_type: str | None = None, limit: int = 20):
    cosmos_store = _resolve_runtime("cosmos_store", _cosmos_store)
    if cosmos_store is None:
        return {"count": 0, "items": [], "warning": "Cosmos DB disabled"}
    safe_limit = max(1, min(limit, 100))
    items = cosmos_store.recent_media(media_type=media_type, limit=safe_limit)
    return {"count": len(items), "items": items}


@router.delete("/media/history")
async def clear_history():
    cosmos_store = _resolve_runtime("cosmos_store", _cosmos_store)
    postgres_store = _resolve_runtime("postgres_store", _postgres_store)
    logger = _resolve_runtime("logger", _logger)
    deleted = 0
    if cosmos_store is not None:
        try:
            result = cosmos_store.clear_media_history(limit=500)
            deleted = result.get("deleted", 0)
        except Exception as exc:
            if logger is not None:
                logger.warning("media.clear_history_cosmos_failed", error=str(exc))
    if postgres_store is not None:
        try:
            postgres_store.clear_media_assets()
        except Exception as exc:
            if logger is not None:
                logger.warning("media.clear_history_postgres_failed", error=str(exc))
    return {"deleted": deleted, "status": "cleared"}


def _safe_output_path(file_path: str) -> Path | None:
    p = Path(file_path)
    if not p.is_absolute():
        p = Path.cwd() / p
    try:
        resolved = p.resolve()
        output_root = (Path.cwd() / "output").resolve()
        resolved.relative_to(output_root)
        return resolved
    except Exception:
        return None


@router.get("/media/download-all")
async def media_download_all(limit: int = 30):
    cosmos_store = _resolve_runtime("cosmos_store", _cosmos_store)
    if cosmos_store is None:
        raise HTTPException(status_code=503, detail="Cosmos DB disabled")

    safe_limit = max(1, min(limit, 100))
    items = cosmos_store.recent_media(media_type=None, limit=safe_limit)
    if not items:
        raise HTTPException(status_code=404, detail="No media history to export")

    buf = io.BytesIO()
    manifest_items: list[dict[str, Any]] = []
    written_names: set[str] = set()

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for idx, item in enumerate(items, start=1):
            result = item.get("result") or {}
            media_type = str(item.get("media_type") or "unknown")
            created_at = str(item.get("created_at") or "")
            entry = {
                "index": idx,
                "id": item.get("id"),
                "media_type": media_type,
                "created_at": created_at,
                "result": result,
            }

            file_path = result.get("file_path")
            if isinstance(file_path, str) and file_path.strip():
                safe_path = _safe_output_path(file_path)
                if safe_path is not None and safe_path.exists() and safe_path.is_file():
                    arc_name = f"assets/{media_type}-{idx:02d}-{safe_path.name}"
                    if arc_name in written_names:
                        arc_name = (
                            f"assets/{media_type}-{idx:02d}-"
                            f"{item.get('id', safe_path.name)}-{safe_path.name}"
                        )
                    zf.write(str(safe_path), arcname=arc_name)
                    written_names.add(arc_name)
                    entry["bundle_file"] = arc_name

            job_id = result.get("job_id")
            if isinstance(job_id, str) and job_id:
                entry["video_status_api"] = f"/media/video/{job_id}"

            manifest_items.append(entry)

        zf.writestr(
            "manifest.json",
            json.dumps(
                {
                    "exported_at": datetime.now(timezone.utc).isoformat(),
                    "count": len(manifest_items),
                    "items": manifest_items,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )

    buf.seek(0)
    filename = f"media-bundle-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.zip"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(buf, media_type="application/zip", headers=headers)
