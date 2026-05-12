"""Azure AI Foundry media generation helpers for interview demos.

Supports image generation with the existing gpt-image-2 deployment and video
job creation with a configurable Azure OpenAI video deployment.
"""

from __future__ import annotations

import base64
import re
import uuid
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
import structlog

from src.config import get_azure_openai_sync_client, get_settings

logger = structlog.get_logger()


class AzureOpenAIMediaTool:
    def __init__(self, output_dir: Path | None = None):
        self._settings = get_settings()
        self._client = get_azure_openai_sync_client()
        self._output_dir = output_dir or Path("output") / "generated-media"
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def generate_image(
        self,
        prompt: str,
        size: str = "1024x1024",
        quality: str = "high",
        background: str = "auto",
        output_format: str = "png",
        image_urls: list[str] | None = None,
        image_data: list[str] | None = None,
    ) -> dict[str, Any]:
        generate_kwargs: dict[str, Any] = {
            "model": self._settings.azure_ai_image_deployment,
            "prompt": prompt,
            "size": size,
            "quality": quality,
            "background": background,
        }

        # Collect reference images from both URLs and direct base64 uploads
        image_inputs: list[str] = []
        if image_data:
            for b64 in image_data[:4]:
                if b64:
                    image_inputs.append(b64)
        if image_urls:
            for url in image_urls[:4]:
                try:
                    img_bytes = self._download_reference_image(url)
                    image_inputs.append(base64.b64encode(img_bytes.read()).decode("ascii"))
                except Exception as exc:
                    logger.warning("media.image_input_download_failed", url=url[:120], error=str(exc))
        if image_inputs:
            generate_kwargs["image"] = image_inputs[:4]

        response = self._client.images.generate(**generate_kwargs)
        img_item = response.data[0]
        b64_payload = getattr(img_item, "b64_json", None)
        if not b64_payload:
            raise RuntimeError("Azure OpenAI image response did not include b64_json data.")

        file_name = f"image-{uuid.uuid4().hex}.{output_format}"
        file_path = self._output_dir / file_name
        file_path.write_bytes(base64.b64decode(b64_payload))

        logger.info("media.image_generated", path=str(file_path), model=self._settings.azure_ai_image_deployment)
        return {
            "model": self._settings.azure_ai_image_deployment,
            "prompt": prompt,
            "size": size,
            "file_path": str(file_path),
            "revised_prompt": getattr(img_item, "revised_prompt", None),
        }

    def start_video_job(
        self,
        prompt: str,
        size: str = "1280x720",
        seconds: int = 8,
        reference_image_url: str | None = None,
    ) -> dict[str, Any]:
        normalized_seconds = str(seconds)
        if normalized_seconds not in {"4", "8", "12"}:
            raise ValueError("seconds must be one of 4, 8, or 12 for the configured video model.")

        create_kwargs: dict[str, Any] = {
            "model": self._settings.azure_ai_video_deployment,
            "prompt": prompt,
            "size": size,
            "seconds": normalized_seconds,
        }
        if reference_image_url:
            image_bytes = self._download_reference_image(reference_image_url)
            create_kwargs["input_reference"] = image_bytes

        video_job = self._client.videos.create(**create_kwargs)
        payload = video_job.model_dump() if hasattr(video_job, "model_dump") else dict(video_job)
        job_id = payload.get("id") or payload.get("job_id")
        status = payload.get("status") or "queued"
        if not job_id:
            raise RuntimeError("Video API did not return a job identifier")

        logger.info("media.video_started", model=self._settings.azure_ai_video_deployment)
        return {
            "model": self._settings.azure_ai_video_deployment,
            "prompt": prompt,
            "size": size,
            "seconds": seconds,
            "job_id": str(job_id),
            "status": status,
            "job": payload,
        }

    def get_video_status(self, job_id: str) -> dict[str, Any]:
        """Fetch latest status for a video job.

        The OpenAI/Azure client surface can differ by version, so this method
        attempts the known retrieve/get patterns and normalizes the response.
        """
        response_obj: Any | None = None
        errors: list[str] = []

        attempts = [
            lambda: self._client.videos.retrieve(job_id),
            lambda: self._client.videos.retrieve(video_id=job_id),
            lambda: self._client.videos.get(job_id),
            lambda: self._client.videos.get(video_id=job_id),
        ]
        for attempt in attempts:
            try:
                response_obj = attempt()
                break
            except Exception as exc:  # pragma: no cover - SDK surface varies
                errors.append(str(exc))

        if response_obj is None:
            raise RuntimeError(f"Unable to query video status for job {job_id}: {' | '.join(errors)}")

        payload = response_obj.model_dump() if hasattr(response_obj, "model_dump") else dict(response_obj)
        normalized_id = payload.get("id") or payload.get("job_id") or job_id
        status = payload.get("status") or "unknown"
        result: dict[str, Any] = {
            "job_id": str(normalized_id),
            "status": status,
            "job": payload,
        }

        if str(status).lower() == "completed":
            local_video = self._ensure_video_downloaded(str(normalized_id), payload)
            if local_video is not None:
                result["file_path"] = str(local_video)

            remote_url = self._find_video_url(payload)
            if remote_url:
                result["video_url"] = remote_url

        return result

    def download_video_bytes(self, job_id: str) -> bytes | None:
        """Download raw video bytes from Azure OpenAI for streaming to client."""
        safe_job_id = re.sub(r"[^a-zA-Z0-9_-]", "", job_id) or uuid.uuid4().hex
        out_path = self._output_dir / f"video-{safe_job_id}.mp4"
        if out_path.exists() and out_path.is_file() and out_path.stat().st_size > 0:
            return out_path.read_bytes()

        # Primary method: videos.download_content (OpenAI SDK >=1.x)
        try:
            content_obj = self._client.videos.download_content(job_id)
            # write_to_file is the most reliable extraction path
            write_to_file = getattr(content_obj, "write_to_file", None)
            if callable(write_to_file):
                write_to_file(str(out_path))
                if out_path.exists() and out_path.stat().st_size > 0:
                    logger.info("media.video_bytes_downloaded", job_id=job_id, path=str(out_path))
                    return out_path.read_bytes()
            # Fallback: .content attribute (raw bytes)
            data = self._extract_video_bytes(content_obj)
            if data:
                out_path.write_bytes(data)
                logger.info("media.video_bytes_downloaded", job_id=job_id, bytes=len(data))
                return data
        except Exception as exc:
            logger.warning("media.download_content_failed", job_id=job_id, error=str(exc))

        # Fallback attempts for older SDK versions
        fallback_attempts = [
            lambda: self._client.videos.content(job_id),
            lambda: self._client.videos.download(job_id),
        ]
        for attempt in fallback_attempts:
            try:
                content_obj = attempt()
            except Exception:
                continue
            data = self._extract_video_bytes(content_obj)
            if data:
                out_path.write_bytes(data)
                logger.info("media.video_bytes_downloaded", job_id=job_id, bytes=len(data))
                return data

        return None

    def _ensure_video_downloaded(self, job_id: str, payload: dict[str, Any]) -> Path | None:
        existing = payload.get("file_path")
        if isinstance(existing, str) and existing:
            existing_path = Path(existing)
            if existing_path.exists() and existing_path.is_file():
                return existing_path

        safe_job_id = re.sub(r"[^a-zA-Z0-9_-]", "", job_id) or uuid.uuid4().hex
        out_path = self._output_dir / f"video-{safe_job_id}.mp4"
        if out_path.exists() and out_path.is_file():
            return out_path

        # Primary method: videos.download_content
        try:
            content_obj = self._client.videos.download_content(job_id)
            write_to_file = getattr(content_obj, "write_to_file", None)
            if callable(write_to_file):
                write_to_file(str(out_path))
                if out_path.exists() and out_path.stat().st_size > 0:
                    logger.info("media.video_downloaded", job_id=job_id, path=str(out_path))
                    return out_path
            data = self._extract_video_bytes(content_obj)
            if data:
                out_path.write_bytes(data)
                logger.info("media.video_downloaded", job_id=job_id, path=str(out_path), bytes=len(data))
                return out_path
        except Exception as exc:
            logger.warning("media.ensure_download_failed", job_id=job_id, error=str(exc))

        # Fallback for older SDK
        fallback_attempts = [
            lambda: self._client.videos.content(job_id),
            lambda: self._client.videos.download(job_id),
        ]
        for attempt in fallback_attempts:
            try:
                content_obj = attempt()
            except Exception:
                continue
            data = self._extract_video_bytes(content_obj)
            if data:
                out_path.write_bytes(data)
                logger.info("media.video_downloaded", job_id=job_id, path=str(out_path), bytes=len(data))
                return out_path

        return None

    def _extract_video_bytes(self, content_obj: Any) -> bytes | None:
        if content_obj is None:
            return None
        if isinstance(content_obj, (bytes, bytearray)):
            return bytes(content_obj)

        direct_content = getattr(content_obj, "content", None)
        if isinstance(direct_content, (bytes, bytearray)):
            return bytes(direct_content)

        read_fn = getattr(content_obj, "read", None)
        if callable(read_fn):
            try:
                data = read_fn()
                if isinstance(data, (bytes, bytearray)):
                    return bytes(data)
            except Exception:
                pass

        response = getattr(content_obj, "response", None)
        response_content = getattr(response, "content", None) if response is not None else None
        if isinstance(response_content, (bytes, bytearray)):
            return bytes(response_content)
        return None

    def _find_video_url(self, payload: Any) -> str | None:
        if isinstance(payload, str):
            lowered = payload.lower()
            if lowered.startswith("http://") or lowered.startswith("https://"):
                return payload
            return None

        if isinstance(payload, list):
            for item in payload:
                found = self._find_video_url(item)
                if found:
                    return found
            return None

        if isinstance(payload, dict):
            for key in ("video_url", "download_url", "output_url", "url", "content_url"):
                val = payload.get(key)
                if isinstance(val, str) and val.lower().startswith(("http://", "https://")):
                    return val
            for val in payload.values():
                found = self._find_video_url(val)
                if found:
                    return found

        return None

    def _download_reference_image(self, reference_image_url: str) -> BytesIO:
        # Handle base64 data URLs from file uploads
        if reference_image_url.startswith("data:"):
            # Format: data:image/png;base64,<data>
            parts = reference_image_url.split(",", 1)
            raw_b64 = parts[1] if len(parts) > 1 else parts[0]
            image_data = BytesIO(base64.b64decode(raw_b64))
            image_data.name = "reference-image.png"
            return image_data
        response = httpx.get(reference_image_url, timeout=60.0)
        response.raise_for_status()
        image_data = BytesIO(response.content)
        image_data.name = Path(reference_image_url).name or "reference-image.png"
        return image_data
