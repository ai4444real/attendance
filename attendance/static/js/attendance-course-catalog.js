'use strict';

const AttendanceCourseCatalogApp = {
    async init() {
        this._els = {
            summary: document.getElementById('summary'),
            catalog: document.getElementById('catalogContainer'),
            importButton: document.getElementById('importGoogleButton'),
            importStatus: document.getElementById('importStatus'),
        };
        this._els.importButton.addEventListener('click', () => this._importFromGoogle());
        await this._load();
    },

    async _load() {
        try {
            const response = await fetch('/api/attendance/course-catalog', { cache: 'no-store' });
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.detail || 'Impossibile leggere il catalogo.');
            this._renderSummary(payload.summary || {});
            this._renderCatalog(payload.editions || []);
        } catch (error) {
            console.error(error);
            this._els.catalog.innerHTML = `<div class="empty">${this._escapeHtml(error.message)}</div>`;
        }
    },

    async _importFromGoogle() {
        this._els.importButton.disabled = true;
        this._els.importStatus.textContent = 'Importazione in corso...';
        try {
            const response = await fetch('/api/attendance/course-catalog/import-google', { method: 'POST' });
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.detail || 'Importazione non riuscita.');
            const outcome = `${payload.rows_read} righe lette · ${payload.created} create · ${payload.updated} aggiornate · ${payload.unchanged} invariate`;
            const warnings = (payload.warnings || []).length
                ? `<ul class="warnings">${payload.warnings.map((warning) => `<li>${this._escapeHtml(warning)}</li>`).join('')}</ul>`
                : '';
            this._els.importStatus.innerHTML = `${this._escapeHtml(outcome)}${warnings}`;
            await this._load();
        } catch (error) {
            console.error(error);
            this._els.importStatus.textContent = error.message;
        } finally {
            this._els.importButton.disabled = false;
        }
    },

    _renderSummary(summary) {
        this._els.summary.innerHTML = `
            <article class="summary-card"><div class="summary-label">Corsi logici</div><div class="summary-value">${summary.logical_courses || 0}</div></article>
            <article class="summary-card"><div class="summary-label">Edizioni / chiavi</div><div class="summary-value">${summary.editions || 0}</div></article>
            <article class="summary-card"><div class="summary-label">Da assegnare</div><div class="summary-value">${summary.unassigned_editions || 0}</div></article>
            <article class="summary-card"><div class="summary-label">Identificatori</div><div class="summary-value">${summary.identifiers || 0}</div></article>
        `;
    },

    _renderCatalog(editions) {
        if (!editions.length) {
            this._els.catalog.innerHTML = '<div class="empty">Il catalogo è vuoto. Usa “Importa da Google” per caricare il foglio Corsi.</div>';
            return;
        }
        this._els.catalog.innerHTML = `
            <div class="table-wrap">
                <table>
                    <thead><tr><th>ID</th><th>Chiave edizione</th><th>Descrizione</th><th>Corso logico</th><th>Classroom</th><th>Calendar</th><th>Link predefinito</th><th>Ultimo import</th></tr></thead>
                    <tbody>${editions.map((edition) => this._renderRow(edition)).join('')}</tbody>
                </table>
            </div>
        `;
    },

    _renderRow(edition) {
        const identifiers = edition.identifiers || {};
        const logicalCourse = edition.logical_course
            ? `<span class="badge assigned">${this._escapeHtml(edition.logical_course.display_name)}</span>`
            : '<span class="badge unassigned">Da definire</span>';
        return `
            <tr>
                <td>${edition.id}</td>
                <td class="key">${this._escapeHtml(edition.edition_key)}</td>
                <td>${this._escapeHtml(edition.display_name)}</td>
                <td>${logicalCourse}</td>
                <td>${this._renderIdentifiers(identifiers.classroom_course_id)}</td>
                <td>${this._renderIdentifiers(identifiers.calendar_id)}</td>
                <td>${this._renderIdentifiers(identifiers.default_link, true)}</td>
                <td class="muted">${this._formatDateTime(edition.last_imported_at)}</td>
            </tr>
        `;
    },

    _renderIdentifiers(values, links = false) {
        if (!values || !values.length) return '<span class="muted">—</span>';
        return `<div class="identifier-list">${values.map((value) => {
            const escaped = this._escapeHtml(value);
            return links && /^https:\/\//i.test(value)
                ? `<a class="identifier" href="${this._escapeAttr(value)}" target="_blank" rel="noopener noreferrer">${escaped}</a>`
                : `<span class="identifier">${escaped}</span>`;
        }).join('')}</div>`;
    },

    _formatDateTime(value) {
        if (!value) return '—';
        return new Date(value).toLocaleString('it-CH', { dateStyle: 'short', timeStyle: 'short' });
    },

    _escapeHtml(value) {
        return String(value)
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#39;');
    },

    _escapeAttr(value) {
        return this._escapeHtml(value);
    },
};

document.addEventListener('DOMContentLoaded', () => {
    AttendanceCourseCatalogApp.init().catch((error) => console.error(error));
});
