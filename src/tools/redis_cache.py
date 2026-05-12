"""Redis cache wrapper for production hot-path caching.

Use cases:
- Chat response cache (prompt + tenant key)
- Search result cache
- Evaluation result cache
- Session/cache invalidation ready
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import redis
import structlog

from src.config import get_settings

logger = structlog.get_logger()


class RedisCache:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.azure_redis_host or not settings.azure_redis_key:
            raise RuntimeError("Redis settings missing: AZURE_REDIS_HOST/AZURE_REDIS_KEY")

        self._ttl = settings.redis_cache_ttl_seconds
        self._client = redis.Redis(
            host=settings.azure_redis_host,
            port=settings.azure_redis_port,
            password=settings.azure_redis_key,
            ssl=True,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
        )

    @staticmethod
    def build_chat_key(message: str, tenant_id: str | None = None) -> str:
        raw = f"chat::{tenant_id or 'default'}::{message.strip()}"
        return "chat:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get_json(self, key: str) -> dict[str, Any] | None:
        val = self._client.get(key)
        if not val:
            return None
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            logger.warning("redis.invalid_json", key=key)
            return None

    def set_json(self, key: str, payload: dict[str, Any], ttl_seconds: int | None = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self._ttl
        self._client.setex(key, ttl, json.dumps(payload, ensure_ascii=True, default=str))

    def ping(self) -> bool:
        return bool(self._client.ping())

    def db_size(self) -> int:
        return int(self._client.dbsize())

    def clear_prefix(self, prefix: str) -> int:
        deleted = 0
        cursor = 0
        pattern = prefix if prefix.endswith("*") else f"{prefix}*"
        while True:
            cursor, keys = self._client.scan(cursor=cursor, match=pattern, count=200)
            if keys:
                deleted += int(self._client.delete(*keys))
            if cursor == 0:
                break
        return deleted

    def clear_known_app_keys(self) -> dict[str, int]:
        return {
            "chat": self.clear_prefix("chat:"),
            "search": self.clear_prefix("search:"),
            "evaluation": self.clear_prefix("eval:"),
        }
