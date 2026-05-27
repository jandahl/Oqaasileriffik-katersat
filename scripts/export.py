#!/usr/bin/env python3
# Copyright 2024 Oqaasileriffik <oqaasileriffik@oqaasileriffik.gl>
# Licensed under the GNU GPL v3 or later - https://www.gnu.org/licenses/gpl-3.0.en.html

import argparse
import gzip
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from schema_info import ATTR_BITS, META, SANDHI_VALUES


def has_attr(bits: int, name: str) -> bool:
    return bool(bits & ATTR_BITS[name])


def _meta() -> dict:
    return {**META, 'generated_at': datetime.now(timezone.utc).isoformat()}


def export_word_classes(db) -> dict:
    db.execute(
        "SELECT wc_class, wc_eng, wc_dan, wc_kal FROM kat_wordclasses ORDER BY wc_class"
    )
    return {
        'meta': _meta(),
        'word_classes': [
            {'id': f'wc_{r[0]}', 'code': r[0], 'english': r[1], 'danish': r[2], 'kalaallisut': r[3]}
            for r in db.fetchall()
        ],
    }


def export_semantic_classes(db) -> dict:
    db.execute(
        "SELECT sem_code, sem_eng, sem_dan, sem_kal FROM kat_semclasses ORDER BY sem_code"
    )
    return {
        'meta': _meta(),
        'semantic_classes': [
            {'id': f'sem_{r[0]}', 'code': r[0], 'english': r[1], 'danish': r[2], 'kalaallisut': r[3]}
            for r in db.fetchall()
        ],
    }


def export_valence_frames(db) -> dict:
    db.execute(
        "SELECT val_id, val_code, val_eng, val_dan, val_kal FROM kat_valence ORDER BY val_id"
    )
    return {
        'meta': _meta(),
        'valence_frames': [
            {
                'id': f'val_{r[0]}',
                'code': r[1],
                'english': r[2],
                'danish': r[3],
                'kalaallisut': r[4],
            }
            for r in db.fetchall()
        ],
    }


def export_domains(db) -> dict:
    db.execute(
        "SELECT dom_id, dom_code, dom_eng, dom_dan, dom_kal FROM kat_domains ORDER BY dom_id"
    )
    return {
        'meta': _meta(),
        'domains': [
            {
                'id': f'dom_{r[0]}',
                'code': r[1],
                'english': r[2],
                'danish': r[3],
                'kalaallisut': r[4],
            }
            for r in db.fetchall()
        ],
    }


def _fetch_translations(db, lang: str) -> dict:
    """Return {lex_id: [translation_string, ...]} ordered by syn_order, deduplicated."""
    db.execute(
        """
        SELECT gls.lex_id, tr.lex_lexeme
          FROM glue_lexeme_synonyms gls
          JOIN kat_lexemes tr ON gls.lex_syn = tr.lex_id
         WHERE tr.lex_language = ?
         ORDER BY gls.lex_id, gls.syn_order, tr.lex_id
        """,
        [lang],
    )
    result: dict = {}
    for lex_id, lexeme in db.fetchall():
        seen = result.setdefault(lex_id, [])
        if lexeme not in seen:
            seen.append(lexeme)
    return result


def export_lexicon(db) -> dict:
    # lex_register stores dom_id as a string after the registers→domains rename.
    # dom_id=0 ("General / Not Special") is treated as unspecified and exported as null.
    db.execute("SELECT dom_id, dom_code, dom_eng, dom_dan, dom_kal FROM kat_domains")
    domains = {
        str(r[0]): {'id': f'dom_{r[0]}', 'code': r[1], 'english': r[2], 'danish': r[3], 'kalaallisut': r[4]}
        for r in db.fetchall()
    }

    eng = _fetch_translations(db, 'eng')
    dan = _fetch_translations(db, 'dan')

    db.execute(
        """
        SELECT
            l.lex_id,
            l.lex_lexeme,
            l.lex_wordclass,
            l.lex_semclass,
            l.lex_sem2,
            l.lex_register,
            NULLIF(l.lex_gender, ''),
            l.lex_stem,
            l.lex_definition,
            l.lex_info,
            l.lex_verbframe,
            l.lex_oldspelling,
            COALESCE(a.let_attrs, 0),
            COALESCE(a.lex_sandhi, 0),
            v.val_code
          FROM kat_lexemes l
          LEFT JOIN kat_lexeme_attrs a ON l.lex_id = a.lex_id
          LEFT JOIN kat_valence v ON l.lex_valence = v.val_id
         WHERE l.lex_language = 'kal'
           AND NOT (COALESCE(a.let_attrs, 0) & 1)
         ORDER BY l.lex_lexeme, l.lex_id
        """
    )
    rows = db.fetchall()

    lexemes = []
    for row in rows:
        (lex_id, lexeme, wc, semclass, sem2, dom_key,
         gender, stem, definition, info, verbframe, oldspelling,
         attrs_bits, sandhi_int, val_code) = row

        sem_classes = [s for s in (semclass, sem2) if s and s != 'UNK']

        dom_str = str(dom_key) if dom_key else '0'
        if dom_str not in ('0', 'nnn') and dom_str not in domains:
            print(f'Warning: unknown domain key {dom_key!r} for lexeme {lex_id}, exporting as null', file=sys.stderr)
            domain = None
        else:
            domain = domains.get(dom_str) if dom_str not in ('0', 'nnn') else None

        if sandhi_int not in SANDHI_VALUES:
            print(f'Warning: unknown sandhi value {sandhi_int!r} for lexeme {lex_id}, exporting as null', file=sys.stderr)

        fst_analyses = [s for s in (stem or '').splitlines() if s.strip()] or None

        entry = {
            'id': f'lex_{lex_id}',
            'kalaallisut': lexeme,
            'english': eng.get(lex_id, []),
            'danish': dan.get(lex_id, []),
            'word_class': wc,
            'semantic_classes': sem_classes,
            'valence': val_code,
            'domain': domain,
            'gender': gender,
            'fst_analyses': fst_analyses,
            'definition': definition or None,
            'info': info or None,
            'verb_frame': verbframe or None,
            'old_spelling': oldspelling or None,
            'sandhi': SANDHI_VALUES.get(sandhi_int),
            'attrs': {
                'archaic': has_attr(attrs_bits, 'archaic'),
                'plural_only': has_attr(attrs_bits, 'plural'),
                'mass': has_attr(attrs_bits, 'mass'),
                'abbreviation': has_attr(attrs_bits, 'abbreviation'),
                'acronym': has_attr(attrs_bits, 'acronym'),
                'derived_morph': has_attr(attrs_bits, 'dermorph'),
                'enclitic': has_attr(attrs_bits, 'enclitic'),
            },
        }
        lexemes.append(entry)

    return {'meta': _meta(), 'lexemes': lexemes}


def write_json(data: dict, path: str, compress: bool = False) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2)
    tmp = p.with_suffix(p.suffix + '.tmp')
    tmp.write_text(text, encoding='utf-8')
    tmp.replace(p)
    print(f'  {p}  ({p.stat().st_size:,} bytes)', file=sys.stderr)
    if compress:
        gz = p.with_suffix(p.suffix + '.gz')
        tmp_gz = gz.with_suffix(gz.suffix + '.tmp')
        with gzip.open(tmp_gz, 'wt', encoding='utf-8', compresslevel=9) as f:
            f.write(text)
        tmp_gz.replace(gz)
        print(f'  {gz}  ({gz.stat().st_size:,} bytes)', file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description='Export katersat.sqlite to JSON')
    parser.add_argument('--db', default='katersat.sqlite', help='Path to katersat.sqlite')
    parser.add_argument('--output', '-o', default='exports', help='Output directory')
    parser.add_argument('--compress', action='store_true', help='Write .json.gz alongside .json')
    args = parser.parse_args()

    db_path = Path(args.db).resolve()
    if not db_path.is_file():
        print(f'Error: {args.db!r} is not a file. Run update.py first.', file=sys.stderr)
        sys.exit(1)

    from contextlib import closing
    with closing(sqlite3.connect(db_path.as_uri() + '?mode=ro', uri=True, isolation_level=None)) as con:
        db = con.cursor()

        exports = [
            ('word_classes.json', export_word_classes),
            ('semantic_classes.json', export_semantic_classes),
            ('valence_frames.json', export_valence_frames),
            ('domains.json', export_domains),
            ('lexicon.json', export_lexicon),
        ]

        out = args.output
        for fname, fn in exports:
            label = fname.replace('.json', '').replace('_', ' ')
            print(f'Exporting {label}...', file=sys.stderr)
            write_json(fn(db), f'{out}/{fname}', args.compress)

    print('Done.', file=sys.stderr)


if __name__ == '__main__':
    main()
