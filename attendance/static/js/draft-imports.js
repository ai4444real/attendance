'use strict';

const DraftImportsApp = {
    async init() {
        this._els = {
            batchList: document.getElementById('batchList'),
            batchSummary: document.getElementById('batchSummary'),
            lessonsContainer: document.getElementById('lessonsContainer'),
        };

        await this._loadBatches();
    },

    async _loadBatches() {
        this._els.batchList.innerHTML = '<div class="empty">Carico gli import batch...</div>';
        this._els.batchSummary.innerHTML = '';
        this._els.lessonsContainer.innerHTML = '<div class="empty">Seleziona un import batch.</div>';

        try {
            const response = await fetch('/api/attendance/import-batches');
            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload.detail || 'Impossibile leggere gli import batch.');
            }

            this._batches = payload.batches || [];
            this._renderBatchList();

            if (this._batches.length > 0) {
                await this._loadBatchDetail(this._batches[0].id);
            } else {
                this._els.batchList.innerHTML = '<div class="empty">Nessun import batch nel database.</div>';
            }
        } catch (error) {
            console.error(error);
            this._els.batchList.innerHTML = `<div class="empty">${this._escapeHtml(error.message)}</div>`;
        }
    },

    _renderBatchList() {
        if (!this._batches || this._batches.length === 0) {
            return;
        }

        this._els.batchList.innerHTML = this._batches.map((batch) => `
            <button class="batch-item${this._selectedBatchId === batch.id ? ' active' : ''}" data-batch-id="${batch.id}" type="button">
                <div class="batch-title">#${batch.id} · ${this._escapeHtml(batch.source_file_name)}</div>
                <div class="batch-meta">
                    ${this._escapeHtml(batch.source_system)} · ${this._formatDateTime(batch.created_at)}<br>
                    ${batch.lessons_count} lezioni · ${batch.participants_count} partecipanti · ${this._escapeHtml(batch.status)}
                </div>
            </button>
        `).join('');

        this._els.batchList.querySelectorAll('[data-batch-id]').forEach((button) => {
            button.addEventListener('click', async () => {
                const batchId = Number(button.getAttribute('data-batch-id'));
                await this._loadBatchDetail(batchId);
            });
        });
    },

    async _loadBatchDetail(batchId) {
        this._selectedBatchId = batchId;
        this._renderBatchList();
        this._els.batchSummary.innerHTML = '';
        this._els.lessonsContainer.innerHTML = '<div class="empty">Carico il dettaglio del batch...</div>';

        try {
            const response = await fetch(`/api/attendance/import-batches/${batchId}`);
            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload.detail || 'Impossibile leggere il dettaglio del batch.');
            }

            this._renderBatchSummary(payload.batch);
            this._renderLessons(payload.lessons || []);
        } catch (error) {
            console.error(error);
            this._els.lessonsContainer.innerHTML = `<div class="empty">${this._escapeHtml(error.message)}</div>`;
        }
    },

    _renderBatchSummary(batch) {
        const cards = [
            ['Batch', `#${batch.id}`, batch.source_file_name],
            ['Stato', batch.status, batch.source_system],
            ['Lezioni', String(batch.lessons_count), 'draft nel DB'],
            ['Partecipanti', String(batch.participants_count), this._formatDateTime(batch.created_at)],
        ];

        this._els.batchSummary.innerHTML = cards.map(([label, value, detail]) => `
            <article class="summary-card">
                <div class="summary-label">${this._escapeHtml(label)}</div>
                <div class="summary-value">${this._escapeHtml(value)}</div>
                <div class="hint">${this._escapeHtml(detail)}</div>
            </article>
        `).join('');
    },

    _renderLessons(lessons) {
        if (lessons.length === 0) {
            this._els.lessonsContainer.innerHTML = '<div class="empty">Questo import batch non contiene lezioni.</div>';
            return;
        }

        this._els.lessonsContainer.innerHTML = lessons.map((lesson) => {
            const diagnostics = lesson.diagnostics || {};
            const summary = lesson.summary || {};
            return `
                <article class="lesson-card">
                    <div class="lesson-head">
                        <div>
                            <h3 class="lesson-title">${this._escapeHtml(lesson.course_name)}</h3>
                            <div class="lesson-subtitle">
                                ${this._escapeHtml(lesson.lesson_date)} · meeting ${this._escapeHtml(lesson.source_meeting_id)} · lesson #${lesson.id}
                            </div>
                        </div>
                        <div class="pill-row">
                            <span class="pill green">Presente ${summary.presente || 0}</span>
                            <span class="pill blue">1ª metà ${summary.prima_meta || 0}</span>
                            <span class="pill yellow">2ª metà ${summary.seconda_meta || 0}</span>
                            <span class="pill red">Assente ${summary.assente || 0}</span>
                        </div>
                    </div>
                    <div class="lesson-body">
                        <div class="timeline-meta">
                            ${this._mini('Threshold', `${Math.round((lesson.threshold_ratio || 0) * 100)}%`)}
                            ${this._mini('Inizio utile', this._formatTime(lesson.effective_start_at))}
                            ${this._mini('Pausa', lesson.break_point_at ? this._formatTime(lesson.break_point_at) : '—')}
                            ${this._mini('Fine utile', this._formatTime(lesson.effective_end_at))}
                            ${this._mini('Picco presenti', String(diagnostics.peak_active_count || 0))}
                            ${this._mini('Sorgente', `${lesson.effective_start_source || 'default'} / ${lesson.effective_end_source || 'default'}`)}
                        </div>
                        <table class="participants-table">
                            <thead>
                                <tr>
                                    <th>Persona</th>
                                    <th>Prima metà</th>
                                    <th>Seconda metà</th>
                                    <th>Stato</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${(lesson.participants || []).map((participant) => `
                                    <tr>
                                        <td>
                                            <strong>${this._escapeHtml(participant.canonical_full_name)}</strong><br>
                                            <span class="hint">${this._escapeHtml(participant.email || 'senza email')}</span>
                                        </td>
                                        <td>
                                            ${this._formatMinutes(participant.minutes_first_half)} / ${this._formatMinutes(participant.duration_first_half)} min
                                        </td>
                                        <td>
                                            ${this._formatMinutes(participant.minutes_second_half)} / ${this._formatMinutes(participant.duration_second_half)} min
                                        </td>
                                        <td>
                                            <span class="presence-tag ${this._escapeHtml(participant.final_presence_status)}">${this._escapeHtml(participant.final_presence_status)}</span>
                                        </td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </article>
            `;
        }).join('');
    },

    _mini(label, value) {
        return `
            <div class="mini">
                <div class="mini-label">${this._escapeHtml(label)}</div>
                <div class="mini-value">${this._escapeHtml(value)}</div>
            </div>
        `;
    },

    _formatDateTime(value) {
        return new Date(value).toLocaleString('it-CH', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
        });
    },

    _formatTime(value) {
        return new Date(value).toLocaleTimeString('it-CH', {
            hour: '2-digit',
            minute: '2-digit',
        });
    },

    _formatMinutes(value) {
        return Number(value || 0).toFixed(1);
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

document.addEventListener('DOMContentLoaded', () => {
    DraftImportsApp.init().catch((error) => console.error(error));
});
