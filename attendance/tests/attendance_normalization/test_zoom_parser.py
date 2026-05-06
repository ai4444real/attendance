import unittest
from zoneinfo import ZoneInfo

from backend.attendance_normalization.zoom_parser import parse_zoom_csv_text


CSV_SAMPLE = """Argomento,Digita,ID,Nome organizzatore,E-mail organizzatore,Ora di inizio,Ora di fine,Partecipanti,Durata (minuti),Minuti totali dei partecipanti,Reparto,Gruppo,Origine,Visualizzatori unici,Max visualizzazioni simultanee,Ora di creazione,Nome (nome originale),E-mail,Ora di ingresso,Ora di uscita,Durata (minuti),Guest,Risposta di esclusione di responsabilità per la registrazione,In sala d’attesa
BIAS,Riunione,896 1053 4856,Andrea Di Gregorio,digregorio@pnlevolution.com,01/30/2025 06:54:02 PM,01/30/2025 08:37:29 PM,3,104,620,,,Zoom,-,-,09/12/2024 07:00:59 PM,Andrea Di Gregorio (Host),digregorio@pnlevolution.com,01/30/2025 06:58:59 PM,01/30/2025 08:01:46 PM,63,No,,No
BIAS,Riunione,896 1053 4856,Andrea Di Gregorio,digregorio@pnlevolution.com,01/30/2025 06:54:02 PM,01/30/2025 08:37:29 PM,3,104,620,,,Zoom,-,-,09/12/2024 07:00:59 PM,Francesco Conte,,01/30/2025 06:58:37 PM,01/30/2025 08:01:42 PM,64,Sì,,No
BIAS,Riunione,896 1053 4856,Andrea Di Gregorio,digregorio@pnlevolution.com,01/30/2025 06:54:02 PM,01/30/2025 08:37:29 PM,3,104,620,,,Zoom,-,-,09/12/2024 07:00:59 PM,Francesco Conte,,01/30/2025 08:10:19 PM,01/30/2025 08:22:27 PM,13,Sì,,No
,,,,,,,,,,,,,,,,,,,,,,,
sessione,Riunione,839 1158 0485,Irene Bazzani,bazzani@pnlevolution.com,01/30/2025 03:04:41 PM,01/30/2025 04:21:39 PM,2,77,153,,,Zoom,-,-,05/27/2022 07:17:47 PM,Irene Bazzani (Host),bazzani@pnlevolution.com,01/30/2025 03:04:41 PM,01/30/2025 04:21:39 PM,77,No,,No
sessione,Riunione,839 1158 0485,Irene Bazzani,bazzani@pnlevolution.com,01/30/2025 03:04:41 PM,01/30/2025 04:21:39 PM,2,77,153,,,Zoom,-,-,05/27/2022 07:17:47 PM,Sena,,01/30/2025 03:07:01 PM,01/30/2025 04:21:38 PM,75,Sì,,No
"""


class ZoomParserTests(unittest.TestCase):
    def test_parses_multiple_meetings_separated_by_blank_rows(self):
        parsed = parse_zoom_csv_text(CSV_SAMPLE)

        self.assertEqual(len(parsed.meetings), 2)
        self.assertEqual(parsed.meetings[0].course, "BIAS")
        self.assertEqual(parsed.meetings[1].course, "sessione")

    def test_skips_host_rows_and_keeps_guest_segments(self):
        parsed = parse_zoom_csv_text(CSV_SAMPLE)

        first_meeting = parsed.meetings[0]
        self.assertEqual(len(first_meeting.segments), 2)
        self.assertTrue(all(segment.full_name != "Andrea Di Gregorio (Host)" for segment in first_meeting.segments))

    def test_groups_duplicate_header_names_by_deduplicating_them(self):
        parsed = parse_zoom_csv_text(CSV_SAMPLE)

        self.assertEqual(parsed.warnings, [])
        self.assertEqual(parsed.meetings[0].meeting_id, "896 1053 4856")

    def test_splits_name_into_first_and_last_name(self):
        parsed = parse_zoom_csv_text(CSV_SAMPLE)

        segment = parsed.meetings[0].segments[0]
        self.assertEqual(segment.first_name, "Francesco")
        self.assertEqual(segment.last_name, "Conte")

    def test_parsed_datetimes_are_timezone_aware_in_europe_zurich(self):
        parsed = parse_zoom_csv_text(CSV_SAMPLE)

        meeting = parsed.meetings[0]
        segment = meeting.segments[0]

        self.assertEqual(meeting.start_time.tzinfo, ZoneInfo("Europe/Zurich"))
        self.assertEqual(meeting.start_time.isoformat(), "2025-01-30T18:54:02+01:00")
        self.assertEqual(segment.join_time.isoformat(), "2025-01-30T18:58:37+01:00")


if __name__ == "__main__":
    unittest.main()
