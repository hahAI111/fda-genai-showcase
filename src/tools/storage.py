"""Azure Blob Storage Tool — Document storage and retrieval.

Enterprise Pattern: Documents are stored in Azure Blob Storage as the
source of truth. AI Search indexes them for retrieval, but the original
documents live in Blob Storage. This separation enables:
1. Independent scaling of storage and search
2. Document versioning and lifecycle management
3. Compliance-friendly audit of what was indexed
4. Re-indexing without re-uploading documents

Identity-based auth — no storage keys.
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from azure.identity import DefaultAzureCredential
from azure.storage.blob import ContentSettings
from azure.storage.blob import BlobServiceClient, ContainerClient

from src.config import get_credential, get_settings

logger = structlog.get_logger()


class BlobStorageTool:
    """Azure Blob Storage for enterprise document management."""

    def __init__(
        self,
        account_url: str | None = None,
        container_name: str | None = None,
        credential: DefaultAzureCredential | str | None = None,
    ):
        settings = get_settings()
        self._account_url = account_url or settings.azure_storage_account_url
        self._container_name = container_name or settings.azure_storage_container
        self._credential = credential or self._resolve_credential()
        self._client: BlobServiceClient | None = None

    def _resolve_credential(self) -> DefaultAzureCredential | str:
        settings = get_settings()
        if settings.azure_storage_account_key:
            return settings.azure_storage_account_key
        return get_credential()

    def _get_service_client(self) -> BlobServiceClient:
        if self._client is None:
            self._client = BlobServiceClient(
                account_url=self._account_url,
                credential=self._credential,
            )
        return self._client

    def _get_container_client(self) -> ContainerClient:
        return self._get_service_client().get_container_client(self._container_name)

    def ensure_container(self) -> None:
        """Create the container if it doesn't exist."""
        container = self._get_container_client()
        try:
            container.get_container_properties()
            logger.info("storage.container_exists", container=self._container_name)
        except Exception:
            container.create_container()
            logger.info("storage.container_created", container=self._container_name)

    def upload_document(
        self,
        blob_name: str,
        content: str | bytes,
        metadata: dict[str, str] | None = None,
        content_type: str = "text/markdown",
    ) -> str:
        """Upload a document to blob storage.

        Returns the blob URL.
        """
        container = self._get_container_client()
        data = content.encode("utf-8") if isinstance(content, str) else content
        blob_client = container.upload_blob(
            name=blob_name,
            data=data,
            overwrite=True,
            metadata=metadata,
            content_settings=ContentSettings(content_type=content_type),
        )
        url = f"{self._account_url}/{self._container_name}/{blob_name}"
        logger.info("storage.uploaded", blob=blob_name, size=len(data))
        return url

    def download_document(self, blob_name: str) -> str:
        """Download a document's content as text."""
        container = self._get_container_client()
        blob_data = container.download_blob(blob_name)
        content = blob_data.readall().decode("utf-8")
        logger.info("storage.downloaded", blob=blob_name, size=len(content))
        return content

    def list_documents(self, prefix: str | None = None) -> list[dict[str, Any]]:
        """List documents in the container."""
        container = self._get_container_client()
        blobs = container.list_blobs(name_starts_with=prefix, include=["metadata"])
        docs = []
        for blob in blobs:
            docs.append({
                "name": blob.name,
                "size": blob.size,
                "last_modified": blob.last_modified.isoformat() if blob.last_modified else None,
                "content_type": blob.content_settings.content_type if blob.content_settings else None,
                "metadata": blob.metadata or {},
            })
        logger.info("storage.listed", prefix=prefix, count=len(docs))
        return docs

    def delete_document(self, blob_name: str) -> None:
        """Delete a document from storage."""
        container = self._get_container_client()
        container.delete_blob(blob_name)
        logger.info("storage.deleted", blob=blob_name)
