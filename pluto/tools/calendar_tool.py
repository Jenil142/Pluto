from datetime import datetime, timedelta, timezone
from google.genai import types
from .calendar_auth import get_calendar_service
from zoneinfo import ZoneInfo

def get_upcoming_events(max_results=10, **kwargs):
    """Fetches upcoming events from the user's primary calendar."""
    service = get_calendar_service()
    if not service:
        return "Error: Could not authenticate with Google Calendar."

    try:
        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])

        if not events:
            return "No upcoming events found."

        result_str = "Upcoming events (Times in IST):\n"
        for event in events:
            start_str = event["start"].get("dateTime", event["start"].get("date"))
            event_id = event.get("id")
            try:
                if "T" in start_str:
                    dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                    dt_ist = dt.astimezone(ZoneInfo("Asia/Kolkata"))
                    start = dt_ist.strftime("%A, %B %d at %I:%M %p (IST)")
                else:
                    start = f"{start_str} (All Day)"
            except Exception:
                start = start_str
                
            result_str += f"- [ID: {event_id}] {start}: {event['summary']}\n"
            
        return result_str
        
    except Exception as e:
        return f"An error occurred while fetching events: {e}"


def create_calendar_event(summary, start_time, end_time, description="", **kwargs):
    """Creates a new event on the user's primary calendar."""
    service = get_calendar_service()
    if not service:
        return "Error: Could not authenticate with Google Calendar."

    event = {
        'summary': summary,
        'description': description,
        'start': {'dateTime': start_time},
        'end': {'dateTime': end_time},
    }

    try:
        event = service.events().insert(calendarId='primary', body=event).execute()
        return f"Event created successfully: {event.get('summary')} at {event.get('htmlLink')}"
    except Exception as e:
        return f"An error occurred while creating the event: {e}"


def delete_calendar_event(event_id=None, query=None, **kwargs):
    """Deletes an event by its exact event_id or by searching a matching query."""
    service = get_calendar_service()
    if not service:
        return "Error: Could not authenticate with Google Calendar."

    try:
        if not event_id and query:
            # Search for events matching the query
            now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            events_result = service.events().list(
                calendarId="primary", q=query, timeMin=now, singleEvents=True, maxResults=5
            ).execute()
            events = events_result.get("items", [])
            if not events:
                return f"No upcoming events found matching query: '{query}'"
            if len(events) > 1:
                matches = ", ".join([f"'{e['summary']}' (ID: {e['id']})" for e in events])
                return f"Multiple events found matching '{query}': {matches}. Please specify the exact event_id."
            event_id = events[0]['id']
            
        elif not event_id:
            return "Error: You must provide either an event_id or a query to delete an event."

        service.events().delete(calendarId='primary', eventId=event_id).execute()
        return f"Successfully deleted event (ID: {event_id})."
    except Exception as e:
        return f"An error occurred while deleting the event: {e}"


def create_task_deadline(summary, due_time, description="", **kwargs):
    """Creates a task deadline as an all-day or 30-minute calendar event."""
    service = get_calendar_service()
    if not service:
        return "Error: Could not authenticate with Google Calendar."

    # Set deadline duration to 30 mins from due_time, or all-day if date only
    try:
        start_dt = datetime.fromisoformat(due_time.replace('Z', '+00:00'))
        end_dt = start_dt + timedelta(minutes=30)
        end_time = end_dt.isoformat()
    except Exception:
        # Fallback if date only
        end_time = due_time

    event = {
        'summary': f"[DEADLINE] {summary}",
        'description': description,
        'start': {'dateTime': due_time} if 'T' in due_time else {'date': due_time},
        'end': {'dateTime': end_time} if 'T' in due_time else {'date': due_time},
    }

    try:
        event = service.events().insert(calendarId='primary', body=event).execute()
        return f"Deadline task created: {event.get('summary')} (Link: {event.get('htmlLink')})"
    except Exception as e:
        return f"An error occurred while creating the task deadline: {e}"


# --- Gemini Tool Declarations ---

get_upcoming_events_declaration = types.FunctionDeclaration(
    name="get_upcoming_events",
    description="Fetches upcoming events from the user's Google Calendar.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "max_results": types.Schema(type="INTEGER", description="Maximum number of events to return. Defaults to 10.")
        }
    )
)

create_calendar_event_declaration = types.FunctionDeclaration(
    name="create_calendar_event",
    description="Creates a new event on the user's Google Calendar. Requires start and end times in RFC3339 format.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "summary": types.Schema(type="STRING", description="Title of the event."),
            "start_time": types.Schema(type="STRING", description="Start time in RFC3339 format (e.g., 2026-09-30T10:00:00+05:30)."),
            "end_time": types.Schema(type="STRING", description="End time in RFC3339 format."),
            "description": types.Schema(type="STRING", description="Optional description.")
        },
        required=["summary", "start_time", "end_time"]
    )
)

delete_calendar_event_declaration = types.FunctionDeclaration(
    name="delete_calendar_event",
    description="Deletes an event from the calendar using its event_id or a search query.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "event_id": types.Schema(type="STRING", description="The unique ID of the event to delete."),
            "query": types.Schema(type="STRING", description="Search query to find the event if ID is unknown.")
        }
    )
)

create_task_deadline_declaration = types.FunctionDeclaration(
    name="create_task_deadline",
    description="Creates a task deadline on the calendar.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "summary": types.Schema(type="STRING", description="Title of the task/deadline."),
            "due_time": types.Schema(type="STRING", description="Due time in RFC3339 format or YYYY-MM-DD."),
            "description": types.Schema(type="STRING", description="Optional description.")
        },
        required=["summary", "due_time"]
    )
)
