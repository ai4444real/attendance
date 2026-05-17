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
        const studentByKey = new Map();
        for (const record of filteredByCourse) {
            const key = this._studentKey(record);
            const current = studentByKey.get(key);
            if (!current || record.canonical_full_name.localeCompare(current, 'it', { sensitivity: 'base' }) < 0) {
                studentByKey.set(key, record.canonical_full_name);
            }
        }
        const students = [...studentByKey.entries()].sort((left, right) => left[1].localeCompare(right[1], 'it', { sensitivity: 'base' }));
        this._els.studentFilter.innerHTML = [
            '<option value="">Tutti gli studenti</option>',
            ...students.map(([key, label]) => `<option value="${this._escapeAttr(key)}">${this._escapeHtml(label)}</option>`),
        ].join('');
        this._els.studentFilter.value = this._filters.student;
    },

    _getFilteredRecords() {
        return this._records.filter((record) => {
            if (this._filters.course && record.course_name !== this._filters.course) return false;
            if (this._filters.student && this._studentKey(record) !== this._filters.student) return false;
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
        const uniqueStudents = new Set(records.map((record) => this._studentKey(record))).size;
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

        const participationByStudentCourse = this._buildParticipationIndex(this._records);

        this._els.tableContainer.innerHTML = `
            <table>
                <thead>
                    <tr>
                        <th>Corso</th>
                        <th>Data</th>
                        <th>Studente</th>
                        <th>Stato di presenza</th>
                        <th>Partecipazione corso</th>
                    </tr>
                </thead>
                <tbody>
                    ${records.map((record) => {
                        const participation = participationByStudentCourse.get(this._studentCourseKey(record));
                        return `
                            <tr>
                                <td>${this._escapeHtml(record.course_name)}</td>
                                <td>${this._escapeHtml(this._formatDate(record.lesson_date))}</td>
                                <td>${this._escapeHtml(record.canonical_full_name)}</td>
                                <td><span class="status-tag ${this._escapeAttr(record.final_presence_status)}">${this._escapeHtml(this._presenceLabel(record.final_presence_status))}</span></td>
                                <td class="participation-cell">${this._renderParticipation(participation)}</td>
                            </tr>
                        `;
                    }).join('')}
                </tbody>
            </table>
        `;
    },

    _buildParticipationIndex(records) {
        const index = new Map();
        for (const record of records) {
            const key = this._studentCourseKey(record);
            const entry = index.get(key) || {
                score: 0,
                expectedLessons: record.expected_lessons_count || 0,
                expectedSource: record.expected_lessons_source || 'official_lessons',
            };
            entry.score += this._presenceScore(record.final_presence_status);
            entry.expectedLessons = record.expected_lessons_count || entry.expectedLessons;
            entry.expectedSource = record.expected_lessons_source || entry.expectedSource;
            index.set(key, entry);
        }

        for (const entry of index.values()) {
            entry.percentage = entry.expectedLessons > 0
                ? (entry.score / entry.expectedLessons) * 100
                : null;
            entry.canTakeExam = entry.expectedSource === 'configured'
                && entry.percentage !== null
                && entry.percentage >= 80;
        }
        return index;
    },

    _renderParticipation(participation) {
        if (!participation || participation.percentage === null) {
            return '<span class="participation-detail">n/d</span>';
        }
        const percentage = this._formatPercentage(participation.percentage);
        const sourceLabel = participation.expectedSource === 'configured'
            ? 'totale configurato'
            : 'totale dedotto';
        const examTag = participation.expectedSource !== 'configured'
            ? '<span class="exam-tag partial">Esame non valutabile</span>'
            : participation.canTakeExam
                ? '<span class="exam-tag ok">Esame ok</span>'
                : '<span class="exam-tag no">Esame no</span>';
        return `
            <div class="participation-value">${this._escapeHtml(percentage)}%</div>
            <div class="participation-detail">${this._escapeHtml(this._formatScore(participation.score))}/${this._escapeHtml(participation.expectedLessons)} · ${this._escapeHtml(sourceLabel)}</div>
            ${examTag}
        `;
    },

    _presenceScore(status) {
        if (status === 'presente') return 1;
        if (status === 'prima_meta' || status === 'seconda_meta') return 0.5;
        return 0;
    },

    _studentCourseKey(record) {
        return `${record.course_name}||${this._studentKey(record)}`;
    },

    _studentKey(record) {
        const name = String(record.canonical_full_name || '').trim().toLocaleLowerCase('it');
        const email = String(record.email || '').trim().toLocaleLowerCase('it');
        return `${name}||${email}`;
    },

    _formatPercentage(value) {
        const rounded = Math.round(value * 10) / 10;
        return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
    },

    _formatScore(value) {
        return Number.isInteger(value) ? String(value) : value.toFixed(1);
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
