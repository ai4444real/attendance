from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import json

from backend.attendance_normalization.service import normalize_zoom_csv_file


CSV_SAMPLE = """Argomento,Digita,ID,Nome organizzatore,E-mail organizzatore,Ora di inizio,Ora di fine,Partecipanti,Durata (minuti),Minuti totali dei partecipanti,Reparto,Gruppo,Origine,Visualizzatori unici,Max visualizzazioni simultanee,Ora di creazione,Nome (nome originale),E-mail,Ora di ingresso,Ora di uscita,Durata (minuti),Guest,Risposta di esclusione di responsabilità per la registrazione,In sala d’attesa
BIAS,Riunione,896 1053 4856,Andrea Di Gregorio,digregorio@pnlevolution.com,01/30/2025 06:54:02 PM,01/30/2025 08:37:29 PM,3,104,620,,,Zoom,-,-,09/12/2024 07:00:59 PM,Andrea Di Gregorio (Host),digregorio@pnlevolution.com,01/30/2025 06:58:59 PM,01/30/2025 08:01:46 PM,63,No,,No
BIAS,Riunione,896 1053 4856,Andrea Di Gregorio,digregorio@pnlevolution.com,01/30/2025 06:54:02 PM,01/30/2025 08:37:29 PM,3,104,620,,,Zoom,-,-,09/12/2024 07:00:59 PM,Francesco Conte,,01/30/2025 06:58:37 PM,01/30/2025 08:01:42 PM,64,Sì,,No
BIAS,Riunione,896 1053 4856,Andrea Di Gregorio,digregorio@pnlevolution.com,01/30/2025 06:54:02 PM,01/30/2025 08:37:29 PM,3,104,620,,,Zoom,-,-,09/12/2024 07:00:59 PM,Francesco Conte,,01/30/2025 08:10:19 PM,01/30/2025 08:22:27 PM,13,Sì,,No
,,,,,,,,,,,,,,,,,,,,,,,
sessione,Riunione,839 1158 0485,Irene Bazzani,bazzani@pnlevolution.com,01/30/2025 03:04:41 PM,01/30/2025 04:21:39 PM,2,77,153,,,Zoom,-,-,05/27/2022 07:17:47 PM,Irene Bazzani (Host),bazzani@pnlevolution.com,01/30/2025 03:04:41 PM,01/30/2025 04:21:39 PM,77,No,,No
sessione,Riunione,839 1158 0485,Irene Bazzani,bazzani@pnlevolution.com,01/30/2025 03:04:41 PM,01/30/2025 04:21:39 PM,2,77,153,,,Zoom,-,-,05/27/2022 07:17:47 PM,Sena,,01/30/2025 03:07:01 PM,01/30/2025 04:21:38 PM,75,Sì,,No
"""

CSV_SAMPLE_WITH_NOISE = """Argomento,Digita,ID,Nome organizzatore,E-mail organizzatore,Ora di inizio,Ora di fine,Partecipanti,Durata (minuti),Minuti totali dei partecipanti,Reparto,Gruppo,Origine,Visualizzatori unici,Max visualizzazioni simultanee,Ora di creazione,Nome (nome originale),E-mail,Ora di ingresso,Ora di uscita,Durata (minuti),Guest,Risposta di esclusione di responsabilità per la registrazione,In sala d’attesa
BIAS,Riunione,896 1053 4856,Andrea Di Gregorio,digregorio@pnlevolution.com,01/30/2025 06:54:02 PM,01/30/2025 08:37:29 PM,4,104,620,,,Zoom,-,-,09/12/2024 07:00:59 PM,Andrea Di Gregorio (Host),digregorio@pnlevolution.com,01/30/2025 06:58:59 PM,01/30/2025 08:01:46 PM,63,No,,No
BIAS,Riunione,896 1053 4856,Andrea Di Gregorio,digregorio@pnlevolution.com,01/30/2025 06:54:02 PM,01/30/2025 08:37:29 PM,4,104,620,,,Zoom,-,-,09/12/2024 07:00:59 PM,Francesco Conte,,01/30/2025 06:58:37 PM,01/30/2025 08:01:42 PM,64,Sì,,No
BIAS,Riunione,896 1053 4856,Andrea Di Gregorio,digregorio@pnlevolution.com,01/30/2025 06:54:02 PM,01/30/2025 08:37:29 PM,4,104,620,,,Zoom,-,-,09/12/2024 07:00:59 PM,Francesco Conte,,01/30/2025 08:10:19 PM,01/30/2025 08:22:27 PM,13,Sì,,No
BIAS,Riunione,896 1053 4856,Andrea Di Gregorio,digregorio@pnlevolution.com,01/30/2025 06:54:02 PM,01/30/2025 08:37:29 PM,4,104,620,,,Zoom,-,-,09/12/2024 07:00:59 PM,gabrielenovello,,01/30/2025 07:00:39 PM,01/30/2025 07:08:50 PM,9,Sì,,No
BIAS,Riunione,896 1053 4856,Andrea Di Gregorio,digregorio@pnlevolution.com,01/30/2025 06:54:02 PM,01/30/2025 08:37:29 PM,4,104,620,,,Zoom,-,-,09/12/2024 07:00:59 PM,gabriele. novello ( gabrielenovello ),,01/30/2025 07:49:39 PM,01/30/2025 08:22:22 PM,33,Sì,,No
BIAS,Riunione,896 1053 4856,Andrea Di Gregorio,digregorio@pnlevolution.com,01/30/2025 06:54:02 PM,01/30/2025 08:37:29 PM,4,104,620,,,Zoom,-,-,09/12/2024 07:00:59 PM,Lidia C. Dumitriu,,01/30/2025 06:30:00 PM,01/30/2025 06:30:12 PM,1,Sì,,No
,,,,,,,,,,,,,,,,,,,,,,,
BIAS,Riunione,896 1053 9999,Andrea Di Gregorio,digregorio@pnlevolution.com,01/31/2025 06:00:00 PM,01/31/2025 06:14:00 PM,2,14,20,,,Zoom,-,-,09/12/2024 07:00:59 PM,Andrea Di Gregorio (Host),digregorio@pnlevolution.com,01/31/2025 06:00:00 PM,01/31/2025 06:14:00 PM,14,No,,No
BIAS,Riunione,896 1053 9999,Andrea Di Gregorio,digregorio@pnlevolution.com,01/31/2025 06:00:00 PM,01/31/2025 06:14:00 PM,2,14,20,,,Zoom,-,-,09/12/2024 07:00:59 PM,Antonia Colombo,,01/31/2025 06:01:00 PM,01/31/2025 06:12:00 PM,11,Sì,,No
"""

CSV_SAMPLE_WITH_PARENTHESES_NOISE = """Argomento,Digita,ID,Nome organizzatore,E-mail organizzatore,Ora di inizio,Ora di fine,Partecipanti,Durata (minuti),Minuti totali dei partecipanti,Reparto,Gruppo,Origine,Visualizzatori unici,Max visualizzazioni simultanee,Ora di creazione,Nome (nome originale),E-mail,Ora di ingresso,Ora di uscita,Durata (minuti),Guest,Risposta di esclusione di responsabilità per la registrazione,In sala d’attesa
COACHING,Riunione,826 5053 1117,Irene Bazzani,bazzani@pnlevolution.com,01/14/2025 06:41:56 PM,01/14/2025 10:39:44 PM,4,238,620,,,Zoom,-,-,05/27/2022 07:17:47 PM,Irene Bazzani (Host),bazzani@pnlevolution.com,01/14/2025 06:41:56 PM,01/14/2025 10:39:44 PM,238,No,,No
COACHING,Riunione,826 5053 1117,Irene Bazzani,bazzani@pnlevolution.com,01/14/2025 06:41:56 PM,01/14/2025 10:39:44 PM,4,238,620,,,Zoom,-,-,05/27/2022 07:17:47 PM,Nadia Gerli ( Nadia ),,01/14/2025 06:57:28 PM,01/14/2025 07:24:40 PM,27,Sì,,No
COACHING,Riunione,826 5053 1117,Irene Bazzani,bazzani@pnlevolution.com,01/14/2025 06:41:56 PM,01/14/2025 10:39:44 PM,4,238,620,,,Zoom,-,-,05/27/2022 07:17:47 PM,Nadia Gerli,,01/14/2025 07:24:41 PM,01/14/2025 08:24:22 PM,60,Sì,,No
"""


class NormalizationServiceTests(unittest.TestCase):
    def test_normalizes_only_preselected_uppercase_courses(self):
        with TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "sample.csv"
            csv_path.write_text(CSV_SAMPLE, encoding="utf-8")

            result = normalize_zoom_csv_file(csv_path, threshold=0.8)

        self.assertEqual(result.total_meetings_found, 2)
        self.assertEqual(result.threshold, 0.8)
        self.assertEqual(result.selected_courses, ["BIAS"])
        self.assertEqual(result.selected_meetings_count, 1)
        self.assertEqual(len(result.meetings), 1)
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0].course, "BIAS")
        self.assertEqual(result.records[0].calculated_presence_status, "prima_meta")
        self.assertGreater(len(result.meetings[0].timeline), 0)
        self.assertEqual(result.meetings[0].peak_active_count, 1)
        self.assertEqual(result.meetings[0].sampled_every_minutes, 10.0)

    def test_ignores_meetings_shorter_than_twenty_minutes(self):
        with TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "sample.csv"
            csv_path.write_text(CSV_SAMPLE_WITH_NOISE, encoding="utf-8")

            result = normalize_zoom_csv_file(csv_path, threshold=0.8)

        self.assertEqual(result.total_meetings_found, 2)
        self.assertEqual(result.selected_meetings_count, 1)
        self.assertTrue(any("meno di 20 minuti" in warning for warning in result.warnings))
        self.assertTrue(all(record.meeting_id != "896 1053 9999" for record in result.records))

    def test_ignores_records_shorter_than_five_minutes(self):
        with TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "sample.csv"
            csv_path.write_text(CSV_SAMPLE_WITH_NOISE, encoding="utf-8")

            result = normalize_zoom_csv_file(csv_path, threshold=0.8)

        full_names = sorted(f"{record.first_name} {record.last_name}".strip() for record in result.records)
        self.assertEqual(len(result.records), 2)
        self.assertEqual(full_names, ["Francesco Conte", "Gabriele Novello"])
        self.assertTrue(any("meno di 5 minuti" in warning for warning in result.warnings))

    def test_applies_identity_alias_rules_before_aggregation(self):
        with TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "sample.csv"
            csv_path.write_text(CSV_SAMPLE_WITH_NOISE, encoding="utf-8")
            rules_path = Path(temp_dir) / "identity_rules.json"
            rules_path.write_text(
                json.dumps(
                    {
                        "aliases": [
                            {
                                "canonical": {
                                    "first_name": "Gabriele",
                                    "last_name": "Novello",
                                    "full_name": "Gabriele Novello",
                                },
                                "aliases": [
                                    "gabrielenovello",
                                    "gabriele. novello ( gabrielenovello )",
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            result = normalize_zoom_csv_file(
                csv_path,
                threshold=0.8,
                identity_rules_path=rules_path,
            )

        gabriele_records = [
            record for record in result.records
            if record.first_name == "Gabriele" and record.last_name == "Novello"
        ]
        self.assertEqual(len(gabriele_records), 1)
        self.assertAlmostEqual(gabriele_records[0].minutes_first_half, 8.2)
        self.assertAlmostEqual(gabriele_records[0].minutes_second_half, 32.7)

    def test_applies_trim_end_minutes_meeting_override(self):
        with TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "sample.csv"
            csv_path.write_text(CSV_SAMPLE, encoding="utf-8")
            overrides_path = Path(temp_dir) / "meeting_overrides.json"
            overrides_path.write_text(
                json.dumps(
                    {
                        "meeting_overrides": [
                            {
                                "course": "BIAS",
                                "date": "2025-01-30",
                                "meeting_id": "896 1053 4856",
                                "trim_end_minutes": 11,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            result = normalize_zoom_csv_file(
                csv_path,
                threshold=0.8,
                meeting_overrides_path=overrides_path,
            )

        self.assertEqual(len(result.records), 1)
        record = result.records[0]
        self.assertEqual(record.effective_end, "2025-01-30T20:26:29")
        self.assertEqual(record.trim_end_minutes, 11)
        self.assertEqual(record.duration_second_half, 37.7)
        self.assertEqual(result.meetings[0].effective_end, "2025-01-30T20:26:29")
        self.assertEqual(result.meetings[0].trim_end_minutes, 11)

    def test_applies_trim_start_minutes_meeting_override(self):
        with TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "sample.csv"
            csv_path.write_text(CSV_SAMPLE, encoding="utf-8")
            overrides_path = Path(temp_dir) / "meeting_overrides.json"
            overrides_path.write_text(
                json.dumps(
                    {
                        "meeting_overrides": [
                            {
                                "course": "BIAS",
                                "date": "2025-01-30",
                                "meeting_id": "896 1053 4856",
                                "trim_start_minutes": 30,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            result = normalize_zoom_csv_file(
                csv_path,
                threshold=0.8,
                meeting_overrides_path=overrides_path,
            )

        self.assertEqual(len(result.records), 1)
        record = result.records[0]
        self.assertEqual(record.effective_start, "2025-01-30T19:30:00")
        self.assertEqual(record.trim_start_minutes, 30)
        self.assertEqual(result.meetings[0].effective_start, "2025-01-30T19:30:00")
        self.assertEqual(result.meetings[0].trim_start_minutes, 30)

    def test_applies_threshold_meeting_override(self):
        with TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "sample.csv"
            csv_path.write_text(CSV_SAMPLE, encoding="utf-8")
            overrides_path = Path(temp_dir) / "meeting_overrides.json"
            overrides_path.write_text(
                json.dumps(
                    {
                        "meeting_overrides": [
                            {
                                "course": "BIAS",
                                "date": "2025-01-30",
                                "meeting_id": "896 1053 4856",
                                "threshold": 0.75,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            result = normalize_zoom_csv_file(
                csv_path,
                threshold=0.8,
                meeting_overrides_path=overrides_path,
            )

        self.assertEqual(len(result.records), 1)
        record = result.records[0]
        self.assertEqual(record.threshold, 0.75)
        self.assertEqual(record.calculated_presence_status, "prima_meta")
        self.assertEqual(result.meetings[0].threshold, 0.75)

    def test_normalizes_parentheses_noise_in_zoom_display_names_before_grouping(self):
        with TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "sample.csv"
            csv_path.write_text(CSV_SAMPLE_WITH_PARENTHESES_NOISE, encoding="utf-8")

            result = normalize_zoom_csv_file(csv_path, threshold=0.8)

        self.assertEqual(result.selected_courses, ["COACHING"])
        self.assertEqual(len(result.records), 1)
        record = result.records[0]
        self.assertEqual(record.first_name, "Nadia")
        self.assertEqual(record.last_name, "Gerli")
        self.assertEqual(record.segment_count, 2)


if __name__ == "__main__":
    unittest.main()
