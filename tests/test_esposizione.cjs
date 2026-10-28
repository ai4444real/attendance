const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const { readRecurringPage, validatePayload, makeBookmarklet } = require('../utilities/esposizione-core.js');

const cell = (innerText, colSpan = 1) => ({ innerText, colSpan, rowSpan: 1 });
const row = (...values) => ({ cells: values.map(value => typeof value === 'string' ? cell(value) : value) });
function fixture() {
    const header = row(cell('FREQUENCY', 2), 'CUSTOMER', 'FIRST INVOICE', 'NEXT', 'END DATE', 'AMOUNT', 'STATUS', '');
    const active = row('Preview', 'Monthly', 'Cliente <b>test</b>', '25. May 2027', '25. May 2027', '25. Jul 2027', 'CHF 500.00', 'Draft', '');
    const ended = row('Preview', 'Monthly', 'Cliente terminato', '25. May 2026', '', '25. Jul 2026', 'CHF 500.00', 'Draft', '');
    const footer = row(cell('1–200 of 232', 9));
    const table = { rows: [header, active, ended, footer], getClientRects: () => [1] };
    const hidden = { rows: [header, active], getClientRects: () => [] };
    const doc = { querySelectorAll: () => [hidden, table] };
    return { table, doc };
}

test('maps colspan header, reads Next, excludes ended rows and preserves footer diagnostics', () => {
    const data = validatePayload(readRecurringPage(fixture().doc));
    assert.equal(data.scanned, 3);
    assert.equal(data.excluded, 1);
    assert.deepEqual(data.rows, [{ frequency: 'Monthly', customer: 'Cliente <b>test</b>', first: '25. May 2027', next: '25. May 2027', end: '25. Jul 2027', amount: 'CHF 500.00', status: 'Draft' }]);
    assert.deepEqual(data.unrecognized, [['1–200 of 232']]);
});

test('rejects ambiguous tables instead of silently choosing one', () => {
    const { table } = fixture();
    assert.throws(() => readRecurringPage({ querySelectorAll: () => [table, table] }), /2 tabelle/);
});

test('rejects inconsistent payload counts and blank Next fields', () => {
    const data = readRecurringPage(fixture().doc);
    assert.throws(() => validatePayload({ ...data, scanned: 10 }), /non validi/);
    data.rows[0].next = ' ';
    assert.throws(() => validatePayload(data), /non validi/);
});

test('bookmarklet transfers real records in the fragment in the same tab', () => {
    let destination;
    const bookmarklet = makeBookmarklet('https://rebekko.pnlevolution.com');
    vm.runInNewContext(decodeURIComponent(bookmarklet.slice('javascript:'.length)), {
        document: fixture().doc,
        location: { origin: 'https://app.smallinvoice.com', assign: value => { destination = value; } },
        confirm: () => true,
        alert: message => assert.fail(message),
    });
    const url = new URL(destination);
    assert.equal(url.pathname, '/utilities/esposizione');
    assert.equal(url.search, '');
    const data = validatePayload(JSON.parse(decodeURIComponent(url.hash.slice('#esposizione='.length))));
    assert.equal(data.rows.length, 1);
    assert.equal(data.rows[0].customer, 'Cliente <b>test</b>');
});

test('cancelled transfer does not navigate', () => {
    vm.runInNewContext(decodeURIComponent(makeBookmarklet('https://rebekko.pnlevolution.com').slice(11)), {
        document: fixture().doc,
        location: { origin: 'https://app.smallinvoice.com', assign: () => assert.fail('Navigated after cancel') },
        confirm: () => false,
        alert: message => assert.fail(message),
    });
});
