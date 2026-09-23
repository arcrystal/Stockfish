#!/usr/bin/env python3
"""Losslessly replace large completed audit artifacts with deterministic gzip files.

Run only after discovery, replay, and independent analysis have completed.
The manifest retains both hashes. Restore with gzip before using frozen runners.
"""
import gzip
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent / 'results/pawn-lmr-audit'


def digest(path, compressed=False):
    h = hashlib.sha256()
    opener = gzip.open if compressed else open
    with opener(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


if __name__ == '__main__':
    assert (ROOT / 'replay-complete.json').exists(), 'Audit must finish first'
    manifest = ROOT / 'compression-manifest.json'
    assert not manifest.exists(), 'Do not overwrite an existing archive manifest'
    records = []
    for source in sorted(ROOT.iterdir()):
        if source.suffix not in {'.log', '.json'} or source.stat().st_size <= 1024 * 1024:
            continue
        if source.name in {'corpus.json', 'selection.json', 'summary.json'}:
            continue
        target = source.with_name(source.name + '.gz')
        record = {'original_path': source.name, 'original_bytes': source.stat().st_size,
                  'original_sha256': digest(source), 'compressed_path': target.name}
        with source.open('rb') as src, target.open('xb') as dst:
            with gzip.GzipFile(filename='', mode='wb', fileobj=dst, mtime=0) as gz:
                shutil.copyfileobj(src, gz)
        assert digest(target, compressed=True) == record['original_sha256']
        record.update(compressed_bytes=target.stat().st_size,
                      compressed_sha256=digest(target))
        records.append(record)
    with manifest.open('x') as out:
        json.dump({'method': 'gzip mtime=0; decompressed SHA256 verified before replacement',
                   'files': records}, out, indent=2)
        out.write('\n')
    for record in records:
        (ROOT / record['original_path']).unlink()
    print(f'Archived {len(records)} files; all decompressed hashes verified.')
