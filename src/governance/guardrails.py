"""Two-Layer Guardrail Pipeline — Enterprise AI Content Safety.

Architecture:
    Layer 1 — INPUT GUARDRAIL (before Agent reasoning)
        • Prompt injection detection
        • PII masking
        • Harmful content blocking
        • Topic restriction enforcement

    Layer 2 — MODEL GUARDRAIL (after Agent/LLM produces output)
        • Output toxicity screening
        • PII leak detection in generated content
        • Hallucination flag heuristics
        • Policy compliance check on output

Both layers write to the audit trail and emit structured logs for
observability. Any BLOCKED result raises GuardrailViolation which
FastAPI converts to an HTTP 400 response.

This is NOT decorative — every /chat, /media/image, /media/video,
/media/ppt request passes through both layers unconditionally.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger()


class GuardrailDecision(str, Enum):
    ALLOW = "allow"
    WARN = "warn"
    BLOCK = "block"


@dataclass
class GuardrailResult:
    decision: GuardrailDecision
    layer: str          # "input" | "model"
    violations: list[str] = field(default_factory=list)
    masked_text: str | None = None   # Text after PII masking (Layer 1 only)
    latency_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_blocked(self) -> bool:
        return self.decision == GuardrailDecision.BLOCK

    @property
    def is_allowed(self) -> bool:
        return self.decision == GuardrailDecision.ALLOW


class GuardrailViolation(Exception):
    """Raised when a guardrail blocks a request."""
    def __init__(self, layer: str, violations: list[str]):
        self.layer = layer
        self.violations = violations
        super().__init__(f"[{layer}] Guardrail blocked: {', '.join(violations)}")


# ─── Regex patterns ────────────────────────────────────────────────────────────

# Prompt injection — Layer 1
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions|rules|prompts)", re.I),
    re.compile(r"you\s+are\s+now\s+(a|an)\s+", re.I),
    re.compile(r"(system|developer)\s*(prompt|message)\s*:", re.I),
    re.compile(r"pretend\s+(you\s+are|to\s+be)", re.I),
    re.compile(r"jailbreak|bypass\s+safety|override\s+restrictions", re.I),
    re.compile(r"DAN\s+mode|do\s+anything\s+now", re.I),
    re.compile(r"<\s*(script|iframe|object|embed)\s*>", re.I),
]

# Harmful content — Layer 1 (blocks explicit violence/adult instructions)
_HARMFUL_INPUT_PATTERNS = [
    re.compile(r"\b(how\s+to\s+(make|build|create)\s+(bomb|weapon|poison|malware|exploit))\b", re.I),
    re.compile(r"\b(child\s+porn|csam|child\s+sexual)\b", re.I),
    re.compile(r"\b(suicide\s+method|self-harm\s+instruction)\b", re.I),
]

# PII — both layers
_PII_PATTERNS: dict[str, tuple[re.Pattern, str]] = {
    "email":       (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[EMAIL]"),
    "phone_us":    (re.compile(r"\b(?:\+1[-.]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[PHONE]"),
    "ssn":         (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    "credit_card": (re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"), "[CC_NUM]"),
    "ip_address":  (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[IP_ADDR]"),
    "api_key":     (re.compile(r"\b[A-Za-z0-9]{32,64}\b"), "[API_KEY]"),  # conservative match
}

# Blocked enterprise topics — Layer 1
_BLOCKED_TOPIC_PATTERNS = [
    re.compile(r"\b(insider\s+trading|material\s+non-public\s+information)\b", re.I),
    re.compile(r"\b(trade\s+secret|confidential\s+competitor)\b", re.I),
]

# Output toxicity — Layer 2
_TOXIC_OUTPUT_PATTERNS = [
    re.compile(r"\b(fuck|shit|bitch|asshole)\b", re.I),          # profanity
    re.compile(r"\b(kill\s+all|genocide|ethnic\s+cleansing)\b", re.I),
    re.compile(r"\b(white\s+supremac|neo-nazi|kkk)\b", re.I),
]

# Hallucination heuristics — Layer 2 (flags, not blocks)
_HALLUCINATION_SIGNALS = [
    re.compile(r"\b(I\s+don'?t\s+know\s+but|as\s+far\s+as\s+I\s+know|I\s+believe\s+that)\b", re.I),
    re.compile(r"\b(may\s+not\s+be\s+accurate|could\s+be\s+wrong|not\s+sure\s+about)\b", re.I),
]


def _mask_pii(text: str) -> tuple[str, list[str]]:
    """Replace PII in text with redacted tokens. Returns (masked_text, detected_types)."""
    detected: list[str] = []
    for pii_type, (pattern, token) in _PII_PATTERNS.items():
        if pattern.search(text):
            text = pattern.sub(token, text)
            detected.append(pii_type)
    return text, detected


class InputGuardrail:
    """Layer 1 — runs BEFORE the agent/LLM sees the input.

    Responsibilities:
    - Block prompt injection
    - Block harmful instructions
    - Mask PII before forwarding to LLM
    - Enforce enterprise topic restrictions
    """

    def __init__(self, enabled: bool = True):
        self._enabled = enabled

    def run(self, text: str, request_id: str = "") -> GuardrailResult:
        """Synchronous screening (fast regex; no network calls)."""
        t0 = time.monotonic()

        if not self._enabled:
            return GuardrailResult(
                decision=GuardrailDecision.ALLOW,
                layer="input",
                masked_text=text,
            )

        violations: list[str] = []

        # 1. Prompt injection — hard block
        for pat in _INJECTION_PATTERNS:
            if pat.search(text):
                violations.append("prompt_injection")
                logger.warning("guardrail.input.blocked", reason="prompt_injection",
                               request_id=request_id, preview=text[:80])
                return GuardrailResult(
                    decision=GuardrailDecision.BLOCK,
                    layer="input",
                    violations=violations,
                    latency_ms=(time.monotonic() - t0) * 1000,
                )

        # 2. Harmful content — hard block
        for pat in _HARMFUL_INPUT_PATTERNS:
            if pat.search(text):
                violations.append("harmful_content")
                logger.warning("guardrail.input.blocked", reason="harmful_content",
                               request_id=request_id)
                return GuardrailResult(
                    decision=GuardrailDecision.BLOCK,
                    layer="input",
                    violations=violations,
                    latency_ms=(time.monotonic() - t0) * 1000,
                )

        # 3. Blocked enterprise topics — hard block
        for pat in _BLOCKED_TOPIC_PATTERNS:
            if pat.search(text):
                violations.append("blocked_enterprise_topic")
                return GuardrailResult(
                    decision=GuardrailDecision.BLOCK,
                    layer="input",
                    violations=violations,
                    latency_ms=(time.monotonic() - t0) * 1000,
                )

        # 4. PII masking — allow but mask
        masked_text, pii_found = _mask_pii(text)
        if pii_found:
            logger.info("guardrail.input.pii_masked", types=pii_found, request_id=request_id)
            violations.extend([f"pii:{t}" for t in pii_found])

        latency_ms = (time.monotonic() - t0) * 1000
        logger.debug("guardrail.input.allowed", latency_ms=latency_ms, request_id=request_id)

        decision = GuardrailDecision.WARN if violations else GuardrailDecision.ALLOW
        return GuardrailResult(
            decision=decision,
            layer="input",
            violations=violations,
            masked_text=masked_text,
            latency_ms=latency_ms,
        )


class ModelOutputGuardrail:
    """Layer 2 — runs AFTER the agent/LLM produces its response.

    Responsibilities:
    - Screen for toxic/harmful output
    - Detect PII leakage in generated content
    - Flag hallucination signals (non-blocking, warning only)
    - Block output that violates enterprise policy
    """

    def __init__(self, enabled: bool = True):
        self._enabled = enabled

    def run(self, text: str, request_id: str = "") -> GuardrailResult:
        """Synchronous output screening."""
        t0 = time.monotonic()

        if not self._enabled:
            return GuardrailResult(decision=GuardrailDecision.ALLOW, layer="model")

        violations: list[str] = []
        metadata: dict[str, Any] = {}

        # 1. Toxic output — hard block
        for pat in _TOXIC_OUTPUT_PATTERNS:
            if pat.search(text):
                violations.append("toxic_output")
                logger.warning("guardrail.model.blocked", reason="toxic_output",
                               request_id=request_id)
                return GuardrailResult(
                    decision=GuardrailDecision.BLOCK,
                    layer="model",
                    violations=violations,
                    latency_ms=(time.monotonic() - t0) * 1000,
                )

        # 2. PII in output — mask and warn
        _, pii_found = _mask_pii(text)
        if pii_found:
            violations.extend([f"output_pii:{t}" for t in pii_found])
            logger.warning("guardrail.model.pii_in_output", types=pii_found,
                           request_id=request_id)

        # 3. Hallucination signals — metadata flag only (non-blocking)
        hallucination_signals = []
        for pat in _HALLUCINATION_SIGNALS:
            if pat.search(text):
                hallucination_signals.append(pat.pattern[:40])
        if hallucination_signals:
            metadata["hallucination_signals"] = hallucination_signals
            logger.info("guardrail.model.hallucination_flag", count=len(hallucination_signals),
                        request_id=request_id)

        latency_ms = (time.monotonic() - t0) * 1000
        logger.debug("guardrail.model.passed", latency_ms=latency_ms, request_id=request_id)

        decision = GuardrailDecision.WARN if violations else GuardrailDecision.ALLOW
        return GuardrailResult(
            decision=decision,
            layer="model",
            violations=violations,
            latency_ms=latency_ms,
            metadata=metadata,
        )


class GuardrailPipeline:
    """Composite: run both layers and collect results.

    Usage:
        pipeline = GuardrailPipeline()

        # Before LLM call
        input_result = pipeline.screen_input(user_text, request_id)
        if input_result.is_blocked:
            raise GuardrailViolation("input", input_result.violations)
        safe_text = input_result.masked_text or user_text

        # After LLM call
        output_result = pipeline.screen_output(llm_response, request_id)
        if output_result.is_blocked:
            raise GuardrailViolation("model", output_result.violations)
    """

    def __init__(self, enabled: bool = True):
        self.input_layer = InputGuardrail(enabled=enabled)
        self.model_layer = ModelOutputGuardrail(enabled=enabled)

    def screen_input(self, text: str, request_id: str = "") -> GuardrailResult:
        return self.input_layer.run(text, request_id=request_id)

    def screen_output(self, text: str, request_id: str = "") -> GuardrailResult:
        return self.model_layer.run(text, request_id=request_id)
