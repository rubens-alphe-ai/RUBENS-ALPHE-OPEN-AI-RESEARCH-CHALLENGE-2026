"""Dependency-free protocol and durable storage for the RA-PSI bridge."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


TASK_SCHEMA_VERSION = "RAPC-TASK-V1"
RESPONSE_SCHEMA_VERSION = "RAPC-RESPONSE-V1"
LEDGER_SCHEMA_VERSION = "RAPC-LEDGER-V1"
DEFAULT_MARKER = "RAPC QVEN"
# Accept both the project's Qven spelling and the model's usual Qwen spelling.
_MARKER_RE = re.compile(r"(?i)(?<![a-z0-9])rapc[\s_-]*q(?:v|w)en(?![a-z0-9])")
_TASK_ID_RE = re.compile(r"^rapc-[0-9a-f]{32}$")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def atomic_write_text(path: Path, content: str) -> None:
    """Write a file so readers see either the old or the complete new value."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _trim_quoted_text(value: str) -> str:
    lines: list[str] = []
    for line in value.splitlines():
        if lines and (
            re.match(r"^\s*>+", line)
            or re.match(r"^\s*-----Original Message-----\s*$", line, re.I)
            or re.match(r"^\s*On .+ wrote:\s*$", line, re.I)
        ):
            break
        lines.append(line)
    return "\n".join(lines).strip()


@dataclass(frozen=True)
class MissionExtraction:
    mission: str
    source: str
    marker: str


def extract_mission(
    subject: str,
    body: str,
    marker: str = DEFAULT_MARKER,
    max_chars: int = 20_000,
) -> MissionExtraction | None:
    """Find a RAPC/Qwen marker and return the unquoted mission after it.

    The marker is deliberately case-insensitive and accepts common separators,
    so `[RAPC Qven]`, `RAPC-QWEN:` and `RAPC QVEN -` are equivalent.
    """

    del marker  # The accepted wire marker is intentionally stable and normalized.
    for source, value in (("body", body or ""), ("subject", subject or "")):
        # Ignore quoted history before looking for a routing marker. Otherwise a
        # newly polled reply could re-submit an old mission from the same thread.
        searchable = _trim_quoted_text(value)
        match = _MARKER_RE.search(searchable)
        if not match:
            continue
        mission = searchable[match.end() :].lstrip(" \t\r\n[]():,-")
        mission = _trim_quoted_text(mission)
        if source == "subject" and not mission:
            mission = _trim_quoted_text(body or "")
        if mission and len(mission) <= max_chars:
            return MissionExtraction(mission=mission, source=source, marker="RAPC QVEN")
    return None


@dataclass(frozen=True)
class InboundMessage:
    message_id: str
    thread_id: str
    subject: str = ""
    sender: str = ""
    body: str = ""
    rfc_message_id: str = ""
    reply_to: str = ""
    references: str = ""
    received_at_utc: str = ""
    headers: dict[str, str] = field(default_factory=dict)


def _message_payload(message: InboundMessage) -> dict[str, str]:
    return {
        "message_id": message.message_id,
        "thread_id": message.thread_id,
        "subject": message.subject,
        "sender": message.sender,
        "body": message.body,
        "rfc_message_id": message.rfc_message_id,
        "reply_to": message.reply_to,
        "references": message.references,
    }


def build_task(message: InboundMessage, marker: str = DEFAULT_MARKER) -> dict[str, Any] | None:
    extraction = extract_mission(message.subject, message.body, marker=marker)
    if extraction is None:
        return None

    mission_sha256 = sha256_text(extraction.mission)
    payload = _message_payload(message)
    payload_sha256 = sha256_text(canonical_json(payload))
    task_id = "rapc-" + sha256_text(f"{message.message_id}\n{mission_sha256}")[:32]
    task: dict[str, Any] = {
        "schema_version": TASK_SCHEMA_VERSION,
        "task_id": task_id,
        "source_message_id": message.message_id,
        "source_thread_id": message.thread_id,
        "source_message_rfc_id": message.rfc_message_id,
        "reply_to": message.reply_to,
        "references": message.references,
        "subject": message.subject,
        "sender": message.sender,
        "received_at_utc": message.received_at_utc,
        "created_at_utc": utc_now(),
        "marker": extraction.marker,
        "marker_source": extraction.source,
        "mission": extraction.mission,
        "task": extraction.mission,  # compatibility with the existing PowerShell worker
        "mission_sha256": mission_sha256,
        "source_payload_sha256": payload_sha256,
        "status": "READY",
        "trace_id": task_id,
    }
    task["envelope_sha256"] = sha256_text(canonical_json(task))
    return task


def verify_task(task: dict[str, Any]) -> None:
    required = {
        "schema_version",
        "task_id",
        "source_message_id",
        "source_thread_id",
        "created_at_utc",
        "mission",
        "mission_sha256",
        "envelope_sha256",
    }
    missing = sorted(required.difference(task))
    if missing:
        raise ValueError("task missing required fields: " + ", ".join(missing))
    if task["schema_version"] != TASK_SCHEMA_VERSION:
        raise ValueError("unsupported task schema")
    if not _TASK_ID_RE.fullmatch(str(task["task_id"])):
        raise ValueError("invalid task id")
    if not isinstance(task["mission"], str) or not task["mission"].strip():
        raise ValueError("task mission is empty")
    if not str(task["created_at_utc"]).strip():
        raise ValueError("task timestamp is empty")
    if sha256_text(str(task["mission"])) != task["mission_sha256"]:
        raise ValueError("task mission hash mismatch")
    without_hash = dict(task)
    without_hash.pop("envelope_sha256", None)
    if sha256_text(canonical_json(without_hash)) != task["envelope_sha256"]:
        raise ValueError("task envelope hash mismatch")


class LockTimeout(TimeoutError):
    pass


class FileLock:
    """Small cross-process lock using an exclusive lock-file creation."""

    def __init__(self, path: Path, timeout_seconds: float = 15.0, stale_after_seconds: float = 300.0):
        self.path = path
        self.timeout_seconds = timeout_seconds
        self.stale_after_seconds = stale_after_seconds
        self._handle: int | None = None

    def __enter__(self) -> "FileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            try:
                self._handle = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self._handle, f"pid={os.getpid()}\ncreated={utc_now()}\n".encode("utf-8"))
                return self
            except FileExistsError:
                try:
                    age = time.time() - self.path.stat().st_mtime
                    if age > self.stale_after_seconds:
                        self.path.unlink()
                        continue
                except FileNotFoundError:
                    continue
                if time.monotonic() >= deadline:
                    raise LockTimeout(f"timed out acquiring bridge lock: {self.path}")
                time.sleep(0.05)

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if self._handle is not None:
            os.close(self._handle)
            self._handle = None
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


class BridgeLedger:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event_type: str, **fields: Any) -> dict[str, Any]:
        event = {
            "schema_version": LEDGER_SCHEMA_VERSION,
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "event_at_utc": utc_now(),
            **fields,
        }
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(event) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return event

    def events(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        result: list[dict[str, Any]] = []
        for line_number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid bridge ledger line {line_number}: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"bridge ledger line {line_number} is not an object")
            result.append(value)
        return result


class BridgeStore:
    """Filesystem queues and append-only trace for one bridge instance."""

    def __init__(
        self,
        workspace: Path,
        agent_inbox: Path | None = None,
        agent_outbox: Path | None = None,
        agent_proposals: Path | None = None,
        state_dir: Path | None = None,
    ):
        self.workspace = workspace.resolve()
        self.agent_inbox = (agent_inbox or self.workspace / "agent_inbox").resolve()
        self.agent_outbox = (agent_outbox or self.workspace / "agent_outbox").resolve()
        self.agent_proposals = (agent_proposals or self.workspace / "agent_proposals").resolve()
        self.state_dir = (state_dir or self.workspace / "bridge_state").resolve()
        for path in (self.agent_inbox, self.agent_outbox, self.agent_proposals, self.state_dir):
            path.mkdir(parents=True, exist_ok=True)
        self.ledger = BridgeLedger(self.state_dir / "ledger.jsonl")
        self.lock_path = self.state_dir / ".bridge.lock"

    def lock(self) -> FileLock:
        return FileLock(self.lock_path)

    def _events(self) -> list[dict[str, Any]]:
        return self.ledger.events()

    def has_event(self, event_type: str, **match: Any) -> bool:
        for event in self._events():
            if event.get("event_type") == event_type and all(event.get(k) == v for k, v in match.items()):
                return True
        return False

    def task_id_for_message(self, message_id: str) -> str | None:
        for event in self._events():
            if event.get("event_type") == "TASK_ENQUEUED" and event.get("source_message_id") == message_id:
                return str(event["task_id"])
        return None

    def enqueue_task(self, task: dict[str, Any]) -> tuple[bool, Path]:
        verify_task(task)
        path = self.agent_inbox / f"{task['task_id']}.json"
        with self.lock():
            previous = self.task_id_for_message(str(task["source_message_id"]))
            if previous is not None:
                existing_path = self.agent_inbox / f"{previous}.json"
                done_path = self.agent_inbox / f"{previous}.json.done"
                return False, existing_path if existing_path.exists() else done_path
            if path.exists():
                existing = json.loads(path.read_text(encoding="utf-8-sig"))
                verify_task(existing)
                if existing["envelope_sha256"] != task["envelope_sha256"]:
                    raise ValueError(f"task path collision with different content: {path.name}")
            else:
                atomic_write_json(path, task)
            self.ledger.append(
                "TASK_ENQUEUED",
                task_id=task["task_id"],
                source_message_id=task["source_message_id"],
                source_thread_id=task["source_thread_id"],
                mission_sha256=task["mission_sha256"],
                envelope_sha256=task["envelope_sha256"],
                path=str(path),
            )
            return True, path

    def record_skipped_message(self, message_id: str, reason: str) -> None:
        with self.lock():
            if not self.has_event("MESSAGE_SKIPPED", source_message_id=message_id):
                self.ledger.append("MESSAGE_SKIPPED", source_message_id=message_id, reason=reason)

    def load_task(self, task_id: str) -> dict[str, Any]:
        path = self.agent_inbox / f"{task_id}.json"
        if not path.exists():
            done = self.agent_inbox / f"{task_id}.json.done"
            if done.exists():
                path = done
        if not path.exists():
            raise FileNotFoundError(f"no task envelope for {task_id}")
        task = json.loads(path.read_text(encoding="utf-8-sig"))
        verify_task(task)
        return task

    def result_files(self) -> Iterable[Path]:
        return sorted(
            path
            for path in self.agent_outbox.glob("rapc-*.result.json")
            if _TASK_ID_RE.fullmatch(path.name.removesuffix(".result.json"))
        )

    def record(self, event_type: str, **fields: Any) -> dict[str, Any]:
        with self.lock():
            return self.ledger.append(event_type, **fields)
