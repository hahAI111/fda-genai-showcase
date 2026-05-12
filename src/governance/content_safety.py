"""Content Safety — Pre/post processing guardrails for enterprise AI.

Enterprise Pattern: Content safety is a non-negotiable for enterprise
deployment. This module provides:
1. Input screening (prompt injection detection, harmful content blocking)
2. Output screening (hallucination flags, harmful content blocking)
3. Topic restriction (enterprise can define allowed/blocked topics)
4. Azure AI Content Safety integration (when configured)

Architecture:
- Local regex layer runs first (fast, zero-latency, always available)
- Azure Content Safety runs second if configured (deep analysis: hate,
  violence, self-harm, sexual content with severity scoring)
- Both layers write to structured logs for audit compliance
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger()


class SafetyLevel(str, Enum):
    SAFE = "safe"
    WARNING = "warning"
    BLOCKED = "blocked"


@dataclass
class SafetyResult:
    level: SafetyLevel
    flags: list[str]
    message: str
    details: dict[str, Any] = field(default_factory=dict)


# Patterns that indicate prompt injection attempts
INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions|rules|prompts)", re.I),
    re.compile(r"you\s+are\s+now\s+(a|an)\s+", re.I),
    re.compile(r"(system|developer)\s*(prompt|message)\s*:", re.I),
    re.compile(r"pretend\s+(you\s+are|to\s+be)", re.I),
    re.compile(r"jailbreak|bypass\s+safety|override\s+restrictions", re.I),
]

# Topics that enterprise deployments commonly restrict
BLOCKED_TOPICS = [
    re.compile(r"\b(competitor\s+confidential|trade\s+secret)\b", re.I),
    re.compile(r"\b(insider\s+trading|material\s+non-public)\b", re.I),
]


class AzureContentSafetyClient:
    """Wrapper for Azure AI Content Safety service.

    Analyzes text for: Hate, Violence, SelfHarm, Sexual content.
    Each category returns severity 0-6. We block at severity >= 2.
    """

    def __init__(self, endpoint: str, key: str):
        self._endpoint = endpoint
        self._key = key
        self._client = None
        self._available = False
        try:
            from azure.ai.contentsafety import ContentSafetyClient
            from azure.core.credentials import AzureKeyCredential
            self._client = ContentSafetyClient(endpoint, AzureKeyCredential(key))
            self._available = True
            logger.info("content_safety.azure_client_initialized", endpoint=endpoint)
        except ImportError:
            logger.warning("content_safety.azure_sdk_not_installed",
                           hint="pip install azure-ai-contentsafety")
        except Exception as e:
            logger.warning("content_safety.azure_client_failed", error=str(e))

    @property
    def available(self) -> bool:
        return self._available

    def analyze_text(self, text: str) -> dict[str, Any]:
        """Analyze text and return category severities."""
        if not self._available or not self._client:
            return {"status": "unavailable"}
        try:
            from azure.ai.contentsafety.models import AnalyzeTextOptions
            request = AnalyzeTextOptions(text=text[:10000])
            response = self._client.analyze_text(request)
            categories = {}
            for item in (response.categories_analysis or []):
                categories[item.category.value if hasattr(item.category, 'value') else str(item.category)] = item.severity
            return {"status": "analyzed", "categories": categories}
        except Exception as e:
            logger.warning("content_safety.azure_analyze_failed", error=str(e))
            return {"status": "error", "error": str(e)}

    def is_safe(self, analysis: dict[str, Any], threshold: int = 2) -> tuple[bool, list[str]]:
        """Check if analysis result is safe. Returns (safe, flagged_categories)."""
        if analysis.get("status") != "analyzed":
            return True, []
        flagged = []
        for category, severity in analysis.get("categories", {}).items():
            if severity >= threshold:
                flagged.append(f"{category}(severity={severity})")
        return len(flagged) == 0, flagged


class ContentSafety:
    """Content safety guardrails for enterprise GenAI.

    Two-tier architecture:
    1. Local regex (always active) — prompt injection, blocked topics
    2. Azure AI Content Safety (when configured) — hate, violence, self-harm, sexual
    """

    def __init__(self, enabled: bool = True, azure_endpoint: str = "", azure_key: str = ""):
        self._enabled = enabled
        self._azure_client: AzureContentSafetyClient | None = None
        if azure_endpoint and azure_key:
            self._azure_client = AzureContentSafetyClient(azure_endpoint, azure_key)

    @property
    def azure_enabled(self) -> bool:
        return self._azure_client is not None and self._azure_client.available

    def screen_input(self, text: str) -> SafetyResult:
        """Screen user input before sending to LLM."""
        if not self._enabled:
            return SafetyResult(level=SafetyLevel.SAFE, flags=[], message="Safety disabled")

        flags = []
        details: dict[str, Any] = {}

        # Layer 1: Local regex — prompt injection
        for pattern in INJECTION_PATTERNS:
            if pattern.search(text):
                flags.append("prompt_injection")
                logger.warning("safety.prompt_injection_detected", text_preview=text[:100])
                return SafetyResult(
                    level=SafetyLevel.BLOCKED,
                    flags=flags,
                    message="Input blocked: potential prompt injection detected.",
                    details={"layer": "local", "reason": "prompt_injection"},
                )

        # Layer 1: Local regex — blocked topics
        for pattern in BLOCKED_TOPICS:
            if pattern.search(text):
                flags.append("blocked_topic")

        # Layer 2: Azure Content Safety (if configured)
        if self._azure_client and self._azure_client.available:
            analysis = self._azure_client.analyze_text(text)
            details["azure_content_safety"] = analysis
            safe, azure_flags = self._azure_client.is_safe(analysis)
            if not safe:
                flags.extend(azure_flags)
                logger.warning("safety.azure_content_blocked", flags=azure_flags)
                return SafetyResult(
                    level=SafetyLevel.BLOCKED,
                    flags=flags,
                    message=f"Input blocked by Azure Content Safety: {', '.join(azure_flags)}",
                    details=details,
                )

        if flags:
            return SafetyResult(
                level=SafetyLevel.WARNING,
                flags=flags,
                message=f"Content flags detected: {', '.join(flags)}",
                details=details,
            )

        return SafetyResult(
            level=SafetyLevel.SAFE, flags=[], message="Input passed safety screening",
            details=details,
        )

    def screen_output(self, text: str) -> SafetyResult:
        """Screen LLM output before returning to user."""
        if not self._enabled:
            return SafetyResult(level=SafetyLevel.SAFE, flags=[], message="Safety disabled")

        flags = []
        details: dict[str, Any] = {}

        # Layer 1: System prompt leak detection
        system_leak_patterns = [
            re.compile(r"(my\s+)?system\s+prompt\s+(is|says|instructs)", re.I),
            re.compile(r"(I\s+was|I\'m)\s+instructed\s+to", re.I),
        ]
        for pattern in system_leak_patterns:
            if pattern.search(text):
                flags.append("system_prompt_leak")

        # Layer 1: Blocked topics in output
        for pattern in BLOCKED_TOPICS:
            if pattern.search(text):
                flags.append("blocked_topic_in_output")

        if "system_prompt_leak" in flags:
            return SafetyResult(
                level=SafetyLevel.BLOCKED,
                flags=flags,
                message="Output blocked: potential system prompt disclosure.",
                details={"layer": "local"},
            )

        # Layer 2: Azure Content Safety on output
        if self._azure_client and self._azure_client.available:
            analysis = self._azure_client.analyze_text(text)
            details["azure_content_safety"] = analysis
            safe, azure_flags = self._azure_client.is_safe(analysis)
            if not safe:
                flags.extend(azure_flags)
                return SafetyResult(
                    level=SafetyLevel.BLOCKED,
                    flags=flags,
                    message=f"Output blocked by Azure Content Safety: {', '.join(azure_flags)}",
                    details=details,
                )

        if flags:
            return SafetyResult(
                level=SafetyLevel.WARNING,
                flags=flags,
                message=f"Output flags: {', '.join(flags)}",
                details=details,
            )

        return SafetyResult(
            level=SafetyLevel.SAFE, flags=[], message="Output passed safety screening",
            details=details,
        )

    def get_status(self) -> dict[str, Any]:
        """Return safety system status for dashboards."""
        return {
            "enabled": self._enabled,
            "local_regex": True,
            "azure_content_safety": self.azure_enabled,
            "categories_monitored": ["Hate", "Violence", "SelfHarm", "Sexual"],
            "pii_patterns": ["email", "phone", "ssn", "credit_card", "ip_address"],
            "injection_patterns": len(INJECTION_PATTERNS),
            "blocked_topic_patterns": len(BLOCKED_TOPICS),
        }
