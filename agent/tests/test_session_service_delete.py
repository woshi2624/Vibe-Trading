"""SessionService deletion cleanup regressions."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.memory.persistent import PersistentMemory
from src.session.events import EventBus
from src.session.service import SessionService
from src.session.store import SessionStore


class _RecordingIndex:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    def index_session(self, session_id: str, title: str) -> None:
        del session_id, title

    def index_message(self, session_id: str, role: str, content: str) -> None:
        del session_id, role, content

    def delete_session(self, session_id: str) -> bool:
        self.deleted.append(session_id)
        return True


def test_delete_session_removes_session_scoped_memories(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    index = _RecordingIndex()
    monkeypatch.setattr("src.session.service.get_shared_index", lambda: index)

    memory_dir = tmp_path / "memory"
    service = SessionService(
        store=SessionStore(tmp_path / "sessions"),
        event_bus=EventBus(),
        runs_dir=tmp_path / "runs",
        memory_dir=memory_dir,
    )
    session = service.create_session("delete cleanup")

    pm = PersistentMemory(memory_dir=memory_dir)
    pm.add("owned-memory", "remove me", "project", session_id=session.session_id)
    pm.add("other-memory", "keep me", "project", session_id="other-session")
    pm.add("global-memory", "keep me too", "project")

    assert service.delete_session(session.session_id) is True

    assert service.store.get_session(session.session_id) is None
    assert index.deleted == [session.session_id]
    remaining = {entry.title for entry in PersistentMemory(memory_dir=memory_dir).list_entries()}
    assert remaining == {"other-memory", "global-memory"}


def test_delete_missing_session_does_not_remove_memories(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    index = _RecordingIndex()
    monkeypatch.setattr("src.session.service.get_shared_index", lambda: index)

    memory_dir = tmp_path / "memory"
    service = SessionService(
        store=SessionStore(tmp_path / "sessions"),
        event_bus=EventBus(),
        runs_dir=tmp_path / "runs",
        memory_dir=memory_dir,
    )
    PersistentMemory(memory_dir=memory_dir).add(
        "owned-memory",
        "still here",
        "project",
        session_id="missing-session",
    )

    assert service.delete_session("missing-session") is False

    remaining = {entry.title for entry in PersistentMemory(memory_dir=memory_dir).list_entries()}
    assert remaining == {"owned-memory"}
    assert index.deleted == []
