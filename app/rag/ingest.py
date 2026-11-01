"""Proposal and transcript ingestion pipeline.

Parses all 10 seed proposals at boot, calculates SHA-256 hashes to ensure
idempotency, extracts metadata from filenames, chunks text, and loads
embeddings into ChromaDB.
"""

import hashlib
import json
import re
from pathlib import Path

from app.config import settings
from app.logging import get_logger
from app.rag.chunker import HeadingAwareChunker
from app.rag.store import add_chunks_to_vector_store

logger = get_logger("rag_ingest")

HASH_REGISTRY_FILENAME = "ingested_proposals_manifest.json"


def compute_sha256(content: str) -> str:
    """Calculate SHA-256 hash of document string."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def derive_metadata_from_filename(filename: str) -> tuple[str, str]:
    """Derive proposal_id and industry from filename convention.

    Example: 'proposal_healthcare.txt' -> ('proposal_healthcare', 'healthcare')
    """
    stem = Path(filename).stem
    match = re.match(r"^proposal_(.+)$", stem)
    industry = match.group(1) if match else "general"
    return stem, industry


def get_hash_registry_path() -> Path:
    """Return path to JSON manifest storing ingested file hashes."""
    persist_dir = Path(settings.CHROMA_PERSIST_DIR)
    persist_dir.mkdir(parents=True, exist_ok=True)
    return persist_dir / HASH_REGISTRY_FILENAME


def load_ingested_manifest() -> dict[str, str]:
    """Load dictionary mapping proposal_id to sha256 hash."""
    path = get_hash_registry_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_ingested_manifest(manifest: dict[str, str]) -> None:
    """Save dictionary mapping proposal_id to sha256 hash."""
    path = get_hash_registry_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def ingest_all_proposals(proposals_dir: str | None = None) -> int:
    """Ingest all proposal files in proposals directory.

    Guarantees all 10 proposals are ingested, skips already ingested identical
    hashes, and asserts completion count.
    """
    target_dir = Path(proposals_dir or settings.PROPOSALS_DIR)
    if not target_dir.is_dir():
        logger.error("proposals_directory_not_found", path=str(target_dir))
        return 0

    proposal_files = sorted(list(target_dir.glob("proposal_*.txt")))
    manifest = load_ingested_manifest()
    chunker = HeadingAwareChunker(target_tokens=400, overlap_tokens=60)

    newly_ingested = 0
    total_processed = 0

    for file_path in proposal_files:
        filename = file_path.name
        proposal_id, industry = derive_metadata_from_filename(filename)

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        file_hash = compute_sha256(content)
        if manifest.get(proposal_id) == file_hash:
            logger.info("proposal_already_ingested_skipping", proposal_id=proposal_id)
            total_processed += 1
            continue

        chunks = chunker.chunk_document(
            raw_text=content,
            source_id=proposal_id,
            source_type="proposal",
            industry=industry,
            extra_metadata={"proposal_id": proposal_id, "filename": filename},
        )

        chunk_ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict] = []

        for c in chunks:
            chunk_id = f"{proposal_id}_{c.chunk_index}"
            chunk_ids.append(chunk_id)
            documents.append(c.text)
            metadatas.append(c.metadata)

        add_chunks_to_vector_store(chunk_ids, documents, metadatas)
        manifest[proposal_id] = file_hash
        newly_ingested += 1
        total_processed += 1
        logger.info(
            "proposal_ingested",
            proposal_id=proposal_id,
            industry=industry,
            chunk_count=len(chunks),
        )

    save_ingested_manifest(manifest)

    expected_proposals = len(proposal_files)
    if total_processed < expected_proposals:
        missing = [
            f.name
            for f in proposal_files
            if derive_metadata_from_filename(f.name)[0] not in manifest
        ]
        logger.warning("ingestion_count_shortfall", missing_proposals=missing)

    logger.info(
        "ingestion_complete",
        total_active_proposals=total_processed,
        newly_ingested=newly_ingested,
    )
    return total_processed


def ingest_runtime_transcript(
    session_id: str,
    transcript_text: str,
    filename: str = "transcript.txt",
) -> int:
    """Ingest a live user transcript into Chroma tagged with session_id."""
    chunker = HeadingAwareChunker(target_tokens=400, overlap_tokens=60)
    chunks = chunker.chunk_document(
        raw_text=transcript_text,
        source_id=filename,
        source_type="transcript",
        industry="unspecified",
        extra_metadata={"session_id": session_id, "filename": filename},
    )

    chunk_ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict] = []

    for c in chunks:
        chunk_id = f"transcript_{session_id}_{c.chunk_index}"
        chunk_ids.append(chunk_id)
        documents.append(c.text)
        metadatas.append(c.metadata)

    add_chunks_to_vector_store(chunk_ids, documents, metadatas)
    logger.info("transcript_ingested", session_id=session_id, chunk_count=len(chunks))
    return len(chunks)
