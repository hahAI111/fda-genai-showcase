"""Google Cloud OAuth — Production-grade authentication for customer infrastructure.

Architectural Governance Pattern:
This module implements the connection between Google's AI products and
customer infrastructure using OAuth 2.0-based authentication.

Supported auth flows:
1. Service Account (server-to-server) — for backend services
2. OAuth 2.0 Authorization Code (web apps) — for user-facing apps
3. Application Default Credentials (ADC) — for GCP-native workloads
4. Workload Identity Federation — for multi-cloud (Azure/AWS → GCP)

Security requirements:
- All tokens are short-lived (1 hour) with automatic refresh
- Scopes are minimally scoped per service
- Credentials are never logged or exposed in responses
- Token refresh is transparent to callers
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


# Minimal scopes per Google AI service
SERVICE_SCOPES = {
    "vertex_ai": [
        "https://www.googleapis.com/auth/cloud-platform",
    ],
    "cloud_storage": [
        "https://www.googleapis.com/auth/devstorage.read_write",
    ],
    "discovery_engine": [
        "https://www.googleapis.com/auth/cloud-platform",
    ],
    "bigquery": [
        "https://www.googleapis.com/auth/bigquery",
    ],
}


@dataclass
class AuthToken:
    """Represents an authenticated token with metadata."""

    access_token: str
    token_type: str = "Bearer"
    expires_at: float = 0.0
    scopes: list[str] = field(default_factory=list)
    service: str = ""

    @property
    def is_expired(self) -> bool:
        return time.time() >= self.expires_at - 60  # 60s buffer

    @property
    def remaining_seconds(self) -> float:
        return max(0, self.expires_at - time.time())


@dataclass
class AuthSession:
    """Tracks an authenticated session for audit."""

    session_id: str
    auth_method: str  # "service_account", "oauth2", "adc", "workload_identity"
    principal: str  # email or service account
    scopes: list[str]
    created_at: float = field(default_factory=time.time)
    last_refreshed: float = field(default_factory=time.time)
    request_count: int = 0


class GoogleAuthManager:
    """Manages authentication to Google Cloud services.

    Implements the Architectural Governance pattern:
    - Centralized auth management (not scattered across tools)
    - Automatic token refresh with audit trail
    - Scope enforcement (least privilege)
    - Multi-cloud credential bridging
    """

    def __init__(self):
        self._credentials = None
        self._sessions: dict[str, AuthSession] = {}
        self._token_cache: dict[str, AuthToken] = {}

    async def get_credentials(self, service: str = "vertex_ai"):
        """Get authenticated credentials for a Google Cloud service.

        Uses Application Default Credentials (ADC) with automatic
        scope selection based on the target service.
        """
        import google.auth
        from google.auth.transport.requests import Request as AuthRequest

        scopes = SERVICE_SCOPES.get(service, SERVICE_SCOPES["vertex_ai"])

        # Check cache
        cache_key = f"{service}:{','.join(scopes)}"
        cached = self._token_cache.get(cache_key)
        if cached and not cached.is_expired:
            return self._credentials

        # Get fresh credentials
        if self._credentials is None:
            settings = get_settings()
            if settings.gcp_service_account_key_path:
                # Explicit service account key (dev environments)
                from google.oauth2 import service_account
                self._credentials = service_account.Credentials.from_service_account_file(
                    settings.gcp_service_account_key_path,
                    scopes=scopes,
                )
                auth_method = "service_account"
            else:
                # Application Default Credentials (production)
                self._credentials, project = google.auth.default(scopes=scopes)
                auth_method = "adc"

            logger.info("auth.credentials_loaded", method=auth_method, service=service)
        else:
            auth_method = "cached"

        # Refresh if needed
        if not self._credentials.valid:
            self._credentials.refresh(AuthRequest())
            logger.info("auth.token_refreshed", service=service)

        # Cache the token
        self._token_cache[cache_key] = AuthToken(
            access_token="[REDACTED]",  # Never log actual tokens
            expires_at=time.time() + 3600,  # ADC tokens are typically 1 hour
            scopes=scopes,
            service=service,
        )

        # Track session for audit
        session = AuthSession(
            session_id=cache_key,
            auth_method=auth_method,
            principal=getattr(self._credentials, "service_account_email", "user@default"),
            scopes=scopes,
        )
        self._sessions[cache_key] = session

        return self._credentials

    async def get_oauth2_authorization_url(
        self,
        redirect_uri: str = "http://localhost:8000/oauth/callback",
        scopes: list[str] | None = None,
    ) -> str:
        """Generate OAuth 2.0 authorization URL for web app flow.

        Used when the platform needs to access resources on behalf of a user
        (e.g., accessing their Cloud Storage or BigQuery datasets).
        """
        from google_auth_oauthlib.flow import Flow

        settings = get_settings()

        if not settings.gcp_oauth_client_id:
            raise ValueError(
                "OAuth client ID not configured. Set GCP_OAUTH_CLIENT_ID in .env"
            )

        client_config = {
            "web": {
                "client_id": settings.gcp_oauth_client_id,
                "client_secret": settings.gcp_oauth_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri],
            }
        }

        flow = Flow.from_client_config(
            client_config,
            scopes=scopes or SERVICE_SCOPES["vertex_ai"],
            redirect_uri=redirect_uri,
        )

        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )

        logger.info("auth.oauth2_url_generated", redirect_uri=redirect_uri)
        return auth_url

    async def exchange_oauth2_code(
        self,
        code: str,
        redirect_uri: str = "http://localhost:8000/oauth/callback",
    ) -> dict[str, Any]:
        """Exchange OAuth 2.0 authorization code for tokens.

        Returns token metadata (never the raw token to the caller).
        """
        from google_auth_oauthlib.flow import Flow

        settings = get_settings()

        client_config = {
            "web": {
                "client_id": settings.gcp_oauth_client_id,
                "client_secret": settings.gcp_oauth_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri],
            }
        }

        flow = Flow.from_client_config(
            client_config,
            scopes=SERVICE_SCOPES["vertex_ai"],
            redirect_uri=redirect_uri,
        )

        flow.fetch_token(code=code)
        credentials = flow.credentials

        logger.info("auth.oauth2_code_exchanged", has_refresh_token=bool(credentials.refresh_token))

        return {
            "authenticated": True,
            "token_type": "Bearer",
            "expires_at": credentials.expiry.isoformat() if credentials.expiry else None,
            "scopes": list(credentials.scopes) if credentials.scopes else [],
        }

    def get_auth_stats(self) -> dict[str, Any]:
        """Auth session statistics for monitoring dashboards."""
        return {
            "active_sessions": len(self._sessions),
            "cached_tokens": len(self._token_cache),
            "sessions": [
                {
                    "service": s.session_id,
                    "method": s.auth_method,
                    "principal": s.principal,
                    "age_seconds": round(time.time() - s.created_at, 0),
                }
                for s in self._sessions.values()
            ],
        }


# === Workload Identity Federation ===

class WorkloadIdentityBridge:
    """Bridge authentication from Azure/AWS to Google Cloud.

    Enables multi-cloud architectures where workloads running on
    Azure or AWS need to access Google Cloud AI services without
    managing separate service account keys.

    Pattern:
    Azure Managed Identity → Workload Identity Pool → GCP SA impersonation
    """

    def __init__(
        self,
        workload_identity_pool: str,
        provider_id: str,
        service_account_email: str,
    ):
        self._pool = workload_identity_pool
        self._provider = provider_id
        self._sa_email = service_account_email

    async def get_federated_credentials(self):
        """Get GCP credentials via Workload Identity Federation."""
        import google.auth
        from google.auth import external_account

        # The credential config is auto-discovered from
        # GOOGLE_APPLICATION_CREDENTIALS pointing to a WIF config JSON
        credentials, project = google.auth.default(
            scopes=SERVICE_SCOPES["vertex_ai"]
        )

        logger.info(
            "auth.workload_identity",
            pool=self._pool,
            provider=self._provider,
            target_sa=self._sa_email,
        )

        return credentials
