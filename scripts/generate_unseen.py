"""Regenerate the independent, synthetic text-PDF validation set.

This authoring script was written without reading the application's parser,
its supported-label lists, its other fixtures, or their generators.
"""

import json
from pathlib import Path
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "fixtures" / "unseen"
WIDTH, HEIGHT = A4
INK = colors.HexColor("#18343B")
MUTED = colors.HexColor("#5E7378")
RULE = colors.HexColor("#CFDEDE")
PALE = colors.HexColor("#F0F5F4")

CASES = [
    {
        "file": "unseen_01.pdf",
        "case": "valid",
        "fields": {
            "supplier": "Cedar Workshop Services Ltd",
            "invoice_number": "CWS-7306",
            "invoice_date": "2026-08-14",
            "currency": "USD",
            "subtotal": "840.00",
            "tax": "84.00",
            "total": "924.00",
        },
        "items": [["Equipment inspection", "2", "300.00", "600.00"],
                  ["Calibration service", "1", "240.00", "240.00"]],
        "purpose": "Ordinary valid invoice; base for the changed-input case.",
    },
    {
        "file": "unseen_02.pdf",
        "case": "valid",
        "fields": {
            "supplier": "Marlow Print Cooperative",
            "invoice_number": "MPC-1942",
            "invoice_date": "2026-08-19",
            "currency": "EUR",
            "subtotal": "1560.00",
            "tax": "312.00",
            "total": "1872.00",
        },
        "items": [["Training booklets", "120", "8.00", "960.00"],
                  ["Presentation folders", "100", "6.00", "600.00"]],
        "purpose": "Valid invoice with a different supplier, currency, and amounts.",
    },
    {
        "file": "unseen_03.pdf",
        "case": "valid",
        "fields": {
            "supplier": "Harbor Technical Studio",
            "invoice_number": "HTS-2681",
            "invoice_date": "2026-09-02",
            "currency": "GBP",
            "subtotal": "2100.00",
            "tax": "420.00",
            "total": "2520.00",
        },
        "items": [["Site survey", "3", "400.00", "1200.00"],
                  ["Drawings and documentation", "2", "450.00", "900.00"]],
        "pages": 2,
        "purpose": "Valid two-page invoice: identity on page one, currency and totals on page two.",
    },
    {
        "file": "unseen_04.pdf",
        "case": "valid",
        "fields": {
            "supplier": "Cedar Workshop Services Ltd",
            "invoice_number": "CWS-7319",
            "invoice_date": "2026-09-11",
            "currency": "USD",
            "subtotal": "1110.00",
            "tax": "111.00",
            "total": "1221.00",
        },
        "items": [["Equipment inspection", "3", "290.00", "870.00"],
                  ["Calibration service", "1", "240.00", "240.00"]],
        "purpose": "Changed input compared with unseen_01: number, date, quantities, price, and all totals differ.",
    },
    {
        "file": "unseen_05.pdf",
        "case": "missing_field",
        "fields": {
            "supplier": "Pine River Office Supply",
            "invoice_number": "PRO-5107",
            "invoice_date": None,
            "currency": "CNY",
            "subtotal": "750.00",
            "tax": "45.00",
            "total": "795.00",
        },
        "items": [["Desktop organizers", "25", "20.00", "500.00"],
                  ["Document trays", "10", "25.00", "250.00"]],
        "purpose": "Invoice date is genuinely absent; all amounts reconcile.",
    },
    {
        "file": "unseen_06.pdf",
        "case": "amount_mismatch",
        "fields": {
            "supplier": "Willow Facility Care",
            "invoice_number": "WFC-8840",
            "invoice_date": "2026-09-05",
            "currency": "EUR",
            "subtotal": "960.00",
            "tax": "192.00",
            "total": "1010.00",
        },
        "items": [["Floor maintenance", "4", "180.00", "720.00"],
                  ["Window cleaning", "2", "120.00", "240.00"]],
        "purpose": "Printed total is intentionally inconsistent with subtotal plus tax; labels preserve printed values.",
    },
]


def text(c, x, y, content, size=10, bold=False, color=INK):
    c.setFillColor(color)
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    c.drawString(x, y, content)


def rule(c, y):
    c.setStrokeColor(RULE)
    c.setLineWidth(0.7)
    c.line(46, y, WIDTH - 46, y)


def page_frame(c, number, count):
    c.setFillColor(INK)
    c.rect(0, HEIGHT - 15, WIDTH, 15, fill=1, stroke=0)
    text(c, 46, HEIGHT - 63, "INVOICE", 27, True)
    text(c, 46, HEIGHT - 88, "SUPPLIER SERVICES / ACCOUNTS", 9, color=MUTED)
    rule(c, HEIGHT - 107)
    rule(c, 62)
    text(c, 46, 43, "Synthetic invoice for validation use", 8, color=MUTED)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8)
    c.drawRightString(WIDTH - 46, 43, f"Page {number} of {count}")


def identity(c, fields):
    text(c, 46, HEIGHT - 145, f"Supplier: {fields['supplier']}", 12, True)
    text(c, 46, HEIGHT - 171, "Bill to: Northfield Design Office", 10)
    text(c, 46, HEIGHT - 192, "18 Orchard Court", 9, color=MUTED)
    text(c, 46, HEIGHT - 235, f"Invoice Number: {fields['invoice_number']}", 10)
    if fields["invoice_date"] is not None:
        text(c, 322, HEIGHT - 235, f"Invoice Date: {fields['invoice_date']}", 10)


def line_items(c, items, y):
    c.setFillColor(PALE)
    c.rect(46, y - 10, WIDTH - 92, 28, fill=1, stroke=0)
    for x, title in [(58, "Description"), (337, "Qty"), (391, "Unit price"), (483, "Amount")]:
        text(c, x, y, title, 9, True)
    y -= 38
    for description, qty, price, amount in items:
        text(c, 58, y, description, 10)
        text(c, 339, y, qty, 10)
        for x, value in [(446, price), (535, amount)]:
            c.setFont("Helvetica", 10)
            c.drawRightString(x, y, value)
        rule(c, y - 14)
        y -= 39
    return y


def totals(c, fields, y):
    text(c, 325, y, f"Currency: {fields['currency']}", 11, True)
    y -= 38
    for label, key in [("Subtotal", "subtotal"), ("Tax", "tax"), ("Total", "total")]:
        is_total = key == "total"
        if is_total:
            c.setFillColor(PALE)
            c.rect(312, y - 12, WIDTH - 358, 35, fill=1, stroke=0)
        text(c, 325, y, f"{label}:", 12 if is_total else 11, is_total)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold" if is_total else "Helvetica", 12 if is_total else 11)
        c.drawRightString(WIDTH - 60, y, fields[key])
        y -= 35


def make_pdf(case):
    fields = case["fields"]
    count = case.get("pages", 1)
    c = canvas.Canvas(str(OUT / case["file"]), pagesize=A4, pageCompression=1)
    c.setTitle("Synthetic supplier invoice")
    c.setAuthor("Independent fixture author")
    page_frame(c, 1, count)
    identity(c, fields)
    line_items(c, case["items"], HEIGHT - 300)
    if count == 2:
        text(c, 46, 280, "Financial summary continues on the next page.", 10, color=MUTED)
        c.showPage()
        page_frame(c, 2, count)
        text(c, 46, HEIGHT - 148, "FINANCIAL SUMMARY", 14, True)
        text(c, 46, HEIGHT - 176, "Charges for the services listed on the preceding page.", 10, color=MUTED)
        totals(c, fields, HEIGHT - 250)
    else:
        totals(c, fields, 360)
    text(c, 46, 140, "Please quote the invoice number with your payment.", 9, color=MUTED)
    c.save()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    labels = []
    for case in CASES:
        fields = case["fields"]
        item_sum = sum(Decimal(row[3]) for row in case["items"])
        assert item_sum == Decimal(fields["subtotal"])
        reconciles = Decimal(fields["subtotal"]) + Decimal(fields["tax"]) == Decimal(fields["total"])
        assert reconciles == (case["case"] != "amount_mismatch")
        make_pdf(case)
        labels.append({
            "file": case["file"],
            "case": case["case"],
            "pages": case.get("pages", 1),
            "expected": fields,
            "purpose": case["purpose"],
        })
    (OUT / "labels.json").write_text(json.dumps(labels, indent=2) + "\n", encoding="utf-8")
    print(f"Created {len(labels)} independent invoice PDFs.")


if __name__ == "__main__":
    main()
