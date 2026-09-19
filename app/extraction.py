"""Small label-based extractor. Never infer missing financial fields."""
import io
import re
from datetime import date
from decimal import Decimal

import pdfplumber

FIELDS = ('supplier', 'invoice_number', 'invoice_date', 'currency', 'subtotal', 'tax', 'total')
AMOUNTS = ('subtotal', 'tax', 'total')
LABELS = {
    'supplier': r'Supplier|Vendor|Seller',
    'invoice_number': r'Invoice number|Invoice reference|Invoice ref\.?|Invoice no\.?|Invoice ID|Invoice #',
    'invoice_date': r'Invoice date|Date issued|Issued on',
    'currency': r'Currency',
    'subtotal': r'Subtotal|Net amount',
    'tax': r'Tax|VAT amount',
    'total': r'Total payable|Grand total|Amount due|Total',
}
# Explicit labels and unambiguous dates only; never guess a numeric date locale.
MONEY = re.compile(r'(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?\Z')
MONTHS = {name.lower(): i for i, name in enumerate(
    ('January','February','March','April','May','June','July','August','September','October','November','December'),1)}
MONTHS.update({name[:3]: number for name,number in list(MONTHS.items())})


def money(value):
    if not value or not MONEY.fullmatch(value):
        return None
    return Decimal(value.replace(',', ''))


def normalize(field, value):
    value = value.strip() if isinstance(value, str) else None
    if not value:
        return None
    if field in AMOUNTS and money(value) is not None:
        return format(money(value), '.2f')
    if field == 'currency':
        return value.upper()
    if field == 'invoice_date':
        match = re.fullmatch(r'(\d{1,2}) ([A-Za-z]+) (\d{4})', value)
        if match and match[2].lower() in MONTHS:
            try:
                return date(int(match[3]), MONTHS[match[2].lower()], int(match[1])).isoformat()
            except ValueError:
                pass
    return value


def page_evidence(page):
    """Read inline fields and label-above-value blocks without merging columns.

    Words at nearly the same height form a row. Wide gaps separate cells.
    A label can use the next cell or the closest aligned row below (<=36pt).
    The gap limits are intentionally modest: unsupported arrangements stay empty.
    """
    rows = []
    for word in sorted(page.extract_words(x_tolerance=2, y_tolerance=3), key=lambda w:(w['top'], w['x0'])):
        if not rows or abs(word['top']-rows[-1][0]['top']) > 3:
            rows.append([word])
        else:
            rows[-1].append(word)
    segments = []
    for words in rows:
        parts = []
        for word in sorted(words, key=lambda w:w['x0']):
            if not parts or word['x0']-parts[-1][-1]['x1'] > 24:
                parts.append([word])
            else:
                parts[-1].append(word)
        segments.append([{'text':' '.join(w['text'] for w in part), 'x0':part[0]['x0'],
                          'x1':part[-1]['x1'], 'top':part[0]['top']} for part in parts])
    field_prefix = re.compile(r'^(?:'+'|'.join(LABELS.values())+r')(?:\s*:|\s+|$)', re.I)
    for ri, row in enumerate(segments):
        for si, cell in enumerate(row):
            for field, labels in LABELS.items():
                if not re.fullmatch(r'(?:'+labels+r')\s*:?', cell['text'], re.I):
                    # Supplier headings such as "SUPPLIER SERVICES / ACCOUNTS"
                    # are not values. Inline supplier fields need an explicit colon.
                    separator = r'\s*:\s*' if field == 'supplier' else r'(?:\s*:\s*|\s+)'
                    inline = re.fullmatch(r'(?:'+labels+r')'+separator+r'(.+)', cell['text'], re.I)
                    if inline and not field_prefix.match(inline[1]):
                        yield field, inline[1], cell['text']
                    continue
                right = row[si+1] if si+1 < len(row) else None
                if right and not field_prefix.match(right['text']):
                    yield field, right['text'], cell['text']+' | '+right['text']
                    continue
                boundary = right['x0']-5 if right else page.width
                for below in segments[ri+1:]:
                    if below[0]['top']-cell['top'] > 36:
                        break
                    candidates = [v for v in below if abs(v['x0']-cell['x0']) <= 12 and v['x1'] < boundary]
                    if candidates:
                        value = candidates[0]['text']
                        if not field_prefix.match(value):
                            yield field, value, cell['text']+' | '+value
                        break


def extract_pdf(content):
    result = {'fields': dict.fromkeys(FIELDS), 'evidence': {f: [] for f in FIELDS},
              'pages': [], 'document_issues': [], 'ambiguous': []}
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            if len(pdf.pages) > 12:
                result['document_issues'] = ['PDF exceeds the 12-page local demo limit.']
                return result
            for i, page in enumerate(pdf.pages, 1):
                text = page.extract_text(x_tolerance=2, y_tolerance=3) or ''
                result['pages'].append({'number': i, 'text': text})
                for field, value, source in page_evidence(page):
                    if value.strip():
                        result['evidence'][field].append({'page': i, 'text': source, 'value': normalize(field,value)})
            if not result['pages'] or any(not p['text'].strip() for p in result['pages']):
                result['document_issues'].append('Page without extractable text: scanned or mixed image PDFs are unsupported. Use a text PDF.')
            for field in FIELDS:
                values = {e['value'] for e in result['evidence'][field]}
                if len(values) == 1:
                    result['fields'][field] = values.pop()
                elif len(values) > 1:
                    result['ambiguous'].append(field)
    except Exception:
        result['document_issues'] = ['Unreadable or encrypted PDF. Supply an unencrypted text PDF.']
    return result


def validate(fields):
    issues = []
    for field in FIELDS:
        if not fields.get(field):
            issues.append({'code': 'missing', 'field': field, 'message': f'Missing {field.replace("_", " ")}.'})
    value = fields.get('invoice_date')
    if value:
        try:
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                raise ValueError()
            date.fromisoformat(value)
        except ValueError:
            issues.append({'code': 'date', 'field': 'invoice_date', 'message': 'Date must be a real date in YYYY-MM-DD format.'})
    if fields.get('currency') and fields['currency'] not in ('USD', 'EUR', 'GBP', 'CNY'):
        issues.append({'code': 'currency', 'field': 'currency', 'message': 'Supported currencies: USD, EUR, GBP, CNY. No currency guessing or conversion.'})
    parsed = {}
    for field in AMOUNTS:
        if fields.get(field):
            parsed[field] = money(fields[field])
            if parsed[field] is None:
                issues.append({'code': 'number', 'field': field, 'message': f'{field.title()} must be nonnegative with at most two decimal places (1,234.56). Credit notes are unsupported.'})
    if len(parsed) == 3 and all(v is not None for v in parsed.values()):
        expected = parsed['subtotal'] + parsed['tax']
        if expected != parsed['total']:
            issues.append({'code': 'amount_mismatch', 'field': 'total',
                'message': f'Subtotal + tax = {expected:.2f}, but total is {parsed["total"]:.2f}. Difference: {parsed["total"] - expected:+.2f}.'})
    return issues
