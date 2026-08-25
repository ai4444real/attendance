'use strict';

const AttendanceCoursesApp = {
    async init() {
        this._els = {
            summary: document.getElementById('summary'),
            courseContainer: document.getElementById('courseContainer'),
            importLessonTopicsButton: document.getElementById('importLessonTopicsButton'),
            lessonEnrichmentStatus: document.getElementById('lessonEnrichmentStatus'),
        };
        this._courses = [];
        this._summary = {};
        this._els.importLessonTopicsButton.addEventListener('click', () => this._importLessonEnrichment());
        await this._load();
    },

    async _load() {
        try {
            const response = await fetch('/api/attendance/school-courses', { cache: 'no-store' });
            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload.detail || 'Impossibile leggere i corsi official.');
            }

            this._courses = payload.courses || [];
            this._summary = payload.summary || {};
            this._renderSummary();
            this._renderCourses();
            this._bindCourseTargetForms();
        } catch (error) {
            console.error(error);
            this._els.courseContainer.innerHTML = `<div class="empty">${this._escapeHtml(error.message)}</div>`;
        }
    },

    _renderSummary() {
        const lessonDates = new Set();
        let presenti = 0;
        let primeMeta = 0;
        let secondeMeta = 0;

        for (const course of this._courses) {
            for (const lesson of course.lessons || []) {
                lessonDates.add(lesson.lesson_date);
                presenti += lesson.presente_count || 0;
                primeMeta += lesson.prima_meta_count || 0;
                secondeMeta += lesson.seconda_meta_count || 0;
            }
        }

        this._els.summary.innerHTML = `
            <article class="summary-card"><div class="summary-label">Corsi</div><div class="summary-value">${this._summary.courses || 0}</div></article>
            <article class="summary-card"><div class="summary-label">Lezioni</div><div class="summary-value">${this._summary.lessons || 0}</div></article>
            <article class="summary-card"><div class="summary-label">Lezioni attese</div><div class="summary-value">${this._summary.expected_lessons || 0}</div></article>
            <article class="summary-card"><div class="summary-label">Date coperte</div><div class="summary-value">${lessonDates.size}</div></article>
            <article class="summary-card"><div class="summary-label">Record presenza</div><div class="summary-value">${this._summary.records || 0}</div></article>
            <article class="summary-card"><div class="summary-label">Presenti</div><div class="summary-value">${presenti}</div></article>
            <article class="summary-card"><div class="summary-label">1ª metà</div><div class="summary-value">${primeMeta}</div></article>
            <article class="summary-card"><div class="summary-label">2ª metà</div><div class="summary-value">${secondeMeta}</div></article>
        `;
    },

    _renderCourses() {
        if (!this._courses.length) {
            this._els.courseContainer.innerHTML = '<div class="empty">Nessun corso official disponibile.</div>';
            return;
        }

        this._els.courseContainer.innerHTML = this._courses.map((course) => {
            const lessons = course.lessons || [];
            const records = lessons.reduce((sum, lesson) => sum + (lesson.total_records || 0), 0);
            const expectedSource = course.expected_lessons_source === 'configured'
                ? 'configurato'
                : 'da lezioni official';
            return `
                <article class="course-card">
                    <div class="course-header">
                        <div>
                            <h3 class="course-title">${this._escapeHtml(course.course_name)}</h3>
                            <div class="course-meta">${lessons.length}/${course.expected_lessons_count || lessons.length} lezioni · ${this._escapeHtml(expectedSource)} · ${records} record presenza</div>
                        </div>
                        <form class="course-target-form" data-course-name="${this._escapeAttr(course.course_name)}">
                            <label class="course-target-label" for="expected-${this._escapeAttr(this._courseInputId(course.course_name))}">Lezioni totali</label>
                            <input
                                id="expected-${this._escapeAttr(this._courseInputId(course.course_name))}"
                                class="course-target-input"
                                name="expected_lessons_count"
                                type="number"
                                min="1"
                                step="1"
                                value="${course.expected_lessons_source === 'configured' ? this._escapeAttr(course.expected_lessons_count) : ''}"
                                placeholder="${this._escapeAttr(course.expected_lessons_count || lessons.length)}"
                            >
                            <button class="course-target-button" type="submit">Salva</button>
                            <div class="course-target-status" aria-live="polite"></div>
                        </form>
                    </div>
                    <div class="lesson-track">
                        ${lessons.map((lesson) => `
                            <div class="lesson-cell" title="${this._escapeAttr(`${course.course_name} · ${this._formatDate(lesson.lesson_date)} · meeting ${lesson.source_meeting_id}`)}">
                                <div class="lesson-date">${this._escapeHtml(this._formatDate(lesson.lesson_date))}</div>
                                ${lesson.topic ? `<div class="lesson-topic">${this._escapeHtml(lesson.topic)}</div>` : ''}
                                ${lesson.external_lesson_id ? `<div class="lesson-external-id">ID lezione ${this._escapeHtml(lesson.external_lesson_id)}</div>` : ''}
                                <div class="lesson-records">${lesson.total_records || 0}</div>
                                <div class="lesson-records-label">presenze</div>
                                <div class="lesson-status-row">
                                    <span class="lesson-pill presente">P ${lesson.presente_count || 0}</span>
                                    <span class="lesson-pill prima_meta">1ª ${lesson.prima_meta_count || 0}</span>
                                    <span class="lesson-pill seconda_meta">2ª ${lesson.seconda_meta_count || 0}</span>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </article>
            `;
        }).join('');
    },

    async _importLessonEnrichment() {
        const button = this._els.importLessonTopicsButton;
        const status = this._els.lessonEnrichmentStatus;
        button.disabled = true;
        status.textContent = 'Lettura e matching in corso...';
        try {
            const response = await fetch('/api/attendance/lessons/import-google-enrichment', { method: 'POST' });
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.detail || 'Importazione non riuscita.');
            status.textContent = [
                `${payload.rows_read} righe lette`,
                `${payload.matched} collegate`,
                `${payload.updated} aggiornate`,
                `${payload.unchanged} invariate`,
                `${payload.missing_catalog_mapping} senza mappatura corso`,
                `${payload.missing_attendance_lesson} senza lezione Attendance`,
                `${payload.ambiguous} ambigue`,
            ].join(' · ');
            await this._load();
        } catch (error) {
            console.error(error);
            status.textContent = error.message;
        } finally {
            button.disabled = false;
        }
    },

    _bindCourseTargetForms() {
        this._els.courseContainer.querySelectorAll('.course-target-form').forEach((form) => {
            form.addEventListener('submit', async (event) => {
                event.preventDefault();
                await this._saveCourseTarget(form);
            });
        });
    },

    async _saveCourseTarget(form) {
        const courseName = form.getAttribute('data-course-name') || '';
        const input = form.querySelector('input[name="expected_lessons_count"]');
        const status = form.querySelector('.course-target-status');
        const rawValue = input ? input.value.trim() : '';
        if (status) status.textContent = 'Salvo...';

        try {
            const response = await fetch('/api/attendance/courses/expected-lessons', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    course_name: courseName,
                    expected_lessons_count: rawValue,
                }),
            });
            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload.detail || 'Aggiornamento non riuscito.');
            }
            if (status) status.textContent = 'Aggiornato';
            await this._load();
        } catch (error) {
            console.error(error);
            if (status) status.textContent = error.message;
        }
    },

    _formatDate(value) {
        const date = new Date(value);
        return date.toLocaleDateString('it-CH', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
        });
    },

    _courseInputId(courseName) {
        return String(courseName)
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, '-')
            .replace(/^-+|-+$/g, '') || 'course';
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
    AttendanceCoursesApp.init().catch((error) => console.error(error));
});
