"""Unit tests for all ExecutionStore implementations."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from backend.storage import InMemoryExecutionStore, JsonExecutionStore


def _make_record(execution_id: str = "exec-1", agent_name: str = "math") -> dict:
    return {
        "execution_id": execution_id,
        "agent_name": agent_name,
        "status": "completed",
        "output": "Result: 10",
        "used_llm": False,
        "created_at": "2026-04-20T10:00:00+00:00",
        "context": {},
    }


class TestInMemoryStore:
    def test_save_and_list(self):
        store = InMemoryExecutionStore()
        record = _make_record()
        store.save(record)
        records = store.list_recent()
        assert len(records) == 1
        assert records[0]["execution_id"] == "exec-1"

    def test_list_returns_most_recent_first(self):
        store = InMemoryExecutionStore()
        store.save(_make_record("exec-1"))
        store.save(_make_record("exec-2"))
        records = store.list_recent()
        assert records[0]["execution_id"] == "exec-2"

    def test_list_respects_limit(self):
        store = InMemoryExecutionStore()
        for i in range(10):
            store.save(_make_record(f"exec-{i}"))
        assert len(store.list_recent(limit=3)) == 3

    def test_empty_store_returns_empty_list(self):
        store = InMemoryExecutionStore()
        assert store.list_recent() == []

    def test_save_returns_record(self):
        store = InMemoryExecutionStore()
        record = _make_record()
        returned = store.save(record)
        assert returned["execution_id"] == record["execution_id"]


class TestJsonStore:
    def test_save_and_list(self, tmp_path: Path):
        path = tmp_path / "test.json"
        store = JsonExecutionStore(path)
        store.save(_make_record("exec-1"))
        records = store.list_recent()
        assert len(records) == 1

    def test_persists_across_instances(self, tmp_path: Path):
        path = tmp_path / "test.json"
        JsonExecutionStore(path).save(_make_record("exec-1"))
        records = JsonExecutionStore(path).list_recent()
        assert records[0]["execution_id"] == "exec-1"

    def test_list_returns_most_recent_first(self, tmp_path: Path):
        path = tmp_path / "test.json"
        store = JsonExecutionStore(path)
        store.save(_make_record("exec-1"))
        store.save(_make_record("exec-2"))
        records = store.list_recent()
        assert records[0]["execution_id"] == "exec-2"

    def test_recovers_from_empty_file(self, tmp_path: Path):
        path = tmp_path / "test.json"
        path.write_text("", encoding="utf-8")
        store = JsonExecutionStore(path)
        assert store.list_recent() == []

    def test_recovers_from_corrupt_file(self, tmp_path: Path):
        path = tmp_path / "test.json"
        path.write_text("not json {{", encoding="utf-8")
        store = JsonExecutionStore(path)
        assert store.list_recent() == []

    def test_creates_parent_directory(self, tmp_path: Path):
        path = tmp_path / "nested" / "dir" / "test.json"
        store = JsonExecutionStore(path)
        store.save(_make_record())
        assert path.exists()
