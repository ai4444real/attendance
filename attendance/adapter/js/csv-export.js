'use strict';

/**
 * CSV Export
 *
 * Generates the normalized output CSV and triggers a browser download.
 */
const CsvExport = {

    headers: [
        'Corso', 'Data', 'Nome', 'Cognome', 'Email', 'Presenza',
        'Min Prima Meta', 'Min Seconda Meta',
        'Durata Prima Meta', 'Durata Seconda Meta',
        'Minuti Totali', 'Segmenti'
    ],

    /**
     * Generate CSV string from normalized records.
     * @param {Array} records
     * @returns {string}
     */
    generate(records) {
        const rows = records.map(r => [
            this._esc(r.course),
            this._esc(this._fmtDate(r.date)),
            this._esc(r.firstName),
            this._esc(r.lastName),
            this._esc(r.email),
            this._esc(r.presence),
            r.minutesFirstHalf,
            r.minutesSecondHalf,
            r.durationFirstHalf,
            r.durationSecondHalf,
            r.totalMinutes,
            r.segmentCount
        ].join(','));

        return [this.headers.join(','), ...rows].join('\n');
    },

    /**
     * Trigger a browser download of the CSV.
     * @param {string} csv
     * @param {string} [filename]
     */
    download(csv, filename) {
        const bom = '\uFEFF'; // BOM for Excel UTF-8 detection
        const blob = new Blob([bom + csv], { type: 'text/csv;charset=utf-8;' });

        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = filename || this.defaultFilename();
        link.style.display = 'none';

        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(link.href);
    },

    defaultFilename() {
        return `attendance_normalized_${new Date().toISOString().split('T')[0]}.csv`;
    },

    // ------------------------------------------------------------------

    _esc(value) {
        if (value == null) return '';
        const s = String(value);
        if (s.includes(',') || s.includes('"') || s.includes('\n')) {
            return '"' + s.replace(/"/g, '""') + '"';
        }
        return s;
    },

    _fmtDate(date) {
        if (!date) return '';
        const d = new Date(date);
        const yyyy = d.getFullYear();
        const mm = String(d.getMonth() + 1).padStart(2, '0');
        const dd = String(d.getDate()).padStart(2, '0');
        return `${yyyy}-${mm}-${dd}`;
    }
};
