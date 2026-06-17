'use strict';

const AttendanceSchoolApp = {
    async init() {
        this._els = {
            summary: document.getElementById('summary'),
            studentFilter: document.getElementById('studentFilter'),
            studentAliasLink: document.getElementById('studentAliasLink'),
            courseCheckboxes: document.getElementById('courseCheckboxes'),
            dateStartFilter: document.getElementById('dateStartFilter'),
            dateEndFilter: document.getElementById('dateEndFilter'),
            selectAllCourses: document.getElementById('selectAllCourses'),
            clearCourses: document.getElementById('clearCourses'),
            orientationContainer: document.getElementById('orientationContainer'),
            tableContainer: document.getElementById('tableContainer'),
            sourceModalHost: document.getElementById('sourceModalHost'),
        };
        this._records = [];
        this._filters = { courses: new Set(), dateStart: '', dateEnd: '', student: '' };
        this._allCourses = [];
        this._studentLabelsByFilterKey = new Map();

        this._els.selectAllCourses.addEventListener('click', () => {
            this._filters.courses = new Set(this._allCourses);
            this._populateCourseCheckboxes();
            this._populateStudentFilter();
            this._render();
        });

        this._els.clearCourses.addEventListener('click', () => {
            this._filters.courses = new Set();
            this._populateCourseCheckboxes();
            this._populateStudentFilter();
            this._render();
        });

        this._els.dateStartFilter.addEventListener('change', () => {
            this._filters.dateStart = this._els.dateStartFilter.value;
            this._populateStudentFilter();
            this._render();
        });

        this._els.dateEndFilter.addEventListener('change', () => {
            this._filters.dateEnd = this._els.dateEndFilter.value;
            this._populateStudentFilter();
            this._render();
        });

        this._els.studentFilter.addEventListener('change', () => {
            this._filters.student = this._els.studentFilter.value;
            this._updateStudentAliasLink();
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
            this._allCourses = [...new Set(this._records.map((record) => record.course_name))]
                .sort((a, b) => a.localeCompare(b, 'it'));
            this._applyDefaultScopeFilters();
            this._populateCourseCheckboxes();
            this._populateStudentFilter();
            this._render();
        } catch (error) {
            console.error(error);
            this._els.tableContainer.innerHTML = `<div class="empty">${this._escapeHtml(error.message)}</div>`;
        }
    },

    _applyDefaultScopeFilters() {
        const preferredCourses = new Set(['MASTER', 'PRACTITIONER']);
        const matchingPreferredCourses = this._allCourses.filter((course) => preferredCourses.has(String(course).toLocaleUpperCase('it')));
        this._filters.courses = new Set(matchingPreferredCourses.length ? matchingPreferredCourses : this._allCourses);

        const lessonDates = this._records
            .map((record) => record.lesson_date)
            .filter(Boolean)
            .sort();
        if (!lessonDates.length) {
            return;
        }
        const latestDate = lessonDates[lessonDates.length - 1];
        const startDate = new Date(`${latestDate}T00:00:00`);
        startDate.setFullYear(startDate.getFullYear() - 1);

        this._filters.dateStart = this._formatDateInput(startDate);
        this._filters.dateEnd = latestDate;
        this._els.dateStartFilter.value = this._filters.dateStart;
        this._els.dateEndFilter.value = this._filters.dateEnd;
    },

    _populateCourseCheckboxes() {
        this._els.courseCheckboxes.innerHTML = this._allCourses.map((course) => {
            const checked = this._filters.courses.has(course) ? 'checked' : '';
            return `
                <label class="course-check">
                    <input type="checkbox" value="${this._escapeAttr(course)}" ${checked}>
                    <span>${this._escapeHtml(course)}</span>
                </label>
            `;
        }).join('');
        this._els.courseCheckboxes.querySelectorAll('input[type="checkbox"]').forEach((checkbox) => {
            checkbox.addEventListener('change', () => {
                if (checkbox.checked) {
                    this._filters.courses.add(checkbox.value);
                } else {
                    this._filters.courses.delete(checkbox.value);
                }
                this._populateStudentFilter();
                this._render();
            });
        });
    },

    _populateStudentFilter() {
        const filteredByCourse = this._records.filter((record) => this._recordMatchesScope(record));
        const studentByKey = new Map();
        for (const record of filteredByCourse) {
            const key = this._studentFilterKey(record);
            const current = studentByKey.get(key);
            const displayName = this._formatPersonName(record.canonical_full_name);
            if (!current || displayName.localeCompare(current, 'it', { sensitivity: 'base' }) < 0) {
                studentByKey.set(key, displayName);
            }
        }
        const students = [...studentByKey.entries()].sort((left, right) => left[1].localeCompare(right[1], 'it', { sensitivity: 'base' }));
        this._els.studentFilter.innerHTML = [
            '<option value="">Tutti gli studenti</option>',
            ...students.map(([key, label]) => `<option value="${this._escapeAttr(key)}">${this._escapeHtml(label)}</option>`),
        ].join('');
        this._studentLabelsByFilterKey = new Map(students);
        if (this._filters.student && !this._studentLabelsByFilterKey.has(this._filters.student)) {
            this._filters.student = '';
        }
        this._els.studentFilter.value = this._filters.student;
        this._updateStudentAliasLink();
    },

    _updateStudentAliasLink() {
        const label = this._studentLabelsByFilterKey.get(this._filters.student) || '';
        const query = label ? `?q=${encodeURIComponent(label)}` : '';
        this._els.studentAliasLink.href = `/attendance/aliases${query}`;
        this._els.studentAliasLink.textContent = label
            ? `Cerca / crea alias per ${label}`
            : 'Cerca / crea alias';
    },

    _getFilteredRecords() {
        return this._records.filter((record) => {
            if (!this._recordMatchesScope(record)) return false;
            if (this._filters.student && this._studentFilterKey(record) !== this._filters.student) return false;
            return true;
        });
    },

    _recordMatchesScope(record) {
        if (!this._filters.courses.has(record.course_name)) return false;
        if (this._filters.dateStart && record.lesson_date < this._filters.dateStart) return false;
        if (this._filters.dateEnd && record.lesson_date > this._filters.dateEnd) return false;
        return true;
    },

    _render() {
        const records = this._getFilteredRecords();
        this._renderSummary(records);
        this._renderOrientation();
        this._renderTable(records);
    },

    _renderSummary(records) {
        const uniqueCourses = new Set(records.map((record) => record.course_name)).size;
        const uniqueStudents = new Set(records.map((record) => this._studentFilterKey(record))).size;
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

    _renderOrientation() {
        if (!this._els.orientationContainer) return;
        if (this._filters.student) {
            this._renderStudentOrientation();
            return;
        }
        this._renderCourseOrientation();
    },

    _renderCourseOrientation() {
        const records = this._records.filter((record) => this._recordMatchesScope(record));
        const courses = this._buildCourseOverview(records);
        if (!courses.length) {
            this._els.orientationContainer.innerHTML = '<div class="empty">Nessun corso official compatibile con i filtri attivi.</div>';
            return;
        }

        this._els.orientationContainer.innerHTML = `
            <div class="orientation-head">
                <div>
                    <h3 class="orientation-title">Mappa corsi</h3>
                    <p class="orientation-subtitle">Una cella per lezione official: data e numero di presenze utili registrate.</p>
                </div>
            </div>
            <div class="course-map">
                ${courses.map((course) => `
                    <article class="course-map-card">
                        <div class="course-map-head">
                            <div>
                                <div class="course-map-title">${this._escapeHtml(course.courseName)}</div>
                                <div class="course-map-meta">
                                    <span>${course.lessons.length} lezioni</span>
                                    <span>${course.totalUsefulPresences} presenze utili</span>
                                    <span>${course.students.size} studenti</span>
                                </div>
                            </div>
                        </div>
                        <div class="lesson-timeline">
                            ${course.lessons.map((lesson) => `
                                <a class="lesson-tile" href="${this._escapeAttr(this._draftLessonUrl(lesson.lesson_id))}" target="_blank" rel="noopener" title="${this._escapeAttr(`${course.courseName} · ${this._formatDate(lesson.lesson_date)} · lesson #${lesson.lesson_id}`)}">
                                    <div class="lesson-tile-date">${this._escapeHtml(this._formatShortDate(lesson.lesson_date))}</div>
                                    <div class="lesson-tile-detail"><span class="lesson-tile-count">${lesson.usefulPresences}</span> presenze</div>
                                </a>
                            `).join('')}
                        </div>
                    </article>
                `).join('')}
            </div>
        `;
    },

    _renderStudentOrientation() {
        const studentLabel = this._studentLabelsByFilterKey.get(this._filters.student) || 'Studente selezionato';
        const recordsByCourse = this._records.filter((record) => {
            if (!this._recordMatchesScope(record)) return false;
            return this._studentFilterKey(record) === this._filters.student;
        });
        const activeCourses = [...new Set(
            recordsByCourse
                .filter((record) => this._presenceScore(record.final_presence_status) > 0)
                .map((record) => record.course_name)
        )]
            .sort((a, b) => a.localeCompare(b, 'it'));
        if (!activeCourses.length) {
            this._els.orientationContainer.innerHTML = '<div class="empty">Nessun corso con presenze per lo studente selezionato.</div>';
            return;
        }

        const participationByStudentCourse = this._buildParticipationIndex(
            this._records.filter((record) => this._recordMatchesScope(record))
        );
        const allLessonsByCourse = this._buildCourseOverview(
            this._records.filter((record) => activeCourses.includes(record.course_name) && this._recordMatchesScope(record))
        );
        const courseByName = new Map(allLessonsByCourse.map((course) => [course.courseName, course]));

        this._els.orientationContainer.innerHTML = `
            <div class="orientation-head">
                <div>
                    <h3 class="orientation-title">${this._escapeHtml(studentLabel)}</h3>
                    <p class="orientation-subtitle">Timeline dei soli corsi dove lo studente compare. Le celle vuote sono lezioni official senza record per quello studente.</p>
                </div>
                <div class="timeline-legend">
                    <span class="legend-dot green">presente</span>
                    <span class="legend-dot blue">prima metà</span>
                    <span class="legend-dot yellow">seconda metà</span>
                    <span class="legend-dot gray">nessun record</span>
                </div>
            </div>
            <div class="course-map">
                ${activeCourses.map((courseName) => {
                    const course = courseByName.get(courseName);
                    const participantByLesson = new Map(
                        recordsByCourse
                            .filter((record) => record.course_name === courseName)
                            .map((record) => [String(record.lesson_id), record])
                    );
                    const firstRecord = recordsByCourse.find((record) => record.course_name === courseName);
                    const participation = firstRecord ? participationByStudentCourse.get(this._studentCourseKey(firstRecord)) : null;
                    return `
                        <article class="course-map-card">
                            <div class="course-map-head">
                                <div>
                                    <div class="course-map-title">${this._escapeHtml(courseName)}</div>
                                    <div class="course-map-meta">
                                        <span>${course?.lessons.length || 0} lezioni official</span>
                                        <span>${participantByLesson.size} lezioni con record</span>
                                    </div>
                                </div>
                                <div class="course-map-score">${this._renderCompactParticipation(participation)}</div>
                            </div>
                            <div class="lesson-timeline">
                                ${(course?.lessons || []).map((lesson) => {
                                    const record = participantByLesson.get(String(lesson.lesson_id));
                                    const status = record?.final_presence_status || 'missing';
                                    return `
                                        <a class="lesson-tile ${this._escapeAttr(status)}" href="${this._escapeAttr(this._draftLessonUrl(lesson.lesson_id))}" target="_blank" rel="noopener" title="${this._escapeAttr(`${courseName} · ${this._formatDate(lesson.lesson_date)} · ${record ? this._presenceLabel(record.final_presence_status) : 'nessun record'}`)}">
                                            <div class="lesson-tile-date">${this._escapeHtml(this._formatShortDate(lesson.lesson_date))}</div>
                                            <div class="lesson-tile-detail">${this._escapeHtml(record ? this._presenceShortLabel(record.final_presence_status) : 'vuoto')}</div>
                                        </a>
                                    `;
                                }).join('')}
                            </div>
                        </article>
                    `;
                }).join('')}
            </div>
        `;
    },

    _buildCourseOverview(records) {
        const byCourse = new Map();
        for (const record of records) {
            const course = byCourse.get(record.course_name) || {
                courseName: record.course_name,
                lessonsById: new Map(),
                students: new Set(),
                totalUsefulPresences: 0,
            };
            const lesson = course.lessonsById.get(String(record.lesson_id)) || {
                lesson_id: record.lesson_id,
                lesson_date: record.lesson_date,
                usefulPresences: 0,
                records: 0,
            };
            lesson.records += 1;
            if (this._presenceScore(record.final_presence_status) > 0) {
                lesson.usefulPresences += 1;
                course.totalUsefulPresences += 1;
            }
            course.students.add(this._studentFilterKey(record));
            course.lessonsById.set(String(record.lesson_id), lesson);
            byCourse.set(record.course_name, course);
        }

        return [...byCourse.values()]
            .map((course) => ({
                ...course,
                lessons: [...course.lessonsById.values()].sort((a, b) => a.lesson_date.localeCompare(b.lesson_date) || String(a.lesson_id).localeCompare(String(b.lesson_id))),
            }))
            .sort((a, b) => a.courseName.localeCompare(b.courseName, 'it'));
    },

    _renderCompactParticipation(participation) {
        if (!participation || participation.percentage === null) {
            return '<div class="course-map-score-detail">n/d</div>';
        }
        return `
            <div class="course-map-score-value">${this._escapeHtml(this._formatPercentage(participation.percentage))}%</div>
            <div class="course-map-score-detail">${this._escapeHtml(this._formatScore(participation.score))}/${this._escapeHtml(participation.expectedLessons)}</div>
        `;
    },

    _renderTable(records) {
        if (!records.length) {
            this._els.tableContainer.innerHTML = '<div class="empty">Nessun record official compatibile con i filtri attivi.</div>';
            return;
        }

        const participationByStudentCourse = this._buildParticipationIndex(this._records.filter((record) => this._recordMatchesScope(record)));

        this._els.tableContainer.innerHTML = `
            <table>
                <thead>
                    <tr>
                        <th>Corso</th>
                        <th>Data</th>
                        <th>Studente</th>
                        <th>Stato di presenza</th>
                        <th>Partecipazione corso</th>
                        <th>Origine</th>
                    </tr>
                </thead>
                <tbody>
                    ${records.map((record) => {
                        const participation = participationByStudentCourse.get(this._studentCourseKey(record));
                        return `
                            <tr>
                                <td>${this._escapeHtml(record.course_name)}</td>
                                <td><a class="lesson-link" href="${this._escapeAttr(this._draftLessonUrl(record.lesson_id))}" target="_blank" rel="noopener">${this._escapeHtml(this._formatDate(record.lesson_date))}</a></td>
                                <td>${this._escapeHtml(this._formatPersonName(record.canonical_full_name))}</td>
                                <td><span class="status-tag ${this._escapeAttr(record.final_presence_status)}">${this._escapeHtml(this._presenceLabel(record.final_presence_status))}</span></td>
                                <td class="participation-cell">${this._renderParticipation(participation)}</td>
                                <td>
                                    <button type="button" class="origin-button" data-origin-record="${this._escapeAttr(this._originRecordPayload(record))}">Origine</button>
                                </td>
                            </tr>
                        `;
                    }).join('')}
                </tbody>
            </table>
        `;
        this._els.tableContainer.querySelectorAll('[data-origin-record]').forEach((button) => {
            button.addEventListener('click', () => {
                const record = JSON.parse(button.getAttribute('data-origin-record') || '{}');
                this._openSourceModal(record);
            });
        });
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

    _originRecordPayload(record) {
        return JSON.stringify({
            lesson_id: record.lesson_id,
            course_name: record.course_name,
            lesson_date: record.lesson_date,
            canonical_full_name: record.canonical_full_name,
            email: record.email || '',
        });
    },

    _draftLessonUrl(lessonId) {
        return `/attendance/drafts?lesson_id=${encodeURIComponent(String(lessonId))}`;
    },

    async _openSourceModal(record) {
        if (!this._els.sourceModalHost) return;
        this._renderSourceModalShell(record, '<div class="source-empty">Caricamento origine...</div>');
        try {
            const query = new URLSearchParams({
                lesson_id: String(record.lesson_id),
                canonical_full_name: record.canonical_full_name || '',
                email: record.email || '',
            });
            const response = await fetch(`/api/attendance/school-record-source?${query.toString()}`, { cache: 'no-store' });
            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload.detail || 'Origine record non disponibile.');
            }
            this._renderSourceModal(record, payload);
        } catch (error) {
            console.error(error);
            this._renderSourceModalShell(record, `<div class="source-empty">${this._escapeHtml(error.message)}</div>`);
        }
    },

    _renderSourceModal(record, payload) {
        const sources = Array.isArray(payload.sources) ? payload.sources : [];
        const body = sources.length > 0
            ? sources.map((source) => this._renderSourceGroup(source, payload.lesson?.meeting_start_at)).join('')
            : '<div class="source-empty">Nessun segmento origine salvato per questo record.</div>';
        this._renderSourceModalShell(record, body);
    },

    _renderSourceGroup(source, meetingStart) {
        const segments = Array.isArray(source.segments)
            ? source.segments.filter((segment) => Array.isArray(segment) && segment.length === 2)
            : [];
        return `
            <section class="source-group">
                <div class="source-group-head">
                    <div>
                        <div class="source-name">${this._escapeHtml(source.raw_full_name || 'Senza nome')}</div>
                        <div class="source-email">${this._escapeHtml(source.email || 'senza email')}</div>
                    </div>
                    <div class="source-count">${segments.length} segment${segments.length === 1 ? 'o' : 'i'}</div>
                </div>
                <div class="source-segments">
                    ${segments.length > 0 ? segments.map((segment) => `
                        <div class="source-segment">
                            ${this._escapeHtml(this._formatDateTime(segment[0], meetingStart))} → ${this._escapeHtml(this._formatDateTime(segment[1], meetingStart))}
                        </div>
                    `).join('') : '<div class="source-empty">Nessun segmento salvato.</div>'}
                </div>
            </section>
        `;
    },

    _renderSourceModalShell(record, bodyHtml) {
        this._closeSourceModal();
        this._els.sourceModalHost.innerHTML = `
            <div class="source-modal-backdrop" data-source-modal-close="1">
                <div class="source-modal" role="dialog" aria-modal="true" aria-labelledby="sourceModalTitle">
                    <div class="source-modal-head">
                        <div>
                            <h4 id="sourceModalTitle" class="source-modal-title">Origine record</h4>
                            <div class="source-modal-subtitle">
                                ${this._escapeHtml(this._formatPersonName(record.canonical_full_name))} · ${this._escapeHtml(record.course_name)} · ${this._escapeHtml(this._formatDate(record.lesson_date))}
                            </div>
                        </div>
                        <button type="button" class="source-modal-close" data-source-modal-close="1" aria-label="Chiudi dettaglio origine">×</button>
                    </div>
                    <div class="source-modal-body">${bodyHtml}</div>
                </div>
            </div>
        `;
        this._els.sourceModalHost.querySelectorAll('[data-source-modal-close]').forEach((node) => {
            node.addEventListener('click', (event) => {
                if (event.target === node || node.classList.contains('source-modal-close')) {
                    this._closeSourceModal();
                }
            });
        });
        document.addEventListener('keydown', this._handleSourceModalEscape);
        this._sourceModalOpen = true;
    },

    _handleSourceModalEscape: (event) => {
        if (event.key === 'Escape' && AttendanceSchoolApp._sourceModalOpen) {
            AttendanceSchoolApp._closeSourceModal();
        }
    },

    _closeSourceModal() {
        if (!this._els?.sourceModalHost) return;
        this._els.sourceModalHost.innerHTML = '';
        this._sourceModalOpen = false;
        document.removeEventListener('keydown', this._handleSourceModalEscape);
    },

    _studentCourseKey(record) {
        return `${record.course_name}||${this._studentKey(record)}`;
    },

    _studentFilterKey(record) {
        return String(record.canonical_full_name || '').trim().toLocaleLowerCase('it');
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

    _formatPersonName(value) {
        return String(value || '').trim().replace(/\S+/g, (word) => {
            if (word.length <= 1 || word !== word.toLocaleUpperCase('it')) {
                return word;
            }
            return word.charAt(0).toLocaleUpperCase('it') + word.slice(1).toLocaleLowerCase('it');
        });
    },

    _presenceLabel(status) {
        return {
            presente: 'Presente',
            prima_meta: 'Prima metà',
            seconda_meta: 'Seconda metà',
            assente: 'Assente',
        }[status] || status;
    },

    _presenceShortLabel(status) {
        return {
            presente: 'presente',
            prima_meta: '1ª metà',
            seconda_meta: '2ª metà',
            assente: 'assente',
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

    _formatShortDate(value) {
        const date = new Date(value);
        return date.toLocaleDateString('it-CH', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
        });
    },

    _formatDateInput(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    },

    _formatDateTime(value, fallbackValue = null) {
        const fallback = fallbackValue ? new Date(fallbackValue) : null;
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) {
            return value || '';
        }
        const hasDateChange = fallback && !Number.isNaN(fallback.getTime())
            ? date.toDateString() !== fallback.toDateString()
            : true;
        const time = date.toLocaleTimeString('it-CH', {
            hour: '2-digit',
            minute: '2-digit',
        });
        if (!hasDateChange) {
            return time;
        }
        return `${date.toLocaleDateString('it-CH', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
        })}, ${time}`;
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
