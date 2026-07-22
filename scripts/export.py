#!/usr/bin/env python3
# Copyright 2024 Oqaasileriffik <oqaasileriffik@oqaasileriffik.gl>
# Licensed under the GNU GPL v3 or later - https://www.gnu.org/licenses/gpl-3.0.en.html

import argparse
import gzip
import json
import re
import shutil
import sys
from contextlib import closing
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


def _semclass_parent_code(code: str, codes: set) -> str | None:
    """Return the parent code for a semantic class code, or None if it is a root.

    Three code systems coexist; in each the parent is the longest *existing*
    ancestor, so missing intermediate levels are skipped rather than orphaning
    the entry:
      - dot-notation (V.1.1, V.10.11.2): strip trailing .segments
        (V.10.1.1 -> V.10.1 -> V.10 -> V). Intermediate dot levels are usually
        absent in the data, so the walk continues up to the surviving root (V).
      - hyphenated lowercase (act-move, cm-gas-h): strip trailing -segments
        (cm-gas-h -> cm-gas -> cm).
      - letter / plain codes (A, AA, Adom, act): longest proper character
        prefix that exists (Adom -> Ado -> Ad -> A; single chars -> None).
    Returns None when no ancestor exists in the data.
    """
    if not code:
        return None
    if '.' in code:
        parts = code.split('.')
        candidates = ['.'.join(parts[:n]) for n in range(len(parts) - 1, 0, -1)]
    elif '-' in code:
        parts = code.split('-')
        candidates = ['-'.join(parts[:n]) for n in range(len(parts) - 1, 0, -1)]
    else:
        candidates = [code[:n] for n in range(len(code) - 1, 0, -1)]
    for cand in candidates:
        # Each candidate is a proper prefix of `code` (strictly shorter, never
        # empty), so it can never equal `code`; a plain membership test suffices.
        if cand in codes:
            return cand
    return None


def export_semantic_classes(db) -> dict:
    db.execute(
        "SELECT sem_code, sem_eng, sem_dan, sem_kal FROM kat_semclasses ORDER BY sem_code"
    )
    rows = db.fetchall()
    codes = {r[0] for r in rows}
    classes = []
    for code, eng, dan, kal in rows:
        parent_code = _semclass_parent_code(code, codes)
        classes.append({
            'id': f'sem_{code}',
            'code': code,
            'english': eng,
            'danish': dan,
            'kalaallisut': kal,
            # ids are derived as sem_<code>, and parent_code is guaranteed to be
            # a code present in `codes`, so sem_<parent_code> is the parent's id.
            'parent_id': f'sem_{parent_code}' if parent_code is not None else None,
        })
    return {'meta': _meta(), 'semantic_classes': classes}


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


def _domain_parent_code(code: str, codes: set) -> str | None:
    """Return the parent code for a domain code, or None for the root.

    Domain codes are zero-padded 3-part dot-notation (a.b.c) where trailing
    zeros mark unused levels. The parent zeroes the deepest non-zero segment:
      X.Y.Z -> X.Y.0 ; X.Y.0 -> X.0.0 ; X.0.0 -> 0.0.0 ; 0.0.0 -> None.
    Returns None when the computed parent is absent from the data (a handful of
    mid-level codes are missing from the source taxonomy).
    """
    if not code:
        return None
    parts = code.split('.')
    if len(parts) != 3:
        # Defensive fallback for any non-3-part code: longest existing ancestor.
        candidates = ['.'.join(parts[:n]) for n in range(len(parts) - 1, 0, -1)]
        for cand in candidates:
            if cand and cand != code and cand in codes:
                return cand
        return None
    a, b, c = parts
    if a == '0' and b == '0' and c == '0':
        return None
    # The all-zero root is handled above, so at least one segment is non-zero
    # and zeroing the deepest one always yields a different, shorter code.
    if c != '0':
        parent = f'{a}.{b}.0'
    elif b != '0':
        parent = f'{a}.0.0'
    else:
        parent = '0.0.0'
    return parent if parent in codes else None


def export_domains(db) -> dict:
    db.execute(
        "SELECT dom_id, dom_code, dom_eng, dom_dan, dom_kal FROM kat_domains ORDER BY dom_id"
    )
    rows = db.fetchall()
    code_to_id = {r[1]: f'dom_{r[0]}' for r in rows}
    codes = set(code_to_id)
    domains = []
    for dom_id, code, eng, dan, kal in rows:
        parent_code = _domain_parent_code(code, codes)
        domains.append({
            'id': f'dom_{dom_id}',
            'code': code,
            'english': eng,
            'danish': dan,
            'kalaallisut': kal,
            # Domain ids are dom_<dom_id>, not derived from the code, so resolve
            # the parent code back to its id via the code->id map.
            'parent_id': code_to_id.get(parent_code) if parent_code is not None else None,
        })
    return {'meta': _meta(), 'domains': domains}


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


# --- Lexeme classification ---------------------------------------------------
# katersat's kat_lexemes table holds several structurally different *kinds* of
# rows behind one shared schema: real dictionary headwords, plus a handful of
# internal morphology-catalog entry types (bound postbases/affixes, clitics)
# that reuse the same table but aren't citation-form words a dictionary user
# would ever search for. Rather than special-case each shape as it's found,
# every row is classified once against LEXEME_CLASSES and routed to the file
# registered for its class. Unmatched rows fall through to the 'lexicon'
# class (lexicon.json) — the only class real end-user lookups should see.
#
# To add a new class: add one entry to LEXEME_CLASSES below. `match` receives
# (lexeme_text, attrs_bits) and returns True/False; the FIRST matching class
# wins (order matters — put narrower/more specific rules first), so pick
# reliable signals. Prefer keying off existing katersat attrs bits over text
# shape alone: an all-uppercase heuristic, for example, would misclassify the
# ~90 legitimate real headwords (EU, DNA, USB, FIFA, ADHD, ...) that are
# uppercase but carry no special attr bit — checked against the live data
# before adopting this design. `subtype` (optional) receives the same args
# and returns a short string distinguishing entries within the class
# (written into each entry's `class_subtype`); omit it if the class has none.
#
# 'dermorph' matches on the attrs bit OR the text shape, not the bit alone:
# katersat's own dermorph flagging is inconsistent — the identical postbase
# text often exists as several rows (different lex_id), only some of which
# carry the dermorph bit, and a handful of chain entries (e.g.
# "SINNAA Der/vv RUJUP Der/vv SUAR Der/vv") have exactly one row and it's
# unflagged. A bit-only check let 95 of these leak into lexicon.json (all
# unambiguous postbase-catalog text, checked against the live data — no real
# headword false-positive risk from the shape check).

# A clean single derivational morpheme: "<MORPHEME> Der/<xy>" (e.g. "SSAQ Der/nn").
# Shared with export_morphemes(), which extracts exactly this subtype into a
# richer, structured postbase-building shape.
_DER_TOKEN = re.compile(r'^(\S+)\s+Der/([nv][nv])$')
_DER_MARKER = re.compile(r'Der/[nv][nv]')


def _is_dermorph(lexeme: str, attrs_bits: int) -> bool:
    return has_attr(attrs_bits, 'dermorph') or bool(_DER_MARKER.search(lexeme or ''))


def _dermorph_subtype(lexeme: str, attrs_bits: int) -> str:
    text = (lexeme or '').strip()
    if _DER_TOKEN.match(text):
        return 'single_affix'
    if len(_DER_MARKER.findall(text)) >= 2:
        return 'chain'
    return 'bare'


LEXEME_CLASSES = [
    # (class_name, match(lexeme, attrs_bits) -> bool, output_filename, subtype_fn_or_None)
    (
        'dermorph',
        _is_dermorph,
        'dermorph.json',
        _dermorph_subtype,
    ),
    (
        'enclitic',
        lambda lexeme, attrs_bits: has_attr(attrs_bits, 'enclitic'),
        'enclitics.json',
        None,
    ),
]

# --- Known upstream data-issue patches --------------------------------------
# katersat's source data occasionally contains a genuinely malformed lexeme
# row — e.g. one row's text accidentally concatenates two unrelated entries.
# Rather than let a bad row export silently as-is, or drop it, patches for
# *confirmed one-off corruption* are declared here and applied to rows that
# fall through to the default 'lexicon' class in export_lexicon().
#
# NOTE: don't reach for this just because a lexeme's text looks concatenated
# or odd — check LEXEME_CLASSES above first. What initially looked like
# corruption in lex_262026 ("A Der/vv TUR Der/vv") turned out to be one of
# ~3,800 legitimate dermorph chain entries, now handled generically by the
# 'dermorph' class instead. Only use this registry for rows verified wrong.
#
# To patch a newly-discovered bad row:
#   1. Add an entry to LEXEME_PATCHES keyed by the source lex_id.
#   2. Set 'type' to an existing handler ('split' or 'flag'), or add a new
#      handler function below and register it in _PATCH_HANDLERS.
#   3. Set 'expected' to the exact current (raw, malformed) lex_lexeme text.
#      This is a tripwire: if upstream katersat later fixes the row (edits it,
#      splits it into proper separate rows, whatever), the live value will no
#      longer match 'expected' and the patch is skipped — the row exports as
#      upstream now has it, with a warning logged, instead of a stale patch
#      silently clobbering the fix forever. Remove the LEXEME_PATCHES entry
#      once that warning confirms upstream is fixed.
#   4. Always set 'reason' — it is logged and written into the exported
#      entry's `data_issue` field so consumers (and future maintainers) can
#      see why the row looks the way it does.
#
# 'split': the row's text is actually N distinct lexemes concatenated
#          together; 'parts' lists the corrected text for each. Each part
#          gets its own id, minted from _PATCH_ID_PREFIX so it can never
#          collide with a real katersat lex_<int> id.
# 'flag':  the text is left as upstream has it (no confident correction yet),
#          but the entry is marked with `data_issue` so it doesn't slip
#          through downstream consumers unnoticed.
LEXEME_PATCHES: dict[int, dict] = {
    # Legend/glossary entries documenting katersat's own "/" and "\" notation
    # conventions (used elsewhere in the dictionary), not Kalaallisut words.
    # Confirmed by direct translation, not by any attrs bit or shape rule --
    # they carry the same 'taaguutit' (terminology-batch) attr as ~27,500
    # legitimate entries, so no general classifier could isolate just these
    # three without also catching real content.
    244765: {
        'type': 'flag',
        'expected': '[ilisarnaatit pineqartut: \\ aamma / ]',
        'reason': 'legend entry documenting katersat\'s "\\" and "/" notation, not a Kalaallisut headword',
    },
    244768: {
        'type': 'flag',
        'expected': '[ilisarnaat pineqartoq: / ]',
        'reason': 'legend entry documenting katersat\'s "/" notation, not a Kalaallisut headword',
    },
    244771: {
        'type': 'flag',
        'expected': '[ilisarnaat pineqartoq: \\ ]',
        'reason': 'legend entry documenting katersat\'s "\\" notation, not a Kalaallisut headword',
    },
}

# Ids minted for patched rows live in a namespace that can never collide with
# a real katersat lex_<int> id (those are always plain integers).
_PATCH_ID_PREFIX = 'lex_patch'


def _patch_split(lex_id: int, base: dict, patch: dict) -> list[dict]:
    """Break one malformed lexeme row into its N constituent clean rows."""
    entries = []
    for i, part in enumerate(patch['parts'], start=1):
        entry = {**base, 'id': f'{_PATCH_ID_PREFIX}_{lex_id}_{i}', 'kalaallisut': part}
        entry['data_issue'] = {
            'type': 'split',
            'source_lex_id': f'lex_{lex_id}',
            'reason': patch['reason'],
        }
        entries.append(entry)
    return entries


def _patch_flag(lex_id: int, base: dict, patch: dict) -> list[dict]:
    """Keep the lexeme text as-is, but mark it as a known upstream data issue."""
    entry = {**base, 'data_issue': {'type': 'flag', 'reason': patch['reason']}}
    return [entry]


# Registry of patch-type -> handler(lex_id, base_entry, patch) -> list[entry].
# Add new patch types here as they're needed; LEXEME_PATCHES entries reference
# them by the 'type' string.
_PATCH_HANDLERS = {
    'split': _patch_split,
    'flag': _patch_flag,
}


def export_lexicon(db) -> dict[str, dict]:
    """Classify every kal lexeme row into one of LEXEME_CLASSES (or the
    default 'lexicon' class) and return {class_name: doc, ...}, one doc per
    output file: doc = {meta, <class_name>: [entries]}. 'lexicon' (the
    general dictionary export) is always present; the other keys match
    LEXEME_CLASSES, always present even when empty, so file shape is stable
    across runs.
    """
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

    # Each doc's entry-list key matches its file's stem, except 'lexicon' ->
    # 'lexemes' (kept for backward compatibility with existing consumers).
    doc_key = {'lexicon': 'lexemes'}
    buckets: dict[str, list] = {'lexicon': []}
    for class_name, _match, fname, _subtype_fn in LEXEME_CLASSES:
        buckets[class_name] = []
        doc_key[class_name] = Path(fname).stem

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

        base = {
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

        matched_class = None
        for class_name, match, _fname, subtype_fn in LEXEME_CLASSES:
            if match(lexeme, attrs_bits):
                matched_class = class_name
                entry = dict(base)
                if subtype_fn is not None:
                    entry['class_subtype'] = subtype_fn(lexeme, attrs_bits)
                buckets[class_name].append(entry)
                break

        if matched_class is not None:
            continue

        patch = LEXEME_PATCHES.get(lex_id)
        if patch is not None and patch.get('expected') is not None and (lexeme or '').strip() != patch['expected']:
            print(
                f'  lexicon: WARNING lex_{lex_id} no longer matches its LEXEME_PATCHES '
                f'entry (expected {patch["expected"]!r}, got {lexeme!r}) — upstream may '
                f'have fixed it; skipping patch and exporting as-is. Remove the '
                f'LEXEME_PATCHES entry once confirmed.',
                file=sys.stderr,
            )
            patch = None

        if patch is not None:
            handler = _PATCH_HANDLERS.get(patch['type'])
            if handler is None:
                raise ValueError(f'unknown patch type {patch["type"]!r} for lex_id {lex_id}')
            print(f'  lexicon: patched lex_{lex_id} ({patch["type"]}): {patch["reason"]}', file=sys.stderr)
            buckets['lexicon'].extend(handler(lex_id, base, patch))
        else:
            buckets['lexicon'].append(base)

    for class_name, _match, fname, _subtype_fn in LEXEME_CLASSES:
        if buckets[class_name]:
            print(f'  lexicon: routed {len(buckets[class_name])} {class_name} entries to {fname}', file=sys.stderr)

    meta = _meta()
    return {name: {'meta': meta, doc_key[name]: entries} for name, entries in buckets.items()}


# Der/XY derivation marker -> (morpheme category, category_shift, continuation_class).
# X = input class, Y = output class (n = noun/N, v = verb/V).
_DER_MAP = {
    'nv': ('denominal_verbs', 'N -> V', 'V_POSTBASE'),
    'vn': ('deverbal_nouns', 'V -> N', 'N_POSTBASE'),
    'nn': ('denominal_nouns', 'N -> N', 'N_POSTBASE'),
    'vv': ('verbal_modifiers', 'V -> V', 'V_POSTBASE'),
}

# katersat sandhi code -> grammarian boundary_behavior enum
# (truncating|additive|assimilative|none). gem (gemination) is the closest to
# 'assimilative'; rec/rep/dep have no enum value and fall back to 'none'. The raw
# katersat code is preserved in application_logic.notes either way.
_SANDHI_BEHAVIOR = {'tru': 'truncating', 'add': 'additive', 'gem': 'assimilative'}
# _DER_TOKEN is shared with the 'dermorph' LEXEME_CLASSES entry above.


def export_morphemes(db) -> dict:
    """Export single derivational affixes from katersat's bound-morpheme (dermorph)
    lexemes into the grammarian/oq morpheme shape ({meta, by_category, flat}).

    Raw-data conversion only: each `dermorph` lexeme whose form is a single
    "<MORPHEME> Der/<xy>" maps to one morpheme entry; the Der marker gives the
    category/category_shift/continuation_class and lex_sandhi gives the boundary
    behavior. Multi-morpheme compounds and bare (un-annotated) dermorph entries
    are skipped and counted (logged), never silently dropped.
    """
    eng = _fetch_translations(db, 'eng')
    dan = _fetch_translations(db, 'dan')
    db.execute(
        """
        SELECT l.lex_id, l.lex_lexeme, a.let_attrs, a.lex_sandhi
          FROM kat_lexemes l
          JOIN kat_lexeme_attrs a ON a.lex_id = l.lex_id
         WHERE l.lex_language = 'kal'
           AND (a.let_attrs & ?)        -- dermorph
           AND NOT (a.let_attrs & ?)    -- not hidden
         ORDER BY l.lex_id
        """,
        [ATTR_BITS['dermorph'], ATTR_BITS['hidden']],
    )
    flat: list[dict] = []
    skipped = 0
    for lex_id, lexeme, _attrs, sandhi_int in db.fetchall():
        m = _DER_TOKEN.match((lexeme or '').strip())
        if not m:
            skipped += 1  # compound (multi-Der) or bare/un-annotated affix
            continue
        morph, der = m.group(1), m.group(2)
        category, shift, cont = _DER_MAP[der]
        sandhi_code = SANDHI_VALUES.get(sandhi_int)
        behavior = _SANDHI_BEHAVIOR.get(sandhi_code or '', 'none')
        notes = [f'katersat lex_id={lex_id}', f'Der/{der}']
        if sandhi_code:
            notes.append(f'sandhi={sandhi_code}')
        glosses = eng.get(lex_id) or dan.get(lex_id)
        meaning = glosses[0] if glosses else ''
        flat.append({
            'id': f'kat_lex_{lex_id}',
            'category': category,
            'lexical_facts': {
                'morpheme_type': 'derivational_affix',
                'category_shift': shift,
                **({'meaning': meaning} if meaning else {}),
            },
            'application_logic': {
                'underlying_form': morph,
                'boundary_behavior': behavior,
                'continuation_class': cont,
                'notes': notes,
            },
            'provenance': ['Oqaasileriffik/katersat', f'lex_{lex_id}'],
        })

    by_category: dict = {}
    for e in flat:
        by_category.setdefault(e['category'], {})[e['id']] = e

    if skipped:
        print(
            f'  morphemes: skipped {skipped} compound/un-annotated dermorph entries '
            f'(kept {len(flat)} single affixes)',
            file=sys.stderr,
        )
    return {
        'meta': {
            **_meta(),
            'schema_version': '1.0',
            # underlying_form values are katersat morphophonemic tags (e.g. "SSAQ"),
            # NOT surface forms. Consumers MUST NOT feed them to a surface-form
            # concatenation/sandhi builder; they would produce wrong words. This
            # is an affix *inventory*, not a buildable morpheme set.
            'morpheme_form': 'morphophonemic',
            'buildable': False,
            'note': (
                'Single derivational affixes extracted from katersat dermorph lexemes. '
                'Morpheme forms are katersat morphophonemic tags, not surface forms.'
            ),
        },
        'by_category': by_category,
        'flat': flat,
    }


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


def export_sqlite(db_path: Path, output_dir: Path, compress: bool) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / 'katersat.sqlite'
    tmp = dest.with_suffix('.sqlite.tmp')
    tmp_gz = None
    try:
        with closing(sqlite3.connect(db_path.as_uri() + '?mode=ro', uri=True)) as src, closing(sqlite3.connect(tmp)) as dst:
            src.backup(dst)
        if compress:
            gz = output_dir / 'katersat.sqlite.gz'
            tmp_gz = gz.with_suffix('.gz.tmp')
            with open(tmp, 'rb') as src_file, gzip.open(tmp_gz, 'wb', compresslevel=9) as dst_file:
                shutil.copyfileobj(src_file, dst_file)
        if compress:
            tmp_gz.replace(gz)
            print(f'  {gz}  ({gz.stat().st_size:,} bytes)', file=sys.stderr)
        tmp.replace(dest)
        print(f'  {dest}  ({dest.stat().st_size:,} bytes)', file=sys.stderr)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        if tmp_gz and tmp_gz.exists():
            tmp_gz.unlink()
        raise


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

        reference_exports = [
            ('word_classes.json', export_word_classes),
            ('semantic_classes.json', export_semantic_classes),
            ('valence_frames.json', export_valence_frames),
            ('domains.json', export_domains),
        ]

        out = args.output
        for fname, fn in reference_exports:
            label = fname.replace('.json', '').replace('_', ' ')
            print(f'Exporting {label}...', file=sys.stderr)
            write_json(fn(db), f'{out}/{fname}', args.compress)

        print('Exporting lexicon...', file=sys.stderr)
        docs = export_lexicon(db)
        lexicon = docs['lexicon']
        write_json(lexicon, f'{out}/lexicon.json', args.compress)
        for class_name, _match, fname, _subtype_fn in LEXEME_CLASSES:
            write_json(docs[class_name], f'{out}/{fname}', args.compress)

        print('Exporting morphemes...', file=sys.stderr)
        write_json(export_morphemes(db), f'{out}/morphemes.json', args.compress)

        print('Splitting lexicon by first letter...', file=sys.stderr)
        by_letter_dir = Path(out) / 'by-letter'
        if by_letter_dir.is_dir():
            for f in by_letter_dir.iterdir():
                if f.is_file():
                    f.unlink()
        by_letter: dict[str, list[dict]] = {}
        for lex in lexicon['lexemes']:
            kalaallisut = lex.get('kalaallisut')
            kalaallisut_clean = kalaallisut.strip() if isinstance(kalaallisut, str) else ''
            first = kalaallisut_clean[0].lower() if kalaallisut_clean else '_'
            key = first if first.isalpha() else '_'
            by_letter.setdefault(key, []).append(lex)
        for key, entries in sorted(by_letter.items()):
            write_json({'meta': lexicon['meta'], 'lexemes': entries}, f'{out}/by-letter/{key}.json', args.compress)
        print(f'  {len(by_letter)} letter shards', file=sys.stderr)

    print('Exporting SQLite...', file=sys.stderr)
    export_sqlite(db_path, Path(out), args.compress)

    print('Done.', file=sys.stderr)


if __name__ == '__main__':
    main()
