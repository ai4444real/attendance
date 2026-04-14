from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.attendance_normalization.exporters import (
    build_default_output_path,
    normalization_result_to_csv,
    normalization_result_to_json,
    write_normalization_result_csv,
    write_normalization_result_json,
)
from backend.attendance_normalization.service import normalize_zoom_csv_file


CSV_SAMPLE = """Argomento,Digita,ID,Nome organizzatore,E-mail organizzatore,Ora di inizio,Ora di fine,Partecipanti,Durata (minuti),Minuti totali dei partecipanti,Reparto,Gruppo,Origine,Visualizzatori unici,Max visualizzazioni simultanee,Ora di creazione,Nome (nome originale),E-mail,Ora di ingresso,Ora di uscita,Durata (minuti),Guest,Risposta di esclusione di responsabilità per la registrazione,In sala d’attesa
BIAS,Riunione,896 1053 4856,Andrea Di Gregorio,digregorio@pnlevolution.com,01/30/2025 06:54:02 PM,01/30/2025 08:37:29 PM,3,104,620,,,Zoom,-,-,09/12/2024 07:00:59 PM,Andrea Di Gregorio (Host),digregorio@pnlevolution.com,01/30/2025 06:58:59 PM,01/30/2025 08:01:46 PM,63,No,,No
BIAS,Riunione,896 1053 4856,Andrea Di Gregorio,digregorio@pnlevolution.com,01/30/2025 06:54:02 PM,01/30/2025 08:37:29 PM,3,104,620,,,Zoom,-,-,09/12/2024 07:00:59 PM,Francesco Conte,,01/30/2025 06:58:37 PM,01/30/2025 08:01:42 PM,64,Sì,,No
"""


class ExportersTests(unittest.TestCase):
    def test_json_export_contains_records_and_selected_courses(self):
        with TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "sample.csv"
            csv_path.write_text(CSV_SAMPLE, encoding="utf-8")
            result = normalize_zoom_csv_file(csv_path, threshold=0.8)

        json_output = normalization_result_to_json(result)

        self.assertIn('"selected_courses"', json_output)
        self.assertIn('"records"', json_output)
        self.assertIn('"BIAS"', json_output)

    def test_csv_export_contains_expected_headers_and_normalized_values(self):
        with TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "sample.csv"
            csv_path.write_text(CSV_SAMPLE, encoding="utf-8")
            result = normalize_zoom_csv_file(csv_path, threshold=0.8)

        csv_output = normalization_result_to_csv(result)

        self.assertIn("Corso,Data,Nome,Cognome,Email,Presenza", csv_output)
        self.assertIn("BIAS", csv_output)
        self.assertIn("Francesco,Conte", csv_output)

    def test_write_helpers_create_files(self):
        with TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "sample.csv"
            csv_path.write_text(CSV_SAMPLE, encoding="utf-8")
            result = normalize_zoom_csv_file(csv_path, threshold=0.8)

            json_destination = Path(temp_dir) / "result.json"
            csv_destination = Path(temp_dir) / "result.csv"

            written_json = write_normalization_result_json(result, json_destination)
            written_csv = write_normalization_result_csv(result, csv_destination)

            self.assertTrue(written_json.exists())
            self.assertTrue(written_csv.exists())
            self.assertIn('"records"', written_json.read_text(encoding="utf-8"))
            self.assertIn("Corso,Data,Nome,Cognome,Email,Presenza", written_csv.read_text(encoding="utf-8-sig"))

    def test_default_output_path_keeps_source_stem_and_extension(self):
        path = build_default_output_path("attendance/data/report-zoom-2025-TUTTO-Simone.csv", "normalized", "json")

        self.assertEqual(path.suffix, ".json")
        self.assertIn("report-zoom-2025-TUTTO-Simone_normalized_", path.name)


if __name__ == "__main__":
    unittest.main()
