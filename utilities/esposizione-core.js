/* Shared by the page, the bookmarklet and the extraction regression tests. */
(function (root) {
    "use strict";

    // Self-contained: serialized into the bookmarklet without external scripts.
    function readRecurringPage(doc) {
        const normalize = value => value.replace(/\s+/g, " ").trim().toLowerCase();
        const required = ["frequency", "customer", "first invoice", "next", "end date", "amount", "status"];
        const matches = [];
        for (const table of doc.querySelectorAll("table")) {
            if (!table.getClientRects().length) continue;
            for (const header of [...table.rows].slice(0, 5)) {
                const cells = [...header.cells];
                if (!required.every(label => cells.some(cell => normalize(cell.innerText) === label))) continue;
                let width = 0;
                const columns = {};
                for (const cell of cells) {
                    const span = cell.colSpan || 1;
                    // Smallinvoice merges Preview + Frequency in its header.
                    columns[normalize(cell.innerText)] = width + span - 1;
                    width += span;
                }
                matches.push({ table, header, columns, width });
                break;
            }
        }
        if (matches.length !== 1) {
            throw new Error("Apri le fatture ricorrenti: trovate " + matches.length + " tabelle compatibili, attesa una sola.");
        }
        const { table, header, columns, width } = matches[0];
        const rows = [];
        const unrecognized = [];
        let excluded = 0;
        const dataRows = [...table.rows].slice([...table.rows].indexOf(header) + 1);
        for (const row of dataRows) {
            const cells = [...row.cells];
            if (cells.length !== width || cells.some(cell => cell.colSpan > 1 || cell.rowSpan > 1)) {
                unrecognized.push(cells.map(cell => cell.innerText.trim()));
                continue;
            }
            const get = label => cells[columns[label]].innerText.trim();
            const next = get("next");
            if (!next || /^[-–—]+$/.test(next)) {
                excluded++;
                continue;
            }
            rows.push({
                frequency: get("frequency"), customer: get("customer"),
                first: get("first invoice"), next, end: get("end date"),
                amount: get("amount"), status: get("status"),
            });
        }
        return {
            version: 1, capturedAt: new Date().toISOString(),
            source: "https://app.smallinvoice.com", scanned: dataRows.length,
            excluded, rows, unrecognized,
        };
    }

    function validatePayload(value) {
        const fail = () => { throw new Error("Dati ricevuti non validi. Ripeti la lettura dalla pagina Smallinvoice."); };
        if (!value || value.version !== 1 || value.source !== "https://app.smallinvoice.com"
            || typeof value.capturedAt !== "string" || !Number.isFinite(Date.parse(value.capturedAt))
            || !Number.isInteger(value.scanned) || value.scanned < 0 || value.scanned > 2000
            || !Number.isInteger(value.excluded) || value.excluded < 0
            || !Array.isArray(value.rows) || !Array.isArray(value.unrecognized)
            || value.rows.length + value.excluded + value.unrecognized.length !== value.scanned) fail();
        for (const row of value.rows) {
            if (!row || !["frequency", "customer", "first", "next", "end", "amount", "status"]
                .every(key => typeof row[key] === "string" && row[key].length <= 2000)
                || !row.next.trim() || /^[-–—]+$/.test(row.next.trim())) fail();
        }
        for (const row of value.unrecognized) {
            if (!Array.isArray(row) || row.length > 100
                || !row.every(cell => typeof cell === "string" && cell.length <= 10000)) fail();
        }
        return value;
    }

    function makeBookmarklet(targetOrigin) {
        const target = new URL("/utilities/esposizione", targetOrigin).href;
        return "javascript:" + encodeURIComponent("(" + function (read, target) {
            try {
                if (location.origin !== "https://app.smallinvoice.com") {
                    throw new Error("Usa questo preferito sulla pagina delle fatture ricorrenti Smallinvoice.");
                }
                const payload = read(document);
                const url = target + "#esposizione=" + encodeURIComponent(JSON.stringify(payload));
                if (url.length > 60000 || payload.scanned > 2000) {
                    throw new Error("Troppi dati per il trasferimento. Riduci le righe nella pagina e riprova.");
                }
                if (confirm("Aprire Esposizione su Rebekko?\n\n" + payload.rows.length
                    + " righe con Next\n" + payload.excluded + " escluse senza Next\n"
                    + payload.unrecognized.length + " righe da verificare\n\nViene letta soltanto la pagina corrente.")) {
                    location.assign(url);
                }
            } catch (error) { alert(error.message); }
        }.toString() + ")(" + readRecurringPage.toString() + "," + JSON.stringify(target) + ");");
    }

    const api = { readRecurringPage, validatePayload, makeBookmarklet };
    if (typeof module !== "undefined" && module.exports) module.exports = api;
    else root.EsposizioneCore = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
