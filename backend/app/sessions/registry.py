from threading import Lock
from backend.app.models.schemas import CreateSessionRequest
from backend.app.sessions.code_generator import generate_session_code
from backend.app.sessions.session import Session

_sessions: dict[str, Session] = {}
_session_lock = Lock()

def get_or_create_session(session_id: str) -> Session:
    if session_id not in _sessions:
        _sessions[session_id] = Session(session_id)
    return _sessions[session_id]

def session_exists(session_id: str) -> bool:
    return session_id in _sessions

def get_session(session_id: str) -> Session | None:
    return _sessions.get(session_id)

def create_session(request: CreateSessionRequest | None = None) -> Session:
    request = request if request is not None else CreateSessionRequest()
    # Sync routes run in threads; checking and reserving a code must be atomic.
    with _session_lock:
        for _ in range(10):
            session_id = generate_session_code()
            if session_id not in _sessions:
                print(f"Creating session with password: {request.password}")
                session = Session(session_id, request.host_name, request.settings, request.password)
                _sessions[session_id] = session
                return session
    raise RuntimeError("Could not allocate a join code. Try again.")
