const { test } = require('node:test');
const assert = require('node:assert/strict');
const { forecast, parseDate, parseCents, toTsv } = require('../utilities/esposizione-forecast.js');
const row = overrides => ({ customer: 'Cliente', frequency: 'Monthly', next: '25. Nov 2026', end: '25. Jan 2027', amount: 'CHF 500.00', ...overrides });

test('includes Next and end date, sums invoices per month in integer cents', () => {
    const result = forecast([row({ amount: 'CHF 0.10' }), row({ amount: 'CHF 0.20' })]);
    assert.deepEqual(result.months.map(m => [m.key, m.cents, m.invoices.length]), [
        ['2026-11', 30, 2], ['2026-12', 30, 2], ['2027-01', 30, 2],
    ]);
    assert.equal(result.totalCents, 90);
    assert.equal(result.invoiceCount, 6);
});

test('semiannual series includes zero months between emissions', () => {
    const result = forecast([row({ frequency: 'Every 6 months', next: '10. Jan 2027', end: '10. Jul 2027' })]);
    assert.equal(result.months.length, 7);
    assert.equal(result.months[1].cents, 0);
    assert.equal(result.invoiceCount, 2);
    assert.equal(result.totalCents, 100000);
});

test('month-end is clamped without losing the original day in later months', () => {
    const result = forecast([row({ next: '31. Jan 2027', end: '31. Mar 2027' })]);
    assert.deepEqual(result.months.flatMap(m => m.invoices.map(i => i.date)), ['2027-01-31', '2027-02-28', '2027-03-31']);
    const leap = forecast([row({ next: '31. Jan 2028', end: '29. Feb 2028' })]);
    assert.equal(leap.months[1].invoices[0].date, '2028-02-29');
});

test('date final before scheduled day excludes that emission', () => {
    const result = forecast([row({ next: '25. Nov 2026', end: '24. Dec 2026' })]);
    assert.equal(result.invoiceCount, 1);
});

test('invalid series are reported, never silently included or partially scheduled', () => {
    const result = forecast([
        row({ frequency: 'Weekly' }), row({ end: '' }), row({ next: '31. Feb 2027' }),
        row({ amount: 'EUR 500.00' }), row({ end: '01. Jan 2026' }), row({}),
    ]);
    assert.equal(result.warnings.length, 5);
    assert.equal(result.accepted, 1);
    assert.equal(result.invoiceCount, 3);
    assert.equal(result.totalCents, 150000);
    assert.deepEqual(forecast([]).months, []);
});

test('dates are explicit and locale independent; CHF separators are handled', () => {
    assert.deepEqual(parseDate('25. Nov 2026'), { year: 2026, month: 11, day: 25 });
    assert.deepEqual(parseDate('25.11.2026'), parseDate('2026-11-25'));
    assert.throws(() => parseDate('2026-13-01'));
    assert.throws(() => parseDate('02/03/2026'));
    for (const text of ["CHF 1’234.50", "CHF 1'234.50", '1 234,50 CHF', 'CHF 1,234.50']) assert.equal(parseCents(text), 123450);
    assert.equal(parseCents('CHF -10.50'), -1050);
    assert.throws(() => parseCents('CHF 500.001'));
});

test('copy includes all months and totals; detailed copy preserves separate invoices safely', () => {
    const result = forecast([row({ customer: '=DANGEROUS\tNAME', amount: 'CHF 1.25' })]);
    const summary = toTsv(result);
    assert.match(summary, /2026-11\t1\t1.25/);
    assert.match(summary, /Totale\t3\t3.75$/);
    const details = toTsv(result, true).split('\n');
    assert.equal(details.length, 4);
    assert.ok(details[1].includes("'=DANGEROUS NAME"));
});
