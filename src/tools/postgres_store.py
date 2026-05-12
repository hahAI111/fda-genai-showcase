"""PostgreSQL store for operational metadata and RAG/search telemetry."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import structlog

from src.config import get_settings

logger = structlog.get_logger()


class PostgresStore:
    def __init__(self) -> None:
        settings = get_settings()
        self._dsn = settings.postgres_dsn
        if not self._dsn:
            raise RuntimeError("PostgreSQL DSN missing: POSTGRES_DSN")

    def _connect(self):
        import psycopg

        return psycopg.connect(self._dsn, autocommit=True)

    def initialize(self) -> None:
        ddl = """
        CREATE TABLE IF NOT EXISTS app_events (
            id BIGSERIAL PRIMARY KEY,
            event_type TEXT NOT NULL,
            payload JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS rag_search_logs (
            id BIGSERIAL PRIMARY KEY,
            query_text TEXT NOT NULL,
            result_count INT NOT NULL,
            top_sources JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS media_assets (
            id BIGSERIAL PRIMARY KEY,
            record_id TEXT,
            media_type TEXT NOT NULL,
            file_path TEXT,
            job_id TEXT,
            metadata JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(ddl)
        logger.info("postgres.initialized")

    def health(self) -> dict[str, Any]:
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT current_database(), version()")
                    row = cur.fetchone()
                    db_name = row[0] if row else "unknown"
            return {"status": "healthy", "database": db_name}
        except Exception as exc:
            return {"status": "unhealthy", "error": str(exc)}

    def log_rag_search(self, query_text: str, result_count: int, top_sources: list[str]) -> None:
        payload = json.dumps(top_sources, ensure_ascii=True)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO rag_search_logs(query_text, result_count, top_sources, created_at)
                    VALUES (%s, %s, %s::jsonb, %s)
                    """,
                    (query_text, int(result_count), payload, datetime.now(UTC)),
                )

    def save_media_asset(
        self,
        media_type: str,
        metadata: dict[str, Any],
        record_id: str | None = None,
        file_path: str | None = None,
        job_id: str | None = None,
    ) -> None:
        payload = json.dumps(metadata, ensure_ascii=True, default=str)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO media_assets(record_id, media_type, file_path, job_id, metadata, created_at)
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s)
                    """,
                    (record_id, media_type, file_path, job_id, payload, datetime.now(UTC)),
                )

    def summary(self) -> dict[str, int]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(1) FROM rag_search_logs")
                rag_count = int(cur.fetchone()[0])
                cur.execute("SELECT COUNT(1) FROM media_assets")
                media_count = int(cur.fetchone()[0])
                cur.execute("SELECT COUNT(1) FROM app_events")
                event_count = int(cur.fetchone()[0])
        return {
            "rag_search_logs": rag_count,
            "media_assets": media_count,
            "app_events": event_count,
        }

    def clear_media_assets(self) -> int:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM media_assets")
                return cur.rowcount

    def add_event(self, event_type: str, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=True, default=str)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO app_events(event_type, payload, created_at) VALUES (%s, %s::jsonb, %s)",
                    (event_type, body, datetime.now(UTC)),
                )
