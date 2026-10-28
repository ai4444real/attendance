(function (root) {
    "use strict";
    const months = { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12 };

    function parseDate(value) {
        const text = value.trim();
        let match = /^(\d{1,2})\.\s*([A-Za-z]{3})\s+(\d{4})$/.exec(text);
        let year, month, day;
        if (match) {
            day = Number(match[1]); month = months[match[2].toLowerCase()]; year = Number(match[3]);
        }
        else if ((match = /^(\d{1,2})\.(\d{1,2})\.(\d{4})$/.exec(text))) {
            day = Number(match[1]); month = Number(match[2]); year = Number(match[3]);
        } else if ((match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text))) {
            [, year, month, day] = match.map(Number);
        } else throw new Error("Data non riconosciuta: " + (value || "(vuota)"));
        if (!month || month > 12 || year < 1900 || year > 2200 || day < 1 || day > new Date(Date.UTC(year, month, 0)).getUTCDate()) {
            throw new Error("Data non valida: " + value);
        }
        return { year, month, day };
    }

    function parseCents(value) {
        let text = value.trim().replace(/^CHF\s*/i, "").replace(/\s*CHF$/i, "").replace(/[\s'’]/g, "");
        if (/^-?\d{1,3}(,\d{3})+\.\d{2}$/.test(text)) text = text.replace(/,/g, "");
        if (/^-?\d+,\d{2}$/.test(text)) text = text.replace(",", ".");
        if (!/^-?\d+(?:\.\d{1,2})?$/.test(text)) throw new Error("Importo CHF non riconosciuto: " + value);
        const [whole, fraction = ""] = text.replace(/^-/, "").split(".");
        const cents = (Number(whole) * 100 + Number(fraction.padEnd(2, "0"))) * (text.startsWith("-") ? -1 : 1);
        if (!Number.isSafeInteger(cents)) throw new Error("Importo troppo grande: " + value);
        return cents;
    }

    const monthKey = date => date.year + "-" + String(date.month).padStart(2, "0");
    const dayKey = date => monthKey(date) + "-" + String(date.day).padStart(2, "0");
    function addMonths(anchor, offset) {
        const serial = anchor.year * 12 + anchor.month - 1 + offset;
        const year = Math.floor(serial / 12), month = serial % 12 + 1;
        return { year, month, day: Math.min(anchor.day, new Date(Date.UTC(year, month, 0)).getUTCDate()) };
    }

    function forecast(rows) {
        const byMonth = new Map(), warnings = [];
        let accepted = 0;
        for (const [index, row] of rows.entries()) {
            try {
                const frequency = row.frequency.trim().toLowerCase();
                const increment = frequency === "monthly" ? 1 : frequency === "every 6 months" ? 6 : null;
                if (!increment) throw new Error("Frequenza non supportata: " + row.frequency);
                const start = parseDate(row.next), end = parseDate(row.end), cents = parseCents(row.amount);
                if (dayKey(end) < dayKey(start)) throw new Error("Data finale precedente a Next");
                const span = (end.year - start.year) * 12 + end.month - start.month;
                if (span > 1200) throw new Error("Intervallo superiore a 100 anni: verificare le date");
                const scheduled = [];
                for (let offset = 0; offset <= span; offset += increment) {
                    const date = addMonths(start, offset);
                    if (dayKey(date) > dayKey(end)) break;
                    scheduled.push({ date: dayKey(date), customer: row.customer, cents, frequency: row.frequency, sourceRow: index + 1 });
                }
                // Validate the whole series before adding any invoice to the totals.
                for (const invoice of scheduled) {
                    const key = invoice.date.slice(0, 7);
                    if (!byMonth.has(key)) byMonth.set(key, { key, cents: 0, invoices: [] });
                    const bucket = byMonth.get(key);
                    bucket.cents += invoice.cents;
                    bucket.invoices.push(invoice);
                }
                accepted++;
            } catch (error) {
                warnings.push({ row: index + 1, customer: row.customer, message: error.message });
            }
        }
        const keys = [...byMonth.keys()].sort();
        const result = [];
        if (keys.length) {
            const start = parseDate(keys[0] + "-01"), last = keys[keys.length - 1];
            for (let offset = 0; ; offset++) {
                const key = monthKey(addMonths(start, offset));
                if (key > last) break;
                const bucket = byMonth.get(key) || { key, cents: 0, invoices: [] };
                bucket.invoices.sort((a, b) => a.date.localeCompare(b.date) || a.customer.localeCompare(b.customer, "it"));
                result.push(bucket);
            }
        }
        return {
            months: result, warnings, accepted,
            totalCents: result.reduce((sum, month) => sum + month.cents, 0),
            invoiceCount: result.reduce((sum, month) => sum + month.invoices.length, 0),
        };
    }

    function toTsv(result, detailed = false) {
        // Protect spreadsheet pastes from interpreting customer text as formulas.
        const safe = value => {
            const text = String(value).replace(/[\t\r\n]+/g, " ");
            return /^[=+@-]/.test(text.trimStart()) ? "'" + text : text;
        };
        const lines = detailed ? [["Mese", "Data fattura", "Cliente", "Frequenza", "Importo CHF"]]
            : [["Mese", "Numero fatture", "Importo CHF"]];
        for (const month of result.months) {
            if (detailed) {
                for (const invoice of month.invoices) lines.push([month.key, invoice.date, safe(invoice.customer), safe(invoice.frequency), (invoice.cents / 100).toFixed(2)]);
            } else lines.push([month.key, month.invoices.length, (month.cents / 100).toFixed(2)]);
        }
        if (!detailed) lines.push(["Totale", result.invoiceCount, (result.totalCents / 100).toFixed(2)]);
        return lines.map(line => line.join("\t")).join("\n");
    }

    const api = { parseDate, parseCents, forecast, toTsv };
    if (typeof module !== "undefined" && module.exports) module.exports = api;
    else root.EsposizioneForecast = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
