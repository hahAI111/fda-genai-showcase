"""Evaluation Pipeline — Continuous quality monitoring for production AI.

Enterprise Pattern: Evaluation isn't just for testing — it runs in production.
This pipeline:
1. Samples a % of production requests for evaluation
2. Runs multi-dimensional quality checks (relevance, groundedness, safety)
3. Logs results for dashboarding and alerting
4. Triggers alerts when quality degrades

This solves the enterprise deployment blocker:
"How do we know the AI is still working correctly after 3 months?"
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any

import structlog

from src.config import get_settings
from src.evaluation.metrics import EvalMetrics, EvalResult

logger = structlog.get_logger()


@dataclass
class EvalReport:
    """Complete evaluation report for one request."""

    conversation_id: str
    query: str
    response: str
    results: list[EvalResult]
    latency_ms: float
    timestamp: float = field(default_factory=time.time)

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def overall_score(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.score for r in self.results) / len(self.results)

    def to_dict(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "query": self.query[:200],
            "response": self.response[:200],
            "overall_score": self.overall_score,
            "all_passed": self.all_passed,
            "metrics": {
                r.metric: {"score": r.score, "passed": r.passed, "reasoning": r.reasoning}
                for r in self.results
            },
            "latency_ms": self.latency_ms,
            "timestamp": self.timestamp,
        }


class EvaluationPipeline:
    """Production evaluation pipeline with sampling and alerting."""

    def __init__(self, sample_rate: float | None = None):
        settings = get_settings()
        self._sample_rate = sample_rate or settings.eval_sample_rate
        self._metrics = EvalMetrics()
        self._enabled = settings.eval_enabled

    def should_evaluate(self) -> bool:
        """Probabilistic sampling — only evaluate a fraction of requests."""
        if not self._enabled:
            return False
        return random.random() < self._sample_rate

    async def evaluate(
        self,
        query: str,
        response: str,
        context: str = "",
        conversation_id: str = "",
    ) -> EvalReport:
        """Run full evaluation suite on a query-response pair.

        Evaluates:
        1. Relevance — does the response answer the query?
        2. Groundedness — is the response supported by retrieved context?
        3. Coherence — is the response well-structured and clear?
        4. Safety — is the response free from harmful content?
        """
        start = time.perf_counter()
        results: list[EvalResult] = []

        # Run evaluations (could be parallelized for lower latency)
        relevance = await self._metrics.evaluate_relevance(query, response)
        results.append(relevance)

        if context:
            groundedness = await self._metrics.evaluate_groundedness(response, context)
            results.append(groundedness)

        coherence = await self._metrics.evaluate_coherence(response)
        results.append(coherence)

        safety = await self._metrics.evaluate_safety(response)
        results.append(safety)

        latency = (time.perf_counter() - start) * 1000

        report = EvalReport(
            conversation_id=conversation_id,
            query=query,
            response=response,
            results=results,
            latency_ms=latency,
        )

        # Log evaluation results
        logger.info(
            "eval.completed",
            conversation_id=conversation_id,
            overall_score=report.overall_score,
            all_passed=report.all_passed,
            latency_ms=latency,
            **{r.metric: r.score for r in results},
        )

        # Alert on failures
        if not report.all_passed:
            failed = [r.metric for r in results if not r.passed]
            logger.warning(
                "eval.quality_alert",
                conversation_id=conversation_id,
                failed_metrics=failed,
                scores={r.metric: r.score for r in results if not r.passed},
            )

        return report
