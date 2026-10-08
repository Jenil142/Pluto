import asyncio
import sys
import logging

logger = logging.getLogger("pluto.core")

_orig_print = print
def safe_print(*args, **kwargs):
    try:
        _orig_print(*args, **kwargs)
        sys.stdout.flush()
    except Exception:
        pass

print = safe_print
from google import genai
from google.genai import types

from .config import PLUTO_MODEL, GEMINI_API_KEY
from .prompts import PLUTO_SYSTEM_PROMPT
from .tools.registry import pluto_tools, TOOL_EXECUTORS
from datetime import datetime
from .memory.chat_history import save_messages, get_message_count, generate_summary, load_latest_summary, get_messages_since_last_summary, load_recent_messages

# Build system prompt with conversation memory
def build_system_prompt():
    """Injects the conversation summary into the system prompt if available."""
    msg_count = get_message_count()

    if msg_count == 0:
        print("[System]: No previous conversations found. Starting fresh.")
        return PLUTO_SYSTEM_PROMPT

    summary = load_latest_summary()

    if summary:
        print(f"[System]: Conversation memory loaded ({msg_count} messages summarized).")
        return f"""{PLUTO_SYSTEM_PROMPT}

Here is a summary of your previous conversations with Sir. Use this to maintain continuity:

{summary}
"""
    else:
        return PLUTO_SYSTEM_PROMPT

client = genai.Client(api_key=GEMINI_API_KEY)

active_sessions = {}

def get_or_create_chat_session(session_id="main"):
    """Dynamically initializes or retrieves an isolated Chat object per session."""
    if session_id in active_sessions:
        return active_sessions[session_id]

    print(f"[System]: Initializing new isolated memory vault for session: {session_id}")
    system_prompt_with_memory = build_system_prompt()
    
    # Load recent raw history from SQLite to prepopulate Gemini's short-term memory
    raw_history = load_recent_messages(50, session_id=session_id)
    chat_history = []
    if raw_history:
        for role, content in raw_history:
            chat_history.append(
                types.Content(role=role, parts=[types.Part.from_text(text=content)])
            )

    chat = client.chats.create(
        model=PLUTO_MODEL,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt_with_memory,
            tools=[pluto_tools],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
        ),
        history=chat_history if chat_history else None
    )
    
    active_sessions[session_id] = chat
    return chat

FATAL_ERRORS = ["402", "401", "403", "billing", "credentials", "API_KEY"]
RETRYABLE_ERRORS = ["503", "429", "name resolution", "timed out", "Connection", "UNAVAILABLE", "RESOURCE_EXHAUSTED"]

async def send_message_with_retry(chat, prompt_or_parts, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await asyncio.to_thread(chat.send_message, prompt_or_parts)
        except Exception as e:
            error_str = str(e)

            # Fatal errors: no point retrying
            if any(code in error_str for code in FATAL_ERRORS):
                print(f"\n[Fatal Error]: {e}")
                print("[Action Required]: Check your API key or billing at https://ai.studio/projects\n")
                return None

            # Retryable errors: back off and try again
            is_retryable = any(code in error_str for code in RETRYABLE_ERRORS)

            if is_retryable and attempt < max_retries - 1:
                wait_time = round(1.5 ** (attempt + 1), 1)  # 1.5s, 2.25s
                print(f"\n[System]: Temporary error ({e}). Retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(wait_time)
                continue

            # Unknown error or exhausted retries
            print(f"\n[System Error]: API request failed after {attempt + 1} attempts - {e}\n")
            return None
    return None

async def generate_response(prompt, session_id="main"):
    chat = get_or_create_chat_session(session_id)
    return await send_message_with_retry(chat, prompt)

def get_function_calls(response):
    function_calls = []

    for candidate in response.candidates:
        for part in candidate.content.parts:
            if part.function_call:
                function_calls.append(part.function_call)

    return function_calls

async def run_tool_loop(response, session_id="main"):
    chat = get_or_create_chat_session(session_id)

    while True:

        function_calls = get_function_calls(response)

        if not function_calls:
            return response

        function_response_parts = []

        for function_call in function_calls:

            result = await execute_tool(function_call)

            function_response_parts.append(
                types.Part.from_function_response(
                    name=function_call.name,
                    response={"result": result},
                )
            )

        response = await send_message_with_retry(chat, function_response_parts)
        if not response:
            return None

async def execute_tool(function_call):
    tool_name = function_call.name
    tool_args = function_call.args
    
    print(f"[Pluto is thinking... executing {tool_name}({tool_args})]")
    
    executor = TOOL_EXECUTORS.get(tool_name)

    if executor is None:
        return {
            "error": f"Unknown tool: {tool_name}"
        }

    try:
        result = await asyncio.to_thread(
            executor,
            **tool_args
        )

        return result

    except Exception as e:
        return {
            "error": f"Tool '{tool_name}' failed: {e}"
        }

async def main():
    background_tasks = set()
    session_messages = []

    while True:
        user_input = await asyncio.to_thread(input, "You: ")
        if user_input.lower() in ("exit", "quit"):
            print("\n[System]: Saving session memory. Please wait...")
            if session_messages:
                save_messages(session_messages)
                
            new_msgs = get_messages_since_last_summary()
            if new_msgs > 0:
                await generate_summary()
            print("[System]: Session saved. Goodbye!")
            break

        # 1. Response
        response = await generate_response(user_input, session_id="main")
        if not response:
            continue

        # 3. Tool Execution
        response = await run_tool_loop(response, session_id="main")
        if response and response.text:
            print("Pluto:", response.text)

            session_messages.append(("user", user_input, datetime.now().isoformat()))
            session_messages.append(("model", response.text, datetime.now().isoformat()))