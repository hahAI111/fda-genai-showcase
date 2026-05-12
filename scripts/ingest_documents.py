"""Document Ingestion — Upload to Blob Storage + Index into Azure AI Search.

Pipeline:
1. Read documents from a source directory
2. Upload originals to Azure Blob Storage (source of truth)
3. Chunk into semantically meaningful segments
4. Index chunks into Azure AI Search (vectorization handled by the index)

Enterprise Pattern:
- Blob Storage = source of truth (document lifecycle)
- AI Search = retrieval index (search + vector)
- Separation enables re-indexing without re-uploading

Usage:
    python -m scripts.ingest_documents --source ./sample_data
"""

from __future__ import annotations

import argparse
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from azure.search.documents import SearchClient

from src.config import get_search_credential, get_settings
from src.tools.storage import BlobStorageTool


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 200,
) -> list[str]:
    """Split text into overlapping chunks.

    Uses sentence-aware splitting to avoid cutting mid-sentence.
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        # Try to break at sentence boundary
        if end < len(text):
            # Look for sentence-ending punctuation near the boundary
            for sep in [". ", ".\n", "! ", "? ", "\n\n"]:
                last_sep = text.rfind(sep, start + chunk_size // 2, end)
                if last_sep != -1:
                    end = last_sep + len(sep)
                    break

        chunks.append(text[start:end].strip())
        start = end - overlap

    return [c for c in chunks if c]  # Filter empty chunks


def generate_doc_id(source: str, chunk_idx: int) -> str:
    """Generate a deterministic document ID for idempotent ingestion."""
    content = f"{source}:{chunk_idx}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def ingest_directory(source_dir: Path):
    """Upload to Blob Storage + Index into Azure AI Search."""
    settings = get_settings()

    if not settings.azure_search_endpoint:
        print("ERROR: AZURE_SEARCH_ENDPOINT not configured")
        return

    # Step 1: Upload originals to Azure Blob Storage
    print("=== Step 1: Upload to Azure Blob Storage ===")
    storage = BlobStorageTool()
    storage.ensure_container()

    supported_extensions = {".txt", ".md", ".json", ".csv"}
    source_files = [f for f in source_dir.rglob("*") if f.suffix.lower() in supported_extensions]

    for file_path in source_files:
        relative_path = file_path.relative_to(source_dir)
        blob_name = str(relative_path).replace("\\", "/")
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        category = _infer_category(file_path)

        storage.upload_document(
            blob_name=blob_name,
            content=content,
            metadata={"category": category, "source_file": str(relative_path)},
            content_type="text/markdown" if file_path.suffix == ".md" else "text/plain",
        )
        print(f"  Uploaded: {blob_name}")

    print(f"  Total files uploaded: {len(source_files)}")
    print()

    # Step 2: Chunk and index into AI Search
    print("=== Step 2: Index into Azure AI Search ===")
    search_client = SearchClient(
        endpoint=settings.azure_search_endpoint,
        index_name=settings.azure_search_index,
        credential=get_search_credential(),
    )

    documents = []

    for file_path in source_files:
        relative_path = file_path.relative_to(source_dir)
        blob_name = str(relative_path).replace("\\", "/")
        blob_url = f"{settings.azure_storage_account_url}/{settings.azure_storage_container}/{blob_name}"

        print(f"  Chunking: {file_path.name}")
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        chunks = chunk_text(text)

        for idx, chunk in enumerate(chunks):
            doc_id = generate_doc_id(str(relative_path), idx)
            documents.append({
                "id": doc_id,
                "title": file_path.stem.replace("_", " ").replace("-", " ").title(),
                "content": chunk,
                "source": str(relative_path),
                "source_url": blob_url,
                "category": _infer_category(file_path),
                "chunk_id": f"{file_path.stem}_{idx}",
                "created_at": datetime.now(timezone.utc).isoformat(),
                # content_vector is generated automatically by integrated vectorization
            })

    if not documents:
        print("  No documents found to ingest.")
        return

    # Batch upload (max 1000 per batch)
    batch_size = 1000
    total_uploaded = 0

    for i in range(0, len(documents), batch_size):
        batch = documents[i : i + batch_size]
        result = search_client.upload_documents(documents=batch)
        succeeded = sum(1 for r in result if r.succeeded)
        total_uploaded += succeeded
        print(f"  Batch {i // batch_size + 1}: {succeeded}/{len(batch)} indexed")

    print(f"  Total: {total_uploaded}/{len(documents)} chunks indexed")
    print()
    print("=== Ingestion complete! ===")


def _infer_category(path: Path) -> str:
    """Infer document category from directory structure."""
    path_str = str(path).lower()
    if "polic" in path_str or "governance" in path_str or "responsible" in path_str or "checklist" in path_str:
        return "policy"
    if "technical" in path_str or "guide" in path_str or "architecture" in path_str:
        return "technical"
    if "case-stud" in path_str or "roadmap" in path_str or "adoption" in path_str:
        return "case-study"
    if "hr" in path_str:
        return "hr"
    return "general"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest documents into AI Search")
    parser.add_argument("--source", type=Path, default=Path("./sample_data"))
    args = parser.parse_args()

    if not args.source.exists():
        print(f"Source directory not found: {args.source}")
        print("Create sample_data/ with .txt or .md files to ingest.")
    else:
        ingest_directory(args.source)
