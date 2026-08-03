#!/usr/bin/env python3
# Copyright 2024 Oqaasileriffik <oqaasileriffik@oqaasileriffik.gl>
# Licensed under the GNU GPL v3 or later - https://www.gnu.org/licenses/gpl-3.0.en.html
#
# Shared constants derived from the katersat schema.

# MySQL SET bitfield order for kat_lexeme_attrs.let_attrs. The local schema.sql
# comment only documented the first 16 members; upstream's current schema.sql
# (github.com/Oqaasileriffik/katersat) has 3 more appended to the SET --
# 'see-instead', 'symbol', 'taaguutit' -- confirmed against the live data:
#   - see_instead (176 kal rows): loanword/spelling-variant entries pointing
#     to a preferred alternate form, e.g. 'albummi', 'aritmetikki', 'balletti'.
#   - symbol (3 kal rows): the headword IS a symbol character itself, e.g.
#     '≈', 'ə', '∨'.
#   - taaguutit (27,529 kal rows, all bulk-stamped 2025-12-30): provenance
#     marker for entries sourced from katersat's official terminology
#     ("taaguut") database, not a content-quality signal by itself -- most are
#     ordinary real headwords, though a handful of non-lexeme meta-notation
#     rows (see LEXEME_PATCHES in export.py) also happen to carry it.
ATTR_BITS = {
    'hidden':      1,
    'root':        2,
    'artificial':  4,
    'archaic':     8,
    'alternate':   16,
    'plural':      32,
    'mass':        64,
    'abbreviation': 128,
    'acronym':     256,
    'dermorph':    512,
    'enclitic':    1024,
    'strict_stem': 2048,
    'qual_plus':   4096,
    'qual_minus':  8192,
    'quant_plus':  16384,
    'quant_minus': 32768,
    'see_instead': 65536,
    'symbol':      131072,
    'taaguutit':   262144,
}

# MySQL ENUM order for kat_lexeme_attrs.lex_sandhi
SANDHI_VALUES = {0: None, 1: 'tru', 2: 'add', 3: 'gem', 4: 'rec', 5: 'rep', 6: 'dep'}

# val_langs bitmask: bit 0 = dan, bit 1 = eng, bit 2 = kal
VAL_LANG_BITS = {'dan': 1, 'eng': 2, 'kal': 4}

# Word class mapping between katersat codes and CG3/FST codes (from gloss.py)
WC_KATERSAT_TO_FST = {
    'N': 'T', 'V': 'V', 'Pali': 'Pali', 'Conj': 'Conj',
    'Adv': 'Adv', 'Interj': 'Intj', 'Pron': 'Pron',
    'Prop': 'Prop', 'Num': 'Num', 'Symbol': 'Symbol',
    'Adj': 'Adj', 'Part': 'Part', 'Prep': 'Prep',
}

# No CC-BY-SA grant has ever existed for this data -- this repo's only
# license document (LICENSE.md) is GPLv3, with no separate carve-out for
# data vs code. The 'license' field below previously read 'CC-BY-SA-4.0',
# copied from the unrelated Oqaasileriffik/dicts repo's terms without a
# matching grant here. See README.md's License section.
META = {
    'version': '1',
    'license': 'GPL-3.0-or-later',
    'attribution': 'Oqaasileriffik / Greenland Language Secretariat',
    'source': 'https://github.com/Oqaasileriffik/katersat',
}
