'use strict';

const DraftImportsApp = {
    async init() {
        this._els = {
            batchList: document.getElementById('batchList'),
            batchSummary: document.getElementById('batchSummary'),
            batchFilters: document.getElementById('batchFilters'),
            lessonFilters: document.getElementById('lessonFilters'),
            lessonList: document.getElementById('lessonList'),
            lessonsContainer: document.getElementById('lessonsContainer'),
        };
        this._batchScope = 'open';
        this._lessonFilter = 'draft';

        await this._loadBatches();
    },

    async _loadBatches(preferredBatchId = null, preferredLessonId = null) {
        this._els.batchList.innerHTML = '<div class="empty">Carico gli import batch...</div>';
        this._els.batchSummary.innerHTML = '';
        this._els.lessonList.innerHTML = '';
        this._els.lessonsContainer.innerHTML = '<div class="empty">Seleziona un import batch.</div>';
        this._renderBatchFilters();

        try {
            const response = await fetch(`/api/attendance/import-batches?scope=${encodeURIComponent(this._batchScope)}`, { cache: 'no-store' });
            const payload = await this._readApiPayload(response);
            if (!response.ok) {
                throw new Error(payload.detail || 'Impossibile leggere gli import batch.');
            }

            this._batches = payload.batches || [];
            this._renderBatchList();

            if (this._batches.length > 0) {
                const nextBatch = this._batches.find((batch) => batch.id === preferredBatchId) || this._batches[0];
                await this._loadBatchDetail(nextBatch.id, preferredLessonId);
            } else {
                this._els.batchList.innerHTML = '<div class="empty">Nessun import batch nel filtro corrente.</div>';
                this._els.batchSummary.innerHTML = '';
            }
        } catch (error) {
            console.error(error);
            this._els.batchList.innerHTML = `<div class="empty">${this._escapeHtml(error.message)}</div>`;
        }
    },

    _renderBatchFilters() {
        const filters = [
            ['open', 'Aperti'],
            ['closed', 'Chiusi'],
            ['all', 'Tutti'],
        ];
        this._els.batchFilters.innerHTML = filters.map(([key, label]) => `
            <button type="button" class="filter-chip${this._batchScope === key ? ' active' : ''}" data-batch-scope="${key}">
                ${label}
            </button>
        `).join('');
        this._els.batchFilters.querySelectorAll('[data-batch-scope]').forEach((button) => {
            button.addEventListener('click', async () => {
                this._batchScope = button.getAttribute('data-batch-scope') || 'open';
                await this._loadBatches();
            });
        });
    },

    _renderBatchList() {
        if (!this._batches || this._batches.length === 0) {
            return;
        }

        this._els.batchList.innerHTML = this._batches.map((batch) => `
            <div class="batch-card">
                <button class="batch-delete" type="button" data-batch-action="delete-batch" data-batch-id="${batch.id}" title="Elimina batch" aria-label="Elimina batch ${batch.id}">×</button>
                <button class="batch-item${this._selectedBatchId === batch.id ? ' active' : ''}" data-batch-id="${batch.id}" type="button">
                    <div class="batch-title">
                        <span class="batch-id">#${batch.id}</span>
                        <span class="batch-file-name" title="${this._escapeAttr(batch.source_file_name)}">${this._escapeHtml(batch.source_file_name)}</span>
                    </div>
                    <div class="batch-meta">
                        ${this._escapeHtml(this._formatDateTime(batch.created_at))} · ${batch.lessons_count} lezioni · ${batch.participants_count} partecipanti
                    </div>
                </button>
            </div>
        `).join('');

        this._els.batchList.querySelectorAll('[data-batch-id]').forEach((button) => {
            button.addEventListener('click', async () => {
                const batchId = Number(button.getAttribute('data-batch-id'));
                await this._loadBatchDetail(batchId);
            });
        });
        this._els.batchList.querySelectorAll('[data-batch-action="delete-batch"]').forEach((button) => {
            button.addEventListener('click', async (event) => {
                event.stopPropagation();
                const batchId = Number(button.getAttribute('data-batch-id'));
                await this._deleteBatch(batchId);
            });
        });
    },

    async _loadBatchDetail(batchId, preferredLessonId = null) {
        this._selectedBatchId = batchId;
        this._selectedLessonId = null;
        this._renderBatchList();
        this._els.batchSummary.innerHTML = '';
        this._els.lessonList.innerHTML = '<div class="empty">Carico la lista lezioni...</div>';
        this._els.lessonsContainer.innerHTML = '<div class="empty">Carico il dettaglio del batch...</div>';

        try {
            const response = await fetch(`/api/attendance/import-batches/${batchId}`, { cache: 'no-store' });
            const payload = await this._readApiPayload(response);
            if (!response.ok) {
                throw new Error(payload.detail || 'Impossibile leggere il dettaglio del batch.');
            }

            this._renderBatchSummary(payload.batch);
            this._renderLessonList(payload.lessons || []);
            const visibleLessons = this._filterLessons(payload.lessons || []);
            if (visibleLessons.length > 0) {
                const nextLesson = visibleLessons.find((lesson) => lesson.id === preferredLessonId) || visibleLessons[0];
                await this._loadLessonDetail(nextLesson.id);
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
            <div class="batch-strip-left">
                <button class="batch-delete" type="button" data-batch-action="delete-batch" data-batch-id="${this._escapeAttr(batch.id)}" title="Elimina batch" aria-label="Elimina batch ${this._escapeAttr(batch.id)}">×</button>
                <div class="batch-strip-title">
                    <span class="batch-id">#${this._escapeHtml(batch.id)}</span>
                    <span class="batch-strip-file-name" title="${this._escapeAttr(batch.source_file_name)}">${this._escapeHtml(batch.source_file_name)}</span>
                </div>
            </div>
            <div class="batch-strip-meta">
                <span><strong>${this._escapeHtml(batch.lessons_count)}</strong> lezioni</span>
                <span><strong>${this._escapeHtml(batch.participants_count)}</strong> partecipanti</span>
                <span>${this._escapeHtml(this._formatDateTime(batch.created_at))}</span>
            </div>
        `;
        this._els.batchSummary.querySelectorAll('[data-batch-action="delete-batch"]').forEach((button) => {
            button.addEventListener('click', async (event) => {
                event.stopPropagation();
                const batchId = Number(button.getAttribute('data-batch-id'));
                await this._deleteBatch(batchId);
            });
        });
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
                        <button class="mini-action neutral" type="button" data-lesson-action="delete-lesson" data-lesson-id="${lesson.id}">Elimina</button>
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
                    return;
                }
                if (action === 'delete-lesson') {
                    await this._deleteLesson(lessonId);
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
            const response = await fetch(`/api/attendance/lessons/${lessonId}`, { cache: 'no-store' });
            const payload = await this._readApiPayload(response);
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
        const visibleParticipants = participants.filter((participant) => participant.final_presence_status !== 'presente');
        const presentParticipants = participants.filter((participant) => participant.final_presence_status === 'presente');
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
                        <div class="marker-setter" data-marker-setter="1">
                            <div class="marker-setter-main">
                                <span class="marker-setter-label">Imposta</span>
                                <button type="button" class="marker-button" data-marker-mode="set-start">inizio</button>
                                <button type="button" class="marker-button" data-marker-mode="set-break">pausa</button>
                                <button type="button" class="marker-button" data-marker-mode="set-end">fine</button>
                            </div>
                            <span class="marker-setter-hint" data-marker-hint>scegli cosa impostare, poi clicca sul grafico</span>
                        </div>
                        <div class="meeting-chart" data-marker-chart="1" data-lesson-id="${lesson.id}">
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
                            <div class="alias-merge-box">
                                <div class="alias-merge-title">Unisci identità</div>
                                <div class="alias-merge-grid">
                                    <select id="aliasCanonicalSelect">
                                        <option value="">Identità canonica</option>
                                        ${participants.map((participant) => `<option value="${participant.id}">${this._escapeHtml(this._participantOptionLabel(participant))}</option>`).join('')}
                                    </select>
                                    <select id="aliasSourceSelect">
                                        <option value="">Alias da unire</option>
                                        ${participants.map((participant) => `<option value="${participant.id}">${this._escapeHtml(this._participantOptionLabel(participant))}</option>`).join('')}
                                    </select>
                                </div>
                                <div class="alias-merge-actions">
                                    <button type="button" class="action-button" data-action="merge-alias" data-lesson-id="${lesson.id}">Unisci</button>
                                    <span class="alias-merge-note">Salva la regola identità nel database e ricompone subito questa lezione draft.</span>
                                </div>
                            </div>
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
                                            <button type="button" class="source-button" data-source-detail="${participant.id}">Origine</button>
                                            ${this._renderPresenceOverrideControl(lesson.id, participant)}
                                        </div>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                    ${presentParticipants.length > 0 ? `
                            <div class="present-list">
                            <div class="present-list-title">Presenti</div>
                            <div class="present-list-items">
                                ${presentParticipants.map((participant) => `
                                    <div class="present-chip">
                                        <span class="present-chip-name">${this._escapeHtml(participant.canonical_full_name)}</span>
                                        ${participant.manual_override_presence_status ? this._renderPresenceOverrideControl(lesson.id, participant) : ''}
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}
                </div>
            </article>
            <div id="sourceModalHost"></div>
        `;
        this._wireLessonActionButtons(lesson);
    },

    _wireLessonActionButtons(lesson) {
        this._wireMarkerSetter(lesson);
        this._els.lessonsContainer.querySelectorAll('[data-action]').forEach((button) => {
            button.addEventListener('click', async () => {
                const action = button.getAttribute('data-action');
                if (action === 'set-threshold') {
                    await this._promptAndSaveThreshold(lesson);
                    return;
                }
                if (action === 'set-start' || action === 'set-break' || action === 'set-end') {
                    await this._promptAndSaveMarker(lesson, action);
                    return;
                }
                if (action === 'merge-alias') {
                    await this._createIdentityAliasFromLesson(lesson);
                }
            });
        });
        this._els.lessonsContainer.querySelectorAll('[data-presence-override]').forEach((select) => {
            select.addEventListener('change', async () => {
                const participantId = Number(select.getAttribute('data-participant-id'));
                const value = select.value;
                if (value === 'auto') {
                    await this._createLessonReviewAction(
                        lesson.id,
                        'clear_manual_presence_status',
                        {},
                        participantId,
                    );
                    return;
                }
                await this._createLessonReviewAction(
                    lesson.id,
                    'set_manual_presence_status',
                    { presence_status: value },
                    participantId,
                );
            });
        });
        this._els.lessonsContainer.querySelectorAll('[data-source-detail]').forEach((button) => {
            button.addEventListener('click', () => {
                const participantId = Number(button.getAttribute('data-source-detail'));
                const participant = lesson.participants.find((item) => item.id === participantId);
                if (participant) {
                    this._openSourceModal(lesson, participant);
                }
            });
        });
    },

    _wireMarkerSetter(lesson) {
        let markerMode = null;
        const chart = this._els.lessonsContainer.querySelector('[data-marker-chart]');
        const buttons = Array.from(this._els.lessonsContainer.querySelectorAll('[data-marker-mode]'));
        const hint = this._els.lessonsContainer.querySelector('[data-marker-hint]');
        const actionConfig = {
            'set-start': { label: 'inizio', type: 'set_effective_start' },
            'set-break': { label: 'pausa', type: 'set_break_point' },
            'set-end': { label: 'fine', type: 'set_effective_end' },
        };

        if (!chart || buttons.length === 0) return;

        const setMode = (nextMode) => {
            markerMode = markerMode === nextMode ? null : nextMode;
            buttons.forEach((button) => {
                button.classList.toggle('active', button.getAttribute('data-marker-mode') === markerMode);
            });
            chart.classList.toggle('setting-mode', Boolean(markerMode));
            if (hint) {
                hint.textContent = markerMode
                    ? `clicca sul grafico per impostare ${actionConfig[markerMode].label}`
                    : 'scegli cosa impostare, poi clicca sul grafico';
            }
        };

        buttons.forEach((button) => {
            button.addEventListener('click', () => {
                setMode(button.getAttribute('data-marker-mode'));
            });
        });

        chart.addEventListener('mousemove', (event) => {
            if (!markerMode || !hint) return;
            const iso = this._buildIsoFromChartClick(lesson, chart, event.clientX);
            hint.textContent = `${actionConfig[markerMode].label}: ${this._formatTime(iso, lesson.meeting_start_at)} · click per salvare`;
        });

        chart.addEventListener('mouseleave', () => {
            if (!markerMode || !hint) return;
            hint.textContent = `clicca sul grafico per impostare ${actionConfig[markerMode].label}`;
        });

        chart.addEventListener('click', async (event) => {
            if (!markerMode) return;
            const config = actionConfig[markerMode];
            const iso = this._buildIsoFromChartClick(lesson, chart, event.clientX);
            setMode(null);
            await this._createLessonReviewAction(lesson.id, config.type, { at: iso });
        });
    },

    async _createIdentityAliasFromLesson(lesson) {
        const canonicalSelect = document.getElementById('aliasCanonicalSelect');
        const aliasSelect = document.getElementById('aliasSourceSelect');
        const canonicalId = Number(canonicalSelect?.value || 0);
        const aliasId = Number(aliasSelect?.value || 0);
        if (!canonicalId || !aliasId) {
            window.alert('Seleziona identità e alias da unire.');
            return;
        }
        if (canonicalId === aliasId) {
            window.alert('Identità e alias devono essere diversi.');
            return;
        }
        const canonicalParticipant = lesson.participants.find((participant) => participant.id === canonicalId);
        const aliasParticipant = lesson.participants.find((participant) => participant.id === aliasId);
        if (!canonicalParticipant || !aliasParticipant) {
            window.alert('Partecipanti non trovati.');
            return;
        }
        try {
            const response = await fetch('/api/attendance/identity-aliases', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    canonical_participant_id: canonicalParticipant.id,
                    alias_participant_id: aliasParticipant.id,
                    canonical_full_name: canonicalParticipant.canonical_full_name,
                    canonical_email: canonicalParticipant.email,
                    alias_full_name: aliasParticipant.canonical_full_name,
                    alias_email: aliasParticipant.email,
                    lesson_id: lesson.id,
                    created_by: 'drafts-ui',
                    notes: `Creato dalla lesson ${lesson.id}`,
                }),
            });
            const data = await this._readApiPayload(response);
            if (!response.ok) throw new Error(data.detail || 'Impossibile registrare l\'alias.');
            canonicalSelect.value = '';
            aliasSelect.value = '';
            await this._reloadCurrentBatch(lesson.id);
            if (data.participants_count !== null && data.participants_count !== undefined) {
                window.alert(`Alias registrato: "${aliasParticipant.canonical_full_name}" -> "${canonicalParticipant.canonical_full_name}". Partecipanti attuali nella lezione: ${data.participants_count}.`);
            } else {
                window.alert(`Alias registrato: "${aliasParticipant.canonical_full_name}" -> "${canonicalParticipant.canonical_full_name}". La lezione viene ricostruita subito.`);
            }
        } catch (error) {
            console.error(error);
            window.alert(error.message);
        }
    },

    _participantOptionLabel(participant) {
        return participant.email
            ? `${participant.canonical_full_name} (${participant.email})`
            : participant.canonical_full_name;
    },

    _renderPresenceOverrideControl(lessonId, participant) {
        const currentValue = participant.manual_override_presence_status || 'auto';
        return `
            <select class="override-select" data-presence-override="1" data-lesson-id="${lessonId}" data-participant-id="${participant.id}">
                <option value="auto"${currentValue === 'auto' ? ' selected' : ''}>Automatico</option>
                <option value="presente"${currentValue === 'presente' ? ' selected' : ''}>Presente</option>
                <option value="prima_meta"${currentValue === 'prima_meta' ? ' selected' : ''}>Prima metà</option>
                <option value="seconda_meta"${currentValue === 'seconda_meta' ? ' selected' : ''}>Seconda metà</option>
                <option value="assente"${currentValue === 'assente' ? ' selected' : ''}>Assente</option>
            </select>
        `;
    },

    _openSourceModal(lesson, participant) {
        const host = document.getElementById('sourceModalHost');
        if (!host) return;
        this._closeSourceModal();
        const sources = this._getParticipantIdentitySources(lesson, participant);
        host.innerHTML = `
            <div class="source-modal-backdrop" data-source-modal-close="1">
                <div class="source-modal" role="dialog" aria-modal="true" aria-labelledby="sourceModalTitle">
                    <div class="source-modal-head">
                        <div>
                            <h4 id="sourceModalTitle" class="source-modal-title">Origine record</h4>
                            <div class="source-modal-subtitle">
                                ${this._escapeHtml(participant.canonical_full_name)} · ${this._escapeHtml(lesson.course_name)} · ${this._escapeHtml(lesson.lesson_date)}
                            </div>
                        </div>
                        <button type="button" class="source-modal-close" data-source-modal-close="1" aria-label="Chiudi dettaglio origine">×</button>
                    </div>
                    <div class="source-modal-body">
                        ${sources.map((source) => `
                            <section class="source-group">
                                <div class="source-group-head">
                                    <div>
                                        <div class="source-name">${this._escapeHtml(source.raw_full_name || participant.canonical_full_name)}</div>
                                        <div class="source-email">${this._escapeHtml(source.email || 'senza email')}</div>
                                    </div>
                                    <div class="source-count">${source.segments.length} segment${source.segments.length === 1 ? 'o' : 'i'}</div>
                                </div>
                                <div class="source-segments">
                                    ${source.segments.length > 0 ? source.segments.map((segment) => `
                                        <div class="source-segment">
                                            ${this._escapeHtml(this._formatDateTime(segment[0], lesson.meeting_start_at))} → ${this._escapeHtml(this._formatDateTime(segment[1], lesson.meeting_start_at))}
                                        </div>
                                    `).join('') : '<div class="source-empty">Nessun segmento salvato.</div>'}
                                </div>
                            </section>
                        `).join('')}
                    </div>
                </div>
            </div>
        `;

        host.querySelectorAll('[data-source-modal-close]').forEach((node) => {
            node.addEventListener('click', (event) => {
                if (event.target === node || node.classList.contains('source-modal-close')) {
                    this._closeSourceModal();
                }
            });
        });
        document.addEventListener('keydown', this._handleSourceModalEscape);
        this._sourceModalHost = host;
    },

    _getParticipantIdentitySources(lesson, participant) {
        const normalizedCanonicalName = String(participant?.canonical_full_name || '').trim().toLowerCase();
        const sameNameParticipants = Array.isArray(lesson?.participants)
            ? lesson.participants.filter((item) => String(item?.canonical_full_name || '').trim().toLowerCase() === normalizedCanonicalName)
            : [participant];
        const grouped = new Map();

        sameNameParticipants.forEach((item) => {
            const sources = this._extractIdentitySources(item);
            sources.forEach((source) => {
                const rawFullName = String(source.raw_full_name || item.raw_full_name || item.canonical_full_name).trim();
                const email = String(source.email || item.email || '').trim();
                const key = `${rawFullName.toLowerCase()}::${email.toLowerCase()}`;
                const entry = grouped.get(key) || {
                    raw_full_name: rawFullName,
                    email,
                    segments: [],
                };
                (Array.isArray(source.segments) ? source.segments : []).forEach((segment) => {
                    if (Array.isArray(segment) && segment.length === 2) {
                        entry.segments.push([segment[0], segment[1]]);
                    }
                });
                grouped.set(key, entry);
            });
        });

        if (grouped.size === 0) {
            return [{
                raw_full_name: String(participant.raw_full_name || participant.canonical_full_name).trim(),
                email: String(participant.email || '').trim(),
                segments: Array.isArray(participant?.metadata?.segments)
                    ? participant.metadata.segments.filter((segment) => Array.isArray(segment) && segment.length === 2)
                    : [],
            }];
        }

        return Array.from(grouped.values())
            .map((entry) => ({
                raw_full_name: entry.raw_full_name,
                email: entry.email,
                segments: this._dedupeAndSortSegments(entry.segments),
            }))
            .sort((left, right) => {
                const leftFirst = left.segments[0]?.[0] || '';
                const rightFirst = right.segments[0]?.[0] || '';
                return leftFirst.localeCompare(rightFirst) || left.raw_full_name.localeCompare(right.raw_full_name);
            });
    },

    _extractIdentitySources(participant) {
        const sourceDetails = participant?.source_details;
        if (Array.isArray(sourceDetails) && sourceDetails.length > 0) {
            return sourceDetails.map((source) => ({
                raw_full_name: String(source.raw_full_name || participant.raw_full_name || participant.canonical_full_name).trim(),
                email: String(source.email || participant.email || '').trim(),
                segments: Array.isArray(source.segments) ? source.segments.filter((segment) => Array.isArray(segment) && segment.length === 2) : [],
            }));
        }
        const sources = participant?.metadata?.identity_sources;
        if (Array.isArray(sources) && sources.length > 0) {
            return sources.map((source) => ({
                raw_full_name: String(source.raw_full_name || participant.raw_full_name || participant.canonical_full_name).trim(),
                email: String(source.email || participant.email || '').trim(),
                segments: Array.isArray(source.segments) ? source.segments.filter((segment) => Array.isArray(segment) && segment.length === 2) : [],
            }));
        }
        return [{
            raw_full_name: String(participant.raw_full_name || participant.canonical_full_name).trim(),
            email: String(participant.email || '').trim(),
            segments: Array.isArray(participant?.metadata?.segments)
                ? participant.metadata.segments.filter((segment) => Array.isArray(segment) && segment.length === 2)
                : [],
        }];
    },

    _dedupeAndSortSegments(segments) {
        const seen = new Set();
        const unique = [];
        segments.forEach((segment) => {
            if (!Array.isArray(segment) || segment.length !== 2) return;
            const key = `${segment[0]}::${segment[1]}`;
            if (seen.has(key)) return;
            seen.add(key);
            unique.push([segment[0], segment[1]]);
        });
        unique.sort((left, right) => String(left[0]).localeCompare(String(right[0])) || String(left[1]).localeCompare(String(right[1])));
        return unique;
    },

    _handleSourceModalEscape: (event) => {
        if (event.key === 'Escape' && DraftImportsApp._sourceModalHost) {
            DraftImportsApp._closeSourceModal();
        }
    },

    _closeSourceModal() {
        if (!this._sourceModalHost) return;
        this._sourceModalHost.innerHTML = '';
        this._sourceModalHost = null;
        document.removeEventListener('keydown', this._handleSourceModalEscape);
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
            const data = await this._readApiPayload(response);
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
            const data = await this._readApiPayload(response);
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
            const data = await this._readApiPayload(response);
            if (!response.ok) throw new Error(data.detail || 'Impossibile aggiornare lo stato della lezione.');
            await this._reloadCurrentBatch(lessonId);
        } catch (error) {
            console.error(error);
            window.alert(error.message);
        }
    },

    async _deleteLesson(lessonId) {
        if (!window.confirm('Eliminare questa lezione dal batch? Verranno rimossi anche partecipanti e correzioni collegate.')) {
            return;
        }
        try {
            const response = await fetch(`/api/attendance/lessons/${lessonId}/delete`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            });
            const data = await this._readApiPayload(response);
            if (!response.ok) throw new Error(data.detail || 'Impossibile eliminare la lezione.');
            await this._loadBatches(this._selectedBatchId, null);
        } catch (error) {
            console.error(error);
            window.alert(error.message);
        }
    },

    async _deleteBatch(batchId) {
        if (!window.confirm('Eliminare questo batch per sempre? Verranno rimossi anche tutte le lezioni, i partecipanti e le correzioni collegate.')) {
            return;
        }
        try {
            const response = await fetch(`/api/attendance/import-batches/${batchId}/delete`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            });
            const data = await this._readApiPayload(response);
            if (!response.ok) throw new Error(data.detail || 'Impossibile eliminare il batch.');
            await this._loadBatches();
        } catch (error) {
            console.error(error);
            window.alert(error.message);
        }
    },

    async _reloadCurrentBatch(preferredLessonId = null) {
        if (!this._selectedBatchId) return;
        const response = await fetch(`/api/attendance/import-batches/${this._selectedBatchId}`, { cache: 'no-store' });
        const payload = await this._readApiPayload(response);
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

    _buildIsoFromChartClick(lesson, chart, clientX) {
        const rect = chart.getBoundingClientRect();
        const startMs = new Date(lesson.meeting_start_at).getTime();
        const endMs = new Date(lesson.meeting_end_at).getTime();
        if (!Number.isFinite(startMs) || !Number.isFinite(endMs) || endMs <= startMs || rect.width <= 0) {
            return lesson.meeting_start_at;
        }
        const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
        const totalMinutes = (endMs - startMs) / 60000;
        const snappedMinutes = Math.max(0, Math.min(totalMinutes, Math.round((totalMinutes * ratio) / 5) * 5));
        return this._buildIsoFromTimestampForLesson(lesson, startMs + snappedMinutes * 60000);
    },

    _buildIsoFromTimestampForLesson(lesson, timestampMs) {
        const selected = new Date(timestampMs);
        return selected.toISOString();
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

    async _readApiPayload(response) {
        const text = await response.text();
        try {
            return text ? JSON.parse(text) : {};
        } catch {
            return {
                detail: text || `Risposta non valida dal server (${response.status})`,
            };
        }
    },

    _renderPercentCell(minutes, duration, threshold) {
        const pct = duration > 0 ? minutes / duration : 0;
        const pctPercent = pct * 100;
        const thresholdPercent = threshold * 100;
        const missingMinutes = Math.max(0, (duration * threshold) - minutes);
        const isPositive = pct >= (threshold - 0.000001);
        const isBorderline = !isPositive && ((threshold - pct) <= 0.02 || missingMinutes <= 5);
        const tone = isPositive ? 'positive' : isBorderline ? 'borderline' : 'negative';
        const shouldShowDecimal = Math.abs(pctPercent - thresholdPercent) < 1.05;
        const pctDisplay = shouldShowDecimal ? `${pctPercent.toFixed(1)}%` : `${Math.round(pctPercent)}%`;
        return `
            <div class="percent-big ${tone}">${pctDisplay}</div>
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

    _escapeAttr(value) {
        return this._escapeHtml(value);
    },
};

document.addEventListener('DOMContentLoaded', () => {
    DraftImportsApp.init().catch((error) => console.error(error));
});
