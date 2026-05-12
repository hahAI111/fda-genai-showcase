"""PII Filter — Detect and mask personally identifiable information.

Enterprise Deployment Blocker:
"We can't send PII to LLMs — our compliance team won't allow it."

Solution: Pre-process all inputs to detect and mask PII before it reaches
the model. Post-process outputs to catch any PII that leaks through.

This uses regex-based detection for common PII patterns. In production,
you'd also integrate Azure AI Content Safety or a dedicated PII service.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import structlog

logger = structlog.get_logger()


@dataclass
class PIIDetection:
    type: str
    value: str
    start: int
    end: int
    masked: str


# Patterns for common PII types
PII_PATTERNS = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "phone_us": re.compile(r"\b(?:\+1[-.]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
    "ip_address": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "date_of_birth": re.compile(
        r"\b(?:DOB|date of birth|born)[:\s]*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
        re.IGNORECASE,
    ),
}

MASK_MAP = {
    "email": "[EMAIL_REDACTED]",
    "phone_us": "[PHONE_REDACTED]",
    "ssn": "[SSN_REDACTED]",
    "credit_card": "[CC_REDACTED]",
    "ip_address": "[IP_REDACTED]",
    "date_of_birth": "[DOB_REDACTED]",
}


class PIIFilter:
    """Detect and mask PII in text — pre/post processing for LLM calls."""

    def __init__(self, enabled: bool = True):
        self._enabled = enabled

    def detect(self, text: str) -> list[PIIDetection]:
        """Detect PII in text without modifying it."""
        if not self._enabled:
            return []

        detections = []
        for pii_type, pattern in PII_PATTERNS.items():
            for match in pattern.finditer(text):
                detections.append(PIIDetection(
                    type=pii_type,
                    value=match.group(),
                    start=match.start(),
                    end=match.end(),
                    masked=MASK_MAP.get(pii_type, "[REDACTED]"),
                ))

        if detections:
            logger.warning(
                "pii.detected",
                count=len(detections),
                types=[d.type for d in detections],
            )

        return detections

    def mask(self, text: str) -> tuple[str, list[PIIDetection]]:
        """Detect and mask PII, returning both the masked text and detections."""
        detections = self.detect(text)
        if not detections:
            return text, []

        # Apply masks in reverse order to preserve positions
        masked_text = text
        for detection in sorted(detections, key=lambda d: d.start, reverse=True):
            masked_text = (
                masked_text[: detection.start]
                + detection.masked
                + masked_text[detection.end :]
            )

        logger.info("pii.masked", original_length=len(text), masked_length=len(masked_text))
        return masked_text, detections

    def has_pii(self, text: str) -> bool:
        """Quick check if text contains PII."""
        return len(self.detect(text)) > 0
