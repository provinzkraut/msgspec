"""
Aggregate the benchmark results into a single Bencher Metric Format (BMF)
document, ready to upload to https://bencher.dev via ``bencher run --adapter json``.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

# conversion factors to nanoseconds for the`'latency' measure.
S_TO_NS = 1e9
MS_TO_NS = 1e6
US_TO_NS = 1e3


def _run(module, *extra_args):
    """Run a benchmark module with ``--json`` and yield its parsed result rows."""
    output = subprocess.check_output(
        [sys.executable, "-m", module, "--json", *extra_args]
    )
    for line in output.decode().splitlines():
        line = line.strip()
        if line:
            yield json.loads(line)


def _latency(value):
    return {"latency": {"value": value}}


def _is_msgspec(label):
    return "msgspec" in label.lower()


def collect_encodings():
    results = {}
    for protocol in ("json", "msgpack"):
        # Select only msgspec's own benchmarks, so the comparison libraries don't
        # need to be installed.
        rows = _run(
            "benchmarks.bench_encodings",
            "-p",
            protocol,
            "-b",
            "msgspec structs",
            "msgspec",
        )
        for row in rows:
            name = f"encodings/{protocol}/{row['label']}"
            results[f"{name}/encode"] = _latency(row["encode"] * S_TO_NS)
            results[f"{name}/decode"] = _latency(row["decode"] * S_TO_NS)
    return results


def collect_structs():
    results = {}
    for row in _run("benchmarks.bench_structs", "-b", "msgspec"):
        for op in ("import", "create", "equality", "order"):
            value = row[op]
            if value is None:
                continue
            results[f"structs/{row['label']}/{op}"] = _latency(value * US_TO_NS)
    return results


def collect_gc():
    results = {}
    for row in _run("benchmarks.bench_gc"):
        if not _is_msgspec(row["label"]):
            continue
        results[f"gc/{row['label']}"] = {
            "latency": {"value": row["gc_time"] * MS_TO_NS},
            "memory": {"value": row["memory"]},
        }
    return results


def collect_validation():
    results = {}
    for row in _run("benchmarks.bench_validation", "--lib", "msgspec"):
        name = f"validation/{row['label']}"
        results[f"{name}/encode"] = _latency(row["encode"] * S_TO_NS)
        results[f"{name}/decode"] = _latency(row["decode"] * S_TO_NS)
        results[name] = {"memory": {"value": row["memory"]}}
    return results


def collect_large_json():
    results = {}
    # `-b msgspec` runs only the msgspec benchmark (plus its "msgspec structs"
    # baseline), so the comparison libraries don't need to be installed.
    for row in _run("benchmarks.bench_large_json", "-b", "msgspec"):
        if not _is_msgspec(row["label"]):
            continue
        results[f"large_json/{row['label']}"] = {
            "latency": {"value": row["time"] * MS_TO_NS},
            "memory": {"value": row["memory"]},
        }
    return results


def collect_file_size():
    # Track the size of the compiled extension (the bulk of msgspec's footprint)
    # as a Bencher "File Size" measure, in bytes. We emit it in the BMF rather than
    # using `bencher run --file-size`, because that flag treats the benchmark
    # command as a build command and discards its stdout -- so the timing/memory
    # benchmarks would be lost. Measured in-process, since the aggregator runs
    # inside the image where msgspec is installed.
    import os

    import msgspec._core

    size = os.path.getsize(msgspec._core.__file__)
    return {"msgspec_core.so": {"file-size": {"value": size}}}


COLLECTORS = {
    "encodings": collect_encodings,
    "structs": collect_structs,
    "gc": collect_gc,
    "validation": collect_validation,
    "large_json": collect_large_json,
    "file_size": collect_file_size,
}

# can't run 'large_json' at the moment, since it requires a download, which isn't available
# at bench runtime, and would blow up the docker image.
# TODO: Figure out a way to properly handle this
DEFAULT_BENCHMARKS = ["encodings", "structs", "gc", "validation", "file_size"]


def main():
    parser = argparse.ArgumentParser(
        description="Emit combined Bencher Metric Format (BMF) JSON for the benchmarks"
    )
    parser.add_argument(
        "--include",
        nargs="*",
        choices=list(COLLECTORS),
        default=DEFAULT_BENCHMARKS,
        metavar="NAME",
        help=(
            "Benchmarks to include. Defaults to the network-free benchmarks: "
            + ", ".join(DEFAULT_BENCHMARKS)
        ),
    )
    parser.add_argument(
        "--exclude",
        nargs="*",
        choices=list(COLLECTORS),
        default=[],
        metavar="NAME",
        help="Benchmarks to exclude from the included set.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Write BMF JSON to this path instead of stdout.",
    )
    args = parser.parse_args()

    selected = [name for name in args.include if name not in args.exclude]

    metrics = {}
    for name in selected:
        print(f"Running {name} benchmark...", file=sys.stderr)
        metrics.update(COLLECTORS[name]())

    text = json.dumps(metrics, indent=2)
    if args.output:
        with open(args.output, "w") as f:
            f.write(text)
    else:
        print(text)


if __name__ == "__main__":
    main()
