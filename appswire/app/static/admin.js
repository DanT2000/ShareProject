'use strict';

// ── Helpers ──────────────────────────────────────────────────────────────────

function esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function q(sel, ctx) { return (ctx || document).querySelector(sel); }
function qa(sel, ctx) { return Array.from((ctx || document).querySelectorAll(sel)); }

// ── Textarea auto-resize ──────────────────────────────────────────────────────

function autoResize(ta) {
  ta.style.height = 'auto';
  ta.style.height = ta.scrollHeight + 'px';
}

qa('textarea.auto-resize').forEach(ta => {
  ta.addEventListener('input', () => autoResize(ta));
  autoResize(ta);
});

// ── Image mode switching ──────────────────────────────────────────────────────

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

// ── Action rows ───────────────────────────────────────────────────────────────

const actionsContainer = q('#actions-container');
let rowCount = 0;

function addActionRow(opts = {}) {
  const idx = rowCount++;
  const kind = opts.kind || 'download';
  const label = opts.label || '';
  const urlVal = opts.url || '';
  const existingFile = opts.existingFile || '';
  const existingFileName = opts.existingFileName || existingFile.split('/').pop();
  const isPrimary = !!opts.isPrimary;

  const row = document.createElement('div');
  row.className = 'action-row';
  row.dataset.existingFile = existingFile;

  row.innerHTML = `
    <div class="action-row-top">
      <select name="action_kind[]" class="action-kind-select">
        <option value="download"${kind === 'download' ? ' selected' : ''}>Download</option>
        <option value="link"${kind === 'link' ? ' selected' : ''}>Link</option>
      </select>
      <input type="text" name="action_label[]" class="action-label-input"
             placeholder="Текст кнопки" value="${esc(label)}">
      <label class="primary-wrap" title="Основная кнопка">
        <input type="radio" name="primary_index" class="primary-radio"
               value="${idx}"${isPrimary ? ' checked' : ''}>
        <span>Primary</span>
      </label>
      <button type="button" class="btn-remove-action" title="Удалить">×</button>
    </div>
    <div class="action-url-field action-sub" style="${kind !== 'link' ? 'display:none' : ''}">
      <input type="url" name="action_url[]" placeholder="https://..." value="${esc(urlVal)}">
    </div>
    <div class="action-file-field action-sub" style="${kind === 'link' ? 'display:none' : ''}">
      <input type="hidden" name="action_existing_file[]" value="${esc(existingFile)}">
      <div class="existing-file-row" style="${existingFile ? '' : 'display:none'}">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
          <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/>
          <polyline points="13 2 13 9 20 9"/>
        </svg>
        <span class="existing-file-name">${esc(existingFileName)}</span>
        <label class="clear-file-label">
          <input type="checkbox" class="clear-file-checkbox" name="action_clear_file" value="${idx}">
          Удалить файл
        </label>
      </div>
      <input type="file" class="action-file-input">
    </div>
  `;

  // Kind toggle
  const kindSel = row.querySelector('.action-kind-select');
  const urlField = row.querySelector('.action-url-field');
  const fileField = row.querySelector('.action-file-field');

  kindSel.addEventListener('change', () => {
    const v = kindSel.value;
    urlField.style.display  = v === 'link'     ? '' : 'none';
    fileField.style.display = v === 'download' ? '' : 'none';
  });

  // Remove
  row.querySelector('.btn-remove-action').addEventListener('click', () => row.remove());

  actionsContainer.appendChild(row);
  return row;
}

q('#add-action-btn')?.addEventListener('click', () => addActionRow());

// ── Before submit: renumber file inputs & radios ──────────────────────────────

q('#project-form')?.addEventListener('submit', function () {
  qa('.action-row', actionsContainer).forEach((row, i) => {
    const radio = row.querySelector('.primary-radio');
    if (radio) radio.value = i;
    const clearCb = row.querySelector('.clear-file-checkbox');
    if (clearCb) clearCb.value = i;
    const fileInput = row.querySelector('.action-file-input');
    if (fileInput) fileInput.name = `action_file_${i}`;
  });
  // If no radio is checked, inject a hidden -1 so the field is always present
  const checkedRadio = q('input.primary-radio:checked', actionsContainer);
  if (!checkedRadio) {
    let fallback = q('#primary_index_hidden');
    if (!fallback) {
      fallback = document.createElement('input');
      fallback.type = 'hidden';
      fallback.name = 'primary_index';
      fallback.id = 'primary_index_hidden';
      this.appendChild(fallback);
    }
    fallback.value = '-1';
  } else {
    const old = q('#primary_index_hidden');
    if (old) old.remove();
  }
});

// ── New project button ────────────────────────────────────────────────────────

q('#new-project-btn')?.addEventListener('click', () => {
  const form = q('#project-form');
  q('#project_id').value = '0';
  q('#form-title').textContent = 'Новый проект';
  q('#submit-btn').textContent = 'Создать';

  // Reset text fields manually
  q('#f-title').value = '';
  q('#f-desc').value = '';
  q('#f-ver').value = '1.0.0';
  q('#f-sort').value = '0';
  q('#f-pub').checked = true;
  q('#f-md').value = '';
  if (q('#image_url_input')) q('#image_url_input').value = '';
  if (q('#image_file')) q('#image_file').value = '';
  if (q('#existing-image-wrap')) q('#existing-image-wrap').style.display = 'none';

  // Reset image mode
  const noneRadio = q('input[name="image_mode"][value="none"]');
  if (noneRadio) { noneRadio.checked = true; applyImageMode('none'); }

  // Clear actions
  actionsContainer.innerHTML = '';
  rowCount = 0;

  // Resize textareas
  qa('textarea.auto-resize').forEach(autoResize);

  // Scroll to form top
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

// ── Populate form if editing (EDIT_PROJECT from template) ────────────────────

if (typeof EDIT_PROJECT !== 'undefined' && EDIT_PROJECT) {
  const p = EDIT_PROJECT;

  q('#project_id').value   = p.id;
  q('#f-title').value      = p.title;
  q('#f-desc').value       = p.description;
  q('#f-ver').value        = p.version;
  q('#f-sort').value       = p.sort_order;
  q('#f-pub').checked      = p.is_published;
  q('#f-md').value         = p.instruction_md;
  q('#form-title').textContent = 'Редактировать';
  q('#submit-btn').textContent = 'Сохранить';

  // Image mode
  const modeRadio = q(`input[name="image_mode"][value="${p.image_mode}"]`);
  if (modeRadio) { modeRadio.checked = true; applyImageMode(p.image_mode); }
  if (p.image_mode === 'url' && q('#image_url_input')) {
    q('#image_url_input').value = p.image_url;
  }
  if (p.image_mode === 'upload' && p.image_path) {
    const wrap = q('#existing-image-wrap');
    const nameEl = q('#existing-image-name');
    if (wrap && nameEl) {
      nameEl.textContent = p.image_path.split('/').pop();
      wrap.style.display = 'block';
    }
  }

  // Actions
  p.actions.forEach(a => {
    addActionRow({
      kind: a.kind,
      label: a.label,
      url: a.url,
      existingFile: a.file_path,
      existingFileName: a.file_name,
      isPrimary: a.is_primary,
    });
  });

  // Resize textareas after fill
  qa('textarea.auto-resize').forEach(autoResize);
}
