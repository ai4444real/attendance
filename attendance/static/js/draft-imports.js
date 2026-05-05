'use strict';

const DraftImportsApp = {
    async init() {
        this._els = {
            batchList: document.getElementById('batchList'),
            batchSummary: document.getElementById('batchSummary'),
            lessonFilters: document.getElementById('lessonFilters'),
            lessonList: document.getElementById('lessonList'),
            lessonsContainer: document.getElementById('lessonsContainer'),
        };
        this._lessonFilter = 'draft';

        await this._loadBatches();
    },

    async _loadBatches() {
        this._els.batchList.innerHTML = '<div class="empty">Carico gli import batch...</div>';
        this._els.batchSummary.innerHTML = '';
        this._els.lessonList.innerHTML = '';
        this._els.lessonsContainer.innerHTML = '<div class="empty">Seleziona un import batch.</div>';

        try {
            const response = await fetch('/api/attendance/import-batches');
            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload.detail || 'Impossibile leggere gli import batch.');
            }

            this._batches = payload.batches || [];
            this._renderBatchList();

            if (this._batches.length > 0) {
                await this._loadBatchDetail(this._batches[0].id);
            } else {
                this._els.batchList.innerHTML = '<div class="empty">Nessun import batch nel database.</div>';
            }
        } catch (error) {
            console.error(error);
            this._els.batchList.innerHTML = `<div class="empty">${this._escapeHtml(error.message)}</div>`;
        }
    },

    _renderBatchList() {
        if (!this._batches || this._batches.length === 0) {
            return;
        }

        this._els.batchList.innerHTML = this._batches.map((batch) => `
            <button class="batch-item${this._selectedBatchId === batch.id ? ' active' : ''}" data-batch-id="${batch.id}" type="button">
                <div class="batch-title">#${batch.id} · ${this._escapeHtml(batch.source_file_name)}</div>
                <div class="batch-meta">
                    ${this._escapeHtml(batch.source_system)} · ${this._formatDateTime(batch.created_at)}<br>
                    ${batch.lessons_count} lezioni · ${batch.participants_count} partecipanti · ${this._escapeHtml(batch.status)}
                </div>
            </button>
        `).join('');

        this._els.batchList.querySelectorAll('[data-batch-id]').forEach((button) => {
            button.addEventListener('click', async () => {
                const batchId = Number(button.getAttribute('data-batch-id'));
                await this._loadBatchDetail(batchId);
            });
        });
    },

    async _loadBatchDetail(batchId) {
        this._selectedBatchId = batchId;
        this._selectedLessonId = null;
        this._renderBatchList();
        this._els.batchSummary.innerHTML = '';
        this._els.lessonList.innerHTML = '<div class="empty">Carico la lista lezioni...</div>';
        this._els.lessonsContainer.innerHTML = '<div class="empty">Carico il dettaglio del batch...</div>';

        try {
            const response = await fetch(`/api/attendance/import-batches/${batchId}`);
            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload.detail || 'Impossibile leggere il dettaglio del batch.');
            }

            this._renderBatchSummary(payload.batch);
            this._renderLessonList(payload.lessons || []);
            const visibleLessons = this._filterLessons(payload.lessons || []);
            if (visibleLessons.length > 0) {
                await this._loadLessonDetail(visibleLessons[0].id);
            } else {
                this._els.lessonsContainer.innerHTML = '<div class="empty">Nessuna lezione nel filtro corrente.</div>';
            }
        } catch (error) {
            console.error(error);
            this._els.lessonsContainer.innerHTML = `<div class="empty">${this._escapeHtml(error.message)}</div>`;
        }
    },

    _renderBatchSummary(batch) {
        this._els.batchSummary.innerHTML = `
            <div class="batch-strip-title">#${this._escapeHtml(batch.id)} · ${this._escapeHtml(batch.source_file_name)}</div>
            <div class="batch-strip-meta">
                <span><strong>${this._escapeHtml(batch.status)}</strong> · ${this._escapeHtml(batch.source_system)}</span>
                <span><strong>${this._escapeHtml(batch.lessons_count)}</strong> lezioni</span>
                <span><strong>${this._escapeHtml(batch.participants_count)}</strong> partecipanti</span>
                <span>${this._escapeHtml(this._formatDateTime(batch.created_at))}</span>
            </div>
        `;
    },

    _renderLessonList(lessons) {
        this._currentLessons = lessons;
        this._renderLessonFilters(lessons);
        const visibleLessons = this._filterLessons(lessons);
        if (visibleLessons.length === 0) {
            this._els.lessonList.innerHTML = '<div class="empty">Questo import batch non contiene lezioni.</div>';
            return;
        }
        this._els.lessonList.innerHTML = visibleLessons.map((lesson) => {
            const summary = lesson.summary || {};
            return `
                <div class="batch-item${this._selectedLessonId === lesson.id ? ' active' : ''}">
                    <button class="lesson-select" data-lesson-id="${lesson.id}" type="button">
                        <div class="batch-title">${this._escapeHtml(lesson.course_name)}</div>
                        <div class="batch-meta">
                            ${this._escapeHtml(lesson.lesson_date)} · meeting ${this._escapeHtml(lesson.source_meeting_id)}<br>
                            P ${summary.presente || 0} · 1ª ${summary.prima_meta || 0} · 2ª ${summary.seconda_meta || 0} · A ${summary.assente || 0}<br>
                            ${this._escapeHtml(lesson.status)}${lesson.is_ignored ? ' · ignorata' : ''}
                        </div>
                    </button>
                    <div class="lesson-actions">
                        <button class="mini-action warn" type="button" data-lesson-action="toggle-ignore" data-lesson-id="${lesson.id}">${lesson.is_ignored ? 'Ripristina' : 'Ignore'}</button>
                        <button class="mini-action good" type="button" data-lesson-action="toggle-status" data-lesson-id="${lesson.id}" data-target-status="${lesson.status === 'official' ? 'draft' : 'official'}">${lesson.status === 'official' ? 'Riapri' : 'Official'}</button>
                    </div>
                </div>
            `;
        }).join('');

        this._els.lessonList.querySelectorAll('.lesson-select[data-lesson-id]').forEach((button) => {
            button.addEventListener('click', async () => {
                const lessonId = Number(button.getAttribute('data-lesson-id'));
                await this._loadLessonDetail(lessonId);
            });
        });
        this._els.lessonList.querySelectorAll('[data-lesson-action]').forEach((button) => {
            button.addEventListener('click', async (event) => {
                event.stopPropagation();
                const lessonId = Number(button.getAttribute('data-lesson-id'));
                const action = button.getAttribute('data-lesson-action');
                if (action === 'toggle-ignore') {
                    const lesson = lessons.find((item) => item.id === lessonId);
                    await this._setLessonIgnored(lessonId, !(lesson && lesson.is_ignored));
                    return;
                }
                if (action === 'toggle-status') {
                    const targetStatus = button.getAttribute('data-target-status');
                    await this._setLessonStatus(lessonId, targetStatus);
                }
            });
        });
    },

    _renderLessonFilters(lessons) {
        const counts = {
            draft: lessons.filter((lesson) => lesson.status === 'draft' && !lesson.is_ignored).length,
            ignored: lessons.filter((lesson) => lesson.is_ignored).length,
            official: lessons.filter((lesson) => lesson.status === 'official' && !lesson.is_ignored).length,
            all: lessons.length,
        };
        this._els.lessonFilters.innerHTML = [
            ['draft', 'Draft'],
            ['ignored', 'Ignorate'],
            ['official', 'Official'],
            ['all', 'Tutte'],
        ].map(([key, label]) => `
            <button type="button" class="filter-chip${this._lessonFilter === key ? ' active' : ''}" data-filter="${key}">
                ${label} <span class="filter-chip-count">${counts[key] || 0}</span>
            </button>
        `).join('');
        this._els.lessonFilters.querySelectorAll('[data-filter]').forEach((button) => {
            button.addEventListener('click', () => {
                this._lessonFilter = button.getAttribute('data-filter') || 'draft';
                this._renderLessonList(this._currentLessons || []);
                if (this._currentLessons && !this._filterLessons(this._currentLessons).some((lesson) => lesson.id === this._selectedLessonId)) {
                    const nextLesson = this._filterLessons(this._currentLessons)[0];
                    if (nextLesson) {
                        this._loadLessonDetail(nextLesson.id);
                    } else {
                        this._selectedLessonId = null;
                        this._els.lessonsContainer.innerHTML = '<div class="empty">Nessuna lezione nel filtro corrente.</div>';
                    }
                }
            });
        });
    },

    _filterLessons(lessons) {
        switch (this._lessonFilter) {
            case 'ignored':
                return lessons.filter((lesson) => lesson.is_ignored);
            case 'official':
                return lessons.filter((lesson) => lesson.status === 'official' && !lesson.is_ignored);
            case 'all':
                return lessons;
            case 'draft':
            default:
                return lessons.filter((lesson) => lesson.status === 'draft' && !lesson.is_ignored);
        }
    },

    async _loadLessonDetail(lessonId) {
        this._selectedLessonId = lessonId;
        if (this._currentLessons) {
            this._renderLessonList(this._currentLessons);
        }
        this._els.lessonsContainer.innerHTML = '<div class="empty">Carico la lezione...</div>';

        try {
            const response = await fetch(`/api/attendance/lessons/${lessonId}`);
            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload.detail || 'Impossibile leggere il dettaglio della lezione.');
            }
            this._renderLessonDetail(payload.lesson);
        } catch (error) {
            console.error(error);
            this._els.lessonsContainer.innerHTML = `<div class="empty">${this._escapeHtml(error.message)}</div>`;
        }
    },

    _renderLessonDetail(lesson) {
        const diagnostics = lesson.diagnostics || {};
        const summary = lesson.summary || {};
        const threshold = lesson.threshold_ratio || 0.8;
        const timeline = diagnostics.timeline || [];
        const peak = diagnostics.peak_active_count || Math.max(...timeline.map((point) => point.active_count), 1);
        const bars = timeline.length > 0
            ? timeline.map((point) => this._buildTimelineBar(point, peak, lesson.meeting_start_at)).join('')
            : '<div class="empty">Timeline non disponibile per questa lezione.</div>';
        const participants = lesson.participants || [];
        const visibleParticipants = participants.filter((participant) => participant.final_presence_status !== 'presente' || participant.manual_override_presence_status);
        const presentParticipants = participants.filter((participant) => participant.final_presence_status === 'presente' && !participant.manual_override_presence_status);
        const diagnosisText = lesson.break_source === 'auto'
            ? 'Pausa rilevata automaticamente dal profilo dei presenti.'
            : lesson.break_source === 'midpoint'
                ? 'Pausa non trovata: il giallo è stato messo a metà esatta del tempo utile.'
                : `Pausa impostata con criterio ${lesson.break_source}.`;
        this._els.lessonsContainer.innerHTML = `
            <article class="lesson-card">
                <div class="lesson-head">
                    <div>
                        <h3 class="lesson-title">${this._escapeHtml(lesson.course_name)}</h3>
                        <div class="lesson-subtitle">
                            ${this._escapeHtml(lesson.lesson_date)} · meeting ${this._escapeHtml(lesson.source_meeting_id)} · lesson #${lesson.id}
                        </div>
                    </div>
                    <div class="pill-row">
                        <span class="pill green">Presente ${summary.presente || 0}</span>
                        <span class="pill blue">1ª metà ${summary.prima_meta || 0}</span>
                        <span class="pill yellow">2ª metà ${summary.seconda_meta || 0}</span>
                        <span class="pill red">Assente ${summary.assente || 0}</span>
                    </div>
                </div>
                <div class="lesson-body">
                    <div class="meeting-diagnostics">
                        <div class="meeting-diagnostics-note">${this._escapeHtml(diagnosisText)}</div>
                        <div class="meeting-chart">
                            <div class="meeting-bars">${bars}</div>
                            <div class="meeting-markers">
                                <div class="meeting-marker zoom-start" style="left:${this._markerPosition(lesson.meeting_start_at, lesson.meeting_start_at, lesson.meeting_end_at)}%">
                                    <span>Inizio Zoom</span>
                                    <strong>${this._escapeHtml(this._formatTime(lesson.meeting_start_at))}</strong>
                                </div>
                                <div class="meeting-marker start" style="left:${this._markerPosition(lesson.effective_start_at, lesson.meeting_start_at, lesson.meeting_end_at)}%">
                                    <span>Inizio utile</span>
                                    <strong>${this._escapeHtml(this._formatTime(lesson.effective_start_at))}</strong>
                                </div>
                                ${lesson.break_point_at ? `
                                <div class="meeting-marker break" style="left:${this._markerPosition(lesson.break_point_at, lesson.meeting_start_at, lesson.meeting_end_at)}%">
                                    <span>Pausa</span>
                                    <strong>${this._escapeHtml(this._formatTime(lesson.break_point_at))}</strong>
                                </div>` : ''}
                                <div class="meeting-marker end" style="left:${this._markerPosition(lesson.effective_end_at, lesson.meeting_start_at, lesson.meeting_end_at)}%">
                                    <span>Fine utile</span>
                                    <strong>${this._escapeHtml(this._formatTime(lesson.effective_end_at))}</strong>
                                </div>
                                <div class="meeting-marker zoom-end" style="left:${this._markerPosition(lesson.meeting_end_at, lesson.meeting_start_at, lesson.meeting_end_at)}%">
                                    <span>Fine Zoom</span>
                                    <strong>${this._escapeHtml(this._formatTime(lesson.meeting_end_at))}</strong>
                                </div>
                            </div>
                            <div class="meeting-axis">
                                <span>${this._escapeHtml(this._formatTime(lesson.meeting_start_at))}</span>
                                <span>${this._escapeHtml(this._formatTime(lesson.meeting_end_at))}</span>
                            </div>
                        </div>
                    </div>
                    <div class="threshold-strip">
                        <div class="threshold-badge">
                            <span class="threshold-badge-label">Threshold</span>
                            <span class="threshold-badge-value">${Math.round(threshold * 100)}%</span>
                        </div>
                    </div>
                    <details class="action-panel">
                        <summary class="action-panel-head">
                            <h4 class="action-panel-title">Correzioni lezione</h4>
                            <span class="action-panel-state">Apri / chiudi</span>
                        </summary>
                        <div class="action-panel-body">
                            <div class="action-buttons">
                                <button type="button" class="action-button" data-action="set-threshold" data-lesson-id="${lesson.id}">Threshold</button>
                                <button type="button" class="action-button" data-action="set-start" data-lesson-id="${lesson.id}">Inizio</button>
                                <button type="button" class="action-button" data-action="set-break" data-lesson-id="${lesson.id}">Pausa</button>
                                <button type="button" class="action-button" data-action="set-end" data-lesson-id="${lesson.id}">Fine</button>
                            </div>
                            <div class="meeting-diagnostics-note">Le correzioni vengono registrate nel database come review action e aggiornano il draft. Per i vecchi import senza segmenti grezzi, i marker richiedono un reimport.</div>
                            <div class="review-actions">
                                ${this._renderReviewActions(lesson.review_actions || [])}
                            </div>
                        </div>
                    </details>
                    <table class="participants-table">
                        <thead>
                            <tr>
                                <th>Persona</th>
                                <th>Prima metà</th>
                                <th>Seconda metà</th>
                                <th>Stato</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${visibleParticipants.map((participant) => `
                                <tr>
                                    <td>
                                        <strong>${this._escapeHtml(participant.canonical_full_name)}</strong><br>
                                        <span class="hint">${this._escapeHtml(participant.email || 'senza email')}</span>
                                    </td>
                                    <td class="percent-cell">
                                        ${this._renderPercentCell(participant.minutes_first_half, participant.duration_first_half, threshold)}
                                    </td>
                                    <td class="percent-cell">
                                        ${this._renderPercentCell(participant.minutes_second_half, participant.duration_second_half, threshold)}
                                    </td>
                                    <td>
                                        <span class="presence-tag ${this._escapeHtml(participant.final_presence_status)}${participant.manual_override_presence_status ? ' manual' : ''}">${this._escapeHtml(participant.final_presence_status)}</span>
                                        <div class="row-actions">
                                            ${participant.final_presence_status !== 'presente' ? `<button type="button" class="mini-action good" data-participant-action="set-presente" data-lesson-id="${lesson.id}" data-participant-id="${participant.id}">Dai presenza</button>` : ''}
                                            ${participant.manual_override_presence_status ? `<button type="button" class="mini-action neutral" data-participant-action="clear-presence" data-lesson-id="${lesson.id}" data-participant-id="${participant.id}">Reset override</button>` : ''}
                                        </div>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                    ${presentParticipants.length > 0 ? `
                        <div class="present-list">
                            <div class="present-list-title">Presenti</div>
                            <div class="present-list-body">${presentParticipants.map((participant) => this._escapeHtml(participant.canonical_full_name)).join(', ')}</div>
                        </div>
                    ` : ''}
                </div>
            </article>
        `;
        this._wireLessonActionButtons(lesson);
    },

    _wireLessonActionButtons(lesson) {
        this._els.lessonsContainer.querySelectorAll('[data-action]').forEach((button) => {
            button.addEventListener('click', async () => {
                const action = button.getAttribute('data-action');
                if (action === 'set-threshold') {
                    await this._promptAndSaveThreshold(lesson);
                    return;
                }
                if (action === 'set-start' || action === 'set-break' || action === 'set-end') {
                    await this._promptAndSaveMarker(lesson, action);
                }
            });
        });
        this._els.lessonsContainer.querySelectorAll('[data-participant-action]').forEach((button) => {
            button.addEventListener('click', async () => {
                const action = button.getAttribute('data-participant-action');
                const participantId = Number(button.getAttribute('data-participant-id'));
                if (action === 'set-presente') {
                    await this._createLessonReviewAction(
                        lesson.id,
                        'set_manual_presence_status',
                        { presence_status: 'presente' },
                        participantId,
                    );
                    return;
                }
                if (action === 'clear-presence') {
                    await this._createLessonReviewAction(
                        lesson.id,
                        'clear_manual_presence_status',
                        {},
                        participantId,
                    );
                }
            });
        });
    },

    async _promptAndSaveThreshold(lesson) {
        const current = `${Math.round((lesson.threshold_ratio || 0) * 100)}`;
        const raw = window.prompt('Nuovo threshold (es. 75 oppure 0.75)', current);
        if (raw === null) return;
        const threshold = this._parseThresholdInput(raw);
        if (threshold === null) {
            window.alert('Threshold non valido.');
            return;
        }
        await this._createLessonReviewAction(lesson.id, 'set_threshold_ratio', { threshold_ratio: threshold });
    },

    async _promptAndSaveMarker(lesson, action) {
        const mapping = {
            'set-start': { label: 'inizio utile', field: 'effective_start_at', type: 'set_effective_start' },
            'set-break': { label: 'pausa', field: 'break_point_at', type: 'set_break_point' },
            'set-end': { label: 'fine utile', field: 'effective_end_at', type: 'set_effective_end' },
        };
        const config = mapping[action];
        const current = lesson[config.field] ? this._formatTime(lesson[config.field]) : '';
        const raw = window.prompt(`Nuovo orario per ${config.label} (HH:MM)`, current);
        if (raw === null) return;
        const iso = this._buildIsoForLessonTime(lesson, raw);
        if (!iso) {
            window.alert('Orario non valido. Usa HH:MM.');
            return;
        }
        await this._createLessonReviewAction(lesson.id, config.type, { at: iso });
    },

    async _createLessonReviewAction(lessonId, actionType, payload, participantId = null) {
        try {
            const response = await fetch(`/api/attendance/lessons/${lessonId}/review-actions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    action_type: actionType,
                    payload,
                    created_by: 'drafts-ui',
                    participant_id: participantId,
                }),
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.detail || 'Impossibile salvare la correzione.');
            }
            await this._loadLessonDetail(lessonId);
        } catch (error) {
            console.error(error);
            window.alert(error.message);
        }
    },

    async _setLessonIgnored(lessonId, isIgnored) {
        try {
            const response = await fetch(`/api/attendance/lessons/${lessonId}/ignore`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ is_ignored: isIgnored }),
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'Impossibile aggiornare la lezione.');
            await this._reloadCurrentBatch(lessonId);
        } catch (error) {
            console.error(error);
            window.alert(error.message);
        }
    },

    async _setLessonStatus(lessonId, status) {
        try {
            const response = await fetch(`/api/attendance/lessons/${lessonId}/status`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status }),
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'Impossibile aggiornare lo stato della lezione.');
            await this._reloadCurrentBatch(lessonId);
        } catch (error) {
            console.error(error);
            window.alert(error.message);
        }
    },

    async _reloadCurrentBatch(preferredLessonId = null) {
        if (!this._selectedBatchId) return;
        const response = await fetch(`/api/attendance/import-batches/${this._selectedBatchId}`);
        const payload = await response.json();
        if (!response.ok) {
            throw new Error(payload.detail || 'Impossibile ricaricare il batch.');
        }
        this._renderBatchSummary(payload.batch);
        this._renderLessonList(payload.lessons || []);
        const visibleLessons = this._filterLessons(payload.lessons || []);
        const nextLesson = visibleLessons.find((lesson) => lesson.id === preferredLessonId) || visibleLessons[0];
        if (nextLesson) {
            await this._loadLessonDetail(nextLesson.id);
        } else {
            this._selectedLessonId = null;
            this._els.lessonsContainer.innerHTML = '<div class="empty">Nessuna lezione nel filtro corrente.</div>';
        }
    },

    _renderReviewActions(actions) {
        if (!actions.length) {
            return '<div class="empty">Nessuna correzione registrata per questa lezione.</div>';
        }

        const activeTypes = new Set();
        return actions.map((action) => {
            const actionScope = action.participant_id ? `${action.action_type}:${action.participant_id}` : action.action_type;
            const isActive = !activeTypes.has(actionScope);
            if (isActive) activeTypes.add(actionScope);
            return `
            <article class="review-action-item${isActive ? ' active' : ''}">
                ${isActive ? '<div class="review-action-badge">Attiva nel draft</div>' : ''}
                <div class="review-action-top">
                    <span class="review-action-type">${this._escapeHtml(action.action_type)}</span>
                    <span class="review-action-meta">${this._escapeHtml(this._formatDateTime(action.created_at))}${action.created_by ? ` · ${this._escapeHtml(action.created_by)}` : ''}</span>
                </div>
                <div class="review-action-payload">${this._escapeHtml(JSON.stringify(action.payload, null, 2))}</div>
            </article>
        `;
        }).join('');
    },

    _buildTimelineBar(point, peak, referenceValue) {
        const ratio = peak > 0 ? point.active_count / peak : 0;
        const height = Math.max(10, Math.round(ratio * 88));
        const tooltip = `${this._formatDateTime(point.timestamp, referenceValue)} · ${point.active_count} presenti`;
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

    _buildIsoForLessonTime(lesson, hhmm) {
        const match = String(hhmm || '').trim().match(/^(\d{1,2}):(\d{2})$/);
        if (!match) return null;
        const hours = Number(match[1]);
        const minutes = Number(match[2]);
        if (hours < 0 || hours > 23 || minutes < 0 || minutes > 59) return null;
        const base = new Date(lesson.meeting_start_at);
        if (Number.isNaN(base.getTime())) return null;
        base.setHours(hours, minutes, 0, 0);
        return base.toISOString();
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

    _renderPercentCell(minutes, duration, threshold) {
        const pct = duration > 0 ? minutes / duration : 0;
        const pctRounded = Math.round(pct * 100);
        const missingMinutes = Math.max(0, (duration * threshold) - minutes);
        const isPositive = pct >= (threshold - 0.000001);
        const isBorderline = !isPositive && ((threshold - pct) <= 0.02 || missingMinutes <= 5);
        const tone = isPositive ? 'positive' : isBorderline ? 'borderline' : 'negative';
        return `
            <div class="percent-big ${tone}">${pctRounded}%</div>
            <div class="percent-meta">${isBorderline ? 'borderline' : `soglia ${Math.round(threshold * 100)}%`}</div>
        `;
    },

    _formatDateTime(value, referenceValue = null) {
        const date = this._coerceDateWithReference(value, referenceValue);
        return date.toLocaleString('it-CH', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
        });
    },

    _formatTime(value, referenceValue = null) {
        const date = this._coerceDateWithReference(value, referenceValue);
        return date.toLocaleTimeString('it-CH', {
            hour: '2-digit',
            minute: '2-digit',
        });
    },

    _coerceDateWithReference(value, referenceValue = null) {
        const raw = String(value ?? '');
        const hasExplicitOffset = /(?:Z|[+\-]\d{2}:\d{2})$/.test(raw);
        if (hasExplicitOffset || !referenceValue) {
            return new Date(raw);
        }

        const reference = String(referenceValue ?? '');
        const offsetMatch = reference.match(/(Z|[+\-]\d{2}:\d{2})$/);
        if (!offsetMatch) {
            return new Date(raw);
        }
        return new Date(`${raw}${offsetMatch[1]}`);
    },

    _formatMinutes(value) {
        return Number(value || 0).toFixed(1);
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
    DraftImportsApp.init().catch((error) => console.error(error));
});
