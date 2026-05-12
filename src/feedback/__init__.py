"""Product Feedback Loop — Technical friction → Product feature requests.

This module implements the Product Feedback Loop responsibility:
"Identify technical friction points and convert them into formal product
feature requests for engineering teams."

The system automatically detects and categorizes friction points:
1. Performance friction — slow TTFT, low TPS, high latency
2. Cost friction — expensive operations, inefficient token usage
3. API friction — missing capabilities, awkward interfaces, error patterns
4. Quality friction — low grounding scores, hallucinations, safety issues
5. Integration friction — auth failures, SDK gaps, connectivity issues

Each detected friction point is automatically:
- Categorized by type and severity
- Enriched with metrics evidence
- Formatted as a product feature request
- Logged for aggregation and trend analysis
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import structlog

from src.config import get_settings

logger = structlog.get_logger()


class FrictionCategory(str, Enum):
    PERFORMANCE = "performance"
    COST = "cost"
    API = "api"
    QUALITY = "quality"
    INTEGRATION = "integration"
    UX = "ux"


class FrictionSeverity(str, Enum):
    LOW = "low"          # Minor inconvenience
    MEDIUM = "medium"    # Workaround needed
    HIGH = "high"        # Blocks production use
    CRITICAL = "critical"  # Data loss or security risk


@dataclass
class FrictionPoint:
    """A detected technical friction point."""

    friction_id: str
    category: FrictionCategory
    severity: FrictionSeverity
    title: str
    description: str
    evidence: dict[str, Any]
    affected_component: str  # e.g., "vertex_ai", "gemini_api", "cloud_storage"
    frequency: int = 1
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    resolved: bool = False

    def to_feature_request(self) -> dict[str, Any]:
        """Convert friction point to a formal product feature request."""
        return {
            "title": f"[{self.category.value.upper()}] {self.title}",
            "severity": self.severity.value,
            "component": self.affected_component,
            "description": self.description,
            "impact": self._impact_statement(),
            "evidence": self.evidence,
            "frequency": self.frequency,
            "customer_impact": self._customer_impact(),
            "suggested_solution": self._suggest_solution(),
            "metadata": {
                "friction_id": self.friction_id,
                "first_seen": self.first_seen,
                "last_seen": self.last_seen,
                "category": self.category.value,
            },
        }

    def _impact_statement(self) -> str:
        impacts = {
            FrictionCategory.PERFORMANCE: f"Adds {self.evidence.get('latency_impact_ms', 'unknown')}ms latency to {self.frequency} requests",
            FrictionCategory.COST: f"Costs ${self.evidence.get('cost_impact_usd', 'unknown')} extra across {self.frequency} requests",
            FrictionCategory.API: f"Required workaround in {self.frequency} code paths",
            FrictionCategory.QUALITY: f"Quality degradation in {self.evidence.get('affected_pct', 'unknown')}% of responses",
            FrictionCategory.INTEGRATION: f"Integration failure rate: {self.evidence.get('failure_rate', 'unknown')}%",
            FrictionCategory.UX: f"User friction in {self.frequency} interactions",
        }
        return impacts.get(self.category, f"Observed {self.frequency} times")

    def _customer_impact(self) -> str:
        if self.severity == FrictionSeverity.CRITICAL:
            return "Blocks production deployment — customers cannot proceed"
        elif self.severity == FrictionSeverity.HIGH:
            return "Requires significant workaround — delays deployment by weeks"
        elif self.severity == FrictionSeverity.MEDIUM:
            return "Adds development overhead — requires custom code"
        else:
            return "Minor friction — cosmetic or documentation issue"

    def _suggest_solution(self) -> str:
        suggestions = {
            FrictionCategory.PERFORMANCE: "Consider adding response streaming support or reducing cold start latency",
            FrictionCategory.COST: "Consider batch pricing tiers or prompt caching at the API level",
            FrictionCategory.API: "Consider adding this as a first-class API feature",
            FrictionCategory.QUALITY: "Consider improving model grounding or adding guardrails",
            FrictionCategory.INTEGRATION: "Consider improving SDK error messages or adding retry guidance",
            FrictionCategory.UX: "Consider simplifying the developer experience",
        }
        return suggestions.get(self.category, "Investigate and propose a solution")


class FeedbackCollector:
    """Collects and manages technical friction points.

    Production usage:
    1. Auto-detect friction from metrics (detect_from_metrics)
    2. Manual friction reports (report_friction)
    3. Aggregate into feature requests (generate_feature_requests)
    4. Export for product team review (export_report)
    """

    def __init__(self):
        self._friction_points: dict[str, FrictionPoint] = {}
        self._feature_requests: list[dict[str, Any]] = []
        self._auto_detection_rules = self._default_detection_rules()

    def report_friction(
        self,
        category: FrictionCategory,
        severity: FrictionSeverity,
        title: str,
        description: str,
        evidence: dict[str, Any],
        component: str,
    ) -> FrictionPoint:
        """Manually report a friction point."""
        friction_id = f"{category.value}:{component}:{title}"

        if friction_id in self._friction_points:
            # Update existing friction point
            existing = self._friction_points[friction_id]
            existing.frequency += 1
            existing.last_seen = time.time()
            existing.evidence.update(evidence)
            if severity.value > existing.severity.value:
                existing.severity = severity
            logger.info("feedback.friction_updated", friction_id=friction_id,
                       frequency=existing.frequency)
            return existing

        fp = FrictionPoint(
            friction_id=friction_id,
            category=category,
            severity=severity,
            title=title,
            description=description,
            evidence=evidence,
            affected_component=component,
        )
        self._friction_points[friction_id] = fp
        logger.info("feedback.friction_reported", friction_id=friction_id,
                   category=category.value, severity=severity.value)
        return fp

    def detect_from_metrics(self, metrics: dict[str, Any]) -> list[FrictionPoint]:
        """Auto-detect friction points from request metrics."""
        detected = []

        for rule in self._auto_detection_rules:
            if rule["check"](metrics):
                fp = self.report_friction(
                    category=rule["category"],
                    severity=rule["severity"],
                    title=rule["title"],
                    description=rule["description"],
                    evidence=rule["evidence_fn"](metrics),
                    component=rule["component"],
                )
                detected.append(fp)

        return detected

    def _default_detection_rules(self) -> list[dict[str, Any]]:
        """Default auto-detection rules for common friction patterns."""
        return [
            {
                "check": lambda m: m.get("ttft_ms", 0) > 2000,
                "category": FrictionCategory.PERFORMANCE,
                "severity": FrictionSeverity.HIGH,
                "title": "High Time-to-First-Token",
                "description": (
                    "TTFT consistently exceeds 2000ms. Users perceive the system as "
                    "unresponsive. This is likely caused by cold starts or model loading "
                    "latency. Consider: (1) keep-alive requests, (2) model warm-up on "
                    "deployment, (3) streaming responses to mask latency."
                ),
                "component": "vertex_ai",
                "evidence_fn": lambda m: {
                    "observed_ttft_ms": m.get("ttft_ms"),
                    "threshold_ms": 2000,
                    "latency_impact_ms": m.get("ttft_ms", 0) - 500,
                },
            },
            {
                "check": lambda m: m.get("tps", float("inf")) < 15,
                "category": FrictionCategory.PERFORMANCE,
                "severity": FrictionSeverity.MEDIUM,
                "title": "Low Token Generation Throughput",
                "description": (
                    "Token generation rate below 15 TPS. Long responses feel sluggish. "
                    "Consider: (1) model quantization, (2) speculative decoding, "
                    "(3) smaller model for simple queries (model routing)."
                ),
                "component": "gemini_api",
                "evidence_fn": lambda m: {
                    "observed_tps": m.get("tps"),
                    "threshold_tps": 15,
                },
            },
            {
                "check": lambda m: m.get("cost_usd", 0) > 0.10,
                "category": FrictionCategory.COST,
                "severity": FrictionSeverity.HIGH,
                "title": "Expensive Per-Request Cost",
                "description": (
                    "Single request cost exceeds $0.10. At scale, this is unsustainable. "
                    "Root causes: (1) large context windows, (2) multi-iteration ReAct, "
                    "(3) no prompt caching. Feature request: native prompt caching in "
                    "Gemini API to reduce repeated context costs."
                ),
                "component": "gemini_api",
                "evidence_fn": lambda m: {
                    "observed_cost_usd": m.get("cost_usd"),
                    "threshold_usd": 0.10,
                    "cost_impact_usd": m.get("cost_usd", 0) - 0.05,
                },
            },
            {
                "check": lambda m: m.get("context_utilization", 0) > 0.8,
                "category": FrictionCategory.API,
                "severity": FrictionSeverity.MEDIUM,
                "title": "Context Window Near Capacity",
                "description": (
                    "Context window utilization exceeds 80%. Risk of truncation and "
                    "quality degradation. Feature request: (1) context compression API, "
                    "(2) automatic summarization of old context, (3) sliding window with "
                    "semantic importance ranking."
                ),
                "component": "gemini_api",
                "evidence_fn": lambda m: {
                    "utilization": m.get("context_utilization"),
                    "threshold": 0.8,
                    "affected_pct": round(m.get("context_utilization", 0) * 100, 1),
                },
            },
            {
                "check": lambda m: m.get("grounding_score", 1.0) < 0.7,
                "category": FrictionCategory.QUALITY,
                "severity": FrictionSeverity.HIGH,
                "title": "Low Grounding Score",
                "description": (
                    "Response grounding score below 0.7 — significant hallucination risk. "
                    "Feature request: (1) built-in grounding verification in Gemini API, "
                    "(2) confidence scores per claim, (3) automatic citation generation."
                ),
                "component": "vertex_ai",
                "evidence_fn": lambda m: {
                    "observed_score": m.get("grounding_score"),
                    "threshold": 0.7,
                    "affected_pct": round((1 - m.get("grounding_score", 1.0)) * 100, 1),
                },
            },
            {
                "check": lambda m: m.get("auth_failures", 0) > 0,
                "category": FrictionCategory.INTEGRATION,
                "severity": FrictionSeverity.HIGH,
                "title": "Authentication Failures",
                "description": (
                    "OAuth/ADC authentication failures detected. Common causes: "
                    "(1) token expiry during long requests, (2) scope mismatch, "
                    "(3) workload identity federation misconfiguration. "
                    "Feature request: clearer error messages with remediation steps."
                ),
                "component": "google_auth",
                "evidence_fn": lambda m: {
                    "failure_count": m.get("auth_failures"),
                    "failure_rate": m.get("auth_failure_rate", "unknown"),
                },
            },
        ]

    def generate_feature_requests(self) -> list[dict[str, Any]]:
        """Convert all unresolved friction points to feature requests."""
        requests = []
        for fp in self._friction_points.values():
            if not fp.resolved:
                requests.append(fp.to_feature_request())

        # Sort by severity (critical first) then frequency
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        requests.sort(key=lambda r: (severity_order.get(r["severity"], 99), -r["frequency"]))

        self._feature_requests = requests
        return requests

    def export_report(self, path: Path | None = None) -> Path:
        """Export friction report as JSON for product team review."""
        settings = get_settings()
        path = path or settings.feedback_log_path.parent / "friction-report.json"
        path.parent.mkdir(parents=True, exist_ok=True)

        report = {
            "generated_at": time.time(),
            "summary": {
                "total_friction_points": len(self._friction_points),
                "unresolved": sum(1 for fp in self._friction_points.values() if not fp.resolved),
                "by_category": self._count_by_category(),
                "by_severity": self._count_by_severity(),
            },
            "feature_requests": self.generate_feature_requests(),
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)

        logger.info("feedback.report_exported", path=str(path), count=len(report["feature_requests"]))
        return path

    def _count_by_category(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for fp in self._friction_points.values():
            counts[fp.category.value] = counts.get(fp.category.value, 0) + 1
        return counts

    def _count_by_severity(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for fp in self._friction_points.values():
            counts[fp.severity.value] = counts.get(fp.severity.value, 0) + 1
        return counts

    def get_stats(self) -> dict[str, Any]:
        """Get feedback system statistics."""
        return {
            "friction_points": len(self._friction_points),
            "unresolved": sum(1 for fp in self._friction_points.values() if not fp.resolved),
            "by_category": self._count_by_category(),
            "by_severity": self._count_by_severity(),
            "feature_requests_generated": len(self._feature_requests),
        }
