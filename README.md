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

**Attribute bits not yet surfaced as `attrs.*` fields:** `scripts/schema_info.py:ATTR_BITS` decodes 19 bits from katersat's `let_attrs` bitfield, but `lexicon.json`'s `attrs` object (see field notes below) only exposes 7 of them. Three were only recently identified (by diffing against upstream's current `schema.sql`, which has 3 more SET members than the copy in this repo) and aren't exposed anywhere in the JSON export yet:

| bit name | value | kal rows | meaning |
|---|---|---|---|
| `see_instead` | 65536 | 176 | loanword/spelling-variant entries pointing to a preferred alternate form (e.g. `albummi`, `aritmetikki`) |
| `symbol` | 131072 | 3 | the headword is a symbol character itself (`≈`, `ə`, `∨`) |
| `taaguutit` | 262144 | 27,529 | provenance marker for entries sourced from katersat's official terminology ("taaguut") database — not a content-quality signal by itself |

`root`, `artificial`, `alternate`, `strict_stem`, `qual_plus`, `qual_minus`, `quant_plus`, `quant_minus` are also decoded but unexposed. Exposing any of these as new `attrs.*` fields is a deliberate scope decision, not done yet.

---

### `exports/lexicon.json` + `exports/by-letter/*.json`

The main export. 86,000+ real Kalaallisut dictionary headwords with translations, semantic tagging, and morphological metadata — the `lexicon` class from the table above.

`lexicon.json` contains all lexemes. `by-letter/` splits the same lexemes into 31 shards by initial letter of the Kalaallisut headword (see the top of this README for the full shard list), each a valid subset with the same schema — useful for lazy-loading in browser tools. Both the full file and each shard share the same `meta.generated_at` timestamp.

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
        "enclitic": false
      }
    }
  ]
}
```

**Field notes**

| Field | Type | Notes |
|---|---|---|
| `id` | string | Stable identifier (`lex_<int>`), or `lex_patch_<int>_<n>` for a lexeme split out of a confirmed corrupted source row — see `data_issue` |
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
| `data_issue` | object\|absent | Present only on entries corrected for a confirmed one-off upstream katersat data error (see `scripts/export.py:LEXEME_PATCHES`). `type` is `"split"` (one corrupted source row split into several lexemes; `source_lex_id` gives the original `lex_<int>` id) or `"flag"` (text left as-is upstream, no confident correction yet). `reason` explains the issue. Never set on entries routed to `dermorph.json`/`enclitics.json` — those use `class_subtype` instead; see below. |

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
    "license": "CC-BY-SA-4.0",
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
| `tests/test_export_lexicon_patches.py` | `export_lexicon()`'s `LEXEME_CLASSES` classifier (dermorph/enclitic routing, `class_subtype`) and the `LEXEME_PATCHES` registry (split/flag handlers, the upstream-fixed-it tripwire) |
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

## Possible improvements

- **Brotli compression** — Brotli typically gives ~15% better ratio than gzip for text; useful for GitHub Pages serving
- **Latin/French/German translations** — tracked in [issue #6](https://github.com/jandahl/Oqaasileriffik-katersat/issues/6); the DB already has `lat` (902 entries), `fra` (12), and `deu` (1) linked via `glue_lexeme_synonyms`
- **Structured `fst_analyses`** — currently exported as raw strings; could be parsed into structured objects (`{"lemma": "nammineq", "tags": ["Pron", "Abs", "Sg"]}`)

---

## License

**Code** (scripts in this repository): GPL-3.0-or-later — see [`LICENSE.md`](LICENSE.md)

**Data** (files in `exports/`): CC-BY-SA-4.0 — © Oqaasileriffik / Greenland Language Secretariat
