(function () {
    "use strict";
    const core = window.EsposizioneCore;
    const key = "rebekko.esposizione.v1";
    const byId = id => document.getElementById(id);
    const bookmark = core.makeBookmarklet(location.origin);
    byId("bookmark").href = bookmark;
    byId("bookmark").addEventListener("click", event => {
        event.preventDefault();
        byId("copyStatus").textContent = "Trascina il pulsante nei preferiti oppure copia il codice e modifica il preferito esistente.";
        byId("copyStatus").closest("details").open = true;
    });
    byId("bookmarkCode").value = bookmark;
    byId("copy").addEventListener("click", async () => {
        try {
            await navigator.clipboard.writeText(bookmark);
            byId("copyStatus").textContent = "Codice copiato.";
        } catch (_) {
            byId("bookmarkCode").select();
            byId("copyStatus").textContent = "Copia il codice selezionato con Ctrl+C.";
        }
    });
    byId("clear").addEventListener("click", () => {
        try { sessionStorage.removeItem(key); } catch (_) { /* Storage may be disabled. */ }
        byId("rows").replaceChildren();
        byId("unknownRows").replaceChildren();
        byId("results").hidden = true;
        byId("message").textContent = "Dati rimossi. Usa il preferito per una nuova lettura.";
    });

    function render(data, restored, stored) {
        byId("included").textContent = data.rows.length;
        byId("excluded").textContent = data.excluded;
        byId("unknown").textContent = data.unrecognized.length;
        byId("capture").textContent = "Lettura del " + new Date(data.capturedAt).toLocaleString("it-CH", { timeZone: "Europe/Zurich" })
            + " · " + data.scanned + " righe esaminate nella pagina Smallinvoice.";
        const fragment = document.createDocumentFragment();
        for (const row of data.rows) {
            const tr = document.createElement("tr");
            for (const field of ["customer", "frequency", "first", "next", "end", "amount", "status"]) {
                const td = document.createElement("td");
                td.textContent = row[field];
                tr.append(td);
            }
            fragment.append(tr);
        }
        byId("rows").replaceChildren(fragment);
        for (const [index, row] of data.unrecognized.entries()) {
            const pre = document.createElement("pre");
            pre.textContent = "Riga da verificare " + (index + 1) + " · " + row.length + " celle\n"
                + row.map((cell, i) => "Cella " + i + ": " + (cell || "(vuota)")).join("\n");
            byId("unknownRows").append(pre);
        }
        byId("diagnostics").hidden = data.unrecognized.length === 0;
        byId("results").hidden = false;
        byId("message").textContent = (restored ? "Ultima lettura di questa scheda ripristinata; non è un aggiornamento da Smallinvoice."
            : "Dati ricevuti da Smallinvoice.")
            + (stored ? "" : " La memoria della scheda non è disponibile: ricaricando perderai questi dati.");
    }

    try {
        const incoming = location.hash.startsWith("#esposizione=");
        let raw;
        if (incoming) {
            if (location.hash.length > 60000) throw new Error("Trasferimento troppo grande. Riduci le righe nella pagina Smallinvoice.");
            raw = decodeURIComponent(location.hash.slice("#esposizione=".length));
            // Remove client data from the address before rendering or navigating.
            history.replaceState(null, "", location.pathname + location.search);
        } else {
            try { raw = sessionStorage.getItem(key); } catch (_) { /* Optional persistence. */ }
        }
        if (!raw) return;
        const data = core.validatePayload(JSON.parse(raw));
        let stored = false;
        try { sessionStorage.setItem(key, JSON.stringify(data)); stored = true; } catch (_) { /* Render anyway. */ }
        render(data, !incoming, stored);
    } catch (error) {
        byId("message").className = "error";
        byId("message").textContent = "Importazione non riuscita: " + error.message;
    }
})();
