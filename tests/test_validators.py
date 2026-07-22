"""Tests for scripts/validators.py, focused on the FORBIDDEN_LEXEME_PATTERNS
guard: lexicon.json must never contain internal morphology-catalog notation
(e.g. a dermorph "Der/xy" marker) that scripts/export.py's LEXEME_CLASSES
should have routed elsewhere. A previous export regression let 95 such
entries slip through undetected; this guard exists so any future regression
fails validation instead of silently reaching lexicon.json / Oq.

Runs under pytest or as a plain script:
`python3 tests/test_validators.py` (exit 1 on failure).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
from validators import check_lexicon  # noqa: E402


def _lexicon(entries):
    return {'lexemes': entries}


def _entry(id_, kalaallisut, **overrides):
    base = {
        'id': id_,
        'kalaallisut': kalaallisut,
        'word_class': 'v',
        'english': [],
        'danish': [],
        'semantic_classes': [],
        'attrs': {},
        'domain': None,
    }
    base.update(overrides)
    return base


def test_ordinary_lexeme_passes():
    errors = check_lexicon(_lexicon([_entry('lex_1', 'illu')]))
    assert errors == []


def test_dermorph_single_affix_text_is_rejected():
    errors = check_lexicon(_lexicon([_entry('lex_5', 'SSAQ Der/nn')]))
    assert any('lex_5' in e and 'Der/xy' in e for e in errors)


def test_dermorph_chain_text_is_rejected():
    errors = check_lexicon(_lexicon([_entry('lex_262026', 'A Der/vv TUR Der/vv')]))
    assert any('lex_262026' in e for e in errors)


def test_regression_examples_from_the_2026_leak_are_all_rejected():
    # Exact strings observed leaking into a real published lexicon.json.
    leaked = [
        'A Der/vv',
        'GUMA Der/vv',
        'SINNAA Der/vv NNGIT Der/vv',
        'SINNAA Der/vv RUJUP Der/vv SUAR Der/vv',
        'SSAASUA Der/nv',
        'SSANGA Der/vv',
        'TARIAANNAA Der/vv',
    ]
    entries = [_entry(f'lex_{i}', text) for i, text in enumerate(leaked)]
    errors = check_lexicon(_lexicon(entries))
    flagged_ids = {e.split(':')[0] for e in errors}
    assert flagged_ids == {f'lex_{i}' for i in range(len(leaked))}


def test_real_acronym_headwords_are_not_false_flagged():
    # Real dictionary entries that are uppercase but unrelated to dermorph
    # notation must never trip this guard.
    entries = [_entry(f'lex_{w}', w) for w in ('EU', 'DNA', 'USB', 'FIFA', 'ADHD')]
    errors = check_lexicon(_lexicon(entries))
    assert errors == []


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
