import unittest
from datetime import datetime
from app.services.time_parser import parse_delivery_time

class TestTimeParser(unittest.TestCase):
    def setUp(self):
        self.ref = datetime(2026, 6, 28, 12, 0, 0)
        self.tomorrow_str = "2026-06-29"

    def test_din_mein_pm(self):
        res = parse_delivery_time("kal saade paanch baje din mein", self.ref)
        self.assertEqual(res["normalized"], f"{self.tomorrow_str} 5:30 PM")
        self.assertIsNone(res["warning"])

    def test_din_mein_pm_bare_hour(self):
        res = parse_delivery_time("kal 2 baje din mein", self.ref)
        self.assertEqual(res["normalized"], f"{self.tomorrow_str} 2:00 PM")
        self.assertIsNone(res["warning"])

    def test_din_mein_am_warning(self):
        res = parse_delivery_time("kal 10 baje din me", self.ref)
        self.assertEqual(res["normalized"], f"{self.tomorrow_str} 10:00")
        self.assertEqual(res["warning"], "AM/PM ambiguity detected. Please confirm.")

    def test_bare_time_warning(self):
        res = parse_delivery_time("kal 5:30 baje", self.ref)
        self.assertEqual(res["normalized"], f"{self.tomorrow_str} 5:30")
        self.assertEqual(res["warning"], "AM/PM ambiguity detected. Please confirm.")

    def test_raat_pm(self):
        res = parse_delivery_time("kal 5:30 baje raat ko", self.ref)
        self.assertEqual(res["normalized"], f"{self.tomorrow_str} 5:30 PM")
        self.assertIsNone(res["warning"])

    def test_subah_am(self):
        res = parse_delivery_time("kal 8 baje subah", self.ref)
        self.assertEqual(res["normalized"], f"{self.tomorrow_str} 8:00 AM")
        self.assertIsNone(res["warning"])

if __name__ == "__main__":
    unittest.main()
