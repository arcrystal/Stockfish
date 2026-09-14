from pathlib import Path
import queue
import subprocess
import threading
import time

ROOT = Path('/Users/acrystal/Desktop/Coding/Games/Stockfish')
SRC = ROOT / '.research-tools/repetition-diagnostic/src'
OUT = ROOT / 'research/results'
ENGINE = str(SRC / 'stockfish')

with (OUT / 'repetition-diagnostic-bench.log').open('w') as log:
    result = subprocess.run([ENGINE, 'bench'], cwd=SRC, stdout=log, stderr=log, timeout=60)
    if result.returncode:
        raise SystemExit(f'bench failed: {result.returncode}')
bench = (OUT / 'repetition-diagnostic-bench.log').read_text()
if 'Nodes searched  : 1648567' not in bench:
    raise SystemExit('Baseline bench signature mismatch; stopping before seed')
print('Bench signature: 1648567', flush=True)

commands = [
    'uci',
    'setoption name Threads value 1',
    'setoption name Hash value 16',
    'setoption name SyzygyProbeLimit value 0',
    'isready',
    'ucinewgame',
    'position fen 4k2q/8/8/8/8/8/8/R3K3 b - - 0 1 moves e8f8 e1f1 f8e8 f1e1 e8f8 e1f1',
    'd',
    'go depth 1 searchmoves f8e8',
    'quit',
]
(OUT / 'repetition-diagnostic-seed.commands').write_text('\n'.join(commands) + '\n')
with (OUT / 'repetition-diagnostic-seed.stdout.log').open('w') as out, \
     (OUT / 'repetition-diagnostic-seed.stderr.log').open('w') as err:
    process = subprocess.Popen([ENGINE], cwd=SRC, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=err, text=True, bufsize=1)
    lines = queue.Queue()
    def read_output():
        for line in process.stdout:
            out.write(line)
            out.flush()
            lines.put(line)
        lines.put(None)
    thread = threading.Thread(target=read_output, daemon=True)
    thread.start()
    def send(command):
        process.stdin.write(command + '\n')
        process.stdin.flush()
    def until(prefix):
        deadline = time.monotonic() + 15
        while True:
            line = lines.get(timeout=max(0.01, deadline-time.monotonic()))
            if line is None:
                raise RuntimeError('engine ended early')
            if line.startswith(prefix):
                return line.strip()
    try:
        send(commands[0]); until('uciok')
        for command in commands[1:5]:
            send(command)
        until('readyok')
        for command in commands[5:9]:
            send(command)
        print(until('bestmove'), flush=True)
        send(commands[9])
        if process.wait(timeout=5):
            raise RuntimeError('seed process failed')
        thread.join(timeout=1)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
print('CPU WORK COMPLETE', flush=True)
