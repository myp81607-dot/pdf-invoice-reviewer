"""Local single-reviewer application. SQLite retains source PDFs and review history."""
import csv
import hashlib
import io
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .extraction import FIELDS, extract_pdf, normalize, validate

ROOT = Path(__file__).resolve().parent.parent


class Review(BaseModel):
    fields: dict[str, str | None] = Field(default_factory=dict)
    action: str = 'save'
    note: str = Field(min_length=1, max_length=1000)


def create_app(database=None):
    db_path = Path(database or os.environ.get('INVOICE_DB', ROOT / 'data' / 'invoices.sqlite3'))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    app = FastAPI(title='Invoice Review Desk')

    @contextmanager
    def db():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    with db() as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS invoices (
              id INTEGER PRIMARY KEY, filename TEXT NOT NULL, digest TEXT NOT NULL,
              pdf BLOB NOT NULL, extracted TEXT NOT NULL, fields TEXT NOT NULL,
              resolved TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL DEFAULT 'pending', created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events (
              id INTEGER PRIMARY KEY, invoice_id INTEGER NOT NULL, at TEXT NOT NULL,
              action TEXT NOT NULL, note TEXT NOT NULL, changes TEXT NOT NULL);
        ''')

    def now():
        return datetime.now(timezone.utc).isoformat(timespec='seconds')

    def records(conn):
        return [dict(r) for r in conn.execute('SELECT id, filename, digest, extracted, fields, resolved, status, created FROM invoices ORDER BY id')]

    def key(fields):
        return tuple(' '.join((fields.get(f) or '').casefold().split()) for f in ('supplier', 'invoice_number'))

    def present(row, rows):
        fields = json.loads(row['fields'])
        original = json.loads(row['extracted'])
        resolved = json.loads(row['resolved'])
        issues = validate(fields)
        issues += [{'code': 'document', 'field': None, 'message': m} for m in original['document_issues']]
        issues += [{'code': 'ambiguous', 'field': f, 'message': f'Conflicting source values for {f}. Enter the verified value with a review note.'}
                   for f in original['ambiguous'] if f not in resolved]
        if row['status'] != 'rejected':
            for other in rows:
                if other['id'] == row['id'] or other['status'] == 'rejected':
                    continue
                if other['digest'] == row['digest']:
                    issues.append({'code': 'duplicate_file', 'field': None,
                        'message': f'Exact file duplicate of record #{other["id"]}. Reject the extra copy before export.'})
                elif all(key(fields)) and key(fields) == key(json.loads(other['fields'])):
                    issues.append({'code': 'duplicate_business', 'field': 'invoice_number',
                        'message': f'Same supplier and invoice number as record #{other["id"]}. Check both documents and reject the extra copy.'})
        return {'id': row['id'], 'filename': row['filename'], 'created': row['created'], 'status': row['status'],
                'fields': fields, 'original_fields': original['fields'], 'evidence': original['evidence'],
                'pages': original['pages'], 'issues': issues, 'exportable': row['status'] == 'confirmed' and not issues}

    def get_row(conn, invoice_id):
        row = conn.execute('SELECT * FROM invoices WHERE id=?', (invoice_id,)).fetchone()
        if row is None:
            raise HTTPException(404, 'Invoice not found.')
        return dict(row)

    @app.get('/api/invoices')
    def list_invoices():
        with db() as conn:
            rows = records(conn)
            return [present(r, rows) for r in rows]

    @app.post('/api/invoices', status_code=201)
    def upload(file: UploadFile = File(...)):
        content = file.file.read(10 * 1024 * 1024 + 1)
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(413, 'Maximum file size is 10 MB.')
        if not content.startswith(b'%PDF-'):
            raise HTTPException(415, 'Only PDF files are accepted.')
        parsed = extract_pdf(content)
        filename = (file.filename or 'invoice.pdf').replace('\\', '/').split('/')[-1]
        with db() as conn:
            cursor = conn.execute('INSERT INTO invoices(filename,digest,pdf,extracted,fields,created) VALUES(?,?,?,?,?,?)',
                (filename, hashlib.sha256(content).hexdigest(), content, json.dumps(parsed), json.dumps(parsed['fields']), now()))
            invoice_id = cursor.lastrowid
            conn.execute('INSERT INTO events(invoice_id,at,action,note,changes) VALUES(?,?,?,?,?)',
                (invoice_id, now(), 'upload', 'Text extracted from uploaded PDF.', '{}'))
            return present(get_row(conn, invoice_id), records(conn))

    @app.get('/api/invoices/{invoice_id}/history')
    def history(invoice_id: int):
        with db() as conn:
            get_row(conn, invoice_id)
            return [dict(r) | {'changes': json.loads(r['changes'])} for r in conn.execute(
                'SELECT at,action,note,changes FROM events WHERE invoice_id=? ORDER BY id', (invoice_id,))]

    @app.post('/api/invoices/{invoice_id}/review')
    def review(invoice_id: int, request: Review):
        if request.action not in ('save', 'confirm', 'reject') or not request.note.strip():
            raise HTTPException(422, 'Choose save, confirm or reject and provide a review note.')
        if set(request.fields) - set(FIELDS):
            raise HTTPException(422, 'Unknown invoice field.')
        if any(v is not None and len(v) > 300 for v in request.fields.values()):
            raise HTTPException(422, 'Field values must be at most 300 characters.')
        with db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = get_row(conn, invoice_id)
            old = json.loads(row['fields'])
            new = old | {f: normalize(f, v) for f, v in request.fields.items()}
            changes = {f: {'before': old[f], 'after': new[f]} for f in FIELDS if old[f] != new[f]}
            resolved = list(set(json.loads(row['resolved'])) | set(request.fields))
            # Every save returns to pending; confirmation applies to the current values only.
            status = {'save': 'pending', 'confirm': 'confirmed', 'reject': 'rejected'}[request.action]
            candidate = row | {'fields': json.dumps(new), 'resolved': json.dumps(resolved), 'status': status}
            check = present(candidate, records(conn))
            if request.action == 'confirm' and check['issues']:
                raise HTTPException(409, {'message': 'Confirmation blocked. Resolve these issues first.', 'issues': check['issues']})
            conn.execute('UPDATE invoices SET fields=?, resolved=?, status=? WHERE id=?',
                (candidate['fields'], candidate['resolved'], status, invoice_id))
            conn.execute('INSERT INTO events(invoice_id,at,action,note,changes) VALUES(?,?,?,?,?)',
                (invoice_id, now(), request.action, request.note.strip(), json.dumps(changes)))
            return present(get_row(conn, invoice_id), records(conn))

    @app.get('/api/invoices/{invoice_id}/pdf')
    def source(invoice_id: int):
        with db() as conn:
            row = get_row(conn, invoice_id)
            return Response(row['pdf'], media_type='application/pdf', headers={'Content-Disposition': 'inline; filename="source.pdf"'})

    @app.get('/api/invoices/{invoice_id}/pages/{page_number}.png')
    def page_image(invoice_id: int, page_number: int):
        import pdfplumber
        with db() as conn:
            row = get_row(conn, invoice_id)
        try:
            with pdfplumber.open(io.BytesIO(row['pdf'])) as pdf:
                if page_number < 1 or page_number > min(len(pdf.pages), 12):
                    raise HTTPException(404, 'Page not found.')
                png = io.BytesIO()
                pdf.pages[page_number - 1].to_image(resolution=105).original.save(png, format='PNG')
                return Response(png.getvalue(), media_type='image/png')
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(422, 'Cannot render this PDF.')

    @app.get('/api/export.csv')
    def export():
        with db() as conn:
            rows = records(conn)
            eligible = [p for r in rows if (p := present(r, rows))['exportable']]
        if not eligible:
            raise HTTPException(409, 'No eligible confirmed invoices. Review the queue first.')
        out = io.StringIO(newline='')
        writer = csv.DictWriter(out, fieldnames=('record_id', *FIELDS))
        writer.writeheader()
        for p in eligible:
            # Quoting alone does not prevent spreadsheet formulas from executing.
            safe = {k: "'" + v if v.lstrip().startswith(('=', '+', '-', '@')) else v for k, v in p['fields'].items()}
            writer.writerow({'record_id': p['id'], **safe})
        return Response('\ufeff' + out.getvalue(), media_type='text/csv',
                        headers={'Content-Disposition': 'attachment; filename="reviewed-invoices.csv"'})

    app.mount('/static', StaticFiles(directory=ROOT / 'app' / 'static'), name='static')

    @app.get('/')
    def index():
        return FileResponse(ROOT / 'app' / 'static' / 'index.html')

    return app
