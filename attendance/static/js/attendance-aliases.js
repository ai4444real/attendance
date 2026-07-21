'use strict';

const AttendanceAliasesApp = {
    async init() {
        this._els = {
            aliasesMeta: document.getElementById('aliasesMeta'),
            aliasesBody: document.getElementById('aliasesBody'),
            rebuildAliasesButton: document.getElementById('rebuildAliasesButton'),
            rebuildAliasesResult: document.getElementById('rebuildAliasesResult'),
            identitySearchInput: document.getElementById('identitySearchInput'),
            identitySearchButton: document.getElementById('identitySearchButton'),
            identitySearchResult: document.getElementById('identitySearchResult'),
            canonicalCandidates: document.getElementById('canonicalCandidates'),
            aliasCandidates: document.getElementById('aliasCandidates'),
            canonicalPreview: document.getElementById('canonicalPreview'),
            aliasPreview: document.getElementById('aliasPreview'),
            createAliasFromCandidatesButton: document.getElementById('createAliasFromCandidatesButton'),
            createAliasResult: document.getElementById('createAliasResult'),
        };
        this._identityCandidates = [];
        this._selectedCanonical = null;
        this._selectedAlias = null;

        this._els.rebuildAliasesButton.addEventListener('click', () => {
            this._rebuildAllLessons().catch((error) => {
                console.error(error);
                this._els.rebuildAliasesResult.textContent = error.message || 'Rebuild identità fallito.';
                this._els.rebuildAliasesResult.classList.add('is-error');
            });
        });

        this._els.identitySearchButton.addEventListener('click', () => {
            this._searchIdentityCandidates().catch((error) => {
                console.error(error);
                this._els.identitySearchResult.textContent = error.message || 'Ricerca identità fallita.';
                this._els.identitySearchResult.classList.add('is-error');
            });
        });
        this._els.identitySearchInput.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                this._searchIdentityCandidates().catch((error) => {
                    console.error(error);
                    this._els.identitySearchResult.textContent = error.message || 'Ricerca identità fallita.';
                    this._els.identitySearchResult.classList.add('is-error');
                });
            }
        });
        this._els.canonicalCandidates.addEventListener('click', (event) => {
            const button = event.target.closest('[data-candidate-index]');
            if (!button) return;
            this._selectedCanonical = this._identityCandidates[Number(button.dataset.candidateIndex)];
            this._renderCandidateLists();
            this._renderAliasPreview();
        });
        this._els.aliasCandidates.addEventListener('click', (event) => {
            const button = event.target.closest('[data-candidate-index]');
            if (!button) return;
            this._selectedAlias = this._identityCandidates[Number(button.dataset.candidateIndex)];
            this._renderCandidateLists();
            this._renderAliasPreview();
        });
        this._els.createAliasFromCandidatesButton.addEventListener('click', () => {
            this._createAliasFromCandidates().catch((error) => {
                console.error(error);
                this._els.createAliasResult.textContent = error.message || 'Creazione alias fallita.';
                this._els.createAliasResult.classList.add('is-error');
            });
        });

        this._els.aliasesBody.addEventListener('click', (event) => {
            const button = event.target.closest('[data-action][data-alias-id]');
            if (!button) {
                return;
            }
            const aliasId = Number(button.dataset.aliasId || 0);
            if (!aliasId) {
                return;
            }
            if (button.dataset.action === 'deactivate-alias') {
                this._deactivateAlias(aliasId, button).catch((error) => {
                    console.error(error);
                    window.alert(error.message || 'Impossibile disattivare l’alias.');
                });
            }
            if (button.dataset.action === 'sync-alias-identity') {
                this._syncAliasIdentity(aliasId, button).catch((error) => {
                    console.error(error);
                    window.alert(error.message || 'Sync identità fallito.');
                });
            }
        });

        await this._loadAliases();
        const initialQuery = new URLSearchParams(window.location.search).get('q') || '';
        if (initialQuery.trim().length >= 2) {
            this._els.identitySearchInput.value = initialQuery.trim();
            await this._searchIdentityCandidates();
        }
    },

    async _searchIdentityCandidates() {
        const query = this._els.identitySearchInput.value.trim();
        this._els.identitySearchResult.classList.remove('is-error');
        this._els.createAliasResult.textContent = '';
        this._els.createAliasResult.classList.remove('is-error');
        if (query.length < 2) {
            this._identityCandidates = [];
            this._selectedCanonical = null;
            this._selectedAlias = null;
            this._renderCandidateLists();
            this._renderAliasPreview();
            this._els.identitySearchResult.textContent = 'Scrivi almeno 2 caratteri.';
            return;
        }

        this._els.identitySearchButton.disabled = true;
        this._els.identitySearchResult.textContent = 'Cerco identità...';
        try {
            const response = await fetch(`/api/attendance/identity-candidates?q=${encodeURIComponent(query)}&limit=50`, {
                cache: 'no-store',
            });
            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload.detail || 'Ricerca identità fallita.');
            }
            this._identityCandidates = payload.candidates || [];
            this._selectedCanonical = null;
            this._selectedAlias = null;
            this._renderCandidateLists();
            this._renderAliasPreview();
            this._els.identitySearchResult.textContent = `${this._identityCandidates.length} risultati. Scegli prima il canonico, poi l’alias.`;
        } finally {
            this._els.identitySearchButton.disabled = false;
        }
    },

    _renderCandidateLists() {
        this._els.canonicalCandidates.innerHTML = this._renderCandidateButtons('canonical');
        this._els.aliasCandidates.innerHTML = this._renderCandidateButtons('alias');
    },

    _renderCandidateButtons(role) {
        if (!this._identityCandidates.length) {
            return '<div class="empty">Nessun risultato selezionabile.</div>';
        }
        const selected = role === 'canonical' ? this._selectedCanonical : this._selectedAlias;
        return this._identityCandidates.map((candidate, index) => {
            const isSelected = selected && this._candidateKey(selected) === this._candidateKey(candidate);
            return `
                <button
                    type="button"
                    class="candidate-button${isSelected ? ' is-selected' : ''}"
                    data-candidate-index="${this._escapeAttr(index)}"
                >
                    <strong>${this._escapeHtml(candidate.canonical_full_name)}</strong>
                    <span class="candidate-meta">${this._escapeHtml(candidate.email || 'senza email')}</span>
                    <span class="candidate-meta">${this._escapeHtml(candidate.lessons_count)} lezioni · ${this._escapeHtml(candidate.appearances_count)} record · ultimo ${this._escapeHtml(candidate.last_seen_at)}</span>
                </button>
            `;
        }).join('');
    },

    _renderAliasPreview() {
        this._els.canonicalPreview.innerHTML = this._selectedCanonical
            ? this._renderPreviewCard(this._selectedCanonical)
            : 'Canonico non selezionato';
        this._els.aliasPreview.innerHTML = this._selectedAlias
            ? this._renderPreviewCard(this._selectedAlias)
            : 'Alias non selezionato';
        const canSubmit = this._selectedCanonical
            && this._selectedAlias
            && this._candidateKey(this._selectedCanonical) !== this._candidateKey(this._selectedAlias);
        this._els.createAliasFromCandidatesButton.disabled = !canSubmit;
    },

    _renderPreviewCard(candidate) {
        return `
            <strong>${this._escapeHtml(candidate.canonical_full_name)}</strong><br>
            <span class="hint">${this._escapeHtml(candidate.email || 'senza email')}</span>
        `;
    },

    async _createAliasFromCandidates() {
        if (!this._selectedCanonical || !this._selectedAlias) {
            return;
        }
        if (this._candidateKey(this._selectedCanonical) === this._candidateKey(this._selectedAlias)) {
            throw new Error('Scegli due identità diverse.');
        }
        const canonical = this._selectedCanonical;
        const alias = this._selectedAlias;
        if (!window.confirm(`Unire "${alias.canonical_full_name}" a "${canonical.canonical_full_name}"?`)) {
            return;
        }

        this._els.createAliasFromCandidatesButton.disabled = true;
        this._els.createAliasResult.classList.remove('is-error');
        this._els.createAliasResult.textContent = 'Salvo alias...';
        try {
            const response = await fetch('/api/attendance/identity-aliases', {
                method: 'POST',
                cache: 'no-store',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    canonical_full_name: canonical.canonical_full_name,
                    canonical_email: canonical.email || null,
                    alias_full_name: alias.canonical_full_name,
                    alias_email: alias.email || null,
                    created_by: 'aliases-ui',
                    notes: 'Creato dalla ricerca identità in /attendance/aliases',
                }),
            });
            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload.detail || 'Creazione alias fallita.');
            }
            this._els.createAliasResult.textContent = payload.identity_sync_error
                ? `Alias salvato, ma sync identità fallito: ${payload.identity_sync_error}`
                : 'Alias salvato. Identità collegata. Ora puoi applicare gli alias alle lezioni.';
            this._els.createAliasResult.classList.toggle('is-error', Boolean(payload.identity_sync_error));
            await this._loadAliases();
        } finally {
            this._els.createAliasFromCandidatesButton.disabled = false;
            this._renderAliasPreview();
        }
    },

    async _rebuildAllLessons() {
        if (!window.confirm('Applicare gli alias attivi a tutte le lezioni importate? Verranno ricostruiti solo i nomi/identità dei partecipanti.')) {
            return;
        }

        this._els.rebuildAliasesButton.disabled = true;
        this._els.rebuildAliasesResult.classList.remove('is-error');
        this._els.rebuildAliasesResult.textContent = 'Rebuild identità in corso...';
        try {
            const response = await fetch('/api/attendance/identity-aliases/rebuild-all', {
                method: 'POST',
                cache: 'no-store',
            });
            let payload = {};
            try {
                payload = await response.json();
            } catch (error) {
                payload = {};
            }
            if (!response.ok) {
                throw new Error(payload.detail || 'Rebuild identità fallito.');
            }

            const pieces = [
                `${payload.rebuilt_lessons || 0} lezioni ricostruite`,
                `${payload.skipped_lessons || 0} saltate`,
                `${payload.error_lessons || 0} errori`,
            ];
            this._els.rebuildAliasesResult.textContent = pieces.join(' · ');
        } finally {
            this._els.rebuildAliasesButton.disabled = false;
        }
    },

    async _loadAliases() {
        try {
            const response = await fetch('/api/attendance/identity-aliases');
            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload.detail || 'Impossibile leggere gli alias.');
            }

            const aliases = payload.aliases || [];
            this._renderMeta(aliases);
            this._renderTable(aliases);
        } catch (error) {
            console.error(error);
            this._els.aliasesBody.innerHTML = `<div class="empty">${this._escapeHtml(error.message)}</div>`;
        }
    },

    _renderMeta(aliases) {
        this._els.aliasesMeta.innerHTML = `
            <span class="meta-pill"><strong>${aliases.length}</strong> alias attivi</span>
        `;
    },

    _renderTable(aliases) {
        if (!aliases.length) {
            this._els.aliasesBody.innerHTML = '<div class="empty">Nessun alias registrato nel database.</div>';
            return;
        }

        this._els.aliasesBody.innerHTML = `
            <table class="aliases-table">
                <thead>
                    <tr>
                        <th>Identità canonica</th>
                        <th>Tipo</th>
                        <th>Alias</th>
                        <th>Creato da</th>
                        <th>Creato il</th>
                        <th>Note</th>
                        <th>Identità</th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>
                    ${aliases.map((alias) => `
                        <tr>
                            <td><span class="alias-name">${this._escapeHtml(alias.canonical_full_name)}</span>${alias.canonical_email ? `<br><span class="hint">${this._escapeHtml(alias.canonical_email)}</span>` : ''}</td>
                            <td>${this._escapeHtml(alias.alias_type)}</td>
                            <td>${this._escapeHtml(alias.alias_value)}</td>
                            <td>${this._escapeHtml(alias.created_by || '—')}</td>
                            <td>${this._escapeHtml(this._formatDateTime(alias.created_at))}</td>
                            <td>${this._escapeHtml(alias.notes || '—')}</td>
                            <td>${this._renderIdentityCell(alias)}</td>
                            <td class="actions-cell">
                                <button
                                    type="button"
                                    class="alias-sync-button"
                                    data-action="sync-alias-identity"
                                    data-alias-id="${this._escapeAttr(alias.id)}"
                                    title="Sincronizza identità stabile"
                                    aria-label="Sincronizza identità per alias ${this._escapeAttr(alias.alias_value)}"
                                >Sync</button>
                                <button
                                    type="button"
                                    class="alias-delete-button"
                                    data-action="deactivate-alias"
                                    data-alias-id="${this._escapeAttr(alias.id)}"
                                    title="Disattiva alias"
                                    aria-label="Disattiva alias ${this._escapeAttr(alias.alias_value)}"
                                >×</button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    },

    _renderIdentityCell(alias) {
        return alias.identity_id
            ? `<span class="identity-link">#${this._escapeHtml(alias.identity_id)}</span>`
            : '<span class="identity-missing">non collegata</span>';
    },

    async _syncAliasIdentity(aliasId, button) {
        button.disabled = true;
        const response = await fetch(`/api/attendance/identity-aliases/${aliasId}/sync-identity`, {
            method: 'POST',
            cache: 'no-store',
        });
        let payload = {};
        try {
            payload = await response.json();
        } catch (error) {
            payload = {};
        }
        if (!response.ok) {
            throw new Error(payload.detail || 'Sync identità fallito.');
        }
        const pieces = [
            `Alias #${payload.alias_id} collegato a identità #${payload.identity_id}`,
        ];
        if (payload.alias_identity_deactivated) {
            pieces.push('identità alias nascosta');
        }
        this._els.rebuildAliasesResult.classList.remove('is-error');
        this._els.rebuildAliasesResult.textContent = pieces.join(' · ');
        await this._loadAliases();
    },

    async _deactivateAlias(aliasId, button) {
        if (!window.confirm('Disattivare questo alias?')) {
            return;
        }
        button.disabled = true;
        const response = await fetch(`/api/attendance/identity-aliases/${aliasId}/deactivate`, {
            method: 'POST',
            cache: 'no-store',
        });
        let payload = {};
        try {
            payload = await response.json();
        } catch (error) {
            payload = {};
        }
        if (!response.ok) {
            throw new Error(payload.detail || 'Impossibile disattivare l’alias.');
        }
        await this._loadAliases();
    },

    _formatDateTime(value) {
        const date = new Date(value);
        return date.toLocaleString('it-CH', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
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

    _candidateKey(candidate) {
        return `${String(candidate.canonical_full_name || '').trim().toLowerCase()}||${String(candidate.email || '').trim().toLowerCase()}`;
    },
};

document.addEventListener('DOMContentLoaded', () => {
    AttendanceAliasesApp.init().catch((error) => console.error(error));
});
