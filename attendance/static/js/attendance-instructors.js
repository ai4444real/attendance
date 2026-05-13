'use strict';

const AttendanceInstructorsApp = {
    async init() {
        this._els = {
            form: document.getElementById('instructorForm'),
            instructorName: document.getElementById('instructorName'),
            aliasOfId: document.getElementById('aliasOfId'),
            notes: document.getElementById('notes'),
            status: document.getElementById('status'),
            instructorsBody: document.getElementById('instructorsBody'),
        };
        this._instructors = [];
        this._els.form.addEventListener('submit', (event) => {
            event.preventDefault();
            this._saveInstructor().catch((error) => {
                console.error(error);
                this._setStatus(error.message || 'Salvataggio fallito.', 'error');
            });
        });
        await this._loadInstructors();
    },

    async _loadInstructors() {
        const response = await fetch('/api/attendance/instructors', { cache: 'no-store' });
        const payload = await response.json();
        if (!response.ok) {
            throw new Error(payload.detail || 'Impossibile leggere i docenti.');
        }
        this._instructors = payload.instructors || [];
        this._renderAliasPicker();
        this._renderTable();
    },

    async _saveInstructor() {
        const payload = {
            instructor_name: this._els.instructorName.value.trim(),
            alias_of_id: this._els.aliasOfId.value || null,
            notes: this._els.notes.value.trim() || null,
        };
        if (!payload.instructor_name) {
            this._setStatus('Inserisci un nome.', 'error');
            return;
        }

        this._setStatus('Salvataggio...', '');
        const response = await fetch('/api/attendance/instructors', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Salvataggio fallito.');
        }
        this._els.form.reset();
        await this._loadInstructors();
        this._setStatus(`Salvato: ${data.instructor.instructor_name}`, 'ok');
    },

    _renderAliasPicker() {
        const canonical = this._instructors.filter((instructor) => !instructor.alias_of_id);
        this._els.aliasOfId.innerHTML = [
            '<option value="">Nome canonico</option>',
            ...canonical.map((instructor) => (
                `<option value="${this._escapeAttr(instructor.id)}">${this._escapeHtml(instructor.instructor_name)}</option>`
            )),
        ].join('');
    },

    _renderTable() {
        if (!this._instructors.length) {
            this._els.instructorsBody.innerHTML = '<div class="empty">Nessun docente registrato.</div>';
            return;
        }
        this._els.instructorsBody.innerHTML = `
            <table class="instructors-table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Nome</th>
                        <th>Tipo</th>
                        <th>Alias di</th>
                        <th>Note</th>
                    </tr>
                </thead>
                <tbody>
                    ${this._instructors.map((instructor) => `
                        <tr>
                            <td>${this._escapeHtml(instructor.id)}</td>
                            <td><span class="teacher-name">${this._escapeHtml(instructor.instructor_name)}</span></td>
                            <td>${instructor.alias_of_id ? '<span class="alias-pill">alias</span>' : '<span class="canonical-pill">canonico</span>'}</td>
                            <td>${this._escapeHtml(instructor.canonical_name || '—')}</td>
                            <td>${this._escapeHtml(instructor.notes || '—')}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    },

    _setStatus(message, type) {
        this._els.status.textContent = message;
        this._els.status.className = `status ${type || ''}`.trim();
    },

    _escapeHtml(value) {
        return String(value ?? '')
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
    AttendanceInstructorsApp.init().catch((error) => console.error(error));
});
