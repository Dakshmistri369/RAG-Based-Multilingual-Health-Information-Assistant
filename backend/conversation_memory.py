"""
backend/conversation_memory.py
================================
Simple in-memory session-based conversation history for SwasthyaSetu AI.

Implementation: Python dict keyed by session_id.
Each session stores a list of {question, answer} turn dicts.

PRODUCTION NOTE:
-----------------
This in-memory dict is appropriate for a hackathon demo running on a single
process. In production, replace this with:
  - Redis (redis-py) for multi-process / multi-instance deployment
  - SQLite or PostgreSQL with SQLAlchemy for persistent history across restarts
  - A dedicated session store service if scaling horizontally

The interface (get_history, update_history, clear_history) is designed to be
drop-in replaceable: changing the backend storage only requires updating these
three functions, with no changes needed in rag_chain.py or main.py.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TypedDict

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from config import MAX_HISTORY_TURNS

logger = logging.getLogger(__name__)


# ── Type definition ───────────────────────────────────────────────────────────

class ConversationTurn(TypedDict):
    question: str
    answer: str


# ── In-memory session store ───────────────────────────────────────────────────
# Module-level dict — shared across all requests in the same process.
# PRODUCTION TODO: Replace with Redis client here.
_sessions: dict[str, list[ConversationTurn]] = {}


# ── Public interface ──────────────────────────────────────────────────────────

def get_history(session_id: str) -> list[ConversationTurn]:
    """
    Retrieve the conversation history for a given session.

    Args:
        session_id: Unique identifier for the user's session.

    Returns:
        List of ConversationTurn dicts (empty list for new sessions).
    """
    return _sessions.get(session_id, [])


def update_history(session_id: str, question: str, answer: str) -> None:
    """
    Append a new turn to the session history, trimming to MAX_HISTORY_TURNS.

    Args:
        session_id: Unique identifier for the user's session.
        question:   The user's question text.
        answer:     The assistant's response text.
    """
    if session_id not in _sessions:
        _sessions[session_id] = []

    _sessions[session_id].append(
        ConversationTurn(question=question, answer=answer)
    )

    # Trim to last MAX_HISTORY_TURNS turns to prevent unbounded memory growth
    if len(_sessions[session_id]) > MAX_HISTORY_TURNS:
        _sessions[session_id] = _sessions[session_id][-MAX_HISTORY_TURNS:]
        logger.debug(
            "Session '%s' trimmed to last %d turns.", session_id, MAX_HISTORY_TURNS
        )

    logger.debug(
        "Session '%s' updated — now has %d turn(s).",
        session_id, len(_sessions[session_id]),
    )


def clear_history(session_id: str) -> bool:
    """
    Remove all conversation history for a given session.

    Args:
        session_id: Unique identifier for the user's session.

    Returns:
        True if the session existed and was cleared, False if it didn't exist.
    """
    if session_id in _sessions:
        del _sessions[session_id]
        logger.info("Session '%s' cleared.", session_id)
        return True
    return False


def get_all_session_ids() -> list[str]:
    """Return a list of all active session IDs. Useful for monitoring."""
    return list(_sessions.keys())


def get_session_count() -> int:
    """Return the number of active sessions."""
    return len(_sessions)


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    print("Testing conversation memory...")

    # Test basic operations
    sid = "test-session-001"

    # New session should return empty history
    assert get_history(sid) == [], "New session should have empty history"
    print("✓ New session returns empty history")

    # Add some turns
    update_history(sid, "What is dengue?", "Dengue is a mosquito-borne disease...")
    update_history(sid, "How to prevent it?", "Use mosquito nets and repellents...")
    history = get_history(sid)
    assert len(history) == 2, f"Expected 2 turns, got {len(history)}"
    print(f"✓ History has {len(history)} turns after 2 updates")

    # Test trimming (add MAX_HISTORY_TURNS + 2 turns)
    for i in range(MAX_HISTORY_TURNS + 2):
        update_history(sid, f"Question {i}", f"Answer {i}")
    history = get_history(sid)
    assert len(history) == MAX_HISTORY_TURNS, (
        f"Expected {MAX_HISTORY_TURNS} turns after trim, got {len(history)}"
    )
    print(f"✓ History correctly trimmed to {MAX_HISTORY_TURNS} turns")

    # Test clear
    result = clear_history(sid)
    assert result is True, "clear_history should return True for existing session"
    assert get_history(sid) == [], "History should be empty after clear"
    print("✓ Session cleared successfully")

    # Clear non-existent session
    result = clear_history("non-existent-session")
    assert result is False, "clear_history should return False for missing session"
    print("✓ clear_history returns False for non-existent session")

    print("\n✓ All conversation memory tests passed.")
