#!/usr/bin/env python3
# Copyright 2024 Oqaasileriffik <oqaasileriffik@oqaasileriffik.gl>
# Licensed under the GNU GPL v3 or later - https://www.gnu.org/licenses/gpl-3.0.en.html

import json
import sys
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def check_lexicon(data: dict) -> list:
    lexemes = data.get('lexemes')
    if lexemes is None:
        return ['missing "lexemes" key']
    if not isinstance(lexemes, list):
        return ['"lexemes" must be a list']
    if not lexemes:
        return ['"lexemes" list is empty']
    errors = []
    ids: set = set()
    for lex in lexemes:
        if not isinstance(lex, dict):
            errors.append('lexeme entry is not a dictionary')
            continue
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
    sem_classes = data.get('semantic_classes')
    if not isinstance(sem_classes, list):
        return ['missing or invalid "semantic_classes" list']
    errors = []
    codes: set = set()
    for sc in sem_classes:
        code = sc.get('code', '') if isinstance(sc, dict) else ''
        if not code:
            errors.append('semantic class missing code')
            continue
        if code in codes:
            errors.append(f'duplicate semantic class code: {code}')
        codes.add(code)
    return errors


def check_word_classes(data: dict) -> list:
    word_classes = data.get('word_classes')
    if not isinstance(word_classes, list):
        return ['missing or invalid "word_classes" list']
    errors = []
    codes: set = set()
    for wc in word_classes:
        code = wc.get('code', '') if isinstance(wc, dict) else ''
        if not code:
            errors.append('word class missing code')
            continue
        if code in codes:
            errors.append(f'duplicate word class code: {code}')
        codes.add(code)
    return errors


def check_valence_frames(data: dict) -> list:
    valence_frames = data.get('valence_frames')
    if not isinstance(valence_frames, list):
        return ['missing or invalid "valence_frames" list']
    errors = []
    ids: set = set()
    for vf in valence_frames:
        vid = vf.get('id', '') if isinstance(vf, dict) else ''
        if not vid:
            errors.append('valence frame missing id')
            continue
        if vid in ids:
            errors.append(f'duplicate valence id: {vid}')
        ids.add(vid)
    return errors


def check_domains(data: dict) -> list:
    domains = data.get('domains')
    if not isinstance(domains, list):
        return ['missing or invalid "domains" list']
    errors = []
    ids: set = set()
    for dom in domains:
        did = dom.get('id', '') if isinstance(dom, dict) else ''
        if not did:
            errors.append('domain missing id')
            continue
        if did in ids:
            errors.append(f'duplicate domain id: {did}')
        ids.add(did)
    return errors


def cross_check(loaded: dict) -> list:
    """Verify referential integrity using already-loaded data (avoids re-reading lexicon.json)."""
    required = {'lexicon', 'word_classes', 'valence_frames', 'semantic_classes', 'domains'}
    if not required.issubset(loaded):
        return ['cross_check skipped: not all files loaded']

    known_wc = {wc.get('code') for wc in loaded['word_classes'].get('word_classes', [])
                if isinstance(wc, dict) and 'code' in wc}
    known_val = {vf.get('code') for vf in loaded['valence_frames'].get('valence_frames', [])
                 if isinstance(vf, dict) and 'code' in vf} | {None}
    known_sem = {sc.get('code') for sc in loaded['semantic_classes'].get('semantic_classes', [])
                 if isinstance(sc, dict) and 'code' in sc}
    known_dom = {d.get('id') for d in loaded['domains'].get('domains', [])
                 if isinstance(d, dict) and 'id' in d} | {None}

    errors = []
    for lex in loaded['lexicon'].get('lexemes', []):
        if not isinstance(lex, dict):
            continue
        lid = lex.get('id', '?')
        if lex.get('word_class') not in known_wc:
            errors.append(f'{lid}: unknown word_class {lex.get("word_class")!r}')
        if lex.get('valence') not in known_val:
            errors.append(f'{lid}: unknown valence {lex.get("valence")!r}')
        for sc in lex.get('semantic_classes', []):
            if sc not in known_sem:
                errors.append(f'{lid}: unknown semantic class {sc!r}')
        dom = lex.get('domain')
        if isinstance(dom, dict) and dom.get('id') not in known_dom:
            errors.append(f'{lid}: unknown domain id {dom.get("id")!r}')
    return errors


CHECKS = [
    ('lexicon.json', 'lexicon', check_lexicon),
    ('semantic_classes.json', 'semantic_classes', check_semantic_classes),
    ('word_classes.json', 'word_classes', check_word_classes),
    ('valence_frames.json', 'valence_frames', check_valence_frames),
    ('domains.json', 'domains', check_domains),
]


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: validators.py <output-dir>', file=sys.stderr)
        sys.exit(1)

    out = Path(sys.argv[1])
    if not out.is_dir():
        print(f'Error: {out} is not a directory', file=sys.stderr)
        sys.exit(1)

    all_errors: list = []
    loaded: dict = {}

    for fname, key, checker in CHECKS:
        path = out / fname
        if not path.exists():
            all_errors.append(f'missing file: {fname}')
            continue
        data = load(path)
        loaded[key] = data
        errs = checker(data)
        if errs:
            all_errors.extend(f'{fname}: {e}' for e in errs)
        else:
            count = next((len(v) for v in data.values() if isinstance(v, list)), 0)
            print(f'  {fname}: OK ({count} entries)', file=sys.stderr)

    cross = cross_check(loaded)
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
