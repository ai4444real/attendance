'use strict';

const AttendanceIdentitiesApp = {
    async init() {
        this._els = {
            identitiesMeta: document.getElementById('identitiesMeta'),
            identitiesBody: document.getElementById('identitiesBody'),
            identityFilterInput: document.getElementById('identityFilterInput'),
            clearIdentityFilterButton: document.getElementById('clearIdentityFilterButton'),
            aliasPreviewCard: document.getElementById('aliasPreviewCard'),
            canonicalPreviewCard: document.getElementById('canonicalPreviewCard'),
            createAliasButton: document.getElementById('createAliasButton'),
            createAliasResult: document.getElementById('createAliasResult'),
        };
        this._identities = [];
        this._filteredIdentities = [];
        this._selectedCanonical = null;
        this._selectedAlias = null;

        this._els.identityFilterInput.addEventListener('input', () => {
            this._applyFilter();
        });
        this._els.clearIdentityFilterButton.addEventListener('click', () => {
            this._els.identityFilterInput.value = '';
            this._applyFilter();
        });
        this._els.identitiesBody.addEventListener('click', (event) => {
            const button = event.target.closest('[data-action][data-identity-index]');
            if (!button) return;
            const identity = this._filteredIdentities[Number(button.dataset.identityIndex)];
            if (!identity) return;
            if (button.dataset.action === 'select-canonical') {
                this._selectedCanonical = identity;
            }
            if (button.dataset.action === 'select-alias') {
                this._selectedAlias = identity;
            }
            if (button.dataset.action === 'deactivate-identity') {
                this._deactivateIdentity(identity).catch((error) => {
                    console.error(error);
                    window.alert(error.message || 'Impossibile ignorare l’identità.');
                });
                return;
            }
            if (button.dataset.action === 'edit-display-name') {
                this._editDisplayName(identity).catch((error) => {
                    console.error(error);
                    window.alert(error.message || 'Impossibile aggiornare il nome.');
                });
                return;
            }
            this._renderAliasPreview();
            this._renderTable(this._filteredIdentities);
        });
        this._els.createAliasButton.addEventListener('click', () => {
            this._createAlias().catch((error) => {
                console.error(error);
                this._els.createAliasResult.textContent = error.message || 'Creazione alias fallita.';
                this._els.createAliasResult.classList.add('is-error');
            });
        });

        await this._loadIdentities();
    },

    async _loadIdentities() {
        try {
            const response = await fetch('/api/attendance/identities?limit=1000', { cache: 'no-store' });
            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload.detail || 'Impossibile leggere le identità.');
            }
            const identities = payload.identities || [];
            this._identities = identities;
            this._applyFilter();
            this._renderAliasPreview();
        } catch (error) {
            console.error(error);
            this._els.identitiesBody.innerHTML = `<div class="empty">${this._escapeHtml(error.message)}</div>`;
        }
    },

    _applyFilter() {
        const needle = this._normalize(this._els.identityFilterInput.value);
        this._filteredIdentities = this._identities.filter((identity) => {
            if (!needle) return true;
            return [
                identity.display_name,
                identity.email || '',
                identity.identity_key,
            ].some((value) => this._normalize(value).includes(needle));
        });
        this._renderMeta(this._filteredIdentities, this._filteredIdentities.length);
        this._renderTable(this._filteredIdentities);
    },

    _renderMeta(identities, totalVisible) {
        this._els.identitiesMeta.innerHTML = `
            <span class="meta-pill"><strong>${this._escapeHtml(totalVisible ?? identities.length)}</strong> identità visibili</span>
            <span class="meta-pill"><strong>${this._escapeHtml(this._identities.length)}</strong> totali caricate</span>
        `;
    },

    _renderTable(identities) {
        if (!identities.length) {
            this._els.identitiesBody.innerHTML = '<div class="empty">Nessuna identità osservata. Lancia la ricostruzione dopo aver creato la tabella nel DB.</div>';
            return;
        }

        this._els.identitiesBody.innerHTML = `
            <table class="identities-table">
                <thead>
                    <tr>
                        <th>Nome</th>
                        <th>Email</th>
                        <th>ID</th>
                        <th>Identity key</th>
                        <th>Azioni</th>
                    </tr>
                </thead>
                <tbody>
                    ${identities.map((identity, index) => `
                        <tr class="${this._rowClass(identity)}">
                            <td><span class="identity-name">${this._escapeHtml(identity.display_name)}</span></td>
                            <td>${this._escapeHtml(identity.email || 'senza email')}</td>
                            <td><span class="identity-key">#${this._escapeHtml(identity.id || '—')}</span></td>
                            <td><span class="identity-key">${this._escapeHtml(identity.identity_key)}</span></td>
                            <td>
                                <div class="identity-row-actions">
                                    <button class="tiny-action" type="button" data-action="select-canonical" data-identity-index="${this._escapeAttr(index)}">Canonico</button>
                                    <button class="tiny-action" type="button" data-action="select-alias" data-identity-index="${this._escapeAttr(index)}">Alias</button>
                                    <button class="tiny-action" type="button" data-action="edit-display-name" data-identity-index="${this._escapeAttr(index)}">Nome</button>
                                    <button class="tiny-action" type="button" data-action="deactivate-identity" data-identity-index="${this._escapeAttr(index)}">Ignora</button>
                                </div>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    },

    _renderAliasPreview() {
        this._els.aliasPreviewCard.innerHTML = this._selectedAlias
            ? this._renderPreviewCard(this._selectedAlias)
            : 'Alias non selezionato';
        this._els.canonicalPreviewCard.innerHTML = this._selectedCanonical
            ? this._renderPreviewCard(this._selectedCanonical)
            : 'Canonico non selezionato';
        const canCreate = this._selectedCanonical
            && this._selectedAlias
            && this._identityKey(this._selectedCanonical) !== this._identityKey(this._selectedAlias);
        this._els.createAliasButton.disabled = !canCreate;
    },

    _renderPreviewCard(identity) {
        return `
            <strong>${this._escapeHtml(identity.display_name)}</strong>
            <span class="hint">${this._escapeHtml(identity.email || 'senza email')}</span><br>
            <span class="identity-key">#${this._escapeHtml(identity.id || '—')}</span><br>
            <span class="identity-key">${this._escapeHtml(identity.identity_key)}</span>
        `;
    },

    async _createAlias() {
        if (!this._selectedCanonical || !this._selectedAlias) {
            return;
        }
        if (this._identityKey(this._selectedCanonical) === this._identityKey(this._selectedAlias)) {
            throw new Error('Scegli due identità diverse.');
        }

        const canonical = this._selectedCanonical;
        const alias = this._selectedAlias;
        const warning = alias.email
            ? ''
            : '\n\nNota: stai collegando un nome senza email. La regola varrà globalmente per quel nome.';
        if (!window.confirm(`Creare alias "${alias.display_name}" verso "${canonical.display_name}"?${warning}`)) {
            return;
        }

        this._els.createAliasButton.disabled = true;
        this._els.createAliasResult.classList.remove('is-error');
        this._els.createAliasResult.textContent = 'Creo alias...';
        try {
            const response = await fetch('/api/attendance/identity-aliases', {
                method: 'POST',
                cache: 'no-store',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    canonical_full_name: canonical.display_name,
                    canonical_email: canonical.email || null,
                    alias_full_name: alias.display_name,
                    alias_email: alias.email || null,
                    created_by: 'identities-ui',
                    notes: 'Creato dalla tabella identità osservate',
                }),
            });
            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload.detail || 'Creazione alias fallita.');
            }
            if (payload.identity_sync_error) {
                this._els.createAliasResult.textContent = `Alias creato, ma sync identità fallito: ${payload.identity_sync_error}`;
                this._els.createAliasResult.classList.add('is-error');
            } else {
                const syncText = payload.identity_sync?.alias_identity_deactivated
                    ? 'Identità alias nascosta.'
                    : 'Identità collegata.';
                this._els.createAliasResult.textContent = `Alias creato. ${syncText}`;
            }
            this._selectedAlias = null;
            this._renderAliasPreview();
            await this._loadIdentities();
        } finally {
            this._els.createAliasButton.disabled = false;
            this._renderAliasPreview();
        }
    },

    async _editDisplayName(identity) {
        if (!identity?.id) return;
        const nextName = window.prompt(
            'Nome visuale per questa identità. Non modifica alias, lezioni o analisi già normalizzate.',
            identity.display_name || ''
        );
        if (nextName === null) {
            return;
        }
        const displayName = nextName.trim().replace(/\s+/g, ' ');
        if (!displayName) {
            throw new Error('Il nome non può essere vuoto.');
        }
        const response = await fetch(`/api/attendance/identities/${encodeURIComponent(String(identity.id))}/display-name`, {
            method: 'POST',
            cache: 'no-store',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ display_name: displayName }),
        });
        const payload = await response.json();
        if (!response.ok) {
            throw new Error(payload.detail || 'Aggiornamento nome fallito.');
        }
        this._identities = this._identities.map((item) => item.id === payload.id ? payload : item);
        if (this._selectedCanonical?.id === payload.id) {
            this._selectedCanonical = payload;
        }
        if (this._selectedAlias?.id === payload.id) {
            this._selectedAlias = payload;
        }
        this._applyFilter();
        this._renderAliasPreview();
    },

    async _deactivateIdentity(identity) {
        if (!identity?.id) return;
        if (!window.confirm(`Ignorare "${identity.display_name}" dalla lista identità? Non viene cancellata dal database.`)) {
            return;
        }
        const response = await fetch(`/api/attendance/identities/${encodeURIComponent(String(identity.id))}/deactivate`, {
            method: 'POST',
            cache: 'no-store',
        });
        const payload = await response.json();
        if (!response.ok) {
            throw new Error(payload.detail || 'Disattivazione identità fallita.');
        }
        this._selectedCanonical = this._selectedCanonical?.id === identity.id ? null : this._selectedCanonical;
        this._selectedAlias = this._selectedAlias?.id === identity.id ? null : this._selectedAlias;
        this._identities = this._identities.filter((item) => item.id !== identity.id);
        this._applyFilter();
        this._renderAliasPreview();
    },

    _rowClass(identity) {
        const classes = [];
        if (this._selectedCanonical && this._identityKey(this._selectedCanonical) === this._identityKey(identity)) {
            classes.push('is-selected-canonical');
        }
        if (this._selectedAlias && this._identityKey(this._selectedAlias) === this._identityKey(identity)) {
            classes.push('is-selected-alias');
        }
        return classes.join(' ');
    },

    _identityKey(identity) {
        return String(identity?.identity_key || '');
    },

    _normalize(value) {
        return String(value || '').trim().toLocaleLowerCase('it');
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
    AttendanceIdentitiesApp.init().catch((error) => console.error(error));
});
