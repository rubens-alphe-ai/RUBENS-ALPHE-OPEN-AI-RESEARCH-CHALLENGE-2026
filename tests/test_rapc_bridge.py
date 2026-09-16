from __future__ import annotations

import base64
import json
import sys
import tempfile
import unittest
from email import policy
from email.parser import BytesParser
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from bridge.core import (  # noqa: E402
    BridgeStore,
    InboundMessage,
    RESPONSE_SCHEMA_VERSION,
    build_task,
    extract_mission,
    sha256_text,
    verify_task,
)
from bridge.gmail_api import GmailApiClient, _extract_text  # noqa: E402
from bridge.service import BridgeService  # noqa: E402
from check_public_safety import scan_tree  # noqa: E402


class FakeGateway:
    def __init__(self, messages: list[InboundMessage]):
        self.messages = messages
        self.sent: list[tuple[str, str]] = []

    def search_messages(self, query: str, max_results: int) -> list[InboundMessage]:
        del query
        return self.messages[:max_results]

    def read_message(self, message_id: str) -> InboundMessage:
        return next(message for message in self.messages if message.message_id == message_id)

    def find_reply_by_task_id(self, thread_id: str, task_id: str) -> str | None:
        del thread_id
        for known_task_id, message_id in self.sent:
            if known_task_id == task_id:
                return message_id
        return None

    def send_reply(self, task: dict[str, object], task_id: str, body: str) -> str:
        del task
        message_id = f"reply-{len(self.sent) + 1}"
        self.sent.append((task_id, message_id))
        return message_id


class RapcBridgeTests(unittest.TestCase):
    def make_message(self) -> InboundMessage:
        return InboundMessage(
            message_id="gmail-message-1",
            thread_id="gmail-thread-1",
            subject="[RA-PSI] task for Qwen",
            sender="Rubens <rubens@example.com>",
            body="[RAPC Qven]\nDesign a bounded experiment for the bridge.\n\nThanks",
            rfc_message_id="<message-1@example.com>",
            reply_to="rubens@example.com",
            received_at_utc="2026-09-15T12:00:00Z",
        )

    def test_marker_is_case_insensitive_and_mission_is_extracted(self) -> None:
        extraction = extract_mission("subject", "prefix\nRAPC-qWeN: do this\n> old quote")
        self.assertIsNotNone(extraction)
        assert extraction is not None
        self.assertEqual(extraction.mission, "do this")
        self.assertEqual(extraction.marker, "RAPC QVEN")
        self.assertIsNone(extract_mission("ordinary", "no routing marker"))

    def test_marker_only_in_quoted_history_is_ignored(self) -> None:
        body = "The latest reply contains no new assignment.\n> [RAPC Qven] old mission"
        self.assertIsNone(extract_mission("ordinary", body))

    def test_bridge_reply_is_not_routed_as_a_new_task(self) -> None:
        message = InboundMessage(
            message_id="gmail-reply-1",
            thread_id="gmail-thread-1",
            body="[RAPC QWEN][RESULT]\nold response",
            headers={"x-rapc-task-id": "rapc-existing"},
        )
        self.assertTrue(BridgeService._is_bridge_reply(message))

    def test_task_is_deterministic_and_verifiable(self) -> None:
        task_a = build_task(self.make_message())
        task_b = build_task(self.make_message())
        self.assertIsNotNone(task_a)
        self.assertEqual(task_a, task_b)
        assert task_a is not None
        self.assertTrue(task_a["task_id"].startswith("rapc-"))
        self.assertEqual(task_a["source_message_id"], "gmail-message-1")
        self.assertEqual(len(task_a["mission_sha256"]), 64)
        self.assertEqual(len(task_a["envelope_sha256"]), 64)
        verify_task(task_a)

    def test_store_deduplicates_one_gmail_message(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = BridgeStore(Path(directory))
            task = build_task(self.make_message())
            assert task is not None
            first, first_path = store.enqueue_task(task)
            second, second_path = store.enqueue_task(task)
            self.assertTrue(first)
            self.assertFalse(second)
            self.assertEqual(first_path, second_path)
            events = store.ledger.events()
            self.assertEqual(len([e for e in events if e["event_type"] == "TASK_ENQUEUED"]), 1)

    def test_service_routes_task_and_sends_one_threaded_reply(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = BridgeStore(Path(directory))
            gateway = FakeGateway([self.make_message()])
            service = BridgeService(gateway, store, send_replies=True)
            first = service.poll_once()
            self.assertEqual(first["tasks_enqueued"], 1)
            task = build_task(self.make_message())
            assert task is not None
            response = "VERIFIED_STATE\nThe bridge is a measurable next step."
            result = {
                "schema_version": RESPONSE_SCHEMA_VERSION,
                "task_id": task["task_id"],
                "source_message_id": task["source_message_id"],
                "source_thread_id": task["source_thread_id"],
                "completed_at_utc": "2026-09-15T12:01:00Z",
                "ok": True,
                "response": response,
                "response_sha256": sha256_text(response),
            }
            (store.agent_outbox / f"{task['task_id']}.result.json").write_text(
                json.dumps(result), encoding="utf-8"
            )
            second = service.poll_once()
            self.assertEqual(second["replies_sent"], 1)
            self.assertEqual(len(gateway.sent), 1)
            third = service.poll_once()
            self.assertEqual(third["replies_recovered"], 1)
            self.assertEqual(len(gateway.sent), 1)
            sent_events = [e for e in store.ledger.events() if e["event_type"] == "REPLY_SENT"]
            self.assertEqual(len(sent_events), 1)

    def test_service_rejects_response_with_wrong_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = BridgeStore(Path(directory))
            gateway = FakeGateway([self.make_message()])
            service = BridgeService(gateway, store, send_replies=True)
            service.poll_once()
            task = build_task(self.make_message())
            assert task is not None
            result = {
                "schema_version": RESPONSE_SCHEMA_VERSION,
                "task_id": task["task_id"],
                "source_message_id": task["source_message_id"],
                "source_thread_id": task["source_thread_id"],
                "completed_at_utc": "2026-09-15T12:01:00Z",
                "ok": True,
                "response": "tampered",
                "response_sha256": "0" * 64,
            }
            (store.agent_outbox / f"{task['task_id']}.result.json").write_text(
                json.dumps(result), encoding="utf-8"
            )
            report = service.poll_once()
            self.assertEqual(report["responses_rejected"], 1)
            self.assertEqual(gateway.sent, [])

    def test_gmail_reply_has_thread_and_idempotency_headers(self) -> None:
        client = GmailApiClient(Path("client.json"), Path("token.json"))
        captured: dict[str, object] = {}

        def fake_request(method: str, path: str, *, params: object = None, body: object = None) -> dict[str, str]:
            captured.update({"method": method, "path": path, "params": params, "body": body})
            return {"id": "gmail-reply-1"}

        client._request_json = fake_request  # type: ignore[method-assign]
        task = {
            "source_message_id": "gmail-message-1",
            "source_thread_id": "gmail-thread-1",
            "source_message_rfc_id": "<message-1@example.com>",
            "references": "<previous@example.com>",
            "reply_to": "rubens@example.com",
            "subject": "RA-PSI task",
        }
        reply_id = client.send_reply(task, "rapc-1234567890abcdef1234567890abcdef", "result")
        self.assertEqual(reply_id, "gmail-reply-1")
        body = captured["body"]
        assert isinstance(body, dict)
        decoded = base64.urlsafe_b64decode(str(body["raw"]) + "==")
        message = BytesParser(policy=policy.default).parsebytes(decoded)
        self.assertEqual(message["X-RAPC-Task-ID"], "rapc-1234567890abcdef1234567890abcdef")
        self.assertEqual(message["In-Reply-To"], "<message-1@example.com>")
        self.assertEqual(body["threadId"], "gmail-thread-1")

    def test_public_safety_flags_secret_file_and_secret_value(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("public", encoding="utf-8")
            self.assertEqual(scan_tree(root), [])
            (root / "credentials.json").write_text("{}", encoding="utf-8")
            self.assertTrue(scan_tree(root))
            (root / "credentials.json").unlink()
            (root / "bad.txt").write_text('"api_key": "' + "A" * 30 + '"', encoding="utf-8")
            self.assertTrue(scan_tree(root))

    def test_extract_text_prefers_plain_text(self) -> None:
        encoded = base64.urlsafe_b64encode(b"plain result").decode().rstrip("=")
        payload = {
            "mimeType": "multipart/alternative",
            "parts": [
                {"mimeType": "text/html", "body": {"data": encoded}},
                {"mimeType": "text/plain", "body": {"data": encoded}},
            ],
        }
        self.assertEqual(_extract_text(payload), "plain result")


if __name__ == "__main__":
    unittest.main()
