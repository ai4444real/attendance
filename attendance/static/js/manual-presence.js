class ManualPresencePage {
    constructor() {
        this.form = document.getElementById('manualPresenceForm');
        this.status = document.getElementById('status');
        this.recordsText = document.getElementById('recordsText');
    }

    init() {
        if (!this.form) {
            return;
        }
        this.form.addEventListener('submit', (event) => {
            event.preventDefault();
            this.submit();
        });
    }

    async submit() {
        this.setStatus('Import in corso...', '');
        const formData = new FormData(this.form);
        const defaultStatus = String(formData.get('presence_status') || 'presente');
        const records = this.parseRecords(this.recordsText.value, defaultStatus);
        if (!records.length) {
            this.setStatus('Inserisci almeno una persona.', 'error');
            return;
        }

        const payload = {
            course_name: String(formData.get('course_name') || '').trim(),
            lesson_date: String(formData.get('lesson_date') || '').trim(),
            presence_source: String(formData.get('presence_source') || 'manual').trim(),
            created_by: 'manual-ui',
            records,
        };

        try {
            const response = await fetch('/api/attendance/manual-presence', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const data = await this.readJson(response);
            if (!response.ok) {
                throw new Error(data.detail || 'Import manuale fallito.');
            }
            this.setStatus(
                `Import manuale salvato: lesson #${data.lesson_id}, ${data.participants_upserted}/${data.records_processed} presenze.`,
                'ok',
            );
        } catch (error) {
            this.setStatus(error.message, 'error');
        }
    }

    parseRecords(text, defaultStatus) {
        return String(text || '')
            .split(/\r?\n/)
            .map((line) => this.parseLine(line, defaultStatus))
            .filter(Boolean);
    }

    parseLine(line, defaultStatus) {
        const clean = String(line || '').trim();
        if (!clean) {
            return null;
        }
        const parts = clean.includes(';')
            ? clean.split(';').map((part) => part.trim())
            : clean.split(',').map((part) => part.trim());
        const fullName = parts[0] || '';
        if (!fullName) {
            return null;
        }
        const email = parts[1] && parts[1].includes('@') ? parts[1] : null;
        const statusCandidate = parts[2] || (parts[1] && !parts[1].includes('@') ? parts[1] : defaultStatus);
        return {
            full_name: fullName,
            email,
            presence_status: statusCandidate || defaultStatus,
        };
    }

    async readJson(response) {
        const text = await response.text();
        if (!text) {
            return {};
        }
        try {
            return JSON.parse(text);
        } catch {
            return { detail: text };
        }
    }

    setStatus(message, type) {
        this.status.textContent = message;
        this.status.className = `status ${type || ''}`.trim();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new ManualPresencePage().init();
});
