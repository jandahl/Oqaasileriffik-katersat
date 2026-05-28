"""Tests for scripts/archive_data.py"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
from archive_data import run, latest_archive_sha, _sort_key, _ARCHIVE_PAT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_source(tmp_path: Path, content: bytes = b'SELECT 1;') -> Path:
    src = tmp_path / 'data.sql'
    src.write_bytes(content)
    return src


def _archive_files(data_dir: Path) -> list[Path]:
    return sorted(
        [p for p in data_dir.glob('*.sql') if _ARCHIVE_PAT.match(p.stem)],
        key=_sort_key,
    )


# ---------------------------------------------------------------------------
# sha / sort helpers
# ---------------------------------------------------------------------------

def test_sort_key_basic():
    assert _sort_key(Path('2024-05-01.sql')) == (2024, 5, 1, 0)


def test_sort_key_with_suffix():
    assert _sort_key(Path('2024-05-01-3.sql')) == (2024, 5, 1, 3)
    assert _sort_key(Path('2024-05-01-10.sql')) == (2024, 5, 1, 10)
    assert _sort_key(Path('2024-05-01-3.sql')) < _sort_key(Path('2024-05-01-10.sql'))


def test_sort_key_non_conforming():
    assert _sort_key(Path('schema.sql')) == (0, 0, 0, 0)


# ---------------------------------------------------------------------------
# run() — first run creates archive + changelog with header
# ---------------------------------------------------------------------------

def test_first_run_creates_archive_and_changelog(tmp_path):
    src = _make_source(tmp_path)
    data_dir = tmp_path / 'data'
    changelog = data_dir / 'CHANGELOG.md'

    run(src, data_dir, changelog)

    files = _archive_files(data_dir)
    assert len(files) == 1

    text = changelog.read_text(encoding='utf-8')
    assert '# Katersat data changelog' in text
    assert files[0].name in text


# ---------------------------------------------------------------------------
# run() — no change → no new archive
# ---------------------------------------------------------------------------

def test_no_change_skips_archive(tmp_path):
    src = _make_source(tmp_path, b'unchanged content')
    data_dir = tmp_path / 'data'
    changelog = data_dir / 'CHANGELOG.md'

    run(src, data_dir, changelog)
    run(src, data_dir, changelog)  # same content

    assert len(_archive_files(data_dir)) == 1


# ---------------------------------------------------------------------------
# run() — changed content → new archive appended to existing changelog
# ---------------------------------------------------------------------------

def test_changed_content_creates_new_archive(tmp_path):
    src = _make_source(tmp_path, b'version 1')
    data_dir = tmp_path / 'data'
    changelog = data_dir / 'CHANGELOG.md'

    run(src, data_dir, changelog)
    src.write_bytes(b'version 2')
    run(src, data_dir, changelog)

    files = _archive_files(data_dir)
    assert len(files) == 2

    text = changelog.read_text(encoding='utf-8')
    assert text.count('# Katersat data changelog') == 1  # header written once
    assert len([l for l in text.splitlines() if l.startswith('|') and 'UTC' not in l and '---' not in l]) == 2


# ---------------------------------------------------------------------------
# run() — same-day duplicate gets numeric suffix
# ---------------------------------------------------------------------------

def test_same_day_duplicate_gets_suffix(tmp_path):
    today = __import__('datetime').datetime.now(__import__('datetime').timezone.utc).date().isoformat()
    src = _make_source(tmp_path, b'v1')
    data_dir = tmp_path / 'data'
    data_dir.mkdir()

    # Pre-seed an archive for today so the first filename is already taken
    (data_dir / f'{today}.sql').write_bytes(b'different content so SHA differs')

    changelog = data_dir / 'CHANGELOG.md'
    run(src, data_dir, changelog)

    files = _archive_files(data_dir)
    suffixed = [f for f in files if f.stem.startswith(f'{today}-')]
    assert len(suffixed) == 1
    assert suffixed[0].stem == f'{today}-1'


# ---------------------------------------------------------------------------
# run() — missing source exits gracefully
# ---------------------------------------------------------------------------

def test_missing_source_does_not_raise(tmp_path):
    data_dir = tmp_path / 'data'
    changelog = data_dir / 'CHANGELOG.md'
    run(tmp_path / 'nonexistent.sql', data_dir, changelog)
    assert not data_dir.exists()


# ---------------------------------------------------------------------------
# latest_archive_sha ignores non-conforming files
# ---------------------------------------------------------------------------

def test_latest_archive_sha_ignores_schema_sql(tmp_path):
    data_dir = tmp_path / 'data'
    data_dir.mkdir()
    (data_dir / 'schema.sql').write_bytes(b'schema')
    assert latest_archive_sha(data_dir) is None
