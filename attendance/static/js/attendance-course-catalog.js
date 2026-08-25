'use strict';

const AttendanceCourseCatalogApp = {
    async init() {
        this._els = {
            summary: document.getElementById('summary'),
            catalog: document.getElementById('catalogContainer'),
            importButton: document.getElementById('importGoogleButton'),
            importStatus: document.getElementById('importStatus'),
            logicalCourseOptions: document.getElementById('logicalCourseOptions'),
        };
        this._els.importButton.addEventListener('click', () => this._importFromGoogle());
        await this._load();
    },

    async _load() {
        try {
            const response = await fetch('/api/attendance/course-catalog', { cache: 'no-store' });
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.detail || 'Impossibile leggere il catalogo.');
            this._logicalCourses = payload.logical_courses || [];
            this._renderLogicalCourseOptions();
            this._renderSummary(payload.summary || {});
            this._renderCatalog(payload.editions || []);
            this._bindCatalogActions();
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
                    <thead><tr><th>ID</th><th>Chiave edizione</th><th>Descrizione</th><th>Corso logico</th><th>Classroom</th><th>Calendar</th><th>Link predefinito</th><th>Ultimo import</th><th></th></tr></thead>
                    <tbody>${editions.map((edition) => this._renderRow(edition)).join('')}</tbody>
                </table>
            </div>
        `;
    },

    _renderRow(edition) {
        const identifiers = edition.identifiers || {};
        const courseCode = edition.logical_course ? edition.logical_course.code : '';
        return `
            <tr>
                <td>${edition.id}</td>
                <td class="key">${this._escapeHtml(edition.edition_key)}</td>
                <td>${this._escapeHtml(edition.display_name)}</td>
                <td>
                    <form class="logical-course-form" data-edition-id="${edition.id}">
                        <input class="logical-course-input" name="course_code" list="logicalCourseOptions" value="${this._escapeAttr(courseCode)}" placeholder="es. FSEA" aria-label="Corso logico per ${this._escapeAttr(edition.edition_key)}">
                        <button class="logical-course-save" type="submit" title="Salva corso logico">✓</button>
                    </form>
                    <div class="logical-course-status" data-status-for="${edition.id}">${courseCode ? '<span class="badge assigned">Assegnato</span>' : '<span class="badge unassigned">Da definire</span>'}</div>
                </td>
                <td>${this._renderIdentifiers(identifiers.classroom_course_id)}</td>
                <td>${this._renderIdentifiers(identifiers.calendar_id)}</td>
                <td>${this._renderIdentifiers(identifiers.default_link, true)}</td>
                <td class="muted">${this._formatDateTime(edition.last_imported_at)}</td>
                <td><button class="delete-edition" type="button" data-edition-id="${edition.id}" data-edition-key="${this._escapeAttr(edition.edition_key)}" title="Elimina dal catalogo" aria-label="Elimina ${this._escapeAttr(edition.edition_key)}">×</button></td>
            </tr>
        `;
    },

    _renderLogicalCourseOptions() {
        this._els.logicalCourseOptions.innerHTML = (this._logicalCourses || [])
            .map((course) => `<option value="${this._escapeAttr(course.code)}">${this._escapeHtml(course.display_name)}</option>`)
            .join('');
    },

    _bindCatalogActions() {
        this._els.catalog.querySelectorAll('.logical-course-form').forEach((form) => {
            form.addEventListener('submit', (event) => {
                event.preventDefault();
                this._saveLogicalCourse(form);
            });
        });
        this._els.catalog.querySelectorAll('.delete-edition').forEach((button) => {
            button.addEventListener('click', () => this._deleteEdition(button));
        });
    },

    async _saveLogicalCourse(form) {
        const editionId = form.dataset.editionId;
        const input = form.querySelector('input[name="course_code"]');
        const status = this._els.catalog.querySelector(`[data-status-for="${editionId}"]`);
        if (status) status.textContent = 'Salvataggio...';
        try {
            const response = await fetch(`/api/attendance/course-catalog/editions/${editionId}/logical-course`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ course_code: input ? input.value.trim() : '' }),
            });
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.detail || 'Salvataggio non riuscito.');
            await this._load();
        } catch (error) {
            console.error(error);
            if (status) status.textContent = error.message;
        }
    },

    async _deleteEdition(button) {
        const editionId = button.dataset.editionId;
        const editionKey = button.dataset.editionKey || 'questa edizione';
        if (!window.confirm(`Eliminare ${editionKey} dal catalogo? Le presenze non verranno toccate.`)) return;
        button.disabled = true;
        try {
            const response = await fetch(`/api/attendance/course-catalog/editions/${editionId}`, { method: 'DELETE' });
            if (!response.ok) {
                const payload = await response.json();
                throw new Error(payload.detail || 'Eliminazione non riuscita.');
            }
            await this._load();
        } catch (error) {
            console.error(error);
            this._els.importStatus.textContent = error.message;
            button.disabled = false;
        }
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
