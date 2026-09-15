#!/usr/bin/env python3
import json, shutil
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
state_path = ROOT / "state/latest-state.json"
public_state_path = ROOT / "docs/api/latest-state.json"
digest_path = ROOT / "docs/api/research-digest.json"

state = json.loads(state_path.read_text(encoding="utf-8"))
state["cycle"] = int(state.get("cycle", 0)) + 1
state["version"] = int(state.get("version", 0)) + 1
state["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
state["last_autonomous_cycle"] = state["updated_at_utc"]

if digest_path.exists():
    digest = json.loads(digest_path.read_text(encoding="utf-8"))
    state["research_digest_version"] = state["cycle"]
    state["research_papers_visible"] = len(digest.get("papers", []))

state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
public_state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
print("Updated state cycle", state["cycle"])
