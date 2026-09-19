# Independent layout, now a regression set

**Evaluation status:** this set was initially withheld. The first extractor scored
0/66 present fields. After that failure, its two-column label-above-value layout
was used to fix extraction. It is now a **regression set, not unseen validation**.
The first measurements remain in `docs/evaluation-initial.json`; fresh independent
validation is in `fixtures/unseen`. The original authoring method is retained below.

These ten **synthetic text PDFs** were authored by an independent sub-agent
without access to the parser implementation or its patterns. They use one
plausible supplier layout: supplier and buyer information on the left,
document details on the right, a line-item table, and an amount summary.
They are personal portfolio examples, not client invoices or payment requests.

The independent author chose the labels, typography, date format, placement,
and cases before evaluation. The main implementation must be frozen before
first running these files; results should not be described as unseen-layout
results if the parser was then tuned on them. No extraction metrics were
generated or inferred while constructing the corpus.

## Coverage and labels

- Ten documents, eleven pages, one layout family; all contain selectable text.
- Five complete, arithmetically consistent invoices, including zero tax,
  GBP and EUR currencies, a thousands separator, and a two-page invoice whose
  amounts appear on page 2 while its identifying fields appear on page 1.
- Four missing-field cases: invoice number, issue date, tax, and supplier.
  Each missing value is truly absent, with `null` as its label.
- One total mismatch: subtotal 300.00 plus tax 24.00, but printed total 340.00.
- No scan samples are included; scan rejection needs a separate evaluation.

`labels.json` records seven fields per document: supplier, invoice number,
ISO issue date, currency, subtotal, tax, and printed total. Amounts are exact
decimal strings. The total label records the actual printed value even when
incorrect; arithmetic correctness is a separate expected issue.

For field accuracy there are **70 labeled slots: 66 present values and 4
explicitly absent values**. Report exact matches over present fields separately
from missing-value detection, and report document-level counts separately.
Do not silently exclude failed or unsupported documents from the denominator.
This small, single-family fixture set is a format generalization probe, not a
representative estimate of performance on real invoices.

Regenerate with `python scripts/generate_heldout.py` from the repository root
(requires ReportLab). The generator does not import or call the application.
