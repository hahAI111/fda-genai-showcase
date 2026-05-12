"""Audit Logger — Immutable audit trail for enterprise compliance.

Enterprise Pattern: Every AI interaction must be auditable.
Regulations (GDPR, SOC2, HIPAA) require:
1. Who asked what, when
2. What data was retrieved
3. What the AI responded
4. What governance checks were applied
5. Token usage for cost attribution

This writes structured JSON logs (JSONL format) that can be
ingested into SIEM/analytics systems.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

from src.config import get_settings

logger = structlog.get_logger()


@dataclass
class AuditEntry:
    """One auditable interaction."""

    event_type: str  # "query", "tool_call", "response", "governance_check"
    conversation_id: str
    user_id: str | None = None
    tenant_id: str | None = None
    agent_name: str = ""
    content: dict[str, Any] = field(default_factory=dict)
    governance: dict[str, Any] = field(default_factory=dict)
    token_usage: dict[str, int] = field(default_factory=dict)
    latency_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "agent_name": self.agent_name,
            "content": self.content,
            "governance": self.governance,
            "token_usage": self.token_usage,
            "latency_ms": self.latency_ms,
            "timestamp": self.timestamp,
        }


class AuditLogger:
    """Append-only audit logger for compliance."""

    def __init__(self, log_path: Path | None = None):
        settings = get_settings()
        self._log_path = log_path or settings.audit_log_path
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, entry: AuditEntry) -> None:
        """Write an audit entry to the JSONL log file."""
        try:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict(), default=str) + "\n")
        except Exception as e:
            logger.error("audit.write_failed", error=str(e))

    def log_query(
        self,
        conversation_id: str,
        query: str,
        user_id: str | None = None,
        tenant_id: str | None = None,
    ) -> None:
        self.log(AuditEntry(
            event_type="query",
            conversation_id=conversation_id,
            user_id=user_id,
            tenant_id=tenant_id,
            content={
                "query": query[:500],
                "query_truncated": len(query) > 500,
            },
        ))

    def log_response(
        self,
        conversation_id: str,
        agent_name: str,
        response: str,
        token_usage: dict[str, int] | None = None,
        latency_ms: float = 0.0,
        governance: dict[str, Any] | None = None,
    ) -> None:
        self.log(AuditEntry(
            event_type="response",
            conversation_id=conversation_id,
            agent_name=agent_name,
            content={"response": response[:500]},
            token_usage=token_usage or {},
            latency_ms=latency_ms,
            governance=governance or {},
        ))

    def log_governance_action(
        self,
        conversation_id: str,
        action: str,
        details: dict[str, Any],
    ) -> None:
        self.log(AuditEntry(
            event_type="governance_check",
            conversation_id=conversation_id,
            governance={"action": action, **details},
        ))
