"""Bridge orchestration: Gmail marker -> Agent Inbox -> Agent Outbox -> Gmail reply."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any, Protocol

from .core import (
    BridgeStore,
    InboundMessage,
    RESPONSE_SCHEMA_VERSION,
    build_task,
    sha256_text,
)


class MailGateway(Protocol):
    def search_messages(self, query: str, max_results: int) -> list[InboundMessage | dict[str, Any]]: ...

    def read_message(self, message_id: str) -> InboundMessage: ...

    def find_reply_by_task_id(self, thread_id: str, task_id: str) -> str | None: ...

    def send_reply(self, task: dict[str, Any], task_id: str, body: str) -> str: ...


class BridgeService:
    def __init__(
        self,
        gateway: MailGateway,
        store: BridgeStore,
        *,
        marker: str = "RAPC QVEN",
        query: str = '{"RAPC Qven" "RAPC Qwen"} -in:spam -in:trash',
        max_results: int = 25,
        send_replies: bool = False,
    ):
        self.gateway = gateway
        self.store = store
        self.marker = marker
        self.query = query
        self.max_results = max_results
        self.send_replies = send_replies

    def poll_once(self) -> dict[str, int | str | bool]:
        cycle_id = "cycle-" + uuid.uuid4().hex
        stats: dict[str, int | str | bool] = {
            "messages_seen": 0,
            "tasks_enqueued": 0,
            "messages_skipped": 0,
            "responses_seen": 0,
            "replies_sent": 0,
            "replies_recovered": 0,
            "replies_ready": 0,
            "responses_rejected": 0,
            "dry_run": not self.send_replies,
        }
        self.store.record("POLL_STARTED", cycle_id=cycle_id, query=self.query)
        try:
            for candidate in self.gateway.search_messages(self.query, self.max_results):
                stats["messages_seen"] += 1
                message = self._materialize(candidate)
                if self._is_bridge_reply(message):
                    self.store.record_skipped_message(message.message_id, "bridge_reply")
                    stats["messages_skipped"] += 1
                    continue
                if self.store.task_id_for_message(message.message_id) is not None or self.store.has_event(
                    "MESSAGE_SKIPPED", source_message_id=message.message_id
                ):
                    stats["messages_skipped"] += 1
                    continue
                task = build_task(message, marker=self.marker)
                if task is None:
                    self.store.record_skipped_message(message.message_id, "marker_not_found_or_empty_mission")
                    stats["messages_skipped"] += 1
                    continue
                created, _ = self.store.enqueue_task(task)
                if created:
                    stats["tasks_enqueued"] += 1

            for result_path in self.store.result_files():
                stats["responses_seen"] += 1
                outcome = self._handle_result(result_path)
                stats[outcome] += 1
        except Exception as exc:
            self.store.record("POLL_FAILED", cycle_id=cycle_id, error=str(exc))
            raise
        self.store.record("POLL_FINISHED", cycle_id=cycle_id, stats=stats)
        return stats

    def _materialize(self, candidate: InboundMessage | dict[str, Any]) -> InboundMessage:
        if isinstance(candidate, InboundMessage):
            return candidate
        message_id = str(candidate.get("message_id") or candidate.get("id") or "")
        if not message_id:
            raise ValueError("mail search result has no message id")
        if candidate.get("body") is not None:
            return InboundMessage(
                message_id=message_id,
                thread_id=str(candidate.get("thread_id") or message_id),
                subject=str(candidate.get("subject") or ""),
                sender=str(candidate.get("sender") or candidate.get("from") or ""),
                body=str(candidate.get("body") or ""),
                rfc_message_id=str(candidate.get("rfc_message_id") or ""),
                reply_to=str(candidate.get("reply_to") or ""),
                references=str(candidate.get("references") or ""),
                received_at_utc=str(candidate.get("received_at_utc") or ""),
                headers={str(key).lower(): str(value) for key, value in dict(candidate.get("headers") or {}).items()},
            )
        return self.gateway.read_message(message_id)

    @staticmethod
    def _is_bridge_reply(message: InboundMessage) -> bool:
        return bool(
            message.headers.get("x-rapc-task-id")
            or message.headers.get("x-rapc-source-message-id")
        )

    def _handle_result(self, result_path: Path) -> str:
        try:
            result = json.loads(result_path.read_text(encoding="utf-8-sig"))
            if not isinstance(result, dict):
                raise ValueError("response envelope must be a JSON object")
            filename_task_id = result_path.name.removesuffix(".result.json")
            task_id = str(result.get("task_id") or "")
            if not task_id or task_id != filename_task_id:
                self.store.record(
                    "RESPONSE_REJECTED",
                    task_id=task_id or filename_task_id,
                    path=str(result_path),
                    reason="task_id_filename_mismatch",
                )
                return "responses_rejected"
            if result.get("schema_version") != RESPONSE_SCHEMA_VERSION:
                self.store.record(
                    "RESPONSE_REJECTED",
                    task_id=task_id,
                    path=str(result_path),
                    reason="unsupported_response_schema",
                )
                return "responses_rejected"
            if not isinstance(result.get("ok"), bool) or not str(result.get("completed_at_utc") or "").strip():
                self.store.record(
                    "RESPONSE_REJECTED",
                    task_id=task_id,
                    path=str(result_path),
                    reason="missing_response_metadata",
                )
                return "responses_rejected"
            task = self.store.load_task(task_id)
            source_message_id = str(result.get("source_message_id") or result.get("message_id") or "")
            source_thread_id = str(result.get("source_thread_id") or "")
            if (
                source_message_id != task["source_message_id"]
                or source_thread_id != task["source_thread_id"]
            ):
                self.store.record(
                    "RESPONSE_REJECTED",
                    task_id=task_id,
                    path=str(result_path),
                    reason="source_identity_mismatch",
                )
                return "responses_rejected"
            response_text = self._response_text(result)
            declared_hash = str(result.get("response_sha256") or "")
            actual_hash = sha256_text(response_text)
            if not declared_hash or declared_hash != actual_hash:
                self.store.record(
                    "RESPONSE_REJECTED",
                    task_id=task_id,
                    path=str(result_path),
                    reason="response_sha256_mismatch",
                )
                return "responses_rejected"
            body = self._render_reply(task, result, response_text, actual_hash)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            self.store.record("RESPONSE_REJECTED", path=str(result_path), reason=str(exc))
            return "responses_rejected"

        with self.store.lock():
            if self.store.has_event("REPLY_SENT", task_id=task_id):
                return "replies_recovered"
            existing = self.gateway.find_reply_by_task_id(str(task["source_thread_id"]), task_id)
            if existing:
                self.store.ledger.append(
                    "REPLY_SENT",
                    task_id=task_id,
                    source_message_id=task["source_message_id"],
                    thread_id=task["source_thread_id"],
                    gmail_message_id=existing,
                    recovered=True,
                    response_sha256=actual_hash,
                )
                return "replies_recovered"
            if not self.send_replies and self.store.has_event("REPLY_READY", task_id=task_id):
                return "replies_ready"
            self.store.ledger.append(
                "REPLY_READY" if not self.send_replies else "REPLY_SEND_INTENT",
                task_id=task_id,
                source_message_id=task["source_message_id"],
                thread_id=task["source_thread_id"],
                response_sha256=actual_hash,
                path=str(result_path),
            )
            if not self.send_replies:
                return "replies_ready"
            gmail_message_id = self.gateway.send_reply(task, task_id, body)
            self.store.ledger.append(
                "REPLY_SENT",
                task_id=task_id,
                source_message_id=task["source_message_id"],
                thread_id=task["source_thread_id"],
                gmail_message_id=gmail_message_id,
                response_sha256=actual_hash,
            )
            return "replies_sent"

    def _response_text(self, result: dict[str, Any]) -> str:
        if result.get("response") is not None:
            return str(result["response"])
        proposal = result.get("proposal")
        if proposal:
            candidate = Path(str(proposal)).resolve()
            allowed = self.store.agent_proposals
            if allowed != candidate and allowed not in candidate.parents:
                raise ValueError("proposal path is outside agent_proposals")
            return candidate.read_text(encoding="utf-8-sig")
        if result.get("ok") is False:
            return "Local Qwen worker reported an error: " + str(result.get("error") or "unknown error")
        raise ValueError("result has neither response nor an allowed proposal path")

    @staticmethod
    def _render_reply(task: dict[str, Any], result: dict[str, Any], response: str, response_hash: str) -> str:
        status = "OK" if result.get("ok", True) else "ERROR"
        return (
            "[RA-PSI][RAPC QWEN][RESULT]\n"
            f"Status: {status}\n"
            f"Task ID: {task['task_id']}\n"
            f"Source message ID: {task['source_message_id']}\n"
            f"Source thread ID: {task['source_thread_id']}\n"
            f"Response SHA-256: {response_hash}\n"
            "\n--- QWEN RESPONSE ---\n"
            f"{response.rstrip()}\n"
            "--- END QWEN RESPONSE ---\n"
        )
