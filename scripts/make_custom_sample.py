"""Create a synthetic PDF using the example supplier label configuration."""
import json
from pathlib import Path

from generate_samples import make_pdf

ROOT = Path(__file__).resolve().parents[1]


def main():
    aliases = json.loads((ROOT / 'config' / 'labels.example.json').read_text(encoding='utf-8'))
    fields = dict(supplier='Example Custom Supplier (fictional)', invoice_number='CUSTOM-001',
                  invoice_date='2026-09-19', currency='USD', subtotal='100.00', tax='10.00', total='110.00')
    output = ROOT / 'data' / 'custom-supplier.pdf'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(make_pdf(fields, label_overrides={field: values[0] for field, values in aliases.items()}))
    print('Created data/custom-supplier.pdf (synthetic). Start the app with INVOICE_LABELS=config/labels.example.json.')


if __name__ == '__main__':
    main()
