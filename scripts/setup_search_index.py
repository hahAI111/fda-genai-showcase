"""Setup Azure AI Search Index + Storage Container.

This script provisions:
1. Azure Blob Storage container for enterprise documents
2. Azure AI Search index with vector search + semantic ranking

Run once to set up infrastructure, then use ingest_documents.py to populate.

Usage:
    python -m scripts.setup_search_index
"""

from __future__ import annotations

import sys

from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    AzureOpenAIVectorizer,
    AzureOpenAIVectorizerParameters,
    HnswAlgorithmConfiguration,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)

from src.config import get_azure_openai_resource_url, get_search_credential, get_settings
from src.tools.storage import BlobStorageTool


def create_storage_container():
    """Ensure the blob storage container exists."""
    print("=== Setting up Azure Blob Storage ===")
    storage = BlobStorageTool()
    storage.ensure_container()
    settings = get_settings()
    print(f"  Container: {settings.azure_storage_container}")
    print(f"  Account: {settings.azure_storage_account_url}")
    print()


def create_search_index():
    """Create or update the AI Search index."""
    print("=== Setting up Azure AI Search Index ===")
    settings = get_settings()

    if not settings.azure_search_endpoint:
        print("ERROR: AZURE_SEARCH_ENDPOINT not configured in .env")
        sys.exit(1)

    client = SearchIndexClient(
        endpoint=settings.azure_search_endpoint,
        credential=get_search_credential(),
    )

    # Define fields
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
        SearchableField(name="title", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SimpleField(name="source", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="source_url", type=SearchFieldDataType.String),
        SimpleField(name="category", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="chunk_id", type=SearchFieldDataType.String),
        SimpleField(name="created_at", type=SearchFieldDataType.DateTimeOffset, filterable=True, sortable=True),
        # Vector field for semantic search
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=3072,  # text-embedding-3-large
            vector_search_profile_name="vector-profile",
        ),
    ]

    # Vector search configuration with integrated vectorization
    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(name="hnsw-config"),
        ],
        profiles=[
            VectorSearchProfile(
                name="vector-profile",
                algorithm_configuration_name="hnsw-config",
                vectorizer_name="azure-openai-vectorizer",
            ),
        ],
        vectorizers=[
            AzureOpenAIVectorizer(
                vectorizer_name="azure-openai-vectorizer",
                parameters=AzureOpenAIVectorizerParameters(
                    resource_url=get_azure_openai_resource_url(),
                    deployment_name=settings.azure_ai_embedding_deployment,
                    api_key=settings.azure_openai_api_key or None,
                    model_name="text-embedding-3-large",
                ),
            ),
        ],
    )

    # Semantic search configuration (cross-encoder re-ranking)
    semantic_search = SemanticSearch(
        configurations=[
            SemanticConfiguration(
                name="default",
                prioritized_fields=SemanticPrioritizedFields(
                    title_field=SemanticField(field_name="title"),
                    content_fields=[SemanticField(field_name="content")],
                ),
            ),
        ],
    )

    index = SearchIndex(
        name=settings.azure_search_index,
        fields=fields,
        vector_search=vector_search,
        semantic_search=semantic_search,
    )

    result = client.create_or_update_index(index)
    print(f"  Index '{result.name}' created/updated successfully")
    print(f"  Fields: {len(fields)}")
    print(f"  Vector dimensions: 3072")
    print(f"  Semantic config: default")
    print(f"  Vectorizer: Azure OpenAI (integrated)")
    print()


if __name__ == "__main__":
    create_storage_container()
    create_search_index()
    print("=== Setup complete! ===")
    print("Next: python -m scripts.ingest_documents --source ./sample_data")
