export function draftKey(record) {
  return `${record.id}:${record.created}`;
}

export function rememberDraft(drafts, record, fields, note) {
  const key = draftKey(record);
  const changed = Object.keys(record.fields).some(field =>
    (fields[field] ?? '') !== (record.fields[field] ?? ''));
  if (!changed && !note.length) {
    delete drafts[key];
    return;
  }
  drafts[key] = {
    fields: { ...fields }, note,
    expected_version: drafts[key]?.expected_version ?? record.revision,
  };
}

export function recordsWithDrafts(drafts, records) {
  return records.filter(record => drafts[draftKey(record)]);
}
