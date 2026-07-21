"""Tests for export_lexicon() (scripts/export.py): the dermorph-chain filter
and the LEXEME_PATCHES known-issue registry.

Uses a tiny hand-built sqlite (no 55 MB data.sql needed). Runs under pytest or
as a plain script: `python3 tests/test_export_lexicon_patches.py` (exit 1 on failure).
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
import export  # noqa: E402
from export import export_lexicon  # noqa: E402


def _make_db(lexemes):
    """Build a minimal katersat-shaped DB from (lex_id, lex_lexeme, lex_wordclass) tuples.

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
    rows = [
        (lex_id, lexeme, wc, 'UNK', 'UNK', '0', '', '', '', '', '', '', None, 'kal')
        for lex_id, lexeme, wc in lexemes
    ]
    con.executemany('INSERT INTO kat_lexemes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)', rows)
    con.commit()
    return con.cursor()


def _by_id(entries):
    return {e['id']: e for e in entries}


class _patched_registry:
    """Context manager: temporarily replace export.LEXEME_PATCHES for one test."""

    def __init__(self, patches):
        self.patches = patches

    def __enter__(self):
        self._orig = export.LEXEME_PATCHES
        export.LEXEME_PATCHES = self.patches

    def __exit__(self, *exc):
        export.LEXEME_PATCHES = self._orig


# --- dermorph chain routing --------------------------------------------------

def test_ordinary_lexeme_passes_through_unchanged():
    lexicon, chains = export_lexicon(_make_db([(1, 'illu', 'n')]))
    ids = _by_id(lexicon['lexemes'])
    assert ids['lex_1']['kalaallisut'] == 'illu'
    assert 'data_issue' not in ids['lex_1']
    assert chains['dermorph_chains'] == []


def test_multi_der_chain_is_routed_to_dermorph_chains_not_lexicon():
    lexicon, chains = export_lexicon(_make_db([(262026, 'A Der/vv TUR Der/vv', 'v')]))
    lex_ids = _by_id(lexicon['lexemes'])
    chain_ids = _by_id(chains['dermorph_chains'])
    # No longer split, no longer flagged as an error: exported whole, but kept
    # out of the general dictionary lexicon since it's not a real headword.
    assert 'lex_262026' not in lex_ids
    assert 'lex_262026' in chain_ids
    entry = chain_ids['lex_262026']
    assert entry['kalaallisut'] == 'A Der/vv TUR Der/vv'
    assert entry['data_issue']['type'] == 'dermorph_chain'


def test_single_der_entry_stays_in_lexicon():
    # A single "STEM Der/xy" form is a legitimate single-affix entry, not a
    # chain -- only 2+ Der markers trigger routing to dermorph_chains.json.
    lexicon, chains = export_lexicon(_make_db([(5, 'SSAQ Der/nn', 'n')]))
    assert 'lex_5' in _by_id(lexicon['lexemes'])
    assert chains['dermorph_chains'] == []


def test_longer_chain_is_also_routed():
    lexicon, chains = export_lexicon(_make_db([
        (9, 'IR Der/nv NIAQ Der/nn TUQ Der/vn', 'n'),
    ]))
    assert 'lex_9' not in _by_id(lexicon['lexemes'])
    assert 'lex_9' in _by_id(chains['dermorph_chains'])


# --- LEXEME_PATCHES registry (for confirmed one-off corruption only) --------

def test_patch_split_creates_distinct_ids_and_leaves_lexicon():
    patches = {
        999: {
            'type': 'split',
            'expected': 'FOO BAR',
            'reason': 'test: two entries concatenated',
            'parts': ['FOO', 'BAR'],
        },
    }
    with _patched_registry(patches):
        lexicon, _chains = export_lexicon(_make_db([(999, 'FOO BAR', 'v')]))
    ids = _by_id(lexicon['lexemes'])
    assert 'lex_999' not in ids
    assert ids['lex_patch_999_1']['kalaallisut'] == 'FOO'
    assert ids['lex_patch_999_2']['kalaallisut'] == 'BAR'
    for split_id in ('lex_patch_999_1', 'lex_patch_999_2'):
        issue = ids[split_id]['data_issue']
        assert issue['type'] == 'split'
        assert issue['source_lex_id'] == 'lex_999'


def test_patch_flag_keeps_text_in_lexicon_with_data_issue():
    patches = {
        998: {'type': 'flag', 'expected': 'weird text', 'reason': 'test: unclear correction'},
    }
    with _patched_registry(patches):
        lexicon, _chains = export_lexicon(_make_db([(998, 'weird text', 'v')]))
    ids = _by_id(lexicon['lexemes'])
    assert ids['lex_998']['kalaallisut'] == 'weird text'
    assert ids['lex_998']['data_issue'] == {'type': 'flag', 'reason': 'test: unclear correction'}


def test_patch_skipped_when_upstream_text_no_longer_matches():
    patches = {
        999: {
            'type': 'split',
            'expected': 'FOO BAR',
            'reason': 'test: two entries concatenated',
            'parts': ['FOO', 'BAR'],
        },
    }
    with _patched_registry(patches):
        # Simulate upstream having fixed the row to something new.
        lexicon, chains = export_lexicon(_make_db([(999, 'illuttoq', 'v')]))
    ids = _by_id(lexicon['lexemes'])
    assert 'lex_patch_999_1' not in ids and 'lex_patch_999_2' not in ids
    assert ids['lex_999']['kalaallisut'] == 'illuttoq'
    assert 'data_issue' not in ids['lex_999']
    assert chains['dermorph_chains'] == []


def test_default_registry_is_empty():
    # lex_262026 is no longer a special case in LEXEME_PATCHES -- it's just
    # one of many dermorph chains, handled generically (see tests above).
    assert export.LEXEME_PATCHES == {}


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
