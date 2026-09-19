import test from 'node:test';
import assert from 'node:assert/strict';
import { draftKey, rememberDraft, recordsWithDrafts } from '../app/static/drafts.mjs';

const record = (id, revision = 1) => ({id, revision, created:'2026-09-19T08:00:00Z', fields:{supplier:'Supplier', total:'120.00'}});

test('separate invoice drafts retain field edits and notes through storage round trips', () => {
  const a = record(1), b = record(2), drafts = {};
  rememberDraft(drafts, a, {...a.fields, total:'125.00'}, 'Check page 2');
  rememberDraft(drafts, b, b.fields, 'A note without field changes');
  const restored = JSON.parse(JSON.stringify(drafts));
  assert.equal(restored[draftKey(a)].fields.total, '125.00');
  assert.equal(restored[draftKey(a)].note, 'Check page 2');
  assert.equal(restored[draftKey(b)].note, 'A note without field changes');
  assert.equal(recordsWithDrafts(restored, [a,b]).length, 2);
  assert.equal(a.fields.total, '120.00');
});

test('a newer saved version never silently upgrades the draft version', () => {
  const a = record(1), drafts = {};
  rememberDraft(drafts, a, {...a.fields, total:'125.00'}, 'Original draft');
  rememberDraft(drafts, record(1,2), {...a.fields, total:'130.00'}, 'Still reviewing');
  assert.equal(drafts[draftKey(a)].expected_version, 1);
});

test('reverting fields alone preserves an unsaved note; reverting both clears the draft', () => {
  const a = record(1), drafts = {};
  rememberDraft(drafts, a, {...a.fields, supplier:'Changed'}, 'Keep this note');
  rememberDraft(drafts, a, a.fields, 'Keep this note');
  assert.equal(recordsWithDrafts(drafts,[a]).length, 1);
  rememberDraft(drafts, a, a.fields, '');
  assert.equal(recordsWithDrafts(drafts,[a]).length, 0);
});

test('switching to another database record with a reused id does not restore the old draft', () => {
  const a = record(1), drafts = {};
  rememberDraft(drafts, a, a.fields, 'Old source document');
  assert.equal(recordsWithDrafts(drafts,[{...a,created:'2026-09-20T08:00:00Z'}]).length, 0);
});
