# PDF Invoice Reviewer

[简体中文](README.zh-CN.md) · [60-second walkthrough](docs/demo.mp4) · [Evaluation notes](docs/evaluation.md)

For an operations assistant preparing a spreadsheet from supplier invoices: upload a text PDF, check the extracted values against the source page, and export the records you have approved. Missing fields, inconsistent totals and duplicate invoices stop a record from entering the CSV.

`PDF → source check → edit or reject → confirm → CSV`

This is a local, single-reviewer portfolio project using synthetic invoices. It suits a known set of English supplier layouts; it does not read scans or connect to accounting, payment or AI services. Supplier labels can be configured without changing Python code. New layouts still need sample-based checks.

Tested code: [`087ba6b`](https://github.com/myp81607-dot/pdf-invoice-reviewer/commit/087ba6b0b3c41f18581bccecde0ddd7c58b6bf2e), [successful CI run](https://github.com/myp81607-dot/pdf-invoice-reviewer/actions/runs/35446565476) on Ubuntu 24.04.5, Python 3.12.14 and Node 22.23.2. This documentation update leaves that tested code unchanged.

| Check | Result |
|---|---|
| `python -m pytest -q` | 22 passed, 2 warnings |
| `node --test tests/drafts.test.mjs` | 4 passed |
| `python scripts/evaluate.py` | 238/238 printed fields, 7/7 missing values; 1/1 scan blocked |

[![Source PDF alongside editable fields](docs/screenshots/01-review-source.jpg)](docs/demo.mp4)

## Try the workflow

The [video](docs/demo.mp4) uses 12 captures from actual browser operations, with captions and each step held for five seconds. It is a condensed walkthrough, not continuous footage or the original operation speed. Repeat it locally with the included PDFs:

1. Upload `fixtures/development/01-normal.pdf` and open the date's source evidence. Change `2026-09-01` to `01 Sep 2026`—the same date—and enter a review note without saving.
2. Upload `fixtures/development/07-amount-mismatch.pdf`, then use the draft filter to return to the first invoice. The date and note remain. **Save changes** saves a pending record for later review; **Discard draft** restores saved values. CSV download stays disabled while this tab has any unfinished drafts.
3. Check the normal invoice against the PDF and use **Confirm**; its date is saved as `2026-09-01`. With drafts resolved, use **Export saved CSV**. The [example export](docs/example-reviewed.csv) contains one approved invoice, `DEMO-1001`, totaling USD `218.63`. Only saved, confirmed records that pass the current checks are included. [Confirmation screen](docs/screenshots/02-confirmed.jpg).
4. Return to the mismatched invoice. Its printed subtotal and tax add to `702.07`, but its total is `707.07`. Confirmation is blocked with a `+5.00` difference, keeping the review note. Compare the source, then reject it with a note or obtain a verified correction. Do not alter numbers merely to pass the check. [See the blocked state](docs/screenshots/03-amount-blocked.jpg).

Also try `08-missing-tax.pdf` in the same folder: the app leaves tax empty rather than calculating a missing source value. In `09-cross-page.pdf`, the total's **p.2** link opens the second page. Upload the same file twice to see duplicate blocking; reject the extra copy to clear it.

## Run locally

Requires Git and Python 3.11+; the recorded environment is Windows with Python 3.12.14. No API keys are needed.

```bash
git clone https://github.com/myp81607-dot/pdf-invoice-reviewer.git
cd pdf-invoice-reviewer
python -m venv .venv
```

Activate the environment with `.venv\Scripts\Activate.ps1` in Windows PowerShell, or `source .venv/bin/activate` on macOS/Linux, then run:

```bash
python -m pip install -r requirements.txt
python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8766
```

Open [localhost:8766](http://127.0.0.1:8766). The sample PDFs are already in the repository. If the port is in use, choose another port in the command and browser address.

## Use your own invoices

Start with a few documents you are allowed to process. You should be able to select their text in a PDF reader. Check one known-good invoice, one missing or incorrect field, and any multi-page layout before processing a batch. The seven output fields are supplier, invoice number, invoice date, currency, subtotal, tax and total; the CSV also includes a local record ID.

For supplier-specific setup, prepare representative PDFs, the expected seven values for each, and the rules you use to accept or reject them. Include duplicate examples and unusual labels. Redacted or synthetic copies are enough if they preserve the layout. A new date convention, additional output field or unfamiliar page structure needs a code change and its own verification.

For label aliases within an otherwise supported layout, copy [`config/labels.example.json`](config/labels.example.json), then edit the relevant field entries. Aliases are literal text, case insensitive, and add to the built-in labels:

```json
{
  "supplier": ["Supplier name"],
  "invoice_number": ["Document reference"]
}
```

Before starting the app, set the file path in PowerShell:

```powershell
$env:INVOICE_LABELS = "config/labels.example.json"
```

Or on macOS/Linux:

```bash
export INVOICE_LABELS=config/labels.example.json
```

Run `python scripts/make_custom_sample.py` to create `data/custom-supplier.pdf`, a synthetic invoice using these two aliases. Start the app with the configuration above and upload it; check that both fields match the source. Restart after changing the configuration. It applies to new uploads; existing records keep their original extraction. This adds names for fields, not OCR or support for arbitrary layouts.

The app stores PDFs, fields and review history in `data/invoices.sqlite3`, which Git ignores. To start a separate workspace, stop the server, set `INVOICE_DB` to another database path using the same environment-variable syntax, and restart. Keep the database private and use authorized data only.

## Edits and export

Each invoice has a draft in the current browser tab. The latest Chrome check retained the field and note through record switches, filtering and an actual reload; upload retention was verified earlier in the in-app browser. These are separate browser runs ([details](docs/evaluation.md#browser-follow-up)). A native leave warning is requested while drafts exist, but its appearance and the native discard-confirmation interaction remain unverified. Save before closing: tab closure is not a reliable way to retain drafts. A draft is not a saved invoice and is never part of an export.

Save, confirm and reject require a note. Saving returns an invoice to pending; confirming checks the submitted values; rejecting excludes it from export. History retains changed values, notes and UTC timestamps, with the original extraction evidence still visible. If another tab has changed the saved record, the app keeps your draft and reports a conflict. Review the newer saved values before discarding the old draft and re-entering any changes you still want. Alternatively, revert every field to its current saved value and clear the note; that tested path clears the draft and re-enables export when eligible records exist.

The backend rechecks required fields, date, currency, exact `Decimal` arithmetic and duplicates on confirmation and export. Both identical files and matching supplier/invoice-number pairs are blocked. A later duplicate can therefore block a previously confirmed invoice. Supplier matching normalizes case and whitespace, not company aliases. CSV strings that resemble spreadsheet formulas get an apostrophe prefix. Download is a repeatable snapshot, not an accounting posting operation.

## Supported input and limits

English text PDFs with explicit labels can use inline values, separate label/value cells or aligned label-above-value blocks, including fields across pages. Inline supplier fields need a colon. The extractor uses nearby text coordinates, so wrapped, widely spaced or dense layouts can fail; see the [geometry limits](docs/evaluation.md#remaining-boundaries).

| Field | Built-in labels |
|---|---|
| Supplier | Supplier, Vendor, Seller |
| Invoice number | Invoice number, Invoice reference/ref, Invoice no., Invoice ID, Invoice # |
| Date | Invoice date, Date issued, Issued on |
| Currency | Currency |
| Subtotal | Subtotal, Net amount |
| Tax | Tax, VAT amount |
| Total | Total, Total payable, Grand total, Amount due |

Labels ignore case. Dates must be `YYYY-MM-DD` or explicit English `DD Month YYYY` / `DD Mon YYYY`. Supported currencies are USD, EUR, GBP and CNY, without conversion. Amounts must be nonnegative dot decimals with at most two fractional digits; grouped commas are accepted. The check is only subtotal + tax = total, not line-item reconciliation or a tax-policy decision.

Files are limited to 10 MB and 12 pages. Scans, image-only pages in mixed PDFs, encryption, handwriting, unlabeled fields, supplier logos alone, credit notes and multilingual layouts are unsupported. Missing text fields can be entered with a verified source and note; an unsupported document remains blocked. A bad text layer can produce a plausible wrong value, so passing checks never replaces source review.

The server has no authentication or production upload isolation. Keep the loopback binding shown above. Shared deployment, multi-user approvals, ERP integration and retention policies need separate work. Local review history is not signed compliance evidence.

## Verification and implementation

The 22 Python checks cover the original workflow plus version conflicts and label configuration; the four Node checks cover draft state. Node is needed only for these checks, not to run the app. The same application and test files also passed in a fresh Windows 11 environment with Python 3.12.14 and Node 26.4.0. [Run environments and the first CI configuration failure](docs/evaluation.md#latest-reproducible-run) are recorded separately.

The earlier synthetic layout evaluation included a first independent failure of **0/66** printed fields and a fresh first-pass result of **35/41**. The latest local and CI reruns reproduced the post-fix result across 35 text PDFs: all 238 printed fields and seven missing values matched; 22 valid invoices passed and 13 defective invoices were blocked. The image-only scan was separately rejected. These are regression results on known synthetic layouts, not unseen or real-world accuracy. [Full denominators and failures](docs/evaluation.md) are retained.

The backend uses FastAPI, SQLite and pdfplumber; the UI is plain HTML/CSS/JavaScript. ReportLab generates synthetic fixtures. Start with [`app/extraction.py`](app/extraction.py), [`app/main.py`](app/main.py) and [`tests/test_workflow.py`](tests/test_workflow.py). No external model or accounting integration has been tested because none is part of this app.

The field/evidence model, geometry rules, review lifecycle, validation, duplicate checks and UI are implemented here. AI assisted implementation and review; independent agents authored evaluation layouts without reading the parser. [invoice2data's documentation and template source](https://github.com/invoice-x/invoice2data) informed the explicit-label approach; its runtime and template corpus are not bundled. [pdfplumber's documentation and page source](https://github.com/jsvine/pdfplumber) informed the actual text, word-coordinate and page-rendering API use. Both references were reviewed on 2026-09-19; their MIT notices are retained in [`docs/licenses`](docs/licenses). The project code and synthetic fixtures use the [MIT license](LICENSE).
