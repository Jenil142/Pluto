import threading

_pending_command = None
_confirmation_result = False
_confirmation_event = threading.Event()

def request_confirmation(command: str) -> bool:
    global _pending_command, _confirmation_result
    
    _pending_command = command
    _confirmation_event.clear()
    
    # Block the current thread (the Gemini tool worker) for up to 60 seconds
    has_response = _confirmation_event.wait(timeout=60.0)
    
    _pending_command = None
    
    if has_response:
        return _confirmation_result
    return False

def get_pending_command():
    return _pending_command

def resolve_confirmation(allow: bool):
    global _confirmation_result
    _confirmation_result = allow
    _confirmation_event.set()
