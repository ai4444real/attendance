from decimal import Decimal

import pytest

from backend.accounting_app.services import parse_fibu_payroll_csv


FIBU_TEXT = """Datum;Periode;Neu;Konto;Soll;Haben;Text;PeriodeVon;PeriodeBis
2026-02-02;2026-01;False;"10220";;9327.5500;"Pagamento";2026-01-01;2026-01-31
2026-02-02;2026-01;False;"22700";;261.0000;"LPP";2026-01-01;2026-01-31
2026-02-02;2026-01;False;"22710";;701.0000;"AVS/AD";2026-01-01;2026-01-31
2026-02-02;2026-01;False;"22730";;112.3000;"LAINF";2026-01-01;2026-01-31
2026-02-02;2026-01;False;"22790";;551.1000;"Imposte alla fonte";2026-01-01;2026-01-31
2026-02-02;2026-01;False;"50000";10952.9500;;"Salario";2026-01-01;2026-01-31
"""


def test_translates_balanced_fibu_payroll_rows() -> None:
    rows = parse_fibu_payroll_csv(FIBU_TEXT)
    assert [(row.description, row.translated_account_code, row.entry_side, row.amount) for row in rows] == [
        ("Stipendio netto", "2062", "credit", Decimal("9327.55")),
        ("LPP", "5720", "credit", Decimal("261.00")),
        ("AVS/AD", "5700", "credit", Decimal("701.00")),
        ("LAINF", "5730", "credit", Decimal("112.30")),
        ("Imposte alla fonte", "5790", "credit", Decimal("551.10")),
        ("Stipendio lordo", "5000", "debit", Decimal("10952.95")),
    ]


def test_rejects_unbalanced_payroll_rows() -> None:
    with pytest.raises(ValueError, match="non bilanciata"):
        parse_fibu_payroll_csv(FIBU_TEXT.replace("10952.9500", "10952.9400"))
