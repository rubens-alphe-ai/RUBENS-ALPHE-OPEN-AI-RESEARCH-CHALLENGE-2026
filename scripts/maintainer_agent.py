#!/usr/bin/env python3
"""Autonomous maintainer: find problems, hypothesise, fix, confirm or refute.

The loop, for each failing check:

1. **Detect** — deterministic checks run against the project (tests, artifact
   validation, secret scan, hash manifest freshness, visitor notes, JSON
   parsing, registry consistency, leak scan of unevaluated experiments).
2. **Hypothesise** — a check with a known safe remedy states it; otherwise the
   local model reads the failure and the implicated files and proposes a
   hypothesis plus exact text edits.
3. **Fix** — edits are applied in a separate git worktree on a new branch.
   The main working copy is never modified.
4. **Confirm or refute** — every check is run again in the worktree. The fix is
   CONFIRMED only if the target check now passes and no other check started
   failing. Otherwise it is REFUTED, the branch is deleted, and the attempt is
   still recorded.
5. **Commit** — a confirmed fix is committed on its branch with the hypothesis
   and the before/after evidence. Nothing is merged or pushed: merging is the
   operator's decision.

Why the gate is deterministic: a small model proposes plausible edits that are
often wrong. Its proposals are allowed to fail; they are not allowed to land
unverified. Edits are also refused outright when they touch frozen experiment
artifacts, bot-managed state, workflows or private files, and a failing test
may never be "fixed" by editing the tests.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
from model_adapter import AdapterConfig, AdapterError, build_adapter  # noqa: E402

WORKTREE_BASE = Path.home() / "Documents" / "RA-PSI-maintainer-worktrees"

EDITABLE_PREFIXES = ("scripts/", "tests/", "docs/", "schemas/", "visitors/README.md", "README.md", "ARCHITECTURE.md")
PROTECTED_PREFIXES = ("docs/api/", "experiments/", "state/", ".github/", "bridge_state/")
MANIFEST_SKIP_NAMES = {"config.local.json", "client_secret.json", "credentials.json", "gmail-token.json"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run(cmd: list[str], cwd: Path, timeout: int = 600) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    scratch = tempfile.gettempdir()
    env.update(TMP=scratch, TEMP=scratch, TMPDIR=scratch)
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, env=env)


def tail(text: str, limit: int = 1500) -> str:
    text = text.strip()
    return text if len(text) <= limit else "...\n" + text[-limit:]


# ---------------------------------------------------------------- checks ----

def check_script(project: Path, *args: str) -> tuple[bool, str]:
    result = run([sys.executable, *args], project)
    return result.returncode == 0, tail(result.stdout + "\n" + result.stderr)


def check_unit_tests(project: Path) -> tuple[bool, str]:
    result = run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], project)
    return result.returncode == 0, tail(result.stderr + "\n" + result.stdout)


def tracked_files(project: Path) -> list[str]:
    result = run(["git", "ls-files", "-z", "--", "."], project)
    return [item for item in result.stdout.split("\0") if item]


def expected_manifest(project: Path) -> dict[str, str]:
    entries = {}
    for relative in sorted(tracked_files(project)):
        path = project / relative
        if (
            relative == "SHA256SUMS.json"
            or not path.is_file()
            or "__pycache__" in relative
            or path.name in MANIFEST_SKIP_NAMES
            or path.name.endswith(".private.json")
        ):
            continue
        entries[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return entries


def check_hash_manifest(project: Path) -> tuple[bool, str]:
    manifest = project / "SHA256SUMS.json"
    try:
        recorded = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, "SHA256SUMS.json unreadable: %s" % exc
    expected = expected_manifest(project)
    stale = sorted(path for path in expected if path in recorded and recorded[path] != expected[path])
    missing = sorted(path for path in expected if path not in recorded)
    extra = sorted(path for path in recorded if path not in expected)
    ok = not (stale or missing or extra)
    return ok, json.dumps(
        {"stale": len(stale), "missing": len(missing), "no_longer_tracked": len(extra),
         "examples": (stale + missing + extra)[:6]}
    )


def check_json_parseable(project: Path) -> tuple[bool, str]:
    broken = []
    for relative in tracked_files(project):
        if relative.endswith(".json"):
            try:
                json.loads((project / relative).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                broken.append("%s: %s" % (relative, exc))
    return not broken, "\n".join(broken[:10]) or "all tracked JSON parses"


VERDICT_TO_STATUS = {"REJECT": "REJECTED", "FINAL_KEEP": "ADOPTED"}


def check_registry_consistency(project: Path) -> tuple[bool, str]:
    registry = json.loads((project / "experiments" / "registry.json").read_text(encoding="utf-8"))
    by_id = {entry["experiment_id"]: entry for entry in registry["experiments"]}
    problems = []
    for decision_path in sorted((project / "experiments").glob("*/results/decision.json")):
        experiment_id = decision_path.parent.parent.name
        decision = json.loads(decision_path.read_text(encoding="utf-8")).get("decision")
        expected = VERDICT_TO_STATUS.get(decision)
        entry = by_id.get(experiment_id)
        if entry is None:
            problems.append("%s has a decision but no registry entry" % experiment_id)
        elif expected and entry.get("status") != expected:
            problems.append("%s decided %s but registry says %s" % (experiment_id, decision, entry.get("status")))
    return not problems, "\n".join(problems) or "registry matches recorded decisions"


def check_unevaluated_leaks(project: Path) -> tuple[bool, str]:
    details = []
    ok = True
    for manifest in sorted((project / "experiments").glob("*/results/experiment-manifest.json")):
        results = manifest.parent
        if (results / "scorecards").is_dir():
            continue  # already evaluated; its outputs are historical record
        if not any(results.glob("*_trial_*.txt")):
            continue
        passed, output = check_script(project, "scripts/scan_packet_leaks.py", "--experiment", results.parent.name)
        ok = ok and passed
        details.append("%s: %s" % (results.parent.name, "CLEAR" if passed else output))
    return ok, "\n".join(details) or "no unevaluated experiment with outputs"


PUBLIC_RAW = "https://raw.githubusercontent.com/rubens-alphe-ai/RUBENS-ALPHE-OPEN-AI-RESEARCH-CHALLENGE-2026/main/"
PUBLIC_PIPELINE_FILES = ("scripts/fetch_research.py", "scripts/analyze_research.py", "scripts/update_state.py", "scripts/build_feed.py")


def check_public_pipeline_sync(project: Path) -> tuple[bool, str]:
    """Compare the research pipeline scripts with the public repository.

    On 2026-09-16 the local copy was still running the arXiv collector that
    failed with HTTP 429, while GitHub had moved to OpenAlex a day earlier.
    Nothing flagged it. Line endings are ignored; content is not.
    """
    import urllib.error
    import urllib.request

    differing, unreachable = [], []
    for relative in PUBLIC_PIPELINE_FILES:
        try:
            with urllib.request.urlopen(PUBLIC_RAW + relative, timeout=20) as response:
                remote = response.read().replace(b"\r\n", b"\n")
        except (urllib.error.URLError, OSError) as exc:
            unreachable.append("%s (%s)" % (relative, exc))
            continue
        local_path = project / relative
        local = local_path.read_bytes().replace(b"\r\n", b"\n") if local_path.is_file() else b""
        if local != remote:
            differing.append(relative)
    if unreachable and not differing:
        # No network is not a defect of the project; report it without failing.
        return True, "public repository unreachable, not compared: " + "; ".join(unreachable)
    return not differing, ("differs from GitHub main: " + ", ".join(differing)) if differing else "pipeline scripts match GitHub main"


CHECKS = [
    {"id": "unit_tests", "run": check_unit_tests, "remedy": None,
     "about": "the unit test suite must pass"},
    {"id": "artifacts_valid", "run": lambda p: check_script(p, "scripts/validate_artifacts.py"), "remedy": None,
     "about": "structural validation of experiment artifacts"},
    {"id": "public_safety", "run": lambda p: check_script(p, "scripts/check_public_safety.py", "."), "remedy": None,
     "about": "no secret-like file or value in the public tree"},
    {"id": "hash_manifest_fresh", "run": check_hash_manifest,
     "remedy": [sys.executable, "scripts/update_hash_manifest.py"],
     "about": "SHA256SUMS.json must match the tracked files",
     "hypothesis": "Tracked files changed after SHA256SUMS.json was last generated, so the published manifest no longer certifies the tree. Regenerating it from the tracked files should make every recorded hash match."},
    {"id": "visitor_notes_valid", "run": lambda p: check_script(p, "scripts/validate_visitor_notes.py"), "remedy": None,
     "about": "visitor notes match their schema and proofs recompute"},
    {"id": "json_parseable", "run": check_json_parseable, "remedy": None,
     "about": "every tracked JSON file parses"},
    {"id": "registry_consistent", "run": check_registry_consistency, "remedy": None,
     "about": "registry status agrees with recorded adjudication decisions"},
    {"id": "no_leaks_before_evaluation", "run": check_unevaluated_leaks, "remedy": None,
     "about": "outputs awaiting evaluation contain no condition-identifying string"},
    {"id": "public_pipeline_in_sync", "run": check_public_pipeline_sync, "remedy": None, "report_only": True,
     "about": "research pipeline scripts match the public repository"},
]


def run_checks(project: Path) -> dict[str, dict]:
    results = {}
    for check in CHECKS:
        try:
            ok, details = check["run"](project)
        except Exception as exc:  # a crashing check is a failing check
            ok, details = False, "check crashed: %r" % exc
        results[check["id"]] = {"ok": ok, "details": details}
    return results


# -------------------------------------------------------- model proposals ----

PROPOSAL_TEMPLATE = """You maintain a research software project. A deterministic check is failing.

CHECK: {check_id} — {about}
FAILURE OUTPUT:
{details}

FILES YOU MAY EDIT (current content):
{files}

Be brief: no explanation outside the JSON.
State one hypothesis for the cause, then propose the smallest fix as exact text
replacements. Each "find" must be copied exactly from a file above and occur in
it exactly once. Do not edit tests to make a failing test pass. If you cannot
identify a safe fix, return an empty edits list.

Return JSON:
{{"hypothesis": "...", "edits": [{{"path": "...", "find": "...", "replace": "..."}}]}}
"""


def implicated_files(project: Path, details: str) -> list[str]:
    found = []
    for match in re.findall(r"[\w./\\-]+\.(?:py|json|md)", details):
        relative = match.replace("\\", "/")
        for marker in ("/project/", "project/"):
            if marker in relative:
                relative = relative.split(marker, 1)[1]
        if (project / relative).is_file() and relative not in found:
            found.append(relative)
    # A failing assertion's traceback names only the test file, which may not
    # be edited to fix it. The code under test is what the test imports.
    for relative in list(found):
        if relative.startswith("tests/"):
            source = (project / relative).read_text(encoding="utf-8", errors="replace")
            for module in re.findall(r"^from (\w+) import", source, re.M):
                candidate = "scripts/%s.py" % module
                if (project / candidate).is_file() and candidate not in found:
                    found.append(candidate)
    found.sort(key=lambda path: path.startswith("tests/"))
    return found[:2]


def editable(relative: str, target_check: str) -> str | None:
    if relative.endswith(".private.json") or relative.startswith(PROTECTED_PREFIXES):
        return "protected path"
    if not relative.startswith(EDITABLE_PREFIXES):
        return "outside editable paths"
    if target_check == "unit_tests" and relative.startswith("tests/"):
        return "a failing test may not be fixed by editing tests"
    return None


def propose_with_model(project: Path, check: dict, details: str, model: str) -> dict:
    files = implicated_files(project, details)
    blocks = []
    for relative in files:
        text = (project / relative).read_text(encoding="utf-8", errors="replace")
        blocks.append("--- %s ---\n%s" % (relative, text[:6000]))
    if not blocks:
        return {"hypothesis": "no implicated editable file could be identified from the failure", "edits": []}
    adapter = build_adapter(AdapterConfig(
        provider="ollama", model=model, endpoint="http://127.0.0.1:11434/api/chat",
        temperature=0.2, max_output_tokens=3500, timeout_seconds=1500, think=False, response_format="json"))
    raw = adapter.generate(PROPOSAL_TEMPLATE.format(
        check_id=check["id"], about=check["about"], details=details[:3000], files="\n\n".join(blocks)), seed=11)
    start, end = raw.find("{"), raw.rfind("}")
    proposal = json.loads(raw[start:end + 1]) if start != -1 and end > start else {}
    edits = proposal.get("edits") if isinstance(proposal.get("edits"), list) else []
    return {"hypothesis": str(proposal.get("hypothesis", "")), "edits": edits}


def apply_edits(project: Path, edits: list, target_check: str) -> list[str]:
    problems = []
    for index, edit in enumerate(edits):
        if not isinstance(edit, dict):
            problems.append("edit %d is not an object" % index)
            continue
        relative = str(edit.get("path", "")).replace("\\", "/").lstrip("./")
        refusal = editable(relative, target_check)
        if refusal:
            problems.append("edit %d refused on %s: %s" % (index, relative, refusal))
            continue
        path = project / relative
        if not path.is_file():
            problems.append("edit %d: %s does not exist" % (index, relative))
            continue
        text = path.read_text(encoding="utf-8")
        find = str(edit.get("find", ""))
        if not find or text.count(find) != 1:
            problems.append("edit %d: find text occurs %d times in %s" % (index, text.count(find) if find else 0, relative))
            continue
        path.write_text(text.replace(find, str(edit.get("replace", ""))), encoding="utf-8")
    return problems


# ------------------------------------------------------------ git plumbing ----

def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return run(["git", "-C", str(repo), *args], repo)


def attempt(repo: Path, project_rel: str, check: dict, before: dict, model: str) -> dict:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    branch = "agent/maint-%s-%s" % (stamp, check["id"].replace("_", "-"))
    worktree = WORKTREE_BASE / branch.replace("/", "_")
    WORKTREE_BASE.mkdir(parents=True, exist_ok=True)
    record = {"check": check["id"], "branch": branch, "started_at_utc": now(),
              "failure": before[check["id"]]["details"]}

    added = git(repo, "worktree", "add", "-b", branch, str(worktree), "HEAD")
    if added.returncode != 0:
        record.update(outcome="ERROR", reason="worktree creation failed: " + tail(added.stderr, 400))
        return record
    project = worktree / project_rel
    try:
        if check["remedy"]:
            record["method"] = "deterministic remedy"
            record["hypothesis"] = check["hypothesis"]
            remedy = run(check["remedy"], project)
            record["fix"] = tail(remedy.stdout, 400)
            refusals = [] if remedy.returncode == 0 else ["remedy failed: " + tail(remedy.stderr, 400)]
        else:
            record["method"] = "model proposal (%s)" % model
            try:
                proposal = propose_with_model(project, check, before[check["id"]]["details"], model)
            except (AdapterError, ValueError, json.JSONDecodeError) as exc:
                proposal = {"hypothesis": "", "edits": [], "error": str(exc)}
            record["hypothesis"] = proposal.get("hypothesis") or "(none offered)"
            record["proposed_edits"] = len(proposal.get("edits", []))
            refusals = apply_edits(project, proposal.get("edits", []), check["id"])
            if proposal.get("error"):
                refusals.append("model error: " + proposal["error"])

        record["edit_refusals"] = refusals
        diff = git(worktree, "status", "--porcelain")
        changed = [line[3:] for line in diff.stdout.splitlines() if line.strip()]
        record["changed_files"] = changed

        after = run_checks(project)
        newly_failing = sorted(cid for cid, res in after.items() if not res["ok"] and before[cid]["ok"])
        target_fixed = after[check["id"]]["ok"]
        record["after"] = {cid: res["ok"] for cid, res in after.items()}
        record["newly_failing"] = newly_failing

        if changed and target_fixed and not newly_failing:
            record["outcome"] = "CONFIRMED"
            message = (
                "maintainer: fix %s\n\nHypothesis: %s\n\nMethod: %s\nChanged: %s\n"
                "Evidence: %s failed before this change and passes after it; no other check regressed.\n\n"
                "Generated-By: RA-PSI maintainer agent\n"
            ) % (check["id"], record["hypothesis"], record["method"], ", ".join(changed[:10]), check["id"])
            git(worktree, "add", "-A")
            committed = git(worktree, "commit", "-q", "-m", message)
            if committed.returncode != 0:
                record.update(outcome="ERROR", reason="commit failed: " + tail(committed.stderr, 400))
        else:
            record["outcome"] = "REFUTED"
            record["reason"] = (
                "no change was made" if not changed
                else "target check still fails" if not target_fixed
                else "fix broke: " + ", ".join(newly_failing)
            )
    finally:
        git(repo, "worktree", "remove", "--force", str(worktree))
        if record.get("outcome") != "CONFIRMED":
            git(repo, "branch", "-D", branch)
            record["branch"] = None
    record["finished_at_utc"] = now()
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", type=Path, default=SCRIPTS.parent, help="project folder inside a git repository")
    parser.add_argument("--model", default="llama3.2:3b")
    parser.add_argument("--max-problems", type=int, default=3)
    parser.add_argument("--detect-only", action="store_true", help="report failing checks without attempting fixes")
    args = parser.parse_args()

    project = args.project.resolve()
    top = run(["git", "rev-parse", "--show-toplevel"], project)
    if top.returncode != 0:
        raise SystemExit("project is not inside a git repository")
    repo = Path(top.stdout.strip())
    project_rel = project.relative_to(repo.resolve()).as_posix() if project != repo.resolve() else "."

    dirty = git(repo, "status", "--porcelain", "--", project_rel).stdout.strip()
    before = run_checks(project)
    # A drift from the public repository needs a human decision about which
    # side is right, so it is reported but never "fixed" automatically.
    failing = [check for check in CHECKS if not before[check["id"]]["ok"] and not check.get("report_only")]
    report = {
        "agent": "RA-PSI maintainer agent", "run_at_utc": now(), "project": str(project),
        "uncommitted_changes_in_project": bool(dirty),
        "checks": {cid: res["ok"] for cid, res in before.items()},
        "failing": [cid for cid, res in before.items() if not res["ok"]], "attempts": [],
    }
    if dirty and not args.detect_only:
        report["note"] = ("The project has uncommitted changes. Fixes are built from the last commit, so they "
                          "cannot see those changes; commit first for the agent to work on the current state.")
    if not args.detect_only:
        for check in failing[: args.max_problems]:
            report["attempts"].append(attempt(repo, project_rel, check, before, args.model))

    reports = project / "agents" / "maintainer-reports"
    reports.mkdir(parents=True, exist_ok=True)
    path = reports / ("%s.json" % datetime.now().strftime("%Y%m%d-%H%M%S"))
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    summary = {
        "checks_passing": sum(before[c]["ok"] for c in before), "checks_total": len(before),
        "failing": report["failing"],
        "attempts": [{"check": a["check"], "outcome": a.get("outcome"), "branch": a.get("branch"),
                      "hypothesis": a.get("hypothesis"), "reason": a.get("reason")} for a in report["attempts"]],
        "report": str(path),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
