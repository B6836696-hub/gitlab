import unittest
from dataclasses import replace
from unittest.mock import patch

from app import create_app, format_current, format_voltage
from bjt import calculate_operating_point

VALID = {
    "vcc": "12", "r1": "47000", "r2": "10000", "rc": "2200",
    "re": "1000", "beta": "150", "vbe": "0.7",
}


class TestFormatting(unittest.TestCase):
    def test_current_units(self):
        self.assertEqual(format_current(0), "0 mA")
        self.assertEqual(format_current(0.0013236752), "1.3237 mA")
        self.assertEqual(format_current(8.8245014873e-06), "8.8245 µA")

    def test_voltage_units(self):
        self.assertEqual(format_voltage(7.7554147846), "7.7554 V")


class TestRoutes(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()

    def test_get_form(self):
        response = self.client.get("/")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        for field in ("vcc", "r1", "r2", "rc", "re", "beta", "vbe"):
            self.assertIn(f'name="{field}"', body)

    def test_valid_post_shows_operating_point(self):
        response = self.client.post("/", data=VALID)
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("1.3237 mA", body)
        self.assertIn("7.7554 V", body)
        self.assertIn("Active", body)
        self.assertIn('data-status="MATCH"', body)
        self.assertNotIn("MISMATCH", body)

    def test_invalid_post_shows_error_and_no_results(self):
        response = self.client.post("/", data=dict(VALID, vcc="0"))
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("ต้องมากกว่า 0 V", body)
        self.assertNotIn('id="results"', body)

    def test_missing_field_shows_error_not_500(self):
        data = dict(VALID)
        del data["r1"]
        response = self.client.post("/", data=data)
        self.assertEqual(response.status_code, 200)
        self.assertIn("กรุณากรอกเป็นตัวเลข", response.get_data(as_text=True))

    def test_cutoff_post_shows_warning(self):
        response = self.client.post("/", data=dict(VALID, r2="1000"))
        body = response.get_data(as_text=True)
        self.assertIn("Cutoff", body)
        self.assertIn('data-status="MATCH"', body)
        self.assertNotIn("MISMATCH", body)

    def test_saturation_post_shows_warning(self):
        response = self.client.post("/", data=dict(VALID, rc="10000", re="100"))
        body = response.get_data(as_text=True)
        self.assertIn("Saturation", body)
        self.assertIn("IC(sat)", body)

    def test_mismatch_post_shows_mismatch_warning(self):
        def wrong_nodal(inputs):
            point = calculate_operating_point(inputs)
            return replace(point, ic_a=point.ic_a * 2)

        with patch("app.calculate_nodal_operating_point", side_effect=wrong_nodal):
            response = self.client.post("/", data=VALID)
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('data-status="MISMATCH"', body)
        self.assertIn("MISMATCH", body)
        self.assertNotIn('data-status="MATCH"', body)

    def test_calculation_error_renders_form_error(self):
        with patch("app.calculate_operating_point", side_effect=ValueError("boom")):
            response = self.client.post("/", data=VALID)
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "ไม่สามารถคำนวณจุดทำงานได้", response.get_data(as_text=True)
        )

    def test_get_includes_circuit_diagram(self):
        body = self.client.get("/").get_data(as_text=True)
        self.assertIn('data-circuit="bjt-ce"', body)
        self.assertIn('aria-label="BJT common-emitter circuit"', body)
        self.assertIn(
            "<title>BJT common-emitter voltage-divider bias circuit</title>",
            body,
        )
        self.assertIn(">Q1<", body)

    def test_valid_post_includes_circuit_diagram(self):
        body = self.client.post("/", data=VALID).get_data(as_text=True)
        self.assertIn('data-circuit="bjt-ce"', body)


if __name__ == "__main__":
    unittest.main()
