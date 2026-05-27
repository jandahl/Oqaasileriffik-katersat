# Katersat JSON Exporter

This is a fork of [Oqaasileriffik/katersat](https://github.com/Oqaasileriffik/katersat), the linguistic database underlying Oqaasileriffik's NLP tools for Kalaallisut (West Greenlandic). This fork adds a JSON export pipeline so the data can be consumed by web tools such as [KalaalliCut](https://github.com/jandahl/kalaalliCut).

Pre-built exports live in [`exports/`](exports/).

---

## Quick start

```bash
# 1. Fetch the latest data from upstream and build katersat.sqlite
python3 update.py

# 2. Export to JSON (outputs to exports/)
python3 scripts/export.py

# 3. Validate the output
python3 scripts/validators.py exports
```

The exporter reads only from `katersat.sqlite` and writes five JSON files to the output directory. Dependencies are Python 3.11+ stdlib only.

---

## Scripts

| Script | Purpose |
|---|---|
| `update.py` | Fetches `data.sql` from upstream and (re)builds `katersat.sqlite` |
| `scripts/export.py` | Reads `katersat.sqlite`, writes JSON to `exports/` |
| `scripts/validators.py` | Checks the exported JSON for integrity errors |
| `scripts/schema_info.py` | Shared constants (attribute bitfield, sandhi enum, metadata) |

### export.py options

```
python3 scripts/export.py [--db katersat.sqlite] [--output exports] [--compress]
```

`--compress` writes a `.json.gz` alongside every `.json` file (~95% size reduction for the lexicon).

---

## Exported files

### `exports/lexicon.json`

The main export. 87,000+ Kalaallisut lexemes with translations, semantic tagging, and morphological metadata.

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
| `id` | string | Stable identifier (`lex_<int>`) |
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

Hidden lexemes (internal database entries) are excluded from the export.

---

### `exports/semantic_classes.json`

850 semantic class codes used to tag lexemes.

```json
{
  "meta": { ... },
  "semantic_classes": [
    {
      "id": "sem_H",
      "code": "H",
      "english": "Human",
      "danish": "Menneskelig",
      "kalaallisut": null
    }
  ]
}
```

Codes prefixed `V.` are verbal semantic classes; all others are nominal.

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
      "kalaallisut": null
    }
  ]
}
```

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

## CI / automation

`.github/workflows/export.yml` runs weekly (Sunday 02:00 UTC) and on manual dispatch. It:

1. Runs `update.py` to fetch the latest `data.sql` from upstream and rebuild `katersat.sqlite`
2. Runs `scripts/export.py --compress` to regenerate all JSON exports
3. Runs `scripts/validators.py` to verify integrity
4. Commits any changed files in `exports/` back to the branch

Trigger a manual run from the GitHub Actions tab if you need an out-of-cycle refresh.

---

## Possible improvements

- **Split `lexicon.json` by initial letter** — at ~72 MB uncompressed the full lexicon is heavy for in-browser fetching; per-letter shards (`lexicon_a.json` … `lexicon_aa.json`) would allow lazy loading
- **Brotli compression** — Brotli typically gives ~15% better ratio than gzip for text; useful for GitHub Pages serving
- **Data hash in `meta`** — include a SHA-1 of `data.sql` so consumers can detect when the underlying data actually changed without diffing the full JSON
- **Live fetch in CI** — `update.py` already supports fetching from `https://tech.oqaasileriffik.gl/katersat/export-katersat.php`; the `data.sql` can be removed from git once network access is available in CI
- **Latin/French/German translations** — the DB contains `lat` (902 entries), `fra` (12), and `deu` (1) language entries linked via `glue_lexeme_synonyms`; trivial to add to the lexicon export
- **Structured `fst_analyses`** — currently exported as raw strings; could be parsed into structured objects (`{"lemma": "nammineq", "tags": ["Pron", "Abs", "Sg"]}`)

---

## License

**Code** (scripts in this repository): GPL-3.0-or-later — see [`LICENSE.md`](LICENSE.md)

**Data** (files in `exports/`): CC-BY-SA-4.0 — © Oqaasileriffik / Greenland Language Secretariat
