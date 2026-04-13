'use strict';

/**
 * Adapter App — Main orchestrator
 *
 * Each course/meeting is rendered as an independent card with:
 *   - Break timeline (draggable)
 *   - Threshold slider (per-course)
 *   - Presence table with overridable status per person
 *
 * Pipeline: parse → auto-detect breaks → render cards → aggregate → display
 */
const AdapterApp = {

    _meetings: [],
    _meetingData: [],   // per-meeting: { breakPoint, breakSource, threshold, aggregated, records, overrides }
    _warnings: [],

    init() {
        const fileInput = document.getElementById('fileInput');
        const dropZone = document.getElementById('dropZone');
        const downloadBtn = document.getElementById('downloadBtn');

        fileInput.addEventListener('change', (e) => this._handleFiles(e.target.files));

        downloadBtn.addEventListener('click', () => {
            const records = this._getAllRecords();
            if (records.length === 0) {
                alert('Nessun dato da esportare.');
                return;
            }
            CsvExport.download(
                CsvExport.generate(records),
                CsvExport.defaultFilename()
            );
        });

        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });
        dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
            this._handleFiles(e.dataTransfer.files);
        });
    },

    // ------------------------------------------------------------------
    // Pipeline
    // ------------------------------------------------------------------

    async _handleFiles(files) {
        if (!files || files.length === 0) return;

        this._meetings = [];
        this._meetingData = [];
        this._warnings = [];
        this._showStatus('Elaborazione in corso...');
        this._clearResults();

        try {
            for (const file of files) {
                if (!file.name.toLowerCase().endsWith('.csv')) {
                    this._warnings.push(`"${file.name}" non e' un file CSV, saltato`);
                    continue;
                }

                const text = await this._readFile(file);
                const { meetings, warnings } = ZoomParser.parse(text);

                this._warnings.push(...warnings.map(w => `[${file.name}] ${w}`));
                this._meetings.push(...meetings);
            }

            if (this._meetings.length === 0) {
                this._showStatus('Nessun meeting trovato nei file caricati.');
                return;
            }

            this._showCourseFilter();

        } catch (error) {
            console.error('Errore elaborazione:', error);
            this._showStatus(`Errore: ${error.message}`);
        }
    },

    _readFile(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target.result);
            reader.onerror = () => reject(new Error(`Errore lettura: ${file.name}`));
            reader.readAsText(file);
        });
    },

    // ------------------------------------------------------------------
    // Data initialization
    // ------------------------------------------------------------------

    _initMeetingData() {
        this._meetingData = [];
        for (let i = 0; i < this._meetings.length; i++) {
            const meeting = this._meetings[i];
            const breakInfo = BreakDetector.detect(meeting);
            let breakPoint, breakSource;

            if (breakInfo) {
                breakPoint = new Date(
                    (breakInfo.breakStart.getTime() + breakInfo.breakEnd.getTime()) / 2
                );
                breakSource = 'auto';
            } else {
                breakPoint = new Date(
                    (meeting.startTime.getTime() + meeting.endTime.getTime()) / 2
                );
                breakSource = 'midpoint';
            }

            this._meetingData.push({
                breakPoint,
                breakSource,
                effectiveStart: this._snapToHalfHour(meeting.startTime),
                threshold: 0.8,
                aggregated: [],
                records: [],
                overrides: new Map()
            });
        }
    },

    // ------------------------------------------------------------------
    // Calculation
    // ------------------------------------------------------------------

    _recalculateAll() {
        const bp = new Map();
        const es = new Map();
        for (let i = 0; i < this._meetingData.length; i++) {
            bp.set(i, this._meetingData[i].breakPoint);
            es.set(i, this._meetingData[i].effectiveStart);
        }

        const allAgg = Aggregator.aggregate(this._meetings, bp, es);

        for (const md of this._meetingData) md.aggregated = [];
        for (const r of allAgg) {
            this._meetingData[r._meetingIndex].aggregated.push(r);
        }

        for (let i = 0; i < this._meetingData.length; i++) {
            this._applyMeetingRules(i);
        }
    },

    _recalculateMeeting(idx) {
        const md = this._meetingData[idx];
        const bp = new Map([[0, md.breakPoint]]);
        const es = new Map([[0, md.effectiveStart]]);
        const agg = Aggregator.aggregate([this._meetings[idx]], bp, es);
        md.aggregated = agg.map(r => ({ ...r, _meetingIndex: idx }));
        this._applyMeetingRules(idx);
    },

    _applyMeetingRules(idx) {
        const md = this._meetingData[idx];
        md.records = md.aggregated.map(r => {
            const key = r.email || `${r.firstName} ${r.lastName}`;
            const calculated = PresenceRules.determine(
                r.minutesFirstHalf, r.minutesSecondHalf,
                r.durationFirstHalf, r.durationSecondHalf,
                md.threshold
            );
            const override = md.overrides.get(key);
            return {
                ...r,
                _calculatedPresence: calculated,
                presence: override || calculated,
                _isOverridden: !!override
            };
        });
    },

    _getAllRecords() {
        const all = [];
        for (const md of this._meetingData) {
            all.push(...md.records);
        }
        return all;
    },

    // ------------------------------------------------------------------
    // Rendering
    // ------------------------------------------------------------------

    _render() {
        this._renderWarnings();
        this._renderGlobalSummary();
        this._renderCourseCards();
        document.getElementById('downloadBtn').style.display = 'inline-block';
        this._showStatus(
            `Completato: ${this._getAllRecords().length} record da ${this._meetings.length} meeting`
        );
    },

    _renderWarnings() {
        const warningsEl = document.getElementById('warnings');
        if (this._warnings.length > 0) {
            warningsEl.innerHTML =
                '<h3>Avvisi</h3>' +
                this._warnings.map(w => `<div class="warning-item">${this._escHtml(w)}</div>`).join('');
            warningsEl.style.display = 'block';
        } else {
            warningsEl.style.display = 'none';
        }
    },

    _renderGlobalSummary() {
        const all = this._getAllRecords();
        const people = new Set(all.map(r => r.email || `${r.firstName} ${r.lastName}`)).size;
        const counts = { presente: 0, prima_meta: 0, seconda_meta: 0, assente: 0 };
        for (const r of all) counts[r.presence]++;

        document.getElementById('summary').innerHTML = `
            <div class="summary-grid">
                <div class="summary-item">
                    <div class="summary-label">Corsi</div>
                    <div class="summary-value">${this._meetings.length}</div>
                </div>
                <div class="summary-item">
                    <div class="summary-label">Partecipanti</div>
                    <div class="summary-value">${people}</div>
                </div>
                <div class="summary-item">
                    <div class="summary-label">Record</div>
                    <div class="summary-value">${all.length}</div>
                </div>
                <div class="summary-item present">
                    <div class="summary-label">Presenti</div>
                    <div class="summary-value">${counts.presente}</div>
                </div>
                <div class="summary-item first-half">
                    <div class="summary-label">Prima metà</div>
                    <div class="summary-value">${counts.prima_meta}</div>
                </div>
                <div class="summary-item second-half">
                    <div class="summary-label">Seconda metà</div>
                    <div class="summary-value">${counts.seconda_meta}</div>
                </div>
                <div class="summary-item absent">
                    <div class="summary-label">Assenti</div>
                    <div class="summary-value">${counts.assente}</div>
                </div>
            </div>
        `;
    },

    _renderCourseCards() {
        const container = document.getElementById('courseCards');
        let html = '';

        for (let i = 0; i < this._meetings.length; i++) {
            html += this._buildCardHTML(i);
        }

        container.innerHTML = html;

        container.querySelectorAll('.course-card').forEach((card) => {
            const idx = parseInt(card.dataset.meetingIndex);
            this._setupCardInteractions(card, idx);
        });
    },

    // ------------------------------------------------------------------
    // Card HTML builders
    // ------------------------------------------------------------------

    _buildCardHTML(idx) {
        const m = this._meetings[idx];
        const md = this._meetingData[idx];
        const { points, maxCount } = this._computeHistogram(m);

        const startMs = m.startTime.getTime();
        const endMs = m.endTime.getTime();
        const total = endMs - startMs;
        const barWidth = total > 0 ? (60000 / total * 100) : 1;

        let histHtml = '';
        for (const p of points) {
            if (p.count === 0) continue;
            const height = maxCount > 0 ? (p.count / maxCount * 100) : 0;
            const left = ((p.time - startMs) / total * 100);
            histHtml += `<div class="mp-hist" style="left:${left.toFixed(2)}%;width:${barWidth.toFixed(2)}%;height:${height.toFixed(0)}%"></div>`;
        }

        const handleLeft = ((md.breakPoint.getTime() - startMs) / total * 100);
        const startPct = ((md.effectiveStart.getTime() - startMs) / total * 100);
        const participants = new Set(m.segments.map(s => s.email || s.fullName)).size;
        const sourceLabel = this._sourceLabel(md.breakSource);
        const thresholdPct = Math.round(md.threshold * 100);
        const startDiffers = md.effectiveStart.getTime() > startMs;

        return `
        <div class="course-card" data-meeting-index="${idx}">
            <div class="cc-header">
                <span class="cc-title">${this._escHtml(m.course)}</span>
                <span class="cc-meta">${this._fmtDate(m.startTime)}</span>
                <span class="cc-meta">${Math.round(m.durationMinutes)} min</span>
                <span class="cc-meta">${participants} partecipanti</span>
            </div>

            <div class="cc-controls">
                <div class="cc-timeline-wrap">
                    <div class="mp-bar">
                        <div class="mp-trim-overlay" style="width:${startPct.toFixed(2)}%"></div>
                        ${histHtml}
                        <div class="mp-start-handle" style="left:${startPct.toFixed(2)}%">
                            <div class="mp-start-line"></div>
                            <div class="mp-start-grip"></div>
                            <div class="mp-start-time">${this._fmtTime(md.effectiveStart)}</div>
                        </div>
                        <div class="mp-handle" style="left:${handleLeft.toFixed(2)}%">
                            <div class="mp-handle-line"></div>
                            <div class="mp-handle-grip"></div>
                            <div class="mp-handle-time">${this._fmtTime(md.breakPoint)}</div>
                        </div>
                    </div>
                    <div class="cc-time-labels">
                        <span>${this._fmtTime(m.startTime)}</span>
                        <span>${this._fmtTime(m.endTime)}</span>
                    </div>
                </div>
                <div class="cc-settings">
                    <span class="cc-start-info">Inizio: ${this._fmtTime(md.effectiveStart)}${startDiffers ? ' (tagliato)' : ''}</span>
                    <span class="cc-break-info">Pausa: ${this._fmtTime(md.breakPoint)} ${sourceLabel}</span>
                    <div class="cc-threshold">
                        <label>Soglia:</label>
                        <input type="range" class="cc-threshold-slider" min="50" max="100" value="${thresholdPct}" step="5">
                        <span class="cc-threshold-value">${thresholdPct}%</span>
                    </div>
                    <button class="mp-apply-btn">Ricalcola</button>
                </div>
            </div>

            <div class="cc-summary">${this._buildCardSummaryHTML(md)}</div>
            <div class="cc-table-wrap">${this._buildCardTableHTML(md)}</div>
        </div>`;
    },

    _buildCardSummaryHTML(md) {
        const counts = { presente: 0, prima_meta: 0, seconda_meta: 0, assente: 0 };
        for (const r of md.records) counts[r.presence]++;
        return `
            <span class="cc-stat present">Presenti: ${counts.presente}</span>
            <span class="cc-stat first-half">Prima metà: ${counts.prima_meta}</span>
            <span class="cc-stat second-half">Seconda metà: ${counts.seconda_meta}</span>
            <span class="cc-stat absent">Assenti: ${counts.assente}</span>
        `;
    },

    _buildCardTableHTML(md) {
        let html = `<table><thead><tr>
            <th>Nome</th><th>Cognome</th><th>Email</th>
            <th>Presenza</th>
            <th>1ª Metà</th><th>2ª Metà</th><th>Seg.</th>
        </tr></thead><tbody>`;

        for (const r of md.records) {
            html += `<tr>
                <td>${this._escHtml(r.firstName)}</td>
                <td>${this._escHtml(r.lastName)}</td>
                <td>${this._escHtml(r.email)}</td>
                <td>${this._buildPresenceSelect(r)}</td>
                <td>${r.minutesFirstHalf} / ${r.durationFirstHalf} (${this._pct(r.minutesFirstHalf, r.durationFirstHalf)})</td>
                <td>${r.minutesSecondHalf} / ${r.durationSecondHalf} (${this._pct(r.minutesSecondHalf, r.durationSecondHalf)})</td>
                <td class="seg-cell">${r.segmentCount}${this._buildTimeline(r)}</td>
            </tr>`;
        }

        html += '</tbody></table>';
        return html;
    },

    _buildPresenceSelect(r) {
        const key = r.email || `${r.firstName} ${r.lastName}`;
        const calc = r._calculatedPresence;
        const effective = r.presence;
        const cls = this._presenceClass(effective);
        const forced = r._isOverridden ? ' forced' : '';
        const selectedValue = r._isOverridden ? effective : 'auto';

        const options = [
            { value: 'auto', label: `${this._presenceLabel(calc)} (auto)` },
            { value: 'presente', label: 'Presente' },
            { value: 'prima_meta', label: 'Prima metà' },
            { value: 'seconda_meta', label: 'Seconda metà' },
            { value: 'assente', label: 'Assente' },
        ];

        let html = `<select class="presence-select ${cls}${forced}" data-key="${this._escAttr(key)}">`;
        for (const opt of options) {
            const sel = opt.value === selectedValue ? ' selected' : '';
            html += `<option value="${opt.value}"${sel}>${opt.label}</option>`;
        }
        html += '</select>';
        return html;
    },

    // ------------------------------------------------------------------
    // Card interactions
    // ------------------------------------------------------------------

    _setupCardInteractions(cardEl, idx) {
        this._setupStartDrag(cardEl, idx);
        this._setupBreakDrag(cardEl, idx);
        this._setupThresholdSlider(cardEl, idx);
        this._setupApplyButton(cardEl, idx);
        this._setupPresenceOverrides(cardEl, idx);
    },

    _setupStartDrag(cardEl, idx) {
        const bar = cardEl.querySelector('.mp-bar');
        const handle = cardEl.querySelector('.mp-start-handle');
        const timeLabel = handle.querySelector('.mp-start-time');
        const trimOverlay = cardEl.querySelector('.mp-trim-overlay');
        const applyBtn = cardEl.querySelector('.mp-apply-btn');
        const meeting = this._meetings[idx];
        const startMs = meeting.startTime.getTime();
        const duration = meeting.endTime.getTime() - startMs;

        const posToTime = (clientX) => {
            const rect = bar.getBoundingClientRect();
            const pct = Math.max(0, Math.min(0.5, (clientX - rect.left) / rect.width));
            return new Date(startMs + pct * duration);
        };

        const updateHandle = (time) => {
            const pct = ((time.getTime() - startMs) / duration * 100);
            handle.style.left = pct + '%';
            trimOverlay.style.width = pct + '%';
            timeLabel.textContent = this._fmtTime(time);
        };

        const stageStart = (time) => {
            updateHandle(time);
            this._meetingData[idx].effectiveStart = time;
            this._updateStartInfo(cardEl, idx);
            applyBtn.style.display = 'inline-block';
        };

        handle.addEventListener('mousedown', (e) => {
            e.preventDefault();
            e.stopPropagation();
            handle.classList.add('dragging');
            bar.dataset.dragging = '1';

            const onMove = (ev) => updateHandle(posToTime(ev.clientX));
            const onUp = (ev) => {
                handle.classList.remove('dragging');
                document.removeEventListener('mousemove', onMove);
                document.removeEventListener('mouseup', onUp);
                stageStart(posToTime(ev.clientX));
                setTimeout(() => { delete bar.dataset.dragging; }, 10);
            };

            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
        });
    },

    _setupBreakDrag(cardEl, idx) {
        const bar = cardEl.querySelector('.mp-bar');
        const handle = cardEl.querySelector('.mp-handle');
        const timeLabel = handle.querySelector('.mp-handle-time');
        const applyBtn = cardEl.querySelector('.mp-apply-btn');
        const meeting = this._meetings[idx];
        const startMs = meeting.startTime.getTime();
        const duration = meeting.endTime.getTime() - startMs;

        const posToTime = (clientX) => {
            const rect = bar.getBoundingClientRect();
            const pct = Math.max(0.05, Math.min(0.95, (clientX - rect.left) / rect.width));
            return new Date(startMs + pct * duration);
        };

        const updateHandle = (time) => {
            const pct = ((time.getTime() - startMs) / duration * 100);
            handle.style.left = pct + '%';
            timeLabel.textContent = this._fmtTime(time);
        };

        const stageBreak = (time) => {
            updateHandle(time);
            this._meetingData[idx].breakPoint = time;
            this._meetingData[idx].breakSource = 'manual';
            this._updateBreakInfo(cardEl, idx);
            applyBtn.style.display = 'inline-block';
        };

        // Click on empty bar area → jump break handle (skip if dragging or clicking a handle)
        bar.addEventListener('click', (e) => {
            if (bar.dataset.dragging) return;
            if (e.target.closest('.mp-handle, .mp-start-handle')) return;
            stageBreak(posToTime(e.clientX));
        });

        handle.addEventListener('mousedown', (e) => {
            e.preventDefault();
            e.stopPropagation();
            handle.classList.add('dragging');
            bar.dataset.dragging = '1';

            const onMove = (ev) => updateHandle(posToTime(ev.clientX));
            const onUp = (ev) => {
                handle.classList.remove('dragging');
                document.removeEventListener('mousemove', onMove);
                document.removeEventListener('mouseup', onUp);
                stageBreak(posToTime(ev.clientX));
                setTimeout(() => { delete bar.dataset.dragging; }, 10);
            };

            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
        });
    },

    _setupThresholdSlider(cardEl, idx) {
        const slider = cardEl.querySelector('.cc-threshold-slider');
        const valueEl = cardEl.querySelector('.cc-threshold-value');

        slider.addEventListener('input', () => {
            const pct = parseInt(slider.value);
            valueEl.textContent = pct + '%';
            this._meetingData[idx].threshold = pct / 100;
            this._applyMeetingRules(idx);
            this._refreshCardResults(cardEl, idx);
        });
    },

    _setupApplyButton(cardEl, idx) {
        const applyBtn = cardEl.querySelector('.mp-apply-btn');

        applyBtn.addEventListener('click', () => {
            try {
                this._recalculateMeeting(idx);
                this._refreshCardResults(cardEl, idx);
                applyBtn.style.display = 'none';
            } catch (err) {
                console.error('Errore ricalcolo:', err);
                this._showStatus(`Errore ricalcolo: ${err.message}`);
            }
        });
    },

    _setupPresenceOverrides(cardEl, idx) {
        cardEl.addEventListener('change', (e) => {
            if (!e.target.classList.contains('presence-select')) return;

            const key = e.target.dataset.key;
            const value = e.target.value;
            const md = this._meetingData[idx];

            if (value === 'auto') {
                md.overrides.delete(key);
            } else {
                md.overrides.set(key, value);
            }

            this._applyMeetingRules(idx);
            this._refreshCardResults(cardEl, idx);
        });
    },

    // ------------------------------------------------------------------
    // Partial updates (only summary + table within a card)
    // ------------------------------------------------------------------

    _refreshCardResults(cardEl, idx) {
        const md = this._meetingData[idx];
        cardEl.querySelector('.cc-summary').innerHTML = this._buildCardSummaryHTML(md);
        cardEl.querySelector('.cc-table-wrap').innerHTML = this._buildCardTableHTML(md);
        this._renderGlobalSummary();
    },

    _updateStartInfo(cardEl, idx) {
        const md = this._meetingData[idx];
        const startMs = this._meetings[idx].startTime.getTime();
        const differs = md.effectiveStart.getTime() > startMs;
        cardEl.querySelector('.cc-start-info').textContent =
            `Inizio: ${this._fmtTime(md.effectiveStart)}${differs ? ' (tagliato)' : ''}`;
    },

    _updateBreakInfo(cardEl, idx) {
        const md = this._meetingData[idx];
        const sourceLabel = this._sourceLabel(md.breakSource);
        cardEl.querySelector('.cc-break-info').textContent =
            `Pausa: ${this._fmtTime(md.breakPoint)} ${sourceLabel}`;
    },

    // ------------------------------------------------------------------
    // Utilities
    // ------------------------------------------------------------------

    _computeHistogram(meeting) {
        const startMs = meeting.startTime.getTime();
        const endMs = meeting.endTime.getTime();
        const step = 60000;
        const points = [];
        let maxCount = 0;

        for (let t = startMs; t <= endMs; t += step) {
            let count = 0;
            for (const seg of meeting.segments) {
                if (seg.joinTime.getTime() <= t && seg.leaveTime.getTime() > t) {
                    count++;
                }
            }
            points.push({ time: t, count });
            if (count > maxCount) maxCount = count;
        }

        return { points, maxCount };
    },

    _clearResults() {
        document.getElementById('summary').innerHTML = '';
        document.getElementById('warnings').innerHTML = '';
        document.getElementById('warnings').style.display = 'none';
        document.getElementById('courseCards').innerHTML = '';
        document.getElementById('downloadBtn').style.display = 'none';
        document.getElementById('courseFilter').style.display = 'none';
    },

    // ------------------------------------------------------------------
    // Course filter
    // ------------------------------------------------------------------

    _isUpperCase(name) {
        const letters = name.replace(/[^a-zA-ZÀ-ÿ]/g, '');
        return letters.length > 0 && letters === letters.toUpperCase();
    },

    _showCourseFilter() {
        const courseMap = new Map();
        for (const m of this._meetings) {
            const name = m.course || '(senza nome)';
            courseMap.set(name, (courseMap.get(name) || 0) + 1);
        }

        const sorted = [...courseMap.entries()].sort((a, b) => a[0].localeCompare(b[0], 'it'));

        let listHtml = '';
        let preSelected = 0;
        for (const [name, count] of sorted) {
            const checked = this._isUpperCase(name);
            if (checked) preSelected++;
            const cls = checked ? ' pre-selected' : '';
            listHtml += `
                <label class="cf-item${cls}">
                    <input type="checkbox" value="${this._escAttr(name)}" ${checked ? 'checked' : ''}>
                    <span>${this._escHtml(name)}</span>
                    <span class="cf-count">${count}</span>
                </label>`;
        }

        const filterEl = document.getElementById('courseFilter');
        filterEl.innerHTML = `
            <div class="cf-header">
                <h3>Seleziona i corsi da elaborare</h3>
                <span class="cf-counter">${preSelected} / ${sorted.length} selezionati</span>
            </div>
            <div class="cf-actions">
                <button class="cf-all">Tutti</button>
                <button class="cf-none">Nessuno</button>
                <button class="cf-uppercase">Solo MAIUSCOLO</button>
                <button class="cf-proceed">Procedi</button>
            </div>
            <div class="cf-list">${listHtml}</div>
        `;
        filterEl.style.display = 'block';

        const updateCounter = () => {
            const total = filterEl.querySelectorAll('.cf-item input').length;
            const checked = filterEl.querySelectorAll('.cf-item input:checked').length;
            filterEl.querySelector('.cf-counter').textContent = `${checked} / ${total} selezionati`;
        };

        filterEl.querySelector('.cf-list').addEventListener('change', updateCounter);

        filterEl.querySelector('.cf-all').addEventListener('click', () => {
            filterEl.querySelectorAll('.cf-item input').forEach(cb => cb.checked = true);
            updateCounter();
        });

        filterEl.querySelector('.cf-none').addEventListener('click', () => {
            filterEl.querySelectorAll('.cf-item input').forEach(cb => cb.checked = false);
            updateCounter();
        });

        filterEl.querySelector('.cf-uppercase').addEventListener('click', () => {
            filterEl.querySelectorAll('.cf-item input').forEach(cb => {
                cb.checked = this._isUpperCase(cb.value);
            });
            updateCounter();
        });

        filterEl.querySelector('.cf-proceed').addEventListener('click', () => {
            this._applyCourseFilter();
        });

        this._showStatus(`${this._meetings.length} meeting trovati. Seleziona i corsi da elaborare.`);
    },

    _applyCourseFilter() {
        const filterEl = document.getElementById('courseFilter');
        const selected = new Set();
        filterEl.querySelectorAll('.cf-item input:checked').forEach(cb => {
            selected.add(cb.value);
        });

        if (selected.size === 0) {
            this._showStatus('Seleziona almeno un corso.');
            return;
        }

        this._meetings = this._meetings.filter(m => selected.has(m.course || '(senza nome)'));
        filterEl.style.display = 'none';

        this._initMeetingData();
        this._recalculateAll();
        this._render();
    },

    _showStatus(msg) {
        document.getElementById('status').textContent = msg;
    },

    /** Snap to nearest :00 or :30, but not before meeting start */
    _snapToHalfHour(meetingStart) {
        const d = new Date(meetingStart);
        const minutes = d.getMinutes();
        const rounded = new Date(d);

        if (minutes < 15) {
            rounded.setMinutes(0, 0, 0);
        } else if (minutes < 45) {
            rounded.setMinutes(30, 0, 0);
        } else {
            rounded.setMinutes(0, 0, 0);
            rounded.setHours(rounded.getHours() + 1);
        }

        // Don't go before the actual meeting start
        return rounded < meetingStart ? new Date(meetingStart) : rounded;
    },

    _sourceLabel(source) {
        if (source === 'auto') return '(auto)';
        if (source === 'manual') return '(manuale)';
        return '(metà)';
    },

    _presenceClass(p) {
        return { presente: 'present', prima_meta: 'first-half', seconda_meta: 'second-half', assente: 'absent' }[p] || '';
    },

    _presenceLabel(p) {
        return { presente: 'Presente', prima_meta: 'Prima metà', seconda_meta: 'Seconda metà', assente: 'Assente' }[p] || p;
    },

    _fmtDate(date) {
        if (!date) return '';
        return new Date(date).toLocaleDateString('it-IT', { day: '2-digit', month: '2-digit', year: 'numeric' });
    },

    _fmtTime(date) {
        if (!date) return '';
        return date.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' });
    },

    _pct(minutes, duration) {
        if (!duration || duration <= 0) return '0%';
        return Math.round(minutes / duration * 100) + '%';
    },

    _escHtml(str) {
        if (!str) return '';
        const d = document.createElement('div');
        d.textContent = str;
        return d.innerHTML;
    },

    _escAttr(str) {
        if (!str) return '';
        return str.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    },

    // ------------------------------------------------------------------
    // Per-student timeline tooltip (on Seg. hover)
    // ------------------------------------------------------------------

    _buildTimeline(r) {
        if (!r._segments || r._segments.length === 0) return '';

        const start = r.meetingStart.getTime();
        const end = r.meetingEnd.getTime();
        const total = end - start;
        if (total <= 0) return '';

        const pct = (t) => ((t - start) / total * 100).toFixed(2);

        let blocks = '';
        for (const seg of r._segments) {
            const left = pct(seg.joinTime.getTime());
            const width = ((seg.leaveTime - seg.joinTime) / total * 100).toFixed(2);
            blocks += `<div class="tl-seg" style="left:${left}%;width:${width}%"></div>`;
        }

        const breakLeft = pct(r._firstHalfEnd.getTime());
        const splitMarker = `<div class="tl-break-line" style="left:${breakLeft}%"></div>`;

        return `
            <div class="tl-tooltip">
                <div class="tl-labels">
                    <span>${this._fmtTime(r.meetingStart)}</span>
                    <span>${this._fmtTime(r.meetingEnd)}</span>
                </div>
                <div class="tl-bar">
                    ${blocks}
                    ${splitMarker}
                </div>
            </div>
        `;
    }
};

document.addEventListener('DOMContentLoaded', () => AdapterApp.init());
