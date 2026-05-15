"""Enterprise GenAI Platform — Configuration.

Supports dual authentication:
- Google Cloud: OAuth 2.0 / Application Default Credentials (ADC)
- Azure: API key or DefaultAzureCredential

Production pattern: prefer identity-based auth, but allow API key mode for
local Azure AI Foundry interview demos and isolated subscriptions.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings


class CloudProvider(str, Enum):
    GOOGLE = "google"
    AZURE = "azure"


class Settings(BaseSettings):
    # Primary cloud provider
    cloud_provider: CloudProvider = CloudProvider.AZURE

    # --- Google Cloud ---
    gcp_project_id: str = "enterprise-genai-platform"
    gcp_location: str = "us-central1"
    gcp_model: str = "gemini-2.5-flash"
    gcp_embedding_model: str = "text-embedding-005"
    # Vertex AI Search
    gcp_search_datastore_id: str = "enterprise-knowledge-store"
    gcp_search_engine_id: str = "enterprise-search-engine"
    # Cloud Storage
    gcp_storage_bucket: str = "enterprise-genai-docs"
    # OAuth 2.0
    gcp_oauth_client_id: str = ""
    gcp_oauth_client_secret: str = ""
    gcp_service_account_key_path: str = ""  # Path to SA JSON key (dev only; prod uses ADC)

    # --- Azure (multi-cloud support) ---
    azure_ai_endpoint: str = ""
    azure_ai_project: str = ""
    azure_ai_api_version: str = "2026-04-01"
    azure_ai_chat_deployment: str = "gpt-5.2"
    azure_ai_embedding_deployment: str = "text-embedding-3-large"
    azure_openai_api_key: str = ""
    azure_openai_base_url: str = ""
    azure_ai_image_deployment: str = "gpt-image-2"
    azure_ai_video_deployment: str = "sora-2"
    azure_subscription_id: str = ""
    azure_resource_group: str = ""
    azure_search_endpoint: str = ""
    azure_search_index: str = "enterprise-knowledge"
    azure_search_api_key: str = ""
    azure_storage_account_url: str = ""
    azure_storage_account_key: str = ""
    azure_storage_container: str = "enterprise-docs"
    # Cosmos DB (database for chat/media records)
    azure_cosmos_endpoint: str = ""
    azure_cosmos_key: str = ""
    azure_cosmos_database: str = "content-studio"
    azure_cosmos_chat_container: str = "chat_records"
    azure_cosmos_media_container: str = "media_records"
    azure_cosmos_eval_container: str = "evaluation_records"
    azure_cosmos_auth_container: str = "auth_records"

    # Azure Cache for Redis (production hot cache)
    azure_redis_host: str = ""
    azure_redis_port: int = 6380
    azure_redis_key: str = ""
    redis_cache_ttl_seconds: int = 600

    # PostgreSQL (operational telemetry + RAG/search logs)
    postgres_dsn: str = ""

    # Observability
    log_level: str = "INFO"
    otel_service_name: str = "enterprise-genai-platform"

    # Security
    cors_allowed_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Governance
    pii_detection_enabled: bool = True
    content_safety_enabled: bool = True
    audit_log_path: Path = Path("./logs/audit.jsonl")
    azure_content_safety_endpoint: str = ""
    azure_content_safety_key: str = ""
    gdpr_data_retention_days: int = 90
    gdpr_right_to_erasure: bool = True

    # Evaluation
    eval_enabled: bool = True
    eval_sample_rate: float = 0.1

    # LLM-Native Metrics
    metrics_enabled: bool = True
    metrics_export_interval_seconds: int = 60

    # Runtime routing for chat endpoint: flat | hierarchical | auto
    agent_runtime_mode: str = "flat"

    # Product Feedback Loop
    feedback_enabled: bool = True
    feedback_log_path: Path = Path("./logs/feedback.jsonl")

    # Cost Control - Idle auto-stop
    auto_stop_enabled: bool = False
    auto_stop_mode: str = "soft"  # soft | hard
    auto_stop_allow_hard_shutdown: bool = False
    auto_stop_idle_minutes: int = 90
    auto_stop_check_interval_seconds: int = 120
    auto_stop_skip_days: str = "20"  # comma-separated month days, e.g. "20,21"
    auto_stop_ignore_paths: str = "/health,/docs,/openapi.json,/internal,/"
    auto_stop_subscription_id: str = ""
    auto_stop_resource_group: str = ""
    auto_stop_webapp_name: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _normalize_azure_openai_base_url(base_url: str) -> str:
    normalized = (base_url or "").strip().rstrip("/")
    if normalized and not normalized.endswith("/openai/v1"):
        normalized = f"{normalized}/openai/v1"
    return normalized


@lru_cache
def get_azure_openai_resource_url() -> str:
    """Return the Azure OpenAI resource URL without the /openai/v1 suffix."""
    settings = get_settings()
    base_url = _normalize_azure_openai_base_url(
        settings.azure_openai_base_url or settings.azure_ai_endpoint,
    )
    return base_url.removesuffix("/openai/v1")


# === Google Cloud Auth ===

@lru_cache
def get_gcp_credentials():
    """Application Default Credentials (ADC) for Google Cloud.

    Auth chain:
    1. GOOGLE_APPLICATION_CREDENTIALS env var (service account JSON)
    2. gcloud auth application-default login (dev workstation)
    3. Metadata server (GKE, Cloud Run, Compute Engine)
    """
    import google.auth
    credentials, project = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    return credentials


@lru_cache
def get_gcp_genai_client():
    """Google GenAI client for Gemini models via Vertex AI."""
    from google import genai

    settings = get_settings()
    client = genai.Client(
        vertexai=True,
        project=settings.gcp_project_id,
        location=settings.gcp_location,
    )
    return client


# === Azure Auth (multi-cloud) ===

@lru_cache
def get_credential():
    """Azure DefaultAzureCredential — kept for multi-cloud support."""
    from azure.identity import DefaultAzureCredential
    return DefaultAzureCredential()


@lru_cache
def get_token_provider():
    """Bearer token provider for Azure OpenAI — identity-based auth, no keys."""
    from azure.identity import get_bearer_token_provider
    return get_bearer_token_provider(
        get_credential(),
        "https://cognitiveservices.azure.com/.default",
    )


@lru_cache
def get_search_credential():
    """Azure AI Search credential supporting API key and Entra auth."""
    from azure.core.credentials import AzureKeyCredential

    settings = get_settings()
    if settings.azure_search_api_key:
        return AzureKeyCredential(settings.azure_search_api_key)
    return get_credential()


@lru_cache
def get_azure_openai_client():
    """Azure OpenAI async client supporting API key and Entra auth."""
    from openai import AsyncAzureOpenAI, AsyncOpenAI

    settings = get_settings()
    if settings.azure_openai_api_key:
        return AsyncOpenAI(
            api_key=settings.azure_openai_api_key,
            base_url=_normalize_azure_openai_base_url(
                settings.azure_openai_base_url or settings.azure_ai_endpoint,
            ),
        )

    return AsyncAzureOpenAI(
        azure_endpoint=settings.azure_ai_endpoint,
        azure_ad_token_provider=get_token_provider(),
        api_version=settings.azure_ai_api_version,
    )


@lru_cache
def get_azure_openai_sync_client():
    """Azure OpenAI sync client for image and video generation helpers."""
    from openai import AzureOpenAI, OpenAI

    settings = get_settings()
    if settings.azure_openai_api_key:
        return OpenAI(
            api_key=settings.azure_openai_api_key,
            base_url=_normalize_azure_openai_base_url(
                settings.azure_openai_base_url or settings.azure_ai_endpoint,
            ),
        )

    return AzureOpenAI(
        azure_endpoint=settings.azure_ai_endpoint,
        azure_ad_token_provider=get_token_provider(),
        api_version=settings.azure_ai_api_version,
    )


@lru_cache
def get_cosmos_client():
    """Cosmos client helper for app-level database persistence."""
    from azure.cosmos import CosmosClient

    settings = get_settings()
    if not settings.azure_cosmos_endpoint or not settings.azure_cosmos_key:
        raise RuntimeError("Cosmos settings missing: AZURE_COSMOS_ENDPOINT/AZURE_COSMOS_KEY")
    return CosmosClient(url=settings.azure_cosmos_endpoint, credential=settings.azure_cosmos_key)
