"""Unit tests for ConversationalQAAgent verifying dynamic reasoning and dual-source RAG."""

import pytest
from app.agents.qa import ConversationalQAAgent


@pytest.mark.asyncio
async def test_qa_past_proposal_floor_monitoring():
    """Verify agent retrieves and reasons over historical manufacturing proposal."""
    qa = ConversationalQAAgent()
    reply = await qa.answer_question(
        query="what was the proposal for the floor monitoring",
        session_id="test_session_none",
    )
    assert "[proposal_manufacturing]" in reply
    assert "Redstone Manufacturing Co." in reply
    assert "$94,000" in reply
    assert "6 months" in reply or "Months 1-3" in reply
    assert "PRODUCTION FLOOR MONITORING SYSTEM" in reply


@pytest.mark.asyncio
async def test_qa_past_proposal_healthcare():
    """Verify agent retrieves past healthcare proposal when asked."""
    qa = ConversationalQAAgent()
    reply = await qa.answer_question(
        query="what was the proposal for healthcare",
        session_id="test_session_none",
    )
    assert "[proposal_healthcare]" in reply
    assert "HEALTHCARE" in reply.upper() or "PATIENT" in reply.upper()


@pytest.mark.asyncio
async def test_qa_transcript_deadline():
    """Verify agent extracts and reasons over transcript timeline and deadlines."""
    qa = ConversationalQAAgent()
    reply = await qa.answer_question(
        query="what was the deadline",
        session_id="test_session_none",
    )
    assert "[client_transcript]" in reply
    assert "Marcus Webb" in reply
    assert "Jenny Tran" in reply
    assert "Q3" in reply
    assert "Q4" in reply
    assert "Atlanta" in reply


@pytest.mark.asyncio
async def test_qa_transcript_budget():
    """Verify agent extracts and reasons over transcript budget and board approvals."""
    qa = ConversationalQAAgent()
    reply = await qa.answer_question(
        query="what is their budget range",
        session_id="test_session_none",
    )
    assert "[client_transcript]" in reply
    assert "$50,000" in reply
    assert "$120,000" in reply


@pytest.mark.asyncio
async def test_qa_transcript_stakeholder_jenny():
    """Verify agent identifies Jenny Tran and her operational role."""
    qa = ConversationalQAAgent()
    reply = await qa.answer_question(
        query="who is jenny",
        session_id="test_session_none",
    )
    assert "Jenny Tran" in reply
    assert "Operations Manager" in reply
    assert "Chicago" in reply or "Dallas" in reply


@pytest.mark.asyncio
async def test_qa_arbitrary_transcript_question_spreadsheets():
    """Verify dynamic dialogue extraction for arbitrary document questions (spreadsheets)."""
    qa = ConversationalQAAgent()
    reply = await qa.answer_question(
        query="how many hours do they spend on spreadsheets",
        session_id="test_session_none",
    )
    assert "[client_transcript]" in reply
    assert "four to five hours" in reply.lower() or "spreadsheet" in reply.lower()


@pytest.mark.asyncio
async def test_qa_arbitrary_transcript_question_consultants():
    """Verify dynamic dialogue extraction for arbitrary document questions (other consultants)."""
    qa = ConversationalQAAgent()
    reply = await qa.answer_question(
        query="what did Marcus say about other consultants",
        session_id="test_session_none",
    )
    assert "[client_transcript]" in reply
    assert "rip" in reply.lower() or "consultants" in reply.lower()
