"""Tests for export_lexicon() (scripts/export.py): the LEXEME_CLASSES
classifier (one output file per lexeme class) and the LEXEME_PATCHES
known-issue registry (for confirmed one-off corruption within the default
'lexicon' class).

Uses a tiny hand-built sqlite (no 55 MB data.sql needed). Runs under pytest or
as a plain script: `python3 tests/test_export_lexicon_patches.py` (exit 1 on failure).
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
import export  # noqa: E402
from export import export_lexicon, LEXEME_CLASSES  # noqa: E402


def _make_db(lexemes):
    """Build a minimal katersat-shaped DB from (lex_id, lex_lexeme, lex_wordclass,
    attrs_bits) tuples. attrs_bits may be None to omit the attrs row entirely.

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
        for lex_id, lexeme, wc, _attrs in lexemes
    ]
    con.executemany('INSERT INTO kat_lexemes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)', rows)
    attrs_rows = [
        (lex_id, attrs, 0) for lex_id, _lexeme, _wc, attrs in lexemes if attrs is not None
    ]
    con.executemany('INSERT INTO kat_lexeme_attrs VALUES (?,?,?)', attrs_rows)
    con.commit()
    return con.cursor()


DERMORPH = 512
HIDDEN = 1
ENCLITIC = 1024


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


# --- class registry shape ----------------------------------------------------

def test_lexicon_always_present_even_if_empty():
    docs = export_lexicon(_make_db([]))
    assert docs['lexicon'] == {'meta': docs['lexicon']['meta'], 'lexemes': []}


def test_every_registered_class_present_even_if_empty():
    docs = export_lexicon(_make_db([(1, 'illu', 'n', None)]))
    names = {c[0] for c in LEXEME_CLASSES}
    assert names == {'dermorph', 'enclitic'}
    for name in names:
        assert name in docs
        key = list(docs[name].keys())
        assert 'meta' in key


def test_all_docs_share_one_generated_at_timestamp():
    docs = export_lexicon(_make_db([(1, 'illu', 'n', None)]))
    stamps = {doc['meta']['generated_at'] for doc in docs.values()}
    assert len(stamps) == 1


# --- default 'lexicon' class -------------------------------------------------

def test_ordinary_lexeme_goes_to_lexicon():
    docs = export_lexicon(_make_db([(1, 'illu', 'n', None)]))
    ids = _by_id(docs['lexicon']['lexemes'])
    assert ids['lex_1']['kalaallisut'] == 'illu'
    assert 'class_subtype' not in ids['lex_1']
    assert docs['dermorph']['dermorph'] == []
    assert docs['enclitic']['enclitics'] == []


def test_ordinary_uppercase_word_without_special_attrs_stays_in_lexicon():
    # Real acronyms/initialisms (EU, DNA, USB, ...) are uppercase but carry no
    # dermorph/enclitic bit in the live data -- must not be misclassified by
    # any shape-based heuristic.
    docs = export_lexicon(_make_db([(2, 'DNA', 't', None)]))
    assert 'lex_2' in _by_id(docs['lexicon']['lexemes'])


# --- 'dermorph' class ---------------------------------------------------------

def test_dermorph_single_affix_routed_with_subtype():
    docs = export_lexicon(_make_db([(5, 'SSAQ Der/nn', 'n', DERMORPH)]))
    assert 'lex_5' not in _by_id(docs['lexicon']['lexemes'])
    entry = _by_id(docs['dermorph']['dermorph'])['lex_5']
    assert entry['kalaallisut'] == 'SSAQ Der/nn'
    assert entry['class_subtype'] == 'single_affix'


def test_dermorph_chain_routed_with_subtype():
    docs = export_lexicon(_make_db([(262026, 'A Der/vv TUR Der/vv', 'v', DERMORPH)]))
    assert 'lex_262026' not in _by_id(docs['lexicon']['lexemes'])
    entry = _by_id(docs['dermorph']['dermorph'])['lex_262026']
    assert entry['kalaallisut'] == 'A Der/vv TUR Der/vv'
    assert entry['class_subtype'] == 'chain'


def test_dermorph_bare_stub_routed_with_subtype():
    # Flagged dermorph but no "Der/xy" marker at all -- an internal
    # morphophonemic stub (e.g. "IP", "NIARIUTAA" in the real data).
    docs = export_lexicon(_make_db([(163321, 'IP', 'v', DERMORPH)]))
    assert 'lex_163321' not in _by_id(docs['lexicon']['lexemes'])
    entry = _by_id(docs['dermorph']['dermorph'])['lex_163321']
    assert entry['kalaallisut'] == 'IP'
    assert entry['class_subtype'] == 'bare'


def test_dermorph_shape_catches_rows_katersat_forgot_to_flag():
    # katersat's own dermorph flagging is inconsistent: the same postbase text
    # often exists as several rows, only some carrying the dermorph bit, and
    # some chain rows (e.g. real "SINNAA Der/vv RUJUP Der/vv SUAR Der/vv") have
    # exactly one row and it's unflagged. Bit-only classification let these
    # leak into lexicon.json; the text shape must be checked too.
    docs = export_lexicon(_make_db([
        (165580, 'SINNAA Der/vv RUJUP Der/vv SUAR Der/vv', 'v', 0),  # bits=0, real data shape
        (165649, 'GUMA Der/vv', 'v', 0),  # bits=0, real data shape
    ]))
    lex_ids = _by_id(docs['lexicon']['lexemes'])
    assert 'lex_165580' not in lex_ids
    assert 'lex_165649' not in lex_ids
    chain = _by_id(docs['dermorph']['dermorph'])['lex_165580']
    assert chain['class_subtype'] == 'chain'
    single = _by_id(docs['dermorph']['dermorph'])['lex_165649']
    assert single['class_subtype'] == 'single_affix'


def test_dermorph_shape_check_ignores_unrelated_bits():
    # A row with some other attrs bit set (e.g. plural) but Der/xy-shaped text
    # is still routed by shape, regardless of which unrelated bit is set.
    PLURAL = 32
    docs = export_lexicon(_make_db([(165738, 'A Der/vv', 'v', PLURAL)]))
    assert 'lex_165738' not in _by_id(docs['lexicon']['lexemes'])
    assert 'lex_165738' in _by_id(docs['dermorph']['dermorph'])


def test_dermorph_class_ignores_hidden_filter_scope():
    # Sanity: hidden entries never reach export_lexicon's row set at all
    # (filtered in SQL), independent of classification.
    docs = export_lexicon(_make_db([(9, 'SSAQ Der/nn', 'n', DERMORPH | HIDDEN)]))
    assert docs['lexicon']['lexemes'] == []
    assert docs['dermorph']['dermorph'] == []
    assert docs['enclitic']['enclitics'] == []


# --- 'enclitic' class ---------------------------------------------------------

def test_enclitic_routed_out_of_lexicon():
    docs = export_lexicon(_make_db([(163838, 'AASIIT', 'encl', ENCLITIC)]))
    assert 'lex_163838' not in _by_id(docs['lexicon']['lexemes'])
    entry = _by_id(docs['enclitic']['enclitics'])['lex_163838']
    assert entry['kalaallisut'] == 'AASIIT'
    assert 'class_subtype' not in entry  # enclitic has no subtype_fn


def test_dermorph_takes_priority_over_enclitic_when_both_set():
    docs = export_lexicon(_make_db([(1, 'SSAQ Der/nn', 'n', DERMORPH | ENCLITIC)]))
    assert 'lex_1' in _by_id(docs['dermorph']['dermorph'])
    assert 'lex_1' not in _by_id(docs['enclitic']['enclitics'])


# --- LEXEME_PATCHES registry (for confirmed one-off corruption only) --------

def test_patch_split_creates_distinct_ids_within_lexicon():
    patches = {
        999: {
            'type': 'split',
            'expected': 'FOO BAR',
            'reason': 'test: two entries concatenated',
            'parts': ['FOO', 'BAR'],
        },
    }
    with _patched_registry(patches):
        docs = export_lexicon(_make_db([(999, 'FOO BAR', 'v', None)]))
    ids = _by_id(docs['lexicon']['lexemes'])
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
        docs = export_lexicon(_make_db([(998, 'weird text', 'v', None)]))
    ids = _by_id(docs['lexicon']['lexemes'])
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
        docs = export_lexicon(_make_db([(999, 'illuttoq', 'v', None)]))
    ids = _by_id(docs['lexicon']['lexemes'])
    assert 'lex_patch_999_1' not in ids and 'lex_patch_999_2' not in ids
    assert ids['lex_999']['kalaallisut'] == 'illuttoq'
    assert 'data_issue' not in ids['lex_999']


def test_patch_never_applies_to_a_classified_row():
    # A dermorph-classified row is routed before LEXEME_PATCHES is even
    # consulted -- patches only apply within the default 'lexicon' class.
    patches = {
        5: {
            'type': 'flag',
            'expected': 'SSAQ Der/nn',
            'reason': 'should never fire: row is dermorph-classified first',
        },
    }
    with _patched_registry(patches):
        docs = export_lexicon(_make_db([(5, 'SSAQ Der/nn', 'n', DERMORPH)]))
    entry = _by_id(docs['dermorph']['dermorph'])['lex_5']
    assert 'data_issue' not in entry
    assert entry['class_subtype'] == 'single_affix'


def test_default_registry_is_empty():
    # lex_262026 is no longer a special case in LEXEME_PATCHES -- it's just
    # one of many dermorph entries, handled generically by LEXEME_CLASSES.
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
