#!/usr/bin/env python3
# Copyright 2024 Oqaasileriffik <oqaasileriffik@oqaasileriffik.gl>
# Licensed under the GNU GPL v3 or later - https://www.gnu.org/licenses/gpl-3.0.en.html

import json
import sys
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def check_lexicon(data: dict) -> list:
    errors = []
    ids: set = set()
    for lex in data.get('lexemes', []):
        lid = lex.get('id', '')
        if not lid:
            errors.append('lexeme missing id')
            continue
        if lid in ids:
            errors.append(f'duplicate id: {lid}')
        ids.add(lid)
        if not lex.get('kalaallisut'):
            errors.append(f'{lid}: missing kalaallisut field')
        if not lex.get('word_class'):
            errors.append(f'{lid}: missing word_class field')
        if not isinstance(lex.get('english'), list):
            errors.append(f'{lid}: english must be a list')
        if not isinstance(lex.get('danish'), list):
            errors.append(f'{lid}: danish must be a list')
        if not isinstance(lex.get('semantic_classes'), list):
            errors.append(f'{lid}: semantic_classes must be a list')
        if not isinstance(lex.get('attrs'), dict):
            errors.append(f'{lid}: attrs must be a dict')
    return errors


def check_semantic_classes(data: dict) -> list:
    errors = []
    codes: set = set()
    for sc in data.get('semantic_classes', []):
        code = sc.get('code', '')
        if not code:
            errors.append('semantic class missing code')
            continue
        if code in codes:
            errors.append(f'duplicate semantic class code: {code}')
        codes.add(code)
    return errors


def check_word_classes(data: dict) -> list:
    errors = []
    codes: set = set()
    for wc in data.get('word_classes', []):
        code = wc.get('code', '')
        if not code:
            errors.append('word class missing code')
            continue
        if code in codes:
            errors.append(f'duplicate word class code: {code}')
        codes.add(code)
    return errors


def check_valence_frames(data: dict) -> list:
    errors = []
    ids: set = set()
    for vf in data.get('valence_frames', []):
        vid = vf.get('id', '')
        if not vid:
            errors.append('valence frame missing id')
            continue
        if vid in ids:
            errors.append(f'duplicate valence id: {vid}')
        ids.add(vid)
    return errors


def cross_check(out: Path) -> list:
    """Verify that word_class, valence, domain codes in lexicon.json exist in reference files."""
    errors = []
    paths = {
        'lexicon': out / 'lexicon.json',
        'wc': out / 'word_classes.json',
        'val': out / 'valence_frames.json',
        'sem': out / 'semantic_classes.json',
        'dom': out / 'domains.json',
    }
    if not all(p.exists() for p in paths.values()):
        return ['cross_check skipped: not all files present']

    known_wc = {wc['code'] for wc in load(paths['wc']).get('word_classes', [])}
    known_val = {vf['code'] for vf in load(paths['val']).get('valence_frames', [])} | {None}
    known_sem = {sc['code'] for sc in load(paths['sem']).get('semantic_classes', [])}
    known_dom = {d['id'] for d in load(paths['dom']).get('domains', [])} | {None}

    for lex in load(paths['lexicon']).get('lexemes', []):
        lid = lex.get('id', '?')
        if lex.get('word_class') not in known_wc:
            errors.append(f'{lid}: unknown word_class {lex.get("word_class")!r}')
        if lex.get('valence') not in known_val:
            errors.append(f'{lid}: unknown valence {lex.get("valence")!r}')
        for sc in lex.get('semantic_classes', []):
            if sc not in known_sem:
                errors.append(f'{lid}: unknown semantic class {sc!r}')
        dom = lex.get('domain')
        if dom is not None and dom.get('id') not in known_dom:
            errors.append(f'{lid}: unknown domain id {dom.get("id")!r}')

    return errors


def check_domains(data: dict) -> list:
    errors = []
    ids: set = set()
    for dom in data.get('domains', []):
        did = dom.get('id', '')
        if not did:
            errors.append('domain missing id')
            continue
        if did in ids:
            errors.append(f'duplicate domain id: {did}')
        ids.add(did)
    return errors


CHECKS = [
    ('lexicon.json', check_lexicon),
    ('semantic_classes.json', check_semantic_classes),
    ('word_classes.json', check_word_classes),
    ('valence_frames.json', check_valence_frames),
    ('domains.json', check_domains),
]


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: validators.py <output-dir>', file=sys.stderr)
        sys.exit(1)

    out = Path(sys.argv[1])
    all_errors: list = []

    for fname, checker in CHECKS:
        path = out / fname
        if not path.exists():
            all_errors.append(f'missing file: {fname}')
            continue
        data = load(path)
        errs = checker(data)
        if errs:
            all_errors.extend(f'{fname}: {e}' for e in errs)
        else:
            count = next((len(v) for v in data.values() if isinstance(v, list)), 0)
            print(f'  {fname}: OK ({count} entries)', file=sys.stderr)

    cross = cross_check(out)
    if cross and cross[0].startswith('cross_check skipped'):
        print(f'  {cross[0]}', file=sys.stderr)
    else:
        all_errors.extend(cross)

    if all_errors:
        for e in all_errors:
            print(f'ERROR: {e}', file=sys.stderr)
        sys.exit(1)

    print('All validations passed.', file=sys.stderr)


if __name__ == '__main__':
    main()
