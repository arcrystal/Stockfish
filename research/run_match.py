#!/usr/bin/env python3
"""Run a reproducible, paired local screening match and preserve its inputs."""

import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shlex
import subprocess


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--book", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--games", type=int, default=1000)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--tc", default="1+0.01")
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--hash", type=int, default=16)
    args = parser.parse_args()
    if args.games <= 0 or args.games % 2:
        parser.error("--games must be a positive even number")
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    inputs = {name: getattr(args, name).resolve() for name in ("candidate", "base", "runner", "book")}
    command = [
        str(inputs["runner"]),
        "-engine", "name=candidate", f"cmd={inputs['candidate']}",
        "-engine", "name=baseline", f"cmd={inputs['base']}",
        "-each", "proto=uci", f"tc={args.tc}", f"option.Hash={args.hash}",
        f"option.Threads={args.threads}",
        "-openings", f"file={inputs['book']}", "format=epd", "order=random",
        "-srand", str(args.seed), "-rounds", str(args.games // 2), "-games", "2", "-repeat",
        "-concurrency", str(args.concurrency),
        "-resign", "movecount=3", "score=600",
        "-draw", "movenumber=34", "movecount=8", "score=20",
        "-report", "penta=true", "-ratinginterval", "100", "-scoreinterval", "100",
        "-config", f"outname={output}.fastchess.json",
        "-autosaveinterval", "0", "-pgnout", f"file={output}.pgn", "nodes=true",
    ]
    metadata_path = Path(f"{output}.json")
    metadata = {
        "purpose": "Fixed-sample local screening; not a Fishtest run or proof of an Elo gain.",
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "inputs": {name: {"path": str(path), "sha256": sha256(path)} for name, path in inputs.items()},
        "command": command,
        "shell_command": shlex.join(command),
        "planned_games": args.games,
    }
    # Exclusive creation protects previous evidence from accidental reruns.
    with metadata_path.open("x") as stream:
        json.dump(metadata, stream, indent=2)
        stream.write("\n")
    print(shlex.join(command), flush=True)
    with Path(f"{output}.log").open("x") as stream:
        result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT)
    metadata["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    metadata["exit_code"] = result.returncode
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"Match finished with exit code {result.returncode}; evidence: {output}.*", flush=True)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
