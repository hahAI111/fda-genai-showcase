"""LLM-Native Metrics — Production-grade metrics for GenAI systems.

This module implements the metrics that matter for LLM production systems,
beyond traditional API metrics (latency, error rate).

LLM-Native Metrics (the ones that Google specifically asked about):
1. Tokens per Second (TPS) — generation throughput
2. Time to First Token (TTFT) — perceived latency
3. Cost per Request — per-query unit economics
4. Token Efficiency — useful tokens / total tokens ratio
5. Context Window Utilization — how full is the context window
6. Reasoning Depth — ReAct iterations per query
7. Delegation Fan-out — parallel sub-agent utilization
8. Grounding Score — retrieval quality metrics

These metrics enable:
- Capacity planning (TPS trends predict when you need to scale)
- Cost forecasting (cost/request × projected volume = budget)
- SLO enforcement (TTFT < 500ms, TPS > 30)
- Model selection (compare Gemini Flash vs Pro on cost/quality tradeoff)
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

from src.config import get_settings

logger = structlog.get_logger()


# === Model Pricing (per 1M tokens, as of 2026) ===

MODEL_PRICING = {
    # Google Gemini
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60, "provider": "google"},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00, "provider": "google"},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40, "provider": "google"},
    # Azure OpenAI
    "gpt-4.1": {"input": 2.00, "output": 8.00, "provider": "azure"},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60, "provider": "azure"},
    "gpt-4.1-nano": {"input": 0.10, "output": 0.40, "provider": "azure"},
    # Open-source (self-hosted cost estimates)
    "llama-3.3-70b": {"input": 0.20, "output": 0.80, "provider": "self-hosted"},
}


@dataclass
class RequestMetrics:
    """LLM-native metrics for a single request."""

    request_id: str
    model: str
    timestamp: float = field(default_factory=time.time)

    # Token metrics
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    # Timing metrics (milliseconds)
    time_to_first_token_ms: float = 0.0  # TTFT — perceived latency
    total_latency_ms: float = 0.0
    generation_latency_ms: float = 0.0  # Excludes tool execution time

    # Throughput
    tokens_per_second: float = 0.0  # TPS — generation throughput

    # Cost
    input_cost_usd: float = 0.0
    output_cost_usd: float = 0.0
    total_cost_usd: float = 0.0
    cost_per_output_token_usd: float = 0.0

    # Efficiency
    context_window_utilization: float = 0.0  # % of context window used
    token_efficiency: float = 0.0  # useful_tokens / total_tokens

    # Agent-specific
    react_iterations: int = 0
    tool_calls: int = 0
    delegation_fan_out: int = 0  # Number of parallel sub-agents
    agent_name: str = ""

    # Quality signals
    grounding_score: float | None = None
    eval_score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "model": self.model,
            "timestamp": self.timestamp,
            "tokens": {
                "prompt": self.prompt_tokens,
                "completion": self.completion_tokens,
                "total": self.total_tokens,
            },
            "timing": {
                "ttft_ms": round(self.time_to_first_token_ms, 2),
                "total_latency_ms": round(self.total_latency_ms, 2),
                "generation_latency_ms": round(self.generation_latency_ms, 2),
                "tokens_per_second": round(self.tokens_per_second, 2),
            },
            "cost": {
                "input_usd": round(self.input_cost_usd, 6),
                "output_usd": round(self.output_cost_usd, 6),
                "total_usd": round(self.total_cost_usd, 6),
            },
            "efficiency": {
                "context_utilization": round(self.context_window_utilization, 4),
                "token_efficiency": round(self.token_efficiency, 4),
            },
            "agent": {
                "name": self.agent_name,
                "react_iterations": self.react_iterations,
                "tool_calls": self.tool_calls,
                "delegation_fan_out": self.delegation_fan_out,
            },
        }


@dataclass
class AggregateMetrics:
    """Aggregated metrics over a time window."""

    window_start: float
    window_end: float
    request_count: int = 0

    # Token aggregates
    total_tokens: int = 0
    avg_tokens_per_request: float = 0.0
    p50_tokens: int = 0
    p95_tokens: int = 0
    p99_tokens: int = 0

    # Latency aggregates
    avg_ttft_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    avg_tps: float = 0.0

    # Cost aggregates
    total_cost_usd: float = 0.0
    avg_cost_per_request_usd: float = 0.0

    # Quality aggregates
    avg_grounding_score: float | None = None
    slo_violations: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "window": {
                "start": self.window_start,
                "end": self.window_end,
                "duration_seconds": self.window_end - self.window_start,
            },
            "requests": self.request_count,
            "tokens": {
                "total": self.total_tokens,
                "avg_per_request": round(self.avg_tokens_per_request, 1),
                "p50": self.p50_tokens,
                "p95": self.p95_tokens,
                "p99": self.p99_tokens,
            },
            "latency": {
                "avg_ttft_ms": round(self.avg_ttft_ms, 2),
                "p50_ms": round(self.p50_latency_ms, 2),
                "p95_ms": round(self.p95_latency_ms, 2),
                "p99_ms": round(self.p99_latency_ms, 2),
                "avg_tps": round(self.avg_tps, 2),
            },
            "cost": {
                "total_usd": round(self.total_cost_usd, 4),
                "avg_per_request_usd": round(self.avg_cost_per_request_usd, 6),
            },
            "quality": {
                "avg_grounding_score": self.avg_grounding_score,
                "slo_violations": self.slo_violations,
            },
        }


# === SLO Definitions ===

DEFAULT_SLOS = {
    "ttft_ms": 500.0,            # Time to First Token < 500ms
    "tps": 30.0,                 # Tokens per Second > 30
    "p99_latency_ms": 5000.0,    # p99 total latency < 5s
    "cost_per_request_usd": 0.05,  # Cost per request < $0.05
    "grounding_score": 0.85,     # Grounding score > 0.85
}


class MetricsCollector:
    """Collects and aggregates LLM-native metrics.

    Production usage:
    1. Record metrics for every request via record()
    2. Export aggregates periodically via get_aggregates()
    3. Check SLO compliance via check_slos()
    4. Feed into Cloud Monitoring / Prometheus / Grafana
    """

    def __init__(self, slos: dict[str, float] | None = None):
        self._metrics: list[RequestMetrics] = []
        self._slos = slos or DEFAULT_SLOS
        self._by_model: dict[str, list[RequestMetrics]] = defaultdict(list)
        self._by_agent: dict[str, list[RequestMetrics]] = defaultdict(list)

    def record(self, metrics: RequestMetrics) -> None:
        """Record metrics for a single request."""
        self._metrics.append(metrics)
        self._by_model[metrics.model].append(metrics)
        if metrics.agent_name:
            self._by_agent[metrics.agent_name].append(metrics)

        # Check SLO violations
        violations = self._check_single_slo(metrics)
        if violations:
            logger.warning(
                "metrics.slo_violation",
                request_id=metrics.request_id,
                violations=violations,
                model=metrics.model,
                agent=metrics.agent_name,
            )

        logger.info(
            "metrics.recorded",
            request_id=metrics.request_id,
            model=metrics.model,
            tps=round(metrics.tokens_per_second, 1),
            cost_usd=round(metrics.total_cost_usd, 6),
            ttft_ms=round(metrics.time_to_first_token_ms, 1),
            total_tokens=metrics.total_tokens,
        )

    def calculate_request_metrics(
        self,
        request_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_latency_ms: float,
        time_to_first_token_ms: float = 0.0,
        generation_latency_ms: float = 0.0,
        react_iterations: int = 0,
        tool_calls: int = 0,
        delegation_fan_out: int = 0,
        agent_name: str = "",
        context_window_size: int = 1_000_000,  # Gemini 2.5 Flash context window
    ) -> RequestMetrics:
        """Calculate all derived metrics from raw measurements."""
        total_tokens = prompt_tokens + completion_tokens

        # Tokens per second (generation throughput)
        gen_time_sec = (generation_latency_ms or total_latency_ms) / 1000
        tps = completion_tokens / gen_time_sec if gen_time_sec > 0 else 0.0

        # Cost calculation
        pricing = MODEL_PRICING.get(model, {"input": 0.40, "output": 1.60})
        input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (completion_tokens / 1_000_000) * pricing["output"]
        total_cost = input_cost + output_cost

        # Efficiency metrics
        ctx_utilization = prompt_tokens / context_window_size if context_window_size > 0 else 0.0
        token_efficiency = completion_tokens / total_tokens if total_tokens > 0 else 0.0

        metrics = RequestMetrics(
            request_id=request_id,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            time_to_first_token_ms=time_to_first_token_ms,
            total_latency_ms=total_latency_ms,
            generation_latency_ms=generation_latency_ms or total_latency_ms,
            tokens_per_second=tps,
            input_cost_usd=input_cost,
            output_cost_usd=output_cost,
            total_cost_usd=total_cost,
            cost_per_output_token_usd=output_cost / completion_tokens if completion_tokens > 0 else 0.0,
            context_window_utilization=ctx_utilization,
            token_efficiency=token_efficiency,
            react_iterations=react_iterations,
            tool_calls=tool_calls,
            delegation_fan_out=delegation_fan_out,
            agent_name=agent_name,
        )

        return metrics

    def get_aggregates(
        self,
        window_seconds: float = 3600,
        model: str | None = None,
        agent: str | None = None,
    ) -> AggregateMetrics:
        """Get aggregated metrics over a time window."""
        now = time.time()
        window_start = now - window_seconds

        # Filter metrics in window
        if model:
            source = self._by_model.get(model, [])
        elif agent:
            source = self._by_agent.get(agent, [])
        else:
            source = self._metrics

        in_window = [m for m in source if m.timestamp >= window_start]

        if not in_window:
            return AggregateMetrics(window_start=window_start, window_end=now)

        # Calculate aggregates
        tokens_list = sorted(m.total_tokens for m in in_window)
        latency_list = sorted(m.total_latency_ms for m in in_window)
        n = len(in_window)

        def percentile(sorted_list: list, p: float) -> float:
            k = max(0, int(len(sorted_list) * p) - 1)
            return sorted_list[k] if sorted_list else 0.0

        grounding_scores = [m.grounding_score for m in in_window if m.grounding_score is not None]

        return AggregateMetrics(
            window_start=window_start,
            window_end=now,
            request_count=n,
            total_tokens=sum(m.total_tokens for m in in_window),
            avg_tokens_per_request=sum(m.total_tokens for m in in_window) / n,
            p50_tokens=int(percentile(tokens_list, 0.50)),
            p95_tokens=int(percentile(tokens_list, 0.95)),
            p99_tokens=int(percentile(tokens_list, 0.99)),
            avg_ttft_ms=sum(m.time_to_first_token_ms for m in in_window) / n,
            p50_latency_ms=percentile(latency_list, 0.50),
            p95_latency_ms=percentile(latency_list, 0.95),
            p99_latency_ms=percentile(latency_list, 0.99),
            avg_tps=sum(m.tokens_per_second for m in in_window) / n,
            total_cost_usd=sum(m.total_cost_usd for m in in_window),
            avg_cost_per_request_usd=sum(m.total_cost_usd for m in in_window) / n,
            avg_grounding_score=(
                sum(grounding_scores) / len(grounding_scores) if grounding_scores else None
            ),
            slo_violations=sum(1 for m in in_window if self._check_single_slo(m)),
        )

    def _check_single_slo(self, metrics: RequestMetrics) -> list[str]:
        """Check if a single request violates any SLOs."""
        violations = []

        if metrics.time_to_first_token_ms > self._slos["ttft_ms"]:
            violations.append(
                f"TTFT {metrics.time_to_first_token_ms:.0f}ms > {self._slos['ttft_ms']:.0f}ms"
            )

        if metrics.tokens_per_second > 0 and metrics.tokens_per_second < self._slos["tps"]:
            violations.append(
                f"TPS {metrics.tokens_per_second:.1f} < {self._slos['tps']:.0f}"
            )

        if metrics.total_cost_usd > self._slos["cost_per_request_usd"]:
            violations.append(
                f"Cost ${metrics.total_cost_usd:.4f} > ${self._slos['cost_per_request_usd']:.4f}"
            )

        return violations

    def check_slos(self, window_seconds: float = 3600) -> dict[str, Any]:
        """Check SLO compliance across all requests in a window."""
        agg = self.get_aggregates(window_seconds=window_seconds)

        compliance = {}
        if agg.request_count > 0:
            compliance["ttft_p50_ok"] = agg.avg_ttft_ms <= self._slos["ttft_ms"]
            compliance["tps_avg_ok"] = agg.avg_tps >= self._slos["tps"]
            compliance["p99_latency_ok"] = agg.p99_latency_ms <= self._slos["p99_latency_ms"]
            compliance["avg_cost_ok"] = agg.avg_cost_per_request_usd <= self._slos["cost_per_request_usd"]
            compliance["slo_violation_rate"] = agg.slo_violations / agg.request_count

        return {
            "slos": self._slos,
            "compliance": compliance,
            "aggregates": agg.to_dict(),
        }

    def get_model_comparison(self, window_seconds: float = 3600) -> dict[str, Any]:
        """Compare metrics across different models."""
        comparisons = {}
        for model in self._by_model:
            agg = self.get_aggregates(window_seconds=window_seconds, model=model)
            if agg.request_count > 0:
                comparisons[model] = {
                    "requests": agg.request_count,
                    "avg_tps": round(agg.avg_tps, 1),
                    "avg_ttft_ms": round(agg.avg_ttft_ms, 1),
                    "avg_cost_usd": round(agg.avg_cost_per_request_usd, 6),
                    "p95_latency_ms": round(agg.p95_latency_ms, 1),
                    "total_cost_usd": round(agg.total_cost_usd, 4),
                }
        return comparisons

    def export_jsonl(self, path: Path | None = None) -> Path:
        """Export all metrics to JSONL for analysis."""
        path = path or Path("./logs/metrics.jsonl")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            for m in self._metrics:
                f.write(json.dumps(m.to_dict()) + "\n")
        return path
