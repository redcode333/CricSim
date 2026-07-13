"""
sessions.py  —  in-memory session store for API game states.
"""
import uuid
from typing import Optional

_store: dict[str, dict] = {}


def new_session(data: dict) -> str:
    sid = str(uuid.uuid4())[:8]
    _store[sid] = data
    return sid


def get(sid: str) -> Optional[dict]:
    return _store.get(sid)


def update(sid: str, patch: dict):
    if sid in _store:
        _store[sid].update(patch)


def delete(sid: str):
    _store.pop(sid, None)
