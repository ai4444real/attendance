'use strict';

const AttendanceAliasesApp = {
    async init() {
        this._els = {
            aliasesMeta: document.getElementById('aliasesMeta'),
            aliasesBody: document.getElementById('aliasesBody'),
        };

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
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
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
};

document.addEventListener('DOMContentLoaded', () => {
    AttendanceAliasesApp.init().catch((error) => console.error(error));
});
