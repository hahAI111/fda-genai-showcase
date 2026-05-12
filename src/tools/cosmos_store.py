"""Cosmos DB storage for chat and media metadata.

This module is production-usable (no mocks):
- Creates database and containers if not present
- Persists chat interactions
- Persists media generation records (image/video/ppt)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from azure.cosmos import CosmosClient, PartitionKey, exceptions

from src.config import get_settings

logger = structlog.get_logger()


class CosmosStore:
    def __init__(self) -> None:
        self._settings = get_settings()
        if not self._settings.azure_cosmos_endpoint or not self._settings.azure_cosmos_key:
            raise RuntimeError("Cosmos settings missing: AZURE_COSMOS_ENDPOINT/AZURE_COSMOS_KEY")

        self._client = CosmosClient(
            url=self._settings.azure_cosmos_endpoint,
            credential=self._settings.azure_cosmos_key,
        )
        self._db = None
        self._chat_container = None
        self._media_container = None
        self._eval_container = None
        self._auth_container = None

    def initialize(self) -> None:
        """Create DB + containers if missing."""
        db_name = self._settings.azure_cosmos_database
        chat_name = self._settings.azure_cosmos_chat_container
        media_name = self._settings.azure_cosmos_media_container
        eval_name = self._settings.azure_cosmos_eval_container
        auth_name = self._settings.azure_cosmos_auth_container

        self._db = self._client.create_database_if_not_exists(id=db_name)
        self._chat_container = self._db.create_container_if_not_exists(
            id=chat_name,
            partition_key=PartitionKey(path="/conversation_id"),
        )
        self._media_container = self._db.create_container_if_not_exists(
            id=media_name,
            partition_key=PartitionKey(path="/media_type"),
        )
        self._eval_container = self._db.create_container_if_not_exists(
            id=eval_name,
            partition_key=PartitionKey(path="/conversation_id"),
        )
        self._auth_container = self._db.create_container_if_not_exists(
            id=auth_name,
            partition_key=PartitionKey(path="/provider"),
        )
        logger.info(
            "cosmos.initialized",
            database=db_name,
            chat_container=chat_name,
            media_container=media_name,
            eval_container=eval_name,
            auth_container=auth_name,
        )

    def health(self) -> dict[str, Any]:
        try:
            if self._db is None:
                self.initialize()
            db_props = self._db.read()
            return {"status": "healthy", "database": db_props.get("id")}
        except Exception as exc:
            return {"status": "unhealthy", "error": str(exc)}

    def save_chat(self, conversation_id: str, user_message: str, response: str, agent: str, governance: dict[str, Any] | None = None) -> str:
        if self._chat_container is None:
            self.initialize()

        item_id = uuid.uuid4().hex
        doc = {
            "id": item_id,
            "conversation_id": conversation_id,
            "user_message": user_message,
            "response": response,
            "agent": agent,
            "governance": governance or {},
            "created_at": datetime.now(UTC).isoformat(),
            "type": "chat_record",
        }
        self._chat_container.upsert_item(doc)
        return item_id

    def save_media(self, media_type: str, prompt: str, result: dict[str, Any], conversation_id: str | None = None) -> str:
        if self._media_container is None:
            self.initialize()

        item_id = uuid.uuid4().hex
        doc = {
            "id": item_id,
            "media_type": media_type,
            "prompt": prompt,
            "result": result,
            "conversation_id": conversation_id,
            "created_at": datetime.now(UTC).isoformat(),
            "type": "media_record",
        }
        self._media_container.upsert_item(doc)
        return item_id

    def recent_media(self, media_type: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        if self._media_container is None:
            self.initialize()

        query = "SELECT TOP @limit * FROM c ORDER BY c.created_at DESC"
        params = [{"name": "@limit", "value": limit}]
        if media_type:
            query = "SELECT TOP @limit * FROM c WHERE c.media_type = @media_type ORDER BY c.created_at DESC"
            params.append({"name": "@media_type", "value": media_type})

        items = list(self._media_container.query_items(query=query, parameters=params, enable_cross_partition_query=True))
        return items

    def count_media(self) -> int:
        if self._media_container is None:
            self.initialize()

        query = "SELECT VALUE COUNT(1) FROM c"
        rows = list(self._media_container.query_items(query=query, enable_cross_partition_query=True))
        if not rows:
            return 0
        return int(rows[0])

    def clear_media_history(self, limit: int = 500) -> dict[str, Any]:
        """Delete up to `limit` media records from Cosmos.

        This is intended for cache/history cleanup from the web UI.
        """
        if self._media_container is None:
            self.initialize()

        safe_limit = max(1, min(limit, 5000))
        query = "SELECT TOP @limit c.id, c.media_type FROM c ORDER BY c.created_at DESC"
        params = [{"name": "@limit", "value": safe_limit}]
        rows = list(
            self._media_container.query_items(
                query=query,
                parameters=params,
                enable_cross_partition_query=True,
            )
        )

        deleted = 0
        failed = 0
        for row in rows:
            item_id = row.get("id")
            media_type = row.get("media_type")
            if not item_id or not media_type:
                failed += 1
                continue
            try:
                self._media_container.delete_item(item=item_id, partition_key=media_type)
                deleted += 1
            except exceptions.CosmosResourceNotFoundError:
                continue
            except Exception:
                failed += 1

        return {
            "requested": safe_limit,
            "matched": len(rows),
            "deleted": deleted,
            "failed": failed,
        }

    def save_evaluation(self, conversation_id: str, query: str, response: str, evaluation: dict[str, Any]) -> str:
        if self._eval_container is None:
            self.initialize()

        item_id = uuid.uuid4().hex
        doc = {
            "id": item_id,
            "conversation_id": conversation_id,
            "query": query,
            "response": response,
            "evaluation": evaluation,
            "created_at": datetime.now(UTC).isoformat(),
            "type": "evaluation_record",
        }
        self._eval_container.upsert_item(doc)
        return item_id

    def save_auth_event(
        self,
        provider: str,
        status: str,
        user_id: str | None = None,
        email: str | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        if self._auth_container is None:
            self.initialize()

        item_id = uuid.uuid4().hex
        doc = {
            "id": item_id,
            "provider": provider,
            "status": status,
            "user_id": user_id,
            "email": email,
            "ip": ip,
            "user_agent": user_agent,
            "metadata": metadata or {},
            "created_at": datetime.now(UTC).isoformat(),
            "type": "auth_event",
        }
        self._auth_container.upsert_item(doc)
        return item_id
