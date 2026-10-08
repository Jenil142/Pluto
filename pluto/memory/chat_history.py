import sqlite3
import os
import asyncio
from datetime import datetime
from google import genai
from google.genai import types
from ..config import MEMORY_MODEL, GEMINI_API_KEY

DATABASE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "chat_history.db")
MEMORY_VAULT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "memory_vault")

# How many recent messages to feed to the summarizer
MAX_MESSAGES_TO_SUMMARIZE = 100

SUMMARY_PROMPT = """
You are the memory filter for an AI assistant called Pluto.

You will receive a raw conversation between Jenil (the user) and Pluto.
Your job is to extract ONLY the information that has long-term value.

KEEP (these are worth remembering):
- Facts about Jenil (preferences, habits, goals, schedule, location)
- Technical decisions (tools chosen, architecture decided, configs set)
- Completed tasks and their outcomes
- Ongoing or unfinished tasks
- Problems encountered and how they were solved
- Explicit instructions ("from now on do X", "always do Y", "never do Z")

DISCARD (these are noise):
- Greetings, small talk, thank yous
- Debugging back-and-forth that was already resolved
- Repeated or redundant information
- One-time questions that have no future relevance
- Error messages that were already fixed

OUTPUT FORMAT:
Write a structured briefing for Pluto using these sections. Skip any section that has no entries.

## Timeline
- A chronological summary of events, milestones, or conversations that occurred during this session

## Key Facts
- Bullet points of important facts about Sir

## Completed Tasks
- What was done and the outcome

## Ongoing Work
- Tasks that are in progress or planned

## Decisions Made
- Technical or personal decisions that should persist

## Standing Instructions
- Rules or preferences Sir has set for Pluto
"""

summarizer_client = genai.Client(api_key=GEMINI_API_KEY)


def _get_connection():
    """Returns a connection to the SQLite database, creating it if needed."""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            session_id TEXT DEFAULT 'main'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            summary TEXT NOT NULL,
            messages_summarized INTEGER NOT NULL,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            session_id TEXT DEFAULT 'main'
        )
    """)
    
    # Safe migration: Add session_id column to existing tables if missing
    try:
        conn.execute("ALTER TABLE messages ADD COLUMN session_id TEXT DEFAULT 'main'")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        conn.execute("ALTER TABLE summaries ADD COLUMN session_id TEXT DEFAULT 'main'")
    except sqlite3.OperationalError:
        pass  # Column already exists

    conn.commit()
    return conn


def save_message(role, content, session_id="main"):
    """Saves a single message (user or model) to the database."""
    conn = _get_connection()
    try:
        conn.execute(
            "INSERT INTO messages (role, content, timestamp, session_id) VALUES (?, ?, ?, ?)",
            (role, content, datetime.now().isoformat(), session_id)
        )
        conn.commit()
    finally:
        conn.close()

def save_messages(messages, session_id="main"):
    """Saves a list of (role, content, timestamp) tuples to the database."""
    conn = _get_connection()
    messages_with_session = [(r, c, t, session_id) for r, c, t in messages]
    try:
        conn.executemany(
            "INSERT INTO messages (role, content, timestamp, session_id) VALUES (?, ?, ?, ?)",
            messages_with_session
        )
        conn.commit()
    finally:
        conn.close()


def load_recent_messages(limit=MAX_MESSAGES_TO_SUMMARIZE, session_id="main"):
    """Loads the last N messages as raw text for summarization."""
    conn = _get_connection()
    try:
        cursor = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit)
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    rows.reverse()
    return rows


async def generate_summary(session_id="main"):
    """Uses the memory model to summarize recent conversation history for a session."""
    rows = load_recent_messages(limit=MAX_MESSAGES_TO_SUMMARIZE, session_id=session_id)

    if not rows:
        return None

    # Fetch the last summary to carry forward long-term memory
    previous_summary = load_latest_summary(session_id)

    # Build the conversation transcript for the summarizer
    transcript = ""
    
    # Inject the previous summary at the top if it exists
    if previous_summary:
        transcript += f"=== PREVIOUS SESSION SUMMARY ===\n{previous_summary}\n\n=== NEW MESSAGES ===\n"

    for role, content in rows:
        speaker = "Jenil" if role == "user" else "Pluto"
        transcript += f"{speaker}: {content}\n"

    try:
        response = await asyncio.to_thread(
            summarizer_client.models.generate_content,
            model=MEMORY_MODEL,
            contents=transcript,
            config=types.GenerateContentConfig(
                system_instruction=SUMMARY_PROMPT
            )
        )

        summary = response.text.strip()
        
        # Note: Cognee removed to prevent 40s blocking delays. 
        # Compaction in SQLite handles long term state perfectly.

        # Save the summary to the database
        conn = _get_connection()
        try:
            conn.execute(
                "INSERT INTO summaries (summary, messages_summarized, timestamp, session_id) VALUES (?, ?, ?, ?)",
                (summary, len(rows), datetime.now().isoformat(), session_id)
            )
            conn.commit()
        finally:
            conn.close()
            
        # Write the compacted summary to the Markdown Vault
        try:
            os.makedirs(MEMORY_VAULT_PATH, exist_ok=True)
            md_path = os.path.join(MEMORY_VAULT_PATH, f"{session_id}.md")
            with open(md_path, "w") as f:
                f.write(f"# Memory Vault: {session_id}\n\n")
                f.write(summary)
        except Exception as vault_err:
            print(f"[System]: Failed to write memory vault markdown - {vault_err}")

        return summary

    except Exception as e:
        print(f"[System]: Could not generate conversation summary - {e}")
        return None


def load_latest_summary(session_id="main"):
    """Loads the most recent conversation summary from the database for a session."""
    conn = _get_connection()
    try:
        cursor = conn.execute(
            "SELECT summary FROM summaries ORDER BY id DESC LIMIT 1"
        )
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def get_message_count(session_id="main"):
    """Returns the total number of messages stored for a session."""
    conn = _get_connection()
    try:
        cursor = conn.execute("SELECT COUNT(*) FROM messages")
        return cursor.fetchone()[0]
    finally:
        conn.close()


def get_messages_since_last_summary(session_id="main"):
    """Returns how many new messages exist since the last summary was generated for a session."""
    conn = _get_connection()
    try:
        cursor = conn.execute("SELECT messages_summarized FROM summaries WHERE session_id = ? ORDER BY id DESC LIMIT 1", (session_id,))
        row = cursor.fetchone()
        last_summarized = row[0] if row else 0

        cursor = conn.execute("SELECT COUNT(*) FROM messages WHERE session_id = ?", (session_id,))
        total = cursor.fetchone()[0]

        return total - last_summarized
    finally:
        conn.close()


def clear_history(session_id=None):
    """Deletes all stored messages and summaries. If session_id is provided, deletes only that session."""
    conn = _get_connection()
    try:
        if session_id:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM summaries WHERE session_id = ?", (session_id,))
        else:
            conn.execute("DELETE FROM messages")
            conn.execute("DELETE FROM summaries")
        conn.commit()
    finally:
        conn.close()
