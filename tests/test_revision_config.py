import csv
import hashlib
import io
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.extraction import configured_labels, extract_pdf
from app.main import create_app
from scripts.generate_samples import make_pdf

FIELDS = dict(supplier='Example Supplier', invoice_number='REV-001', invoice_date='2026-09-19',
              currency='USD', subtotal='100.00', tax='10.00', total='110.00')


def test_stale_review_preserves_saved_values_history_and_export(tmp_path, monkeypatch):
    monkeypatch.delenv('INVOICE_LABELS', raising=False)
    client = TestClient(create_app(tmp_path / 'review.sqlite3'))
    invoice = client.post('/api/invoices', files={'file': ('invoice.pdf', make_pdf(FIELDS))}).json()
    assert invoice['revision'] == 1
    url = f'/api/invoices/{invoice["id"]}/review'
    saved = client.post(url, json={'expected_version': 1, 'action': 'confirm', 'note': 'Checked source.'}).json()
    assert saved['revision'] == 2 and saved['exportable']
    history_url = f'/api/invoices/{invoice["id"]}/history'
    history = client.get(history_url).json()
    stale = client.post(url, json={'expected_version': 1, 'action': 'save', 'note': 'Older tab draft.',
                                   'fields': {'total': '999.00'}})
    assert stale.status_code == 409
    assert stale.json()['detail']['code'] == 'version_conflict'
    assert stale.json()['detail']['current'] == saved
    assert client.get('/api/invoices').json() == [saved]
    assert client.get(history_url).json() == history
    exported = list(csv.DictReader(io.StringIO(client.get('/api/export.csv').text.lstrip('\ufeff'))))
    assert exported[0]['total'] == '110.00'
    pending = client.post(url, json={'expected_version': 2, 'action': 'save', 'note': 'Reopen review.'}).json()
    rejected = client.post(url, json={'expected_version': 3, 'action': 'reject', 'note': 'Do not process.'}).json()
    assert pending['revision'] == 3 and rejected['revision'] == 4
    assert client.post(url, json={'action': 'save', 'note': 'Missing version.'}).status_code == 422
    assert client.post(url, json={'expected_version': 0, 'action': 'save', 'note': 'Invalid version.'}).status_code == 422


def test_old_database_gets_revision_without_losing_invoice(tmp_path, monkeypatch):
    monkeypatch.delenv('INVOICE_LABELS', raising=False)
    path = tmp_path / 'old.sqlite3'
    pdf = make_pdf(FIELDS)
    with sqlite3.connect(path) as conn:
        conn.execute('''CREATE TABLE invoices (
            id INTEGER PRIMARY KEY, filename TEXT NOT NULL, digest TEXT NOT NULL,
            pdf BLOB NOT NULL, extracted TEXT NOT NULL, fields TEXT NOT NULL,
            resolved TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL DEFAULT 'pending', created TEXT NOT NULL)''')
        conn.execute('INSERT INTO invoices(filename,digest,pdf,extracted,fields,created) VALUES(?,?,?,?,?,?)',
                     ('old.pdf', hashlib.sha256(pdf).hexdigest(), pdf, json.dumps(extract_pdf(pdf)),
                      json.dumps(FIELDS), '2026-09-19T00:00:00+00:00'))
    client = TestClient(create_app(path))
    invoice = client.get('/api/invoices').json()[0]
    assert invoice['revision'] == 1 and invoice['fields'] == FIELDS
    response = client.post(f'/api/invoices/{invoice["id"]}/review',
                           json={'expected_version': 1, 'action': 'confirm', 'note': 'Existing invoice checked.'})
    assert response.status_code == 200 and response.json()['revision'] == 2
    assert TestClient(create_app(path)).get('/api/invoices').json()[0]['exportable']


def test_label_file_changes_extraction_and_keeps_default_labels(tmp_path, monkeypatch):
    aliases = {'supplier': ['Supplier name'], 'invoice_number': ['Document reference']}
    pdf = make_pdf(FIELDS, label_overrides={field: names[0] for field, names in aliases.items()})
    without = extract_pdf(pdf)
    assert without['fields']['supplier'] is None and without['fields']['invoice_number'] is None
    config = tmp_path / 'labels.json'
    config.write_text(json.dumps(aliases), encoding='utf-8')
    monkeypatch.setenv('INVOICE_LABELS', str(config))
    client = TestClient(create_app(tmp_path / 'configured.sqlite3'))
    invoice = client.post('/api/invoices', files={'file': ('custom.pdf', pdf)}).json()
    assert invoice['fields'] == FIELDS and not invoice['issues']
    assert invoice['evidence']['supplier'][0]['text'].startswith('Supplier name:')
    normal = client.post('/api/invoices', files={'file': ('normal.pdf', make_pdf(FIELDS | {'invoice_number': 'REV-002'}))}).json()
    assert normal['fields']['supplier'] == FIELDS['supplier'] and not normal['issues']


def test_aliases_are_literal_text():
    labels = configured_labels({'supplier': ['Seller (legal)']})
    literal = extract_pdf(make_pdf(FIELDS, label_overrides={'supplier': 'Seller (legal)'}), labels)
    regex_like = extract_pdf(make_pdf(FIELDS, label_overrides={'supplier': 'Seller legal'}), labels)
    assert literal['fields']['supplier'] == FIELDS['supplier']
    assert regex_like['fields']['supplier'] is None


@pytest.mark.parametrize('config', ['{broken', '{"unknown": ["Label"]}', '{"supplier": "Name"}',
                                  '{"supplier": [""]}', '{"supplier": [1]}', '{"supplier": []}'])
def test_invalid_label_configuration_fails_at_startup(tmp_path, monkeypatch, config):
    path = tmp_path / 'labels.json'
    path.write_text(config, encoding='utf-8')
    monkeypatch.setenv('INVOICE_LABELS', str(path))
    with pytest.raises(ValueError, match='INVOICE_LABELS'):
        create_app(tmp_path / 'invalid.sqlite3')
