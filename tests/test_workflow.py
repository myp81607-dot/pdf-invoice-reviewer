import csv
import io

import pytest
from fastapi.testclient import TestClient

from app.extraction import extract_pdf, validate
from app.main import create_app
from scripts.generate_samples import make_pdf


@pytest.fixture
def fields():
    return dict(supplier='Acme Demo',invoice_number='INV-1',invoice_date='2026-09-19',currency='USD',subtotal='0.10',tax='0.20',total='0.30')


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(tmp_path/'review.sqlite3'))


def upload(client, fields, **kwargs):
    return client.post('/api/invoices',files={'file':('invoice.pdf',make_pdf(fields,**kwargs),'application/pdf')}).json()


def review(client, id, action='confirm', **fields):
    return client.post(f'/api/invoices/{id}/review',json={'fields':fields,'action':action,'note':'Verified against source PDF.'})


def test_input_changes_output_and_decimal(fields):
    a=extract_pdf(make_pdf(fields))
    b=extract_pdf(make_pdf(fields|{'total':'0.31'}))
    assert a['fields']['total']=='0.30' and not validate(a['fields'])
    assert b['fields']['total']=='0.31'
    assert validate(b['fields'])[0]['code']=='amount_mismatch'


def test_normal_requires_confirmation_then_csv(client,fields):
    r=upload(client,fields)
    assert r['fields']==fields and not r['exportable']
    assert client.get('/api/export.csv').status_code==409
    assert review(client,r['id']).json()['exportable']
    result=client.get('/api/export.csv')
    parsed=list(csv.DictReader(io.StringIO(result.text.lstrip('\ufeff'))))
    assert len(parsed)==1 and parsed[0]['total']=='0.30'


def test_mismatch_blocked_missing_null_and_edit_history(client,fields):
    r=upload(client,fields|{'tax':None,'total':'0.31'})
    assert r['fields']['tax'] is None
    assert review(client,r['id']).status_code==409
    assert review(client,r['id'],action='save',tax='0.20').status_code==200
    assert review(client,r['id']).status_code==409
    assert review(client,r['id'],total='0.30').json()['exportable']
    history=client.get(f'/api/invoices/{r["id"]}/history').json()
    assert history[-1]['changes']['total']=={'before':'0.31','after':'0.30'}
    assert history[-2]['changes']['tax']['before'] is None
    changed=review(client,r['id'],action='save',total='0.35').json()
    assert changed['status']=='pending' and not changed['exportable']


def test_business_duplicate_invalidates_confirmed_until_extra_rejected(client,fields):
    first=upload(client,fields)
    assert review(client,first['id']).status_code==200
    second=upload(client,fields,layout='ledger')
    assert any(i['code']=='duplicate_business' for i in second['issues'])
    assert client.get('/api/export.csv').status_code==409
    assert review(client,second['id']).status_code==409
    assert review(client,second['id'],action='reject').status_code==200
    assert client.get('/api/export.csv').status_code==200


def test_same_number_different_supplier_allowed(client,fields):
    upload(client,fields)
    r=upload(client,fields|{'supplier':'Different Vendor'})
    assert not r['issues'] and review(client,r['id']).status_code==200


def test_exact_duplicate_cannot_be_hidden_by_field_edit(client,fields):
    pdf=make_pdf(fields)
    first=client.post('/api/invoices',files={'file':('a.pdf',pdf)}).json()
    second=client.post('/api/invoices',files={'file':('renamed.pdf',pdf)}).json()
    assert any(i['code']=='duplicate_file' for i in second['issues'])
    assert review(client,second['id'],invoice_number='DIFFERENT').status_code==409
    assert review(client,first['id'],action='reject').status_code==200
    assert review(client,second['id']).status_code==200


def test_cross_page_and_ambiguous_source(client,fields):
    r=upload(client,fields,cross_page=True)
    assert r['evidence']['total'][0]['page']==2
    assert client.get(f'/api/invoices/{r["id"]}/pages/2.png').headers['content-type']=='image/png'
    conflicting=upload(client,fields|{'invoice_number':'INV-2'},extra_line='Total: 0.31')
    assert conflicting['fields']['total'] is None
    assert any(i['code']=='ambiguous' for i in conflicting['issues'])
    assert review(client,conflicting['id'],total='0.30').status_code==200


def test_unsupported_scan_bad_pdf_and_validation(client,fields):
    r=upload(client,fields,scan=True)
    assert any(i['code']=='document' for i in r['issues'])
    assert review(client,r['id'],**fields).status_code==409
    assert client.post('/api/invoices',files={'file':('bad.pdf',b'not a PDF')}).status_code==415
    broken=client.post('/api/invoices',files={'file':('bad.pdf',b'%PDF-broken')}).json()
    assert any(i['code']=='document' for i in broken['issues'])
    assert {i['code'] for i in validate(fields|{'invoice_date':'2026-02-30','currency':'ZZZ','total':'NaN'})}=={'date','currency','number'}


def test_persistence_and_required_note(tmp_path,fields):
    path=tmp_path/'persist.sqlite3'
    with TestClient(create_app(path)) as c:
        r=upload(c,fields)
        assert c.post(f'/api/invoices/{r["id"]}/review',json={'action':'confirm','note':' '}).status_code==422
        review(c,r['id'])
    with TestClient(create_app(path)) as c:
        assert c.get('/api/invoices').json()[0]['exportable']
        assert len(c.get(f'/api/invoices/{r["id"]}/history').json())==2


def test_csv_neutralizes_formula_supplier(client,fields):
    r=upload(client,fields|{'supplier':'=1+1'})
    assert review(client,r['id']).status_code==200
    assert "'=1+1" in client.get('/api/export.csv').text


def test_missing_value_does_not_consume_neighbor_label(client):
    from reportlab.pdfgen import canvas
    stream=io.BytesIO()
    pdf=canvas.Canvas(stream)
    pdf.drawString(44,750,'Supplier:')
    pdf.drawString(330,750,'Invoice number: GAP-001')
    for y,text in [(710,'Invoice date: 2026-09-19'),(680,'Currency: USD'),
                   (650,'Subtotal: 10.00'),(620,'Tax: 1.00'),(590,'Total: 11.00')]:
        pdf.drawString(44,y,text)
    pdf.save()
    r=client.post('/api/invoices',files={'file':('missing.pdf',stream.getvalue())}).json()
    assert r['fields']['supplier'] is None
    assert r['fields']['invoice_number']=='GAP-001'
    assert review(client,r['id']).status_code==409


def test_supplier_section_heading_is_not_a_field(fields):
    result=extract_pdf(make_pdf(fields,extra_line='SUPPLIER SERVICES / ACCOUNTS'))
    assert result['fields']['supplier']==fields['supplier']
    assert 'supplier' not in result['ambiguous']
