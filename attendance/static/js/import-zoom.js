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
            summaryGrid: document.getElementById('summaryGrid'),
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
            this._setStatus(`Import draft creato per ${file.name}. Batch #${payload.batch_id}.`, 'success');
        } catch (error) {
            console.error(error);
            this._setStatus(`Errore: ${error.message}`, 'error');
        } finally {
            this._setBusy(false);
        }
    },

    _renderSummary(fileName, payload) {
        const cards = [
            {
                label: 'File',
                value: fileName,
                detail: `batch #${payload.batch_id}`,
            },
            {
                label: 'Lezioni',
                value: String(payload.lessons_created ?? 0),
                detail: 'salvate in draft',
            },
            {
                label: 'Partecipanti',
                value: String(payload.participants_created ?? 0),
                detail: 'record draft creati',
            },
            {
                label: 'Stato',
                value: String(payload.status ?? 'draft'),
                detail: payload.source_file_name || 'import batch',
            },
        ];

        this._els.summaryGrid.innerHTML = cards.map((card) => `
            <article class="summary-card">
                <div class="summary-label">${this._escapeHtml(card.label)}</div>
                <div class="summary-value">${this._escapeHtml(card.value)}</div>
                <div class="summary-detail">${this._escapeHtml(card.detail)}</div>
            </article>
        `).join('');

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
