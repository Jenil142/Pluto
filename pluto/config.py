import os
from dotenv import load_dotenv

load_dotenv()

PLUTO_MODEL = os.getenv("PLUTO_MODEL", "gemini-3.5-flash-lite")
MEMORY_MODEL = os.getenv("MEMORY_MODEL", "gemini-3.1-flash-lite")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PLUTO_API_TIMEOUT = int(os.getenv("PLUTO_API_TIMEOUT", "0"))