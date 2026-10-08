from datetime import datetime
from google.genai import types

def get_current_datetime(**kwargs):
    """Returns the current date and time. Ignores any hallucinated arguments."""
    return datetime.now().strftime("%A, %B %d, %Y - %I:%M %p")

datetime_function_declaration = types.FunctionDeclaration(
    name="get_current_datetime",
    description="Returns the current date and time. Use when the user asks about the current time or date.",
    parameters=None
)