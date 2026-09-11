from google import genai
from google.genai import types
from dotenv import load_dotenv
import os
import cognee
import asyncio

load_dotenv()

# ==========================================
# Configuration
# ==========================================

PLUTO_MODEL = "gemini-3.5-flash-lite"
MEMORY_MODEL = "gemini-3.1-flash-lite"

# ==========================================
# Gemini client
# ==========================================

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

# ==========================================
# Pluto personality
# ==========================================

system_prompt = """
You are Pluto, a personal AI assistant that works for Jenil.

Always address Jenil as "Sir".
You have a personality inspired by JARVIS from Iron Man.
Be concise, precise, professional, and helpful.
Speak only when necessary.

Important:
Use long-term memory when relevant, but do not mention
the memory system to the user.
"""

# ==========================================
# Pluto chat session
# ==========================================

chat = client.chats.create(
    model=PLUTO_MODEL,
    config=types.GenerateContentConfig(
        system_instruction=system_prompt
    )
)

# ==========================================
# Memory trigger keywords
# ==========================================

MEMORY_RECALL_TRIGGERS = [
    "remember",
    "don't forget",
    "do not forget",
    "my name",
    "my project",
    "my projects",
    "what am i building",
    "what am i working on",
    "what project",
    "what do you know about me",
    "what do you remember about me",
    "what are my preferences",
    "what do i prefer",
    "what is my favorite",
]


# ==========================================
# Memory writing triggers
# ==========================================

MEMORY_WRITE_TRIGGERS = [
    "remember that",
    "remember this",
    "don't forget that",
    "do not forget that",
    "i prefer",
    "i like",
    "i dislike",
    "my favorite is",
    "i use",
    "i am using",
    "i'm using",
    "i am building",
    "i'm building",
    "i am working on",
    "i'm working on",
    "from now on",
    "my goal is",
    "my goal",
    "i want to build",
]


# ==========================================
# Memory retrieval gate
# ==========================================

def might_need_memory(text):
    text = text.lower()

    return any(
        trigger in text
        for trigger in MEMORY_RECALL_TRIGGERS
    )


# ==========================================
# Memory writing gate
# ==========================================

def might_contain_memory(text):
    text = text.lower()

    return any(
        trigger in text
        for trigger in MEMORY_WRITE_TRIGGERS
    )


# ==========================================
# Recall permanent memory
# ==========================================

async def recall_memory(query):
    try:
        results = await cognee.recall(
            query,
            only_context=True
        )

        if not results:
            return None

        # Convert Cognee results into clean text
        memory_text = []

        for result in results:
            if hasattr(result, "text") and result.text:
                memory_text.append(result.text)

            elif isinstance(result, str):
                memory_text.append(result)

            elif isinstance(result, dict):
                if "text" in result:
                    memory_text.append(str(result["text"]))

                elif "value" in result:
                    memory_text.append(str(result["value"]))

        if not memory_text:
            return None

        unique_memory = list(dict.fromkeys(memory_text))
        return "\n".join(unique_memory)

    except Exception as e:
        print("[Memory] Recall error:", e)
        return None

# ==========================================
# Process and save memory
# ==========================================

async def process_memory(user_input):

    if not might_contain_memory(user_input):
        return

    memory_system_prompt = """
You are Pluto's memory manager.

Determine whether the user's message contains information
that should be remembered across future conversations.

REMEMBER:
- Personal preferences
- Long-term projects
- Long-term goals
- Technical environment
- Persistent facts about Jenil
- Important decisions
- Explicit requests to remember something

IGNORE:
- Greetings
- Small talk
- Temporary questions
- One-time calculations
- Temporary statements
- Information with no future value

Return exactly one of:

REMEMBER: <concise memory statement>

or:

IGNORE
"""

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=MEMORY_MODEL,
            contents=user_input,
            config=types.GenerateContentConfig(
                system_instruction=memory_system_prompt
            )
        )

        result = response.text.strip()

        if result.startswith("REMEMBER:"):

            memory = result[len("REMEMBER:"):].strip()

            if memory:
                await cognee.remember(memory)

                print("[Memory] Saved:", memory)

        elif result == "IGNORE":

            pass

        else:

            print("[Memory] Unexpected response:", result)

    except Exception as e:

        print("[Memory] Write error:", e)


# ==========================================
# Generate Pluto response
# ==========================================

async def generate_response(prompt):
    """
    Run the synchronous Gemini call without blocking
    the asyncio event loop.
    """

    return await asyncio.to_thread(
        chat.send_message,
        prompt
    )


# ==========================================
# Main Pluto loop
# ==========================================

async def main():

    background_tasks = set()

    while True:

        user_input = await asyncio.to_thread(
            input,
            "You: "
        )

        if user_input.lower() in ("exit", "quit"):
            break

        # ==================================
        # 1. Recall memory only when useful
        # ==================================

        memories = None

        if might_need_memory(user_input):

            memories = await recall_memory(user_input)

        # ==================================
        # 2. Prepare prompt
        # ==================================

        if memories:

            prompt = f"""
Relevant information from your long-term memory:

{memories}

Current user message:

{user_input}
"""

        else:

            prompt = user_input

        # ==================================
        # 3. Generate Pluto response
        # ==================================

        response = await generate_response(prompt)

        print("Pluto:", response.text)

        # ==================================
        # 4. Save memory in background
        # ==================================

        task = asyncio.create_task(
            process_memory(user_input)
        )

        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)


# ==========================================
# Start Pluto
# ==========================================

if __name__ == "__main__":
    asyncio.run(main())