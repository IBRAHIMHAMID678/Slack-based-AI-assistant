"""Standalone CLI script for indexing or re-indexing all proposal files into ChromaDB.

Usage:
    python scripts/ingest.py
"""

import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.logging import configure_logging, get_logger
from app.rag.ingest import ingest_all_proposals

configure_logging("INFO")
logger = get_logger("scripts_ingest")


def main() -> None:
    """Run proposal ingestion from CLI."""
    logger.info("starting_standalone_proposal_ingestion")
    count = ingest_all_proposals()
    print(f"\nSuccessfully verified/ingested {count} proposal documents.")
    assert count == 10, f"Expected 10 proposals, got {count}"
    print("Ingestion count assertion passed: 10/10 proposals verified.")


if __name__ == "__main__":
    main()
