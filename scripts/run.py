#!/usr/bin/env python3
"""One-command autonomous run: ingest -> deterministic intelligence -> static build."""
import subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
for name in ('ingest.py', 'pipeline.py', 'build.py'):
    print('\n===', name, '===')
    p = subprocess.run([sys.executable, str(ROOT / name)], cwd=ROOT.parent)
    if p.returncode:
        raise SystemExit(p.returncode)
