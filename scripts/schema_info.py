#!/usr/bin/env python3
# Copyright 2024 Oqaasileriffik <oqaasileriffik@oqaasileriffik.gl>
# Licensed under the GNU GPL v3 or later - https://www.gnu.org/licenses/gpl-3.0.en.html
#
# Shared constants derived from the katersat schema.

# MySQL SET bitfield order for kat_lexeme_attrs.let_attrs
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

META = {
    'version': '1',
    'license': 'CC-BY-SA-4.0',
    'attribution': 'Oqaasileriffik / Greenland Language Secretariat',
    'source': 'https://github.com/Oqaasileriffik/katersat',
}
