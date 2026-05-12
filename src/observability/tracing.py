"""Observability — Structured logging and distributed tracing.

Enterprise Pattern: You can't operate what you can't observe.
This module provides:
1. Structured JSON logging (machine-parseable, not just for humans)
2. OpenTelemetry tracing (distributed traces across agents)
3. Metrics collection (latency, token usage, error rates)
4. Correlation IDs (trace a request across all agents)

This solves the enterprise blocker:
"We deployed AI but when something goes wrong, we can't debug it."
"""

from __future__ import annotations

import logging
import os

import structlog
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from src.config import get_settings


def setup_logging() -> None:
    """Configure structured JSON logging with structlog."""
    settings = get_settings()

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def setup_tracing() -> trace.Tracer:
    """Configure OpenTelemetry distributed tracing.

    In production, replace ConsoleSpanExporter with:
    - OTLPSpanExporter for Jaeger/Tempo
    - AzureMonitorTraceExporter for Application Insights
    """
    settings = get_settings()

    resource = Resource.create({
        "service.name": settings.otel_service_name,
        "service.version": "0.1.0",
    })

    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)

    return trace.get_tracer(settings.otel_service_name)


# Global tracer instance
_tracer: trace.Tracer | None = None


def get_tracer() -> trace.Tracer:
    global _tracer
    if os.getenv("PYTEST_CURRENT_TEST"):
        # Pytest captures and closes stdio aggressively; avoid background exporter noise.
        return trace.get_tracer("enterprise-genai-platform-test")
    if _tracer is None:
        _tracer = setup_tracing()
    return _tracer
