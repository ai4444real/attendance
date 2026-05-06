'use strict';

const ImportZoomApp = {
    init() {
        this._els = {
            dropZone: document.getElementById('dropZone'),
            fileInput: document.getElementById('fileInput'),
            pickFileBtn: document.getElementById('pickFileBtn'),
            reviewLastBtn: document.getElementById('reviewLastBtn'),
            statusLine: document.getElementById('statusLine'),
            summaryPanel: document.getElementById('summaryPanel'),
            summaryStrip: document.getElementById('summaryStrip'),
            importedLessonsList: document.getElementById('importedLessonsList'),
            skippedLessonsList: document.getElementById('skippedLessonsList'),
        };

        this._wireUpload();
        this._wireReviewLast();
    },

    _wireUpload() {
        this._els.pickFileBtn.addEventListener('click', () => this._els.fileInput.click());
        this._els.fileInput.addEventListener('change', (event) => {
            const file = event.target.files && event.target.files[0];
            if (file) {
                this._uploadFile(file);
            }
        });

        this._els.dropZone.addEventListener('dragover', (event) => {
            event.preventDefault();
            this._els.dropZone.classList.add('dragover');
        });

        this._els.dropZone.addEventListener('dragleave', () => {
            this._els.dropZone.classList.remove('dragover');
        });

        this._els.dropZone.addEventListener('drop', (event) => {
            event.preventDefault();
            this._els.dropZone.classList.remove('dragover');
            const file = event.dataTransfer.files && event.dataTransfer.files[0];
            if (file) {
                this._uploadFile(file);
            }
        });
    },

    _wireReviewLast() {
        this._els.reviewLastBtn.addEventListener('click', () => {
            window.location.href = '/attendance/review';
        });
    },

    async _uploadFile(file) {
        if (!file.name.toLowerCase().endsWith('.csv')) {
            this._setStatus('Serve un file CSV Zoom.', 'error');
            return;
        }

        this._setBusy(true);
        this._setStatus(`Carico ${file.name} e avvio la normalizzazione...`, 'info');

        try {
            const formData = new FormData();
            formData.append('file', file, file.name);

            const response = await fetch('/api/attendance/import-draft', {
                method: 'POST',
                body: formData,
            });

            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload.detail || 'Normalizzazione fallita.');
            }

            this._renderSummary(file.name, payload);
            if (payload.batch_created) {
                this._setStatus(`Import draft creato per ${file.name}. Batch #${payload.batch_id}.`, 'success');
            } else {
                this._setStatus(`Nessuna nuova lezione importata da ${file.name}: tutto già presente nel database.`, 'success');
            }
        } catch (error) {
            console.error(error);
            this._setStatus(`Errore: ${error.message}`, 'error');
        } finally {
            this._setBusy(false);
        }
    },

    _renderSummary(fileName, payload) {
        const stripItems = [
            {
                label: 'Batch',
                value: payload.batch_created ? `#${payload.batch_id}` : 'nessuno',
                tone: payload.batch_created ? 'good' : '',
            },
            {
                label: 'Lezioni importate',
                value: String(payload.lessons_created ?? 0),
                tone: (payload.lessons_created ?? 0) > 0 ? 'good' : '',
            },
            {
                label: 'Lezioni non importate',
                value: String(payload.duplicate_lessons_skipped ?? 0),
                tone: (payload.duplicate_lessons_skipped ?? 0) > 0 ? 'warn' : '',
            },
        ];

        this._els.summaryStrip.innerHTML = stripItems.map((item) => `
            <div class="result-pill">
                <span class="result-pill-label">${this._escapeHtml(item.label)}</span>
                <span class="result-pill-value ${this._escapeHtml(item.tone || '')}">${this._escapeHtml(item.value)}</span>
            </div>
        `).join('');

        const imported = payload.imported_lessons || [];
        const skipped = payload.skipped_duplicates || [];
        this._els.importedLessonsList.innerHTML = imported.length > 0
            ? `
                ${imported.slice(0, 8).map((item) => `
                    <div class="summary-item">
                        ${this._escapeHtml(item.course_name)} · ${this._escapeHtml(item.lesson_date)}
                        <span class="summary-item-hint">meeting ${this._escapeHtml(item.source_meeting_id)}</span>
                    </div>
                `).join('')}
                ${imported.length > 8 ? `<div class="summary-item">... e altre ${this._escapeHtml(imported.length - 8)} lezioni importate</div>` : ''}
            `
            : '<div class="summary-empty">Nessuna lezione nuova in questo file.</div>';

        this._els.skippedLessonsList.innerHTML = skipped.length > 0
            ? `
                ${skipped.slice(0, 8).map((item) => `
                    <div class="summary-item">
                        ${this._escapeHtml(item.course_name)} · ${this._escapeHtml(item.lesson_date)}
                        <span class="summary-item-hint">già presente in batch #${this._escapeHtml(item.existing_batch_id)} · lesson #${this._escapeHtml(item.existing_lesson_id)}</span>
                    </div>
                `).join('')}
                ${skipped.length > 8 ? `<div class="summary-item">... e altre ${this._escapeHtml(skipped.length - 8)} lezioni già presenti</div>` : ''}
            `
            : '<div class="summary-empty">Nessuna lezione saltata.</div>';

        this._els.summaryPanel.classList.remove('hidden');
    },

    _setBusy(isBusy) {
        this._els.pickFileBtn.disabled = isBusy;
        this._els.reviewLastBtn.disabled = isBusy;
        this._els.fileInput.disabled = isBusy;
    },

    _setStatus(message, kind) {
        this._els.statusLine.textContent = message;
        this._els.statusLine.className = `status-line ${kind}`;
    },

    _escapeHtml(value) {
        return String(value)
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#39;');
    },
};

document.addEventListener('DOMContentLoaded', () => ImportZoomApp.init());
