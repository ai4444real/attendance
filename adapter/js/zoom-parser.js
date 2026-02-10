'use strict';

/**
 * Zoom CSV Parser
 *
 * Parses Zoom "meeting participant details" reports into structured data.
 *
 * Handles:
 *   - BOM marker
 *   - Quoted CSV fields (dates contain commas)
 *   - Duplicate header "Durata (minuti)" (meeting-level vs participant-level)
 *   - Multiple meetings per file (separated by blank lines)
 *   - Host filtering (Guest = "No")
 */
const ZoomParser = {

    /**
     * Parse a Zoom CSV file into an array of meeting objects.
     *
     * @param {string} csvText - Raw file content
     * @returns {{ meetings: Array, warnings: Array<string> }}
     */
    parse(csvText) {
        const warnings = [];

        const clean = csvText.replace(/^\uFEFF/, '');
        const lines = clean.split('\n');

        if (lines.length < 2) {
            throw new Error('Il file CSV deve contenere almeno intestazioni e una riga');
        }

        const rawHeaders = this._parseLine(lines[0]);
        const headers = this._deduplicateHeaders(rawHeaders);

        const meetings = [];
        let currentRows = [];

        for (let i = 1; i < lines.length; i++) {
            const trimmed = lines[i].trim();

            if (!trimmed) {
                if (currentRows.length > 0) {
                    const m = this._buildMeeting(currentRows, warnings);
                    if (m) meetings.push(m);
                    currentRows = [];
                }
                continue;
            }

            const values = this._parseLine(trimmed);
            if (values.length >= headers.length) {
                const row = {};
                headers.forEach((h, idx) => {
                    row[h] = (values[idx] || '').trim();
                });
                currentRows.push(row);
            } else {
                warnings.push(`Riga ${i + 1}: colonne non corrispondenti (${values.length}/${headers.length}), saltata`);
            }
        }

        // Last meeting (file may not end with blank line)
        if (currentRows.length > 0) {
            const m = this._buildMeeting(currentRows, warnings);
            if (m) meetings.push(m);
        }

        return { meetings, warnings };
    },

    // ------------------------------------------------------------------
    // Private
    // ------------------------------------------------------------------

    _buildMeeting(rows, warnings) {
        if (rows.length === 0) return null;

        const first = rows[0];
        const startTime = this._parseDateTime(first['Ora di inizio']);
        const endTime = this._parseDateTime(first['Ora di fine']);

        if (!startTime || !endTime) {
            warnings.push(`Meeting "${first['Argomento'] || '?'}": date non valide, saltato`);
            return null;
        }

        const meeting = {
            course: first['Argomento'] || '',
            meetingId: first['ID'] || '',
            organizer: first['Nome organizzatore'] || '',
            organizerEmail: first['E-mail organizzatore'] || '',
            startTime,
            endTime,
            durationMinutes: (endTime - startTime) / (1000 * 60),
            segments: []
        };

        for (const row of rows) {
            const rawName = row['Nome (nome originale)'] || '';
            const email = row['E-mail'] || '';
            const guestField = (row['Guest'] || '').toLowerCase();

            // Skip non-guests (hosts / organizers)
            if (guestField !== 'sì' && guestField !== 'si') {
                continue;
            }

            const joinTime = this._parseDateTime(row['Ora di ingresso']);
            const leaveTime = this._parseDateTime(row['Ora di uscita']);

            if (!joinTime || !leaveTime) {
                warnings.push(`Meeting "${meeting.course}": segmento con date non valide per "${rawName}", saltato`);
                continue;
            }

            const { firstName, lastName } = this._splitName(rawName);

            meeting.segments.push({
                fullName: rawName,
                firstName,
                lastName,
                email,
                joinTime,
                leaveTime,
                durationMinutes: (leaveTime - joinTime) / (1000 * 60)
            });
        }

        return meeting;
    },

    /**
     * Parse a CSV line handling quoted fields.
     */
    _parseLine(line) {
        const result = [];
        let current = '';
        let inQuotes = false;

        for (let i = 0; i < line.length; i++) {
            const ch = line[i];
            if (ch === '"') {
                if (inQuotes && line[i + 1] === '"') {
                    current += '"';
                    i++;
                } else {
                    inQuotes = !inQuotes;
                }
            } else if (ch === ',' && !inQuotes) {
                result.push(current);
                current = '';
            } else {
                current += ch;
            }
        }
        result.push(current);
        return result;
    },

    /**
     * Make duplicate header names unique: "X", "X" → "X", "X_2"
     */
    _deduplicateHeaders(headers) {
        const counts = {};
        return headers.map(h => {
            const t = h.trim();
            if (!counts[t]) { counts[t] = 1; return t; }
            counts[t]++;
            return `${t}_${counts[t]}`;
        });
    },

    /**
     * Parse Zoom date string "MM/DD/YYYY HH:MM:SS AM/PM" → Date
     */
    _parseDateTime(str) {
        if (!str) return null;
        const m = str.match(/(\d{2})\/(\d{2})\/(\d{4})\s+(\d{1,2}):(\d{2}):(\d{2})\s+(AM|PM)/i);
        if (!m) return null;

        let [, month, day, year, hours, minutes, seconds, period] = m;
        hours = parseInt(hours);
        if (period.toUpperCase() === 'PM' && hours !== 12) hours += 12;
        if (period.toUpperCase() === 'AM' && hours === 12) hours = 0;

        return new Date(
            parseInt(year), parseInt(month) - 1, parseInt(day),
            hours, parseInt(minutes), parseInt(seconds)
        );
    },

    /**
     * Split "Daniel Lo Russo" → { firstName: "Daniel", lastName: "Lo Russo" }
     * Uses first word as first name, rest as last name.
     */
    _splitName(fullName) {
        const clean = fullName
            .replace(/\(Host\)/gi, '')
            .replace(/\([^)]*\)/g, '')
            .trim();

        const parts = clean.split(/\s+/);
        if (parts.length === 0) return { firstName: '', lastName: '' };
        if (parts.length === 1) return { firstName: this._cap(parts[0]), lastName: '' };

        return {
            firstName: this._cap(parts[0]),
            lastName: parts.slice(1).map(p => this._cap(p)).join(' ')
        };
    },

    /** Capitalize first letter: "luca" → "Luca" */
    _cap(word) {
        if (!word) return '';
        return word.charAt(0).toUpperCase() + word.slice(1);
    }
};
