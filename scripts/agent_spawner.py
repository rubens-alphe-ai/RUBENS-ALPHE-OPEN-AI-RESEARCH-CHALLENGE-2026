#!/usr/bin/env python3
"""Bounded specialist-agent spawner for RA-PSI.

Reads a task, works out which competences it needs, resolves them against the
registry, and proposes a specialist specification for each gap. Everything runs
on the local Ollama install, so no paid provider is ever involved.

Three properties make a spawned population safe to grow:

* a specialist is a **prompt specification**, not a process. It has no tools,
  no filesystem and no network. It receives text and returns text.
* spawning is **bounded** by the limits block in the registry: agents per task,
  recursion depth and total registry size.
* a new specification is registered as ``PROPOSED`` and is never executed.
  Only an operator running ``approve`` moves it to ``APPROVED``.

Nothing here modifies canonical experiment state. Per ADR-002, a proposal is
not evidence until it has been executed and checked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_adapter import AdapterConfig, AdapterError, build_adapter  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "agents" / "registry.json"
LEDGER_PATH = ROOT / "agents" / "spawn-ledger.jsonl"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def save_registry(registry: dict) -> None:
    REGISTRY_PATH.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def ledger(event: str, payload: dict) -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {"at_utc": now(), "event": event}
    record.update(payload)
    with LEDGER_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


# Lifecycle fields are excluded: the hash binds WHAT the agent is, not where it
# sits in the approval workflow. Including "status" would make every approval
# invalidate the hash it had just checked.
MUTABLE_FIELDS = ("spec_sha256", "status")


def spec_hash(spec: dict) -> str:
    material = {key: spec[key] for key in sorted(spec) if key not in MUTABLE_FIELDS}
    encoded = json.dumps(material, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (slug or "specialist")[:48]


def extract_json(text: str):
    """Pull JSON out of a small model's chatty answer.

    A 3B model routinely emits several top-level values in a row rather than
    one, wraps them in prose, or fences them. Every top-level value is decoded
    and, when they are all arrays, they are concatenated into a single list.
    """
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    candidate = (fenced.group(1) if fenced else text).strip()

    decoder = json.JSONDecoder()
    values = []
    index = 0
    while index < len(candidate):
        start = min(
            (pos for pos in (candidate.find("[", index), candidate.find("{", index)) if pos != -1),
            default=-1,
        )
        if start == -1:
            break
        try:
            value, offset = decoder.raw_decode(candidate, start)
        except json.JSONDecodeError:
            index = start + 1
            continue
        values.append(value)
        index = offset

    if not values:
        raise ValueError("no JSON value found in model output")
    if len(values) == 1:
        return values[0]
    if all(isinstance(value, list) for value in values):
        merged = []
        for value in values:
            merged.extend(value)
        return merged
    return values[0]


def normalise_keys(item: dict) -> dict:
    """Accept why-blocking, why_blocking, whyBlocking and similar drift."""
    return {re.sub(r"[^a-z0-9]+", "_", key.lower()): value for key, value in item.items()}


def adapter_for(model: str, temperature: float = 0.3, as_json: bool = False):
    return build_adapter(
        AdapterConfig(
            provider="ollama",
            model=model,
            endpoint="http://127.0.0.1:11434/api/chat",
            temperature=temperature,
            max_output_tokens=1024,
            timeout_seconds=600,
            think=False,
            response_format="json" if as_json else None,
        )
    )


# Constrained JSON decoding collapses a bare array request into a single
# object, so the array is requested inside a named field instead.
ANALYSE_TEMPLATE = """You plan which specialists a task needs. Do not solve the task.

TASK:
{task}

Identify {limit} DIFFERENT competences the task requires. For each one, give a
short domain name and one sentence on why the task would stall without it.

Return exactly this JSON shape, with {limit} entries in the list:
{{"competences": [{{"domain": "short name", "why_blocking": "one sentence"}}]}}
"""

DRAFT_TEMPLATE = """Write the system prompt for a narrow specialist assistant.

DOMAIN: {domain}
WHY IT IS NEEDED: {why}

The specialist has no tools, no file access and no internet. It reads text and
writes text. Keep the system prompt under 120 words, concrete, and state what
it must refuse to guess.

Answer with ONLY JSON: {{"purpose": "one sentence", "system_prompt": "..."}}
"""


def analyse_task(task: str, model: str, limit: int) -> list:
    raw = adapter_for(model, as_json=True).generate(
        ANALYSE_TEMPLATE.format(task=task, limit=limit), seed=1
    )
    parsed = extract_json(raw)
    if isinstance(parsed, dict):
        # Three shapes seen from small models under constrained decoding:
        # {"competences": [...]}, a bare single competence object, and a dict
        # whose only list value is the competence list.
        if "domain" in normalise_keys(parsed):
            parsed = [parsed]
        else:
            for value in parsed.values():
                if isinstance(value, list):
                    parsed = value
                    break
    if not isinstance(parsed, list):
        raise ValueError("expected a JSON array of competences")
    competences = []
    for raw_item in parsed[:limit]:
        if not isinstance(raw_item, dict):
            continue
        item = normalise_keys(raw_item)
        if item.get("domain"):
            competences.append(
                {
                    "domain": str(item["domain"])[:80],
                    "why_blocking": str(item.get("why_blocking", ""))[:300],
                }
            )
    return competences


def draft_spec(competence: dict, registry: dict, model: str, depth: int, parent) -> dict:
    prohibitions = registry["universal_prohibitions"]
    parsed = extract_json(
        adapter_for(model, as_json=True).generate(
            DRAFT_TEMPLATE.format(
                domain=competence["domain"], why=competence["why_blocking"]
            ),
            seed=2,
        )
    )
    parsed = normalise_keys(parsed) if isinstance(parsed, dict) else {}
    system_prompt = str(parsed.get("system_prompt", "")).strip()
    if len(system_prompt) < 20:
        raise ValueError(
            "model returned an unusable system prompt for " + repr(competence["domain"])
        )
    # The prohibitions are appended by this script, never left to the drafting
    # model: a spawned agent must not be able to soften its own limits.
    system_prompt += "\n\nYou must never:\n" + "\n".join(
        "- " + rule for rule in prohibitions
    )
    spec = {
        "agent_id": slugify(competence["domain"]),
        "domain": competence["domain"],
        "purpose": str(parsed.get("purpose", competence["why_blocking"]))[:400],
        "system_prompt": system_prompt,
        "model": model,
        "provider": "ollama",
        "status": "PROPOSED",
        "created_at_utc": now(),
        "created_by": parent or "agent_spawner",
        "depth": depth,
        "may_not": list(prohibitions),
    }
    if parent:
        spec["parent_agent_id"] = parent
    spec["spec_sha256"] = spec_hash(spec)
    return spec


def cmd_plan(args) -> int:
    registry = load_registry()
    limits = registry["limits"]
    if args.depth > limits["max_depth"]:
        print("REFUSED: depth %d exceeds max_depth %d" % (args.depth, limits["max_depth"]))
        return 1
    budget = min(args.max_agents, limits["max_agents_per_task"])
    existing = {agent["agent_id"] for agent in registry["agents"]}

    try:
        competences = analyse_task(args.task, args.model, budget)
    except (AdapterError, ValueError) as exc:
        print(json.dumps({"error": "planning failed", "detail": str(exc)}, indent=2))
        return 1
    if not competences:
        print(json.dumps({"error": "planner returned no usable competence"}, indent=2))
        return 1
    ledger("PLAN", {"task": args.task[:300], "competences": [c["domain"] for c in competences]})

    reused = []
    proposed = []
    refused = []
    for competence in competences:
        agent_id = slugify(competence["domain"])
        if agent_id in existing:
            reused.append(agent_id)
            continue
        if len(registry["agents"]) + len(proposed) >= limits["max_registry_size"]:
            refused.append({"domain": competence["domain"], "reason": "registry full"})
            continue
        try:
            proposed.append(
                draft_spec(competence, registry, args.model, args.depth, args.parent)
            )
        except (AdapterError, ValueError) as exc:
            refused.append({"domain": competence["domain"], "reason": str(exc)})

    if args.write and proposed:
        registry["agents"].extend(proposed)
        save_registry(registry)
        ledger("PROPOSED", {"agent_ids": [spec["agent_id"] for spec in proposed]})

    report = {
        "task": args.task[:200],
        "budget": budget,
        "reused_existing": reused,
        "proposed": [
            {"agent_id": s["agent_id"], "domain": s["domain"], "status": s["status"]}
            for s in proposed
        ],
        "refused": refused,
        "written_to_registry": bool(args.write and proposed),
        "note": "PROPOSED agents are never executed. Run 'approve' to enable one.",
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def cmd_approve(args) -> int:
    registry = load_registry()
    for agent in registry["agents"]:
        if agent["agent_id"] == args.agent_id:
            if agent["spec_sha256"] != spec_hash(agent):
                print(
                    "REFUSED: spec hash mismatch for %s; the specification was edited "
                    "after proposal" % args.agent_id
                )
                return 1
            agent["status"] = "APPROVED"
            save_registry(registry)
            ledger("APPROVED", {"agent_id": args.agent_id})
            print(json.dumps({"agent_id": args.agent_id, "status": "APPROVED"}, indent=2))
            return 0
    print("unknown agent_id: " + args.agent_id)
    return 1


def cmd_run(args) -> int:
    registry = load_registry()
    agent = None
    for candidate in registry["agents"]:
        if candidate["agent_id"] == args.agent_id:
            agent = candidate
            break
    if agent is None:
        print("unknown agent_id: " + args.agent_id)
        return 1
    if agent["status"] != "APPROVED":
        print(
            "REFUSED: %s is %s; only APPROVED agents run" % (args.agent_id, agent["status"])
        )
        return 1
    # The status flag alone is not the gate. A registry edit can set APPROVED
    # and alter the system prompt in the same write, so the approval is only
    # honoured when the specification still hashes to what was approved.
    if agent["spec_sha256"] != spec_hash(agent):
        ledger("REFUSED_TAMPERED", {"agent_id": args.agent_id})
        print(
            "REFUSED: %s carries APPROVED but its specification no longer matches "
            "spec_sha256; the approval does not cover this text" % args.agent_id
        )
        return 1
    answer = adapter_for(agent["model"]).generate(
        agent["system_prompt"] + "\n\n" + args.input, seed=args.seed
    )
    ledger(
        "RUN",
        {
            "agent_id": args.agent_id,
            "output_sha256": hashlib.sha256(answer.encode()).hexdigest(),
        },
    )
    print(answer)
    return 0


def cmd_list(args) -> int:
    registry = load_registry()
    report = {
        "limits": registry["limits"],
        "count": len(registry["agents"]),
        "agents": [
            {
                "agent_id": a["agent_id"],
                "domain": a["domain"],
                "status": a["status"],
                "depth": a.get("depth", 0),
                "spec_intact": a["spec_sha256"] == spec_hash(a),
            }
            for a in registry["agents"]
        ],
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="analyse a task and propose the specialists it needs")
    plan.add_argument("task")
    plan.add_argument("--model", default="llama3.2:3b")
    plan.add_argument("--max-agents", type=int, default=5)
    plan.add_argument("--depth", type=int, default=0)
    plan.add_argument("--parent", default=None)
    plan.add_argument("--write", action="store_true", help="persist proposals to the registry")
    plan.set_defaults(func=cmd_plan)

    approve = sub.add_parser("approve", help="operator action: allow a proposed agent to run")
    approve.add_argument("agent_id")
    approve.set_defaults(func=cmd_approve)

    run = sub.add_parser("run", help="run an approved specialist on some input")
    run.add_argument("agent_id")
    run.add_argument("input")
    run.add_argument("--seed", type=int, default=7)
    run.set_defaults(func=cmd_run)

    listing = sub.add_parser("list", help="show the registry and its limits")
    listing.set_defaults(func=cmd_list)

    args = parser.parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
