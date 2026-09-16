#!/usr/bin/env python3
"""Command-line entry point for the RA-PSI Gmail/Qwen bridge."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from bridge.core import BridgeStore
    from bridge.gmail_api import DEFAULT_SCOPES, GmailApiClient
    from bridge.ollama_client import OllamaClient
    from bridge.service import BridgeService
else:
    from .core import BridgeStore
    from .gmail_api import DEFAULT_SCOPES, GmailApiClient
    from .ollama_client import OllamaClient
    from .service import BridgeService


def _resolve_path(value: str, base: Path) -> Path:
    expanded = os.path.expandvars(os.path.expanduser(value))
    path = Path(expanded)
    return path if path.is_absolute() else (base / path).resolve()


def load_config(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("bridge config must be a JSON object")
    return value


def build_service(config: dict[str, Any], config_path: Path, workspace_override: Path | None, send_replies: bool | None) -> tuple[BridgeService, OllamaClient, str]:
    base = config_path.parent
    paths = config.get("paths") or {}
    workspace_value = workspace_override or _resolve_path(str(paths.get("workspace") or "../.."), base)
    workspace = workspace_value.resolve()
    store = BridgeStore(
        workspace,
        agent_inbox=_resolve_path(str(paths.get("agent_inbox") or "agent_inbox"), workspace),
        agent_outbox=_resolve_path(str(paths.get("agent_outbox") or "agent_outbox"), workspace),
        agent_proposals=_resolve_path(str(paths.get("agent_proposals") or "agent_proposals"), workspace),
        state_dir=_resolve_path(str(paths.get("state_dir") or "bridge_state"), workspace),
    )
    gmail = config.get("gmail") or {}
    scopes = tuple(str(item) for item in gmail.get("scopes") or DEFAULT_SCOPES)
    gateway = GmailApiClient(
        _resolve_path(str(gmail.get("client_secret_path") or "gmail-client.json"), base),
        _resolve_path(str(gmail.get("token_path") or "gmail-token.json"), base),
        scopes=scopes,
    )
    send = bool(config.get("send_replies", False)) if send_replies is None else send_replies
    bridge = BridgeService(
        gateway,
        store,
        marker=str(config.get("marker") or "RAPC QVEN"),
        query=str(gmail.get("query") or '{"RAPC Qven" "RAPC Qwen"} -in:spam -in:trash'),
        max_results=int(config.get("max_results") or 25),
        send_replies=send,
    )
    ollama_cfg = config.get("ollama") or {}
    ollama = OllamaClient(
        str(ollama_cfg.get("base_url") or "http://127.0.0.1:11434"),
        int(ollama_cfg.get("health_timeout_seconds") or 5),
    )
    return bridge, ollama, str(ollama_cfg.get("model") or "qwen3:4b-nothink")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RA-PSI Gmail <-> Agent Inbox/Outbox bridge")
    parser.add_argument("--config", type=Path, required=True, help="path to a local config file outside public GitHub content")
    parser.add_argument("--workspace", type=Path, help="override the workspace containing agent_inbox and agent_outbox")
    parser.add_argument("--once", action="store_true", help="run one poll and exit")
    parser.add_argument("--poll-seconds", type=int, help="override the configured polling interval")
    parser.add_argument("--send-replies", dest="send_replies", action="store_true", help="enable Gmail replies after an explicit local choice")
    parser.add_argument("--dry-run", dest="send_replies", action="store_false", help="do not send Gmail replies")
    parser.set_defaults(send_replies=None)
    args = parser.parse_args(argv)
    config_path = args.config.expanduser().resolve()
    config = load_config(config_path)
    service, ollama, model = build_service(config, config_path, args.workspace, args.send_replies)
    try:
        models = ollama.require_model(model)
        print(json.dumps({"ollama": "ready", "model": model, "available_models": models}, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"ollama": "not_ready", "model": model, "error": str(exc)}, ensure_ascii=False))
        return 2

    interval = int(args.poll_seconds or config.get("poll_interval_seconds") or 30)
    while True:
        try:
            report = service.poll_once()
            print(json.dumps(report, ensure_ascii=False))
        except Exception as exc:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
            if args.once:
                return 1
        if args.once:
            return 0
        time.sleep(max(5, interval))


if __name__ == "__main__":
    raise SystemExit(main())
