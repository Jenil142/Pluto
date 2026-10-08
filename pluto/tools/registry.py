from google.genai import types
from .datetime_tool import datetime_function_declaration, get_current_datetime
from .terminal_tool import terminal_function_declaration, execute_terminal_command
from .calendar_tool import (
    get_upcoming_events_declaration, get_upcoming_events,
    create_calendar_event_declaration, create_calendar_event,
    delete_calendar_event_declaration, delete_calendar_event,
    create_task_deadline_declaration, create_task_deadline
)
from .web_search_tool import search_web_declaration, search_web
from .browser_tool import (
    browser_task_declaration, execute_browser_task,
    list_sessions_declaration, list_browser_sessions
)

# 1. Define tools for Gemini
pluto_tools = types.Tool(
    function_declarations=[
        datetime_function_declaration,
        terminal_function_declaration,
        get_upcoming_events_declaration,
        create_calendar_event_declaration,
        delete_calendar_event_declaration,
        create_task_deadline_declaration,
        search_web_declaration,
        browser_task_declaration,
        list_sessions_declaration,
    ]
)

# 2. Map tool names to their execution logic
TOOL_EXECUTORS = {
    "get_current_datetime": get_current_datetime,
    "execute_terminal_command": execute_terminal_command,
    "get_upcoming_events": get_upcoming_events,
    "create_calendar_event": create_calendar_event,
    "delete_calendar_event": delete_calendar_event,
    "create_task_deadline": create_task_deadline,
    "search_web": search_web,
    "execute_browser_task": execute_browser_task,
    "list_browser_sessions": list_browser_sessions,
}