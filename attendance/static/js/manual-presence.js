class ManualPresencePage {
    constructor() {
        this.form = document.getElementById('manualPresenceForm');
        this.status = document.getElementById('status');
        this.recordsText = document.getElementById('recordsText');
        this.existingFields = document.getElementById('existingTargetFields');
        this.manualFields = document.getElementById('manualTargetFields');
        this.existingCourse = document.getElementById('existingCourse');
        this.existingLesson = document.getElementById('existingLesson');
        this.targets = [];
    }

    init() {
        if (!this.form) {
            return;
        }
        this.form.addEventListener('submit', (event) => {
            event.preventDefault();
            this.submit();
        });
        this.form.querySelectorAll('input[name="target_mode"]').forEach((input) => {
            input.addEventListener('change', () => this.updateTargetMode());
        });
        this.existingCourse.addEventListener('change', () => this.renderLessonsForSelectedCourse());
        this.updateTargetMode();
        this.loadTargets();
    }

    async submit() {
        this.setStatus('Import in corso...', '');
        const formData = new FormData(this.form);
        const mode = String(formData.get('target_mode') || 'existing');
        const defaultStatus = String(formData.get('presence_status') || 'presente');
        const records = this.parseRecords(this.recordsText.value, defaultStatus);
        if (!records.length) {
            this.setStatus('Inserisci almeno una persona.', 'error');
            return;
        }

        const payload = {
            presence_source: String(formData.get('presence_source') || 'manual').trim(),
            created_by: 'manual-ui',
            records,
        };
        if (mode === 'existing') {
            payload.lesson_id = Number(formData.get('lesson_id') || 0);
            if (!payload.lesson_id) {
                this.setStatus('Scegli una lezione esistente oppure passa alla modalita manuale.', 'error');
                return;
            }
        } else {
            payload.course_name = String(formData.get('course_name') || '').trim();
            payload.lesson_date = String(formData.get('lesson_date') || '').trim();
        }

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

    async loadTargets() {
        try {
            const response = await fetch('/api/attendance/manual-presence-targets', { cache: 'no-store' });
            const data = await this.readJson(response);
            if (!response.ok) {
                throw new Error(data.detail || 'Impossibile caricare corsi e lezioni.');
            }
            this.targets = data.courses || [];
            this.renderCourses();
        } catch (error) {
            this.existingCourse.innerHTML = '<option value="">Corsi non disponibili</option>';
            this.existingLesson.innerHTML = '<option value="">Usa inserimento manuale</option>';
            this.setStatus(error.message, 'error');
        }
    }

    renderCourses() {
        if (!this.targets.length) {
            this.existingCourse.innerHTML = '<option value="">Nessun corso official disponibile</option>';
            this.existingLesson.innerHTML = '<option value="">Usa inserimento manuale</option>';
            return;
        }
        this.existingCourse.innerHTML = [
            '<option value="">Scegli corso</option>',
            ...this.targets.map((course) => `<option value="${this.escapeAttr(course.course_name)}">${this.escapeHtml(course.course_name)}</option>`),
        ].join('');
    }

    renderLessonsForSelectedCourse() {
        const selectedCourse = this.existingCourse.value;
        const course = this.targets.find((item) => item.course_name === selectedCourse);
        if (!course) {
            this.existingLesson.innerHTML = '<option value="">Scegli prima un corso</option>';
            return;
        }
        this.existingLesson.innerHTML = [
            '<option value="">Scegli lezione</option>',
            ...course.lessons.map((lesson) => {
                const label = `${lesson.lesson_date} - meeting ${lesson.source_meeting_id} - ${lesson.total_records} presenze`;
                return `<option value="${Number(lesson.lesson_id)}">${this.escapeHtml(label)}</option>`;
            }),
        ].join('');
    }

    updateTargetMode() {
        const mode = new FormData(this.form).get('target_mode') || 'existing';
        const useExisting = mode === 'existing';
        this.existingFields.classList.toggle('hidden', !useExisting);
        this.manualFields.classList.toggle('hidden', useExisting);
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

    escapeHtml(value) {
        return String(value ?? '')
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#039;');
    }

    escapeAttr(value) {
        return this.escapeHtml(value);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new ManualPresencePage().init();
});
