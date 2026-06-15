import unittest

from app.services.gemini import GeminiService


class FallbackParserTests(unittest.TestCase):
    def test_parses_customer_multiple_items_and_delivery_time(self):
        result = GeminiService._parse_order_fallback(
            "Kal Gupta Store ko subah 5 packet Parle-G aur 2 kg sugar bhej dena."
        )

        self.assertEqual(result["customer_name"], "Gupta Store")
        self.assertEqual(result["delivery_time"].lower(), "kal subah")
        self.assertEqual(
            result["items"],
            [
                {"name": "Parle-G", "quantity": 5, "unit": "packet", "price": None},
                {"name": "sugar", "quantity": 2, "unit": "kg", "price": None},
            ],
        )

    def test_does_not_put_order_sentence_in_delivery_time(self):
        result = GeminiService._parse_order_fallback(
            "Gupta Store ko 5 packet Parle-G aur 2 kg sugar bhej dena."
        )

        self.assertEqual(result["delivery_time"], "")

    def test_returns_no_items_when_quantity_is_missing(self):
        result = GeminiService._parse_order_fallback("Gupta Store ko chips bhej dena.")

        self.assertEqual(result["customer_name"], "Gupta Store")
        self.assertEqual(result["items"], [])

    def test_removes_timeline_labels_before_parsing(self):
        result = GeminiService._parse_order_fallback(
            "00:01 Gupta Store ko 00:04 5 packet Parle-G aur 2 kg sugar bhej dena 00:10"
        )

        self.assertEqual(result["customer_name"], "Gupta Store")
        self.assertEqual([item["quantity"] for item in result["items"]], [5, 2])

    def test_parses_clear_hindi_script_order(self):
        result = GeminiService._parse_order_fallback(
            "कल गुप्ता स्टोर को सुबह 5 पैकेट पारले जी और 2 केजी शुगर भेज देना"
        )

        self.assertEqual(result["customer_name"], "गुप्ता स्टोर")
        self.assertEqual(result["delivery_time"], "कल सुबह")
        self.assertEqual(
            result["items"],
            [
                {"name": "पारले जी", "quantity": 5, "unit": "पैकेट", "price": None},
                {"name": "शुगर", "quantity": 2, "unit": "केजी", "price": None},
            ],
        )

    def test_does_not_treat_delivery_clock_as_item_quantity(self):
        result = GeminiService._parse_order_fallback(
            "Gupta Store ko shaam 5 baje 2 kg sugar bhej dena"
        )

        self.assertEqual(result["delivery_time"].lower(), "shaam 5 baje")
        self.assertEqual(
            result["items"],
            [{"name": "sugar", "quantity": 2, "unit": "kg", "price": None}],
        )


if __name__ == "__main__":
    unittest.main()
