'use strict';

const AttendanceIdentitiesApp = {
    async init() {
        this._els = {
            identitiesMeta: document.getElementById('identitiesMeta'),
            identitiesBody: document.getElementById('identitiesBody'),
            rebuildIdentitiesButton: document.getElementById('rebuildIdentitiesButton'),
            rebuildIdentitiesResult: document.getElementById('rebuildIdentitiesResult'),
        };

        this._els.rebuildIdentitiesButton.addEventListener('click', () => {
            this._rebuildIdentities().catch((error) => {
                console.error(error);
                this._els.rebuildIdentitiesResult.textContent = error.message || 'Ricostruzione identità fallita.';
                this._els.rebuildIdentitiesResult.classList.add('is-error');
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
            this._renderMeta(identities, payload.total_visible);
            this._renderTable(identities);
        } catch (error) {
            console.error(error);
            this._els.identitiesBody.innerHTML = `<div class="empty">${this._escapeHtml(error.message)}</div>`;
        }
    },

    async _rebuildIdentities() {
        if (!window.confirm('Ricostruire il registro identità dai partecipanti già salvati?')) {
            return;
        }
        this._els.rebuildIdentitiesButton.disabled = true;
        this._els.rebuildIdentitiesResult.classList.remove('is-error');
        this._els.rebuildIdentitiesResult.textContent = 'Ricostruzione in corso...';
        try {
            const response = await fetch('/api/attendance/identities/rebuild', {
                method: 'POST',
                cache: 'no-store',
            });
            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload.detail || 'Ricostruzione identità fallita.');
            }
            this._els.rebuildIdentitiesResult.textContent = [
                `${payload.source_identities || 0} identità trovate`,
                `${payload.rows_upserted || 0} righe upsert`,
                `${payload.identities_count || 0} totali`,
            ].join(' · ');
            await this._loadIdentities();
        } finally {
            this._els.rebuildIdentitiesButton.disabled = false;
        }
    },

    _renderMeta(identities, totalVisible) {
        this._els.identitiesMeta.innerHTML = `
            <span class="meta-pill"><strong>${this._escapeHtml(totalVisible ?? identities.length)}</strong> identità visibili</span>
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
                        <th>Identity key</th>
                    </tr>
                </thead>
                <tbody>
                    ${identities.map((identity) => `
                        <tr>
                            <td><span class="identity-name">${this._escapeHtml(identity.display_name)}</span></td>
                            <td>${this._escapeHtml(identity.email || 'senza email')}</td>
                            <td><span class="identity-key">${this._escapeHtml(identity.identity_key)}</span></td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
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
    AttendanceIdentitiesApp.init().catch((error) => console.error(error));
});
