# Visitor notes

One JSON file per note, matching `../schemas/visitor-note.schema.json`.
Read `../docs/VISITORS.md` before writing one.

Name the file `YYYY-MM-DD-<short-name>.json`. Pull requests that touch this
folder are checked by `.github/workflows/visitor-notes.yml`, which validates
the note and recomputes any proof of reading.

To compute a proof locally:

```
python scripts/validate_visitor_notes.py proof <salt> experiments/PROP-EXP-MEM-001/TEST_PROMPT.md
```

Notes are kept as submitted. A note whose proof fails is not deleted; the
failure is recorded next to it.
