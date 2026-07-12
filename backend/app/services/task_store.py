from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock

from app.models import TaskRecord


class TaskStore:
    def __init__(self, root: Path, retention_hours: int) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.retention = timedelta(hours=retention_hours)
        self._lock = Lock()

    def directory(self, task_id: str) -> Path:
        return self.root / task_id

    def create(self, record: TaskRecord) -> Path:
        task_dir = self.directory(record.id)
        task_dir.mkdir(parents=True, exist_ok=False)
        self.save(record)
        return task_dir

    def save(self, record: TaskRecord) -> None:
        record.updated_at = datetime.now(timezone.utc)
        path = self.directory(record.id) / "task.json"
        payload = record.model_dump(mode="json")
        with self._lock:
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def get(self, task_id: str) -> TaskRecord | None:
        path = self.directory(task_id) / "task.json"
        if not path.exists():
            return None
        return TaskRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def delete(self, task_id: str) -> bool:
        task_dir = self.directory(task_id)
        if not task_dir.exists():
            return False
        shutil.rmtree(task_dir)
        return True

    def cleanup_expired(self) -> int:
        now = datetime.now(timezone.utc)
        removed = 0
        for path in self.root.iterdir():
            if not path.is_dir():
                continue
            record = self.get(path.name)
            if record and now - record.updated_at > self.retention:
                shutil.rmtree(path, ignore_errors=True)
                removed += 1
        return removed

