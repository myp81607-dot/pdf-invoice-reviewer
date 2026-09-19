# Evaluation notes

Verification date: 2026-09-19. Dependencies are pinned in `requirements.txt`. Latest runs and earlier extraction/review evidence are separated below.

This is a small synthetic-document demonstration, not a benchmark for real supplier invoices. No real customer dataset, production deployment, savings or financial outcome was measured.

## Latest reproducible run

[CI run 35446565476 passed](https://github.com/myp81607-dot/pdf-invoice-reviewer/actions/runs/35446565476) on code commit [`087ba6b0b3c41f18581bccecde0ddd7c58b6bf2e`](https://github.com/myp81607-dot/pdf-invoice-reviewer/commit/087ba6b0b3c41f18581bccecde0ddd7c58b6bf2e). The application and tests are unchanged from `fa997e9`, used for the local and browser checks. The cited CI result belongs to `087ba6b`; later documentation commits are separate.

| Environment | Python / Node | Python checks | Draft checks |
|---|---|---|---|
| GitHub Ubuntu 24.04.5, runner image `20260907.300.1` | 3.12.14 / 22.23.2 | 22 passed, 2 warnings, 0.84 s | 4 passed, 0 failed |
| Fresh local environment, Windows 11 build 26200 | 3.12.14 / 26.4.0 | 22 passed, 2 warnings, 1.56 s | 4 passed, 0 failed |

The CI commands are below. Locally, dependency installation used `python -m pip --isolated install -r requirements.txt` in a fresh virtual environment, followed by the same three check commands. CI used an empty `INVOICE_LABELS` and a database path under the runner's temporary directory; the local run used an allowlisted environment and temporary database. Neither received external-service credentials or a custom corpus.

```bash
python -m pip install -r requirements.txt
python -m pytest -q
node --test tests/drafts.test.mjs
python scripts/evaluate.py
```

Both extraction reruns reported **238/238 printed fields**, **7/7 nulls** and **35/35 text documents** matching; the separate scan was blocked. Checks passed for **22/22 source-valid invoices** and blocked **13/13 source-defective invoices**. These reproduce the known regression set, not a new unseen-layout result. The evaluator prints metrics; it does not itself fail the process merely because a metric drops.

The [first CI run](https://github.com/myp81607-dot/pdf-invoice-reviewer/actions/runs/35446383688), on `27e04ff`, failed before jobs because job-level `env` used an unavailable `runner` context; setting the temporary database through `GITHUB_ENV` in a run step fixed that workflow error.

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

Recorded parsing time for the original post-fix local run: development **0.125 s**, first-layout regression **0.097 s**, fresh-layout regression **0.052 s**. These exclude UI rendering/upload latency and are not performance guarantees. Timings vary on rerun.

## Original-release behavior checks and independent review

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

## Review-workflow revision, 2026-09-19

The reported lost-edit path was reproduced in the running browser: editing a field and its review note on invoice A, switching to B and returning to A restored saved values and erased both inputs. The UI now keeps a separate draft for each invoice in the current tab, with a visible draft state and an explicit discard action. CSV download is disabled while that tab has any drafts; the backend still exports only persisted, confirmed and currently valid records.

Verification completed in that revision:

- `python -m pytest -q`: **22 passed**, comprising the original 12 workflow checks and 10 version-conflict/configuration checks.
- `node --test tests/drafts.test.mjs`: **4 passed**. These cover field/note retention through a storage round trip, retaining the original expected version, clearing drafts only after both fields and notes are reverted, and not restoring a draft to a different record that reused an ID. Node is an optional test dependency, not an application runtime dependency.
- Actual operation in the in-app browser preserved both a changed field and a review note through invoice navigation, filter changes and another PDF upload.
- An actual two-tab check saved a note-only change in tab B, advancing revision 1 to 2. Tab A's stale save received HTTP 409, displayed the newer saved values, retained its own field and note, and disabled review actions until the draft was discarded. A note-only save therefore also participates in conflict detection.
- The configurable label path was exercised with `INVOICE_LABELS` and `python scripts/make_custom_sample.py`, which produces `data/custom-supplier.pdf`. Literal aliases are merged with built-in labels at startup and affect new uploads; previously extracted records are unchanged.

Drafts are written to `sessionStorage`, and `beforeunload` is registered while drafts exist. The first browser reload/leave-prompt attempt timed out without exposing a dialog. The follow-up below subsequently verified reload recovery; native warning and discard-dialog interaction remain unverified. Drafts are local browser state, not server backups or multi-user review sessions.

This revision adds label aliases, not new geometry rules, OCR or external integrations. No new unseen layout evaluation was run; the first-pass failures and post-fix regression figures above remain unchanged.

## Browser follow-up

Chrome **153.0.8010.52** was checked against the unchanged `fa997e9` application on an isolated local port and fresh database. The normal and amount-mismatch PDFs were seeded through the API: this Chrome controller could not upload files under its existing permissions, which were not expanded. Upload-retention evidence therefore remains the earlier in-app-browser run above; this is not one combined sequence in a single browser.

- In the original Chrome tab, the edited date `01 Sep 2026` and note survived a record switch, draft filtering and an actual reload. The filter reset to all records and a new server GET was observed, while both draft inputs returned.
- Tab A saved revision 1 as 2; tab B's stale save returned HTTP 409 and retained its field and note. After another tab loaded revision 2 and A confirmed revision 3, that stale revision-2 save was also blocked with its draft retained.
- Native **Discard draft** confirmation handling hung the controller, so the dialog interaction is unverified. In a usable stale-draft tab, reverting the date to the saved `2026-09-01` and clearing the note with the keyboard removed the draft and enabled export.
- **Export saved CSV** produced a new physical download. Although the controller's download wait timed out, reading that newly downloaded CSV verified one row: `DEMO-1001`, USD `218.63`, ISO date `2026-09-01`. The download is verified.

The native `beforeunload` warning was not observed, even though reload completed. No browser-close recovery or native discard-confirmation result is claimed. Save before closing a tab; browser storage and prompt policy still apply. The existing video and screenshots were not re-created for this follow-up.

## Reproduce the demo

Use the README commands, then `python -m pytest -q` and `python scripts/evaluate.py`. The evaluator overwrites only `docs/evaluation.json`; historical first-pass reports remain unchanged. Fixture generators are optional and do not import application parsing code. The file `scripts/generate_heldout.py` retains its historical name but now writes the former independent set to `fixtures/regression`.

The [60-second walkthrough](demo.mp4) contains 12 screenshots captured during actual browser operations against a fresh local database using synthetic PDFs. Each is held for five seconds with a caption. It is a condensed step demonstration, not a continuous screen recording or a measure of original operation speed. The three images under [`screenshots`](screenshots) were also refreshed from the running UI.

The walkthrough uses `fixtures/development/01-normal.pdf` and `07-amount-mismatch.pdf`: inspect the normal invoice's source date; change `2026-09-01` to `01 Sep 2026` and add a note; upload the mismatched invoice; return through the draft filter and find both inputs retained; confirm the normal invoice, normalizing the date to ISO; download its CSV; inspect the mismatched total; attempt confirmation and see the `+5.00` block with the note retained; reject that invoice. [`example-reviewed.csv`](example-reviewed.csv) is the actual download and contains exactly one saved, confirmed invoice, `DEMO-1001`, for USD `218.63`.

## Remaining boundaries

The parser supports the labels and numeric formats listed in the README. Nearby value cells must be aligned within 12 PDF points and at most 36 points below a label; rows are grouped within 3 points and cell gaps over 24 points separate columns. These simple geometry rules can miss widely spaced, wrapped, densely packed or rotated values. Missing fields are never inferred from logos or totals. Conflicting candidates require review; a single incorrect text-layer candidate may pass structural checks and still need human correction.

The app does not reconcile line items, calculate tax policy, identify supplier aliases, validate bank details, detect all forged PDFs or integrate payments. Exact-file comparison uses SHA-256 solely for the required duplicate-file check. Local review history is editable by someone controlling the database. Authentication, upload-process isolation and multi-user review are outside this local demo.
