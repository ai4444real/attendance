from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.attendance_normalization.service import normalize_zoom_csv_file


CSV_SAMPLE = """Argomento,Digita,ID,Nome organizzatore,E-mail organizzatore,Ora di inizio,Ora di fine,Partecipanti,Durata (minuti),Minuti totali dei partecipanti,Reparto,Gruppo,Origine,Visualizzatori unici,Max visualizzazioni simultanee,Ora di creazione,Nome (nome originale),E-mail,Ora di ingresso,Ora di uscita,Durata (minuti),Guest,Risposta di esclusione di responsabilità per la registrazione,In sala d’attesa
BIAS,Riunione,896 1053 4856,Andrea Di Gregorio,digregorio@pnlevolution.com,01/30/2025 06:54:02 PM,01/30/2025 08:37:29 PM,3,104,620,,,Zoom,-,-,09/12/2024 07:00:59 PM,Andrea Di Gregorio (Host),digregorio@pnlevolution.com,01/30/2025 06:58:59 PM,01/30/2025 08:01:46 PM,63,No,,No
BIAS,Riunione,896 1053 4856,Andrea Di Gregorio,digregorio@pnlevolution.com,01/30/2025 06:54:02 PM,01/30/2025 08:37:29 PM,3,104,620,,,Zoom,-,-,09/12/2024 07:00:59 PM,Francesco Conte,,01/30/2025 06:58:37 PM,01/30/2025 08:01:42 PM,64,Sì,,No
BIAS,Riunione,896 1053 4856,Andrea Di Gregorio,digregorio@pnlevolution.com,01/30/2025 06:54:02 PM,01/30/2025 08:37:29 PM,3,104,620,,,Zoom,-,-,09/12/2024 07:00:59 PM,Francesco Conte,,01/30/2025 08:10:19 PM,01/30/2025 08:22:27 PM,13,Sì,,No
,,,,,,,,,,,,,,,,,,,,,,,
sessione,Riunione,839 1158 0485,Irene Bazzani,bazzani@pnlevolution.com,01/30/2025 03:04:41 PM,01/30/2025 04:21:39 PM,2,77,153,,,Zoom,-,-,05/27/2022 07:17:47 PM,Irene Bazzani (Host),bazzani@pnlevolution.com,01/30/2025 03:04:41 PM,01/30/2025 04:21:39 PM,77,No,,No
sessione,Riunione,839 1158 0485,Irene Bazzani,bazzani@pnlevolution.com,01/30/2025 03:04:41 PM,01/30/2025 04:21:39 PM,2,77,153,,,Zoom,-,-,05/27/2022 07:17:47 PM,Sena,,01/30/2025 03:07:01 PM,01/30/2025 04:21:38 PM,75,Sì,,No
"""


class NormalizationServiceTests(unittest.TestCase):
    def test_normalizes_only_preselected_uppercase_courses(self):
        with TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "sample.csv"
            csv_path.write_text(CSV_SAMPLE, encoding="utf-8")

            result = normalize_zoom_csv_file(csv_path, threshold=0.8)

        self.assertEqual(result.total_meetings_found, 2)
        self.assertEqual(result.selected_courses, ["BIAS"])
        self.assertEqual(result.selected_meetings_count, 1)
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0].course, "BIAS")
        self.assertEqual(result.records[0].calculated_presence_status, "prima_meta")


if __name__ == "__main__":
    unittest.main()
