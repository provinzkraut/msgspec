from __future__ import annotations

import dataclasses
import importlib.metadata
import json
import sys
import timeit
from typing import Any, Callable, Literal

import msgspec

from .generate_data import make_filesystem_data

# The benchmark names selectable via `--bench-name`, per protocol. Each library
# is only imported when its benchmark is selected, so unselected ones don't need
# to be installed (the continuous-benchmarking image ships msgspec alone).
JSON_BENCHMARK_NAMES = [
    "msgspec structs",
    "msgspec",
    "json",
    "orjson",
    "ujson",
    "rapidjson",
    "simdjson",
]
MSGPACK_BENCHMARK_NAMES = [
    "msgspec structs",
    "msgspec",
    "msgpack",
    "ormsgpack",
]
# De-duplicated union (preserving order), used for the `--bench-name` choices.
BENCHMARK_NAMES = list(dict.fromkeys(JSON_BENCHMARK_NAMES + MSGPACK_BENCHMARK_NAMES))


class File(msgspec.Struct, kw_only=True, omit_defaults=True, tag="file"):
    name: str
    created_by: str
    created_at: str
    updated_by: str | None = None
    updated_at: str | None = None
    nbytes: int
    permissions: Literal["READ", "WRITE", "READ_WRITE"]


class Directory(msgspec.Struct, kw_only=True, omit_defaults=True, tag="directory"):
    name: str
    created_by: str
    created_at: str
    updated_by: str | None = None
    updated_at: str | None = None
    contents: list[File | Directory]


@dataclasses.dataclass
class Benchmark:
    label: str
    version: str
    encode: Callable
    decode: Callable
    schema: Any = None

    def run(self, data: bytes) -> dict:
        if self.schema is not None:
            data = msgspec.convert(data, self.schema)
        timer = timeit.Timer("func(data)", globals={"func": self.encode, "data": data})
        n, t = timer.autorange()
        encode_time = t / n

        data = self.encode(data)

        timer = timeit.Timer("func(data)", globals={"func": self.decode, "data": data})
        n, t = timer.autorange()
        decode_time = t / n

        return {
            "label": self.label,
            "encode": encode_time,
            "decode": decode_time,
        }


def json_benchmarks(selected):
    enc = msgspec.json.Encoder()
    dec = msgspec.json.Decoder(Directory)
    dec2 = msgspec.json.Decoder()

    benchmarks = []
    if "msgspec structs" in selected:
        benchmarks.append(
            Benchmark("msgspec structs", None, enc.encode, dec.decode, Directory)
        )
    if "msgspec" in selected:
        benchmarks.append(
            Benchmark("msgspec", msgspec.__version__, enc.encode, dec2.decode)
        )
    if "json" in selected:
        benchmarks.append(Benchmark("json", None, json.dumps, json.loads))
    if "orjson" in selected:
        import orjson

        benchmarks.append(
            Benchmark("orjson", orjson.__version__, orjson.dumps, orjson.loads)
        )
    if "ujson" in selected:
        import ujson

        benchmarks.append(
            Benchmark(
                "ujson", ujson.__version__, lambda obj: ujson.dumps(obj), ujson.loads
            )
        )
    if "rapidjson" in selected:
        import rapidjson

        benchmarks.append(
            Benchmark(
                "rapidjson",
                rapidjson.__version__,
                rapidjson.Encoder(),
                rapidjson.Decoder(),
            )
        )
    if "simdjson" in selected:
        import simdjson

        benchmarks.append(
            Benchmark(
                "simdjson",
                importlib.metadata.version("pysimdjson"),
                simdjson.dumps,
                simdjson.loads,
            )
        )

    return benchmarks


def msgpack_benchmarks(selected):
    enc = msgspec.msgpack.Encoder()
    dec = msgspec.msgpack.Decoder(Directory)
    dec2 = msgspec.msgpack.Decoder()

    benchmarks = []
    if "msgspec structs" in selected:
        benchmarks.append(
            Benchmark("msgspec structs", None, enc.encode, dec.decode, Directory)
        )
    if "msgspec" in selected:
        benchmarks.append(
            Benchmark("msgspec", msgspec.__version__, enc.encode, dec2.decode)
        )
    if "msgpack" in selected:
        import msgpack

        benchmarks.append(
            Benchmark("msgpack", msgpack.__version__, msgpack.dumps, msgpack.loads)
        )
    if "ormsgpack" in selected:
        import ormsgpack

        benchmarks.append(
            Benchmark(
                "ormsgpack", ormsgpack.__version__, ormsgpack.packb, ormsgpack.unpackb
            )
        )

    return benchmarks


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Benchmark different python serialization libraries"
    )
    parser.add_argument(
        "-b",
        "--bench-name",
        dest="bench_names",
        nargs="*",
        choices=BENCHMARK_NAMES,
        default=BENCHMARK_NAMES,
        help="A list of benchmark names to run. Defaults to all.",
    )
    parser.add_argument(
        "--versions",
        action="store_true",
        help="Output library version info, and exit immediately",
    )
    parser.add_argument(
        "-n",
        type=int,
        help="The number of objects in the generated data, defaults to 1000",
        default=1000,
    )
    parser.add_argument(
        "-p",
        "--protocol",
        choices=["json", "msgpack"],
        default="json",
        help="The protocol to benchmark, defaults to JSON",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="whether to output the results as json",
    )
    args = parser.parse_args()

    selected = set(args.bench_names)
    benchmarks = (
        json_benchmarks(selected)
        if args.protocol == "json"
        else msgpack_benchmarks(selected)
    )

    if args.versions:
        for bench in benchmarks:
            if bench.version is not None:
                print(f"- {bench.label}: {bench.version}")
        sys.exit(0)

    data = make_filesystem_data(args.n)

    results = [benchmark.run(data) for benchmark in benchmarks]

    if args.json:
        for line in results:
            print(json.dumps(line))
    else:
        # Compose the results table
        results.sort(key=lambda row: row["encode"] + row["decode"])
        best_et = results[0]["encode"]
        best_dt = results[0]["decode"]
        best_tt = best_et + best_dt

        columns = (
            "",
            "encode (μs)",
            "vs.",
            "decode (μs)",
            "vs.",
            "total (μs)",
            "vs.",
        )
        rows = [
            (
                r["label"],
                f"{1_000_000 * r['encode']:.1f}",
                f"{r['encode'] / best_et:.1f}",
                f"{1_000_000 * r['decode']:.1f}",
                f"{r['decode'] / best_dt:.1f}",
                f"{1_000_000 * (r['encode'] + r['decode']):.1f}",
                f"{(r['encode'] + r['decode']) / best_tt:.1f}",
            )
            for r in results
        ]
        widths = tuple(
            max(max(map(len, x)), len(c)) for x, c in zip(zip(*rows), columns)
        )
        row_template = ("|" + (" %%-%ds |" * len(columns))) % widths
        header = row_template % tuple(columns)
        bar_underline = "+%s+" % "+".join("=" * (w + 2) for w in widths)
        bar = "+%s+" % "+".join("-" * (w + 2) for w in widths)
        parts = [bar, header, bar_underline]
        for r in rows:
            parts.append(row_template % r)
            parts.append(bar)
        print("\n".join(parts))


if __name__ == "__main__":
    main()
