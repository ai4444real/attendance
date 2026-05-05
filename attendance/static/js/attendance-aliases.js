'use strict';

const AttendanceAliasesApp = {
    async init() {
        this._els = {
            aliasesMeta: document.getElementById('aliasesMeta'),
            aliasesBody: document.getElementById('aliasesBody'),
        };

        this._els.aliasesBody.addEventListener('click', (event) => {
            const button = event.target.closest('[data-action="deactivate-alias"]');
            if (!button) {
                return;
            }
            const aliasId = Number(button.dataset.aliasId || 0);
            if (!aliasId) {
                return;
            }
            this._deactivateAlias(aliasId, button).catch((error) => {
                console.error(error);
                window.alert(error.message || 'Impossibile disattivare l’alias.');
            });
        });

        await this._loadAliases();
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
                            <td class="actions-cell">
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
};

document.addEventListener('DOMContentLoaded', () => {
    AttendanceAliasesApp.init().catch((error) => console.error(error));
});
