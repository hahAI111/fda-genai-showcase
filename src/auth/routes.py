"""OAuth 2.0 API endpoints for Google Cloud authentication.

Provides REST endpoints for OAuth flow management:
- GET /auth/login — redirect to Google OAuth consent screen
- GET /auth/callback — handle OAuth code exchange
- GET /auth/status — current auth session status
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from src.auth import GoogleAuthManager

try:
    from src.tools.cosmos_store import CosmosStore
except Exception:  # pragma: no cover - optional runtime dependency
    CosmosStore = None  # type: ignore[assignment]

router = APIRouter(prefix="/auth", tags=["authentication"])

auth_manager = GoogleAuthManager()
_cosmos_store = None


def _get_cosmos_store():
    global _cosmos_store
    if CosmosStore is None:
        return None

    if _cosmos_store is None:
        try:
            _cosmos_store = CosmosStore()
            _cosmos_store.initialize()
        except Exception:
            _cosmos_store = None
    return _cosmos_store


@router.get("/login")
async def oauth_login(
    redirect_uri: str = "http://localhost:8000/auth/callback",
):
    """Initiate OAuth 2.0 login flow."""
    try:
        auth_url = await auth_manager.get_oauth2_authorization_url(
            redirect_uri=redirect_uri,
        )
        return RedirectResponse(url=auth_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/callback")
async def oauth_callback(code: str, state: str | None = None):
    """Handle OAuth 2.0 callback with authorization code."""
    try:
        result = await auth_manager.exchange_oauth2_code(code=code)

        store = _get_cosmos_store()
        if store is not None:
            try:
                user_info = result.get("user", {}) if isinstance(result, dict) else {}
                store.save_auth_event(
                    provider="google_oauth",
                    status="success",
                    user_id=user_info.get("id"),
                    email=user_info.get("email"),
                    metadata={"state": state},
                )
            except Exception:
                pass

        return result
    except Exception as e:
        store = _get_cosmos_store()
        if store is not None:
            try:
                store.save_auth_event(
                    provider="google_oauth",
                    status="failed",
                    metadata={"error": str(e), "state": state},
                )
            except Exception:
                pass
        raise HTTPException(status_code=400, detail=f"OAuth exchange failed: {e}")


@router.get("/status")
async def auth_status():
    """Current authentication session status."""
    return auth_manager.get_auth_stats()
