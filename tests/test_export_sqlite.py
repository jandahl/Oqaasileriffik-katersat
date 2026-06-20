"""Tests for export_sqlite() in scripts/export.py and check_sqlite_gz() in scripts/validators.py"""
import gzip
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
from export import export_sqlite
from validators import check_sqlite_gz


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sqlite(tmp_path: Path, name: str = 'test.sqlite') -> Path:
    p = tmp_path / name
    con = sqlite3.connect(p)
    con.execute('CREATE TABLE _dummy (id INTEGER PRIMARY KEY)')
    con.commit()
    con.close()
    return p


# ---------------------------------------------------------------------------
# export_sqlite — basic copy (no compress)
# ---------------------------------------------------------------------------

def test_export_sqlite_copies_file(tmp_path):
    db = _make_sqlite(tmp_path)
    out = tmp_path / 'exports'
    export_sqlite(db, out, compress=False)
    dest = out / 'katersat.sqlite'
    assert dest.exists()
    assert dest.stat().st_size > 0


def test_export_sqlite_no_gz_when_compress_false(tmp_path):
    db = _make_sqlite(tmp_path)
    out = tmp_path / 'exports'
    export_sqlite(db, out, compress=False)
    assert not (out / 'katersat.sqlite.gz').exists()


# ---------------------------------------------------------------------------
# export_sqlite — with compress
# ---------------------------------------------------------------------------

def test_export_sqlite_creates_gz(tmp_path):
    db = _make_sqlite(tmp_path)
    out = tmp_path / 'exports'
    export_sqlite(db, out, compress=True)
    gz = out / 'katersat.sqlite.gz'
    assert gz.exists()
    assert gz.stat().st_size > 0


def test_export_sqlite_gz_has_sqlite_magic(tmp_path):
    db = _make_sqlite(tmp_path)
    out = tmp_path / 'exports'
    export_sqlite(db, out, compress=True)
    with gzip.open(out / 'katersat.sqlite.gz', 'rb') as f:
        header = f.read(16)
    assert header[:4] == b'SQLi'


def test_export_sqlite_creates_output_dir(tmp_path):
    db = _make_sqlite(tmp_path)
    out = tmp_path / 'deep' / 'nested' / 'exports'
    export_sqlite(db, out, compress=True)
    assert (out / 'katersat.sqlite').exists()
    assert (out / 'katersat.sqlite.gz').exists()


# ---------------------------------------------------------------------------
# check_sqlite_gz validator
# ---------------------------------------------------------------------------

def test_check_sqlite_gz_valid(tmp_path):
    db = _make_sqlite(tmp_path)
    gz = tmp_path / 'katersat.sqlite.gz'
    with open(db, 'rb') as src, gzip.open(gz, 'wb', compresslevel=9) as dst:
        import shutil
        shutil.copyfileobj(src, dst)
    assert check_sqlite_gz(gz) == []


def test_check_sqlite_gz_empty(tmp_path):
    gz = tmp_path / 'katersat.sqlite.gz'
    with gzip.open(gz, 'wb') as f:
        pass
    errs = check_sqlite_gz(gz)
    assert errs
    assert 'empty' in errs[0]


def test_check_sqlite_gz_bad_magic(tmp_path):
    gz = tmp_path / 'katersat.sqlite.gz'
    with gzip.open(gz, 'wb') as f:
        f.write(b'NOT_SQLITE_DATA_HERE')
    errs = check_sqlite_gz(gz)
    assert errs
    assert 'magic' in errs[0]


def test_check_sqlite_gz_not_a_gzip(tmp_path):
    gz = tmp_path / 'katersat.sqlite.gz'
    gz.write_bytes(b'this is not a gzip file')
    errs = check_sqlite_gz(gz)
    assert errs
