'use strict';

const AttendanceFollowupsApp = {
    async init() {
        this._els = {
            summary: document.getElementById('summary'),
            criteriaText: document.getElementById('criteriaText'),
            followupContainer: document.getElementById('followupContainer'),
        };
        await this._load();
    },

    async _load() {
        try {
            const response = await fetch('/api/attendance/school-followups', { cache: 'no-store' });
            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload.detail || 'Impossibile leggere gli alert.');
            }
            this._criteria = payload.criteria || {};
            this._followups = payload.followups || [];
            this._render();
        } catch (error) {
            console.error(error);
            this._els.followupContainer.innerHTML = `<div class="empty">${this._escapeHtml(error.message)}</div>`;
        }
    },

    _render() {
        this._renderSummary();
        this._renderCriteria();
        this._renderTable();
    },

    _renderSummary() {
        const courses = new Set(this._followups.map((item) => item.course_name)).size;
        const students = new Set(this._followups.map((item) => item.canonical_full_name)).size;
        const missed = this._followups.reduce((sum, item) => sum + (item.missed_lessons_count || 0), 0);
        this._els.summary.innerHTML = `
            <article class="summary-card"><div class="summary-label">Alert</div><div class="summary-value">${this._followups.length}</div></article>
            <article class="summary-card"><div class="summary-label">Corsi</div><div class="summary-value">${courses}</div></article>
            <article class="summary-card"><div class="summary-label">Studenti</div><div class="summary-value">${students}</div></article>
            <article class="summary-card"><div class="summary-label">Assenze implicite</div><div class="summary-value">${missed}</div></article>
        `;
    },

    _renderCriteria() {
        const recent = this._criteria.recent_lessons_limit || 4;
        const threshold = this._criteria.missed_lessons_threshold || 3;
        this._els.criteriaText.textContent = `Mostra studenti con almeno ${threshold} assenze implicite nelle ultime ${recent} lezioni official del corso.`;
    },

    _renderTable() {
        if (!this._followups.length) {
            this._els.followupContainer.innerHTML = '<div class="empty">Nessuno studente da richiamare con i criteri attuali.</div>';
            return;
        }

        this._els.followupContainer.innerHTML = `
            <table>
                <thead>
                    <tr>
                        <th>Corso</th>
                        <th>Studente</th>
                        <th>Assenze recenti</th>
                        <th>Ultime lezioni</th>
                    </tr>
                </thead>
                <tbody>
                    ${this._followups.map((item) => `
                        <tr>
                            <td>${this._escapeHtml(item.course_name)}</td>
                            <td>
                                <div class="student-name">${this._escapeHtml(item.canonical_full_name)}</div>
                                ${item.email ? `<div class="student-email">${this._escapeHtml(item.email)}</div>` : ''}
                            </td>
                            <td>
                                <div class="missed-count">${item.missed_lessons_count}/${item.checked_lessons_count}</div>
                                <div class="student-email">${item.attended_lessons_count} presenti nelle lezioni controllate</div>
                            </td>
                            <td>
                                <div class="lesson-dots">
                                    ${(item.recent_lessons || []).map((lesson) => `
                                        <span
                                            class="lesson-dot ${lesson.attended ? 'present' : 'missing'}"
                                            title="${this._escapeAttr(this._formatDate(lesson.lesson_date))} · ${lesson.attended ? 'presente' : 'assenza implicita'}"
                                        >
                                            ${lesson.attended ? 'P' : 'A'}
                                        </span>
                                    `).join('')}
                                </div>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    },

    _formatDate(value) {
        const date = new Date(value);
        return date.toLocaleDateString('it-CH', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
        });
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
    AttendanceFollowupsApp.init().catch((error) => console.error(error));
});
