#!/usr/bin/env python3
"""Replay a history-sensitive qsearch example through ordinary UCI commands."""
import argparse
import json
from pathlib import Path
import queue
import re
import subprocess
import threading
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    positions = {
        "history": "fen 4k2q/8/8/8/8/8/8/R3K3 b - - 0 1 moves e8f8 e1f1 f8e8 f1e1 e8f8 e1f1",
        "no-history": "fen 5k1q/8/8/8/8/8/8/R4K2 b - - 6 4",
    }
    summary = {}
    for label, position in positions.items():
        commands = ["uci", "setoption name Threads value 1", "setoption name Hash value 16",
                    "setoption name SyzygyProbeLimit value 0", "isready", "ucinewgame",
                    f"position {position}", "d", "go depth 1 searchmoves f8e8", "quit"]
        prefix = Path(f"{args.output}-{label}")
        with Path(f"{prefix}.commands").open("x") as stream:
            stream.write("\n".join(commands) + "\n")
        with Path(f"{prefix}.stdout").open("x") as stdout, Path(f"{prefix}.stderr").open("x") as stderr:
            process = subprocess.Popen([str(args.engine.resolve())], stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=stderr, text=True, bufsize=1)
            lines = queue.Queue()
            captured = []

            def read():
                for line in process.stdout:
                    stdout.write(line)
                    stdout.flush()
                    lines.put(line)
                lines.put(None)

            reader = threading.Thread(target=read, daemon=True)
            reader.start()

            def send(command):
                process.stdin.write(command + "\n")
                process.stdin.flush()

            def until(prefix):
                deadline = time.monotonic() + 20
                while True:
                    line = lines.get(timeout=max(0.01, deadline - time.monotonic()))
                    if line is None:
                        raise RuntimeError("Engine ended before UCI response")
                    captured.append(line)
                    if line.startswith(prefix):
                        return line.strip()

            try:
                send(commands[0])
                until("uciok")
                for command in commands[1:5]:
                    send(command)
                until("readyok")
                for command in commands[5:9]:
                    send(command)
                bestmove = until("bestmove")
                send("quit")
                if process.wait(timeout=5):
                    raise RuntimeError("Engine returned nonzero exit status")
                reader.join(timeout=1)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
        scores = re.findall(r"score cp (-?\d+)", "".join(captured))
        if not scores or not bestmove.startswith("bestmove f8e8"):
            raise RuntimeError(f"Unexpected result: {bestmove}")
        summary[label] = {"score_cp": int(scores[-1]), "bestmove": bestmove}
    with Path(f"{args.output}.json").open("x") as stream:
        json.dump(summary, stream, indent=2)
        stream.write("\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
