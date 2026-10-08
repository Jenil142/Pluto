import asyncio
import cognee
from google import genai
from google.genai import types
from ..config import MEMORY_MODEL, GEMINI_API_KEY
from .prompts import MEMORY_SYSTEM_PROMPT

memory_client = genai.Client(api_key=GEMINI_API_KEY)

async def recall_memory(query: str):
    try:
        results = await cognee.recall(query, only_context=True)
        if not results:
            return None

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

        return "\n".join(list(dict.fromkeys(memory_text)))
    except Exception as e:
        print("[Memory] Recall error:", e)
        return None

async def process_memory(user_input: str):
    try:
        response = await asyncio.to_thread(
            memory_client.models.generate_content,
            model=MEMORY_MODEL,
            contents=user_input,
            config=types.GenerateContentConfig(system_instruction=MEMORY_SYSTEM_PROMPT)
        )

        result = response.text.strip()
        if result.startswith("REMEMBER:"):
            memory = result[len("REMEMBER:"):].strip()
            if memory:
                await cognee.remember(memory)
                print(f"\r[Memory] Saved: {memory}\nYou: ", end="", flush=True)
        elif result != "IGNORE":
            print("[Memory] Unexpected response:", result)
    except Exception as e:
        print("[Memory] Write error:", e)