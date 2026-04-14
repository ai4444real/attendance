'use strict';

const NormalizedReviewApp = {
    _rawRecords: [],
    _records: [],
    _filteredRecords: [],
    _selectedIndex: null,
    _filters: {
        search: '',
        course: '',
        presence: '',
        flaggedOnly: false,
        excludeAuto: false,
        borderlineMargin: 0.03,
    },

    init() {
        this._els = {
            fileInput: document.getElementById('fileInput'),
            pickFileBtn: document.getElementById('pickFileBtn'),
            dropZone: document.getElementById('dropZone'),
            resetBtn: document.getElementById('resetBtn'),
            fileHint: document.getElementById('fileHint'),
            summaryGrid: document.getElementById('summaryGrid'),
            detailPanel: document.getElementById('detailPanel'),
            detailEmpty: document.getElementById('detailEmpty'),
            detailGrid: document.getElementById('detailGrid'),
            detailFlags: document.getElementById('detailFlags'),
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

            this._rawRecords = parsed;
            this._records = this._annotateRecords(parsed);
            this._selectedIndex = null;

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
        this._els.detailPanel.classList.remove('hidden');
        this._els.filtersPanel.classList.remove('hidden');
        this._els.issuesPanel.classList.remove('hidden');
        this._els.tablePanel.classList.remove('hidden');
    },

    _reset() {
        this._rawRecords = [];
        this._records = [];
        this._filteredRecords = [];
        this._selectedIndex = null;
        this._els.fileInput.value = '';
        this._els.fileHint.textContent = 'Formati supportati: CSV esportato dalla CLI, oppure JSON completo del risultato.';
        this._els.resetBtn.classList.add('hidden');
        this._els.summaryGrid.classList.add('hidden');
        this._els.filtersPanel.classList.add('hidden');
        this._els.issuesPanel.classList.add('hidden');
        this._els.tablePanel.classList.add('hidden');
        this._clearDetail();
        this._els.recordsBody.innerHTML = '';
        this._els.summaryGrid.innerHTML = '';
        this._els.issuesGrid.innerHTML = '';
    },

    _parseNormalizedJson(text) {
        const payload = JSON.parse(text);
        const records = Array.isArray(payload.records) ? payload.records : payload;
        if (!Array.isArray(records)) {
            throw new Error('JSON non riconosciuto: manca un array di record.');
        }
        return records.map((record, index) => this._normalizeRecordFromObject(record, index));
    },

    _parseNormalizedCsv(text) {
        const rows = this._parseCsvRows(text);
        if (rows.length < 2) {
            throw new Error('CSV vuoto o non valido.');
        }

        const headers = rows[0].map((value) => value.replace(/^\ufeff/, '').trim());
        return rows.slice(1)
            .filter((row) => row.some((cell) => (cell || '').trim() !== ''))
            .map((row, index) => {
                const record = {};
                headers.forEach((header, headerIndex) => {
                    record[header] = row[headerIndex] ?? '';
                });
                return this._normalizeRecordFromObject(record, index);
            });
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
            const nearFirst = this._isBorderline(pctFirst, record.durationFirstHalf);
            const nearSecond = this._isBorderline(pctSecond, record.durationSecondHalf);
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
                });
            }
            if (record.breakSource !== 'auto') {
                flags.push({
                    key: 'split',
                    tone: 'info',
                    label: `Split ${record.breakSource || 'non auto'}`,
                });
            }
            if (record.segmentCount > 2) {
                flags.push({
                    key: 'segments',
                    tone: 'alert',
                    label: `${record.segmentCount} segmenti`,
                });
            }
            if (!record.email) {
                flags.push({
                    key: 'email',
                    tone: 'info',
                    label: 'Email assente',
                });
            }
            if ((duplicateMap.get(duplicateKey) || 0) > 1) {
                flags.push({
                    key: 'duplicate',
                    tone: 'alert',
                    label: 'Nome duplicato nello stesso meeting',
                });
            }

            return {
                ...record,
                pctFirst,
                pctSecond,
                flags,
                isFlagged: flags.length > 0,
                duplicateCount: duplicateMap.get(duplicateKey) || 0,
            };
        });
    },

    _populateCourseFilter() {
        const courses = [...new Set(this._records.map((record) => record.course))].sort((a, b) => a.localeCompare(b, 'it'));
        let html = '<option value="">Tutti i corsi</option>';
        for (const course of courses) {
            html += `<option value="${this._escapeAttr(course)}">${this._escapeHtml(course)}</option>`;
        }
        this._els.courseSelect.innerHTML = html;
    },

    _renderSummary() {
        const total = this._records.length;
        const courses = new Set(this._records.map((record) => record.course)).size;
        const meetings = new Set(this._records.map((record) => `${record.course}|${record.date}|${record.meetingId}`)).size;
        const borderline = this._records.filter((record) => record.flags.some((flag) => flag.key === 'borderline')).length;
        const nonAuto = this._records.filter((record) => record.breakSource !== 'auto').length;
        const fragmented = this._records.filter((record) => record.segmentCount > 2).length;
        const duplicate = this._records.filter((record) => record.flags.some((flag) => flag.key === 'duplicate')).length;

        this._els.summaryGrid.innerHTML = `
            <article class="summary-card info">
                <div class="summary-label">Record</div>
                <div class="summary-value">${total}</div>
                <div class="summary-detail">Righe normalizzate caricate</div>
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
        `;
    },

    _renderIssues() {
        const borderline = this._records.filter((record) => record.flags.some((flag) => flag.key === 'borderline')).length;
        const nonAuto = this._records.filter((record) => record.breakSource !== 'auto').length;
        const fragmented = this._records.filter((record) => record.segmentCount > 2).length;
        const missingEmail = this._records.filter((record) => !record.email).length;
        const duplicate = this._records.filter((record) => record.flags.some((flag) => flag.key === 'duplicate')).length;

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
        this._syncSelectedRecord();
    },

    _renderTable() {
        const rows = this._filteredRecords.map((record, index) => {
            const isSelected = index === this._selectedIndex;
            const classes = [];
            if (record.isFlagged) classes.push('flagged');
            if (isSelected) classes.push('selected');

            return `
                <tr class="${classes.join(' ')}" data-row-index="${index}">
                    <td>${this._buildFlagHtml(record.flags)}</td>
                    <td>${this._escapeHtml(record.course)}</td>
                    <td>${this._escapeHtml(this._formatDate(record.date))}</td>
                    <td>${this._escapeHtml(record.fullName || '(senza nome)')}</td>
                    <td>${this._escapeHtml(record.email || '-')}</td>
                    <td><span class="presence ${this._escapeAttr(record.presence)}">${this._escapeHtml(this._presenceLabel(record.presence))}</span></td>
                    <td>${this._metricCell(record.minutesFirstHalf, record.durationFirstHalf, record.pctFirst)}</td>
                    <td>${this._metricCell(record.minutesSecondHalf, record.durationSecondHalf, record.pctSecond)}</td>
                    <td>${this._escapeHtml(record.totalMinutes.toFixed(1))} min</td>
                    <td>${this._escapeHtml(String(record.segmentCount))}</td>
                    <td>${this._escapeHtml(record.breakSource || '-')}</td>
                    <td>${this._escapeHtml(record.meetingId || '-')}</td>
                </tr>
            `;
        }).join('');

        this._els.recordsBody.innerHTML = rows || '<tr><td colspan="12" class="muted">Nessun record corrisponde ai filtri correnti.</td></tr>';
        this._els.tableMeta.textContent = `${this._filteredRecords.length} record visibili su ${this._records.length}.`;

        this._els.recordsBody.querySelectorAll('tr[data-row-index]').forEach((row) => {
            row.addEventListener('click', () => {
                this._selectedIndex = parseInt(row.dataset.rowIndex, 10);
                this._renderTable();
                this._renderDetail();
            });
        });
    },

    _syncSelectedRecord() {
        if (this._filteredRecords.length === 0) {
            this._clearDetail();
            return;
        }

        if (this._selectedIndex == null || this._selectedIndex >= this._filteredRecords.length) {
            this._selectedIndex = 0;
        }
        this._renderDetail();
    },

    _renderDetail() {
        const record = this._filteredRecords[this._selectedIndex];
        if (!record) {
            this._clearDetail();
            return;
        }

        this._els.detailEmpty.classList.add('hidden');
        this._els.detailGrid.classList.remove('hidden');
        this._els.detailFlags.classList.remove('hidden');

        this._els.detailGrid.innerHTML = `
            <div class="detail-item"><span class="k">Corso</span><span class="v">${this._escapeHtml(record.course)}</span></div>
            <div class="detail-item"><span class="k">Data</span><span class="v">${this._escapeHtml(this._formatDate(record.date))}</span></div>
            <div class="detail-item"><span class="k">Persona</span><span class="v">${this._escapeHtml(record.fullName || '(senza nome)')}</span></div>
            <div class="detail-item"><span class="k">Email</span><span class="v">${this._escapeHtml(record.email || '-')}</span></div>
            <div class="detail-item"><span class="k">Esito</span><span class="v">${this._escapeHtml(this._presenceLabel(record.presence))}</span></div>
            <div class="detail-item"><span class="k">1ª metà</span><span class="v">${record.minutesFirstHalf.toFixed(1)} / ${record.durationFirstHalf.toFixed(1)} min (${this._formatPct(record.pctFirst)})</span></div>
            <div class="detail-item"><span class="k">2ª metà</span><span class="v">${record.minutesSecondHalf.toFixed(1)} / ${record.durationSecondHalf.toFixed(1)} min (${this._formatPct(record.pctSecond)})</span></div>
            <div class="detail-item"><span class="k">Minuti totali</span><span class="v">${record.totalMinutes.toFixed(1)} min</span></div>
            <div class="detail-item"><span class="k">Segmenti</span><span class="v">${record.segmentCount}</span></div>
            <div class="detail-item"><span class="k">Inizio effettivo</span><span class="v">${this._escapeHtml(this._formatDateTime(record.effectiveStart))}</span></div>
            <div class="detail-item"><span class="k">Break point</span><span class="v">${this._escapeHtml(this._formatDateTime(record.breakPoint))}</span></div>
            <div class="detail-item"><span class="k">Break source</span><span class="v">${this._escapeHtml(record.breakSource || '-')}</span></div>
            <div class="detail-item"><span class="k">Meeting ID</span><span class="v">${this._escapeHtml(record.meetingId || '-')}</span></div>
            <div class="detail-item"><span class="k">Duplicati nome stesso meeting</span><span class="v">${record.duplicateCount}</span></div>
        `;

        this._els.detailFlags.innerHTML = this._buildFlagHtml(record.flags, true);
    },

    _clearDetail() {
        this._els.detailEmpty.classList.remove('hidden');
        this._els.detailGrid.classList.add('hidden');
        this._els.detailFlags.classList.add('hidden');
        this._els.detailGrid.innerHTML = '';
        this._els.detailFlags.innerHTML = '';
    },

    _buildFlagHtml(flags, expanded = false) {
        if (!flags || flags.length === 0) {
            return expanded ? '<span class="flag success">Nessun flag</span>' : '<span class="muted">-</span>';
        }
        return flags.map((flag) => `<span class="flag ${flag.tone}">${this._escapeHtml(flag.label)}</span>`).join(expanded ? '' : ' ');
    },

    _metricCell(minutes, duration, pct) {
        return `${minutes.toFixed(1)} / ${duration.toFixed(1)}<br><span class="muted">${this._formatPct(pct)}</span>`;
    },

    _calcPct(minutes, duration) {
        if (!duration || duration <= 0) return 0;
        return minutes / duration;
    },

    _isBorderline(pct, duration) {
        if (!duration || duration <= 0) return false;
        return Math.abs(pct - 0.8) <= this._filters.borderlineMargin;
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
