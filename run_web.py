"""Local browser launcher: py -3.12 run_web.py (Windows), python3 run_web.py elsewhere."""
from __future__ import annotations

import hashlib
from pathlib import Path
import os
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent


def main() -> int:
    if sys.version_info < (3, 11):
        print('ViralCut requires Python 3.11 or newer; Python 3.12 x64 is recommended.')
        return 1
    env = ROOT / '.venv-web'
    python = env / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    requirements = ROOT / 'requirements.txt'
    stamp = env / '.requirements-sha256'
    fingerprint = hashlib.sha256(requirements.read_bytes()).hexdigest()
    if not python.is_file():
        print('[ViralCut] Creating local Python environment...', flush=True)
        venv.EnvBuilder(with_pip=True).create(env)
    if not stamp.is_file() or stamp.read_text().strip() != fingerprint:
        print('[ViralCut] Installing browser-mode dependencies. First launch may take several minutes.', flush=True)
        subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(requirements)], cwd=ROOT, check=True)
        stamp.write_text(fingerprint)
    print('[ViralCut] Starting local website. Keep this terminal open; Ctrl+C stops the server.', flush=True)
    return subprocess.call([str(python), '-m', 'viralcut', '--open-browser', *sys.argv[1:]], cwd=ROOT)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(0)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f'[ViralCut] Could not start: {exc}', file=sys.stderr)
        raise SystemExit(1)
