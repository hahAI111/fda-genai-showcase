"""Media Agent — Unified ReAct agent for image, video, and PPT generation.

This agent uses the ReAct pattern (Thought → Action → Observation) to
understand what kind of media the user wants, refine the prompt, apply
guardrails, call the right tool, and return a structured result.

Supported capabilities:
  - Image generation (gpt-image-2 via Azure AI Foundry)
  - Video generation (sora-2 via Azure AI Foundry)
  - Video status polling
  - PowerPoint generation (GPT-4.1-mini + python-pptx)

Every request passes through:
  1. InputGuardrail  — prompt injection, harmful content, PII mask
  2. Tool execution  — real Azure AI calls (no stubs)
  3. ModelOutputGuardrail — toxic output, PII in response
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from src.agents.base import AgentContext, AgentResponse, AgentRole, AgentStep, BaseAgent
from src.governance.guardrails import GuardrailPipeline, GuardrailViolation
from src.tools.media import AzureOpenAIMediaTool
from src.tools.ppt import PPTGenerationTool

logger = structlog.get_logger()


# System prompt for the media planning ReAct loop
_MEDIA_SYSTEM_PROMPT = """You are an Enterprise Media Creation Agent with ReAct reasoning.

You have access to three tools:
  - generate_image(prompt, size): create a high-quality PNG image
  - generate_ppt(topic, audience, style): create a PowerPoint deck
  - start_video_job(prompt, seconds): start a video generation job (async)

ALWAYS follow this reasoning pattern:
  Thought: Analyze the user request. What media type? What prompt will produce the best result?
  Action: Choose ONE tool and call it with a refined, detailed prompt.
  Observation: Summarize the result.
  Final Answer: Return the result with file_path and actionable next steps.

Rules:
- If the request is ambiguous, default to "image" for visuals and "ppt" for documents.
- Refine vague prompts into professional, detailed ones (add context, style, quality cues).
- Video jobs are async — always tell the user to poll /media/video/{job_id}.
- NEVER fabricate file paths or job IDs. Only report what the tool returns.
- Keep Final Answer concise: < 120 words.
"""


class MediaAgent(BaseAgent):
    """ReAct agent that creates images, videos, and PowerPoint decks."""

    agent_name = "media_agent"

    def __init__(self):
        super().__init__(
            name=self.agent_name,
            role=AgentRole.ARCHITECT,
            description="Unified media agent for image, video, and PowerPoint generation.",
        )
        self._guardrails = GuardrailPipeline(enabled=True)
        self._media_tool  = AzureOpenAIMediaTool()
        self._ppt_tool    = PPTGenerationTool()
        # Job registry — maps job_id → status dict (in-memory; survives request)
        self._video_jobs: dict[str, dict[str, Any]] = {}

    @property
    def system_prompt(self) -> str:
        return _MEDIA_SYSTEM_PROMPT

    # ── Public interface ────────────────────────────────────────────────────────

    async def create_media(
        self,
        request: str,
        media_type: str | None = None,   # "image" | "video" | "ppt" | None (auto-detect)
        request_id: str | None = None,
        image_urls: list[str] | None = None,
        image_data: list[str] | None = None,
        image_size: str = "1024x1024",
        image_quality: str = "high",
        image_background: str = "auto",
        image_output_format: str = "png",
        video_seconds: str = "4",
        video_size: str = "1280x720",
        video_reference_image_url: str | None = None,
        ppt_audience: str = "enterprise stakeholders",
        ppt_style: str = "professional",
        ppt_slides: int = 6,
    ) -> AgentResponse:
        """Entry point — run guardrails then dispatch to the right tool.

        Args:
            request: Natural-language description of what to create
            media_type: Explicit type; if None the agent auto-detects
            request_id: Trace ID for audit correlation
        """
        rid = request_id or uuid.uuid4().hex
        steps: list[AgentStep] = []

        # ── Layer 1: Input Guardrail ────────────────────────────────────────────
        input_result = self._guardrails.screen_input(request, request_id=rid)
        steps.append(AgentStep(
            step_type="guardrail_input",
            agent_name=self.agent_name,
            content=f"InputGuardrail: {input_result.decision.value} | violations={input_result.violations}",
            latency_ms=input_result.latency_ms,
        ))
        if input_result.is_blocked:
            raise GuardrailViolation("input", input_result.violations)

        safe_request = input_result.masked_text or request

        # ── Auto-detect media type ──────────────────────────────────────────────
        if not media_type:
            media_type = self._detect_media_type(safe_request)
        steps.append(AgentStep(
            step_type="react_step",
            agent_name=self.agent_name,
            content=f"Thought: User wants '{media_type}'. Request: {safe_request[:120]}",
            latency_ms=0,
        ))

        # ── Dispatch to tool ───────────────────────────────────────────────────
        import time
        t0 = time.monotonic()
        result: dict[str, Any]

        try:
            if media_type == "image":
                result = self._media_tool.generate_image(
                    prompt=self._refine_image_prompt(safe_request),
                    size=image_size,
                    quality=image_quality,
                    background=image_background,
                    output_format=image_output_format,
                    image_urls=image_urls or [],
                    image_data=image_data or [],
                )
            elif media_type == "video":
                job = self._media_tool.start_video_job(
                    prompt=self._refine_video_prompt(safe_request),
                    size=video_size,
                    seconds=int(video_seconds),
                    reference_image_url=video_reference_image_url,
                )
                job_id = str(job.get("job_id") or "")
                if not job_id:
                    raise RuntimeError("Video job started but no job_id was returned by the model API")
                self._video_jobs[job_id] = job
                result = job
            elif media_type == "ppt":
                result = await self._ppt_tool.generate(
                    topic=safe_request,
                    audience=ppt_audience,
                    style=ppt_style,
                    slides=ppt_slides,
                )
            else:
                raise ValueError(f"Unsupported media_type: {media_type}")
        except GuardrailViolation:
            raise
        except Exception as exc:
            logger.exception("media_agent.tool_failed", media_type=media_type, error=str(exc))
            return AgentResponse(
                agent_name=self.agent_name,
                content=f"Media generation failed: {exc}",
                context=AgentContext(turn_id=rid),
                steps=steps,
            )

        tool_latency = (time.monotonic() - t0) * 1000
        steps.append(AgentStep(
            step_type="tool_call",
            agent_name=self.agent_name,
            content=f"Action: {media_type} tool → {result}",
            latency_ms=tool_latency,
        ))

        # ── Build natural-language response ────────────────────────────────────
        final_text = self._format_response(media_type, result)

        # ── Layer 2: Model Output Guardrail ────────────────────────────────────
        output_result = self._guardrails.screen_output(final_text, request_id=rid)
        steps.append(AgentStep(
            step_type="guardrail_model",
            agent_name=self.agent_name,
            content=f"ModelGuardrail: {output_result.decision.value} | violations={output_result.violations}",
            latency_ms=output_result.latency_ms,
        ))
        if output_result.is_blocked:
            raise GuardrailViolation("model", output_result.violations)

        logger.info(
            "media_agent.completed",
            media_type=media_type,
            request_id=rid,
            latency_ms=tool_latency,
        )

        return AgentResponse(
            agent_name=self.agent_name,
            content=final_text,
            context=AgentContext(turn_id=rid),
            steps=steps,
            metadata={"media_type": media_type, "result": result, "request_id": rid},
        )

    def get_video_status(self, job_id: str) -> dict[str, Any]:
        """Poll status of a previously started video job."""
        if job_id in self._video_jobs:
            # Try to refresh via media tool
            try:
                status = self._media_tool.get_video_status(job_id)
                self._video_jobs[job_id].update(status)
                return self._video_jobs[job_id]
            except Exception:
                return self._video_jobs[job_id]
        raise KeyError(f"Unknown job_id: {job_id}")

    def download_video_bytes(self, job_id: str) -> bytes | None:
        """Download raw video bytes for streaming to client."""
        return self._media_tool.download_video_bytes(job_id)

    # ── Private helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _detect_media_type(text: str) -> str:
        text_lower = text.lower()
        if any(k in text_lower for k in ("video", "clip", "animation", "movie", "sora")):
            return "video"
        if any(k in text_lower for k in ("ppt", "powerpoint", "presentation", "slides", "deck")):
            return "ppt"
        return "image"

    @staticmethod
    def _refine_image_prompt(request: str) -> str:
        if len(request) > 200:
            return request
        return (
            f"{request}. "
            "High-quality, professional, detailed, enterprise-grade visualization. "
            "Clean composition, modern design aesthetic."
        )

    @staticmethod
    def _refine_video_prompt(request: str) -> str:
        if len(request) > 200:
            return request
        return (
            f"Cinematic video: {request}. "
            "Professional production quality, smooth motion, corporate visual style."
        )

    @staticmethod
    def _infer_audience(text: str) -> str:
        text_lower = text.lower()
        if any(k in text_lower for k in ("executive", "c-suite", "ceo", "board")):
            return "C-suite executives"
        if any(k in text_lower for k in ("technical", "engineer", "developer", "architect")):
            return "engineering teams"
        if any(k in text_lower for k in ("sales", "customer", "client")):
            return "sales and customer-facing teams"
        return "enterprise stakeholders"

    @staticmethod
    def _format_response(media_type: str, result: dict[str, Any]) -> str:
        if media_type == "image":
            return (
                f"Image generated successfully.\n"
                f"File: {result.get('file_path')}\n"
                f"Model: {result.get('model')} | Size: {result.get('size')}\n"
                f"Revised prompt: {result.get('revised_prompt') or 'N/A'}"
            )
        elif media_type == "video":
            return (
                f"Video job started. Status: {result.get('status', 'queued')}\n"
                f"Job ID: {result.get('job_id')}\n"
                f"Poll status at: GET /media/video/{result.get('job_id')}"
            )
        elif media_type == "ppt":
            return (
                f"PowerPoint created: {result.get('title')}\n"
                f"Slides: {result.get('slide_count')} | File: {result.get('file_path')}\n"
                f"Audience: {result.get('audience')}"
            )
        return str(result)
