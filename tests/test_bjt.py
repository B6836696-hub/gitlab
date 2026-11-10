import math
import unittest

from bjt import BiasInputs, validate_inputs

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


if __name__ == "__main__":
    unittest.main()
