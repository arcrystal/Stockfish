#!/usr/bin/env python3
"""Interleaved, fixed-work timing for an exact-output engine optimization."""
import argparse
import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import subprocess
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    binaries = {name: getattr(args, name).resolve() for name in ("base", "candidate")}
    metadata = {
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "purpose": "Predeclared 20 paired whole-engine fixed-depth benchmarks; no Elo estimate.",
        "bench_args": ["bench", "16", "1", "15", "default", "depth"],
        "method": "One warmup per engine, then 20 pairs in alternating AB/BA order. No discarded runs.",
        "inputs": {name: {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                   for name, path in binaries.items()},
        "runs": [],
    }
    metadata_path = args.output / "timings.json"

    def save():
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")

    save()
    expected_nodes = None
    for pair in range(-1, 20):
        order = ("base", "candidate") if pair % 2 == 0 or pair == -1 else ("candidate", "base")
        for name in order:
            started = time.perf_counter()
            result = subprocess.run([str(binaries[name]), *metadata["bench_args"]],
                                    capture_output=True, check=True)
            wall = time.perf_counter() - started
            prefix = "warmup" if pair == -1 else f"pair-{pair + 1:02}"
            (args.output / f"{prefix}-{name}.stdout").write_bytes(result.stdout)
            (args.output / f"{prefix}-{name}.stderr").write_bytes(result.stderr)
            log = result.stderr.decode()
            nodes = int(re.search(r"Nodes searched\s*:\s*(\d+)", log)[1])
            search_ms = int(re.search(r"Total time \(ms\)\s*:\s*(\d+)", log)[1])
            if expected_nodes is None:
                expected_nodes = nodes
            if nodes != expected_nodes:
                raise RuntimeError(f"Fixed work differs: expected {expected_nodes}, got {nodes}")
            metadata["runs"].append({"pair": pair + 1, "warmup": pair == -1, "engine": name,
                                     "nodes": nodes, "search_ms": search_ms, "wall_seconds": wall})
            save()
        print(f"Completed {'warmup' if pair == -1 else f'pair {pair + 1}/20'}", flush=True)

    def summarize(field):
        differences = []
        for pair in range(1, 21):
            values = {run["engine"]: run[field] for run in metadata["runs"] if run["pair"] == pair}
            differences.append(math.log(values["base"] / values["candidate"]))
        mean = statistics.mean(differences)
        # Two-sided Student t critical value for 19 degrees of freedom.
        half = 2.093024054 * statistics.stdev(differences) / math.sqrt(20)
        return {"geometric_speedup_percent": 100 * math.expm1(mean),
                "approximate_95pct_interval_percent": [100 * math.expm1(mean - half),
                                                        100 * math.expm1(mean + half)],
                "paired_log_speed_ratios": differences}

    metadata["summary"] = {field: summarize(field) for field in ("search_ms", "wall_seconds")}
    metadata["limitations"] = (
        "Intervals assume paired log ratios are approximately independent and stationary. "
        "No CPU affinity was applied on macOS. Thermal, OS scheduling and run-order effects may remain. "
        "One build per variant: PGO/layout variation is not isolated. This is local ARM64 timing, not Elo."
    )
    metadata["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save()
    print(json.dumps(metadata["summary"], indent=2), flush=True)


if __name__ == "__main__":
    main()
