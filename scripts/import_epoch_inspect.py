#!/usr/bin/env python3
"""Per-item results from Epoch AI's public Inspect logs, without downloading them.

Epoch AI links a public Inspect `.eval` log to many of its benchmark runs (data
under CC BY 4.0). A log is a zip archive. Most of its bulk is full transcripts —
one SWE-bench Verified log tried here was over eight gigabytes — while the
per-sample scores sit in one member, `summaries.json`, of a few megabytes.

So this reads the archive remotely: the end of the file for the central
directory, then only that member, with HTTP range requests. Gigabytes become
megabytes, and nothing large is written to disk.

COMPRESSION. Inspect writes some logs with deflate and newer ones with zstd.
Python's standard library reads deflate only. zstd needs the `zstandard`
package; when it is missing, a zstd log is refused by name rather than skipped
quietly, because a silent skip would drop models from the panel without saying
which.

GAPS ARE NOT FAILURES. A sample with no score — the run errored — is a gap, not
a wrong answer. The table keeps only the items every kept model has a score
for, and reports how many it dropped and why.

  python scripts/import_epoch_inspect.py --epoch-zip benchmark_data.zip \
      --benchmark swe_bench_verified --out swe.csv --manifest swe.provenance.json
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import struct
import sys
import time
import urllib.request
import zipfile
import zlib
from pathlib import Path

AGENT = "RA-PSI-public-audit/1.0 (psychometric re-analysis of published results)"
MEMBER = "summaries.json"


def fetch_range(url: str, start: int, end: int) -> bytes:
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": AGENT, "Range": "bytes=%d-%d" % (start, end)})
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read()
        except Exception:  # noqa: BLE001
            if attempt == 3:
                raise
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("unreachable")


def content_length(url: str) -> int:
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return int(response.headers["Content-Length"])


def central_directory(url: str, size: int) -> tuple[int, int]:
    tail = fetch_range(url, max(0, size - 66000), size - 1)
    eocd = tail.rfind(b"PK\x05\x06")
    if eocd < 0:
        raise ValueError("no end-of-central-directory record")
    cd_size, cd_offset = struct.unpack("<II", tail[eocd + 12:eocd + 20])
    if cd_offset == 0xFFFFFFFF or cd_size == 0xFFFFFFFF:
        locator = tail.rfind(b"PK\x06\x07", 0, eocd)
        zip64_offset = struct.unpack("<Q", tail[locator + 8:locator + 16])[0]
        record = fetch_range(url, zip64_offset, zip64_offset + 55)
        cd_size, cd_offset = struct.unpack("<QQ", record[40:56])
    return cd_offset, cd_size


def find_member(directory: bytes, name: str) -> tuple[int, int, int]:
    pos = 0
    while pos < len(directory) and directory[pos:pos + 4] == b"PK\x01\x02":
        method = struct.unpack("<H", directory[pos + 10:pos + 12])[0]
        comp, _uncomp = struct.unpack("<II", directory[pos + 20:pos + 28])
        n, e, c = struct.unpack("<HHH", directory[pos + 28:pos + 34])
        offset = struct.unpack("<I", directory[pos + 42:pos + 46])[0]
        filename = directory[pos + 46:pos + 46 + n].decode("utf-8")
        extra = directory[pos + 46 + n:pos + 46 + n + e]
        if filename == name:
            if comp == 0xFFFFFFFF or offset == 0xFFFFFFFF:
                # zip64 extra field: values appear in order, only those that overflowed
                i = 0
                while i < len(extra):
                    tag, length = struct.unpack("<HH", extra[i:i + 4])
                    if tag == 0x0001:
                        values = list(struct.unpack("<%dQ" % (length // 8), extra[i + 4:i + 4 + length]))
                        if _uncomp == 0xFFFFFFFF:
                            values.pop(0)
                        if comp == 0xFFFFFFFF:
                            comp = values.pop(0)
                        if offset == 0xFFFFFFFF:
                            offset = values.pop(0)
                    i += 4 + length
            return method, comp, offset
        pos += 46 + n + e + c
    raise KeyError(name)


def read_member(url: str, name: str = MEMBER) -> bytes:
    size = content_length(url)
    cd_offset, cd_size = central_directory(url, size)
    method, comp, offset = find_member(fetch_range(url, cd_offset, cd_offset + cd_size - 1), name)
    header = fetch_range(url, offset, offset + 29)
    n, e = struct.unpack("<HH", header[26:30])
    data = fetch_range(url, offset + 30 + n + e, offset + 30 + n + e + comp - 1)
    if method == zipfile.ZIP_STORED:
        return data
    if method == zipfile.ZIP_DEFLATED:
        return zlib.decompress(data, -15)
    if method == 93:
        try:
            import zstandard
        except ImportError:
            raise SystemExit("%s is zstd-compressed, which Python's standard library cannot read; "
                             "install the `zstandard` package to include it" % url)
        return zstandard.ZstdDecompressor().stream_reader(io.BytesIO(data)).read()
    raise SystemExit("%s uses compression method %d, which this reader does not handle" % (url, method))


def outcomes(summaries: list[dict]) -> tuple[dict[str, int], dict]:
    got: dict[str, int] = {}
    notes = {"no_score": 0, "not_binary": 0, "repeated": 0}
    for sample in summaries:
        scores = sample.get("scores") or {}
        if not scores:
            notes["no_score"] += 1
            continue
        value = next(iter(scores.values())).get("value")
        if value in ("C", 1, 1.0, True):
            bit = 1
        elif value in ("I", 0, 0.0, False):
            bit = 0
        else:
            notes["not_binary"] += 1
            continue
        key = str(sample["id"])
        if key in got:
            notes["repeated"] += 1
            continue
        got[key] = bit
    return got, notes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--epoch-zip", type=Path, required=True)
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    archive = zipfile.ZipFile(args.epoch_zip)
    rows = list(csv.DictReader(io.StringIO(archive.read(args.benchmark + ".csv").decode("utf-8"))))
    runs = [(r["Model version"], r["Logs"].strip()) for r in rows if r.get("Logs", "").strip().endswith(".eval")]
    per_model: dict[str, dict[str, int]] = {}
    provenance = []
    for model, url in runs:
        record = {"model": model, "url": url}
        try:
            raw = read_member(url)
        except SystemExit as refusal:
            record["refused"] = str(refusal)
            provenance.append(record)
            print("refused", model, file=sys.stderr)
            continue
        except Exception as exc:  # noqa: BLE001
            record["unreachable"] = str(exc)[:200]
            provenance.append(record)
            print("unreachable", model, exc, file=sys.stderr)
            continue
        record["summaries_sha256"] = hashlib.sha256(raw).hexdigest()
        got, notes = outcomes(json.loads(raw))
        record.update({"samples_scored": len(got), **notes})
        provenance.append(record)
        if model in per_model:
            record["duplicate_model_skipped"] = True
            continue
        per_model[model] = got
        print("ok", model, len(got), file=sys.stderr)

    if not per_model:
        raise SystemExit("no log could be read")
    common = set.intersection(*(set(v) for v in per_model.values()))
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["trial", "item", "correct"])
        for model, got in per_model.items():
            for item in sorted(common):
                writer.writerow([model, item, got[item]])
    args.manifest.write_text(json.dumps({
        "record_version": "RA-PSI-EPOCH-INSPECT-V1",
        "source": "Epoch AI, Capabilities & benchmarking, https://epoch.ai/benchmarks, CC BY 4.0",
        "benchmark": args.benchmark,
        "models_kept": len(per_model),
        "items_common_to_every_kept_model": len(common),
        "items_seen_at_all": len(set().union(*(set(v) for v in per_model.values()))),
        "runs": provenance,
    }, indent=1), encoding="utf-8")
    print(json.dumps({"models": len(per_model), "common_items": len(common)}))


if __name__ == "__main__":
    main()
