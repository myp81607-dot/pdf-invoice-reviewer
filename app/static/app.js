import { draftKey, rememberDraft, recordsWithDrafts } from './drafts.mjs';

const names = {supplier:'Supplier', invoice_number:'Invoice number', invoice_date:'Invoice date',
  currency:'Currency', subtotal:'Subtotal', tax:'Tax', total:'Total'};
const storageKey = 'invoice-review-drafts';
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c =>
  ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
let rows = [], selected = null, page = 1, busy = false, drafts = {}, storageAvailable = true;
try { drafts = JSON.parse(sessionStorage.getItem(storageKey) || '{}'); }
catch { storageAvailable = false; }

function message(text) { $('message').textContent = text; $('message').hidden = !text; }
function persistDrafts() {
  try { sessionStorage.setItem(storageKey, JSON.stringify(drafts)); }
  catch { storageAvailable = false; }
}
function draftCount() { return recordsWithDrafts(drafts, rows).length; }
function updateExport() {
  const count = draftCount();
  $('export').disabled = busy || count > 0 || !rows.some(r => r.exportable);
  $('export-note').textContent = count
    ? `${count} draft${count === 1 ? '' : 's'} in this tab. Save or discard before exporting.`
    : 'Only saved, confirmed records are included.';
}
window.addEventListener('beforeunload', event => {
  if (draftCount()) { event.preventDefault(); event.returnValue = ''; }
});
async function request(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const body = await response.json();
    const error = Error(typeof body.detail === 'string' ? body.detail
      : body.detail?.message || 'Request failed. Check the form values.');
    error.detail = body.detail;
    throw error;
  }
  return response;
}
function status(record) {
  if (record.status === 'rejected') return ['Rejected', 'rejected'];
  if (record.issues.length) return ['Needs attention', ''];
  return record.exportable ? ['Confirmed', 'good'] : ['Awaiting review', 'pending'];
}
async function refresh() { rows = await (await request('/api/invoices')).json(); render(); }

function validation(record) {
  const draft = drafts[draftKey(record)];
  if (draft) {
    if (draft.expected_version !== record.revision) return `<div class="issues"><strong>This invoice changed in another tab.</strong>
      <p>Your draft uses version ${draft.expected_version}; the saved record is version ${record.revision}.
      Your draft is kept. Compare the saved values, then discard the draft and re-enter any changes you still need.</p>
      <details><summary>Latest saved values (${esc(record.status)})</summary><dl class="saved-values">
      ${Object.entries(names).map(([f,n]) => `<dt>${n}</dt><dd>${esc(record.fields[f] ?? '(empty)')}</dd>`).join('')}</dl></details></div>`;
    return `<div class="draft-notice"><strong>Draft in this tab</strong><span>${storageAvailable
      ? 'Fields and note are kept when you switch records or reload this tab.'
      : 'Browser storage is unavailable. Keep this tab open until you save.'}
      These edits have not been saved, checked or included in a CSV.</span></div>`;
  }
  if (record.issues.length) return `<div class="issues"><strong>Cannot confirm this invoice</strong><ul>
    ${record.issues.map(i => `<li>${esc(i.message)}</li>`).join('')}</ul></div>`;
  return `<div class="checks-ok">Saved values pass the checks.${record.exportable
    ? ' Confirmed for export.' : ' Review the source before confirming.'}</div>`;
}

function render() {
  $('count').textContent = rows.length;
  $('blocked').textContent = rows.filter(r => r.status !== 'rejected' && r.issues.length).length;
  $('pending').textContent = rows.filter(r => r.status === 'pending' && !r.issues.length).length;
  $('ready').textContent = rows.filter(r => r.exportable).length;
  updateExport();
  const filter = $('filter').value;
  const visible = rows.filter(r => filter === 'all' || (filter === 'drafts' ? !!drafts[draftKey(r)]
    : filter === 'attention' ? r.status !== 'rejected' && r.issues.length : r.status === filter));
  if (!visible.some(r => r.id === selected)) selected = visible[0]?.id ?? null;
  $('queue').innerHTML = visible.map(r => {
    const [label, cls] = status(r);
    return `<button class="queue-item ${r.id === selected ? 'selected' : ''}" data-id="${r.id}">
      <strong>${esc(r.fields.supplier || 'Supplier not found')}</strong><small>${esc(r.fields.invoice_number || r.filename)} · #${r.id}</small>
      <span class="badge ${cls}">${label}</span><span class="draft-tag" ${drafts[draftKey(r)] ? '' : 'hidden'}>Draft</span>
      <span class="queue-amount">${esc(r.fields.currency || '')} ${esc(r.fields.total || '—')}</span></button>`;
  }).join('') || '<p class="hint queue-empty">No records in this view.</p>';
  document.querySelectorAll('[data-id]').forEach(button => button.onclick = () => {
    if (busy) return;
    selected = Number(button.dataset.id); page = 1; message(''); render();
  });
  const r = rows.find(r => r.id === selected);
  if (!r) {
    $('detail').innerHTML = '<div class="empty"><h2>Select an invoice</h2><p>Upload a text PDF, or choose a different queue filter.</p></div>';
    setBusy(busy); return;
  }
  const draft = drafts[draftKey(r)], fields = draft?.fields ?? r.fields;
  const [label, cls] = status(r);
  page = Math.min(page, Math.max(1, r.pages.length));
  $('detail').innerHTML = `<div class="detail-title"><div><h2>${esc(r.fields.invoice_number || 'Untitled invoice')}</h2>
    <p>${esc(r.filename)} · ${r.pages.length} page${r.pages.length === 1 ? '' : 's'} · saved version ${r.revision}</p></div>
    <span class="badge ${cls}">${label}</span></div><div id="validation">${validation(r)}</div>
    <div class="review-columns"><div><div class="column-heading">Invoice fields</div>
    ${Object.entries(names).map(([f,n]) => `<label class="field"><span class="field-label">${n}
      <span class="edited" id="edited-${f}" ${fields[f] !== r.original_fields[f] ? '' : 'hidden'}>${fields[f] !== r.fields[f] ? 'Draft' : 'Edited'}</span></span>
      <input id="field-${f}" value="${esc(fields[f])}" class="${fields[f] ? '' : 'missing'}" placeholder="Not found" maxlength="300">
      <div class="evidence">${r.evidence[f].length ? r.evidence[f].map(e =>
        `<button type="button" data-page="${e.page}" title="${esc(e.text)}">p.${e.page}</button> ${esc(e.text)}`).join('<br>')
        : 'No extraction evidence. Enter only a verified value.'}</div></label>`).join('')}</div>
    <div><div class="column-heading">Source PDF</div><div class="source-toolbar"><select id="page" aria-label="Source page">
      ${r.pages.map(p => `<option value="${p.number}" ${p.number === page ? 'selected' : ''}>Page ${p.number} of ${r.pages.length}</option>`).join('')}</select>
      <a href="/api/invoices/${r.id}/pdf" target="_blank" rel="noopener">Open PDF</a></div><div id="page-content"></div></div></div>
    <div class="review-actions"><label for="note">Review note (required to save, confirm or reject)</label>
      <textarea id="note" maxlength="1000" placeholder="What did you verify or change?">${esc(draft?.note ?? '')}</textarea>
      <div class="actions-row"><button data-action="save">Save changes</button><button class="primary" data-action="confirm">Confirm</button>
      <button id="discard-draft" ${draft ? '' : 'hidden'}>Discard draft</button><button class="danger" data-action="reject">Reject</button></div>
      <p class="hint">Saving changes returns the invoice to pending. Confirmation applies to the saved values.</p></div>
    <details class="history"><summary>Review history</summary><div id="history"></div></details>`;
  renderPage(r);
  $('page').onchange = () => { page = Number($('page').value); renderPage(r); };
  document.querySelectorAll('[data-page]').forEach(button => button.onclick = () => {
    page = Number(button.dataset.page); $('page').value = page; renderPage(r);
  });
  document.querySelectorAll('[data-action]').forEach(button => button.onclick = () => review(button.dataset.action));
  document.querySelectorAll('.field input, #note').forEach(input => input.oninput = captureDraft);
  $('discard-draft').onclick = () => {
    if (!window.confirm('Discard this draft and its review note? The saved invoice will stay unchanged.')) return;
    delete drafts[draftKey(r)]; persistDrafts(); render(); message('Draft discarded. Showing the saved invoice.');
  };
  setBusy(busy); loadHistory(r.id);
}

function captureDraft() {
  const r = rows.find(r => r.id === selected);
  if (!r) return;
  const fields = Object.fromEntries(Object.keys(names).map(f => [f, $(`field-${f}`).value]));
  rememberDraft(drafts, r, fields, $('note').value); persistDrafts();
  $('validation').innerHTML = validation(r);
  $('discard-draft').hidden = !drafts[draftKey(r)];
  const tag = document.querySelector(`[data-id="${r.id}"] .draft-tag`);
  if (tag) tag.hidden = !drafts[draftKey(r)];
  for (const f of Object.keys(names)) {
    $(`edited-${f}`).hidden = (fields[f] || null) === r.original_fields[f];
    $(`edited-${f}`).textContent = (fields[f] || null) !== r.fields[f] ? 'Draft' : 'Edited';
  }
  updateExport();
}
function setBusy(value) {
  busy = value;
  document.querySelectorAll('.queue-item, .field input, #note, #filter, #files, #discard-draft').forEach(el => el.disabled = value);
  const r = rows.find(r => r.id === selected), draft = r && drafts[draftKey(r)];
  const conflict = draft && draft.expected_version !== r.revision;
  document.querySelectorAll('[data-action]').forEach(button => button.disabled = value || !!conflict);
  updateExport();
}
function renderPage(r) {
  const p = r.pages.find(p => p.number === page);
  $('page-content').innerHTML = p ? `<img class="source-image" alt="Original PDF page ${page}" src="/api/invoices/${r.id}/pages/${page}.png">
    <details class="source-text"><summary>Extracted page text</summary><pre>${esc(p.text || 'No extractable text.')}</pre></details>`
    : '<p class="hint">No readable source pages. Open the PDF to inspect it.</p>';
}
async function loadHistory(id) {
  try {
    const events = await (await request(`/api/invoices/${id}/history`)).json();
    if (id !== selected) return;
    $('history').innerHTML = events.map(e => `<div class="event"><b>${esc(e.action)}</b> · ${esc(e.at)}<br>${esc(e.note)}
      ${Object.keys(e.changes).length ? `<pre>${esc(Object.entries(e.changes).map(([f,v]) =>
        `${names[f]}: ${v.before ?? '(empty)'} → ${v.after ?? '(empty)'}`).join('\n'))}</pre>` : ''}</div>`).join('');
  } catch (e) { message(e.message); }
}
async function review(action) {
  if (busy) return;
  captureDraft();
  const r = rows.find(r => r.id === selected), draft = drafts[draftKey(r)];
  if (!draft?.note.trim()) { message('Add a review note first.'); $('note').focus(); return; }
  const fields = Object.fromEntries(Object.entries(draft.fields).map(([f,v]) => [f, v.trim() || null]));
  setBusy(true);
  try {
    const saved = await (await request(`/api/invoices/${r.id}/review`, {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({fields, action, note:draft.note.trim(), expected_version:draft.expected_version})})).json();
    rows = rows.map(row => row.id === saved.id ? saved : row);
    delete drafts[draftKey(r)]; persistDrafts(); render();
    const outcome = action === 'confirm' ? 'Saved and confirmed. Eligible for CSV while all checks pass.'
      : action === 'reject' ? 'Invoice rejected. It is excluded from CSV.' : 'Changes saved. Confirm the updated invoice before export.';
    try { await refresh(); message(outcome); }
    catch { message(outcome + ' The queue could not be refreshed. Reload to check other records.'); }
  } catch (e) {
    if (e.detail?.code === 'version_conflict') { rows = rows.map(row => row.id === r.id ? e.detail.current : row); render(); }
    else if (e.detail?.issues) $('validation').innerHTML = `<div class="issues"><strong>Not saved. Fix these draft values before confirming.</strong>
      <ul>${e.detail.issues.map(i => `<li>${esc(i.message)}</li>`).join('')}</ul></div>`;
    message(e.message + ' Your draft is kept.');
  } finally { setBusy(false); }
}
$('files').onchange = async () => {
  if (busy) return;
  setBusy(true);
  try {
    for (const file of $('files').files) {
      message(`Reading ${file.name}…`);
      const data = new FormData(); data.append('file', file);
      const r = await (await request('/api/invoices', {method:'POST', body:data})).json();
      selected = r.id; page = 1;
    }
    $('filter').value = 'all'; await refresh(); message('Upload complete. Existing drafts are kept.');
  } catch (e) {
    try { await refresh(); } catch { /* Keep the original upload error. */ }
    message(e.message);
  } finally { $('files').value = ''; setBusy(false); }
};
$('filter').onchange = render;
$('export').onclick = async () => {
  if (draftCount()) { message('Save or discard drafts in this tab before exporting.'); return; }
  try {
    const r = await request('/api/export.csv'), url = URL.createObjectURL(await r.blob());
    const a = document.createElement('a'); a.href = url; a.download = 'reviewed-invoices.csv'; a.click(); URL.revokeObjectURL(url);
    message('Downloaded saved, confirmed records. Browser drafts are never included.');
  } catch (e) { message(e.message); }
};
refresh().catch(e => message(e.message));
