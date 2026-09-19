"""Build independent, synthetic held-out invoice fixtures; never invokes the parser.

Run from anywhere: python scripts/generate_heldout.py
Dependencies: reportlab (fixture generation only).
"""

from datetime import date
from decimal import Decimal
import json
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


DEST = Path(__file__).resolve().parents[1] / "fixtures" / "regression"
WIDTH, HEIGHT = A4
INK = HexColor("#163b36")
GRAY = HexColor("#66746f")
PALE = HexColor("#edf4ef")


def record(name, number, day, currency, subtotal, tax, total, *, supplier="Fern & Field Office Supply", pages=1, issues=()):
    return {
        "file": name + ".pdf",
        "pages": pages,
        "fields": {
            "supplier": supplier,
            "invoice_number": number,
            "invoice_date": day,
            "currency": currency,
            "subtotal": subtotal,
            "tax": tax,
            "total": total,
        },
        "expected_issues": list(issues),
    }


CASES = [
    record("01_standard_usd", "FF-260901", "2026-09-01", "USD", "1200.00", "96.00", "1296.00"),
    record("02_zero_tax", "FF-260902", "2026-09-02", "USD", "420.00", "0.00", "420.00"),
    record("03_gbp_decimals", "FF-260903", "2026-09-03", "GBP", "165.50", "33.10", "198.60"),
    record("04_thousands_separator", "FF-260904", "2026-09-04", "EUR", "9987.65", "1997.53", "11985.18"),
    record("05_cross_page", "FF-260905", "2026-09-05", "USD", "1800.00", "144.00", "1944.00", pages=2),
    record("06_missing_reference", None, "2026-09-06", "USD", "600.00", "48.00", "648.00", issues=("missing:invoice_number",)),
    record("07_missing_date", "FF-260907", None, "USD", "280.00", "22.40", "302.40", issues=("missing:invoice_date",)),
    record("08_missing_tax", "FF-260908", "2026-09-08", "USD", "800.00", None, "864.00", issues=("missing:tax",)),
    record("09_total_mismatch", "FF-260909", "2026-09-09", "USD", "300.00", "24.00", "340.00", issues=("amount_mismatch",)),
    record("10_missing_supplier", "FF-260910", "2026-09-10", "USD", "950.00", "76.00", "1026.00", supplier=None, issues=("missing:supplier",)),
]


def label_value(pdf, x, y, label, value):
    pdf.setFillColor(GRAY)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(x, y, label.upper())
    if value is not None:
        pdf.setFillColor(INK)
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(x, y - 19, value)


def money(value):
    return f"{Decimal(value):,.2f}"


def base_page(pdf, page_number, total_pages):
    pdf.setFillColor(INK)
    pdf.rect(0, HEIGHT - 16, WIDTH, 16, fill=1, stroke=0)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(44, HEIGHT - 46, "SYNTHETIC DEMO / NO PAYMENT REQUIRED")
    pdf.setStrokeColor(HexColor("#c6d4cd"))
    pdf.line(44, 64, WIDTH - 44, 64)
    pdf.setFillColor(GRAY)
    pdf.setFont("Helvetica", 8)
    pdf.drawString(44, 47, "Fictional supplier, buyer, goods and amounts. Personal portfolio fixture.")
    pdf.drawRightString(WIDTH - 44, 47, f"Page {page_number} of {total_pages}")


def draw_invoice(case):
    fields = case["fields"]
    pdf = canvas.Canvas(str(DEST / case["file"]), pagesize=A4)
    pdf.setTitle("Synthetic supplier invoice - independent held-out layout")
    pdf.setAuthor("Invoice Review Dashboard demo")
    base_page(pdf, 1, case["pages"])
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 30)
    pdf.drawString(44, HEIGHT - 102, "INVOICE")
    label_value(pdf, 44, HEIGHT - 143, "Supplier", fields["supplier"])
    label_value(pdf, 44, HEIGHT - 213, "Bill to", "Meadow Works Demo Studio")
    label_value(pdf, 340, HEIGHT - 143, "Invoice reference", fields["invoice_number"])
    issued = date.fromisoformat(fields["invoice_date"]).strftime("%d %B %Y") if fields["invoice_date"] else None
    label_value(pdf, 340, HEIGHT - 213, "Issued on", issued)
    label_value(pdf, 340, HEIGHT - 279, "Currency", fields["currency"])
    pdf.setFillColor(GRAY)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(44, HEIGHT - 292, "Order: DEMO-STUDIO-09")
    table_y = HEIGHT - 344
    pdf.setFillColor(PALE)
    pdf.rect(44, table_y - 10, WIDTH - 88, 29, fill=1, stroke=0)
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(55, table_y, "DESCRIPTION")
    pdf.drawRightString(394, table_y, "QTY")
    pdf.drawRightString(WIDTH - 55, table_y, "LINE AMOUNT")
    rows = 6 if case["pages"] == 2 else 1
    subtotal = Decimal(fields["subtotal"])
    amounts = [subtotal / rows] * rows
    for index, amount in enumerate(amounts):
        row_y = table_y - 38 - index * 32
        pdf.setFont("Helvetica", 10)
        pdf.drawString(55, row_y, f"Studio supplies bundle {index + 1}" if rows > 1 else "Studio supplies bundle")
        pdf.drawRightString(394, row_y, "1")
        pdf.drawRightString(WIDTH - 55, row_y, money(str(amount)))
    if case["pages"] == 2:
        pdf.setFillColor(GRAY)
        pdf.setFont("Helvetica-Oblique", 10)
        pdf.drawString(44, 218, "The invoice summary follows on page 2.")
        pdf.showPage()
        base_page(pdf, 2, 2)
        pdf.setFillColor(INK)
        pdf.setFont("Helvetica-Bold", 24)
        pdf.drawString(44, HEIGHT - 104, "Invoice summary")
        pdf.setFont("Helvetica", 10)
        pdf.drawString(44, HEIGHT - 132, "Continuation of the six supplies bundles shown on page 1.")
        totals_y = HEIGHT - 236
    else:
        totals_y = table_y - 112
    for index, (label, key) in enumerate((("Subtotal", "subtotal"), ("Tax", "tax"), ("Total payable", "total"))):
        current_y = totals_y - index * 39
        if key == "total":
            pdf.setFillColor(PALE)
            pdf.rect(286, current_y - 12, WIDTH - 330, 35, fill=1, stroke=0)
        pdf.setFillColor(INK)
        pdf.setFont("Helvetica-Bold" if key == "total" else "Helvetica", 11)
        pdf.drawString(299, current_y, label)
        if fields[key] is not None:
            pdf.drawRightString(WIDTH - 55, current_y, money(fields[key]))
    pdf.setFillColor(GRAY)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(44, 143, "This document is for software testing only.")
    pdf.drawString(44, 127, "No bank details or live payment instructions are included.")
    pdf.save()


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    for case in CASES:
        draw_invoice(case)
    labels = {
        "corpus": "Fern & Field independent held-out layout",
        "synthetic": True,
        "layout_families": 1,
        "document_count": len(CASES),
        "text_pdf_count": len(CASES),
        "scan_count": 0,
        "field_names": list(CASES[0]["fields"]),
        "label_contract": "Amounts are exact base-10 strings; dates are ISO 8601; null means absent from the source. expected_issues describes source defects, independent of parser wording.",
        "cases": CASES,
    }
    (DEST / "labels.json").write_text(json.dumps(labels, indent=2) + "\n", encoding="utf-8")
    print(f"Created {len(CASES)} synthetic text PDFs and labels in {DEST}")


if __name__ == "__main__":
    main()
