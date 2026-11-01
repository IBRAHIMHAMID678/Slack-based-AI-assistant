"""Headless smoke test running the full proposal generation pipeline in mock mode.

Usage:
    python scripts/smoke.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.db.migrate import init_db
from app.logging import configure_logging, get_logger
from app.orchestrator.pipeline import ProposalOrchestrator
from app.rag.ingest import ingest_all_proposals

configure_logging("INFO")
logger = get_logger("smoke_test")


class SmokeMockClient:
    """Mock client for smoke test headless execution."""

    def __init__(self) -> None:
        self.files_uploaded = []

    async def chat_postMessage(self, **kwargs):
        return {"ok": True, "ts": "1700000001.0001"}

    async def chat_update(self, **kwargs):
        return {"ok": True}

    async def files_upload_v2(self, **kwargs):
        self.files_uploaded.append(kwargs)
        return {"ok": True, "file": {"id": "F_SMOKE_DOCX"}}


async def run_smoke_test() -> None:
    """Execute end-to-end headless flow and assert output DOCX exists."""
    logger.info("starting_headless_smoke_test")

    # Step 1: Initialize Database
    init_db()

    # Step 2: Ensure all 10 proposals are ingested
    ingest_all_proposals()

    # Step 3: Load real discovery transcript
    transcript_file = ROOT_DIR / "client_transcript.txt"
    if not transcript_file.exists():
        raise FileNotFoundError(f"Missing {transcript_file}")

    with open(transcript_file, "r", encoding="utf-8") as f:
        transcript_text = f.read()

    orchestrator = ProposalOrchestrator()
    client = SmokeMockClient()

    channel_id = "C_SMOKE_TEST"
    thread_ts = "1700000000.9999"
    user_id = "U_SMOKE_USER"

    logger.info("submitting_transcript_to_orchestrator")
    await orchestrator.handle_transcript_upload(
        channel_id=channel_id,
        thread_ts=thread_ts,
        user_id=user_id,
        file_url="https://mock.slack.com/files/client_transcript.txt",
        filename="client_transcript.txt",
        client=client,
        raw_content_override=transcript_text,
    )

    logger.info("approving_draft_proposal")
    await orchestrator.handle_draft_approval(
        channel_id=channel_id,
        thread_ts=thread_ts,
        user_id=user_id,
        client=client,
    )

    # Step 4: Assert output DOCX exists and has non-zero size
    out_dir = ROOT_DIR / "out"
    docx_files = list(out_dir.glob("*.docx"))
    assert len(docx_files) >= 1, "Expected at least one generated DOCX proposal in out/"

    latest_docx = max(docx_files, key=lambda p: p.stat().st_mtime)
    file_size = latest_docx.stat().st_size
    assert file_size > 1000, f"Generated DOCX is suspiciously small: {file_size} bytes"

    print("\n" + "=" * 60)
    print("[SUCCESS] SMOKE TEST PASSED SUCCESSFULLY!")
    print(f"Generated Proposal: {latest_docx.name} ({file_size:,} bytes)")
    print("=" * 60 + "\n")


def main() -> None:
    asyncio.run(run_smoke_test())


if __name__ == "__main__":
    main()
