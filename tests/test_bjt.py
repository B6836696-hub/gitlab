import math
import unittest

from bjt import BiasInputs, validate_inputs
from bjt import VCE_SAT_V, calculate_operating_point, classify_region

VALID = {
    "vcc": "12", "r1": "47000", "r2": "10000", "rc": "2200",
    "re": "1000", "beta": "150", "vbe": "0.7",
}


class TestValidateInputs(unittest.TestCase):
    def test_accepts_valid_inputs(self):
        inputs, errors = validate_inputs(VALID)
        self.assertEqual(errors, {})
        self.assertIsInstance(inputs, BiasInputs)
        self.assertAlmostEqual(inputs.vcc_v, 12.0)
        self.assertAlmostEqual(inputs.beta, 150.0)

    def test_rejects_non_numeric(self):
        inputs, errors = validate_inputs(dict(VALID, vcc="abc"))
        self.assertIsNone(inputs)
        self.assertEqual(errors["vcc"], "กรุณากรอกเป็นตัวเลข")

    def test_rejects_missing_field(self):
        raw = dict(VALID)
        del raw["r1"]
        inputs, errors = validate_inputs(raw)
        self.assertIsNone(inputs)
        self.assertIn("r1", errors)

    def test_rejects_non_finite(self):
        for value in ("nan", "inf", "-inf"):
            with self.subTest(value=value):
                inputs, errors = validate_inputs(dict(VALID, vcc=value))
                self.assertIsNone(inputs)
                self.assertEqual(errors["vcc"], "ต้องเป็นจำนวนจำกัด")

    def test_rejects_non_positive_supply(self):
        inputs, errors = validate_inputs(dict(VALID, vcc="0"))
        self.assertIsNone(inputs)
        self.assertEqual(errors["vcc"], "ต้องมากกว่า 0 V")

    def test_rejects_non_positive_resistors(self):
        for field in ("r1", "r2", "rc", "re"):
            with self.subTest(field=field):
                inputs, errors = validate_inputs(dict(VALID, **{field: "0"}))
                self.assertIsNone(inputs)
                self.assertIn(field, errors)

    def test_rejects_beta_below_one(self):
        inputs, errors = validate_inputs(dict(VALID, beta="0.9"))
        self.assertIsNone(inputs)
        self.assertEqual(errors["beta"], "ต้องมีค่าอย่างน้อย 1")

    def test_rejects_vbe_outside_range(self):
        for value in ("-0.1", "12", "20"):
            with self.subTest(value=value):
                inputs, errors = validate_inputs(dict(VALID, vbe=value))
                self.assertIsNone(inputs)
                self.assertEqual(errors["vbe"], "ต้องอยู่ระหว่าง 0 ถึง VCC")

    def test_accepts_vbe_above_vbb_as_cutoff(self):
        # VBE above the divider voltage is a valid cutoff circuit, not an input error.
        inputs, errors = validate_inputs(dict(VALID, r2="1000"))
        self.assertEqual(errors, {})
        self.assertIsNotNone(inputs)


class TestCalculateOperatingPoint(unittest.TestCase):
    def test_worked_example(self):
        inputs, _ = validate_inputs(VALID)
        result = calculate_operating_point(inputs)
        self.assertAlmostEqual(result.vbb_v, 2.1052631579, places=9)
        self.assertAlmostEqual(result.rb_ohm, 8245.614035, places=6)
        self.assertAlmostEqual(result.ib_a, 8.8245014873e-6, places=15)
        self.assertAlmostEqual(result.ic_a, 1.3236752231e-3, places=12)
        self.assertAlmostEqual(result.ie_a, 1.3324997246e-3, places=12)
        self.assertAlmostEqual(result.ve_v, 1.3324997246, places=9)
        self.assertAlmostEqual(result.vb_v, 2.0324997246, places=9)
        self.assertAlmostEqual(result.vc_v, 9.0879145092, places=9)
        self.assertAlmostEqual(result.vce_v, 7.7554147846, places=9)
        self.assertEqual(result.region, "active")
        self.assertIsNone(result.ic_sat_a)

    def test_cutoff_when_vbb_below_vbe(self):
        inputs, _ = validate_inputs(dict(VALID, r2="1000"))
        result = calculate_operating_point(inputs)
        self.assertEqual(result.region, "cutoff")
        self.assertEqual(result.ib_a, 0.0)
        self.assertEqual(result.ic_a, 0.0)
        self.assertEqual(result.ie_a, 0.0)
        self.assertEqual(result.ve_v, 0.0)
        self.assertAlmostEqual(result.vb_v, 0.25, places=12)
        self.assertEqual(result.vc_v, 12.0)
        self.assertEqual(result.vce_v, 12.0)

    def test_saturation_and_limit_current(self):
        inputs, _ = validate_inputs(dict(VALID, rc="10000", re="100"))
        result = calculate_operating_point(inputs)
        self.assertEqual(result.region, "saturation")
        self.assertLess(result.vce_v, VCE_SAT_V)
        self.assertAlmostEqual(
            result.ic_sat_a, (12.0 - VCE_SAT_V) / (10000.0 + 100.0), places=12
        )

    def test_classify_region_boundary(self):
        self.assertEqual(classify_region(1e-6, 0.2), "saturation")
        self.assertEqual(classify_region(1e-6, 0.2000001), "active")
        self.assertEqual(classify_region(0.0, 5.0), "cutoff")

    def test_large_finite_inputs_stay_finite(self):
        raw = dict(
            VALID, vcc="1000000", r1="1000000000", r2="1000000000",
            rc="1000000", re="1000000", beta="1000000",
        )
        inputs, _ = validate_inputs(raw)
        result = calculate_operating_point(inputs)
        for value in (
            result.vbb_v, result.rb_ohm, result.ib_a, result.ic_a,
            result.ie_a, result.ve_v, result.vb_v, result.vc_v, result.vce_v,
        ):
            self.assertTrue(math.isfinite(value))


if __name__ == "__main__":
    unittest.main()
