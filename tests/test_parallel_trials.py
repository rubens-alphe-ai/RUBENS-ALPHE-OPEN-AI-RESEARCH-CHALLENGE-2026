"""Running trials in parallel changes the wall clock, not the evidence."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_blind_trials as rbt  # noqa: E402


class FakeAdapter:
    """Records how many requests overlap, and answers with the trial's seed."""

    live = 0
    peak = 0
    lock = threading.Lock()

    def __init__(self, config):
        self.config = config
        self.last_served_model = config.model

    def generate(self, prompt: str, seed: int) -> str:
        with FakeAdapter.lock:
            FakeAdapter.live += 1
            FakeAdapter.peak = max(FakeAdapter.peak, FakeAdapter.live)
        try:
            threading.Event().wait(0.05)
            return "handoff for seed %d" % seed
        finally:
            with FakeAdapter.lock:
                FakeAdapter.live -= 1


def manifest_for(folder: Path, count: int) -> Path:
    results = folder / "experiments" / "PROP-EXP-TEST" / "results"
    results.mkdir(parents=True)
    (results.parent / "TEST_PROMPT.md").write_text("Answer.", encoding="utf-8")
    (results.parent / "STATE.txt").write_text("The state.", encoding="utf-8")
    trials = []
    for index in range(count):
        for condition in ("baseline", "structured"):
            trials.append({"trial_id": "%s-%d" % (condition, index), "pair_id": "pair-%d" % index,
                           "seed": 100 + index, "condition": condition,
                           "state_path": "experiments/PROP-EXP-TEST/STATE.txt",
                           "output_path": "experiments/PROP-EXP-TEST/results/%s_trial_%02d.txt" % (condition, index),
                           "protocol_sha256": "a" * 64, "prompt_sha256": "b" * 64, "state_sha256": "c" * 64})
    path = results / "experiment-manifest.json"
    path.write_text(json.dumps({"experiment_id": "PROP-EXP-TEST", "trials": trials}), encoding="utf-8")
    return path


def arguments(root: Path, manifest: Path, workers: int) -> argparse.Namespace:
    return argparse.Namespace(root=root, manifest=manifest, condition="all", provider="openai-compatible",
                              model="test-model", endpoint="https://x.invalid/v1", temperature=0.8,
                              max_output_tokens=500, timeout_seconds=60, think=None, dry_run=False,
                              overwrite=False, retries=0, min_free_mb=0, memory_wait_seconds=0, resume=True,
                              workers=workers, api_key_env="", api_key_file="", extra_body=None)


class ParallelTrialTests(unittest.TestCase):
    def run_with(self, workers: int, pairs: int = 4) -> tuple[Path, int]:
        FakeAdapter.live = FakeAdapter.peak = 0
        folder = Path(tempfile.mkdtemp())
        manifest = manifest_for(folder, pairs)
        with mock.patch.object(rbt, "build_adapter", FakeAdapter):
            rbt.run(arguments(folder, manifest, workers))
        return folder, FakeAdapter.peak

    def test_parallel_writes_every_output_and_overlaps(self) -> None:
        folder, peak = self.run_with(workers=4)
        outputs = sorted((folder / "experiments" / "PROP-EXP-TEST" / "results").glob("*_trial_*.txt"))
        self.assertEqual(len(outputs), 8)
        self.assertGreater(peak, 1)

    def test_sequential_never_overlaps(self) -> None:
        _, peak = self.run_with(workers=1)
        self.assertEqual(peak, 1)

    def test_same_answers_either_way(self) -> None:
        parallel, _ = self.run_with(workers=4)
        sequential, _ = self.run_with(workers=1)
        results = lambda folder: {path.name: path.read_text(encoding="utf-8")
                                  for path in (folder / "experiments" / "PROP-EXP-TEST" / "results").glob("*_trial_*.txt")}
        self.assertEqual(results(parallel), results(sequential))

    def test_metadata_records_the_experiment_and_hash(self) -> None:
        folder, _ = self.run_with(workers=3, pairs=2)
        metadata = json.loads((folder / "experiments" / "PROP-EXP-TEST" / "results" / "baseline_trial_00.metadata.json")
                              .read_text(encoding="utf-8"))
        self.assertEqual(metadata["experiment_id"], "PROP-EXP-TEST")
        self.assertEqual(len(metadata["output_sha256"]), 64)

    def test_resume_skips_what_exists(self) -> None:
        folder, _ = self.run_with(workers=4, pairs=2)
        before = {path: path.stat().st_mtime_ns
                  for path in (folder / "experiments" / "PROP-EXP-TEST" / "results").glob("*_trial_*.txt")}
        manifest = folder / "experiments" / "PROP-EXP-TEST" / "results" / "experiment-manifest.json"
        with mock.patch.object(rbt, "build_adapter", FakeAdapter):
            rbt.run(arguments(folder, manifest, 4))
        after = {path: path.stat().st_mtime_ns for path in before}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
