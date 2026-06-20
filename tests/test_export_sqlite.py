"""Tests for export_sqlite() in scripts/export.py and check_sqlite()/check_sqlite_gz() in scripts/validators.py"""
import gzip
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
from export import export_sqlite
from validators import check_sqlite, check_sqlite_gz


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
    _SQLITE_MAGIC = b'SQLite format 3\x00'
    with gzip.open(out / 'katersat.sqlite.gz', 'rb') as f:
        header = f.read(16)
    assert header.startswith(_SQLITE_MAGIC)


def test_export_sqlite_creates_output_dir(tmp_path):
    db = _make_sqlite(tmp_path)
    out = tmp_path / 'deep' / 'nested' / 'exports'
    export_sqlite(db, out, compress=True)
    assert (out / 'katersat.sqlite').exists()
    assert (out / 'katersat.sqlite.gz').exists()


# ---------------------------------------------------------------------------
# check_sqlite / check_sqlite_gz validator
# ---------------------------------------------------------------------------

def test_check_sqlite_valid_uncompressed(tmp_path):
    db = _make_sqlite(tmp_path)
    assert check_sqlite(db, compressed=False) == []


def test_check_sqlite_valid_compressed(tmp_path):
    db = _make_sqlite(tmp_path)
    gz = tmp_path / 'katersat.sqlite.gz'
    with open(db, 'rb') as src, gzip.open(gz, 'wb', compresslevel=9) as dst:
        shutil.copyfileobj(src, dst)
    assert check_sqlite(gz, compressed=True) == []


def test_check_sqlite_gz_delegates_to_check_sqlite(tmp_path):
    db = _make_sqlite(tmp_path)
    gz = tmp_path / 'katersat.sqlite.gz'
    with open(db, 'rb') as src, gzip.open(gz, 'wb', compresslevel=9) as dst:
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


def test_check_sqlite_uncompressed_bad_magic(tmp_path):
    bad = tmp_path / 'bad.sqlite'
    bad.write_bytes(b'NOT_SQLITE_DATA_AT_ALL')
    errs = check_sqlite(bad, compressed=False)
    assert errs
    assert 'magic' in errs[0]


def test_check_sqlite_uncompressed_empty(tmp_path):
    empty = tmp_path / 'empty.sqlite'
    empty.write_bytes(b'')
    errs = check_sqlite(empty, compressed=False)
    assert errs
    assert 'empty' in errs[0]
