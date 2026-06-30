"""Tests for export_morphemes() in scripts/export.py.

Uses a tiny hand-built sqlite (no 55 MB data.sql needed). Runs under pytest or
as a plain script: `python3 tests/test_export_morphemes.py` (exit 1 on failure).
"""
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
from export import export_morphemes  # noqa: E402

DERMORPH = 512
HIDDEN = 1
ROOT = 2


def _make_db(tmp_path: Path) -> sqlite3.Cursor:
    """Build a minimal katersat-shaped DB with a handful of morpheme rows."""
    p = tmp_path / 'm.sqlite'
    con = sqlite3.connect(p)
    con.executescript(
        """
        CREATE TABLE kat_lexemes (
            lex_id INTEGER PRIMARY KEY, lex_lexeme TEXT, lex_language TEXT
        );
        CREATE TABLE kat_lexeme_attrs (
            lex_id INTEGER PRIMARY KEY, let_attrs INTEGER, lex_sandhi INTEGER
        );
        CREATE TABLE glue_lexeme_synonyms (
            lex_id INTEGER, lex_syn INTEGER, syn_order INTEGER
        );
        """
    )
    lexemes = [
        (1, 'SSAQ Der/nn', 'kal'),       # nn, sandhi add
        (2, 'IR Der/nv', 'kal'),         # nv, sandhi tru, no gloss
        (3, 'TUQ Der/vn', 'kal'),        # vn, sandhi gem -> assimilative
        (4, 'GALLAR Der/vv', 'kal'),     # vv, sandhi rec -> none
        (5, 'IR Der/nv NIAQ Der/nn', 'kal'),  # compound -> skipped
        (6, 'IP', 'kal'),                # bare, no Der -> skipped
        (7, 'illu', 'kal'),              # not dermorph -> not selected
        (8, 'XXX Der/nn', 'kal'),        # dermorph + hidden -> excluded
        (9, 'REP Der/vv', 'kal'),        # vv, sandhi rep (5) -> none
        (10, 'DEP Der/nn', 'kal'),       # nn, sandhi dep (6) -> none
        (11, 'SIUR Der/nv', 'kal'),      # nv, Danish-only gloss
        (100, 'small one', 'eng'),       # english gloss target for lex 1
        (201, 'finde', 'dan'),           # danish-only gloss target for lex 11
    ]
    attrs = [
        (1, DERMORPH, 2),                # add
        (2, DERMORPH, 1),                # tru
        (3, DERMORPH, 3),                # gem
        (4, DERMORPH, 4),                # rec (no enum)
        (5, DERMORPH, 2),
        (6, DERMORPH, 1),
        (7, ROOT, 0),
        (8, DERMORPH | HIDDEN, 2),
        (9, DERMORPH, 5),                # rep (no enum)
        (10, DERMORPH, 6),               # dep (no enum)
        (11, DERMORPH, 2),               # add
    ]
    con.executemany('INSERT INTO kat_lexemes VALUES (?,?,?)', lexemes)
    con.executemany('INSERT INTO kat_lexeme_attrs VALUES (?,?,?)', attrs)
    con.executemany(
        'INSERT INTO glue_lexeme_synonyms VALUES (?,?,?)',
        [(1, 100, 0), (11, 201, 0)],
    )
    con.commit()
    return con.cursor()


def _by_id(doc):
    return {e['id']: e for e in doc['flat']}


def test_clean_single_affixes_only(tmp_path: Path):
    doc = export_morphemes(_make_db(tmp_path))
    ids = _by_id(doc)
    # Only the clean single-Der affixes survive.
    assert set(ids) == {
        'kat_lex_1', 'kat_lex_2', 'kat_lex_3', 'kat_lex_4',
        'kat_lex_9', 'kat_lex_10', 'kat_lex_11',
    }
    # Compound, bare, non-dermorph and hidden entries are excluded.
    for absent in ('kat_lex_5', 'kat_lex_6', 'kat_lex_7', 'kat_lex_8'):
        assert absent not in ids


def test_der_marker_mapping(tmp_path: Path):
    ids = _by_id(export_morphemes(_make_db(tmp_path)))
    e1 = ids['kat_lex_1']
    assert e1['category'] == 'denominal_nouns'
    assert e1['lexical_facts']['category_shift'] == 'N -> N'
    assert e1['lexical_facts']['morpheme_type'] == 'derivational_affix'
    assert e1['application_logic']['underlying_form'] == 'SSAQ'
    assert e1['application_logic']['continuation_class'] == 'N_POSTBASE'
    assert ids['kat_lex_2']['category'] == 'denominal_verbs'
    assert ids['kat_lex_2']['application_logic']['continuation_class'] == 'V_POSTBASE'
    assert ids['kat_lex_3']['category'] == 'deverbal_nouns'
    assert ids['kat_lex_4']['category'] == 'verbal_modifiers'


def test_sandhi_to_boundary_behavior(tmp_path: Path):
    ids = _by_id(export_morphemes(_make_db(tmp_path)))
    assert ids['kat_lex_1']['application_logic']['boundary_behavior'] == 'additive'   # add
    assert ids['kat_lex_2']['application_logic']['boundary_behavior'] == 'truncating'  # tru
    assert ids['kat_lex_3']['application_logic']['boundary_behavior'] == 'assimilative'  # gem
    # rec/rep/dep have no enum value -> none, but the raw code is preserved in notes.
    assert ids['kat_lex_4']['application_logic']['boundary_behavior'] == 'none'
    assert 'sandhi=rec' in ids['kat_lex_4']['application_logic']['notes']
    assert ids['kat_lex_9']['application_logic']['boundary_behavior'] == 'none'   # rep
    assert 'sandhi=rep' in ids['kat_lex_9']['application_logic']['notes']
    assert ids['kat_lex_10']['application_logic']['boundary_behavior'] == 'none'  # dep
    assert 'sandhi=dep' in ids['kat_lex_10']['application_logic']['notes']
    assert 'sandhi=add' in ids['kat_lex_1']['application_logic']['notes']
    assert 'Der/nn' in ids['kat_lex_1']['application_logic']['notes']


def test_gloss_and_provenance(tmp_path: Path):
    ids = _by_id(export_morphemes(_make_db(tmp_path)))
    # English synonym becomes the meaning.
    assert ids['kat_lex_1']['lexical_facts']['meaning'] == 'small one'
    # No English gloss → fall back to the Danish synonym.
    assert ids['kat_lex_11']['lexical_facts']['meaning'] == 'finde'
    # Affix without any gloss simply omits meaning (schema does not require it).
    assert 'meaning' not in ids['kat_lex_2']['lexical_facts']
    # Provenance always cites katersat + the lex id.
    assert ids['kat_lex_1']['provenance'] == ['Oqaasileriffik/katersat', 'lex_1']


def test_envelope_shape(tmp_path: Path):
    doc = export_morphemes(_make_db(tmp_path))
    assert 'generated_at' in doc['meta'] and doc['meta']['schema_version'] == '1.0'
    # Non-buildability is signalled explicitly so consumers never surface-build these.
    assert doc['meta']['buildable'] is False
    assert doc['meta']['morpheme_form'] == 'morphophonemic'
    # by_category mirrors flat; boundary_behavior stays within the grammarian enum.
    allowed = {'truncating', 'additive', 'assimilative', 'none'}
    flat_ids = {e['id'] for e in doc['flat']}
    cat_ids = {eid for cat in doc['by_category'].values() for eid in cat}
    assert flat_ids == cat_ids
    for e in doc['flat']:
        assert e['application_logic']['boundary_behavior'] in allowed
        assert e['id'] and e['category']  # schema-required fields present


if __name__ == '__main__':
    import inspect
    import tempfile
    import traceback

    failures = 0
    for _name, _fn in sorted(globals().items()):
        if _name.startswith('test_') and callable(_fn):
            with tempfile.TemporaryDirectory() as d:
                try:
                    if 'tmp_path' in inspect.signature(_fn).parameters:
                        _fn(Path(d))
                    else:
                        _fn()
                    print(f'ok - {_name}')
                except Exception:
                    failures += 1
                    traceback.print_exc()
                    print(f'FAIL - {_name}')
    print('SUCCESS' if not failures else f'FAILURE ({failures})')
    sys.exit(1 if failures else 0)
