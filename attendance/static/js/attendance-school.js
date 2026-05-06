'use strict';

const AttendanceSchoolApp = {
    async init() {
        this._els = {
            summary: document.getElementById('summary'),
            courseFilter: document.getElementById('courseFilter'),
            studentFilter: document.getElementById('studentFilter'),
            tableContainer: document.getElementById('tableContainer'),
        };
        this._records = [];
        this._filters = { course: '', student: '' };

        this._els.courseFilter.addEventListener('change', () => {
            this._filters.course = this._els.courseFilter.value;
            this._filters.student = '';
            this._populateStudentFilter();
            this._render();
        });

        this._els.studentFilter.addEventListener('change', () => {
            this._filters.student = this._els.studentFilter.value;
            this._render();
        });

        await this._load();
    },

    async _load() {
        try {
            const response = await fetch('/api/attendance/school-records', { cache: 'no-store' });
            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload.detail || 'Impossibile leggere i dati official.');
            }
            this._records = (payload.records || []).slice().sort((a, b) => {
                const courseCompare = a.course_name.localeCompare(b.course_name, 'it');
                if (courseCompare !== 0) return courseCompare;
                const dateCompare = a.lesson_date.localeCompare(b.lesson_date);
                if (dateCompare !== 0) return dateCompare;
                return a.canonical_full_name.localeCompare(b.canonical_full_name, 'it');
            });
            this._populateCourseFilter();
            this._populateStudentFilter();
            this._render();
        } catch (error) {
            console.error(error);
            this._els.tableContainer.innerHTML = `<div class="empty">${this._escapeHtml(error.message)}</div>`;
        }
    },

    _populateCourseFilter() {
        const courses = [...new Set(this._records.map((record) => record.course_name))].sort((a, b) => a.localeCompare(b, 'it'));
        this._els.courseFilter.innerHTML = ['<option value="">Tutti i corsi</option>', ...courses.map((course) => `<option value="${this._escapeAttr(course)}">${this._escapeHtml(course)}</option>`)].join('');
        this._els.courseFilter.value = this._filters.course;
    },

    _populateStudentFilter() {
        const filteredByCourse = this._records.filter((record) => !this._filters.course || record.course_name === this._filters.course);
        const students = [...new Set(filteredByCourse.map((record) => record.canonical_full_name))].sort((a, b) => a.localeCompare(b, 'it'));
        this._els.studentFilter.innerHTML = ['<option value="">Tutti gli studenti</option>', ...students.map((student) => `<option value="${this._escapeAttr(student)}">${this._escapeHtml(student)}</option>`)].join('');
        this._els.studentFilter.value = this._filters.student;
    },

    _getFilteredRecords() {
        return this._records.filter((record) => {
            if (this._filters.course && record.course_name !== this._filters.course) return false;
            if (this._filters.student && record.canonical_full_name !== this._filters.student) return false;
            return true;
        });
    },

    _render() {
        const records = this._getFilteredRecords();
        this._renderSummary(records);
        this._renderTable(records);
    },

    _renderSummary(records) {
        const uniqueCourses = new Set(records.map((record) => record.course_name)).size;
        const uniqueStudents = new Set(records.map((record) => record.canonical_full_name)).size;
        const lessons = new Set(records.map((record) => `${record.course_name}|${record.lesson_date}|${record.lesson_id}`)).size;
        const counts = { presente: 0, prima_meta: 0, seconda_meta: 0, assente: 0 };
        records.forEach((record) => {
            counts[record.final_presence_status] = (counts[record.final_presence_status] || 0) + 1;
        });

        this._els.summary.innerHTML = `
            <article class="summary-card"><div class="summary-label">Record</div><div class="summary-value">${records.length}</div></article>
            <article class="summary-card"><div class="summary-label">Lezioni</div><div class="summary-value">${lessons}</div></article>
            <article class="summary-card"><div class="summary-label">Corsi</div><div class="summary-value">${uniqueCourses}</div></article>
            <article class="summary-card"><div class="summary-label">Studenti</div><div class="summary-value">${uniqueStudents}</div></article>
            <article class="summary-card"><div class="summary-label">Presenti</div><div class="summary-value">${counts.presente || 0}</div></article>
            <article class="summary-card"><div class="summary-label">1ª metà</div><div class="summary-value">${counts.prima_meta || 0}</div></article>
            <article class="summary-card"><div class="summary-label">2ª metà</div><div class="summary-value">${counts.seconda_meta || 0}</div></article>
            <article class="summary-card"><div class="summary-label">Assenti</div><div class="summary-value">${counts.assente || 0}</div></article>
        `;
    },

    _renderTable(records) {
        if (!records.length) {
            this._els.tableContainer.innerHTML = '<div class="empty">Nessun record official compatibile con i filtri attivi.</div>';
            return;
        }

        this._els.tableContainer.innerHTML = `
            <table>
                <thead>
                    <tr>
                        <th>Corso</th>
                        <th>Data</th>
                        <th>Studente</th>
                        <th>Stato di presenza</th>
                    </tr>
                </thead>
                <tbody>
                    ${records.map((record) => `
                        <tr>
                            <td>${this._escapeHtml(record.course_name)}</td>
                            <td>${this._escapeHtml(this._formatDate(record.lesson_date))}</td>
                            <td>${this._escapeHtml(record.canonical_full_name)}</td>
                            <td><span class="status-tag ${this._escapeAttr(record.final_presence_status)}">${this._escapeHtml(this._presenceLabel(record.final_presence_status))}</span></td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    },

    _presenceLabel(status) {
        return {
            presente: 'Presente',
            prima_meta: 'Prima metà',
            seconda_meta: 'Seconda metà',
            assente: 'Assente',
        }[status] || status;
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
    AttendanceSchoolApp.init().catch((error) => console.error(error));
});
