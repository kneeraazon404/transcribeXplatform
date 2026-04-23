from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    id: str
    filename: str
    status: JobStatus = JobStatus.QUEUED
    messages: list[str] = field(default_factory=list)
    transcript: Optional[str] = None
    error: Optional[str] = None
    # Internal: paths to clean up after download
    _temp_dir: Optional[Path] = field(default=None, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add_message(self, text: str) -> None:
        with self._lock:
            self.messages.append(text)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "id": self.id,
                "filename": self.filename,
                "status": self.status,
                "messages": list(self.messages),
                "transcript": self.transcript,
                "error": self.error,
            }


# Global in-memory store — fine for single-process deployments
_store: dict[str, Job] = {}
_store_lock = threading.Lock()


def create_job(filename: str, temp_dir: Optional[Path] = None) -> Job:
    job = Job(id=str(uuid.uuid4()), filename=filename, _temp_dir=temp_dir)
    with _store_lock:
        _store[job.id] = job
    return job


def get_job(job_id: str) -> Optional[Job]:
    with _store_lock:
        return _store.get(job_id)


def list_jobs() -> list[dict]:
    with _store_lock:
        return [j.snapshot() for j in _store.values()]
