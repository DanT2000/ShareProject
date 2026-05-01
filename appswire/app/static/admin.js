'use strict';

// ── Helpers ──────────────────────────────────────────────────────────────────

function esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function q(sel, ctx)  { return (ctx || document).querySelector(sel); }
function qa(sel, ctx) { return Array.from((ctx || document).querySelectorAll(sel)); }

// ── Tabs ──────────────────────────────────────────────────────────────────────

function switchTab(name) {
  qa('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  qa('.tab-panel').forEach(p => { p.hidden = p.id !== `tab-${name}`; });
}

qa('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

// ── Textarea auto-resize (description only, capped by CSS max-height) ────────

function autoResize(ta) {
  ta.style.height = 'auto';
  ta.style.height = Math.min(ta.scrollHeight, 160) + 'px';
}

qa('textarea.auto-resize').forEach(ta => {
  ta.addEventListener('input', () => autoResize(ta));
  autoResize(ta);
});

// ── Image mode (pill radios) ──────────────────────────────────────────────────

const imgUrlField    = q('#image-url-field');
const imgUploadField = q('#image-upload-field');

function applyImageMode(mode) {
  if (imgUrlField)    imgUrlField.style.display    = mode === 'url'    ? 'block' : 'none';
  if (imgUploadField) imgUploadField.style.display = mode === 'upload' ? 'block' : 'none';
}

qa('input[name="image_mode"]').forEach(r => {
  r.addEventListener('change', () => applyImageMode(r.value));
  if (r.checked) applyImageMode(r.value);
});

// ── Actions counter ───────────────────────────────────────────────────────────

const actionsContainer = q('#actions-container');
const actionsCountEl   = q('#actions-count');
const actionsEmptyHint = q('#actions-empty-hint');
let rowCount = 0;

function updateActionsCount() {
  const n = actionsContainer ? actionsContainer.querySelectorAll('.action-row').length : 0;
  if (actionsCountEl)   actionsCountEl.textContent = n === 0 ? '0 действий' : `${n} действи${n === 1 ? 'е' : n < 5 ? 'я' : 'й'}`;
  if (actionsEmptyHint) actionsEmptyHint.style.display = n === 0 ? 'block' : 'none';
}

updateActionsCount();

// ── Add action row ────────────────────────────────────────────────────────────

function addActionRow(opts = {}) {
  const idx  = rowCount++;
  const kind = opts.kind || 'download';

  const row = document.createElement('div');
  row.className = 'action-row';

  row.innerHTML = `
    <div class="action-row-top">
      <select name="action_kind[]" class="action-kind-select">
        <option value="download"${kind === 'download' ? ' selected' : ''}>Download</option>
        <option value="link"${kind === 'link' ? ' selected' : ''}>Link</option>
      </select>
      <input type="text" name="action_label[]" class="action-label-input"
             placeholder="Текст кнопки" value="${esc(opts.label || '')}">
    </div>
    <div class="action-row-controls">
      <label class="primary-wrap">
        <input type="radio" name="primary_index" class="primary-radio"
               value="${idx}"${opts.isPrimary ? ' checked' : ''}>
        <span>Primary</span>
      </label>
      <button type="button" class="btn-remove-action" title="Удалить">×</button>
    </div>
    <div class="action-url-field" style="${kind !== 'link' ? 'display:none' : ''}">
      <input type="url" name="action_url[]" placeholder="https://..." value="${esc(opts.url || '')}">
    </div>
    <div class="action-file-field" style="${kind === 'link' ? 'display:none' : ''}">
      <input type="hidden" name="action_existing_file[]" value="${esc(opts.existingFile || '')}">
      <div class="existing-file-row" style="${opts.existingFile ? '' : 'display:none'}">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13">
          <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/>
          <polyline points="13 2 13 9 20 9"/>
        </svg>
        <span class="existing-file-name">${esc(opts.existingFileName || (opts.existingFile || '').split('/').pop())}</span>
        <label class="clear-file-label">
          <input type="checkbox" class="clear-file-checkbox" name="action_clear_file" value="${idx}">
          Удалить
        </label>
      </div>
      <input type="file" class="action-file-input">
    </div>
  `;

  const kindSel   = row.querySelector('.action-kind-select');
  const urlField  = row.querySelector('.action-url-field');
  const fileField = row.querySelector('.action-file-field');

  kindSel.addEventListener('change', () => {
    urlField.style.display  = kindSel.value === 'link'     ? '' : 'none';
    fileField.style.display = kindSel.value === 'download' ? '' : 'none';
  });

  row.querySelector('.btn-remove-action').addEventListener('click', () => {
    row.remove();
    updateActionsCount();
  });

  actionsContainer.appendChild(row);
  updateActionsCount();
  return row;
}

q('#add-action-btn')?.addEventListener('click', () => {
  addActionRow();
  // Switch to actions tab if not already there
  switchTab('actions');
});

// ── Before submit: renumber indices ──────────────────────────────────────────

q('#project-form')?.addEventListener('submit', function () {
  qa('.action-row', actionsContainer).forEach((row, i) => {
    const radio = row.querySelector('.primary-radio');
    if (radio) radio.value = i;
    const cb = row.querySelector('.clear-file-checkbox');
    if (cb) cb.value = i;
    const fi = row.querySelector('.action-file-input');
    if (fi) fi.name = `action_file_${i}`;
  });
  const checked = q('input.primary-radio:checked', actionsContainer);
  if (!checked) {
    let hid = q('#primary_index_hidden');
    if (!hid) {
      hid = document.createElement('input');
      hid.type = 'hidden'; hid.name = 'primary_index'; hid.id = 'primary_index_hidden';
      this.appendChild(hid);
    }
    hid.value = '-1';
  } else {
    const old = q('#primary_index_hidden');
    if (old) old.remove();
  }
});

// ── New project ───────────────────────────────────────────────────────────────

q('#new-project-btn')?.addEventListener('click', () => {
  q('#project_id').value = '0';
  q('#form-title').textContent = 'Новый проект';
  q('#submit-btn').textContent = 'Создать проект';

  q('#f-title').value = '';
  q('#f-desc').value  = '';
  q('#f-ver').value   = '1.0.0';
  q('#f-sort').value  = '0';
  q('#f-pub').checked = true;
  q('#f-md').value    = '';

  const urlInp = q('#image_url_input');
  if (urlInp) urlInp.value = '';
  const existImg = q('#existing-image-wrap');
  if (existImg) existImg.style.display = 'none';

  const noneRadio = q('input[name="image_mode"][value="none"]');
  if (noneRadio) { noneRadio.checked = true; applyImageMode('none'); }

  actionsContainer.innerHTML = '';
  rowCount = 0;
  updateActionsCount();

  qa('textarea.auto-resize').forEach(autoResize);
  switchTab('basic');
  q('.dash-sidebar')?.scrollTo({ top: 0, behavior: 'smooth' });
});

// ── Delete confirmation ───────────────────────────────────────────────────────

qa('.delete-project-form').forEach(form => {
  form.addEventListener('submit', e => {
    if (!confirm('Удалить проект и все его файлы? Это действие необратимо.')) {
      e.preventDefault();
    }
  });
});

// ── Populate form for edit (EDIT_PROJECT comes from template) ─────────────────

if (typeof EDIT_PROJECT !== 'undefined' && EDIT_PROJECT) {
  const p = EDIT_PROJECT;

  q('#project_id').value = p.id;
  q('#f-title').value    = p.title;
  q('#f-desc').value     = p.description;
  q('#f-ver').value      = p.version;
  q('#f-sort').value     = p.sort_order;
  q('#f-pub').checked    = p.is_published;
  q('#f-md').value       = p.instruction_md;

  q('#form-title').textContent   = 'Редактировать';
  q('#submit-btn').textContent   = 'Сохранить изменения';

  // Image
  const modeR = q(`input[name="image_mode"][value="${p.image_mode}"]`);
  if (modeR) { modeR.checked = true; applyImageMode(p.image_mode); }
  if (p.image_mode === 'url' && q('#image_url_input')) {
    q('#image_url_input').value = p.image_url;
  }
  if (p.image_mode === 'upload' && p.image_path) {
    const wrap = q('#existing-image-wrap');
    const name = q('#existing-image-name');
    if (wrap && name) {
      name.textContent = p.image_path.split('/').pop();
      wrap.style.display = 'flex';
    }
  }

  // Actions
  p.actions.forEach(a => addActionRow({
    kind: a.kind, label: a.label, url: a.url,
    existingFile: a.file_path, existingFileName: a.file_name,
    isPrimary: a.is_primary,
  }));

  qa('textarea.auto-resize').forEach(autoResize);
}
