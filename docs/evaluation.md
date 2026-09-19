# Evaluation notes

Run date: 2026-09-19. Windows, Python 3.12.14. Dependencies are pinned in `requirements.txt`.

This is a small synthetic-document demonstration, not a benchmark for real supplier invoices. No real customer dataset, production deployment, savings or financial outcome was measured.

## Three stages, with the failures retained

1. **Development:** 20 PDFs from the implementation-side generator: 19 text PDFs in classic inline and ledger label/value layouts, plus one image-only scan. Included missing values, arithmetic mismatches, unsupported date/currency and two-page documents.
2. **First independent layout:** a separate author did not inspect the parser or its patterns. Ten PDFs had two-column label-above-value blocks, English month names and amounts without colons. The initial line-based extractor got **0/66 printed fields**, with four correct nulls. Five valid source invoices were blocked; five defective invoices were also blocked. These blocks did not establish correct diagnosis of their defects. Source inspection identified the layout failure; these documents became the `regression` set after word-coordinate extraction was implemented.
3. **Fresh independent first pass:** another author did not inspect the parser, generators or other fixtures. Six PDFs used explicit English labels and ISO dates, including cross-page, changed-input, missing-date and mismatch cases. The fixed parser got **35/41 printed fields (85.4%)**, with one correct null. All six supplier fields were ambiguous because `SUPPLIER SERVICES / ACCOUNTS` was taken as a second supplier candidate. **0/6 whole documents** matched; all six were blocked, including four valid invoices. After observing this result, inline supplier matching was restricted to colon-delimited labels. Current reruns of this set are regression checks. **There is no untouched estimate for the final parser.** We stopped after this necessary defect fix rather than repeatedly sampling until a perfect headline appeared.

All independent PDF pages were rendered and inspected by their author. Their label files preserve printed totals even when wrong. No PDF was changed to suit the parser after its evaluation.

Original machine output:

- [`evaluation-initial.json`](evaluation-initial.json): development and original independent failure.
- [`evaluation-independent-first-pass.json`](evaluation-independent-first-pass.json): geometry repair plus fresh independent first pass.
- [`evaluation.json`](evaluation.json): current post-fix regression run; `unseen` is the historical folder name, not a claim that it remains unseen.

## Denominators and matching

Seven required fields: supplier, invoice number, invoice date, currency, subtotal, tax, total. Exact equality after explicit normalization: dot-decimal amounts rendered to two places; known English month dates converted to ISO; currency uppercased. Supplier and invoice number are compared exactly after trimming, not fuzzy matched.

| Current regression subset | Text PDFs | Printed field matches | Null matches | All seven slots exact | Complete-source documents exact |
|---|---:|---:|---:|---:|---:|
| Development | 19 | 131/131 | 2/2 | 19/19 | 17/17 |
| Former independent layout | 10 | 66/66 | 4/4 | 10/10 | 6/6 |
| Fresh layout after its observed fix | 6 | 41/41 | 1/1 | 6/6 | 5/5 |
| Total | 35 | 238/238 | 7/7 | 35/35 | 28/28 |

“All seven slots” includes correctly preserved nulls. “Complete-source” excludes documents whose source truly lacks a required value; a correct extraction of a bad printed total still counts as faithful extraction, while the arithmetic gate blocks it separately. No failed text document is removed from the field denominator. The image-only scan is excluded from text-field accuracy because OCR is unsupported; its explicit rejection is measured as **1/1** separately.

Current check outcomes before human confirmation: **22/22 source-valid text invoices passed; 13/13 source-defective text invoices blocked; 0 defective text invoices passed.** Every upload is initially pending. Human review requirement: **36/36 (100%)**, even when extraction and automatic checks pass. Regression labels are not a substitute for manual approval.

Recorded parsing time for the final run: development **0.125 s**, first-layout regression **0.097 s**, fresh-layout regression **0.052 s**. These are one local sequential run, without UI rendering/upload latency, not performance guarantees. Timings will vary on rerun.

## Behavior checks and independent review

`python -m pytest -q` → **12 passed, 2 warnings in 0.88 s** on this run. The warnings concern upstream Starlette/httpx/AnyIO deprecated test APIs.

- Changed PDF totals change extracted values and arithmetic results; `0.10 + 0.20` is exact.
- Pending, invalid and rejected records cannot export. Editing a confirmed record returns it to pending.
- A new exact or business duplicate blocks a previously confirmed invoice. Rejecting the extra copy clears the conflict. Same number/different supplier remains allowed.
- Missing fields stay null; corrections retain old/new values, notes and original extraction evidence.
- Cross-page evidence points at page 2; actual page PNG and original PDF endpoints work.
- Scanned, malformed and invalid-date/currency inputs are blocked; blank notes cannot approve records.
- SQLite state survives app reconstruction; formula-looking strings are neutralized in CSV.
- An empty supplier field cannot consume a neighboring `Invoice number: ...` cell. Supplier section headings cannot become invoice field values.

An independent reviewer executed isolated API checks and found two concrete issues: a stale green UI banner after rejected edits, and empty values consuming adjacent inline labels after the layout change. Both were fixed. The UI fix was verified in the running browser by changing `218.63` to `999.00`: confirmation was blocked with `+780.37` displayed. The adjacent-label bug has a targeted regression test. Review was scoped to required correctness; no production-readiness claim is made.

## Reproduce the demo

Use the README commands, then `python -m pytest -q` and `python scripts/evaluate.py`. The evaluator overwrites only `docs/evaluation.json`; historical first-pass reports remain unchanged. Fixture generators are optional and do not import application parsing code. The file `scripts/generate_heldout.py` retains its historical name but now writes the former independent set to `fixtures/regression`.

Screenshots under [`screenshots`](screenshots) are from the actual browser and backend using synthetic PDFs. [`example-reviewed.csv`](example-reviewed.csv) is a real export after UI confirmation. No continuous screen recording was produced.

## Remaining boundaries

The parser supports the labels and numeric formats listed in the README. Nearby value cells must be aligned within 12 PDF points and at most 36 points below a label; rows are grouped within 3 points and cell gaps over 24 points separate columns. These simple geometry rules can miss widely spaced, wrapped, densely packed or rotated values. Missing fields are never inferred from logos or totals. Conflicting candidates require review; a single incorrect text-layer candidate may pass structural checks and still need human correction.

The app does not reconcile line items, calculate tax policy, identify supplier aliases, validate bank details, detect all forged PDFs or integrate payments. Exact-file comparison uses SHA-256 solely for the required duplicate-file check. Local review history is editable by someone controlling the database. Authentication, upload-process isolation and multi-user review are outside this local demo.
