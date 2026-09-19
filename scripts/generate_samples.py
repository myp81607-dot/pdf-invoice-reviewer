"""Generate development/demo PDFs only. Held-out layout is authored separately."""
import io
import json
from decimal import Decimal
from pathlib import Path

from PIL import Image, ImageDraw
from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'fixtures' / 'development'


def make_pdf(fields, layout='classic', cross_page=False, scan=False, extra_line=None):
    stream = io.BytesIO()
    c = canvas.Canvas(stream, pagesize=(595, 842))
    c.setTitle('Synthetic supplier invoice - personal demonstration')
    c.setAuthor('Invoice Review Desk demo')

    def header(page):
        c.setFillColor(HexColor('#143d43'))
        c.rect(0, 728, 595, 114, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont('Helvetica-Bold', 25)
        c.drawString(46, 787, 'INVOICE' if layout == 'classic' else 'SUPPLIER STATEMENT')
        c.setFont('Helvetica', 10)
        c.drawString(46, 761, 'SYNTHETIC SAMPLE / NOT A REAL PAYMENT REQUEST')
        c.setFillColor(HexColor('#7b9195'))
        c.setFont('Helvetica', 9)
        c.drawString(46, 38, f'Personal demonstration only | Page {page}')

    if scan:
        img = Image.new('RGB', (595, 842), 'white')
        d = ImageDraw.Draw(img)
        d.text((40, 70), 'SYNTHETIC SCANNED INVOICE - IMAGE ONLY', fill='black')
        for i, (f, v) in enumerate(fields.items()):
            d.text((40, 130 + i * 45), f'{f}: {v}', fill='black')
        c.drawImage(ImageReader(img), 0, 0, width=595, height=842)
        c.save()
        return stream.getvalue()
    header(1)
    aliases = dict(zip(fields, ['Supplier','Invoice number','Invoice date','Currency','Subtotal','Tax','Total']))
    if layout == 'ledger':
        aliases.update(supplier='Vendor', invoice_number='Invoice no.', invoice_date='Date issued', subtotal='Net amount', tax='VAT amount', total='Amount due')
    y = 677
    for i, (f, v) in enumerate(fields.items()):
        if cross_page and i == 4:
            c.setFont('Helvetica-Oblique', 11)
            c.drawString(46, 180, 'Amount summary continues on page 2.')
            c.showPage()
            header(2)
            y = 677
        if v is None:
            continue
        c.setFillColor(HexColor('#203e46'))
        c.setFont('Helvetica-Bold' if f == 'total' else 'Helvetica', 13)
        if layout == 'ledger':
            c.setFillColor(HexColor('#f0f5f4'))
            c.rect(40, y - 12, 515, 33, fill=1, stroke=0)
            c.setFillColor(HexColor('#203e46'))
            c.drawString(52, y, aliases[f] + ':')
            c.drawString(248, y, str(v))
        else:
            c.drawString(46, y, f'{aliases[f]}: {v}')
        y -= 48
    if extra_line:
        c.drawString(46, y, extra_line)
    c.setFont('Helvetica', 10)
    c.setFillColor(HexColor('#69858d'))
    c.drawString(46, 118, 'Bill to: Example Operations Team (fictional)')
    c.drawString(46, 98, 'Description: office supplies / service package for a synthetic demo')
    c.save()
    return stream.getvalue()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    labels = []
    for i in range(1, 21):
        subtotal = Decimal('125.50') + Decimal(i) * Decimal('73.25')
        tax = (subtotal * Decimal('.10')).quantize(Decimal('.01'))
        fields = dict(supplier='Northstar Office Supply' if i % 2 else 'Harbor IT Services',
                      invoice_number=f'DEMO-{1000+i}', invoice_date=f'2026-09-{i:02}',
                      currency='USD' if i % 2 else 'EUR', subtotal=f'{subtotal:.2f}',
                      tax=f'{tax:.2f}', total=f'{subtotal+tax:.2f}')
        issues = []
        if i in (7, 16):
            fields['total'] = f'{subtotal+tax+Decimal("5.00"):.2f}'
            issues = ['amount_mismatch']
        if i in (8, 17):
            fields['tax' if i == 8 else 'invoice_date'] = None
            issues = ['missing']
        if i == 18:
            fields['invoice_date'] = '09/18/2026'
            issues = ['date']
        if i == 19:
            fields['currency'] = 'XYZ'
            issues = ['currency']
        scan = i == 20
        name = {1:'01-normal.pdf',7:'07-amount-mismatch.pdf',8:'08-missing-tax.pdf',9:'09-cross-page.pdf',20:'20-scan-unsupported.pdf'}.get(i,f'{i:02}-sample.pdf')
        (OUT / name).write_bytes(make_pdf(fields, 'classic' if i%2 else 'ledger', i in (9,10), scan))
        labels.append({'file':name,'fields':fields,'expected_issues':issues or (['document'] if scan else []), 'scan':scan})
    (OUT / 'labels.json').write_text(json.dumps(labels,indent=2),encoding='utf-8')
    print(f'Generated {len(labels)} development PDFs.')


if __name__ == '__main__':
    main()
