# Independent unseen invoice fixtures

**Result status:** the first pass after the geometry repair was 35/41 present
fields and 1/1 absent field. A section title was incorrectly treated as a second
supplier candidate, making all six supplier fields ambiguous. A subsequent fix
requires a colon for inline supplier labels. Current reruns of this set are
**post-fix regression results**, not independent accuracy estimates. The original
first pass is retained in `docs/evaluation-independent-first-pass.json`.

Six synthetic supplier invoices authored independently of the application parser,
its label rules, its other fixtures, and the other fixture generator. Every PDF
contains selectable text; none is a scan. The visual template was designed for
this set. Amounts use dot decimals, dates use ISO notation, and currencies are
explicit three-letter codes.

The set contains four arithmetically valid invoices, including a two-page invoice
and a changed-input counterpart; one invoice with a genuinely absent invoice
date; and one invoice with an intentionally inconsistent printed total.

`labels.json` is an array of records. `file` is relative to this directory;
`expected` contains the seven required field values. Date strings are canonical
YYYY-MM-DD; amount strings retain two decimal places. A JSON null means that
field is absent from the printed invoice. Values for the mismatch case preserve
the printed numbers and do not silently correct the total. `case`, `pages`, and
`purpose` describe fixture intent.

Regenerate from the repository root with:

```powershell
python scripts/generate_unseen.py
```

The fixture author did not execute extraction against this set and did not
change the fixture contents based on extractor behavior. All seven PDF pages
were rendered and visually inspected before release.
