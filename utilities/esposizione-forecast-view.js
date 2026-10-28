(function () {
    "use strict";
    const byId = id => document.getElementById(id);
    const money = cents => new Intl.NumberFormat("it-CH", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(cents / 100);
    const monthLabel = key => new Intl.DateTimeFormat("it-CH", { month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(key + "-01T12:00:00Z"));
    let current = null;
    function element(tag, text, className) {
        const node = document.createElement(tag);
        if (text !== undefined) node.textContent = text;
        if (className) node.className = className;
        return node;
    }
    function invoiceTable(invoices) {
        const table = element("table"), head = element("thead"), header = element("tr"), body = element("tbody");
        for (const title of ["Data", "Cliente", "Importo CHF"]) header.append(element("th", title));
        head.append(header);
        for (const invoice of invoices) {
            const tr = element("tr");
            tr.append(element("td", invoice.date.split("-").reverse().join(".")), element("td", invoice.customer), element("td", money(invoice.cents), "number"));
            body.append(tr);
        }
        table.append(head, body);
        return table;
    }
    function openMonth(key) {
        const details = byId("month-" + key);
        details.open = true;
        details.scrollIntoView({ behavior: "smooth", block: "center" });
        details.querySelector("summary").focus({ preventScroll: true });
    }
    function drawChart(months) {
        byId("chart").replaceChildren();
        if (!months.length) return;
        const ns = "http://www.w3.org/2000/svg";
        const svgNode = (tag, attrs, text) => {
            const node = document.createElementNS(ns, tag);
            for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
            if (text !== undefined) node.textContent = text;
            return node;
        };
        const width = Math.max(850, months.length * 78 + 110), height = 320;
        const left = 100, right = width - 20, top = 30, bottom = 250;
        const maximum = Math.max(100, ...months.map(month => month.cents));
        const minimum = Math.min(0, ...months.map(month => month.cents));
        const y = cents => bottom - (cents - minimum) / (maximum - minimum) * (bottom - top);
        const svg = svgNode("svg", { width, height, viewBox: "0 0 " + width + " " + height, role: "group", "aria-label": "Importi previsti per mese in CHF. Ogni barra apre le fatture del mese." });
        for (let i = 0; i <= 4; i++) {
            const value = minimum + (maximum - minimum) * i / 4, position = y(value);
            svg.append(svgNode("line", { x1: left, x2: right, y1: position, y2: position, stroke: "#d9e2ec" }));
            svg.append(svgNode("text", { x: left - 10, y: position + 4, "text-anchor": "end", fill: "#52606d", "font-size": 12 }, money(Math.round(value))));
        }
        svg.append(svgNode("line", { x1: left, x2: right, y1: y(0), y2: y(0), stroke: "#52606d" }));
        const step = (right - left) / months.length;
        for (const [index, month] of months.entries()) {
            const x = left + step * index + step / 2;
            const label = monthLabel(month.key) + ": CHF " + money(month.cents) + ", " + month.invoices.length + " fatture";
            const group = svgNode("g", { role: "button", tabindex: "0", "aria-label": label });
            group.append(svgNode("title", {}, label));
            // Transparent full-height target also makes zero months clickable.
            group.append(svgNode("rect", { x: x - step * .4, y: top, width: step * .8, height: bottom - top, fill: "transparent", "pointer-events": "all", class: "hit-area" }));
            group.append(svgNode("rect", { x: x - step * .28, y: Math.min(y(0), y(month.cents)), width: step * .56, height: Math.max(2, Math.abs(y(0) - y(month.cents))), fill: month.cents < 0 ? "#b45309" : "#005090", rx: 3 }));
            group.append(svgNode("text", { x, y: month.cents < 0 ? y(month.cents) + 16 : y(month.cents) - 8, "text-anchor": "middle", fill: "#102a43", "font-size": 11 }, money(month.cents)));
            group.append(svgNode("text", { x, y: 282, "text-anchor": "middle", fill: "#102a43", "font-size": 12 }, month.key));
            group.addEventListener("click", () => openMonth(month.key));
            group.addEventListener("keydown", event => {
                if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openMonth(month.key); }
            });
            svg.append(group);
        }
        byId("chart").append(svg);
    }
    function render(rows) {
        current = window.EsposizioneForecast.forecast(rows);
        byId("forecastTotal").textContent = money(current.totalCents);
        byId("forecastCount").textContent = current.invoiceCount;
        byId("forecastMonths").textContent = current.months.length;
        byId("monthlyCount").textContent = current.invoiceCount;
        byId("monthlyTotal").textContent = money(current.totalCents);
        byId("forecastEmpty").hidden = current.months.length !== 0;
        byId("forecastWarnings").hidden = current.warnings.length === 0;
        byId("warningList").replaceChildren(...current.warnings.map(warning => element("li", "Riga " + warning.row + " · " + warning.customer + ": " + warning.message)));
        byId("monthlyRows").replaceChildren();
        for (const month of current.months) {
            const tr = element("tr"), cell = element("td"), details = element("details");
            details.id = "month-" + month.key;
            details.append(element("summary", monthLabel(month.key)));
            details.append(month.invoices.length ? invoiceTable(month.invoices) : element("p", "Nessuna fattura prevista in questo mese."));
            cell.append(details);
            tr.append(cell, element("td", month.invoices.length, "number"), element("td", money(month.cents), "number"));
            byId("monthlyRows").append(tr);
        }
        byId("copyMonthly").disabled = byId("copyInvoices").disabled = !current.months.length;
        byId("tableCopyStatus").textContent = "";
        byId("manualCopy").hidden = true;
        drawChart(current.months);
    }
    async function copy(detailed) {
        if (!current) return;
        const text = window.EsposizioneForecast.toTsv(current, detailed);
        try {
            await navigator.clipboard.writeText(text);
            byId("manualCopy").hidden = true;
            byId("tableCopyStatus").textContent = "Copiato: puoi incollare in Excel, Google Sheets o un altro documento.";
        } catch (_) {
            byId("manualCopy").hidden = false;
            byId("tableCopyText").value = text;
            byId("tableCopyText").select();
            byId("tableCopyStatus").textContent = "Copia manualmente il testo selezionato.";
        }
    }
    byId("copyMonthly").addEventListener("click", () => copy(false));
    byId("copyInvoices").addEventListener("click", () => copy(true));
    window.EsposizioneForecastView = {
        render,
        clear() {
            current = null;
            for (const id of ["chart", "monthlyRows", "warningList"]) byId(id).replaceChildren();
            byId("tableCopyText").value = "";
            byId("manualCopy").hidden = true;
        },
    };
})();
