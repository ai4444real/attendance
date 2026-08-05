from decimal import Decimal

import pytest

from backend.accounting_app.services import (
    parse_postfinance_credit_card_pdf,
    parse_postfinance_credit_card_text,
)


def test_parses_charges_foreign_currency_and_credits() -> None:
    text = """
    Contabiliz- Acquisti Dettagli Importo in CHF
    10.04.26 09.04.26 CANVA* I04846 CANVA.COM USATX EUR 12.00 11.52
    Azienda grafica
    Cambio 0.9440968418 del 09.04.26 CHF 11.33
    Tassa amministrativa 1.70% CHF 0.19
    14.04.26 14.04.26 RIMBORSO ESERCENTE -8.40
    Totale PostFinance Visa Business Card 3.12
    27.04.26 Riporto del saldo sul conto principale -3.12
    """

    transactions = parse_postfinance_credit_card_text(text)

    assert [(item.date, item.description, item.amount) for item in transactions] == [
        ("10.04.2026", "CANVA* I04846 CANVA.COM USATX EUR 12.00", Decimal("-11.52")),
        ("14.04.2026", "RIMBORSO ESERCENTE", Decimal("8.40")),
    ]


def test_rejects_empty_or_non_transaction_pdf() -> None:
    with pytest.raises(ValueError, match="vuoto"):
        parse_postfinance_credit_card_pdf(b"")
