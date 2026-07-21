"""Tests for the LEXEME_PATCHES mechanism in export_lexicon() (scripts/export.py).

Uses a tiny hand-built sqlite (no 55 MB data.sql needed). Runs under pytest or
as a plain script: `python3 tests/test_export_lexicon_patches.py` (exit 1 on failure).
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
from export import export_lexicon, LEXEME_PATCHES  # noqa: E402


def _make_db() -> sqlite3.Cursor:
    """Build a minimal katersat-shaped DB with a clean row and a patched row.

    In-memory: the returned cursor keeps its connection (and thus the DB) alive.
    """
    con = sqlite3.connect(':memory:')
    con.executescript(
        """
        CREATE TABLE kat_lexemes (
            lex_id INTEGER PRIMARY KEY, lex_lexeme TEXT, lex_wordclass TEXT,
            lex_semclass TEXT, lex_sem2 TEXT, lex_register TEXT, lex_gender TEXT,
            lex_stem TEXT, lex_definition TEXT, lex_info TEXT, lex_verbframe TEXT,
            lex_oldspelling TEXT, lex_valence INTEGER, lex_language TEXT
        );
        CREATE TABLE kat_lexeme_attrs (
            lex_id INTEGER PRIMARY KEY, let_attrs INTEGER, lex_sandhi INTEGER
        );
        CREATE TABLE kat_valence (val_id INTEGER PRIMARY KEY, val_code TEXT);
        CREATE TABLE kat_domains (
            dom_id INTEGER PRIMARY KEY, dom_code TEXT, dom_eng TEXT, dom_dan TEXT, dom_kal TEXT
        );
        CREATE TABLE glue_lexeme_synonyms (
            lex_id INTEGER, lex_syn INTEGER, syn_order INTEGER
        );
        """
    )
    lexemes = [
        (1, 'illu', 'n', 'UNK', 'UNK', '0', '', '', 'house', '', '', '', None, 'kal'),
        (262026, 'A Der/vv TUR Der/vv', 'v', 'UNK', 'UNK', '0', '', '', '', '', '', '', None, 'kal'),
    ]
    con.executemany(
        'INSERT INTO kat_lexemes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)', lexemes
    )
    con.commit()
    return con.cursor()


def _by_id(doc):
    return {e['id']: e for e in doc['lexemes']}


def test_unpatched_row_passes_through_unchanged():
    doc = export_lexicon(_make_db())
    ids = _by_id(doc)
    assert 'lex_1' in ids
    assert ids['lex_1']['kalaallisut'] == 'illu'
    assert 'data_issue' not in ids['lex_1']


def test_patched_row_is_split_with_distinct_ids():
    doc = export_lexicon(_make_db())
    ids = _by_id(doc)
    # The malformed source row is not exported under its original id...
    assert 'lex_262026' not in ids
    # ...instead it is split into parts with ids that cannot collide with any
    # real katersat lex_<int> id (those are always plain integers).
    assert 'lex_patch_262026_1' in ids
    assert 'lex_patch_262026_2' in ids
    assert ids['lex_patch_262026_1']['kalaallisut'] == 'A Der/vv'
    assert ids['lex_patch_262026_2']['kalaallisut'] == 'TUR Der/vv'


def test_patched_row_carries_data_issue_provenance():
    doc = export_lexicon(_make_db())
    ids = _by_id(doc)
    for split_id in ('lex_patch_262026_1', 'lex_patch_262026_2'):
        issue = ids[split_id]['data_issue']
        assert issue['type'] == 'split'
        assert issue['source_lex_id'] == 'lex_262026'
        assert issue['reason'] == LEXEME_PATCHES[262026]['reason']


def test_split_parts_inherit_shared_fields():
    doc = export_lexicon(_make_db())
    ids = _by_id(doc)
    # Split parts share the source row's non-text fields (word_class etc.),
    # only the lexeme text and id are overridden.
    assert ids['lex_patch_262026_1']['word_class'] == 'v'
    assert ids['lex_patch_262026_2']['word_class'] == 'v'


if __name__ == '__main__':
    import traceback

    failures = 0
    for _name, _fn in sorted(globals().items()):
        if _name.startswith('test_') and callable(_fn):
            try:
                _fn()
                print(f'ok - {_name}')
            except Exception:
                failures += 1
                traceback.print_exc()
                print(f'FAIL - {_name}')
    print('SUCCESS' if not failures else f'FAILURE ({failures})')
    sys.exit(1 if failures else 0)
