'use strict';

const NormalizedReviewApp = {
    _ignoredLessonKeys: new Set(),
    _rawRecords: [],
    _records: [],
    _filteredRecords: [],
    _lessonMeta: new Map(),
    _expandedLessons: new Set(),
    _dragState: null,
    _markerPickState: null,
    _filters: {
        search: '',
        course: '',
        presence: '',
        flaggedOnly: false,
        excludeAuto: false,
        borderlineMargin: 0.03,
    },

    init() {
        this._ignoredLessonKeys = this._loadIgnoredLessonKeys();
        this._els = {
            fileInput: document.getElementById('fileInput'),
            pickFileBtn: document.getElementById('pickFileBtn'),
            dropZone: document.getElementById('dropZone'),
            resetBtn: document.getElementById('resetBtn'),
            fileHint: document.getElementById('fileHint'),
            summaryGrid: document.getElementById('summaryGrid'),
            filtersPanel: document.getElementById('filtersPanel'),
            courseSelect: document.getElementById('courseSelect'),
            presenceSelect: document.getElementById('presenceSelect'),
            searchInput: document.getElementById('searchInput'),
            flaggedOnlyCheckbox: document.getElementById('flaggedOnlyCheckbox'),
            excludeAutoCheckbox: document.getElementById('excludeAutoCheckbox'),
            borderlineMargin: document.getElementById('borderlineMargin'),
            issuesPanel: document.getElementById('issuesPanel'),
            issuesGrid: document.getElementById('issuesGrid'),
            tablePanel: document.getElementById('tablePanel'),
            tableMeta: document.getElementById('tableMeta'),
            recordsBody: document.getElementById('recordsBody'),
        };

        this._wireUpload();
        this._wireFilters();
    },

    _wireUpload() {
        this._els.pickFileBtn.addEventListener('click', () => this._els.fileInput.click());
        this._els.fileInput.addEventListener('change', (event) => {
            const file = event.target.files && event.target.files[0];
            if (file) this._loadFile(file);
        });

        this._els.dropZone.addEventListener('click', (event) => {
            if (event.target.tagName !== 'BUTTON') {
                this._els.fileInput.click();
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
            if (file) this._loadFile(file);
        });

        this._els.resetBtn.addEventListener('click', () => this._reset());
    },

    _wireFilters() {
        this._els.searchInput.addEventListener('input', (event) => {
            this._filters.search = event.target.value.trim().toLowerCase();
            this._applyFilters();
        });

        this._els.courseSelect.addEventListener('change', (event) => {
            this._filters.course = event.target.value;
            this._applyFilters();
        });

        this._els.presenceSelect.addEventListener('change', (event) => {
            this._filters.presence = event.target.value;
            this._applyFilters();
        });

        this._els.flaggedOnlyCheckbox.addEventListener('change', (event) => {
            this._filters.flaggedOnly = event.target.checked;
            this._applyFilters();
        });

        this._els.excludeAutoCheckbox.addEventListener('change', (event) => {
            this._filters.excludeAuto = event.target.checked;
            this._applyFilters();
        });

        this._els.borderlineMargin.addEventListener('change', (event) => {
            this._filters.borderlineMargin = parseFloat(event.target.value || '0.03');
            this._records = this._annotateRecords(this._rawRecords);
            this._renderSummary();
            this._renderIssues();
            this._applyFilters();
        });
    },

    async _loadFile(file) {
        try {
            const text = await file.text();
            const ext = file.name.toLowerCase().split('.').pop();
            const parsed = ext === 'json'
                ? this._parseNormalizedJson(text)
                : this._parseNormalizedCsv(text);

            this._lessonMeta = parsed.lessonMeta || new Map();
            this._rawRecords = parsed.records;
            this._records = this._annotateRecords(parsed.records);

            this._els.fileHint.textContent = `${file.name} caricato. ${this._records.length} record pronti per la revisione.`;
            this._els.resetBtn.classList.remove('hidden');

            this._populateCourseFilter();
            this._showSections();
            this._renderSummary();
            this._renderIssues();
            this._applyFilters();
        } catch (error) {
            console.error(error);
            this._els.fileHint.textContent = `Errore caricamento file: ${error.message}`;
        }
    },

    _showSections() {
        this._els.summaryGrid.classList.remove('hidden');
        this._els.filtersPanel.classList.remove('hidden');
        this._els.issuesPanel.classList.remove('hidden');
        this._els.tablePanel.classList.remove('hidden');
    },

    _reset() {
        this._rawRecords = [];
        this._records = [];
        this._filteredRecords = [];
        this._lessonMeta = new Map();
        this._expandedLessons = new Set();
        this._ignoredLessonKeys = this._loadIgnoredLessonKeys();
        this._els.fileInput.value = '';
        this._els.fileHint.textContent = 'Formato consigliato: JSON v2 del motore Python. Il CSV resta solo come ingresso secondario leggibile da umani.';
        this._els.resetBtn.classList.add('hidden');
        this._els.summaryGrid.classList.add('hidden');
        this._els.filtersPanel.classList.add('hidden');
        this._els.issuesPanel.classList.add('hidden');
        this._els.tablePanel.classList.add('hidden');
        this._els.recordsBody.innerHTML = '';
        this._els.summaryGrid.innerHTML = '';
        this._els.issuesGrid.innerHTML = '';
    },

    _parseNormalizedJson(text) {
        const payload = JSON.parse(text);
        if (payload && payload.schema_version === 2 && Array.isArray(payload.courses)) {
            return this._flattenStructuredJson(payload);
        }
        throw new Error('JSON non riconosciuto: serve il formato canonico schema_version 2.');
    },

    _flattenStructuredJson(payload) {
        const records = [];
        const lessonMeta = new Map();
        let index = 0;

        for (const course of payload.courses || []) {
            for (const meeting of course.meetings || []) {
                const lessonKey = this._lessonKeyFromParts(course.course, meeting.date);
                lessonMeta.set(lessonKey, {
                    course: course.course,
                    date: meeting.date,
                    meetingId: meeting.meeting_id,
                    effectiveStart: meeting.effective_start,
                    breakPoint: meeting.break_point,
                    effectiveEnd: meeting.effective_end,
                    breakSource: meeting.break_source,
                    threshold: meeting.threshold,
                    trimStartMinutes: meeting.trim_start_minutes ?? 0,
                    trimEndMinutes: meeting.trim_end_minutes ?? 0,
                    participantCount: meeting.participant_count ?? 0,
                    summary: meeting.summary || {},
                    diagnostics: meeting.diagnostics || null,
                });

                for (const participant of meeting.participants || []) {
                    records.push(this._normalizeRecordFromObject({
                        course: course.course,
                        date: meeting.date,
                        meeting_id: meeting.meeting_id,
                        effective_start: meeting.effective_start,
                        break_point: meeting.break_point,
                        effective_end: meeting.effective_end,
                        threshold: meeting.threshold,
                        trim_end_minutes: meeting.trim_end_minutes,
                        break_source: meeting.break_source,
                        ...participant,
                    }, index++));
                }
            }
        }

        return { records, lessonMeta };
    },

    _parseNormalizedCsv(text) {
        const rows = this._parseCsvRows(text);
        if (rows.length < 2) {
            throw new Error('CSV vuoto o non valido.');
        }

        const headers = rows[0].map((value) => value.replace(/^\ufeff/, '').trim());
        const records = rows.slice(1)
            .filter((row) => row.some((cell) => (cell || '').trim() !== ''))
            .map((row, index) => {
                const record = {};
                headers.forEach((header, headerIndex) => {
                    record[header] = row[headerIndex] ?? '';
                });
                return this._normalizeRecordFromObject(record, index);
            });

        return {
            records,
            lessonMeta: new Map(),
        };
    },

    _normalizeRecordFromObject(raw, index) {
        const course = raw.Corso ?? raw.course ?? '';
        const date = raw.Data ?? raw.date ?? '';
        const firstName = raw.Nome ?? raw.first_name ?? raw.firstName ?? '';
        const lastName = raw.Cognome ?? raw.last_name ?? raw.lastName ?? '';
        const email = raw.Email ?? raw.email ?? '';
        const presence = raw.Presenza ?? raw.calculated_presence_status ?? raw.calculatedPresenceStatus ?? '';
        const minutesFirstHalf = this._toNumber(raw['Min Prima Meta'] ?? raw.minutes_first_half ?? raw.minutesFirstHalf);
        const minutesSecondHalf = this._toNumber(raw['Min Seconda Meta'] ?? raw.minutes_second_half ?? raw.minutesSecondHalf);
        const durationFirstHalf = this._toNumber(raw['Durata Prima Meta'] ?? raw.duration_first_half ?? raw.durationFirstHalf);
        const durationSecondHalf = this._toNumber(raw['Durata Seconda Meta'] ?? raw.duration_second_half ?? raw.durationSecondHalf);
        const totalMinutes = this._toNumber(raw['Minuti Totali'] ?? raw.total_minutes ?? raw.totalMinutes);
        const segmentCount = this._toNumber(raw.Segmenti ?? raw.segment_count ?? raw.segmentCount);
        const meetingId = raw['Meeting ID'] ?? raw.meeting_id ?? raw.meetingId ?? '';
        const effectiveStart = raw['Effective Start'] ?? raw.effective_start ?? raw.effectiveStart ?? '';
        const breakPoint = raw['Break Point'] ?? raw.break_point ?? raw.breakPoint ?? '';
        const effectiveEnd = raw['Effective End'] ?? raw.effective_end ?? raw.effectiveEnd ?? '';
        const threshold = this._toNumber(raw.Threshold ?? raw.threshold ?? raw.threshold_value ?? 0.8);
        const trimStartMinutes = this._toNumber(raw['Trim Start Minutes'] ?? raw.trim_start_minutes ?? raw.trimStartMinutes);
        const trimEndMinutes = this._toNumber(raw['Trim End Minutes'] ?? raw.trim_end_minutes ?? raw.trimEndMinutes);
        const breakSource = raw['Break Source'] ?? raw.break_source ?? raw.breakSource ?? '';

        return {
            _index: index,
            course,
            date,
            firstName,
            lastName,
            fullName: `${firstName} ${lastName}`.trim(),
            email,
            presence,
            minutesFirstHalf,
            minutesSecondHalf,
            durationFirstHalf,
            durationSecondHalf,
            totalMinutes,
            segmentCount,
            meetingId,
            effectiveStart,
            breakPoint,
            effectiveEnd,
            threshold,
            trimStartMinutes,
            trimEndMinutes,
            breakSource,
        };
    },

    _annotateRecords(records) {
        const duplicateMap = new Map();
        for (const record of records) {
            const key = [
                record.course.trim().toLowerCase(),
                record.date.trim().toLowerCase(),
                record.fullName.trim().toLowerCase(),
            ].join('|');
            duplicateMap.set(key, (duplicateMap.get(key) || 0) + 1);
        }

        return records.map((record) => {
            const pctFirst = this._calcPct(record.minutesFirstHalf, record.durationFirstHalf);
            const pctSecond = this._calcPct(record.minutesSecondHalf, record.durationSecondHalf);
            const threshold = record.threshold || 0.8;
            const nearFirst = this._isBorderline(pctFirst, record.durationFirstHalf, threshold);
            const nearSecond = this._isBorderline(pctSecond, record.durationSecondHalf, threshold);
            const duplicateKey = [
                record.course.trim().toLowerCase(),
                record.date.trim().toLowerCase(),
                record.fullName.trim().toLowerCase(),
            ].join('|');

            const flags = [];
            if (nearFirst || nearSecond) {
                flags.push({
                    key: 'borderline',
                    tone: 'warning',
                    label: `Borderline ${nearFirst && nearSecond ? '1ª/2ª' : nearFirst ? '1ª' : '2ª'} metà`,
                    review: true,
                });
            }
            if (record.breakSource !== 'auto') {
                flags.push({
                    key: 'split',
                    tone: 'info',
                    label: `Split ${record.breakSource || 'non auto'}`,
                    review: true,
                });
            }
            if (record.segmentCount > 2) {
                flags.push({
                    key: 'segments',
                    tone: 'alert',
                    label: `${record.segmentCount} segmenti`,
                    review: true,
                });
            }
            if (!record.email) {
                flags.push({
                    key: 'email',
                    tone: 'info',
                    label: 'Email assente',
                    review: false,
                });
            }
            if ((duplicateMap.get(duplicateKey) || 0) > 1) {
                flags.push({
                    key: 'duplicate',
                    tone: 'alert',
                    label: 'Nome duplicato nello stesso meeting',
                    review: true,
                });
            }

            const reviewFlags = flags.filter((flag) => flag.review !== false);

            return {
                ...record,
                pctFirst,
                pctSecond,
                flags,
                isFlagged: reviewFlags.length > 0,
                reviewFlags,
                duplicateCount: duplicateMap.get(duplicateKey) || 0,
            };
        });
    },

    _populateCourseFilter() {
        const courses = [...new Set(this._records
            .filter((record) => !this._isIgnoredRecord(record))
            .map((record) => record.course))].sort((a, b) => a.localeCompare(b, 'it'));
        let html = '<option value="">Tutti i corsi</option>';
        for (const course of courses) {
            html += `<option value="${this._escapeAttr(course)}">${this._escapeHtml(course)}</option>`;
        }
        this._els.courseSelect.innerHTML = html;
    },

    _renderSummary() {
        const total = this._records.length;
        const visibleRecords = this._records.filter((record) => !this._isIgnoredRecord(record));
        const courses = new Set(visibleRecords.map((record) => record.course)).size;
        const meetings = new Set(visibleRecords.map((record) => `${record.course}|${record.date}|${record.meetingId}`)).size;
        const borderline = visibleRecords.filter((record) => record.flags.some((flag) => flag.key === 'borderline')).length;
        const nonAuto = visibleRecords.filter((record) => record.breakSource !== 'auto').length;
        const fragmented = visibleRecords.filter((record) => record.segmentCount > 2).length;
        const duplicate = visibleRecords.filter((record) => record.flags.some((flag) => flag.key === 'duplicate')).length;
        const ignored = this._ignoredLessonKeys.size;

        this._els.summaryGrid.innerHTML = `
            <article class="summary-card info">
                <div class="summary-label">Record</div>
                <div class="summary-value">${visibleRecords.length}</div>
                <div class="summary-detail">Righe attive su ${total} caricate</div>
            </article>
            <article class="summary-card success">
                <div class="summary-label">Corsi</div>
                <div class="summary-value">${courses}</div>
                <div class="summary-detail">Corsi distinti nel file</div>
            </article>
            <article class="summary-card info">
                <div class="summary-label">Meeting</div>
                <div class="summary-value">${meetings}</div>
                <div class="summary-detail">Lezioni o sessioni distinte</div>
            </article>
            <article class="summary-card warning">
                <div class="summary-label">Borderline</div>
                <div class="summary-value">${borderline}</div>
                <div class="summary-detail">Vicini alla soglia attuale</div>
            </article>
            <article class="summary-card warning">
                <div class="summary-label">Split non auto</div>
                <div class="summary-value">${nonAuto}</div>
                <div class="summary-detail">Midpoint o manuale</div>
            </article>
            <article class="summary-card alert">
                <div class="summary-label">Segmentati</div>
                <div class="summary-value">${fragmented}</div>
                <div class="summary-detail">Più di 2 segmenti</div>
            </article>
            <article class="summary-card alert">
                <div class="summary-label">Duplicati</div>
                <div class="summary-value">${duplicate}</div>
                <div class="summary-detail">Stesso nome nello stesso meeting</div>
            </article>
            <article class="summary-card info">
                <div class="summary-label">Ignorati</div>
                <div class="summary-value">${ignored}</div>
                <div class="summary-detail">Lezioni escluse dalla review</div>
            </article>
        `;
    },

    _renderIssues() {
        const visibleRecords = this._records.filter((record) => !this._isIgnoredRecord(record));
        const borderline = visibleRecords.filter((record) => record.flags.some((flag) => flag.key === 'borderline')).length;
        const nonAuto = visibleRecords.filter((record) => record.breakSource !== 'auto').length;
        const fragmented = visibleRecords.filter((record) => record.segmentCount > 2).length;
        const missingEmail = visibleRecords.filter((record) => !record.email).length;
        const duplicate = visibleRecords.filter((record) => record.flags.some((flag) => flag.key === 'duplicate')).length;

        this._els.issuesGrid.innerHTML = `
            <article class="issue-box warning">
                <h3>Vicini alla soglia</h3>
                <div class="issue-count">${borderline}</div>
                <p>Persone a pochi punti percentuali dal limite. Sono i casi in cui il giudizio umano spesso fa la differenza.</p>
            </article>
            <article class="issue-box info">
                <h3>Split da controllare</h3>
                <div class="issue-count">${nonAuto}</div>
                <p>Meeting in cui il giallo non è uscito da un detector automatico, ma da midpoint o in futuro da correzione manuale.</p>
            </article>
            <article class="issue-box alert">
                <h3>Sessioni spezzate</h3>
                <div class="issue-count">${fragmented}</div>
                <p>Partecipanti entrati e usciti molte volte. Tipicamente sono i casi più rumorosi e difficili da leggere.</p>
            </article>
            <article class="issue-box success">
                <h3>Email mancanti</h3>
                <div class="issue-count">${missingEmail}</div>
                <p>Nome e cognome vanno bene per leggere, ma senza email il matching futuro sarà più fragile.</p>
            </article>
            <article class="issue-box alert">
                <h3>Duplicati nello stesso meeting</h3>
                <div class="issue-count">${duplicate}</div>
                <p>Stesso nome nello stesso corso e data: spesso è un indizio di entrate multiple o anagrafica sporca.</p>
            </article>
        `;
    },

    _applyFilters() {
        this._filteredRecords = this._records.filter((record) => {
            if (this._isIgnoredRecord(record)) return false;
            if (this._filters.course && record.course !== this._filters.course) return false;
            if (this._filters.presence && record.presence !== this._filters.presence) return false;
            if (this._filters.flaggedOnly && !record.isFlagged) return false;
            if (this._filters.excludeAuto && record.breakSource === 'auto') return false;

            if (this._filters.search) {
                const haystack = [
                    record.course,
                    record.date,
                    record.fullName,
                    record.email,
                    record.meetingId,
                    record.breakSource,
                ].join(' ').toLowerCase();
                if (!haystack.includes(this._filters.search)) return false;
            }
            return true;
        });

        this._renderTable();
    },

    _applyThresholdOverride(lessonKey, nextThreshold) {
        const lessonMeta = this._lessonMeta.get(lessonKey);
        if (!lessonMeta) return;

        lessonMeta.threshold = nextThreshold;
        lessonMeta.localThresholdOverride = true;

        for (const record of this._rawRecords) {
            if (this._lessonKeyFor(record) !== lessonKey) continue;
            record.threshold = nextThreshold;
            record.presence = this._determinePresenceStatus(
                record.minutesFirstHalf,
                record.minutesSecondHalf,
                record.durationFirstHalf,
                record.durationSecondHalf,
                nextThreshold,
            );
        }

        const lessonRecords = this._rawRecords.filter((record) => this._lessonKeyFor(record) === lessonKey);
        lessonMeta.summary = this._buildLessonSummaryFromRecords(lessonRecords);

        this._records = this._annotateRecords(this._rawRecords);
        this._renderSummary();
        this._renderIssues();
        this._applyFilters();
    },

    _renderTable() {
        if (this._filteredRecords.length === 0) {
            this._els.recordsBody.innerHTML = '<tr><td colspan="3" class="muted">Nessun record corrisponde ai filtri correnti.</td></tr>';
            this._els.tableMeta.innerHTML = this._buildTableMetaHtml(0);
            this._wireTableMetaActions();
            return;
        }

        const groups = this._groupByLesson(this._filteredRecords);
        let html = '';

        for (const [lessonKey, lesson] of groups) {
            const { course, date, records } = lesson;
            const flaggedCount = records.filter((record) => record.isFlagged).length;
            const lessonMeta = this._lessonMeta.get(lessonKey);
            const ignoreKey = lessonMeta
                ? this._ignoreKeyForLessonMeta(lessonMeta)
                : this._ignoreKeyForRecord(records[0]);
            const rows = records.map((record) => {
                const classes = [];
                if (record.isFlagged) classes.push('flagged');

                return `
                    <tr class="${classes.join(' ')}">
                        <td class="person-cell">${this._buildPersonCell(record)}</td>
                        <td class="half-cell">${this._buildHalfCell(record, 'first')}</td>
                        <td class="half-cell">${this._buildHalfCell(record, 'second')}</td>
                    </tr>
                `;
            }).join('');

            html += `
                <div class="course-group ${this._expandedLessons.has(lessonKey) ? 'expanded' : ''}" data-lesson-key="${this._escapeAttr(lessonKey)}">
                    <div class="course-group-header" data-lesson-key="${this._escapeAttr(lessonKey)}">
                        <div class="course-group-summary">
                            <div class="course-group-title">${this._escapeHtml(course || '(senza corso)')}</div>
                            <div class="course-group-meta">${this._escapeHtml(this._formatDate(date))} · ${records.length} persone · ${flaggedCount} da rivedere</div>
                        </div>
                        <div class="course-group-actions">
                            <button type="button" class="lesson-ignore-button" data-action="ignore-lesson" data-ignore-key="${this._escapeAttr(ignoreKey)}" title="Ignora questa lezione">×</button>
                        </div>
                        <div class="course-group-overview">${records.map((record) => this._buildLessonPersonToken(record)).join('')}</div>
                    </div>
                    <div class="course-group-body">
                    ${this._buildMeetingDiagnostics(lessonMeta, records)}
                    <div class="table-wrap">
                        <table>
                            <thead>
                                <tr>
                                    <th>Persona</th>
                                    <th>Prima metà</th>
                                    <th>Seconda metà</th>
                                </tr>
                            </thead>
                            <tbody>${rows}</tbody>
                        </table>
                    </div>
                    </div>
                </div>
            `;
        }

        this._els.recordsBody.innerHTML = `<tr><td colspan="3" style="padding:0;border:none;background:transparent;"><div>${html}</div></td></tr>`;
        this._els.tableMeta.innerHTML = this._buildTableMetaHtml(this._filteredRecords.length);
        this._wireTableMetaActions();

        this._els.recordsBody.querySelectorAll('.course-group-header').forEach((header) => {
            header.addEventListener('click', () => {
                const lessonKey = header.dataset.lessonKey;
                if (this._expandedLessons.has(lessonKey)) {
                    this._expandedLessons.delete(lessonKey);
                } else {
                    this._expandedLessons.add(lessonKey);
                }
                this._renderTable();
            });
        });

        this._els.recordsBody.querySelectorAll('[data-action=\"edit-threshold\"]').forEach((node) => {
            node.addEventListener('click', (event) => {
                event.preventDefault();
                event.stopPropagation();
                const lessonKey = node.dataset.lessonKey;
                const lessonMeta = this._lessonMeta.get(lessonKey);
                if (!lessonMeta) return;

                const currentPct = Math.round((lessonMeta.threshold || 0.8) * 100);
                const rawValue = window.prompt('Nuova soglia per questa lezione (es. 75 o 0.75)', String(currentPct));
                if (rawValue == null) return;

                const parsed = this._parseThresholdInput(rawValue);
                if (parsed == null) {
                    window.alert('Valore threshold non valido. Usa per esempio 75 oppure 0.75');
                    return;
                }

                this._applyThresholdOverride(lessonKey, parsed);
            });
        });

        this._els.recordsBody.querySelectorAll('[data-action=\"ignore-lesson\"]').forEach((node) => {
            node.addEventListener('click', (event) => {
                event.preventDefault();
                event.stopPropagation();
                const ignoreKey = node.dataset.ignoreKey;
                if (!ignoreKey) return;
                this._ignoredLessonKeys.add(ignoreKey);
                this._saveIgnoredLessonKeys();
                this._populateCourseFilter();
                this._renderSummary();
                this._renderIssues();
                this._applyFilters();
            });
        });

        this._els.recordsBody.querySelectorAll('[data-action=\"arm-marker-pick\"]').forEach((node) => {
            node.addEventListener('click', (event) => {
                event.preventDefault();
                event.stopPropagation();
                const lessonKey = node.dataset.lessonKey;
                const markerType = node.dataset.markerType;
                if (!lessonKey || !markerType) return;
                this._markerPickState = { lessonKey, markerType };
                this._expandedLessons.add(lessonKey);
                this._renderTable();
            });
        });

        this._els.recordsBody.querySelectorAll('[data-action=\"place-marker\"]').forEach((node) => {
            node.addEventListener('click', (event) => {
                if (!this._markerPickState) return;
                const lessonKey = node.dataset.lessonKey;
                if (lessonKey !== this._markerPickState.lessonKey) return;
                event.preventDefault();
                event.stopPropagation();
                this._applyMarkerFromClientX(lessonKey, this._markerPickState.markerType, node, event.clientX);
                this._markerPickState = null;
                this._renderTable();
            });
        });

        this._els.recordsBody.querySelectorAll('[data-drag-marker]').forEach((node) => {
            node.addEventListener('pointerdown', (event) => {
                this._startMarkerDrag(event, node);
            });
        });
    },

    _wireTableMetaActions() {
        this._els.tableMeta.querySelectorAll('[data-action=\"clear-ignored-lessons\"]').forEach((node) => {
            node.addEventListener('click', (event) => {
                event.preventDefault();
                this._ignoredLessonKeys.clear();
                this._saveIgnoredLessonKeys();
                this._populateCourseFilter();
                this._renderSummary();
                this._renderIssues();
                this._applyFilters();
            });
        });
    },

    _groupByLesson(records) {
        const groups = new Map();
        for (const record of records) {
            const key = this._lessonKeyFor(record);
            if (!groups.has(key)) {
                groups.set(key, {
                    course: record.course || '',
                    date: record.date || '',
                    records: [],
                });
            }
            groups.get(key).records.push(record);
        }
        return new Map(
            [...groups.entries()].sort((a, b) => {
                const left = `${a[1].course}|${a[1].date}`;
                const right = `${b[1].course}|${b[1].date}`;
                return left.localeCompare(right, 'it');
            })
        );
    },

    _buildTableMetaHtml(visibleCount) {
        const ignoredCount = this._ignoredLessonKeys.size;
        const restoreHtml = ignoredCount > 0
            ? `<button type="button" class="meta-action-button" data-action="clear-ignored-lessons">Ripristina ignorati</button>`
            : '';
        return `
            <span>${visibleCount} record visibili su ${this._records.length}.${ignoredCount > 0 ? ` ${ignoredCount} lezioni ignorate.` : ''}</span>
            ${restoreHtml}
        `;
    },

    _startMarkerDrag(event, node) {
        event.preventDefault();
        event.stopPropagation();
        const lessonKey = node.dataset.lessonKey;
        const markerType = node.dataset.dragMarker;
        const lessonMeta = this._lessonMeta.get(lessonKey);
        if (!lessonKey || !markerType || !lessonMeta) return;

        this._dragState = {
            lessonKey,
            markerType,
            pointerId: event.pointerId,
        };

        document.addEventListener('pointermove', this._boundHandleMarkerDrag ??= (moveEvent) => {
            this._handleMarkerDrag(moveEvent);
        });
        document.addEventListener('pointerup', this._boundStopMarkerDrag ??= (upEvent) => {
            this._stopMarkerDrag(upEvent);
        });
        document.addEventListener('pointercancel', this._boundStopMarkerDrag);
    },

    _handleMarkerDrag(event) {
        if (!this._dragState) return;
        if (event.pointerId !== this._dragState.pointerId) return;
        const { lessonKey, markerType } = this._dragState;
        const chart = this._els.recordsBody.querySelector(`.meeting-chart[data-lesson-key="${CSS.escape(lessonKey)}"]`);
        if (!chart) return;
        this._applyMarkerFromClientX(lessonKey, markerType, chart, event.clientX);
        this._renderTable();
    },

    _applyMarkerFromClientX(lessonKey, markerType, chart, clientX) {
        const lessonMeta = this._lessonMeta.get(lessonKey);
        if (!lessonMeta || !chart) return;
        const diagnostics = lessonMeta.diagnostics || {};
        const meetingStart = diagnostics.meeting_start || lessonMeta.effectiveStart;
        const meetingEnd = diagnostics.meeting_end || lessonMeta.effectiveEnd;
        const rect = chart.getBoundingClientRect();
        const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
        const candidateIso = this._isoFromRatio(meetingStart, meetingEnd, ratio);
        if (!candidateIso) return;

        const currentState = {
            effectiveStart: lessonMeta.effectiveStart,
            breakPoint: lessonMeta.breakPoint,
            effectiveEnd: lessonMeta.effectiveEnd,
            ...(lessonMeta.localMarkerOverride || {}),
        };

        if (markerType === 'start') {
            currentState.effectiveStart = this._clampMarkerIso(
                candidateIso,
                meetingStart,
                currentState.breakPoint,
                5
            );
        } else if (markerType === 'break') {
            currentState.breakPoint = this._clampMarkerIso(
                candidateIso,
                currentState.effectiveStart,
                currentState.effectiveEnd,
                5
            );
        } else if (markerType === 'end') {
            currentState.effectiveEnd = this._clampMarkerIso(
                candidateIso,
                currentState.breakPoint,
                meetingEnd,
                5
            );
        } else {
            return;
        }

        lessonMeta.localMarkerOverride = currentState;
    },

    _stopMarkerDrag(event) {
        if (!this._dragState) return;
        if (event && event.pointerId != null && event.pointerId !== this._dragState.pointerId) return;
        this._dragState = null;
        document.removeEventListener('pointermove', this._boundHandleMarkerDrag);
        document.removeEventListener('pointerup', this._boundStopMarkerDrag);
        document.removeEventListener('pointercancel', this._boundStopMarkerDrag);
    },

    _buildFlagHtml(flags, expanded = false) {
        if (!flags || flags.length === 0) {
            return expanded ? '<span class="flag success">Nessun flag</span>' : '<span class="muted">-</span>';
        }
        return flags.map((flag) => `<span class="flag ${flag.tone}">${this._escapeHtml(flag.label)}</span>`).join(expanded ? '' : ' ');
    },

    _buildPersonCell(record) {
        const emailHtml = record.email ? ` (${this._escapeHtml(record.email)})` : '';
        const flagsHtml = record.flags.length > 0
            ? `<div class="flag-stack">${this._buildFlagHtml(record.flags)}</div>`
            : '';

        return `
            <div class="person-name">${this._escapeHtml(record.fullName || '(senza nome)')}${emailHtml}</div>
            <div class="person-meta">
                ${this._escapeHtml(record.course)}<br>
                ${this._escapeHtml(this._formatDate(record.date))} · ${this._escapeHtml(this._presenceLabel(record.presence))}
            </div>
            ${flagsHtml}
        `;
    },

    _buildHalfCell(record, side) {
        const pct = side === 'first' ? record.pctFirst : record.pctSecond;
        const minutes = side === 'first' ? record.minutesFirstHalf : record.minutesSecondHalf;
        const duration = side === 'first' ? record.durationFirstHalf : record.durationSecondHalf;
        const threshold = record.threshold || 0.8;
        const thresholdPct = Math.round(threshold * 100);
        const deltaValue = Math.round((pct - threshold) * 100);
        const deltaClass = deltaValue >= 0 ? 'positive' : 'negative';
        const deltaText = `${deltaValue > 0 ? '+' : ''}${deltaValue}`;

        return `
            <div class="delta ${deltaClass}">${deltaText}</div>
            <div class="half-detail">
                ${this._formatPct(pct)} su ${thresholdPct}%<br>
                ${minutes.toFixed(1)} / ${duration.toFixed(1)} min
            </div>
        `;
    },

    _buildLessonPersonToken(record) {
        const firstDelta = Math.round((record.pctFirst - (record.threshold || 0.8)) * 100);
        const secondDelta = Math.round((record.pctSecond - (record.threshold || 0.8)) * 100);
        const tooltip = [
            `${record.fullName || '(senza nome)'}${record.email ? ` (${record.email})` : ''}`,
            `1ª metà: ${this._formatPct(record.pctFirst)} (${firstDelta > 0 ? '+' : ''}${firstDelta})`,
            `2ª metà: ${this._formatPct(record.pctSecond)} (${secondDelta > 0 ? '+' : ''}${secondDelta})`,
        ].join('\n');
        const threshold = record.threshold || 0.8;
        return `
            <span class="lesson-person" title="${this._escapeAttr(tooltip)}">
                <span class="lesson-person-name">${this._escapeHtml(record.fullName || '(senza nome)')}</span>
                <span class="lesson-dots">
                    <span class="lesson-dot ${this._dotClass(record.pctFirst, threshold, record.durationFirstHalf)}"></span>
                    <span class="lesson-dot ${this._dotClass(record.pctSecond, threshold, record.durationSecondHalf)}"></span>
                </span>
            </span>
        `;
    },

    _buildMeetingDiagnostics(lessonMeta, records) {
        if (!lessonMeta) {
            return `
                <div class="meeting-diagnostics empty">
                    <div class="meeting-diagnostics-note">
                        Diagnostica meeting non disponibile: con il CSV vedi il risultato, ma non il profilo temporale della lezione. Per questo blocco conviene caricare il JSON v2.
                    </div>
                </div>
            `;
        }

        const diagnostics = lessonMeta.diagnostics || {};
        const markerState = lessonMeta.localMarkerOverride || {};
        const timeline = diagnostics.timeline || [];
        const peak = diagnostics.peak_active_count || Math.max(...timeline.map((point) => point.active_count), 1);
        const bars = timeline.length > 0
            ? timeline.map((point) => this._buildTimelineBar(point, peak)).join('')
            : '<div class="meeting-diagnostics-note">Timeline non disponibile per questa lezione.</div>';

        const meetingStart = diagnostics.meeting_start || lessonMeta.effectiveStart;
        const meetingEnd = diagnostics.meeting_end || lessonMeta.effectiveEnd;
        const effectiveStartValue = markerState.effectiveStart || lessonMeta.effectiveStart;
        const breakPointValue = markerState.breakPoint || lessonMeta.breakPoint;
        const effectiveEndValue = markerState.effectiveEnd || lessonMeta.effectiveEnd;
        const markerMeetingStart = this._markerPosition(meetingStart, meetingStart, meetingEnd);
        const markerStart = this._markerPosition(effectiveStartValue, meetingStart, meetingEnd);
        const markerBreak = this._markerPosition(breakPointValue, meetingStart, meetingEnd);
        const markerEnd = this._markerPosition(effectiveEndValue, meetingStart, meetingEnd);
        const markerMeetingEnd = this._markerPosition(meetingEnd, meetingStart, meetingEnd);
        const trimStartMinutes = diagnostics.trim_start_minutes ?? lessonMeta.trimStartMinutes ?? 0;
        const trimEndMinutes = diagnostics.trim_end_minutes ?? lessonMeta.trimEndMinutes ?? 0;
        const effectiveStartSource = diagnostics.effective_start_source || 'snap';
        const effectiveEndSource = diagnostics.effective_end_source || 'meeting_end';
        const suggestedStart = diagnostics.suggested_effective_start || null;
        const suggestedEnd = diagnostics.suggested_effective_end || null;
        const suggestionConfidence = diagnostics.suggestion_confidence || null;
        const thresholdPct = Math.round((lessonMeta.threshold || 0.8) * 100);
        const thresholdOverrideNote = lessonMeta.localThresholdOverride ? ' · override locale' : '';
        const summary = lessonMeta.summary || {};
        const diagnosisText = lessonMeta.breakSource === 'auto'
            ? 'Pausa rilevata automaticamente dal profilo dei presenti.'
            : lessonMeta.breakSource === 'midpoint'
                ? 'Pausa non trovata: il giallo è stato messo a metà esatta del tempo utile.'
                : `Pausa impostata con criterio ${lessonMeta.breakSource}.`;
        const suggestionText = (suggestedStart || suggestedEnd)
            ? `Suggerimento ${suggestionConfidence || 'medio'}: ${suggestedStart ? `inizio ${this._formatTime(suggestedStart)}` : 'inizio ok'}${suggestedStart && suggestedEnd ? ' · ' : ''}${suggestedEnd ? `fine ${this._formatTime(suggestedEnd)}` : 'fine ok'}.`
            : 'Nessun suggerimento automatico di inizio/fine: il profilo sembra già coerente oppure poco leggibile.';
        const proposalHtml = this._buildMarkerProposalHtml(lessonMeta, meetingStart, meetingEnd);
        const lessonKey = this._lessonKeyFromParts(lessonMeta.course, lessonMeta.date);
        const isPicking = this._markerPickState && this._markerPickState.lessonKey === lessonKey;
        const pickLabel = isPicking
            ? ({ start: 'inizio utile', break: 'pausa', end: 'fine utile' }[this._markerPickState.markerType] || 'marker')
            : null;

        return `
            <div class="meeting-diagnostics">
                <div class="meeting-diagnostics-head">
                    <div class="meeting-diagnostics-stats">
                        <div class="diag-stat">
                            <span class="diag-k">Meeting</span>
                            <span class="diag-v">${this._escapeHtml(lessonMeta.meetingId || '-')}</span>
                        </div>
                        <div class="diag-stat">
                            <span class="diag-k">Threshold</span>
                            <span class="diag-v"><button type="button" class="diag-button" data-action="edit-threshold" data-lesson-key="${this._escapeAttr(this._lessonKeyFromParts(lessonMeta.course, lessonMeta.date))}">${thresholdPct}%</button>${this._escapeHtml(thresholdOverrideNote)}</span>
                        </div>
                        <div class="diag-stat">
                            <span class="diag-k">Picco presenti</span>
                            <span class="diag-v">${peak}</span>
                        </div>
                        <div class="diag-stat">
                            <span class="diag-k">Ritardo inizio</span>
                            <span class="diag-v">${trimStartMinutes > 0 ? `${trimStartMinutes} min` : 'no'} · ${this._escapeHtml(effectiveStartSource)}</span>
                        </div>
                        <div class="diag-stat">
                            <span class="diag-k">Coda tagliata</span>
                            <span class="diag-v">${trimEndMinutes > 0 ? `${trimEndMinutes} min` : 'no'} · ${this._escapeHtml(effectiveEndSource)}</span>
                        </div>
                        <div class="diag-stat">
                            <span class="diag-k">Suggest inizio</span>
                            <span class="diag-v">${suggestedStart ? this._escapeHtml(this._formatTime(suggestedStart)) : 'no'}</span>
                        </div>
                        <div class="diag-stat">
                            <span class="diag-k">Suggest fine</span>
                            <span class="diag-v">${suggestedEnd ? this._escapeHtml(this._formatTime(suggestedEnd)) : 'no'}</span>
                        </div>
                    </div>
                    <div class="meeting-diagnostics-summary">
                        <span class="diag-pill success">Presente ${summary.presente || 0}</span>
                        <span class="diag-pill info">1ª metà ${summary.prima_meta || 0}</span>
                        <span class="diag-pill warning">2ª metà ${summary.seconda_meta || 0}</span>
                        <span class="diag-pill alert">Assente ${summary.assente || 0}</span>
                    </div>
                </div>
                <div class="marker-edit-row">
                    <span class="marker-edit-label">Imposta</span>
                    <button type="button" class="marker-action-button" data-action="arm-marker-pick" data-marker-type="start" data-lesson-key="${this._escapeAttr(lessonKey)}">inizio</button>
                    <button type="button" class="marker-action-button" data-action="arm-marker-pick" data-marker-type="break" data-lesson-key="${this._escapeAttr(lessonKey)}">pausa</button>
                    <button type="button" class="marker-action-button" data-action="arm-marker-pick" data-marker-type="end" data-lesson-key="${this._escapeAttr(lessonKey)}">fine</button>
                </div>
                <div class="meeting-diagnostics-note">${this._escapeHtml(diagnosisText)}</div>
                <div class="meeting-diagnostics-note">${this._escapeHtml(suggestionText)}</div>
                ${isPicking ? `<div class="meeting-diagnostics-note picking-note">Clicca sulla timeline per impostare ${this._escapeHtml(pickLabel)}.</div>` : ''}
                <div class="meeting-chart ${isPicking ? 'picking' : ''}" data-action="place-marker" data-lesson-key="${this._escapeAttr(lessonKey)}">
                    <div class="meeting-bars">${bars}</div>
                    <div class="meeting-markers">
                        <div class="meeting-marker zoom-start" style="left:${markerMeetingStart}%">
                            <span>Inizio Zoom</span>
                            <strong>${this._escapeHtml(this._formatTime(meetingStart))}</strong>
                        </div>
                        <div class="meeting-marker start" style="left:${markerStart}%">
                            <span>Inizio utile</span>
                            <strong>${this._escapeHtml(this._formatTime(effectiveStartValue))}</strong>
                        </div>
                        <div class="meeting-marker break" style="left:${markerBreak}%">
                            <span>Pausa</span>
                            <strong>${this._escapeHtml(this._formatTime(breakPointValue))}</strong>
                        </div>
                        <div class="meeting-marker end" style="left:${markerEnd}%">
                            <span>Fine utile</span>
                            <strong>${this._escapeHtml(this._formatTime(effectiveEndValue))}</strong>
                        </div>
                        <div class="meeting-marker zoom-end" style="left:${markerMeetingEnd}%">
                            <span>Fine Zoom</span>
                            <strong>${this._escapeHtml(this._formatTime(meetingEnd))}</strong>
                        </div>
                    </div>
                    <div class="meeting-axis">
                        <span>${this._escapeHtml(this._formatTime(meetingStart))}</span>
                        <span>${this._escapeHtml(this._formatTime(meetingEnd))}</span>
                    </div>
                </div>
                ${proposalHtml}
            </div>
        `;
    },

    _buildMarkerProposalHtml(lessonMeta, meetingStart, meetingEnd) {
        const markerState = lessonMeta.localMarkerOverride;
        if (!markerState) {
            return `
                <div class="marker-proposal muted">
                    Puoi impostare <strong>inizio</strong>, <strong>pausa</strong> o <strong>fine</strong> cliccando prima il comando e poi la timeline. La vista non ricalcola ancora le presenze: genera solo la proposta.
                </div>
            `;
        }

        const startValue = markerState.effectiveStart || lessonMeta.effectiveStart;
        const breakValue = markerState.breakPoint || lessonMeta.breakPoint;
        const endValue = markerState.effectiveEnd || lessonMeta.effectiveEnd;
        const trimStart = Math.max(0, this._minutesBetweenIso(lessonMeta.effectiveStart, startValue));
        const trimEnd = Math.max(0, this._minutesBetweenIso(endValue, meetingEnd));
        const payload = {
            course: lessonMeta.course,
            date: lessonMeta.date,
            meeting_id: lessonMeta.meetingId,
            trim_start_minutes: Number(trimStart.toFixed(1)),
            break_point: breakValue,
            trim_end_minutes: Number(trimEnd.toFixed(1)),
        };

        return `
            <div class="marker-proposal active">
                <div class="marker-proposal-title">Override locale proposto</div>
                <div class="marker-proposal-copy">Inizio ${this._escapeHtml(this._formatTime(startValue))} · Pausa ${this._escapeHtml(this._formatTime(breakValue))} · Fine ${this._escapeHtml(this._formatTime(endValue))} · Ritardo ${trimStart.toFixed(1)} min · Taglio finale ${trimEnd.toFixed(1)} min</div>
                <pre class="marker-proposal-code">${this._escapeHtml(JSON.stringify(payload, null, 2))}</pre>
            </div>
        `;
    },

    _buildTimelineBar(point, peak) {
        const ratio = peak > 0 ? point.active_count / peak : 0;
        const height = Math.max(10, Math.round(ratio * 88));
        const tooltip = `${this._formatDateTime(point.timestamp)} · ${point.active_count} presenti`;
        return `<span class="meeting-bar" style="height:${height}px" title="${this._escapeAttr(tooltip)}"></span>`;
    },

    _markerPosition(value, start, end) {
        const startMs = new Date(start).getTime();
        const endMs = new Date(end).getTime();
        const valueMs = new Date(value).getTime();
        if (!Number.isFinite(startMs) || !Number.isFinite(endMs) || endMs <= startMs || !Number.isFinite(valueMs)) {
            return 0;
        }
        return Math.max(0, Math.min(100, ((valueMs - startMs) / (endMs - startMs)) * 100));
    },

    _isoFromRatio(start, end, ratio) {
        const startMs = new Date(start).getTime();
        const endMs = new Date(end).getTime();
        if (!Number.isFinite(startMs) || !Number.isFinite(endMs) || endMs <= startMs) {
            return null;
        }
        const valueMs = startMs + ((endMs - startMs) * ratio);
        const snappedMs = Math.round(valueMs / 60000) * 60000;
        return this._toLocalIsoString(new Date(snappedMs));
    },

    _clampMarkerIso(candidate, lowerBound, upperBound, marginMinutes = 0) {
        const lowerMs = new Date(lowerBound).getTime();
        const upperMs = new Date(upperBound).getTime();
        const candidateMs = new Date(candidate).getTime();
        if (![lowerMs, upperMs, candidateMs].every(Number.isFinite)) {
            return candidate;
        }

        const marginMs = marginMinutes * 60000;
        const minValue = lowerMs + marginMs;
        const maxValue = upperMs - marginMs;
        const clamped = maxValue <= minValue
            ? Math.max(lowerMs, Math.min(upperMs, candidateMs))
            : Math.max(minValue, Math.min(maxValue, candidateMs));
        return this._toLocalIsoString(new Date(clamped));
    },

    _minutesBetweenIso(start, end) {
        const startMs = new Date(start).getTime();
        const endMs = new Date(end).getTime();
        if (!Number.isFinite(startMs) || !Number.isFinite(endMs)) return 0;
        return (endMs - startMs) / 60000;
    },

    _toLocalIsoString(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        const seconds = String(date.getSeconds()).padStart(2, '0');
        return `${year}-${month}-${day}T${hours}:${minutes}:${seconds}`;
    },

    _dotClass(pct, threshold = 0.8, duration = 1) {
        if (pct >= threshold) return 'positive';
        if (this._isBorderline(pct, duration, threshold)) return 'borderline';
        return 'negative';
    },

    _lessonKeyFor(record) {
        return `${record.course || ''}|${record.date || ''}`;
    },

    _lessonKeyFromParts(course, date) {
        return `${course || ''}|${date || ''}`;
    },

    _lessonIdentityKey(course, date, meetingId) {
        return [
            String(course || '').trim().toLowerCase(),
            String(date || '').trim().toLowerCase(),
            String(meetingId || '').trim().toLowerCase(),
        ].join('|');
    },

    _ignoreKeyForRecord(record) {
        return this._lessonIdentityKey(record.course, record.date, record.meetingId);
    },

    _ignoreKeyForLessonMeta(lessonMeta) {
        if (lessonMeta) {
            return this._lessonIdentityKey(lessonMeta.course, lessonMeta.date, lessonMeta.meetingId);
        }
        return '';
    },

    _isIgnoredRecord(record) {
        return this._ignoredLessonKeys.has(this._ignoreKeyForRecord(record));
    },

    _loadIgnoredLessonKeys() {
        try {
            const raw = window.localStorage.getItem('normalizedReview.ignoredLessons');
            if (!raw) return new Set();
            const parsed = JSON.parse(raw);
            if (!Array.isArray(parsed)) return new Set();
            return new Set(parsed.filter((value) => typeof value === 'string' && value.trim() !== ''));
        } catch (error) {
            console.warn('Impossibile leggere gli ignorati salvati.', error);
            return new Set();
        }
    },

    _saveIgnoredLessonKeys() {
        try {
            window.localStorage.setItem(
                'normalizedReview.ignoredLessons',
                JSON.stringify([...this._ignoredLessonKeys].sort())
            );
        } catch (error) {
            console.warn('Impossibile salvare gli ignorati.', error);
        }
    },

    _calcPct(minutes, duration) {
        if (!duration || duration <= 0) return 0;
        return minutes / duration;
    },

    _isBorderline(pct, duration, threshold = 0.8) {
        if (!duration || duration <= 0) return false;
        return pct < threshold && (threshold - pct) <= this._filters.borderlineMargin;
    },

    _parseThresholdInput(value) {
        const normalized = String(value ?? '').trim().replace(',', '.');
        if (!normalized) return null;
        let parsed = parseFloat(normalized);
        if (!Number.isFinite(parsed) || parsed <= 0) return null;
        if (parsed > 1) parsed = parsed / 100;
        if (parsed <= 0 || parsed > 1) return null;
        return parsed;
    },

    _determinePresenceStatus(minutesFirst, minutesSecond, durationFirst, durationSecond, threshold) {
        const pctFirst = this._calcPct(minutesFirst, durationFirst);
        const pctSecond = this._calcPct(minutesSecond, durationSecond);
        const firstPresent = durationFirst > 0 && pctFirst >= threshold;
        const secondPresent = durationSecond > 0 && pctSecond >= threshold;

        if (firstPresent && secondPresent) return 'presente';
        if (firstPresent) return 'prima_meta';
        if (secondPresent) return 'seconda_meta';
        return 'assente';
    },

    _buildLessonSummaryFromRecords(records) {
        const summary = { presente: 0, prima_meta: 0, seconda_meta: 0, assente: 0 };
        for (const record of records) {
            summary[record.presence] = (summary[record.presence] || 0) + 1;
        }
        return summary;
    },

    _toNumber(value) {
        const parsed = parseFloat(String(value ?? '').replace(',', '.'));
        return Number.isFinite(parsed) ? parsed : 0;
    },

    _presenceLabel(value) {
        return {
            presente: 'Presente',
            prima_meta: 'Prima metà',
            seconda_meta: 'Seconda metà',
            assente: 'Assente',
        }[value] || value || '-';
    },

    _formatPct(value) {
        return `${Math.round(value * 100)}%`;
    },

    _formatDate(value) {
        if (!value) return '-';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return value;
        return date.toLocaleDateString('it-IT');
    },

    _formatTime(value) {
        if (!value) return '-';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return value;
        return date.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' });
    },

    _formatDateTime(value) {
        if (!value) return '-';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return value;
        return date.toLocaleString('it-IT', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        });
    },

    _escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    },

    _escapeAttr(value) {
        return this._escapeHtml(value);
    },

    _parseCsvRows(text) {
        const rows = [];
        let row = [];
        let current = '';
        let inQuotes = false;

        for (let index = 0; index < text.length; index++) {
            const char = text[index];
            const next = text[index + 1];

            if (char === '"') {
                if (inQuotes && next === '"') {
                    current += '"';
                    index++;
                } else {
                    inQuotes = !inQuotes;
                }
            } else if (char === ',' && !inQuotes) {
                row.push(current);
                current = '';
            } else if ((char === '\n' || char === '\r') && !inQuotes) {
                if (char === '\r' && next === '\n') index++;
                row.push(current);
                rows.push(row);
                row = [];
                current = '';
            } else {
                current += char;
            }
        }

        if (current.length > 0 || row.length > 0) {
            row.push(current);
            rows.push(row);
        }
        return rows;
    },
};

document.addEventListener('DOMContentLoaded', () => NormalizedReviewApp.init());
