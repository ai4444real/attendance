from decimal import Decimal

import pytest

from backend.accounting_app.services import parse_bank_csv


def _csv(account_header: str) -> str:
    return "\n".join([
        'Date from:;="01.01.2026"', 'Date to:;="30.06.2026"',
        'Entry type:;="All"', account_header, 'Currency:;="CHF"', '',
        'Date;Notification text;Credit;Debit;Value;Balance', '',
        '12.05.2026;STRIPE C4O2S5;245.39;;12.05.2026;56145.31',
        '', 'Total;', '',
    ]) + "\n"


@pytest.mark.parametrize('label', ['Account:', 'Conto:', 'Konto:', 'Compte:', 'IBAN:'])
def test_localized_headers_identify_the_same_bank_account(label):
    item, = parse_bank_csv(_csv(f'{label};="CH42 0900 0000 6974 6625 0"'), 'postfinance')
    assert item.source_key == 'CH4209000000697466250'
    assert item.date == '12.05.2026'
    assert item.amount == Decimal('245.39')
    assert item.balance == Decimal('56145.31')


@pytest.mark.parametrize('header', ['', 'Unknown:;CH4209000000697466250', 'Conto:;', 'Account:;postfinance'])
def test_missing_or_invalid_account_stops_import(header):
    with pytest.raises(ValueError, match='Conto PostFinance'):
        parse_bank_csv(_csv(header), 'postfinance')


def test_conflicting_accounts_stop_import():
    text = _csv('Account:;CH4209000000697466250').replace(
        'Currency:;="CHF"', 'Conto:;CH9300762011623852957',
    )
    with pytest.raises(ValueError, match='ambiguo'):
        parse_bank_csv(text, 'postfinance')
