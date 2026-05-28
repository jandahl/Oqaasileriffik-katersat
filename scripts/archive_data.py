#!/usr/bin/env python3
# Copyright 2024 Oqaasileriffik <oqaasileriffik@oqaasileriffik.gl>
# Licensed under the GNU GPL v3 or later - https://www.gnu.org/licenses/gpl-3.0.en.html

"""Archive data.sql to data/YYYY-MM-DD.sql when upstream content has changed."""

import hashlib
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / 'data'
SOURCE = ROOT / 'data.sql'
CHANGELOG = DATA_DIR / 'CHANGELOG.md'


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def latest_archive_sha() -> str | None:
    def sort_key(path: Path):
        parts = path.stem.split('-')
        suffix = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
        return (parts[:3], suffix)

    sql_files = sorted(DATA_DIR.glob('*.sql'), key=sort_key)
    return sha256(sql_files[-1]) if sql_files else None


def main() -> None:
    if not SOURCE.exists():
        print('data.sql not found, skipping archive', file=sys.stderr)
        sys.exit(0)

    DATA_DIR.mkdir(exist_ok=True)

    current_sha = sha256(SOURCE)
    previous_sha = latest_archive_sha()
    now = datetime.now(timezone.utc).isoformat(timespec='seconds')

    if current_sha == previous_sha:
        print(f'  data.sql unchanged ({current_sha[:12]}), skipping archive', file=sys.stderr)
        return

    # Content changed — find an unused filename for today
    today = datetime.now(timezone.utc).date().isoformat()
    dest = DATA_DIR / f'{today}.sql'
    suffix = 1
    while dest.exists():
        dest = DATA_DIR / f'{today}-{suffix}.sql'
        suffix += 1

    shutil.copy2(SOURCE, dest)
    print(f'  archived → data/{dest.name}  ({dest.stat().st_size:,} bytes)', file=sys.stderr)

    # Append to changelog (create with header if new)
    existed = CHANGELOG.exists()
    with CHANGELOG.open('a', encoding='utf-8') as f:
        if not existed:
            f.write('# Katersat data changelog\n\n')
            f.write('Entries appear only when upstream data actually changed.\n\n')
            f.write('| UTC timestamp | SHA-256 (12) | Archived file |\n')
            f.write('|---|---|---|\n')
        f.write(f'| {now} | {current_sha[:12]} | `{dest.name}` |\n')


if __name__ == '__main__':
    main()
