#!/usr/bin/env python3
"""Measure how much of a document survives *your* pipeline, not ours.

`handoff_bench.py` can measure exactly one transformation: a model writing a
handover note from a prompt we wrote. That is a limit of the code, not of the
method. What the method actually needs is:

    document -> frozen key -> some transformation -> blind reader -> compare letters

and the transformation can be anything a team runs over text and cares about
preserving facts through: a context compactor, a RAG chunker and its retriever,
a summariser, a translation pipeline, a PII redactor, a fine-tune against its
base. This script makes the transformation the customer's own system, named in
a small JSON file, and leaves everything else exactly as it was.

Three kinds of pipeline:

* `http`   POST the document to a URL, read the transformed text back out of
           the JSON response at a declared path. Headers come from a *file*,
           never from the spec, and the file is opened at call time.
* `command` run a local command with the document on stdin and take stdout.
* `model`  an instruction sent to an OpenAI-compatible endpoint, which is what
           `handoff_bench` already did. It is kept here so the existing
           benchmark is a special case of this tool rather than a rival to it.
* `document` no transformation at all. This is the ceiling arm: what a reader
           can answer when handed the whole document. It is the default
           baseline, and a pipeline that scores near it is losing nothing.

What this refuses to do:

* It does not measure one pipeline alone. A single arm confounds the reader's
  own strength with the pipeline's quality: a reader that answers 60% of the
  quiz from a perfect text and a reader that answers 60% from a damaged one are
  indistinguishable. There are always two arms and the number that matters is
  the paired difference between them, with its interval.
* It does not analyse a run whose failures fell unevenly across the arms.
  That rule is `handoff_bench.usability` and it is read here, not decided again.
  Such a run is not a weaker result; it is not a result.
* It does not re-implement the quiz. Option order is derived from a seed in
  `handoff_quiz.render_quiz`, and a second implementation of that shuffle would
  drift and quietly invalidate every comparison ever made against it.
* It does not trust anything the customer's system returns. An empty answer, an
  absurdly long one, and — the misconfiguration that matters most — the input
  handed straight back are each detected and named. A pipeline that echoes its
  input scores perfectly and means nothing, so it is never allowed to pass
  silently.
* It never reads, prints, logs or stores a credential. A headers file is named
  by path and opened inside the request; its contents never reach a report, a
  log line or an error message, and the body of a failed HTTP response is not
  read back, because a server is free to echo the headers it was sent.

Example:

  python scripts/measure_pipeline.py --document notes.md --quiz quiz.json \\
      --pipeline specs/redactor.json --out measure/ --repeats 5 \\
      --reader-model openai/gpt-oss-120b --reader-api-key-file ~/keys/provider.key

A spec is a small JSON file:

  {"name": "redactor", "kind": "http",
   "url": "https://pipeline.example.com/redact",
   "headers_file": "~/keys/vendor-headers.json",
   "body": {"text": "{{document}}", "mode": "strict"},
   "response_path": "result.redacted"}
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import handoff_bench as hb  # noqa: E402
import handoff_quiz as hq  # noqa: E402
from evaluate_experiment import AdapterError, call, sha256_text  # noqa: E402

PLACEHOLDER = "{{document}}"
DEFAULT_TIMEOUT = 300
HOP = "1"  # one transformation, not a chain; kept as a hop so the report shape matches

# Required fields per kind. Anything else in a spec is passed through untouched,
# so a customer can keep their own annotations in the same file.
REQUIRED = {"http": ("url", "body", "response_path"), "command": ("command",),
            "model": ("endpoint", "model", "instruction"), "document": ()}

# A spec is committed to a repository far more often than a key file is. Any
# value that looks like a credential is refused at load time with a pointer to
# headers_file, rather than being copied into report.json where it would then
# also fail scripts/check_public_safety.py.
INLINE_SECRET = re.compile(r"(?i)(bearer\s+\S|authorization\s*:|api[_-]?key\s*[=:]|"
                           r"(?:access|refresh)_token\s*[=:]|\bsk-[A-Za-z0-9_-]{8,})")

ARM_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,39}")


class PipelineError(RuntimeError):
    """The customer's system did not give us usable text.

    Separate from AdapterError because it is never our provider's fault and is
    never retried: a misconfigured URL, a missing response path or a script that
    exits non-zero will fail identically the second time.
    """


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact_url(url: str) -> str:
    """A URL without its query string, for error messages.

    Some services carry their key in `?api_key=`. We have no way to tell which
    parameters are secret, so none of them are ever repeated back.
    """
    return url.split("?", 1)[0]


def walk(value: object):
    """Every string anywhere inside a decoded JSON value."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk(item)


def fill(template: object, document: str) -> object:
    """Substitute the document into a body template, at any depth."""
    if isinstance(template, str):
        return template.replace(PLACEHOLDER, document)
    if isinstance(template, dict):
        return {key: fill(item, document) for key, item in template.items()}
    if isinstance(template, list):
        return [fill(item, document) for item in template]
    return template


def dig(payload: object, path: str) -> str:
    """Follow a dotted path to the transformed text in a JSON response.

    Integer steps index lists, so `choices.0.message.content` works on the shape
    most providers return. When a step is missing the error names the keys that
    were there — keys only, never values, because a response body may carry
    anything the customer's system chose to put in it.
    """
    current = payload
    for step in path.split("."):
        if isinstance(current, list):
            if not re.fullmatch(r"-?\d+", step):
                raise PipelineError("response_path %r reached a list at %r, which needs a number" % (path, step))
            index = int(step)
            if not -len(current) <= index < len(current):
                raise PipelineError("response_path %r asked for item %d of a list of %d" % (path, index, len(current)))
            current = current[index]
        elif isinstance(current, dict):
            if step not in current:
                raise PipelineError("response_path %r: the response has no %r (it has %s)"
                                    % (path, step, ", ".join(sorted(current)[:8]) or "no keys"))
            current = current[step]
        else:
            raise PipelineError("response_path %r: %r is not inside an object or a list" % (path, step))
    if not isinstance(current, str):
        raise PipelineError("response_path %r holds %s, not text" % (path, type(current).__name__))
    return current


def read_headers(path: str | None) -> dict[str, str]:
    """Open the headers file, use it, and let nothing from it escape.

    Every error raised here names the path and never the content — including the
    JSON decoding error, whose message would otherwise quote the line it choked
    on. The returned dict goes straight into the request and is not stored.
    """
    if not path:
        return {}
    resolved = Path(path).expanduser()
    if not resolved.is_file():
        raise PipelineError("no headers file at %s" % resolved)
    try:
        loaded = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise PipelineError("the headers file %s is not valid JSON" % resolved) from None
    if not isinstance(loaded, dict) or not all(isinstance(item, str) for item in loaded.values()):
        raise PipelineError("the headers file %s must be a JSON object whose values are all strings" % resolved)
    return {str(name): item for name, item in loaded.items()}


def http_transform(spec: dict, document: str) -> str:
    """POST the document and read the transformed text out of the response.

    The body of a failed response is deliberately not read. A server that
    reflects the request — many do, in a debug field — would put the
    Authorization header we just sent into our error message and from there into
    a stored record. The status code is enough to fix a misconfiguration.
    """
    data = json.dumps(fill(spec["body"], document)).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    headers.update(read_headers(spec.get("headers_file")))
    request = urllib.request.Request(spec["url"], data=data, headers=headers,
                                     method=str(spec.get("method", "POST")).upper())
    try:
        with urllib.request.urlopen(request, timeout=int(spec.get("timeout_seconds", DEFAULT_TIMEOUT))) as response:
            raw = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        raise PipelineError("HTTP %d from %s" % (exc.code, redact_url(spec["url"]))) from None
    except urllib.error.URLError as exc:
        raise PipelineError("could not reach %s: %s" % (redact_url(spec["url"]), str(exc.reason)[:160])) from None
    except OSError as exc:
        raise PipelineError("request to %s failed: %s" % (redact_url(spec["url"]), type(exc).__name__)) from None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise PipelineError("%s answered %d bytes that are not JSON" % (redact_url(spec["url"]), len(raw))) from None
    return dig(payload, spec["response_path"])


def command_transform(spec: dict, document: str) -> str:
    """Run the customer's own script with the document on stdin.

    The command is a list of arguments and never a shell string: a string would
    be split by one set of quoting rules on this machine and a different set on
    theirs, and a measurement that depends on which machine ran it is not a
    measurement. Standard error is surfaced truncated when the command fails,
    because a pipeline nobody can debug is a pipeline nobody runs.
    """
    try:
        finished = subprocess.run(spec["command"], input=document.encode("utf-8"),
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  timeout=int(spec.get("timeout_seconds", DEFAULT_TIMEOUT)))
    except FileNotFoundError:
        raise PipelineError("no such command: %s" % spec["command"][0]) from None
    except subprocess.TimeoutExpired:
        raise PipelineError("%s did not finish within %s seconds"
                            % (spec["command"][0], spec.get("timeout_seconds", DEFAULT_TIMEOUT))) from None
    if finished.returncode != 0:
        detail = finished.stderr.decode("utf-8", "replace").strip()[:200]
        raise PipelineError("%s exited %d%s" % (spec["command"][0], finished.returncode,
                                                (": " + detail) if detail else ""))
    return finished.stdout.decode("utf-8", "replace")


def model_transform(spec: dict, document: str) -> str:
    """The behaviour handoff_bench already had, as one pipeline kind among others."""
    entry = {"evaluator_id": "pipeline-model", "model": spec["model"], "endpoint": spec["endpoint"],
             "json_mode": False, "max_tokens": int(spec.get("max_tokens", 5000)),
             "extra_body": spec.get("extra_body"),
             "api_key_file": str(Path(spec["api_key_file"]).expanduser()) if spec.get("api_key_file") else "",
             "api_key_env": spec.get("api_key_env", "")}
    try:
        content, _served = call(entry, document + "\n\n" + spec["instruction"], entry["max_tokens"])
    except AdapterError as exc:
        raise PipelineError(str(exc)[:300]) from None
    return content


def document_transform(spec: dict, document: str) -> str:
    """No transformation. The ceiling every other arm is measured against."""
    return document


TRANSFORMS = {"http": http_transform, "command": command_transform,
              "model": model_transform, "document": document_transform}


def transform(spec: dict, document: str) -> str:
    return TRANSFORMS[spec["kind"]](spec, document)


def validate_spec(spec: object, where: str) -> dict:
    """Refuse a spec we cannot run, or one carrying a credential, before anything is called."""
    if not isinstance(spec, dict):
        raise SystemExit("%s must contain a JSON object" % where)
    kind = spec.get("kind")
    if kind not in REQUIRED:
        raise SystemExit("%s: kind must be one of %s, not %r" % (where, ", ".join(sorted(REQUIRED)), kind))
    missing = [field for field in REQUIRED[kind] if not spec.get(field)]
    if missing:
        raise SystemExit("%s: a %s pipeline needs %s" % (where, kind, ", ".join(missing)))
    name = spec.get("name") or ""
    if name and not ARM_NAME.fullmatch(str(name)):
        raise SystemExit("%s: name %r must be letters, digits, dashes or underscores" % (where, name))
    if kind == "http":
        if spec.get("headers"):
            # The one rule about credentials that a schema can enforce. Inline
            # headers end up in the repository and in report.json.
            raise SystemExit("%s: headers must live in a file named by headers_file, never inline in the spec"
                             % where)
        if not str(spec["url"]).lower().startswith(("http://", "https://")):
            raise SystemExit("%s: url must start with http:// or https://" % where)
        if not any(PLACEHOLDER in text for text in walk(spec["body"])):
            raise SystemExit("%s: the body template never mentions %s, so the document would not be sent"
                             % (where, PLACEHOLDER))
    if kind == "command":
        command = spec["command"]
        if not isinstance(command, list) or not command or not all(isinstance(part, str) for part in command):
            raise SystemExit("%s: command must be a non-empty list of strings, not a shell string; quoting "
                             "rules differ between machines and a run that depends on which machine ran it "
                             "is not a measurement" % where)
    for text in walk({key: value for key, value in spec.items() if key != "headers_file"}):
        if INLINE_SECRET.search(text):
            raise SystemExit("%s: this spec appears to contain a credential. Put it in a file and name that "
                             "file with headers_file (http) or read it from the environment inside your own "
                             "command; a spec is stored in the report and committed to repositories" % where)
    return spec


def load_spec(path: Path, fallback_name: str) -> dict:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit("no pipeline spec at %s" % path) from None
    except json.JSONDecodeError as exc:
        raise SystemExit("%s is not valid JSON: line %d" % (path, exc.lineno)) from None
    spec = validate_spec(loaded, str(path))
    spec["name"] = str(spec.get("name") or fallback_name)
    if not ARM_NAME.fullmatch(spec["name"]):
        raise SystemExit("%s: name %r must be letters, digits, dashes or underscores" % (path, spec["name"]))
    return spec


def describe(spec: dict) -> dict:
    """What goes into the report about a pipeline: enough to rerun it, no secrets.

    The headers file is named but never opened here, and a URL keeps its path
    and loses its query string for the same reason error messages do.
    """
    shown = {"name": spec["name"], "kind": spec["kind"]}
    if spec["kind"] == "http":
        shown.update({"url": redact_url(spec["url"]), "response_path": spec["response_path"],
                      "headers_file": spec.get("headers_file") or None})
    elif spec["kind"] == "command":
        shown["command"] = list(spec["command"])
    elif spec["kind"] == "model":
        shown.update({"endpoint": spec["endpoint"], "model": spec["model"]})
    return shown


def inspect_output(text: str, document: str, kind: str, max_chars: int) -> tuple[str | None, list[str]]:
    """Judge what came back before a reader ever sees it.

    Returns a refusal reason, or None, plus flags worth reporting either way.
    Returning the input unchanged is not treated as a failure — the pipeline
    answered — but it is the single most likely misconfiguration, it would score
    at the ceiling, and a number nobody questioned is worse than no number. So
    it is flagged, counted per arm, and printed at the top of the report.
    """
    flags: list[str] = []
    if not text.strip():
        return "the pipeline returned an empty string", flags
    if len(text) > max_chars:
        return ("the pipeline returned %d characters, over the %d allowed; a reader cannot be given that, and "
                "a run that silently truncates it measures the truncation" % (len(text), max_chars)), flags
    if kind != "document" and " ".join(text.split()) == " ".join(document.split()):
        flags.append("returned_input_unchanged")
    return None, flags


def run_case(case: dict, document: str, quiz: dict, rendered: list[dict], key: dict[str, str],
             reader: dict, out: Path, words: int | None, max_chars: int) -> dict:
    """One repeat of one arm: transform, check, read, grade. Stored, so a rerun resumes.

    The record uses handoff_bench's field names — `strategy`, `chain`, `grades`
    — because handoff_bench.summarise and handoff_bench.usability read them, and
    diagnose_report.py renders what those two produce. Calling an arm a
    "strategy" on disk is the price of not forking three files.
    """
    arm, repeat = case["arm"], case["repeat"]
    spec = case["spec"]
    stored = out / ("%s-%02d.json" % (arm, repeat))
    if stored.is_file():
        return json.loads(stored.read_text(encoding="utf-8"))
    record = {"strategy": arm, "repeat": repeat, "read_at": [1], "word_limit": words,
              "pipeline": describe(spec), "flags": [], "written_at_utc": now()}

    def failed(reason: str) -> dict:
        # Written down, never dropped. A silent failure removes exactly the runs
        # where a pipeline struggles, which are the runs that decide the verdict.
        record["error"] = reason[:300]
        (out / ("%s-%02d.failed.json" % (arm, repeat))).write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return record

    try:
        produced = transform(spec, document)
    except PipelineError as exc:
        return failed(str(exc))
    problem, flags = inspect_output(produced, document, spec["kind"], max_chars)
    record["flags"] = flags
    if problem:
        return failed(problem)
    text, cut = hb.trim(produced.strip(), words)
    record["chain"] = [{"hop": 1, "text": text, "words_written": len(produced.split()),
                        "words_kept": len(text.split()), "trimmed": cut, "sha256": sha256_text(text)}]
    prompt = hq.reader_prompt(quiz, rendered, text)
    try:
        content, _served = call(reader, prompt, int(reader.get("max_tokens", 5000)))
    except AdapterError as exc:
        return failed("reader: %s" % exc)
    answers, problems = hq.parse_answers(content, [item["id"] for item in rendered])
    if not answers:
        return failed("reader returned no usable answer")
    record["grades"] = {HOP: {"answers": answers, "problems": problems, **hq.grade(answers, key, rendered)}}
    stored.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return record


def complete_repeats(records: list[dict], arms: list[str]) -> list[dict]:
    """Only repeats that succeeded in every arm, ordered so the pairing is real.

    handoff_bench.summarise pairs an arm against the control by zipping the two
    lists positionally. That is correct only while both lists hold the same
    repeats in the same order. If repeat 3 fails in one arm and repeat 4 in the
    other, the zip pairs repeat 4 of one with repeat 3 of the other and the
    paired interval quietly becomes an unpaired one. Dropping a repeat that did
    not complete everywhere, and sorting what is left, makes the pairing hold
    without changing the shared function. The dropped runs are still counted in
    full by usability(), which is what decides whether any of this is reportable.
    """
    graded: dict[str, set[int]] = {arm: set() for arm in arms}
    for record in records:
        if "grades" in record and record.get("strategy") in graded:
            graded[record["strategy"]].add(record["repeat"])
    shared = set.intersection(*graded.values()) if graded else set()
    return sorted((record for record in records
                   if record.get("strategy") in graded and "grades" in record and record["repeat"] in shared),
                  key=lambda record: (record["strategy"], record["repeat"]))


def flags_by_arm(records: list[dict], arms: list[str], flag: str) -> dict[str, int]:
    return {arm: sum(1 for record in records
                     if record.get("strategy") == arm and flag in (record.get("flags") or []))
            for arm in arms}


def frozen_arms(records: list[dict], arms: dict[str, dict]) -> list[str]:
    """Arms whose every completed repeat produced byte-identical text.

    A deterministic pipeline and a temperature-zero reader produce the same
    answers every time, a standard deviation of zero, and an interval of zero
    width that looks decisive and measures nothing but itself. Naming it is the
    only defence, because every downstream renderer will read that interval as
    resolved.

    The untransformed-document arm is skipped: it is constant by definition, and
    a warning that fires on every run teaches a reader to ignore it.
    """
    frozen = []
    for arm, spec in arms.items():
        if spec.get("kind") == "document":
            continue
        digests = {step["sha256"] for record in records if record.get("strategy") == arm
                   for step in record.get("chain", [])}
        if len(digests) == 1 and sum(1 for r in records if r.get("strategy") == arm and "grades" in r) > 1:
            frozen.append(arm)
    return sorted(frozen)


def render_report(tables: dict, meta: dict, control: str) -> str:
    """handoff_bench's report, with what is specific to a customer's pipeline added.

    The tables and — more importantly — the refusal banner above them are
    rendered by handoff_bench so that the unusable-run rule has exactly one
    implementation. Everything appended below is about the pipelines themselves:
    what they are, whether any of them handed the document straight back, and
    whether any of them moved at all between repeats.
    """
    lines = [hb.render_report(tables, meta, control).rstrip(), ""]
    lines += ["## What was measured", "",
              "| Arm | Kind | Where |", "|---|---|---|"]
    for arm, shown in sorted(meta.get("arms", {}).items()):
        where = (shown.get("url") or shown.get("endpoint")
                 or (" ".join(shown["command"]) if shown.get("command") else "the document itself"))
        lines.append("| %s%s | %s | `%s` |" % (arm, " (baseline)" if arm == control else "", shown["kind"], where))
    lines.append("")
    unchanged = {arm: count for arm, count in (meta.get("unchanged_by_arm") or {}).items() if count}
    if unchanged:
        lines += ["**A pipeline handed the document back unchanged.** %s. An arm that returns its input scores "
                  "at the ceiling and measures nothing; this is almost always a misconfigured response path or "
                  "a pass-through mode left switched on. The numbers above for that arm are not a result."
                  % "; ".join("`%s` on %d of %d runs" % (arm, count, meta["repeats"])
                              for arm, count in sorted(unchanged.items())), ""]
    if meta.get("identical_output_arms"):
        lines += ["Every completed run of %s produced byte-identical text, so those intervals describe the "
                  "reader's variation alone and not the pipeline's. A narrow interval there is a property "
                  "of a deterministic pipeline, not strength of evidence."
                  % ", ".join("`%s`" % arm for arm in meta["identical_output_arms"]), ""]
    lines += ["Pairs analysed: %d of %d requested. A repeat that failed in any arm is dropped from every arm, "
              "so the difference above is genuinely paired; every failure is still counted in full by the "
              "usability verdict." % (meta.get("pairs_analysed", 0), meta["repeats"]), ""]
    return "\n".join(lines) + "\n"


def dry_run(arms: dict[str, dict], document: str, max_chars: int) -> int:
    """Call each pipeline once, report what came back, and ask no reader anything.

    This is the cheap way to find out that a response path is wrong or that a
    service is echoing its input, before spending a reader call per repeat.
    """
    worst = 0
    for arm, spec in sorted(arms.items()):
        try:
            produced = transform(spec, document)
        except PipelineError as exc:
            print("%s: FAILED - %s" % (arm, exc), flush=True)
            worst = 1
            continue
        problem, flags = inspect_output(produced, document, spec["kind"], max_chars)
        detail = "%d characters, %d words, sha256 %s" % (len(produced), len(produced.split()),
                                                         sha256_text(produced)[:12])
        if problem:
            print("%s: FAILED - %s" % (arm, problem), flush=True)
            worst = 1
        elif flags:
            print("%s: %s - %s" % (arm, ", ".join(flags), detail), flush=True)
            worst = max(worst, 1)
        else:
            print("%s: ok - %s" % (arm, detail), flush=True)
    return worst


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--document", type=Path, required=True)
    parser.add_argument("--quiz", type=Path, required=True)
    parser.add_argument("--pipeline", type=Path, required=True, help="the pipeline spec to measure")
    parser.add_argument("--baseline", type=Path,
                        help="a second spec to compare against (default: the untransformed document, which is "
                             "the ceiling a pipeline can only lose against)")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--words", type=int, default=None,
                        help="cut every arm's output to this many words. Leave unset when comparing two "
                             "pipelines; set it when one arm is much longer than the other and you want to "
                             "know whether it is the content or the length that carried the facts")
    parser.add_argument("--max-output-chars", type=int, default=None,
                        help="refuse an output longer than this (default: 20x the document, floor 50000)")
    parser.add_argument("--reader-model", default="openai/gpt-oss-120b",
                        help="the blind reader. Use a model unrelated to anything inside your pipeline")
    parser.add_argument("--reader-endpoint", default="https://openrouter.ai/api/v1/chat/completions")
    parser.add_argument("--reader-api-key-file",
                        help="path to a file holding the reader's API key. It is opened by the adapter at call "
                             "time and is never printed, logged or stored")
    parser.add_argument("--reader-api-key-env", help="environment variable holding the reader's API key instead")
    parser.add_argument("--reader-max-tokens", type=int, default=5000)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--dry-run", action="store_true",
                        help="run each pipeline once, report what it returned, and call no reader")
    args = parser.parse_args()

    if args.repeats < 1:
        raise SystemExit("--repeats must be at least 1")
    document = args.document.read_text(encoding="utf-8")
    max_chars = args.max_output_chars or max(50000, 20 * len(document))

    pipeline = load_spec(args.pipeline, args.pipeline.stem)
    if args.baseline:
        baseline = load_spec(args.baseline, args.baseline.stem)
    else:
        baseline = validate_spec({"kind": "document", "name": "document"}, "the default baseline")
    if baseline["name"] == pipeline["name"]:
        raise SystemExit("both arms are called %r; give one of the specs a distinct \"name\""
                         % pipeline["name"])
    arms = {pipeline["name"]: pipeline, baseline["name"]: baseline}
    control = baseline["name"]

    if args.dry_run:
        raise SystemExit(dry_run(arms, document, max_chars))

    if not (args.reader_api_key_file or args.reader_api_key_env):
        raise SystemExit("the reader needs a key: pass --reader-api-key-file or --reader-api-key-env")
    if args.reader_api_key_file:
        # Existence and size only. Reading the file here would put the key into
        # this process for no reason; the adapter needs it and this script
        # does not, and a run that dies after fifty calls because the path was
        # wrong is the most expensive way to learn it.
        key_file = Path(args.reader_api_key_file).expanduser()
        if not key_file.is_file():
            raise SystemExit("no API key file at %s; write the key into that file (one line) and run again"
                             % key_file)
        if key_file.stat().st_size == 0:
            raise SystemExit("the API key file %s is empty" % key_file)
    reader = {"evaluator_id": "pipeline-reader", "model": args.reader_model, "endpoint": args.reader_endpoint,
              "json_mode": False, "max_tokens": args.reader_max_tokens,
              "extra_body": {"reasoning": {"effort": "low"}},
              "api_key_file": str(Path(args.reader_api_key_file).expanduser()) if args.reader_api_key_file else "",
              "api_key_env": args.reader_api_key_env or ""}

    quiz = json.loads(args.quiz.read_text(encoding="utf-8"))
    rendered, key = hq.render_quiz(quiz, args.document.name + ":" + quiz["quiz_version"])
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "answer-key.json").write_text(
        json.dumps({"key": key, "rendered": rendered}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    cases = [{"arm": name, "repeat": index, "spec": spec}
             for name, spec in arms.items() for index in range(1, args.repeats + 1)]
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        records = list(pool.map(lambda case: run_case(case, document, quiz, rendered, key, reader,
                                                      args.out, args.words, max_chars), cases))

    names = sorted(arms)
    failed = [record for record in records if "grades" not in record]
    analysed = complete_repeats(records, names)
    tables = {HOP: hb.summarise(analysed, int(HOP), control)}
    meta = {"document": args.document.name,
            "fact_questions": sum(1 for item in rendered if item["kind"] == "fact"),
            "absent_questions": sum(1 for item in rendered if item["kind"] == "absent"),
            "read_at": [int(HOP)], "repeats": args.repeats,
            # handoff_bench wrote a model name here and diagnose_report prints it
            # as "Writer". For a pipeline the honest answer is the spec, so the
            # spec is what it prints.
            "generator": "%s (%s)" % (pipeline["name"], pipeline["kind"]),
            "reader": args.reader_model, "word_limit": args.words,
            "failed_runs": len(failed),
            "failures": [{"strategy": record["strategy"], "repeat": record["repeat"],
                          "error": record.get("error", "")[:160]} for record in failed],
            "usability": hb.usability(records, names),
            "control": control, "arms": {name: describe(spec) for name, spec in arms.items()},
            "pairs_analysed": len(analysed) // max(1, len(names)),
            "unchanged_by_arm": flags_by_arm(records, names, "returned_input_unchanged"),
            "identical_output_arms": frozen_arms(records, arms),
            "max_output_chars": max_chars}
    (args.out / "report.json").write_text(
        json.dumps({"meta": meta, "by_hop": tables}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (args.out / "report.md").write_text(render_report(tables, meta, control), encoding="utf-8")
    print(json.dumps({"out": str(args.out), "control": control, "failed_runs": len(failed),
                      "pairs_analysed": meta["pairs_analysed"],
                      "unchanged_by_arm": meta["unchanged_by_arm"],
                      "usable": meta["usability"]["usable"], "by_hop": tables}, indent=2, ensure_ascii=False))
    print("\nbuyer-facing page: python scripts/diagnose_report.py --bench %s --out %s --control %s "
          "--document %s --quiz %s" % (args.out, args.out / "page", control, args.document, args.quiz), flush=True)


if __name__ == "__main__":
    main()
