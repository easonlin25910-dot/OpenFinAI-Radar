import unittest
from datetime import date, datetime, timezone

from openfinai_radar.models import TimeEvidence, resolve_effective_time


class TimeModelTests(unittest.TestCase):
    def test_business_event_beats_earlier_media_report(self):
        chosen = resolve_effective_time(
            [
                TimeEvidence(date(2026, 8, 1), "media_report", 0.65),
                TimeEvidence(date(2026, 8, 5), "product_release", 0.98),
            ],
            datetime(2026, 8, 6, tzinfo=timezone.utc),
        )
        self.assertEqual(chosen.kind, "product_release")
        self.assertEqual(chosen.value, date(2026, 8, 5))

    def test_earliest_evidence_wins_within_same_grade(self):
        chosen = resolve_effective_time(
            [
                TimeEvidence(date(2026, 8, 8), "media_report", 0.65),
                TimeEvidence(date(2026, 8, 3), "media_report", 0.65),
            ],
            datetime(2026, 8, 9, tzinfo=timezone.utc),
        )
        self.assertEqual(chosen.value, date(2026, 8, 3))

    def test_discovery_time_is_last_resort(self):
        chosen = resolve_effective_time([], datetime(2026, 8, 9, tzinfo=timezone.utc))
        self.assertEqual(chosen.kind, "system_discovery")
        self.assertEqual(chosen.confidence, 0.30)


if __name__ == "__main__":
    unittest.main()

