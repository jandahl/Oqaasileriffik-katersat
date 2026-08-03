# Katersat JSON Exporter

This is a fork of [Oqaasileriffik/katersat](https://github.com/Oqaasileriffik/katersat), the linguistic database underlying Oqaasileriffik's NLP tools for Kalaallisut (West Greenlandic). This fork adds a JSON export pipeline so the data can be consumed by web tools such as [KalaalliCut](https://github.com/jandahl/kalaalliCut).

Pre-built exports are published to **GitHub Pages**. Every file below is also available with a `.gz` suffix (gzip-compressed):

```
https://jandahl.github.io/Oqaasileriffik-katersat/lexicon.json
https://jandahl.github.io/Oqaasileriffik-katersat/dermorph.json
https://jandahl.github.io/Oqaasileriffik-katersat/enclitics.json
https://jandahl.github.io/Oqaasileriffik-katersat/morphemes.json
https://jandahl.github.io/Oqaasileriffik-katersat/word_classes.json
https://jandahl.github.io/Oqaasileriffik-katersat/semantic_classes.json
https://jandahl.github.io/Oqaasileriffik-katersat/valence_frames.json
https://jandahl.github.io/Oqaasileriffik-katersat/domains.json
https://jandahl.github.io/Oqaasileriffik-katersat/katersat.sqlite
https://jandahl.github.io/Oqaasileriffik-katersat/by-letter/<letter>.json
```

`by-letter/` has 31 shards: one per letter of the Kalaallisut alphabet (`a`–`z`, plus `å`, `æ`, `ø`, `ə`), and one catch-all `_.json` for headwords that don't start with a letter (e.g. leading digits or punctuation) — e.g. `by-letter/a.json`, `by-letter/n.json`, `by-letter/_.json`.

Full inventory of every file, with schema details for each: see [Exported files](#exported-files) below.

> **Setup**: enable GitHub Pages in repo Settings → Pages → Source: `gh-pages` branch, `/ (root)`.

---

## Quick start

```bash
# 1. Fetch the latest data from upstream and build katersat.sqlite
python3 update.py

# 2. Export to JSON (outputs to exports/)
python3 scripts/export.py

# 3. Validate the output (includes SQLite artifacts)
python3 scripts/validators.py exports
```

The exporter reads only from `katersat.sqlite` and writes JSON files to the output directory (full lexicon + per-letter shards + reference files). `scripts/validators.py` checks structural integrity of every exported JSON file (required fields, no duplicate/dangling ids, referential integrity against `word_classes.json`/`valence_frames.json`/`semantic_classes.json`/`domains.json`) and both `katersat.sqlite`/`katersat.sqlite.gz` (SQLite header/magic-byte check). It also runs a **regression guard**, `FORBIDDEN_LEXEME_PATTERNS`, against every `lexicon.json` entry's `kalaallisut` field: any text matching a known non-headword shape (currently: a `Der/xy` dermorph postbase marker) fails validation. This exists because a classification bug once let 95 such entries reach `lexicon.json` undetected (see `scripts/export.py`'s `LEXEME_CLASSES` history) — the guard runs against the *actual generated output*, so any future regression in that pipeline, from any cause, fails the build instead of silently reaching consumers. Extend it by appending `(pattern, reason)` tuples in `scripts/validators.py`.

Expected validator output includes:

```text
katersat.sqlite.gz: OK
katersat.sqlite: OK
All validations passed.
```

---

## Scripts

| Script | Purpose |
|---|---|
| `update.py` | Fetches `data.sql` from upstream and (re)builds `katersat.sqlite` |
| `scripts/export.py` | Reads `katersat.sqlite`, writes JSON to `exports/` |
| `scripts/validators.py` | Checks the exported JSON for integrity errors, including the `FORBIDDEN_LEXEME_PATTERNS` non-headword guard on `lexicon.json` |
| `scripts/schema_info.py` | Shared constants (attribute bitfield, sandhi enum, metadata) |
| `scripts/archive_data.py` | Archives `data.sql` to `data/YYYY-MM-DD.sql` when upstream content changes |

See [Testing](#testing) below for `tests/`, which is separate from `scripts/validators.py`: the tests exercise the export/validation code itself against small synthetic databases, while `validators.py` checks the real generated output.

### export.py options

```
python3 scripts/export.py [--db katersat.sqlite] [--output exports] [--compress]
```

`--compress` writes a `.json.gz` alongside every `.json` file (~95% size reduction for the lexicon), and also writes `katersat.sqlite.gz` — a gzip-compressed copy of the raw SQLite database.

---

## Exported files

### Lexeme classification

`kat_lexemes` holds several structurally different *kinds* of rows behind one shared schema: real dictionary headwords, plus a few internal morphology-catalog entry types (bound postbases/affixes, clitics) that reuse the same table but aren't citation-form words a dictionary user would search for. `scripts/export.py` classifies every row exactly once, against `LEXEME_CLASSES`, and routes it to the file registered for its class:

| class | rule | file | notes |
|---|---|---|---|
| `lexicon` (default) | everything not matched below | `lexicon.json` | real dictionary headwords only |
| `dermorph` | `attrs.derived_morph` bit set **or** the lexeme text contains a `Der/xy` marker | `dermorph.json` | see subtypes below |
| `enclitic` | `attrs.enclitic` bit set | `enclitics.json` | bound clitic morphemes in katersat's internal notation |

Classification is keyed off katersat's existing attrs bits, not lexeme text shape, wherever the bit is reliable — checked against the live data: an all-uppercase heuristic, for example, would misclassify ~90 legitimate real headwords (`EU`, `DNA`, `USB`, `FIFA`, `ADHD`, …) that are uppercase but carry no special attr bit. The one exception is `dermorph`, which also matches on text shape (a `Der/[nv][nv]` marker): katersat's own `dermorph` bit is inconsistently applied upstream — the identical postbase text sometimes exists as several rows under different `lex_id`s, only some flagged, and a few chain entries have exactly one row and it's unflagged. Bit-only matching let 95 such rows leak into `lexicon.json` before this was caught; the shape check is a safety net specifically for that gap, not a general design pattern to reach for elsewhere.

Hidden lexemes (`attrs.hidden`, internal database entries) never reach classification at all — they're excluded in SQL before this step.

**Attribute bits recently added to `attrs.*`:** `scripts/schema_info.py:ATTR_BITS` decodes 19 bits from katersat's `let_attrs` bitfield. Three were only recently identified (by diffing against upstream's current `schema.sql`, which has 3 more SET members than the copy in this repo) and are now exposed as `attrs.*` fields (see field notes below):

| bit name | value | kal rows | meaning |
|---|---|---|---|
| `see_instead` | 65536 | 176 | loanword/spelling-variant entries pointing to a preferred alternate form (e.g. `albummi`, `aritmetikki`) |
| `symbol` | 131072 | 3 | the headword is a symbol character itself (`≈`, `ə`, `∨`) |
| `taaguutit` | 262144 | 27,529 | provenance marker for entries sourced from katersat's official terminology ("taaguut") database — not a content-quality signal by itself |

None of these three classify a row out of `lexicon.json` — unlike `dermorph`/`enclitic`, they're ordinary attrs flags on real headwords. `root`, `artificial`, `alternate`, `strict_stem`, `qual_plus`, `qual_minus`, `quant_plus`, `quant_minus` are also decoded in `ATTR_BITS` but still not exposed as `attrs.*` fields — a deliberate scope decision, not done yet.

---

### `exports/lexicon.json` + `exports/by-letter/*.json`

The main export. 86,000+ real Kalaallisut dictionary headwords with translations, semantic tagging, and morphological metadata — the `lexicon` class from the table above.

`by-letter/` is a **partition** of `lexicon.json`, computed by `scripts/export.py:split_by_letter()`: every lexeme appears in exactly one shard (by the case-folded first character of `kalaallisut`, non-alphabetic/missing first characters bucketed into `_.json`), and the union of all 31 shards equals `lexicon.json`'s lexeme list exactly — same entries, same schema, no additions, no drops. This is enforced by a test (`tests/test_export_lexicon_patches.py`), not just documented as a convention. Both the full file and each shard share the identical `meta.generated_at` timestamp (literally the same object, not independently regenerated). Use `by-letter/` for lazy-loading in browser tools; use `lexicon.json` when you need the whole thing at once.

```json
{
  "meta": { ... },
  "lexemes": [
    {
      "id": "lex_12345",
      "kalaallisut": "nammineq",
      "english": ["oneself", "itself"],
      "danish": ["sig selv"],
      "word_class": "pron",
      "semantic_classes": ["Hprof", "H"],
      "valence": "IV",
      "domain": {
        "id": "dom_12",
        "code": "3.0.0",
        "english": "ØK ECONOMY & TRADE",
        "danish": "ØK ØKONOMI OG HANDEL",
        "kalaallisut": "ØK ANINGAASAQARNERMIK NALILERSUIFFIIT"
      },
      "gender": null,
      "fst_analyses": [
        "\"nammineq\" Pron Abs Sg",
        "\"nammineq\" Pron Abs Pl"
      ],
      "definition": "...",
      "info": null,
      "verb_frame": null,
      "old_spelling": null,
      "sandhi": null,
      "attrs": {
        "archaic": false,
        "plural_only": false,
        "mass": false,
        "abbreviation": false,
        "acronym": false,
        "derived_morph": false,
        "enclitic": false,
        "see_instead": false,
        "symbol": false,
        "taaguutit": false
      }
    }
  ]
}
```

**Field notes**

| Field | Type | Notes |
|---|---|---|
| `id` | string | Stable identifier (`lex_<int>`). The `LEXEME_PATCHES` `'split'` handler *can* mint `lex_patch_<int>_<n>` ids for a lexeme split out of a corrupted source row — see `data_issue` — but as of this writing no `split` patch is active, so no `lex_patch_*` id currently appears in the real output; only `'flag'` patches (3 of them) are currently in use |
| `kalaallisut` | string | The Kalaallisut lexeme |
| `english` | string[] | English translations, ordered by preference |
| `danish` | string[] | Danish translations, ordered by preference |
| `word_class` | string | See `word_classes.json` for codes (`t`=noun, `v`=verb, `prop`, `adj`, …) |
| `semantic_classes` | string[] | 0–2 codes from `semantic_classes.json`; empty when unclassified |
| `valence` | string\|null | Valence code from `valence_frames.json`; null for uninflected words |
| `domain` | object\|null | Subject domain from `domains.json`; null = general/unspecified |
| `gender` | string\|null | Grammatical gender code; rare, mostly null |
| `fst_analyses` | string[]\|null | Raw FST stem analyses (one string per analysis line from `kat_lexemes.lex_stem`) |
| `definition` | string\|null | Kalaallisut definition text |
| `info` | string\|null | Editorial notes |
| `verb_frame` | string\|null | Verbal argument frame description |
| `old_spelling` | string\|null | Pre-reform spelling variant |
| `sandhi` | string\|null | Sandhi rule: `tru`, `add`, `gem`, `rec`, `rep`, `dep`, or null |
| `attrs.archaic` | bool | Archaic/obsolete lexeme |
| `attrs.plural_only` | bool | Only occurs in plural forms |
| `attrs.mass` | bool | Mass noun |
| `attrs.abbreviation` | bool | Abbreviated form |
| `attrs.acronym` | bool | Acronym |
| `attrs.derived_morph` | bool | Derivational morpheme (not a free lexeme) |
| `attrs.enclitic` | bool | Enclitic element |
| `attrs.see_instead` | bool | Loanword/spelling-variant entry with a preferred alternate form somewhere else in the dictionary. Flag only — katersat doesn't structurally record *which* entry is preferred (checked: `glue_lexeme_synonyms` isn't it — same-language links there exist on ~23,400 unrelated lexemes and cover only 43 of the 176 `see_instead` rows), so this can't resolve to a target id |
| `attrs.symbol` | bool | Headword is a symbol character itself (e.g. `≈`, `ə`, `∨`) |
| `attrs.taaguutit` | bool | Sourced from katersat's official terminology ("taaguut") database; provenance only, not a content-quality signal |
| `data_issue` | object\|absent | Present only on entries corrected for a confirmed one-off upstream katersat data error (see `scripts/export.py:LEXEME_PATCHES`). `type` is `"split"` (one corrupted source row split into several `lex_patch_*` lexemes; `source_lex_id` gives the original `lex_<int>` id — supported by the code, but no `split` patch is currently registered) or `"flag"` (text left as-is upstream, tagged rather than corrected — currently the only type in active use, on 3 entries: `lex_244765`, `lex_244768`, `lex_244771`, legend entries documenting katersat's own `/`/`\` notation). `reason` explains the issue. Never set on entries routed to `dermorph.json`/`enclitics.json` — those use `class_subtype` instead; see below. |

`lexicon.json` never contains a `dermorph`- or `enclitic`-classified entry — see "Lexeme classification" above.

---

### `exports/dermorph.json`

Every katersat lexeme matching the `dermorph` class rule above — roughly 4,500 entries, none of which appear in `lexicon.json`. Each entry has the same shape as a `lexicon.json` lexeme, plus `class_subtype`:

| `class_subtype` | meaning | example |
|---|---|---|
| `single_affix` | one clean postbase, `"STEM Der/xy"` | `"SSAQ Der/nn"` |
| `chain` | an attested sequence of 2+ postbases combining in a fixed order | `"A Der/vv TUR Der/vv"`, `"VALLAAR Der/vv RUJUP Der/vv SUAR Der/vv NNGIT Der/vv TUQ Der/vn"` |
| `bare` | an internal morphophonemic stub with no `Der/xy` marker at all | `"IP"`, `"NIARIUTAA"`, `"NNGIT=INNAR=SINNAAvv"` |

```json
{
  "meta": { ... },
  "dermorph": [
    {
      "id": "lex_262026",
      "kalaallisut": "A Der/vv TUR Der/vv",
      "...": "... same shape as a lexicon.json lexeme entry ...",
      "class_subtype": "chain"
    }
  ]
}
```

None of these are errors — katersat legitimately catalogues its derivational-morpheme system this way — but a concatenated tag string like `"A Der/vv TUR Der/vv"` or a bare code like `"IP"` isn't a real dictionary headword, so all three subtypes are kept out of the general lexicon. `single_affix` entries are also covered, in a richer structured shape for postbase-building, by `morphemes.json` (see below) — `chain` and `bare` are not, since that export only extracts clean single affixes.

---

### `exports/enclitics.json`

Katersat lexemes flagged `enclitic` (`attrs.enclitic`) — a handful of bound clitic morphemes written in katersat's internal notation (e.g. `"AASIIT"`, `"LU"`), not citation-form words. Same shape as `lexicon.json`, no `class_subtype`.

---

### `exports/morphemes.json`

A structured, buildable-affix-oriented view of the `single_affix` subset of `dermorph.json` (~580 entries) — different envelope shape from every other export, purpose-built for postbase/derivation tooling (e.g. a grammar-aware morpheme picker) rather than dictionary lookup. Derived independently from `dermorph.json`: both come from the same underlying `dermorph`-shaped rows, but `export_morphemes()` re-queries and re-filters rather than reusing `export_lexicon()`'s output.

```json
{
  "meta": {
    "version": "1",
    "schema_version": "1.0",
    "morpheme_form": "morphophonemic",
    "buildable": false,
    "note": "Single derivational affixes extracted from katersat dermorph lexemes. Morpheme forms are katersat morphophonemic tags, not surface forms.",
    "...": "... plus the standard meta fields (license, attribution, source, generated_at) ..."
  },
  "by_category": {
    "denominal_nouns": {
      "kat_lex_163342": { "...": "same object as the matching entry in flat, below" }
    }
  },
  "flat": [
    {
      "id": "kat_lex_163342",
      "category": "verbal_modifiers",
      "lexical_facts": {
        "morpheme_type": "derivational_affix",
        "category_shift": "V -> V",
        "meaning": "..."
      },
      "application_logic": {
        "underlying_form": "SSA",
        "boundary_behavior": "additive",
        "continuation_class": "V_POSTBASE",
        "notes": ["katersat lex_id=163342", "Der/vv", "sandhi=add"]
      },
      "provenance": ["Oqaasileriffik/katersat", "lex_163342"]
    }
  ]
}
```

**Field notes**

| Field | Notes |
|---|---|
| `id` | `kat_lex_<lex_id>` (a different prefix from `lex_<id>` elsewhere, to signal this is a katersat-derived derivational unit, not a lexicon entry) |
| `category` | One of `denominal_verbs` (N→V), `deverbal_nouns` (V→N), `denominal_nouns` (N→N), `verbal_modifiers` (V→V), from the `Der/xy` marker |
| `lexical_facts.meaning` | First English gloss, falling back to Danish; omitted entirely if neither exists |
| `application_logic.underlying_form` | The katersat **morphophonemic tag** (e.g. `"SSA"`), not a surface form — see `meta.buildable` below |
| `application_logic.boundary_behavior` | `truncating`, `additive`, `assimilative`, or `none`, mapped from katersat's sandhi code; the raw code is preserved in `notes` |
| `meta.buildable` | Always `false`. This is an affix *inventory*, not a buildable morpheme set — consumers must not feed `underlying_form` values into a surface-form concatenation/sandhi builder, since they aren't surface forms |
| `by_category` | The same entries as `flat`, grouped by `category`, keyed by `id`, for lookups that don't want to filter the flat list |

`chain` and `bare` subtype entries in `dermorph.json` are **not** covered here — only clean single affixes can be represented in this buildable-unit shape.

---

### `exports/semantic_classes.json`

850 semantic class codes used to tag lexemes.

```json
{
  "meta": { ... },
  "semantic_classes": [
    {
      "id": "sem_HH",
      "code": "HH",
      "english": "Group of humans",
      "danish": null,
      "kalaallisut": null,
      "parent_id": "sem_H"
    },
    {
      "id": "sem_H",
      "code": "H",
      "english": "Human",
      "danish": "Menneskelig",
      "kalaallisut": null,
      "parent_id": null
    }
  ]
}
```

Codes prefixed `V.` are verbal semantic classes; all others are nominal.

`parent_id` links each class to its parent in the same file (`null` at the
root). Three code systems coexist, and the parent is the longest *existing*
ancestor in each, so callers can build the tree without string-parsing codes:

- dot-notation (`V.1.1` → `V`): trailing `.segments` are stripped; absent
  intermediate levels are skipped up to the surviving root.
- hyphenated lowercase (`act-move` → `act`): trailing `-segments` are stripped.
- letter / plain codes (`Adom` → `A`): longest character prefix that exists.

---

### `exports/word_classes.json`

14 word class codes.

```json
{
  "meta": { ... },
  "word_classes": [
    { "id": "wc_t", "code": "t", "english": "Noun", "danish": "Substantiv", "kalaallisut": null },
    { "id": "wc_v", "code": "v", "english": "Verb", "danish": "Verbum", "kalaallisut": null }
  ]
}
```

Note: katersat uses lowercase codes (`t`, `v`) internally; these differ from the uppercase FST/CG3 tags (`N`, `V`) used in analysis streams.

---

### `exports/valence_frames.json`

1,130 valence patterns describing verb argument structure.

```json
{
  "meta": { ... },
  "valence_frames": [
    {
      "id": "val_1",
      "code": "IV",
      "english": "Intransitive verb",
      "danish": "Intransitivt verbum",
      "kalaallisut": null
    }
  ]
}
```

---

### `exports/domains.json`

208 subject-domain entries, organized in a hierarchical dot-notation (`1.0.0` = top level, `1.1.0` = sub-domain, `1.1.1` = leaf).

```json
{
  "meta": { ... },
  "domains": [
    {
      "id": "dom_1",
      "code": "1.0.0",
      "english": "STAT STATE, PUBLIC ADMINISTRATION and POLITICS",
      "danish": "STAT Staten, offentlig forvaltning og politik",
      "kalaallisut": null,
      "parent_id": "dom_0"
    }
  ]
}
```

`parent_id` links each domain to its parent in the same file. Codes are
zero-padded 3-part dot-notation; the parent zeroes the deepest non-zero segment
(`X.Y.Z` → `X.Y.0` → `X.0.0` → `0.0.0`), and the root `0.0.0` plus a few codes
whose mid-level parent is absent from the taxonomy have `parent_id: null`.

Lexemes with `domain: null` belong to domain 0 ("General / Not Special").

---

### `meta` block (all files)

Every file includes a top-level `meta` object:

```json
{
  "meta": {
    "version": "1",
    "license": "GPL-3.0-or-later",
    "attribution": "Oqaasileriffik / Greenland Language Secretariat",
    "source": "https://github.com/Oqaasileriffik/katersat",
    "generated_at": "2024-01-01T02:00:00+00:00"
  }
}
```

---

## Testing

```bash
pip install pytest
pytest tests/ -v
```

Every test file is also runnable standalone without pytest — `python3 tests/test_export_lexicon_patches.py` etc. — printing `ok`/`FAIL` per test and exiting 1 on failure; useful in a sandbox without pytest installed. All tests use small hand-built in-memory SQLite databases (no `data.sql` required) and run in well under a second.

| File | Covers |
|---|---|
| `tests/test_export_lexicon_patches.py` | `export_lexicon()`'s `LEXEME_CLASSES` classifier (dermorph/enclitic routing, `class_subtype`), the `LEXEME_PATCHES` registry (split/flag handlers, the upstream-fixed-it tripwire), and `split_by_letter()`'s partition property (union of shards == lexicon entries, no drops/duplicates) |
| `tests/test_export_morphemes.py` | `export_morphemes()` — Der marker → category mapping, sandhi → boundary_behavior, compound/bare skip-and-count |
| `tests/test_export_sqlite.py` | `export_sqlite()` and the SQLite/gzip magic-byte checks in `scripts/validators.py` |
| `tests/test_validators.py` | `check_lexicon()`'s `FORBIDDEN_LEXEME_PATTERNS` non-headword guard, including the exact strings from the production leak this guard was built to catch |
| `tests/test_archive_data.py` | `scripts/archive_data.py`'s archive-filename sort order and changelog/dedup logic |

CI runs the full suite via `pytest tests/ -v` as a **required gate**: `export.yml`'s `export` job (which fetches data, regenerates JSON, and deploys to `gh-pages`) only runs after the `test` job passes — a test failure blocks the deploy, it doesn't just get logged.

---

## CI / automation

`.github/workflows/export.yml` runs weekly (Sunday 02:00 UTC), on manual dispatch, and on every push to `main` that touches `scripts/**`, `tests/**`, or the workflow file itself. It has two jobs:

**`test`** (always runs first):
1. Runs `pytest tests/ -v`. If this fails, the `export` job below does not run at all.

**`export`** (`needs: test`):
1. Runs `update.py` to fetch the latest `data.sql` from upstream and rebuild `katersat.sqlite`
2. Runs `scripts/archive_data.py` — if the upstream data has changed, archives `data.sql` to `data/YYYY-MM-DD.sql` and appends an entry to `data/CHANGELOG.md`, then commits back to `main`
3. Runs `scripts/export.py --compress` to regenerate all JSON exports
4. Runs `scripts/validators.py` to verify integrity (including the `FORBIDDEN_LEXEME_PATTERNS` guard — see [Scripts](#scripts) above)
5. Force-pushes the contents of `exports/` to the `gh-pages` branch, which GitHub Pages serves directly

Trigger a manual run from the GitHub Actions tab if you need an out-of-cycle refresh.

---

## SQLite endpoint

The raw `katersat.sqlite` database (and its gzip-compressed counterpart) is published to GitHub Pages alongside the JSON exports:

```
https://jandahl.github.io/Oqaasileriffik-katersat/katersat.sqlite
https://jandahl.github.io/Oqaasileriffik-katersat/katersat.sqlite.gz
```

This allows consumers that can query SQLite directly — for example via [SQLite WASM](https://sqlite.org/wasm/doc/trunk/index.md) in the browser — to fetch the entire database in one request and run arbitrary SQL queries client-side. The intended downstream consumer is [jandahl/oq](https://github.com/jandahl/oq).

---

## Example queries

All examples below were run against real exported data (not hand-written) before being added here. Table/column names use katersat's original prefixed names (`lex_lexeme`, `let_attrs`, …) — see [`schema.sql`](schema.sql) for the full schema; there's no separate "clean" naming layer in the SQLite file itself, only in the JSON export field names.

### jq — querying the JSON exports

```bash
# Look up a headword exactly (a spelling can have several senses -- "illu"
# below returns 6 entries, one per sense/domain, this is normal)
jq '.lexemes[] | select(.kalaallisut == "illu")' lexicon.json

# Count verbs
jq '[.lexemes[] | select(.word_class == "v")] | length' lexicon.json

# Count archaic-flagged entries
jq '[.lexemes[] | select(.attrs.archaic == true)] | length' lexicon.json

# List every entry with a known data-quality flag (currently 3, see LEXEME_PATCHES)
jq '.lexemes[] | select(.data_issue != null) | {id, kalaallisut, data_issue}' lexicon.json

# Count dermorph.json entries by class_subtype
jq '.dermorph | group_by(.class_subtype) | map({subtype: .[0].class_subtype, count: length})' dermorph.json

# List root (top-level) domains
jq '.domains[] | select(.parent_id == null) | {code, english}' domains.json

# Search a by-letter shard instead of the full lexicon.json (faster for one letter)
jq '.lexemes[] | select(.kalaallisut | startswith("qajaq"))' by-letter/q.json
```

### sqlite3 — querying `katersat.sqlite` directly

```bash
# Exact headword lookup
sqlite3 katersat.sqlite \
  "SELECT lex_id, lex_lexeme, lex_wordclass FROM kat_lexemes WHERE lex_language='kal' AND lex_lexeme = 'illu';"

# Decode the let_attrs bitfield with a bitwise AND -- values are in
# scripts/schema_info.py:ATTR_BITS (e.g. archaic = 8)
sqlite3 katersat.sqlite \
  "SELECT l.lex_lexeme FROM kat_lexemes l JOIN kat_lexeme_attrs a ON l.lex_id = a.lex_id
    WHERE l.lex_language='kal' AND (a.let_attrs & 8) LIMIT 10;"

# Translations for a headword, via the same glue_lexeme_synonyms join export.py uses
sqlite3 katersat.sqlite \
  "SELECT tr.lex_lexeme, tr.lex_language FROM kat_lexemes l
    JOIN glue_lexeme_synonyms g ON g.lex_id = l.lex_id
    JOIN kat_lexemes tr ON tr.lex_id = g.lex_syn
    WHERE l.lex_lexeme = 'illu' AND l.lex_language='kal'
    ORDER BY g.syn_order;"

# Lexeme count per word class
sqlite3 katersat.sqlite \
  "SELECT lex_wordclass, COUNT(*) FROM kat_lexemes WHERE lex_language='kal'
    GROUP BY lex_wordclass ORDER BY COUNT(*) DESC;"

# Combine with jq via -json output mode for structured post-processing
sqlite3 -json katersat.sqlite \
  "SELECT * FROM kat_lexemes WHERE lex_lexeme LIKE '%Der/vv%' LIMIT 3;" | jq .
```

---

## Possible improvements

- **Brotli compression** — Brotli typically gives ~15% better ratio than gzip for text; useful for GitHub Pages serving
- **Latin translations** — tracked in [issue #6](https://github.com/jandahl/Oqaasileriffik-katersat/issues/6); the DB has 905 `lat` entries linked via `glue_lexeme_synonyms`, the same mechanism used for `english`/`danish`. There's also `gre` (Greek, 13 entries), unmentioned in that issue. `fra` and `deu` are valid language codes in `kat_languages` but currently have **zero** entries in `kat_lexemes` — issue #6 originally cited `fra` (12) and `deu` (1), which no longer exist in the live data; re-check before acting on it
- **Structured `fst_analyses`** — currently exported as raw strings; could be parsed into structured objects (`{"lemma": "nammineq", "tags": ["Pron", "Abs", "Sg"]}`)
- **Curiosity, not a claimed bug: a handful of `t` (Noun)-tagged multi-word entries look verbal, not nominal** — e.g. `lex_250063` (`-mik ilisimasaqalerpoq`) ends in `-poq`, a finite 3sg indicative verb ending, not nominalizing morphology like the `-lik`/`-toq`/`-soq` endings on similar-looking neighbors (which do look correctly tagged as nominal/participial forms). Only ~4 entries share this exact shape (case-clitic prefix + full word, tagged `t`) out of 87k+, so low priority either way. This is *not* upstream feedback for Oqaasileriffik to act on — nobody here has the linguistic standing to make that call from outside the project — just a note for whoever wants to dig into katersat's `-`-prefixed collocation entries someday and understands the convention better than this export pipeline does.

---

## License

**Everything in this repository — code and data alike — is GPL-3.0-or-later.** See
[`LICENSE.md`](LICENSE.md) for the full text. There is no separate CC-BY-SA grant for
`exports/`; attribution ("Oqaasileriffik / Greenland Language Secretariat") is still owed,
under GPL-3.0-or-later.
